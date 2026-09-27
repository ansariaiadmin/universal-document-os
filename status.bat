@echo off
echo Status: Universal Document OS
echo ========================================
docker --version 2>nul || echo Docker missing
docker compose ps 2>nul
echo.
echo .env:
if exist .env (echo   .env exists ^(kept out of git^)) else (echo   .env missing - run install.bat)
echo.
echo Health:
curl -sf http://localhost:8000/api/health >nul 2>&1 && echo   OK - http://localhost:8000/api/health UP || echo   DOWN - run start.bat
curl -sf http://localhost:8000/app >nul 2>&1 && echo   OK - panel UP || echo   panel DOWN
echo.
pause
