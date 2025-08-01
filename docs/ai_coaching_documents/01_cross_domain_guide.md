# Cross-Domain Guide

This guide covers platform-wide concerns that affect all services in the unified Pulse Platform.

## 🔐 Authentication & Authorization

### **Unified Platform Authentication Architecture**
- **Backend Service**: Centralized authentication hub (login, logout, session management)
- **Frontend Platform**: Primary user interface with embedded ETL management
- **ETL Service**: Embedded service using shared authentication tokens
- **Seamless Integration**: Single sign-on across all platform components

### **Unified Authentication Flow**
```
1. User logs in via Platform Frontend → Backend Service validates credentials
2. Backend Service creates JWT token + database session
3. Frontend stores token in localStorage + cookie
4. ETL iframe receives token via URL parameter for embedded access
5. ETL Service validates tokens via Backend Service API calls
6. Logout invalidates session across entire platform
```

### **Cross-Service Navigation Authentication**
```
Platform Frontend ↔ ETL Service Direct Navigation:
1. Frontend checks user.is_admin before showing ETL menu
2. If admin: POST token to ETL service via /auth/navigate
3. ETL Service validates token and creates session cookie
4. User navigates to ETL service with proper authentication
5. ETL Service provides return navigation to frontend
6. Non-admin users never see ETL management options
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

## 🔗 **Platform Integration Patterns**

### **Embedded Service Architecture**
The Pulse Platform uses iframe embedding for seamless service integration:

```typescript
// Platform Integration Pattern
interface EmbeddedServiceConfig {
  baseUrl: string;
  authToken: string;
  theme: 'light' | 'dark';
  colorMode: 'default' | 'custom';
  embedded: boolean;
}

// ETL Service Embedding
const etlConfig: EmbeddedServiceConfig = {
  baseUrl: 'http://localhost:8000',
  authToken: user.token,
  theme: currentTheme,
  colorMode: currentColorMode,
  embedded: true
};
```

### **Cross-Service Communication**
```
Frontend Platform ←→ Backend Service (Direct API calls)
Frontend Platform ←→ ETL Service (POST navigation with token)
ETL Service ←→ Backend Service (Authentication validation)
ETL Service ←→ Frontend Platform (Return navigation with token)
```

### **Branding Strategy**
```
Platform Level (Login Pages):
├─ Frontend Login: Pulse Platform branding
├─ ETL Login: Pulse Platform branding (fallback)
└─ Consistent platform identity

Client Level (Internal Pages):
├─ Frontend Header: Client-specific logo (WEX, TechCorp, etc.)
├─ ETL Home: Client-specific logo
└─ Dynamic loading based on user.client_name
```

### **Theme Synchronization**
```typescript
// Theme propagation to embedded services
useEffect(() => {
  const iframe = document.querySelector('iframe[title="ETL Management"]');
  if (iframe) {
    const newUrl = buildETLUrl({
      page: 'home',
      token: authToken,
      theme: currentTheme,
      colorMode: currentColorMode
    });
    iframe.src = newUrl;
  }
}, [currentTheme, currentColorMode]);
```

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

### **Unified Platform Service Boundaries**
- **Frontend Platform**: Primary user interface, cross-service navigation, client branding
- **Backend Service**: User identity, authentication, permissions, session management
- **ETL Service**: Business data, analytics, job orchestration, admin interface with return navigation

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

### **Multi-Client Security (PRODUCTION-READY)**
- **Complete Client Isolation**: All database queries filter by client_id
- **Zero Cross-Client Access**: Enterprise-grade data separation
- **Client-Scoped Operations**: Every endpoint validates client ownership
- **Secure Multi-Tenancy**: Production-ready multi-client architecture

### **RBAC Implementation**
- **Roles**: admin, user, view (defined in Backend Service, per client)
- **Resources**: etl_jobs, home_page, admin_panel, etc.
- **Actions**: read, execute, delete, admin
- **Validation**: Backend Service permission checks + client_id validation

### **Data Protection**
- **Client Data Isolation**: Every query filters by client_id
- **Password Hashing**: PBKDF2 with SHA-256, 100k iterations
- **Token Security**: JWT with secure secret, proper expiration + client_id
- **Session Security**: Database-backed sessions, proper invalidation per client

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

## 🔄 Workflow Management

### **Workflow Architecture**
- **Service Ownership**: ETL Service manages all workflow operations
- **Database Constraints**: Unique commitment points per client/integration
- **Validation Strategy**: Pre-validation before database operations
- **Error Handling**: User-friendly messages for constraint violations

### **Commitment Point Rules**
```python
# Database constraint (PostgreSQL)
CREATE UNIQUE INDEX idx_unique_commitment_point_per_client_integration
ON workflows(client_id, integration_id)
WHERE is_commitment_point = true;

# API validation pattern
if update_data.is_commitment_point:
    existing = session.query(Workflow).filter(
        Workflow.client_id == user.client_id,
        Workflow.integration_id == update_data.integration_id,
        Workflow.is_commitment_point == True,
        Workflow.id != workflow_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Only one commitment point allowed per integration..."
        )
```

### **Frontend Integration**
- **Modal Population**: Always populate dropdowns before setting values
- **Error Display**: Parse JSON error responses properly
- **Validation**: Backend validation takes precedence over frontend

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

### **Workflow Management**
- ❌ **Don't** rely only on frontend validation for constraints
- ❌ **Don't** use generic error messages for constraint violations
- ❌ **Don't** forget to populate dropdowns before setting values
- ✅ **Do** validate at API level before database operations
- ✅ **Do** provide clear, actionable error messages
- ✅ **Do** include integration/workflow names in error context

### **Service Communication**
- ❌ **Don't** call ETL endpoints for user management
- ❌ **Don't** bypass Backend Service for authentication
- ✅ **Do** call Backend Service directly for auth operations
- ✅ **Do** handle service communication errors gracefully
