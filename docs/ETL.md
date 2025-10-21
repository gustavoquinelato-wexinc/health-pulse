# ETL & QUEUE SYSTEM

**Comprehensive ETL Architecture with RabbitMQ Queue Management**

This document covers the complete ETL system architecture, job orchestration, queue management, and integration capabilities for Jira, GitHub, and custom data sources.

## 🏗️ ETL Architecture Overview

### Modern Queue-Based ETL Architecture (Current)

The ETL system uses a modern, queue-based architecture with complete Extract → Transform → Load separation:

```
┌─────────────────┐    API Calls    ┌─────────────────┐    Queue Msgs    ┌─────────────────┐
│  Frontend ETL   │─────────────────►│ Backend Service │─────────────────►│   RabbitMQ      │
│  (Port 3333)    │                 │   /app/etl/*    │                 │  (Port 5672)    │
├─────────────────┤                 ├─────────────────┤                 ├─────────────────┤
│ • Job Dashboard │                 │ • ETL Endpoints │                 │ • Extract Queue │
│ • Custom Fields │                 │ • Auth Flow     │                 │ • Transform Q   │
│ • WIT Mgmt      │                 │ • Queue Mgmt    │                 │ • Load Queue    │
│ • Status Mgmt   │                 │ • Data Extract  │                 │ • Vector Queue  │
│ • Integrations  │                 │ • Job Control   │                 │ • Dead Letter   │
│ • Progress UI   │                 │ • Discovery API │                 │ • Retry Logic   │
│ • Real-time     │                 │ • Field Mapping │                 │ • Monitoring    │
└─────────────────┘                 └─────────────────┘                 └─────────────────┘
                                              │                                   │
                                              ▼                                   ▼
                                    ┌─────────────────┐                 ┌─────────────────┐
                                    │   PostgreSQL    │                 │  Queue Workers  │
                                    │  (Port 5432)    │                 │  (Background)   │
                                    ├─────────────────┤                 ├─────────────────┤
                                    │ • ETL Jobs      │                 │ • Extract Worker│
                                    │ • Raw Data      │                 │ • Transform Wkr │
                                    │ • Custom Fields │                 │ • Load Worker   │
                                    │ • Field Mappings│                 │ • Vector Worker │
                                    │ • Work Items    │                 │ • Progress Upd  │
                                    │ • Integrations  │                 │ • Error Handle  │
                                    │ • Statuses      │                 │ • Notifications │
                                    └─────────────────┘                 └─────────────────┘
```

### Legacy ETL Service (Deprecated)

```
┌─────────────────┐
│  ETL Service    │  ⚠️ DO NOT USE - LEGACY BACKUP ONLY
│  (Port 8002)    │
├─────────────────┤
│ • Jinja2 HTML   │  • Keep untouched as reference
│ • Monolithic    │  • All functionality moved to Backend Service
│ • Old Patterns  │  • No new development here
│ • Direct DB     │  • Replaced by queue-based architecture
└─────────────────┘
```

### Key Architectural Improvements

#### ✅ **Complete Extract → Transform → Load Separation**
- **Extract Workers**: Pure data extraction from APIs to raw storage
- **Transform Workers**: Data cleaning, normalization, and custom field mapping
- **Load Workers**: Optimized bulk loading to final tables
- **Vector Workers**: Embedding generation and vector database operations

#### ✅ **Dynamic Custom Fields System**
- **UI-Driven Configuration**: Custom field mapping without code changes
- **Project-Specific Discovery**: Automatic field discovery per Jira project
- **Optimized Storage**: 20 dedicated columns + unlimited JSON overflow
- **Performance Optimized**: Indexed JSON queries for overflow fields

## 🔄 Job Orchestration System

### Simplified ETL Job Lifecycle (Current System)

```
NOT_STARTED ──► READY ──► RUNNING ──► FINISHED
     │            │         │          │
     │            │         │          │
     ▼            ▼         ▼          ▼
  Waiting     Queued    Processing   Next Job
  Manual      Auto      All Stages   Cycle
  Trigger     Execute   (E→T→L→V)    Continue
                           │
                           ▼
                        FAILED
                      (On Error)
```

**Job Status Simplified (2025 Update):**
- **NOT_STARTED**: Initial state, waiting for trigger
- **READY**: Queued for execution, will auto-execute
- **RUNNING**: Currently executing all ETL stages with real-time status updates
- **FINISHED**: Successfully completed all stages
- **FAILED**: Error occurred, requires attention

### Tier-Based Queue Processing (Current Architecture)

#### 1. **Extract Stage**
- **Purpose**: Pure data extraction from external APIs
- **Queues**: `extraction_queue_{tier}` (e.g., `extraction_queue_premium`)
- **Output**: Raw data stored in `raw_extraction_data` table
- **Features**: API rate limiting, cursor management, checkpoint recovery

#### 2. **Transform Stage**
- **Purpose**: Data cleaning, normalization, and custom field mapping
- **Queues**: `transform_queue_{tier}` (e.g., `transform_queue_premium`)
- **Input**: Raw data from extract stage
- **Output**: Cleaned, mapped data ready for loading
- **Features**: Dynamic custom field processing, data validation

#### 3. **Load Stage**
- **Purpose**: Bulk loading to final database tables
- **Queues**: Handled within transform workers (no separate queue)
- **Input**: Transformed data from transform stage
- **Output**: Data in final business tables (issues, work_items, etc.)
- **Features**: Optimized bulk operations, relationship mapping

#### 4. **Vectorization Stage**
- **Purpose**: Generate embeddings for semantic search and multi-agent AI
- **Queues**: `embedding_queue_{tier}` (e.g., `embedding_queue_premium`)
- **Input**: Final loaded data from transform stage
- **Output**: Vector embeddings in Qdrant database + bridge table tracking
- **Features**:
  - Multi-agent architecture with source_type filtering (JIRA, GITHUB)
  - Integration-based embedding configuration
  - Tenant isolation with dedicated collections
  - Bridge table (qdrant_vectors) for PostgreSQL ↔ Qdrant mapping

### Job States & Transitions (Simplified System)

#### Job States
- **NOT_STARTED**: Initial state, waiting for trigger
- **READY**: Queued for execution, will auto-execute
- **RUNNING**: Currently executing with real-time status updates (all stages: E→T→L→V)
- **FINISHED**: Successfully completed all stages
- **FAILED**: Error occurred, requires attention

#### Job Properties
- **active**: Boolean flag to enable/disable job (inactive jobs are skipped)
- **next_run**: Timestamp for next scheduled execution

#### Orchestration Logic
```python
# Smart job orchestration with timing optimization
class JobOrchestrator:
    def __init__(self):
        self.fast_retry_interval = 15 * 60  # 15 minutes between jobs
        self.full_cycle_interval = 60 * 60  # 1 hour for full cycle
    
    async def get_next_job(self, tenant_id: int) -> Optional[ETLJob]:
        # Get active jobs only (skip paused)
        active_jobs = await self.get_active_jobs(tenant_id)
        
        # Find next job with READY status
        next_job = None
        for job in active_jobs:
            if job.status == "READY":
                next_job = job
                break

        # If no READY jobs, cycle back to first and mark as READY
        if not next_job and active_jobs:
            next_job = active_jobs[0]
            next_job.status = "READY"
            # Use full interval when cycling back
            await self.schedule_job(next_job, delay=self.full_cycle_interval)
        elif next_job:
            # Use fast retry for job-to-job transitions
            await self.schedule_job(next_job, delay=self.fast_retry_interval)
        
        return next_job
    
    async def execute_job(self, job: ETLJob):
        # Validate both job.active and integration.active
        if not job.active:
            logger.info(f"Skipping inactive job: {job.name}")
            return
        
        integration = await self.get_integration(job.integration_id)
        if not integration.active:
            await self.finish_job_with_alert(
                job, 
                "Integration is inactive - job skipped"
            )
            return
        
        # Execute job with real-time status updates
        await self.run_job_with_status_tracking(job)
```

### Real-Time Status System

#### JSON-Based Status Architecture
Each ETL job maintains a comprehensive JSON status structure that tracks all stages:

```python
# Job Status Structure (stored in etl_jobs.status JSONB column)
{
    "overall": "RUNNING",  # READY, RUNNING, FINISHED, FAILED
    "steps": {
        "jira_projects_and_issue_types": {
            "order": 1,
            "extraction": "finished",  # idle, running, finished
            "transform": "finished",
            "embedding": "running",
            "display_name": "Projects & Types"
        },
        "jira_statuses_and_relationships": {
            "order": 2,
            "extraction": "finished",
            "transform": "finished",
            "embedding": "idle",
            "display_name": "Statuses & Relations"
        },
        "jira_issues_with_changelogs": {
            "order": 3,
            "extraction": "running",
            "transform": "idle",
            "embedding": "idle",
            "display_name": "Issues & Changelogs"
        },
        "jira_dev_status": {
            "order": 4,
            "extraction": "idle",
            "transform": "idle",
            "embedding": "idle",
            "display_name": "Development Status"
        }
    }
}
```

#### WebSocket Real-Time Updates
Workers send status updates via WebSocket **only** when processing messages with `first_item=true` or `last_item=true`:

```python
# WebSocket Update Conditions (in workers)
if job_id and first_item:
    # Send status update when starting a new stage
    await self._send_worker_status(
        worker_type="extraction",  # or "transform", "embedding"
        tenant_id=tenant_id,
        job_id=job_id,
        status="running",
        step=step_type
    )

if job_id and last_item:
    # Send status update when completing a stage
    await self._send_worker_status(
        worker_type="extraction",
        tenant_id=tenant_id,
        job_id=job_id,
        status="finished",
        step=step_type
    )
```

**Key Principles:**
- **No individual item progression messages** - only step-level status updates
- **Database-first approach** - workers update database, then send complete JSON via WebSocket
- **Consistent message format** - frontend receives same JSON structure as database refresh

**WebSocket Channels:**
- `/ws/job/extraction/{tenant_id}/{job_id}` - Extraction worker updates
- `/ws/job/transform/{tenant_id}/{job_id}` - Transform worker updates
- `/ws/job/embedding/{tenant_id}/{job_id}` - Embedding worker updates

**Message Format:**
```json
{
  "type": "job_status_update",
  "tenant_id": 1,
  "job_id": 1,
  "status": {
    "overall": "RUNNING",
    "steps": {
      "jira_projects_and_issue_types": {
        "extraction": "finished",
        "transform": "running",
        "embedding": "idle"
      }
    }
  }
}
```

## 🐰 RabbitMQ Queue System

### Queue Architecture

```
┌─────────────────┐    Publish    ┌─────────────────┐    Consume    ┌─────────────────┐
│   ETL Jobs      │──────────────►│   Job Queue     │──────────────►│  Job Workers    │
│   (Scheduler)   │               │   (RabbitMQ)    │               │  (Background)   │
└─────────────────┘               └─────────────────┘               └─────────────────┘
                                           │
                                           ▼
                                  ┌─────────────────┐
                                  │  Dead Letter    │
                                  │  Queue (DLQ)    │
                                  │  (Failed Jobs)  │
                                  └─────────────────┘
```

### Queue Configuration

#### Primary Queues
```python
# ETL job execution queue
ETL_JOB_QUEUE = {
    "name": "etl.jobs",
    "durable": True,
    "auto_delete": False,
    "arguments": {
        "x-message-ttl": 3600000,  # 1 hour TTL
        "x-dead-letter-exchange": "etl.dlx",
        "x-dead-letter-routing-key": "failed"
    }
}

# Vectorization processing queue
VECTORIZATION_QUEUE = {
    "name": "etl.vectorization",
    "durable": True,
    "auto_delete": False,
    "arguments": {
        "x-message-ttl": 1800000,  # 30 minutes TTL
        "x-max-retries": 3
    }
}

# Custom fields sync queue
CUSTOM_FIELDS_QUEUE = {
    "name": "etl.custom_fields",
    "durable": True,
    "auto_delete": False,
    "arguments": {
        "x-message-ttl": 600000,  # 10 minutes TTL
        "x-max-retries": 5
    }
}
```

#### Dead Letter Queue
```python
# Failed job handling
DEAD_LETTER_QUEUE = {
    "name": "etl.failed",
    "durable": True,
    "auto_delete": False,
    "arguments": {
        "x-message-ttl": 86400000,  # 24 hours retention
        "x-max-length": 1000  # Max 1000 failed messages
    }
}
```

### Queue Message Formats

#### Job Execution Message
```json
{
  "job_id": 123,
  "tenant_id": 1,
  "integration_id": 456,
  "job_type": "jira_sync",
  "config": {
    "full_sync": false,
    "batch_size": 50,
    "include_custom_fields": true
  },
  "scheduled_at": "2024-01-15T10:00:00Z",
  "priority": 1,
  "retry_count": 0,
  "max_retries": 3
}
```

#### Extraction Worker Message
```json
{
  "tenant_id": 1,
  "integration_id": 456,
  "job_id": 123,
  "type": "jira_dev_status_fetch",
  "provider": "Jira",
  "last_sync_date": "2025-10-21T14:00:00",
  "first_item": true,
  "last_item": false,
  "last_job_item": false,
  "issue_id": "2035047",
  "issue_key": "BEX-7997"
}
```

#### Transform Worker Message
```json
{
  "tenant_id": 1,
  "integration_id": 456,
  "job_id": 123,
  "type": "jira_dev_status",
  "provider": "jira",
  "last_sync_date": "2025-10-21T14:00:00",
  "first_item": false,
  "last_item": true,
  "last_job_item": true,
  "raw_data_id": 789
}
```

#### Vectorization Message
```json
{
  "tenant_id": 1,
  "table_name": "work_items",
  "external_id": "PROJ-123",
  "operation": "insert",
  "job_id": 123,
  "first_item": false,
  "last_item": true,
  "last_job_item": true
}
```

**Key Message Structure:**
- **Orchestration Flags**: `first_item`, `last_item`, `last_job_item` are always included for proper worker status updates
- **Worker Status**: Workers set themselves to "running" on `first_item=true` and "finished" on `last_item=true`
- **Job Completion**: Only the final message with `last_job_item=true` triggers job completion
- **Data References**: Extraction→Transform uses `raw_data_id`, Transform→Embedding uses `external_id`

### Queue Workers

#### Job Execution Worker
```python
class ETLJobWorker:
    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        self.connection = pika.BlockingConnection(
            pika.URLParameters(settings.RABBITMQ_URL)
        )
        self.channel = self.connection.channel()
    
    async def process_job(self, message: dict):
        job_id = message["job_id"]
        tenant_id = message["tenant_id"]
        
        try:
            # Set job status to RUNNING
            await self.update_job_status(job_id, "RUNNING")

            # Execute ETL job with real-time status updates (all stages)
            await self.execute_etl_job(message)

            # Set job status to FINISHED
            await self.update_job_status(job_id, "FINISHED")
            
            # Schedule next job
            await self.schedule_next_job(tenant_id)
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}")
            await self.update_job_status(job_id, "FAILED", error=str(e))
            
            # Send to dead letter queue for manual review
            await self.send_to_dlq(message, error=str(e))
```

#### Vectorization Worker
```python
class VectorizationWorker:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = QdrantClient()
    
    async def process_vectorization(self, message: dict):
        entity_id = message["entity_id"]
        content = message["content"]
        
        try:
            # Generate embedding
            embedding = await self.embedding_service.generate_embedding(
                content, 
                config=message["embedding_config"]
            )
            
            # Store in vector database
            await self.vector_store.upsert_vector(
                entity_id=entity_id,
                vector=embedding,
                metadata=message["metadata"]
            )
            
            # Update vectorization status
            await self.update_vectorization_status(entity_id, "completed")
            
        except Exception as e:
            logger.error(f"Vectorization failed for {entity_id}: {str(e)}")
            await self.update_vectorization_status(entity_id, "failed", error=str(e))
```

## 🔌 Integration Management

### Supported Integrations

#### 1. Jira Integration

**🔧 Jira Endpoint Usage:**
- **Automatic ETL Jobs**: Use `/rest/api/3/project/search` endpoint
  - Returns `{values: [...]}` with `issueTypes` (camelCase)
  - Used by job scheduler for regular data extraction
  - Processed by `_process_jira_project_search()` transform function
- **Manual Custom Fields Sync**: Use `/rest/api/3/issue/createmeta` endpoint
  - Returns `{projects: [...]}` with `issuetypes` (lowercase)
  - Triggered when user clicks "Queue for Extraction & Transform" button in UI
  - Processed by `_process_jira_custom_fields()` transform function

```python
class JiraIntegration:
    def __init__(self, config: dict):
        self.base_url = config["base_url"]
        self.username = config["username"]
        self.api_token = config["api_token"]
        self.projects = config.get("projects", [])
    
    async def sync_data(self, job_config: dict):
        # Step 1: Extract projects and issue types
        await self.extract_projects_and_issue_types()

        # Step 2: Extract statuses and relationships
        await self.extract_statuses_and_relationships()

        # Step 3: Extract issues with changelogs
        await self.extract_issues_with_changelogs(batch_size=job_config.get("batch_size", 50))

        # Step 4: Extract development status (if enabled)
        if job_config.get("include_dev_status", True):
            await self.extract_dev_status()

        # Note: Transform and embedding stages are handled by separate workers
        # Status updates are sent via WebSocket as each stage completes
```

#### 2. GitHub Integration
```python
class GitHubIntegration:
    def __init__(self, config: dict):
        self.token = config["token"]
        self.repositories = config.get("repositories", [])
        self.github_client = Github(self.token)
    
    async def sync_data(self, job_config: dict):
        # Batched processing for memory efficiency
        batch_size = job_config.get("batch_size", 50)
        
        for repo_name in self.repositories:
            repo = self.github_client.get_repo(repo_name)
            
            # Process PRs in batches
            prs = repo.get_pulls(state="all")
            await self.process_prs_in_batches(prs, batch_size)
            
            # Queue for vectorization
            await self.queue_vectorization(repo_name)
```

### Custom Fields Mapping System

#### Simplified Direct Mapping Architecture

The ETL system uses a simplified custom fields mapping architecture that directly maps Jira custom fields to 20 standardized columns in work_items table.

```
┌─────────────────────────────────────────────────────────────────┐
│                Custom Fields Mapping Architecture              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🔍 Global Discovery    🎯 Direct Mapping    💾 Tenant Config   │
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │ Extract all     │    │ 20 FK columns   │    │ Per tenant/ │  │
│  │ custom fields   │───►│ point directly  │───►│ integration │  │
│  │ globally        │    │ to custom_fields│    │ mapping     │  │
│  └─────────────────┘    └─────────────────┘    └─────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Database Schema
```sql
-- Global custom fields table
CREATE TABLE custom_fields (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(100) NOT NULL,     -- 'customfield_10001'
    name VARCHAR(255) NOT NULL,            -- 'Agile Team'
    field_type VARCHAR(100) NOT NULL,      -- 'team', 'string', 'option'
    operations JSONB DEFAULT '[]',         -- ['set'], ['add', 'remove']
    integration_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, integration_id, external_id)
);

-- Direct mapping configuration per tenant/integration
CREATE TABLE custom_fields_mapping (
    id SERIAL PRIMARY KEY,

    -- Special field mappings (always shown first in UI)
    team_field_id INTEGER REFERENCES custom_fields(id),
    code_changed_field_id INTEGER REFERENCES custom_fields(id),
    story_points_field_id INTEGER REFERENCES custom_fields(id),

    -- 20 direct FK columns to custom_fields
    custom_field_01_id INTEGER REFERENCES custom_fields(id),
    custom_field_02_id INTEGER REFERENCES custom_fields(id),
    -- ... (18 more columns)
    custom_field_20_id INTEGER REFERENCES custom_fields(id),

    integration_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, integration_id)
);
#### ETL Processing Flow
```python
class CustomFieldsTransformWorker:
    def process_jira_custom_fields(self, raw_data_id: int, tenant_id: int, integration_id: int):
        """Process Jira createmeta response to extract global custom fields"""

        # 1. Get raw createmeta data
        raw_data = self._get_raw_data(session, raw_data_id)
        projects_data = raw_data.get('projects', [])

        # 2. Collect all unique custom fields globally (not per project)
        global_custom_fields = {}  # field_key -> field_info

        for project_data in projects_data:
            issue_types = project_data.get('issuetypes', [])
            for issue_type in issue_types:
                fields = issue_type.get('fields', {})
                for field_key, field_info in fields.items():
                    if field_key.startswith('customfield_'):
                        # Keep first occurrence globally
                        if field_key not in global_custom_fields:
                            global_custom_fields[field_key] = field_info

        # 3. Process each unique custom field once
        for field_key, field_info in global_custom_fields.items():
            self._process_custom_field_data(
                field_key, field_info, tenant_id, integration_id
            )

    def _process_custom_field_data(self, field_key: str, field_info: dict,
                                   tenant_id: int, integration_id: int):
        """Create/update global custom field record"""
        field_name = field_info.get('name', '')
        field_type = field_info.get('schema', {}).get('type', 'string')
        operations = field_info.get('operations', [])

        # Insert or update in custom_fields table
        custom_field = {
            'external_id': field_key,
            'name': field_name,
            'field_type': field_type,
            'operations': json.dumps(operations),
            'tenant_id': tenant_id,
            'integration_id': integration_id
        }

        # Bulk insert with conflict handling
        BulkOperations.bulk_insert(session, 'custom_fields', [custom_field])
```
#### Work Items Processing with Custom Fields Mapping
```python
class WorkItemsTransformWorker:
    def process_work_items(self, raw_issues: list, tenant_id: int, integration_id: int):
        """Transform work items using custom fields mapping"""

        # 1. Get the custom fields mapping for this tenant/integration
        mapping = session.query(CustomFieldMapping).filter_by(
            tenant_id=tenant_id,
            integration_id=integration_id
        ).first()

        if not mapping:
            logger.warning(f"No custom fields mapping found for tenant {tenant_id}, integration {integration_id}")
            return

        # 2. Process each work item
        for raw_issue in raw_issues:
            work_item_data = self._extract_base_fields(raw_issue)

            # 3. Map custom fields using the direct FK mapping
            for i in range(1, 21):  # 20 custom field columns
                custom_field = getattr(mapping, f'custom_field_{i:02d}')
                if custom_field:
                    # Get the value from raw issue
                    field_value = raw_issue.get('fields', {}).get(custom_field.external_id)
                    if field_value is not None:
                        # Store in the corresponding work_item column
                        work_item_data[f'custom_field_{i:02d}'] = self._transform_field_value(
                            field_value, custom_field.field_type
                        )

            # 4. Bulk insert work item
            BulkOperations.bulk_insert(session, 'work_items', [work_item_data])
```

#### Enhanced Workflow Metrics Calculation

The transform worker calculates comprehensive workflow metrics from changelog data **in-memory** without querying the database:

```python
class TransformWorker:
    def _process_changelogs_data(self, db, issues_data, integration_id, tenant_id, statuses_map):
        """Process changelogs and calculate workflow metrics efficiently"""

        # 1. Build changelogs list (in-memory)
        changelogs_to_insert = []
        for issue in issues_data:
            for history in issue.get('changelog', {}).get('histories', []):
                # Process status transitions
                changelogs_to_insert.append({
                    'work_item_id': work_item_id,
                    'from_status_id': from_status_id,
                    'to_status_id': to_status_id,
                    'transition_start_date': start_date,
                    'transition_change_date': change_date,
                    'time_in_status_seconds': time_diff.total_seconds()
                })

        # 2. Bulk insert changelogs
        BulkOperations.bulk_insert(db, 'changelogs', changelogs_to_insert)

        # 3. Calculate workflow metrics from in-memory data (no DB query!)
        self._calculate_and_update_workflow_metrics(
            db, changelogs_to_insert, work_items_map, statuses_map, integration_id, tenant_id
        )

    def _calculate_enhanced_workflow_metrics(self, changelogs, status_categories):
        """Calculate 15 workflow metrics from changelog data"""

        metrics = {
            'work_first_committed_at': None,      # First transition to 'To Do'
            'work_first_started_at': None,        # First transition to 'In Progress'
            'work_last_started_at': None,         # Last transition to 'In Progress'
            'work_first_completed_at': None,      # First transition to 'Done'
            'work_last_completed_at': None,       # Last transition to 'Done'
            'total_work_starts': 0,               # Count of transitions to 'In Progress'
            'total_completions': 0,               # Count of transitions to 'Done'
            'total_backlog_returns': 0,           # Count of transitions to 'To Do'
            'total_work_time_seconds': 0.0,       # Time spent in 'In Progress'
            'total_review_time_seconds': 0.0,     # Time spent in 'To Do'
            'total_cycle_time_seconds': 0.0,      # First start → Last completion
            'total_lead_time_seconds': 0.0,       # First commit → Last completion
            'workflow_complexity_score': 0,       # (backlog_returns × 2) + (completions - 1)
            'rework_indicator': False,            # work_starts > 1
            'direct_completion': False            # Went straight to done
        }

        # Process changelogs and calculate metrics...
        return metrics
```

**Performance Benefits**:
- ✅ **No extra database queries** - all data already in memory
- ✅ **Single pass processing** - calculate metrics while processing changelogs
- ✅ **Bulk update** - update all work items in one operation
- ✅ **~50% faster** than old ETL service (which queried changelogs back from DB)

**Workflow Metrics Calculated**:
| Metric | Description |
|--------|-------------|
| `work_first_committed_at` | First time moved to "To Do" |
| `work_first_started_at` | First time work started |
| `work_last_started_at` | Most recent work start |
| `work_first_completed_at` | First time completed |
| `work_last_completed_at` | Most recent completion |
| `total_work_starts` | How many times work started |
| `total_completions` | How many times completed |
| `total_backlog_returns` | How many times returned to backlog |
| `total_work_time_seconds` | Time spent working |
| `total_review_time_seconds` | Time spent in review |
| `total_cycle_time_seconds` | Time from start to completion |
| `total_lead_time_seconds` | Time from commit to completion |
| `workflow_complexity_score` | Workflow complexity indicator |
| `rework_indicator` | Whether work was restarted |
| `direct_completion` | Completed without intermediate steps |

```
        return result
```

#### Database Schema for Custom Fields
```sql
-- Enhanced work_items table with custom fields support
ALTER TABLE work_items ADD COLUMN IF NOT EXISTS custom_field_01 TEXT;
ALTER TABLE work_items ADD COLUMN IF NOT EXISTS custom_field_02 TEXT;
-- ... up to custom_field_20
ALTER TABLE work_items ADD COLUMN IF NOT EXISTS custom_field_20 TEXT;

-- Project custom fields discovery cache
CREATE TABLE IF NOT EXISTS projects_custom_fields (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    project_key VARCHAR(50) NOT NULL,
    integration_type VARCHAR(50) NOT NULL,
    discovered_fields JSONB NOT NULL,
    discovered_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, project_key, integration_type)
);
```

### Data Extraction Strategy

#### Extract-Transform-Load Pattern
```python
class ETLDataProcessor:
    def __init__(self):
        self.extract_phase = DataExtractor()
        self.transform_phase = DataTransformer()
        self.load_phase = DataLoader()
    
    async def process_data(self, integration_config: dict):
        # EXTRACT: Store raw API responses
        raw_data = await self.extract_phase.extract_all_data(integration_config)
        await self.store_raw_data(raw_data)
        
        # TRANSFORM: Process and clean data
        transformed_data = await self.transform_phase.transform_data(raw_data)
        
        # LOAD: Bulk insert to final tables
        await self.load_phase.bulk_insert(transformed_data)
        
        # VECTORIZE: Queue for embedding generation
        await self.queue_vectorization(transformed_data)
```

#### Raw Data Preservation
```python
# Store exact API responses without manipulation
async def store_raw_extraction_data(self, project_id: str, payload: dict):
    """Store original full payload per project for complete data preservation"""
    raw_record = {
        "project_id": project_id,
        "extraction_type": "jira_issues",
        "raw_payload": payload,  # Exact API response
        "extracted_at": datetime.utcnow(),
        "payload_size": len(json.dumps(payload))
    }
    
    await self.db.insert("raw_extraction_data", raw_record)
    
    # Queue reference ID for processing (not full payload)
    await self.queue_processing_reference(raw_record["id"])
```

## 📊 ETL Monitoring & Analytics

### Job Performance Tracking

#### Execution Metrics
```python
class ETLMetrics:
    def __init__(self):
        self.metrics_collector = MetricsCollector()
    
    async def track_job_execution(self, job_id: int, metrics: dict):
        await self.metrics_collector.record({
            "job_id": job_id,
            "execution_time": metrics["duration"],
            "records_processed": metrics["record_count"],
            "errors_encountered": metrics["error_count"],
            "memory_usage": metrics["peak_memory"],
            "api_calls_made": metrics["api_calls"],
            "vectorization_queued": metrics["vectors_queued"]
        })
```

#### Queue Health Monitoring
```python
class QueueMonitor:
    def __init__(self):
        self.rabbitmq_client = RabbitMQClient()
    
    async def get_queue_health(self):
        return {
            "job_queue": await self.get_queue_stats("etl.jobs"),
            "vectorization_queue": await self.get_queue_stats("etl.vectorization"),
            "dead_letter_queue": await self.get_queue_stats("etl.failed"),
            "worker_status": await self.get_worker_status()
        }
```

## 🚀 Evolution Plan Implementation Status

### ✅ Phase 0: Foundation (COMPLETED)
- **Frontend ETL**: Modern React + TypeScript interface (Port 3333)
- **Backend ETL Module**: FastAPI endpoints at `/app/etl/*`
- **Basic Job Management**: Job cards, status tracking, manual controls

### ✅ Phase 1: Queue Infrastructure (COMPLETED)
- **RabbitMQ Integration**: Complete queue system with multiple queues
- **Raw Data Storage**: `raw_extraction_data` table for pure extraction
- **Queue Workers**: Background processing with retry logic
- **Extract → Transform → Load**: True ETL separation

### ✅ Phase 2: Jira Enhancement with Simplified Custom Fields (IMPLEMENTED)
- **Global Custom Fields**: Extract all custom fields globally from Jira `/createmeta` API (manual sync only)
- **Automatic ETL Jobs**: Use Jira `/project/search` API for regular job execution
- **Direct FK Mapping**: 20 FK columns in custom_fields_mapping table point directly to custom_fields
- **Tenant-Level Configuration**: One mapping configuration per tenant/integration
- **Simplified Processing**: Transform workers use direct FK relationships for mapping

#### Recent Bug Fixes & Improvements ✅
- **🔧 Data Truncation Fix**: Removed "Story" filter from Jira createmeta API calls to retrieve ALL issue types
- **🔧 WIT Deduplication**: Fixed transform worker to create 11 unique issue types instead of 86 duplicates
- **🔧 Project-WIT Relationships**: Fixed creation of 86 project-issuetype relationships
- **🔧 Import Error Fix**: Added missing `json` import in custom_fields.py
- **🔧 Migration Rollback**: Fixed foreign key constraint violations in migration rollbacks
- **📊 Debug Logging**: Added comprehensive logging for payload sizes and processing steps

#### Phase 2.1: Database Foundation ✅
- **Simplified Schema**: custom_fields table (global) + custom_fields_mapping table (20 FK columns)
- **Model Updates**: Updated unified models with direct FK relationships
- **Constraint Management**: Unique constraints on (tenant_id, integration_id, external_id)

#### Phase 2.2: Global Custom Fields Extraction ✅
- **Manual Sync Only**: Extract all custom fields from Jira `/createmeta` API (user-triggered)
- **Automatic Jobs**: Use Jira `/project/search` API for regular ETL job execution
- **Deduplication Logic**: Process each custom field only once across all projects
- **Raw Data Storage**: Store complete API responses for debugging/reprocessing

#### Phase 2.3: Transform & Load Processing ✅
- **Transform Workers**: Global custom fields processing with deduplication
- **Direct FK Mapping**: Use custom_fields_mapping table for tenant-specific field mapping
- **Bulk Operations**: Optimized bulk insert/update operations with conflict handling

### ✅ Phase 3: GitHub Enhancement (IMPLEMENTED)
- **Queue Migration**: All GitHub ETL logic migrated to queue architecture
- **Unified Management**: GitHub jobs managed through etl_jobs table
- **Performance Maintained**: Existing functionality preserved with improved architecture
- **Batched Processing**: 50 PRs per batch for memory optimization

### 🔄 Future Enhancements (Planned)
- **Additional Integrations**: Azure DevOps, Aha!, custom APIs
- **Advanced Analytics**: Data quality metrics, trend analysis
- **Webhook Support**: Real-time event processing
- **Enhanced AI Integration**: Improved vectorization and semantic search

## 📊 Architecture Benefits Achieved

### ✅ **Business Value Delivered**
- **Zero-Code Custom Fields**: UI-driven field management without deployments
- **Unlimited Scalability**: 20 optimized columns + unlimited JSON overflow
- **Project-Specific Configuration**: Custom field discovery per Jira project
- **Real-Time Monitoring**: Live job status and stage tracking

### ✅ **Technical Excellence**
- **True ETL Separation**: Extract → Transform → Load → Vectorize pipeline
- **Queue-Based Processing**: Scalable, resilient background processing
- **Optimized Performance**: Indexed JSON queries, bulk operations
- **Error Recovery**: Comprehensive retry logic and dead letter queues

### ✅ **Operational Excellence**
- **Unified Management**: Single interface for all ETL operations
- **Real-Time Updates**: WebSocket-based status tracking
- **Comprehensive Monitoring**: Queue health, job status, error tracking
- **Self-Healing**: Automatic retry and recovery mechanisms

## 🔧 Troubleshooting Guide

### Common Issues & Solutions

#### **Issue: ETL Job Stuck in RUNNING Status**

**Symptoms:**
- Job shows RUNNING status but no progress
- No new raw_extraction_data records being created
- Queue shows 0 consumers

**Diagnosis:**
```bash
# Check worker status
python -c "
import sys, os
sys.path.append('services/backend-service')
from app.workers.worker_manager import get_worker_manager
manager = get_worker_manager()
print(f'Workers running: {manager.running}')
print(f'Total workers: {len(manager.workers)}')
"

# Check queue status
python -c "
import sys, os
sys.path.append('services/backend-service')
from app.etl.queue.queue_manager import QueueManager
qm = QueueManager()
stats = qm.get_queue_stats('extraction_queue_premium')
print(f'Messages: {stats[\"message_count\"]}, Consumers: {stats[\"consumer_count\"]}')
"
```

**Solutions:**
1. **Restart Workers**: `manager.restart_all_workers()`
2. **Reset Job Status**: Update job status from RUNNING to READY
3. **Check Logs**: Look for worker crash errors in backend service logs

#### **Issue: Extraction Steps Not Happening**

**Symptoms:**
- Projects/statuses extraction completes
- Issues/changelogs extraction never starts
- Missing jira_issues_changelogs in raw_extraction_data

**Diagnosis:**
```bash
# Check raw data progression
python -c "
import sys, os
sys.path.append('services/backend-service')
from app.core.database import get_database
from sqlalchemy import text

database = get_database()
with database.get_read_session_context() as session:
    result = session.execute(text('SELECT type, COUNT(*) FROM raw_extraction_data WHERE tenant_id = 1 GROUP BY type'))
    for row in result:
        print(f'{row[0]}: {row[1]} records')
"
```

**Solutions:**
1. **Check Worker Logs**: Look for extraction worker errors
2. **Verify Integration**: Ensure integration is active and credentials valid
3. **Manual Queue Test**: Manually queue issues extraction message
4. **Restart ETL Job**: Reset job status and trigger new run

#### **Issue: Queue Messages Not Being Consumed**

**Symptoms:**
- Messages published to queue successfully
- Queue shows messages but 0 consumers
- Workers appear to be running but not processing

**Solutions:**
1. **Check RabbitMQ Connection**: Verify RabbitMQ is running on port 5672
2. **Restart Backend Service**: Workers start with backend service
3. **Check Database Connections**: Verify PostgreSQL connectivity
4. **Review Worker Threads**: Check if worker threads are alive

### Debugging Commands

#### **Check ETL Job Status**
```bash
curl -X GET "http://localhost:3001/app/etl/jobs?tenant_id=1" \
  -H "X-Internal-Auth: YOUR_INTERNAL_AUTH_KEY"
```

#### **Check Queue Health**
```bash
# RabbitMQ Management UI
http://localhost:15672
# Default: guest/guest
```

#### **Reset Stuck Job**
```bash
curl -X PUT "http://localhost:3001/app/etl/jobs/1/status" \
  -H "X-Internal-Auth: YOUR_INTERNAL_AUTH_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "READY"}'
```

#### **Manual Worker Restart**
```python
from app.workers.worker_manager import get_worker_manager
manager = get_worker_manager()
success = manager.restart_all_workers()
print(f"Restart success: {success}")
```

---

**The ETL & Queue system provides enterprise-grade data processing with dynamic custom fields, queue-based architecture, and comprehensive monitoring capabilities.**
