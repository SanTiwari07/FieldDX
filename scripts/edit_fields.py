"""Apply one field officer's correction to an area's field shapes, and rebuild only what it touches.

No automatic field map is complete: around Vairag (Solapur) Fields of the World covers under half the
land with a field shape, and some shapes join two farms or split one. The officer knows the land, so
they can fix it on the map:

  add      draw a field the model missed. The shape is cut to the area and around fields already
           watched; shapes that were too small to watch and lie mostly inside it are replaced by it.
  split    draw a line across a field to cut it in two (or more).
  merge    join two or more touching shapes into one field.
  remove   this shape is not a field (a road, a house, a threshing yard).

The correction is kept in edits.json, so a full rebuild of the area applies it again. Only the new
shapes are read from the downloaded Sentinel-2 passes; fields the correction does not touch keep their
ids, pixels and closed cases. The alerts are then detected again for the whole area (a few seconds).

The last line printed is a JSON result: {"ok": true, "message": ..., "added": [...], "removed": [...]}.

Run:  python scripts/edit_fields.py --area data/areas/<area> --op '{"op": "add", "geometry": {...}}'
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pyproj
import shapely
from shapely.geometry import LineString, mapping, shape
from shapely.ops import split
from shapely.ops import transform as shp_transform

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_cases  # noqa: E402
import build_dataset as bd  # noqa: E402

MIN_PIECE_M2 = 50       # a drawn or split piece smaller than this is a slip of the pointer, not a field
ABSORB_SHARE = 0.5      # an unwatched shape at least this much inside a drawn field is replaced by it


class EditError(Exception):
    pass


def _polys(g) -> list:
    """The polygons of a geometry, largest first, without slivers."""
    parts = [p for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and p.area >= MIN_PIECE_M2]
    return sorted(parts, key=lambda p: -p.area)


def _stretch(p, q, metres: float = 30.0):
    """Move the end point p of a cut line further away from q, so a line drawn up to the field's
    boundary still cuts right through it."""
    dx, dy = p[0] - q[0], p[1] - q[1]
    d = (dx * dx + dy * dy) ** 0.5 or 1.0
    return (p[0] + dx / d * metres, p[1] + dy / d * metres)


def _write(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj), encoding="utf-8")
    tmp.replace(path)


def plan(op: dict, shapes: dict, area_utm, to_utm) -> tuple[list[str], list]:
    """What the correction removes (shape keys) and adds (polygons in the grid's CRS)."""
    kind = op.get("op")
    geom_of = lambda key: shp_transform(to_utm, shape(shapes[key]["geometry"]))  # noqa: E731

    def need(key):
        if key not in shapes:
            raise EditError("That shape is no longer on the map. Reload the map and try again.")
        return key

    if kind == "add":
        try:
            drawn = shp_transform(to_utm, shape(op["geometry"]))
        except (KeyError, TypeError, ValueError, AttributeError):
            raise EditError("Draw the field with at least three corners.")
        drawn = drawn if drawn.is_valid else drawn.buffer(0)
        g = drawn.intersection(area_utm) if area_utm is not None else drawn
        if g.area < MIN_PIECE_M2:
            raise EditError("The shape you drew is outside your area or too small to be a field.")
        watched = [geom_of(k) for k, f in shapes.items() if f["properties"]["status"] == "watched"]
        if watched:
            g = g.difference(shapely.union_all([w.buffer(0.5) for w in watched]))
        pieces = _polys(g.buffer(-1).buffer(1))
        if not pieces:
            raise EditError("That land is already inside fields that are watched. To change one, split or merge it.")
        absorbed = []
        for k, f in shapes.items():
            if f["properties"]["status"] == "watched":
                continue
            s = geom_of(k)
            if s.area > 0 and s.intersection(g).area >= ABSORB_SHARE * s.area:
                absorbed.append(k)
        return absorbed, pieces

    if kind == "split":
        key = need(op.get("key"))
        coords = op.get("line") or []
        if len(coords) < 2:
            raise EditError("Draw the cut as a line of at least two points.")
        pts = list(shp_transform(to_utm, LineString(coords)).coords)
        pts[0], pts[-1] = _stretch(pts[0], pts[1]), _stretch(pts[-1], pts[-2])
        pieces = _polys(split(geom_of(key), LineString(pts)))
        if len(pieces) < 2:
            raise EditError("Draw the line right across the field, from one side to the other.")
        return [key], pieces

    if kind == "merge":
        keys = list(dict.fromkeys(op.get("keys") or []))
        if len(keys) < 2:
            raise EditError("Choose at least two shapes to merge.")
        u = shapely.union_all([geom_of(need(k)).buffer(1.5) for k in keys]).buffer(-1.5)
        if u.geom_type != "Polygon":
            raise EditError("Only shapes that touch can be merged into one field.")
        return keys, [u]

    if kind == "remove":
        return [need(op.get("key"))], []

    raise EditError("Unknown correction.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", required=True)
    ap.add_argument("--op", required=True, help="the correction, as JSON")
    a = ap.parse_args()
    folder = Path(a.area).resolve()
    try:
        result = apply(folder, json.loads(a.op))
    except EditError as e:
        print(json.dumps({"ok": False, "message": str(e)}))
        sys.exit(3)
    print(json.dumps(result))


def apply(folder: Path, op: dict) -> dict:
    meta = json.loads((folder / "area.json").read_text(encoding="utf-8"))
    if not (folder / bd.SHAPES_FILE).exists():
        raise EditError("Rebuild this area once before correcting its fields: it was built before corrections existed.")
    s2 = folder / "raw" / "s2"
    grid = json.loads((s2 / "grid.json").read_text(encoding="utf-8"))
    to_ll = pyproj.Transformer.from_crs(grid["epsg"], "EPSG:4326", always_xy=True).transform
    to_utm = pyproj.Transformer.from_crs("EPSG:4326", grid["epsg"], always_xy=True).transform
    area_utm = bd.area_in_grid(meta, grid)
    shapes_fc = json.loads((folder / bd.SHAPES_FILE).read_text(encoding="utf-8"))
    fields_fc = json.loads((folder / "fields.geojson").read_text(encoding="utf-8"))
    edits = bd.read_edits(folder)
    shapes = {f["properties"]["key"]: f for f in shapes_fc["features"] if f["properties"]["status"] != "gap"}

    removed, pieces = plan(op, shapes, area_utm, to_utm)

    # ---- record the correction so a full rebuild applies it again
    stamp = datetime.now().replace(microsecond=0).isoformat()
    added_keys = []
    for k in removed:
        if k.startswith("officer-"):
            edits["added"] = [x for x in edits["added"] if x["key"] != k]
        elif k not in edits["removed"]:
            edits["removed"].append(k)
    n = edits.get("next", 1)
    for p in pieces:
        key = f"officer-{n}"
        n += 1
        added_keys.append(key)
        edits["added"].append({"key": key, "how": op["op"], "at": stamp,
                               "geometry": mapping(shapely.set_precision(shp_transform(to_ll, p), 1e-7))})
    edits["next"] = n

    # ---- drop the fields whose shapes went
    gone_fields = [shapes[k]["properties"]["field_id"] for k in removed if shapes[k]["properties"].get("field_id")]
    fields_fc["features"] = [f for f in fields_fc["features"] if f["properties"]["id"] not in gone_fields]
    for fid in gone_fields:
        for sub in ("grids", "scenes"):
            (folder / sub / f"{fid}.json").unlink(missing_ok=True)

    # ---- read the new shapes from the downloaded passes, nothing else
    new = gpd.GeoDataFrame({"key": added_keys, "source": [bd.OFFICER_SOURCE] * len(pieces)},
                           geometry=pieces, crs=grid["epsg"])
    wc = bd.read_band(s2 / "worldcover.tif", 1).astype(int)
    skipped, why = defaultdict(int), {}
    fields = bd.prepare(bd.select_fields(new, grid, wc, skipped, why), grid, skipped, why)
    room = bd.MAX_FIELDS - len(fields_fc["features"])
    for f in fields[max(room, 0):]:
        why[f["src"]] = "over_limit"
    fields = fields[:max(room, 0)]
    last = max((int(f["properties"]["id"][1:]) for f in fields_fc["features"]), default=0)
    for f in fields:
        last += 1
        f["id"] = f"F{last:03d}"
        f["key"], f["source"] = new.at[f["src"], "key"], bd.OFFICER_SOURCE
    if fields:
        dates = json.loads((s2 / "dates.json").read_text(encoding="utf-8"))
        series = bd.cut_series(fields, s2, dates)
        app_from = fields_fc.get("provenance", {}).get("app_from") or bd.APP_FROM
        months = bd.year_window(max(dates))
        fields_fc["features"] += [bd.write_field(folder, f, series[f["id"]], grid, to_ll, app_from, months)
                                  for f in fields]
    if not fields_fc["features"]:
        raise EditError("An area needs at least one watched field.")
    fields_fc.setdefault("provenance", {})["officer_shapes"] = len(edits["added"])

    # ---- the map's shapes and gaps
    field_of = {f["src"]: f["id"] for f in fields}
    keep = [f for k, f in shapes.items() if k not in removed]
    added_feats = bd.shapes_collection(new, why, field_of, area_utm, to_ll)["features"]
    added_feats = [f for f in added_feats if f["properties"]["status"] != "gap"]
    all_utm = [shp_transform(to_utm, shape(f["geometry"])) for f in keep + added_feats]
    shapes_fc["features"] = keep + added_feats + bd.gap_features(area_utm, all_utm, to_ll)

    _write(folder / "fields.geojson", fields_fc)
    _write(folder / bd.SHAPES_FILE, shapes_fc)
    _write(folder / bd.EDITS_FILE, edits)
    summary = build_cases.write_cases(folder)

    added = [{"key": f["properties"]["key"], "status": f["properties"]["status"],
              "field_id": f["properties"]["field_id"], "area_ha": f["properties"]["area_ha"]} for f in added_feats]
    return {"ok": True, "op": op["op"], "added": added, "removed": removed, "removed_fields": gone_fields,
            "message": message(op["op"], added, removed, gone_fields), "alerts": summary}


REASON = {
    "small": f"under {bd.MIN_WHOLE_HA} ha, too small to read from 10 m pixels",
    "tiny_core": "too thin to hold enough clear 10 m pixels",
    "cropland": "mostly not cropland on the land-cover map",
    "edge": "too close to the edge of the downloaded imagery",
    "large": f"over {bd.MAX_HA:.0f} ha",
    "over_limit": f"beyond the {bd.MAX_FIELDS} fields an area keeps",
}


def message(kind: str, added: list, removed: list, gone: list) -> str:
    watched = [x for x in added if x["status"] == "watched"]
    other = [x for x in added if x["status"] != "watched"]
    names = ", ".join(f"Field {x['field_id'][1:]}" for x in watched)
    if kind == "remove":
        return ("Removed. It is no longer a field" + (f", and Field {gone[0][1:]} is no longer watched." if gone else "."))
    head = {"add": "Field added", "split": "Field split", "merge": "Fields merged"}[kind]
    parts = [f"{head}: watching {names}, read from the satellite passes already downloaded." if watched
             else f"{head}."]
    for x in other:
        parts.append(f"The {x['area_ha']} ha shape is on the map but not watched: {REASON.get(x['status'], x['status'])}.")
    if kind == "add" and len(removed):
        parts.append(f"It replaces {len(removed)} smaller shape{'s' if len(removed) != 1 else ''} the model had drawn there.")
    return " ".join(parts)


if __name__ == "__main__":
    main()
