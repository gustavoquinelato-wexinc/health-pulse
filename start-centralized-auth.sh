#!/bin/bash

# Pulse Platform - Centralized Authentication Startup Script
# Starts all services with centralized authentication

echo "🚀 Starting Pulse Platform with Centralized Authentication..."
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to start a service
start_service() {
    local service_name=$1
    local port=$2
    local directory=$3
    local command=$4
    
    echo -e "${BLUE}Starting $service_name on port $port...${NC}"
    
    if check_port $port; then
        echo -e "${YELLOW}⚠️  Port $port is already in use. Skipping $service_name.${NC}"
        return
    fi
    
    cd "$directory"
    
    # Start service in background
    eval "$command" &
    local pid=$!
    
    # Wait a moment and check if service started
    sleep 2
    if kill -0 $pid 2>/dev/null; then
        echo -e "${GREEN}✅ $service_name started successfully (PID: $pid)${NC}"
    else
        echo -e "${RED}❌ Failed to start $service_name${NC}"
    fi
    
    cd - > /dev/null
}

echo -e "${BLUE}🔧 Checking prerequisites...${NC}"

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python is not installed or not in PATH${NC}"
    exit 1
fi

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed or not in PATH${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"
echo ""

# Start services in order
echo -e "${BLUE}🏗️  Starting services...${NC}"
echo ""

# 1. Start Auth Service (Port 4000)
start_service "Auth Service" 4000 "services/auth-service" "python -m uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload"

# 2. Start Backend Service (Port 3001)
start_service "Backend Service" 3001 "services/backend-service" "venv\\Scripts\\python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload"

# 3. Start ETL Service (Port 8000)
start_service "ETL Service" 8000 "services/etl-service" "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

# 4. Start Frontend Service (Port 3000)
start_service "Frontend Service" 3000 "services/frontend-app" "npm run dev"

echo ""
echo -e "${GREEN}🎉 All services started!${NC}"
echo ""
echo -e "${BLUE}📋 Service URLs:${NC}"
echo -e "   🔐 Auth Service:     ${YELLOW}http://localhost:4000${NC} (API only)"
echo -e "   🔧 Backend Service:  ${YELLOW}http://localhost:3001${NC}"
echo -e "   📊 ETL Service:      ${YELLOW}http://localhost:8000${NC}"
echo -e "   🌐 Frontend App:     ${YELLOW}http://localhost:3000${NC}"
echo ""
echo -e "${BLUE}🔐 Secure Authentication Flow:${NC}"
echo -e "   1. Visit ${YELLOW}http://localhost:3000${NC} (Frontend)"
echo -e "   2. Shows Frontend login page (no redirect)"
echo -e "   3. Enter credentials → Backend validates via Auth Service API"
echo -e "   4. Visit ${YELLOW}http://localhost:8000${NC} (ETL) → Automatically authenticated"
echo ""
echo -e "${BLUE}🧪 Testing:${NC}"
echo -e "   • Default credentials: ${YELLOW}admin@pulse.com / pulse${NC}"
echo -e "   • Check logs in each service terminal for debugging"
echo ""
echo -e "${GREEN}✨ Secure Centralized Authentication is now active!${NC}"
echo -e "${BLUE}Press Ctrl+C to stop all services${NC}"

# Wait for user to stop services
wait
