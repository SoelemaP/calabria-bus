# Calabria Bus

Commuter app for Consorzio Autolinee TPL bus lines in the Cosenza / Rende area.
Pick origin and destination and it shows only the corse valid for that date;
browse any line to see its full quadro orario and route on a map.

The app is a single static file (`index.html`) that reads its data from
`data.json`. Data is generated from the official PDF quadri orari by the scripts
in `tools/`, so updating schedules never means touching the app code.

## Repository layout

```
index.html          The app (static; no build step)
data.json           Runtime data the app fetches: lines, stops, routes, trips, calendar
calendar.json       School terms & breaks (drives Scol / Non Scol validity) — edit by hand
stops.csv           One row per stop; you fill lat/lng here (semicolon-delimited)
periodicity.js      Reference copy of the validity logic (same rules the app uses)
tools/
  parse_quadri.py   PDFs -> build/schedules.json, and syncs new stops into stops.csv
  geocode.py        Optional: pre-fill stops.csv coordinates from OpenStreetMap (run locally)
  build_data.py     build/schedules.json + stops.csv + calendar.json -> data.json
schedules/          Source PDF quadri orari (optional to commit)
requirements.txt    pdfplumber
```

## How validity works (the important part)

Each corsa (trip) carries two independent tags from the PDF:

- **Periodo** (`Fer`, `Fer*`, `Est`, `Est*`, `Fest`, `Fest*`, `Non Scol`,
  `Non Scol*`, `Scol`, `Univ`, `Univ*`) — a **date window**.
- **Cadenza** (`LMmGVS_`) — a **day-of-week mask** (Mon…Sun; `_` = off).

A corsa is shown on a date **d** iff `dayMatch(d) AND periodMatch(d)`:

- `dayMatch` — the cadenza admits d's day. **Holidays collapse to Sunday**, so
  weekday-only corse drop out on holidays (e.g. Feriale on 1 May) while Sunday/
  festivo corse still show. Italian holidays incl. Easter are computed in code.
- `periodMatch` — d falls inside that Periodo's window. Note the asterisk is
  **not** a uniform modifier: for `Fer*/Fest*/Non Scol*` it means "except
  August", for `Est*` a shorter range, for `Univ*` "excludes July" — each code
  is its own explicit predicate.

The daily timetable is the **union** of every corsa passing both tests, so
overlapping periods (a weekday that is also school term and university term)
resolve automatically without priorities.

## Updating schedules

```bash
pip install -r requirements.txt

# 1. drop the new PDF quadri in schedules/, then parse them
python3 tools/parse_quadri.py schedules/*.pdf
#    -> writes build/schedules.json and adds any NEW stops to stops.csv
#       (coordinates already in stops.csv are preserved)

# 2. (optional) auto pre-fill coordinates for blank rows — GUESSES, verify them
python3 tools/geocode.py

# 3. open stops.csv, fill/correct lat & lng, set verificato=yes on good ones

# 4. build the app data
python3 tools/build_data.py
#    -> writes data.json
```

Commit `index.html`, `data.json`, `stops.csv`, `calendar.json`.

## Running it

- **GitHub Pages** (or any web host): just serve the folder — `index.html`
  fetches `data.json` over http(s). Pages requires a public repo on the free plan.
- **Locally:** `python3 -m http.server` then open `http://localhost:8000`.
  Opening `index.html` directly from disk (`file://`) won't work — browsers
  block `fetch` on `file://`.

## Not yet built

- **Transfers.** Search matches direct single-line journeys only; changing
  between lines is a separate routing feature.
- **Private map.** A static site exposes `data.json` to anyone; the timetables
  are public data, so this is fine, but don't put anything sensitive in it.
