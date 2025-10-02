# Phase 1: Quick Reference Guide

**Last Updated**: 2025-09-30  
**Duration**: 1 week (revised from 2 weeks)

## ✅ What We're Doing

1. **Verify RabbitMQ** - Already configured, just verify it works
2. **Add 1 Database Table** - `raw_extraction_data` in migration 0001
3. **Copy Unified Models** - From etl-service to backend-service
4. **Create Queue Manager** - RabbitMQ integration in backend-service
5. **Create Raw Data APIs** - Store/retrieve complete API responses
6. **Test Everything** - Ensure all components work together

## ❌ What We're NOT Doing

1. ❌ NO `etl_job_queue` table - RabbitMQ handles queue state
2. ❌ NO `/api` subfolder - `app/etl/` is already all APIs
3. ❌ NO separate `etl_schemas.py` - Define schemas inline
4. ❌ NO item-by-item queuing - Use batch approach
5. ❌ NO modifying ETL service - That's Phase 2

## 🎯 Key Architecture Decisions

### Database vs RabbitMQ

| Component | Purpose | Stores |
|-----------|---------|--------|
| **Database** | Data storage | Complete API responses (large) |
| **RabbitMQ** | Work queue | Just IDs (tiny) |

### Batch Processing

```
Jira API returns 1000 issues
↓
Store 1 record in database (all 1000 issues in JSONB)
↓
Queue 1 message in RabbitMQ (just the record ID)
↓
Worker retrieves from database and processes batch
```

**NOT** 1000 individual records/messages!

## 📁 File Structure

```
services/backend-service/app/
├── models/
│   └── unified_models.py          # ✅ COPY from etl-service
├── etl/
│   ├── __init__.py
│   ├── router.py                  # ✅ UPDATE - add raw_data router
│   ├── wits.py                    # ✅ Existing
│   ├── statuses.py                # ✅ Existing
│   ├── integrations.py            # ✅ Existing
│   ├── qdrant.py                  # ✅ Existing
│   ├── raw_data.py                # 🔄 NEW - Raw data APIs
│   ├── queue/
│   │   ├── __init__.py
│   │   └── queue_manager.py       # 🔄 NEW - RabbitMQ integration
│   ├── transformers/              # 🔄 NEW - Phase 2
│   │   └── __init__.py
│   └── loaders/                   # 🔄 NEW - Phase 2
│       └── __init__.py
```

## 🗄️ Database Schema

**Only ONE table needed**:

```sql
CREATE TABLE raw_extraction_data (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    integration_id INTEGER NOT NULL REFERENCES integrations(id),
    entity_type VARCHAR(50) NOT NULL,     -- 'jira_issues_batch'
    external_id VARCHAR(255),             -- 'batch_1'
    raw_data JSONB NOT NULL,              -- Complete API response
    extraction_metadata JSONB,            -- Extraction context
    processing_status VARCHAR(20) DEFAULT 'pending',
    error_details JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    active BOOLEAN DEFAULT TRUE
);
```

**Add to**: `services/backend-service/scripts/migrations/0001_initial_db_schema.py`

## 🐰 RabbitMQ Configuration

**Already configured in docker-compose.yml**:
- Port 5672: AMQP
- Port 15672: Management UI
- User: etl_user
- Password: etl_password
- VHost: pulse_etl

**Queue Topology**:
- `extract_queue` - Extraction jobs
- `transform_queue` - Transform jobs (Phase 1)
- `load_queue` - Load jobs (Phase 2)

## 🔌 API Endpoints

All under `/app/etl` prefix:

```python
POST   /app/etl/raw-data/store        # Store raw API response
GET    /app/etl/raw-data              # Retrieve raw data
PUT    /app/etl/raw-data/{id}/status  # Update processing status
```

## 📝 Implementation Steps

### 1. Database (1 hour)
```bash
# Edit migration file
nano services/backend-service/scripts/migrations/0001_initial_db_schema.py
# Add raw_extraction_data table

# Run migration
cd services/backend-service
python scripts/migration_runner.py --drop-all
python scripts/migration_runner.py --apply-all
```

### 2. Copy Models (1 hour)
```bash
cp services/etl-service/app/models/unified_models.py \
   services/backend-service/app/models/unified_models.py
```

### 3. Create Directories (15 min)
```bash
cd services/backend-service/app/etl
mkdir -p queue transformers loaders
touch queue/__init__.py transformers/__init__.py loaders/__init__.py
```

### 4. Implement Raw Data APIs (2 days)
Create `services/backend-service/app/etl/raw_data.py`:
- Define Pydantic schemas inline
- Implement 3 endpoints
- Add to router

### 5. Implement Queue Manager (2 days)
Create `services/backend-service/app/etl/queue/queue_manager.py`:
- RabbitMQ connection
- Queue topology setup
- Publish methods

### 6. Testing (1 day)
- Test all APIs
- Test queue publishing
- Verify database records
- Check RabbitMQ UI

## ✅ Success Criteria

- [ ] `raw_extraction_data` table exists
- [ ] `unified_models.py` copied and working
- [ ] RabbitMQ accessible at http://localhost:15672
- [ ] Can store 1000 items in 1 database record
- [ ] Can queue just the ID in RabbitMQ
- [ ] All 3 raw data APIs working
- [ ] Queue manager can publish messages
- [ ] All tests passing

## 🚀 Quick Commands

```bash
# Start RabbitMQ
docker-compose up -d rabbitmq

# Access RabbitMQ UI
open http://localhost:15672
# Login: etl_user / etl_password

# Run migration
cd services/backend-service
python scripts/migration_runner.py --drop-all
python scripts/migration_runner.py --apply-all

# Install dependencies
pip install pika
pip freeze > requirements.txt

# Test backend
cd services/backend-service
python run_backend.py
```

## 📊 Timeline

| Task | Duration |
|------|----------|
| Verify RabbitMQ | 1 hour |
| Database Schema | 1 hour |
| Copy Models | 1 hour |
| Directory Structure | 15 min |
| Raw Data APIs | 2 days |
| Queue Manager | 2 days |
| Router Update | 1 hour |
| Testing | 1 day |
| **TOTAL** | **1 week** |

## 🎯 Key Principles

1. **Batch Processing**: 1 API call = 1 database record = 1 queue message
2. **Separation**: Database stores data, RabbitMQ queues work
3. **Small Messages**: Queue only IDs, not full data
4. **Debugging**: Complete API responses preserved
5. **Reprocessing**: Can retry without re-extracting

## 📚 Related Documents

- [Phase 1 Full Details](phase_1_queue_infrastructure.md)
- [Phase 1 Clarifications](PHASE_1_CLARIFICATIONS.md)
- [Phase 1 Quick Start](phase_1_quick_start.md)
- [Main README](README.md)

