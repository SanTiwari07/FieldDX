"""The zone geometry that turns a real field outline into pixels (scripts/build_dataset.py)."""
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import build_dataset as bd  # noqa: E402

GRID = {"x0": 400000, "y_top": 2220000}


def L_shape():
    # an L-shaped field with 100 m wide arms and its north-east corner cut away: nothing like a rectangle
    x, y = 400100, 2219600
    return Polygon([(x, y), (x + 240, y), (x + 240, y + 100), (x + 100, y + 100), (x + 100, y + 240), (x, y + 240)])


def test_zones_partition_the_shape_and_follow_its_form():
    poly = L_shape()
    g = bd.build_grid(poly, GRID)
    inside, az, rz = g["inside"] == 1, g["az"], g["rz"]
    # pixel centres inside the polygon
    assert abs(inside.sum() * 100 - poly.area) / poly.area < 0.2
    # every analysis pixel is inside the field and the outermost 10 m ring is never analysed
    assert ((az >= 0) <= inside).all()
    assert ((az < 0) & inside).sum() > 0
    # interior quadrants and edges both exist, and the raw ring sits on the boundary side
    zones = {bd.ZONES[k] for k in np.unique(az[az >= 0])}
    assert {"in_nw", "in_sw", "in_se", "edge_n", "edge_s", "edge_e", "edge_w"} <= zones
    assert "in_ne" not in zones  # the cut-away corner has no interior: zones follow the real shape
    assert (rz >= 0).sum() > (az[inside] >= 0).sum() * 0.2


def test_compass_sectors_follow_the_diagonals():
    assert bd.sector(0, 5) == "n" and bd.sector(0, -5) == "s" and bd.sector(5, 0) == "e" and bd.sector(-5, 1) == "w"
    assert bd.quadrant(3, 3) == "ne" and bd.quadrant(-3, -3) == "sw" and bd.quadrant(-3, 3) == "nw"


def test_the_scene_mask_recipe_matches_pragya():
    # Cloud Score+ at 0.60 and SCL classes 3 (shadow), 8, 9 (cloud), 10 (cirrus) are masked, plus no-data and saturated
    assert bd.CS_MIN == 0.60
    assert {3, 8, 9, 10} <= bd.SCL_BAD and {0, 1} <= bd.SCL_BAD and 4 not in bd.SCL_BAD and 5 not in bd.SCL_BAD
