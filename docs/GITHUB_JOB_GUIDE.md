# GitHub Job Recovery and Checkpoint System Guide

## 📋 **Overview**

The GitHub ETL job implements a sophisticated multi-level checkpoint and recovery system that ensures no data loss during interruptions, rate limits, or failures. This guide covers the checkpoint architecture, recovery mechanisms, and troubleshooting procedures.

## 🏗️ **Checkpoint Architecture**

### **Multi-Level Checkpoint System**

The GitHub job uses a hierarchical checkpoint system with multiple levels of granularity:

```
Repository Level
├── PR Pagination Level (last_pr_cursor)
└── Individual PR Level (current_pr_node_id)
    ├── Commit Pagination (last_commit_cursor)
    ├── Review Pagination (last_review_cursor)
    ├── Comment Pagination (last_comment_cursor)
    └── Review Thread Pagination (last_review_thread_cursor)
```

### **Checkpoint Fields**

| Field | Purpose | Recovery Behavior |
|-------|---------|-------------------|
| `repo_processing_queue` | JSON array of repositories to process | Resume from unfinished repositories |
| `last_pr_cursor` | GraphQL cursor for PR pagination | Resume PR fetching from specific page |
| `current_pr_node_id` | Currently processing PR node ID | Resume nested processing for specific PR |
| `last_commit_cursor` | Cursor for commit pagination within PR | Resume commit fetching within PR |
| `last_review_cursor` | Cursor for review pagination within PR | Resume review fetching within PR |
| `last_comment_cursor` | Cursor for comment pagination within PR | Resume comment fetching within PR |
| `last_review_thread_cursor` | Cursor for review thread pagination | Resume review thread fetching within PR |

## 🔄 **Recovery Flow**

### **1. Job Startup Recovery Check**

```python
if job_schedule.is_recovery_run():
    logger.info("Recovery run detected - resuming from checkpoint")
    # Load checkpoint state and resume processing
else:
    logger.info("Normal run - starting fresh")
    # Start normal processing
```

### **2. Repository-Level Recovery**

- **Queue Management**: Resume from `repo_processing_queue`
- **Skip Completed**: Repositories marked as `finished: true` are skipped
- **Continue Processing**: Resume from first unfinished repository

### **3. PR-Level Recovery**

- **Cursor Resume**: Use `last_pr_cursor` to resume PR pagination
- **Early Termination**: Use `last_sync_at` timestamp for optimization
- **Nested Check**: Check for `current_pr_node_id` for interrupted PR processing

### **4. Nested Recovery (Within PR)**

If `current_pr_node_id` exists:
- **Find PR**: Locate the interrupted PR in database
- **Resume Commits**: If `last_commit_cursor` exists, resume commit pagination
- **Resume Reviews**: If `last_review_cursor` exists, resume review pagination
- **Resume Comments**: If `last_comment_cursor` exists, resume comment pagination
- **Resume Threads**: If `last_review_thread_cursor` exists, resume thread pagination

## 🚨 **Rate Limit Handling**

### **Rate Limit Detection**

```python
if graphql_client.is_rate_limited():
    # Save checkpoint immediately
    job_schedule.update_checkpoint({
        'last_pr_cursor': pr_cursor,
        'current_pr_node_id': current_pr_node_id,
        # ... other relevant cursors
    })
    # Return with rate_limit_reached: true
```

### **Checkpoint Save Points**

1. **Before API Requests**: Check rate limit before making requests
2. **On Rate Limit Hit**: Immediately save current state
3. **On Exceptions**: Save state in exception handlers
4. **On Nested Failures**: Save nested cursor data

### **Fast Retry Mechanism**

- **Automatic Scheduling**: Rate limit failures trigger fast retry scheduling
- **Shorter Intervals**: Retry jobs run at 5-30 minute intervals instead of 60 minutes
- **State Preservation**: All checkpoint data is maintained across retries

## 🛠️ **Troubleshooting**

### **Common Issues**

#### **Missing PRs After Interruption**

**Symptoms**: Repository shows fewer PRs in database than in GitHub
**Cause**: Checkpoint not properly saved during rate limit
**Solution**: Fixed in 2025-07-22 update - checkpoint data now properly returned in exception handlers

#### **Nested Data Incomplete**

**Symptoms**: PR exists but missing commits/reviews/comments
**Cause**: Interruption during nested pagination without checkpoint save
**Solution**: Enhanced nested checkpoint system saves state at all levels

#### **Recovery Not Working**

**Symptoms**: Job restarts from beginning instead of resuming
**Cause**: Checkpoint data not properly saved or retrieved
**Diagnosis**: Check `job_schedules` table for checkpoint fields

### **Diagnostic Commands**

```sql
-- Check current checkpoint state
SELECT job_name, status, last_pr_cursor, current_pr_node_id, 
       last_commit_cursor, last_review_cursor, last_comment_cursor
FROM job_schedules 
WHERE job_name = 'github_sync';

-- Check repository queue
SELECT repo_processing_queue 
FROM job_schedules 
WHERE job_name = 'github_sync';

-- Check PR counts for specific repository
SELECT COUNT(*) as pr_count 
FROM pull_requests pr
JOIN repositories r ON pr.repository_id = r.id
WHERE r.name = 'your-repo-name';
```

### **Manual Recovery**

If automatic recovery fails:

1. **Check Job Status**: Verify job is in PENDING state with checkpoint data
2. **Validate Cursors**: Ensure cursor values are valid GraphQL cursors
3. **Clear Checkpoints**: If corrupted, clear checkpoint fields to restart
4. **Monitor Logs**: Watch for checkpoint save/load messages during execution

## 📊 **Monitoring and Logging**

### **Key Log Messages**

- `"Resuming PR processing from cursor: {cursor}"` - PR-level recovery
- `"Resuming nested pagination for PR: {pr_node_id}"` - Nested recovery
- `"Rate limit checkpoint saved: cursor={cursor}"` - Rate limit handling
- `"Saved nested pagination checkpoint for PR {pr_id}"` - Nested checkpoint save

### **Performance Metrics**

- **Recovery Success Rate**: Percentage of successful recoveries
- **Data Completeness**: Comparison of GitHub vs database counts
- **Checkpoint Frequency**: How often checkpoints are saved
- **Recovery Time**: Time to resume from checkpoint

## 🔧 **Recent Improvements (2025-07-22)**

### **Critical Fixes Applied**

1. **Exception Handler Fix**: Rate limit exceptions now properly return checkpoint data
2. **Nested Checkpoint Enhancement**: All nested pagination levels now save checkpoints
3. **Immediate Saves**: Checkpoints saved immediately when failures occur
4. **Complete State Tracking**: Enhanced tracking of current processing state

### **Before vs After**

**Before**: 
- Rate limit exceptions returned empty checkpoint data
- Nested failures didn't save state
- Recovery gaps caused missing data

**After**:
- All exceptions properly preserve checkpoint state
- Multi-level checkpoint saves at every failure point
- Complete recovery with no data loss

## 📚 **Related Documentation**

- [Agent Guidance](AGENT_GUIDANCE.md) - Overall development guidelines
- [Architecture](ARCHITECTURE.md) - System architecture overview
- [Migration Guide](MIGRATION_GUIDE.md) - Database migration procedures
