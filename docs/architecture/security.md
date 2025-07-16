# Security Design

## 🛡️ Security Philosophy

The Pulse Platform implements **"Defense in Depth"** security strategy:

- **Zero Trust Architecture**: Verify every request, trust nothing by default
- **Principle of Least Privilege**: Minimal access rights for each component
- **Security by Design**: Security considerations built into every layer
- **Data Protection**: Comprehensive protection of sensitive data
- **Audit Trail**: Complete logging of security-relevant events

## 🏗️ Security Architecture

### **Security Layers**

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────┐  │
│  │   Frontend      │    │   Backend       │    │   ETL   │  │
│  │   Security      │    │   Security      │    │ Security│  │
│  │                 │    │                 │    │         │  │
│  │ • JWT Storage   │    │ • JWT Verify    │    │ • API   │  │
│  │ • HTTPS Only    │    │ • RBAC Check    │    │   Keys  │  │
│  │ • CSP Headers   │    │ • Rate Limit    │    │ • Input │  │
│  │ • XSS Protect   │    │ • Input Valid   │    │   Valid │  │
│  └─────────────────┘    └─────────────────┘    └─────────┘  │
│                                │                            │
│                                ▼                            │
│                    ┌─────────────────────┐                  │
│                    │   Data Security     │                  │
│                    │                     │                  │
│                    │ • Encryption at Rest│                  │
│                    │ • Encrypted Transit │                  │
│                    │ • Token Encryption  │                  │
│                    │ • Database Security │                  │
│                    └─────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

## 🔐 Authentication & Authorization

### **Current Implementation (ETL Service)**

#### **Hardcoded Authentication**
```python
# Simple authentication for development
HARDCODED_CREDENTIALS = {
    "email": "gustavo.quinelato@wexinc.com",
    "password": "pulse"
}

@router.post("/auth/login")
async def login(request: LoginRequest):
    """Simple hardcoded authentication"""
    
    if (request.email == HARDCODED_CREDENTIALS["email"] and 
        request.password == HARDCODED_CREDENTIALS["password"]):
        
        # Generate JWT token
        token = create_jwt_token({
            "email": request.email,
            "exp": datetime.utcnow() + timedelta(hours=24)
        })
        
        return {"access_token": token, "token_type": "bearer"}
    
    raise HTTPException(401, "Invalid credentials")
```

### **Planned Implementation (Full Stack)**

#### **JWT-Based Authentication**
```python
# Backend Service - JWT Authentication
class JWTAuth:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_token(self, user_data: dict, expires_delta: timedelta = None) -> str:
        """Create JWT token with user data"""
        
        to_encode = user_data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=24)
        
        to_encode.update({"exp": expire})
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> dict:
        """Verify and decode JWT token"""
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "Token has expired")
        except jwt.JWTError:
            raise HTTPException(401, "Invalid token")
```

#### **Role-Based Access Control (RBAC)**
```python
# User roles and permissions
class UserRole(Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

class Permission(Enum):
    ETL_START = "etl.start"
    ETL_STOP = "etl.stop"
    ETL_VIEW = "etl.view"
    ETL_CONFIGURE = "etl.configure"
    ADMIN_ACCESS = "admin.access"

ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        Permission.ETL_START,
        Permission.ETL_STOP,
        Permission.ETL_VIEW,
        Permission.ETL_CONFIGURE,
        Permission.ADMIN_ACCESS
    ],
    UserRole.OPERATOR: [
        Permission.ETL_START,
        Permission.ETL_STOP,
        Permission.ETL_VIEW
    ],
    UserRole.VIEWER: [
        Permission.ETL_VIEW
    ]
}

def require_permission(permission: Permission):
    """Decorator to require specific permission"""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = get_current_user()
            
            if not user.has_permission(permission):
                raise HTTPException(403, f"Permission {permission.value} required")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

## 🔒 Service-to-Service Security

### **Internal API Authentication**

#### **API Key Management**
```python
# Internal API key validation
class InternalAuth:
    def __init__(self):
        self.api_keys = {
            "backend_service": os.getenv("BACKEND_INTERNAL_KEY"),
            "etl_service": os.getenv("ETL_INTERNAL_KEY")
        }
    
    def validate_internal_request(self, request: Request) -> bool:
        """Validate internal service request"""
        
        internal_key = request.headers.get("X-Internal-Auth")
        
        if not internal_key:
            return False
        
        # Validate key
        return internal_key in self.api_keys.values()
    
    def get_service_identity(self, request: Request) -> str:
        """Get service identity from request"""
        
        internal_key = request.headers.get("X-Internal-Auth")
        
        for service, key in self.api_keys.items():
            if key == internal_key:
                return service
        
        return "unknown"
```

#### **Request Signing (Planned)**
```python
# HMAC request signing for enhanced security
import hmac
import hashlib

class RequestSigner:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()
    
    def sign_request(self, method: str, path: str, body: str, timestamp: str) -> str:
        """Sign request with HMAC"""
        
        message = f"{method}\n{path}\n{body}\n{timestamp}"
        signature = hmac.new(
            self.secret_key,
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def verify_signature(self, request: Request) -> bool:
        """Verify request signature"""
        
        signature = request.headers.get("X-Signature")
        timestamp = request.headers.get("X-Timestamp")
        
        if not signature or not timestamp:
            return False
        
        # Check timestamp freshness (prevent replay attacks)
        if abs(time.time() - float(timestamp)) > 300:  # 5 minutes
            return False
        
        # Verify signature
        expected_signature = self.sign_request(
            request.method,
            str(request.url.path),
            await request.body(),
            timestamp
        )
        
        return hmac.compare_digest(signature, expected_signature)
```

## 🔐 Data Protection

### **Encryption at Rest**

#### **Sensitive Data Encryption**
```python
from cryptography.fernet import Fernet

class DataEncryption:
    def __init__(self, encryption_key: str):
        self.cipher = Fernet(encryption_key.encode())
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data before storage"""
        
        if not data:
            return data
        
        encrypted_data = self.cipher.encrypt(data.encode())
        return encrypted_data.decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data after retrieval"""
        
        if not encrypted_data:
            return encrypted_data
        
        decrypted_data = self.cipher.decrypt(encrypted_data.encode())
        return decrypted_data.decode()

# Database model with encrypted fields
class Integration(BaseEntity):
    name: str
    integration_type: str
    
    # Encrypted fields
    _api_token: str = Column("api_token", String)
    _api_secret: str = Column("api_secret", String)
    
    @property
    def api_token(self) -> str:
        return encryption.decrypt_sensitive_data(self._api_token)
    
    @api_token.setter
    def api_token(self, value: str):
        self._api_token = encryption.encrypt_sensitive_data(value)
```

### **Encryption in Transit**

#### **HTTPS Configuration**
```python
# Production HTTPS configuration
import ssl

def create_ssl_context():
    """Create SSL context for HTTPS"""
    
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(
        certfile="/path/to/cert.pem",
        keyfile="/path/to/key.pem"
    )
    
    # Security settings
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS")
    
    return context

# Run with HTTPS
if __name__ == "__main__":
    ssl_context = create_ssl_context()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=443,
        ssl_context=ssl_context
    )
```

## 🛡️ Input Validation & Sanitization

### **Request Validation**

#### **Pydantic Models with Validation**
```python
from pydantic import BaseModel, validator, Field
import re

class JobStartRequest(BaseModel):
    job_name: str = Field(..., min_length=1, max_length=50)
    force: bool = False
    parameters: dict = Field(default_factory=dict)
    
    @validator('job_name')
    def validate_job_name(cls, v):
        # Whitelist allowed job names
        allowed_jobs = ['jira_sync', 'github_sync', 'aha_sync', 'azure_sync']
        if v not in allowed_jobs:
            raise ValueError(f'Invalid job name. Allowed: {allowed_jobs}')
        return v
    
    @validator('parameters')
    def validate_parameters(cls, v):
        # Limit parameter size
        if len(str(v)) > 1000:
            raise ValueError('Parameters too large')
        return v

class LoginRequest(BaseModel):
    email: str = Field(..., regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    password: str = Field(..., min_length=1, max_length=100)
    
    @validator('email')
    def validate_email(cls, v):
        # Additional email validation
        if len(v) > 254:
            raise ValueError('Email too long')
        return v.lower()
```

### **SQL Injection Prevention**

#### **Parameterized Queries**
```python
# Always use parameterized queries with SQLAlchemy
def get_job_by_name(job_name: str) -> JobSchedule:
    """Safe database query with parameters"""
    
    # SQLAlchemy automatically parameterizes queries
    return session.query(JobSchedule).filter(
        JobSchedule.job_name == job_name  # Automatically parameterized
    ).first()

# Never use string formatting for SQL
# BAD: f"SELECT * FROM jobs WHERE name = '{job_name}'"
# GOOD: Use SQLAlchemy ORM or parameterized queries
```

## 🔍 Security Monitoring

### **Security Event Logging**

#### **Audit Trail**
```python
class SecurityAuditLogger:
    def __init__(self):
        self.logger = logging.getLogger("security_audit")
    
    def log_authentication_attempt(self, email: str, success: bool, ip_address: str):
        """Log authentication attempts"""
        
        self.logger.info(
            "Authentication attempt",
            extra={
                "event_type": "authentication",
                "email": email,
                "success": success,
                "ip_address": ip_address,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def log_permission_check(self, user_id: str, permission: str, granted: bool):
        """Log permission checks"""
        
        self.logger.info(
            "Permission check",
            extra={
                "event_type": "authorization",
                "user_id": user_id,
                "permission": permission,
                "granted": granted,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def log_sensitive_operation(self, user_id: str, operation: str, resource: str):
        """Log sensitive operations"""
        
        self.logger.warning(
            "Sensitive operation",
            extra={
                "event_type": "sensitive_operation",
                "user_id": user_id,
                "operation": operation,
                "resource": resource,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
```

### **Rate Limiting**

#### **API Rate Limiting**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.route("/api/v1/jobs/start")
@limiter.limit("5/minute")  # 5 requests per minute
async def start_job(request: Request):
    """Rate-limited job start endpoint"""
    pass

@app.route("/auth/login")
@limiter.limit("10/minute")  # 10 login attempts per minute
async def login(request: Request):
    """Rate-limited login endpoint"""
    pass
```

## 🚨 Security Incident Response

### **Threat Detection**

#### **Anomaly Detection**
```python
class SecurityMonitor:
    def __init__(self):
        self.failed_login_threshold = 5
        self.suspicious_activity_patterns = [
            r"(?i)(union|select|insert|delete|drop|exec)",  # SQL injection
            r"<script.*?>.*?</script>",  # XSS attempts
            r"\.\.\/",  # Path traversal
        ]
    
    def detect_brute_force(self, ip_address: str) -> bool:
        """Detect brute force login attempts"""
        
        recent_failures = get_recent_login_failures(ip_address, minutes=15)
        
        if recent_failures >= self.failed_login_threshold:
            self.alert_security_team(f"Brute force detected from {ip_address}")
            return True
        
        return False
    
    def scan_for_malicious_input(self, input_data: str) -> bool:
        """Scan input for malicious patterns"""
        
        for pattern in self.suspicious_activity_patterns:
            if re.search(pattern, input_data):
                self.alert_security_team(f"Malicious input detected: {pattern}")
                return True
        
        return False
```

This security design provides comprehensive protection across all layers of the Pulse Platform while maintaining usability and performance.
