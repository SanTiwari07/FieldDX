---
doc: spec
status: approved
---

# FieldDx — Technical Spec

*Sanskar Tiwari and Shambhavi Patil.*

Every component below is labelled the same way as the PRD: **Built** (exists and stays as is), **Change** (exists, behaves differently after this build), **New** (does not exist yet).

## How This Works, In Plain Language
FieldDx has two halves that talk over a small web API.

- **The engine** (Python, FastAPI) reads the Niphad satellite and weather data that ships in the repo, decides whether a greenery drop is real and unusual, scores the possible causes, and picks the next check. It is plain rules, not a language model, so the same field always gives the same answer.
- **The screens** (React, TypeScript) show the case and let the officer record what they found.
- **The check list** (`data/checks.json`) says, for every field check, what each result supports and what it counts against. The engine trusts this file completely, so the evidence rules live here, not in code.
- **The findings store** (a SQLite file on the laptop) keeps every finding the officer records, in order.

When the officer opens a case, the engine rebuilds it from the satellite evidence and then replays each recorded finding on top. Each finding moves only the causes the check list says it supports or contradicts. The engine then picks the next check again from whatever causes are still live. The screen shows what moved, what stayed the same, and why. A fixed template writes the plain-language summary, so the wording is identical on every run.

Why this shape: it is the app that already exists, with one idea changed. A finding is now a step in an investigation, not the end of one. Nothing new needs to be installed or hosted.

## The Core Journey Through the System
PRD ref: `prd.md > The Core Journey`. Values are real engine output for Field 128, simulated under the rules in this spec.

1. **Dashboard.** The browser asks the engine for the Niphad home view, and Field 128 is listed as needing attention. **Built**
2. **Open Field 128.** The engine builds the case from shipped data: triage stages, then ranked causes. Pest or disease spread 0.7 (leading), irrigation failure 0.4 (possible), nutrient deficiency and standing water 0.0 (ruled out). **Built**
3. **Next check.** The engine scores each check by how cleanly it separates the top two causes, per minute of the officer's time. Under the corrected check list (see *Check List and Evidence Rules*), the **leaf undersides** check (4 min) wins over the drip line (5 min). **Change**: today the drip line wins only because a working line was miscounted as support for pests.
4. **Record a finding.** On the field checklist, the officer records **Leaves clean**. The browser sends it to the engine, which saves it to the findings store. The case stays open. **Change**
5. **Replay.** The engine rebuilds the case and applies the finding. Leaves clean counts only against pest or disease spread, so its score falls from 0.7 to 0.2 (less likely, still possible). Irrigation failure stays at 0.4: unchanged, and now first because pest weakened. Nutrient deficiency and standing water are unchanged. **New**
6. **Next check recalculated.** Leaf undersides is marked done. The live causes are now irrigation failure and pest or disease spread, and the best remaining check is the **drip line and valve on the south edge**. The slip says why it changed. **New**
7. **The screen.** *Investigation updated* appears near the top, with the before-and-after for each cause, the new field-visit evidence, and the new slip. The template summary explains the same thing. **New**

## Stack
The existing, working stack. No new dependencies.
- **Python 3.11+**, **FastAPI** for the API, **Pydantic 2** for data shapes. [FastAPI](https://fastapi.tiangolo.com/) · [Pydantic](https://docs.pydantic.dev/)
- **SQLite** through Python's built-in `sqlite3` for officer findings. [sqlite3](https://docs.python.org/3/library/sqlite3.html)
- **React 18**, **TypeScript 5**, **Vite 5**, React Router 6 for the screens. [React](https://react.dev/) · [Vite](https://vite.dev/)
- **pytest** for the engine checks. [pytest](https://docs.pytest.org/)
- **Gemini** (`google-genai`) stays installed but is **off for the proof**. [Gemini API](https://ai.google.dev/gemini-api/docs)

## Where It Runs and How Someone Tries It
Runs locally: the engine on port 8000, the screens on port 5173. No API keys are needed. The Niphad data ships in `data/`.

```
cd backend
pip install -e ".[dev]"
python -m uvicorn app.main:app --port 8000      # with FIELDDX_LLM=off set, see below
```
```
cd frontend
npm install
npm run dev
```
Set `FIELDDX_LLM=off` before starting the engine (PowerShell: `$env:FIELDDX_LLM="off"`; bash: `export FIELDDX_LLM=off`), or put it in `.env`.

**Before each take of the video:**
1. `python scripts/reset_demo.py` clears every recorded finding and stored summary for the Niphad demo area. **New**
2. `cd backend` then `python -m pytest tests/test_field128_demo.py` confirms the engine still gives the expected before-and-after. **New**
3. Open <http://localhost:5173>, choose **Try the demo area**, open Field 128.

Submission needs the demo video on YouTube and the public GitHub repo. No deployment for now.

**Current demo video:** <https://youtu.be/LRmjZv-JO-s>. It was recorded before this build, so it shows the app's previous behaviour, not the changes proposed in this spec. After the build, the workflow is checked against the real app and the video is re-recorded if it no longer matches.

## Look and Feel
From `prd.md > Look and Feel`, using the tokens already in `frontend/src/styles/tokens.css` (from `docs/DESIGN.md`). **Built**
- The dark next-check slip (`--ink`) stays the strongest element.
- *Investigation updated* is a small pill near the top of the case: turmeric outline and text on `--turmeric-soft`, the same treatment as other "needs you" states. No toast, no animation beyond the existing fade.
- Movement labels are small uppercase word chips beside each cause: MORE LIKELY, LESS LIKELY, RULED OUT, UNCHANGED, NEWLY CONSIDERED. Each pairs with a glyph (↑ ↓ ✕ = +), so meaning never depends on colour.
- Copy is calm and factual: *Pest or disease spread: less likely. Leaves clean on the south edge (E9).* Never *confirmed*.

## Components

### Check List and Evidence Rules
`data/checks.json`. Implements `prd.md > Reversible but Never Arbitrary`. **Change**
- A result lists a cause under `supports` only if it is direct evidence for it. Ruling a cause out goes under `against` only.
- Corrections: `drip_line.wet` and `soil_probe.moist` drop their `supports` (today `["H8", "H9"]`). All other results already follow the rule.
- Labels: `drip_line.dry` reads **Drip line not working**, `drip_line.wet` reads **Drip line working**, and the `then` text for each is reworded to describe the observation. Keys stay `dry` and `wet`, so nothing else has to be renamed.

### Findings Store
`backend/app/db.py`. Implements `prd.md > Recording a Finding` and `prd.md > States and Boundaries` (persistence). **Change**
- New table `case_findings(id INTEGER PRIMARY KEY, area_id, case_id, check_id, outcome, note, recorded_at, recorded_by)`. One row per finding, in the order recorded.
- Functions: `add_finding(...)`, `list_findings(area_id, case_id)`, and `reset(area_id)`, which now also clears findings.
- The old `case_outcomes` table is no longer read or written. It is left in place, so no migration is needed.

### Finding Replay
`backend/app/resolve.py`, `apply_finding()` replacing `apply_outcome()`. Implements `prd.md > Investigation Update After a Finding` and `prd.md > Reversible but Never Arbitrary`. **Change**
- Adds a field-visit evidence item, then moves each cause in that result's `supports` up by `OUTCOME_WEIGHT` (0.5) and each cause in its `against` down by the same amount (never below 0). **No other cause's score changes.**
- Re-sorts the causes and sets statuses: the top one is *leading*, any below `RULED_OUT_BELOW` (0.15) is *ruled out*, and the rest are *possible*. **The case stays open.** Nothing is marked confirmed.
- Builds an **update** record for the last finding. For each cause it stores the score and status before and after, plus a movement label:
  - **more likely** / **less likely**: the score went up or down;
  - **ruled out**: it crossed below the threshold;
  - **newly considered**: it went from ruled out to possible, which is only possible through a `supports` entry;
  - **unchanged**: the score is the same. If the cause's position changed anyway, the reason says why, for example *now first because pest or disease spread became less likely*.
- Each changed cause gets one reason line that cites the field-visit evidence id.
- **None fits** (implements `prd.md > When No Cause Fits`): if every cause is ruled out after a finding, the case shows that none of the current explanations fits well, keeps the finding, and recommends a call or visit. It reuses the existing `unexplained` outcome.

### Next Check Recalculation
`backend/app/next_check.py`. Implements `prd.md > Next Check Responds to the Finding`. **Change**
- `choose(top_two, state, done)`. The separation scoring is **kept as it is**: a check separates two causes only if one of its results supports one and counts against the other. Checks in `done` (already recorded on this case) are skipped.
- With one live cause, pick the cheapest check that has a result supporting it and a result against it. If there is none, recommend *Call the farmer or visit the field*.
- Returns a short **why it changed** line for the slip, built from the finding, for example: *Leaves were clean, so pest or disease spread is less likely. The drip line now best separates irrigation failure from pest or disease spread.*

### Case Service and API
`backend/app/service.py`, `backend/app/main.py`. **Change**
- `effective_case()` builds the base case, then replays every row from `list_findings()` in order through `apply_finding()` and the next-check recalculation.
- `POST /api/cases/{case_id}/findings` with body `{check_id, outcome, note}` validates the check and result, saves the finding, and returns the updated case. It replaces `POST /api/cases/{case_id}/close`, which is removed.
- Inbox and home show an updated case as open, with the label *Investigation updated*.

### Template Summary
`backend/app/narrative.py`, `backend/app/llm.py`. Implements `prd.md > Look and Feel` and the reproducibility decision. **Change**
- When a case has findings, the summary always comes from the template, even if a Gemini key is set. It states what was checked, what moved and what stayed the same, and the new next check, from the update record.
- The template never uses the word *confirmed* for a cause.
- With `FIELDDX_LLM=off`, every summary is template-written.

### Case Screen: Investigation Update
`frontend/src/components/NextCheck.tsx` (replaces `ResolutionCard` with `InvestigationUpdate`), `Diagnosis.tsx`, `Summary.tsx`, `Dock.tsx`. Implements `prd.md > Investigation Update After a Finding`. **Change / New**
- `InvestigationUpdate` shows the pill, the finding (*Leaf undersides: leaves clean*, with its evidence link), and the before-and-after list of causes with movement chips and reason lines.
- `Diagnosis.tsx` shows a movement chip on each cause while an update exists.
- `Summary.tsx` and `Dock.tsx` drop their *confirmed* and *closed* branches and show the leading cause as *still leading, not confirmed*.
- The slip in `NextCheck.tsx` shows the recalculated check and its *why it changed* line.

### Field Checklist
`frontend/src/pages/Checklist.tsx`, `frontend/src/api.ts`. Implements `prd.md > Recording a Finding`. **Change**
- Saving a result calls `api.recordFinding(caseId, {check_id, outcome, note})` (replacing `api.close`), then returns to the case.
- `api.ts` gains the `InvestigationUpdate` and `Movement` types and drops `Resolution`.

### Demo Reset and Field 128 Check
`scripts/reset_demo.py`, `backend/tests/test_field128_demo.py`. Implements the reproducibility requirement. **New**
- `reset_demo.py` calls `db.reset("niphad")`.
- `test_field128_demo.py` runs the real Niphad case, with no fixture, and asserts:
  - before: pest or disease spread leading, irrigation failure possible, first check `leaf_undersides`;
  - after **Leaves clean**: pest or disease spread less likely (0.2, possible), irrigation failure unchanged (0.4) and first, nutrient deficiency and standing water unchanged and ruled out, the case open, the next check `drip_line`, and no cause marked confirmed;
  - after **Drip line working** with no other finding: irrigation failure ruled out, and nutrient deficiency unchanged.

## Data Model
- **Satellite evidence, fields, weather, scenes**: shipped files in `data/areas/niphad/`. Read-only. Unchanged by the officer. **Built**
- **Check list**: `data/checks.json`. Read-only at run time. Edited once in this build. **Change**
- **Findings**: rows in `case_findings` in the SQLite file. Added when the officer saves a result. They persist across reloads and restarts until `reset_demo.py` runs. **New**
- **The case the screen shows**: not stored. It is rebuilt on every request from the shipped data plus the findings. **Built** (now with replay)
- **Update record**: part of the rebuilt case (`CaseResult.update`), describing the most recent finding. Replaces `CaseResult.resolution`. **New**

When the officer leaves and comes back, the case is rebuilt from the same files and the same findings, so it looks the same.

## File Structure
```
FieldDX/
├── backend/
│   ├── app/
│   │   ├── main.py           # API routes: POST /cases/{id}/findings replaces /close        (Change)
│   │   ├── service.py        # effective_case(): base case + replay of all findings         (Change)
│   │   ├── resolve.py        # apply_finding(): moves only named causes, builds the update  (Change)
│   │   ├── next_check.py     # choose(): skips done checks, one-live-cause rule, reason      (Change)
│   │   ├── db.py             # case_findings table, add/list findings, reset clears them    (Change)
│   │   ├── models.py         # InvestigationUpdate, CauseMove; CaseResult.update            (Change)
│   │   ├── narrative.py      # template summary for updated cases, never "confirmed"        (Change)
│   │   ├── llm.py            # skips the model when a case has findings                     (Change)
│   │   ├── engine/           # triage stages and cause rules                                (Built)
│   │   └── ...               # areas, overview, places, assistant, raster: not touched      (Built)
│   └── tests/
│       ├── test_field128_demo.py   # the real Field 128 before-and-after                   (New)
│       └── test_logic.py           # closing tests rewritten for findings                  (Change)
├── frontend/src/
│   ├── api.ts                # recordFinding(); InvestigationUpdate types                   (Change)
│   ├── pages/Checklist.tsx   # saves a finding and returns to the case                      (Change)
│   └── components/
│       ├── NextCheck.tsx     # InvestigationUpdate panel; slip with "why it changed"        (Change)
│       ├── Diagnosis.tsx     # movement chips per cause                                     (Change)
│       ├── Summary.tsx       # still leading, never confirmed                               (Change)
│       └── Dock.tsx          # same, for the phone dock                                     (Change)
├── data/
│   ├── checks.json           # corrected supports; Drip line working / not working          (Change)
│   └── areas/niphad/         # shipped demo area                                            (Built)
├── scripts/reset_demo.py     # one-command reset before each take                           (New)
├── docs/                     # DESIGN.md, idea.md, screenshots                              (Built)
└── devpost/                  # scope, PRD, spec and their review pages
```

## External Services and Dependencies
None on the demo path. The Niphad data is in the repo, and `FIELDDX_LLM=off` keeps Gemini out of it. Earth Engine, Fields of the World and Open-Meteo are only used to build new areas, which is deferred (`prd.md > Deferred From the POC`).

## Important Failure Modes
- **Findings left over from a previous take** → the case opens already updated. Run `python scripts/reset_demo.py` before each take.
- **A Gemini key in `.env`** → updated cases still use the template, and `FIELDDX_LLM=off` covers the first summary too. If the opening summary wording differs from rehearsal, check the variable.
- **The engine output drifts** from what the video script says (for example after another rule edit) → `test_field128_demo.py` fails before recording.
- **Existing tests that expect closing** → rewritten in the same build step, so the suite stays green.

## What Was Simplified and Why
- **No closing at all** instead of a four-outcome closing workflow. The proof is the feedback loop (`prd.md > Deferred From the POC`). A full version would need closing states, a summary screen and a follow-up queue.
- **Template summary** instead of the Gemini case file for the proof, so every run reads the same. Gemini can come back later behind the same validator, once it is taught that findings never confirm.
- **Fixing the check list** instead of special rules in code. One data edit applies the principle to every field, not just Field 128.
- **Shared demo officer, one area.** Sign-in exists but the proof only needs *Try the demo area*.
- **None fits = every cause ruled out.** It is a simple, testable trigger. A richer version could weigh how well the leader is supported.

## Decisions and Open Issues
Learner decisions in this spec:
- **A working drip line (and moist soil) counts only against irrigation failure**, not for pests or nutrients. The rule lives in `data/checks.json`, not in Field 128-specific code.
- **The computed next check stands.** With the corrected rules, Field 128 recommends the leaf undersides first. No location-priority rule is added to keep the drip line first.
- **The demo records Leaves clean.** Pest or disease spread becomes less likely, irrigation failure is unchanged but moves to first, and the next check becomes the drip line. Irrigation failure must never be labelled more likely here.
- **Template summary for the proof and the video.** Gemini stays optional for later and never affects the demo.
- **Local only.** Record locally and upload to YouTube. No deployment.
- **Reproducibility first**: a one-command reset and a Field 128 test before filming.

Implementation details derived from those (agent, agreed in principle):
- Keep the app's existing strict separation scoring. A looser rule, where an *against* result also counts as separating, was tried in simulation and picked leaf yellowing first, because it treated "not pests" as evidence for irrigation. That breaks the learner's principle.
- Findings stored as rows and replayed. Keys `dry`/`wet` kept with new labels.

**The useful unknown.** How does a small evidence rule change ripple through the app? It was clarified by simulating Field 128 under each rule. Correcting one `supports` list changed the first recommended check from the drip line to the leaf undersides. The test in *Demo Reset and Field 128 Check* now pins that behaviour down.

**PRD update.** `prd.md > The Core Journey` and the payoff examples were written around the drip line first. They are revised to match these decisions (leaf undersides first, Leaves clean, then the drip line), with a note that the change came from this spec.

**Open issues.** None blocking. Check during the build: that the existing phone dock and inbox still read well with the new *Investigation updated* label.
