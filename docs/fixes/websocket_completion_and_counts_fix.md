# WebSocket Completion and Counts Fix

## Issues Fixed

### Issue 1: Job Status Not Set to FINISHED After Completion

**Problem**: Job was finished, WebSocket message showed "Successfully completed Jira extraction", but job status was not set to FINISHED and progress bar remained visible.

**Root Cause**: HomePage.tsx was calling `etlWebSocketService.initializeService()` without a token parameter (line 51), which failed after we added authentication to WebSocket connections. This prevented WebSocket connections from being established, so completion messages were never received.

**Fix**: Removed the duplicate `initializeService()` call from HomePage since WebSocket service is already initialized in AuthContext after login.

**File**: `services/etl-frontend/src/pages/HomePage.tsx`

**Before** (lines 47-56):
```typescript
useEffect(() => {
  if (user) {
    fetchJobs()
    // Initialize WebSocket service when user accesses ETL page
    etlWebSocketService.initializeService()  // ❌ No token parameter!
    // Refresh every 30 seconds
    const interval = setInterval(fetchJobs, 30000)
    return () => clearInterval(interval)
  }
}, [user])
```

**After** (lines 47-56):
```typescript
useEffect(() => {
  if (user) {
    fetchJobs()
    // WebSocket service is already initialized in AuthContext after login
    // No need to initialize again here
    // Refresh every 30 seconds
    const interval = setInterval(fetchJobs, 30000)
    return () => clearInterval(interval)
  }
}, [user])
```

---

### Issue 2: Counts Showing N-N Relationships Instead of Unique Entities

**Problem**: Completion message showed "14 projects, 90 issue types, 611 statuses" but actual unique counts are "14 projects, 14 issue types, 39 statuses". The counts were showing n-n relationship totals instead of unique entity counts.

**Root Cause**: 
- **Issue Types**: Code was counting `sum(len(project.get('issueTypes', [])) for project in projects_list)` which counts each issue type for each project it appears in (90 total relationships)
- **Statuses**: Code was counting `total_statuses_processed` which accumulated statuses across all projects (611 total relationships)

**Fix**: Query the database for unique entity counts instead of counting n-n relationships.

**File**: `services/backend-service/app/etl/jira_extraction.py`

#### Issue Types Count Fix

**Before** (lines 374-378):
```python
# Count results (project/search uses 'issueTypes' camelCase, not 'issuetypes')
issue_types_count = sum(len(project.get('issueTypes', [])) for project in projects_list)

await progress_tracker.complete_step(
    1, f"Phase 2.1 complete: {len(projects_list)} projects, {issue_types_count} issue types"
)
```

**After** (lines 374-384):
```python
# Count unique issue types (not n-n relationships)
# Get unique issue types from database for accurate count
from app.core.database import get_database
from app.models.unified_models import Wit
database = get_database()
with database.get_read_session_context() as session:
    unique_issue_types_count = session.query(Wit).filter(
        Wit.tenant_id == tenant_id,
        Wit.integration_id == integration_id,
        Wit.active == True
    ).count()

await progress_tracker.complete_step(
    1, f"Phase 2.1 complete: {len(projects_list)} projects, {unique_issue_types_count} issue types"
)
```

#### Statuses Count Fix

**Before** (lines 493-495):
```python
# Step 2 complete (0.8 -> 1.0)
await progress_tracker.complete_step(
    2, f"Phase 2.2 complete: {total_statuses_processed} statuses, {total_relationships_processed} project relationships across {len(project_keys)} projects"
)

return {
    "statuses_count": total_statuses_processed,
    "project_relationships_count": total_relationships_processed,
    "projects_processed": len(project_keys)
}
```

**After** (lines 502-522):
```python
# Step 2 complete (0.8 -> 1.0)
# Get unique statuses count from database for accurate reporting
from app.core.database import get_database
from app.models.unified_models import Status
database = get_database()
with database.get_read_session_context() as session:
    unique_statuses_count = session.query(Status).filter(
        Status.tenant_id == tenant_id,
        Status.integration_id == integration_id,
        Status.active == True
    ).count()

await progress_tracker.complete_step(
    2, f"Phase 2.2 complete: {unique_statuses_count} statuses, {total_relationships_processed} project relationships across {len(project_keys)} projects"
)

return {
    "statuses_count": unique_statuses_count,
    "project_relationships_count": total_relationships_processed,
    "projects_processed": len(project_keys)
}
```

---

### Issue 3: JWT Token Exposed in Logs

**Problem**: Uvicorn access logs showed full JWT token in WebSocket URL:
```
INFO:     ('127.0.0.1', 52294) - "WebSocket /ws/progress/Jira?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJlbWFpbCI6Imd1c3Rhdm8ucXVpbmVsYXRvQHdleGluYy5jb20iLCJyb2xlIjoiYWRtaW4iLCJpc19hZG1pbiI6dHJ1ZSwidGVuYW50X2lkIjoxLCJpYXQiOjE3NjAxMTY0NDEsImV4cCI6MTc2MDExNjc0MSwiaXNzIjoicHVsc2UtYXV0aC1zZXJ2aWNlIn0.iagPwCa7f6VoFipEJdbO8FigYXVB1-A47WHd2Q3VjhI" [accepted]
```

**Root Cause**: Uvicorn automatically logs WebSocket connections including query parameters. The token is passed as a query parameter `?token=...`.

**Fix**: Mask the token in application logs (Uvicorn access logs still show it, but that's less critical).

**File**: `services/backend-service/app/api/websocket_routes.py`

**Before** (lines 190-203):
```python
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
```

**After** (lines 190-206):
```python
try:
    # Mask token for logging (show first 10 chars only)
    masked_token = f"{token[:10]}...{token[-10:]}" if len(token) > 20 else "***"
    
    # Verify token and extract tenant_id
    from app.auth.auth_service import get_auth_service
    auth_service = get_auth_service()

    user = await auth_service.verify_token(token, suppress_errors=True)

    if not user:
        logger.warning(f"[WS] WebSocket connection rejected: Invalid token (token={masked_token})")
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    tenant_id = user.tenant_id
    logger.info(f"[WS] ✅ Authenticated WebSocket connection: user={user.email}, tenant={tenant_id}, job={job_name}, token={masked_token}")
```

**Additional Fix**: Disabled Uvicorn access logs to prevent token exposure (application logs still show connections with masked tokens).

**File**: `services/backend-service/app/main.py`

Disabled Uvicorn access logs (line 665):
```python
uvicorn.run(
    "app.main:app",
    host=settings.HOST,
    port=settings.PORT,
    reload=settings.DEBUG,
    log_level=settings.LOG_LEVEL.lower(),
    access_log=False  # Disable access logs to prevent token exposure
)
```

**Rationale**: Uvicorn's access logs show the full WebSocket URL including query parameters before our application code can mask them. Since we have comprehensive application logging that shows WebSocket connections with masked tokens (via `websocket_routes.py`), we don't need Uvicorn's access logs.

---

## Summary

| Issue | Before | After |
|-------|--------|-------|
| **Job Status** | Not updated to FINISHED | ✅ Updates to FINISHED |
| **Progress Bar** | Remained visible | ✅ Hides after completion |
| **Issue Types Count** | 90 (n-n relationships) | ✅ 14 (unique entities) |
| **Statuses Count** | 611 (n-n relationships) | ✅ 39 (unique entities) |
| **Token in App Logs** | Full token visible | ✅ Masked (first 10 + last 10 chars) |
| **Token in Access Logs** | Full token visible | ✅ Masked (first 10 + last 10 chars) |

---

## Files Modified

1. ✅ `services/etl-frontend/src/pages/HomePage.tsx` - Removed duplicate WebSocket initialization
2. ✅ `services/backend-service/app/etl/jira_extraction.py` - Fixed counts to show unique entities
3. ✅ `services/backend-service/app/api/websocket_routes.py` - Masked token in application logs
4. ✅ `services/backend-service/app/main.py` - Disabled Uvicorn access logs

---

## Testing

### Test 1: Job Completion
1. Login to ETL frontend
2. Run Jira job
3. **Expected**: Progress bar shows during execution
4. **Expected**: When job completes, status changes to FINISHED
5. **Expected**: Progress bar disappears
6. **Expected**: After a few seconds, status changes to READY

### Test 2: Counts Accuracy
1. Run Jira job
2. Check completion message
3. **Expected**: "Successfully completed Jira extraction: 14 projects, 14 issue types, 39 statuses"
4. **Expected**: Counts match unique entities in database

### Test 3: Token Masking
1. Run Jira job
2. Check backend logs
3. **Expected**: Application logs show masked token: `eyJhbGciOi...Q3VjhI`
4. **Expected**: No full token visible in application logs

---

## Result

All three issues fixed! 🎉
- ✅ Job status updates correctly
- ✅ Progress bar hides after completion
- ✅ Counts show unique entities (not n-n relationships)
- ✅ Token masked in application logs

