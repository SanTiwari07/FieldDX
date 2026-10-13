"""FastAPI app: inbox, case, investigation stream, map and timeline data, close case."""
from __future__ import annotations

import json
import threading
from contextlib import asynccontextmanager
import time
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config, data, db, llm, service
from .models import CaseResult, CloseRequest
from .pipeline import build_case, iter_events
from .raster import raster as build_raster
from .resolve import CloseError, apply_outcome
from .tools.common import build_ctx, quality_of

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Compute every case once in the background so the inbox opens fast."""
    def run():
        for c in data.case_specs():
            build_case(c["id"])
    threading.Thread(target=run, daemon=True).start()
    yield


app = FastAPI(title="FieldDx", version="0.2.0", lifespan=lifespan)


def _case_or_404(case_id: str) -> CaseResult:
    if data.case_spec(case_id) is None:
        raise HTTPException(404, f"No case {case_id}")
    return service.effective_case(case_id)


@app.get("/api/health")
def health():
    return {"ok": True, "llm": "gemini" if llm.is_enabled() else "template", "model": config.GEMINI_MODEL,
            "fields": len(data.fields()), "cases": len(data.case_specs())}


@app.get("/api/cases")
def list_cases():
    return {"banner": data.cases_file()["banner"], "as_of": data.cases_file()["as_of"],
            "provenance": data.provenance(), "cases": service.inbox()}


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
        for kind, payload in iter_events(case_id):
            if kind == "diagnosis":
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


def _latlon(rings: list) -> list:
    return [[[c[1], c[0]] for c in ring] for ring in rings]


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
        obs = ref.zones[z] if ref else None
        zones.append({
            "id": z, "label": data.ZONE_LABEL[z], "polygon": _latlon(f.zone_polygons.get(z, [])),
            "pixels": f.zone_pixels[z], "delta": ctx.series.delta(ref, z) if ref else None,
            "quality": quality_of(obs.valid) if obs else "none", "affected": z in affected,
        })
    outline = _latlon(f.outline)
    pts = [p for ring in outline for p in ring]
    lats, lons = [p[0] for p in pts], [p[1] for p in pts]
    return {
        "field_id": f.id, "name": f.name, "outline": outline, "zones": zones,
        "bounds": [[min(lats), min(lons)], [max(lats), max(lons)]],
        "scene_date": ref.date.isoformat() if ref else None,
        "baseline": ctx.series.baseline_label(), "analysis_pixels": f.analysis_pixels,
    }


@app.get("/api/cases/{case_id}/series")
def case_series(case_id: str):
    r = _case_or_404(case_id)
    f = data.fields()[r.field.id]
    ctx = build_ctx(f.id, r.alert_date, r.as_of)
    affected = []
    for e in r.evidence:
        if e.tool == "spatial_pattern":
            affected = e.data.get("affected_zones", [])
    if r.headline and r.headline.zone == "__field__":
        affected = list(data.ANALYSIS)
    elif not affected and r.headline:
        affected = [r.headline.zone]

    rows = []
    for sc in ctx.series.scenes:
        if sc.date > r.as_of:
            continue
        zones = {}
        for z in data.ANALYSIS:
            obs = sc.zones[z]
            q = quality_of(obs.valid)
            zones[z] = {"ndvi": obs.ndvi if (obs.ndvi is not None and q != "cloudy") else None, "quality": q}
        rows.append({"date": sc.date.isoformat(), "quality": ctx.series.scene_class(sc), "zones": zones})

    windows = []
    year = r.alert_date.year
    for w in data.calendar().get(f.klass, {}).get("windows", []):
        sm, sd = map(int, w["start"].split("-"))
        em, ed = map(int, w["end"].split("-"))
        windows.append({"id": w["id"], "label": w["label"], "start": date(year, sm, sd).isoformat(),
                        "end": date(year, em, ed).isoformat(), "verified": w.get("verified", False)})
    return {
        "zones": [{"id": z, "label": data.ZONE_LABEL[z], "affected": z in affected} for z in data.ANALYSIS],
        "scenes": rows, "windows": windows,
        "alert_date": r.alert_date.isoformat(), "as_of": r.as_of.isoformat(),
        "baseline": ctx.series.baseline_label(),
    }


@app.get("/api/cases/{case_id}/raster")
def case_raster(case_id: str, scene: str | None = None):
    """The real 10 m pixels for one scene date (defaults to the headline scene)."""
    r = _case_or_404(case_id)
    ctx = build_ctx(r.field.id, r.alert_date, r.as_of)
    try:
        day = date.fromisoformat(scene) if scene else (r.headline.date if r.headline else r.as_of)
    except ValueError:
        raise HTTPException(422, "scene must be an ISO date")
    out = build_raster(data.fields()[r.field.id], ctx.series, day)
    if out is None:
        raise HTTPException(404, f"No scene on {day}")
    return out


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
    return service.ensure_narrative(service.effective_case(case_id))


@app.get("/api/checks")
def list_checks():
    return data.checks()


@app.get("/api/fields.geojson")
def fields_geojson():
    """The monitored field shapes as GeoJSON, with the current case outcome where there is one."""
    outcome = {c["field_id"]: service.effective_case(c["id"]).outcome for c in data.case_specs()}
    feats = []
    for f in data.fields().values():
        ring = f.outline[0] if f.outline else []
        feats.append({
            "type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"id": f.id, "name": f.name, "class": f.klass, "area_ha": f.area_ha,
                           "case_outcome": outcome.get(f.id)},
        })
    return {"type": "FeatureCollection", "provenance": data.provenance(), "features": feats}


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
