"""Load the real dataset of each area, built by scripts/build_area.py.

Every area lives in its own folder, data/areas/<area>/, so an officer only ever reads the area they
work in. Fields are real shapes (Fields of the World), scenes are real Sentinel-2 L2A pixels masked with Cloud
Score+ and SCL, weather is the Open-Meteo archive. Zone values are derived here from the pixels, so
every number the tools report traces back to pixels.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache

import numpy as np
import pyproj

from . import config

INTERIOR = ["in_nw", "in_ne", "in_sw", "in_se"]
EDGES = ["edge_n", "edge_e", "edge_s", "edge_w"]
ANALYSIS = INTERIOR + EDGES
RAW = ["raw_edge_n", "raw_edge_e", "raw_edge_s", "raw_edge_w"]
ALL_ZONES = ANALYSIS + RAW
# A field too small or too thin for the eight zones is read as one: its core pixels (the shape shrunk
# half a pixel). Every field also has a "whole" reading, the union of its analysis pixels.
WHOLE = "whole"
ZONE_CODES = ANALYSIS + [WHOLE]  # grid az codes: 0-7 the eight zones, 8 a whole-field core pixel

ZONE_LABEL = {
    "in_nw": "North-west interior", "in_ne": "North-east interior",
    "in_sw": "South-west interior", "in_se": "South-east interior",
    "edge_n": "North edge", "edge_e": "East edge", "edge_s": "South edge", "edge_w": "West edge",
    "raw_edge_n": "North edge (unshrunk)", "raw_edge_e": "East edge (unshrunk)",
    "raw_edge_s": "South edge (unshrunk)", "raw_edge_w": "West edge (unshrunk)",
    WHOLE: "Whole field",
}
SIDE_NAME = {"n": "north", "e": "east", "s": "south", "w": "west"}
CLASS_LABEL = {
    "perennial": "Perennial canopy",
    "seasonal": "Seasonal crop",
    "unknown": "Crop not identified",
}
CELL_M = 10


@dataclass(frozen=True)
class ZoneObs:
    ndvi: float | None
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
    px: np.ndarray  # NDVI of every pixel inside the field, NaN where masked; same order as Grid.cells

    def __hash__(self):  # numpy arrays are not hashable; a scene is identified by its date
        return hash(self.date)


@dataclass(frozen=True)
class Grid:
    epsg: str
    x0: float
    y_top: float
    r0: int
    c0: int
    nr: int
    nc: int
    inside: np.ndarray  # nr x nc bool
    az: np.ndarray      # nr x nc int, index into ANALYSIS, -1 outside the analysis area
    rz: np.ndarray      # nr x nc int, index into RAW, -1 when not on the outer ring
    cells: np.ndarray   # flat indices of the pixels inside the field, row-major

    def bounds_lonlat(self) -> list[list[float]]:
        """[[south, west], [north, east]] of the grid rectangle, for placing the raster."""
        to_ll = pyproj.Transformer.from_crs(self.epsg, "EPSG:4326", always_xy=True)
        left = self.x0 + self.c0 * CELL_M
        top = self.y_top - self.r0 * CELL_M
        right, bottom = left + self.nc * CELL_M, top - self.nr * CELL_M
        pts = [to_ll.transform(x, y) for x in (left, right) for y in (top, bottom)]
        lons, lats = [p[0] for p in pts], [p[1] for p in pts]
        return [[min(lats), min(lons)], [max(lats), max(lons)]]


@dataclass(frozen=True)
class FieldRec:
    area: str
    id: str
    name: str
    klass: str
    area_ha: float
    compactness: float
    analysis_pixels: int
    zone_pixels: dict[str, int]
    zone_polygons: dict[str, list]   # zone -> list of rings, each a list of [lon, lat]
    outline: list                    # list of rings, each a list of [lon, lat]
    lat: float
    lon: float
    monthly: dict[str, float]
    pixel_count: int = 0
    mode: str = "zoned"              # "zoned": eight zones and the edge ring; "whole": one zone

    @property
    def zones(self) -> list[str]:
        """The zones this field is analysed in."""
        return ANALYSIS if self.mode == "zoned" else [WHOLE]

    @property
    def raw_zones(self) -> list[str]:
        """The unshrunk edge ring, used only by the boundary check; a whole field has none."""
        return RAW if self.mode == "zoned" else []


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def areas_root():
    return config.DATA_DIR / "areas"


def area_dir(area: str):
    return areas_root() / area


def _rings(geom: dict) -> list:
    """Exterior rings of a Polygon or MultiPolygon GeoJSON geometry."""
    if not geom or not geom.get("coordinates"):
        return []
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [p[0] for p in geom["coordinates"]]
    return []


@lru_cache(maxsize=None)
def provenance(area: str) -> dict:
    return _read(area_dir(area) / "fields.geojson").get("provenance", {})


@lru_cache(maxsize=None)
def fields(area: str) -> dict[str, FieldRec]:
    raw = _read(area_dir(area) / "fields.geojson")
    out: dict[str, FieldRec] = {}
    for feat in raw["features"]:
        p = feat["properties"]
        mode = p.get("mode", "zoned")
        zp = dict(p["zone_pixels"])
        zp.setdefault(WHOLE, sum(zp.get(z, 0) for z in ANALYSIS))
        zones = ANALYSIS if mode == "zoned" else [WHOLE]
        polys = {z: _rings(g) for z, g in p["zones"].items()}
        polys.setdefault(WHOLE, _rings(feat["geometry"]))
        out[p["id"]] = FieldRec(
            area=area, id=p["id"], name=p["name"], klass=p.get("class", "unknown"), area_ha=p["area_ha"],
            compactness=p.get("compactness", 0.0), analysis_pixels=sum(zp.get(z, 0) for z in zones),
            zone_pixels=zp, zone_polygons=polys,
            outline=_rings(feat["geometry"]), lat=p["centroid"][1], lon=p["centroid"][0],
            monthly=p.get("ndvi_monthly", {}), mode=mode,
        )
    return out


@lru_cache(maxsize=None)
def _shapes(area: str) -> tuple:
    path = area_dir(area) / "shapes.geojson"
    return tuple(_read(path)["features"]) if path.exists() else ()


def shapes(area: str) -> list[dict]:
    """Every field shape in the area, watched or not and why, and the gaps where no field was found
    (scripts/build_dataset.py). Empty for an area built before this file existed."""
    return list(_shapes(area))


@lru_cache(maxsize=None)
def grid(area: str, field_id: str) -> Grid:
    g = _read(area_dir(area) / "grids" / f"{field_id}.json")
    nr, nc = g["nr"], g["nc"]
    inside = np.array(g["inside"], dtype=bool).reshape(nr, nc)
    return Grid(
        epsg=g["epsg"], x0=g["x0"], y_top=g["y_top"], r0=g["r0"], c0=g["c0"], nr=nr, nc=nc, inside=inside,
        az=np.array(g["az"], dtype=int).reshape(nr, nc), rz=np.array(g["rz"], dtype=int).reshape(nr, nc),
        cells=np.flatnonzero(inside.ravel()),
    )


def _zone_obs(g: Grid, px: np.ndarray) -> dict[str, ZoneObs]:
    az = g.az.ravel()[g.cells]
    rz = g.rz.ravel()[g.cells]
    ok = ~np.isnan(px)
    out: dict[str, ZoneObs] = {}
    for k, z in enumerate(ANALYSIS):
        m = az == k
        n = int(m.sum())
        out[z] = ZoneObs(float(px[m & ok].mean()) if (m & ok).any() else None, float((m & ok).sum() / n) if n else 0.0, n)
    for k, z in enumerate(RAW):
        m = rz == k
        n = int(m.sum())
        out[z] = ZoneObs(float(px[m & ok].mean()) if (m & ok).any() else None, float((m & ok).sum() / n) if n else 0.0, n)
    m = az >= 0  # the whole-field reading: every analysis pixel, whichever zone it is in
    n = int(m.sum())
    out[WHOLE] = ZoneObs(float(px[m & ok].mean()) if (m & ok).any() else None, float((m & ok).sum() / n) if n else 0.0, n)
    return out


@lru_cache(maxsize=None)
def scenes(area: str, field_id: str) -> tuple[Scene, ...]:
    g = grid(area, field_id)
    raw = _read(area_dir(area) / "scenes" / f"{field_id}.json")
    out = []
    for s in raw["scenes"]:
        px = np.array([np.nan if v is None else v / 1000.0 for v in s["ndvi"]], dtype=float)
        out.append(Scene(
            date=date.fromisoformat(s["date"]), scene_id=s["scene_id"], cloud_pct=s.get("cloud_pct", 0),
            shadow_pct=s.get("shadow_pct", 0), cirrus_pct=s.get("cirrus_pct", 0),
            zones=_zone_obs(g, px), px=px,
        ))
    return tuple(sorted(out, key=lambda x: x.date))


@dataclass(frozen=True)
class WeatherDay:
    date: date
    rain_mm: float
    tmax_c: float
    rh_mean: float
    soil_moisture: float


@lru_cache(maxsize=None)
def weather(area: str) -> tuple[WeatherDay, ...]:
    raw = _read(area_dir(area) / "weather.json")
    return tuple(
        WeatherDay(date.fromisoformat(d["date"]), d["rain_mm"], d["tmax_c"], d["rh_mean"], d["soil_moisture"])
        for d in raw["days"]
    )


@lru_cache(maxsize=None)
def weather_meta(area: str) -> dict:
    raw = _read(area_dir(area) / "weather.json")
    return {k: v for k, v in raw.items() if k != "days"}


@lru_cache(maxsize=None)
def calendar(area: str) -> dict:
    """Management windows per canopy class. An area without a calendar file has none."""
    path = area_dir(area) / "calendar.json"
    return _read(path)["classes"] if path.exists() else {}


@lru_cache(maxsize=1)
def checks() -> dict:
    return _read(config.DATA_DIR / "checks.json")


@lru_cache(maxsize=None)
def cases_file(area: str) -> dict:
    return _read(area_dir(area) / "cases.json")


def case_specs(area: str) -> list[dict]:
    return cases_file(area)["cases"]


def case_spec(area: str, case_id: str) -> dict | None:
    return next((c for c in case_specs(area) if c["id"] == case_id), None)


def is_ready(area: str) -> bool:
    """An area can be read once its build has written the alerts, the last file of a build."""
    return (area_dir(area) / "cases.json").exists() and (area_dir(area) / "fields.geojson").exists()


def clear_caches() -> None:
    for fn in (provenance, fields, _shapes, grid, scenes, weather, weather_meta, calendar, checks, cases_file):
        fn.cache_clear()


def distance_km(a: FieldRec, b: FieldRec) -> float:
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    x = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a.lat)) * math.cos(math.radians(b.lat)) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(x))
