<#
.SYNOPSIS
  Start the NER Logistics platform: API + dashboard on one port.

.EXAMPLE
  .\run.ps1
  Seed network (46 places) - fast, always works.

.EXAMPLE
  .\run.ps1 -Osm
  Full OpenStreetMap network: 6,502 nodes, 25,360 km of road.

.EXAMPLE
  .\run.ps1 -Osm -Port 9000
#>
param(
    [switch]$Osm,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Windows installs the launcher as `python`; some setups only have `py`.
$python = if (Get-Command python -ErrorAction SilentlyContinue) { "python" }
          elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" }
          else { throw "Python 3.11+ not found. Install it from python.org and re-run." }

if ($Osm) {
    $env:NER_USE_OSM = "1"
    Write-Host "Network: seed + OpenStreetMap"
} else {
    Write-Host "Network: seed only (pass -Osm for the full road network)"
}

& $python -c "import fastapi, uvicorn, networkx" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies..."
    & $python -m pip install --quiet -r backend/requirements.txt
}

Write-Host ""
Write-Host "  Dashboard  http://localhost:$Port/"
Write-Host "  API docs   http://localhost:$Port/docs"
Write-Host "  Health     http://localhost:$Port/health"
Write-Host ""

& $python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $Port
