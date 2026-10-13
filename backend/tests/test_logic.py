"""Engine logic on a tiny hand-built dataset with known answers (see fixture_data.py)."""
from datetime import date, timedelta

import pytest
from pytest import approx as pytest_approx

from app import config, data, db
from tests import fixture_data as fx
from tests.conftest import signed_in

D = date.fromisoformat


def rain(d):
    # steady rain until 28 Sep, then a dry spell to the end of the data
    return 5.0 if d <= date(2026, 9, 28) and d.day % 2 == 0 else 0.0


def humid(d):
    return 88 if date(2026, 9, 10) <= d <= date(2026, 9, 24) else 55


def east_edge(r, c):
    return c >= fx.NC - 3


def hero(d, r, c):
    if not east_edge(r, c):
        return 0.0
    return {date(2026, 9, 25): -0.07, date(2026, 9, 30): -0.13, date(2026, 10, 5): -0.19, date(2026, 10, 10): -0.23}.get(d, -0.23 if d > date(2026, 10, 10) else 0.0)


def haze(d, r, c):
    if d == date(2026, 10, 5):
        return None if (r + c) % 5 < 2 else -0.22
    return 0.0


def boundary(d, r, c):
    return -0.30 if (d >= date(2026, 10, 5) and c == fx.NC - 1) else 0.0


def wave(d, r, c):
    return -0.30 if d >= date(2026, 10, 5) else 0.0


def single_pass(d, r, c):
    return -0.25 if (d == date(2026, 10, 10) and r < 7 and c < 10) else 0.0


def scattered(d, r, c):
    quad = (r < 7 and c >= 10) or (r >= 7 and c < 10)
    return -0.15 if (quad and r >= 3 and r <= 10 and 3 <= c <= 16 and d >= date(2026, 10, 5)) else 0.0


def spreading(d, r, c):
    inside = 3 <= r <= 10 and 3 <= c <= 16
    if not inside:
        return 0.0
    nw, ne, sw = r < 7 and c < 10, r < 7 and c >= 10, r >= 7 and c < 10
    table = {
        date(2026, 9, 25): (-0.06, 0, 0), date(2026, 9, 30): (-0.12, 0, 0),
        date(2026, 10, 5): (-0.16, -0.10, 0), date(2026, 10, 10): (-0.18, -0.14, -0.10),
    }
    v = table.get(d)
    if not v:
        return 0.0
    return v[0] if nw else v[1] if ne else v[2] if sw else 0.0


def flooded(d, r, c):
    return -1.0 if d >= date(2026, 10, 5) else 0.0  # NDVI of about -0.25: open water


def build_all(tmp):
    fields = {
        "HERO": {"ev": hero}, "N1": {}, "N2": {}, "N3": {},
        "HAZE": {"ev": haze}, "EDGE": {"ev": boundary},
        "P1": {"class": "perennial", "ev": wave}, "P2": {"class": "perennial", "ev": wave},
        "P3": {"class": "perennial", "ev": wave}, "P4": {"class": "perennial", "ev": wave},
        "WAIT": {"ev": single_pass}, "ODD": {"class": "unknown", "ev": scattered}, "PEST": {"ev": spreading},
        "WET": {"class": "unknown", "ev": flooded},
        # small fields read as one zone, about 10 km from the rest so they are nobody's neighbour
        "SMALL": {"mode": "whole", "class": "unknown", "lon": 74.20, "ev": hero},
        "SMALLHAZE": {"mode": "whole", "class": "unknown", "lon": 74.21, "ev": haze},
    }
    cases = [
        {"id": "HERO", "field_id": "HERO", "alert_date": "2026-09-30"},
        {"id": "HAZE", "field_id": "HAZE", "alert_date": "2026-10-05"},
        {"id": "EDGE", "field_id": "EDGE", "alert_date": "2026-10-05"},
        {"id": "P1", "field_id": "P1", "alert_date": "2026-10-05"},
        {"id": "WAIT", "field_id": "WAIT", "alert_date": "2026-10-10"},
        {"id": "ODD", "field_id": "ODD", "alert_date": "2026-10-05"},
        {"id": "PEST", "field_id": "PEST", "alert_date": "2026-09-30"},
        {"id": "WET", "field_id": "WET", "alert_date": "2026-10-05"},
        {"id": "SMALL", "field_id": "SMALL", "alert_date": "2026-09-30"},
        {"id": "SMALLHAZE", "field_id": "SMALLHAZE", "alert_date": "2026-10-05"},
    ]
    fx.build(tmp, fields, weather={"rain": rain, "rh": humid}, cases=cases)


@pytest.fixture()
def ds(tmp_path, monkeypatch):
    from app import pipeline, service
    build_all(tmp_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    data.clear_caches()
    pipeline._cached.cache_clear()
    db.reset()
    yield tmp_path
    data.clear_caches()
    pipeline._cached.cache_clear()


def case(cid):
    from app.pipeline import build_case
    return build_case(fx.AREA, cid)


def test_edge_drop_in_a_harvest_window_is_still_a_field_case(ds):
    r = case("HERO")
    assert r.outcome == "field_case"
    assert r.hypotheses[0].id == "H7" and r.hypotheses[0].confidence == "high"
    assert r.next_check.check_id == "drip_line" and "east" in r.next_check.label
    assert r.severity in ("high", "medium")


def test_hazy_scene_is_dismissed_as_an_artefact(ds):
    r = case("HAZE")
    assert r.outcome == "auto_dismissed" and r.stage_outcome.hypothesis_id == "H1"
    assert "haze" in r.stage_outcome.reason.lower() or "cloud" in r.stage_outcome.reason.lower()


def test_boundary_only_drop_is_dismissed(ds):
    r = case("EDGE")
    assert r.outcome == "auto_dismissed" and r.stage_outcome.hypothesis_id == "H2"


def test_field_wide_loss_shared_by_neighbours_in_the_pruning_window_is_dismissed(ds):
    r = case("P1")
    assert r.outcome == "auto_dismissed" and r.stage_outcome.hypothesis_id == "H3"
    assert "pruning" in r.stage_outcome.reason.lower()
    assert "farmer" in r.stage_outcome.confirm_with.lower()


def test_a_single_clear_pass_waits_for_the_next_one(ds):
    r = case("WAIT")
    assert r.outcome == "watch" and r.stage_outcome.kind == "watch"
    assert r.next_check is None and r.severity is None


def test_scattered_loss_is_unexplained_and_offers_a_visit(ds):
    r = case("ODD")
    assert r.outcome == "unexplained" and r.next_check.check_id == "visit"
    assert r.visit_checklist and r.severity is not None


def test_spreading_patch_points_to_pests_and_asks_for_the_leaves(ds):
    r = case("PEST")
    assert r.outcome == "field_case" and r.hypotheses[0].id == "H8"
    assert r.next_check.check_id == "leaf_undersides"
    assert "drip_line" not in {c.check_id for c in r.next_check.candidates}


def test_open_water_on_a_field_is_standing_water_not_a_failing_crop(ds):
    r = case("WET")
    assert r.outcome == "field_case" and r.hypotheses[0].id == "H10"
    assert any("open water" in ln.text for ln in r.hypotheses[0].for_lines)
    assert r.next_check.check_id == "water_look"


@pytest.mark.parametrize("cid", ["HERO", "HAZE", "EDGE", "P1", "WAIT", "ODD", "PEST", "WET"])
def test_every_line_cites_evidence_and_the_template_narrative_validates(ds, cid):
    from app.narrative import template_narrative, validate_narrative
    r = case(cid)
    valid = {e.id for e in r.evidence}
    for h in r.hypotheses:
        for ln in h.for_lines + h.against_lines:
            assert ln.evidence_ids and set(ln.evidence_ids) <= valid
    assert validate_narrative(template_narrative(r), r) == []


def test_closing_a_field_case_adds_evidence_and_reranks(ds):
    from app.main import app
    c = signed_in(fx.AREA)
    j = c.post("/api/cases/HERO/close", json={"check_id": "drip_line", "outcome": "dry", "note": "Valve blocked"}).json()
    assert j["outcome"] == "resolved" and j["evidence"][-1]["source"] == "Officer field visit"
    assert j["resolution"]["confirmed_id"] == "H7"
    assert c.post("/api/cases/HERO/close", json={"check_id": "drip_line", "outcome": "dry"}).status_code == 409
    before = next(h for h in case("PEST").hypotheses if h.id == "H8").score
    clean = c.post("/api/cases/PEST/close", json={"check_id": "leaf_undersides", "outcome": "clean"}).json()
    after = next(h for h in clean["hypotheses"] if h["id"] == "H8")
    assert clean["resolution"]["ranking_before"][0] == "H8"
    assert after["score"] == pytest_approx(before - config.OUTCOME_WEIGHT)  # clean leaves lower pests, not erase them
    assert any("clean" in ln["text"].lower() for ln in after["against_lines"])


def test_an_unexplained_case_can_be_closed_with_what_the_officer_found(ds):
    from app.main import app
    c = signed_in(fx.AREA)
    j = c.post("/api/cases/ODD/close", json={"check_id": "visit", "outcome": "harvested", "note": "Cut last week"}).json()
    assert j["outcome"] == "resolved" and j["resolution"]["confirmed_id"] == "H3"
    none = c.post("/api/cases/ODD/close", json={"check_id": "visit", "outcome": "other"})
    assert none.status_code == 409


def test_a_watch_case_cannot_be_closed(ds):
    from app.main import app
    c = signed_in(fx.AREA)
    assert c.post("/api/cases/WAIT/close", json={"check_id": "visit", "outcome": "harvested"}).status_code == 422


def test_cloudy_scenes_never_carry_a_number(ds):
    from app.main import app
    c = signed_in(fx.AREA)
    s = c.get("/api/cases/HAZE/series").json()
    assert all(isinstance(row["zones"]["in_nw"]["ndvi"], (float, type(None))) for row in s["scenes"])
    r = c.get("/api/cases/HAZE/raster?scene=2026-10-05").json()
    assert r["quality"] == "partial" and any(2 in row for row in r["mask"])
    masked = [(y, x) for y, row in enumerate(r["mask"]) for x, v in enumerate(row) if v == 2]
    assert all(r["ndvi"][y][x] is None for y, x in masked)


def test_baseline_never_reaches_back_into_the_monsoon(ds):
    from app.tools.common import Series
    f = data.fields(fx.AREA)["HERO"]
    ser = Series(f, D("2026-10-05"))
    a, b = ser.baseline_dates
    assert (D("2026-10-05") - a).days <= 75 and (D("2026-10-05") - b).days >= 20


def test_a_small_field_is_read_as_one_zone_and_never_overclaims(ds):
    r = case("SMALL")
    skipped = {e.tool for e in r.evidence}
    assert "boundary_check" not in skipped and "spatial_pattern" not in skipped  # skipped tools add no evidence
    assert r.headline and r.headline.zone == "__field__" and r.headline.zone_label == "Whole field"
    assert all(h.confidence != "high" for h in r.hypotheses if h.stage == 3)
    assert r.outcome in ("unexplained", "field_case") and "reads it as one" in r.limits
    c = signed_in(fx.AREA)
    m = c.get("/api/cases/SMALL/map").json()
    assert [z["id"] for z in m["zones"]] == ["whole"] and m["mode"] == "whole"
    s = c.get("/api/cases/SMALL/series").json()
    assert [z["id"] for z in s["zones"]] == ["whole"] and all(set(row["zones"]) == {"whole"} for row in s["scenes"])
    assert c.get("/api/cases/SMALL/raster").status_code == 200
    with c.stream("GET", "/api/cases/SMALL/investigate?pace=0") as resp:
        text = "".join(resp.iter_text())
    assert "too small to separate its edges" in text and "read as one zone" in text


def test_a_small_field_still_has_its_cloud_artefacts_dismissed(ds):
    r = case("SMALLHAZE")
    assert r.outcome == "auto_dismissed" and r.stage_outcome.hypothesis_id == "H1"
