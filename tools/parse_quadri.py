#!/usr/bin/env python3
"""
parse_quadri.py  —  Consorzio Autolinee TPL quadri orari -> build/schedules.json
                    and keeps stops.csv in sync (adds new stops, never touches
                    coordinates you've already filled in).

Usage:
    python3 tools/parse_quadri.py schedules/*.pdf

It VALIDATES each page before trusting it. Pages whose N Corsa / Periodo /
Cadenza / Km Tot header block is missing, or whose columns don't line up, are
skipped and reported by name instead of producing garbage times.
"""
import sys, re, os, json, glob
import pdfplumber

PALETTE = ["#2563EB","#DC2626","#059669","#D97706","#7C3AED","#0891B2",
           "#DB2777","#65A30D","#EA580C","#4F46E5","#0D9488","#B91C1C"]

def slug(name):
    s = re.sub(r'[^a-z0-9]+','_', name.lower()).strip('_')
    return 's_'+s[:40]

def clean_time(t):
    t=(t or '').strip()
    return t if (re.fullmatch(r'\d{2}:\d{2}',t) and t!='00:00') else None

def parse_page(page):
    text = page.extract_text() or ''
    mline = re.search(r'Linea\s*N[°º]\s*(\d+)\s+(.+)', text)
    if not mline:
        return None, "no 'Linea N°' header"
    num = mline.group(1)
    name = re.split(r'\s{2,}|Macroitinerario', mline.group(2))[0].strip()
    direction = 'andata' if 'Corse Andata' in text else ('ritorno' if 'Corse Ritorno' in text else None)
    if not direction:
        return None, "no 'Corse Andata/Ritorno'"
    tables = page.extract_tables()
    if not tables:
        return None, "no table found"
    tbl = max(tables, key=len)
    hdr={}; stop_rows=[]
    for row in tbl:
        label=(row[1] or '').strip() if len(row)>1 and row[1] else ''
        first=(row[0] or '').strip() if row[0] else ''
        if first=='FERMATE' or label=='N° Corsa': hdr['corsa']=[(c or '').strip() for c in row[2:]]
        elif label=='Periodo':  hdr['periodo']=[(c or '').strip() for c in row[2:]]
        elif label=='Cadenza':  hdr['cadenza']=[(c or '').strip() for c in row[2:]]
        elif label=='Km Tot':   hdr['km']=[(c or '').strip() for c in row[2:]]
        elif first:             stop_rows.append((first,[(c or '').strip() for c in row[2:]]))
    # --- validation ---
    for key in ('corsa','periodo','cadenza'):
        if key not in hdr: return None, f"missing '{key}' header row"
    n=len(hdr['corsa'])
    if not (len(hdr['periodo'])==n and len(hdr['cadenza'])==n):
        return None, "header columns misaligned"
    if not stop_rows: return None, "no stop rows"
    bad=[nm for nm,cells in stop_rows if len(cells)<n]
    if bad: return None, f"{len(bad)} stop rows have too few columns (first: {bad[0]!r})"
    return {'num':num,'name':name,'direction':direction,'hdr':hdr,'stops':stop_rows}, None

def main(patterns):
    files=[]
    for p in patterns: files+=glob.glob(p)
    if not files:
        print("No PDFs matched.", file=sys.stderr); sys.exit(1)

    lines={}; routes={}; trips=[]; stop_names={}; warnings=[]
    color_idx={}
    for path in sorted(files):
        with pdfplumber.open(path) as pdf:
            for pi,page in enumerate(pdf.pages):
                parsed,err = parse_page(page)
                if err:
                    warnings.append(f"{os.path.basename(path)} p{pi+1}: {err}")
                    continue
                num=parsed['num']; lid='l_'+num
                if lid not in lines:
                    ci=color_idx.setdefault(num, len(color_idx))
                    lines[lid]={'id':lid,'number':num,'name':parsed['name'],'color':PALETTE[ci%len(PALETTE)]}
                stop_ids=[]
                for nm,_ in parsed['stops']:
                    sid=slug(nm); stop_ids.append(sid)
                    stop_names.setdefault(sid, nm)
                # route key allows deviation variants on same line+direction
                key=(lid,parsed['direction'],tuple(stop_ids))
                if key not in routes:
                    same=[r for r in routes.values() if r['lineId']==lid and r['direction']==parsed['direction']]
                    suffix='' if not same else f"_v{len(same)+1}"
                    rid=f"r_{num}_{parsed['direction']}{suffix}"
                    routes[key]={'id':rid,'lineId':lid,'direction':parsed['direction'],'stopIds':stop_ids}
                rid=routes[key]['id']
                hdr=parsed['hdr']
                for ci in range(len(hdr['corsa'])):
                    times={}
                    for si,(nm,cells) in enumerate(parsed['stops']):
                        ct=clean_time(cells[ci] if ci<len(cells) else '')
                        if ct: times[stop_ids[si]]=ct
                    dep=next((times[s] for s in stop_ids if s in times), None)
                    trips.append({'id':f"t_{hdr['corsa'][ci]}",'routeId':rid,
                                  'corsaNo':hdr['corsa'][ci],
                                  'periodo':hdr['periodo'][ci],'cadenza':hdr['cadenza'][ci],
                                  'departure':dep,'times':times})

    os.makedirs('build', exist_ok=True)
    json.dump({'lines':list(lines.values()),
               'routes':list(routes.values()),
               'trips':trips},
              open('build/schedules.json','w'), ensure_ascii=False, indent=1)

    sync_stops_csv(stop_names)

    print(f"OK  lines={len(lines)} routes={len(routes)} trips={len(trips)} stops={len(stop_names)}")
    if warnings:
        print(f"\n{len(warnings)} page(s) SKIPPED — check these:")
        for w in warnings: print("  -", w)

def sync_stops_csv(stop_names, path='stops.csv'):
    """Add a row for every new stop; preserve existing coords/verified flags."""
    hdr=['stop_id','name','comune','zona','richiesta','geocode_query','lat','lng','fonte','geocode_match','verificato']
    existing={}
    if os.path.exists(path):
        with open(path,encoding='utf-8') as f:
            cols=f.readline().rstrip('\n').split(';')
            for ln in f:
                vals=ln.rstrip('\n').split(';')
                row=dict(zip(cols,vals))
                existing[row['stop_id']]=row
    def build_row(sid,name):
        comune = name.split('(')[0].strip().title() if '(' in name else name.title()
        m=re.search(r'\((.*)\)',name); inside=m.group(1) if m else ''
        zona=inside.split('-',1)[0].strip()
        q=re.sub(r'a rich\.?','',inside,flags=re.I).replace('n.c.',' ').replace('-',', ')
        q=re.sub(r'\s*,\s*',', ',q); q=re.sub(r'\s+',' ',q).strip().strip(',').strip()
        return {'stop_id':sid,'name':name,'comune':comune,'zona':zona,
                'richiesta':'R' if 'a rich' in name.lower() else '',
                'geocode_query':f"{q}, {comune}, Italia",'lat':'','lng':'',
                'fonte':'','geocode_match':'','verificato':'no'}
    added=0
    for sid,name in stop_names.items():
        if sid not in existing:
            existing[sid]=build_row(sid,name); added+=1
    with open(path,'w',encoding='utf-8') as f:
        f.write(';'.join(hdr)+'\n')
        for sid in existing:
            r=existing[sid]; f.write(';'.join(str(r.get(k,'')) for k in hdr)+'\n')
    print(f"stops.csv: +{added} new, {len(existing)} total (existing coords preserved)")

if __name__=='__main__':
    main(sys.argv[1:] or ['schedules/*.pdf'])
