@echo off
REM Simple verification script that avoids PowerShell parsing issues

set DB_NAME=phack
set POSTGRES_USER=postgres
set CONTAINER_NAME=phack-postgres-primary

echo Verifying database restore for '%DB_NAME%'...
echo Container: %CONTAINER_NAME%
echo.

REM Check if container is running
docker ps | findstr %CONTAINER_NAME% >nul
if errorlevel 1 (
    echo Container not running
    pause
    exit /b 1
)

echo Container is running
echo.

REM Simple counts only
echo Data counts:
echo.

echo Issues:
docker exec %CONTAINER_NAME% psql -U %POSTGRES_USER% -d %DB_NAME% -c "SELECT COUNT(*) FROM issues;"

echo.
echo Pull Requests:
docker exec %CONTAINER_NAME% psql -U %POSTGRES_USER% -d %DB_NAME% -c "SELECT COUNT(*) FROM pull_requests;"

echo.
echo Primary Keys:
docker exec %CONTAINER_NAME% psql -U %POSTGRES_USER% -d %DB_NAME% -c "SELECT COUNT(*) FROM pg_indexes WHERE indexname LIKE '%%_pkey';"

echo.
echo Foreign Keys:
docker exec %CONTAINER_NAME% psql -U %POSTGRES_USER% -d %DB_NAME% -c "SELECT COUNT(*) FROM pg_constraint WHERE contype = 'f';"

echo.
echo Verification complete!
pause
