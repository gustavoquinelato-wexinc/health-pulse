# ETL Service Guide

This guide covers ETL Service specific functionality, patterns, and best practices.

## 🔄 Job Orchestration

### **Job Management Architecture**
- **Main Orchestrator**: Runs every 60 minutes, manages both jobs
- **Job States**: PENDING, RUNNING, FINISHED, FAILED, PAUSED
- **Recovery Logic**: Retry failed jobs with configurable intervals
- **Force Stop**: Instant termination with proper cleanup

### **Job State Transitions**
```
PENDING → RUNNING → FINISHED/FAILED
RUNNING → PAUSED (manual pause)
PAUSED → RUNNING (manual resume)
FAILED → PENDING (retry logic)
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

## ⚙️ Flow Management

### **Status Mapping Architecture**
- **Flow Steps**: Define workflow stages (To Do, In Progress, Done)
- **Status Mappings**: Map Jira statuses to flow steps
- **Issue Type Mappings**: Different flows for different issue types

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
- ❌ **Don't** implement local authentication logic
- ❌ **Don't** bypass centralized auth system

### **Real-time Features**
- ✅ **Do** implement WebSocket reconnection logic
- ✅ **Do** provide fallback to polling
- ❌ **Don't** rely solely on WebSocket for critical updates
- ❌ **Don't** ignore connection state changes
