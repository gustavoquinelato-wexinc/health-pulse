# Pulse Platform - Software Engineering Intelligence Platform

A comprehensive ETL platform for integrating and processing data from multiple sources including Jira, GitHub, Aha!, and Azure DevOps for development workflow analytics and project management insights.

## 🏗️ Architecture Overview

Pulse Platform follows a microservices architecture with secure service communication:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Frontend       │    │  Backend        │    │  ETL Service    │
│  (React SPA)    │◄──►│  (API Gateway)  │◄──►│  (Data Engine)  │
│  Port: 3000     │    │  Port: 5000     │    │  Port: 8000     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │  PostgreSQL     │    │  Redis Cache    │
                       │  (Main DB)      │    │  (Optional)     │
                       │  Port: 5432     │    │  Port: 6379     │
                       └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │  External APIs  │
                                               │ Jira • GitHub   │
                                               │ Aha! • Azure    │
                                               └─────────────────┘
```

## 📁 Project Structure

```
pulse-platform/
├── docs/                     # Comprehensive documentation
│   ├── architecture/         # System design documents
│   ├── etl/                  # ETL-specific documentation
│   └── deployment/           # Deployment guides
├── services/
│   ├── etl-service/          # ✅ COMPLETE - Python FastAPI ETL engine
│   ├── backend-service/      # 🔄 PLANNED - API gateway and auth
│   └── frontend-service/     # 🔄 PLANNED - React dashboard
├── scripts/                  # Utility scripts
├── docker-compose.yml        # Service orchestration
└── README.md
```

## 🚀 Services

### **ETL Service** (`/services/etl-service/`) ✅ **COMPLETE**
- **Purpose**: Core data extraction, transformation, and loading engine
- **Technology**: Python 3.11+, FastAPI, SQLAlchemy, APScheduler
- **Database**: PostgreSQL (migrated from Snowflake)
- **Features**:
  - **Multi-source ETL**: Jira, GitHub, Aha!, Azure DevOps
  - **Job Orchestration**: Active/Passive model with smart scheduling
  - **Checkpoint Recovery**: Precise failure recovery with cursor-based pagination
  - **Rate Limit Handling**: Graceful API rate limit management
  - **Real-time Dashboard**: Live job monitoring and control
  - **Pause/Resume**: Intelligent job control with status management
- **Port**: 8000
- **Documentation**: [ETL Service README](services/etl-service/README.md)

### **Backend Service** (`/services/backend-service/`) 🔄 **PLANNED**
- **Purpose**: API gateway, authentication, and business logic
- **Technology**: Node.js/Python (TBD)
- **Features**:
  - **JWT Authentication**: User authentication and session management
  - **ETL Proxy**: Secure proxy to ETL service APIs
  - **RBAC Permissions**: Role-based access control
  - **API Aggregation**: Unified API layer for frontend
- **Port**: 5000
- **Documentation**: [Backend Service README](services/backend-service/README.md)

### **Frontend Service** (`/services/frontend-service/`) 🔄 **PLANNED**
- **Purpose**: React-based user interface and dashboard
- **Technology**: React, TypeScript, Tailwind CSS
- **Features**:
  - **ETL Dashboard**: Real-time job monitoring and controls
  - **Analytics Views**: Data visualization and insights
  - **User Management**: Authentication and role management
  - **Responsive Design**: Mobile-friendly interface
- **Port**: 3000
- **Documentation**: [Frontend Service README](services/frontend-service/README.md)

## 📊 Supported Integrations

| Integration | Status | Features | Recovery |
|-------------|--------|----------|----------|
| **Jira** | ✅ Active | Issues, Projects, Users, Custom Fields, Dev Status | ✅ Checkpoint-based |
| **GitHub** | ✅ Active | Repositories, Pull Requests, Commits, Reviews, Comments | ✅ Cursor-based |
| **Aha!** | 🔄 Planned | Features, Releases, Ideas, Goals | 🔄 TBD |
| **Azure DevOps** | 🔄 Planned | Work Items, Repositories, Pipelines, Builds | 🔄 TBD |

## 🔧 Quick Start

### Prerequisites
- Docker & Docker Compose
- Git
- PostgreSQL (local or Docker)
- API tokens for integrations (Jira, GitHub, etc.)

### 1. Clone Repository
```bash
git clone <repository-url>
cd pulse-platform
```

### 2. Environment Setup
```bash
# Copy environment template
cp services/etl-service/.env.example services/etl-service/.env

# Edit with your configuration
nano services/etl-service/.env
```

### 3. Start ETL Service
```bash
# Using Docker
docker-compose up etl-service

# Or locally
cd services/etl-service
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Access Applications
- **ETL Dashboard**: http://localhost:8000
- **ETL API**: http://localhost:8000/docs (Swagger UI)
- **Health Check**: http://localhost:8000/health

## 📚 Documentation

### **Architecture & Design**
- [System Architecture](docs/architecture/overview.md) - Overall system design and patterns
- [Microservices Communication](docs/architecture/microservices.md) - Service interaction patterns
- [Security Design](docs/architecture/security.md) - Authentication and authorization

### **ETL System**
- [Recovery Strategy](docs/etl/recovery-strategy.md) - Checkpoint and failure recovery rules
- [Job Orchestration](docs/etl/job-orchestration.md) - Active/Passive job management
- [Checkpoint System](docs/etl/checkpoint-system.md) - Cursor-based recovery design

### **Deployment**
- [Docker Setup](docs/deployment/docker-setup.md) - Container orchestration
- [Environment Configuration](docs/deployment/environment-setup.md) - Configuration management

### **Service Documentation**
- [ETL Service](services/etl-service/README.md) - Complete ETL engine documentation
- [Backend Service](services/backend-service/README.md) - API gateway documentation
- [Frontend Service](services/frontend-service/README.md) - React dashboard documentation

## 🛠️ Development

### **Local Development**
```bash
# ETL Service (Primary)
cd services/etl-service
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --reload

# Backend Service (Planned)
cd services/backend-service
npm install
npm run dev

# Frontend Service (Planned)
cd services/frontend-service
npm install
npm start
```

### **Database Management**
```bash
# Reset ETL database
cd services/etl-service
python scripts/reset_database.py

# Initialize with sample data
python scripts/init_sample_data.py
```

## 📊 Data Flow

1. **External APIs** → ETL Service extracts data (Jira, GitHub, etc.)
2. **ETL Service** → Transforms and loads into PostgreSQL
3. **ETL Service** → Provides APIs for processed data
4. **Backend Service** → Proxies ETL APIs with authentication
5. **Frontend Service** → Displays dashboards and analytics

## 🔐 Security

- **Authentication**: JWT-based user authentication (planned)
- **Authorization**: Role-based access control (RBAC)
- **Service Communication**: Internal API keys and request signing
- **Data Protection**: Encrypted tokens and sensitive data
- **Network Security**: Service isolation and IP whitelisting
- **Input Validation**: Comprehensive request validation and sanitization

## 📈 Monitoring & Observability

- **Job Status**: Real-time job monitoring dashboard
- **Logs**: Structured logging with colored console output
- **Metrics**: Job execution metrics and performance tracking
- **Health Checks**: Service health monitoring endpoints
- **Error Tracking**: Comprehensive error logging and recovery
- **Rate Limit Monitoring**: API usage tracking and alerts

## 🧪 Testing

```bash
# ETL Service tests
cd services/etl-service
python -m pytest tests/ -v

# Integration tests
python -m pytest tests/integration/ -v

# Load testing
python scripts/load_test.py
```

## 🚀 Key Features

### **ETL Engine**
- ✅ **Multi-source Integration**: Jira, GitHub, Aha!, Azure DevOps
- ✅ **Checkpoint Recovery**: Precise failure recovery with cursor tracking
- ✅ **Rate Limit Handling**: Graceful API rate limit management
- ✅ **Job Orchestration**: Active/Passive model with smart scheduling
- ✅ **Real-time Dashboard**: Live job monitoring and control

### **Data Processing**
- ✅ **Bulk Operations**: Efficient batch processing for large datasets
- ✅ **Incremental Updates**: Only process changed data
- ✅ **Data Validation**: Comprehensive data quality checks
- ✅ **Relationship Mapping**: Automatic linking between data sources

### **Operational Excellence**
- ✅ **Pause/Resume**: Intelligent job control with status management
- ✅ **Force Start/Stop**: Manual job control with safety mechanisms
- ✅ **Recovery Strategies**: Different recovery patterns per integration
- ✅ **Monitoring**: Real-time status updates and progress tracking

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the `/docs` directory for comprehensive guides
- **Issues**: Create GitHub issues for bugs and feature requests
- **Development**: See service-specific README files for detailed setup
- **ETL Dashboard**: Access http://localhost:8000 for live monitoring

---

**Built with ❤️ for Software Engineering Intelligence and ETL Excellence** 🚀
