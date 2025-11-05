"""
GitHub Extraction Worker - Processes GitHub-specific extraction requests.

Handles GitHub extraction message types:
- github_repositories: Extract GitHub repositories using GitHub Search API
- github_prs_commits_reviews_comments: Extract PRs with nested data using GraphQL

This worker is called from the extraction_worker_router based on message type.

Features:
- GitHub Search API with smart batching for 256 char limit
- Jira PR links integration for non-health repositories
- LOOP 1/LOOP 2 pattern: Queue to transform + Queue to PR extraction
- Rate limit handling with checkpoint recovery
- Incremental sync support
- GraphQL-based PR extraction with nested data (commits, reviews, comments)
"""

import json
import urllib.parse
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy import text

from app.core.logging_config import get_logger
from app.models.unified_models import Integration
from app.core.config import AppConfig
from app.etl.github.github_graphql_client import GitHubGraphQLClient, GitHubRateLimitException
from app.etl.github.github_rest_client import GitHubRestClient

logger = get_logger(__name__)


class GitHubExtractionWorker:
    """
    Worker for processing GitHub-specific extraction requests.

    Note: This is NOT a queue consumer itself. It's called from ExtractionWorkerRouter
    which is the actual queue consumer. This class contains provider-specific logic.

    This worker delegates to the github_extraction module which contains all the
    production-ready extraction logic.
    """

    def __init__(self):
        """Initialize GitHub extraction worker."""
        logger.info("Initialized GitHubExtractionWorker")

    async def process_github_extraction(self, message_type: str, message: Dict[str, Any]) -> bool:
        """
        Route GitHub extraction message to appropriate processor.

        Args:
            message_type: Type of GitHub extraction message
            message: Message containing extraction request details

        Returns:
            bool: True if processing succeeded
        """
        try:
            logger.info(f"🚀 [GITHUB] process_github_extraction called with type={message_type}")

            if message_type == 'github_repositories':
                logger.info(f"🚀 [GITHUB] Processing github_repositories extraction")
                result = await self._extract_github_repositories(message)
                logger.info(f"🚀 [GITHUB] github_repositories extraction returned: {result}")
                return result
            elif message_type == 'github_prs_commits_reviews_comments':
                logger.info(f"🚀 [GITHUB] Processing github_prs_commits_reviews_comments extraction")
                result = await self._extract_github_prs(message)
                logger.info(f"🚀 [GITHUB] github_prs_commits_reviews_comments extraction returned: {result}")
                return result
            else:
                logger.warning(f"Unknown GitHub extraction type: {message_type}")
                return False
        except Exception as e:
            logger.error(f"💥 [GITHUB] Error in process_github_extraction: {e}")
            import traceback
            logger.error(f"💥 [GITHUB] Full traceback: {traceback.format_exc()}")
            return False

    async def _extract_github_repositories(self, message: Dict[str, Any]) -> bool:
        """
        Extract GitHub repositories for a tenant.

        Args:
            message: Message containing extraction request details

        Returns:
            bool: True if extraction succeeded
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            token = message.get('token')

            logger.info(f"🚀 [GITHUB] Starting repositories extraction for tenant {tenant_id}, integration {integration_id}")

            # Call the actual extraction method
            result = await self.extract_github_repositories(
                integration_id=integration_id,
                tenant_id=tenant_id,
                job_id=job_id,
                old_last_sync_date=None,
                token=token
            )

            if result.get('success'):
                logger.info(f"✅ [GITHUB] Repositories extraction completed for tenant {tenant_id}")
                logger.info(f"📊 [GITHUB] Processed {result.get('repositories_count', 0)} repositories")
                return True
            else:
                logger.error(f"❌ [GITHUB] Repositories extraction failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"💥 [GITHUB] Error extracting repositories: {e}")
            import traceback
            logger.error(f"💥 [GITHUB] Full traceback: {traceback.format_exc()}")
            return False

    async def _extract_github_prs(self, message: Dict[str, Any]) -> bool:
        """
        Extract PRs with nested data from GitHub.

        Args:
            message: Message containing extraction request details

        Returns:
            bool: True if extraction succeeded
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            token = message.get('token')
            owner = message.get('owner')
            repo_name = message.get('repo_name')
            pr_cursor = message.get('pr_cursor')
            first_item = message.get('first_item', False)
            old_last_sync_date = message.get('old_last_sync_date')
            new_last_sync_date = message.get('new_last_sync_date')
            last_repo = message.get('last_repo', False)

            logger.info(f"🚀 [GITHUB] Starting PRs extraction for tenant {tenant_id}, integration {integration_id}")

            # Call the actual extraction method
            result = await self.extract_github_prs_commits_reviews_comments(
                tenant_id=tenant_id,
                integration_id=integration_id,
                job_id=job_id,
                pr_cursor=pr_cursor,
                owner=owner,
                repo_name=repo_name,
                first_item=first_item,
                old_last_sync_date=old_last_sync_date,
                new_last_sync_date=new_last_sync_date,
                last_repo=last_repo,
                token=token
            )

            if result.get('success'):
                logger.info(f"✅ [GITHUB] PRs extraction completed for tenant {tenant_id}")
                return True
            else:
                logger.error(f"❌ [GITHUB] PRs extraction failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"❌ Error in GitHub PRs extraction: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    async def extract_github_repositories(self,
        integration_id: int,
        tenant_id: int,
        job_id: int,
        old_last_sync_date: Optional[str] = None,
        token: str = None  # 🔑 Job execution token
    ) -> Dict[str, Any]:
        """
        Extract GitHub repositories (Phase 3 / Step 1).

        This is the first step of the GitHub job. It extracts repositories from GitHub API
        using the same search approach as the old etl-service.

        Search Strategy:
        1. Query Jira PR links for non-health repository names
        2. Combine health- filter with non-health repo names using OR operators
        3. Use GitHub Search API exclusively with smart batching for 256 char limit

        Args:
            integration_id: GitHub integration ID
            tenant_id: Tenant ID
            job_id: ETL job ID
            old_last_sync_date: Last sync date for incremental extraction (YYYY-MM-DD format)

        Returns:
            Dictionary with extraction result
        """
        logger.info(f"🚀 [GITHUB] Starting repository extraction for tenant {tenant_id}, integration {integration_id}")

        # Set last_run_started_at at the beginning of extraction
        if job_id:
            self._set_job_start_time(job_id, tenant_id)

        from app.core.config import AppConfig

        try:
            # Get integration details
            from app.core.database_router import get_read_session_context
            with get_read_session_context() as db:  # This is a standalone function, not a method
                integration = db.query(Integration).filter(
                    Integration.id == integration_id,
                    Integration.tenant_id == tenant_id
                ).first()

                if not integration:
                    logger.error(f"Integration {integration_id} not found")
                    return {'success': False, 'error': f'Integration {integration_id} not found'}

                # Get GitHub token from encrypted password field (like Jira)
                if not integration.password:
                    logger.error("GitHub token not found in integration")
                    return {'success': False, 'error': 'GitHub token not found in integration'}

                # Decrypt the token
                key = AppConfig.load_key()
                github_token = AppConfig.decrypt_token(integration.password, key)

                # Get settings
                settings = integration.settings or {}

                # Get organization from settings
                org = settings.get('organization')
                if not org:
                    logger.error("GitHub organization not found in integration settings")
                    return {'success': False, 'error': 'GitHub organization not found in integration settings'}

                # Get repository filter patterns from settings (can be string or array)
                repository_filter = settings.get('repository_filter', ['health-'])

                # Handle both old string format and new array format for backward compatibility
                if isinstance(repository_filter, str):
                    name_filters = [repository_filter]
                else:
                    name_filters = repository_filter if repository_filter else ['health-']

                # Determine date range for search
                if old_last_sync_date:
                    start_date = old_last_sync_date
                else:
                    # Default: last 730 days
                    start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')

                # IMPORTANT: Capture current date at extraction start
                # This is the END date of the search range and will be used as the new_last_sync_date
                # for the NEXT job run (for incremental sync)
                end_date = datetime.now().strftime('%Y-%m-%d')

                logger.info(f"📅 Search date range: {start_date} to {end_date}")
                logger.info(f"🔍 Repository filters: {name_filters}")
                logger.info(f"🏢 Organization: {org}")
                logger.info(f"⏭️ Next sync will use new_last_sync_date: {end_date}")

                # Step 1: Query Jira PR links for non-health repository names
                logger.info("Step 1: Querying Jira PR links for repository names...")
                non_health_repo_names = set()

                try:
                    pr_links_query = text("""
                        SELECT DISTINCT r.full_name
                        FROM repositories r
                        JOIN prs pr ON pr.repository_id = r.id
                        JOIN work_items_prs_links wpl ON wpl.external_repo_id = pr.external_repo_id
                            AND wpl.pull_request_number = pr.number
                        WHERE r.tenant_id = :tenant_id
                            AND r.integration_id = :integration_id
                            AND r.active = TRUE
                            AND pr.active = TRUE
                            AND wpl.active = TRUE
                    """)

                    result = db.execute(pr_links_query, {
                        'tenant_id': tenant_id,
                        'integration_id': integration_id
                    })

                    for row in result:
                        repo_full_name = row[0]
                        if '/' in repo_full_name:
                            repo_name = repo_full_name.split('/', 1)[1]
                            # Filter out repos matching any of the filter patterns
                            should_exclude = False
                            for filter_pattern in name_filters:
                                clean_filter = filter_pattern.rstrip('-') if filter_pattern.endswith('-') else filter_pattern
                                if clean_filter and clean_filter in repo_name:
                                    should_exclude = True
                                    break
                            if not should_exclude:
                                non_health_repo_names.add(repo_name)

                    logger.info(f"Found {len(non_health_repo_names)} unique non-health repositories from Jira PR links")

                except Exception as e:
                    logger.warning(f"Could not query Jira PR links: {e}")
                    non_health_repo_names = set()

                # Store the integration data for use outside the session
                integration_data = {
                    'github_token': github_token,
                    'org': org,
                    'name_filters': name_filters,
                    'start_date': start_date,
                    'end_date': end_date,
                    'non_health_repo_names': non_health_repo_names
                }
                logger.info(f"✅ Exiting database session, integration_data prepared")
        except Exception as e:
            logger.error(f"❌ Error in database session: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise

        try:
            logger.info("Step 2: Searching GitHub repositories using combined search patterns...")
            logger.info(f"DEBUG: integration_data keys = {list(integration_data.keys())}")

            from app.etl.workers.queue_manager import QueueManager
            queue_manager = QueueManager()

            # Search GitHub repositories and accumulate all results
            total_repositories = 0

            # Get all repositories as a complete list using REST client
            rest_client = GitHubRestClient(integration_data['github_token'])
            all_repositories = rest_client.search_repositories(
                org=integration_data['org'],
                start_date=integration_data['start_date'],
                end_date=integration_data['end_date'],
                name_filters=integration_data['name_filters'],
                additional_repo_names=list(integration_data['non_health_repo_names']) if integration_data['non_health_repo_names'] else None
            )

            logger.info(f"📦 Retrieved {len(all_repositories)} total repositories from GitHub API")

            # Process each repository as a separate raw_extraction_data record
            if all_repositories:
                # 🔄 LOOP 1: Extract all repos and queue to transform
                logger.info(f"📤 [LOOP 1] Queuing {len(all_repositories)} repositories to transform")
                for i, repo in enumerate(all_repositories):
                    is_first = (i == 0)
                    is_last = (i == len(all_repositories) - 1)

                    # Store individual repository in raw_extraction_data
                    # 🔑 Transform worker expects 'repositories' key (array), so wrap single repo in array
                    raw_data_id = self.store_raw_extraction_data(
                        integration_id, tenant_id, "github_repositories",
                        {
                            'repositories': [repo],  # 🔑 Wrap in array with 'repositories' key
                            'search_date_range': {
                                'start_date': integration_data['start_date'],
                                'end_date': integration_data['end_date']
                            },
                            'search_filters': integration_data['name_filters'],
                            'organization': integration_data['org'],
                            'extracted_at': datetime.now().isoformat(),  # Using module-level import from line 24
                            'repo_index': i + 1,
                            'total_repositories': len(all_repositories)
                        }
                    )

                    if not raw_data_id:
                        logger.error(f"Failed to store raw repository data for repo {i+1}/{len(all_repositories)}")
                        return {'success': False, 'error': f'Failed to store raw repository data for repo {i+1}'}

                    # Queue for transform with proper first_item/last_item flags
                    # 🔑 first_item=true ONLY on first repository
                    # 🔑 last_item=true ONLY on last repository
                    # 🔑 last_repo=true ONLY on last repository (signals to Step 2 that this is the final repo)
                    logger.info(f"Queuing repository {i+1}/{len(all_repositories)} for transform (raw_data_id={raw_data_id}, first={is_first}, last={is_last})")
                    success = queue_manager.publish_transform_job(
                        tenant_id=tenant_id,
                        integration_id=integration_id,
                        raw_data_id=raw_data_id,
                        data_type='github_repositories',
                        job_id=job_id,
                        provider='github',
                        old_last_sync_date=old_last_sync_date,  # 🔑 Used for filtering (old_last_sync_date)
                        new_last_sync_date=end_date,  # 🔑 Used for job completion (extraction end date)
                        token=token,  # 🔑 Include token in message
                        first_item=is_first,              # 🔑 True only on first repo
                        last_item=is_last,                # 🔑 True only on last repo
                        last_job_item=False,              # 🔑 Never set to True here - job continues to PR extraction
                        last_repo=is_last                 # 🔑 True only on last repo - signals to Step 2
                    )

                    if not success:
                        logger.error(f"Failed to queue repository {i+1}/{len(all_repositories)} for transform")

                logger.info(f"✅ [LOOP 1 COMPLETE] All {len(all_repositories)} repositories queued to transform")

                # 🔑 LOOP 2: Queue each repository to Step 2 extraction (NO database query)
                logger.info(f"📤 [LOOP 2] Queuing {len(all_repositories)} repositories to Step 2 extraction")
                for i, repo in enumerate(all_repositories):
                    is_first = (i == 0)
                    is_last = (i == len(all_repositories) - 1)

                    # Queue PR extraction for this repository
                    # 🔑 NO database query - use repo data directly from extraction
                    logger.info(f"Queuing PR extraction for repository {i+1}/{len(all_repositories)}: {repo.get('full_name')} (first={is_first}, last={is_last})")

                    success_pr = queue_manager.publish_extraction_job(
                        tenant_id=tenant_id,
                        integration_id=integration_id,
                        extraction_type='github_prs_commits_reviews_comments',
                        extraction_data={
                            'owner': repo.get('owner', {}).get('login') if isinstance(repo.get('owner'), dict) else repo.get('owner'),
                            'repo_name': repo.get('name'),
                            'full_name': repo.get('full_name'),
                            'integration_id': integration_id  # 🔑 Pass integration_id to avoid DB query
                        },
                        job_id=job_id,
                        provider='github',
                        old_last_sync_date=old_last_sync_date,  # 🔑 Pass for incremental sync
                        new_last_sync_date=end_date,
                        token=token,  # 🔑 Include token in message
                        first_item=is_first,              # 🔑 True only on first repo
                        last_item=is_last,                # 🔑 True only on last repo
                        last_job_item=False,              # 🔑 Never set to True here - job continues
                        last_repo=is_last                 # 🔑 True only on last repo - signals to Step 2
                    )

                    if not success_pr:
                        logger.error(f"Failed to queue PR extraction for repository {i+1}/{len(all_repositories)}")

                logger.info(f"✅ [LOOP 2 COMPLETE] All {len(all_repositories)} repositories queued to Step 2 extraction")
                total_repositories = len(all_repositories)

            logger.info(f"✅ [GITHUB] Repository extraction completed: {total_repositories} repositories found and queued for transform and PR extraction")

            # 🏁 Handle case when NO repositories were found
            if total_repositories == 0:
                logger.info(f"📤 No repositories found - sending completion message to transform queue")
                # 🔑 Completion message pattern:
                # - raw_data_id=None signals this is a closing message
                # - last_job_item=True signals job completion
                # - Transform worker will set its own status to finished and forward to embedding
                # - Embedding worker will update its status and overall job status to finished
                success = queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    raw_data_id=None,  # 🔑 Completion message marker
                    data_type='github_repositories',
                    job_id=job_id,
                    provider='github',
                    old_last_sync_date=old_last_sync_date,  # 🔑 Used for filtering (old_last_sync_date)
                    new_last_sync_date=end_date,  # 🔑 Used for job completion (extraction end date)
                    first_item=True,
                    last_item=True,
                    last_job_item=True,  # 🔑 Signal job completion - transform will forward to embedding
                    token=token  # 🔑 Include token in message
                )
                if not success:
                    logger.error(f"Failed to queue completion message for no repositories case")

            return {
                'success': True,
                'repositories_count': total_repositories,
                'old_last_sync_date': old_last_sync_date,  # 🔑 Pass to PR extraction
                'message': f'Successfully extracted and queued {total_repositories} repositories'
            }

        except Exception as e:
            logger.error(f"❌ [GITHUB] Error extracting repositories: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}


    def store_raw_extraction_data(self, 
        integration_id: int,
        tenant_id: int,
        data_type: str,
        raw_data: Dict[str, Any]
    ) -> Optional[int]:
        """
        Store raw GitHub extraction data in raw_extraction_data table.

        This follows the same pattern as Jira extraction - stores complete batch response.

        Args:
            integration_id: Integration ID
            tenant_id: Tenant ID
            data_type: Type of data (e.g., 'github_repositories')
            raw_data: Raw data from GitHub API (complete batch response)

        Returns:
            raw_data_id if successful, None otherwise
        """
        try:
            from app.core.database import get_database
            database = get_database()

            with database.get_write_session_context() as db:
                insert_query = text("""
                    INSERT INTO raw_extraction_data (
                        tenant_id, integration_id, type,
                        raw_data, status, active, created_at
                    ) VALUES (
                        :tenant_id, :integration_id, :type,
                        CAST(:raw_data AS jsonb), 'pending', TRUE, NOW()
                    ) RETURNING id
                """)

                result = db.execute(insert_query, {
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'type': data_type,
                    'raw_data': json.dumps(raw_data)
                })

                raw_data_id = result.fetchone()[0]
                logger.info(f"✅ Stored raw GitHub data (type={data_type}) with ID {raw_data_id}")
                return raw_data_id

        except Exception as e:
            logger.error(f"❌ Error storing raw GitHub data: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None


    async def github_extraction_worker(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main extraction worker entry point - Routes to appropriate handler.

        This is the router for Phase 4 GitHub extraction. It checks the message type
        to determine whether to process a fresh/next PR page, nested pagination, or recovery.

        Message Types:
        1. Fresh/Next PR Page: pr_cursor (None or value), nested_type absent
        2. Nested Continuation: pr_node_id present, nested_type present
        3. Nested Recovery: type='github_nested_extraction_recovery', nested_nodes_status present

        Args:
            message: Queue message with extraction parameters

        Returns:
            Dictionary with extraction result
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')  # 🔑 Extract from message
            job_id = message.get('job_id')
            repository_id = message.get('repository_id')

            logger.info(f"🔀 [ROUTER] Extraction worker received message for repo {repository_id}")

            # 🔑 Extract token from message
            token = message.get('token')

            # ROUTER: Check if this is nested recovery from rate limit checkpoint
            if message.get('type') == 'github_nested_extraction_recovery':
                # NESTED RECOVERY: Resume from rate limit checkpoint
                logger.info(f"⏭️ [ROUTER] Routing to extract_nested_recovery (PR {message.get('pr_id')})")
                result = await extract_nested_recovery(
                    tenant_id=tenant_id,
                    integration_id=integration_id,  # 🔑 For service-to-service auth
                    job_id=job_id,
                    pr_id=message.get('pr_id'),
                    pr_node_id=message.get('pr_node_id'),
                    nested_nodes_status=message.get('nested_nodes_status', {}),
                    owner=message.get('owner'),  # 🔑 Pass repo info from message
                    repo_name=message.get('repo_name'),
                    full_name=message.get('full_name'),
                    old_last_sync_date=message.get('old_last_sync_date')
                )
            # ROUTER: Check if this is nested data continuation
            elif message.get('nested_type'):
                # NESTED CONTINUATION: Extract next page of nested data
                logger.info(f"🔀 [ROUTER] Routing to extract_nested_pagination (nested_type={message.get('nested_type')})")
                result = await extract_nested_pagination(
                    tenant_id=tenant_id,
                    integration_id=integration_id,  # 🔑 For service-to-service auth
                    job_id=job_id,
                    pr_node_id=message['pr_node_id'],
                    nested_type=message['nested_type'],
                    nested_cursor=message['nested_cursor'],
                    owner=message.get('owner'),  # 🔑 Pass repo info from message
                    repo_name=message.get('repo_name'),
                    full_name=message.get('full_name'),
                    old_last_sync_date=message.get('old_last_sync_date'),  # Forward from message
                    new_last_sync_date=message.get('new_last_sync_date'),  # 🔑 Forward from message
                    last_repo=message.get('last_repo', False),  # 🔑 Forward flag from message
                    last_pr_last_nested=message.get('last_pr', False),  # 🔑 Forward last_pr as last_pr_last_nested
                    token=token  # 🔑 Include token in message
                )
            else:
                # FRESH OR NEXT PR PAGE
                is_fresh = message.get('pr_cursor') is None
                logger.info(f"🔀 [ROUTER] Routing to extract_github_prs_commits_reviews_comments ({'fresh' if is_fresh else 'next'} page)")
                result = await extract_github_prs_commits_reviews_comments(
                    tenant_id=tenant_id,
                    integration_id=integration_id,  # 🔑 For service-to-service auth
                    job_id=job_id,
                    pr_cursor=message.get('pr_cursor'),  # None for fresh, value for next
                    owner=message.get('owner'),  # From message (avoids DB lookup)
                    repo_name=message.get('repo_name'),  # From message (avoids DB lookup)
                    first_item=message.get('first_item', False),  # 🔑 Forward from message
                    old_last_sync_date=message.get('old_last_sync_date'),  # 🔑 Old sync date for filtering
                    new_last_sync_date=message.get('new_last_sync_date'),  # 🔑 New sync date for job completion
                    token=token,  # 🔑 Include token in message
                    last_repo=message.get('last_repo', False)  # 🔑 Forward from message
                )

            return result

        except Exception as e:
            logger.error(f"❌ Extraction worker error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}


    async def extract_github_prs_commits_reviews_comments(self,
        tenant_id: int,
        integration_id: int,
        job_id: int,
        pr_cursor: Optional[str] = None,
        owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        first_item: bool = False,  # 🔑 NEW: Received from message
        old_last_sync_date: Optional[str] = None,  # 🔑 Old sync date for filtering
        new_last_sync_date: Optional[str] = None,  # 🔑 New sync date for job completion
        last_repo: bool = False,  # 🔑 NEW: True if this is the last repository
        token: str = None  # 🔑 Job execution token
    ) -> Dict[str, Any]:
        """
        Extract PRs with nested data (commits, reviews, comments) using GraphQL.

        This is Phase 4 / Step 2 of the GitHub job. It extracts pull requests with
        all nested data in a single GraphQL query, then queues them for transformation.

        NOTE: This function does NOT receive last_pr parameter because it cannot know
        if it's processing the last PR (it only sees one page at a time). The last_pr
        flag is calculated internally and passed to nested extraction messages.

        Checkpoint Recovery:
        - Saves PR cursor to etl_jobs.checkpoint_data for recovery
        - On restart, resumes from last saved cursor
        - Tracks nested cursors for each PR with incomplete data

        Flow:
        1. Fetch PR page (fresh or next)
        2. Split PRs into individual raw_data entries (Type 1: PR+nested)
        3. Queue all PRs to transform
        4. For each PR, calculate last_pr flag and queue nested pagination messages if needed
        5. Queue next PR page if exists
        6. Send completion message if last page (raw_data_id=None, last_job_item=True)
        7. Save checkpoint with PR cursor for recovery

        Args:
            tenant_id: Tenant ID
            job_id: ETL job ID
            repository_id: Repository ID
            pr_cursor: Cursor for pagination (None for fresh, value for next page)
            owner: Repository owner (optional, from message - avoids DB lookup)
            repo_name: Repository name (optional, from message - avoids DB lookup)
            first_item: True if this is the first PR of the first repository (from message)
            last_repo: True if this is the last repository (from message)
            old_last_sync_date: Old sync date for filtering PRs
            new_last_sync_date: New sync date for job completion tracking
            token: Job execution token

        Returns:
            Dictionary with extraction result
        """
        logger.info(f"🚀 [FUNCTION ENTRY] extract_github_prs_commits_reviews_comments called with pr_cursor={pr_cursor}, last_repo={last_repo}")
        try:
            is_fresh = (pr_cursor is None)
            logger.info(f"🚀 Starting GitHub PR extraction - {'Fresh' if is_fresh else 'Next'} page for {owner}/{repo_name}")

            # 🔑 IMPORTANT: Capture current date at start of extraction
            # This is the END date of the search range and will be used as new_last_sync_date
            # for the NEXT job run (for incremental sync)
            extraction_end_date = datetime.now().strftime('%Y-%m-%d')

            from app.core.database_router import get_read_session_context, get_write_session_context
            from app.core.config import AppConfig
            from app.etl.workers.queue_manager import QueueManager

            # 🔑 owner and repo_name should ALWAYS be provided from message (no DB query for data)
            if not owner or not repo_name:
                logger.error(f"owner and repo_name must be provided in message for PR extraction")
                return {'success': False, 'error': 'owner and repo_name required in message'}

            logger.info(f"✅ Using owner and repo_name from message: {owner}/{repo_name}")
            logger.info(f"📅 Using old_last_sync_date for filtering: {old_last_sync_date}")

            # 🔑 Get integration (service-to-service, not data processing)
            with get_read_session_context() as db:
                integration = db.query(Integration).filter(
                    Integration.id == integration_id,
                    Integration.tenant_id == tenant_id
                ).first()

                if not integration or not integration.password:
                    logger.error(f"Integration {integration_id} not found or token missing")
                    return {'success': False, 'error': 'Integration not found or token missing'}

            # Decrypt the token
            key = AppConfig.load_key()
            github_token = AppConfig.decrypt_token(integration.password, key)

            # Initialize clients
            from app.etl.github.github_graphql_client import GitHubGraphQLClient
            github_client = GitHubGraphQLClient(github_token)
            queue_manager = QueueManager()

            # STEP 1: Fetch PR page
            logger.info(f"🔄 Fetching PR page for {owner}/{repo_name} (cursor: {pr_cursor or 'None'})")
            try:
                pr_page = await github_client.get_pull_requests_with_details(
                    owner, repo_name, pr_cursor
                )
            except GitHubRateLimitException as e:
                logger.warning(f"⚠️ Rate limit hit during PR extraction: {e}")
                self._save_rate_limit_checkpoint(
                    job_id=job_id,
                    tenant_id=tenant_id,
                    rate_limit_node_type='prs',
                    last_pr_cursor=pr_cursor,
                    rate_limit_reset_at=github_client.rate_limit_reset
                )

                # 🔑 Send completion message to transform queue to signal job completion
                # This allows the job to finish gracefully even though we hit rate limit
                logger.info(f"📤 Sending completion message to transform queue due to rate limit")
                queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=integration.id,
                    raw_data_id=None,  # 🔑 Completion message marker
                    data_type='github_prs_commits_reviews_comments',
                    job_id=job_id,
                    provider='github',
                    old_last_sync_date=old_last_sync_date,  # 🔑 Forward old_last_sync_date
                    new_last_sync_date=new_last_sync_date,  # 🔑 Forward new_last_sync_date for job completion
                    first_item=False,
                    last_item=True,
                    last_job_item=True,  # 🔑 Signal job completion
                    token=token  # 🔑 Include token in message
                )

                return {
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'is_rate_limit': True,
                    'rate_limit_reset_at': github_client.rate_limit_reset
                }

            if not pr_page or 'data' not in pr_page:
                logger.error(f"Failed to fetch PR page for {owner}/{repo_name}")
                return {'success': False, 'error': 'Failed to fetch PR page'}

            prs = pr_page['data']['repository']['pullRequests']['nodes']
            if not prs:
                logger.warning(f"No PRs found in page for {owner}/{repo_name}")

                # 🔑 If this is the last repository (last_repo=true), send completion message
                if last_repo:
                    logger.info(f"🏁 [COMPLETION] No PRs found and this is the last repo - sending completion message")
                    queue_manager.publish_transform_job(
                        tenant_id=tenant_id,
                        integration_id=integration.id,
                        raw_data_id=None,  # 🔑 Completion message marker
                        data_type='github_prs_commits_reviews_comments',
                        job_id=job_id,
                        provider='github',
                        old_last_sync_date=old_last_sync_date,  # 🔑 Used for filtering (old_last_sync_date)
                        new_last_sync_date=extraction_end_date,  # 🔑 Used for job completion (extraction end date)
                        first_item=False,
                        last_item=True,
                        last_job_item=True,  # 🔑 Signal job completion
                        last_repo=last_repo,
                        last_pr=False,
                        token=token  # 🔑 Include token in message
                    )
                    logger.info(f"✅ Completion message queued to transform")

                return {'success': True, 'prs_processed': 0}

            logger.info(f"📝 Processing {len(prs)} PRs from page")

            # STEP 1.5: Filter PRs by old_last_sync_date for incremental sync
            # PRs are ordered by UPDATED_AT DESC, so we can stop early when reaching old PRs
            filtered_prs = []
            early_termination = False

            # 🔑 If no old_last_sync_date provided, use 2-year default (same as repository extraction)
            if not old_last_sync_date:
                # Using module-level imports from line 24
                two_years_ago = datetime.now() - timedelta(days=730)
                old_last_sync_date = two_years_ago.strftime('%Y-%m-%d')
                logger.info(f"📅 No old_last_sync_date provided, using 2-year default: {old_last_sync_date}")

            logger.info(f"🔍 Filtering PRs by old_last_sync_date: {old_last_sync_date}")
            from datetime import timezone  # Only need timezone, datetime already imported at module level

            # Parse old_last_sync_date (format: YYYY-MM-DD or YYYY-MM-DD HH:MM)
            try:
                if ' ' in old_last_sync_date:
                    # Has time component
                    last_sync_dt = datetime.fromisoformat(old_last_sync_date.replace(' ', 'T'))
                else:
                    # Date only, set to start of day (UTC timezone to match PR timestamps)
                    last_sync_dt = datetime.fromisoformat(old_last_sync_date + 'T00:00:00').replace(tzinfo=timezone.utc)
            except ValueError:
                logger.warning(f"Could not parse old_last_sync_date: {old_last_sync_date}, processing all PRs")
                filtered_prs = prs
            else:
                for pr in prs:
                    try:
                        # PR.updatedAt is ISO format: "2025-10-27T14:30:00Z"
                        pr_updated_at_str = pr.get('updatedAt', '')
                        if not pr_updated_at_str:
                            logger.warning(f"PR {pr.get('number')} has no updatedAt, including it")
                            filtered_prs.append(pr)
                            continue

                        # Parse PR updated time (already has timezone info from 'Z')
                        pr_updated_dt = datetime.fromisoformat(pr_updated_at_str.replace('Z', '+00:00'))

                        if pr_updated_dt > last_sync_dt:
                            # PR is newer than last sync, include it
                            filtered_prs.append(pr)
                        else:
                            # PR is older than last sync, stop pagination
                            logger.info(f"⏹️ PR {pr.get('number')} updated at {pr_updated_at_str} is older than old_last_sync_date {old_last_sync_date}, stopping pagination")
                            early_termination = True
                            break
                    except Exception as e:
                        logger.warning(f"Error parsing PR updated time: {e}, including PR")
                        filtered_prs.append(pr)

            logger.info(f"✅ Filtered {len(filtered_prs)} PRs (from {len(prs)} total)")

            # STEP 2: Split PRs into individual raw_data entries
            # 🔑 Clean structure: pr_data contains all nested data, no duplication
            raw_data_ids = []
            with get_write_session_context() as db:
                for pr in filtered_prs:
                    raw_data = {
                        'pr_id': pr['id'],
                        'owner': owner,  # 🔑 Include owner for transform to lookup repository
                        'repo_name': repo_name,  # 🔑 Include repo_name for transform to lookup repository
                        'full_name': f"{owner}/{repo_name}",  # 🔑 Include full_name for easier analysis
                        'pr_data': pr  # 🔑 pr_data already contains commits, reviews, comments, reviewThreads
                    }
                    raw_data_id = self._store_raw_extraction_data(
                        db, tenant_id, integration_id,
                        'github_prs_commits_reviews_comments',
                        raw_data, pr['id']  # 🔑 Use PR external_id (GitHub PR node_id)
                    )
                    raw_data_ids.append(raw_data_id)

            logger.info(f"💾 Stored {len(raw_data_ids)} raw data entries")

            # Get page info early to determine if there are more pages
            page_info = pr_page['data']['repository']['pullRequests']['pageInfo']
            has_next_page = page_info['hasNextPage']

            logger.info(f"📄 [PR PAGE INFO] hasNextPage={has_next_page}, endCursor={page_info.get('endCursor')}, PRs in page={len(filtered_prs)}")

            # STEP 3: Check if there are ANY nested pagination jobs needed
            # 🔑 This determines if last_item should be true on the last PR
            has_nested_pagination = False
            for pr in filtered_prs:
                if (pr['commits']['pageInfo']['hasNextPage'] or
                    pr['reviews']['pageInfo']['hasNextPage'] or
                    pr['comments']['pageInfo']['hasNextPage'] or
                    pr['reviewThreads']['pageInfo']['hasNextPage']):
                    has_nested_pagination = True
                    break

            logger.info(f"🔍 Has nested pagination: {has_nested_pagination}")

            # STEP 4: Queue all PRs to transform
            # 🔑 first_item=true ONLY on first PR when received from message
            # 🔑 last_item=true ONLY on last PR when no more PR pages to fetch
            # 🔑 Calculate last_pr for each PR in the page
            # last_pr=true ONLY when:
            #    - This is the last PR in the page (i == len(raw_data_ids) - 1)
            #    - AND no more PR pages (not has_next_page)
            #    - AND this is the last repository (last_repo=true)
            for i, raw_data_id in enumerate(raw_data_ids):
                is_first = (i == 0 and first_item)  # 🔑 Use received first_item flag, not is_fresh
                is_last_pr_in_page = (i == len(raw_data_ids) - 1)

                # 🔑 Calculate last_pr for THIS specific PR
                # Only true if this is the last PR in page AND no more pages AND last repo
                pr_last_pr = (is_last_pr_in_page and not has_next_page and last_repo)

                # 🔑 Set last_item=true ONLY when:
                # - This is the last PR (pr_last_pr=true)
                # - AND no nested pagination needed (all nested data fits in first page)
                # 🔑 NOTE: last_item signals end of THIS repository's PR extraction AND job completion
                is_last_item = (pr_last_pr and not has_nested_pagination)

                # 🔑 Only set last_job_item=true if:
                # - This is the last PR (pr_last_pr=true)
                # - AND no nested pagination needed
                is_last_job_item = is_last_item

                queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=integration.id,
                    raw_data_id=raw_data_id,
                    data_type='github_prs_commits_reviews_comments',
                    job_id=job_id,
                    provider='github',
                    old_last_sync_date=old_last_sync_date,  # 🔑 Used for filtering (old_last_sync_date)
                    new_last_sync_date=extraction_end_date,  # 🔑 Used for job completion (extraction end date)
                    first_item=is_first,
                    last_item=is_last_item,  # 🔑 True only when all conditions met
                    last_job_item=is_last_job_item,  # 🔑 True only when all conditions met
                    last_repo=last_repo,
                    last_pr=pr_last_pr,  # 🔑 Calculated per-PR
                    token=token  # 🔑 Include token in message
                )

            logger.info(f"📤 Queued {len(raw_data_ids)} PRs to transform")

            # STEP 5: Loop through each PR and queue nested pagination if needed
            # 🔑 Build list of nested types that need pagination for this PR
            for pr_index, pr in enumerate(filtered_prs):
                pr_node_id = pr['id']

                # Determine which nested types need pagination
                nested_types_needing_pagination = []
                if pr['commits']['pageInfo']['hasNextPage']:
                    nested_types_needing_pagination.append(('commits', pr['commits']['pageInfo']['endCursor']))
                if pr['reviews']['pageInfo']['hasNextPage']:
                    nested_types_needing_pagination.append(('reviews', pr['reviews']['pageInfo']['endCursor']))
                if pr['comments']['pageInfo']['hasNextPage']:
                    nested_types_needing_pagination.append(('comments', pr['comments']['pageInfo']['endCursor']))
                if pr['reviewThreads']['pageInfo']['hasNextPage']:
                    nested_types_needing_pagination.append(('review_threads', pr['reviewThreads']['pageInfo']['endCursor']))

                # Queue each nested type with index info
                # 🔑 Calculate last_pr_last_nested: true ONLY for the last nested type of the last PR
                # This simplifies the logic - nested extraction only needs to check this one flag
                is_last_pr_in_filtered = (pr_index == len(filtered_prs) - 1)

                total_nested_types = len(nested_types_needing_pagination)
                for nested_index, (nested_type, nested_cursor) in enumerate(nested_types_needing_pagination):
                    is_last_nested_type = (nested_index == total_nested_types - 1)

                    # 🔑 Set last_pr_last_nested=true ONLY for the last nested type of the last PR of the last repo
                    # This way, nested extraction only needs to check last_pr_last_nested (not is_last_nested_type)
                    last_pr_last_nested = (is_last_pr_in_filtered and not has_next_page and last_repo and is_last_nested_type)

                    queue_manager.publish_extraction_job(
                        tenant_id=tenant_id,
                        integration_id=integration_id,  # 🔑 Use integration_id from function parameter
                        extraction_type='github_prs_commits_reviews_comments',  # Route to github_extraction_worker
                        extraction_data={
                            'owner': owner,  # 🔑 Pass repo info instead of repository_id
                            'repo_name': repo_name,
                            'full_name': f"{owner}/{repo_name}",
                            'pr_node_id': pr_node_id,
                            'nested_type': nested_type,
                            'nested_cursor': nested_cursor
                        },
                        job_id=job_id,
                        provider='github',
                        old_last_sync_date=old_last_sync_date,  # 🔑 Used for filtering (old_last_sync_date)
                        new_last_sync_date=extraction_end_date,  # 🔑 Used for job completion (extraction end date)
                        first_item=False,
                        last_item=False,                    # 🔑 Will be set to true only on final nested page
                        last_job_item=False,                # 🔑 Will be set to true only on final nested page
                        last_repo=last_repo,                # 🔑 Forward: true if last repository
                        last_pr_last_nested=last_pr_last_nested  # 🔑 last_pr_last_nested: true ONLY for last nested type of last PR
                    )
                    logger.info(f"📤 Queued {nested_type} pagination (nested_type={nested_type}, last_pr_last_nested={last_pr_last_nested})")

            logger.info(f"📤 Queued nested pagination messages for PRs with incomplete data")

            # STEP 5: Queue next PR page if exists (and we didn't hit early termination)
            # 🔑 RELAY FLAGS: Pass last_repo=true to next page
            # This signals "you are processing the last repository" through the PR page chain
            next_pr_cursor = None
            logger.info(f"🔍 [NEXT PAGE CHECK] has_next_page={has_next_page}, early_termination={early_termination}")
            if has_next_page and not early_termination:
                next_pr_cursor = page_info['endCursor']
                logger.info(f"📤 [QUEUING NEXT PR PAGE] Cursor={next_pr_cursor}, last_repo={last_repo}")
                queue_manager.publish_extraction_job(
                    tenant_id=tenant_id,
                    integration_id=integration_id,  # 🔑 Use integration_id from function parameter
                    extraction_type='github_prs_commits_reviews_comments',  # Same as main extraction type
                    extraction_data={
                        'owner': owner,  # 🔑 Pass repo info instead of repository_id
                        'repo_name': repo_name,
                        'full_name': f"{owner}/{repo_name}",
                        'pr_cursor': next_pr_cursor,
                        'pr_node_id': None  # Fresh request for next page
                    },
                    job_id=job_id,
                    provider='github',
                    old_last_sync_date=old_last_sync_date,  # 🔑 Used for filtering (old_last_sync_date)
                    new_last_sync_date=extraction_end_date,  # 🔑 Used for job completion (extraction end date)
                    first_item=False,
                    last_item=False,           # 🔑 Not the last item yet - more PRs to process
                    last_job_item=False,       # 🔑 Not job completion yet
                    last_repo=last_repo        # 🔑 Forward: true if last repository
                )
                logger.info(f"📤 Queued next PR page to extraction queue with last_repo={last_repo}")
            elif early_termination:
                logger.info(f"⏹️ Early termination due to old PRs, not queuing next page")

            # STEP 6: Save checkpoint for recovery
            self._save_checkpoint(
                job_id, tenant_id,
                last_pr_cursor=next_pr_cursor,
                prs_processed=len(filtered_prs)
            )

            # 🔑 NOTE: Completion message is ONLY sent when there are NO PRs to extract
            # (see early return above when not prs). This ensures we only send one completion
            # message per repository extraction, not multiple times.

            logger.info(f"✅ PR extraction completed: {len(prs)} PRs processed")
            return {
                'success': True,
                'prs_processed': len(prs),
                'raw_data_ids_queued': len(raw_data_ids)
            }

        except Exception as e:
            logger.error(f"❌ Error in GitHub PR extraction: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}


    async def extract_nested_pagination(self,
        tenant_id: int,
        integration_id: int,
        job_id: int,
        pr_node_id: str,
        nested_type: str,
        nested_cursor: str,
        owner: Optional[str] = None,  # 🔑 Repository owner
        repo_name: Optional[str] = None,  # 🔑 Repository name
        full_name: Optional[str] = None,  # 🔑 Full repository name
        old_last_sync_date: Optional[str] = None,
        new_last_sync_date: Optional[str] = None,  # 🔑 NEW: Extraction end date for job completion
        last_repo: bool = False,  # 🔑 NEW: True if this is the last repository
        last_pr_last_nested: bool = False,  # 🔑 NEW: True ONLY for the last nested type of the last PR of the last repo
        token: str = None  # 🔑 Job execution token
    ) -> Dict[str, Any]:
        """
        Extract next page of nested data (commits, reviews, comments) for a specific PR.

        This handles pagination for nested data within a PR. When a PR has more commits,
        reviews, or comments than fit in the first page, this function fetches the next page.

        NOTE: This function calculates last_item and last_job_item internally based on
        has_more, last_repo, and last_pr_last_nested flags. The last_pr_last_nested flag is already set to true
        ONLY for the last nested type of the last PR, so we don't need to check is_last_nested_type.

        Flow:
        1. Fetch nested page
        2. Save to raw_data (Type 2: nested-only)
        3. Queue to transform
        4. If more pages exist, queue next nested page to extraction

        Args:
            tenant_id: Tenant ID
            job_id: ETL job ID
            repository_id: Repository ID
            pr_node_id: GraphQL node ID of the PR
            nested_type: Type of nested data ('commits', 'reviews', 'comments', 'review_threads')
            nested_cursor: Cursor for pagination
            owner: Repository owner (from message - avoids DB lookup)
            repo_name: Repository name (from message - avoids DB lookup)
            full_name: Full repository name (from message - avoids DB lookup)
            last_repo: True if this is the last repository (from message)
            last_pr_last_nested: True ONLY for the last nested type of the last PR of the last repo (from message)
            old_last_sync_date: Old sync date for filtering
            new_last_sync_date: New sync date for job completion tracking
            token: Job execution token

        Returns:
            Dictionary with extraction result
        """
        try:
            logger.info(f"🚀 Extracting nested {nested_type} for PR {pr_node_id}")

            from app.core.database_router import get_read_session_context, get_write_session_context
            from app.core.config import AppConfig
            from app.etl.workers.queue_manager import QueueManager

            # 🔑 Use owner/repo_name from message (no DB query for data)
            if not owner or not repo_name:
                logger.error(f"owner and repo_name required for nested extraction")
                return {'success': False, 'error': 'owner and repo_name required'}

            logger.info(f"✅ Using owner and repo_name from message: {owner}/{repo_name}")

            # 🔑 Get integration and GitHub token (service-to-service, not data processing)
            with get_read_session_context() as db:
                integration = db.query(Integration).filter(
                    Integration.id == integration_id,
                    Integration.tenant_id == tenant_id
                ).first()

            if not integration or not integration.password:
                logger.error(f"Integration {integration_id} not found or token missing")
                return {'success': False, 'error': 'Integration not found or token missing'}

            # Decrypt the token
            key = AppConfig.load_key()
            github_token = AppConfig.decrypt_token(integration.password, key)

            # Initialize clients
            from app.etl.github.github_graphql_client import GitHubGraphQLClient
            github_client = GitHubGraphQLClient(github_token)
            queue_manager = QueueManager()

            # STEP 1: Fetch nested page based on type
            logger.info(f"🔄 Fetching {nested_type} page for PR {pr_node_id}")

            try:
                if nested_type == 'commits':
                    response = await github_client.get_more_commits_for_pr(pr_node_id, nested_cursor)
                    nested_data = response['data']['node']['commits'] if response and 'data' in response else None
                elif nested_type == 'reviews':
                    response = await github_client.get_more_reviews_for_pr(pr_node_id, nested_cursor)
                    nested_data = response['data']['node']['reviews'] if response and 'data' in response else None
                elif nested_type == 'comments':
                    response = await github_client.get_more_comments_for_pr(pr_node_id, nested_cursor)
                    nested_data = response['data']['node']['comments'] if response and 'data' in response else None
                elif nested_type == 'review_threads':
                    response = await github_client.get_more_review_threads_for_pr(pr_node_id, nested_cursor)
                    nested_data = response['data']['node']['reviewThreads'] if response and 'data' in response else None
                else:
                    logger.error(f"Unknown nested_type: {nested_type}")
                    return {'success': False, 'error': f'Unknown nested_type: {nested_type}'}
            except GitHubRateLimitException as e:
                logger.warning(f"⚠️ Rate limit hit during {nested_type} extraction: {e}")
                self._save_rate_limit_checkpoint(
                    job_id=job_id,
                    tenant_id=tenant_id,
                    rate_limit_node_type=nested_type,
                    current_pr_id=pr_node_id,
                    current_pr_node_id=pr_node_id,
                    rate_limit_reset_at=github_client.rate_limit_reset
                )

                # 🔑 Send completion message to transform queue to signal job completion
                # This allows the job to finish gracefully even though we hit rate limit
                logger.info(f"📤 Sending completion message to transform queue due to rate limit in {nested_type}")
                queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=integration.id,
                    raw_data_id=None,  # 🔑 Completion message marker
                    data_type='github_prs_commits_reviews_comments',
                    job_id=job_id,
                    provider='github',
                    old_last_sync_date=old_last_sync_date,  # 🔑 Forward old_last_sync_date
                    new_last_sync_date=new_last_sync_date,  # 🔑 Forward new_last_sync_date for job completion
                    first_item=False,
                    last_item=True,
                    last_job_item=True,  # 🔑 Signal job completion
                    token=token  # 🔑 Include token in message
                )

                return {
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'is_rate_limit': True,
                    'rate_limit_reset_at': github_client.rate_limit_reset
                }

            if not nested_data:
                logger.error(f"Failed to fetch {nested_type} for PR {pr_node_id}")
                return {'success': False, 'error': f'Failed to fetch {nested_type}'}

            has_more = nested_data['pageInfo']['hasNextPage']

            # STEP 2: Save nested data to raw_data (Type 2)
            # 🔑 Include repo info for transform to lookup repository
            raw_data = {
                'pr_id': pr_node_id,
                'owner': owner,  # 🔑 Include repo info for transform
                'repo_name': repo_name,
                'full_name': full_name or f"{owner}/{repo_name}",
                'nested_type': nested_type,
                'data': nested_data['nodes'],
                'cursor': nested_data['pageInfo']['endCursor'] if has_more else None,
                'has_more': has_more
            }

            with get_write_session_context() as db:
                raw_data_id = self._store_raw_extraction_data(
                    db, tenant_id, integration_id,
                    'github_prs_nested',  # 🔑 Renamed from github_prs_commits_reviews_comments
                    raw_data, pr_node_id  # 🔑 Use PR node_id as external_id
                )

            logger.info(f"💾 Stored nested {nested_type} data (has_more={has_more})")

            # STEP 3: Determine if this is the last item to queue
            # 🔑 last_item=true ONLY if:
            #    - last_pr_last_nested=true (already incorporates last nested type + last PR + last repo)
            #    - AND there are no more pages for this nested type (not has_more)
            # 🔑 NOTE: last_item signals "end of step" - only true on FINAL item of ENTIRE job
            is_last_item = (last_pr_last_nested and not has_more)

            # 🔑 last_job_item=true ONLY if:
            #    - last_pr_last_nested=true (already incorporates last nested type + last PR + last repo)
            #    - AND there are no more pages for this nested type (not has_more)
            # 🔑 NOTE: last_job_item signals "end of job" - same conditions as last_item for nested extraction
            is_last_job_item = (last_pr_last_nested and not has_more)

            # STEP 4: Queue to transform
            queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration.id,
                raw_data_id=raw_data_id,
                data_type='github_prs_commits_reviews_comments',
                job_id=job_id,
                provider='github',
                old_last_sync_date=last_sync_date,  # 🔑 Used for filtering (old_last_sync_date)
                new_last_sync_date=new_last_sync_date,  # 🔑 Used for job completion (extraction end date)
                first_item=False,
                last_item=is_last_item,  # 🔑 True only on last page of last nested type of last PR of last repo
                last_job_item=is_last_job_item,  # 🔑 True only on last page of last nested type of last PR of last repo
                last_repo=last_repo,
                last_pr_last_nested=last_pr_last_nested,
                token=token  # 🔑 Include token in message
            )

            logger.info(f"📤 Queued {nested_type} page to transform (last_item={is_last_item}, last_job_item={is_last_job_item})")

            # STEP 5: If more pages exist, queue next nested page to extraction
            # 🔑 Forward last_pr_last_nested to next nested page
            if has_more:
                queue_manager.publish_extraction_job(
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    extraction_type='github_prs_commits_reviews_comments',  # Route to github_extraction_worker
                    extraction_data={
                        'owner': owner,  # 🔑 Pass repo info instead of repository_id
                        'repo_name': repo_name,
                        'full_name': full_name or f"{owner}/{repo_name}",
                        'pr_node_id': pr_node_id,
                        'nested_type': nested_type,
                        'nested_cursor': nested_data['pageInfo']['endCursor']
                    },
                    job_id=job_id,
                    provider='github',
                    old_last_sync_date=old_last_sync_date,  # 🔑 Used for filtering (old_last_sync_date)
                    new_last_sync_date=new_last_sync_date,  # 🔑 Used for job completion (extraction end date)
                    first_item=False,
                    last_item=False,                # 🔑 Will be set to true only on final nested page
                    last_job_item=False,            # 🔑 Will be set to true only on final nested page
                    last_repo=last_repo,            # 🔑 Forward: true if last repository
                    last_pr_last_nested=last_pr_last_nested,  # 🔑 Forward: last_pr_last_nested
                    token=token  # 🔑 CRITICAL: Forward token to nested extraction
                )
                logger.info(f"📤 Queued next {nested_type} page to extraction queue with last_repo={last_repo}, last_pr_last_nested={last_pr_last_nested}")
            # 🔑 NOTE: Do NOT send completion message here!
            # Completion message is only sent from main PR extraction when no more PR pages exist.
            # Nested pagination extraction doesn't know about other PRs or PR pages.

            logger.info(f"✅ Nested {nested_type} extraction completed (items: {len(nested_data['nodes'])})")
            return {
                'success': True,
                'nested_type': nested_type,
                'items_processed': len(nested_data['nodes']),
                'has_more': has_more
            }

        except Exception as e:
            logger.error(f"❌ Error in nested pagination for {nested_type}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}


    async def extract_nested_recovery(self, 
        tenant_id: int,
        integration_id: int,
        job_id: int,
        pr_id: str,
        pr_node_id: str,
        nested_nodes_status: Dict[str, Any],
        owner: Optional[str] = None,  # 🔑 Repository owner
        repo_name: Optional[str] = None,  # 🔑 Repository name
        full_name: Optional[str] = None,  # 🔑 Full repository name
        old_last_sync_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resume nested extraction from rate limit checkpoint.

        Handles partial nested data state:
        - Skip nodes marked as complete (has_next_page: false)
        - Continue pagination for nodes with has_next_page: true
        - Fetch from scratch for nodes with fetched: false

        Args:
            tenant_id: Tenant ID
            job_id: ETL job ID
            repository_id: Repository ID
            pr_id: PR ID
            pr_node_id: GraphQL node ID of the PR
            nested_nodes_status: Status of nested nodes from checkpoint
            old_last_sync_date: Last sync date for incremental extraction

        Returns:
            Dictionary with extraction result
        """
        try:
            logger.info(f"⏭️ Resuming nested extraction for PR {pr_id} from checkpoint")

            from app.core.database_router import get_read_session_context

            # Get repository info
            with get_read_session_context() as db:
                from app.models.unified_models import Repository
                repository = db.query(Repository).filter(
                    Repository.id == repository_id,
                    Repository.tenant_id == tenant_id
                ).first()

            if not repository:
                return {'success': False, 'error': 'Repository not found'}

            # Get integration and GitHub token
            with get_read_session_context() as db:
                integration = db.query(Integration).filter(
                    Integration.id == repository.integration_id,
                    Integration.tenant_id == tenant_id
                ).first()

            if not integration or not integration.password:
                return {'success': False, 'error': 'Integration not found or token missing'}

            # Process each nested node type
            nested_types = ['commits', 'reviews', 'comments', 'review_threads']

            for nested_type in nested_types:
                node_status = nested_nodes_status.get(nested_type, {})

                if node_status.get('fetched') and not node_status.get('has_next_page'):
                    # Node is complete, skip it
                    logger.info(f"⏭️  Skipping {nested_type} (already complete)")
                    continue

                if node_status.get('fetched') and node_status.get('has_next_page'):
                    # Continue pagination from saved cursor
                    logger.info(f"🔄 Continuing {nested_type} pagination from cursor")
                    cursor = node_status.get('cursor')

                    result = await extract_nested_pagination(
                        tenant_id=tenant_id,
                        integration_id=integration_id,  # 🔑 For service-to-service auth
                        job_id=job_id,
                        pr_node_id=pr_node_id,
                        nested_type=nested_type,
                        nested_cursor=cursor,
                        owner=owner,  # 🔑 Pass repo info
                        repo_name=repo_name,
                        full_name=full_name,
                        old_last_sync_date=old_last_sync_date
                    )

                    if not result.get('success'):
                        if result.get('is_rate_limit'):
                            # Another rate limit hit, return with is_rate_limit flag
                            return result
                        logger.warning(f"Failed to continue {nested_type} pagination: {result.get('error')}")

                elif not node_status.get('fetched'):
                    # Fetch from scratch
                    logger.info(f"🔄 Fetching {nested_type} from scratch")

                    result = await extract_nested_pagination(
                        tenant_id=tenant_id,
                        integration_id=integration_id,  # 🔑 For service-to-service auth
                        job_id=job_id,
                        pr_node_id=pr_node_id,
                        nested_type=nested_type,
                        nested_cursor=None,  # Start from beginning
                        owner=owner,  # 🔑 Pass repo info
                        repo_name=repo_name,
                        full_name=full_name,
                        old_last_sync_date=old_last_sync_date
                    )

                    if not result.get('success'):
                        if result.get('is_rate_limit'):
                            # Rate limit hit, return with is_rate_limit flag
                            return result
                        logger.warning(f"Failed to fetch {nested_type}: {result.get('error')}")

            logger.info(f"✅ Nested extraction recovery completed for PR {pr_id}")
            return {'success': True, 'pr_id': pr_id}

        except Exception as e:
            logger.error(f"❌ Error in nested extraction recovery: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}


    def _store_raw_extraction_data(self, 
        db,
        tenant_id: int,
        integration_id: int,
        entity_type: str,
        raw_data: Dict[str, Any],
        external_id: str
    ) -> int:
        """
        Store raw extraction data in the database.

        Args:
            db: Database session
            tenant_id: Tenant ID
            integration_id: Integration ID
            entity_type: Type of entity being stored
            raw_data: Raw data dictionary
            external_id: External ID for the entity

        Returns:
            ID of the stored raw_extraction_data record
        """
        from app.core.utils import DateTimeHelper

        insert_query = text("""
            INSERT INTO raw_extraction_data (
                tenant_id, integration_id, type, raw_data, external_id, created_at
            ) VALUES (
                :tenant_id, :integration_id, :type, :raw_data, :external_id, :created_at
            )
            RETURNING id
        """)

        result = db.execute(insert_query, {
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'type': entity_type,
            'raw_data': json.dumps(raw_data),
            'external_id': external_id,
            'created_at': DateTimeHelper.now_default()
        })

        raw_data_id = result.scalar()
        logger.debug(f"Stored raw_extraction_data with ID {raw_data_id}")
        return raw_data_id


    def _save_checkpoint(self, 
        job_id: int,
        tenant_id: int,
        last_pr_cursor: Optional[str] = None,
        prs_processed: int = 0
    ):
        """
        Save checkpoint data for recovery in case of failure.

        Stores PR cursor and other state in etl_jobs.checkpoint_data JSON field
        for recovery on restart.

        Args:
            job_id: ETL job ID
            tenant_id: Tenant ID
            last_pr_cursor: Cursor for next PR page (None if no more pages)
            prs_processed: Number of PRs processed in this batch
        """
        try:
            from app.core.database import get_database
            from app.core.utils import DateTimeHelper

            database = get_database()

            checkpoint_data = {
                'last_pr_cursor': last_pr_cursor,
                'prs_processed': prs_processed,
                'checkpoint_timestamp': DateTimeHelper.now_default().isoformat()
            }

            with database.get_write_session_context() as db:
                update_query = text("""
                    UPDATE etl_jobs
                    SET checkpoint_data = :checkpoint_data,
                        last_updated_at = NOW()
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)
                db.execute(update_query, {
                    'job_id': job_id,
                    'tenant_id': tenant_id,
                    'checkpoint_data': json.dumps(checkpoint_data)
                })
                logger.info(f"✅ Saved checkpoint: {checkpoint_data}")
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")


    def _save_rate_limit_checkpoint(self, 
        job_id: int,
        tenant_id: int,
        rate_limit_node_type: str,
        current_pr_id: Optional[str] = None,
        current_pr_node_id: Optional[str] = None,
        last_pr_cursor: Optional[str] = None,
        nested_nodes_status: Optional[Dict[str, Any]] = None,
        rate_limit_reset_at: Optional[str] = None,
        last_repo_pushed_date: Optional[str] = None
    ):
        """
        Save checkpoint when rate limit is hit.

        Stores complete state information for recovery:
        - WHERE rate limit occurred (node_type)
        - WHAT was already fetched (nested_nodes_status)
        - WHEN to retry (rate_limit_reset_at)
        - For repositories: last_repo_pushed_date for resume query

        Args:
            job_id: ETL job ID
            tenant_id: Tenant ID
            rate_limit_node_type: 'repositories', 'prs', 'commits', 'reviews', 'comments', 'review_threads'
            current_pr_id: PR ID if rate limit hit during nested extraction
            current_pr_node_id: PR node ID for GraphQL queries
            last_pr_cursor: Cursor for PR pagination (if PR-level rate limit)
            nested_nodes_status: Dict tracking which nested nodes were fetched
            rate_limit_reset_at: When rate limit resets (ISO format)
            last_repo_pushed_date: Last repo's pushed date (YYYY-MM-DD) for repository extraction resume
        """
        try:
            from app.core.database import get_database
            from app.core.utils import DateTimeHelper

            database = get_database()

            checkpoint_data = {
                'rate_limit_hit': True,
                'rate_limit_node_type': rate_limit_node_type,
                'rate_limit_reset_at': rate_limit_reset_at or (DateTimeHelper.now_default() + timedelta(minutes=1)).isoformat(),
                'current_pr_id': current_pr_id,
                'current_pr_node_id': current_pr_node_id,
                'last_pr_cursor': last_pr_cursor,
                'nested_nodes_status': nested_nodes_status or {},
                'last_repo_pushed_date': last_repo_pushed_date
            }

            with database.get_write_session_context() as db:
                update_query = text("""
                    UPDATE etl_jobs
                    SET checkpoint_data = :checkpoint_data,
                        last_updated_at = NOW()
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)
                db.execute(update_query, {
                    'job_id': job_id,
                    'tenant_id': tenant_id,
                    'checkpoint_data': json.dumps(checkpoint_data)
                })
                logger.info(f"✅ Saved rate limit checkpoint: node_type={rate_limit_node_type}, reset_at={checkpoint_data['rate_limit_reset_at']}")
        except Exception as e:
            logger.error(f"Error saving rate limit checkpoint: {e}")


    def _set_job_start_time(self, job_id: int, tenant_id: int):
        """
        Set last_run_started_at timestamp for the job at the beginning of extraction.

        This follows the same pattern as Jira extraction.

        Args:
            job_id: ETL job ID
            tenant_id: Tenant ID
        """
        try:
            from app.core.database import get_database
            from app.core.utils import DateTimeHelper

            database = get_database()
            job_start_time = DateTimeHelper.now_default()

            with database.get_write_session_context() as db:
                update_query = text("""
                    UPDATE etl_jobs
                    SET last_run_started_at = :job_start_time,
                        last_updated_at = :job_start_time
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)
                db.execute(update_query, {
                    'job_id': job_id,
                    'tenant_id': tenant_id,
                    'job_start_time': job_start_time
                })
                logger.info(f"✅ Set last_run_started_at to {job_start_time} for job {job_id}")
        except Exception as e:
            logger.error(f"Error setting job start time: {e}")

