#!/bin/bash

# 🚀 Start Multi-Instance ETL Services
# This script starts separate ETL instances for each client

echo "🚀 Starting Multi-Instance ETL Services"
echo "======================================="

# Check if Docker Compose is available
if command -v docker-compose &> /dev/null; then
    echo "🐳 Using Docker Compose for multi-instance setup..."
    docker-compose -f docker-compose.multi-client.yml up -d
    
    echo ""
    echo "✅ Multi-instance services started!"
    echo ""
    echo "📊 Service URLs:"
    echo "  • WEX ETL:      http://localhost:8000"
    echo "  • TechCorp ETL: http://localhost:8001"
    echo "  • Backend:      http://localhost:3002"
    echo "  • PostgreSQL:   localhost:5432"
    echo ""
    echo "🔍 Check logs with:"
    echo "  docker-compose -f docker-compose.multi-client.yml logs -f"
    
elif command -v python &> /dev/null; then
    echo "🐍 Using Python for local multi-instance setup..."
    echo ""
    echo "🔧 Setting up environment files..."

    # Create combined environment files for each client
    echo "Creating WEX ETL environment..."
    cat .env.shared .env.etl.wex > services/etl-service/.env.wex

    echo "Creating TechCorp ETL environment..."
    cat .env.shared .env.etl.techcorp > services/etl-service/.env.techcorp

    echo "Starting WEX ETL instance (Port 8000)..."
    cd services/etl-service
    cp .env.wex .env
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
    WEX_PID=$!
    cd ../..

    echo "Starting TechCorp ETL instance (Port 8001)..."
    cd services/etl-service
    cp .env.techcorp .env
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 &
    TECHCORP_PID=$!
    
    cd ../..
    
    echo ""
    echo "✅ Multi-instance services started!"
    echo ""
    echo "📊 Service URLs:"
    echo "  • WEX ETL:      http://localhost:8000 (PID: $WEX_PID)"
    echo "  • TechCorp ETL: http://localhost:8001 (PID: $TECHCORP_PID)"
    echo "  • Backend:      http://localhost:3002 (start separately)"
    echo ""
    echo "🛑 To stop services:"
    echo "  kill $WEX_PID $TECHCORP_PID"
    
    # Save PIDs for easy cleanup
    echo "$WEX_PID" > .wex_etl.pid
    echo "$TECHCORP_PID" > .techcorp_etl.pid
    
else
    echo "❌ Neither Docker Compose nor Python found"
    echo "Please install Docker Compose or Python to run multi-instance setup"
    exit 1
fi

echo ""
echo "🧪 Test the setup with:"
echo "  python tests/test_per_client_orchestrators.py"
