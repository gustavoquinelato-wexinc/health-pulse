# Backend Service Guide

This guide covers Backend Service specific functionality, focusing on user management, authentication, and session handling.

## 👥 User Management

### **User CRUD Operations**
- **Create**: Admin can create users with roles and permissions
- **Read**: List users with filtering, pagination, search
- **Update**: Modify user details, roles, activation status
- **Delete**: Soft delete (deactivate) with dependency handling

### **User Model Structure**
```python
class User(Base, BaseEntity):
    # Identity
    id, email, password_hash
    first_name, last_name, role
    
    # Authorization
    is_admin, auth_provider
    
    # Metadata
    last_login_at
    
    # BaseEntity fields
    client_id, active, created_at, last_updated_at
```

### **User Lifecycle Management**
```python
# User creation with validation
def create_user(user_data):
    # Validate email uniqueness
    # Hash password securely
    # Set default permissions
    # Create audit trail
    
# User deactivation (soft delete)
def deactivate_user(user_id):
    # Mark user as inactive
    # Invalidate all user sessions
    # Update last_updated_at
    # Maintain data integrity
```

## 🔐 Session Management

### **Session Architecture**
- **Database-backed**: Sessions stored in `user_sessions` table
- **JWT Integration**: Token hash stored for validation/invalidation
- **Multi-session Support**: Users can have multiple active sessions
- **Proper Cleanup**: Expired sessions cleaned up automatically

### **Session Model Structure**
```python
class UserSession(Base, BaseEntity):
    # Core fields
    id, user_id, token_hash, expires_at
    
    # Metadata
    ip_address, user_agent
    
    # BaseEntity fields
    client_id, active, created_at, last_updated_at
```

### **Session Operations**
```python
# Session creation during login
async def create_session(user, ip_address, user_agent):
    # Generate JWT token
    # Hash token for storage
    # Store session in database
    # Set proper expiration
    
# Session validation
async def verify_token(token):
    # Hash incoming token
    # Find matching active session
    # Check expiration
    # Return user data if valid
    
# Session invalidation
async def invalidate_session(token):
    # Find session by token hash
    # Mark as inactive
    # Update last_updated_at
    # Return success status
```

## 🔑 Authentication APIs

### **Core Authentication Endpoints**
```python
# Login endpoint
POST /auth/login
{
    "email": "user@example.com",
    "password": "password"
}
# Returns: JWT token + user data

# Token validation (for other services)
POST /api/v1/auth/validate-service
Headers: Authorization: Bearer <token>
# Returns: User data if valid

# Session invalidation
POST /api/v1/admin/auth/invalidate-session
Headers: Authorization: Bearer <token>
# Returns: Success/failure status

# Current session info
GET /api/v1/admin/current-session
Headers: Authorization: Bearer <token>
# Returns: Current session details
```

### **Authentication Flow**
```python
# Login process
1. Validate credentials against database
2. Create JWT token with user claims
3. Store session in database with token hash
4. Update user.last_login_at
5. Return token and user data

# Token validation process
1. Extract token from Authorization header
2. Hash token for database lookup
3. Find matching active session
4. Check expiration and user status
5. Return user data or error
```

## 🛡️ Permission System

### **RBAC Implementation**
- **Roles**: admin, user, view (hierarchical)
- **Resources**: etl_jobs, admin_panel, users, etc.
- **Actions**: read, execute, delete, admin
- **Matrix**: Role-resource-action combinations

### **Permission Checking**
```python
# Permission validation
def require_permission(resource: str, action: str):
    def decorator(func):
        async def wrapper(user: User = Depends(get_current_user)):
            if not has_permission(user, resource, action):
                raise HTTPException(403, "Insufficient permissions")
            return await func(user)
        return wrapper
    return decorator

# Usage in endpoints
@router.get("/admin/users")
async def get_users(user: User = Depends(require_permission("users", "read"))):
    return get_all_users()
```

### **Permission Matrix**
```python
DEFAULT_ROLE_PERMISSIONS = {
    Role.ADMIN: {
        Resource.USERS: {Action.READ, Action.EXECUTE, Action.DELETE, Action.ADMIN},
        Resource.ADMIN_PANEL: {Action.READ, Action.EXECUTE, Action.DELETE, Action.ADMIN},
        # ... all resources with all actions
    },
    Role.USER: {
        Resource.DASHBOARDS: {Action.READ},
        Resource.ETL_JOBS: {Action.READ},
        # ... limited access
    },
    Role.VIEW: {
        Resource.DASHBOARDS: {Action.READ},
        # ... most restrictive
    }
}
```

## 📊 Admin Statistics

### **User Statistics**
```python
# Statistics calculation
def get_system_stats():
    total_users = count_all_users()
    active_users = count_active_users()
    logged_users = count_users_with_active_sessions()  # Key fix!
    admin_users = count_admin_users()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "logged_users": logged_users,  # Based on active sessions
        "admin_users": admin_users
    }
```

### **Session Statistics**
```python
# Active sessions with user info
def get_active_sessions():
    return session.query(
        UserSession,
        User.first_name,
        User.last_name,
        User.email,
        User.role
    ).join(User).filter(
        UserSession.active == True,
        UserSession.expires_at > now(),
        User.active == True
    ).all()
```

## 🔧 Database Operations

### **User-Related Queries**
```python
# User search with filters
def search_users(search_term, role_filter, active_filter):
    query = session.query(User)
    
    if search_term:
        query = query.filter(
            or_(
                User.email.ilike(f"%{search_term}%"),
                User.first_name.ilike(f"%{search_term}%"),
                User.last_name.ilike(f"%{search_term}%")
            )
        )
    
    if role_filter:
        query = query.filter(User.role == role_filter)
    
    if active_filter is not None:
        query = query.filter(User.active == active_filter)
    
    return query.all()
```

### **Session Cleanup**
```python
# Cleanup expired sessions
def cleanup_expired_sessions():
    session.query(UserSession).filter(
        UserSession.expires_at < now()
    ).update({"active": False})
    
    session.commit()
```

## 🔐 Security Patterns

### **Password Security**
```python
# Password hashing
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000  # 100k iterations
    )
    return base64.b64encode(password_hash).decode('utf-8')

# Password verification
def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    computed_hash = hash_password_with_salt(password, salt)
    return secrets.compare_digest(stored_hash, computed_hash)
```

### **Token Security**
```python
# JWT token creation
def create_jwt_token(user: User) -> str:
    payload = {
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "is_admin": user.is_admin,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")

# Token hashing for storage
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
```

## 🚨 Error Handling

### **Authentication Errors**
```python
# Common error responses
HTTP_401_UNAUTHORIZED = {
    "status_code": 401,
    "detail": "Invalid or expired token",
    "headers": {"WWW-Authenticate": "Bearer"}
}

HTTP_403_FORBIDDEN = {
    "status_code": 403,
    "detail": "Insufficient permissions"
}

# Error logging
logger.warning(f"❌ Authentication failed for email: {email}")
logger.info(f"✅ User {user.email} logged in successfully")
```

### **Session Management Errors**
```python
# Session validation errors
if not user_session:
    logger.warning(f"❌ No session found with token_hash: {token_hash[:50]}...")
    return False

if user_session.expires_at < now():
    logger.warning(f"❌ Session expired for user: {user_session.user_id}")
    return False
```

## 🚨 Common Patterns & Pitfalls

### **Session Management**
- ✅ **Do** use session IDs for "current session" detection
- ✅ **Do** hash tokens before storing in database
- ✅ **Do** check both session.active and expires_at
- ❌ **Don't** use user email for session identification
- ❌ **Don't** store raw JWT tokens in database

### **User Management**
- ✅ **Do** use soft delete (deactivate) for users
- ✅ **Do** invalidate sessions when deactivating users
- ✅ **Do** validate email uniqueness before creation
- ❌ **Don't** hard delete users with existing data
- ❌ **Don't** allow duplicate email addresses

### **Statistics & Metrics**
- ✅ **Do** count logged users based on active sessions
- ✅ **Do** exclude deactivated users from active counts
- ✅ **Do** use proper joins for session statistics
- ❌ **Don't** use last_login_at for "currently logged" count
- ❌ **Don't** include expired sessions in active counts

### **Authentication APIs**
- ✅ **Do** validate tokens on every request
- ✅ **Do** return consistent error formats
- ✅ **Do** log authentication events for audit
- ❌ **Don't** expose sensitive user data in tokens
- ❌ **Don't** allow authentication bypass for any endpoint
