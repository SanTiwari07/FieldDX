---
doc: checklist
status: approved
---

# Build Checklist

Build mode: fast (switched from learn after slice 1, at the learner's request)

## Slices

- [x] **1. Field 128 recommends the leaf undersides first**
  Becomes usable: Opening Field 128 shows the corrected evidence and the computed first check, inspect the leaf undersides, with results reading the new way (Drip line working / not working elsewhere in the check list).
  Why now: The evidence-rule fix is the riskiest change, because it moved the recommended check in simulation. Proving it on the real engine first means every later slice builds on the actual numbers the video will show.
  PRD ref: `prd.md > Reversible but Never Arbitrary`, `prd.md > The Next Check`, `prd.md > The Core Journey` (steps 1–6)
  Spec ref: `spec.md > Check List and Evidence Rules`, `spec.md > Demo Reset and Field 128 Check`
  Build: Correct `drip_line.wet` and `soil_probe.moist` supports in `data/checks.json` and relabel the drip-line results. Start `backend/tests/test_field128_demo.py` with the before-state assertions on the real Niphad case. Update any existing test that encoded the old supports.
  Verify (mechanical): `python -m pytest` in `backend` passes, including the new before-state test (pest or disease spread 0.7 leading, irrigation failure 0.4 possible, first check `leaf_undersides`). Start the API and confirm `GET /api/cases/F128` returns `leaf_undersides` as the next check.
  Learner check: Start the app, choose Try the demo area, open Field 128, and confirm the dark slip now says to inspect the leaf undersides, with pests or lesions visible and leaves clean as the results.
  Commit: `Count working drip lines and moist soil only against irrigation failure`

- [x] **2. Recording Leaves clean keeps the case open and recalculates the next check**
  Becomes usable: On the field checklist, recording Leaves clean returns to an open case. Pest or disease spread drops to less likely, irrigation failure is unchanged but first, and the slip moves to the drip line on the south edge. The finding survives a reload, and one command resets it.
  Why now: This is the kernel, the feedback loop itself. It needs storage, replay, scoring and the next check working together, so it comes before any presentation work.
  PRD ref: `prd.md > Recording a Finding`, `prd.md > Next Check Responds to the Finding`, `prd.md > States and Boundaries` (persistence)
  Spec ref: `spec.md > Findings Store`, `spec.md > Finding Replay`, `spec.md > Next Check Recalculation`, `spec.md > Case Service and API`, `spec.md > Field Checklist`, `spec.md > Demo Reset and Field 128 Check`
  Build: Add the `case_findings` table and functions. Replace `apply_outcome` with `apply_finding` (moves only named causes, never closes, nothing confirmed). Replay findings in `effective_case`. Make `choose()` skip done checks, add the one-live-cause rule and the why-it-changed line. Add `POST /api/cases/{id}/findings` and remove `/close`. Point `Checklist.tsx` at `api.recordFinding`. Add `scripts/reset_demo.py`. Extend the Field 128 test with the after-Leaves-clean assertions, and rewrite the closing tests in `test_logic.py`.
  Verify (mechanical): `python -m pytest` passes, including after Leaves clean (pest 0.2 possible, irrigation 0.4 unchanged and first, nutrient and standing water unchanged, case open, next check `drip_line`, no cause confirmed). Through the running API: post the finding, reload the case, and see the same result. Run `scripts/reset_demo.py` and see the case return to its before state. `npm run build` in `frontend` succeeds.
  Learner check: Open Field 128, go to the field checklist, record Leaves clean, and confirm you land back on an open case whose slip now says to check the drip line and valve on the south edge. Reload the page and confirm it's still there, then run `python scripts/reset_demo.py` and confirm Field 128 is back to the leaf-undersides check.
  Commit: `Keep cases open after a finding and recompute the next check`

- [x] **3. The case shows Investigation updated with a clear before-and-after**
  Becomes usable: After a finding, the case shows the quiet Investigation updated pill, the finding with its evidence link, each cause's movement chip (word plus glyph) with a one-line reason, the slip's why-it-changed line, and a template summary that never says confirmed.
  Why now: Slice 2 makes the logic right. This slice makes it readable, answering what changed, why, and what next, which is the moment the video depends on.
  PRD ref: `prd.md > Investigation Update After a Finding`, `prd.md > Look and Feel`
  Spec ref: `spec.md > Finding Replay` (update record), `spec.md > Case Screen: Investigation Update`, `spec.md > Template Summary`, `spec.md > Look and Feel`
  Build: Add the `InvestigationUpdate`/`CauseMove` models and the update record, including the unchanged-but-now-first reason. Template summary for cases with findings, and skip the model for them. Replace `ResolutionCard` with `InvestigationUpdate`, add movement chips in `Diagnosis.tsx`, drop the confirmed/closed branches in `Summary.tsx` and `Dock.tsx`, and show the reason on the slip. Inbox and home show an updated case as open.
  Verify (mechanical): `python -m pytest` passes, with the Field 128 test asserting the movement labels (pest less likely, irrigation unchanged with a now-first reason) and no `confirmed` in the case or summary text. `npm run build` succeeds. In the running app after Leaves clean, the page text contains Investigation updated, LESS LIKELY, UNCHANGED, and the drip-line reason, and does not contain confirmed. Screenshot taken.
  Learner check: Record Leaves clean on Field 128 and read the case top to bottom. Can you tell at a glance what changed, why, and what to do next, without anything saying confirmed?
  Commit: `Show the investigation update after a finding`

- [ ] **4. Honest edge cases: no cause fits, and a drip line found working**
  Becomes usable: A finding that leaves every cause ruled out shows that none of the current explanations fits well and suggests a call or visit. Recording Drip line working on its own rules out irrigation failure without reviving nutrient deficiency. The phone dock and inbox read correctly.
  Why now: These protect the principles (no forced diagnosis, reversible but never arbitrary) once the main loop is solid. They are not in the video, so they come after it works.
  PRD ref: `prd.md > When No Cause Fits`, `prd.md > Reversible but Never Arbitrary`, `prd.md > States and Boundaries`
  Spec ref: `spec.md > Finding Replay` (none fits), `spec.md > Next Check Recalculation` (one live cause), `spec.md > Demo Reset and Field 128 Check`
  Build: Route an all-ruled-out case to the `unexplained` outcome with its message and a call-or-visit check. Add the Drip-line-working-alone assertions and a none-fits test. Check the phone dock and inbox at mobile width and fix the labels if needed.
  Verify (mechanical): `python -m pytest` passes, including the new edge-case tests. `npm run build` succeeds. At 375 px wide, the updated Field 128 case and the inbox show the update label without overflow. Screenshot taken.
  Learner check: After Leaves clean, record the next recommended check, Drip line working. Confirm irrigation failure is now ruled out, nutrient deficiency is still unchanged, pest or disease spread is not confirmed, and the slip suggests calling the farmer or visiting. Then look at the updated case on a phone-sized window. (Drip line working as the very first finding is covered by the test, because the checklist only offers the recommended check.)
  Commit: `Handle findings that fit no cause and keep ruled-out causes honest`

## Hands-on Checkpoints

- [ ] Early usable behavior explored — folded into the final kick-the-tires session (fast mode, learner asked to build all slices quickly)
- [ ] Final kick-the-tires exploration and feedback completed

## Final Review

- [ ] Final review complete — feedback resolved and learner confirms ready to ship

## Code Tour and App Map

- [ ] Learning activity complete — guided route, focused alternative, prior practice connected, or brief recap
- [ ] Optional edit and transfer reflection addressed — offered/declined/already covered/not applicable as appropriate
- [ ] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: not started
Route and stops: not started
Edit outcome: not started
Reflection: not started
Activity mode: not started

## Revisions

- The test fixture's irrigation-led case (HERO) now also starts at the leaf undersides rather than the drip line — the corrected evidence rules apply to every field, so the test was updated to the computed answer instead of special-casing it.
- The check's on-screen label is "Photograph leaf undersides in the affected patch" (its existing wording in `data/checks.json`); the planning docs' "inspect the leaf undersides" refers to this same check.
- Early hands-on checkpoint folded into the final review — the learner switched to fast mode after slice 1 and asked for all slices quickly, so the loop is tried once, end to end, at the final checkpoint.
