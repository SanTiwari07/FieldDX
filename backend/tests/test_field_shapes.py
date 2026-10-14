"""Every field shape on the map, the land with none, and the officer's corrections to them."""
import sys
from pathlib import Path

import pytest
from shapely.geometry import box, mapping

from app import areas, data
from tests.conftest import signed_in

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import build_dataset as bd  # noqa: E402
import edit_fields as ef  # noqa: E402
import ftw_global  # noqa: E402

same = lambda x, y, z=None: (x, y)  # noqa: E731  shapes already in metres: no reprojection


def test_an_earlier_year_fills_gaps_but_never_doubles_a_field():
    base = [("a", 2025, 0.9, box(0, 0, 100, 100))]
    earlier = [
        ("b", 2024, 0.8, box(50, 0, 150, 100)),     # half under field a: the same field, drawn again
        ("c", 2024, 0.8, box(200, 0, 300, 100)),    # where 2025 found nothing: a missed field
        ("d", 2024, 0.8, box(210, 0, 310, 100)),    # overlaps c, which was just added
        ("e", 2024, 0.8, box(95, 0, 195, 100)),     # 5% under field a: still fills a gap
    ]
    kept = [c[0] for c in ftw_global.fill_gaps(base, earlier)]
    assert kept == ["c", "e"]


def test_gaps_are_the_land_no_shape_covers_without_the_slivers_between_shapes():
    area = box(0, 0, 400, 200)
    shapes = [box(0, 0, 98, 200), box(101, 0, 200, 200)]   # a 3 m strip between them is not a gap
    to_ll = same
    gaps = bd.gap_features(area, shapes, to_ll)
    assert len(gaps) == 1 and gaps[0]["properties"]["status"] == "gap"
    assert gaps[0]["properties"]["area_ha"] == pytest.approx(4.0, abs=0.15)   # the right half, 200 x 200 m
    assert bd.gap_features(None, shapes, to_ll) == []


def _shapes(**kw):
    out = {}
    for key, (geom, status) in kw.items():
        out[key] = {"geometry": mapping(geom), "properties": {"key": key, "status": status,
                                                             "field_id": "F001" if status == "watched" else None}}
    return out


def test_a_drawn_field_is_cut_around_watched_fields_and_replaces_small_shapes_under_it():
    shapes = _shapes(w=(box(0, 0, 50, 100), "watched"), s=(box(60, 10, 80, 30), "small"), far=(box(300, 0, 320, 20), "small"))
    removed, pieces = ef.plan({"op": "add", "geometry": mapping(box(20, 0, 120, 100))}, shapes, box(0, 0, 400, 200), same)
    assert removed == ["s"]
    assert len(pieces) == 1 and pieces[0].bounds[0] == pytest.approx(50.5, abs=1.0)  # starts where field w ends
    with pytest.raises(ef.EditError):  # drawn entirely over a watched field
        ef.plan({"op": "add", "geometry": mapping(box(5, 5, 45, 95))}, shapes, box(0, 0, 400, 200), same)
    with pytest.raises(ef.EditError):  # drawn outside the area
        ef.plan({"op": "add", "geometry": mapping(box(500, 500, 600, 600))}, shapes, box(0, 0, 400, 200), same)


def test_split_merge_and_remove():
    shapes = _shapes(a=(box(0, 0, 100, 100), "watched"), b=(box(100, 0, 150, 100), "small"), c=(box(300, 0, 350, 50), "small"))
    area = box(0, 0, 400, 200)
    removed, pieces = ef.plan({"op": "split", "key": "a", "line": [[50, 20], [50, 80]]}, shapes, area, same)
    assert removed == ["a"] and len(pieces) == 2  # the line stops short of the edges but is stretched through
    assert sorted(round(p.area) for p in pieces) == [5000, 5000]
    with pytest.raises(ef.EditError):
        ef.plan({"op": "split", "key": "a", "line": [[200, 0], [250, 50]]}, shapes, area, same)  # misses the field
    removed, pieces = ef.plan({"op": "merge", "keys": ["a", "b"]}, shapes, area, same)
    assert removed == ["a", "b"] and len(pieces) == 1 and round(pieces[0].area) == 15000
    with pytest.raises(ef.EditError):
        ef.plan({"op": "merge", "keys": ["a", "c"]}, shapes, area, same)  # they do not touch
    assert ef.plan({"op": "remove", "key": "c"}, shapes, area, same) == (["c"], [])
    with pytest.raises(ef.EditError):
        ef.plan({"op": "remove", "key": "gone"}, shapes, area, same)


def test_the_map_gets_every_shape_but_the_demo_cannot_be_corrected():
    c = signed_in("niphad")
    gj = c.get("/api/fields.geojson").json()
    assert len(gj["features"]) == len(data.fields("niphad"))
    assert gj["editable"] is False and isinstance(gj["others"], list)
    assert all("case_reason" in f["properties"] for f in gj["features"])
    r = c.post("/api/area/fields", json={"op": "remove", "key": "ftw-1"})
    assert r.status_code == 422 and "demo" in r.json()["detail"]
    assert c.post("/api/area/fields", json={"op": "add", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 1]]]}}).status_code == 422
    with pytest.raises(areas.AreaError):
        areas.edit_fields("niphad", {"op": "explode"})


def test_inbox_rows_say_why_a_case_was_dismissed():
    rows = signed_in("niphad").get("/api/cases").json()["cases"]
    assert all("kind" in r and "green_before" in r for r in rows)
    assert {r["kind"] for r in rows if r["outcome"] != "auto_dismissed"} <= {None}
