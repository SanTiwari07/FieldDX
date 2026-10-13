"""FastAPI app: sign-in, the officer's area and its build, then the inbox, case, investigation stream,
map and timeline data, and close case, all scoped to the officer's own area."""
from __future__ import annotations

import json
import re
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import areas, config, data, db, llm, places, service
from .models import CaseResult, CloseRequest
from .pipeline import build_case, iter_events
from .raster import raster as build_raster
from .resolve import CloseError, apply_outcome
from .tools.common import build_ctx, quality_of


def _warm(area: str) -> None:
    """Compute every case of an area once in the background so its inbox opens fast."""
    def run():
        try:
            for c in data.case_specs(area):
                build_case(area, c["id"])
        except (OSError, KeyError, ValueError):
            pass
    threading.Thread(target=run, daemon=True).start()


def _seed_demo() -> None:
    """The officer behind "Explore the demo": works in the area shipped with the repository."""
    if not data.is_ready(config.DEMO_AREA):
        return
    o = db.find_officer("demo")
    if o is None:
        db.create_officer("demo", "Demo officer", secrets.token_urlsafe(18), config.DEMO_AREA)
    elif o["area_id"] is None:
        db.set_officer_area(o["id"], config.DEMO_AREA)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _seed_demo()
    areas.on_ready(_warm)
    areas.resume_interrupted()
    for a in areas.list_areas():
        if a["status"] == "ready":
            _warm(a["id"])
    yield


app = FastAPI(title="FieldDx", version="0.3.0", lifespan=lifespan)


# ---- sign-in

def current_officer(request: Request) -> dict:
    token = request.cookies.get(config.SESSION_COOKIE)
    officer = db.session_officer(token) if token else None
    if officer is None:
        raise HTTPException(401, "Sign in to continue")
    return officer


def current_area(officer: dict = Depends(current_officer)) -> str:
    """The officer's area, once it is built. Every case route reads only this area."""
    area = officer.get("area_id")
    if not area:
        raise HTTPException(409, "Choose the area you work in first")
    if not data.is_ready(area):
        raise HTTPException(409, "Your area is still being set up")
    return area


def _start_session(response: Response, officer: dict) -> dict:
    token = db.open_session(officer["id"])
    response.set_cookie(config.SESSION_COOKIE, token, max_age=config.SESSION_DAYS * 86400,
                        httponly=True, samesite="lax", path="/")
    return _me(officer)


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    pin: str = Field(min_length=1, max_length=64)


class Registration(Credentials):
    name: str = Field(min_length=1, max_length=60)


USERNAME = re.compile(r"[a-z0-9][a-z0-9._-]{2,29}")


@app.post("/api/auth/register")
def register(body: Registration, response: Response):
    username = body.username.strip().lower()
    if not USERNAME.fullmatch(username):
        raise HTTPException(422, "Use 3 to 30 letters, numbers, dots or dashes for the username")
    if username == "demo" or db.find_officer(username):
        raise HTTPException(409, "That username is taken")
    if not re.fullmatch(r"\d{4,8}", body.pin):
        raise HTTPException(422, "The PIN is 4 to 8 digits")
    name = " ".join(body.name.split())
    if len(name) < 2:
        raise HTTPException(422, "Enter your name")
    return _start_session(response, db.create_officer(username, name, body.pin))


@app.post("/api/auth/login")
def login(body: Credentials, response: Response):
    officer = db.check_pin(body.username.strip().lower(), body.pin)
    if officer is None or officer["username"] == "demo":
        time.sleep(0.4)  # slow down guessing
        raise HTTPException(401, "That username and PIN do not match")
    return _start_session(response, officer)


@app.post("/api/auth/demo")
def demo_login(response: Response):
    _seed_demo()
    officer = db.find_officer("demo")
    if officer is None:
        raise HTTPException(404, "The demo area is not available on this server")
    return _start_session(response, officer)


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(config.SESSION_COOKIE)
    if token:
        db.close_session(token)
    response.delete_cookie(config.SESSION_COOKIE, path="/")
    return {"ok": True}


def _me(officer: dict) -> dict:
    meta = areas.load(officer["area_id"]) if officer.get("area_id") else None
    return {
        "officer": {"name": officer["name"], "username": officer["username"], "demo": officer["username"] == "demo"},
        "area": areas.summary(meta) if meta else None,
    }


@app.get("/api/me")
def me(officer: dict = Depends(current_officer)):
    return _me(officer)


# ---- choosing and building the area

@app.get("/api/places")
def search_places(q: str = Query(..., min_length=2, max_length=120), _o: dict = Depends(current_officer)):
    try:
        return {"places": places.search(q)}
    except OSError:
        raise HTTPException(502, "Place search is not reachable right now. Try again, or enter coordinates.")


@app.get("/api/places/fields-source")
def fields_source(country: str = Query(..., max_length=3), subdivision: str = Query("", max_length=8),
                  _o: dict = Depends(current_officer)):
    """Where the published field shapes for a region live, and whether the model can be run here."""
    part = places.ftw_partition(country.upper(), subdivision.upper())
    return {"partition": part, "model_available": config.ftw_cli() is not None,
            "max_km2": config.AREA_MAX_KM2}


@app.get("/api/ftw/{code}.pmtiles")
def ftw_tiles(code: str, request: Request, _o: dict = Depends(current_officer)):
    """Byte ranges of a state's Fields of the World PMTiles, fetched once and served same-origin.

    The browser could read Source Cooperative directly, but over flaky or HTTP/3-hostile networks many
    tile reads fail; through the API they share one connection and a small cache.
    """
    rng = request.headers.get("range", "")
    if not re.fullmatch(r"[A-Z]{2}_[A-Z0-9]{1,3}", code) or not re.fullmatch(r"bytes=\d+-\d+", rng):
        raise HTTPException(400, "Ask for a byte range of a known partition")
    try:
        body, total, etag = places.ftw_range(code, rng)
    except places.NotPublished:
        raise HTTPException(404, "Fields of the World has not published this partition")
    except OSError:
        raise HTTPException(502, "Fields of the World is not reachable right now")
    start = int(rng[6:].split("-")[0])
    headers = {"Content-Range": f"bytes {start}-{start + len(body) - 1}/{total}", "Accept-Ranges": "bytes",
               "Cache-Control": "private, max-age=86400"}
    if etag:
        headers["ETag"] = etag
    return Response(body, status_code=206, media_type="application/octet-stream", headers=headers)


@app.get("/api/areas")
def list_areas(_o: dict = Depends(current_officer)):
    return {"areas": [a for a in areas.list_areas() if a["status"] in ("ready", "building", "queued")]}


class NewArea(BaseModel):
    name: str
    region: str = ""
    geometry: dict
    mode: str
    field_source: str = "ftw_global"
    boundary: dict | None = None
    partition: dict | None = None
    picked_points: list[list[float]] | None = None


@app.post("/api/areas")
def create_area(body: NewArea, officer: dict = Depends(current_officer)):
    if officer["username"] == "demo":
        raise HTTPException(403, "The demo officer works in the demo area. Create your own account to set up an area.")
    part = None
    if body.field_source == "ftw_global":
        # trust only a partition this server can find, never a URL sent by the browser
        code = (body.partition or {}).get("code", "")
        country, _, sub = code.partition("_")
        part = places.ftw_partition(country, sub) if code else None
    try:
        meta = areas.create(name=body.name, region=body.region, geometry=body.geometry, mode=body.mode,
                            field_source=body.field_source, boundary=body.boundary, partition=part,
                            picked_points=body.picked_points, created_by=officer["id"])
    except areas.AreaError as e:
        raise HTTPException(422, str(e))
    db.set_officer_area(officer["id"], meta["id"])
    return _me(db.get_officer(officer["id"]))


class JoinArea(BaseModel):
    area_id: str | None


@app.post("/api/me/area")
def set_my_area(body: JoinArea, officer: dict = Depends(current_officer)):
    if officer["username"] == "demo" and body.area_id != config.DEMO_AREA:
        raise HTTPException(403, "The demo officer works in the demo area")
    if body.area_id is not None and areas.load(body.area_id) is None:
        raise HTTPException(404, "No such area")
    db.set_officer_area(officer["id"], body.area_id)
    return _me(db.get_officer(officer["id"]))


@app.get("/api/area/build")
def area_build(officer: dict = Depends(current_officer)):
    if not officer.get("area_id"):
        raise HTTPException(409, "Choose the area you work in first")
    meta = areas.load(officer["area_id"])
    if meta is None:
        raise HTTPException(404, "Your area no longer exists")
    return {"area": areas.summary(meta), "build": meta["build"]}


@app.post("/api/area/retry")
def area_retry(officer: dict = Depends(current_officer)):
    if not officer.get("area_id"):
        raise HTTPException(409, "Choose the area you work in first")
    try:
        meta = areas.retry(officer["area_id"])
    except areas.AreaError as e:
        raise HTTPException(404, str(e))
    return {"area": areas.summary(meta), "build": meta["build"]}


# ---- the area's cases

@app.get("/api/health")
def health():
    return {"ok": True, "llm": "gemini" if llm.is_enabled() else "template", "model": config.GEMINI_MODEL,
            "areas": sum(1 for a in areas.list_areas() if a["status"] == "ready")}


def _case_or_404(area: str, case_id: str) -> CaseResult:
    if data.case_spec(area, case_id) is None:
        raise HTTPException(404, f"No case {case_id} in your area")
    return service.effective_case(area, case_id)


@app.get("/api/home")
def home(area: str = Depends(current_area), officer: dict = Depends(current_officer)):
    """Today's briefing for the officer's area: what the satellites saw and what needs a person."""
    rows = service.inbox(area)
    count = lambda *o: sum(1 for r in rows if r["outcome"] in o)  # noqa: E731
    cf = data.cases_file(area)
    meta = areas.load(area) or {}
    scenes = data.scenes(area, next(iter(data.fields(area))))
    last_pass = max((s.date for s in scenes), default=None)
    return {
        "area": areas.summary(meta) if meta else {"id": area},
        "officer": {"name": officer["name"]},
        "as_of": cf["as_of"], "last_pass": last_pass.isoformat() if last_pass else None,
        "fields": len(data.fields(area)), "alerts": len(rows),
        "counts": {"visit": count("field_case", "unexplained"), "watch": count("watch"),
                   "area_alert": count("area_alert"), "dismissed": count("auto_dismissed"),
                   "resolved": count("resolved")},
        "top": [r for r in rows if r["outcome"] in ("field_case", "unexplained")][:3],
        "detector": cf.get("detector"), "provenance": data.provenance(area),
    }


@app.get("/api/cases")
def list_cases(area: str = Depends(current_area)):
    cf = data.cases_file(area)
    return {"banner": cf["banner"], "as_of": cf["as_of"], "area": (areas.load(area) or {}).get("name", area),
            "provenance": data.provenance(area), "cases": service.inbox(area)}


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, area: str = Depends(current_area)):
    return service.attach_stored_narrative(area, _case_or_404(area, case_id))


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


@app.get("/api/cases/{case_id}/investigate")
def investigate(case_id: str, pace: int | None = Query(None, ge=0, le=2000), area: str = Depends(current_area)):
    """Server-sent events: steps and evidence one by one, then the diagnosis and the narrative."""
    if data.case_spec(area, case_id) is None:
        raise HTTPException(404, f"No case {case_id} in your area")
    delay = (config.DEMO_PACING_MS if pace is None else pace) / 1000.0

    def stream():
        for kind, payload in iter_events(area, case_id):
            if kind == "diagnosis":
                continue
            if kind == "step" and payload["state"] == "running":
                time.sleep(delay)
            yield _sse(kind, payload)
            if kind == "step" and payload["state"] in ("done", "skipped") and delay:
                time.sleep(delay * 0.35)
        result = service.effective_case(area, case_id)
        yield _sse("diagnosis", result.model_dump(mode="json"))
        result = service.ensure_narrative(area, result)
        yield _sse("narrative", {"narrative": result.narrative.model_dump(mode="json"),
                                 "source": result.narrative_source})
        yield _sse("done", {})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _latlon(rings: list) -> list:
    return [[[c[1], c[0]] for c in ring] for ring in rings]


@app.get("/api/cases/{case_id}/map")
def case_map(case_id: str, area: str = Depends(current_area)):
    r = _case_or_404(area, case_id)
    f = data.fields(area)[r.field.id]
    ctx = build_ctx(area, f.id, r.alert_date, r.as_of)
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
def case_series(case_id: str, area: str = Depends(current_area)):
    r = _case_or_404(area, case_id)
    f = data.fields(area)[r.field.id]
    ctx = build_ctx(area, f.id, r.alert_date, r.as_of)
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
    for w in data.calendar(area).get(f.klass, {}).get("windows", []):
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
def case_raster(case_id: str, scene: str | None = None, area: str = Depends(current_area)):
    """The real 10 m pixels for one scene date (defaults to the headline scene)."""
    r = _case_or_404(area, case_id)
    ctx = build_ctx(area, r.field.id, r.alert_date, r.as_of)
    try:
        day = date.fromisoformat(scene) if scene else (r.headline.date if r.headline else r.as_of)
    except ValueError:
        raise HTTPException(422, "scene must be an ISO date")
    out = build_raster(data.fields(area)[r.field.id], ctx.series, day)
    if out is None:
        raise HTTPException(404, f"No scene on {day}")
    return out


@app.post("/api/cases/{case_id}/close")
def close_case(case_id: str, body: CloseRequest, area: str = Depends(current_area),
               officer: dict = Depends(current_officer)):
    if data.case_spec(area, case_id) is None:
        raise HTTPException(404, f"No case {case_id} in your area")
    base = build_case(area, case_id)
    closed_at = db.now()
    try:
        apply_outcome(base, body.check_id, body.outcome, body.note, closed_at)  # validate before saving
    except CloseError as e:
        raise HTTPException(422, str(e))
    if db.get_outcome(area, case_id):
        raise HTTPException(409, "This case is already closed")
    db.save_outcome(area, case_id, body.check_id, body.outcome, body.note, closed_at, officer["id"])
    return service.ensure_narrative(area, service.effective_case(area, case_id))


@app.get("/api/checks")
def list_checks(_o: dict = Depends(current_officer)):
    return data.checks()


@app.get("/api/fields.geojson")
def fields_geojson(area: str = Depends(current_area)):
    """The area's monitored field shapes as GeoJSON, with the current case outcome where there is one."""
    outcome = {c["field_id"]: service.effective_case(area, c["id"]).outcome for c in data.case_specs(area)}
    feats = []
    for f in data.fields(area).values():
        ring = f.outline[0] if f.outline else []
        feats.append({
            "type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"id": f.id, "name": f.name, "class": f.klass, "area_ha": f.area_ha,
                           "case_outcome": outcome.get(f.id)},
        })
    meta = areas.load(area) or {}
    return {"type": "FeatureCollection", "provenance": data.provenance(area), "features": feats,
            "area": {"geometry": meta.get("geometry"), "bbox": meta.get("bbox")}}


@app.post("/api/admin/reset")
def reset(area: str = Depends(current_area)):
    """Clear closed cases and stored narratives in the officer's area, so a demo starts clean."""
    db.reset(area)
    return {"ok": True}


# Serve the built frontend when it exists (npm run build)
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "No such API route")
        target = config.FRONTEND_DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(config.FRONTEND_DIST / "index.html")
