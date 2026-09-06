"""Network reference data: places and segments, with live risk scoring."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ...config import MODES
from ...core.network import JUNCTION_KIND
from ..deps import get_network, get_risk_model

router = APIRouter(prefix="/network", tags=["network"])


def _is_named(name: str) -> bool:
    """OSM junctions are named after their node id; those are not place names."""
    return not (name.startswith("n") and name[1:].isdigit())


def segment_label(from_name: str, to_name: str, route_ref: str) -> str:
    """A label a person can read.

    Most nodes in an OSM-derived network are unnamed junctions, so "n4021632273
    - n12296272662" is the common case and tells a planner nothing. Falling back
    to the road reference at least says which highway is affected.
    """
    from_named, to_named = _is_named(from_name), _is_named(to_name)
    if from_named and to_named:
        return f"{from_name} – {to_name}"
    if from_named:
        return f"{route_ref} near {from_name}"
    if to_named:
        return f"{route_ref} near {to_name}"
    return route_ref


@router.get("/places", summary="All places in the network")
def list_places(
    state: str | None = Query(None, description="Filter by state name"),
    settlements_only: bool = Query(
        False,
        description="Exclude road junctions. On an OSM-derived network most "
                    "nodes are junctions, which nobody can pick from a list.",
    ),
):
    network = get_network()
    places = [
        p.to_dict() for p in network.places.values()
        if not settlements_only or p.kind != JUNCTION_KIND
    ]
    if state:
        places = [p for p in places if p["state"].lower() == state.lower()]
    places.sort(key=lambda p: p["name"])
    return {"count": len(places), "places": places}


@router.get("/segments", summary="All segments with risk for the given month")
def list_segments(
    month: str = Query("jul", description="Month of travel, e.g. jul"),
    mode: str | None = Query(None, description="Filter by mode"),
):
    network = get_network()
    risk_model = get_risk_model()

    rows = []
    for edge in network.edges:
        if mode and edge["mode"] != mode:
            continue
        assessment = risk_model.assess(edge, month)
        from_name = network.places[edge["u"]].name
        to_name = network.places[edge["v"]].name
        risk = assessment.to_dict()
        # The per-factor breakdown is only wanted when a user clicks one
        # segment. Shipping it for all 11,000 costs megabytes on every load.
        risk.pop("drivers", None)

        rows.append(
            {
                **edge,
                "from_name": from_name,
                "to_name": to_name,
                "label": segment_label(from_name, to_name, edge["route_ref"]),
                "named": _is_named(from_name) or _is_named(to_name),
                "geometry": [
                    [network.places[edge["u"]].lon, network.places[edge["u"]].lat],
                    [network.places[edge["v"]].lon, network.places[edge["v"]].lat],
                ],
                "risk": risk,
            }
        )

    rows.sort(key=lambda r: -r["risk"]["probability"])
    return {
        "count": len(rows),
        "month": month,
        "risk_model": risk_model.name,
        "modes": list(MODES),
        # Landslide history is what separates a merely steep road from a
        # known-bad one. Where the network carries none, the risk model is
        # running on terrain, carriageway width and rainfall alone, and its
        # range is correspondingly compressed - the UI says so rather than
        # presenting a weaker signal as if it were the same one.
        "landslide_history": any(e["landslide_events"] for e in network.edges),
        "segments": rows,
    }
