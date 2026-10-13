import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";
import type { RasterData } from "../api";
import { fmtDelta } from "../lib/format";
import { DELTA_BINS } from "../lib/format";
import { legendFor, MODE_LABEL, Mode, NDVI_BINS } from "../lib/ramps";
import type { Hover } from "./RasterOverlay";

/** Floating legend. It always describes exactly what the pixels were painted with. */
export function Legend({
  mode, raster, hover,
}: {
  mode: Mode;
  raster: RasterData | null;
  hover: Hover | null;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  if (mode === "satellite") return null;
  const lg = legendFor(mode);
  const s = raster?.stats;

  return (
    <div className="legend">
      <button type="button" className="legend-head" aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)}>
        <span>
          <strong>{mode === "ndvi" ? "NDVI" : "Change in NDVI"}</strong>
          <small>{mode === "ndvi" ? "Greenness, 0 to 1" : "Against the field's own baseline"}</small>
        </span>
        <ChevronDown size={16} aria-hidden className={open ? "up" : ""} />
      </button>
      <div className="legend-scale">
        <div className="legend-bar" style={{ background: lg.gradient }} aria-hidden />
        <div className="legend-ends"><span>{lg.min}</span><span>{lg.mid}</span><span>{lg.max}</span></div>
      </div>
      <div id={id} hidden={!open} className="legend-body">
        <ul className="legend-bins">
          {mode === "ndvi"
            ? NDVI_BINS.map((b) => (
                <li key={b.label}>
                  <i style={{ background: b.color }} />
                  <span>{b.label}</span>
                  <small>{b.max === null ? `≥ ${b.min}` : `${b.min} to ${b.max}`}</small>
                </li>
              ))
            : DELTA_BINS.slice(0, 6).filter((_, i) => i !== 3).map((b) => (
                <li key={b.label}>
                  <i style={{ background: b.color }} />
                  <span>{b.label}</span>
                </li>
              ))}
          <li><i className="hatch" /><span>No value</span><small>cloud or haze</small></li>
        </ul>
        {raster && (
          <p className="legend-sum">
            {s ? (
              <>Mean {s.mean.toFixed(2)}, middle 80% {s.p10.toFixed(2)} to {s.p90.toFixed(2)}. </>
            ) : (
              <>No value: this pass is cloudy. </>
            )}
            {Math.round(raster.visible * 100)}% of pixels visible.
          </p>
        )}
        <p className="legend-hover" aria-live="off">
          {hover
            ? hover.masked || hover.ndvi === null
              ? "Pixel under the pointer: no value"
              : <>Pixel: NDVI {hover.ndvi.toFixed(2)}, change {fmtDelta(hover.delta)}</>
            : `Move over the field to read a 10 m pixel (${MODE_LABEL[mode]} view)`}
        </p>
      </div>
    </div>
  );
}
