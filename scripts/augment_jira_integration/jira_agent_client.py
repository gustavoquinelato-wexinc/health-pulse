#!/usr/bin/env python3
"""
Jira Integration Client for Augment Agent

This script provides a simplified command-line interface for AI agents to interact with Jira.
It uses environment variables for configuration and supports essential Jira operations.

Usage:
    python scripts/augment_jira_integration/jira_agent_client.py [--debug] get --issue ISSUE_KEY
    python scripts/augment_jira_integration/jira_agent_client.py [--debug] create-epic --title "Epic Title" --description "Epic Description"
    python scripts/augment_jira_integration/jira_agent_client.py [--debug] create-story --title "Story Title" --description "Story Description" [--parent EPIC_KEY]
    python scripts/augment_jira_integration/jira_agent_client.py [--debug] create-subtask --parent STORY_KEY --title "Subtask Title" --description "Subtask Description"
    python scripts/augment_jira_integration/jira_agent_client.py [--debug] update --issue ISSUE_KEY --title "New Title" [--description "New Description"]
    python scripts/augment_jira_integration/jira_agent_client.py [--debug] comment --issue ISSUE_KEY --message "Comment text"
    python scripts/augment_jira_integration/jira_agent_client.py [--debug] transition --issue ISSUE_KEY --status "Development" [--resolution "Done"]
    python scripts/augment_jira_integration/jira_agent_client.py [--debug] get-transitions --issue ISSUE_KEY

Debug Mode:
    Add --debug flag to see detailed environment variables, request/response information, and error details.
"""

import os
import sys
import json
import argparse
import requests
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from requests.auth import HTTPBasicAuth

# Add the project root to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

def load_env_file():
    """Load environment variables from the root .env file."""
    # Get the root directory (two levels up from this script)
    root_dir = Path(__file__).parent.parent.parent
    env_file = root_dir / '.env'

    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Only set if not already in environment
                    if key not in os.environ:
                        os.environ[key] = value

# Load environment variables from .env file
load_env_file()

class JiraAgentClient:
    """Jira client specifically designed for AI agent interactions."""

    def __init__(self, debug: bool = False):
        """Initialize the Jira client with environment variables."""
        self.debug = debug
        self.base_url = os.getenv('JIRA_URL')
        self.username = os.getenv('JIRA_USERNAME')
        self.token = os.getenv('JIRA_TOKEN')
        self.project_key = os.getenv('JIRA_PROJECT_KEY_FOR_AUGMENT_AGENT')
        self.team_field = os.getenv('JIRA_TEAM_FIELD_FOR_AUGMENT_AGENT')
        self.team_value = os.getenv('JIRA_TEAM_VALUE_FOR_AUGMENT_AGENT')

        # Load workflow configurations
        self.subtask_workflow = os.getenv('JIRA_SUBTASK_WORKFLOW', '').split(',') if os.getenv('JIRA_SUBTASK_WORKFLOW') else []
        self.story_workflow = os.getenv('JIRA_STORY_WORKFLOW', '').split(',') if os.getenv('JIRA_STORY_WORKFLOW') else []
        self.epic_workflow = os.getenv('JIRA_EPIC_WORKFLOW', '').split(',') if os.getenv('JIRA_EPIC_WORKFLOW') else []

        # Load resolution configurations
        self.resolution_required = os.getenv('JIRA_STORY_RESOLUTION_REQUIRED', 'false').lower() == 'true'
        self.success_resolution = os.getenv('JIRA_SUCCESS_RESOLUTION', 'Done')
        self.abandoned_resolution = os.getenv('JIRA_ABANDONED_RESOLUTION', "Won't Do")

        # Validate required environment variables
        required_vars = ['JIRA_URL', 'JIRA_USERNAME', 'JIRA_TOKEN', 'JIRA_PROJECT_KEY_FOR_AUGMENT_AGENT']
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Setup authentication (like health-gustractor)
        self.auth = HTTPBasicAuth(self.username, self.token)
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a request to the Jira API with error handling."""
        url = f"{self.base_url}/rest/api/latest/{endpoint}"

        if self.debug:
            print(f"DEBUG - Making {method} request to: {url}")
            print(f"DEBUG - Using auth: {self.auth.username}:{self.auth.password[:10]}...{self.auth.password[-4:]}")

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=self.headers, auth=self.auth, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, auth=self.auth, json=data, timeout=30)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=self.headers, auth=self.auth, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if self.debug:
                print(f"DEBUG - Response status: {response.status_code}")
                print(f"DEBUG - Response headers: {dict(response.headers)}")

            response.raise_for_status()

            # Handle empty responses (like 204 No Content for updates)
            if response.status_code == 204 or not response.text.strip():
                return {}

            return response.json()

        except requests.exceptions.HTTPError as e:
            if self.debug:
                print(f"DEBUG - HTTP Error: {e}")
                print(f"DEBUG - Response text: {response.text}")
            error_detail = ""
            try:
                error_detail = response.json().get('errorMessages', [])
            except:
                error_detail = response.text

            raise Exception(f"Jira API error ({response.status_code}): {error_detail}")
        except requests.exceptions.RequestException as e:
            if self.debug:
                print(f"DEBUG - Request Exception: {e}")
            raise Exception(f"Request failed: {str(e)}")

    def get_user_account_id(self, email_or_username: str) -> str:
        """Get Jira user accountId from email or username."""
        try:
            # Use the user search API to find the user
            response = self._make_request('GET', f'user/search?query={email_or_username}')

            if response and len(response) > 0:
                # Return the accountId of the first matching user
                return response[0].get('accountId')
            else:
                if self.debug:
                    print(f"DEBUG - No user found for: {email_or_username}")
                return None

        except Exception as e:
            if self.debug:
                print(f"DEBUG - Error getting user accountId: {e}")
            return None

    def create_epic(self, title: str, description: str, acceptance_criteria: str = None,
                   story_points: int = None, risk_assessment: str = None, assignee: str = None) -> Dict[str, Any]:
        """Create a new epic in the configured project with enhanced fields."""
        issue_data = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": title,
                "description": description,  # Use plain string instead of ADF
                "issuetype": {"name": "Epic"},
                "customfield_10011": title  # Epic Name field
            }
        }

        # Add acceptance criteria if provided (customfield_10222)
        if acceptance_criteria:
            issue_data["fields"]["customfield_10222"] = acceptance_criteria

        # Add story points if provided (customfield_10024)
        if story_points:
            issue_data["fields"]["customfield_10024"] = story_points

        # Add risk assessment if provided (customfield_10218)
        if risk_assessment:
            issue_data["fields"]["customfield_10218"] = risk_assessment

        # Add assignee if provided
        if assignee:
            account_id = self.get_user_account_id(assignee)
            if account_id:
                issue_data["fields"]["assignee"] = {"accountId": account_id}
            else:
                if self.debug:
                    print(f"DEBUG - Could not find accountId for assignee: {assignee}")

        # Add team field if configured
        if self.team_field and self.team_value:
            # For dropdown fields, we need to find the field ID
            # customfield_10128 is commonly used for team fields
            issue_data["fields"]["customfield_10128"] = {"value": self.team_value}

        result = self._make_request('POST', 'issue', issue_data)
        return {
            "success": True,
            "key": result.get("key"),
            "id": result.get("id"),
            "url": f"{self.base_url}/browse/{result.get('key')}",
            "message": f"Epic created successfully: {result.get('key')}"
        }

    def update_epic(self, issue_key: str, title: str = None, description: str = None,
                   acceptance_criteria: str = None, story_points: int = None,
                   risk_assessment: str = None, assignee: str = None,
                   override_mode: bool = True) -> Dict[str, Any]:
        """Update an existing epic with enhanced fields.

        Args:
            override_mode: If True, provided fields completely override existing content.
                          If False, fields are only updated if provided.
        """
        update_data = {"fields": {}}

        if title is not None:
            update_data["fields"]["summary"] = title
            update_data["fields"]["customfield_10011"] = title  # Epic Name field

        if description is not None:
            update_data["fields"]["description"] = description

        if acceptance_criteria is not None:
            update_data["fields"]["customfield_10222"] = acceptance_criteria

        if story_points is not None:
            update_data["fields"]["customfield_10024"] = story_points

        if risk_assessment is not None:
            update_data["fields"]["customfield_10218"] = risk_assessment

        if assignee is not None:
            if assignee == "":  # Empty string means unassign
                update_data["fields"]["assignee"] = None
            else:
                account_id = self.get_user_account_id(assignee)
                if account_id:
                    update_data["fields"]["assignee"] = {"accountId": account_id}
                else:
                    if self.debug:
                        print(f"DEBUG - Could not find accountId for assignee: {assignee}")

        # PUT requests for updates typically return empty responses (204 No Content)
        try:
            self._make_request('PUT', f'issue/{issue_key}', update_data)
            return {
                "success": True,
                "key": issue_key,
                "url": f"{self.base_url}/browse/{issue_key}",
                "message": f"Epic updated successfully: {issue_key}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to update epic {issue_key}: {str(e)}"
            }
    
    def create_story(self, title: str, description: str, parent_key: Optional[str] = None,
                    acceptance_criteria: str = None, story_points: int = None, assignee: str = None) -> Dict[str, Any]:
        """Create a new story, optionally under an epic, with enhanced fields."""
        issue_data = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": title,
                "description": description,  # Use plain string with Jira markup
                "issuetype": {"name": "Story"}
            }
        }

        # Add parent epic if specified
        if parent_key:
            issue_data["fields"]["parent"] = {"key": parent_key}

        # Add acceptance criteria if provided (customfield_10222)
        if acceptance_criteria:
            issue_data["fields"]["customfield_10222"] = acceptance_criteria

        # Add story points if provided (customfield_10024)
        if story_points:
            issue_data["fields"]["customfield_10024"] = story_points

        # Add assignee if provided
        if assignee:
            account_id = self.get_user_account_id(assignee)
            if account_id:
                issue_data["fields"]["assignee"] = {"accountId": account_id}
            else:
                if self.debug:
                    print(f"DEBUG - Could not find accountId for assignee: {assignee}")

        # Add team field if configured
        if self.team_field and self.team_value:
            issue_data["fields"]["customfield_10128"] = {"value": self.team_value}

        result = self._make_request('POST', 'issue', issue_data)
        return {
            "success": True,
            "key": result.get("key"),
            "id": result.get("id"),
            "url": f"{self.base_url}/browse/{result.get('key')}",
            "message": f"Story created successfully: {result.get('key')}"
        }

    def update_story(self, issue_key: str, title: str = None, description: str = None,
                    acceptance_criteria: str = None, story_points: int = None,
                    assignee: str = None, override_mode: bool = True) -> Dict[str, Any]:
        """Update an existing story with enhanced fields.

        Args:
            override_mode: If True, provided fields completely override existing content.
                          If False, fields are only updated if provided.
        """
        update_data = {"fields": {}}

        if title is not None:
            update_data["fields"]["summary"] = title

        if description is not None:
            update_data["fields"]["description"] = description

        if acceptance_criteria is not None:
            update_data["fields"]["customfield_10222"] = acceptance_criteria

        if story_points is not None:
            update_data["fields"]["customfield_10024"] = story_points

        if assignee is not None:
            if assignee == "":  # Empty string means unassign
                update_data["fields"]["assignee"] = None
            else:
                account_id = self.get_user_account_id(assignee)
                if account_id:
                    update_data["fields"]["assignee"] = {"accountId": account_id}
                else:
                    if self.debug:
                        print(f"DEBUG - Could not find accountId for assignee: {assignee}")

        # PUT requests for updates typically return empty responses (204 No Content)
        try:
            self._make_request('PUT', f'issue/{issue_key}', update_data)
            return {
                "success": True,
                "key": issue_key,
                "url": f"{self.base_url}/browse/{issue_key}",
                "message": f"Story updated successfully: {issue_key}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to update story {issue_key}: {str(e)}"
            }
    
    def create_subtask(self, parent_key: str, title: str, description: str,
                      assignee: str = None) -> Dict[str, Any]:
        """Create a new subtask under a parent story with enhanced fields."""
        issue_data = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": title,
                "description": description,  # Use plain string with Jira markup
                "issuetype": {"name": "Sub-task"},
                "parent": {"key": parent_key}
            }
        }

        # Add assignee if provided
        if assignee:
            account_id = self.get_user_account_id(assignee)
            if account_id:
                issue_data["fields"]["assignee"] = {"accountId": account_id}
            else:
                if self.debug:
                    print(f"DEBUG - Could not find accountId for assignee: {assignee}")

        # Add team field if configured
        if self.team_field and self.team_value:
            issue_data["fields"]["customfield_10128"] = {"value": self.team_value}

        result = self._make_request('POST', 'issue', issue_data)
        return {
            "success": True,
            "key": result.get("key"),
            "id": result.get("id"),
            "url": f"{self.base_url}/browse/{result.get('key')}",
            "message": f"Subtask created successfully: {result.get('key')}"
        }
    
    def update_issue(self, issue_key: str, title: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
        """Update an existing issue."""
        update_data = {"fields": {}}
        
        if title:
            update_data["fields"]["summary"] = title
        
        if description:
            update_data["fields"]["description"] = description  # Use plain string instead of ADF
        
        if not update_data["fields"]:
            return {"success": False, "message": "No fields to update"}
        
        self._make_request('PUT', f'issue/{issue_key}', update_data)
        return {
            "success": True,
            "key": issue_key,
            "url": f"{self.base_url}/browse/{issue_key}",
            "message": f"Issue updated successfully: {issue_key}"
        }
    
    def add_comment(self, issue_key: str, message: str) -> Dict[str, Any]:
        """Add a comment to an issue."""
        comment_data = {
            "body": message  # Use plain string instead of ADF
        }
        
        result = self._make_request('POST', f'issue/{issue_key}/comment', comment_data)
        return {
            "success": True,
            "comment_id": result.get("id"),
            "url": f"{self.base_url}/browse/{issue_key}",
            "message": f"Comment added to {issue_key}"
        }
    
    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """Get a specific issue by its key."""
        if self.debug:
            # Debug: Print environment variables being used
            print(f"DEBUG - Environment Variables:")
            print(f"  JIRA_URL: {self.base_url}")
            print(f"  JIRA_USERNAME: {self.username}")
            print(f"  JIRA_TOKEN: {self.token[:10]}...{self.token[-4:] if len(self.token) > 14 else self.token}")
            print(f"  JIRA_PROJECT_KEY_FOR_AUGMENT_AGENT: {self.project_key}")
            print(f"  JIRA_TEAM_FIELD_FOR_AUGMENT_AGENT: {self.team_field}")
            print(f"  JIRA_TEAM_VALUE_FOR_AUGMENT_AGENT: {self.team_value}")
            print(f"DEBUG - Request URL: {self.base_url}/rest/api/latest/issue/{issue_key}")
            print(f"DEBUG - Headers: {self.headers}")
            print(f"DEBUG - Auth: {self.auth}")
            print()

        try:
            result = self._make_request('GET', f'issue/{issue_key}')

            fields = result.get("fields", {})
            issue_data = {
                "key": result.get("key"),
                "summary": fields.get("summary"),
                "description": self._extract_description_text(fields.get("description")),
                "status": fields.get("status", {}).get("name"),
                "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else "Unassigned",
                "issuetype": fields.get("issuetype", {}).get("name"),
                "project": fields.get("project", {}).get("key"),
                "created": fields.get("created"),
                "updated": fields.get("updated"),
                "url": f"{self.base_url}/browse/{result.get('key')}"
            }

            return {
                "success": True,
                "issue": issue_data,
                "message": f"Retrieved issue: {issue_key}"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to retrieve issue: {issue_key}"
            }

    def _extract_description_text(self, description_obj) -> str:
        """Extract plain text from Jira's description object."""
        if not description_obj:
            return ""

        if isinstance(description_obj, str):
            return description_obj

        # Handle Atlassian Document Format (ADF)
        if isinstance(description_obj, dict) and "content" in description_obj:
            text_parts = []
            for content in description_obj.get("content", []):
                if content.get("type") == "paragraph":
                    for item in content.get("content", []):
                        if item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
            return " ".join(text_parts)

        return str(description_obj)

    def get_workflow_for_issue_type(self, issue_type: str) -> List[str]:
        """Get the workflow steps for a given issue type."""
        issue_type_lower = issue_type.lower()
        if issue_type_lower in ['sub-task', 'subtask']:
            return self.subtask_workflow
        elif issue_type_lower in ['story', 'task']:
            return self.story_workflow
        elif issue_type_lower == 'epic':
            return self.epic_workflow
        else:
            return []

    def validate_status_transition(self, issue_type: str, current_status: str, target_status: str) -> Dict[str, Any]:
        """Validate if a status transition is allowed for the issue type."""
        workflow = self.get_workflow_for_issue_type(issue_type)

        if not workflow:
            return {
                "valid": False,
                "error": f"No workflow defined for issue type: {issue_type}",
                "workflow": []
            }

        if current_status not in workflow:
            return {
                "valid": False,
                "error": f"Current status '{current_status}' not found in {issue_type} workflow",
                "workflow": workflow
            }

        if target_status not in workflow:
            return {
                "valid": False,
                "error": f"Target status '{target_status}' not found in {issue_type} workflow",
                "workflow": workflow
            }

        current_index = workflow.index(current_status)
        target_index = workflow.index(target_status)

        # Allow moving forward or backward in workflow
        return {
            "valid": True,
            "current_index": current_index,
            "target_index": target_index,
            "direction": "forward" if target_index > current_index else "backward" if target_index < current_index else "same",
            "workflow": workflow
        }

    def get_valid_transitions(self, issue_key: str) -> Dict[str, Any]:
        """Get valid transitions for an issue."""
        try:
            # Get current issue details
            issue_result = self.get_issue(issue_key)
            if not issue_result["success"]:
                return issue_result

            issue = issue_result["issue"]
            issue_type = issue["issuetype"]
            current_status = issue["status"]

            workflow = self.get_workflow_for_issue_type(issue_type)
            if not workflow:
                return {
                    "success": False,
                    "error": f"No workflow defined for issue type: {issue_type}",
                    "issue_key": issue_key
                }

            current_index = workflow.index(current_status) if current_status in workflow else -1

            return {
                "success": True,
                "issue_key": issue_key,
                "issue_type": issue_type,
                "current_status": current_status,
                "current_index": current_index,
                "workflow": workflow,
                "valid_transitions": workflow,
                "message": f"Workflow for {issue_type}: {' → '.join(workflow)}"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to get transitions for issue: {issue_key}"
            }

    def transition_issue(self, issue_key: str, target_status: str, resolution: str = None) -> Dict[str, Any]:
        """Transition an issue to a new status with workflow validation."""
        try:
            # Get current issue details
            issue_result = self.get_issue(issue_key)
            if not issue_result["success"]:
                return issue_result

            issue = issue_result["issue"]
            issue_type = issue["issuetype"]
            current_status = issue["status"]

            if self.debug:
                print(f"DEBUG - Transitioning {issue_key} ({issue_type}) from '{current_status}' to '{target_status}'")

            # Validate the transition
            validation = self.validate_status_transition(issue_type, current_status, target_status)
            if not validation["valid"]:
                return {
                    "success": False,
                    "error": validation["error"],
                    "issue_key": issue_key,
                    "current_status": current_status,
                    "target_status": target_status,
                    "workflow": validation.get("workflow", []),
                    "message": f"Invalid transition: {validation['error']}"
                }

            # If already at target status, no need to transition
            if current_status == target_status:
                return {
                    "success": True,
                    "issue_key": issue_key,
                    "current_status": current_status,
                    "target_status": target_status,
                    "message": f"Issue {issue_key} is already in status '{target_status}'"
                }

            # Get available transitions from Jira API
            transitions_result = self._make_request('GET', f'issue/{issue_key}/transitions')
            available_transitions = transitions_result.get('transitions', [])

            # Find the transition that leads to our target status
            target_transition = None
            for transition in available_transitions:
                if transition['to']['name'] == target_status:
                    target_transition = transition
                    break

            if not target_transition:
                available_statuses = [t['to']['name'] for t in available_transitions]
                return {
                    "success": False,
                    "error": f"No direct transition available from '{current_status}' to '{target_status}'",
                    "issue_key": issue_key,
                    "current_status": current_status,
                    "target_status": target_status,
                    "available_transitions": available_statuses,
                    "message": f"Available transitions from '{current_status}': {', '.join(available_statuses)}"
                }

            # Prepare transition data
            transition_data = {
                "transition": {
                    "id": target_transition['id']
                }
            }

            # Handle resolution for final states (only for Stories, not Sub-tasks)
            if (self.resolution_required and
                target_status.lower() in ['released', 'done', 'closed'] and
                issue_type.lower() in ['story', 'task']):
                # Determine resolution based on parameter or default to success
                if resolution:
                    final_resolution = resolution
                elif target_status.lower() == 'released':
                    final_resolution = self.success_resolution
                else:
                    final_resolution = self.success_resolution

                transition_data["fields"] = {
                    "resolution": {"name": final_resolution}
                }

                if self.debug:
                    print(f"DEBUG - Adding resolution '{final_resolution}' for final state '{target_status}' (Story/Task only)")

            if self.debug:
                print(f"DEBUG - Performing transition with data: {transition_data}")

            # Transition API typically returns 204 No Content, so handle empty response
            url = f"{self.base_url}/rest/api/latest/issue/{issue_key}/transitions"
            response = requests.post(
                url,
                headers=self.headers,
                auth=self.auth,
                json=transition_data,
                timeout=30
            )

            if self.debug:
                print(f"DEBUG - Transition response status: {response.status_code}")
                print(f"DEBUG - Transition response text: '{response.text}'")

            response.raise_for_status()  # This will handle 204 No Content properly

            return {
                "success": True,
                "issue_key": issue_key,
                "previous_status": current_status,
                "new_status": target_status,
                "transition_id": target_transition['id'],
                "url": f"{self.base_url}/browse/{issue_key}",
                "message": f"Successfully transitioned {issue_key} from '{current_status}' to '{target_status}'"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to transition issue {issue_key}: {str(e)}"
            }




def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description='Jira Integration Client for Augment Agent')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Get Issue
    get_parser = subparsers.add_parser('get', help='Get an issue by key')
    get_parser.add_argument('--issue', required=True, help='Issue key to retrieve')

    # Create Epic
    epic_parser = subparsers.add_parser('create-epic', help='Create a new epic')
    epic_parser.add_argument('--title', required=True, help='Epic title')
    epic_parser.add_argument('--description', required=True, help='Epic description')
    epic_parser.add_argument('--acceptance-criteria', help='Acceptance criteria (customfield_10222)')
    epic_parser.add_argument('--story-points', type=int, help='Story points (customfield_10024)')
    epic_parser.add_argument('--risk-assessment', help='Risk assessment (customfield_10218)')
    epic_parser.add_argument('--assignee', help='Assignee username')

    # Create Story
    story_parser = subparsers.add_parser('create-story', help='Create a new story')
    story_parser.add_argument('--title', required=True, help='Story title')
    story_parser.add_argument('--description', required=True, help='Story description')
    story_parser.add_argument('--parent', help='Parent epic key (optional)')
    story_parser.add_argument('--acceptance-criteria', help='Acceptance criteria (customfield_10222)')
    story_parser.add_argument('--story-points', type=int, help='Story points (customfield_10024)')
    story_parser.add_argument('--assignee', help='Assignee username')

    # Create Subtask
    subtask_parser = subparsers.add_parser('create-subtask', help='Create a new subtask')
    subtask_parser.add_argument('--parent', required=True, help='Parent story key')
    subtask_parser.add_argument('--title', required=True, help='Subtask title')
    subtask_parser.add_argument('--description', required=True, help='Subtask description')
    subtask_parser.add_argument('--assignee', help='Assignee username')

    # Update Issue (Generic)
    update_parser = subparsers.add_parser('update', help='Update an existing issue')
    update_parser.add_argument('--issue', required=True, help='Issue key to update')
    update_parser.add_argument('--title', help='New title')
    update_parser.add_argument('--description', help='New description')

    # Update Epic
    update_epic_parser = subparsers.add_parser('update-epic', help='Update an existing epic')
    update_epic_parser.add_argument('--issue', required=True, help='Epic key to update')
    update_epic_parser.add_argument('--title', help='New epic title')
    update_epic_parser.add_argument('--description', help='New epic description')
    update_epic_parser.add_argument('--acceptance-criteria', help='New acceptance criteria (customfield_10222)')
    update_epic_parser.add_argument('--story-points', type=int, help='New story points (customfield_10024)')
    update_epic_parser.add_argument('--risk-assessment', help='New risk assessment (customfield_10218)')
    update_epic_parser.add_argument('--assignee', help='New assignee username')

    # Update Story
    update_story_parser = subparsers.add_parser('update-story', help='Update an existing story')
    update_story_parser.add_argument('--issue', required=True, help='Story key to update')
    update_story_parser.add_argument('--title', help='New story title')
    update_story_parser.add_argument('--description', help='New story description')
    update_story_parser.add_argument('--acceptance-criteria', help='New acceptance criteria (customfield_10222)')
    update_story_parser.add_argument('--story-points', type=int, help='New story points (customfield_10024)')
    update_story_parser.add_argument('--assignee', help='New assignee username')

    # Add Comment
    comment_parser = subparsers.add_parser('comment', help='Add comment to an issue')
    comment_parser.add_argument('--issue', required=True, help='Issue key')
    comment_parser.add_argument('--message', required=True, help='Comment message')

    # Transition Issue
    transition_parser = subparsers.add_parser('transition', help='Transition an issue to a new status')
    transition_parser.add_argument('--issue', required=True, help='Issue key')
    transition_parser.add_argument('--status', required=True, help='Target status')
    transition_parser.add_argument('--resolution', help='Resolution for final states (Done, Won\'t Do, etc.)')

    # Get Valid Transitions
    transitions_parser = subparsers.add_parser('get-transitions', help='Get valid transitions for an issue')
    transitions_parser.add_argument('--issue', required=True, help='Issue key')

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        client = JiraAgentClient(debug=args.debug)

        if args.command == 'get':
            result = client.get_issue(args.issue)
        elif args.command == 'create-epic':
            result = client.create_epic(
                args.title,
                args.description,
                getattr(args, 'acceptance_criteria', None),
                getattr(args, 'story_points', None),
                getattr(args, 'risk_assessment', None),
                getattr(args, 'assignee', None)
            )
        elif args.command == 'create-story':
            result = client.create_story(
                args.title,
                args.description,
                args.parent,
                getattr(args, 'acceptance_criteria', None),
                getattr(args, 'story_points', None),
                getattr(args, 'assignee', None)
            )
        elif args.command == 'create-subtask':
            result = client.create_subtask(
                args.parent,
                args.title,
                args.description,
                getattr(args, 'assignee', None)
            )
        elif args.command == 'update':
            result = client.update_issue(args.issue, args.title, args.description)
        elif args.command == 'update-epic':
            result = client.update_epic(
                args.issue,
                getattr(args, 'title', None),
                getattr(args, 'description', None),
                getattr(args, 'acceptance_criteria', None),
                getattr(args, 'story_points', None),
                getattr(args, 'risk_assessment', None),
                getattr(args, 'assignee', None)
            )
        elif args.command == 'update-story':
            result = client.update_story(
                args.issue,
                getattr(args, 'title', None),
                getattr(args, 'description', None),
                getattr(args, 'acceptance_criteria', None),
                getattr(args, 'story_points', None),
                getattr(args, 'assignee', None)
            )
        elif args.command == 'comment':
            result = client.add_comment(args.issue, args.message)
        elif args.command == 'transition':
            result = client.transition_issue(args.issue, args.status, args.resolution)
        elif args.command == 'get-transitions':
            result = client.get_valid_transitions(args.issue)
        else:
            print(f"Unknown command: {args.command}")
            return
        
        # Output result as JSON for AI agent consumption
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "message": f"Operation failed: {str(e)}"
        }
        print(json.dumps(error_result, indent=2))
        sys.exit(1)


if __name__ == '__main__':
    main()
