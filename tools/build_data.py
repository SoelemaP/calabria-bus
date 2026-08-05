#!/usr/bin/env python3
"""
build_data.py — merge parsed schedules + stops.csv + calendar.json -> data.json
(the file the app fetches).

    python3 tools/build_data.py

Reads:  build/schedules.json  (from parse_quadri.py)
        stops.csv             (coordinates you filled/verified)
        calendar.json         (school terms & breaks)
Writes: data.json
"""
import json, csv, sys, os
DELIM=';'
def num(x):
    x=(x or '').strip().replace(',','.')
    try: return float(x)
    except: return None

sched=json.load(open('build/schedules.json',encoding='utf-8'))
cal=json.load(open('calendar.json',encoding='utf-8'))
coords={}
for row in csv.DictReader(open('stops.csv',encoding='utf-8'),delimiter=DELIM):
    coords[row['stop_id']]={'lat':num(row.get('lat')),'lng':num(row.get('lng')),
                            'name':row['name'],'request':row.get('richiesta','')=='R'}

# stops = every stop referenced by a route, enriched with coords
used=set()
for r in sched['routes']: used.update(r['stopIds'])
stops=[]
missing=[]
for sid in used:
    c=coords.get(sid)
    if not c:
        missing.append(sid); 
        stops.append({'id':sid,'name':sid,'request':False,'lat':None,'lng':None}); continue
    stops.append({'id':sid,'name':c['name'],'request':c['request'],'lat':c['lat'],'lng':c['lng']})

data={'lines':sched['lines'],'stops':stops,'routes':sched['routes'],
      'trips':sched['trips'],'calendar':cal}
json.dump(data,open('data.json','w'),ensure_ascii=False,indent=1)

withcoord=sum(1 for s in stops if s['lat'] is not None)
print(f"data.json: {len(data['lines'])} lines, {len(stops)} stops "
      f"({withcoord} with coords), {len(data['trips'])} trips")
if missing:
    print(f"WARNING: {len(missing)} route stops not found in stops.csv (run parse_quadri.py first)")
