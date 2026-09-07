#!/usr/bin/env bash
# Start the NER Logistics platform: API + dashboard on one port.
#
#   ./run.sh              the full network - 10,572 places, 25,360 km of road
#   ./run.sh --seed       the small 46-place seed network, for a quick check
#   PORT=9000 ./run.sh    pick a port
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
# The full network is the default. It is committed, so it always loads, and a
# demo should not depend on remembering a flag - typing ./run.sh used to give
# the 46-place seed network, which is a fraction of what the project does.
if [ "${1:-}" = "--seed" ]; then
  echo "Network: seed only (46 places)"
else
  export NER_USE_OSM=1
  echo "Network: full OpenStreetMap road network"
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
