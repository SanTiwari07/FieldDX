"""The real 10 m pixels of one field and one scene, ready to paint on the map.

NDVI comes straight from the masked Sentinel-2 pixels. Change is each pixel's NDVI minus that same
pixel's median over the baseline scenes, so a field's own texture (rows, soil patches) cancels out and
only what moved is left. A cloudy scene is masked whole and never carries a number.
"""
from __future__ import annotations

import warnings
from datetime import date

import numpy as np

from . import data
from .data import ANALYSIS, FieldRec
from .tools.common import Series

OUTSIDE, VALID, MASKED = 0, 1, 2


def _full(g: data.Grid, flat: np.ndarray) -> np.ndarray:
    out = np.full(g.nr * g.nc, np.nan)
    out[g.cells] = flat
    return out.reshape(g.nr, g.nc)


def _lists(a: np.ndarray, ndigits: int) -> list:
    return [[None if np.isnan(v) else round(float(v), ndigits) for v in row] for row in a]


def raster(field: FieldRec, series: Series, day: date) -> dict | None:
    scene = series.scene_at(day)
    if scene is None:
        return None
    g = data.grid(field.area, field.id)
    cls = series.scene_class(scene)
    ndvi = _full(g, scene.px)
    base = None
    if series.baseline_scenes:
        stack = np.stack([_full(g, s.px) for s in series.baseline_scenes])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # pixels masked in every baseline scene
            base = np.nanmedian(stack, axis=0)
    delta = ndvi - base if base is not None else np.full_like(ndvi, np.nan)

    if cls == "cloudy":
        ndvi = np.full_like(ndvi, np.nan)
        delta = np.full_like(ndvi, np.nan)

    mask = np.where(~g.inside, OUTSIDE, np.where(np.isnan(ndvi), MASKED, VALID))
    valid = ndvi[mask == VALID]
    stats = None
    if valid.size and cls != "cloudy":
        stats = {"mean": round(float(valid.mean()), 3), "p10": round(float(np.percentile(valid, 10)), 3),
                 "p90": round(float(np.percentile(valid, 90)), 3)}
    zone_names = np.where(g.az >= 0, np.array(ANALYSIS)[np.clip(g.az, 0, 7)], "")
    return {
        "date": day.isoformat(), "w": g.nc, "h": g.nr, "pixel_m": data.CELL_M, "bounds": g.bounds_lonlat(),
        "quality": cls, "visible": round(float(valid.size / max(1, g.inside.sum())), 2) if cls != "cloudy" else 0.0,
        "ndvi": _lists(ndvi, 3), "delta": _lists(delta, 3), "mask": mask.tolist(), "stats": stats,
        "zones": zone_names.tolist(),
    }
