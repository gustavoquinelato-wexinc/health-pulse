# 🔒 Environment Configuration Guide

This guide explains the service-specific environment configuration that follows security best practices and the principle of least privilege. Each service now has its own complete `.env` file with only the configuration it needs.

## 🎯 **Architecture Overview**

### **Current: Service-Specific Environment (Secure)**
```
✅ Each service has its own complete .env file
✅ ETL service only has access to its required configuration
✅ Backend service only has access to its required configuration
✅ Frontend service only has access to its required configuration
✅ Minimal security blast radius
✅ No shared or combined environment files needed
```

### **After: Service-Specific Environments (Secure)**
```
✅ Each service gets only the secrets it needs
✅ Shared configuration in .env.shared
✅ Service-specific secrets in separate files
✅ Minimal security blast radius
✅ Production-ready architecture
```

## 📁 **File Structure**

```
pulse-platform/
├── .env.shared              # 🔒 Shared config (DB, Redis, URLs) - NO secrets
├── .env.backend             # 🔒 Backend secrets (JWT, sessions)
├── .env.frontend            # 🔒 Frontend config (public only)
├── .env.etl.wex            # 🔒 WEX-specific ETL secrets & API tokens
├── .env.etl.techcorp       # 🔒 TechCorp-specific ETL secrets & API tokens
├── .env.etl.acme           # 🔒 ACME-specific ETL secrets & API tokens
├── .env.shared.example      # ✅ Template for shared config
├── .env.backend.example     # ✅ Template for backend secrets
├── .env.frontend.example    # ✅ Template for frontend config
├── .env.etl.example         # ✅ Template for client-specific ETL config
├── docker-compose.dev.yml   # Development environment
├── docker-compose.multi-client.yml  # Multi-instance production
└── services/
    ├── backend-service/     # Authentication & API hub
    ├── etl-service/         # Data processing & job orchestration
    └── frontend-app/        # User interface
```

## 🔧 **Environment File Breakdown**

### **`.env.shared` - Shared Configuration**
```bash
# Database settings (shared across all services and clients)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=pulse
POSTGRES_DATABASE=pulse_db

# Redis settings
REDIS_HOST=localhost
REDIS_PORT=6379

# Service URLs (for inter-service communication)
BACKEND_SERVICE_URL=http://localhost:3001
ETL_SERVICE_URL=http://localhost:8000

# Service URLs
BACKEND_SERVICE_URL=http://localhost:3001
ETL_SERVICE_URL=http://localhost:8000

# 🔒 SECURITY: Contains NO secrets
```

### **`.env.backend` - Backend Secrets Only**
```bash
# JWT secrets (Backend manages all authentication)
JWT_SECRET_KEY=backend-jwt-secret
SESSION_SECRET_KEY=backend-session-secret

# 🔒 SECURITY: Only Backend Service accesses these
```

### **`.env.etl.wex` - WEX ETL Secrets Only**
```bash
# Client configuration
CLIENT_NAME=WEX

# API token encryption
ENCRYPTION_KEY=etl-encryption-key

# WEX-specific API credentials
JIRA_TOKEN=wex-jira-api-token
GITHUB_TOKEN=wex-github-api-token

# 🔒 SECURITY: Only WEX ETL instance accesses these
```

### **`.env.frontend` - Public Configuration Only**
```bash
# Public configuration (exposed to browser)
VITE_API_BASE_URL=http://localhost:3001
VITE_APP_TITLE=Pulse Platform

# 🔒 SECURITY: NO secrets in this file
```

## 🚀 **Usage Instructions**

### **Development Environment**
```bash
# Single ETL instance for development
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

### **Multi-Instance Production**
```bash
# Multiple ETL instances (one per client)
docker-compose -f docker-compose.multi-client.yml up -d

# View logs
docker-compose -f docker-compose.multi-client.yml logs -f
```

### **Manual Local Development**
```bash
# Automated setup
./start-multi-instance.sh

# Manual setup (WEX client)
cat .env.shared .env.etl.wex > services/etl-service/.env
cd services/etl-service
python -m uvicorn app.main:app --port 8000

# Manual setup (TechCorp client)
cat .env.shared .env.etl.techcorp > services/etl-service/.env
cd services/etl-service
python -m uvicorn app.main:app --port 8001
```

## 🔒 **Security Benefits**

### **Principle of Least Privilege**
- **Backend Service**: Only gets JWT and session secrets
- **ETL Service**: Only gets API tokens and encryption keys
- **Frontend**: Only gets public configuration
- **No cross-service secret access**

### **Reduced Blast Radius**
- Compromised ETL service ≠ JWT secrets exposed
- Compromised Backend ≠ API tokens exposed
- Compromised Frontend ≠ server secrets exposed

### **Production Ready**
- Container orchestration friendly
- Kubernetes secrets compatible
- CI/CD pipeline ready
- Secret rotation friendly

## 🐳 **Container Deployment**

### **Docker Compose Pattern**
```yaml
services:
  backend:
    env_file:
      - .env.shared      # Shared config
      - .env.backend     # Backend secrets only
  
  etl-wex:
    env_file:
      - .env.shared      # Shared config
      - .env.etl.wex     # WEX ETL secrets only

  etl-techcorp:
    env_file:
      - .env.shared      # Shared config
      - .env.etl.techcorp # TechCorp ETL secrets only
```

### **Kubernetes Secrets Pattern**
```yaml
# backend-secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: backend-secrets
data:
  JWT_SECRET_KEY: <base64>

# etl-wex-secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: etl-wex-secrets
data:
  ENCRYPTION_KEY: <base64>
  JIRA_TOKEN: <base64>

# etl-techcorp-secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: etl-techcorp-secrets
data:
  ENCRYPTION_KEY: <base64>
  JIRA_TOKEN: <base64>
```

## 🔄 **Migration Runner & Database Scripts**

### **New Location and Approach**

The migration system has been moved to the backend service for better architectural alignment:

```bash
# Run migrations from backend service
cd services/backend-service
python scripts/migration_runner.py --status

# Apply all pending migrations
python scripts/migration_runner.py --apply-all

# Rollback to specific migration
python scripts/migration_runner.py --rollback-to 001

# Create new migration
python scripts/migration_runner.py --new "Add new feature"
```

### **Why Backend Service Hosts Migrations**

1. **Database Ownership**: Backend service manages database schema and connections
2. **Service-Specific Config**: Uses backend service's own .env file (no combination needed)
3. **Architectural Alignment**: Database operations belong with the database service
4. **Security**: No need for cross-service configuration access

### **Service Execution**

Each service runs independently with its own complete environment file:

```bash
# ETL Service
cd services/etl-service
python -m uvicorn app.main:app --reload

# Backend Service
cd services/backend-service
python -m uvicorn app.main:app --reload

# Frontend Service
cd services/frontend-app
npm run dev
```

### **Environment File Structure**

| Service | Environment File | Contains |
|---------|-----------------|----------|
| **Backend Service** | `services/backend-service/.env` | Database config, JWT secrets, CORS settings |
| **ETL Service** | `services/etl-service/.env` | Client config, API tokens, database config |
| **Frontend Service** | `services/frontend-app/.env` | Service URLs, feature flags |

## ⚠️ **Important Notes**

### **Never Commit Secret Files**
Add to `.gitignore`:
```
services/backend-service/.env
services/etl-service/.env
services/frontend-app/.env
```

### **Example Files Are Safe**
`.env.example` files in each service are safe to commit (no secrets)

### **Production Deployment**
- Use proper secret management (Kubernetes secrets, AWS Secrets Manager, etc.)
- Rotate secrets regularly
- Monitor secret access
- Use different secrets per environment

## 🧪 **Testing**

```bash
# Test environment setup
python test_client_isolation_security.py

# Test multi-instance setup
python test_per_client_orchestrators.py

# Expected: All services start with correct secrets only
```
