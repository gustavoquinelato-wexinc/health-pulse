"""
Jira API Client

Handles all interactions with the Jira REST API for ETL operations.
"""

import requests
import time
from typing import List, Dict
from app.core.logging_config import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)


class JiraAPIClient:
    """Client for Jira API."""
    
    def __init__(self, username: str, token: str, base_url: str):
        self.username = username
        self.token = token
        self.base_url = base_url
        # Progress tracking
        self.last_fetch_progress = {'current': 0, 'total': 0, 'percentage': 0}
    
    def get_projects(self, expand: str = None, max_results: int = 50) -> List[Dict]:
        """
        Fetch Jira projects filtered by configured project keys with pagination and retry logic.

        Args:
            expand: Fields to expand in the response
            max_results: Maximum results per page (default: 50)

        Returns:
            List of project objects
        """
        settings = get_settings()
        jira_projects = settings.jira_projects_list

        all_projects = []
        start_at = 0
        max_retries = 3

        while True:
            # Try to fetch a page with retries
            for retry_count in range(max_retries):
                try:
                    # Use API 3 search endpoint with project keys filter
                    url = f"{self.base_url}/rest/api/3/project/search"

                    # Build params as list of tuples to handle multiple 'keys' parameters
                    params = [
                        ('startAt', start_at),
                        ('maxResults', max_results)
                    ]

                    # Add each project key as a separate 'keys' parameter
                    for project_key in jira_projects:
                        params.append(('keys', str(project_key)))

                    if expand:
                        params.append(('expand', expand))

                    response = requests.get(
                        url,
                        auth=(self.username, self.token),
                        params=params,
                        timeout=30
                    )
                    response.raise_for_status()

                    # Handle the API 3 response structure
                    response_data = response.json()

                    # API 3 returns: {"values": [...], "total": 12, "maxResults": 50, ...}
                    if isinstance(response_data, dict) and 'values' in response_data:
                        batch_data = response_data['values']
                        total = response_data.get('total', 0)
                        is_last = response_data.get('isLast', True)
                    else:
                        # Fallback for unexpected response format
                        batch_data = response_data if isinstance(response_data, list) else []
                        total = len(batch_data)
                        is_last = True

                    # Success! Process the data
                    if batch_data:
                        all_projects.extend(batch_data)
                        logger.debug(f"Fetched {len(batch_data)} projects (total: {len(all_projects)})")

                    # Check if we have more pages
                    if not batch_data or is_last or len(batch_data) < max_results or start_at + len(batch_data) >= total:
                        # No more pages, we're done with pagination
                        logger.info(f"Successfully fetched {len(all_projects)} projects")
                        return all_projects

                    # More pages available, continue pagination
                    start_at += max_results
                    break  # Break out of retry loop, continue with next page

                except requests.exceptions.RequestException as e:
                    if retry_count < max_retries - 1:
                        wait_time = 2 ** (retry_count + 1)  # Exponential backoff
                        logger.warning(f"Request failed for projects (attempt {retry_count + 1}/{max_retries}), retrying in {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Failed to fetch projects after {max_retries} attempts: {e}")
                        return all_projects
                except Exception as e:
                    logger.error(f"Unexpected error fetching projects: {e}")
                    return all_projects
            else:
                # If we get here, all retries failed
                logger.error(f"Failed to fetch projects after {max_retries} attempts")
                break

        logger.info(f"Successfully fetched {len(all_projects)} projects")
        return all_projects

    def get_project_statuses(self, project_id: str, max_results: int = 100) -> List[Dict]:
        """
        Fetch all statuses for a specific project with pagination and retry logic.

        Args:
            project_id: The project ID or key
            max_results: Maximum results per page (default: 100)

        Returns:
            List of issue type objects, each containing statuses array
        """
        all_statuses = []
        start_at = 0
        max_retries = 3

        while True:
            retry_count = 0
            success = False

            while retry_count < max_retries and not success:
                try:
                    url = f"{self.base_url}/rest/api/3/project/{project_id}/statuses"
                    params = {
                        'startAt': start_at,
                        'maxResults': max_results
                    }

                    response = requests.get(
                        url,
                        auth=(self.username, self.token),
                        params=params,
                        timeout=30
                    )
                    response.raise_for_status()

                    result = response.json()

                    # The API returns an array of issue types with statuses
                    if isinstance(result, list):
                        batch_data = result
                    else:
                        # Handle paginated response structure if it exists
                        batch_data = result.get('values', result.get('issuetypes', []))

                    if not batch_data:
                        success = True
                        break

                    all_statuses.extend(batch_data)
                    logger.debug(f"Fetched {len(batch_data)} issue types with statuses for project {project_id} (total: {len(all_statuses)})")

                    # Check if we have more pages
                    if isinstance(result, dict):
                        is_last = result.get('isLast', True)
                        total = result.get('total', len(batch_data))
                        if is_last or len(batch_data) < max_results or start_at + len(batch_data) >= total:
                            success = True
                            break
                    else:
                        # For array responses, if we get less than max_results, we're done
                        if len(batch_data) < max_results:
                            success = True
                            break

                    start_at += max_results
                    success = True

                except requests.exceptions.RequestException as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count  # Exponential backoff
                        logger.warning(f"Request failed for project {project_id} statuses (attempt {retry_count}/{max_retries}), retrying in {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Failed to fetch statuses for project {project_id} after {max_retries} attempts: {e}")
                        return all_statuses
                except Exception as e:
                    logger.error(f"Unexpected error fetching statuses for project {project_id}: {e}")
                    return all_statuses

            if not success:
                break

            # If we got here and it's not paginated (array response), we're done
            if isinstance(result, list):
                break

        logger.info(f"Successfully fetched {len(all_statuses)} issue types with statuses for project {project_id}")
        return all_statuses
    
    def get_issues(self, jql: str = None, max_results: int = 100, progress_callback=None) -> List[Dict]:
        """
        Fetch all Jira issues with changelog using JQL with pagination and retry logic.

        Args:
            jql: JQL query string
            max_results: Maximum results per page (default: 100)
            progress_callback: Optional callback function for progress updates

        Returns:
            List of all issues matching the JQL query
        """
        if not jql:
            # Default JQL to fetch recently updated issues
            jql = f"updated >= -30d ORDER BY updated DESC"

        all_issues = []
        start_at = 0
        max_retries = 3

        while True:
            # Try to fetch a page with retries
            for retry_count in range(max_retries):
                try:
                    url = f"{self.base_url}/rest/api/2/search"
                    params = {
                        'jql': jql,
                        'startAt': start_at,
                        'maxResults': max_results,
                        'fields': '*all',
                        'expand': 'changelog'  # Always include changelog
                    }

                    response = requests.get(
                        url,
                        auth=(self.username, self.token),
                        params=params,
                        timeout=5  # Very short timeout to prevent blocking
                    )
                    response.raise_for_status()

                    result = response.json()
                    batch_issues = result.get('issues', [])
                    total = result.get('total', 0)

                    # Success! Process the data
                    if batch_issues:
                        all_issues.extend(batch_issues)

                        # Call progress callback if provided
                        if progress_callback:
                            progress_callback(f"Fetched {len(all_issues)} of {total} issues so far...")
                        else:
                            logger.info(f"[JIRA] Fetched {len(batch_issues)} issues (total: {len(all_issues)}/{total})")

                        # Store progress information for external access
                        self.last_fetch_progress = {
                            'current': len(all_issues),
                            'total': total,
                            'percentage': (len(all_issues) / total) * 100 if total > 0 else 0
                        }

                    # Check if we have more pages
                    if not batch_issues or len(batch_issues) < max_results or start_at + len(batch_issues) >= total:
                        # No more pages, we're done with pagination
                        logger.info(f"Successfully fetched {len(all_issues)} issues with JQL: {jql}")
                        return all_issues

                    # More pages available, continue pagination
                    start_at += max_results
                    break  # Break out of retry loop, continue with next page

                except requests.exceptions.RequestException as e:
                    if retry_count < max_retries - 1:
                        wait_time = 2 ** (retry_count + 1)  # Exponential backoff
                        logger.warning(f"Request failed for issues JQL '{jql}' (attempt {retry_count + 1}/{max_retries}), retrying in {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Failed to fetch issues with JQL '{jql}' after {max_retries} attempts: {e}")
                        return all_issues
                except Exception as e:
                    logger.error(f"Unexpected error fetching issues with JQL '{jql}': {e}")
                    return all_issues
            else:
                # If we get here, all retries failed
                logger.error(f"Failed to fetch issues with JQL '{jql}' after {max_retries} attempts")
                return all_issues

    def get_issue_changelogs(self, issue_key: str, max_results: int = 100) -> List[Dict]:
        """
        Fetch all changelogs for a specific issue with pagination and retry logic.

        NOTE: This method is kept for backward compatibility and fallback scenarios.
        The preferred approach is to use expand=changelog in get_issues() to fetch
        changelogs together with issues in a single API call.

        Args:
            issue_key: The issue key (e.g., 'PROJ-123')
            max_results: Maximum number of changelogs to fetch per request

        Returns:
            List of changelog dictionaries
        """
        all_changelogs = []
        start_at = 0
        max_retries = 3

        while True:
            url = f"{self.base_url}/rest/api/2/issue/{issue_key}/changelog"
            params = {
                'startAt': start_at,
                'maxResults': max_results
            }

            success = False
            for attempt in range(max_retries):
                try:
                    response = requests.get(
                        url,
                        params=params,
                        auth=(self.username, self.token),
                        headers={'Accept': 'application/json'},
                        timeout=30
                    )

                    if response.status_code == 200:
                        data = response.json()
                        changelogs = data.get('values', [])
                        all_changelogs.extend(changelogs)

                        # Check if there are more results
                        if len(changelogs) < max_results or data.get('isLast', True):
                            return all_changelogs  # No more pages, return results

                        start_at += len(changelogs)
                        success = True
                        break  # Break retry loop, continue pagination
                    elif response.status_code == 404:
                        logger.warning(f"Issue {issue_key} not found")
                        return []
                    else:
                        logger.warning(f"Attempt {attempt + 1}: HTTP {response.status_code} for issue {issue_key}")
                        if attempt == max_retries - 1:  # Last attempt
                            logger.error(f"Failed to fetch changelogs for issue {issue_key} after {max_retries} attempts")
                            return []
                        time.sleep(2 ** attempt)  # Exponential backoff

                except requests.exceptions.RequestException as e:
                    logger.warning(f"Attempt {attempt + 1}: Request failed for issue {issue_key}: {e}")
                    if attempt == max_retries - 1:  # Last attempt
                        logger.error(f"Failed to fetch changelogs for issue {issue_key} after {max_retries} attempts")
                        return []
                    time.sleep(2 ** attempt)  # Exponential backoff

            # If we didn't succeed after all retries, break the pagination loop
            if not success:
                break

        logger.info(f"Successfully fetched {len(all_changelogs)} changelogs for issue {issue_key}")
        return all_changelogs

    def _make_request(self, endpoint: str, method: str = 'GET', params: Dict = None, headers: Dict = None, timeout: int = 30) -> Dict:
        """
        Generic method to make HTTP requests to Jira API.

        Args:
            endpoint: API endpoint (without base URL)
            method: HTTP method (GET, POST, etc.)
            params: Query parameters
            headers: Request headers
            timeout: Request timeout in seconds

        Returns:
            JSON response as dictionary
        """
        url = f"{self.base_url}/{endpoint}"

        # Default headers
        default_headers = {'Accept': 'application/json'}
        if headers:
            default_headers.update(headers)

        try:
            if method.upper() == 'GET':
                response = requests.get(
                    url,
                    auth=(self.username, self.token),
                    params=params,
                    headers=default_headers,
                    timeout=timeout
                )
            elif method.upper() == 'POST':
                response = requests.post(
                    url,
                    auth=(self.username, self.token),
                    params=params,
                    headers=default_headers,
                    timeout=timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {endpoint}: {e}")
            return {}

    def get_issue_dev_details(self, issue_external_id: str, application_type: str = "GitHub", data_type: str = "branch") -> Dict:
        """
        Fetch development details for a specific issue.

        Args:
            issue_external_id: The external ID of the issue
            application_type: Type of application (GitHub, Bitbucket, etc.)
            data_type: Type of data to fetch (branch, pullrequest, etc.)

        Returns:
            Development details as dictionary
        """
        endpoint = "rest/dev-status/latest/issue/detail"
        params = {
            "issueId": issue_external_id,
            "applicationType": application_type,
            "dataType": data_type
        }

        logger.debug(f"Fetching development details for issue {issue_external_id}")
        return self._make_request(endpoint, params=params)
