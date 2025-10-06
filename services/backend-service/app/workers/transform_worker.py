"""
Transform Worker for processing raw ETL data.

Consumes messages from transform_queue and processes raw data based on type:
- jira_custom_fields: Process custom fields discovery data
- jira_issues: Process Jira issues data (future)
- github_prs: Process GitHub PRs data (future)
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .base_worker import BaseWorker
from .bulk_operations import BulkOperations
from app.models.unified_models import (
    Project, Wit, CustomField, ProjectWits, Integration
)
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class TransformWorker(BaseWorker):
    """
    Transform worker that processes raw extraction data into final database tables.

    Handles different data types:
    - jira_custom_fields: Creates/updates projects, WITs, custom fields, and relationships

    Supports tenant-specific queues for multi-tenant processing.
    """

    def __init__(self, queue_name: str = 'transform_queue'):
        """
        Initialize transform worker for specified queue.

        Args:
            queue_name: Name of the queue to consume from (default: 'transform_queue')
        """
        super().__init__(queue_name)
    
    def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a transform message based on its type.
        
        Args:
            message: Message containing raw_data_id and type
            
        Returns:
            bool: True if processing succeeded
        """
        try:
            message_type = message.get('type')
            raw_data_id = message.get('raw_data_id')
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            
            if not all([message_type, raw_data_id, tenant_id, integration_id]):
                logger.error(f"Missing required fields in message: {message}")
                return False
            
            logger.info(f"Processing {message_type} message for raw_data_id={raw_data_id}")
            
            # Route to appropriate processor based on type
            if message_type == 'jira_custom_fields':
                return self._process_jira_custom_fields(
                    raw_data_id, tenant_id, integration_id
                )
            else:
                logger.warning(f"Unknown message type: {message_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing transform message: {e}")
            return False
    
    def _process_jira_custom_fields(
        self, 
        raw_data_id: int, 
        tenant_id: int, 
        integration_id: int
    ) -> bool:
        """
        Process Jira custom fields data from createmeta API response.
        
        Creates/updates:
        - Projects
        - Work Item Types (WITs)
        - Custom Fields
        - Project-WIT relationships
        
        Args:
            raw_data_id: ID of raw_extraction_data record
            tenant_id: Tenant ID
            integration_id: Integration ID
            
        Returns:
            bool: True if processing succeeded
        """
        try:
            with self.get_db_session() as session:
                # 1. Get raw data
                raw_data = self._get_raw_data(session, raw_data_id)
                if not raw_data:
                    logger.error(f"Raw data not found: {raw_data_id}")
                    return False
                
                # 2. Parse createmeta response
                # raw_data is already the createmeta response from Jira API
                createmeta_response = raw_data
                projects_data = createmeta_response.get('projects', [])
                
                if not projects_data:
                    logger.warning(f"No projects found in raw data: {raw_data_id}")
                    return True  # Not an error, just empty data
                
                logger.info(f"Processing {len(projects_data)} projects from createmeta")
                
                # 3. Process projects and collect data for bulk operations
                projects_to_insert = []
                projects_to_update = []
                wits_to_insert = []
                wits_to_update = []
                custom_fields_to_insert = []
                custom_fields_to_update = []
                project_wit_relationships = []

                # Get existing data for comparison
                existing_projects = self._get_existing_projects(session, tenant_id, integration_id)
                existing_wits = self._get_existing_wits(session, tenant_id, integration_id)
                existing_custom_fields = self._get_existing_custom_fields(session, tenant_id, integration_id)
                existing_relationships = self._get_existing_project_wit_relationships(session, tenant_id)

                # Collect all unique custom fields globally (not per project)
                global_custom_fields = {}  # field_key -> field_info

                # Process each project
                for project_data in projects_data:
                    project_result = self._process_project_data(
                        project_data, tenant_id, integration_id,
                        existing_projects, existing_wits, existing_custom_fields,
                        existing_relationships, global_custom_fields
                    )

                    if project_result:
                        projects_to_insert.extend(project_result.get('projects_to_insert', []))
                        projects_to_update.extend(project_result.get('projects_to_update', []))
                        wits_to_insert.extend(project_result.get('wits_to_insert', []))
                        wits_to_update.extend(project_result.get('wits_to_update', []))
                        project_wit_relationships.extend(project_result.get('project_wit_relationships', []))

                # Process global custom fields once
                logger.info(f"Processing {len(global_custom_fields)} unique custom fields globally")
                for field_key, field_info in global_custom_fields.items():
                    cf_result = self._process_custom_field_data(
                        field_key, field_info, tenant_id, integration_id,
                        existing_custom_fields
                    )
                    if cf_result:
                        custom_fields_to_insert.extend(cf_result.get('custom_fields_to_insert', []))
                        custom_fields_to_update.extend(cf_result.get('custom_fields_to_update', []))

                logger.info(f"Custom fields to insert: {len(custom_fields_to_insert)}, to update: {len(custom_fields_to_update)}")
                
                # 4. Perform bulk operations
                self._perform_bulk_operations(
                    session, projects_to_insert, projects_to_update,
                    wits_to_insert, wits_to_update,
                    custom_fields_to_insert, custom_fields_to_update,
                    project_wit_relationships
                )
                
                # 5. Update raw data status
                self._update_raw_data_status(session, raw_data_id, 'completed')
                
                session.commit()
                logger.info(f"Successfully processed custom fields for raw_data_id={raw_data_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error processing Jira custom fields: {e}")
            return False
    
    def _get_raw_data(self, session, raw_data_id: int) -> Optional[Dict[str, Any]]:
        """Get raw data from database."""
        try:
            query = text("""
                SELECT raw_data FROM raw_extraction_data 
                WHERE id = :raw_data_id AND status = 'pending'
            """)
            result = session.execute(query, {'raw_data_id': raw_data_id}).fetchone()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting raw data: {e}")
            return None
    
    def _update_raw_data_status(self, session, raw_data_id: int, status: str):
        """Update raw data processing status."""
        try:
            query = text("""
                UPDATE raw_extraction_data
                SET status = :status, last_updated_at = NOW()
                WHERE id = :raw_data_id
            """)
            session.execute(query, {'raw_data_id': raw_data_id, 'status': status})
        except Exception as e:
            logger.error(f"Error updating raw data status: {e}")
            raise

    def _get_existing_projects(self, session, tenant_id: int, integration_id: int) -> Dict[str, Project]:
        """Get existing projects indexed by external_id."""
        projects = session.query(Project).filter(
            Project.tenant_id == tenant_id,
            Project.integration_id == integration_id,
            Project.active == True
        ).all()
        return {p.external_id: p for p in projects if p.external_id}

    def _get_existing_wits(self, session, tenant_id: int, integration_id: int) -> Dict[str, Wit]:
        """Get existing WITs indexed by external_id."""
        wits = session.query(Wit).filter(
            Wit.tenant_id == tenant_id,
            Wit.integration_id == integration_id,
            Wit.active == True
        ).all()
        return {w.external_id: w for w in wits if w.external_id}

    def _get_existing_custom_fields(self, session, tenant_id: int, integration_id: int) -> Dict[str, CustomField]:
        """Get existing custom fields indexed by external_id."""
        custom_fields = session.query(CustomField).filter(
            CustomField.tenant_id == tenant_id,
            CustomField.integration_id == integration_id,
            CustomField.active == True
        ).all()
        return {cf.external_id: cf for cf in custom_fields if cf.external_id}

    def _get_existing_project_wit_relationships(self, session, tenant_id: int) -> set:
        """Get existing project-wit relationships as set of tuples."""
        query = text("""
            SELECT pw.project_id, pw.wit_id
            FROM projects_wits pw
            JOIN projects p ON pw.project_id = p.id
            WHERE p.tenant_id = :tenant_id AND p.active = true
        """)
        result = session.execute(query, {'tenant_id': tenant_id}).fetchall()
        return {(row[0], row[1]) for row in result}

    def _process_project_data(
        self,
        project_data: Dict[str, Any],
        tenant_id: int,
        integration_id: int,
        existing_projects: Dict[str, Project],
        existing_wits: Dict[str, Wit],
        existing_custom_fields: Dict[str, CustomField],
        existing_relationships: set,
        global_custom_fields: Dict[str, Dict[str, Any]]
    ) -> Dict[str, List]:
        """
        Process a single project's data from createmeta response.

        Returns:
            Dict with lists of data to insert/update
        """
        result = {
            'projects_to_insert': [],
            'projects_to_update': [],
            'wits_to_insert': [],
            'wits_to_update': [],
            'project_wit_relationships': []
        }

        try:
            project_external_id = project_data.get('id')
            project_key = project_data.get('key')
            project_name = project_data.get('name')

            if not all([project_external_id, project_key, project_name]):
                logger.warning(f"Incomplete project data: {project_data}")
                return result

            # Process project
            if project_external_id in existing_projects:
                # Check if project needs update
                existing_project = existing_projects[project_external_id]
                if (existing_project.key != project_key or
                    existing_project.name != project_name):
                    result['projects_to_update'].append({
                        'id': existing_project.id,
                        'key': project_key,
                        'name': project_name,
                        'last_updated_at': datetime.now(timezone.utc)
                    })
                project_id = existing_project.id
            else:
                # New project
                project_insert_data = {
                    'external_id': project_external_id,
                    'key': project_key,
                    'name': project_name,
                    'project_type': None,  # Project type not available in createmeta, fetch separately later
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'active': True,
                    'created_at': datetime.now(timezone.utc),
                    'last_updated_at': datetime.now(timezone.utc)
                }
                result['projects_to_insert'].append(project_insert_data)
                project_id = None  # Will be set after insert

            # Process issue types (WITs) and collect unique custom fields per project
            issue_types = project_data.get('issuetypes', [])
            unique_custom_fields = {}  # field_key -> field_info (deduplicated)

            for issue_type in issue_types:
                wit_result = self._process_wit_data(
                    issue_type, tenant_id, integration_id, existing_wits
                )
                if wit_result:
                    result['wits_to_insert'].extend(wit_result.get('wits_to_insert', []))
                    result['wits_to_update'].extend(wit_result.get('wits_to_update', []))

                # Collect custom fields from this issue type (deduplicate by field_key)
                fields = issue_type.get('fields', {})
                for field_key, field_info in fields.items():
                    if field_key.startswith('customfield_'):
                        # Keep the first occurrence of each custom field
                        if field_key not in unique_custom_fields:
                            unique_custom_fields[field_key] = field_info

            # Add unique custom fields from this project to global collection
            for field_key, field_info in unique_custom_fields.items():
                # Keep the first occurrence globally (across all projects)
                if field_key not in global_custom_fields:
                    global_custom_fields[field_key] = field_info

            return result

        except Exception as e:
            logger.error(f"Error processing project data: {e}")
            return result

    def _process_wit_data(
        self,
        issue_type_data: Dict[str, Any],
        tenant_id: int,
        integration_id: int,
        existing_wits: Dict[str, Wit]
    ) -> Dict[str, List]:
        """Process work item type (issue type) data."""
        result = {
            'wits_to_insert': [],
            'wits_to_update': []
        }

        try:
            wit_external_id = issue_type_data.get('id')
            wit_name = issue_type_data.get('name')
            wit_description = issue_type_data.get('description', '')
            hierarchy_level = issue_type_data.get('hierarchyLevel', 0)

            if not all([wit_external_id, wit_name]):
                return result

            if wit_external_id in existing_wits:
                # Check if WIT needs update
                existing_wit = existing_wits[wit_external_id]
                if (existing_wit.original_name != wit_name or
                    existing_wit.description != wit_description or
                    existing_wit.hierarchy_level != hierarchy_level):
                    result['wits_to_update'].append({
                        'id': existing_wit.id,
                        'original_name': wit_name,
                        'description': wit_description,
                        'hierarchy_level': hierarchy_level,
                        'last_updated_at': datetime.now(timezone.utc)
                    })
            else:
                # New WIT
                wit_insert_data = {
                    'external_id': wit_external_id,
                    'original_name': wit_name,
                    'description': wit_description,
                    'hierarchy_level': hierarchy_level,
                    'wits_mapping_id': None,  # Will be set by mapping logic later
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'active': True,
                    'created_at': datetime.now(timezone.utc),
                    'last_updated_at': datetime.now(timezone.utc)
                }
                result['wits_to_insert'].append(wit_insert_data)

            return result

        except Exception as e:
            logger.error(f"Error processing WIT data: {e}")
            return result

    def _process_custom_field_data(
        self,
        field_key: str,
        field_info: Dict[str, Any],
        tenant_id: int,
        integration_id: int,
        existing_custom_fields: Dict[str, CustomField]
    ) -> Dict[str, List]:
        """Process custom field data using new schema (external_id, field_type, no project_id)."""
        result = {
            'custom_fields_to_insert': [],
            'custom_fields_to_update': []
        }

        try:
            field_name = field_info.get('name', '')
            field_schema = field_info.get('schema', {})
            field_type = field_schema.get('type', 'string')
            operations = field_info.get('operations', [])

            if not field_name:
                return result

            if field_key in existing_custom_fields:
                # Check if custom field needs update
                existing_cf = existing_custom_fields[field_key]
                if (existing_cf.name != field_name or
                    existing_cf.field_type != field_type):
                    import json
                    result['custom_fields_to_update'].append({
                        'id': existing_cf.id,
                        'name': field_name,
                        'field_type': field_type,
                        'operations': json.dumps(operations) if operations else '[]',  # Convert to JSON string
                        'last_updated_at': datetime.now(timezone.utc)
                    })
            else:
                # New custom field (global, no project_id)
                import json
                cf_insert_data = {
                    'name': field_name,
                    'external_id': field_key,
                    'field_type': field_type,
                    'operations': json.dumps(operations) if operations else '[]',  # Convert to JSON string
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'active': True,
                    'created_at': datetime.now(timezone.utc),
                    'last_updated_at': datetime.now(timezone.utc)
                }
                result['custom_fields_to_insert'].append(cf_insert_data)

            return result

        except Exception as e:
            logger.error(f"Error processing custom field data: {e}")
            return result

    def _perform_bulk_operations(
        self,
        session,
        projects_to_insert: List[Dict],
        projects_to_update: List[Dict],
        wits_to_insert: List[Dict],
        wits_to_update: List[Dict],
        custom_fields_to_insert: List[Dict],
        custom_fields_to_update: List[Dict],
        project_wit_relationships: List[tuple]
    ):
        """Perform bulk database operations."""
        try:
            # 1. Bulk insert projects first
            if projects_to_insert:
                BulkOperations.bulk_insert(session, 'projects', projects_to_insert)

            # 2. Bulk update projects
            if projects_to_update:
                BulkOperations.bulk_update(session, 'projects', projects_to_update)

            # 3. Bulk insert WITs
            if wits_to_insert:
                BulkOperations.bulk_insert(session, 'wits', wits_to_insert)

            # 4. Bulk update WITs
            if wits_to_update:
                BulkOperations.bulk_update(session, 'wits', wits_to_update)

            # 5. Bulk insert custom fields (global, no project relationship)
            if custom_fields_to_insert:
                BulkOperations.bulk_insert(session, 'custom_fields', custom_fields_to_insert)

            # 6. Bulk update custom fields
            if custom_fields_to_update:
                BulkOperations.bulk_update(session, 'custom_fields', custom_fields_to_update)

            # 7. Bulk insert project-WIT relationships
            if project_wit_relationships:
                BulkOperations.bulk_insert_relationships(session, 'projects_wits', project_wit_relationships)

        except Exception as e:
            logger.error(f"Error in bulk operations: {e}")
            raise


