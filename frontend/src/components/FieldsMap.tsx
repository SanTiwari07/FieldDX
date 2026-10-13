import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Polygon, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { useNavigate } from "react-router-dom";
import "leaflet/dist/leaflet.css";
import { api, FieldsGeoJson, Outcome } from "../api";

const STYLE: Record<string, { color: string; fill: string; label: string }> = {
  field_case: { color: "#101c16", fill: "#101c16", label: "Needs a visit" },
  unexplained: { color: "#101c16", fill: "#101c16", label: "Ask or visit" },
  watch: { color: "#8a5a00", fill: "#e09a0d", label: "Watching" },
  area_alert: { color: "#1769aa", fill: "#1769aa", label: "Area alert" },
  resolved: { color: "#065f2c", fill: "#065f2c", label: "Resolved" },
  auto_dismissed: { color: "#737b82", fill: "#9aa0a6", label: "Dismissed" },
  none: { color: "#5c6670", fill: "#ffffff", label: "No alert" },
};

function Fit({ pts }: { pts: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (!pts.length) return;
    map.fitBounds(pts, { padding: [24, 24] });
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(map.getContainer());
    return () => ro.disconnect();
  }, [map, pts]);
  return null;
}

function Dots({ gj, nav }: { gj: FieldsGeoJson; nav: (to: string) => void }) {
  const map = useMap();
  const [zoom, setZoom] = useState(map.getZoom());
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) });
  if (zoom >= 15) return null; // from here the real shapes are big enough to see and click
  return (
    <>
      {gj.features.map((f) => {
        const o = f.properties.case_outcome;
        const ring = f.geometry.coordinates[0];
        const lat = ring.reduce((a, c) => a + c[1], 0) / ring.length;
        const lng = ring.reduce((a, c) => a + c[0], 0) / ring.length;
        const st = STYLE[o ?? "none"];
        return (
          <CircleMarker key={f.properties.id} center={[lat, lng]} radius={o ? 7 : 4}
            pathOptions={{ color: "#ffffff", weight: 2, fillColor: st.fill, fillOpacity: o ? 0.95 : 0.7 }}
            eventHandlers={{ click: () => o && nav(`/case/${f.properties.id}`) }}>
            <Tooltip sticky>
              <strong>{f.properties.name}</strong><br />{f.properties.area_ha} ha, {f.properties.class}<br />{st.label}{o ? ". Click to open." : ""}
            </Tooltip>
          </CircleMarker>
        );
      })}
    </>
  );
}

/** Every monitored field, drawn with its real shape and coloured by what the investigation concluded. */
export default function FieldsMap({ fieldId }: { fieldId?: string }) {
  const [gj, setGj] = useState<FieldsGeoJson | null>(null);
  const nav = useNavigate();
  useEffect(() => { api.fieldsGeoJson().then(setGj).catch(() => undefined); }, []);
  const pts = useMemo(
    () => (gj ? gj.features.flatMap((f) => f.geometry.coordinates[0].map(([lng, lat]) => [lat, lng] as [number, number])) : []),
    [gj],
  );
  if (!gj) return <div className="fieldsmap skeleton" aria-busy="true" />;
  const used = Array.from(new Set(gj.features.map((f) => f.properties.case_outcome ?? "none")));
  return (
    <figure className="fieldsmap-wrap">
      <div className="fieldsmap">
        <MapContainer center={[20.077, 74.115]} zoom={13} scrollWheelZoom className="map" aria-label="Map of the monitored fields, coloured by case outcome">
          <TileLayer attribution="Imagery &copy; Esri, Maxar, Earthstar Geographics"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" maxNativeZoom={18} maxZoom={19} />
          <Fit pts={pts} />
          {gj.features.map((f) => {
            const o = (f.properties.case_outcome ?? "none") as Outcome | "none";
            const st = STYLE[o];
            const has = f.properties.case_outcome !== null;
            return (
              <Polygon key={f.properties.id} positions={f.geometry.coordinates[0].map(([lng, lat]) => [lat, lng])}
                pathOptions={{ color: st.color, weight: f.properties.id === fieldId ? 4 : has ? 2.5 : 1.5, fillColor: st.fill, fillOpacity: has ? 0.5 : 0.12, opacity: 0.95 }}
                eventHandlers={{ click: () => has && nav(`/case/${f.properties.id}`) }}>
                <Tooltip sticky>
                  <strong>{f.properties.name}</strong><br />{f.properties.area_ha} ha, {f.properties.class}<br />{st.label}{has ? ". Click to open." : ""}
                </Tooltip>
              </Polygon>
            );
          })}
          <Dots gj={gj} nav={nav} />
        </MapContainer>
      </div>
      <figcaption className="fieldsmap-legend">
        {used.map((k) => (
          <span key={k}><i style={{ background: STYLE[k].fill, borderColor: STYLE[k].color }} /> {STYLE[k].label}</span>
        ))}
        <span className="muted">Zoom in to see the real field shapes. Shapes: Fields of the World model, 2025. Imagery: Esri.</span>
      </figcaption>
    </figure>
  );
}
