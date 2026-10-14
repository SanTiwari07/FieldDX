import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CircleMarker, MapContainer, Polygon, Polyline, Rectangle, TileLayer, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  Activity, ArrowRight, Check, CornerUpLeft, Hand, Layers, MapPin, MousePointerClick, Navigation, PenLine, Search, Trash2, Type, X,
} from "lucide-react";
import { api, AreaSummary, FieldsSource, GeoPolygon, OverviewMap, OverviewSummary, Place } from "../api";
import { fmtDate } from "../lib/format";
import { DELTA_STOPS } from "../lib/ramps";
import { useSession } from "../session";
import { FtwLayer, MIN_FIELD_HA, PickedField, ZONED_HA } from "../components/FtwLayer";
import { Spinner } from "../components/ui";

type Mode = "pick" | "draw" | "coords";
type LngLat = [number, number];

const MAX_KM2_FALLBACK = 150;
const PICK_MARGIN_M = 400;

// ---------- geometry (lon/lat, small areas)

function ringKm2(ring: LngLat[]): number {
  if (ring.length < 3) return 0;
  const lat0 = ring.reduce((a, p) => a + p[1], 0) / ring.length;
  const kx = 111.32 * Math.cos((lat0 * Math.PI) / 180), ky = 110.57;
  let s = 0;
  for (let i = 0; i < ring.length; i++) {
    const [x1, y1] = ring[i], [x2, y2] = ring[(i + 1) % ring.length];
    s += x1 * kx * (y2 * ky) - x2 * kx * (y1 * ky);
  }
  return Math.abs(s) / 2;
}

function closeRing(ring: LngLat[]): LngLat[] {
  const r = ring.slice();
  const [a, b] = [r[0], r[r.length - 1]];
  if (a[0] !== b[0] || a[1] !== b[1]) r.push(a);
  return r;
}

function boxAround(points: LngLat[], marginM: number): LngLat[] {
  const lats = points.map((p) => p[1]), lngs = points.map((p) => p[0]);
  const lat0 = (Math.min(...lats) + Math.max(...lats)) / 2;
  const dLat = marginM / 110_570, dLng = marginM / (111_320 * Math.cos((lat0 * Math.PI) / 180));
  const w = Math.min(...lngs) - dLng, e = Math.max(...lngs) + dLng, s = Math.min(...lats) - dLat, n = Math.max(...lats) + dLat;
  return [[w, s], [e, s], [e, n], [w, n], [w, s]];
}

function squareAround(lat: number, lng: number, km: number): LngLat[] {
  const half = (km * 1000) / 2;
  return boxAround([[lng, lat]], half);
}

/** One line "lat, lon" gives a square of the chosen size; three or more lines are the corners of a polygon. */
function parseCoords(text: string, km: number): { ring: LngLat[] | null; error: string } {
  const lines = text.split(/\n|;/).map((l) => l.trim()).filter(Boolean);
  const pts: LngLat[] = [];
  for (const l of lines) {
    const m = l.match(/^(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)$/);
    if (!m) return { ring: null, error: `Could not read "${l.slice(0, 40)}". Write latitude, longitude.` };
    const lat = Number(m[1]), lng = Number(m[2]);
    if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return { ring: null, error: `"${l}" is not a place on Earth.` };
    pts.push([lng, lat]);
  }
  if (!pts.length) return { ring: null, error: "" };
  if (pts.length === 1) return { ring: squareAround(pts[0][1], pts[0][0], km), error: "" };
  if (pts.length === 2) return { ring: null, error: "Two points make a line. Add a third corner, or keep one centre point." };
  return { ring: closeRing(pts), error: "" };
}

const toLatLng = (ring: LngLat[]) => ring.map(([lng, lat]) => [lat, lng] as [number, number]);

function outerRings(g: GeoPolygon): LngLat[][] {
  return g.type === "Polygon" ? [g.coordinates[0] as LngLat[]] : g.coordinates.map((p) => p[0] as LngLat[]);
}

// ---------- map helpers

const WORLD: [number, number][] = [[-89, -179.9], [-89, 179.9], [89, 179.9], [89, -179.9]];

/** Fit and lock the map to the chosen region: the officer works inside it, not across the country. */
function RegionLock({ place }: { place: Place | null }) {
  const map = useMap();
  useEffect(() => {
    if (!place) {
      map.setMaxBounds(undefined as unknown as L.LatLngBoundsExpression);
      map.setMinZoom(3);
      return;
    }
    const b = L.latLngBounds(place.bounds);
    map.setMaxBounds(undefined as unknown as L.LatLngBoundsExpression);
    map.setMinZoom(3);
    map.invalidateSize();
    map.fitBounds(b, { padding: [24, 24], animate: false });
    map.setMinZoom(Math.max(3, map.getZoom() - 1));
    map.setMaxBounds(b.pad(0.35));
  }, [map, place]);
  return null;
}

function FitTo({ ring }: { ring: LngLat[] | null }) {
  const map = useMap();
  const key = ring ? ring.map((p) => p.join(",")).join(";") : "";
  useEffect(() => {
    if (ring && ring.length > 2) map.fitBounds(L.latLngBounds(toLatLng(ring)), { padding: [40, 40], maxZoom: 16 });
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function MapHandle({ onMap }: { onMap: (m: L.Map) => void }) {
  const map = useMap();
  useEffect(() => { onMap(map); }, [map, onMap]);
  return null;
}

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "–" : `${Math.round(v * 100)}%`);

/** The region at a glance: how much of its cropland lost greenness this fortnight, and where. */
function Overview({ place, summary, error, onGo }: {
  place: Place;
  summary: OverviewSummary | null;
  error: string;
  onGo: (b: [[number, number], [number, number]], near: string) => void;
}) {
  if (error) return <p className="hint warn">{error}</p>;
  if (!summary) {
    return <p className="hint"><Spinner /> Reading this fortnight's Sentinel-2 passes across {place.name}. This takes about half a minute.</p>;
  }
  const w = summary.windows;
  return (
    <>
      <p className="setup-sub">Cropland NDVI, {fmtDate(w.recent[0])} to {fmtDate(w.recent[1])} against {fmtDate(w.baseline[0])} to {fmtDate(w.baseline[1])}. Clouds masked per pixel.</p>
      <dl className="ov-stats">
        <div className="drop"><dt>Lost greenness</dt><dd>{pct(summary.drop)}</dd><small>of cropland, 0.10 NDVI or more</small></div>
        <div className="gain"><dt>Greened up</dt><dd>{pct(summary.gain)}</dd><small>0.10 NDVI or more</small></div>
        <div><dt>Seen clearly</dt><dd>{pct(summary.seen)}</dd><small>of {summary.cropland_km2.toLocaleString()} km² cropland</small></div>
      </dl>
      {summary.hotspots.length > 0 ? (
        <>
          <h3 className="ov-h"><Activity size={14} aria-hidden /> Where most of it dropped</h3>
          <ul className="hotspots">
            {summary.hotspots.map((h, i) => (
              <li key={i}>
                <button type="button" onClick={() => onGo(h.bounds, h.near)}>
                  <span className="hs-text">
                    <strong>Around {h.near || `${h.center[0].toFixed(3)}, ${h.center[1].toFixed(3)}`}</strong>
                    <small>{pct(h.drop)} of {h.cropland_km2} km² of cropland dropped</small>
                  </span>
                  <span className="hs-bar" aria-hidden><span style={{ width: `${Math.min(100, h.drop * 100)}%` }} /></span>
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : <p className="muted small">No part of the region stands out this fortnight.</p>}
      <p className="muted small">A screen, not a diagnosis: a harvested field drops like a failing one. Go to the land and mark it, and FieldDx investigates it field by field.</p>
    </>
  );
}

function ZoomWatch({ onZoom }: { onZoom: (z: number) => void }) {
  const map = useMapEvents({ zoomend: () => onZoom(map.getZoom()) });
  useEffect(() => { onZoom(map.getZoom()); }, [map, onZoom]);
  return null;
}

function DrawClicks({ active, onAdd }: { active: boolean; onAdd: (p: LngLat) => void }) {
  const map = useMap();
  useEffect(() => {
    if (active) map.doubleClickZoom.disable();
    else map.doubleClickZoom.enable();
    map.getContainer().classList.toggle("is-drawing", active);
  }, [map, active]);
  useMapEvents({ click: (e) => { if (active) onAdd([e.latlng.lng, e.latlng.lat]); } });
  return null;
}

// ---------- page

function ExistingAreas({ areas, onJoin, busy }: { areas: AreaSummary[]; onJoin: (id: string) => void; busy: string }) {
  if (!areas.length) return null;
  return (
    <section className="setup-block">
      <h2 className="setup-h">Already set up</h2>
      <p className="setup-sub">Work in an area a colleague has built. Its cases and findings are shared.</p>
      <ul className="area-list">
        {areas.map((a) => (
          <li key={a.id}>
            <div>
              <strong>{a.name}</strong>
              <small>{a.region}{a.fields ? ` · ${a.fields} fields` : ""}{a.status !== "ready" ? " · being set up" : ""}</small>
            </div>
            <button type="button" className="btn btn-outline btn-sm" onClick={() => onJoin(a.id)} disabled={!!busy}>
              {busy === a.id ? <Spinner /> : null} Work here
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function Setup() {
  const { me, set } = useSession();
  const nav = useNavigate();
  const [existing, setExisting] = useState<AreaSummary[]>([]);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Place[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [place, setPlace] = useState<Place | null>(null);
  const [source, setSource] = useState<FieldsSource | null>(null);
  const [mode, setMode] = useState<Mode>("draw");
  const [showFtw, setShowFtw] = useState(true);
  const [zoom, setZoom] = useState(5);
  const [picked, setPicked] = useState<PickedField[]>([]);
  const [draw, setDraw] = useState<LngLat[]>([]);
  const [closed, setClosed] = useState(false);
  const [coordText, setCoordText] = useState("");
  const [km, setKm] = useState(5);
  const [fieldSource, setFieldSource] = useState<"ftw_global" | "ftw_model">("ftw_global");
  const [name, setName] = useState("");
  const [nameTouched, setNameTouched] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [ovMap, setOvMap] = useState<OverviewMap | null>(null);
  const [ovSummary, setOvSummary] = useState<OverviewSummary | null>(null);
  const [ovError, setOvError] = useState("");
  const [showChange, setShowChange] = useState(true);
  const [goText, setGoText] = useState("");
  const [goPoint, setGoPoint] = useState<[number, number] | null>(null);
  const [goError, setGoError] = useState("");
  const mapRef = useRef<L.Map | null>(null);
  const onMap = useCallback((m: L.Map) => { mapRef.current = m; }, []);
  const searchBox = useRef<HTMLInputElement>(null);

  useEffect(() => { api.areas().then((r) => setExisting(r.areas)).catch(() => undefined); }, []);
  useEffect(() => { searchBox.current?.focus(); }, []);

  const partition = source?.partition ?? null;
  const maxKm2 = source?.max_km2 ?? MAX_KM2_FALLBACK;

  // pick mode needs the published map; without it, start in draw mode and run the model if we can
  useEffect(() => {
    if (!source) return;
    if (!source.partition) {
      setMode((m) => (m === "pick" ? "draw" : m));
      setFieldSource("ftw_model");
    } else {
      setFieldSource("ftw_global");
    }
  }, [source]);

  const search = async (e?: FormEvent) => {
    e?.preventDefault();
    if (q.trim().length < 2) return;
    setSearching(true);
    setSearchError("");
    try {
      setResults((await api.places(q.trim())).places);
    } catch (err) {
      setSearchError((err as Error).message);
    } finally {
      setSearching(false);
    }
  };

  const choose = async (p: Place) => {
    setPlace(p);
    setResults(null);
    setName(p.name);
    setPicked([]); setDraw([]); setClosed(false); setCoordText(""); setError("");
    setSource(null);
    setOvMap(null); setOvSummary(null); setOvError(""); setGoPoint(null); setGoError("");
    const region = { name: p.name, bounds: p.bounds, boundary: p.boundary };
    api.overviewMap(region).then(setOvMap).catch((e) => setOvError((e as Error).message));
    api.overviewSummary(region).then(setOvSummary).catch((e) => setOvError((e as Error).message));
    try {
      setSource(await api.fieldsSource(p.country, p.subdivision));
    } catch (e) {
      setSource({ partition: null, model_available: false, max_km2: MAX_KM2_FALLBACK });
      setError(`Could not check the published field shapes: ${(e as Error).message}`);
    }
  };

  const coords = useMemo(() => parseCoords(coordText, km), [coordText, km]);

  const flyTo = (b: [[number, number], [number, number]]) => mapRef.current?.flyToBounds(b, { padding: [24, 24], duration: 0.8 });

  /** Take the officer to a farm by its coordinates; the polygon is drawn there. */
  const goTo = (e: FormEvent) => {
    e.preventDefault();
    setGoError("");
    const m = goText.trim().match(/^(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)$/);
    if (!m) { setGoError("Write latitude, longitude, for example 16.7410, 74.4425."); return; }
    const lat = Number(m[1]), lng = Number(m[2]);
    if (place && !L.latLngBounds(place.bounds).contains([lat, lng])) {
      setGoError(`That point is outside ${place.name}. Check the order: latitude first, then longitude.`);
      return;
    }
    setGoPoint([lat, lng]);
    mapRef.current?.flyTo([lat, lng], 17, { duration: 0.8 });
    if (mode === "coords") setMode("draw");
  };

  const ring: LngLat[] | null = useMemo(() => {
    if (mode === "pick") return picked.length ? boxAround(picked.map((p) => p.point), PICK_MARGIN_M) : null;
    if (mode === "draw") return closed && draw.length >= 3 ? closeRing(draw) : null;
    return coords.ring;
  }, [mode, picked, draw, closed, coords.ring]);

  const km2 = ring ? ringKm2(ring.slice(0, -1)) : 0;
  const tooBig = km2 > maxKm2;
  const wholePicks = picked.filter((p) => p.areaHa !== null && p.areaHa < ZONED_HA).length;
  const canBuild = !!place && !!ring && !tooBig && km2 > 0.05 && name.trim().length >= 2 && !busy
    && (fieldSource === "ftw_model" ? !!source?.model_available : !!partition);

  const [pickNote, setPickNote] = useState("");
  const togglePick = (f: PickedField) => {
    if (picked.some((p) => p.key === f.key)) {
      setPicked((list) => list.filter((p) => p.key !== f.key));
      setPickNote("");
      return;
    }
    if (f.areaHa !== null && f.areaHa < MIN_FIELD_HA) {
      setPickNote(`That field is ${f.areaHa < 0.1 ? "under 0.1" : f.areaHa.toFixed(2)} ha, about ${Math.max(1, Math.round(f.areaHa * 100))} pixels of 10 m. FieldDx needs at least ${MIN_FIELD_HA} ha to read a field, so it cannot watch this one. Pick a yellow field.`);
      return;
    }
    setPickNote("");
    setPicked((list) => [...list, f]);
  };

  const addVertex = (p: LngLat) => {
    if (closed) return;
    if (draw.length >= 3) {
      const map0 = draw[0];
      const near = Math.hypot((p[0] - map0[0]) * 111_320 * Math.cos((p[1] * Math.PI) / 180), (p[1] - map0[1]) * 110_570);
      if (near < Math.max(25, 1.5 * 2 ** (20 - zoom))) { setClosed(true); return; }
    }
    setDraw((d) => [...d, p]);
  };

  const join = async (id: string) => {
    setBusy(id);
    try {
      set(await api.joinArea(id));
      nav("/", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy("");
    }
  };

  const build = async () => {
    if (!place || !ring) return;
    setBusy("build");
    setError("");
    try {
      const m = await api.createArea({
        name: name.trim(), region: [place.name, place.context].filter(Boolean).join(", "),
        geometry: { type: "Polygon", coordinates: [ring] }, mode, field_source: fieldSource,
        boundary: place.boundary, partition: partition ? { code: partition.code } : null,
        picked_points: mode === "pick" ? picked.map((p) => p.point) : undefined,
      });
      set(m);
      nav("/", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy("");
    }
  };

  if (me?.officer.demo) {
    return (
      <main className="page narrow">
        <h1>The demo officer works in Niphad</h1>
        <p className="lede">Create your own account to mark an area of your own. The demo area stays as it is for everyone.</p>
        <button type="button" className="btn btn-primary" onClick={() => nav("/")}>Back to Niphad <ArrowRight size={15} aria-hidden /></button>
      </main>
    );
  }

  const mask = place
    ? (place.boundary ? outerRings(place.boundary).map((r) => toLatLng(r)) : [toLatLng(boxAround([[place.bounds[0][1], place.bounds[0][0]], [place.bounds[1][1], place.bounds[1][0]]], 0))])
    : [];

  return (
    <main className="setup">
      <aside className="setup-panel">
        <header>
          <div className="eyebrow">Step 2 of 3 · Your area</div>
          <h1>Where do you work{me ? `, ${me.officer.name.split(" ")[0]}` : ""}?</h1>
          <p className="lede">FieldDx builds real data for the area you mark, and you will only see cases from it.</p>
        </header>

        {!place && <ExistingAreas areas={existing} onJoin={join} busy={busy} />}

        <section className="setup-block">
          <h2 className="setup-h"><span className="n">1</span> Find your region</h2>
          {place ? (
            <div className="place-chip">
              <MapPin size={16} aria-hidden />
              <div><strong>{place.name}</strong><small>{place.kind} · {place.context}</small></div>
              <button type="button" className="icon-btn" aria-label="Choose another region" onClick={() => { setPlace(null); setSource(null); setPicked([]); setDraw([]); setClosed(false); searchBox.current?.focus(); }}>
                <X size={16} />
              </button>
            </div>
          ) : (
            <>
              <form className="search" onSubmit={search} role="search">
                <Search size={16} aria-hidden />
                <input ref={searchBox} className="input" value={q} onChange={(e) => setQ(e.target.value)}
                  placeholder="District, taluka or village, e.g. Kolhapur" aria-label="Search for your region" />
                <button className="btn btn-primary btn-sm" type="submit" disabled={searching || q.trim().length < 2}>
                  {searching ? <Spinner /> : "Search"}
                </button>
              </form>
              {searchError && <p className="form-error" role="alert">{searchError}</p>}
              {results && (
                results.length ? (
                  <ul className="results" aria-label="Places found">
                    {results.map((p) => (
                      <li key={p.id}>
                        <button type="button" onClick={() => choose(p)}>
                          <strong>{p.name}</strong> <span className="kind">{p.kind}</span>
                          <small>{p.context}</small>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : <p className="muted small">Nothing found. Try the district name.</p>
              )}
            </>
          )}
        </section>

        {place && (
          <section className="setup-block">
            <h2 className="setup-h"><span className="n">2</span> What is changing in {place.name}</h2>
            <Overview place={place} summary={ovSummary} error={ovError}
              onGo={(b, near) => { flyTo(b); if (near && !nameTouched) setName(`Around ${near}`); }} />
          </section>
        )}

        {place && (
          <section className="setup-block">
            <h2 className="setup-h"><span className="n">3</span> Go to the land and mark it</h2>
            <form className="search goto" onSubmit={goTo}>
              <Navigation size={16} aria-hidden />
              <input className="input" value={goText} onChange={(e) => setGoText(e.target.value)} spellCheck={false}
                placeholder="Farm coordinates, e.g. 16.7410, 74.4425" aria-label="Go to coordinates" />
              <button className="btn btn-outline btn-sm" type="submit" disabled={!goText.trim()}>Go</button>
            </form>
            {goError && <p className="form-error">{goError}</p>}
            <p className="muted small">Or zoom in on the map, or tap a hotspot above. Then mark the land you want examined:</p>
            <div className="seg mode-seg" role="tablist" aria-label="How to mark the area">
              <button type="button" role="tab" aria-selected={mode === "draw"} className={mode === "draw" ? "on" : ""} onClick={() => setMode("draw")}><PenLine size={14} aria-hidden /> Draw a polygon</button>
              <button type="button" role="tab" aria-selected={mode === "pick"} className={mode === "pick" ? "on" : ""} disabled={!partition} onClick={() => setMode("pick")}><MousePointerClick size={14} aria-hidden /> Pick fields</button>
              <button type="button" role="tab" aria-selected={mode === "coords"} className={mode === "coords" ? "on" : ""} onClick={() => setMode("coords")}><Type size={14} aria-hidden /> Type corners</button>
            </div>

            {mode === "pick" && (
              <div className="mode-help">
                <p>Tap fields on the map to add them. These are the field shapes Fields of the World already published for {place.subdivision ? "this state" : "this region"} ({partition?.layers[0]}).</p>
                <p className="muted small">Fields of {ZONED_HA} ha or more are read in eight zones, four interior quarters and four edges, which lets FieldDx tell an edge problem from a patch. Smaller fields down to {MIN_FIELD_HA} ha are read as one zone: the drop, neighbours, weather and season still count, but not where in the field it is.</p>
                {zoom < 13 && <p className="hint"><Hand size={14} aria-hidden /> Zoom in to see the fields.</p>}
                <p className="stat"><strong>{picked.length}</strong> field{picked.length === 1 ? "" : "s"} picked
                  {picked.length > 0 && <button type="button" className="link-btn" onClick={() => setPicked([])}>Clear</button>}</p>
                <p className="ftw-key"><span className="k-big" aria-hidden /> Eight zones <span className="k-whole" aria-hidden /> One zone <span className="k-small" aria-hidden /> Under {MIN_FIELD_HA} ha, too small</p>
                {pickNote && <p className="hint warn" role="status">{pickNote}</p>}
                {wholePicks > 0 && <p className="muted small">{wholePicks} of them {wholePicks === 1 ? "is" : "are"} under {ZONED_HA} ha and will be read as one zone.</p>}
                {picked.length > 0 && picked.length < 3 && <p className="muted small">Pick a few neighbouring fields too: FieldDx compares each field with similar ones within 2 km to tell an area-wide event from a field problem.</p>}
              </div>
            )}
            {mode === "draw" && (
              <div className="mode-help">
                <p>Click around the land to place corners. Click the first corner again to close the shape.</p>
                <div className="draw-tools">
                  <span className="stat"><strong>{draw.length}</strong> corner{draw.length === 1 ? "" : "s"}{closed ? ", closed" : ""}</span>
                  <button type="button" className="btn btn-ghost btn-sm" disabled={!draw.length} onClick={() => { setClosed(false); setDraw((d) => d.slice(0, -1)); }}><CornerUpLeft size={14} aria-hidden /> Undo</button>
                  <button type="button" className="btn btn-ghost btn-sm" disabled={draw.length < 3 || closed} onClick={() => setClosed(true)}><Check size={14} aria-hidden /> Close shape</button>
                  <button type="button" className="btn btn-ghost btn-sm" disabled={!draw.length} onClick={() => { setDraw([]); setClosed(false); }}><Trash2 size={14} aria-hidden /> Clear</button>
                </div>
              </div>
            )}
            {mode === "coords" && (
              <div className="mode-help">
                <label className="field">
                  <span className="caption">One point per line: latitude, longitude</span>
                  <textarea value={coordText} onChange={(e) => setCoordText(e.target.value)} rows={4} spellCheck={false}
                    placeholder={`${place.center[0].toFixed(4)}, ${place.center[1].toFixed(4)}`} />
                </label>
                <p className="muted small">One point makes a square around it. Three or more points are the corners of your area.</p>
                <label className="field inline">
                  <span className="caption">Square size</span>
                  <select className="input" value={km} onChange={(e) => setKm(Number(e.target.value))}>
                    {[2, 3, 5, 7, 9, 12].map((k) => <option key={k} value={k}>{k} × {k} km</option>)}
                  </select>
                </label>
                {coords.error && <p className="form-error">{coords.error}</p>}
              </div>
            )}
            {ring && (
              <p className={`area-size ${tooBig ? "bad" : ""}`}>
                {km2 < 1 ? `${(km2 * 100).toFixed(0)} ha` : `${km2.toFixed(1)} km²`}
                {tooBig ? ` is over the ${maxKm2} km² limit. Make it smaller.` : mode === "pick" ? " of imagery around the picked fields." : " marked."}
              </p>
            )}
          </section>
        )}

        {place && ring && !tooBig && (
          <section className="setup-block">
            <h2 className="setup-h"><span className="n">4</span> Build it</h2>
            <fieldset className="source">
              <legend className="caption">Field shapes</legend>
              <label className={`radio ${!partition ? "off" : ""}`}>
                <input type="radio" name="src" checked={fieldSource === "ftw_global"} disabled={!partition} onChange={() => setFieldSource("ftw_global")} />
                <span><strong>Fields of the World map</strong><small>{partition ? `Published shapes for ${partition.code.replace("_", "-")}. About two minutes.` : "Not published for this region."}</small></span>
              </label>
              <label className={`radio ${!source?.model_available || mode === "pick" ? "off" : ""}`}>
                <input type="radio" name="src" checked={fieldSource === "ftw_model"} disabled={!source?.model_available || mode === "pick"} onChange={() => setFieldSource("ftw_model")} />
                <span><strong>Run the model on fresh imagery</strong><small>{source?.model_available ? "Sharper on small plots, but takes 15 to 40 minutes." : "The model is not installed on this server."}</small></span>
              </label>
            </fieldset>
            <label className="field">
              <span className="caption">Name of this area</span>
              <input className="input" value={name} onChange={(e) => { setName(e.target.value); setNameTouched(true); }} maxLength={60} />
            </label>
            <p className="muted small">FieldDx will fetch about 13 months of Sentinel-2 passes for {km2 < 1 ? `${(km2 * 100).toFixed(0)} ha` : `${km2.toFixed(1)} km²`}, the weather, and then look for alerts. You can leave this page while it works.</p>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button type="button" className="btn btn-primary btn-block" disabled={!canBuild} onClick={build}>
              {busy === "build" ? <Spinner /> : null} Set up {name.trim() || "this area"} <ArrowRight size={15} aria-hidden />
            </button>
          </section>
        )}
        {!ring && error && <p className="form-error" role="alert">{error}</p>}
      </aside>

      <section className="setup-map" aria-label="Map">
        <MapContainer center={[20.5, 78.9]} zoom={5} minZoom={3} scrollWheelZoom className="map" worldCopyJump={false}>
          <TileLayer attribution="Imagery &copy; Esri, Maxar, Earthstar Geographics" maxNativeZoom={18} maxZoom={19}
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
          <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
            maxNativeZoom={18} maxZoom={19} opacity={0.85} />
          <RegionLock place={place} />
          <ZoomWatch onZoom={setZoom} />
          <MapHandle onMap={onMap} />
          {place && ovMap && showChange && (
            <TileLayer key={ovMap.key} url={ovMap.tiles} opacity={zoom >= 15 ? 0.5 : 0.85} zIndex={250} maxNativeZoom={15} maxZoom={19}
              attribution="Change: Sentinel-2 via Google Earth Engine" />
          )}
          {place && ovSummary && showChange && zoom < 13 && ovSummary.hotspots.map((h, i) => (
            <Rectangle key={`hs-${i}`} bounds={h.bounds} pathOptions={{ color: "#fbbf24", weight: 1.5, dashArray: "5 5", fill: false }}
              eventHandlers={{ click: () => flyTo(h.bounds) }} />
          ))}
          {goPoint && (
            <CircleMarker center={goPoint} radius={9} interactive={false}
              pathOptions={{ color: "#101c16", weight: 3, fillColor: "#ffffff", fillOpacity: 1 }} />
          )}
          {place && (
            <>
              <Polygon positions={[WORLD, ...mask]} interactive={false}
                pathOptions={{ stroke: false, fillColor: "#0b1410", fillOpacity: 0.55 }} />
              {mask.map((r, i) => (
                <Polygon key={i} positions={r} interactive={false} pathOptions={{ color: "#ffffff", weight: 2, opacity: 0.9, fill: false, dashArray: "6 6" }} />
              ))}
            </>
          )}
          {place && partition && (showFtw || mode === "pick") && (
            <FtwLayer url={`/api/ftw/${partition.code}.pmtiles`} layer={partition.layers[0]} picking={mode === "pick"} picked={picked} onPick={togglePick} />
          )}
          <DrawClicks active={!!place && mode === "draw" && !closed} onAdd={addVertex} />
          {mode === "draw" && draw.length > 0 && (
            <>
              {closed
                ? <Polygon positions={toLatLng(draw)} pathOptions={{ color: "#ffffff", weight: 3, fillColor: "#101c16", fillOpacity: 0.18 }} interactive={false} />
                : <Polyline positions={toLatLng(draw)} pathOptions={{ color: "#ffffff", weight: 3, dashArray: "4 6" }} interactive={false} />}
              {draw.map(([lng, lat], i) => (
                <CircleMarker key={i} center={[lat, lng]} radius={i === 0 && !closed && draw.length >= 3 ? 8 : 5}
                  pathOptions={{ color: i === 0 ? "#101c16" : "#ffffff", weight: 2, fillColor: i === 0 ? "#ffffff" : "#101c16", fillOpacity: 1 }}
                  eventHandlers={{ click: (e) => { if (i === 0 && draw.length >= 3 && !closed) { L.DomEvent.stopPropagation(e); setClosed(true); } } }} />
              ))}
            </>
          )}
          {mode === "pick" && ring && (
            <Rectangle bounds={L.latLngBounds(toLatLng(ring))} interactive={false}
              pathOptions={{ color: "#ffffff", weight: 1.5, dashArray: "4 4", fill: false }} />
          )}
          {mode === "pick" && picked.map((p) => (
            <CircleMarker key={p.key} center={[p.point[1], p.point[0]]} radius={4} interactive={false}
              pathOptions={{ color: "#101c16", weight: 1.5, fillColor: "#ffffff", fillOpacity: 1 }} />
          ))}
          {mode === "coords" && ring && (
            <>
              <Polygon positions={toLatLng(ring)} pathOptions={{ color: "#ffffff", weight: 3, fillColor: "#101c16", fillOpacity: 0.18 }} interactive={false} />
              <FitTo ring={ring} />
            </>
          )}
        </MapContainer>
        {place && (
          <div className="map-toggles">
            {ovMap && (
              <button type="button" className={`map-toggle ${showChange ? "on" : ""}`} onClick={() => setShowChange((v) => !v)} aria-pressed={showChange}>
                <Activity size={14} aria-hidden /> Change this fortnight
              </button>
            )}
            {partition && mode !== "pick" && (
              <button type="button" className={`map-toggle ${showFtw ? "on" : ""}`} onClick={() => setShowFtw((v) => !v)} aria-pressed={showFtw}>
                <Layers size={14} aria-hidden /> Fields of the World shapes
              </button>
            )}
          </div>
        )}
        {place && ovMap && showChange && (
          <div className="ov-legend" aria-label="Legend: change in NDVI this fortnight">
            <strong>NDVI change, cropland</strong>
            <div className="legend-bar" style={{ background: `linear-gradient(90deg, ${DELTA_STOPS.map(([, c]) => c).join(", ")})` }} />
            <div className="legend-ends"><span>Loss ≤ −0.15</span><span>0</span><span>Gain ≥ +0.15</span></div>
          </div>
        )}
        {!place && <div className="map-hint"><Search size={14} aria-hidden /> Search for your district to lock the map to it.</div>}
      </section>
    </main>
  );
}
