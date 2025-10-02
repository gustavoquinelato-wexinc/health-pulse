# Phase 3-1: Clean Database Schema + Qdrant Integration

**Implemented**: YES ✅
**Duration**: 1 day (Day 1 of 10)
**Priority**: CRITICAL
**Dependencies**: Phase 2 completion

## 🎯 Phase 3 Overview

**Transform the Pulse Platform into a high-performance AI-powered system with:**
- **Clean 3-Database Architecture**: PostgreSQL Primary + Replica + Qdrant (no backward compatibility)
- **Multi-Provider AI Support**: OpenAI, Azure, Sentence Transformers, Custom Gateway (WrenAI-inspired)
- **10x Performance Improvement**: Optimized LangGraph with intelligent caching and parallel processing
- **Enterprise-Scale Vector Operations**: Ready for 10M+ records from day one
- **WrenAI-Inspired Optimizations**: Configuration-driven pipelines, provider abstraction, and cost optimization

**Total Phase 3 Duration**: 10 days (6 sub-phases)
**Next Phases**: 3-2 → 3-3 → 3-4 → 3-5 → 3-6

## 🎯 Phase 3-1 Objectives

1. **CLEAN VECTOR REMOVAL**: Remove all vector columns from PostgreSQL (no backward compatibility)
2. **Qdrant Integration**: Add Qdrant as dedicated vector database for 10M+ scale
3. **AI Configuration Tables**: Add AI provider and configuration management
4. **3-Database Architecture**: PostgreSQL Primary + Replica + Qdrant
5. **Migration Rollback**: Clean slate approach with fresh migrations

## 🎯 Key Decisions Made (Phase 3 Overall)

### **1. Clean Slate Approach** ✅
- **No backward compatibility** - Remove all vector columns from PostgreSQL
- **No data migration** - Fresh start with clean migrations
- **Simplified architecture** - PostgreSQL handles business data only

### **2. 3-Database Architecture** ✅
- **PostgreSQL Primary (5432)**: Business data, AI configuration, write operations
- **PostgreSQL Replica (5433)**: Read operations, analytics, dashboards
- **Qdrant (6333)**: Vector storage ONLY, semantic search, client-isolated collections

### **3. Optimized LangGraph (Single Framework)** ✅
- **No Hamilton complexity** - Stick with optimized LangGraph for simplicity
- **Performance optimizations**: Parallel processing, intelligent caching, smart routing
- **10x performance improvement** through optimization, not framework complexity

## 🗄️ 3-Database Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLEAN 3-DATABASE SETUP                       │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL Primary     │  PostgreSQL Replica    │  Qdrant      │
│  (Port 5432)           │  (Port 5433)           │  (Port 6333)  │
│  ├─ Business Data      │  ├─ Read Operations     │  ├─ Vectors  │
│  ├─ User Management    │  ├─ Analytics          │  ├─ Semantic │
│  ├─ AI Configuration   │  ├─ Reports            │  ├─ Search   │
│  ├─ Job Orchestration  │  ├─ Dashboards         │  ├─ RAG      │
│  ├─ Qdrant References  │  ├─ ML Monitoring      │  ├─ Client   │
│  └─ NO VECTOR COLUMNS  │  └─ NO VECTOR COLUMNS   │  └─ Isolated │
└─────────────────────────────────────────────────────────────────┘
```

### **Database Responsibilities:**
- **PostgreSQL Primary**: All business logic, AI configuration, write operations
- **PostgreSQL Replica**: Read operations, analytics, dashboards, reports
- **Qdrant**: Vector storage ONLY, semantic search, AI operations, client-isolated collections

## 🔄 **Implementation Tasks**

### **Task 3-1.1: Clean Migration Rollback**
```bash
# services/backend-service
python scripts/migration_runner.py --rollback-all

# This will:
# 1. Drop all tables with vector columns
# 2. Clean slate for fresh start
# 3. Remove all AI Phase 1 vector infrastructure
```

### **Task 3-1.2: Update Migration 0001 (Remove All Vector Columns)**
**File**: `services/backend-service/scripts/migrations/0001_initial_db_schema.py`

```sql
-- REMOVE embedding vector(1536) from ALL 24 tables
-- Clean approach - no backward compatibility

-- Example: Clean work_items table (apply to all 24 tables)
CREATE TABLE IF NOT EXISTS work_items (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id),
    key VARCHAR(50) NOT NULL,
    summary TEXT,
    description TEXT,
    -- ... all existing business fields ...
    -- NO EMBEDDING COLUMN - vectors go to Qdrant only
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(tenant_id, key)
);

-- Apply same pattern to all 24 tables:
-- tenants, users, projects, repositories, prs, prs_comments,
-- prs_reviews, prs_commits, statuses, statuses_mappings,
-- wits, wits_mappings, wits_hierarchies, workflows,
-- changelogs, wits_prs_links, projects_wits,
-- projects_statuses, user_permissions, user_sessions, system_settings,
-- dora_market_benchmarks, dora_metric_insights

-- NO vector columns in ANY table
```

### **Task 3-1.3: Add Qdrant Reference Tracking**
```sql
-- New table to track Qdrant vectors with client isolation
CREATE TABLE IF NOT EXISTS qdrant_vectors (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    table_name VARCHAR(50) NOT NULL,
    record_id INTEGER NOT NULL,
    qdrant_collection VARCHAR(100) NOT NULL,
    qdrant_point_id UUID NOT NULL,
    vector_type VARCHAR(50) NOT NULL, -- 'content', 'summary', 'metadata'
    embedding_model VARCHAR(100) NOT NULL, -- Track which model generated this
    embedding_provider VARCHAR(50) NOT NULL, -- 'openai', 'azure', 'sentence_transformers'
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(client_id, table_name, record_id, vector_type)
);

-- Performance indexes
CREATE INDEX idx_qdrant_vectors_client ON qdrant_vectors(client_id);
CREATE INDEX idx_qdrant_vectors_table_record ON qdrant_vectors(table_name, record_id);
CREATE INDEX idx_qdrant_vectors_collection ON qdrant_vectors(qdrant_collection);
CREATE INDEX idx_qdrant_vectors_point_id ON qdrant_vectors(qdrant_point_id);
CREATE INDEX idx_qdrant_vectors_provider ON qdrant_vectors(embedding_provider);
```

### **Task 3-1.4: Enhanced Integration Table (WrenAI-Inspired Multi-Provider Support)**
```sql
-- Enhanced integrations table with AI provider support
CREATE TABLE IF NOT EXISTS integrations (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    integration_type VARCHAR(50) NOT NULL, -- 'jira', 'github', 'ai_provider'
    integration_subtype VARCHAR(50), -- 'embedding', 'llm', 'gateway', 'data_source'
    integration_name VARCHAR(100) NOT NULL,
    base_url TEXT,
    credentials JSONB DEFAULT '{}',
    configuration JSONB DEFAULT '{}',

    -- AI-specific columns (inspired by WrenAI's provider abstraction)
    model_config JSONB DEFAULT '{}', -- Model-specific configuration
    performance_config JSONB DEFAULT '{}', -- Timeout, batch size, etc.
    fallback_integration_id INTEGER REFERENCES integrations(id),
    
    -- WrenAI-inspired provider metadata
    provider_metadata JSONB DEFAULT '{}', -- Provider capabilities, limits, etc.
    cost_config JSONB DEFAULT '{}', -- Cost tracking configuration

    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);
```

### **Task 3-1.5: AI Configuration Tables (WrenAI-Inspired)**
```sql
-- Tenant AI preferences (inspired by WrenAI's configuration system)
CREATE TABLE IF NOT EXISTS tenant_ai_preferences (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    preference_type VARCHAR(50) NOT NULL, -- 'default_models', 'performance', 'cost_limits'
    configuration JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    UNIQUE(tenant_id, preference_type)
);

-- Tenant AI configuration (inspired by WrenAI's pipeline configuration)
CREATE TABLE IF NOT EXISTS tenant_ai_configuration (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    config_category VARCHAR(50) NOT NULL, -- 'embedding_models', 'llm_models', 'pipeline_config'
    configuration JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    UNIQUE(tenant_id, config_category)
);

-- AI usage tracking (inspired by WrenAI's cost monitoring)
CREATE TABLE IF NOT EXISTS ai_usage_tracking (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    provider VARCHAR(50) NOT NULL, -- 'openai', 'azure', 'sentence_transformers'
    operation VARCHAR(50) NOT NULL, -- 'embedding', 'text_generation', 'analysis'
    model_name VARCHAR(100),
    input_count INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost DECIMAL(10,4) DEFAULT 0.0,
    request_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);
```

### **Task 3-1.6: Add Qdrant to Docker Compose**
**File**: `docker-compose.yml`

```yaml
services:
  qdrant:
    image: qdrant/qdrant:v1.11.0
    container_name: pulse-qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"  # HTTP API
      - "6334:6334"  # gRPC API  
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__HTTP_PORT: 6333
      QDRANT__SERVICE__GRPC_PORT: 6334
      QDRANT__LOG_LEVEL: INFO
      # Performance optimizations for 10M+ scale
      QDRANT__STORAGE__PERFORMANCE__MAX_SEARCH_THREADS: 4
      QDRANT__STORAGE__PERFORMANCE__MAX_OPTIMIZATION_THREADS: 2
    networks:
      - pulse-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  qdrant_data:
```

### **Task 3-1.7: Environment Configuration**
**File**: `.env`

```bash
# Qdrant Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_TIMEOUT=120

# AI Provider Configuration (WrenAI-inspired)
DEFAULT_EMBEDDING_PROVIDER=sentence_transformers
DEFAULT_LLM_PROVIDER=azure_openai
AI_CACHE_TTL=3600
AI_BATCH_SIZE=100
AI_MAX_RETRIES=3
```

## ✅ Success Criteria

1. **Clean Migration**: All vector columns removed from PostgreSQL
2. **Qdrant Setup**: Qdrant service running and accessible
3. **Reference Tracking**: qdrant_vectors table created and indexed
4. **AI Configuration**: All AI configuration tables created
5. **3-Database Health**: All three databases (Primary, Replica, Qdrant) operational
6. **Client Isolation**: Qdrant collections properly namespaced by client

## 🚨 Risk Mitigation

1. **Data Loss Prevention**: Confirm no production data before rollback
2. **Service Dependencies**: Update all services to handle missing vector columns
3. **Qdrant Connectivity**: Verify network connectivity between services
4. **Performance Testing**: Validate Qdrant performance with test data

## 📝 Testing Checklist

- [ ] Migration rollback completes successfully
- [ ] Migration 0001 runs without vector columns
- [ ] Qdrant service starts and responds to health checks
- [ ] qdrant_vectors table created with proper indexes
- [ ] AI configuration tables created
- [ ] All three databases accessible from services
- [ ] Client isolation working in Qdrant collections

## 🔄 Completion Enables

- **Phase 3-2**: Multi-provider AI framework implementation
- **Phase 3-3**: Frontend AI configuration interface
- **Phase 3-4**: ETL AI integration with Qdrant
- **Phase 3-5**: High-performance vector generation
