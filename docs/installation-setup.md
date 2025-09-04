# Installation & Setup Guide

**Complete Deployment & Configuration Guide**

This document provides step-by-step instructions for installing, configuring, and deploying the Pulse Platform in various environments.

## 🚀 Quick Start

### Prerequisites

#### System Requirements
- **Operating System**: Windows 10+, macOS 10.15+, or Linux (Ubuntu 18.04+)
- **Memory**: 8GB RAM minimum, 16GB recommended
- **Storage**: 10GB free space minimum
- **Network**: Internet connection for API integrations

#### Required Software
- **Docker**: Version 20.10+ with Docker Compose
- **Git**: Version 2.20+ for repository management
- **Python**: Version 3.11+ (for development setup)
- **Node.js**: Version 18+ (for frontend development)

#### Port Requirements
Ensure these ports are available:
- **3000**: Frontend application
- **3001**: Backend service API
- **8000**: ETL service
- **5432**: PostgreSQL primary database
- **5433**: PostgreSQL replica database
- **6379**: Redis cache

### ⚡ One-Command Development Setup

For fresh development environment setup:

```bash
# 1. Clone repository
git clone <repository-url>
cd pulse-platform

# 2. Complete development setup (ONE COMMAND!)
python scripts/setup_development.py

# 3. Configure environment files (automatically copied from .env.example files)
# Edit the root .env file with your settings
nano .env
# Edit service-specific .env files if needed
nano services/backend-service/.env
nano services/etl-service/.env
nano services/frontend-app/.env

# 4. Start database and run migrations
docker-compose -f docker-compose.db.yml up -d
python services/backend-service/scripts/migration_runner.py --apply-all

# 5. Start services (using root venv)
# Activate root virtual environment first: venv\Scripts\activate (Windows) or source venv/bin/activate (Unix)
# Backend: cd services/backend-service && python -m uvicorn app.main:app --reload --port 3001
# ETL: cd services/etl-service && python -m uvicorn app.main:app --reload --port 8000
# Frontend: cd services/frontend-app && npm run dev
```

**What `setup_development.py` does:**
- ✅ Creates Python virtual environments for all services (individual service venvs)
- ✅ Installs all Python dependencies (including pandas, numpy, websockets)
- ✅ Installs Node.js dependencies for frontend
- ✅ Copies `.env.example` to `.env` for all services (root + individual services)
- ✅ Cross-platform support (Windows, Linux, macOS)

**Recommended: Root Virtual Environment Setup**
For simplified dependency management and to avoid APScheduler import issues, use the root venv approach:
```bash
# Create and use single root virtual environment (RECOMMENDED)
python scripts/install_requirements.py all
```

**Note**: The root venv approach is now recommended as it resolves dependency conflicts and APScheduler import issues that can occur with individual service virtual environments.

### 🐳 Docker-Only Setup (Alternative)

For Docker-only deployment:

```bash
# 1. Clone repository
git clone <repository-url>
cd pulse-platform

# 2. Start database infrastructure
docker-compose -f docker-compose.db.yml up -d

# 3. Run database migrations
python services/backend-service/scripts/migration_runner.py --apply-all

# 4. Start all services
docker-compose up -d

# 5. Access the platform
# Frontend: http://localhost:3000
# ETL Management: http://localhost:8000/home
# API Documentation: http://localhost:3001/docs
```

## 🗄️ Database Setup

### Option A: Primary-Replica Architecture (Recommended)

#### Start Database Infrastructure
```bash
# Start PostgreSQL primary and replica
docker-compose -f docker-compose.db.yml up -d

# Verify both databases are running
docker ps | grep pulse-postgres
```

#### Verify Replication
```bash
# Check primary database
docker exec pulse-postgres-primary psql -U postgres -d pulse_db -c "SELECT 'PRIMARY' as db_type;"

# Check replica database
docker exec pulse-postgres-replica psql -U postgres -d pulse_db -c "SELECT 'REPLICA' as db_type, pg_is_in_recovery();"

# Monitor replication status
docker exec pulse-postgres-primary psql -U postgres -d pulse_db -c "SELECT * FROM pg_replication_slots;"
```

#### Run Migrations
```bash
# Apply all database migrations
python services/backend-service/scripts/migration_runner.py --apply-all

# Check migration status
python services/backend-service/scripts/migration_runner.py --status

# Rollback migrations if needed
python services/backend-service/scripts/migration_runner.py --rollback
```

### Option B: Single Database (Development)

#### Local PostgreSQL Setup
```bash
# Install PostgreSQL locally
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql

# Windows
# Download from https://www.postgresql.org/download/windows/
```

#### Database Configuration
```sql
-- Create database and user
CREATE DATABASE pulse_db;
CREATE USER pulse_user WITH PASSWORD 'pulse_password';
GRANT ALL PRIVILEGES ON DATABASE pulse_db TO pulse_user;
```

## 📦 Dependencies & Requirements

### Centralized Requirements Management

All Python dependencies are managed centrally in the `/requirements/` folder:

- **`common.txt`** - Shared dependencies (FastAPI, SQLAlchemy, etc.)
- **`backend-service.txt`** - Backend-specific dependencies (pandas, numpy, websockets)
- **`etl-service.txt`** - ETL-specific dependencies (APScheduler, Jira, websockets)
- **`auth-service.txt`** - Auth service dependencies (minimal JWT-only)

### Recently Added Dependencies

The following dependencies were added to fix missing imports:

**Backend Service:**
- `pandas` - Data processing and analytics
- `numpy` - Numerical computing
- `websockets` - Real-time WebSocket support

**ETL Service:**
- `websockets` - Real-time progress updates

### Installation Options

```bash
# Option 1: Complete setup (recommended for new developers)
python scripts/setup_development.py

# Option 2: Install all dependencies in root virtual environment (RECOMMENDED)
# This approach uses all-services.txt for consistent dependency management
python scripts/install_requirements.py all

# Option 3: Install specific service (creates individual service venv)
python scripts/install_requirements.py backend-service
python scripts/install_requirements.py etl-service
python scripts/install_requirements.py auth-service
```

### Root Virtual Environment (Recommended)

The platform now supports a **unified root virtual environment** approach for simplified dependency management:

**Benefits:**
- ✅ **Single venv**: One virtual environment for all services
- ✅ **Consistent versions**: No package conflicts between services
- ✅ **Easier maintenance**: Single requirements installation
- ✅ **Simplified activation**: Just activate root `venv/`

**Usage:**
```bash
# Install all dependencies in root venv
python scripts/install_requirements.py all

# Activate root virtual environment
# Windows
venv\Scripts\activate
# Unix/Linux/macOS
source venv/bin/activate

# Now all services use the same environment
cd services/backend-service && python -m uvicorn app.main:app --reload --port 3001
cd services/etl-service && python -m uvicorn app.main:app --reload --port 8000
```

## ⚙️ Service Configuration

### Environment Files Setup

**Note:** If you used `python scripts/setup_development.py`, all `.env` files are already created from their respective `.env.example` files.

#### Environment File Structure

The platform uses both centralized and service-specific configuration:

```bash
# Root configuration (shared settings)
.env                              # Main configuration file (includes integration credentials)

# Service-specific configuration
services/backend-service/.env     # Backend-specific settings
services/etl-service/.env         # ETL-specific settings (client-specific)
services/frontend-app/.env        # Frontend-specific settings
```

#### Configuration Priority

1. **Service-specific `.env`** - Takes priority for that service
2. **Root `.env`** - Fallback for shared settings (includes database, AI providers, integration credentials)
3. **Environment variables** - Override both files

**Important**: The root `.env` file now contains integration credentials (GitHub/Jira tokens) that are **only used during migration 0002** to encrypt and store them in the database. After migration, credentials are managed through the database integrations table.

#### Manual Setup (if not using setup script)
```bash
# Copy all .env.example files
cp .env.example .env
cp services/backend-service/.env.example services/backend-service/.env
cp services/etl-service/.env.example services/etl-service/.env
cp services/frontend-app/.env.example services/frontend-app/.env

# Edit each file with your configuration
nano .env
nano services/backend-service/.env
nano services/etl-service/.env
nano services/frontend-app/.env
```

**Backend .env Example:**
```env
# Database Configuration
DATABASE_URL=postgresql://postgres:pulse@localhost:5432/pulse_db
DATABASE_REPLICA_URL=postgresql://postgres:pulse@localhost:5433/pulse_db

# Auth Service URL (backend delegates all token ops)
AUTH_SERVICE_URL=http://localhost:4000

# Service URLs
ETL_SERVICE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

#### ETL Service Configuration
```bash
# Create ETL service environment file
cd services/etl-service
cp .env.example .env

# Edit .env with your client-specific configuration
nano .env
```

**ETL .env Example:**
```env
# Client Configuration
CLIENT_NAME=YourCompany

# Database Configuration
DATABASE_URL=postgresql://postgres:pulse@localhost:5432/pulse_db
DATABASE_REPLICA_URL=postgresql://postgres:pulse@localhost:5433/pulse_db

# API Credentials
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=admin@yourcompany.com
JIRA_API_TOKEN=your-jira-api-token

GITHUB_TOKEN=your-github-token
GITHUB_ORG=your-github-organization

# Service URLs
BACKEND_SERVICE_URL=http://localhost:3001
```

#### Frontend Configuration
```bash
# Create frontend environment file
cd services/frontend-app
cp .env.example .env

# Edit .env with service URLs
nano .env
```

**Frontend .env Example:**
```env
# API Endpoints
VITE_BACKEND_URL=http://localhost:3001
VITE_ETL_URL=http://localhost:8000

# Application Settings
VITE_APP_NAME=Pulse Platform
VITE_ENVIRONMENT=development

# Feature Flags
VITE_ENABLE_REAL_TIME=true
VITE_ENABLE_AI_FEATURES=true
VITE_ENABLE_DARK_MODE=true
```

## 🔑 API Integration Setup

### GitHub Integration

#### Create GitHub Personal Access Token
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Click "Generate new token (classic)"
3. Select scopes:
   - `repo` (Full control of private repositories)
   - `read:org` (Read org and team membership)
   - `read:user` (Read user profile data)
4. Copy the generated token

#### Configure GitHub Settings
```bash
# Add to ROOT .env file (used during migration 0002 only)
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# Organization is configured in the GitHub integration base_search field
# Example: "health-" for repositories containing "health"
```

### Jira Integration

#### Create Jira API Token
1. Go to Atlassian Account Settings → Security → API tokens
2. Click "Create API token"
3. Enter a label (e.g., "Pulse Platform")
4. Copy the generated token

#### Configure Jira Settings
```bash
# Add to ROOT .env file (used during migration 0002 only)
JIRA_URL=https://yourcompany.atlassian.net
JIRA_USERNAME=your-email@yourcompany.com
JIRA_TOKEN=ATATT3xFfGF0...

# Project filtering is configured in the Jira integration base_search field
# Example: "project in (PROJ1,PROJ2,PROJ3) AND labels = 'urgent'"
```

#### Test API Connections
```bash
# Test GitHub connection
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

# Test Jira connection
curl -u "$JIRA_EMAIL:$JIRA_API_TOKEN" "$JIRA_BASE_URL/rest/api/3/myself"
```

## 🚀 Service Deployment

### Development Deployment

#### Manual Service Startup (Development)

**Option A: Root Virtual Environment (Recommended)**

**Prerequisites:** Run `python scripts/install_requirements.py all` to set up root virtual environment.

```bash
# Activate root virtual environment once
# Windows
venv\Scripts\activate
# Unix/Linux/macOS
source venv/bin/activate

# Terminal 1: Backend Service
cd services/backend-service
python -m uvicorn app.main:app --reload --port 3001

# Terminal 2: ETL Service
cd services/etl-service
python -m uvicorn app.main:app --reload --port 8000

# Terminal 3: Frontend Application
cd services/frontend-app
npm run dev
```

**Option B: Individual Service Virtual Environments**

**Prerequisites:** Run `python scripts/setup_development.py` first to set up individual virtual environments.

```bash
# Terminal 1: Backend Service
cd services/backend-service
# Windows
venv\Scripts\activate
# Unix/Linux/macOS
source venv/bin/activate
uvicorn app.main:app --reload --port 3001

# Terminal 2: ETL Service
cd services/etl-service
# Windows
venv\Scripts\activate
# Unix/Linux/macOS
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3: Frontend Application
cd services/frontend-app
npm run dev
```

#### Alternative: Manual Setup Without Scripts

**Root Virtual Environment Approach (Recommended):**
```bash
# Install all Python dependencies in root venv
python scripts/install_requirements.py all

# Install frontend dependencies
cd services/frontend-app && npm install

# Then start services using Option A above
```

**Individual Service Approach:**
```bash
# Install individual service dependencies
python scripts/install_requirements.py backend-service
python scripts/install_requirements.py etl-service
python scripts/install_requirements.py auth-service

# Install frontend dependencies
cd services/frontend-app && npm install

# Then start services using Option B above
```

#### Docker Development
```bash
# Start all services with Docker
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Deployment

#### Docker Production Setup
```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Start production services
docker-compose -f docker-compose.prod.yml up -d

# Configure reverse proxy (nginx example)
sudo nano /etc/nginx/sites-available/pulse-platform
```

**Nginx Configuration Example:**
```nginx
server {
    listen 80;
    server_name pulse.yourcompany.com;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /api/ {
        proxy_pass http://localhost:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /etl/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 👥 Initial User Setup

### Create Admin User

#### Using Migration Script
```bash
# Run user creation migration
python services/backend-service/scripts/migration_runner.py --create-admin-user

# Or manually create user
python scripts/create_admin_user.py --email admin@yourcompany.com --password secure_password
```

#### Default Credentials
```
Email: admin@yourcompany.com
Password: pulse_admin_2024
Role: admin
```

**⚠️ Important: Change default password immediately after first login**

### Configure Client Settings

#### Access Admin Panel
1. Login to frontend: http://localhost:3000
2. Navigate to Settings → System Settings
3. Configure client-specific settings:
   - Company name and branding
   - Integration credentials
   - Job scheduling preferences
   - Theme and color preferences

## ⏰ Timezone Configuration

### **Important: UTC-First Approach**

The Pulse Platform uses **UTC for all database operations** to ensure consistency across timezones:

- **Database Storage**: All timestamps stored in UTC
- **PostgreSQL**: Configured with `timezone = 'UTC'`
- **Job Scheduling**: Use `SCHEDULER_TIMEZONE=UTC` in environment files
- **Display**: Frontend converts UTC to user's local timezone

**Critical Rules:**
- ✅ Always use `DateTimeHelper.now_utc()` for database operations
- ❌ Never use `datetime.now()` for database operations
- ✅ Convert to local timezone only for display purposes

## 🔧 System Verification

### Health Checks

#### Service Health
```bash
# Check service status
curl http://localhost:3001/health
curl http://localhost:8000/health

# Check database connectivity
docker exec pulse-postgres-primary psql -U postgres -d pulse_db -c "SELECT 1;"
```

#### Integration Testing
```bash
# Test ETL job functionality
cd services/etl-service
python scripts/test_jobs.py --test-connection

# Run sample data collection
python scripts/test_jobs.py --run-sample
```

### Performance Verification

#### Database Performance
```bash
# Check database performance
docker exec pulse-postgres-primary psql -U postgres -d pulse_db -c "
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size 
FROM pg_tables WHERE schemaname='public' 
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;
"
```

#### Service Performance
```bash
# Monitor resource usage
docker stats

# Check service logs for errors
docker-compose logs --tail=100 backend-service
docker-compose logs --tail=100 etl-service
```

## 🔒 Security Hardening

### Production Security Checklist

#### Environment Security
- [ ] Change all default passwords
- [ ] Use strong JWT secrets (32+ characters)
- [ ] Enable HTTPS/TLS in production
- [ ] Configure proper CORS origins
- [ ] Set up firewall rules
- [ ] Enable database SSL connections

#### API Security
- [ ] Rotate API tokens regularly
- [ ] Use least-privilege API permissions
- [ ] Enable API rate limiting
- [ ] Monitor for suspicious activity
- [ ] Set up security alerts

#### Database Security
- [ ] Use strong database passwords
- [ ] Enable database encryption at rest
- [ ] Configure database backups
- [ ] Set up database monitoring
- [ ] Restrict database network access

## 📊 Monitoring & Maintenance

### Log Management

#### Log Locations
```bash
# Service logs
docker-compose logs backend-service
docker-compose logs etl-service
docker-compose logs frontend-app

# Database logs
docker logs pulse-postgres-primary
docker logs pulse-postgres-replica
```

#### Log Rotation
```bash
# Configure log rotation
sudo nano /etc/logrotate.d/pulse-platform
```

### Backup Strategy

#### Database Backups
```bash
# Create database backup
docker exec pulse-postgres-primary pg_dump -U postgres pulse_db > backup_$(date +%Y%m%d).sql

# Automated backup script
#!/bin/bash
BACKUP_DIR="/backups/pulse-platform"
DATE=$(date +%Y%m%d_%H%M%S)
docker exec pulse-postgres-primary pg_dump -U postgres pulse_db > "$BACKUP_DIR/pulse_db_$DATE.sql"
```

#### Configuration Backups
```bash
# Backup configuration files
tar -czf config_backup_$(date +%Y%m%d).tar.gz services/*/\.env docker-compose*.yml
```

## 🆘 Troubleshooting

### Common Issues

#### Setup Script Issues
```bash
# If setup_development.py fails
python scripts/setup_development.py --skip-venv  # Skip venv creation
python scripts/setup_development.py --skip-frontend  # Skip frontend setup

# Check Python version (3.11+ required)
python --version

# Check Node.js version (18+ required)
node --version

# Manual fallback
python scripts/install_requirements.py all
cd services/frontend-app && npm install
```

#### Virtual Environment Issues
```bash
# Remove and recreate virtual environment
cd services/backend-service
rm -rf venv
python -m venv venv

# Windows activation
venv\Scripts\activate

# Unix/Linux/macOS activation
source venv/bin/activate

# Reinstall dependencies
pip install -r ../../requirements/backend-service.txt
```

#### Missing Dependencies
```bash
# If you get import errors for pandas, numpy, or websockets
cd services/backend-service
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install pandas numpy websockets

# Or reinstall all requirements
pip install -r ../../requirements/backend-service.txt
```

#### Service Won't Start
```bash
# Check port conflicts
netstat -tulpn | grep :3001

# Check Docker status
docker info

# View detailed logs
docker-compose logs --tail=50 service-name
```

#### Database Connection Issues
```bash
# Test database connectivity
docker exec pulse-postgres-primary psql -U postgres -d pulse_db -c "SELECT 1;"

# Check database configuration
grep DATABASE_URL services/*/\.env
```

#### API Integration Failures
```bash
# Test API credentials
cd services/etl-service
python scripts/test_jobs.py --test-connection

# Check API rate limits
curl -I -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit
```

#### Long-Running Job Timeouts
```bash
# If Jira/GitHub jobs timeout after processing large datasets (30k+ records)
# Adjust database connection pool settings in .env:
DB_POOL_RECYCLE=1800  # 30 minutes (from default 3600)

# Monitor job progress and use chunked processing
# Jobs automatically implement checkpoint recovery for large datasets
```

### Getting Help

#### Support Resources
- **Documentation**: Check all documentation in `/docs` folder
- **API Documentation**: http://localhost:3001/docs and http://localhost:8000/docs
- **Logs**: Always check service logs for detailed error information
- **Health Endpoints**: Use `/health` endpoints for service status

---

This installation guide provides everything needed to successfully deploy and configure the Pulse Platform in any environment.
