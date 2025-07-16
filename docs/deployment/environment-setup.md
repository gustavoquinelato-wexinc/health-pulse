# Environment Setup and Configuration

## 🎯 Environment Overview

The Pulse Platform supports multiple deployment environments with specific configurations:

- **Development**: Local development with debugging enabled
- **Testing**: Automated testing environment
- **Staging**: Pre-production testing environment
- **Production**: Live production environment

## 🔧 Environment Configuration

### **Configuration Hierarchy**

```
Environment Variables (Highest Priority)
    ↓
.env.{environment} Files
    ↓
.env File
    ↓
Default Values (Lowest Priority)
```

### **Environment Files Structure**

```
pulse-platform/
├── .env.example                 # Template for all environments
├── .env.development            # Development-specific settings
├── .env.testing                # Testing environment settings
├── .env.staging                # Staging environment settings
├── .env.production             # Production environment settings
└── services/
    ├── etl-service/
    │   ├── .env.example
    │   ├── .env.development
    │   └── .env.production
    ├── backend-service/
    │   └── .env.example
    └── frontend-service/
        └── .env.example
```

## 🛠️ Development Environment

### **Prerequisites**
- Python 3.11+
- Node.js 18+
- PostgreSQL 12+
- Git
- Docker (optional)

### **Development Configuration**

#### **.env.development**
```bash
# Application Settings
DEBUG=true
LOG_LEVEL=DEBUG
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8000

# Database (Local PostgreSQL)
DATABASE_URL=postgresql://pulse_user:pulse_password@localhost:5432/pulse_dev

# Integrations (Development/Sandbox)
JIRA_BASE_URL=https://your-dev-domain.atlassian.net
JIRA_EMAIL=dev-user@company.com
JIRA_API_TOKEN=dev-api-token

GITHUB_TOKEN=dev-github-token

# Development Features
ENABLE_DEBUG_TOOLBAR=true
ENABLE_PROFILING=true
MOCK_EXTERNAL_APIS=false

# Cache (Optional for development)
REDIS_URL=redis://localhost:6379/0

# Security (Development keys)
SECRET_KEY=dev-secret-key-not-for-production
ENCRYPTION_KEY=dev-encryption-key-32-bytes-long

# Job Configuration
ORCHESTRATOR_INTERVAL_MINUTES=5  # Faster for development
```

### **Development Setup Script**

#### **setup-dev.sh**
```bash
#!/bin/bash
# Development environment setup script

set -e

echo "Setting up Pulse Platform development environment..."

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required"; exit 1; }
command -v psql >/dev/null 2>&1 || { echo "PostgreSQL is required"; exit 1; }

# Setup ETL Service
echo "Setting up ETL Service..."
cd services/etl-service

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env.development
echo "Please edit services/etl-service/.env.development with your configuration"

# Setup database
echo "Setting up database..."
python scripts/reset_database.py

# Setup Backend Service (when available)
echo "Backend Service setup will be added when implemented"

# Setup Frontend Service (when available)
echo "Frontend Service setup will be added when implemented"

echo "Development environment setup complete!"
echo "Start ETL service with: cd services/etl-service && python -m uvicorn app.main:app --reload"
```

## 🧪 Testing Environment

### **Testing Configuration**

#### **.env.testing**
```bash
# Application Settings
DEBUG=false
LOG_LEVEL=WARNING
ENVIRONMENT=testing
HOST=0.0.0.0
PORT=8000

# Test Database (Isolated)
DATABASE_URL=postgresql://test_user:test_password@localhost:5432/pulse_test

# Mock Integrations
JIRA_BASE_URL=https://mock-jira.example.com
JIRA_EMAIL=test@example.com
JIRA_API_TOKEN=mock-token

GITHUB_TOKEN=mock-github-token

# Testing Features
MOCK_EXTERNAL_APIS=true
ENABLE_TEST_FIXTURES=true
DISABLE_RATE_LIMITING=true

# Fast execution for tests
ORCHESTRATOR_INTERVAL_MINUTES=1

# Test Security Keys
SECRET_KEY=test-secret-key
ENCRYPTION_KEY=test-encryption-key-32-bytes-long
```

### **Test Database Setup**

#### **setup-test-db.sh**
```bash
#!/bin/bash
# Test database setup

# Create test database
createdb pulse_test -U postgres

# Run migrations
cd services/etl-service
python scripts/reset_database.py --environment=testing

# Load test fixtures
python scripts/load_test_fixtures.py
```

### **CI/CD Configuration**

#### **.github/workflows/test.yml**
```yaml
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test_password
          POSTGRES_USER: test_user
          POSTGRES_DB: pulse_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        cd services/etl-service
        pip install -r requirements.txt
    
    - name: Run tests
      env:
        DATABASE_URL: postgresql://test_user:test_password@localhost:5432/pulse_test
      run: |
        cd services/etl-service
        python -m pytest tests/ -v --cov=app
```

## 🚀 Staging Environment

### **Staging Configuration**

#### **.env.staging**
```bash
# Application Settings
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=staging
HOST=0.0.0.0
PORT=8000

# Staging Database
DATABASE_URL=postgresql://staging_user:${STAGING_DB_PASSWORD}@staging-db:5432/pulse_staging

# Staging Integrations (Sandbox/Test instances)
JIRA_BASE_URL=https://staging-domain.atlassian.net
JIRA_EMAIL=${STAGING_JIRA_EMAIL}
JIRA_API_TOKEN=${STAGING_JIRA_TOKEN}

GITHUB_TOKEN=${STAGING_GITHUB_TOKEN}

# Staging Features
ENABLE_PERFORMANCE_MONITORING=true
ENABLE_ERROR_TRACKING=true

# Cache
REDIS_URL=redis://staging-redis:6379/0

# Security (Staging keys)
SECRET_KEY=${STAGING_SECRET_KEY}
ENCRYPTION_KEY=${STAGING_ENCRYPTION_KEY}

# Job Configuration
ORCHESTRATOR_INTERVAL_MINUTES=30
```

### **Staging Deployment**

#### **deploy-staging.sh**
```bash
#!/bin/bash
# Staging deployment script

set -e

echo "Deploying to staging environment..."

# Build and tag images
docker build -t pulse/etl-service:staging services/etl-service/

# Deploy to staging
docker-compose -f docker-compose.staging.yml down
docker-compose -f docker-compose.staging.yml up -d

# Wait for services to be ready
sleep 30

# Run health checks
curl -f http://staging.pulse.company/health || exit 1

# Run smoke tests
cd services/etl-service
python -m pytest tests/smoke/ -v

echo "Staging deployment completed successfully!"
```

## 🏭 Production Environment

### **Production Configuration**

#### **.env.production**
```bash
# Application Settings
DEBUG=false
LOG_LEVEL=WARNING
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000

# Production Database (Managed service)
DATABASE_URL=postgresql://${PROD_DB_USER}:${PROD_DB_PASSWORD}@${PROD_DB_HOST}:5432/${PROD_DB_NAME}

# Production Integrations
JIRA_BASE_URL=${PROD_JIRA_URL}
JIRA_EMAIL=${PROD_JIRA_EMAIL}
JIRA_API_TOKEN=${PROD_JIRA_TOKEN}

GITHUB_TOKEN=${PROD_GITHUB_TOKEN}

# Production Features
ENABLE_PERFORMANCE_MONITORING=true
ENABLE_ERROR_TRACKING=true
ENABLE_AUDIT_LOGGING=true
ENABLE_METRICS_COLLECTION=true

# Production Cache (Managed Redis)
REDIS_URL=redis://${PROD_REDIS_HOST}:6379/0

# Production Security
SECRET_KEY=${PROD_SECRET_KEY}
ENCRYPTION_KEY=${PROD_ENCRYPTION_KEY}

# Production Job Configuration
ORCHESTRATOR_INTERVAL_MINUTES=60

# External Services
SENTRY_DSN=${SENTRY_DSN}
DATADOG_API_KEY=${DATADOG_API_KEY}
```

### **Production Deployment**

#### **deploy-production.sh**
```bash
#!/bin/bash
# Production deployment script with safety checks

set -e

# Safety checks
if [ "$ENVIRONMENT" != "production" ]; then
    echo "Error: ENVIRONMENT must be set to 'production'"
    exit 1
fi

if [ -z "$PROD_SECRET_KEY" ]; then
    echo "Error: Production secrets not configured"
    exit 1
fi

echo "Deploying to production environment..."

# Create backup
echo "Creating database backup..."
pg_dump $DATABASE_URL > backup-$(date +%Y%m%d-%H%M%S).sql

# Deploy with zero downtime
echo "Starting rolling deployment..."
docker-compose -f docker-compose.prod.yml up -d --scale etl-service=2

# Health check
echo "Performing health checks..."
for i in {1..10}; do
    if curl -f https://pulse.company/health; then
        echo "Health check passed"
        break
    fi
    echo "Health check failed, retrying in 10 seconds..."
    sleep 10
done

# Scale down old instances
docker-compose -f docker-compose.prod.yml up -d --scale etl-service=1

echo "Production deployment completed successfully!"
```

## 🔐 Secrets Management

### **Development Secrets**
```bash
# Local development - use .env files
# Never commit real secrets to version control
```

### **Production Secrets**

#### **Using Docker Secrets**
```bash
# Create secrets
echo "prod-secret-key" | docker secret create prod_secret_key -
echo "prod-db-password" | docker secret create prod_db_password -

# Use in docker-compose
services:
  etl-service:
    secrets:
      - prod_secret_key
      - prod_db_password
    environment:
      - SECRET_KEY_FILE=/run/secrets/prod_secret_key
      - DB_PASSWORD_FILE=/run/secrets/prod_db_password
```

#### **Using External Secret Management**
```bash
# AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id prod/pulse/db-password

# HashiCorp Vault
vault kv get -field=password secret/prod/pulse/database

# Kubernetes Secrets
kubectl get secret pulse-secrets -o jsonpath='{.data.db-password}' | base64 -d
```

## 📊 Environment Monitoring

### **Health Check Endpoints**
```bash
# Development
curl http://localhost:8000/health

# Staging
curl https://staging.pulse.company/health

# Production
curl https://pulse.company/health
```

### **Environment-Specific Monitoring**

#### **Development**
- Local log files
- Console output
- Basic health checks

#### **Staging**
- Centralized logging
- Performance monitoring
- Integration testing

#### **Production**
- Full observability stack
- Real-time alerting
- SLA monitoring
- Security monitoring

## 🔧 Configuration Validation

### **Environment Validation Script**

#### **validate-config.py**
```python
#!/usr/bin/env python3
"""Validate environment configuration"""

import os
import sys
from urllib.parse import urlparse

def validate_database_url(url):
    """Validate database URL format"""
    try:
        parsed = urlparse(url)
        assert parsed.scheme == 'postgresql'
        assert parsed.hostname
        assert parsed.port
        assert parsed.username
        assert parsed.password
        return True
    except:
        return False

def validate_environment():
    """Validate current environment configuration"""
    
    required_vars = [
        'DATABASE_URL',
        'SECRET_KEY',
        'JIRA_BASE_URL',
        'JIRA_EMAIL',
        'JIRA_API_TOKEN'
    ]
    
    errors = []
    
    # Check required variables
    for var in required_vars:
        if not os.getenv(var):
            errors.append(f"Missing required environment variable: {var}")
    
    # Validate database URL
    db_url = os.getenv('DATABASE_URL')
    if db_url and not validate_database_url(db_url):
        errors.append("Invalid DATABASE_URL format")
    
    # Check secret key length
    secret_key = os.getenv('SECRET_KEY')
    if secret_key and len(secret_key) < 32:
        errors.append("SECRET_KEY must be at least 32 characters")
    
    if errors:
        print("Configuration validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("Configuration validation passed!")

if __name__ == "__main__":
    validate_environment()
```

This environment setup ensures consistent, secure, and maintainable deployments across all stages of the development lifecycle.
