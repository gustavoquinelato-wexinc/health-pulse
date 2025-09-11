# Phase 3-4: ETL AI Integration (Backend Service Integration)

**Implemented**: YES ✅
**Duration**: 2 days (Days 6-7 of 10)
**Priority**: HIGH
**Dependencies**: Phase 3-3 completion

> **🏗️ Architecture Update (September 2025)**: This phase focuses on completing the ETL-Backend AI integration. Backend Service already has all AI infrastructure (HybridProviderManager, Qdrant, providers). ETL Service will call Backend Service for AI operations.

## 💼 Business Outcome

**Real-time AI-Powered Data Processing**: Transform ETL operations from simple data extraction to intelligent data processing with real-time vectorization, enabling instant semantic search and AI-powered analytics that reduce information discovery time from hours to seconds.


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

## 🎯 Phase 3-4 Objectives (Simplified Architecture)

1. **Complete Backend AI Endpoints**: Add missing vector storage and search endpoints to Backend Service
2. **ETL AI Integration**: Update ETL Service to call Backend Service for AI operations
3. **Real-time Vectorization**: Generate embeddings during data extraction via Backend Service
4. **Vector Storage**: Store embeddings in Qdrant via Backend Service
5. **Bridge Table Management**: Create QdrantVector records for PostgreSQL-Qdrant linking
6. **ETL Job Integration**: Add AI operations to existing Jira and GitHub extraction jobs

## 🔗 Backend Service AI Integration Architecture

### **Current State Analysis**
✅ **Already Implemented in Backend Service**:
- `HybridProviderManager` - Intelligent routing between WEX Gateway and local models
- `PulseQdrantClient` - High-performance vector operations with tenant isolation
- `WEXGatewayProvider` & `SentenceTransformersProvider` - AI provider implementations
- `/api/v1/ai/embeddings` - Embedding generation endpoint
- AI usage tracking and performance monitoring

❌ **Missing Components**:
- Vector storage endpoint for ETL Service
- Vector search endpoint for Frontend Service
- QdrantVector bridge table management
- ETL job AI integration

### **Required Backend Service Endpoints**
```python
# services/backend-service/app/api/ai_config_routes.py (NEW ENDPOINTS)

# NEW: Vector storage endpoint for ETL Service
@router.post("/ai/vectors/store")
async def store_vectors(
    request: dict,
    user: UserData = Depends(require_authentication)
):
    """Store vectors in Qdrant with metadata linking for ETL Service"""
    try:
        # Extract request data
        table_name = request.get("table_name")
        record_id = request.get("record_id")
        content = request.get("content")
        vector_type = request.get("vector_type", "content")
        tenant_id = user.tenant_id

        if not all([table_name, record_id, content]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        # Import AI components
        from app.ai.hybrid_provider_manager import HybridProviderManager
        from app.ai.qdrant_client import PulseQdrantClient
        from app.models.unified_models import QdrantVector

        db_session = get_db_session()

        try:
            # 1. Generate embeddings using existing hybrid provider
            hybrid_manager = HybridProviderManager(db_session)
            embedding_result = await hybrid_manager.generate_embeddings([content])

            if not embedding_result.success:
                return {"success": False, "error": embedding_result.error}

            # 2. Store in Qdrant
            qdrant_client = PulseQdrantClient()
            await qdrant_client.initialize()

            collection_name = f"client_{tenant_id}_{table_name}"

            # Create collection if it doesn't exist
            await qdrant_client.create_collection(collection_name)

            # Prepare payload with metadata
            payload = {
                "tenant_id": tenant_id,
                "table_name": table_name,
                "record_id": record_id,
                "vector_type": vector_type,
                "content_preview": content[:500]  # Store preview for debugging
            }

            # Store vector in Qdrant
            result = await qdrant_client.upsert_vectors(
                collection_name=collection_name,
                vectors=embedding_result.data,
                payloads=[payload]
            )

            if not result.success:
                return {"success": False, "error": result.error}

            # 3. Create bridge record in PostgreSQL
            qdrant_vector = QdrantVector(
                tenant_id=tenant_id,
                table_name=table_name,
                record_id=record_id,
                qdrant_collection=collection_name,
                qdrant_point_id=result.point_ids[0],  # Get the generated point ID
                vector_type=vector_type,
                embedding_model=embedding_result.model_used,
                embedding_provider=embedding_result.provider_used
            )

            db_session.add(qdrant_vector)
            db_session.commit()

            return {
                "success": True,
                "qdrant_point_id": result.point_ids[0],
                "provider_used": embedding_result.provider_used,
                "processing_time": embedding_result.processing_time,
                "cost": embedding_result.cost
            }

        finally:
            db_session.close()

    except Exception as e:
        logger.error(f"Error storing vectors: {e}")
        raise HTTPException(status_code=500, detail="Failed to store vectors")

# NEW: Vector search endpoint for Frontend Service
@router.post("/ai/vectors/search")
async def search_vectors(
    request: dict,
    user: UserData = Depends(require_authentication)
):
    """Search vectors in Qdrant for semantic similarity"""
    try:
        query_text = request.get("query_text")
        table_name = request.get("table_name")
        limit = request.get("limit", 10)
        tenant_id = user.tenant_id

        if not all([query_text, table_name]):
            raise HTTPException(status_code=400, detail="Missing query_text or table_name")

        # Import AI components
        from app.ai.hybrid_provider_manager import HybridProviderManager
        from app.ai.qdrant_client import PulseQdrantClient

        db_session = get_db_session()

        try:
            # 1. Generate query embedding
            hybrid_manager = HybridProviderManager(db_session)
            embedding_result = await hybrid_manager.generate_embeddings([query_text])

            if not embedding_result.success:
                return {"success": False, "error": embedding_result.error}

            # 2. Search in Qdrant
            qdrant_client = PulseQdrantClient()
            await qdrant_client.initialize()

            collection_name = f"client_{tenant_id}_{table_name}"

            search_results = await qdrant_client.search_vectors(
                collection_name=collection_name,
                query_vector=embedding_result.data[0],
                limit=limit,
                filter_conditions={"tenant_id": tenant_id}
            )

            # 3. Format results
            results = []
            for result in search_results:
                results.append({
                    "record_id": result.payload.get("record_id"),
                    "score": result.score,
                    "content_preview": result.payload.get("content_preview"),
                    "vector_type": result.payload.get("vector_type")
                })

            return {
                "success": True,
                "results": results,
                "query_embedding_provider": embedding_result.provider_used,
                "processing_time": embedding_result.processing_time
            }

        finally:
            db_session.close()

    except Exception as e:
        logger.error(f"Error searching vectors: {e}")
        raise HTTPException(status_code=500, detail="Failed to search vectors")
```

### **ETL Service AI Client Enhancement**
```python
# services/etl-service/app/clients/ai_client.py (ENHANCED)

class AIClient:
    """Enhanced AI Client for calling Backend Service AI endpoints"""

    def __init__(self):
        self.backend_url = getattr(settings, 'BACKEND_SERVICE_URL', 'http://localhost:3001')
        self.timeout = 30.0

    async def store_entity_vector(self, table_name: str, record_id: int,
                                 content: str, tenant_id: int,
                                 vector_type: str = "content") -> dict:
        """Store entity vector in Qdrant via Backend Service"""
        try:
            headers = {"Content-Type": "application/json"}

            payload = {
                "table_name": table_name,
                "record_id": record_id,
                "content": content,
                "vector_type": vector_type
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.backend_url}/api/v1/ai/vectors/store",
                    json=payload,
                    headers=headers
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Vector storage failed: {response.status_code} - {response.text}")
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"Failed to store entity vector: {e}")
            return {"success": False, "error": str(e)}

    async def search_similar_entities(self, query_text: str, table_name: str,
                                    limit: int = 10) -> dict:
        """Search for similar entities using semantic search"""
        try:
            headers = {"Content-Type": "application/json"}

            payload = {
                "query_text": query_text,
                "table_name": table_name,
                "limit": limit
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.backend_url}/api/v1/ai/vectors/search",
                    json=payload,
                    headers=headers
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Vector search failed: {response.status_code} - {response.text}")
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"Failed to search vectors: {e}")
            return {"success": False, "error": str(e)}

# Enhanced convenience functions for ETL jobs
async def store_work_item_vector(work_item_data: dict, tenant_id: int) -> bool:
    """Store work item vector during ETL processing"""
    client = get_ai_client()

    # Combine title and description for vectorization
    content = f"{work_item_data.get('summary', '')} {work_item_data.get('description', '')}"

    result = await client.store_entity_vector(
        table_name="work_items",
        record_id=work_item_data['id'],
        content=content,
        tenant_id=tenant_id,
        vector_type="content"
    )

    if result.get("success"):
        logger.info(f"Stored vector for work item {work_item_data['id']} using {result.get('provider_used')}")
        return True
    else:
        logger.error(f"Failed to store vector for work item {work_item_data['id']}: {result.get('error')}")
        return False

async def store_pull_request_vector(pr_data: dict, tenant_id: int) -> bool:
    """Store pull request vector during ETL processing"""
    client = get_ai_client()

    # Combine title and description for vectorization
    content = f"{pr_data.get('title', '')} {pr_data.get('body', '')}"

    result = await client.store_entity_vector(
        table_name="pull_requests",
        record_id=pr_data['id'],
        content=content,
        tenant_id=tenant_id,
        vector_type="content"
    )

    if result.get("success"):
        logger.info(f"Stored vector for PR {pr_data['id']} using {result.get('provider_used')}")
        return True
    else:
        logger.error(f"Failed to store vector for PR {pr_data['id']}: {result.get('error')}")
        return False
```

### **ETL Job Integration Examples**
```python
# services/etl-service/app/jobs/jira_job.py (ENHANCED)

from app.clients.ai_client import store_work_item_vector

async def process_jira_issues(integration_config: dict, tenant_id: int):
    """Enhanced Jira job with AI vectorization"""
    try:
        # 1. Extract issues from Jira (existing logic)
        issues = await extract_jira_issues(integration_config)

        # 2. Store in PostgreSQL (existing logic)
        stored_issues = []
        for issue_data in issues:
            issue_id = await store_issue_in_postgres(issue_data, tenant_id)
            issue_data['id'] = issue_id
            stored_issues.append(issue_data)

        # 3. NEW: Store vectors in Qdrant via Backend Service
        vectorization_results = []
        for issue_data in stored_issues:
            try:
                success = await store_work_item_vector(issue_data, tenant_id)
                vectorization_results.append({
                    "issue_id": issue_data['id'],
                    "vectorized": success
                })
            except Exception as e:
                logger.error(f"Failed to vectorize issue {issue_data['id']}: {e}")
                vectorization_results.append({
                    "issue_id": issue_data['id'],
                    "vectorized": False,
                    "error": str(e)
                })

        # 4. Log results
        successful_vectors = sum(1 for r in vectorization_results if r['vectorized'])
        logger.info(f"Jira job completed: {len(stored_issues)} issues stored, "
                   f"{successful_vectors} vectors created")

        return {
            "success": True,
            "issues_processed": len(stored_issues),
            "vectors_created": successful_vectors,
            "vectorization_results": vectorization_results
        }

    except Exception as e:
        logger.error(f"Jira job failed: {e}")
        return {"success": False, "error": str(e)}

# services/etl-service/app/jobs/github_job.py (ENHANCED)

from app.clients.ai_client import store_pull_request_vector

async def process_github_pull_requests(integration_config: dict, tenant_id: int):
    """Enhanced GitHub job with AI vectorization"""
    try:
        # 1. Extract PRs from GitHub (existing logic)
        pull_requests = await extract_github_prs(integration_config)

        # 2. Store in PostgreSQL (existing logic)
        stored_prs = []
        for pr_data in pull_requests:
            pr_id = await store_pr_in_postgres(pr_data, tenant_id)
            pr_data['id'] = pr_id
            stored_prs.append(pr_data)

        # 3. NEW: Store vectors in Qdrant via Backend Service
        vectorization_results = []
        for pr_data in stored_prs:
            try:
                success = await store_pull_request_vector(pr_data, tenant_id)
                vectorization_results.append({
                    "pr_id": pr_data['id'],
                    "vectorized": success
                })
            except Exception as e:
                logger.error(f"Failed to vectorize PR {pr_data['id']}: {e}")
                vectorization_results.append({
                    "pr_id": pr_data['id'],
                    "vectorized": False,
                    "error": str(e)
                })

        # 4. Log results
        successful_vectors = sum(1 for r in vectorization_results if r['vectorized'])
        logger.info(f"GitHub job completed: {len(stored_prs)} PRs stored, "
                   f"{successful_vectors} vectors created")

        return {
            "success": True,
            "prs_processed": len(stored_prs),
            "vectors_created": successful_vectors,
            "vectorization_results": vectorization_results
        }

    except Exception as e:
        logger.error(f"GitHub job failed: {e}")
        return {"success": False, "error": str(e)}
```

### **Data Flow Summary**
```
1. ETL Service extracts data (Jira issues, GitHub PRs)
2. ETL Service stores business data in PostgreSQL
3. ETL Service calls Backend Service: store_entity_vector()
4. Backend Service generates embeddings using HybridProviderManager
5. Backend Service stores vectors in Qdrant with metadata
6. Backend Service creates QdrantVector bridge record in PostgreSQL
7. Frontend Service can search vectors via Backend Service
8. Backend Service combines vector results with PostgreSQL data
```

This approach maintains clean service boundaries:
- **ETL Service**: Data extraction and processing
- **Backend Service**: All AI operations (embeddings, Qdrant, search)
- **Frontend Service**: UI and calls Backend for AI queries

## 🔧 Configuration Requirements

### **Environment Variables**
```env
# Backend Service AI Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_TIMEOUT=120

# Service Communication
BACKEND_SERVICE_URL=http://localhost:3001
ETL_SERVICE_URL=http://localhost:8000
# AI Provider Integration Configuration
WEX_AI_GATEWAY_URL=http://internal-ai-gateway
WEX_AI_GATEWAY_TOKEN=your-gateway-token

# Qdrant Collection Naming
QDRANT_COLLECTION_PREFIX=client_
```

### **Integration Table Configuration**
The existing `integrations` table already supports AI providers:
```sql
-- AI Provider integration example
INSERT INTO integrations (
    tenant_id, provider, type, base_url, ai_model,
    ai_model_config, active
) VALUES (
    123, 'wex_gateway', 'AI', 'http://internal-ai-gateway',
    'bedrock-claude-sonnet-4-v1',
    '{"temperature": 0.1, "max_tokens": 4000}', true
);
```



## 📋 Implementation Tasks

### **Task 3-4.1: Backend Service AI Endpoints**
- [ ] Add `/api/v1/ai/vectors/store` endpoint for ETL Service vector storage
- [ ] Add `/api/v1/ai/vectors/search` endpoint for Frontend Service semantic search
- [ ] Implement QdrantVector bridge table management in endpoints
- [ ] Add proper error handling and validation for vector operations

### **Task 3-4.2: ETL Service AI Client Enhancement**
- [ ] Add `store_entity_vector()` method to AIClient class
- [ ] Add `search_similar_entities()` method to AIClient class
- [ ] Create convenience functions: `store_work_item_vector()`, `store_pull_request_vector()`
- [ ] Add proper error handling and logging for AI operations

### **Task 3-4.3: ETL Job AI Integration**
- [ ] Update Jira job to call `store_work_item_vector()` after storing in PostgreSQL
- [ ] Update GitHub job to call `store_pull_request_vector()` after storing in PostgreSQL
- [ ] Add vectorization result tracking and logging
- [ ] Implement graceful fallback when AI operations fail

### **Task 3-4.4: Testing and Validation**
- [ ] Test complete ETL → Backend → Qdrant flow with real data
- [ ] Validate vector storage and retrieval operations
- [ ] Test semantic search functionality
- [ ] Verify tenant isolation in Qdrant collections

## ✅ Success Criteria

1. **ETL AI Integration**: ETL jobs successfully store vectors in Qdrant via Backend Service
2. **Vector Storage**: QdrantVector bridge records correctly link PostgreSQL and Qdrant data
3. **Semantic Search**: Frontend can search vectors and retrieve related PostgreSQL records
4. **Performance**: Vector operations complete within acceptable timeframes
5. **Error Handling**: Graceful fallback when AI operations fail
6. **Monitoring**: AI usage tracking and performance metrics working

## 🔄 Completion Enables

- **Phase 3-5**: Vector collection management and performance optimization
- **Phase 3-6**: AI query interface using existing Backend Service infrastructure
- **Real-time AI Operations**: ETL jobs generating vectors during data extraction
