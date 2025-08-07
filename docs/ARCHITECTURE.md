# Architecture Guide

**Pulse Platform System Architecture & Design**

This document provides a comprehensive overview of the Pulse Platform's architecture, including system topology, multi-tenancy design, database architecture, and deployment configurations.

## 🏗️ System Architecture Overview

### Three-Tier Architecture

Pulse Platform follows a modern microservices architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend Application                         │
│                   (React/TypeScript - Port 3000)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📊 Executive Dashboards    🎨 Client Branding                  │
│  📈 DORA Metrics           🌙 Dark/Light Mode                   │
│  🔧 Admin Interface        📱 Responsive Design                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                    │                       │
                    ▼                       ▼
┌─────────────────┐              ┌─────────────────┐
│  Backend        │              │  ETL Service    │
│  Service        │◄────────────►│  (FastAPI)      │
│  (FastAPI)      │              │  Port: 8000     │
│  Port: 3001     │              │                 │
│                 │              │ • Data Extract  │
│ • Authentication│              │ • Job Control   │
│ • User Mgmt     │              │ • Orchestration │
│ • Session Mgmt  │              │ • Recovery      │
│ • API Gateway   │              │ • Admin APIs    │
│ • Client Mgmt   │              │                 │
└─────────────────┘              └─────────────────┘
                    │                       │
                    └───────────────────────┼───────────────────────┐
                                           │                       │
                                           ▼                       ▼
                        ┌─────────────────┐    ┌─────────────────┐
                        │  PostgreSQL     │───►│  PostgreSQL     │
                        │  PRIMARY        │    │  REPLICA        │
                        │  Port: 5432     │    │  Port: 5433     │
                        │                 │    │                 │
                        │ • Write Ops     │    │ • Read Ops      │
                        │ • User Mgmt     │    │ • Analytics     │
                        │ • Job Control   │    │ • Dashboards    │
                        │ • Auth/Sessions │    │ • Reports       │
                        └─────────────────┘    └─────────────────┘
                                │                       ▲
                                └───WAL Streaming───────┘
```

### Service Responsibilities

#### Frontend Application (Port 3000)
- **Executive Dashboards**: C-level friendly visualizations and KPIs
- **DORA Metrics**: Lead time, deployment frequency, change failure rate, MTTR
- **User Interface**: Responsive design with client-specific branding
- **Authentication Flow**: JWT token management and session handling
- **Real-time Updates**: WebSocket integration for live data

#### Backend Service (Port 3001)
- **Authentication Hub**: Centralized JWT-based authentication
- **User Management**: Registration, login, session management, RBAC
- **API Gateway**: Unified interface for frontend and ETL service
- **Client Management**: Multi-tenant client isolation and configuration
- **Analytics APIs**: DORA metrics, GitHub analytics, portfolio insights

#### ETL Service (Port 8000)
- **Data Processing**: Extract, transform, load operations
- **Job Orchestration**: Smart scheduling with recovery strategies
- **Integration Management**: Jira, GitHub, and custom data sources
- **Real-time Monitoring**: WebSocket updates and progress tracking
- **Admin Interface**: Configuration and management tools

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
```sql
-- Multi-tenant client management
clients (id, name, active, created_at, last_updated_at)

-- User accounts with RBAC
users (id, client_id, email, password_hash, role, active)

-- Session tracking
user_sessions (id, user_id, client_id, token_hash, active, created_at)

-- Client-specific configurations
system_settings (id, client_id, setting_key, setting_value, setting_type)
```

#### Integration Tables
```sql
-- API connection configurations
integrations (id, client_id, integration_type, config_data, active)

-- Project metadata
jira_projects (id, client_id, integration_id, project_key, project_name)

-- Repository tracking
github_repositories (id, client_id, integration_id, repo_name, repo_url)
```

#### Analytics Tables
```sql
-- Pull request data and metrics
github_pull_requests (id, client_id, repo_id, pr_number, title, state, created_at, merged_at)

-- Issue tracking and analysis
jira_issues (id, client_id, project_id, issue_key, summary, status, created_date)

-- Calculated DORA metrics
dora_metrics (id, client_id, metric_type, metric_value, calculation_date)
```

## 🐳 Docker Architecture

### Development Environment

#### Database Services (docker-compose.db.yml)
```yaml
services:
  postgres-primary:
    image: postgres:17
    environment:
      POSTGRES_DB: pulse_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: pulse
    ports:
      - "5432:5432"
    volumes:
      - postgres_primary_data:/var/lib/postgresql/data
      - ./docker/postgres/primary:/docker-entrypoint-initdb.d

  postgres-replica:
    image: postgres:17
    environment:
      POSTGRES_PRIMARY_HOST: postgres-primary
      POSTGRES_REPLICATION_USER: replicator
      POSTGRES_REPLICATION_PASSWORD: replicator_password
    ports:
      - "5433:5432"
    volumes:
      - postgres_replica_data:/var/lib/postgresql/data
      - ./docker/postgres/replica:/docker-entrypoint-initdb.d
    depends_on:
      - postgres-primary
```

#### Application Services (docker-compose.yml)
```yaml
services:
  backend-service:
    build: ./services/backend-service
    ports:
      - "3001:3001"
    environment:
      - DATABASE_URL=postgresql://postgres:pulse@postgres-primary:5432/pulse_db
      - DATABASE_REPLICA_URL=postgresql://postgres:pulse@postgres-replica:5432/pulse_db
    depends_on:
      - postgres-primary
      - postgres-replica

  etl-service:
    build: ./services/etl-service
    ports:
      - "8000:8000"
    environment:
      - CLIENT_NAME=${CLIENT_NAME}
      - DATABASE_URL=postgresql://postgres:pulse@postgres-primary:5432/pulse_db
    depends_on:
      - postgres-primary
      - backend-service

  frontend-app:
    build: ./services/frontend-app
    ports:
      - "3000:3000"
    environment:
      - VITE_BACKEND_URL=http://backend-service:3001
      - VITE_ETL_URL=http://etl-service:8000
    depends_on:
      - backend-service
```

### Production Environment

#### Multi-Client Configuration
```yaml
# docker-compose.multi-client.yml
services:
  # Multiple ETL instances for different clients
  etl-wex:
    build: ./services/etl-service
    environment:
      - CLIENT_NAME=WEX
      - DATABASE_URL=postgresql://postgres:pulse@postgres-primary:5432/pulse_db
    ports:
      - "8000:8000"

  etl-techcorp:
    build: ./services/etl-service
    environment:
      - CLIENT_NAME=TechCorp
      - DATABASE_URL=postgresql://postgres:pulse@postgres-primary:5432/pulse_db
    ports:
      - "8001:8000"

  # Load balancer for frontend
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - frontend-app
      - backend-service
```

## 🔄 Data Flow Architecture

### Request Flow

#### Authentication Flow
```
1. User Login → Frontend
2. Frontend → Backend Service (POST /api/v1/auth/login)
3. Backend → Primary Database (validate credentials)
4. Backend → Frontend (JWT token + user data)
5. Frontend stores token for subsequent requests
```

#### Data Processing Flow
```
1. ETL Job Trigger → ETL Service
2. ETL Service → External APIs (Jira/GitHub)
3. ETL Service → Primary Database (store raw data)
4. ETL Service → Data Processing (transform & analyze)
5. ETL Service → Primary Database (store processed data)
6. Primary Database → Replica Database (streaming replication)
7. Frontend → Backend Service → Replica Database (read analytics)
```

#### Real-time Updates Flow
```
1. ETL Job Progress → WebSocket Manager
2. WebSocket Manager → Connected Clients (real-time updates)
3. Frontend receives updates → UI refresh
4. Dashboard updates without page reload
```

### Integration Architecture

#### External API Integration
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  External APIs  │───►│  ETL Service    │───►│  PostgreSQL     │
│                 │    │                 │    │                 │
│ • Jira Cloud    │    │ • Rate Limiting │    │ • Normalized    │
│ • GitHub API    │    │ • Error Handling│    │   Schema        │
│ • Custom APIs   │    │ • Data Transform│    │ • Client        │
│                 │    │ • Validation    │    │   Isolation     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Deployment Strategies

### Development Deployment
- **Local Development**: Manual service startup with hot reload
- **Docker Development**: Containerized services with volume mounts
- **Database**: Single PostgreSQL instance or primary-replica setup

### Staging Deployment
- **Container Orchestration**: Docker Compose with production-like configuration
- **Database**: Primary-replica setup with backup strategies
- **Load Testing**: Performance validation and bottleneck identification

### Production Deployment
- **Container Platform**: Kubernetes or Docker Swarm
- **Database**: High-availability PostgreSQL cluster
- **Load Balancing**: Nginx or cloud load balancer
- **SSL/TLS**: Automated certificate management
- **Monitoring**: Comprehensive logging and metrics collection

## 🔧 Configuration Management

### Environment-Based Configuration
- **Development**: Local .env files with development settings
- **Staging**: Environment variables with staging configurations
- **Production**: Secure secret management with production settings

### Client-Specific Configuration
- **Database Storage**: Client settings stored in system_settings table
- **Runtime Configuration**: Dynamic configuration loading per client
- **Feature Flags**: Client-specific feature enablement

### Service Discovery
- **Development**: Hardcoded service URLs
- **Production**: Service mesh or container orchestration discovery

---

This architecture provides a robust, scalable, and secure foundation for the Pulse Platform, supporting enterprise-grade multi-tenancy while maintaining high performance and reliability.
