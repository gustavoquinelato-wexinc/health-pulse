# HTTP Client Shutdown Fix

## Problem

The application was experiencing "Event loop is closed" errors during shutdown:

```
2025-10-17 14:18:24 - asyncio - ERROR - Task exception was never retrieved
future: <Task finished name='Task-204' coro=<AsyncClient.aclose() done, defined at ...> exception=RuntimeError('Event loop is closed')>
Traceback (most recent call last):
  File "C:\Users\...\httpx\_client.py", line 1974, in aclose
    await self._transport.aclose()
  ...
RuntimeError: Event loop is closed
```

## Root Cause

The issue was caused by global `httpx.AsyncClient` instances in the shared HTTP client modules that were not being properly closed during application shutdown. When the FastAPI application shuts down:

1. The event loop begins closing
2. Global HTTP clients try to clean up their connections
3. Cleanup tasks are scheduled on the already-closed event loop
4. This causes "Event loop is closed" errors

## Solution

### 1. Added cleanup functions to HTTP client modules

**Backend Service** (`services/backend-service/app/core/http_client.py`):
```python
async def cleanup_async_client():
    """
    Cleanup the global async HTTP client to prevent event loop errors during shutdown.
    """
    global _client
    if _client is not None:
        try:
            await _client.aclose()
            logger.debug("Global HTTP client cleaned up successfully")
        except Exception as e:
            # Suppress cleanup errors to avoid noise in logs during shutdown
            logger.debug(f"Error during HTTP client cleanup (suppressed): {e}")
        finally:
            _client = None
```

**ETL Service** (`services/etl-service/app/core/http_client.py`):
- Added identical cleanup function

### 2. Integrated cleanup into application shutdown

**Backend Service** (`services/backend-service/app/main.py`):
```python
# In the lifespan finally block
# Close HTTP client connections
try:
    print("[INFO] Closing HTTP client connections...")
    from app.core.http_client import cleanup_async_client
    await cleanup_async_client()
    print("[INFO] HTTP client connections closed")
except Exception as e:
    print(f"[WARNING] Error closing HTTP client connections: {e}")
```

**ETL Service** (`services/etl-service/app/main.py`):
- Added identical cleanup in lifespan finally block

### 3. Added synchronous wrapper for non-async contexts

```python
def cleanup_async_client_sync():
    """
    Synchronous wrapper for cleanup_async_client for use in non-async contexts.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, schedule cleanup as a task
            asyncio.create_task(cleanup_async_client())
        else:
            # If loop is not running, run cleanup directly
            loop.run_until_complete(cleanup_async_client())
    except RuntimeError:
        # Event loop is closed or not available, skip cleanup
        global _client
        _client = None
```

## Files Modified

1. `services/backend-service/app/core/http_client.py` - Added cleanup functions
2. `services/backend-service/app/main.py` - Added cleanup to shutdown process
3. `services/etl-service/app/core/http_client.py` - Added cleanup functions
4. `services/etl-service/app/main.py` - Added cleanup to shutdown process

## Testing

After this fix:
1. Start the backend service: `cd services/backend-service && python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload`
2. Stop the service with Ctrl+C or kill the process
3. Verify no "Event loop is closed" errors appear in logs
4. Verify the shutdown process shows "HTTP client connections closed" message

## Notes

- The cleanup functions suppress errors to avoid noise during shutdown
- Other HTTP client usage in the codebase uses `async with httpx.AsyncClient()` pattern which automatically handles cleanup
- This fix specifically addresses the global shared HTTP clients that persist for the application lifetime
