"""Choose the cheapest observation that best separates the top two hypotheses.

    split(check) = 1.0  if one outcome supports A and argues against B, and another does the reverse
                 = 0.5  if only one of those outcomes exists
                 = 0.0  otherwise
    score(check) = split(check) / cost_min        (ties go to the lower cost)

An outcome that only argues against one cause does not count as separating it from another: ruling one
cause out is not evidence for the other. Checks already done on the case are skipped. When a single cause
is still live, the best check is one that can either support it or count against it.
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


def test_score(check: dict, a: str) -> float:
    """How well a check tests a single cause: one outcome supports it and another counts against it."""
    outs = check["outcomes"].values()
    return 1.0 if any(a in oc["supports"] for oc in outs) and any(a in oc["against"] for oc in outs) else 0.0


def _applies(check: dict, state: dict) -> bool:
    rule = check.get("applies_when", "always")
    if rule == "edge_zone":
        return bool(state.get("has_edge_zone"))
    return True


def _outcomes(ch: dict) -> list[CheckOutcome]:
    return [CheckOutcome(key=k, label=o["label"], then=o["then"], supports=o["supports"], against=o["against"])
            for k, o in ch["outcomes"].items()]


def choose(live: list[str], state: dict, done: frozenset[str] | set[str] = frozenset()) -> NextCheck | None:
    """The best check for the top two live causes, or for the only one left."""
    if not live:
        return None
    pair = list(live[:2])
    rows = []
    for ch in data.checks()["checks"]:
        if ch["id"] in done or not _applies(ch, state):
            continue
        sp = split_score(ch, *pair) if len(pair) == 2 else test_score(ch, pair[0])
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

    notes = ({1.0: "Splits cleanly", 0.5: "Informative one way", 0.0: "Does not separate them"} if len(pair) == 2
             else {1.0: "Can confirm or count against it", 0.0: "Does not test it"})
    candidates = [
        CandidateCheck(
            check_id=ch["id"], short=ch["short"], label=label(ch), cost_min=ch["cost_min"],
            split=sp, score=score, chosen=(ch is best[0]), note=notes[sp],
        )
        for ch, sp, score in rows
    ]
    ch = best[0]
    return NextCheck(
        check_id=ch["id"], label=label(ch), cost_min=ch["cost_min"],
        outcomes=_outcomes(ch), hypotheses=pair, candidates=candidates,
    )


def visit_check(klass: str) -> NextCheck:
    """Call the farmer or visit: the check when no single observation separates the causes."""
    v = data.checks()["visit"]
    outs = [o for o in _outcomes(v) if not (o.key == "pruned" and klass != "perennial")]
    return NextCheck(check_id="visit", label=v["label"], cost_min=v["cost_min"], hypotheses=[], candidates=[],
                     outcomes=outs)
