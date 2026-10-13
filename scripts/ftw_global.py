"""Read real field boundaries for an area from the published Fields of the World global map.

FTW Global (Robinson et al. 2026, CC-BY-4.0) is the PRUE model run wall to wall over Sentinel-2 for
2024 and 2025: about 3.2 billion field polygons, stored as GeoParquet per state on Source Cooperative.
Only the row groups whose bounding boxes touch the area are read over HTTP, so a 9 x 9 km area costs
a minute or two, not the whole 3 GB state file.

Keeps the latest year present, then the fields whose centre is inside the area polygon, or exactly the
fields the officer picked on the map (each pick is the point they clicked; the field is the polygon
holding it). Writes polygons.parquet in the same form ftw_fields.py does, so
build_dataset.py reads either.

Run:  python scripts/ftw_global.py --area data/areas/<area>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
import geopandas as gpd
import shapely
from shapely.geometry import Point, shape


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", required=True, help="the area folder, holding area.json")
    a = ap.parse_args()
    folder = Path(a.area)
    meta = json.loads((folder / "area.json").read_text(encoding="utf-8"))
    part = meta.get("partition") or {}
    if not part.get("parquet"):
        print("No Fields of the World partition for this area.", file=sys.stderr)
        sys.exit(2)
    area = shape(meta["geometry"])
    w, s, e, n = area.bounds
    picks = [Point(p[0], p[1]) for p in (meta.get("picked_points") or [])]

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    print(f"reading {part['code']} fields inside {w:.4f},{s:.4f},{e:.4f},{n:.4f}", file=sys.stderr, flush=True)
    rows = con.execute(f"""
        SELECT id, year("determination:datetime") AS yr, confidence, ST_AsWKB(geometry) AS wkb
        FROM read_parquet('{part["parquet"]}')
        WHERE bbox.xmax >= ? AND bbox.xmin <= ? AND bbox.ymax >= ? AND bbox.ymin <= ?
    """, [w, e, s, n]).fetchall()
    if not rows:
        print("Fields of the World has no fields inside this area.", file=sys.stderr)
        sys.exit(3)

    latest = max(r[1] for r in rows if r[1] is not None)
    geoms = shapely.from_wkb([bytes(r[3]) for r in rows])
    keep = []
    for r, g in zip(rows, geoms):
        if r[1] != latest or g is None or g.is_empty:
            continue
        if picks:
            if any(g.contains(p) for p in picks):
                keep.append((str(r[0]), r[2], g))
        elif area.contains(g.representative_point()):
            keep.append((str(r[0]), r[2], g))
    print(f"{len(rows)} polygons touch the area; {len(keep)} from {latest} are inside it", file=sys.stderr, flush=True)
    if not keep:
        print("None of the Fields of the World fields lie inside this area.", file=sys.stderr)
        sys.exit(3)

    out = folder / "raw" / "ftw_global"
    out.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame({"ftw_id": [k[0] for k in keep], "confidence": [k[1] for k in keep]},
                           geometry=[k[2] for k in keep], crs="EPSG:4326")
    gdf.to_parquet(out / "polygons.parquet")
    (out / "source.json").write_text(json.dumps({
        "source": f"Fields of the World Global {latest} (PRUE model, CC-BY-4.0), partition {part['code']}",
        "year": int(latest), "fields": len(keep), "url": part["parquet"],
    }, indent=1), encoding="utf-8")
    print(f"wrote {len(keep)} fields to {out / 'polygons.parquet'}", file=sys.stderr)


if __name__ == "__main__":
    main()
