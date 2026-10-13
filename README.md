# FieldDx

**Differential diagnosis for farm fields.** Satellites can tell you *that* a field changed. FieldDx tells a field officer *what probably happened, what it definitely wasn't, and the one cheapest check that settles it.*

It runs after a satellite alert, the way an agronomist would:

1. Is the signal real? (cloud, shadow, mixed boundary pixels)
2. Is it expected, or shared with the area? (management windows, neighbours, weather)
3. If it is this field only, which causes fit the evidence, and which single on-site check separates the top two?

The officer gets a **case file**, not a heatmap: ranked hypotheses where every line cites evidence (`E1`, `E4`), the false alarms thrown out with their reasons, and a "next best check" slip. When she reports back, the finding becomes new evidence and the ranking updates.

> **Data honesty.** Every case in this repository runs on a **simulated** dataset shaped like a Sentinel-2 export (12 plots near Niphad, Nashik; cluster weather). It is not real imagery, and the UI says so on every case. The Earth Engine export script is not included yet. Crop-calendar management windows are placeholders marked *assumed, unverified* until confirmed with an agronomist.

## How it works

- **Deterministic tools** (`backend/app/tools`) turn the cached data into evidence: scene quality, NDVI change, boundary check (re-run with a 10 m inner buffer), neighbour comparison, spatial pattern, weather, crop calendar.
- **A rule table** (`backend/app/engine/rules.py`) scores ten hypotheses in three stages. Stage 1 and 2 gates dismiss the case with a reason; Stage 3 ranks field-specific causes. If nothing clears the evidence bar the answer is **"Unexplained, visit"**, never a forced guess.
- **Next best check** (`backend/app/next_check.py`) is computed, not written by a model: `score = how cleanly a result splits the top two ÷ minutes on site`. The candidate table is shown under "Why this check?".
- **The LLM never invents a cause.** Gemini (optional) only writes the plain-language case file from the evidence list. Its output is validated: every line must cite known evidence IDs, hypotheses must be in the engine's order. One retry, then a template narrative. With no key the app works the same.
- **A real map, at pixel level.** Each case opens on a Leaflet map (Esri satellite or OpenStreetMap) with the field painted as 10 m NDVI pixels. Switch between NDVI, Change against the field's baseline, and plain satellite; pick any pass from the scene bar; compare two dates side by side; hover a pixel to read it.
- **Honest about resolution.** Cloudy passes stay in the scene bar but are disabled and never show a number. Hazy scenes mask the affected pixels. The map can draw the 10 m grid, and each case carries a limits note.

Not modelled yet: red-edge (NDRE) evidence, real elevation for waterlogging, and live satellite ingestion. Storm/hail and waterlogging are scored from weather only.

## Demo cases

| Case | Plot | What it shows | Outcome |
|---|---|---|---|
| C1 | 07 onion | Drop on the east edge, 12 dry days, neighbours fine | Irrigation failure (high), next check: the east drip line |
| C4 | 09 onion | A patch that spreads across three scenes after a wet, humid spell | Pest or disease (high), next check: leaf undersides |
| C6 | 12 onion | Confirmed drop that fits no pattern | Unexplained, visit checklist |
| C2 | 10 onion | One hazy scene | Dismissed: cloud or haze |
| C3 | 02 grape | Uniform drop inside the pruning window | Dismissed: expected management event |
| C5 | 11 onion | Edge drop that vanishes inside the 10 m buffer | Dismissed: boundary mixing |

## Run it

Requires Python 3.11+ and Node 20+.

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

**Rebuild the data.** `python scripts/build_scenarios.py` regenerates `data/` deterministically.

**Tests.**

```bash
cd backend && python -m pytest
```

They cover each tool on the simulated series, one golden outcome per scenario, citation integrity (including a model answer with an invented evidence ID, which must fall back), next-check selection, and the close-case API.

## Layout

```
backend/app   tools/ engine/ next_check.py pipeline.py raster.py narrative.py llm.py resolve.py db.py main.py
backend/tests pytest suite
frontend/src  pages/ components/ styles/ (design tokens from DESIGN.md)
data/         simulated fields, scenes, weather, calendar, checks, scenarios
scripts/      build_scenarios.py
DESIGN.md     the visual language
idea.md       the concept and the hypothesis table
```

## Sources and attribution

- Basemaps: Esri World Imagery (satellite) and OpenStreetMap contributors (street), shown through Leaflet with their attributions.
- The NDVI colour scale, its interpretation bins and the map interaction pattern come from the author's earlier project, Pragya (the scale follows the EOS NDVI colormap convention).
- Imagery and weather values in the demo are simulated. A real build would use Copernicus Sentinel-2 L2A and the Open-Meteo historical archive.
