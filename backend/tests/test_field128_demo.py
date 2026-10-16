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


def after(*findings):
    from datetime import datetime
    from app.resolve import apply_finding
    r = build_case(AREA, "F128")
    for check_id, outcome in findings:
        r = apply_finding(r, check_id, outcome, "", datetime(2026, 10, 16, 10, 0))
    return r


def test_leaves_clean_lowers_pests_leaves_irrigation_alone_and_moves_to_the_drip_line():
    r = after(("leaf_undersides", "clean"))
    s = scores(r)
    assert r.outcome == "field_case"                 # the case stays open
    assert s["H8"] == (0.2, "possible")              # pest or disease spread: less likely, still possible
    assert s["H7"] == (0.4, "leading")               # irrigation failure: unchanged, first because pests weakened
    assert s["H9"] == (0.0, "ruled_out") and s["H10"] == (0.0, "ruled_out")
    assert r.next_check.check_id == "drip_line" and "south" in r.next_check.label
    assert r.next_check.reason.startswith("Leaves clean, so pest or disease spread is less likely.")
    causes = " ".join(h.model_dump_json() for h in r.hypotheses) + r.next_check.reason
    assert "confirmed" not in causes.lower()      # the drop itself may be confirmed by scenes; no cause is


def test_the_update_says_what_moved_what_did_not_and_never_confirms():
    from app.narrative import template_narrative, validate_narrative
    r = after(("leaf_undersides", "clean"))
    moves = {m.id: m for m in r.update.moves}
    assert moves["H8"].movement == "less_likely" and moves["H8"].evidence_ids == [r.update.evidence_id]
    assert moves["H7"].movement == "unchanged" and moves["H7"].after_rank == 1 and moves["H7"].before_rank == 2
    assert "It now ranks first because pest or disease spread became less likely" in moves["H7"].reason
    assert moves["H9"].movement == "unchanged" and moves["H10"].movement == "unchanged"
    cf = template_narrative(r)
    assert validate_narrative(cf, r) == []
    text = cf.summary.text + " ".join(ln.text for h in cf.hypotheses for ln in h.why)
    assert "Investigation updated" in cf.summary.text and "stays open" in cf.summary.text
    assert "confirmed" not in text.lower()


def test_drip_line_working_next_rules_out_irrigation_without_reviving_nutrients():
    r = after(("leaf_undersides", "clean"), ("drip_line", "wet"))
    s = scores(r)
    assert s["H7"] == (0.0, "ruled_out")             # irrigation failure ruled out by the working drip line
    assert s["H9"] == (0.0, "ruled_out")             # nutrient deficiency is not revived by it
    assert s["H8"] == (0.2, "leading")               # the one cause left: best remaining fit, still weak
    assert {m.id: m.movement for m in r.update.moves}["H9"] == "unchanged"
    assert r.outcome == "field_case" and r.next_check.check_id == "visit"
    assert "call the farmer or visit" in r.next_check.reason


def test_drip_line_working_as_a_first_finding_only_counts_against_irrigation():
    # the checklist only offers the recommended check, so point the case at the drip line to test the rule alone
    base = build_case(AREA, "F128")
    drip = next(c for c in base.next_check.candidates if c.check_id == "drip_line")
    base.next_check = base.next_check.model_copy(update={"check_id": "drip_line", "label": drip.label})
    from datetime import datetime
    from app.resolve import apply_finding
    r = apply_finding(base, "drip_line", "wet", "", datetime(2026, 10, 16, 10, 0))
    s = scores(r)
    assert s["H7"] == (0.0, "ruled_out") and s["H8"] == (0.7, "leading") and s["H9"] == (0.0, "ruled_out")


def test_a_finding_that_leaves_no_cause_standing_says_none_fits():
    # a constructed starting point: pests is the only live cause, and clean leaves count against it
    from datetime import datetime
    from app.narrative import template_narrative, validate_narrative
    from app.resolve import apply_finding
    base = build_case(AREA, "F128")
    for h in base.hypotheses:
        if h.id == "H7":
            h.score, h.status = 0.0, "ruled_out"
        if h.id == "H8":
            h.score = 0.5
    r = apply_finding(base, "leaf_undersides", "clean", "", datetime(2026, 10, 16, 10, 0))
    assert all(h.status == "ruled_out" for h in r.hypotheses if h.stage == 3)
    assert r.outcome == "unexplained" and r.next_check.check_id == "visit"
    cf = template_narrative(r)
    assert validate_narrative(cf, r) == []
    assert "None of the current explanations fits well" in cf.summary.text
    assert "confirmed" not in cf.summary.text.lower()
