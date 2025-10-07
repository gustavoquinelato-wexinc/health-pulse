# INSTALLATION & SETUP

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
- **4000**: Auth service
- **5173**: Frontend development server
- **5174**: ETL frontend
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

# 4. Start database and run migrations
docker-compose -f docker-compose.db.yml up -d
python services/backend-service/scripts/migration_runner.py --apply-all

# 5. Start all services
npm run dev:all
```

**What the setup script does:**
- ✅ Creates Python virtual environments for all services
- ✅ Installs all dependencies (FastAPI, pandas, numpy, websockets, etc.)
- ✅ Installs Node.js dependencies for frontend
- ✅ Copies `.env.example` files to `.env` for all services
- ✅ Cross-platform support (Windows, Linux, macOS)

## 🐳 Docker Deployment

### Production Deployment

```bash
# 1. Clone and configure
git clone <repository-url>
cd pulse-platform
cp .env.example .env
# Edit .env with production settings

# 2. Build and start all services
docker-compose up -d

# 3. Run database migrations
docker-compose exec backend python scripts/migration_runner.py --apply-all

# 4. Create initial admin user
docker-compose exec backend python scripts/create_admin_user.py
```

### Development with Docker

```bash
# Start only database services
docker-compose -f docker-compose.db.yml up -d

# Start individual services for development
docker-compose up backend etl-service
```

### Docker Configuration Files

- **docker-compose.yml**: Full production stack
- **docker-compose.db.yml**: Database services only
- **docker-compose.dev.yml**: Development overrides

## 🗄️ Database Setup

### PostgreSQL Configuration

#### Primary-Replica Setup

```yaml
# docker-compose.db.yml
services:
  postgres-primary:
    image: postgres:15
    environment:
      POSTGRES_DB: pulse_platform
      POSTGRES_USER: pulse_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_primary_data:/var/lib/postgresql/data
      - ./scripts/init-replica.sh:/docker-entrypoint-initdb.d/init-replica.sh

  postgres-replica:
    image: postgres:15
    environment:
      POSTGRES_DB: pulse_platform
      POSTGRES_USER: pulse_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      PGUSER: postgres
    ports:
      - "5433:5432"
    volumes:
      - postgres_replica_data:/var/lib/postgresql/data
    depends_on:
      - postgres-primary
```

#### Database Migrations

```bash
# Apply all migrations
python services/backend-service/scripts/migration_runner.py --apply-all

# Apply specific migration
python services/backend-service/scripts/migration_runner.py --apply 0001

# Rollback migration
python services/backend-service/scripts/migration_runner.py --rollback 0001

# Check migration status
python services/backend-service/scripts/migration_runner.py --status
```

### Redis Configuration

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  command: redis-server --appendonly yes
```

## ⚙️ Environment Configuration

### Core Environment Variables

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pulse_platform
DB_USER=pulse_user
DB_PASSWORD=your_secure_password

# Redis Configuration
REDIS_URL=redis://localhost:6379

# JWT Configuration
JWT_SECRET_KEY=your_jwt_secret_key
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24

# API Configuration
API_V1_STR=/api/v1
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]

# External Integrations
JIRA_BASE_URL=https://your-company.atlassian.net
GITHUB_API_URL=https://api.github.com

# AI Configuration
OPENAI_API_KEY=your_openai_api_key
EMBEDDING_MODEL=text-embedding-ada-002
```

### Service-Specific Configuration

#### Backend Service (.env)
```bash
# Service Configuration
SERVICE_NAME=backend-service
DEBUG=false
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://pulse_user:password@localhost:5432/pulse_platform
DATABASE_REPLICA_URL=postgresql://pulse_user:password@localhost:5433/pulse_platform

# Authentication
AUTH_SERVICE_URL=http://localhost:4000
```

#### ETL Service (.env)
```bash
# Service Configuration
SERVICE_NAME=etl-service
DEBUG=false
LOG_LEVEL=INFO

# Queue Configuration
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
QUEUE_NAME=etl_processing

# Integration APIs
JIRA_API_TOKEN=your_jira_token
GITHUB_TOKEN=your_github_token
```

#### Frontend (.env)
```bash
# API Endpoints
VITE_API_URL=http://localhost:3001
VITE_ETL_API_URL=http://localhost:8000
VITE_AUTH_URL=http://localhost:4000

# Feature Flags
VITE_ENABLE_AI_FEATURES=true
VITE_ENABLE_DARK_MODE=true
```

## 🔧 Service Configuration

### Backend Service Setup

```bash
cd services/backend-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run migrations
python scripts/migration_runner.py --apply-all

# Start service
uvicorn app.main:app --reload --port 3001
```

### ETL Service Setup

```bash
cd services/etl-service

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start service
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd services/frontend-app

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

### ETL Frontend Setup

```bash
cd services/etl-frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

## 🚀 Production Deployment

### Docker Swarm Deployment

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.prod.yml pulse-platform

# Scale services
docker service scale pulse-platform_backend=3
docker service scale pulse-platform_etl=2
```

### Kubernetes Deployment

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: pulse-platform

---
# k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend-service
  namespace: pulse-platform
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend-service
  template:
    metadata:
      labels:
        app: backend-service
    spec:
      containers:
      - name: backend
        image: pulse-platform/backend:latest
        ports:
        - containerPort: 3001
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
```

### Health Checks

```bash
# Service health endpoints
curl http://localhost:3001/health    # Backend Service
curl http://localhost:4000/health    # Auth Service
curl http://localhost:8000/health    # ETL Service (Legacy)

# Frontend applications
curl http://localhost:3000           # Frontend App
curl http://localhost:3333           # ETL Frontend

# Database and infrastructure
curl http://localhost:3001/health/db     # PostgreSQL connectivity
curl http://localhost:3001/health/redis # Redis connectivity
curl http://localhost:6333/health       # Qdrant vector database
curl http://localhost:15672             # RabbitMQ management UI
```

### Service Ports Reference

| Service | Port | Purpose |
|---------|------|---------|
| **Frontend App** | 3000 | Main React application |
| **ETL Frontend** | 3333 | ETL management interface |
| **Backend Service** | 3001 | Main API and business logic |
| **Auth Service** | 4000 | Authentication and authorization |
| **ETL Service** | 8000 | ⚠️ LEGACY - Reference only |
| **PostgreSQL Primary** | 5432 | Main database |
| **PostgreSQL Replica** | 5433 | Read replica |
| **Redis** | 6379 | Cache and sessions |
| **RabbitMQ AMQP** | 5672 | Message queue |
| **RabbitMQ Management** | 15672 | Queue management UI |
| **Qdrant HTTP** | 6333 | Vector database API |
| **Qdrant gRPC** | 6334 | Vector database gRPC |

## 🔍 Troubleshooting

### Common Issues

#### Port Conflicts
```bash
# Check port usage
netstat -tulpn | grep :3001

# Kill process using port
sudo kill -9 $(lsof -t -i:3001)
```

#### Database Connection Issues
```bash
# Test database connection
psql -h localhost -p 5432 -U pulse_user -d pulse_platform

# Check database logs
docker logs pulse-platform-postgres-primary-1
```

#### Permission Issues
```bash
# Fix file permissions
chmod +x scripts/*.sh
chmod +x scripts/*.py

# Fix directory permissions
chmod -R 755 logs/
```

### Log Analysis

```bash
# View service logs
docker-compose logs -f backend
docker-compose logs -f etl-service

# View specific log files
tail -f services/backend-service/logs/backend-service.log
tail -f services/etl-service/logs/etl-service.log
```

## 📋 Post-Installation Checklist

### Initial Setup
- [ ] Database migrations applied successfully
- [ ] Admin user created
- [ ] All services responding to health checks
- [ ] Redis cache operational
- [ ] Log files being created

### Security Configuration
- [ ] JWT secret keys configured
- [ ] Database passwords changed from defaults
- [ ] HTTPS certificates installed (production)
- [ ] Firewall rules configured
- [ ] Backup procedures established

### Integration Setup
- [ ] Jira API credentials configured
- [ ] GitHub API tokens configured
- [ ] AI service API keys configured
- [ ] Email service configured (if applicable)
- [ ] Monitoring alerts configured

---

**For additional support, refer to the troubleshooting section or contact the development team.**
