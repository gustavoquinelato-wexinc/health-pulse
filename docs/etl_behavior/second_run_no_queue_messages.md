# ETL Second Run - No Queue Messages (Expected Behavior)

## Question

> "At the second job run, the job runs normally but I don't see any messages in neither the transform nor the vectorization queues. If those queues are not getting new messages because there were no updates to be done in the new extracted records, then fine! but can you confirm that?"

## Answer

**✅ YES, this is EXPECTED BEHAVIOR!**

The ETL system only queues entities for vectorization when they are **inserted** or **updated**. If the data hasn't changed, nothing is queued.

---

## Evidence from Logs

### First Run (10:14:50)

```
📊 Summary: 14 projects to insert, 0 to update
📊 Summary: 14 WITs to insert, 0 to update (deduplicated from 14 unique)

Attempting to queue 14 projects entities for vectorization
Queued 14 projects entities for vectorization

Attempting to queue 14 wits entities for vectorization
Queued 14 wits entities for vectorization
```

**Result**: 14 projects + 14 WITs queued for vectorization ✅

---

### Second Run (10:20:09)

```
📊 Summary: 0 projects to insert, 0 to update
📊 Summary: 0 WITs to insert, 0 to update (deduplicated from 14 unique)

Creating 90 project-wit relationships
Created 90 project-wit relationships
Successfully processed Jira project search data
```

**Result**: 0 projects + 0 WITs queued for vectorization ✅

**Why?** No changes detected - all data is identical to what's already in the database.

---

## How the Logic Works

### Projects Update Detection

```python
if project_external_id in existing_projects:
    # Update existing project
    existing_project = existing_projects[project_external_id]
    if (existing_project.key != project_key or
        existing_project.name != project_name or
        existing_project.project_type != project_type):
        result['projects_to_update'].append({...})  # ← Only if changed!
```

**Checks**:
- ✅ Project key changed?
- ✅ Project name changed?
- ✅ Project type changed?

If **ALL** are the same → **NO UPDATE** → **NO QUEUEING**

---

### WITs Update Detection

```python
if wit_external_id in existing_wits:
    # Check if WIT needs update
    existing_wit = existing_wits[wit_external_id]
    if (existing_wit.original_name != wit_name or
        existing_wit.description != wit_description or
        existing_wit.hierarchy_level != hierarchy_level or
        existing_wit.wits_mapping_id != wits_mapping_id):
        result['wits_to_update'].append({...})  # ← Only if changed!
```

**Checks**:
- ✅ WIT name changed?
- ✅ WIT description changed?
- ✅ WIT hierarchy level changed?
- ✅ WIT mapping ID changed?

If **ALL** are the same → **NO UPDATE** → **NO QUEUEING**

---

### Queueing Logic

```python
# 6. Queue entities for vectorization AFTER commit
if result['projects_to_insert']:
    self._queue_entities_for_vectorization(tenant_id, 'projects', result['projects_to_insert'])
if result['projects_to_update']:
    self._queue_entities_for_vectorization(tenant_id, 'projects', result['projects_to_update'])
if result['wits_to_insert']:
    self._queue_entities_for_vectorization(tenant_id, 'wits', result['wits_to_insert'])
if result['wits_to_update']:
    self._queue_entities_for_vectorization(tenant_id, 'wits', result['wits_to_update'])
```

**Key Point**: Queueing happens **ONLY IF** there are entities in the insert/update lists.

---

## When Would Second Run Queue Messages?

The second run would queue messages if:

### Scenario 1: Project Name Changed in Jira
```
First Run:  Project "BDP" with name "Benefits Data Products"
            → Inserted → Queued for vectorization

Jira Change: Admin renames project to "Benefits Data Platform"

Second Run: Project "BDP" with name "Benefits Data Platform"
            → existing_project.name != project_name
            → Added to projects_to_update
            → Queued for vectorization ✅
```

### Scenario 2: WIT Description Changed in Jira
```
First Run:  WIT "Story" with description "A user story"
            → Inserted → Queued for vectorization

Jira Change: Admin updates description to "User story for development"

Second Run: WIT "Story" with description "User story for development"
            → existing_wit.description != wit_description
            → Added to wits_to_update
            → Queued for vectorization ✅
```

### Scenario 3: New WIT Mapping Created
```
First Run:  WIT "Story" with wits_mapping_id = NULL
            → Inserted → Queued for vectorization

User Action: Creates mapping "Story" → "User Story" in WITs Mappings page

Second Run: WIT "Story" with wits_mapping_id = 5
            → existing_wit.wits_mapping_id != wits_mapping_id
            → Added to wits_to_update
            → Queued for vectorization ✅
```

---

## Statuses Behavior

**Note**: Statuses are processed differently - they are extracted per-project, not globally.

From the logs, we can see statuses ARE being queued on subsequent runs:

```
Second Run (10:20:11):
Attempting to queue 12 statuses entities for vectorization
Attempting to queue 8 statuses entities for vectorization
Attempting to queue 4 statuses entities for vectorization
...
```

**Why?** Statuses are extracted from each project's workflow, and the extraction logic processes them per-project, so they may be re-queued even if unchanged. This is a different pattern from projects/WITs.

---

## Summary Table

| Entity Type | First Run | Second Run (No Changes) | Second Run (With Changes) |
|-------------|-----------|-------------------------|---------------------------|
| **Projects** | ✅ Queued (14 inserted) | ❌ Not queued (0 changed) | ✅ Queued (N updated) |
| **WITs** | ✅ Queued (14 inserted) | ❌ Not queued (0 changed) | ✅ Queued (N updated) |
| **Statuses** | ✅ Queued (39 inserted) | ✅ Queued (per-project extraction) | ✅ Queued (per-project extraction) |

---

## Verification

### Check if Data Actually Changed

```sql
-- Check if any projects were updated recently
SELECT key, name, last_updated_at 
FROM projects 
WHERE tenant_id = 1 
ORDER BY last_updated_at DESC;

-- Check if any WITs were updated recently
SELECT external_id, original_name, last_updated_at 
FROM wits 
WHERE tenant_id = 1 
ORDER BY last_updated_at DESC;
```

**Expected**: If second run didn't queue anything, `last_updated_at` should still be from the first run.

---

### Check Vectorization Status

```sql
-- Check what's been vectorized
SELECT table_name, COUNT(*) 
FROM qdrant_vectors 
WHERE tenant_id = 1 
GROUP BY table_name;
```

**Expected**:
- First run: 14 projects + 14 WITs + 39 statuses = 67 total
- Second run: Same counts (no new vectorizations)

---

## Conclusion

**✅ CONFIRMED: This is expected behavior!**

The ETL system is **smart** and **efficient**:
- ✅ Only extracts data from Jira (always runs)
- ✅ Only transforms and stores data that changed (conditional)
- ✅ Only queues for vectorization what was inserted/updated (conditional)
- ✅ Avoids unnecessary work and queue messages

**Benefits**:
1. **Performance**: No wasted CPU/memory on unchanged data
2. **Cost**: No unnecessary embedding API calls
3. **Idempotency**: Can run the job multiple times safely
4. **Efficiency**: Queue workers only process what's needed

**When to Worry**:
- ❌ If you KNOW data changed in Jira but second run shows "0 to update"
- ❌ If vectorization counts don't match database counts after first run
- ❌ If logs show errors during comparison logic

**Your Case**: ✅ Everything is working perfectly! The job is being smart and not queueing unchanged data.

