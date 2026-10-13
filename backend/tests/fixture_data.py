"""A tiny hand-made dataset in the exact file format the real pipeline writes.

It exists only so the engine's logic can be tested with known answers (an edge drop, a hazy scene, a
boundary artefact...). The product itself never reads it: it is built as an area called "fixture" in a
temp folder and the loader is pointed there for the duration of a test.
"""
from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path

from app import config

ROOT = Path(config.ROOT)
NR, NC = 14, 20
ZONES = ["in_nw", "in_ne", "in_sw", "in_se", "edge_n", "edge_e", "edge_s", "edge_w"]
RAWZ = ["raw_edge_n", "raw_edge_e", "raw_edge_s", "raw_edge_w"]
AREA = "fixture"
START = date(2026, 8, 1)
END = date(2026, 10, 10)


def side_of(r: int, c: int) -> str:
    """Nearest border: n (top), s, w, e."""
    d = {"n": r, "s": NR - 1 - r, "w": c, "e": NC - 1 - c}
    return min(d, key=d.get)


def zones_for(r: int, c: int) -> tuple[int, int]:
    d = min(r, NR - 1 - r, c, NC - 1 - c)
    az = rz = -1
    if d >= 3:
        az = ZONES.index("in_" + ("n" if r < NR / 2 else "s") + ("w" if c < NC / 2 else "e"))
    elif d >= 1:
        az = ZONES.index("edge_" + side_of(r, c))
    if d < 2:
        rz = RAWZ.index("raw_edge_" + side_of(r, c))
    return az, rz


def dates(every=5):
    d = START
    while d <= END:
        yield d
        d += timedelta(days=every)


def ring(lon0, lat0, w=0.0020, h=0.0015):
    return [[lon0, lat0], [lon0 + w, lat0], [lon0 + w, lat0 + h], [lon0, lat0 + h], [lon0, lat0]]


def build(root: Path, fields: dict[str, dict], weather: dict | None = None, cases: list | None = None) -> Path:
    """fields: id -> {class, lon, ev(date, r, c) -> delta or None to mask, skip(date) -> bool}"""
    real = Path(config.ROOT) / "data"
    tmp = root / "areas" / AREA
    for sub in ("grids", "scenes"):
        (tmp / sub).mkdir(parents=True, exist_ok=True)
    shutil.copy(real / "checks.json", root / "checks.json")
    shutil.copy(real / "areas" / "niphad" / "calendar.json", tmp / "calendar.json")
    (tmp / "area.json").write_text(json.dumps({"id": AREA, "name": "Fixture", "region": "test", "status": "ready"}),
                                   encoding="utf-8")

    feats = []
    for k, (fid, spec) in enumerate(fields.items()):
        lon0, lat0 = spec.get("lon", 74.10 + 0.0025 * k), spec.get("lat", 20.07)
        cells = [(r, c) for r in range(NR) for c in range(NC)]
        az = [zones_for(r, c)[0] for r, c in cells]
        rz = [zones_for(r, c)[1] for r, c in cells]
        counts = {z: az.count(i) for i, z in enumerate(ZONES)}
        counts.update({z: rz.count(i) for i, z in enumerate(RAWZ)})
        zp = {z: {"type": "Polygon", "coordinates": [ring(lon0, lat0)]} for z in ZONES}
        feats.append({
            "type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring(lon0, lat0)]},
            "properties": {
                "id": fid, "name": f"Fixture {fid}", "area_ha": 2.0, "compactness": 0.8, "cropland_fraction": 1.0,
                "class": spec.get("class", "seasonal"), "ndvi_monthly": {}, "centroid": [lon0 + 0.001, lat0 + 0.00075],
                "zone_pixels": counts, "zones": zp,
            },
        })
        (tmp / "grids" / f"{fid}.json").write_text(json.dumps({
            "epsg": "EPSG:32643", "x0": 400000 + k * 300, "y_top": 2220000, "cell_m": 10, "r0": 0, "c0": 0,
            "nr": NR, "nc": NC, "inside": [1] * (NR * NC), "az": az, "rz": rz,
        }), encoding="utf-8")

        scenes = []
        for d in dates():
            if spec.get("skip") and spec["skip"](d):
                continue
            ev = spec.get("ev", lambda d, r, c: 0.0)
            px = []
            masked = 0
            for r, c in cells:
                delta = ev(d, r, c)
                if delta is None:
                    px.append(None)
                    masked += 1
                else:
                    jitter = (((r * 7 + c * 13 + k) % 11) - 5) * 0.002
                    px.append(round((spec.get("base", 0.75) + jitter + delta) * 1000))
            cloud = round(100 * masked / len(cells))
            scenes.append({"date": d.isoformat(), "scene_id": f"FIX-{d:%Y%m%d}", "cloud_pct": cloud,
                           "shadow_pct": 0, "cirrus_pct": 0, "ndvi": px})
        (tmp / "scenes" / f"{fid}.json").write_text(json.dumps({"field_id": fid, "scenes": scenes}), encoding="utf-8")

    (tmp / "fields.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "provenance": {"imagery": "test fixture", "boundaries": "test fixture"},
        "features": feats,
    }), encoding="utf-8")

    w = weather or {}
    days = []
    d = date(2026, 6, 1)
    while d <= date(2026, 10, 12):
        rain = w.get("rain", lambda d: 0.0)(d)
        days.append({"date": d.isoformat(), "rain_mm": rain, "tmax_c": 31.0, "rh_mean": w.get("rh", lambda d: 55)(d),
                     "soil_moisture": w.get("soil", lambda d: 0.28)(d)})
        d += timedelta(days=1)
    (tmp / "weather.json").write_text(json.dumps({"source": "test fixture", "days": days}), encoding="utf-8")

    (tmp / "cases.json").write_text(json.dumps({
        "as_of": END.isoformat(), "banner": "Test fixture data.",
        "cases": cases if cases is not None else [{"id": f, "field_id": f, "alert_date": END.isoformat()} for f in fields],
    }), encoding="utf-8")
    return tmp
