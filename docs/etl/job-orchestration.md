# ETL Job Orchestration

## 🎯 Orchestration Philosophy

The Pulse Platform uses an **Active/Passive Job Model** with intelligent orchestration:

- **Single Job Execution**: Only one ETL job runs at a time to prevent resource conflicts
- **Smart Scheduling**: Orchestrator intelligently selects which job to run next
- **Manual Override**: Force start/stop capabilities for operational control
- **Status-Based Logic**: Job selection based on current status and priority
- **Graceful Coordination**: Smooth transitions between jobs and states

## 🏗️ Orchestration Architecture

### **Core Components**

```
┌─────────────────────────────────────────────────────────────┐
│                    ETL Orchestrator                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────┐  │
│  │   Scheduler     │    │  Job Manager    │    │  Status │  │
│  │   (APScheduler) │◄──►│   (Logic)       │◄──►│ Monitor │  │
│  │                 │    │                 │    │         │  │
│  │  • Cron Jobs    │    │  • Job Selection│    │ • Health│  │
│  │  • Intervals    │    │  • Execution    │    │ • Logs  │  │
│  │  • Manual       │    │  • Coordination │    │ • Alerts│  │
│  └─────────────────┘    └─────────────────┘    └─────────┘  │
│                                │                            │
│                                ▼                            │
│                    ┌─────────────────────┐                  │
│                    │    Job Execution    │                  │
│                    │                     │                  │
│                    │  ┌─────┐  ┌─────┐   │                  │
│                    │  │Jira │  │GitHub│   │                  │
│                    │  │ Job │  │ Job │   │                  │
│                    │  └─────┘  └─────┘   │                  │
│                    └─────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

## 📊 Job Status Model

### **Job States**
```python
class JobStatus(Enum):
    NOT_STARTED = "NOT_STARTED"  # Initial state, never run
    PENDING = "PENDING"          # Ready to run, waiting for orchestrator
    RUNNING = "RUNNING"          # Currently executing
    FINISHED = "FINISHED"        # Completed successfully
    PAUSED = "PAUSED"           # Manually paused, skipped by orchestrator
    FAILED = "FAILED"           # Failed execution (rare, usually becomes PENDING)
```

### **Status Transitions**
```
NOT_STARTED → [Force Start] → PENDING → [Orchestrator] → RUNNING → FINISHED
                                                            ↓
                                                         FAILED
                                                            ↓
                                                        PENDING (Recovery)

PENDING/FINISHED → [Pause] → PAUSED → [Unpause] → PENDING/FINISHED
```

## 🔄 Orchestration Logic

### **Job Selection Algorithm**

```python
def select_next_job() -> Optional[JobSchedule]:
    """Select the next job to run based on priority and status"""
    
    # 1. Find all active jobs
    active_jobs = session.query(JobSchedule).filter(
        JobSchedule.active == True
    ).all()
    
    # 2. Check if any job is currently running
    running_jobs = [job for job in active_jobs if job.status == 'RUNNING']
    if running_jobs:
        logger.info("Job already running, skipping orchestration")
        return None
    
    # 3. Find PENDING jobs (highest priority)
    pending_jobs = [job for job in active_jobs if job.status == 'PENDING']
    if pending_jobs:
        # Return first PENDING job (FIFO)
        return pending_jobs[0]
    
    # 4. No PENDING jobs, orchestration complete
    logger.info("No PENDING jobs found, orchestration complete")
    return None
```

### **Orchestration Flow**

```python
async def run_orchestrator():
    """Main orchestration logic"""
    logger.info("STARTING: ETL Orchestrator starting...")
    
    try:
        # Select next job to run
        job = select_next_job()
        
        if not job:
            logger.info("SUCCESS: No jobs to run, orchestration complete")
            return
        
        logger.info(f"FOUND: PENDING job: {job.job_name}")
        
        # Lock job (set to RUNNING)
        job.status = 'RUNNING'
        job.started_at = datetime.utcnow()
        session.commit()
        
        logger.info(f"LOCKED: job {job.job_name} (status: RUNNING)")
        
        # Trigger job execution
        await trigger_job_execution(job)
        
        logger.info(f"SUCCESS: Orchestrator completed - {job.job_name} job triggered")
        
    except Exception as e:
        logger.error(f"ERROR: Orchestrator failed: {e}")
        raise
```

## ⏰ Scheduling Strategy

### **Automatic Scheduling**

#### **Orchestrator Schedule**
```python
# Runs every 60 minutes
scheduler.add_job(
    func=run_orchestrator,
    trigger="interval",
    minutes=60,
    id="etl_orchestrator",
    name="ETL Job Orchestrator"
)
```

#### **Schedule Configuration**
- **Interval**: 60 minutes (configurable in database)
- **Minimum Interval**: 1 hour (UI restriction)
- **Maximum Interval**: 24 hours
- **Timezone**: UTC for consistency

### **Manual Scheduling**

#### **Force Start Orchestrator**
```python
@router.post("/api/v1/orchestrator/start")
async def force_start_orchestrator():
    """Manually trigger orchestrator execution"""
    logger.info("Orchestrator manually triggered")
    await run_orchestrator()
    return {"success": True, "message": "Orchestrator triggered successfully"}
```

#### **Force Start Individual Job**
```python
@router.post("/api/v1/jobs/{job_name}/start")
async def force_start_job(job_name: str):
    """Force start a specific job"""
    job = get_job_by_name(job_name)
    job.status = 'PENDING'
    session.commit()
    
    # Immediately trigger orchestrator
    await run_orchestrator()
    return {"success": True, "message": f"Job {job_name} started"}
```

## 🎮 Job Control Mechanisms

### **Pause/Unpause Logic**

#### **Pause Job**
```python
def pause_job(job_name: str):
    """Pause a job (sets to PAUSED status)"""
    job = get_job_by_name(job_name)
    
    if job.status == 'RUNNING':
        raise ValueError("Cannot pause running job - stop it first")
    
    job.status = 'PAUSED'
    session.commit()
    
    logger.info(f"Job {job_name} paused")
```

#### **Unpause Job (Smart Logic)**
```python
def unpause_job(job_name: str):
    """Unpause a job with intelligent status setting"""
    job = get_job_by_name(job_name)
    other_job = get_other_job(job_name)
    
    if other_job.status in ['PENDING', 'RUNNING']:
        # Other job has priority, set to FINISHED
        job.status = 'FINISHED'
        logger.info(f"Job {job_name} unpaused to FINISHED (other job active)")
    else:
        # No conflict, set to PENDING for next run
        job.status = 'PENDING'
        logger.info(f"Job {job_name} unpaused to PENDING")
    
    session.commit()
```

### **Force Stop Logic**

#### **Jira Force Stop (Clean Abort)**
```python
def force_stop_jira():
    """Stop Jira job - clean abort, reprocess next time"""
    job = get_job_by_name('jira_sync')
    
    if job.status == 'RUNNING':
        job.status = 'FINISHED'
        job.error_message = "Manually stopped - saved items will be reprocessed on next run"
        session.commit()
        
        logger.info("Jira job manually stopped - clean abort")
```

#### **GitHub Force Stop (Checkpoint Recovery)**
```python
def force_stop_github():
    """Stop GitHub job - preserve checkpoint for recovery"""
    job = get_job_by_name('github_sync')
    
    if job.status == 'RUNNING':
        job.status = 'PENDING'
        job.error_message = "Manually stopped - will resume from last checkpoint"
        job.retry_count += 1
        session.commit()
        
        logger.info("GitHub job manually stopped - will resume from checkpoint")
```

## 🛡️ Orchestration Safety Mechanisms

### **Concurrency Control**

#### **Single Job Execution**
```python
def ensure_single_job_execution():
    """Ensure only one job runs at a time"""
    running_jobs = session.query(JobSchedule).filter(
        JobSchedule.status == 'RUNNING',
        JobSchedule.active == True
    ).count()
    
    if running_jobs > 1:
        logger.error(f"VIOLATION: Multiple jobs running simultaneously: {running_jobs}")
        # Alert administrators
        send_alert("Multiple ETL jobs running", severity="HIGH")
```

#### **Resource Lock Management**
```python
def acquire_job_lock(job_name: str) -> bool:
    """Acquire exclusive lock for job execution"""
    try:
        job = session.query(JobSchedule).filter(
            JobSchedule.job_name == job_name,
            JobSchedule.status.in_(['PENDING', 'FINISHED'])
        ).with_for_update().first()
        
        if job:
            job.status = 'RUNNING'
            session.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to acquire lock for {job_name}: {e}")
        return False
```

### **Error Handling**

#### **Orchestrator Failure Recovery**
```python
def recover_from_orchestrator_failure():
    """Recover from orchestrator failure"""
    # Find jobs stuck in RUNNING state
    stuck_jobs = session.query(JobSchedule).filter(
        JobSchedule.status == 'RUNNING',
        JobSchedule.started_at < datetime.utcnow() - timedelta(hours=2)
    ).all()
    
    for job in stuck_jobs:
        logger.warning(f"Recovering stuck job: {job.job_name}")
        job.status = 'PENDING'  # Reset for retry
        job.error_message = "Recovered from stuck state"
        session.commit()
```

## 📊 Orchestration Monitoring

### **Orchestrator Status**

```python
def get_orchestrator_status():
    """Get current orchestrator status"""
    return {
        "is_running": scheduler.running,
        "next_run": get_next_scheduled_run(),
        "last_run": get_last_run_time(),
        "active_jobs": get_active_job_count(),
        "running_jobs": get_running_job_count(),
        "pending_jobs": get_pending_job_count()
    }
```

### **Job Execution Metrics**

```python
def get_job_metrics():
    """Get job execution metrics"""
    return {
        "total_executions": get_total_job_executions(),
        "successful_executions": get_successful_executions(),
        "failed_executions": get_failed_executions(),
        "average_execution_time": get_average_execution_time(),
        "last_24h_executions": get_recent_executions(hours=24)
    }
```

## 🎯 Orchestration Best Practices

### **Design Principles**
1. **Single Responsibility**: One job at a time for resource efficiency
2. **Fail Fast**: Quick failure detection and recovery
3. **Graceful Degradation**: Continue other operations when one fails
4. **Transparent Operations**: Clear logging and status reporting
5. **Manual Override**: Always allow manual intervention

### **Operational Guidelines**
1. **Monitor Regularly**: Check orchestrator health and job status
2. **Plan Maintenance**: Use pause functionality for system maintenance
3. **Test Recovery**: Regularly test failure and recovery scenarios
4. **Optimize Timing**: Adjust schedule based on data volume and API limits
5. **Document Changes**: Track all manual interventions and configuration changes

This orchestration system provides reliable, efficient, and controllable ETL job management with comprehensive monitoring and safety mechanisms.
