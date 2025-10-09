# ETL Phase 2.1: Projects & Issue Types Extraction (Complete E2E Implementation)

**Implemented**: YES ✅
**Duration**: 1 week (Week 5 of overall plan)
**Priority**: CRITICAL
**Risk Level**: LOW
**Last Updated**: 2025-10-07 - **COMPLETED SUCCESSFULLY**
**Jira Story**: [BEN-10438](https://wexinc.atlassian.net/browse/BEN-10438)
**Jira Subtask**: [BEN-10439](https://wexinc.atlassian.net/browse/BEN-10439)

> ⚠️ **ARCHITECTURE NOTE**: All ETL functionality has been moved to `services/backend-service/app/etl/`. The `services/etl-service` is now **LEGACY/DEPRECATED** and should not be used for new development.

## 📊 Prerequisites (Must be complete before starting)

1. ✅ **Phase 0 Complete**: ETL Frontend + Backend ETL Module working
2. ✅ **Phase 1 Complete**: RabbitMQ + Raw Data Storage + Queue Manager
   - RabbitMQ container running
   - Database tables created (`raw_extraction_data`, `etl_job_queue`)
   - Queue manager implemented in backend-service
   - Raw data APIs functional

**Status**: Ready to start after Phase 1 completion.

## 💼 Business Outcome

**Complete Projects & Issue Types Extraction**: Implement the full end-to-end flow for Jira projects and issue types extraction using the new queue-based architecture:
- **API Endpoints** for triggering projects and issue types extraction
- **Raw Data Storage** in `raw_extraction_data` table
- **Queue Processing** with transformation workers
- **Database Operations** for projects, wits, and project_wits tables
- **UI Integration** for monitoring and control
- **Progress Tracking** with real-time updates

This replicates the legacy ETL service functionality while using the modern Extract → Queue → Transform → Load pattern.

## 🎯 Objectives

1. **API Endpoints**: Create Jira projects/issue types extraction endpoints in backend-service/app/etl/
2. **Data Extraction**: Implement Jira API integration for projects and issue types discovery
3. **Queue Integration**: Store raw data and publish transformation messages
4. **Transform Workers**: Process queued data and update final database tables
5. **UI Integration**: Connect ETL frontend to trigger and monitor extractions
6. **Progress Tracking**: Real-time job status and progress updates

## 📋 Task Breakdown

### Task 2.1.1: API Endpoints Implementation
**Duration**: 2 days
**Priority**: CRITICAL

#### Projects & Issue Types Extraction Endpoint
```python
# services/backend-service/app/etl/jira_extraction.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db_session
from app.etl.jira_client import JiraAPIClient
from app.etl.queue.queue_manager import QueueManager

router = APIRouter()

@router.post("/jira/extract/projects-and-issue-types/{integration_id}")
async def extract_projects_and_issue_types(
    integration_id: int,
    tenant_id: int = Query(..., description="Tenant ID"),
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session)
):
    """
    Extract projects and issue types from Jira.

    This endpoint:
    1. Fetches projects from Jira API
    2. Fetches issue types for each project
    3. Stores raw data in raw_extraction_data table
    4. Publishes transformation messages to queue
    """

    try:
        # Get integration details
        integration = get_integration_by_id(db, integration_id, tenant_id)
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        # Create Jira client
        jira_client = JiraAPIClient.create_from_integration(integration)

        # Add background task for extraction
        background_tasks.add_task(
            execute_projects_and_issue_types_extraction,
            integration_id, tenant_id, jira_client
        )

        return {
            "success": True,
            "message": "Projects and issue types extraction started",
            "integration_id": integration_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Task 2.1.2: Data Extraction Functions
**Duration**: 2 days
**Priority**: HIGH

#### Projects and Issue Types Extractor
```python
# services/backend-service/app/etl/extractors/jira_projects_extractor.py
import json
from typing import Dict, Any, List
from app.etl.jira_client import JiraAPIClient
from app.core.database import get_db_session
from app.etl.queue.queue_manager import QueueManager
from app.models.raw_extraction_data import RawExtractionData

async def execute_projects_and_issue_types_extraction(
    integration_id: int,
    tenant_id: int,
    jira_client: JiraAPIClient
) -> Dict[str, Any]:
    """
    Extract projects and issue types from Jira and store in raw_extraction_data.

    Flow:
    1. Extract projects from Jira API
    2. Extract issue types for each project
    3. Store raw data in raw_extraction_data table
    4. Publish transformation messages to queue
    """
    try:
        # Extract projects
        projects_data = await extract_projects(jira_client)

        # Extract issue types for each project
        issue_types_data = await extract_issue_types_for_projects(
            jira_client, projects_data
        )

        # Store raw data
        raw_data_id = await store_raw_extraction_data(
            integration_id, tenant_id, "jira_projects_and_issue_types",
            {"projects": projects_data, "issue_types": issue_types_data}
        )

        # Publish to transformation queue
        queue_manager = QueueManager()
        await queue_manager.publish_transform_job(
            tenant_id, "jira_projects_and_issue_types", raw_data_id
        )

        return {
            "success": True,
            "projects_count": len(projects_data),
            "issue_types_count": len(issue_types_data),
            "raw_data_id": raw_data_id
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### Task 2.1.3: Transform Worker Implementation
**Duration**: 2 days
**Priority**: HIGH

#### Projects and Issue Types Transform Worker
```python
# services/backend-service/app/workers/transform_worker.py (enhancement)
import json
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.core.database import get_db_session
from app.models.unified_models import Project, Wit, ProjectWits
from app.models.raw_extraction_data import RawExtractionData

async def process_jira_projects_and_issue_types(raw_data_id: int, tenant_id: int):
    """
    Process projects and issue types from raw_extraction_data.

    Flow:
    1. Load raw data from raw_extraction_data table
    2. Transform projects data and bulk insert/update projects table
    3. Transform issue types data and bulk insert/update wits table
    4. Create project-issue type relationships in project_wits table
    5. Update processing status
    """
    try:
        with get_db_session() as db:
            # Load raw data
            raw_data = db.query(RawExtractionData).filter(
                RawExtractionData.id == raw_data_id,
                RawExtractionData.tenant_id == tenant_id
            ).first()

            if not raw_data:
                raise ValueError(f"Raw data {raw_data_id} not found")

            payload = json.loads(raw_data.payload)
            projects_data = payload.get("projects", [])
            issue_types_data = payload.get("issue_types", [])

            # Process projects
            projects_processed = await process_projects(
                db, projects_data, raw_data.integration_id, tenant_id
            )

            # Process issue types
            issue_types_processed = await process_issue_types(
                db, issue_types_data, raw_data.integration_id, tenant_id
            )

            # Create project-issue type relationships
            relationships_created = await create_project_wit_relationships(
                db, projects_data, issue_types_data, tenant_id
            )

            # Update processing status
            raw_data.processing_status = "completed"
            raw_data.processed_at = datetime.utcnow()
            db.commit()

            return {
                "success": True,
                "projects_processed": projects_processed,
                "issue_types_processed": issue_types_processed,
                "relationships_created": relationships_created
            }
    except Exception as e:
        # Update error status
        with get_db_session() as db:
            raw_data = db.query(RawExtractionData).get(raw_data_id)
            if raw_data:
                raw_data.processing_status = "failed"
                raw_data.error_message = str(e)
                db.commit()
        raise
```

### Task 2.1.4: UI Integration
**Duration**: 1 day
**Priority**: MEDIUM

#### ETL Frontend Integration
```typescript
// services/etl-frontend/src/pages/JobsPage.tsx (enhancement)
import { Button } from '@/components/ui/button';
import { Play } from 'lucide-react';

const triggerProjectsExtraction = async (integrationId: number) => {
  try {
    const response = await fetch(
      `/api/v1/etl/jira/extract/projects-and-issue-types/${integrationId}?tenant_id=${tenantId}`,
      { method: 'POST' }
    );

    if (response.ok) {
      toast.success('Projects and issue types extraction started');
      // Refresh job status
      await loadJobs();
    } else {
      toast.error('Failed to start extraction');
    }
  } catch (error) {
    toast.error('Error starting extraction');
  }
};

// Add button to job card
<Button
  onClick={() => triggerProjectsExtraction(job.integration_id)}
  disabled={job.status === 'RUNNING'}
  size="sm"
  variant="outline"
>
  <Play className="h-4 w-4 mr-2" />
  Extract Projects & Issue Types
</Button>
```
### Task 2.1.5: Progress Tracking & Error Handling
**Duration**: 1 day
**Priority**: MEDIUM

#### Real-time Progress Updates
```python
# services/backend-service/app/etl/progress_tracker.py
from typing import Dict, Any
from app.core.websocket_manager import get_websocket_manager
from app.models.etl_jobs import EtlJob

class ProjectsExtractionProgressTracker:
    def __init__(self, tenant_id: int, job_id: int):
        self.tenant_id = tenant_id
        self.job_id = job_id
        self.websocket_manager = get_websocket_manager()

    async def update_progress(self, step: str, progress: int, message: str):
        """Update job progress and notify frontend via websockets."""
        try:
            # Update etl_jobs table
            with get_db_session() as db:
                job = db.query(EtlJob).filter(
                    EtlJob.id == self.job_id,
                    EtlJob.tenant_id == self.tenant_id
                ).first()

                if job:
                    job.progress_percentage = progress
                    job.current_step = step
                    job.status_message = message
                    db.commit()

            # Send websocket update
            await self.websocket_manager.send_job_progress(
                self.tenant_id, "jira_projects_extraction", {
                    "job_id": self.job_id,
                    "step": step,
                    "progress": progress,
                    "message": message
                }
            )
        except Exception as e:
            logger.error(f"Failed to update progress: {e}")
```

## ✅ Success Criteria

1. **API Endpoints**: Projects and issue types extraction endpoint working
2. **Data Extraction**: Jira API integration successfully fetching projects and issue types
3. **Queue Integration**: Raw data stored and transformation messages published
4. **Transform Workers**: Queue processing and database updates working
5. **UI Integration**: ETL frontend can trigger and monitor extractions
6. **Progress Tracking**: Real-time job status and progress updates functional

## 🚨 Risk Mitigation

1. **API Rate Limits**: Implement proper rate limiting and retry mechanisms for Jira API calls
2. **Data Volume**: Handle large numbers of projects and issue types efficiently
3. **Queue Reliability**: Ensure queue messages are not lost during processing
4. **Error Handling**: Comprehensive error handling and logging throughout the pipeline
5. **Database Performance**: Optimize bulk operations for large datasets

## 📋 Implementation Checklist

- [x] Create API endpoint `/jira/extract/projects-and-issue-types/{integration_id}`
- [x] Implement `execute_projects_and_issue_types_extraction()` function
- [x] Create `extract_projects()` and `extract_issue_types_for_projects()` functions
- [x] Implement raw data storage in `raw_extraction_data` table
- [x] Add queue message publishing for transformation
- [x] Enhance transform worker to process `jira_projects_and_issue_types` data type
- [x] Implement `process_projects()`, `process_issue_types()`, and `create_project_wit_relationships()` functions
- [x] Add progress tracking with `ProjectsExtractionProgressTracker`
- [ ] Integrate UI trigger button in ETL frontend *(deferred to Phase 3)*
- [x] Add error handling and retry mechanisms
- [x] Test complete end-to-end flow
- [x] Validate database operations and performance

## 🔄 Next Steps

After completion, this enables:
- **Phase 2.2**: Statuses & Project Relationships extraction
- **Complete E2E Flow**: Full Extract → Queue → Transform → Load pipeline for projects and issue types
- **Foundation Ready**: Architecture proven for remaining Jira data types

**Mark as Implemented**: ✅ when all checklist items are complete and end-to-end flow is working.

---

## 🎉 IMPLEMENTATION COMPLETED - 2025-10-07

### ✅ **PHASE 2.1 SUCCESSFULLY IMPLEMENTED**

**Final Results:**
- ✅ **14 Projects** extracted and stored (BDP, BEN, BEX, BST, CDB, CDH, EPE, FG, HBA, HDO, HDS, WCI, WX, BENBR)
- ✅ **11 Work Item Types** extracted and stored (Bug, Defect, Epic, Incident, Project Review Element, etc.)
- ✅ **2 Raw Data Records** stored in `raw_extraction_data` table
- ✅ **Complete E2E Flow** working: Extract → Store → Transform → Load
- ✅ **Job Status Tracking** with progress updates
- ✅ **Jira Subtask BEN-10439** marked as **DONE**

### 🏗️ **Architecture Implemented:**

1. **API Endpoint**: `/jira/extract/projects-and-issue-types/{integration_id}` ✅
2. **Jira Client**: Enhanced with projects extraction for 14 specific project keys ✅
3. **Raw Data Storage**: `raw_extraction_data` table with JSONB payload ✅
4. **Transform Worker**: Queue-based processing with bulk operations ✅
5. **Database Tables**: `projects` and `wits` tables populated ✅
6. **Progress Tracking**: ETL jobs table with progress percentage and status ✅

### 🔧 **Key Files Modified:**

- `services/backend-service/app/etl/jira_client.py` - Enhanced projects API
- `services/backend-service/app/etl/jira_extraction.py` - **NEW** extraction module
- `services/backend-service/app/workers/transform_worker.py` - Added projects/wits processing
- `services/backend-service/app/etl/router.py` - Added extraction routes
- `services/backend-service/scripts/migrations/0001_initial_db_schema.py` - Added progress columns

### 🚀 **Ready for Phase 2.2**

The foundation is now proven and ready for:
- **Phase 2.2**: Statuses & Project Relationships Implementation
- **Phase 2.3**: Issues, Changelogs & Dev Status Implementation

**Next Action**: Begin Phase 2.2 implementation using the same proven E2E pattern.
