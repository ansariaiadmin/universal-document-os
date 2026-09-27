@echo off
chcp 65001 >nul
echo ========================================
echo   Universal Document OS — installer (Windows)
echo ========================================
echo.

echo [1/4] Docker
docker --version || (
  echo Docker not found - https://docs.docker.com/get-docker/
  pause
  exit /b 1
)
docker compose version || (
  echo Docker Compose V2 not found
  pause
  exit /b 1
)

echo [2/4] .env
if exist .env (
  echo   .env already exists - keeping it
) else (
  copy .env.example .env >nul
  echo   .env created from .env.example
)

echo [3/4] Build ^& start
docker compose up --build -d

echo [4/4] Waiting for health check
set /a tries=0
:waitloop
set /a tries+=1
curl -sf http://localhost:8000/api/health >nul 2>&1 && goto healthy
if %tries% geq 30 goto unhealthy
timeout /t 1 /nobreak >nul
goto waitloop

:healthy
echo.
echo ========================================
echo   Universal Document OS is ready
echo ========================================
echo   Landing:        http://localhost:8000
echo   Panel+Dashboard: http://localhost:8000/app
echo   API docs:       http://localhost:8000/api/docs
echo.
pause
exit /b 0

:unhealthy
echo Health check did not pass within 30s - run logs.bat
pause
exit /b 1
