# Security & Authentication Guide

**Comprehensive Security Architecture & Authentication System**

This document covers all security aspects of the Pulse Platform, including authentication mechanisms, role-based access control (RBAC), client isolation, and security best practices.

## 🔐 Authentication Architecture

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

---

This security architecture ensures enterprise-grade protection while maintaining usability and performance across the multi-tenant Pulse Platform.
