"""
GitHub Transform Handler - Processes GitHub-specific ETL data.

Handles all GitHub message types:
- github_repositories: Process GitHub repositories
- github_prs: Process GitHub PRs with nested data (commits, reviews, comments)
- github_prs_nested: Process nested pagination for PRs
- github_prs_commits_reviews_comments: Legacy message type (routes to github_prs)
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy import text
from contextlib import contextmanager

from app.etl.workers.bulk_operations import BulkOperations
from app.core.logging_config import get_logger
from app.core.database import get_database, get_write_session
from app.etl.workers.queue_manager import QueueManager
from app.core.utils import DateTimeHelper


logger = get_logger(__name__)


class GitHubTransformHandler:
    """
    Handler for processing GitHub-specific ETL data.

    This is a specialized handler (not a queue consumer) that processes
    GitHub-specific transformation logic. It's called from TransformWorker
    which is the actual queue consumer and router.

    Uses dependency injection to receive WorkerStatusManager and QueueManager.
    """

    def __init__(self, status_manager=None, queue_manager=None):
        """
        Initialize GitHub transform handler.

        Args:
            status_manager: WorkerStatusManager instance for sending status updates (injected by router)
            queue_manager: QueueManager instance for publishing to queues (injected by router)
        """
        self.database = get_database()
        self.queue_manager = queue_manager or QueueManager()  # 🔑 Dependency injection with fallback
        self.status_manager = status_manager  # 🔑 Dependency injection
        logger.debug("Initialized GitHubTransformHandler")

    @contextmanager
    def get_db_session(self):
        """
        Get a database session with automatic cleanup.

        Usage:
            with self.get_db_session() as session:
                # Use session for writes

        Note: This uses write session context. For read-only operations,
        consider using get_db_read_session() instead.
        """
        with self.database.get_write_session_context() as session:
            yield session

    @contextmanager
    def get_db_read_session(self):
        """
        Get a read-only database session with automatic cleanup.

        Usage:
            with self.get_db_read_session() as session:
                # Use session for reads only
        """
        with self.database.get_read_session_context() as session:
            yield session

    async def _send_worker_status(self, step: str, tenant_id: int, job_id: int,
                                   status: str, step_type: str = None):
        """
        Send worker status update using injected status manager.

        Args:
            step: ETL step name (e.g., 'extraction', 'transform', 'embedding')
            tenant_id: Tenant ID
            job_id: Job ID
            status: Status to send (e.g., 'running', 'finished', 'failed')
            step_type: Optional step type for logging (e.g., 'github_repositories')
        """
        if self.status_manager:
            await self.status_manager.send_worker_status(
                step=step,
                tenant_id=tenant_id,
                job_id=job_id,
                status=status,
                step_type=step_type
            )
        else:
            logger.warning(f"Status manager not available - cannot send {status} status for {step_type}")

    async def process_github_message(self, message_type: str, message: Dict[str, Any]) -> bool:
        """
        Route GitHub transform messages to appropriate handler method.

        Args:
            message_type: Type of message (e.g., 'github_repositories')
            message: Full message dict with structure:
                {
                    'type': str,
                    'provider': 'github',
                    'tenant_id': int,
                    'integration_id': int,
                    'job_id': int,
                    'raw_data_id': int | None,
                    'token': str,
                    'first_item': bool,
                    'last_item': bool,
                    'last_job_item': bool,
                    ... other fields
                }

        Returns:
            bool: True if processing succeeded
        """
        try:
            # Extract common fields from message
            raw_data_id = message.get('raw_data_id')
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            first_item = message.get('first_item', False)
            last_item = message.get('last_item', False)

            logger.debug(f"🔄 [GITHUB] Processing {message_type} for raw_data_id={raw_data_id} (first={first_item}, last={last_item})")

            # 🎯 HANDLE COMPLETION MESSAGE: raw_data_id=None signals completion
            if raw_data_id is None:
                logger.debug(f"🎯 [COMPLETION] Received completion message for {message_type}")
                return await self._handle_completion_message(message_type, message)

            # Route to appropriate handler based on message type
            if message_type == 'github_repositories':
                return await self._process_github_repositories(raw_data_id, tenant_id, integration_id, job_id, message)
            elif message_type in ('github_prs', 'github_prs_commits_reviews_comments'):
                return await self._process_github_prs(raw_data_id, tenant_id, integration_id, job_id, message)
            elif message_type == 'github_prs_nested':
                return await self._process_github_prs_nested(raw_data_id, tenant_id, integration_id, job_id, message)
            else:
                logger.warning(f"Unknown GitHub message type: {message_type}")
                return False

        except Exception as e:
            logger.error(f"Error processing GitHub message type {message_type}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    # ============ COMPLETION MESSAGE HANDLING ============

    async def _handle_completion_message(self, message_type: str, message: Dict[str, Any]) -> bool:
        """
        Handle completion messages (raw_data_id=None) for GitHub transform steps.

        Args:
            message_type: Type of completion message
            message: Full message dict

        Returns:
            bool: True if completion message handled successfully
        """
        tenant_id = message.get('tenant_id')
        job_id = message.get('job_id')
        integration_id = message.get('integration_id')
        token = message.get('token')
        last_item = message.get('last_item', False)
        rate_limited = message.get('rate_limited', False)  # 🔑 Rate limit flag from extraction

        # Handle different completion message types
        if message_type == 'github_repositories':
            logger.debug(f"🎯 [COMPLETION] Processing github_repositories completion message (rate_limited={rate_limited})")
            self.queue_manager.publish_embedding_job(
                tenant_id=tenant_id,
                table_name='repositories',
                external_id=None,  # 🔑 Completion message marker
                job_id=job_id,
                step_type='github_repositories',
                integration_id=integration_id,
                provider=message.get('provider', 'github'),
                old_last_sync_date=message.get('old_last_sync_date'),
                new_last_sync_date=message.get('new_last_sync_date'),  # 🔑 Forward new_last_sync_date for job completion
                first_item=message.get('first_item', False),
                last_item=last_item,
                last_job_item=message.get('last_job_item', False),
                token=token,
                rate_limited=rate_limited  # 🔑 Forward rate_limited flag to embedding
            )
            logger.debug(f"🎯 [COMPLETION] github_repositories completion message forwarded to embedding")

            # 🔑 Send transform worker "finished" status when last_item=True
            if last_item and job_id:
                await self._send_worker_status("transform", tenant_id, job_id, "finished", "github_repositories")
                logger.debug(f"✅ [GITHUB] Transform step marked as finished for github_repositories (completion message)")

            return True

        elif message_type in ('github_prs', 'github_prs_nested', 'github_prs_commits_reviews_comments'):
            logger.debug(f"🎯 [COMPLETION] Processing {message_type} completion message (rate_limited={rate_limited})")
            self.queue_manager.publish_embedding_job(
                tenant_id=tenant_id,
                table_name='prs',
                external_id=None,  # 🔑 Completion message marker
                job_id=job_id,
                step_type='github_prs_commits_reviews_comments',
                integration_id=integration_id,
                provider=message.get('provider', 'github'),
                old_last_sync_date=message.get('old_last_sync_date'),
                new_last_sync_date=message.get('new_last_sync_date'),  # 🔑 Forward new_last_sync_date for job completion
                first_item=message.get('first_item', False),
                last_item=last_item,
                last_job_item=message.get('last_job_item', False),
                token=token,
                rate_limited=rate_limited  # 🔑 Forward rate_limited flag to embedding
            )
            logger.debug(f"🎯 [COMPLETION] {message_type} completion message forwarded to embedding")

            # 🔑 Send transform worker "finished" status when last_item=True
            if last_item and job_id:
                await self._send_worker_status("transform", tenant_id, job_id, "finished", "github_prs_commits_reviews_comments")
                logger.debug(f"✅ [GITHUB] Transform step marked as finished for {message_type} (completion message)")

            return True

        else:
            logger.warning(f"⚠️ [COMPLETION] Unknown GitHub completion message type: {message_type}")
            return False

    # ============ GITHUB PROCESSING METHODS ============
    # All GitHub-specific processing methods extracted from transform_worker.py



    async def _process_github_repositories(self, raw_data_id: int, tenant_id: int, integration_id: int,
                                    job_id: int, message: Dict[str, Any] = None) -> bool:
        """
        Process GitHub repositories batch from raw_extraction_data.

        Flow:
        1. Load raw data containing all repositories
        2. Transform each repository and upsert to repositories table
        3. Queue each repository for embedding with proper first_item/last_item flags
        4. Send WebSocket status updates

        Args:
            raw_data_id: ID of raw extraction data
            tenant_id: Tenant ID
            integration_id: Integration ID
            job_id: ETL job ID
            message: Original message with flags and metadata

        Returns:
            bool: True if processing succeeded
        """
        try:
            first_item = message.get('first_item', False) if message else False
            last_item = message.get('last_item', False) if message else False
            last_job_item = message.get('last_job_item', False) if message else False
            provider = message.get('provider', 'github') if message else 'github'
            old_last_sync_date = message.get('old_last_sync_date') if message else None
            new_last_sync_date = message.get('new_last_sync_date') if message else None  # 🔑 Extraction end date for job completion

            logger.debug(f"🚀 [GITHUB] Processing repositories batch for tenant {tenant_id}, integration {integration_id}, raw_data_id={raw_data_id}")

            # Note: WebSocket status is sent by TransformWorkerRouter, not here

            # Fetch raw batch data
            from app.core.database import get_database
            database = get_database()

            with database.get_read_session_context() as db:
                raw_data_query = text("""
                    SELECT raw_data FROM raw_extraction_data
                    WHERE id = :raw_data_id AND tenant_id = :tenant_id
                """)
                result = db.execute(raw_data_query, {'raw_data_id': raw_data_id, 'tenant_id': tenant_id}).fetchone()

                if not result:
                    logger.error(f"Raw data not found for raw_data_id={raw_data_id}")
                    return False

                raw_batch_data = result[0]
                if isinstance(raw_batch_data, str):
                    raw_batch_data = json.loads(raw_batch_data)

            # Extract repositories from batch
            repositories = raw_batch_data.get('repositories', [])
            logger.debug(f"📦 Processing {len(repositories)} repositories from batch")

            if not repositories:
                logger.warning(f"No repositories found in raw_data_id={raw_data_id}")
                return True

            # Transform and upsert all repositories in this batch
            # 🔑 Flag forwarding logic for looping through repositories:
            # - first_item=True only on FIRST repo in the loop
            # - last_item=True only on LAST repo in the loop
            # - last_job_item=True only on LAST repo in the loop (when incoming last_job_item=True)
            # - All middle repos: all flags=False

            # Collect repos to queue AFTER database transaction completes
            repos_to_queue = []

            with database.get_write_session_context() as db:
                for i, raw_repo_data in enumerate(repositories):
                    is_first_repo_in_loop = (i == 0)
                    is_last_repo_in_loop = (i == len(repositories) - 1)

                    transformed_repo = {
                        'tenant_id': tenant_id,
                        'integration_id': integration_id,
                        'external_id': str(raw_repo_data.get('id')),
                        'name': raw_repo_data.get('name'),
                        'full_name': raw_repo_data.get('full_name'),
                        'owner': raw_repo_data.get('owner', {}).get('login'),
                        'description': raw_repo_data.get('description'),
                        'language': raw_repo_data.get('language'),
                        'default_branch': raw_repo_data.get('default_branch'),
                        'visibility': raw_repo_data.get('visibility'),
                        'topics': json.dumps(raw_repo_data.get('topics', [])),  # Convert to JSON string for JSONB
                        'is_private': raw_repo_data.get('private', False),
                        'archived': raw_repo_data.get('archived', False),
                        'disabled': raw_repo_data.get('disabled', False),
                        'fork': raw_repo_data.get('fork', False),
                        'is_template': raw_repo_data.get('is_template', False),
                        'allow_forking': raw_repo_data.get('allow_forking', True),
                        'web_commit_signoff_required': raw_repo_data.get('web_commit_signoff_required', False),
                        'has_issues': raw_repo_data.get('has_issues', True),
                        'has_wiki': raw_repo_data.get('has_wiki', False),
                        'has_discussions': raw_repo_data.get('has_discussions', False),
                        'has_projects': raw_repo_data.get('has_projects', False),
                        'has_downloads': raw_repo_data.get('has_downloads', True),
                        'has_pages': raw_repo_data.get('has_pages', False),
                        'license': raw_repo_data.get('license', {}).get('name') if raw_repo_data.get('license') else None,
                        'stargazers_count': raw_repo_data.get('stargazers_count', 0),
                        'forks_count': raw_repo_data.get('forks_count', 0),
                        'open_issues_count': raw_repo_data.get('open_issues_count', 0),
                        'size': raw_repo_data.get('size', 0),
                        'repo_created_at': self._parse_datetime(raw_repo_data.get('created_at')),
                        'repo_updated_at': self._parse_datetime(raw_repo_data.get('updated_at')),
                        'pushed_at': self._parse_datetime(raw_repo_data.get('pushed_at')),
                        'active': True,
                        'last_updated_at': self._get_current_time()
                    }

                    upsert_query = text("""
                        INSERT INTO repositories (
                            tenant_id, integration_id, external_id, name, full_name, owner,
                            description, language, default_branch, visibility, topics,
                            is_private, archived, disabled, fork, is_template, allow_forking,
                            web_commit_signoff_required, has_issues, has_wiki, has_discussions,
                            has_projects, has_downloads, has_pages, license,
                            stargazers_count, forks_count, open_issues_count, size,
                            repo_created_at, repo_updated_at, pushed_at, active, last_updated_at
                        ) VALUES (
                            :tenant_id, :integration_id, :external_id, :name, :full_name, :owner,
                            :description, :language, :default_branch, :visibility, :topics,
                            :is_private, :archived, :disabled, :fork, :is_template, :allow_forking,
                            :web_commit_signoff_required, :has_issues, :has_wiki, :has_discussions,
                            :has_projects, :has_downloads, :has_pages, :license,
                            :stargazers_count, :forks_count, :open_issues_count, :size,
                            :repo_created_at, :repo_updated_at, :pushed_at, :active, :last_updated_at
                        )
                        ON CONFLICT (tenant_id, integration_id, external_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            full_name = EXCLUDED.full_name,
                            owner = EXCLUDED.owner,
                            description = EXCLUDED.description,
                            language = EXCLUDED.language,
                            default_branch = EXCLUDED.default_branch,
                            visibility = EXCLUDED.visibility,
                            topics = EXCLUDED.topics,
                            is_private = EXCLUDED.is_private,
                            archived = EXCLUDED.archived,
                            disabled = EXCLUDED.disabled,
                            fork = EXCLUDED.fork,
                            is_template = EXCLUDED.is_template,
                            allow_forking = EXCLUDED.allow_forking,
                            web_commit_signoff_required = EXCLUDED.web_commit_signoff_required,
                            has_issues = EXCLUDED.has_issues,
                            has_wiki = EXCLUDED.has_wiki,
                            has_discussions = EXCLUDED.has_discussions,
                            has_projects = EXCLUDED.has_projects,
                            has_downloads = EXCLUDED.has_downloads,
                            has_pages = EXCLUDED.has_pages,
                            license = EXCLUDED.license,
                            stargazers_count = EXCLUDED.stargazers_count,
                            forks_count = EXCLUDED.forks_count,
                            open_issues_count = EXCLUDED.open_issues_count,
                            size = EXCLUDED.size,
                            repo_created_at = EXCLUDED.repo_created_at,
                            repo_updated_at = EXCLUDED.repo_updated_at,
                            pushed_at = EXCLUDED.pushed_at,
                            active = EXCLUDED.active,
                            last_updated_at = EXCLUDED.last_updated_at
                        RETURNING id, external_id
                    """)

                    result = db.execute(upsert_query, transformed_repo)
                    repo_record = result.fetchone()

                    if repo_record:
                        # Store repo info for queueing AFTER transaction commits
                        repos_to_queue.append({
                            'external_id': repo_record[1],
                            'full_name': transformed_repo['full_name'],
                            'is_first_in_batch': is_first_repo_in_loop,
                            'is_last_in_batch': is_last_repo_in_loop
                        })

                        logger.debug(f"✅ Processed repository {transformed_repo['full_name']}")

            # 🔑 CRITICAL: Queue for embedding AFTER database transaction commits
            # This prevents race condition where embedding worker tries to read data before it's committed
            # 🔑 Flag logic: Forward flags from incoming message (extraction worker already set them correctly)
            # - Extraction worker sends first_item=True ONLY on first repo across ALL repos
            # - Extraction worker sends last_item=True ONLY on last repo across ALL repos
            # - Each transform message processes 1 repo, so we forward the flags as-is

            # 🔑 Extract flags and token from incoming message
            incoming_first_item = message.get('first_item', False) if message else False
            incoming_last_item = message.get('last_item', False) if message else False
            token = message.get('token') if message else None

            for i, repo_info in enumerate(repos_to_queue):
                # 🔑 Forward flags from message (don't recalculate based on loop position)
                # Since each message contains only 1 repo, we use the incoming flags directly
                repo_first_item = incoming_first_item
                repo_last_item = incoming_last_item
                repo_last_job_item = incoming_last_item and last_job_item

                self.queue_manager.publish_embedding_job(
                    tenant_id=tenant_id,
                    table_name='repositories',
                    external_id=repo_info['external_id'],
                    job_id=job_id,
                    step_type='github_repositories',
                    integration_id=integration_id,
                    provider=provider,
                    old_last_sync_date=old_last_sync_date,
                    new_last_sync_date=new_last_sync_date,  # 🔑 Extraction end date for job completion
                    first_item=repo_first_item,
                    last_item=repo_last_item,
                    last_job_item=repo_last_job_item,
                    token=token  # 🔑 Include token in message
                )

                logger.debug(f"Queued repo {repo_info['full_name']} for embedding (first={repo_first_item}, last={repo_last_item}, job_end={repo_last_job_item})")

            # ✅ Mark raw data as completed after all repos are queued
            from app.core.utils import DateTimeHelper
            now = DateTimeHelper.now_default()

            update_query = text("""
                UPDATE raw_extraction_data
                SET status = 'completed',
                    last_updated_at = :now,
                    error_details = NULL
                WHERE id = :raw_data_id
            """)
            with database.get_write_session_context() as db:
                db.execute(update_query, {'raw_data_id': raw_data_id, 'now': now})
                db.commit()

            logger.debug(f"Processed {len(repos_to_queue)} repositories - marked raw_data_id={raw_data_id} as completed")

            # 🔑 Send transform worker "finished" status when last_item=True
            if last_item and job_id:
                await self._send_worker_status("transform", tenant_id, job_id, "finished", "github_repositories")
                logger.debug(f"✅ [GITHUB] Transform step marked as finished for github_repositories")

            # 🔑 NOTE: Step 2 extraction queuing is handled by Extraction worker (Step 1)
            # Transform worker only processes and inserts data, does NOT queue next extraction steps
            # This maintains unidirectional flow: Extract → Transform → Embed

            logger.debug(f"✅ [GITHUB] Processed {len(repositories)} repositories and queued for embedding")
            return True

        except Exception as e:
            logger.error(f"❌ [GITHUB] Error processing repositories: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    async def _process_github_prs(
        self, raw_data_id: int, tenant_id: int, integration_id: int,
        job_id: int = None, message: Dict[str, Any] = None
    ) -> bool:
        """
        Process GitHub PR data with nested commits, reviews, comments.

        Handles PR+nested data (complete or partial nested data).

        Flow:
        - Insert PR + all nested data from pr_data object
        - Queue to embedding only if all nested data complete (no pending nested pagination)

        Args:
            raw_data_id: ID of raw extraction data
            tenant_id: Tenant ID
            integration_id: Integration ID
            job_id: ETL job ID
            message: Original message with flags and metadata

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            # Note: WebSocket status is sent by TransformWorkerRouter, not here

            from app.core.database import get_database
            database = get_database()

            with database.get_write_session_context() as db:
                # Load raw data with external_id (repository external_id)
                raw_data_query = text("""
                    SELECT raw_data, external_id FROM raw_extraction_data WHERE id = :raw_data_id
                """)
                result = db.execute(raw_data_query, {'raw_data_id': raw_data_id}).fetchone()

                if not result:
                    logger.error(f"Raw data {raw_data_id} not found")
                    return False

                import json
                raw_json = json.loads(result[0]) if isinstance(result[0], str) else result[0]
                raw_data_external_id = result[1]  # 🔑 PR external_id from raw_extraction_data (not used for repo lookup)
                pr_id = raw_json.get('pr_id')

                # 🔑 Check if this is a nested pagination message (Type 2)
                # Type 2 messages have 'nested_type' and 'data' instead of 'pr_data'
                if raw_json.get('nested_type'):
                    logger.debug(f"🔄 Routing to _process_github_prs_nested for {raw_json.get('nested_type')}")
                    return self._process_github_prs_nested(raw_data_id, tenant_id, integration_id, job_id, message)

                # 🔑 Initialize entities_to_queue_after_commit (will be set if conditions met)
                entities_to_queue_after_commit = None

                # 🔑 Extract PR data from pr_data object (Type 1 message)
                pr_data = raw_json.get('pr_data')
                if not pr_data:
                    logger.error(f"No pr_data found in raw_json for raw_data_id={raw_data_id}")
                    return False

                logger.debug(f"📝 [TYPE 1] Processing PR data for PR {pr_id}")

                # Extract nested data from pr_data object
                pr_commits = pr_data.get('commits', {}).get('nodes', [])
                pr_reviews = pr_data.get('reviews', {}).get('nodes', [])
                pr_comments = pr_data.get('comments', {}).get('nodes', [])
                pr_review_threads = pr_data.get('reviewThreads', {}).get('nodes', [])

                # Check if there are more pages for any nested data
                has_pending_nested = (
                    pr_data.get('commits', {}).get('pageInfo', {}).get('hasNextPage', False) or
                    pr_data.get('reviews', {}).get('pageInfo', {}).get('hasNextPage', False) or
                    pr_data.get('comments', {}).get('pageInfo', {}).get('hasNextPage', False) or
                    pr_data.get('reviewThreads', {}).get('pageInfo', {}).get('hasNextPage', False)
                )

                logger.debug(f"  PR has {len(pr_commits)} commits, {len(pr_reviews)} reviews, {len(pr_comments)} comments, {len(pr_review_threads)} review threads")
                logger.debug(f"  Has pending nested data: {has_pending_nested}")

                # 🔑 Look up repository_id by full_name (stored in raw_data from extraction)
                full_name = raw_json.get('full_name')
                owner = raw_json.get('owner')
                repo_name = raw_json.get('repo_name')

                if not full_name and (not owner or not repo_name):
                    logger.error(f"full_name or owner/repo_name not found in raw_data for PR {pr_id}")
                    return False

                # Use full_name if available, otherwise construct from owner/repo_name
                lookup_full_name = full_name or f"{owner}/{repo_name}"

                # Query repository by full_name (get both id and external_id)
                repo_lookup_query = text("""
                    SELECT id, external_id FROM repositories
                    WHERE full_name = :full_name AND tenant_id = :tenant_id
                """)
                repo_result = db.execute(repo_lookup_query, {
                    'full_name': lookup_full_name,
                    'tenant_id': tenant_id
                }).fetchone()

                if not repo_result:
                    logger.error(f"Repository {lookup_full_name} not found in database for PR {pr_id}")
                    return False

                repository_id = repo_result[0]
                repo_external_id = repo_result[1]  # 🔑 Get repository's external_id (not PR's!)
                logger.debug(f"✅ Looked up repository_id={repository_id}, external_id={repo_external_id} for {lookup_full_name}")

                # Insert PR data
                pr_db_id = self._insert_pr(db, pr_data, tenant_id, integration_id, repository_id, repo_external_id)
                if not pr_db_id:
                    logger.error(f"Failed to insert PR {pr_id}")
                    return False

                # Insert nested data
                if pr_commits:
                    self._insert_commits(db, pr_commits, pr_db_id, tenant_id, integration_id)
                if pr_reviews:
                    self._insert_reviews(db, pr_reviews, pr_db_id, tenant_id, integration_id)
                if pr_comments:
                    self._insert_comments(db, pr_comments, pr_db_id, tenant_id, integration_id)
                if pr_review_threads:
                    self._insert_review_threads(db, pr_review_threads, pr_db_id, tenant_id, integration_id)

                logger.debug(f"✅ Inserted PR {pr_id} with nested data")

                # 🔑 ALWAYS queue entities to embedding, regardless of first_item/last_item flags
                # Those flags are ONLY for WebSocket status updates and job completion tracking
                # Queue all entities: PR + all nested entities from this message
                entities_to_queue_after_commit = [
                    {'table_name': 'prs', 'external_id': pr_data['id']}
                ]

                # Add commits (use commit.oid as external_id, same as _insert_commits)
                for commit_data in pr_commits:
                    commit_external_id = commit_data.get('commit', {}).get('oid')
                    if commit_external_id:
                        logger.debug(f"  Queuing commit {commit_external_id} to embedding")
                        entities_to_queue_after_commit.append({'table_name': 'prs_commits', 'external_id': commit_external_id})
                    else:
                        logger.warning(f"  ⚠️ Commit has no oid: {commit_data}")

                # Add reviews (already a list from extraction)
                for review_data in pr_reviews:
                    if review_data.get('id'):
                        review_id = review_data['id']
                        logger.debug(f"  Queuing review {review_id} to embedding")
                        entities_to_queue_after_commit.append({'table_name': 'prs_reviews', 'external_id': review_id})

                # Add comments (already a list from extraction)
                for comment_data in pr_comments:
                    if comment_data.get('id'):
                        entities_to_queue_after_commit.append({'table_name': 'prs_comments', 'external_id': comment_data['id']})

                # Add review threads (stored as comments in prs_comments table)
                for thread_data in pr_review_threads:
                    # Review thread comments are nested in the thread object
                    for comment_data in thread_data.get('comments', {}).get('nodes', []):
                        if comment_data.get('id'):
                            entities_to_queue_after_commit.append({'table_name': 'prs_comments', 'external_id': comment_data['id']})

                logger.debug(f"📤 Queuing {len(entities_to_queue_after_commit)} entities for PR {pr_id} to embedding")

                # ✅ Mark raw data as completed
                update_query = text("""
                    UPDATE raw_extraction_data
                    SET status = 'completed',
                        last_updated_at = NOW(),
                        error_details = NULL
                    WHERE id = :raw_data_id
                """)
                db.execute(update_query, {'raw_data_id': raw_data_id})

                # Note: WebSocket status is sent by TransformWorkerRouter, not here

                db.commit()
                logger.debug(f"✅ [GITHUB] Processed PR data and marked raw_data_id={raw_data_id} as completed")

                # 🔑 Queue to embedding AFTER commit so entities are visible in database
                if entities_to_queue_after_commit:
                    last_item_flag = message.get('last_item', False) if message else False
                    last_job_item_flag = message.get('last_job_item', False) if message else False
                    token = message.get('token') if message else None  # 🔑 Extract token from message

                    self._queue_github_nested_entities_for_embedding(
                        tenant_id=tenant_id,
                        pr_external_id=pr_data['id'],
                        job_id=job_id,
                        integration_id=integration_id,
                        provider=message.get('provider', 'github') if message else 'github',
                        first_item=message.get('first_item', False) if message else False,
                        last_item=last_item_flag,  # 🔑 Use actual flag from message
                        last_job_item=last_job_item_flag,  # 🔑 Only True if this is the last message in the entire job
                        message=message,
                        entities_to_queue=entities_to_queue_after_commit,  # 🔑 Pass list of entities with external IDs
                        token=token  # 🔑 Forward token to embedding
                    )

                    # 🔑 Send transform worker "finished" status when last_item=True
                    if last_item_flag and job_id:
                        await self._send_worker_status("transform", tenant_id, job_id, "finished", "github_prs_commits_reviews_comments")
                        logger.debug(f"✅ [GITHUB] Transform step marked as finished for github_prs_commits_reviews_comments")

                return True

        except Exception as e:
            logger.error(f"❌ [GITHUB] Error processing github_prs: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    async def _process_github_prs_nested(
        self, raw_data_id: int, tenant_id: int, integration_id: int,
        job_id: int = None, message: Dict[str, Any] = None
    ) -> bool:
        """
        Process GitHub nested data (commits, reviews, comments, review threads) for a PR.

        Handles nested data continuation when a PR has more pages of nested data.

        Flow:
        - Insert only nested data for the specified nested_type
        - Queue to embedding only if this is the last page of nested data (has_more=false)

        Args:
            raw_data_id: ID of raw extraction data
            tenant_id: Tenant ID
            integration_id: Integration ID
            job_id: ETL job ID
            message: Original message with flags and metadata

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            from app.core.database import get_database
            database = get_database()

            with database.get_write_session_context() as db:
                # Load raw data
                raw_data_query = text("""
                    SELECT raw_data FROM raw_extraction_data WHERE id = :raw_data_id
                """)
                result = db.execute(raw_data_query, {'raw_data_id': raw_data_id}).fetchone()

                if not result:
                    logger.error(f"Raw data {raw_data_id} not found")
                    return False

                import json
                raw_json = json.loads(result[0]) if isinstance(result[0], str) else result[0]
                pr_id = raw_json.get('pr_id')
                nested_type = raw_json.get('nested_type')

                logger.debug(f"📝 [NESTED] Processing {nested_type} for PR {pr_id}")

                # Lookup PR by external_id
                pr_lookup_query = text("""
                    SELECT id FROM prs WHERE external_id = :external_id AND tenant_id = :tenant_id
                """)
                pr_result = db.execute(pr_lookup_query, {
                    'external_id': pr_id,
                    'tenant_id': tenant_id
                }).fetchone()

                if not pr_result:
                    logger.warning(f"PR {pr_id} not found in database")
                    return False

                pr_db_id = pr_result[0]

                # Insert nested data based on type
                nested_data = raw_json.get('data', [])
                if nested_type == 'commits':
                    self._insert_commits(db, nested_data, pr_db_id, tenant_id, integration_id)
                elif nested_type == 'reviews':
                    self._insert_reviews(db, nested_data, pr_db_id, tenant_id, integration_id)
                elif nested_type == 'comments':
                    self._insert_comments(db, nested_data, pr_db_id, tenant_id, integration_id)
                elif nested_type == 'review_threads':
                    self._insert_review_threads(db, nested_data, pr_db_id, tenant_id, integration_id)

                logger.debug(f"✅ Inserted {len(nested_data)} {nested_type} for PR {pr_id}")

                # Mark raw data as completed
                from app.core.utils import DateTimeHelper
                now = DateTimeHelper.now_default()

                update_query = text("""
                    UPDATE raw_extraction_data
                    SET status = 'completed',
                        last_updated_at = :now,
                        error_details = NULL
                    WHERE id = :raw_data_id
                """)
                db.execute(update_query, {'raw_data_id': raw_data_id, 'now': now})

                # 🔑 ALWAYS queue nested entities to embedding, regardless of pagination
                # first_item/last_item flags are ONLY for WebSocket status updates
                # Queue every page of nested data as it arrives

                logger.debug(f"📤 Queuing nested entities for PR {pr_id} to embedding ({nested_type})")

                # 🔑 Build list of nested entities to queue
                entities_to_queue = []

                # Map nested type to table name
                table_name_map = {
                    'commits': 'prs_commits',
                    'reviews': 'prs_reviews',
                    'comments': 'prs_comments',
                    'review_threads': 'prs_comments'  # Review threads are stored as comments
                }

                table_name = table_name_map.get(nested_type)
                if table_name:
                    if nested_type == 'review_threads':
                        # For review threads, extract comment IDs from inside each thread
                        for thread_data in nested_data:
                            for comment_data in thread_data.get('comments', {}).get('nodes', []):
                                comment_external_id = comment_data.get('id')
                                if comment_external_id:
                                    entities_to_queue.append({'table_name': table_name, 'external_id': comment_external_id})
                    else:
                        # For commits, reviews, comments - extract directly from data array
                        for entity_data in nested_data:
                            if nested_type == 'commits':
                                external_id = entity_data.get('commit', {}).get('oid')
                            else:
                                external_id = entity_data.get('id')

                            if external_id:
                                entities_to_queue.append({'table_name': table_name, 'external_id': external_id})

                db.commit()
                logger.debug(f"✅ [GITHUB] Processed nested {nested_type} data and marked raw_data_id={raw_data_id} as completed")

                # 🔑 Queue to embedding AFTER commit so entities are visible in database
                if entities_to_queue:
                    token = message.get('token') if message else None  # 🔑 Extract token from message
                    last_item_flag = message.get('last_item', False) if message else False

                    self._queue_github_nested_entities_for_embedding(
                        tenant_id=tenant_id,
                        pr_external_id=pr_id,
                        job_id=job_id,
                        integration_id=integration_id,
                        provider=message.get('provider', 'github') if message else 'github',
                        first_item=message.get('first_item', False) if message else False,
                        last_item=last_item_flag,  # 🔑 Use actual flag from message
                        last_job_item=message.get('last_job_item', False) if message else False,
                        message=message,
                        entities_to_queue=entities_to_queue,
                        token=token  # 🔑 Forward token to embedding
                    )

                    # 🔑 Send transform worker "finished" status when last_item=True
                    if last_item_flag and job_id:
                        await self._send_worker_status("transform", tenant_id, job_id, "finished", "github_prs_commits_reviews_comments")
                        logger.debug(f"✅ [GITHUB] Transform step marked as finished for github_prs_nested")

                return True

        except Exception as e:
            logger.error(f"❌ [GITHUB] Error processing github_prs_nested: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    def _insert_pr(self, db, pr_data: dict, tenant_id: int, integration_id: int, repository_id: int = None, repo_external_id: str = None) -> int:
        """
        Insert or update a PR in the prs table.

        Args:
            db: Database session
            pr_data: PR data from GraphQL response (includes nested commits, reviews, comments, reviewThreads)
            tenant_id: Tenant ID
            integration_id: Integration ID
            repository_id: Database ID of the repository (from raw_data)
            repo_external_id: External ID of the repository (from raw_extraction_data.external_id)

        Returns:
            PR database ID if successful, None otherwise
        """
        try:
            from app.core.utils import DateTimeHelper
            from sqlalchemy import text

            pr_id = pr_data.get('id')
            if not pr_id:
                logger.error(f"PR data missing 'id' field")
                return None

            logger.debug(f"🔍 Inserting PR {pr_id}")

            # Extract nested data from pr_data object
            pr_commits = pr_data.get('commits', {}).get('nodes', [])
            pr_reviews = pr_data.get('reviews', {}).get('nodes', [])
            pr_comments = pr_data.get('comments', {}).get('nodes', [])
            pr_review_threads = pr_data.get('reviewThreads', {}).get('nodes', [])

            # Calculate PR metrics from GraphQL data
            metrics = self._calculate_pr_metrics(pr_data, pr_commits, pr_reviews, pr_comments, pr_review_threads)
            logger.debug(f"📊 Calculated PR metrics: commit_count={metrics['commit_count']}, reviewers={metrics['reviewers']}, rework_commits={metrics['rework_commit_count']}")

            # 🔑 Use repository_id from raw_data (passed as parameter)
            if not repository_id:
                logger.error(f"Repository ID not provided for PR {pr_id}")
                return None

            logger.debug(f"  Using repository_id={repository_id} from raw_data")

            # Build PR data for insertion
            transformed_pr = {
                'external_id': pr_data['id'],
                'external_repo_id': repo_external_id,
                'number': pr_data.get('number'),
                'name': pr_data.get('title'),
                'body': pr_data.get('body'),
                'status': pr_data.get('state'),
                'pr_created_at': self._parse_datetime(pr_data.get('createdAt')),
                'pr_updated_at': self._parse_datetime(pr_data.get('updatedAt')),
                'closed_at': self._parse_datetime(pr_data.get('closedAt')),
                'merged_at': self._parse_datetime(pr_data.get('mergedAt')),
                'user_name': pr_data.get('author', {}).get('login'),
                'repository_id': repository_id,  # 🔑 Looked up from database
                'source': metrics['source'],
                'destination': metrics['destination'],
                'commit_count': metrics['commit_count'],
                'additions': metrics['additions'],
                'deletions': metrics['deletions'],
                'changed_files': metrics['changed_files'],
                'reviewers': metrics['reviewers'],
                'first_review_at': metrics['first_review_at'],
                'rework_commit_count': metrics['rework_commit_count'],
                'review_cycles': metrics['review_cycles'],
                'discussion_comment_count': metrics['discussion_comment_count'],
                'review_comment_count': metrics['review_comment_count'],
                'integration_id': integration_id,
                'tenant_id': tenant_id,
                'active': True,
                'last_updated_at': DateTimeHelper.now_default()
            }

            # Upsert PR
            upsert_query = text("""
                INSERT INTO prs (
                    external_id, external_repo_id, number, name, body, status, pr_created_at, pr_updated_at,
                    closed_at, merged_at, user_name, repository_id, source, destination, commit_count, additions,
                    deletions, changed_files, reviewers, first_review_at, rework_commit_count, review_cycles,
                    discussion_comment_count, review_comment_count, integration_id, tenant_id, active, last_updated_at
                ) VALUES (
                    :external_id, :external_repo_id, :number, :name, :body, :status, :pr_created_at, :pr_updated_at,
                    :closed_at, :merged_at, :user_name, :repository_id, :source, :destination, :commit_count, :additions,
                    :deletions, :changed_files, :reviewers, :first_review_at, :rework_commit_count, :review_cycles,
                    :discussion_comment_count, :review_comment_count, :integration_id, :tenant_id, :active, :last_updated_at
                )
                ON CONFLICT (external_id, tenant_id)
                DO UPDATE SET
                    external_repo_id = EXCLUDED.external_repo_id,
                    name = EXCLUDED.name,
                    body = EXCLUDED.body,
                    status = EXCLUDED.status,
                    pr_updated_at = EXCLUDED.pr_updated_at,
                    closed_at = EXCLUDED.closed_at,
                    merged_at = EXCLUDED.merged_at,
                    source = EXCLUDED.source,
                    destination = EXCLUDED.destination,
                    commit_count = EXCLUDED.commit_count,
                    additions = EXCLUDED.additions,
                    deletions = EXCLUDED.deletions,
                    changed_files = EXCLUDED.changed_files,
                    reviewers = EXCLUDED.reviewers,
                    first_review_at = EXCLUDED.first_review_at,
                    rework_commit_count = EXCLUDED.rework_commit_count,
                    review_cycles = EXCLUDED.review_cycles,
                    discussion_comment_count = EXCLUDED.discussion_comment_count,
                    review_comment_count = EXCLUDED.review_comment_count,
                    last_updated_at = EXCLUDED.last_updated_at
                RETURNING id
            """)

            pr_result = db.execute(upsert_query, transformed_pr)
            pr_db_id = pr_result.scalar()
            logger.debug(f"✅ Upserted PR {pr_id} (db_id={pr_db_id})")

            return pr_db_id

        except Exception as e:
            logger.error(f"❌ Error inserting PR: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _insert_commits(self, db, commits: list, pr_db_id: int, tenant_id: int, integration_id: int = None) -> None:
        """Insert commits for a PR"""
        if not commits:
            logger.debug(f"No commits to insert for PR {pr_db_id}")
            return

        from app.core.utils import DateTimeHelper
        from sqlalchemy import text

        logger.debug(f"🔍 Inserting {len(commits)} commits for PR {pr_db_id}, tenant_id={tenant_id}, integration_id={integration_id}")

        for commit_data in commits:
            try:
                commit_oid = commit_data['commit']['oid']
                logger.debug(f"  ✅ Inserting commit {commit_oid} (type: {type(commit_oid).__name__})")

                insert_query = text("""
                    INSERT INTO prs_commits (
                        pr_id, external_id, author_name, author_email, authored_date,
                        committer_name, committer_email, committed_date, message,
                        integration_id, tenant_id, active, created_at, last_updated_at
                    ) VALUES (
                        :pr_id, :external_id, :author_name, :author_email, :authored_date,
                        :committer_name, :committer_email, :committed_date, :message,
                        :integration_id, :tenant_id, :active, :created_at, :last_updated_at
                    )
                    ON CONFLICT (external_id, tenant_id)
                    DO UPDATE SET
                        message = EXCLUDED.message,
                        authored_date = EXCLUDED.authored_date,
                        committed_date = EXCLUDED.committed_date,
                        last_updated_at = EXCLUDED.last_updated_at
                """)

                db.execute(insert_query, {
                    'pr_id': pr_db_id,
                    'external_id': commit_oid,
                    'author_name': commit_data['commit']['author']['name'] if commit_data['commit'].get('author') else None,
                    'author_email': commit_data['commit']['author']['email'] if commit_data['commit'].get('author') else None,
                    'authored_date': self._parse_datetime(commit_data['commit']['author']['date']) if commit_data['commit'].get('author') else None,
                    'committer_name': commit_data['commit']['committer']['name'] if commit_data['commit'].get('committer') else None,
                    'committer_email': commit_data['commit']['committer']['email'] if commit_data['commit'].get('committer') else None,
                    'committed_date': self._parse_datetime(commit_data['commit']['committer']['date']) if commit_data['commit'].get('committer') else None,
                    'message': commit_data['commit']['message'],
                    'integration_id': integration_id,
                    'tenant_id': tenant_id,
                    'active': True,
                    'created_at': DateTimeHelper.now_default(),
                    'last_updated_at': DateTimeHelper.now_default()
                })
                logger.debug(f"  ✅ Inserted commit {commit_oid} into prs_commits")
            except Exception as e:
                logger.error(f"❌ Error inserting commit {commit_data.get('commit', {}).get('oid', 'unknown')}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")

    def _insert_reviews(self, db, reviews: list, pr_db_id: int, tenant_id: int, integration_id: int = None) -> None:
        """Insert reviews for a PR"""
        if not reviews:
            logger.debug(f"No reviews to insert for PR {pr_db_id}")
            return

        from app.core.utils import DateTimeHelper
        from sqlalchemy import text

        logger.debug(f"Inserting {len(reviews)} reviews for PR {pr_db_id}, tenant_id={tenant_id}, integration_id={integration_id}")

        for review_data in reviews:
            try:
                review_id = review_data['id']
                logger.debug(f"  Inserting review {review_id}")

                insert_query = text("""
                    INSERT INTO prs_reviews (
                        pr_id, external_id, author_login, state, body, submitted_at,
                        integration_id, tenant_id, active, created_at, last_updated_at
                    ) VALUES (
                        :pr_id, :external_id, :author_login, :state, :body, :submitted_at,
                        :integration_id, :tenant_id, :active, :created_at, :last_updated_at
                    )
                    ON CONFLICT (external_id, tenant_id)
                    DO UPDATE SET
                        state = EXCLUDED.state,
                        body = EXCLUDED.body,
                        submitted_at = EXCLUDED.submitted_at,
                        last_updated_at = EXCLUDED.last_updated_at
                """)

                db.execute(insert_query, {
                    'pr_id': pr_db_id,
                    'external_id': review_id,
                    'author_login': review_data['author']['login'] if review_data.get('author') else None,
                    'state': review_data['state'],
                    'body': review_data.get('body'),
                    'submitted_at': self._parse_datetime(review_data['submittedAt']) if review_data.get('submittedAt') else None,
                    'integration_id': integration_id,
                    'tenant_id': tenant_id,
                    'active': True,
                    'created_at': DateTimeHelper.now_default(),
                    'last_updated_at': DateTimeHelper.now_default()
                })
                logger.debug(f"  ✅ Inserted review {review_id}")
            except Exception as e:
                logger.error(f"❌ Error inserting review {review_data.get('id', 'unknown')}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")

    def _insert_comments(self, db, comments: list, pr_db_id: int, tenant_id: int, integration_id: int = None) -> None:
        """Insert comments for a PR"""
        if not comments:
            return

        from app.core.utils import DateTimeHelper
        from sqlalchemy import text

        for comment_data in comments:
            try:
                insert_query = text("""
                    INSERT INTO prs_comments (
                        pr_id, external_id, author_login, body, created_at_github, updated_at_github,
                        integration_id, tenant_id, active, created_at, last_updated_at
                    ) VALUES (
                        :pr_id, :external_id, :author_login, :body, :created_at_github, :updated_at_github,
                        :integration_id, :tenant_id, :active, :created_at, :last_updated_at
                    )
                    ON CONFLICT (external_id, tenant_id)
                    DO UPDATE SET
                        body = EXCLUDED.body,
                        updated_at_github = EXCLUDED.updated_at_github,
                        last_updated_at = EXCLUDED.last_updated_at
                """)

                db.execute(insert_query, {
                    'pr_id': pr_db_id,
                    'external_id': comment_data['id'],
                    'author_login': comment_data['author']['login'] if comment_data.get('author') else None,
                    'body': comment_data['body'],
                    'created_at_github': self._parse_datetime(comment_data['createdAt']),
                    'updated_at_github': self._parse_datetime(comment_data['updatedAt']) if comment_data.get('updatedAt') else None,
                    'integration_id': integration_id,
                    'tenant_id': tenant_id,
                    'active': True,
                    'created_at': DateTimeHelper.now_default(),
                    'last_updated_at': DateTimeHelper.now_default()
                })
            except Exception as e:
                logger.warning(f"Error inserting comment {comment_data['id']}: {e}")

    def _insert_review_threads(self, db, threads: list, pr_db_id: int, tenant_id: int, integration_id: int = None) -> None:
        """Insert review threads and their comments for a PR"""
        if not threads:
            return

        from app.core.utils import DateTimeHelper
        from sqlalchemy import text

        for thread_data in threads:
            try:
                # Insert comments from the thread
                for comment_data in thread_data.get('comments', {}).get('nodes', []):
                    insert_query = text("""
                        INSERT INTO prs_comments (
                            pr_id, external_id, author_login, body, created_at_github, updated_at_github,
                            path, position, integration_id, tenant_id, active, created_at, last_updated_at
                        ) VALUES (
                            :pr_id, :external_id, :author_login, :body, :created_at_github, :updated_at_github,
                            :path, :position, :integration_id, :tenant_id, :active, :created_at, :last_updated_at
                        )
                        ON CONFLICT (external_id, tenant_id)
                        DO UPDATE SET
                            body = EXCLUDED.body,
                            updated_at_github = EXCLUDED.updated_at_github,
                            last_updated_at = EXCLUDED.last_updated_at
                    """)

                    db.execute(insert_query, {
                        'pr_id': pr_db_id,
                        'external_id': comment_data['id'],
                        'author_login': comment_data['author']['login'] if comment_data.get('author') else None,
                        'body': comment_data['body'],
                        'created_at_github': self._parse_datetime(comment_data['createdAt']),
                        'updated_at_github': self._parse_datetime(comment_data['updatedAt']) if comment_data.get('updatedAt') else None,
                        'path': comment_data.get('path'),
                        'position': comment_data.get('position'),
                        'integration_id': integration_id,
                        'tenant_id': tenant_id,
                        'active': True,
                        'created_at': DateTimeHelper.now_default(),
                        'last_updated_at': DateTimeHelper.now_default()
                    })
            except Exception as e:
                logger.warning(f"Error inserting review thread comment: {e}")

    def _queue_github_nested_entities_for_embedding(
        self,
        tenant_id: int,
        pr_external_id: str,
        job_id: int,
        integration_id: int,
        provider: str,
        first_item: bool = False,
        last_item: bool = False,
        last_job_item: bool = False,
        message: Dict[str, Any] = None,
        entities_to_queue: List[Dict[str, Any]] = None,
        token: str = None  # 🔑 Job execution token
    ) -> None:
        """
        Queue GitHub entities for embedding using individual entity messages.

        This queues individual PR, commits, reviews, and comments with their external IDs.
        Simple message structure: just pass external_id, embedding worker queries database.

        Args:
            tenant_id: Tenant ID
            pr_external_id: PR external ID
            job_id: ETL job ID
            integration_id: Integration ID
            provider: Provider name (github)
            first_item: Whether this is the first item in the step
            last_item: Whether this is the last item in the step
            last_job_item: Whether this is the last item in the entire job
            message: Original message (for provider/last_sync_date)
            entities_to_queue: List of dicts with 'table_name' and 'external_id'
        """
        try:
            if not entities_to_queue:
                logger.warning(f"⚠️ No entities provided for queuing GitHub entities")
                return

            # 🔑 Extract both dates from message
            old_last_sync_date = message.get('old_last_sync_date') if message else None  # old_last_sync_date (for filtering)
            new_last_sync_date = message.get('new_last_sync_date') if message else None  # extraction end date (for job completion)

            logger.debug(f"📤 Queuing {len(entities_to_queue)} GitHub entities for embedding (first_item={first_item}, last_item={last_item}, last_job_item={last_job_item})")

            for i, entity in enumerate(entities_to_queue):
                table_name = entity.get('table_name')
                external_id = entity.get('external_id')

                if not table_name or not external_id:
                    logger.warning(f"⚠️ Skipping entity with missing table_name or external_id: {entity}")
                    continue

                is_last = (i == len(entities_to_queue) - 1)
                entity_first_item = first_item and (i == 0)
                entity_last_item = is_last and last_item
                entity_last_job_item = is_last and last_job_item

                logger.debug(f"  Entity {i}/{len(entities_to_queue)}: {table_name} {external_id} (first={entity_first_item}, last={entity_last_item}, last_job={entity_last_job_item})")

                self.queue_manager.publish_embedding_job(
                    tenant_id=tenant_id,
                    table_name=table_name,
                    external_id=str(external_id),
                    job_id=job_id,
                    integration_id=integration_id,
                    provider=provider,
                    old_last_sync_date=old_last_sync_date,  # 🔑 Used for filtering (old_last_sync_date)
                    new_last_sync_date=new_last_sync_date,  # 🔑 Used for job completion (extraction end date)
                    first_item=entity_first_item,  # Only first entity has first_item=true
                    last_item=entity_last_item,  # Only last entity has last_item=true
                    last_job_item=entity_last_job_item,  # Only last entity signals job completion
                    step_type='github_prs_commits_reviews_comments',  # 🔑 ETL step name for status tracking
                    token=token  # 🔑 Include token in message
                )

            logger.debug(f"📤 Queued {len(entities_to_queue)} GitHub entities for embedding")

        except Exception as e:
            logger.error(f"❌ Error queuing GitHub nested entities for embedding: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")


    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        """Parse ISO8601 datetime strings from GitHub (handles trailing 'Z')."""
        if not value:
            return None
        try:
            if isinstance(value, str):
                # Normalize 'Z' to '+00:00' for fromisoformat
                return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
            return value
        except Exception:
            return None

    def _get_current_time(self) -> datetime:
        """Get current datetime in configured timezone for database timestamps."""
        from app.core.utils import DateTimeHelper
        return DateTimeHelper.now_default()

    def _calculate_pr_metrics(
        self,
        pr_data: Dict[str, Any],
        pr_commits: List[Dict[str, Any]],
        pr_reviews: List[Dict[str, Any]],
        pr_comments: List[Dict[str, Any]],
        pr_review_threads: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute PR metrics using available GraphQL payloads.
        Returns a dict with all expected metric fields present.
        """
        # Basic PR fields if present on PR node
        additions = pr_data.get('additions', 0) if isinstance(pr_data, dict) else 0
        deletions = pr_data.get('deletions', 0) if isinstance(pr_data, dict) else 0
        changed_files = pr_data.get('changedFiles', 0) if isinstance(pr_data, dict) else 0
        source = pr_data.get('headRefName') or pr_data.get('headRef', {}).get('name')
        destination = pr_data.get('baseRefName') or pr_data.get('baseRef', {}).get('name')

        # Commits
        commit_count = 0
        commit_dates: List[datetime] = []
        if pr_commits:
            for c in pr_commits:
                try:
                    commit_count += 1
                    authored = c.get('commit', {}).get('author', {}).get('date')
                    committed = c.get('commit', {}).get('committer', {}).get('date')
                    dt = self._parse_datetime(committed or authored)
                    if dt:
                        commit_dates.append(dt)
                except Exception:
                    continue

        # Reviews
        reviewers_set = set()
        first_review_at = None
        changes_requested_cycles = 0
        if pr_reviews:
            for r in pr_reviews:
                author_login = (r.get('author') or {}).get('login') if isinstance(r, dict) else None
                if author_login:
                    reviewers_set.add(author_login)
                submitted_at = r.get('submittedAt') if isinstance(r, dict) else None
                dt = self._parse_datetime(submitted_at)
                if dt:
                    if first_review_at is None or dt < first_review_at:
                        first_review_at = dt
                state = r.get('state') if isinstance(r, dict) else None
                if state == 'CHANGES_REQUESTED':
                    changes_requested_cycles += 1

        # Comments
        discussion_comment_count = len(pr_comments) if pr_comments else 0
        review_comment_count = 0
        if pr_review_threads:
            for t in pr_review_threads:
                try:
                    review_comment_count += len(((t.get('comments') or {}).get('nodes')) or [])
                except Exception:
                    continue

        # Rework commits (commits after first review)
        rework_commit_count = 0
        if first_review_at and commit_dates:
            for dt in commit_dates:
                if dt and dt > first_review_at:
                    rework_commit_count += 1

        return {
            'source': source,
            'destination': destination,
            'commit_count': commit_count,
            'additions': additions,
            'deletions': deletions,
            'changed_files': changed_files,
            'reviewers': len(reviewers_set),
            'first_review_at': first_review_at,
            'rework_commit_count': rework_commit_count,
            'review_cycles': changes_requested_cycles,
            'discussion_comment_count': discussion_comment_count,
            'review_comment_count': review_comment_count,
        }
