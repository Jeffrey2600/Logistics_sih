"""SIH26002 - AI-Based Smart Logistics and Accessibility Intelligence for the NER.

FastAPI application entrypoint.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.deps import get_network, get_risk_model
from .api.routes import accessibility, network, routing

app = FastAPI(
    title="NER Logistics & Accessibility Intelligence",
    description=(
        "Multimodal freight routing and spatial accessibility scoring for the "
        "eight North Eastern states, with monsoon disruption risk priced into "
        "every segment."
    ),
    version="0.1.0",
)

# The dashboard is served from a different origin on free-tier hosting.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(network.router)
app.include_router(routing.router)
app.include_router(accessibility.router)


@app.get("/health", tags=["meta"], summary="Liveness and loaded-data summary")
def health():
    net = get_network()
    return {
        "status": "ok",
        "places": len(net.places),
        "segments": len(net.edges),
        "risk_model": get_risk_model().name,
    }
