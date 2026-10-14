"""crop_calendar: does the drop fall in a local management window for this kind of canopy?

The crop itself is not known. FieldDx only knows whether the canopy looks perennial (it never went to
bare soil in the past year of NDVI) or seasonal. Management windows are therefore keyed to that class,
and they are placeholders until an agronomist confirms them, which the evidence says out loud.
"""
from __future__ import annotations

from datetime import date, timedelta

from .. import config, data
from .common import Ctx, ToolResult, fmt_date


def green_before(monthly: dict[str, float], day: date) -> tuple[float, str] | None:
    """The highest monthly NDVI in `day`'s month and the two before it, and that month: was there a
    green crop to harvest? The onset month counts because a slow drop can begin while the crop is still
    at its peak (onset Aug 24, peak in August)."""
    prev = [f"{day.year if day.month - k > 0 else day.year - 1}-{(day.month - k - 1) % 12 + 1:02d}" for k in (0, 1, 2)]
    vals = [(monthly[m], m) for m in prev if m in monthly]
    return max(vals) if vals else None


def year_before(day: date) -> str:
    """First month (YYYY-MM) of the twelve full months before `day`'s month."""
    y, m = (day.year - 1, day.month + 1) if day.month < 12 else (day.year, 1)
    return f"{y}-{m:02d}"


def active_window(area: str, klass: str, day: date) -> dict | None:
    slack = timedelta(days=config.MANAGEMENT_SLACK_DAYS)
    for w in data.calendar(area).get(klass, {}).get("windows", []):
        sm, sd = map(int, w["start"].split("-"))
        em, ed = map(int, w["end"].split("-"))
        start, end = date(day.year, sm, sd), date(day.year, em, ed)
        if start - slack <= day <= end + slack:
            return {**w, "start_date": start.isoformat(), "end_date": end.isoformat()}
    return None


def run(ctx: Ctx) -> ToolResult:
    f = ctx.field
    onset = ctx.state.get("onset_date") or ctx.alert
    window = active_window(f.area, f.klass, onset)
    monthly = f.monthly
    lows = [v for m, v in monthly.items() if year_before(onset) <= m < f"{onset:%Y-%m}"]
    low = min(lows) if lows else None

    if low is None:
        kind = "There is no year of NDVI history to tell perennial from seasonal."
    elif f.klass == "perennial":
        kind = f"The canopy looks perennial: it never fell below NDVI {low:.2f} in a monthly median over the past year."
    elif f.klass == "seasonal":
        kind = f"The canopy looks seasonal: it fell to NDVI {low:.2f} in a monthly median over the past year."
    else:
        kind = "The crop could not be identified from a year of NDVI."

    green = green_before(monthly, onset)
    if green and green[0] >= config.GREEN_CROP_NDVI:
        kind += f" It carried a green crop just before the drop (NDVI {green[0]:.2f} in {date.fromisoformat(green[1] + '-01'):%B})."

    if window:
        verified = window.get("verified", False)
        finding = (
            f"The drop began {fmt_date(onset)}, inside the {window['label'][:1].lower() + window['label'][1:]} window "
            f"({fmt_date(date.fromisoformat(window['start_date']))} to {fmt_date(date.fromisoformat(window['end_date']))}, "
            f"{'verified' if verified else 'assumed, not yet verified with an agronomist'}). {kind}"
        )
    else:
        finding = (
            f"No management window in the calendar for this kind of canopy around {fmt_date(onset)}. {kind} "
            "There is no crop-specific expected curve, so a normal crop cycle cannot be ruled in or out."
        )

    return ToolResult(
        tool="crop_calendar", title="Crop calendar", finding=finding,
        facts={"in_window": window is not None, "expected_drop": None,
               "green_before": (green[0] >= config.GREEN_CROP_NDVI) if green else None},
        vars={
            "window_label": window["label"] if window else "",
            "window_verified": "verified" if (window and window.get("verified")) else "assumed",
            "window_ask": window.get("ask", "") if window else "",
            "green_before": f"{green[0]:.2f}" if green else "",
        },
        data={"window": window, "onset": onset.isoformat(), "class": f.klass, "monthly": monthly},
        as_of=onset, quality="n/a",
        source=("Crop calendar (assumed window, unverified) and 12 months of Sentinel-2 NDVI"
                if window and not window.get("verified") else "Crop calendar and 12 months of Sentinel-2 NDVI"),
        visual={"type": "months", "rows": [{"month": m, "value": v} for m, v in monthly.items()]} if monthly else None,
    )
