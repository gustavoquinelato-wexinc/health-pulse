# Architecture Guide

**Pulse Platform System Architecture & Design**

This document provides a comprehensive overview of the Pulse Platform's architecture, including system topology, multi-tenancy design, database architecture, and deployment configurations.

## 🏗️ System Architecture Overview

### Four-Tier Architecture

Pulse Platform follows a modern microservices architecture with centralized authentication and clear separation of concerns:

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

#### Auth Service (Port 4000)
- **Centralized Authentication**: OAuth-like authorization flow
- **Cross-Domain SSO**: Single sign-on across all services
- **Provider Abstraction**: Local database and OKTA integration ready
- **Token Generation**: JWT token creation and validation
- **Session Coordination**: Cross-service session management

#### Backend Service (Port 3001)
- **User Management**: Registration, RBAC, user CRUD operations
- **API Gateway**: Unified interface for frontend and ETL service
- **Token Validation**: JWT token verification with auth service
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