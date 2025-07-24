# Cross-Domain Guide

This guide covers platform-wide concerns that affect all services in the Pulse Platform.

## 🔐 Authentication & Authorization

### **Centralized Authentication Architecture**
- **Backend Service**: Handles all authentication (login, logout, session management)
- **ETL Service**: Uses centralized auth for validation, no local auth
- **Frontend**: Manages tokens in localStorage and cookies

### **Authentication Flow**
```
1. User logs in → Backend Service validates credentials
2. Backend Service creates JWT token + database session
3. Frontend stores token in localStorage + cookie
4. ETL Service validates tokens via Backend Service API calls
5. Logout invalidates session in Backend Service database
```

### **Token Management**
- **JWT Secret**: Shared via environment variable `JWT_SECRET_KEY`
- **Storage**: localStorage (primary) + cookies (fallback)
- **Validation**: ETL Service calls Backend Service for validation
- **Invalidation**: Backend Service marks sessions as `active = false`

### **Session Detection**
- **Current Session**: Compare session IDs, not user emails
- **Multi-browser**: Each browser gets unique session ID
- **"Self" Detection**: Use `/api/v1/admin/current-session` endpoint

## 🗄️ Database Architecture

### **Unified Models Pattern**
- **Single Source**: `unified_models.py` in each service
- **Shared Schema**: Both services use same database schema
- **Relationships**: Proper FK constraints, avoid redundant data

### **User & Session Management**
```python
# User model fields
class User(Base, BaseEntity):
    id, email, password_hash, first_name, last_name
    role, is_admin, auth_provider, last_login_at
    
# Session model fields  
class UserSession(Base, BaseEntity):
    id, user_id, token_hash, expires_at
    ip_address, user_agent
    # BaseEntity: client_id, active, created_at, last_updated_at
```

### **Migration Patterns**
- **Location**: `/migrations/` at root level
- **Format**: Raw SQL CREATE/DROP/INSERT statements
- **Execution**: Use `migration_runner.py` in `/scripts/`
- **Rollback**: Always include rollback scripts

## 🔄 Inter-Service Communication

### **Service Boundaries**
- **Backend Service**: User identity, authentication, permissions
- **ETL Service**: Business data, analytics, job orchestration
- **Frontend**: User interface, token management

### **API Patterns**
```python
# ETL Service calls Backend Service
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{backend_url}/api/v1/admin/auth/invalidate-session",
        headers={"Authorization": f"Bearer {token}"}
    )
```

### **Error Handling**
- **Authentication Errors**: 401 → redirect to login
- **Permission Errors**: 403 → show access denied
- **Service Errors**: 500 → log and show generic error

## 🛡️ Security Patterns

### **RBAC Implementation**
- **Roles**: admin, user, view (defined in Backend Service)
- **Resources**: etl_jobs, dashboards, admin_panel, etc.
- **Actions**: read, execute, delete, admin
- **Validation**: Backend Service permission checks

### **Data Protection**
- **Password Hashing**: PBKDF2 with SHA-256, 100k iterations
- **Token Security**: JWT with secure secret, proper expiration
- **Session Security**: Database-backed sessions, proper invalidation

## ⚙️ Configuration Management

### **Environment Variables**
```bash
# Shared across services
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
DATABASE_URL=postgresql://...
BACKEND_SERVICE_URL=http://localhost:3001

# Service-specific
DEBUG=true
LOG_LEVEL=INFO
```

### **Settings Pattern**
```python
# Use Pydantic Settings for type safety
class Settings(BaseSettings):
    JWT_SECRET_KEY: str = Field(env="JWT_SECRET_KEY")
    BACKEND_SERVICE_URL: str = Field(env="BACKEND_SERVICE_URL")
    
    class Config:
        env_file = ".env"
```

## 📊 Logging & Monitoring

### **Logging Standards**
- **Format**: Structured logging with context
- **Levels**: DEBUG, INFO, WARNING, ERROR
- **Authentication**: Log auth success/failure with user context
- **Session Management**: Log session creation/invalidation

### **Error Patterns**
```python
# Authentication errors
logger.warning(f"❌ Token verification failed for user: {email}")
logger.info(f"✅ Session invalidated successfully for user: {email}")

# Service communication
logger.error(f"Backend Service returned status {response.status_code}")
```

## 🔧 Development Patterns

### **Package Management**
- **Always use package managers**: npm, pip, etc.
- **Never edit package files manually**: Leads to version conflicts
- **Update lock files**: Ensure consistent dependencies

### **Testing Approach**
- **Write tests first**: For new functionality
- **Test authentication**: Session management, token validation
- **Test service communication**: API calls between services
- **Clean up test files**: Delete after execution unless asked to keep

### **Code Organization**
- **Separation of concerns**: Keep auth in Backend, business logic in ETL
- **Consistent patterns**: Follow established service patterns
- **Documentation**: Update guides when patterns change

## 🚨 Common Pitfalls

### **Authentication Issues**
- ❌ **Don't** clear localStorage before calling logout API
- ❌ **Don't** use only user email for session detection
- ❌ **Don't** mix old and new auth systems
- ✅ **Do** get token first, then invalidate, then clear storage

### **Database Issues**
- ❌ **Don't** create redundant data across services
- ❌ **Don't** use string comparisons without .lower()
- ✅ **Do** use proper FK relationships
- ✅ **Do** exclude deactivated records from metrics

### **Service Communication**
- ❌ **Don't** call ETL endpoints for user management
- ❌ **Don't** bypass Backend Service for authentication
- ✅ **Do** call Backend Service directly for auth operations
- ✅ **Do** handle service communication errors gracefully
