@echo off
rem One command to run HeatSafe locally: API on :8000 and the web app on :3000.
rem Usage (from the repo root):  dev
rem Close the two windows it opens to stop everything.
setlocal
cd /d "%~dp0"

if not exist "ml\data\published\latest.json" (
  echo No published data found in ml\data\published. Run the pipeline or sync a bundle first.
  exit /b 1
)
if not exist "frontend\node_modules" (
  echo Installing frontend packages first...
  call npm --prefix frontend ci || exit /b 1
)

rem The API reads the published bundle; the database is optional for this demo.
set HEATSAFE_PUBLISHED_DIR=ml/data/published
set PYTHONPATH=.
start "HeatSafe API :8000" cmd /k python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
start "HeatSafe Web :3000" cmd /k npm --prefix frontend run dev

echo Starting... opening http://localhost:3000 in a few seconds.
timeout /t 6 /nobreak >nul
start "" http://localhost:3000
endlocal
