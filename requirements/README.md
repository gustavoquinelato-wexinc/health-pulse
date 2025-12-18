# Requirements Structure

This directory contains centralized dependency management for the Pulse Platform **Python services**.

> **Note**: The frontend services (Node.js/React) use `package.json` for dependency management.

## 📁 Files

- **`all.txt`** - All dependencies for both backend and auth services
- **`backend.txt`** - Backend Service dependencies (includes ETL, AI, and all core functionality)
- **`auth.txt`** - Auth Service dependencies (minimal JWT-based authentication)

## 🚀 Installation

### Complete Setup (Recommended for New Developers)

```bash
# One-command setup: creates virtual environments + installs all dependencies
python scripts/setup_development.py

# This automatically handles:
# - Python virtual environments for all services
# - All Python dependencies
# - Node.js dependencies for frontend
# - Environment file setup
```

### Individual Service Installation

```bash
# Install for specific service
python scripts/install_requirements.py backend
python scripts/install_requirements.py auth

# Install for all services
python scripts/install_requirements.py all
```

### Direct Installation

```bash
# From service directory
cd services/backend-service
pip install -r ../../requirements/backend.txt

cd services/auth-service
pip install -r ../../requirements/auth.txt
```

## 🎯 Benefits

- **Centralized Management**: All dependencies defined in one place
- **Service Isolation**: Each service gets only what it needs
- **Virtual Environment Support**: Automatic venv creation per service
- **Cross-Platform**: Works on Windows, Linux, and macOS
- **Simple Structure**: Just 3 files - all, backend, auth

## 📦 Dependency Categories

### Backend Service (backend.txt)
**Web Framework:**
- FastAPI, Uvicorn - Web framework and ASGI server

**Database:**
- SQLAlchemy, psycopg2-binary - ORM and PostgreSQL driver
- pgvector - PostgreSQL vector extension for AI

**Security:**
- PyJWT, bcrypt, cryptography - Authentication and encryption

**ETL & Queue Management:**
- APScheduler - Job scheduling
- pika - RabbitMQ client for queue management
- jira>=3.8.0 - Jira API client

**AI & Embeddings:**
- qdrant-client - Vector database client
- sqlglot>=20.0.0 - SQL validation and parsing

**Data Processing:**
- pandas - Data processing and analytics
- numpy - Numerical computing

**Communication:**
- httpx - HTTP client for service-to-service communication
- websockets - Real-time WebSocket updates
- redis - Caching and session management

**Utilities:**
- python-dotenv - Environment configuration
- pydantic[email] - Data validation
- structlog, colorama - Logging
- python-dateutil, pytz - Date/time handling
- psutil - System monitoring

### Auth Service (auth.txt)
**Minimal JWT-based authentication:**
- FastAPI, Uvicorn - Web framework
- PyJWT - JWT token handling
- httpx - Backend service communication
- pydantic - Data validation
- pytest - Testing framework

## 🔧 Adding New Dependencies

1. **Backend dependency**: Add to `backend.txt`
2. **Auth dependency**: Add to `auth.txt`
3. **Reinstall**: Run installation script to update

## 🚨 Important Notes

- Always use the installation script from the root directory
- Each service has its own virtual environment
- Dependencies are installed in the service directory, not root
- The `all.txt` file references both backend and auth files
