# Updated ETL Architecture Overview

**Document Version**: 1.1  
**Date**: 2025-09-26  
**Status**: REVISED BASED ON FEEDBACK  

## 🎯 Revised Architecture

Based on your feedback, here's the updated, simplified architecture:

### **Service Architecture (No Load Balancer)**

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Frontend      │  │   Backend       │  │   ETL Service   │
│   (React SPA)   │  │   (FastAPI)     │  │   (FastAPI)     │
│   Port 3000     │  │   Port 3001     │  │   Port 8000     │
│                 │  │                 │  │                 │
│ • Job Dashboard │  │ • Authentication│  │ • Extract Only  │
│ • Progress UI   │  │ • Transform APIs│  │ • Raw Storage   │
│ • Settings      │  │ • Load APIs     │  │ • Queue Workers │
│ • Real-time     │  │ • ETL Module    │  │ • Integrations  │
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
│  │ Primary     │  │ Cache       │  │ Vector DB   │        │
│  │ Port 5432   │  │ Port 6379   │  │ Port 6333   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## 🏗️ Backend Service ETL Module Structure

Instead of creating a separate backend service, we add an ETL module to the existing backend service:

```
services/backend-service/app/
├── ai/                    # Existing AI module
│   ├── providers/
│   ├── query_processor.py
│   └── ...
├── etl/                   # NEW ETL module
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── raw_data.py    # Raw data management
│   │   ├── transform.py   # Transform APIs
│   │   ├── load.py        # Load APIs
│   │   └── pipeline.py    # Pipeline orchestration
│   ├── transformers/
│   │   ├── __init__.py
│   │   ├── jira_transformer.py
│   │   └── github_transformer.py
│   ├── loaders/
│   │   ├── __init__.py
│   │   ├── work_item_loader.py
│   │   └── pr_loader.py
│   ├── queue/
│   │   ├── __init__.py
│   │   └── queue_manager.py
│   └── models/
│       ├── __init__.py
│       └── etl_schemas.py
├── api/                   # Existing API routes
├── auth/                  # Existing auth
├── core/                  # Existing core
└── models/                # Existing models
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
