"""Invariants that must hold on the real dataset, whatever the satellites saw this season."""
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import shape

from app import config, data
from app.narrative import template_narrative, validate_narrative
from app.pipeline import build_case

ALLOWED = {"auto_dismissed", "area_alert", "field_case", "unexplained", "watch"}


@pytest.fixture(scope="module", autouse=True)
def real_data():
    data.clear_caches()
    assert config.DATA_DIR.name == "data", "these tests read the real dataset in data/"
    yield


def test_the_dataset_is_real_and_complete():
    fields = data.fields()
    assert len(fields) >= 30
    prov = data.provenance()
    assert "Fields of the World" in prov["boundaries"] and "Sentinel-2" in prov["imagery"]
    meta = data.weather_meta()
    assert "Open-Meteo" in meta["source"]
    assert data.weather()[-1].date >= date(2026, 10, 10)
    assert "simulat" not in json.dumps(prov).lower() and "fixture" not in data.cases_file()["banner"].lower()


def test_field_shapes_are_real_polygons_not_squares():
    raw = json.loads((config.DATA_DIR / "fields.geojson").read_text(encoding="utf-8"))
    verts = []
    for ft in raw["features"]:
        g = shape(ft["geometry"])
        assert g.is_valid and 0.5 <= ft["properties"]["area_ha"] <= 13
        verts.append(len(g.exterior.coords) - 1)
    assert max(verts) > 6 and len(set(verts)) > 3  # varied outlines, not a fixed rectangle


def test_every_field_grid_and_scene_line_up():
    for fid in data.fields():
        g = data.grid(fid)
        assert g.cells.size == int(g.inside.sum()) >= 40
        assert (g.az[g.inside] >= -1).all() and g.az.max() <= 7
        for sc in data.scenes(fid):
            assert sc.px.shape == (g.cells.size,)
            ok = ~np.isnan(sc.px)
            assert ((sc.px[ok] >= -0.2) & (sc.px[ok] <= 1.0)).all()


def test_every_case_investigates_and_cites_only_real_evidence():
    specs = data.case_specs()
    assert specs, "build_cases.py found no alerts"
    for c in specs:
        r = build_case(c["id"])
        assert r.outcome in ALLOWED
        ids = {e.id for e in r.evidence}
        assert len(ids) >= 4
        for h in r.hypotheses:
            for ln in h.for_lines + h.against_lines:
                assert ln.evidence_ids and set(ln.evidence_ids) <= ids
        assert validate_narrative(template_narrative(r), r) == []
        if r.outcome == "auto_dismissed":
            assert r.stage_outcome.reason
        if r.outcome in ("field_case", "unexplained"):
            assert r.next_check is not None


def test_alerts_are_detected_not_hand_picked():
    from app.tools.common import Series
    for c in data.case_specs()[:10]:
        f = data.fields()[c["field_id"]]
        d = date.fromisoformat(c["alert_date"])
        sc = next(s for s in data.scenes(f.id) if s.date == d)
        ser = Series(f, d)
        worst = min((ser.delta(sc, z) for z in data.ALL_ZONES if ser.delta(sc, z) is not None), default=0)
        assert worst <= config.SIGNIFICANT_DROP


def test_cloudy_passes_carry_no_pixel_values(client):
    for fid in list(data.fields())[:12]:
        ctx_case = next((c for c in data.case_specs() if c["field_id"] == fid), None)
        if not ctx_case:
            continue
        cloudy = [s for s in data.scenes(fid) if np.isnan(s.px).mean() > 0.5]
        if not cloudy:
            continue
        r = client.get(f"/api/cases/{ctx_case['id']}/raster?scene={cloudy[0].date}")
        if r.status_code == 200 and r.json()["quality"] == "cloudy":
            body = r.json()
            assert body["stats"] is None and body["visible"] == 0.0
            assert all(v is None for row in body["ndvi"] for v in row)
            return
    pytest.skip("no cloudy pass among the first fields")


def test_api_serves_the_whole_workspace(client):
    body = client.get("/api/cases").json()
    assert body["cases"] and "Real data" in body["banner"]
    cid = body["cases"][0]["id"]
    for path in ("", "/map", "/series", "/raster"):
        assert client.get(f"/api/cases/{cid}{path}").status_code == 200
    m = client.get(f"/api/cases/{cid}/map").json()
    assert len(m["zones"]) == 8 and m["outline"]
    with client.stream("GET", f"/api/cases/{cid}/investigate?pace=0") as resp:
        text = "".join(resp.iter_text())
    assert "event: evidence" in text and "event: narrative" in text and text.rstrip().endswith("data: {}")
    gj = client.get("/api/fields.geojson").json()
    assert len(gj["features"]) == len(data.fields())


def test_an_open_case_can_be_closed_with_a_finding(client):
    open_case = next(c for c in client.get("/api/cases").json()["cases"] if c["outcome"] in ("field_case", "unexplained"))
    r = client.get(f"/api/cases/{open_case['id']}").json()
    nc = r["next_check"]
    key = nc["outcomes"][0]["key"]
    j = client.post(f"/api/cases/{open_case['id']}/close", json={"check_id": nc["check_id"], "outcome": key, "note": "test"}).json()
    assert j["outcome"] == "resolved" and j["evidence"][-1]["source"] == "Officer field visit"
    assert client.post("/api/admin/reset").json() == {"ok": True}
    assert client.get(f"/api/cases/{open_case['id']}").json()["outcome"] != "resolved"
