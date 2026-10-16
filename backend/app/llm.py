"""Gemini writes the case-file prose. It reasons only over evidence the tools produced.

Anything it returns is validated (known evidence IDs, engine order, every line cited). One retry
with the error message, then the template narrative. No key, no network or a bad answer all end
in the template, so the app never depends on the model.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Callable

from pydantic import ValidationError

from . import config
from .models import CaseFile, CaseResult
from .narrative import explained_ids, template_narrative, validate_narrative

log = logging.getLogger("fielddx.llm")

RULES = """You write the plain-language case file for a field officer at a farmer producer organisation.
Hard rules:
1. Use ONLY the evidence listed below. Do not add causes, numbers or facts that are not in it.
2. Every line you write must cite at least one evidence ID such as E1 or E3 in evidence_ids, and only IDs from the list.
3. Do not change the ranking. Explain the hypotheses in exactly the order given.
4. If evidence is missing, say it is unknown. Never guess.
5. Short sentences, plain English, no jargon.
Return JSON only, with exactly this shape:
{"summary": {"text": str, "evidence_ids": [str]},
 "hypotheses": [{"id": str, "why": [{"text": str, "evidence_ids": [str]}]}],
 "next_check_explainer": {"text": str, "evidence_ids": [str]} or null,
 "limits": str}
"""


def is_enabled() -> bool:
    return config.LLM_MODE != "off" and bool(os.environ.get("GEMINI_API_KEY"))


def build_prompt(r: CaseResult) -> str:
    ev = [{"id": e.id, "tool": e.tool, "finding": e.finding, "as_of": e.as_of.isoformat(),
           "quality": e.quality, "source": e.source} for e in r.evidence]
    ranking = [
        {
            "id": h.id, "name": h.name, "confidence": h.confidence, "status": h.status,
            "for": [{"text": ln.text, "evidence_ids": ln.evidence_ids} for ln in h.for_lines],
            "against": [{"text": ln.text, "evidence_ids": ln.evidence_ids} for ln in h.against_lines],
            "unknown": [ln.text for ln in h.unknown_lines],
        }
        for h in r.hypotheses if h.id in explained_ids(r)
    ]
    nc = None
    if r.next_check:
        nc = {"check": r.next_check.label, "minutes": r.next_check.cost_min,
              "outcomes": [{"result": o.label, "means": o.then} for o in r.next_check.outcomes]}
    payload = {
        "field": f"{r.field.name} ({r.field.class_label.lower()})", "outcome": r.outcome,
        "stage_outcome": r.stage_outcome.model_dump() if r.stage_outcome else None,
        "evidence": ev, "hypotheses_in_order": ranking, "next_check": nc, "limits": r.limits,
    }
    return RULES + "\nCASE:\n" + json.dumps(payload, indent=1, default=str)


def _call_model(prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(http_options=types.HttpOptions(timeout=int(config.LLM_TIMEOUT_S * 1000)))
    resp = client.models.generate_content(
        model=config.GEMINI_MODEL, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
    )
    return resp.text or ""


def generate_narrative(r: CaseResult, call: Callable[[str], str] | None = None) -> tuple[CaseFile, str]:
    """Return (narrative, source) where source is 'gemini' or 'template'."""
    if r.update is not None:
        # after a finding the case file is always the template: same words every run, and no model to
        # teach that ruling one cause out never confirms another
        return template_narrative(r), "template"
    if call is None:
        if not is_enabled():
            return template_narrative(r), "template"
        call = _call_model
    prompt = build_prompt(r)
    problem = ""
    for attempt in range(2):
        try:
            text = call(prompt if not problem else f"{prompt}\n\nYour last answer was rejected: {problem}\nFix it and return JSON only.")
            cf = CaseFile.model_validate_json(_strip_fence(text))
            errors = validate_narrative(cf, r)
            if not errors:
                return cf, "gemini"
            problem = "; ".join(errors[:6])
        except (ValidationError, ValueError) as e:
            problem = f"invalid JSON for the schema ({str(e)[:160]})"
        except Exception as e:  # network, quota, blocked or empty response, timeout
            log.warning("LLM call failed: %s", e)
            break
    return template_narrative(r), "template"


def _strip_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    return t
