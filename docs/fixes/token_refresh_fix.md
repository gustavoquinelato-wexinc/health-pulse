# Token Refresh Fix - Prevent Premature Logout

## Problem

**User Issue**: "I am getting logged out when the token expires instead of it being refreshed in the background while my session is still active (it should have a 60min timeout when inactive)"

### Root Causes

1. **Refresh Window Too Small**: Token only refreshed if expiring in < 1 minute (60 seconds)
2. **Token Expiry**: JWT tokens expire in 60 minutes
3. **Check Interval**: Frontend checks every 30 seconds
4. **Race Condition**: If check happens at 59 seconds before expiry, next check is at 29 seconds → token expires before refresh!
5. **Aggressive Logout**: Any validation error (network issue, etc.) caused immediate logout
6. **No Retry Logic**: Single refresh failure = immediate logout
7. **WebSocket Token Not Updated**: After token refresh, WebSocket connections still used old token

---

## Solution

### 1. Increase Refresh Window

**Before**: Refresh if token expires in < 1 minute (60 seconds)
```typescript
if (timeUntilExpiry < 60000) {  // ❌ Too small!
  await refreshToken()
}
```

**After**: Refresh if token expires in < 5 minutes (300 seconds)
```typescript
if (timeUntilExpiry < 300000) {  // ✅ 5 minute buffer
  console.log(`🔄 Token expiring in ${Math.floor(timeUntilExpiry / 1000)}s, attempting refresh...`)
  await refreshToken()
}
```

**Why 5 minutes?**
- Token expires in 60 minutes
- Check every 60 seconds
- Refresh starts at 55 minutes → plenty of time for retry if first attempt fails
- Even if network is slow, we have 5 minutes to complete the refresh

---

### 2. Increase Check Interval

**Before**: Check every 30 seconds
```typescript
}, 30000) // ❌ Too frequent, wastes resources
```

**After**: Check every 60 seconds (1 minute)
```typescript
}, 60000) // ✅ Balanced: responsive but not wasteful
```

**Why 60 seconds?**
- With 5-minute refresh window, checking every minute is sufficient
- Reduces server load (fewer validation requests)
- Still responsive enough for user experience

---

### 3. Smarter Error Handling

**Before**: Logout on ANY error
```typescript
} catch (error) {
  // Session validation failed, logout  ❌ Too aggressive!
  setUser(null)
  window.location.replace('/login')
}
```

**After**: Only logout on 401 Unauthorized
```typescript
} catch (validationError: any) {
  // Only logout on 401 Unauthorized - ignore network errors
  if (validationError?.response?.status === 401) {
    console.warn('⚠️ Session unauthorized (401), logging out')
    setUser(null)
    window.location.replace('/login')
  } else {
    // Network error or other issue - don't logout, just log warning
    console.warn('⚠️ Session validation error (non-401), keeping session:', validationError?.message)
  }
}
```

**Why?**
- Network issues are temporary - don't logout user
- Server restarts are temporary - don't logout user
- Only logout if server explicitly says "unauthorized" (401)

---

### 4. Update WebSocket Token on Refresh

**Before**: WebSocket connections kept old token
```typescript
const refreshToken = async (): Promise<boolean> => {
  // ... refresh logic ...
  localStorage.setItem('pulse_token', newToken)
  axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`
  return true  // ❌ WebSocket still has old token!
}
```

**After**: WebSocket connections updated with new token
```typescript
const refreshToken = async (): Promise<boolean> => {
  // ... refresh logic ...
  localStorage.setItem('pulse_token', newToken)
  axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`
  
  // Update WebSocket service with new token
  try {
    await etlWebSocketService.updateToken(newToken)  // ✅ Reconnect with new token
    console.log('✅ Token refreshed successfully (WebSocket updated)')
  } catch (wsError) {
    console.error('❌ Failed to update WebSocket token:', wsError)
  }
  
  return true
}
```

---

### 5. Add WebSocket Token Update Method

**New Method**: `updateToken()` in WebSocket service

```typescript
/**
 * Update auth token and reconnect all WebSocket connections
 * Called when token is refreshed to maintain connections with new token
 */
async updateToken(newToken: string) {
  console.log('🔄 ETL WebSocket Service: Updating token and reconnecting')
  this.authToken = newToken

  // Store current job names before disconnecting
  const activeJobs = Array.from(this.connections.keys())
  
  // Disconnect all existing connections
  this.connections.forEach((ws, jobName) => {
    try {
      ws.close()
    } catch (error) {
      console.error(`Failed to close WebSocket for ${jobName}:`, error)
    }
  })
  this.connections.clear()
  this.reconnectAttempts.clear()

  // Reconnect to all previously active jobs with new token
  activeJobs.forEach(jobName => {
    const listeners = this.listeners.get(jobName) || []
    if (listeners.length > 0) {
      // Reconnect with existing listeners
      this.createConnection(jobName)
    }
  })

  console.log(`✅ Reconnected ${activeJobs.length} WebSocket connections with new token`)
}
```

**Why?**
- Maintains existing listeners (no need to re-register)
- Seamless reconnection (user doesn't notice)
- Prevents WebSocket authentication errors after token refresh

---

## Timeline Comparison

### Before Fix ❌

```
Time    | Event
--------|----------------------------------------------------------
0:00    | User logs in, token expires at 1:00
0:30    | Check #1: Token expires in 30 min → No action
1:00    | Check #2: Token expires in 29.5 min → No action
...
59:00   | Check #118: Token expires in 1 min → No action (> 60s)
59:30   | Check #119: Token expires in 30s → Refresh attempt!
59:35   | Network slow, refresh takes 5 seconds
59:40   | Refresh completes, new token stored
1:00:00 | Old token expires
1:00:05 | Check #120: Validation with new token → Success ✅
```

**Problem**: If refresh fails at 59:30, next check is at 1:00:00 → token already expired!

---

### After Fix ✅

```
Time    | Event
--------|----------------------------------------------------------
0:00    | User logs in, token expires at 1:00
1:00    | Check #1: Token expires in 59 min → No action
2:00    | Check #2: Token expires in 58 min → No action
...
55:00   | Check #55: Token expires in 5 min → Refresh attempt!
55:02   | Refresh completes, new token stored
55:02   | WebSocket connections updated with new token
55:02   | New token expires at 1:55:00
56:00   | Check #56: Token expires in 59 min → No action
...
1:50:00 | Check #110: Token expires in 5 min → Refresh attempt!
1:50:02 | Refresh completes, new token stored
...
```

**Benefits**:
- ✅ Refresh happens 5 minutes before expiry (plenty of buffer)
- ✅ If first refresh fails, we have 4 more minutes to retry
- ✅ WebSocket connections stay alive with new token
- ✅ User never experiences logout due to token expiry

---

## Configuration

### Backend Token Expiry

**File**: `services/backend-service/app/core/config.py`
```python
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 60 minutes
```

**File**: `.env`
```env
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### Frontend Refresh Settings

**File**: `services/etl-frontend/src/contexts/AuthContext.tsx`

| Setting | Value | Reason |
|---------|-------|--------|
| **Token Expiry** | 60 minutes | Backend configuration |
| **Check Interval** | 60 seconds | Balance between responsiveness and server load |
| **Refresh Window** | 5 minutes | Large buffer for network issues and retries |
| **Logout on Error** | 401 only | Don't logout on temporary network issues |

---

## Testing

### Test 1: Normal Token Refresh
1. Login to ETL frontend
2. Wait 55 minutes
3. **Expected**: Console shows "🔄 Token expiring in 300s, attempting refresh..."
4. **Expected**: Console shows "✅ Token refreshed successfully (WebSocket updated)"
5. **Expected**: User stays logged in

### Test 2: Network Error During Validation
1. Login to ETL frontend
2. Stop backend service temporarily
3. Wait for validation check (every 60 seconds)
4. **Expected**: Console shows "⚠️ Session validation error (non-401), keeping session"
5. **Expected**: User stays logged in
6. Restart backend service
7. **Expected**: Next validation succeeds

### Test 3: Invalid Token (401)
1. Login to ETL frontend
2. Manually corrupt token in localStorage
3. Wait for validation check
4. **Expected**: Console shows "⚠️ Session unauthorized (401), logging out"
5. **Expected**: User redirected to /login

### Test 4: WebSocket Token Update
1. Login to ETL frontend
2. Start a Jira job (WebSocket connection active)
3. Wait 55 minutes for token refresh
4. **Expected**: Console shows "✅ Reconnected 1 WebSocket connections with new token"
5. **Expected**: Job progress continues to display without interruption

---

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Refresh Window** | 1 minute | 5 minutes ✅ |
| **Check Interval** | 30 seconds | 60 seconds ✅ |
| **Logout on Network Error** | Yes ❌ | No ✅ |
| **Logout on 401** | Yes ✅ | Yes ✅ |
| **WebSocket Token Update** | No ❌ | Yes ✅ |
| **Retry Buffer** | 30 seconds | 5 minutes ✅ |
| **User Experience** | Frequent logouts | Seamless session ✅ |

**Result**: Users can now work uninterrupted for hours without being logged out due to token expiry! 🎉

