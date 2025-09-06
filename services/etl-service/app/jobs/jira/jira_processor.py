"""
Jira Data Processor

Handles transformation and processing of Jira data for ETL operations.
"""

from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.logging_config import get_logger
from app.core.utils import DateTimeHelper
from app.models.unified_models import Project, Wit, Status, StatusMapping, WitMapping

logger = get_logger(__name__)


class JiraDataProcessor:
    """Processes and transforms Jira data for database storage."""

    def __init__(self, session: Session, integration=None):
        self.session = session
        self.integration = integration
    
    def process_issue_data(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process raw Jira issue data into database format.
        
        Args:
            issue_data: Raw issue data from Jira API
            
        Returns:
            Processed issue data ready for database insertion
        """
        try:
            fields = issue_data.get('fields', {})

            # Extract basic fields
            processed = {
                'key': issue_data.get('key', None),
                'summary': fields.get('summary', None),
                'description': self._extract_description(fields.get('description')),
                'acceptance_criteria': fields.get('customfield_10222', None),  # Acceptance criteria custom field
                'created': self._parse_datetime(fields.get('created')),
                'updated': self._parse_datetime(fields.get('updated')),
                'work_first_started_at': None,  # Will be calculated from status transitions
                'work_first_completed_at': None,  # Will be calculated from status transitions
                'priority': self._extract_priority(fields.get('priority')),
                'resolution': self._extract_resolution(fields.get('resolution')),
                'labels': fields.get('labels') if fields.get('labels') else None,  # None for empty lists
                'story_points': fields.get('customfield_10024'),  # Story points field
                'team': self._extract_team(fields.get('customfield_10128')),  # Team custom field
                'assignee': self._extract_assignee(fields.get('assignee')),
                'project_id': self._extract_project_id(fields.get('project')),
                'wit_id': self._extract_wit_id(fields.get('issuetype')),
                'status_id': self._extract_status_id(fields.get('status')),
                'parent_id': self._extract_parent_id(fields.get('parent')),
                'code_changed': True if fields.get('customfield_10000','') != "{}" else False,

                # Custom fields (01-20) - can be mapped to specific Jira custom fields later
                # Example mapping: 'custom_field_01': fields.get('customfield_12345', None),
                'custom_field_01': fields.get('customfield_10110', None),  # aha_epic_url
                'custom_field_02': fields.get('customfield_10150', None),  # aha_initiative
                'custom_field_03': fields.get('customfield_10359', None),  # aha_project_code
                'custom_field_04': fields.get('customfield_10414') if fields.get('customfield_10414') else None,  # project_code
                'custom_field_05': fields.get('customfield_12103', None),  # aha_milestone
                'custom_field_06': None,  # Available for future mapping
                'custom_field_07': None,  # Available for future mapping
                'custom_field_08': None,  # Available for future mapping
                'custom_field_09': None,  # Available for future mapping
                'custom_field_10': None,  # Available for future mapping
                'custom_field_11': None,  # Available for future mapping
                'custom_field_12': None,  # Available for future mapping
                'custom_field_13': None,  # Available for future mapping
                'custom_field_14': None,  # Available for future mapping
                'custom_field_15': None,  # Available for future mapping
                'custom_field_16': None,  # Available for future mapping
                'custom_field_17': None,  # Available for future mapping
                'custom_field_18': None,  # Available for future mapping
                'custom_field_19': None,  # Available for future mapping
                'custom_field_20': None   # Available for future mapping
            }

            # Log schema compatibility success
            logger.debug(f"✅ Processed issue {issue_data.get('key', 'unknown')} with enhanced schema compatibility (embedding=None)")
            return processed

        except Exception as e:
            logger.error(f"❌ Schema compatibility error processing issue {issue_data.get('key', 'unknown')}: {e}")
            return {}
    
    def _parse_datetime(self, date_str: str) -> datetime:
        """Parse Jira datetime string preserving local time for user-friendly analysis."""
        return DateTimeHelper.parse_jira_datetime_preserve_local(date_str)
    
    def _extract_priority(self, priority_data: Dict) -> str:
        """Extract priority name from Jira priority object."""
        if not priority_data:
            return None
        return priority_data.get('name', None)
    
    def _extract_resolution(self, resolution_data: Dict) -> str:
        """Extract resolution name from Jira resolution object."""
        if not resolution_data:
            return None
        return resolution_data.get('name', None)
    
    def _extract_assignee(self, assignee_data: Dict) -> str:
        """Extract assignee display name from Jira assignee object."""
        if not assignee_data:
            return None
        return f"{assignee_data.get('displayName', None)} <{assignee_data.get('emailAddress', None)}>"
    
    def _extract_project_id(self, project_data: Dict) -> str:
        """Extract project ID from Jira project object."""
        if not project_data:
            return None
        return project_data.get('id', None)
    
    def _extract_wit_id(self, issuetype_data: Dict) -> str:
        """Extract issue type ID from Jira issue type object."""
        if not issuetype_data:
            return None
        return issuetype_data.get('id', None)
    
    def _extract_status_id(self, status_data: Dict) -> str:
        """Extract status ID from Jira status object."""
        if not status_data:
            return None
        return status_data.get('id', None)

    def _extract_team(self, team_data: Dict) -> str:
        """Extract team name from Jira custom field object."""
        if not team_data:
            return None
        if isinstance(team_data, dict):
            return team_data.get('value', None)
        return str(team_data) if team_data else None

    def _extract_description(self, description_obj) -> str:
        """Extract plain text from Jira's description object (handles ADF format)."""
        if not description_obj:
            return None

        # If it's already a string, return it
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
                elif content.get("type") == "codeBlock":
                    # Handle code blocks
                    for item in content.get("content", []):
                        if item.get("type") == "text":
                            text_parts.append(f"```\n{item.get('text', '')}\n```")
                elif content.get("type") == "bulletList" or content.get("type") == "orderedList":
                    # Handle lists
                    for list_item in content.get("content", []):
                        if list_item.get("type") == "listItem":
                            for paragraph in list_item.get("content", []):
                                if paragraph.get("type") == "paragraph":
                                    for item in paragraph.get("content", []):
                                        if item.get("type") == "text":
                                            text_parts.append(f"• {item.get('text', '')}")
            return "\n".join(text_parts) if text_parts else None

        # Fallback to string conversion
        return str(description_obj) if description_obj else None
    
    def _extract_parent_id(self, parent_data: Dict) -> str:
        """Extract parent issue ID from Jira parent object."""
        if not parent_data:
            return None
        return parent_data.get('id', None)
    
    def process_project_data(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process raw Jira project data into database format.

        Args:
            project_data: Raw project data from Jira API

        Returns:
            Processed project data ready for database insertion
        """
        try:
            # Helper function to safely handle unicode strings
            def safe_unicode_string(value):
                if value is None:
                    return None
                if isinstance(value, str):
                    # Replace problematic unicode characters that might cause encoding issues
                    return value.encode('utf-8', errors='replace').decode('utf-8')
                return str(value)

            processed_data = {
                'external_id': project_data.get('id', None),
                'key': safe_unicode_string(project_data.get('key', None)),
                'name': safe_unicode_string(project_data.get('name', None)),
                'project_type': safe_unicode_string(project_data.get('projectTypeKey', None))
                # embedding field automatically defaults to None in model
            }

            # Log schema compatibility success
            logger.debug(f"✅ Processed project {project_data.get('key', 'unknown')} with enhanced schema compatibility")
            return processed_data

        except Exception as e:
            logger.error(f"❌ Schema compatibility error processing project {project_data.get('key', 'unknown')}: {e}")
            return {}
    
    def process_issuetype_data(self, issuetype_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process raw Jira issue type data into database format with mapping.

        Args:
            issuetype_data: Raw issue type data from Jira API

        Returns:
            Processed issue type data ready for database insertion
        """
        try:
            # Helper function to safely handle unicode strings
            def safe_unicode_string(value):
                if value is None:
                    return None
                if isinstance(value, str):
                    # Replace problematic unicode characters that might cause encoding issues
                    return value.encode('utf-8', errors='replace').decode('utf-8')
                return str(value)

            original_name = safe_unicode_string(issuetype_data.get('name', None))

            # Find issuetype mapping for this issue type from database
            issuetype_mapping_id = None
            hierarchy_level = issuetype_data.get('hierarchyLevel', 0)  # Default hierarchy level
            tenant_id = getattr(self.integration, 'tenant_id', None) if self.integration else None

            if original_name and tenant_id:
                # Look up issuetype mapping in database (case-insensitive on both sides)
                # Include the hierarchy relationship to avoid lazy loading issues
                from sqlalchemy.orm import joinedload
                issuetype_mapping = self.session.query(WitMapping).options(
                    joinedload(WitMapping.issuetype_hierarchy)
                ).filter(
                    func.lower(WitMapping.issuetype_from) == original_name.lower(),
                    WitMapping.tenant_id == tenant_id
                ).first()

                if issuetype_mapping:
                    issuetype_mapping_id = issuetype_mapping.id
                    # Get hierarchy level from the related hierarchy record
                    hierarchy_level = issuetype_mapping.issuetype_hierarchy.level_number if issuetype_mapping.issuetype_hierarchy else 0
                    logger.debug(f"Mapped issuetype '{original_name}' to '{issuetype_mapping.issuetype_to}' (hierarchy: {hierarchy_level}) via issuetype mapping")
                else:
                    logger.warning(f"No issuetype mapping found in database for issuetype '{original_name}' and client {tenant_id}")
            else:
                if not original_name:
                    logger.warning("No issuetype name provided for mapping")
                if not tenant_id:
                    logger.warning("No tenant_id available for issuetype mapping")

            return {
                'external_id': issuetype_data.get('id', None),
                'original_name': original_name,
                'issuetype_mapping_id': issuetype_mapping_id,  # Foreign key relationship to WitMapping
                'description': safe_unicode_string(issuetype_data.get('description', None)),
                'hierarchy_level': hierarchy_level,
                'active': True  # Default to active for new issue types
            }
        except Exception as e:
            logger.error(f"Error processing issue type data for {issuetype_data.get('name', 'unknown')}: {e}")
            return {}
    
    def process_status_data(self, status_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process raw Jira status data into database format with flow step mapping.

        Args:
            status_data: Raw status data from Jira API

        Returns:
            Processed status data ready for database insertion
        """
        try:
            # Helper function to safely handle unicode strings
            def safe_unicode_string(value):
                if value is None:
                    return None
                if isinstance(value, str):
                    # Replace problematic unicode characters that might cause encoding issues
                    return value.encode('utf-8', errors='replace').decode('utf-8')
                return str(value)

            original_name = safe_unicode_string(status_data.get('name', None))
            category = safe_unicode_string(status_data.get('statusCategory', {}).get('name', None))

            # Find status mapping for this status from database
            status_mapping_id = None
            tenant_id = getattr(self.integration, 'tenant_id', None) if self.integration else None

            if original_name and tenant_id:
                # Look up status mapping in database (case-insensitive on both sides)
                status_mapping = self.session.query(StatusMapping).filter(
                    func.lower(StatusMapping.status_from) == original_name.lower(),
                    StatusMapping.tenant_id == tenant_id
                ).first()

                if status_mapping:
                    status_mapping_id = status_mapping.id

                    if status_mapping.workflow:
                        logger.debug(f"Mapped status '{original_name}' to workflow '{status_mapping.workflow.step_name}' via status mapping")
                    else:
                        logger.warning(f"Status mapping found but no workflow linked for status '{original_name}' and client {tenant_id}")
                else:
                    logger.warning(f"No status mapping found in database for status '{original_name}' and client {tenant_id}")
            else:
                if not original_name:
                    logger.warning("No status name provided for mapping")
                if not tenant_id:
                    logger.warning("No tenant_id available for status mapping")

            return {
                'external_id': status_data.get('id', None),
                'original_name': original_name,
                'status_mapping_id': status_mapping_id,  # Foreign key relationship to StatusMapping
                'category': category,
                'description': safe_unicode_string(status_data.get('description', None)),
                'active': True  # Default to active for new statuses
            }
        except Exception as e:
            logger.error(f"Error processing status data for {status_data.get('name', 'unknown')}: {e}")
            return {}

    def process_changelog_data(self, changelog_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process raw Jira changelog data into database format.

        Args:
            changelog_data: Raw changelog data from Jira API

        Returns:
            Processed changelog data ready for database insertion
        """
        try:
            # Extract basic changelog information
            created = self._parse_datetime(changelog_data.get('created'))
            author_data = changelog_data.get('author', {})
            author = author_data.get('displayName') if author_data else None

            # Look for status changes in the items
            items = changelog_data.get('items', [])
            status_change = None

            for item in items:
                if item.get('field') == 'status':
                    status_change = item
                    break

            if not status_change:
                # Not a status change, skip this changelog
                return {}

            return {
                'from_status_id': status_change.get('from'),  # External ID of from status
                'to_status_id': status_change.get('to'),      # External ID of to status
                'changed_at': created,
                'author': author
            }

        except Exception as e:
            logger.error(f"Error processing changelog data for {changelog_data.get('id', 'unknown')}: {e}")
            return {}
