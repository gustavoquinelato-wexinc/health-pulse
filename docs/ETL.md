# ETL & QUEUE SYSTEM

**Comprehensive ETL Architecture with RabbitMQ Queue Management**

This document provides an overview of the ETL system architecture, job orchestration, queue management, and integration capabilities. For detailed job lifecycle information, see:

- **[ETL_JIRA_JOB_LIFECYCLE.md](ETL_JIRA_JOB_LIFECYCLE.md)** - Detailed Jira job lifecycle with 4-step extraction process
- **[ETL_GITHUB_JOB_LIFECYCLE.md](ETL_GITHUB_JOB_LIFECYCLE.md)** - Detailed GitHub job lifecycle with 2-step extraction and nested pagination

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
- **Transform Workers**: Router + specialized handlers for data cleaning, normalization, and custom field mapping
  - **TransformWorker**: Queue consumer and router (routes to provider-specific handlers)
  - **JiraTransformHandler**: Jira-specific data processing (custom fields, statuses, issues, dev status)
  - **GitHubTransformHandler**: GitHub-specific data processing (repositories, PRs, nested entities)
- **Load Workers**: Optimized bulk loading to final tables
- **Vector Workers**: Embedding generation and vector database operations

#### ✅ **Dynamic Custom Fields System**
- **UI-Driven Configuration**: Custom field mapping without code changes
- **Project-Specific Discovery**: Automatic field discovery per Jira project
- **Optimized Storage**: 20 dedicated columns + unlimited JSON overflow
- **Performance Optimized**: Indexed JSON queries for overflow fields

#### ✅ **Provider-Centric Code Organization**
The ETL codebase is organized by provider with clear separation of concerns:

```
services/backend-service/app/etl/
├── workers/                           # Generic worker infrastructure
│   ├── base_worker.py                # Base class for all workers
│   ├── worker_status_manager.py      # Reusable status update component
│   ├── queue_manager.py              # RabbitMQ queue management
│   ├── bulk_operations.py            # Bulk database operations
│   ├── worker_manager.py             # Worker lifecycle management
│   ├── extraction_worker_router.py   # Routes extraction messages to providers
│   ├── transform_worker_router.py    # Routes transform messages to providers
│   └── embedding_worker_router.py    # Generic embedding worker (provider-agnostic)
│
├── jira/                              # Jira-specific integration
│   ├── client.py                     # Jira API client
│   ├── custom_fields.py              # Custom fields discovery & mapping
│   ├── jira_extraction_worker.py     # Jira extraction logic
│   ├── jira_transform_worker.py      # Jira transform logic
│   └── jira_embedding_worker.py      # Jira mapping tables embedding API
│
└── github/                            # GitHub-specific integration
    ├── graphql_client.py             # GitHub GraphQL client
    ├── github_extraction_worker.py   # GitHub extraction logic
    └── github_transform_worker.py    # GitHub transform logic
```

**Architecture Benefits:**
- **Separation of Concerns**: Generic router vs. provider-specific logic
- **Maintainability**: Each provider's code in one dedicated folder
- **Scalability**: Easy to add new providers (e.g., GitLab, Azure DevOps)
- **Consistency**: All providers follow the same worker pattern
- **Clarity**: Clear file organization makes navigation intuitive

**WorkerStatusManager Pattern:**
- **Composition over Inheritance**: Reusable component for status updates
- **Dependency Injection**: Routers inject `status_manager` into provider-specific workers/handlers
- **No Code Duplication**: Single source of truth for WebSocket status updates
- **Flexible**: Any worker can use WorkerStatusManager without inheritance
- **Usage**:
  - `BaseWorker` creates `WorkerStatusManager` instance in `__init__`
  - Routers pass `self.status_manager` to provider workers/handlers
  - Workers/handlers call `self.status_manager.send_worker_status()` to send updates

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

### 🔑 Token Mechanism for Job Tracking

Every ETL job uses a **unique token (UUID)** that is generated at job start and forwarded through the entire pipeline for job tracking and correlation:

**Token Lifecycle:**
1. **Generation**: Token created in `etl/jobs.py` when job starts (stored in `etl_jobs.status->token`)
2. **Forwarding**: Token included in EVERY message through all stages:
   - Extraction → Transform queue
   - Transform → Embedding queue
   - Nested extraction jobs (GitHub pagination)
   - Dev status extraction (Jira step 4)
3. **Usage**: Workers use token for:
   - Job correlation across logs
   - Tracking message flow through pipeline
   - Debugging multi-step jobs
   - Ensuring message integrity

**Token in Message Structure:**
```python
# All messages include token
message = {
    'tenant_id': 1,
    'job_id': 123,
    'token': '6f0fa209-3c3e-4e21-9bbe-ecff52563b61',  # 🔑 Unique job token
    'type': 'jira_dev_status',
    'first_item': True,
    'last_item': False,
    # ... other fields
}
```

**Critical Rule**: Token MUST be forwarded in ALL queue messages:
- ✅ Extraction → Transform: Include `token` parameter
- ✅ Transform → Embedding: Include `token` parameter
- ✅ Nested extraction (GitHub): Include `token` parameter
- ✅ Dev status extraction (Jira): Include `token` parameter

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
  "token": "6f0fa209-3c3e-4e21-9bbe-ecff52563b61",
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
  "token": "6f0fa209-3c3e-4e21-9bbe-ecff52563b61",
  "raw_data_id": 789
}
```

#### Embedding Worker Message
```json
{
  "tenant_id": 1,
  "table_name": "work_items",
  "external_id": "PROJ-123",
  "job_id": 123,
  "type": "jira_dev_status",
  "first_item": false,
  "last_item": true,
  "last_job_item": true,
  "token": "6f0fa209-3c3e-4e21-9bbe-ecff52563b61"
}
```

**Key Message Structure:**
- **Orchestration Flags**: `first_item`, `last_item`, `last_job_item` are always included for proper worker status updates
- **Worker Status**: Workers set themselves to "running" on `first_item=true` and "finished" on `last_item=true`
- **Job Completion**: Only the final message with `last_job_item=true` triggers job completion
- **Data References**: Extraction→Transform uses `raw_data_id`, Transform→Embedding uses `external_id`
- **Token Forwarding**: `token` (UUID) is generated at job start and forwarded through ALL stages (extraction → transform → embedding) for job tracking and correlation

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

## � Generic Job Lifecycle Rules

### Job Status Structure

Each ETL job maintains a comprehensive JSON status structure:

```json
{
  "overall": "READY|RUNNING|FINISHED|FAILED",
  "steps": {
    "step_name": {
      "order": 1,
      "display_name": "Step Display Name",
      "extraction": "idle|running|finished|failed",
      "transform": "idle|running|finished|failed",
      "embedding": "idle|running|finished|failed"
    }
  }
}
```

### Data Flow Rules: Extraction → Transform → Embedding

#### Rule 1: One raw_data_id Per Logical Unit

Extraction creates one raw_data_id per logical unit. For specific examples, see:
- [ETL_JIRA_JOB_LIFECYCLE.md](ETL_JIRA_JOB_LIFECYCLE.md) - Jira raw_data_id structure
- [ETL_GITHUB_JOB_LIFECYCLE.md](ETL_GITHUB_JOB_LIFECYCLE.md) - GitHub raw_data_id structure

#### Rule 2: Transform Processes One raw_data_id Per Message

**Transform worker receives one message per raw_data_id:**
1. Fetches raw_extraction_data using raw_data_id
2. Parses and transforms the data
3. Inserts/updates entities in final tables
4. **CRITICAL**: Does NOT immediately queue to embedding
5. Waits for `last_item=True` to know when to queue

#### Rule 3: Transform Queues to Embedding on last_item=True

**When transform receives last_item=True:**
1. It has processed all raw_data_ids for this step
2. It queries the database for ALL distinct entities of this type
3. It queues EACH distinct entity to embedding with proper flags:
   - First entity: `first_item=True, last_item=False`
   - Middle entities: `first_item=False, last_item=False`
   - Last entity: `first_item=False, last_item=True`

#### Rule 4: Embedding Processes One external_id Per Message

**Embedding worker receives one message per external_id:**
1. Fetches entity from final table using external_id
2. Extracts text for vectorization
3. Stores vectors in Qdrant
4. Sends WebSocket status on first_item=True and last_item=True

#### Rule 5: Flag Propagation

**Flags flow through the pipeline:**
- Extraction → Transform: `first_item`, `last_item`, `last_job_item`
- Transform → Embedding: `first_item`, `last_item`, `last_job_item`
- **EXCEPTION**: Transform may recalculate `first_item` and `last_item` when queuing multiple entities to embedding

### Extraction Worker Architecture

#### Router Pattern (ExtractionWorkerRouter)

**ExtractionWorkerRouter** acts as the queue consumer and router:
1. Consumes messages from tier-based extraction queues
2. Routes messages to provider-specific workers based on `provider` field:
   - `provider: 'jira'` → **JiraExtractionWorker**
   - `provider: 'github'` → **GitHubExtractionWorker**
3. Sends "running" status when `first_item=True` (via router)
4. Provider-specific workers send "finished" status when extraction completes

#### Worker Pattern (JiraExtractionWorker, GitHubExtractionWorker)

**Specialized Workers** handle provider-specific extraction logic:
- **JiraExtractionWorker**: Processes all Jira extraction types
  - `jira_projects_and_issue_types` → Extracts projects and issue types, sends "finished" status
  - `jira_statuses_and_relationships` → Extracts statuses, sends "finished" status
  - `jira_issues_with_changelogs` → Extracts issues, sends "finished" status
  - `jira_dev_status` → Extracts dev status per issue, sends "finished" when `last_item=True`

- **GitHubExtractionWorker**: Processes all GitHub extraction types
  - `github_repositories` → Extracts all repos, sends "finished" after LOOP 1 + LOOP 2
  - `github_prs_commits_reviews_comments` → Extracts PRs with nested data, sends "finished" on final page

Both workers receive **WorkerStatusManager** via dependency injection:
- `status_manager` - Injected by ExtractionWorkerRouter for sending WebSocket status updates
- Workers use `self.status_manager.send_worker_status()` to send "finished" status
- Each worker knows when its extraction is complete and sends status accordingly

**Architecture Pattern:**
- **Composition over Inheritance**: Workers don't inherit from BaseWorker
- **Dependency Injection**: Router injects `status_manager` into workers
- **WorkerStatusManager**: Reusable component for status updates without inheritance
- **Provider-Specific Completion Logic**: Each worker controls when to send "finished" status

### Transform Worker Architecture

#### Router Pattern (TransformWorker)

**TransformWorker** acts as the queue consumer and router:
1. Consumes messages from tier-based transform queues
2. Routes messages to provider-specific handlers based on message type prefix:
   - `jira_*` messages → **JiraTransformHandler**
   - `github_*` messages → **GitHubTransformHandler**
3. Handles WebSocket status updates for first_item and last_item
4. Manages job status updates in database

#### Handler Pattern (JiraTransformHandler, GitHubTransformHandler)

**Specialized Handlers** process provider-specific logic:
- **JiraTransformHandler**: Processes all Jira message types
  - `jira_custom_fields` → `_process_jira_custom_fields()`
  - `jira_special_fields` → `_process_jira_special_fields()`
  - `jira_projects_and_issue_types` → `_process_jira_project_search()`
  - `jira_statuses_and_project_relationships` → `_process_jira_statuses_and_project_relationships()`
  - `jira_issues_with_changelogs` → `_process_jira_single_issue_changelog()`
  - `jira_dev_status` → `_process_jira_dev_status()`

- **GitHubTransformHandler**: Processes all GitHub message types
  - `github_repositories` → `_process_github_repositories()`
  - `github_prs` / `github_prs_commits_reviews_comments` → `_process_github_prs()`
  - `github_prs_nested` → `_process_github_prs_nested()`

Both handlers receive **WorkerStatusManager** via dependency injection:
- `status_manager` - Injected by TransformWorkerRouter for sending WebSocket status updates
- Handlers use `self.status_manager.send_worker_status()` to send status updates
- Database session management via `get_db_session()` and `get_db_read_session()`

**Architecture Pattern:**
- **Composition over Inheritance**: Handlers don't inherit from BaseWorker
- **Dependency Injection**: Router injects `status_manager` into handlers
- **WorkerStatusManager**: Reusable component for status updates without inheritance

### Transform Worker Rules

#### Message Processing

**For Regular Messages (raw_data_id != None)**
1. Fetch raw_extraction_data from database using raw_data_id
2. Parse and transform the data
3. Insert/update entities in final tables
4. Queue to embedding with SAME flags: `first_item`, `last_item`, `last_job_item`
5. Send WebSocket status updates:
   - If `first_item=True`: send "running" status
   - If `last_item=True`: send "finished" status

**For Completion Messages (raw_data_id == None)**
1. Recognize as completion marker
2. Send "finished" status (because `last_item=True`)
3. Forward to embedding with SAME flags: `first_item`, `last_item`, `last_job_item`
4. Do NOT process any data (no database operations)

#### Flag Forwarding Rules

Transform ALWAYS forwards flags as-is to embedding:
- `first_item` → `first_item`
- `last_item` → `last_item`
- `last_job_item` → `last_job_item`

This ensures embedding worker knows when to send status updates and when to complete the job.

### Embedding Worker Rules

#### Message Processing

**For Regular Messages (external_id != None)**
1. Fetch entities from final tables using external_id
2. Extract text for vectorization
3. Store vectors in Qdrant
4. Update qdrant_vectors bridge table
5. Send WebSocket status updates:
   - If `first_item=True`: send "running" status
   - If `last_item=True`: send "finished" status

**For Completion Messages (external_id == None)**
1. Recognize as completion marker
2. Send "finished" status (because `last_item=True`)
3. If `last_job_item=True`: call `_complete_etl_job()`
   - Sets overall job status to FINISHED
   - Updates last_run_finished_at timestamp
4. Do NOT process any data (no database operations)

#### Job Completion Logic

Only triggered when `last_job_item=True`:
- Sets overall status to FINISHED
- Sets `reset_deadline` = current time + 30 seconds (ISO timestamp)
- Sets `reset_attempt` = 0
- Updates last_run_finished_at timestamp
- Updates last_sync_date with provided value
- Schedules delayed task to check job completion and reset to READY

#### System-Level Reset Countdown

After job completion, the system uses a **backend-managed countdown** (not UI-managed):

**Flow:**
1. **Job Finishes**: Embedding worker calls `complete_etl_job()`:
   - Sets `reset_deadline` = now + 30 seconds
   - Sets `reset_attempt` = 0
   - Schedules delayed task via `job_reset_scheduler.py` using `threading.Timer`

2. **Scheduled Check** (after 30s): Backend runs `reset_check_task()`:
   - Verifies all steps are finished
   - Checks all queues (extraction, transform, embedding) for remaining messages with job token
   - **If work remains**:
     - Extends deadline with exponential backoff (60s, 180s, 300s)
     - Updates database with new `reset_deadline`
     - Does NOT send WebSocket (workers send their own status updates)
     - Schedules next check using `threading.Timer`
   - **If all complete**:
     - Resets job to READY, all steps to 'idle'
     - Sends WebSocket update to notify UI

3. **UI Countdown**: Frontend receives `reset_deadline` via WebSocket:
   ```json
   {
     "overall": "FINISHED",
     "token": "uuid-token",
     "reset_deadline": "2025-11-13T10:30:00",
     "reset_attempt": 0,
     "steps": { ... }
   }
   ```
   - Calculates remaining time: `deadline - current_time`
   - Displays "Resetting in 30s", "Resetting in 29s", etc.
   - All users see the same countdown (system-level, not per-session)

**Key Benefits:**
- **System-level**: Countdown stored in database, not browser
- **Multi-user sync**: All users see the same countdown
- **Works offline**: Resets even when no users are logged in
- **Exponential backoff**: Automatically extends if work remains
- **Reliable execution**: Uses `threading.Timer` instead of asyncio tasks for guaranteed execution
- **No race conditions**: Reset scheduler doesn't overwrite worker status updates

### WebSocket Status Updates

#### When Status Updates Are Sent

Status updates are sent ONLY when:
- `first_item=True` → Send "running" status
- `last_item=True` → Send "finished" status

#### Why Not on Every Message?

- Regular messages have `first_item=False, last_item=False`
- These don't trigger WebSocket updates
- Only the first and last messages of a step trigger updates
- This prevents UI flickering and reduces WebSocket traffic

## �🔌 Integration Management

### Supported Integrations

#### 1. Jira Integration

Jira integration supports:
- **4-step sequential extraction**: Projects → Statuses → Issues → Dev Status
- **Custom fields discovery**: Automatic detection of project-specific custom fields
- **Incremental sync**: Filters by last_sync_date to process only new/updated data
- **Batch processing**: Configurable batch sizes for API efficiency
- **Rate limiting**: Automatic rate limit handling with checkpoint recovery

For detailed job lifecycle, see [ETL_JIRA_JOB_LIFECYCLE.md](ETL_JIRA_JOB_LIFECYCLE.md)

#### 2. GitHub Integration

GitHub integration supports:
- **2-step extraction**: Repositories → PRs with nested data (commits, reviews, comments)
- **GraphQL-based extraction**: Efficient single query for all entity types
- **Nested pagination**: Handles PRs with >10 commits, reviews, or comments
- **Incremental sync**: Filters PRs by updatedAt to reduce API quota usage
- **Rate limit recovery**: Checkpoint-based recovery with cursor tracking

For detailed job lifecycle, see [ETL_GITHUB_JOB_LIFECYCLE.md](ETL_GITHUB_JOB_LIFECYCLE.md)

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

The transform worker processes custom fields in two stages:

1. **Global Custom Fields Discovery**: Extract all unique custom fields from Jira API responses
2. **Tenant-Specific Mapping**: Apply custom_fields_mapping configuration to map fields to work_items columns

This separation allows:
- Global field discovery without code changes
- Per-tenant field configuration via UI
- Efficient bulk operations for data loading

#### Enhanced Workflow Metrics Calculation

The transform worker calculates comprehensive workflow metrics from changelog data **in-memory** without querying the database:

**Performance Benefits**:
- ✅ **No extra database queries** - all data already in memory
- ✅ **Single pass processing** - calculate metrics while processing changelogs
- ✅ **Bulk update** - update all work items in one operation
- ✅ **~50% faster** than legacy ETL service

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

The ETL system follows a strict separation of concerns:

1. **Extract**: Store raw API responses in `raw_extraction_data` table without manipulation
2. **Transform**: Process and clean data, apply custom field mappings, calculate metrics
3. **Load**: Bulk insert to final business tables
4. **Vectorize**: Queue for embedding generation and vector database storage

#### Raw Data Preservation

All API responses are stored exactly as received for:
- Complete data preservation and auditability
- Ability to reprocess data without re-fetching from APIs
- Debugging and troubleshooting
- Compliance and data governance

## 📊 ETL Monitoring & Analytics

### Job Performance Tracking

The system tracks:
- **Execution metrics**: Duration, records processed, errors, memory usage
- **API metrics**: API calls made, rate limit hits, recovery attempts
- **Vectorization metrics**: Vectors queued, embedding generation time

### Queue Health Monitoring

RabbitMQ monitoring provides:
- **Queue statistics**: Message count, consumer count, throughput
- **Worker status**: Active workers, processing rate, error rate
- **Dead letter queue**: Failed messages for manual review and recovery

## 🚀 Capabilities & Features

### ✅ Core ETL Capabilities

**Extract Stage**
- Pure data extraction from external APIs (Jira, GitHub)
- Raw data preservation without manipulation
- API rate limiting and checkpoint recovery
- Cursor-based pagination for large datasets

**Transform Stage**
- Data cleaning and normalization
- Custom field mapping and processing
- Workflow metrics calculation from changelog data
- Bulk operations for performance

**Load Stage**
- Optimized bulk loading to final tables
- Relationship mapping and foreign key management
- Transaction handling and error recovery

**Vectorization Stage**
- Embedding generation for semantic search
- Vector database storage (Qdrant)
- Bridge table tracking for PostgreSQL ↔ Qdrant mapping
- Multi-agent architecture with source filtering

### ✅ Integration Capabilities

**Jira Integration**
- 4-step sequential extraction (Projects → Statuses → Issues → Dev Status)
- Custom fields discovery and mapping
- Incremental sync with last_sync_date filtering
- Batch processing with configurable sizes
- Rate limit handling with checkpoint recovery

**GitHub Integration**
- 2-step extraction (Repositories → PRs with nested data)
- GraphQL-based extraction for efficiency
- Nested pagination for complex PR data
- Incremental sync with updatedAt filtering
- Rate limit recovery with cursor tracking

### ✅ Custom Fields System

- **Global Discovery**: Automatic detection of all custom fields
- **Tenant Configuration**: Per-tenant/integration field mapping via UI
- **20 Optimized Columns**: Direct FK mapping to custom_fields table
- **JSON Overflow**: Unlimited additional fields in JSON column
- **Zero-Code Management**: UI-driven configuration without deployments

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
