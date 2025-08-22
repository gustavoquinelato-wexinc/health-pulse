@echo off
REM Restore from SQL dump to Pulse platform database

set DB_NAME=pulse_db
set DUMP_FILE=pulse_platform_full_dump.backup
set POSTGRES_USER=postgres
set POSTGRES_PASSWORD=pulse
set CONTAINER_NAME=pulse-postgres-primary

echo.
echo ========================================
echo   Pulse Platform Database Restore
echo ========================================
echo.
echo Database: %DB_NAME%
echo Container: %CONTAINER_NAME%
echo Dump file: %DUMP_FILE%
echo.

REM Check if dump file exists
if not exist "%DUMP_FILE%" (
    echo ❌ Error: Dump file '%DUMP_FILE%' not found!
    echo    Please ensure the dump file is in the current directory.
    pause
    exit /b 1
)

REM Check if container is running
docker ps | findstr "%CONTAINER_NAME%" >nul
if errorlevel 1 (
    echo ❌ Error: Container '%CONTAINER_NAME%' is not running!
    echo    Please start the database with: docker-compose -f docker-compose.db.yml up -d
    pause
    exit /b 1
)

REM Drop and create database
echo 🗑️  Dropping existing database '%DB_NAME%'...
docker exec -e PGPASSWORD=%POSTGRES_PASSWORD% %CONTAINER_NAME% psql -U %POSTGRES_USER% -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '%DB_NAME%' AND pid <> pg_backend_pid();" 2>nul
docker exec -e PGPASSWORD=%POSTGRES_PASSWORD% %CONTAINER_NAME% psql -U %POSTGRES_USER% -c "DROP DATABASE IF EXISTS %DB_NAME%;" 2>nul

echo 🆕 Creating new database '%DB_NAME%'...
docker exec -e PGPASSWORD=%POSTGRES_PASSWORD% %CONTAINER_NAME% psql -U %POSTGRES_USER% -c "CREATE DATABASE %DB_NAME%;"

if errorlevel 1 (
    echo ❌ Failed to create database
    pause
    exit /b 1
)

REM Copy dump file to container and restore
echo 📁 Copying dump file to container...
docker cp "%DUMP_FILE%" %CONTAINER_NAME%:/tmp/restore_dump.backup

echo 🔄 Restoring database from dump...
echo    This may take several minutes for large databases...
echo    Step 1: Copying dump file to container...
echo    Step 2: Restoring database with all constraints and indexes...
echo    Note: 'does not exist' errors are normal for empty database - they will be ignored
docker exec -e PGPASSWORD=%POSTGRES_PASSWORD% %CONTAINER_NAME% pg_restore -U %POSTGRES_USER% -d %DB_NAME% --no-acl --no-owner --single-transaction /tmp/restore_dump.backup

REM Note: pg_restore may return error code even on successful restore due to 'does not exist' warnings
REM Check if tables were actually created to determine success
docker exec -e PGPASSWORD=%POSTGRES_PASSWORD% %CONTAINER_NAME% psql -U %POSTGRES_USER% -d %DB_NAME% -c "\dt" | findstr "issues" >nul

if errorlevel 1 (
    echo.
    echo ❌ Restore may have failed - no 'issues' table found
    echo    Check the output above for errors
    echo.
    pause
    exit /b 1
) else (
    echo.
    echo ✅ Database restore completed successfully!
    echo.
)

REM Clean up temporary file
echo 🧹 Cleaning up temporary files...
docker exec %CONTAINER_NAME% rm -f /tmp/restore_dump.backup

echo.
echo 🔍 Verifying restore...
docker exec -e PGPASSWORD=%POSTGRES_PASSWORD% %CONTAINER_NAME% psql -U %POSTGRES_USER% -d %DB_NAME% -c "SELECT COUNT(*) as issue_count FROM issues;"
docker exec -e PGPASSWORD=%POSTGRES_PASSWORD% %CONTAINER_NAME% psql -U %POSTGRES_USER% -d %DB_NAME% -c "SELECT COUNT(*) as pr_count FROM pull_requests;"

echo.
echo 📋 Next steps:
echo    1. Update your .env file: POSTGRES_DATABASE=%DB_NAME%
echo    2. Restart services: docker-compose restart etl backend
echo.
echo ✅ Pulse platform database restore complete!
echo.
pause
