"""Feature extraction shared by the risk API and the ML training script.

Kept in one module so training and inference can never drift apart.
"""
from __future__ import annotations

import math

from ..config import SEASON_RAIN_INDEX

TERRAIN_ORDINAL = {"plain": 0, "riverine": 1, "hilly": 2, "mountain": 3, "aerial": 0}
MODE_ORDINAL = {"road": 0, "rail": 1, "water": 2, "air": 3}

FEATURE_ORDER = [
    "terrain_ordinal",
    "mode_ordinal",
    "distance_km",
    "lanes",
    "monsoon_exposure",
    "landslide_density_per_100km",
    "landslide_history_saturated",
    "rain_index",
    "rain_x_terrain",
    "rain_x_history",
]


def edge_features(edge: dict, month: str) -> dict[str, float]:
    terrain = edge.get("terrain", "plain")
    length = max(float(edge.get("distance_km", 1.0)), 1.0)
    density = float(edge.get("landslide_events", 0)) * 100.0 / length
    history = 1.0 - math.exp(-density / 6.0)
    rain = SEASON_RAIN_INDEX.get(month.lower()[:3], 0.5)
    terrain_ord = TERRAIN_ORDINAL.get(terrain, 0)

    return {
        "terrain_ordinal": float(terrain_ord),
        "mode_ordinal": float(MODE_ORDINAL.get(edge.get("mode", "road"), 0)),
        "distance_km": length,
        "lanes": float(edge.get("lanes", 0) or 0),
        "monsoon_exposure": float(edge.get("monsoon_exposure", 0.3)),
        "landslide_density_per_100km": density,
        "landslide_history_saturated": history,
        "rain_index": rain,
        "rain_x_terrain": rain * terrain_ord,
        "rain_x_history": rain * history,
    }
