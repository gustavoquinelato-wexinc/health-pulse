# Requirements Structure

This directory contains centralized dependency management for the Pulse Platform **Python services**.

> **Note**: The frontend service (Node.js/React) uses `package.json` for dependency management.

## 📁 Files

- **`common.txt`** - Shared dependencies across all services (FastAPI, SQLAlchemy, etc.)
- **`backend-service.txt`** - Backend Service specific dependencies (includes ETL and common.txt)
- **`auth-service.txt`** - Auth Service specific dependencies (API-only; includes minimal web + JWT)
- **`etl-service.txt`** - Legacy ETL dependencies (kept for reference, ETL now integrated in backend-service)

## 🚀 Installation

### Complete Setup (Recommended for New Developers)

```bash
# One-command setup: creates virtual environments + installs all dependencies
python scripts/setup_development.py

# This automatically handles:
# - Python virtual environments for all services
# - All Python dependencies (including new additions)
# - Node.js dependencies for frontend
# - Environment file setup
```

### Individual Service Installation

```bash
# Install for specific service
python scripts/install_requirements.py backend-service
python scripts/install_requirements.py auth-service

# Install for all services
python scripts/install_requirements.py all
```

### Direct Installation

```bash
# From service directory
cd services/backend-service
pip install -r requirements.txt

cd services/auth-service
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

### Backend Service Specific (includes ETL)
- httpx - HTTP client for service communication
- cryptography - Additional encryption utilities
- **pandas** - Data processing and analytics
- **numpy** - Numerical computing
- **websockets** - Real-time updates and notifications
- **pika** - RabbitMQ client for ETL queue management
- **qdrant-client** - Qdrant vector database client for AI/embeddings
- **pika** - RabbitMQ client for ETL queue management
- **qdrant-client** - Qdrant vector database client for AI/embeddings
- APScheduler - Job scheduling (ETL)
- Jira - Jira API client (ETL)
- Redis - Caching (ETL)
- psutil - System monitoring (ETL)

### Auth Service Specific
- Minimal dependencies for authentication and JWT handling

## 🔧 Adding New Dependencies

1. **Shared dependency**: Add to `common.txt`
2. **Service-specific**: Add to appropriate service file
3. **Reinstall**: Run installation script to update

### Recent Changes (2025-12-18)

**Architecture Update:**
- ETL functionality has been integrated into `backend-service`
- All ETL dependencies are now part of `backend-service.txt`
- The `etl-service.txt` file is kept for reference only

**Backend Service (includes ETL):**
- `pandas` - Data processing and statistical analysis
- `numpy` - Numerical computing operations
- `websockets` - Real-time WebSocket communication
- `pika` - RabbitMQ Python client for queue management
- `qdrant-client` - Qdrant vector database client for embeddings
- `APScheduler` - Job scheduling for ETL
- `Jira` - Jira API client for ETL
- `psutil` - System monitoring for ETL

## 🚨 Important Notes

- Always use the installation script from the root directory
- Each service can have its own virtual environment
- Dependencies are installed in the service directory, not root
- Common dependencies are automatically included via `-r common.txt`

