"""What is changing across a whole region this fortnight: the screen before an officer marks an area.

Computed live in Google Earth Engine from real Sentinel-2 L2A, masked per pixel with Cloud Score+
(0.60) and the scene classification layer, and limited to ESA WorldCover cropland. For every pixel it
compares the median NDVI of the last 16 days with the median of 25 to 50 days ago, the same idea as the
alert detector but over the whole district at once.

It is a screening layer, not a diagnosis: a harvested field drops just like a failing one. Its job is
to show where to look; the officer then marks the land there and FieldDx investigates field by field.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
import urllib.request
from collections import OrderedDict
from datetime import date, timedelta

from . import config, places

S2 = "COPERNICUS/S2_SR_HARMONIZED"
CSP = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
WORLDCOVER = "ESA/WorldCover/v200"
SCL_BAD = [0, 1, 3, 8, 9, 10, 11]
DROP, GAIN = -0.10, 0.10
# discrete bins of the app's change ramp (frontend lib/ramps.ts, DELTA_STOPS)
PALETTE = ["7a3410", "b8662a", "e7b98a", "f2f1ee", "a9d4cf", "4e9a93", "145e59"]
MAX_KM2 = 60_000
MAP_TTL_S = 3 * 3600

_ee_lock = threading.Lock()
_ee_ready = False
_maps: dict[str, tuple[str, float]] = {}
_summaries: dict[str, dict] = {}
_tiles: "OrderedDict[tuple, bytes]" = OrderedDict()
_tiles_lock = threading.Lock()


class OverviewError(ValueError):
    pass


def _ee():
    global _ee_ready
    import ee  # imported lazily: the app runs without Earth Engine, only this screen needs it
    with _ee_lock:
        if not _ee_ready:
            try:
                project = os.environ.get("FIELDDX_EE_PROJECT")
                ee.Initialize(project=project) if project else ee.Initialize()
            except Exception as e:  # noqa: BLE001
                raise OverviewError("Earth Engine is not set up on this server (run earthengine authenticate)") from e
            _ee_ready = True
    return ee


def windows(today: date | None = None) -> dict:
    t = today or date.today()
    return {"recent": [(t - timedelta(days=16)).isoformat(), t.isoformat()],
            "baseline": [(t - timedelta(days=50)).isoformat(), (t - timedelta(days=25)).isoformat()]}


def key_for(region: dict) -> str:
    raw = json.dumps(region, sort_keys=True) + date.today().isoformat()
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _km2(bounds: list) -> float:
    (s, w), (n, e) = bounds
    return abs(n - s) * 110.57 * abs(e - w) * 111.32 * math.cos(math.radians((n + s) / 2))


def _region(ee, region: dict):
    b = region.get("boundary")
    if b and b.get("type") in ("Polygon", "MultiPolygon"):
        return ee.Geometry(b)
    (s, w), (n, e) = region["bounds"]
    return ee.Geometry.Rectangle([w, s, e, n])


def _change(ee, geom):
    """NDVI change per cropland pixel (recent median minus baseline median), and the WorldCover cropland mask."""
    win = windows()
    cs = ee.ImageCollection(CSP)

    def ndvi(img):
        scl = img.select("SCL")
        ok = img.select("cs_cdf").gte(0.60)
        for c in SCL_BAD:
            ok = ok.And(scl.neq(c))
        return img.normalizedDifference(["B8", "B4"]).rename("ndvi").updateMask(ok)

    def median(start, end):
        col = ee.ImageCollection(S2).filterBounds(geom).filterDate(start, ee.Date(end).advance(1, "day"))
        return col.linkCollection(cs, ["cs_cdf"]).map(ndvi).median()

    crop = ee.ImageCollection(WORLDCOVER).first().select("Map").eq(40)
    change = median(*win["recent"]).subtract(median(*win["baseline"])).rename("change")
    return change.updateMask(crop), crop


def tile_url(region: dict) -> dict:
    """An XYZ layer of this fortnight's NDVI change over the region's cropland."""
    if _km2(region["bounds"]) > MAX_KM2:
        raise OverviewError("That region is too large to scan at once; choose a district or smaller")
    key = key_for(region)
    hit = _maps.get(key)
    if hit and time.time() - hit[1] < MAP_TTL_S:
        return {"key": key, "windows": windows()}
    ee = _ee()
    geom = _region(ee, region)
    change, _crop = _change(ee, geom)
    bins = (ee.Image(0).where(change.gt(-0.15), 1).where(change.gt(-0.10), 2).where(change.gt(-0.05), 3)
            .where(change.gt(0.05), 4).where(change.gt(0.10), 5).where(change.gt(0.15), 6))
    vis = bins.updateMask(change.mask()).clip(geom).visualize(min=0, max=6, palette=PALETTE)
    url = vis.getMapId()["tile_fetcher"].url_format
    _maps[key] = (url, time.time())
    return {"key": key, "windows": windows()}


def tile(key: str, z: int, x: int, y: int) -> bytes | None:
    hit = _maps.get(key)
    if not hit:
        return None
    k = (key, z, x, y)
    with _tiles_lock:
        if k in _tiles:
            _tiles.move_to_end(k)
            return _tiles[k]
    url = hit[0].replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
    req = urllib.request.Request(url, headers={"User-Agent": config.HTTP_USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    with _tiles_lock:
        _tiles[k] = body
        while len(_tiles) > 3000:
            _tiles.popitem(last=False)
    return body


def summary(region: dict, name: str = "") -> dict:
    """Share of the region's cropland that lost or gained greenness, and the cells where most of it dropped."""
    key = key_for(region)
    if key in _summaries:
        return _summaries[key]
    if _km2(region["bounds"]) > MAX_KM2:
        raise OverviewError("That region is too large to scan at once; choose a district or smaller")
    ee = _ee()
    geom = _region(ee, region)
    change, crop = _change(ee, geom)
    seen = change.mask().gt(0).And(crop)
    stack = ee.Image.cat([crop.rename("crop"), seen.rename("seen"),
                          change.lte(DROP).And(seen).rename("drop"), change.gte(GAIN).And(seen).rename("gain")]).unmask(0)
    km2 = _km2(region["bounds"])
    scale = max(60, int(math.sqrt(km2 * 1e6 / 2.5e6)))  # about 2.5 million pixels whatever the region size
    tot = stack.reduceRegion(ee.Reducer.sum(), geom, scale, maxPixels=1e10, bestEffort=True, tileScale=4).getInfo()

    # hotspots: a grid of cells over the region, ranked by the share of their clearly seen cropland that dropped
    (s, w), (n, e) = region["bounds"]
    cell_km = max(3.0, math.sqrt(km2) / 9)
    dlat = cell_km / 110.57
    dlon = cell_km / (111.32 * math.cos(math.radians((n + s) / 2)))
    cells = []
    lat = s
    while lat < n:
        lon = w
        while lon < e:
            cells.append(ee.Feature(ee.Geometry.Rectangle([lon, lat, lon + dlon, lat + dlat]),
                                    {"w": lon, "s": lat, "e": lon + dlon, "n": lat + dlat}))
            lon += dlon
        lat += dlat
    def inside(f):  # measure only the part of each cell inside the region, and name it from that part
        g = f.geometry().intersection(geom, ee.ErrorMargin(100))
        c = g.centroid(ee.ErrorMargin(100)).coordinates()
        return f.setGeometry(g).set({"cx": c.get(0), "cy": c.get(1)})
    fc = ee.FeatureCollection(cells).filterBounds(geom).map(inside)
    rows = stack.reduceRegions(fc, ee.Reducer.sum(), scale, tileScale=4).getInfo()["features"]
    spots = []
    for f in rows:
        p = f["properties"]
        if p.get("crop", 0) <= 0 or p.get("seen", 0) < 0.3 * p["crop"] or p["seen"] < 50:
            continue
        spots.append({"bounds": [[p["s"], p["w"]], [p["n"], p["e"]]],
                      "center": [p.get("cy", (p["s"] + p["n"]) / 2), p.get("cx", (p["w"] + p["e"]) / 2)],
                      "drop": round(p["drop"] / p["seen"], 3), "gain": round(p["gain"] / p["seen"], 3),
                      "seen": round(p["seen"] / p["crop"], 3), "cropland_km2": round(p["crop"] * scale * scale / 1e6, 1)})
    spots.sort(key=lambda h: -h["drop"])
    top = [h for h in spots if h["drop"] >= 0.05][:6]
    for h in top:
        h["near"] = places.nearest_name(*h["center"])

    crop_px, seen_px = tot.get("crop", 0) or 0, tot.get("seen", 0) or 0
    out = {
        "key": key, "name": name, "windows": windows(), "scale_m": scale, "cell_km": round(cell_km, 1),
        "cropland_km2": round(crop_px * scale * scale / 1e6),
        "seen": round(seen_px / crop_px, 3) if crop_px else 0.0,
        "drop": round((tot.get("drop", 0) or 0) / seen_px, 3) if seen_px else None,
        "gain": round((tot.get("gain", 0) or 0) / seen_px, 3) if seen_px else None,
        "hotspots": top,
        "source": "Copernicus Sentinel-2 L2A with Cloud Score+ (0.60) and SCL masks, ESA WorldCover 2021 cropland, via Google Earth Engine",
    }
    _summaries[key] = out
    return out
