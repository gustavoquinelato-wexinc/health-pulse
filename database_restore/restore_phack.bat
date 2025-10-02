@echo off
REM Restore from SQL dump to phack database

set DB_NAME=phack
set DUMP_FILE=pulse_platform_full_dump.backup
set POSTGRES_USER=postgres
set CONTAINER_NAME=phack-postgres-primary

echo 🗄️  Restoring from SQL dump to '%DB_NAME%'...
echo    Dump file: %DUMP_FILE%
echo    Container: %CONTAINER_NAME%
echo.

REM Check if binary dump file exists
if not exist "%DUMP_FILE%" (
    echo ❌ Error: Binary dump file '%DUMP_FILE%' not found!
    echo    Run create_dump_sql.bat first to create the binary dump
    pause
    exit /b 1
)

REM Show file info
for %%A in ("%DUMP_FILE%") do echo ✅ Found binary dump: %%~nxA (%%~zA bytes)
echo.

REM Check container
docker ps | findstr %CONTAINER_NAME% >nul
if errorlevel 1 (
    echo ❌ Container not running
    exit /b 1
)

REM Drop and create database
echo 🗑️  Dropping existing database '%DB_NAME%'...
docker exec %CONTAINER_NAME% psql -U %POSTGRES_USER% -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '%DB_NAME%' AND pid <> pg_backend_pid();" 2>nul
docker exec %CONTAINER_NAME% psql -U %POSTGRES_USER% -c "DROP DATABASE IF EXISTS %DB_NAME%;" 2>nul

echo 🆕 Creating new database '%DB_NAME%'...
docker exec %CONTAINER_NAME% psql -U %POSTGRES_USER% -c "CREATE DATABASE %DB_NAME%;"
if errorlevel 1 (
    echo ❌ Failed to create database
    exit /b 1
)

REM Restore from binary dump using proper method
echo 📥 Restoring from binary dump (this may take several minutes)...
echo    Step 1: Copying dump file to container...
docker cp %DUMP_FILE% %CONTAINER_NAME%:/tmp/restore_dump.backup

echo    Step 2: Restoring database with all constraints and indexes...
echo    Note: 'does not exist' errors are normal for empty database - they will be ignored
docker exec %CONTAINER_NAME% pg_restore -U %POSTGRES_USER% -d %DB_NAME% --no-acl --no-owner --single-transaction /tmp/restore_dump.backup

REM Note: pg_restore may return error code even on successful restore due to 'does not exist' warnings
REM Check if tables were actually created to determine success
docker exec %CONTAINER_NAME% psql -U %POSTGRES_USER% -d %DB_NAME% -c "\dt" | findstr "work_items" >nul
if errorlevel 1 (
    echo ❌ Binary restore failed - no tables were created
    docker exec %CONTAINER_NAME% rm /tmp/restore_dump.backup 2>nul
    exit /b 1
) else (
    echo ✅ Tables created successfully (warnings about non-existent items are normal)
)

echo    Step 3: Cleaning up temporary file in container...
docker exec %CONTAINER_NAME% rm /tmp/restore_dump.backup

echo ✅ Binary restore completed successfully!
echo.
echo 🔍 Verifying restore...
docker exec %CONTAINER_NAME% psql -U %POSTGRES_USER% -d %DB_NAME% -c "SELECT COUNT(*) as work_item_count FROM work_items;"
docker exec %CONTAINER_NAME% psql -U %POSTGRES_USER% -d %DB_NAME% -c "SELECT COUNT(*) as pr_count FROM prs;"

echo.
echo 📋 Next steps:
echo    1. Update your .env file: DATABASE_NAME=%DB_NAME%
echo    2. Restart services: docker-compose restart etl-service backend-service
pause
