# Vectorization Queue Timing Fix

## Problem

The VectorizationWorker was only processing `statuses` messages from the queue, but not `projects` or `wits` messages, even though the TransformWorker was queueing them.

## Root Cause

The TransformWorker was queueing entities for vectorization **BEFORE** committing them to the database:

```
1. TransformWorker inserts projects/wits into database (not committed yet)
2. TransformWorker queues them for vectorization
3. VectorizationWorker picks up the message immediately
4. VectorizationWorker tries to fetch the entity from database
5. ❌ Entity doesn't exist yet because commit hasn't happened
6. VectorizationWorker returns False (entity not found)
7. TransformWorker commits the database transaction
```

This created a race condition where the VectorizationWorker would try to process entities that didn't exist yet in the database.

### Why Statuses Worked

The statuses processing code (in `_process_jira_statuses_and_project_relationships`) was already doing it correctly:

```python
# Commit all changes BEFORE queueing for vectorization
db.commit()

# Queue statuses for vectorization AFTER commit
if statuses_result['statuses_to_insert']:
    self._queue_entities_for_vectorization(tenant_id, 'statuses', ...)
```

But the projects/wits processing code was queueing BEFORE commit.

## Solution

Updated the TransformWorker to follow the same pattern as statuses - **commit BEFORE queueing**.

### Changes Made

#### 1. Fixed `_process_jira_project_search` method

**Before**:
```python
# Bulk operations
if result['projects_to_insert']:
    bulk_ops.bulk_insert(session, 'projects', result['projects_to_insert'])
    # Queue for vectorization BEFORE commit ❌
    self._queue_entities_for_vectorization(tenant_id, 'projects', result['projects_to_insert'])

# ... more operations ...

session.commit()  # Commit happens AFTER queueing
```

**After**:
```python
# Bulk operations
if result['projects_to_insert']:
    bulk_ops.bulk_insert(session, 'projects', result['projects_to_insert'])
    # Don't queue yet

# ... more operations ...

# Commit all changes BEFORE queueing for vectorization
session.commit()

# Queue entities for vectorization AFTER commit ✅
if result['projects_to_insert']:
    self._queue_entities_for_vectorization(tenant_id, 'projects', result['projects_to_insert'])
```

#### 2. Fixed `_perform_bulk_operations` method

**Before**:
```python
def _perform_bulk_operations(...):
    if projects_to_insert:
        BulkOperations.bulk_insert(session, 'projects', projects_to_insert)
        # Queue for vectorization immediately ❌
        self._queue_entities_for_vectorization(tenant_id, 'projects', projects_to_insert)
```

**After**:
```python
def _perform_bulk_operations(...):
    """
    Perform bulk database operations.
    
    NOTE: This method only performs database operations.
    Vectorization queueing should be done AFTER commit by the caller.
    """
    if projects_to_insert:
        BulkOperations.bulk_insert(session, 'projects', projects_to_insert)
        # Don't queue - let caller handle it after commit
    
    # Return the entities that need vectorization
    return {
        'projects_to_insert': projects_to_insert,
        'projects_to_update': projects_to_update,
        'wits_to_insert': wits_to_insert,
        'wits_to_update': wits_to_update
    }
```

#### 3. Updated caller to queue after commit

```python
# Perform bulk operations
bulk_result = self._perform_bulk_operations(...)

# Update raw data status
self._update_raw_data_status(session, raw_data_id, 'completed')

# Commit all changes BEFORE queueing for vectorization
session.commit()

# Queue entities for vectorization AFTER commit ✅
if bulk_result:
    if bulk_result.get('projects_to_insert'):
        self._queue_entities_for_vectorization(tenant_id, 'projects', bulk_result['projects_to_insert'])
    if bulk_result.get('projects_to_update'):
        self._queue_entities_for_vectorization(tenant_id, 'projects', bulk_result['projects_to_update'])
    # ... etc
```

## Correct Flow After Fix

```
1. TransformWorker inserts projects/wits into database
2. TransformWorker commits the database transaction
3. TransformWorker queues entities for vectorization
4. VectorizationWorker picks up the message
5. VectorizationWorker fetches the entity from database
6. ✅ Entity exists because commit already happened
7. VectorizationWorker generates embedding and stores in Qdrant
```

## Key Principle

**Always commit database changes BEFORE queueing async operations that depend on those changes.**

This ensures that:
- ✅ Entities exist in the database when workers try to fetch them
- ✅ No race conditions between commit and queue processing
- ✅ Consistent behavior across all entity types
- ✅ Failed vectorization doesn't block database commits

## Files Modified

1. `services/backend-service/app/workers/transform_worker.py`
   - `_process_jira_project_search()` - Moved queueing after commit
   - `_perform_bulk_operations()` - Removed queueing, returns entities instead
   - `_process_jira_custom_fields()` - Updated to queue after commit

## Testing

After this fix:

1. **Run a Jira sync** that creates/updates projects and issue types
2. **Check the logs** - you should see:
   ```
   Queued X projects entities for vectorization
   Queued Y wits entities for vectorization
   ```
3. **Check VectorizationWorker logs** - you should see:
   ```
   Processing vectorization: projects - PROJECT_KEY
   Processing vectorization: wits - 10001
   Generated embedding of dimension 1536
   Stored point UUID in collection client_1_projects
   ```
4. **Verify in Qdrant** - collections should contain vectors for projects and wits

## Related Patterns

This same pattern should be applied anywhere we:
1. Insert/update database records
2. Queue async operations that depend on those records

Examples:
- ✅ Statuses processing (already correct)
- ✅ Projects/WITs processing (fixed)
- 🔍 Work items processing (check if needed)
- 🔍 GitHub PRs processing (check if needed)
- 🔍 Changelogs processing (check if needed)

## Additional Fix #1: Wit Model Attributes

### Problem
After fixing the queue timing, VectorizationWorker started processing wits but encountered errors:
```
ERROR - Error preparing entity data for wits: 'Wit' object has no attribute 'name'
```

### Root Cause
The `_prepare_entity_data` method was trying to access `entity.name` and `entity.icon_url` for wits, but the Wit model uses different field names:
- ✅ `original_name` (not `name`)
- ✅ `external_id` (for identification)
- ✅ `hierarchy_level` (for context)
- ❌ No `icon_url` field exists

### Solution
Updated the wits data preparation to use correct field names:

**Before**:
```python
elif table_name == "wits":
    return {
        "name": entity.name or "",  # ❌ Wrong field
        "description": entity.description or "",
        "icon_url": entity.icon_url or ""  # ❌ Field doesn't exist
    }
```

**After**:
```python
elif table_name == "wits":
    return {
        "external_id": entity.external_id or "",
        "original_name": entity.original_name or "",  # ✅ Correct field
        "description": entity.description or "",
        "hierarchy_level": entity.hierarchy_level or 0
    }
```

---

## Additional Fix #2: Missing external_id in Wits Queue Messages

### Problem
After fixing the Wit model attributes, TransformWorker was still warning:
```
WARNING - No external_id found for wits entity: {'id': 78, 'original_name': 'Epic', ...}
```

### Root Cause
When preparing wits for queueing, the `wits_to_update` dictionaries didn't include `external_id`:

**In `_process_project_search_data` method (line 621-631)**:
```python
result['wits_to_update'].append({
    'id': existing_wit.id,
    # ❌ Missing external_id
    'original_name': wit_name,
    'description': wit_description,
    'hierarchy_level': hierarchy_level,
    'last_updated_at': datetime.now(timezone.utc)
})
```

**In `_process_issue_types_data` method (line 373-386)**:
```python
issue_types_to_update.append({
    'id': existing[1],
    # ❌ Missing external_id
    'original_name': original_name,
    'description': description,
    'hierarchy_level': hierarchy_level,
    'wits_mapping_id': wits_mapping_id
})
```

### Solution
Added `external_id` to both update dictionaries:

**After**:
```python
# In _process_project_search_data
result['wits_to_update'].append({
    'id': existing_wit.id,
    'external_id': wit_external_id,  # ✅ Added for queueing
    'original_name': wit_name,
    'description': wit_description,
    'hierarchy_level': hierarchy_level,
    'last_updated_at': datetime.now(timezone.utc)
})

# In _process_issue_types_data
issue_types_to_update.append({
    'id': existing[1],
    'external_id': external_id,  # ✅ Added for queueing
    'original_name': original_name,
    'description': description,
    'hierarchy_level': hierarchy_level,
    'wits_mapping_id': wits_mapping_id
})
```

### Why This Matters
The `_queue_entities_for_vectorization` method looks for `external_id` in the entity dictionary:
```python
elif table_name == 'wits':
    external_id = entity.get('external_id')  # Needs this field!
```

Without `external_id` in the dictionary, the queueing fails with a warning and the entity is not vectorized.

## Benefits

- ✅ VectorizationWorker can now process all entity types
- ✅ No more "entity not found" errors (commit before queue)
- ✅ No more "object has no attribute 'name'" errors for wits (correct field names)
- ✅ No more "No external_id found" warnings (external_id included in updates)
- ✅ Consistent vectorization across projects, wits, and statuses
- ✅ Proper separation of concerns (commit → queue → process)
- ✅ More reliable ETL pipeline
- ✅ Correct field mapping for all entity types
- ✅ Both insert and update operations queue correctly for vectorization

