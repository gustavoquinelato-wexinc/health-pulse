# Vectorization Strategy & Multi-Agent Architecture

## Question 1: Are we vectorizing all columns?

### Current State (After Fixes)

#### Projects
**Database Columns**:
- `id`, `external_id`, `key`, `name`, `project_type`, `integration_id`, `tenant_id`, `active`, `created_at`, `last_updated_at`

**Vectorized Fields**:
```python
{
    "external_id": entity.external_id or "",
    "key": entity.key or "",
    "name": entity.name or "",
    "project_type": entity.project_type or ""
}
```

**Text Content for Embedding**:
```
"Key: BEN | Name: Benefits Platform | Type: software | ID: 10000"
```

**Missing from Vectorization**: None - all meaningful fields are vectorized

---

#### Statuses
**Database Columns**:
- `id`, `external_id`, `original_name`, `status_mapping_id`, `category`, `description`, `integration_id`, `tenant_id`, `active`, `created_at`, `last_updated_at`

**Vectorized Fields**:
```python
{
    "external_id": entity.external_id or "",
    "original_name": entity.original_name or "",
    "description": entity.description or "",
    "category": entity.category or ""
}
```

**Text Content for Embedding**:
```
"Name: In Progress | Category: indeterminate | Description: Work is in progress"
```

**Missing from Vectorization**: `status_mapping_id` (internal reference, not meaningful for semantic search)

---

#### Work Item Types (WITs)
**Database Columns**:
- `id`, `external_id`, `original_name`, `wits_mapping_id`, `description`, `hierarchy_level`, `integration_id`, `tenant_id`, `active`, `created_at`, `last_updated_at`

**Vectorized Fields**:
```python
{
    "external_id": entity.external_id or "",
    "original_name": entity.original_name or "",
    "description": entity.description or "",
    "hierarchy_level": entity.hierarchy_level or 0
}
```

**Text Content for Embedding**:
```
"Name: Epic | Description: A big user story that needs to be broken down | Level: 1"
```

**Missing from Vectorization**: `wits_mapping_id` (internal reference, not meaningful for semantic search)

---

### Summary: What's Vectorized vs What's Not

| Entity Type | Total Columns | Vectorized | Not Vectorized | Reason for Exclusion |
|-------------|---------------|------------|----------------|---------------------|
| **Projects** | 10 | 4 | 6 | IDs, timestamps, flags (not semantic) |
| **Statuses** | 11 | 4 | 7 | IDs, timestamps, flags (not semantic) |
| **WITs** | 11 | 4 | 7 | IDs, timestamps, flags (not semantic) |

**Excluded Fields (Common Pattern)**:
- `id` - Internal database ID
- `integration_id` - Foreign key reference
- `tenant_id` - Foreign key reference
- `active` - Boolean flag
- `created_at` - Timestamp
- `last_updated_at` - Timestamp
- `*_mapping_id` - Internal mapping references

**Why These Are Excluded**: These fields are for database operations, not semantic meaning. They're available in the metadata payload stored in Qdrant, but not used for embedding generation.

---

## Question 2: Will custom fields work with agent queries?

### Scenario
User asks agent: "Show me all high-priority bugs assigned to John in the Benefits project that have custom field X = Y"

### Current Architecture

#### Work Items Table Structure
```sql
CREATE TABLE work_items (
    -- Standard fields
    id, external_id, key, project_id, team, summary, description,
    acceptance_criteria, wit_id, status_id, resolution, story_points,
    assignee, labels, priority, parent_external_id,
    
    -- 20 dedicated custom field columns
    custom_field_1, custom_field_2, ..., custom_field_20,
    
    -- Overflow for additional custom fields
    custom_fields_overflow JSONB,
    
    -- Timestamps
    created, updated, work_first_committed_at, ...
)
```

#### Custom Fields Mapping Table
```sql
CREATE TABLE custom_fields (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR,
    field_name VARCHAR,
    field_type VARCHAR,
    description TEXT,
    integration_id INTEGER,
    tenant_id INTEGER
)
```

### The Problem

**Current Vectorization**: Work items are vectorized with standard fields only:
```python
{
    "key": "BEN-123",
    "summary": "Fix login bug",
    "description": "Users cannot login...",
    "status_name": "In Progress",
    "assignee": "John Doe",
    "priority": "High"
}
```

**Missing**: Custom field values are NOT included in the embedding!

### The Solution: Multi-Agent Architecture

#### Phase 1: Hybrid Retrieval (Current State)
```
User Query → Orchestrator Agent
    ↓
    ├─→ Vector Search (semantic similarity)
    │   └─→ Finds: "bugs", "login", "John", "Benefits"
    │
    └─→ SQL Filter (exact matches)
        └─→ Filters: priority='High', custom_field_X='Y'
```

**How It Works**:
1. **Vector Search**: Finds semantically similar work items based on summary/description
2. **SQL Post-Filter**: Applies exact filters on custom fields, priority, assignee, etc.
3. **Combine Results**: Returns work items that match both semantic AND exact criteria

**Advantages**:
- ✅ Works with ANY custom field (no need to re-vectorize)
- ✅ Exact matching on custom fields
- ✅ Fast SQL queries on indexed columns

**Limitations**:
- ❌ Cannot do semantic search on custom field VALUES
- ❌ Example: "Find items where custom_field_notes mentions 'security concern'" won't work

---

#### Phase 2: Enhanced Vectorization (Future State)

**Option A: Include Custom Fields in Embeddings**
```python
# Vectorize work items with custom fields
{
    "key": "BEN-123",
    "summary": "Fix login bug",
    "description": "Users cannot login...",
    "priority": "High",
    "assignee": "John Doe",
    "custom_field_1": "Security",
    "custom_field_2": "Q1 2025",
    "custom_field_notes": "This is a critical security issue affecting all users"
}
```

**Advantages**:
- ✅ Semantic search on custom field values
- ✅ Agent can understand context from custom fields

**Challenges**:
- ❌ Need to re-vectorize when custom fields change
- ❌ Embedding size increases
- ❌ Different tenants have different custom fields

---

**Option B: Separate Custom Field Vectors**
```
Collection: tenant_1_work_items
    └─→ Standard fields only

Collection: tenant_1_work_items_custom_fields
    └─→ Custom field values only
```

**Advantages**:
- ✅ Flexible - can vectorize only text custom fields
- ✅ No need to re-vectorize standard fields
- ✅ Can handle tenant-specific custom fields

**Challenges**:
- ❌ More complex queries (need to search both collections)
- ❌ Need to join results

---

**Option C: Metadata-Based Filtering (Recommended)**
```python
# Store custom fields in Qdrant metadata
vector_data = {
    'id': 'BEN-123',
    'vector': embedding,  # From standard fields only
    'payload': {
        'key': 'BEN-123',
        'summary': 'Fix login bug',
        'priority': 'High',
        'assignee': 'John Doe',
        # Custom fields in metadata
        'custom_fields': {
            'security_level': 'Critical',
            'target_release': 'Q1 2025',
            'notes': 'This is a critical security issue'
        }
    }
}
```

**Query Pattern**:
```python
# Qdrant supports filtering on metadata
results = qdrant_client.search(
    collection_name="tenant_1_work_items",
    query_vector=embedding,
    query_filter={
        "must": [
            {"key": "priority", "match": {"value": "High"}},
            {"key": "custom_fields.security_level", "match": {"value": "Critical"}}
        ]
    }
)
```

**Advantages**:
- ✅ Semantic search on standard fields
- ✅ Exact filtering on custom fields
- ✅ No need to re-vectorize
- ✅ Qdrant handles the filtering efficiently

**This is the RECOMMENDED approach!**

---

### Multi-Agent Query Flow (Recommended)

```
User: "Show me high-priority bugs in Benefits with security_level=Critical"
    ↓
Orchestrator Agent
    ↓
    ├─→ Parse Query
    │   ├─ Semantic: "bugs", "Benefits"
    │   └─ Filters: priority="High", custom_fields.security_level="Critical"
    │
    ├─→ Route to Jira Agent
    │   └─→ Qdrant Vector Search with Metadata Filters
    │       └─→ Returns: BEN-123, BEN-456
    │
    └─→ Enrich with Database Data
        └─→ SQL JOIN to get full work item details + custom fields
        └─→ Returns: Complete work item objects
```

---

## Recommendations

### Immediate (Phase 1)
1. ✅ **Fixed**: Vectorize all meaningful fields for projects, statuses, wits
2. ✅ **Fixed**: Store metadata in Qdrant payload
3. 🔄 **TODO**: Implement Qdrant metadata filtering in agent queries
4. 🔄 **TODO**: Store custom field values in Qdrant metadata payload

### Short-term (Phase 2)
1. 🔄 **TODO**: Implement hybrid search (vector + metadata filters)
2. 🔄 **TODO**: Add custom field values to work item vectorization metadata
3. 🔄 **TODO**: Test agent queries with custom field filters

### Long-term (Phase 3)
1. 🔄 **TODO**: Evaluate if semantic search on custom field VALUES is needed
2. 🔄 **TODO**: If yes, implement Option C (metadata-based filtering)
3. 🔄 **TODO**: Monitor query performance and optimize

---

## Answer to Your Questions

### Q1: Are we vectorizing all columns?
**Answer**: We're vectorizing all **meaningful** columns (names, descriptions, types, categories). We're NOT vectorizing:
- Internal IDs (id, integration_id, tenant_id)
- Timestamps (created_at, last_updated_at)
- Boolean flags (active)
- Mapping references (*_mapping_id)

These are stored in Qdrant metadata but not used for embedding generation.

### Q2: Will custom fields work with agent queries?
**Answer**: YES, but with the right architecture:

**Current State**: Custom fields can be used for EXACT filtering via SQL post-processing

**Recommended State**: Store custom fields in Qdrant metadata payload, use Qdrant's metadata filtering for hybrid search (semantic + exact filters)

**Future State**: If semantic search on custom field VALUES is needed, include them in embedding generation (but this requires re-vectorization when custom fields change)

**Best Practice**: Use Qdrant metadata filtering (Option C) - it gives you the best of both worlds without the complexity of re-vectorization.

