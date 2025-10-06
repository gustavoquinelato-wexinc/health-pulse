# Health Pulse Platform - Architecture Diagrams

This document contains comprehensive visual architecture diagrams for the Health Pulse platform using Mermaid syntax. These diagrams can be rendered in any Mermaid-compatible viewer or documentation system.

## 1. Complete Platform Architecture

```mermaid
graph TB
    %% Frontend Layer
    subgraph "Frontend Layer"
        FA[Frontend App<br/>React + TypeScript<br/>Port: 5173]
        ETL[ETL Frontend<br/>React + TypeScript<br/>Port: 3333]
    end
    
    %% Service Layer
    subgraph "Service Layer"
        BS[Backend Service<br/>FastAPI<br/>Port: 3001]
        AS[Auth Service<br/>FastAPI<br/>Port: 4000]
        ETLS[ETL Service<br/>LEGACY<br/>Port: 8000]
    end
    
    %% Data Layer
    subgraph "Data Layer"
        PG[(PostgreSQL<br/>Primary: 5432<br/>Replica: 5433)]
        RD[(Redis Cache<br/>Port: 6379)]
        RMQ[RabbitMQ<br/>AMQP: 5672<br/>Management: 15672]
        QD[(Qdrant Vector DB<br/>HTTP: 6333<br/>gRPC: 6334)]
    end
    
    %% Queue Workers
    subgraph "Background Workers"
        EW[Extract Worker]
        TW[Transform Worker]
        LW[Load Worker]
        VW[Vector Worker]
    end
    
    %% Connections
    FA --> BS
    ETL --> BS
    BS --> AS
    BS --> PG
    BS --> RD
    BS --> RMQ
    BS --> QD
    
    RMQ --> EW
    RMQ --> TW
    RMQ --> LW
    RMQ --> VW
    
    EW --> PG
    TW --> PG
    LW --> PG
    VW --> QD
    
    %% Legacy connections (dashed)
    ETLS -.-> PG
    ETLS -.-> RD
    
    %% Styling
    classDef frontend fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef service fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef data fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef worker fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef legacy fill:#ffebee,stroke:#c62828,stroke-width:2px,stroke-dasharray: 5 5
    
    class FA,ETL frontend
    class BS,AS service
    class PG,RD,RMQ,QD data
    class EW,TW,LW,VW worker
    class ETLS legacy
```

## 2. ETL Queue-Based Processing Pipeline

```mermaid
graph LR
    %% External Sources
    subgraph "External Sources"
        JIRA[Jira API<br/>Issues & Custom Fields]
        GH[GitHub API<br/>PRs & Repositories]
        AHA[Aha! API<br/>Features]
    end
    
    %% ETL Frontend
    subgraph "ETL Management"
        UI[ETL Frontend<br/>Port: 3333<br/>• Job Dashboard<br/>• Custom Fields UI<br/>• Progress Tracking]
    end
    
    %% Backend ETL
    subgraph "Backend ETL Module"
        API[Backend Service<br/>/app/etl/*<br/>• Job Control<br/>• Field Discovery<br/>• Queue Management]
    end
    
    %% Queue System
    subgraph "RabbitMQ Queues (Port 5672)"
        EQ[Extract Queue<br/>etl.extract]
        TQ[Transform Queue<br/>etl.transform]
        LQ[Load Queue<br/>etl.load]
        VQ[Vector Queue<br/>etl.vectorization]
        DLQ[Dead Letter Queue<br/>etl.dlq]
    end
    
    %% Workers
    subgraph "Background Workers"
        EW[Extract Worker<br/>• API Calls<br/>• Rate Limiting<br/>• Raw Storage]
        TW[Transform Worker<br/>• Data Cleaning<br/>• Custom Fields<br/>• Validation]
        LW[Load Worker<br/>• Bulk Insert<br/>• Relationships<br/>• Optimization]
        VW[Vector Worker<br/>• Embeddings<br/>• Qdrant Storage<br/>• Semantic Index]
    end
    
    %% Storage
    subgraph "Data Storage"
        RAW[(Raw Data<br/>raw_extraction_data)]
        FINAL[(Final Tables<br/>work_items, prs<br/>statuses, wits)]
        VECTOR[(Vector DB<br/>Qdrant 6333<br/>Embeddings)]
    end
    
    %% Flow
    UI --> API
    API --> EQ
    
    JIRA --> EW
    GH --> EW
    AHA --> EW
    
    EQ --> EW
    EW --> RAW
    EW --> TQ
    
    TQ --> TW
    TW --> LQ
    
    LQ --> LW
    LW --> FINAL
    LW --> VQ
    
    VQ --> VW
    VW --> VECTOR
    
    %% Error handling
    EW -.-> DLQ
    TW -.-> DLQ
    LW -.-> DLQ
    VW -.-> DLQ
    
    %% Progress updates
    EW -.-> UI
    TW -.-> UI
    LW -.-> UI
    VW -.-> UI
    
    %% Styling
    classDef ui fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef api fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef queue fill:#fff8e1,stroke:#f57c00,stroke-width:2px
    classDef worker fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    classDef storage fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef external fill:#f1f8e9,stroke:#689f38,stroke-width:2px
    
    class UI ui
    class API api
    class EQ,TQ,LQ,VQ,DLQ queue
    class EW,TW,LW,VW worker
    class RAW,FINAL,VECTOR storage
    class JIRA,GH,AHA external
```

## 3. Dynamic Custom Fields Management System

```mermaid
graph TD
    %% Discovery Phase
    subgraph "Field Discovery"
        PROJ[Project Selection<br/>Jira Project Key]
        API_CALL[Jira createmeta API<br/>/rest/api/3/issue/createmeta]
        DISCOVER[Field Discovery<br/>• Custom Fields<br/>• Field Types<br/>• Allowed Values]
    end

    %% UI Configuration
    subgraph "UI Configuration"
        FIELDS_UI[Custom Fields UI<br/>• Drag & Drop<br/>• Field Mapping<br/>• Priority Setting]
        MAP_CONFIG[Mapping Configuration<br/>• 20 Dedicated Columns<br/>• JSON Overflow<br/>• Field Priorities]
    end

    %% Storage Strategy
    subgraph "Storage Strategy"
        DEDICATED[Dedicated Columns<br/>custom_field_01<br/>custom_field_02<br/>...<br/>custom_field_20]
        OVERFLOW[JSON Overflow<br/>custom_fields_overflow<br/>JSONB Column<br/>Unlimited Fields]
    end

    %% Processing Pipeline
    subgraph "Transform Processing"
        EXTRACT_RAW[Raw Data<br/>Jira API Response]
        APPLY_MAPPING[Apply UI Mappings<br/>• Field Transformation<br/>• Type Conversion<br/>• Validation]
        STORE_FINAL[Final Storage<br/>• Optimized Columns<br/>• Indexed JSON<br/>• Query Performance]
    end

    %% Database Schema
    subgraph "Database Schema"
        WORK_ITEMS[(work_items table<br/>• Standard columns<br/>• 20 custom columns<br/>• JSON overflow<br/>• GIN index)]
        MAPPINGS[(integrations table<br/>custom_field_mappings<br/>JSON configuration)]
    end

    %% Flow
    PROJ --> API_CALL
    API_CALL --> DISCOVER
    DISCOVER --> FIELDS_UI
    FIELDS_UI --> MAP_CONFIG
    MAP_CONFIG --> MAPPINGS

    EXTRACT_RAW --> APPLY_MAPPING
    MAPPINGS --> APPLY_MAPPING
    APPLY_MAPPING --> DEDICATED
    APPLY_MAPPING --> OVERFLOW
    DEDICATED --> WORK_ITEMS
    OVERFLOW --> WORK_ITEMS

    WORK_ITEMS --> STORE_FINAL

    %% Performance Benefits
    subgraph "Performance Benefits"
        FAST_QUERY[Fast Queries<br/>• Indexed columns<br/>• Direct access<br/>• No JSON parsing]
        FLEXIBLE[Unlimited Fields<br/>• JSON overflow<br/>• Dynamic schema<br/>• Future-proof]
    end

    DEDICATED --> FAST_QUERY
    OVERFLOW --> FLEXIBLE

    %% Styling
    classDef discovery fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef ui fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef storage fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
    classDef processing fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef database fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef benefits fill:#f1f8e9,stroke:#558b2f,stroke-width:2px

    class PROJ,API_CALL,DISCOVER discovery
    class FIELDS_UI,MAP_CONFIG ui
    class DEDICATED,OVERFLOW storage
    class EXTRACT_RAW,APPLY_MAPPING,STORE_FINAL processing
    class WORK_ITEMS,MAPPINGS database
    class FAST_QUERY,FLEXIBLE benefits
```

## 4. Authentication & Authorization Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend as Frontend App<br/>(Port 5173)
    participant ETL as ETL Frontend<br/>(Port 3333)
    participant Backend as Backend Service<br/>(Port 3001)
    participant Auth as Auth Service<br/>(Port 4000)
    participant DB as PostgreSQL<br/>(Port 5432)

    %% Initial Login
    User->>Frontend: Access Application
    Frontend->>Auth: POST /auth/login<br/>{username, password}
    Auth->>DB: Validate Credentials
    DB-->>Auth: User Data
    Auth->>Auth: Generate JWT Token
    Auth-->>Frontend: JWT Token + User Info
    Frontend->>Frontend: Store Token in Memory

    %% Cross-Service Navigation
    User->>Frontend: Navigate to ETL
    Frontend->>ETL: Redirect with Token
    ETL->>ETL: Store Token

    %% API Calls with Authentication
    ETL->>Backend: GET /app/etl/jobs<br/>Authorization: Bearer {token}
    Backend->>Auth: Validate Token
    Auth-->>Backend: Token Valid + User Claims
    Backend->>DB: Query ETL Jobs
    DB-->>Backend: Job Data
    Backend-->>ETL: ETL Jobs Response

    %% Token Refresh
    Note over Frontend,Auth: Token Near Expiry
    Frontend->>Auth: POST /auth/refresh<br/>Authorization: Bearer {token}
    Auth->>Auth: Validate & Generate New Token
    Auth-->>Frontend: New JWT Token
    Frontend->>Frontend: Update Stored Token

    %% Multi-Tenant Access
    User->>Backend: API Request with Tenant Context
    Backend->>Auth: Validate Token + Tenant
    Auth->>DB: Check Tenant Permissions
    DB-->>Auth: Tenant Access Rights
    Auth-->>Backend: Authorized for Tenant
    Backend->>DB: Query with tenant_id filter
    DB-->>Backend: Tenant-Specific Data
    Backend-->>User: Filtered Response

    %% Error Handling
    User->>Backend: API Request (Invalid Token)
    Backend->>Auth: Validate Token
    Auth-->>Backend: 401 Unauthorized
    Backend-->>User: 401 Response
    User->>Frontend: Redirect to Login
```

## 4.1. Service-to-Service Authentication Flow

```mermaid
graph TD
    %% Frontend Layer
    subgraph "Frontend Applications"
        FA[Frontend App<br/>React + TypeScript<br/>Port: 5173]
        ETL[ETL Frontend<br/>React + TypeScript<br/>Port: 3333]
    end

    %% Service Layer
    subgraph "Backend Services"
        BS[Backend Service<br/>FastAPI<br/>Port: 3001]
        AS[Auth Service<br/>FastAPI<br/>Port: 4000]
    end

    %% ETL Processing (Internal to Backend)
    subgraph "ETL Processing (Internal)"
        ETL_API[ETL API Endpoints<br/>/app/etl/*<br/>• Custom Fields<br/>• Jobs<br/>• Integrations]
        ETL_WORKERS[ETL Workers<br/>• Transform Worker<br/>• Extract Worker<br/>• Load Worker]
    end

    %% Data Layer
    subgraph "Data & Queue Layer"
        PG[(PostgreSQL<br/>Port: 5432)]
        RMQ[RabbitMQ<br/>Port: 5672]
    end

    %% Authentication Flows
    FA -->|1. JWT Token| BS
    ETL -->|2. JWT Token| BS
    BS -->|3. Validate Token| AS
    AS -->|4. User Data| BS

    %% Internal ETL Processing (No Auth Required)
    BS -->|5. Internal Call| ETL_API
    ETL_API -->|6. Queue Message| RMQ
    RMQ -->|7. Process Data| ETL_WORKERS
    ETL_WORKERS -->|8. Direct DB Access<br/>System Credentials| PG

    %% No Direct Communication
    ETL -.->|❌ NO DIRECT COMM| AS
    ETL_API -.->|❌ NO DIRECT COMM| AS
    ETL_WORKERS -.->|❌ NO AUTH NEEDED| AS

    %% Annotations
    BS -->|9. Business Logic| PG

    %% Styling
    classDef frontend fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef service fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef etl fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
    classDef data fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef nocomm fill:#ffebee,stroke:#c62828,stroke-width:2px,stroke-dasharray: 5 5

    class FA,ETL frontend
    class BS,AS service
    class ETL_API,ETL_WORKERS etl
    class PG,RMQ data
```

### Authentication Types Explained:

#### 🌐 **User Authentication (Interactive)**
- **Path**: Frontend → Backend Service → Auth Service
- **Purpose**: Validate user requests from UI applications
- **Token**: JWT in Authorization header
- **Flow**: `ETL Frontend → Backend /app/etl/* → Auth Service validation`

#### 🤖 **System Authentication (Workers)**
- **Path**: RabbitMQ Workers → Database (Direct)
- **Purpose**: Background processing without user context
- **Credentials**: System database credentials
- **No Auth Service**: Workers don't need user authentication

#### 🔧 **Internal Processing (No Auth)**
- **Path**: Backend Service → ETL API Endpoints (Internal)
- **Purpose**: Internal service communication
- **Security**: Same process, no network calls
- **Context**: User context passed through function calls

## 5. Database Schema Overview

```mermaid
erDiagram
    TENANTS {
        int id PK
        string name
        string domain
        boolean active
        timestamp created_at
        timestamp updated_at
    }

    USERS {
        int id PK
        int tenant_id FK
        string username
        string email
        string password_hash
        string role
        boolean active
        timestamp created_at
    }

    INTEGRATIONS {
        int id PK
        int tenant_id FK
        string name
        string type
        string base_url
        text credentials
        jsonb custom_field_mappings
        boolean active
        timestamp created_at
    }

    ETL_JOBS {
        int id PK
        int tenant_id FK
        int integration_id FK
        string name
        string status
        jsonb config
        timestamp last_run_started_at
        timestamp last_success_at
        timestamp created_at
    }

    RAW_EXTRACTION_DATA {
        int id PK
        int tenant_id FK
        int integration_id FK
        string entity_type
        string external_id
        jsonb raw_data
        timestamp extracted_at
    }

    WORK_ITEMS {
        int id PK
        int tenant_id FK
        int integration_id FK
        string external_id
        string title
        string status
        string custom_field_01
        string custom_field_02
        string custom_field_20
        jsonb custom_fields_overflow
        timestamp created_at
        timestamp updated_at
    }

    PRS {
        int id PK
        int tenant_id FK
        int integration_id FK
        string external_id
        string title
        string state
        string author
        timestamp created_at
        timestamp merged_at
    }

    VECTORIZATION_QUEUE {
        int id PK
        int tenant_id FK
        string entity_type
        int entity_id
        string status
        text error_message
        timestamp queued_at
        timestamp processed_at
    }

    %% Relationships
    TENANTS ||--o{ USERS : "has"
    TENANTS ||--o{ INTEGRATIONS : "has"
    TENANTS ||--o{ ETL_JOBS : "has"
    TENANTS ||--o{ RAW_EXTRACTION_DATA : "has"
    TENANTS ||--o{ WORK_ITEMS : "has"
    TENANTS ||--o{ PRS : "has"
    TENANTS ||--o{ VECTORIZATION_QUEUE : "has"

    INTEGRATIONS ||--o{ ETL_JOBS : "has"
    INTEGRATIONS ||--o{ RAW_EXTRACTION_DATA : "extracts_to"
    INTEGRATIONS ||--o{ WORK_ITEMS : "creates"
    INTEGRATIONS ||--o{ PRS : "creates"
```

## 6. Deployment Architecture

```mermaid
graph TB
    %% Load Balancer
    subgraph "Load Balancer"
        LB[NGINX/HAProxy<br/>SSL Termination<br/>Port 80/443]
    end

    %% Application Tier
    subgraph "Application Tier"
        subgraph "Frontend Services"
            FA1[Frontend App<br/>Instance 1<br/>Port 5173]
            FA2[Frontend App<br/>Instance 2<br/>Port 5174]
            ETL1[ETL Frontend<br/>Instance 1<br/>Port 3333]
            ETL2[ETL Frontend<br/>Instance 2<br/>Port 3334]
        end

        subgraph "Backend Services"
            BS1[Backend Service<br/>Instance 1<br/>Port 3001]
            BS2[Backend Service<br/>Instance 2<br/>Port 3002]
            AS1[Auth Service<br/>Instance 1<br/>Port 4000]
            AS2[Auth Service<br/>Instance 2<br/>Port 4001]
        end
    end

    %% Data Tier
    subgraph "Data Tier"
        subgraph "Primary Database"
            PG_PRIMARY[(PostgreSQL Primary<br/>Port 5432<br/>Read/Write)]
        end

        subgraph "Read Replicas"
            PG_REPLICA1[(PostgreSQL Replica 1<br/>Port 5433<br/>Read Only)]
            PG_REPLICA2[(PostgreSQL Replica 2<br/>Port 5434<br/>Read Only)]
        end

        subgraph "Cache & Queue"
            REDIS_CLUSTER[Redis Cluster<br/>Ports 6379-6384<br/>Cache & Sessions]
            RMQ_CLUSTER[RabbitMQ Cluster<br/>Ports 5672-5674<br/>Message Queue]
        end

        subgraph "Vector Database"
            QDRANT_CLUSTER[Qdrant Cluster<br/>Ports 6333-6335<br/>Vector Storage]
        end
    end

    %% Background Processing
    subgraph "Background Workers"
        WORKER_POOL[Worker Pool<br/>• Extract Workers<br/>• Transform Workers<br/>• Load Workers<br/>• Vector Workers]
    end

    %% Connections
    LB --> FA1
    LB --> FA2
    LB --> ETL1
    LB --> ETL2

    FA1 --> BS1
    FA2 --> BS2
    ETL1 --> BS1
    ETL2 --> BS2

    BS1 --> AS1
    BS2 --> AS2

    BS1 --> PG_PRIMARY
    BS2 --> PG_PRIMARY
    BS1 --> PG_REPLICA1
    BS2 --> PG_REPLICA2

    BS1 --> REDIS_CLUSTER
    BS2 --> REDIS_CLUSTER

    BS1 --> RMQ_CLUSTER
    BS2 --> RMQ_CLUSTER

    BS1 --> QDRANT_CLUSTER
    BS2 --> QDRANT_CLUSTER

    RMQ_CLUSTER --> WORKER_POOL
    WORKER_POOL --> PG_PRIMARY
    WORKER_POOL --> QDRANT_CLUSTER

    %% Replication
    PG_PRIMARY -.-> PG_REPLICA1
    PG_PRIMARY -.-> PG_REPLICA2

    %% Styling
    classDef lb fill:#ffecb3,stroke:#ff8f00,stroke-width:3px
    classDef frontend fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef backend fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef database fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef cache fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef workers fill:#fce4ec,stroke:#c2185b,stroke-width:2px

    class LB lb
    class FA1,FA2,ETL1,ETL2 frontend
    class BS1,BS2,AS1,AS2 backend
    class PG_PRIMARY,PG_REPLICA1,PG_REPLICA2 database
    class REDIS_CLUSTER,RMQ_CLUSTER,QDRANT_CLUSTER cache
    class WORKER_POOL workers
```

## How to Use These Diagrams

### Viewing Options
1. **GitHub/GitLab**: These platforms render Mermaid diagrams automatically
2. **VS Code**: Install Mermaid Preview extension
3. **Online Viewers**:
   - https://mermaid.live/
   - https://mermaid-js.github.io/mermaid-live-editor/
4. **Documentation Sites**: GitBook, Notion, Confluence support Mermaid

### Exporting
- **PNG/SVG**: Use mermaid.live or mermaid-cli
- **PDF**: Export from online viewers
- **Presentations**: Copy diagram code into presentation tools that support Mermaid

### Customization
- Modify colors by changing `classDef` definitions
- Add/remove components by editing the graph structure
- Update ports/endpoints as the system evolves

---

**File**: `docs/ARCHITECTURE_DIAGRAMS.md`
**Version**: 1.0.0
**Last Updated**: 2025-10-03
**Diagrams**: 6 comprehensive architecture diagrams
