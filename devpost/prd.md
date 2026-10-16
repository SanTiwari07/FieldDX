---
doc: prd
status: approved
---

# FieldDx — Product Requirements

FieldDx helps a field officer at a farmer producer organisation work out why a field lost greenery and which single check to do next, without claiming more than the evidence supports.
Source: `scope.md > The Unique Kernel`, `scope.md > Who It's For`.

*Sanskar Tiwari and Shambhavi Patil.*

**How to read the labels.** FieldDx was mostly built before this PRD, so every behaviour carries one label (`scope.md > Carried Into the PRD`):
- **Verified**: run on the real Field 128 case during this review, and it behaves as described.
- **Built**: exists in the app today, but was not re-checked during this review.
- **Change**: exists, but behaves differently from what this PRD asks for.
- **New**: does not exist yet.

## The Core Journey
Develops `scope.md > The Core Loop` and `scope.md > What "Working" Looks Like`.

1. The officer opens FieldDx on the Niphad demo area and sees the fields that need attention beside the area map. **Built**
2. They open Field 128, flagged for a greenery drop near the south edge (alert date 5 Oct 2026). **Verified**
3. The case shows the satellite imagery, the change in greenery over time, and the evidence behind the alert. **Built**
4. The investigation runs its checks before any diagnosis. First: is the drop real (image quality)? Then: is it ordinary (harvest, pruning, weather, neighbours)? Only after that are causes ranked. **Built**
5. Field 128's ranked causes: pest or disease spread leading (high), irrigation failure possible (medium), nutrient deficiency and standing water ruled out. Each cause shows evidence for and against. **Verified**
6. The dark next-check slip recommends checking the drip line and valve on the south edge, and says what each result would mean. **Verified**
7. On the field checklist, the officer records the example finding **Drip line working**. **Built** for recording, **Change** for what happens next.
8. **The payoff.** The case stays open and shows *Investigation updated*:
   - Irrigation failure is ruled out, with the reason.
   - Pest or disease spread is still leading, but not confirmed.
   - Nutrient deficiency stays ruled out.
   - The next check changes to inspecting the undersides of leaves for thrips or mildew, with the reason.

   **Change / New**

Success means the screen answers three questions at once: what changed, why it changed, and what to do next.

## Screens and Layout
No new screens. The proof uses screens the app already has. **Built**
- **Today / dashboard**: the fields needing attention, with the Niphad map.
- **Case**: summary, imagery, greenery trend, evidence timeline, the investigation with ranked causes, and the dark next-check slip.
- **Field checklist**: where the officer records the result of the recommended check.
- **Phone view**: the case summary, recommended check and finding form work on a phone (`scope.md > The POC Boundary`).

After recording a finding, the officer is back on the **Case** screen, which shows the updated investigation (see *Investigation Update After a Finding*).

## Look and Feel
Keep the existing visual language in `docs/DESIGN.md`. No new design system. **Built**
- A calm, well-organised clinical case file: serious about evidence, open about uncertainty, focused on the officer's next decision.
- Lichen-grey canvas, monsoon-teal type, turmeric for what needs the officer.
- **The dark next-check slip stays the strongest element on the page.**
- **The *Investigation updated* moment is noticeable but quiet**: a small status label near the top of the case. It is not a success popup or a celebration, because the investigation isn't necessarily solved. **New**
- Changes use subtle movement indicators **with short word labels** (less likely, still leading, new evidence), never colour alone. **New**

## Features and Behavior

### Alert Triage Before Diagnosis
Develops `scope.md > The Core Loop` steps 2–3. **Built**
- Before ranking causes, FieldDx checks whether the drop is real (clouds, shadows, poor imagery, pixels mixing with nearby land) and whether something ordinary explains it (harvest, pruning, weather, the same change in neighbouring fields).
- An alert explained at this stage is set aside as a false alarm or ordinary change, with the reason shown.
  - [ ] Field 128's case shows the data-quality and ordinary-change checks before the ranked causes.

### Ranked Causes With Evidence
Develops `scope.md > The Core Loop` step 4. **Verified**
- Each cause shows its status (leading, possible, ruled out), how sure FieldDx is, and evidence lines for and against, each linked to an evidence item.
  - [ ] Field 128 shows pest or disease spread leading, irrigation failure possible, and nutrient deficiency and standing water ruled out, each with linked evidence.

### The Next Check
Develops `scope.md > The Unique Kernel`. **Verified**
- One practical check is recommended, chosen because its possible results separate the leading causes. It shows what each result would mean.
  - [ ] Field 128's slip recommends checking the drip line and valve on the south edge, with results for not working (points to irrigation failure) and working (look at the leaves for thrips and mildew).

### Recording a Finding
Develops `scope.md > The Core Loop` step 6. **Built**, with a **Change**
- The officer records the result of the recommended check on the field checklist. **Built**
- The finding appears in the evidence timeline as a new field-visit item, marked as observed by the officer. **Built**
- The two drip-line results read **Drip line working** and **Drip line not working**. These describe what the officer saw, not a diagnosis. **Change**: today they read Drip line wet and Drip line dry.
- **Recording a finding does not close or resolve the case.** **Change**: today any finding closes the case and the top cause shows as confirmed on the ground.
  - [ ] After recording Drip line working on Field 128, the case is still open and the field-visit item is in the evidence timeline.
  - [ ] Nothing on the screen says confirmed or closed.

### Investigation Update After a Finding
The payoff. Develops `scope.md > What "Working" Looks Like` step 6 and `scope.md > Carried Into the PRD`. **New**
- The current confirmation card (Confirmed on the ground) is **replaced** by an *Investigation updated* state. **Change**
- That state shows three things: the new evidence, what changed in the ranking of causes, and the next recommended check.
- A short **before-and-after** for the causes. Each cause carries a movement label (more likely, less likely, ruled out, unchanged, newly considered) and, if it changed, one line saying why, linked to the evidence that caused it. Example: *Irrigation failure ruled out: the officer recorded that the drip line is working.*
- The leading cause can stay leading, but it reads as still leading, not confirmed.
- The case shows clearly that the investigation is still open.
  - [ ] After Drip line working on Field 128, irrigation failure shows ruled out with a reason that cites the field-visit evidence.
  - [ ] Pest or disease spread shows still leading, and the word confirmed appears nowhere.
  - [ ] Every cause whose position or status changed has a movement label and a one-line reason. Unchanged causes show unchanged.
  - [ ] The update makes sense without colour: each change has a word label.

### Reversible but Never Arbitrary
**Change**
- A finding raises a cause only if it directly supports that cause. Ruling one cause out never promotes another, because the absence of evidence for one cause is not evidence for another.
- A cause ruled out on strong evidence comes back only with meaningful contradicting evidence, and the screen explains why the earlier conclusion is being reconsidered.
- **Change**: today a working drip line brings nutrient deficiency back from ruled out to possible (medium), because it counts as support for that cause.
  - [ ] After Drip line working on Field 128, nutrient deficiency stays ruled out and shows unchanged.
  - [ ] Any cause that rises shows the specific evidence that raised it.

### Next Check Responds to the Finding
Develops `scope.md > Carried Into the PRD`. **New**
- When a finding changes the investigation, the dark slip moves to the next most useful check. It says why the recommendation changed and what each result would mean.
- For Field 128 after Drip line working, the next check is to inspect the undersides of leaves for thrips or mildew. FieldDx's check list already names this as the follow-up to a working drip line.
  - [ ] After Drip line working, the slip shows the leaf-underside check, with a reason that refers to the drip-line finding.
  - [ ] The slip remains the strongest visual element on the case.

### When No Cause Fits
**New**. A build requirement, **not part of the one-minute demo** unless there is a genuine, reproducible example.
- If a finding fits none of the current causes (for example, the leaves look healthy), FieldDx records it as evidence, notes that the expected signs weren't found, and reassesses. It can say that none of the current explanations fits well instead of forcing a diagnosis.
- It does not conclude the whole field is healthy or that the alert was false, since a field visit only observes what was checked at that time. It suggests another check or an expert assessment.
  - [ ] A finding that supports no cause does not make any cause leading or confirmed on its own, and the case says none of the current explanations fits well.

## States and Boundaries
- **Alert set aside**: the drop is not real, or something ordinary explains it. The case shows why, and no causes are ranked. **Built**
- **Open, before any finding**: ranked causes and one next check. **Verified** on Field 128.
- **Open, investigation updated**: after a finding, with the before-and-after and a new next check. The case is still open. **New**
- **None of the causes fits**: the observation is kept, no diagnosis is forced, and a next step is suggested. **New**
- **Persistence**: a recorded finding stays in the case's evidence timeline when the officer comes back later. **Built** today for closed cases. Check during the build that it still holds once cases stay open.
- **Phone**: the case summary, next check and finding form are usable on a phone. **Built**, not re-checked during this review.

## Product Decisions
- **Recording a finding never closes a case.** Closing is a deliberate officer action. Ruling out one cause is not the same as confirming another.
- **Ruling out is not confirming.** After a finding, the top cause is still leading, not confirmed, unless field evidence directly confirms it.
- **Causes are reversible, never arbitrarily.** Only direct evidence raises a cause.
- **The finding is named Drip line working** (and Drip line not working). It describes the observation without implying a diagnosis.
- **The confirmation card is replaced by Investigation updated.** It shows the new evidence, the change in ranking, and the next check.
- **Quiet update, loud next check.** The update is a small label and a short before-and-after. The dark slip stays the strongest element.
- **Words as well as colour** for every change.
- **The demo ends at Investigation updated plus the new next check.** The full closing workflow is deferred, so the proof stays on one reliable, honest investigation from start to finish.
- **When No Cause Fits is built but not filmed** unless a genuine, reproducible example exists.
- **Keep the existing design language** in `docs/DESIGN.md`.

## What We're Building
For the proof, on the Niphad demo area and Field 128:
1. Recording a finding no longer closes the case or marks anything confirmed, and the drip-line results read Drip line working and Drip line not working.
2. The *Investigation updated* state, replacing the confirmation card, with the new evidence, a before-and-after for the causes, and evidence-linked reasons.
3. Re-ranking that raises a cause only on direct evidence. Nutrient deficiency stays ruled out after Drip line working.
4. The next check updates after a finding, with the reason: inspect the leaf undersides for thrips or mildew.
5. The state for when none of the current explanations fits well.

Everything else in the core journey already exists and should keep working.

## Deferred From the POC
- **Full closing workflow** with four outcomes: cause identified, no active issue found, inconclusive and needs follow-up, data issue or false alarm. Deferred because the demo proves the feedback loop, not case management.
- **Summary and confirmation screen** before closing.
- **Follow-up state** with scheduling, reminders and tracking.
- **Advanced handling** of unusual findings and expert escalation.
- From scope: sign-in and accounts, region overview, building new areas on demand, correcting field shapes, Ask FieldDx chat, polishing every phone screen, and learning from past findings (`scope.md > Later`). These exist in the app but are not part of the proof.

## Possible Later Enhancements
- An officer-confirmed cause, clearly separated from a cause only suggested by satellite data, once closing exists.
- A closed case that keeps the original alert, every finding and the reasoning for future reference.

## Non-Goals
- **FieldDx does not declare a diagnosis.** The officer stays responsible for the field decision.
- **No celebration or success popup** after a finding. The investigation isn't solved.
- **No new design system.**
- **No new areas or regions** for the proof. Niphad only.

## Open Questions
None blocking. Both earlier questions are now Product Decisions: the finding's name, and replacing the confirmation card.
