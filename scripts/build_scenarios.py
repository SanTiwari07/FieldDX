"""Build the simulated demo dataset.

Writes:
  data/fields.geojson           12 plots near Niphad, Nashik (illustrative positions)
  data/scenes/<field_id>.json   Sentinel-2-style zonal NDVI per scene, with SCL quality
  data/weather/niphad.json      daily rain, Tmax, humidity, soil moisture

Everything is SIMULATED and deterministic (fixed seed). It is shaped like the output of
the Earth Engine export described in IMPLEMENTATION_PLAN.md section 4.3, so the real export
can replace it without touching the backend. Nothing here is real imagery.

Run:  python scripts/build_scenarios.py
"""
from __future__ import annotations

import json
import math
import random
import statistics
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SEED = 2610
ORIGIN_LAT, ORIGIN_LON = 20.0780, 74.1100
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(ORIGIN_LAT))

SCENE_START = date(2026, 7, 7)
SCENE_COUNT = 20  # every 5 days, last one 2026-10-10
WEATHER_START = date(2026, 6, 15)
WEATHER_END = date(2026, 10, 12)

INTERIOR = ["in_nw", "in_ne", "in_sw", "in_se"]
EDGES = ["edge_n", "edge_e", "edge_s", "edge_w"]
RAW = ["raw_edge_n", "raw_edge_e", "raw_edge_s", "raw_edge_w"]
ALL_ZONES = INTERIOR + EDGES + RAW

# Share of the sky blocked per scene date, cluster-wide (monsoon tail, clearing from September)
CLOUD_BY_INDEX = [0.85, 0.60, 0.90, 0.35, 0.70, 0.95, 0.50, 0.15, 0.65, 0.10,
                  0.05, 0.40, 0.00, 0.08, 0.00, 0.10, 0.00, 0.05, 0.00, 0.00]

# id, crop, name, village, column, row, width m, height m, anchor date
FIELDS = [
    ("F01", "grape", "Plot 01", "Niphad", 0, 0, 210, 140, "2026-04-10"),
    ("F02", "grape", "Plot 02", "Niphad", 1, 0, 200, 130, "2026-04-12"),
    ("F03", "grape", "Plot 03", "Chandori", 2, 0, 220, 150, "2026-04-08"),
    ("F04", "grape", "Plot 04", "Chandori", 3, 0, 190, 140, "2026-04-14"),
    ("F05", "grape", "Plot 05", "Ozar", 0, 1, 205, 135, "2026-04-11"),
    ("F06", "grape", "Plot 06", "Ozar", 1, 1, 215, 145, "2026-04-15"),
    ("F07", "onion", "Plot 07", "Pimpalgaon", 2, 1, 200, 130, "2026-07-10"),
    ("F08", "onion", "Plot 08", "Pimpalgaon", 3, 1, 210, 140, "2026-07-12"),
    ("F09", "onion", "Plot 09", "Lasalgaon", 0, 2, 200, 135, "2026-07-09"),
    ("F10", "onion", "Plot 10", "Lasalgaon", 1, 2, 195, 130, "2026-07-11"),
    ("F12", "onion", "Plot 12", "Ozar", 2, 2, 205, 140, "2026-07-10"),
    ("F11", "onion", "Plot 11", "Ozar", 3, 2, 200, 135, "2026-07-13"),
]
COL_X = [0, 270, 540, 810]
ROW_Y = [0, 200, 400]

# Where each plot's edges meet something that can mix pixels. Default is another crop plot.
EDGE_CONTEXT_OVERRIDES = {
    "F11": {"e": ("bare_plot", "recently harvested plot (bare soil)")},
    "F01": {"w": ("road", "village road")},
    "F05": {"w": ("road", "village road")},
    "F09": {"w": ("bund", "field bund")},
    "F07": {"n": ("field", "neighbouring grape plot")},
}

CALENDAR = json.loads((DATA / "calendar.json").read_text(encoding="utf-8"))["crops"]


# ----------------------------------------------------------------- geometry

def to_lonlat(x: float, y: float, w: float, h: float, ox: float, oy: float) -> list[float]:
    lat = ORIGIN_LAT + (oy + y) / M_PER_DEG_LAT
    lon = ORIGIN_LON + (ox + x) / M_PER_DEG_LON
    return [round(lon, 7), round(lat, 7)]


def ring(points, w, h, ox, oy):
    pts = [to_lonlat(x, y, w, h, ox, oy) for x, y in points]
    pts.append(pts[0])
    return pts


def poly_area(points):
    s = 0.0
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def band(w, h, outer, inner):
    """Four mitred trapezoids between an outer inset and an inner inset (metres)."""
    ox0, ox1, oy0, oy1 = outer, w - outer, outer, h - outer
    ix0, ix1, iy0, iy1 = inner, w - inner, inner, h - inner
    return {
        "n": [(ox0, oy1), (ox1, oy1), (ix1, iy1), (ix0, iy1)],
        "e": [(ox1, oy1), (ox1, oy0), (ix1, iy0), (ix1, iy1)],
        "s": [(ox1, oy0), (ox0, oy0), (ix0, iy0), (ix1, iy0)],
        "w": [(ox0, oy0), (ox0, oy1), (ix0, iy1), (ix0, iy0)],
    }


def build_zones(w, h):
    """Zone polygons in local metres. Analysis area is inset 10 m; the ring is 20 m wide."""
    zones: dict[str, list[tuple[float, float]]] = {}
    for side, pts in band(w, h, 10, 30).items():
        zones[f"edge_{side}"] = pts
    for side, pts in band(w, h, 0, 20).items():
        zones[f"raw_edge_{side}"] = pts
    cx, cy = w / 2, h / 2
    ix0, ix1, iy0, iy1 = 30, w - 30, 30, h - 30
    zones["in_nw"] = [(ix0, cy), (cx, cy), (cx, iy1), (ix0, iy1)]
    zones["in_ne"] = [(cx, cy), (ix1, cy), (ix1, iy1), (cx, iy1)]
    zones["in_sw"] = [(ix0, iy0), (cx, iy0), (cx, cy), (ix0, cy)]
    zones["in_se"] = [(cx, iy0), (ix1, iy0), (ix1, cy), (cx, cy)]
    return zones


# ----------------------------------------------------------------- crop truth

def expected_ndvi(crop: str, anchor: date, day: date) -> float:
    curve = CALENDAR[crop]["curve"]
    d = (day - anchor).days
    if d <= curve[0][0]:
        return curve[0][1]
    for (d0, v0), (d1, v1) in zip(curve, curve[1:]):
        if d <= d1:
            return v0 + (v1 - v0) * (d - d0) / (d1 - d0)
    return curve[-1][1]


# ----------------------------------------------------------------- scenarios
# Additive NDVI change per zone and scene date. Scene dates are ISO strings.

def uniform(deltas: dict[str, float], jitter: float = 0.008, seed: int = 0):
    """Same change on every analysis and raw zone, with a little per-zone spread."""
    rng = random.Random(seed)
    spread = {z: rng.uniform(-jitter, jitter) for z in ALL_ZONES}
    return {z: {d: v + spread[z] for d, v in deltas.items()} for z in ALL_ZONES}


def edge_with_raw(edge: str, deltas: dict[str, float], raw_scale: float = 1.08):
    side = edge.split("_")[1]
    return {
        f"edge_{side}": deltas,
        f"raw_edge_{side}": {d: v * raw_scale for d, v in deltas.items()},
    }


def merge(*parts):
    out: dict[str, dict[str, float]] = {}
    for part in parts:
        for zone, series in part.items():
            out.setdefault(zone, {}).update(series)
    return out


EVENTS: dict[str, dict[str, dict[str, float]]] = {
    # C1: irrigation failure on the east edge, creeping a little into the nearby interior
    "F07": merge(
        edge_with_raw("edge_e", {"2026-09-25": -0.065, "2026-09-30": -0.125, "2026-10-05": -0.18, "2026-10-10": -0.225}),
        {"in_ne": {"2026-10-10": -0.03}, "in_se": {"2026-10-10": -0.03}},
    ),
    # C4: a patch in the north-west that spreads across scenes
    "F09": {
        "in_nw": {"2026-09-25": -0.05, "2026-09-30": -0.115, "2026-10-05": -0.15, "2026-10-10": -0.17},
        "in_ne": {"2026-10-05": -0.095, "2026-10-10": -0.14},
        "in_sw": {"2026-10-10": -0.095},
    },
    # C2: haze on the 5 Oct scene lowers every zone, gone by 10 Oct
    "F10": uniform({"2026-10-05": -0.22}, jitter=0.01, seed=11),
    # C5: only the unshrunk east edge drops: mixed pixels beside a harvested plot
    "F11": {"raw_edge_e": {"2026-10-05": -0.21, "2026-10-10": -0.25}, "edge_e": {"2026-10-05": -0.02, "2026-10-10": -0.025}},
    # C6: a confirmed drop in two diagonal interior quadrants that matches no pattern
    "F12": {
        "in_ne": {"2026-10-05": -0.13, "2026-10-10": -0.14},
        "in_sw": {"2026-10-05": -0.12, "2026-10-10": -0.13},
    },
}
# Grape fruit pruning: sudden, uniform leaf loss. Plots are pruned on different days.
for fid, deltas, seed in [
    ("F01", {"2026-10-05": -0.20, "2026-10-10": -0.34}, 21),
    ("F02", {"2026-10-05": -0.20, "2026-10-10": -0.34}, 22),
    ("F03", {"2026-10-05": -0.19, "2026-10-10": -0.33}, 23),
    ("F04", {"2026-10-10": -0.22}, 24),
    ("F05", {"2026-10-10": -0.22}, 25),
]:
    EVENTS[fid] = uniform(deltas, jitter=0.008, seed=seed)

# A scene that is partly hazy for one field regardless of the cluster-wide cloud level
FORCED_VALID = {("F10", "2026-10-05"): 0.62}
# Passes missing for a field (no image)
MISSING_PASSES = {("F03", "2026-09-20"), ("F11", "2026-09-10"), ("F05", "2026-08-31")}
# Dates that must stay clean so the scenario outcome is not decided by chance
CLEAN_FROM = "2026-09-05"


def quality_class(valid: float) -> str:
    if valid >= 0.8:
        return "usable"
    if valid >= 0.5:
        return "partial"
    return "cloudy"


# ----------------------------------------------------------------- build

def build_fields_and_scenes():
    rng = random.Random(SEED)
    features = []
    scene_dates = [SCENE_START + timedelta(days=5 * i) for i in range(SCENE_COUNT)]

    for fid, crop, name, village, col, row, w, h, anchor_s in FIELDS:
        ox, oy = COL_X[col], ROW_Y[row]
        zones_m = build_zones(w, h)
        pixels = {z: max(1, round(poly_area(p) / 100)) for z, p in zones_m.items()}
        analysis_pixels = sum(pixels[z] for z in INTERIOR + EDGES)

        context = {s: {"kind": "field", "label": "neighbouring plot"} for s in "nesw"}
        for side, (kind, label) in EDGE_CONTEXT_OVERRIDES.get(fid, {}).items():
            context[side] = {"kind": kind, "label": label}

        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring([(0, 0), (w, 0), (w, h), (0, h)], w, h, ox, oy)]},
            "properties": {
                "id": fid,
                "name": f"{name} · {village}",
                "village": village,
                "crop": crop,
                "anchor_date": anchor_s,
                "anchor_label": CALENDAR[crop]["anchor_label"],
                "anchor_assumed": True,
                "cluster": "niphad",
                "size_m": [w, h],
                "origin_m": [ox, oy],
                "area_ha": round(w * h / 10_000, 2),
                "analysis_pixels": analysis_pixels,
                "edge_context": context,
                "zones": {
                    z: {"pixels": pixels[z], "polygon": [ring(zones_m[z], w, h, ox, oy)]}
                    for z in ALL_ZONES
                },
            },
        })

        anchor = date.fromisoformat(anchor_s)
        field_offset = rng.uniform(-0.025, 0.025)
        zone_offset = {z: rng.uniform(-0.01, 0.01) for z in ALL_ZONES}
        for z in EDGES:
            zone_offset[z] -= 0.015
        for z in RAW:
            zone_offset[z] -= 0.045  # mixed boundary pixels sit lower

        scenes = []
        for idx, d in enumerate(scene_dates):
            iso = d.isoformat()
            if (fid, iso) in MISSING_PASSES:
                continue
            cloud = CLOUD_BY_INDEX[idx]
            field_valid = max(0.0, min(1.0, 1 - cloud * rng.uniform(0.7, 1.15)))
            if iso >= CLEAN_FROM:
                field_valid = max(field_valid, 0.9)
            field_valid = FORCED_VALID.get((fid, iso), field_valid)
            invalid = 1 - field_valid

            scene_zones = {}
            for z in ALL_ZONES:
                valid = max(0.0, min(1.0, field_valid + rng.uniform(-0.04, 0.04)))
                if iso >= CLEAN_FROM and (fid, iso) not in FORCED_VALID:
                    valid = max(valid, 0.85)
                truth = expected_ndvi(crop, anchor, d) + field_offset + zone_offset[z]
                delta = EVENTS.get(fid, {}).get(z, {}).get(iso, 0.0)
                q = quality_class(valid)
                if q == "usable":
                    noise = rng.gauss(0, 0.006)
                    ndvi = truth + delta + noise
                elif q == "partial":
                    haze = -0.05 * (1 - valid) / 0.5
                    # an explicit event on a partial scene already carries its own haze
                    ndvi = truth + delta + (0 if delta else haze) + rng.gauss(0, 0.02)
                else:
                    ndvi = truth + delta - rng.uniform(0.12, 0.40) + rng.gauss(0, 0.05)
                scene_zones[z] = {
                    "ndvi": round(max(0.02, min(0.95, ndvi)), 3),
                    "valid_fraction": round(valid, 2),
                    "pixels": pixels[z],
                }
            scenes.append({
                "date": iso,
                "scene_id": f"SIM-{d:%Y%m%d}",
                "cloud_pct": round(invalid * 75),
                "shadow_pct": round(invalid * 15),
                "cirrus_pct": round(invalid * 10),
                "zones": scene_zones,
            })

        out = {"field_id": fid, "synthetic": True, "scenes": scenes}
        (DATA / "scenes" / f"{fid}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    fc = {"type": "FeatureCollection", "synthetic": True, "features": features}
    (DATA / "fields.geojson").write_text(json.dumps(fc), encoding="utf-8")
    return len(features), SCENE_COUNT


def build_weather():
    rng = random.Random(SEED + 1)
    days = []
    wetness = 1.0
    d = WEATHER_START
    special_rain = {
        date(2026, 9, 16): 9.0, date(2026, 9, 17): 14.0, date(2026, 9, 18): 10.0,
        date(2026, 9, 19): 5.0, date(2026, 9, 28): 7.0,
    }
    while d <= WEATHER_END:
        if d in special_rain:
            rain = special_rain[d]
        elif d >= date(2026, 9, 20):
            rain = 0.0
        elif d.month in (6, 7, 8):
            rain = round(rng.uniform(2, 22), 1) if rng.random() < 0.55 else 0.0
        else:
            rain = round(rng.uniform(1, 6), 1) if rng.random() < 0.3 else 0.0

        if date(2026, 9, 16) <= d <= date(2026, 9, 24):
            rh = rng.uniform(87, 93)
        elif rain > 0:
            rh = rng.uniform(72, 86)
        else:
            rh = rng.uniform(48, 66) if d >= date(2026, 9, 25) else rng.uniform(60, 78)

        tmax = {6: 33, 7: 29.5, 8: 29, 9: 31, 10: 33}[d.month] + rng.uniform(-1.5, 1.5)
        wetness = wetness * 0.93 + rain / 30
        sm = 0.255 + 0.045 * wetness / (wetness + 1.5) + rng.uniform(-0.002, 0.002)
        days.append({
            "date": d.isoformat(), "rain_mm": rain, "tmax_c": round(tmax, 1),
            "rh_mean": round(rh, 0), "soil_moisture": round(sm, 3),
        })
        d += timedelta(days=1)

    out = {
        "cluster": "niphad", "lat": ORIGIN_LAT, "lon": ORIGIN_LON, "synthetic": True,
        "source": "Simulated daily weather shaped like an Open-Meteo archive pull",
        "days": days,
    }
    (DATA / "weather" / "niphad.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    sm = [x["soil_moisture"] for x in days]
    last7, win60 = sm[-9:-2], sm[-62:-2]
    anomaly = statistics.mean(last7) - statistics.mean(win60)
    return len(days), round(anomaly, 3)


if __name__ == "__main__":
    (DATA / "scenes").mkdir(parents=True, exist_ok=True)
    (DATA / "weather").mkdir(parents=True, exist_ok=True)
    n_fields, n_scenes = build_fields_and_scenes()
    n_days, z = build_weather()
    print(f"fields={n_fields} scenes/field<={n_scenes} weather_days={n_days} soil_moisture_anomaly(7d vs 60d)={z}")
