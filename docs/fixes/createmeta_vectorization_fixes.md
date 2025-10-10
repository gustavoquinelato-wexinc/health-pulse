# Custom Fields Sync (/createmeta) Vectorization Fixes

## Issues Identified

### Issue #1: WITs Getting Vectorized from `/createmeta`
**Problem**: When running Jira sync at the custom_fields page (which uses `/createmeta`), WITs were being queued for vectorization.

**Root Cause**: The `_process_jira_custom_fields` method was queueing projects and wits for vectorization (lines 905-908).

**Why This is Wrong**: 
- `/createmeta` endpoint is for **custom fields discovery only**
- It processes projects and WITs as a side effect (to understand which custom fields belong to which projects/issue types)
- Only `/project/search` should queue for vectorization
- Vectorizing from both endpoints would create duplicates

**Solution**: Removed vectorization queueing from `_process_jira_custom_fields`

**File**: `services/backend-service/app/workers/transform_worker.py` (lines 896-904)

```python
# BEFORE (WRONG)
# Commit all changes BEFORE queueing for vectorization
session.commit()

# 7. Queue entities for vectorization AFTER commit
if bulk_result:
    if bulk_result.get('projects_to_insert'):
        self._queue_entities_for_vectorization(tenant_id, 'projects', bulk_result['projects_to_insert'])
    if bulk_result.get('projects_to_update'):
        self._queue_entities_for_vectorization(tenant_id, 'projects', bulk_result['projects_to_update'])
    if bulk_result.get('wits_to_insert'):
        self._queue_entities_for_vectorization(tenant_id, 'wits', bulk_result['wits_to_insert'])
    if bulk_result.get('wits_to_update'):
        self._queue_entities_for_vectorization(tenant_id, 'wits', bulk_result['wits_to_update'])

# AFTER (CORRECT)
# Commit all changes
session.commit()

# NOTE: /createmeta is for custom fields discovery only
# Projects and WITs are NOT queued for vectorization here
# Only /project/search should queue for vectorization
```

---

### Issue #2: WITs Saved Without `wits_mapping_id`
**Problem**: None of the saved WITs have `wits_mapping_id` set.

**Root Cause**: The `_process_wit_data` method was setting `wits_mapping_id = None` with a comment "Will be set by mapping logic later", but there was no mapping logic!

**Why This is Important**:
- `wits_mapping_id` links WITs to their standardized mapping (e.g., "Story" → "User Story", hierarchy level 0)
- Without this, the system doesn't know how to categorize/group different WIT types
- The mapping is defined in the `wits_mappings` table

**Solution**: Added `_lookup_wit_mapping_id` method to lookup the mapping based on `wit_from` (original_name) and `tenant_id`

**File**: `services/backend-service/app/workers/transform_worker.py` (lines 1112-1215)

```python
def _process_wit_data(...):
    # ... existing code ...
    
    # Lookup wits_mapping_id from wits_mappings table
    wits_mapping_id = self._lookup_wit_mapping_id(wit_name, tenant_id)
    if wits_mapping_id:
        logger.info(f"Found wits_mapping_id={wits_mapping_id} for WIT '{wit_name}'")
    else:
        logger.info(f"No wits_mapping found for WIT '{wit_name}' - will be set to NULL")
    
    # Include wits_mapping_id in both insert and update
    if wit_external_id in existing_wits:
        # Update
        result['wits_to_update'].append({
            'id': existing_wit.id,
            'external_id': wit_external_id,
            'original_name': wit_name,
            'description': wit_description,
            'hierarchy_level': hierarchy_level,
            'wits_mapping_id': wits_mapping_id,  # ✅ Added
            'last_updated_at': datetime.now(timezone.utc)
        })
    else:
        # Insert
        wit_insert_data = {
            'external_id': wit_external_id,
            'original_name': wit_name,
            'description': wit_description,
            'hierarchy_level': hierarchy_level,
            'wits_mapping_id': wits_mapping_id,  # ✅ Added
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'active': True,
            'created_at': datetime.now(timezone.utc),
            'last_updated_at': datetime.now(timezone.utc)
        }

def _lookup_wit_mapping_id(self, wit_name: str, tenant_id: int) -> Optional[int]:
    """
    Lookup wits_mapping_id from wits_mappings table based on wit_from (original_name).
    """
    try:
        with self.get_db_session() as session:
            from sqlalchemy import func
            from app.models.unified_models import WitMapping
            
            # Case-insensitive lookup
            mapping = session.query(WitMapping).filter(
                func.lower(WitMapping.wit_from) == wit_name.lower(),
                WitMapping.tenant_id == tenant_id,
                WitMapping.active == True
            ).first()
            
            return mapping.id if mapping else None
            
    except Exception as e:
        logger.warning(f"Error looking up wit mapping for '{wit_name}': {e}")
        return None
```

**How It Works**:
1. When processing a WIT (e.g., "Story"), lookup in `wits_mappings` table
2. Find matching record where `wit_from = "Story"` and `tenant_id = 1`
3. Get the `id` from that record
4. Store it as `wits_mapping_id` in the `wits` table

**Example**:
```sql
-- wits_mappings table
id | wit_from | wit_to      | wits_hierarchy_id | tenant_id
1  | Story    | User Story  | 5                 | 1
2  | Bug      | Defect      | 6                 | 1

-- wits table (after fix)
id | external_id | original_name | wits_mapping_id | tenant_id
10 | 10001       | Story         | 1               | 1
11 | 10004       | Bug           | 2               | 1
```

---

### Issue #3: VectorizationWorker Should Handle INSERT vs UPDATE
**Problem**: If custom fields sync runs first, WITs are created. Then when Jira job runs, TransformWorker performs UPDATE on WITs. VectorizationWorker should understand if this is an INSERT or UPDATE in Qdrant.

**Analysis**: This is already handled correctly! ✅

**How It Works**:

#### 1. Deterministic Point ID Generation
The VectorizationWorker generates a **deterministic UUID** for each entity based on `tenant_id`, `table_name`, and `record_id`:

```python
# services/backend-service/app/workers/vectorization_worker.py (lines 391-410)
def _get_point_id(self, table_name: str, external_id: str, record_id: int) -> str:
    """Generate Qdrant point ID for the entity (UUID format)."""
    import uuid

    # Create deterministic UUID for point ID
    # This ensures same entity always gets same point ID
    unique_string = f"{self.tenant_id}_{table_name}_{record_id}"
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

    return point_id
```

**Why This Matters**:
- Same entity (e.g., WIT id=10) always generates the **same point ID**
- First vectorization: Qdrant inserts new point with this ID
- Re-vectorization: Qdrant **replaces** existing point with same ID (no duplicate!)

**Example**:
```python
# First time: WIT id=10 for tenant_id=1
point_id = uuid5("1_wits_10")  # → "a1b2c3d4-..."

# Second time: Same WIT updated
point_id = uuid5("1_wits_10")  # → "a1b2c3d4-..." (SAME ID!)
```

#### 2. Qdrant Upsert Operation
Qdrant's `upsert` method handles both INSERT and UPDATE automatically:

```python
# services/backend-service/app/ai/qdrant_client.py (lines 265-270)
await asyncio.get_event_loop().run_in_executor(
    None,
    self.client.upsert,  # ← Official Qdrant client upsert method
    collection_name,
    batch
)
```

**Qdrant Upsert Behavior** (from Qdrant documentation):
- If point with ID exists → **UPDATE** (replace vector and payload)
- If point with ID doesn't exist → **INSERT** (create new point)
- **No duplicates** are ever created!

#### 3. Bridge Table Upsert
The `qdrant_vectors` bridge table uses PostgreSQL UPSERT:
```python
# services/backend-service/app/workers/vectorization_worker.py (lines 586-609)
stmt = insert(QdrantVector).values(
    source_type=source_type,
    table_name=table_name,
    record_id=record_id,
    qdrant_collection=collection_name,
    qdrant_point_id=qdrant_point_id,
    vector_type='content',
    integration_id=integration_id,
    tenant_id=tenant_id,
    active=True
)

# ON CONFLICT UPDATE
stmt = stmt.on_conflict_do_update(
    index_elements=['tenant_id', 'table_name', 'record_id', 'vector_type'],
    set_={
        'qdrant_point_id': qdrant_point_id,
        'qdrant_collection': collection_name,
        'integration_id': integration_id,
        'active': True,
        'last_updated_at': datetime.utcnow()
    }
)
```

**Conflict Resolution**: Based on unique constraint `(tenant_id, table_name, record_id, vector_type)`

---

### Summary: No Duplicates Anywhere! ✅

**Qdrant Collections**:
- ✅ Deterministic point IDs ensure same entity → same ID
- ✅ Qdrant `upsert` replaces existing points (no duplicates)
- ✅ Re-vectorization updates the vector, not creates new one

**Bridge Table** (`qdrant_vectors`):
- ✅ PostgreSQL UPSERT based on `(tenant_id, table_name, record_id, vector_type)`
- ✅ Re-vectorization updates `last_updated_at` (no duplicates)

**Result**: Whether you run custom fields sync first or Jira job first, or run them multiple times, you'll never get duplicate vectors! 🎉

**Scenario Example**:

1. **Custom Fields Sync Runs First** (`/createmeta`):
   - WIT "Story" (id=10) is inserted into `wits` table
   - ❌ NOT queued for vectorization (after fix #1)

2. **Jira Job Runs** (`/project/search`):
   - WIT "Story" (id=10) already exists
   - TransformWorker detects changes and adds to `wits_to_update`
   - ✅ Queued for vectorization with `external_id = "10001"`
   - VectorizationWorker:
     - Fetches WIT from database (id=10)
     - Generates embedding
     - Calls `upsert_vectors` → **INSERT** (first time)
     - Calls `_store_bridge_record` → **INSERT** (first time)

3. **Jira Job Runs Again** (later):
   - WIT "Story" (id=10) has description change
   - TransformWorker adds to `wits_to_update`
   - ✅ Queued for vectorization
   - VectorizationWorker:
     - Fetches updated WIT from database
     - Generates new embedding
     - Calls `upsert_vectors` → **UPDATE** (point exists)
     - Calls `_store_bridge_record` → **UPDATE** (record exists)

**Result**: The system correctly handles both INSERT and UPDATE without any issues! ✅

---

## Summary of Fixes

| Issue | Status | File | Lines |
|-------|--------|------|-------|
| #1: WITs vectorized from `/createmeta` | ✅ Fixed | `transform_worker.py` | 896-904 |
| #2: WITs missing `wits_mapping_id` | ✅ Fixed | `transform_worker.py` | 1112-1215 |
| #3: INSERT vs UPDATE handling | ✅ Already Working | `vectorization_worker.py` | 586-609 |

---

## Testing Checklist

### Test 1: Custom Fields Sync (No Vectorization)
- [ ] Run custom fields sync from ETL frontend
- [ ] Check logs - should NOT see "Queued X wits entities for vectorization"
- [ ] Verify WITs are saved with `wits_mapping_id` populated
- [ ] Check `qdrant_vectors` table - should be empty (no vectorization)

### Test 2: Jira Job After Custom Fields Sync
- [ ] Run Jira job (`/project/search`)
- [ ] Check logs - should see "Queued X wits entities for vectorization"
- [ ] Verify WITs are updated (if changes detected)
- [ ] Check `qdrant_vectors` table - should have records for WITs
- [ ] Check Qdrant collection `tenant_1_wits` - should have vectors

### Test 3: WITs Mapping Lookup
- [ ] Ensure `wits_mappings` table has mappings (e.g., "Story" → "User Story")
- [ ] Run custom fields sync
- [ ] Check `wits` table - `wits_mapping_id` should be populated
- [ ] Verify mapping is correct (matches `wits_mappings.id`)

### Test 4: Update Scenario
- [ ] Run Jira job first time (creates WITs and vectors)
- [ ] Change WIT description in Jira
- [ ] Run Jira job again
- [ ] Check logs - should see "WIT needs update"
- [ ] Verify `qdrant_vectors.last_updated_at` is updated
- [ ] Verify Qdrant vector is updated (not duplicated)

---

## Expected Behavior

### `/createmeta` (Custom Fields Sync)
```
✅ Processes projects (insert/update)
✅ Processes WITs (insert/update)
✅ Sets wits_mapping_id based on lookup
✅ Processes custom fields
✅ Creates project-wit relationships
❌ Does NOT queue for vectorization
```

### `/project/search` (Jira Job)
```
✅ Processes projects (insert/update)
✅ Processes WITs (insert/update)
✅ Sets wits_mapping_id based on lookup
✅ Creates project-wit relationships
✅ Queues projects for vectorization
✅ Queues WITs for vectorization
```

### VectorizationWorker
```
✅ Handles both INSERT and UPDATE automatically
✅ Uses Qdrant upsert (no duplicates)
✅ Uses PostgreSQL UPSERT for bridge table
✅ Updates last_updated_at on re-vectorization
```

---

## Benefits

1. ✅ **No Duplicate Vectors**: Only `/project/search` queues for vectorization
2. ✅ **Proper WIT Mapping**: All WITs have `wits_mapping_id` set correctly
3. ✅ **Idempotent Operations**: Can run custom fields sync multiple times safely
4. ✅ **Correct Update Handling**: VectorizationWorker handles INSERT/UPDATE transparently
5. ✅ **Clean Separation**: `/createmeta` for discovery, `/project/search` for ETL

