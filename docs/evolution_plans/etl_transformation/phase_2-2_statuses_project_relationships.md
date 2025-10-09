# ETL Phase 2.2: Statuses & Project Relationships (Complete E2E Implementation)

**Implemented**: NO ❌
**Duration**: 1 week (Week 6 of overall plan)
**Priority**: HIGH
**Risk Level**: MEDIUM
**Last Updated**: 2025-10-07
**Jira Story**: [BEN-10438](https://wexinc.atlassian.net/browse/BEN-10438)
**Jira Subtask**: [BEN-10440](https://wexinc.atlassian.net/browse/BEN-10440)

> ⚠️ **ARCHITECTURE NOTE**: All ETL functionality has been moved to `services/backend-service/app/etl/`. The `services/etl-service` is now **LEGACY/DEPRECATED** and should not be used for new development.

## 📊 Prerequisites (Must be complete before starting)

1. ✅ **Phase 0 Complete**: ETL Frontend + Backend ETL Module working
2. ✅ **Phase 1 Complete**: RabbitMQ + Raw Data Storage + Queue Manager
   - RabbitMQ container running
   - Database tables created (`raw_extraction_data`, `etl_job_queue`)
   - Queue manager implemented in backend-service
   - Raw data APIs functional
3. ✅ **Phase 2.1 Complete**: Projects & Issue Types Extraction
   - Projects and issue types extraction working end-to-end
   - Queue processing and transform workers functional
   - Database operations for projects, wits, and project_wits tables

**Status**: Ready to start after Phase 2.1 completion.

## 💼 Business Outcome

**Complete Statuses & Project Relationships Extraction**: Implement the full end-to-end flow for Jira statuses and project relationships extraction using the new queue-based architecture:
- **API Endpoints** for triggering statuses and project relationships extraction
- **Raw Data Storage** in `raw_extraction_data` table
- **Queue Processing** with transformation workers
- **Database Operations** for statuses and projects_statuses tables
- **UI Integration** for monitoring and control
- **Progress Tracking** with real-time updates

This builds upon Phase 2.1 to complete the foundational Jira metadata extraction capabilities.

## 🎯 Objectives

1. **API Endpoints**: Create Jira statuses/project relationships extraction endpoints in backend-service/app/etl/
2. **Data Extraction**: Implement Jira API integration for statuses and project-status relationships
3. **Queue Integration**: Store raw data and publish transformation messages
4. **Transform Workers**: Process queued data and update final database tables
5. **UI Integration**: Connect ETL frontend to trigger and monitor extractions
6. **Progress Tracking**: Real-time job status and progress updates

## 📋 Task Breakdown

### Task 2.2.1: API Endpoints Implementation
**Duration**: 2 days
**Priority**: CRITICAL

#### Statuses & Project Relationships Extraction Endpoint
```python
# services/backend-service/app/etl/jira_extraction.py (enhancement)
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from app.core.database import get_db_session
from app.etl.jira_client import JiraAPIClient
from app.etl.queue.queue_manager import QueueManager

@router.post("/jira/extract/statuses-and-relationships/{integration_id}")
async def extract_statuses_and_relationships(
    integration_id: int,
    tenant_id: int = Query(..., description="Tenant ID"),
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session)
):
    """
    Extract statuses and project-status relationships from Jira.

    This endpoint:
    1. Fetches all statuses from Jira API
    2. Fetches project-status relationships
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
            execute_statuses_and_relationships_extraction,
            integration_id, tenant_id, jira_client
        )

        return {
            "success": True,
            "message": "Statuses and project relationships extraction started",
            "integration_id": integration_id
        }
        raise HTTPException(status_code=500, detail=str(e))
```

### Task 2.2.2: Data Extraction Functions
**Duration**: 2 days
**Priority**: CRITICAL

#### Statuses and Project Relationships Extraction Function
```python
# services/backend-service/app/etl/jira_extraction.py (enhancement)
async def execute_statuses_and_relationships_extraction(
    integration_id: int,
    tenant_id: int,
    jira_client: JiraAPIClient
):
    """
    Execute the complete statuses and project relationships extraction.

    This function:
    1. Extracts all statuses from Jira
    2. Extracts project-status relationships
    3. Stores raw data in raw_extraction_data table
    4. Publishes transformation messages to queue
    """
    try:
        logger.info(f"Starting statuses extraction for integration {integration_id}")

        # Extract statuses
        statuses_data = await extract_statuses(jira_client)

        # Extract project-status relationships
        project_statuses_data = await extract_project_status_relationships(jira_client)

        # Store raw data
        await store_statuses_raw_data(integration_id, tenant_id, statuses_data, project_statuses_data)

        # Publish to transformation queue
        await publish_statuses_transformation_message(integration_id, tenant_id)

        logger.info(f"Statuses extraction completed for integration {integration_id}")

    except Exception as e:
        logger.error(f"Statuses extraction failed for integration {integration_id}: {e}")
        raise

async def extract_statuses(jira_client: JiraAPIClient) -> List[Dict[str, Any]]:
    """Extract all statuses from Jira API."""
    try:
        # Get all statuses
        response = await jira_client.get("/rest/api/3/status")
        statuses = response.json() if hasattr(response, 'json') else response

        logger.info(f"Extracted {len(statuses)} statuses from Jira")
        return statuses

    except Exception as e:
        logger.error(f"Failed to extract statuses: {e}")
        raise

async def extract_project_status_relationships(jira_client: JiraAPIClient) -> List[Dict[str, Any]]:
    """Extract project-status relationships from Jira API."""
    try:
        # Get all projects first
        projects_response = await jira_client.get("/rest/api/3/project")
        projects = projects_response.json() if hasattr(projects_response, 'json') else projects_response

        project_statuses = []

        for project in projects:
            try:
                # Get statuses for this project
                project_statuses_response = await jira_client.get(
                    f"/rest/api/3/project/{project['key']}/statuses"
                )
                project_status_data = project_statuses_response.json() if hasattr(project_statuses_response, 'json') else project_statuses_response

                project_statuses.append({
                    'project_id': project['id'],
                    'project_key': project['key'],
                    'project_name': project['name'],
                    'statuses': project_status_data
                })

            except Exception as e:
                logger.warning(f"Failed to get statuses for project {project['key']}: {e}")
                continue

        logger.info(f"Extracted status relationships for {len(project_statuses)} projects")
        return project_statuses

    except Exception as e:
        logger.error(f"Failed to extract project-status relationships: {e}")
        raise
```

### Task 2.2.3: Transform Worker Implementation
**Duration**: 2 days
**Priority**: HIGH

#### Statuses Transform Worker Enhancement
```python
# services/backend-service/app/workers/transform_worker.py (enhancement)
async def process_jira_statuses_and_relationships(self, message_data: Dict[str, Any]):
    """
    Process statuses and project-status relationships from raw data.

    This function:
    1. Retrieves raw data from raw_extraction_data table
    2. Processes statuses and saves to statuses table
    3. Processes project-status relationships and saves to projects_statuses table
    4. Updates job progress and status
    """
    try:
        integration_id = message_data['integration_id']
        tenant_id = message_data['tenant_id']
        extraction_id = message_data['extraction_id']

        logger.info(f"Processing statuses and relationships for extraction {extraction_id}")

        # Get raw data
        raw_data = await self.get_raw_extraction_data(extraction_id)

        # Process statuses
        await self.process_statuses(raw_data['statuses'], tenant_id)

        # Process project-status relationships
        await self.process_project_status_relationships(raw_data['project_statuses'], tenant_id)

        logger.info(f"Successfully processed statuses and relationships for extraction {extraction_id}")

    except Exception as e:
        logger.error(f"Failed to process statuses and relationships: {e}")
        raise

async def process_statuses(self, statuses_data: List[Dict[str, Any]], tenant_id: int):
    """Process and save statuses to database."""
    try:
        with get_db_session() as db:
            for status_data in statuses_data:
                # Check if status already exists
                existing_status = db.query(Status).filter(
                    Status.jira_status_id == status_data['id'],
                    Status.tenant_id == tenant_id
                ).first()

                if existing_status:
                    # Update existing status
                    existing_status.jira_status_name = status_data['name']
                    existing_status.jira_status_description = status_data.get('description', '')
                    existing_status.status_category = status_data.get('statusCategory', {}).get('name', '')
                    existing_status.updated_at = datetime.utcnow()
                else:
                    # Create new status
                    new_status = Status(
                        tenant_id=tenant_id,
                        jira_status_id=status_data['id'],
                        jira_status_name=status_data['name'],
                        jira_status_description=status_data.get('description', ''),
                        status_category=status_data.get('statusCategory', {}).get('name', ''),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(new_status)

            db.commit()
            logger.info(f"Processed {len(statuses_data)} statuses")

    except Exception as e:
        logger.error(f"Failed to process statuses: {e}")
        raise
```

### Task 2.2.2: Enhanced Issues Extraction Job
**Duration**: 2 days
**Priority**: HIGH

#### Dynamic Issues Extraction
```python
# ⚠️ UPDATED PATH: services/backend-service/app/etl/jobs/jira_issues_extract_job.py
# (etl-service is legacy - all ETL moved to backend-service/app/etl/)
class JiraIssuesExtractJob(BaseExtractJob):
    """Extract Jira issues with dynamic custom fields based on UI mappings"""
    
    def __init__(self, tenant_id: int, integration_id: int):
        super().__init__(tenant_id, integration_id)
        self.jira_client = JiraClient(integration_id)
    
    async def extract_data(self) -> List[Dict[str, Any]]:
        """Extract issues with project-specific field lists"""
        
        logger.info(f"Starting Jira issues extraction for integration {self.integration_id}")
        
        # Get projects for this integration
        projects = await self.get_integration_projects()
        
        all_issues = []
        
        for project in projects:
            try:
                logger.info(f"Extracting issues for project {project['key']}")
                
                # Get custom field mappings for this integration
                field_mappings = await self.get_custom_field_mappings()
                
                # Build dynamic field list
                fields_to_fetch = self.build_field_list(field_mappings, project['key'])
                
                # Extract issues for this project
                project_issues = await self.extract_project_issues(
                    project['key'], 
                    fields_to_fetch
                )
                
                # Add project context to each issue
                for issue in project_issues:
                    issue['project_id'] = project['id']
                    issue['project_key'] = project['key']
                
                all_issues.extend(project_issues)
                
                logger.info(f"Extracted {len(project_issues)} issues from project {project['key']}")
                
            except Exception as e:
                logger.error(f"Failed to extract issues from project {project['key']}: {e}")
                continue
        
        logger.info(f"Issues extraction completed. Total issues: {len(all_issues)}")
        return all_issues
    
    async def get_custom_field_mappings(self) -> Dict[str, str]:
        """Get custom field mappings from integration configuration"""
        
        # Query integrations table for custom_field_mappings JSONB
        # This would be replaced with actual database query
        return {
            'custom_field_01': 'customfield_10110',  # Aha! Epic URL
            'custom_field_02': 'customfield_10150',  # Aha! Initiative
            'custom_field_03': 'customfield_10359',  # Project Code
            'custom_field_04': 'customfield_10414',  # Team Codes
            'custom_field_05': 'customfield_12103',  # Epic Template
        }
    
    def build_field_list(self, field_mappings: Dict[str, str], project_key: str) -> List[str]:
        """Build dynamic field list based on mappings and project"""
        
        # Base fields (always needed)
        fields = [
            'key', 'summary', 'description', 'status', 'assignee', 'reporter',
            'priority', 'issuetype', 'project', 'created', 'updated', 'resolutiondate',
            'parent', 'resolution', 'labels', 'components', 'versions', 'fixVersions'
        ]
        
        # Add mapped custom fields
        mapped_fields = [field_id for field_id in field_mappings.values() if field_id]
        fields.extend(mapped_fields)
        
        # Add common fields that might go to overflow
        common_overflow_fields = [
            'customfield_10024',  # Story points
            'customfield_10128',  # Team
            'customfield_10000',  # Code changed
            'customfield_10222',  # Acceptance criteria
            'customfield_10011',  # Epic Name
        ]
        fields.extend(common_overflow_fields)
        
        # Get project-specific discovered fields (top 20 most common)
        discovered_fields = self.get_project_discovered_fields(project_key, limit=20)
        fields.extend(discovered_fields)
        
        # Remove duplicates and return
        return list(set(fields))
    
    def get_project_discovered_fields(self, project_key: str, limit: int = 20) -> List[str]:
        """Get most common discovered fields for a project"""
        
        # This would query projects_custom_fields table
        # Return top N most common fields for this project
        return [
            'customfield_11970',  # Business Area
            'customfield_12626',  # Request Details
            'customfield_15288',  # Additional field
        ]
    
    async def extract_project_issues(self, project_key: str, fields: List[str]) -> List[Dict[str, Any]]:
        """Extract issues for a specific project with dynamic field list"""
        
        # Get last sync date for incremental extraction
        last_sync = await self.get_last_sync_date(project_key)
        
        # Build JQL query for incremental sync
        jql = self.build_incremental_jql(project_key, last_sync)
        
        logger.info(f"Using JQL: {jql}")
        logger.info(f"Fetching {len(fields)} fields: {fields[:10]}...")  # Log first 10 fields
        
        # Extract issues in batches
        issues = []
        start_at = 0
        batch_size = 100
        
        while True:
            try:
                batch = await self.jira_client.search_issues(
                    jql=jql,
                    start_at=start_at,
                    max_results=batch_size,
                    fields=fields,
                    expand=['changelog', 'renderedFields']
                )
                
                if not batch.get('issues'):
                    break
                
                issues.extend(batch['issues'])
                start_at += batch_size
                
                logger.info(f"Fetched batch: {len(batch['issues'])} issues (total: {len(issues)})")
                
                if len(batch['issues']) < batch_size:
                    break
                    
            except Exception as e:
                logger.error(f"Failed to fetch batch starting at {start_at}: {e}")
                break
        
        return issues
    
    def build_incremental_jql(self, project_key: str, last_sync: str = None) -> str:
        """Build JQL query for incremental sync"""
        
        base_jql = f"project = {project_key}"
        
        if last_sync:
            # Incremental sync - get issues updated since last sync
            jql = f"{base_jql} AND updated >= '{last_sync}'"
        else:
            # Full sync - get all issues
            jql = base_jql
        
        # Order by updated date for consistent pagination
        jql += " ORDER BY updated ASC"
        
        return jql
    
    async def get_last_sync_date(self, project_key: str) -> str:
        """Get last sync date for incremental extraction"""
        
        # Query etl_jobs table for last successful run
        # Return in Jira-compatible format: "YYYY-MM-DD HH:MM"
        return "2025-01-01 00:00"  # Placeholder
    
    def get_entity_type(self) -> str:
        """Return entity type for this job"""
        return "jira_issues"
```

### Task 2.2.3: etl_jobs Table Integration
**Duration**: 2 days
**Priority**: HIGH

#### Job Orchestration with etl_jobs
```python
# ⚠️ UPDATED PATH: services/backend-service/app/etl/orchestration/jira_orchestrator.py
# (etl-service is legacy - all ETL moved to backend-service/app/etl/)
from app.core.database import get_database_connection
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class JiraJobOrchestrator:
    """Orchestrate Jira jobs using etl_jobs table"""
    
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.db = get_database_connection()
    
    async def schedule_jira_jobs(self, integration_id: int):
        """Schedule Jira jobs in etl_jobs table"""
        
        logger.info(f"Scheduling Jira jobs for integration {integration_id}")
        
        jobs_to_schedule = [
            {
                'job_name': f'jira_discovery_{integration_id}',
                'job_type': 'jira_discovery',
                'integration_id': integration_id,
                'schedule_interval_minutes': 1440,  # Daily discovery
                'retry_interval_minutes': 60,       # 1 hour retry
                'priority': 1,                      # High priority
                'max_retries': 3,
                'description': 'Discover custom fields and issue types from Jira projects'
            },
            {
                'job_name': f'jira_issues_{integration_id}',
                'job_type': 'jira_issues',
                'integration_id': integration_id,
                'schedule_interval_minutes': 360,   # 6 hours
                'retry_interval_minutes': 15,       # 15 min retry
                'priority': 5,                      # Normal priority
                'max_retries': 5,
                'depends_on': f'jira_discovery_{integration_id}',
                'description': 'Extract Jira issues with dynamic custom fields'
            }
        ]
        
        for job_config in jobs_to_schedule:
            await self.create_or_update_etl_job(job_config)
        
        logger.info(f"Scheduled {len(jobs_to_schedule)} Jira jobs")
    
    async def create_or_update_etl_job(self, job_config: Dict[str, Any]):
        """Create or update job in etl_jobs table"""
        
        try:
            # Check if job already exists
            existing_job = await self.db.fetchrow("""
                SELECT id FROM etl_jobs 
                WHERE job_name = $1 AND tenant_id = $2
            """, job_config['job_name'], self.tenant_id)
            
            if existing_job:
                # Update existing job
                await self.db.execute("""
                    UPDATE etl_jobs SET
                        job_type = $1,
                        integration_id = $2,
                        schedule_interval_minutes = $3,
                        retry_interval_minutes = $4,
                        priority = $5,
                        max_retries = $6,
                        depends_on = $7,
                        description = $8,
                        last_updated_at = NOW()
                    WHERE job_name = $9 AND tenant_id = $10
                """, 
                    job_config['job_type'],
                    job_config['integration_id'],
                    job_config['schedule_interval_minutes'],
                    job_config['retry_interval_minutes'],
                    job_config['priority'],
                    job_config.get('max_retries', 3),
                    job_config.get('depends_on'),
                    job_config.get('description'),
                    job_config['job_name'],
                    self.tenant_id
                )
                logger.info(f"Updated job: {job_config['job_name']}")
            else:
                # Create new job
                await self.db.execute("""
                    INSERT INTO etl_jobs (
                        job_name, job_type, integration_id, tenant_id,
                        schedule_interval_minutes, retry_interval_minutes,
                        priority, max_retries, depends_on, description,
                        status, created_at, last_updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'READY', NOW(), NOW()
                    )
                """,
                    job_config['job_name'],
                    job_config['job_type'],
                    job_config['integration_id'],
                    self.tenant_id,
                    job_config['schedule_interval_minutes'],
                    job_config['retry_interval_minutes'],
                    job_config['priority'],
                    job_config.get('max_retries', 3),
                    job_config.get('depends_on'),
                    job_config.get('description')
                )
                logger.info(f"Created job: {job_config['job_name']}")
                
        except Exception as e:
            logger.error(f"Failed to create/update job {job_config['job_name']}: {e}")
            raise
    
    async def get_ready_jobs(self) -> List[Dict[str, Any]]:
        """Get jobs that are ready to run"""
        
        return await self.db.fetch("""
            SELECT * FROM etl_jobs 
            WHERE tenant_id = $1 
            AND status = 'READY'
            AND (depends_on IS NULL OR depends_on IN (
                SELECT job_name FROM etl_jobs 
                WHERE tenant_id = $1 AND status = 'COMPLETED'
            ))
            ORDER BY priority ASC, created_at ASC
        """, self.tenant_id)
    
    async def update_job_status(self, job_name: str, status: str, progress: int = 0, error_message: str = None):
        """Update job status and progress"""
        
        await self.db.execute("""
            UPDATE etl_jobs SET
                status = $1,
                progress_percentage = $2,
                error_message = $3,
                last_updated_at = NOW(),
                last_run_started_at = CASE WHEN $1 = 'RUNNING' THEN NOW() ELSE last_run_started_at END,
                last_run_finished_at = CASE WHEN $1 IN ('COMPLETED', 'FAILED') THEN NOW() ELSE last_run_finished_at END
            WHERE job_name = $4 AND tenant_id = $5
        """, status, progress, error_message, job_name, self.tenant_id)
```

## ✅ Success Criteria

1. **API Endpoints**: Statuses and project relationships extraction endpoints working
2. **Data Extraction**: Complete statuses and project-status relationships extracted from Jira
3. **Raw Data Storage**: All extracted data stored in raw_extraction_data table
4. **Queue Processing**: Transform workers processing statuses data successfully
5. **Database Operations**: Statuses and projects_statuses tables populated correctly
6. **UI Integration**: ETL frontend can trigger and monitor statuses extraction
7. **Progress Tracking**: Real-time progress updates working

## 🚨 Risk Mitigation

1. **API Rate Limits**: Implement proper rate limiting for Jira API calls
2. **Large Datasets**: Handle large numbers of statuses and projects efficiently
3. **Data Consistency**: Ensure status relationships are correctly mapped
4. **Queue Failures**: Proper error handling and retry mechanisms for queue processing
5. **Database Performance**: Optimize bulk operations for statuses and relationships

## 📋 Implementation Checklist

- [ ] Create API endpoint `/jira/extract/statuses-and-relationships/{integration_id}`
- [ ] Implement `execute_statuses_and_relationships_extraction()` function
- [ ] Create `extract_statuses()` and `extract_project_status_relationships()` functions
- [ ] Implement raw data storage in `raw_extraction_data` table
- [ ] Add queue message publishing for transformation
- [ ] Enhance transform worker to process `jira_statuses_and_relationships` data type
- [ ] Implement `process_statuses()` and `process_project_status_relationships()` functions
- [ ] Add progress tracking with `StatusesExtractionProgressTracker`
- [ ] Integrate UI trigger button in ETL frontend
- [ ] Add error handling and retry mechanisms
- [ ] Test complete end-to-end flow
- [ ] Validate database operations and performance

## 🔄 Next Steps

After completion, this enables:
- **Phase 2.3**: Issues, Changelogs & Dev Status extraction
- **Complete Metadata Foundation**: All Jira metadata (projects, issue types, statuses) available
- **Foundation Ready**: Architecture proven for complex data extraction

**Mark as Implemented**: ✅ when all checklist items are complete and end-to-end flow is working.
