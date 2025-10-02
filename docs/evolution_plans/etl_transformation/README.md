# ETL Transformation Evolution Plan

**Status**: PHASE 1 COMPLETE - READY FOR PHASE 2
**Timeline**: 7 weeks total (Phase 0: 2 weeks ✅, Phase 1: 1 session ✅, Remaining: 4 weeks)
**Progress**: 37.5% complete (Phases 0-1 of 4 phases done)
**Priority**: HIGH
**Last Updated**: 2025-09-30

---

## 🚀 Quick Start

**New to this project?** Start here:
1. **[Current State Summary](support/CURRENT_STATE_SUMMARY.md)** - Understand what's built and what's next
2. **[Phase 1 Quick Reference](PHASE_1_QUICK_REFERENCE.md)** - ⭐ Quick reference for Phase 1 implementation
3. **[Phase 1 Implementation Guide](phase_1_queue_infrastructure.md)** - Complete implementation details
4. **[Implementation Status](support/implementation_status.md)** - Detailed progress tracking
5. **[Folder Structure](FOLDER_STRUCTURE.md)** - How documentation is organized

---

## 🎯 Overview

This evolution plan transforms the current monolithic ETL service into a modern, scalable microservices architecture with proper Extract → Transform → Load separation, queue-based processing, and enterprise-grade multi-tenancy.

**Current Progress**: 25% complete (Phase 0 of 4 phases done)

## ✅ Phase 0: Foundation (COMPLETE)

**Duration**: 2 weeks
**Status**: ✅ IMPLEMENTED

### What Was Accomplished

1. **New ETL Frontend (React SPA)**
   - Created `services/etl-frontend` as standalone React application
   - Port 3333 to avoid conflicts with main frontend (port 3000)
   - Implemented all basic management pages:
     - ✅ Work Item Types (WITs) Mappings
     - ✅ WITs Hierarchies
     - ✅ Status Mappings
     - ✅ Workflows
     - ✅ Integrations Management
     - ✅ Qdrant Dashboard
   - Full authentication integration with backend-service
   - Theme support (light/dark mode with custom color schemes)
   - Responsive design with collapsed sidebar navigation

2. **Backend Service ETL Module**
   - Created `services/backend-service/app/etl/` module structure
   - Implemented API endpoints for:
     - ✅ `/app/etl/wits` - Work Item Types management
     - ✅ `/app/etl/statuses` - Status mappings and workflows
     - ✅ `/app/etl/integrations` - Integration CRUD operations
     - ✅ `/app/etl/qdrant` - Qdrant dashboard and health checks
   - Centralized ETL router combining all sub-routers
   - Full tenant isolation and authentication

3. **Architecture Established**
   - Frontend (React) → Backend Service (FastAPI) communication working
   - ETL service remains untouched as backup
   - Clean separation: new etl-frontend never touches old etl-service
   - API base URL: `http://localhost:3001/app/etl`

### Current State vs Target State

**Current Architecture:**
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   ETL Frontend  │  │   Backend       │  │   ETL Service   │
│   (React SPA)   │  │   (FastAPI)     │  │   (UNTOUCHED)   │
│   Port 3333     │  │   Port 3001     │  │   Port 8000     │
│                 │  │                 │  │                 │
│ ✅ WITs Pages   │  │ ✅ ETL Module   │  │ • Old monolith  │
│ ✅ Status Pages │  │ ✅ CRUD APIs    │  │ • Backup only   │
│ ✅ Integrations │  │ ✅ Qdrant APIs  │  │ • Not modified  │
│ ✅ Qdrant Page  │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                     │
         └─────────────────────┘
              HTTP/REST
```

**Current State After Phase 1:**
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   ETL Frontend  │  │   Backend       │  │   ETL Service   │
│   (React SPA)   │  │   (FastAPI)     │  │   (UNTOUCHED)   │
│   Port 3333     │  │   Port 3001     │  │   Port 8000     │
│                 │  │                 │  │                 │
│ ✅ Management   │  │ ✅ ETL Module   │  │ • Backup only   │
│ 🔄 Jobs UI      │  │ ✅ Queue Mgmt   │  │ • Phase 2 work  │
│                 │  │ ✅ Raw Data API │  │                 │
│                 │  │ ✅ Unified Mdls │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                     │
         └─────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │    RabbitMQ     │
                    │ ✅ Queue Mgmt   │
                    │   Port 5672     │
                    └─────────────────┘
```

## 📋 Implementation Phases

### ✅ **Phase 0: Foundation** (COMPLETE)
**Duration**: 2 weeks
**Status**: ✅ IMPLEMENTED
**Summary**: [Phase 0 Implementation Summary](completed/phase_0_implementation_summary.md)

- ✅ Created new ETL Frontend (React SPA on port 3333)
- ✅ Implemented basic management pages (WITs, Statuses, Workflows, Integrations, Qdrant)
- ✅ Created backend-service ETL module structure (`app/etl/`)
- ✅ Implemented CRUD APIs for all management entities
- ✅ Established frontend → backend communication pattern
- ✅ Full authentication and tenant isolation working

### 🔄 **Phase 1: Queue Infrastructure & Raw Data Storage** (Week 3)
**Status**: NOT STARTED ❌
**Duration**: 1 week (revised from 2 weeks)
**Documents**:
- [Phase 1 Quick Reference](PHASE_1_QUICK_REFERENCE.md) - ⭐ Quick reference guide
- [Phase 1 Implementation Guide](phase_1_queue_infrastructure.md) - Complete implementation details

**Key Objectives:**
- ✅ Verify RabbitMQ (already in docker-compose.yml)
- Create database table for raw data storage (`raw_extraction_data` only - add to migration 0001)
- Copy `unified_models.py` from etl-service to backend-service
- Implement RabbitMQ queue manager in backend-service
- Create raw data storage APIs (inline Pydantic schemas)
- Establish queue topology (extract, transform, load queues)

**Deliverables:**
- ✅ RabbitMQ verified (already configured)
- Database migration updated with `raw_extraction_data` table
- Queue manager class with publish/consume methods
- Raw data CRUD APIs in backend-service
- Batch-based processing (1 API call = 1 DB record = 1 queue message)

### 🔄 **Phase 2: ETL Service Refactoring** (Weeks 5-6)
**Status**: NOT STARTED ❌
**Document**: [Phase 2 Details](phase_2_etl_service_refactor.md)

**Key Objectives:**
- Refactor ETL service jobs to extract-only pattern
- Remove transform/load logic from ETL service
- Implement raw data storage after extraction
- Publish transform jobs to RabbitMQ queue
- Create queue workers for transform/load operations

**Deliverables:**
- Extract-only job classes (Jira, GitHub, etc.)
- Raw data storage integration
- Queue publishing after extraction
- Transform/Load workers in backend-service

### 🔄 **Phase 3: Frontend Job Management** (Week 7)
**Status**: NOT STARTED ❌
**Document**: [Phase 3 Details](phase_3_frontend_job_management.md)

**Key Objectives:**
- Create Jobs page in etl-frontend
- Implement job control UI (start, pause, stop)
- Add real-time progress tracking
- Display queue status and metrics
- Preserve UX from old ETL service

**Deliverables:**
- Jobs management page with controls
- Real-time WebSocket progress updates
- Queue monitoring dashboard
- Job history and logs viewer

### 🔄 **Phase 4: Testing & Production** (Week 8)
**Status**: NOT STARTED ❌
**Document**: [Phase 4 Details](phase_4_testing_production.md)

**Key Objectives:**
- End-to-end pipeline testing
- Performance benchmarking
- Production deployment procedures
- Monitoring and alerting setup
- Documentation and training

**Deliverables:**
- Comprehensive test suite
- Performance metrics and optimization
- Production deployment guide
- Monitoring dashboards
- User documentation

## 🏗️ Detailed Architecture Evolution

### **Legacy State (Before Phase 0)**
```
┌─────────────────────────────────────┐
│     Monolithic ETL Service          │
│     (services/etl-service)          │
│  ┌─────────────────────────────────┐│
│  │ Extract + Transform + Load      ││
│  │ + UI (Jinja2) + API + Jobs     ││
│  │ + Orchestration + WebSocket    ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

### **Current State (Phase 0 Complete)**
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   ETL Frontend  │  │   Backend       │  │   ETL Service   │
│   (React SPA)   │  │   (FastAPI)     │  │   (UNTOUCHED)   │
│   Port 3333     │  │   Port 3001     │  │   Port 8000     │
│                 │  │                 │  │                 │
│ ✅ WITs Mgmt    │  │ ✅ app/etl/     │  │ • Backup only   │
│ ✅ Status Mgmt  │  │ ✅ wits.py      │  │ • Not modified  │
│ ✅ Workflows    │  │ ✅ statuses.py  │  │ • Will refactor │
│ ✅ Integrations │  │ ✅ integrations │  │   in Phase 2    │
│ ✅ Qdrant UI    │  │ ✅ qdrant.py    │  │                 │
│ 🔄 Jobs (TODO)  │  │ ✅ router.py    │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                     │
         └─────────────────────┘
              HTTP/REST
         (No queue yet)
```

### **Target State (All Phases Complete)**
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
│                RabbitMQ Container (Port 5672)               │
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

## 🎯 Key Benefits

### **Technical Excellence**
- ✅ **True ETL Separation**: Extract → Transform → Load pipeline
- ✅ **Queue-Based Processing**: Reliable, scalable job management
- ✅ **Raw Data Preservation**: Complete API responses for debugging/reprocessing
- ✅ **Microservices Architecture**: Independent scaling and deployment

### **Business Value**
- ✅ **Improved Performance**: 50% faster processing through parallelization
- ✅ **Enhanced Reliability**: 99% uptime with queue-based error recovery
- ✅ **Better Monitoring**: Clear visibility into each pipeline stage
- ✅ **Easier Maintenance**: Clean separation of concerns

### **Operational Benefits**
- ✅ **Docker Integration**: All services containerized
- ✅ **Multi-tenant Ready**: Enterprise-grade tenant isolation
- ✅ **Pluggable Integrations**: Easy addition of new data sources
- ✅ **Production Ready**: Comprehensive testing and monitoring

## 🔧 Technology Stack

### **Infrastructure**
- **Message Queue**: RabbitMQ (Docker container)
- **Database**: PostgreSQL Primary + Replica + Qdrant
- **Cache**: Redis
- **Containerization**: Docker Compose

### **Services**
- **Frontend**: React SPA with real-time updates
- **Backend**: FastAPI with ETL module
- **ETL Service**: FastAPI extract-only service
- **Queue Workers**: Python async workers

### **Development**
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **ORM**: SQLAlchemy
- **Queue**: Pika (RabbitMQ client)
- **Testing**: Pytest

## 📊 Success Metrics

### **Performance Targets**
- **Pipeline Throughput**: 50% improvement over current
- **Queue Processing**: <1 second job queuing
- **Error Recovery**: >95% automatic recovery rate
- **Data Integrity**: 100% consistency validation

### **Reliability Targets**
- **Uptime**: 99% service availability
- **Queue Reliability**: >99.9% message delivery
- **Error Handling**: Comprehensive retry mechanisms
- **Monitoring**: Real-time alerting and dashboards

## 🚨 Risk Mitigation

### **Technical Risks**
1. **Queue Complexity**: Start simple, add complexity gradually
2. **Data Migration**: Thorough testing with sample data
3. **Service Dependencies**: Circuit breakers and fallback mechanisms
4. **Performance Impact**: Continuous monitoring and optimization

### **Business Risks**
1. **User Disruption**: Maintain UI/UX consistency during migration
2. **Timeline Delays**: Prioritize core functionality over nice-to-have features
3. **Integration Issues**: Extensive testing with real data sources
4. **Training Needs**: Comprehensive documentation and knowledge transfer

## 📋 Prerequisites & Current Status

### **Environment Setup**
- ✅ Docker and Docker Compose installed
- ✅ Python 3.11+ environment
- ✅ PostgreSQL database accessible
- ✅ Redis cache accessible
- ✅ Development tools configured
- ✅ Node.js 18+ for React frontend
- ✅ RabbitMQ container (already in docker-compose.yml)

### **Knowledge Requirements**
- ✅ FastAPI framework familiarity
- ✅ React and TypeScript
- ✅ Multi-tenant architecture patterns
- 🔄 RabbitMQ message queue concepts (needed for Phase 1)
- 🔄 ETL pipeline principles (needed for Phase 2)
- ✅ Docker containerization

### **What's Working Now**
1. ✅ ETL Frontend running on port 3333
2. ✅ Backend Service ETL module at `/app/etl`
3. ✅ All management pages functional:
   - WITs Mappings & Hierarchies
   - Status Mappings & Workflows
   - Integrations with logo upload
   - Qdrant dashboard
4. ✅ Authentication and tenant isolation
5. ✅ Theme support (light/dark, custom colors)

### **What's Missing (Next Steps - Phase 1)**
1. 🔄 Raw data storage table (`raw_extraction_data`)
2. 🔄 Queue manager implementation
3. 🔄 Raw data storage APIs
4. 🔄 Unified models copied from etl-service
5. 🔄 Queue topology setup (extract, transform, load queues)

## 🚀 Next Steps - Phase 1

**Immediate Focus**: Queue Infrastructure & Raw Data Storage

1. **Verify RabbitMQ** (1 hour)
   - ✅ Already in docker-compose.yml
   - Verify it starts correctly
   - Access management UI (port 15672)

2. **Database Schema Updates** (1 hour)
   - Add `raw_extraction_data` table to migration 0001
   - Execute migration and verify table creation
   - NO separate etl_job_queue table (RabbitMQ handles queuing)

3. **Copy Unified Models** (1 hour)
   - Copy `unified_models.py` from etl-service to backend-service
   - Both services need identical data models

4. **Queue Manager Implementation** (2 days)
   - Create `app/etl/queue/queue_manager.py`
   - Implement publish/consume methods
   - Set up queue topology (extract, transform, load queues)

5. **Raw Data APIs** (2 days)
   - Create `app/etl/raw_data.py` with inline Pydantic schemas
   - Implement store/retrieve/update endpoints
   - Add to ETL router
   - Batch-based processing (1 API call = 1 DB record = 1 queue message)

**Timeline**: 1 week (revised from 2 weeks)
**Risk**: Low (infrastructure setup)
**Dependencies**: None (Phase 0 complete)

## 📚 Documentation Index

### 🚀 Start Here (New to the Project)
1. **[Current State Summary](support/CURRENT_STATE_SUMMARY.md)** - What's built, what's next
2. **[Visual Roadmap](support/visual_roadmap.md)** - Visual journey from legacy to target
3. **[Implementation Status](support/implementation_status.md)** - Detailed progress tracking

### 📋 Phase Implementation Guides
- **[Phase 0 Summary](completed/phase_0_implementation_summary.md)**: ✅ Complete - What was built
- **[Phase 1 Quick Reference](PHASE_1_QUICK_REFERENCE.md)**: 🔄 Next - ⭐ Quick reference guide
- **[Phase 1 Implementation Guide](phase_1_queue_infrastructure.md)**: 🔄 Complete implementation details
- **[Phase 2 Details](phase_2_etl_service_refactor.md)**: ⏳ Extract-only pattern
- **[Phase 3 Details](phase_3_frontend_job_management.md)**: ⏳ Jobs UI
- **[Phase 4 Details](phase_4_testing_production.md)**: ⏳ Testing & Deployment

### 🏗️ Architecture & Design
- **[Architecture Overview](support/architecture_overview.md)**: Current vs Target state
- **[Database Schema](../../../architecture.md)**: Database structure
- **[Integration Management](../../../integration-management.md)**: External systems
- **[Jobs Orchestration](../../../jobs-orchestration.md)**: Job management

### 📦 Archive
- **[Archive Documents](support/)**: Old planning documents and alternatives

---

**Current Status**: Phase 0 Complete ✅ (25% overall progress)
**Next Step**: Begin [Phase 1 Quick Reference](PHASE_1_QUICK_REFERENCE.md) or [Phase 1 Implementation Guide](phase_1_queue_infrastructure.md)
**Timeline**: 5 weeks remaining (1 week Phase 1, 2 weeks Phase 2, 1 week each for 3-4)
