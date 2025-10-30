"""
GitHub Extraction Module for ETL Backend Service
Handles complete GitHub extraction including repositories, pull requests, commits, reviews, and comments.

This module provides functions to extract GitHub data and store it in the raw_extraction_data table
for subsequent transformation and embedding.

Flow:
1. Extract data from GitHub API (repositories, PRs, commits, reviews, comments)
2. Store raw data in raw_extraction_data table with raw_data_id
3. Queue for transformation with raw_data_id reference
4. Transform worker processes and stores in appropriate tables
5. Embedding worker vectorizes data

Phase 3 (Current): github_repositories (Step 1)
Phase 4 (Future): github_pull_requests, github_commits, github_reviews, github_comments (Steps 2-5)
"""

import json
import logging
import urllib.parse
from typing import Dict, Any, Optional
from sqlalchemy import text
from datetime import datetime, timedelta

from app.models.unified_models import Integration
from app.core.config import AppConfig
from app.etl.github_graphql_client import GitHubRateLimitException

logger = logging.getLogger(__name__)


async def extract_github_repositories(
    integration_id: int,
    tenant_id: int,
    job_id: int,
    last_sync_date: Optional[str] = None
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
        last_sync_date: Last sync date for incremental extraction (YYYY-MM-DD format)

    Returns:
        Dictionary with extraction result
    """
    logger.info(f"🚀 [GITHUB] Starting repository extraction for tenant {tenant_id}, integration {integration_id}")

    # Set last_run_started_at at the beginning of extraction
    if job_id:
        _set_job_start_time(job_id, tenant_id)

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
            if last_sync_date:
                start_date = last_sync_date
            else:
                # Default: last 90 days
                start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

            end_date = datetime.now().strftime('%Y-%m-%d')

            logger.info(f"📅 Search date range: {start_date} to {end_date}")
            logger.info(f"🔍 Repository filters: {name_filters}")
            logger.info(f"🏢 Organization: {org}")

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

        from app.etl.queue.queue_manager import QueueManager
        queue_manager = QueueManager()

        # Search GitHub repositories incrementally and queue as we go
        # This prevents large payloads and allows streaming processing
        total_repositories = 0
        is_first_batch = True
        last_repo_pushed_date = None  # Track for rate limit recovery

        try:
            repositories_generator = _search_github_repositories_paginated(
                token=integration_data['github_token'],
                org=integration_data['org'],
                start_date=integration_data['start_date'],
                end_date=integration_data['end_date'],
                name_filters=integration_data['name_filters'],
                additional_repo_names=list(integration_data['non_health_repo_names']) if integration_data['non_health_repo_names'] else None
            )

            # Process each batch of repositories
            is_first_batch_overall = True  # Track if this is the first batch across all pages
            for batch_repos, is_last_batch in repositories_generator:
                logger.info(f"📊 Processing batch of {len(batch_repos)} repositories (is_last_batch={is_last_batch})")

                # Track last repo's pushed date for rate limit recovery
                if batch_repos:
                    last_repo = batch_repos[-1]  # Last repo in batch
                    if 'pushed_at' in last_repo:
                        # Extract date only (YYYY-MM-DD) without time
                        last_repo_pushed_date = last_repo['pushed_at'].split('T')[0]
                        logger.info(f"📅 Last repo pushed date: {last_repo_pushed_date}")

                # Store batch in raw_extraction_data
                raw_data_id = store_raw_extraction_data(
                    integration_id, tenant_id, "github_repositories",
                    {
                        'repositories': batch_repos,
                        'search_date_range': {
                            'start_date': integration_data['start_date'],
                            'end_date': integration_data['end_date']
                        },
                        'search_filters': integration_data['name_filters'],
                        'organization': integration_data['org'],
                        'extracted_at': datetime.now().isoformat(),
                        'batch_info': {
                            'is_first_batch': is_first_batch_overall,
                            'is_last_batch': is_last_batch
                        }
                    }
                )

                if not raw_data_id:
                    logger.error("Failed to store raw repository batch data")
                    return {'success': False, 'error': 'Failed to store raw repository batch data'}

                # Queue for transform with proper first_item/last_item flags
                # 🔑 first_item=true ONLY on first batch of first page
                # 🔑 last_item=true ONLY on last batch of last page
                logger.info(f"Queuing batch of {len(batch_repos)} repositories for transform (raw_data_id={raw_data_id}, first={is_first_batch_overall}, last={is_last_batch})")
                success = queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    raw_data_id=raw_data_id,
                    data_type='github_repositories',
                    job_id=job_id,
                    provider='github',
                    last_sync_date=last_sync_date,
                    first_item=is_first_batch_overall,  # 🔑 True only on first batch overall
                    last_item=is_last_batch,            # 🔑 True only on last batch
                    last_job_item=False                 # 🔑 Never set to True here - job continues to PR extraction
                )

                if not success:
                    logger.error(f"Failed to queue repository batch for transform")

                total_repositories += len(batch_repos)
                is_first_batch_overall = False  # After first batch, never true again

            logger.info(f"✅ [GITHUB] Repository extraction completed: {total_repositories} repositories found and queued for transform")

            # 🎯 Handle case when NO repositories were found
            if total_repositories == 0:
                logger.info(f"📤 No repositories found - sending completion message to transform queue")
                success = queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    raw_data_id=None,  # 🔑 Completion message marker
                    data_type='github_repositories',
                    job_id=job_id,
                    provider='github',
                    last_sync_date=last_sync_date,
                    first_item=True,
                    last_item=True,
                    last_job_item=True  # 🔑 Complete the job since no data to process
                )
                if not success:
                    logger.error(f"Failed to queue completion message for no repositories case")

            return {
                'success': True,
                'repositories_count': total_repositories,
                'last_sync_date': last_sync_date,  # 🔑 Pass to PR extraction
                'message': f'Successfully extracted and queued {total_repositories} repositories'
            }

        except StopIteration:
            # Generator exhausted normally
            logger.info(f"✅ [GITHUB] Repository extraction completed: {total_repositories} repositories found and queued for transform")

            # 🎯 Handle case when NO repositories were found
            if total_repositories == 0:
                logger.info(f"📤 No repositories found - sending completion message to transform queue")
                success = queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    raw_data_id=None,  # 🔑 Completion message marker
                    data_type='github_repositories',
                    job_id=job_id,
                    provider='github',
                    last_sync_date=last_sync_date,
                    first_item=True,
                    last_item=True,
                    last_job_item=True  # 🔑 Complete the job since no data to process
                )
                if not success:
                    logger.error(f"Failed to queue completion message for no repositories case")

            return {
                'success': True,
                'repositories_count': total_repositories,
                'last_sync_date': last_sync_date,  # 🔑 Pass to PR extraction
                'message': f'Successfully extracted and queued {total_repositories} repositories'
            }

    except Exception as e:
        logger.error(f"❌ [GITHUB] Error extracting repositories: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return {'success': False, 'error': str(e)}


def store_raw_extraction_data(
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


def _search_github_repositories_paginated(
    token: str,
    org: str,
    start_date: str,
    end_date: str,
    name_filter: Optional[str] = None,
    name_filters: Optional[list] = None,
    additional_repo_names: Optional[list] = None
):
    """
    Search GitHub repositories using the GitHub Search API with pagination.

    Yields batches of repositories as they are fetched, allowing incremental processing
    without loading all results into memory first.

    Uses combined search patterns with OR operators to find repositories matching:
    1. The name_filters patterns (e.g., ['health-', 'bp-'])
    2. Specific repository names from Jira PR links

    Handles the 256 character limit by batching search patterns.

    Args:
        token: GitHub personal access token
        org: Organization name (e.g., 'wexinc')
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        name_filter: (Deprecated) Single pattern filter for backward compatibility
        name_filters: Array of pattern filters (e.g., ['health-', 'bp-'])
        additional_repo_names: List of specific repo names to include

    Yields:
        Tuple of (batch_repos: list, is_last_batch: bool)
    """
    import httpx

    # Handle both old string format and new array format for backward compatibility
    filters_to_use = name_filters if name_filters else (
        [name_filter] if name_filter else []
    )

    logger.info(f"🔍 [GITHUB SEARCH] Starting repository search with token={token[:20]}..., org={org}, filters={filters_to_use}")

    try:
        # Base query parts that are always included
        base_query_parts = [f"org:{org}", f"pushed:{start_date}..{end_date}"]
        base_query = " ".join(base_query_parts)
        logger.info(f"🔍 [GITHUB SEARCH] Base query: {base_query}")

        # Build search patterns
        search_patterns = []

        # Add name filter patterns if provided
        if filters_to_use:
            for filter_pattern in filters_to_use:
                # Keep the filter as-is (including trailing hyphens) - httpx will handle URL encoding properly
                search_patterns.append(f"{filter_pattern} in:name")
                logger.info(f"🔍 [GITHUB SEARCH] Added filter pattern: {filter_pattern} in:name")

        # Add specific repo names
        if additional_repo_names:
            logger.info(f"🔍 [GITHUB SEARCH] Adding {len(additional_repo_names)} additional repo names")
            for full_name in additional_repo_names:
                if '/' in full_name:
                    repo_name = full_name.split('/', 1)[1]  # Get part after '/'
                else:
                    repo_name = full_name
                search_patterns.append(f"{repo_name} in:name")

        batch_size = 100  # Batch size for yielding results

        if not search_patterns:
            logger.warning("🔍 [GITHUB SEARCH] No search patterns provided for GitHub repository search")
            return

        logger.info(f"🔍 [GITHUB SEARCH] Total search patterns: {len(search_patterns)}")

        # Batch patterns to stay within 256 character limit
        pattern_batches = _batch_search_patterns(base_query, search_patterns, max_length=256)

        logger.info(f"🔍 [GITHUB SEARCH] Executing {len(pattern_batches)} search requests to stay within character limit")

        # Execute each batch
        logger.info(f"🔍 [GITHUB SEARCH] Creating HTTP client...")
        with httpx.Client() as client:
            logger.info(f"🔍 [GITHUB SEARCH] HTTP client created successfully")
            total_repos_yielded = 0
            for i, batch_patterns in enumerate(pattern_batches, 1):
                # Combine patterns with OR and wrap in parentheses for proper GitHub search syntax
                combined_patterns = " OR ".join(batch_patterns)
                full_query = f"{base_query} ({combined_patterns})"

                logger.info(f"🔍 [GITHUB SEARCH] Batch {i}/{len(pattern_batches)}: Query length = {len(full_query)}, Query = {full_query[:100]}...")

                endpoint = "https://api.github.com/search/repositories"
                params = {
                    "q": full_query,
                    "sort": "updated",
                    "order": "asc",
                    "per_page": 100
                }

                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "ETL-Service/1.0"
                }

                logger.info(f"🔍 [GITHUB SEARCH] Making HTTP request to {endpoint}?q={urllib.parse.quote(full_query)}")
                try:
                    # Paginate through search results using Link header
                    # Yield batches as we fetch them to avoid loading all into memory
                    accumulated_repos = []
                    next_url = None
                    page = 1
                    is_last_pattern_batch = (i == len(pattern_batches))

                    while True:
                        if next_url:
                            # Use the next URL from Link header
                            logger.debug(f"🔍 [GITHUB SEARCH] Using next URL from Link header: {next_url[:100]}...")
                            response = client.get(next_url, headers=headers, timeout=30.0)
                        else:
                            # First request with params
                            current_params = {**params, "page": page}
                            logger.debug(f"🔍 [GITHUB SEARCH] Sending request with params: {current_params}")
                            response = client.get(endpoint, params=current_params, headers=headers, timeout=30.0)

                        logger.info(f"🔍 [GITHUB SEARCH] Response status: {response.status_code}")

                        # Check for rate limit (403 or 429)
                        if response.status_code in (403, 429):
                            logger.warning(f"⏸️ Rate limit hit during repository search: {response.status_code}")
                            # Extract reset time from headers
                            reset_time = response.headers.get('X-RateLimit-Reset')
                            if reset_time:
                                from datetime import datetime
                                reset_at = datetime.utcfromtimestamp(int(reset_time)).isoformat() + 'Z'
                                logger.warning(f"Rate limit resets at: {reset_at}")
                            else:
                                reset_at = None

                            # Raise custom exception to be caught by caller
                            raise GitHubRateLimitException(
                                f"GitHub Search API rate limit exceeded (status {response.status_code})",
                                reset_at=reset_at
                            )

                        if response.status_code != 200:
                            logger.error(f"GitHub API error: {response.status_code} - {response.text}")
                            break

                        data = response.json()
                        items = data.get('items', [])

                        if not items:
                            logger.info(f"🔍 [GITHUB SEARCH] No more items in response")
                            break

                        accumulated_repos.extend(items)
                        logger.info(f"Batch {i}, Page {page}: {len(items)} items, accumulated: {len(accumulated_repos)}")

                        # Yield accumulated repos when we reach batch_size or hit limits
                        should_yield = False
                        is_last_page = False

                        # Check if we've reached 1000 result limit
                        if len(accumulated_repos) >= 1000:
                            logger.info(f"🔍 [GITHUB SEARCH] Reached 1000 result limit")
                            should_yield = True
                            is_last_page = True

                        # Parse Link header for next page
                        link_header = response.headers.get('link', '')
                        next_url = None
                        if link_header:
                            # Parse Link header: <url>; rel="next", <url>; rel="last"
                            for link in link_header.split(','):
                                if 'rel="next"' in link:
                                    # Extract URL from <url>
                                    next_url = link.split(';')[0].strip().strip('<>')
                                    logger.debug(f"🔍 [GITHUB SEARCH] Found next URL in Link header")
                                    break

                        if not next_url:
                            logger.info(f"🔍 [GITHUB SEARCH] No next link in header, pagination complete for this pattern batch")
                            should_yield = True
                            is_last_page = True

                        # Yield batch if we have repos and either reached batch_size or end of pagination
                        if accumulated_repos and (should_yield or len(accumulated_repos) >= batch_size):
                            is_last_batch = is_last_page and is_last_pattern_batch
                            logger.info(f"🔍 [GITHUB SEARCH] Yielding {len(accumulated_repos)} repos (is_last_batch={is_last_batch})")
                            yield (accumulated_repos, is_last_batch)
                            total_repos_yielded += len(accumulated_repos)
                            accumulated_repos = []

                        if is_last_page:
                            break

                        page += 1

                    logger.info(f"Batch {i}/{len(pattern_batches)}: completed")

                except GitHubRateLimitException as e:
                    logger.warning(f"⏸️ Rate limit hit during repository search batch {i}/{len(pattern_batches)}")
                    # Save checkpoint with last extracted repo's pushed date
                    _save_rate_limit_checkpoint(
                        job_id=job_id,
                        tenant_id=tenant_id,
                        rate_limit_node_type='repositories',
                        rate_limit_reset_at=e.reset_at,
                        last_repo_pushed_date=last_repo_pushed_date
                    )
                    # Return rate limit status to caller
                    return {
                        'success': False,
                        'error': 'Rate limit exceeded during repository search',
                        'is_rate_limit': True,
                        'rate_limit_reset_at': e.reset_at,
                        'repositories_count': total_repositories
                    }

                except Exception as e:
                    logger.error(f"Batch {i}/{len(pattern_batches)} failed: {e}")
                    logger.error(f"Failed query: {full_query}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    # Continue with other batches instead of failing completely
                    continue

        logger.info(f"🔍 [GITHUB SEARCH] Total repositories yielded: {total_repos_yielded}")

    except Exception as e:
        logger.error(f"❌ Error searching GitHub repositories: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return


def _batch_search_patterns(base_query: str, patterns: list, max_length: int = 256) -> list:
    """
    Batch search patterns to stay within character limit.

    Args:
        base_query: Base query string (org, date range, etc.)
        patterns: List of search patterns to batch
        max_length: Maximum query length (default 256)

    Returns:
        List of pattern batches
    """
    batches = []
    current_batch = []

    # Account for base query + space + " OR " separators
    base_length = len(base_query) + 1  # +1 for space before patterns

    for pattern in patterns:
        # Calculate length if we add this pattern
        if current_batch:
            # Need " OR " separator
            test_length = base_length + len(" OR ".join(current_batch + [pattern]))
        else:
            # First pattern in batch
            test_length = base_length + len(pattern)

        if test_length <= max_length:
            current_batch.append(pattern)
        else:
            # Current batch is full, start new one
            if current_batch:
                batches.append(current_batch)
            current_batch = [pattern]

    # Add final batch if not empty
    if current_batch:
        batches.append(current_batch)

    return batches


async def github_extraction_worker(message: Dict[str, Any]) -> Dict[str, Any]:
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
        job_id = message.get('job_id')
        repository_id = message.get('repository_id')

        logger.info(f"🔀 [ROUTER] Extraction worker received message for repo {repository_id}")

        # ROUTER: Check if this is nested recovery from rate limit checkpoint
        if message.get('type') == 'github_nested_extraction_recovery':
            # NESTED RECOVERY: Resume from rate limit checkpoint
            logger.info(f"🔄 [ROUTER] Routing to extract_nested_recovery (PR {message.get('pr_id')})")
            result = await extract_nested_recovery(
                tenant_id=tenant_id,
                job_id=job_id,
                repository_id=repository_id,
                pr_id=message.get('pr_id'),
                pr_node_id=message.get('pr_node_id'),
                nested_nodes_status=message.get('nested_nodes_status', {}),
                last_sync_date=message.get('last_sync_date')
            )
        # ROUTER: Check if this is nested data continuation
        elif message.get('nested_type'):
            # NESTED CONTINUATION: Extract next page of nested data
            logger.info(f"🔀 [ROUTER] Routing to extract_nested_pagination (nested_type={message.get('nested_type')})")
            result = await extract_nested_pagination(
                tenant_id=tenant_id,
                job_id=job_id,
                repository_id=repository_id,
                pr_node_id=message['pr_node_id'],
                nested_type=message['nested_type'],
                nested_cursor=message['nested_cursor'],
                last_sync_date=message.get('last_sync_date'),  # Forward from message
                nested_index=message.get('nested_index', 0),  # 🔑 Forward nested type info
                total_nested_types=message.get('total_nested_types', 1),  # 🔑 Forward nested type info
                is_last_nested_type=message.get('is_last_nested_type', False),  # 🔑 Forward nested type info
                last_item=message.get('last_item', False),  # 🔑 Forward flag from message
                last_job_item=message.get('last_job_item', False)  # 🔑 Forward flag from message
            )
        else:
            # FRESH OR NEXT PR PAGE
            is_fresh = message.get('pr_cursor') is None
            logger.info(f"🔀 [ROUTER] Routing to extract_github_prs_commits_reviews_comments ({'fresh' if is_fresh else 'next'} page)")
            result = await extract_github_prs_commits_reviews_comments(
                tenant_id=tenant_id,
                job_id=job_id,
                repository_id=repository_id,
                pr_cursor=message.get('pr_cursor'),  # None for fresh, value for next
                owner=message.get('owner'),  # From message (avoids DB lookup)
                repo_name=message.get('repo_name'),  # From message (avoids DB lookup)
                first_item=message.get('first_item', False),  # 🔑 Forward from message
                last_item=message.get('last_item', False),  # Forward from message
                last_sync_date=message.get('last_sync_date')  # Forward from message
            )

        return result

    except Exception as e:
        logger.error(f"❌ Extraction worker error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {'success': False, 'error': str(e)}


async def extract_github_prs_commits_reviews_comments(
    tenant_id: int,
    job_id: int,
    repository_id: int,
    pr_cursor: Optional[str] = None,
    owner: Optional[str] = None,
    repo_name: Optional[str] = None,
    first_item: bool = False,  # 🔑 NEW: Received from message
    last_item: bool = False,
    last_sync_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract PRs with nested data (commits, reviews, comments) using GraphQL.

    This is Phase 4 / Step 2 of the GitHub job. It extracts pull requests with
    all nested data in a single GraphQL query, then queues them for transformation.

    Checkpoint Recovery:
    - Saves PR cursor to etl_jobs.checkpoint_data for recovery
    - On restart, resumes from last saved cursor
    - Tracks nested cursors for each PR with incomplete data

    Flow:
    1. Fetch PR page (fresh or next)
    2. Split PRs into individual raw_data entries (Type 1: PR+nested)
    3. Queue all PRs to transform
    4. For each PR, queue nested pagination messages if needed
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
        last_item: True if this is the last repo (from message)

    Returns:
        Dictionary with extraction result
    """
    try:
        is_fresh = (pr_cursor is None)
        logger.info(f"🚀 Starting GitHub PR extraction - {'Fresh' if is_fresh else 'Next'} page for repo {repository_id}")

        from app.core.database_router import get_read_session_context, get_write_session_context
        from app.core.config import AppConfig
        from app.etl.queue.queue_manager import QueueManager

        # If owner and repo_name not provided, fetch from database
        if not owner or not repo_name:
            with get_read_session_context() as db:
                from app.models.unified_models import Repository
                repository = db.query(Repository).filter(
                    Repository.id == repository_id,
                    Repository.tenant_id == tenant_id
                ).first()

            if not repository:
                logger.error(f"Repository {repository_id} not found")
                return {'success': False, 'error': 'Repository not found'}

            owner, repo_name = repository.full_name.split('/', 1)
        else:
            logger.info(f"✅ Using owner and repo_name from message: {owner}/{repo_name}")

        # Get integration and GitHub token
        with get_read_session_context() as db:
            from app.models.unified_models import Repository
            repository = db.query(Repository).filter(
                Repository.id == repository_id,
                Repository.tenant_id == tenant_id
            ).first()

            if repository:
                integration = db.query(Integration).filter(
                    Integration.id == repository.integration_id,
                    Integration.tenant_id == tenant_id
                ).first()
            else:
                integration = None

        if not integration or not integration.password:
            logger.error(f"Integration not found or token missing")
            return {'success': False, 'error': 'Integration not found or token missing'}

        # Decrypt the token
        key = AppConfig.load_key()
        github_token = AppConfig.decrypt_token(integration.password, key)

        # Initialize clients
        from app.etl.github_graphql_client import GitHubGraphQLClient
        github_client = GitHubGraphQLClient(github_token)
        queue_manager = QueueManager()

        # STEP 1: Fetch PR page
        logger.info(f"📥 Fetching PR page for {owner}/{repo_name} (cursor: {pr_cursor or 'None'})")
        try:
            pr_page = await github_client.get_pull_requests_with_details(
                owner, repo_name, pr_cursor
            )
        except GitHubRateLimitException as e:
            logger.warning(f"⏸️ Rate limit hit during PR extraction: {e}")
            _save_rate_limit_checkpoint(
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
                first_item=False,
                last_item=True,
                last_job_item=True  # 🔑 Signal job completion
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
            return {'success': True, 'prs_processed': 0}

        logger.info(f"📦 Processing {len(prs)} PRs from page")

        # STEP 1.5: Filter PRs by last_sync_date for incremental sync
        # PRs are ordered by UPDATED_AT DESC, so we can stop early when reaching old PRs
        filtered_prs = []
        early_termination = False

        # 🔑 If no last_sync_date provided, use 2-year default (same as repository extraction)
        if not last_sync_date:
            from datetime import datetime, timedelta
            two_years_ago = datetime.now() - timedelta(days=730)
            last_sync_date = two_years_ago.strftime('%Y-%m-%d')
            logger.info(f"📅 No last_sync_date provided, using 2-year default: {last_sync_date}")

        logger.info(f"🔍 Filtering PRs by last_sync_date: {last_sync_date}")
        from datetime import datetime, timezone

        # Parse last_sync_date (format: YYYY-MM-DD or YYYY-MM-DD HH:MM)
        try:
            if ' ' in last_sync_date:
                # Has time component
                last_sync_dt = datetime.fromisoformat(last_sync_date.replace(' ', 'T'))
            else:
                # Date only, set to start of day (UTC timezone to match PR timestamps)
                last_sync_dt = datetime.fromisoformat(last_sync_date + 'T00:00:00').replace(tzinfo=timezone.utc)
        except ValueError:
            logger.warning(f"Could not parse last_sync_date: {last_sync_date}, processing all PRs")
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
                        logger.info(f"🛑 PR {pr.get('number')} updated at {pr_updated_at_str} is older than last_sync_date {last_sync_date}, stopping pagination")
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
                    'repository_id': repository.id,  # 🔑 Include repository_id to avoid DB lookup in transform
                    'pr_data': pr  # 🔑 pr_data already contains commits, reviews, comments, reviewThreads
                }
                raw_data_id = _store_raw_extraction_data(
                    db, tenant_id, repository.integration_id,
                    'github_prs',  # 🔑 Renamed from github_prs_commits_reviews_comments
                    raw_data, repository.external_id  # 🔑 Use repository external_id, not PR id
                )
                raw_data_ids.append(raw_data_id)

        logger.info(f"💾 Stored {len(raw_data_ids)} raw data entries")

        # Get page info early to determine if there are more pages
        page_info = pr_page['data']['repository']['pullRequests']['pageInfo']
        has_next_page = page_info['hasNextPage']

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
        # 🔑 last_job_item=true ONLY on last PR when:
        #    - No more PR pages (not has_next_page)
        #    - AND no nested pagination needed (all nested data fits in first page)
        for i, raw_data_id in enumerate(raw_data_ids):
            is_first = (i == 0 and first_item)  # 🔑 Use received first_item flag, not is_fresh
            is_last = (i == len(raw_data_ids) - 1 and not has_next_page)  # Last only if no more PR pages

            # 🔑 Only set last_job_item=true if this is the last PR AND no nested pagination needed
            # If nested pagination exists, nested workers will handle job completion
            is_last_job_item = (is_last and not has_nested_pagination)

            queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration.id,
                raw_data_id=raw_data_id,
                data_type='github_prs_commits_reviews_comments',
                job_id=job_id,
                provider='github',
                first_item=is_first,
                last_item=is_last,
                last_job_item=is_last_job_item  # 🔑 True only when no nested pagination
            )

        logger.info(f"📤 Queued {len(raw_data_ids)} PRs to transform")

        # STEP 5: Loop through each PR and queue nested pagination if needed
        # 🔑 Build list of nested types that need pagination for this PR
        for pr in filtered_prs:
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
            # 🔑 RELAY FLAGS: Pass last_item=true, last_job_item=true to LAST nested type
            # This signals "you will be the last nested type to process" through the nested chain
            total_nested_types = len(nested_types_needing_pagination)
            for nested_index, (nested_type, nested_cursor) in enumerate(nested_types_needing_pagination):
                is_last_nested_type = (nested_index == total_nested_types - 1)

                queue_manager.publish_extraction_job(
                    tenant_id=tenant_id,
                    integration_id=repository.integration_id,
                    extraction_type='github_prs_commits_reviews_comments',  # Route to github_extraction_worker
                    extraction_data={
                        'repository_id': repository_id,
                        'pr_node_id': pr_node_id,
                        'nested_type': nested_type,
                        'nested_cursor': nested_cursor,
                        'nested_index': nested_index,                    # 🔑 Index of this nested type
                        'total_nested_types': total_nested_types,        # 🔑 Total nested types for this PR
                        'is_last_nested_type': is_last_nested_type       # 🔑 Is this the last nested type?
                    },
                    job_id=job_id,
                    provider='github',
                    last_sync_date=last_sync_date,
                    first_item=False,
                    last_item=is_last_nested_type,      # 🔑 RELAY: True only on last nested type
                    last_job_item=is_last_nested_type   # 🔑 RELAY: True only on last nested type
                )
                logger.info(f"📤 Queued {nested_type} pagination (index {nested_index}/{total_nested_types}, is_last={is_last_nested_type}, last_item={is_last_nested_type}, last_job_item={is_last_nested_type})")

        logger.info(f"📤 Queued nested pagination messages for PRs with incomplete data")

        # STEP 5: Queue next PR page if exists (and we didn't hit early termination)
        # 🔑 RELAY FLAGS: Pass last_item=true, last_job_item=true to next page
        # This signals "you will be the last page to fetch" through the PR page chain
        next_pr_cursor = None
        if has_next_page and not early_termination:
            next_pr_cursor = page_info['endCursor']
            queue_manager.publish_extraction_job(
                tenant_id=tenant_id,
                integration_id=repository.integration_id,
                extraction_type='github_prs_commits_reviews_comments',  # Same as main extraction type
                extraction_data={
                    'repository_id': repository_id,
                    'pr_cursor': next_pr_cursor,
                    'pr_node_id': None,  # Fresh request for next page
                    'owner': owner,  # Include owner/repo_name to avoid DB lookup
                    'repo_name': repo_name
                },
                job_id=job_id,
                provider='github',
                last_sync_date=last_sync_date,
                first_item=False,
                last_item=True,            # 🔑 RELAY: Pass true to next page
                last_job_item=True         # 🔑 RELAY: Pass true to next page
            )
            logger.info(f"📤 Queued next PR page to extraction queue with last_item=true, last_job_item=true")
        elif early_termination:
            logger.info(f"🛑 Early termination due to old PRs, not queuing next page")

        # STEP 6: Save checkpoint for recovery
        _save_checkpoint(
            job_id, tenant_id,
            last_pr_cursor=next_pr_cursor,
            prs_processed=len(filtered_prs)
        )

        # STEP 7: Send completion message if this is the last PR page (no more pages or early termination)
        # 🔑 Completion message pattern (same as Jira dev_status):
        # - raw_data_id=None signals completion
        # - last_item=True indicates this is the last page
        # - last_job_item=True indicates job should complete after this
        if not has_next_page or early_termination:
            logger.info(f"🎯 [COMPLETION] Sending completion message for PR extraction (last page, no more data)")
            queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration.id,
                raw_data_id=None,  # 🔑 Completion message marker
                data_type='github_prs_commits_reviews_comments',
                job_id=job_id,
                provider='github',
                first_item=False,
                last_item=True,
                last_job_item=True  # 🔑 Signal job completion
            )
            logger.info(f"✅ Completion message queued to transform")

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


async def extract_nested_pagination(
    tenant_id: int,
    job_id: int,
    repository_id: int,
    pr_node_id: str,
    nested_type: str,
    nested_cursor: str,
    last_sync_date: Optional[str] = None,
    nested_index: int = 0,
    total_nested_types: int = 1,
    is_last_nested_type: bool = False,
    last_item: bool = False,  # 🔑 NEW: Received from message
    last_job_item: bool = False  # 🔑 NEW: Received from message
) -> Dict[str, Any]:
    """
    Extract next page of nested data (commits, reviews, comments) for a specific PR.

    This handles pagination for nested data within a PR. When a PR has more commits,
    reviews, or comments than fit in the first page, this function fetches the next page.

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
        nested_index: Index of this nested type (0-based)
        total_nested_types: Total number of nested types for this PR
        is_last_nested_type: Whether this is the last nested type to process
        last_item: True if this is the last nested type (from message)
        last_job_item: True if this is the last nested type (from message)

    Returns:
        Dictionary with extraction result
    """
    try:
        logger.info(f"🚀 Extracting nested {nested_type} for PR {pr_node_id}")

        from app.core.database_router import get_read_session_context, get_write_session_context
        from app.core.config import AppConfig
        from app.etl.queue.queue_manager import QueueManager

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

        # Decrypt the token
        key = AppConfig.load_key()
        github_token = AppConfig.decrypt_token(integration.password, key)

        # Initialize clients
        from app.etl.github_graphql_client import GitHubGraphQLClient
        github_client = GitHubGraphQLClient(github_token)
        queue_manager = QueueManager()

        # STEP 1: Fetch nested page based on type
        logger.info(f"📥 Fetching {nested_type} page for PR {pr_node_id}")

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
            logger.warning(f"⏸️ Rate limit hit during {nested_type} extraction: {e}")
            _save_rate_limit_checkpoint(
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
                first_item=False,
                last_item=True,
                last_job_item=True  # 🔑 Signal job completion
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
        # 🔑 No nested_data_only flag - message type indicates this is nested data
        raw_data = {
            'pr_id': pr_node_id,
            'repository_id': repository.id,  # 🔑 Include repository_id to avoid DB lookup in transform
            'nested_type': nested_type,
            'data': nested_data['nodes'],
            'cursor': nested_data['pageInfo']['endCursor'] if has_more else None,
            'has_more': has_more
        }

        with get_write_session_context() as db:
            raw_data_id = _store_raw_extraction_data(
                db, tenant_id, repository.integration_id,
                'github_prs_nested',  # 🔑 Renamed from github_prs_commits_reviews_comments
                raw_data, repository.external_id  # 🔑 Use repository external_id, not PR id
            )

        logger.info(f"💾 Stored nested {nested_type} data (has_more={has_more})")

        # STEP 3: Determine if this is the last item to queue
        # 🔑 last_item=true ONLY if:
        #    - This is the last nested type (is_last_nested_type=true)
        #    - AND there are no more pages for this nested type (not has_more)
        #    - AND we received last_item=true from the message (relay forward)
        is_last_item = (is_last_nested_type and not has_more and last_item)

        # 🔑 last_job_item=true ONLY if:
        #    - This is the last nested type (is_last_nested_type=true)
        #    - AND there are no more pages for this nested type (not has_more)
        #    - AND we received last_job_item=true from the message (relay forward)
        is_last_job_item = (is_last_nested_type and not has_more and last_job_item)

        # STEP 4: Queue to transform
        queue_manager.publish_transform_job(
            tenant_id=tenant_id,
            integration_id=integration.id,
            raw_data_id=raw_data_id,
            data_type='github_prs_commits_reviews_comments',
            job_id=job_id,
            provider='github',
            first_item=False,
            last_item=is_last_item,  # 🔑 True only on last page of last nested type
            last_job_item=is_last_job_item  # 🔑 True only on last page of last nested type
        )

        logger.info(f"📤 Queued {nested_type} page to transform (last_item={is_last_item})")

        # STEP 5: If more pages exist, queue next nested page to extraction
        # 🔑 RELAY FLAGS: Pass last_item and last_job_item to next nested page
        if has_more:
            queue_manager.publish_extraction_job(
                tenant_id=tenant_id,
                integration_id=integration.id,
                extraction_type='github_prs_commits_reviews_comments',  # Route to github_extraction_worker
                extraction_data={
                    'repository_id': repository_id,
                    'pr_node_id': pr_node_id,
                    'nested_type': nested_type,
                    'nested_cursor': nested_data['pageInfo']['endCursor'],
                    'nested_index': nested_index,                    # 🔑 Forward nested type info
                    'total_nested_types': total_nested_types,        # 🔑 Forward nested type info
                    'is_last_nested_type': is_last_nested_type       # 🔑 Forward nested type info
                },
                job_id=job_id,
                provider='github',
                last_sync_date=last_sync_date,
                first_item=False,
                last_item=last_item,            # 🔑 RELAY: Pass through to next page
                last_job_item=last_job_item     # 🔑 RELAY: Pass through to next page
            )
            logger.info(f"📤 Queued next {nested_type} page to extraction queue with last_item={last_item}, last_job_item={last_job_item}")
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


async def extract_nested_recovery(
    tenant_id: int,
    job_id: int,
    repository_id: int,
    pr_id: str,
    pr_node_id: str,
    nested_nodes_status: Dict[str, Any],
    last_sync_date: Optional[str] = None
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
        last_sync_date: Last sync date for incremental extraction

    Returns:
        Dictionary with extraction result
    """
    try:
        logger.info(f"🔄 Resuming nested extraction for PR {pr_id} from checkpoint")

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
                logger.info(f"📥 Continuing {nested_type} pagination from cursor")
                cursor = node_status.get('cursor')

                result = await extract_nested_pagination(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    repository_id=repository_id,
                    pr_node_id=pr_node_id,
                    nested_type=nested_type,
                    nested_cursor=cursor,
                    last_sync_date=last_sync_date
                )

                if not result.get('success'):
                    if result.get('is_rate_limit'):
                        # Another rate limit hit, return with is_rate_limit flag
                        return result
                    logger.warning(f"Failed to continue {nested_type} pagination: {result.get('error')}")

            elif not node_status.get('fetched'):
                # Fetch from scratch
                logger.info(f"📥 Fetching {nested_type} from scratch")

                result = await extract_nested_pagination(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    repository_id=repository_id,
                    pr_node_id=pr_node_id,
                    nested_type=nested_type,
                    nested_cursor=None,  # Start from beginning
                    last_sync_date=last_sync_date
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


def _store_raw_extraction_data(
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


def _save_checkpoint(
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


def _save_rate_limit_checkpoint(
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


def _set_job_start_time(job_id: int, tenant_id: int):
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

