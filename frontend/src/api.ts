export type Quality = "usable" | "partial" | "cloudy" | "none" | "n/a";
export type Confidence = "high" | "medium" | "low";
export type Severity = "high" | "medium" | "low";
export type Outcome = "auto_dismissed" | "area_alert" | "field_case" | "unexplained" | "resolved";
export type Stance = "for" | "against" | "neutral";

export interface Evidence {
  id: string;
  tool: string;
  title: string;
  finding: string;
  data: Record<string, any>;
  as_of: string;
  quality: Quality;
  source: string;
  visual: any | null;
  stance: Stance;
}

export interface Line {
  text: string;
  evidence_ids: string[];
}

export interface Hypothesis {
  id: string;
  name: string;
  stage: 1 | 2 | 3;
  score: number;
  confidence: Confidence;
  status: "leading" | "possible" | "ruled_out" | "fired";
  for_lines: Line[];
  against_lines: Line[];
  unknown_lines: Line[];
  brief: string;
}

export interface StageOutcome {
  kind: "auto_dismissed" | "area_alert";
  hypothesis_id: string;
  title: string;
  reason: string;
  evidence_ids: string[];
  confirm_with: string | null;
}

export interface CheckOutcome {
  key: string;
  label: string;
  then: string;
  supports: string[];
  against: string[];
}

export interface Candidate {
  check_id: string;
  short: string;
  label: string;
  cost_min: number;
  split: number;
  score: number;
  chosen: boolean;
  note: string;
}

export interface NextCheck {
  check_id: string;
  label: string;
  cost_min: number;
  outcomes: CheckOutcome[];
  hypotheses: string[];
  candidates: Candidate[];
}

export interface CaseFile {
  summary: Line;
  hypotheses: { id: string; why: Line[] }[];
  next_check_explainer: Line | null;
  limits: string;
}

export interface Headline {
  delta: number;
  zone: string;
  zone_label: string;
  date: string;
  quality: Quality;
  baseline_label: string;
}

export interface Resolution {
  check_id: string;
  check_label: string;
  outcome_key: string;
  outcome_label: string;
  note: string;
  closed_at: string;
  confirmed_id: string;
  confirmed_name: string;
  ranking_before: string[];
  ranking_after: string[];
}

export interface FieldInfo {
  id: string;
  name: string;
  village: string;
  crop: string;
  area_ha: number;
  analysis_pixels: number;
  anchor_date: string;
  anchor_label: string;
  anchor_assumed: boolean;
}

export interface CaseResult {
  case_id: string;
  field: FieldInfo;
  alert_date: string;
  as_of: string;
  replayed: boolean;
  scenario_label: string;
  banner: string;
  outcome: Outcome;
  severity: Severity | null;
  headline: Headline | null;
  evidence: Evidence[];
  hypotheses: Hypothesis[];
  stage_outcome: StageOutcome | null;
  next_check: NextCheck | null;
  visit_checklist: string[];
  narrative: CaseFile | null;
  narrative_source: "gemini" | "template" | null;
  resolution: Resolution | null;
  limits: string;
}

export interface InboxRow {
  id: string;
  field: FieldInfo;
  outcome: Outcome;
  severity: Severity | null;
  headline: Headline | null;
  leading: string;
  confidence: Confidence | null;
  reason: string | null;
  stage_title: string | null;
  alert_date: string;
  replayed: boolean;
}

export interface MapZone {
  id: string;
  label: string;
  polygon: [number, number][];
  pixels: number;
  delta: number | null;
  quality: Quality;
  affected: boolean;
}

export interface MapData {
  field_id: string;
  name: string;
  outline: [number, number][];
  zones: MapZone[];
  grid: [[number, number], [number, number]][];
  bounds: [[number, number], [number, number]];
  scene_date: string | null;
  baseline: string;
  size_m: [number, number];
  analysis_pixels: number;
}

export interface SeriesData {
  zones: { id: string; label: string; affected: boolean }[];
  scenes: { date: string; quality: Quality; zones: Record<string, { ndvi: number | null; quality: Quality }> }[];
  expected: { date: string; value: number }[];
  windows: { id: string; label: string; start: string; end: string; verified: boolean }[];
  alert_date: string;
  as_of: string;
  baseline: string;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  inbox: () => fetch("/api/cases").then((r) => json<{ banner: string; as_of: string; cases: InboxRow[] }>(r)),
  getCase: (id: string) => fetch(`/api/cases/${id}`).then((r) => json<CaseResult>(r)),
  map: (id: string) => fetch(`/api/cases/${id}/map`).then((r) => json<MapData>(r)),
  series: (id: string) => fetch(`/api/cases/${id}/series`).then((r) => json<SeriesData>(r)),
  close: (id: string, body: { check_id: string; outcome: string; note: string }) =>
    fetch(`/api/cases/${id}/close`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => json<CaseResult>(r)),
  reset: () => fetch("/api/admin/reset", { method: "POST" }).then((r) => json<{ ok: boolean }>(r)),
  raster: (id: string, scene?: string) =>
    fetch(`/api/cases/${id}/raster${scene ? `?scene=${scene}` : ""}`).then((r) => json<RasterData>(r)),
};

export interface RasterData {
  date: string;
  w: number;
  h: number;
  pixel_m: number;
  bounds: [[number, number], [number, number]];
  quality: Quality;
  visible: number;
  ndvi: (number | null)[][];
  delta: (number | null)[][];
  mask: number[][];
  stats: { mean: number; p10: number; p90: number } | null;
  zones: string[][];
}

