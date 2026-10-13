"""Assemble the FieldDx dataset from real inputs. Nothing here is simulated.

Inputs (all real), in the area's folder data/areas/<area>/:
  raw/ftw_b5/polygons.parquet   field boundaries from the Fields of the World model (ftw_fields.py), or
  raw/ftw_global/...            the published Fields of the World global map (ftw_global.py)
  raw/s2/                       Sentinel-2 L2A pixels from Earth Engine (export_s2.py)
  area.json                     the area polygon the officer marked, if any: fields outside it are dropped

Outputs in the same folder:
  fields.geojson          the selected real field shapes, with provenance and the inferred class
  grids/<id>.json         the 10 m pixel grid of each field: which pixels are inside, and their zones
  scenes/<id>.json        per scene, NDVI of every pixel inside the field (x1000, null when masked)

Selection: area 0.8 to 12 ha, compact shape, at least 60% ESA WorldCover cropland (no river, town or
trees), far enough from the edge of the downloaded area, and every analysis zone has at least 2 pixels.

Zones follow idea.md section 4.2: the analysis area is the shape shrunk 10 m (drops boundary-mixed
pixels), the interior is shrunk a further 20 m split into four quadrants, the edge ring between them is
split into N, E, S, W, and the unshrunk 20 m ring (raw_edge_*) exists only for the boundary check.

Run:  python scripts/build_dataset.py --area data/areas/niphad [--app-from 2026-06-10] [--fields raw/ftw_global/polygons.parquet]
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import numpy as np
import pyproj
import rasterio
from shapely import contains_xy
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform as shp_transform

ROOT = Path(__file__).resolve().parent.parent

ZONES = ["in_nw", "in_ne", "in_sw", "in_se", "edge_n", "edge_e", "edge_s", "edge_w"]
RAWZ = ["raw_edge_n", "raw_edge_e", "raw_edge_s", "raw_edge_w"]

SCL_BAD = {0, 1, 3, 8, 9, 10, 11}  # no data, saturated, shadow, cloud (medium, high), cirrus, snow
CS_MIN = 0.60
APP_FROM = "2026-06-10"  # default: scenes before this are used only to infer the crop class
BOUNDARIES_B5 = "Fields of the World (FTW) PRUE EfficientNet-B5 CC-BY model, run on Sentinel-2 L2A scenes of 2025 (ftw-tools)"
MIN_HA, MAX_HA = 0.8, 12.0
CROP_FRACTION = 0.60
MAX_FIELDS = 150
MIN_ZONE_PX = 2


def sector(dx: float, dy: float) -> str:
    """Compass side of a point relative to the centroid, by the diagonals (y points north)."""
    if abs(dy) >= abs(dx):
        return "n" if dy >= 0 else "s"
    return "e" if dx >= 0 else "w"


def year_window(as_of: str) -> tuple[str, str]:
    """The twelve full months (YYYY-MM, inclusive) before the month of `as_of`."""
    y, m = int(as_of[:4]), int(as_of[5:7])
    first = f"{y - 1}-{m + 1:02d}" if m < 12 else f"{y}-01"
    last = f"{y}-{m - 1:02d}" if m > 1 else f"{y - 1}-12"
    return first, last


def quadrant(dx: float, dy: float) -> str:
    return ("n" if dy >= 0 else "s") + ("e" if dx >= 0 else "w")


def load_polygons(grid, path, within=None):
    """Field polygons in the grid's CRS; with `within` (a lon/lat shape), only those whose centre is inside it."""
    g = gpd.read_parquet(path)
    if within is not None:
        g = g[g.geometry.representative_point().within(within)]
    return g.to_crs(grid["epsg"]).reset_index(drop=True)


def read_band(path: Path, band: int) -> np.ndarray:
    with rasterio.open(path) as ds:
        return ds.read(band)


SKIP_REASONS = {  # read after a count: "3 under 0.8 ha"
    "small": f"under {MIN_HA} ha", "large": f"over {MAX_HA:.0f} ha", "irregular": "with an irregular outline",
    "edge": "at the edge of the imagery", "narrow": "too narrow for 10 m zones", "cropland": "not mostly cropland",
    "thin_zones": "with a zone under 2 pixels",
}


def select_fields(g, grid, worldcover, skipped=None):
    """Fields that can be diagnosed zone by zone; `skipped` counts why the others were left out."""
    skipped = skipped if skipped is not None else defaultdict(int)
    x0, ytop, nx, ny = grid["x0"], grid["y_top"], grid["nx"], grid["ny"]
    xmax, ymin = x0 + nx * 10, ytop - ny * 10
    picked = []
    for i, row in g.iterrows():
        poly = row.geometry
        if poly.geom_type == "MultiPolygon":
            poly = max(poly.geoms, key=lambda p: p.area)
        poly = poly.buffer(0).simplify(2.0)
        area = poly.area / 1e4
        if not (MIN_HA <= area <= MAX_HA):
            skipped["small" if area < MIN_HA else "large"] += 1
            continue
        compact = 4 * np.pi * poly.area / poly.length ** 2
        if compact < 0.35:
            skipped["irregular"] += 1
            continue
        minx, miny, maxx, maxy = poly.bounds
        if minx < x0 + 40 or maxx > xmax - 40 or miny < ymin + 40 or maxy > ytop - 40:
            skipped["edge"] += 1
            continue
        analysis = poly.buffer(-10)
        interior = poly.buffer(-30)
        if analysis.is_empty or interior.is_empty or interior.area < 400:
            skipped["narrow"] += 1
            continue
        # land cover inside the shape
        c0, c1 = int((minx - x0) // 10), int((maxx - x0) // 10) + 1
        r0, r1 = int((ytop - maxy) // 10), int((ytop - miny) // 10) + 1
        rr, cc = np.mgrid[r0:r1, c0:c1]
        px = x0 + (cc + 0.5) * 10
        py = ytop - (rr + 0.5) * 10
        inside = contains_xy(poly, px, py)
        if inside.sum() < 40:
            skipped["small"] += 1
            continue
        lc = worldcover[r0:r1, c0:c1][inside]
        crop = float((lc == 40).mean())
        if crop < CROP_FRACTION:
            skipped["cropland"] += 1
            continue
        picked.append((i, poly, area, compact, crop))
    return picked


def build_grid(poly, grid):
    """Pixel grid of one field: inside map, analysis zone code and raw edge code per pixel."""
    x0, ytop = grid["x0"], grid["y_top"]
    minx, miny, maxx, maxy = poly.bounds
    c0, c1 = int((minx - x0) // 10) - 1, int((maxx - x0) // 10) + 2
    r0, r1 = int((ytop - maxy) // 10) - 1, int((ytop - miny) // 10) + 2
    rr, cc = np.mgrid[r0:r1, c0:c1]
    px = x0 + (cc + 0.5) * 10
    py = ytop - (rr + 0.5) * 10
    cen = poly.centroid
    analysis, interior, raw_inner = poly.buffer(-10), poly.buffer(-30), poly.buffer(-20)
    ins = contains_xy(poly, px, py)
    in_a = contains_xy(analysis, px, py)
    in_i = contains_xy(interior, px, py)
    in_r = contains_xy(raw_inner, px, py)
    az = np.full(px.shape, -1, dtype=np.int8)
    rz = np.full(px.shape, -1, dtype=np.int8)
    for (r, c), inside in np.ndenumerate(ins):
        if not inside:
            continue
        dx, dy = px[r, c] - cen.x, py[r, c] - cen.y
        if in_i[r, c]:
            az[r, c] = ZONES.index("in_" + quadrant(dx, dy))
        elif in_a[r, c]:
            az[r, c] = ZONES.index("edge_" + sector(dx, dy))
        if not in_r[r, c]:
            rz[r, c] = RAWZ.index("raw_edge_" + sector(dx, dy))
    return {"r0": r0, "c0": c0, "nr": r1 - r0, "nc": c1 - c0,
            "inside": ins.astype(np.int8), "az": az, "rz": rz}


def zone_polygons(poly, grid_info, grid, to_ll):
    """Zone shapes for the map outline layer: the union of the pixels of each analysis zone, smoothed."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    x0, ytop = grid["x0"], grid["y_top"]
    out = {}
    for k, z in enumerate(ZONES):
        cells = []
        for (r, c), v in np.ndenumerate(grid_info["az"]):
            if v == k:
                gx = x0 + (grid_info["c0"] + c) * 10
                gy = ytop - (grid_info["r0"] + r) * 10
                cells.append(box(gx, gy - 10, gx + 10, gy))
        u = unary_union(cells).intersection(poly) if cells else poly.buffer(-1000)
        out[z] = shp_transform(to_ll, u)
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", required=True, help="the area folder, e.g. data/areas/niphad")
    ap.add_argument("--app-from", default=APP_FROM, help="first scene date the app shows (YYYY-MM-DD)")
    ap.add_argument("--fields", default="raw/ftw_b5/polygons.parquet", help="field polygons, relative to the area")
    ap.add_argument("--boundaries", default=BOUNDARIES_B5, help="where the field polygons came from (provenance)")
    a = ap.parse_args()
    OUT = Path(a.area)
    meta = json.loads((OUT / "area.json").read_text(encoding="utf-8")) if (OUT / "area.json").exists() else {}
    within = shape(meta["geometry"]) if meta.get("geometry") else None
    S2 = OUT / "raw" / "s2"
    app_from = a.app_from
    grid = json.loads((S2 / "grid.json").read_text(encoding="utf-8"))
    to_ll = pyproj.Transformer.from_crs(grid["epsg"], "EPSG:4326", always_xy=True).transform
    wc = read_band(S2 / "worldcover.tif", 1).astype(int)

    g = load_polygons(grid, OUT / a.fields, within)
    print(f"{len(g)} FTW polygons", file=sys.stderr)
    skipped = defaultdict(int)
    picked = select_fields(g, grid, wc, skipped)
    print(f"{len(picked)} pass area, shape, cropland and edge filters", file=sys.stderr)

    # build zone grids; drop fields whose zones are too thin to measure
    fields = []
    for i, poly, area, compact, crop in picked:
        gi = build_grid(poly, grid)
        counts = {z: int((gi["az"] == k).sum()) for k, z in enumerate(ZONES)}
        if min(counts.values()) < MIN_ZONE_PX:
            skipped["thin_zones"] += 1
            continue
        fields.append({"src": int(i), "poly": poly, "area": area, "compact": compact, "crop": crop, "gi": gi, "counts": counts})
    print(f"{len(fields)} fields have at least {MIN_ZONE_PX} pixels in every zone", file=sys.stderr)
    why = ", ".join(f"{n} {SKIP_REASONS[k]}" for k, n in sorted(skipped.items(), key=lambda kv: -kv[1]))
    if why:
        print(f"skipped: {why}", file=sys.stderr)
    if not fields:
        print(f"None of the {len(g)} field shape{'s' if len(g) != 1 else ''} can be monitored ({why}). "
              "Choose fields of at least 1 ha with some width to them, or mark a wider area.", file=sys.stderr)
        sys.exit(3)

    # keep the most compact, largest fields if there are very many
    if len(fields) > MAX_FIELDS:
        fields.sort(key=lambda f: -(f["compact"] * min(f["area"], 4)))
        fields = fields[:MAX_FIELDS]
    fields.sort(key=lambda f: (-f["poly"].centroid.y // 400, f["poly"].centroid.x))  # north to south, west to east
    for n, f in enumerate(fields, 1):
        f["id"] = f"F{n:03d}"

    # ---- read every scene once, cut out every field
    dates = json.loads((S2 / "dates.json").read_text(encoding="utf-8"))
    first_month, last_month = year_window(max(dates))
    series = {f["id"]: {} for f in fields}
    aoi_quality = {}
    for d in dates:
        with rasterio.open(S2 / f"{d}.tif") as ds:
            ndvi, scl, cs = ds.read(1), ds.read(2), ds.read(3)
        have = scl > -9000
        aoi_quality[d] = {"data": float(have.mean())}
        for f in fields:
            gi = f["gi"]
            sl = (slice(gi["r0"], gi["r0"] + gi["nr"]), slice(gi["c0"], gi["c0"] + gi["nc"]))
            ins = gi["inside"] == 1
            sc, nd, c = scl[sl][ins], ndvi[sl][ins], cs[sl][ins]
            if (sc > -9000).mean() < 0.5:
                continue  # the pass did not cover this field
            clear = (~np.isin(sc, list(SCL_BAD))) & (c >= CS_MIN) & np.isfinite(nd) & (nd > -1) & (nd <= 1) & (sc > -9000)
            n = len(sc)
            series[f["id"]][d] = {
                "ndvi": np.where(clear, np.round(nd * 1000), np.iinfo(np.int16).min).astype(int),
                "cloud": int(round(100 * np.isin(sc, [8, 9]).sum() / n)),
                "shadow": int(round(100 * (sc == 3).sum() / n)),
                "cirrus": int(round(100 * (sc == 10).sum() / n)),
            }

    # ---- crop class from a year of NDVI: a perennial canopy never goes to bare soil
    monthly_all = {}
    for f in fields:
        by_month = defaultdict(list)
        for d, s in series[f["id"]].items():
            ok = s["ndvi"] != np.iinfo(np.int16).min
            if ok.mean() >= 0.8:
                by_month[d[:7]].append(float(np.mean(s["ndvi"][ok])) / 1000)
        monthly = {m: round(statistics.median(v), 3) for m, v in sorted(by_month.items()) if len(v) >= 1}
        monthly_all[f["id"]] = monthly

    (OUT / "grids").mkdir(exist_ok=True)
    (OUT / "scenes").mkdir(exist_ok=True)
    for old in list((OUT / "grids").glob("*.json")) + list((OUT / "scenes").glob("*.json")):
        old.unlink()

    feats = []
    for f in fields:
        fid, gi = f["id"], f["gi"]
        monthly = monthly_all[fid]
        vals = [v for m, v in monthly.items() if first_month <= m <= last_month]
        low = min(vals) if vals else None
        klass = "unknown" if len(vals) < 7 else ("perennial" if low >= 0.30 else "seasonal")
        zp = zone_polygons(f["poly"], gi, grid, to_ll)
        cen = shp_transform(to_ll, f["poly"].centroid)
        feats.append({
            "type": "Feature",
            "geometry": mapping(shp_transform(to_ll, f["poly"])),
            "properties": {
                "id": fid, "name": f"Field {fid[1:]}", "area_ha": round(f["area"], 2),
                "compactness": round(float(f["compact"]), 2), "cropland_fraction": round(f["crop"], 2),
                "class": klass, "ndvi_monthly": monthly,
                "centroid": [round(cen.x, 6), round(cen.y, 6)],
                "zone_pixels": f["counts"],
                "zones": {z: mapping(g) for z, g in zp.items()},
            },
        })
        (OUT / "grids" / f"{fid}.json").write_text(json.dumps({
            "epsg": grid["epsg"], "x0": grid["x0"], "y_top": grid["y_top"], "cell_m": 10,
            "r0": gi["r0"], "c0": gi["c0"], "nr": gi["nr"], "nc": gi["nc"],
            "inside": gi["inside"].ravel().tolist(), "az": gi["az"].ravel().tolist(), "rz": gi["rz"].ravel().tolist(),
        }), encoding="utf-8")
        ins_idx = np.flatnonzero(gi["inside"].ravel() == 1)
        scenes = []
        for d in sorted(series[fid]):
            if d < app_from:
                continue
            s = series[fid][d]
            scenes.append({
                "date": d, "scene_id": f"S2L2A-{d.replace('-', '')}",
                "cloud_pct": s["cloud"], "shadow_pct": s["shadow"], "cirrus_pct": s["cirrus"],
                "ndvi": [None if v == np.iinfo(np.int16).min else int(v) for v in s["ndvi"]],
            })
        (OUT / "scenes" / f"{fid}.json").write_text(json.dumps({"field_id": fid, "inside_pixels": len(ins_idx), "scenes": scenes}), encoding="utf-8")

    fc = {
        "type": "FeatureCollection",
        "provenance": {
            "boundaries": a.boundaries,
            "imagery": grid["source"],
            "landcover": "ESA WorldCover 2021 (CC-BY-4.0), used only to keep cropland",
            "grid": {k: grid[k] for k in ("epsg", "x0", "y_top", "nx", "ny", "cell_m", "bbox")},
        },
        "features": feats,
    }
    (OUT / "fields.geojson").write_text(json.dumps(fc), encoding="utf-8")
    cls = defaultdict(int)
    for ft in feats:
        cls[ft["properties"]["class"]] += 1
    print(f"wrote {len(feats)} fields, classes {dict(cls)}, scenes per field ~{statistics.mean(len(json.loads((OUT/'scenes'/(ft['properties']['id']+'.json')).read_text())['scenes']) for ft in feats[:5]):.0f}", file=sys.stderr)


if __name__ == "__main__":
    main()
