# ETL Phase 3: GitHub Repositories Recreation

**Implemented**: NO ❌
**Duration**: 1 week
**Priority**: HIGH
**Risk Level**: MEDIUM
**Last Updated**: 2025-10-21

## 📊 Prerequisites (Must be complete before starting)

1. ✅ **Phase 0 Complete**: ETL Frontend + Backend ETL Module working
2. ✅ **Phase 1 Complete**: RabbitMQ + Raw Data Storage + Queue Manager
3. ✅ **Phase 2 Complete**: Jira Enhancement with Queue-based Processing
   - Worker status updates working
   - WebSocket communication functional
   - Transform/embedding workers operational

**Status**: Ready to start after Phase 2 completion.

## 💼 Business Outcome

**GitHub Repository ETL with New Architecture**: Recreate GitHub repository discovery and management using the new queue-based ETL architecture, following the exact same approach as Jira:

- **Repository Discovery**: Extract repositories from GitHub API using integration settings
- **Queue-based Processing**: Extract → Transform → Embedding pipeline
- **Job Management**: Integrate with etl_jobs table and WebSocket status updates
- **Configuration-driven**: Use integration.settings for repository filtering
- **Incremental Sync**: Process only new/updated repositories since last sync

This establishes the foundation for GitHub PR/commit/review processing in Phase 4.

## 🎯 Objectives

1. **Repository Job Creation**: Add github_repositories job to etl_jobs table
2. **Extraction Logic**: Implement repository discovery using GitHub API
3. **Queue Integration**: Extract → Transform → Embedding pipeline for repositories
4. **WebSocket Updates**: Real-time status updates for all worker stages
5. **Configuration Support**: Use integration.settings for repository filtering
6. **Incremental Processing**: Only process new/updated repositories

## 📋 Task Breakdown

### Task 3.1: GitHub Repository Job Configuration
**Duration**: 1 day
**Priority**: HIGH

#### Add GitHub Repository Job to ETL Jobs Table
```python
# services/backend-service/app/etl/github_jobs.py
from app.models.unified_models import EtlJob
from app.core.database import get_write_session

async def create_github_repository_job(integration_id: int, tenant_id: int):
    """Create GitHub repository ETL job"""
    
    with get_write_session() as db:
        # Check if job already exists
        existing_job = db.query(EtlJob).filter(
            EtlJob.integration_id == integration_id,
            EtlJob.job_name == 'github_repositories'
        ).first()
        
        if existing_job:
            return existing_job
        
        # Create new GitHub repository job
        github_job = EtlJob(
            job_name='github_repositories',
            integration_id=integration_id,
            tenant_id=tenant_id,
            active=True,
            schedule_interval_minutes=1440,  # Daily
            status={
                "github_repositories": {
                    "order": 1,
                    "extraction": "idle",
                    "transform": "idle", 
                    "embedding": "idle",
                    "display_name": "GitHub Repositories"
                }
            },
            next_run=datetime.now(timezone.utc)
        )
        
        db.add(github_job)
        db.commit()
        return github_job
```

#### ETL Frontend Job Card Integration
```typescript
// services/frontend-etl/src/components/JobCard.tsx
interface JobStep {
  name: string;
  displayName: string;
  extraction: WorkerStatus;
  transform: WorkerStatus;
  embedding: WorkerStatus;
}

const getJobSteps = (jobName: string): JobStep[] => {
  switch (jobName) {
    case 'jira_sync':
      return [
        { name: 'jira_projects_and_issue_types', displayName: 'Projects & Issue Types', ... },
        { name: 'jira_statuses_and_relationships', displayName: 'Statuses & Relationships', ... },
        { name: 'jira_issues_with_changelogs', displayName: 'Issues & Changelogs', ... },
        { name: 'jira_dev_status', displayName: 'Development Status', ... }
      ];
    
    case 'github_repositories':
      return [
        { name: 'github_repositories', displayName: 'GitHub Repositories', ... }
      ];
    
    default:
      return [];
  }
};
```

### Task 3.2: GitHub Repository Extraction
**Duration**: 2 days
**Priority**: HIGH

#### Repository Extraction Logic
```python
# services/backend-service/app/etl/github_extraction.py
from typing import Dict, Any, List
from app.integrations.github_client import GitHubClient
from app.core.logging_config import get_logger

logger = get_logger(__name__)

async def extract_github_repositories(
    tenant_id: int,
    integration_id: int,
    job_id: int,
    last_sync_date: str = None
) -> Dict[str, Any]:
    """
    Extract GitHub repositories using integration settings.
    
    Similar to Jira extraction approach:
    1. Get integration settings for repository filtering
    2. Search repositories using GitHub API
    3. Store raw data in raw_extraction_data table
    4. Queue for transform processing
    """
    try:
        logger.info(f"Starting GitHub repository extraction for integration {integration_id}")
        
        # Get integration settings
        with get_read_session() as db:
            integration = db.query(Integration).filter(
                Integration.id == integration_id,
                Integration.tenant_id == tenant_id
            ).first()
            
            if not integration or not integration.active:
                return {'success': False, 'error': 'Integration not found or inactive'}
            
            settings = integration.settings or {}
            repository_filter = settings.get('repository_filter', '')
            
        # Initialize GitHub client
        github_client = GitHubClient(integration_id)
        
        # Search repositories based on filter
        repositories = []
        if repository_filter:
            # Search repositories by name filter
            search_query = f"user:{github_client.owner} {repository_filter} in:name"
            repos_response = await github_client.search_repositories(search_query)
            repositories.extend(repos_response.get('items', []))
        else:
            # Get all repositories for the organization/user
            repositories = await github_client.get_all_repositories()
        
        # Also get distinct repositories from work_items_prs_links
        with get_read_session() as db:
            existing_repos_query = text("""
                SELECT DISTINCT external_repo_id, repo_full_name
                FROM work_items_prs_links
                WHERE integration_id = :integration_id AND tenant_id = :tenant_id
                AND active = true
            """)
            existing_repos = db.execute(existing_repos_query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id
            }).fetchall()
            
            # Add repositories that exist in PR links but not in search results
            existing_repo_ids = {repo['id'] for repo in repositories}
            for repo_row in existing_repos:
                if repo_row[0] not in existing_repo_ids:
                    # Fetch repository details from GitHub API
                    repo_details = await github_client.get_repository_by_full_name(repo_row[1])
                    if repo_details:
                        repositories.append(repo_details)
        
        logger.info(f"Found {len(repositories)} repositories to process")
        
        # Store raw data and queue for processing
        raw_data_ids = []
        for i, repo in enumerate(repositories):
            first_item = (i == 0)
            last_item = (i == len(repositories) - 1)
            
            # Store in raw_extraction_data
            raw_data_id = await store_raw_extraction_data(
                tenant_id=tenant_id,
                integration_id=integration_id,
                entity_type='github_repositories',
                raw_data=repo,
                external_id=str(repo['id'])
            )
            raw_data_ids.append(raw_data_id)
            
            # Queue for transform
            await queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                raw_data_id=raw_data_id,
                data_type='github_repositories',
                job_id=job_id,
                provider='github',
                last_sync_date=last_sync_date,
                first_item=first_item,
                last_item=last_item,
                last_job_item=last_item  # Single step job
            )
        
        return {
            'success': True,
            'repositories_processed': len(repositories),
            'raw_data_ids': raw_data_ids
        }
        
    except Exception as e:
        logger.error(f"Error in GitHub repository extraction: {e}")
        return {'success': False, 'error': str(e)}
```

### Task 3.3: GitHub Repository Transform Worker
**Duration**: 2 days
**Priority**: HIGH

#### Transform Worker Implementation
```python
# services/backend-service/app/workers/transform_worker.py (add method)

def _process_github_repositories(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
    """
    Process GitHub repository data from raw_extraction_data.
    
    Flow:
    1. Load raw data from raw_extraction_data table
    2. Transform repository data to repositories table format
    3. Bulk insert/update repositories table
    4. Queue for vectorization
    """
    try:
        # 🎯 HANDLE COMPLETION MESSAGE: raw_data_id=None signals job completion
        if raw_data_id is None and message and message.get('last_job_item'):
            logger.info(f"[COMPLETION] Received completion message for github_repositories (no data to process)")
            
            # Send completion message to embedding queue
            self._queue_entities_for_embedding(
                tenant_id=tenant_id,
                table_name='repositories',
                entities=[],  # Empty list
                job_id=job_id,
                message_type='github_repositories',
                integration_id=integration_id,
                provider='github',
                last_sync_date=message.get('last_sync_date'),
                first_item=True,
                last_item=True,
                last_job_item=True  # 🎯 Signal job completion to embedding worker
            )
            
            logger.info(f"✅ Sent completion message to embedding queue")
            return True
        
        # 🎯 DEBUG: Log message flags for repository processing
        first_item = message.get('first_item', False) if message else False
        last_item = message.get('last_item', False) if message else False
        last_job_item = message.get('last_job_item', False) if message else False
        
        logger.info(f"🎯 [GITHUB_REPOS] Processing github_repositories for raw_data_id={raw_data_id} (first={first_item}, last={last_item}, job_end={last_job_item})")
        
        # ✅ Send transform worker "running" status when first_item=True
        if message and message.get('first_item') and job_id:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "running", "github_repositories"))
                logger.info(f"✅ Transform worker marked as running for github_repositories (first_item=True)")
            finally:
                loop.close()
        
        with self.get_db_session() as db:
            # Load raw data
            raw_data = self._get_raw_data(db, raw_data_id)
            if not raw_data:
                logger.error(f"Raw data {raw_data_id} not found")
                return False
            
            repo_data = raw_data.get('raw_data', {})
            
            # Transform repository data
            transformed_repo = {
                'external_id': str(repo_data.get('id')),
                'name': repo_data.get('name'),
                'full_name': repo_data.get('full_name'),
                'description': repo_data.get('description'),
                'url': repo_data.get('html_url'),
                'is_private': repo_data.get('private', False),
                'repo_created_at': self._parse_datetime(repo_data.get('created_at')),
                'repo_updated_at': self._parse_datetime(repo_data.get('updated_at')),
                'pushed_at': self._parse_datetime(repo_data.get('pushed_at')),
                'language': repo_data.get('language'),
                'default_branch': repo_data.get('default_branch'),
                'archived': repo_data.get('archived', False),
                'integration_id': integration_id,
                'tenant_id': tenant_id,
                'active': True
            }
            
            # Upsert repository
            upsert_query = text("""
                INSERT INTO repositories (
                    external_id, name, full_name, description, url, is_private,
                    repo_created_at, repo_updated_at, pushed_at, language,
                    default_branch, archived, integration_id, tenant_id, active,
                    created_at, last_updated_at
                ) VALUES (
                    :external_id, :name, :full_name, :description, :url, :is_private,
                    :repo_created_at, :repo_updated_at, :pushed_at, :language,
                    :default_branch, :archived, :integration_id, :tenant_id, :active,
                    NOW(), NOW()
                )
                ON CONFLICT (external_id, tenant_id)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    full_name = EXCLUDED.full_name,
                    description = EXCLUDED.description,
                    url = EXCLUDED.url,
                    is_private = EXCLUDED.is_private,
                    repo_updated_at = EXCLUDED.repo_updated_at,
                    pushed_at = EXCLUDED.pushed_at,
                    language = EXCLUDED.language,
                    default_branch = EXCLUDED.default_branch,
                    archived = EXCLUDED.archived,
                    active = EXCLUDED.active,
                    last_updated_at = NOW()
                RETURNING id, external_id
            """)
            
            result = db.execute(upsert_query, transformed_repo)
            repo_record = result.fetchone()
            
            if repo_record:
                # Queue for embedding
                self._queue_entities_for_embedding(
                    tenant_id=tenant_id,
                    table_name='repositories',
                    entities=[{
                        'id': repo_record[0],
                        'external_id': repo_record[1]
                    }],
                    job_id=job_id,
                    message_type='github_repositories',
                    integration_id=integration_id,
                    provider=message.get('provider', 'github'),
                    last_sync_date=message.get('last_sync_date'),
                    first_item=message.get('first_item', False),
                    last_item=message.get('last_item', False),
                    last_job_item=message.get('last_job_item', False)
                )
                
                logger.info(f"✅ Processed repository {transformed_repo['full_name']} and queued for embedding")
            
            # ✅ Send transform worker "finished" status when last_item=True
            if message and message.get('last_item') and job_id:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "finished", "github_repositories"))
                    logger.info(f"✅ Transform worker marked as finished for github_repositories")
                finally:
                    loop.close()
            
            return True
            
    except Exception as e:
        logger.error(f"Error processing github_repositories: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False
```

## ✅ Success Criteria

1. **Job Integration**: GitHub repository job properly integrated with etl_jobs table
2. **Repository Discovery**: All repositories discovered using integration settings + PR links
3. **Queue Processing**: Extract → Transform → Embedding pipeline working
4. **WebSocket Updates**: Real-time status updates for all worker stages
5. **Data Consistency**: Repository data properly stored in repositories table
6. **Incremental Sync**: Only new/updated repositories processed

## 🚨 Risk Mitigation

1. **API Rate Limits**: Implement proper GitHub API rate limiting
2. **Large Repository Sets**: Handle pagination for organizations with many repositories
3. **Configuration Errors**: Validate integration settings before processing
4. **Worker Failures**: Implement proper error handling and retry logic
5. **Data Integrity**: Ensure repository data consistency across processing stages

## 📋 Implementation Checklist

- [ ] Add github_repositories job to etl_jobs table structure
- [ ] Implement GitHub repository extraction logic
- [ ] Add repository transform processing to transform worker
- [ ] Update ETL frontend to display GitHub repository job card
- [ ] Implement WebSocket status updates for all worker stages
- [ ] Add repository filtering based on integration settings
- [ ] Include repositories from existing work_items_prs_links
- [ ] Test complete pipeline end-to-end
- [ ] Validate incremental sync functionality
- [ ] Test error handling and recovery scenarios

## 🔄 Next Steps

After completion, this enables:
- **Phase 4**: GitHub PR/Commit/Review processing using GraphQL
- **Repository Foundation**: Established repository data for PR processing
- **Consistent Architecture**: Same queue-based approach as Jira
- **Scalable Processing**: Ready for high-volume GitHub data extraction
