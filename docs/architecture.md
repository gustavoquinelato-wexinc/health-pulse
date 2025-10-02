# architecture.md - Architecture Guide

**Pulse Platform System Architecture & Design**

This document provides a comprehensive overview of the Pulse Platform's architecture, including system topology, multi-tenancy design, database architecture, and deployment configurations.

## 🏗️ System Architecture Overview

### Five-Tier Architecture with AI ✅ **ENHANCED WITH COMPREHENSIVE VECTORIZATION**

Pulse Platform follows a modern microservices architecture with centralized authentication, comprehensive AI capabilities, and clear separation of concerns. **Phase 3-4 Complete**: All ETL data tables now have AI vectorization for unified semantic search.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend Application                         │
│                   (React/TypeScript - Port 5173)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📊 Executive Dashboards    🎨 Client Branding                  │
│  📈 DORA Metrics           🌙 Dark/Light Mode                   │
│  🔧 Admin Interface        📱 Responsive Design                 │
│  🤖 AI Features            🔍 Semantic Search                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                    │                       │
                    ▼                       ▼
┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
│  Backend        │              │  ETL Frontend   │              │  ETL Service    │
│  Service        │◄────────────►│  (React/TS)     │              │  (LEGACY)       │
│  (FastAPI)      │              │  Port: 5174     │              │  Port: 8002     │
│  Port: 3001     │              │                 │              │                 │
│                 │              │ • Job Cards     │              │ ⚠️ DO NOT USE   │
│ • Authentication│              │ • WIT Mgmt      │              │ • Old Monolith  │
│ • User Mgmt     │              │ • Status Mgmt   │              │ • Jinja2 HTML   │
│ • Session Mgmt  │              │ • Integrations  │              │ • Legacy Backup │
│ • API Gateway   │              │ • Dark Mode     │              │ • Reference Only│
│ • Client Mgmt   │              │ • Responsive    │              │                 │
│ • ML Monitoring │              │                 │              │ See NEW_ETL_    │
│ • AI Operations │              │                 │              │ ARCHITECTURE.md │
│ • Flexible AI   │              │                 │              │ for migration   │
│ • Embeddings    │              │                 │              │ details         │
│ • Chat Agents   │              │                 │              │                 │
│ • Vector Ops    │              │                 │              │                 │
│ • JSON Routing  │              │                 │              │                 │
│ • RBAC & JWT    │              │                 │              │                 │
│ • ETL Endpoints │              │                 │              │                 │
│   /app/etl/*    │              │                 │              │                 │
└─────────────────┘              └─────────────────┘              └─────────────────┘
                    │                       │
                    └───────────────────────┼─────┐
                                           │     │
                                           ▼     ▼
                        ┌─────────────────┐    ┌─────────────────┐         │
                        │  PostgreSQL     │───►│  PostgreSQL     │         │
                        │  PRIMARY        │    │  REPLICA        │         │
                        │  Port: 5432     │    │  Port: 5433     │         │
                        │                 │    │                 │         │
                        │ • Write Ops     │    │ • Read Ops      │         │
                        │ • User Mgmt     │    │ • Analytics     │         │
                        │ • Job Control   │    │ • Dashboards    │         │
                        │ • Auth/Sessions │    │ • Reports       │         │
                        │ • ML Monitoring │    │ • ML Analytics  │         │
                        │ • Vector Ops    │    │ • Similarity    │         │
                        │ • pgvector      │    │ • pgvector      │         │
                        │ • postgresml    │    │ • postgresml    │         │
                        └─────────────────┘    └─────────────────┘         │
                                │                       ▲                 │
                                └───WAL Streaming───────┘                 │
                                                                          │
                        ┌─────────────────────────────────────────────────┘
                        ▼
                ┌─────────────────┐    ┌─────────────────┐
                │  Qdrant Vector  │    │  Redis Cache    │
                │  Database       │    │  Port: 6379     │
                │  Port: 6333     │    │                 │
                │                 │    │ • Session Store │
                │ • Vector Store  │    │ • API Cache     │
                │ • Embeddings    │    │ • Job Queue     │
                │ • Similarity    │    │ • Rate Limiting │
                │ • Collections   │    │ • Color Cache   │
                │ • Tenant Isolation │ │ • Performance   │
                │ • HNSW Indexes  │    │ • LRU Eviction  │
                │ • Semantic Search│   │                 │
                └─────────────────┘    └─────────────────┘
```

### Service Responsibilities

#### Frontend Application (Port 5173)
- **Executive Dashboards**: C-level friendly visualizations and KPIs
- **DORA Metrics**: Lead time, deployment frequency, change failure rate, MTTR
- **User Interface**: Responsive design with client-specific branding
- **Authentication Flow**: JWT token management and session handling
- **Real-time Updates**: WebSocket integration for live data

#### Backend Service (Port 3001)
- **Authentication & RBAC**: JWT token management and role-based access control
- **User Management**: User accounts, sessions, and permissions
- **API Gateway**: Central API routing and request handling
- **Client Management**: Multi-tenant client configuration and isolation
- **ML Monitoring**: AI performance tracking and analytics integration
- **ETL Endpoints**: New ETL backend APIs at `/app/etl/*` (see `docs/etl/NEW_ETL_ARCHITECTURE.md`)

#### ETL Frontend (Port 5174) - **NEW ARCHITECTURE**
- **Modern React UI**: TypeScript + Vite + Tailwind CSS
- **Job Management**: Job cards, status tracking, execution controls
- **Configuration**: WITs, statuses, hierarchies, workflows, integrations
- **Dark Mode**: Full theme support with auto-inverting logos
- **Real-time Updates**: Job progress and status monitoring
- **⚠️ Note**: Replaces old ETL service (port 8002) - see migration guide

#### ETL Service (Port 8002) - **⚠️ LEGACY - DO NOT USE**
- **Status**: Legacy monolithic service kept as reference/backup only
- **DO NOT**: Modify or add new features to this service
- **Migration**: All new ETL development goes to `etl-frontend` + `backend-service/app/etl/`
- **Documentation**: See `docs/etl/NEW_ETL_ARCHITECTURE.md` for full migration guide

#### Qdrant Vector Database (Port 6333)
- **Vector Storage**: High-performance vector database for embeddings
- **Semantic Search**: Fast similarity search with HNSW indexes
- **Tenant Isolation**: Client-specific collections for multi-tenancy
- **Scalability**: Optimized for 10M+ vectors with performance tuning
- **API Access**: HTTP (6333) and gRPC (6334) interfaces
- **Integration**: Replaces PostgreSQL pgvector for dedicated vector operations

#### Redis Cache (Port 6379)
- **Session Storage**: User session and authentication token caching
- **API Caching**: Response caching for improved performance
- **Job Queue**: Background job queuing and processing
- **Rate Limiting**: API rate limiting and throttling
- **Color Caching**: Client-specific color scheme caching
- **Performance**: LRU eviction with 256MB memory limit
- **Session Coordination**: Cross-service session management

#### Backend Service (Port 3001)
- **User Management**: User CRUD (profile/preferences); no RBAC logic
- **API Gateway**: Unified interface for frontend and ETL service
- **Auth Delegation**: Delegates JWT validation and permission checks to Auth Service
- **Client Management**: Multi-tenant client isolation and configuration
- **Analytics APIs**: DORA metrics, GitHub analytics, portfolio insights

#### ETL Service (Port 8000)
- **Data Processing**: Extract, transform, load operations
- **Job Orchestration**: Smart scheduling with recovery strategies
- **Integration Management**: Web interface for external system connections
- **AI Provider Support**: Unified configuration for AI services (WEX AI Gateway, OpenAI, Azure)
- **Logo Management**: Tenant-based asset organization with file upload
- **Real-time Monitoring**: WebSocket updates and progress tracking
- **Admin Interface**: Configuration and management tools
- **AI Agent Integration**: LangGraph workflows for strategic business intelligence
- **Comprehensive AI Vectorization**: Bulk vector processing for all 13 data tables
- **Semantic Search**: Vector-based content discovery and analysis across all business data
- **ML Data Preparation**: Data preprocessing for AI models
- **ETL → Backend AI Integration**: Clean service boundaries with Backend handling all AI operations



## 🏢 Multi-Tenant Architecture

### Client Isolation Strategy

Pulse Platform implements **complete client isolation** at multiple levels:

#### Database Level Isolation
```sql
-- All tables include tenant_id for tenant separation
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    email VARCHAR(255) NOT NULL,
    -- ... other fields
    UNIQUE(tenant_id, email)
);

-- Every query filters by tenant_id
SELECT * FROM users WHERE tenant_id = ? AND active = true;
```

#### Application Level Isolation
- **JWT Tokens**: Include tenant_id in token payload
- **API Endpoints**: All endpoints validate tenant ownership
- **Session Management**: Tenant-scoped session storage
- **Job Processing**: Background jobs respect tenant boundaries

#### Configuration Isolation
- **Tenant-Specific Settings**: Stored in system_settings table (color schemas, branding)
- **User-Specific Settings**: Stored in users table (theme_mode preferences)
- **Custom Branding**: Per-tenant logos and color schemes
- **Integration Configs**: Separate API credentials and logos per tenant
- **Asset Isolation**: Tenant-specific logo and file storage
- **Feature Flags**: Tenant-specific feature enablement

### Multi-Instance Deployment

For handling multiple tenants simultaneously:

```bash
# Multiple ETL instances for different tenants
TENANT_NAME=wex python -m uvicorn app.main:app --port 8000
TENANT_NAME=techcorp python -m uvicorn app.main:app --port 8001
TENANT_NAME=enterprise python -m uvicorn app.main:app --port 8002
```

## 🗄️ Database Architecture

### Primary-Replica Setup

The platform uses PostgreSQL with streaming replication for high availability:

#### Primary Database (Port 5432)
- **Write Operations**: All INSERT, UPDATE, DELETE operations
- **User Management**: Authentication and session data
- **Job Control**: ETL job status and configuration
- **Real-time Data**: Live updates and notifications

#### Replica Database (Port 5433)
- **Read Operations**: Analytics queries and dashboard data
- **Reporting**: Historical data analysis and metrics
- **Performance**: Offloads read traffic from primary
- **Backup**: Additional data redundancy

#### Replication Configuration
```sql
-- Primary database configuration
wal_level = replica
max_wal_senders = 3
wal_keep_segments = 64
archive_mode = on

-- Replica configuration
hot_standby = on
primary_conninfo = 'host=primary port=5432 user=replicator'
primary_slot_name = 'replica_slot'
```

### Schema Design

#### Core Tables

The database schema includes comprehensive business data tables with integrated AI capabilities:

**Business Data Tables (24 tables with vector columns)**:
- **Tenant Management**: `tenants` - Multi-tenant foundation
- **User Management**: `users`, `users_sessions`, `users_permissions` - Authentication and RBAC
- **Integration Management**: `integrations` - External system connections with AI provider support
- **Project Management**: `projects`, `workflows` - Project structure and workflows
- **Work Item Tracking**: `work_items`, `changelogs` - Work item data with change history
- **Development Data**: `repositories`, `prs`, `prs_*` - GitHub development metrics
- **Configuration**: `statuses`, `wits`, `*_mappings` - Workflow and type mappings
- **System Management**: `system_settings`, `etl_jobs` - Configuration and job control
- **Analytics**: `dora_market_benchmarks`, `dora_metric_insights` - Performance benchmarks
- **UI Customization**: `client_color_settings` - Client-specific branding

#### AI Enhancement Features (Phase 1)

**Vector Columns**: All 24 business tables include `embedding vector(1536)` columns for:
- Semantic search capabilities
- Content similarity analysis
- Future ML model integration
- Text embedding storage (OpenAI text-embedding-3-small compatible)

**ML Monitoring Tables**:
```sql
-- AI Learning Memory - User feedback and corrections
CREATE TABLE ai_learning_memory (
    id SERIAL PRIMARY KEY,
    error_type VARCHAR(50) NOT NULL,
    user_intent TEXT NOT NULL,
    failed_query TEXT NOT NULL,
    specific_issue TEXT NOT NULL,
    corrected_query TEXT,
    user_feedback TEXT,
    user_correction TEXT,
    message_id VARCHAR(255),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW()
);

-- AI Predictions - ML model predictions and accuracy tracking
CREATE TABLE ai_predictions (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    prediction_value FLOAT NOT NULL,
    input_features TEXT,
    actual_value FLOAT,
    accuracy_score FLOAT,
    prediction_type VARCHAR(50) NOT NULL,
    validated_at TIMESTAMP,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW()
);

-- AI Performance Metrics - System performance monitoring
CREATE TABLE ai_performance_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    metric_unit VARCHAR(20),
    measurement_timestamp TIMESTAMP NOT NULL,
    context_data TEXT,
    service_name VARCHAR(50),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW()
);

-- ML Anomaly Alerts - Anomaly detection and alerting
CREATE TABLE ml_anomaly_alert (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    alert_data JSONB NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by INTEGER,
    acknowledged_at TIMESTAMP,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW()
);
```

#### PostgresML Integration

**Database Extensions**:
- **pgvector**: Vector similarity search and storage
- **postgresml**: Machine learning capabilities (prepared for Phase 2+)

**Vector Indexes**: HNSW indexes on embedding columns for efficient similarity search:
```sql
-- Example vector indexes
CREATE INDEX idx_work_items_embedding_hnsw ON work_items USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_prs_embedding_hnsw ON prs USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_projects_embedding_hnsw ON projects USING hnsw (embedding vector_cosine_ops);
```

**ML Dependencies**: XGBoost, LightGBM, and scikit-learn installed for future ML model training

## 🤖 AI Architecture (Phase 3 Implementation)

### AI Enhancement Overview

Pulse Platform has evolved through multiple AI phases, culminating in a clean 3-database architecture optimized for performance and scalability. The current implementation provides production-ready AI capabilities with dedicated vector storage and flexible JSON-based provider management.

### Flexible AI Provider Framework ✅ **NEW**

**Zero-Schema-Change Architecture**: All AI provider routing logic is stored in JSON configuration, enabling unlimited provider flexibility without database migrations.

**Simplified Integration Types**:
- **Data**: Jira, GitHub, WEX Fabric, WEX AD
- **AI**: WEX AI Gateway, WEX AI Gateway Fallback
- **Embedding**: Local Embeddings (free), WEX Embeddings (paid)

**Context-Aware Provider Selection**:
- **ETL Operations**: Automatically prefer local models (`source: "local"`) for cost-effective data processing
- **Frontend Operations**: Automatically prefer external models (`source: "external"`) for high-quality AI interactions
- **Gateway Routing**: `gateway_route: true` uses WEX AI Gateway as intermediary, `gateway_route: false` connects directly

**Future-Proof Design**: Easy addition of new providers (Ollama, custom LLMs, external APIs) without schema changes.

### 3-Database Architecture

**PostgreSQL Primary (Port 5432)**: Business data, AI configuration, write operations
**PostgreSQL Replica (Port 5433)**: Read operations, analytics, dashboards
**Qdrant Vector Database (Port 6333)**: Dedicated vector storage, semantic search, tenant-isolated collections

### Vector Storage & Similarity Search

**Qdrant Vector Database**: Dedicated high-performance vector storage:
- **Purpose**: Store text embeddings for semantic search and similarity analysis
- **Dimensions**: 1536 (compatible with OpenAI text-embedding-3-small)
- **Collections**: Tenant-specific collections for complete isolation
- **Performance**: Optimized for 10M+ vectors with HNSW indexes
- **APIs**: HTTP (6333) and gRPC (6334) for flexible integration

**Supported Operations**:
```sql
-- Similarity search (when embeddings are populated)
SELECT * FROM work_items
WHERE tenant_id = ?
ORDER BY embedding <-> ?::vector
LIMIT 10;

-- Vector distance calculations
SELECT id, summary, embedding <-> ?::vector AS distance
FROM work_items
WHERE tenant_id = ? AND embedding IS NOT NULL;
```

### ML Monitoring Infrastructure

**AI Learning Memory**: Captures user feedback and corrections for continuous improvement
- Error type classification and user intent tracking
- Failed query analysis and suggested fixes
- User feedback integration for model improvement

**AI Predictions**: Logs ML model predictions and accuracy tracking
- Model performance monitoring across different prediction types
- Accuracy scoring and validation tracking
- Input feature storage for model debugging

**AI Performance Metrics**: System-wide performance monitoring
- Service-level performance tracking (backend, ETL, AI)
- Metric aggregation and trend analysis
- Context-aware performance measurement

**ML Anomaly Alerts**: Automated anomaly detection and alerting
- Severity-based alert classification
- Acknowledgment workflow for operations teams
- Rich alert data storage in JSONB format

### Database Architecture for AI

**Primary Database (Port 5432)**:
- **Business Data**: Core application data and AI configuration
- **Write Operations**: All transactional data and ML monitoring
- **pgvector Extension**: Legacy vector support (migrated to Qdrant)
- **postgresml Extension**: ML model training and inference (prepared)

**Replica Database (Port 5433)**:
- **Read Operations**: Analytics, dashboards, and reporting
- **Performance**: Offloads read-heavy operations from primary
- **Consistency**: WAL streaming for real-time replication

**Qdrant Vector Database (Port 6333)**:
- **Vector Storage**: Dedicated high-performance vector operations
- **Tenant Collections**: Complete isolation with client-specific collections
- **Semantic Search**: Fast similarity search with optimized HNSW indexes
- **Scalability**: Designed for 10M+ vectors with performance tuning

### Database Migration System

**Migration Runner**: Automated database schema and data management
- **Schema Migrations**: Incremental database schema updates with rollback support
- **Data Seeding**: Tenant-specific data initialization (WEX, Apple, Google)
- **Credential Management**: Encrypted storage of integration credentials
- **DORA Benchmarks**: Performance analytics baseline data insertion
- **Column Cleanup**: Streamlined integration schema with only required JSON columns

**Migration Status**:
- ✅ **Migration 0001**: Core schema creation with clean integration table structure
- ✅ **Migration 0002**: WEX tenant setup with encrypted credentials and DORA data
- ✅ **Migration 0003**: Apple tenant configuration with project-specific settings
- ✅ **Migration 0004**: Google tenant setup with health-focused repository filtering

### AI Service Integration Points

**Backend Service**: Enhanced with ML monitoring APIs and authentication for AI features
**ETL Service**: Integrated AI Agent with LangGraph workflows, embedding generation, and ML data processing
**Frontend**: Ready for AI feature toggles, ML insights display, and semantic search interface

### Phase 3 Completion Status

✅ **3-Database Architecture**: PostgreSQL Primary/Replica + Qdrant Vector Database
✅ **Qdrant Integration**: Dedicated vector storage with tenant-isolated collections
✅ **Redis Caching**: Session storage, API caching, and performance optimization
✅ **AI Agent Integration**: LangGraph-based strategic intelligence integrated into ETL Service
✅ **Integration Management**: Web interface for external system and AI provider configuration
✅ **Vector Operations**: High-performance semantic search and similarity analysis
✅ **ML Monitoring**: Comprehensive AI performance tracking and anomaly detection
✅ **Database Migrations**: All schema migrations working correctly with clean column structure
✅ **DORA Data**: Benchmark data successfully inserted for performance analytics
✅ **WEX Tenant Setup**: Multi-tenant architecture with WEX as primary tenant (ID: 1)
✅ **Credential Management**: Encrypted storage of integration credentials with .env support
✅ **Backward Compatibility**: All existing functionality preserved and enhanced

### Current AI Capabilities (Production Ready) ✅ **PHASE 3-4 COMPLETE**

✅ **Strategic Intelligence**: LangGraph-powered business analysis and insights
✅ **Comprehensive Vectorization**: All 13 ETL data tables vectorized for unified semantic search
✅ **Bulk AI Processing**: Optimized ETL → Backend → Qdrant integration with bulk operations
✅ **Cross-Platform Search**: Unified semantic search across Jira and GitHub data
✅ **Real-time Vector Generation**: Automatic vectorization during data extraction
✅ **Integration Management**: Unified configuration for data sources and AI providers
✅ **Performance Optimization**: Redis caching and Qdrant vector operations
✅ **Tenant Isolation**: Complete multi-tenant support across all AI components
✅ **Monitoring & Analytics**: Real-time AI performance tracking and optimization
✅ **Error Resilience**: AI operation failures don't impact ETL jobs

### Vectorized Data Tables (13 total):
- **Jira Core**: changelogs, wits, statuses, projects
- **GitHub Core**: prs_comments, prs_reviews, prs_commits, repositories
- **Cross-Platform**: wits_prs_links
- **Configuration**: wits_hierarchies, wits_mappings, statuses_mappings, workflows

## � Deployment Architecture

### Docker Compose Configuration

The platform uses Docker Compose for local development and can be adapted for production deployment:

**Core Services:**
- **Frontend**: React/TypeScript application (Port 5173)
- **Backend Service**: FastAPI authentication and user management (Port 3001)
- **ETL Service**: FastAPI data processing, job orchestration, and AI agent (Port 8000)

**Data Layer:**
- **PostgreSQL Primary**: PostgresML image with pgvector (Port 5432)
- **PostgreSQL Replica**: Read replica with WAL streaming (Port 5433)
- **Qdrant**: Vector database for embeddings (Ports 6333/6334)
- **Redis**: Cache and session storage (Port 6379)

**Networking:**
- **Internal Network**: `pulse-network` bridge for service communication
- **Health Checks**: All services include health check endpoints
- **Volume Persistence**: Data persistence for databases and cache

### Production Considerations

**Scalability:**
- Services can be horizontally scaled using container orchestration
- Database replicas can be added for read scaling
- Qdrant supports clustering for vector storage scaling

**Security:**
- All inter-service communication over internal network
- Environment-based configuration for secrets
- JWT-based authentication with configurable providers

## �📊 Logging & Monitoring Architecture

### Structured Logging System

The platform implements a comprehensive structured logging system with the following features:

#### **ETL Service Logging**
- **Structured Logs**: Using structlog for rich, contextual logging with key-value pairs
- **Colorful Console Output**: Beautiful colored logs for development and debugging
- **Windows Compatible**: No Unicode emoji characters to prevent encoding errors
- **Categorized Prefixes**: Clear prefixes for easy filtering and analysis

#### **Log Categories**
```
[HTTP]    - HTTP requests and responses with timing and status codes
[WS]      - WebSocket connections, messages, and client management
[AUTH]    - Authentication flows, token validation, and session management
[JIRA]    - Jira job execution, API calls, and data processing
[GITHUB]  - GitHub job execution, API calls, and repository operations
[ORCH]    - Orchestrator operations, job scheduling, and coordination
[ETL]     - ETL service lifecycle events and configuration
[SCHED]   - Scheduler operations and job timing
[COLOR]   - Color schema management and client branding
[BULK]    - Bulk database operations and performance metrics
[ERROR]   - Error conditions, exceptions, and failure scenarios
[TEST]    - Testing, debugging, and development messages
```

#### **Log Output Example**
```
2025-09-04T01:19:52.225555Z [info] [HTTP] Request [app.core.logging_config] method=GET url=http://localhost:8000/ headers_count=15
2025-09-04T01:19:52.226255Z [info] [WS] Connected [app.core.websocket_manager] job_name=Jira total_connections=1
2025-09-04T01:19:52.239316Z [info] [BULK] Processing 9 issuetypes records for bulk insert [jobs] job_name=Jira
```

#### **Monitoring Integration**
- **Real-time WebSocket Updates**: Live progress tracking for all ETL jobs
- **Client-Specific Log Files**: Separate log files per client for isolation
- **Web-Based Log Viewer**: Built-in log management interface at `/logs`
- **Performance Metrics**: Request timing, database operation metrics, and job execution stats

---

## 📚 Related Documentation

**Core System Documentation:**
- [Security & Authentication](security-authentication.md) - RBAC, JWT tokens, permissions, tenant isolation
- [Jobs & Orchestration](jobs-orchestration.md) - ETL jobs, orchestrator, recovery strategies
- [Integration Management](integration-management.md) - External system connections and AI providers
- [System Settings](system-settings.md) - Configuration reference, settings explanation
- [Installation & Setup](installation-setup.md) - Requirements, deployment, database setup

**AI & Advanced Features:**
- [Flexible AI Providers](flexible-ai-providers.md) - JSON-based provider management and routing
- [AI Agent Architecture](hackathon/ai-agent-architecture.md) - LangGraph workflows and strategic intelligence
- [AI Evolution Plans](evolution_plans/ai/) - AI development phases and roadmap
- [Development Guide](../services/etl-service/docs/development-guide.md) - Development, testing, debugging

**Infrastructure & Operations:**
- [Log Management Guide](../services/etl-service/docs/log-management.md) - Comprehensive logging system
- [Docker Compose](../docker-compose.yml) - Container orchestration configuration
- [Environment Configuration](../.env.example) - Environment variables and settings