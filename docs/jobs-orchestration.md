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

## 🤖 AI & ML Job Management (Phase 1+)

### AI-Enhanced Job Orchestration

The orchestrator has been enhanced with AI capabilities for intelligent job management and ML monitoring:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Enhanced Orchestrator                        │
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │  Job Scheduler  │    │  Recovery Mgr   │    │ Status Mgr  │  │
│  │                 │    │                 │    │             │  │
│  │ • Smart Timing  │    │ • Checkpoint    │    │ • Real-time │  │
│  │ • Dependencies  │    │ • Retry Logic   │    │ • WebSocket │  │
│  │ • Load Balance  │    │ • Error Handle  │    │ • Progress  │  │
│  │ • AI Monitoring │    │ • ML Recovery   │    │ • AI Metrics│  │
│  └─────────────────┘    └─────────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub Job    │    │    Jira Job     │    │   AI Jobs       │
│                 │    │                 │    │  (Phase 2+)     │
│ • Pull Requests │    │ • Issues        │    │                 │
│ • Repositories  │    │ • Projects      │    │ • Embedding Gen │
│ • Commits       │    │ • Sprints       │    │ • ML Training   │
│ • Deployments   │    │ • Workflows     │    │ • Validation    │
│ • ML Data Prep  │    │ • ML Data Prep  │    │ • Predictions   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### ML Monitoring Integration

#### Performance Metrics Collection
```python
# AI Performance Monitoring during job execution
class AIJobMonitor:
    def __init__(self, job_name: str, client_id: int):
        self.job_name = job_name
        self.client_id = client_id
        self.start_time = None
        self.metrics = []

    async def log_performance_metric(self, metric_name: str, value: float, unit: str = None):
        """Log performance metrics to ML monitoring system"""
        metric = AIPerformanceMetric(
            metric_name=metric_name,
            metric_value=value,
            metric_unit=unit,
            service_name='etl',
            client_id=self.client_id,
            measurement_timestamp=datetime.utcnow()
        )
        await self.save_metric(metric)

    async def detect_anomalies(self, current_metrics: Dict[str, float]):
        """Detect performance anomalies during job execution"""
        for metric_name, value in current_metrics.items():
            if await self.is_anomaly(metric_name, value):
                await self.create_anomaly_alert(metric_name, value)
```

#### AI Learning Memory Integration
```python
# Capture job failures for AI learning
class JobFailureLearning:
    async def capture_failure(self, job_name: str, error: Exception, context: Dict):
        """Capture job failures for AI learning and improvement"""
        learning_entry = AILearningMemory(
            error_type='job_failure',
            user_intent=f'Execute {job_name} job successfully',
            failed_query=str(context.get('last_operation', '')),
            specific_issue=str(error),
            client_id=context['client_id'],
            learning_context=context
        )
        await self.save_learning_entry(learning_entry)

    async def suggest_recovery_strategy(self, job_name: str, error_type: str):
        """Use AI learning to suggest recovery strategies"""
        similar_failures = await self.find_similar_failures(job_name, error_type)
        if similar_failures:
            return await self.generate_recovery_suggestion(similar_failures)
        return None
```

### AI Job Types (Phase 2+)

#### Embedding Generation Jobs
```python
class EmbeddingGenerationJob(BaseJob):
    """Generate embeddings for text content"""

    async def run(self):
        # Process issues, PRs, and other text content
        # Generate embeddings using AI service
        # Update vector columns in database
        # Monitor performance and accuracy
        pass
```

#### ML Model Training Jobs
```python
class MLModelTrainingJob(BaseJob):
    """Train ML models for predictions and validation"""

    async def run(self):
        # Extract features from historical data
        # Train models (story point estimation, timeline forecasting)
        # Validate model performance
        # Deploy models to AI service
        pass
```

#### Data Validation Jobs
```python
class DataValidationJob(BaseJob):
    """Validate data quality using ML models"""

    async def run(self):
        # Run data quality checks
        # Detect anomalies in incoming data
        # Flag potential data issues
        # Generate validation reports
        pass
```

### Enhanced Job Recovery with AI

#### Intelligent Retry Strategies
```python
class AIEnhancedRecovery:
    async def determine_retry_strategy(self, job_name: str, error: Exception):
        """Use AI to determine optimal retry strategy"""

        # Analyze error patterns from AI learning memory
        error_analysis = await self.analyze_error_pattern(str(error))

        # Determine retry strategy based on AI insights
        if error_analysis.get('transient_error_probability') > 0.8:
            return RetryStrategy(
                max_attempts=5,
                backoff_factor=2,
                jitter=True
            )
        elif error_analysis.get('configuration_error_probability') > 0.7:
            return RetryStrategy(
                max_attempts=1,
                require_manual_intervention=True
            )

        return RetryStrategy(max_attempts=3, backoff_factor=1.5)
```

### AI Monitoring Dashboard Integration

#### Real-time AI Metrics
- **ML Model Performance**: Accuracy, precision, recall metrics
- **Embedding Generation**: Processing speed and quality metrics
- **Anomaly Detection**: Alert frequency and accuracy
- **Data Validation**: Quality scores and issue detection rates
- **AI Service Health**: Response times and availability

#### AI Job Status Tracking
```python
# Enhanced job status with AI metrics
{
    "job_name": "github_data_extraction",
    "status": "RUNNING",
    "progress": 75,
    "ai_metrics": {
        "data_quality_score": 0.95,
        "anomalies_detected": 2,
        "ml_predictions_generated": 150,
        "embedding_generation_rate": "50 items/sec"
    },
    "ai_alerts": [
        {
            "type": "performance_degradation",
            "severity": "medium",
            "message": "Processing speed 20% below baseline"
        }
    ]
}
```

### Phase Implementation Status

#### Phase 1 (Completed ✅)
- **ML Monitoring Infrastructure**: Performance metrics and anomaly detection tables
- **AI Learning Memory**: Error capture and learning system
- **Enhanced Job Models**: Vector columns and AI-ready data structures
- **Monitoring Integration**: Basic AI metrics collection framework

#### Phase 3-1 through 3-3 (Completed ✅)
- **Qdrant Integration**: High-performance vector database with tenant isolation
- **Flexible AI Provider Framework**: JSON-based provider configuration
- **Frontend AI Configuration**: Self-service AI management interface

#### Phase 3-4: ETL AI Integration (Completed ✅) **JUST COMPLETED**
- **Comprehensive Vectorization**: All 13 ETL data tables now vectorized
- **Bulk AI Processing**: Optimized ETL → Backend → Qdrant integration
- **Real-time Vector Generation**: Automatic vectorization during data extraction
- **Cross-Platform Search**: Unified semantic search across Jira and GitHub data
- **Clean Service Boundaries**: ETL processes data, Backend handles all AI operations
- **Error Resilience**: AI operation failures don't impact ETL jobs
- **External ID Architecture**: Queue-based vectorization using external system IDs (GitHub PR numbers, Jira issue keys) for better performance
- **GitHub Entity Support**: All GitHub entity types (repositories, PRs, commits, reviews, comments) properly vectorized

#### Vectorized Data Tables (13 total):
- **Jira Core**: changelogs, wits, statuses, projects
- **GitHub Core**: prs_comments, prs_reviews, prs_commits, repositories
- **Cross-Platform**: wits_prs_links
- **Configuration**: wits_hierarchies, wits_mappings, statuses_mappings, workflows

#### Vectorization Queue Architecture:
- **External ID-Based**: Uses external system identifiers (GitHub PR numbers, Jira issue keys) instead of internal database primary keys
- **Table-Specific Field Mapping**: work_items use "key" field, GitHub entities use "external_id" field
- **Backend Join Processing**: Backend service joins vectorization queue with actual tables during processing
- **Progress Routing**: Vectorization progress sent to dedicated "Vectorization" websocket channel
- **Entity Data Preparation**: Table-specific data transformation for all GitHub and Jira entity types

#### Phase 3-5+ (Ready for Implementation)
- **Vector Collection Management**: Qdrant collection optimization and performance testing
- **AI Query Interface**: Natural language query processing
- **ML Model Training Jobs**: Automated model training and deployment
- **Data Validation Jobs**: AI-powered data quality assurance
- **Intelligent Recovery**: AI-driven error analysis and recovery strategies
- **Predictive Scheduling**: ML-based optimal job scheduling

---

This enhanced orchestration system provides robust, scalable, and AI-powered job management for the Pulse Platform's ETL and ML operations.
