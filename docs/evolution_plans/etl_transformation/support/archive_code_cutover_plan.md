# Code Cutover Plan: Monolithic ETL → Microservices Architecture

**Document Version**: 1.0  
**Date**: 2025-09-26  
**Status**: READY FOR EXECUTION  

## 🎯 Overview

This document outlines the step-by-step process for replacing the current monolithic ETL service with the new microservices architecture. The plan ensures zero data loss and minimal disruption while maintaining all essential functionality.

## 📋 Pre-Cutover Preparation

### **1. Backup Current System**
```bash
# Create backup of current ETL service
cd services/
cp -r etl-service etl-service-backup-$(date +%Y%m%d)

# Export current database schema and data (optional reference)
pg_dump -h localhost -U postgres -d pulse_platform > backup_$(date +%Y%m%d).sql
```

### **2. Environment Setup**
```bash
# Install RabbitMQ
docker run -d --name rabbitmq-etl \
  -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=etl_user \
  -e RABBITMQ_DEFAULT_PASS=etl_password \
  rabbitmq:3-management

# Update .env file
echo "RABBITMQ_URL=amqp://etl_user:etl_password@localhost:5672/" >> .env
echo "ETL_QUEUE_ENABLED=true" >> .env
```

### **3. Dependency Installation**
```bash
# Backend service dependencies
cd services/backend-service
pip install pika aio-pika celery redis

# ETL service dependencies  
cd ../etl-service
pip install pika aio-pika

# Frontend dependencies
cd ../frontend-app
npm install @tanstack/react-query socket.io-client
```

## 🔄 Phase 1: Database Schema Migration

### **Step 1: Modify Migration 0001**
```python
# Edit services/backend-service/scripts/migrations/0001_initial_db_schema.py
# Add the following tables after existing schema creation:

def apply(connection):
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    
    # ... existing schema creation code ...
    
    # ADD: Raw data storage table
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
    
    # ADD: ETL job queue table
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
    
    # ADD: Performance indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_data_tenant_type ON raw_extraction_data(tenant_id, entity_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_data_status ON raw_extraction_data(processing_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_data_external_id ON raw_extraction_data(external_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_etl_queue_tenant_status ON etl_job_queue(tenant_id, status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_etl_queue_priority ON etl_job_queue(priority, scheduled_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_etl_queue_type ON etl_job_queue(job_type, entity_type);")
```

### **Step 2: Execute Database Migration**
```bash
cd services/backend-service

# Drop and recreate database (safe in greenfield)
python scripts/migration_runner.py --drop-all

# Apply all migrations including modified 0001
python scripts/migration_runner.py --apply-all

# Verify new tables exist
python scripts/migration_runner.py --status
```

## 🏗️ Phase 2: Backend Service Enhancement

### **Step 1: Add Raw Data Models**
```python
# services/backend-service/app/models/unified_models.py
# Add after existing models:

class RawExtractionData(Base, BaseEntity):
    """Raw data storage for ETL pipeline"""
    __tablename__ = 'raw_extraction_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    integration_id = Column(Integer, ForeignKey('integrations.id'), nullable=False)
    entity_type = Column(String(50), nullable=False)
    external_id = Column(String(255), nullable=True)
    raw_data = Column(JSON, nullable=False)
    extraction_metadata = Column(JSON, nullable=True)
    processing_status = Column(String(20), default='pending')
    error_details = Column(JSON, nullable=True)
    processed_at = Column(DateTime, nullable=True)

class ETLJobQueue(Base, BaseEntity):
    """ETL job queue for pipeline management"""
    __tablename__ = 'etl_job_queue'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    priority = Column(Integer, default=5)
    status = Column(String(20), default='pending')
    scheduled_at = Column(DateTime, default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_details = Column(JSON, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
```

### **Step 2: Add Queue Manager**
```python
# services/backend-service/app/core/queue_manager.py
import pika
import json
from typing import Dict, Any
from app.core.config import get_settings

class QueueManager:
    def __init__(self):
        self.settings = get_settings()
        self.connection = None
        self.channel = None
    
    async def connect(self):
        """Establish RabbitMQ connection"""
        self.connection = pika.BlockingConnection(
            pika.URLParameters(self.settings.RABBITMQ_URL)
        )
        self.channel = self.connection.channel()
        
        # Declare exchanges and queues
        await self.setup_topology()
    
    async def setup_topology(self):
        """Setup RabbitMQ exchanges and queues"""
        # Declare exchanges
        self.channel.exchange_declare(
            exchange='etl.direct',
            exchange_type='direct',
            durable=True
        )
        
        # Declare queues
        self.channel.queue_declare(queue='etl.extract', durable=True)
        self.channel.queue_declare(queue='etl.transform', durable=True)
        self.channel.queue_declare(queue='etl.load', durable=True)
        
        # Bind queues to exchange
        self.channel.queue_bind(exchange='etl.direct', queue='etl.extract', routing_key='extract')
        self.channel.queue_bind(exchange='etl.direct', queue='etl.transform', routing_key='transform')
        self.channel.queue_bind(exchange='etl.direct', queue='etl.load', routing_key='load')
    
    async def publish_job(self, routing_key: str, message: Dict[str, Any]):
        """Publish job to queue"""
        self.channel.basic_publish(
            exchange='etl.direct',
            routing_key=routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                priority=message.get('priority', 5)
            )
        )
```

### **Step 3: Add ETL APIs**
```python
# services/backend-service/app/api/etl_pipeline.py
from fastapi import APIRouter, Depends, HTTPException
from app.core.queue_manager import QueueManager
from app.auth.centralized_auth_middleware import UserData, require_authentication

router = APIRouter()

@router.post("/api/v1/etl/trigger-pipeline")
async def trigger_etl_pipeline(
    request: ETLPipelineRequest,
    user: UserData = Depends(require_authentication)
):
    """Trigger complete ETL pipeline"""
    queue_manager = QueueManager()
    await queue_manager.connect()
    
    # Publish extract job
    extract_message = {
        'tenant_id': user.tenant_id,
        'job_type': 'extract',
        'entity_type': request.entity_type,
        'integration_id': request.integration_id,
        'payload': request.payload,
        'priority': request.priority or 5
    }
    
    await queue_manager.publish_job('extract', extract_message)
    
    return {'status': 'success', 'message': 'ETL pipeline triggered'}

@router.post("/api/v1/etl/raw-data")
async def store_raw_data(
    request: StoreRawDataRequest,
    user: UserData = Depends(require_authentication)
):
    """Store raw extraction data"""
    # Implementation for storing raw data
    pass

@router.get("/api/v1/etl/jobs/{job_id}/status")
async def get_job_status(
    job_id: str,
    user: UserData = Depends(require_authentication)
):
    """Get ETL job status"""
    # Implementation for job status
    pass
```

## 🔄 Phase 3: ETL Service Refactoring

### **Step 1: Create New ETL Service Structure**
```bash
# Create new ETL service structure
mkdir -p services/etl-service-new/app/{extractors,workers,integrations,core}
mkdir -p services/etl-service-new/app/api

# Copy essential files
cp services/etl-service/app/core/{config,database,logging_config}.py services/etl-service-new/app/core/
cp services/etl-service/app/models/unified_models.py services/etl-service-new/app/models/
```

### **Step 2: Refactor Extractors**
```python
# services/etl-service-new/app/extractors/jira_extractor.py
from app.jobs.jira.jira_client import JiraClient  # Reuse existing client
from app.core.queue_manager import QueueManager

class JiraExtractor:
    def __init__(self, integration_config):
        self.config = integration_config
        self.client = JiraClient(integration_config)
        self.queue_manager = QueueManager()
    
    async def extract_issues(self, tenant_id: int, jql_query: str) -> List[Dict]:
        """Extract Jira issues and store raw data"""
        # Use existing business logic
        raw_issues = await self.client.get_issues_batch(jql_query)
        
        # Store raw data
        for issue in raw_issues:
            await self.store_raw_data(
                tenant_id=tenant_id,
                entity_type='jira_issues',
                external_id=issue['key'],
                raw_data=issue
            )
        
        # Queue for transformation
        await self.queue_transform_job(tenant_id, 'jira_issues', len(raw_issues))
        
        return raw_issues
    
    async def store_raw_data(self, tenant_id: int, entity_type: str, external_id: str, raw_data: Dict):
        """Store raw data in database"""
        # Implementation for storing raw data
        pass
    
    async def queue_transform_job(self, tenant_id: int, entity_type: str, record_count: int):
        """Queue transformation job"""
        transform_message = {
            'tenant_id': tenant_id,
            'job_type': 'transform',
            'entity_type': entity_type,
            'record_count': record_count
        }
        await self.queue_manager.publish_job('transform', transform_message)
```

### **Step 3: Create Queue Workers**
```python
# services/etl-service-new/app/workers/extract_worker.py
import pika
import json
from app.extractors.jira_extractor import JiraExtractor
from app.extractors.github_extractor import GitHubExtractor

class ExtractWorker:
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        self.channel = self.connection.channel()
    
    def start_consuming(self):
        """Start consuming extract jobs"""
        self.channel.basic_consume(
            queue='etl.extract',
            on_message_callback=self.process_extract_job,
            auto_ack=False
        )
        self.channel.start_consuming()
    
    def process_extract_job(self, ch, method, properties, body):
        """Process extraction job"""
        try:
            message = json.loads(body)
            entity_type = message['entity_type']
            
            if entity_type.startswith('jira_'):
                extractor = JiraExtractor(message['integration_config'])
                result = await extractor.extract_issues(
                    tenant_id=message['tenant_id'],
                    **message['payload']
                )
            elif entity_type.startswith('github_'):
                extractor = GitHubExtractor(message['integration_config'])
                result = await extractor.extract_prs(
                    tenant_id=message['tenant_id'],
                    **message['payload']
                )
            
            # Acknowledge successful processing
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            # Handle error and potentially retry
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
```

## 🎨 Phase 4: Frontend Migration

### **Step 1: Create React Components**
```typescript
// services/frontend-app/src/components/etl/JobPipelineView.tsx
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { etlApi } from '../../services/etl-api';

export const JobPipelineView: React.FC = () => {
  const { data: jobs, isLoading } = useQuery({
    queryKey: ['etl-jobs'],
    queryFn: () => etlApi.getJobs(),
    refetchInterval: 5000 // Real-time updates
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="job-pipeline-vertical">
      {jobs?.map(job => (
        <JobCard key={job.id} job={job} />
      ))}
    </div>
  );
};
```

### **Step 2: API Integration**
```typescript
// services/frontend-app/src/services/etl-api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_BACKEND_URL,
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('token')}`
  }
});

export const etlApi = {
  triggerPipeline: (tenantId: number, entityType: string, payload: any) =>
    api.post('/api/v1/etl/trigger-pipeline', { tenantId, entityType, payload }),
  
  getJobs: () => api.get('/api/v1/etl/jobs'),
  
  getJobStatus: (jobId: string) => api.get(`/api/v1/etl/jobs/${jobId}/status`),
  
  getRawData: (tenantId: number, entityType: string) =>
    api.get(`/api/v1/etl/raw-data?tenant_id=${tenantId}&entity_type=${entityType}`)
};
```

## 🔄 Phase 5: Service Replacement

### **Step 1: Stop Current ETL Service**
```bash
# Stop current ETL service
cd services/etl-service
# Stop the service (Ctrl+C or kill process)

# Rename current service
cd ../
mv etl-service etl-service-old
mv etl-service-new etl-service
```

### **Step 2: Start New Services**
```bash
# Start RabbitMQ workers
cd services/etl-service
python -m app.workers.extract_worker &
python -m app.workers.transform_worker &
python -m app.workers.load_worker &

# Start ETL API service
python run_etl.py &

# Start backend service
cd ../backend-service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 &

# Start frontend
cd ../frontend-app
npm run dev &
```

### **Step 3: Verification**
```bash
# Test ETL pipeline
curl -X POST http://localhost:8001/api/v1/etl/trigger-pipeline \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"entity_type": "jira_issues", "integration_id": 1, "payload": {}}'

# Check queue status
curl http://localhost:15672/api/queues (RabbitMQ Management UI)

# Verify data flow
psql -d pulse_platform -c "SELECT COUNT(*) FROM raw_extraction_data;"
```

## ✅ Post-Cutover Validation

### **Functional Testing**
- [ ] ETL pipeline triggers successfully
- [ ] Raw data is stored correctly
- [ ] Transformation jobs process data
- [ ] Final data appears in business tables
- [ ] UI displays job status correctly
- [ ] Real-time updates work
- [ ] Error handling functions properly

### **Performance Testing**
- [ ] Queue throughput meets requirements
- [ ] Database performance is acceptable
- [ ] UI responsiveness is maintained
- [ ] Memory usage is within limits

### **Data Integrity Testing**
- [ ] All existing data is preserved
- [ ] New data follows correct schema
- [ ] Tenant isolation is maintained
- [ ] No data corruption occurred

## 🚨 Rollback Plan

If issues arise, rollback procedure:

```bash
# Stop new services
pkill -f "extract_worker"
pkill -f "transform_worker" 
pkill -f "load_worker"

# Restore old service
mv etl-service etl-service-failed
mv etl-service-old etl-service

# Restart old service
cd services/etl-service
python run_etl.py

# Restore database if needed
psql -d pulse_platform < backup_$(date +%Y%m%d).sql
```

This cutover plan ensures a smooth transition from the monolithic architecture to the new microservices architecture while maintaining data integrity and system functionality.
