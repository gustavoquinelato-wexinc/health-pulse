# Health Pulse PowerShell Profile Functions
# Copy this entire file content into your $PROFILE

# === NAVIGATION COMMANDS ===

# Main project directory
function pulse {
    Set-Location C:\workspace\health-pulse\
    Write-Host "[PULSE] Health Pulse Project Root" -ForegroundColor Cyan
}

# Services parent directory
function pulse-services {
    Set-Location C:\workspace\health-pulse\services\
    Write-Host "[PULSE] Services Directory" -ForegroundColor Cyan
}

# Documentation directory
function pulse-docs {
    Set-Location C:\workspace\health-pulse\docs\
    Write-Host "[PULSE] Documentation Directory" -ForegroundColor Cyan
}

# Backend service directory
function pulse-backend {
    Set-Location C:\workspace\health-pulse\services\backend-service\
    Write-Host "[PULSE] Backend Service" -ForegroundColor Blue
}

# Auth service directory
function pulse-auth {
    Set-Location C:\workspace\health-pulse\services\auth-service\
    Write-Host "[PULSE] Auth Service" -ForegroundColor Blue
}

# Frontend app directory
function pulse-frontend {
    Set-Location C:\workspace\health-pulse\services\frontend-app\
    Write-Host "[PULSE] Frontend App" -ForegroundColor Blue
}

# ETL Frontend app directory
function pulse-etl-frontend {
    Set-Location C:\workspace\health-pulse\services\etl-frontend\
    Write-Host "[PULSE] ETL Frontend" -ForegroundColor Blue
}



# === SERVER COMMANDS ===

# Starts the backend server (with better reload handling)
function run-backend {
    pulse-backend
    Write-Host "[START] Starting backend server on port 3001..." -ForegroundColor Green
    # Kill existing process first
    Get-Process | Where-Object {$_.ProcessName -eq "python" -and $_.CommandLine -like "*3001*"} | Stop-Process -Force -ErrorAction SilentlyContinue
    python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload
}

# Restart backend (kills and restarts)
function restart-backend {
    Write-Host "[RESTART] Restarting backend server..." -ForegroundColor Yellow
    Get-Process | Where-Object {$_.ProcessName -eq "python" -and $_.CommandLine -like "*3001*"} | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    run-backend
}

# Starts the auth server
function run-auth {
    pulse-auth
    Write-Host "[START] Starting auth server on port 4000..." -ForegroundColor Green
    python -m uvicorn app.main:app --reload --port 4000
}



# Starts the frontend dev server
function run-frontend {
    pulse-frontend
    Write-Host "[START] Starting frontend dev server..." -ForegroundColor Green
    npm run dev
}

# Starts the ETL frontend dev server
function run-etl-frontend {
    pulse-etl-frontend
    Write-Host "[START] Starting ETL frontend dev server..." -ForegroundColor Green
    npm run dev
}

# Opens the Qdrant dashboard
function run-qdrant {
    Write-Host "[OPEN] Opening Qdrant dashboard..." -ForegroundColor Cyan
    Start-Process "http://localhost:6333/dashboard"
}

# Opens RabbitMQ Management
function run-rabbit {
    Write-Host "[OPEN] Opening RabbitMQ Management..." -ForegroundColor Cyan
    Start-Process "http://localhost:15672"
}

# Opens PostgreSQL Admin (if pgAdmin is installed)
function run-pgadmin {
    Write-Host "[OPEN] Opening pgAdmin..." -ForegroundColor Cyan
    Start-Process "http://localhost:5050"
}

# === DATABASE COMMANDS ===

# Rolls back all database migrations
function db-rollback {
    pulse
    Write-Host "[DB] Rolling back all database migrations..." -ForegroundColor Red
    python .\services\backend-service\scripts\migration_runner.py --rollback-to 0000
}

# Applies all pending database migrations
function db-migrate {
    pulse
    Write-Host "[DB] Applying all pending database migrations..." -ForegroundColor Green
    python .\services\backend-service\scripts\migration_runner.py --apply-all
}

# Shows database migration status
function db-status {
    pulse
    Write-Host "[DB] Checking database migration status..." -ForegroundColor Cyan
    python .\services\backend-service\scripts\migration_runner.py --status
}

# Creates a new migration
function db-create-migration {
    param([string]$name)
    if (-not $name) {
        Write-Host "[ERROR] Please provide a migration name: db-create-migration 'migration_name'" -ForegroundColor Red
        return
    }
    pulse
    Write-Host "[DB] Creating new migration: $name" -ForegroundColor Green
    python .\services\backend-service\scripts\migration_runner.py --create $name
}

# === DEVELOPMENT UTILITIES ===

# Kill all project processes
function kill-all {
    Write-Host "[STOP] Stopping all Health Pulse processes..." -ForegroundColor Red
    Get-Process | Where-Object {$_.ProcessName -eq "python" -and ($_.CommandLine -like "*3001*" -or $_.CommandLine -like "*4000*")} | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process | Where-Object {$_.ProcessName -eq "node" -and ($_.CommandLine -like "*vite*" -or $_.CommandLine -like "*3000*" -or $_.CommandLine -like "*3333*")} | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "[SUCCESS] All processes stopped" -ForegroundColor Green
}

# Check what's running on common ports
function check-ports {
    Write-Host "[CHECK] Checking common Health Pulse ports..." -ForegroundColor Cyan
    $ports = @(3000, 3001, 3333, 4000, 5432, 6333, 15672)
    foreach ($port in $ports) {
        $connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($connection) {
            Write-Host "[OK] Port $port is in use" -ForegroundColor Green
        } else {
            Write-Host "[FREE] Port $port is free" -ForegroundColor Red
        }
    }
}

# Open project in VS Code
function code-pulse {
    pulse
    Write-Host "[CODE] Opening Health Pulse in VS Code..." -ForegroundColor Cyan
    code .
}

# Git status for all services
function git-status-all {
    pulse
    Write-Host "[GIT] Git status for Health Pulse project..." -ForegroundColor Cyan
    git status --short
}

# Show project structure
function pulse-tree {
    pulse
    Write-Host "[TREE] Health Pulse Project Structure:" -ForegroundColor Cyan
    tree /F /A services docs | Select-Object -First 50
}

# === MASTER COMMANDS ===

# Start All Services (New Windows)
function run-all {
    Write-Host "[START] Starting all servers in new windows..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "run-backend"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "run-auth"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "run-frontend"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "run-etl-frontend"
    Start-Sleep -Seconds 3
    run-qdrant
    run-rabbit
    Write-Host "[SUCCESS] All services started!" -ForegroundColor Green
}

# Start All Services (Windows Terminal Tabs)
function run-all-tabs {
    Write-Host "[START] Starting all servers in new tabs..." -ForegroundColor Cyan
    wt -w 0 new-tab --title "Backend"      powershell.exe -NoExit -Command "run-backend"
    wt -w 0 new-tab --title "Auth"         powershell.exe -NoExit -Command "run-auth"
    wt -w 0 new-tab --title "Frontend"     powershell.exe -NoExit -Command "run-frontend"
    wt -w 0 new-tab --title "ETL-Frontend" powershell.exe -NoExit -Command "run-etl-frontend"
    Start-Sleep -Seconds 3
    run-qdrant
    run-rabbit
    Write-Host "[SUCCESS] All services started in tabs!" -ForegroundColor Green
}

# Full development setup
function dev-setup {
    Write-Host "[SETUP] Setting up development environment..." -ForegroundColor Yellow

    # Check if all required tools are available
    $tools = @("python", "node", "npm", "git")
    foreach ($tool in $tools) {
        if (Get-Command $tool -ErrorAction SilentlyContinue) {
            Write-Host "[OK] $tool is available" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] $tool is not available" -ForegroundColor Red
        }
    }

    # Install dependencies
    Write-Host "[INSTALL] Installing Python dependencies..." -ForegroundColor Cyan
    pulse
    python scripts/install_requirements.py all

    Write-Host "[INSTALL] Installing Node.js dependencies..." -ForegroundColor Cyan
    pulse-frontend; npm install
    pulse-etl-frontend; npm install

    Write-Host "[SUCCESS] Development setup complete!" -ForegroundColor Green
}

# Quick health check
function pulse-health {
    Write-Host "[HEALTH] Health Pulse System Check..." -ForegroundColor Cyan
    check-ports
    Write-Host ""
    git-status-all
    Write-Host ""
    Write-Host "[STATUS] System Status:" -ForegroundColor Yellow
    Write-Host "Database: " -NoNewline
    if (Test-NetConnection localhost -Port 5432 -WarningAction SilentlyContinue -InformationLevel Quiet) {
        Write-Host "[OK] Running" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Not Running" -ForegroundColor Red
    }
    Write-Host "Redis: " -NoNewline
    if (Test-NetConnection localhost -Port 6379 -WarningAction SilentlyContinue -InformationLevel Quiet) {
        Write-Host "[OK] Running" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Not Running" -ForegroundColor Red
    }
    Write-Host "RabbitMQ: " -NoNewline
    if (Test-NetConnection localhost -Port 5672 -WarningAction SilentlyContinue -InformationLevel Quiet) {
        Write-Host "[OK] Running" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Not Running" -ForegroundColor Red
    }
}

# === QUICK ALIASES ===
Set-Alias -Name p -Value pulse
Set-Alias -Name pb -Value pulse-backend
Set-Alias -Name pf -Value pulse-frontend
Set-Alias -Name pe -Value pulse-etl-frontend
Set-Alias -Name rb -Value restart-backend
Set-Alias -Name dbr -Value db-rollback
Set-Alias -Name dbm -Value db-migrate
Set-Alias -Name rat -Value run-all-tabs

Write-Host "[SUCCESS] Health Pulse PowerShell functions loaded!" -ForegroundColor Green
Write-Host "[TIP] Try: pulse-health, run-all-tabs, restart-backend" -ForegroundColor Cyan
