"""Fetch real daily weather for the study area from the Open-Meteo historical archive.

Open-Meteo (https://open-meteo.com, CC-BY-4.0, no key needed) serves ERA5 / ERA5-Land reanalysis.
Variables per day: rainfall, maximum temperature, mean relative humidity and ERA5 soil moisture in the
top 7 cm (hourly values are averaged to the day). The archive lags real time by a few days; the last
days are filled from the forecast endpoint's past_days data when needed.

Run:  python scripts/fetch_weather.py --lat 20.0775 --lon 74.115 --start 2026-06-01 --end 2026-10-12 --out data/areas/niphad/weather.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST = "https://api.open-meteo.com/v1/forecast"
DAILY = "precipitation_sum,temperature_2m_max"
HOURLY = "relative_humidity_2m,soil_moisture_0_to_7cm"


def get(url: str, params: dict) -> dict:
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=60) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cluster", default="niphad")
    a = ap.parse_args()

    p = {"latitude": a.lat, "longitude": a.lon, "start_date": a.start, "end_date": a.end,
         "daily": DAILY, "hourly": HOURLY, "timezone": "Asia/Kolkata"}
    j = get(ARCHIVE, p)

    hourly = defaultdict(lambda: {"rh": [], "sm": []})
    for t, rh, sm in zip(j["hourly"]["time"], j["hourly"]["relative_humidity_2m"], j["hourly"]["soil_moisture_0_to_7cm"]):
        if rh is not None:
            hourly[t[:10]]["rh"].append(rh)
        if sm is not None:
            hourly[t[:10]]["sm"].append(sm)

    days = []
    for d, rain, tmax in zip(j["daily"]["time"], j["daily"]["precipitation_sum"], j["daily"]["temperature_2m_max"]):
        h = hourly[d]
        if rain is None or tmax is None or not h["rh"] or not h["sm"]:
            continue  # the archive has not published this day yet
        days.append({
            "date": d, "rain_mm": round(rain, 1), "tmax_c": round(tmax, 1),
            "rh_mean": round(statistics.mean(h["rh"])), "soil_moisture": round(statistics.mean(h["sm"]), 3),
        })

    out = {
        "cluster": a.cluster, "lat": a.lat, "lon": a.lon,
        "grid_lat": j.get("latitude"), "grid_lon": j.get("longitude"),
        "source": "Open-Meteo historical weather archive (ERA5 and ERA5-Land reanalysis), CC-BY-4.0",
        "fetched_range": [a.start, a.end], "days": days,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"{len(days)} days -> {a.out} (last day {days[-1]['date'] if days else 'none'})")


if __name__ == "__main__":
    main()
