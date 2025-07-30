# Centralized Authentication Architecture

## Overview

The Pulse Platform now uses **centralized authentication** where all authentication and session management is handled by the **Backend Service**. This provides a single source of truth for user management, sessions, and security policies.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │  Backend        │    │  ETL Service    │
│   (React)       │    │  Service        │    │  (FastAPI)      │
│                 │    │  (FastAPI)      │    │                 │
│  ┌───────────┐  │    │  ┌───────────┐  │    │  ┌───────────┐  │
│  │   Auth    │──┼────┼─▶│   Auth    │  │    │  │   Auth    │  │
│  │ Context   │  │    │  │ Service   │  │    │  │Validation │──┼──┐
│  └───────────┘  │    │  └───────────┘  │    │  └───────────┘  │  │
└─────────────────┘    │  ┌───────────┐  │    └─────────────────┘  │
                       │  │ Session   │  │                         │
                       │  │Management │  │    ┌─────────────────┐  │
                       │  └───────────┘  │    │  Validation     │◀─┘
                       │  ┌───────────┐  │    │  Request        │
                       │  │   User    │  │    └─────────────────┘
                       │  │Management │  │
                       │  └───────────┘  │
                       └─────────────────┘
```

## Key Components

### 1. Backend Service (Authentication Provider)
- **Location**: `services/backend-service/`
- **Responsibilities**:
  - User authentication (login/logout)
  - JWT token generation and validation
  - Session management (create, list, revoke)
  - User management (CRUD operations)
  - Password hashing and verification

### 2. Frontend (Authentication Consumer)
- **Location**: `services/frontend-app/`
- **Responsibilities**:
  - Login form and user interface
  - Token storage (localStorage)
  - Automatic token validation on app startup
  - Session management UI

### 3. ETL Service (Authentication Consumer)
- **Location**: `services/etl-service/`
- **Responsibilities**:
  - Token validation via Backend Service
  - Admin page authentication
  - API endpoint protection

## Authentication Flow

### Login Process
1. **Frontend** sends credentials to **Backend Service** `/auth/login`
2. **Backend Service** validates credentials against database
3. **Backend Service** creates JWT token and database session
4. **Backend Service** returns token and user data
5. **Frontend** stores token and updates UI

### Token Validation
1. **ETL Service** receives request with JWT token
2. **ETL Service** forwards token to **Backend Service** `/api/v1/auth/validate-service`
3. **Backend Service** validates token and returns user data
4. **ETL Service** proceeds with authorized request

### Session Management
- **Multiple Sessions**: Users can have multiple concurrent sessions
- **Session Tracking**: Each session tracks IP, user agent, and activity
- **Session Revocation**: Users can revoke individual or all sessions

## API Endpoints

### Backend Service (Authentication Provider)

#### Authentication
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout
- `GET /api/v1/auth/validate` - Token validation (for frontend)
- `POST /api/v1/auth/validate-service` - Token validation (for services)
- `POST /api/v1/auth/refresh` - Token refresh

#### Session Management
- `GET /api/v1/auth/sessions` - List user sessions
- `DELETE /api/v1/auth/sessions/{id}` - Revoke specific session
- `DELETE /api/v1/auth/sessions` - Revoke all sessions (except current)

#### User Management
- `GET /api/v1/admin/users` - List users
- `POST /api/v1/admin/users` - Create user
- `PUT /api/v1/admin/users/{id}` - Update user
- `DELETE /api/v1/admin/users/{id}` - Delete user

### ETL Service (Authentication Consumer)

#### Redirected Endpoints
- `POST /auth/login` → Redirects to Backend Service
- `POST /auth/logout` → Redirects to Backend Service
- `POST /api/v1/auth/refresh` → Redirects to Backend Service
- `GET /api/v1/admin/users` → Redirects to Backend Service

#### Local Endpoints
- `GET /api/v1/auth/validate` - Local validation via Backend Service
- All ETL-specific endpoints (jobs, data, etc.)

## Configuration

### Environment Variables

```env
# Backend Service URL (required for ETL Service)
BACKEND_SERVICE_URL=http://localhost:3002

# Frontend API URL (required for Frontend)
VITE_API_BASE_URL=http://localhost:3002

# ETL Service URL (for Backend Service communication)
ETL_SERVICE_URL=http://localhost:8000
```

### Production Configuration

```env
# Production URLs
BACKEND_SERVICE_URL=https://your-domain.com/api
VITE_API_BASE_URL=https://your-domain.com/api
ETL_SERVICE_URL=https://your-domain.com/etl

# Docker Configuration
BACKEND_SERVICE_URL=http://backend-service:3002
ETL_SERVICE_URL=http://etl:8000
```

## Security Features

### JWT Tokens
- **Algorithm**: HS256
- **Expiration**: 24 hours (configurable)
- **Storage**: Database sessions for revocation capability

### Session Management
- **Multiple Sessions**: Supported per user
- **Session Tracking**: IP address, user agent, timestamps
- **Automatic Cleanup**: Expired sessions are cleaned up on login

### Password Security
- **Hashing**: bcrypt with salt
- **Local Authentication**: Stored in Backend Service only
- **OKTA Ready**: Architecture supports OKTA integration

## Migration Notes

### What Changed
1. **Removed from ETL Service**:
   - `app/auth/auth_service.py`
   - `app/auth/auth_middleware.py`
   - `app/auth/permissions.py`
   - User, UserSession, UserPermission models from `unified_models.py`

2. **Added to ETL Service**:
   - `app/auth/centralized_auth_service.py`
   - `app/auth/centralized_auth_middleware.py`

3. **Updated in ETL Service**:
   - All API routes now use centralized authentication
   - `main.py` updated to use centralized auth service
   - Login template redirects to Backend Service
   - Health, logs, and admin endpoints use new middleware

4. **Updated in Frontend**:
   - Real authentication instead of mock
   - Token validation on startup
   - Proper session management

5. **Database Management**:
   - Migration-based approach adopted - removed reset scripts
   - Backend Service contains all database tables (including user tables)
   - ETL Service no longer manages authentication-related tables
   - Use `/scripts/migrations/` for schema and data management

### Backward Compatibility
- ETL Service endpoints redirect to Backend Service
- Frontend maintains same authentication interface
- Database schema unchanged (sessions still stored)

## Troubleshooting

### Common Issues
1. **401 Unauthorized**: Check BACKEND_SERVICE_URL configuration
2. **Connection Refused**: Ensure Backend Service is running
3. **Token Invalid**: Check JWT secret consistency
4. **CORS Errors**: Update CORS_ORIGINS configuration

### Debug Endpoints
- `GET /debug/token-info` - Token debugging information
- `GET /debug/jwt-info` - JWT configuration details
- `GET /api/v1/health` - Service health check
