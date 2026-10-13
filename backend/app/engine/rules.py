"""The hypothesis table (idea.md section 6) as data.

A rule is a list of weighted conditions over facts the tools produce. Supports sum to at most 1.
A condition whose fact is missing is "unknown": it counts neither way and is shown as unknown.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Cond:
    fact: str
    label: str            # what the line says when the condition holds; {vars} are filled in
    weight: float
    want: bool = True     # the fact must equal this for the condition to hold
    unknown: str = ""     # what is unknown and what would settle it


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    stage: int
    supports: tuple[Cond, ...]
    against: tuple[Cond, ...] = ()
    requires: tuple[str, ...] = ()   # facts that must be True before a gate may fire
    short: str = ""                  # used in reasons and one-line summaries


# Which tool produces which fact (used to attach evidence IDs to a line)
FACT_SOURCE = {
    "alert_scene_poor": "scene_quality", "clear_scenes_since": "scene_quality",
    "drop_significant": "ndvi_series", "drop_confirmed": "ndvi_series", "drop_single_date": "ndvi_series",
    "recovered_next": "ndvi_series", "drop_sudden": "ndvi_series", "drop_gradual": "ndvi_series",
    "raw_edge_drop": "boundary_check", "edge_survives_buffer": "boundary_check",
    "edge_vanishes_in_buffer": "boundary_check", "edge_next_to_bare": "boundary_check",
    "interior_fine": "boundary_check", "interior_dropped": "boundary_check",
    "neighbours_dropped": "neighbour_compare", "neighbours_fine": "neighbour_compare",
    "pattern_uniform": "spatial_pattern", "pattern_edge": "spatial_pattern",
    "pattern_spreading": "spatial_pattern", "pattern_patch_or_spreading": "spatial_pattern",
    "pattern_patch": "spatial_pattern", "pattern_localised": "spatial_pattern",
    "dry_spell": "weather", "heavy_rain": "weather", "heat_stress": "weather", "dry_or_hot": "weather",
    "rain_in_window": "weather", "soil_moisture_low": "weather", "soil_moisture_normal": "weather",
    "humid_after_rain": "weather", "no_weather_trigger": "weather",
    "in_window": "crop_calendar", "expected_drop": "crop_calendar",
    "ndre_low": "red_edge", "ndmi_high": "red_edge",
}

NDRE_UNKNOWN = "Red-edge (NDRE) needs 20 m bands and is not computed in this build; a leaf check would settle it."
NDMI_UNKNOWN = "Wetness (NDMI) is not computed in this build; a look for standing water would settle it."

RULES: tuple[Rule, ...] = (
    # ---- Stage 1: is the signal real?
    Rule(
        "H1", "Data artefact (cloud, shadow or haze)", 1,
        supports=(
            Cond("alert_scene_poor", "The alert scene is {alert_scene_class}, not clear", 0.35),
            Cond("drop_single_date", "The drop shows on a single date", 0.25),
            Cond("recovered_next", "Values recover on the next clear scene", 0.40),
        ),
        against=(Cond("drop_confirmed", "The drop persists across {n_confirming} clear scenes", 0.60),),
        requires=("recovered_next",),
        short="Cloud or haze on the scene",
    ),
    Rule(
        "H2", "Boundary-mixing artefact", 1,
        supports=(
            Cond("raw_edge_drop", "The drop sits on the {edge_name} edge of the unshrunk polygon", 0.20),
            Cond("edge_vanishes_in_buffer", "The drop disappears once the 10 m boundary ring is removed", 0.45),
            Cond("edge_next_to_bare", "That side borders a {edge_context}", 0.25),
            Cond("interior_fine", "The interior zones are stable", 0.10),
        ),
        against=(
            Cond("edge_survives_buffer", "The edge drop survives the 10 m buffer", 0.60),
            Cond("interior_dropped", "The interior zones dropped as well", 0.40),
        ),
        requires=("edge_vanishes_in_buffer",),
        short="Edge pixels mixing with the neighbour",
    ),
    # ---- Stage 2: expected, or shared with the area?
    Rule(
        "H3", "Management event", 2,
        supports=(
            Cond("in_window", "The drop began inside the {window_label} window ({window_verified})", 0.35),
            Cond("pattern_uniform", "The loss is uniform across the field", 0.25),
            Cond("drop_sudden", "The drop is sudden", 0.15),
            Cond("neighbours_dropped", "Same-crop neighbours dropped in the same window", 0.25),
        ),
        against=(
            Cond("in_window", "The drop is outside any known management window", 0.50, want=False),
            Cond("pattern_localised", "The loss is localised, not field-wide", 0.40),
        ),
        requires=("in_window",),
        short="Management event",
    ),
    Rule(
        "H4", "Normal crop cycle", 2,
        supports=(
            Cond("expected_drop", "The crop curve expects a fall at this stage", 0.60),
            Cond("pattern_uniform", "The loss is uniform across the field", 0.20),
            Cond("drop_gradual", "The decline is gradual", 0.20),
        ),
        against=(Cond("expected_drop", "The crop curve expects no fall at this stage", 0.50, want=False),),
        requires=("expected_drop",),
        short="Normal crop cycle",
    ),
    Rule(
        "H5", "Regional dry or hot spell", 2,
        supports=(
            Cond("neighbours_dropped", "Same-crop neighbours dropped too", 0.40),
            Cond("dry_or_hot", "The window is dry or hot", 0.35),
            Cond("soil_moisture_low", "Soil moisture is low across the area", 0.25),
        ),
        against=(
            Cond("neighbours_fine", "Neighbours are fine, so the cause is local", 0.50),
            Cond("in_window", "A management event already explains the drop", 0.40),
        ),
        requires=("neighbours_dropped",),
        short="Regional dry or hot spell",
    ),
    Rule(
        "H6", "Storm, hail or unseasonal rain damage", 2,
        supports=(
            Cond("heavy_rain", "A heavy rain day fell inside the window", 0.50),
            Cond("neighbours_dropped", "Neighbours were hit too", 0.25),
            Cond("drop_sudden", "The drop is sudden", 0.25),
        ),
        against=(Cond("heavy_rain", "No heavy rain day in the window", 0.60, want=False),),
        requires=("heavy_rain",),
        short="Storm or hail damage",
    ),
    # ---- Stage 3: field-specific differential
    Rule(
        "H7", "Irrigation failure", 3,
        supports=(
            Cond("pattern_edge", "The loss is concentrated on the {edge_name} edge", 0.35),
            Cond("edge_survives_buffer", "The edge drop survives the 10 m buffer, so it is not mixed pixels", 0.25),
            Cond("dry_spell", "It has been dry for {days_since_rain} days", 0.15),
            Cond("neighbours_fine", "Same-crop neighbours are fine", 0.15),
            Cond("soil_moisture_normal", "Area soil moisture is normal, so it is not regional drought", 0.10),
        ),
        against=(
            Cond("rain_in_window", "Rain fell in the window", 0.40),
            Cond("pattern_uniform", "The loss is uniform, not edge or row aligned", 0.30),
            Cond("neighbours_dropped", "Neighbours dropped too", 0.40),
        ),
        short="Irrigation failure",
    ),
    Rule(
        "H8", "Pest or disease spread", 3,
        supports=(
            Cond("pattern_spreading", "The affected patch grows across scenes", 0.40),
            Cond("pattern_patch_or_spreading", "The loss forms a patch rather than an edge or a uniform fall", 0.30),
            Cond("neighbours_fine", "Same-crop neighbours are fine", 0.15),
            Cond("humid_after_rain", "Rain and humid days came before the drop began", 0.15),
        ),
        against=(
            Cond("pattern_uniform", "The loss is uniform, not patchy", 0.40),
            Cond("neighbours_dropped", "Neighbours dropped too, which points to an area cause", 0.30),
        ),
        short="Pest or disease spread",
    ),
    Rule(
        "H9", "Nutrient deficiency", 3,
        supports=(
            Cond("drop_gradual", "The decline is slow and steady", 0.35),
            Cond("neighbours_fine", "Neighbours sown at the same time are fine", 0.15),
            Cond("ndre_low", "Red-edge index is low relative to NDVI", 0.30, unknown=NDRE_UNKNOWN),
            Cond("no_weather_trigger", "No weather trigger in the window", 0.20),
        ),
        against=(
            Cond("drop_sudden", "The drop is sudden, which is unusual for a nutrient shortfall", 0.30),
            Cond("in_window", "A management event falls in the window", 0.40),
        ),
        short="Nutrient deficiency",
    ),
    Rule(
        "H10", "Waterlogging", 3,
        supports=(
            Cond("heavy_rain", "A heavy rain day fell inside the window", 0.50),
            Cond("pattern_patch", "The loss sits in a patch, possibly low ground", 0.30),
            Cond("ndmi_high", "Wetness index is high in the affected zone", 0.20, unknown=NDMI_UNKNOWN),
        ),
        against=(Cond("heavy_rain", "No heavy rain day in the window", 0.70, want=False),),
        short="Waterlogging",
    ),
)

RULE_BY_ID = {r.id: r for r in RULES}
