# ETL Phase 4: GitHub PRs, Commits & Reviews with GraphQL

**Implemented**: NO ❌
**Duration**: 2 weeks
**Priority**: HIGH
**Risk Level**: MEDIUM
**Last Updated**: 2025-10-21

## 📊 Prerequisites (Must be complete before starting)

1. ✅ **Phase 0 Complete**: ETL Frontend + Backend ETL Module working
2. ✅ **Phase 1 Complete**: RabbitMQ + Raw Data Storage + Queue Manager
3. ✅ **Phase 2 Complete**: Jira Enhancement with Queue-based Processing
4. ✅ **Phase 3 Complete**: GitHub Repository Recreation
   - Repository discovery working
   - Repository data in repositories table
   - Queue-based processing established

**Status**: Ready to start after Phase 3 completion.

## 💼 Business Outcome

**GitHub PR/Commit/Review ETL with GraphQL**: Implement comprehensive GitHub data extraction using GraphQL API with queue-based processing and recovery logic:

- **GraphQL Integration**: Efficient bulk data fetching using GitHub GraphQL API
- **Multi-step Processing**: PRs → Commits → Reviews → Comments pipeline
- **Queue-based Architecture**: Extract → Transform → Embedding for each entity type
- **Recovery Logic**: Resume processing from checkpoints on failures
- **WebSocket Updates**: Real-time status updates for all processing stages
- **Incremental Sync**: Process only new/updated data since last sync

This completes the GitHub ETL migration to the new architecture.

## 🎯 Objectives

1. **Multi-step Job Structure**: Create github_prs job with 4 processing steps
2. **GraphQL Extraction**: Implement efficient GraphQL-based data extraction
3. **Recovery Mechanisms**: Checkpoint-based recovery for large datasets
4. **Queue Integration**: Full Extract → Transform → Embedding pipeline
5. **WebSocket Updates**: Real-time status updates for all worker stages
6. **Data Relationships**: Maintain PR → Commit → Review → Comment relationships

## 📋 Task Breakdown

### Task 4.1: GitHub PR Job Structure
**Duration**: 2 days
**Priority**: HIGH

#### Multi-step GitHub PR Job Configuration
```python
# services/backend-service/app/etl/github_jobs.py
async def create_github_pr_job(integration_id: int, tenant_id: int):
    """Create GitHub PR ETL job with multiple steps"""
    
    with get_write_session() as db:
        # Check if job already exists
        existing_job = db.query(EtlJob).filter(
            EtlJob.integration_id == integration_id,
            EtlJob.job_name == 'github_prs'
        ).first()
        
        if existing_job:
            return existing_job
        
        # Create new GitHub PR job with 4 steps
        github_pr_job = EtlJob(
            job_name='github_prs',
            integration_id=integration_id,
            tenant_id=tenant_id,
            active=True,
            schedule_interval_minutes=240,  # Every 4 hours
            status={
                "github_pull_requests": {
                    "order": 1,
                    "extraction": "idle",
                    "transform": "idle",
                    "embedding": "idle",
                    "display_name": "Pull Requests"
                },
                "github_commits": {
                    "order": 2,
                    "extraction": "idle",
                    "transform": "idle",
                    "embedding": "idle",
                    "display_name": "Commits"
                },
                "github_reviews": {
                    "order": 3,
                    "extraction": "idle",
                    "transform": "idle",
                    "embedding": "idle",
                    "display_name": "Reviews"
                },
                "github_comments": {
                    "order": 4,
                    "extraction": "idle",
                    "transform": "idle",
                    "embedding": "idle",
                    "display_name": "Comments"
                }
            },
            next_run=datetime.now(timezone.utc)
        )
        
        db.add(github_pr_job)
        db.commit()
        return github_pr_job
```

#### ETL Frontend Multi-step Job Card
```typescript
// services/frontend-etl/src/components/JobCard.tsx
const getJobSteps = (jobName: string): JobStep[] => {
  switch (jobName) {
    case 'github_prs':
      return [
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
```python
# services/backend-service/app/etl/github_extraction.py
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
    2. For each repository, extract PRs using GraphQL
    3. Store raw PR data and queue for transform
    4. After all PRs, trigger commits extraction
    """
    try:
        logger.info(f"Starting GitHub PR extraction for integration {integration_id}")
        
        # Get repositories for this integration
        with get_read_session() as db:
            repositories = db.query(Repository).filter(
                Repository.integration_id == integration_id,
                Repository.tenant_id == tenant_id,
                Repository.active == True
            ).all()
        
        if not repositories:
            logger.warning(f"No repositories found for integration {integration_id}")
            # Send completion message for empty step
            await queue_manager.publish_extraction_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                extraction_type='github_commits_fetch',
                extraction_data={},
                job_id=job_id,
                provider='github',
                last_sync_date=last_sync_date,
                first_item=True,
                last_item=True,
                last_job_item=False  # Not the final step
            )
            return {'success': True, 'prs_processed': 0}
        
        # Initialize GraphQL client
        github_client = GitHubGraphQLClient(integration_id)
        
        total_prs = 0
        pr_extraction_jobs = []
        
        # Process each repository
        for repo_idx, repository in enumerate(repositories):
            owner, repo_name = repository.full_name.split('/', 1)
            
            # Get PRs for this repository using GraphQL
            pr_cursor = None
            repo_pr_count = 0
            
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
                
                # Store each PR as raw data and queue for transform
                for pr_idx, pr_data in enumerate(prs):
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
                    
                    repo_pr_count += 1
                    total_prs += 1
                
                # Check for pagination
                page_info = response['data']['repository']['pullRequests']['pageInfo']
                if not page_info['hasNextPage']:
                    break
                pr_cursor = page_info['endCursor']
        
        logger.info(f"Found {total_prs} PRs across {len(repositories)} repositories")
        
        # Queue all PRs for transform processing
        for i, pr_job in enumerate(pr_extraction_jobs):
            first_item = (i == 0)
            last_item = (i == len(pr_extraction_jobs) - 1)
            
            await queue_manager.publish_transform_job(
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
        
        # After all PRs queued, trigger commits extraction
        if pr_extraction_jobs:
            # Queue commits extraction (next step)
            await queue_manager.publish_extraction_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                extraction_type='github_commits_fetch',
                extraction_data={'trigger_from': 'pull_requests'},
                job_id=job_id,
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
        logger.error(f"Error in GitHub PR extraction: {e}")
        return {'success': False, 'error': str(e)}


async def extract_github_commits(
    tenant_id: int,
    integration_id: int,
    job_id: int,
    last_sync_date: str = None
) -> Dict[str, Any]:
    """Extract GitHub commits for recent PRs using GraphQL"""
    try:
        logger.info(f"Starting GitHub commit extraction for integration {integration_id}")
        
        # Get recent PRs that might have new commits
        with get_read_session() as db:
            recent_prs = db.query(Pr).filter(
                Pr.integration_id == integration_id,
                Pr.tenant_id == tenant_id,
                Pr.active == True
            ).limit(100).all()  # Process recent PRs
        
        if not recent_prs:
            # Trigger reviews extraction (next step)
            await queue_manager.publish_extraction_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                extraction_type='github_reviews_fetch',
                extraction_data={'trigger_from': 'commits'},
                job_id=job_id,
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
        
        # Queue commits for transform
        for i, commit_job in enumerate(commit_extraction_jobs):
            first_item = (i == 0)
            last_item = (i == len(commit_extraction_jobs) - 1)
            
            await queue_manager.publish_transform_job(
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
        
        # Trigger reviews extraction (next step)
        await queue_manager.publish_extraction_job(
            tenant_id=tenant_id,
            integration_id=integration_id,
            extraction_type='github_reviews_fetch',
            extraction_data={'trigger_from': 'commits'},
            job_id=job_id,
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
        logger.error(f"Error in GitHub commit extraction: {e}")
        return {'success': False, 'error': str(e)}
```

### Task 4.3: Transform Workers for GitHub Entities
**Duration**: 3 days
**Priority**: HIGH

#### GitHub Entity Transform Processing
```python
# services/backend-service/app/workers/transform_worker.py (add methods)

def _process_github_pull_requests(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
    """Process GitHub PR data from raw_extraction_data"""
    try:
        # Handle completion message
        if raw_data_id is None and message and message.get('last_job_item'):
            return self._handle_completion_message(
                tenant_id, integration_id, job_id, message, 
                'prs', 'github_pull_requests'
            )
        
        # Set running status on first item
        if message and message.get('first_item') and job_id:
            await self._send_worker_status("transform", tenant_id, job_id, "running", "github_pull_requests")
        
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
                # Queue for embedding
                self._queue_entities_for_embedding(
                    tenant_id=tenant_id,
                    table_name='prs',
                    entities=[{
                        'id': pr_record[0],
                        'external_id': pr_record[1]
                    }],
                    job_id=job_id,
                    message_type='github_pull_requests',
                    integration_id=integration_id,
                    provider=message.get('provider', 'github'),
                    last_sync_date=message.get('last_sync_date'),
                    first_item=message.get('first_item', False),
                    last_item=message.get('last_item', False),
                    last_job_item=message.get('last_job_item', False)
                )
            
            # Set finished status on last item
            if message and message.get('last_item') and job_id:
                await self._send_worker_status("transform", tenant_id, job_id, "finished", "github_pull_requests")
            
            return True
            
    except Exception as e:
        logger.error(f"Error processing github_pull_requests: {e}")
        return False

def _process_github_commits(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
    """Process GitHub commit data from raw_extraction_data"""
    # Similar structure to _process_github_pull_requests
    # Transform commit data to prs_commits table
    pass

def _process_github_reviews(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
    """Process GitHub review data from raw_extraction_data"""
    # Similar structure to _process_github_pull_requests
    # Transform review data to prs_reviews table
    pass

def _process_github_comments(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
    """Process GitHub comment data from raw_extraction_data"""
    # Similar structure to _process_github_pull_requests
    # Transform comment data to prs_comments table
    # This is the final step, so last_job_item=True on the last comment
    pass
```

## ✅ Success Criteria

1. **Multi-step Processing**: All 4 GitHub entity types processed in sequence
2. **GraphQL Integration**: Efficient data extraction using GitHub GraphQL API
3. **Recovery Logic**: Checkpoint-based recovery for large datasets
4. **Queue Processing**: Full Extract → Transform → Embedding pipeline
5. **WebSocket Updates**: Real-time status updates for all processing stages
6. **Data Relationships**: Proper PR → Commit → Review → Comment relationships

## 🚨 Risk Mitigation

1. **GraphQL Rate Limits**: Implement proper rate limiting and retry logic
2. **Large Datasets**: Use pagination and checkpoints for recovery
3. **API Failures**: Implement robust error handling and recovery
4. **Memory Usage**: Process data in batches to prevent memory issues
5. **Data Consistency**: Ensure proper relationships between entities

## 📋 Implementation Checklist

- [ ] Create github_prs job with 4-step structure
- [ ] Implement GraphQL PR extraction with pagination
- [ ] Implement GraphQL commit extraction
- [ ] Implement GraphQL review extraction  
- [ ] Implement GraphQL comment extraction
- [ ] Add transform processing for all GitHub entity types
- [ ] Update ETL frontend for multi-step GitHub job display
- [ ] Implement checkpoint-based recovery logic
- [ ] Test complete pipeline end-to-end
- [ ] Validate data relationships and integrity

## 🔄 Next Steps

After completion, this enables:
- **Complete GitHub ETL**: Full GitHub data processing in new architecture
- **Production Deployment**: Ready for production use
- **Performance Optimization**: Foundation for performance improvements
- **Advanced Features**: Ready for additional GitHub integrations
