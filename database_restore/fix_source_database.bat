@echo off
REM Simple CMD batch file to fix database constraints (avoids PowerShell issues)

set SOURCE_DB=pulse_db
set POSTGRES_USER=postgres
set CONTAINER_NAME=pulse-postgres-primary

echo Fixing missing constraints in source database '%SOURCE_DB%'...
echo Container: %CONTAINER_NAME%
echo.

REM Check container
docker ps | findstr %CONTAINER_NAME% >nul
if errorlevel 1 (
    echo Container not running
    pause
    exit /b 1
)

echo Container is running
echo.

REM Copy SQL file to container
echo Copying constraint fixes to container...
docker cp fix_source_constraints.sql %CONTAINER_NAME%:/tmp/fix_constraints.sql

REM Apply the fixes
echo Applying constraint fixes...
echo This may show some errors for constraints that already exist - this is normal
echo.

docker exec %CONTAINER_NAME% psql -U %POSTGRES_USER% -d %SOURCE_DB% -f /tmp/fix_constraints.sql

echo.
echo Constraint fixes applied!
echo.

REM Simple verification using cmd
echo Quick verification...
docker exec %CONTAINER_NAME% psql -U %POSTGRES_USER% -d %SOURCE_DB% -c "SELECT COUNT(*) FROM pg_indexes WHERE indexname LIKE '%%_pkey';"

docker exec %CONTAINER_NAME% psql -U %POSTGRES_USER% -d %SOURCE_DB% -c "SELECT COUNT(*) FROM pg_constraint WHERE contype = 'f';"

REM Cleanup
docker exec %CONTAINER_NAME% rm /tmp/fix_constraints.sql

echo.
echo Source database constraints fixed!
echo.
echo Next steps:
echo 1. Run: create_dump.bat
echo 2. Run: restore_phack.bat
echo 3. Run: verify_restore.bat
pause
