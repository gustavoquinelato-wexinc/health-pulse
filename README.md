# Pulse Platform - Unified Engineering Analytics Platform

## 🏗️ **Platform Architecture Overview**

The Pulse Platform is a unified engineering analytics platform that seamlessly integrates ETL management capabilities through embedded iframe technology, providing a comprehensive solution for DORA metrics, engineering analytics, and data pipeline orchestration.

### **Unified Platform Architecture**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Pulse Platform Frontend                     │
│                      (React/Vite - Port 5173)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📊 DORA Metrics Dashboard                                      │
│  📈 Engineering Analytics                                       │
│  🔧 Settings Management                                         │
│  🤖 AI Chat Interface                                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              🔧 ETL Management (Admin Only)                │ │
│  │                                                             │ │
│  │  iframe: http://localhost:8000?embedded=true&token=...      │ │
│  │                                                             │ │
│  │  • Job Orchestration Dashboard                             │ │
│  │  • Data Pipeline Configuration                             │ │
│  │  • Real-time Progress Monitoring                           │ │
│  │  • Integration Management                                  │ │
│  │  • Admin Panel Access                                      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                    │                       │
                    ▼                       ▼
┌─────────────────┐              ┌─────────────────┐    ┌───────────────────┐
│  Backend        │              │  ETL Service    │    │  AI Service       │
│  Service        │◄────────────►│  (Embedded)     │    │  (LangGraph)      │
│  (Node.js)      │              │  (FastAPI)      │    │  Port: 8001       │
│  Port: 3002     │              │  Port: 8000     │    │                   │
│                 │              │                 │    │ • AI Orchestrator │
│ • Authentication│              │ • Data Extract  │    │ • Agent Workflows │
│ • User Mgmt     │              │ • Job Control   │    │ • MCP Servers     │
│ • Session Mgmt  │              │ • Orchestration │    │ • Tool Integration│
│ • API Gateway   │              │ • Recovery      │    │                   │
│ • Client Mgmt   │              │ • Admin APIs    │    │                   │
└─────────────────┘              └─────────────────┘    └───────────────────┘
                    │                       │                       │
                    └───────────────────────┼───────────────────────┘
                                           │
                                           ▼
                                ┌─────────────────┐
                                │  PostgreSQL     │
                                │  (Database)     │
                                │  Port: 5432     │
                                │                 │
                                │ • User Data     │
                                │ • Job State     │
                                │ • Analytics     │
                                │ • Audit Logs    │
                                └─────────────────┘
```

## 🌟 **Key Platform Features**

### **🔗 Unified Experience**
- **Seamless Integration**: ETL management embedded directly in main platform
- **Single Sign-On**: Shared authentication across all components
- **Consistent Branding**: Client-specific logos and themes throughout
- **Role-Based Access**: Admin-only ETL management with automatic access control

### **📊 Engineering Analytics**
- **DORA Metrics**: Deployment frequency, lead time, MTTR, change failure rate
- **Real-time Monitoring**: Live job progress and system health
- **Portfolio Analytics**: Multi-project insights and trends
- **C-Level KPIs**: Executive dashboards and reporting

### **🔧 ETL Management (Admin Only)**
- **Job Orchestration**: Automated data pipeline scheduling
- **Progress Tracking**: Real-time job monitoring with WebSocket updates
- **Recovery Systems**: Checkpoint-based failure recovery
- **Integration Management**: Jira, GitHub, and custom data sources

### **🎨 Modern UI/UX**
- **Responsive Design**: Works seamlessly on desktop and mobile
- **Dark/Light Themes**: User preference with system sync
- **Custom Color Schemas**: Client-specific branding options
- **Glassmorphism Design**: Modern, professional interface

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

## 🚀 **Quick Start**

### **Platform Access**
1. **Main Platform**: http://localhost:5173
   - DORA Metrics Dashboard
   - Engineering Analytics
   - Settings Management

2. **ETL Management** (Admin Only): Embedded within main platform
   - Accessible via ETL menu item (admin users only)
   - Seamless iframe integration
   - Shared authentication and branding

### **User Roles**
- **Admin Users**: Full platform access + ETL management
- **Standard Users**: Platform analytics and dashboards only
- **Viewer Users**: Read-only access to dashboards

### **Development Setup**
```bash
# 1. Start Backend Service (Authentication Hub)
cd services/backend-service && npm run dev

# 2. Start ETL Service (Embedded Component)
cd services/etl-service && python -m uvicorn app.main:app --reload

# 3. Start Frontend Platform (Main Interface)
cd services/frontend-app && npm run dev
```

### **Default Login Credentials**
- **Admin**: gustavo.quinelato@wexinc.com / pulse
- **User**: user@pulse.com / pulse
- **Viewer**: viewer@pulse.com / pulse

### **Core Components**

#### **🎯 Frontend Platform (Unified Interface)**
- **DORA Metrics Dashboard:** Deployment frequency, lead time, MTTR, change failure rate
- **Engineering Analytics:** GitHub insights, portfolio analytics, team metrics
- **Embedded ETL Management:** iframe integration for admin users
- **Role-Based Navigation:** Dynamic menu based on user permissions
- **Client Branding:** Dynamic logo and theme loading
- **Real-time Updates:** WebSocket integration for live data
- **Responsive Design:** Mobile and desktop optimized

#### **🔐 Backend Service (Authentication Hub)**
- **Centralized Authentication:** JWT-based auth with role-based access control
- **User Management:** Registration, login, session management
- **API Gateway:** Unified interface for frontend and ETL service
- **Client Management:** Multi-client support with isolated data
- **Analytics APIs:** DORA metrics, GitHub analytics, portfolio insights
- **Session Validation:** Token verification for embedded services

#### **🔧 ETL Service (Embedded Component)**
- **Admin-Only Interface:** Embedded iframe for authorized users
- **Job Orchestration:** Smart scheduling, fast retry system, monitoring
- **Data Integration:** Jira, GitHub, and custom data sources
- **Real-time Progress:** WebSocket updates, live dashboards
- **Checkpoint System:** Fault-tolerant, resumable operations
- **Shared Authentication:** Token validation via Backend Service

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
- Python 3.8+ (for manual execution)
- PostgreSQL & Redis (for manual execution)
- 8GB+ RAM recommended
- Ports 3002, 5173, 8000, 8001, 5432, 6379 available

### **1. Clone & Setup**
```bash
git clone <repository-url>
cd pulse-platform

# Configure multi-client environment files
cp .env.shared.example .env.shared
cp .env.etl.wex.example .env.etl.wex
cp .env.backend.example .env.backend

# Edit environment files with your configuration
# .env.shared - Database and shared configuration
# .env.etl.wex - WEX client-specific API keys and settings
# .env.backend - Backend service configuration
```

### **2. Environment Setup**

#### **For Docker Deployment (Recommended)**
```bash
# Start all services with multi-client support
./start-multi-instance.sh

# Or use Docker Compose directly
docker-compose -f docker-compose.multi-client.yml up -d
```

#### **For Manual Development**
```bash
# Create combined environment file for migration runner
cat .env.shared .env.etl.wex > .env

# Install dependencies (centralized requirements management)
python scripts/install_requirements.py all
# Or for specific service:
python scripts/install_requirements.py etl-service
```

### **3. Database Setup**
```bash
# Run migrations (requires combined .env file in root)
python scripts/migration_runner.py

# Or reset database with sample data (development only)
cd services/etl-service
python scripts/reset_database.py --all
```

### **4. Start Services**

#### **Docker Method (Production-like)**
```bash
# All services
./start-multi-instance.sh

# Individual services
docker-compose -f docker-compose.multi-client.yml up etl-wex -d
```

#### **Manual Method (Development)**
```bash
# Backend Service
cd services/backend-service
cp ../..env.shared ../..env.backend .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 3002 --reload

# ETL Service (WEX client)
cd services/etl-service
cat ../../.env.shared ../../.env.etl.wex > .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd services/frontend-app
npm install
npm run dev
```

### **5. Access Services**
- **Frontend:** http://localhost:5173
- **ETL Dashboard:** http://localhost:8000
- **Backend Service API:** http://localhost:3002
- **ETL API Documentation:** http://localhost:8000/docs (admin access required)

### **6. Initial Configuration**
```bash
# Test API connections
cd services/etl-service
python scripts/test_jobs.py --test-connection

# Access admin panel to configure integrations
# Navigate to: http://localhost:8000/admin
```

## ⚙️ **Configuration**

### **Multi-Client Environment Setup**

The platform uses **separate environment files** for different configuration layers:

#### **Shared Configuration (`.env.shared`)**
```env
# PostgreSQL Database (shared across all clients)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=pulse
POSTGRES_DATABASE=pulse_db

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379

# Service URLs
BACKEND_SERVICE_URL=http://localhost:3002
ETL_SERVICE_URL=http://localhost:8000
```

#### **Client-Specific Configuration (`.env.etl.wex`)**
```env
# Client Identification
CLIENT_NAME=WEX

# Jira Configuration (WEX-specific)
JIRA_URL=https://wexinc.atlassian.net
JIRA_USERNAME=your-email@wexinc.com
JIRA_TOKEN=your-wex-jira-api-token

# GitHub Configuration (WEX-specific)
GITHUB_TOKEN=your-wex-github-token
GITHUB_ORG=wexinc
```

#### **Backend Service Configuration (`.env.backend`)**
```env
# JWT Security
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Admin User (created automatically)
ADMIN_EMAIL=admin@company.com
ADMIN_PASSWORD=secure-admin-password-change-in-production
```

### **Environment File Usage**

#### **For Migration Runner & Scripts**
```bash
# Migration runner requires combined environment file in root
cat .env.shared .env.etl.wex > .env
python scripts/migration_runner.py
```

#### **For Manual Service Execution**
```bash
# ETL Service needs combined environment
cd services/etl-service
cat ../../.env.shared ../../.env.etl.wex > .env
python -m uvicorn app.main:app --reload

# Backend Service needs combined environment
cd services/backend-service
cat ../../.env.shared ../../.env.backend > .env
python -m uvicorn app.main:app --reload
```

#### **For Docker Deployment**
```bash
# Docker Compose automatically combines environment files
docker-compose -f docker-compose.multi-client.yml up -d
```

### **Docker Configuration**

The platform uses Docker Compose for orchestration. Key configuration files:

- `docker-compose.multi-client.yml` - Multi-client production environment
- `docker-compose.yml` - Single-client development environment
- `.env.shared` - **Shared configuration (database, Redis, service URLs)**
- `.env.etl.{client}` - **Client-specific ETL configuration**
- `.env.backend` - **Backend service configuration**
- `start-multi-instance.sh` - Multi-client management script

### **Adding New Clients**

To add a new client (e.g., TechCorp):

1. **Create client environment file:**
```bash
cp .env.etl.wex .env.etl.techcorp
# Edit .env.etl.techcorp with TechCorp-specific settings
```

2. **Update Docker Compose:**
```yaml
# Add to docker-compose.multi-client.yml
etl-techcorp:
  build: ./services/etl-service
  environment:
    - CLIENT_NAME=TechCorp
  env_file:
    - .env.shared
    - .env.etl.techcorp
```

3. **Update startup scripts:**
```bash
# Add TechCorp to start-multi-instance.sh
```

## 🔧 **Development Workflow**

### **Prerequisites for Manual Development**

#### **Install Dependencies (Centralized Management)**
```bash
# Install all service dependencies from root
python scripts/install_requirements.py all

# Install specific service dependencies
python scripts/install_requirements.py etl-service
python scripts/install_requirements.py backend-service

# Each service uses isolated virtual environments
# Dependencies are managed centrally but installed per-service
```

#### **Environment Setup for Development**
```bash
# Create combined environment files for each service
# ETL Service
cd services/etl-service
cat ../../.env.shared ../../.env.etl.wex > .env

# Backend Service
cd services/backend-service
cat ../../.env.shared ../../.env.backend > .env

# Root level (for migration runner and scripts)
cd ../..
cat .env.shared .env.etl.wex > .env
```

### **Service Development**

#### **ETL Service Development**
```bash
# Setup environment
cd services/etl-service
cat ../../.env.shared ../../.env.etl.wex > .env

# Run locally (development)
python -m uvicorn app.main:app --reload --port 8000

# Run tests
python scripts/test_jobs.py

# Test API connections
python scripts/test_jobs.py --test-connection
```

#### **Backend Service Development**
```bash
# Setup environment
cd services/backend-service
cat ../../.env.shared ../../.env.backend > .env

# Run locally (development)
python -m uvicorn app.main:app --reload --port 3002

# Test authentication endpoints
curl -X POST http://localhost:3002/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@company.com","password":"your-admin-password"}'
```

#### **Frontend Development**
```bash
cd services/frontend-app

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

### **Database Management**

#### **Database Migrations (Production Method)**
```bash
# Ensure root .env file exists for migration runner
cat .env.shared .env.etl.wex > .env

# Run migrations
python scripts/migration_runner.py

# Rollback to specific migration
python scripts/migration_runner.py --rollback-to 001

# Check migration status
python scripts/migration_runner.py --status
```

#### **Reset Database (Development Only)**
```bash
cd services/etl-service

# Complete reset with sample data
python scripts/reset_database.py --all

# Reset tables only
python scripts/reset_database.py --recreate-tables

# Reset specific components
python scripts/reset_database.py --reset-integrations
```

#### **Manual Database Operations**
```bash
# Connect to database
docker-compose exec postgres psql -U postgres -d pulse_db

# Or with local PostgreSQL
psql -h localhost -U postgres -d pulse_db

# Check client data
SELECT id, name, active FROM clients;

# Check user sessions
SELECT u.email, s.created_at, s.last_accessed_at
FROM users u JOIN user_sessions s ON u.id = s.user_id
WHERE s.active = true;
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

### **Multi-Client Security Architecture**
- **Complete Client Isolation:** All database operations filter by client_id
- **Zero Cross-Client Access:** Enterprise-grade data separation
- **Client-Scoped Authentication:** JWT tokens include client context
- **Secure Multi-Tenancy:** Production-ready multi-client architecture

### **Authentication & Authorization**
- **JWT Tokens:** Secure API access with client_id validation
- **Role-based Access:** Admin, User, Viewer roles per client
- **Session Management:** Database-backed session storage with client isolation
- **Centralized Auth:** Backend service handles all authentication

### **API Security**
- **Client Validation:** All endpoints validate client ownership
- **Input Validation:** Comprehensive request validation
- **CORS Configuration:** Secure cross-origin requests
- **Admin Protection:** Admin functions scoped to client data only

### **Data Security**
- **Client Data Isolation:** Every query filters by client_id
- **Secure Job Processing:** Background jobs respect client boundaries
- **Encrypted Storage:** Sensitive data encryption
- **Secure Connections:** HTTPS/TLS for external APIs
- **Audit Logging:** Comprehensive activity tracking per client

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

#### **Environment Configuration Issues**
```bash
# Missing .env file for migration runner
cat .env.shared .env.etl.wex > .env
python scripts/migration_runner.py

# Service can't find environment variables
cd services/etl-service
cat ../../.env.shared ../../.env.etl.wex > .env

# Check environment file contents
head -20 .env

# Verify client configuration
grep CLIENT_NAME .env
```

#### **Service Won't Start**
```bash
# Check Docker status
docker info

# Check port conflicts (Windows)
netstat -an | findstr :8000

# Check port conflicts (Linux/Mac)
netstat -tulpn | grep :8000

# View service logs
docker-compose -f docker-compose.multi-client.yml logs etl-wex

# Check service dependencies
docker-compose -f docker-compose.multi-client.yml ps
```

#### **Database Connection Issues**
```bash
# Test database connection
docker-compose exec postgres psql -U postgres -d pulse_db

# Check database configuration
grep POSTGRES .env.shared

# Reset database (development only)
cd services/etl-service
python scripts/reset_database.py --all

# Run migrations manually
python scripts/migration_runner.py
```

#### **API Integration Issues**
```bash
# Test API connections
cd services/etl-service
python scripts/test_jobs.py --test-connection

# Check API credentials
grep JIRA_TOKEN .env
grep GITHUB_TOKEN .env

# Test specific API endpoints
curl -H "Authorization: Bearer $JIRA_TOKEN" \
  "https://wexinc.atlassian.net/rest/api/3/myself"
```

#### **Authentication Issues**
```bash
# Check JWT configuration
grep JWT_SECRET_KEY .env

# Test login endpoint
curl -X POST http://localhost:3002/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@company.com","password":"your-password"}'

# Check user sessions
docker-compose exec postgres psql -U postgres -d pulse_db \
  -c "SELECT email, active FROM users WHERE email LIKE '%admin%';"
```

#### **Client Isolation Issues**
```bash
# Verify client setup
docker-compose exec postgres psql -U postgres -d pulse_db \
  -c "SELECT id, name, active FROM clients;"

# Check client_id in data
docker-compose exec postgres psql -U postgres -d pulse_db \
  -c "SELECT DISTINCT client_id FROM integrations;"

# Verify CLIENT_NAME environment variable
docker-compose exec etl-wex env | grep CLIENT_NAME
```

### **Performance Issues**
```bash
# Monitor resource usage
docker stats

# Check database performance
docker-compose exec postgres psql -U postgres -d pulse_db \
  -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# Optimize database
docker-compose exec postgres psql -U postgres -d pulse_db \
  -c "VACUUM ANALYZE;"

# Check table sizes
docker-compose exec postgres psql -U postgres -d pulse_db \
  -c "SELECT schemaname,tablename,pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size FROM pg_tables WHERE schemaname='public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;"
```

### **Development vs Production Issues**

#### **Environment File Differences**
```bash
# Development: Manual environment setup
cat .env.shared .env.etl.wex > .env

# Production: Docker Compose handles environment
docker-compose -f docker-compose.multi-client.yml up -d

# Check which method you're using
ls -la .env*
```

#### **Dependency Installation Issues**
```bash
# Use centralized requirements management
python scripts/install_requirements.py all

# Check virtual environment
cd services/etl-service
python -c "import sys; print(sys.prefix)"

# Reinstall specific service
python scripts/install_requirements.py etl-service --force
```

## 📋 **Quick Reference**

### **Most Common Operations**

#### **🚀 Start Platform (Docker - Recommended)**
```bash
# Start all services
./start-multi-instance.sh

# Or manually
docker-compose -f docker-compose.multi-client.yml up -d
```

#### **🔧 Manual Development Setup**
```bash
# 1. Install dependencies
python scripts/install_requirements.py all

# 2. Create environment files
cat .env.shared .env.etl.wex > .env

# 3. Run migrations
python scripts/migration_runner.py

# 4. Start services
cd services/etl-service
cat ../../.env.shared ../../.env.etl.wex > .env
python -m uvicorn app.main:app --reload --port 8000
```

#### **🗄️ Database Operations**
```bash
# Run migrations (requires root .env file)
cat .env.shared .env.etl.wex > .env
python scripts/migration_runner.py

# Reset database (development only)
cd services/etl-service
python scripts/reset_database.py --all

# Connect to database
docker-compose exec postgres psql -U postgres -d pulse_db
```

#### **🔍 Troubleshooting**
```bash
# Check environment files
ls -la .env*
head -5 .env

# Check service logs
docker-compose -f docker-compose.multi-client.yml logs etl-wex

# Test API connections
cd services/etl-service
python scripts/test_jobs.py --test-connection

# Check service status
docker-compose -f docker-compose.multi-client.yml ps
```

#### **🌐 Service URLs**
- **Frontend**: http://localhost:5173
- **ETL Dashboard**: http://localhost:8000
- **Backend API**: http://localhost:3002
- **ETL API Docs**: http://localhost:8000/docs (admin required)

## 📚 **Additional Resources**

### **API Documentation**
- **ETL Service:** http://localhost:8000/docs
- **Backend Service:** http://localhost:3002/docs
- **AI Service:** http://localhost:8001/docs

### **Development Tools**
- **Database Admin:** pgAdmin or similar
- **API Testing:** Postman, curl
- **Log Analysis:** Docker logs, application logs

### **Platform Documentation**
- **[📚 Documentation Index](docs/DOCUMENTATION_INDEX.md)** - Complete documentation navigation
- **[🔧 Environment Setup](docs/ENVIRONMENT_SETUP.md)** - Service-specific environment configuration
- **[🚀 Multi-Instance Setup](docs/MULTI_INSTANCE_SETUP.md)** - Multi-client ETL deployment guide
- **[🤖 Agent Guidance](docs/AGENT_GUIDANCE.md)** - Essential guidance for Augment Code agents
- **[Architecture Guide](docs/ARCHITECTURE.md)** - System architecture and design
- **[Migration Guide](docs/MIGRATION_GUIDE.md)** - Database migration system
- **[Scripts Guide](docs/SCRIPTS_GUIDE.md)** - Cross-service scripts and utilities

### **Service Documentation**
- **[ETL Development Guide](services/etl-service/docs/DEVELOPMENT_GUIDE.md)** - ETL service development and testing
- **[ETL Service README](services/etl-service/README.md)** - ETL service overview and features
- **[Backend Service README](services/backend-service/README.md)** - Backend service development guide
- **[Frontend README](services/frontend-app/README.md)** - Frontend application guide

### **Testing Documentation**
- **[🧪 Test Overview](tests/README.md)** - Integration and validation tests
- **[🚨 Security Tests](tests/test_client_isolation_security.py)** - Critical client isolation validation
- **[🔧 Functionality Tests](tests/test_client_name_lookup.py)** - Client name lookup validation
- **[🏗️ Architecture Tests](tests/test_per_client_orchestrators.py)** - Multi-instance setup validation

### **External Documentation**
- **Jira API:** https://developer.atlassian.com/cloud/jira/platform/rest/v3/
- **GitHub API:** https://docs.github.com/en/rest
- **Docker Compose:** https://docs.docker.com/compose/
