"""Deterministic tools. Each takes a Ctx and returns a ToolResult that becomes one piece of evidence."""
from . import (boundary_check, crop_calendar, ndvi_series, neighbour_compare,
               scene_quality, spatial_pattern, weather)

# Fixed order: later tools read values the earlier ones leave in ctx.state
PIPELINE = [
    ("scene_quality", scene_quality.run, "Checking scene quality", "Scene quality"),
    ("ndvi_series", ndvi_series.run, "Measuring the NDVI change", "NDVI change"),
    ("boundary_check", boundary_check.run, "Testing the field boundary", "Boundary check"),
    ("neighbour_compare", neighbour_compare.run, "Comparing same-crop neighbours", "Neighbours"),
    ("spatial_pattern", spatial_pattern.run, "Reading the spatial pattern", "Spatial pattern"),
    ("weather", weather.run, "Pulling weather for the window", "Weather"),
    ("crop_calendar", crop_calendar.run, "Checking the crop calendar", "Crop calendar"),
]
