"""SIH26002 - AI-Based Smart Logistics and Accessibility Intelligence for the NER.

FastAPI application entrypoint.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
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


class NoCacheStatic(StaticFiles):
    """Serve the dashboard without browser caching.

    The page is three files that must agree with each other. A browser holding
    a cached app.js against a freshly pulled index.html gets a page whose
    controls never populate, with no error to explain it - which is exactly
    what a stale cache produced after an update. The files are small and served
    from the same process, so re-fetching them costs nothing worth saving.
    """

    def is_not_modified(self, *args, **kwargs) -> bool:
        return False

    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response


# The dashboard is static files with no build step, served from the same
# process as the API. One free-tier service, one origin, no CORS in practice.
# Mounted last so it never shadows an API route.
FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/", NoCacheStatic(directory=FRONTEND_DIR, html=True), name="dashboard")
