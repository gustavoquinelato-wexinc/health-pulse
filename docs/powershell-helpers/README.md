# PowerShell Helpers for Health Pulse

This directory contains PowerShell utilities to streamline Health Pulse development workflow.

## 📁 Files

- **`powershell-profile.ps1`** - Complete PowerShell functions to copy into your `$PROFILE`

## 🚀 Quick Setup

### 1. Install PowerShell Functions
```powershell
# Open your PowerShell profile
notepad $PROFILE

# Copy ALL content from: docs/powershell-helpers/powershell-profile.ps1
# Paste into your $PROFILE and save

# Reload your profile
. $PROFILE
```

### 2. Verify Installation
```powershell
pulse-health    # Should show system status
pulse          # Should navigate to project root
```

---

## 🚀 Essential Commands

| Command | Description |
|---------|-------------|
| `pulse` | Go to project root |
| `run-all-tabs` | Start all services in tabs |
| `kill-all` | Stop all services |
| `pulse-health` | System health check |
| `restart-backend` | Restart backend service |

## 📁 Navigation

| Command | Directory |
|---------|-----------|
| `pulse` | Project root |
| `pulse-backend` | Backend service |
| `pulse-frontend` | Frontend app |
| `pulse-etl-frontend` | ETL frontend |

| `pulse-auth` | Auth service |

## 🖥️ Services

| Command | Service | Port |
|---------|---------|------|
| `run-backend` | Backend API | 3001 |
| `run-auth` | Auth Service | 4000 |

| `run-frontend` | Frontend App | 3000 |
| `run-etl-frontend` | ETL Frontend | 3333 |

## 🗄️ Database

| Command | Action |
|---------|--------|
| `db-migrate` | Apply migrations |
| `db-rollback` | Rollback all |
| `db-status` | Check status |
| `db-create-migration "name"` | Create new migration |

## 🔧 Utilities

| Command | Purpose |
|---------|---------|
| `check-ports` | Check port usage |
| `code-pulse` | Open in VS Code |
| `git-status-all` | Git status |
| `dev-setup` | Setup environment |

## 🌐 External Services

| Command | Service | URL |
|---------|---------|-----|
| `run-qdrant` | Qdrant Dashboard | localhost:6333 |
| `run-rabbit` | RabbitMQ Management | localhost:15672 |
| `run-pgadmin` | PostgreSQL Admin | localhost:5050 |

---

## 🔧 Troubleshooting

### PowerShell Profile Issues
```powershell
# If you get syntax errors when loading profile:
# 1. Check file encoding (should be UTF-8)
# 2. Remove any emoji characters if they cause issues
# 3. Use the clean version: powershell-profile.ps1

# Test profile syntax before loading:
Get-Content $PROFILE | Out-String | Invoke-Expression
```

### Common Workflow Issues
```powershell
# Backend won't restart properly:
restart-backend    # Kills and restarts cleanly

# Check what's using ports:
check-ports       # Shows all Health Pulse ports

# Services won't start:
kill-all          # Stop everything first
run-all-tabs      # Start fresh
```

---

## 📚 Daily Workflow Examples

### Morning Startup
```powershell
pulse-health      # Check system status
run-all-tabs      # Start all services
```

### Development Cycle
```powershell
# Make backend changes
restart-backend   # Quick restart

# Check status
check-ports      # Verify services running
```

### End of Day
```powershell
kill-all         # Stop all services cleanly
```

---

## 🎯 Quick Aliases

- **`p`** = `pulse` (go to project root)
- **`pb`** = `pulse-backend` (go to backend)
- **`pf`** = `pulse-frontend` (go to frontend)
- **`pe`** = `pulse-etl-frontend` (go to ETL frontend)
- **`rb`** = `restart-backend` (restart backend service)

---

*Health Pulse Development Team | 2025*
