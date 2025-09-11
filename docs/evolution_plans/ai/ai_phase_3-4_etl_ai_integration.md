# Phase 3-4: ETL AI Integration & Optimized LangGraph (Hybrid Provider Integration)

**Implemented**: NO ❌
**Duration**: 2 days (Days 6-7 of 10)
**Priority**: HIGH
**Dependencies**: Phase 3-3 completion

> **🏗️ Architecture Update (September 2025)**: This phase has been updated to reflect the new architecture where AI operations are centralized in Backend Service. ETL Service now calls Backend Service for AI operations instead of having its own AI components.

## 💼 Business Outcome

**Intelligent Data Processing**: Transform ETL operations from basic data extraction to AI-powered insights generation, enabling automatic pattern recognition, anomaly detection, and predictive analytics that reduce manual data analysis time by 80% and improve decision-making speed.


## 📊 Expected Performance Improvements

### **Vector Search Performance:**
- **Current (pgvector)**: 500-2000ms for 1M+ records
- **New (Qdrant)**: 50-200ms for 10M+ records
- **Improvement**: **10-40x faster**

### **Query Processing Performance:**
- **Simple queries**: 200-500ms (cached/direct routing)
- **Complex queries**: 1-3 seconds (parallel processing)
- **Cache hit ratio**: 70-80% for repeated queries
- **Concurrent requests**: 10x improvement with proper caching

### **Cost Optimization:**
- **Local models**: Zero cost for embeddings (Sentence Transformers)
- **WEX Gateway**: Cost-effective for complex analysis
- **Smart routing**: Automatic selection based on task complexity

### **Scalability:**
- **Current capacity**: 1M records with performance degradation
- **New capacity**: 10M+ records with consistent performance
- **Tenant isolation**: Perfect separation using existing integration table
- **Resource usage**: Vector operations don't impact business database

## 🎯 Phase 3-4 Objectives (Updated Architecture)

1. **ETL-Backend AI Integration**: Connect ETL service with Backend Service AI operations
2. **Real-time Vectorization**: Generate embeddings during data extraction via Backend Service
3. **Intelligent Caching**: Multi-level caching for 10x performance improvement
4. **Smart Provider Routing**: Backend Service handles automatic selection between WEX Gateway and local models
5. **Background Processing**: Async AI operations for better user experience
6. **Clean Service Boundaries**: ETL focuses on data processing, Backend handles AI operations

## ⚡ Optimized LangGraph Implementation (Hybrid Provider Integration)

### **Enhanced Strategic Agent with Hybrid Providers**
```python
# services/etl-service/app/ai/optimized_strategic_agent.py
from langgraph.graph import StateGraph
from cachetools import TTLCache
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
import hashlib
import logging
from typing import Dict, List, Any, Optional
from ..ai.hybrid_provider_manager import HybridProviderManager

logger = logging.getLogger(__name__)

class OptimizedStrategicAgent:
    """High-performance strategic agent with hybrid provider support"""

    def __init__(self, db_session, qdrant_client):
        # Use HybridProviderManager instead of direct provider manager
        self.hybrid_provider_manager = HybridProviderManager(db_session)
        self.qdrant_client = qdrant_client
        self.workflow = self._create_optimized_workflow()

        # Multi-level caching for performance
        self.query_cache = TTLCache(maxsize=5000, ttl=3600)      # 1-hour query cache
        self.schema_cache = TTLCache(maxsize=1000, ttl=7200)     # 2-hour schema cache
        self.embedding_cache = TTLCache(maxsize=10000, ttl=86400) # 24-hour embedding cache

        # Parallel processing
        self.parallel_executor = ThreadPoolExecutor(max_workers=4)

        # Performance monitoring
        self.performance_metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_response_time": 0,
            "parallel_operations": 0,
            "simple_queries": 0,
            "complex_queries": 0
        }
    
    def _create_optimized_workflow(self) -> StateGraph:
        """Create performance-optimized workflow with intelligent routing"""
        workflow = StateGraph(StrategicAgentState)
        
        # Entry point with intelligent routing
        workflow.add_node("smart_entry", self._smart_entry_point)
        
        # Fast paths for different query types
        workflow.add_node("cached_response", self._return_cached_response)
        workflow.add_node("simple_sql_generation", self._simple_sql_generation)
        
        # Parallel processing nodes for complex queries
        workflow.add_node("parallel_validation", self._parallel_validation)
        workflow.add_node("parallel_retrieval", self._parallel_retrieval)
        workflow.add_node("optimized_generation", self._optimized_generation)
        
        # Smart routing based on query complexity and cache status
        workflow.set_entry_point("smart_entry")
        workflow.add_conditional_edges(
            "smart_entry",
            self._intelligent_routing,
            {
                "cached": "cached_response",           # Fastest path: return cached result
                "simple": "simple_sql_generation",     # Fast path: direct SQL generation
                "complex": "parallel_validation"       # Full pipeline: parallel processing
            }
        )
        
        # Parallel processing flow for complex queries
        workflow.add_edge("parallel_validation", "parallel_retrieval")
        workflow.add_edge("parallel_retrieval", "optimized_generation")
        
        return workflow
    
    async def _smart_entry_point(self, state: StrategicAgentState) -> StrategicAgentState:
        """Intelligent entry point with performance tracking"""
        start_time = time.time()
        
        # Add performance tracking to state
        state["start_time"] = start_time
        state["client_id"] = state.get("client_id")
        state["user_query"] = state.get("user_query", "")
        
        # Generate cache key
        cache_content = f"{state['client_id']}:{state['user_query']}"
        state["query_hash"] = hashlib.md5(cache_content.encode()).hexdigest()
        
        logger.info(f"Processing query for client {state['client_id']}: {state['user_query'][:100]}...")
        
        return state
    
    def _intelligent_routing(self, state: StrategicAgentState) -> str:
        """Smart routing based on cache and complexity (WrenAI-inspired)"""
        query_hash = state.get("query_hash")
        
        # Check cache first (fastest path - 50-100ms)
        if query_hash in self.query_cache:
            state["cached_result"] = self.query_cache[query_hash]
            self.performance_metrics["cache_hits"] += 1
            logger.info(f"Cache hit for query: {query_hash[:8]}")
            return "cached"
        
        self.performance_metrics["cache_misses"] += 1
        
        # Analyze query complexity
        complexity_score = self._analyze_query_complexity(state.get("user_query", ""))
        
        if complexity_score < 0.3:
            self.performance_metrics["simple_queries"] += 1
            logger.info(f"Simple query detected (score: {complexity_score:.2f})")
            return "simple"    # Direct generation (200-500ms)
        else:
            self.performance_metrics["complex_queries"] += 1
            logger.info(f"Complex query detected (score: {complexity_score:.2f})")
            return "complex"   # Full validation pipeline (1-3 seconds)
    
    def _analyze_query_complexity(self, query: str) -> float:
        """Score query complexity (0.0 = simple, 1.0 = very complex)"""
        if not query:
            return 0.0
        
        query_lower = query.lower()
        
        complexity_indicators = [
            len(query.split()) > 20,                    # Long queries
            "join" in query_lower,                      # Joins
            "subquery" in query_lower,                  # Subqueries  
            len(re.findall(r'\band\b|\bor\b', query_lower)) > 2,  # Multiple conditions
            "aggregate" in query_lower or "sum" in query_lower or "count" in query_lower,  # Aggregations
            "time" in query_lower or "date" in query_lower,     # Time-based queries
            "compare" in query_lower or "vs" in query_lower,    # Comparison queries
            "trend" in query_lower or "over time" in query_lower,  # Trend analysis
        ]
        
        return sum(complexity_indicators) / len(complexity_indicators)
    
    async def _return_cached_response(self, state: StrategicAgentState) -> StrategicAgentState:
        """Return cached response (fastest path)"""
        cached_result = state.get("cached_result")
        
        state["final_response"] = cached_result
        state["response_source"] = "cache"
        state["processing_time"] = time.time() - state["start_time"]
        
        logger.info(f"Returned cached response in {state['processing_time']:.3f}s")
        
        return state
    
    async def _simple_sql_generation(self, state: StrategicAgentState) -> StrategicAgentState:
        """Fast path for simple queries (skip validation)"""
        try:
            # Get embedding for semantic search
            embedding = await self._get_or_generate_embedding(
                state["user_query"], 
                state["client_id"]
            )
            
            # Quick schema retrieval
            schema_context = await self._get_cached_schema_context(state["client_id"])
            
            # Direct SQL generation without validation
            sql_result = await self._generate_sql_direct(
                state["user_query"],
                schema_context,
                embedding
            )
            
            state["sql_query"] = sql_result["sql"]
            state["final_response"] = sql_result
            state["response_source"] = "simple_generation"
            state["processing_time"] = time.time() - state["start_time"]
            
            # Cache the result
            self.query_cache[state["query_hash"]] = sql_result
            
            logger.info(f"Simple SQL generated in {state['processing_time']:.3f}s")
            
        except Exception as e:
            logger.error(f"Simple SQL generation failed: {e}")
            # Fallback to complex pipeline
            return await self._parallel_validation(state)
        
        return state
    
    async def _parallel_validation(self, state: StrategicAgentState) -> StrategicAgentState:
        """Run multiple validations in parallel (WrenAI approach)"""
        self.performance_metrics["parallel_operations"] += 1
        
        logger.info("Starting parallel validation")
        
        # Run validations concurrently for performance
        validation_tasks = [
            self._validate_sql_syntax(state),
            self._validate_sql_semantics(state),
            self._validate_business_context(state)
        ]
        
        try:
            results = await asyncio.gather(*validation_tasks, return_exceptions=True)
            
            state["syntax_validation"] = results[0] if not isinstance(results[0], Exception) else {"valid": False, "error": str(results[0])}
            state["semantic_validation"] = results[1] if not isinstance(results[1], Exception) else {"valid": False, "error": str(results[1])}
            state["business_validation"] = results[2] if not isinstance(results[2], Exception) else {"valid": False, "error": str(results[2])}
            
            logger.info("Parallel validation completed")
            
        except Exception as e:
            logger.error(f"Parallel validation failed: {e}")
            state["validation_error"] = str(e)
        
        return state
    
    async def _parallel_retrieval(self, state: StrategicAgentState) -> StrategicAgentState:
        """Retrieve context information in parallel"""
        client_id = state.get("client_id")
        user_query = state.get("user_query", "")
        
        logger.info("Starting parallel retrieval")
        
        # Run retrievals concurrently for performance
        retrieval_tasks = [
            self._retrieve_schema_context(client_id),
            self._retrieve_similar_queries(user_query, client_id),
            self._retrieve_business_rules(client_id),
            self._get_or_generate_embedding(user_query, client_id)
        ]
        
        try:
            results = await asyncio.gather(*retrieval_tasks, return_exceptions=True)
            
            state["schema_context"] = results[0] if not isinstance(results[0], Exception) else {}
            state["similar_queries"] = results[1] if not isinstance(results[1], Exception) else []
            state["business_rules"] = results[2] if not isinstance(results[2], Exception) else {}
            state["query_embedding"] = results[3] if not isinstance(results[3], Exception) else []
            
            logger.info("Parallel retrieval completed")
            
        except Exception as e:
            logger.error(f"Parallel retrieval failed: {e}")
            state["retrieval_error"] = str(e)
        
        return state
    
    async def _optimized_generation(self, state: StrategicAgentState) -> StrategicAgentState:
        """Optimized SQL generation with all context"""
        try:
            # Generate SQL with full context
            sql_result = await self._generate_sql_with_context(
                state["user_query"],
                state.get("schema_context", {}),
                state.get("similar_queries", []),
                state.get("business_rules", {}),
                state.get("query_embedding", [])
            )
            
            state["sql_query"] = sql_result["sql"]
            state["final_response"] = sql_result
            state["response_source"] = "complex_generation"
            state["processing_time"] = time.time() - state["start_time"]
            
            # Cache the result for future use
            self.query_cache[state["query_hash"]] = sql_result
            
            logger.info(f"Complex SQL generated in {state['processing_time']:.3f}s")
            
        except Exception as e:
            logger.error(f"Optimized generation failed: {e}")
            state["generation_error"] = str(e)
            state["final_response"] = {"error": "SQL generation failed", "details": str(e)}
        
        return state
    
    async def _get_or_generate_embedding(self, text: str, client_id: int) -> List[float]:
        """Get embedding with caching for performance"""
        cache_key = f"{client_id}:{hashlib.md5(text.encode()).hexdigest()}"
        
        if cache_key in self.embedding_cache:
            return self.embedding_cache[cache_key]
        
        try:
            # Get configured embedding provider for client
            provider = await self.ai_provider_manager.get_embedding_provider(client_id)
            embedding = await provider.generate_embeddings([text])
            
            if embedding and len(embedding) > 0:
                self.embedding_cache[cache_key] = embedding[0]
                return embedding[0]
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
        
        return []
    
    async def _get_cached_schema_context(self, client_id: int) -> Dict[str, Any]:
        """Get schema context with caching"""
        cache_key = f"schema_{client_id}"
        
        if cache_key in self.schema_cache:
            return self.schema_cache[cache_key]
        
        try:
            # Retrieve schema context from database
            schema_context = await self._retrieve_schema_context(client_id)
            self.schema_cache[cache_key] = schema_context
            return schema_context
            
        except Exception as e:
            logger.error(f"Schema context retrieval failed: {e}")
            return {}
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        total_queries = self.performance_metrics["cache_hits"] + self.performance_metrics["cache_misses"]
        cache_hit_rate = (self.performance_metrics["cache_hits"] / total_queries * 100) if total_queries > 0 else 0
        
        return {
            **self.performance_metrics,
            "cache_hit_rate": cache_hit_rate,
            "total_queries": total_queries
        }
```

### **ETL AI Service Integration**
```python
# services/etl-service/app/ai/ai_service_manager.py
from typing import Dict, List, Any, Optional
import asyncio
import logging
from .optimized_strategic_agent import OptimizedStrategicAgent
from .ai_provider_manager import AIProviderManager
from .qdrant_client import PulseQdrantClient

logger = logging.getLogger(__name__)

class ETLAIServiceManager:
    """Main AI service manager for ETL operations"""
    
    def __init__(self):
        self.ai_provider_manager = AIProviderManager()
        self.qdrant_client = PulseQdrantClient()
        self.strategic_agent = OptimizedStrategicAgent(
            self.ai_provider_manager,
            self.qdrant_client
        )
        
        # Background task queue for async operations
        self.background_tasks = asyncio.Queue()
        self.is_processing = False
    
    async def initialize(self):
        """Initialize AI service components"""
        try:
            await self.ai_provider_manager.initialize()
            await self.qdrant_client.initialize()
            
            # Start background task processor
            asyncio.create_task(self._process_background_tasks())
            
            logger.info("ETL AI Service Manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI service manager: {e}")
            raise
    
    async def process_user_query(self, user_query: str, client_id: int) -> Dict[str, Any]:
        """Process user query with optimized strategic agent"""
        try:
            # Create initial state
            initial_state = {
                "user_query": user_query,
                "client_id": client_id,
                "timestamp": time.time()
            }
            
            # Process with optimized workflow
            result = await self.strategic_agent.workflow.ainvoke(initial_state)
            
            # Extract final response
            final_response = result.get("final_response", {})
            processing_time = result.get("processing_time", 0)
            response_source = result.get("response_source", "unknown")
            
            logger.info(f"Query processed in {processing_time:.3f}s via {response_source}")
            
            return {
                "success": True,
                "response": final_response,
                "processing_time": processing_time,
                "source": response_source,
                "client_id": client_id
            }
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "client_id": client_id
            }
    
    async def generate_embeddings_batch(self, texts: List[str], client_id: int) -> List[List[float]]:
        """Generate embeddings in batch for performance"""
        try:
            provider = await self.ai_provider_manager.get_embedding_provider(client_id)
            embeddings = await provider.generate_embeddings(texts)
            
            logger.info(f"Generated {len(embeddings)} embeddings for client {client_id}")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            return []
    
    async def store_vectors_batch(self, client_id: int, table_name: str, 
                                 records: List[Dict[str, Any]]) -> bool:
        """Store vectors in Qdrant with batch processing"""
        try:
            # Ensure collection exists
            await self.qdrant_client.create_collection(client_id, table_name)
            
            # Batch upsert for performance
            point_ids = await self.qdrant_client.upsert_vectors_batch(
                client_id, table_name, records
            )
            
            logger.info(f"Stored {len(point_ids)} vectors for client {client_id}, table {table_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Batch vector storage failed: {e}")
            return False
    
    async def search_similar_content(self, query: str, client_id: int, 
                                   table_name: str, limit: int = 10) -> List[Dict]:
        """Search for similar content using Qdrant"""
        try:
            # Generate query embedding
            query_embedding = await self.strategic_agent._get_or_generate_embedding(query, client_id)
            
            if not query_embedding:
                return []
            
            # Search similar vectors
            results = await self.qdrant_client.search_similar(
                client_id, table_name, query_embedding, limit
            )
            
            logger.info(f"Found {len(results)} similar items for query")
            
            return results
            
        except Exception as e:
            logger.error(f"Similar content search failed: {e}")
            return []
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics"""
        agent_metrics = self.strategic_agent.get_performance_metrics()
        provider_metrics = self.ai_provider_manager.get_performance_metrics()
        
        return {
            "agent_metrics": agent_metrics,
            "provider_metrics": provider_metrics,
            "background_queue_size": self.background_tasks.qsize()
        }
    
    async def _process_background_tasks(self):
        """Process background AI tasks"""
        self.is_processing = True
        
        while self.is_processing:
            try:
                # Get task from queue with timeout
                task = await asyncio.wait_for(self.background_tasks.get(), timeout=1.0)
                
                # Process the task
                await self._execute_background_task(task)
                
            except asyncio.TimeoutError:
                # No tasks in queue, continue
                continue
            except Exception as e:
                logger.error(f"Background task processing failed: {e}")
```

## 📋 Implementation Tasks

### **Task 3-4.1: Enhanced Strategic Agent with Hybrid Providers**
- [ ] Update OptimizedStrategicAgent to use HybridProviderManager
- [ ] Implement intelligent routing between WEX Gateway and local models
- [ ] Add cost tracking and optimization logic
- [ ] Create smart query complexity analysis

### **Task 3-4.2: ETL Hybrid AI Integration**
- [ ] Create ETLAIServiceManager with hybrid provider support
- [ ] Implement batch processing using both WEX Gateway and local models
- [ ] Add background task processing with cost optimization
- [ ] Integrate with existing ETL workflows and integration table

### **Task 3-4.3: Performance and Cost Optimization**
- [ ] Implement multi-level caching system
- [ ] Add parallel processing for validations
- [ ] Create smart routing based on cost and performance
- [ ] Optimize embedding generation using local models for bulk operations

### **Task 3-4.4: Integration Table Enhancement**
- [ ] Create AI query processing endpoints
- [ ] Add performance metrics endpoints
- [ ] Implement batch operation endpoints
- [ ] Add health check and monitoring endpoints

## ✅ Success Criteria

1. **Performance**: 10x improvement in query processing speed
2. **Intelligent Routing**: Automatic optimization based on query complexity
3. **Caching**: 70-80% cache hit rate for repeated queries
4. **Parallel Processing**: Concurrent validations and retrievals
5. **Background Processing**: Non-blocking AI operations
6. **Monitoring**: Comprehensive performance metrics

## 🔄 Completion Enables

- **Phase 3-5**: High-performance vector generation and backfill
- **Phase 3-6**: AI agent foundation with optimized processing
- **Phase 3-7**: Testing and validation of complete AI system
