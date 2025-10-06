# ETL Phase 2.2: Jira Enhanced Extraction with Discovery

**Implemented**: NO ❌
**Duration**: 1 week (Week 6 of overall plan)
**Priority**: HIGH
**Risk Level**: MEDIUM
**Last Updated**: 2025-10-02

## 📊 Prerequisites (Must be complete before starting)

1. ✅ **Phase 2.1 Complete**: Database Foundation & UI Management
   - Custom field tables created
   - JSON overflow column added to work_items
   - Custom field mapping UI functional
   - Custom field discovery UI working

**Status**: Cannot start until Phase 2.1 is complete.

## 💼 Business Outcome

**Enhanced Jira Extraction with Project-Specific Discovery**: Implement intelligent Jira data extraction that:
- **Discovers custom fields** per project using createmeta API
- **Builds dynamic field lists** based on UI mappings
- **Extracts project-specific issue types** instead of scanning all Jira
- **Integrates with etl_jobs table** for job management
- **Supports incremental sync** with proper checkpoint management

This creates intelligent, efficient Jira extraction that adapts to project configurations.

## 🎯 Objectives

1. **Discovery Job**: Implement project-specific custom field discovery
2. **Enhanced Extraction**: Dynamic field lists based on UI configuration
3. **Issue Type Discovery**: Project-specific issue types from createmeta
4. **etl_jobs Integration**: Use etl_jobs table for job orchestration
5. **Performance**: Optimize API calls and reduce unnecessary data fetching

## 📋 Task Breakdown

### Task 2.2.1: Jira Discovery Job Implementation
**Duration**: 3 days
**Priority**: CRITICAL

#### Discovery Job Base Class
```python
# services/etl-service/app/jobs/jira/jira_discovery_job.py
from typing import Dict, Any, List
from app.jobs.base_job import BaseExtractJob
from app.integrations.jira_client import JiraClient
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class JiraDiscoveryJob(BaseExtractJob):
    """Discover project-specific custom fields and issue types using createmeta API"""
    
    def __init__(self, tenant_id: int, integration_id: int):
        super().__init__(tenant_id, integration_id)
        self.jira_client = JiraClient(integration_id)
    
    async def extract_data(self) -> List[Dict[str, Any]]:
        """Extract project metadata from createmeta endpoint"""
        
        logger.info(f"Starting Jira discovery for integration {self.integration_id}")
        
        # Get all projects for this integration
        projects = await self.get_integration_projects()
        logger.info(f"Found {len(projects)} projects to discover")
        
        discovery_data = []
        
        for project in projects:
            try:
                logger.info(f"Discovering metadata for project {project['key']}")
                
                # Call /rest/api/3/issue/createmeta for this project
                createmeta = await self.jira_client.get_createmeta(
                    project_keys=[project['key']],
                    expand='projects.issuetypes.fields'
                )
                
                # Extract custom fields and issue types
                project_data = self.extract_project_metadata(project, createmeta)
                discovery_data.append(project_data)
                
                logger.info(f"Discovered {len(project_data['custom_fields'])} custom fields and {len(project_data['issue_types'])} issue types for {project['key']}")
                
            except Exception as e:
                logger.error(f"Failed to discover metadata for project {project['key']}: {e}")
                # Continue with other projects
                continue
        
        logger.info(f"Discovery completed. Found metadata for {len(discovery_data)} projects")
        return discovery_data
    
    def extract_project_metadata(self, project: Dict, createmeta: Dict) -> Dict[str, Any]:
        """Extract custom fields and issue types from createmeta response"""
        
        custom_fields = []
        issue_types = []
        
        for project_data in createmeta.get('projects', []):
            if project_data.get('key') != project['key']:
                continue
                
            for issuetype in project_data.get('issuetypes', []):
                # Store issue type
                issue_types.append({
                    'jira_issuetype_id': issuetype['id'],
                    'jira_issuetype_name': issuetype['name'],
                    'jira_issuetype_description': issuetype.get('description', ''),
                    'hierarchy_level': issuetype.get('hierarchyLevel', 0),
                    'is_subtask': issuetype.get('subtask', False)
                })
                
                # Extract custom fields from this issue type
                for field_key, field_info in issuetype.get('fields', {}).items():
                    if field_key.startswith('customfield_'):
                        # Check if we already have this field (avoid duplicates across issue types)
                        existing_field = next(
                            (f for f in custom_fields if f['jira_field_id'] == field_key), 
                            None
                        )
                        
                        if not existing_field:
                            custom_fields.append({
                                'jira_field_id': field_key,
                                'jira_field_name': field_info.get('name', ''),
                                'jira_field_type': field_info.get('schema', {}).get('type', 'string'),
                                'jira_field_schema': field_info.get('schema', {}),
                                'is_required': field_info.get('required', False),
                                'has_default_value': field_info.get('hasDefaultValue', False)
                            })
        
        return {
            'project_id': project['id'],
            'project_key': project['key'],
            'project_name': project['name'],
            'custom_fields': custom_fields,
            'issue_types': issue_types,
            'discovery_timestamp': datetime.utcnow().isoformat()
        }
    
    async def get_integration_projects(self) -> List[Dict[str, Any]]:
        """Get projects for this integration from database"""
        
        # This would query the projects table
        # For now, return a sample - replace with actual DB query
        return [
            {'id': 1, 'key': 'BEN', 'name': 'Benefits Platform'},
            {'id': 2, 'key': 'HEALTH', 'name': 'Health Platform'}
        ]
    
    def get_entity_type(self) -> str:
        """Return entity type for this job"""
        return "jira_discovery"
    
    def get_extraction_metadata(self) -> Dict[str, Any]:
        """Return Jira-specific extraction metadata"""
        metadata = super().get_extraction_metadata()
        metadata.update({
            'discovery_type': 'project_metadata',
            'jira_instance': self.jira_client.base_url,
            'api_endpoint': '/rest/api/3/issue/createmeta'
        })
        return metadata
```

#### Enhanced Jira Client for Createmeta
```python
# services/etl-service/app/integrations/jira_client.py
class JiraClient:
    """Enhanced Jira client with createmeta support"""
    
    async def get_createmeta(self, project_keys: List[str], expand: str = None) -> Dict[str, Any]:
        """Get create metadata for projects"""
        
        try:
            params = {
                'projectKeys': ','.join(project_keys)
            }
            
            if expand:
                params['expand'] = expand
            
            response = await self.session.get(
                f"{self.base_url}/rest/api/3/issue/createmeta",
                params=params,
                auth=(self.username, self.token),
                timeout=30
            )
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get createmeta for projects {project_keys}: {e}")
            raise
    
    async def get_project_details(self, project_key: str) -> Dict[str, Any]:
        """Get detailed project information"""
        
        try:
            response = await self.session.get(
                f"{self.base_url}/rest/api/3/project/{project_key}",
                auth=(self.username, self.token),
                timeout=30
            )
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get project details for {project_key}: {e}")
            raise
```

### Task 2.2.2: Enhanced Issues Extraction Job
**Duration**: 2 days
**Priority**: HIGH

#### Dynamic Issues Extraction
```python
# services/etl-service/app/jobs/jira/jira_issues_extract_job.py
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
# services/etl-service/app/orchestration/jira_orchestrator.py
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

1. **Discovery Job**: Project-specific custom field discovery working
2. **Enhanced Extraction**: Dynamic field lists based on UI mappings
3. **Issue Type Discovery**: Project-specific issue types stored correctly
4. **etl_jobs Integration**: Jobs managed through etl_jobs table
5. **Performance**: Optimized API calls with reduced unnecessary data fetching

## 🚨 Risk Mitigation

1. **API Rate Limits**: Implement proper rate limiting and retry logic
2. **Large Projects**: Handle projects with many custom fields efficiently
3. **Discovery Failures**: Graceful handling when createmeta API fails
4. **Data Consistency**: Ensure discovered data is properly validated
5. **Job Dependencies**: Proper handling of job dependencies in etl_jobs

## 📋 Implementation Checklist

- [ ] Implement Jira discovery job with createmeta API
- [ ] Enhance Jira client with createmeta support
- [ ] Implement enhanced issues extraction with dynamic fields
- [ ] Create job orchestration using etl_jobs table
- [ ] Add job status tracking and progress updates
- [ ] Test discovery job with real Jira projects
- [ ] Test enhanced extraction with UI-configured mappings
- [ ] Validate job dependencies and scheduling
- [ ] Test incremental sync functionality
- [ ] Performance test with large projects

## 🔄 Next Steps

After completion, this enables:
- **Phase 2.3**: Transform & Load Processing with dynamic custom fields
- **Real-time discovery**: Projects automatically discover new custom fields
- **Efficient extraction**: Only fetch fields that are actually used

**Mark as Implemented**: ✅ when all checklist items are complete and jobs are running successfully.
