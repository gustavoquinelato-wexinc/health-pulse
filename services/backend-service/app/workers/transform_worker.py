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


from .base_worker import BaseWorker
from .bulk_operations import BulkOperations
from app.models.unified_models import (
    Project, Wit, CustomField
)
from app.core.logging_config import get_logger
from app.core.database import get_database
from app.etl.queue.queue_manager import QueueManager

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
            elif message_type == 'jira_projects_and_issue_types':
                return self._process_jira_projects_and_issue_types(
                    raw_data_id, tenant_id, integration_id
                )
            elif message_type == 'jira_project_search':
                return self._process_jira_project_search(
                    raw_data_id, tenant_id, integration_id
                )
            elif message_type == 'jira_project_statuses':
                return self._process_jira_statuses_and_project_relationships(
                    raw_data_id, tenant_id, integration_id
                )
            else:
                logger.warning(f"Unknown message type: {message_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing transform message: {e}")
            return False

    def _process_jira_projects_and_issue_types(self, raw_data_id: int, tenant_id: int, integration_id: int) -> bool:
        """
        Process Jira projects and issue types from raw_extraction_data.

        Flow:
        1. Load raw data from raw_extraction_data table
        2. Transform projects data and bulk insert/update projects table
        3. Transform issue types data and bulk insert/update wits table
        4. Create project-issue type relationships in project_wits table
        5. Update processing status
        """
        try:
            logger.info(f"Processing jira_projects_and_issue_types for raw_data_id={raw_data_id}")

            with self.get_db_session() as db:
                # Load raw data
                raw_data_query = text("""
                    SELECT raw_data
                    FROM raw_extraction_data
                    WHERE id = :raw_data_id AND tenant_id = :tenant_id
                """)
                result = db.execute(raw_data_query, {
                    'raw_data_id': raw_data_id,
                    'tenant_id': tenant_id
                }).fetchone()

                if not result:
                    logger.error(f"Raw data {raw_data_id} not found")
                    return False

                raw_data_json = result[0]
                # raw_data is already a dict from JSONB column
                payload = raw_data_json if isinstance(raw_data_json, dict) else json.loads(raw_data_json)
                # Jira API returns 'values' array, not 'projects'
                projects_data = payload.get("values", payload.get("projects", []))

                if not projects_data:
                    logger.warning(f"No projects data found in raw_data_id={raw_data_id}")
                    return True

                logger.info(f"Processing {len(projects_data)} projects")

                # Process projects and issue types
                try:
                    logger.info("Starting _process_projects_data...")
                    projects_processed = self._process_projects_data(
                        db, projects_data, integration_id, tenant_id
                    )
                    logger.info(f"Completed _process_projects_data: {projects_processed} projects processed")
                except Exception as e:
                    logger.error(f"Error in _process_projects_data: {e}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    raise

                try:
                    logger.info("Starting _process_issue_types_data...")
                    issue_types_processed = self._process_issue_types_data(
                        db, projects_data, integration_id, tenant_id
                    )
                    logger.info(f"Completed _process_issue_types_data: {issue_types_processed} issue types processed")
                except Exception as e:
                    print(f"ERROR in _process_issue_types_data: {e}")
                    import traceback
                    print(f"Full traceback: {traceback.format_exc()}")
                    logger.error(f"Error in _process_issue_types_data: {e}")
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    raise

                # Create project-wit relationships using the working approach
                try:
                    logger.info("Creating project-wit relationships from createmeta data...")

                    # Extract relationships from createmeta structure
                    project_wit_relationships = []
                    for project in projects_data:
                        project_external_id = project.get('id')
                        # createmeta uses 'issuetypes' (lowercase)
                        issue_types = project.get('issuetypes', [])

                        for issue_type in issue_types:
                            wit_external_id = issue_type.get('id')
                            if project_external_id and wit_external_id:
                                project_wit_relationships.append((project_external_id, wit_external_id))

                    logger.info(f"Extracted {len(project_wit_relationships)} relationships from createmeta data")

                    if project_wit_relationships:
                        relationships_created = self._create_project_wit_relationships_for_search(
                            db, project_wit_relationships, integration_id, tenant_id
                        )
                        logger.info(f"Created {relationships_created} project-wit relationships")
                    else:
                        relationships_created = 0
                        logger.warning("No project-wit relationships found in createmeta data")

                except Exception as e:
                    print(f"ERROR in project-wit relationships creation: {e}")
                    import traceback
                    print(f"Full traceback: {traceback.format_exc()}")
                    logger.error(f"Error in project-wit relationships creation: {e}")
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    # Don't raise - let the job continue
                    relationships_created = 0

                # Update processing status
                update_query = text("""
                    UPDATE raw_extraction_data
                    SET status = 'completed',
                        last_updated_at = NOW(),
                        error_details = NULL
                    WHERE id = :raw_data_id
                """)
                db.execute(update_query, {'raw_data_id': raw_data_id})
                db.commit()

                logger.info(f"Successfully processed projects and issue types: "
                          f"{projects_processed} projects, {issue_types_processed} issue types, "
                          f"{relationships_created} relationships")

                return True

        except Exception as e:
            logger.error(f"Error processing jira_projects_and_issue_types: {e}")

            # Update error status
            try:
                with self.get_db_session() as db:
                    error_query = text("""
                        UPDATE raw_extraction_data
                        SET status = 'failed',
                            error_details = :error_details
                        WHERE id = :raw_data_id
                    """)
                    db.execute(error_query, {
                        'raw_data_id': raw_data_id,
                        'error_details': json.dumps({'error': str(e)})
                    })
                    db.commit()
            except Exception as update_error:
                logger.error(f"Failed to update error status: {update_error}")

            return False

    def _process_projects_data(self, db, projects_data: List[Dict], integration_id: int, tenant_id: int) -> int:
        """Process and bulk insert/update projects."""
        try:
            projects_to_insert = []
            projects_to_update = []

            # Get existing projects
            existing_query = text("""
                SELECT external_id, id, name, key, project_type
                FROM projects
                WHERE integration_id = :integration_id AND tenant_id = :tenant_id
            """)
            existing_results = db.execute(existing_query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id
            }).fetchall()

            existing_projects = {row[0]: row for row in existing_results}

            for project in projects_data:
                external_id = project.get('id')
                key = project.get('key')
                name = project.get('name', '')
                project_type = project.get('projectTypeKey', 'software')

                if external_id in existing_projects:
                    # Update existing project
                    existing = existing_projects[external_id]
                    # existing: (external_id, id, name, key, project_type)
                    if (existing[2] != name or existing[3] != key or existing[4] != project_type):
                        projects_to_update.append({
                            'id': existing[1],
                            'name': name,
                            'key': key,
                            'project_type': project_type
                        })
                else:
                    # Insert new project
                    projects_to_insert.append({
                        'external_id': external_id,
                        'key': key,
                        'name': name,
                        'project_type': project_type,
                        'integration_id': integration_id,
                        'tenant_id': tenant_id
                    })

            # Bulk insert new projects
            if projects_to_insert:
                insert_query = text("""
                    INSERT INTO projects (
                        external_id, key, name, project_type,
                        integration_id, tenant_id, active, created_at, last_updated_at
                    ) VALUES (
                        :external_id, :key, :name, :project_type,
                        :integration_id, :tenant_id, TRUE, NOW(), NOW()
                    )
                """)
                db.execute(insert_query, projects_to_insert)
                logger.info(f"Inserted {len(projects_to_insert)} new projects")

            # Bulk update existing projects
            if projects_to_update:
                update_query = text("""
                    UPDATE projects
                    SET name = :name, key = :key, project_type = :project_type,
                        last_updated_at = NOW()
                    WHERE id = :id
                """)
                db.execute(update_query, projects_to_update)
                logger.info(f"Updated {len(projects_to_update)} existing projects")

            return len(projects_to_insert) + len(projects_to_update)

        except Exception as e:
            logger.error(f"Error processing projects data: {e}")
            raise

    def _process_issue_types_data(self, db, projects_data: List[Dict], integration_id: int, tenant_id: int) -> int:
        """Process and bulk insert/update issue types (wits) with mapping links."""
        try:
            issue_types_to_insert = []
            issue_types_to_update = []

            # Get existing issue types
            existing_query = text("""
                SELECT external_id, id, original_name, description, hierarchy_level, wits_mapping_id
                FROM wits
                WHERE integration_id = :integration_id AND tenant_id = :tenant_id
            """)
            existing_results = db.execute(existing_query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id
            }).fetchall()

            existing_wits = {row[0]: row for row in existing_results}

            # Get existing wits mappings for linking
            mappings_query = text("""
                SELECT id, wit_from, wit_to
                FROM wits_mappings
                WHERE integration_id = :integration_id AND tenant_id = :tenant_id AND active = TRUE
            """)
            mappings_results = db.execute(mappings_query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id
            }).fetchall()

            # Create mapping lookup: original_name -> mapping_id
            wits_mapping_lookup = {row[1]: row[0] for row in mappings_results}
            logger.info(f"Found {len(wits_mapping_lookup)} wits mappings: {list(wits_mapping_lookup.keys())}")

            # Extract unique issue types from all projects
            # Handle both createmeta API (issuetypes) and project search API (issueTypes)
            unique_issue_types = {}
            for project in projects_data:
                # Try both camelCase (project search API) and lowercase (createmeta API)
                issue_types = project.get('issueTypes', project.get('issuetypes', []))
                for issue_type in issue_types:
                    external_id = issue_type.get('id')
                    if external_id and external_id not in unique_issue_types:
                        unique_issue_types[external_id] = issue_type

            for external_id, issue_type in unique_issue_types.items():
                original_name = issue_type.get('name', '')
                description = issue_type.get('description', '')
                hierarchy_level = issue_type.get('hierarchyLevel', 0)

                # Find matching wits mapping
                wits_mapping_id = wits_mapping_lookup.get(original_name)
                if wits_mapping_id:
                    logger.debug(f"Found mapping for '{original_name}' -> mapping_id {wits_mapping_id}")
                else:
                    logger.debug(f"No mapping found for issue type '{original_name}' - will use default processing")

                if external_id in existing_wits:
                    # Update existing issue type
                    existing = existing_wits[external_id]
                    # existing: (external_id, id, original_name, description, hierarchy_level, wits_mapping_id)
                    if (existing[2] != original_name or existing[3] != description or
                        existing[4] != hierarchy_level or existing[5] != wits_mapping_id):
                        issue_types_to_update.append({
                            'id': existing[1],
                            'original_name': original_name,
                            'description': description,
                            'hierarchy_level': hierarchy_level,
                            'wits_mapping_id': wits_mapping_id
                        })
                else:
                    # Insert new issue type
                    issue_types_to_insert.append({
                        'external_id': external_id,
                        'original_name': original_name,
                        'description': description,
                        'hierarchy_level': hierarchy_level,
                        'wits_mapping_id': wits_mapping_id,
                        'integration_id': integration_id,
                        'tenant_id': tenant_id
                    })

            # Bulk insert new issue types
            if issue_types_to_insert:
                insert_query = text("""
                    INSERT INTO wits (
                        external_id, original_name, description, hierarchy_level, wits_mapping_id,
                        integration_id, tenant_id, active, created_at, last_updated_at
                    ) VALUES (
                        :external_id, :original_name, :description, :hierarchy_level, :wits_mapping_id,
                        :integration_id, :tenant_id, TRUE, NOW(), NOW()
                    )
                """)
                db.execute(insert_query, issue_types_to_insert)
                logger.info(f"Inserted {len(issue_types_to_insert)} new issue types with mapping links")

            # Bulk update existing issue types
            if issue_types_to_update:
                update_query = text("""
                    UPDATE wits
                    SET original_name = :original_name, description = :description,
                        hierarchy_level = :hierarchy_level, wits_mapping_id = :wits_mapping_id,
                        last_updated_at = NOW()
                    WHERE id = :id
                """)
                db.execute(update_query, issue_types_to_update)
                logger.info(f"Updated {len(issue_types_to_update)} existing issue types with mapping links")

            return len(issue_types_to_insert) + len(issue_types_to_update)

        except Exception as e:
            logger.error(f"Error processing issue types data: {e}")
            raise


    
    def _process_jira_project_search(self, raw_data_id: int, tenant_id: int, integration_id: int) -> bool:
        """
        Process Jira projects and issue types from project/search API endpoint.

        This handles data from /rest/api/3/project/search which returns:
        {"values": [...]} with "issueTypes" (camelCase)

        Args:
            raw_data_id: ID of the raw data record
            tenant_id: Tenant ID
            integration_id: Integration ID

        Returns:
            bool: True if processing was successful
        """
        try:
            logger.info(f"Processing Jira project search data for raw_data_id={raw_data_id}")

            database = get_database()
            with database.get_session_context() as session:
                # 1. Load raw data
                result = session.execute(text(
                    'SELECT raw_data FROM raw_extraction_data WHERE id = :raw_data_id'
                ), {'raw_data_id': raw_data_id}).fetchone()

                if not result:
                    logger.error(f"No raw data found for raw_data_id={raw_data_id}")
                    return False

                raw_data_json = result[0]
                payload = raw_data_json if isinstance(raw_data_json, dict) else json.loads(raw_data_json)

                # Project search API returns 'values' array, not 'projects'
                projects_data = payload.get("values", [])

                if not projects_data:
                    logger.warning(f"No projects data found in raw_data_id={raw_data_id}")
                    return False

                logger.info(f"Processing {len(projects_data)} projects from project/search API")

                # 2. Process the data using the same logic but with correct field names
                result = self._process_project_search_data(
                    session, projects_data, integration_id, tenant_id
                )

                # 3. Bulk operations for database efficiency
                if result['projects_to_insert']:
                    bulk_ops = BulkOperations()
                    bulk_ops.bulk_insert(session, 'projects', result['projects_to_insert'])
                    logger.info(f"Inserted {len(result['projects_to_insert'])} new projects")
                    # Queue for vectorization
                    self._queue_entities_for_vectorization(tenant_id, 'projects', result['projects_to_insert'])

                if result['projects_to_update']:
                    bulk_ops = BulkOperations()
                    bulk_ops.bulk_update(session, 'projects', result['projects_to_update'])
                    logger.info(f"Updated {len(result['projects_to_update'])} projects")
                    # Queue for vectorization
                    self._queue_entities_for_vectorization(tenant_id, 'projects', result['projects_to_update'])

                if result['wits_to_insert']:
                    bulk_ops = BulkOperations()
                    bulk_ops.bulk_insert(session, 'wits', result['wits_to_insert'])
                    logger.info(f"Inserted {len(result['wits_to_insert'])} new WITs")
                    # Queue for vectorization
                    self._queue_entities_for_vectorization(tenant_id, 'wits', result['wits_to_insert'])

                if result['wits_to_update']:
                    bulk_ops = BulkOperations()
                    bulk_ops.bulk_update(session, 'wits', result['wits_to_update'])
                    logger.info(f"Updated {len(result['wits_to_update'])} WITs")
                    # Queue for vectorization
                    self._queue_entities_for_vectorization(tenant_id, 'wits', result['wits_to_update'])

                # 4. Create project-wit relationships
                if result['project_wit_relationships']:
                    logger.info(f"Creating {len(result['project_wit_relationships'])} project-wit relationships")
                    relationships_created = self._create_project_wit_relationships_for_search(
                        session, result['project_wit_relationships'], integration_id, tenant_id
                    )
                    logger.info(f"Created {relationships_created} project-wit relationships")

                # 5. Mark raw data as completed
                session.execute(text(
                    'UPDATE raw_extraction_data SET status = :status WHERE id = :raw_data_id'
                ), {'status': 'completed', 'raw_data_id': raw_data_id})

                session.commit()
                logger.info(f"Successfully processed Jira project search data for raw_data_id={raw_data_id}")
                return True

        except Exception as e:
            logger.error(f"Error processing Jira project search data: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    def _process_project_search_data(
        self,
        session,
        projects_data: List[Dict],
        integration_id: int,
        tenant_id: int
    ) -> Dict[str, List]:
        """
        Process projects data from project/search API endpoint.

        This handles the 'values' array with 'issueTypes' (camelCase) structure.
        """
        result = {
            'projects_to_insert': [],
            'projects_to_update': [],
            'wits_to_insert': [],
            'wits_to_update': [],
            'project_wit_relationships': []
        }

        # Get existing data
        existing_projects = {
            p.external_id: p for p in session.query(Project).filter(
                Project.tenant_id == tenant_id,
                Project.integration_id == integration_id,
                Project.active == True
            ).all()
        }

        existing_wits = {
            w.external_id: w for w in session.query(Wit).filter(
                Wit.tenant_id == tenant_id,
                Wit.integration_id == integration_id,
                Wit.active == True
            ).all()
        }

        # Process each project
        for project_data in projects_data:
            project_external_id = project_data.get('id')
            project_key = project_data.get('key')
            project_name = project_data.get('name')

            if not project_external_id:
                logger.warning(f"Skipping project without external_id: {project_data}")
                continue

            # Process project
            if project_external_id in existing_projects:
                # Update existing project
                existing_project = existing_projects[project_external_id]
                result['projects_to_update'].append({
                    'id': existing_project.id,
                    'key': project_key,
                    'name': project_name,
                    'last_updated_at': datetime.now(timezone.utc)
                })
            else:
                # New project
                result['projects_to_insert'].append({
                    'external_id': project_external_id,
                    'key': project_key,
                    'name': project_name,
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'active': True,
                    'created_at': datetime.now(timezone.utc),
                    'last_updated_at': datetime.now(timezone.utc)
                })

            # Process issue types (WITs) - note: issueTypes (camelCase) for project/search API
            issue_types = project_data.get('issueTypes', [])
            project_wit_external_ids = []

            for issue_type in issue_types:
                wit_external_id = issue_type.get('id')
                wit_name = issue_type.get('name')
                wit_description = issue_type.get('description', '')
                hierarchy_level = issue_type.get('hierarchyLevel', 0)

                if not wit_external_id:
                    logger.warning(f"Skipping issue type without external_id: {issue_type}")
                    continue

                project_wit_external_ids.append(wit_external_id)

                if wit_external_id in existing_wits:
                    # Update existing WIT
                    existing_wit = existing_wits[wit_external_id]
                    result['wits_to_update'].append({
                        'id': existing_wit.id,
                        'original_name': wit_name,
                        'description': wit_description,
                        'hierarchy_level': hierarchy_level,
                        'last_updated_at': datetime.now(timezone.utc)
                    })
                else:
                    # New WIT
                    result['wits_to_insert'].append({
                        'external_id': wit_external_id,
                        'original_name': wit_name,
                        'description': wit_description,
                        'hierarchy_level': hierarchy_level,
                        'tenant_id': tenant_id,
                        'integration_id': integration_id,
                        'active': True,
                        'created_at': datetime.now(timezone.utc),
                        'last_updated_at': datetime.now(timezone.utc)
                    })

            # Create project-wit relationships
            for wit_external_id in project_wit_external_ids:
                relationship = (project_external_id, wit_external_id)
                result['project_wit_relationships'].append(relationship)

        return result

    def _create_project_wit_relationships_for_search(
        self,
        session,
        project_wit_relationships: List[tuple],
        integration_id: int,
        tenant_id: int
    ) -> int:
        """
        Create project-wit relationships for project/search API data.
        """
        try:
            # Get project and wit mappings
            projects = session.query(Project).filter(
                Project.tenant_id == tenant_id,
                Project.integration_id == integration_id,
                Project.active == True
            ).all()
            projects_dict = {p.external_id: p.id for p in projects}

            wits = session.query(Wit).filter(
                Wit.tenant_id == tenant_id,
                Wit.integration_id == integration_id,
                Wit.active == True
            ).all()
            wits_dict = {w.external_id: w.id for w in wits}

            # Convert external IDs to database IDs
            actual_relationships = []
            for relationship in project_wit_relationships:
                try:
                    if len(relationship) >= 2:
                        project_external_id = relationship[0]
                        wit_external_id = relationship[1]

                        project_id = projects_dict.get(project_external_id)
                        wit_id = wits_dict.get(wit_external_id)

                        if project_id and wit_id:
                            actual_relationships.append((project_id, wit_id))
                        else:
                            logger.warning(f"Missing project or wit for relationship: {project_external_id} -> {wit_external_id}")
                    else:
                        logger.warning(f"Skipping malformed relationship: {relationship}")
                except Exception as e:
                    logger.warning(f"Error processing relationship {relationship}: {e}")
                    continue

            # Insert relationships using simple SQL
            relationships_created = 0
            for project_id, wit_id in actual_relationships:
                try:
                    session.execute(text("""
                        INSERT INTO projects_wits (project_id, wit_id)
                        VALUES (:project_id, :wit_id)
                        ON CONFLICT (project_id, wit_id) DO NOTHING
                    """), {'project_id': project_id, 'wit_id': wit_id})
                    relationships_created += 1
                except Exception as e:
                    logger.warning(f"Error inserting relationship ({project_id}, {wit_id}): {e}")

            return relationships_created

        except Exception as e:
            logger.error(f"Error creating project-wit relationships: {e}")
            return 0

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
                # Jira API returns 'values' array, not 'projects'
                projects_data = createmeta_response.get('values', createmeta_response.get('projects', []))

                if not projects_data:
                    logger.warning(f"No projects found in raw data: {raw_data_id}")
                    return True  # Not an error, just empty data

                logger.info(f"🔍 DEBUG: Processing {len(projects_data)} projects from createmeta")

                # Debug: Count total issue types and relationships
                total_issue_types = 0
                total_relationships = 0
                unique_issue_types = set()
                for project in projects_data:
                    # Handle both camelCase (project search API) and lowercase (createmeta API)
                    issue_types = project.get('issueTypes', project.get('issuetypes', []))
                    total_issue_types += len(issue_types)
                    total_relationships += len(issue_types)
                    for it in issue_types:
                        unique_issue_types.add(it.get('id'))

                logger.info(f"🔍 DEBUG: Found {len(unique_issue_types)} unique issue types across all projects")
                logger.info(f"🔍 DEBUG: Expected {total_relationships} project-wit relationships")
                logger.info(f"🔍 DEBUG: Unique issue type IDs: {sorted(unique_issue_types)}")
                
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

                logger.info(f"🔍 DEBUG: Found {len(existing_projects)} existing projects")
                logger.info(f"🔍 DEBUG: Found {len(existing_wits)} existing WITs: {list(existing_wits.keys())}")
                logger.info(f"🔍 DEBUG: Found {len(existing_custom_fields)} existing custom fields")
                logger.info(f"🔍 DEBUG: Found {len(existing_relationships)} existing relationships")

                # Collect all unique custom fields globally (not per project)
                global_custom_fields = {}  # field_key -> field_info

                # Process each project
                logger.info(f"🔍 DEBUG: Starting to process {len(projects_data)} projects individually...")
                for i, project_data in enumerate(projects_data):
                    project_key = project_data.get('key', 'UNKNOWN')
                    project_name = project_data.get('name', 'UNKNOWN')
                    # Handle both camelCase (project search API) and lowercase (createmeta API)
                    issue_types_count = len(project_data.get('issueTypes', project_data.get('issuetypes', [])))

                    logger.info(f"🔍 DEBUG: Processing project {i+1}/{len(projects_data)}: {project_key} ({project_name}) with {issue_types_count} issue types")

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

                        logger.info(f"🔍 DEBUG: After processing {project_key}: Total WITs to insert: {len(wits_to_insert)}, relationships: {len(project_wit_relationships)}")
                    else:
                        logger.warning(f"🔍 DEBUG: No result returned for project {project_key}")

                logger.info(f"🔍 DEBUG: Final totals after all projects:")
                logger.info(f"🔍 DEBUG:   - Projects to insert: {len(projects_to_insert)}")
                logger.info(f"🔍 DEBUG:   - Projects to update: {len(projects_to_update)}")
                logger.info(f"🔍 DEBUG:   - WITs to insert (before dedup): {len(wits_to_insert)}")
                logger.info(f"🔍 DEBUG:   - WITs to update: {len(wits_to_update)}")
                logger.info(f"🔍 DEBUG:   - Project-wit relationships: {len(project_wit_relationships)}")

                # 🔧 FIX: Deduplicate WITs globally by external_id
                # The same WIT (e.g., "Story" with id "10001") appears in multiple projects
                # We should only insert each unique WIT once
                unique_wits_to_insert = {}
                for wit in wits_to_insert:
                    external_id = wit.get('external_id')
                    if external_id and external_id not in unique_wits_to_insert:
                        unique_wits_to_insert[external_id] = wit

                wits_to_insert = list(unique_wits_to_insert.values())

                logger.info(f"🔍 DEBUG: After WIT deduplication:")
                logger.info(f"🔍 DEBUG:   - Unique WITs to insert: {len(wits_to_insert)}")
                logger.info(f"🔍 DEBUG:   - WIT external IDs: {list(unique_wits_to_insert.keys())}")

                # Show WIT names for debugging
                for wit in wits_to_insert:
                    logger.info(f"🔍 DEBUG:   - WIT to insert: {wit.get('original_name')} (id: {wit.get('external_id')})")

                # Also deduplicate WITs to update
                unique_wits_to_update = {}
                for wit in wits_to_update:
                    wit_id = wit.get('id')  # Database ID for updates
                    if wit_id and wit_id not in unique_wits_to_update:
                        unique_wits_to_update[wit_id] = wit

                wits_to_update = list(unique_wits_to_update.values())
                logger.info(f"🔍 DEBUG:   - Unique WITs to update: {len(wits_to_update)}")

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
                
                # 4. Perform bulk operations (projects and WITs first)
                self._perform_bulk_operations(
                    session, projects_to_insert, projects_to_update,
                    wits_to_insert, wits_to_update,
                    custom_fields_to_insert, custom_fields_to_update,
                    []  # Empty relationships for now
                )

                # 5. Create project-wit relationships after projects and WITs are saved
                if project_wit_relationships:
                    logger.info(f"Creating {len(project_wit_relationships)} project-wit relationships")
                    relationships_created = self._create_project_wit_relationships_for_search(
                        session, project_wit_relationships, integration_id, tenant_id
                    )
                    logger.info(f"Created {relationships_created} project-wit relationships")


                
                # 6. Update raw data status
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
            Dict with lists of data to insert/update and project-wit relationships to create
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
            # Handle both camelCase (project search API) and lowercase (createmeta API)
            issue_types = project_data.get('issueTypes', project_data.get('issuetypes', []))

            logger.info(f"🔍 DEBUG: _process_project_data - Processing {project_key} ({project_name}) with {len(issue_types)} issue types")

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
            # Handle both camelCase (project search API) and lowercase (createmeta API)
            issue_types = project_data.get('issueTypes', project_data.get('issuetypes', []))
            unique_custom_fields = {}  # field_key -> field_info (deduplicated)
            project_wit_external_ids = []  # Store WIT external IDs for this project

            logger.info(f"🔍 DEBUG: Processing {len(issue_types)} issue types for project {project_key}")

            for i, issue_type in enumerate(issue_types):
                wit_external_id = issue_type.get('id')
                wit_name = issue_type.get('name', 'UNKNOWN')

                logger.info(f"🔍 DEBUG: Processing issue type {i+1}/{len(issue_types)}: {wit_name} (id: {wit_external_id})")

                if wit_external_id:
                    project_wit_external_ids.append(wit_external_id)
                    logger.info(f"🔍 DEBUG: Added WIT external ID {wit_external_id} to project {project_key}")

                wit_result = self._process_wit_data(
                    issue_type, tenant_id, integration_id, existing_wits
                )
                if wit_result:
                    wits_to_insert = wit_result.get('wits_to_insert', [])
                    wits_to_update = wit_result.get('wits_to_update', [])

                    logger.info(f"🔍 DEBUG: WIT result for {wit_name}: {len(wits_to_insert)} to insert, {len(wits_to_update)} to update")

                    result['wits_to_insert'].extend(wits_to_insert)
                    result['wits_to_update'].extend(wits_to_update)
                else:
                    logger.warning(f"🔍 DEBUG: No WIT result for {wit_name} (id: {wit_external_id})")

                # Collect custom fields from this issue type (deduplicate by field_key)
                fields = issue_type.get('fields', {})
                for field_key, field_info in fields.items():
                    if field_key.startswith('customfield_'):
                        # Keep the first occurrence of each custom field
                        if field_key not in unique_custom_fields:
                            unique_custom_fields[field_key] = field_info

            # Store project-wit relationships for later processing (after WITs are saved)
            # We'll store as (project_external_id, wit_external_id) tuples
            logger.info(f"🔍 DEBUG: Creating {len(project_wit_external_ids)} project-wit relationships for project {project_key}")
            logger.info(f"🔍 DEBUG: WIT external IDs for {project_key}: {project_wit_external_ids}")

            for wit_external_id in project_wit_external_ids:
                relationship = (project_external_id, wit_external_id)
                result['project_wit_relationships'].append(relationship)
                logger.info(f"🔍 DEBUG: Added relationship: project {project_external_id} -> wit {wit_external_id}")

            # Add unique custom fields from this project to global collection
            for field_key, field_info in unique_custom_fields.items():
                # Keep the first occurrence globally (across all projects)
                if field_key not in global_custom_fields:
                    global_custom_fields[field_key] = field_info

            logger.info(f"🔍 DEBUG: Project {project_key} summary:")
            logger.info(f"🔍 DEBUG:   - WITs to insert: {len(result['wits_to_insert'])}")
            logger.info(f"🔍 DEBUG:   - WITs to update: {len(result['wits_to_update'])}")
            logger.info(f"🔍 DEBUG:   - Project-wit relationships: {len(result['project_wit_relationships'])}")
            logger.info(f"🔍 DEBUG:   - Unique custom fields: {len(unique_custom_fields)}")
            logger.info(f"🔍 DEBUG:   - Relationship details: {result['project_wit_relationships']}")

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

            logger.info(f"🔍 DEBUG: _process_wit_data - Processing WIT: {wit_name} (id: {wit_external_id})")

            if not all([wit_external_id, wit_name]):
                logger.warning(f"🔍 DEBUG: Incomplete WIT data: external_id={wit_external_id}, name={wit_name}")
                return result

            if wit_external_id in existing_wits:
                # Check if WIT needs update
                existing_wit = existing_wits[wit_external_id]
                logger.info(f"🔍 DEBUG: WIT {wit_name} already exists, checking for updates...")

                if (existing_wit.original_name != wit_name or
                    existing_wit.description != wit_description or
                    existing_wit.hierarchy_level != hierarchy_level):
                    logger.info(f"🔍 DEBUG: WIT {wit_name} needs update")
                    result['wits_to_update'].append({
                        'id': existing_wit.id,
                        'original_name': wit_name,
                        'description': wit_description,
                        'hierarchy_level': hierarchy_level,
                        'last_updated_at': datetime.now(timezone.utc)
                    })
                else:
                    logger.info(f"🔍 DEBUG: WIT {wit_name} is up to date, no update needed")
            else:
                # New WIT
                logger.info(f"🔍 DEBUG: WIT {wit_name} is new, adding to insert list")
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
                # Queue for vectorization
                self._queue_entities_for_vectorization(tenant_id, 'projects', projects_to_insert)

            # 2. Bulk update projects
            if projects_to_update:
                BulkOperations.bulk_update(session, 'projects', projects_to_update)
                # Queue for vectorization
                self._queue_entities_for_vectorization(tenant_id, 'projects', projects_to_update)

            # 3. Bulk insert WITs
            if wits_to_insert:
                BulkOperations.bulk_insert(session, 'wits', wits_to_insert)
                # Queue for vectorization
                self._queue_entities_for_vectorization(tenant_id, 'wits', wits_to_insert)

            # 4. Bulk update WITs
            if wits_to_update:
                BulkOperations.bulk_update(session, 'wits', wits_to_update)
                # Queue for vectorization
                self._queue_entities_for_vectorization(tenant_id, 'wits', wits_to_update)

            # 5. Bulk insert custom fields (global, no project relationship)
            if custom_fields_to_insert:
                BulkOperations.bulk_insert(session, 'custom_fields', custom_fields_to_insert)
                # Note: Custom fields are not vectorized (they're metadata)

            # 6. Bulk update custom fields
            if custom_fields_to_update:
                BulkOperations.bulk_update(session, 'custom_fields', custom_fields_to_update)
                # Note: Custom fields are not vectorized (they're metadata)

            # 7. Project-WIT relationships are handled separately using _create_project_wit_relationships_for_search
            # This ensures proper error handling and data validation

        except Exception as e:
            logger.error(f"Error in bulk operations: {e}")
            raise

    def _process_jira_statuses_and_project_relationships(self, raw_data_id: int, tenant_id: int, integration_id: int) -> bool:
        """
        Process statuses and project relationships from raw data.

        This function:
        1. Retrieves raw data from raw_extraction_data table
        2. Processes statuses and saves to statuses table with mapping links
        3. Processes project-status relationships and saves to projects_statuses table
        4. Returns success status
        """
        try:
            with self.get_db_session() as db:
                # Load raw data
                raw_data_query = text("""
                    SELECT raw_data
                    FROM raw_extraction_data
                    WHERE id = :raw_data_id AND tenant_id = :tenant_id
                """)
                result = db.execute(raw_data_query, {'raw_data_id': raw_data_id, 'tenant_id': tenant_id}).fetchone()

                if not result:
                    logger.error(f"No raw data found for id {raw_data_id}")
                    return False

                raw_data_json = result[0]
                payload = raw_data_json if isinstance(raw_data_json, dict) else json.loads(raw_data_json)

                # Handle both old consolidated format and new individual project format
                if "project_key" in payload:
                    # New individual project format: {'project_key': 'BEN', 'statuses': [...]}
                    project_key = payload.get("project_key")
                    project_statuses_response = payload.get("statuses", [])

                    logger.info(f"Processing individual project {project_key} with {len(project_statuses_response)} issue types")

                    # Extract unique statuses from this project
                    unique_statuses = {}
                    project_relationships = []

                    for issuetype_data in project_statuses_response:
                        for status_data in issuetype_data.get('statuses', []):
                            status_external_id = status_data.get('id')
                            if status_external_id:
                                # Collect unique statuses
                                if status_external_id not in unique_statuses:
                                    unique_statuses[status_external_id] = status_data

                                # Create project-status relationship
                                project_relationships.append({
                                    'project_key': project_key,
                                    'status_id': status_external_id,
                                    'status_name': status_data.get('name'),
                                    'issue_type_id': issuetype_data.get('id'),
                                    'issue_type_name': issuetype_data.get('name')
                                })

                    statuses_data = list(unique_statuses.values())
                    project_statuses_data = project_relationships

                else:
                    # Old consolidated format: {'statuses': [...], 'project_statuses': [...]}
                    statuses_data = payload.get("statuses", [])
                    project_statuses_data = payload.get("project_statuses", [])

                logger.info(f"Processing {len(statuses_data)} statuses and {len(project_statuses_data)} project relationships")

                # Process statuses and project relationships
                statuses_processed = self._process_statuses_data(db, statuses_data, integration_id, tenant_id)
                relationships_processed = self._process_project_status_relationships_data(db, project_statuses_data, integration_id, tenant_id)

                # Update raw data status to completed
                update_query = text("""
                    UPDATE raw_extraction_data
                    SET status = 'completed',
                        last_updated_at = NOW(),
                        error_details = NULL
                    WHERE id = :raw_data_id
                """)
                db.execute(update_query, {'raw_data_id': raw_data_id})

                # Commit all changes
                db.commit()

                logger.info(f"Successfully processed {statuses_processed} statuses and {relationships_processed} project relationships")
                return True

        except Exception as e:
            logger.error(f"Error processing statuses and project relationships: {e}")
            return False

    def _process_statuses_data(self, db, statuses_data: List[Dict], integration_id: int, tenant_id: int) -> int:
        """Process and bulk insert/update statuses."""
        try:
            statuses_to_insert = []
            statuses_to_update = []

            # Get existing statuses
            existing_query = text("""
                SELECT external_id, id, original_name, category, description, status_mapping_id
                FROM statuses
                WHERE integration_id = :integration_id AND tenant_id = :tenant_id
            """)
            existing_results = db.execute(existing_query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id
            }).fetchall()

            existing_statuses = {row[0]: row for row in existing_results}

            # Get existing status mappings for linking
            mappings_query = text("""
                SELECT id, status_from, status_to
                FROM statuses_mappings
                WHERE integration_id = :integration_id AND tenant_id = :tenant_id AND active = TRUE
            """)
            mappings_results = db.execute(mappings_query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id
            }).fetchall()

            # Create mapping lookup: original_name -> mapping_id
            status_mapping_lookup = {row[1]: row[0] for row in mappings_results}
            logger.info(f"Found {len(status_mapping_lookup)} status mappings: {list(status_mapping_lookup.keys())}")

            # Process each status
            for status_data in statuses_data:
                external_id = status_data.get('id')
                original_name = status_data.get('name', '')
                description = status_data.get('description', '')
                category = status_data.get('statusCategory', {}).get('name', '')

                # Find matching status mapping
                status_mapping_id = status_mapping_lookup.get(original_name)
                if status_mapping_id:
                    logger.debug(f"Found mapping for '{original_name}' -> mapping_id {status_mapping_id}")
                else:
                    logger.debug(f"No mapping found for status '{original_name}' (this is normal for unmapped statuses)")

                if external_id in existing_statuses:
                    # Update existing status
                    existing = existing_statuses[external_id]
                    # existing: (external_id, id, original_name, category, description, status_mapping_id)
                    if (existing[2] != original_name or existing[3] != category or
                        existing[4] != description or existing[5] != status_mapping_id):
                        statuses_to_update.append({
                            'id': existing[1],
                            'original_name': original_name,
                            'category': category,
                            'description': description,
                            'status_mapping_id': status_mapping_id
                        })
                else:
                    # Insert new status
                    statuses_to_insert.append({
                        'external_id': external_id,
                        'original_name': original_name,
                        'category': category,
                        'description': description,
                        'status_mapping_id': status_mapping_id,
                        'integration_id': integration_id,
                        'tenant_id': tenant_id
                    })

            # Bulk insert new statuses
            if statuses_to_insert:
                insert_query = text("""
                    INSERT INTO statuses (
                        external_id, original_name, category, description, status_mapping_id,
                        integration_id, tenant_id, active, created_at, last_updated_at
                    ) VALUES (
                        :external_id, :original_name, :category, :description, :status_mapping_id,
                        :integration_id, :tenant_id, TRUE, NOW(), NOW()
                    )
                """)
                db.execute(insert_query, statuses_to_insert)
                logger.info(f"Inserted {len(statuses_to_insert)} new statuses with mapping links")

            # Bulk update existing statuses
            if statuses_to_update:
                update_query = text("""
                    UPDATE statuses
                    SET original_name = :original_name, category = :category,
                        description = :description, status_mapping_id = :status_mapping_id,
                        last_updated_at = NOW()
                    WHERE id = :id
                """)
                db.execute(update_query, statuses_to_update)
                logger.info(f"Updated {len(statuses_to_update)} existing statuses with mapping links")

            return len(statuses_to_insert) + len(statuses_to_update)

        except Exception as e:
            logger.error(f"Error processing statuses data: {e}")
            raise

    def _process_project_status_relationships_data(self, db, project_statuses_data: List[Dict], integration_id: int, tenant_id: int) -> int:
        """Process and bulk insert/update project-status relationships."""
        try:
            relationships_to_insert = []

            # Get existing projects mapping (both external_id and key -> internal_id)
            projects_query = text("""
                SELECT external_id, key, id
                FROM projects
                WHERE integration_id = :integration_id AND tenant_id = :tenant_id
            """)
            projects_results = db.execute(projects_query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id
            }).fetchall()

            projects_lookup = {row[0]: row[2] for row in projects_results}  # external_id -> internal_id
            projects_key_lookup = {row[1]: row[2] for row in projects_results}  # key -> internal_id
            logger.info(f"Found {len(projects_lookup)} projects for relationship mapping")

            # Get existing statuses mapping (external_id -> internal_id)
            statuses_query = text("""
                SELECT external_id, id
                FROM statuses
                WHERE integration_id = :integration_id AND tenant_id = :tenant_id
            """)
            statuses_results = db.execute(statuses_query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id
            }).fetchall()

            statuses_lookup = {row[0]: row[1] for row in statuses_results}
            logger.info(f"Found {len(statuses_lookup)} statuses for relationship mapping")

            # Get existing relationships to avoid duplicates
            existing_relationships_query = text("""
                SELECT project_id, status_id
                FROM projects_statuses
            """)
            existing_relationships = db.execute(existing_relationships_query).fetchall()
            existing_pairs = {(row[0], row[1]) for row in existing_relationships}

            # Process each project-status relationship
            for project_status_data in project_statuses_data:
                # Handle both old and new formats
                if 'project_key' in project_status_data:
                    # New format: {'project_key': 'BEN', 'status_id': '123', ...}
                    project_key = project_status_data.get('project_key')
                    project_internal_id = projects_key_lookup.get(project_key)
                    status_external_id = project_status_data.get('status_id')

                    if not project_internal_id:
                        logger.warning(f"Project with key {project_key} not found in projects table")
                        continue

                    status_internal_id = statuses_lookup.get(status_external_id)

                    if not status_internal_id:
                        logger.warning(f"Status {status_external_id} not found in statuses table")
                        continue

                    # Check if relationship already exists
                    relationship_pair = (project_internal_id, status_internal_id)
                    if relationship_pair not in existing_pairs:
                        relationships_to_insert.append({
                            'project_id': project_internal_id,
                            'status_id': status_internal_id
                        })
                        existing_pairs.add(relationship_pair)

                else:
                    # Old format: {'project_id': '123', 'statuses': [...]}
                    project_external_id = project_status_data.get('project_id')
                    project_internal_id = projects_lookup.get(project_external_id)

                    if not project_internal_id:
                        logger.warning(f"Project {project_external_id} not found in projects table")
                        continue

                    statuses = project_status_data.get('statuses', [])

                    # Process each issue type's statuses
                    for issue_type_statuses in statuses:
                        if isinstance(issue_type_statuses, dict) and 'statuses' in issue_type_statuses:
                            for status_data in issue_type_statuses['statuses']:
                                status_external_id = status_data.get('id')
                                status_internal_id = statuses_lookup.get(status_external_id)

                                if not status_internal_id:
                                    logger.warning(f"Status {status_external_id} not found in statuses table")
                                    continue

                                # Check if relationship already exists
                                relationship_pair = (project_internal_id, status_internal_id)
                                if relationship_pair not in existing_pairs:
                                    relationships_to_insert.append({
                                        'project_id': project_internal_id,
                                        'status_id': status_internal_id
                                    })
                                    existing_pairs.add(relationship_pair)

            # Bulk insert new relationships
            if relationships_to_insert:
                insert_query = text("""
                    INSERT INTO projects_statuses (project_id, status_id)
                    VALUES (:project_id, :status_id)
                    ON CONFLICT (project_id, status_id) DO NOTHING
                """)
                db.execute(insert_query, relationships_to_insert)
                logger.info(f"Inserted {len(relationships_to_insert)} new project-status relationships")

            return len(relationships_to_insert)

        except Exception as e:
            logger.error(f"Error processing project-status relationships data: {e}")
            raise

    def _queue_entities_for_vectorization(
        self,
        tenant_id: int,
        table_name: str,
        entities: List[Dict[str, Any]]
    ):
        """
        Queue entities for vectorization by publishing messages to vectorization queue.

        Args:
            tenant_id: Tenant ID
            table_name: Name of the table (projects, wits, statuses, etc.)
            entities: List of entity dictionaries with external_id or key
        """
        if not entities:
            return

        try:
            queue_manager = QueueManager()
            queued_count = 0

            for entity in entities:
                # Get external ID based on table type
                external_id = None

                if table_name == 'projects':
                    external_id = entity.get('key')
                elif table_name == 'wits':
                    external_id = entity.get('external_id')
                elif table_name == 'statuses':
                    external_id = entity.get('external_id')
                elif table_name == 'custom_fields':
                    external_id = entity.get('external_id')
                elif table_name == 'work_items':
                    external_id = entity.get('key')
                elif table_name == 'changelogs':
                    external_id = entity.get('external_id')
                elif table_name in ['prs', 'prs_commits', 'prs_reviews', 'prs_comments', 'repositories']:
                    external_id = entity.get('external_id')
                elif table_name == 'work_items_prs_links':
                    # Special case: use internal ID
                    external_id = str(entity.get('id'))
                else:
                    # Default: try external_id first, then key
                    external_id = entity.get('external_id') or entity.get('key')

                if not external_id:
                    logger.warning(f"No external_id found for {table_name} entity: {entity}")
                    continue

                # Publish vectorization message
                success = queue_manager.publish_vectorization_job(
                    tenant_id=tenant_id,
                    table_name=table_name,
                    external_id=str(external_id),
                    operation='insert'
                )

                if success:
                    queued_count += 1

            if queued_count > 0:
                logger.info(f"Queued {queued_count} {table_name} entities for vectorization")

        except Exception as e:
            logger.error(f"Error queuing entities for vectorization: {e}")
            # Don't raise - vectorization is async and shouldn't block transform


