---
version: alpha
name: FieldDx Case File
description: The design language for FieldDx, a differential-diagnosis tool for farm fields. It reads like a clinical case file kept by a field agronomist. The chrome is calm and neutral, the data carries the colour, and every claim is visibly tied to a piece of evidence. Light canvas, hairline rules, tight corners, tabular numbers, and one dark "prescription slip" for the next best check, which is the only loud element on screen.

colors:
  # Chrome: neutral, so the map and the evidence carry the colour
  canvas: "#ffffff"
  canvas-subtle: "#f8fafc"
  canvas-sunken: "#f1f4f3"
  border: "#e5e7eb"
  border-subtle: "#f3f4f6"
  border-strong: "#d1d5db"
  ink: "#101c16"
  ink-hover: "#22302a"
  text-primary: "#101c16"
  text-secondary: "#5c6670"
  text-tertiary: "#737b82"
  text-disabled: "#b4b8bc"
  on-ink: "#ffffff"
  focus: "#10b981"

  # Brand: used sparingly, never as a data colour
  brand: "#065f2c"
  brand-wash: "#e5f4e9"

  # Severity (inbox ranking): icon + text always, never colour alone
  severity-high: "#b91c1c"
  severity-high-soft: "#fceaea"
  severity-high-border: "#f6c9c9"
  severity-medium: "#8a5a00"
  severity-medium-soft: "#fdf4e3"
  severity-medium-border: "#f6dfae"
  severity-low: "#5c6670"
  severity-low-soft: "#f2f3f2"

  # Case status
  status-resolved: "#065f2c"
  status-resolved-soft: "#e5f4e9"
  status-dismissed: "#737b82"
  status-area-alert: "#1769aa"
  status-area-alert-soft: "#e7f2fd"

  # Evidence polarity (left rule + glyph + word)
  evidence-for: "#1769aa"
  evidence-against: "#5c6670"
  evidence-unknown: "#b4b8bc"

  # Scene quality
  quality-usable: "#065f2c"
  quality-partial: "#8a5a00"
  quality-cloudy: "#737b82"
  quality-none: "#b4b8bc"

  # Map: change in NDVI vs the field's own baseline (diverging, no red, no traffic-light green)
  dndvi-loss-3: "#7a3410"
  dndvi-loss-2: "#b8662a"
  dndvi-loss-1: "#e7b98a"
  dndvi-zero: "#f2f1ee"
  dndvi-gain-1: "#a9d4cf"
  dndvi-gain-2: "#4e9a93"
  dndvi-gain-3: "#145e59"

  # Timeline / legend only: absolute NDVI, soil to canopy
  ndvi-0: "#8a6a3b"
  ndvi-1: "#c9b57a"
  ndvi-2: "#e4e7b8"
  ndvi-3: "#a9cf8e"
  ndvi-4: "#5da66a"
  ndvi-5: "#1f6f4a"

  # Map overlays
  overlay-field-outline: "#101c16"
  overlay-halo: "#ffffff"
  overlay-zone-selected: "#1769aa"
  overlay-pixel-grid: "rgba(255,255,255,0.35)"
  overlay-nodata-hatch: "#d1d5db"

typography:
  display:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: -0.022em
  heading-1:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: -0.018em
  heading-2:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: -0.011em
  heading-3:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: -0.011em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: -0.011em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: -0.011em
  ui-label:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: 0
  caption:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0
  eyebrow:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: 0.06em
    textTransform: uppercase
  data-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: 600
    lineHeight: 1.15
    fontVariantNumeric: tabular-nums
  data-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.3
    fontVariantNumeric: tabular-nums
  evidence-id:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 700
    lineHeight: 1
    fontVariantNumeric: tabular-nums

rounded:
  none: 0px
  xs: 4px
  sm: 6px
  md: 8px
  lg: 12px
  pill: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 20px
  xl: 24px
  xxl: 32px
  section: 40px

elevation:
  flat: "none"
  raised: "0 1px 2px rgba(16,28,22,0.04), 0 2px 8px rgba(16,28,22,0.04)"
  overlay: "0 8px 28px rgba(16,28,22,0.12)"

motion:
  ease: "cubic-bezier(0.16, 1, 0.3, 1)"
  fast: 120ms
  base: 180ms
  stagger: 250ms

components:
  app-bar:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.text-primary}"
    borderColor: "{colors.border}"
    typography: "{typography.ui-label}"

  wordmark:
    textColor: "{colors.brand}"
    typography: "{typography.heading-3}"

  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-ink}"
    typography: "{typography.ui-label}"
    rounded: "{rounded.sm}"
    padding: "10px 16px"

  button-secondary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.text-primary}"
    borderColor: "{colors.border-strong}"
    typography: "{typography.ui-label}"
    rounded: "{rounded.sm}"
    padding: "10px 16px"

  button-ghost:
    textColor: "{colors.text-secondary}"
    typography: "{typography.ui-label}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"

  inbox-row:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.text-primary}"
    rowBorder: "{colors.border}"
    typography: "{typography.body-md}"
    padding: "{spacing.sm} {spacing.md}"

  inbox-row-dismissed:
    backgroundColor: "{colors.canvas-subtle}"
    textColor: "{colors.text-tertiary}"
    typography: "{typography.body-md}"

  severity-badge:
    typography: "{typography.caption}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"

  quality-badge:
    typography: "{typography.caption}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"

  evidence-card:
    backgroundColor: "{colors.canvas}"
    borderColor: "{colors.border}"
    leftRuleWidth: 3px
    rounded: "{rounded.md}"
    padding: "{spacing.sm} {spacing.md}"
    typography: "{typography.body-md}"

  evidence-ref:
    backgroundColor: "{colors.canvas-sunken}"
    textColor: "{colors.text-primary}"
    typography: "{typography.evidence-id}"
    rounded: "{rounded.xs}"
    padding: "2px 6px"

  agent-step:
    textColor: "{colors.text-secondary}"
    typography: "{typography.body-md}"

  hypothesis-card:
    backgroundColor: "{colors.canvas}"
    borderColor: "{colors.border-strong}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"

  hypothesis-card-ruled-out:
    backgroundColor: "{colors.canvas-subtle}"
    textColor: "{colors.text-tertiary}"
    borderColor: "{colors.border}"
    rounded: "{rounded.md}"

  confidence-meter:
    filled: "{colors.ink}"
    empty: "{colors.border}"
    segments: 3

  next-check-slip:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-ink}"
    typography: "{typography.body-lg}"
    rounded: "{rounded.md}"
    padding: "{spacing.xl}"

  check-candidates-table:
    headerBackground: "{colors.canvas-subtle}"
    headerTypography: "{typography.eyebrow}"
    bodyTypography: "{typography.data-sm}"
    rowBorder: "{colors.border}"
    winnerRowBackground: "{colors.canvas-sunken}"

  limits-note:
    backgroundColor: "{colors.canvas-subtle}"
    textColor: "{colors.text-secondary}"
    borderColor: "{colors.border}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"

  scenario-banner:
    backgroundColor: "{colors.severity-medium-soft}"
    textColor: "{colors.severity-medium}"
    borderColor: "{colors.severity-medium-border}"
    typography: "{typography.caption}"

  map-frame:
    backgroundColor: "{colors.canvas-sunken}"
    borderColor: "{colors.border}"
    rounded: "{rounded.md}"

  timeline-chart:
    backgroundColor: "{colors.canvas}"
    gridline: "{colors.border-subtle}"
    affectedZoneLine: "{colors.ink}"
    otherZoneLine: "{colors.border-strong}"
    expectedBand: "{colors.canvas-sunken}"

  close-case-form:
    backgroundColor: "{colors.canvas}"
    borderColor: "{colors.border}"
    rounded: "{rounded.md}"
    padding: "{spacing.xl}"

  text-input:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.text-primary}"
    borderColor: "{colors.border-strong}"
    typography: "{typography.body-md}"
    rounded: "{rounded.sm}"
    padding: "10px 12px"

---


## Overview

FieldDx is a case file, not a dashboard. The officer opens it to decide where to go today and what to check when they get there, so the design favours **reading and trusting** over browsing. The metaphor is a clinician's chart: a ranked list of patients (the inbox), a chart per patient (the case), test results (evidence cards), a differential (ranked hypotheses), and an order for one test (the next best check).

Three rules shape everything:

1. **The chrome stays neutral so the data can speak.** Buttons, panels and navigation are ink, white and grey. Colour is reserved for things that mean something: severity, scene quality, NDVI change and evidence polarity. In particular, green is *not* the action colour. On a map of vegetation, green already means "healthy", and a green button competes with it.
2. **Every claim shows its source.** Any sentence in a diagnosis carries evidence chips (`E1`, `E4`). Missing evidence is shown as "unknown", never filled in.
3. **One loud element per screen.** The next best check is set on a dark ink "prescription slip". Nothing else on screen uses a dark fill, so the eye lands there.

**Key characteristics**
- Light canvas only (`{colors.canvas}` / `{colors.canvas-subtle}`). Officers use it in offices and daylight; no dark mode in v1.
- Ink (`{colors.ink}`) is the action colour. Brand green (`{colors.brand}`) appears only in the wordmark and the "resolved" state.
- Hairline borders and pale sunken fills separate content; shadows are rare and very soft.
- Tight corners: controls at `{rounded.sm}`, cards at `{rounded.md}`. It should feel like a precise instrument, not a consumer app.
- Every number uses tabular figures and states its date.
- Status is always **icon + word**, never colour alone.

## Colors

### Chrome
- **Canvas** `{colors.canvas}` #ffffff: cards, the inbox table, forms.
- **Canvas subtle** `{colors.canvas-subtle}` #f8fafc: the page behind cards; dismissed inbox rows.
- **Canvas sunken** `{colors.canvas-sunken}` #f1f4f3: the map frame background, evidence-ID chips, the winning row in the check-candidates table.
- **Ink** `{colors.ink}` #101c16: headings, body text and the primary button. A green-black rather than pure black, so it sits warmly next to the map.
- **Text secondary / tertiary** #5c6670 / #737b82: labels, metadata, dismissed rows. Tertiary is the lightest grey that still passes 4.5:1 on white.

### Brand
- **Brand** `{colors.brand}` #065f2c: the wordmark and "resolved" status only. Never a button, never a map colour.

### Severity (inbox)
| Level | Text | Fill | Icon | Word |
|---|---|---|---|---|
| High | #b91c1c | #fceaea | octagon-alert | "High" |
| Medium | #8a5a00 | #fdf4e3 | triangle-alert | "Medium" |
| Low | #5c6670 | #f2f3f2 | arrow-down-circle | "Low" |

Severity × confidence sets the inbox order. Severity colour appears only on the badge, never as a full row fill.

### Case status
- **Open** has no colour; it's the default.
- **Area alert** `{colors.status-area-alert}` blue: Stage 2 found a shared, regional cause. Shown with a "map-pin-group" icon and the word "Area alert".
- **Dismissed** `{colors.status-dismissed}` grey: the row is muted and always shows its reason ("Cloud on Oct 4 scene", "Grape fruit pruning, expected").
- **Resolved** `{colors.status-resolved}` brand green, with a check icon.

### Evidence polarity
An evidence line inside a hypothesis has a 3px left rule, a glyph and a word:
- **For**: `{colors.evidence-for}` blue rule, "+" glyph, "supports".
- **Against**: `{colors.evidence-against}` slate rule, "−" glyph, "against".
- **Unknown**: dashed `{colors.evidence-unknown}` rule, "?" glyph, "unknown". The text says what would resolve it ("No clear scene since Oct 9").

### Scene quality
| Class | Colour | Icon | On screen |
|---|---|---|---|
| Usable | #065f2c | circle-check | Value shown |
| Partial | #8a5a00 | circle-dashed | Value shown with "partial" badge |
| Cloudy | #737b82 | cloud-off | **No number.** Reason shown instead |
| No image | #b4b8bc | circle-help | **No number.** "No pass in this window" |

A cloudy scene never shows NDVI 0 or a blank cell that reads as zero. In the timeline it's a hollow marker; on the map it's a grey hatch.

### Map: NDVI change
The case map shows **change versus the field's own recent baseline**, not raw NDVI. Raw NDVI makes a young crop look "stressed"; change shows what actually moved.

`#7a3410 → #b8662a → #e7b98a → #f2f1ee → #a9d4cf → #4e9a93 → #145e59`
(big loss → no change → big gain)

This is a brown-to-teal diverging ramp. It avoids red (reserved for severity) and avoids the red/green pairing that colour-blind officers can't separate. Bins are fixed and listed in the legend with their ΔNDVI values, e.g. "≤ −0.15".

### Timeline: absolute NDVI
Raw NDVI appears only in the timeline axis band and legend: `#8a6a3b → #c9b57a → #e4e7b8 → #a9cf8e → #5da66a → #1f6f4a` (bare soil → dense canopy). Values are never clipped to the legend range.

## Typography

**Inter** for everything, with `tabular-nums` on every number so columns and live-updating values don't jitter. No monospace. Evidence IDs are bold tabular Inter in a sunken chip, which reads as a reference without looking like code.

| Token | Size | Weight | Use |
|---|---|---|---|
| `display` | 28px | 700 | Case title: field name + village |
| `heading-1` | 22px | 700 | Screen titles |
| `heading-2` | 18px | 600 | Section titles: "Investigation", "Diagnosis" |
| `heading-3` | 15px | 600 | Card titles, hypothesis names |
| `body-lg` | 16px | 400 | The next-best-check instruction |
| `body-md` | 14px | 400 | Default text, evidence lines |
| `ui-label` | 14px | 600 | Buttons, tabs |
| `caption` | 12px | 500 | Dates, badges, legends |
| `eyebrow` | 11px | 600, uppercase | Field labels above values, table headers |
| `data-lg` | 24px | 600, tabular | Headline numbers: ΔNDVI, days without rain |
| `data-sm` | 13px | 500, tabular | Table numbers |
| `evidence-id` | 12px | 700, tabular | `E1`, `E2`… |

Numbers carry a unit and a date: "ΔNDVI −0.21 · Oct 9 vs Sep 24", "0 mm rain · last 12 days". NDVI is shown to two decimals.

Hierarchy comes from weight and size together. Uppercase is only for `eyebrow` labels.

## Layout

### Spacing
4px base. Tokens: 4, 8, 12, 16, 20, 24, 32, 40. Use 16 inside cards, 24 between cards, 40 between screen sections.

### Screens

**Inbox** (desktop-first, works on tablet)
A single table, not cards. Columns: severity, field + village, crop, what changed (ΔNDVI + date), leading hypothesis, confidence, status. Open cases sit on top in severity × confidence order. Dismissed cases sit below a "Dismissed automatically (2)" divider, muted, each with its reason. Area alerts appear as one grouped row, not as one row per field.

**Case** (two columns at ≥1024px)
- Left (about 60%): `map-frame` with the field, its zones, the ΔNDVI overlay and the 10 m pixel-grid toggle; below it, `timeline-chart` per zone.
- Right (about 40%): the investigation rail. Agent steps run top to bottom, then the diagnosis, then the next-check slip.
- Under 1024px the columns stack: map, then investigation, then timeline.

**Next best check / field checklist** (must work at 375px)
This is what the officer opens on their phone at the field. It needs one column, large tap targets (44px minimum), the instruction in `body-lg`, a "what each result means" list, and the close-case form directly under it.

**Close case**
A short form: what you found (free text), photo (optional), result chips that map to the candidate check's outcomes ("Drip line dry", "Drip line wet"). After saving, the finding appears as a new evidence card (`E7`) and the hypothesis ranking re-orders with a short animation.

### Grid
Content max width 1200px, 24px gutters on desktop, 16px on mobile. No horizontal scroll at 375px; the inbox table turns into stacked rows on mobile, with severity and field name on the first line.

## Elevation & Depth

| Level | Treatment | Use |
|---|---|---|
| 0 | Flat | Page, table rows, timeline |
| 1 | 1px `{colors.border}` | Cards, evidence cards, map frame |
| 2 | `{elevation.raised}` | Hypothesis cards, the next-check slip |
| 3 | `{elevation.overlay}` | Dialogs, map popovers |

Depth comes from the sunken/subtle fills and the one dark slip, not from shadows.

## Shapes

| Token | Value | Use |
|---|---|---|
| `xs` | 4px | Evidence-ID chips |
| `sm` | 6px | Buttons, inputs, limits note |
| `md` | 8px | Cards, map frame, next-check slip |
| `lg` | 12px | Dialogs only |
| `pill` | 9999px | Badges |

## Components

### Inbox
**`inbox-row`**: one line per case on a hairline. The leading hypothesis is in `heading-3` and confidence is a small `confidence-meter`. The whole row is clickable, with a hover fill of `{colors.canvas-subtle}`.

**`inbox-row-dismissed`**: muted text plus a reason chip. It is never hidden, because showing the dismissals is what makes the open cases believable.

### Investigation
**`agent-step`**: one line per tool call, with four states, each an icon + word:
- queued: hollow circle, "Waiting"
- running: spinner, "Checking scene quality…"
- done: check, a one-line result plus its evidence ID
- skipped: dash, a reason ("No clear scene to compare")

Steps reveal one by one (`{motion.stagger}` apart, `{motion.base}` fade + 4px rise). With `prefers-reduced-motion`, they appear instantly.

**`evidence-card`**: an ID chip, a one-line finding, the source and date in `caption`, and an optional mini-visual (sparkline, weather bars, neighbour mini-map). The card has a 3px left rule coloured by what it supports *once the diagnosis exists*; before that, the rule is grey.

**`evidence-ref`**: the `E3` chip. Clicking it scrolls to and briefly outlines the evidence card. Every sentence in the diagnosis ends with at least one.

### Diagnosis
**`hypothesis-card`**: rank number, name, `confidence-meter` (three segments plus the word High / Medium / Low), and three short lists: **For**, **Against** and **Unknown**, each line citing evidence.

**`hypothesis-card-ruled-out`**: collapsed to one line, "Ruled out: Waterlogging, no heavy rain (E5)". It stays visible so the officer sees what was considered.

**Stage outcomes**: if Stage 1 or 2 ends the case, the diagnosis area shows one card in place of the differential, with the outcome ("Auto-dismissed", "Area alert") and its evidence.

**"Unexplained, visit"**: if no hypothesis clears the bar, the diagnosis says so in plain words, lists what was ruled out, and the next-check slip becomes a general visit checklist.

### Next best check (the hero)
**`next-check-slip`**: dark ink card. An eyebrow label "NEXT BEST CHECK", the instruction in `body-lg` ("Check the drip line on the east edge"), then two result lines, each "If … → …" ("If dry → irrigation failure", "If wet → inspect leaf undersides for thrips"). A cost line follows ("about 5 minutes on site"), and the primary action, "Open field checklist", comes last. Because the slip is dark, its button is inverted: white fill with ink text.

**`check-candidates-table`**: sits under the slip, collapsed by default ("Why this check?"). Columns: check, cost, "splits A vs B?", score. The winner row is sunken and marked with a check icon and the word "Chosen".

### Map & timeline
**`map-frame`**: Leaflet, with a muted satellite basemap. The field outline is 2px ink with a 1px white halo, so it reads on any imagery. Zones are outlined; the anomalous zone gets the ΔNDVI fill plus a selected outline in `{colors.overlay-zone-selected}`. A **"Show 10 m pixels"** toggle draws the Sentinel-2 grid in white at 35%, next to the `limits-note`. Cloudy areas get a grey hatch. Custom controls placed over the map need a z-index above Leaflet's panes (controls sit at 800–1000).

**`timeline-chart`**: one line per zone. The affected zone is ink, the others light grey, and the expected crop curve is a sunken band behind them. Usable scenes are solid dots, partial scenes half-filled, cloudy scenes hollow with no value line through them. A vertical marker shows the alert date, and management windows (e.g. a pruning window) appear as labelled shaded spans.

### Honesty components
**`limits-note`**: a small panel on every case, e.g. "Each pixel is 10 m × 10 m. This field is about 40 pixels. FieldDx can see zones, not individual vines or rows."

**`scenario-banner`**: shown on any case built from replayed or simulated data: "Replayed scenario: real imagery, simulated field outcome." It is not dismissible in demo builds.

### Forms
**`text-input`**: white, 1px strong border, `{rounded.sm}`, focus ring `{colors.focus}` 2px with a 2px offset. Labels sit above in `eyebrow`. Errors appear below in severity-high text with an icon.

## Accessibility
- Text contrast is at least 4.5:1 everywhere, including tertiary text and badges.
- Every status uses icon + word. Colour is a third channel, never the only one.
- Keyboard focus is always visible (2px `{colors.focus}` outline). Mouse clicks don't show the ring.
- The map has a text equivalent: the evidence cards state what the map shows ("Loss concentrated on the east edge, 9 of 40 pixels").
- Honour `prefers-reduced-motion` for the agent-step reveal and the re-ranking animation.

## Do's and Don'ts

### Do
- Keep the chrome ink, white and grey; let data, severity and the next-check slip carry colour.
- Show ΔNDVI on the map and raw NDVI only in the timeline.
- Put an evidence ID on every diagnostic sentence.
- Show dismissed cases and ruled-out hypotheses, muted but visible.
- State the date and source of every number.
- Write "unknown" when evidence is missing, and say what would resolve it.
- Keep the next-check slip the only dark surface on the screen.
- Make the field checklist work one-handed on a phone.

### Don't
- Don't use green for buttons or links. Green on this product means vegetation.
- Don't use a red-to-green NDVI ramp.
- Don't show a number for a cloudy or missing scene, and never show NDVI 0 as a stand-in.
- Don't let the LLM's prose appear without evidence chips.
- Don't stack shadows or round corners beyond `{rounded.md}` on working surfaces.
- Don't hide the 10 m resolution limit; it's part of why judges and officers trust the result.
- Don't present a replayed scenario as live data.

## Provenance
- This replaces an earlier draft that copied NerdWallet's brand language. Nothing here comes from NerdWallet.
- Several principles are carried over from the author's earlier project, Pragya: quality classes that never show a value for cloudy scenes, icon + text for every status, tabular numbers, visible focus, and the Leaflet z-index rule. Those are design ideas only. No code from Pragya is used in this repository; FieldDx code is written fresh, as the hackathon rules require.
