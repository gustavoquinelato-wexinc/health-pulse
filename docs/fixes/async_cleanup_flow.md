# Async Cleanup Flow Diagram

## Before Fix (Problematic Flow)

```
VectorizationWorker.process_message()
│
├─> _generate_embedding()
│   │
│   ├─> Create HybridProviderManager(session)
│   │   └─> Creates WEXGatewayProvider
│   │       └─> Creates AsyncOpenAI client (httpx.AsyncClient internally)
│   │
│   ├─> asyncio.run(initialize_providers())
│   │   └─> Creates event loop → runs → CLOSES event loop
│   │
│   ├─> asyncio.run(generate_embeddings())
│   │   └─> Creates event loop → runs → CLOSES event loop
│   │       └─> AsyncOpenAI client schedules cleanup tasks
│   │           └─> ❌ ERROR: Event loop already closed!
│   │
│   └─> Return embedding
│
└─> Continue processing...
```

**Problem**: AsyncOpenAI client tries to cleanup after event loop is closed.

---

## After Fix (Correct Flow)

```
VectorizationWorker.process_message()
│
├─> _generate_embedding()
│   │
│   ├─> Create HybridProviderManager(session)
│   │   └─> Creates WEXGatewayProvider
│   │       └─> Creates AsyncOpenAI client (httpx.AsyncClient internally)
│   │
│   ├─> asyncio.run(generate_with_cleanup())
│   │   │
│   │   └─> Creates event loop
│   │       │
│   │       ├─> try:
│   │       │   ├─> await initialize_providers()
│   │       │   └─> await generate_embeddings()
│   │       │
│   │       ├─> finally:
│   │       │   └─> await hybrid_provider.cleanup()
│   │       │       └─> await wex_provider.cleanup()
│   │       │           └─> await client.close()
│   │       │               └─> ✅ Properly closes httpx connections
│   │       │
│   │       └─> CLOSES event loop (all resources already cleaned up)
│   │
│   └─> Return embedding
│
└─> Continue processing...
```

**Solution**: All async operations in single event loop context with proper cleanup before loop closes.

---

## Key Differences

### Before Fix
- ❌ Multiple `asyncio.run()` calls creating/destroying event loops
- ❌ AsyncOpenAI client not explicitly closed
- ❌ Cleanup tasks scheduled on closed event loop
- ❌ "Event loop is closed" errors in logs

### After Fix
- ✅ Single `asyncio.run()` call per operation
- ✅ AsyncOpenAI client explicitly closed in finally block
- ✅ All cleanup happens before event loop closes
- ✅ Clean logs with no errors

---

## Cleanup Chain

```
VectorizationWorker
    └─> calls cleanup on
        HybridProviderManager
            └─> calls cleanup on each provider
                ├─> WEXGatewayProvider.cleanup()
                │   └─> await client.close()
                │       └─> Closes httpx.AsyncClient
                │           └─> Closes HTTP connections
                │
                └─> SentenceTransformersProvider.cleanup()
                    └─> Shuts down ThreadPoolExecutor
                    └─> Releases model from memory
```

---

## Pattern Applied

### General Pattern for Async Resource Management

```python
# ❌ WRONG - Multiple event loops
def sync_function():
    resource = AsyncResource()
    asyncio.run(resource.initialize())
    result = asyncio.run(resource.do_work())
    # Resource cleanup happens after event loop closes - ERROR!
    return result

# ✅ CORRECT - Single event loop with cleanup
def sync_function():
    async def work_with_cleanup():
        resource = AsyncResource()
        try:
            await resource.initialize()
            result = await resource.do_work()
            return result
        finally:
            await resource.cleanup()  # Cleanup before loop closes
    
    return asyncio.run(work_with_cleanup())
```

### Applied to VectorizationWorker

```python
# ✅ CORRECT - Applied pattern
def _generate_embedding(self, tenant_id, entity_data, table_name):
    async def generate_with_cleanup():
        hybrid_provider = HybridProviderManager(session)
        try:
            await hybrid_provider.initialize_providers(tenant_id)
            response = await hybrid_provider.generate_embeddings(...)
            return response.data[0]
        finally:
            await hybrid_provider.cleanup()
    
    return asyncio.run(generate_with_cleanup())
```

---

## Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| Event Loop Management | Multiple loops created/destroyed | Single loop per operation |
| Resource Cleanup | Implicit (fails) | Explicit (succeeds) |
| Error Logs | "Event loop is closed" errors | Clean logs |
| Memory Management | Potential leaks | Proper cleanup |
| HTTP Connections | May remain open | Properly closed |
| Code Pattern | Anti-pattern | Best practice |

---

## Testing Checklist

- [x] No "Event loop is closed" errors in logs
- [x] No "Task exception was never retrieved" errors
- [x] Embeddings still generated correctly
- [x] Qdrant storage still works
- [x] Worker processes messages successfully
- [x] No memory leaks over time
- [x] HTTP connections properly closed

