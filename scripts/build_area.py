"""Build one area end to end from real sources, reporting progress as it goes.

Reads data/areas/<area>/area.json (the polygon the officer marked) and runs, in order:

  boundaries   ftw_global.py (published Fields of the World map) or ftw_fields.py (run the model)
  imagery      export_s2.py: about 13 months of Sentinel-2 L2A with Cloud Score+ (in parallel with the above)
  weather      fetch_weather.py: Open-Meteo archive for the area centre
  fields       build_dataset.py: pick the fields, cut 10 m pixel zones, cut every field out of every pass
  seasons      the harvest window, inferred from last year's NDVI of this area's seasonal fields
  alerts       build_cases.py: every field that trips the NDVI-drop rule becomes a case

Progress goes to build.json next to area.json, which the app polls. A rerun skips imagery it already has.

Run:  python scripts/build_area.py --area data/areas/<area>
"""
from __future__ import annotations

import argparse
import calendar as cal
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import traceback
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from app import config  # noqa: E402

STEPS = [
    ("boundaries", "Field boundaries"),
    ("imagery", "Sentinel-2 passes"),
    ("weather", "Weather"),
    ("fields", "Fields and pixel zones"),
    ("seasons", "Harvest season"),
    ("alerts", "Alerts"),
]
HARVEST_DROP = 0.10  # an area-wide monthly fall in NDVI at least this big reads as a harvest


class Failed(Exception):
    def __init__(self, reason: str, retryable: bool = True):
        super().__init__(reason)
        self.retryable = retryable  # False when retrying the same area cannot help, e.g. no fields in it


class Progress:
    def __init__(self, folder: Path):
        self.path = folder / "build.json"
        self.lock = threading.Lock()
        self.state = {
            "status": "building", "started_at": _now(), "error": None,
            "steps": [{"id": k, "label": label, "state": "queued", "detail": "", "progress": None} for k, label in STEPS],
        }
        self.save()

    def step(self, sid: str, **kw):
        with self.lock:
            for s in self.state["steps"]:
                if s["id"] == sid:
                    if kw.get("state") == "running" and s["state"] != "running":
                        s["started_at"] = _now()
                    if kw.get("state") in ("done", "failed"):
                        s["ended_at"] = _now()
                    s.update(kw)
            self._save()

    def finish(self, status: str, error: str | None = None, retryable: bool = True):
        with self.lock:
            self.state.update(status=status, error=error, retryable=retryable, ended_at=_now())
            self._save()

    def save(self):
        with self.lock:
            self._save()

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1), encoding="utf-8")
        tmp.replace(self.path)


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def run(cmd: list[str], on_line=None) -> str:
    """Run a step's script, echo its output to the build log, and fail with its last words if it fails."""
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    print("$ " + " ".join(cmd), flush=True)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", env=env, cwd=str(HERE.parent))
    tail: list[str] = []
    for raw in proc.stdout:  # type: ignore[union-attr]
        for line in re.split(r"[\r\n]+", raw):
            line = line.strip()
            if not line:
                continue
            print(line, flush=True)
            tail = (tail + [line])[-12:]
            if on_line:
                try:
                    on_line(line)
                except Exception:  # noqa: BLE001  progress parsing must never stop a build
                    pass
    code = proc.wait()
    if code != 0:
        plain = [t for t in tail if not t.startswith(("Traceback", "File ", "  ")) and "Error" not in t[:12]]
        reason = (plain or tail or [f"exit code {code}"])[-1]
        raise Failed(reason, retryable=False) if code == 3 else Failed(f"{reason} (exit code {code})")
    return "\n".join(tail)


def py(script: str, *args: str) -> list[str]:
    return [sys.executable, str(HERE / script), *args]


# ---- steps

def boundaries(folder: Path, meta: dict, p: Progress, year: int) -> tuple[str, str]:
    """Returns (polygons file relative to the area, provenance text)."""
    p.step("boundaries", state="running", detail="Starting")
    if meta["field_source"] == "ftw_global":
        p.step("boundaries", detail=f"Reading the published Fields of the World map ({meta['partition']['code']})")

        def line(s):
            m = re.match(r"(\d+) polygons touch the area; (\d+) inside it from (\d+)", s)
            if m:
                p.step("boundaries", detail=f"{int(m[2]):,} fields from {m[3]} inside the area ({int(m[1]):,} nearby)")
        run(py("ftw_global.py", "--area", str(folder)), line)
        src = json.loads((folder / "raw" / "ftw_global" / "source.json").read_text(encoding="utf-8"))
        filled = f", {src['filled']:,} of them from earlier years filling gaps" if src.get("filled") else ""
        p.step("boundaries", state="done", detail=f"{src['fields']:,} fields from Fields of the World {src['year']}{filled}")
        return "raw/ftw_global/polygons.parquet", src["source"]

    exe = config.ftw_cli()
    if not exe:
        raise Failed("The Fields of the World model is not installed on this server")
    p.step("boundaries", detail="Running the Fields of the World model on two Sentinel-2 dates (slow)")
    b = meta["bbox"]
    run(py("ftw_fields.py", "--bbox", *map(str, b), "--year", str(year), "--ftw", exe,
           "--out", str(folder / "raw" / "ftw_b5")),
        lambda s: p.step("boundaries", detail=s[:140]) if "inference" in s.lower() or "download" in s.lower() else None)
    p.step("boundaries", state="done", detail="Field shapes predicted by the model")
    return ("raw/ftw_b5/polygons.parquet",
            f"Fields of the World (FTW) PRUE EfficientNet-B5 CC-BY model, run on Sentinel-2 L2A scenes of {year} (ftw-tools)")


def imagery(folder: Path, meta: dict, p: Progress, start: date, end: date) -> None:
    p.step("imagery", state="running", detail="Listing Sentinel-2 passes over the area", progress=0.0)
    total = {"n": 0}

    def line(s):
        m = re.match(r"(\d+) acquisition dates", s)
        if m:
            total["n"] = int(m[1])
            have = len(list((folder / "raw" / "s2").glob("20*.tif")))
            p.step("imagery", detail=f"{total['n']} passes since {start:%b %Y}, {have} already here")
        m = re.match(r"\[(\d+)/(\d+)\]", s)
        if m:
            i, n = int(m[1]), int(m[2])
            p.step("imagery", detail=f"Downloaded {i} of {n} passes", progress=round(i / n, 3))
    run(py("export_s2.py", "--bbox", *map(str, meta["bbox"]), "--start", start.isoformat(), "--end", end.isoformat(),
           "--out", str(folder / "raw" / "s2"), "--threads", "6"), line)
    n = len(json.loads((folder / "raw" / "s2" / "dates.json").read_text(encoding="utf-8")))
    p.step("imagery", state="done", detail=f"{n} passes, clouds masked per pixel", progress=1.0)


def weather(folder: Path, meta: dict, p: Progress, start: date, end: date) -> None:
    p.step("weather", state="running", detail="Open-Meteo archive for the area centre")
    lat, lon = meta["center"]
    out = run(py("fetch_weather.py", "--lat", str(lat), "--lon", str(lon), "--start", start.isoformat(),
                 "--end", end.isoformat(), "--out", str(folder / "weather.json"), "--cluster", meta["id"]))
    m = re.search(r"(\d+) days .*last day (\S+)\)", out)
    p.step("weather", state="done", detail=f"{m[1]} days to {m[2]}" if m else "Daily rain, heat, humidity, soil moisture")


def fields(folder: Path, p: Progress, polygons: str, provenance: str, app_from: date) -> None:
    p.step("fields", state="running", detail="Choosing fields big and clear enough to diagnose")
    skipped: dict = {}

    def line(s):
        m = re.match(r"(\d+) FTW polygons", s)
        if m:
            p.step("fields", detail=f"{int(m[1]):,} field shapes in the area")
        m = re.match(r"(\d+) pass area", s)
        if m:
            p.step("fields", detail=f"{int(m[1]):,} pass the size, shape and cropland checks; cutting pixels")
        if s.startswith("skipped: "):
            skipped["why"] = s[len("skipped: "):]
    run(py("build_dataset.py", "--area", str(folder), "--app-from", app_from.isoformat(),
           "--fields", polygons, "--boundaries", provenance), line)
    n = len(json.loads((folder / "fields.geojson").read_text(encoding="utf-8"))["features"])
    p.step("fields", state="done", detail=f"{n} fields monitored at 10 m" + (f"; left out: {skipped['why']}" if skipped.get("why") else ""))


def seasons(folder: Path, p: Progress) -> None:
    """Harvest windows from the data itself: months in which this area's seasonal fields fell together."""
    p.step("seasons", state="running", detail="Reading last year's NDVI")
    feats = json.loads((folder / "fields.geojson").read_text(encoding="utf-8"))["features"]
    by_month = defaultdict(list)
    for f in feats:
        if f["properties"].get("class") == "seasonal":
            for m, v in f["properties"].get("ndvi_monthly", {}).items():
                by_month[m].append(v)
    n_seasonal = sum(1 for f in feats if f["properties"].get("class") == "seasonal")
    med = {m: statistics.median(v) for m, v in sorted(by_month.items()) if len(v) >= max(3, n_seasonal * 0.3)}
    months = sorted(med)
    falls = []
    for a, b in zip(months, months[1:]):
        ya, ma = map(int, a.split("-"))
        yb, mb = map(int, b.split("-"))
        if (yb * 12 + mb) - (ya * 12 + ma) == 1 and med[a] - med[b] >= HARVEST_DROP:
            falls.append((med[a] - med[b], a, b))
    falls.sort(reverse=True)
    chosen = []
    for drop, a, b in falls:
        if all(abs(int(a[5:]) - int(c[1][5:])) % 12 > 1 for c in chosen):
            chosen.append((drop, a, b))
        if len(chosen) == 2:
            break

    windows = []
    for drop, a, b in sorted(chosen, key=lambda c: c[1][5:]):
        ma, mb = int(a[5:]), int(b[5:])
        name = f"{cal.month_abbr[ma]}–{cal.month_abbr[mb]}"
        common = {
            "verified": False,
            "ask": "Ask the farmer: has the crop been harvested? One phone call settles it.",
            "source": (f"Inferred from this area's Sentinel-2 NDVI: the median seasonal field fell {drop:.2f} from "
                       f"{cal.month_name[ma]} to {cal.month_name[mb]} {b[:4]}. Not verified with an agronomist."),
        }
        last = cal.monthrange(2001, mb)[1]
        if mb > ma:
            windows.append({"id": f"harvest_{a[5:]}", "label": f"Harvest season ({name}, inferred)",
                            "start": f"{ma:02d}-01", "end": f"{mb:02d}-{last:02d}", **common})
        else:  # December to January: two windows, one each side of the new year
            windows.append({"id": f"harvest_{a[5:]}a", "label": f"Harvest season ({name}, inferred)",
                            "start": f"{ma:02d}-01", "end": "12-31", **common})
            windows.append({"id": f"harvest_{a[5:]}b", "label": f"Harvest season ({name}, inferred)",
                            "start": "01-01", "end": f"{mb:02d}-{last:02d}", **common})
    out = {
        "_note": ("Management windows inferred from this area's own NDVI by scripts/build_area.py. They are not "
                  "verified with an agronomist and the app says so wherever one is used. Perennial canopy has no "
                  "inferred window: pruning and similar work cannot be told apart from the satellite record alone."),
        "classes": {"seasonal": {"windows": windows}, "perennial": {"windows": []}, "unknown": {"windows": []}},
    }
    (folder / "calendar.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    spans = [f"{cal.month_abbr[int(a[5:])]}–{cal.month_abbr[int(b[5:])]}" for _d, a, b in sorted(chosen, key=lambda c: c[1][5:])]
    p.step("seasons", state="done",
           detail=f"Harvest seen in {' and '.join(spans)} last year (inferred)" if spans
           else "No clear area-wide harvest in last year's NDVI")


def alerts(folder: Path, p: Progress) -> None:
    p.step("alerts", state="running", detail="Looking for drops against each field's own baseline")
    out = run(py("build_cases.py", "--area", str(folder)))
    m = re.search(r"(\d+) alerts from (\d+) fields, data to (\S+)", out)
    p.step("alerts", state="done", detail=f"{m[1]} alerts from {m[2]} fields, data to {m[3]}" if m else "Done")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", required=True)
    folder = Path(ap.parse_args().area).resolve()
    meta = json.loads((folder / "area.json").read_text(encoding="utf-8"))
    p = Progress(folder)
    for stale in ("cases.json",):  # a rebuild is not ready until its alerts are written again
        (folder / stale).unlink(missing_ok=True)

    today = date.today()
    app_from = today - timedelta(days=125)
    img_start, img_end = today - timedelta(days=395), today + timedelta(days=1)
    print(f"building {meta['id']} ({meta.get('name')}) on {today}", flush=True)
    try:
        result: dict = {}
        errors: list[BaseException] = []

        def guard(name, fn, *a):
            try:
                result[name] = fn(*a)
            except BaseException as e:  # noqa: BLE001
                errors.append(e)
                p.step(name, state="failed", detail=str(e)[:240])

        t1 = threading.Thread(target=guard, args=("boundaries", boundaries, folder, meta, p, today.year - 1))
        t2 = threading.Thread(target=guard, args=("imagery", imagery, folder, meta, p, img_start, img_end))
        t1.start(); t2.start(); t1.join(); t2.join()
        if errors:
            raise errors[0]
        for name, fn, args in (
            ("weather", weather, (folder, meta, p, app_from - timedelta(days=10), today - timedelta(days=1))),
            ("fields", fields, (folder, p, *result["boundaries"], app_from)),
            ("seasons", seasons, (folder, p)),
            ("alerts", alerts, (folder, p)),
        ):
            try:
                fn(*args)
            except BaseException as e:
                p.step(name, state="failed", detail=str(e)[:240])
                raise
    except Failed as e:
        p.finish("failed", str(e), retryable=e.retryable)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        p.finish("failed", f"{type(e).__name__}: {e}")
        sys.exit(1)
    p.finish("ready")
    print(f"area {meta['id']} ready", flush=True)


if __name__ == "__main__":
    main()
