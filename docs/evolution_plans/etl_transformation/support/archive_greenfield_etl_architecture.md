# Greenfield ETL Architecture Blueprint

**Document Version**: 1.0  
**Date**: 2025-09-26  
**Status**: DRAFT  

## 🎯 Executive Summary

This document outlines the foundational architecture for a modern, greenfield ETL platform that replaces the current monolithic service with a scalable, multi-tenant microservices architecture. The design prioritizes proper Extract → Transform → Load separation, queue-based processing, and enterprise-grade multi-tenancy from day one.

## 📋 Part 1: Project Context & Constraints

### **Greenfield Advantages**
- ✅ **No Production Users**: Complete freedom to redesign architecture
- ✅ **Destructible Database**: Can drop/recreate PostgreSQL without data loss concerns
- ✅ **Clean Slate**: No legacy code constraints or backward compatibility requirements
- ✅ **Modern Patterns**: Implement current best practices from the start

### **Migration File Rules (CRITICAL)**
```
Current State: 4 migrations exactly
├── 0001_initial_db_schema.py     # Core schema
├── 0002_initial_seed_data_wex.py # WEX tenant data
├── 0003_initial_seed_data_apple.py # Apple tenant data  
└── 0004_initial_seed_data_google.py # Google tenant data

New Architecture Rules:
├── MODIFY: Edit 0001 directly for schema changes (NO new migrations)
├── PRESERVE: Keep 0002, 0003, 0004 for tenant data
└── CREATE: ONE new migration for all raw data tables
```

## 📊 Part 2: Current Architecture Analysis

### **Existing Business Logic (PRESERVE)**

#### **Core ETL Workflows**
1. **Jira Integration**: 
   - Issue types & projects extraction
   - Statuses & project links extraction  
   - Issues, changelogs & dev_status extraction
   - Custom JQL query support
   - Incremental sync with checkpoint recovery

2. **GitHub Integration**:
   - Repository discovery via Search API
   - Pull request extraction via GraphQL API
   - Incremental sync with cursor-based pagination
   - PR-WorkItem linking via WitPrLinks table

3. **Orchestration Pattern**:
   - Active/Passive job model
   - Status-based job sequencing (PENDING → RUNNING → FINISHED)
   - Tenant-isolated job execution
   - Checkpoint recovery for failed jobs

#### **Essential UI/UX Patterns (PRESERVE)**
1. **Job Pipeline Visualization**: Vertical job cards with status indicators
2. **Real-time Progress**: WebSocket-based progress updates
3. **Manual Job Control**: Force start, pause, resume capabilities
4. **Integration Management**: Visual integration cards with logos
5. **Log Management**: Real-time log viewing and filtering
6. **Settings Management**: Dynamic orchestrator configuration

### **Current Architecture Limitations (REPLACE)**
1. **Monolithic Service**: Single FastAPI service handling UI + ETL + API
2. **Coupled Extract/Transform**: Data extraction and transformation in same process
3. **No Raw Data Storage**: Processed data directly inserted to final tables
4. **Limited Queue System**: Simple database-based job status tracking
5. **Tight Coupling**: UI, API, and ETL logic intertwined

## 🏗️ Part 3: Target Architecture

### **Multi-Tenancy Model: Unified SaaS Architecture**

**Decision**: Implement **unified multi-tenant SaaS model** with tenant isolation at all layers.

**Justification**:
- ✅ **Greenfield Advantage**: No existing single-tenant constraints
- ✅ **Operational Efficiency**: Single deployment, unified monitoring
- ✅ **Cost Optimization**: Shared infrastructure with tenant isolation
- ✅ **Scalability**: Horizontal scaling with tenant-aware load balancing
- ✅ **Security**: Database-level tenant isolation with row-level security

### **Tenant Priority & Queue Management**

```python
# Multi-tenant queue architecture
TENANT_QUEUE_STRATEGY = {
    'enterprise': {
        'dedicated_workers': 3,
        'priority_weight': 10,
        'queue_name': 'etl.enterprise.{tenant_id}'
    },
    'professional': {
        'dedicated_workers': 2, 
        'priority_weight': 5,
        'queue_name': 'etl.professional.{tenant_id}'
    },
    'standard': {
        'shared_workers': True,
        'priority_weight': 1,
        'queue_name': 'etl.standard.shared'
    }
}
```

### **Service Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (Nginx)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Frontend      │  │   Backend       │  │   ETL Service   │
│   (React SPA)   │  │   (FastAPI)     │  │   (FastAPI)     │
│                 │  │                 │  │                 │
│ • Job Dashboard │  │ • Authentication│  │ • Extract Only  │
│ • Progress UI   │  │ • Job APIs      │  │ • Queue Mgmt    │
│ • Settings      │  │ • Transform APIs│  │ • Raw Storage   │
│ • Real-time     │  │ • Load APIs     │  │ • Integration   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Message Queue (RabbitMQ)                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Extract     │  │ Transform   │  │ Load        │        │
│  │ Queue       │  │ Queue       │  │ Queue       │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ PostgreSQL  │  │ Redis       │  │ Qdrant      │        │
│  │ Primary     │  │ Cache       │  │ Vector DB   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 Part 4: ETL Pipeline Design

### **True ETL Separation**

#### **Extract Service (ETL Service)**
```python
# services/etl-service/app/extractors/
class JiraExtractor:
    async def extract_issues(self, tenant_id: int, integration_id: int) -> List[Dict]:
        """Extract raw JSON from Jira API"""
        raw_data = await self.jira_client.get_issues(jql_query)
        
        # Store raw data immediately
        await self.store_raw_data(
            tenant_id=tenant_id,
            integration_id=integration_id,
            entity_type='jira_issues',
            raw_data=raw_data,
            extraction_metadata={
                'jql_query': jql_query,
                'total_count': len(raw_data),
                'extraction_timestamp': datetime.utcnow()
            }
        )
        
        # Queue for transformation
        await self.queue_for_transform(
            tenant_id=tenant_id,
            entity_type='jira_issues',
            raw_data_ids=[record.id for record in raw_data]
        )
```

#### **Transform Service (Backend Service)**
```python
# services/backend-service/app/transformers/
class JiraTransformer:
    async def transform_issues(self, raw_data_batch: List[RawData]) -> List[WorkItem]:
        """Transform raw JSON to business objects"""
        transformed_items = []
        
        for raw_record in raw_data_batch:
            jira_issue = raw_record.data  # Raw JSON
            
            # Business logic transformation
            work_item = WorkItem(
                tenant_id=raw_record.tenant_id,
                external_id=jira_issue['key'],
                summary=jira_issue['fields']['summary'],
                description=jira_issue['fields']['description'],
                # ... transformation logic
            )
            transformed_items.append(work_item)
        
        # Queue for loading
        await self.queue_for_load(transformed_items)
        return transformed_items
```

#### **Load Service (Backend Service)**
```python
# services/backend-service/app/loaders/
class WorkItemLoader:
    async def load_work_items(self, work_items: List[WorkItem]) -> LoadResult:
        """Bulk load transformed data to final tables"""
        
        # Bulk upsert to final tables
        result = await self.bulk_upsert(work_items)
        
        # Queue for vectorization
        await self.queue_for_vectorization(
            entity_type='work_items',
            entity_ids=[item.id for item in work_items]
        )
        
        return result
```

### **Raw Data Storage Schema**

```sql
-- New migration: 0005_raw_data_storage.py
CREATE TABLE raw_extraction_data (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    integration_id INTEGER NOT NULL REFERENCES integrations(id),
    entity_type VARCHAR(50) NOT NULL, -- 'jira_issues', 'github_prs', etc.
    external_id VARCHAR(255), -- Original system ID
    raw_data JSONB NOT NULL, -- Complete API response
    extraction_metadata JSONB, -- Query params, timestamps, etc.
    processing_status VARCHAR(20) DEFAULT 'pending', -- pending, transformed, loaded, failed
    error_details JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    
    -- Indexes for performance
    INDEX idx_raw_data_tenant_type (tenant_id, entity_type),
    INDEX idx_raw_data_status (processing_status),
    INDEX idx_raw_data_external_id (external_id),
    INDEX idx_raw_data_created (created_at)
);

-- ETL job queue for proper pipeline management
CREATE TABLE etl_job_queue (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    job_type VARCHAR(50) NOT NULL, -- 'extract', 'transform', 'load'
    entity_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL, -- Job-specific data
    priority INTEGER DEFAULT 5, -- 1=highest, 10=lowest
    status VARCHAR(20) DEFAULT 'pending',
    scheduled_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_details JSONB,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    INDEX idx_etl_queue_tenant_status (tenant_id, status),
    INDEX idx_etl_queue_priority (priority, scheduled_at),
    INDEX idx_etl_queue_type (job_type, entity_type)
);
```

## 📋 Part 5: Implementation Deliverables

### **Phase 1: Backend Service (Weeks 1-2)**
1. **Transform/Load APIs**: Create transformation and loading endpoints
2. **Queue Management**: Implement RabbitMQ integration
3. **Raw Data APIs**: Create raw data storage and retrieval endpoints
4. **Job Orchestration**: Enhanced job management with proper ETL separation

### **Phase 2: ETL Service Refactor (Weeks 3-4)**  
1. **Extract-Only Service**: Refactor to extraction-only service
2. **Raw Data Storage**: Implement raw JSON storage
3. **Queue Integration**: Connect to RabbitMQ for job distribution
4. **Integration Framework**: Pluggable integration system

### **Phase 3: Frontend Migration (Weeks 5-6)**
1. **React SPA**: Migrate from server-side templates to React
2. **Real-time Dashboard**: WebSocket-based progress tracking
3. **Job Management UI**: Enhanced job control interface
4. **Settings Management**: Dynamic configuration interface

### **Phase 4: Testing & Optimization (Weeks 7-8)**
1. **End-to-End Testing**: Complete pipeline testing
2. **Performance Optimization**: Queue and database tuning
3. **Monitoring Setup**: Comprehensive observability
4. **Documentation**: Complete system documentation

## 🚀 Next Steps

1. **Review & Approval**: Stakeholder review of architecture blueprint
2. **Database Migration**: Implement raw data storage schema
3. **Service Development**: Begin backend service implementation
4. **Queue Setup**: Configure RabbitMQ infrastructure
5. **Progressive Migration**: Implement services incrementally

This architecture provides a solid foundation for a scalable, maintainable ETL platform that can grow with your business needs while maintaining the essential user experience from the current system.

---

## 📋 APPENDIX A: Database Migration Strategy

### **Migration File Rules Implementation**

#### **Step 1: Modify Existing Migration 0001**
```python
# Edit services/backend-service/scripts/migrations/0001_initial_db_schema.py
# Add raw data tables to existing schema creation

def apply(connection):
    # ... existing schema creation ...

    # ADD: Raw data storage tables
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_etl_queue_tenant_status ON etl_job_queue(tenant_id, status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_etl_queue_priority ON etl_job_queue(priority, scheduled_at);")
```

#### **Step 2: Database Setup Execution**
```bash
# Complete database reset and setup
cd services/backend-service

# 1. Drop existing database (safe in greenfield)
python scripts/migration_runner.py --drop-all

# 2. Apply all migrations (including modified 0001)
python scripts/migration_runner.py --apply-all

# 3. Verify schema
python scripts/migration_runner.py --status
```

## 📋 APPENDIX B: Queue System Design

### **RabbitMQ Architecture**

#### **Exchange and Queue Structure**
```python
# Queue topology for multi-tenant ETL
RABBITMQ_TOPOLOGY = {
    'exchanges': {
        'etl.direct': {
            'type': 'direct',
            'durable': True,
            'description': 'Direct routing for ETL jobs'
        },
        'etl.topic': {
            'type': 'topic',
            'durable': True,
            'description': 'Topic-based routing for complex patterns'
        }
    },

    'queues': {
        # Tenant-specific queues for enterprise customers
        'etl.extract.tenant.{tenant_id}': {
            'routing_key': 'extract.tenant.{tenant_id}',
            'priority_levels': 10,
            'max_length': 1000
        },

        # Shared queues for standard customers
        'etl.extract.shared': {
            'routing_key': 'extract.shared',
            'priority_levels': 5,
            'max_length': 5000
        },

        # Transform and Load queues
        'etl.transform': {
            'routing_key': 'transform.*',
            'worker_count': 3
        },

        'etl.load': {
            'routing_key': 'load.*',
            'worker_count': 2
        }
    }
}
```

#### **Message Structure**
```python
# Standardized message format
class ETLMessage:
    tenant_id: int
    job_id: str
    job_type: str  # 'extract', 'transform', 'load'
    entity_type: str  # 'jira_issues', 'github_prs'
    payload: Dict[str, Any]
    priority: int = 5
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime
    scheduled_at: datetime

# Example extract message
extract_message = {
    'tenant_id': 1,
    'job_id': 'jira_extract_20250926_001',
    'job_type': 'extract',
    'entity_type': 'jira_issues',
    'payload': {
        'integration_id': 5,
        'jql_query': 'project = PROJ AND updated >= "2025-09-26"',
        'batch_size': 100
    },
    'priority': 3,
    'created_at': '2025-09-26T10:00:00Z'
}
```

### **Worker Pattern Implementation**
```python
# services/etl-service/app/workers/extract_worker.py
class ExtractWorker:
    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        self.connection = get_rabbitmq_connection()

    async def process_message(self, message: ETLMessage):
        """Process extraction job"""
        try:
            # Get appropriate extractor
            extractor = self.get_extractor(message.entity_type)

            # Perform extraction
            raw_data = await extractor.extract(
                tenant_id=message.tenant_id,
                **message.payload
            )

            # Store raw data
            await self.store_raw_data(raw_data)

            # Queue for transformation
            await self.queue_transform_job(message, raw_data)

        except Exception as e:
            await self.handle_error(message, e)
```

## 📋 APPENDIX C: Integration Framework Design

### **Pluggable Integration System**
```python
# services/etl-service/app/integrations/base.py
class BaseIntegration:
    """Base class for all data source integrations"""

    def __init__(self, integration_config: Integration):
        self.config = integration_config
        self.tenant_id = integration_config.tenant_id

    async def extract(self, entity_type: str, **params) -> List[Dict]:
        """Extract data from external system"""
        raise NotImplementedError

    async def validate_connection(self) -> bool:
        """Test connection to external system"""
        raise NotImplementedError

    def get_supported_entities(self) -> List[str]:
        """Return list of supported entity types"""
        raise NotImplementedError

# services/etl-service/app/integrations/jira_integration.py
class JiraIntegration(BaseIntegration):
    """Jira-specific integration implementation"""

    def get_supported_entities(self) -> List[str]:
        return ['issues', 'projects', 'statuses', 'issue_types']

    async def extract(self, entity_type: str, **params) -> List[Dict]:
        if entity_type == 'issues':
            return await self.extract_issues(**params)
        elif entity_type == 'projects':
            return await self.extract_projects(**params)
        # ... other entity types

    async def extract_issues(self, jql_query: str, batch_size: int = 100) -> List[Dict]:
        """Extract Jira issues using existing business logic"""
        # Reuse existing jira_client logic
        from app.jobs.jira.jira_client import JiraClient

        client = JiraClient(self.config)
        return await client.get_issues_batch(jql_query, batch_size)
```

### **Integration Registry**
```python
# services/etl-service/app/integrations/registry.py
class IntegrationRegistry:
    """Registry for all available integrations"""

    _integrations = {
        'jira': JiraIntegration,
        'github': GitHubIntegration,
        'azure_devops': AzureDevOpsIntegration,  # Future
        'gitlab': GitLabIntegration,  # Future
    }

    @classmethod
    def get_integration(cls, provider: str, config: Integration) -> BaseIntegration:
        """Get integration instance for provider"""
        integration_class = cls._integrations.get(provider.lower())
        if not integration_class:
            raise ValueError(f"Unsupported integration provider: {provider}")
        return integration_class(config)

    @classmethod
    def register_integration(cls, provider: str, integration_class: type):
        """Register new integration type"""
        cls._integrations[provider.lower()] = integration_class
```
