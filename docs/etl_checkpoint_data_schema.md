# ETL Checkpoint Data Schema

**Purpose**: Generic JSONB column in `etl_jobs` table for job-specific recovery and state management.

---

## 🎯 Overview

The `checkpoint_data` column replaces all job-specific checkpoint columns with a flexible JSON structure that can accommodate any job type's recovery needs.

### **Benefits**
- ✅ No schema changes needed for new job types
- ✅ Each job can store exactly what it needs
- ✅ Easy to extend with new fields
- ✅ Supports complex nested data structures
- ✅ Enables precise recovery from interruptions

---

## 📋 Schema by Job Type

### **1. GitHub Job**

```json
{
  "last_pr_cursor": "Y3Vyc29yOnYyOpK5MjAyNC0wMS0xNVQxMjowMDowMFo=",
  "current_pr_node_id": "PR_kwDOABCDEF4",
  "last_commit_cursor": "abc123def456",
  "last_review_cursor": "review_cursor_789",
  "last_comment_cursor": "comment_cursor_012",
  "repositories_processed": ["repo1", "repo2"],
  "current_repository": "repo3",
  "batch_number": 5,
  "total_prs_processed": 150,
  "recovery_mode": true
}
```

**Field Descriptions**:
- `last_pr_cursor`: GitHub GraphQL cursor for PR pagination
- `current_pr_node_id`: Current PR being processed (for mid-PR recovery)
- `last_commit_cursor`: Cursor for commits within current PR
- `last_review_cursor`: Cursor for reviews within current PR
- `last_comment_cursor`: Cursor for comments within current PR
- `repositories_processed`: List of completed repositories
- `current_repository`: Repository currently being processed
- `batch_number`: Current batch number (for batched processing)
- `total_prs_processed`: Running count of PRs processed
- `recovery_mode`: Flag indicating recovery from interruption

**Usage Example**:
```python
# Save checkpoint during processing
checkpoint_data = {
    "last_pr_cursor": pr_cursor,
    "current_repository": repo_name,
    "batch_number": current_batch,
    "recovery_mode": False
}

await db.execute("""
    UPDATE etl_jobs 
    SET checkpoint_data = %s 
    WHERE id = %s
""", (json.dumps(checkpoint_data), job_id))

# Resume from checkpoint
job = await db.fetchone("SELECT * FROM etl_jobs WHERE id = %s", (job_id,))
checkpoint = job['checkpoint_data'] or {}

if checkpoint.get('recovery_mode'):
    # Resume from last cursor
    start_cursor = checkpoint.get('last_pr_cursor')
else:
    # Start fresh
    start_cursor = None
```

---

### **2. Jira Job**

```json
{
  "last_sync_date": "2025-01-15T12:00:00Z",
  "projects_processed": ["PROJ", "TEST"],
  "current_project": "DEMO",
  "last_issue_key": "DEMO-1234",
  "batch_number": 3,
  "total_issues_processed": 5000,
  "last_jql": "project = DEMO AND updated >= '2025-01-15 12:00'",
  "start_at": 100,
  "max_results": 100
}
```

**Field Descriptions**:
- `last_sync_date`: Last successful sync timestamp (ISO 8601)
- `projects_processed`: List of completed projects
- `current_project`: Project currently being processed
- `last_issue_key`: Last issue processed (for recovery)
- `batch_number`: Current batch number
- `total_issues_processed`: Running count
- `last_jql`: Last JQL query executed
- `start_at`: Jira pagination offset
- `max_results`: Jira pagination page size

**Usage Example**:
```python
# Incremental sync using checkpoint
job = await db.fetchone("SELECT * FROM etl_jobs WHERE job_name = 'Jira'")
checkpoint = job['checkpoint_data'] or {}

# Use last_sync_date for incremental sync
last_sync = checkpoint.get('last_sync_date', '1970-01-01T00:00:00Z')
jql = f"updated >= '{last_sync}' ORDER BY updated ASC"

# Process issues...

# Update checkpoint after successful batch
checkpoint_data = {
    "last_sync_date": datetime.utcnow().isoformat(),
    "total_issues_processed": checkpoint.get('total_issues_processed', 0) + len(issues),
    "last_issue_key": issues[-1]['key']
}

await db.execute("""
    UPDATE etl_jobs
    SET checkpoint_data = %s,
        last_run_finished_at = NOW()
    WHERE id = %s
""", (json.dumps(checkpoint_data), job_id))
```

---

### **3. WEX AD Job**

```json
{
  "last_sync_timestamp": "2025-01-15T12:00:00Z",
  "users_processed": 150,
  "groups_processed": 25,
  "last_user_id": "user_abc123",
  "last_group_id": "group_xyz789",
  "sync_type": "incremental",
  "delta_token": "abc123def456"
}
```

**Field Descriptions**:
- `last_sync_timestamp`: Last successful sync
- `users_processed`: Count of users synced
- `groups_processed`: Count of groups synced
- `last_user_id`: Last user processed (for pagination)
- `last_group_id`: Last group processed (for pagination)
- `sync_type`: `full` or `incremental`
- `delta_token`: AD delta query token for incremental sync

---

### **4. WEX Fabric Job**

```json
{
  "last_sync_timestamp": "2025-01-15T12:00:00Z",
  "datasets_processed": ["dataset1", "dataset2"],
  "current_dataset": "dataset3",
  "last_record_id": "rec_12345",
  "batch_number": 2,
  "total_records_processed": 10000,
  "workspace_id": "workspace_abc",
  "continuation_token": "token_xyz"
}
```

**Field Descriptions**:
- `last_sync_timestamp`: Last successful sync
- `datasets_processed`: List of completed datasets
- `current_dataset`: Dataset currently being processed
- `last_record_id`: Last record processed
- `batch_number`: Current batch number
- `total_records_processed`: Running count
- `workspace_id`: Fabric workspace identifier
- `continuation_token`: Fabric API continuation token

---

## 🔄 Common Patterns

### **Pattern 1: Incremental Sync with Timestamp**

```python
def get_sync_start_date(checkpoint_data: dict) -> str:
    """Get start date for incremental sync"""
    return checkpoint_data.get('last_sync_date', '1970-01-01T00:00:00Z')

def update_sync_checkpoint(job_id: int, new_timestamp: str):
    """Update checkpoint after successful sync"""
    await db.execute("""
        UPDATE etl_jobs 
        SET checkpoint_data = jsonb_set(
            COALESCE(checkpoint_data, '{}'),
            '{last_sync_date}',
            %s
        ),
        last_finished_at = NOW()
        WHERE id = %s
    """, (f'"{new_timestamp}"', job_id))
```

### **Pattern 2: Cursor-Based Pagination**

```python
def get_next_cursor(checkpoint_data: dict, entity_type: str) -> Optional[str]:
    """Get cursor for next page"""
    cursor_key = f"last_{entity_type}_cursor"
    return checkpoint_data.get(cursor_key)

def save_cursor(job_id: int, entity_type: str, cursor: str):
    """Save cursor for pagination"""
    cursor_key = f"last_{entity_type}_cursor"
    await db.execute("""
        UPDATE etl_jobs 
        SET checkpoint_data = jsonb_set(
            COALESCE(checkpoint_data, '{}'),
            %s,
            %s
        )
        WHERE id = %s
    """, (f'{{{cursor_key}}}', f'"{cursor}"', job_id))
```

### **Pattern 3: Batch Processing with Recovery**

```python
def get_batch_state(checkpoint_data: dict) -> dict:
    """Get current batch processing state"""
    return {
        'batch_number': checkpoint_data.get('batch_number', 1),
        'items_processed': checkpoint_data.get('total_items_processed', 0),
        'recovery_mode': checkpoint_data.get('recovery_mode', False)
    }

def save_batch_checkpoint(job_id: int, batch_number: int, items_processed: int):
    """Save batch processing checkpoint"""
    checkpoint_data = {
        'batch_number': batch_number,
        'total_items_processed': items_processed,
        'recovery_mode': False,
        'last_checkpoint_at': datetime.utcnow().isoformat()
    }
    
    await db.execute("""
        UPDATE etl_jobs 
        SET checkpoint_data = %s
        WHERE id = %s
    """, (json.dumps(checkpoint_data), job_id))
```

---

## 🛠️ PostgreSQL JSONB Operations

### **Update Specific Field**

```sql
-- Update single field
UPDATE etl_jobs 
SET checkpoint_data = jsonb_set(
    COALESCE(checkpoint_data, '{}'),
    '{last_sync_date}',
    '"2025-01-15T12:00:00Z"'
)
WHERE id = 1;
```

### **Append to Array**

```sql
-- Add repository to processed list
UPDATE etl_jobs 
SET checkpoint_data = jsonb_set(
    COALESCE(checkpoint_data, '{}'),
    '{repositories_processed}',
    COALESCE(checkpoint_data->'repositories_processed', '[]'::jsonb) || '"repo_new"'::jsonb
)
WHERE id = 1;
```

### **Increment Counter**

```sql
-- Increment total_issues_processed
UPDATE etl_jobs 
SET checkpoint_data = jsonb_set(
    COALESCE(checkpoint_data, '{}'),
    '{total_issues_processed}',
    to_jsonb(COALESCE((checkpoint_data->>'total_issues_processed')::int, 0) + 100)
)
WHERE id = 1;
```

### **Query by Checkpoint Field**

```sql
-- Find jobs in recovery mode
SELECT * FROM etl_jobs 
WHERE checkpoint_data->>'recovery_mode' = 'true';

-- Find jobs that processed specific repository
SELECT * FROM etl_jobs 
WHERE checkpoint_data->'repositories_processed' ? 'repo1';

-- Find jobs with batch_number > 5
SELECT * FROM etl_jobs 
WHERE (checkpoint_data->>'batch_number')::int > 5;
```

---

## ✅ Best Practices

1. **Always use COALESCE** when updating checkpoint_data to handle NULL values
2. **Store timestamps in ISO 8601 format** for consistency
3. **Include recovery_mode flag** to distinguish normal vs recovery runs
4. **Save checkpoints frequently** during long-running jobs
5. **Clear recovery flags** after successful completion
6. **Use typed fields** (don't mix strings and numbers for same field)
7. **Document your schema** in code comments
8. **Validate checkpoint data** before using it

---

## 🔍 Debugging

### **View Checkpoint Data**

```sql
-- Pretty print checkpoint data
SELECT 
    id,
    job_name,
    jsonb_pretty(checkpoint_data) as checkpoint
FROM etl_jobs
WHERE job_name = 'GitHub';
```

### **Reset Checkpoint**

```sql
-- Clear checkpoint data (start fresh)
UPDATE etl_jobs 
SET checkpoint_data = NULL,
    retry_count = 0,
    error_message = NULL
WHERE id = 1;
```

### **Validate Checkpoint Structure**

```python
def validate_checkpoint(checkpoint_data: dict, job_type: str) -> bool:
    """Validate checkpoint data structure"""
    required_fields = {
        'github': ['last_pr_cursor', 'current_repository'],
        'jira': ['last_sync_date', 'last_issue_key'],
        'wex_ad': ['last_sync_timestamp', 'delta_token'],
        'wex_fabric': ['last_sync_timestamp', 'workspace_id']
    }
    
    fields = required_fields.get(job_type.lower(), [])
    return all(field in checkpoint_data for field in fields)
```

---

**Last Updated**: 2025-10-02  
**Related Migration**: 0005_etl_jobs_autonomous_architecture

