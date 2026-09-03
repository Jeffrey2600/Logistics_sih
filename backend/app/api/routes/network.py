"""Network reference data: places and segments, with live risk scoring."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ...config import MODES
from ..deps import get_network, get_risk_model

router = APIRouter(prefix="/network", tags=["network"])


@router.get("/places", summary="All places in the network")
def list_places(state: str | None = Query(None, description="Filter by state name")):
    network = get_network()
    places = [p.to_dict() for p in network.places.values()]
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
        rows.append(
            {
                **edge,
                "from_name": network.places[edge["u"]].name,
                "to_name": network.places[edge["v"]].name,
                "geometry": [
                    [network.places[edge["u"]].lon, network.places[edge["u"]].lat],
                    [network.places[edge["v"]].lon, network.places[edge["v"]].lat],
                ],
                "risk": assessment.to_dict(),
            }
        )

    rows.sort(key=lambda r: -r["risk"]["probability"])
    return {
        "count": len(rows),
        "month": month,
        "risk_model": risk_model.name,
        "modes": list(MODES),
        "segments": rows,
    }
