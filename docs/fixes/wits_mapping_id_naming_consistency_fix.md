# Wits Mapping ID Naming Consistency Fix

## Issue

**Problem**: Inconsistent naming between database column and Python model attribute caused `AttributeError` when running Jira job the second time.

**Error Message**:
```
AttributeError: 'Wit' object has no attribute 'wits_mapping_id'. Did you mean: 'wit_mapping_id'?
```

**Root Cause**: The database column is named `wits_mapping_id` (plural), but the Python model attribute was named `wit_mapping_id` (singular).

---

## Database Schema Analysis

### Database Column Names (from migration)

```sql
-- wits table
CREATE TABLE IF NOT EXISTS wits (
    id SERIAL,
    external_id VARCHAR,
    original_name VARCHAR NOT NULL,
    wits_mapping_id INTEGER,  -- ✅ PLURAL
    description VARCHAR,
    hierarchy_level INTEGER NOT NULL,
    ...
);

-- statuses table
CREATE TABLE IF NOT EXISTS statuses (
    id SERIAL,
    external_id VARCHAR,
    original_name VARCHAR NOT NULL,
    status_mapping_id INTEGER,  -- ✅ SINGULAR
    category VARCHAR NOT NULL,
    ...
);

-- wits_mappings table
CREATE TABLE IF NOT EXISTS wits_mappings (
    id SERIAL,
    wit_from VARCHAR NOT NULL,
    wit_to VARCHAR NOT NULL,
    wits_hierarchy_id INTEGER NOT NULL,  -- ✅ PLURAL
    ...
);
```

**Pattern**: The database uses **plural** naming for `wits_*` tables and **singular** for `status_*` tables.

---

## Python Model Analysis (Before Fix)

### Wit Model (INCONSISTENT ❌)
```python
class Wit(Base, IntegrationBaseEntity):
    __tablename__ = 'wits'
    
    wit_mapping_id = Column(Integer, ForeignKey('wits_mappings.id'), 
                           quote=False, nullable=True, 
                           name="wits_mapping_id")  # ❌ Python: singular, DB: plural
```

### Status Model (CONSISTENT ✅)
```python
class Status(Base, IntegrationBaseEntity):
    __tablename__ = 'statuses'
    
    status_mapping_id = Column(Integer, ForeignKey('status_mappings.id'), 
                              quote=False, nullable=True, 
                              name="status_mapping_id")  # ✅ Both singular
```

### WitMapping Model (CONSISTENT ✅)
```python
class WitMapping(Base, IntegrationBaseEntity):
    __tablename__ = 'wits_mappings'
    
    wits_hierarchy_id = Column(Integer, ForeignKey('wits_hierarchies.id'), 
                              quote=False, nullable=False, 
                              name="wits_hierarchy_id")  # ✅ Both plural
```

---

## The Fix

### Principle
**Code should match database column names** to avoid confusion for future maintainers.

Since the database column is `wits_mapping_id`, the Python attribute should also be `wits_mapping_id`.

---

## Files Modified

### 1. `services/backend-service/app/models/unified_models.py`

**Before** (line 383):
```python
wit_mapping_id = Column(Integer, ForeignKey('wits_mappings.id'), 
                       quote=False, nullable=True, 
                       name="wits_mapping_id")
```

**After** (line 383):
```python
wits_mapping_id = Column(Integer, ForeignKey('wits_mappings.id'), 
                        quote=False, nullable=True, 
                        name="wits_mapping_id")
```

**Change**: Python attribute renamed from `wit_mapping_id` to `wits_mapping_id` to match database column.

---

### 2. `services/backend-service/app/etl/wits.py`

**Before** (line 667):
```python
dependent_wits = session.query(Wit).filter(
    Wit.wit_mapping_id == mapping_id,  # ❌ Old singular name
    Wit.active == True
).count()
```

**After** (line 667):
```python
dependent_wits = session.query(Wit).filter(
    Wit.wits_mapping_id == mapping_id,  # ✅ New plural name
    Wit.active == True
).count()
```

**Change**: Updated query to use `wits_mapping_id` instead of `wit_mapping_id`.

---

### 3. `services/backend-service/app/workers/transform_worker.py`

**No changes needed** - This file was already using `wits_mapping_id` correctly in:
- Line 324: SQL query selecting `wits_mapping_id`
- Line 367: Variable assignment `wits_mapping_id = wits_mapping_lookup.get(original_name)`
- Line 385: Dictionary key `'wits_mapping_id': wits_mapping_id`
- Line 394: Dictionary key `'wits_mapping_id': wits_mapping_id`
- Line 403: SQL INSERT column `wits_mapping_id`
- Line 418: SQL UPDATE column `wits_mapping_id`
- Line 642: Variable assignment `wits_mapping_id = self._lookup_wit_mapping_id(wit_name, tenant_id)`
- Line 650: Object attribute `existing_wit.wits_mapping_id`
- Line 657: Dictionary key `'wits_mapping_id': wits_mapping_id`
- Line 668: Dictionary key `'wits_mapping_id': wits_mapping_id`
- Line 1175: Variable assignment `wits_mapping_id = self._lookup_wit_mapping_id(wit_name, tenant_id)`
- Line 1189: Object attribute `existing_wit.wits_mapping_id`
- Line 1197: Dictionary key `'wits_mapping_id': wits_mapping_id`
- Line 1210: Dictionary key `'wits_mapping_id': wits_mapping_id`
- Line 1225: Function name `_lookup_wit_mapping_id`

---

## Verification Checklist

### ✅ Database Schema
- [x] `wits` table has column `wits_mapping_id` (plural)
- [x] `statuses` table has column `status_mapping_id` (singular)
- [x] `wits_mappings` table has column `wits_hierarchy_id` (plural)
- [x] No migration changes needed

### ✅ Python Models
- [x] `Wit.wits_mapping_id` matches database column `wits_mapping_id`
- [x] `Status.status_mapping_id` matches database column `status_mapping_id`
- [x] `WitMapping.wits_hierarchy_id` matches database column `wits_hierarchy_id`

### ✅ Code References
- [x] `services/backend-service/app/models/unified_models.py` - Fixed
- [x] `services/backend-service/app/etl/wits.py` - Fixed
- [x] `services/backend-service/app/workers/transform_worker.py` - Already correct
- [x] `services/etl-service/*` - Skipped (deprecated)

---

## Testing

### Test 1: Run Jira Job First Time
```bash
# Should work - creates new WITs
curl -X POST http://localhost:3001/app/etl/jobs/1/run-now?tenant_id=1 \
  -H "X-Internal-Auth: your-secret-key"
```

**Expected**: ✅ Job completes successfully, WITs created with `wits_mapping_id` populated

### Test 2: Run Jira Job Second Time
```bash
# Should work - updates existing WITs
curl -X POST http://localhost:3001/app/etl/jobs/1/run-now?tenant_id=1 \
  -H "X-Internal-Auth: your-secret-key"
```

**Expected**: ✅ Job completes successfully, WITs updated (no AttributeError)

**Before Fix**: ❌ `AttributeError: 'Wit' object has no attribute 'wits_mapping_id'`

### Test 3: Check Database
```sql
-- Verify wits_mapping_id is populated
SELECT id, external_id, original_name, wits_mapping_id 
FROM wits 
WHERE tenant_id = 1;
```

**Expected**: WITs with mappings have `wits_mapping_id` populated, others have NULL

---

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Database Column** | `wits_mapping_id` | `wits_mapping_id` (unchanged) |
| **Python Attribute** | `wit_mapping_id` ❌ | `wits_mapping_id` ✅ |
| **Consistency** | ❌ Mismatch | ✅ Match |
| **First Run** | ✅ Works | ✅ Works |
| **Second Run** | ❌ AttributeError | ✅ Works |

**Root Cause**: Python attribute name didn't match database column name

**Fix**: Renamed Python attribute to match database column name

**Impact**: 
- ✅ Jira job now works on subsequent runs
- ✅ Code is more maintainable (consistent naming)
- ✅ No database migration needed
- ✅ No changes to deprecated etl-service

---

## Lessons Learned

1. **Always match Python attribute names to database column names** - This avoids confusion and makes code more maintainable

2. **Use explicit `name=` parameter in SQLAlchemy Column definitions** - This makes the mapping clear:
   ```python
   # Good - explicit mapping
   wits_mapping_id = Column(Integer, name="wits_mapping_id")
   
   # Bad - implicit mapping (can cause confusion)
   wit_mapping_id = Column(Integer, name="wits_mapping_id")
   ```

3. **Check all related code when fixing naming issues** - Not just the model, but also:
   - API routes that query the model
   - Workers that process the data
   - Any raw SQL queries

4. **Test both INSERT and UPDATE paths** - The error only appeared on the second run (UPDATE path), not the first run (INSERT path)

