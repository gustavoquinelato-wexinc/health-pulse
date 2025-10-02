# Migration 0005: ETL Jobs Autonomous Architecture

**Date**: 2025-10-02  
**Status**: Ready for execution  
**Impact**: 🔴 **BREAKING** - Old ETL service will stop working

---

## 🎯 Overview

This migration transforms the ETL system from **orchestrator-based** to **autonomous job scheduling**:

- **Before**: Central orchestrator manages job sequencing and timing
- **After**: Each job has independent scheduling with APScheduler

---

## 📋 Changes Summary

### 1. **etl_jobs Table - Complete Redesign**

#### **Removed Columns** ❌
- `execution_order` - No orchestrator, no sequencing needed
- `last_repo_sync_checkpoint` - Moved to `checkpoint_data` JSON
- `repo_processing_queue` - Moved to `checkpoint_data` JSON
- `last_pr_cursor` - Moved to `checkpoint_data` JSON
- `current_pr_node_id` - Moved to `checkpoint_data` JSON
- `last_commit_cursor` - Moved to `checkpoint_data` JSON
- `last_review_cursor` - Moved to `checkpoint_data` JSON
- `last_comment_cursor` - Moved to `checkpoint_data` JSON
- `last_review_thread_cursor` - Moved to `checkpoint_data` JSON
- `last_success_at` - Renamed to `last_run_finished_at`

#### **Added Columns** ✅
- `schedule_interval_minutes` - Normal run interval (e.g., 360 min = 6 hours)
- `retry_interval_minutes` - Fast retry interval (15 min for all jobs)
- `checkpoint_data` - Generic JSONB for job-specific recovery data
- `last_run_finished_at` - Replaces `last_success_at` (consistent naming with `last_run_started_at`)

#### **Modified Columns** 🔄
- `status` - Simplified to 4 values: `READY`, `RUNNING`, `FINISHED`, `FAILED`
  - Old values: `PENDING`, `NOT_STARTED`, `PAUSED`, `ERROR` → Converted to new values

#### **Final Schema** (14 columns)
```sql
CREATE TABLE etl_jobs (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'READY',
    schedule_interval_minutes INTEGER NOT NULL DEFAULT 360,
    retry_interval_minutes INTEGER NOT NULL DEFAULT 15,
    last_run_started_at TIMESTAMP,
    last_run_finished_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    checkpoint_data JSONB,
    integration_id INTEGER REFERENCES integrations(id),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(job_name, tenant_id),
    CHECK (status IN ('READY', 'RUNNING', 'FINISHED', 'FAILED'))
);
```

---

### 2. **Removed Tables** ❌

#### **vectorization_queue**
- **Reason**: Vectorization now integrated into transform workers
- **Impact**: No separate vectorization job needed
- **New Flow**: Extract → Transform → Load → **Vectorize** (all in one worker)

---

### 3. **Removed System Settings** ❌

Deleted from `system_settings` table (7 settings total):

#### **Orchestrator Settings** (4 settings)
- `orchestrator_interval_minutes`
- `orchestrator_enabled`
- `orchestrator_retry_enabled`
- `orchestrator_retry_interval_minutes`

**Reason**: No orchestrator anymore - each job has its own scheduling.

#### **Job-Specific Sync Settings** (2 settings)
- `jira_sync_enabled`
- `github_sync_enabled`

**Reason**: Each job now has `active` field in `etl_jobs` table.

#### **Concurrent Jobs Limit** (1 setting)
- `max_concurrent_jobs`

**Reason**: Jobs run independently now, no global concurrency limit needed.

---

### 4. **Job Configuration Changes**

#### **Jobs Seeded Per Tenant**

| Job Name | Interval | Retry | Active | Notes |
|----------|----------|-------|--------|-------|
| **Jira** | 360 min (6h) | 15 min | ✅ Yes | Active by default |
| **GitHub** | 240 min (4h) | 15 min | ✅ Yes | Active by default |
| **WEX Fabric** | 1440 min (24h) | 15 min | ❌ No | Inactive (not implemented) |
| **WEX AD** | 720 min (12h) | 15 min | ❌ No | Inactive (not implemented) |
| ~~**Vectorization**~~ | - | - | - | **REMOVED** (integrated into workers) |

---

## 🔄 Migration Steps

### **Upgrade** (Apply Migration)

```bash
cd services/backend-service
python scripts/migrate.py upgrade
```

**What happens:**
1. ✅ Backup existing `etl_jobs` data
2. ✅ Drop `vectorization_queue` table
3. ✅ Delete 7 ETL-related settings from `system_settings`
   - 4 orchestrator settings
   - 2 job-specific sync settings (jira_sync_enabled, github_sync_enabled)
   - 1 concurrent jobs limit (max_concurrent_jobs)
4. ✅ Drop and recreate `etl_jobs` table with new schema
5. ✅ Create indexes for performance
6. ✅ Seed jobs for all tenants (WEX, Apple, Google)

### **Downgrade** (Rollback Migration)

```bash
cd services/backend-service
python scripts/migrate.py rollback
```

**What happens:**
- ⚠️ **Simple rollback not possible** - schema changes are too extensive
- **Recommended approach**: Drop database and re-run migrations 0001-0004

---

## ⚠️ Breaking Changes

### **Old ETL Service Will Stop Working**

After this migration:
- ❌ Old `etl-service` orchestrator will fail (expects old schema)
- ❌ Vectorization job will not exist
- ❌ Job sequencing logic will break

### **What Still Works**

- ✅ Database schema is valid
- ✅ All data is preserved
- ✅ Integrations are unchanged
- ✅ New ETL architecture can start fresh

---

## 🚀 Next Steps After Migration

### 1. **Implement Job Scheduler** (Backend Service)

Create `services/backend-service/app/etl/job_scheduler.py`:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

class ETLJobScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
    
    async def schedule_all_jobs(self):
        """Schedule all active jobs from database"""
        jobs = await db.query("SELECT * FROM etl_jobs WHERE active = TRUE")
        
        for job in jobs:
            await self.schedule_job(job)
    
    async def schedule_job(self, job):
        """Schedule individual job with dynamic interval"""
        interval = (
            job.retry_interval_minutes 
            if job.retry_count > 0 and job.status == 'FAILED'
            else job.schedule_interval_minutes
        )
        
        self.scheduler.add_job(
            func=self.execute_job,
            trigger=IntervalTrigger(minutes=interval),
            id=f"job_{job.id}",
            args=[job.id],
            max_instances=1,
            replace_existing=True
        )
    
    async def execute_job(self, job_id: int):
        """Publish job to RabbitMQ extract queue"""
        job = await self.get_job(job_id)
        
        await queue_manager.publish_extract_job(
            tenant_id=job.tenant_id,
            integration_id=job.integration_id,
            job_type=job.job_name.lower(),
            job_params={"checkpoint_data": job.checkpoint_data}
        )
```

### 2. **Update Frontend** (etl-frontend)

- Remove orchestrator controls
- Add per-job schedule configuration UI
- Update job cards to show individual intervals
- Remove "execution order" display

### 3. **Implement Transform Worker with Vectorization**

Create `services/backend-service/app/etl/workers/transform_worker.py`:

```python
class TransformWorker:
    async def process_message(self, message: Dict):
        # 1. Get raw data
        raw_data = await self.get_raw_data(message['raw_data_id'])
        
        # 2. Transform
        transformed = await self.transform(raw_data)
        
        # 3. Load to primary tables
        inserted_ids = await self.bulk_load(transformed)
        
        # 4. Vectorize immediately (NEW!)
        await self.vectorize_entities(transformed)
```

---

## 📊 Testing Strategy

### **Before Running Migration**

1. ✅ Backup database
2. ✅ Test migration on dev environment first
3. ✅ Verify all tenants have required integrations

### **After Running Migration**

1. ✅ Verify `etl_jobs` table has correct schema
2. ✅ Verify all tenants have 4 jobs seeded
3. ✅ Verify `vectorization_queue` table is dropped
4. ✅ Verify orchestrator settings removed from `system_settings`
5. ✅ Check migration recorded in `migration_history`

### **SQL Verification Queries**

```sql
-- Check etl_jobs schema
\d etl_jobs

-- Count jobs per tenant
SELECT tenant_id, COUNT(*) as job_count 
FROM etl_jobs 
GROUP BY tenant_id;

-- Verify no vectorization jobs
SELECT * FROM etl_jobs WHERE LOWER(job_name) = 'vectorization';

-- Verify ETL settings removed (should return 0 rows)
SELECT * FROM system_settings
WHERE setting_key IN (
    'orchestrator_interval_minutes', 'orchestrator_enabled',
    'orchestrator_retry_enabled', 'orchestrator_retry_interval_minutes',
    'jira_sync_enabled', 'github_sync_enabled', 'max_concurrent_jobs'
);

-- Verify vectorization_queue dropped
SELECT * FROM information_schema.tables WHERE table_name = 'vectorization_queue';
```

---

## 🎯 Success Criteria

- ✅ Migration runs without errors
- ✅ All tenants have 4 jobs (Jira, GitHub, WEX Fabric, WEX AD)
- ✅ No vectorization job exists
- ✅ `vectorization_queue` table does not exist
- ✅ 7 ETL-related settings removed from `system_settings`
- ✅ Old ETL service stops working (expected)
- ✅ Database schema matches new autonomous architecture

---

## 📝 Rollback Plan

If migration fails or needs to be reverted:

### **Option 1: Simple Rollback** (if caught immediately)
```bash
python scripts/migrate.py rollback
```

### **Option 2: Full Reset** (recommended)
```bash
# 1. Drop database
DROP DATABASE health_pulse;

# 2. Recreate database
CREATE DATABASE health_pulse;

# 3. Re-run migrations 0001-0004
python scripts/migrate.py upgrade
```

---

## 🔗 Related Documentation

- [ETL Transformation Architecture](../evolution_plans/etl_transformation/)
- [RabbitMQ Queue Design](../jobs-orchestration.md)
- [Autonomous Job Scheduling](../etl_autonomous_jobs.md)

---

## ✅ Migration Checklist

- [ ] Backup production database
- [ ] Test migration on dev environment
- [ ] Verify all tenants have integrations
- [ ] Run migration: `python scripts/migrate.py upgrade`
- [ ] Verify schema changes with SQL queries
- [ ] Test new job scheduler implementation
- [ ] Update frontend to remove orchestrator controls
- [ ] Implement transform worker with integrated vectorization
- [ ] Monitor first job executions
- [ ] Document any issues or learnings

---

**Migration Author**: AI Agent  
**Review Status**: Pending  
**Approved By**: -  
**Executed On**: -

