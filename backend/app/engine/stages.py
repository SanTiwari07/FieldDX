"""Score every hypothesis, then walk the three stages to an outcome."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .. import config
from ..models import HypothesisResult, Line, StageOutcome
from .rules import FACT_SOURCE, RULES, Cond, Rule


class _Vars(defaultdict):
    def __missing__(self, key):
        return ""


@dataclass
class Scored:
    rule: Rule
    score: float
    gate_ok: bool
    for_lines: list[Line] = field(default_factory=list)
    against_lines: list[Line] = field(default_factory=list)
    unknown_lines: list[Line] = field(default_factory=list)


@dataclass
class Diagnosis:
    outcome: str
    hypotheses: list[HypothesisResult]
    stage_outcome: StageOutcome | None
    lead_id: str | None
    ranking: list[str]  # stage 3 ids, best first


def _line(cond: Cond, vars_: dict, ids: list[str]) -> Line:
    return Line(text=cond.label.format_map(_Vars(str, vars_)), evidence_ids=ids)


def score_rule(rule: Rule, facts: dict, vars_: dict, ev_ids: dict[str, str]) -> Scored:
    total = 0.0
    out = Scored(rule=rule, score=0.0, gate_ok=all(facts.get(f) is True for f in rule.requires))
    for sign, conds, bucket in ((1, rule.supports, out.for_lines), (-1, rule.against, out.against_lines)):
        for c in conds:
            val = facts.get(c.fact)
            tool = FACT_SOURCE.get(c.fact)
            ev = ev_ids.get(tool) if tool else None
            if val is None or (ev is None and not c.unknown):
                # Not measured. Only supports are worth listing as unknown.
                if sign == 1 and (c.unknown or tool in ev_ids):
                    out.unknown_lines.append(Line(
                        text=c.unknown or f"Not known: {c.label[0].lower() + c.label[1:]}",
                        evidence_ids=[ev] if ev else [],
                    ))
                continue
            if tool and ev is None:
                continue  # the tool was skipped, so there is no evidence to cite
            if val == c.want:
                total += sign * c.weight
                bucket.append(_line(c, vars_, [ev] if ev else []))
    out.score = round(max(0.0, min(1.0, total)), 3)
    return out


def confidence_for(score: float, lead_over_next: float) -> str:
    if score >= config.CONF_HIGH and lead_over_next >= config.CONF_HIGH_LEAD:
        return "high"
    if score >= config.CONF_MEDIUM:
        return "medium"
    return "low"


def _brief(s: Scored) -> str:
    if s.against_lines:
        ids = ", ".join(s.against_lines[0].evidence_ids)
        return f"{s.against_lines[0].text} ({ids})" if ids else s.against_lines[0].text
    return "No supporting evidence in the data we have"


def diagnose(facts: dict, vars_: dict, ev_ids: dict[str, str]) -> Diagnosis:
    scored = {r.id: score_rule(r, facts, vars_, ev_ids) for r in RULES}

    def fired(stage: int) -> list[Scored]:
        return sorted(
            (s for s in scored.values() if s.rule.stage == stage and s.gate_ok and s.score >= config.GATE_FIRE),
            key=lambda s: -s.score,
        )

    winner: Scored | None = None
    outcome = ""
    f1, f2 = fired(1), fired(2)
    if f1:
        winner, outcome = f1[0], "auto_dismissed"
    elif f2:
        winner = f2[0]
        outcome = "area_alert" if winner.rule.id in ("H5", "H6") else "auto_dismissed"

    stage3 = sorted((s for s in scored.values() if s.rule.stage == 3), key=lambda s: (-s.score, int(s.rule.id[1:])))
    if winner is None:
        if stage3 and stage3[0].score >= config.FIELD_CASE_MIN:
            outcome = "field_case"
        else:
            outcome = "unexplained"

    # confidence: stage 3 relative to the next one down; gates by their own score
    conf: dict[str, str] = {}
    for i, s in enumerate(stage3):
        nxt = stage3[i + 1].score if i + 1 < len(stage3) else 0.0
        conf[s.rule.id] = confidence_for(s.score, s.score - nxt)
    for s in scored.values():
        if s.rule.stage != 3:
            conf[s.rule.id] = "high" if s.score >= 0.85 else "medium" if s.score >= config.GATE_FIRE else "low"

    lead_id = None
    if outcome == "field_case":
        lead_id = stage3[0].rule.id
    elif winner is not None:
        lead_id = winner.rule.id

    hyps: list[HypothesisResult] = []

    def build(s: Scored) -> HypothesisResult:
        rid = s.rule.id
        if winner is not None and rid == winner.rule.id:
            status = "fired"
        elif outcome == "field_case" and rid == lead_id:
            status = "leading"
        elif s.score < config.RULED_OUT_BELOW:
            status = "ruled_out"
        else:
            status = "possible"
        return HypothesisResult(
            id=rid, name=s.rule.name, stage=s.rule.stage, score=s.score, confidence=conf[rid],
            status=status, for_lines=s.for_lines, against_lines=s.against_lines,
            unknown_lines=s.unknown_lines if status != "ruled_out" else [],
            brief=_brief(s) if status == "ruled_out" else "",
        )

    ordered = ([winner] if winner else []) + stage3 + [
        s for s in sorted(scored.values(), key=lambda x: (x.rule.stage, int(x.rule.id[1:])))
        if s.rule.stage != 3 and s is not winner
    ]
    seen = set()
    for s in ordered:
        if s.rule.id in seen:
            continue
        seen.add(s.rule.id)
        hyps.append(build(s))

    stage_outcome = _stage_outcome(winner, outcome, vars_, facts) if winner else None
    return Diagnosis(outcome=outcome, hypotheses=hyps, stage_outcome=stage_outcome,
                     lead_id=lead_id, ranking=[s.rule.id for s in stage3])


def _stage_outcome(w: Scored, outcome: str, vars_: dict, facts: dict) -> StageOutcome:
    rid = w.rule.id
    ids = sorted({i for line in w.for_lines for i in line.evidence_ids}, key=lambda x: int(x[1:]))
    v = _Vars(str, vars_)
    confirm = None
    if rid == "H1":
        word = "Cloud or haze" if vars_.get("alert_scene_class") in ("partial", "cloudy") else "Data artefact"
        reason, title = f"{word} on the {vars_.get('alert_date', '')} scene", "Auto-dismissed: data artefact"
    elif rid == "H2":
        reason = f"Edge pixels mix with the {vars_.get('edge_context', 'neighbouring plot')} next door"
        title = "Auto-dismissed: boundary mixing"
    elif rid == "H3":
        label = vars_.get("window_label", "Management event")
        reason, title = f"{label}, expected", "Auto-dismissed: expected management event"
        confirm = f"Ask the farmer: was {label.lower()} done this week? One phone call settles it."
    elif rid == "H4":
        reason, title = "Normal crop cycle", "Auto-dismissed: normal crop cycle"
        confirm = "Ask the farmer: has the crop been harvested? One phone call settles it."
    elif rid == "H5":
        reason = f"{v['n_dropped']} of {v['n_neighbours']} neighbouring {v['crop']} plots dropped in a dry or hot spell"
        title = "Area alert: regional dry or hot spell"
    else:
        reason, title = "Heavy rain with neighbours also hit", "Area alert: storm or hail"
    return StageOutcome(
        kind="area_alert" if outcome == "area_alert" else "auto_dismissed",
        hypothesis_id=rid, title=title, reason=reason, evidence_ids=ids, confirm_with=confirm,
    )
