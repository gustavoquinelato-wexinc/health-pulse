# Requirements Structure

This directory contains centralized dependency management for the Pulse Platform services.

## 📁 Files

- **`common.txt`** - Shared dependencies across all services (FastAPI, SQLAlchemy, etc.)
- **`etl-service.txt`** - ETL Service specific dependencies (includes common.txt)
- **`backend-service.txt`** - Backend Service specific dependencies (includes common.txt)
- **`auth-service.txt`** - Auth Service specific dependencies (API-only; includes minimal web + JWT)

## 🚀 Installation

### From Root Directory (Recommended)

```bash
# Install for specific service
python scripts/install_requirements.py etl-service
python scripts/install_requirements.py backend-service
python scripts/install_requirements.py auth-service

# Install for all services
python scripts/install_requirements.py all
```

### Direct Installation

```bash
# From service directory
cd services/etl-service
pip install -r requirements.txt

cd services/backend-service  
pip install -r requirements.txt
```

## 🎯 Benefits

- **Centralized Management**: All dependencies defined in one place
- **Shared Dependencies**: Common packages defined once in `common.txt`
- **Service Isolation**: Each service gets only what it needs
- **Virtual Environment Support**: Automatic venv creation per service
- **Cross-Platform**: Works on Windows, Linux, and macOS

## 📦 Dependency Categories

### Common Dependencies
- FastAPI, Uvicorn - Web framework
- SQLAlchemy, psycopg2 - Database
- Pydantic - Data validation
- Structlog - Logging
- PyJWT, bcrypt - Security

### ETL Service Specific
- APScheduler - Job scheduling
- Jira - Jira API client
- Redis - Caching
- Jinja2 - Web templates
- psutil - System monitoring

### Backend Service Specific
- httpx - HTTP client for service communication
- cryptography - Additional encryption utilities

## 🔧 Adding New Dependencies

1. **Shared dependency**: Add to `common.txt`
2. **Service-specific**: Add to appropriate service file
3. **Reinstall**: Run installation script to update

## 🚨 Important Notes

- Always use the installation script from the root directory
- Each service can have its own virtual environment
- Dependencies are installed in the service directory, not root
- Common dependencies are automatically included via `-r common.txt`
