# FieldDx

**Differential diagnosis for farm fields.** Satellites can tell a field officer *that* a field changed. FieldDx tells them *what probably happened, what it definitely wasn't, and the one cheapest check that settles it.*

A field officer at a farmer producer organisation looks after hundreds of smallholder plots and can visit perhaps fifteen a day. Free Sentinel-2 imagery already shows where vegetation dropped, but a red patch on a map does not say whether it is a cloud, a harvest, the whole village, or a real problem on one farm. So the alerts get ignored.

FieldDx runs the investigation that should follow every alert, the way an agronomist would:

1. **Is the signal real?** Cloud, shadow, haze, mixed boundary pixels, a single odd pass.
2. **Is it expected, or shared with the area?** Harvest or pruning season, neighbouring fields, weather.
3. **If it is this field alone, which causes fit the evidence**, and what is the cheapest thing to ask or check that tells them apart?

The officer gets a **case file**, not a heatmap: ranked causes where every line cites its evidence (`E1`, `E4`), the false alarms thrown out with their reasons, and one next check. When the officer reports back, the finding becomes new evidence and the ranking updates.

## Contents

- [The officer's flow](#the-officers-flow)
- [Quick start](#quick-start)
- [Real data, and what is assumed](#real-data-and-what-is-assumed)
- [How the diagnosis works](#how-the-diagnosis-works)
- [Areas, accounts and builds](#areas-accounts-and-builds)
- [Building an area by hand](#building-an-area-by-hand)
- [Configuration](#configuration)
- [Tests](#tests)
- [Limits](#limits)
- [Project layout](#project-layout)
- [Sources and licences](#sources-and-licences)

## The officer's flow

```
Sign in
  -> Find your region          the map locks to the district and shows what changed there this fortnight
  -> Go to the land, mark it   coordinates or a hotspot take you there; draw a polygon or pick fields
  -> FieldDx builds it         real field shapes, a year of Sentinel-2, weather, then the alerts
  -> Today's briefing          what was thrown out, what is a harvest, what is area-wide, which fields need you
  -> Check the fields map      every shape in the area, why each is or is not watched; fix what the model got wrong
  -> Case                      the investigation replays, then the diagnosis and the next check
  -> Visit and close           the finding becomes evidence and the ranking updates
```

1. **Sign in.** Create an account with a username and a 4 to 8 digit PIN, or sign in. *Explore the demo area* opens the shipped Niphad area (Nashik) without an account.
2. **Find your region.** Search a district, taluka or village. The map locks to the region's real boundary from OpenStreetMap, and paints this fortnight's change in cropland NDVI across the whole region, computed live in Google Earth Engine from cloud-masked Sentinel-2. A summary gives the share of cropland that lost or gained greenness and the places where most of it dropped, named after the nearest village ("around Karambali, 64% of cropland dropped"). This is a screen, not a diagnosis: a harvested field drops just like a failing one.
3. **Go to the land and mark it.** Type a farm's coordinates to fly to it, tap a hotspot, or zoom in. Then mark the land to examine:
   - **draw a polygon** around it (the default),
   - **pick fields** on the published Fields of the World map, whose shapes stream onto the map for the region's state, or
   - **type corners**: one point for a square of 2 to 12 km, or three or more corners.

   An area a colleague has already set up can be joined instead.
4. **FieldDx builds it.** For that polygon only, from real sources, with progress shown step by step: field shapes, about 13 months of Sentinel-2 passes, weather, 10 m pixel zones per field, the harvest season, then the alerts. A few square kilometres take five to ten minutes, and the officer can leave the page while it runs.
5. **Today's briefing.** Fields watched, alerts raised, how many are a harvest, how many were dismissed and why, area-wide events, fields waiting for another clear pass, and the few that need a call or a visit, with where to start. Drops inside the inferred harvest season are one *Harvest under way* card, which says how many of those fields had a green crop just before and that one call to a few farmers confirms it.
6. **Check the fields map, and correct it.** The map draws every field shape inside the area, not only the watched ones: watched fields in their case colour, harvest in wheat, shapes too small or too thin to read from 10 m pixels as dashed outlines, shapes that are not cropland as dotted ones, and land where no field shape was found as a cyan hatch. The area boundary is a solid line and the land outside it is dimmed. Every shape answers a tap. **Correct fields** lets the officer draw a field the model missed, split a shape that joins two farms, merge shapes that are one farm, or mark a shape as not a field. Only that field is read again from the passes already downloaded (seconds, not a rebuild); the alerts are then detected again, and every other field keeps its id and its closed cases.
7. **Cases.** Each case replays its investigation step by step, then shows the ranked diagnosis and the next best check on a phone-friendly checklist. Recording what was found closes the case and re-ranks the causes.

Every route reads only the signed-in officer's area. A case ID from another area answers "not found".

## Quick start

Requires Python 3.11 or newer and Node 20 or newer. The Niphad demo area ships in `data/`, so the app runs offline once installed.

```bash
cd backend
pip install -e ".[dev]"
python -m uvicorn app.main:app --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173> and choose **Explore the demo area**, or create an account and set up an area of your own. The dev server proxies `/api` to port 8000. For a single process, run `npm run build` in `frontend/` and the API serves the built app at <http://localhost:8000>.

The API does not reload itself. Restart it after pulling new code.

Setting up new areas and the region overview also need the pipeline packages and Earth Engine on the server:

```bash
pip install -r scripts/requirements.txt
earthengine authenticate
```

## Real data, and what is assumed

Nothing in the app is simulated. Every number traces back to a real source.

| What | Source |
|---|---|
| Field shapes | **Fields of the World** (FTW). Either the published FTW Global map (PRUE model, 2024 and 2025, about 3.2 billion fields, read per state from Source Cooperative), or the FTW model (PRUE EfficientNet-B5, CC-BY weights) run on fresh Sentinel-2 scenes of the area, as for the Niphad demo. From the published map, the latest year is the base and an earlier year's field is added where it fills a gap (at most a quarter of it under a latest-year field). A shape is a remote-sensing field unit, not a legal parcel. |
| Corrections | The **field officer**: fields drawn, split, merged or removed on the map. They are kept in the area's `edits.json`, applied again on every rebuild, and named in the provenance. |
| Places | **OpenStreetMap** through Nominatim: the region's name and real boundary. |
| Imagery | Copernicus **Sentinel-2 L2A** at 10 m through Google Earth Engine. Cloud, shadow and cirrus are masked per pixel with **Cloud Score+** (0.60) and the scene classification layer. |
| Cropland | **ESA WorldCover 2021** keeps only cropland: no river, town or trees. |
| Weather | **Open-Meteo** archive (ERA5 and ERA5-Land reanalysis): rain, heat, humidity and soil moisture. |
| Alerts | Detected from the data by `scripts/build_cases.py`: a zone at least 0.10 NDVI below the field's own baseline on a clear pass in the last 21 days. No case is hand-picked. |
| Region overview | The same Sentinel-2 and Cloud Score+ masks, computed live over the whole region: median NDVI of the last 16 days against 25 to 50 days ago, cropland only. |

What is **assumed, and says so wherever it is used**:

- **The crop is not known.** Each field is called *perennial canopy* or *seasonal crop* from a year of NDVI.
- **Management windows are not known either.** In a new area the harvest season is inferred from the area's own NDVI: the months in which last year's median seasonal field fell by 0.10 or more. Niphad keeps its grape-pruning and kharif-harvest placeholders. None of these is verified with an agronomist.
- **Small fields are read as one zone.** A field of 0.8 ha or more with some width to it is split into eight zones. A smaller, thinner or irregular field down to 0.2 ha is read as one zone, its core pixels. Its drop, neighbours, weather and season still count, but where in the field the loss sits does not, so the boundary and pattern checks are skipped, and no cause is stated with high confidence. Fields under 0.2 ha (about 20 pixels) are not watched. The build reports how many shapes were left out and why. Around Solapur, for example, most published field shapes are under 0.8 ha.

## How the diagnosis works

- **Deterministic tools** (`backend/app/tools`) turn real pixels into cited evidence: scene quality, NDVI change per zone, a boundary check (re-run with a 10 m inner buffer), neighbour comparison, spatial pattern, weather and crop calendar.
- **Zones follow the real shape.** A field's 10 m pixels are split into an analysis area (the shape shrunk 10 m), four interior quadrants, four edges, and an unshrunk 20 m ring used only by the boundary check. A field too small or thin for that is read as one zone: its pixels at least half a pixel inside the boundary. The case says which, and the boundary and pattern checks say why they were skipped.
- **A rule table** (`backend/app/engine/rules.py`) scores ten hypotheses in three stages. Stages 1 and 2 dismiss the case with a reason or raise an area alert; stage 3 ranks field-specific causes. A drop seen on only one clear pass is *watched*, not escalated. If nothing clears the bar, the answer is "ask or visit", never a forced guess.
- **The next best check** (`backend/app/next_check.py`) is computed, not written by a model: how cleanly a result splits the top two causes, divided by the minutes it takes. The candidate table sits under "Why this check?".
- **The language model never invents a cause.** Gemini, when configured, only writes the plain-language case file from the evidence list. Its output is validated: every line must cite known evidence IDs and follow the engine's order. One retry, then a template narrative. Without a key the app works the same.
- **A map at pixel level.** The field is painted as its real 10 m pixels on satellite imagery: NDVI, change against each pixel's own baseline, or plain satellite. Any pass can be picked from the scene bar, two dates compared side by side, and a pixel inspected under the pointer. Cloudy passes stay in the scene bar, disabled, and never show a number.

The full hypothesis table and the reasoning behind it are in [idea.md](idea.md). The visual language is in [DESIGN.md](DESIGN.md).

## Areas, accounts and builds

**Accounts.** Officers and sessions live in SQLite (`backend/fielddx.db`). PINs are stored as PBKDF2 hashes, and the session is an HttpOnly cookie whose token is stored hashed. The demo officer can only work in the demo area.

**Areas.** An area is a folder, `data/areas/<id>/`:

| File | Holds |
|---|---|
| `area.json` | The polygon, how it was marked, the region it sits in |
| `fields.geojson` | The monitored field shapes, their zones, whether each is read in eight zones or as one, and the inferred class |
| `shapes.geojson` | Every field shape in the area, watched or not and why, and the land where no shape was found, for the map |
| `edits.json` | The officer's corrections to the shapes, applied again on a rebuild |
| `grids/`, `scenes/` | Each field's 10 m pixel grid, and its NDVI on every pass |
| `weather.json` | Daily weather for the area centre |
| `calendar.json` | Management windows (inferred, or placeholders for Niphad) |
| `cases.json` | The alerts the detector found |
| `build.json`, `build.log` | Build progress and output, while and after it builds |
| `raw/` | Downloaded imagery and field shapes, reused on a rebuild |

Only `data/areas/niphad` is in git. Areas built at runtime stay on the machine that built them. Findings and stored narratives are keyed by area, so areas never share or overwrite each other's cases.

**Builds.** The API runs `scripts/build_area.py` in a subprocess, one area at a time. Progress is written to `build.json` and shown on the officer's home screen. If the server stops mid-build, the build resumes when it starts again, and imagery already downloaded is kept. A build that cannot help on a retry, such as an area with no fields big enough to monitor, says so and asks for the area to be marked again.

**Map data through the API.** The state's FTW field tiles (`/api/ftw/<state>.pmtiles`) and the region overview tiles (`/api/overview/tiles/...`) are served through the API with a small cache, because many networks drop the HTTP/3 connections the upstream hosts offer.

**API.** All routes except sign-in and health need a session.

| Route | Purpose |
|---|---|
| `POST /api/auth/register`, `/login`, `/demo`, `/logout`; `GET /api/me` | Accounts and the session |
| `GET /api/places`, `/api/places/fields-source` | Place search, and where a state's field shapes are published |
| `POST /api/overview/map`, `/api/overview/summary` | This fortnight's change across a region |
| `GET /api/areas`; `POST /api/areas`; `POST /api/me/area` | List, create and join areas |
| `GET /api/area/build`; `POST /api/area/retry` | Build progress, and retrying a stopped build |
| `GET /api/home` | Today's briefing for the officer's area |
| `GET /api/cases`, `/api/cases/{id}` and `/investigate`, `/map`, `/series`, `/raster` | Cases, the live investigation stream, map and timeline data |
| `GET /api/fields.geojson`; `POST /api/area/fields` | Every field shape on the map; correct them (add, split, merge, remove) |
| `POST /api/cases/{id}/close`; `POST /api/admin/reset` | Record a finding; reopen closed cases in the area |

## Building an area by hand

The app runs the build, but `scripts/build_area.py` also works on any folder holding an `area.json`:

```bash
python scripts/build_area.py --area data/areas/<id>
```

Each step can also be run on its own:

```bash
# field shapes: the published FTW Global map for the area's state
python scripts/ftw_global.py --area data/areas/<id>

# or the FTW model on fresh imagery (needs the ftw CLI; FIELDDX_FTW points at it)
python scripts/ftw_fields.py --bbox 74.07 20.04 74.16 20.12 --year 2025 --out data/areas/niphad/raw/ftw_b5

# Sentinel-2 pixels with Cloud Score+ and SCL, plus WorldCover, on a 10 m grid in the area's UTM zone
python scripts/export_s2.py --bbox 74.07 20.04 74.16 20.12 --start 2025-10-01 --end 2026-10-13 --out data/areas/niphad/raw/s2

# weather
python scripts/fetch_weather.py --lat 20.0775 --lon 74.115 --start 2026-06-01 --end 2026-10-12 --out data/areas/niphad/weather.json

# pick the fields, build the pixel zones, cut every field out of every pass
python scripts/build_dataset.py --area data/areas/niphad

# detect the alerts
python scripts/build_cases.py --area data/areas/niphad

# correct one field shape; only what it touches is read again, then the alerts
python scripts/edit_fields.py --area data/areas/<id> --op '{"op": "remove", "key": "ftw-4110685"}'
```

## Configuration

Set these in the environment or in a `.env` file at the repository root (see `.env.example`). All are optional.

| Variable | Default | Effect |
|---|---|---|
| `GEMINI_API_KEY` | none | Lets Gemini write the case file. Without it, a template narrative is used. |
| `GEMINI_MODEL` | `gemini-3.8-flash` | The Gemini model. |
| `FIELDDX_LLM` | `auto` | `off` always uses the template narrative. |
| `FIELDDX_LLM_TIMEOUT` | `25` | Seconds to wait for the model. |
| `DEMO_PACING` | `550` | Milliseconds between investigation steps, so a viewer can follow. |
| `FIELDDX_DATA` | `data/` | Where the areas live. |
| `FIELDDX_DB` | `backend/fielddx.db` | The SQLite database. |
| `FIELDDX_EE_PROJECT` | none | Earth Engine cloud project, if your account needs one. |
| `FIELDDX_FTW` | found on `PATH` | Path to the `ftw` CLI, for running the model on fresh imagery. |
| `FIELDDX_PYTHON` | the API's Python | The interpreter that runs the build scripts. |
| `FIELDDX_NOMINATIM` | OpenStreetMap | A Nominatim search endpoint. |
| `FIELDDX_FTW_GLOBAL` | Source Cooperative | Base URL of the FTW Global partitions. |
| `FIELDDX_API` | `http://127.0.0.1:8000` | Frontend only: where the dev server proxies `/api`. |

*Reset closed cases* in the officer menu clears closed cases and stored narratives in the signed-in officer's area, so a demo can start clean.

## Tests

```bash
cd backend
python -m pytest
```

- **Engine logic** is tested on a small hand-built fixture with known answers: an edge drop, a hazy pass, a boundary artefact, a pruning wave, a spreading patch, standing water.
- **The real Niphad data** is tested for invariants: polygons, grids and scenes line up, cloudy passes carry no values, every case cites only evidence it has, and the API serves a whole case.
- **Accounts and areas** are tested for sign-in, area scoping (one officer never sees another area's cases or findings), area validation, the inferred harvest season, and input checks on the tile and overview routes.
- **Field shapes** are tested for the gap fill between Fields of the World years, the land with no shape (without the slivers between shapes), each correction (draw, split, merge, remove, and the ones that must be refused), and that the demo area cannot be corrected.

The fixture exists only for tests. The product never reads it.

## Limits

- **10 m pixels.** FieldDx sees zones of a field, not rows or plants. Fields from 0.2 to 0.8 ha are read as one zone, so it cannot say where in them a loss sits, and some of their pixels mix with the land around them. Fields under 0.2 ha are not watched. An area keeps up to 400 fields.
- **Cloud gaps.** In the monsoon, days can pass without a clear view. Those passes are shown as gaps, never as numbers.
- **Not modelled yet:** red-edge (NDRE) evidence, elevation for waterlogging, and a real crop calendar. Storm damage and waterlogging are scored from weather only.
- **The region overview is a screen.** It shows where greenness dropped, not why. The diagnosis comes from marking the land and building it.
- **Field shapes are not complete.** No automatic map finds every smallholder field. Around Vairag (Solapur), Fields of the World puts a shape on under half the land; most of the rest is roads, houses and trees, but some is fields the model missed or joined together. The map shows those gaps, and the officer closes them with **Correct fields**. A field the officer draws under 0.2 ha is shown but, like any field that small, not watched.
- **Accounts are deliberately simple:** a username and PIN, with no password reset or roles.

## Project layout

```
backend/app      main.py (API), areas.py (areas and builds), places.py (place search, FTW partitions),
                 overview.py (region change), pipeline.py, engine/, tools/, next_check.py, resolve.py,
                 narrative.py, llm.py, raster.py, data.py, db.py, config.py
backend/tests    engine logic on a fixture, invariants on the real data, accounts and areas
frontend/src     pages/ (SignIn, Setup, Home, Inbox, Case, Checklist), components/, styles/, session.tsx, api.ts
data/            checks.json, areas/niphad/ (the shipped demo area), areas/<id>/ built at runtime
scripts/         build_area.py, ftw_global.py, ftw_fields.py, export_s2.py, fetch_weather.py,
                 build_dataset.py, build_cases.py, edit_fields.py
DESIGN.md        the visual language
idea.md          the concept, the hypothesis table and the reasoning behind it
```

## Sources and licences

- **Field boundaries:** Fields of the World, Kerner et al. and Robinson et al., <https://fieldsofthe.world>. Model weights CC-BY-4.0, code MIT. FTW Global map: Robinson et al. 2026, "The first global agricultural field boundary map at 10 m resolution" (arXiv:2605.11055), CC-BY-4.0, on Source Cooperative.
- **Places and boundaries:** OpenStreetMap contributors (ODbL), through Nominatim.
- **Imagery:** contains modified Copernicus Sentinel data, through Google Earth Engine, with Cloud Score+ (Google).
- **Land cover:** ESA WorldCover 2021 (CC-BY-4.0).
- **Weather:** Open-Meteo, ERA5 and ERA5-Land reanalysis (CC-BY-4.0).
- **Basemaps:** Esri World Imagery, and OpenStreetMap contributors, through Leaflet.
- The NDVI colour scale, its interpretation bins and the map interaction pattern come from the author's earlier project, Pragya.
