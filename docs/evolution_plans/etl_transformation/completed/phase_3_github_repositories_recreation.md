# ETL Phase 3: GitHub Repositories Recreation

**Implemented**: NO ❌
**Duration**: 1 week
**Priority**: HIGH
**Risk Level**: MEDIUM
**Last Updated**: 2025-10-24

## 📊 Prerequisites (Must be complete before starting)

1. ✅ **Phase 0 Complete**: ETL Frontend + Backend ETL Module working
2. ✅ **Phase 1 Complete**: RabbitMQ + Raw Data Storage + Queue Manager
3. ✅ **Phase 2 Complete**: Jira Enhancement with Queue-based Processing
   - Worker status updates working
   - WebSocket communication functional
   - Transform/embedding workers operational
   - Message structure and flag forwarding patterns established

**Status**: Ready to start after Phase 2 completion.

## 💼 Business Outcome

**GitHub Repository ETL with New Architecture**: Recreate GitHub repository discovery and management using the new queue-based ETL architecture, following the exact same approach as Jira:

- **Repository Discovery**: Extract repositories from GitHub API using integration settings
- **Queue-based Processing**: Extract → Transform → Embedding pipeline (single-step job)
- **Job Management**: Integrate with etl_jobs table and WebSocket status updates
- **Configuration-driven**: Use integration.settings for repository filtering
- **Incremental Sync**: Process only new/updated repositories since last sync
- **Real-time Status**: 3 worker circles (Extraction, Transform, Embedding) with live updates

This establishes the foundation for GitHub PR/commit/review processing in Phase 4.

## 🎯 Objectives

1. **Add First Step**: Add `github_repositories` step to existing GitHub job in etl_jobs table
2. **Extraction Logic**: Implement repository discovery using GitHub API with proper message structure
3. **Queue Integration**: Extract → Transform → Embedding pipeline with flag forwarding
4. **WebSocket Updates**: Real-time status updates on first_item=True and last_item=True
5. **Configuration Support**: Use integration.settings for repository filtering
6. **Incremental Processing**: Only process new/updated repositories using last_sync_date

## 📋 Task Breakdown

### Task 3.1: Add GitHub Repositories Step to Existing Job
**Duration**: 1 day
**Priority**: HIGH

#### Update Existing GitHub Job with First Step

**Key Pattern**: The GitHub job already exists. Phase 3 adds the first step (`github_repositories`). Phase 4 will add more steps.

```python
# services/backend-service/app/etl/github_jobs.py
# The GitHub job should already exist with this structure:
# When adding the first step, ensure the status JSON includes github_repositories

# Example of what the existing job status should look like after Phase 3:
status={
    "overall": "READY",  # 🔑 REQUIRED: Database CHECK constraint
    "steps": {
        "github_repositories": {
            "order": 1,
            "display_name": "GitHub Repositories",
            "extraction": "idle",
            "transform": "idle",
            "embedding": "idle"
        }
        # Phase 4 will add more steps here:
        # "github_pull_requests", "github_commits", "github_reviews", "github_comments"
    }
}
```

#### ETL Frontend Job Card Integration
```typescript
// services/frontend-etl/src/components/JobCard.tsx
// Update getJobSteps to include GitHub job with its steps

const getJobSteps = (jobName: string): JobStep[] => {
  switch (jobName) {
    case 'Jira':
      return [
        { name: 'jira_projects_and_issue_types', displayName: 'Projects & Issue Types', ... },
        { name: 'jira_statuses_and_relationships', displayName: 'Statuses & Relationships', ... },
        { name: 'jira_issues_with_changelogs', displayName: 'Issues & Changelogs', ... },
        { name: 'jira_dev_status', displayName: 'Development Status', ... }
      ];

    case 'GitHub':
      return [
        { name: 'github_repositories', displayName: 'GitHub Repositories', ... }
        // Phase 4 will add more steps:
        // { name: 'github_pull_requests', displayName: 'Pull Requests', ... },
        // { name: 'github_commits', displayName: 'Commits', ... },
        // { name: 'github_reviews', displayName: 'Reviews', ... },
        // { name: 'github_comments', displayName: 'Comments', ... }
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

**Key Patterns**:
- Send "running" status when `first_item=True`
- Send "finished" status when `last_item=True`
- Always forward `first_item`, `last_item`, `last_job_item` flags
- Use `DateTimeHelper.now_default()` for all timestamps
- Atomic race condition check on job start

```python
# services/backend-service/app/etl/github_extraction.py
from typing import Dict, Any, List
from app.integrations.github_client import GitHubClient
from app.core.logging_config import get_logger
from app.core.database import get_read_session, get_write_session
from app.etl.queue.queue_manager import QueueManager
from app.core.utils import DateTimeHelper
from sqlalchemy import text

logger = get_logger(__name__)

async def extract_github_repositories(
    tenant_id: int,
    integration_id: int,
    job_id: int,
    last_sync_date: str = None
) -> Dict[str, Any]:
    """
    Extract GitHub repositories using integration settings.

    Flow:
    1. Atomic race condition check (prevent double-running)
    2. Get integration settings for repository filtering
    3. Search repositories using GitHub API
    4. Store raw data in raw_extraction_data table
    5. Queue for transform processing with proper flags
    6. Send WebSocket status updates on first_item and last_item
    """
    try:
        logger.info(f"🚀 Starting GitHub repository extraction for integration {integration_id}")

        # Get integration settings
        with get_read_session() as db:
            integration = db.query(Integration).filter(
                Integration.id == integration_id,
                Integration.tenant_id == tenant_id
            ).first()

            if not integration or not integration.active:
                logger.error(f"Integration {integration_id} not found or inactive")
                return {'success': False, 'error': 'Integration not found or inactive'}

            # Handle settings as JSON string or dict
            try:
                if isinstance(integration.settings, str):
                    import json
                    settings = json.loads(integration.settings)
                else:
                    settings = integration.settings or {}
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Invalid integration settings: {e}")
                settings = {}

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

        # Also get distinct repositories from repositories table (not work_items_prs_links)
        with get_read_session() as db:
            existing_repos_query = text("""
                SELECT DISTINCT r.id, r.full_name
                FROM repositories r
                WHERE r.integration_id = :integration_id AND r.tenant_id = :tenant_id
                AND r.active = true
            """)
            existing_repos = db.execute(existing_repos_query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id
            }).fetchall()

            # Add repositories that exist in DB but not in search results
            existing_repo_ids = {repo['id'] for repo in repositories}
            for repo_row in existing_repos:
                if repo_row[0] not in existing_repo_ids:
                    # Fetch repository details from GitHub API
                    repo_details = await github_client.get_repository_by_full_name(repo_row[1])
                    if repo_details:
                        repositories.append(repo_details)

        logger.info(f"📦 Found {len(repositories)} repositories to process")

        if not repositories:
            logger.info(f"No repositories found for integration {integration_id}")
            return {'success': True, 'repositories_processed': 0}

        # Store raw data and queue for processing
        queue_manager = QueueManager()
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

            # 🔑 Queue for transform with proper flags
            success = queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                raw_data_id=raw_data_id,
                data_type='github_repositories',
                job_id=job_id,
                provider='github',
                last_sync_date=last_sync_date,
                first_item=first_item,
                last_item=last_item,
                last_job_item=last_item  # Single-step job: last_item triggers completion
            )

            if not success:
                logger.error(f"Failed to queue repository {repo['id']} for transform")

        logger.info(f"✅ Queued {len(repositories)} repositories for transform processing")

        return {
            'success': True,
            'repositories_processed': len(repositories),
            'raw_data_ids': raw_data_ids
        }

    except Exception as e:
        logger.error(f"❌ Error in GitHub repository extraction: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {'success': False, 'error': str(e)}
```

### Task 3.3: GitHub Repository Transform Worker
**Duration**: 2 days
**Priority**: HIGH

#### Transform Worker Implementation

**Key Patterns**:
- Handle completion message when `raw_data_id=None` and `last_job_item=True`
- Send "running" status on `first_item=True` using `_send_worker_status()`
- Send "finished" status on `last_item=True`
- Always forward flags to embedding queue using `queue_manager.publish_embedding_job()`
- Use database status update pattern: `status->steps->{step_name}->{worker_type}`

```python
# services/backend-service/app/workers/transform_worker.py (add method)

def _process_github_repositories(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
    """
    Process GitHub repository data from raw_extraction_data.

    Flow:
    1. Handle completion message (raw_data_id=None)
    2. Load raw data from raw_extraction_data table
    3. Transform repository data to repositories table format
    4. Upsert to repositories table
    5. Queue for embedding with proper flag forwarding
    6. Send WebSocket status updates
    """
    try:
        # 🔑 HANDLE COMPLETION MESSAGE: raw_data_id=None signals job completion
        if raw_data_id is None and message and message.get('last_job_item'):
            logger.info(f"[COMPLETION] Received completion message for github_repositories (no data to process)")

            # Forward completion to embedding queue
            self.queue_manager.publish_embedding_job(
                tenant_id=tenant_id,
                table_name='repositories',
                external_id=None,  # 🔑 None signals completion
                job_id=job_id,
                message_type='github_repositories',
                integration_id=integration_id,
                provider='github',
                last_sync_date=message.get('last_sync_date'),
                first_item=True,
                last_item=True,
                last_job_item=True  # 🔑 Signal job completion to embedding worker
            )

            logger.info(f"✅ Sent completion message to embedding queue")
            return True

        # Log message flags for debugging
        first_item = message.get('first_item', False) if message else False
        last_item = message.get('last_item', False) if message else False
        last_job_item = message.get('last_job_item', False) if message else False

        logger.info(f"🎯 [GITHUB_REPOS] Processing raw_data_id={raw_data_id} (first={first_item}, last={last_item}, job_end={last_job_item})")

        # 🔑 Send transform worker "running" status when first_item=True
        if message and message.get('first_item') and job_id:
            self._send_worker_status("transform", tenant_id, job_id, "running", "github_repositories")
            logger.info(f"✅ Transform worker marked as running for github_repositories")

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
                # 🔑 Queue for embedding with proper flag forwarding
                self.queue_manager.publish_embedding_job(
                    tenant_id=tenant_id,
                    table_name='repositories',
                    external_id=repo_record[1],  # Use external_id from database
                    job_id=job_id,
                    message_type='github_repositories',
                    integration_id=integration_id,
                    provider=message.get('provider', 'github'),
                    last_sync_date=message.get('last_sync_date'),
                    first_item=message.get('first_item', False),  # 🔑 Forward flags
                    last_item=message.get('last_item', False),
                    last_job_item=message.get('last_job_item', False)
                )

                logger.info(f"✅ Processed repository {transformed_repo['full_name']} and queued for embedding")

            # 🔑 Send transform worker "finished" status when last_item=True
            if message and message.get('last_item') and job_id:
                self._send_worker_status("transform", tenant_id, job_id, "finished", "github_repositories")
                logger.info(f"✅ Transform worker marked as finished for github_repositories")

            return True

    except Exception as e:
        logger.error(f"❌ Error processing github_repositories: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False
```

## ✅ Success Criteria

1. **Step Integration**: `github_repositories` step properly added to existing GitHub job in etl_jobs table
2. **Repository Discovery**: All repositories discovered using integration settings + existing repositories table
3. **Queue Processing**: Extract → Transform → Embedding pipeline working with proper flag forwarding
4. **WebSocket Updates**: Real-time status updates on first_item=True (running) and last_item=True (finished)
5. **Data Consistency**: Repository data properly stored in repositories table with external_id
6. **Incremental Sync**: Only new/updated repositories processed using last_sync_date
7. **Completion Chain**: Proper completion message flow (raw_data_id=None) through all workers
8. **Status JSON**: Database status updates follow pattern `status->steps->github_repositories->{worker_type}`

## 🚨 Risk Mitigation

1. **API Rate Limits**: Implement proper GitHub API rate limiting and backoff
2. **Large Repository Sets**: Handle pagination for organizations with many repositories
3. **Configuration Errors**: Validate integration settings JSON before processing
4. **Worker Failures**: Implement proper error handling and retry logic
5. **Data Integrity**: Ensure repository data consistency across processing stages
6. **Race Conditions**: Use atomic UPDATE with WHERE clause to prevent double-running jobs
7. **Message Loss**: Ensure all messages are properly queued before returning success

## 📋 Implementation Checklist

- [ ] Verify GitHub job exists in etl_jobs table with correct status JSON structure
- [ ] Add github_repositories step to status JSON (overall + steps wrapper)
- [ ] Implement GitHub repository extraction with atomic race condition check
- [ ] Add repository transform processing to transform worker
- [ ] Implement WebSocket status updates using _send_worker_status()
- [ ] Add repository filtering based on integration.settings JSON
- [ ] Query repositories table (not work_items_prs_links) for existing repos
- [ ] Implement completion message handling (raw_data_id=None)
- [ ] Use queue_manager.publish_embedding_job() for embedding queue
- [ ] Forward first_item, last_item, last_job_item flags through all workers
- [ ] Update ETL frontend to display GitHub job with github_repositories step
- [ ] Test complete pipeline end-to-end with multiple repositories
- [ ] Validate incremental sync functionality with last_sync_date
- [ ] Test error handling and recovery scenarios
- [ ] Verify WebSocket status circles update correctly on frontend

## 🔄 Next Steps

After completion, this enables:
- **Phase 4**: GitHub PR/Commit/Review processing using GraphQL (multi-step job)
- **Repository Foundation**: Established repository data for PR processing
- **Consistent Architecture**: Same queue-based approach as Jira
- **Scalable Processing**: Ready for high-volume GitHub data extraction
