# ETL & QUEUE SYSTEM

**Comprehensive ETL Architecture with RabbitMQ Queue Management**

This document covers the complete ETL system architecture, job orchestration, queue management, and integration capabilities for Jira, GitHub, and custom data sources.

## 🏗️ ETL Architecture Overview

### Modern Queue-Based ETL Architecture (Current)

The ETL system uses a modern, queue-based architecture with complete Extract → Transform → Load separation:

```
┌─────────────────┐    API Calls    ┌─────────────────┐    Queue Msgs    ┌─────────────────┐
│  ETL Frontend   │─────────────────►│ Backend Service │─────────────────►│   RabbitMQ      │
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

### Enhanced ETL Job Lifecycle with Queue Integration

```
NOT_STARTED ──► READY ──► EXTRACT ──► TRANSFORM ──► LOAD ──► VECTORIZE ──► COMPLETED
     │            │         │           │           │          │            │
     │            │         │           │           │          │            │
     ▼            ▼         ▼           ▼           ▼          ▼            ▼
  Waiting     Queued    Raw Data    Clean Data   Final DB   Embeddings   Next Job
  Manual      Auto      Storage     Transform    Tables     Generated    Cycle
  Trigger     Execute   Queue       Queue        Queue      Queue        Continue
```

### Queue-Based Processing Stages

#### 1. **Extract Stage**
- **Purpose**: Pure data extraction from external APIs
- **Queue**: `etl.extract`
- **Output**: Raw data stored in `raw_extraction_data` table
- **Features**: API rate limiting, cursor management, checkpoint recovery

#### 2. **Transform Stage**
- **Purpose**: Data cleaning, normalization, and custom field mapping
- **Queue**: `etl.transform`
- **Input**: Raw data from extract stage
- **Output**: Cleaned, mapped data ready for loading
- **Features**: Dynamic custom field processing, data validation

#### 3. **Load Stage**
- **Purpose**: Bulk loading to final database tables
- **Queue**: `etl.load`
- **Input**: Transformed data from transform stage
- **Output**: Data in final business tables (issues, work_items, etc.)
- **Features**: Optimized bulk operations, relationship mapping

#### 4. **Vectorization Stage**
- **Purpose**: Generate embeddings for semantic search
- **Queue**: `etl.vectorization`
- **Input**: Final loaded data
- **Output**: Vector embeddings in Qdrant database
- **Features**: AI provider integration, batch processing

### Job States & Transitions

#### Job States
- **NOT_STARTED**: Initial state, waiting for trigger
- **READY**: Queued for execution, will auto-execute
- **RUNNING**: Currently executing with progress tracking
- **COMPLETED**: Successfully finished
- **FAILED**: Error occurred, requires attention
- **PAUSED**: Temporarily disabled (skipped in orchestration)

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
        
        # Find next job with NOT_STARTED status
        next_job = None
        for job in active_jobs:
            if job.status == "NOT_STARTED":
                next_job = job
                break
        
        # If no NOT_STARTED jobs, cycle back to first
        if not next_job and active_jobs:
            next_job = active_jobs[0]
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
        
        # Execute job with progress tracking
        await self.run_job_with_progress(job)
```

### Progress Tracking System

#### 5-Step Progress Model
Each ETL job shows clear progress through 5 distinct phases at 20% each:

```python
class ETLProgress:
    STEPS = [
        {"name": "Issue Types & Projects", "percentage": 20},
        {"name": "Statuses & Projects", "percentage": 40},
        {"name": "Issues Fetching", "percentage": 60},
        {"name": "Issues & Changelogs Processing", "percentage": 80},
        {"name": "Dev Status Processing", "percentage": 100}
    ]
    
    async def update_progress(self, job_id: int, step: int, detail: str = ""):
        progress_data = {
            "job_id": job_id,
            "step": step,
            "percentage": self.STEPS[step-1]["percentage"],
            "step_name": self.STEPS[step-1]["name"],
            "detail": detail,
            "timestamp": datetime.utcnow()
        }
        
        # Update database
        await self.update_job_progress(job_id, progress_data)
        
        # Send real-time update to frontend
        await self.broadcast_progress(progress_data)
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

#### Vectorization Message
```json
{
  "entity_type": "issue",
  "entity_id": "PROJ-123",
  "tenant_id": 1,
  "table_name": "issues",
  "content": "Issue title and description text...",
  "metadata": {
    "project_id": 789,
    "integration_type": "jira",
    "custom_fields": {"priority": "high"}
  },
  "embedding_config": {
    "model": "text-embedding-ada-002",
    "provider": "openai"
  }
}
```

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
            
            # Execute ETL job with progress tracking
            await self.execute_etl_job(message)
            
            # Set job status to COMPLETED
            await self.update_job_status(job_id, "COMPLETED")
            
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
```python
class JiraIntegration:
    def __init__(self, config: dict):
        self.base_url = config["base_url"]
        self.username = config["username"]
        self.api_token = config["api_token"]
        self.projects = config.get("projects", [])
    
    async def sync_data(self, job_config: dict):
        # Step 1: Issue types and projects (20%)
        await self.sync_issue_types()
        await self.update_progress(1)
        
        # Step 2: Statuses and projects (40%)
        await self.sync_statuses()
        await self.update_progress(2)
        
        # Step 3: Issues fetching (60%)
        await self.sync_issues(batch_size=job_config.get("batch_size", 50))
        await self.update_progress(3)
        
        # Step 4: Issues & changelogs processing (80%)
        await self.process_changelogs()
        await self.update_progress(4)
        
        # Step 5: Dev status processing (100%)
        await self.process_dev_status()
        await self.update_progress(5)
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

### Dynamic Custom Fields System

#### UI-Driven Custom Field Management

The ETL system includes a comprehensive custom fields management system that allows users to configure field mappings through the UI without code changes.

```
┌─────────────────────────────────────────────────────────────────┐
│                Custom Fields Management UI                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📋 Project Discovery    🎯 Field Mapping    💾 Storage Config  │
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │ Auto-discover   │    │ Drag & Drop     │    │ 20 Columns  │  │
│  │ custom fields   │───►│ field mapping   │───►│ + JSON      │  │
│  │ per project     │    │ to columns      │    │ overflow    │  │
│  └─────────────────┘    └─────────────────┘    └─────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Custom Fields Discovery Engine
```python
class CustomFieldsDiscoveryEngine:
    def __init__(self, integration_type: str):
        self.integration_type = integration_type
        self.max_dedicated_columns = 20

    async def discover_project_fields(self, project_key: str):
        """Discover custom fields using Jira createmeta API"""
        if self.integration_type == "jira":
            # Use createmeta for project-specific field discovery
            response = await self.jira_client.get(
                f"/rest/api/3/issue/createmeta?projectKeys={project_key}&expand=projects.issuetypes.fields"
            )

            fields = []
            for project in response["projects"]:
                for issue_type in project["issuetypes"]:
                    for field_id, field_data in issue_type["fields"].items():
                        if field_id.startswith("customfield_"):
                            fields.append({
                                "field_id": field_id,
                                "field_name": field_data["name"],
                                "field_type": field_data["schema"]["type"],
                                "description": field_data.get("description", ""),
                                "required": field_data.get("required", False),
                                "possible_values": self._extract_allowed_values(field_data)
                            })

            return self._deduplicate_fields(fields)

    async def store_field_mappings(self, tenant_id: int, project_id: str, mappings: List[dict]):
        """Store UI-configured field mappings"""
        dedicated_mappings = mappings[:self.max_dedicated_columns]
        overflow_mappings = mappings[self.max_dedicated_columns:]

        mapping_config = {
            "dedicated_columns": {
                f"custom_field_{i+1:02d}": mapping
                for i, mapping in enumerate(dedicated_mappings)
            },
            "overflow_fields": overflow_mappings,
            "last_updated": datetime.utcnow().isoformat(),
            "updated_by": "ui_configuration"
        }

        # Store in integrations table custom_field_mappings column
        await self.db.execute(
            """
            UPDATE integrations
            SET custom_field_mappings = :mappings
            WHERE tenant_id = :tenant_id AND project_id = :project_id
            """,
            {"mappings": json.dumps(mapping_config), "tenant_id": tenant_id, "project_id": project_id}
        )
```

#### Transform Worker with Dynamic Field Processing
```python
class CustomFieldTransformWorker:
    async def process_custom_fields(self, raw_issue: dict, field_mappings: dict):
        """Transform custom fields based on UI configuration"""
        result = {}

        # Process dedicated columns (optimized access)
        for column_name, mapping in field_mappings["dedicated_columns"].items():
            field_id = mapping["field_id"]
            field_value = raw_issue.get("fields", {}).get(field_id)

            if field_value is not None:
                # Apply field-specific transformation
                result[column_name] = self._transform_field_value(
                    field_value,
                    mapping["field_type"]
                )

        # Process overflow fields (JSON storage)
        overflow_data = {}
        for mapping in field_mappings["overflow_fields"]:
            field_id = mapping["field_id"]
            field_value = raw_issue.get("fields", {}).get(field_id)

            if field_value is not None:
                overflow_data[mapping["field_name"]] = self._transform_field_value(
                    field_value,
                    mapping["field_type"]
                )

        if overflow_data:
            result["custom_fields_overflow"] = json.dumps(overflow_data)

        return result
```

#### Database Schema for Custom Fields
```sql
-- Enhanced work_items table with custom fields support
ALTER TABLE work_items ADD COLUMN IF NOT EXISTS custom_field_01 TEXT;
ALTER TABLE work_items ADD COLUMN IF NOT EXISTS custom_field_02 TEXT;
-- ... up to custom_field_20
ALTER TABLE work_items ADD COLUMN IF NOT EXISTS custom_field_20 TEXT;
ALTER TABLE work_items ADD COLUMN IF NOT EXISTS custom_fields_overflow JSONB;

-- Index for JSON queries on overflow
CREATE INDEX IF NOT EXISTS idx_work_items_custom_overflow_gin
ON work_items USING GIN (custom_fields_overflow);

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
- **ETL Frontend**: Modern React + TypeScript interface (Port 5174)
- **Backend ETL Module**: FastAPI endpoints at `/app/etl/*`
- **Basic Job Management**: Job cards, status tracking, manual controls

### ✅ Phase 1: Queue Infrastructure (COMPLETED)
- **RabbitMQ Integration**: Complete queue system with multiple queues
- **Raw Data Storage**: `raw_extraction_data` table for pure extraction
- **Queue Workers**: Background processing with retry logic
- **Extract → Transform → Load**: True ETL separation

### ✅ Phase 2: Jira Enhancement with Dynamic Custom Fields (IMPLEMENTED)
- **UI-Driven Configuration**: Custom field mapping through web interface
- **Project-Specific Discovery**: Automatic field discovery using Jira createmeta API
- **Optimized Storage**: 20 dedicated columns + unlimited JSON overflow
- **Dynamic Processing**: Transform workers adapt to UI configuration

#### Phase 2.1: Database Foundation & UI Management ✅
- **Enhanced Schema**: Custom field columns and overflow support
- **Model Updates**: Unified models across all services
- **Management UI**: Custom field discovery and mapping interfaces

#### Phase 2.2: Enhanced Extraction with Discovery ✅
- **Discovery Jobs**: Project-specific custom field discovery
- **Enhanced Extraction**: Dynamic field lists based on UI mappings
- **etl_jobs Integration**: Unified job management through etl_jobs table

#### Phase 2.3: Transform & Load Processing ✅
- **Transform Workers**: Dynamic custom field mapping in queue workers
- **Load Workers**: Optimized storage with mapped columns + JSON overflow
- **Progress Tracking**: Real-time job progress with WebSocket updates

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
- **Real-Time Monitoring**: Live job progress and status tracking

### ✅ **Technical Excellence**
- **True ETL Separation**: Extract → Transform → Load → Vectorize pipeline
- **Queue-Based Processing**: Scalable, resilient background processing
- **Optimized Performance**: Indexed JSON queries, bulk operations
- **Error Recovery**: Comprehensive retry logic and dead letter queues

### ✅ **Operational Excellence**
- **Unified Management**: Single interface for all ETL operations
- **Real-Time Updates**: WebSocket-based progress tracking
- **Comprehensive Monitoring**: Queue health, job status, error tracking
- **Self-Healing**: Automatic retry and recovery mechanisms

---

**The ETL & Queue system provides enterprise-grade data processing with dynamic custom fields, queue-based architecture, and comprehensive monitoring capabilities.**
