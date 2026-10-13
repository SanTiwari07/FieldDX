"""Shared context and helpers for the deterministic tools."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from .. import config, data
from ..data import ANALYSIS, EDGES, INTERIOR, FieldRec, Scene


def quality_of(valid: float) -> str:
    if valid >= config.QUALITY_USABLE:
        return "usable"
    if valid >= config.QUALITY_PARTIAL:
        return "partial"
    return "cloudy"


def fmt_date(d: date) -> str:
    return f"{d:%b} {d.day}"


def fmt_delta(v: float) -> str:
    return f"{v:+.2f}".replace("-", "−")


class Series:
    """One field's scenes with the baseline and the per-zone change measured against it."""

    def __init__(self, field_rec: FieldRec, alert: date):
        self.field = field_rec
        self.scenes = list(data.scenes(field_rec.area, field_rec.id))
        self.alert = alert
        self.baseline_scenes: list[Scene] = []
        self.baseline, self.baseline_dates = self._baseline()

    # -- scene helpers
    def scene_at(self, d: date) -> Scene | None:
        return next((s for s in self.scenes if s.date == d), None)

    def scene_class(self, scene: Scene | None) -> str:
        if scene is None:
            return "none"
        return quality_of(self.scene_valid(scene))

    def scene_valid(self, scene: Scene) -> float:
        zones = self.field.zones
        total = sum(scene.zones[z].pixels for z in zones)
        return sum(scene.zones[z].pixels * scene.zones[z].valid for z in zones) / total if total else 0.0

    def usable(self, start: date | None = None, end: date | None = None) -> list[Scene]:
        return [
            s for s in self.scenes
            if self.scene_class(s) == "usable"
            and (start is None or s.date >= start) and (end is None or s.date <= end)
        ]

    # -- baseline
    def _baseline(self) -> tuple[dict[str, float], tuple[date, date] | None]:
        """Median of clear passes 25 to 45 days before the alert; widened to 20 to 75 days if too few."""
        picks: list[Scene] = []
        for near, far in ((config.BASELINE_TO_DAYS, config.BASELINE_FROM_DAYS), (20, 75)):
            lo, hi = self.alert - timedelta(days=far), self.alert - timedelta(days=near)
            picks = self.usable(lo, hi)
            if len(picks) >= 2:
                break
        if len(picks) < 2:
            return {}, None
        self.baseline_scenes = picks
        base = {}
        for z in data.ALL_ZONES + [data.WHOLE]:
            vals = [s.zones[z].ndvi for s in picks if s.zones[z].ndvi is not None]
            if vals:
                base[z] = statistics.median(vals)
        return base, (picks[0].date, picks[-1].date)

    def baseline_label(self) -> str:
        if not self.baseline_dates:
            return "no baseline"
        a, b = self.baseline_dates
        return f"{fmt_date(a)} to {fmt_date(b)}" if a != b else fmt_date(a)

    # -- change vs baseline
    def delta(self, scene: Scene | None, zone: str) -> float | None:
        """Change in NDVI against the zone's own baseline. None when no honest number exists."""
        if scene is None or zone not in self.baseline:
            return None
        obs = scene.zones[zone]
        if obs.ndvi is None or quality_of(obs.valid) in ("cloudy", "none"):
            return None
        return round(obs.ndvi - self.baseline[zone], 3)

    def weighted_delta(self, scene: Scene | None, zones: list[str]) -> float | None:
        if scene is None:
            return None
        num = den = 0.0
        for z in zones:
            d = self.delta(scene, z)
            if d is None:
                continue
            w = scene.zones[z].pixels
            num += d * w
            den += w
        return round(num / den, 3) if den else None

    def deltas(self, scene: Scene | None, zones: list[str]) -> dict[str, float | None]:
        return {z: self.delta(scene, z) for z in zones}

    def latest_usable(self, as_of: date) -> Scene | None:
        picks = self.usable(None, as_of)
        return picks[-1] if picks else None


@dataclass
class ToolResult:
    tool: str
    title: str
    finding: str = ""
    facts: dict[str, bool | None] = field(default_factory=dict)
    vars: dict[str, str] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    as_of: date | None = None
    quality: str = "usable"
    source: str = "Sentinel-2 L2A, Cloud Score+ masked (via Earth Engine)"
    visual: dict[str, Any] | None = None
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class Ctx:
    field: FieldRec
    alert: date
    as_of: date
    series: Series
    neighbours: list[FieldRec]
    state: dict[str, Any] = field(default_factory=dict)  # values handed from one tool to the next


def build_ctx(area: str, field_id: str, alert: date, as_of: date) -> Ctx:
    f = data.fields(area)[field_id]
    others = [
        o for o in data.fields(area).values()
        if o.id != f.id and f.klass != "unknown" and o.klass == f.klass
        and data.distance_km(f, o) <= config.NEIGHBOUR_RADIUS_KM
    ]
    return Ctx(field=f, alert=alert, as_of=as_of, series=Series(f, alert), neighbours=others)


def interior_mean(series: Series, scene: Scene | None) -> float | None:
    return series.weighted_delta(scene, INTERIOR)


def adjacent_edges(a: str, b: str) -> bool:
    order = EDGES
    i, j = order.index(a), order.index(b)
    return (i - j) % 4 in (1, 3)
