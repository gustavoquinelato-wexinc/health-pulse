"""
GitHub API Client for ETL Service.

This module provides a client for interacting with the GitHub API to extract
repository, pull request, and development data.
"""

import requests
import time
import dateutil.parser
from datetime import datetime
from typing import Dict, List, Any, Optional
from app.core.logging_config import get_logger
# REMOVED: Old rate limit exceptions - replaced by new orchestration system

logger = get_logger(__name__)


class GitHubClient:
    """Client for GitHub API interactions."""
    
    def __init__(self, token: str, base_url: str = "https://api.github.com"):
        """
        Initialize GitHub client.

        Args:
            token: GitHub personal access token
            base_url: GitHub API base URL
        """
        self.token = token
        self.base_url = base_url.rstrip('/')
        self.rate_limit_remaining = 5000  # Default GitHub limit
        self.rate_limit_reset = None

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'ETL-Service/1.0'
        })

    def _update_rate_limit_info(self, response: requests.Response):
        """Update rate limit information from response headers."""
        self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', self.rate_limit_remaining))
        self.rate_limit_reset = int(response.headers.get('X-RateLimit-Reset', 0))

        logger.debug(f"Rate limit updated: {self.rate_limit_remaining} requests remaining")

    def is_rate_limited(self) -> bool:
        """Check if we have hit the rate limit (0 remaining requests)."""
        return self.rate_limit_remaining <= 0

    def check_rate_limit_before_request(self):
        """Check rate limit before making a request and log info if rate limited."""
        if self.is_rate_limited():
            logger.warning(f"GitHub API rate limit reached: {self.rate_limit_remaining} requests remaining")
            logger.warning("Consider implementing checkpoint-based recovery in the calling function")

    def _make_request(self, endpoint: str, params: Dict[str, Any] = None, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Make a request to the GitHub API with retry logic.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters
            max_retries: Maximum number of retries
            
        Returns:
            JSON response data or None if failed
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(max_retries):
            try:
                # Check rate limit before making request
                if self.is_rate_limited():
                    logger.warning(f"GitHub API rate limit reached: {self.rate_limit_remaining} requests remaining")
                    raise Exception("GitHub API rate limit exceeded")

                # Get configurable timeout
                from app.core.settings_manager import get_github_request_timeout
                timeout = get_github_request_timeout()

                logger.debug(f"Making GitHub API request: {url} with {timeout}s timeout")
                response = self.session.get(url, params=params, timeout=timeout)

                # Update rate limit info from response
                self._update_rate_limit_info(response)

                # Handle rate limiting
                if response.status_code == 403 and 'rate limit' in response.text.lower():
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                    current_time = int(time.time())
                    sleep_time = max(reset_time - current_time + 1, 60)

                    logger.error(f"Rate limit exceeded. Would need to sleep for {sleep_time} seconds.")
                    logger.error("Rate limit handling should be implemented at the job level with checkpoints.")
                    raise Exception(f"GitHub API rate limit exceeded. Reset time: {reset_time}")

                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to make request after {max_retries} attempts")
                    return None
        
        return None
    
    def _paginate_request(self, endpoint: str, params: Dict[str, Any] = None, per_page: int = 100) -> List[Dict[str, Any]]:
        """
        Make paginated requests to GitHub API using Link headers.

        Args:
            endpoint: API endpoint
            params: Query parameters
            per_page: Items per page

        Returns:
            List of all items from all pages
        """
        all_items = []
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        if params is None:
            params = {}

        params['per_page'] = per_page
        page = 1

        while url:
            try:
                # Check rate limit before making request
                self.check_rate_limit_before_request()

                # Get configurable timeout
                from app.core.settings_manager import get_github_request_timeout
                timeout = get_github_request_timeout()

                logger.debug(f"Making GitHub API request: {url} with {timeout}s timeout")
                response = self.session.get(url, params=params, timeout=timeout)

                # Update rate limit info from response
                self._update_rate_limit_info(response)

                # Handle rate limiting
                if response.status_code == 403 and 'rate limit' in response.text.lower():
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                    logger.error(f"Rate limit exceeded during pagination. Reset time: {reset_time}")
                    raise Exception(f"GitHub API rate limit exceeded during pagination. Reset time: {reset_time}")

                response.raise_for_status()
                response_data = response.json()

                # Handle both list responses and object responses with items
                if isinstance(response_data, list):
                    items = response_data
                else:
                    items = response_data.get('items', [])

                if not items:
                    break

                all_items.extend(items)
                logger.debug(f"Fetched page {page} with {len(items)} items")

                # Check for next page using Link header
                link_header = response.headers.get('Link', '')
                next_url = None

                if link_header:
                    # Parse Link header to find rel="next"
                    links = link_header.split(',')
                    for link in links:
                        if 'rel="next"' in link:
                            # Extract URL from <URL>; rel="next"
                            next_url = link.split(';')[0].strip().strip('<>')
                            break

                url = next_url
                params = {}  # Clear params for subsequent requests as they're in the URL
                page += 1

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                break

        logger.info(f"Total items fetched: {len(all_items)}")
        return all_items

    def _paginate_request_incremental(self, endpoint: str, params: Dict[str, Any], last_sync_at=None) -> List[Dict[str, Any]]:
        """
        Make paginated requests with incremental sync support.
        Stops fetching when items are older than last_sync_at.

        Args:
            endpoint: API endpoint
            params: Query parameters
            last_sync_at: Last sync timestamp (datetime object)

        Returns:
            List of items
        """
        from datetime import datetime
        import dateutil.parser

        all_items = []
        page = 1

        while True:
            current_params = params.copy()
            current_params['page'] = page

            logger.debug(f"Fetching page {page} from {endpoint}")
            response = self._make_request(endpoint, params=current_params)

            if not response or not isinstance(response, list):
                break

            items = response
            if not items:
                break

            # Check if we should stop based on last_sync_at
            if last_sync_at:
                should_continue = False
                for item in items:
                    # Check updated_at field
                    updated_at_str = item.get('updated_at')
                    if updated_at_str:
                        try:
                            updated_at = dateutil.parser.parse(updated_at_str)
                            # Remove timezone info for comparison if last_sync_at is naive
                            if last_sync_at.tzinfo is None and updated_at.tzinfo is not None:
                                updated_at = updated_at.replace(tzinfo=None)
                            elif last_sync_at.tzinfo is not None and updated_at.tzinfo is None:
                                # This shouldn't happen with GitHub API, but handle it
                                updated_at = updated_at.replace(tzinfo=last_sync_at.tzinfo)

                            if updated_at > last_sync_at:
                                all_items.append(item)
                                should_continue = True
                            else:
                                # Item is older than last sync, we can stop
                                logger.info(f"Found item older than last sync ({updated_at} <= {last_sync_at}), stopping pagination")
                                break
                        except Exception as e:
                            logger.warning(f"Error parsing updated_at '{updated_at_str}': {e}")
                            all_items.append(item)  # Include item if we can't parse date
                            should_continue = True
                    else:
                        # No updated_at field, include the item
                        all_items.append(item)
                        should_continue = True

                if not should_continue:
                    break
            else:
                # No incremental sync, add all items
                all_items.extend(items)

            # Check if there are more pages
            if len(items) < params.get('per_page', 30):
                break

            page += 1

            # Safety check to prevent infinite loops
            if page > 1000:
                logger.warning(f"Reached maximum page limit (1000) for {endpoint}")
                break

        logger.info(f"Total items fetched with incremental sync: {len(all_items)}")
        return all_items
    
    def get_repositories(self, org: str = None, user: str = None, last_sync_at=None) -> List[Dict[str, Any]]:
        """
        Get repositories for an organization or user with incremental sync support.

        Args:
            org: Organization name
            user: User name
            last_sync_at: Last sync timestamp for incremental sync (datetime object)

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

        logger.info(f"Fetching repositories from {endpoint} with incremental sync")
        if last_sync_at:
            logger.info(f"Last sync at: {last_sync_at}")

        return self._paginate_request_incremental(endpoint, params, last_sync_at)
    
    def get_pull_requests(self, owner: str, repo: str, state: str = 'all', last_sync_at=None) -> List[Dict[str, Any]]:
        """
        Get pull requests for a repository with incremental sync support.

        Args:
            owner: Repository owner
            repo: Repository name
            state: PR state ('open', 'closed', 'all')
            last_sync_at: Last sync timestamp for incremental sync (datetime object)

        Returns:
            List of pull request data
        """
        endpoint = f"repos/{owner}/{repo}/pulls"
        params = {
            'state': state,
            'sort': 'updated',
            'direction': 'desc',
            'per_page': 100
        }

        logger.info(f"Fetching pull requests for {owner}/{repo} with incremental sync")
        if last_sync_at:
            logger.info(f"Last sync at: {last_sync_at}")

        return self._paginate_request_incremental(endpoint, params, last_sync_at)
    
    def get_pull_request_details(self, owner: str, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            Detailed pull request data
        """
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}"
        logger.debug(f"Fetching PR details for {owner}/{repo}#{pr_number}")
        return self._make_request(endpoint)
    
    def get_pull_request_reviews(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Get reviews for a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of review data
        """
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        logger.debug(f"Fetching PR reviews for {owner}/{repo}#{pr_number}")
        result = self._paginate_request(endpoint)
        logger.info(f"PR #{pr_number} reviews: Total items fetched: {len(result)}")
        return result
    
    def get_pull_request_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Get commits for a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of commit data
        """
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}/commits"
        logger.debug(f"Fetching PR commits for {owner}/{repo}#{pr_number}")
        result = self._paginate_request(endpoint)
        logger.info(f"PR #{pr_number} commits: Total items fetched: {len(result)}")
        return result

    def search_repositories_combined(self, org: str, start_date: str, end_date: str,
                                   filter: str = None, additional_repo_names: List[str] = None) -> List[Dict[str, Any]]:
        """
        Search repositories using GitHub Search API with combined patterns.
        Uses OR operators to combine health- filter with specific repo names.
        Handles 256 character limit by batching requests.

        Args:
            org: Organization name (e.g., 'wexinc')
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            filter: Pattern filter (e.g., 'health-')
            additional_repo_names: List of specific repo names to include

        Returns:
            List of repository data from all search requests
        """
        all_repos = []

        # Base query parts that are always included
        base_query_parts = [f"org:{org}", f"pushed:{start_date}..{end_date}"]
        base_query = " ".join(base_query_parts)

        # Calculate base query length for character limit calculations
        base_length = len(base_query)

        # Start with health- filter if provided
        search_patterns = []
        if filter:
            # Handle trailing hyphens in filter - GitHub search doesn't like them
            clean_filter = filter.rstrip('-') if filter.endswith('-') else filter
            if clean_filter:  # Only add if there's something left after cleaning
                search_patterns.append(f"{clean_filter} in:name")

        # Add specific repo names (extract just the repo name part after '/')
        if additional_repo_names:
            for full_name in additional_repo_names:
                if '/' in full_name:
                    repo_name = full_name.split('/', 1)[1]  # Get part after '/'
                    search_patterns.append(f"{repo_name} in:name")
                else:
                    search_patterns.append(f"{full_name} in:name")

        if not search_patterns:
            logger.warning("No search patterns provided")
            return []

        # Batch patterns to stay within 256 character limit
        pattern_batches = self._batch_search_patterns(base_query, search_patterns, max_length=256)

        logger.info(f"Executing {len(pattern_batches)} search requests to stay within character limit")

        # Execute each batch
        for i, batch_patterns in enumerate(pattern_batches, 1):
            # Combine patterns with OR
            combined_patterns = " OR ".join(batch_patterns)
            full_query = f"{base_query} {combined_patterns}"

            endpoint = "search/repositories"
            params = {
                "q": full_query,
                "sort": "updated",
                "order": "asc",
                "per_page": 100
            }

            # Log each batch query and full URL so you can see all the searches being performed
            logger.info(f"Batch {i}/{len(pattern_batches)} Query: {full_query}")

            # Create the URL that requests will actually use (with proper encoding)
            import urllib.parse
            query_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
            actual_url = f"{self.base_url}/{endpoint}?{query_params}"
            logger.info(f"Full Search URL: {actual_url}")

            batch_results = self._paginate_search_request(endpoint, params)
            all_repos.extend(batch_results)

            logger.info(f"Batch {i}/{len(pattern_batches)}: {len(batch_results)} repositories")

        # Remove duplicates (same repo might match multiple patterns)
        unique_repos = {}
        for repo in all_repos:
            repo_id = repo.get('id')
            if repo_id and repo_id not in unique_repos:
                unique_repos[repo_id] = repo
            else:
                logger.info(f"Non-unique repo: {repo.get("name","")}")

        final_repos = list(unique_repos.values())
        logger.info(f"Total unique repositories found: {len(final_repos)}")

        return final_repos

    def _batch_search_patterns(self, base_query: str, patterns: List[str], max_length: int = 256) -> List[List[str]]:
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

    def search_repositories(self, org: str, start_date: str, end_date: str, filter: str = None) -> List[Dict[str, Any]]:
        """
        Legacy method - kept for backward compatibility.
        Use search_repositories_combined for new implementations.
        """
        return self.search_repositories_combined(org, start_date, end_date, filter=filter)

    def search_pull_requests(self, repo_full_name: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Search pull requests using GitHub Search API.

        Args:
            repo_full_name: Repository full name (e.g., 'wexinc/health-repo')
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            List of pull request data
        """
        query = f"is:pr repo:{repo_full_name} updated:{start_date}..{end_date}"
        endpoint = "search/issues"
        params = {
            "q": query,
            "sort": "updated",
            "order": "asc",
            "per_page": 100
        }

        logger.info(f"Searching pull requests with query: {query}")
        return self._paginate_search_request(endpoint, params)

    def _paginate_search_request(self, endpoint: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Paginate through GitHub Search API results.

        Args:
            endpoint: Search API endpoint
            params: Query parameters

        Returns:
            List of all items from all pages
        """
        all_items = []
        page = 1

        while True:
            try:
                # Check rate limit before making request
                self.check_rate_limit_before_request()

                current_params = {**params, "page": page}
                response = self._make_request(endpoint, current_params)

                if not response or 'items' not in response:
                    break

                items = response['items']
                if not items:
                    break

                all_items.extend(items)
                logger.info(f"Search API - {endpoint}: Fetched page {page}, {len(items)} items, total: {len(all_items)}")

                # GitHub Search API has a 1000 result limit
                if len(all_items) >= 1000 or len(items) < params.get('per_page', 30):
                    break

                page += 1

            except Exception as e:
                logger.error(f"Error during search pagination on page {page}: {e}")
                break

        logger.info(f"Search API - {endpoint}: Completed, total items: {len(all_items)}")
        return all_items

    def get_pull_request_reviews(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Get all reviews for a specific pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of review data dictionaries
        """
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        logger.debug(f"Fetching PR reviews: {endpoint}")

        try:
            response = self._make_request(endpoint)
            if response and response.status_code == 200:
                reviews = response.json()
                logger.debug(f"Found {len(reviews)} reviews for PR #{pr_number}")
                return reviews
            else:
                logger.warning(f"Failed to fetch reviews for PR #{pr_number}: {response.status_code if response else 'No response'}")
                return []
        except Exception as e:
            logger.error(f"Error fetching reviews for PR #{pr_number}: {e}")
            return []

    def get_pull_request_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Get all commits for a specific pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of commit data dictionaries
        """
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}/commits"
        logger.debug(f"Fetching PR commits: {endpoint}")

        try:
            response = self._make_request(endpoint)
            if response and response.status_code == 200:
                commits = response.json()
                logger.debug(f"Found {len(commits)} commits for PR #{pr_number}")
                return commits
            else:
                logger.warning(f"Failed to fetch commits for PR #{pr_number}: {response.status_code if response else 'No response'}")
                return []
        except Exception as e:
            logger.error(f"Error fetching commits for PR #{pr_number}: {e}")
            return []

    def get_pull_request_comments(self, owner: str, repo: str, pr_number: int) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all comments for a specific pull request (both issue comments and review comments).

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Dictionary with 'issue_comments' and 'review_comments' keys
        """
        result = {
            'issue_comments': [],
            'review_comments': []
        }

        # Get issue comments (main thread comments)
        issue_endpoint = f"repos/{owner}/{repo}/issues/{pr_number}/comments"
        logger.debug(f"Fetching PR issue comments: {issue_endpoint}")

        try:
            response = self._make_request(issue_endpoint)
            if response and response.status_code == 200:
                issue_comments = response.json()
                result['issue_comments'] = issue_comments
                logger.debug(f"Found {len(issue_comments)} issue comments for PR #{pr_number}")
            else:
                logger.warning(f"Failed to fetch issue comments for PR #{pr_number}: {response.status_code if response else 'No response'}")
        except Exception as e:
            logger.error(f"Error fetching issue comments for PR #{pr_number}: {e}")

        # Get review comments (line-specific comments)
        review_endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}/comments"
        logger.debug(f"Fetching PR review comments: {review_endpoint}")

        try:
            response = self._make_request(review_endpoint)
            if response and response.status_code == 200:
                review_comments = response.json()
                result['review_comments'] = review_comments
                logger.debug(f"Found {len(review_comments)} review comments for PR #{pr_number}")
            else:
                logger.warning(f"Failed to fetch review comments for PR #{pr_number}: {response.status_code if response else 'No response'}")
        except Exception as e:
            logger.error(f"Error fetching review comments for PR #{pr_number}: {e}")

        total_comments = len(result['issue_comments']) + len(result['review_comments'])
        logger.debug(f"Total comments for PR #{pr_number}: {total_comments}")

        return result
