# ETL Recovery Strategy

## 🎯 Recovery Philosophy

The Pulse Platform ETL system is designed with **"Fail Fast, Recover Precisely"** philosophy:

- **Immediate Failure Detection**: Quick identification of issues
- **Precise Recovery Points**: Resume exactly where failure occurred
- **Data Integrity**: No data loss or duplication during recovery
- **Graceful Degradation**: Continue processing other jobs when one fails
- **Transparent Recovery**: Clear visibility into recovery process

## 🔄 Recovery Models by Integration

### **Jira Integration Recovery**

#### **Strategy: Checkpoint-Based Recovery**
```python
# Recovery Pattern
if failure_detected:
    save_current_state()
    mark_job_as_failed()
    # Next run: resume from last successful checkpoint
```

#### **Recovery Rules**
1. **Complete Restart**: Jira jobs restart from beginning on failure
2. **Saved Items Reprocessed**: Previously saved items are reprocessed (idempotent)
3. **No Partial State**: Clean slate approach for data consistency
4. **Fast Recovery**: Optimized for quick restart and completion

#### **Checkpoint Data**
```json
{
  "last_sync_at": "2025-01-16T10:30:00Z",
  "total_issues_processed": 1250,
  "current_project": "PROJ-123",
  "error_message": "Rate limit exceeded"
}
```

### **GitHub Integration Recovery**

#### **Strategy: Cursor-Based Recovery**
```python
# Recovery Pattern
if failure_detected:
    save_cursor_position()
    save_repository_queue_state()
    mark_job_as_pending()  # Ready for immediate resume
```

#### **Recovery Rules**
1. **Precise Resume**: Resume from exact failure point using GraphQL cursors
2. **Repository Queue**: Track which repositories are finished/pending
3. **Cursor Preservation**: Save GraphQL pagination cursors for each repository
4. **Incremental Progress**: Never lose progress on completed repositories

#### **Checkpoint Data**
```json
{
  "repo_processing_queue": [
    {"name": "repo1", "finished": true},
    {"name": "repo2", "finished": false, "cursor": "Y3Vyc29yOjE="}
  ],
  "last_repo_sync_checkpoint": "repo2",
  "github_pr_cursor": "Y3Vyc29yOjE=",
  "total_prs_processed": 450
}
```

## 🛡️ Recovery Triggers

### **Automatic Recovery Triggers**
1. **Rate Limit Exceeded**: Graceful stop with immediate recovery readiness
2. **Network Timeout**: Retry with exponential backoff
3. **API Errors**: Temporary failures trigger recovery mode
4. **Resource Exhaustion**: Memory/CPU limits trigger graceful shutdown

### **Manual Recovery Triggers**
1. **Force Stop**: User-initiated job termination
2. **System Maintenance**: Planned downtime recovery
3. **Configuration Changes**: Recovery after settings update
4. **Data Corruption**: Manual intervention and recovery

## 📊 Recovery States and Transitions

### **Job Status Flow**
```
NOT_STARTED → PENDING → RUNNING → [FAILURE] → PENDING (Recovery Ready)
                                → [SUCCESS] → FINISHED
                                → [PAUSED] → PAUSED (Manual Control)
```

### **Recovery State Machine**
```
RUNNING → FAILURE_DETECTED → CHECKPOINT_SAVED → PENDING → RECOVERY_READY
```

## 🔧 Recovery Implementation

### **1. Checkpoint Management**

#### **Save Checkpoint**
```python
def save_checkpoint(job_id: str, checkpoint_data: dict):
    """Save recovery checkpoint with timestamp"""
    job = session.query(JobSchedule).filter_by(id=job_id).first()
    job.checkpoint_data = checkpoint_data
    job.last_checkpoint_at = datetime.utcnow()
    session.commit()
```

#### **Load Checkpoint**
```python
def load_checkpoint(job_id: str) -> dict:
    """Load recovery checkpoint data"""
    job = session.query(JobSchedule).filter_by(id=job_id).first()
    return job.checkpoint_data or {}
```

### **2. Recovery Detection**

#### **Automatic Recovery Detection**
```python
def detect_recovery_needed(job: JobSchedule) -> bool:
    """Detect if job needs recovery"""
    return (
        job.status == 'PENDING' and 
        job.checkpoint_data is not None and
        job.last_checkpoint_at is not None
    )
```

### **3. Recovery Execution**

#### **Jira Recovery**
```python
def recover_jira_job(job: JobSchedule):
    """Recover Jira job from checkpoint"""
    logger.info("Jira recovery: Complete restart with saved state reference")
    # Clear previous checkpoint for fresh start
    job.checkpoint_data = None
    # Restart extraction from beginning
    return extract_jira_data(full_refresh=True)
```

#### **GitHub Recovery**
```python
def recover_github_job(job: JobSchedule):
    """Recover GitHub job from precise checkpoint"""
    checkpoint = job.checkpoint_data
    logger.info(f"GitHub recovery: Resuming from {checkpoint.get('last_repo_sync_checkpoint')}")
    
    # Resume from exact repository and cursor position
    return extract_github_data(
        resume_from_repo=checkpoint.get('last_repo_sync_checkpoint'),
        cursor=checkpoint.get('github_pr_cursor'),
        repo_queue=checkpoint.get('repo_processing_queue', [])
    )
```

## 🚨 Failure Scenarios and Recovery

### **Scenario 1: Rate Limit Exceeded**

#### **Jira Rate Limit**
```
1. Detect rate limit → Save current progress → Set status to FINISHED
2. Next scheduled run → Start fresh with rate limit reset
3. Reprocess all items (idempotent operations)
```

#### **GitHub Rate Limit**
```
1. Detect rate limit → Save cursor and queue state → Set status to PENDING
2. Manual/automatic retry → Resume from exact cursor position
3. Continue processing remaining repositories
```

### **Scenario 2: Network Failure**

#### **Temporary Network Issues**
```
1. Retry with exponential backoff (3 attempts)
2. If all retries fail → Save checkpoint → Mark as PENDING
3. Next run → Resume from checkpoint
```

#### **Extended Network Outage**
```
1. Immediate checkpoint save
2. Graceful job termination
3. Status set to PENDING for later recovery
4. Alert administrators
```

### **Scenario 3: Data Validation Failure**

#### **Invalid Data Detected**
```
1. Log validation error with details
2. Skip invalid record (continue processing)
3. Save checkpoint with error count
4. Complete job with warnings
```

#### **Critical Data Corruption**
```
1. Immediate job termination
2. Save checkpoint with error details
3. Set status to FAILED
4. Require manual intervention
```

## 📈 Recovery Metrics and Monitoring

### **Recovery Success Metrics**
- **Recovery Time**: Time from failure to successful resume
- **Data Consistency**: Verification of no data loss/duplication
- **Recovery Rate**: Percentage of successful recoveries
- **Checkpoint Frequency**: How often checkpoints are saved

### **Recovery Monitoring**
```python
# Recovery monitoring example
recovery_metrics = {
    "total_recoveries": 45,
    "successful_recoveries": 43,
    "average_recovery_time": "2.3 minutes",
    "data_consistency_rate": "100%"
}
```

## 🔍 Recovery Testing

### **Recovery Test Scenarios**
1. **Simulated Rate Limits**: Test graceful rate limit handling
2. **Network Interruption**: Test network failure recovery
3. **Process Termination**: Test unexpected shutdown recovery
4. **Data Corruption**: Test invalid data handling
5. **Resource Exhaustion**: Test memory/CPU limit recovery

### **Recovery Validation**
```python
def validate_recovery(job_id: str, pre_failure_state: dict, post_recovery_state: dict):
    """Validate successful recovery"""
    assert post_recovery_state['processed_count'] >= pre_failure_state['processed_count']
    assert no_data_duplication(job_id)
    assert data_integrity_maintained(job_id)
```

## 🎯 Recovery Best Practices

### **Design Principles**
1. **Idempotent Operations**: All data operations can be safely repeated
2. **Atomic Transactions**: Use database transactions for consistency
3. **Checkpoint Frequency**: Balance between performance and recovery granularity
4. **Error Context**: Capture sufficient context for debugging
5. **Recovery Testing**: Regular testing of recovery scenarios

### **Implementation Guidelines**
1. **Save Early, Save Often**: Checkpoint at logical boundaries
2. **Validate Checkpoints**: Ensure checkpoint data is complete and valid
3. **Monitor Recovery**: Track recovery success rates and performance
4. **Document Failures**: Comprehensive logging for post-mortem analysis
5. **Graceful Degradation**: Continue other jobs when one fails

This recovery strategy ensures robust, reliable ETL operations with minimal data loss and maximum system availability.
