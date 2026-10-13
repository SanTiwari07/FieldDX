"""FastAPI app: inbox, case, investigation stream, map and timeline data, close case."""
from __future__ import annotations

import json
import time
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config, data, db, llm, service
from .models import CaseResult, CloseRequest
from .pipeline import build_case, iter_events
from .resolve import CloseError, apply_outcome
from .tools.common import build_ctx, quality_of

app = FastAPI(title="FieldDx", version="0.1.0")


def _case_or_404(case_id: str) -> CaseResult:
    if data.case_spec(case_id) is None:
        raise HTTPException(404, f"No case {case_id}")
    return service.effective_case(case_id)


@app.get("/api/health")
def health():
    return {"ok": True, "llm": "gemini" if llm.is_enabled() else "template",
            "model": config.GEMINI_MODEL}


@app.get("/api/cases")
def list_cases():
    return {"banner": data.scenarios().get("banner", ""), "as_of": data.scenarios()["as_of"],
            "cases": service.inbox()}


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    return service.attach_stored_narrative(_case_or_404(case_id))


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


@app.get("/api/cases/{case_id}/investigate")
def investigate(case_id: str, pace: int | None = Query(None, ge=0, le=2000)):
    """Server-sent events: steps and evidence one by one, then the diagnosis and the narrative."""
    if data.case_spec(case_id) is None:
        raise HTTPException(404, f"No case {case_id}")
    delay = (config.DEMO_PACING_MS if pace is None else pace) / 1000.0

    def stream():
        final = None
        for kind, payload in iter_events(case_id):
            if kind == "diagnosis":
                final = payload
                continue
            if kind == "step" and payload["state"] == "running":
                time.sleep(delay)
            yield _sse(kind, payload)
            if kind == "step" and payload["state"] in ("done", "skipped") and delay:
                time.sleep(delay * 0.35)
        result = service.effective_case(case_id)
        yield _sse("diagnosis", result.model_dump(mode="json"))
        result = service.ensure_narrative(result)
        yield _sse("narrative", {"narrative": result.narrative.model_dump(mode="json"),
                                 "source": result.narrative_source})
        yield _sse("done", {})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _lerp_point(f: data.FieldRec, x: float, y: float) -> list[float]:
    """Local metres within the field to [lat, lon], using the outline corners as the frame."""
    sw, se, _ne, nw = f.outline[0][0], f.outline[0][1], f.outline[0][2], f.outline[0][3]
    w, h = f.size_m
    lon = sw[0] + (se[0] - sw[0]) * x / w
    lat = sw[1] + (nw[1] - sw[1]) * y / h
    return [lat, lon]


@app.get("/api/cases/{case_id}/map")
def case_map(case_id: str):
    r = _case_or_404(case_id)
    f = data.fields()[r.field.id]
    ctx = build_ctx(f.id, r.alert_date, r.as_of)
    ref = ctx.series.scene_at(r.headline.date) if r.headline else ctx.series.latest_usable(r.as_of)
    affected = []
    for e in r.evidence:
        if e.tool == "spatial_pattern":
            affected = e.data.get("affected_zones", [])
    if not affected and r.headline and r.headline.zone in data.ANALYSIS:
        affected = [r.headline.zone]

    zones = []
    for z in data.ANALYSIS:
        poly = [[c[1], c[0]] for c in f.zone_polygons[z][0]]
        obs = ref.zones[z] if ref else None
        zones.append({
            "id": z, "label": data.ZONE_LABEL[z], "polygon": poly, "pixels": f.zone_pixels[z],
            "delta": ctx.series.delta(ref, z) if ref else None,
            "quality": quality_of(obs.valid) if obs else "none",
            "affected": z in affected,
        })
    w, h = f.size_m
    lines = []
    for i in range(0, w + 1, 10):
        lines.append([_lerp_point(f, i, 0), _lerp_point(f, i, h)])
    for j in range(0, h + 1, 10):
        lines.append([_lerp_point(f, 0, j), _lerp_point(f, w, j)])
    outline = [[c[1], c[0]] for c in f.outline[0]]
    lats, lons = [p[0] for p in outline], [p[1] for p in outline]
    return {
        "field_id": f.id, "name": f.name, "outline": outline, "zones": zones, "grid": lines,
        "bounds": [[min(lats), min(lons)], [max(lats), max(lons)]],
        "scene_date": ref.date.isoformat() if ref else None,
        "baseline": ctx.series.baseline_label(), "size_m": [w, h],
        "analysis_pixels": f.analysis_pixels,
    }


@app.get("/api/cases/{case_id}/series")
def case_series(case_id: str):
    r = _case_or_404(case_id)
    f = data.fields()[r.field.id]
    ctx = build_ctx(f.id, r.alert_date, r.as_of)
    first = ctx.series.scenes[0].date
    affected = []
    for e in r.evidence:
        if e.tool == "spatial_pattern":
            affected = e.data.get("affected_zones", [])
    if r.headline and r.headline.zone == "__field__":
        affected = list(data.ANALYSIS)
    elif not affected and r.headline:
        affected = [r.headline.zone]

    rows, d = [], first
    while d <= r.as_of:
        sc = ctx.series.scene_at(d)
        zones = {}
        for z in data.ANALYSIS:
            if sc is None:
                zones[z] = {"ndvi": None, "quality": "none"}
                continue
            q = quality_of(sc.zones[z].valid)
            zones[z] = {"ndvi": sc.zones[z].ndvi if q != "cloudy" else None, "quality": q}
        rows.append({"date": d.isoformat(), "quality": ctx.series.scene_class(sc), "zones": zones})
        d += timedelta(days=5)

    from .tools.crop_calendar import expected_ndvi
    expected = [{"date": row["date"], "value": round(expected_ndvi(f.crop, f.anchor_date, date.fromisoformat(row["date"])), 3)}
                for row in rows]
    windows = [w for w in data.calendar()[f.crop]["windows"]]
    return {
        "zones": [{"id": z, "label": data.ZONE_LABEL[z], "affected": z in affected} for z in data.ANALYSIS],
        "scenes": rows, "expected": expected, "windows": windows,
        "alert_date": r.alert_date.isoformat(), "as_of": r.as_of.isoformat(),
        "baseline": ctx.series.baseline_label(),
    }


@app.post("/api/cases/{case_id}/close")
def close_case(case_id: str, body: CloseRequest):
    if data.case_spec(case_id) is None:
        raise HTTPException(404, f"No case {case_id}")
    base = build_case(case_id)
    closed_at = db.now()
    try:
        apply_outcome(base, body.check_id, body.outcome, body.note, closed_at)  # validate before saving
    except CloseError as e:
        raise HTTPException(422, str(e))
    if db.get_outcome(case_id):
        raise HTTPException(409, "This case is already closed")
    db.save_outcome(case_id, body.check_id, body.outcome, body.note, closed_at)
    result = service.ensure_narrative(service.effective_case(case_id))
    return result


@app.get("/api/checks")
def list_checks():
    return data.checks()


@app.post("/api/admin/reset")
def reset():
    db.reset()
    return {"ok": True}


# Serve the built frontend when it exists (npm run build)
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        target = config.FRONTEND_DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(config.FRONTEND_DIST / "index.html")
