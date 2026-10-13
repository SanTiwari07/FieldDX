"""A 10 m pixel raster for one field and scene, derived from the zone values.

The cached data is zonal (eight zones plus the unshrunk edge rings). The map wants pixels, so each
10 m cell takes its zone's value plus smooth, deterministic texture. The texture is the same on every
date for a given pixel (so a pixel's change against its own baseline shows only the event), with a
little per-date noise on top. Cloud and haze are masked as soft blobs sized to the scene's valid
fraction, and a cloudy scene is masked whole. Nothing here is real imagery; a real build would read
the pixels from the export instead.
"""
from __future__ import annotations

import math
import random
import zlib
from datetime import date
from functools import lru_cache

from . import data
from .data import ANALYSIS, RAW, FieldRec
from .tools.common import Series, quality_of

PIXEL_M = 10


def _inside(poly: list[list[float]], x: float, y: float) -> bool:
    ins = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-18) + xi:
            ins = not ins
        j = i
    return ins


@lru_cache(maxsize=None)
def _layout(field_id: str) -> dict:
    f = data.fields()[field_id]
    w, h = f.size_m
    nx, ny = max(1, round(w / PIXEL_M)), max(1, round(h / PIXEL_M))
    ring = f.outline[0]
    sw, se, nw = ring[0], ring[1], ring[3]
    zones: list[list[str]] = []
    for r in range(ny):  # r = 0 is the north row
        j = ny - 1 - r
        row = []
        for i in range(nx):
            lon = sw[0] + (se[0] - sw[0]) * (i + 0.5) / nx
            lat = sw[1] + (nw[1] - sw[1]) * (j + 0.5) / ny
            z = next((z for z in ANALYSIS if _inside(f.zone_polygons[z][0], lon, lat)), None)
            if z is None:
                z = next((z for z in RAW if _inside(f.zone_polygons[z][0], lon, lat)), "in_nw")
            row.append(z)
        zones.append(row)
    bounds = [[min(sw[1], nw[1]), min(sw[0], se[0])], [max(sw[1], nw[1]), max(sw[0], se[0])]]
    return {"nx": nx, "ny": ny, "zones": zones, "bounds": bounds}


def _field(seed: str, terms: int = 4):
    rng = random.Random(seed)
    parts = [(rng.uniform(0.18, 0.55), rng.uniform(0.18, 0.55), rng.uniform(0, 6.28), rng.uniform(0.6, 1.0)) for _ in range(terms)]
    norm = sum(p[3] for p in parts)

    def f(x: float, y: float) -> float:
        return sum(a * math.sin(fx * x + fy * y + ph) for fx, fy, ph, a in parts) / norm

    return f


def _jitter(*key) -> float:
    return zlib.crc32("|".join(map(str, key)).encode()) / 2**32 - 0.5


def raster(field: FieldRec, series: Series, day: date) -> dict | None:
    scene = series.scene_at(day)
    if scene is None:
        return None
    lay = _layout(field.id)
    nx, ny = lay["nx"], lay["ny"]
    cls = series.scene_class(scene)
    valid = series.scene_valid(scene)

    texture = _field(f"{field.id}:texture")
    rows_t = _field(f"{field.id}:rows", terms=2)
    clouds = _field(f"{field.id}:{day.isoformat()}:cloud", terms=5)

    cells = []
    for r in range(ny):
        for i in range(nx):
            z = lay["zones"][r][i]
            base_n = scene.zones[z].ndvi
            static = 0.042 * texture(i, r) + 0.018 * rows_t(i * 1.7, r * 0.3)
            temporal = 0.016 * _jitter(field.id, day, i, r)
            cells.append((r, i, z, base_n + static + temporal, series.baseline.get(z, base_n) + static, clouds(i, r)))

    masked: set[tuple[int, int]] = set()
    if cls == "cloudy":
        masked = {(c[0], c[1]) for c in cells}
    else:
        share = 1 - valid
        if share >= 0.04:
            ordered = sorted(cells, key=lambda c: -c[5])
            masked = {(c[0], c[1]) for c in ordered[: round(share * len(cells))]}

    ndvi = [[None] * nx for _ in range(ny)]
    delta = [[None] * nx for _ in range(ny)]
    mask = [[0] * nx for _ in range(ny)]
    visible = []
    for r, i, z, v, b, _c in cells:
        if (r, i) in masked:
            mask[r][i] = 1
            continue
        ndvi[r][i] = round(max(0.0, min(0.95, v)), 3)
        delta[r][i] = round(v - b, 3)
        visible.append(ndvi[r][i])

    stats = None
    if visible and cls != "cloudy":
        s = sorted(visible)
        pick = lambda p: s[min(len(s) - 1, int(p * (len(s) - 1)))]
        stats = {"mean": round(sum(s) / len(s), 3), "p10": pick(0.1), "p90": pick(0.9)}
    return {
        "date": day.isoformat(), "w": nx, "h": ny, "pixel_m": PIXEL_M, "bounds": lay["bounds"],
        "quality": cls, "visible": round(len(visible) / (nx * ny), 2) if cls != "cloudy" else 0.0,
        "ndvi": ndvi, "delta": delta, "mask": mask, "stats": stats,
        "zones": lay["zones"],
    }
