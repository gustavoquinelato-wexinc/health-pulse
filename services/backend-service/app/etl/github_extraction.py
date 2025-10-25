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
        with get_read_session_context() as db:
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

        repositories_generator = _search_github_repositories_paginated(
            token=integration_data['github_token'],
            org=integration_data['org'],
            start_date=integration_data['start_date'],
            end_date=integration_data['end_date'],
            name_filters=integration_data['name_filters'],
            additional_repo_names=list(integration_data['non_health_repo_names']) if integration_data['non_health_repo_names'] else None
        )

        # Process each batch of repositories
        for batch_repos, is_last_batch in repositories_generator:
            logger.info(f"📊 Processing batch of {len(batch_repos)} repositories (is_last_batch={is_last_batch})")

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
                        'is_first_batch': is_first_batch,
                        'is_last_batch': is_last_batch
                    }
                }
            )

            if not raw_data_id:
                logger.error("Failed to store raw repository batch data")
                return {'success': False, 'error': 'Failed to store raw repository batch data'}

            # Queue for transform with proper first_item/last_item flags
            logger.info(f"Queuing batch of {len(batch_repos)} repositories for transform (raw_data_id={raw_data_id})")
            success = queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                raw_data_id=raw_data_id,
                data_type='github_repositories',
                job_id=job_id,
                provider='github',
                last_sync_date=integration_data['start_date'],
                first_item=is_first_batch,      # 🔑 True only on first batch
                last_item=is_last_batch,        # 🔑 True only on last batch
                last_job_item=is_last_batch     # 🔑 Job completion on last batch
            )

            if not success:
                logger.error(f"Failed to queue repository batch for transform")

            total_repositories += len(batch_repos)
            is_first_batch = False

        logger.info(f"✅ [GITHUB] Repository extraction completed: {total_repositories} repositories found and queued for transform")

        return {
            'success': True,
            'repositories_count': total_repositories,
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

