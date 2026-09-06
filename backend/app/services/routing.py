"""Route planning: optimal itinerary, alternatives, and disruption replanning."""
from __future__ import annotations

from itertools import islice

import networkx as nx

from ..config import DEFAULT_WEIGHTS, DRY_SEASON, MODES, PEAK_MONSOON
from ..core.costing import normalise_weights
from ..core.network import (
    Network, attach_terminals, cached_graph, detach_terminals,
)
from ..core.risk import RiskModel


class RoutingError(Exception):
    """Raised when a request cannot be satisfied by the network."""


def _summarise(graph: nx.DiGraph, path: list[tuple[str, str]], network: Network) -> dict:
    legs: list[dict] = []
    distance = hours = money = delay = objective = 0.0
    peak_risk = 0.0
    transhipments = 0

    for a, b in zip(path, path[1:]):
        data = graph.edges[a, b]
        if data["kind"] == "virtual":
            continue

        cost = data["cost"]
        objective += cost.generalised
        hours += cost.hours
        money += cost.cost_per_tonne
        delay += cost.expected_delay_hours
        distance += cost.distance_km

        if data["kind"] == "transfer":
            transhipments += 1
            legs.append(
                {
                    "type": "transfer",
                    "at": a[0],
                    "at_name": network.places[a[0]].name,
                    "from_mode": a[1],
                    "to_mode": b[1],
                    "hours": round(cost.hours, 2),
                    "cost_per_tonne": round(cost.cost_per_tonne, 2),
                }
            )
            continue

        risk = data["risk"]
        peak_risk = max(peak_risk, risk.probability)
        raw = data["raw"]
        origin_place, destination_place = network.places[a[0]], network.places[b[0]]
        legs.append(
            {
                "type": "travel",
                "edge_id": data["edge_id"],
                "from": a[0],
                "from_name": origin_place.name,
                # Coordinates travel with the leg: a route crosses road
                # junctions the client never lists, so it cannot look them up.
                "from_lat": origin_place.lat,
                "from_lon": origin_place.lon,
                "to": b[0],
                "to_name": destination_place.name,
                "to_lat": destination_place.lat,
                "to_lon": destination_place.lon,
                "mode": data["mode"],
                "route_ref": raw["route_ref"],
                "terrain": raw["terrain"],
                "distance_km": raw["distance_km"],
                "hours": round(cost.hours, 2),
                "cost_per_tonne": round(cost.cost_per_tonne, 2),
                "risk": risk.to_dict(),
            }
        )

    if not legs:
        raise RoutingError("path contained no physical movement")

    mode_chain: list[str] = []
    for leg in legs:
        if leg["type"] == "travel" and (not mode_chain or mode_chain[-1] != leg["mode"]):
            mode_chain.append(leg["mode"])

    return {
        "legs": legs,
        "summary": {
            "distance_km": round(distance, 1),
            "transit_hours": round(hours, 2),
            "expected_delay_hours": round(delay, 2),
            "total_hours": round(hours + delay, 2),
            "cost_per_tonne": round(money, 2),
            "peak_segment_risk": round(peak_risk, 4),
            # The value actually minimised, exposed so alternatives can be
            # ranked in the UI on the same basis the optimiser used.
            "objective_score": round(objective, 4),
            "transhipments": transhipments,
            "mode_chain": mode_chain,
        },
    }


def plan_route(
    network: Network,
    risk_model: RiskModel,
    origin: str,
    destination: str,
    month: str = "jul",
    weights: dict[str, float] | None = None,
    modes: list[str] | None = None,
    blocked_edge_ids: list[str] | None = None,
    value_of_time: float = 25.0,
    alternatives: int = 2,
) -> dict:
    if origin not in network.places:
        raise RoutingError(f"unknown origin: {origin}")
    if destination not in network.places:
        raise RoutingError(f"unknown destination: {destination}")
    if origin == destination:
        raise RoutingError("origin and destination are the same place")

    allowed = set(modes) if modes else set(MODES)
    unknown = allowed - set(MODES)
    if unknown:
        raise RoutingError(f"unknown mode(s): {', '.join(sorted(unknown))}")

    resolved = normalise_weights(weights, DEFAULT_WEIGHTS)
    graph = cached_graph(
        network,
        risk_model,
        month,
        resolved,
        allowed_modes=allowed,
        blocked_edge_ids=set(blocked_edge_ids or []),
        value_of_time=value_of_time,
    )
    source, sink = attach_terminals(graph, origin, destination)
    try:
        return _plan_on(graph, network, source, sink, origin, destination,
                        month, resolved, risk_model, alternatives, allowed,
                        blocked_edge_ids)
    finally:
        # The graph is shared via the cache; leaving terminals behind would
        # corrupt every later request that hits the same entry.
        detach_terminals(graph, source, sink)


def _plan_on(graph, network, source, sink, origin, destination, month, resolved,
             risk_model, alternatives, allowed, blocked_edge_ids):
    for place_id, terminal in ((origin, source), (destination, sink)):
        if graph.has_node(terminal):
            continue
        # Distinguish "you filtered out its only mode" from "your closures cut
        # it off", because the second one is the finding, not a user error.
        served = network.modes_at(place_id) & allowed
        name = network.places[place_id].name
        if served and blocked_edge_ids:
            raise RoutingError(
                f"{name} is isolated: every {'/'.join(sorted(served))} link "
                f"serving it is in the closure list"
            )
        raise RoutingError(f"{name} is not served by the selected modes")

    try:
        paths = list(
            islice(
                nx.shortest_simple_paths(graph, source, sink, weight="weight"),
                max(1, alternatives + 1),
            )
        )
    except nx.NetworkXNoPath as exc:
        raise RoutingError(
            "no route exists between these places under the selected modes"
        ) from exc

    itineraries = []
    seen: set[tuple] = set()
    for path in paths:
        itinerary = _summarise(graph, path, network)
        signature = tuple(
            (leg.get("edge_id"), leg["type"]) for leg in itinerary["legs"]
        )
        if signature in seen:
            continue
        seen.add(signature)
        itineraries.append(itinerary)

    return {
        "origin": network.places[origin].to_dict(),
        "destination": network.places[destination].to_dict(),
        "month": month,
        "weights": {k: round(v, 3) for k, v in resolved.items()},
        "risk_model": risk_model.name,
        "recommended": itineraries[0],
        "alternatives": itineraries[1:],
    }


def seasonal_comparison(
    network: Network,
    risk_model: RiskModel,
    origin: str,
    destination: str,
    **kwargs,
) -> dict:
    """Same lane, dry season versus peak monsoon.

    This is the number that makes the NER logistics problem legible: the same
    consignment on the same lane costs materially more, and arrives materially
    later, for four months of the year.
    """
    dry = plan_route(network, risk_model, origin, destination, month=DRY_SEASON, **kwargs)
    wet = plan_route(network, risk_model, origin, destination, month=PEAK_MONSOON, **kwargs)

    d, w = dry["recommended"]["summary"], wet["recommended"]["summary"]
    return {
        "origin": dry["origin"],
        "destination": dry["destination"],
        "dry_season": {"month": DRY_SEASON, **dry["recommended"]["summary"], "legs": dry["recommended"]["legs"]},
        "monsoon": {"month": PEAK_MONSOON, **wet["recommended"]["summary"], "legs": wet["recommended"]["legs"]},
        "delta": {
            "hours": round(w["total_hours"] - d["total_hours"], 2),
            "cost_per_tonne": round(w["cost_per_tonne"] - d["cost_per_tonne"], 2),
            "reroutes": d["mode_chain"] != w["mode_chain"],
        },
    }
