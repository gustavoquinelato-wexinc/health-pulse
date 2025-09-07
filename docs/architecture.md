# architecture.md - Architecture Guide

**Pulse Platform System Architecture & Design**

This document provides a comprehensive overview of the Pulse Platform's architecture, including system topology, multi-tenancy design, database architecture, and deployment configurations.

## 🏗️ System Architecture Overview

### Five-Tier Architecture with AI

Pulse Platform follows a modern microservices architecture with centralized authentication, AI capabilities, and clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend Application                         │
│                   (React/TypeScript - Port 3000)               │
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
┌─────────────────┐              ┌─────────────────┐    ┌─────────────────┐
│  Backend        │              │  ETL Service    │    │  AI Service     │
│  Service        │◄────────────►│  (FastAPI)      │◄──►│  (FastAPI)      │
│  (FastAPI)      │              │  Port: 8000     │    │  Port: 5000     │
│  Port: 3001     │              │                 │    │                 │
│                 │              │ • Data Extract  │    │ • ML Models     │
│ • Authentication│              │ • Job Control   │    │ • Embeddings    │
│ • User Mgmt     │              │ • Orchestration │    │ • Predictions   │
│ • Session Mgmt  │              │ • Recovery      │    │ • Validation    │
│ • API Gateway   │              │ • Admin APIs    │    │ • Monitoring    │
│ • Client Mgmt   │              │ • ML Data Prep  │    │ • Inference     │
│ • ML Monitoring │              │                 │    │                 │
└─────────────────┘              └─────────────────┘    └─────────────────┘
                    │                       │                       │
                    └───────────────────────┼───────────────────────┼─────┐
                                           │                       │     │
                                           ▼                       ▼     ▼
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
                ┌─────────────────┐
                │  Auth Service   │
                │  (FastAPI)      │
                │  Port: 4000     │
                │                 │
                │ • Centralized   │
                │   Authentication│
                │ • RBAC          │
                │ • JWT Tokens    │
                │ • SSO           │
                │ • OKTA Ready    │
                └─────────────────┘
```

### Service Responsibilities

#### Frontend Application (Port 3000)
- **Executive Dashboards**: C-level friendly visualizations and KPIs
- **DORA Metrics**: Lead time, deployment frequency, change failure rate, MTTR
- **User Interface**: Responsive design with client-specific branding
- **Authentication Flow**: JWT token management and session handling
- **Real-time Updates**: WebSocket integration for live data

#### Auth Service (Port 4000)
- **Centralized Authentication & RBAC**: OAuth-like flow, RBAC source of truth
- **Cross-Domain SSO**: Single sign-on across all services
- **Provider Abstraction**: Local database and OKTA integration ready
- **Token Authority**: JWT generation and validation
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
- **Integration Management**: Jira, GitHub, and custom data sources
- **Real-time Monitoring**: WebSocket updates and progress tracking
- **Admin Interface**: Configuration and management tools
- **ML Data Preparation**: Data preprocessing for AI models (Phase 2+)

#### AI Service (Port 5000) - Phase 1 Foundation
- **ML Model Management**: Model training, validation, and inference (Phase 2+)
- **Embedding Generation**: Text-to-vector conversion for semantic search (Phase 2+)
- **Prediction Services**: Story point estimation, timeline forecasting (Phase 3+)
- **Validation Layer**: Smart data validation using ML models (Phase 2+)
- **Monitoring Integration**: Performance metrics and anomaly detection
- **Vector Operations**: Similarity search and content analysis (Phase 2+)

## 🏢 Multi-Tenant Architecture

### Client Isolation Strategy

Pulse Platform implements **complete client isolation** at multiple levels:

#### Database Level Isolation
```sql
-- All tables include client_id for tenant separation
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    email VARCHAR(255) NOT NULL,
    -- ... other fields
    UNIQUE(client_id, email)
);

-- Every query filters by client_id
SELECT * FROM users WHERE client_id = ? AND active = true;
```

#### Application Level Isolation
- **JWT Tokens**: Include client_id in token payload
- **API Endpoints**: All endpoints validate client ownership
- **Session Management**: Client-scoped session storage
- **Job Processing**: Background jobs respect client boundaries

#### Configuration Isolation
- **Client-Specific Settings**: Stored in system_settings table (color schemas, branding)
- **User-Specific Settings**: Stored in users table (theme_mode preferences)
- **Custom Branding**: Per-client logos and color schemes
- **Integration Configs**: Separate API credentials per client
- **Feature Flags**: Client-specific feature enablement

### Multi-Instance Deployment

For handling multiple clients simultaneously:

```bash
# Multiple ETL instances for different clients
CLIENT_NAME=wex python -m uvicorn app.main:app --port 8000
CLIENT_NAME=techcorp python -m uvicorn app.main:app --port 8001
CLIENT_NAME=enterprise python -m uvicorn app.main:app --port 8002
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
- **User Management**: `users`, `user_sessions`, `user_permissions` - Authentication and RBAC
- **Integration Management**: `integrations` - External system connections
- **Project Management**: `projects`, `workflows` - Project structure and workflows
- **Work Item Tracking**: `work_items`, `changelogs` - Work item data with change history
- **Development Data**: `repositories`, `prs`, `prs_*` - GitHub development metrics
- **Configuration**: `statuses`, `wits`, `*_mappings` - Workflow and type mappings
- **System Management**: `system_settings`, `job_schedules` - Configuration and job control
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
    client_id INTEGER NOT NULL REFERENCES clients(id),
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
    client_id INTEGER NOT NULL REFERENCES clients(id),
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
    client_id INTEGER NOT NULL REFERENCES clients(id),
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
    client_id INTEGER NOT NULL REFERENCES clients(id),
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
CREATE INDEX idx_issues_embedding_hnsw ON issues USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_pull_requests_embedding_hnsw ON pull_requests USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_projects_embedding_hnsw ON projects USING hnsw (embedding vector_cosine_ops);
```

**ML Dependencies**: XGBoost, LightGBM, and scikit-learn installed for future ML model training

## 🤖 AI Architecture (Phase 1 Implementation)

### AI Enhancement Overview

Pulse Platform has been enhanced with comprehensive AI capabilities as part of the AI Evolution Plan Phase 1. The implementation provides the foundation for advanced machine learning features while maintaining backward compatibility.

### Vector Storage & Similarity Search

**Vector Columns**: All business tables now include `embedding vector(1536)` columns:
- **Purpose**: Store text embeddings for semantic search and similarity analysis
- **Dimensions**: 1536 (compatible with OpenAI text-embedding-3-small)
- **Current State**: Columns exist but are NULL during Phase 1 (populated in Phase 2+)
- **Indexing**: HNSW indexes for efficient similarity search

**Supported Operations**:
```sql
-- Similarity search (when embeddings are populated)
SELECT * FROM issues
WHERE client_id = ?
ORDER BY embedding <-> ?::vector
LIMIT 10;

-- Vector distance calculations
SELECT id, summary, embedding <-> ?::vector AS distance
FROM issues
WHERE client_id = ? AND embedding IS NOT NULL;
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
- **pgvector Extension**: Vector operations and similarity search
- **postgresml Extension**: ML model training and inference (prepared)
- **Write Operations**: All ML monitoring data and vector updates

**Replica Database (Port 5433)**:
- **Read Operations**: ML analytics and similarity search queries
- **Performance**: Offloads AI-heavy read operations from primary
- **Consistency**: Same extensions available for inference operations

### AI Service Integration Points

**Backend Service**: Enhanced with ML monitoring APIs and vector-aware models
**ETL Service**: Prepared for embedding generation and ML data processing
**Frontend**: Ready for AI feature toggles and ML insights display
**Auth Service**: Unchanged - maintains existing authentication flow

### Phase 1 Completion Status

✅ **Database Schema**: Enhanced with vector columns and ML monitoring tables
✅ **Model Updates**: All unified models support vector columns and ML entities
✅ **Infrastructure**: PostgresML and pgvector extensions installed
✅ **Indexes**: Vector similarity search indexes created
✅ **Dependencies**: ML libraries (XGBoost, LightGBM, scikit-learn) installed
✅ **Backward Compatibility**: All existing functionality preserved

### Future AI Capabilities (Phase 2+)

🔄 **Validation Layer**: Smart data validation using ML models
🔄 **Embedding Generation**: Automatic text embedding for all content
🔄 **Similarity Search**: Content discovery and duplicate detection
🔄 **Predictive Analytics**: Story point estimation and timeline forecasting
🔄 **Anomaly Detection**: Automated issue and performance anomaly detection
🔄 **Conversational Interface**: Natural language query and interaction

## 📊 Logging & Monitoring Architecture

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