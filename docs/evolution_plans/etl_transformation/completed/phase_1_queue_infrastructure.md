# ETL Phase 1: Queue Infrastructure & Raw Data Storage

**Status**: ✅ COMPLETE
**Documentation**: ✅ COMPLETE
**Implementation**: ✅ COMPLETE
**Duration**: 1 session (estimated: 1 week)
**Priority**: HIGH
**Risk Level**: LOW
**Completed**: 2025-09-30

## 📊 Prerequisites (Phase 0 - COMPLETE ✅)

Before starting Phase 1, the following must be in place:

1. ✅ **ETL Frontend Created**: React SPA running on port 3333
2. ✅ **Backend ETL Module**: `services/backend-service/app/etl/` structure exists
3. ✅ **Management APIs Working**: WITs, Statuses, Workflows, Integrations, Qdrant
4. ✅ **Frontend-Backend Communication**: HTTP/REST working correctly
5. ✅ **Authentication**: Tenant isolation and JWT auth functional
6. ✅ **RabbitMQ Running**: Already configured in docker-compose.yml (both files)

**All prerequisites are met. Ready to proceed with Phase 1.**

## 💼 Business Outcome

**Queue-Based ETL Foundation**: Establish RabbitMQ message queue infrastructure and raw data storage capabilities, enabling asynchronous job processing and complete API response preservation for debugging and reprocessing.

**Key Principle**: Separate storage (database) from queuing (RabbitMQ)
- **Database**: Stores complete API responses for debugging, reprocessing, audit trail
- **RabbitMQ**: Queues small messages (just IDs) for async work coordination

## 🎯 Objectives

1. ✅ **RabbitMQ Infrastructure**: Already in Docker Compose - verify configuration
2. **Database Schema**: Create `raw_extraction_data` table (RabbitMQ handles queue state internally)
3. **Unified Models**: Copy ETL service unified_models.py to backend-service for consistency
4. **Queue Manager**: Implement RabbitMQ connectivity and message publishing
5. **Raw Data APIs**: Create endpoints for storing and retrieving raw extraction data
6. **Queue Topology**: Establish extract/transform/load queue structure

## 🚫 What We're NOT Doing

- ❌ NO `etl_job_queue` database table (RabbitMQ manages queue state)
- ❌ NO `/api` subfolder in `app/etl/` (already all APIs)
- ❌ NO separate `etl_schemas.py` file (define schemas inline)
- ❌ NO item-by-item queuing (use batch-based approach)
- ❌ NO modifying ETL service jobs (Phase 2)

## 🤔 Why `raw_extraction_data` Table?

**Question**: "Why do we need a database table if RabbitMQ handles the queue?"

**Answer**: Different purposes - separation of concerns!

### RabbitMQ (Queue Management)
- **Purpose**: Coordinate async work
- **Stores**: Small messages with IDs (4 bytes)
- **Good at**: Fast message delivery, retries, priorities
- **Bad at**: Storing large data, querying, debugging

### Database (Data Storage)
- **Purpose**: Store complete API responses
- **Stores**: Full JSON responses (can be MBs)
- **Good at**: Querying, debugging, reprocessing, audit trail
- **Bad at**: Message queuing, async coordination

### Example Flow
```python
# 1. Extract from Jira (1000 issues)
issues = await jira_client.search_issues(jql)  # Large response

# 2. Store complete response in database
raw_record = await store_raw_data({
    "raw_data": issues  # Complete API response (large)
})

# 3. Queue just the ID in RabbitMQ
await queue_manager.publish({
    "raw_data_id": raw_record.id  # Just an integer (tiny)
})

# 4. Worker retrieves from database
raw_data = db.query(RawExtractionData).get(message['raw_data_id'])
work_items = transform(raw_data.raw_data)
```

### Benefits
- ✅ **Small RabbitMQ messages**: Fast, efficient
- ✅ **Debugging**: Can inspect exact API response that failed
- ✅ **Reprocessing**: Retry transform without calling Jira API again
- ✅ **Audit trail**: Complete history of extractions
- ✅ **Data safety**: Even if RabbitMQ crashes, data is safe

## 📋 Task Breakdown

### Task 1.1: Verify RabbitMQ Configuration
**Duration**: 1 hour
**Priority**: HIGH

#### Verify docker-compose.yml
RabbitMQ is already configured in both docker-compose files:

```yaml
# docker-compose.yml (already exists)
rabbitmq:
  image: rabbitmq:3.13-management-alpine
  container_name: pulse-rabbitmq
  restart: unless-stopped
  ports:
    - "5672:5672"   # AMQP port
    - "15672:15672" # Management UI
  volumes:
    - rabbitmq_data:/var/lib/rabbitmq
  environment:
    RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-etl_user}
    RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-etl_password}
    RABBITMQ_DEFAULT_VHOST: ${RABBITMQ_VHOST:-pulse_etl}
  networks:
    - pulse-network
  healthcheck:
    test: ["CMD", "rabbitmq-diagnostics", "ping"]
    interval: 30s
    timeout: 10s
    retries: 3
```

#### Verify .env Configuration
Ensure .env has RabbitMQ credentials:
```bash
# RabbitMQ Configuration
RABBITMQ_USER=etl_user
RABBITMQ_PASSWORD=etl_password
RABBITMQ_VHOST=pulse_etl
RABBITMQ_URL=amqp://etl_user:etl_password@localhost:5672/pulse_etl
```

#### Test RabbitMQ
```bash
# Start RabbitMQ
docker-compose up -d rabbitmq

# Access management UI
# http://localhost:15672
# Login: etl_user / etl_password

# Verify health
docker exec pulse-rabbitmq rabbitmq-diagnostics ping
```

### Task 1.2: Database Schema Updates
**Duration**: 1 hour
**Priority**: CRITICAL

**IMPORTANT**: Only ONE table needed - `raw_extraction_data`. RabbitMQ handles all queue state internally.

#### Add to Migration 0001

Edit `services/backend-service/scripts/migrations/0001_initial_db_schema.py` and add this table creation near the end (before the final commit):

```python
# Edit services/backend-service/scripts/migrations/0001_initial_db_schema.py
# Add this section after all existing table creations

def apply(connection):
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    # ... all existing table creation code ...

    # ============================================================================
    # ETL RAW DATA STORAGE (Phase 1)
    # ============================================================================
    print("📋 Creating ETL raw data storage table...")

    # Raw extraction data storage - complete API responses for debugging/reprocessing
    # This table stores BATCHES of data (e.g., 1000 Jira issues in one record)
    # RabbitMQ queues just reference the ID of this record
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_extraction_data (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            integration_id INTEGER NOT NULL REFERENCES integrations(id),

            -- Batch metadata
            entity_type VARCHAR(50) NOT NULL,  -- 'jira_issues_batch', 'github_prs_batch', etc.
            external_id VARCHAR(255),          -- 'batch_1', 'batch_2', etc.

            -- Complete API response (ALL items in batch)
            raw_data JSONB NOT NULL,           -- { "issues": [...1000 issues...], "total": 1000 }

            -- Extraction context
            extraction_metadata JSONB,         -- { "jql": "...", "cursor": "...", "batch_number": 1 }

            -- Processing tracking
            processing_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
            error_details JSONB,               -- Error information if processing failed
            created_at TIMESTAMP DEFAULT NOW(),
            processed_at TIMESTAMP,
            active BOOLEAN DEFAULT TRUE
        );
    """)

    print("📋 Creating ETL performance indexes...")

    # Performance indexes for raw data queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_data_tenant_type ON raw_extraction_data(tenant_id, entity_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_data_status ON raw_extraction_data(processing_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_data_external_id ON raw_extraction_data(external_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_data_integration ON raw_extraction_data(integration_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_data_created ON raw_extraction_data(created_at DESC);")

    print("✅ ETL raw data table and indexes created")

    # ... rest of migration code (commit, etc.) ...
```

**Key Points**:
- ✅ Add to existing migration 0001 (not a new migration)
- ✅ Only ONE table needed
- ✅ Stores BATCHES (1 record = 1000 issues)
- ❌ NO `etl_job_queue` table (RabbitMQ handles this)

#### Execute Database Migration
```bash
cd services/backend-service

# Drop and recreate database (safe in development)
python scripts/migration_runner.py --drop-all

# Apply all migrations including modified 0001
python scripts/migration_runner.py --apply-all

# Verify new table exists
python scripts/migration_runner.py --status
```

### Task 1.3: Copy Unified Models from ETL Service
**Duration**: 1 hour
**Priority**: CRITICAL

**Rationale**: Backend service needs the same data models as ETL service for consistency.

#### Copy unified_models.py
```bash
# Copy the entire unified_models.py from ETL service to backend service
cp services/etl-service/app/models/unified_models.py \
   services/backend-service/app/models/unified_models.py

# Verify the file exists
ls -la services/backend-service/app/models/unified_models.py
```

**Important**: This ensures both services use identical data models for:
- WorkItem, Pr, PrCommit, PrReview, PrComment
- Integration, Project, Repository
- Wit, Status, Workflow, WitMapping, StatusMapping
- All other entities

### Task 1.4: ETL Module Structure Expansion
**Duration**: 1 hour
**Priority**: HIGH

**SIMPLIFIED**: No `/api` subfolder needed - ETL module is already all APIs.

#### Current Structure (Phase 0)
```
services/backend-service/app/etl/
├── __init__.py
├── router.py              # ✅ Exists - combines all sub-routers
├── wits.py                # ✅ Exists - WITs management APIs
├── statuses.py            # ✅ Exists - Status mappings & workflows APIs
├── integrations.py        # ✅ Exists - Integration CRUD APIs
└── qdrant.py              # ✅ Exists - Qdrant dashboard APIs
```

#### Target Structure (Phase 1)
```bash
# Create additional directories for Phase 1
mkdir -p services/backend-service/app/etl/queue
mkdir -p services/backend-service/app/etl/transformers
mkdir -p services/backend-service/app/etl/loaders

# Create __init__.py files
touch services/backend-service/app/etl/queue/__init__.py
touch services/backend-service/app/etl/transformers/__init__.py
touch services/backend-service/app/etl/loaders/__init__.py
```

#### Final Structure (Phase 1 Complete)
```
services/backend-service/app/etl/
├── __init__.py
├── router.py              # ✅ Update to include new routes
├── wits.py                # ✅ Existing - WITs management APIs
├── statuses.py            # ✅ Existing - Status mappings & workflows APIs
├── integrations.py        # ✅ Existing - Integration CRUD APIs
├── qdrant.py              # ✅ Existing - Qdrant dashboard APIs
├── raw_data.py            # 🔄 NEW - Raw data storage APIs (Phase 1)
├── queue/                 # 🔄 NEW - Phase 1
│   ├── __init__.py
│   └── queue_manager.py   # 🔄 RabbitMQ integration
├── transformers/          # 🔄 NEW - Phase 2
│   ├── __init__.py
│   ├── jira_transformer.py
│   └── github_transformer.py
└── loaders/               # 🔄 NEW - Phase 2
    ├── __init__.py
    ├── work_item_loader.py
    └── pr_loader.py
```

**Note**: No `/api` subfolder - all files in `app/etl/` are already API endpoints.

#### Update ETL Module Initialization
```python
# services/backend-service/app/etl/__init__.py
"""
ETL Module for Backend Service

This module handles the Transform and Load operations of the ETL pipeline.
Extract operations are handled by the separate ETL service.

Phase 0 (COMPLETE):
- Management APIs: WITs, Statuses, Workflows, Integrations, Qdrant

Phase 1 (IN PROGRESS):
- Queue infrastructure: RabbitMQ integration
- Raw data storage: Complete API response preservation
- Queue-based processing: RabbitMQ manages all queue state

Phase 2 (PLANNED):
- Transform operations: Business logic transformation
- Load operations: Bulk loading to final tables
- Workers: Queue consumers for async processing

Structure:
- wits.py, statuses.py, integrations.py, qdrant.py: Management APIs (Phase 0)
- raw_data.py: Raw data storage APIs (Phase 1)
- queue/: RabbitMQ integration and message publishing (Phase 1)
- transformers/: Business logic transformation classes (Phase 2)
- loaders/: Bulk loading operations for final tables (Phase 2)
"""

from .router import router

__all__ = ['router']
```

### Task 1.5: Raw Data Management APIs
**Duration**: 2 days
**Priority**: HIGH

#### Raw Data API Implementation
```python
# services/backend-service/app/etl/raw_data.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel

from app.core.database import get_db_session
from app.auth.centralized_auth_middleware import UserData, require_authentication
from app.models.unified_models import RawExtractionData

router = APIRouter(prefix="/app/etl", tags=["ETL Raw Data"])

# Pydantic schemas for raw data operations
class StoreRawDataRequest(BaseModel):
    integration_id: int
    entity_type: str  # 'issue', 'pr', 'commit', 'review', etc.
    external_id: Optional[str] = None
    raw_data: Dict[str, Any]  # Complete API response
    extraction_metadata: Optional[Dict[str, Any]] = None

class RawDataResponse(BaseModel):
    id: int
    entity_type: str
    external_id: Optional[str]
    raw_data: Dict[str, Any]
    processing_status: str
    created_at: datetime

    class Config:
        from_attributes = True

class UpdateStatusRequest(BaseModel):
    status: str  # 'pending', 'processing', 'completed', 'failed'
    error_details: Optional[Dict[str, Any]] = None

@router.post("/raw-data/store", response_model=dict)
async def store_raw_data(
    request: StoreRawDataRequest,
    user: UserData = Depends(require_authentication),
    db: Session = Depends(get_db_session)
):
    """Store raw extraction data from ETL service"""
    try:
        raw_record = RawExtractionData(
            tenant_id=user.tenant_id,
            integration_id=request.integration_id,
            entity_type=request.entity_type,
            external_id=request.external_id,
            raw_data=request.raw_data,
            extraction_metadata=request.extraction_metadata,
            processing_status='pending'
        )
        
        db.add(raw_record)
        db.commit()
        db.refresh(raw_record)
        
        return {
            "status": "success",
            "record_id": raw_record.id,
            "message": "Raw data stored successfully"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to store raw data: {str(e)}")

@router.get("/raw-data", response_model=List[RawDataResponse])
async def get_raw_data(
    entity_type: str = Query(..., description="Entity type to retrieve"),
    status: Optional[str] = Query(None, description="Processing status filter"),
    limit: int = Query(100, description="Maximum records to return"),
    user: UserData = Depends(require_authentication),
    db: Session = Depends(get_db_session)
):
    """Retrieve raw data for processing"""
    try:
        query = db.query(RawExtractionData).filter(
            RawExtractionData.tenant_id == user.tenant_id,
            RawExtractionData.entity_type == entity_type
        )
        
        if status:
            query = query.filter(RawExtractionData.processing_status == status)
        
        records = query.order_by(RawExtractionData.created_at).limit(limit).all()
        
        return [
            RawDataResponse(
                id=record.id,
                entity_type=record.entity_type,
                external_id=record.external_id,
                raw_data=record.raw_data,
                processing_status=record.processing_status,
                created_at=record.created_at
            )
            for record in records
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve raw data: {str(e)}")

@router.put("/raw-data/{record_id}/status", response_model=dict)
async def update_processing_status(
    record_id: int,
    request: UpdateStatusRequest,
    user: UserData = Depends(require_authentication),
    db: Session = Depends(get_db_session)
):
    """Update processing status of raw data record"""
    try:
        record = db.query(RawExtractionData).filter(
            RawExtractionData.id == record_id,
            RawExtractionData.tenant_id == user.tenant_id
        ).first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Raw data record not found")
        
        record.processing_status = request.status
        if request.error_details:
            record.error_details = request.error_details
        if request.status in ['completed', 'failed']:
            record.processed_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Status updated to {request.status}"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")
```

### Task 1.4: RabbitMQ Integration
**Duration**: 2 days  
**Priority**: HIGH  

#### Queue Manager Implementation
```python
# services/backend-service/app/etl/queue/queue_manager.py
import pika
import json
import asyncio
from typing import Dict, Any, List, Optional
from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class ETLQueueManager:
    """RabbitMQ queue manager for ETL pipeline"""
    
    def __init__(self):
        self.settings = get_settings()
        self.connection = None
        self.channel = None
        self.connected = False
    
    async def connect(self):
        """Establish RabbitMQ connection"""
        try:
            connection_params = pika.URLParameters(self.settings.RABBITMQ_URL)
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()
            
            await self.setup_topology()
            self.connected = True
            logger.info("RabbitMQ connection established")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    async def setup_topology(self):
        """Setup RabbitMQ exchanges and queues"""
        try:
            # Declare exchange
            self.channel.exchange_declare(
                exchange='etl.direct',
                exchange_type='direct',
                durable=True
            )
            
            # Declare queues
            queues = ['etl.extract', 'etl.transform', 'etl.load']
            for queue_name in queues:
                self.channel.queue_declare(queue=queue_name, durable=True)
                routing_key = queue_name.split('.')[1]  # extract, transform, load
                self.channel.queue_bind(
                    exchange='etl.direct',
                    queue=queue_name,
                    routing_key=routing_key
                )
            
            logger.info("RabbitMQ topology setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup RabbitMQ topology: {e}")
            raise
    
    async def publish_job(self, routing_key: str, message: Dict[str, Any], priority: int = 5):
        """Publish job to queue"""
        try:
            if not self.connected:
                await self.connect()
            
            self.channel.basic_publish(
                exchange='etl.direct',
                routing_key=routing_key,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    priority=priority
                )
            )
            
            logger.info(f"Published job to {routing_key}: {message.get('job_type', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to publish job: {e}")
            raise
    
    async def publish_extract_job(self, tenant_id: int, job_data: Dict[str, Any]):
        """Publish extraction job to ETL service"""
        message = {
            'tenant_id': tenant_id,
            'job_type': 'extract',
            'entity_type': job_data.get('entity_type'),
            'integration_id': job_data.get('integration_id'),
            'payload': job_data.get('payload', {}),
            'priority': job_data.get('priority', 5),
            'created_at': job_data.get('created_at')
        }
        await self.publish_job('extract', message, message['priority'])
    
    async def publish_transform_job(self, tenant_id: int, raw_data_ids: List[int], entity_type: str):
        """Publish transformation job"""
        message = {
            'tenant_id': tenant_id,
            'job_type': 'transform',
            'entity_type': entity_type,
            'raw_data_ids': raw_data_ids,
            'priority': 5
        }
        await self.publish_job('transform', message)
    
    async def publish_load_job(self, tenant_id: int, transformed_data: List[Dict], entity_type: str):
        """Publish load job"""
        message = {
            'tenant_id': tenant_id,
            'job_type': 'load',
            'entity_type': entity_type,
            'transformed_data': transformed_data,
            'priority': 5
        }
        await self.publish_job('load', message)
    
    def close(self):
        """Close RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            self.connected = False
            logger.info("RabbitMQ connection closed")
```

### Task 1.5: ETL Data Models
**Duration**: 1 day  
**Priority**: MEDIUM  

#### ETL Schemas Implementation
```python
# services/backend-service/app/etl/models/etl_schemas.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime

class StoreRawDataRequest(BaseModel):
    """Request schema for storing raw extraction data"""
    integration_id: int = Field(..., description="Integration ID that extracted the data")
    entity_type: str = Field(..., description="Type of entity (jira_issues, github_prs, etc.)")
    external_id: Optional[str] = Field(None, description="External system ID")
    raw_data: Dict[str, Any] = Field(..., description="Complete raw API response")
    extraction_metadata: Optional[Dict[str, Any]] = Field(None, description="Extraction context and parameters")

class RawDataResponse(BaseModel):
    """Response schema for raw data retrieval"""
    id: int
    entity_type: str
    external_id: Optional[str]
    raw_data: Dict[str, Any]
    processing_status: str
    created_at: datetime

class UpdateStatusRequest(BaseModel):
    """Request schema for updating processing status"""
    status: str = Field(..., description="New processing status")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Error details if status is failed")

class TransformRequest(BaseModel):
    """Request schema for transformation jobs"""
    raw_data_ids: List[int] = Field(..., description="List of raw data record IDs to transform")
    entity_type: str = Field(..., description="Entity type being transformed")
    transform_options: Optional[Dict[str, Any]] = Field(None, description="Transformation options")

class LoadRequest(BaseModel):
    """Request schema for load jobs"""
    entity_type: str = Field(..., description="Entity type being loaded")
    transformed_data: List[Dict[str, Any]] = Field(..., description="Transformed data to load")
    load_options: Optional[Dict[str, Any]] = Field(None, description="Load options")

class ETLPipelineRequest(BaseModel):
    """Request schema for triggering complete ETL pipeline"""
    entity_type: str = Field(..., description="Entity type to process")
    integration_id: int = Field(..., description="Integration to extract from")
    payload: Dict[str, Any] = Field(..., description="Extraction parameters")
    priority: Optional[int] = Field(5, description="Job priority (1=highest, 10=lowest)")
```

## ✅ Success Criteria

1. **Database Schema**: Raw data and job queue tables created successfully
2. **ETL Module**: Clean module structure established in backend service
3. **Raw Data APIs**: Store, retrieve, and update raw data operations functional
4. **Queue Integration**: RabbitMQ connectivity and job publishing working
5. **Data Models**: Comprehensive schemas for all ETL operations

## 🚨 Risk Mitigation

1. **Database Migration**: Test migration on development environment first
2. **Queue Connectivity**: Implement connection retry logic and health checks
3. **Data Validation**: Comprehensive input validation for all APIs
4. **Error Handling**: Graceful error handling with detailed logging
5. **Performance**: Index optimization for raw data queries

## 📋 Implementation Checklist

### Database & Models
- [ ] Add `raw_extraction_data` table to migration 0001
- [ ] Execute database migration: `python scripts/migration_runner.py --drop-all && --apply-all`
- [ ] Verify table exists: `python scripts/migration_runner.py --status`
- [ ] Copy `unified_models.py` from etl-service to backend-service

### Directory Structure
- [ ] Create `services/backend-service/app/etl/queue/` directory
- [ ] Create `services/backend-service/app/etl/transformers/` directory
- [ ] Create `services/backend-service/app/etl/loaders/` directory
- [ ] Create `__init__.py` files in each directory

### RabbitMQ
- [ ] Verify RabbitMQ running: `docker-compose up -d rabbitmq`
- [ ] Access management UI: http://localhost:15672 (etl_user/etl_password)
- [ ] Install pika: `pip install pika` and update requirements.txt
- [ ] Implement `app/etl/queue/queue_manager.py`
- [ ] Test queue connectivity

### APIs
- [ ] Create `app/etl/raw_data.py` with Pydantic schemas inline
- [ ] Implement POST `/app/etl/raw-data/store`
- [ ] Implement GET `/app/etl/raw-data`
- [ ] Implement PUT `/app/etl/raw-data/{id}/status`
- [ ] Add raw_data router to `app/etl/router.py`

### Testing
- [ ] Test raw data storage API
- [ ] Test raw data retrieval API
- [ ] Test status update API
- [ ] Test RabbitMQ message publishing
- [ ] Verify database records created
- [ ] Check RabbitMQ management UI for queues

## ✅ Success Criteria

1. ✅ `raw_extraction_data` table exists with proper indexes
2. ✅ `unified_models.py` copied and working in backend-service
3. ✅ RabbitMQ running and accessible via management UI
4. ✅ Queue topology established (extract_queue, transform_queue, load_queue)
5. ✅ Raw data APIs functional and tested
6. ✅ Queue manager can publish messages to RabbitMQ
7. ✅ Can store batch of 1000 items and queue just the ID
8. ✅ All tests passing

## 🔄 Next Steps

After Phase 1 completion, this enables:

**Phase 2: ETL Service Refactoring**
- Refactor ETL service jobs to extract-only
- Store raw data via backend API
- Publish to RabbitMQ queue
- Remove transform/load logic from ETL service

**Phase 3: Frontend Job Management**
- Create Jobs page in etl-frontend
- Real-time progress tracking
- Queue monitoring dashboard

## 📊 Revised Timeline

| Task | Duration | Notes |
|------|----------|-------|
| Verify RabbitMQ | 1 hour | Already configured |
| Database Schema | 1 hour | Add to migration 0001 |
| Copy Unified Models | 1 hour | Simple file copy |
| Directory Structure | 15 min | mkdir commands |
| Raw Data APIs | 2 days | Main implementation |
| Queue Manager | 2 days | RabbitMQ integration |
| Router Update | 1 hour | Add to router.py |
| Testing | 1 day | Comprehensive tests |
| **TOTAL** | **1 week** | Simplified from 2 weeks |

## 🎯 Key Takeaways

1. **Separation of Concerns**: Database stores data, RabbitMQ queues work
2. **Batch Processing**: 1 record = 1 API call (e.g., 1000 issues)
3. **Small Messages**: RabbitMQ messages contain only IDs (4 bytes)
4. **No Redundancy**: Only ONE table needed, RabbitMQ handles queue state
5. **Debugging**: Complete API responses preserved for troubleshooting
6. **Reprocessing**: Can retry transforms without re-extracting from external APIs
