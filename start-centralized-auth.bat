@echo off
setlocal enabledelayedexpansion

REM Pulse Platform - Centralized Authentication Startup Script (Windows)
REM Starts all services with centralized authentication

echo Starting Pulse Platform with Centralized Authentication...
echo ==================================================

REM Function to check if port is in use
:check_port
netstat -an | find ":%1 " | find "LISTENING" >nul
if %errorlevel% == 0 (
    echo WARNING: Port %1 is already in use. Skipping %2.
    exit /b 1
) else (
    echo OK: Port %1 is free. Starting %2...
    exit /b 0
)

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

echo Starting services...
echo.

REM Start Auth Service (Port 4000)
call :check_port 4000 "Auth Service"
if %errorlevel% neq 0 goto skip_auth
echo Starting Auth Service on port 4000...
cd services\auth-service
start "Auth Service" cmd /k "venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload"
cd ..\..
timeout /t 3 /nobreak >nul
:skip_auth

REM Start Backend Service (Port 3001)
call :check_port 3001 "Backend Service"
if %errorlevel% neq 0 goto skip_backend
echo Starting Backend Service on port 3001...
cd services\backend-service
start "Backend Service" cmd /k "venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload"
cd ..\..
timeout /t 3 /nobreak >nul
:skip_backend

REM Start ETL Service (Port 8000)
call :check_port 8000 "ETL Service"
if %errorlevel% neq 0 goto skip_etl
echo Starting ETL Service on port 8000...
cd services\etl-service
start "ETL Service" cmd /k "venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
cd ..\..
timeout /t 3 /nobreak >nul
:skip_etl

REM Start Frontend Service (Port 3000)
call :check_port 3000 "Frontend Service"
if %errorlevel% == 0 goto skip_frontend
echo Starting Frontend Service on port 3000...
cd services\frontend-app
start "Frontend Service" cmd /k "npm run dev"
cd ..\..
timeout /t 3 /nobreak >nul
:skip_frontend

echo.
echo All services started!
echo.
echo Service URLs:
echo    Auth Service:     http://localhost:4000 (API only)
echo    Backend Service:  http://localhost:3001
echo    ETL Service:      http://localhost:8000
echo    Frontend App:     http://localhost:3000
echo.
echo Secure Authentication Flow:
echo    1. Visit http://localhost:3000 (Frontend)
echo    2. Shows Frontend login page (no redirect)
echo    3. Enter credentials - Backend validates via Auth Service API
echo    4. Visit http://localhost:8000 (ETL) - Automatically authenticated
echo.
echo Testing:
echo    Default credentials: admin@pulse.com / pulse
echo    Check logs in each service terminal for debugging
echo.
echo Secure Centralized Authentication is now active!
echo.
echo Press any key to open the Frontend in your browser...
pause >nul

REM Open frontend in default browser
start http://localhost:3000

echo.
echo Services are running in separate terminal windows.
echo Close those windows to stop the services.
echo.
pause
