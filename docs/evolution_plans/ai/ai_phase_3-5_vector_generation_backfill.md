# Phase 3-5: High-Performance Vector Generation & Backfill

**Implemented**: NO ❌
**Duration**: 2 days (Days 8-9 of 10)
**Priority**: HIGH
**Dependencies**: Phase 3-4 completion

## 🎯 Objectives

1. **High-Performance Vector Generation**: 10x faster than hackathon approach with optimized batching
2. **Intelligent Backfill**: Smart population of vectors for existing data (1M+ records)
3. **Multi-Provider Optimization**: Use best provider for each use case (cost vs performance)
4. **Progress Monitoring**: Real-time progress tracking for large-scale operations
5. **Error Recovery**: Robust error handling and retry mechanisms
6. **Client Isolation**: Perfect separation of vector data by client

## 🚀 High-Performance Vector Generation Architecture

### **Optimized Vector Generation Pipeline**
```python
# services/etl-service/app/ai/vector_generation_pipeline.py
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import time
import math

logger = logging.getLogger(__name__)

@dataclass
class VectorGenerationJob:
    """Vector generation job configuration"""
    client_id: int
    table_name: str
    records: List[Dict[str, Any]]
    vector_type: str  # 'content', 'summary', 'metadata'
    provider_preference: str  # 'fast', 'balanced', 'quality'
    batch_size: int = 100
    max_retries: int = 3

@dataclass
class VectorGenerationProgress:
    """Progress tracking for vector generation"""
    total_records: int
    processed_records: int
    successful_records: int
    failed_records: int
    current_batch: int
    total_batches: int
    start_time: float
    estimated_completion: float
    current_provider: str
    errors: List[str]

class HighPerformanceVectorGenerator:
    """High-performance vector generation with intelligent provider selection"""
    
    def __init__(self, ai_provider_manager, qdrant_client):
        self.ai_provider_manager = ai_provider_manager
        self.qdrant_client = qdrant_client
        
        # Performance optimization
        self.max_concurrent_batches = 4
        self.executor = ThreadPoolExecutor(max_workers=8)
        
        # Progress tracking
        self.active_jobs: Dict[str, VectorGenerationProgress] = {}
        
        # Provider performance tracking
        self.provider_performance = {
            "sentence_transformers": {"speed": 1000, "cost": 0.0, "quality": 0.8},
            "openai": {"speed": 100, "cost": 0.0001, "quality": 0.95},
            "azure_openai": {"speed": 500, "cost": 0.0001, "quality": 0.95}
        }
    
    async def generate_vectors_for_table(self, job: VectorGenerationJob) -> VectorGenerationProgress:
        """Generate vectors for entire table with progress tracking"""
        job_id = f"{job.client_id}_{job.table_name}_{job.vector_type}"
        
        # Initialize progress tracking
        total_batches = math.ceil(len(job.records) / job.batch_size)
        progress = VectorGenerationProgress(
            total_records=len(job.records),
            processed_records=0,
            successful_records=0,
            failed_records=0,
            current_batch=0,
            total_batches=total_batches,
            start_time=time.time(),
            estimated_completion=0,
            current_provider="",
            errors=[]
        )
        
        self.active_jobs[job_id] = progress
        
        try:
            # Select optimal provider based on preference and data size
            provider = await self._select_optimal_provider(job)
            progress.current_provider = provider.config.provider_type
            
            logger.info(f"Starting vector generation for {job.table_name} with {provider.config.provider_type}")
            
            # Ensure Qdrant collection exists
            await self.qdrant_client.create_collection(
                job.client_id, 
                job.table_name,
                provider.model_info.dimensions
            )
            
            # Process in batches with concurrency control
            semaphore = asyncio.Semaphore(self.max_concurrent_batches)
            
            batch_tasks = []
            for i in range(0, len(job.records), job.batch_size):
                batch = job.records[i:i + job.batch_size]
                batch_num = i // job.batch_size + 1
                
                task = self._process_batch_with_semaphore(
                    semaphore, job, batch, batch_num, provider, progress
                )
                batch_tasks.append(task)
            
            # Execute all batches with controlled concurrency
            await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Calculate final statistics
            progress.estimated_completion = time.time()
            total_time = progress.estimated_completion - progress.start_time
            
            logger.info(f"Vector generation completed for {job.table_name}: "
                       f"{progress.successful_records}/{progress.total_records} successful "
                       f"in {total_time:.2f}s")
            
            return progress
            
        except Exception as e:
            logger.error(f"Vector generation failed for {job.table_name}: {e}")
            progress.errors.append(str(e))
            return progress
        
        finally:
            # Clean up job tracking
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
    
    async def _select_optimal_provider(self, job: VectorGenerationJob):
        """Select optimal provider based on job requirements"""
        available_providers = await self.ai_provider_manager.get_available_providers(job.client_id)
        
        if job.provider_preference == "fast":
            # Prioritize speed: local models first
            for provider_type in ["sentence_transformers", "azure_openai", "openai"]:
                if provider_type in available_providers:
                    return await self.ai_provider_manager.get_provider(job.client_id, provider_type)
        
        elif job.provider_preference == "quality":
            # Prioritize quality: OpenAI models first
            for provider_type in ["openai", "azure_openai", "sentence_transformers"]:
                if provider_type in available_providers:
                    return await self.ai_provider_manager.get_provider(job.client_id, provider_type)
        
        else:  # balanced
            # Balance cost and performance
            if len(job.records) > 10000:
                # Large dataset: use free local models
                if "sentence_transformers" in available_providers:
                    return await self.ai_provider_manager.get_provider(job.client_id, "sentence_transformers")
            
            # Medium dataset: use Azure OpenAI for balance
            if "azure_openai" in available_providers:
                return await self.ai_provider_manager.get_provider(job.client_id, "azure_openai")
        
        # Fallback to first available provider
        if available_providers:
            provider_type = list(available_providers.keys())[0]
            return await self.ai_provider_manager.get_provider(job.client_id, provider_type)
        
        raise ValueError("No AI providers available for client")
    
    async def _process_batch_with_semaphore(self, semaphore, job, batch, batch_num, provider, progress):
        """Process batch with concurrency control"""
        async with semaphore:
            return await self._process_batch(job, batch, batch_num, provider, progress)
    
    async def _process_batch(self, job: VectorGenerationJob, batch: List[Dict], 
                           batch_num: int, provider, progress: VectorGenerationProgress):
        """Process single batch of records"""
        try:
            # Extract text content for embedding
            texts = []
            for record in batch:
                text_content = self._extract_text_content(record, job.vector_type)
                texts.append(text_content)
            
            # Generate embeddings for batch
            embeddings = await provider.generate_embeddings(texts)
            
            if len(embeddings) != len(batch):
                raise ValueError(f"Embedding count mismatch: {len(embeddings)} vs {len(batch)}")
            
            # Prepare Qdrant records
            qdrant_records = []
            for i, (record, embedding) in enumerate(zip(batch, embeddings)):
                qdrant_record = {
                    "record_id": record["id"],
                    "vector": embedding,
                    "metadata": {
                        "text_content": texts[i][:500],  # Store first 500 chars for debugging
                        "vector_type": job.vector_type,
                        "generated_at": time.time(),
                        "provider": provider.config.provider_type,
                        "model": provider.config.model_name
                    }
                }
                qdrant_records.append(qdrant_record)
            
            # Store in Qdrant
            point_ids = await self.qdrant_client.upsert_vectors_batch(
                job.client_id, job.table_name, qdrant_records
            )
            
            # Update PostgreSQL with Qdrant references
            await self._update_qdrant_references(job, batch, point_ids, provider)
            
            # Update progress
            progress.processed_records += len(batch)
            progress.successful_records += len(batch)
            progress.current_batch = batch_num
            
            # Update estimated completion time
            if progress.processed_records > 0:
                elapsed_time = time.time() - progress.start_time
                records_per_second = progress.processed_records / elapsed_time
                remaining_records = progress.total_records - progress.processed_records
                progress.estimated_completion = time.time() + (remaining_records / records_per_second)
            
            logger.info(f"Batch {batch_num}/{progress.total_batches} completed: "
                       f"{progress.processed_records}/{progress.total_records} records")
            
        except Exception as e:
            logger.error(f"Batch {batch_num} failed: {e}")
            progress.failed_records += len(batch)
            progress.errors.append(f"Batch {batch_num}: {str(e)}")
    
    def _extract_text_content(self, record: Dict[str, Any], vector_type: str) -> str:
        """Extract text content based on vector type"""
        if vector_type == "content":
            # Full content embedding
            parts = []
            for field in ["summary", "description", "title", "content"]:
                if field in record and record[field]:
                    parts.append(str(record[field]))
            return " ".join(parts)
        
        elif vector_type == "summary":
            # Summary-only embedding
            return str(record.get("summary", record.get("title", "")))
        
        elif vector_type == "metadata":
            # Metadata embedding
            parts = []
            for field in ["status", "priority", "type", "labels"]:
                if field in record and record[field]:
                    parts.append(f"{field}: {record[field]}")
            return " ".join(parts)
        
        else:
            # Default: use summary or title
            return str(record.get("summary", record.get("title", record.get("description", ""))))
    
    async def _update_qdrant_references(self, job: VectorGenerationJob, batch: List[Dict], 
                                      point_ids: List[str], provider):
        """Update PostgreSQL with Qdrant point references"""
        try:
            # This would be implemented to update the qdrant_vectors table
            # with references to the stored vectors
            pass
        except Exception as e:
            logger.error(f"Failed to update Qdrant references: {e}")
    
    def get_job_progress(self, job_id: str) -> Optional[VectorGenerationProgress]:
        """Get progress for active job"""
        return self.active_jobs.get(job_id)
    
    def get_all_active_jobs(self) -> Dict[str, VectorGenerationProgress]:
        """Get all active job progress"""
        return self.active_jobs.copy()
```

### **Intelligent Backfill Manager**
```python
# services/etl-service/app/ai/backfill_manager.py
import asyncio
import logging
from typing import List, Dict, Any, Optional
from .vector_generation_pipeline import HighPerformanceVectorGenerator, VectorGenerationJob

logger = logging.getLogger(__name__)

class IntelligentBackfillManager:
    """Manages intelligent backfill of vectors for existing data"""
    
    def __init__(self, vector_generator: HighPerformanceVectorGenerator, db_session):
        self.vector_generator = vector_generator
        self.db_session = db_session
        
        # Tables to backfill (all 24 business tables)
        self.backfill_tables = [
            "issues", "pull_requests", "pull_request_comments", "pull_request_reviews",
            "projects", "repositories", "users", "clients", "statuses", "issuetypes",
            "workflows", "issue_changelogs", "jira_pull_request_links", 
            "projects_issuetypes", "projects_statuses", "user_permissions",
            "system_settings", "dora_market_benchmarks", "dora_metric_insights"
        ]
    
    async def start_intelligent_backfill(self, client_id: int, 
                                       priority_tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Start intelligent backfill process for client"""
        try:
            # Analyze existing data to prioritize backfill
            backfill_plan = await self._create_backfill_plan(client_id, priority_tables)
            
            logger.info(f"Starting backfill for client {client_id} with {len(backfill_plan)} tables")
            
            # Execute backfill plan
            results = {}
            for table_plan in backfill_plan:
                table_name = table_plan["table_name"]
                
                logger.info(f"Starting backfill for table: {table_name}")
                
                # Create vector generation job
                job = VectorGenerationJob(
                    client_id=client_id,
                    table_name=table_name,
                    records=table_plan["records"],
                    vector_type="content",  # Default to content vectors
                    provider_preference=table_plan["provider_preference"],
                    batch_size=table_plan["batch_size"]
                )
                
                # Execute vector generation
                progress = await self.vector_generator.generate_vectors_for_table(job)
                
                results[table_name] = {
                    "total_records": progress.total_records,
                    "successful_records": progress.successful_records,
                    "failed_records": progress.failed_records,
                    "processing_time": progress.estimated_completion - progress.start_time,
                    "provider_used": progress.current_provider,
                    "errors": progress.errors
                }
                
                logger.info(f"Completed backfill for {table_name}: "
                           f"{progress.successful_records}/{progress.total_records} successful")
            
            return {
                "success": True,
                "client_id": client_id,
                "tables_processed": len(results),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Backfill failed for client {client_id}: {e}")
            return {
                "success": False,
                "client_id": client_id,
                "error": str(e)
            }
    
    async def _create_backfill_plan(self, client_id: int, 
                                  priority_tables: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Create intelligent backfill plan based on data analysis"""
        backfill_plan = []
        
        # Determine table priority
        tables_to_process = priority_tables if priority_tables else self.backfill_tables
        
        for table_name in tables_to_process:
            # Get record count and sample data
            record_info = await self._analyze_table_data(client_id, table_name)
            
            if record_info["record_count"] == 0:
                continue
            
            # Determine optimal settings based on data size
            if record_info["record_count"] > 50000:
                # Large table: use fast local models
                provider_preference = "fast"
                batch_size = 200
            elif record_info["record_count"] > 10000:
                # Medium table: balanced approach
                provider_preference = "balanced"
                batch_size = 150
            else:
                # Small table: prioritize quality
                provider_preference = "quality"
                batch_size = 100
            
            table_plan = {
                "table_name": table_name,
                "records": record_info["records"],
                "record_count": record_info["record_count"],
                "provider_preference": provider_preference,
                "batch_size": batch_size,
                "priority": self._get_table_priority(table_name)
            }
            
            backfill_plan.append(table_plan)
        
        # Sort by priority (high priority first)
        backfill_plan.sort(key=lambda x: x["priority"], reverse=True)
        
        return backfill_plan
    
    async def _analyze_table_data(self, client_id: int, table_name: str) -> Dict[str, Any]:
        """Analyze table data for backfill planning"""
        try:
            # Get record count
            count_query = f"SELECT COUNT(*) FROM {table_name} WHERE client_id = :client_id"
            count_result = await self.db_session.execute(count_query, {"client_id": client_id})
            record_count = count_result.scalar()
            
            if record_count == 0:
                return {"record_count": 0, "records": []}
            
            # Get all records for processing
            # Note: In production, you might want to implement pagination for very large tables
            records_query = f"""
                SELECT * FROM {table_name} 
                WHERE client_id = :client_id 
                AND active = true
                ORDER BY created_at DESC
            """
            records_result = await self.db_session.execute(records_query, {"client_id": client_id})
            records = [dict(row) for row in records_result.fetchall()]
            
            return {
                "record_count": record_count,
                "records": records
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze table {table_name}: {e}")
            return {"record_count": 0, "records": []}
    
    def _get_table_priority(self, table_name: str) -> int:
        """Get priority for table backfill (higher number = higher priority)"""
        priority_map = {
            # High priority: core business data
            "issues": 10,
            "pull_requests": 10,
            "projects": 9,
            "repositories": 9,
            
            # Medium priority: supporting data
            "pull_request_comments": 7,
            "pull_request_reviews": 7,
            "users": 6,
            "issue_changelogs": 6,
            
            # Lower priority: configuration and metadata
            "statuses": 4,
            "issuetypes": 4,
            "workflows": 3,
            "system_settings": 2,
            
            # Lowest priority: reference data
            "dora_market_benchmarks": 1,
            "dora_metric_insights": 1
        }
        
        return priority_map.get(table_name, 5)  # Default medium priority
```

## 📋 Implementation Tasks

### **Task 3-5.1: High-Performance Vector Generation**
- [ ] Create HighPerformanceVectorGenerator with batching and concurrency
- [ ] Implement intelligent provider selection
- [ ] Add progress tracking and monitoring
- [ ] Create error handling and retry mechanisms

### **Task 3-5.2: Intelligent Backfill Manager**
- [ ] Create IntelligentBackfillManager
- [ ] Implement data analysis for backfill planning
- [ ] Add table prioritization logic
- [ ] Create backfill execution workflow

### **Task 3-5.3: Progress Monitoring UI**
- [ ] Create real-time progress dashboard
- [ ] Add backfill status indicators
- [ ] Implement progress charts and metrics
- [ ] Create error reporting interface

### **Task 3-5.4: Performance Optimization**
- [ ] Optimize batch sizes for different providers
- [ ] Implement concurrent processing with semaphores
- [ ] Add memory management for large datasets
- [ ] Create performance benchmarking tools

## ✅ Success Criteria

1. **Performance**: 10x faster vector generation than hackathon approach
2. **Scale**: Successfully process 1M+ records without performance degradation
3. **Intelligence**: Automatic provider selection based on data size and requirements
4. **Monitoring**: Real-time progress tracking for all operations
5. **Reliability**: Robust error handling and recovery mechanisms
6. **Client Isolation**: Perfect separation of vector data by client

## 🔄 Completion Enables

- **Phase 3-6**: AI agent foundation with populated vectors
- **Phase 3-7**: Testing and validation of complete AI system
- **Phase 4**: ML integration with vector-enabled data
