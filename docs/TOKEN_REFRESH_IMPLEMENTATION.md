# Token Refresh Implementation

## 🎯 **Problem Solved**

**Issue**: ETL frontend users were getting 401 Unauthorized errors because JWT tokens expire after 5 minutes, but there was no automatic token refresh mechanism.

**Root Cause**: 
- Auth service configured with 5-minute token expiry for security
- ETL frontend had no token refresh functionality
- Users were being logged out every 5 minutes

## ✅ **Solution Implemented**

### **1. Backend Token Refresh Endpoint**

**File**: `services/backend-service/app/api/auth_routes.py`

Added `/api/v1/auth/refresh` endpoint that:
- Validates current token via auth service
- Generates new token using existing user data
- Returns new token with same user permissions
- Maintains session continuity

```python
@router.post("/refresh")
async def refresh_token(request: Request):
    """Token refresh endpoint. Validates current token and returns a new one if valid."""
    # Validates current token
    # Generates new token for same user
    # Returns: {"success": True, "token": "new_jwt_token", "user": user_data}
```

### **2. Auth Service Token Creation**

**File**: `services/backend-service/app/auth/auth_service.py`

Added `create_access_token()` method:
- Creates JWT tokens with proper expiry (5 minutes)
- Uses same secret key and algorithm as auth service
- Maintains token format consistency

```python
def create_access_token(self, user_data: Dict[str, Any]) -> str:
    """Create a new JWT access token for the given user data"""
    # Creates JWT with 5-minute expiry
    # Uses consistent payload format
    # Returns signed JWT token
```

### **3. Frontend Token Refresh Context**

**File**: `services/etl-frontend/src/contexts/AuthContext.tsx`

Added automatic token refresh functionality:
- `refreshToken()` method for manual refresh
- Automatic refresh when token expires in <1 minute
- Enhanced session validation with proactive refresh

```typescript
// Refresh JWT token
const refreshToken = async (): Promise<boolean> => {
  // Calls /api/v1/auth/refresh endpoint
  // Updates localStorage with new token
  // Updates axios headers
  // Returns success status
}
```

### **4. Enhanced Session Validation**

Updated session validation to:
- Check token expiry every 30 seconds (improved from 60 seconds)
- Automatically refresh tokens expiring within 1 minute
- Parse JWT payload to check expiry time
- Graceful fallback to logout if refresh fails

### **5. API Interceptor with Retry**

**File**: `services/etl-frontend/src/services/etlApiService.ts`

Enhanced axios interceptor to:
- Detect 401 errors from expired tokens
- Automatically attempt token refresh
- Retry original request with new token
- Fallback to logout if refresh fails

```typescript
// Response interceptor for error handling with token refresh
etlApi.interceptors.response.use(
  (response) => response,
  async (error) => {
    // On 401 error, try to refresh token
    // Retry original request with new token
    // Logout if refresh fails
  }
)
```

---

## 🔧 **Configuration**

### **Token Expiry Settings**

**Auth Service**: `services/auth-service/app/core/config.py`
```python
JWT_EXPIRY_MINUTES: int = 5  # Short expiry for security - frontend should refresh tokens
```

**Backend Service**: `services/backend-service/app/core/config.py`
```python
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # Used for validation, not generation
```

### **Refresh Timing**

- **Token Expiry**: 5 minutes
- **Session Check**: Every 30 seconds
- **Proactive Refresh**: When <1 minute remaining
- **Retry Logic**: Single retry on 401 errors

---

## 🎉 **Benefits**

1. ✅ **Seamless User Experience**: No more unexpected logouts
2. ✅ **Security Maintained**: 5-minute token expiry preserved
3. ✅ **Automatic Recovery**: Failed API calls automatically retry with fresh tokens
4. ✅ **Proactive Refresh**: Tokens refreshed before expiry
5. ✅ **Graceful Degradation**: Logout only when refresh fails
6. ✅ **Performance**: Reduced authentication overhead

---

## 🧪 **Testing the Fix**

### **1. Login and Wait**
1. Login to ETL frontend
2. Wait 4+ minutes (token should auto-refresh)
3. Verify no logout occurs
4. Check browser console for refresh logs

### **2. API Call Test**
1. Login to ETL frontend
2. Wait for token to expire (5+ minutes)
3. Navigate to Queue Management page
4. Verify API calls work (should auto-refresh and retry)

### **3. Manual Refresh Test**
```javascript
// In browser console
const { refreshToken } = useAuth();
refreshToken().then(success => console.log('Refresh success:', success));
```

---

## 🔍 **Monitoring**

### **Browser Console Logs**
- `✅ Token refreshed successfully` - Successful refresh
- `Token expiring soon, attempting refresh...` - Proactive refresh
- `❌ Failed to refresh token` - Refresh failure (will logout)

### **Backend Logs**
- `Token refreshed successfully for user_id: X` - Successful refresh
- `Token refresh error: ...` - Refresh failure details

### **Network Tab**
- `POST /api/v1/auth/refresh` - Refresh requests
- `200 OK` responses with new tokens
- Automatic retry of failed 401 requests

---

## 🚀 **Result**

**Before**: Users logged out every 5 minutes with 401 errors
**After**: Seamless experience with automatic token refresh

The ETL frontend now maintains user sessions indefinitely while preserving the security benefits of short-lived tokens! 🎉

---

## 🔄 **Frontend-App Service Updated Too**

### **Additional Changes Made**

**File**: `services/frontend-app/src/contexts/AuthContext.tsx`

1. **Added `refreshToken()` method** - Same functionality as ETL frontend
2. **Enhanced session validation** - Proactive token refresh before expiry
3. **Updated axios interceptor** - Automatic retry on 401 errors with token refresh
4. **Improved timing** - Check every 30 seconds instead of 10 minutes

**File**: `services/frontend-app/src/services/apiService.ts`

1. **Fixed import path** - Changed from `apiTenant.js` to `apiClient.js`

### **Consistent Behavior Across Services**

Both `etl-frontend` and `frontend-app` now have:
- ✅ **Automatic token refresh** before expiry
- ✅ **API retry logic** on 401 errors
- ✅ **Proactive refresh** when <1 minute remaining
- ✅ **30-second validation** intervals
- ✅ **Graceful fallback** to logout if refresh fails

This ensures a **consistent user experience** across all frontend services! 🚀
