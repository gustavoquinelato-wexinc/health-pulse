# ETL Service - Pulse Platform Data Engine

A comprehensive FastAPI-based ETL service for extracting, transforming, and loading data from multiple sources including Jira, GitHub, Aha!, and Azure DevOps with intelligent job orchestration and checkpoint recovery.

## 🎯 Overview

The ETL Service is the core data processing engine of the Pulse Platform, designed for:

- **Multi-source Integration**: Jira, GitHub, Aha!, Azure DevOps
- **Intelligent Job Orchestration**: Active/Passive model with smart scheduling
- **Checkpoint Recovery**: Precise failure recovery with cursor-based pagination
- **Rate Limit Handling**: Graceful API rate limit management
- **Real-time Monitoring**: Live home page with job control capabilities
- **ML Data Preparation**: Enhanced data processing for AI capabilities (Phase 1+)
- **Vector-Ready Processing**: Data preparation for embedding generation (Phase 2+)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                ETL Service (AI Enhanced)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────┐  │
│  │   Web API       │    │  Job Engine     │    │  Data   │  │
│  │   (FastAPI)     │◄──►│  (Orchestrator) │◄──►│ Layer   │  │
│  │                 │    │                 │    │         │  │
│  │  • Dashboard    │    │  • Scheduling   │    │ • ORM   │  │
│  │  • REST APIs    │    │  • Execution    │    │ • Cache │  │
│  │  • Auth         │    │  • Recovery     │    │ • DB    │  │
│  │  • ML Monitoring│    │  • AI Monitoring│    │ • Vector│  │
│  └─────────────────┘    └─────────────────┘    └─────────┘  │
│                                │                            │
│                                ▼                            │
│                    ┌─────────────────────┐                  │
│                    │    Integrations     │                  │
│                    │                     │                  │
│                    │  ┌─────┐  ┌─────┐   │                  │
│                    │  │Jira │  │GitHub│   │                  │
│                    │  │ API │  │ API │   │                  │
│                    │  └─────┘  └─────┘   │                  │
│                    └─────────────────────┘                  │
│                                │                            │
│                                ▼                            │
│                    ┌─────────────────────┐                  │
│                    │   AI Data Prep      │ ← Phase 1        │
│                    │                     │                  │
│                    │  • Schema Compat    │                  │
│                    │  • Vector Prep      │                  │
│                    │  • ML Monitoring    │                  │
│                    └─────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
                   ┌─────────────────────────────┐
                   │   PostgreSQL (Enhanced)     │
                   │                             │
                   │  • Primary DB (Port 5432)   │
                   │  • Replica DB (Port 5433)   │
                   │  • pgvector Extension       │
                   │  • postgresml Extension     │
                   │  • Vector Indexes (HNSW)    │
                   │  • ML Monitoring Tables     │
                   └─────────────────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   AI Service    │ ← Phase 2+
                       │   (Future)      │
                       │   Port: 5000    │
                       └─────────────────┘
```

## 🚀 Features

### **Core ETL Capabilities**
- ✅ **Jira Integration**: Complete data extraction including dev_status
- ✅ **GitHub Integration**: GraphQL-based PR, commit, and review extraction
- ✅ **PostgreSQL Storage**: Unified data model with relationship mapping
- ✅ **Bulk Operations**: Efficient batch processing for large datasets
- ✅ **Data Validation**: Comprehensive data quality checks

### **Job Management**
- ✅ **Active/Passive Orchestration**: Single job execution with smart coordination
- ✅ **Checkpoint Recovery**: Precise failure recovery with state preservation
- ✅ **Fast Retry System**: Intelligent retry logic with configurable intervals (15min default)
- ✅ **Manual Controls**: Force start, stop, pause, and resume capabilities
- ✅ **Status Management**: Real-time job status tracking and transitions
- ✅ **Rate Limit Handling**: Graceful API rate limit detection and recovery

### **Monitoring & Control**
- ✅ **Real-time Dashboard**: Live job monitoring with control interface
- ✅ **WebSocket Updates**: Real-time progress updates and notifications *(recently added)*
- ✅ **Enhanced Log Management**: Table-based log viewer with pagination and individual file actions
- ✅ **Structured Logging**: Colored console logs with detailed execution tracking
- ✅ **Health Monitoring**: Service health checks and status reporting
- ✅ **Error Tracking**: Comprehensive error logging and recovery metrics
- ✅ **Performance Metrics**: Job execution timing and throughput monitoring

## 📁 Project Structure

```
etl-service/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── api/                    # Modular API endpoints
│   │   ├── health.py           # Health check endpoints
│   │   ├── jobs.py             # Job management endpoints
│   │   ├── data.py             # Data access endpoints
│   │   ├── home.py             # Home page endpoints
│   │   ├── logs.py             # Log management endpoints
│   │   ├── debug.py            # Debug endpoints
│   │   ├── scheduler.py        # Scheduler control endpoints
│   │   ├── admin_routes.py     # Legacy admin routes
│   │   └── web_routes.py       # Legacy web routes
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Configuration management (consolidated)
│   │   ├── database.py         # Database connections and session management
│   │   ├── cache.py            # Redis caching layer
│   │   └── settings_manager.py # Dynamic settings management
│   ├── jobs/
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # Job orchestration engine
│   │   ├── jira/
│   │   │   ├── jira_job.py     # Jira ETL job implementation
│   │   │   └── jira_extractor.py # Jira API data extraction
│   │   └── github/
│   │       ├── github_job.py   # GitHub ETL job implementation
│   │       ├── github_graphql_extractor.py # GitHub GraphQL extraction
│   │       └── github_graphql_client.py    # GraphQL client
│   ├── models/
│   │   ├── __init__.py
│   │   └── unified_models.py   # Unified database models (PostgreSQL)
│   ├── templates/
│   │   └── home.html           # WebSocket-based real-time ETL home page
│   └── utils/
│       ├── __init__.py
│       ├── datetime_helper.py  # DateTime utilities
│       └── logging_utils.py    # Logging utilities
├── scripts/                    # Executable utilities (moved from utils)
│   ├── reset_database.py      # Database reset and initialization (includes integrations)
│   ├── generate_secret_key.py # Security key generation
│   └── test_jobs.py           # Job testing and debugging
├── logs/                      # Application logs (auto-created)
├── Dockerfile
├── requirements.txt
├── .env                      # Environment configuration (copy from root .env.example)
└── README.md
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 12+
- Git
- API tokens (Jira, GitHub)

### 1. Installation

#### **Quick Setup (Recommended)**
```bash
# Clone repository
git clone <repository-url>
cd pulse-platform

# One-command setup for ALL services (including ETL)
python scripts/setup_development.py

# ETL service is now ready with virtual environment and dependencies!
```

#### **Manual Setup (Alternative)**
```bash
# Clone repository
git clone <repository-url>
cd pulse-platform/services/etl-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies using centralized requirements
pip install -r ../../requirements/etl-service.txt
```

### 2. Configuration
```bash
# Copy environment template from root directory
cp ../../.env.example ../../.env

# Edit configuration with your settings
nano ../../.env
```

**Note**: The ETL service uses the root-level `.env` file for configuration. This ensures consistency across all services in the platform.

**Required Environment Variables:**
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/pulse_db

# Jira Integration
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token

# GitHub Integration
GITHUB_TOKEN=your-github-personal-access-token

# Optional: Redis Cache
REDIS_URL=redis://localhost:6379/0
```

### 3. Database Setup
```bash
# Reset and initialize database
python scripts/reset_database.py

# Verify database connection
python -c "from app.core.database import get_database; print('Database connected!')"
```

### 4. Start Service
```bash
# Development mode (recommended)
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. Access Applications
- **ETL Dashboard**: http://localhost:8000 (Login: gustavo.quinelato@wexinc.com / pulse)
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health

## 📊 Supported Integrations

| Integration | Status | Features | Recovery Strategy |
|-------------|--------|----------|-------------------|
| **Jira** | ✅ Active | Issues, Projects, Users, Custom Fields, Dev Status | Checkpoint-based restart |
| **GitHub** | ✅ Active | Repositories, Pull Requests, Commits, Reviews, Comments | Cursor-based resume |
| **Aha!** | 🔄 Planned | Features, Releases, Ideas, Goals | TBD |
| **Azure DevOps** | 🔄 Planned | Work Items, Repositories, Pipelines, Builds | TBD |

## ⚙️ Configuration

### Complete Environment Configuration

```bash
# Application Settings
DEBUG=true
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# Database Configuration (PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost:5432/pulse_db

# Jira Integration
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token

# GitHub Integration
GITHUB_TOKEN=your-github-personal-access-token

# Aha! Integration (Planned)
AHA_DOMAIN=your-domain.aha.io
AHA_API_KEY=your-aha-api-key

# Azure DevOps Integration (Planned)
AZURE_DEVOPS_ORG=https://dev.azure.com/your-org
AZURE_DEVOPS_TOKEN=your-azure-devops-token

# Optional: Redis Cache
REDIS_URL=redis://localhost:6379/0

# Security
JWT_SECRET_KEY=your-jwt-secret-key-here
SECRET_KEY=your-secret-key-change-this-in-production
ENCRYPTION_KEY=your-32-byte-encryption-key

# Job Configuration
ORCHESTRATOR_INTERVAL_MINUTES=60

# Fast Retry Configuration (Optional)
ORCHESTRATOR_RETRY_ENABLED=true
ORCHESTRATOR_RETRY_INTERVAL_MINUTES=15
ORCHESTRATOR_MAX_RETRY_ATTEMPTS=3
```

### API Token Setup

#### **Jira API Token**
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Create a new API token
3. Use your email as username and the token as password

#### **GitHub Personal Access Token**
1. Go to https://github.com/settings/tokens
2. Generate new token with `repo` and `read:org` scopes
3. Copy the token to your environment configuration

#### **Aha! API Key** (Planned)
1. Go to your Aha! account settings
2. Generate API key with read permissions
3. Add to environment configuration

## 📊 API Endpoints

### **Home & Authentication**
- `GET /` - ETL Home (redirects to login)
- `GET /login` - Login page
- `POST /auth/login` - User authentication
- `GET /home` - Main ETL home page

### **Job Management**
- `GET /api/v1/jobs/status` - Get all job statuses
- `POST /api/v1/jobs/{job_name}/start` - Force start specific job
- `POST /api/v1/jobs/{job_name}/set-active` - Set job as active (PENDING) and other as FINISHED
- `POST /api/v1/jobs/{job_name}/pause` - Pause specific job
- `POST /api/v1/jobs/{job_name}/unpause` - Unpause specific job

### **Orchestrator Control**
- `GET /api/v1/orchestrator/status` - Get orchestrator status
- `POST /api/v1/orchestrator/start` - Force start orchestrator
- `POST /api/v1/orchestrator/pause` - Pause orchestrator
- `POST /api/v1/orchestrator/resume` - Resume orchestrator

### **Monitoring & Logs**
- `GET /api/v1/logs/recent` - Get recent log entries with filtering and pagination
- `GET /api/v1/logs/files` - List all available log files with metadata
- `GET /api/v1/logs/download/{filename}` - Download specific log files (ZIP format)
- `DELETE /api/v1/logs/cleanup` - Bulk delete old log files by age
- `DELETE /api/v1/logs/file/{filename}` - Delete or clear individual log files
- `GET /api/v1/health` - Service health check
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation

### **WebSocket Endpoints**
- `WS /ws/progress/{job_name}` - Real-time job progress updates
- Supports: jira_sync, github_sync, orchestrator

## 🔄 ETL Process Flow

### **Jira ETL Process**
1. **Authentication**: Validate Jira API credentials
2. **Project Discovery**: List available Jira projects
3. **Issue Extraction**: Extract issues with all fields and custom fields
4. **Dev Status Extraction**: Get development status data from dev_status endpoint
5. **User Extraction**: Extract user information and relationships
6. **Data Transformation**: Clean, normalize, and validate data
7. **PostgreSQL Loading**: Bulk insert into unified database schema
8. **Checkpoint Save**: Save progress for recovery
9. **Job Completion**: Update job status and execution metrics

### **Fast Retry System**

The ETL service includes an intelligent fast retry system for handling job failures:

#### **How It Works**
1. **Normal Operation**: Jobs run on the main orchestrator interval (60 minutes default)
2. **Failure Detection**: When a job fails, the system automatically schedules a fast retry
3. **Fast Retry**: Failed jobs are retried at shorter intervals (15 minutes default)
4. **Max Attempts**: After maximum retry attempts (3 default), jobs fall back to normal interval
5. **Success Recovery**: Successful retry clears the retry count and returns to normal scheduling

#### **Configuration**
```bash
# Enable/disable fast retry system
ORCHESTRATOR_RETRY_ENABLED=true

# Fast retry interval (minutes)
ORCHESTRATOR_RETRY_INTERVAL_MINUTES=15

# Maximum retry attempts before falling back to normal interval
ORCHESTRATOR_MAX_RETRY_ATTEMPTS=3
```

#### **Benefits**
- **Faster Recovery**: Failed jobs retry quickly instead of waiting for the next hourly run
- **Reduced Downtime**: Transient failures are resolved within 15 minutes instead of up to 60 minutes
- **Intelligent Fallback**: Persistent failures don't spam the system - they fall back to normal intervals
- **Configurable**: All retry parameters can be adjusted via the dashboard or environment variables

### **GitHub ETL Process**
1. **Authentication**: Validate GitHub API token
2. **Repository Discovery**: Find repositories from Jira dev_status + pattern search
3. **GraphQL Extraction**: Extract PRs, commits, reviews, and comments using GraphQL
4. **Cursor Management**: Save pagination cursors for precise recovery
5. **Rate Limit Handling**: Graceful handling of API rate limits
6. **Data Transformation**: Normalize GitHub data to unified schema
7. **Issue Linking**: Link pull requests with Jira issues
8. **Bulk Loading**: Efficient batch insert operations
9. **Recovery State**: Save checkpoint for resumable processing

## 🧪 Testing

### **Unit Tests**
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v

# With coverage report
python -m pytest tests/ --cov=app --cov-report=html
```

### **Integration Tests**
```bash
# Test database operations
python -m pytest tests/integration/test_database.py -v

# Test API endpoints
python -m pytest tests/integration/test_api.py -v

# Test job execution
python -m pytest tests/integration/test_jobs.py -v
```

### **Manual Testing**
```bash
# Test ETL dashboard
curl http://localhost:8000/

# Test job status API
curl http://localhost:8000/api/v1/jobs/status

# Test health endpoint
curl http://localhost:8000/api/v1/health
```

## 📈 Monitoring & Observability

### **Real-time Home Page**
- **WebSocket Progress**: Real-time progress bars with instant percentage updates
- **Enhanced Log Management**: Table-based log viewer with pagination, search, and file management
- **Individual File Actions**: Download, delete, or clear content of specific log files
- **Bulk Operations**: Delete all logs or logs older than specified days
- **Job Status Monitoring**: Live job state tracking and transitions
- **Control Interface**: Manual job control (start, stop, pause, resume)
- **Professional UI**: Consistent dark theme with streamlined interface

### **Health Checks**
- **Application Health**: `/api/v1/health` endpoint with comprehensive status
- **Database Connectivity**: PostgreSQL connection and query testing
- **External API Health**: Jira and GitHub API connectivity validation
- **Job Status Health**: Orchestrator and job execution status

### **Logging System**
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Colored Console**: Development-friendly colored console output
- **Log Levels**: DEBUG, INFO, WARNING, ERROR with appropriate filtering
- **Request Tracking**: Complete request/response logging for debugging
- **Job Execution Logs**: Detailed ETL job execution tracking

### **Performance Metrics**
- **Job Execution Times**: Complete job duration and phase timing
- **Success/Failure Rates**: Job completion statistics and error rates
- **Data Volume Metrics**: Records processed, API calls made, data transferred
- **API Response Times**: External API performance monitoring
- **Recovery Metrics**: Checkpoint frequency and recovery success rates

## 🔐 Security

### **Authentication & Authorization**
- **Hardcoded Login**: Simple authentication (gustavo.quinelato@wexinc.com/pulse)
- **JWT Tokens**: Secure session management with token-based auth
- **Internal API Keys**: Service-to-service authentication (planned)
- **Role-Based Access**: User permission system (planned)

### **Data Protection**
- **Encrypted Tokens**: Secure storage of API tokens and credentials
- **Input Validation**: Comprehensive request validation and sanitization
- **SQL Injection Prevention**: Parameterized queries and ORM protection
- **Rate Limiting**: API request throttling and abuse prevention

### **Network Security**
- **CORS Configuration**: Cross-origin request security
- **Security Headers**: HTTP security headers for web dashboard
- **HTTPS Support**: SSL/TLS encryption for production deployments
- **Database Security**: Connection encryption and access control

## 🎯 Key Features Summary

### **✅ Implemented Features**
- **Multi-source ETL**: Jira and GitHub integration with unified data model
- **Job Orchestration**: Active/Passive model with intelligent scheduling
- **Checkpoint Recovery**: Precise failure recovery with cursor-based pagination
- **Fast Retry System**: Intelligent retry logic with configurable intervals and max attempts
- **Rate Limit Handling**: Graceful API rate limit detection and recovery
- **Real-time Dashboard**: Live job monitoring with manual control capabilities
- **Bulk Operations**: Efficient batch processing for large datasets
- **Data Validation**: Comprehensive data quality checks and error handling

### **🔄 Planned Features**
- **Additional Integrations**: Aha! and Azure DevOps support
- **Enhanced Security**: Full RBAC and service-to-service authentication
- **Advanced Analytics**: Data insights and trend analysis
- **Webhook Support**: Real-time event processing
- **API Gateway Integration**: Unified API access through backend service

## 🐛 Troubleshooting

### **Common Issues**

#### **1. Database Connection Failed**
```bash
# Check PostgreSQL connection
python -c "from app.core.database import get_database; get_database().test_connection()"

# Reset database if needed
python scripts/reset_database.py
```

#### **2. Jira Authentication Failed**
- Verify API token is valid and not expired
- Check email format in JIRA_EMAIL (must be exact Jira account email)
- Ensure JIRA_BASE_URL includes https:// and correct domain
- Test connection: `curl -u email:token https://domain.atlassian.net/rest/api/2/myself`

#### **3. GitHub Rate Limit Exceeded**
- Check rate limit status: `curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit`
- Wait for rate limit reset (usually 1 hour)
- Consider using multiple tokens for higher limits

#### **4. Job Stuck in RUNNING State**
- Check application logs for errors
- Restart service if necessary (jobs will resume from checkpoints)
- Check for database connection issues
- Jobs have built-in timeout and error handling

#### **5. Dashboard Login Issues**
- Use hardcoded credentials: `gustavo.quinelato@wexinc.com` / `pulse`
- Clear browser cache and cookies
- Check browser console for JavaScript errors
- Verify service is running on correct port (8000)

### **Debug Commands**

```bash
# Check service status (admin only)
curl http://localhost:8000/api/v1/health

# Check job status
curl http://localhost:8000/api/v1/jobs/status

# Debug system information
curl http://localhost:8000/api/v1/debug/system

# Test external connections
curl http://localhost:8000/api/v1/debug/connections

# View logs
tail -f logs/app.log

# Monitor real-time progress via WebSocket dashboard
# Visit http://localhost:8000/dashboard

# Test database connection
python -c "from app.core.database import get_database; print('DB OK')"

# Reset everything
python scripts/reset_database.py
```

### **Performance Optimization**

#### **Database Performance**
- Ensure PostgreSQL has sufficient memory allocation
- Monitor connection pool usage
- Use bulk operations for large datasets
- Regular database maintenance and vacuuming

#### **API Rate Limits**
- Monitor API usage in dashboard
- Implement exponential backoff for retries
- Use GraphQL for GitHub to reduce API calls
- Cache frequently accessed data

## 📚 Additional Documentation

- **[Development Guide](docs/development-guide.md)** - Complete development, testing, and debugging guide
- **[Log Management Guide](docs/log-management.md)** - Comprehensive log management system documentation
- **[System Architecture](../../docs/architecture.md)** - Overall system design
- **[Security & Authentication](../../docs/security-authentication.md)** - Security implementation
- **[Jobs & Orchestration](../../docs/jobs-orchestration.md)** - Job management system
- **[System Settings](../../docs/system-settings.md)** - Configuration reference
- **[Installation & Setup](../../docs/installation-setup.md)** - Setup guide

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with comprehensive tests
4. Ensure all tests pass (`python -m pytest`)
5. Update documentation as needed
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.

---

**🚀 Built with ❤️ for Software Engineering Intelligence and ETL Excellence**
   - Restart the service
   - Clear job cache if needed

### Debug Mode

Enable debug logging:
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

## 📚 Additional Resources

- [Jira REST API Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
- [Snowflake Python Connector](https://docs.snowflake.com/en/user-guide/python-connector.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## 🤝 Contributing

1. Follow the existing code structure
2. Add tests for new features
3. Update documentation
4. Follow Python PEP 8 style guide
5. Use type hints

---

**Part of the Kairus Platform - Software Engineering Intelligence**
