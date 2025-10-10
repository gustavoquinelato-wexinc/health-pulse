@echo off
echo Restarting Backend Service...

REM Kill any existing backend processes
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3001') do (
    echo Killing process %%a
    taskkill /PID %%a /F >nul 2>&1
)

REM Wait a moment
timeout /t 2 /nobreak >nul

REM Start the backend service
echo Starting backend service on port 3001...
cd /d "%~dp0"
python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --log-level info --no-access-log

pause
