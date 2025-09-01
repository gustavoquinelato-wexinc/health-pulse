@echo off
setlocal enabledelayedexpansion

REM Pulse Platform - Simple Service Startup Script (Windows)
REM Starts all services with their correct virtual environments

echo Starting Pulse Platform Services...
echo ===================================

echo Checking prerequisites...

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if Node.js is available
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    pause
    exit /b 1
)

echo OK: Prerequisites check passed
echo.

echo Checking for Windows Terminal...
wt --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Windows Terminal not found, falling back to separate CMD windows...
    echo.
    echo Starting services in separate CMD windows...
    echo.

    echo Starting Auth Service on port 4000...
    cd services\auth-service
    start "Auth Service" cmd /k ".\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload"
    cd ..\..
    timeout /t 2 /nobreak >nul

    echo Starting Backend Service on port 3001...
    cd services\backend-service
    start "Backend Service" cmd /k ".\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload"
    cd ..\..
    timeout /t 2 /nobreak >nul

    echo Starting ETL Service on port 8000...
    cd services\etl-service
    start "ETL Service" cmd /k ".\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    cd ..\..
    timeout /t 2 /nobreak >nul

    echo Starting Frontend Service on port 3000...
    cd services\frontend-app
    start "Frontend Service" cmd /k "npm run dev"
    cd ..\..
    timeout /t 2 /nobreak >nul
) else (
    echo OK: Windows Terminal found
    echo.
    echo Starting services in Windows Terminal with multiple tabs...
    echo.

    REM Start Windows Terminal with multiple tabs
    wt -w 0 ^
        nt -d "%CD%\services\auth-service" --title "Auth Service" cmd /k ".\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload" ^; ^
        nt -d "%CD%\services\backend-service" --title "Backend Service" cmd /k ".\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload" ^; ^
        nt -d "%CD%\services\etl-service" --title "ETL Service" cmd /k ".\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" ^; ^
        nt -d "%CD%\services\frontend-app" --title "Frontend App" cmd /k "npm run dev" ^; ^
        nt -d "%CD%\services\backend-service" --title "Migrations" cmd /k "echo Migration Terminal Ready - Use: .\venv\Scripts\python.exe -m alembic upgrade head"

    timeout /t 3 /nobreak >nul
)

echo.
echo All services started!
echo.
echo Service URLs:
echo    Auth Service:     http://localhost:4000 (API only)
echo    Backend Service:  http://localhost:3001
echo    ETL Service:      http://localhost:8000
echo    Frontend App:     http://localhost:3000
echo.
echo Migration Commands (use in Migrations tab):
echo    Run migrations:   .\venv\Scripts\python.exe -m alembic upgrade head
echo    Create migration: .\venv\Scripts\python.exe -m alembic revision --autogenerate -m "description"
echo    Migration status: .\venv\Scripts\python.exe -m alembic current
echo.
echo Default credentials: admin@pulse.com / pulse
echo Check logs in each service terminal for debugging
echo.
echo Press any key to open the Frontend in your browser...
pause >nul

REM Open frontend in default browser
start http://localhost:3000

echo.
wt --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Services are running in separate CMD windows.
    echo Close those windows to stop the services.
) else (
    echo Services are running in Windows Terminal tabs.
    echo Close the Windows Terminal window or individual tabs to stop services.
)
echo.
pause
