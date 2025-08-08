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
- **Python**: Version 3.8+ (for manual development)
- **Node.js**: Version 16+ (for frontend development)

#### Port Requirements
Ensure these ports are available:
- **3000**: Frontend application
- **3001**: Backend service API
- **8000**: ETL service
- **5432**: PostgreSQL primary database
- **5433**: PostgreSQL replica database
- **6379**: Redis cache

### 30-Second Setup (Docker)

```bash
# 1. Clone repository
git clone <repository-url>
cd pulse-platform

# 2. Start database infrastructure
docker-compose -f docker-compose.db.yml up -d

# 3. Run database migrations
python scripts/migration_runner.py

# 4. Start all services
docker-compose up -d

# 5. Access the platform
# Frontend: http://localhost:3000
# ETL Management: http://localhost:8000
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
python scripts/migration_runner.py

# Check migration status
python scripts/migration_runner.py --status
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

## ⚙️ Service Configuration

### Environment Files Setup

#### Backend Service Configuration
```bash
# Create backend service environment file
cd services/backend-service
cp .env.example .env

# Edit .env with your configuration
nano .env
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
# Add to ETL service .env file
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_ORG=your-organization-name
```

### Jira Integration

#### Create Jira API Token
1. Go to Atlassian Account Settings → Security → API tokens
2. Click "Create API token"
3. Enter a label (e.g., "Pulse Platform")
4. Copy the generated token

#### Configure Jira Settings
```bash
# Add to ETL service .env file
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=your-email@yourcompany.com
JIRA_API_TOKEN=ATATT3xFfGF0...
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

#### Manual Service Startup
```bash
# Terminal 1: Backend Service
cd services/backend-service
python -m uvicorn app.main:app --reload --port 3001

# Terminal 2: ETL Service
cd services/etl-service
python -m uvicorn app.main:app --reload --port 8000

# Terminal 3: Frontend Application
cd services/frontend-app
npm install
npm run dev
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
python scripts/migration_runner.py --create-admin-user

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

### Getting Help

#### Support Resources
- **Documentation**: Check all documentation in `/docs` folder
- **API Documentation**: http://localhost:3001/docs and http://localhost:8000/docs
- **Logs**: Always check service logs for detailed error information
- **Health Endpoints**: Use `/health` endpoints for service status

---

This installation guide provides everything needed to successfully deploy and configure the Pulse Platform in any environment.
