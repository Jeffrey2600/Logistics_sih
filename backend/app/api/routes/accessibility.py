"""Accessibility index and facility-siting endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ...models.schemas import FacilityImpactRequest
from ...services.accessibility import accessibility_index, facility_impact
from ..deps import get_network, get_risk_model

router = APIRouter(prefix="/accessibility", tags=["accessibility"])


@router.get("/index", summary="Accessibility score for every place")
def index(month: str = Query("jul", description="Month to evaluate")):
    return accessibility_index(get_network(), get_risk_model(), month=month)


@router.post("/facility-impact", summary="Rank candidate sites for a new facility")
def impact(request: FacilityImpactRequest):
    try:
        return facility_impact(
            get_network(),
            get_risk_model(),
            candidate_ids=request.candidate_ids,
            facility_type=request.facility_type,
            month=request.month,
            threshold_hours=request.threshold_hours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
