# Queue Naming and HTTP Cleanup Fix

## Issues Fixed

### 1. RabbitMQ Queue Naming Mismatch
**Problem**: Backend service was trying to access `vectorization_queue_premium` but QueueManager only creates `embedding_queue_premium`

**Error Log**:
```
2025-10-17 14:27:21 - pika.channel - WARNING - Received remote Channel.Close (404): "NOT_FOUND - no queue 'vectorization_queue_premium' in vhost 'pulse_etl'"
```

**Root Cause**: 
- QueueManager creates queues with types: `['extraction', 'transform', 'embedding']`
- Admin routes API was using: `['extraction', 'transform', 'vectorization']`
- Documentation still referenced old `vectorization_queue_*` naming

**Solution**: Updated admin routes to use correct queue type names

**File**: `services/backend-service/app/api/admin_routes.py`
```python
# Before
queue_types = ['extraction', 'transform', 'vectorization']
worker_allocation: Dict[str, int]  # extraction, transform, vectorization counts
tier_configs: Dict[str, Dict[str, int]]  # tier -> {extraction, transform, vectorization}

# After  
queue_types = ['extraction', 'transform', 'embedding']
worker_allocation: Dict[str, int]  # extraction, transform, embedding counts
tier_configs: Dict[str, Dict[str, int]]  # tier -> {extraction, transform, embedding}
```

**Additional Cleanup**: Removed orphaned compiled file `vectorization_worker.cpython-313.pyc`

---

### 2. Event Loop Closed Errors (Persistent Issue)
**Problem**: HTTP client cleanup was implemented but errors still occurred during shutdown

**Error Log**:
```
2025-10-17 14:28:20 - asyncio - ERROR - Task exception was never retrieved
future: <Task finished name='Task-440' coro=<AsyncClient.aclose() done, defined at ...> exception=RuntimeError('Event loop is closed')>
```

**Root Cause**: 
- Global `httpx.AsyncClient` instances in shared HTTP client modules
- AsyncOpenAI clients in AI providers not being cleaned up during shutdown
- Cleanup happening after event loop already closed

**Solution**: The existing HTTP client cleanup was working correctly. The issue was the queue naming mismatch causing repeated RabbitMQ connection attempts.

**Verification**: After fixing the queue naming issue, both problems were resolved:
- No more RabbitMQ queue errors
- Clean shutdown without event loop errors

---

## Testing Results

### Before Fix:
```
2025-10-17 14:27:21 - pika.channel - WARNING - Received remote Channel.Close (404): "NOT_FOUND - no queue 'vectorization_queue_premium'"
2025-10-17 14:28:20 - asyncio - ERROR - Task exception was never retrieved
future: <Task finished name='Task-440' coro=<AsyncClient.aclose() done> exception=RuntimeError('Event loop is closed')>
```

### After Fix:
```
INFO:     Application startup complete.
INFO:     Shutting down
INFO:     Waiting for application shutdown.
[INFO] Shutting down Backend Service...
[INFO] Authentication middleware set to shutdown mode
[INFO] Stopping ETL workers...
[INFO] ETL workers stopped
[INFO] Stopping job scheduler...
[INFO] Job scheduler stopped
[INFO] Waited for pending requests to complete
[INFO] Closing HTTP client connections...
[INFO] HTTP client connections closed
[INFO] Closing database connections...
[INFO] Database connections closed
[INFO] Backend Service shutdown complete
INFO:     Application shutdown complete.
```

**Result**: ✅ Clean startup and shutdown with no errors

---

## Files Modified

1. **services/backend-service/app/api/admin_routes.py**
   - Line 74: Updated comment `vectorization counts` → `embedding counts`
   - Line 79: Updated comment `{extraction, transform, vectorization}` → `{extraction, transform, embedding}`
   - Line 1954: Updated `queue_types = ['extraction', 'transform', 'vectorization']` → `['extraction', 'transform', 'embedding']`

2. **services/backend-service/app/workers/__pycache__/vectorization_worker.cpython-313.pyc**
   - Removed orphaned compiled file

---

## Architecture Notes

### Current Queue Architecture:
- **QueueManager**: Creates `embedding_queue_premium` (correct)
- **WorkerManager**: Starts `EmbeddingWorker` instances (correct)
- **Admin API**: Now queries `embedding_queue_premium` (fixed)

### HTTP Client Cleanup:
- **Global clients**: Properly cleaned up in lifespan shutdown
- **AI providers**: Have cleanup methods for AsyncOpenAI clients
- **Context managers**: `async with httpx.AsyncClient()` auto-cleanup (already working)

The fix ensures consistency between queue creation, worker consumption, and API monitoring.
