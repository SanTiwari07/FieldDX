"""Case-file prose: a deterministic template, and the validator any LLM output must pass.

The template is what the demo falls back to, so the app works with no model at all.
"""
from __future__ import annotations

import re

from .models import CaseFile, CaseFileLine, CaseResult, HypothesisExplainer, HypothesisResult

EVIDENCE_REF = re.compile(r"\bE\d+\b")


def explained_ids(r: CaseResult) -> list[str]:
    """The hypotheses a narrative must explain, in the order the engine ranks them."""
    if r.stage_outcome is not None:
        return [] if r.stage_outcome.kind == "watch" else [r.stage_outcome.hypothesis_id]
    return [h.id for h in r.hypotheses if h.stage == 3 and h.status in ("leading", "possible")]


def _ids(lines) -> list[str]:
    out: list[str] = []
    for ln in lines:
        for i in ln.evidence_ids:
            if i not in out:
                out.append(i)
    return sorted(out, key=lambda x: int(x[1:]))


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def _tool_ids(r: CaseResult, *tools: str) -> list[str]:
    return [e.id for e in r.evidence if e.tool in tools]


def template_narrative(r: CaseResult) -> CaseFile:
    by_id = {h.id: h for h in r.hypotheses}

    if r.stage_outcome is not None and r.stage_outcome.kind == "watch":
        so = r.stage_outcome
        summary = CaseFileLine(
            text=("The drop shows on one clear pass only, so FieldDx cannot yet tell a real change from a "
                  "passing artefact. It waits for the next clear pass before asking anyone to visit."),
            evidence_ids=so.evidence_ids,
        )
        return CaseFile(summary=summary, hypotheses=[], next_check_explainer=None, limits=r.limits)

    if r.stage_outcome is not None:
        so = r.stage_outcome
        h = by_id[so.hypothesis_id]
        head = "Area alert, not a field case" if so.kind == "area_alert" else "Dismissed automatically"
        body = " ".join(_sentence(ln.text) for ln in h.for_lines[:3])
        summary = CaseFileLine(text=f"{head}: {so.reason}. {body}".strip(), evidence_ids=so.evidence_ids)
        why = [CaseFileLine(text=_sentence(ln.text), evidence_ids=ln.evidence_ids) for ln in h.for_lines[:4]]
        return CaseFile(
            summary=summary, hypotheses=[HypothesisExplainer(id=h.id, why=why)],
            next_check_explainer=None, limits=r.limits,
        )

    ranked = [by_id[i] for i in explained_ids(r)]
    if r.outcome == "unexplained" or not ranked:
        ids = _tool_ids(r, "ndvi_series", "spatial_pattern", "neighbour_compare") or _tool_ids(r, "ndvi_series")
        summary = CaseFileLine(
            text=(
                "The drop is real and confirmed, but no hypothesis clears the evidence bar, so FieldDx will not guess. "
                "A visit is needed, and the checklist below covers the usual suspects."
            ),
            evidence_ids=ids,
        )
        expl = [
            HypothesisExplainer(
                id=h.id,
                why=[CaseFileLine(text=_sentence(ln.text), evidence_ids=ln.evidence_ids) for ln in h.for_lines[:2]],
            )
            for h in ranked if h.for_lines
        ]
        return CaseFile(summary=summary, hypotheses=expl, next_check_explainer=None, limits=r.limits)

    if r.update is not None:
        return _updated(r, ranked)
    lead = ranked[0]
    lines = lead.for_lines[:3]
    parts = [f"{lead.name} is the leading explanation ({lead.confidence} confidence)."]
    parts += [_sentence(ln.text) for ln in lines]
    ids = _ids(lines)
    if len(ranked) > 1 and ranked[1].for_lines:
        second = ranked[1]
        parts.append(f"Next most likely: {second.name.lower()} ({second.confidence}).")
        ids = sorted(set(ids) | set(_ids(second.for_lines[:1])), key=lambda x: int(x[1:]))
    summary = CaseFileLine(text=" ".join(parts), evidence_ids=ids)

    expl = []
    for h in ranked:
        why = [CaseFileLine(text=_sentence(ln.text), evidence_ids=ln.evidence_ids) for ln in h.for_lines[:3]]
        if h.against_lines:
            a = h.against_lines[0]
            why.append(CaseFileLine(text="Against: " + _sentence(a.text[0].lower() + a.text[1:]), evidence_ids=a.evidence_ids))
        if not why:
            why = [CaseFileLine(text="No evidence in the data points this way.", evidence_ids=_tool_ids(r, "ndvi_series")[:1])]
        expl.append(HypothesisExplainer(id=h.id, why=why))

    nxt = None
    if r.next_check:
        nc = r.next_check
        text = nc.label + ". " + " ".join(f"{o.label}: {o.then}." for o in nc.outcomes)
        refs = sorted(
            {i for h in ranked[:2] for ln in h.for_lines[:2] for i in ln.evidence_ids},
            key=lambda x: int(x[1:]),
        ) or _tool_ids(r, "ndvi_series")[:1]
        nxt = CaseFileLine(text=text, evidence_ids=refs)
    return CaseFile(summary=summary, hypotheses=expl, next_check_explainer=nxt, limits=r.limits)


_MOVE_WORDS = {"more_likely": "is more likely", "less_likely": "is less likely", "ruled_out": "is ruled out",
               "newly_considered": "is back under consideration"}


def _updated(r: CaseResult, ranked: list[HypothesisResult]) -> CaseFile:
    """The case file after an officer finding: what was checked, what moved, what did not, and what next.
    Always the template, so the wording is the same on every run; it never calls a cause confirmed."""
    u = r.update
    assert u is not None
    lead = ranked[0]
    moved = [m for m in u.moves if m.movement != "unchanged"]
    parts = [f"Investigation updated after a field visit: {u.outcome_label.lower()} ({u.evidence_id})."]
    if moved:
        parts.append(" ".join(f"{m.name} {_MOVE_WORDS[m.movement]}." for m in moved))
    else:
        parts.append("The finding moves none of the causes.")
    lm = next((m for m in u.moves if m.id == lead.id), None)
    if lm is not None and lm.movement == "unchanged" and lm.after_rank < lm.before_rank:
        parts.append(f"{lead.name} is now first with no new evidence for it, because the others weakened. "
                     "It is the best remaining fit, not a diagnosis.")
    else:
        parts.append(f"{lead.name} is first. It is the best remaining fit, not a diagnosis.")
    parts.append("The case stays open.")
    summary = CaseFileLine(text=" ".join(parts), evidence_ids=[u.evidence_id])

    expl = []
    for h in ranked:
        m = next((m for m in u.moves if m.id == h.id), None)
        why = [CaseFileLine(text=_sentence(m.reason), evidence_ids=m.evidence_ids or [u.evidence_id])] if m else []
        why += [CaseFileLine(text=_sentence(ln.text), evidence_ids=ln.evidence_ids) for ln in h.for_lines[:2]]
        if h.against_lines:
            a = h.against_lines[-1]
            why.append(CaseFileLine(text="Against: " + _sentence(a.text[0].lower() + a.text[1:]), evidence_ids=a.evidence_ids))
        expl.append(HypothesisExplainer(id=h.id, why=why))

    nxt = None
    if r.next_check:
        nc = r.next_check
        text = nc.label + ". " + (nc.reason + " " if nc.reason else "") + " ".join(f"{o.label}: {o.then}." for o in nc.outcomes)
        nxt = CaseFileLine(text=text, evidence_ids=[u.evidence_id])
    return CaseFile(summary=summary, hypotheses=expl, next_check_explainer=nxt, limits=r.limits)


def validate_narrative(cf: CaseFile, r: CaseResult) -> list[str]:
    """Return a list of problems; empty means the narrative may be shown."""
    valid = {e.id for e in r.evidence}
    errors: list[str] = []

    def check_line(where: str, ln: CaseFileLine):
        if not ln.text.strip():
            errors.append(f"{where}: empty text")
        if not ln.evidence_ids:
            errors.append(f"{where}: no evidence id")
        for i in ln.evidence_ids:
            if i not in valid:
                errors.append(f"{where}: unknown evidence id {i}")
        for i in EVIDENCE_REF.findall(ln.text):
            if i not in valid:
                errors.append(f"{where}: text cites unknown evidence id {i}")

    check_line("summary", cf.summary)
    expected = explained_ids(r)
    got = [h.id for h in cf.hypotheses]
    if got != expected:
        errors.append(f"hypotheses {got} do not match the engine order {expected}")
    for h in cf.hypotheses:
        if not h.why:
            errors.append(f"{h.id}: no lines")
        for n, ln in enumerate(h.why):
            check_line(f"{h.id}[{n}]", ln)
    if r.next_check is not None and r.next_check.hypotheses:
        if cf.next_check_explainer is None:
            errors.append("next_check_explainer missing")
        else:
            check_line("next_check_explainer", cf.next_check_explainer)
    if not cf.limits.strip():
        errors.append("limits missing")
    return errors
