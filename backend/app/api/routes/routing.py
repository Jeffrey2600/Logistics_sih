"""Route optimisation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...models.schemas import RouteRequest, SeasonalRequest
from ...services.routing import RoutingError, plan_route, seasonal_comparison
from ..deps import get_network, get_risk_model

router = APIRouter(prefix="/routing", tags=["routing"])


@router.post("/plan", summary="Optimal multimodal itinerary with alternatives")
def plan(request: RouteRequest):
    try:
        return plan_route(
            get_network(),
            get_risk_model(),
            origin=request.origin,
            destination=request.destination,
            month=request.month,
            weights=request.weights.model_dump() if request.weights else None,
            modes=request.modes,
            blocked_edge_ids=request.blocked_edge_ids,
            value_of_time=request.value_of_time,
            alternatives=request.alternatives,
        )
    except RoutingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/seasonal", summary="Same lane in dry season versus peak monsoon")
def seasonal(request: SeasonalRequest):
    try:
        return seasonal_comparison(
            get_network(),
            get_risk_model(),
            origin=request.origin,
            destination=request.destination,
            weights=request.weights.model_dump() if request.weights else None,
            modes=request.modes,
            value_of_time=request.value_of_time,
            alternatives=0,
        )
    except RoutingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
