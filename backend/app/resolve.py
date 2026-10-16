"""Apply an officer finding: it becomes new evidence, moves only the causes it names, and the next check
is chosen again. A finding never closes the case, and nothing is confirmed by ruling something else out."""
from __future__ import annotations

from datetime import datetime

from . import config, data
from .models import CaseResult, Evidence, HypothesisResult, Line
from .engine.stages import confidence_for
from .next_check import choose, visit_check
from .pipeline import assign_stance


class CloseError(ValueError):
    pass


def _find_check(check_id: str) -> dict:
    if check_id == "visit":
        return data.checks()["visit"]
    for ch in data.checks()["checks"]:
        if ch["id"] == check_id:
            return ch
    raise CloseError(f"Unknown check '{check_id}'")


def _rank(hs: list[HypothesisResult]) -> list[HypothesisResult]:
    return sorted(hs, key=lambda h: (-h.score, int(h.id[1:])))


def apply_finding(base: CaseResult, check_id: str, outcome_key: str, note: str, recorded_at: datetime) -> CaseResult:
    if base.outcome not in ("field_case", "unexplained"):
        raise CloseError("Only open field cases take findings")
    nc = base.next_check
    if nc is None or nc.check_id != check_id:
        raise CloseError(f"This case is not waiting for '{check_id}'")
    check = _find_check(check_id)
    if outcome_key not in check["outcomes"]:
        raise CloseError(f"Unknown result '{outcome_key}' for {check_id}")
    outcome = check["outcomes"][outcome_key]

    r = base.model_copy(deep=True)
    eid = f"E{len(r.evidence) + 1}"
    finding = f"{outcome['label']}. {nc.label}."
    if note.strip():
        finding += f" Officer note: {note.strip()}"
    r.evidence.append(Evidence(
        id=eid, tool="field_visit", title="Field visit", finding=finding,
        data={"check_id": check_id, "outcome": outcome_key, "note": note.strip()},
        as_of=recorded_at.date(), quality="usable", source="Officer field visit",
    ))

    # only the causes this result names move; every other score stays exactly where it was
    supports, against = set(outcome["supports"]), set(outcome["against"])
    pool = [h for h in r.hypotheses if h.stage == 3 or h.id in supports | against]
    for h in pool:
        if h.id in supports:
            h.score = round(h.score + config.OUTCOME_WEIGHT, 3)
            h.for_lines.append(Line(text=f"On site: {outcome['label'].lower()}", evidence_ids=[eid]))
        elif h.id in against:
            h.score = round(max(0.0, h.score - config.OUTCOME_WEIGHT), 3)
            h.against_lines.append(Line(text=f"On site: {outcome['label'].lower()}", evidence_ids=[eid]))

    ordered = _rank(pool)
    for i, h in enumerate(ordered):
        nxt = ordered[i + 1].score if i + 1 < len(ordered) else 0.0
        h.confidence = confidence_for(min(h.score, 1.5), h.score - nxt)
        if h.score < config.RULED_OUT_BELOW:
            h.status = "ruled_out"
            h.unknown_lines = []
            h.brief = (h.against_lines[-1].text + f" ({', '.join(h.against_lines[-1].evidence_ids)})"
                       if h.against_lines else "No supporting evidence in the data we have")
        else:
            h.status = "leading" if i == 0 else "possible"
    ids = {h.id for h in ordered}
    r.hypotheses = ordered + [h for h in r.hypotheses if h.id not in ids]

    top = ordered[0] if ordered and ordered[0].status == "leading" else None
    assign_stance(r.evidence, top)

    # the next check is chosen again from what is still live, skipping checks already done
    done = {e.data.get("check_id") for e in r.evidence if e.tool == "field_visit"}
    live = [h.id for h in ordered if h.status != "ruled_out"]
    new = choose(live, r.check_context, done)
    if new is None and "visit" not in done:
        new = visit_check(r.field.klass)
    if new is not None:
        new.reason = _reason(outcome["label"], base, r, new)
    r.next_check = new
    r.narrative = None
    r.narrative_source = None
    return r


def _reason(result_label: str, before: CaseResult, after: CaseResult, nc) -> str:
    """One line for the slip: what the finding moved, and what the new check is for."""
    old = {h.id: h for h in before.hypotheses}
    moved = []
    for h in after.hypotheses:
        o = old.get(h.id)
        if o is None or o.score == h.score:
            continue
        if h.status == "ruled_out" and o.status != "ruled_out":
            moved.append(f"{h.name.lower()} is ruled out")
        else:
            moved.append(f"{h.name.lower()} is {'more' if h.score > o.score else 'less'} likely")
    first = f"{result_label}, so {', '.join(moved)}." if moved else f"{result_label} moves none of the causes."
    names = {h.id: h.name.lower() for h in after.hypotheses}
    if nc.check_id == "visit":
        return f"{first} No quick check separates what is left, so call the farmer or visit."
    if len(nc.hypotheses) == 2:
        a, b = nc.hypotheses
        return f"{first} This check now best separates {names[a]} from {names[b]}."
    return f"{first} This check can support or count against {names[nc.hypotheses[0]]}."
