![FieldDx: differential diagnosis for farm fields. A case card for Field 128 in Niphad, Nashik reads: Pest or disease spread, likely. Next best check: the drip line and valve on the south edge, about 5 minutes.](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/brand/banner.jpg)

![Real data, no mocks](https://img.shields.io/badge/data-100%25%20real%2C%20no%20mocks-123232?style=flat-square) ![Sentinel-2, 10 m](https://img.shields.io/badge/imagery-Sentinel--2%20%C2%B7%2010%20m-1769aa?style=flat-square) ![Fields of the World](https://img.shields.io/badge/fields-Fields%20of%20the%20World-d99a1e?style=flat-square) ![59 tests passing](https://img.shields.io/badge/tests-59%20passing-065f2c?style=flat-square) ![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-4d5c58?style=flat-square&logo=python&logoColor=white) ![React and Vite](https://img.shields.io/badge/React-Vite-4d5c58?style=flat-square&logo=react&logoColor=white)

---

## Monday, 7:10 am, Niphad

You are the field officer for a farmer producer organisation in the grape and onion belt of Nashik. A few hundred member farmers have your number. Last season unseasonal rain ruined vineyards across the district, about 45,000 hectares by the first estimates, [6] and every one of those farmers remembers whether someone came.

The satellite map on your phone shows **68 fields that lost green in the last three weeks**. You have one day, and time for perhaps fifteen farms.

Which fifteen?

Some of that red is a hazy pass the satellite half-saw. Some is a field cut for harvest, exactly on schedule. Seventeen of those fields are a whole neighbourhood drying out in the same hot spell: one problem, not seventeen visits. And somewhere in there is the plot where something is spreading across the south edge, and every day you spend at the wrong farm, it spreads a little further.

A red patch cannot tell you which is which. So officers learn to stop looking, and the farmer finds out when the leaves curl. For a family that farms about one hectare, the national average, [2] there is no second field to make up for a lost one.

**FieldDx was built for that morning.**

*The scene is illustrative. Its numbers are the real alerts in the shipped Niphad demo area and the sources at the end of this page.*

### Why this is hard everywhere, not only in Niphad

| Number | What it means |
|---|---|
| **1 : 1,162** | One public extension worker for every 1,162 operational holdings in India, against a recommended 1 : 750. [1] |
| **86.1 %** | Share of Indian holdings that are small or marginal, under 2 hectares. The average holding is 1.08 ha. [2] |
| **10,000** | Farmer producer organisations registered under the national FPO scheme, each needing someone to look after its members' fields. [3] |
| **608 million** | Farms in the world. 84 % are under 2 hectares, and together they grow about a third of the world's food. [7] |
| **1 : 3,000** | Average extension worker to farmer ratio reported across Africa; 1 : 5,000 to 1 : 10,000 in Nigeria. [8] |

The imagery stopped being the problem years ago. Sentinel-2 photographs every field on Earth about every five days, for free. What is missing is the step after the picture: **the investigation**.

## What FieldDx does

*Dx* is medical shorthand for diagnosis. A good doctor does not see a fever and say "flu". They run a differential: what else could it be, what rules each one out, and which single test settles it. A good agronomist does the same with a field, and FieldDx does it for every alert, automatically:

1. **Is the signal real?** Cloud, shadow, haze, edge pixels mixing with the land next door, a single odd pass.
2. **Is it expected, or shared with the area?** Harvest or pruning season, the neighbouring fields, the weather.
3. **If it is this field alone, which causes fit the evidence**, and what is the cheapest thing to ask or check that tells them apart?

The officer gets a **case file, not a heatmap**: ranked causes where every line cites its evidence (`E2`, `E5`), the false alarms thrown out with their reasons, and **one next check**. When the officer reports back, the finding becomes new evidence and the ranking updates.

![68 of 150 fields lost green in three weeks; 26 need the officer. Stage 1, is the signal real: 2 not real, 8 watching. Stage 2, expected or shared: 15 expected harvest or pruning, 17 area-wide. Stage 3, this field alone: 2 with a named cause and one check, 24 ask or visit.](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/brand/triage.png)

That is the real Niphad demo area, not a mock-up: **42 of 68 alerts explained without anyone getting on a motorcycle**, and the 26 that remain arrive with a reason, a ranking and a question to ask.

### Three promises

- **It throws out its own false alarms, and says why.** Most tools only show hits. Showing the cloud and the harvest it dismissed is what makes the hits believable.
- **The language model never invents a cause.** Deterministic code turns pixels into evidence and ranks the causes. Gemini only writes the plain-language case file, must cite evidence IDs that exist, and is replaced by a template if it does not.
- **When it does not know, it asks.** If nothing clears the bar, the answer is "ask or visit" with the cheapest question, never a forced guess.

## A walk through the app

Every screen below is a screenshot of the running app on real Sentinel-2 data for Niphad, Nashik.

![Field 128: pest or disease spread, likely, painted as its real 10 m pixels, with the next best check pinned at the bottom](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/05-case-summary.jpg)

*A case. Field 128, painted as its real 10 m pixels. The likely cause in plain words, what else it could be, what was ruled out, and the next best check pinned at the bottom.*

![Sign-in page over real satellite imagery of Niphad](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/01-sign-in.jpg)
**Sign in.** The demo area is one tap, no account needed. An officer account is a username and a PIN.

![Today: 26 fields need you today, with every alert split into groups](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/02-today.jpg)
**Today.** One sentence says how many fields need the officer. One bar shows where every other alert went. The fields to start with sit beside the map.

![Cases in Niphad ranked by severity and confidence](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/03-cases.jpg)
**Cases.** Every alert, ranked by severity and confidence, each with its likely cause or the question to ask.

![Evidence tab: ranked hypotheses, each line citing evidence IDs](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/06-case-evidence.jpg)
**Evidence.** Each cause lists what supports it and what argues against it, every line tied to an evidence ID. The case file is written by Gemini and cites evidence only.

![Before and after: Oct 2 against Oct 10, side by side](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/07-case-compare.jpg)
**Compare.** Any two passes side by side. Here the south edge of Field 128 between Oct 2 and Oct 10.

![NDVI by zone over the season, with cloudy passes shown as gaps](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/08-case-trend.jpg)
**Trend.** NDVI by zone since June. Cloudy monsoon passes are hollow circles and never a number. The note under it says what 10 m pixels can and cannot see.

![Ask: why not irrigation failure, answered with evidence citations](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/09-case-ask.jpg)
**Ask FieldDx.** "Why not irrigation failure?" Answered from this area's own records, with the evidence it used. In English, Hindi or Marathi.

![Field 095 dismissed as a data artefact on the Oct 2 scene](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/10-case-dismissed.jpg)
**A false alarm, dismissed.** Field 095 dropped on a hazy Oct 2 pass and recovered. No visit needed, and the reason is on screen.

![Field checklist: check the drip line, what each result means, record the finding](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/11-field-checklist.jpg)
**At the field.** One check, what each result means, and a form to record the finding, which becomes new evidence.

![Map of every watched field in Niphad coloured by case](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/04-fields-map.jpg)
**Every field.** All watched fields, coloured by what happened to them.

![Mark the land: tap published Fields of the World shapes](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/12-mark-the-land.jpg)
**Mark your own land.** Search a taluka, confirm its outline, then draw around the farms, tap published Fields of the World shapes, or type coordinates.

![Region overview: where crops lost green this fortnight, live from Earth Engine](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/13-region-overview.jpg)
**Not sure where to look?** This fortnight's change in cropland NDVI, computed live in Google Earth Engine. A screen, not a diagnosis.

![Today on a phone](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/15-phone-today.jpg)

![A case on a phone](https://raw.githubusercontent.com/SanTiwari07/FieldDX/main/docs/screenshots/14-phone-case.jpg)

*Built for a phone in a field as much as a desk in an office.*

## How FieldDx thinks

*The diagram for this section is in the [README on GitHub](https://github.com/SanTiwari07/FieldDX#readme).*

### Evidence first

Seven deterministic tools (`backend/app/tools`) turn real pixels into numbered evidence. For Field 128 they produced seven pieces, `E1` to `E7`:

| Tool | What it asks | Why it matters |
|---|---|---|
| `scene_quality` | Was the pass clear? How many clear passes since the alert? | Cloud Score+ and the scene classification layer, per pixel |
| `ndvi_series` | How big, how fast, confirmed by how many passes? | Each zone against its own baseline |
| `boundary_check` | Does an edge drop survive a 10 m inner buffer? | Rules out pixels mixing with the land next door |
| `neighbour_compare` | Did nearby fields of the same kind drop too? | Separates a field problem from an area problem |
| `spatial_pattern` | Edge, patch, spreading, or the whole field? | Patches that grow point one way, uniform falls another |
| `weather` | Dry spell, heat, heavy rain, soil moisture? | Open-Meteo, ERA5 and ERA5-Land |
| `crop_calendar` | Is this harvest or pruning season? | Inferred from the area's own NDVI |

### Eleven hypotheses, scored in three stages

A rule table (`backend/app/engine/rules.py`) holds each hypothesis as weighted conditions over those facts. A missing fact counts neither way and is shown as unknown.

| Stage | Hypotheses |
|---|---|
| 1. Is it real? | Data artefact (cloud, shadow or haze) · Boundary-mixing artefact |
| 2. Expected or shared? | Management event or harvest · Normal crop cycle · Regional dry or hot spell · Storm, hail or unseasonal rain damage · Harvest or field work across the area |
| 3. This field alone | Irrigation failure · Pest or disease spread · Nutrient deficiency · Standing water |

### The next best check is computed, not written

A doctor orders the one test that separates the top two diagnoses, not ten tests. FieldDx scores every on-site check in `data/checks.json` by how cleanly its result splits the top two causes, divided by the minutes it takes (`backend/app/next_check.py`). For Field 128, pest or disease spread against irrigation failure:

| Check | Minutes | Splits the two? | Score | |
|---|---:|---|---:|---|
| Photograph leaf undersides in the affected patch | 4 | one way only | 0.125 | **chosen** |
| Check the drip line and valve on the south edge | 5 | one way only | 0.1 |  |
| Dig 10 cm in the affected zone and feel the soil | 10 | one way only | 0.05 |  |
| Note which leaves are yellowing, old or new | 2 | no | 0 |  |
| Look for standing water and check how wet the soil is | 2 | no | 0 |  |

The officer sees the same table under *Why this check?*. A result only separates two causes if it supports one and counts against the other: a working drip line counts against irrigation failure but is not evidence for pests, so the leaf check is as informative and a minute cheaper.

### A finding updates the investigation, it does not close it

The officer records what they found at the recommended check. The finding becomes evidence, moves only the causes `data/checks.json` says it supports or contradicts, and the next check is chosen again from what is still live (`backend/app/resolve.py`). For Field 128, *Leaves clean* makes pest or disease spread less likely (0.7 to 0.2). Irrigation failure is unchanged at 0.4 and now ranks first because pests weakened, and the next check becomes the drip line on the south edge. The case shows *Investigation updated · still open*, with a word label and a reason for every cause. No cause is ever marked confirmed by ruling another out. If a finding leaves no cause standing, the case says none of the current explanations fits well and asks for a call or visit.

### Where the language model sits, and where it does not

- **It never ranks, scores or names a cause.** The engine does.
- **It writes the case file from the evidence list.** Every line must cite known evidence IDs and follow the engine's order. One retry, then a template narrative. Without a key, the app works the same.
- **Ask FieldDx is retrieval first** (`backend/app/assistant.py`). Every case and watched field becomes a short record. A question is matched by field number, then by word overlap (BM25). Gemini answers only from those records, links what it used, and is told never to invent numbers, pests or doses. An officer only ever sees their own area.

## Architecture

*The diagram for this section is in the [README on GitHub](https://github.com/SanTiwari07/FieldDX#readme).*

| Layer | Built with |
|---|---|
| Imagery and region change | Google Earth Engine, Sentinel-2 L2A, Cloud Score+, ESA WorldCover |
| Field boundaries | Fields of the World: the published FTW Global map, or the FTW model run on fresh scenes |
| Weather | Open-Meteo archive (ERA5, ERA5-Land) |
| API | Python, FastAPI, SQLite, a build subprocess per area |
| Diagnosis | Plain Python tools and a rule table, unit tested on known answers |
| Language | Gemini, validated against the evidence list, with a template fallback |
| App | React, Vite, TypeScript, Leaflet, PMTiles |

## Built on real data

Nothing in the app is simulated. Every number traces back to a real source.

| What | Source |
|---|---|
| Field shapes | **Fields of the World** (FTW). Either the published FTW Global map (PRUE model, 2024 and 2025, about 3.2 billion fields, [9] read per state from Source Cooperative), or the FTW model (PRUE EfficientNet-B5, CC-BY weights) run on fresh Sentinel-2 scenes of the area, as for the Niphad demo. From the published map, the latest year is the base and an earlier year's field is added where it fills a gap (at most a quarter of it under a latest-year field). A shape is a remote-sensing field unit, not a legal parcel. |
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
- **Small fields are read as one zone.** A field of 0.8 ha or more with some width to it is split into eight zones. A smaller, thinner or irregular field down to 0.2 ha is read as one zone, its core pixels. Its drop, neighbours, weather and season still count, but where in the field the loss sits does not, so the boundary and pattern checks are skipped, and no cause is stated with high confidence. Fields under 0.2 ha (about 20 pixels) are not watched.

## India first

FieldDx starts in India because that is where the gap between imagery and action is widest, and where the smallest fields make the problem hardest.

**Built around how Indian agriculture is actually organised.**

- **The officer is the user, not the farmer.** FPO field officers, agriculture assistants and KVK staff triage hundreds of plots each. FieldDx is an inbox for that job, not another farmer app.
- **Talukas, not bounding boxes.** An officer searches *Niphad taluka* or *Vairag tehsil*, confirms the outline, and marks the land they look after. A few square kilometres build in five to ten minutes.
- **Smallholder fields, honestly.** Around Solapur most published field shapes are under 0.8 ha. FieldDx reads those as one zone and says so, rather than pretending to see inside them.
- **Monsoon cloud is normal.** Cloudy passes are kept in the timeline as gaps and never turned into numbers. A drop seen on only one clear pass is *watched*, not escalated.
- **The officer's language.** Ask FieldDx answers in English, Hindi and Marathi.
- **Areas built so far on this codebase** include Niphad and Kolhapur district in Maharashtra, Baramati in Pune, Kurhani in Bihar and Jagraon in Punjab, all from the same open sources.

**Where it plugs into India's public systems next.** These are directions, not partnerships:

| System | How FieldDx could fit |
|---|---|
| **AgriStack** Digital Crop Survey, 23.90 crore plots across 461 districts in Rabi 2024-25 [4] | The crop sown registry would replace FieldDx's biggest assumption, *the crop is not known*, with the crop the surveyor recorded. |
| **PMFBY** and **YES-TECH**, with a 30 % weightage on remote-sensing yields for paddy and wheat since Kharif 2023 [5] | Triage before a loss assessment: which drops are cloud, harvest or area-wide, and which fields need a person on the ground. |
| **10,000 FPOs** under the national scheme [3] | One officer, one area, one inbox per FPO, with cases and findings shared between colleagues in the same area. |
| **Krishi Vigyan Kendras** and state extension | Recorded findings become a record of what officers actually found, field by field, season by season. |

## Then the world

Nothing in FieldDx's data stack is Indian. Every source already covers the planet:

| Ingredient | Coverage |
|---|---|
| Sentinel-2 imagery and Cloud Score+ | Every land surface, about every 5 days |
| Fields of the World Global | Wall-to-wall field boundaries, about 3.2 billion fields [9] |
| ESA WorldCover | Global land cover at 10 m |
| Open-Meteo, ERA5 | Global weather reanalysis |
| OpenStreetMap | Place names and boundaries worldwide |

What changes from one country to the next is small and kept as data, not code:

- **The check catalogue** (`data/checks.json`). The drip line that settles a case in a Nashik vineyard becomes a soil probe in a rain-fed maize field or a look at the canal gate on an irrigated one.
- **The calendar.** Already inferred from each area's own NDVI; a national crop calendar would sharpen it.
- **The language** of the case file and of Ask FieldDx.

The people who would use it are the same everywhere: an extension worker with a few thousand farmers, a cooperative agronomist, a crop insurer deciding where to send an assessor, an NGO running a smallholder programme. Five of every six farms on Earth are smallholdings. [7] They all need the step after the picture.

## What it cannot do yet

- **10 m pixels.** FieldDx sees zones of a field, not rows or plants. Fields from 0.2 to 0.8 ha are read as one zone, so it cannot say where in them a loss sits, and some of their pixels mix with the land around them. Fields under 0.2 ha are not watched. An area keeps up to 400 fields.
- **Cloud gaps.** In the monsoon, days can pass without a clear view. Those passes are shown as gaps, never as numbers.
- **Not modelled yet:** red-edge (NDRE) evidence, elevation for waterlogging, and a real crop calendar. Storm damage and waterlogging are scored from weather only.
- **The region overview is a screen.** It shows where greenness dropped, not why. The diagnosis comes from marking the land and building it.
- **Field shapes are not complete.** No automatic map finds every smallholder field. Around Vairag (Solapur), Fields of the World puts a shape on under half the land; most of the rest is roads, houses and trees, but some is fields the model missed or joined together. The map shows those gaps, and the officer closes them with **Correct fields**.
- **Accounts are deliberately simple:** a username and PIN, with no password reset or roles.

### Next

- Red-edge (NDRE) and moisture (NDMI) evidence from the 20 m bands, so a leaf check is needed less often.
- The crop from AgriStack's crop sown registry instead of *perennial or seasonal*.
- Elevation for waterlogging, and rainfall from the area's own gauges where they exist.
- More Indian languages for the case file and Ask FieldDx, starting with Kannada, Telugu and Punjabi.
- Learning from past findings: what officers found, used as priors for the next case in the same area.

## Run it

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

Open <http://localhost:5173> and choose **Try the demo area**, or create an account and set up an area of your own. The dev server proxies `/api` to port 8000. For a single process, run `npm run build` in `frontend/` and the API serves the built app at <http://localhost:8000>.

The API does not reload itself. Restart it after pulling new code.

Setting up new areas and the region overview also need the pipeline packages and Earth Engine on the server:

```bash
pip install -r scripts/requirements.txt
earthengine authenticate
```

Run the tests with `python -m pytest` in `backend/`. `tests/test_field128_demo.py` checks the demo case on the real data: the first check, and what *Leaves clean* changes.

For a demo recording, set `FIELDDX_LLM=off` so the case file always comes from the template, and run `python scripts/reset_demo.py` before each take.

## Sources

**The problem**

1. Agriculture extension in India: one extension worker per 1,162 operational holdings against a recommended 1 : 750. *Agriculture Extension System in India: A Meta-analysis*, ICRISAT. <https://oar.icrisat.org/11401/1/Agriculture-Extension-System-in-India-A-Meta-analysis.pdf>
2. Agriculture Census 2015-16, Government of India: 86.1 % of holdings small and marginal (under 2 ha), average operational holding 1.08 ha. Press Information Bureau, *Categorisation of Farmers*. <https://pib.gov.in/newsite/PrintRelease.aspx?relid=188051>
3. 10,000 FPOs registered under the Central Sector Scheme for Formation and Promotion of 10,000 FPOs. Press Information Bureau, 8 August 2025. <https://pib.gov.in/PressReleasePage.aspx?PRID=2154174>
4. AgriStack: Digital Crop Survey in 461 districts covering more than 23.90 crore plots. Press Information Bureau, *Digital Identities to Farmers*, March 2025. <https://pib.gov.in/PressReleasePage.aspx?PRID=2117390>
5. YES-TECH under PMFBY: 30 % weightage to remote-sensing yield estimates for paddy and wheat from Kharif 2023. Press Information Bureau. <https://pib.gov.in/PressReleasePage.aspx?PRID=2085179>
6. Unseasonal rain in Nashik: about 45,000 ha of vineyards severely damaged by preliminary estimates. *Free Press Journal*. <https://www.freepressjournal.in/pune/nashik-grapes-hit-hard-by-rains-45000-hectares-of-vineyards-damaged-3500-crore-loss-feared>
7. Lowder, Sánchez and Bertini (2021), *Which farms feed the world and has farmland become more concentrated?*, World Development 142: more than 608 million farms; farms under 2 ha are 84 % of all farms and produce about 35 % of the world's food. <https://www.sciencedirect.com/science/article/pii/S0305750X2100067X> and FAO, <https://www.fao.org/newsroom/detail/Small-family-farmers-produce-a-third-of-the-world-s-food/en>
8. Extension worker to farmer ratios in Africa: about 1 : 3,000 on average, 1 : 5,000 to 1 : 10,000 in Nigeria, 1 : 1,800 in Uganda. *African Journal of Food, Agriculture, Nutrition and Development* 24(3), special issue on agricultural extension, Sasakawa Africa Association. <https://www.saa-safe.org/elfiles/l4KESreQ/AJFAND%20Volume24.No3_Special%20Issue%20on%20Agricultural%20Extension.pdf>
9. Robinson et al. (2026), *The first global agricultural field boundary map at 10 m resolution*, arXiv:2605.11055.

**Data and licences**

- **Field boundaries:** Fields of the World, Kerner et al. and Robinson et al., <https://fieldsofthe.world>. Model weights CC-BY-4.0, code MIT. FTW Global map CC-BY-4.0, on Source Cooperative.
- **Places and boundaries:** OpenStreetMap contributors (ODbL), through Nominatim.
- **Imagery:** contains modified Copernicus Sentinel data, through Google Earth Engine, with Cloud Score+ (Google).
- **Land cover:** ESA WorldCover 2021 (CC-BY-4.0).
- **Weather:** Open-Meteo, ERA5 and ERA5-Land reanalysis (CC-BY-4.0).
- **Basemaps:** Esri World Imagery, and OpenStreetMap contributors, through Leaflet.
- The NDVI colour scale, its interpretation bins and the map interaction pattern come from the author's earlier project, Pragya.

*FieldDx · Know why a field changed before you drive out to it.*
