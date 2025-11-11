"""
Jira API Client for ETL Backend Service
Handles Jira API interactions for custom fields discovery and other ETL operations
"""

import requests
from typing import List, Dict, Any, Optional
from app.core.logging_config import get_logger
from app.core.config import AppConfig

logger = get_logger(__name__)


class JiraAPIClient:
    """Client for Jira API operations in the ETL backend service."""
    
    def __init__(self, username: str, token: str, base_url: str):
        """
        Initialize Jira API client.
        
        Args:
            username: Jira username/email
            token: Jira API token (encrypted)
            base_url: Jira instance base URL
        """
        self.username = username
        self.token = token
        self.base_url = base_url.rstrip('/')
    
    def get_createmeta(self, project_keys: List[str], issue_type_names: Optional[List[str]] = None, expand: Optional[str] = None) -> Dict[str, Any]:
        """
        Get create metadata for projects using Jira's createmeta API.
        
        Args:
            project_keys: List of project keys to get metadata for
            issue_type_names: Optional list of issue type names to filter by
            expand: Optional expand parameter (e.g., 'projects.issuetypes.fields')
            
        Returns:
            Dictionary containing createmeta response with projects, issue types, and custom fields
        """
        try:
            url = f"{self.base_url}/rest/api/3/issue/createmeta"
            
            # Build query parameters
            params = {
                'projectKeys': ','.join(project_keys)
            }
            
            if issue_type_names:
                params['issuetypeNames'] = ','.join(issue_type_names)
            
            if expand:
                params['expand'] = expand
            
            logger.info(f"Requesting createmeta for projects: {project_keys}")
            
            response = requests.get(
                url,
                auth=(self.username, self.token),
                params=params,
                headers={
                    'Accept': 'application/json',
                    'Accept-Charset': 'utf-8',
                    'User-Agent': 'Health-Pulse-ETL-Backend/1.0'
                },
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Successfully retrieved createmeta for {len(result.get('projects', []))} projects")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get createmeta for projects {project_keys}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting createmeta: {e}")
            raise

    def get_field_by_id(self, field_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific field by ID using Jira's field search API.
        This is used for special fields like development that don't appear in createmeta.

        Args:
            field_id: The field ID to search for (e.g., 'customfield_10000')

        Returns:
            Dictionary containing full API response with 'values' array, or None if not found
        """
        try:
            url = f"{self.base_url}/rest/api/3/field/search"

            params = {
                'id': field_id
            }

            logger.info(f"Requesting field info for: {field_id}")

            response = requests.get(
                url,
                auth=(self.username, self.token),
                params=params,
                headers={
                    'Accept': 'application/json',
                    'Accept-Charset': 'utf-8',
                    'User-Agent': 'Health-Pulse-ETL-Backend/1.0'
                },
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            values = result.get('values', [])
            if values:
                logger.info(f"Successfully retrieved field info for {field_id}: {values[0].get('name')}")
                # Return full response with values array for transform worker
                return result
            else:
                logger.warning(f"Field {field_id} not found")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get field info for {field_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting field info for {field_id}: {e}")
            return None

    def get_projects(self, project_keys: Optional[List[str]] = None, max_results: int = 100, expand: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch Jira projects with issue types, optionally filtered by project keys.

        Args:
            project_keys: Optional list of project keys to filter by
            max_results: Maximum results per page (default: 100)
            expand: Optional expand parameter for additional data

        Returns:
            List of project objects with issue types included
        """
        try:
            url = f"{self.base_url}/rest/api/3/project/search"

            # Build params as list of tuples to handle multiple 'keys' parameters
            params = [
                ('startAt', 0),
                ('maxResults', max_results)
            ]

            # Add each project key as a separate 'keys' parameter (matching old ETL service)
            if project_keys:
                for project_key in project_keys:
                    params.append(('keys', str(project_key)))

            if expand:
                params.append(('expand', expand))

            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'User-Agent': 'Health-Pulse-ETL/1.0'
            }

            logger.info(f"Fetching projects with keys: {project_keys or 'ALL'}")

            response = requests.get(
                url,
                auth=(self.username, self.token),
                params=params,
                headers=headers,
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            # API 3 returns: {"values": [...], "total": 12, "maxResults": 50, ...}
            projects = result.get('values', [])
            total = result.get('total', 0)

            # Log project keys that were returned
            returned_keys = [p.get('key') for p in projects]
            logger.info(f"Successfully fetched {len(projects)} projects out of {total} total")
            logger.info(f"Returned project keys: {returned_keys}")

            # Check if we got all requested projects
            if project_keys:
                missing_keys = set(project_keys) - set(returned_keys)
                if missing_keys:
                    logger.warning(f"⚠️ Missing projects from Jira API response: {list(missing_keys)}")
                    logger.warning(f"Possible reasons:")
                    logger.warning(f"  1. Projects are archived or deleted in Jira")
                    logger.warning(f"  2. User doesn't have permission to access these projects")
                    logger.warning(f"  3. Projects are hidden from the API user")
                    logger.warning(f"  4. Project keys are misspelled in integration settings")
                    logger.warning(f"ETL will continue with {len(projects)} accessible projects: {returned_keys}")

            return projects

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get projects: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting projects: {e}")
            raise
    
    @classmethod
    def create_from_integration(cls, integration) -> 'JiraAPIClient':
        """
        Create JiraAPIClient from an Integration model instance.
        
        Args:
            integration: Integration model instance with Jira credentials
            
        Returns:
            Configured JiraAPIClient instance
        """
        # Decrypt the token
        key = AppConfig.load_key()
        decrypted_token = AppConfig.decrypt_token(integration.password, key)
        
        return cls(
            username=integration.username,
            token=decrypted_token,
            base_url=integration.base_url
        )



    def get_project_statuses(self, project_key: str) -> List[Dict[str, Any]]:
        """
        Get project-specific statuses for a single project (following old ETL approach).

        Args:
            project_key: Single project key to get statuses for

        Returns:
            List of issue type objects, each containing statuses array
        """
        try:
            url = f"{self.base_url}/rest/api/3/project/{project_key}/statuses"

            response = requests.get(
                url,
                auth=(self.username, self.token),
                headers={'Accept': 'application/json'},
                timeout=30
            )

            if response.status_code == 200:
                statuses_data = response.json()
                logger.info(f"Retrieved statuses for project {project_key}: {len(statuses_data)} issue types")
                return statuses_data
            else:
                logger.warning(f"Failed to get statuses for project {project_key}: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error getting statuses for project {project_key}: {e}")
            return []

    def search_issues(
        self,
        jql: str,
        next_page_token: Optional[str] = None,
        max_results: int = 50,
        fields: Optional[List[str]] = None,
        expand: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Search for issues using JQL with pagination support using nextPageToken.

        Args:
            jql: JQL query string
            next_page_token: Token for next page (from previous response)
            max_results: Maximum results per page (default: 50, max: 100)
            fields: List of fields to include in response (default: all)
            expand: List of entities to expand (e.g., ['changelog'])

        Returns:
            Dictionary containing:
            - issues: List of issue objects
            - nextPageToken: Token for next page (if available)
            - isLast: Boolean indicating if this is the last page
        """
        try:
            # Use the latest JQL search API (same as old etl-service)
            url = f"{self.base_url}/rest/api/latest/search/jql"

            # Build request body for POST request
            request_body = {
                'jql': jql,
                'maxResults': max_results
            }

            # Handle fields parameter
            if fields:
                # If fields is ['*all'], use "*all" string in array
                if fields == ['*all']:
                    request_body['fields'] = ['*all']
                else:
                    request_body['fields'] = fields

            # Handle expand parameter - must be a string, not array
            if expand:
                # If expand is a list, join with comma
                if isinstance(expand, list):
                    request_body['expand'] = ','.join(expand)
                else:
                    request_body['expand'] = expand

            # Handle pagination using nextPageToken (new API style)
            if next_page_token:
                request_body['nextPageToken'] = next_page_token

            logger.debug(f"Searching issues with JQL: {jql} (nextPageToken={'present' if next_page_token else 'none'}, maxResults={max_results})")

            response = requests.post(
                url,
                auth=(self.username, self.token),
                json=request_body,
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'User-Agent': 'Health-Pulse-ETL-Backend/1.0'
                },
                timeout=60
            )

            response.raise_for_status()
            result = response.json()

            issues_count = len(result.get('issues', []))
            is_last = result.get('isLast', True)
            has_next = result.get('nextPageToken') is not None

            logger.info(f"Retrieved {issues_count} issues (isLast={is_last}, hasNext={has_next})")

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to search issues with JQL '{jql}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching issues: {e}")
            raise

    def get_issue_dev_details(self, issue_external_id: str, application_type: str = "GitHub", data_type: str = "branch") -> Dict[str, Any]:
        """
        Fetch development details for a specific issue.

        Args:
            issue_external_id: The external ID of the issue
            application_type: Type of application (GitHub, Bitbucket, etc.)
            data_type: Type of data to fetch (branch, pullrequest, etc.)

        Returns:
            Development details as dictionary
        """
        import time
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                url = f"{self.base_url}/rest/dev-status/latest/issue/detail"
                params = {
                    "issueId": issue_external_id,
                    "applicationType": application_type,
                    "dataType": data_type
                }

                logger.debug(f"Fetching development details for issue {issue_external_id} (attempt {attempt + 1}/{max_retries})")

                response = requests.get(
                    url,
                    auth=(self.username, self.token),
                    params=params,
                    headers={'Accept': 'application/json'},
                    timeout=30
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Failed to get dev details for issue {issue_external_id}: {response.status_code}")
                    return {}

            except (requests.exceptions.ConnectionError, ConnectionResetError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Connection error fetching dev details for issue {issue_external_id} (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"Error fetching dev details for issue {issue_external_id} after {max_retries} attempts: {e}")
                    return {}
            except Exception as e:
                logger.error(f"Error fetching dev details for issue {issue_external_id}: {e}")
                return {}

    def get_dev_status(self, issue_id: str) -> Dict[str, Any]:
        """
        Alias for get_issue_dev_details for consistency with extraction worker.

        Args:
            issue_id: The external ID of the issue

        Returns:
            Development status details as dictionary
        """
        return self.get_issue_dev_details(issue_id, application_type="GitHub", data_type="pullrequest")


def extract_custom_fields_from_createmeta(createmeta_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract custom fields information from Jira createmeta API response.
    
    Args:
        createmeta_response: Response from /rest/api/3/issue/createmeta
        
    Returns:
        List of discovered custom fields with metadata
    """
    discovered_fields = []
    
    try:
        projects = createmeta_response.get('projects', [])
        
        for project in projects:
            project_key = project.get('key')
            project_name = project.get('name')
            
            issue_types = project.get('issuetypes', [])
            
            for issue_type in issue_types:
                issue_type_name = issue_type.get('name')
                fields = issue_type.get('fields', {})
                
                for field_id, field_info in fields.items():
                    # Only process custom fields (they start with 'customfield_')
                    if field_id.startswith('customfield_'):
                        field_name = field_info.get('name', field_id)
                        field_schema = field_info.get('schema', {})
                        field_type = field_schema.get('type', 'unknown')
                        
                        # Check if we already have this field
                        existing_field = next(
                            (f for f in discovered_fields if f['jira_field_id'] == field_id),
                            None
                        )
                        
                        if existing_field:
                            # Add project to existing field
                            if project_key not in existing_field['projects']:
                                existing_field['projects'].append(project_key)
                                existing_field['project_count'] += 1
                            if issue_type_name not in existing_field['issue_types']:
                                existing_field['issue_types'].append(issue_type_name)
                        else:
                            # Add new field
                            discovered_fields.append({
                                'jira_field_id': field_id,
                                'jira_field_name': field_name,
                                'jira_field_type': field_type,
                                'schema': field_schema,
                                'projects': [project_key],
                                'project_count': 1,
                                'issue_types': [issue_type_name]
                            })
        
        logger.info(f"Extracted {len(discovered_fields)} unique custom fields from createmeta response")
        return discovered_fields

    except Exception as e:
        logger.error(f"Error extracting custom fields from createmeta: {e}")
        return []
