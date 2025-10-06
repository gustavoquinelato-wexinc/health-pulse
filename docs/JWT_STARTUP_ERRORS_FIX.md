# JWT Startup Errors Fix

## 🚨 **Problem Identified**

**Issue**: Backend service was showing continuous "Invalid JWT token for user unknown" errors during startup, even when no other services were running.

**Root Cause**: The `TenantLoggingMiddleware` was running on **every HTTP request** (including internal health checks and startup requests) and attempting to validate JWT tokens that don't exist for system/internal requests.

## 🔍 **Error Source**

**File**: `services/backend-service/app/core/client_logging_middleware.py`  
**Line**: 100 - `user = await auth_service.verify_token(token)`

**What was happening**:
1. Backend service starts up
2. Internal health checks and system requests are made
3. TenantLoggingMiddleware intercepts ALL requests
4. Middleware tries to extract JWT tokens from system requests
5. No valid tokens exist for system requests
6. `auth_service.verify_token()` logs "Invalid JWT token for user unknown"
7. This happens repeatedly during startup

## ✅ **Solution Applied**

### **1. Skip Token Validation for System Endpoints**

Updated `TenantLoggingMiddleware` to skip JWT validation for internal/system endpoints:

```python
# Skip token validation for internal/system endpoints to avoid JWT errors during startup
path = str(request.url.path)
if any(path.startswith(skip_path) for skip_path in [
    "/health", "/api/v1/health", "/docs", "/redoc", "/openapi.json",
    "/favicon.ico", "/static/", "/_internal"
]):
    return None
```

### **2. Added Error Suppression Parameter**

Modified `auth_service.verify_token()` to support error suppression for middleware:

```python
async def verify_token(self, token: str, suppress_errors: bool = False) -> Optional[User]:
    """
    Args:
        token: JWT token to verify
        suppress_errors: If True, suppresses warning logs for invalid tokens (useful for middleware)
    """
```

### **3. Conditional Error Logging**

Updated JWT error handling to respect the suppress_errors flag:

```python
except jwt.ExpiredSignatureError:
    if not suppress_errors:
        logger.warning(f"JWT token expired for user {user_id or 'unknown'}")
    return None
except jwt.InvalidTokenError:
    if not suppress_errors:
        logger.warning(f"Invalid JWT token for user {user_id or 'unknown'}")
    return None
```

### **4. Updated Middleware Call**

Modified middleware to use error suppression:

```python
# Validate token and extract user info (suppress JWT errors for middleware)
auth_service = get_auth_service()
user = await auth_service.verify_token(token, suppress_errors=True)
```

---

## 🎯 **Expected Behavior Now**

### **✅ System Requests (No JWT Errors)**
- Health checks: `/health`, `/api/v1/health`
- Documentation: `/docs`, `/redoc`, `/openapi.json`
- Static files: `/favicon.ico`, `/static/*`
- Internal endpoints: `/_internal/*`

**Result**: No JWT validation attempted, no error logs

### **✅ User Requests (Normal JWT Validation)**
- API endpoints: `/api/v1/*` (except health)
- Authentication endpoints: `/auth/*`
- Admin endpoints: `/api/v1/admin/*`

**Result**: Normal JWT validation with appropriate error logging for invalid user tokens

### **✅ Startup Process**
- Backend service starts cleanly
- Workers start without JWT errors
- Internal health checks work silently
- No "Invalid JWT token for user unknown" spam

---

## 🧪 **Testing the Fix**

### **1. Clean Startup Test**
```bash
# Start only backend service
cd services/backend-service
python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload

# Expected: No JWT error messages during startup
```

### **2. Health Check Test**
```bash
# Should work without JWT errors
curl http://localhost:3001/health
curl http://localhost:3001/api/v1/health
```

### **3. User Authentication Test**
```bash
# Should still validate JWT tokens and log errors for invalid tokens
curl -H "Authorization: Bearer invalid_token" http://localhost:3001/api/v1/admin/workers/status

# Expected: Proper JWT validation error (not suppressed)
```

---

## 📋 **Files Modified**

### **Backend Service**
1. `services/backend-service/app/core/client_logging_middleware.py`
   - Added system endpoint skip logic
   - Updated to use error suppression

2. `services/backend-service/app/auth/auth_service.py`
   - Added `suppress_errors` parameter to `verify_token()`
   - Conditional error logging based on suppress_errors flag

---

## 🎉 **Benefits**

1. ✅ **Clean Startup**: No more JWT error spam during service startup
2. ✅ **System Stability**: Internal requests don't trigger authentication
3. ✅ **Proper Logging**: User authentication errors still logged appropriately
4. ✅ **Performance**: Reduced unnecessary JWT validation for system requests
5. ✅ **Developer Experience**: Clean logs during development
6. ✅ **Backward Compatibility**: No changes to existing authentication flow

---

## 🚀 **Verification**

After applying this fix:

1. **Start backend service** - Should see clean startup logs
2. **No JWT errors** during worker initialization
3. **Health checks work** without authentication attempts
4. **User authentication** still works normally with proper error logging
5. **Multi-tenant workers** start without JWT issues

This fix ensures that the **multi-tenant worker architecture** can start cleanly without JWT authentication errors, while maintaining proper security for user-facing endpoints! 🔒
