from datetime import date

from app import data
from app.tools import PIPELINE
from app.tools.common import build_ctx

AS_OF = date.fromisoformat(data.scenarios()["as_of"])


def run_all(field_id, alert):
    ctx = build_ctx(field_id, date.fromisoformat(alert), AS_OF)
    return ctx, {name: fn(ctx) for name, fn, _, _ in PIPELINE}


def test_hero_edge_drop_survives_the_buffer():
    ctx, out = run_all("F07", "2026-09-30")
    assert out["ndvi_series"].facts["drop_confirmed"] is True
    assert out["boundary_check"].facts["edge_survives_buffer"] is True
    assert out["spatial_pattern"].facts["pattern_edge"] is True
    assert out["neighbour_compare"].facts["neighbours_fine"] is True
    assert out["weather"].facts["dry_spell"] is True
    assert ctx.state["edge_name"] == "east"


def test_cloud_scene_is_not_a_number():
    ctx, out = run_all("F10", "2026-10-05")
    assert out["scene_quality"].data["alert_scene_class"] == "partial"
    assert out["ndvi_series"].facts["recovered_next"] is True
    assert out["ndvi_series"].facts["drop_confirmed"] is False
    # cloudy zone-scenes must give no delta at all, never zero
    scene = ctx.series.scene_at(date(2026, 7, 17))
    assert ctx.series.scene_class(scene) == "cloudy"
    assert all(ctx.series.delta(scene, z) is None for z in data.ANALYSIS)


def test_boundary_ring_removes_a_mixed_pixel_drop():
    _, out = run_all("F11", "2026-10-05")
    assert out["boundary_check"].facts["edge_vanishes_in_buffer"] is True
    assert out["boundary_check"].facts["edge_next_to_bare"] is True


def test_pruning_wave_is_uniform_and_shared():
    _, out = run_all("F02", "2026-10-05")
    assert out["spatial_pattern"].facts["pattern_uniform"] is True
    assert out["neighbour_compare"].facts["neighbours_dropped"] is True
    assert out["crop_calendar"].facts["in_window"] is True


def test_patch_that_spreads():
    _, out = run_all("F09", "2026-09-30")
    assert out["spatial_pattern"].data["pattern"] == "spreading"
    assert out["weather"].facts["humid_after_rain"] is True


def test_missing_pass_is_a_gap_not_a_zero():
    scene_dates = {s.date for s in data.scenes("F03")}
    assert date(2026, 9, 20) not in scene_dates
