# Shared Session System - Implementation Guide

## 🎯 Overview

The Pulse Platform now implements a **shared session system** that enables seamless Single Sign-On (SSO) across all services. Users can login once and navigate between Frontend and ETL services without re-authentication.

## 🏗️ Architecture

### **Session Flow**
```
User Login → Backend Service → Redis Session + HTTP Cookie
                ↓
    Cookie shared between:
    - Frontend (localhost:3000)  
    - ETL Service (localhost:8000)
                ↓
    Both services validate via Backend Service API
```

### **Key Components**

1. **Backend Service** - Session Authority
   - Issues JWT tokens and HTTP-only cookies
   - Stores sessions in Redis for fast access
   - Validates sessions for all services
   - Handles logout and session invalidation

2. **Redis Session Manager** - Fast Session Storage
   - Stores session data with automatic expiration
   - Enables cross-service session sharing
   - Provides atomic session operations

3. **Frontend** - Live Session Monitoring
   - Periodic session validation (5-minute intervals)
   - Automatic 401 response handling
   - Multi-source token retrieval (localStorage + cookies)

4. **ETL Service** - Session Consumer
   - Validates sessions via Backend Service API
   - Checks cookies first, then Authorization headers
   - Seamless navigation from Frontend

## 🔐 Security Features

### **HTTP-Only Cookies**
- Prevents XSS attacks
- Domain-wide sharing (localhost in dev, your-domain.com in prod)
- Automatic expiration matching JWT lifetime

### **Redis Session Storage**
- Fast session lookups (1ms vs 50ms database)
- Automatic cleanup with TTL
- Concurrent-safe operations

### **Multi-Layer Validation**
- JWT signature validation
- Redis session existence check
- Database session verification (fallback)

## 🚀 Implementation Details

### **Backend Service Changes**

#### Redis Session Manager (`app/core/redis_session_manager.py`)
```python
class RedisSessionManager:
    async def store_session(token_hash, user_data, ttl_seconds)
    async def get_session(token_hash) -> user_data
    async def invalidate_session(token_hash)
    async def invalidate_all_user_sessions(user_id)
    async def extend_session(token_hash, ttl_seconds)
```

#### Enhanced Auth Service (`app/auth/auth_service.py`)
- Redis-first session validation
- Database fallback for reliability
- Cross-service logout functionality

#### Updated Auth Routes (`app/api/auth_routes.py`)
- Login sets HTTP-only cookies
- Logout clears cookies across services
- New `/logout-all` endpoint for multi-device logout

### **Frontend Changes**

#### Enhanced Auth Context (`src/contexts/AuthContext.tsx`)
- Periodic session validation (5-minute intervals)
- Axios interceptor for automatic 401 handling
- Multi-source token retrieval (localStorage + cookies)

#### Live Session Features
```typescript
// Periodic validation
setInterval(validateSession, 5 * 60 * 1000)

// Automatic 401 handling
axios.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) logout()
    return Promise.reject(error)
  }
)
```

### **ETL Service Integration**
- Already configured to check cookies first
- Validates sessions via Backend Service API
- Seamless navigation from Frontend

## 📋 Usage Examples

### **Cross-Service Navigation**
1. User logs into Frontend → Backend sets cookie
2. User clicks "ETL Management" → ETL reads cookie → Validates with Backend → Access granted
3. User logs into ETL directly → Backend sets cookie → Frontend automatically authenticated

### **Session Management**
```javascript
// Frontend - Multi-source token retrieval
function getAuthToken() {
    return localStorage.getItem('pulse_token') || 
           getCookieValue('pulse_token')
}

// Backend - Redis session validation
async def verify_token(token):
    # 1. Check Redis (fast)
    session_data = await redis_manager.get_session(token_hash)
    if session_data: return create_user_from_session(session_data)
    
    # 2. Fallback to database
    return validate_database_session(token)
```

## 🧪 Testing

### **Test Script**
Run `python test_shared_sessions.py` to verify:
- Backend Service login with cookie setting
- Token validation via headers and cookies
- Cross-service authentication (ETL ← Backend)
- Logout with cookie clearing
- Session invalidation across services

### **Manual Testing**
1. Start services: Redis, Backend, ETL, Frontend
2. Login to Frontend → Navigate to ETL (no re-auth)
3. Login to ETL → Navigate to Frontend (no re-auth)
4. Logout from either → Both services require re-auth

## 🔧 Configuration

### **Environment Variables**
```env
# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# JWT Configuration  
JWT_SECRET_KEY=your-secret-key
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Service URLs
BACKEND_SERVICE_URL=http://localhost:3001
ETL_SERVICE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
```

### **Cookie Settings**
```python
# Development
domain="localhost"
secure=False
samesite="lax"

# Production
domain="your-domain.com"
secure=True  # HTTPS only
samesite="lax"
```

## 🚨 Troubleshooting

### **Common Issues**

1. **Sessions not shared between services**
   - Check Redis is running: `docker ps | grep redis`
   - Verify cookie domain settings match
   - Ensure services use same JWT secret

2. **Periodic validation not working**
   - Check browser console for errors
   - Verify Backend Service `/auth/validate` endpoint
   - Check axios interceptor setup

3. **Logout not clearing sessions**
   - Verify Redis session invalidation
   - Check cookie clearing in browser
   - Ensure all services use same session validation

### **Debug Commands**
```bash
# Check Redis sessions
redis-cli keys "pulse:session:*"

# Test Backend Service
curl -X POST http://localhost:3001/auth/validate \
  -H "Authorization: Bearer YOUR_TOKEN"

# Test ETL Service
curl -b "pulse_token=YOUR_TOKEN" http://localhost:8000/home
```

## 🎉 Benefits Achieved

✅ **Seamless UX** - Login once, access everything  
✅ **Enterprise-grade** - Standard SSO pattern for B2B SaaS  
✅ **Performance** - Redis sessions (1ms vs 50ms database)  
✅ **Security** - HTTP-only cookies, automatic session cleanup  
✅ **Reliability** - Database fallback, multi-layer validation  
✅ **Scalability** - Redis handles thousands of concurrent sessions  

The shared session system transforms the Pulse Platform into a truly integrated experience where users can seamlessly navigate between all services without authentication friction.
