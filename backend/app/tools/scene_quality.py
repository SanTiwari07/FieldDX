"""scene_quality: was the alert scene fit to trust, and are there clear scenes since?"""
from __future__ import annotations

from datetime import timedelta

from .common import Ctx, ToolResult, fmt_date


def run(ctx: Ctx) -> ToolResult:
    s = ctx.series
    alert_scene = s.scene_at(ctx.alert)
    cls = s.scene_class(alert_scene)
    clear_since = [sc for sc in s.usable(ctx.alert, ctx.as_of)]
    next_clear = next((sc for sc in s.usable(ctx.alert + timedelta(days=1), ctx.as_of)), None)

    if alert_scene is None:
        finding = f"No Sentinel-2 pass over this field on {fmt_date(ctx.alert)}."
    else:
        lost = alert_scene.cloud_pct + alert_scene.shadow_pct + alert_scene.cirrus_pct
        clear_pct = round(s.scene_valid(alert_scene) * 100)
        if cls == "usable":
            finding = (
                f"Alert scene {fmt_date(ctx.alert)} is usable ({clear_pct}% clear pixels). "
                f"{len(clear_since)} clear scene{'s' if len(clear_since) != 1 else ''} from the alert to {fmt_date(ctx.as_of)}."
            )
        else:
            word = "partial" if cls == "partial" else "cloudy"
            tail = (
                f" Next clear scene: {fmt_date(next_clear.date)}."
                if next_clear else " No clear scene since."
            )
            finding = (
                f"Alert scene {fmt_date(ctx.alert)} is {word}: {lost}% of pixels lost to cloud, "
                f"shadow or cirrus ({clear_pct}% clear).{tail}"
            )

    # last eight passes on the five-day grid, gaps included
    strip = []
    d = ctx.as_of
    grid = [d - timedelta(days=5 * i) for i in range(7, -1, -1)]
    for gd in grid:
        sc = s.scene_at(gd)
        strip.append({"date": gd.isoformat(), "quality": s.scene_class(sc), "alert": gd == ctx.alert})

    ctx.state["alert_scene_class"] = cls
    ctx.state["clear_scenes_since_alert"] = len(clear_since)
    return ToolResult(
        tool="scene_quality",
        title="Scene quality",
        finding=finding,
        facts={
            "alert_scene_poor": cls in ("partial", "cloudy", "none"),
            "clear_scenes_since": len(clear_since) >= 1,
        },
        vars={"alert_date": fmt_date(ctx.alert), "alert_scene_class": cls},
        data={
            "alert_scene_class": cls,
            "cloud_pct": alert_scene.cloud_pct if alert_scene else None,
            "shadow_pct": alert_scene.shadow_pct if alert_scene else None,
            "cirrus_pct": alert_scene.cirrus_pct if alert_scene else None,
            "clear_scenes_since_alert": len(clear_since),
            "next_clear_scene": next_clear.date.isoformat() if next_clear else None,
        },
        as_of=ctx.alert,
        quality=cls,
        visual={"type": "strip", "items": strip},
    )
