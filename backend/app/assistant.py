"""Ask FieldDx: answers an officer's question about the fields in their area from the area's own data.

Retrieval first. Every case and every watched field of the area becomes a short plain-text document, and
the area itself one more (counts, dates, weather). A question is matched to documents by field number
first ("field 94", "F094", "plot 128"), then by word overlap (BM25). The case the officer has open always
comes first, with its evidence in full. Gemini answers only from those documents and cites the fields it
used; with no key, no network or a failed call, the best-matching documents are returned as they are, so
the assistant never depends on the model.
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta

from . import areas, config, data, llm, service
from .models import CaseResult

log = logging.getLogger("fielddx.assistant")

OUTCOME_WORDS = {
    "field_case": "needs a call or a visit",
    "unexplained": "needs a call or a visit; no single cause is clear yet",
    "watch": "watching: seen on one clear pass only, waiting for the next before sending anyone",
    "area_alert": "area-wide event: similar fields nearby changed too, so not this farm's own problem",
    "auto_dismissed": "set aside automatically, no visit needed",
    "resolved": "resolved after a check on the ground",
}
STOP = set("""a an and are as at be been but by can could did do does for from had has have how i if in into is it its
me my no not of on or our should so that the their them then there these they this to was we were what when where which
who why will with would you your about any field fields plot plots farm crop please tell show give""".split())
FIELD_REF = re.compile(r"\b(?:field|plot|farm|f)\s*[-#]?\s*0*(\d{1,4})\b", re.I)
MAX_DOCS = 7


@dataclass
class Doc:
    id: str            # case or field id, or "area"
    title: str
    kind: str          # "case", "field" or "area"
    text: str
    link: str | None = None


def _conf(c: str) -> str:
    return {"high": "high confidence", "medium": "medium confidence", "low": "low confidence"}[c]


def case_text(r: CaseResult, full: bool = False) -> str:
    f = r.field
    lines = [
        f"{f.name} (case {r.case_id}). {f.class_label}, {f.area_ha} ha, read "
        f"{'as one zone' if f.mode == 'whole' else 'in eight zones'}.",
        f"Status: {OUTCOME_WORDS.get(r.outcome, r.outcome)}. Severity: {r.severity or 'none'}. "
        f"Alert raised {r.alert_date:%d %b %Y}; data as of {r.as_of:%d %b %Y}.",
    ]
    if r.headline:
        h = r.headline
        lines.append(f"Change: NDVI {h.delta:+.2f} in the {h.zone_label.lower()} on {h.date:%d %b %Y} "
                     f"against the field's own baseline ({h.baseline_label}); scene {h.quality}.")
    if r.stage_outcome:
        so = r.stage_outcome
        lines.append(f"{so.title}. Reason: {so.reason}." + (f" To confirm: {so.confirm_with}" if so.confirm_with else ""))
    live = [h for h in r.hypotheses if h.status in ("leading", "possible") and h.stage == 3]
    for i, h in enumerate(live):
        head = "Most likely cause" if i == 0 else "Also possible"
        lines.append(f"{head}: {h.name} ({_conf(h.confidence)}).")
        for ln in h.for_lines:
            lines.append(f"  For {h.name.lower()}: {ln.text} [{', '.join(ln.evidence_ids)}]")
        for ln in h.against_lines:
            lines.append(f"  Against {h.name.lower()}: {ln.text} [{', '.join(ln.evidence_ids)}]")
        for ln in h.unknown_lines:
            lines.append(f"  Unknown: {ln.text}")
    ruled = [h for h in r.hypotheses if h.status == "ruled_out" and h.brief]
    if ruled:
        lines.append("Ruled out: " + "; ".join(f"{h.name} ({h.brief})" for h in ruled) + ".")
    if r.next_check:
        nc = r.next_check
        lines.append(f"Next best check: {nc.label} About {nc.cost_min} minutes.")
        for o in nc.outcomes:
            lines.append(f"  If {o.label.lower()}: {o.then}")
    if r.visit_checklist and r.outcome == "unexplained":
        lines.append("Visit checklist: " + " ".join(r.visit_checklist[:4]))
    if r.update:
        u = r.update
        moves = "; ".join(f"{m.name}: {m.movement.replace('_', ' ')}" for m in u.moves)
        lines.append(f"Investigation updated on {u.recorded_at[:10]}: {u.check_label} found '{u.outcome_label}'. "
                     f"{moves}. The case is still open; no cause is confirmed." + (f" Officer's note: {u.note}" if u.note else ""))
    if r.narrative:
        lines.append(f"Case file summary: {r.narrative.summary.text}")
    if full:
        lines.append("Evidence:")
        for e in r.evidence:
            lines.append(f"  {e.id} {e.title} ({e.as_of:%d %b}, {e.quality}): {e.finding}")
        if r.limits:
            lines.append(f"Limits: {r.limits}")
    return "\n".join(lines)


def field_text(rec: data.FieldRec) -> str:
    months = sorted(rec.monthly.items())[-6:]
    trend = ", ".join(f"{m} {v:.2f}" for m, v in months) if months else "no monthly values"
    klass = {"perennial": "perennial canopy", "seasonal": "seasonal crop"}.get(rec.klass, "crop not identified")
    return (f"{rec.name} (field {rec.id}). {klass}, {rec.area_ha} ha. No alert in the last 21 days, so nothing "
            f"stands out on the satellite passes. Monthly NDVI: {trend}.")


def area_text(area: str) -> str:
    meta = areas.load(area) or {}
    rows = service.inbox(area)
    cnt = Counter(r["outcome"] for r in rows)
    harvest = sum(1 for r in rows if r["kind"] == "harvest")
    cf = data.cases_file(area)
    lines = [
        f"Area {meta.get('name', area)}, {meta.get('region', '')}. {len(data.fields(area))} fields watched. "
        f"Satellite data as of {cf['as_of']}.",
        f"{len(rows)} fields raised an alert (a zone 0.10 NDVI or more below its own baseline in the last 21 days): "
        f"{cnt['field_case'] + cnt['unexplained']} need a call or a visit, {cnt['watch']} are being watched, "
        f"{cnt['area_alert']} are area-wide events, {harvest} look like a harvest, "
        f"{cnt['auto_dismissed'] - harvest} were set aside for other reasons, {cnt['resolved']} are resolved.",
    ]
    visit = [r for r in rows if r["outcome"] in ("field_case", "unexplained")]
    if visit:
        lines.append("Fields that need a person, most urgent first: " + "; ".join(
            f"{r['field']['name']} ({r['severity'] or 'no'} severity, {r['leading']})" for r in visit[:10]) + ".")
    try:
        days = data.weather(area)
        end = days[-1].date
        recent = [d for d in days if d.date > end - timedelta(days=21)]
        rain = sum(d.rain_mm or 0 for d in recent)
        tmax = max((d.tmax_c for d in recent if d.tmax_c is not None), default=None)
        lines.append(f"Weather in the 21 days to {end:%d %b %Y}: {rain:.0f} mm of rain"
                     + (f", hottest day {tmax:.0f} °C" if tmax is not None else "") + " (Open-Meteo reanalysis).")
    except (OSError, KeyError, ValueError, IndexError):
        pass
    lines.append("Sources: Sentinel-2 L2A imagery via Google Earth Engine with clouds masked, field shapes from "
                 "Fields of the World, weather from Open-Meteo. The crop itself is not known; harvest windows are inferred.")
    return "\n".join(lines)


def documents(area: str) -> list[Doc]:
    docs = [Doc("area", (areas.load(area) or {}).get("name", area), "area", area_text(area))]
    with_case = set()
    for c in data.case_specs(area):
        r = service.attach_stored_narrative(area, service.effective_case(area, c["id"]))
        with_case.add(r.field.id)
        docs.append(Doc(r.case_id, r.field.name, "case", case_text(r), f"/case/{r.case_id}"))
    for fid, rec in data.fields(area).items():
        if fid not in with_case:
            docs.append(Doc(fid, rec.name, "field", field_text(rec)))
    return docs


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9ऀ-ॿ]+", text.lower()) if t not in STOP and len(t) > 1]


def _bm25(query: list[str], docs: list[Doc]) -> list[float]:
    toks = [_tokens(d.text) for d in docs]
    n = len(docs)
    avg = sum(len(t) for t in toks) / max(1, n)
    df = Counter(w for t in toks for w in set(t))
    scores = []
    for t in toks:
        tf = Counter(t)
        s = 0.0
        for w in set(query):
            if w not in tf:
                continue
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            s += idf * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(t) / avg))
        scores.append(s)
    return scores


def retrieve(area: str, question: str, case_id: str | None = None, history: list[dict] | None = None) -> list[Doc]:
    docs = documents(area)
    by_id = {d.id: d for d in docs}
    picked: list[Doc] = []

    def add(d: Doc | None):
        if d is not None and d not in picked and len(picked) < MAX_DOCS:
            picked.append(d)

    if case_id and case_id in by_id:
        r = service.attach_stored_narrative(area, service.effective_case(area, case_id))
        d = by_id[case_id]
        add(Doc(d.id, d.title, d.kind, case_text(r, full=True), d.link))
    # field numbers named in the question, or in the last turns when the question says "it" or "that field"
    recent = " ".join(h.get("text", "") for h in (history or [])[-2:])
    for text in (question, recent):
        for num in FIELD_REF.findall(text):
            add(by_id.get(f"F{int(num):03d}"))
    add(by_id["area"])
    scores = _bm25(_tokens(question), docs)
    for s, d in sorted(zip(scores, docs), key=lambda x: -x[0]):
        if s <= 0:
            break
        add(d)
    return picked


RULES = """You are Ask FieldDx, the assistant of a field officer at a farmer producer organisation in India.
FieldDx watches the officer's fields with Sentinel-2 satellite passes and explains why a field lost greenness.
Rules:
1. Answer ONLY from the CONTEXT below. If the answer is not there, say plainly that FieldDx does not have it
   and say what the officer could check on the ground. Never guess.
2. Never invent numbers, dates, crop names, pests, chemicals or doses. Do not prescribe sprays or fertiliser;
   say an agronomist should confirm any treatment.
3. Name fields as they are named ("Field 128"). When you use a fact from a field, cite it as [F128]. You may
   also cite evidence as [F128 E2].
4. Plain, short sentences a field officer can act on. No jargon: say "greenness" and give NDVI only as a number in
   brackets. Use a short list only when comparing several fields. Keep to about 120 words unless asked for more.
5. Asked what to check or what to ask the farmer, turn the field's next best check and its possible results (or
   its visit checklist) into a few simple questions or steps, and say what each answer would mean.
6. When the officer has a field open, do not repeat its name in every sentence; cite its evidence as [E2].
7. Reply in the language of the question (English, Hindi or Marathi).
"""


def build_prompt(question: str, docs: list[Doc], history: list[dict], case_id: str | None) -> str:
    ctx = "\n\n".join(f"--- {d.kind.upper()} {d.id}: {d.title}\n{d.text}" for d in docs)
    turns = "\n".join(f"{'Officer' if h.get('role') == 'user' else 'FieldDx'}: {h.get('text', '')[:600]}"
                      for h in history[-6:])
    focus = (f"The officer has {case_id} open; 'this field' means {case_id}. Cite its evidence as [E1], [E2].\n"
             if case_id else "")
    return f"{RULES}\nCONTEXT:\n{ctx}\n\n{focus}CONVERSATION SO FAR:\n{turns or '(none)'}\n\nOfficer: {question}\nFieldDx:"


def _call_model(prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(http_options=types.HttpOptions(timeout=int(config.LLM_TIMEOUT_S * 1000)))
    # a short answer over a given context needs little thinking: about 4 s instead of 15 s on Gemini 3
    try:
        cfg = types.GenerateContentConfig(temperature=0.2, thinking_config=types.ThinkingConfig(thinking_level="low"))
        resp = client.models.generate_content(model=config.GEMINI_MODEL, contents=prompt, config=cfg)
    except Exception as e:
        if "thinking" not in str(e).lower():
            raise
        resp = client.models.generate_content(model=config.GEMINI_MODEL, contents=prompt,
                                              config=types.GenerateContentConfig(temperature=0.2))
    return (resp.text or "").strip()


def _fallback(docs: list[Doc], case_id: str | None) -> str:
    lead = [d for d in docs if d.kind != "area"][:2] or docs[:1]
    parts = []
    for d in lead:
        keep = [ln for ln in d.text.split("\n") if not ln.startswith("  ")][:5]
        parts.append("\n".join(keep))
    head = "The assistant is offline, so here is what FieldDx has on that:" if llm.is_enabled() else \
        "Here is what FieldDx has on that (no language model is set up, so this is the raw record):"
    return head + "\n\n" + "\n\n".join(parts)


def answer(area: str, question: str, case_id: str | None = None, history: list[dict] | None = None) -> dict:
    history = history or []
    docs = retrieve(area, question, case_id, history)
    text, mode = "", "retrieval"
    if llm.is_enabled():
        try:
            text = _call_model(build_prompt(question, docs, history, case_id))
            mode = "gemini" if text else "retrieval"
        except Exception as e:  # network, quota, blocked or empty response, timeout
            log.warning("assistant call failed: %s", e)
    if not text:
        text = _fallback(docs, case_id)
    cited = set(re.findall(r"\[(F\d{3,4})", text))
    if case_id and re.search(r"\[E\d+", text):
        cited.add(case_id)
    sources = [{"id": d.id, "title": d.title, "kind": d.kind, "link": d.link, "cited": d.id in cited}
               for d in docs if d.kind != "area"]
    sources.sort(key=lambda s: not s["cited"])
    return {"answer": text, "mode": mode, "sources": sources[:5]}
