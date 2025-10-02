# Updated ETL Architecture Overview

**Document Version**: 2.0
**Date**: 2025-09-30
**Status**: PHASE 0 COMPLETE - UPDATED WITH CURRENT STATE
**Previous Version**: 1.1 (2025-09-26)

## 📊 Implementation Status

### ✅ Phase 0: Foundation (COMPLETE)
- **ETL Frontend**: React SPA created and running on port 3333
- **Backend ETL Module**: `app/etl/` structure with management APIs
- **Pages Implemented**: WITs, Statuses, Workflows, Integrations, Qdrant
- **Communication**: Frontend → Backend HTTP/REST working
- **Authentication**: Full tenant isolation and JWT auth

### 🔄 Next Phase: Queue Infrastructure (Phase 1)
- **RabbitMQ**: Container to be added to docker-compose
- **Raw Data Storage**: Database tables to be created
- **Queue Manager**: RabbitMQ integration to be implemented
- **Raw Data APIs**: Endpoints to be created

## 🎯 Current Architecture (Phase 0 Complete)

### **Current Service Architecture (Phase 0 Complete)**

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   ETL Frontend  │  │   Backend       │  │   ETL Service   │
│   (React SPA)   │  │   (FastAPI)     │  │   (UNTOUCHED)   │
│   Port 3333     │  │   Port 3001     │  │   Port 8000     │
│                 │  │                 │  │                 │
│ ✅ WITs Mgmt    │  │ ✅ app/etl/     │  │ • Backup only   │
│ ✅ Status Mgmt  │  │   ├── wits.py   │  │ • Not modified  │
│ ✅ Workflows    │  │   ├── statuses  │  │ • Will refactor │
│ ✅ Integrations │  │   ├── integr.   │  │   in Phase 2    │
│ ✅ Qdrant UI    │  │   ├── qdrant    │  │                 │
│ 🔄 Jobs (TODO)  │  │   └── router    │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                     │
         └─────────────────────┘
              HTTP/REST
         (No queue yet)

┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ PostgreSQL  │  │ Redis       │  │ Qdrant      │        │
│  │ Primary     │  │ Cache       │  │ Vector DB   │        │
│  │ Port 5432   │  │ Port 6379   │  │ Port 6333   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### **Target Service Architecture (All Phases Complete)**

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   ETL Frontend  │  │   Backend       │  │   ETL Service   │
│   (React SPA)   │  │   (FastAPI)     │  │   (FastAPI)     │
│   Port 3333     │  │   Port 3001     │  │   Port 8000     │
│                 │  │                 │  │                 │
│ • Management UI │  │ • app/etl/      │  │ • Extract ONLY  │
│ • Jobs Control  │  │ • Transform APIs│  │ • Raw Storage   │
│ • Progress View │  │ • Load APIs     │  │ • Queue Publish │
│ • Queue Monitor │  │ • Queue Manager │  │ • Integrations  │
│ • Real-time WS  │  │ • Workers       │  │ • No Transform  │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                RabbitMQ Container                           │
│                   Port 5672                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Extract     │  │ Transform   │  │ Load        │        │
│  │ Queue       │  │ Queue       │  │ Queue       │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ PostgreSQL  │  │ Redis       │  │ Qdrant      │        │
│  │ + Raw Data  │  │ Cache       │  │ Vector DB   │        │
│  │ Port 5432   │  │ Port 6379   │  │ Port 6333   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## 🏗️ Backend Service ETL Module Structure

### Current Structure (Phase 0 Complete)

```
services/backend-service/app/
├── ai/                    # ✅ Existing AI module
│   ├── providers/
│   ├── query_processor.py
│   └── ...
├── etl/                   # ✅ ETL module (Phase 0)
│   ├── __init__.py        # ✅ Module initialization
│   ├── router.py          # ✅ Main ETL router
│   ├── wits.py            # ✅ WITs management APIs
│   ├── statuses.py        # ✅ Status mappings & workflows
│   ├── integrations.py    # ✅ Integration CRUD
│   └── qdrant.py          # ✅ Qdrant dashboard
├── api/                   # ✅ Existing API routes
├── auth/                  # ✅ Existing auth
├── core/                  # ✅ Existing core
└── models/                # ✅ Existing models
```

### Target Structure (All Phases Complete)

```
services/backend-service/app/
├── ai/                    # ✅ Existing AI module
│   ├── providers/
│   ├── query_processor.py
│   └── ...
├── etl/                   # ETL module (expanding)
│   ├── __init__.py        # ✅ Phase 0
│   ├── router.py          # ✅ Phase 0 (will update in Phase 1)
│   ├── wits.py            # ✅ Phase 0
│   ├── statuses.py        # ✅ Phase 0
│   ├── integrations.py    # ✅ Phase 0
│   ├── qdrant.py          # ✅ Phase 0
│   ├── api/               # 🔄 Phase 1+
│   │   ├── __init__.py
│   │   ├── raw_data.py    # 🔄 Phase 1 - Raw data management
│   │   ├── transform.py   # 🔄 Phase 2 - Transform APIs
│   │   ├── load.py        # 🔄 Phase 2 - Load APIs
│   │   └── pipeline.py    # 🔄 Phase 2 - Pipeline orchestration
│   ├── queue/             # 🔄 Phase 1
│   │   ├── __init__.py
│   │   └── queue_manager.py  # 🔄 Phase 1 - RabbitMQ integration
│   ├── models/            # 🔄 Phase 1
│   │   ├── __init__.py
│   │   └── etl_schemas.py    # 🔄 Phase 1 - Pydantic schemas
│   ├── transformers/      # 🔄 Phase 2
│   │   ├── __init__.py
│   │   ├── jira_transformer.py
│   │   └── github_transformer.py
│   └── loaders/           # 🔄 Phase 2
│       ├── __init__.py
│       ├── work_item_loader.py
│       └── pr_loader.py
├── api/                   # ✅ Existing API routes
├── auth/                  # ✅ Existing auth
├── core/                  # ✅ Existing core
└── models/                # ✅ Existing models
```

## 🔄 ETL Pipeline Flow

### **1. Extract (ETL Service)**
```python
# ETL Service extracts raw data and stores it
raw_data = await jira_extractor.extract_issues()
await store_raw_data(raw_data)
await queue_transform_job(raw_data_ids)
```

### **2. Transform (Backend Service ETL Module)**
```python
# Backend Service transforms raw data
raw_records = await get_raw_data(raw_data_ids)
work_items = await jira_transformer.transform(raw_records)
await queue_load_job(work_items)
```

### **3. Load (Backend Service ETL Module)**
```python
# Backend Service loads transformed data
await work_item_loader.bulk_load(work_items)
await queue_vectorization(work_items)
```

## 🐳 Docker Integration

### **Updated docker-compose.yml**
```yaml
services:
  # ... existing services ...
  
  # RabbitMQ Message Queue for ETL Pipeline
  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    container_name: pulse-rabbitmq
    restart: unless-stopped
    ports:
      - "5672:5672"   # AMQP port
      - "15672:15672" # Management UI
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-etl_user}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-etl_password}
      RABBITMQ_DEFAULT_VHOST: ${RABBITMQ_VHOST:-pulse_etl}
    networks:
      - pulse-network
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  etl:
    # ... existing ETL service config ...
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

volumes:
  # ... existing volumes ...
  rabbitmq_data:
```

## 🔧 Environment Configuration

### **Required .env Variables**
```bash
# RabbitMQ Configuration
RABBITMQ_USER=etl_user
RABBITMQ_PASSWORD=etl_password
RABBITMQ_VHOST=pulse_etl
RABBITMQ_URL=amqp://etl_user:etl_password@localhost:5672/pulse_etl

# ETL Configuration
ETL_QUEUE_ENABLED=true
ETL_BATCH_SIZE=100
ETL_MAX_RETRIES=3
```

## 🎯 Benefits of This Approach

### **1. Simplified Architecture**
- ✅ **No Load Balancer**: Direct service communication
- ✅ **Single Backend**: ETL logic in backend service modules
- ✅ **Container Integration**: RabbitMQ as Docker container
- ✅ **Easier Maintenance**: All business logic in one service

### **2. Clean Separation of Concerns**
- ✅ **ETL Service**: Extract-only + Queue workers
- ✅ **Backend Service**: Transform + Load + APIs + AI
- ✅ **Frontend Service**: React SPA + Real-time UI
- ✅ **Message Queue**: Reliable job processing

### **3. Microservice Benefits Without Complexity**
- ✅ **Independent Scaling**: ETL service can scale separately
- ✅ **Technology Flexibility**: Different tech stacks per service
- ✅ **Fault Isolation**: ETL failures don't affect backend APIs
- ✅ **Development Efficiency**: Teams can work independently

### **4. Production Ready**
- ✅ **Docker Integration**: All services containerized
- ✅ **Queue Reliability**: RabbitMQ for robust job processing
- ✅ **Multi-tenant**: Tenant-aware queue routing
- ✅ **Monitoring**: Health checks and observability

## 🚀 Implementation Benefits

### **Development Efficiency**
- **Familiar Structure**: Similar to existing `app/ai` module
- **Code Reuse**: Leverage existing backend infrastructure
- **Single Deployment**: Backend service handles all business logic
- **Easier Testing**: All APIs in one service

### **Operational Simplicity**
- **Container Management**: Standard Docker Compose setup
- **Service Discovery**: No complex networking required
- **Monitoring**: Centralized logging and metrics
- **Deployment**: Single backend service deployment

### **Scalability Path**
- **Horizontal Scaling**: ETL service scales independently
- **Queue Scaling**: RabbitMQ clustering for high throughput
- **Database Scaling**: Existing PostgreSQL replica setup
- **Future Flexibility**: Easy to split backend if needed

This revised architecture maintains all the benefits of proper ETL separation while significantly simplifying the implementation and maintenance overhead. The ETL module in the backend service provides clean separation without the complexity of managing multiple backend services.
