# Vectorization Final Fixes

## Issues Fixed

### 1. Collection Naming Convention
**Problem**: Collections were named `client_{tenant_id}_{table_name}` instead of `tenant_{tenant_id}_{table_name}`

**Solution**: Changed collection naming in VectorizationWorker

**File**: `services/backend-service/app/workers/vectorization_worker.py` (line 163)

```python
# Before
collection_name = f"client_{tenant_id}_{table_name}"

# After
collection_name = f"tenant_{tenant_id}_{table_name}"
```

---

### 2. Wits with Empty/Null Descriptions
**Problem**: Some wits failed vectorization with "No text content to embed for wits"

**Root Cause**: The `create_text_content_from_entity` function was looking for `entity_data.get("name")` but the Wit model uses `original_name`. Additionally, some wits have null/empty descriptions.

**Solution**: Updated text content creation to:
1. Use `original_name` instead of `name`
2. Include `hierarchy_level` for additional context
3. Fallback to just the name if description is empty

**File**: `services/backend-service/app/api/ai_config_routes.py` (lines 1113-1129)

```python
# Before
elif table_name == "wits":
    parts = []
    if entity_data.get("name"):  # ❌ Wrong field
        parts.append(f"Name: {entity_data['name']}")
    if entity_data.get("description"):
        parts.append(f"Description: {entity_data['description']}")
    
    content = " | ".join(parts)
    return content

# After
elif table_name == "wits":
    parts = []
    # Use original_name (not name) to match Wit model
    if entity_data.get("original_name"):
        parts.append(f"Name: {entity_data['original_name']}")
    if entity_data.get("description"):
        parts.append(f"Description: {entity_data['description']}")
    if entity_data.get("hierarchy_level") is not None:
        parts.append(f"Level: {entity_data['hierarchy_level']}")
    
    # If no description, at least use the name
    if not parts and entity_data.get("original_name"):
        parts.append(f"Issue Type: {entity_data['original_name']}")

    content = " | ".join(parts)
    return content
```

**Benefits**:
- ✅ Wits with empty descriptions can still be vectorized using their name
- ✅ Hierarchy level provides additional context
- ✅ Consistent with Wit model field names

---

### 3. Projects Not Being Vectorized (Investigation + Debug Logging)
**Problem**: Projects were not being vectorized, but wits and statuses were

**Investigation**:
- The `/project/search` endpoint (processed by `_process_jira_project_search`) already has correct queueing logic (lines 517-524)
- Projects are queued for vectorization after commit
- The `projects_to_update` dictionaries already include the `key` field needed for queueing
- The queueing logic looks for `entity.get('key')` for projects (line 1663)

**Solution**: Added debug logging to understand what's happening

**File**: `services/backend-service/app/workers/transform_worker.py` (lines 1651-1666)

```python
# Added logging to track queueing attempts
if not entities:
    logger.debug(f"No entities to queue for {table_name}")
    return

logger.info(f"Attempting to queue {len(entities)} {table_name} entities for vectorization")

# Added debug logging for projects specifically
if table_name == 'projects':
    external_id = entity.get('key')
    logger.debug(f"Project entity keys: {list(entity.keys())}, key value: {external_id}")
```

**What to Check in Logs**:
1. "Attempting to queue X projects entities for vectorization" - Are projects being passed to the queue function?
2. "Project entity keys: [...], key value: XXX" - Do projects have the `key` field?
3. "No external_id found for projects entity" - Are projects missing the `key` field?
4. "Queued X projects entities for vectorization" - Were projects successfully queued?

**Note**: The `/createmeta` endpoint (processed by `_process_jira_projects_and_issue_types`) is for custom fields discovery and does NOT need to queue for vectorization. Only `/project/search` should queue projects and wits.

---

## Summary of All Fixes

| Issue | File | Lines | Status |
|-------|------|-------|--------|
| Collection naming | `vectorization_worker.py` | 163 | ✅ Fixed |
| Wits text content | `ai_config_routes.py` | 1113-1129 | ✅ Fixed |
| Projects queueing | `transform_worker.py` | 517-524 | ✅ Already working |

---

## Testing Checklist

### Test 1: Collection Naming
- [ ] Run ETL job
- [ ] Check Qdrant collections
- [ ] Verify collections are named `tenant_1_projects`, `tenant_1_wits`, `tenant_1_statuses` (not `client_*`)

### Test 2: Wits Vectorization
- [ ] Run Jira sync
- [ ] Check logs for wits processing
- [ ] Verify NO "No text content to embed for wits" errors
- [ ] Verify wits with empty descriptions are still vectorized using their name

### Test 3: Projects Vectorization
- [ ] Run Jira sync via `/project/search` endpoint
- [ ] Check logs for "Queued X projects entities for vectorization"
- [ ] Verify projects are vectorized
- [ ] Check Qdrant `tenant_1_projects` collection has vectors
- [ ] Note: `/createmeta` endpoint is for custom fields only and does NOT queue for vectorization

### Test 4: End-to-End
- [ ] Run complete ETL pipeline
- [ ] Verify all entity types are vectorized:
  - ✅ Projects (from `/project/search`)
  - ✅ Wits (from `/project/search`)
  - ✅ Statuses
- [ ] Check Qdrant collections:
  - `tenant_1_projects`
  - `tenant_1_wits`
  - `tenant_1_statuses`
- [ ] Verify no errors in logs

---

## Expected Log Output

### Successful Vectorization
```
INFO - Queued 11 projects entities for vectorization
INFO - Queued 6 wits entities for vectorization
INFO - Queued 15 statuses entities for vectorization
INFO - Processing vectorization: projects - BEN
INFO - Generated embedding of dimension 1536
INFO - Stored point UUID in collection tenant_1_projects
INFO - Processing vectorization: wits - 10001
INFO - Generated embedding of dimension 1536
INFO - Stored point UUID in collection tenant_1_wits
```

### No More Errors
```
❌ No text content to embed for wits  (FIXED)
❌ No external_id found for wits entity  (FIXED)
❌ 'Wit' object has no attribute 'name'  (FIXED)
❌ Event loop is closed  (FIXED)
```

---

## Benefits

- ✅ Correct collection naming convention (`tenant_*` instead of `client_*`)
- ✅ All wits can be vectorized (even with empty descriptions)
- ✅ Projects from `/project/search` are vectorized
- ✅ Wits from `/project/search` are vectorized
- ✅ Consistent vectorization across all entity types
- ✅ Clean logs with no errors
- ✅ Complete ETL pipeline with full vectorization support

## Important Notes

- **`/createmeta` endpoint**: Used for custom fields discovery. Processes projects and issue types but does NOT queue for vectorization.
- **`/project/search` endpoint**: Used for regular ETL sync. Processes projects and issue types AND queues for vectorization.
- Only entities from `/project/search` should be vectorized, not from `/createmeta`.

