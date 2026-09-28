@echo off
title DemandLens - Cold-Start Forecasting Platform
cd /d "%~dp0"
echo ========================================================
echo   DemandLens Enterprise Decision Support Platform
echo ========================================================
echo.
echo Starting FastAPI Web Server on http://127.0.0.1:8000 ...
start "" http://127.0.0.1:8000
python app.py
pause
