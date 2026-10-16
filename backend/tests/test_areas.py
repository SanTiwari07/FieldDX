"""Sign-in, areas and scoping: an officer sees their own area and nothing else."""
import json
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import areas, config, data, db
from app.main import app
from tests import fixture_data as fx
from tests.conftest import signed_in
from tests.test_logic import build_all

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import build_area  # noqa: E402
import build_dataset  # noqa: E402

SQUARE = {"type": "Polygon", "coordinates": [[[74.10, 20.06], [74.12, 20.06], [74.12, 20.08], [74.10, 20.08], [74.10, 20.06]]]}


@pytest.fixture()
def two_areas(tmp_path, monkeypatch):
    """The real Niphad area next to the hand-built fixture area, in one data folder."""
    from app import pipeline
    build_all(tmp_path)
    shutil.copytree(Path(config.ROOT) / "data" / "areas" / "niphad", tmp_path / "areas" / "niphad",
                    ignore=shutil.ignore_patterns("raw"))
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(areas, "enqueue", lambda area_id: None)  # never start a real build in tests
    data.clear_caches()
    pipeline._cached.cache_clear()
    db.reset()
    yield tmp_path
    data.clear_caches()
    pipeline._cached.cache_clear()


def test_nothing_is_served_without_signing_in():
    c = TestClient(app)
    for path in ("/api/cases", "/api/home", "/api/me", "/api/fields.geojson", "/api/cases/F010"):
        assert c.get(path).status_code == 401, path
    assert c.post("/api/admin/reset").status_code == 401


def test_register_sign_out_and_back_in():
    c = TestClient(app)
    assert c.post("/api/auth/register", json={"name": "Asha", "username": "x", "pin": "1234"}).status_code == 422
    assert c.post("/api/auth/register", json={"name": "Asha", "username": "asha.k", "pin": "12"}).status_code == 422
    me = c.post("/api/auth/register", json={"name": "Asha K", "username": "Asha.K", "pin": "2468"}).json()
    assert me["officer"]["username"] == "asha.k" and me["area"] is None
    assert c.post("/api/auth/register", json={"name": "Other", "username": "asha.k", "pin": "1357"}).status_code == 409
    # no area yet: the case routes ask for one instead of showing someone else's
    assert c.get("/api/cases").status_code == 409
    assert c.post("/api/auth/logout").json() == {"ok": True}
    assert c.get("/api/me").status_code == 401
    assert c.post("/api/auth/login", json={"username": "asha.k", "pin": "0000"}).status_code == 401
    assert c.post("/api/auth/login", json={"username": "ASHA.K", "pin": "2468"}).status_code == 200
    assert c.get("/api/me").json()["officer"]["name"] == "Asha K"


def test_the_demo_officer_works_in_the_shipped_area_only():
    c = TestClient(app)
    me = c.post("/api/auth/demo").json()
    assert me["officer"]["demo"] and me["area"]["id"] == config.DEMO_AREA and me["area"]["status"] == "ready"
    assert c.post("/api/auth/login", json={"username": "demo", "pin": "anything"}).status_code == 401
    assert c.post("/api/me/area", json={"area_id": "somewhere-else"}).status_code == 403
    assert c.post("/api/areas", json={"name": "Mine", "geometry": SQUARE, "mode": "draw"}).status_code == 403
    home = c.get("/api/home").json()
    assert home["fields"] == len(data.fields(config.DEMO_AREA)) and home["alerts"] == len(data.case_specs(config.DEMO_AREA))
    assert sum(home["counts"].values()) == home["alerts"]


def test_an_officer_never_sees_another_areas_cases(two_areas):
    here = signed_in(fx.AREA)
    there = signed_in("niphad")
    mine = {c["id"] for c in here.get("/api/cases").json()["cases"]}
    theirs = {c["id"] for c in there.get("/api/cases").json()["cases"]}
    assert mine and theirs and not (mine & theirs)
    assert here.get("/api/cases/HERO").status_code == 200
    assert there.get("/api/cases/HERO").status_code == 404
    other = next(iter(theirs))
    for path in ("", "/map", "/series", "/raster"):
        assert here.get(f"/api/cases/{other}{path}").status_code == 404
    assert len(here.get("/api/fields.geojson").json()["features"]) == len(data.fields(fx.AREA))
    # a finding in one area does not leak into the other, and a reset stays in its own area
    assert here.post("/api/cases/HERO/close", json={"check_id": "drip_line", "outcome": "dry"}).status_code == 200
    assert db.get_outcome(fx.AREA, "HERO") and db.get_outcome("niphad", "HERO") is None
    there.post("/api/admin/reset")
    assert db.get_outcome(fx.AREA, "HERO")


def test_an_area_is_created_from_a_drawn_polygon_and_queued(two_areas, monkeypatch):
    from app import places
    c = signed_in(fx.AREA)
    part = {"code": "IN_MH", "country": "IN", "parquet": "https://example.invalid/IN_MH.parquet"}
    monkeypatch.setattr(places, "ftw_partition", lambda country, sub: part if (country, sub) == ("IN", "MH") else None)
    big = {"type": "Polygon", "coordinates": [[[74.0, 20.0], [74.3, 20.0], [74.3, 20.3], [74.0, 20.3], [74.0, 20.0]]]}
    r = c.post("/api/areas", json={"name": "Too big", "geometry": big, "mode": "draw", "partition": {"code": "IN_MH"}})
    assert r.status_code == 422 and "km²" in r.json()["detail"]
    r = c.post("/api/areas", json={"name": "Nowhere", "geometry": SQUARE, "mode": "draw", "partition": {"code": "XX_YY"}})
    assert r.status_code == 422 and "Fields of the World" in r.json()["detail"]
    r = c.post("/api/areas", json={"name": "Pimpalgaon farms", "region": "Nashik", "geometry": SQUARE,
                                   "mode": "draw", "partition": {"code": "IN_MH", "parquet": "https://evil.example/x"}})
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["area"]["name"] == "Pimpalgaon farms" and me["area"]["status"] in ("queued", "failed", "interrupted")
    meta = json.loads((two_areas / "areas" / me["area"]["id"] / "area.json").read_text(encoding="utf-8"))
    assert meta["partition"]["parquet"].startswith("https://example.invalid")  # the server's URL, not the browser's
    assert 4 < meta["km2"] < 6 and meta["bbox"] == [74.1, 20.06, 74.12, 20.08]
    # the new area is not built yet, so its cases are not served
    assert c.get("/api/cases").status_code == 409
    assert c.get("/api/area/build").json()["area"]["id"] == me["area"]["id"]


def test_the_harvest_season_is_inferred_from_the_areas_own_ndvi(tmp_path):
    months = {"2025-09": 0.62, "2025-10": 0.64, "2025-11": 0.31, "2025-12": 0.28, "2026-01": 0.30,
              "2026-02": 0.52, "2026-03": 0.55, "2026-04": 0.33}
    feats = [{"properties": {"class": "seasonal", "ndvi_monthly": {m: v + k * 0.01 for m, v in months.items()}}} for k in range(5)]
    feats.append({"properties": {"class": "perennial", "ndvi_monthly": {m: 0.6 for m in months}}})
    (tmp_path / "fields.geojson").write_text(json.dumps({"features": feats}), encoding="utf-8")
    (tmp_path / "build.json").write_text("{}", encoding="utf-8")
    build_area.seasons(tmp_path, build_area.Progress(tmp_path))
    cal = json.loads((tmp_path / "calendar.json").read_text(encoding="utf-8"))["classes"]
    wins = cal["seasonal"]["windows"]
    assert [(w["start"], w["end"]) for w in wins] == [("03-01", "04-30"), ("10-01", "11-30")]
    assert all(not w["verified"] and "Inferred" in w["source"] for w in wins)
    assert cal["perennial"]["windows"] == []


def test_the_class_window_is_the_twelve_months_before_the_data_ends():
    assert build_dataset.year_window("2026-10-10") == ("2025-11", "2026-09")
    assert build_dataset.year_window("2026-01-05") == ("2025-02", "2025-12")
    assert build_dataset.year_window("2026-12-01") == ("2026-01", "2026-11")


def test_the_tile_proxy_only_serves_byte_ranges_of_a_state_partition():
    c = TestClient(app)
    assert c.get("/api/ftw/IN_MH.pmtiles", headers={"Range": "bytes=0-126"}).status_code == 401
    c.post("/api/auth/demo")
    for code, rng in (("IN%2FMH", "bytes=0-10"), ("IN_M-H", "bytes=0-10"), ("in_mh", "bytes=0-10"), ("IN_MH", ""), ("IN_MH", "bytes=0-")):
        assert c.get(f"/api/ftw/{code}.pmtiles", headers={"Range": rng} if rng else {}).status_code in (400, 404), (code, rng)


def test_the_region_overview_checks_its_input_before_asking_earth_engine():
    c = TestClient(app)
    body = {"name": "Kolhapur", "bounds": [[16.0, 73.6], [17.2, 74.7]], "boundary": None}
    assert c.post("/api/overview/summary", json=body).status_code == 401
    c.post("/api/auth/demo")
    assert c.post("/api/overview/map", json={**body, "bounds": [[17.2, 73.6], [16.0, 74.7]]}).status_code == 422
    huge = {**body, "bounds": [[8.0, 68.0], [35.0, 97.0]]}
    r = c.post("/api/overview/summary", json=huge)
    assert r.status_code == 422 and "district" in r.json()["detail"]
    assert c.get("/api/overview/tiles/not-a-key/5/1/1.png").status_code == 400
    assert c.get("/api/overview/tiles/0123456789abcdef/5/1/1.png").status_code == 404


def test_a_network_blip_is_not_read_as_a_state_without_fields(monkeypatch):
    import urllib.error
    from app import places
    monkeypatch.setattr(places.time, "sleep", lambda s: None)
    monkeypatch.setattr(places, "_partitions", {})

    def down(req, timeout=0):
        raise urllib.error.URLError("timed out")
    monkeypatch.setattr(places.urllib.request, "urlopen", down)
    with pytest.raises(places.PartitionUnreachable):
        places.ftw_partition("IN", "BR")

    def missing(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
    monkeypatch.setattr(places.urllib.request, "urlopen", missing)
    assert places.ftw_partition("IN", "LD") is None


def test_a_taluka_is_found_without_the_word_taluka(monkeypatch):
    from app import places
    monkeypatch.setattr(places, "_found", places.OrderedDict())
    asked = []

    def nominatim(q):
        asked.append(q)
        # Nominatim knows the taluka by its bare name only, and sometimes has a bad moment
        return ({"name": "Raver", "kind": "Taluka"},) if q in ("raver", "raver, jalgaon") and len(asked) > 1 else ()
    monkeypatch.setattr(places, "_search", nominatim)

    assert places.search("Raver") == []  # a passing empty answer
    assert places.search("Raver") == [{"name": "Raver", "kind": "Taluka"}]  # was not kept
    assert places.search("Raver  Taluka, Jalgaon")[0]["name"] == "Raver"
    assert asked[-2:] == ["raver taluka, jalgaon", "raver, jalgaon"]
    assert places.bare_name("Dist. Jalgaon") == "jalgaon"
    assert places.bare_name("Blockley") == "blockley"
