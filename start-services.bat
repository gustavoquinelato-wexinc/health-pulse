@echo off
setlocal enabledelayedexpansion

REM Pulse Platform - Service Management Script (Windows)
REM Manage all services with start, restart, and close options

set "SERVICES_RUNNING=false"
set "FIRST_RUN=true"

:MAIN_MENU
cls
echo.
echo ==============================================================
echo                    PULSE PLATFORM MANAGER
echo ==============================================================
echo.
if "%SERVICES_RUNNING%"=="true" (
    echo Status: [RUNNING] Services are ACTIVE
) else (
    echo Status: [STOPPED] Services are INACTIVE
)
echo.
echo Service URLs:
echo    Frontend App:     http://localhost:3000
echo    Backend Service:  http://localhost:3001
echo    Auth Service:     http://localhost:4000 (API only)
echo    ETL Service:      http://localhost:8000
echo.
echo --------------------------------------------------------------
echo.

if "%FIRST_RUN%"=="true" (
    echo Auto-starting all services...
    set "FIRST_RUN=false"
    goto START_ALL_SERVICES
)

echo [1] Start All Services
echo [2] Start Auth Service
echo [3] Start Backend Service
echo [4] Start ETL Service
echo [5] Start Frontend Service
echo [6] Restart All Services
echo [7] Stop All Services
echo [8] Open Frontend in Browser
echo [9] Open ETL in Browser
echo [10] Exit
echo.
set /p choice="Select option (1-10): "

if "%choice%"=="1" goto START_ALL_SERVICES
if "%choice%"=="2" goto START_AUTH_SERVICE
if "%choice%"=="3" goto START_BACKEND_SERVICE
if "%choice%"=="4" goto START_ETL_SERVICE
if "%choice%"=="5" goto START_FRONTEND_SERVICE
if "%choice%"=="6" goto RESTART_SERVICES
if "%choice%"=="7" goto STOP_SERVICES
if "%choice%"=="8" goto OPEN_FRONTEND_BROWSER
if "%choice%"=="9" goto OPEN_ETL_BROWSER
if "%choice%"=="10" goto EXIT_SCRIPT
echo Invalid choice. Please try again.
timeout /t 2 /nobreak >nul
goto MAIN_MENU

:CHECK_PREREQUISITES
echo Checking prerequisites...

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo.
    echo Press any key to return to menu...
    pause >nul
    goto MAIN_MENU
)

REM Check if Node.js is available
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH
    echo.
    echo Press any key to return to menu...
    pause >nul
    goto MAIN_MENU
)

echo [OK] Prerequisites check passed
echo.
goto :eof

:START_ALL_SERVICES
echo.
echo Starting All Pulse Platform Services...
echo =======================================
call :CHECK_PREREQUISITES

echo Checking for Windows Terminal...
wt --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Windows Terminal not found, using separate CMD windows...
    echo.
    echo Starting services in separate CMD windows...
    echo.

    echo Starting Auth Service on port 4000...
    cd services\auth-service
    start "Auth Service" cmd /k "..\..\venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload"
    cd ..\..
    timeout /t 2 /nobreak >nul

    echo Starting Backend Service on port 3001...
    cd services\backend-service
    start "Backend Service" cmd /k "..\..\venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload"
    cd ..\..
    timeout /t 2 /nobreak >nul

    echo Starting ETL Service on port 8000...
    cd services\etl-service
    start "ETL Service" cmd /k "..\..\venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    cd ..\..
    timeout /t 2 /nobreak >nul

    echo Starting Frontend Service on port 3000...
    cd services\frontend-app
    start "Frontend Service" cmd /k "npm run dev"
    cd ..\..
    timeout /t 2 /nobreak >nul
) else (
    echo [OK] Windows Terminal found
    echo.
    echo Starting services in Windows Terminal with multiple tabs...
    echo.

    REM Start Windows Terminal with multiple tabs
    wt new-tab --title "Auth Service" -d "%CD%\services\auth-service" cmd /k "..\..\venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload" ; new-tab --title "Backend Service" -d "%CD%\services\backend-service" cmd /k "..\..\venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload" ; new-tab --title "ETL Service" -d "%CD%\services\etl-service" cmd /k "..\..\venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" ; new-tab --title "Frontend App" -d "%CD%\services\frontend-app" cmd /k "npm run dev" ; new-tab --title "Migrations" -d "%CD%\services\backend-service" cmd /k "echo Migration Terminal Ready && echo Use: ..\..\venv\Scripts\python -m alembic upgrade head && cmd"

    timeout /t 3 /nobreak >nul
)

set "SERVICES_RUNNING=true"
echo.
echo [SUCCESS] All services started successfully!
echo.
timeout /t 2 /nobreak >nul
goto MAIN_MENU

:START_AUTH_SERVICE
echo.
echo Starting Auth Service...
echo =======================
call :CHECK_PREREQUISITES
call :START_SINGLE_SERVICE "Auth Service" "services\auth-service" "..\..\venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload"
timeout /t 2 /nobreak >nul
goto MAIN_MENU

:START_BACKEND_SERVICE
echo.
echo Starting Backend Service...
echo ===========================
call :CHECK_PREREQUISITES
call :START_SINGLE_SERVICE "Backend Service" "services\backend-service" "..\..\venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload"
timeout /t 2 /nobreak >nul
goto MAIN_MENU

:START_ETL_SERVICE
echo.
echo Starting ETL Service...
echo ======================
call :CHECK_PREREQUISITES
call :START_SINGLE_SERVICE "ETL Service" "services\etl-service" "..\..\venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 2 /nobreak >nul
goto MAIN_MENU

:START_FRONTEND_SERVICE
echo.
echo Starting Frontend Service...
echo ============================
call :START_SINGLE_SERVICE "Frontend Service" "services\frontend-app" "npm run dev"
timeout /t 2 /nobreak >nul
goto MAIN_MENU

:START_SINGLE_SERVICE
set "service_name=%~1"
set "service_dir=%~2"
set "service_cmd=%~3"

echo Starting %service_name%...
wt --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Windows Terminal not found, using CMD window...
    cd %service_dir%
    start "%service_name%" cmd /k "%service_cmd%"
    cd ..\..
) else (
    echo [OK] Opening %service_name% in new Windows Terminal tab...
    wt new-tab --title "%service_name%" -d "%CD%\%service_dir%" cmd /k "%service_cmd%"
)
echo.
echo [SUCCESS] %service_name% started successfully!
goto :eof

:RESTART_SERVICES
if "%SERVICES_RUNNING%"=="false" (
    echo [WARNING] No services are currently running!
    echo.
    echo Press any key to return to menu...
    pause >nul
    goto MAIN_MENU
)

echo.
echo Restarting Pulse Platform Services...
echo ======================================
call :STOP_SERVICES_SILENT
timeout /t 2 /nobreak >nul
goto START_ALL_SERVICES

:STOP_SERVICES
if "%SERVICES_RUNNING%"=="false" (
    echo [WARNING] No services are currently running!
    echo.
    timeout /t 2 /nobreak >nul
    goto MAIN_MENU
)

echo.
echo Stopping Pulse Platform Services...
echo ====================================
call :STOP_SERVICES_SILENT
echo.
echo [SUCCESS] All services stopped successfully!
echo.
timeout /t 2 /nobreak >nul
goto MAIN_MENU

:STOP_SERVICES_SILENT
echo Finding and stopping service processes...
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" /fo csv ^| findstr "uvicorn"') do (
    echo   Stopping Python service %%i...
    taskkill /pid %%i /f >nul 2>&1
)
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq node.exe" /fo csv ^| findstr "node"') do (
    echo   Stopping Node.js service %%i...
    taskkill /pid %%i /f >nul 2>&1
)
set "SERVICES_RUNNING=false"
goto :eof

:OPEN_FRONTEND_BROWSER
echo.
echo Opening Frontend in browser...
start http://localhost:3000
echo.
timeout /t 1 /nobreak >nul
goto MAIN_MENU

:OPEN_ETL_BROWSER
echo.
echo Opening ETL Service in browser...
start http://localhost:8000
echo.
timeout /t 1 /nobreak >nul
goto MAIN_MENU

:EXIT_SCRIPT
if "%SERVICES_RUNNING%"=="true" (
    echo.
    echo [INFO] Stopping all services before exit...
    call :STOP_SERVICES_SILENT
    echo [SUCCESS] All services stopped.
)
echo.
echo Goodbye! Thanks for using Pulse Platform Manager.
echo.
timeout /t 2 /nobreak >nul
exit /b 0
