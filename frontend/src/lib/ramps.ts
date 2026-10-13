/**
 * Map colour scales.
 *
 * NDVI: the discrete 0.05-step scale and the interpretation bins are carried over from the author's
 * earlier project (Pragya), which follows the EOS NDVI colormap convention: each colour applies from
 * its threshold up to the next one. Change: FieldDx's own brown-to-teal ramp for change against the
 * field's baseline (see DESIGN.md).
 */

export type Stop = [number, string];

export const NDVI_STOPS: Stop[] = [
  [-1.0, "#ad0028"], [0.05, "#c5142a"], [0.1, "#e02d2c"], [0.15, "#ef4c3a"], [0.2, "#fe6c4a"],
  [0.25, "#ff8d5a"], [0.3, "#ffab69"], [0.35, "#ffc67d"], [0.4, "#ffe093"], [0.45, "#ffefab"],
  [0.5, "#fdfec2"], [0.55, "#eaf7ac"], [0.6, "#d5ef94"], [0.65, "#b9e383"], [0.7, "#9bd873"],
  [0.75, "#77ca6f"], [0.8, "#53bd6b"], [0.85, "#14aa60"], [0.9, "#009755"], [0.95, "#007e47"],
];

export const NDVI_BINS = [
  { min: 0.6, max: null as number | null, label: "Dense, healthy vegetation", color: "#77ca6f" },
  { min: 0.4, max: 0.6, label: "Moderate vegetation", color: "#ffe093" },
  { min: 0.2, max: 0.4, label: "Sparse or stressed vegetation", color: "#fe6c4a" },
  { min: 0.0, max: 0.2, label: "Bare soil", color: "#e02d2c" },
];

export const DELTA_STOPS: Stop[] = [
  [-9, "#7a3410"], [-0.15, "#b8662a"], [-0.1, "#e7b98a"], [-0.05, "#f2f1ee"],
  [0.05, "#a9d4cf"], [0.1, "#4e9a93"], [0.15, "#145e59"],
];

function pick(stops: Stop[], v: number): string {
  let color = stops[0][1];
  for (const [t, c] of stops) {
    if (v >= t) color = c;
    else break;
  }
  return color;
}

export const ndviColor = (v: number) => pick(NDVI_STOPS, v);
export const deltaColorOf = (v: number) => {
  // bins are (min, max]; a change of exactly -0.05 sits in the loss bin
  return pick(DELTA_STOPS, v + 1e-9);
};

export type Mode = "ndvi" | "change" | "satellite";

export const MODE_LABEL: Record<Mode, string> = { ndvi: "NDVI", change: "Change", satellite: "Satellite" };

/** Legend gradient and end labels for a mode. */
export function legendFor(mode: Mode) {
  if (mode === "change") {
    return {
      gradient: `linear-gradient(90deg, ${DELTA_STOPS.map(([, c]) => c).join(", ")})`,
      min: "≤ −0.15", mid: "0", max: "≥ +0.15",
      low: "Loss", high: "Gain",
    };
  }
  return {
    gradient: `linear-gradient(90deg, ${NDVI_STOPS.map(([, c]) => c).join(", ")})`,
    min: "0.0", mid: "0.5", max: "1.0", low: "Bare", high: "Dense",
  };
}

export const MASK_FILL = "#e5e7eb";
