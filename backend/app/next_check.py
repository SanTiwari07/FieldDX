"""Choose the cheapest observation that best separates the top two hypotheses.

    split(check) = 1.0  if one outcome supports A and argues against B, and another does the reverse
                 = 0.5  if only one of those outcomes exists
                 = 0.0  otherwise
    score(check) = split(check) / cost_min        (ties go to the lower cost)
"""
from __future__ import annotations

from . import data
from .models import CandidateCheck, CheckOutcome, NextCheck

NAMES = {"H7": "irrigation failure", "H8": "pest or disease", "H9": "nutrient deficiency"}


def split_score(check: dict, a: str, b: str) -> float:
    a_over_b = b_over_a = False
    for oc in check["outcomes"].values():
        if a in oc["supports"] and b in oc["against"]:
            a_over_b = True
        if b in oc["supports"] and a in oc["against"]:
            b_over_a = True
    return 1.0 if (a_over_b and b_over_a) else 0.5 if (a_over_b or b_over_a) else 0.0


def _applies(check: dict, state: dict) -> bool:
    rule = check.get("applies_when", "always")
    if rule == "edge_zone":
        return bool(state.get("has_edge_zone"))
    return True


def choose(top_two: list[str], state: dict) -> NextCheck | None:
    if len(top_two) < 2:
        return None
    a, b = top_two
    rows = []
    for ch in data.checks()["checks"]:
        if not _applies(ch, state):
            continue
        sp = split_score(ch, a, b)
        score = round(sp / ch["cost_min"], 4)
        rows.append((ch, sp, score))
    if not rows:
        return None
    rows.sort(key=lambda r: (-r[2], r[0]["cost_min"], r[0]["id"]))
    best = rows[0]
    if best[2] <= 0:
        return None

    edge = state.get("edge_name") or "affected"

    def label(ch):
        return ch["label"].format(edge=edge)

    candidates = [
        CandidateCheck(
            check_id=ch["id"], short=ch["short"], label=label(ch), cost_min=ch["cost_min"],
            split=sp, score=score, chosen=(ch is best[0]),
            note={1.0: "Splits cleanly", 0.5: "Informative one way", 0.0: "Does not separate them"}[sp],
        )
        for ch, sp, score in rows
    ]
    ch = best[0]
    outcomes = [
        CheckOutcome(key=k, label=o["label"], then=o["then"], supports=o["supports"], against=o["against"])
        for k, o in ch["outcomes"].items()
    ]
    return NextCheck(
        check_id=ch["id"], label=label(ch), cost_min=ch["cost_min"],
        outcomes=outcomes, hypotheses=[a, b], candidates=candidates,
    )
