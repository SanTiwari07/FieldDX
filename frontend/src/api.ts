export type Quality = "usable" | "partial" | "cloudy" | "none" | "n/a";
export type Confidence = "high" | "medium" | "low";
export type Severity = "high" | "medium" | "low";
export type Outcome = "auto_dismissed" | "area_alert" | "field_case" | "unexplained" | "watch" | "resolved";
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
  kind: "auto_dismissed" | "area_alert" | "watch";
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
  klass: string;
  class_label: string;
  area_ha: number;
  analysis_pixels: number;
  mode?: "zoned" | "whole";
}

export interface CaseResult {
  case_id: string;
  field: FieldInfo;
  alert_date: string;
  as_of: string;
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
  /** why a dismissed case was thrown out: a harvest, another management event, a data artefact or boundary mixing */
  kind: DismissalKind | null;
  /** the field's highest monthly NDVI in the alert's month and the two before it */
  green_before: number | null;
}

export type DismissalKind = "harvest" | "management" | "artefact" | "boundary";

export interface MapZone {
  id: string;
  label: string;
  polygon: [number, number][][];
  pixels: number;
  delta: number | null;
  quality: Quality;
  affected: boolean;
}

export interface MapData {
  field_id: string;
  name: string;
  outline: [number, number][][];
  zones: MapZone[];
  bounds: [[number, number], [number, number]];
  scene_date: string | null;
  baseline: string;
  analysis_pixels: number;
}

export interface SeriesData {
  zones: { id: string; label: string; affected: boolean }[];
  scenes: { date: string; quality: Quality; zones: Record<string, { ndvi: number | null; quality: Quality }> }[];
  windows: { id: string; label: string; start: string; end: string; verified: boolean }[];
  alert_date: string;
  as_of: string;
  baseline: string;
}

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

/** Signed out, or no area yet: the app shell listens and moves the officer to the right step. */
export const SESSION_EVENT = "fielddx:session";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* keep status text */
    }
    if (res.status === 401 || (res.status === 409 && /area/i.test(detail))) {
      window.dispatchEvent(new CustomEvent(SESSION_EVENT, { detail: res.status }));
    }
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

const post = (url: string, body?: unknown) =>
  fetch(url, {
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

export const api = {
  me: () => fetch("/api/me").then((r) => json<Me>(r)),
  register: (body: { name: string; username: string; pin: string }) => post("/api/auth/register", body).then((r) => json<Me>(r)),
  login: (body: { username: string; pin: string }) => post("/api/auth/login", body).then((r) => json<Me>(r)),
  demo: () => post("/api/auth/demo").then((r) => json<Me>(r)),
  logout: () => post("/api/auth/logout").then((r) => json<{ ok: boolean }>(r)),
  places: (q: string) => fetch(`/api/places?q=${encodeURIComponent(q)}`).then((r) => json<{ places: Place[] }>(r)),
  fieldsSource: (country: string, subdivision: string) =>
    fetch(`/api/places/fields-source?country=${encodeURIComponent(country)}&subdivision=${encodeURIComponent(subdivision)}`)
      .then((r) => json<FieldsSource>(r)),
  overviewMap: (r: RegionRequest) => post("/api/overview/map", r).then((res) => json<OverviewMap>(res)),
  overviewSummary: (r: RegionRequest) => post("/api/overview/summary", r).then((res) => json<OverviewSummary>(res)),
  areas: () => fetch("/api/areas").then((r) => json<{ areas: AreaSummary[] }>(r)),
  createArea: (body: NewArea) => post("/api/areas", body).then((r) => json<Me>(r)),
  joinArea: (area_id: string | null) => post("/api/me/area", { area_id }).then((r) => json<Me>(r)),
  build: () => fetch("/api/area/build").then((r) => json<{ area: AreaSummary; build: BuildState }>(r)),
  retryBuild: () => post("/api/area/retry").then((r) => json<{ area: AreaSummary; build: BuildState }>(r)),
  home: () => fetch("/api/home").then((r) => json<HomeData>(r)),
  inbox: () => fetch("/api/cases").then((r) => json<{ banner: string; as_of: string; area: string; provenance: Provenance; cases: InboxRow[] }>(r)),
  fieldsGeoJson: () => fetch("/api/fields.geojson").then((r) => json<FieldsGeoJson>(r)),
  editFields: (edit: FieldEdit) => post("/api/area/fields", edit).then((r) => json<FieldEditResult>(r)),
  getCase: (id: string) => fetch(`/api/cases/${id}`).then((r) => json<CaseResult>(r)),
  map: (id: string) => fetch(`/api/cases/${id}/map`).then((r) => json<MapData>(r)),
  series: (id: string) => fetch(`/api/cases/${id}/series`).then((r) => json<SeriesData>(r)),
  close: (id: string, body: { check_id: string; outcome: string; note: string }) =>
    fetch(`/api/cases/${id}/close`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => json<CaseResult>(r)),
  reset: () => post("/api/admin/reset").then((r) => json<{ ok: boolean }>(r)),
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


export interface Provenance {
  boundaries?: string;
  imagery?: string;
  landcover?: string;
}

export interface FieldsGeoJson {
  type: "FeatureCollection";
  area?: { geometry: GeoPolygon | null; bbox: number[] | null };
  features: {
    type: "Feature";
    geometry: { type: "Polygon"; coordinates: [number, number][][] };
    properties: {
      id: string; name: string; class: string; area_ha: number; mode: "zoned" | "whole";
      case_outcome: Outcome | null; case_reason: DismissalKind | null;
      key: string | null; ndvi_month: string | null; ndvi: number | null;
    };
  }[];
  provenance?: Provenance;
  /** every other field shape in the area and why it is not watched, and the land where no shape was found */
  others?: OtherShape[];
  /** the signed-in officer can correct the shapes in this area */
  editable?: boolean;
}

export type ShapeStatus = "small" | "tiny_core" | "cropland" | "edge" | "large" | "over_limit" | "gap";

export interface OtherShape {
  type: "Feature";
  geometry: GeoPolygon;
  properties: { key: string; source: string; area_ha: number; status: ShapeStatus; field_id: null };
}

export type FieldEdit =
  | { op: "add"; geometry: { type: "Polygon"; coordinates: number[][][] } }
  | { op: "split"; key: string; line: number[][] }
  | { op: "merge"; keys: string[] }
  | { op: "remove"; key: string };

export interface FieldEditResult {
  ok: boolean;
  message: string;
  added: { key: string; status: string; field_id: string | null; area_ha: number }[];
  removed: string[];
  removed_fields: string[];
}

export type GeoPolygon = { type: "Polygon"; coordinates: number[][][] } | { type: "MultiPolygon"; coordinates: number[][][][] };

export interface Officer {
  name: string;
  username: string;
  demo: boolean;
}

export type BuildStatus = "ready" | "queued" | "building" | "failed" | "interrupted";

export interface AreaSummary {
  id: string;
  name: string;
  region: string;
  bbox: number[];
  center: [number, number];
  mode?: "draw" | "coords" | "pick";
  field_source?: "ftw_global" | "ftw_model";
  km2?: number;
  status: BuildStatus;
  geometry: GeoPolygon | null;
  boundary: GeoPolygon | null;
  fields?: number;
  as_of?: string;
  created_at?: string;
  built_at?: string;
}

export interface Me {
  officer: Officer;
  area: AreaSummary | null;
}

export interface Place {
  id: string;
  name: string;
  kind: string;
  context: string;
  center: [number, number];
  bounds: [[number, number], [number, number]];
  boundary: GeoPolygon | null;
  country: string;
  subdivision: string;
}

export interface Partition {
  code: string;
  country: string;
  parquet: string;
  pmtiles: string;
  layers: string[];
}

export interface FieldsSource {
  partition: Partition | null;
  model_available: boolean;
  max_km2: number;
}

export interface NewArea {
  name: string;
  region: string;
  geometry: GeoPolygon;
  mode: "draw" | "coords" | "pick";
  field_source: "ftw_global" | "ftw_model";
  boundary: GeoPolygon | null;
  partition: { code: string } | null;
  picked_points?: [number, number][];
}

export interface RegionRequest {
  name: string;
  bounds: [[number, number], [number, number]];
  boundary: GeoPolygon | null;
}

export interface OverviewWindows {
  recent: [string, string];
  baseline: [string, string];
}

export interface OverviewMap {
  key: string;
  tiles: string;
  windows: OverviewWindows;
}

export interface Hotspot {
  bounds: [[number, number], [number, number]];
  center: [number, number];
  drop: number;
  gain: number;
  seen: number;
  cropland_km2: number;
  near: string;
}

export interface OverviewSummary {
  key: string;
  name: string;
  windows: OverviewWindows;
  cropland_km2: number;
  seen: number;
  drop: number | null;
  gain: number | null;
  cell_km: number;
  hotspots: Hotspot[];
  source: string;
}

export interface BuildStep {
  id: string;
  label: string;
  state: "queued" | "running" | "done" | "failed";
  detail: string;
  progress: number | null;
  started_at?: string;
  ended_at?: string;
}

export interface BuildState {
  status: BuildStatus;
  steps?: BuildStep[];
  error?: string | null;
  retryable?: boolean;
  started_at?: string;
  ended_at?: string;
  queue_position?: number | null;
}

export interface HomeData {
  area: AreaSummary;
  officer: { name: string };
  as_of: string;
  last_pass: string | null;
  fields: number;
  alerts: number;
  counts: { visit: number; watch: number; area_alert: number; dismissed: number; harvest: number; resolved: number };
  top: InboxRow[];
  detector: string;
  provenance: Provenance;
}
