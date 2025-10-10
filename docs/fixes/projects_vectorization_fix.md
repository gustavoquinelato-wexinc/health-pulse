# Projects Vectorization Fix

## Issue

**Problem**: All 14 projects were being queued for vectorization but were NOT being stored in Qdrant or the `qdrant_vectors` bridge table.

**Symptoms**:
- TransformWorker logs: "Queued 14 projects entities for vectorization" ✅
- VectorizationWorker logs: "Processing vectorization: projects - BDP" ✅
- But NO follow-up logs: "✅ Vectorization complete" ❌
- No errors in logs ❌
- Projects missing from `qdrant_vectors` table ❌

---

## Root Cause Analysis

### Investigation Steps

1. **Checked TransformWorker queueing** ✅
   - Log line 311: "Attempting to queue 14 projects entities for vectorization"
   - Log line 314-353: All 14 projects queued with messages like:
     ```
     Message published to vectorization_queue_tenant_1: 
     {'tenant_id': 1, 'table_name': 'projects', 'external_id': 'BDP', 'operation': 'insert'}
     ```

2. **Checked VectorizationWorker receiving** ✅
   - Log lines 319-357: All 14 projects received:
     ```
     Processing vectorization: projects - BDP
     Processing vectorization: projects - BEN
     ...
     ```

3. **Checked for errors** ❌
   - No "Error processing vectorization" messages
   - No "Failed to generate embedding" messages
   - No "Failed to store in Qdrant" messages
   - **Silent failure!**

4. **Found the bug** 🐛
   - **TransformWorker** (`transform_worker.py` line 1734):
     ```python
     if table_name == 'projects':
         external_id = entity.get('key')  # ← Queues with 'key' field (e.g., "BDP")
     ```
   
   - **VectorizationWorker** (`vectorization_worker.py` line 237):
     ```python
     # All other tables: use external_id field
     else:
         entity = session.query(model).filter(
             model.external_id == external_id,  # ← Tries to fetch by 'external_id' field!
             model.tenant_id == tenant_id,
             model.active == True
         ).first()
     ```

---

## The Bug Explained

### Projects Table Schema
```sql
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(255),  -- Jira numeric ID (e.g., "12658")
    key VARCHAR(50),            -- Jira project key (e.g., "BDP")
    name VARCHAR(255),
    ...
);
```

### What Was Happening

1. **TransformWorker queues**: `{'table_name': 'projects', 'external_id': 'BDP'}`
   - Uses `key` field value ("BDP")

2. **VectorizationWorker tries to fetch**:
   ```python
   session.query(Project).filter(
       Project.external_id == 'BDP',  # ❌ Looking for external_id = "BDP"
       ...
   ).first()
   ```
   - But `external_id` is "12658", not "BDP"!
   - Query returns `None`

3. **VectorizationWorker code** (line 134-137):
   ```python
   if not entity:
       logger.debug(f"Entity not found (may have been queued before commit): {table_name} - {external_id}")
       return False  # ← Silent failure!
   ```
   - Returns `False` without error (only `debug` level log)
   - No "✅ Vectorization complete" message
   - No error message

---

## The Fix

### Changed File: `services/backend-service/app/workers/vectorization_worker.py`

**Before** (lines 218-240):
```python
try:
    # Special case for work_items: use 'key' field instead of 'external_id'
    if table_name == 'work_items':
        entity = session.query(model).filter(
            model.key == external_id,
            model.tenant_id == tenant_id,
            model.active == True
        ).first()
    
    # Special case for work_items_prs_links: use internal ID
    elif table_name == 'work_items_prs_links':
        entity = session.query(model).filter(
            model.id == int(external_id),
            model.tenant_id == tenant_id,
            model.active == True
        ).first()
    
    # All other tables: use external_id field
    else:
        entity = session.query(model).filter(
            model.external_id == external_id,  # ❌ Projects fall into this case!
            model.tenant_id == tenant_id,
            model.active == True
        ).first()
```

**After** (lines 218-249):
```python
try:
    # Special case for projects: use 'key' field instead of 'external_id'
    # TransformWorker queues projects with 'key' (e.g., "BDP", "BEN")
    if table_name == 'projects':
        entity = session.query(model).filter(
            model.key == external_id,  # ✅ Use 'key' field!
            model.tenant_id == tenant_id,
            model.active == True
        ).first()
    
    # Special case for work_items: use 'key' field instead of 'external_id'
    elif table_name == 'work_items':
        entity = session.query(model).filter(
            model.key == external_id,
            model.tenant_id == tenant_id,
            model.active == True
        ).first()
    
    # Special case for work_items_prs_links: use internal ID
    elif table_name == 'work_items_prs_links':
        entity = session.query(model).filter(
            model.id == int(external_id),
            model.tenant_id == tenant_id,
            model.active == True
        ).first()
    
    # All other tables: use external_id field
    else:
        entity = session.query(model).filter(
            model.external_id == external_id,
            model.tenant_id == tenant_id,
            model.active == True
        ).first()
```

---

## Expected Behavior After Fix

### Before Fix:
```
TransformWorker: Queue project with key="BDP"
    ↓
VectorizationWorker: Try to fetch by external_id="BDP"
    ↓
Database: No project with external_id="BDP" (it's "12658")
    ↓
VectorizationWorker: Entity not found, return False (silent)
    ↓
Result: ❌ Project NOT vectorized
```

### After Fix:
```
TransformWorker: Queue project with key="BDP"
    ↓
VectorizationWorker: Try to fetch by key="BDP"
    ↓
Database: Found project with key="BDP" ✅
    ↓
VectorizationWorker: Generate embedding → Store in Qdrant → Store bridge record
    ↓
VectorizationWorker: Log "✅ Vectorization complete: projects - BDP"
    ↓
Result: ✅ Project vectorized successfully
```

---

## Testing

### Test 1: Run Jira Job
```bash
# Trigger Jira job from ETL frontend
# Or use backend API:
curl -X POST http://localhost:3001/app/etl/jira/run-now \
  -H "X-Internal-Auth: your-secret-key"
```

**Expected Logs**:
```
TransformWorker: Attempting to queue 14 projects entities for vectorization
TransformWorker: Queued 14 projects entities for vectorization
VectorizationWorker: Processing vectorization: projects - BDP
VectorizationWorker: ✅ Vectorization complete: projects - BDP  ← NEW!
VectorizationWorker: Processing vectorization: projects - BEN
VectorizationWorker: ✅ Vectorization complete: projects - BEN  ← NEW!
...
```

### Test 2: Check Database
```sql
-- Check qdrant_vectors table
SELECT table_name, COUNT(*) 
FROM qdrant_vectors 
WHERE tenant_id = 1 
GROUP BY table_name;

-- Expected:
-- projects: 14
-- wits: 15 (or 14 if duplicate Milestone is handled)
-- statuses: 39
-- Total: 68
```

### Test 3: Check Qdrant
```bash
# Run diagnostic script
cd services/backend-service
python scripts/diagnose_vectorization.py
```

**Expected Output**:
```
Database Counts:
- projects: 14
- wits: 15
- statuses: 39
Total: 68

Qdrant Vectors Bridge Table:
- projects: 14 ✅
- wits: 15 ✅
- statuses: 39 ✅
Total: 68 ✅

Missing: 0 (all entities vectorized!)
```

---

## Related Issues Fixed

This fix also ensures consistency with how `work_items` are handled:
- Both `projects` and `work_items` use `key` field for querying
- Both have `external_id` field in database but queue with `key`
- VectorizationWorker now handles both correctly

---

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Projects Queued** | ✅ 14 | ✅ 14 |
| **Projects Received** | ✅ 14 | ✅ 14 |
| **Projects Fetched** | ❌ 0 (wrong field) | ✅ 14 (correct field) |
| **Projects Vectorized** | ❌ 0 | ✅ 14 |
| **Error Logs** | ❌ Silent failure | ✅ Clear success logs |

**Root Cause**: Field mismatch between TransformWorker (queues with `key`) and VectorizationWorker (fetched by `external_id`)

**Fix**: Added special case for `projects` table to fetch by `key` field instead of `external_id`

**Impact**: All 14 projects will now be successfully vectorized and stored in Qdrant! 🎉

