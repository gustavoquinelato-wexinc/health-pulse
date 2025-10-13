# ETL Phase 2.3: Issues, Changelogs & Dev Status (Complete E2E Implementation)

**Implemented**: YES ✅
**Duration**: 1 week (Week 7 of overall plan)
**Priority**: HIGH
**Risk Level**: MEDIUM
**Last Updated**: 2025-10-13
**Status**: COMPLETED
**Jira Story**: [BEN-10438](https://wexinc.atlassian.net/browse/BEN-10438)
**Jira Subtask**: [BEN-10441](https://wexinc.atlassian.net/browse/BEN-10441) - DONE

> ⚠️ **ARCHITECTURE NOTE**: All ETL functionality is implemented in `services/backend-service/app/etl/`. The `services/etl-service` is now **LEGACY/DEPRECATED** and should not be used for new development.

## 📊 Prerequisites (Must be complete before starting)

1. ✅ **Phase 0 Complete**: ETL Frontend + Backend ETL Module working
2. ✅ **Phase 1 Complete**: RabbitMQ + Raw Data Storage + Queue Manager
   - RabbitMQ container running
   - Database tables created (`raw_extraction_data`, `etl_job_queue`)
   - Queue manager implemented in backend-service
   - Raw data APIs functional
3. ✅ **Phase 2.1 Complete**: Projects & Issue Types Extraction
   - Projects and issue types extraction working end-to-end
4. ✅ **Phase 2.2 Complete**: Statuses & Project Relationships
   - Statuses and project relationships extraction working end-to-end
   - Complete metadata foundation available

**Status**: Ready to start after Phase 2.2 completion.

## 💼 Business Outcome

**Complete Issues, Changelogs & Dev Status Extraction**: Implement the full end-to-end flow for Jira issues, changelogs, and development status extraction using the new queue-based architecture:
- **API Endpoints** for triggering issues, changelogs, and dev status extraction
- **Raw Data Storage** in `raw_extraction_data` table
- **Queue Processing** with transformation workers
- **Database Operations** for work_items, changelogs, and dev_status tables
- **Custom Fields Processing** with dynamic mapping and JSON overflow
- **UI Integration** for monitoring and control
- **Progress Tracking** with real-time updates

This completes the core Jira ETL functionality, providing full work item tracking with change history and development status.

## 🎯 Objectives

1. **API Endpoints**: Create issues, changelogs, and dev status extraction endpoints in backend-service/app/etl/
2. **Data Extraction**: Implement Jira API integration for issues, changelogs, and development status
3. **Queue Integration**: Store raw data and publish transformation messages
4. **Transform Workers**: Process queued data and update final database tables
5. **Custom Fields Processing**: Dynamic mapping with 20 columns + JSON overflow
6. **UI Integration**: Connect ETL frontend to trigger and monitor extractions
7. **Progress Tracking**: Real-time job status and progress updates

## 📋 Task Breakdown

### Task 2.3.1: API Endpoints Implementation
**Duration**: 2 days
**Priority**: CRITICAL

#### Issues, Changelogs & Dev Status Extraction Endpoint
```python
# services/backend-service/app/etl/jira_extraction.py (enhancement)
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from app.core.database import get_db_session
from app.etl.jira_client import JiraAPIClient
from app.etl.queue.queue_manager import QueueManager

@router.post("/jira/extract/issues-changelogs-dev-status/{integration_id}")
async def extract_issues_changelogs_dev_status(
    integration_id: int,
    tenant_id: int = Query(..., description="Tenant ID"),
    project_keys: List[str] = Query(None, description="Specific project keys to extract"),
    incremental: bool = Query(True, description="Incremental extraction"),
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session)
):
    """
    Extract issues, changelogs, and dev status from Jira.
    
    This endpoint:
    1. Fetches issues with custom fields from Jira API
    2. Fetches changelogs for each issue
    3. Processes dev status (code_changed field)
    4. Stores raw data in raw_extraction_data table
    5. Publishes transformation messages to queue
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
            execute_issues_changelogs_dev_status_extraction,
            integration_id, tenant_id, jira_client, project_keys, incremental
        )
        
        return {
            "success": True,
            "message": "Issues, changelogs, and dev status extraction started",
            "integration_id": integration_id,
            "incremental": incremental,
            "project_keys": project_keys
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Task 2.3.2: Data Extraction Functions
**Duration**: 3 days
**Priority**: CRITICAL

#### Issues, Changelogs & Dev Status Extraction Function
```python
# services/backend-service/app/etl/jira_extraction.py (enhancement)
async def execute_issues_changelogs_dev_status_extraction(
    integration_id: int,
    tenant_id: int,
    jira_client: JiraAPIClient,
    project_keys: List[str] = None,
    incremental: bool = True
):
    """
    Execute the complete issues, changelogs, and dev status extraction.
    
    This function:
    1. Extracts issues with custom fields from Jira
    2. Extracts changelogs for each issue
    3. Processes dev status information
    4. Stores raw data in raw_extraction_data table
    5. Publishes transformation messages to queue
    """
    try:
        logger.info(f"Starting issues extraction for integration {integration_id}")
        
        # Get projects to extract from
        if not project_keys:
            projects = await get_integration_projects(integration_id, tenant_id)
            project_keys = [p['key'] for p in projects]
        
        # Extract issues for each project
        for project_key in project_keys:
            await extract_project_issues_with_changelogs(
                jira_client, integration_id, tenant_id, project_key, incremental
            )
        
        logger.info(f"Issues extraction completed for integration {integration_id}")
        
    except Exception as e:
        logger.error(f"Issues extraction failed for integration {integration_id}: {e}")
        raise

async def extract_project_issues_with_changelogs(
    jira_client: JiraAPIClient,
    integration_id: int,
    tenant_id: int,
    project_key: str,
    incremental: bool = True
):
    """Extract issues with changelogs for a specific project."""
    try:
        # Build JQL query for incremental extraction
        jql = build_incremental_jql(project_key, incremental, tenant_id)
        
        # Get custom field mappings for dynamic field list
        field_mappings = await get_custom_field_mappings(integration_id, tenant_id)
        fields = build_dynamic_field_list(field_mappings)
        
        # Extract issues in batches
        start_at = 0
        batch_size = 50  # Smaller batches for memory efficiency
        
        while True:
            # Get batch of issues
            issues_response = await jira_client.search_issues(
                jql=jql,
                start_at=start_at,
                max_results=batch_size,
                fields=fields,
                expand=['changelog']
            )
            
            issues = issues_response.get('issues', [])
            if not issues:
                break
            
            # Process each issue with changelogs and dev status
            for issue in issues:
                await process_issue_with_changelogs_and_dev_status(
                    issue, integration_id, tenant_id, jira_client
                )
            
            start_at += batch_size
            logger.info(f"Processed {start_at} issues for project {project_key}")
        
    except Exception as e:
        logger.error(f"Failed to extract issues for project {project_key}: {e}")
        raise
```

### Task 2.3.3: Transform Worker Implementation
**Duration**: 2 days
**Priority**: HIGH

#### Issues Transform Worker Enhancement
```python
# services/backend-service/app/workers/transform_worker.py (enhancement)
async def process_jira_issues_changelogs_dev_status(self, message_data: Dict[str, Any]):
    """
    Process issues, changelogs, and dev status from raw data.
    
    This function:
    1. Retrieves raw data from raw_extraction_data table
    2. Processes issues with custom fields mapping
    3. Processes changelogs and saves to changelogs table
    4. Processes dev status and saves to dev_status table
    5. Updates job progress and status
    """
    try:
        integration_id = message_data['integration_id']
        tenant_id = message_data['tenant_id']
        extraction_id = message_data['extraction_id']
        
        logger.info(f"Processing issues, changelogs, and dev status for extraction {extraction_id}")
        
        # Get raw data
        raw_data = await self.get_raw_extraction_data(extraction_id)
        
        # Process issues with custom fields
        await self.process_issues_with_custom_fields(raw_data['issues'], tenant_id, integration_id)
        
        # Process changelogs
        await self.process_changelogs(raw_data['changelogs'], tenant_id)
        
        # Process dev status
        await self.process_dev_status(raw_data['dev_status'], tenant_id)
        
        logger.info(f"Successfully processed issues, changelogs, and dev status for extraction {extraction_id}")
        
    except Exception as e:
        logger.error(f"Failed to process issues, changelogs, and dev status: {e}")
        raise
```

### Task 2.3.4: UI Integration
**Duration**: 1 day
**Priority**: MEDIUM

#### ETL Frontend Integration for Issues Extraction
```typescript
// services/etl-frontend/src/components/JobCard.tsx (enhancement)
const handleIssuesExtraction = async () => {
  try {
    setIsLoading(true);
    
    const response = await fetch(
      `/api/v1/etl/jira/extract/issues-changelogs-dev-status/${integration.id}?tenant_id=${tenantId}&incremental=true`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    if (!response.ok) {
      throw new Error('Failed to start issues extraction');
    }
    
    const result = await response.json();
    
    // Show success message
    toast.success('Issues extraction started successfully');
    
    // Refresh job status
    await refreshJobStatus();
    
  } catch (error) {
    console.error('Issues extraction failed:', error);
    toast.error('Failed to start issues extraction');
  } finally {
    setIsLoading(false);
  }
};
```

### Task 2.3.5: Progress Tracking & Error Handling
**Duration**: 1 day
**Priority**: MEDIUM

#### Issues Extraction Progress Tracker
```python
# services/backend-service/app/etl/progress/issues_progress_tracker.py
class IssuesExtractionProgressTracker:
    """Track progress for issues, changelogs, and dev status extraction."""
    
    def __init__(self, integration_id: int, tenant_id: int):
        self.integration_id = integration_id
        self.tenant_id = tenant_id
        self.total_steps = 5
        self.current_step = 0
        
    async def track_issues_extraction(self):
        """Track the complete issues extraction process."""
        try:
            await self.update_progress(1, "Starting issues extraction...")
            
            await self.update_progress(2, "Fetching issues with custom fields...")
            
            await self.update_progress(3, "Processing changelogs and dev status...")
            
            await self.update_progress(4, "Storing raw data and queuing for processing...")
            
            await self.update_progress(5, "Issues extraction completed successfully")
            
        except Exception as e:
            await self.update_progress(self.current_step, f"Error: {str(e)}")
            raise
```

## ✅ Success Criteria

1. **API Endpoints**: Issues, changelogs, and dev status extraction endpoints working
2. **Data Extraction**: Complete issues with custom fields, changelogs, and dev status extracted from Jira
3. **Raw Data Storage**: All extracted data stored in raw_extraction_data table
4. **Queue Processing**: Transform workers processing issues data successfully
5. **Database Operations**: Work_items, changelogs, and dev_status tables populated correctly
6. **Custom Fields Processing**: Dynamic mapping with 20 columns + JSON overflow working
7. **UI Integration**: ETL frontend can trigger and monitor issues extraction
8. **Progress Tracking**: Real-time progress updates working

## 🚨 Risk Mitigation

1. **Large Datasets**: Handle large numbers of issues efficiently with batching
2. **Memory Usage**: Process issues in small batches to avoid memory issues
3. **API Rate Limits**: Implement proper rate limiting for Jira API calls
4. **Data Consistency**: Ensure changelogs and dev status are correctly linked to issues
5. **Queue Performance**: Optimize queue processing for large volumes of data

## 📋 Implementation Checklist

- [ ] Create API endpoint `/jira/extract/issues-changelogs-dev-status/{integration_id}`
- [ ] Implement `execute_issues_changelogs_dev_status_extraction()` function
- [ ] Create `extract_project_issues_with_changelogs()` and related functions
- [ ] Implement raw data storage in `raw_extraction_data` table
- [ ] Add queue message publishing for transformation
- [ ] Enhance transform worker to process `jira_issues_changelogs_dev_status` data type
- [ ] Implement custom fields processing with dynamic mapping
- [ ] Implement changelogs and dev status processing functions
- [ ] Add progress tracking with `IssuesExtractionProgressTracker`
- [ ] Integrate UI trigger button in ETL frontend
- [ ] Add error handling and retry mechanisms
- [ ] Test complete end-to-end flow
- [ ] Validate database operations and performance

## 🔄 Next Steps

After completion, this enables:
- **Complete Jira ETL Pipeline**: Full Extract → Queue → Transform → Load for all Jira data types
- **Phase 3**: GitHub Enhancement and additional integrations
- **Production Ready**: Core ETL functionality complete and tested

**Mark as Implemented**: ✅ when all checklist items are complete and end-to-end flow is working.
