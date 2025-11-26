# Worker Status Check Before Job Execution

## Overview

This document describes the worker status check mechanism that prevents ETL jobs from being queued when workers are not running.

## Problem Statement

Previously, when users stopped all workers via the Queue Management page and then triggered a job (manually or automatically), the job would:
1. Change status to RUNNING
2. Queue messages to the extraction queue
3. Messages would sit in the queue indefinitely (no workers to process them)
4. Job would appear stuck in RUNNING state
5. User would have no clear indication of what went wrong

## Solution

Added a worker status check **before** queuing any extraction job. If workers are not running:
1. Job is immediately marked as FAILED
2. Clear error message is set: "No workers are currently running. Please start workers from the Queue Management page before running jobs."
3. No messages are queued to RabbitMQ
4. User sees immediate feedback in the UI

## Implementation

### 1. Worker Status Check Function

Added `_check_workers_running()` function in both:
- `services/backend-service/app/etl/jobs.py` (for manual job triggers)
- `services/backend-service/app/etl/job_scheduler.py` (for automatic job triggers)

```python
def _check_workers_running() -> tuple[bool, str]:
    """
    Check if extraction workers are currently running.
    
    Returns:
        tuple: (workers_running: bool, message: str)
    """
    try:
        from app.etl.workers.worker_manager import get_worker_manager
        
        manager = get_worker_manager()
        status = manager.get_worker_status()
        
        workers_running = status.get('running', False)
        
        if not workers_running:
            message = "No workers are currently running. Please start workers from the Queue Management page before running jobs."
            logger.warning(f"⚠️ Worker check failed: {message}")
            return False, message
        
        logger.info(f"✅ Worker check passed: Workers are running")
        return True, "Workers are running"
        
    except Exception as e:
        logger.error(f"❌ Error checking worker status: {e}")
        # If we can't check status, assume workers are running to avoid blocking jobs
        return True, "Worker status check failed - proceeding anyway"
```

### 2. Integration Points

The worker check is integrated at the beginning of:

1. **`_queue_jira_extraction_job()`** in `jobs.py` (line ~940)
   - Called when user clicks "Run Now" on a Jira job
   
2. **`_queue_github_extraction_job()`** in `jobs.py` (line ~1070)
   - Called when user clicks "Run Now" on a GitHub job
   
3. **`_queue_jira_extraction()`** in `job_scheduler.py` (line ~650)
   - Called when automatic job scheduler triggers a Jira job

### 3. Failure Handling

When workers are not running, the job is marked as FAILED and an HTTPException is raised:

```python
# Update job status to FAILED with proper error message
database = get_database()
with database.get_write_session_context() as session:
    from app.core.utils import DateTimeHelper
    import json
    now = DateTimeHelper.now_default()

    # Create the status JSON with error message
    status_update = json.dumps({
        'overall': 'FAILED',
        'error': worker_message
    })

    # Use CAST() instead of :: to avoid syntax conflicts with named parameters
    update_query = text("""
        UPDATE etl_jobs
        SET status = status || CAST(:status_update AS jsonb),
            last_updated_at = :now
        WHERE id = :job_id AND tenant_id = :tenant_id
    """)

    session.execute(update_query, {
        'job_id': job_id,
        'tenant_id': tenant_id,
        'status_update': status_update,
        'now': now
    })
    session.commit()

# Send WebSocket update to notify UI
try:
    from app.api.websocket_routes import send_status_update
    await send_status_update(
        tenant_id=tenant_id,
        job_id=job_id,
        step_name='overall',
        status='failed',
        error=worker_message
    )
except Exception as ws_error:
    logger.warning(f"Failed to send WebSocket update: {ws_error}")

# Raise HTTPException with clear error message
raise HTTPException(status_code=400, detail=worker_message)
```

This approach ensures:
1. Database is updated with FAILED status and error message
2. WebSocket notification is sent to update the UI in real-time
3. HTTPException is raised with the clear error message (not generic "Failed to queue extraction job")
4. The error message is shown to the user in the alert

## User Experience

### Before
1. User stops all workers
2. User clicks "Run Now" on a job
3. Job shows "RUNNING" status
4. Nothing happens (messages queued but no workers to process)
5. Job appears stuck
6. User confused about what's wrong

### After
1. User stops all workers
2. User clicks "Run Now" on a job
3. Job immediately shows "FAILED" status
4. Error message: "No workers are currently running. Please start workers from the Queue Management page before running jobs."
5. User knows exactly what to do

## Testing

A test script is provided at `services/backend-service/test_worker_check.py`:

```bash
cd services/backend-service
python test_worker_check.py
```

This will:
- Check current worker status
- Display whether workers are running or stopped
- Show worker details if running
- Exit with code 0 if workers running, 1 if stopped

## Edge Cases

### 1. Worker Status Check Fails
If the worker status check itself fails (exception), the system assumes workers are running and proceeds with queuing. This prevents a broken status check from blocking all jobs.

### 2. Workers Stop After Check
If workers are running during the check but stop immediately after, the message will be queued and processed when workers restart. This is acceptable as it's a race condition.

### 3. Automatic Jobs
Automatic jobs (triggered by scheduler) also perform the worker check. If workers are stopped, the job is marked as FAILED and will retry on the next schedule interval.

## Related Files

- `services/backend-service/app/etl/jobs.py` - Manual job triggers
- `services/backend-service/app/etl/job_scheduler.py` - Automatic job triggers
- `services/backend-service/app/etl/workers/worker_manager.py` - Worker status management
- `services/backend-service/test_worker_check.py` - Test script

