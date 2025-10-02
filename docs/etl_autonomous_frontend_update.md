# ETL Autonomous Architecture - Frontend & Backend Updates

## Overview
Updated the ETL frontend and backend to support the new autonomous job architecture where each job manages its own schedule independently (no orchestrator).

**Date**: 2025-10-02  
**Migration**: 0005_etl_jobs_autonomous_architecture

---

## Database Schema Changes (Migration 0005)

### **etl_jobs Table - New Schema**

```sql
CREATE TABLE etl_jobs (
    -- Primary Key
    id SERIAL PRIMARY KEY,
    
    -- Core Job Identity
    job_name VARCHAR NOT NULL,
    
    -- Job Status
    status VARCHAR(20) NOT NULL DEFAULT 'READY',
    
    -- Scheduling Configuration (NEW)
    schedule_interval_minutes INTEGER NOT NULL DEFAULT 360,
    retry_interval_minutes INTEGER NOT NULL DEFAULT 15,
    
    -- Execution Tracking
    last_run_started_at TIMESTAMP,
    last_run_finished_at TIMESTAMP,  -- RENAMED from last_finished_at
    
    -- Error Handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Generic Recovery/Checkpoint (NEW)
    checkpoint_data JSONB,
    
    -- Foreign Keys
    integration_id INTEGER REFERENCES integrations(id),
    
    -- BaseEntity Fields (ALWAYS LAST)
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(job_name, tenant_id),
    CHECK (status IN ('READY', 'RUNNING', 'FINISHED', 'FAILED'))
);
```

### **Removed Columns**
- ❌ `execution_order` - No orchestrator, no execution sequence
- ❌ `last_success_at` - Replaced by `last_run_finished_at`
- ❌ All GitHub-specific cursor columns - Moved to `checkpoint_data` JSONB

### **Added Columns**
- ✅ `schedule_interval_minutes` - How often job runs (e.g., 360 = 6 hours)
- ✅ `retry_interval_minutes` - Fast retry on failure (e.g., 15 = 15 minutes)
- ✅ `checkpoint_data` - JSONB for job-specific recovery data

### **Renamed Columns**
- 🔄 `last_finished_at` → `last_run_finished_at` (consistency with `last_run_started_at`)

### **Status Values Changed**
- ❌ Removed: `PENDING`, `PAUSED`
- ✅ Kept: `READY`, `RUNNING`, `FINISHED`, `FAILED`

---

## Frontend Changes

### **1. HomePage.tsx** (`services/etl-frontend/src/pages/HomePage.tsx`)

#### **Removed**
- ❌ OrchestratorControl component
- ❌ OrchestratorSettingsModal
- ❌ Orchestrator status/settings state
- ❌ `fetchOrchestratorStatus()` and `fetchOrchestratorSettings()`
- ❌ `handleToggleOrchestrator()`, `handleStartOrchestrator()`, `handleSaveOrchestratorSettings()`
- ❌ `handlePauseJob()`, `handleResumeJob()`, `handleForcePending()`

#### **Added**
- ✅ JobSettingsModal component
- ✅ `selectedJobForSettings` state
- ✅ `handleRunNow()` - Manually trigger job
- ✅ `handleSaveJobSettings()` - Update job schedule/retry intervals

#### **Updated**
- 🔄 Job interface now includes `schedule_interval_minutes`, `retry_interval_minutes`, `last_run_finished_at`
- 🔄 Jobs sorted alphabetically by `job_name` (not by `execution_order`)
- 🔄 Page title: "ETL Jobs Dashboard" (was "ETL Pipeline Dashboard")
- 🔄 Subtitle: "Monitor and control your autonomous data synchronization jobs"

### **2. JobCard.tsx** (`services/etl-frontend/src/components/JobCard.tsx`)

#### **Removed**
- ❌ Pause/Resume buttons
- ❌ Force Pending button
- ❌ `execution_order` prop
- ❌ `last_success_at` prop
- ❌ PENDING and PAUSED status handling

#### **Added**
- ✅ "Run Now" button (manual trigger)
- ✅ Settings button (gear icon)
- ✅ Schedule interval display
- ✅ `schedule_interval_minutes` and `retry_interval_minutes` props
- ✅ `last_run_finished_at` prop
- ✅ FAILED status handling

#### **Updated**
- 🔄 Status colors: READY is now green (was gray)
- 🔄 Last run time uses `last_run_finished_at` (was `last_success_at`)
- 🔄 Shows "Interval: 6h" instead of execution order
- 🔄 Action buttons: Run Now, Settings, Details, On/Off Toggle

### **3. JobSettingsModal.tsx** (`services/etl-frontend/src/components/JobSettingsModal.tsx`)

**New Component** - Replaces OrchestratorSettingsModal

#### **Features**
- ✅ Configure `schedule_interval_minutes` (how often job runs)
- ✅ Configure `retry_interval_minutes` (fast retry on failure)
- ✅ Quick preset buttons (1h, 4h, 6h, 12h, 24h for schedule; 5m, 15m, 30m, 1h for retry)
- ✅ Validation: retry interval must be < schedule interval
- ✅ Human-readable time display (e.g., "6 hours" instead of "360 minutes")
- ✅ Info box explaining how scheduling works

---

## Backend Changes

### **1. jobs.py** (`services/backend-service/app/etl/jobs.py`)

#### **Removed Endpoints**
- ❌ `POST /jobs/{job_id}/pause`
- ❌ `POST /jobs/{job_id}/resume`
- ❌ `POST /jobs/{job_id}/force-pending`
- ❌ `POST /jobs/{job_id}/finish`

#### **Added Endpoints**
- ✅ `POST /jobs/{job_id}/run-now` - Manually trigger job execution
- ✅ `POST /jobs/{job_id}/settings` - Update schedule/retry intervals

#### **Updated Endpoints**
- 🔄 `GET /jobs` - Returns new schema fields, sorted by `job_name` ASC
- 🔄 `GET /jobs/{job_id}` - Returns `checkpoint_data` JSONB
- 🔄 `POST /jobs/{job_id}/toggle-active` - No changes (still works)

#### **Removed Helper Functions**
- ❌ `find_next_ready_job()` - No orchestrator, no job sequencing

#### **Updated Schemas**

**JobCardResponse**
```python
class JobCardResponse(BaseModel):
    id: int
    job_name: str
    status: str  # 'READY', 'RUNNING', 'FINISHED', 'FAILED'
    active: bool
    schedule_interval_minutes: int  # NEW
    retry_interval_minutes: int     # NEW
    integration_id: Optional[int]
    integration_type: Optional[str]
    integration_logo_filename: Optional[str]
    last_run_started_at: Optional[datetime]
    last_run_finished_at: Optional[datetime]  # RENAMED
    error_message: Optional[str]
    retry_count: int
```

**JobDetailsResponse**
```python
class JobDetailsResponse(BaseModel):
    id: int
    job_name: str
    status: str
    active: bool
    schedule_interval_minutes: int  # NEW
    retry_interval_minutes: int     # NEW
    integration_id: Optional[int]
    last_run_started_at: Optional[datetime]
    last_run_finished_at: Optional[datetime]  # RENAMED
    created_at: datetime
    last_updated_at: datetime
    error_message: Optional[str]
    retry_count: int
    checkpoint_data: Optional[Dict[str, Any]]  # NEW
```

**New Schemas**
```python
class JobSettingsRequest(BaseModel):
    schedule_interval_minutes: int = Field(..., ge=1)
    retry_interval_minutes: int = Field(..., ge=1)

class JobSettingsResponse(BaseModel):
    success: bool
    message: str
    job_id: int
    schedule_interval_minutes: int
    retry_interval_minutes: int
```

---

## Migration Summary

### **What Was Removed**
1. ❌ Orchestrator concept - No central job coordinator
2. ❌ Execution order - Jobs don't run in sequence
3. ❌ PENDING/PAUSED statuses - Simplified to READY/RUNNING/FINISHED/FAILED
4. ❌ Pause/Resume/Force Pending actions - Not needed in autonomous model
5. ❌ `vectorization_queue` table - Vectorization integrated into workers
6. ❌ 7 system_settings entries - ETL config moved to job level

### **What Was Added**
1. ✅ Per-job scheduling - Each job has its own interval
2. ✅ Per-job retry logic - Each job has its own retry interval
3. ✅ Generic checkpoint system - JSONB for any job type
4. ✅ Job settings UI - Configure each job independently
5. ✅ Manual job trigger - "Run Now" button

### **Key Architectural Changes**
- **Before**: Orchestrator controls all jobs in sequence
- **After**: Each job is autonomous with its own schedule

---

## Testing Checklist

### **Frontend**
- [ ] Home page loads without orchestrator control
- [ ] Job cards display schedule interval
- [ ] "Run Now" button triggers job
- [ ] Settings modal opens and saves
- [ ] On/Off toggle works
- [ ] Details modal opens

### **Backend**
- [ ] `GET /jobs` returns new schema
- [ ] `GET /jobs/{id}` returns checkpoint_data
- [ ] `POST /jobs/{id}/run-now` sets status to RUNNING
- [ ] `POST /jobs/{id}/settings` updates intervals
- [ ] `POST /jobs/{id}/toggle-active` still works

### **Database**
- [ ] Migration 0005 applies successfully
- [ ] All jobs seeded for all tenants
- [ ] System settings cleaned up
- [ ] Indexes created

---

## Next Steps (Phase 2/3)

1. **Implement Job Scheduler** - APScheduler to run jobs on their intervals
2. **Implement Workers** - Extract/Transform/Load workers
3. **Implement RabbitMQ Integration** - Queue-based processing
4. **Implement Checkpoint Logic** - Use `checkpoint_data` for recovery
5. **Remove Placeholder Messages** - Make "Run Now" actually execute jobs

---

## Files Modified

### **Frontend**
- `services/etl-frontend/src/pages/HomePage.tsx`
- `services/etl-frontend/src/components/JobCard.tsx`
- `services/etl-frontend/src/components/JobSettingsModal.tsx` (NEW)

### **Backend**
- `services/backend-service/app/etl/jobs.py`

### **Database**
- `services/backend-service/scripts/migrations/0005_etl_jobs_autonomous_architecture.py`

### **Documentation**
- `docs/migrations/0005_autonomous_etl_architecture.md`
- `docs/etl_checkpoint_data_schema.md`
- `docs/etl_autonomous_frontend_update.md` (THIS FILE)

---

**Status**: ✅ Complete - Ready for testing

