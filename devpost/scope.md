---
doc: scope
status: approved
---

# FieldDx

Differential diagnosis for farm fields. When a field loses greenery, FieldDx works out what probably happened, what it wasn't, and the one check that settles it.

*Built by Sanskar Tiwari and Shambhavi Patil.*

## The Unique Kernel
"The most important part is what happens next." FieldDx doesn't stop at a red patch or a list of possible causes. It picks **one practical check whose possible outcomes best separate the leading causes**, for example the drip line and valve along the south edge of a vineyard. The officer's finding then goes back in as new evidence and changes the assessment. It stays honest about uncertainty: "I don't want it to confidently diagnose something when the available data isn't enough."

## Who It's For
A field officer at a farmer producer organisation (FPO), starting in Indian farming communities such as Niphad near Nashik. They are responsible for more farms than they can physically visit. Free satellite maps show them *that* a field lost greenery, not *why*. It might be disease, pests, irrigation, normal harvesting or pruning, weather, or a cloudy image raising a false alarm. Today they chase alerts with little to go on, or they ignore them.

## The Core Loop
1. Open FieldDx and see the fields in their area where greenery has dropped.
2. Open one field: what changed, when, and how reliable the satellite observation is.
3. FieldDx checks whether the drop is real (clouds, shadows, poor imagery, pixels mixing with nearby land) and whether something ordinary explains it (harvest, pruning, weather, the same change in neighbouring fields).
4. If it is still concerning, FieldDx ranks the possible causes (irrigation failure, pest or disease spread, nutrient deficiency, standing water), with the evidence for and against each one and the uncertainty made clear.
5. It recommends one next check. The officer decides whether to call the farmer, ask a few questions, or visit.
6. The officer records what they found. That finding becomes evidence, FieldDx updates the case, and the case is resolved, monitored, or investigated further.

They come back because it means "less time chasing false alarms and more time investigating fields that genuinely need attention."

## Inspiration & Identity
A case file, not a heatmap: an investigation the officer can read and question, rather than a red patch on a map. It should "support their judgement, not replace their experience or pretend that satellite imagery can see everything happening on the ground." Existing visual direction is in [docs/DESIGN.md](../docs/DESIGN.md). `3-prd` confirms look and feel.

## Why This Matters to the Learner
"The gap between detecting a problem and actually helping someone decide what to do about it." Sanskar wants to use AI and satellite data for real problems in agriculture, especially for small farmers, "not just another AI project or a good-looking dashboard." Success means "technically useful, honest about its limitations, and practical enough that a field officer could understand what to do next without blindly trusting an AI-generated answer."

## What "Working" Looks Like
A one-minute demo on one real case, Field 128 in the Niphad area, with a suspected pest or disease spread near the south edge:

1. The dashboard shows the fields needing attention and the Niphad map. Open Field 128.
2. The case shows the satellite imagery, the greenery change over time, and the evidence behind the alert.
3. The investigation shows the data-quality check, the neighbour comparison, weather and season, and the ranked causes. It "doesn't jump straight from a red patch to a diagnosis."
4. The recommended check is to inspect the drip line and valve along the south edge, chosen because its outcomes separate an irrigation problem from pest or disease spread.
5. On the field checklist, record a clearly labelled example finding: the drip line is working properly.
6. **The moment to remember:** the evidence and the ranking visibly change on screen because of that finding, not just a "resolved" stamp.

The full cycle: a satellite alert becomes an investigation, the investigation gives a practical next step, and the officer's finding feeds back into the assessment.

## The POC Boundary
- One real area: the existing Niphad dataset (real Sentinel-2 imagery, field shapes and weather), already shipped in the repo.
- Real alerts, with the image-quality and "ordinary explanation" checks.
- Evidence-backed ranking of causes, with uncertainty shown.
- One recommended next check per case, chosen to separate the leading causes.
- Recording a finding, which updates the evidence and the ranking.
- A responsive phone view for the essentials only: case summary, recommended check, finding form.

## Later
Each of these has a real purpose but isn't needed to prove the loop:
- **Sign-in and accounts.** Matter once several officers share the platform. A ready demo is enough to prove the loop.
- **Region overview.** Helps officers discover where crop health is changing, but the proof starts once an alert exists for a field.
- **Marking land and building new areas on demand.** Key for other regions, but brings heavy data-processing complexity. Prove the investigation on Niphad first.
- **Correcting field shapes.** Add it when testing shows wrong boundaries are a significant problem.
- **Ask FieldDx chat.** The case screen should explain the causes, evidence and next check clearly without a chat.
- **Polishing every screen for phones.** Wait until the core workflow is validated.
- **Learning from past findings** across cases to make future investigations more useful.

## Explicitly Cut
Nothing is cut permanently. "Most have a genuine purpose; they simply don't all need to exist at the beginning."

## Where This Stands
This scope was written after most of FieldDx was built, as a deliberate look back. The app already includes several of the *Later* items. The reflection, in Sanskar's words: "I think I tried to build too much around the core idea. If I were starting again, I'd focus on proving the investigation loop first." The build and the demo should keep the investigation loop at the center, and treat the rest as supporting features rather than part of the proof.

## Carried Into the PRD
Raised at scope review:
- **Define the payoff exactly.** After the officer records a finding, what changes: how the evidence updates, how the ranking of causes moves, and how the recommended next check responds. The before-and-after should be easy to follow in the demo without a long explanation.
- **Built vs. proposed.** Each behaviour in the PRD and spec says whether the existing FieldDx implementation already does it (verified), or whether it is something to demonstrate or improve. "So we don't accidentally promise behaviour that hasn't been verified."
