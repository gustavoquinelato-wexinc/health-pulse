# Pulse Platform - Deployment Guide

## 🚀 **Deployment Overview**

This guide covers deployment strategies for the Pulse Platform across different environments.

## 🔧 **Prerequisites**

### **System Requirements**
- **Docker:** 20.10+ with Docker Compose
- **Memory:** 8GB+ RAM recommended
- **Storage:** 20GB+ available disk space
- **Network:** Ports 3001, 5173, 8000, 8001, 5432, 6379 available

### **External Dependencies**
- **Jira Cloud:** API access with valid credentials
- **GitHub:** Personal access token with repository permissions
- **PostgreSQL:** Database for data storage
- **Redis:** (Optional) For caching and session management

## 🏠 **Development Deployment**

### **Quick Start**
```bash
# Clone repository
git clone <repository-url>
cd pulse-platform

# Configure environment
cp .env.example .env
# Edit .env with your API keys and configuration

# Start all services
./start-platform.sh start

# Or start individual services
./start-platform.sh start etl
./start-platform.sh start frontend
./start-platform.sh start backend
```

### **Service URLs**
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:3001
- **ETL Service:** http://localhost:8000
- **AI Service:** http://localhost:8001
- **Database:** localhost:5432
- **Redis:** localhost:6379

### **Development Commands**
```bash
# View service status
./start-platform.sh status

# View logs
./start-platform.sh logs etl
./start-platform.sh logs frontend

# Stop services
./start-platform.sh stop

# Restart services
./start-platform.sh restart
```

## 🏭 **Production Deployment**

### **Environment Configuration**

#### **Production Environment Variables**
```env
# Database Configuration
DATABASE_URL=postgresql://pulse_user:secure_password@db-host:5432/pulse_db
POSTGRES_DB=pulse_db
POSTGRES_USER=pulse_user
POSTGRES_PASSWORD=secure_password

# Security Configuration
SECRET_KEY=your-super-secure-jwt-key-256-bits
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# External API Configuration
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=service-account@company.com
JIRA_API_TOKEN=your-production-jira-token

GITHUB_TOKEN=your-production-github-token
GITHUB_ORG=your-organization

# Service Configuration
ETL_SERVICE_URL=https://etl.your-domain.com
BACKEND_SERVICE_URL=https://api.your-domain.com
FRONTEND_URL=https://pulse.your-domain.com

# Redis Configuration (Optional)
REDIS_URL=redis://redis-host:6379

# Admin User
ADMIN_EMAIL=admin@company.com
ADMIN_PASSWORD=secure-admin-password
```

### **Docker Production Deployment**
```bash
# Production build
docker-compose -f docker-compose.prod.yml up -d

# With environment override
ENV=production docker-compose -f docker-compose.prod.yml up -d

# Scale services
docker-compose -f docker-compose.prod.yml up -d --scale etl=2 --scale backend=3
```

### **Production Docker Compose**
```yaml
# docker-compose.prod.yml
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
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  etl:
    build:
      context: ./services/etl-service
      dockerfile: Dockerfile.prod
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - JIRA_BASE_URL=${JIRA_BASE_URL}
      - GITHUB_TOKEN=${GITHUB_TOKEN}
    restart: unless-stopped
    depends_on:
      - postgres
      - redis

  backend:
    build:
      context: ./services/backend-service
      dockerfile: Dockerfile.prod
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
    restart: unless-stopped
    depends_on:
      - postgres

  frontend:
    build:
      context: ./services/frontend-app
      dockerfile: Dockerfile.prod
    environment:
      - VITE_API_URL=${BACKEND_SERVICE_URL}
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

## ☸️ **Kubernetes Deployment**

### **Namespace Setup**
```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: pulse-platform
```

### **ConfigMap**
```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: pulse-config
  namespace: pulse-platform
data:
  POSTGRES_DB: pulse_db
  POSTGRES_USER: pulse_user
  JIRA_BASE_URL: https://your-domain.atlassian.net
  GITHUB_ORG: your-organization
```

### **Secrets**
```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: pulse-secrets
  namespace: pulse-platform
type: Opaque
data:
  POSTGRES_PASSWORD: <base64-encoded-password>
  SECRET_KEY: <base64-encoded-jwt-key>
  JIRA_API_TOKEN: <base64-encoded-jira-token>
  GITHUB_TOKEN: <base64-encoded-github-token>
```

### **Database Deployment**
```yaml
# postgres.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: pulse-platform
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        envFrom:
        - configMapRef:
            name: pulse-config
        - secretRef:
            name: pulse-secrets
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
```

### **ETL Service Deployment**
```yaml
# etl-service.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: etl-service
  namespace: pulse-platform
spec:
  replicas: 2
  selector:
    matchLabels:
      app: etl-service
  template:
    metadata:
      labels:
        app: etl-service
    spec:
      containers:
      - name: etl-service
        image: pulse-platform/etl-service:latest
        envFrom:
        - configMapRef:
            name: pulse-config
        - secretRef:
            name: pulse-secrets
        ports:
        - containerPort: 8000
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

## 🔒 **Security Considerations**

### **Network Security**
- **Firewall Rules:** Restrict access to necessary ports only
- **VPN Access:** Secure administrative access
- **SSL/TLS:** HTTPS for all external communication
- **Internal Communication:** Encrypted service-to-service communication

### **Data Security**
- **Database Encryption:** Encrypt data at rest
- **Backup Encryption:** Secure backup storage
- **API Keys:** Secure credential management
- **Audit Logging:** Comprehensive access logging

### **Container Security**
- **Image Scanning:** Regular vulnerability scanning
- **Non-root Users:** Run containers as non-root
- **Resource Limits:** CPU and memory constraints
- **Security Contexts:** Proper security policies

## 📊 **Monitoring & Observability**

### **Health Checks**
```bash
# Service health endpoints
curl http://localhost:8000/health    # ETL Service
curl http://localhost:3001/health    # Backend Service
curl http://localhost:8001/health    # AI Service
```

### **Logging**
```bash
# View service logs
docker-compose logs -f etl
docker-compose logs -f backend
docker-compose logs -f frontend

# Kubernetes logs
kubectl logs -f deployment/etl-service -n pulse-platform
```

### **Metrics Collection**
- **Prometheus:** Metrics collection and storage
- **Grafana:** Metrics visualization and dashboards
- **AlertManager:** Alert routing and management
- **Jaeger:** Distributed tracing (optional)

## 🔄 **Backup & Recovery**

### **Database Backup**
```bash
# Create backup
docker-compose exec postgres pg_dump -U pulse_user pulse_db > backup.sql

# Restore backup
docker-compose exec -T postgres psql -U pulse_user pulse_db < backup.sql
```

### **Configuration Backup**
```bash
# Backup configuration
tar -czf config-backup.tar.gz .env docker-compose.yml

# Backup application data
docker-compose exec postgres pg_dump -U pulse_user pulse_db | gzip > pulse_db_backup.sql.gz
```

### **Disaster Recovery**
1. **Regular Backups:** Automated daily database backups
2. **Configuration Management:** Version-controlled configuration
3. **Infrastructure as Code:** Reproducible infrastructure
4. **Recovery Testing:** Regular recovery procedure testing

## 🚀 **Scaling Strategies**

### **Horizontal Scaling**
```bash
# Scale ETL service
docker-compose up -d --scale etl=3

# Scale backend service
docker-compose up -d --scale backend=2
```

### **Load Balancing**
- **Nginx:** Reverse proxy and load balancer
- **HAProxy:** High-availability load balancer
- **Cloud Load Balancers:** AWS ALB, GCP Load Balancer

### **Database Scaling**
- **Read Replicas:** Distribute read operations
- **Connection Pooling:** Optimize database connections
- **Partitioning:** Horizontal data partitioning
- **Caching:** Redis for frequently accessed data

## 🔧 **Troubleshooting**

### **Common Issues**
```bash
# Service won't start
docker-compose ps
docker-compose logs service-name

# Database connection issues
docker-compose exec postgres psql -U pulse_user -d pulse_db

# Port conflicts
netstat -tulpn | grep :8000

# Resource issues
docker stats
```

### **Performance Optimization**
- **Resource Allocation:** Proper CPU and memory limits
- **Database Tuning:** PostgreSQL configuration optimization
- **Caching Strategy:** Redis implementation
- **Connection Pooling:** Database connection optimization

---

**For development deployment, see the main README.md. For service-specific deployment details, check individual service documentation.**
