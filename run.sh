#!/usr/bin/env bash
# Start the NER Logistics platform: API + dashboard on one port.
#
#   ./run.sh              seed network (46 places) - fast, always works
#   ./run.sh --osm        full OSM network (6,502 nodes, 25,360 km of road)
#   PORT=9000 ./run.sh    pick a port
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
if [ "${1:-}" = "--osm" ]; then
  export NER_USE_OSM=1
  echo "Network: seed + OpenStreetMap"
else
  echo "Network: seed only (pass --osm for the full road network)"
fi

python3 -c "import fastapi, uvicorn, networkx" 2>/dev/null || {
  echo "Installing dependencies…"
  python3 -m pip install --quiet -r backend/requirements.txt
}

echo
echo "  Dashboard  http://localhost:${PORT}/"
echo "  API docs   http://localhost:${PORT}/docs"
echo "  Health     http://localhost:${PORT}/health"
echo
exec python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT}"
