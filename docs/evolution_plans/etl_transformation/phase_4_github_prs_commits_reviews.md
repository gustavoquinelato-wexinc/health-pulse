# ETL Phase 4: GitHub PRs, Commits & Reviews with GraphQL

**Implemented**: NO ❌
**Duration**: 2 weeks
**Priority**: HIGH
**Risk Level**: MEDIUM
**Last Updated**: 2025-10-24

## 📊 Prerequisites (Must be complete before starting)

1. ✅ **Phase 0 Complete**: ETL Frontend + Backend ETL Module working
2. ✅ **Phase 1 Complete**: RabbitMQ + Raw Data Storage + Queue Manager
3. ✅ **Phase 2 Complete**: Jira Enhancement with Queue-based Processing
4. ✅ **Phase 3 Complete**: GitHub Repository Recreation
   - Repository discovery working
   - Repository data in repositories table
   - Queue-based processing established
   - Single-step job pattern understood

**Status**: Ready to start after Phase 3 completion.

## 💼 Business Outcome

**GitHub PR/Commit/Review ETL with GraphQL**: Implement comprehensive GitHub data extraction using GraphQL API with queue-based processing and recovery logic:

- **GraphQL Integration**: Efficient bulk data fetching using GitHub GraphQL API
- **Multi-step Processing**: PRs → Commits → Reviews → Comments pipeline (4-step job like Jira)
- **Queue-based Architecture**: Extract → Transform → Embedding for each entity type
- **Recovery Logic**: Resume processing from checkpoints on failures
- **WebSocket Updates**: Real-time status updates for all processing stages (3 circles per step)
- **Incremental Sync**: Process only new/updated data since last sync
- **Proper Flag Forwarding**: first_item, last_item, last_job_item forwarded through all workers

This completes the GitHub ETL migration to the new architecture.

## 🎯 Objectives

1. **Add More Steps**: Add `github_pull_requests`, `github_commits`, `github_reviews`, `github_comments` steps to existing GitHub job
2. **GraphQL Extraction**: Implement efficient GraphQL-based data extraction with pagination
3. **Recovery Mechanisms**: Checkpoint-based recovery for large datasets
4. **Queue Integration**: Full Extract → Transform → Embedding pipeline with proper flag forwarding
5. **WebSocket Updates**: Real-time status updates for all worker stages (running/finished)
6. **Data Relationships**: Maintain PR → Commit → Review → Comment relationships
7. **Completion Chain**: Proper completion message flow through all 4 steps

## 📋 Task Breakdown

### Task 4.1: Add More Steps to Existing GitHub Job
**Duration**: 2 days
**Priority**: HIGH

#### Update Existing GitHub Job with Additional Steps

**Key Pattern**: The GitHub job already exists from Phase 3. Phase 4 adds 4 more steps to it.

```python
# services/backend-service/app/etl/github_jobs.py
# The GitHub job should be updated to include all 5 steps:

# After Phase 4, the status JSON should look like:
status={
    "overall": "READY",  # 🔑 REQUIRED: Database CHECK constraint
    "steps": {
        "github_repositories": {
            "order": 1,
            "display_name": "GitHub Repositories",
            "extraction": "idle",
            "transform": "idle",
            "embedding": "idle"
        },
        "github_pull_requests": {
            "order": 2,
            "display_name": "Pull Requests",
            "extraction": "idle",
            "transform": "idle",
            "embedding": "idle"
        },
        "github_commits": {
            "order": 3,
            "display_name": "Commits",
            "extraction": "idle",
            "transform": "idle",
            "embedding": "idle"
        },
        "github_reviews": {
            "order": 4,
            "display_name": "Reviews",
            "extraction": "idle",
            "transform": "idle",
            "embedding": "idle"
        },
        "github_comments": {
            "order": 5,
            "display_name": "Comments",
            "extraction": "idle",
            "transform": "idle",
            "embedding": "idle"
        }
    }
}
```

#### ETL Frontend Multi-step Job Card
```typescript
// services/frontend-etl/src/components/JobCard.tsx
// Update getJobSteps to include all GitHub steps

const getJobSteps = (jobName: string): JobStep[] => {
  switch (jobName) {
    case 'GitHub':
      return [
        { name: 'github_repositories', displayName: 'GitHub Repositories', ... },
        { name: 'github_pull_requests', displayName: 'Pull Requests', ... },
        { name: 'github_commits', displayName: 'Commits', ... },
        { name: 'github_reviews', displayName: 'Reviews', ... },
        { name: 'github_comments', displayName: 'Comments', ... }
      ];

    default:
      return [];
  }
};
```

### Task 4.2: GitHub GraphQL Extraction with Recovery
**Duration**: 4 days
**Priority**: HIGH

#### GraphQL PR Extraction with Checkpoints

**Key Patterns**:
- Multi-step job: PRs → Commits → Reviews → Comments
- Each step sends `last_item=True` to trigger next step's extraction
- Only final step (Comments) has `last_job_item=True`
- Send WebSocket status on first_item=True (running) and last_item=True (finished)
- Use `DateTimeHelper.now_default()` for timestamps

```python
# services/backend-service/app/etl/github_extraction.py
from typing import Dict, Any, List
from app.integrations.github_client import GitHubGraphQLClient
from app.core.logging_config import get_logger
from app.core.database import get_read_session, get_write_session
from app.etl.queue.queue_manager import QueueManager
from app.core.utils import DateTimeHelper
from sqlalchemy import text

logger = get_logger(__name__)

async def extract_github_pull_requests(
    tenant_id: int,
    integration_id: int,
    job_id: int,
    last_sync_date: str = None
) -> Dict[str, Any]:
    """
    Extract GitHub PRs using GraphQL with checkpoint recovery.

    Flow:
    1. Get all repositories for this integration
    2. For each repository, extract PRs using GraphQL with pagination
    3. Store raw PR data in raw_extraction_data table
    4. Queue all PRs for transform processing
    5. When last_item=True, trigger commits extraction (next step)
    """
    try:
        logger.info(f"🚀 Starting GitHub PR extraction for integration {integration_id}")

        # Get repositories for this integration
        with get_read_session() as db:
            repositories = db.query(Repository).filter(
                Repository.integration_id == integration_id,
                Repository.tenant_id == tenant_id,
                Repository.active == True
            ).all()

        if not repositories:
            logger.warning(f"No repositories found for integration {integration_id}")
            # Send completion message to trigger next step (commits)
            queue_manager = QueueManager()
            queue_manager.publish_extraction_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                job_id=job_id,
                extraction_type='github_commits',
                extraction_data={},
                provider='github',
                last_sync_date=last_sync_date,
                first_item=True,
                last_item=True,
                last_job_item=False  # Not the final step
            )
            return {'success': True, 'prs_processed': 0}

        # Initialize GraphQL client
        github_client = GitHubGraphQLClient(integration_id)
        queue_manager = QueueManager()

        total_prs = 0
        pr_extraction_jobs = []

        # Process each repository
        for repo_idx, repository in enumerate(repositories):
            owner, repo_name = repository.full_name.split('/', 1)

            # Get PRs for this repository using GraphQL with pagination
            pr_cursor = None

            while True:
                # Fetch batch of PRs with GraphQL
                response = await github_client.get_pull_requests_with_details(
                    owner, repo_name, pr_cursor, last_sync_date
                )

                if not response or 'data' not in response:
                    break

                prs = response['data']['repository']['pullRequests']['nodes']
                if not prs:
                    break

                # Store each PR as raw data
                for pr_data in prs:
                    # Store in raw_extraction_data
                    raw_data_id = await store_raw_extraction_data(
                        tenant_id=tenant_id,
                        integration_id=integration_id,
                        entity_type='github_pull_requests',
                        raw_data=pr_data,
                        external_id=pr_data['id']
                    )

                    pr_extraction_jobs.append({
                        'raw_data_id': raw_data_id,
                        'pr_number': pr_data['number'],
                        'repository_id': repository.id
                    })

                    total_prs += 1

                # Check for pagination
                page_info = response['data']['repository']['pullRequests']['pageInfo']
                if not page_info['hasNextPage']:
                    break
                pr_cursor = page_info['endCursor']

        logger.info(f"📦 Found {total_prs} PRs across {len(repositories)} repositories")

        # Queue all PRs for transform processing
        for i, pr_job in enumerate(pr_extraction_jobs):
            first_item = (i == 0)
            last_item = (i == len(pr_extraction_jobs) - 1)

            queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                raw_data_id=pr_job['raw_data_id'],
                data_type='github_pull_requests',
                job_id=job_id,
                provider='github',
                last_sync_date=last_sync_date,
                first_item=first_item,
                last_item=last_item,
                last_job_item=False  # Not the final step
            )

        # 🔑 When last_item=True, trigger commits extraction (next step)
        if pr_extraction_jobs:
            queue_manager.publish_extraction_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                job_id=job_id,
                extraction_type='github_commits',
                extraction_data={'trigger_from': 'pull_requests'},
                provider='github',
                last_sync_date=last_sync_date,
                first_item=True,
                last_item=True,
                last_job_item=False  # Not the final step
            )

        return {
            'success': True,
            'prs_processed': total_prs,
            'repositories_processed': len(repositories)
        }

    except Exception as e:
        logger.error(f"❌ Error in GitHub PR extraction: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {'success': False, 'error': str(e)}


async def extract_github_commits(
    tenant_id: int,
    integration_id: int,
    job_id: int,
    last_sync_date: str = None
) -> Dict[str, Any]:
    """
    Extract GitHub commits for recent PRs using GraphQL.

    Flow:
    1. Get recent PRs from prs table
    2. For each PR, extract commits using GraphQL
    3. Store raw commit data
    4. Queue for transform processing
    5. When last_item=True, trigger reviews extraction (next step)
    """
    try:
        logger.info(f"🚀 Starting GitHub commit extraction for integration {integration_id}")

        queue_manager = QueueManager()

        # Get recent PRs that might have new commits
        with get_read_session() as db:
            recent_prs = db.query(Pr).filter(
                Pr.integration_id == integration_id,
                Pr.tenant_id == tenant_id,
                Pr.active == True
            ).limit(100).all()  # Process recent PRs

        if not recent_prs:
            logger.warning(f"No PRs found for commit extraction")
            # Trigger reviews extraction (next step)
            queue_manager.publish_extraction_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                job_id=job_id,
                extraction_type='github_reviews',
                extraction_data={'trigger_from': 'commits'},
                provider='github',
                last_sync_date=last_sync_date,
                first_item=True,
                last_item=True,
                last_job_item=False
            )
            return {'success': True, 'commits_processed': 0}

        # Extract commits for each PR using GraphQL
        github_client = GitHubGraphQLClient(integration_id)
        total_commits = 0
        commit_extraction_jobs = []

        for pr in recent_prs:
            # Get repository info
            with get_read_session() as db:
                repository = db.query(Repository).get(pr.repository_id)

            if not repository:
                continue

            owner, repo_name = repository.full_name.split('/', 1)

            # Get commits for this PR using GraphQL
            commits_response = await github_client.get_pr_commits(
                owner, repo_name, pr.number
            )

            if commits_response and 'data' in commits_response:
                commits = commits_response['data']['repository']['pullRequest']['commits']['nodes']

                for commit_data in commits:
                    # Store commit raw data
                    raw_data_id = await store_raw_extraction_data(
                        tenant_id=tenant_id,
                        integration_id=integration_id,
                        entity_type='github_commits',
                        raw_data=commit_data,
                        external_id=commit_data['commit']['oid']
                    )

                    commit_extraction_jobs.append({
                        'raw_data_id': raw_data_id,
                        'pr_id': pr.id,
                        'commit_sha': commit_data['commit']['oid']
                    })

                    total_commits += 1

        logger.info(f"📦 Found {total_commits} commits across {len(recent_prs)} PRs")

        # Queue commits for transform
        for i, commit_job in enumerate(commit_extraction_jobs):
            first_item = (i == 0)
            last_item = (i == len(commit_extraction_jobs) - 1)

            queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                raw_data_id=commit_job['raw_data_id'],
                data_type='github_commits',
                job_id=job_id,
                provider='github',
                last_sync_date=last_sync_date,
                first_item=first_item,
                last_item=last_item,
                last_job_item=False
            )

        # 🔑 When last_item=True, trigger reviews extraction (next step)
        queue_manager.publish_extraction_job(
            tenant_id=tenant_id,
            integration_id=integration_id,
            job_id=job_id,
            extraction_type='github_reviews',
            extraction_data={'trigger_from': 'commits'},
            provider='github',
            last_sync_date=last_sync_date,
            first_item=True,
            last_item=True,
            last_job_item=False
        )

        return {
            'success': True,
            'commits_processed': total_commits
        }

    except Exception as e:
        logger.error(f"❌ Error in GitHub commit extraction: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {'success': False, 'error': str(e)}
```

### Task 4.3: Transform Workers for GitHub Entities
**Duration**: 3 days
**Priority**: HIGH

#### GitHub Entity Transform Processing

**Key Patterns**:
- All 4 steps follow same pattern: completion message → load raw data → transform → upsert → queue embedding
- Only final step (github_comments) has `last_job_item=True` on last item
- Always forward flags from incoming message to outgoing message
- Use `queue_manager.publish_embedding_job()` for embedding queue

```python
# services/backend-service/app/workers/transform_worker.py (add methods)

def _process_github_pull_requests(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
    """Process GitHub PR data from raw_extraction_data"""
    try:
        # 🔑 Handle completion message
        if raw_data_id is None and message and message.get('last_job_item'):
            logger.info(f"[COMPLETION] Received completion message for github_pull_requests")
            self.queue_manager.publish_embedding_job(
                tenant_id=tenant_id,
                table_name='prs',
                external_id=None,
                job_id=job_id,
                message_type='github_pull_requests',
                integration_id=integration_id,
                provider='github',
                last_sync_date=message.get('last_sync_date'),
                first_item=True,
                last_item=True,
                last_job_item=message.get('last_job_item', False)
            )
            return True

        # 🔑 Send "running" status on first_item=True
        if message and message.get('first_item') and job_id:
            self._send_worker_status("transform", tenant_id, job_id, "running", "github_pull_requests")

        with self.get_db_session() as db:
            # Load and transform PR data
            raw_data = self._get_raw_data(db, raw_data_id)
            if not raw_data:
                return False

            pr_data = raw_data.get('raw_data', {})

            # Transform PR data
            transformed_pr = {
                'external_id': pr_data['id'],
                'number': pr_data['number'],
                'title': pr_data['title'],
                'body': pr_data.get('body'),
                'state': pr_data['state'],
                'created_at': self._parse_datetime(pr_data['createdAt']),
                'updated_at': self._parse_datetime(pr_data['updatedAt']),
                'closed_at': self._parse_datetime(pr_data.get('closedAt')),
                'merged_at': self._parse_datetime(pr_data.get('mergedAt')),
                'author_login': pr_data['author']['login'] if pr_data.get('author') else None,
                'base_branch': pr_data['baseRefName'],
                'head_branch': pr_data['headRefName'],
                'is_draft': pr_data.get('isDraft', False),
                'additions': pr_data.get('additions', 0),
                'deletions': pr_data.get('deletions', 0),
                'changed_files': pr_data.get('changedFiles', 0),
                'integration_id': integration_id,
                'tenant_id': tenant_id,
                'active': True
            }

            # Upsert PR
            upsert_query = text("""
                INSERT INTO prs (
                    external_id, number, title, body, state, created_at, updated_at,
                    closed_at, merged_at, author_login, base_branch, head_branch,
                    is_draft, additions, deletions, changed_files,
                    integration_id, tenant_id, active, last_updated_at
                ) VALUES (
                    :external_id, :number, :title, :body, :state, :created_at, :updated_at,
                    :closed_at, :merged_at, :author_login, :base_branch, :head_branch,
                    :is_draft, :additions, :deletions, :changed_files,
                    :integration_id, :tenant_id, :active, NOW()
                )
                ON CONFLICT (external_id, tenant_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    body = EXCLUDED.body,
                    state = EXCLUDED.state,
                    updated_at = EXCLUDED.updated_at,
                    closed_at = EXCLUDED.closed_at,
                    merged_at = EXCLUDED.merged_at,
                    additions = EXCLUDED.additions,
                    deletions = EXCLUDED.deletions,
                    changed_files = EXCLUDED.changed_files,
                    last_updated_at = NOW()
                RETURNING id, external_id
            """)

            result = db.execute(upsert_query, transformed_pr)
            pr_record = result.fetchone()

            if pr_record:
                # 🔑 Queue for embedding with flag forwarding
                self.queue_manager.publish_embedding_job(
                    tenant_id=tenant_id,
                    table_name='prs',
                    external_id=pr_record[1],
                    job_id=job_id,
                    message_type='github_pull_requests',
                    integration_id=integration_id,
                    provider=message.get('provider', 'github'),
                    last_sync_date=message.get('last_sync_date'),
                    first_item=message.get('first_item', False),
                    last_item=message.get('last_item', False),
                    last_job_item=message.get('last_job_item', False)
                )

            # 🔑 Send "finished" status on last_item=True
            if message and message.get('last_item') and job_id:
                self._send_worker_status("transform", tenant_id, job_id, "finished", "github_pull_requests")

            return True

    except Exception as e:
        logger.error(f"❌ Error processing github_pull_requests: {e}")
        return False

def _process_github_commits(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
    """Process GitHub commit data from raw_extraction_data"""
    # Similar structure to _process_github_pull_requests
    # Transform commit data to prs_commits table
    # Forward all flags to embedding queue
    pass

def _process_github_reviews(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
    """Process GitHub review data from raw_extraction_data"""
    # Similar structure to _process_github_pull_requests
    # Transform review data to prs_reviews table
    # Forward all flags to embedding queue
    pass

def _process_github_comments(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
    """Process GitHub comment data from raw_extraction_data"""
    # Similar structure to _process_github_pull_requests
    # Transform comment data to prs_comments table
    # 🔑 This is the final step: last_job_item=True on the last comment
    # When last_item=True, embedding worker will complete the entire job
    pass
```

## ✅ Success Criteria

1. **Multi-step Processing**: All 4 new GitHub entity types processed in sequence (PRs → Commits → Reviews → Comments)
2. **GraphQL Integration**: Efficient data extraction using GitHub GraphQL API with pagination
3. **Recovery Logic**: Checkpoint-based recovery for large datasets
4. **Queue Processing**: Full Extract → Transform → Embedding pipeline with proper flag forwarding
5. **WebSocket Updates**: Real-time status updates on first_item=True (running) and last_item=True (finished)
6. **Data Relationships**: Proper PR → Commit → Review → Comment relationships maintained
7. **Completion Chain**: Proper completion message flow through all 4 steps with last_job_item=True only on final step
8. **Status JSON**: Database status updates follow pattern `status->steps->{step_name}->{worker_type}`

## 🚨 Risk Mitigation

1. **GraphQL Rate Limits**: Implement proper rate limiting and retry logic
2. **Large Datasets**: Use pagination and checkpoints for recovery
3. **API Failures**: Implement robust error handling and recovery
4. **Memory Usage**: Process data in batches to prevent memory issues
5. **Data Consistency**: Ensure proper relationships between entities
6. **Step Triggering**: Only last step (comments) has last_job_item=True to prevent premature job completion

## 📋 Implementation Checklist

- [ ] Verify GitHub job exists with github_repositories step from Phase 3
- [ ] Add 4 new steps to status JSON: github_pull_requests, github_commits, github_reviews, github_comments
- [ ] Implement GraphQL PR extraction with pagination and proper flag forwarding
- [ ] Implement GraphQL commit extraction with next-step triggering
- [ ] Implement GraphQL review extraction with next-step triggering
- [ ] Implement GraphQL comment extraction (final step with last_job_item=True)
- [ ] Add transform processing for all 4 GitHub entity types
- [ ] Implement completion message handling for each step
- [ ] Use queue_manager.publish_embedding_job() for all embedding queues
- [ ] Implement WebSocket status updates using _send_worker_status()
- [ ] Update ETL frontend for multi-step GitHub job display (5 circles total)
- [ ] Implement checkpoint-based recovery logic
- [ ] Test complete pipeline end-to-end with multiple repositories
- [ ] Validate data relationships and integrity
- [ ] Verify WebSocket status circles update correctly for all 5 steps
- [ ] Test error handling and recovery scenarios

## 🔄 Next Steps

After completion, this enables:
- **Complete GitHub ETL**: Full GitHub data processing in new architecture
- **Production Deployment**: Ready for production use
- **Performance Optimization**: Foundation for performance improvements
- **Advanced Features**: Ready for additional GitHub integrations
