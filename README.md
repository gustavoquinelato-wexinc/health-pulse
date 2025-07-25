# Pulse Platform - Complete Documentation

## 🏗️ **Architecture Overview**

The Pulse Platform is a microservices-based data integration platform designed for enterprise-scale ETL operations, real-time analytics, and AI-powered insights.

### **System Architecture**

```
Row 1: Application Services
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌───────────────────┐
│  Frontend       │◄──►│  Backend        │    │  ETL Service    │    │  AI Service       │
│  (React/Vite)   │    │  Service        │    │  (Python)       │    │  (LangGraph)      │
│  Port: 5173     │    │  (Python/FastAPI│    │  Port: 8000     │    │  Port: 8001       │
│                 │    │  Port: 3001     │    │                 │    │                   │
│ • Dashboard UI  │    │                 │    │ • Data Extract  │    │ • AI Orchestrator │
│ • DORA Metrics  │    │ • API Gateway   │    │ • Job Control   │    │ • Agent Workflows │
│ • GitHub Analytics│   │ • Authentication│    │ • Data Loading  │    │ • MCP Servers     │
│ • Portfolio View│    │ • Analytics APIs│◄──►│ • Orchestration │    │ • Tool Integration│
│ • C-Level KPIs  │    │ • Job Coordination│   │ • Recovery      │    │                   │
│ • ETL Settings  │    │ • Data Transform│    │ • Progress Track│    │                   │
│ • AI Chat (MCP) │◄───┼─ Caching Layer  │    └─────────────────┘    │                   │
└─────────────────┘    └─────────────────┘                           └───────────────────┘
                                │                       │                       │
                                ▼                       ▼                       ▼
Row 2: Caching Layer            │              ┌─────────────────┐              │
                                └─────────────►│  Redis Cache    │◄─────────────┘
                                               │  (Caching)      │
                                               │  Port: 6379     │
                                               │                 │
                                               │ • Query Cache   │
                                               │ • Session Cache │
                                               │ • Job Queue     │
                                               │ • Performance   │
                                               └─────────────────┘
                                                       │
                                                       ▼
Row 3: Database Layer                         ┌─────────────────┐
                                              │  PostgreSQL     │
                                              │  (Database)     │
                                              │  Port: 5432     │
                                              │                 │
                                              │ • Primary DB    │
                                              │ • Job State     │
                                              │ • User Data     │
                                              │ • Audit Logs    │
                                              └─────────────────┘

External Integrations:
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Data APIs      │    │  AI/LLM APIs    │    │  MCP Ecosystem  │
│                 │    │                 │    │                 │
│ • Jira Cloud    │    │ • OpenAI        │    │ • MCP Servers   │
│ • GitHub API    │    │ • Claude        │    │ • Tool Protocols│
│ • Rate Limits   │    │ • Local LLMs    │    │ • Agent Tools   │
│ • Auth Tokens   │    │ • Embeddings    │    │ • Context Mgmt  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       ▲                       ▲
         │                       │                       │
    ETL Service            AI Service              Frontend (Direct)
```

### **Core Components**

#### **🔄 ETL Service (Data Engineering)**
- **Jira Integration:** Issue tracking, project management data
- **GitHub Integration:** Repository, PR, commit data
- **Job Orchestration:** Smart scheduling, fast retry system, monitoring
- **Real-time Progress:** WebSocket updates, live dashboards
- **Checkpoint System:** Fault-tolerant, resumable operations
- **Log Management:** Table-based log viewer, file management, bulk operations

#### **📊 Backend Service (Data Analytics & API Gateway)**
- **Analytics APIs:** DORA metrics, GitHub analytics, portfolio insights
- **API Gateway:** Unified interface for React frontend
- **Authentication:** JWT-based auth with role-based access control
- **Job Coordination:** ETL settings management and job control
- **Data Processing:** Complex calculations and statistical analysis
- **Performance Optimization:** Query caching, connection pooling
- **Real-time Updates:** WebSocket support for live data

#### **🧠 AI Service**
- **Data Analysis:** Pattern recognition, anomaly detection
- **Predictive Models:** Sprint planning, risk assessment
- **Insights Engine:** Automated reporting, recommendations

#### **🌐 Frontend**
- **Dashboard UI:** Interactive analytics dashboards
- **Real-time Monitoring:** Live job status, progress tracking
- **ETL Management:** Configuration and job control interface

### **Data Flow Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  External APIs  │───►│  ETL Service    │───►│  PostgreSQL     │
│                 │    │                 │    │                 │
│ • Jira Issues   │    │ • Extract       │    │ • Unified       │
│ • GitHub PRs    │    │ • Transform     │    │   Schema        │
│ • Repositories  │    │ • Load          │    │ • Normalized    │
│ • Changelogs    │    │ • Validate      │    │   Data          │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Frontend UI    │◄───│  Backend        │◄───│  Data Analysis  │
│                 │    │  Service        │    │                 │
│ • DORA Metrics  │    │                 │    │ • Complex       │
│ • GitHub Analytics│   │ • Analytics APIs│    │   Queries       │
│ • Portfolio View│    │ • Aggregations  │    │ • Statistical   │
│ • C-Level KPIs  │    │ • Transformations│    │   Analysis      │
│ • ETL Settings  │    │ • API Gateway   │    │ • Performance   │
│ • Real-time UI  │    │ • Caching       │    │   Optimization  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  AI Service     │
                       │                 │
                       │ • ML Models     │
                       │ • Insights      │
                       │ • Predictions   │
                       │ • Recommendations│
                       └─────────────────┘
```

## 🚀 **Quick Start Guide**

### **Prerequisites**
- Docker & Docker Compose
- Git
- 8GB+ RAM recommended
- Ports 3001, 5173, 8000, 8001, 5432, 6379 available

### **1. Clone & Setup**
```bash
git clone <repository-url>
cd pulse-platform

# Configure centralized environment (SINGLE .env file for all services)
cp .env.example .env
# Edit .env with your API keys and configuration
```

### **2. Start Platform**
```bash
# Start all services
./start-platform.sh start

# Or start specific service
./start-platform.sh start etl
```

### **3. Access Services**
- **Frontend:** http://localhost:5173
- **ETL Dashboard:** http://localhost:8000
- **Backend Service API:** http://localhost:3001
- **AI Service:** http://localhost:8001

### **4. Initial Configuration**
```bash
# Complete database setup with integrations (first time only)
cd services/etl-service
python scripts/reset_database.py --all

# Test connections
python scripts/test_jobs.py --test-connection
```

## ⚙️ **Configuration**

### **Environment Variables**

#### **Database Configuration**
```env
# PostgreSQL Database
DATABASE_URL=postgresql://pulse_user:pulse_password@localhost:5432/pulse_db
POSTGRES_DB=pulse_db
POSTGRES_USER=pulse_user
POSTGRES_PASSWORD=pulse_password
```

#### **External API Integration**
```env
# Jira Configuration
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token

# GitHub Configuration  
GITHUB_TOKEN=your-github-personal-access-token
GITHUB_ORG=your-organization-name
```

#### **Security Configuration**
```env
# JWT Security
JWT_SECRET_KEY=your-super-secret-jwt-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Admin User (created automatically)
ADMIN_EMAIL=admin@company.com
ADMIN_PASSWORD=secure-admin-password
```

#### **Service Configuration**
```env
# ETL Service
ETL_SERVICE_URL=http://localhost:8000
REDIS_URL=redis://localhost:6379

# AI Service
AI_SERVICE_URL=http://localhost:8001
OPENAI_API_KEY=your-openai-key (optional)
```

### **Docker Configuration**

The platform uses Docker Compose for orchestration. Key configuration files:

- `docker-compose.yml` - Development environment
- `docker-compose.prod.yml` - Production environment
- `.env` - **Centralized environment variables for ALL services**
- `start-platform.sh` - Management script

**Important**: The platform uses a **single `.env` file** at the root level that contains configuration for all services. Do not create service-specific `.env` files.

## 🔧 **Development Workflow**

### **Service Development**

#### **ETL Service Development**
```bash
cd services/etl-service

# Install dependencies
pip install -r requirements.txt

# Run locally (development)
uvicorn app.main:app --reload --port 8000

# Run tests
python scripts/test_jobs.py
```

#### **Backend Service Development**
```bash
cd services/backend-service

# Install dependencies
pip install -r requirements.txt

# Run locally (development)
uvicorn app.main:app --reload --port 3001
```

#### **Frontend Development**
```bash
cd services/frontend-app

# Install dependencies
npm install

# Run development server
npm run dev
```

### **Database Management**

#### **Reset Database (Development)**
```bash
cd services/etl-service

# Complete reset with sample data
python scripts/reset_database.py --all

# Reset tables only
python scripts/reset_database.py --recreate-tables
```

#### **Database Migrations**
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

### **Testing & Debugging**

#### **ETL Job Testing**
```bash
cd services/etl-service

# Interactive testing
python scripts/test_jobs.py

# Test API connections
python scripts/test_jobs.py --test-connection

# Debug mode
python scripts/test_jobs.py --debug
```

#### **Service Health Checks**
```bash
# Check all services
./start-platform.sh status

# View logs
./start-platform.sh logs etl
```

## 📊 **Monitoring & Operations**

### **Job Monitoring**

#### **Real-time Dashboard**
- Access: http://localhost:8000
- Features: Live progress, job status, error tracking
- WebSocket updates for real-time monitoring

#### **Job Management**
- **Start/Stop:** Manual job control
- **Scheduling:** Automated job orchestration with fast retry system
- **Recovery:** Automatic checkpoint-based recovery
- **Monitoring:** Progress tracking, error handling

### **Performance Monitoring**

#### **System Metrics**
```bash
# Container resource usage
docker stats

# Service-specific metrics
docker-compose logs -f etl
```

#### **Database Performance**
```bash
# Connect to database
docker-compose exec postgres psql -U pulse_user -d pulse_db

# Check table sizes
SELECT schemaname,tablename,pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size 
FROM pg_tables WHERE schemaname='public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## 🔒 **Security**

### **Authentication & Authorization**
- **JWT Tokens:** Secure API access
- **Role-based Access:** Admin, User, Viewer roles
- **Session Management:** Redis-based session storage

### **API Security**
- **Rate Limiting:** Prevents API abuse
- **Input Validation:** Comprehensive request validation
- **CORS Configuration:** Secure cross-origin requests

### **Data Security**
- **Encrypted Storage:** Sensitive data encryption
- **Secure Connections:** HTTPS/TLS for external APIs
- **Audit Logging:** Comprehensive activity tracking

## 🚀 **Deployment**

### **Development Deployment**
```bash
# Start all services
./start-platform.sh start

# Start specific services
./start-platform.sh start etl
```

### **Production Deployment**
```bash
# Production build
docker-compose -f docker-compose.prod.yml up -d

# With custom environment
ENV=production ./start-platform.sh start
```

### **Scaling**
```bash
# Scale ETL service
docker-compose up -d --scale etl=3

# Load balancer configuration
# (Configure nginx/traefik for production)
```

## 🔧 **Troubleshooting**

### **Common Issues**

#### **Service Won't Start**
```bash
# Check Docker status
docker info

# Check port conflicts
netstat -tulpn | grep :8000

# View service logs
./start-platform.sh logs etl
```

#### **Database Connection Issues**
```bash
# Test database connection
docker-compose exec postgres psql -U pulse_user -d pulse_db

# Reset database
cd services/etl-service
python scripts/reset_database.py --all
```

#### **API Integration Issues**
```bash
# Test API connections
cd services/etl-service
python scripts/test_jobs.py --test-connection

# Check API credentials in .env file
```

### **Performance Issues**
```bash
# Monitor resource usage
docker stats

# Check database performance
docker-compose exec postgres pg_stat_activity

# Optimize database
VACUUM ANALYZE;
```

## 📚 **Additional Resources**

### **API Documentation**
- **ETL Service:** http://localhost:8000/docs
- **Backend Service:** http://localhost:3001/docs
- **AI Service:** http://localhost:8001/docs

### **Development Tools**
- **Database Admin:** pgAdmin or similar
- **API Testing:** Postman, curl
- **Log Analysis:** Docker logs, application logs

### **Platform Documentation**
- **[📚 Documentation Index](docs/DOCUMENTATION_INDEX.md)** - Complete documentation navigation
- **[🤖 Agent Guidance](docs/AGENT_GUIDANCE.md)** - Essential guidance for Augment Code agents
- **[Architecture Guide](docs/ARCHITECTURE.md)** - System architecture and design
- **[Migration Guide](docs/MIGRATION_GUIDE.md)** - Database migration system
- **[Scripts Guide](docs/SCRIPTS_GUIDE.md)** - Cross-service scripts and utilities

### **Service Documentation**
- **[ETL Development Guide](services/etl-service/docs/DEVELOPMENT_GUIDE.md)** - ETL service development and testing
- **[ETL Service README](services/etl-service/README.md)** - ETL service overview and features
- **[Backend Service README](services/backend-service/README.md)** - Backend service development guide
- **[Frontend README](services/frontend-app/README.md)** - Frontend application guide

### **External Documentation**
- **Jira API:** https://developer.atlassian.com/cloud/jira/platform/rest/v3/
- **GitHub API:** https://docs.github.com/en/rest
- **Docker Compose:** https://docs.docker.com/compose/
