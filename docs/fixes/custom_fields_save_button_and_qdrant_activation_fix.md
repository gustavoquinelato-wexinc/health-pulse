# Custom Fields Save Button & Qdrant Activation Fix

**Date**: 2025-10-11  
**Components**: ETL Frontend (Custom Fields Page), Backend Service (WITs & Statuses)

## Overview

Fixed two issues:
1. Moved "Save Mappings" button inside the table header (matching other mapping pages)
2. Fixed qdrant_vectors table not being updated when activating hierarchies/mappings/workflows

## Issue 1: Save Mappings Button Placement

### Problem
The "Save Mappings" button was positioned at the top of the page next to "Sync from Jira", which was inconsistent with other mapping pages that have action buttons inside the table header.

### Solution
Moved the "Save Mappings" button inside the table header, matching the pattern used in other mapping pages (WITs Mappings, Status Mappings, Workflows).

### Changes Made

**File**: `services/etl-frontend/src/pages/CustomFieldMappingPage.tsx`

**Before**:
```tsx
{/* Action Buttons */}
<div className="mb-6 flex justify-end space-x-3">
  <button onClick={syncCustomFields}>Sync from Jira</button>
  <button onClick={saveMappingConfig}>Save Mappings</button>
</div>

<div className="table-container">
  <div className="table-header">
    <h2>Custom Field Mappings</h2>
  </div>
  ...
</div>
```

**After**:
```tsx
{/* Sync from Jira Button */}
<div className="mb-6 flex justify-end">
  <button onClick={syncCustomFields}>Sync from Jira</button>
</div>

<div className="table-container">
  <div className="table-header flex justify-between">
    <div>
      <h2>Custom Field Mappings</h2>
      <p>Map Jira custom fields to work_items table columns...</p>
    </div>
    <button onClick={saveMappingConfig}>Save Mappings</button>
  </div>
  ...
</div>
```

**Button Styling**:
- Changed from `var(--gradient-1-2)` to `bg-blue-600 hover:bg-blue-700`
- Matches the "Create Mapping" buttons in other pages
- Consistent blue color scheme

## Issue 2: Qdrant Vectors Not Activated

### Problem
When deactivating a hierarchy/mapping/workflow, the corresponding record in the `qdrant_vectors` table was correctly set to `active = false`. However, when activating it again, the `qdrant_vectors` record remained inactive, causing the vector to not be used in AI queries.

### Root Cause
The update endpoints only updated `qdrant_vectors.active = false` when deactivating, but did not update it back to `true` when activating.

**Original Code Pattern**:
```python
if mapping_data.active is not None:
    mapping.active = mapping_data.active
    
    # If deactivating, also deactivate corresponding vectors
    if mapping_data.active is False:  # ← Only handles deactivation
        session.query(QdrantVector).filter(...).update({'active': False})
```

### Solution
Changed the logic to update `qdrant_vectors.active` for both activation and deactivation.

**Fixed Code Pattern**:
```python
if mapping_data.active is not None:
    mapping.active = mapping_data.active
    
    # Update corresponding vectors in qdrant_vectors
    session.query(QdrantVector).filter(...).update({
        'active': mapping_data.active,  # ← Now handles both true and false
        'last_updated_at': DateTimeHelper.now_default()
    })
```

### Files Modified

1. **`services/backend-service/app/etl/wits.py`**
   - Fixed `update_wit_hierarchy()` endpoint (line 265-276)
   - Fixed `update_wit_mapping()` endpoint (line 601-612)

2. **`services/backend-service/app/etl/statuses.py`**
   - Fixed `update_status_mapping()` endpoint (line 368-379)
   - Fixed `update_workflow()` endpoint (line 451-462)

### Affected Tables

All mapping tables now correctly sync their active state with qdrant_vectors:
- `wits_hierarchies` ↔ `qdrant_vectors` (table_name = 'wits_hierarchies')
- `wits_mappings` ↔ `qdrant_vectors` (table_name = 'wits_mappings')
- `statuses_mappings` ↔ `qdrant_vectors` (table_name = 'status_mappings')
- `workflows` ↔ `qdrant_vectors` (table_name = 'workflows')

## Testing

### Test Issue 1: Save Mappings Button

1. Navigate to Custom Fields page
2. Verify "Sync from Jira" button is at top-right (gradient style)
3. Verify "Save Mappings" button is inside table header (blue style)
4. Verify button placement matches other mapping pages
5. Click "Save Mappings" and verify it works

### Test Issue 2: Qdrant Activation

**Test Deactivation**:
1. Navigate to WITs Hierarchies page
2. Deactivate a hierarchy
3. Check database:
   ```sql
   SELECT active FROM wits_hierarchies WHERE id = X;  -- Should be false
   SELECT active FROM qdrant_vectors WHERE table_name = 'wits_hierarchies' AND record_id = X;  -- Should be false
   ```

**Test Activation** (the fix):
1. Activate the same hierarchy
2. Check database:
   ```sql
   SELECT active FROM wits_hierarchies WHERE id = X;  -- Should be true
   SELECT active FROM qdrant_vectors WHERE table_name = 'wits_hierarchies' AND record_id = X;  -- Should be true ✓
   ```

**Repeat for all mapping types**:
- WITs Mappings
- Status Mappings
- Workflows

## Database Impact

### Before Fix
```
wits_hierarchies:     active = true
qdrant_vectors:       active = false  ← Stuck inactive!
```
Result: Vector not used in AI queries even though hierarchy is active.

### After Fix
```
wits_hierarchies:     active = true
qdrant_vectors:       active = true   ← Correctly synced!
```
Result: Vector properly used in AI queries when hierarchy is active.

## AI Query Impact

### Before Fix
When a hierarchy was reactivated:
- ✅ Appeared in UI as active
- ✅ Used in ETL jobs
- ❌ **NOT** included in AI vector searches (qdrant_vectors.active = false)
- ❌ AI agents couldn't see the reactivated data

### After Fix
When a hierarchy is reactivated:
- ✅ Appears in UI as active
- ✅ Used in ETL jobs
- ✅ **Included** in AI vector searches (qdrant_vectors.active = true)
- ✅ AI agents can see the reactivated data

## Code Changes Summary

### Frontend Changes
**File**: `services/etl-frontend/src/pages/CustomFieldMappingPage.tsx`
- Removed "Save Mappings" from top action buttons
- Added "Save Mappings" to table header
- Changed button styling to match other pages

### Backend Changes

**File**: `services/backend-service/app/etl/wits.py`

**Line 265-276** (WIT Hierarchies):
```python
# Before
if hierarchy_update.active is False:
    session.query(QdrantVector).filter(...).update({'active': False})

# After
session.query(QdrantVector).filter(...).update({
    'active': hierarchy_update.active  # Handles both true and false
})
```

**Line 601-612** (WIT Mappings):
```python
# Before
if mapping_data.active is False:
    session.query(QdrantVector).filter(...).update({'active': False})

# After
session.query(QdrantVector).filter(...).update({
    'active': mapping_data.active  # Handles both true and false
})
```

**File**: `services/backend-service/app/etl/statuses.py`

**Line 368-379** (Status Mappings):
```python
# Before
if mapping_data.active is False:
    session.query(QdrantVector).filter(...).update({'active': False})

# After
session.query(QdrantVector).filter(...).update({
    'active': mapping_data.active  # Handles both true and false
})
```

**Line 451-462** (Workflows):
```python
# Before
if workflow_data.active is False:
    session.query(QdrantVector).filter(...).update({'active': False})

# After
session.query(QdrantVector).filter(...).update({
    'active': workflow_data.active  # Handles both true and false
})
```

## Benefits

✅ **Consistent UI** - Save button placement matches other mapping pages  
✅ **Correct Styling** - Blue button matches create/action buttons  
✅ **Fixed Activation** - Qdrant vectors properly activated/deactivated  
✅ **AI Query Accuracy** - AI agents see correct active/inactive data  
✅ **Data Integrity** - Main table and qdrant_vectors stay in sync  
✅ **Complete Coverage** - Fixed for all 4 mapping table types

## Migration Notes

**No migration required** - The fix is in the update logic. Existing inactive qdrant_vectors records will be fixed automatically when users activate the corresponding hierarchies/mappings/workflows through the UI.

If you want to fix existing records immediately, run:
```sql
-- Sync qdrant_vectors with main tables
UPDATE qdrant_vectors qv
SET active = h.active, last_updated_at = NOW()
FROM wits_hierarchies h
WHERE qv.table_name = 'wits_hierarchies' 
  AND qv.record_id = h.id 
  AND qv.active != h.active;

UPDATE qdrant_vectors qv
SET active = m.active, last_updated_at = NOW()
FROM wits_mappings m
WHERE qv.table_name = 'wits_mappings' 
  AND qv.record_id = m.id 
  AND qv.active != m.active;

UPDATE qdrant_vectors qv
SET active = sm.active, last_updated_at = NOW()
FROM statuses_mappings sm
WHERE qv.table_name = 'status_mappings' 
  AND qv.record_id = sm.id 
  AND qv.active != sm.active;

UPDATE qdrant_vectors qv
SET active = w.active, last_updated_at = NOW()
FROM workflows w
WHERE qv.table_name = 'workflows' 
  AND qv.record_id = w.id 
  AND qv.active != w.active;
```

