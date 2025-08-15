# Pulse Platform

**Enterprise-Grade DevOps Analytics & Project Intelligence Platform**

Pulse Platform is a comprehensive, multi-tenant SaaS solution designed for senior leadership and C-level executives to gain deep insights into their software development lifecycle. Built with enterprise-scale architecture, the platform provides real-time analytics, DORA metrics, and intelligent project tracking across multiple clients and teams.

## 🚀 Platform Overview

### What is Pulse Platform?

Pulse Platform transforms raw development data into actionable business intelligence. By integrating with your existing tools (Jira, GitHub, and more), it provides a unified view of your engineering performance, project health, and delivery metrics.

**Key Capabilities:**
- **DORA Metrics**: Lead Time, Deployment Frequency, Change Failure Rate, Recovery Time
- **Project Intelligence**: Real-time project status, risk assessment, delivery predictions
- **Multi-Source Integration**: Seamless data aggregation from Jira, GitHub, and other tools
- **Executive Dashboards**: C-level friendly visualizations and KPIs
- **Multi-Tenant Architecture**: Secure client isolation with enterprise-grade security
### Why Pulse Platform?

**🏢 Enterprise-Ready**
- Multi-tenant SaaS architecture with complete client isolation
- Primary-replica database setup for high availability and performance
- Comprehensive RBAC system with granular permissions
- Client-specific logging and audit trails

**📊 Business Intelligence**
- Transform development metrics into business insights
- Identify bottlenecks and optimization opportunities
- Track delivery performance against commitments
- Predictive analytics for project outcomes

**🔧 Robust & Scalable**
- Microservices architecture with independent scaling
- Event-driven job orchestration with recovery strategies
- Real-time WebSocket updates and notifications
- Docker-based deployment with production-ready configurations

**🎨 Executive Experience**
- Clean, professional UI designed for senior leadership
- Customizable color schemes and branding per client
- User-specific light/dark mode preferences with enterprise aesthetics
- Mobile-responsive design for on-the-go access

## 🏗️ Architecture Highlights

**Four-Tier Microservices Architecture:**
- **Frontend App** (React/TypeScript): Executive dashboards and user interface
- **Backend Service** (FastAPI/Python): User management, RBAC, API gateway, and analytics
- **ETL Service** (FastAPI/Python): Data processing, job orchestration, and integrations
- **Auth Service** (FastAPI/Python): API-only authentication validation backend

**Technology Stack:**
- **Frontend**: React 18, TypeScript, Tailwind CSS, Vite
- **Backend**: FastAPI, SQLAlchemy, Pandas/NumPy, WebSockets, Redis
- **Database**: PostgreSQL with primary-replica setup
- **Infrastructure**: Docker, Redis caching, real-time WebSocket updates

## 🧭 Navigation UX
- All sidebar and submenu items support native browser interactions: right-click → Open link in new tab, middle-click, and Cmd/Ctrl+click. We achieve this by rendering real anchor links (React Router Links in the frontend; <a href> in ETL).

## 🎨 Design System & Colors
- See docs/design-system.md for color tokens and rules (on-color, on-gradient) and first-paint fallback strategy.
- Backend exposes both default_colors and custom_colors; the frontend and ETL set CSS vars accordingly.

**Enterprise Features:**
- PostgreSQL primary-replica setup for high availability
- Redis caching for optimal performance
- **Secure API-only authentication service**
- **Cross-service authentication and OKTA integration ready**
- JWT-based authentication with session management
- Client-specific data isolation and security
- Real-time job monitoring and recovery capabilities

## 📚 Documentation

This platform includes comprehensive documentation to help you understand, deploy, and maintain the system:

### Core Documentation

| Document | Description |
|----------|-------------|
| **[Architecture Guide](docs/architecture.md)** | System design, topology, multi-tenancy, database setup, Docker configurations |
| **[Security & Authentication](docs/security-authentication.md)** | RBAC, JWT tokens, permissions, client isolation, security best practices |
| **[Jobs & Orchestration](docs/jobs-orchestration.md)** | ETL jobs, orchestrator, recovery strategies, Jira/GitHub integrations |
| **[System Settings](docs/system-settings.md)** | Configuration reference, settings explanation, customization options |
| **[Installation & Setup](docs/installation-setup.md)** | Requirements, deployment, database setup, getting started guide |

### API Documentation

The platform provides comprehensive API documentation through OpenAPI/Swagger:

- **Auth Service**: `http://localhost:4000/health` (API-only authentication backend)
- **Backend Service API**: `http://localhost:3001/docs`
- **ETL Service API**: `http://localhost:8000/docs`

## 🎯 Target Audience

**Primary Users:**
- **C-Level Executives**: Strategic insights and high-level metrics
- **Engineering Directors**: Team performance and delivery tracking
- **Project Managers**: Project health and timeline monitoring
- **DevOps Teams**: System administration and maintenance

**Use Cases:**
- Executive reporting and board presentations
- Engineering performance optimization
- Project delivery predictability
- Resource allocation decisions
- Technical debt and risk assessment

## 🌟 Key Differentiators

**Enterprise-Grade Security**
- Multi-tenant architecture with complete client isolation
- Comprehensive audit logging and compliance features
- Role-based access control with granular permissions

**Intelligent Analytics**
- DORA metrics with industry benchmarking
- Predictive project delivery analytics
- Automated risk detection and alerting

**Seamless Integration**
- Native Jira and GitHub connectors
- Extensible architecture for additional integrations
- Real-time data synchronization

**Executive Experience**
- Purpose-built for senior leadership consumption
- Clean, professional interface with customizable branding
- Mobile-responsive design for executive mobility

## 🚀 Getting Started

### **⚡ Quick Setup (Recommended)**

```bash
# 1. Clone repository
git clone <repository-url>
cd pulse-platform

# 2. One-command development setup
python scripts/setup_development.py

# 3. Configure environment files (automatically created)
nano .env  # Edit with your database and API credentials

# 4. Start database and run migrations
docker-compose -f docker-compose.db.yml up -d
python services/backend-service/scripts/migration_runner.py --apply-all

# 5. Start services (virtual environments already created!)
# Backend: cd services/backend-service && venv/Scripts/activate && uvicorn app.main:app --reload --port 3001
# ETL: cd services/etl-service && venv/Scripts/activate && uvicorn app.main:app --reload --port 8000
# Frontend: cd services/frontend-app && npm run dev
```

**What the setup script does:**
- ✅ Creates Python virtual environments for all services
- ✅ Installs all dependencies (FastAPI, pandas, numpy, websockets, etc.)
- ✅ Installs Node.js dependencies for frontend
- ✅ Copies `.env.example` files to `.env` for all services
- ✅ Cross-platform support (Windows, Linux, macOS)

### **📚 Comprehensive Guide**

For detailed setup instructions, see our [Installation & Setup Guide](docs/installation-setup.md) which covers:

1. **Prerequisites**: System requirements and dependencies
2. **Database Setup**: PostgreSQL primary-replica configuration
3. **Service Deployment**: Docker-based deployment strategies
4. **Initial Configuration**: Client setup and system settings
5. **Integration Setup**: Connecting Jira and GitHub

## 📞 Support & Maintenance

Pulse Platform is designed for enterprise reliability with comprehensive monitoring, logging, and recovery capabilities. The platform includes:

- **Health Monitoring**: Real-time system health checks
- **Automated Recovery**: Self-healing job orchestration
- **Comprehensive Logging**: Client-specific audit trails
- **Performance Metrics**: Built-in performance monitoring

---

**Built for Enterprise. Designed for Executives. Engineered for Scale.**

*Pulse Platform - Transforming Development Data into Business Intelligence*


















