#!/bin/bash

# Kairus Platform Startup Script
# This script helps you start the entire platform or individual services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}$1${NC}"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_status "Docker is running"
}

# Function to check if .env file exists
check_env_file() {
    if [ ! -f ".env" ]; then
        print_warning ".env file not found. Creating from .env.example..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
            print_warning "Please edit .env file with your actual configuration before starting services"
            print_warning "Required: SNOWFLAKE_*, JIRA_*, and security keys"
            return 1
        else
            print_error ".env.example file not found"
            exit 1
        fi
    fi
    print_status ".env file found"
    return 0
}

# Function to start all services
start_all() {
    print_header "🚀 Starting Kairus Platform - All Services"
    
    check_docker
    if ! check_env_file; then
        print_error "Please configure .env file first"
        exit 1
    fi
    
    print_status "Starting all services with docker-compose..."
    docker-compose up -d
    
    print_status "Waiting for services to be ready..."
    sleep 10
    
    print_header "📊 Service Status:"
    docker-compose ps
    
    print_header "🌐 Access URLs:"
    echo -e "  Frontend:     ${GREEN}http://localhost:3001${NC}"
    echo -e "  Backend API:  ${GREEN}http://localhost:3000${NC}"
    echo -e "  ETL Service:  ${GREEN}http://localhost:8000${NC}"
    echo -e "  AI Service:   ${GREEN}http://localhost:8001${NC}"
    echo ""
    echo -e "  API Docs:"
    echo -e "    ETL:        ${BLUE}http://localhost:8000/docs${NC}"
    echo -e "    AI:         ${BLUE}http://localhost:8001/docs${NC}"
    echo -e "    Backend:    ${BLUE}http://localhost:3000/api-docs${NC}"
}

# Function to start individual service
start_service() {
    local service=$1
    print_header "🚀 Starting $service"
    
    check_docker
    check_env_file
    
    case $service in
        "etl"|"etl-service")
            print_status "Starting ETL Service..."
            docker-compose up -d etl-service redis postgres
            print_status "ETL Service available at: http://localhost:8000"
            print_status "API Documentation: http://localhost:8000/docs"
            ;;
        "ai"|"ai-service")
            print_status "Starting AI Service..."
            docker-compose up -d ai-service
            print_status "AI Service available at: http://localhost:8001"
            print_status "API Documentation: http://localhost:8001/docs"
            ;;
        "backend"|"backend-service")
            print_status "Starting Backend Service..."
            docker-compose up -d backend-service postgres redis
            print_status "Backend Service available at: http://localhost:3000"
            print_status "API Documentation: http://localhost:3000/api-docs"
            ;;
        "frontend"|"frontend-app")
            print_status "Starting Frontend App..."
            docker-compose up -d frontend-app
            print_status "Frontend App available at: http://localhost:3001"
            ;;
        *)
            print_error "Unknown service: $service"
            print_status "Available services: etl, ai, backend, frontend"
            exit 1
            ;;
    esac
}

# Function to stop services
stop_services() {
    print_header "🛑 Stopping Kairus Platform"
    docker-compose down
    print_status "All services stopped"
}

# Function to show logs
show_logs() {
    local service=$1
    if [ -z "$service" ]; then
        print_status "Showing logs for all services..."
        docker-compose logs -f
    else
        print_status "Showing logs for $service..."
        docker-compose logs -f "$service"
    fi
}

# Function to show status
show_status() {
    print_header "📊 Kairus Platform Status"
    
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running"
        return 1
    fi
    
    echo ""
    print_status "Docker Containers:"
    docker-compose ps
    
    echo ""
    print_status "Service Health Checks:"
    
    # Check ETL Service
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "  ETL Service:     ${GREEN}✓ Healthy${NC} (http://localhost:8000)"
    else
        echo -e "  ETL Service:     ${RED}✗ Unhealthy${NC}"
    fi
    
    # Check AI Service
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo -e "  AI Service:      ${GREEN}✓ Healthy${NC} (http://localhost:8001)"
    else
        echo -e "  AI Service:      ${RED}✗ Unhealthy${NC}"
    fi
    
    # Check Backend Service
    if curl -s http://localhost:3000/health > /dev/null 2>&1; then
        echo -e "  Backend Service: ${GREEN}✓ Healthy${NC} (http://localhost:3000)"
    else
        echo -e "  Backend Service: ${RED}✗ Unhealthy${NC}"
    fi
    
    # Check Frontend App
    if curl -s http://localhost:3001 > /dev/null 2>&1; then
        echo -e "  Frontend App:    ${GREEN}✓ Healthy${NC} (http://localhost:3001)"
    else
        echo -e "  Frontend App:    ${RED}✗ Unhealthy${NC}"
    fi
}

# Function to show help
show_help() {
    print_header "Kairus Platform Management Script"
    echo ""
    echo "Usage: $0 [COMMAND] [SERVICE]"
    echo ""
    echo "Commands:"
    echo "  start [SERVICE]    Start all services or specific service"
    echo "  stop              Stop all services"
    echo "  restart [SERVICE] Restart all services or specific service"
    echo "  status            Show service status"
    echo "  logs [SERVICE]    Show logs for all or specific service"
    echo "  help              Show this help message"
    echo ""
    echo "Services:"
    echo "  etl               ETL Service (Port 8000)"
    echo "  ai                AI Service (Port 8001)"
    echo "  backend           Backend Service (Port 3000)"
    echo "  frontend          Frontend App (Port 3001)"
    echo ""
    echo "Examples:"
    echo "  $0 start                 # Start all services"
    echo "  $0 start etl            # Start only ETL service"
    echo "  $0 logs backend         # Show backend service logs"
    echo "  $0 status               # Show all service status"
}

# Main script logic
case "${1:-help}" in
    "start")
        if [ -z "$2" ]; then
            start_all
        else
            start_service "$2"
        fi
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        stop_services
        sleep 2
        if [ -z "$2" ]; then
            start_all
        else
            start_service "$2"
        fi
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs "$2"
        ;;
    "help"|"--help"|"-h")
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
