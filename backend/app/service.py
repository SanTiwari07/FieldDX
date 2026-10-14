"""Glue between the pipeline, the stored findings and the narrative."""
from __future__ import annotations

from datetime import datetime

from . import config, data, db
from .llm import generate_narrative
from .models import CaseFile, CaseResult
from .narrative import template_narrative
from .pipeline import build_case, inbox_sort_key
from .resolve import apply_outcome


def effective_case(area: str, case_id: str) -> CaseResult:
    """Pipeline result with the officer's finding applied, if there is one."""
    base = build_case(area, case_id)
    row = db.get_outcome(area, case_id)
    if row:
        base = apply_outcome(base, row["check_id"], row["outcome"], row["note"],
                             datetime.fromisoformat(row["closed_at"]))
    return base


def phase(r: CaseResult) -> str:
    return "closed" if r.outcome == "resolved" else "open"


def narrative_key(area: str, r: CaseResult) -> str:
    return f"{area}:{r.case_id}:{phase(r)}"


def attach_stored_narrative(area: str, r: CaseResult) -> CaseResult:
    """Use a stored narrative if there is one, otherwise the template (fast, no model call)."""
    stored = db.get_narrative(narrative_key(area, r))
    if stored:
        r.narrative, r.narrative_source = CaseFile.model_validate_json(stored[0]), stored[1]  # type: ignore[assignment]
    else:
        r.narrative, r.narrative_source = template_narrative(r), "template"
    return r


def ensure_narrative(area: str, r: CaseResult) -> CaseResult:
    """Generate (Gemini or template) and store, once per case phase."""
    key = narrative_key(area, r)
    if db.get_narrative(key) is None:
        cf, source = generate_narrative(r)
        db.save_narrative(key, cf.model_dump_json(), source, config.GEMINI_MODEL if source == "gemini" else None)
    return attach_stored_narrative(area, r)


def dismissal_kind(r: CaseResult) -> str | None:
    """Why a dismissed case was thrown out, as one word the inbox groups by: a harvest (an expected
    management window that is a harvest, or the crop's normal cycle), another management event, a data
    artefact or boundary mixing."""
    if r.outcome != "auto_dismissed" or not r.stage_outcome:
        return None
    rid, reason = r.stage_outcome.hypothesis_id, (r.stage_outcome.reason or "").lower()
    if rid == "H4" or (rid == "H3" and "harvest" in reason):
        return "harvest"
    return {"H1": "artefact", "H2": "boundary", "H3": "management"}.get(rid)


def green_before(area: str, field_id: str, day) -> float | None:
    """The field's highest monthly NDVI in the two months before the alert's month: was there a green
    crop to harvest?"""
    m = data.fields(area)[field_id].monthly
    y, mo = day.year, day.month
    prev = [f"{y if mo - k > 0 else y - 1}-{(mo - k - 1) % 12 + 1:02d}" for k in (1, 2)]
    vals = [m[k] for k in prev if k in m]
    return max(vals) if vals else None


def inbox(area: str) -> list[dict]:
    rows = []
    results = sorted((effective_case(area, c["id"]) for c in data.case_specs(area)), key=inbox_sort_key)
    for r in results:
        lead = next((h for h in r.hypotheses if h.status in ("leading", "fired")), None)
        if r.outcome == "resolved" and r.resolution:
            lead_name, conf = r.resolution.confirmed_name, "high"
        elif r.outcome == "unexplained":
            ask = (r.visit_checklist[0] if r.visit_checklist else "").split(".")[0].split("It is one")[0].strip()
            lead_name, conf = (ask or "Ask or visit: no clear cause"), None
        elif r.outcome == "watch":
            lead_name, conf = "Waiting for the next clear pass", None
        else:
            lead_name = lead.name if lead else ""
            conf = lead.confidence if lead and r.outcome == "field_case" else None
        reason = r.stage_outcome.reason if r.stage_outcome else None
        rows.append({
            "id": r.case_id, "field": r.field.model_dump(mode="json"),
            "outcome": r.outcome, "severity": r.severity,
            "headline": r.headline.model_dump(mode="json") if r.headline else None,
            "leading": lead_name, "confidence": conf, "reason": reason,
            "stage_title": r.stage_outcome.title if r.stage_outcome else None,
            "alert_date": r.alert_date.isoformat(),
            "kind": dismissal_kind(r), "green_before": green_before(area, r.field.id, r.alert_date),
        })
    return rows
