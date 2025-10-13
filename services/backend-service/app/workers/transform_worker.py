"""
Transform Worker for processing raw ETL data.

Consumes messages from transform_queue and processes raw data based on type:
- jira_custom_fields: Process custom fields discovery data from createmeta API
- jira_special_fields: Process special fields from field search API (e.g., development field)
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
    - jira_special_fields: Creates/updates special fields not in createmeta (e.g., development field)

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
            elif message_type == 'jira_special_fields':
                return self._process_jira_special_fields(
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
            elif message_type == 'jira_issues_changelogs':
                return self._process_jira_issues_changelogs(
                    raw_data_id, tenant_id, integration_id
                )
            elif message_type == 'jira_dev_status':
                return self._process_jira_dev_status(
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
                            'external_id': external_id,  # Include external_id for queueing
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

                if result['projects_to_update']:
                    bulk_ops = BulkOperations()
                    bulk_ops.bulk_update(session, 'projects', result['projects_to_update'])
                    logger.info(f"Updated {len(result['projects_to_update'])} projects")

                if result['wits_to_insert']:
                    bulk_ops = BulkOperations()
                    bulk_ops.bulk_insert(session, 'wits', result['wits_to_insert'])
                    logger.info(f"Inserted {len(result['wits_to_insert'])} new WITs")

                if result['wits_to_update']:
                    bulk_ops = BulkOperations()
                    bulk_ops.bulk_update(session, 'wits', result['wits_to_update'])
                    logger.info(f"Updated {len(result['wits_to_update'])} WITs")

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

                # Commit all changes BEFORE queueing for vectorization
                session.commit()

                # 6. Queue entities for vectorization AFTER commit
                if result['projects_to_insert']:
                    self._queue_entities_for_vectorization(tenant_id, 'projects', result['projects_to_insert'])
                if result['projects_to_update']:
                    self._queue_entities_for_vectorization(tenant_id, 'projects', result['projects_to_update'])
                if result['wits_to_insert']:
                    self._queue_entities_for_vectorization(tenant_id, 'wits', result['wits_to_insert'])
                if result['wits_to_update']:
                    self._queue_entities_for_vectorization(tenant_id, 'wits', result['wits_to_update'])

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
        Process projects data from /project/search API endpoint.

        COMPLETELY SEPARATE from /createmeta processing!

        Key features:
        - Handles 'values' array with 'issueTypes' (camelCase)
        - DEDUPLICATES WITs across all projects (same WIT can appear in multiple projects)
        - Queues projects and WITs for vectorization
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

        # Track unique WITs across all projects to avoid duplicates
        wits_seen = {}  # external_id -> wit_data

        # Process each project
        for project_data in projects_data:
            project_external_id = project_data.get('id')
            project_key = project_data.get('key')
            project_name = project_data.get('name')
            project_type = project_data.get('projectTypeKey')

            if not project_external_id:
                logger.warning(f"Skipping project without external_id: {project_data}")
                continue

            logger.info(f"  📁 Processing project {project_key} ({project_name})")

            # Process project
            if project_external_id in existing_projects:
                # Update existing project
                existing_project = existing_projects[project_external_id]
                if (existing_project.key != project_key or
                    existing_project.name != project_name or
                    existing_project.project_type != project_type):
                    result['projects_to_update'].append({
                        'id': existing_project.id,
                        'key': project_key,  # Needed for queueing
                        'name': project_name,
                        'project_type': project_type,
                        'last_updated_at': datetime.now(timezone.utc)
                    })
                    logger.info(f"    ✏️  Project {project_key} needs update")
            else:
                # New project
                result['projects_to_insert'].append({
                    'external_id': project_external_id,
                    'key': project_key,
                    'name': project_name,
                    'project_type': project_type,
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'active': True,
                    'created_at': datetime.now(timezone.utc),
                    'last_updated_at': datetime.now(timezone.utc)
                })
                logger.info(f"    ➕ Project {project_key} is new")

            # Process issue types (WITs) - DEDUPLICATE across all projects
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

                # Only process each unique WIT once (deduplicate)
                if wit_external_id not in wits_seen:
                    # Lookup wits_mapping_id
                    wits_mapping_id = self._lookup_wit_mapping_id(wit_name, tenant_id)

                    if wit_external_id in existing_wits:
                        # Check if WIT needs update
                        existing_wit = existing_wits[wit_external_id]
                        if (existing_wit.original_name != wit_name or
                            existing_wit.description != wit_description or
                            existing_wit.hierarchy_level != hierarchy_level or
                            existing_wit.wits_mapping_id != wits_mapping_id):
                            result['wits_to_update'].append({
                                'id': existing_wit.id,
                                'external_id': wit_external_id,  # Needed for queueing
                                'original_name': wit_name,
                                'description': wit_description,
                                'hierarchy_level': hierarchy_level,
                                'wits_mapping_id': wits_mapping_id,
                                'last_updated_at': datetime.now(timezone.utc)
                            })
                            logger.info(f"      ✏️  WIT {wit_name} (id={wit_external_id}) needs update")
                    else:
                        # New WIT
                        result['wits_to_insert'].append({
                            'external_id': wit_external_id,
                            'original_name': wit_name,
                            'description': wit_description,
                            'hierarchy_level': hierarchy_level,
                            'wits_mapping_id': wits_mapping_id,
                            'tenant_id': tenant_id,
                            'integration_id': integration_id,
                            'active': True,
                            'created_at': datetime.now(timezone.utc),
                            'last_updated_at': datetime.now(timezone.utc)
                        })
                        logger.info(f"      ➕ WIT {wit_name} (id={wit_external_id}) is new")

                    # Mark as seen
                    wits_seen[wit_external_id] = True

            # Create project-wit relationships
            for wit_external_id in project_wit_external_ids:
                relationship = (project_external_id, wit_external_id)
                result['project_wit_relationships'].append(relationship)

        logger.info(f"📊 Summary: {len(result['projects_to_insert'])} projects to insert, {len(result['projects_to_update'])} to update")
        logger.info(f"📊 Summary: {len(result['wits_to_insert'])} WITs to insert, {len(result['wits_to_update'])} to update (deduplicated from {len(wits_seen)} unique)")

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
                bulk_result = self._perform_bulk_operations(
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

                # 6. Auto-map development field if it exists
                self._auto_map_development_field(session, tenant_id, integration_id)

                # 7. Update raw data status
                self._update_raw_data_status(session, raw_data_id, 'completed')

                # Commit all changes
                session.commit()

                # NOTE: /createmeta is for custom fields discovery only
                # Projects and WITs are NOT queued for vectorization here
                # Only /project/search should queue for vectorization

                logger.info(f"Successfully processed custom fields for raw_data_id={raw_data_id}")
                return True

        except Exception as e:
            logger.error(f"Error processing Jira custom fields: {e}")
            return False

    def _process_jira_special_fields(
        self, raw_data_id: int, tenant_id: int, integration_id: int
    ) -> bool:
        """
        Process special fields from /rest/api/3/field/search API response.

        Special fields are those not available in createmeta API (e.g., development field).
        This method can handle any field fetched via field search API.

        Response format:
        {
            "maxResults": 50,
            "startAt": 0,
            "total": 1,
            "isLast": true,
            "values": [
                {
                    "id": "customfield_10000",
                    "name": "development",
                    "schema": {"type": "any", "custom": "...", "customId": 10000},
                    "typeDisplayName": "Dev Summary Custom Field",
                    "description": "Includes development summary panel information used in JQL"
                }
            ]
        }

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

                # 2. Parse field search response
                field_search_response = raw_data
                values = field_search_response.get('values', [])

                if not values:
                    logger.warning(f"No field data found in raw data: {raw_data_id}")
                    return True  # Not an error, just empty data

                # Get the first (and should be only) field
                field_data = values[0]
                field_id = field_data.get('id')
                field_name = field_data.get('name', 'Unknown')
                field_schema = field_data.get('schema', {})
                field_type = field_schema.get('type', 'any')

                # Rename 'development' to 'Development' for better display
                if field_name.lower() == 'development':
                    field_name = 'Development'

                logger.info(f"Processing special field: {field_id} - {field_name}")

                # 3. Check if field already exists
                existing_custom_fields = self._get_existing_custom_fields(session, tenant_id, integration_id)

                # 4. Insert or update custom field
                if field_id in existing_custom_fields:
                    # Update existing field
                    logger.info(f"Special field {field_id} already exists, updating")
                    update_query = text("""
                        UPDATE custom_fields
                        SET name = :name,
                            field_type = :field_type,
                            last_updated_at = NOW()
                        WHERE external_id = :external_id
                        AND tenant_id = :tenant_id
                        AND integration_id = :integration_id
                    """)
                    session.execute(update_query, {
                        'name': field_name,
                        'field_type': field_type,
                        'external_id': field_id,
                        'tenant_id': tenant_id,
                        'integration_id': integration_id
                    })
                else:
                    # Insert new field
                    logger.info(f"Inserting new special field: {field_id} - {field_name}")
                    insert_query = text("""
                        INSERT INTO custom_fields (
                            external_id, name, field_type, operations,
                            tenant_id, integration_id, active, created_at, last_updated_at
                        ) VALUES (
                            :external_id, :name, :field_type, :operations,
                            :tenant_id, :integration_id, TRUE, NOW(), NOW()
                        )
                    """)
                    session.execute(insert_query, {
                        'external_id': field_id,
                        'name': field_name,
                        'field_type': field_type,
                        'operations': None,  # No operations for special fields
                        'tenant_id': tenant_id,
                        'integration_id': integration_id
                    })

                # 5. Auto-map development field if this is the development field
                import os
                development_field_id = os.getenv('JIRA_DEVELOPMENT_FIELD_ID', 'customfield_10000')
                if field_id == development_field_id:
                    self._auto_map_development_field(session, tenant_id, integration_id)

                # 6. Update raw data status
                self._update_raw_data_status(session, raw_data_id, 'completed')

                # Commit all changes
                session.commit()

                logger.info(f"Successfully processed special field for raw_data_id={raw_data_id}")
                return True

        except Exception as e:
            logger.error(f"Error processing Jira special field: {e}")
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

    def _auto_map_development_field(self, session, tenant_id: int, integration_id: int):
        """
        Auto-map development field to development_field_id if it exists in custom_fields.
        This is called after custom fields are synced from Jira.
        """
        try:
            import os
            development_field_id = os.getenv('JIRA_DEVELOPMENT_FIELD_ID', 'customfield_10000')

            # Check if development field exists in custom_fields
            check_query = text("""
                SELECT id FROM custom_fields
                WHERE external_id = :external_id
                AND tenant_id = :tenant_id
                AND integration_id = :integration_id
                AND active = true
            """)
            result = session.execute(check_query, {
                'external_id': development_field_id,
                'tenant_id': tenant_id,
                'integration_id': integration_id
            }).fetchone()

            if not result:
                logger.info(f"Development field {development_field_id} not found, skipping auto-mapping")
                return

            custom_field_db_id = result[0]
            logger.info(f"Found development field {development_field_id} with ID {custom_field_db_id}")

            # Check if custom_fields_mapping record exists
            mapping_check_query = text("""
                SELECT id FROM custom_fields_mapping
                WHERE tenant_id = :tenant_id
                AND integration_id = :integration_id
            """)
            mapping_result = session.execute(mapping_check_query, {
                'tenant_id': tenant_id,
                'integration_id': integration_id
            }).fetchone()

            if mapping_result:
                # Update existing mapping
                update_query = text("""
                    UPDATE custom_fields_mapping
                    SET development_field_id = :field_id,
                        last_updated_at = NOW()
                    WHERE tenant_id = :tenant_id
                    AND integration_id = :integration_id
                """)
                session.execute(update_query, {
                    'field_id': custom_field_db_id,
                    'tenant_id': tenant_id,
                    'integration_id': integration_id
                })
                logger.info(f"Auto-mapped development field {development_field_id} to development_field_id")
            else:
                # Create new mapping record
                insert_query = text("""
                    INSERT INTO custom_fields_mapping (
                        tenant_id, integration_id, development_field_id,
                        active, created_at, last_updated_at
                    ) VALUES (
                        :tenant_id, :integration_id, :field_id,
                        true, NOW(), NOW()
                    )
                """)
                session.execute(insert_query, {
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'field_id': custom_field_db_id
                })
                logger.info(f"Created custom_fields_mapping and auto-mapped development field {development_field_id}")

        except Exception as e:
            logger.error(f"Error auto-mapping development field: {e}")
            # Don't raise - this is a nice-to-have feature, not critical

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

            # Lookup wits_mapping_id from wits_mappings table
            wits_mapping_id = self._lookup_wit_mapping_id(wit_name, tenant_id)
            if wits_mapping_id:
                logger.info(f"🔍 DEBUG: Found wits_mapping_id={wits_mapping_id} for WIT '{wit_name}'")
            else:
                logger.info(f"🔍 DEBUG: No wits_mapping found for WIT '{wit_name}' - will be set to NULL")

            if wit_external_id in existing_wits:
                # Check if WIT needs update
                existing_wit = existing_wits[wit_external_id]
                logger.info(f"🔍 DEBUG: WIT {wit_name} already exists, checking for updates...")

                if (existing_wit.original_name != wit_name or
                    existing_wit.description != wit_description or
                    existing_wit.hierarchy_level != hierarchy_level or
                    existing_wit.wits_mapping_id != wits_mapping_id):
                    logger.info(f"🔍 DEBUG: WIT {wit_name} needs update")
                    result['wits_to_update'].append({
                        'id': existing_wit.id,
                        'external_id': wit_external_id,  # Include for queueing
                        'original_name': wit_name,
                        'description': wit_description,
                        'hierarchy_level': hierarchy_level,
                        'wits_mapping_id': wits_mapping_id,
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
                    'wits_mapping_id': wits_mapping_id,
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

    def _lookup_wit_mapping_id(self, wit_name: str, tenant_id: int) -> Optional[int]:
        """
        Lookup wits_mapping_id from wits_mappings table based on wit_from (original_name).

        Args:
            wit_name: Original WIT name from Jira (e.g., "Story", "Bug", "Epic")
            tenant_id: Tenant ID

        Returns:
            wits_mapping_id if found, None otherwise
        """
        try:
            with self.get_db_session() as session:
                from sqlalchemy import func
                from app.models.unified_models import WitMapping

                # Case-insensitive lookup
                mapping = session.query(WitMapping).filter(
                    func.lower(WitMapping.wit_from) == wit_name.lower(),
                    WitMapping.tenant_id == tenant_id,
                    WitMapping.active == True
                ).first()

                return mapping.id if mapping else None

        except Exception as e:
            logger.warning(f"Error looking up wit mapping for '{wit_name}': {e}")
            return None

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
        """
        Perform bulk database operations.

        NOTE: This method only performs database operations.
        Vectorization queueing should be done AFTER commit by the caller.
        """
        try:
            # 1. Bulk insert projects first
            if projects_to_insert:
                BulkOperations.bulk_insert(session, 'projects', projects_to_insert)
                logger.info(f"Inserted {len(projects_to_insert)} projects")

            # 2. Bulk update projects
            if projects_to_update:
                BulkOperations.bulk_update(session, 'projects', projects_to_update)
                logger.info(f"Updated {len(projects_to_update)} projects")

            # 3. Bulk insert WITs
            if wits_to_insert:
                BulkOperations.bulk_insert(session, 'wits', wits_to_insert)
                logger.info(f"Inserted {len(wits_to_insert)} WITs")

            # 4. Bulk update WITs
            if wits_to_update:
                BulkOperations.bulk_update(session, 'wits', wits_to_update)
                logger.info(f"Updated {len(wits_to_update)} WITs")

            # 5. Bulk insert custom fields (global, no project relationship)
            if custom_fields_to_insert:
                BulkOperations.bulk_insert(session, 'custom_fields', custom_fields_to_insert)
                logger.info(f"Inserted {len(custom_fields_to_insert)} custom fields")
                # Note: Custom fields are not vectorized (they're metadata)

            # 6. Bulk update custom fields
            if custom_fields_to_update:
                BulkOperations.bulk_update(session, 'custom_fields', custom_fields_to_update)
                logger.info(f"Updated {len(custom_fields_to_update)} custom fields")
                # Note: Custom fields are not vectorized (they're metadata)

            # 7. Project-WIT relationships are handled separately using _create_project_wit_relationships_for_search
            # This ensures proper error handling and data validation

            # Return the entities that need vectorization (caller will queue after commit)
            return {
                'projects_to_insert': projects_to_insert,
                'projects_to_update': projects_to_update,
                'wits_to_insert': wits_to_insert,
                'wits_to_update': wits_to_update
            }

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

                # Process statuses and project relationships (returns entities for vectorization)
                statuses_result = self._process_statuses_data(db, statuses_data, integration_id, tenant_id)
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

                # Commit all changes BEFORE queueing for vectorization
                db.commit()

                # Queue statuses for vectorization AFTER commit
                if statuses_result['statuses_to_insert']:
                    self._queue_entities_for_vectorization(tenant_id, 'statuses', statuses_result['statuses_to_insert'])
                if statuses_result['statuses_to_update']:
                    self._queue_entities_for_vectorization(tenant_id, 'statuses', statuses_result['statuses_to_update'])

                statuses_processed = statuses_result['count']
                logger.info(f"Successfully processed {statuses_processed} statuses and {relationships_processed} project relationships")
                return True

        except Exception as e:
            logger.error(f"Error processing statuses and project relationships: {e}")
            return False

    def _process_statuses_data(self, db, statuses_data: List[Dict], integration_id: int, tenant_id: int) -> Dict[str, Any]:
        """
        Process and bulk insert/update statuses.

        Returns:
            Dict with 'count', 'statuses_to_insert', and 'statuses_to_update'
        """
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

            # Return entities for vectorization (to be queued AFTER commit)
            return {
                'count': len(statuses_to_insert) + len(statuses_to_update),
                'statuses_to_insert': statuses_to_insert,
                'statuses_to_update': statuses_to_update
            }

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
            logger.debug(f"No entities to queue for {table_name}")
            return

        try:
            logger.info(f"Attempting to queue {len(entities)} {table_name} entities for vectorization")
            queue_manager = QueueManager()
            queued_count = 0

            for entity in entities:
                # Get external ID based on table type
                external_id = None

                if table_name == 'projects':
                    external_id = entity.get('key')
                    logger.debug(f"Project entity keys: {list(entity.keys())}, key value: {external_id}")
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

    def _process_jira_issues_changelogs(self, raw_data_id: int, tenant_id: int, integration_id: int) -> bool:
        """
        Process Jira issues and changelogs from raw_extraction_data.

        Flow:
        1. Load raw data from raw_extraction_data table
        2. Transform issues data and bulk insert/update work_items table
        3. Transform changelogs data and bulk insert changelogs table
        4. Queue work_items and changelogs for vectorization
        """
        try:
            logger.info(f"Processing jira_issues_changelogs for raw_data_id={raw_data_id}")

            with self.get_db_session() as db:
                # Load raw data
                raw_data = self._get_raw_data(db, raw_data_id)
                if not raw_data:
                    logger.error(f"Raw data {raw_data_id} not found")
                    return False

                issues_data = raw_data.get('issues', [])
                if not issues_data:
                    logger.warning(f"No issues data found in raw_data_id={raw_data_id}")
                    return True

                logger.info(f"Processing {len(issues_data)} issues")

                # Get reference data for mapping
                projects_map, wits_map, statuses_map = self._get_reference_data_maps(db, integration_id, tenant_id)

                # Get custom field mappings from integration
                custom_field_mappings = self._get_custom_field_mappings(db, integration_id, tenant_id)
                logger.info(f"Loaded {len(custom_field_mappings)} custom field mappings")

                # Process issues
                issues_processed = self._process_issues_data(
                    db, issues_data, integration_id, tenant_id, projects_map, wits_map, statuses_map, custom_field_mappings
                )

                # Process changelogs
                changelogs_processed = self._process_changelogs_data(
                    db, issues_data, integration_id, tenant_id, statuses_map
                )

                # Update raw data status to completed
                update_query = text("""
                    UPDATE raw_extraction_data
                    SET status = 'completed',
                        last_updated_at = NOW(),
                        error_details = NULL
                    WHERE id = :raw_data_id
                """)
                db.execute(update_query, {'raw_data_id': raw_data_id})
                db.commit()

                logger.info(f"Processed {issues_processed} issues and {changelogs_processed} changelogs - marked raw_data_id={raw_data_id} as completed")
                return True

        except Exception as e:
            logger.error(f"Error processing jira_issues_changelogs: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

            # Mark raw data as failed
            try:
                with self.get_db_session() as db:
                    error_query = text("""
                        UPDATE raw_extraction_data
                        SET status = 'failed',
                            error_details = :error_details::jsonb,
                            last_updated_at = NOW()
                        WHERE id = :raw_data_id
                    """)
                    db.execute(error_query, {
                        'raw_data_id': raw_data_id,
                        'error_details': json.dumps({'error': str(e)[:500]})  # Proper JSON format
                    })
                    db.commit()
            except Exception as update_error:
                logger.error(f"Failed to update raw_data status to failed: {update_error}")

            return False

    def _get_reference_data_maps(self, db, integration_id: int, tenant_id: int):
        """Get reference data maps for projects, wits, and statuses."""
        # Get projects map
        projects_query = text("""
            SELECT external_id, id, key
            FROM projects
            WHERE integration_id = :integration_id AND tenant_id = :tenant_id
        """)
        projects_result = db.execute(projects_query, {
            'integration_id': integration_id,
            'tenant_id': tenant_id
        }).fetchall()
        projects_map = {row[0]: {'id': row[1], 'key': row[2]} for row in projects_result}

        # Get wits map
        wits_query = text("""
            SELECT external_id, id
            FROM wits
            WHERE integration_id = :integration_id AND tenant_id = :tenant_id
        """)
        wits_result = db.execute(wits_query, {
            'integration_id': integration_id,
            'tenant_id': tenant_id
        }).fetchall()
        wits_map = {row[0]: row[1] for row in wits_result}

        # Get statuses map
        statuses_query = text("""
            SELECT external_id, id
            FROM statuses
            WHERE integration_id = :integration_id AND tenant_id = :tenant_id
        """)
        statuses_result = db.execute(statuses_query, {
            'integration_id': integration_id,
            'tenant_id': tenant_id
        }).fetchall()
        statuses_map = {row[0]: row[1] for row in statuses_result}

        return projects_map, wits_map, statuses_map

    def _get_custom_field_mappings(self, db, integration_id: int, tenant_id: int) -> Dict[str, str]:
        """
        Get custom field mappings from custom_fields_mapping table.

        Returns:
            Dict mapping Jira field IDs (e.g., 'customfield_10024') to work_items column names or special fields
            Includes special fields: 'team', 'development', 'story_points'

        Example:
            {
                'customfield_10001': 'team',  # Special field
                'customfield_10000': 'development',  # Special field
                'customfield_10024': 'story_points',  # Special field
                'customfield_10128': 'custom_field_01',  # Regular custom field
                'customfield_10222': 'custom_field_02',  # Regular custom field
            }
        """
        try:
            # Get custom field mappings from custom_fields_mapping table
            query = text("""
                SELECT
                    cfm.team_field_id,
                    cfm.development_field_id,
                    cfm.story_points_field_id,
                    cfm.custom_field_01_id, cfm.custom_field_02_id, cfm.custom_field_03_id,
                    cfm.custom_field_04_id, cfm.custom_field_05_id, cfm.custom_field_06_id,
                    cfm.custom_field_07_id, cfm.custom_field_08_id, cfm.custom_field_09_id,
                    cfm.custom_field_10_id, cfm.custom_field_11_id, cfm.custom_field_12_id,
                    cfm.custom_field_13_id, cfm.custom_field_14_id, cfm.custom_field_15_id,
                    cfm.custom_field_16_id, cfm.custom_field_17_id, cfm.custom_field_18_id,
                    cfm.custom_field_19_id, cfm.custom_field_20_id
                FROM custom_fields_mapping cfm
                WHERE cfm.integration_id = :integration_id AND cfm.tenant_id = :tenant_id
            """)
            result = db.execute(query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id
            }).fetchone()

            if not result:
                logger.info(f"No custom field mappings found for integration {integration_id}")
                return {}

            # Get custom_fields external_ids for the mapped field IDs
            field_ids = [fid for fid in result if fid is not None]
            if not field_ids:
                logger.info(f"No custom fields mapped for integration {integration_id}")
                return {}

            # Query custom_fields to get external_ids
            fields_query = text("""
                SELECT id, external_id
                FROM custom_fields
                WHERE id = ANY(:field_ids) AND tenant_id = :tenant_id
            """)
            fields_result = db.execute(fields_query, {
                'field_ids': field_ids,
                'tenant_id': tenant_id
            }).fetchall()

            # Create map of field_id -> external_id
            field_id_to_external_id = {row[0]: row[1] for row in fields_result}

            # Build mappings dict
            mappings = {}

            # Special fields (indices 0, 1, 2)
            if result[0]:  # team_field_id
                external_id = field_id_to_external_id.get(result[0])
                if external_id:
                    mappings[external_id] = 'team'

            if result[1]:  # development_field_id
                external_id = field_id_to_external_id.get(result[1])
                if external_id:
                    mappings[external_id] = 'development'

            if result[2]:  # story_points_field_id
                external_id = field_id_to_external_id.get(result[2])
                if external_id:
                    mappings[external_id] = 'story_points'

            # Regular custom fields (indices 3-22 for custom_field_01 to custom_field_20)
            for i in range(20):
                field_id = result[3 + i]  # Start from index 3
                if field_id:
                    external_id = field_id_to_external_id.get(field_id)
                    if external_id:
                        mappings[external_id] = f'custom_field_{i+1:02d}'

            logger.info(f"Loaded {len(mappings)} custom field mappings for integration {integration_id}")
            return mappings

        except Exception as e:
            logger.error(f"Error loading custom field mappings: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {}

    def _extract_all_fields(self, fields: Dict, custom_field_mappings: Dict[str, str]) -> Dict:
        """
        Extract all mapped fields from Jira issue fields based on mappings.
        Includes special fields (team, code_changed, story_points) and custom fields.

        Args:
            fields: Jira issue fields dict
            custom_field_mappings: Dict mapping Jira field IDs to work_items column names
                                  e.g., {
                                      'customfield_10001': 'team',
                                      'customfield_10000': 'code_changed',
                                      'customfield_10024': 'story_points',
                                      'customfield_10128': 'custom_field_01'
                                  }

        Returns:
            Dict with all field column names and values, plus overflow
            e.g., {
                'team': 'R&I',
                'code_changed': True,
                'story_points': 5.0,
                'custom_field_01': 'Epic Name',
                'custom_field_02': 'Some value',
                'custom_fields_overflow': {'customfield_99999': 'some value'}
            }
        """
        result = {}
        overflow = {}

        if not custom_field_mappings:
            # No mappings configured - don't extract any custom fields
            logger.debug("No custom field mappings configured - skipping custom field extraction")
            return result

        # Extract mapped fields (special + custom)
        for jira_field_id, column_name in custom_field_mappings.items():
            if jira_field_id in fields:
                value = fields[jira_field_id]

                # Special handling for specific fields
                if column_name == 'team':
                    # Team field - extract from dict or string
                    if value is None:
                        result[column_name] = None
                    elif isinstance(value, dict):
                        result[column_name] = value.get('name') or value.get('value')
                    elif isinstance(value, str):
                        result[column_name] = value
                    else:
                        result[column_name] = str(value)

                elif column_name == 'code_changed':
                    # Code changed field - detect PR/commit data
                    code_changed = False
                    if isinstance(value, bool):
                        code_changed = value
                    elif isinstance(value, str):
                        # Check if string contains PR/commit data indicators
                        value_lower = value.lower()
                        if 'pullrequest=' in value_lower or 'commit=' in value_lower:
                            code_changed = True
                        elif value_lower in ('true', 'yes', '1'):
                            code_changed = True
                    elif isinstance(value, dict):
                        # Check for PR/commit data in dict
                        if 'pullrequest' in value or 'commit' in value:
                            code_changed = True
                        else:
                            # Check 'value' key
                            val = value.get('value', '')
                            code_changed = str(val).lower() in ('true', 'yes', '1')
                    result[column_name] = code_changed

                elif column_name == 'story_points':
                    # Story points field - convert to float
                    story_points = None
                    if value is not None:
                        try:
                            if isinstance(value, (int, float)):
                                story_points = float(value)
                            elif isinstance(value, str):
                                story_points = float(value)
                        except (ValueError, TypeError):
                            logger.warning(f"Could not parse story_points value: {value}")
                            story_points = None
                    result[column_name] = story_points

                else:
                    # Regular custom field - handle different field types
                    if value is None:
                        result[column_name] = None
                    elif isinstance(value, dict):
                        # Complex field (e.g., user, option) - extract display value
                        result[column_name] = value.get('displayName') or value.get('name') or value.get('value') or str(value)
                    elif isinstance(value, list):
                        # Array field - join values
                        if value and isinstance(value[0], dict):
                            result[column_name] = ', '.join([item.get('name') or item.get('value') or str(item) for item in value])
                        else:
                            result[column_name] = ', '.join([str(v) for v in value])
                    else:
                        # Simple field (string, number, etc.)
                        result[column_name] = str(value) if not isinstance(value, str) else value

        # Check for unmapped custom fields (for overflow)
        for field_key, field_value in fields.items():
            if field_key.startswith('customfield_') and field_key not in custom_field_mappings:
                # This is a custom field that's not mapped - add to overflow
                if field_value is not None:
                    overflow[field_key] = field_value

        # Add overflow if any
        if overflow:
            result['custom_fields_overflow'] = overflow
            logger.debug(f"Found {len(overflow)} unmapped custom fields in overflow")

        return result

    def _process_issues_data(
        self, db, issues_data: List[Dict], integration_id: int, tenant_id: int,
        projects_map: Dict, wits_map: Dict, statuses_map: Dict, custom_field_mappings: Dict[str, str]
    ) -> int:
        """
        Process and insert/update issues in work_items table.

        Args:
            custom_field_mappings: Dict mapping Jira field IDs to work_items column names
                                  e.g., {'customfield_10024': 'custom_field_01'}
        """
        from datetime import datetime, timezone

        # Get existing issues
        external_ids = [issue.get('id') for issue in issues_data if issue.get('id')]
        existing_issues_query = text("""
            SELECT external_id, id, key
            FROM work_items
            WHERE integration_id = :integration_id AND tenant_id = :tenant_id
            AND external_id = ANY(:external_ids)
        """)
        existing_result = db.execute(existing_issues_query, {
            'integration_id': integration_id,
            'tenant_id': tenant_id,
            'external_ids': external_ids
        }).fetchall()
        existing_issues_map = {row[0]: {'id': row[1], 'key': row[2]} for row in existing_result}

        issues_to_insert = []
        issues_to_update = []
        current_time = datetime.now(timezone.utc)

        for issue in issues_data:
            try:
                external_id = issue.get('id')
                if not external_id:
                    continue

                fields = issue.get('fields', {})
                key = issue.get('key')

                # Extract field values
                project_external_id = fields.get('project', {}).get('id')
                wit_external_id = fields.get('issuetype', {}).get('id')
                status_external_id = fields.get('status', {}).get('id')

                # Map to internal IDs
                project_id = projects_map.get(project_external_id, {}).get('id') if project_external_id else None
                wit_id = wits_map.get(wit_external_id) if wit_external_id else None
                status_id = statuses_map.get(status_external_id) if status_external_id else None

                # Parse dates
                created = self._parse_datetime(fields.get('created'))
                updated = self._parse_datetime(fields.get('updated'))

                # Extract other fields
                summary = fields.get('summary')
                description = fields.get('description')
                priority = fields.get('priority', {}).get('name') if fields.get('priority') else None
                resolution = fields.get('resolution', {}).get('name') if fields.get('resolution') else None
                assignee = fields.get('assignee', {}).get('displayName') if fields.get('assignee') else None
                labels = ','.join(fields.get('labels', [])) if fields.get('labels') else None
                parent_external_id = fields.get('parent', {}).get('id') if fields.get('parent') else None

                # Extract special fields and custom fields based on mappings
                # This will extract team, code_changed, story_points, and custom_field_01-20
                all_fields_data = self._extract_all_fields(fields, custom_field_mappings)

                # Extract special fields from the result
                team = all_fields_data.pop('team', None)
                code_changed = all_fields_data.pop('code_changed', False)
                story_points = all_fields_data.pop('story_points', None)

                # Remaining fields are custom_field_01-20 and overflow
                custom_fields_data = all_fields_data

                # Check if issue exists
                if external_id in existing_issues_map:
                    # Update existing issue
                    update_dict = {
                        'id': existing_issues_map[external_id]['id'],
                        'summary': summary,
                        'description': description,
                        'project_id': project_id,
                        'wit_id': wit_id,
                        'status_id': status_id,
                        'priority': priority,
                        'resolution': resolution,
                        'assignee': assignee,
                        'team': team,
                        'labels': labels,
                        'updated': updated,
                        'parent_external_id': parent_external_id,
                        'code_changed': code_changed,
                        'story_points': story_points,
                        'last_updated_at': current_time
                    }
                    # Add custom fields to update dict
                    update_dict.update(custom_fields_data)
                    issues_to_update.append(update_dict)
                else:
                    # Insert new issue
                    insert_dict = {
                        'integration_id': integration_id,
                        'tenant_id': tenant_id,
                        'external_id': external_id,
                        'key': key,
                        'summary': summary,
                        'description': description,
                        'project_id': project_id,
                        'wit_id': wit_id,
                        'status_id': status_id,
                        'priority': priority,
                        'resolution': resolution,
                        'assignee': assignee,
                        'team': team,
                        'labels': labels,
                        'created': created,
                        'updated': updated,
                        'parent_external_id': parent_external_id,
                        'code_changed': code_changed,
                        'story_points': story_points,
                        'active': True,
                        'created_at': current_time,
                        'last_updated_at': current_time
                    }
                    # Add custom fields to insert dict
                    insert_dict.update(custom_fields_data)
                    issues_to_insert.append(insert_dict)

            except Exception as e:
                logger.error(f"Error processing issue {issue.get('key', 'unknown')}: {e}")
                continue

        # Bulk insert new issues
        if issues_to_insert:
            BulkOperations.bulk_insert(db, 'work_items', issues_to_insert)
            logger.info(f"Inserted {len(issues_to_insert)} new issues")

            # Queue for vectorization
            self._queue_entities_for_vectorization(tenant_id, 'work_items', issues_to_insert)

        # Bulk update existing issues
        if issues_to_update:
            BulkOperations.bulk_update(db, 'work_items', issues_to_update)
            logger.info(f"Updated {len(issues_to_update)} existing issues")

            # Queue for vectorization
            self._queue_entities_for_vectorization(tenant_id, 'work_items', issues_to_update)

        return len(issues_to_insert) + len(issues_to_update)

    def _process_changelogs_data(
        self, db, issues_data: List[Dict], integration_id: int, tenant_id: int,
        statuses_map: Dict
    ) -> int:
        """Process and insert changelogs from issues data."""
        from datetime import datetime, timezone

        # Get work_items map for changelog linking
        work_items_query = text("""
            SELECT external_id, id, key, created
            FROM work_items
            WHERE integration_id = :integration_id AND tenant_id = :tenant_id
        """)
        work_items_result = db.execute(work_items_query, {
            'integration_id': integration_id,
            'tenant_id': tenant_id
        }).fetchall()
        work_items_map = {row[2]: {'id': row[1], 'external_id': row[0], 'created': row[3]} for row in work_items_result}

        # Get existing changelogs to avoid duplicates
        existing_changelogs_query = text("""
            SELECT work_item_id, external_id
            FROM changelogs
            WHERE integration_id = :integration_id AND tenant_id = :tenant_id
        """)
        existing_result = db.execute(existing_changelogs_query, {
            'integration_id': integration_id,
            'tenant_id': tenant_id
        }).fetchall()
        existing_changelogs = {(row[0], row[1]) for row in existing_result}

        changelogs_to_insert = []
        current_time = datetime.now(timezone.utc)

        for issue in issues_data:
            try:
                issue_key = issue.get('key')
                if not issue_key or issue_key not in work_items_map:
                    continue

                work_item_id = work_items_map[issue_key]['id']
                work_item_created = work_items_map[issue_key]['created']

                # Get changelog from issue
                changelog = issue.get('changelog', {})
                histories = changelog.get('histories', [])

                if not histories:
                    continue

                # Sort changelogs by created date
                sorted_histories = sorted(histories, key=lambda x: x.get('created', ''))

                # Process each changelog entry
                for i, history in enumerate(sorted_histories):
                    try:
                        changelog_external_id = history.get('id')
                        if not changelog_external_id:
                            continue

                        # Skip if already exists
                        if (work_item_id, changelog_external_id) in existing_changelogs:
                            continue

                        # Look for status changes in items
                        items = history.get('items', [])
                        status_change = None
                        for item in items:
                            if item.get('field') == 'status':
                                status_change = item
                                break

                        if not status_change:
                            # Not a status change, skip
                            continue

                        # Extract status transition
                        from_status_external_id = status_change.get('from')
                        to_status_external_id = status_change.get('to')

                        from_status_id = statuses_map.get(from_status_external_id) if from_status_external_id else None
                        to_status_id = statuses_map.get(to_status_external_id) if to_status_external_id else None

                        # Parse transition date
                        transition_change_date = self._parse_datetime(history.get('created'))

                        # Calculate transition_start_date
                        if i == 0:
                            # First transition starts from issue creation
                            transition_start_date = work_item_created
                            # Ensure timezone-aware for comparison
                            if transition_start_date and transition_start_date.tzinfo is None:
                                transition_start_date = transition_start_date.replace(tzinfo=timezone.utc)
                        else:
                            # Subsequent transitions start from previous transition date
                            prev_history = sorted_histories[i-1]
                            transition_start_date = self._parse_datetime(prev_history.get('created'))

                        # Calculate time in status (seconds)
                        time_in_status_seconds = None
                        if transition_start_date and transition_change_date:
                            # Ensure both are timezone-aware for subtraction
                            if transition_start_date.tzinfo is None:
                                transition_start_date = transition_start_date.replace(tzinfo=timezone.utc)
                            if transition_change_date.tzinfo is None:
                                transition_change_date = transition_change_date.replace(tzinfo=timezone.utc)

                            time_diff = transition_change_date - transition_start_date
                            time_in_status_seconds = time_diff.total_seconds()

                        # Extract author
                        author_data = history.get('author', {})
                        changed_by = author_data.get('displayName') if author_data else None

                        changelogs_to_insert.append({
                            'integration_id': integration_id,
                            'tenant_id': tenant_id,
                            'work_item_id': work_item_id,
                            'external_id': changelog_external_id,
                            'from_status_id': from_status_id,
                            'to_status_id': to_status_id,
                            'transition_start_date': transition_start_date,
                            'transition_change_date': transition_change_date,
                            'time_in_status_seconds': time_in_status_seconds,
                            'changed_by': changed_by,
                            'active': True,
                            'created_at': current_time,
                            'last_updated_at': current_time
                        })

                    except Exception as e:
                        logger.error(f"Error processing changelog {history.get('id', 'unknown')}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error processing changelogs for issue {issue.get('key', 'unknown')}: {e}")
                continue

        # Bulk insert changelogs
        if changelogs_to_insert:
            BulkOperations.bulk_insert(db, 'changelogs', changelogs_to_insert)
            logger.info(f"Inserted {len(changelogs_to_insert)} new changelogs")

            # Queue for vectorization
            self._queue_entities_for_vectorization(tenant_id, 'changelogs', changelogs_to_insert)

        # Calculate and update enhanced workflow metrics from in-memory changelog data
        if changelogs_to_insert:
            logger.info(f"Calculating enhanced workflow metrics for {len(work_items_map)} work items...")
            self._calculate_and_update_workflow_metrics(
                db, changelogs_to_insert, work_items_map, statuses_map, integration_id, tenant_id
            )

        return len(changelogs_to_insert)

    def _calculate_and_update_workflow_metrics(
        self, db, changelogs_data: List[Dict], work_items_map: Dict,
        statuses_map: Dict, integration_id: int, tenant_id: int
    ):
        """
        Calculate enhanced workflow metrics from in-memory changelog data and bulk update work_items.

        Args:
            changelogs_data: List of changelog dicts (from changelogs_to_insert)
            work_items_map: Dict mapping work_item keys to {id, external_id, created}
            statuses_map: Dict mapping status external_ids to status internal IDs
        """
        from datetime import datetime, timezone
        from app.core.utils import DateTimeHelper

        # Group changelogs by work_item_id
        changelogs_by_work_item = {}
        for changelog in changelogs_data:
            work_item_id = changelog['work_item_id']
            if work_item_id not in changelogs_by_work_item:
                changelogs_by_work_item[work_item_id] = []
            changelogs_by_work_item[work_item_id].append(changelog)

        # Get status categories map (status_id -> category)
        status_categories = {}
        reverse_statuses_map = {v: k for k, v in statuses_map.items()}  # internal_id -> external_id

        statuses_query = text("""
            SELECT id, external_id, category
            FROM statuses
            WHERE integration_id = :integration_id AND tenant_id = :tenant_id
        """)
        statuses_result = db.execute(statuses_query, {
            'integration_id': integration_id,
            'tenant_id': tenant_id
        }).fetchall()
        status_categories = {row[0]: row[2].lower() if row[2] else None for row in statuses_result}

        # Calculate metrics for each work item
        work_items_to_update = []
        current_time = datetime.now(timezone.utc)

        for work_item_id, changelogs in changelogs_by_work_item.items():
            # Sort changelogs by transition_change_date DESC (newest first)
            sorted_changelogs = sorted(
                changelogs,
                key=lambda x: x['transition_change_date'] if x['transition_change_date'] else datetime.min.replace(tzinfo=timezone.utc),
                reverse=True
            )

            # Calculate metrics
            metrics = self._calculate_enhanced_workflow_metrics(
                sorted_changelogs, status_categories
            )

            # Add to update list
            work_items_to_update.append({
                'id': work_item_id,
                'work_first_committed_at': metrics['work_first_committed_at'],
                'work_first_started_at': metrics['work_first_started_at'],
                'work_last_started_at': metrics['work_last_started_at'],
                'work_first_completed_at': metrics['work_first_completed_at'],
                'work_last_completed_at': metrics['work_last_completed_at'],
                'total_work_starts': metrics['total_work_starts'],
                'total_completions': metrics['total_completions'],
                'total_backlog_returns': metrics['total_backlog_returns'],
                'total_work_time_seconds': metrics['total_work_time_seconds'],
                'total_review_time_seconds': metrics['total_review_time_seconds'],
                'total_cycle_time_seconds': metrics['total_cycle_time_seconds'],
                'total_lead_time_seconds': metrics['total_lead_time_seconds'],
                'workflow_complexity_score': metrics['workflow_complexity_score'],
                'rework_indicator': metrics['rework_indicator'],
                'direct_completion': metrics['direct_completion'],
                'last_updated_at': current_time
            })

        # Bulk update work_items
        if work_items_to_update:
            BulkOperations.bulk_update(db, 'work_items', work_items_to_update)
            logger.info(f"Updated workflow metrics for {len(work_items_to_update)} work items")

    def _calculate_enhanced_workflow_metrics(
        self, changelogs: List[Dict], status_categories: Dict[int, str]
    ) -> Dict[str, any]:
        """
        Calculate comprehensive workflow metrics from changelog data.

        Args:
            changelogs: List of changelog dicts (sorted by transition_change_date DESC)
            status_categories: Dict mapping status_id to category ('to do', 'in progress', 'done')

        Returns:
            Dictionary containing all enhanced workflow metrics
        """
        from app.core.utils import DateTimeHelper

        if not changelogs:
            return {
                'work_first_committed_at': None,
                'work_first_started_at': None,
                'work_last_started_at': None,
                'work_first_completed_at': None,
                'work_last_completed_at': None,
                'total_work_starts': 0,
                'total_completions': 0,
                'total_backlog_returns': 0,
                'total_work_time_seconds': 0.0,
                'total_review_time_seconds': 0.0,
                'total_cycle_time_seconds': 0.0,
                'total_lead_time_seconds': 0.0,
                'workflow_complexity_score': 0,
                'rework_indicator': False,
                'direct_completion': False
            }

        metrics = {
            'work_first_committed_at': None,
            'work_first_started_at': None,
            'work_last_started_at': None,
            'work_first_completed_at': None,
            'work_last_completed_at': None,
            'total_work_starts': 0,
            'total_completions': 0,
            'total_backlog_returns': 0,
            'total_work_time_seconds': 0.0,
            'total_review_time_seconds': 0.0,
            'total_cycle_time_seconds': 0.0,
            'total_lead_time_seconds': 0.0,
            'workflow_complexity_score': 0,
            'rework_indicator': False,
            'direct_completion': False
        }

        # Track time spent in each category
        time_tracking = {}

        # Process changelogs (already sorted DESC - newest first)
        for changelog in changelogs:
            transition_date = changelog.get('transition_change_date')
            to_status_id = changelog.get('to_status_id')
            time_in_status = changelog.get('time_in_status_seconds', 0.0) or 0.0

            if not transition_date or not to_status_id:
                continue

            to_category = status_categories.get(to_status_id)

            # Accumulate time in each category
            if to_category and time_in_status:
                time_tracking[to_category] = time_tracking.get(to_category, 0.0) + time_in_status

            # Count transitions and track timing milestones
            if to_category:
                # Commitment tracking (TO 'To Do' statuses)
                if to_category == 'to do':
                    metrics['total_backlog_returns'] += 1
                    # First commitment = oldest (always update, will be last in DESC order)
                    metrics['work_first_committed_at'] = transition_date

                # Work starts (TO 'In Progress')
                if to_category == 'in progress':
                    metrics['total_work_starts'] += 1
                    # Last work start = newest (first in DESC order) - only set once
                    if not metrics['work_last_started_at']:
                        metrics['work_last_started_at'] = transition_date
                    # First work start = oldest (always update, will be last in DESC order)
                    metrics['work_first_started_at'] = transition_date

                # Completions (TO 'Done')
                if to_category == 'done':
                    metrics['total_completions'] += 1
                    # Last completion = newest (first in DESC order) - only set once
                    if not metrics['work_last_completed_at']:
                        metrics['work_last_completed_at'] = transition_date
                    # First completion = oldest (always update, will be last in DESC order)
                    metrics['work_first_completed_at'] = transition_date

        # Aggregate time metrics
        metrics['total_work_time_seconds'] = time_tracking.get('in progress', 0.0)
        metrics['total_review_time_seconds'] = time_tracking.get('to do', 0.0)

        # Calculate cycle time (first start to last completion)
        if metrics['work_first_started_at'] and metrics['work_last_completed_at']:
            metrics['total_cycle_time_seconds'] = DateTimeHelper.calculate_time_difference_seconds_float(
                metrics['work_first_started_at'], metrics['work_last_completed_at']
            ) or 0.0

        # Calculate lead time (first commitment to last completion)
        if metrics['work_first_committed_at'] and metrics['work_last_completed_at']:
            metrics['total_lead_time_seconds'] = DateTimeHelper.calculate_time_difference_seconds_float(
                metrics['work_first_committed_at'], metrics['work_last_completed_at']
            ) or 0.0

        # Calculate pattern metrics
        metrics['workflow_complexity_score'] = (
            (metrics['total_backlog_returns'] * 2) +
            max(0, metrics['total_completions'] - 1)
        )

        metrics['rework_indicator'] = metrics['total_work_starts'] > 1

        # Calculate direct completion (went straight from creation to done without intermediate steps)
        metrics['direct_completion'] = (
            len(changelogs) == 1 and
            metrics['total_completions'] == 1 and
            metrics['total_work_starts'] == 0
        )

        return metrics

    def _process_jira_dev_status(self, raw_data_id: int, tenant_id: int, integration_id: int) -> bool:
        """
        Process Jira dev_status data from raw_extraction_data.

        Flow:
        1. Load raw data from raw_extraction_data table
        2. Extract PR links from dev_status
        3. Bulk insert/update work_items_prs_links table
        4. Queue for vectorization
        """
        try:
            logger.info(f"Processing jira_dev_status for raw_data_id={raw_data_id}")

            with self.get_db_session() as db:
                # Load raw data
                raw_data = self._get_raw_data(db, raw_data_id)
                if not raw_data:
                    logger.error(f"Raw data {raw_data_id} not found")
                    return False

                dev_status_data = raw_data.get('dev_status', [])
                if not dev_status_data:
                    logger.warning(f"No dev_status data found in raw_data_id={raw_data_id}")
                    return True

                logger.info(f"Processing dev_status for {len(dev_status_data)} issues")

                # Process dev_status
                pr_links_processed = self._process_dev_status_data(
                    db, dev_status_data, integration_id, tenant_id
                )

                logger.info(f"Processed {pr_links_processed} PR links from dev_status")
                return True

        except Exception as e:
            logger.error(f"Error processing jira_dev_status: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    def _process_dev_status_data(
        self, db, dev_status_data: List[Dict], integration_id: int, tenant_id: int
    ) -> int:
        """Process dev_status data and insert/update work_items_prs_links table."""
        from datetime import datetime, timezone

        # Get work_items map
        work_items_query = text("""
            SELECT key, id, external_id
            FROM work_items
            WHERE integration_id = :integration_id AND tenant_id = :tenant_id
        """)
        work_items_result = db.execute(work_items_query, {
            'integration_id': integration_id,
            'tenant_id': tenant_id
        }).fetchall()
        work_items_map = {row[0]: {'id': row[1], 'external_id': row[2]} for row in work_items_result}

        # Get existing PR links to avoid duplicates
        existing_links_query = text("""
            SELECT work_item_id, external_repo_id, pull_request_number
            FROM work_items_prs_links
            WHERE integration_id = :integration_id AND tenant_id = :tenant_id
        """)
        existing_result = db.execute(existing_links_query, {
            'integration_id': integration_id,
            'tenant_id': tenant_id
        }).fetchall()
        existing_links = {(row[0], row[1], row[2]) for row in existing_result}

        pr_links_to_insert = []
        current_time = datetime.now(timezone.utc)

        for dev_status_item in dev_status_data:
            try:
                issue_key = dev_status_item.get('issue_key')
                if not issue_key or issue_key not in work_items_map:
                    continue

                work_item_id = work_items_map[issue_key]['id']
                dev_details = dev_status_item.get('dev_details', {})

                # Extract PR links from dev_details
                pr_links = self._extract_pr_links_from_dev_status(dev_details)

                for pr_link in pr_links:
                    # Check if link already exists
                    link_key = (work_item_id, pr_link['repo_id'], pr_link['pr_number'])
                    if link_key in existing_links:
                        continue

                    pr_links_to_insert.append({
                        'integration_id': integration_id,
                        'tenant_id': tenant_id,
                        'work_item_id': work_item_id,
                        'external_repo_id': pr_link['repo_id'],
                        'repo_full_name': pr_link.get('repo_name', ''),
                        'pull_request_number': pr_link['pr_number'],
                        'branch_name': pr_link.get('branch'),
                        'commit_sha': pr_link.get('commit'),
                        'pr_status': pr_link.get('status'),
                        'active': True,
                        'created_at': current_time,
                        'last_updated_at': current_time
                    })

            except Exception as e:
                logger.error(f"Error processing dev_status for issue {dev_status_item.get('issue_key', 'unknown')}: {e}")
                continue

        # Bulk insert PR links
        if pr_links_to_insert:
            BulkOperations.bulk_insert(db, 'work_items_prs_links', pr_links_to_insert)
            logger.info(f"Inserted {len(pr_links_to_insert)} new PR links")

            # Fetch the inserted records with their generated IDs for vectorization
            inserted_links = self._fetch_inserted_pr_links(db, pr_links_to_insert, integration_id, tenant_id)

            # Queue for vectorization (using internal ID)
            if inserted_links:
                self._queue_entities_for_vectorization(tenant_id, 'work_items_prs_links', inserted_links)

        return len(pr_links_to_insert)

    def _fetch_inserted_pr_links(
        self, db, pr_links_to_insert: List[Dict], integration_id: int, tenant_id: int
    ) -> List[Dict]:
        """
        Fetch the inserted PR links with their generated IDs.

        This is needed because bulk_insert doesn't return the generated IDs,
        but we need them for vectorization queueing.

        Args:
            db: Database session
            pr_links_to_insert: List of PR link dicts that were just inserted
            integration_id: Integration ID
            tenant_id: Tenant ID

        Returns:
            List of PR link dicts with 'id' field populated
        """
        if not pr_links_to_insert:
            return []

        try:
            # Build a query to fetch all the inserted records
            # We'll match on (work_item_id, external_repo_id, pull_request_number) which is unique
            conditions = []
            for link in pr_links_to_insert:
                conditions.append(
                    f"(work_item_id = {link['work_item_id']} AND "
                    f"external_repo_id = '{link['external_repo_id']}' AND "
                    f"pull_request_number = {link['pull_request_number']})"
                )

            where_clause = " OR ".join(conditions)

            query = text(f"""
                SELECT id, work_item_id, external_repo_id, pull_request_number
                FROM work_items_prs_links
                WHERE integration_id = :integration_id
                  AND tenant_id = :tenant_id
                  AND ({where_clause})
            """)

            result = db.execute(query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id
            }).fetchall()

            # Convert to list of dicts with 'id' field
            fetched_links = [
                {
                    'id': row[0],
                    'work_item_id': row[1],
                    'external_repo_id': row[2],
                    'pull_request_number': row[3]
                }
                for row in result
            ]

            logger.info(f"Fetched {len(fetched_links)} PR links with IDs for vectorization")
            return fetched_links

        except Exception as e:
            logger.error(f"Error fetching inserted PR links: {e}")
            return []

    def _extract_pr_links_from_dev_status(self, dev_details: Dict) -> List[Dict]:
        """Extract PR links from Jira dev_status API response."""
        pr_links = []

        try:
            if not isinstance(dev_details, dict) or 'detail' not in dev_details:
                return pr_links

            for detail in dev_details['detail']:
                if not isinstance(detail, dict):
                    continue

                # Get pull requests from detail
                pull_requests = detail.get('pullRequests', [])
                for pr in pull_requests:
                    try:
                        # Extract PR information
                        pr_url = pr.get('url', '')
                        pr_id = pr.get('id', '')
                        pr_name = pr.get('name', '')
                        pr_status = pr.get('status', '')

                        # Parse PR number and repo from URL or name
                        # Example URL: https://github.com/wexinc/health-api/pull/123
                        pr_number = None
                        repo_name = ''
                        repo_id = ''

                        if pr_url:
                            parts = pr_url.split('/')
                            if len(parts) >= 2:
                                pr_number = int(parts[-1]) if parts[-1].isdigit() else None
                                if len(parts) >= 5:
                                    repo_name = f"{parts[-4]}/{parts[-3]}"
                                    repo_id = pr.get('repositoryId', repo_name)

                        if not pr_number:
                            # Try to extract from name (e.g., "#123")
                            if pr_name.startswith('#'):
                                pr_number = int(pr_name[1:]) if pr_name[1:].isdigit() else None

                        if pr_number:
                            pr_links.append({
                                'repo_id': repo_id or pr_id,
                                'repo_name': repo_name,
                                'pr_number': pr_number,
                                'branch': pr.get('source', {}).get('branch'),
                                'commit': pr.get('lastCommit', {}).get('id'),
                                'status': pr_status
                            })

                    except Exception as e:
                        logger.warning(f"Error parsing PR from dev_status: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error extracting PR links from dev_status: {e}")

        return pr_links

    def _parse_datetime(self, date_str: str):
        """Parse datetime string from Jira API."""
        if not date_str:
            return None

        try:
            from datetime import datetime
            # Jira returns ISO 8601 format: 2024-01-15T10:30:00.000+0000
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"Error parsing datetime '{date_str}': {e}")
            return None


