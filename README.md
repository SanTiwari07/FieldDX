# FieldDx

**Differential diagnosis for farm fields.** Satellites can tell you *that* a field changed. FieldDx tells a field officer *what probably happened, what it definitely wasn't, and the one cheapest check that settles it.*

It runs after a satellite alert, the way an agronomist would:

1. Is the signal real? (cloud, shadow, mixed boundary pixels, a single odd pass)
2. Is it expected, or shared with the area? (harvest or pruning season, neighbours, weather)
3. If it is this field only, which causes fit the evidence, and what is the cheapest thing to ask or check?

The officer gets a **case file**, not a heatmap: ranked hypotheses where every line cites evidence (`E1`, `E4`), the false alarms thrown out with their reasons, and a next-step slip. When she reports back, the finding becomes new evidence and the ranking updates.

## Everything is real data

Nothing in the app is simulated. Every number traces back to a real source:

| What | Source |
|---|---|
| Field shapes | **Fields of the World** (FTW) segmentation model, PRUE EfficientNet-B5 (CC-BY weights), run on real Sentinel-2 scenes of Niphad, Nashik. A shape is a model prediction (a remote-sensing field unit), not a legal parcel. |
| Imagery | Copernicus **Sentinel-2 L2A** at 10 m through Google Earth Engine. Clouds, shadow and cirrus are masked per pixel with **Cloud Score+** (0.60) and the scene classification layer. |
| Cropland | ESA WorldCover 2021 keeps only cropland (no river, town or trees). |
| Weather | **Open-Meteo** archive (ERA5 / ERA5-Land reanalysis): rain, heat, humidity and soil moisture. |
| Alerts | Detected from the data (`scripts/build_cases.py`): a zone at least 0.10 NDVI below the field's own baseline on a clear pass in the last 21 days. No case is hand-picked. |

What is **assumed and says so**: the crop is not known, so each field is called *perennial canopy* or *seasonal crop* from a year of NDVI, and the harvest and fruit-pruning windows are placeholders until an agronomist confirms them. Every case says when it relies on one.

The published FTW global vectors are sparse over smallholder Nashik (about 170 polygons in a 55 × 38 km box), so the model is run directly on the area; `scripts/ftw_fields.py` wraps the official `ftw` CLI.

## How it works

- **Deterministic tools** (`backend/app/tools`) turn real pixels into cited evidence: scene quality, NDVI change per zone, boundary check (re-run with a 10 m inner buffer), neighbour comparison, spatial pattern, weather, crop calendar.
- **Zones follow the real shape.** Each field's 10 m pixels are split into an analysis area (shape shrunk 10 m), four interior quadrants, four edges and an unshrunk 20 m ring used only for the boundary check.
- **A rule table** (`backend/app/engine/rules.py`) scores ten hypotheses in three stages. Stage 1 and 2 gates dismiss the case with a reason, or raise an area alert; stage 3 ranks field-specific causes. A drop seen on only one clear pass is *watched*, not escalated. If nothing clears the bar the answer is **"ask or visit"**, never a forced guess.
- **Next best check** (`backend/app/next_check.py`) is computed, not written by a model: `score = how cleanly a result splits the top two ÷ minutes`. The candidate table is under "Why this check?".
- **The LLM never invents a cause.** Gemini (optional) only writes the plain-language case file from the evidence list. Its output is validated: every line must cite known evidence IDs, hypotheses must be in the engine's order. One retry, then a template narrative. With no key the app works the same.
- **A real map at pixel level.** Leaflet on Esri satellite imagery (or OpenStreetMap), the field painted as its real 10 m NDVI pixels. Switch between NDVI, Change against the pixel's own baseline, and plain satellite; pick any real pass from the scene bar; compare two dates; hover a pixel. Cloudy passes stay in the scene bar but disabled, and never show a number.
- **Honest about resolution.** Each case carries a limits note, and the inbox has a map of every monitored field coloured by outcome.

Not modelled yet: red-edge (NDRE) evidence, elevation for waterlogging, a real crop calendar. Storm damage and waterlogging are scored from weather only.

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

For a single process, run `npm run build` in `frontend/` and the API serves the built app at `http://localhost:8000`.

**Gemini (optional).** Copy `.env.example` to `.env` and set `GEMINI_API_KEY` (and `GEMINI_MODEL` if you want another model). Set `FIELDDX_LLM=off` to force the template narrative. Narratives are stored in SQLite so a replay never depends on a live call.

**Starting a clean take.** The "Reset demo" button (or `POST /api/admin/reset`) clears closed cases and stored narratives. `DEMO_PACING` (milliseconds, default 550) sets the pause between investigation steps.

**Tests.** `cd backend && python -m pytest`. The engine logic is tested on a tiny hand-built fixture with known answers (an edge drop, a hazy pass, a boundary artefact, a pruning wave, a spreading patch...), and the real dataset is tested for invariants: real polygons, grids and scenes line up, cloudy passes carry no values, every case cites only evidence it has, and the API serves a whole case.

## Rebuild the data

All steps need network access; Earth Engine needs `earthengine authenticate` once. `pip install -r scripts/requirements.txt`.

```bash
# 1. real field boundaries (Fields of the World model, run in its own environment)
python scripts/ftw_fields.py --bbox 74.09 20.055 74.14 20.10 --year 2025

# 2. real Sentinel-2 pixels, Cloud Score+ and SCL, plus WorldCover, on a 10 m UTM grid
python scripts/export_s2.py --bbox 74.09 20.055 74.14 20.10 --start 2025-10-01 --end 2026-10-13 --out data/raw/s2

# 3. real weather
python scripts/fetch_weather.py --lat 20.0775 --lon 74.115 --start 2026-06-01 --end 2026-10-12 --out data/weather/niphad.json

# 4. select fields, build the pixel zones, cut every field out of every scene
python scripts/build_dataset.py

# 5. detect the alerts
python scripts/build_cases.py
```

## Layout

```
backend/app   tools/ engine/ next_check.py pipeline.py raster.py narrative.py llm.py resolve.py data.py main.py
backend/tests logic tests on a fixture, invariants on the real data
frontend/src  pages/ components/ styles/ (design tokens from DESIGN.md)
data/         fields.geojson, grids/, scenes/, weather/, cases.json, calendar.json, checks.json
scripts/      ftw_fields.py export_s2.py fetch_weather.py build_dataset.py build_cases.py
DESIGN.md     the visual language
idea.md       the concept and the hypothesis table
```

## Sources and licences

- Field boundaries: Fields of the World, Robinson et al., <https://fieldsofthe.world>; model weights CC-BY-4.0; code MIT.
- Imagery: contains modified Copernicus Sentinel data, via Google Earth Engine and Cloud Score+ (Google).
- Land cover: ESA WorldCover 2021 (CC-BY-4.0).
- Weather: Open-Meteo, ERA5 and ERA5-Land reanalysis (CC-BY-4.0).
- Basemaps: Esri World Imagery and OpenStreetMap contributors, through Leaflet.
- The NDVI colour scale, its interpretation bins and the map interaction pattern come from the author's earlier project, Pragya.
