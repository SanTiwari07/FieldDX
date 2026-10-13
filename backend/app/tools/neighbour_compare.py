"""neighbour_compare: did similar fields nearby drop in the same window?"""
from __future__ import annotations

from .. import config, data
from .common import Ctx, Series, ToolResult, fmt_date


def run(ctx: Ctx) -> ToolResult:
    rows = []
    for nb in ctx.neighbours:
        ser = Series(nb, ctx.alert)
        sc = ser.latest_usable(ctx.as_of)
        d = ser.weighted_delta(sc, nb.zones)
        if d is None:
            continue
        rows.append({
            "id": nb.id, "name": nb.name, "delta": d,
            "km": round(data.distance_km(ctx.field, nb), 2),
            "dropped": d <= config.NEIGHBOUR_DROP,
        })

    n = len(rows)
    dropped = sum(1 for r in rows if r["dropped"])
    share = dropped / n if n else None
    enough = n >= config.MIN_NEIGHBOURS
    shared = (share >= config.NEIGHBOURS_SHARED) if enough else None
    fine = (share < config.NEIGHBOURS_FINE) if enough else None

    crop = {"perennial": "perennial-canopy", "seasonal": "seasonal-crop"}.get(ctx.field.klass, "nearby")
    if not enough:
        finding = f"Only {n} {crop} plot{'s' if n != 1 else ''} within {config.NEIGHBOUR_RADIUS_KM:.0f} km; too few to compare."
    elif shared:
        finding = (
            f"{dropped} of {n} {crop} plots within {config.NEIGHBOUR_RADIUS_KM:.0f} km dropped by "
            f"{abs(config.NEIGHBOUR_DROP):.2f} NDVI or more ({share:.0%}). The change is shared with the area."
        )
    elif fine:
        finding = (
            f"{dropped} of {n} {crop} plots within {config.NEIGHBOUR_RADIUS_KM:.0f} km dropped "
            f"({share:.0%}). Neighbours are fine, so this looks local to the field."
        )
    else:
        finding = (
            f"{dropped} of {n} {crop} plots within {config.NEIGHBOUR_RADIUS_KM:.0f} km dropped "
            f"({share:.0%}). Not clearly shared and not clearly local."
        )

    latest = ctx.state.get("ref_scene")
    return ToolResult(
        tool="neighbour_compare", title="Neighbours", finding=finding,
        facts={"neighbours_dropped": shared, "neighbours_fine": fine},
        vars={"n_dropped": str(dropped), "n_neighbours": str(n), "crop": crop},
        data={"neighbours": rows, "share_dropped": share, "radius_km": config.NEIGHBOUR_RADIUS_KM},
        as_of=latest.date if latest else ctx.as_of,
        quality="usable" if enough else "partial",
        visual={"type": "dots", "rows": rows},
    )
