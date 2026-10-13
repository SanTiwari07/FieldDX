"""Settings and every tunable threshold in one place.

The thresholds are starting guesses (IMPLEMENTATION_PLAN section 5.2). They are meant to be
tuned against real exports and written into the spec; nothing else in the code hard-codes them.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.environ.get("FIELDDX_DATA", ROOT / "data"))
DB_PATH = Path(os.environ.get("FIELDDX_DB", ROOT / "backend" / "fielddx.db"))
FRONTEND_DIST = ROOT / "frontend" / "dist"

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
# "auto" uses Gemini when a key is set, "off" always uses the template narrative
LLM_MODE = os.environ.get("FIELDDX_LLM", "auto").lower()
LLM_TIMEOUT_S = float(os.environ.get("FIELDDX_LLM_TIMEOUT", "25"))
# Pause between investigation steps so a viewer can follow along (milliseconds)
DEMO_PACING_MS = int(os.environ.get("DEMO_PACING", "550"))


# ---- scene quality (share of pixels left after masking SCL 0, 1, 3, 8, 9, 10, 11)
QUALITY_USABLE = 0.80
QUALITY_PARTIAL = 0.50

# ---- NDVI change
BASELINE_FROM_DAYS = 45   # baseline window: 45 to 25 days before the alert
BASELINE_TO_DAYS = 25
SIGNIFICANT_DROP = -0.10  # a zone has dropped
ONSET_DROP = -0.05        # a zone has started to drop
ANOMALOUS_ZONE = -0.08    # a zone counts as anomalous in the pattern test
CONFIRM_SCENES = 2        # clear scenes needed to confirm a drop
RECOVERED_WITHIN = -0.05  # a zone has recovered if it is back above this
SUDDEN_DAYS = 10          # onset to significant drop within this many days = sudden

# ---- boundary check
EDGE_SURVIVES = -0.06       # shrunk-edge change must still be at least this bad
EDGE_VS_INTERIOR = 0.06     # and this much worse than the interior

# ---- neighbours
NEIGHBOUR_RADIUS_KM = 2.0
NEIGHBOUR_DROP = -0.08
NEIGHBOURS_SHARED = 0.50    # share of neighbours dropped: shared with the area
NEIGHBOURS_FINE = 0.25      # share below this: the problem is local
MIN_NEIGHBOURS = 2

# ---- spatial pattern
UNIFORM_SPREAD = 0.05
EDGE_GAP = 0.08

# ---- weather
DRY_SPELL_MM = 5.0          # less than this in 10 days
RAIN_WINDOW_MM = 15.0       # at least this in 14 days counts as rain in the window
HEAVY_RAIN_MM = 50.0        # a single day
HEAT_C = 38.0
HEAT_DAYS = 3
HUMID_RH = 85.0
HUMID_DAYS = 3
HUMID_RAIN_MM = 20.0        # rain in the 10 days before onset
SOIL_LOW = -0.04            # 7-day mean minus 60-day mean, m3/m3
WINDOW_DAYS = 14
RAIN_RECENT_MM = 5.0        # a day at or above this counts as rain for "days since rain"

# ---- crop calendar
EXPECTED_DROP = -0.08
MANAGEMENT_SLACK_DAYS = 5

# ---- engine
GATE_FIRE = 0.60            # stage 1 and 2 hypotheses fire at this score
FIELD_CASE_MIN = 0.45       # below this the answer is "Unexplained, visit"
CONF_HIGH = 0.65
CONF_HIGH_LEAD = 0.25
CONF_MEDIUM = 0.40
RULED_OUT_BELOW = 0.15
OUTCOME_WEIGHT = 0.5        # how far an officer finding moves a hypothesis

# ---- severity
SEVERITY_AREA = 0.08        # share of analysis pixels affected for a "high" case
