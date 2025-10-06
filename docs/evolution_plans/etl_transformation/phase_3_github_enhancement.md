# ETL Phase 3: GitHub Enhancement with Queue Integration

**Implemented**: NO ❌
**Duration**: 1 week (Week 8 of overall plan)
**Priority**: MEDIUM
**Risk Level**: LOW
**Last Updated**: 2025-10-02

## 📊 Prerequisites (Must be complete before starting)

1. ✅ **Phase 0 Complete**: ETL Frontend + Backend ETL Module working
2. ✅ **Phase 1 Complete**: RabbitMQ + Raw Data Storage + Queue Manager
3. ✅ **Phase 2 Complete**: Jira Enhancement with Dynamic Custom Fields
   - Queue-based processing working
   - etl_jobs table integration functional
   - Transform/Load workers operational

**Status**: Ready to start after Phase 2 completion.

## 💼 Business Outcome

**GitHub ETL with Queue Integration**: Migrate existing GitHub ETL logic to the new queue-based architecture:
- **Copy existing ETL logic** from old etl-service (no new features)
- **Queue-based processing** with Extract → Transform → Load separation
- **etl_jobs table integration** for job management
- **Maintain existing functionality** for PRs, commits, reviews, comments

This creates consistency across all ETL jobs using the same queue architecture.

## 🎯 Objectives

1. **Logic Migration**: Copy existing GitHub ETL logic to new architecture
2. **Queue Integration**: Implement Extract → Transform → Load pipeline
3. **Job Management**: Integrate with etl_jobs table
4. **Data Consistency**: Maintain existing GitHub data structure
5. **Performance**: Ensure queue-based processing is efficient

## 📋 Task Breakdown

### Task 3.1: GitHub Extraction Jobs
**Duration**: 2 days
**Priority**: HIGH

#### GitHub Extract Job Implementation
```python
# services/etl-service/app/jobs/github/github_extract_job.py
from typing import Dict, Any, List
from app.jobs.base_job import BaseExtractJob
from app.integrations.github_client import GitHubClient

class GitHubExtractJob(BaseExtractJob):
    """GitHub extraction job - extract only"""
    
    def __init__(self, tenant_id: int, integration_id: int, extract_type: str = 'prs'):
        super().__init__(tenant_id, integration_id)
        self.extract_type = extract_type
        self.github_client = GitHubClient(integration_id)
    
    async def extract_data(self) -> List[Dict[str, Any]]:
        """Extract raw data from GitHub"""
        if self.extract_type == 'prs':
            return await self.extract_pull_requests()
        elif self.extract_type == 'commits':
            return await self.extract_commits()
        elif self.extract_type == 'reviews':
            return await self.extract_reviews()
        elif self.extract_type == 'comments':
            return await self.extract_comments()
        elif self.extract_type == 'repositories':
            return await self.extract_repositories()
        else:
            raise ValueError(f"Unknown extract type: {self.extract_type}")
    
    async def extract_pull_requests(self) -> List[Dict[str, Any]]:
        """Extract GitHub pull requests (copy existing logic)"""
        
        # Get repositories for this integration
        repositories = await self.get_integration_repositories()
        
        all_prs = []
        
        for repo in repositories:
            # Get last sync date for incremental extraction
            last_sync = await self.get_last_sync_date('prs', repo['id'])
            
            # Extract PRs for this repository
            repo_prs = await self.github_client.get_pull_requests(
                repo_owner=repo['owner'],
                repo_name=repo['name'],
                since=last_sync,
                state='all'  # Get open, closed, merged
            )
            
            # Add repository context to each PR
            for pr in repo_prs:
                pr['repository_id'] = repo['id']
                pr['repository_name'] = repo['name']
                pr['repository_owner'] = repo['owner']
            
            all_prs.extend(repo_prs)
        
        return all_prs
    
    async def extract_commits(self) -> List[Dict[str, Any]]:
        """Extract GitHub commits (copy existing logic)"""
        
        repositories = await self.get_integration_repositories()
        all_commits = []
        
        for repo in repositories:
            last_sync = await self.get_last_sync_date('commits', repo['id'])
            
            repo_commits = await self.github_client.get_commits(
                repo_owner=repo['owner'],
                repo_name=repo['name'],
                since=last_sync
            )
            
            for commit in repo_commits:
                commit['repository_id'] = repo['id']
                commit['repository_name'] = repo['name']
                commit['repository_owner'] = repo['owner']
            
            all_commits.extend(repo_commits)
        
        return all_commits
    
    async def extract_reviews(self) -> List[Dict[str, Any]]:
        """Extract GitHub PR reviews (copy existing logic)"""
        
        # Get recent PRs that might have new reviews
        recent_prs = await self.get_recent_prs_for_reviews()
        all_reviews = []
        
        for pr in recent_prs:
            pr_reviews = await self.github_client.get_pr_reviews(
                repo_owner=pr['repository_owner'],
                repo_name=pr['repository_name'],
                pr_number=pr['number']
            )
            
            for review in pr_reviews:
                review['pr_id'] = pr['id']
                review['repository_id'] = pr['repository_id']
            
            all_reviews.extend(pr_reviews)
        
        return all_reviews
    
    async def extract_comments(self) -> List[Dict[str, Any]]:
        """Extract GitHub PR comments (copy existing logic)"""
        
        recent_prs = await self.get_recent_prs_for_comments()
        all_comments = []
        
        for pr in recent_prs:
            # Get both issue comments and review comments
            issue_comments = await self.github_client.get_issue_comments(
                repo_owner=pr['repository_owner'],
                repo_name=pr['repository_name'],
                issue_number=pr['number']
            )
            
            review_comments = await self.github_client.get_review_comments(
                repo_owner=pr['repository_owner'],
                repo_name=pr['repository_name'],
                pr_number=pr['number']
            )
            
            # Add context to comments
            for comment in issue_comments + review_comments:
                comment['pr_id'] = pr['id']
                comment['repository_id'] = pr['repository_id']
                comment['comment_type'] = 'issue' if comment in issue_comments else 'review'
            
            all_comments.extend(issue_comments + review_comments)
        
        return all_comments
    
    def get_entity_type(self) -> str:
        """Return entity type"""
        return f"github_{self.extract_type}"
    
    def get_extraction_metadata(self) -> Dict[str, Any]:
        """Return GitHub-specific extraction metadata"""
        metadata = super().get_extraction_metadata()
        metadata.update({
            'extract_type': self.extract_type,
            'github_instance': self.github_client.base_url,
            'incremental_sync': True
        })
        return metadata
```

#### etl_jobs Integration for GitHub
```python
# services/etl-service/app/orchestration/github_orchestrator.py
class GitHubJobOrchestrator:
    """Orchestrate GitHub jobs using etl_jobs table"""
    
    async def schedule_github_jobs(self, integration_id: int):
        """Schedule GitHub jobs in etl_jobs table"""
        
        jobs_to_schedule = [
            {
                'job_name': f'github_repositories_{integration_id}',
                'job_type': 'github_repositories',
                'integration_id': integration_id,
                'schedule_interval_minutes': 1440,  # Daily
                'priority': 1
            },
            {
                'job_name': f'github_prs_{integration_id}',
                'job_type': 'github_prs',
                'integration_id': integration_id,
                'schedule_interval_minutes': 240,   # 4 hours
                'priority': 5,
                'depends_on': f'github_repositories_{integration_id}'
            },
            {
                'job_name': f'github_commits_{integration_id}',
                'job_type': 'github_commits',
                'integration_id': integration_id,
                'schedule_interval_minutes': 360,   # 6 hours
                'priority': 4,
                'depends_on': f'github_prs_{integration_id}'
            },
            {
                'job_name': f'github_reviews_{integration_id}',
                'job_type': 'github_reviews',
                'integration_id': integration_id,
                'schedule_interval_minutes': 480,   # 8 hours
                'priority': 3,
                'depends_on': f'github_prs_{integration_id}'
            },
            {
                'job_name': f'github_comments_{integration_id}',
                'job_type': 'github_comments',
                'integration_id': integration_id,
                'schedule_interval_minutes': 720,   # 12 hours
                'priority': 2,
                'depends_on': f'github_prs_{integration_id}'
            }
        ]
        
        for job_config in jobs_to_schedule:
            await self.create_or_update_etl_job(job_config)
```

### Task 3.2: GitHub Transform Workers
**Duration**: 2 days
**Priority**: HIGH

#### GitHub Transform Worker Implementation
```python
# services/backend-service/app/etl/workers/github_transform_worker.py
class GitHubTransformWorker(BaseQueueWorker):
    """Transform raw GitHub data (copy existing logic)"""
    
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process GitHub transformation job"""
        
        raw_data_ids = message.get('raw_data_ids', [])
        entity_type = message.get('entity_type')
        
        if entity_type == 'github_prs':
            return await self.process_prs_data(raw_data_ids)
        elif entity_type == 'github_commits':
            return await self.process_commits_data(raw_data_ids)
        elif entity_type == 'github_reviews':
            return await self.process_reviews_data(raw_data_ids)
        elif entity_type == 'github_comments':
            return await self.process_comments_data(raw_data_ids)
        elif entity_type == 'github_repositories':
            return await self.process_repositories_data(raw_data_ids)
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")
    
    async def process_prs_data(self, raw_data_ids: List[int]):
        """Transform raw GitHub PRs to prs table (copy existing logic)"""
        
        processed_count = 0
        
        for raw_data_id in raw_data_ids:
            # Get raw data
            raw_record = await self.get_raw_data(raw_data_id)
            pr_data = raw_record['raw_data']
            
            # Transform PR data (copy from existing processor)
            transformed_data = await self.transform_pr(pr_data)
            
            # Queue for loading
            await self.queue_for_loading('prs', transformed_data, raw_data_id)
            
            processed_count += 1
        
        return {
            'success': True,
            'processed_count': processed_count
        }
    
    async def transform_pr(self, pr_data):
        """Transform PR data (copy existing logic)"""
        
        return {
            'external_id': str(pr_data.get('id')),
            'number': pr_data.get('number'),
            'title': pr_data.get('title'),
            'body': pr_data.get('body'),
            'state': pr_data.get('state'),
            'created_at': self.parse_datetime(pr_data.get('created_at')),
            'updated_at': self.parse_datetime(pr_data.get('updated_at')),
            'closed_at': self.parse_datetime(pr_data.get('closed_at')),
            'merged_at': self.parse_datetime(pr_data.get('merged_at')),
            'author_login': pr_data.get('user', {}).get('login'),
            'author_id': pr_data.get('user', {}).get('id'),
            'assignee_login': pr_data.get('assignee', {}).get('login') if pr_data.get('assignee') else None,
            'assignee_id': pr_data.get('assignee', {}).get('id') if pr_data.get('assignee') else None,
            'base_branch': pr_data.get('base', {}).get('ref'),
            'head_branch': pr_data.get('head', {}).get('ref'),
            'base_sha': pr_data.get('base', {}).get('sha'),
            'head_sha': pr_data.get('head', {}).get('sha'),
            'is_draft': pr_data.get('draft', False),
            'additions': pr_data.get('additions', 0),
            'deletions': pr_data.get('deletions', 0),
            'changed_files': pr_data.get('changed_files', 0),
            'commits_count': pr_data.get('commits', 0),
            'comments_count': pr_data.get('comments', 0),
            'review_comments_count': pr_data.get('review_comments', 0),
            'repository_id': pr_data.get('repository_id'),
            'integration_id': raw_record['integration_id'],
            'tenant_id': raw_record['tenant_id']
        }
    
    async def process_commits_data(self, raw_data_ids: List[int]):
        """Transform raw GitHub commits (copy existing logic)"""
        # Similar pattern for commits
        pass
    
    async def process_reviews_data(self, raw_data_ids: List[int]):
        """Transform raw GitHub reviews (copy existing logic)"""
        # Similar pattern for reviews
        pass
    
    async def process_comments_data(self, raw_data_ids: List[int]):
        """Transform raw GitHub comments (copy existing logic)"""
        # Similar pattern for comments
        pass
```

### Task 3.3: GitHub Load Workers
**Duration**: 2 days
**Priority**: HIGH

#### GitHub Load Worker Implementation
```python
# services/backend-service/app/etl/workers/github_load_worker.py
class GitHubLoadWorker(BaseQueueWorker):
    """Load transformed GitHub data to final tables"""
    
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Load transformed data to GitHub tables"""
        
        transformed_data_ids = message.get('transformed_data_ids', [])
        entity_type = message.get('entity_type')
        
        loaded_count = 0
        
        for data_id in transformed_data_ids:
            # Get transformed data
            transformed_record = await self.get_transformed_data(data_id)
            github_data = transformed_record['transformed_data']
            
            # Load to appropriate table
            if entity_type == 'github_prs':
                await self.upsert_pr(github_data)
            elif entity_type == 'github_commits':
                await self.upsert_commit(github_data)
            elif entity_type == 'github_reviews':
                await self.upsert_review(github_data)
            elif entity_type == 'github_comments':
                await self.upsert_comment(github_data)
            elif entity_type == 'github_repositories':
                await self.upsert_repository(github_data)
            
            # Queue for vectorization (all GitHub entities)
            await self.queue_for_vectorization(entity_type, github_data)
            
            loaded_count += 1
        
        return {
            'success': True,
            'loaded_count': loaded_count
        }
    
    async def upsert_pr(self, pr_data):
        """Upsert PR to prs table (copy existing logic)"""
        
        await self.db.execute("""
            INSERT INTO prs (
                external_id, number, title, body, state, created_at, updated_at,
                closed_at, merged_at, author_login, author_id, assignee_login,
                assignee_id, base_branch, head_branch, base_sha, head_sha,
                is_draft, additions, deletions, changed_files, commits_count,
                comments_count, review_comments_count, repository_id,
                integration_id, tenant_id
            ) VALUES (
                %(external_id)s, %(number)s, %(title)s, %(body)s, %(state)s,
                %(created_at)s, %(updated_at)s, %(closed_at)s, %(merged_at)s,
                %(author_login)s, %(author_id)s, %(assignee_login)s,
                %(assignee_id)s, %(base_branch)s, %(head_branch)s,
                %(base_sha)s, %(head_sha)s, %(is_draft)s, %(additions)s,
                %(deletions)s, %(changed_files)s, %(commits_count)s,
                %(comments_count)s, %(review_comments_count)s,
                %(repository_id)s, %(integration_id)s, %(tenant_id)s
            )
            ON CONFLICT (external_id, tenant_id) 
            DO UPDATE SET
                title = EXCLUDED.title,
                body = EXCLUDED.body,
                state = EXCLUDED.state,
                updated_at = EXCLUDED.updated_at,
                closed_at = EXCLUDED.closed_at,
                merged_at = EXCLUDED.merged_at,
                assignee_login = EXCLUDED.assignee_login,
                assignee_id = EXCLUDED.assignee_id,
                additions = EXCLUDED.additions,
                deletions = EXCLUDED.deletions,
                changed_files = EXCLUDED.changed_files,
                commits_count = EXCLUDED.commits_count,
                comments_count = EXCLUDED.comments_count,
                review_comments_count = EXCLUDED.review_comments_count,
                last_updated_at = NOW()
        """, pr_data)
```

### Task 3.4: Queue Worker Registration
**Duration**: 1 day
**Priority**: MEDIUM

#### Update Worker Registry
```python
# services/etl-service/app/workers/worker_registry.py
class WorkerRegistry:
    """Registry for all queue workers"""
    
    def __init__(self):
        self.workers = {
            # Existing workers
            'etl.extract': ExtractWorker(),
            'etl.transform.jira': JiraTransformWorker(),
            'etl.load.jira': JiraLoadWorker(),
            
            # New GitHub workers
            'etl.transform.github': GitHubTransformWorker(),
            'etl.load.github': GitHubLoadWorker(),
        }
    
    def start_all_workers(self):
        """Start all registered workers"""
        for queue_name, worker in self.workers.items():
            worker.start_consuming()
```

## ✅ Success Criteria

1. **Logic Migration**: All existing GitHub ETL logic copied to new architecture
2. **Queue Integration**: Extract → Transform → Load pipeline working for GitHub
3. **Job Management**: GitHub jobs managed through etl_jobs table
4. **Data Consistency**: GitHub data structure maintained (no changes)
5. **Performance**: Queue-based processing efficient and reliable

## 🚨 Risk Mitigation

1. **Logic Accuracy**: Careful copying of existing transformation logic
2. **Data Integrity**: Validate that migrated logic produces same results
3. **Queue Performance**: Monitor GitHub queue processing times
4. **Error Handling**: Implement proper retry logic for GitHub API failures
5. **Rate Limiting**: Respect GitHub API rate limits in extraction jobs

## 📋 Implementation Checklist

- [ ] Implement GitHub extract jobs (PRs, commits, reviews, comments, repositories)
- [ ] Integrate GitHub jobs with etl_jobs table
- [ ] Implement GitHub transform workers
- [ ] Implement GitHub load workers
- [ ] Update worker registry with GitHub workers
- [ ] Test complete GitHub pipeline end-to-end
- [ ] Validate data consistency with existing ETL
- [ ] Test queue performance with GitHub data volumes
- [ ] Implement proper error handling and retry logic
- [ ] Update job orchestration for GitHub jobs

## 🔄 Next Steps

After completion, this enables:
- **Phase 4**: Testing and production deployment
- **Complete ETL Migration**: All jobs using queue-based architecture
- **Unified Job Management**: All ETL jobs managed through etl_jobs table
- **Scalable Architecture**: Ready for additional data sources
