"""SIH26002 - AI-Based Smart Logistics and Accessibility Intelligence for the NER.

FastAPI application entrypoint.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.deps import get_network, get_risk_model
from .api.routes import accessibility, network, routing
from .config import BASE_DIR
from .core.network import use_osm

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
    components = net.components()
    orphaned = sum(len(c) for c in components[1:])
    return {
        "status": "ok",
        "places": len(net.places),
        "segments": len(net.edges),
        "risk_model": get_risk_model().name,
        "network_source": "seed+osm" if use_osm() else "seed",
        # A fragmented network still answers routing queries for the reachable
        # pairs while every score for an orphaned place is quietly wrong, so
        # connectivity is reported rather than assumed.
        "connected": len(components) == 1,
        "components": len(components),
        "orphaned_places": orphaned,
    }


# The dashboard is static files with no build step, served from the same
# process as the API. One free-tier service, one origin, no CORS in practice.
# Mounted last so it never shadows an API route.
FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="dashboard")
