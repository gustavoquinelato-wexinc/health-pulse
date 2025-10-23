#!/usr/bin/env pwsh
# Health Pulse Services Restart Script
# This script cleanly stops and restarts all services

Write-Host "🔄 Health Pulse Services Restart Script" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

# Function to kill processes by name
function Stop-ServiceProcesses {
    param([string]$ProcessName, [string]$ServiceName)
    
    Write-Host "🛑 Stopping $ServiceName processes..." -ForegroundColor Yellow
    
    $processes = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue
    if ($processes) {
        foreach ($process in $processes) {
            Write-Host "  Killing process $($process.Id) ($ProcessName)" -ForegroundColor Red
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 2
    } else {
        Write-Host "  No $ProcessName processes found" -ForegroundColor Green
    }
}

# Function to check if port is available
function Test-Port {
    param([int]$Port)
    
    try {
        $connection = New-Object System.Net.Sockets.TcpClient
        $connection.Connect("localhost", $Port)
        $connection.Close()
        return $true
    } catch {
        return $false
    }
}

# Step 1: Stop all services
Write-Host "`n📋 Step 1: Stopping all services..." -ForegroundColor Cyan

# Stop Python processes (backend, auth, workers)
Stop-ServiceProcesses -ProcessName "python" -ServiceName "Python Services"

# Stop Node.js processes (frontend)
Stop-ServiceProcesses -ProcessName "node" -ServiceName "Node.js Services"

# Wait for processes to fully stop
Write-Host "⏳ Waiting for processes to stop..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Step 2: Check ports are free
Write-Host "`n📋 Step 2: Checking ports..." -ForegroundColor Cyan

$ports = @(3000, 3001, 3333, 4000)
foreach ($port in $ports) {
    if (Test-Port -Port $port) {
        Write-Host "  ❌ Port $port is still in use" -ForegroundColor Red
    } else {
        Write-Host "  ✅ Port $port is available" -ForegroundColor Green
    }
}

# Step 3: Start services in order
Write-Host "`n📋 Step 3: Starting services..." -ForegroundColor Cyan

# Start Auth Service first
Write-Host "🚀 Starting Auth Service (port 4000)..." -ForegroundColor Green
Start-Process -FilePath "powershell" -ArgumentList "-Command", "cd 'services/auth-service'; python -m uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload" -WindowStyle Minimized

Start-Sleep -Seconds 3

# Start Backend Service
Write-Host "🚀 Starting Backend Service (port 3001)..." -ForegroundColor Green
Start-Process -FilePath "powershell" -ArgumentList "-Command", "cd 'services/backend-service'; python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload" -WindowStyle Minimized

Start-Sleep -Seconds 5

# Start Frontend Service
Write-Host "🚀 Starting Frontend Service (port 3000)..." -ForegroundColor Green
Start-Process -FilePath "powershell" -ArgumentList "-Command", "cd 'services/frontend-app'; npm run dev" -WindowStyle Minimized

Start-Sleep -Seconds 3

# Start ETL Frontend Service
Write-Host "🚀 Starting ETL Frontend Service (port 3333)..." -ForegroundColor Green
Start-Process -FilePath "powershell" -ArgumentList "-Command", "cd 'services/etl-frontend'; npm run dev" -WindowStyle Minimized

Start-Sleep -Seconds 5

# Step 4: Health checks
Write-Host "`n📋 Step 4: Health checks..." -ForegroundColor Cyan

$services = @(
    @{Name="Auth Service"; Port=4000; Endpoint="/health"},
    @{Name="Backend Service"; Port=3001; Endpoint="/health"},
    @{Name="Frontend Service"; Port=3000; Endpoint="/"},
    @{Name="ETL Frontend Service"; Port=3333; Endpoint="/"}
)

foreach ($service in $services) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$($service.Port)$($service.Endpoint)" -TimeoutSec 10 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host "  ✅ $($service.Name) is healthy" -ForegroundColor Green
        } else {
            Write-Host "  ❌ $($service.Name) returned status $($response.StatusCode)" -ForegroundColor Red
        }
    } catch {
        Write-Host "  ❌ $($service.Name) is not responding" -ForegroundColor Red
    }
}

Write-Host "`n🎉 Service restart complete!" -ForegroundColor Cyan
Write-Host "📝 Services should be available at:" -ForegroundColor White
Write-Host "   - Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "   - ETL Frontend: http://localhost:3333" -ForegroundColor White
Write-Host "   - Backend API: http://localhost:3001" -ForegroundColor White
Write-Host "   - Auth Service: http://localhost:4000" -ForegroundColor White
