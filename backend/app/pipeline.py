"""Run the tools, the rules and the next-check scoring for one case.

`iter_events` is the single source of truth: the SSE stream replays it with pauses between steps,
and `build_case` consumes it with none.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Iterator

from . import config, data
from .data import ZONE_LABEL
from .engine.stages import diagnose
from .models import (CaseResult, CheckOutcome, Evidence, FieldInfo, Headline, HypothesisResult, NextCheck)
from .next_check import choose
from .tools import PIPELINE
from .tools.common import ToolResult, build_ctx

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}
CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}

STEP_LABELS = {name: (running, title) for name, _fn, running, title in PIPELINE}
STEP_LABELS["engine"] = ("Applying the hypothesis rules", "Hypothesis rules")
STEP_LABELS["next_check"] = ("Choosing the next best check", "Next best check")


def limits_text(f: data.FieldRec) -> str:
    return (
        f"Each pixel is 10 m × 10 m. This field has about {f.analysis_pixels} analysis pixels ({f.area_ha} ha), "
        "so FieldDx can see zones, not individual plants or rows. The field shape is a model prediction, not a survey. "
        "The crop is not known, only whether the canopy looks perennial or seasonal. Cloud gaps can hide days of change. "
        "Storm damage and waterlogging are scored from weather only, and red-edge (NDRE) is not used yet."
    )


def _severity(delta: float, area_share: float) -> str:
    d = abs(delta)
    if d >= 0.18 and area_share >= config.SEVERITY_AREA:
        return "high"
    if d >= 0.12:
        return "medium"
    return "low"


def _evidence(res: ToolResult, eid: str) -> Evidence:
    return Evidence(
        id=eid, tool=res.tool, title=res.title, finding=res.finding, data=res.data,
        as_of=res.as_of, quality=res.quality, source=res.source, visual=res.visual,
    )


def assign_stance(evidence: list[Evidence], lead: HypothesisResult | None) -> None:
    for e in evidence:
        e.stance = "neutral"
    if lead is None:
        return
    for_ids = {i for ln in lead.for_lines for i in ln.evidence_ids}
    against_ids = {i for ln in lead.against_lines for i in ln.evidence_ids}
    for e in evidence:
        if e.id in for_ids:
            e.stance = "for"
        elif e.id in against_ids:
            e.stance = "against"


def iter_events(case_id: str) -> Iterator[tuple[str, dict]]:
    spec = data.case_spec(case_id)
    if spec is None:
        raise KeyError(case_id)
    cases = data.cases_file()
    as_of = date.fromisoformat(cases["as_of"])
    alert = date.fromisoformat(spec["alert_date"])
    ctx = build_ctx(spec["field_id"], alert, as_of)

    evidence: list[Evidence] = []
    facts: dict = {}
    vars_: dict = {}
    ev_ids: dict[str, str] = {}

    for name, fn, running, _title in PIPELINE:
        yield "step", {"tool": name, "state": "running", "label": running}
        res = fn(ctx)
        facts.update(res.facts)
        if res.skipped:
            yield "step", {"tool": name, "state": "skipped", "label": running, "reason": res.skip_reason}
            continue
        vars_.update(res.vars)
        eid = f"E{len(evidence) + 1}"
        ev_ids[name] = eid
        ev = _evidence(res, eid)
        evidence.append(ev)
        yield "evidence", ev.model_dump(mode="json")
        yield "step", {"tool": name, "state": "done", "label": running, "evidence_ids": [eid], "summary": res.finding}

    yield "step", {"tool": "engine", "state": "running", "label": STEP_LABELS["engine"][0]}
    diag = diagnose(facts, vars_, ev_ids)
    yield "step", {"tool": "engine", "state": "done", "label": STEP_LABELS["engine"][0],
                   "evidence_ids": [], "summary": _engine_summary(diag)}

    yield "step", {"tool": "next_check", "state": "running", "label": STEP_LABELS["next_check"][0]}
    next_check = None
    if diag.outcome == "field_case" and len(diag.ranking) >= 2:
        next_check = choose(diag.ranking[:2], ctx.state)
    if diag.outcome == "unexplained":
        v = data.checks()["visit"]
        next_check = NextCheck(
            check_id="visit", label=v["label"], cost_min=v["cost_min"], hypotheses=[], candidates=[],
            outcomes=[CheckOutcome(key=k, label=o["label"], then=o["then"], supports=o["supports"], against=o["against"])
                      for k, o in v["outcomes"].items() if not (k == "pruned" and ctx.field.klass != "perennial")],
        )
    if next_check and diag.outcome == "unexplained":
        yield "step", {"tool": "next_check", "state": "skipped", "label": STEP_LABELS["next_check"][0],
                       "reason": "No single check separates the causes, so a call or visit is the check."}
    elif next_check:
        yield "step", {"tool": "next_check", "state": "done", "label": STEP_LABELS["next_check"][0],
                       "evidence_ids": [], "summary": f"{next_check.label} ({next_check.cost_min} min)"}
    else:
        reason = ("Case closed at an earlier stage, no check needed."
                  if diag.outcome in ("auto_dismissed", "area_alert", "watch")
                  else "No single check separates the leading causes; a general visit checklist applies.")
        yield "step", {"tool": "next_check", "state": "skipped", "label": STEP_LABELS["next_check"][0], "reason": reason}

    # headline and severity
    s = ctx.series
    primary = ctx.state.get("primary_zone")
    headline = None
    severity = None
    if primary:
        delta = ctx.state["primary_delta"]
        label = "Whole field" if primary == "__field__" else ZONE_LABEL[primary]
        headline = Headline(
            delta=delta, zone=primary, zone_label=label,
            date=ctx.state["headline_scene_date"], quality=ctx.state["ref_quality"],
            baseline_label=s.baseline_label(),
        )
        affected = ctx.state.get("affected_zones") or ([] if primary == "__field__" else [primary])
        zone_px = ctx.field.zone_pixels
        total = sum(zone_px[z] for z in data.ANALYSIS)
        share = 1.0 if primary == "__field__" else sum(zone_px.get(z, 0) for z in affected if z in data.ANALYSIS) / total
        if diag.outcome in ("field_case", "unexplained"):
            severity = _severity(delta, share)

    lead = next((h for h in diag.hypotheses if h.id == diag.lead_id), None)
    assign_stance(evidence, lead)

    f = ctx.field
    result = CaseResult(
        case_id=case_id,
        field=FieldInfo(
            id=f.id, name=f.name, klass=f.klass, class_label=data.CLASS_LABEL[f.klass],
            area_ha=f.area_ha, analysis_pixels=f.analysis_pixels,
        ),
        alert_date=alert, as_of=as_of, banner=cases["banner"],
        outcome=diag.outcome, severity=severity, headline=headline,
        evidence=evidence, hypotheses=diag.hypotheses, stage_outcome=diag.stage_outcome,
        next_check=next_check,
        visit_checklist=_visit_list(diag.outcome, facts, vars_),
        limits=limits_text(f),
    )
    yield "diagnosis", result.model_dump(mode="json")


def _visit_list(outcome: str, facts: dict, vars_: dict) -> list[str]:
    if outcome != "unexplained":
        return []
    items = list(data.checks()["visit_checklist"])
    if facts.get("in_window"):
        ask = vars_.get("window_ask") or "Ask the farmer whether the crop was harvested or pruned this week."
        items.insert(0, ask.replace(" One phone call settles it.", " It is one phone call and may settle the case."))
    return items


def _engine_summary(diag) -> str:
    if diag.stage_outcome:
        return f"{diag.stage_outcome.title}. {diag.stage_outcome.reason}."
    if diag.outcome == "unexplained":
        return "No hypothesis clears the evidence bar. Answer: unexplained, visit."
    top = diag.hypotheses[0]
    return f"Leading: {top.name} ({top.confidence} confidence)."


@lru_cache(maxsize=None)
def _cached(case_id: str) -> CaseResult:
    last = None
    for kind, payload in iter_events(case_id):
        if kind == "diagnosis":
            last = payload
    return CaseResult.model_validate(last)


def build_case(case_id: str) -> CaseResult:
    """The deterministic result for a case, before any officer finding is applied."""
    return _cached(case_id).model_copy(deep=True)


def inbox_sort_key(r: CaseResult) -> tuple:
    group = {"field_case": 0, "unexplained": 0, "watch": 1, "area_alert": 2, "resolved": 3, "auto_dismissed": 4}[r.outcome]
    sev = SEVERITY_RANK.get(r.severity or "low", 0)
    lead = next((h for h in r.hypotheses if h.status in ("leading", "fired")), None)
    conf = CONFIDENCE_RANK.get(lead.confidence, 0) if lead and r.outcome != "unexplained" else 1
    mag = abs(r.headline.delta) if r.headline else 0
    return (group, -sev, -conf, -mag, r.case_id)
