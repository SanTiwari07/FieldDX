"""Areas: the piece of land an officer is responsible for, and the build that turns it into data.

An area is a polygon the officer marked (drawn, typed as coordinates, or the fields they picked from
the Fields of the World map). Building it runs scripts/build_area.py, which fetches real field
boundaries, real Sentinel-2 passes and real weather for that polygon and then detects the alerts.
Only one build runs at a time; progress is written by the script to build.json in the area folder.
"""
from __future__ import annotations

import json
import math
import os
import re
import secrets
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from . import config, data

_lock = threading.Lock()
_queue: list[str] = []
_running: dict[str, subprocess.Popen] = {}
_worker: threading.Thread | None = None
_on_ready = []  # callbacks(area_id) once a build finishes


class AreaError(ValueError):
    pass


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    tmp.replace(path)


# ---- geometry helpers (lon/lat GeoJSON, small areas, so an equirectangular measure is enough)

def _rings(geom: dict) -> list[list[list[float]]]:
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [p[0] for p in geom["coordinates"]]
    raise AreaError("The area must be a polygon")


def area_km2(geom: dict) -> float:
    total = 0.0
    for ring in _rings(geom):
        lat0 = sum(p[1] for p in ring) / len(ring)
        kx, ky = 111.32 * math.cos(math.radians(lat0)), 110.57
        pts = [(p[0] * kx, p[1] * ky) for p in ring]
        total += abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2
    return total


def bbox_of(geom: dict) -> list[float]:
    pts = [p for ring in _rings(geom) for p in ring]
    return [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]


def _valid_geom(geom: dict) -> dict:
    if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
        raise AreaError("The area must be a polygon")
    for ring in _rings(geom):
        if len(ring) < 4:
            raise AreaError("A polygon needs at least three corners")
        for lon, lat, *_ in ring:
            if not (-180 <= lon <= 180 and -60 <= lat <= 75):
                raise AreaError("A corner is outside the map")
        if ring[0] != ring[-1]:
            ring.append(ring[0])
    return geom


# ---- registry

def area_path(area_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{2,48}", area_id or ""):
        raise AreaError("Unknown area")
    return data.area_dir(area_id)


def load(area_id: str) -> dict | None:
    try:
        meta = _read_json(area_path(area_id) / "area.json")
    except AreaError:
        return None
    if meta is None:
        return None
    return {**meta, "build": build_state(area_id, meta)}


def build_state(area_id: str, meta: dict | None = None) -> dict:
    """Where the area's build is: ready, queued, building (with steps) or failed (with the reason)."""
    if data.is_ready(area_id) and not (area_id in _running or area_id in _queue):
        return {"status": "ready"}
    state = _read_json(data.area_dir(area_id) / "build.json") or {}
    status = state.get("status") or ("queued" if area_id in _queue else "failed")
    if area_id in _running:
        status = "building"
    elif area_id in _queue:
        status = "queued"
    elif status in ("building", "queued"):
        status = "interrupted"
    return {**state, "status": status, "queue_position": (_queue.index(area_id) + 1) if area_id in _queue else None}


def summary(meta: dict) -> dict:
    keys = ("id", "name", "region", "bbox", "center", "mode", "field_source", "km2", "created_at", "built_at")
    out = {k: meta.get(k) for k in keys}
    out["status"] = meta["build"]["status"]
    out["geometry"] = meta.get("geometry")
    out["boundary"] = meta.get("boundary")
    if out["status"] == "ready":
        try:
            out["fields"] = len(data.fields(meta["id"]))
            out["as_of"] = data.cases_file(meta["id"])["as_of"]
        except (OSError, KeyError, ValueError):
            pass
    return out


def list_areas() -> list[dict]:
    root = data.areas_root()
    if not root.exists():
        return []
    out = []
    for d in sorted(root.iterdir()):
        if d.is_dir() and (d / "area.json").exists():
            meta = load(d.name)
            if meta:
                out.append(summary(meta))
    return out


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:28] or "area"
    return f"{base}-{secrets.token_hex(2)}"


def create(*, name: str, region: str, geometry: dict, mode: str, field_source: str,
           boundary: dict | None = None, partition: dict | None = None, picked_points: list | None = None,
           created_by: int | None = None) -> dict:
    name = " ".join((name or "").split())[:60]
    if len(name) < 2:
        raise AreaError("Give the area a name")
    if mode not in ("draw", "coords", "pick"):
        raise AreaError("Unknown way of marking the area")
    if field_source not in ("ftw_global", "ftw_model"):
        raise AreaError("Unknown source of field boundaries")
    if field_source == "ftw_global" and not partition:
        raise AreaError("Fields of the World has no published fields for this region; run the model instead")
    if field_source == "ftw_model" and not config.ftw_cli():
        raise AreaError("The Fields of the World model is not installed on this server")
    picks = []
    for p in (picked_points or [])[:500]:
        try:
            picks.append([round(float(p[0]), 7), round(float(p[1]), 7)])
        except (TypeError, ValueError, IndexError):
            raise AreaError("A picked field has no position")
    if mode == "pick" and not picks:
        raise AreaError("Pick at least one field")
    if mode == "pick" and field_source != "ftw_global":
        raise AreaError("Picked fields come from the Fields of the World map")
    geometry = _valid_geom(geometry)
    km2 = area_km2(geometry)
    if km2 < config.AREA_MIN_KM2:
        raise AreaError("The area is too small to hold a field")
    if km2 > config.AREA_MAX_KM2:
        raise AreaError(f"The area is {km2:.0f} km²; keep it under {config.AREA_MAX_KM2:.0f} km² so a year of imagery stays manageable")
    b = bbox_of(geometry)
    area_id = _slug(name)
    folder = data.area_dir(area_id)
    folder.mkdir(parents=True, exist_ok=False)
    meta = {
        "id": area_id, "name": name, "region": " ".join((region or "").split())[:120],
        "bbox": [round(v, 6) for v in b], "center": [round((b[1] + b[3]) / 2, 6), round((b[0] + b[2]) / 2, 6)],
        "geometry": geometry, "km2": round(km2, 2), "boundary": boundary,
        "mode": mode, "field_source": field_source, "partition": partition,
        "picked_points": picks,
        "status": "building", "created_by": created_by, "created_at": _now(),
    }
    _write_json(folder / "area.json", meta)
    _write_json(folder / "build.json", {"status": "queued", "steps": [], "created_at": _now()})
    enqueue(area_id)
    return load(area_id)  # type: ignore[return-value]


# ---- build queue

def enqueue(area_id: str) -> None:
    global _worker
    with _lock:
        if area_id in _queue or area_id in _running:
            return
        _queue.append(area_id)
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_work, daemon=True, name="area-builds")
            _worker.start()


def retry(area_id: str) -> dict:
    meta = load(area_id)
    if meta is None:
        raise AreaError("Unknown area")
    if meta["build"]["status"] in ("ready", "building", "queued"):
        return meta
    enqueue(area_id)
    return load(area_id)  # type: ignore[return-value]


def _work() -> None:
    while True:
        with _lock:
            if not _queue:
                return
            area_id = _queue[0]
        folder = data.area_dir(area_id)
        log = open(folder / "build.log", "a", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                [config.PYTHON, str(config.SCRIPTS_DIR / "build_area.py"), "--area", str(folder)],
                stdout=log, stderr=subprocess.STDOUT, cwd=str(config.ROOT),
            )
            with _lock:
                _queue.pop(0)
                _running[area_id] = proc
            code = proc.wait()
        except OSError as e:
            code = -1
            _write_json(folder / "build.json", {"status": "failed", "error": f"Could not start the build: {e}"})
            with _lock:
                if _queue and _queue[0] == area_id:
                    _queue.pop(0)
        finally:
            log.close()
            with _lock:
                _running.pop(area_id, None)
        data.clear_caches()
        if code == 0 and data.is_ready(area_id):
            meta = _read_json(folder / "area.json") or {}
            meta.update(status="ready", built_at=_now())
            _write_json(folder / "area.json", meta)
            for fn in list(_on_ready):
                fn(area_id)


def on_ready(fn) -> None:
    _on_ready.append(fn)


# ---- the officer's corrections to the field shapes

EDIT_OPS = ("add", "split", "merge", "remove")
_edit_lock = threading.Lock()


def can_edit(area_id: str) -> bool:
    """Shapes can be corrected in an area built with the shapes file, and never in the shipped demo."""
    return area_id != config.DEMO_AREA and (data.area_dir(area_id) / "shapes.geojson").exists()


def edit_fields(area_id: str, op: dict) -> dict:
    """Apply one correction (scripts/edit_fields.py) and return its result. Only the shapes it touches
    are read again from the downloaded imagery, then the area's alerts are detected again."""
    if op.get("op") not in EDIT_OPS:
        raise AreaError("Unknown correction")
    if not can_edit(area_id):
        raise AreaError("Fields in this area cannot be corrected. Rebuild it first." if area_id != config.DEMO_AREA
                        else "The demo area cannot be changed")
    if area_id in _running or area_id in _queue:
        raise AreaError("The area is being built; correct its fields once the build is done")
    if not _edit_lock.acquire(timeout=1):
        raise AreaError("Another correction is still being applied; try again in a moment")
    try:
        proc = subprocess.run(
            [config.PYTHON, str(config.SCRIPTS_DIR / "edit_fields.py"), "--area", str(data.area_dir(area_id)),
             "--op", json.dumps(op)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(config.ROOT), timeout=300,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise AreaError(f"Could not apply the correction: {e}")
    finally:
        _edit_lock.release()
        data.clear_caches()
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
    try:
        result = json.loads(lines[-1])
    except (IndexError, ValueError):
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or [f"exit code {proc.returncode}"]
        raise AreaError(f"Could not apply the correction: {tail[0][:200]}")
    if not result.get("ok"):
        raise AreaError(result.get("message") or "Could not apply the correction")
    for fn in list(_on_ready):  # the area's data changed under its cached cases
        fn(area_id)
    return result


def resume_interrupted() -> None:
    """Builds that were running when the server stopped pick up where they left off."""
    for a in list_areas():
        if a["status"] == "interrupted":
            enqueue(a["id"])
