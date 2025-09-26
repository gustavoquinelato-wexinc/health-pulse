# ETL Phase 1: Backend Service ETL Module

**Implemented**: NO ❌  
**Duration**: Weeks 1-2  
**Priority**: HIGH  
**Risk Level**: LOW  

## 💼 Business Outcome

**Foundation for Modern ETL**: Establish the Transform and Load components of the ETL pipeline within the existing backend service, creating a clean separation of concerns while maintaining the simplicity of a single backend microservice.

## 🎯 Objectives

1. **ETL Module Structure**: Create `app/etl` sub-structure in backend service (similar to `app/ai`)
2. **Transform APIs**: Implement business logic transformation endpoints
3. **Load APIs**: Create bulk loading operations for final data tables
4. **Queue Integration**: Add RabbitMQ connectivity for job processing
5. **Database Schema**: Update schema for raw data storage and job queue

## 📋 Task Breakdown

### Task 1.1: Database Schema Updates
**Duration**: 2 days  
**Priority**: CRITICAL  

#### Modify Existing Migration 0001
```python
# Edit services/backend-service/scripts/migrations/0001_initial_db_schema.py
# Add raw data tables to existing schema creation

def apply(connection):
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    
    # ... existing schema creation code ...
    
    print("📋 Creating ETL raw data tables...")
    
    # Raw extraction data storage
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_extraction_data (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            integration_id INTEGER NOT NULL REFERENCES integrations(id),
            entity_type VARCHAR(50) NOT NULL,
            external_id VARCHAR(255),
            raw_data JSONB NOT NULL,
            extraction_metadata JSONB,
            processing_status VARCHAR(20) DEFAULT 'pending',
            error_details JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            processed_at TIMESTAMP
        );
    """)
    
    # ETL job queue
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS etl_job_queue (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            job_type VARCHAR(50) NOT NULL,
            entity_type VARCHAR(50) NOT NULL,
            payload JSONB NOT NULL,
            priority INTEGER DEFAULT 5,
            status VARCHAR(20) DEFAULT 'pending',
            scheduled_at TIMESTAMP DEFAULT NOW(),
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_details JSONB,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3
        );
    """)
    
    print("📋 Creating ETL performance indexes...")
    
    # Performance indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_data_tenant_type ON raw_extraction_data(tenant_id, entity_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_data_status ON raw_extraction_data(processing_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_data_external_id ON raw_extraction_data(external_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_etl_queue_tenant_status ON etl_job_queue(tenant_id, status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_etl_queue_priority ON etl_job_queue(priority, scheduled_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_etl_queue_type ON etl_job_queue(job_type, entity_type);")
    
    print("✅ ETL tables and indexes created")
```

#### Execute Database Migration
```bash
cd services/backend-service

# Drop and recreate database (safe in greenfield)
python scripts/migration_runner.py --drop-all

# Apply all migrations including modified 0001
python scripts/migration_runner.py --apply-all

# Verify new tables exist
python scripts/migration_runner.py --status
```

### Task 1.2: ETL Module Structure Creation
**Duration**: 1 day  
**Priority**: HIGH  

#### Create Directory Structure
```bash
# Create ETL module structure in backend service
mkdir -p services/backend-service/app/etl/{api,transformers,loaders,queue,models}
touch services/backend-service/app/etl/__init__.py
touch services/backend-service/app/etl/api/__init__.py
touch services/backend-service/app/etl/transformers/__init__.py
touch services/backend-service/app/etl/loaders/__init__.py
touch services/backend-service/app/etl/queue/__init__.py
touch services/backend-service/app/etl/models/__init__.py
```

#### ETL Module Initialization
```python
# services/backend-service/app/etl/__init__.py
"""
ETL Module for Backend Service

This module handles the Transform and Load operations of the ETL pipeline.
Extract operations are handled by the separate ETL service.

Structure:
- api/: FastAPI routers for ETL endpoints
- transformers/: Business logic transformation classes
- loaders/: Bulk loading operations for final tables
- queue/: RabbitMQ integration and job management
- models/: ETL-specific schemas and data models
"""

from .api import raw_data, transform, load, pipeline

__all__ = ['raw_data', 'transform', 'load', 'pipeline']
```

### Task 1.3: Raw Data Management APIs
**Duration**: 2 days  
**Priority**: HIGH  

#### Raw Data API Implementation
```python
# services/backend-service/app/etl/api/raw_data.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db_session
from app.auth.centralized_auth_middleware import UserData, require_authentication
from app.etl.models.etl_schemas import StoreRawDataRequest, RawDataResponse, UpdateStatusRequest
from app.models.unified_models import RawExtractionData

router = APIRouter(prefix="/api/v1/etl", tags=["ETL Raw Data"])

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

- [ ] Modify migration 0001 with raw data tables
- [ ] Execute database migration and verify tables
- [ ] Create ETL module directory structure
- [ ] Implement raw data management APIs
- [ ] Add RabbitMQ queue manager
- [ ] Create ETL data models and schemas
- [ ] Test RabbitMQ connectivity
- [ ] Validate raw data storage and retrieval
- [ ] Update backend service main.py to include ETL routes
- [ ] Create unit tests for ETL module

## 🔄 Next Steps

After completion, this enables:
- **Phase 2**: ETL service refactoring to extract-only operations
- **Queue Processing**: Message-based job distribution
- **Data Pipeline**: Foundation for Transform and Load operations
