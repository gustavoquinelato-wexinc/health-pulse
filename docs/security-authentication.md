# Security & Authentication Guide

**Comprehensive Security Architecture & Authentication System**

This document covers all security aspects of the Pulse Platform, including authentication mechanisms, role-based access control (RBAC), client isolation, and security best practices.

> **📋 Consolidated Documentation**: This guide now includes content from the former root-level security documents (CENTRALIZED_AUTH_GUIDE.md, CROSS_DOMAIN_AUTH_SOLUTION.md, SECURITY_NOTICE.md) for centralized security documentation.

## 🔐 Centralized Authentication Architecture

### Overview

Pulse Platform features a **centralized authentication service** that provides OAuth-like authentication flow across all services. This architecture solves cross-domain authentication challenges and provides enterprise-grade SSO capabilities.

### Authentication Flow

```
Frontend (3000) ──┐
                  ├──→ Auth Service (4000) ──→ Backend Service (3001) ──→ Database
ETL Service (8000) ──┘
```

**Step-by-Step Process:**
1. User visits any service → Redirected to Auth Service if not authenticated
2. Auth Service validates credentials with Backend Service
3. Auth Service generates authorization code → Redirects back to originating service
4. Service exchanges code for JWT token via Backend Service
5. Subsequent requests use JWT token validated by Backend Service

### Benefits
- ✅ **Cross-Domain Authentication** - Works across different domains
- ✅ **Single Sign-On (SSO)** - Login once, access all services
- ✅ **OKTA Integration Ready** - Provider abstraction layer implemented
- ✅ **Centralized Session Management** - Logout affects all services
- ✅ **Security** - OAuth-like flow with proper token validation

### JWT-Based Authentication

Pulse Platform uses JSON Web Tokens (JWT) for secure, stateless authentication:

```python
# JWT Token Structure
{
  "user_id": 123,
  "client_id": 1,
  "email": "user@company.com",
  "role": "admin",
  "exp": 1640995200,  # Expiration timestamp
  "iat": 1640908800   # Issued at timestamp
}
```

#### Token Management
- **Access Tokens**: Short-lived (60 minutes default)
- **Refresh Strategy**: Automatic token refresh on API calls
- **Secure Storage**: HttpOnly cookies + localStorage fallback
- **Cross-Service**: Shared JWT secret across all services

### Authentication Flow

#### Login Process
```
1. User submits credentials → Frontend
2. Frontend → Backend Service (POST /api/v1/auth/login)
3. Backend validates credentials against database
4. Backend generates JWT token with user + client context
5. Backend → Frontend (JWT token + user profile)
6. Frontend stores token securely
7. Subsequent requests include JWT in Authorization header
```

#### Session Management
```sql
-- Database-backed session tracking
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    client_id INTEGER NOT NULL REFERENCES clients(id),
    token_hash VARCHAR(255) NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);
```

#### Cross-Service Authentication
- **Backend Service**: Primary authentication provider
- **ETL Service**: Validates tokens via Backend Service API
- **Frontend**: Manages token lifecycle and renewal

## 👥 Role-Based Access Control (RBAC)

### User Roles

#### Admin Role
- **Full Platform Access**: All features and administrative functions
- **User Management**: Create, modify, delete users within their client
- **ETL Management**: Access to job orchestration and configuration
- **System Settings**: Modify client-specific configurations
- **Analytics**: Full access to all metrics and reports

#### User Role
- **Dashboard Access**: View DORA metrics and analytics
- **Limited Settings**: Personal preferences only
- **Read-Only ETL**: View job status but cannot control jobs
- **Standard Analytics**: Access to standard reports and metrics

#### Viewer Role
- **Read-Only Access**: View dashboards and reports only
- **No Configuration**: Cannot modify any settings
- **Limited Analytics**: Basic metrics and visualizations only
- **No User Management**: Cannot see or manage other users

### Permission Matrix

| Feature | Admin | User | Viewer |
|---------|-------|------|--------|
| View Dashboards | ✅ | ✅ | ✅ |
| DORA Metrics | ✅ | ✅ | ✅ |
| User Management | ✅ | ❌ | ❌ |
| ETL Job Control | ✅ | ❌ | ❌ |
| System Settings | ✅ | Personal Only | ❌ |
| Client Configuration | ✅ | ❌ | ❌ |
| Integration Setup | ✅ | ❌ | ❌ |
| Advanced Analytics | ✅ | ✅ | ❌ |

### Role Implementation

```python
# Role-based endpoint protection
@require_role("admin")
async def manage_users(request: Request):
    # Admin-only functionality
    pass

@require_role(["admin", "user"])
async def view_analytics(request: Request):
    # Admin and User access
    pass

@require_auth
async def view_dashboard(request: Request):
    # Any authenticated user
    pass
```

## 🏢 Multi-Tenant Security

### Client Isolation Strategy

#### Complete Data Separation
```python
# Every database query includes client_id filter
async def get_user_data(user_id: int, client_id: int):
    query = """
    SELECT * FROM users 
    WHERE id = ? AND client_id = ? AND active = true
    """
    return await database.fetch_one(query, user_id, client_id)
```

#### Client-Scoped Authentication
- **JWT Tokens**: Always include client_id in payload
- **API Validation**: Every endpoint validates client ownership
- **Session Isolation**: Sessions are client-specific
- **Cross-Client Prevention**: Impossible to access other client's data

#### Security Boundaries
```
┌─────────────────────────────────────────────────────────────────┐
│                        Client A (WEX)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Users     │  │   Sessions  │  │      Data & Jobs        │  │
│  │ • Admin A   │  │ • Token A1  │  │ • Jira Projects A       │  │
│  │ • User A1   │  │ • Token A2  │  │ • GitHub Repos A        │  │
│  │ • User A2   │  │             │  │ • Analytics Data A      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      Client B (TechCorp)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Users     │  │   Sessions  │  │      Data & Jobs        │  │
│  │ • Admin B   │  │ • Token B1  │  │ • Jira Projects B       │  │
│  │ • User B1   │  │ • Token B2  │  │ • GitHub Repos B        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Client-Specific Configuration

#### Secure Settings Storage
```sql
-- Client-specific system settings
CREATE TABLE system_settings (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    setting_key VARCHAR(255) NOT NULL,
    setting_value TEXT,
    setting_type VARCHAR(50) DEFAULT 'string',
    encrypted BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, setting_key)
);
```

#### Encrypted Sensitive Data
- **API Credentials**: Encrypted at rest using AES-256
- **Database Passwords**: Secure key management
- **JWT Secrets**: Environment-based secret storage
- **Integration Tokens**: Client-specific encryption keys

## 🛡️ API Security

### Request Validation

#### Authentication Middleware
```python
async def authenticate_request(request: Request):
    # Extract JWT token from header or cookie
    token = extract_token(request)
    if not token:
        raise HTTPException(401, "Authentication required")
    
    # Validate token and extract user context
    user_data = await verify_jwt_token(token)
    if not user_data:
        raise HTTPException(401, "Invalid token")
    
    # Attach user context to request
    request.state.user = user_data
    request.state.client_id = user_data["client_id"]
```

#### Client Ownership Validation
```python
async def validate_client_ownership(request: Request, resource_client_id: int):
    user_client_id = request.state.client_id
    if user_client_id != resource_client_id:
        raise HTTPException(403, "Access denied: client mismatch")
```

### Input Validation & Sanitization

#### Request Validation
- **Pydantic Models**: Strict input validation and type checking
- **SQL Injection Prevention**: Parameterized queries only
- **XSS Protection**: Input sanitization and output encoding
- **CSRF Protection**: Token-based CSRF prevention

#### Rate Limiting
```python
# API rate limiting per client
@rate_limit("100/minute", per="client_id")
async def api_endpoint(request: Request):
    client_id = request.state.client_id
    # Process request with rate limiting
```

### CORS Configuration

#### Secure Cross-Origin Requests
```python
# CORS settings
CORS_ORIGINS = [
    "http://localhost:3000",    # Frontend development
    "http://localhost:5173",    # Vite dev server
    "https://pulse.company.com" # Production domain
]

# Strict CORS policy
allow_credentials=True
allow_methods=["GET", "POST", "PUT", "DELETE"]
allow_headers=["Authorization", "Content-Type"]
```

### Endpoint Permissions

#### User vs Admin Endpoints
```python
# User-specific endpoints (accessible to all authenticated users)
/api/v1/user/theme-mode          # Personal theme preferences
/api/v1/user/profile             # User profile management
/api/v1/user/password            # Password changes

# Admin-only endpoints (require admin role)
/api/v1/admin/color-scheme       # Client-wide color schema
/api/v1/admin/user-management    # User CRUD operations
/api/v1/admin/client-management  # Client configuration
```

#### Permission Validation
```python
# User endpoint - requires authentication only
@router.get("/api/v1/user/theme-mode")
async def get_user_theme(user: User = Depends(get_current_user)):
    # Any authenticated user can access their own settings

# Admin endpoint - requires admin role
@router.get("/api/v1/admin/users")
async def get_users(user: User = Depends(require_permission(Resource.USERS, Action.READ))):
    # Only admin users can access this endpoint
```

## 🔒 Data Security

### Encryption Standards

#### Data at Rest
- **Database Encryption**: PostgreSQL TDE (Transparent Data Encryption)
- **Sensitive Fields**: AES-256 encryption for API tokens and passwords
- **File Storage**: Encrypted client logos and documents
- **Backup Encryption**: Encrypted database backups

#### Data in Transit
- **HTTPS/TLS**: All API communications encrypted with TLS 1.3
- **Database Connections**: SSL-encrypted database connections
- **Internal Services**: mTLS for service-to-service communication
- **WebSocket Security**: WSS (WebSocket Secure) for real-time updates

### Data Privacy & Compliance

#### GDPR Compliance
- **Data Portability**: Export user data in standard formats
- **Right to Deletion**: Complete data removal on request
- **Consent Management**: Explicit consent for data processing
- **Data Minimization**: Collect only necessary data

#### Audit Logging
```sql
-- Comprehensive audit trail
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🔧 Security Configuration

### Environment Security

#### Development Environment
```bash
# Development .env (non-production secrets)
JWT_SECRET_KEY=dev-secret-key-change-in-production
DATABASE_URL=postgresql://postgres:pulse@localhost:5432/pulse_db
ENCRYPTION_KEY=dev-encryption-key-32-characters
```

#### Production Environment
```bash
# Production secrets (secure secret management)
JWT_SECRET_KEY=${VAULT_JWT_SECRET}
DATABASE_URL=${VAULT_DATABASE_URL}
ENCRYPTION_KEY=${VAULT_ENCRYPTION_KEY}
SSL_CERT_PATH=/etc/ssl/certs/pulse.crt
SSL_KEY_PATH=/etc/ssl/private/pulse.key
```

### Security Headers

#### HTTP Security Headers
```python
# Security headers middleware
security_headers = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'",
    "Referrer-Policy": "strict-origin-when-cross-origin"
}
```

## 🚨 Security Monitoring

### Threat Detection

#### Suspicious Activity Monitoring
- **Failed Login Attempts**: Rate limiting and account lockout
- **Unusual Access Patterns**: Geographic and time-based anomaly detection
- **Privilege Escalation**: Monitor role changes and admin actions
- **Data Access Anomalies**: Unusual data access patterns

#### Security Alerts
```python
# Security event monitoring
async def log_security_event(event_type: str, user_id: int, client_id: int, details: dict):
    await audit_logger.log({
        "event_type": event_type,
        "user_id": user_id,
        "client_id": client_id,
        "details": details,
        "timestamp": datetime.utcnow(),
        "severity": get_event_severity(event_type)
    })
    
    if is_critical_event(event_type):
        await send_security_alert(event_type, details)
```

### Incident Response

#### Security Incident Procedures
1. **Detection**: Automated monitoring and alerting
2. **Assessment**: Evaluate threat severity and impact
3. **Containment**: Isolate affected systems and users
4. **Investigation**: Analyze logs and determine root cause
5. **Recovery**: Restore normal operations securely
6. **Lessons Learned**: Update security measures and procedures

## 🔐 Centralized Authentication System

### Overview

The Pulse Platform features a **centralized authentication service** that provides OAuth-like authentication flow across all services. This solves cross-domain authentication challenges and prepares the platform for OKTA integration.

### Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   ETL Service   │
│ (Port 3000)     │    │  (Port 8000)    │
└─────────────────┘    └─────────────────┘
         │                       │
         │              ┌────────┴────────┐
         │              │                 │
         └──────────────┼─────────────────┼─────────────┐
                        │                 │             │
                        ▼                 ▼             ▼
              ┌─────────────────────────────────┐      ┌─────────────────┐
              │     Backend Service             │      │   Auth Service  │
              │       (Port 3001)               │◄────►│   (Port 4000)   │
              │                                 │      │                 │
              │ • Session Management            │      │ • OAuth Flow    │
              │ • Token Validation              │      │ • OKTA Ready    │
              │ • User CRUD                     │      │ • Provider      │
              │ • Cross-Service Auth            │      │   Abstraction   │
              └─────────────────────────────────┘      └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │   Database      │
                    │                 │
                    │ • User Data     │
                    │ • Sessions      │
                    │ • Permissions   │
                    └─────────────────┘
```

### Authentication Flow

#### 1. Initial Login
```
1. User visits Frontend → Redirected to Auth Service
2. Auth Service → Login form (local DB or OKTA)
3. Successful auth → Auth Service generates JWT
4. Auth Service → Redirects to Frontend with auth code
5. Frontend → Exchanges code for JWT token
6. Frontend → Stores token for API calls
```

#### 2. Cross-Service Access
```
1. Frontend → Makes API call to Backend with JWT
2. Backend → Validates JWT with Auth Service
3. Backend → Processes request if valid
4. ETL Service → Uses same JWT validation flow
```

### Implementation Benefits

- **Single Sign-On**: Login once, access all services
- **OKTA Ready**: Easy integration with enterprise identity providers
- **Security**: Centralized token validation and revocation
- **Scalability**: Independent authentication service
- **Compliance**: Enterprise-grade security standards

## 🌐 Cross-Domain Authentication Solution

### Enterprise-Grade Subdomain Architecture

#### Subdomain Cookie Sharing
```
Development:
Frontend: http://localhost:3000
ETL:      http://localhost:8000
Backend:  http://localhost:3001
Cookies:  domain=.localhost

Production:
Frontend: https://app.yourcompany.com
ETL:      https://etl.yourcompany.com
Backend:  https://api.yourcompany.com
Cookies:  domain=.yourcompany.com
```

#### Enterprise Standard Pattern
This follows industry-standard subdomain patterns used by major SaaS platforms:
- **Salesforce**: app.salesforce.com, setup.salesforce.com
- **Microsoft**: portal.azure.com, admin.microsoft.com
- **Google**: console.cloud.google.com, admin.google.com

### Implementation Details

#### Cookie Configuration
```javascript
// Frontend cookie settings
document.cookie = `auth_token=${token}; domain=.yourcompany.com; secure; httpOnly; sameSite=strict`;

// Backend cookie validation
app.use(cookieParser());
app.use((req, res, next) => {
  const token = req.cookies.auth_token;
  // Validate token across all subdomains
});
```

#### Security Considerations
- **HTTPS Only**: All production subdomains use SSL/TLS
- **Secure Cookies**: HttpOnly and Secure flags enabled
- **SameSite**: Strict policy to prevent CSRF attacks
- **Domain Validation**: Verify subdomain authenticity

## 🚨 Security Incident Management

### Historical Security Notice

**Date**: 2024-01-XX
**Severity**: CRITICAL (RESOLVED)
**Status**: RESOLVED

#### Issue Description
A `.env` file containing sensitive credentials was accidentally committed to the repository. This file contained:
- JWT secret keys
- Database passwords
- API tokens for Jira, GitHub, Aha!, and Azure DevOps
- Encryption keys
- Other sensitive configuration data

#### Immediate Actions Taken
1. **Repository Cleanup**: Removed sensitive file from git history
2. **Credential Rotation**: All exposed credentials were immediately rotated
3. **Access Review**: Comprehensive audit of all system access
4. **Security Hardening**: Enhanced .gitignore and pre-commit hooks

#### Preventive Measures Implemented
- **Enhanced .gitignore**: Comprehensive exclusion of sensitive files
- **Pre-commit Hooks**: Automated scanning for secrets before commits
- **Environment Separation**: Clear separation of development and production secrets
- **Access Controls**: Stricter repository access permissions
- **Security Training**: Team education on secure development practices

#### Current Security Status
✅ **All credentials rotated**
✅ **Repository cleaned**
✅ **Monitoring enhanced**
✅ **Preventive measures active**
✅ **No ongoing security risks**

### Security Incident Response Plan

#### 1. Detection and Analysis
- **Immediate Assessment**: Determine scope and impact
- **Evidence Collection**: Preserve logs and system state
- **Stakeholder Notification**: Alert relevant team members

#### 2. Containment and Eradication
- **Immediate Containment**: Stop ongoing threats
- **System Isolation**: Isolate affected systems if necessary
- **Threat Removal**: Remove malicious elements

#### 3. Recovery and Lessons Learned
- **System Restoration**: Restore normal operations
- **Monitoring Enhancement**: Improve detection capabilities
- **Process Updates**: Update security procedures
- **Team Training**: Enhance security awareness

---

This comprehensive security guide ensures the Pulse Platform maintains enterprise-grade security standards while providing seamless authentication across all services.

This security architecture ensures enterprise-grade protection while maintaining usability and performance across the multi-tenant Pulse Platform.
