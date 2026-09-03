"""Request and response contracts for the public API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Month = Literal["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
Mode = Literal["road", "rail", "water", "air"]


class Weights(BaseModel):
    cost: float = Field(0.4, ge=0, description="Weight on freight cost per tonne")
    time: float = Field(0.4, ge=0, description="Weight on total transit time")
    risk: float = Field(0.2, ge=0, description="Weight on disruption probability")


class RouteRequest(BaseModel):
    origin: str = Field(..., description="Origin place id, e.g. KHM")
    destination: str = Field(..., description="Destination place id, e.g. GAU")
    month: Month = Field("jul", description="Month of despatch; drives monsoon risk")
    modes: list[Mode] | None = Field(
        None, description="Restrict to these modes; omit to allow all"
    )
    weights: Weights | None = None
    blocked_edge_ids: list[str] = Field(
        default_factory=list,
        description="Segments to treat as closed, e.g. ['SLG-GTK-road']",
    )
    value_of_time: float = Field(
        25.0, ge=0, description="INR per tonne per hour; raise for perishables"
    )
    alternatives: int = Field(2, ge=0, le=5)


class SeasonalRequest(BaseModel):
    origin: str
    destination: str
    modes: list[Mode] | None = None
    weights: Weights | None = None
    value_of_time: float = Field(25.0, ge=0)


class FacilityImpactRequest(BaseModel):
    candidate_ids: list[str] = Field(..., min_length=1, max_length=12)
    facility_type: Literal["market", "coldstore"] = "coldstore"
    month: Month = "jul"
    threshold_hours: float = Field(6.0, gt=0, le=72)
