"""spatial_pattern: uniform, edge-concentrated, single patch, or spreading across dates."""
from __future__ import annotations

import statistics
from datetime import timedelta

from .. import config
from ..data import ANALYSIS, EDGES, INTERIOR, SIDE_NAME, ZONE_LABEL
from .common import Ctx, ToolResult, adjacent_edges, fmt_delta, interior_mean

PATTERN_WORDS = {
    "uniform": "uniform across the field",
    "edge": "concentrated on the edge",
    "patch": "a single patch",
    "spreading": "a patch that is spreading",
    "mixed": "scattered, with no clear shape",
}


def _anomalous(series, scene) -> list[str]:
    out = []
    for z in ANALYSIS:
        d = series.delta(scene, z)
        if d is not None and d <= config.ANOMALOUS_ZONE:
            out.append(z)
    return out


def run(ctx: Ctx) -> ToolResult:
    s = ctx.series
    ref = ctx.state.get("ref_scene")
    quiet = {
        "pattern_uniform": False, "pattern_edge": False, "pattern_patch_or_spreading": False,
        "pattern_spreading": False, "pattern_localised": False,
    }
    if ref is None:
        return ToolResult(tool="spatial_pattern", title="Spatial pattern", skipped=True,
                          skip_reason="No clear scene to read a pattern from.", facts=quiet, quality="none")

    deltas = s.deltas(ref, ANALYSIS)
    vals = {z: v for z, v in deltas.items() if v is not None}
    anomalous = _anomalous(s, ref)
    if not anomalous:
        return ToolResult(
            tool="spatial_pattern", title="Spatial pattern", skipped=True,
            skip_reason=f"No zone is below the anomaly threshold on the latest clear scene.",
            facts=quiet, as_of=ref.date, quality="usable",
        )

    interior = interior_mean(s, ref) or 0.0
    spread = max(vals.values()) - min(vals.values())
    mean_all = statistics.mean(vals.values())
    # growth in the number of anomalous zones across clear scenes since a week before the alert
    counts = []
    for sc in s.usable(None, ctx.as_of):
        if sc.date >= ctx.alert - timedelta(days=10):
            counts.append((sc.date, len(_anomalous(s, sc))))
    growing = len(counts) >= 3 and all(
        counts[i][1] < counts[i + 1][1] for i in range(len(counts) - 3, len(counts) - 1)
    ) and counts[-3][1] >= 1

    edge_hits = [z for z in anomalous if z in EDGES]
    edge_like = (
        len(edge_hits) == len(anomalous) and 1 <= len(edge_hits) <= 2
        and (len(edge_hits) == 1 or adjacent_edges(*edge_hits))
        and all(interior - vals[z] >= config.EDGE_GAP for z in edge_hits)
    )
    if spread <= config.UNIFORM_SPREAD and mean_all <= config.ANOMALOUS_ZONE:
        pattern = "uniform"
    elif growing:
        pattern = "spreading"
    elif edge_like:
        pattern = "edge"
    elif len(anomalous) == 1 and anomalous[0] in INTERIOR:
        pattern = "patch"
    else:
        pattern = "mixed"

    zones_px = {z: s.field.zone_pixels[z] for z in ANALYSIS}
    affected_px = sum(zones_px[z] for z in anomalous)
    total_px = sum(zones_px.values())
    names = [ZONE_LABEL[z].lower() for z in anomalous]
    worst = min(anomalous, key=lambda z: vals[z])
    edge_name = SIDE_NAME[worst.split("_")[1]] if worst in EDGES else ""

    if pattern == "uniform":
        finding = (
            f"The loss is uniform: all zones within {spread:.2f} NDVI of each other, "
            f"mean {fmt_delta(mean_all)}."
        )
    elif pattern == "edge":
        finding = (
            f"Loss is concentrated on the {' and '.join(names)}: {affected_px} of {total_px} analysis pixels, "
            f"ΔNDVI {fmt_delta(vals[worst])} against {fmt_delta(interior)} in the interior."
        )
    elif pattern == "spreading":
        trail = " → ".join(str(c) for _, c in counts[-3:])
        finding = (
            f"A patch that grows across scenes: anomalous zones {trail}. Now {', '.join(names)} "
            f"({affected_px} of {total_px} pixels)."
        )
    elif pattern == "patch":
        finding = f"A single patch in the {names[0]}: {affected_px} of {total_px} analysis pixels, ΔNDVI {fmt_delta(vals[worst])}."
    else:
        finding = (
            f"Scattered loss with no clear shape: {', '.join(names)} ({affected_px} of {total_px} pixels), "
            "not edge-aligned, not uniform and not growing."
        )

    facts = {
        "pattern_uniform": pattern == "uniform",
        "pattern_edge": pattern == "edge",
        "pattern_spreading": pattern == "spreading",
        "pattern_patch_or_spreading": pattern in ("patch", "spreading"),
        "pattern_localised": pattern in ("edge", "patch", "spreading", "mixed"),
        "pattern_patch": pattern == "patch",
    }
    ctx.state.update(pattern=pattern, affected_zones=anomalous, edge_name=edge_name,
                     has_edge_zone=bool(edge_hits))
    return ToolResult(
        tool="spatial_pattern", title="Spatial pattern", finding=finding, facts=facts,
        vars={"edge_name": edge_name, "pattern": PATTERN_WORDS[pattern], "zones": ", ".join(names)},
        data={"pattern": pattern, "affected_zones": anomalous, "affected_pixels": affected_px,
              "total_pixels": total_px, "zone_counts": [[d.isoformat(), c] for d, c in counts]},
        as_of=ref.date, quality="usable",
        visual={"type": "zones", "rows": [
            {"zone": z, "label": ZONE_LABEL[z], "value": vals.get(z), "anomalous": z in anomalous}
            for z in ANALYSIS
        ]},
    )
