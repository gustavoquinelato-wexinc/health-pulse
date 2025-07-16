# Pulse Platform - Deployment Guide

This guide provides step-by-step instructions for deploying the complete Pulse Platform monorepo.

## 🏗️ Complete Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Kairus Platform                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │   Frontend App  │    │ Backend Service │    │   ETL Service   │        │
│  │   (React/Next)  │◄──►│     (BFF)       │◄──►│   (FastAPI)     │        │
│  │   Port: 3001    │    │   Port: 3000    │    │   Port: 8000    │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│                                 │                        │                 │
│                                 ▼                        ▼                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │   AI Service    │    │   PostgreSQL    │    │   Snowflake     │        │
│  │   (FastAPI)     │    │   (Backend DB)  │    │ (Data Warehouse)│        │
│  │   Port: 8001    │    │   Port: 5432    │    │   (External)    │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│           │                        │                        │              │
│           ▼                        ▼                        ▼              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │      Redis      │    │      Jira       │    │     GitHub      │        │
│  │    (Cache)      │    │ (Data Source)   │    │ (Data Source)   │        │
│  │   Port: 6379    │    │   (External)    │    │   (External)    │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 📁 Complete Directory Structure

```
pulse-platform/
├── README.md                          # Main project documentation
├── docker-compose.yml                 # Orchestration configuration
├── .env.example                       # Environment template
├── .gitignore                         # Git ignore rules
├── start-platform.sh                  # Linux/Mac startup script
├── start-platform.bat                 # Windows startup script
├── DEPLOYMENT.md                      # This deployment guide
└── services/
    ├── etl-service/                   # 🎯 PRIMARY FOCUS - Complete Implementation
    │   ├── app/
    │   │   ├── main.py                # FastAPI application
    │   │   ├── api/                   # API routes
    │   │   ├── core/                  # Core functionality
    │   │   ├── jobs/                  # ETL jobs
    │   │   ├── models/                # Database models
    │   │   └── schemas/               # Pydantic schemas
    │   ├── requirements.txt           # Python dependencies
    │   ├── Dockerfile                 # Container configuration
    │   ├── .env.example              # Environment template
    │   └── README.md                  # Service documentation
    ├── ai-service/                    # 🤖 Functional Skeleton
    │   ├── app/
    │   │   ├── main.py                # FastAPI application
    │   │   ├── api/                   # ML API endpoints
    │   │   ├── models/                # ML models
    │   │   └── services/              # AI services
    │   ├── requirements.txt           # Python dependencies
    │   ├── Dockerfile                 # Container configuration
    │   └── README.md                  # Service documentation
    ├── backend-service/               # 🔗 Functional Skeleton
    │   ├── src/
    │   │   ├── app.ts                 # Express application
    │   │   ├── server.ts              # Server entry point
    │   │   ├── routes/                # API routes
    │   │   ├── controllers/           # Route controllers
    │   │   ├── middleware/            # Express middleware
    │   │   └── services/              # Business logic
    │   ├── package.json               # Node.js dependencies
    │   ├── Dockerfile                 # Container configuration
    │   └── README.md                  # Service documentation
    └── frontend-app/                  # 🎨 Functional Skeleton
        ├── src/
        │   ├── app/                   # Next.js App Router
        │   ├── components/            # React components
        │   ├── lib/                   # Utilities
        │   └── styles/                # CSS styles
        ├── package.json               # Node.js dependencies
        ├── Dockerfile                 # Container configuration
        └── README.md                  # Service documentation
```

## 🚀 Quick Start Deployment

### Prerequisites

1. **Docker & Docker Compose** installed
2. **Git** for cloning the repository
3. **Snowflake account** with database access
4. **Jira instance** with API access
5. **GitHub token** (optional)

### Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd pulse-platform

# Copy environment template
cp .env.example .env

# Edit environment file with your credentials
nano .env  # or use your preferred editor
```

### Step 2: Configure Environment

Edit `.env` file with your actual values:

```bash
# Required Snowflake Configuration
SNOWFLAKE_ACCOUNT=your_account.region
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_SCHEMA=your_schema
SNOWFLAKE_WAREHOUSE=your_warehouse

# Required Jira Configuration
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your_email@domain.com
JIRA_TOKEN=your_api_token

# Generate secure keys for production
ETL_SECRET_KEY=your-secure-secret-key
ETL_ENCRYPTION_KEY=your-32-byte-encryption-key
BACKEND_JWT_SECRET=your-jwt-secret
```

### Step 3: Start the Platform

**Option A: Using the startup script (Recommended)**

```bash
# Linux/Mac
chmod +x start-platform.sh
./start-platform.sh start

# Windows
start-platform.bat start
```

**Option B: Using Docker Compose directly**

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

### Step 4: Verify Deployment

Access the services:

- **Frontend Dashboard**: http://localhost:3001
- **Backend API**: http://localhost:3000
- **ETL Service**: http://localhost:8000
- **AI Service**: http://localhost:8001

API Documentation:
- **ETL API Docs**: http://localhost:8000/docs
- **AI API Docs**: http://localhost:8001/docs
- **Backend API Docs**: http://localhost:3000/api-docs

## 🔧 Individual Service Deployment

### ETL Service Only (Primary Focus)

```bash
# Start ETL service with dependencies
./start-platform.sh start etl

# Or with docker-compose
docker-compose up -d etl-service redis postgres
```

### AI Service Only

```bash
./start-platform.sh start ai
```

### Backend Service Only

```bash
./start-platform.sh start backend
```

### Frontend App Only

```bash
./start-platform.sh start frontend
```

## 📊 Monitoring and Management

### Check Service Status

```bash
# Using startup script
./start-platform.sh status

# Using docker-compose
docker-compose ps
```

### View Logs

```bash
# All services
./start-platform.sh logs

# Specific service
./start-platform.sh logs etl
docker-compose logs -f etl-service
```

### Stop Services

```bash
# Stop all
./start-platform.sh stop

# Or with docker-compose
docker-compose down
```

## 🔐 Security Configuration

### Production Security Checklist

- [ ] Generate unique secret keys for each service
- [ ] Configure proper CORS origins
- [ ] Set up SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Set up monitoring and alerting
- [ ] Configure backup strategies
- [ ] Review and update default passwords

### Environment Security

```bash
# Generate secure keys
openssl rand -hex 32  # For SECRET_KEY
openssl rand -hex 16  # For ENCRYPTION_KEY
```

## 🧪 Testing the Deployment

### Health Checks

```bash
# Test all service health endpoints
curl http://localhost:8000/health  # ETL Service
curl http://localhost:8001/health  # AI Service
curl http://localhost:3000/health  # Backend Service
curl http://localhost:3001         # Frontend App
```

### ETL Service Test

```bash
# Test Jira extraction (requires configuration)
curl -X POST http://localhost:8000/api/v1/etl/jira/extract \
  -H "Content-Type: application/json" \
  -d '{"project_key": "TEST"}'
```

## 🚨 Troubleshooting

### Common Issues

1. **Docker not running**
   ```bash
   # Start Docker service
   sudo systemctl start docker  # Linux
   # Or start Docker Desktop on Windows/Mac
   ```

2. **Port conflicts**
   ```bash
   # Check what's using the ports
   netstat -tulpn | grep :8000
   # Kill conflicting processes or change ports in docker-compose.yml
   ```

3. **Environment variables not loaded**
   ```bash
   # Verify .env file exists and has correct format
   cat .env
   # Restart services after changing .env
   docker-compose down && docker-compose up -d
   ```

4. **Snowflake connection issues**
   - Verify account name format: `account.region`
   - Check user permissions
   - Ensure warehouse is running
   - Test connection manually

5. **Jira authentication issues**
   - Verify API token is valid
   - Check username format (should be email)
   - Ensure Jira URL is correct

### Log Analysis

```bash
# Check specific service logs
docker-compose logs etl-service | grep ERROR
docker-compose logs ai-service | grep WARNING
```

## 📈 Scaling and Performance

### Horizontal Scaling

```bash
# Scale specific services
docker-compose up -d --scale etl-service=2
docker-compose up -d --scale ai-service=3
```

### Resource Limits

Edit `docker-compose.yml` to add resource limits:

```yaml
services:
  etl-service:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

## 🔄 Updates and Maintenance

### Updating Services

```bash
# Pull latest images
docker-compose pull

# Restart with new images
docker-compose down && docker-compose up -d
```

### Backup Strategies

- Database backups (PostgreSQL)
- Configuration backups (.env files)
- Model backups (AI service models)
- Log archival

---

**🎉 Congratulations! Your Pulse Platform is now deployed and ready for software engineering intelligence!**
