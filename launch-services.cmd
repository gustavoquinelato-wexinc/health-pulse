@echo off
REM Simple launcher that forces Command Prompt execution
cd /d "%~dp0"
cmd /k start-services.bat
