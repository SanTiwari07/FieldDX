# FieldDx

**Differential diagnosis for farm fields.** Satellites can tell you *that* a field changed. FieldDx tells a field officer *what probably happened, what it definitely wasn't, and the one cheapest check that settles it.*

It runs after a satellite alert, the way an agronomist would:

1. Is the signal real? (cloud, shadow, mixed boundary pixels, a single odd pass)
2. Is it expected, or shared with the area? (harvest or pruning season, neighbours, weather)
3. If it is this field only, which causes fit the evidence, and what is the cheapest thing to ask or check?

The officer gets a **case file**, not a heatmap: ranked hypotheses where every line cites evidence (`E1`, `E4`), the false alarms thrown out with their reasons, and a next-step slip. When she reports back, the finding becomes new evidence and the ranking updates.

## The flow

```
Sign in ─► Region overview ─► Go to the land, mark it ─► FieldDx builds it ─► Today's briefing ─► Cases ─► Investigation ─► Next check ─► Visit and close
```

1. **Sign in.** An officer creates an account (username and a 4 to 8 digit PIN) or signs in. *Explore the demo area* opens the shipped Niphad area without an account.
2. **Find your region and see what is changing.** Search a district, taluka or village (OpenStreetMap). The map locks to that region's real boundary and paints this fortnight's change in cropland NDVI across all of it, computed live in Google Earth Engine from cloud-masked Sentinel-2. A summary gives the share of cropland that lost or gained greenness and the places where most of it dropped ("around Karambali, 64% of cropland"). Tap one to fly there. This is a screen, not a diagnosis: harvest shows up here too.
3. **Go to the land and mark it.** Type a farm's coordinates to fly to it, or zoom in, then:
   - **draw a polygon** around the land, or
   - **pick fields** on the published Fields of the World map for that state (the shapes stream in as PMTiles), or
   - **type corners**: one point for a square of 2 to 12 km, or three or more corners.

   A colleague's area can also be joined as it is.
4. **FieldDx builds it** from real sources, for that polygon only, with live progress: field shapes, about 13 months of Sentinel-2, weather, 10 m pixel zones, the harvest season, then the alerts. A small area takes a few minutes; you can leave the page.
5. **Today's briefing** shows what happened to this week's passes: fields watched, alerts raised, how many were dismissed and why, area-wide events, and the few fields that need a call or a visit, with where to start.
6. **Cases, investigation, next check, close** work as before, and every route reads only the officer's own area. Another area's case IDs answer 404.

## Everything is real data

Nothing in the app is simulated. Every number traces back to a real source:

| What | Source |
|---|---|
| Field shapes | **Fields of the World** (FTW). Either the published **FTW Global** map (PRUE model, 2024 and 2025, about 3.2 billion fields, read per state from Source Cooperative), or the FTW model (PRUE EfficientNet-B5, CC-BY weights) run on fresh Sentinel-2 scenes of the area, as for the Niphad demo. A shape is a model prediction (a remote-sensing field unit), not a legal parcel. |
| Places | **OpenStreetMap** Nominatim: the region's name and real boundary, which the map locks to. |
| Imagery | Copernicus **Sentinel-2 L2A** at 10 m through Google Earth Engine. Clouds, shadow and cirrus are masked per pixel with **Cloud Score+** (0.60) and the scene classification layer. |
| Cropland | ESA WorldCover 2021 keeps only cropland (no river, town or trees). |
| Weather | **Open-Meteo** archive (ERA5 / ERA5-Land reanalysis): rain, heat, humidity and soil moisture. |
| Alerts | Detected from the data (`scripts/build_cases.py`): a zone at least 0.10 NDVI below the field's own baseline on a clear pass in the last 21 days. No case is hand-picked. |

What is **assumed and says so**: the crop is not known, so each field is called *perennial canopy* or *seasonal crop* from a year of NDVI. Management windows are not known either. In a new area the harvest season is **inferred from the area's own NDVI**: the months in which last year's median seasonal field fell by 0.10 or more. Niphad keeps its grape-pruning and kharif-harvest placeholders. None of these is verified with an agronomist, and every case says when it relies on one.

Smallholder plots are small. Fields under about 0.8 ha cannot be split into zones at 10 m, so they are not monitored, and the build says how many shapes passed.

## How it works

- **Deterministic tools** (`backend/app/tools`) turn real pixels into cited evidence: scene quality, NDVI change per zone, boundary check (re-run with a 10 m inner buffer), neighbour comparison, spatial pattern, weather, crop calendar.
- **Zones follow the real shape.** Each field's 10 m pixels are split into an analysis area (shape shrunk 10 m), four interior quadrants, four edges and an unshrunk 20 m ring used only for the boundary check.
- **A rule table** (`backend/app/engine/rules.py`) scores ten hypotheses in three stages. Stage 1 and 2 gates dismiss the case with a reason, or raise an area alert; stage 3 ranks field-specific causes. A drop seen on only one clear pass is *watched*, not escalated. If nothing clears the bar the answer is **"ask or visit"**, never a forced guess.
- **Next best check** (`backend/app/next_check.py`) is computed, not written by a model: `score = how cleanly a result splits the top two ÷ minutes`. The candidate table is under "Why this check?".
- **The LLM never invents a cause.** Gemini (optional) only writes the plain-language case file from the evidence list. Its output is validated: every line must cite known evidence IDs, hypotheses must be in the engine's order. One retry, then a template narrative. With no key the app works the same.
- **A real map at pixel level.** Leaflet on Esri satellite imagery (or OpenStreetMap), the field painted as its real 10 m NDVI pixels. Switch between NDVI, Change against the pixel's own baseline, and plain satellite; pick any real pass from the scene bar; compare two dates; hover a pixel. Cloudy passes stay in the scene bar but disabled, and never show a number.
- **Honest about resolution.** Each case carries a limits note, and the inbox has a map of every monitored field coloured by outcome.

Not modelled yet: red-edge (NDRE) evidence, elevation for waterlogging, a real crop calendar. Storm damage and waterlogging are scored from weather only.

## Accounts and areas

- Officers and sessions live in SQLite (`backend/fielddx.db`). PINs are stored as PBKDF2 hashes, and the session is an HttpOnly cookie whose token is stored hashed.
- Every case, map, timeline, raster and close route is resolved inside the signed-in officer's area. Findings and stored narratives are keyed by area.
- An area is a folder, `data/areas/<id>/`: `area.json` (the polygon and how it was marked), `fields.geojson`, `grids/`, `scenes/`, `weather.json`, `calendar.json` and `cases.json`, plus `build.json` and `build.log` while it builds. Only `data/areas/niphad` is in git. Areas built at runtime stay on the machine that built them.
- The build runs `scripts/build_area.py` in a subprocess, one area at a time. If the server stops mid-build, the build resumes when the server starts again, and the imagery already downloaded is kept.
- The state's FTW PMTiles reach the browser through `/api/ftw/<state>.pmtiles`, a small byte-range proxy with a cache, because many networks drop the HTTP/3 connections Source Cooperative offers.

## Run it

Requires Python 3.11+ and Node 20+. The repository ships the dataset in `data/`, so the app runs offline.

```bash
# backend
cd backend
pip install -e ".[dev]"
python -m uvicorn app.main:app --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to port 8000
```

Open the app and create an account, or choose *Explore the demo area* to go straight to Niphad. `FIELDDX_API` points the dev proxy at another API address.

For a single process, run `npm run build` in `frontend/` and the API serves the built app at `http://localhost:8000`.

**Gemini (optional).** Copy `.env.example` to `.env` and set `GEMINI_API_KEY` (and `GEMINI_MODEL` if you want another model). Set `FIELDDX_LLM=off` to force the template narrative. Narratives are stored in SQLite so a replay never depends on a live call.

**Starting a clean take.** *Reset closed cases* in the officer menu (or `POST /api/admin/reset`) clears closed cases and stored narratives in the signed-in officer's area. `DEMO_PACING` (milliseconds, default 550) sets the pause between investigation steps.

**Tests.** `cd backend && python -m pytest`. The engine logic is tested on a tiny hand-built fixture with known answers (an edge drop, a hazy pass, a boundary artefact, a pruning wave, a spreading patch...), and the real dataset is tested for invariants: real polygons, grids and scenes line up, cloudy passes carry no values, every case cites only evidence it has, and the API serves a whole case.

## Building areas

Building an area needs network access and the pipeline's packages on the server: `pip install -r scripts/requirements.txt`, and `earthengine authenticate` once. The app runs `scripts/build_area.py` for you. It can also be run by hand on any folder holding an `area.json`:

```bash
python scripts/build_area.py --area data/areas/<id>
```

It runs these steps, which also work on their own:

```bash
# field shapes: the published FTW Global map for the area's state ...
python scripts/ftw_global.py --area data/areas/<id>
# ... or the FTW model on fresh imagery (needs the ftw CLI, see scripts/ftw_fields.py; FIELDDX_FTW points at it)
python scripts/ftw_fields.py --bbox 74.07 20.04 74.16 20.12 --year 2025 --out data/areas/niphad/raw/ftw_b5

# Sentinel-2 pixels, Cloud Score+ and SCL, plus WorldCover, on a 10 m grid in the area's UTM zone
python scripts/export_s2.py --bbox 74.07 20.04 74.16 20.12 --start 2025-10-01 --end 2026-10-13 --out data/areas/niphad/raw/s2

# weather
python scripts/fetch_weather.py --lat 20.0775 --lon 74.115 --start 2026-06-01 --end 2026-10-12 --out data/areas/niphad/weather.json

# select fields, build the pixel zones, cut every field out of every scene
python scripts/build_dataset.py --area data/areas/niphad

# detect the alerts
python scripts/build_cases.py --area data/areas/niphad
```

## Layout

```
backend/app   tools/ engine/ next_check.py pipeline.py raster.py narrative.py llm.py resolve.py data.py
              areas.py (areas and builds) places.py (place search, FTW partitions) db.py main.py
backend/tests logic tests on a fixture, invariants on the real data, sign-in and area scoping
frontend/src  pages/ (SignIn, Setup, Home, Inbox, Case, Checklist) components/ styles/ session.tsx
data/         checks.json, areas/niphad/ (the shipped demo area), areas/<id>/ built at runtime
scripts/      build_area.py ftw_global.py ftw_fields.py export_s2.py fetch_weather.py build_dataset.py build_cases.py
DESIGN.md     the visual language
idea.md       the concept and the hypothesis table
```

## Sources and licences

- Field boundaries: Fields of the World, Robinson et al., <https://fieldsofthe.world>; model weights CC-BY-4.0; code MIT. FTW Global map: Robinson et al. 2026, "The first global agricultural field boundary map at 10 m resolution" (arXiv:2605.11055), CC-BY-4.0, on Source Cooperative.
- Places and boundaries: OpenStreetMap contributors (ODbL), through Nominatim.
- Imagery: contains modified Copernicus Sentinel data, via Google Earth Engine and Cloud Score+ (Google).
- Land cover: ESA WorldCover 2021 (CC-BY-4.0).
- Weather: Open-Meteo, ERA5 and ERA5-Land reanalysis (CC-BY-4.0).
- Basemaps: Esri World Imagery and OpenStreetMap contributors, through Leaflet.
- The NDVI colour scale, its interpretation bins and the map interaction pattern come from the author's earlier project, Pragya.
