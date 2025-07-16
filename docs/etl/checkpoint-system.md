# ETL Checkpoint System

## 🎯 Checkpoint Philosophy

The Pulse Platform ETL system implements a sophisticated checkpoint system designed for **"Zero Data Loss, Precise Recovery"**:

- **Granular Checkpoints**: Save progress at logical boundaries
- **Cursor-Based Recovery**: Resume from exact failure points
- **State Preservation**: Maintain complete processing state
- **Idempotent Operations**: Safe to replay any checkpoint
- **Performance Optimized**: Minimal overhead during normal operations

## 🏗️ Checkpoint Architecture

### **Checkpoint Storage Model**

```python
class JobSchedule(BaseEntity):
    """Job schedule with checkpoint support"""
    
    # Core job information
    job_name: str
    status: JobStatus
    
    # Checkpoint data
    checkpoint_data: dict = None  # JSONB field for flexible checkpoint storage
    last_checkpoint_at: datetime = None
    
    # Recovery metadata
    retry_count: int = 0
    error_message: str = None
    
    def get_checkpoint_state(self) -> dict:
        """Get formatted checkpoint state for recovery"""
        return {
            "checkpoint_data": self.checkpoint_data or {},
            "last_checkpoint": self.last_checkpoint_at,
            "retry_count": self.retry_count,
            "error_context": self.error_message
        }
```

### **Checkpoint Data Structure**

#### **Jira Checkpoint Format**
```json
{
  "last_sync_at": "2025-01-16T10:30:00Z",
  "total_issues_processed": 1250,
  "current_project": "PROJ-123",
  "projects_completed": ["PROJ-001", "PROJ-002"],
  "extraction_phase": "issues",
  "error_context": {
    "last_successful_operation": "project_extraction",
    "failure_point": "issue_processing",
    "recoverable": true
  }
}
```

#### **GitHub Checkpoint Format**
```json
{
  "repo_processing_queue": [
    {
      "name": "wexinc/repo1",
      "finished": true,
      "last_cursor": null
    },
    {
      "name": "wexinc/repo2", 
      "finished": false,
      "last_cursor": "Y3Vyc29yOjE2NzM5NzI4MDA="
    }
  ],
  "last_repo_sync_checkpoint": "wexinc/repo2",
  "github_pr_cursor": "Y3Vyc29yOjE2NzM5NzI4MDA=",
  "total_prs_processed": 450,
  "current_phase": "pr_extraction",
  "rate_limit_context": {
    "remaining_calls": 30,
    "reset_time": "2025-01-16T11:00:00Z"
  }
}
```

## 🔄 Checkpoint Operations

### **1. Checkpoint Creation**

#### **Save Checkpoint**
```python
def save_checkpoint(job: JobSchedule, checkpoint_data: dict, phase: str = None):
    """Save checkpoint with metadata"""
    
    # Enhance checkpoint with metadata
    enhanced_checkpoint = {
        **checkpoint_data,
        "checkpoint_timestamp": datetime.utcnow().isoformat(),
        "checkpoint_phase": phase,
        "checkpoint_version": "1.0"
    }
    
    # Update job with checkpoint
    job.checkpoint_data = enhanced_checkpoint
    job.last_checkpoint_at = datetime.utcnow()
    
    session.commit()
    
    logger.info(f"Checkpoint saved for {job.job_name} at phase: {phase}")
```

#### **Checkpoint Triggers**
```python
# Automatic checkpoint triggers
CHECKPOINT_TRIGGERS = {
    "jira": [
        "project_completion",
        "issue_batch_completion", 
        "dev_status_completion",
        "error_occurrence"
    ],
    "github": [
        "repository_completion",
        "pr_batch_completion",
        "rate_limit_reached",
        "api_error_occurrence"
    ]
}
```

### **2. Checkpoint Recovery**

#### **Recovery Detection**
```python
def detect_recovery_scenario(job: JobSchedule) -> RecoveryType:
    """Detect what type of recovery is needed"""
    
    if not job.checkpoint_data:
        return RecoveryType.FRESH_START
    
    if job.status == 'PENDING' and job.checkpoint_data:
        return RecoveryType.CHECKPOINT_RESUME
    
    if job.retry_count > 0:
        return RecoveryType.RETRY_WITH_BACKOFF
    
    return RecoveryType.NORMAL_EXECUTION
```

#### **Recovery Execution**
```python
async def execute_recovery(job: JobSchedule, recovery_type: RecoveryType):
    """Execute appropriate recovery strategy"""
    
    if recovery_type == RecoveryType.CHECKPOINT_RESUME:
        logger.info(f"Recovery run detected - resuming from checkpoint")
        
        if job.job_name == 'jira_sync':
            return await recover_jira_job(job)
        elif job.job_name == 'github_sync':
            return await recover_github_job(job)
    
    elif recovery_type == RecoveryType.FRESH_START:
        logger.info(f"Fresh start - no checkpoint data found")
        return await execute_fresh_job(job)
```

## 🎯 Integration-Specific Checkpoints

### **Jira Checkpoint Strategy**

#### **Checkpoint Boundaries**
```python
# Jira checkpoint boundaries
JIRA_CHECKPOINT_BOUNDARIES = [
    "project_discovery_complete",
    "project_issues_complete", 
    "project_dev_status_complete",
    "user_extraction_complete",
    "data_transformation_complete"
]
```

#### **Jira Recovery Logic**
```python
def recover_jira_job(job: JobSchedule):
    """Recover Jira job - complete restart approach"""
    
    checkpoint = job.checkpoint_data
    
    # Jira uses complete restart for simplicity and data consistency
    logger.info("Jira recovery: Complete restart with reference to previous state")
    
    # Clear checkpoint for fresh start
    job.checkpoint_data = None
    session.commit()
    
    # Start fresh extraction (idempotent operations)
    return extract_jira_data(
        reference_checkpoint=checkpoint,  # For logging/analysis only
        full_refresh=True
    )
```

### **GitHub Checkpoint Strategy**

#### **Cursor-Based Checkpoints**
```python
# GitHub checkpoint boundaries
GITHUB_CHECKPOINT_BOUNDARIES = [
    "repository_discovery_complete",
    "repository_pr_extraction_complete",
    "repository_commit_extraction_complete", 
    "repository_review_extraction_complete",
    "pr_issue_linking_complete"
]
```

#### **GitHub Recovery Logic**
```python
def recover_github_job(job: JobSchedule):
    """Recover GitHub job - precise cursor-based resume"""
    
    checkpoint = job.checkpoint_data
    
    logger.info(f"GitHub recovery: Resuming from repository {checkpoint.get('last_repo_sync_checkpoint')}")
    
    # Resume from exact position
    return extract_github_data(
        repo_queue=checkpoint.get('repo_processing_queue', []),
        resume_from_repo=checkpoint.get('last_repo_sync_checkpoint'),
        pr_cursor=checkpoint.get('github_pr_cursor'),
        processed_count=checkpoint.get('total_prs_processed', 0)
    )
```

## 🛡️ Checkpoint Validation

### **Data Integrity Checks**

#### **Checkpoint Validation**
```python
def validate_checkpoint(checkpoint_data: dict, job_type: str) -> bool:
    """Validate checkpoint data integrity"""
    
    required_fields = {
        "jira": ["last_sync_at", "extraction_phase"],
        "github": ["repo_processing_queue", "last_repo_sync_checkpoint"]
    }
    
    job_required = required_fields.get(job_type, [])
    
    for field in job_required:
        if field not in checkpoint_data:
            logger.error(f"Invalid checkpoint: missing {field}")
            return False
    
    return True
```

#### **Recovery Validation**
```python
def validate_recovery_state(job: JobSchedule, pre_recovery_state: dict):
    """Validate successful recovery"""
    
    post_recovery_state = get_current_job_state(job)
    
    # Ensure no data loss
    assert post_recovery_state['processed_count'] >= pre_recovery_state['processed_count']
    
    # Ensure no duplication
    assert no_duplicate_records(job.job_name)
    
    # Ensure data consistency
    assert data_integrity_maintained(job.job_name)
    
    logger.info(f"Recovery validation passed for {job.job_name}")
```

## 📊 Checkpoint Performance

### **Performance Optimization**

#### **Checkpoint Frequency**
```python
# Optimized checkpoint frequency
CHECKPOINT_FREQUENCY = {
    "jira": {
        "issues": 100,      # Every 100 issues
        "projects": 1,      # Every project
        "time": 300         # Every 5 minutes
    },
    "github": {
        "repositories": 1,  # Every repository
        "prs": 50,         # Every 50 PRs
        "time": 180        # Every 3 minutes
    }
}
```

#### **Checkpoint Size Management**
```python
def optimize_checkpoint_size(checkpoint_data: dict) -> dict:
    """Optimize checkpoint data size"""
    
    # Remove unnecessary data
    optimized = {
        key: value for key, value in checkpoint_data.items()
        if key in ESSENTIAL_CHECKPOINT_FIELDS
    }
    
    # Compress large arrays
    if 'repo_processing_queue' in optimized:
        optimized['repo_processing_queue'] = compress_repo_queue(
            optimized['repo_processing_queue']
        )
    
    return optimized
```

## 🔍 Checkpoint Monitoring

### **Checkpoint Metrics**

```python
def get_checkpoint_metrics(job_name: str) -> dict:
    """Get checkpoint performance metrics"""
    
    return {
        "checkpoint_frequency": get_checkpoint_frequency(job_name),
        "average_checkpoint_size": get_average_checkpoint_size(job_name),
        "recovery_success_rate": get_recovery_success_rate(job_name),
        "time_to_recovery": get_average_recovery_time(job_name),
        "data_consistency_rate": get_data_consistency_rate(job_name)
    }
```

### **Checkpoint Health Monitoring**

```python
def monitor_checkpoint_health():
    """Monitor checkpoint system health"""
    
    health_metrics = {
        "checkpoint_storage_usage": get_checkpoint_storage_usage(),
        "checkpoint_validation_failures": get_validation_failures(),
        "recovery_failures": get_recovery_failures(),
        "checkpoint_corruption_incidents": get_corruption_incidents()
    }
    
    # Alert on issues
    for metric, value in health_metrics.items():
        if value > HEALTH_THRESHOLDS[metric]:
            send_alert(f"Checkpoint health issue: {metric} = {value}")
    
    return health_metrics
```

## 🎯 Best Practices

### **Checkpoint Design Principles**

1. **Atomic Checkpoints**: Each checkpoint represents a consistent state
2. **Minimal Data**: Store only essential recovery information
3. **Versioned Format**: Support checkpoint format evolution
4. **Validation**: Always validate checkpoint data before use
5. **Cleanup**: Remove old checkpoints to prevent storage bloat

### **Recovery Guidelines**

1. **Test Recovery**: Regularly test recovery scenarios
2. **Monitor Performance**: Track recovery time and success rates
3. **Document Changes**: Record checkpoint format changes
4. **Graceful Degradation**: Handle corrupted checkpoints gracefully
5. **User Communication**: Provide clear recovery status to users

This checkpoint system ensures robust, efficient, and reliable ETL operations with minimal data loss and maximum recovery precision.
