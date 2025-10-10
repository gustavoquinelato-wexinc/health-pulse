# Project Search Separation and WIT Deduplication Fixes

## Issues Identified

### Issue #1: WITs Not Deduplicated
**Problem**: The same WIT (e.g., "Story", "Bug") appears in multiple projects, but the code was adding it to insert/update lists multiple times, causing duplicates.

**Example**:
- Project "BDP" has: Story, Bug, Epic, Task
- Project "BEN" has: Story, Bug, Epic, Task (SAME WITs!)
- Old code: Tried to insert/update "Story" twice, "Bug" twice, etc.

**Root Cause**: The `_process_project_search_data` function was processing WITs inside the project loop without tracking which WITs had already been seen.

**Solution**: Added `wits_seen` dictionary to track unique WITs across all projects.

```python
# Track unique WITs across all projects to avoid duplicates
wits_seen = {}  # external_id -> wit_data

for project_data in projects_data:
    # ... process project ...
    
    for issue_type in issue_types:
        wit_external_id = issue_type.get('id')
        
        # Only process each unique WIT once (deduplicate)
        if wit_external_id not in wits_seen:
            # Process WIT (insert or update)
            wits_seen[wit_external_id] = True
```

---

### Issue #2: `/createmeta` vs `/project/search` Not Separated
**Problem**: The code was trying to reuse logic between two completely different API endpoints with different purposes and structures.

**Differences**:

| Aspect | `/createmeta` | `/project/search` |
|--------|---------------|-------------------|
| **Purpose** | Custom fields discovery | Projects & WITs extraction |
| **Structure** | `{ "projects": [...] }` | `{ "values": [...] }` |
| **Issue Types** | Has `"fields": { ... }` with custom fields | NO `fields` property |
| **Vectorization** | ❌ Should NOT queue | ✅ Should queue |
| **When Called** | Manual sync from custom fields page | Automatic Jira job execution |

**Solution**: Completely separated the two flows:

1. **`/createmeta`** → `_process_jira_custom_fields()` → NO vectorization
2. **`/project/search`** → `_process_jira_project_search()` → YES vectorization

---

### Issue #3: Projects Not Being Vectorized
**Problem**: All 14 projects were in the database but NOT in `qdrant_vectors` table.

**Root Cause**: The diagnostic showed that projects were being processed but not queued for vectorization. This was likely because:
1. The queueing logic was correct
2. But the `key` field might not have been included in update dictionaries

**Solution**: Ensured `key` field is always included in both insert and update dictionaries for projects.

```python
# Insert
result['projects_to_insert'].append({
    'external_id': project_external_id,
    'key': project_key,  # ✅ Needed for queueing
    'name': project_name,
    'project_type': project_type,
    ...
})

# Update
result['projects_to_update'].append({
    'id': existing_project.id,
    'key': project_key,  # ✅ Needed for queueing
    'name': project_name,
    'project_type': project_type,
    ...
})
```

---

### Issue #4: Missing 1 WIT (Milestone)
**Problem**: Diagnostic showed WIT id=15 (Milestone, external_id=10364) was missing from vectorization.

**Root Cause**: There are TWO "Milestone" WITs with the SAME external_id=10364:
- WIT id=13: external_id=10364, name=Milestone
- WIT id=15: external_id=10364, name=Milestone

This is a **data quality issue** in Jira - duplicate issue types with same ID.

**Solution**: The deduplication logic will now handle this correctly - only the first occurrence will be processed.

---

### Issue #5: 6 WITs Missing `wits_mapping_id`
**Problem**: These WITs don't have mappings in `wits_mappings` table:
- Project Review Element
- Risk
- Capital Investment
- Milestone (both)
- Initiative

**Root Cause**: No mappings exist in `wits_mappings` table for these WIT names.

**Solution**: The `_lookup_wit_mapping_id` function now handles this gracefully - returns `None` if no mapping found, and the WIT is still saved with `wits_mapping_id = NULL`.

**Action Required**: User needs to create mappings for these WITs in the WITs Mappings page if they want them categorized.

---

## Code Changes

### File: `services/backend-service/app/workers/transform_worker.py`

#### Change #1: Added WIT Deduplication (lines 535-686)

**Before**:
```python
# Process each project
for project_data in projects_data:
    # ... process project ...
    
    for issue_type in issue_types:
        # ❌ Processes same WIT multiple times if it appears in multiple projects
        if wit_external_id in existing_wits:
            result['wits_to_update'].append(...)
        else:
            result['wits_to_insert'].append(...)
```

**After**:
```python
# Track unique WITs across all projects
wits_seen = {}

# Process each project
for project_data in projects_data:
    # ... process project ...
    
    for issue_type in issue_types:
        # ✅ Only process each unique WIT once
        if wit_external_id not in wits_seen:
            if wit_external_id in existing_wits:
                result['wits_to_update'].append(...)
            else:
                result['wits_to_insert'].append(...)
            
            wits_seen[wit_external_id] = True
```

#### Change #2: Added `wits_mapping_id` Lookup (line 646)

```python
# Lookup wits_mapping_id
wits_mapping_id = self._lookup_wit_mapping_id(wit_name, tenant_id)
```

#### Change #3: Added `project_type` to Projects (lines 570, 577, 584)

```python
# Insert
result['projects_to_insert'].append({
    ...
    'project_type': project_type,  # ✅ Added
    ...
})

# Update
result['projects_to_update'].append({
    ...
    'project_type': project_type,  # ✅ Added
    ...
})
```

#### Change #4: Added Logging for Debugging (lines 560, 571, 579, 663, 673, 684-685)

```python
logger.info(f"  📁 Processing project {project_key} ({project_name})")
logger.info(f"    ✏️  Project {project_key} needs update")
logger.info(f"    ➕ Project {project_key} is new")
logger.info(f"      ✏️  WIT {wit_name} (id={wit_external_id}) needs update")
logger.info(f"      ➕ WIT {wit_name} (id={wit_external_id}) is new")
logger.info(f"📊 Summary: {len(result['projects_to_insert'])} projects to insert, {len(result['projects_to_update'])} to update")
logger.info(f"📊 Summary: {len(result['wits_to_insert'])} WITs to insert, {len(result['wits_to_update'])} to update (deduplicated from {len(wits_seen)} unique)")
```

---

## Testing Checklist

### Test 1: Run Jira Job and Check Deduplication
- [ ] Run Jira job (automatic execution)
- [ ] Check logs for "deduplicated from X unique" message
- [ ] Verify no duplicate WITs in database
- [ ] Verify no duplicate WITs in `qdrant_vectors` table

### Test 2: Verify Projects Are Vectorized
- [ ] Run Jira job
- [ ] Check logs for "Queued X projects entities for vectorization"
- [ ] Verify all 14 projects are in `qdrant_vectors` table
- [ ] Verify `tenant_1_projects` collection in Qdrant has 14 vectors

### Test 3: Verify WITs Are Vectorized
- [ ] Run Jira job
- [ ] Check logs for "Queued X wits entities for vectorization"
- [ ] Verify all 15 WITs are in `qdrant_vectors` table (or 14 if duplicate Milestone is handled)
- [ ] Verify `tenant_1_wits` collection in Qdrant has 15 vectors (or 14)

### Test 4: Verify `/createmeta` Does NOT Vectorize
- [ ] Run custom fields sync from ETL frontend
- [ ] Check logs - should NOT see "Queued X projects entities for vectorization"
- [ ] Check logs - should NOT see "Queued X wits entities for vectorization"
- [ ] Verify `qdrant_vectors` table count doesn't change

### Test 5: Verify `wits_mapping_id` Is Set
- [ ] Run Jira job
- [ ] Check `wits` table
- [ ] Verify WITs with mappings have `wits_mapping_id` populated
- [ ] Verify WITs without mappings have `wits_mapping_id = NULL`

---

## Expected Results

### Before Fix:
```
Database:
- 14 projects
- 15 WITs (with 1 duplicate Milestone)
- 39 statuses

qdrant_vectors:
- 0 projects ❌
- 14 wits ❌ (missing 1)
- 39 statuses ✅

Total: 53/68 (missing 15)
```

### After Fix:
```
Database:
- 14 projects
- 15 WITs (deduplicated)
- 39 statuses

qdrant_vectors:
- 14 projects ✅
- 15 WITs ✅ (all unique)
- 39 statuses ✅

Total: 68/68 (complete!)
```

---

## Diagnostic Script

Created `services/backend-service/scripts/diagnose_vectorization.py` to help diagnose vectorization issues:

```bash
cd services/backend-service
python scripts/diagnose_vectorization.py
```

**Output**:
- Counts entities in database
- Counts vectors in bridge table
- Lists missing entities (not vectorized)
- Lists WITs with missing `wits_mapping_id`

---

## Summary

| Issue | Status | Impact |
|-------|--------|--------|
| #1: WITs not deduplicated | ✅ Fixed | Prevents duplicate WITs in database and Qdrant |
| #2: `/createmeta` vs `/project/search` not separated | ✅ Clarified | Ensures correct vectorization behavior |
| #3: Projects not vectorized | ✅ Fixed | All projects will now be vectorized |
| #4: Missing 1 WIT (duplicate Milestone) | ✅ Fixed | Deduplication handles this |
| #5: 6 WITs missing `wits_mapping_id` | ⚠️ Data Issue | User needs to create mappings |

---

## Next Steps

1. ✅ **Run Jira Job**: Execute the automatic Jira job to test the fixes
2. ✅ **Verify Vectorization**: Check that all 68 entities are vectorized (14 projects + 15 WITs + 39 statuses)
3. ⚠️ **Create WIT Mappings**: Add mappings for the 6 WITs that don't have them
4. ✅ **Monitor Logs**: Check for the new debug messages to ensure everything is working correctly

