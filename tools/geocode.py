#!/usr/bin/env python3
"""
geocode.py — OPTIONAL first-pass coordinates for stops.csv via OpenStreetMap Nominatim.

Run LOCALLY (needs internet). Fills lat/lng ONLY for rows that are still empty
and not marked verificato=yes. It writes fonte=nominatim and the matched address
into geocode_match so you can sanity-check. THESE ARE GUESSES — verify each one,
then set verificato=yes. Landmark and 'a richiesta' stops will often be wrong.

    python3 tools/geocode.py            # fill empty rows
    python3 tools/geocode.py --all      # re-geocode even rows that have coords (except verificato=yes)

Respects Nominatim's policy: 1 request/second, descriptive User-Agent.
"""
import csv, sys, time, json, urllib.parse, urllib.request

CSV='stops.csv'; DELIM=';'
UA='calabria-bus/1.0 (personal timetable project; contact: you@example.com)'
REDO='--all' in sys.argv

def geocode(q):
    url='https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode(
        {'q':q,'format':'json','limit':1,'countrycodes':'it'})
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=20) as r:
        data=json.load(r)
    if not data: return None
    d=data[0]; return float(d['lat']),float(d['lon']),d.get('display_name','')

rows=list(csv.DictReader(open(CSV,encoding='utf-8'),delimiter=DELIM))
fields=rows[0].keys() if rows else []
done=0; miss=0
for row in rows:
    if row.get('verificato','').lower()=='yes': continue
    if row.get('lat') and not REDO: continue
    q=row.get('geocode_query') or row.get('name')
    try:
        res=geocode(q)
    except Exception as e:
        print('ERR',q,e); res=None
    if res:
        lat,lng,disp=res
        row['lat']=f'{lat:.6f}'; row['lng']=f'{lng:.6f}'
        row['fonte']='nominatim'; row['geocode_match']=disp[:80]
        done+=1; print(f'OK  {row["name"][:40]:40}  {lat:.5f},{lng:.5f}')
    else:
        miss+=1; print(f'--  {row["name"][:40]:40}  no match')
    time.sleep(1.0)  # be polite

with open(CSV,'w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(fields),delimiter=DELIM)
    w.writeheader(); w.writerows(rows)
print(f'\nfilled={done} missed={miss}. Now VERIFY each point and set verificato=yes.')
