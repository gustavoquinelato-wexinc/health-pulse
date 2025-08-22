@echo off
REM Create SQL dump (alternative format)

set SOURCE_DB=pulse_db
set DUMP_FILE=pulse_platform_full_dump.backup
set POSTGRES_USER=postgres
set CONTAINER_NAME=pulse-postgres-primary

echo 🗄️  Creating SQL dump (alternative format)...
echo    Source: %SOURCE_DB%
echo    Target: %DUMP_FILE%
echo.

REM Check container
docker ps | findstr %CONTAINER_NAME% >nul
if errorlevel 1 (
    echo ❌ Container not running
    exit /b 1
)

REM Create binary dump using internal container path (avoids Windows redirection issues)
echo 📥 Creating binary dump with all constraints, FKs, and indexes...
echo    This includes: tables, data, primary keys, foreign keys, unique constraints, indexes, triggers
echo    Step 1: Creating comprehensive dump with schema and data...
echo    Including: tables, data, primary keys, foreign keys, unique constraints, indexes
docker exec %CONTAINER_NAME% pg_dump -U %POSTGRES_USER% -d %SOURCE_DB% -Fc --verbose --no-privileges --no-owner --disable-triggers -f /tmp/pulse_dump.backup

echo    Step 2: Copying dump file to local directory...
docker cp %CONTAINER_NAME%:/tmp/pulse_dump.backup %DUMP_FILE%

echo    Step 3: Cleaning up temporary file in container...
docker exec %CONTAINER_NAME% rm /tmp/pulse_dump.backup

if errorlevel 1 (
    echo ❌ SQL dump failed
    exit /b 1
)

REM Show file info
for %%A in ("%DUMP_FILE%") do (
    echo ✅ SQL dump created: %%~nxA (%%~zA bytes)
)

echo.
echo 📋 To restore SQL dump:
echo    docker exec -i phack-postgres-primary psql -U postgres -d phack < %DUMP_FILE%
pause
