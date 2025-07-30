@echo off

REM 🚀 Start Multi-Instance ETL Services (Windows)
REM This script starts separate ETL instances for each client

echo 🚀 Starting Multi-Instance ETL Services
echo =======================================

REM Check if Docker Compose is available
docker-compose --version >nul 2>&1
if %errorlevel% == 0 (
    echo 🐳 Using Docker Compose for multi-instance setup...
    docker-compose -f docker-compose.multi-client.yml up -d
    
    echo.
    echo ✅ Multi-instance services started!
    echo.
    echo 📊 Service URLs:
    echo   • WEX ETL:      http://localhost:8000
    echo   • TechCorp ETL: http://localhost:8001
    echo   • Backend:      http://localhost:3001
    echo   • PostgreSQL:   localhost:5432
    echo.
    echo 🔍 Check logs with:
    echo   docker-compose -f docker-compose.multi-client.yml logs -f
    
) else (
    echo 🐍 Using Python for local multi-instance setup...
    echo.
    echo 🔧 Setting up environment files...

    REM Create combined environment files for each client
    echo Creating WEX ETL environment...
    copy /b .env.shared + .env.etl.wex services\etl-service\.env.wex

    echo Creating TechCorp ETL environment...
    copy /b .env.shared + .env.etl.techcorp services\etl-service\.env.techcorp

    echo Starting WEX ETL instance (Port 8000)...
    cd services\etl-service
    copy .env.wex .env
    start "WEX ETL" python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
    cd ..\..

    echo Starting TechCorp ETL instance (Port 8001)...
    cd services\etl-service
    copy .env.techcorp .env
    start "TechCorp ETL" python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
    
    cd ..\..
    
    echo.
    echo ✅ Multi-instance services started!
    echo.
    echo 📊 Service URLs:
    echo   • WEX ETL:      http://localhost:8000
    echo   • TechCorp ETL: http://localhost:8001
    echo   • Backend:      http://localhost:3001 (start separately)
    echo.
    echo 🛑 To stop services, close the terminal windows
)

echo.
echo 🧪 Test the setup with:
echo   python tests/test_per_client_orchestrators.py

pause
