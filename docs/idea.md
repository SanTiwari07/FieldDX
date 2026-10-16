# FieldDx — Differential Diagnosis for Farm Fields

> **One-liner:** Satellites can tell you *that* a field changed. FieldDx tells you *what probably happened, what it definitely wasn't, and the one cheapest check that settles it.*

**Name:** *Dx* is medical shorthand for diagnosis. FieldDx runs a differential diagnosis on a field, the way a doctor does on a patient. Spell this out once in the video intro, since not every judge will know "Dx."

**Hackathon:** Devpost — Build With AI: Basics · Category: Agriculture · Deadline: Oct 26, 2026, 5:00 pm EDT (Oct 27, 2:30 am IST)

> **Status.** This is the concept the project started from. The [README](../README.md) describes what is built. The main change since: FieldDx is no longer one fixed cluster near Nashik. An officer signs in, picks their region anywhere, sees what is changing across it, marks the land they look after, and FieldDx builds that area from real data on demand. Sections 4, 8 and 10 are updated to match.

---

## 1. The problem

A field officer at a Farmer Producer Organisation (FPO) near Nashik is responsible for 200–500 smallholder plots. Crop stress (water, pests, disease, nutrients) is cheapest to fix in the first week, but she can visit maybe 15 farms a day.

Free satellite imagery (Sentinel-2, every ~5 days) already shows vegetation drops. The trouble is that existing tools stop at a **red patch on a map**. A red patch doesn't tell her:

- whether it's real stress or a cloud, a shadow, or a harvest,
- whether it's one farm's problem or the whole village's,
- what to look for when she gets there.

So she ignores the alerts, and farmers find out when the damage is visible.

## 2. The insight

Don't build a better detector. **Build the investigation that happens after detection.**

A good agronomist doesn't see a red patch and say "pests." She runs a differential diagnosis:

1. Is it real? (Check image quality.)
2. Is it just this field? (Compare neighbours.)
3. What shape is it? (Edges, patches, uniform.)
4. What else happened? (Rain, heat, crop stage.)
5. What would tell the remaining causes apart?

FieldDx runs those five steps automatically and hands her a **case file**, not a heatmap.

## 3. Who it's for

**Primary:** FPO field officers and agronomists triaging many fields.
**Not:** individual farmers (different UX, language, and trust problem — out of scope for v1).

Why this user: one person, one clear job (decide where to go today), and a natural product shape (an inbox of cases).

## 4. The product (what the user actually sees)

```
Sign in ──► Region overview ──► Mark the land ──► Build ──► Today's briefing ──► Case ──► Investigation ──► Field-visit checklist ──► Close case
```

| Screen | What it does |
|---|---|
| **Sign in** | An officer account, or the demo area without one. |
| **Region overview** | Search a district; the map locks to it and shows where cropland greenness dropped this fortnight, with the places where most of it dropped. A screen, not a diagnosis. |
| **Mark the land** | Go to a farm by its coordinates or a hotspot, then draw a polygon, pick Fields of the World fields, or type corners. |
| **Build** | Real field shapes, a year of Sentinel-2, weather and the alerts for that polygon, with progress step by step. |
| **Today's briefing** | What happened to this week's passes: dismissed, area-wide, waiting, and the few fields that need a visit. |
| **Cases** | Flagged fields ranked by severity × confidence. Dismissed false alarms shown greyed out with the reason ("cloud on Oct 4 scene"). |
| **Case** | Map with the field split into zones, NDVI timeline, the anomalous zone highlighted, before/after imagery. |
| **Investigation** | The agent's checks, run live, each producing a piece of **evidence** with an ID (E1, E2…). |
| **Diagnosis** | Ranked hypotheses. Each one lists the evidence for it, against it, and what's still unknown. |
| **Next best check** | The single cheapest observation that best separates the top two hypotheses, e.g. *"Check drip line on the east edge — if dry, it's irrigation failure; if wet, inspect leaf undersides for thrips."* |
| **Close case** | Officer records what she found. That outcome is stored against the case. |

## 5. What makes it a 10/10 (and not another NDVI dashboard)

1. **It rejects its own false alarms on camera.** Most demos only show hits. Showing the agent dismiss a cloud artefact and a normal harvest is what makes the hits believable.
2. **The LLM never invents a cause.** Deterministic checks produce evidence; the LLM only reasons over evidence IDs and must cite them. Every claim in a diagnosis links back to E1…En. If evidence is missing, it says "unknown," not a guess.
3. **"Next best check" instead of "here's the answer."** It picks the observation that splits the leading hypotheses — the way a doctor orders one test, not ten. This is the novel part and the hero of the video.
4. **Honest about resolution.** It shows the 10 m pixel grid over the field and says what that can and can't see. Judges trust products that state their limits.

## 6. How the investigation works

### Agent tools (deterministic, each returns evidence)

| Tool | Returns |
|---|---|
| `scene_quality(field, date)` | Cloud / shadow / cirrus % over the field from the Sentinel-2 scene classification layer (SCL 3, 8, 9, 10). Each scene gets a quality class: usable / partial / cloudy / no image |
| `ndvi_series(field)` | Per-zone NDVI over the season; size and speed of the drop; how many clear scenes confirm it |
| `boundary_check(field)` | Re-runs the drop on the field shrunk 10 m inward (one pixel). Says whether an "edge" pattern survives once mixed boundary pixels are removed |
| `neighbour_compare(field, radius)` | Did surrounding fields, ideally the same crop, drop at the same time? |
| `spatial_pattern(field)` | Uniform / edge-concentrated / single patch / spreading over dates |
| `weather(lat, lon, window)` | Rainfall, max temp, heat-stress days, relative humidity, ERA5 soil moisture (Open-Meteo historical archive, free, no key) |
| `crop_calendar(crop, sowing_or_pruning_date, region)` | Expected NDVI curve plus local management windows (grape fruit pruning, onion transplanting / harvest, ploughing). Flags drops that match a scheduled event |
| `red_edge(field)` | NDRE vs NDVI per zone (20 m). Low NDRE relative to NDVI hints at chlorophyll / nitrogen problems. Coarse, so it's supporting evidence only |

### Hypothesis rules (the reasoning backbone)

Checks run in three stages. **Stage 1 gates** run first; if one fires, the case is auto-dismissed with its reason and never reaches the officer as an alert. **Stage 2** asks whether the drop is expected or shared with the area. **Stage 3** is the field-specific differential. If nothing in Stage 3 clears its evidence bar, the answer is **"Unexplained — visit"**, never a forced guess.

| # | Hypothesis | Supports it | Rules it out | Tools | Next best check (cost) | Outcome |
|---|---|---|---|---|---|---|
| **Stage 1 — Is the signal real?** |||||||
| 1 | **Data artefact** (cloud, shadow, haze) | Drop on a single date; that scene is "partial" or "cloudy" in SCL; values recover on the next clear scene | Drop persists across 2+ "usable" scenes | `scene_quality`, `ndvi_series` | None | Auto-dismiss: *"cloud on Oct 4 scene"* |
| 2 | **Boundary-mixing artefact** | Drop is edge-concentrated, but disappears when the field is shrunk 10 m inward; edge sits next to a road, bund, bare plot or recently harvested neighbour | Edge drop survives the inner buffer; interior pixels also dropped | `boundary_check`, `spatial_pattern`, `neighbour_compare` | None | Auto-dismiss: *"edge pixels mix with the bare plot next door"* |
| **Stage 2 — Expected, or shared with the area?** |||||||
| 3 | **Management event** (grape fruit pruning, onion transplanting, ploughing) | Sudden, uniform drop inside a known local management window; field-wide, not patchy; same-crop neighbours show the same drop within ~2 weeks | Drop outside any management window; patchy or edge-only pattern | `crop_calendar`, `spatial_pattern`, `neighbour_compare` | Ask farmer: *"Did you prune / transplant / plough this week?"* (1 phone call) | Dismiss with reason, or confirm by call |
| 4 | **Normal crop cycle** (senescence, harvest) | Timing matches the expected curve for crop and sowing date; gradual and uniform | Too early for the crop stage; neighbours sown together are still green | `crop_calendar`, `ndvi_series` | Ask farmer: *"Harvested?"* (1 phone call) | Dismiss with reason |
| 5 | **Regional heat / dry spell** | Neighbours dropped together; heat-stress days or no rain for 10+ days; low ERA5 soil moisture across the area | Only this field dropped; rain in the window; soil moisture normal | `neighbour_compare`, `weather` | None for this field | Escalate as an **area alert**, not a field case |
| 6 | **Storm / hail / unseasonal rain damage** | Sudden drop right after a heavy rain or storm day; neighbours hit too; can be patchy across the cluster | No storm or heavy rain in the window | `weather`, `neighbour_compare`, `ndvi_series` | Photo of canopy: torn leaves, lodging, bruised bunches (1 visit, 5 min) | Area alert + spot check |
| **Stage 3 — Field-specific differential** |||||||
| 7 | **Irrigation failure** | Edge or row-aligned drop that **survives the inner buffer**; no rain in the window; neighbours fine; area soil moisture normal (so it's not regional drought) | Rain in the window; uniform drop; neighbours also dropped | `boundary_check`, `spatial_pattern`, `weather`, `neighbour_compare` | Check drip line / pump / valve at the affected edge (visit, 5 min) | Field case |
| 8 | **Pest / disease spread** | Patch that **grows across dates**; neighbours fine. For fungal disease (e.g. downy mildew in grape): rain plus high humidity in the prior 7–10 days | Sudden uniform drop; no growth across dates | `spatial_pattern`, `ndvi_series`, `weather` | Photo of leaf undersides in the patch (visit, 5 min) | Field case |
| 9 | **Nutrient deficiency** | Slow, steady decline or failure to green up vs same-crop neighbours sown at the same time; NDRE low relative to NDVI; no weather trigger | Sudden drop; clear weather or management trigger | `ndvi_series`, `neighbour_compare`, `red_edge`, `crop_calendar` | Check which leaves are yellowing, old vs new (visit, 2 min); soil test if unclear | Field case |
| 10 | **Waterlogging** | Heavy rain in the window; drop in the lowest-lying zone; NDMI / NDWI high in that zone | No heavy rain; drop not tied to low ground | `weather`, `spatial_pattern` | Check for standing water / wet, smelly roots (visit, 2 min) | Field case |

**Verify locally before demo day:** the management windows (when Nashik grape growers do fruit pruning, the onion transplant and harvest months) and the humidity rule for downy mildew. Confirm them with a local agronomist or a KVK / NRC-Grapes publication, and cite the source in the repo.

### Choosing the next best check

The next best check is computed, not written by the LLM. For the top two Stage 3 hypotheses, score each candidate check:

`score = how cleanly it splits the two hypotheses ÷ cost in minutes`

A check splits cleanly if one result supports hypothesis A and the other supports B (e.g. "drip line dry" → irrigation failure; "drip line wet" → look at pests). Show the candidate table on the Diagnosis screen with the winner highlighted, so judges can see the choice was reasoned.

When the officer closes the case, their finding is stored as new evidence (e.g. `E7: drip line dry at east edge`) and the hypothesis ranking updates on screen. That's the payoff moment of the demo.

The LLM's job: run the tools, apply this table, write the case file in plain language citing evidence IDs, and turn the officer's free-text finding into a structured result. The table, gates and next-check scoring live in code, so the reasoning is inspectable and the demo still works if the LLM call fails.

## 7. Demo (the 3-minute video)

| Time | Shot |
|---|---|
| 0:00–0:20 | Problem: 300 fields, 15 visits a day, and a map full of red that nobody trusts. |
| 0:20–0:45 | Sign in, search the district: the map locks to it and shows where cropland dropped this fortnight. Today's briefing: of 150 fields, most alerts are already dismissed with a reason ("cloud", "harvest, expected"), a few are area-wide, and a handful need a visit. |
| 0:45–1:45 | Open the top case. The agent runs live: scene quality usable, neighbours fine, edge-concentrated pattern, no rain for 12 days. Evidence cards appear one by one. |
| 1:45–2:20 | Diagnosis: irrigation failure (high), pest spread (low). Every line cites evidence. Next best check: "inspect the east-edge drip line." |
| 2:20–2:40 | Officer closes the case: "Drip line clogged." Case marked resolved. |
| 2:40–3:00 | Who it's for, what it can't do (10 m pixels, cloud gaps), what's next. |

## 8. Data plan (keep it real)

What was planned: 12 to 20 hand-drawn fields in one Nashik cluster, exported once to JSON, with one documented anomaly.

What was built, all from real sources and nothing simulated:

- **Field shapes from Fields of the World**, not hand-drawn: the FTW model run on Sentinel-2 for the Niphad demo (150 fields), and the published FTW Global map for areas set up by officers.
- **Sentinel-2 L2A** pixels at 10 m through Google Earth Engine, masked per pixel with Cloud Score+ and the scene classification layer, kept as each field's pixels on every pass, not just zone averages.
- **Alerts detected from the data**, never hand-picked: any zone 0.10 NDVI below its own baseline on a clear pass in the last 21 days. The real season decides what the demo shows; in October most drops are post-monsoon harvest, and the app says so.
- **Weather** from the Open-Meteo archive (ERA5 and ERA5-Land).
- **Areas built on demand.** The Niphad area ships with the repo so the demo runs offline. Any other area is built from the same sources when an officer marks it.

## 9. Stack

- **Frontend:** React + Vite, Leaflet for the map, Recharts for the NDVI timeline.
- **Backend:** FastAPI. Tools are plain Python functions over the cached data.
- **Agent:** one LLM with tool calling. System prompt forces evidence-ID citations; output validated against a JSON schema (hypotheses, evidence refs, next check).
- **Storage:** SQLite for cases and outcomes.

## 10. Explicitly out of scope

Training any model · farmer-facing app · vernacular languages · yield prediction · scheduled re-builds as new passes arrive. Each is a reasonable next step; none helps the video.

Moved into scope since the first draft: officer sign-in, and areas anywhere (a region overview, then land the officer marks, built from real data on demand).

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Earth Engine export eats days | Time-box to one evening. Fallback: Planetary Computer STAC, or a smaller field set. |
| Monsoon cloud gaps in the series | That's a feature — show the agent handling them. |
| LLM hallucinates a cause | Schema validation + "every claim cites an evidence ID" check. Reject and retry. |
| Looks like a tech PoC | Build the inbox → case → close loop first; it's what the design criterion rewards. |

## 12. Timeline (Oct 13 – Oct 26)

| Day | Goal |
|---|---|
| Oct 13 | Run the skill pack from an empty repo. Generate scope.md, prd.md, spec.md from this doc. |
| Oct 14–15 | Pick fields, export NDVI + scene quality to JSON. |
| Oct 16–17 | Tools + hypothesis table, unit-tested on the cached data. |
| Oct 18–19 | Agent loop with evidence citations and schema validation. |
| Oct 20–21 | Inbox, Case, Diagnosis, Close screens. |
| Oct 22 | Submit an early version to the Discord forum for the "Will It Ship" live review. |
| Oct 23–24 | Fix what the review flagged. Polish the demo case. |
| Oct 25 | Record and edit the video. |
| Oct 26 | Write the description, final check of repo and docs, submit with buffer. |

## 13. Submission checklist

- [ ] New repo, started from an empty folder in the submission window
- [ ] Built with the Devpost Learn skill pack
- [ ] `scope.md`, `prd.md`, `spec.md` committed
- [ ] Public repo URL
- [ ] 1–3 min video showing the whole loop working (reviewers won't run the code)
- [ ] Description: what it does, who it's for, what you learned

## 14. The pitch, in one breath

> "Satellites already see crop stress. Nobody trusts the alerts because half are clouds and the rest don't say what to do. FieldDx investigates every alert like an agronomist would — throws out the false ones, explains the real ones with evidence, and tells the field officer the one thing to check when she gets there."
