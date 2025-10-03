# Pulse Authentication Service - API Only

Pure backend authentication validation service for the Pulse Platform. **No user interface** - API only service.

## 🏗️ Architecture

The Authentication Service is a backend API that validates credentials and generates tokens:

- **Frontend Service** (Port 5173) → Backend Service → Auth Service (API)
- **ETL Frontend** (Port 3333) → Backend Service → Auth Service (API)
- **Backend Service** (Port 3001) → Calls Auth Service for validation
- **Legacy ETL Service** (Port 8000) → ⚠️ DEPRECATED - Reference only

## 🔐 Secure Authentication Flow

### 1. User Login (No Redirect)
```
User → Frontend/ETL Login Page → Backend Service
```

### 2. Credential Validation
```
Backend Service → Auth Service API → Credential Validation
```

### 3. Token Generation
```
Auth Service → JWT Token → Backend Service → Frontend/ETL Frontend
```

### 4. API Access
```
Frontend/ETL Frontend → Backend Service (with token) → Auth Service Validation
```

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL database (shared with other services)
- Redis (optional, for production caching)

### Installation

1. **Install dependencies:**
```bash
cd services/auth-service
pip install -r requirements.txt
```

2. **Environment Configuration:**
The auth service uses the same `.env` file as other services in the project root.

3. **Run the service:**
```bash
# Development
python -m uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload

# Production
python -m uvicorn app.main:app --host 0.0.0.0 --port 4000
```

## 📡 API Endpoints - No UI

### Authentication API Endpoints

#### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "auth-service",
  "version": "1.0.0"
}
```

#### `POST /api/v1/validate-credentials`
Validates user credentials against backend service.

**Request Body:**
```json
{
  "email": "admin@pulse.com",
  "password": "pulse"
}
```

**Response:**
```json
{
  "valid": true,
  "user": {
    "id": 2,
    "email": "admin@pulse.com",
    "role": "admin",
    "is_admin": true,
    "client_id": 1
  },
  "error": null
}
```

#### `POST /api/v1/generate-token`
Generates JWT token for validated user.

**Request Body:**
```json
{
  "email": "admin@pulse.com",
  "password": "pulse"
}
```

**Response:**
```json
{
  "access_token": "jwt_token_here",
  "token_type": "Bearer",
  "expires_in": 86400,
  "user": {
    "id": 2,
    "email": "admin@pulse.com",
    "role": "admin",
    "is_admin": true,
    "client_id": 1
  }
}
```

### Utility Endpoints

#### `GET /health`
Health check endpoint.

#### `GET /logout`
Centralized logout endpoint.

## 🔧 Configuration

### Registered Services

Services must be registered in the `REGISTERED_SERVICES` configuration:

```python
REGISTERED_SERVICES = {
    "frontend": {
        "name": "Pulse Frontend",
        "redirect_uris": [
            "http://localhost:3000/auth/callback",
            "https://app.company.com/auth/callback"
        ],
        "allowed_scopes": ["read", "write", "admin"]
    },
    "etl-frontend": {
        "name": "Pulse ETL Frontend",
        "redirect_uris": [
            "http://localhost:3333/auth/callback",
            "https://etl.company.com/auth/callback"
        ],
        "allowed_scopes": ["read", "write", "admin"]
    }
}
```

### Environment Variables

Uses the same environment variables as other Pulse Platform services:

- `JWT_SECRET_KEY` - Secret key for JWT token signing
- `JWT_ALGORITHM` - JWT algorithm (default: HS256)
- `POSTGRES_*` - Database connection settings

## 🔒 Security Features

- **Authorization Code Flow**: Secure OAuth-like flow
- **JWT Tokens**: Stateless authentication tokens
- **CSRF Protection**: State parameter validation
- **Redirect URI Validation**: Prevents redirect attacks
- **Code Expiration**: Authorization codes expire in 10 minutes
- **Single Use Codes**: Authorization codes can only be used once

## 🌐 Cross-Domain Support

The service is designed to work across different domains:

- **Development**: `localhost` with different ports
- **Production**: Different subdomains (e.g., `auth.company.com`, `app.company.com`)

CORS is configured to allow requests from all registered service domains.

## 📝 Integration Guide

See the main project documentation for integrating services with the centralized auth service.

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app
```

## 📊 Monitoring

- Health check: `GET /health`
- Logs: Structured logging with request tracing
- Metrics: Integration with platform monitoring (future)
