"""Load the cached JSON (fields, scenes, weather, calendar, checks, scenarios)."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from . import config

INTERIOR = ["in_nw", "in_ne", "in_sw", "in_se"]
EDGES = ["edge_n", "edge_e", "edge_s", "edge_w"]
ANALYSIS = INTERIOR + EDGES
RAW = ["raw_edge_n", "raw_edge_e", "raw_edge_s", "raw_edge_w"]
ALL_ZONES = ANALYSIS + RAW

ZONE_LABEL = {
    "in_nw": "North-west interior", "in_ne": "North-east interior",
    "in_sw": "South-west interior", "in_se": "South-east interior",
    "edge_n": "North edge", "edge_e": "East edge", "edge_s": "South edge", "edge_w": "West edge",
    "raw_edge_n": "North edge (unshrunk)", "raw_edge_e": "East edge (unshrunk)",
    "raw_edge_s": "South edge (unshrunk)", "raw_edge_w": "West edge (unshrunk)",
}
SIDE_NAME = {"n": "north", "e": "east", "s": "south", "w": "west"}


@dataclass(frozen=True)
class ZoneObs:
    ndvi: float
    valid: float
    pixels: int


@dataclass(frozen=True)
class Scene:
    date: date
    scene_id: str
    cloud_pct: int
    shadow_pct: int
    cirrus_pct: int
    zones: dict[str, ZoneObs]


@dataclass(frozen=True)
class FieldRec:
    id: str
    name: str
    village: str
    crop: str
    anchor_date: date
    anchor_label: str
    anchor_assumed: bool
    area_ha: float
    analysis_pixels: int
    size_m: tuple[int, int]
    origin_m: tuple[int, int]
    edge_context: dict[str, dict]
    zone_pixels: dict[str, int]
    zone_polygons: dict[str, list]
    outline: list
    lat: float
    lon: float


@dataclass(frozen=True)
class WeatherDay:
    date: date
    rain_mm: float
    tmax_c: float
    rh_mean: float
    soil_moisture: float


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def fields() -> dict[str, FieldRec]:
    raw = _read(config.DATA_DIR / "fields.geojson")
    out: dict[str, FieldRec] = {}
    for feat in raw["features"]:
        p = feat["properties"]
        ring = feat["geometry"]["coordinates"][0]
        lon = sum(c[0] for c in ring[:-1]) / (len(ring) - 1)
        lat = sum(c[1] for c in ring[:-1]) / (len(ring) - 1)
        out[p["id"]] = FieldRec(
            id=p["id"], name=p["name"], village=p["village"], crop=p["crop"],
            anchor_date=date.fromisoformat(p["anchor_date"]), anchor_label=p["anchor_label"],
            anchor_assumed=p["anchor_assumed"], area_ha=p["area_ha"],
            analysis_pixels=p["analysis_pixels"], size_m=tuple(p["size_m"]),
            origin_m=tuple(p["origin_m"]), edge_context=p["edge_context"],
            zone_pixels={z: v["pixels"] for z, v in p["zones"].items()},
            zone_polygons={z: v["polygon"] for z, v in p["zones"].items()},
            outline=feat["geometry"]["coordinates"], lat=lat, lon=lon,
        )
    return out


@lru_cache(maxsize=None)
def scenes(field_id: str) -> tuple[Scene, ...]:
    raw = _read(config.DATA_DIR / "scenes" / f"{field_id}.json")
    out = []
    for s in raw["scenes"]:
        zones = {
            z: ZoneObs(ndvi=v["ndvi"], valid=v["valid_fraction"], pixels=v["pixels"])
            for z, v in s["zones"].items()
        }
        out.append(Scene(
            date=date.fromisoformat(s["date"]), scene_id=s["scene_id"],
            cloud_pct=s.get("cloud_pct", 0), shadow_pct=s.get("shadow_pct", 0),
            cirrus_pct=s.get("cirrus_pct", 0), zones=zones,
        ))
    return tuple(sorted(out, key=lambda x: x.date))


@lru_cache(maxsize=1)
def weather() -> tuple[WeatherDay, ...]:
    raw = _read(config.DATA_DIR / "weather" / "niphad.json")
    return tuple(
        WeatherDay(date.fromisoformat(d["date"]), d["rain_mm"], d["tmax_c"], d["rh_mean"], d["soil_moisture"])
        for d in raw["days"]
    )


@lru_cache(maxsize=1)
def weather_meta() -> dict:
    raw = _read(config.DATA_DIR / "weather" / "niphad.json")
    return {k: v for k, v in raw.items() if k != "days"}


@lru_cache(maxsize=1)
def calendar() -> dict:
    return _read(config.DATA_DIR / "calendar.json")["crops"]


@lru_cache(maxsize=1)
def checks() -> dict:
    return _read(config.DATA_DIR / "checks.json")


@lru_cache(maxsize=1)
def scenarios() -> dict:
    return _read(config.DATA_DIR / "scenarios.json")


def case_specs() -> list[dict]:
    return scenarios()["cases"]


def case_spec(case_id: str) -> dict | None:
    return next((c for c in case_specs() if c["id"] == case_id), None)


def distance_km(a: FieldRec, b: FieldRec) -> float:
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    x = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a.lat)) * math.cos(math.radians(b.lat)) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(x))
