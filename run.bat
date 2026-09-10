@echo off
REM Start the NER Logistics platform on Windows, from cmd.exe.
REM
REM   run.bat            the full network - 10,572 places, 25,360 km of road
REM   run.bat --seed     the small 46-place seed network, for a quick check
REM
REM cmd.exe rather than PowerShell, because PowerShell refuses to run an
REM unsigned .ps1 by default and telling a first-time user to change their
REM execution policy is a worse first five minutes than a .bat file.
setlocal
cd /d "%~dp0"

if "%PORT%"=="" set "PORT=8000"

REM The py launcher is what the python.org installer sets up; fall back to
REM python on PATH for installs that do not have it.
set "PY=py"
%PY% -V >NUL 2>&1 || set "PY=python"
%PY% -V >NUL 2>&1 || (
  echo Python was not found. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during setup, then run this again.
  exit /b 1
)

if /i "%~1"=="--seed" (
  echo Network: seed only ^(46 places^)
) else (
  set "NER_USE_OSM=1"
  echo Network: full OpenStreetMap road network
)

%PY% -c "import fastapi, uvicorn, networkx" >NUL 2>&1
if errorlevel 1 (
  echo Installing dependencies...
  %PY% -m pip install -r backend\requirements.txt
  if errorlevel 1 (
    echo.
    echo Installing the dependencies failed. docs\RUNNING.md lists the usual
    echo causes and what to do about each.
    exit /b 1
  )
)

echo.
echo   Dashboard  http://localhost:%PORT%/
echo   API docs   http://localhost:%PORT%/docs
echo.
echo   Leave this window open. Press Ctrl+C to stop.
echo.

%PY% -m uvicorn backend.app.main:app --host 127.0.0.1 --port %PORT%
