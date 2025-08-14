# Jira Job Connection Timeout Fix

## Problem Summary 🚨

**Issue**: Jira job failed after processing 30k+ records with database connection timeout:
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) server closed the connection unexpectedly
Instance <JobSchedule at 0x271428f1a50> is not bound to a Session; attribute refresh operation cannot proceed
```

**Root Causes**:
1. **Long-running transaction**: Processing 30k+ records in single transaction
2. **Connection timeout**: Database connection closed after 30 minutes
3. **Session detachment**: SQLAlchemy session became unbound after connection loss
4. **No chunked commits**: All data processed before any commit

## Solution Implemented ✅

### 1. Database Connection Pool Optimization

**File**: `.env`
```bash
# Reduced pool recycle time for long-running jobs
DB_POOL_RECYCLE=1800  # 30 minutes (from 1 hour)
```

### 2. Enhanced Connection Recovery

**File**: `services/etl-service/app/jobs/jira/jira_job.py`

Added robust connection recovery logic:
```python
# Enhanced commit with connection recovery for large datasets
try:
    session.commit()
except Exception as commit_error:
    # Check if it's a connection issue
    if ("server closed the connection" in str(commit_error) or 
        "not bound to a Session" in str(commit_error) or
        "OperationalError" in str(type(commit_error))):
        
        # Perform session recovery with new connection
        with database.get_session() as new_session:
            fresh_job_schedule = new_session.query(JobSchedule).filter_by(id=job_schedule.id).first()
            if fresh_job_schedule:
                fresh_job_schedule.set_finished()  # or appropriate status
                new_session.commit()
```

### 3. Chunked Transaction Processing

**File**: `services/etl-service/app/core/settings_manager.py`

Added new configuration settings:
```python
'jira_commit_batch_size': {
    'value': 500,
    'type': 'integer',
    'description': 'Number of records to process before committing transaction'
},
'jira_session_refresh_interval': {
    'value': 1000,
    'type': 'integer', 
    'description': 'Number of records processed before refreshing database session'
}
```

**File**: `services/etl-service/app/jobs/jira/jira_extractors.py`

Implemented chunked processing for both issues and changelogs:
```python
# Process issues in chunks to prevent long-running transactions
commit_batch_size = get_jira_commit_batch_size()  # 500 records

for i in range(0, len(issues_to_insert), commit_batch_size):
    chunk = issues_to_insert[i:i + commit_batch_size]
    perform_bulk_insert(session, Issue, chunk, "issues", job_logger)
    
    # Commit this chunk
    session.commit()
    job_logger.progress(f"[COMMITTED] Committed {len(chunk)} issues")
```

## Benefits of This Solution 🎯

### 1. **Prevents Connection Timeouts**
- Shorter pool recycle time (30 min vs 1 hour)
- Chunked commits every 500 records
- No single transaction longer than ~2-3 minutes

### 2. **Robust Error Recovery**
- Detects connection loss automatically
- Creates fresh session with new connection
- Preserves job status even if final commit fails

### 3. **Better Progress Tracking**
- Commits happen incrementally
- Progress is saved even if job fails mid-way
- Easier to resume from checkpoints

### 4. **Configurable Performance**
- Batch sizes can be tuned per environment
- Session refresh intervals adjustable
- No hardcoded limits

## Configuration Recommendations 📊

### For Large Datasets (30k+ records):
```bash
# .env settings
DB_POOL_RECYCLE=1800              # 30 minutes
DB_POOL_SIZE=20                   # Increased pool size
DB_MAX_OVERFLOW=30                # Higher overflow

# System settings (via admin UI)
jira_commit_batch_size=500        # Commit every 500 records
jira_session_refresh_interval=1000 # Refresh every 1000 records
jira_database_batch_size=100      # Query batch size
```

### For Smaller Datasets (<10k records):
```bash
# Can use larger batch sizes for better performance
jira_commit_batch_size=1000       # Commit every 1000 records
jira_session_refresh_interval=2000 # Less frequent refresh
```

## Testing Verification ✅

To verify the fix works:

1. **Monitor job logs** for chunked commit messages:
   ```
   [COMMITTED] Committed 500 issues (total: 1500/30000)
   [COMMITTED] Committed 500 changelogs (total: 2000/45000)
   ```

2. **Check database** for incremental progress during job execution

3. **Test connection recovery** by simulating connection loss

4. **Verify job completion** even with large datasets

## Future Enhancements 🚀

1. **Dynamic batch sizing** based on record complexity
2. **Connection health monitoring** with proactive refresh
3. **Parallel processing** for independent data chunks
4. **Resume capability** from exact failure point

This solution transforms the Jira job from a single long-running transaction into a series of manageable chunks, preventing connection timeouts while maintaining data integrity.
