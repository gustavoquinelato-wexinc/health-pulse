# AI & VECTORIZATION

**Comprehensive AI Integration & Vector Search System**

This document covers all AI capabilities in the Pulse Platform, including vectorization, embedding models, semantic search, and AI provider integrations.

## 🤖 AI Architecture Overview

### Flexible AI Provider System

Pulse Platform implements a hybrid AI architecture supporting multiple providers and deployment models:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AI Gateway    │    │  Direct Models  │    │  Vector Store   │
│   (Internal)    │    │   (Local/API)   │    │   (Qdrant)      │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • OpenAI GPT    │    │ • Local LLMs    │    │ • Collections   │
│ • Claude        │    │ • Transformers  │    │ • Embeddings    │
│ • Custom Models │    │ • ONNX Models   │    │ • Similarity    │
│ • Rate Limiting │    │ • GPU/CPU       │    │ • Filtering     │
│ • Cost Control  │    │ • Offline Mode  │    │ • Clustering    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### AI Integration Types

#### 1. AI Gateway Integration (Internal Clients)
- **Purpose**: Centralized AI service for internal company use
- **Features**: Rate limiting, cost control, model routing
- **Configuration**: `gateway_route = true`
- **Use Cases**: Frontend AI agents, chat interfaces

#### 2. Direct Model Integration (External Clients)
- **Purpose**: Direct API calls for external clients
- **Features**: Full JSON configuration, model flexibility
- **Configuration**: `gateway_route = false`
- **Use Cases**: ETL processing, embedding generation

## 🔍 Vectorization System

### Multi-Agent Vectorization Architecture

All ETL data tables are vectorized with source_type classification for specialized AI agents:

```
┌─────────────────┐    Embedding    ┌─────────────────┐    Storage    ┌─────────────────┐
│  Source Data    │─────────────────►│  Vector Model   │─────────────►│  Qdrant DB      │
├─────────────────┤                 ├─────────────────┤              ├─────────────────┤
│ • Issues        │                 │ • OpenAI Ada    │              │ • Collections   │
│ • Comments      │                 │ • Local Models  │              │ • Points        │
│ • Pull Requests │                 │ • Transformers  │              │ • Metadata      │
│ • Repositories  │                 │ • Custom Models │              │ • Indexes       │
│ • Work Items    │                 │ • Multi-lang    │              │ • Clusters      │
│ • Status Data   │                 │ • Batch Process │              │ • Similarity    │
└─────────────────┘                 └─────────────────┘              └─────────────────┘
```

### Vectorization Pipeline

#### 1. Data Extraction
```python
# Extract text content from structured data
def extract_vectorizable_content(entity):
    content_parts = []
    
    if hasattr(entity, 'title'):
        content_parts.append(f"Title: {entity.title}")
    if hasattr(entity, 'description'):
        content_parts.append(f"Description: {entity.description}")
    if hasattr(entity, 'comments'):
        content_parts.extend([f"Comment: {c.body}" for c in entity.comments])
    
    return " | ".join(content_parts)
```

#### 2. Embedding Generation
```python
# Generate embeddings using configured provider
async def generate_embedding(text: str, provider_config: dict):
    if provider_config.get('gateway_route'):
        # Use AI Gateway
        return await ai_gateway_client.embed(text, model=provider_config['model'])
    else:
        # Direct model call
        return await direct_model_client.embed(text, **provider_config)
```

#### 3. Vector Storage
```python
# Store vectors in Qdrant with metadata
def store_vector(entity_id: str, vector: List[float], metadata: dict):
    point = {
        "id": entity_id,
        "vector": vector,
        "payload": {
            "entity_type": metadata["type"],
            "tenant_id": metadata["tenant_id"],
            "created_at": metadata["timestamp"],
            "source_table": metadata["table"],
            **metadata["custom_fields"]
        }
    }
    qdrant_client.upsert(collection_name="pulse_vectors", points=[point])
```

### Multi-Agent Architecture

#### Source Type Classification

All vectorized data is classified by source_type for specialized agent access:

```python
SOURCE_TYPE_MAPPING = {
    # Jira Agent's scope
    'work_items': 'JIRA',
    'changelogs': 'JIRA',
    'projects': 'JIRA',
    'statuses': 'JIRA',
    'statuses_mappings': 'JIRA',
    'workflows': 'JIRA',
    'wits': 'JIRA',
    'wits_hierarchies': 'JIRA',
    'wits_mappings': 'JIRA',
    'work_items_prs_links': 'JIRA',  # Jira agent owns cross-system links
    'sprints': 'JIRA',

    # Portfolio Management (Jira-related strategic planning)
    'programs': 'JIRA',
    'portfolios': 'JIRA',
    'risks': 'JIRA',
    'dependencies': 'JIRA',

    # GitHub Agent's scope
    'prs': 'GITHUB',
    'prs_commits': 'GITHUB',
    'prs_reviews': 'GITHUB',
    'prs_comments': 'GITHUB',
    'repositories': 'GITHUB',
}
```

#### Agent Query Patterns

```python
# Jira Agent: Get all Jira vectors
jira_vectors = session.query(QdrantVector).filter(
    QdrantVector.tenant_id == tenant_id,
    QdrantVector.source_type == 'JIRA',
    QdrantVector.active == True
).all()

# GitHub Agent: Get all GitHub vectors
github_vectors = session.query(QdrantVector).filter(
    QdrantVector.tenant_id == tenant_id,
    QdrantVector.source_type == 'GITHUB',
    QdrantVector.active == True
).all()

# Master Agent: Orchestrate across all agents
all_vectors = session.query(QdrantVector).join(Integration).filter(
    QdrantVector.tenant_id == tenant_id,
    QdrantVector.source_type.in_(['JIRA', 'GITHUB']),
    QdrantVector.active == True
).all()
```

#### Bridge Table Schema

The `qdrant_vectors` table provides PostgreSQL ↔ Qdrant mapping:

```sql
CREATE TABLE qdrant_vectors (
    id SERIAL PRIMARY KEY,

    -- Agent scope and source identification
    source_type VARCHAR(50) NOT NULL,           -- 'JIRA', 'GITHUB'
    table_name VARCHAR(50) NOT NULL,            -- 'work_items', 'prs', etc.
    record_id INTEGER NOT NULL,                 -- Internal DB record ID

    -- Qdrant references
    qdrant_collection VARCHAR(100) NOT NULL,    -- 'client_1_jira_work_items'
    qdrant_point_id UUID NOT NULL UNIQUE,       -- UUID for Qdrant point

    -- Vector metadata
    vector_type VARCHAR(50) NOT NULL,           -- 'content', 'summary', 'metadata'

    -- IntegrationBaseEntity fields
    integration_id INTEGER NOT NULL REFERENCES integrations(id),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for multi-agent queries
CREATE INDEX idx_qdrant_vectors_source_type ON qdrant_vectors (tenant_id, source_type);
CREATE UNIQUE INDEX idx_qdrant_vectors_point_id ON qdrant_vectors (qdrant_point_id);
CREATE INDEX idx_qdrant_vectors_active ON qdrant_vectors (tenant_id, active);
```

### Vectorized Data Tables

#### Core ETL Tables
- **Issues**: Title, description, comments, labels
- **Pull Requests**: Title, description, diff content, comments
- **Repositories**: Name, description, README content
- **Work Items**: Title, description, acceptance criteria
- **Comments**: Body text, thread context
- **Status Updates**: Change descriptions, notes

#### Vector Metadata
```json
{
  "entity_id": "issue_123",
  "entity_type": "issue",
  "tenant_id": 1,
  "project_id": 456,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T15:45:00Z",
  "source_table": "issues",
  "integration_type": "jira",
  "custom_fields": {
    "priority": "high",
    "component": "backend",
    "assignee": "john.doe"
  }
}
```

## 🔍 Semantic Search System

### Multi-Modal Search Capabilities

#### 1. Similarity Search
```python
# Find similar content across all data types
async def semantic_search(query: str, tenant_id: int, limit: int = 10):
    query_vector = await generate_embedding(query)
    
    results = qdrant_client.search(
        collection_name="pulse_vectors",
        query_vector=query_vector,
        query_filter={
            "must": [{"key": "tenant_id", "match": {"value": tenant_id}}]
        },
        limit=limit,
        score_threshold=0.7
    )
    
    return [
        {
            "entity_id": hit.id,
            "score": hit.score,
            "entity_type": hit.payload["entity_type"],
            "content": hit.payload.get("content_preview"),
            "metadata": hit.payload
        }
        for hit in results
    ]
```

#### 2. Filtered Search
```python
# Search with entity type and metadata filters
async def filtered_search(query: str, filters: dict, tenant_id: int):
    query_vector = await generate_embedding(query)
    
    filter_conditions = [
        {"key": "tenant_id", "match": {"value": tenant_id}}
    ]
    
    if filters.get("entity_type"):
        filter_conditions.append({
            "key": "entity_type", 
            "match": {"value": filters["entity_type"]}
        })
    
    if filters.get("project_id"):
        filter_conditions.append({
            "key": "project_id", 
            "match": {"value": filters["project_id"]}
        })
    
    return qdrant_client.search(
        collection_name="pulse_vectors",
        query_vector=query_vector,
        query_filter={"must": filter_conditions},
        limit=filters.get("limit", 10)
    )
```

#### 3. Clustering & Analytics
```python
# Discover content clusters and patterns
async def discover_clusters(tenant_id: int, entity_type: str = None):
    # Get vectors for clustering
    vectors = qdrant_client.scroll(
        collection_name="pulse_vectors",
        scroll_filter={
            "must": [
                {"key": "tenant_id", "match": {"value": tenant_id}},
                {"key": "entity_type", "match": {"value": entity_type}}
            ] if entity_type else [
                {"key": "tenant_id", "match": {"value": tenant_id}}
            ]
        },
        limit=1000
    )
    
    # Apply clustering algorithm
    from sklearn.cluster import KMeans
    
    vector_data = [point.vector for point in vectors[0]]
    clusters = KMeans(n_clusters=5).fit(vector_data)
    
    return {
        "clusters": clusters.labels_.tolist(),
        "centroids": clusters.cluster_centers_.tolist(),
        "entities": [point.id for point in vectors[0]]
    }
```

## 🛠️ AI Provider Configuration

### Provider Types

#### 1. OpenAI Integration
```json
{
  "type": "openai",
  "model": "text-embedding-ada-002",
  "api_key": "${OPENAI_API_KEY}",
  "gateway_route": true,
  "cost_tier": "standard",
  "rate_limit": 1000
}
```

#### 2. Local Model Integration
```json
{
  "type": "local",
  "model_path": "/models/sentence-transformers/all-MiniLM-L6-v2",
  "device": "cuda:0",
  "gateway_route": false,
  "batch_size": 32,
  "max_length": 512
}
```

#### 3. Azure OpenAI Integration
```json
{
  "type": "azure_openai",
  "endpoint": "https://your-resource.openai.azure.com/",
  "api_key": "${AZURE_OPENAI_KEY}",
  "deployment_name": "text-embedding-ada-002",
  "api_version": "2023-05-15",
  "gateway_route": true
}
```

### Model Selection Strategy

#### Frontend AI Agents (Gateway Route)
- **Use Case**: Chat interfaces, user queries
- **Provider**: AI Gateway with OpenAI/Claude
- **Configuration**: `gateway_route = true`
- **Benefits**: Rate limiting, cost control, monitoring

#### ETL Processing (Direct Route)
- **Use Case**: Bulk embedding generation
- **Provider**: Local models or direct API
- **Configuration**: `gateway_route = false`
- **Benefits**: Performance, cost efficiency, offline capability

## 📊 AI Performance Monitoring

### Embedding Quality Metrics

#### 1. Similarity Accuracy
```python
# Measure embedding quality through similarity tests
def measure_embedding_quality(test_pairs: List[Tuple[str, str, float]]):
    results = []
    
    for text1, text2, expected_similarity in test_pairs:
        vec1 = generate_embedding(text1)
        vec2 = generate_embedding(text2)
        
        actual_similarity = cosine_similarity(vec1, vec2)
        accuracy = 1 - abs(expected_similarity - actual_similarity)
        
        results.append({
            "text1": text1,
            "text2": text2,
            "expected": expected_similarity,
            "actual": actual_similarity,
            "accuracy": accuracy
        })
    
    return {
        "average_accuracy": sum(r["accuracy"] for r in results) / len(results),
        "results": results
    }
```

#### 2. Search Relevance
```python
# Measure search result relevance
def measure_search_relevance(queries: List[dict]):
    relevance_scores = []
    
    for query_data in queries:
        results = semantic_search(
            query=query_data["query"],
            tenant_id=query_data["tenant_id"]
        )
        
        # Calculate relevance based on expected results
        expected_ids = set(query_data["expected_results"])
        actual_ids = set(r["entity_id"] for r in results[:5])
        
        precision = len(expected_ids & actual_ids) / len(actual_ids)
        recall = len(expected_ids & actual_ids) / len(expected_ids)
        
        relevance_scores.append({
            "query": query_data["query"],
            "precision": precision,
            "recall": recall,
            "f1_score": 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        })
    
    return relevance_scores
```

### Cost & Performance Tracking

#### 1. API Usage Monitoring
```python
# Track AI API usage and costs
class AIUsageTracker:
    def __init__(self):
        self.usage_log = []
    
    def log_request(self, provider: str, model: str, tokens: int, cost: float):
        self.usage_log.append({
            "timestamp": datetime.utcnow(),
            "provider": provider,
            "model": model,
            "tokens": tokens,
            "cost": cost
        })
    
    def get_daily_usage(self, date: datetime) -> dict:
        day_usage = [
            log for log in self.usage_log 
            if log["timestamp"].date() == date.date()
        ]
        
        return {
            "total_requests": len(day_usage),
            "total_tokens": sum(log["tokens"] for log in day_usage),
            "total_cost": sum(log["cost"] for log in day_usage),
            "by_provider": self._group_by_provider(day_usage)
        }
```

#### 2. Performance Benchmarks
```python
# Benchmark embedding generation performance
async def benchmark_embedding_performance():
    test_texts = [
        "Short text for testing",
        "Medium length text with more content for performance testing",
        "Very long text content that includes multiple sentences and paragraphs to test the performance of embedding generation with larger inputs that might be more representative of real-world usage patterns."
    ]
    
    results = {}
    
    for provider in ["openai", "local", "azure"]:
        provider_results = []
        
        for text in test_texts:
            start_time = time.time()
            embedding = await generate_embedding(text, provider_config[provider])
            end_time = time.time()
            
            provider_results.append({
                "text_length": len(text),
                "generation_time": end_time - start_time,
                "embedding_dimension": len(embedding)
            })
        
        results[provider] = {
            "average_time": sum(r["generation_time"] for r in provider_results) / len(provider_results),
            "results": provider_results
        }
    
    return results
```

## 🔧 AI System Administration

### Vector Database Management

#### 1. Collection Management
```python
# Manage Qdrant collections
def create_collection(collection_name: str, vector_size: int):
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "size": vector_size,
            "distance": "Cosine"
        },
        optimizers_config={
            "default_segment_number": 2,
            "max_segment_size": 20000,
            "memmap_threshold": 20000
        }
    )

def optimize_collection(collection_name: str):
    qdrant_client.update_collection(
        collection_name=collection_name,
        optimizer_config={
            "deleted_threshold": 0.2,
            "vacuum_min_vector_number": 1000,
            "default_segment_number": 0,
            "max_segment_size": 20000
        }
    )
```

#### 2. Index Maintenance
```python
# Maintain vector indexes for optimal performance
def rebuild_indexes(collection_name: str):
    # Get collection info
    info = qdrant_client.get_collection(collection_name)
    
    # Recreate with optimized settings
    qdrant_client.update_collection(
        collection_name=collection_name,
        vectors_config={
            "size": info.config.params.vectors.size,
            "distance": info.config.params.vectors.distance,
            "hnsw_config": {
                "m": 16,
                "ef_construct": 100,
                "full_scan_threshold": 10000
            }
        }
    )
```

### AI Model Management

#### 1. Model Deployment
```bash
# Deploy local embedding models
docker run -d \
  --name embedding-service \
  --gpus all \
  -p 8080:8080 \
  -v /models:/models \
  sentence-transformers/all-MiniLM-L6-v2

# Health check
curl http://localhost:8080/health
```

#### 2. Model Updates
```python
# Update AI provider configurations
def update_ai_provider(tenant_id: int, provider_config: dict):
    # Validate configuration
    if not validate_provider_config(provider_config):
        raise ValueError("Invalid provider configuration")
    
    # Test connection
    test_result = test_provider_connection(provider_config)
    if not test_result.success:
        raise ConnectionError(f"Provider test failed: {test_result.error}")
    
    # Update database
    db.query(Integration).filter(
        Integration.tenant_id == tenant_id,
        Integration.type == "ai_provider"
    ).update({"config": provider_config})
    
    # Clear cache
    cache.delete(f"ai_provider:{tenant_id}")
```

---

## 📊 Detailed Vectorization Strategy

### Vectorized Fields by Entity Type

#### Projects
**Database Columns**:
- `id`, `external_id`, `key`, `name`, `project_type`, `integration_id`, `tenant_id`, `active`, `created_at`, `last_updated_at`

**Vectorized Fields**:
```python
{
    "external_id": entity.external_id or "",
    "key": entity.key or "",
    "name": entity.name or "",
    "project_type": entity.project_type or ""
}
```

**Text Content for Embedding**:
```
"Key: BEN | Name: Benefits Platform | Type: software | ID: 10000"
```

**Missing from Vectorization**: None - all meaningful fields are vectorized

---

#### Statuses
**Database Columns**:
- `id`, `external_id`, `original_name`, `status_mapping_id`, `category`, `description`, `integration_id`, `tenant_id`, `active`, `created_at`, `last_updated_at`

**Vectorized Fields**:
```python
{
    "external_id": entity.external_id or "",
    "original_name": entity.original_name or "",
    "description": entity.description or "",
    "category": entity.category or ""
}
```

**Text Content for Embedding**:
```
"Name: In Progress | Category: indeterminate | Description: Work is in progress"
```

**Missing from Vectorization**: `status_mapping_id` (internal reference, not meaningful for semantic search)

---

#### Work Item Types (WITs)
**Database Columns**:
- `id`, `external_id`, `original_name`, `wits_mapping_id`, `description`, `hierarchy_level`, `integration_id`, `tenant_id`, `active`, `created_at`, `last_updated_at`

**Vectorized Fields**:
```python
{
    "external_id": entity.external_id or "",
    "original_name": entity.original_name or "",
    "description": entity.description or "",
    "hierarchy_level": entity.hierarchy_level or 0
}
```

**Text Content for Embedding**:
```
"Name: Epic | Description: A big user story that needs to be broken down | Level: 1"
```

**Missing from Vectorization**: `wits_mapping_id` (internal reference, not meaningful for semantic search)

---

### Vectorization Summary

| Entity Type | Total Columns | Vectorized | Not Vectorized | Reason for Exclusion |
|-------------|---------------|------------|----------------|---------------------|
| **Projects** | 10 | 4 | 6 | IDs, timestamps, flags (not semantic) |
| **Statuses** | 11 | 4 | 7 | IDs, timestamps, flags (not semantic) |
| **WITs** | 11 | 4 | 7 | IDs, timestamps, flags (not semantic) |

**Excluded Fields (Common Pattern)**:
- `id` - Internal database ID
- `integration_id` - Foreign key reference
- `tenant_id` - Foreign key reference
- `active` - Boolean flag
- `created_at` - Timestamp
- `last_updated_at` - Timestamp
- `*_mapping_id` - Internal mapping references

**Why These Are Excluded**: These fields are for database operations, not semantic meaning. They're available in the metadata payload stored in Qdrant, but not used for embedding generation.

---

## 🤖 Multi-Agent Architecture with Custom Fields

### Custom Fields Integration

#### Work Items Table Structure
```sql
CREATE TABLE work_items (
    -- Standard fields
    id, external_id, key, project_id, team, summary, description,
    acceptance_criteria, wit_id, status_id, resolution, story_points,
    assignee, labels, priority, parent_external_id,

    -- Special mapped fields (from custom_fields_mapping)
    team, code_changed, story_points,

    -- 20 dedicated custom field columns
    custom_field_01, custom_field_02, ..., custom_field_20,

    -- Workflow metrics
    work_first_committed_at, work_first_started_at, ...
)
```

#### Custom Fields Mapping Table
```sql
CREATE TABLE custom_fields_mapping (
    id SERIAL PRIMARY KEY,

    -- Special field mappings
    team_field_id INTEGER REFERENCES custom_fields(id),
    code_changed_field_id INTEGER REFERENCES custom_fields(id),
    story_points_field_id INTEGER REFERENCES custom_fields(id),

    -- 20 custom field mappings
    custom_field_01_id INTEGER REFERENCES custom_fields(id),
    custom_field_02_id INTEGER REFERENCES custom_fields(id),
    ...
    custom_field_20_id INTEGER REFERENCES custom_fields(id),

    integration_id INTEGER,
    tenant_id INTEGER
)
```

### Hybrid Retrieval Strategy (Recommended)

```
User Query → Orchestrator Agent
    ↓
    ├─→ Vector Search (semantic similarity)
    │   └─→ Finds: "bugs", "login", "John", "Benefits"
    │
    └─→ Metadata Filters (exact matches)
        └─→ Filters: priority='High', custom_field_X='Y'
```

**How It Works**:
1. **Vector Search**: Finds semantically similar work items based on summary/description
2. **Qdrant Metadata Filters**: Applies exact filters on custom fields, priority, assignee, etc.
3. **Combine Results**: Returns work items that match both semantic AND exact criteria

**Advantages**:
- ✅ Works with ANY custom field (no need to re-vectorize)
- ✅ Exact matching on custom fields
- ✅ Fast Qdrant metadata filtering
- ✅ Semantic search on standard fields

---

### Metadata-Based Filtering (Recommended Approach)

```python
# Store custom fields in Qdrant metadata
vector_data = {
    'id': 'BEN-123',
    'vector': embedding,  # From standard fields only
    'payload': {
        'key': 'BEN-123',
        'summary': 'Fix login bug',
        'priority': 'High',
        'assignee': 'John Doe',
        # Custom fields in metadata
        'custom_fields': {
            'security_level': 'Critical',
            'target_release': 'Q1 2025',
            'notes': 'This is a critical security issue'
        }
    }
}
```

**Query Pattern**:
```python
# Qdrant supports filtering on metadata
results = qdrant_client.search(
    collection_name="tenant_1_work_items",
    query_vector=embedding,
    query_filter={
        "must": [
            {"key": "priority", "match": {"value": "High"}},
            {"key": "custom_fields.security_level", "match": {"value": "Critical"}}
        ]
    }
)
```

**Advantages**:
- ✅ Semantic search on standard fields
- ✅ Exact filtering on custom fields
- ✅ No need to re-vectorize when custom fields change
- ✅ Qdrant handles the filtering efficiently
- ✅ Tenant-specific custom fields supported

---

### Multi-Agent Query Flow

```
User: "Show me high-priority bugs in Benefits with security_level=Critical"
    ↓
Orchestrator Agent
    ↓
    ├─→ Parse Query
    │   ├─ Semantic: "bugs", "Benefits"
    │   └─ Filters: priority="High", custom_fields.security_level="Critical"
    │
    ├─→ Route to Jira Agent
    │   └─→ Qdrant Vector Search with Metadata Filters
    │       └─→ Returns: BEN-123, BEN-456
    │
    └─→ Enrich with Database Data
        └─→ SQL JOIN to get full work item details + custom fields
        └─→ Returns: Complete work item objects
```

---

**The AI & Vectorization system provides comprehensive semantic search capabilities across all platform data, enabling intelligent insights and content discovery with full support for custom fields and metadata filtering.**
