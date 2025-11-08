"""
GitHub REST API Client for Backend Service ETL
Handles REST API requests to GitHub for repository extraction.
"""

import httpx
import urllib.parse
import requests
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class GitHubRateLimitException(Exception):
    """Custom exception for GitHub API rate limit exceeded."""
    def __init__(self, message: str, reset_at: Optional[str] = None):
        super().__init__(message)
        self.reset_at = reset_at


class GitHubRestClient:
    """Client for GitHub REST API interactions."""
    
    def __init__(self, token: str):
        """
        Initialize GitHub REST API client.

        Args:
            token: GitHub personal access token
        """
        self.token = token
        self.base_url = "https://api.github.com"
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = None

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'ETL-Service/1.0'
        })

    def _update_rate_limit_info(self, response: requests.Response):
        """Update rate limit information from response headers."""
        if 'X-RateLimit-Remaining' in response.headers:
            self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
            self.rate_limit_reset = response.headers.get('X-RateLimit-Reset')
            logger.debug(f"REST API rate limit updated: {self.rate_limit_remaining} requests remaining")

    def is_rate_limited(self) -> bool:
        """Check if we have hit the rate limit."""
        return self.rate_limit_remaining <= 0

    def _make_request(self, endpoint: str, params: Dict[str, Any] = None, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Make a REST API request with retry logic.

        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters
            max_retries: Maximum number of retries

        Returns:
            Response data or None if failed
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(max_retries):
            try:
                if self.is_rate_limited():
                    logger.warning(f"REST API rate limit reached: {self.rate_limit_remaining} requests remaining")
                    raise GitHubRateLimitException(
                        f"GitHub REST API rate limit exceeded",
                        reset_at=self.rate_limit_reset
                    )

                logger.debug(f"Making GitHub REST request (attempt {attempt + 1}): {endpoint}")
                response = self.session.get(url, params=params, timeout=30)

                # Update rate limit info from response
                self._update_rate_limit_info(response)

                # Check for rate limit errors
                if response.status_code == 403 and 'rate limit' in response.text.lower():
                    logger.warning("REST API rate limit exceeded - stopping gracefully")
                    raise GitHubRateLimitException(
                        f"GitHub REST API rate limit exceeded",
                        reset_at=response.headers.get('X-RateLimit-Reset')
                    )

                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                is_server_error = (
                    hasattr(e, 'response') and e.response is not None and
                    e.response.status_code in [502, 503, 504]
                )

                if is_server_error:
                    logger.warning(f"GitHub server error (attempt {attempt + 1}/{max_retries}): {e}")
                else:
                    logger.warning(f"REST request failed (attempt {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    backoff_time = (2 ** attempt) * (3 if is_server_error else 1)
                    logger.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                else:
                    logger.error(f"Failed to make REST request after {max_retries} attempts")
                    return None
        
        return None

    def get_repositories(self, org: str = None, user: str = None, last_sync_date: str = None) -> List[Dict[str, Any]]:
        """
        Get repositories for an organization or user with pagination.

        Args:
            org: Organization name
            user: User name
            last_sync_date: Last sync date for filtering (YYYY-MM-DD format)

        Returns:
            List of repository data
        """
        if org:
            endpoint = f"orgs/{org}/repos"
        elif user:
            endpoint = f"users/{user}/repos"
        else:
            endpoint = "user/repos"  # Current authenticated user

        params = {
            'type': 'all',
            'sort': 'updated',
            'direction': 'desc',
            'per_page': 100
        }

        logger.info(f"Fetching repositories from {endpoint}")
        if last_sync_date:
            logger.info(f"Last sync date: {last_sync_date}")

        all_repos = []
        page = 1
        
        while True:
            params['page'] = page
            logger.info(f"📄 Fetching repositories page {page}")
            
            response = self._make_request(endpoint, params)
            
            if not response:
                logger.error(f"Failed to fetch repositories page {page}")
                break
            
            if not isinstance(response, list):
                logger.error(f"Unexpected response format: {type(response)}")
                break
            
            if len(response) == 0:
                logger.info(f"No more repositories on page {page}")
                break
            
            logger.info(f"📦 Fetched {len(response)} repositories on page {page}")
            all_repos.extend(response)
            
            # If we got fewer items than per_page, we've reached the end
            if len(response) < params['per_page']:
                logger.info(f"Reached last page (got {len(response)} < {params['per_page']})")
                break
            
            page += 1
            
            # Safety limit to prevent infinite loops
            if page > 100:
                logger.warning(f"⚠️ Reached safety limit of 100 pages")
                break
        
        logger.info(f"📊 Total repositories fetched: {len(all_repos)}")
        return all_repos

    def search_repositories(self,
        org: str,
        start_date: str,
        end_date: str,
        name_filter: Optional[str] = None,
        name_filters: Optional[List[str]] = None,
        additional_repo_names: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search GitHub repositories using the GitHub Search API with pagination.

        Accumulates ALL repositories from all pages and search patterns, then returns
        a complete list. This allows the caller to determine which item is last.

        Uses combined search patterns with OR operators to find repositories matching:
        1. The name_filters patterns (e.g., ['health-', 'bp-'])
        2. Specific repository names from Jira PR links

        Handles the 256 character limit by batching search patterns.

        Args:
            org: Organization name (e.g., 'wexinc')
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            name_filter: (Deprecated) Single pattern filter for backward compatibility
            name_filters: Array of pattern filters (e.g., ['health-', 'bp-'])
            additional_repo_names: List of specific repo names to include

        Returns:
            List of all repositories found across all pages and search patterns
        """
        # Handle both old string format and new array format for backward compatibility
        filters_to_use = name_filters if name_filters else (
            [name_filter] if name_filter else []
        )

        logger.info(f"🔍 [GITHUB SEARCH] Starting repository search with org={org}, filters={filters_to_use}")

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

            if not search_patterns:
                logger.warning("🔍 [GITHUB SEARCH] No search patterns provided for GitHub repository search")
                return []

            logger.info(f"🔍 [GITHUB SEARCH] Total search patterns: {len(search_patterns)}")

            # Batch patterns to stay within 256 character limit
            pattern_batches = self._batch_search_patterns(base_query, search_patterns, max_length=256)

            logger.info(f"🔍 [GITHUB SEARCH] Executing {len(pattern_batches)} search requests to stay within character limit")

            # Accumulate ALL repositories from all pages and patterns
            all_repositories = []

            # Execute each batch
            logger.info(f"🔍 [GITHUB SEARCH] Creating HTTP client...")
            with httpx.Client() as client:
                logger.info(f"🔍 [GITHUB SEARCH] HTTP client created successfully")
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
                        "Authorization": f"token {self.token}",
                        "Accept": "application/vnd.github.v3+json",
                        "User-Agent": "ETL-Service/1.0"
                    }

                    logger.info(f"🔍 [GITHUB SEARCH] Making HTTP request to {endpoint}?q={urllib.parse.quote(full_query)}")
                    try:
                        # Paginate through search results using Link header
                        # Accumulate all repos from all pages
                        accumulated_repos = []
                        next_url = None
                        page = 1

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

                            # Check if we've reached 1000 result limit (GitHub Search API limit)
                            is_last_page = False
                            if len(accumulated_repos) >= 1000:
                                logger.info(f"🔍 [GITHUB SEARCH] Reached 1000 result limit")
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
                                is_last_page = True

                            # Accumulate all repos (don't yield yet)
                            if is_last_page:
                                logger.info(f"🔍 [GITHUB SEARCH] End of pagination for pattern batch {i}/{len(pattern_batches)}: accumulated {len(accumulated_repos)} repos")
                                all_repositories.extend(accumulated_repos)
                                accumulated_repos = []
                                break

                            page += 1

                        logger.info(f"Batch {i}/{len(pattern_batches)}: completed")

                    except GitHubRateLimitException:
                        # Re-raise rate limit exceptions to be handled by caller
                        raise

                    except Exception as e:
                        logger.error(f"Batch {i}/{len(pattern_batches)} failed: {e}")
                        logger.error(f"Failed query: {full_query}")
                        import traceback
                        logger.error(f"Full traceback: {traceback.format_exc()}")
                        # Continue with other batches instead of failing completely
                        continue

            logger.info(f"🔍 [GITHUB SEARCH] Total repositories found: {len(all_repositories)}")
            return all_repositories

        except GitHubRateLimitException:
            # Re-raise rate limit exceptions
            raise
        except Exception as e:
            logger.error(f"❌ Error searching GitHub repositories: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return []

    def _batch_search_patterns(self, base_query: str, patterns: List[str], max_length: int = 256) -> List[List[str]]:
        """
        Batch search patterns to stay within character limit.

        GitHub Search API has a 256 character limit for the query string.
        This method batches patterns so each batch stays under the limit.

        Args:
            base_query: Base query string (e.g., "org:wexinc pushed:2024-01-01..2024-12-31")
            patterns: List of search patterns (e.g., ["health- in:name", "bp- in:name"])
            max_length: Maximum query length (default: 256)

        Returns:
            List of pattern batches, where each batch is a list of patterns
        """
        batches = []
        current_batch = []

        # Calculate base length including parentheses and OR operators
        # Format: "base_query (pattern1 OR pattern2 OR pattern3)"
        base_length = len(base_query) + 3  # +3 for " ()"

        for pattern in patterns:
            # Calculate length if we add this pattern
            if current_batch:
                # Need to add " OR " before this pattern
                test_length = base_length + len(" OR ".join(current_batch + [pattern]))
            else:
                # First pattern in batch
                test_length = base_length + len(pattern)

            if test_length > max_length and current_batch:
                # Adding this pattern would exceed limit, start new batch
                batches.append(current_batch)
                current_batch = [pattern]
            else:
                # Pattern fits in current batch
                current_batch.append(pattern)

        # Add final batch if not empty
        if current_batch:
            batches.append(current_batch)

        logger.info(f"Batched {len(patterns)} patterns into {len(batches)} batches")
        return batches

