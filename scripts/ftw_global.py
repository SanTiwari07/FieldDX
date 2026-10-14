"""Read real field boundaries for an area from the published Fields of the World global map.

FTW Global (Robinson et al. 2026, CC-BY-4.0) is the PRUE model run wall to wall over Sentinel-2 for
2024 and 2025: about 3.2 billion field polygons, stored as GeoParquet per state on Source Cooperative.
Only the row groups whose bounding boxes touch the area are read over HTTP, so a 9 x 9 km area costs
a minute or two, not the whole 3 GB state file.

Keeps the fields whose centre is inside the area polygon, or exactly the fields the officer picked on
the map (each pick is the point they clicked; the field is the polygon holding it). The latest year is
the base map. Each year misses some fields the other found, so a field from an earlier year is added
where it fills a gap: no more than a quarter of it overlaps a latest-year field. Around Vairag
(Solapur) this adds 47 fields to 465. Most of the land the two years disagree on is thin slivers along
shared edges, not missing fields, so those are not added.

Writes polygons.parquet (ftw_id, confidence, year, geometry) in the same form ftw_fields.py does, so
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


GAP_OVERLAP = 0.25  # an earlier-year field fills a gap if at most this share of it is under a latest-year field


def fill_gaps(base: list, earlier: list) -> list:
    """Earlier-year fields that lie mostly where the base map has no field, newest year first, never
    overlapping each other by more than the same share. Rows are (id, year, confidence, geometry)."""
    from shapely.strtree import STRtree
    fix = lambda g: g if g.is_valid else g.buffer(0)  # noqa: E731
    base_g = [fix(c[3]) for c in base]
    tree = STRtree(base_g) if base_g else None
    added: list = []
    out = []
    for c in sorted(earlier, key=lambda c: -c[1]):
        g = fix(c[3])
        if g.is_empty or g.area <= 0:
            continue
        near = [base_g[i] for i in tree.query(g)] if tree is not None else []
        near += [a for a in added if a.intersects(g)]
        if sum(g.intersection(t).area for t in near) <= GAP_OVERLAP * g.area:
            out.append((c[0], c[1], c[2], g))
            added.append(g)
    return out


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
    cands = [(str(r[0]), r[1], r[2], g) for r, g in zip(rows, geoms)
             if r[1] is not None and g is not None and not g.is_empty]
    if picks:
        keep = []
        for p in picks:  # the latest year's field under the click, else an earlier year's
            hits = sorted((c for c in cands if c[3].contains(p)), key=lambda c: -c[1])
            if hits and hits[0][0] not in {k[0] for k in keep}:
                keep.append(hits[0])
    else:
        inside = [c for c in cands if area.contains(c[3].representative_point())]
        keep = [c for c in inside if c[1] == latest]
        keep += fill_gaps(keep, [c for c in inside if c[1] != latest])
    n_fill = sum(1 for k in keep if k[1] != latest)
    print(f"{len(rows)} polygons touch the area; {len(keep)} inside it from {latest}"
          + (f" ({n_fill} of them from earlier years, filling gaps)" if n_fill else ""), file=sys.stderr, flush=True)
    if not keep:
        print("None of the Fields of the World fields lie inside this area.", file=sys.stderr)
        sys.exit(3)

    out = folder / "raw" / "ftw_global"
    out.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame({"ftw_id": [k[0] for k in keep], "confidence": [k[2] for k in keep],
                            "year": [int(k[1]) for k in keep]},
                           geometry=[k[3] for k in keep], crs="EPSG:4326")
    gdf.to_parquet(out / "polygons.parquet")
    (out / "source.json").write_text(json.dumps({
        "source": (f"Fields of the World Global {latest}"
                   + (f", gaps filled from earlier years ({n_fill} fields)" if n_fill else "")
                   + f" (PRUE model, CC-BY-4.0), partition {part['code']}"),
        "year": int(latest), "fields": len(keep), "filled": n_fill, "url": part["parquet"],
    }, indent=1), encoding="utf-8")
    print(f"wrote {len(keep)} fields to {out / 'polygons.parquet'}", file=sys.stderr)


if __name__ == "__main__":
    main()
