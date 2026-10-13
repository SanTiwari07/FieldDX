import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, Pane, Polygon, Polyline, TileLayer, Tooltip, ZoomControl, useMap, useMapEvents } from "react-leaflet";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import { Columns2, Grid3x3, Layers } from "lucide-react";
import { api, MapData, RasterData, SeriesData } from "../api";
import { fmtDate, fmtDelta } from "../lib/format";
import { MODE_LABEL, Mode } from "../lib/ramps";
import { Legend } from "./Legend";
import { Hover, RasterOverlay } from "./RasterOverlay";
import { SceneBar } from "./SceneBar";

const cache = new Map<string, RasterData>();

function useRaster(caseId: string, date: string | null) {
  const [data, setData] = useState<RasterData | null>(null);
  useEffect(() => {
    if (!date) return setData(null);
    const key = `${caseId}:${date}`;
    const hit = cache.get(key);
    if (hit) return setData(hit);
    let live = true;
    api.raster(caseId, date).then((r) => {
      cache.set(key, r);
      if (live) setData(r);
    }).catch(() => live && setData(null));
    return () => { live = false; };
  }, [caseId, date]);
  return data;
}

/** Keeps the field framed on load and on resize, until the person moves the map themselves. */
function Fit({ bounds }: { bounds: MapData["bounds"] }) {
  const map = useMap();
  useEffect(() => {
    let touched = false, fitting = false;
    const fit = () => {
      fitting = true;
      map.invalidateSize();
      map.fitBounds(bounds, { paddingTopLeft: [28, 64], paddingBottomRight: [28, 84], maxZoom: 19, animate: false });
      fitting = false;
    };
    fit();
    const ro = new ResizeObserver(() => { if (!touched) fit(); });
    ro.observe(map.getContainer());
    const stop = () => { if (!fitting) touched = true; };
    map.on("dragstart zoomstart", stop);
    return () => { ro.disconnect(); map.off("dragstart zoomstart", stop); };
  }, [map, bounds]);
  return null;
}

/** Two maps panned and zoomed together. */
function Sync({ id, registry }: { id: string; registry: React.MutableRefObject<Record<string, LeafletMap>> }) {
  const map = useMap();
  const lock = useRef(false);
  useEffect(() => {
    registry.current[id] = map;
    return () => { delete registry.current[id]; };
  }, [map, id, registry]);
  useMapEvents({
    move() {
      if (lock.current) return;
      for (const [k, other] of Object.entries(registry.current)) {
        if (k === id) continue;
        lock.current = true;
        other.setView(map.getCenter(), map.getZoom(), { animate: false });
        lock.current = false;
      }
    },
  });
  return null;
}

function zoneMeans(r: RasterData | null) {
  const out: Record<string, { ndvi: number; delta: number } | undefined> = {};
  if (!r) return out;
  const acc: Record<string, { n: number; v: number; d: number }> = {};
  for (let y = 0; y < r.h; y++)
    for (let x = 0; x < r.w; x++) {
      const v = r.ndvi[y][x], d = r.delta[y][x];
      if (v === null || d === null) continue;
      const z = r.zones[y][x];
      const a = (acc[z] ??= { n: 0, v: 0, d: 0 });
      a.n++; a.v += v; a.d += d;
    }
  for (const [z, a] of Object.entries(acc)) out[z] = { ndvi: a.v / a.n, delta: a.d / a.n };
  return out;
}

function MapPane({
  id, registry, map, raster, mode, grid, base, caption, onHover, headerExtra,
}: {
  id: string;
  registry: React.MutableRefObject<Record<string, LeafletMap>>;
  map: MapData;
  raster: RasterData | null;
  mode: Mode;
  grid: boolean;
  base: "sat" | "street";
  caption?: string;
  onHover?: (h: Hover | null) => void;
  headerExtra?: ReactNode;
}) {
  const means = useMemo(() => zoneMeans(raster), [raster]);
  return (
    <div className={`pane base-${base}`}>
      {(caption || headerExtra) && (
        <div className="pane-tag">
          {caption && <strong>{caption}</strong>}
          {headerExtra}
        </div>
      )}
      <MapContainer bounds={map.bounds} scrollWheelZoom zoomSnap={0.25} maxZoom={19} zoomControl={false} className="map" aria-label={`Map of ${map.name}`}>
        {base === "sat" ? (
          <TileLayer key="sat" attribution="Imagery &copy; Esri, Maxar, Earthstar Geographics"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" maxNativeZoom={18} maxZoom={19} />
        ) : (
          <TileLayer key="street" attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxNativeZoom={19} maxZoom={19} />
        )}
        <Fit bounds={map.bounds} />
        <ZoomControl position="bottomright" />
        <Sync id={id} registry={registry} />
        {raster && <RasterOverlay raster={raster} mode={mode} grid={grid} onHover={onHover} />}
        <Pane name="zones" style={{ zIndex: 450 }}>
          {map.zones.map((z) => {
            const m = means[z.id];
            return (
              <Polygon key={z.id} positions={z.polygon.map((ring) => [ring])}
                pathOptions={{ color: z.affected ? "#1769aa" : "#ffffff", weight: z.affected ? 3 : 1, opacity: z.affected ? 1 : 0.5, fill: true, fillOpacity: 0, dashArray: z.affected ? undefined : "2 4" }}>
                <Tooltip sticky>
                  <strong>{z.label}</strong>
                  {z.affected && <><br />Affected zone</>}
                  <br />
                  {m ? <>NDVI {m.ndvi.toFixed(2)}, change {fmtDelta(m.delta)}</> : "No value on this pass"}
                  <br />{z.pixels} pixels
                </Tooltip>
              </Polygon>
            );
          })}
        </Pane>
        <Pane name="outline" style={{ zIndex: 500 }}>
          <Polyline positions={map.outline} pathOptions={{ color: "#ffffff", weight: 5, opacity: 0.95, interactive: false }} />
          <Polyline positions={map.outline} pathOptions={{ color: "#101c16", weight: 2.25, interactive: false }} />
        </Pane>
      </MapContainer>
    </div>
  );
}

export function MapWorkspace({
  caseId, map, series, headlineDate,
}: {
  caseId: string;
  map: MapData;
  series: SeriesData;
  headlineDate: string | null;
}) {
  const usable = useMemo(() => series.scenes.filter((s) => s.quality === "usable" || s.quality === "partial"), [series]);
  const initial = headlineDate && usable.some((s) => s.date === headlineDate) ? headlineDate : usable[usable.length - 1]?.date ?? null;
  const before = useMemo(() => {
    const prior = series.scenes.filter((s) => s.quality === "usable" && s.date < series.alert_date);
    return prior[prior.length - 1]?.date ?? usable[0]?.date ?? null;
  }, [series, usable]);

  const [scene, setScene] = useState<string | null>(initial);
  const [left, setLeft] = useState<string | null>(before);
  const [compare, setCompare] = useState(false);
  const [mode, setMode] = useState<Mode>("ndvi");
  const [grid, setGrid] = useState(false);
  const [base, setBase] = useState<"sat" | "street">("sat");
  const [hover, setHover] = useState<Hover | null>(null);
  const registry = useRef<Record<string, LeafletMap>>({});

  const now = useRaster(caseId, scene);
  const then = useRaster(caseId, compare ? left : null);

  return (
    <div className={`ws ${compare ? "is-compare" : ""}`}>
      <div className="ws-maps">
        {compare && (
          <MapPane id="left" registry={registry} map={map} raster={then} mode={mode} grid={grid} base={base}
            caption={left ? `Before: ${fmtDate(left)}` : "Before"}
            headerExtra={
              <label className="pane-pick">
                <span className="sr-only">Choose the earlier pass</span>
                <select value={left ?? ""} onChange={(e) => setLeft(e.target.value)}>
                  {usable.map((s) => <option key={s.date} value={s.date}>{fmtDate(s.date)}</option>)}
                </select>
              </label>
            } />
        )}
        <MapPane id="right" registry={registry} map={map} raster={now} mode={mode} grid={grid} base={base}
          caption={compare ? `Now: ${scene ? fmtDate(scene) : ""}` : undefined} onHover={setHover} />
      </div>

      <div className="ws-tools" role="toolbar" aria-label="Map layers">
        <div className="seg seg-mode" role="group" aria-label="Colour the field by">
          {(["ndvi", "change", "satellite"] as Mode[]).map((m) => (
            <button key={m} type="button" aria-pressed={mode === m} className={mode === m ? "on" : ""} onClick={() => setMode(m)}>
              {MODE_LABEL[m]}
            </button>
          ))}
        </div>
        <div className="seg" role="group" aria-label="Map options">
          <button type="button" aria-pressed={grid} className={grid ? "on" : ""} onClick={() => setGrid((g) => !g)} title="Draw the 10 m pixel grid">
            <Grid3x3 size={14} aria-hidden /><span>10 m grid</span>
          </button>
          <button type="button" aria-pressed={compare} className={compare ? "on" : ""} onClick={() => setCompare((c) => !c)} title="Compare two dates side by side">
            <Columns2 size={14} aria-hidden /><span>Compare</span>
          </button>
          <button type="button" aria-pressed={base === "street"} className={base === "street" ? "on" : ""} onClick={() => setBase((b) => (b === "sat" ? "street" : "sat"))} title="Switch between satellite and street base map">
            <Layers size={14} aria-hidden /><span>{base === "sat" ? "Street map" : "Satellite map"}</span>
          </button>
        </div>
      </div>

      <div className="ws-legend">
        <Legend mode={mode} raster={now} hover={hover} />
      </div>

      <div className="ws-scenes">
        <SceneBar scenes={series.scenes} selected={scene} alertDate={series.alert_date} onSelect={setScene} />
      </div>
    </div>
  );
}
