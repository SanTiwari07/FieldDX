"""weather: rain, heat, humidity and soil moisture around the alert window."""
from __future__ import annotations

import statistics
from datetime import timedelta

from .. import config, data
from .common import Ctx, ToolResult, fmt_date


def run(ctx: Ctx) -> ToolResult:
    days = data.weather()
    by_date = {d.date: d for d in days}
    end = ctx.as_of
    win = [by_date[end - timedelta(days=i)] for i in range(config.WINDOW_DAYS - 1, -1, -1) if (end - timedelta(days=i)) in by_date]
    if not win:
        return ToolResult(tool="weather", title="Weather", skipped=True, skip_reason="No weather for this window.",
                          quality="none", source="Weather")

    last10 = win[-10:]
    rain_14 = sum(d.rain_mm for d in win)
    rain_10 = sum(d.rain_mm for d in last10)
    wet_days = [d for d in days if d.date <= end and d.rain_mm >= config.RAIN_RECENT_MM]
    since = (end - wet_days[-1].date).days if wet_days else None
    heat_days = sum(1 for d in win if d.tmax_c >= config.HEAT_C)
    humid_days = sum(1 for d in win if d.rh_mean >= config.HUMID_RH)
    max_day = max(d.rain_mm for d in win)

    sm = [d.soil_moisture for d in days if d.date <= end]
    last7 = statistics.mean(sm[-7:])
    win60 = statistics.mean(sm[-60:])
    anomaly = last7 - win60

    dry_spell = rain_10 < config.DRY_SPELL_MM
    heavy = max_day >= config.HEAVY_RAIN_MM
    heat = heat_days >= config.HEAT_DAYS
    rain_in_window = rain_14 >= config.RAIN_WINDOW_MM
    soil_low = anomaly <= config.SOIL_LOW

    # disease weather in the 10 days before the drop started
    onset = ctx.state.get("onset_date")
    humid_after_rain: bool | None = None
    pre = {}
    if onset:
        pw = [by_date[onset - timedelta(days=i)] for i in range(10, 0, -1) if (onset - timedelta(days=i)) in by_date]
        if pw:
            pre = {
                "rain_mm": round(sum(d.rain_mm for d in pw), 1),
                "humid_days": sum(1 for d in pw if d.rh_mean >= config.HUMID_RH),
            }
            humid_after_rain = pre["rain_mm"] >= config.HUMID_RAIN_MM and pre["humid_days"] >= config.HUMID_DAYS

    if since is None:
        spell = "No rain of 5 mm or more in the record."
    elif since >= 7:
        spell = f"No rain of {config.RAIN_RECENT_MM:.0f} mm or more for {since} days."
    else:
        spell = f"Last rain of {config.RAIN_RECENT_MM:.0f} mm or more was {since} days ago."
    parts = [spell, f"{rain_14:.0f} mm in the last {config.WINDOW_DAYS} days."]
    if heavy:
        parts.append(f"Heavy rain day of {max_day:.0f} mm in the window.")
    else:
        parts.append(f"No day above {config.HEAVY_RAIN_MM:.0f} mm.")
    parts.append("No heat-stress days." if not heat_days else f"{heat_days} day{'s' if heat_days != 1 else ''} at {config.HEAT_C:.0f}°C or hotter.")
    parts.append(
        "Soil moisture is " + ("well below" if soil_low else "close to") + f" its 60-day mean ({anomaly:+.3f} m³/m³).".replace("-", "−")
    )
    if humid_after_rain:
        parts.append(f"Before the drop began: {pre['rain_mm']:.0f} mm of rain and {pre['humid_days']} humid days.")
    finding = " ".join(parts)

    no_trigger = not (dry_spell or heavy or heat or bool(humid_after_rain))
    return ToolResult(
        tool="weather", title="Weather", finding=finding,
        facts={
            "dry_spell": dry_spell, "heavy_rain": heavy, "heat_stress": heat,
            "dry_or_hot": dry_spell or heat, "rain_in_window": rain_in_window,
            "soil_moisture_low": soil_low, "soil_moisture_normal": not soil_low,
            "humid_after_rain": humid_after_rain if onset else None,
            "no_weather_trigger": no_trigger,
        },
        vars={"days_since_rain": str(since if since is not None else ""), "rain_14d": f"{rain_14:.0f}"},
        data={
            "rain_14d_mm": round(rain_14, 1), "rain_10d_mm": round(rain_10, 1),
            "days_since_rain": since, "max_day_mm": max_day, "heat_days": heat_days,
            "humid_days": humid_days, "soil_moisture_anomaly": round(anomaly, 3),
            "pre_onset": pre or None,
        },
        as_of=end, quality="usable",
        source=data.weather_meta().get("source", "Weather"),
        visual={"type": "rain", "days": [
            {"date": d.date.isoformat(), "rain": d.rain_mm, "tmax": d.tmax_c} for d in win
        ]},
    )
