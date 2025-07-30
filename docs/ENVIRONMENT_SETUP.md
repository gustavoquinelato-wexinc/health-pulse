# 🔒 Environment Configuration Guide

This guide explains the new service-specific environment configuration that follows security best practices and the principle of least privilege.

## 🎯 **Architecture Overview**

### **Before: Shared Environment (Security Risk)**
```
❌ All services shared one .env file
❌ ETL service had access to JWT secrets
❌ Backend service had access to API tokens
❌ Frontend had access to server secrets
❌ Large security blast radius
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
├── .env.shared              # 🔒 Shared config (DB, URLs) - NO secrets
├── .env.backend             # 🔒 Backend secrets (JWT, sessions)
├── .env.etl.wex            # 🔒 WEX-specific ETL secrets
├── .env.etl.techcorp       # 🔒 TechCorp-specific ETL secrets
├── .env.frontend           # 🔒 Frontend config (public only)
├── docker-compose.dev.yml   # Development environment
├── docker-compose.multi-client.yml  # Multi-instance production
└── services/
    ├── backend-service/
    ├── etl-service/
    └── frontend-app/
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
BACKEND_SERVICE_URL=http://localhost:3002
ETL_SERVICE_URL=http://localhost:8000

# Service URLs
BACKEND_SERVICE_URL=http://localhost:3002
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
VITE_API_BASE_URL=http://localhost:3002
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

## 🔄 **Migration Runner & Scripts**

### **Environment File Requirements**

The migration runner and other root-level scripts require a **combined environment file** in the root directory:

```bash
# Create combined environment file for migration runner
cat .env.shared .env.etl.wex > .env

# Run migrations
python scripts/migration_runner.py

# Check migration status
python scripts/migration_runner.py --status

# Rollback to specific migration
python scripts/migration_runner.py --rollback-to 001
```

### **Why Combined Environment File is Needed**

1. **Migration Runner**: Uses ETL service configuration classes that expect all variables in one file
2. **Database Scripts**: Need both shared database config and client-specific settings
3. **Cross-Service Scripts**: Require access to multiple service configurations

### **Manual Service Execution**

Each service needs its own combined environment file:

```bash
# ETL Service (WEX client)
cd services/etl-service
cat ../../.env.shared ../../.env.etl.wex > .env
python -m uvicorn app.main:app --reload

# Backend Service
cd services/backend-service
cat ../../.env.shared ../../.env.backend > .env
python -m uvicorn app.main:app --reload
```

### **Docker vs Manual Execution**

| Method | Environment Handling | Use Case |
|--------|---------------------|----------|
| **Docker Compose** | Automatically combines env files | Production, testing |
| **Manual Execution** | Requires manual file combination | Development, debugging |
| **Migration Runner** | Needs combined `.env` in root | Database operations |

## ⚠️ **Important Notes**

### **Never Commit Secret Files**
Add to `.gitignore`:
```
.env.backend
.env.etl*
.env.production*
```

### **Keep Shared Config Safe**
`.env.shared` is safe to commit (no secrets)

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
