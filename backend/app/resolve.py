"""Close a case: the officer's finding becomes new evidence and the ranking updates."""
from __future__ import annotations

from datetime import date, datetime

from . import config, data
from .models import CaseResult, Evidence, HypothesisResult, Line, Resolution
from .engine.stages import confidence_for
from .pipeline import assign_stance


class CloseError(ValueError):
    pass


def _find_check(check_id: str) -> dict:
    for ch in data.checks()["checks"]:
        if ch["id"] == check_id:
            return ch
    raise CloseError(f"Unknown check '{check_id}'")


def apply_outcome(base: CaseResult, check_id: str, outcome_key: str, note: str, closed_at: datetime) -> CaseResult:
    if base.outcome not in ("field_case", "unexplained"):
        raise CloseError("Only open field cases can be closed")
    check = _find_check(check_id)
    if outcome_key not in check["outcomes"]:
        raise CloseError(f"Unknown result '{outcome_key}' for {check_id}")
    outcome = check["outcomes"][outcome_key]

    r = base.model_copy(deep=True)
    eid = f"E{len(r.evidence) + 1}"
    edge = ""
    if r.next_check and r.next_check.check_id == check_id:
        edge = r.next_check.label
    label = (r.next_check.label if r.next_check and r.next_check.check_id == check_id
             else check["label"].format(edge="affected"))
    finding = f"{outcome['label']}. {label}."
    if note.strip():
        finding += f" Officer note: {note.strip()}"
    r.evidence.append(Evidence(
        id=eid, tool="field_visit", title="Field visit", finding=finding,
        data={"check_id": check_id, "outcome": outcome_key, "note": note.strip()},
        as_of=closed_at.date(), quality="usable", source="Officer field visit",
    ))

    stage3 = [h for h in r.hypotheses if h.stage == 3]
    before = [h.id for h in sorted(stage3, key=lambda h: (-h.score, int(h.id[1:])))]
    for h in stage3:
        if h.id in outcome["supports"]:
            h.score = round(h.score + config.OUTCOME_WEIGHT, 3)
            h.for_lines.append(Line(text=f"On site: {outcome['label'].lower()}", evidence_ids=[eid]))
        elif h.id in outcome["against"]:
            h.score = round(max(0.0, h.score - config.OUTCOME_WEIGHT), 3)
            h.against_lines.append(Line(text=f"On site: {outcome['label'].lower()}", evidence_ids=[eid]))

    ordered = sorted(stage3, key=lambda h: (-h.score, int(h.id[1:])))
    after = [h.id for h in ordered]
    for i, h in enumerate(ordered):
        nxt = ordered[i + 1].score if i + 1 < len(ordered) else 0.0
        h.confidence = confidence_for(min(h.score, 1.5), h.score - nxt)
        if i == 0:
            h.status = "leading"
        elif h.score < config.RULED_OUT_BELOW:
            h.status = "ruled_out"
            h.unknown_lines = []
            h.brief = (h.against_lines[-1].text + f" ({', '.join(h.against_lines[-1].evidence_ids)})"
                       if h.against_lines else "No supporting evidence in the data we have")
        else:
            h.status = "possible"
    # keep stage 1 and 2 entries where they were; re-order stage 3 by the new ranking
    others = [h for h in r.hypotheses if h.stage != 3]
    r.hypotheses = ordered + others

    top = ordered[0]
    assign_stance(r.evidence, top)
    r.outcome = "resolved"
    r.next_check = r.next_check
    r.narrative = None
    r.narrative_source = None
    r.resolution = Resolution(
        check_id=check_id, check_label=label, outcome_key=outcome_key, outcome_label=outcome["label"],
        note=note.strip(), closed_at=closed_at.isoformat(timespec="seconds"),
        confirmed_id=top.id, confirmed_name=top.name, ranking_before=before, ranking_after=after,
    )
    return r
