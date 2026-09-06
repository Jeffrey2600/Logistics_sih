"""Flood disruption risk.

The Brahmaputra floods every monsoon. It displaces lakhs of people, closes
NH-15 and the Rangiya-Murkongselek rail line for weeks at a time, and is the
single largest recurring disruption to freight in Assam. A logistics model for
the NER that scores only landslides is describing the hills and ignoring the
valley.

Flooding and landslides are near-opposites in where they strike. A landslide
needs a steep slope; a flood needs a flat one near a river. Modelling them as
one number would let a hill road's landslide risk stand in for a valley road's
flood risk, and both would be wrong. They are therefore separate hazards,
combined only at the end.

Inputs, all free and already in the pipeline:

* **Elevation** from the Copernicus DEM via Open-Meteo. The dominant signal:
  the valley floor sits at 40-90 m, the hills either side above 500 m.
* **Terrain** from road sinuosity, as elsewhere - floodplains are flat.
* **Rainfall** from the NASA POWER climatology already used for landslides.

What it does not have, and would need to be authoritative: observed flood
extent (Sentinel-1 or the Global Flood Database), river gauge levels, and
embankment condition. Assam's flooding is heavily shaped by embankments, and a
breach is a local event no terrain model can anticipate.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass

from ..config import PROCESSED_DIR

ELEVATION_CSV = PROCESSED_DIR / "node_elevation.csv"

# Below this the ground is floodplain; above it, flooding is a local matter of
# drainage rather than a river leaving its channel. The Brahmaputra valley
# floor runs about 40-90 m from Dibrugarh down to Dhubri.
FLOODPLAIN_M = 90.0
# Above this, river flooding is not a plausible mechanism at all.
UPLAND_M = 400.0

# Not every floodplain road floods every monsoon. Assam's flooding is severe but
# patchy: it follows particular reaches, embankment breaches and tributary
# confluences, not the whole valley at once. Without observed flood extent this
# constant is the honest stand-in for "what share of floodplain road is actually
# cut in a typical monsoon", and it is the single number here most in need of
# ground truth - a Sentinel-1 flood-extent join would replace it outright.
FLOODPLAIN_AFFECTED_SHARE = 0.40

# Flat ground drains slowly and holds water; a hill road sheds it.
TERRAIN_FLATNESS = {
    "plain": 1.0,
    "riverine": 1.0,
    "hilly": 0.25,
    "mountain": 0.05,
    "aerial": 0.0,
}

# Flooding lags the rain that causes it: the Brahmaputra rises with upstream
# catchment runoff and Himalayan snowmelt, so June-August are worse than the
# rainfall figures alone suggest and the recession runs into October.
FLOOD_SEASON = {
    "jan": 0.02, "feb": 0.02, "mar": 0.05, "apr": 0.15, "may": 0.45,
    "jun": 0.90, "jul": 1.00, "aug": 0.95, "sep": 0.70, "oct": 0.30,
    "nov": 0.08, "dec": 0.03,
}

# A flooded road is impassable for longer than a cleared landslip: water has to
# drain and the surface is often scoured underneath.
FLOOD_CLOSURE_HOURS = 60.0

# As with landslides, the chance a given consignment meets the closure is much
# lower than the chance the segment floods at some point in the month.
TRIP_EXPOSURE = 0.20

# Modes differ: a barge is indifferent to high water until it is extreme, and
# an aircraft entirely so.
MODE_SENSITIVITY = {"road": 1.0, "rail": 0.85, "water": 0.15, "air": 0.05}


@dataclass(frozen=True)
class FloodAssessment:
    probability: float
    per_trip_probability: float
    expected_delay_hours: float
    elevation_m: float | None
    drivers: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "probability": round(self.probability, 4),
            "per_trip_probability": round(self.per_trip_probability, 4),
            "expected_delay_hours": round(self.expected_delay_hours, 2),
            "elevation_m": self.elevation_m,
            "drivers": {k: round(v, 4) for k, v in self.drivers.items()},
        }


_elevation: dict[str, float] | None = None


def node_elevation() -> dict[str, float]:
    """{node_id: metres}, empty when the dataset has not been built."""
    global _elevation
    if _elevation is None:
        if not ELEVATION_CSV.exists():
            _elevation = {}
        else:
            try:
                with ELEVATION_CSV.open(encoding="utf-8") as fh:
                    _elevation = {
                        row["node_id"]: float(row["elevation_m"])
                        for row in csv.DictReader(fh)
                    }
            except (KeyError, ValueError):
                _elevation = {}
    return _elevation


def clear_cache() -> None:
    global _elevation
    _elevation = None


def segment_elevation(edge: dict) -> float | None:
    """Lower of the two ends: a road floods at its lowest point."""
    table = node_elevation()
    heights = [table[end] for end in (edge.get("u"), edge.get("v")) if end in table]
    return min(heights) if heights else None


def lowland_score(elevation_m: float | None) -> float:
    """1 on the floodplain, tapering to 0 in the uplands."""
    if elevation_m is None:
        return 0.0
    if elevation_m <= FLOODPLAIN_M:
        return 1.0
    if elevation_m >= UPLAND_M:
        return 0.0
    return (UPLAND_M - elevation_m) / (UPLAND_M - FLOODPLAIN_M)


def assess(edge: dict, month: str, rain_index: float) -> FloodAssessment:
    """Flood risk for one segment in one month."""
    elevation = segment_elevation(edge)
    lowland = lowland_score(elevation)
    flatness = TERRAIN_FLATNESS.get(edge.get("terrain", "plain"), 0.5)

    # Both conditions are necessary, so they multiply rather than add: a flat
    # plateau at 800 m does not flood, and neither does a gorge at 60 m.
    susceptibility = lowland * (0.35 + 0.65 * flatness) * FLOODPLAIN_AFFECTED_SHARE

    season = FLOOD_SEASON.get(month.lower()[:3], 0.2)
    # Local rainfall matters, but the river carries water from far upstream, so
    # the season sets the floor and rain modulates it rather than gating it.
    trigger = season * (0.6 + 0.4 * min(rain_index, 1.0))

    probability = max(0.0, min(1.0, susceptibility * trigger))
    probability *= MODE_SENSITIVITY.get(edge.get("mode", "road"), 1.0)

    per_trip = probability * TRIP_EXPOSURE
    return FloodAssessment(
        probability=probability,
        per_trip_probability=per_trip,
        expected_delay_hours=per_trip * FLOOD_CLOSURE_HOURS,
        elevation_m=elevation,
        drivers={
            "lowland": lowland,
            "flatness": flatness,
            "season": season,
            "rain_index": rain_index,
        },
    )


def data_available() -> bool:
    return bool(node_elevation())


def coverage(network_node_ids) -> float:
    """Share of the network that has an elevation, 0-1.

    Partial coverage is worse than none: a segment with no elevation scores
    zero flood risk, which on a map is indistinguishable from a road that is
    genuinely safe. A half-built dataset would paint the unmeasured half of the
    valley green. Callers report this so the map can say "not measured" instead.
    """
    table = node_elevation()
    ids = set(network_node_ids)
    if not ids:
        return 0.0
    return len(ids & set(table)) / len(ids)
