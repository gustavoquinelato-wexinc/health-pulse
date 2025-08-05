# Jobs & Orchestration Guide

**ETL Job Management, Orchestration & Recovery Strategies**

This document covers all aspects of job management in the Pulse Platform, including the orchestrator system, individual job types, recovery strategies, and integration management.

## 🎯 Job Orchestration Overview

### Orchestrator Architecture

The Pulse Platform uses an intelligent orchestrator that manages multiple ETL jobs with smart scheduling and recovery capabilities:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Orchestrator                            │
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │  Job Scheduler  │    │  Recovery Mgr   │    │ Status Mgr  │  │
│  │                 │    │                 │    │             │  │
│  │ • Smart Timing  │    │ • Checkpoint    │    │ • Real-time │  │
│  │ • Dependencies  │    │ • Retry Logic   │    │ • WebSocket │  │
│  │ • Load Balance  │    │ • Error Handle  │    │ • Progress  │  │
│  └─────────────────┘    └─────────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub Job    │    │    Jira Job     │    │  Sleep Job      │
│                 │    │                 │    │  (Orchestrator) │
│ • Pull Requests │    │ • Issues        │    │                 │
│ • Repositories  │    │ • Projects      │    │ • Retry Failed  │
│ • Commits       │    │ • Sprints       │    │ • Health Check  │
│ • Deployments   │    │ • Workflows     │    │ • Maintenance   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Job States & Lifecycle

#### Job Status States
- **NOT_STARTED**: Job has not been initiated
- **PENDING**: Job is queued and waiting to start
- **RUNNING**: Job is currently executing
- **FINISHED**: Job completed successfully
- **ERROR**: Job failed with an error
- **PAUSED**: Job is temporarily paused

#### State Transitions
```
NOT_STARTED → PENDING → RUNNING → FINISHED
                ↓         ↓
              PAUSED ← ERROR
                ↓      ↓
              RUNNING (retry)
```

## 🔄 Individual Job Types

### GitHub Job

#### Purpose & Scope
- **Data Collection**: Pull requests, repositories, commits, deployments
- **DORA Metrics**: Lead time, deployment frequency, change failure rate
- **Team Analytics**: Developer productivity and collaboration metrics

#### Data Sources
```python
# GitHub API endpoints
GITHUB_ENDPOINTS = {
    "repositories": "/orgs/{org}/repos",
    "pull_requests": "/repos/{owner}/{repo}/pulls",
    "commits": "/repos/{owner}/{repo}/commits",
    "deployments": "/repos/{owner}/{repo}/deployments",
    "releases": "/repos/{owner}/{repo}/releases"
}
```

#### Processing Flow
1. **Repository Discovery**: Fetch all repositories for the organization
2. **Pull Request Analysis**: Collect PR data with merge/close timestamps
3. **Commit Processing**: Analyze commit patterns and frequency
4. **Deployment Tracking**: Monitor deployment success/failure rates
5. **Metrics Calculation**: Compute DORA metrics from collected data

#### Recovery Strategies
- **Checkpoint System**: Save progress after each repository
- **Incremental Updates**: Only fetch data newer than last successful run
- **Rate Limit Handling**: Automatic backoff and retry on API limits
- **Partial Failure Recovery**: Continue with remaining repositories if some fail

### Jira Job

#### Purpose & Scope
- **Issue Tracking**: Stories, bugs, tasks, epics
- **Sprint Analytics**: Velocity, burndown, completion rates
- **Project Health**: Cycle time, throughput, quality metrics

#### Data Sources
```python
# Jira API endpoints
JIRA_ENDPOINTS = {
    "projects": "/rest/api/3/project",
    "issues": "/rest/api/3/search",
    "sprints": "/rest/agile/1.0/board/{board_id}/sprint",
    "workflows": "/rest/api/3/workflow",
    "users": "/rest/api/3/users/search"
}
```

#### Processing Flow
1. **Project Discovery**: Identify active Jira projects
2. **Issue Collection**: Fetch issues with full history and transitions
3. **Sprint Analysis**: Process sprint data and velocity calculations
4. **Workflow Mapping**: Understand project-specific workflows
5. **Metrics Generation**: Calculate cycle time, throughput, and quality metrics

#### Recovery Strategies
- **JQL-Based Checkpoints**: Use JQL queries to resume from specific points
- **Date-Range Processing**: Process data in manageable date chunks
- **Project-Level Recovery**: Restart from failed project, not entire job
- **Field-Level Validation**: Verify data integrity during processing

### Sleep Job (Orchestrator)

#### Purpose & Scope
- **Retry Management**: Automatically retry failed jobs
- **Health Monitoring**: Check system health and job status
- **Maintenance Tasks**: Cleanup, optimization, and housekeeping
- **Smart Scheduling**: Determine optimal timing for job execution

#### Retry Logic
```python
# Intelligent retry strategy
RETRY_CONFIG = {
    "max_retries": 3,
    "base_delay": 300,      # 5 minutes
    "exponential_backoff": True,
    "jitter": True,         # Add randomness to prevent thundering herd
    "retry_conditions": [
        "network_timeout",
        "api_rate_limit",
        "temporary_service_error"
    ]
}
```

#### Recovery Timing
- **Fast Recovery**: 5-30 minutes for transient failures
- **Standard Recovery**: 1-4 hours for API issues
- **Extended Recovery**: 24 hours for major outages
- **Manual Intervention**: Critical failures requiring admin action

## 🛠️ Job Control & Management

### Manual Job Control

#### Start/Stop Operations
```python
# Job control endpoints
POST /api/v1/jobs/{job_name}/start     # Start specific job
POST /api/v1/jobs/{job_name}/stop      # Stop running job
POST /api/v1/jobs/{job_name}/pause     # Pause job execution
POST /api/v1/jobs/{job_name}/resume    # Resume paused job
POST /api/v1/jobs/orchestrator/start   # Start orchestrator
```

#### Force Operations
- **Force Start**: Override job state and start immediately
- **Force Stop**: Terminate job regardless of current state
- **Emergency Stop**: Kill all running jobs (admin only)

#### Job Scheduling
```python
# Orchestrator scheduling logic
SCHEDULE_CONFIG = {
    "github_job": {
        "interval": "4_hours",
        "fast_recovery": "30_minutes",  # When status is PENDING
        "dependencies": []
    },
    "jira_job": {
        "interval": "6_hours", 
        "fast_recovery": "1_hour",
        "dependencies": []
    },
    "sleep_job": {
        "interval": "15_minutes",
        "dependencies": ["github_job", "jira_job"]
    }
}
```

### Real-Time Monitoring

#### WebSocket Updates
```javascript
// Real-time job status updates
websocket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    switch(data.type) {
        case 'job_started':
            updateJobStatus(data.job_name, 'RUNNING');
            break;
        case 'job_progress':
            updateProgressBar(data.job_name, data.progress);
            break;
        case 'job_completed':
            updateJobStatus(data.job_name, 'FINISHED');
            break;
        case 'job_error':
            updateJobStatus(data.job_name, 'ERROR');
            showErrorDetails(data.error_message);
            break;
    }
};
```

#### Progress Tracking
- **Percentage Complete**: Real-time progress updates
- **Current Operation**: What the job is currently processing
- **Records Processed**: Count of items processed vs. total
- **Time Estimates**: ETA for job completion

## 🔧 Integration Management

### API Configuration

#### GitHub Integration
```python
# GitHub configuration
GITHUB_CONFIG = {
    "base_url": "https://api.github.com",
    "organization": "your-org",
    "token": "ghp_xxxxxxxxxxxxxxxxxxxx",
    "rate_limit": {
        "requests_per_hour": 5000,
        "core_limit": 5000,
        "search_limit": 30
    },
    "retry_config": {
        "max_retries": 3,
        "backoff_factor": 2
    }
}
```

#### Jira Integration
```python
# Jira configuration
JIRA_CONFIG = {
    "base_url": "https://company.atlassian.net",
    "email": "admin@company.com",
    "api_token": "ATATT3xFfGF0...",
    "projects": ["PROJ1", "PROJ2", "PROJ3"],
    "max_results": 100,
    "fields": [
        "summary", "status", "assignee", "created", 
        "updated", "resolutiondate", "priority"
    ]
}
```

### Data Validation & Quality

#### Input Validation
```python
# Data validation rules
VALIDATION_RULES = {
    "github_pr": {
        "required_fields": ["number", "title", "state", "created_at"],
        "date_format": "ISO8601",
        "state_values": ["open", "closed", "merged"]
    },
    "jira_issue": {
        "required_fields": ["key", "summary", "status", "created"],
        "key_pattern": r"^[A-Z]+-\d+$",
        "status_mapping": "project_specific"
    }
}
```

#### Data Quality Checks
- **Completeness**: Verify all required fields are present
- **Consistency**: Check data relationships and references
- **Accuracy**: Validate data formats and ranges
- **Timeliness**: Ensure data is current and relevant

## 🚨 Error Handling & Recovery

### Error Classification

#### Transient Errors (Retry Automatically)
- **Network Timeouts**: Temporary connectivity issues
- **API Rate Limits**: Temporary API quota exhaustion
- **Service Unavailable**: Temporary service outages
- **Database Locks**: Temporary database contention

#### Permanent Errors (Manual Intervention Required)
- **Authentication Failures**: Invalid API credentials
- **Permission Denied**: Insufficient API permissions
- **Data Format Changes**: API response format changes
- **Configuration Errors**: Invalid job configuration

### Recovery Mechanisms

#### Checkpoint System
```python
# Job checkpoint implementation
class JobCheckpoint:
    def __init__(self, job_name: str, client_id: int):
        self.job_name = job_name
        self.client_id = client_id
        
    async def save_checkpoint(self, data: dict):
        """Save current job progress"""
        await database.execute(
            "INSERT INTO job_checkpoints (job_name, client_id, checkpoint_data, created_at) "
            "VALUES (?, ?, ?, ?)",
            self.job_name, self.client_id, json.dumps(data), datetime.utcnow()
        )
    
    async def load_checkpoint(self) -> dict:
        """Load last successful checkpoint"""
        result = await database.fetch_one(
            "SELECT checkpoint_data FROM job_checkpoints "
            "WHERE job_name = ? AND client_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            self.job_name, self.client_id
        )
        return json.loads(result["checkpoint_data"]) if result else {}
```

#### Graceful Degradation
- **Partial Success**: Continue processing even if some items fail
- **Fallback Strategies**: Use cached data when APIs are unavailable
- **Service Isolation**: Prevent failures in one service from affecting others
- **Circuit Breaker**: Temporarily disable failing integrations

## 📊 Job Performance & Optimization

### Performance Metrics

#### Job Execution Metrics
- **Duration**: Total time for job completion
- **Throughput**: Records processed per minute
- **Success Rate**: Percentage of successful job runs
- **Error Rate**: Frequency and types of errors

#### Resource Utilization
- **CPU Usage**: Processing load during job execution
- **Memory Usage**: Peak memory consumption
- **Network I/O**: API request volume and response times
- **Database Load**: Query performance and connection usage

### Optimization Strategies

#### Parallel Processing
```python
# Concurrent processing for improved performance
async def process_repositories_parallel(repositories: List[str]):
    semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
    
    async def process_repo(repo: str):
        async with semaphore:
            return await fetch_repo_data(repo)
    
    tasks = [process_repo(repo) for repo in repositories]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

#### Caching Strategies
- **API Response Caching**: Cache frequently accessed API responses
- **Computed Metrics Caching**: Store calculated metrics for reuse
- **Configuration Caching**: Cache integration configurations
- **Schema Caching**: Cache database schema information

---

This orchestration system provides robust, scalable, and reliable job management for the Pulse Platform's ETL operations.
