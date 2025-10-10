# Async Client Cleanup Fix

## Problem

When the VectorizationWorker started, it would produce errors like:

```
2025-10-09 23:27:16 - asyncio - ERROR - Task exception was never retrieved
future: <Task finished name='Task-128' coro=<AsyncClient.aclose() done, defined at ...> exception=RuntimeError('Event loop is closed')>
Traceback (most recent call last):
  ...
  File "...\asyncio\base_events.py", line 556, in _check_closed
    raise RuntimeError('Event loop is closed')
RuntimeError: Event loop is closed
```

## Root Cause

The issue occurred because:

1. **VectorizationWorker** uses `asyncio.run()` to execute async operations in a synchronous context
2. Each `asyncio.run()` call creates a new event loop, runs the coroutine, and **closes the event loop**
3. **WEXGatewayProvider** creates an `AsyncOpenAI` client in `__init__()` which internally uses `httpx.AsyncClient`
4. When the event loop closes, the `AsyncOpenAI` client tries to clean up its HTTP connections
5. However, the cleanup tasks are scheduled on the already-closed event loop, causing the error

The error was harmless (just cleanup tasks failing) but created noise in the logs and indicated improper resource management.

## Solution

Implemented proper async resource cleanup using the following pattern:

### 1. Added cleanup methods to providers

**WEXGatewayProvider** (`services/backend-service/app/ai/providers/wex_gateway_provider.py`):
```python
async def cleanup(self):
    """Cleanup async resources to prevent event loop errors"""
    try:
        if self.client:
            await self.client.close()
            logger.debug("WEX Gateway provider cleaned up")
    except Exception as e:
        logger.warning(f"Error during WEX Gateway cleanup: {e}")
```

**SentenceTransformersProvider** already had a cleanup method.

### 2. Added cleanup to HybridProviderManager

**HybridProviderManager** (`services/backend-service/app/ai/hybrid_provider_manager.py`):
```python
async def cleanup(self):
    """Cleanup all provider resources to prevent event loop errors"""
    try:
        for provider_key, provider in self.providers.items():
            if hasattr(provider, 'cleanup'):
                try:
                    await provider.cleanup()
                except Exception as e:
                    logger.warning(f"Error cleaning up provider {provider_key}: {e}")
        logger.debug("HybridProviderManager cleaned up all providers")
    except Exception as e:
        logger.warning(f"Error during HybridProviderManager cleanup: {e}")
```

### 3. Updated VectorizationWorker to use cleanup

**VectorizationWorker** (`services/backend-service/app/workers/vectorization_worker.py`):

Changed from:
```python
# Initialize providers
init_success = asyncio.run(hybrid_provider.initialize_providers(tenant_id))
# Generate embeddings
response = asyncio.run(hybrid_provider.generate_embeddings(...))
```

To:
```python
# Use a single async context to initialize, generate, and cleanup
async def generate_with_cleanup():
    try:
        # Initialize providers
        init_success = await hybrid_provider.initialize_providers(tenant_id)
        # Generate embeddings
        response = await hybrid_provider.generate_embeddings(...)
        return embedding
    finally:
        # Cleanup providers before event loop closes
        await hybrid_provider.cleanup()

# Run the async function with proper cleanup
return asyncio.run(generate_with_cleanup())
```

### 4. Updated API endpoints

**bulk_vector_operations** endpoint (`services/backend-service/app/api/ai_config_routes.py`):
```python
try:
    # ... vector operations ...
    return result
finally:
    # Cleanup AI providers to prevent event loop errors
    await hybrid_manager.cleanup()
```

## Key Principles

1. **Always cleanup async resources** before the event loop closes
2. **Use try/finally blocks** to ensure cleanup happens even on errors
3. **Consolidate async operations** into a single `asyncio.run()` call when possible
4. **Implement cleanup methods** for all classes that manage async resources

## Benefits

- ✅ Eliminates "Event loop is closed" errors in logs
- ✅ Proper resource management and cleanup
- ✅ Prevents potential memory leaks from unclosed connections
- ✅ Cleaner logs without error noise
- ✅ Better async/await patterns

## Files Modified

1. `services/backend-service/app/ai/providers/wex_gateway_provider.py` - Added cleanup method
2. `services/backend-service/app/ai/hybrid_provider_manager.py` - Added cleanup method
3. `services/backend-service/app/workers/vectorization_worker.py` - Updated to use cleanup pattern
4. `services/backend-service/app/api/ai_config_routes.py` - Added cleanup to bulk operations endpoint

## Testing

After this fix:
1. Start the VectorizationWorker
2. Process vectorization messages
3. Verify no "Event loop is closed" errors appear in logs
4. Verify embeddings are still generated correctly
5. Verify Qdrant storage still works correctly

