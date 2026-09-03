"""Central tuning constants for the NER logistics model.

Every number here is an assumption, not a measurement. They are kept in one
place, with a source note, so they can be defended in review and swapped for
surveyed values without touching the algorithms.
"""
from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SEED_DIR = BASE_DIR / "data" / "seed"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "ml" / "landslide"

MODES = ("road", "rail", "water", "air")

# Freight tariff, INR per tonne-km. Order-of-magnitude figures from published
# NITI Aayog / MoRTH modal-cost comparisons; road is the NER reality, the other
# modes are the policy alternative the platform is meant to argue for.
RATE_PER_TONNE_KM = {"road": 3.5, "rail": 1.6, "water": 1.1, "air": 22.0}

# Line-haul speeds (km/h) before terrain and lane adjustment.
ROAD_SPEED = {
    "plain": {4: 55.0, 2: 40.0, 1: 28.0},
    "hilly": {4: 38.0, 2: 30.0, 1: 20.0},
    "mountain": {4: 30.0, 2: 22.0, 1: 15.0},
}
RAIL_SPEED = {"plain": 35.0, "hilly": 22.0, "mountain": 18.0, "riverine": 30.0}
WATER_SPEED = 12.0
AIR_SPEED = 550.0

# Fixed per-leg overhead in hours (loading, terminal dwell, security).
MODE_FIXED_HOURS = {"road": 0.5, "rail": 4.0, "water": 6.0, "air": 3.0}

# Terrain multiplier on operating cost: gradient, fuel burn, tyre wear,
# lower payload utilisation on hill sections.
TERRAIN_COST_FACTOR = {
    "plain": 1.0,
    "hilly": 1.25,
    "mountain": 1.55,
    "riverine": 1.0,
    "aerial": 1.0,
}

# Transhipment penalty between modes at a common node: (INR/tonne, hours).
TRANSFER_PENALTY = {
    frozenset(("road", "rail")): (250.0, 6.0),
    frozenset(("road", "water")): (200.0, 8.0),
    frozenset(("road", "air")): (900.0, 4.0),
    frozenset(("rail", "water")): (220.0, 10.0),
    frozenset(("rail", "air")): (950.0, 6.0),
    frozenset(("water", "air")): (1000.0, 12.0),
}

# Seasonal rainfall intensity index used by the risk model, 0-1.
# NER monsoon runs roughly May-September with pre-monsoon showers from March.
SEASON_RAIN_INDEX = {
    "jan": 0.05, "feb": 0.08, "mar": 0.25, "apr": 0.45, "may": 0.70,
    "jun": 0.95, "jul": 1.00, "aug": 0.90, "sep": 0.70, "oct": 0.35,
    "nov": 0.12, "dec": 0.05,
}
DRY_SEASON = "jan"
PEAK_MONSOON = "jul"

# Expected hours of closure when a segment is actually disrupted, by terrain.
# Drives the expected-delay term, which is what makes a risky short route lose
# to a longer safe one during monsoon.
EXPECTED_CLOSURE_HOURS = {
    "plain": 6.0,
    "hilly": 18.0,
    "mountain": 36.0,
    "riverine": 12.0,
    "aerial": 4.0,
}

# Default weights for the generalised-cost objective. Exposed per-request.
DEFAULT_WEIGHTS = {"cost": 0.4, "time": 0.4, "risk": 0.2}

# Normalisation anchors so the three objective terms are comparable. The cost
# anchor is roughly a typical Guwahati-to-state-capital road haul; setting it
# too high flattens the gap between road and air and lets air freight win lanes
# no shipper of bulk agri produce would ever fly.
NORM_COST_PER_TONNE = 2500.0
NORM_TIME_HOURS = 60.0

# Value of time for cargo, INR per tonne per hour. Converts expected delay into
# money so perishables can be modelled by raising it.
DEFAULT_VALUE_OF_TIME = 25.0
