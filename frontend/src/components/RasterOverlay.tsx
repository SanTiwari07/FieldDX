import { useMemo, useRef } from "react";
import { ImageOverlay, useMapEvents } from "react-leaflet";
import type { RasterData } from "../api";
import { deltaColorOf, MASK_FILL, Mode, ndviColor } from "../lib/ramps";

const CELL = 18; // canvas pixels per 10 m pixel; the browser scales it, `pixelated` keeps edges crisp

export function paintRaster(r: RasterData, mode: Mode, grid: boolean, cell = CELL): string {
  const c = document.createElement("canvas");
  c.width = r.w * cell;
  c.height = r.h * cell;
  const g = c.getContext("2d")!;
  for (let y = 0; y < r.h; y++) {
    for (let x = 0; x < r.w; x++) {
      const masked = r.mask[y][x] === 1;
      const v = mode === "change" ? r.delta[y][x] : r.ndvi[y][x];
      if (masked || v === null) {
        g.fillStyle = MASK_FILL;
        g.fillRect(x * cell, y * cell, cell, cell);
        g.strokeStyle = "#9aa0a6";
        g.lineWidth = Math.max(1, cell / 9);
        g.beginPath();
        g.moveTo(x * cell, y * cell + cell);
        g.lineTo(x * cell + cell, y * cell);
        g.stroke();
      } else {
        g.fillStyle = mode === "change" ? deltaColorOf(v) : ndviColor(v);
        g.fillRect(x * cell, y * cell, cell, cell);
      }
    }
  }
  if (grid) {
    g.strokeStyle = "rgba(255,255,255,0.55)";
    g.lineWidth = 1;
    g.beginPath();
    for (let x = 0; x <= r.w; x++) { g.moveTo(x * cell + 0.5, 0); g.lineTo(x * cell + 0.5, c.height); }
    for (let y = 0; y <= r.h; y++) { g.moveTo(0, y * cell + 0.5); g.lineTo(c.width, y * cell + 0.5); }
    g.stroke();
  }
  return c.toDataURL("image/png");
}

export interface Hover {
  x: number;
  y: number;
  ndvi: number | null;
  delta: number | null;
  masked: boolean;
}

/** Reports which 10 m pixel the pointer is over. */
function Probe({ r, onHover }: { r: RasterData; onHover: (h: Hover | null) => void }) {
  const last = useRef("");
  const [[s, w], [n, e]] = r.bounds;
  useMapEvents({
    mousemove(ev) {
      const { lat, lng } = ev.latlng;
      const x = Math.floor(((lng - w) / (e - w)) * r.w);
      const y = Math.floor(((n - lat) / (n - s)) * r.h);
      const key = `${x},${y}`;
      if (key === last.current) return;
      last.current = key;
      if (x < 0 || y < 0 || x >= r.w || y >= r.h) return onHover(null);
      onHover({ x, y, ndvi: r.ndvi[y][x], delta: r.delta[y][x], masked: r.mask[y][x] === 1 });
    },
    mouseout() {
      last.current = "";
      onHover(null);
    },
  });
  return null;
}

export function RasterOverlay({
  raster, mode, grid, onHover,
}: {
  raster: RasterData;
  mode: Mode;
  grid: boolean;
  onHover?: (h: Hover | null) => void;
}) {
  const url = useMemo(() => (mode === "satellite" ? "" : paintRaster(raster, mode, grid)), [raster, mode, grid]);
  return (
    <>
      {url && <ImageOverlay url={url} bounds={raster.bounds} opacity={0.88} className="pixel-overlay" zIndex={420} />}
      {onHover && <Probe r={raster} onHover={onHover} />}
    </>
  );
}
