# ETL Service - Jira to Snowflake Data Pipeline

The ETL Service is the primary component of the Kairus Platform, responsible for extracting data from Jira (including the dev_status endpoint) and loading it into a Snowflake Data Warehouse.

## 🎯 Features

### Core Functionality
- **Deep Jira Data Extraction**: Complete extraction including dev_status endpoint
- **Snowflake Integration**: Direct loading into Snowflake Data Warehouse
- **Scheduled Jobs**: Automated ETL processes with APScheduler
- **Real-time Processing**: On-demand ETL job execution
- **Data Validation**: Comprehensive data quality checks

### Technical Features
- **FastAPI Framework**: High-performance async API
- **SQLAlchemy ORM**: Database abstraction and migrations
- **Caching System**: Redis/In-memory caching for performance
- **Security Middleware**: Authentication, rate limiting, input validation
- **Monitoring**: Health checks, structured logging, metrics
- **Error Handling**: Comprehensive error tracking and recovery

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│      Jira       │    │   ETL Service   │    │   Snowflake     │
│                 │───►│                 │───►│                 │
│  - Issues       │    │  - Extraction   │    │  - Issues       │
│  - Projects     │    │  - Transform    │    │  - Projects     │
│  - Dev Status   │    │  - Validation   │    │  - Dev Data     │
│  - Users        │    │  - Loading      │    │  - Users        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 Project Structure

```
etl-service/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── api/
│   │   ├── __init__.py
│   │   ├── etl_routes.py       # ETL job endpoints
│   │   └── admin_routes.py     # Admin endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Configuration management
│   │   ├── database.py         # Database connections
│   │   ├── logging_config.py   # Logging setup
│   │   ├── middleware.py       # Security middleware
│   │   ├── security.py         # Security utilities
│   │   ├── cache.py           # Caching system
│   │   └── utils.py           # Utility functions
│   ├── jobs/
│   │   ├── __init__.py
│   │   └── jira_job.py        # Jira extraction jobs
│   ├── models/
│   │   ├── __init__.py
│   │   └── unified_models.py   # Database models
│   └── schemas/
│       ├── __init__.py
│       └── api_schemas.py      # Pydantic schemas
├── tests/
│   ├── __init__.py
│   ├── test_api/
│   ├── test_jobs/
│   └── test_models/
├── scripts/
│   └── init_db.py             # Database initialization
├── logs/                      # Application logs
├── Dockerfile
├── requirements.txt
├── pytest.ini
├── .env.example
└── README.md
```

## 🚀 Quick Start

### Using Docker (Recommended)

1. **From the monorepo root**:
```bash
cd kairus-platform
docker-compose up etl-service
```

2. **Access the service**:
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Admin Interface: http://localhost:8000/admin

### Local Development

1. **Install dependencies**:
```bash
cd services/etl-service
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your Jira and Snowflake credentials
```

3. **Run the service**:
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Application Settings
DEBUG=true
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
SECRET_KEY=your-secret-key
ENCRYPTION_KEY=your-32-byte-encryption-key

# Snowflake Configuration
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_SCHEMA=your_schema
SNOWFLAKE_WAREHOUSE=your_warehouse

# Jira Configuration
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your_email@domain.com
JIRA_TOKEN=your_api_token

# Job Configuration
JIRA_JOB_INTERVAL_HOURS=24
```

### Jira API Token Setup

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Create a new API token
3. Use your email as username and the token as password

## 📊 API Endpoints

### ETL Operations
- `POST /api/v1/etl/jira/extract` - Start Jira extraction
- `GET /api/v1/etl/jobs/{job_id}` - Get job status
- `GET /api/v1/etl/jobs` - List all jobs

### Administration
- `GET /api/v1/admin/integrations` - List integrations
- `POST /api/v1/admin/integrations` - Create integration
- `GET /api/v1/admin/health` - Detailed health check

### Monitoring
- `GET /health` - Basic health check
- `GET /docs` - API documentation
- `GET /redoc` - Alternative documentation

## 🔄 ETL Process Flow

1. **Authentication**: Validate Jira credentials
2. **Project Discovery**: List available Jira projects
3. **Issue Extraction**: Extract issues with all fields
4. **Dev Status Extraction**: Get development status data
5. **Data Transformation**: Clean and normalize data
6. **Data Validation**: Ensure data quality
7. **Snowflake Loading**: Load data into warehouse
8. **Job Completion**: Update job status and logs

## 🧪 Testing

Run the test suite:

```bash
# All tests
python -m pytest

# Specific test categories
python -m pytest tests/test_api/
python -m pytest tests/test_jobs/
python -m pytest tests/test_models/

# With coverage
python -m pytest --cov=app
```

## 📈 Monitoring

### Health Checks
- Application health: `/health`
- Database connectivity: Included in health response
- Jira connectivity: Validated during job execution

### Logging
- Structured JSON logging
- Log levels: DEBUG, INFO, WARNING, ERROR
- Request/response logging
- Job execution tracking

### Metrics
- Job execution times
- Success/failure rates
- Data volume processed
- API response times

## 🔐 Security

- JWT token authentication
- API rate limiting
- Input validation and sanitization
- SQL injection prevention
- CORS configuration
- Security headers

## 🐛 Troubleshooting

### Common Issues

1. **Snowflake Connection Failed**
   - Verify credentials in `.env`
   - Check network connectivity
   - Ensure warehouse is running

2. **Jira Authentication Failed**
   - Verify API token is valid
   - Check username format (email)
   - Ensure Jira URL is correct

3. **Job Stuck in Running State**
   - Check application logs
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
