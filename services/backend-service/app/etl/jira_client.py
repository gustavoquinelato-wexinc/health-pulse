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
            logger.info(f"Successfully fetched {len(projects)} projects")

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
