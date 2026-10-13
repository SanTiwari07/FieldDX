"""ndvi_series: size, speed and confirmation of the NDVI drop, per zone."""
from __future__ import annotations

import statistics
from datetime import timedelta

import numpy as np

from .. import config
from .. import data
from ..data import ZONE_CODES, ZONE_LABEL
from .common import Ctx, ToolResult, fmt_date, fmt_delta


def run(ctx: Ctx) -> ToolResult:
    s = ctx.series
    ANALYSIS = ctx.field.zones  # the eight zones, or the one zone of a small field
    ALL_ZONES = ANALYSIS + ctx.field.raw_zones
    whole_mode = ctx.field.mode == "whole"
    alert_scene = s.scene_at(ctx.alert)
    alert_deltas = s.deltas(alert_scene, ALL_ZONES)
    usable_since = s.usable(ctx.alert, ctx.as_of)
    latest = s.latest_usable(ctx.as_of)
    latest_deltas = s.deltas(latest, ALL_ZONES)

    alert_zones = [z for z, v in alert_deltas.items() if v is not None and v <= config.SIGNIFICANT_DROP]
    now_zones = [z for z, v in latest_deltas.items() if v is not None and v <= config.SIGNIFICANT_DROP]
    watch = alert_zones or now_zones

    def mean_over(scene, zones):
        vals = [s.delta(scene, z) for z in zones]
        vals = [v for v in vals if v is not None]
        return statistics.mean(vals) if vals else None

    confirming = [
        sc for sc in usable_since
        if watch and (mean_over(sc, watch) is not None) and mean_over(sc, watch) <= config.SIGNIFICANT_DROP
    ]
    confirmed = len(confirming) >= config.CONFIRM_SCENES

    later = [sc for sc in usable_since if sc.date > ctx.alert]
    recovered: bool | None = None
    if later and watch:
        m = mean_over(later[0], watch)
        recovered = m is not None and m > config.RECOVERED_WITHIN

    # primary zone: the worst zone that is part of the drop, analysis zones before raw ones
    ref_scene = latest if now_zones else alert_scene
    ref_deltas = s.deltas(ref_scene, ANALYSIS)
    ref_quality = s.scene_class(ref_scene)
    candidates = {z: v for z, v in ref_deltas.items() if v is not None}
    in_watch = {z: v for z, v in candidates.items() if z in watch}
    raw_watch = {z: s.delta(ref_scene, z) for z in watch if z not in ANALYSIS and s.delta(ref_scene, z) is not None}
    pool = in_watch or raw_watch or candidates
    primary = min(pool, key=pool.get) if pool else None
    primary_delta = pool.get(primary) if primary else None
    whole_field = whole_mode and primary is not None or (
        bool(candidates) and (max(candidates.values()) - min(candidates.values()) <= config.UNIFORM_SPREAD
                              and statistics.mean(candidates.values()) <= config.ANOMALOUS_ZONE))
    if whole_field:
        primary = "__field__"
        primary_delta = s.weighted_delta(ref_scene, ANALYSIS)
    primary_label = "whole field" if primary == "__field__" else (ZONE_LABEL[primary].lower() if primary else "")

    def primary_delta_at(sc):
        return s.weighted_delta(sc, ANALYSIS) if primary == "__field__" else s.delta(sc, primary)

    # onset and speed on the primary zone, read from clear scenes (and the alert scene itself)
    onset = sig = None
    if primary:
        lo = ctx.alert - timedelta(days=30)
        for sc in s.scenes:
            if sc.date < lo or sc.date > ctx.as_of:
                continue
            if s.scene_class(sc) != "usable" and sc.date != ctx.alert:
                continue
            d = primary_delta_at(sc)
            if d is None:
                continue
            if onset is None and d <= config.ONSET_DROP:
                onset = sc.date
            if sig is None and d <= config.SIGNIFICANT_DROP:
                sig = sc.date
        if sig and not onset:
            onset = sig
    days_to_drop = (sig - onset).days if sig and onset else None
    sudden = days_to_drop is not None and days_to_drop <= config.SUDDEN_DAYS
    gradual = days_to_drop is not None and days_to_drop > config.SUDDEN_DAYS

    significant = bool(watch)

    # open water reads as NDVI below zero: flooded or ponded ground, not a failing crop. Measured over
    # the zones that dropped, so a pond in one corner of an otherwise bare field is still seen.
    zone_ids = [ZONE_CODES.index(z) for z in watch if z in ANALYSIS] or [ZONE_CODES.index(z) for z in ANALYSIS]
    g = data.grid(ctx.field.area, ctx.field.id)
    az = g.az.ravel()[g.cells]

    def water_share(sc):
        if sc is None:
            return None
        ok = ~np.isnan(sc.px) & np.isin(az, zone_ids)
        return float((sc.px[ok] < 0.0).mean()) if ok.any() else None

    now_w = water_share(ref_scene) if ref_quality in ("usable", "partial") else None
    base_w = water_share(s.baseline_scenes[-1]) if s.baseline_scenes else None
    standing = bool(now_w is not None and now_w >= 0.40 and (base_w or 0.0) < 0.25)
    ctx.state.update(
        latest_scene=latest, ref_scene=latest, primary_zone=primary,
        onset_date=onset, alert_zones=alert_zones, confirmed=confirmed,
        primary_delta=primary_delta, ref_quality=ref_quality,
        headline_scene_date=(ref_scene.date if ref_scene else ctx.alert),
    )

    if not significant or primary is None:
        finding = f"No zone is more than {abs(config.SIGNIFICANT_DROP):.2f} NDVI below its baseline ({s.baseline_label()})."
    else:
        base = statistics.mean(s.baseline[z] for z in ANALYSIS) if primary == "__field__" else s.baseline.get(primary)
        head = (
            f"ΔNDVI {fmt_delta(primary_delta)} in the {primary_label} on "
            f"{fmt_date(ref_scene.date)} vs baseline {base:.2f} ({s.baseline_label()})."
        )
        if confirmed:
            n = len(confirming)
            tail = f" Confirmed by {n} clear scenes since {fmt_date(confirming[0].date)}."
        elif recovered:
            tail = (
                f" Seen on {fmt_date(ctx.alert)} only; by {fmt_date(later[0].date)} it is "
                f"back within {abs(config.RECOVERED_WITHIN):.2f} of baseline."
            )
        else:
            n = len(confirming)
            tail = f" {n} clear scene{'s' if n != 1 else ''} confirm{'s' if n == 1 else ''} it, {config.CONFIRM_SCENES} needed."
        speed = ""
        if days_to_drop is not None and confirmed:
            limit = f"−{abs(config.SIGNIFICANT_DROP):.2f}"
            if days_to_drop == 0:
                speed = f" Sudden: past {limit} on the first scene where it dipped."
            else:
                speed = f" {'Sudden' if sudden else 'Gradual'}: {days_to_drop} days from first dip to {limit}."
        finding = head + tail + speed
        if standing:
            finding += f" {now_w:.0%} of the pixels in the affected zones now read as open water (NDVI below zero)."

    # sparkline: affected zone against the interior mean, last 10 scenes
    spark = []
    for sc in s.scenes[-10:]:
        cls = s.scene_class(sc)
        spark.append({
            "date": sc.date.isoformat(),
            "quality": cls,
            "zone": primary_delta_at(sc) if primary else None,
            "interior": None if whole_mode else s.weighted_delta(sc, ["in_nw", "in_ne", "in_sw", "in_se"]),
        })

    per_zone = {z: v for z, v in (latest_deltas if now_zones else alert_deltas).items()}
    return ToolResult(
        tool="ndvi_series",
        title="NDVI change",
        finding=finding,
        facts={
            "drop_significant": significant,
            "drop_confirmed": confirmed if significant else None,
            "drop_single_date": (significant and not confirmed),
            "recovered_next": recovered,
            "drop_sudden": sudden if significant else None,
            "drop_gradual": gradual if significant else None,
            "standing_water": standing if significant else None,
        },
        vars={
            "zone": primary_label,
            "delta": fmt_delta(primary_delta) if primary_delta is not None else "",
            "n_confirming": str(len(confirming)),
            "water_pct": f"{now_w:.0%}" if now_w is not None else "",
        },
        data={
            "baseline": {"dates": [d.isoformat() for d in s.baseline_dates] if s.baseline_dates else None,
                         "values": {z: round(v, 3) for z, v in s.baseline.items() if z in ANALYSIS}},
            "deltas": per_zone,
            "primary_zone": primary,
            "confirming_scenes": [c.date.isoformat() for c in confirming],
            "onset": onset.isoformat() if onset else None,
            "days_to_drop": days_to_drop,
        },
        as_of=ref_scene.date if ref_scene else ctx.alert,
        quality=ref_quality if significant else "usable",
        visual={"type": "spark", "label": primary_label.capitalize(), "points": spark},
    )
