# Docker Setup and Deployment

## 🐳 Docker Architecture

The Pulse Platform uses Docker containers for consistent deployment across environments:

- **ETL Service**: Python FastAPI application with PostgreSQL
- **Backend Service**: API Gateway (planned)
- **Frontend Service**: React SPA (planned)
- **PostgreSQL**: Database container
- **Redis**: Caching layer (optional)

## 🏗️ Container Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Network                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────┐  │
│  │   Frontend      │    │   Backend       │    │   ETL   │  │
│  │   Container     │◄──►│   Container     │◄──►│ Service │  │
│  │   (nginx)       │    │   (node/python) │    │ (python)│  │
│  │   Port: 3000    │    │   Port: 5000    │    │Port:8000│  │
│  └─────────────────┘    └─────────────────┘    └─────────┘  │
│                                │                            │
│                                ▼                            │
│                    ┌─────────────────────┐                  │
│                    │   PostgreSQL        │                  │
│                    │   Container         │                  │
│                    │   Port: 5432        │                  │
│                    └─────────────────────┘                  │
│                                │                            │
│                                ▼                            │
│                    ┌─────────────────────┐                  │
│                    │   Redis Container   │                  │
│                    │   Port: 6379        │                  │
│                    └─────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Docker Configuration Files

### **Root docker-compose.yml**
```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15
    container_name: pulse-postgres
    environment:
      POSTGRES_DB: pulse_db
      POSTGRES_USER: pulse_user
      POSTGRES_PASSWORD: pulse_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
    networks:
      - pulse-network
    restart: unless-stopped

  # Redis Cache (Optional)
  redis:
    image: redis:7-alpine
    container_name: pulse-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - pulse-network
    restart: unless-stopped
    command: redis-server --appendonly yes

  # ETL Service
  etl-service:
    build:
      context: ./services/etl-service
      dockerfile: Dockerfile
    container_name: pulse-etl-service
    environment:
      - DATABASE_URL=postgresql://pulse_user:pulse_password@postgres:5432/pulse_db
      - REDIS_URL=redis://redis:6379/0
    ports:
      - "8000:8000"
    volumes:
      - ./services/etl-service/logs:/app/logs
      - ./services/etl-service/.env:/app/.env
    depends_on:
      - postgres
      - redis
    networks:
      - pulse-network
    restart: unless-stopped

  # Backend Service (Planned)
  backend-service:
    build:
      context: ./services/backend-service
      dockerfile: Dockerfile
    container_name: pulse-backend-service
    environment:
      - DATABASE_URL=postgresql://pulse_user:pulse_password@postgres:5432/pulse_db
      - ETL_SERVICE_URL=http://etl-service:8000
    ports:
      - "5000:5000"
    depends_on:
      - postgres
      - etl-service
    networks:
      - pulse-network
    restart: unless-stopped

  # Frontend Service (Planned)
  frontend-service:
    build:
      context: ./services/frontend-service
      dockerfile: Dockerfile
    container_name: pulse-frontend-service
    environment:
      - REACT_APP_API_URL=http://localhost:5000
    ports:
      - "3000:3000"
    depends_on:
      - backend-service
    networks:
      - pulse-network
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:

networks:
  pulse-network:
    driver: bridge
```

### **ETL Service Dockerfile**
```dockerfile
# services/etl-service/Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🚀 Deployment Commands

### **Development Deployment**

#### **Start All Services**
```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d etl-service

# Start with logs
docker-compose up etl-service
```

#### **View Logs**
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f etl-service

# View last 100 lines
docker-compose logs --tail=100 etl-service
```

#### **Service Management**
```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Restart specific service
docker-compose restart etl-service

# Rebuild and restart
docker-compose up -d --build etl-service
```

### **Production Deployment**

#### **Production docker-compose.yml**
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - pulse-network
    restart: always
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M

  etl-service:
    image: pulse/etl-service:${VERSION}
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
      - LOG_LEVEL=INFO
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config
    networks:
      - pulse-network
    restart: always
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

volumes:
  postgres_data:

networks:
  pulse-network:
    driver: bridge
```

#### **Production Deployment Script**
```bash
#!/bin/bash
# deploy.sh

set -e

# Configuration
VERSION=${1:-latest}
ENVIRONMENT=${2:-production}

echo "Deploying Pulse Platform version: $VERSION"
echo "Environment: $ENVIRONMENT"

# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Stop existing services
docker-compose -f docker-compose.prod.yml down

# Start services with new version
VERSION=$VERSION docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
sleep 30

# Check service health
docker-compose -f docker-compose.prod.yml ps

echo "Deployment completed successfully!"
```

## 🔧 Environment Configuration

### **Environment Files**

#### **.env.example**
```bash
# Application
DEBUG=false
LOG_LEVEL=INFO
SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-32-byte-encryption-key

# Database
DATABASE_URL=postgresql://pulse_user:pulse_password@localhost:5432/pulse_db

# Integrations
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token

GITHUB_TOKEN=your-github-personal-access-token

# Optional
REDIS_URL=redis://localhost:6379/0

# Job Configuration
ORCHESTRATOR_INTERVAL_MINUTES=60
```

#### **Production Environment**
```bash
# .env.production
DEBUG=false
LOG_LEVEL=WARNING
SECRET_KEY=${SECRET_KEY}
ENCRYPTION_KEY=${ENCRYPTION_KEY}

DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}

JIRA_BASE_URL=${JIRA_URL}
JIRA_EMAIL=${JIRA_EMAIL}
JIRA_API_TOKEN=${JIRA_TOKEN}

GITHUB_TOKEN=${GITHUB_TOKEN}

REDIS_URL=redis://${REDIS_HOST}:6379/0
```

## 📊 Monitoring and Health Checks

### **Health Check Configuration**
```yaml
# Health check for ETL service
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### **Monitoring Stack (Optional)**
```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    networks:
      - pulse-network

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    networks:
      - pulse-network

volumes:
  grafana_data:
```

## 🔐 Security Configuration

### **Production Security**
```yaml
# Security-hardened configuration
services:
  etl-service:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    user: "1000:1000"
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

### **Secrets Management**
```bash
# Using Docker secrets
echo "your-secret-key" | docker secret create jwt_secret -
echo "your-db-password" | docker secret create db_password -

# Reference in compose file
services:
  etl-service:
    secrets:
      - jwt_secret
      - db_password
    environment:
      - SECRET_KEY_FILE=/run/secrets/jwt_secret
      - DB_PASSWORD_FILE=/run/secrets/db_password

secrets:
  jwt_secret:
    external: true
  db_password:
    external: true
```

## 🚀 Scaling and Load Balancing

### **Horizontal Scaling**
```yaml
# Scale ETL service
services:
  etl-service:
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
```

### **Load Balancer Configuration**
```yaml
# nginx load balancer
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - etl-service
    networks:
      - pulse-network
```

## 🔧 Troubleshooting

### **Common Issues**

#### **Container Won't Start**
```bash
# Check logs
docker-compose logs etl-service

# Check container status
docker-compose ps

# Inspect container
docker inspect pulse-etl-service
```

#### **Database Connection Issues**
```bash
# Test database connection
docker-compose exec postgres psql -U pulse_user -d pulse_db

# Check network connectivity
docker-compose exec etl-service ping postgres
```

#### **Performance Issues**
```bash
# Monitor resource usage
docker stats

# Check container resources
docker-compose exec etl-service top
```

This Docker setup provides a robust, scalable foundation for deploying the Pulse Platform across different environments.
