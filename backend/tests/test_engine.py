import json

import pytest

from app import data
from app.llm import generate_narrative
from app.models import CaseFile
from app.narrative import template_narrative, validate_narrative
from app.next_check import split_score
from app.pipeline import build_case

CASES = [(c["id"], c["expected"]) for c in data.case_specs()]


@pytest.mark.parametrize("case_id,expected", CASES)
def test_golden_outcomes(case_id, expected):
    r = build_case(case_id)
    assert r.outcome == expected["outcome"]
    if expected["outcome"] == "field_case":
        assert r.hypotheses[0].id == expected["top"]
    elif expected["outcome"] == "auto_dismissed":
        assert r.stage_outcome.hypothesis_id == expected["top"]
    else:
        assert r.stage_outcome is None and r.next_check is None and r.visit_checklist


@pytest.mark.parametrize("case_id,_", CASES)
def test_no_invented_evidence_ids(case_id, _):
    r = build_case(case_id)
    valid = {e.id for e in r.evidence}
    for h in r.hypotheses:
        for ln in h.for_lines + h.against_lines:
            assert ln.evidence_ids and set(ln.evidence_ids) <= valid
    assert validate_narrative(template_narrative(r), r) == []


def test_hero_next_check_is_the_drip_line():
    r = build_case("C1")
    assert r.hypotheses[0].confidence == "high"
    assert r.next_check.check_id == "drip_line"
    assert "east" in r.next_check.label
    assert r.next_check.candidates[0].check_id == "drip_line"


def test_pest_case_does_not_ask_about_a_drip_line():
    r = build_case("C4")
    assert r.next_check.check_id == "leaf_undersides"
    assert "drip_line" not in {c.check_id for c in r.next_check.candidates}


def test_split_score():
    drip = next(c for c in data.checks()["checks"] if c["id"] == "drip_line")
    assert split_score(drip, "H7", "H8") == 1.0
    assert split_score(drip, "H8", "H7") == 1.0
    assert split_score(drip, "H7", "H9") == 1.0
    assert split_score(drip, "H7", "H10") == 0.0


def fake(payload):
    return lambda prompt: payload if isinstance(payload, str) else json.dumps(payload)


def test_bad_evidence_id_retries_then_falls_back():
    r = build_case("C1")
    bad = template_narrative(r).model_dump(mode="json")
    bad["summary"]["evidence_ids"] = ["E99"]
    calls = []

    def call(prompt):
        calls.append(prompt)
        return json.dumps(bad)

    cf, source = generate_narrative(r, call)
    assert source == "template" and len(calls) == 2
    assert "E99" in calls[1]
    assert isinstance(cf, CaseFile)


def test_valid_model_answer_is_accepted():
    r = build_case("C1")
    good = template_narrative(r).model_dump(mode="json")
    assert generate_narrative(r, fake(good))[1] == "gemini"


def test_wrong_hypothesis_order_is_rejected():
    r = build_case("C1")
    good = template_narrative(r).model_dump(mode="json")
    good["hypotheses"].reverse()
    assert generate_narrative(r, fake(good))[1] == "template"


def test_blocked_or_empty_response_falls_back():
    r = build_case("C1")
    assert generate_narrative(r, fake(""))[1] == "template"

    def boom(prompt):
        raise TimeoutError("slow")

    assert generate_narrative(r, boom)[1] == "template"
