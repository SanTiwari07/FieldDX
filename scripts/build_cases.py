"""Detect alerts in an area's real data and write its cases.json.

This is the stage before the investigation: a plain NDVI-drop detector, the thing FieldDx is built to
sit behind. A field raises an alert when, on any clear or partly clear pass in the last 21 days of
data, a zone is at least 0.10 NDVI below that field's own baseline (the median of clear passes 25 to
45 days before) and that zone has at least 2 valid pixels. The first such pass is the alert date.
Nothing is hand-picked: every field that trips the rule becomes a case, and the engine then decides
whether it is a false alarm, an area event, or something to visit.

Run:  python scripts/build_cases.py --area data/areas/niphad
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import config, data  # noqa: E402
from app.tools.common import Series  # noqa: E402

LOOKBACK_DAYS = 21
MIN_VALID_PIXELS = 2


def detect(area: str, field_id: str, as_of):
    f = data.fields(area)[field_id]
    for sc in data.scenes(area, field_id):
        if sc.date < as_of - timedelta(days=LOOKBACK_DAYS) or sc.date > as_of:
            continue
        ser = Series(f, sc.date)
        if ser.scene_class(sc) not in ("usable", "partial") or not ser.baseline:
            continue
        for z in data.ALL_ZONES:
            obs = sc.zones[z]
            d = ser.delta(sc, z)
            if d is not None and d <= config.SIGNIFICANT_DROP and obs.valid * obs.pixels >= MIN_VALID_PIXELS:
                return sc.date
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", required=True, help="the area folder, e.g. data/areas/niphad")
    folder = Path(ap.parse_args().area).resolve()
    data.areas_root = lambda: folder.parent  # read the area through the app's own loader, wherever it lives
    area = folder.name
    as_of = max(s.date for fid in data.fields(area) for s in data.scenes(area, fid))
    cases = []
    for fid in data.fields(area):
        d = detect(area, fid, as_of)
        if d:
            cases.append({"id": fid, "field_id": fid, "alert_date": d.isoformat()})
    cases.sort(key=lambda c: (c["alert_date"], c["id"]))
    out = {
        "as_of": as_of.isoformat(),
        "banner": ("Real data: Sentinel-2 imagery via Earth Engine with Cloud Score+ masking, field shapes from the "
                   "Fields of the World model, weather from Open-Meteo."),
        "detector": (f"A zone at least {abs(config.SIGNIFICANT_DROP):.2f} NDVI below the field's own baseline on any "
                     f"clear or partly clear pass in the last {LOOKBACK_DAYS} days."),
        "fields_monitored": len(data.fields(area)),
        "cases": cases,
    }
    (folder / "cases.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"{len(cases)} alerts from {len(data.fields(area))} fields, data to {as_of}")


if __name__ == "__main__":
    main()
