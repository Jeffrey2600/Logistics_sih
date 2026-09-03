"""Generalised cost of traversing a segment.

The optimiser does not minimise distance. It minimises a weighted blend of
money, time and expected disruption, which is what actually decides whether
ginger from Kohima reaches a Guwahati buyer while it is still saleable.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import (
    AIR_SPEED,
    DEFAULT_VALUE_OF_TIME,
    MODE_FIXED_HOURS,
    NORM_COST_PER_TONNE,
    NORM_TIME_HOURS,
    RAIL_SPEED,
    RATE_PER_TONNE_KM,
    ROAD_SPEED,
    TERRAIN_COST_FACTOR,
    TRANSFER_PENALTY,
    WATER_SPEED,
)
from .risk import RiskAssessment


@dataclass(frozen=True)
class LegCost:
    distance_km: float
    hours: float
    cost_per_tonne: float
    risk_probability: float
    expected_delay_hours: float
    generalised: float


def effective_speed(edge: dict) -> float:
    """Line-haul speed for a segment, after terrain and carriageway width."""
    mode = edge.get("mode", "road")
    terrain = edge.get("terrain", "plain")
    if mode == "road":
        lanes = int(edge.get("lanes", 2) or 2)
        table = ROAD_SPEED.get(terrain, ROAD_SPEED["plain"])
        # Fall back to the nearest defined lane class rather than KeyError on
        # an unexpected value from ingested OSM data.
        return table.get(lanes, table[min(table, key=lambda k: abs(k - lanes))])
    if mode == "rail":
        return RAIL_SPEED.get(terrain, RAIL_SPEED["plain"])
    if mode == "water":
        return WATER_SPEED
    if mode == "air":
        return AIR_SPEED
    return 30.0


def leg_cost(
    edge: dict,
    risk: RiskAssessment,
    weights: dict[str, float],
    value_of_time: float = DEFAULT_VALUE_OF_TIME,
) -> LegCost:
    mode = edge.get("mode", "road")
    terrain = edge.get("terrain", "plain")
    distance = float(edge["distance_km"])

    hours = distance / effective_speed(edge) + MODE_FIXED_HOURS.get(mode, 0.5)
    money = (
        distance
        * RATE_PER_TONNE_KM.get(mode, 3.5)
        * TERRAIN_COST_FACTOR.get(terrain, 1.0)
    )

    # Expected delay is priced twice on purpose: once as lost cargo value in the
    # money term, once as a standalone risk term the planner can weight up when
    # reliability matters more than the average outcome.
    delay = risk.expected_delay_hours
    money_with_delay = money + delay * value_of_time

    generalised = (
        weights["cost"] * (money_with_delay / NORM_COST_PER_TONNE)
        + weights["time"] * ((hours + delay) / NORM_TIME_HOURS)
        + weights["risk"] * risk.per_trip_probability
    )

    return LegCost(
        distance_km=distance,
        hours=hours,
        cost_per_tonne=money,
        risk_probability=risk.probability,
        expected_delay_hours=delay,
        generalised=generalised,
    )


def transfer_cost(
    from_mode: str, to_mode: str, weights: dict[str, float]
) -> LegCost:
    """Cost of changing mode at a node (breaking bulk, terminal dwell)."""
    money, hours = TRANSFER_PENALTY.get(frozenset((from_mode, to_mode)), (300.0, 6.0))
    generalised = (
        weights["cost"] * (money / NORM_COST_PER_TONNE)
        + weights["time"] * (hours / NORM_TIME_HOURS)
    )
    return LegCost(
        distance_km=0.0,
        hours=hours,
        cost_per_tonne=money,
        risk_probability=0.0,
        expected_delay_hours=0.0,
        generalised=generalised,
    )


def normalise_weights(raw: dict[str, float] | None, default: dict[str, float]) -> dict[str, float]:
    weights = dict(default) if not raw else {k: float(raw.get(k, default[k])) for k in default}
    total = sum(weights.values())
    if total <= 0:
        return dict(default)
    return {k: v / total for k, v in weights.items()}
