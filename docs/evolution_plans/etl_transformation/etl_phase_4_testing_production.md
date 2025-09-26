# ETL Phase 4: Testing & Production

**Implemented**: NO ❌  
**Duration**: Weeks 7-8  
**Priority**: CRITICAL  
**Risk Level**: HIGH  

## 💼 Business Outcome

**Production-Ready ETL Platform**: Comprehensive testing, performance optimization, and production deployment of the new ETL architecture, ensuring 99% uptime and 50% performance improvement over the legacy system.

## 🎯 Objectives

1. **End-to-End Testing**: Comprehensive testing of the complete ETL pipeline
2. **Performance Optimization**: Achieve 50% improvement in processing speed
3. **Production Deployment**: Safe deployment with rollback capabilities
4. **Monitoring & Observability**: Complete visibility into system health
5. **Documentation & Training**: User guides and operational procedures

## 📋 Task Breakdown

### Task 4.1: End-to-End Testing
**Duration**: 3 days  
**Priority**: CRITICAL  

#### Integration Test Suite
```python
# tests/integration/test_etl_pipeline.py
import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.etl.queue.queue_manager import ETLQueueManager
from app.models.unified_models import RawExtractionData, WorkItem, Pr
from tests.fixtures.sample_data import SAMPLE_JIRA_ISSUE, SAMPLE_GITHUB_PR

class TestETLPipeline:
    """End-to-end ETL pipeline tests"""
    
    @pytest.mark.asyncio
    async def test_complete_jira_pipeline(self, test_tenant, test_integration):
        """Test complete Jira ETL pipeline: Extract → Transform → Load"""
        
        # 1. Trigger extraction job
        queue_manager = ETLQueueManager()
        await queue_manager.connect()
        
        await queue_manager.publish_extract_job(
            tenant_id=test_tenant.id,
            job_data={
                'entity_type': 'jira_issues',
                'integration_id': test_integration.id,
                'payload': {'jql': 'project = TEST'}
            }
        )
        
        # 2. Wait for extraction to complete
        await asyncio.sleep(5)
        
        # 3. Verify raw data was stored
        db = next(get_db_session())
        raw_records = db.query(RawExtractionData).filter(
            RawExtractionData.tenant_id == test_tenant.id,
            RawExtractionData.entity_type == 'jira_issues'
        ).all()
        
        assert len(raw_records) > 0
        assert raw_records[0].processing_status == 'pending'
        
        # 4. Wait for transformation to complete
        await asyncio.sleep(10)
        
        # 5. Verify work items were created
        work_items = db.query(WorkItem).filter(
            WorkItem.tenant_id == test_tenant.id
        ).all()
        
        assert len(work_items) > 0
        assert work_items[0].title is not None
        assert work_items[0].status is not None
        
        # 6. Verify vectorization was queued
        # Check vectorization queue for new entries
        
        db.close()
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, test_tenant):
        """Test error handling and recovery mechanisms"""
        
        # 1. Trigger job with invalid configuration
        queue_manager = ETLQueueManager()
        await queue_manager.connect()
        
        await queue_manager.publish_extract_job(
            tenant_id=test_tenant.id,
            job_data={
                'entity_type': 'invalid_type',
                'integration_id': 999,  # Non-existent integration
                'payload': {}
            }
        )
        
        # 2. Wait for error handling
        await asyncio.sleep(5)
        
        # 3. Verify error was logged and job marked as failed
        db = next(get_db_session())
        raw_records = db.query(RawExtractionData).filter(
            RawExtractionData.tenant_id == test_tenant.id,
            RawExtractionData.processing_status == 'failed'
        ).all()
        
        assert len(raw_records) > 0
        assert raw_records[0].error_details is not None
        
        db.close()
    
    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self, test_tenant_1, test_tenant_2):
        """Test that tenant data is properly isolated"""
        
        # 1. Create data for both tenants
        queue_manager = ETLQueueManager()
        await queue_manager.connect()
        
        # Tenant 1 job
        await queue_manager.publish_extract_job(
            tenant_id=test_tenant_1.id,
            job_data={
                'entity_type': 'jira_issues',
                'integration_id': 1,
                'payload': {'jql': 'project = TENANT1'}
            }
        )
        
        # Tenant 2 job
        await queue_manager.publish_extract_job(
            tenant_id=test_tenant_2.id,
            job_data={
                'entity_type': 'jira_issues',
                'integration_id': 2,
                'payload': {'jql': 'project = TENANT2'}
            }
        )
        
        # 2. Wait for processing
        await asyncio.sleep(10)
        
        # 3. Verify tenant isolation
        db = next(get_db_session())
        
        tenant_1_data = db.query(RawExtractionData).filter(
            RawExtractionData.tenant_id == test_tenant_1.id
        ).all()
        
        tenant_2_data = db.query(RawExtractionData).filter(
            RawExtractionData.tenant_id == test_tenant_2.id
        ).all()
        
        # Verify each tenant only sees their own data
        assert all(record.tenant_id == test_tenant_1.id for record in tenant_1_data)
        assert all(record.tenant_id == test_tenant_2.id for record in tenant_2_data)
        
        db.close()
```

#### Performance Test Suite
```python
# tests/performance/test_etl_performance.py
import pytest
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from app.etl.queue.queue_manager import ETLQueueManager

class TestETLPerformance:
    """Performance tests for ETL pipeline"""
    
    @pytest.mark.asyncio
    async def test_throughput_benchmark(self, test_tenant):
        """Test ETL pipeline throughput"""
        
        start_time = time.time()
        job_count = 100
        
        queue_manager = ETLQueueManager()
        await queue_manager.connect()
        
        # Submit multiple jobs concurrently
        tasks = []
        for i in range(job_count):
            task = queue_manager.publish_extract_job(
                tenant_id=test_tenant.id,
                job_data={
                    'entity_type': 'jira_issues',
                    'integration_id': 1,
                    'payload': {'jql': f'key = TEST-{i}'}
                }
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        # Wait for all jobs to complete
        await asyncio.sleep(30)
        
        end_time = time.time()
        total_time = end_time - start_time
        throughput = job_count / total_time
        
        # Assert minimum throughput (jobs per second)
        assert throughput >= 5.0, f"Throughput {throughput:.2f} jobs/sec below minimum"
        
        print(f"ETL Throughput: {throughput:.2f} jobs/second")
    
    @pytest.mark.asyncio
    async def test_memory_usage(self, test_tenant):
        """Test memory usage during large data processing"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process large dataset
        queue_manager = ETLQueueManager()
        await queue_manager.connect()
        
        # Submit job with large payload
        large_payload = {'jql': 'project = LARGE', 'batch_size': 1000}
        
        await queue_manager.publish_extract_job(
            tenant_id=test_tenant.id,
            job_data={
                'entity_type': 'jira_issues',
                'integration_id': 1,
                'payload': large_payload
            }
        )
        
        # Wait for processing
        await asyncio.sleep(60)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Assert memory usage stays within reasonable bounds
        assert memory_increase < 500, f"Memory increase {memory_increase:.2f}MB too high"
        
        print(f"Memory usage: {initial_memory:.2f}MB → {final_memory:.2f}MB (+{memory_increase:.2f}MB)")
```

### Task 4.2: Performance Optimization
**Duration**: 2 days  
**Priority**: HIGH  

#### Database Query Optimization
```python
# services/backend-service/app/etl/optimizations/query_optimizer.py
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.core.database import get_db_session

class ETLQueryOptimizer:
    """Optimize database queries for ETL operations"""
    
    @staticmethod
    async def optimize_raw_data_queries():
        """Add performance indexes for raw data queries"""
        db = next(get_db_session())
        
        try:
            # Composite indexes for common query patterns
            db.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_raw_data_tenant_type_status 
                ON raw_extraction_data(tenant_id, entity_type, processing_status);
            """))
            
            db.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_raw_data_created_at_desc 
                ON raw_extraction_data(created_at DESC);
            """))
            
            # Partial indexes for active processing
            db.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_raw_data_pending 
                ON raw_extraction_data(tenant_id, entity_type) 
                WHERE processing_status = 'pending';
            """))
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()
    
    @staticmethod
    async def optimize_bulk_operations():
        """Optimize bulk insert/update operations"""
        db = next(get_db_session())
        
        try:
            # Increase work_mem for bulk operations
            db.execute(text("SET work_mem = '256MB';"))
            
            # Disable autocommit for bulk operations
            db.execute(text("SET autocommit = false;"))
            
            # Optimize for bulk inserts
            db.execute(text("SET synchronous_commit = off;"))
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()
```

#### Queue Performance Tuning
```python
# services/etl-service/app/core/queue_optimizer.py
import pika
from app.core.config import get_settings

class QueueOptimizer:
    """Optimize RabbitMQ performance for ETL workloads"""
    
    @staticmethod
    async def configure_high_throughput():
        """Configure RabbitMQ for high throughput"""
        settings = get_settings()
        
        connection_params = pika.URLParameters(settings.RABBITMQ_URL)
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()
        
        try:
            # Set prefetch count for better load distribution
            channel.basic_qos(prefetch_count=10, global_qos=True)
            
            # Configure queue arguments for performance
            queue_args = {
                'x-max-length': 10000,  # Prevent queue from growing too large
                'x-message-ttl': 3600000,  # 1 hour TTL
                'x-max-priority': 10  # Enable priority queuing
            }
            
            # Apply to all ETL queues
            queues = ['etl.extract', 'etl.transform', 'etl.load']
            for queue_name in queues:
                channel.queue_declare(
                    queue=queue_name,
                    durable=True,
                    arguments=queue_args
                )
            
        finally:
            connection.close()
```

### Task 4.3: Production Deployment
**Duration**: 2 days  
**Priority**: CRITICAL  

#### Deployment Script
```bash
#!/bin/bash
# scripts/deploy_etl_production.sh

set -e

echo "🚀 Starting ETL Production Deployment"

# 1. Backup current database
echo "📋 Creating database backup..."
docker exec pulse-postgres pg_dump -U postgres pulse_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Stop current services
echo "⏹️ Stopping current services..."
docker-compose down

# 3. Pull latest images
echo "📥 Pulling latest images..."
docker-compose pull

# 4. Start database services first
echo "🗄️ Starting database services..."
docker-compose up -d postgres redis qdrant rabbitmq

# 5. Wait for databases to be ready
echo "⏳ Waiting for databases..."
sleep 30

# 6. Run database migrations
echo "📋 Running database migrations..."
docker-compose run --rm backend python scripts/migration_runner.py --apply-all

# 7. Start backend services
echo "🔧 Starting backend services..."
docker-compose up -d backend etl

# 8. Wait for backend to be ready
echo "⏳ Waiting for backend services..."
sleep 15

# 9. Start frontend
echo "🎨 Starting frontend..."
docker-compose up -d frontend

# 10. Verify deployment
echo "✅ Verifying deployment..."
./scripts/verify_deployment.sh

echo "🎉 ETL Production Deployment Complete!"
```

#### Health Check Script
```bash
#!/bin/bash
# scripts/verify_deployment.sh

set -e

echo "🔍 Verifying ETL Deployment"

# Check service health
services=("frontend" "backend" "etl" "postgres" "redis" "qdrant" "rabbitmq")

for service in "${services[@]}"; do
    echo "Checking $service..."
    if docker-compose ps $service | grep -q "Up"; then
        echo "✅ $service is running"
    else
        echo "❌ $service is not running"
        exit 1
    fi
done

# Check API endpoints
echo "🔍 Testing API endpoints..."

# Backend health check
if curl -f http://localhost:3001/health > /dev/null 2>&1; then
    echo "✅ Backend API is responding"
else
    echo "❌ Backend API is not responding"
    exit 1
fi

# ETL service health check
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ ETL service is responding"
else
    echo "❌ ETL service is not responding"
    exit 1
fi

# RabbitMQ management interface
if curl -f http://localhost:15672 > /dev/null 2>&1; then
    echo "✅ RabbitMQ management is accessible"
else
    echo "❌ RabbitMQ management is not accessible"
    exit 1
fi

echo "🎉 All services are healthy!"
```

### Task 4.4: Monitoring & Observability
**Duration**: 1 day  
**Priority**: HIGH  

#### Monitoring Dashboard Configuration
```yaml
# monitoring/docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: pulse-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana:latest
    container_name: pulse-grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

volumes:
  prometheus_data:
  grafana_data:
```

#### ETL Metrics Collection
```python
# services/backend-service/app/etl/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import time
from functools import wraps

# ETL Pipeline Metrics
etl_jobs_total = Counter('etl_jobs_total', 'Total ETL jobs processed', ['tenant_id', 'job_type', 'status'])
etl_job_duration = Histogram('etl_job_duration_seconds', 'ETL job duration', ['tenant_id', 'job_type'])
etl_queue_size = Gauge('etl_queue_size', 'Current queue size', ['queue_name'])
etl_processing_rate = Gauge('etl_processing_rate', 'Items processed per second', ['tenant_id', 'entity_type'])

def track_etl_job(job_type: str):
    """Decorator to track ETL job metrics"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tenant_id = kwargs.get('tenant_id', 'unknown')
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                etl_jobs_total.labels(tenant_id=tenant_id, job_type=job_type, status='success').inc()
                return result
            except Exception as e:
                etl_jobs_total.labels(tenant_id=tenant_id, job_type=job_type, status='error').inc()
                raise
            finally:
                duration = time.time() - start_time
                etl_job_duration.labels(tenant_id=tenant_id, job_type=job_type).observe(duration)
        
        return wrapper
    return decorator
```

## ✅ Success Criteria

1. **Testing**: 100% pass rate on integration and performance tests
2. **Performance**: 50% improvement in processing speed over legacy system
3. **Deployment**: Zero-downtime deployment with rollback capability
4. **Monitoring**: Complete observability with alerts and dashboards
5. **Documentation**: Comprehensive user and operational guides

## 🚨 Risk Mitigation

1. **Deployment Risks**: Blue-green deployment with automatic rollback
2. **Performance Issues**: Load testing and performance monitoring
3. **Data Integrity**: Comprehensive validation and backup procedures
4. **Service Dependencies**: Circuit breakers and fallback mechanisms
5. **User Impact**: Gradual rollout with user communication

## 📋 Implementation Checklist

- [ ] Create comprehensive integration test suite
- [ ] Implement performance benchmarking tests
- [ ] Optimize database queries and indexes
- [ ] Configure RabbitMQ for high throughput
- [ ] Create production deployment scripts
- [ ] Set up monitoring and alerting
- [ ] Configure Grafana dashboards
- [ ] Create operational runbooks
- [ ] Test disaster recovery procedures
- [ ] Validate security configurations

## 🔄 Next Steps

After completion, this enables:
- **Production Operations**: Full ETL platform in production
- **Continuous Improvement**: Performance monitoring and optimization
- **Scale Planning**: Capacity planning for growth
- **Feature Development**: Foundation for advanced ETL features
