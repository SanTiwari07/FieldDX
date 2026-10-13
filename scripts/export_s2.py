"""Export real Sentinel-2 pixels for an area from Google Earth Engine.

For each acquisition date that touches the area, one GeoTIFF on a 10 m UTM grid (snapped to whole
multiples of 10 m, which is where the Sentinel-2 grid sits) with three float32 bands:

    ndvi   (B8 - B4) / (B8 + B4), no masking
    scl    Scene Classification Layer class (0 = no data)
    cs     Cloud Score+ cs_cdf (0 to 1)

Masking is applied later (build_dataset.py) so the raw bands stay available. The recipe follows the
author's earlier project (Pragya): COPERNICUS/S2_SR_HARMONIZED joined with
GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED, a pixel is clear when cs_cdf >= 0.60 and SCL is not 3
(shadow), 8, 9 (cloud) or 10 (cirrus). There is deliberately NO whole-granule CLOUDY_PIXEL_PERCENTAGE
prefilter: that figure describes a ~110 km tile, not the field, and during the monsoon it hides most
usable passes. Reflectance is scaled by 1/10000 only (the NDVI ratio is unaffected).

Also exports ESA WorldCover (2021) on the same grid, used to keep fields that are cropland.

Needs `earthengine authenticate` to have been run once.

Run:  python scripts/export_s2.py --bbox 74.07 20.04 74.16 20.12 --start 2025-10-01 --end 2026-10-13 --out data/areas/niphad/raw/s2
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ee
import numpy as np
import pyproj

S2 = "COPERNICUS/S2_SR_HARMONIZED"
CSP = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
WORLDCOVER = "ESA/WorldCover/v200"


def utm_epsg(bbox) -> str:
    """The UTM zone of the area's centre, where Sentinel-2 tiles are delivered."""
    lon, lat = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    zone = int((lon + 180) // 6) + 1
    return f"EPSG:{(32600 if lat >= 0 else 32700) + zone}"


def grid_for(bbox, epsg, margin_m=60):
    """UTM-aligned pixel grid: (x0, y_top, nx, ny) with 10 m cells on multiples of 10."""
    to_utm = pyproj.Transformer.from_crs("EPSG:4326", epsg, always_xy=True)
    xs, ys = zip(*[to_utm.transform(lon, lat) for lon in (bbox[0], bbox[2]) for lat in (bbox[1], bbox[3])])
    x0 = int(np.floor((min(xs) - margin_m) / 10) * 10)
    x1 = int(np.ceil((max(xs) + margin_m) / 10) * 10)
    y0 = int(np.floor((min(ys) - margin_m) / 10) * 10)
    y1 = int(np.ceil((max(ys) + margin_m) / 10) * 10)
    return x0, y1, (x1 - x0) // 10, (y1 - y0) // 10


def region_of(x0, ytop, nx, ny, epsg):
    return ee.Geometry.Rectangle([x0, ytop - ny * 10, x0 + nx * 10, ytop], epsg, geodesic=False)


def day_image(day: str, region):
    d0 = ee.Date(day)
    d1 = d0.advance(1, "day")
    s2 = ee.ImageCollection(S2).filterBounds(region).filterDate(d0, d1)
    cs = ee.ImageCollection(CSP).filterBounds(region).filterDate(d0, d1)
    sr = s2.mosaic()
    ndvi = sr.select("B8").subtract(sr.select("B4")).divide(sr.select("B8").add(sr.select("B4"))).rename("ndvi")
    scl = sr.select("SCL").rename("scl")
    csb = cs.select("cs_cdf").mosaic().rename("cs")
    return ndvi.addBands(scl).addBands(csb).unmask(-9999).toFloat()


def download(image, region, x0, ytop, epsg, path: Path, retries=4):
    url = image.getDownloadURL({
        "name": path.stem, "format": "GEO_TIFF", "region": region,
        "crs": epsg, "crs_transform": [10, 0, x0, 0, -10, ytop],
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                data = r.read()
            path.write_bytes(data)
            return len(data)
        except Exception as e:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def list_days(region, start, end):
    col = ee.ImageCollection(S2).filterBounds(region).filterDate(start, end)
    stamps = col.aggregate_array("system:time_start").getInfo()
    days = sorted({datetime.fromtimestamp(t / 1000, timezone.utc).strftime("%Y-%m-%d") for t in stamps})
    return days


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("LON0", "LAT0", "LON1", "LAT1"))
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True, help="exclusive, as Earth Engine filterDate")
    ap.add_argument("--out", required=True)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--project", default=None, help="Earth Engine cloud project, if one is required")
    a = ap.parse_args()

    ee.Initialize(project=a.project) if a.project else ee.Initialize()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    epsg = utm_epsg(a.bbox)
    x0, ytop, nx, ny = grid_for(a.bbox, epsg)
    region = region_of(x0, ytop, nx, ny, epsg)
    meta = {"epsg": epsg, "x0": x0, "y_top": ytop, "nx": nx, "ny": ny, "cell_m": 10,
            "bbox": a.bbox, "start": a.start, "end": a.end,
            "source": "Copernicus Sentinel-2 L2A (COPERNICUS/S2_SR_HARMONIZED) with Cloud Score+ via Google Earth Engine"}
    (out / "grid.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"grid {nx}x{ny} cells at x0={x0} y_top={ytop}", file=sys.stderr)

    lc = out / "worldcover.tif"
    if not lc.exists():
        img = ee.ImageCollection(WORLDCOVER).first().select("Map").unmask(0).toFloat()
        n = download(img, region, x0, ytop, epsg, lc)
        print(f"worldcover {n/1e3:.0f} kB", file=sys.stderr)

    days = list_days(region, a.start, a.end)
    print(f"{len(days)} acquisition dates", file=sys.stderr, flush=True)
    todo = [d for d in days if not (out / f"{d}.tif").exists()]

    def one(d):
        n = download(day_image(d, region), region, x0, ytop, epsg, out / f"{d}.tif")
        return d, n

    done = 0
    with ThreadPoolExecutor(max_workers=a.threads) as ex:
        for fut in as_completed([ex.submit(one, d) for d in todo]):
            d, n = fut.result()
            done += 1
            print(f"[{done}/{len(todo)}] {d} {n/1e6:.1f} MB", file=sys.stderr, flush=True)
    (out / "dates.json").write_text(json.dumps(days), encoding="utf-8")


if __name__ == "__main__":
    main()
