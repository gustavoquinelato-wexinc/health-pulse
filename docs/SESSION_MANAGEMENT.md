# Session Management - Authentication, Synchronization & User Preferences

## Overview

This document consolidates all session management functionality across the Pulse Platform, including:
- **Login/Logout** - User authentication flow
- **Session Synchronization** - Real-time cross-service session sync via WebSocket
- **User Preferences** - Color schemas and light/dark mode
- **Token Management** - JWT token refresh and validation

---

## 🔐 Authentication Flow

### Login Process

```
User → Frontend → Backend Service → Auth Service → Database
                                          ↓
                                    JWT Token + Session
                                          ↓
                                    Frontend (stores token)
                                          ↓
                                    WebSocket Connection
```

**Steps:**
1. User submits credentials (email/password)
2. Frontend sends to Backend Service `/api/v1/auth/login`
3. Backend validates credentials against database
4. Backend generates JWT token (5-minute expiry)
5. Backend creates session record in database + Redis cache
6. Frontend stores token in memory and localStorage
7. Frontend establishes WebSocket connection for real-time sync

### Logout Process

```
User → Frontend → Backend Service → Database
                        ↓
                  WebSocket Broadcast
                        ↓
            All User's Devices/Tabs
```

**Steps:**
1. User clicks logout
2. Frontend disconnects WebSocket
3. Frontend sends logout request to Backend
4. Backend invalidates session in database + Redis
5. Backend broadcasts `SESSION_INVALIDATED` to all user's WebSocket connections
6. All tabs/devices receive instant logout notification
7. Frontend clears token and redirects to login

---

## 🔄 Real-Time Session Synchronization

### WebSocket Architecture

The platform uses WebSocket connections for **instant real-time synchronization** across all tabs, windows, and devices.

#### Backend: SessionWebSocketManager

**Location:** `services/backend-service/app/api/websocket_routes.py`

**Features:**
- Maintains connections indexed by `user_id`
- Supports multiple connections per user (multiple tabs/devices)
- Automatic cleanup of disconnected clients
- Broadcast methods for each event type

**Key Methods:**
```python
async def connect(websocket, user_id, user_email)
async def disconnect(websocket, user_id, user_email)
async def broadcast_to_user(user_id, message, event_type)
async def broadcast_logout(user_id, reason)
async def broadcast_login(user_id, user_email)
async def broadcast_color_schema_change(user_id, colors)
async def broadcast_theme_mode_change(user_id, theme_mode)
```

#### Frontend: SessionWebSocketService

**Location:**
- `services/frontend-app/src/services/sessionWebSocketService.ts`
- `services/frontend-etl/src/services/sessionWebSocketService.ts`

**Features:**
- Singleton service instance
- Automatic reconnection (up to 5 attempts)
- Ping/pong keep-alive (every 30 seconds)
- Event handler callbacks

**Usage:**
```typescript
sessionWebSocketService.connect(token, {
  onLogout: () => logout(),
  onThemeModeChange: (mode: string) => updateTheme(mode),
  onColorSchemaChange: (colors: any) => refreshUserColors()
})
```

### WebSocket Endpoint

**Endpoint:** `ws://localhost:3001/ws/session?token={jwt_token}`

**Authentication:** Requires valid JWT token as query parameter

**Message Types:**

#### Server → Client

**1. Session Invalidated (Logout)**
```json
{
  "type": "SESSION_INVALIDATED",
  "event": "logout",
  "reason": "user_logout",
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

**2. Session Created (Login)**
```json
{
  "type": "SESSION_CREATED",
  "event": "login",
  "user_email": "user@example.com",
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

**3. Color Schema Updated**
```json
{
  "type": "COLOR_SCHEMA_UPDATED",
  "event": "color_change",
  "colors": {
    "light": { "color1": "#2862EB", ... },
    "dark": { "color1": "#3B7FFF", ... }
  },
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

**4. Theme Mode Updated**
```json
{
  "type": "THEME_MODE_UPDATED",
  "event": "theme_change",
  "theme_mode": "dark",
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

#### Client → Server

**Ping (Keep-Alive)**
```json
{
  "type": "ping"
}
```

**Server Response:**
```json
{
  "type": "pong",
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

### Backup Mechanisms

#### localStorage Events (Same-Origin)

**Purpose:** Backup mechanism for same-origin tabs (e.g., multiple tabs on port 3000)

**Implementation:**
```typescript
// Broadcast logout to same-origin tabs
localStorage.setItem('pulse_logout_event', Date.now().toString())
localStorage.removeItem('pulse_logout_event')

// Listen for logout events
window.addEventListener('storage', (event) => {
  if (event.key === 'pulse_logout_event') {
    logout()
  }
})
```

**Limitation:** Only works for tabs on the same domain:port

---

## 🎨 User Preferences

### Color Schema Management

**Storage:** `client_color_settings` table in database

**Structure:**
- **12 color combinations per tenant** (2 modes × 2 themes × 3 accessibility levels)
  - **Modes:** default, custom
  - **Themes:** light, dark
  - **Accessibility:** regular, AA, AAA compliance

**API Endpoints:**

**Get Color Schema:**
```http
GET /api/v1/user/color-schema
```

**Update Color Schema (Admin Only):**
```http
PUT /api/v1/admin/color-schema/unified
{
  "light": { "color1": "#2862EB", ... },
  "dark": { "color1": "#3B7FFF", ... }
}
```

**Real-Time Sync:**
When admin updates color schema:
1. Backend updates database
2. Backend broadcasts to all tenant users via WebSocket
3. All users' frontends receive instant update
4. Colors refresh without page reload

### Theme Mode (Light/Dark)

**Storage:** `users.theme_mode` column in database

**Values:** `light` | `dark`

**API Endpoints:**

**Get Theme Mode:**
```http
GET /api/v1/user/theme-mode
```

**Update Theme Mode:**
```http
PUT /api/v1/user/theme-mode
{
  "mode": "dark"
}
```

**Real-Time Sync:**
When user changes theme mode:
1. Backend updates database
2. Backend broadcasts to all user's devices via WebSocket
3. All tabs/devices update theme instantly

**Frontend Implementation:**
```typescript
// Update theme mode
const updateTheme = (mode: string) => {
  localStorage.setItem('pulse_theme', mode)
  document.documentElement.setAttribute('data-theme', mode)
}

// Listen for WebSocket updates
sessionWebSocketService.connect(token, {
  onThemeModeChange: (mode) => updateTheme(mode)
})
```

---

## 🔑 Token Management

### JWT Token Configuration

**Expiry:** 5 minutes (for enhanced security)

**Algorithm:** HS256

**Payload:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "tenant_id": 1,
  "is_admin": false,
  "exp": 1705320600
}
```

### Automatic Token Refresh

**Configuration:**
- **Token Expiry:** 5 minutes
- **Session Check:** Every 30 seconds
- **Proactive Refresh:** When <1 minute remaining
- **Retry Logic:** Single retry on 401 errors

**Frontend Implementation:**
```typescript
// Check token expiry every 30 seconds
setInterval(async () => {
  const token = localStorage.getItem('pulse_token')
  if (!token) return

  const payload = JSON.parse(atob(token.split('.')[1]))
  const expiresAt = payload.exp * 1000
  const now = Date.now()
  const timeUntilExpiry = expiresAt - now

  // Refresh if less than 1 minute remaining
  if (timeUntilExpiry < 60000) {
    await refreshToken()
  }
}, 30000)
```

### Session Validation

**Endpoint:** `POST /api/v1/auth/validate`

**Purpose:** Validate token and session status

**Response:**
```json
{
  "valid": true,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "tenant_id": 1
  }
}
```

---

## 🔒 Security Considerations

1. **Authentication Required** - All WebSocket connections require valid JWT token
2. **User Isolation** - Messages only broadcast to specific user's connections
3. **Tenant Isolation** - Color schema changes respect tenant boundaries
4. **Token Validation** - Token verified on connection, invalid tokens rejected
5. **Auto-Disconnect** - Invalid/expired tokens cause immediate disconnect
6. **Session Timeout** - 480 minutes (8 hours) of inactivity
7. **Concurrent Sessions** - Multiple sessions allowed per user

---

## 📊 Monitoring

### WebSocket Status Endpoint

**GET** `/api/v1/websocket/session/status`

**Response:**
```json
{
  "total_connections": 5,
  "connected_users": [1, 2, 3],
  "user_count": 3
}
```

### Logs

**Backend Logs:**
```
[SessionWS] ✅ User connected: user@example.com (user_id=1, connections=2)
[SessionWS] 📢 Broadcasting logout to user_id=1 (2 connections)
[SessionWS] ✅ Broadcast complete: 2/2 successful, 0 failed
[SessionWS] 🔌 User disconnected: user@example.com (user_id=1, remaining=1)
```

**Frontend Logs:**
```
[SessionWS] Connecting to session WebSocket...
[SessionWS] ✅ Connected
[SessionWS] Received message: SESSION_INVALIDATED logout
[SessionWS] 🚪 Session invalidated: user_logout
[SessionWS] Disconnecting...
```

---

## 🧪 Testing

### Test 1: Logout Synchronization
1. Open frontend-app in Tab 1 (http://localhost:3000)
2. Open frontend-etl in Tab 2 (http://localhost:3333)
3. Login to both
4. Logout from Tab 1
5. **Expected:** Tab 2 logs out instantly (< 1 second)

### Test 2: Theme Mode Synchronization
1. Open frontend-app in multiple tabs
2. Change theme mode (dark/light) in one tab
3. **Expected:** All tabs update theme instantly

### Test 3: Color Schema Synchronization
1. Open frontend-app as admin
2. Open frontend-etl in another tab
3. Change color schema in frontend-app
4. **Expected:** frontend-etl updates colors instantly

### Test 4: Multi-Device
1. Login on Device A (laptop)
2. Login on Device B (phone/tablet)
3. Logout from Device A
4. **Expected:** Device B logs out instantly

---

## 🚀 Benefits Over Previous Approach

| Feature | Old Approach | New WebSocket Approach |
|---------|-------------|------------------------|
| **Logout Sync** | 60-second polling delay | Instant (< 100ms) |
| **Cross-Origin** | postMessage (parent/child only) | Works across all tabs/devices |
| **Theme Sync** | Manual refresh required | Instant automatic update |
| **Color Sync** | Page reload required | Real-time without reload |
| **Network Efficiency** | Constant polling | Event-driven (no waste) |
| **Multi-Device** | Not supported | Full support |
| **Reliability** | HTTP notifications failed | WebSocket with auto-reconnect |

---

## 📝 Migration Notes

### Removed/Deprecated
- ❌ HTTP `/api/logout-notification` endpoints (never implemented)
- ❌ postMessage cross-origin notifications (unreliable)
- ❌ 60-second polling for session validation (replaced with WebSocket)
- ❌ Manual fetch() calls to notify other frontends

### Kept for Compatibility
- ✅ localStorage events (same-origin tabs backup)
- ✅ Periodic token validation (backup mechanism)
- ✅ Cookie-based session sharing

---

## 🔗 Related Documentation

- **Security & Authentication:** `docs/SECURITY.md`
- **Architecture Overview:** `docs/architecture.md`
- **Backend Service:** `services/backend-service/README.md`
- **Frontend App:** `services/frontend-app/README.md`
- **ETL Frontend:** `services/frontend-etl/README.md`

