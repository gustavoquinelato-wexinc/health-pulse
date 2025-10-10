# WebSocket Authentication Fix

## Problem

**Original Issue**: WebSocket connections were established **before user login**, creating security and architectural problems:

1. **Security Hole**: No authentication - anyone could connect with `?tenant_id=1` query parameter
2. **Wrong Timing**: Connections established on service startup, not after user login
3. **Hardcoded Tenant**: `tenant_id=1` hardcoded in frontend, not extracted from user session
4. **No User Context**: WebSocket had no knowledge of which user was connected

---

## Solution

**New Architecture**: WebSocket connections are now **authenticated and user-tied**:

1. **Authentication Required**: JWT token required for WebSocket handshake
2. **Connect After Login**: WebSocket initialized AFTER successful user authentication
3. **Tenant from Token**: `tenant_id` extracted from JWT token on backend
4. **Tenant Broadcasting**: All admins of same tenant see same job progress (already working, just needed auth)

---

## Changes Made

### 1. Backend: WebSocket Endpoint Authentication

**File**: `services/backend-service/app/api/websocket_routes.py`

**Before** (lines 178-218):
```python
@router.websocket("/ws/progress/{job_name}")
async def websocket_progress_endpoint(websocket: WebSocket, job_name: str, tenant_id: int = Query(1)):
    """
    Service-to-service WebSocket endpoint for real-time job progress updates.
    
    Note: This is a service-to-service connection - no user authentication required.
    """
    logger.info(f"[WS] Service-to-service WebSocket connection for tenant {tenant_id} job: {job_name}")
    
    # Register client (this will accept the WebSocket connection)
    await websocket_manager.connect(websocket, tenant_id, job_name)
    ...
```

**After** (lines 178-239):
```python
@router.websocket("/ws/progress/{job_name}")
async def websocket_progress_endpoint(websocket: WebSocket, job_name: str, token: str = Query(...)):
    """
    Authenticated WebSocket endpoint for real-time job progress updates.
    
    Note: This endpoint requires user authentication. The tenant_id is extracted from the JWT token.
    All admins of the same tenant will see the same job progress (tenant-isolated broadcasting).
    """
    try:
        # Verify token and extract tenant_id
        from app.auth.auth_service import get_auth_service
        auth_service = get_auth_service()
        
        user = await auth_service.verify_token(token, suppress_errors=True)
        
        if not user:
            logger.warning(f"[WS] WebSocket connection rejected: Invalid or expired token")
            await websocket.close(code=1008, reason="Invalid or expired token")
            return
        
        tenant_id = user.tenant_id
        logger.info(f"[WS] ✅ Authenticated WebSocket connection: user={user.email}, tenant={tenant_id}, job={job_name}")

        # Register client (this will accept the WebSocket connection)
        await websocket_manager.connect(websocket, tenant_id, job_name)
        ...
```

**Key Changes**:
- ✅ Changed parameter from `tenant_id: int = Query(1)` to `token: str = Query(...)`
- ✅ Added token verification using `auth_service.verify_token()`
- ✅ Extract `tenant_id` from verified user object
- ✅ Close connection with error code if token is invalid
- ✅ Log authenticated user email and tenant for audit trail

---

### 2. Frontend: WebSocket Service Refactoring

**File**: `services/etl-frontend/src/services/websocketService.ts`

#### 2.1 Add Auth Token Storage

**Before** (lines 37-65):
```typescript
class ETLWebSocketService {
  private connections: Map<string, WebSocket> = new Map()
  private listeners: Map<string, JobProgressListener[]> = new Map()
  private reconnectAttempts: Map<string, number> = new Map()
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000
  private isInitialized = false

  async initializeService() {
    // Guard against double initialization
    if (this.isInitialized) {
      return
    }
    this.isInitialized = true
    
    // Wait for backend and discover active jobs
    ...
  }
}
```

**After** (lines 37-89):
```typescript
class ETLWebSocketService {
  private connections: Map<string, WebSocket> = new Map()
  private listeners: Map<string, JobProgressListener[]> = new Map()
  private reconnectAttempts: Map<string, number> = new Map()
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000
  private isInitialized = false
  private authToken: string | null = null  // ✅ NEW: Store auth token

  /**
   * Initialize WebSocket service after user login with authentication token
   * This should be called from AuthContext after successful login
   */
  async initializeService(token: string) {  // ✅ NEW: Requires token parameter
    if (this.isInitialized) {
      return
    }
    this.isInitialized = true
    this.authToken = token  // ✅ NEW: Store token
    
    console.log('🔌 ETL WebSocket Service: Initializing with authenticated token')
    ...
  }

  /**
   * Disconnect all WebSocket connections (called on logout)
   */
  disconnectAll() {  // ✅ NEW: Cleanup method
    console.log('🔌 ETL WebSocket Service: Disconnecting all connections')
    this.connections.forEach((ws, jobName) => {
      try {
        ws.close()
      } catch (error) {
        console.error(`Failed to close WebSocket for ${jobName}:`, error)
      }
    })
    this.connections.clear()
    this.listeners.clear()
    this.reconnectAttempts.clear()
    this.isInitialized = false
    this.authToken = null
  }
}
```

#### 2.2 Use Token in WebSocket URL

**Before** (lines 220-229):
```typescript
private createConnection(jobName: string) {
  try {
    // Service-to-service WebSocket connection - no authentication required
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const tenantId = 1  // ❌ Hardcoded!
    const wsUrl = `${protocol}//localhost:3001/ws/progress/${jobName}?tenant_id=${tenantId}`
    ...
```

**After** (lines 220-230):
```typescript
private createConnection(jobName: string) {
  try {
    if (!this.authToken) {
      console.error(`❌ Cannot create WebSocket connection for ${jobName}: No auth token`)
      return
    }

    // Authenticated WebSocket connection - token required
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//localhost:3001/ws/progress/${jobName}?token=${encodeURIComponent(this.authToken)}`
    ...
```

#### 2.3 Use Token in API Calls

**Before** (lines 109-132):
```typescript
private async discoverAndConnectActiveJobs() {
  try {
    // Fetch active jobs - no authentication
    const response = await fetch('http://localhost:3001/api/v1/websocket/status?active_jobs=true&tenant_id=1')
    ...
```

**After** (lines 109-141):
```typescript
private async discoverAndConnectActiveJobs() {
  try {
    if (!this.authToken) {
      console.error('❌ ETL WebSocket Service: No auth token available')
      return
    }

    // Fetch active jobs using authenticated API call
    const response = await fetch('http://localhost:3001/api/v1/websocket/status?active_jobs=true', {
      headers: {
        'Authorization': `Bearer ${this.authToken}`
      }
    })
    ...
```

---

### 3. Frontend: Remove Startup Initialization

**File**: `services/etl-frontend/src/main.tsx`

**Before** (lines 1-15):
```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { etlWebSocketService } from './services/websocketService'

// Initialize service-to-service WebSocket communication immediately on service startup
etlWebSocketService.initializeService()  // ❌ Called before user login!

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

**After** (lines 1-13):
```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// WebSocket service is now initialized AFTER user login (in AuthContext)
// This ensures proper authentication and tenant isolation

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

---

### 4. Frontend: Initialize After Login

**File**: `services/etl-frontend/src/contexts/AuthContext.tsx`

#### 4.1 Import WebSocket Service

**Added** (line 5):
```typescript
import { etlWebSocketService } from '../services/websocketService'
```

#### 4.2 Initialize After Login

**Added** (lines 647-653):
```typescript
// After successful login...
setUser(formattedUser)
setupCrossServiceCookie(token)

// Initialize WebSocket service with authenticated token
try {
  await etlWebSocketService.initializeService(token)
  console.log('✅ WebSocket service initialized after login')
} catch (error) {
  console.error('❌ Failed to initialize WebSocket service:', error)
}
```

#### 4.3 Initialize After Token Validation

**Added** (lines 578-588):
```typescript
// After token validation (user already logged in)...
setUser(formattedUser)

// Initialize WebSocket service with existing token
const token = localStorage.getItem('pulse_token')
if (token) {
  try {
    await etlWebSocketService.initializeService(token)
    console.log('✅ WebSocket service initialized after token validation')
  } catch (error) {
    console.error('❌ Failed to initialize WebSocket service:', error)
  }
}
```

#### 4.4 Initialize After Cross-Service Auth

**Added** (lines 361-367):
```typescript
// After cross-service authentication...
setUser(formattedUser)

// Initialize WebSocket service with cross-service token
try {
  await etlWebSocketService.initializeService(event.data.token)
  console.log('✅ WebSocket service initialized after cross-service auth')
} catch (error) {
  console.error('❌ Failed to initialize WebSocket service:', error)
}
```

#### 4.5 Disconnect on Logout

**Added** (lines 754-760):
```typescript
const logout = async () => {
  setUser(null)

  // Disconnect all WebSocket connections
  try {
    etlWebSocketService.disconnectAll()
    console.log('✅ WebSocket service disconnected on logout')
  } catch (error) {
    console.error('❌ Failed to disconnect WebSocket service:', error)
  }
  
  // ... rest of logout logic
}
```

#### 4.6 Disconnect on Cross-Tab Logout

**Added** (line 293):
```typescript
const handleStorageChange = (event: StorageEvent) => {
  if (event.key === 'pulse_logout_event') {
    etlWebSocketService.disconnectAll()  // ✅ NEW
    setUser(null)
    localStorage.clear()
    // ...
  }
}
```

---

## Architecture Flow

### Before Fix ❌

```
1. Service Starts
   ↓
2. main.tsx: etlWebSocketService.initializeService()  ← NO AUTH!
   ↓
3. WebSocket connects with ?tenant_id=1  ← HARDCODED!
   ↓
4. User visits /login page
   ↓
5. User logs in
   ↓
6. WebSocket already connected (wrong tenant if multi-tenant!)
```

### After Fix ✅

```
1. Service Starts
   ↓
2. main.tsx: (no WebSocket initialization)
   ↓
3. User visits /login page
   ↓
4. User logs in
   ↓
5. AuthContext: etlWebSocketService.initializeService(token)  ← WITH AUTH!
   ↓
6. WebSocket connects with ?token=<jwt>
   ↓
7. Backend verifies token → extracts tenant_id → connects to tenant-specific channel
   ↓
8. User sees progress for their tenant's jobs
   ↓
9. User logs out
   ↓
10. AuthContext: etlWebSocketService.disconnectAll()  ← CLEANUP!
```

---

## Security Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Authentication** | ❌ None | ✅ JWT token required |
| **Tenant Isolation** | ❌ Hardcoded `tenant_id=1` | ✅ Extracted from token |
| **User Context** | ❌ No user info | ✅ User email logged |
| **Connection Timing** | ❌ Before login | ✅ After login |
| **Token Expiry** | ❌ N/A | ✅ Connection closed if token expires |
| **Logout Cleanup** | ❌ Connections persist | ✅ All connections closed |

---

## Testing

### Test 1: Login Flow
1. Start backend-service and etl-frontend
2. Navigate to `http://localhost:5173/login`
3. Login with valid credentials
4. **Expected**: Console shows "✅ WebSocket service initialized after login"
5. **Expected**: Backend logs show "✅ Authenticated WebSocket connection: user=<email>, tenant=<id>"

### Test 2: Invalid Token
1. Modify WebSocket service to use invalid token
2. Try to connect
3. **Expected**: WebSocket connection rejected with code 1008
4. **Expected**: Backend logs show "WebSocket connection rejected: Invalid or expired token"

### Test 3: Logout Flow
1. Login successfully
2. Verify WebSocket is connected
3. Logout
4. **Expected**: Console shows "✅ WebSocket service disconnected on logout"
5. **Expected**: All WebSocket connections closed

### Test 4: Multi-Tenant Isolation
1. Login as user from tenant 1
2. Run Jira job for tenant 1
3. **Expected**: User sees progress updates
4. Login as user from tenant 2 (different browser)
5. **Expected**: User does NOT see tenant 1's progress

---

## Summary

**Problem**: WebSocket connections were insecure and established before user login

**Solution**: 
- ✅ Backend now requires JWT token for WebSocket handshake
- ✅ Frontend initializes WebSocket AFTER login with auth token
- ✅ Tenant ID extracted from token (no hardcoding)
- ✅ All connections cleaned up on logout
- ✅ Tenant-based broadcasting already working, just needed auth layer

**Impact**: Secure, user-tied WebSocket connections with proper tenant isolation! 🎉

