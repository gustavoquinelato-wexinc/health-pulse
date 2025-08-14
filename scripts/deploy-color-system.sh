#!/bin/bash

# Color System Production Deployment Script
# 
# This script deploys the modernized color system to production
# with proper validation, backup, and rollback capabilities.
#
# Usage: ./deploy-color-system.sh [environment] [options]
#
# Environments: staging, production
# Options: --dry-run, --skip-backup, --force

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/tmp/color_system_deploy_${TIMESTAMP}.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT=""
DRY_RUN=false
SKIP_BACKUP=false
FORCE=false
BACKUP_FILE=""

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        "INFO")
            echo -e "${BLUE}[${timestamp}] ℹ️  ${message}${NC}" | tee -a "$LOG_FILE"
            ;;
        "SUCCESS")
            echo -e "${GREEN}[${timestamp}] ✅ ${message}${NC}" | tee -a "$LOG_FILE"
            ;;
        "WARNING")
            echo -e "${YELLOW}[${timestamp}] ⚠️  ${message}${NC}" | tee -a "$LOG_FILE"
            ;;
        "ERROR")
            echo -e "${RED}[${timestamp}] ❌ ${message}${NC}" | tee -a "$LOG_FILE"
            ;;
    esac
}

# Error handler
error_exit() {
    log "ERROR" "$1"
    log "ERROR" "Deployment failed. Check log file: $LOG_FILE"
    exit 1
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            staging|production)
                ENVIRONMENT="$1"
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --skip-backup)
                SKIP_BACKUP=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                error_exit "Unknown option: $1"
                ;;
        esac
    done

    if [[ -z "$ENVIRONMENT" ]]; then
        error_exit "Environment must be specified (staging or production)"
    fi
}

# Show help
show_help() {
    cat << EOF
Color System Deployment Script

Usage: $0 [environment] [options]

Environments:
    staging     Deploy to staging environment
    production  Deploy to production environment

Options:
    --dry-run       Show what would be deployed without making changes
    --skip-backup   Skip database backup (not recommended for production)
    --force         Skip confirmation prompts
    -h, --help      Show this help message

Examples:
    $0 staging --dry-run
    $0 production --force
    $0 staging
EOF
}

# Check prerequisites
check_prerequisites() {
    log "INFO" "Checking deployment prerequisites..."

    # Check required commands
    local required_commands=("docker" "docker-compose" "psql" "redis-cli" "curl" "jq")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            error_exit "Required command not found: $cmd"
        fi
    done

    # Check environment files
    local env_files=(".env" "services/backend-service/.env" "services/frontend-app/.env" "services/etl-service/.env")
    for env_file in "${env_files[@]}"; do
        if [[ ! -f "$PROJECT_ROOT/$env_file" ]]; then
            error_exit "Environment file not found: $env_file"
        fi
    done

    # Check Docker
    if ! docker info &> /dev/null; then
        error_exit "Docker is not running"
    fi

    log "SUCCESS" "Prerequisites check passed"
}

# Load environment configuration
load_environment() {
    log "INFO" "Loading environment configuration for: $ENVIRONMENT"

    # Source environment files
    if [[ -f "$PROJECT_ROOT/.env.$ENVIRONMENT" ]]; then
        source "$PROJECT_ROOT/.env.$ENVIRONMENT"
        log "SUCCESS" "Loaded environment-specific configuration"
    else
        log "WARNING" "No environment-specific configuration found (.env.$ENVIRONMENT)"
    fi

    # Validate required environment variables
    local required_vars=("DATABASE_HOST" "DATABASE_USER" "DATABASE_NAME")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            error_exit "Required environment variable not set: $var"
        fi
    done
}

# Create database backup
create_backup() {
    if [[ "$SKIP_BACKUP" == true ]]; then
        log "WARNING" "Skipping database backup (--skip-backup specified)"
        return
    fi

    log "INFO" "Creating database backup..."

    BACKUP_FILE="/tmp/pulse_backup_${TIMESTAMP}.sql"
    
    if [[ "$DRY_RUN" == true ]]; then
        log "INFO" "[DRY RUN] Would create backup: $BACKUP_FILE"
        return
    fi

    pg_dump -h "$DATABASE_HOST" -U "$DATABASE_USER" -d "$DATABASE_NAME" > "$BACKUP_FILE" || error_exit "Database backup failed"
    
    # Compress backup
    gzip "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gz"
    
    log "SUCCESS" "Database backup created: $BACKUP_FILE"
}

# Run database migration
run_migration() {
    log "INFO" "Running color system database migration..."

    cd "$PROJECT_ROOT/services/backend-service"

    if [[ "$DRY_RUN" == true ]]; then
        log "INFO" "[DRY RUN] Would run migration dry-run"
        python scripts/run_color_migration.py --dry-run || error_exit "Migration dry-run failed"
        return
    fi

    # Run actual migration
    python scripts/run_color_migration.py || error_exit "Database migration failed"
    
    log "SUCCESS" "Database migration completed"
}

# Validate migration
validate_migration() {
    log "INFO" "Validating color system migration..."

    cd "$PROJECT_ROOT/services/backend-service"

    if [[ "$DRY_RUN" == true ]]; then
        log "INFO" "[DRY RUN] Would validate migration"
        return
    fi

    python scripts/validate_color_system.py --verbose || error_exit "Migration validation failed"
    
    log "SUCCESS" "Migration validation passed"
}

# Deploy services
deploy_services() {
    log "INFO" "Deploying color system services..."

    cd "$PROJECT_ROOT"

    if [[ "$DRY_RUN" == true ]]; then
        log "INFO" "[DRY RUN] Would deploy services with docker-compose"
        return
    fi

    # Build and deploy services
    docker-compose -f docker-compose.prod.yml build || error_exit "Service build failed"
    docker-compose -f docker-compose.prod.yml up -d || error_exit "Service deployment failed"

    # Wait for services to be ready
    log "INFO" "Waiting for services to be ready..."
    sleep 30

    log "SUCCESS" "Services deployed successfully"
}

# Run health checks
run_health_checks() {
    log "INFO" "Running health checks..."

    if [[ "$DRY_RUN" == true ]]; then
        log "INFO" "[DRY RUN] Would run health checks"
        return
    fi

    local backend_url="http://localhost:3001"
    local etl_url="http://localhost:8000"

    # Check backend health
    if curl -s "$backend_url/api/v1/health" | jq -e '.status == "healthy"' > /dev/null; then
        log "SUCCESS" "Backend service is healthy"
    else
        error_exit "Backend service health check failed"
    fi

    # Check ETL health
    if curl -s "$etl_url/health" | jq -e '.status == "healthy"' > /dev/null; then
        log "SUCCESS" "ETL service is healthy"
    else
        error_exit "ETL service health check failed"
    fi

    # Check Redis
    if redis-cli ping > /dev/null 2>&1; then
        log "SUCCESS" "Redis is healthy"
    else
        log "WARNING" "Redis health check failed (optional service)"
    fi

    log "SUCCESS" "Health checks passed"
}

# Run integration tests
run_integration_tests() {
    log "INFO" "Running integration tests..."

    cd "$PROJECT_ROOT/services/backend-service"

    if [[ "$DRY_RUN" == true ]]; then
        log "INFO" "[DRY RUN] Would run integration tests"
        return
    fi

    python scripts/test_color_system.py --verbose || error_exit "Integration tests failed"
    
    log "SUCCESS" "Integration tests passed"
}

# Rollback function
rollback() {
    log "WARNING" "Rolling back deployment..."

    if [[ -n "$BACKUP_FILE" && -f "$BACKUP_FILE" ]]; then
        log "INFO" "Restoring database from backup: $BACKUP_FILE"
        gunzip -c "$BACKUP_FILE" | psql -h "$DATABASE_HOST" -U "$DATABASE_USER" -d "$DATABASE_NAME"
        log "SUCCESS" "Database restored from backup"
    fi

    # Rollback services
    cd "$PROJECT_ROOT"
    docker-compose -f docker-compose.prod.yml down
    log "SUCCESS" "Services rolled back"
}

# Cleanup function
cleanup() {
    log "INFO" "Cleaning up temporary files..."
    
    # Remove old log files (keep last 10)
    find /tmp -name "color_system_deploy_*.log" -type f | sort | head -n -10 | xargs rm -f
    
    log "SUCCESS" "Cleanup completed"
}

# Main deployment function
main() {
    log "INFO" "Starting Color System Deployment"
    log "INFO" "Environment: $ENVIRONMENT"
    log "INFO" "Dry Run: $DRY_RUN"
    log "INFO" "Log File: $LOG_FILE"
    echo

    # Confirmation prompt
    if [[ "$FORCE" != true && "$DRY_RUN" != true ]]; then
        echo -e "${YELLOW}⚠️  This will deploy the Color System to $ENVIRONMENT${NC}"
        echo -e "${YELLOW}   This includes database migrations and service updates${NC}"
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "INFO" "Deployment cancelled by user"
            exit 0
        fi
    fi

    # Deployment steps
    check_prerequisites
    load_environment
    create_backup
    run_migration
    validate_migration
    deploy_services
    run_health_checks
    run_integration_tests
    cleanup

    log "SUCCESS" "Color System deployment completed successfully!"
    log "INFO" "Deployment log saved to: $LOG_FILE"

    if [[ "$DRY_RUN" == true ]]; then
        echo
        echo -e "${BLUE}🔍 DRY RUN COMPLETED${NC}"
        echo -e "${BLUE}   No changes were made to the system${NC}"
        echo -e "${BLUE}   Run without --dry-run to execute the deployment${NC}"
    else
        echo
        echo -e "${GREEN}🎉 DEPLOYMENT SUCCESSFUL${NC}"
        echo -e "${GREEN}   Color System is now live in $ENVIRONMENT${NC}"
        echo -e "${GREEN}   Monitor the system and check logs for any issues${NC}"
    fi
}

# Trap errors and run rollback
trap 'rollback' ERR

# Parse arguments and run main function
parse_args "$@"
main
