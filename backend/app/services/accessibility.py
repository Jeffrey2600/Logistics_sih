"""Accessibility intelligence.

Routing answers "how do I move this consignment". Accessibility answers the
question MDoNER actually invests against: which places are structurally cut off,
from what, and how much worse does the monsoon make it. Every score here is a
door-to-facility travel time, not a straight-line distance, because in the NER
the two differ by a factor of three.
"""
from __future__ import annotations

import math

import networkx as nx

from ..config import DRY_SEASON, MODES, PEAK_MONSOON
from ..core.network import Network, build_graph
from ..core.risk import RiskModel

# Half-life style decay constants, in hours. A facility 3h away scores well for
# a market run; the same 3h to a gateway port is excellent.
DECAY_HOURS = {"market": 4.0, "coldstore": 8.0, "gateway": 18.0}

# Gateways: where NER freight actually enters and leaves the region.
GATEWAY_IDS = ("GAU", "SLG")

COMPONENT_WEIGHTS = {
    "market": 0.30,
    "coldstore": 0.25,
    "gateway": 0.25,
    "reliability": 0.20,
}


def _hours_weight(_u, _v, data) -> float:
    """Edge weight in expected hours, including probable disruption delay."""
    cost = data.get("cost")
    if cost is None:
        return 0.0
    return cost.hours + cost.expected_delay_hours


def _travel_hours_to_targets(
    graph: nx.DiGraph, target_ids: set[str]
) -> dict[str, float]:
    """Shortest expected hours from every place to its nearest target place.

    Runs one multi-source Dijkstra from the targets. The physical network is
    symmetric, so distance-to-nearest-target equals distance-from-nearest-target.
    """
    sources = [n for n in graph.nodes if n[0] in target_ids]
    if not sources:
        return {}

    lengths = nx.multi_source_dijkstra_path_length(graph, sources, weight=_hours_weight)

    best: dict[str, float] = {}
    for (place_id, _mode), hours in lengths.items():
        if place_id not in best or hours < best[place_id]:
            best[place_id] = hours
    return best


def _decay_score(hours: float | None, tau: float) -> float:
    """Map travel time to 0-100. Unreachable scores zero, not an error."""
    if hours is None or math.isinf(hours):
        return 0.0
    return 100.0 * math.exp(-hours / tau)


def _graph_for(network: Network, risk_model: RiskModel, month: str) -> nx.DiGraph:
    # Accessibility is a time question, so the graph is built time-weighted.
    return build_graph(
        network,
        risk_model,
        month,
        weights={"cost": 0.0, "time": 1.0, "risk": 0.0},
        allowed_modes=set(MODES),
    )


def accessibility_index(
    network: Network,
    risk_model: RiskModel,
    month: str = PEAK_MONSOON,
    extra_markets: set[str] | None = None,
    extra_coldstores: set[str] | None = None,
) -> dict:
    """Score every place, in the given month, against markets, cold chain and gateways.

    `extra_*` inject proposed facilities so a planner can ask what a new cold
    store would actually buy, before it is built.
    """
    markets = {p.id for p in network.places.values() if p.has_market} | (extra_markets or set())
    coldstores = {p.id for p in network.places.values() if p.has_coldstore} | (extra_coldstores or set())
    gateways = set(GATEWAY_IDS)

    graph = _graph_for(network, risk_model, month)
    dry_graph = _graph_for(network, risk_model, DRY_SEASON)

    to_market = _travel_hours_to_targets(graph, markets)
    to_coldstore = _travel_hours_to_targets(graph, coldstores)
    to_gateway = _travel_hours_to_targets(graph, gateways)
    dry_to_market = _travel_hours_to_targets(dry_graph, markets)

    rows = []
    for place in network.places.values():
        m_h = to_market.get(place.id)
        c_h = to_coldstore.get(place.id)
        g_h = to_gateway.get(place.id)
        dry_h = dry_to_market.get(place.id)

        # Reliability: how much the monsoon stretches the market run. A place
        # that is 2h away in January and 9h away in July is not a 2h place.
        if m_h is not None and dry_h not in (None, 0.0):
            degradation = max(0.0, (m_h - dry_h) / dry_h)
            reliability = 100.0 * math.exp(-degradation / 0.5)
        else:
            reliability = 0.0

        components = {
            "market": _decay_score(m_h, DECAY_HOURS["market"]),
            "coldstore": _decay_score(c_h, DECAY_HOURS["coldstore"]),
            "gateway": _decay_score(g_h, DECAY_HOURS["gateway"]),
            "reliability": reliability,
        }
        score = sum(components[k] * w for k, w in COMPONENT_WEIGHTS.items())

        # A junction is a graph node, not a place anyone lives; a place cut off
        # from every market cannot be scored, only reported.
        is_settlement = bool(
            place.population > 0 or place.has_market or place.has_coldstore
        )
        reachable = m_h is not None and g_h is not None

        rows.append(
            {
                **place.to_dict(),
                "is_settlement": is_settlement,
                "reachable": reachable,
                "hours_to_market": round(m_h, 2) if m_h is not None else None,
                "hours_to_coldstore": round(c_h, 2) if c_h is not None else None,
                "hours_to_gateway": round(g_h, 2) if g_h is not None else None,
                "hours_to_market_dry": round(dry_h, 2) if dry_h is not None else None,
                "components": {k: round(v, 1) for k, v in components.items()},
                "accessibility_score": round(score, 1),
                "tier": _tier(score),
            }
        )

    rows.sort(key=lambda r: r["accessibility_score"])

    # Rank settlements only. Once the network comes from OSM, most nodes are
    # road junctions - nobody lives at a junction, and an unreachable one scores
    # a perfect zero, so ranking every node buries the real towns under graph
    # artefacts. The map still colours every node; the ranking is about places
    # where people actually are.
    ranked = [r for r in rows if r["is_settlement"] and r["reachable"]]

    return {
        "month": month,
        "risk_model": risk_model.name,
        "component_weights": COMPONENT_WEIGHTS,
        "settlements": len(ranked),
        "unreachable": sum(1 for r in rows if not r["reachable"]),
        "underserved": ranked[:10],
        "places": rows,
    }


def _tier(score: float) -> str:
    if score >= 70:
        return "well_connected"
    if score >= 50:
        return "adequate"
    if score >= 30:
        return "underserved"
    return "critically_underserved"


def facility_impact(
    network: Network,
    risk_model: RiskModel,
    candidate_ids: list[str],
    facility_type: str = "coldstore",
    month: str = PEAK_MONSOON,
    threshold_hours: float = 6.0,
) -> dict:
    """Rank candidate sites for a new facility by population brought within reach.

    This is the investment-appraisal view: for each candidate location, how many
    people move inside `threshold_hours` of the facility type, and how much the
    region's mean accessibility score improves.
    """
    if facility_type not in ("market", "coldstore"):
        raise ValueError("facility_type must be 'market' or 'coldstore'")

    baseline = accessibility_index(network, risk_model, month=month)
    key = f"hours_to_{facility_type}"
    base_rows = {r["id"]: r for r in baseline["places"]}
    base_mean = sum(r["accessibility_score"] for r in baseline["places"]) / len(base_rows)
    base_covered = sum(
        r["population"]
        for r in baseline["places"]
        if r[key] is not None and r[key] <= threshold_hours
    )

    results = []
    for candidate in candidate_ids:
        if candidate not in network.places:
            raise ValueError(f"unknown candidate site: {candidate}")

        kwargs = (
            {"extra_markets": {candidate}}
            if facility_type == "market"
            else {"extra_coldstores": {candidate}}
        )
        after = accessibility_index(network, risk_model, month=month, **kwargs)
        after_rows = {r["id"]: r for r in after["places"]}

        covered = sum(
            r["population"]
            for r in after["places"]
            if r[key] is not None and r[key] <= threshold_hours
        )
        mean_score = sum(r["accessibility_score"] for r in after["places"]) / len(after_rows)

        newly = [
            {
                "id": r["id"],
                "name": r["name"],
                "population": r["population"],
                "hours_before": base_rows[r["id"]][key],
                "hours_after": r[key],
            }
            for r in after["places"]
            if r[key] is not None
            and r[key] <= threshold_hours
            and (base_rows[r["id"]][key] is None or base_rows[r["id"]][key] > threshold_hours)
        ]

        results.append(
            {
                "site": network.places[candidate].to_dict(),
                "population_newly_covered": covered - base_covered,
                "places_newly_covered": sorted(
                    newly, key=lambda x: -x["population"]
                ),
                "mean_score_before": round(base_mean, 2),
                "mean_score_after": round(mean_score, 2),
                "mean_score_gain": round(mean_score - base_mean, 2),
            }
        )

    results.sort(key=lambda r: (-r["population_newly_covered"], -r["mean_score_gain"]))
    return {
        "facility_type": facility_type,
        "month": month,
        "threshold_hours": threshold_hours,
        "baseline_population_covered": base_covered,
        "ranked_sites": results,
    }
