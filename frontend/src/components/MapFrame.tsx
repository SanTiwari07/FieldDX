import { useEffect, useState } from "react";
import { MapContainer, Pane, Polygon, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { Grid3x3, Layers } from "lucide-react";
import { MapData } from "../api";
import { DELTA_BINS, deltaColor, fmtDate, fmtDelta } from "../lib/format";

function Fit({ bounds }: { bounds: MapData["bounds"] }) {
  const map = useMap();
  useEffect(() => {
    let touched = false;
    let fitting = false;
    const fit = () => {
      fitting = true;
      map.invalidateSize();
      map.fitBounds(bounds, { padding: [34, 34], maxZoom: 19, animate: false });
      fitting = false;
    };
    fit();
    // the frame can change size as fonts and the rail settle; keep the field centred until the user moves the map
    const ro = new ResizeObserver(() => {
      if (!touched) fit();
    });
    ro.observe(map.getContainer());
    const stop = () => {
      if (!fitting) touched = true;
    };
    map.on("dragstart zoomstart", stop);
    return () => {
      ro.disconnect();
      map.off("dragstart zoomstart", stop);
    };
  }, [map, bounds]);
  return null;
}

export function MapFrame({ data, fieldName }: { data: MapData; fieldName: string }) {
  const [grid, setGrid] = useState(false);
  const [base, setBase] = useState<"sat" | "street">("sat");
  const noData = (q: string) => q === "cloudy" || q === "none";
  return (
    <figure className={`map-frame base-${base}`}>
      {/* hatch used for zones with no honest number */}
      <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden>
        <defs>
          <pattern id="nodata-hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="7" height="7" fill="#e5e7eb" fillOpacity="0.85" />
            <line x1="0" y1="0" x2="0" y2="7" stroke="#9aa0a6" strokeWidth="2" />
          </pattern>
        </defs>
      </svg>

      <MapContainer
        bounds={data.bounds}
        scrollWheelZoom={false}
        zoomSnap={0.25}
        maxZoom={19}
        className="map"
        attributionControl
        aria-label={`Map of ${fieldName} with zones coloured by change in NDVI`}
      >
        {base === "sat" ? (
          <TileLayer
            key="sat"
            attribution="Imagery &copy; Esri, Maxar, Earthstar Geographics"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            maxNativeZoom={18}
            maxZoom={19}
          />
        ) : (
          <TileLayer
            key="street"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxNativeZoom={19}
            maxZoom={19}
          />
        )}
        <Fit bounds={data.bounds} />
        <Pane name="zones" style={{ zIndex: 450 }}>
          {data.zones.map((z) => (
            <Polygon
              key={z.id}
              positions={z.polygon}
              pathOptions={{
                stroke: true,
                color: z.affected ? "#1769aa" : "#ffffff",
                weight: z.affected ? 3 : 1,
                opacity: z.affected ? 1 : 0.55,
                fillColor: z.delta === null ? "#e5e7eb" : deltaColor(z.delta),
                fillOpacity: noData(z.quality) ? 1 : z.delta !== null && Math.abs(z.delta) < 0.05 ? 0.42 : 0.82,
                className: noData(z.quality) ? "zone-nodata" : undefined,
              }}
            >
              <Tooltip sticky>
                <strong>{z.label}</strong>
                <br />
                {noData(z.quality) ? "No value: cloud or no pass" : <>ΔNDVI {fmtDelta(z.delta)}</>}
                <br />
                {z.pixels} pixels
              </Tooltip>
            </Polygon>
          ))}
        </Pane>
        <Pane name="outline" style={{ zIndex: 500 }}>
          <Polyline positions={data.outline} pathOptions={{ color: "#ffffff", weight: 5, opacity: 0.95, interactive: false }} />
          <Polyline positions={data.outline} pathOptions={{ color: "#101c16", weight: 2.25, interactive: false }} />
          {grid &&
            data.grid.map((l, i) => (
              <Polyline key={i} positions={l} pathOptions={{ color: "#ffffff", weight: 0.8, opacity: 0.55, interactive: false }} />
            ))}
        </Pane>
      </MapContainer>

      <div className="map-overlay map-controls">
        <div className="seg" role="group" aria-label="Base map">
          <Layers size={14} aria-hidden />
          <button type="button" aria-pressed={base === "sat"} className={base === "sat" ? "on" : ""} onClick={() => setBase("sat")}>Satellite</button>
          <button type="button" aria-pressed={base === "street"} className={base === "street" ? "on" : ""} onClick={() => setBase("street")}>Street</button>
        </div>
        <button type="button" className={`toggle ${grid ? "on" : ""}`} aria-pressed={grid} onClick={() => setGrid((g) => !g)}>
          <Grid3x3 size={14} aria-hidden /> Show 10 m pixels
        </button>
      </div>

      <figcaption className="map-legend">
        <div className="legend-title">
          <span className="eyebrow">Change in NDVI</span>
          <span className="muted">
            {data.scene_date ? `${fmtDate(data.scene_date)} vs baseline ${data.baseline}` : "No clear scene"}
          </span>
        </div>
        <div className="legend-bins" role="list">
          {DELTA_BINS.map((b) => (
            <span key={b.label} role="listitem" title={b.label}>
              <i style={{ background: b.color }} />
              <small>{b.label}</small>
            </span>
          ))}
          <span role="listitem" title="No value">
            <i className="hatch" />
            <small>No value</small>
          </span>
        </div>
      </figcaption>
    </figure>
  );
}
