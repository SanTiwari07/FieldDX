"""The demo case, on the real Niphad data: what the video shows must be what the engine computes."""
import pytest

from app import config, data
from app.pipeline import build_case

AREA = "niphad"


@pytest.fixture(scope="module", autouse=True)
def real_data():
    data.clear_caches()
    assert config.DATA_DIR.name == "data", "these tests read the real dataset in data/areas/niphad"
    yield


def scores(r):
    return {h.id: (round(h.score, 3), h.status) for h in r.hypotheses if h.stage == 3}


def test_before_any_finding_the_leaf_undersides_come_first():
    r = build_case(AREA, "F128")
    assert r.outcome == "field_case"
    s = scores(r)
    assert s["H8"] == (0.7, "leading")      # pest or disease spread
    assert s["H7"] == (0.4, "possible")     # irrigation failure
    assert s["H9"][1] == "ruled_out" and s["H10"][1] == "ruled_out"
    # a working drip line no longer counts for pests, so the leaf check splits the top two as well and costs less
    assert r.next_check.check_id == "leaf_undersides"
    assert r.next_check.hypotheses == ["H8", "H7"]


def test_check_results_only_support_what_they_directly_show():
    checks = {c["id"]: c for c in data.checks()["checks"]}
    assert checks["drip_line"]["outcomes"]["wet"]["supports"] == []
    assert checks["drip_line"]["outcomes"]["wet"]["label"] == "Drip line working"
    assert checks["drip_line"]["outcomes"]["dry"]["label"] == "Drip line not working"
    assert checks["soil_probe"]["outcomes"]["moist"]["supports"] == []
