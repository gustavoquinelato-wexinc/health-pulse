# ETL Phase 2: ETL Service Refactoring

**Implemented**: NO ❌
**Duration**: 2 weeks (Weeks 5-6 of overall plan)
**Priority**: HIGH
**Risk Level**: MEDIUM
**Last Updated**: 2025-09-30

## 📊 Prerequisites (Must be complete before starting)

1. ✅ **Phase 0 Complete**: ETL Frontend + Backend ETL Module working
2. 🔄 **Phase 1 Complete**: RabbitMQ + Raw Data Storage + Queue Manager
   - RabbitMQ container running
   - Database tables created (`raw_extraction_data`, `etl_job_queue`)
   - Queue manager implemented in backend-service
   - Raw data APIs functional

**Status**: Cannot start until Phase 1 is complete.

## 💼 Business Outcome

**Extract-Only ETL Service**: Transform the current monolithic ETL service (`services/etl-service`) into a focused extraction service that:
- Extracts raw data from external systems (Jira, GitHub, etc.)
- Stores complete API responses in `raw_extraction_data` table
- Publishes transform jobs to RabbitMQ queue
- NO transformation or loading logic (moved to backend-service workers)

This creates true separation between Extract and Transform/Load operations.

## 🎯 Objectives

1. **Service Refactoring**: Convert ETL service jobs to extract-only pattern
2. **Raw Data Storage**: Store complete API responses after extraction
3. **Queue Publishing**: Publish transform jobs to RabbitMQ after extraction
4. **Worker Implementation**: Create transform/load workers in backend-service
5. **Job Orchestration**: Update orchestrator for queue-based processing

## 📋 Task Breakdown

### Task 2.1: ETL Service Architecture Refactor
**Duration**: 3 days  
**Priority**: CRITICAL  

#### Remove Transform/Load Logic
```python
# services/etl-service/app/jobs/base_job.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from app.core.queue_manager import ETLQueueManager
from app.core.raw_data_storage import RawDataStorage

class BaseExtractJob(ABC):
    """Base class for extraction-only jobs"""
    
    def __init__(self, tenant_id: int, integration_id: int):
        self.tenant_id = tenant_id
        self.integration_id = integration_id
        self.queue_manager = ETLQueueManager()
        self.raw_storage = RawDataStorage()
    
    @abstractmethod
    async def extract_data(self) -> List[Dict[str, Any]]:
        """Extract raw data from external system"""
        pass
    
    async def run(self) -> Dict[str, Any]:
        """Execute extraction job"""
        try:
            # Extract raw data
            raw_data_list = await self.extract_data()
            
            # Store raw data
            stored_ids = []
            for raw_data in raw_data_list:
                record_id = await self.raw_storage.store(
                    tenant_id=self.tenant_id,
                    integration_id=self.integration_id,
                    entity_type=self.get_entity_type(),
                    external_id=raw_data.get('id'),
                    raw_data=raw_data,
                    extraction_metadata=self.get_extraction_metadata()
                )
                stored_ids.append(record_id)
            
            # Queue transformation job
            await self.queue_manager.publish_transform_job(
                tenant_id=self.tenant_id,
                raw_data_ids=stored_ids,
                entity_type=self.get_entity_type()
            )
            
            return {
                'status': 'success',
                'extracted_count': len(raw_data_list),
                'stored_ids': stored_ids,
                'queued_for_transform': True
            }
            
        except Exception as e:
            await self.handle_extraction_error(e)
            raise
    
    @abstractmethod
    def get_entity_type(self) -> str:
        """Return entity type for this job"""
        pass
    
    def get_extraction_metadata(self) -> Dict[str, Any]:
        """Return extraction context metadata"""
        return {
            'tenant_id': self.tenant_id,
            'integration_id': self.integration_id,
            'extraction_time': datetime.utcnow().isoformat(),
            'job_type': self.__class__.__name__
        }
```

#### Refactor Jira Job
```python
# services/etl-service/app/jobs/jira/jira_extract_job.py
from typing import Dict, Any, List
from app.jobs.base_job import BaseExtractJob
from app.integrations.jira_client import JiraClient

class JiraExtractJob(BaseExtractJob):
    """Jira extraction job - extract only"""
    
    def __init__(self, tenant_id: int, integration_id: int, extract_type: str = 'issues'):
        super().__init__(tenant_id, integration_id)
        self.extract_type = extract_type
        self.jira_client = JiraClient(integration_id)
    
    async def extract_data(self) -> List[Dict[str, Any]]:
        """Extract raw data from Jira"""
        if self.extract_type == 'issues':
            return await self.extract_issues()
        elif self.extract_type == 'projects':
            return await self.extract_projects()
        elif self.extract_type == 'statuses':
            return await self.extract_statuses()
        else:
            raise ValueError(f"Unknown extract type: {self.extract_type}")
    
    async def extract_issues(self) -> List[Dict[str, Any]]:
        """Extract Jira issues"""
        # Use existing extraction logic but return raw data
        issues = []
        
        # Get last sync date for incremental extraction
        last_sync = await self.get_last_sync_date()
        
        # Build JQL query for incremental sync
        jql = self.build_incremental_jql(last_sync)
        
        # Extract issues in batches
        start_at = 0
        batch_size = 100
        
        while True:
            batch = await self.jira_client.search_issues(
                jql=jql,
                start_at=start_at,
                max_results=batch_size,
                expand=['changelog', 'renderedFields']
            )
            
            if not batch.get('issues'):
                break
            
            issues.extend(batch['issues'])
            start_at += batch_size
            
            if len(batch['issues']) < batch_size:
                break
        
        return issues
    
    def get_entity_type(self) -> str:
        """Return entity type"""
        return f"jira_{self.extract_type}"
    
    def get_extraction_metadata(self) -> Dict[str, Any]:
        """Return Jira-specific extraction metadata"""
        metadata = super().get_extraction_metadata()
        metadata.update({
            'extract_type': self.extract_type,
            'jira_instance': self.jira_client.base_url,
            'incremental_sync': True
        })
        return metadata
```

### Task 2.2: Raw Data Storage Implementation
**Duration**: 2 days  
**Priority**: HIGH  

#### Raw Data Storage Service
```python
# services/etl-service/app/core/raw_data_storage.py
import httpx
from typing import Dict, Any, Optional
from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class RawDataStorage:
    """Service for storing raw extraction data via backend API"""
    
    def __init__(self):
        self.settings = get_settings()
        self.backend_url = self.settings.BACKEND_SERVICE_URL
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def store(
        self,
        tenant_id: int,
        integration_id: int,
        entity_type: str,
        external_id: Optional[str],
        raw_data: Dict[str, Any],
        extraction_metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Store raw data via backend API"""
        try:
            payload = {
                'integration_id': integration_id,
                'entity_type': entity_type,
                'external_id': external_id,
                'raw_data': raw_data,
                'extraction_metadata': extraction_metadata
            }
            
            # Get auth token for tenant
            auth_token = await self.get_service_token(tenant_id)
            
            response = await self.client.post(
                f"{self.backend_url}/api/v1/etl/raw-data/store",
                json=payload,
                headers={'Authorization': f'Bearer {auth_token}'}
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Stored raw data for {entity_type}: {result['record_id']}")
            return result['record_id']
            
        except Exception as e:
            logger.error(f"Failed to store raw data: {e}")
            raise
    
    async def get_service_token(self, tenant_id: int) -> str:
        """Get service authentication token for tenant"""
        # Implementation for service-to-service authentication
        # This would use a service account or JWT token
        pass
```

### Task 2.3: Queue Workers Implementation
**Duration**: 3 days  
**Priority**: HIGH  

#### Queue Worker Base Class
```python
# services/etl-service/app/workers/base_worker.py
import pika
import json
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any
from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class BaseQueueWorker(ABC):
    """Base class for RabbitMQ queue workers"""
    
    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        self.settings = get_settings()
        self.connection = None
        self.channel = None
    
    async def connect(self):
        """Connect to RabbitMQ"""
        try:
            connection_params = pika.URLParameters(self.settings.RABBITMQ_URL)
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()
            
            # Ensure queue exists
            self.channel.queue_declare(queue=self.queue_name, durable=True)
            
            logger.info(f"Connected to queue: {self.queue_name}")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    def start_consuming(self):
        """Start consuming messages from queue"""
        try:
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=self.on_message,
                auto_ack=False
            )
            
            logger.info(f"Starting to consume from {self.queue_name}")
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("Stopping consumer...")
            self.channel.stop_consuming()
            self.connection.close()
    
    def on_message(self, channel, method, properties, body):
        """Handle incoming message"""
        try:
            message = json.loads(body.decode('utf-8'))
            logger.info(f"Processing message: {message.get('job_type', 'unknown')}")
            
            # Process message asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.process_message(message))
            
            if result.get('success', False):
                channel.basic_ack(delivery_tag=method.delivery_tag)
                logger.info("Message processed successfully")
            else:
                # Reject and requeue for retry
                channel.basic_nack(
                    delivery_tag=method.delivery_tag,
                    requeue=True
                )
                logger.error(f"Message processing failed: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            channel.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=False  # Don't requeue malformed messages
            )
    
    @abstractmethod
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process the message - implemented by subclasses"""
        pass
```

#### Extract Queue Worker
```python
# services/etl-service/app/workers/extract_worker.py
from typing import Dict, Any
from app.workers.base_worker import BaseQueueWorker
from app.jobs.jira.jira_extract_job import JiraExtractJob
from app.jobs.github.github_extract_job import GitHubExtractJob

class ExtractWorker(BaseQueueWorker):
    """Worker for processing extraction jobs"""
    
    def __init__(self):
        super().__init__('etl.extract')
    
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process extraction job message"""
        try:
            tenant_id = message['tenant_id']
            integration_id = message.get('integration_id')
            entity_type = message.get('entity_type')
            payload = message.get('payload', {})
            
            # Route to appropriate extraction job
            if entity_type.startswith('jira_'):
                extract_type = entity_type.replace('jira_', '')
                job = JiraExtractJob(tenant_id, integration_id, extract_type)
            elif entity_type.startswith('github_'):
                extract_type = entity_type.replace('github_', '')
                job = GitHubExtractJob(tenant_id, integration_id, extract_type)
            else:
                raise ValueError(f"Unknown entity type: {entity_type}")
            
            # Execute extraction
            result = await job.run()
            
            return {
                'success': True,
                'result': result
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
```

### Task 2.4: Integration Framework
**Duration**: 2 days  
**Priority**: MEDIUM  

#### Pluggable Integration Pattern
```python
# services/etl-service/app/integrations/base_integration.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseIntegration(ABC):
    """Base class for all external system integrations"""
    
    def __init__(self, integration_id: int, config: Dict[str, Any]):
        self.integration_id = integration_id
        self.config = config
        self.client = None
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with external system"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to external system"""
        pass
    
    @abstractmethod
    async def extract_entities(self, entity_type: str, **kwargs) -> List[Dict[str, Any]]:
        """Extract entities from external system"""
        pass
    
    @abstractmethod
    def get_supported_entities(self) -> List[str]:
        """Return list of supported entity types"""
        pass
    
    async def get_incremental_sync_date(self, entity_type: str) -> Optional[str]:
        """Get last sync date for incremental extraction"""
        # Implementation to get last sync date from database
        pass
```

## ✅ Success Criteria

1. **Service Refactoring**: ETL service handles extraction only
2. **Raw Data Storage**: Complete API responses stored via backend API
3. **Queue Processing**: RabbitMQ workers process extraction jobs
4. **Integration Framework**: Pluggable pattern for new data sources
5. **Job Orchestration**: Updated orchestrator uses queue system

## 🚨 Risk Mitigation

1. **Service Dependencies**: Implement circuit breakers for backend API calls
2. **Queue Reliability**: Add dead letter queues for failed messages
3. **Data Integrity**: Validate raw data before storage
4. **Performance**: Monitor queue processing times and throughput
5. **Error Handling**: Comprehensive error logging and alerting

## 📋 Implementation Checklist

- [ ] Refactor ETL service to extract-only operations
- [ ] Implement raw data storage service
- [ ] Create queue worker base classes
- [ ] Add extract queue worker
- [ ] Update Jira job for extraction only
- [ ] Update GitHub job for extraction only
- [ ] Create integration framework base classes
- [ ] Update orchestrator for queue-based processing
- [ ] Test queue message flow
- [ ] Validate raw data storage and retrieval

## 🔄 Next Steps

After completion, this enables:
- **Phase 3**: Frontend migration to new API endpoints
- **Transform/Load**: Backend service processes queued jobs
- **Monitoring**: Queue-based job tracking and progress
