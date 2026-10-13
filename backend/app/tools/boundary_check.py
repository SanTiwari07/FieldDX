"""boundary_check: does an edge drop survive once the 10 m mixed-pixel ring is removed?"""
from __future__ import annotations

from .. import config
from ..data import SIDE_NAME
from .common import Ctx, ToolResult, fmt_date, fmt_delta, interior_mean


def run(ctx: Ctx) -> ToolResult:
    s = ctx.series
    ref = ctx.state.get("ref_scene")
    if ctx.field.mode == "whole":
        # no facts: whether the drop is mixed boundary pixels stays unknown, not "no"
        return ToolResult(
            tool="boundary_check", title="Boundary check", skipped=True,
            skip_reason=(f"At {ctx.field.area_ha} ha this field is too small to separate its edges from its interior "
                         "at 10 m, so mixing with the land around it cannot be ruled out."),
            as_of=ref.date if ref else ctx.alert, quality="n/a",
        )
    interior = interior_mean(s, ref)
    sides = []
    for side in "nesw":
        raw = s.delta(ref, f"raw_edge_{side}")
        if raw is not None and raw <= config.SIGNIFICANT_DROP:
            sides.append(side)

    quiet = {
        "raw_edge_drop": False, "edge_survives_buffer": False,
        "edge_vanishes_in_buffer": False, "edge_next_to_bare": False,
        "interior_fine": interior is not None and interior > -0.05,
        "interior_dropped": interior is not None and interior <= config.ANOMALOUS_ZONE,
    }
    if not sides or len(sides) == 4:
        reason = (
            "The drop is on every side, so it is not an edge effect."
            if len(sides) == 4 else "No edge drop on the unshrunk polygon, so there is nothing to test."
        )
        return ToolResult(
            tool="boundary_check", title="Boundary check", skipped=True, skip_reason=reason,
            facts=quiet, as_of=ref.date if ref else ctx.alert, quality="n/a",
        )

    rows, survives, vanishes = [], [], []
    for side in sides:
        raw = s.delta(ref, f"raw_edge_{side}")
        shrunk = s.delta(ref, f"edge_{side}")
        if shrunk is None or interior is None:
            continue
        sv = shrunk <= config.EDGE_SURVIVES and (interior - shrunk) >= config.EDGE_VS_INTERIOR
        survives.append(sv)
        vanishes.append(shrunk > config.EDGE_SURVIVES)
        rows.append((side, raw, shrunk))

    if not rows:
        return ToolResult(tool="boundary_check", title="Boundary check", skipped=True,
                          skip_reason="No clear pixels to test the buffer.", facts=quiet, quality="n/a")

    side, raw, shrunk = rows[0]
    name = SIDE_NAME[side]
    survives_any, vanishes_all = any(survives), all(vanishes)
    if survives_any:
        finding = (
            f"{name.capitalize()} edge: ΔNDVI {fmt_delta(raw)} on the unshrunk polygon and "
            f"{fmt_delta(shrunk)} after removing the 10 m boundary ring (interior {fmt_delta(interior)}). "
            "The edge drop survives, so it is not just mixed boundary pixels."
        )
    elif vanishes_all:
        finding = (
            f"{name.capitalize()} edge: ΔNDVI {fmt_delta(raw)} on the unshrunk polygon but only "
            f"{fmt_delta(shrunk)} inside the 10 m buffer, so the drop is mixed boundary pixels "
            "from whatever lies beyond the field edge."
        )
    else:
        finding = (
            f"{name.capitalize()} edge: ΔNDVI {fmt_delta(raw)} unshrunk, {fmt_delta(shrunk)} inside the buffer, "
            f"interior {fmt_delta(interior)}. The buffer does not separate the edge from the interior."
        )

    facts = {
        "raw_edge_drop": True,
        "edge_survives_buffer": survives_any,
        "edge_vanishes_in_buffer": vanishes_all,
        "edge_next_to_bare": False,
        "interior_fine": interior > -0.05,
        "interior_dropped": interior <= config.ANOMALOUS_ZONE,
    }
    ctx.state["boundary_side"] = side
    return ToolResult(
        tool="boundary_check", title="Boundary check", finding=finding, facts=facts,
        vars={"edge_name": name},
        data={"sides": sides, "raw": raw, "shrunk": shrunk, "interior": interior, "survives": survives_any},
        as_of=ref.date, quality="usable",
        visual={"type": "bars", "unit": "ΔNDVI", "rows": [
            {"label": "Edge, unshrunk", "value": raw},
            {"label": "Edge, 10 m buffer", "value": shrunk},
            {"label": "Interior", "value": interior},
        ]},
    )
