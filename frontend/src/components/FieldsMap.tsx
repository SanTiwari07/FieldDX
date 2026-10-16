import { useCallback, useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Polygon, Polyline, Popup, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { useNavigate } from "react-router-dom";
import "leaflet/dist/leaflet.css";
import { Check, CornerUpLeft, Merge, PenLine, Scissors, Trash2, X } from "lucide-react";
import { api, FieldEdit, FieldsGeoJson, GeoPolygon, OtherShape, Outcome, ShapeStatus } from "../api";
import { useSession } from "../session";

type LatLng = [number, number];
type Style = { color: string; fill: string; label: string };

const STYLE: Record<string, Style> = {
  field_case: { color: "#101c16", fill: "#101c16", label: "Needs a visit" },
  unexplained: { color: "#101c16", fill: "#101c16", label: "Ask or visit" },
  watch: { color: "#8a5a00", fill: "#e09a0d", label: "Watching" },
  area_alert: { color: "#1769aa", fill: "#1769aa", label: "Area alert" },
  resolved: { color: "#065f2c", fill: "#065f2c", label: "Resolved" },
  harvest: { color: "#6b4d16", fill: "#d9b26a", label: "Harvest (expected)" },
  auto_dismissed: { color: "#737b82", fill: "#9aa0a6", label: "Dismissed" },
  none: { color: "#ffffff", fill: "#ffffff", label: "Watched, no alert" },
};

/** Shapes that are on the map but not watched, and why: said in words a field officer can act on. */
const OTHER: Record<ShapeStatus, { label: string; why: (ha: number) => string }> = {
  small: {
    label: "Too small to read",
    why: (ha) => `${ha} ha holds too few 10 m satellite pixels (under 20, most of them mixed with the land around), so its health is not read. If it belongs with its neighbour, merge them.`,
  },
  tiny_core: {
    label: "Too thin to read",
    why: () => "The shape is too thin to hold 10 clear 10 m pixels inside its boundary, so its health is not read. If it belongs with its neighbour, merge them.",
  },
  cropland: {
    label: "Not cropland",
    why: () => "Less than 60% of it is cropland on the ESA WorldCover map (trees, houses, water or bare ground), so it is not watched.",
  },
  edge: { label: "At the imagery edge", why: () => "Too close to the edge of the downloaded imagery to read reliably." },
  large: { label: "Too large", why: () => "Over 12 ha: probably several fields merged into one shape. Split it." },
  over_limit: { label: "Over the limit", why: () => "An area keeps up to 400 fields; this one is beyond that." },
  gap: {
    label: "No field found",
    why: (ha) => `No field shape on these ${ha} ha. It may be a road, houses, trees or water, or a field the model missed. If it is a field, draw it.`,
  },
};

const WORLD: LatLng[] = [[-89, -179.9], [-89, 179.9], [89, 179.9], [89, -179.9]];
// Above this many unwatched shapes (a district-sized area) they are drawn on one canvas, not as SVG paths.
// The canvas cannot hatch, so the land with no field shape gets a plain tint there.
const CANVAS_FROM = 2000;
const toLL = (ring: number[][]) => ring.map(([lng, lat]) => [lat, lng] as LatLng);
const rings = (g: GeoPolygon): LatLng[][][] =>
  g.type === "Polygon" ? [g.coordinates.map(toLL)] : g.coordinates.map((p) => p.map(toLL));

type Tool = "add" | "split" | "merge" | "remove";
const TOOLS: { id: Tool; label: string; Icon: typeof PenLine }[] = [
  { id: "add", label: "Draw a field", Icon: PenLine },
  { id: "split", label: "Split", Icon: Scissors },
  { id: "merge", label: "Merge", Icon: Merge },
  { id: "remove", label: "Not a field", Icon: Trash2 },
];

/** Fit the area, and fit it again when the map's box changes size (it often has none when it first
 * mounts), until the officer moves the map themselves. */
function Fit({ pts }: { pts: LatLng[] }) {
  const map = useMap();
  const key = pts.length ? `${pts[0]}|${pts.length}` : "";
  useEffect(() => {
    if (!pts.length) return;
    let moved = false;
    let fitting = false;
    const fit = () => { fitting = true; map.fitBounds(pts, { padding: [16, 16], animate: false }); fitting = false; };
    const stop = () => { if (!fitting) moved = true; };
    fit();
    map.on("dragstart zoomstart", stop);
    const ro = new ResizeObserver(() => { map.invalidateSize(); if (!moved) fit(); });
    ro.observe(map.getContainer());
    return () => { ro.disconnect(); map.off("dragstart zoomstart", stop); };
  }, [map, key]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

/** Clicks on the map while drawing. A click within 12 screen pixels of `first` closes the shape. */
function Clicks({ on, first, onAdd, onClose }: { on: boolean; first: LatLng | null; onAdd: (p: LatLng) => void; onClose: () => void }) {
  const map = useMapEvents({
    click: (e) => {
      if (!on) return;
      if (first && map.latLngToContainerPoint(first).distanceTo(e.containerPoint) < 12) onClose();
      else onAdd([e.latlng.lat, e.latlng.lng]);
    },
  });
  useEffect(() => { map.getContainer().classList.toggle("is-drawing", on); }, [map, on]);
  return null;
}

function useZoom() {
  const map = useMap();
  const [zoom, setZoom] = useState(map.getZoom());
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) });
  return zoom;
}

/** At low zoom the shapes are specks: a dot per field that needs attention, so none is missed.
 * Dismissed fields (harvest included) get none: in harvest season they would bury the few that matter. */
function Dots({ gj, nav }: { gj: FieldsGeoJson; nav: (to: string) => void }) {
  const zoom = useZoom();
  if (zoom >= 15) return null;
  return (
    <>
      {gj.features.filter((f) => f.properties.case_outcome && f.properties.case_outcome !== "auto_dismissed").map((f) => {
        const p = f.properties;
        const ring = f.geometry.coordinates[0];
        const lat = ring.reduce((a, c) => a + c[1], 0) / ring.length;
        const lng = ring.reduce((a, c) => a + c[0], 0) / ring.length;
        const st = STYLE[p.case_outcome ?? "none"];
        return (
          <CircleMarker key={p.id} center={[lat, lng]} radius={6}
            pathOptions={{ color: "#ffffff", weight: 2, fillColor: st.fill, fillOpacity: 0.95 }}
            eventHandlers={{ click: () => nav(`/case/${p.id}`) }}>
            <Tooltip sticky><strong>{p.name}</strong><br />{st.label}. Click to open.</Tooltip>
          </CircleMarker>
        );
      })}
    </>
  );
}

const instructions = (tool: Tool, picked: number, pts: number): string => {
  if (tool === "add") return pts < 3 ? "Click the corners of the field on the imagery. Three or more." : "Click the first corner, or Save, to finish the field.";
  if (tool === "split") return picked ? (pts < 2 ? "Now click points for a line right across the field, where it should be cut." : "Save to cut the field along the line.") : "Click the field to split.";
  if (tool === "merge") return picked < 2 ? "Click the shapes that belong to one field. They must touch." : `Save to merge ${picked} shapes into one field.`;
  return picked ? "Save to mark this shape as not a field." : "Click the shape that is not a field (a road, a house, a threshing yard).";
};

/**
 * Every field shape in the officer's area on satellite imagery. Watched fields are coloured by what the
 * investigation concluded; shapes too small or not cropland are outlined and say why; land where no field
 * shape was found is hatched. Everything is clickable. The area boundary is a solid line, and the land
 * outside it is dimmed. Where the officer may, the shapes can be corrected: draw a missed field, split,
 * merge, or remove one, and only that field is read again from the satellite passes.
 */
export default function FieldsMap({ fieldId }: { fieldId?: string }) {
  const [gj, setGj] = useState<FieldsGeoJson | null>(null);
  const [tool, setTool] = useState<Tool | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [pts, setPts] = useState<LatLng[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const nav = useNavigate();
  const { refresh } = useSession();
  const canvas = useMemo(() => L.canvas({ padding: 0.5 }), []);

  const load = useCallback(() => api.fieldsGeoJson().then(setGj).catch(() => undefined), []);
  useEffect(() => { load(); }, [load]);

  const outline = useMemo(() => (gj?.area?.geometry ? rings(gj.area.geometry).map((r) => r[0]) : []), [gj]);
  const fitPts = useMemo(
    () => (outline.length ? outline.flat() : (gj?.features ?? []).flatMap((f) => toLL(f.geometry.coordinates[0]))),
    [gj, outline],
  );

  const reset = () => { setPicked([]); setPts([]); };
  const choose = (t: Tool | null) => { setTool(t); reset(); setNote(null); };
  useEffect(() => {
    if (!tool) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") choose(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [tool]);

  if (!gj) return <div className="fieldsmap skeleton" aria-busy="true" />;

  const others = gj.others ?? [];
  const gaps = others.filter((o) => o.properties.status === "gap");
  const shapesOut = others.filter((o) => o.properties.status !== "gap");
  const big = others.length > CANVAS_FROM;
  const drawing = tool === "add" || (tool === "split" && picked.length === 1);
  const selecting = !!tool && !drawing;

  const pick = (key: string | null) => {
    if (!key || !selecting) return;
    if (tool === "merge") setPicked((p) => (p.includes(key) ? p.filter((k) => k !== key) : [...p, key]));
    else setPicked([key]);
  };

  const addPoint = (p: LatLng) => setPts((x) => [...x, p]);

  const ready = (tool === "add" && pts.length >= 3) || (tool === "split" && picked.length === 1 && pts.length >= 2)
    || (tool === "merge" && picked.length >= 2) || (tool === "remove" && picked.length === 1);

  async function save() {
    if (!tool) return;
    const lnglat = (p: LatLng) => [p[1], p[0]];
    let edit: FieldEdit;
    if (tool === "add") {
      const ring = pts.map(lnglat);
      edit = { op: "add", geometry: { type: "Polygon", coordinates: [[...ring, ring[0]]] } };
    } else if (tool === "split") edit = { op: "split", key: picked[0], line: pts.map(lnglat) };
    else if (tool === "merge") edit = { op: "merge", keys: picked };
    else edit = { op: "remove", key: picked[0] };
    setBusy(true);
    setNote(null);
    try {
      const r = await api.editFields(edit);
      setNote({ ok: true, text: r.message });
      reset();
      await Promise.all([load(), refresh()]);
    } catch (e) {
      setNote({ ok: false, text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }

  // ---- legend counts
  const counts = new Map<string, number>();
  const bump = (k: string) => counts.set(k, (counts.get(k) ?? 0) + 1);
  gj.features.forEach((f) => bump(f.properties.case_reason === "harvest" ? "harvest" : f.properties.case_outcome ?? "none"));
  shapesOut.forEach((o) => bump(`o:${o.properties.status}`));
  const gapHa = gaps.reduce((a, g) => a + g.properties.area_ha, 0);

  // what the officer marks is white and ink, as on the setup map (docs/DESIGN.md): a picked shape is ink at 50%
  const selStyle = { color: "#ffffff", weight: 3.5, opacity: 1, dashArray: undefined, fillColor: "#101c16", fillOpacity: 0.5 };
  const interactiveKey = `${tool ?? "view"}-${drawing ? "d" : "s"}`;

  const otherPopup = (o: OtherShape) => (
    <Popup>
      <div className="fm-pop">
        <strong>{OTHER[o.properties.status].label}</strong>
        <p>{OTHER[o.properties.status].why(o.properties.area_ha)}</p>
        {o.properties.source && <small>Shape: {o.properties.source}</small>}
        {gj.editable && (
          <small className="fm-pop-hint">To fix it, use Correct fields above the map.</small>
        )}
      </div>
    </Popup>
  );

  return (
    <figure className="fieldsmap-wrap">
      {gj.editable && (
        <div className="fm-tools" role="toolbar" aria-label="Correct the field shapes">
          {!tool ? (
            <>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => choose("add")}><PenLine size={14} aria-hidden /> Correct fields</button>
              <span className="muted small">Draw a field the satellite map missed, split or merge shapes, or remove one. Only that field is read again.</span>
            </>
          ) : (
            <>
              <div className="seg" role="group" aria-label="Correction">
                {TOOLS.map(({ id, label, Icon }) => (
                  <button key={id} type="button" className={tool === id ? "on" : ""} aria-pressed={tool === id} aria-label={label} onClick={() => choose(id)} disabled={busy}>
                    <Icon size={14} aria-hidden /><span>{label}</span>
                  </button>
                ))}
              </div>
              <span className="fm-instr" aria-live="polite">{busy ? "Reading the field from the satellite passes already downloaded. This takes up to a minute." : instructions(tool, picked.length, pts.length)}</span>
              <span className="fm-actions">
                {(pts.length > 0 || picked.length > 0) && (
                  <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => (pts.length ? setPts((x) => x.slice(0, -1)) : setPicked((p) => p.slice(0, -1)))}>
                    <CornerUpLeft size={14} aria-hidden /> Undo
                  </button>
                )}
                <button type="button" className="btn btn-primary btn-sm" disabled={!ready || busy} onClick={save}>
                  {busy ? <span className="spinner" aria-hidden /> : <Check size={14} aria-hidden />} Save
                </button>
                <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => choose(null)}><X size={14} aria-hidden /> Done</button>
              </span>
            </>
          )}
        </div>
      )}
      {note && <p className={note.ok ? "fm-note" : "fm-note is-error"} role={note.ok ? "status" : "alert"}>{note.text}</p>}

      <div className={`fieldsmap ${busy ? "is-busy" : ""}`}>
        {/* the hatch for land where no field shape was found; referenced by fill="url(#fm-gap)" */}
        <svg width="0" height="0" aria-hidden style={{ position: "absolute" }}>
          <defs>
            <pattern id="fm-gap" patternUnits="userSpaceOnUse" width="7" height="7" patternTransform="rotate(45)">
              <rect width="7" height="7" fill="rgba(56, 217, 245, 0.08)" />
              <line x1="0" y1="0" x2="0" y2="7" stroke="#38d9f5" strokeWidth="1.4" strokeOpacity="0.7" />
            </pattern>
          </defs>
        </svg>
        <MapContainer center={fitPts[0] ?? [20.5, 78.9]} zoom={13} zoomSnap={0.25} scrollWheelZoom className="map" aria-label="Map of every field shape in your area: watched fields coloured by case outcome, shapes not watched, and land with no field found">
          <TileLayer attribution="Imagery &copy; Esri, Maxar, Earthstar Geographics"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" maxNativeZoom={18} maxZoom={20} />
          <Fit pts={fitPts} />
          <Clicks on={drawing && !busy} first={tool === "add" && pts.length >= 3 ? pts[0] : null} onAdd={addPoint} onClose={save} />

          {/* outside the area: dimmed, so the officer's land stands out */}
          {outline.length > 0 && (
            <Polygon positions={[WORLD, ...outline]} interactive={false}
              pathOptions={{ stroke: false, fillColor: "#05090a", fillOpacity: 0.55 }} />
          )}

          {gaps.map((o) => (
            <Polygon key={`${o.properties.key}-${interactiveKey}`} positions={rings(o.geometry)} interactive={!drawing}
              pathOptions={big ? { renderer: canvas, color: "#38d9f5", weight: 1, opacity: 0.9, fillColor: "#38d9f5", fillOpacity: 0.16 }
                : { color: "#38d9f5", weight: 1, opacity: 0.9, fillColor: "url(#fm-gap)", fillOpacity: 1 }}>
              {!tool && otherPopup(o)}
            </Polygon>
          ))}

          {shapesOut.map((o) => {
            const k = o.properties.key;
            const sel = picked.includes(k);
            const crop = o.properties.status === "cropland";
            return (
              <Polygon key={`${k}-${interactiveKey}`} positions={rings(o.geometry)} interactive={!drawing}
                pathOptions={{
                  ...(big ? { renderer: canvas } : {}),
                  ...(sel ? selStyle
                    : { color: crop ? "#c3c8cc" : "#ffffff", weight: 1.2, opacity: 0.95, dashArray: crop ? "1 4" : "4 3",
                        fillColor: "#ffffff", fillOpacity: crop ? 0.02 : 0.06 }),
                }}
                eventHandlers={{ click: () => pick(k) }}>
                {!tool && otherPopup(o)}
              </Polygon>
            );
          })}

          {gj.features.map((f) => {
            const p = f.properties;
            const kind = p.case_reason === "harvest" ? "harvest" : (p.case_outcome ?? "none") as Outcome | "none";
            const st = STYLE[kind];
            const has = p.case_outcome !== null;
            const sel = !!p.key && picked.includes(p.key);
            return (
              <Polygon key={`${p.id}-${interactiveKey}`} positions={toLL(f.geometry.coordinates[0])} interactive={!drawing}
                pathOptions={sel ? selStyle
                  : { color: st.color, weight: p.id === fieldId ? 4 : has ? 2.5 : 1.6, fillColor: st.fill, fillOpacity: has ? 0.5 : 0.14, opacity: 0.95 }}
                eventHandlers={{ click: () => { if (selecting) pick(p.key); else if (!tool && has) nav(`/case/${p.id}`); } }}>
                {!tool && !has && (
                  <Popup>
                    <div className="fm-pop">
                      <strong>{p.name}</strong>
                      <p>{p.area_ha} ha, {p.class === "perennial" ? "perennial canopy" : p.class === "seasonal" ? "seasonal crop" : "crop not identified"}, read {p.mode === "whole" ? "as one zone" : "in eight zones"}.</p>
                      <p>No alert in the last 21 days.{p.ndvi !== null && p.ndvi_month ? ` NDVI ${p.ndvi.toFixed(2)} in ${new Date(`${p.ndvi_month}-01`).toLocaleString("en-IN", { month: "short", year: "numeric" })}.` : ""}</p>
                    </div>
                  </Popup>
                )}
                {!tool && (
                  <Tooltip sticky>
                    <strong>{p.name}</strong><br />{p.area_ha} ha, {p.class}<br />{st.label}{has ? ". Click to open." : ""}
                  </Tooltip>
                )}
              </Polygon>
            );
          })}

          {/* the area boundary: a dark halo under a solid white line reads on any imagery */}
          {outline.map((r, i) => (
            <Polygon key={`halo-${i}`} positions={r} interactive={false} pathOptions={{ color: "#05090a", weight: 7, opacity: 0.75, fill: false }} />
          ))}
          {outline.map((r, i) => (
            <Polygon key={`edge-${i}`} positions={r} interactive={false} pathOptions={{ color: "#ffffff", weight: 3, opacity: 1, fill: false }} />
          ))}

          {/* what the officer is drawing */}
          {pts.length > 0 && (tool === "add" && pts.length >= 3
            ? <Polygon positions={pts} interactive={false} pathOptions={{ color: "#ffffff", weight: 3, fillColor: "#101c16", fillOpacity: 0.18 }} />
            : <Polyline positions={pts} interactive={false} pathOptions={{ color: "#ffffff", weight: 3, dashArray: tool === "split" ? undefined : "4 6" }} />)}
          {pts.map((p, i) => (
            <CircleMarker key={`pt-${i}`} center={p} radius={i === 0 && tool === "add" && pts.length >= 3 ? 8 : 5} interactive={false}
              pathOptions={{ color: "#101c16", weight: 2, fillColor: "#ffffff", fillOpacity: 1 }} />
          ))}

          {!tool && <Dots gj={gj} nav={nav} />}
        </MapContainer>
      </div>

      <figcaption className="fieldsmap-legend">
        {Object.keys(STYLE).filter((k) => counts.get(k)).map((k) => (
          <span key={k}><i style={{ background: STYLE[k].fill, borderColor: STYLE[k].color, opacity: k === "none" ? 0.6 : 0.9 }} /> {STYLE[k].label} <b>{counts.get(k)}</b></span>
        ))}
        {(Object.keys(OTHER) as ShapeStatus[]).filter((k) => k !== "gap" && counts.get(`o:${k}`)).map((k) => (
          <span key={k}><i className={k === "cropland" ? "lg-dotted" : "lg-dashed"} /> {OTHER[k].label} <b>{counts.get(`o:${k}`)}</b></span>
        ))}
        {gaps.length > 0 && <span><i className="lg-hatch" /> No field found <b>{gapHa.toFixed(0)} ha</b></span>}
        <span className="lg-edge"><i /> Your area</span>
        <span className="muted">Click any shape to see what it is. Shapes: {gj.provenance?.boundaries?.split(" (")[0] ?? "Fields of the World"}. Imagery: Esri.</span>
      </figcaption>
    </figure>
  );
}
