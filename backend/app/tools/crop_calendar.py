"""crop_calendar: is the drop expected from the crop curve or a local management window?"""
from __future__ import annotations

from datetime import date, timedelta

from .. import config, data
from .common import Ctx, ToolResult, fmt_date


def expected_ndvi(crop: str, anchor: date, day: date) -> float:
    curve = data.calendar()[crop]["curve"]
    d = (day - anchor).days
    if d <= curve[0][0]:
        return curve[0][1]
    for (d0, v0), (d1, v1) in zip(curve, curve[1:]):
        if d <= d1:
            return v0 + (v1 - v0) * (d - d0) / (d1 - d0)
    return curve[-1][1]


def active_window(crop: str, day: date) -> dict | None:
    slack = timedelta(days=config.MANAGEMENT_SLACK_DAYS)
    for w in data.calendar()[crop]["windows"]:
        start, end = date.fromisoformat(w["start"]), date.fromisoformat(w["end"])
        if start - slack <= day <= end + slack:
            return w
    return None


def run(ctx: Ctx) -> ToolResult:
    f = ctx.field
    onset = ctx.state.get("onset_date") or ctx.alert
    window = active_window(f.crop, onset)
    base_day = ctx.series.baseline_dates[1] if ctx.series.baseline_dates else ctx.alert - timedelta(days=30)
    now_day = ctx.state["ref_scene"].date if ctx.state.get("ref_scene") else ctx.as_of
    exp_then, exp_now = expected_ndvi(f.crop, f.anchor_date, base_day), expected_ndvi(f.crop, f.anchor_date, now_day)
    expected_change = exp_now - exp_then
    expected_drop = expected_change <= config.EXPECTED_DROP

    anchor_note = f"{f.anchor_label} {fmt_date(f.anchor_date)}" + (", assumed" if f.anchor_assumed else "")
    if window:
        verified = window.get("verified", False)
        finding = (
            f"The drop began {fmt_date(onset)}, inside the {window['label'].lower()} window "
            f"({fmt_date(date.fromisoformat(window['start']))} to {fmt_date(date.fromisoformat(window['end']))}, "
            f"{'verified' if verified else 'assumed, not yet verified with an agronomist'})."
        )
    else:
        finding = f"No management window in the {f.crop} calendar around {fmt_date(onset)}. "
        finding += (
            f"The expected curve falls by {abs(expected_change):.2f} NDVI over this period ({anchor_note})."
            if expected_drop else
            f"The expected curve is {'flat' if abs(expected_change) < 0.03 else 'steady'} over this period ({anchor_note})."
        )

    curve_pts = []
    d = date(2026, 7, 7)
    while d <= date(2026, 10, 10):
        curve_pts.append({"date": d.isoformat(), "value": round(expected_ndvi(f.crop, f.anchor_date, d), 3)})
        d += timedelta(days=5)

    return ToolResult(
        tool="crop_calendar", title="Crop calendar", finding=finding,
        facts={
            "in_window": window is not None,
            "expected_drop": expected_drop,
        },
        vars={
            "window_label": window["label"] if window else "",
            "window_verified": "verified" if (window and window.get("verified")) else "assumed",
        },
        data={
            "window": window, "onset": onset.isoformat(),
            "expected_change": round(expected_change, 3), "anchor": f.anchor_date.isoformat(),
            "expected_curve": curve_pts,
        },
        as_of=onset, quality="n/a",
        source="Crop calendar (assumed windows, unverified)" if window and not window.get("verified") else "Crop calendar",
    )
