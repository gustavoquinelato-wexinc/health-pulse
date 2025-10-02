# Greenfield ETL Implementation Plan

**Document Version**: 1.0  
**Date**: 2025-09-26  
**Status**: READY FOR EXECUTION  

## 🎯 Overview

This document provides a streamlined, phased implementation plan for the greenfield ETL architecture. The plan prioritizes rapid value delivery while building a robust, scalable foundation.

## 📋 Pre-Implementation Checklist

### **Environment Preparation**
- [ ] **Database Backup**: Export current data (optional, for reference)
- [ ] **Environment Variables**: Verify all required settings in `.env`
- [ ] **Dependencies**: Install RabbitMQ and required Python packages
- [ ] **Development Setup**: Ensure all services can be run locally

### **Migration File Preparation**
- [ ] **Review Current Migrations**: Verify 4 existing migrations (0001-0004)
- [ ] **Backup Migration Files**: Copy current migration files for reference
- [ ] **Database Reset Plan**: Confirm database can be safely dropped/recreated

## 🚀 Phase 1: Backend Service ETL Enhancement (Weeks 1-2)

### **Week 1: ETL Sub-structure in Backend Service**

#### **Day 1-2: Create ETL Module Structure**
```bash
# Create ETL sub-structure in backend service (similar to app/ai)
mkdir -p services/backend-service/app/etl/{api,transformers,loaders,queue}
mkdir -p services/backend-service/app/etl/models
```

```python
# services/backend-service/app/etl/__init__.py
"""ETL module for backend service - handles Transform and Load operations"""

# services/backend-service/app/etl/api/__init__.py
"""ETL API endpoints"""

# services/backend-service/app/etl/api/raw_data.py
from fastapi import APIRouter, Depends
from app.auth.centralized_auth_middleware import UserData, require_authentication

router = APIRouter(prefix="/api/v1/etl", tags=["ETL Raw Data"])

@router.post("/raw-data/store")
async def store_raw_data(request: StoreRawDataRequest, user: UserData = Depends(require_authentication)):
    """Store raw extraction data"""

@router.get("/raw-data")
async def get_raw_data(entity_type: str, user: UserData = Depends(require_authentication)):
    """Retrieve raw data for processing"""

@router.put("/raw-data/{record_id}/status")
async def update_processing_status(record_id: int, status: str, user: UserData = Depends(require_authentication)):
    """Update processing status"""
```

#### **Day 3-4: Transform APIs**
```python
# services/backend-service/app/etl/api/transform.py
from fastapi import APIRouter, Depends
from app.etl.transformers.jira_transformer import JiraTransformer
from app.etl.transformers.github_transformer import GitHubTransformer

router = APIRouter(prefix="/api/v1/etl", tags=["ETL Transform"])

@router.post("/transform/jira-issues")
async def transform_jira_issues(request: TransformRequest, user: UserData = Depends(require_authentication)):
    """Transform raw Jira issues to WorkItem objects"""
    transformer = JiraTransformer()
    return await transformer.transform_issues(request.raw_data_ids, user.tenant_id)

@router.post("/transform/github-prs")
async def transform_github_prs(request: TransformRequest, user: UserData = Depends(require_authentication)):
    """Transform raw GitHub PRs to Pr objects"""
    transformer = GitHubTransformer()
    return await transformer.transform_prs(request.raw_data_ids, user.tenant_id)
```

#### **Day 5: Load APIs**
```python
# services/backend-service/app/etl/api/load.py
from fastapi import APIRouter, Depends
from app.etl.loaders.work_item_loader import WorkItemLoader
from app.etl.loaders.pr_loader import PrLoader

router = APIRouter(prefix="/api/v1/etl", tags=["ETL Load"])

@router.post("/load/work-items")
async def load_work_items(request: LoadRequest, user: UserData = Depends(require_authentication)):
    """Bulk load transformed work items"""
    loader = WorkItemLoader()
    return await loader.bulk_load(request.work_items, user.tenant_id)

@router.post("/load/pull-requests")
async def load_pull_requests(request: LoadRequest, user: UserData = Depends(require_authentication)):
    """Bulk load transformed pull requests"""
    loader = PrLoader()
    return await loader.bulk_load(request.pull_requests, user.tenant_id)
```

### **Week 2: Queue Integration & ETL Orchestration**

#### **Day 1-2: RabbitMQ Setup (Docker Integration)**
```bash
# RabbitMQ is now included in docker-compose.yml
# Start with docker-compose
docker-compose up -d rabbitmq

# Access RabbitMQ Management UI at http://localhost:15672
# Default credentials: etl_user / etl_password
```

#### **Day 3-4: Queue Management in Backend Service**
```python
# services/backend-service/app/etl/queue/queue_manager.py
import pika
import json
from typing import Dict, Any, List
from app.core.config import get_settings

class ETLQueueManager:
    def __init__(self):
        self.settings = get_settings()
        self.connection = None
        self.channel = None

    async def connect(self):
        """Establish RabbitMQ connection"""
        self.connection = pika.BlockingConnection(
            pika.URLParameters(f"amqp://{self.settings.RABBITMQ_USER}:{self.settings.RABBITMQ_PASSWORD}@localhost:5672/{self.settings.RABBITMQ_VHOST}")
        )
        self.channel = self.connection.channel()
        await self.setup_topology()

    async def publish_extract_job(self, tenant_id: int, job_data: Dict):
        """Publish extraction job to queue"""

    async def publish_transform_job(self, tenant_id: int, raw_data_ids: List[int]):
        """Publish transformation job to queue"""

    async def publish_load_job(self, tenant_id: int, transformed_data: List[Dict]):
        """Publish load job to queue"""
```

#### **Day 5: ETL Pipeline Orchestration**
```python
# services/backend-service/app/etl/api/pipeline.py
from fastapi import APIRouter, Depends
from app.etl.queue.queue_manager import ETLQueueManager

router = APIRouter(prefix="/api/v1/etl", tags=["ETL Pipeline"])

@router.post("/pipeline/trigger")
async def trigger_etl_pipeline(request: ETLPipelineRequest, user: UserData = Depends(require_authentication)):
    """Trigger complete ETL pipeline for tenant"""
    queue_manager = ETLQueueManager()
    await queue_manager.connect()

    # Publish extract job to ETL service
    await queue_manager.publish_extract_job(user.tenant_id, request.job_data)

    return {"status": "success", "message": "ETL pipeline triggered"}

@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str, user: UserData = Depends(require_authentication)):
    """Get detailed job status and progress"""
    # Implementation for job status tracking
    pass
```

## 🔄 Phase 2: ETL Service Refactor (Weeks 3-4)

### **Week 3: Extract-Only Service**

#### **Day 1-2: Database Schema Update**
```sql
-- Modify 0001_initial_db_schema.py
-- Add raw data tables (as shown in architecture document)

-- Execute migration
cd services/backend-service
python scripts/migration_runner.py --drop-all
python scripts/migration_runner.py --apply-all
```

#### **Day 3-4: Extractor Refactoring**
```python
# services/etl-service/app/extractors/jira_extractor.py
class JiraExtractor:
    async def extract_and_store(self, tenant_id: int, integration_id: int):
        """Extract data and store raw JSON"""
        # Use existing business logic
        raw_issues = await self.extract_issues()
        
        # Store raw data
        await self.store_raw_data(raw_issues)
        
        # Queue for transformation
        await self.queue_transform_job(raw_issues)
```

#### **Day 5: Integration Framework**
```python
# services/etl-service/app/integrations/
# Implement pluggable integration system
# (as detailed in architecture document)
```

### **Week 4: Queue Workers**

#### **Day 1-3: Worker Implementation**
```python
# services/etl-service/app/workers/
class ExtractWorker:
    """Handles extraction jobs from queue"""
    
class TransformWorker:
    """Handles transformation jobs from queue"""
    
class LoadWorker:
    """Handles load jobs from queue"""
```

#### **Day 4-5: Service Integration**
```python
# services/etl-service/app/main.py
# Remove UI routes, keep only API endpoints
# Add queue worker startup
# Integrate with RabbitMQ
```

## 🎨 Phase 3: Frontend Migration (Weeks 5-6)

### **Week 5: React SPA Foundation**

#### **Day 1-2: Project Setup**
```bash
# Create new React app structure
cd services/frontend-app
npm install @tanstack/react-query axios socket.io-client
npm install @radix-ui/react-dialog @radix-ui/react-progress
```

#### **Day 3-4: Core Components**
```typescript
// src/components/etl/
JobPipelineView.tsx     // Vertical job pipeline
JobCard.tsx             // Individual job status card
ProgressIndicator.tsx   // Real-time progress
LogViewer.tsx          // Log management
```

#### **Day 5: API Integration**
```typescript
// src/services/etl-api.ts
export const etlApi = {
  triggerPipeline: (tenantId: number, jobType: string) => Promise<JobResponse>,
  getJobStatus: (jobId: string) => Promise<JobStatus>,
  getRawData: (tenantId: number, entityType: string) => Promise<RawData[]>,
  // ... other API methods
}
```

### **Week 6: UI/UX Migration**

#### **Day 1-3: Dashboard Migration**
```typescript
// Migrate existing UI patterns to React
// Preserve essential workflows:
// - Job pipeline visualization
// - Manual job control
// - Real-time progress updates
// - Integration management
```

#### **Day 4-5: WebSocket Integration**
```typescript
// src/hooks/useRealTimeUpdates.ts
export const useRealTimeUpdates = (tenantId: number) => {
  // WebSocket connection for real-time job updates
  // Progress notifications
  // Status changes
}
```

## 🧪 Phase 4: Testing & Optimization (Weeks 7-8)

### **Week 7: End-to-End Testing**

#### **Day 1-2: Pipeline Testing**
```python
# tests/integration/test_etl_pipeline.py
async def test_complete_jira_pipeline():
    """Test extract → transform → load for Jira data"""
    
async def test_complete_github_pipeline():
    """Test extract → transform → load for GitHub data"""
    
async def test_multi_tenant_isolation():
    """Verify tenant data isolation"""
```

#### **Day 3-4: Performance Testing**
```python
# tests/performance/
test_queue_throughput.py    # Queue performance
test_database_load.py       # Database performance
test_concurrent_tenants.py  # Multi-tenant performance
```

#### **Day 5: Error Handling Testing**
```python
# tests/error_handling/
test_extraction_failures.py    # API failures, rate limits
test_transformation_errors.py  # Data validation errors
test_queue_failures.py         # Queue connectivity issues
```

### **Week 8: Production Readiness**

#### **Day 1-2: Monitoring Setup**
```python
# Add comprehensive logging
# Set up health checks
# Configure alerting
# Performance metrics
```

#### **Day 3-4: Documentation**
```markdown
# Create comprehensive documentation:
# - API documentation
# - Deployment guide
# - Troubleshooting guide
# - User manual
```

#### **Day 5: Go-Live Preparation**
```bash
# Final deployment checklist
# Environment configuration
# Database migration verification
# Service startup verification
# End-to-end smoke tests
```

## 📊 Success Metrics

### **Technical Metrics**
- ✅ **Pipeline Separation**: Extract, Transform, Load run independently
- ✅ **Queue Performance**: <1 second job queuing, >95% success rate
- ✅ **Data Integrity**: 100% data consistency between raw and final tables
- ✅ **Multi-tenancy**: Complete tenant isolation verified
- ✅ **Scalability**: Support for 10+ concurrent tenants

### **Business Metrics**
- ✅ **User Experience**: All essential workflows preserved
- ✅ **Performance**: 50% improvement in processing speed
- ✅ **Reliability**: 99% uptime, automated error recovery
- ✅ **Maintainability**: Clear separation of concerns, pluggable architecture

## 🚨 Risk Mitigation

### **Technical Risks**
1. **Queue Complexity**: Start with simple RabbitMQ setup, add complexity gradually
2. **Data Migration**: Thorough testing with sample data before full migration
3. **Service Dependencies**: Implement circuit breakers and fallback mechanisms
4. **Performance Degradation**: Continuous monitoring and optimization

### **Business Risks**
1. **User Disruption**: Maintain UI/UX consistency during migration
2. **Data Loss**: Multiple backup strategies and rollback plans
3. **Timeline Delays**: Prioritize core functionality, defer nice-to-have features
4. **Integration Issues**: Extensive testing with real data sources

## ✅ Implementation Checklist

### **Phase 1 Completion Criteria**
- [ ] Raw data storage APIs functional
- [ ] Transform/Load APIs implemented
- [ ] RabbitMQ integration working
- [ ] Basic queue management operational

### **Phase 2 Completion Criteria**
- [ ] ETL service refactored to extract-only
- [ ] Queue workers implemented and tested
- [ ] Integration framework functional
- [ ] Database schema updated

### **Phase 3 Completion Criteria**
- [ ] React SPA deployed and functional
- [ ] All essential UI workflows migrated
- [ ] Real-time updates working
- [ ] API integration complete

### **Phase 4 Completion Criteria**
- [ ] End-to-end testing passed
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Production deployment ready

This implementation plan provides a clear roadmap for transforming your monolithic ETL service into a modern, scalable microservices architecture while preserving essential business functionality and user experience.
