# ETL Service Guide

This guide covers the ETL Service as an embedded component within the Pulse Platform, including job orchestration, embedded interface patterns, and integration best practices.

## 🏗️ **Embedded Architecture**

### **Service Role**
The ETL Service now operates as an embedded component within the Pulse Platform:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Pulse Platform                              │
│  ┌─────────────────┐                                           │
│  │   Frontend      │                                           │
│  │   (Port 3000)   │                                           │
│  │                 │                                           │
│  │  ┌─────────────┐│    ┌─────────────────┐                   │
│  │  │ ETL iframe  ││◄──►│  ETL Service    │                   │
│  │  │ (embedded)  ││    │  (Port 8000)    │                   │
│  │  └─────────────┘│    │                 │                   │
│  └─────────────────┘    │ • Authenticated APIs │                   │
│                         │ • Job Control   │                   │
│                         │ • Data Pipeline │                   │
│                         │ • Embedded UI   │                   │
│                         └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

### **Cross-Service Navigation Features**
- **Direct Navigation**: POST-based authentication for seamless service switching
- **Admin-Only Access**: Restricted to users with admin privileges
- **Shared Authentication**: Uses JWT tokens from Backend Service
- **Return Navigation**: Pulse button provides navigation back to frontend
- **Client Branding**: Dynamic logo loading based on user's client

### **URL Parameters for Embedding**
```
http://localhost:8000/home?embedded=true&token=JWT_TOKEN&theme=light&colorMode=default
```

**Parameters:**
- `embedded=true`: Enables embedded mode (hides header, adjusts styling)
- `token=JWT_TOKEN`: Authentication token from parent application
- `theme=light|dark`: Theme mode from parent application
- `colorMode=default|custom`: Color schema from parent application

## 🔐 **Admin-Only Authentication**

### **Admin Credentials Required**
All ETL Service functionality requires admin-level authentication. There is no separate "admin context" - everything is admin-protected:

```python
# Embedded authentication middleware
async def handle_embedded_auth(request: Request):
    # Check for token in URL parameters (embedded mode)
    token = request.query_params.get('token')

    if not token:
        # Fall back to cookie/header authentication
        token = request.cookies.get('pulse_token')
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]

    if token:
        # Validate with Backend Service
        user_data = await auth_service.verify_token(token)
        if user_data and user_data.get('is_admin'):
            return user_data

    # Redirect to platform login for direct access without authentication
    return RedirectResponse(url="/login?error=authentication_required")

    # Return 401 for embedded access
    raise HTTPException(status_code=401, detail="Authentication required")
```

### **Admin Access Control**
```python
# All ETL routes require admin authentication
@router.get("/home")
async def home(
    request: Request,
    current_user: UserData = Depends(require_admin_authentication)
):
    # All ETL functionality requires admin credentials
    # No additional admin check needed - require_admin_authentication handles it
    if request.query_params.get('embedded'):
        # Handle embedded mode
            return templates.TemplateResponse("access_denied.html", {
                "request": request,
                "message": "ETL Management requires administrator privileges"
            })
        else:
            # Redirect to login with error
            return RedirectResponse(url="/login?error=permission_denied&resource=etl_management")
```

### **Client Logo Integration**
```python
# Dynamic client logo loading
async def load_client_logo(user_data: dict) -> str:
    client_name = user_data.get('client_name', '').lower()

    client_logos = {
        'wex': '/static/wex-logo-image.png',
        'techcorp': '/static/techcorp-logo.png',
        # Add more client logos as needed
    }

    return client_logos.get(client_name, '/static/wex-logo-image.png')  # Default
```

## 🔄 Job Orchestration

### **Job Management Architecture**
- **Main Orchestrator**: Runs every 60 minutes, manages both jobs
- **Job States**: NOT_STARTED, PENDING, RUNNING, FINISHED, ERROR, PAUSED
- **Recovery Logic**: Retry failed jobs with configurable intervals
- **Force Stop**: Instant termination with proper cleanup

### **Job State Transitions**
```
NOT_STARTED → PENDING → RUNNING → FINISHED/ERROR
RUNNING → PAUSED (manual pause)
PAUSED → RUNNING (manual resume)
ERROR → PENDING (retry logic)
```

### **Orchestrator Patterns**
```python
# Job state management
if other_job_status == "PAUSED":
    # Keep other job PAUSED, don't change to FINISHED
    keep_paused_job_state()

# Force stop implementation
async def force_stop_job(job_type):
    # Set stop flag immediately
    set_stop_flag(job_type)
    # Disable other job controls
    disable_other_controls()
    # Wait for graceful termination
    await wait_for_job_cleanup()
```

### **Recovery Strategies**
- **Sleep Orchestrator**: Separate 5-30 minute interval for retries
- **Anticipatory Retry**: Don't wait for main 60-minute cycle
- **Configurable Retry**: User-friendly retry settings near main orchestrator

## 📊 Data Processing

### **Jira Data Extraction**
- **Pagination**: Check cancellation at each API request
- **Rate Limiting**: Respect Jira API limits
- **Data Mapping**: Issues → Statuses → Status Mappings → Flow Steps
- **Cancellation**: Graceful termination during long-running operations

### **Git Data Processing**
- **Repository Management**: Multiple repos per integration
- **Pull Request Analysis**: Reviews, commits, comments
- **Metrics Calculation**: DORA metrics, engineering analytics
- **Data Relationships**: Proper FK constraints, avoid duplication

### **Data Quality Patterns**
```python
# Case-insensitive string comparisons
status_name.lower() == mapped_status.lower()

# Exclude deactivated records from metrics
WHERE flow_step.active = true 
  AND status_mapping.active = true
  AND issue.active = true
```

## 🔗 Integration Management

### **External API Patterns**
- **Authentication**: Store encrypted credentials
- **Connection Testing**: Validate before saving
- **Error Handling**: Graceful degradation, retry logic
- **Rate Limiting**: Respect external API limits

### **Integration Types**
```python
# Jira Integration
{
    "type": "jira",
    "base_url": "https://company.atlassian.net",
    "username": "user@company.com",
    "api_token": "encrypted_token"
}

# Git Integration  
{
    "type": "github",
    "base_url": "https://api.github.com",
    "token": "encrypted_token",
    "repositories": ["org/repo1", "org/repo2"]
}
```

## 📈 Dashboard & Analytics

### **Real-time Updates**
- **WebSocket Communication**: Live job status updates
- **Auto-refresh**: Configurable intervals (30s, 1m, 5m)
- **State Synchronization**: Keep UI in sync with backend state

### **Metrics Calculation**
- **DORA Metrics**: Deployment frequency, lead time, MTTR, change failure rate
- **Engineering Analytics**: PR analysis, code review metrics
- **Exclusion Logic**: Deactivated records excluded at ALL levels

### **Dashboard Patterns**
```javascript
// WebSocket message handling
websocket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    updateJobStatus(data.job_type, data.status);
    updateProgress(data.progress);
};

// Auto-refresh configuration
const refreshTimer = setInterval(() => {
    refreshData();
    refreshSystemHealth();
}, interval);
```

## 🌐 WebSocket Management

### **Connection Patterns**
- **Auto-reconnect**: Handle connection drops gracefully
- **Message Types**: job_status, progress_update, system_health
- **Error Handling**: Fallback to polling if WebSocket fails

### **Real-time Features**
```javascript
// Job status updates
{
    "type": "job_status",
    "job_type": "jira_sync",
    "status": "RUNNING",
    "progress": 45
}

// System health updates
{
    "type": "system_health",
    "database": "healthy",
    "integrations": "warning"
}
```

## ⚙️ Workflow Management

### **Workflow Architecture**
- **Workflow Steps**: Define workflow stages (To Do, In Progress, Done, Discarded)
- **Commitment Points**: Mark the initial commitment point for lead time calculation (Kanban principles)
- **Integration Assignment**: Associate workflows with specific integrations or apply globally
- **Status Mappings**: Map Jira statuses to workflow steps
- **Issue Type Mappings**: Different workflows for different issue types

### **Commitment Point Validation**
- Only one commitment point allowed per client/integration combination
- Validation occurs at both frontend and backend levels
- Clear error messages guide users to resolve conflicts

### **Dependency Management**
```python
# Deletion with reassignment
def delete_flow_step(step_id, reassign_to_id):
    # Show impact warning first
    affected_count = count_affected_issues(step_id)
    
    # Reassign dependent mappings
    reassign_status_mappings(step_id, reassign_to_id)
    
    # Then delete the flow step
    delete_step(step_id)
```

### **Validation Patterns**
- **Circular Dependencies**: Prevent invalid flow configurations
- **Required Mappings**: Ensure all statuses are mapped
- **Data Integrity**: Validate before allowing changes

## 🔐 Authentication Integration

### **Centralized Auth Usage**
```python
# Token validation via Backend Service
from app.auth.centralized_auth_service import get_centralized_auth_service

auth_service = get_centralized_auth_service()
user_data = await auth_service.verify_token(token)
```

### **Middleware Patterns**
- **Web Routes**: Redirect to login if not authenticated
- **API Routes**: Return 401 for invalid tokens
- **Admin Routes**: Require admin role for sensitive operations

### **Cross-Service Navigation**
```python
# Navigation endpoint for frontend → ETL authentication
@router.post("/auth/navigate")
async def navigate_with_token(request: Request):
    """Handle navigation from frontend with token authentication."""
    data = await request.json()
    token = data.get("token")
    return_url = data.get("return_url")

    # Validate token via Backend Service
    auth_service = get_centralized_auth_service()
    user_data = await auth_service.verify_token(token)

    if user_data:
        # Create session cookie and redirect
        response = RedirectResponse(url="/home", status_code=302)
        response.set_cookie(
            key="pulse_token",
            value=token,
            max_age=3600,
            httponly=True,
            path="/"
        )
        # Store return URL for pulse navigation
        if return_url:
            response.set_cookie(key="return_url", value=return_url, max_age=3600)
        return response
```

### **Session Management**
- **No Local Sessions**: ETL Service doesn't manage sessions
- **Token Validation**: Always validate via Backend Service
- **Logout Handling**: Call Backend Service for session invalidation

## 📝 Configuration Management

### **Settings Structure**
```python
class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # External Services
    BACKEND_SERVICE_URL: str
    
    # Job Configuration
    SCHEDULER_TIMEZONE: str = "UTC"
    
    # Security
    SECRET_KEY: str
    ENCRYPTION_KEY: str
```

### **Environment Variables**
- **Required**: DATABASE_URL, BACKEND_SERVICE_URL
- **Optional**: DEBUG, LOG_LEVEL, SCHEDULER_TIMEZONE
- **Security**: SECRET_KEY, ENCRYPTION_KEY for data encryption

## 🚨 Common Patterns & Pitfalls

### **Job Management**
- ✅ **Do** check cancellation flags during long operations
- ✅ **Do** maintain job state consistency
- ❌ **Don't** change PAUSED jobs to FINISHED automatically
- ❌ **Don't** allow multiple jobs to run simultaneously

### **Data Processing**
- ✅ **Do** use case-insensitive string comparisons
- ✅ **Do** exclude deactivated records from metrics
- ❌ **Don't** create circular dependencies in flow mappings
- ❌ **Don't** process data without proper validation

### **Authentication**
- ✅ **Do** validate tokens via Backend Service
- ✅ **Do** handle authentication errors gracefully
- ✅ **Do** support bidirectional authentication (ETL → Frontend navigation)
- ✅ **Do** use postMessage for cross-service communication
- ✅ **Do** handle 302 redirects as successful logout responses
- ❌ **Don't** implement local authentication logic
- ❌ **Don't** bypass centralized auth system
- ❌ **Don't** make direct Frontend-ETL API calls (use Backend Service)
- ❌ **Don't** pass tokens in URLs (use POST with proper headers)

### **Real-time Features**
- ✅ **Do** implement WebSocket reconnection logic
- ✅ **Do** provide fallback to polling
- ❌ **Don't** rely solely on WebSocket for critical updates
- ❌ **Don't** ignore connection state changes
