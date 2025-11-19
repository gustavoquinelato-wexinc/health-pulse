"""
Jira Transform Handler - Processes Jira-specific ETL data.

Handles all Jira message types:
- jira_custom_fields: Process custom fields discovery data from createmeta API
- jira_special_fields: Process special fields from field search API (e.g., development field)
- jira_projects_and_issue_types: Process projects and issue types
- jira_statuses_and_relationships: Process statuses and project relationships
- jira_issues_with_changelogs: Process individual work items with changelogs
- jira_dev_status: Process development status data
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy import text
from contextlib import contextmanager

from app.etl.workers.bulk_operations import BulkOperations
from app.models.unified_models import Project, Wit, CustomField
from app.core.logging_config import get_logger
from app.core.database import get_database, get_write_session
from app.core.utils import DateTimeHelper

logger = get_logger(__name__)


class JiraTransformHandler:
    """
    Handler for processing Jira-specific ETL data.

    This is a specialized handler (not a queue consumer) that processes
    Jira-specific transformation logic. It's called from TransformWorker
    which is the actual queue consumer and router.

    Uses dependency injection to receive WorkerStatusManager and QueueManager.
    """

    def __init__(self, status_manager=None, queue_manager=None):
        """
        Initialize Jira transform handler.

        Args:
            status_manager: WorkerStatusManager instance for sending status updates (injected by router)
            queue_manager: QueueManager instance for publishing to queues (injected by router)
        """
        self.database = get_database()
        self.status_manager = status_manager  # 🔑 Dependency injection
        self.queue_manager = queue_manager    # 🔑 Dependency injection
        logger.debug("Initialized JiraTransformHandler")

    @contextmanager
    def get_db_session(self):
        """
        Get a database session with automatic cleanup.

        Usage:
            with self.get_db_session() as session:
                # Use session for writes

        Note: This uses write session context. For read-only operations,
        consider using get_db_read_session() instead.
        """
        with self.database.get_write_session_context() as session:
            yield session

    @contextmanager
    def get_db_read_session(self):
        """
        Get a read-only database session with automatic cleanup.

        Usage:
            with self.get_db_read_session() as session:
                # Use session for reads only
        """
        with self.database.get_read_session_context() as session:
            yield session

    async def _send_worker_status(self, step: str, tenant_id: int, job_id: int,
                                   status: str, step_type: str = None):
        """
        Send worker status update using injected status manager.

        Args:
            step: ETL step name (e.g., 'extraction', 'transform', 'embedding')
            tenant_id: Tenant ID
            job_id: Job ID
            status: Status to send (e.g., 'running', 'finished', 'failed')
            step_type: Optional step type for logging (e.g., 'jira_projects_and_issue_types')
        """
        if self.status_manager:
            await self.status_manager.send_worker_status(
                step=step,
                tenant_id=tenant_id,
                job_id=job_id,
                status=status,
                step_type=step_type
            )
        else:
            logger.warning(f"Status manager not available - cannot send {status} status for {step_type}")

    async def process_jira_message(self, message_type: str, message: Dict[str, Any]) -> bool:
        """
        Route Jira transform messages to appropriate handler method.

        Args:
            message_type: Type of message (e.g., 'jira_projects_and_issue_types')
            message: Full message dict with structure:
                {
                    'type': str,
                    'provider': 'jira',
                    'tenant_id': int,
                    'integration_id': int,
                    'job_id': int,
                    'raw_data_id': int | None,
                    'token': str,
                    'first_item': bool,
                    'last_item': bool,
                    'last_job_item': bool,
                    ... other fields
                }

        Returns:
            bool: True if processing succeeded
        """
        try:
            # Extract common fields from message
            raw_data_id = message.get('raw_data_id')
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            first_item = message.get('first_item', False)
            last_item = message.get('last_item', False)
            token = message.get('token')

            logger.debug(f"🔄 [JIRA] Processing {message_type} for raw_data_id={raw_data_id} (first={first_item}, last={last_item})")

            # 🎯 HANDLE COMPLETION MESSAGE: raw_data_id=None signals completion
            if raw_data_id is None:
                logger.debug(f"🎯 [COMPLETION] Received completion message for {message_type}")
                return await self._handle_completion_message(message_type, message)

            # Route to appropriate handler based on message type
            if message_type == 'jira_custom_fields':
                return self._process_jira_custom_fields(raw_data_id, tenant_id, integration_id)
            elif message_type == 'jira_special_fields':
                return self._process_jira_special_fields(raw_data_id, tenant_id, integration_id)
            elif message_type == 'jira_projects_and_issue_types':
                return await self._process_jira_project_search(raw_data_id, tenant_id, integration_id, job_id, message)
            elif message_type == 'jira_statuses_and_relationships':
                return await self._process_jira_statuses_and_project_relationships(raw_data_id, tenant_id, integration_id, job_id, message)
            elif message_type == 'jira_issues_with_changelogs':
                return await self._process_jira_single_issue_changelog(raw_data_id, tenant_id, integration_id, job_id, message)
            elif message_type == 'jira_dev_status':
                return await self._process_jira_dev_status(raw_data_id, tenant_id, integration_id, job_id, message)
            else:
                logger.warning(f"Unknown Jira message type: {message_type}")
                return False

        except Exception as e:
            logger.error(f"Error processing Jira message type {message_type}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    # ============ COMPLETION MESSAGE HANDLING ============

    async def _handle_completion_message(self, message_type: str, message: Dict[str, Any]) -> bool:
        """
        Handle completion messages (raw_data_id=None) for Jira transform steps.

        Args:
            message_type: Type of completion message
            message: Full message dict

        Returns:
            bool: True if completion message handled successfully
        """
        tenant_id = message.get('tenant_id')
        job_id = message.get('job_id')
        integration_id = message.get('integration_id')
        last_item = message.get('last_item', False)
        token = message.get('token')

        # Send WebSocket status: transform worker finished (on last_item)
        if last_item and job_id:
            try:
                await self._send_worker_status("transform", tenant_id, job_id, "finished", message_type)
                logger.debug(f"✅ Transform worker marked as finished for {message_type} (completion message)")
            except Exception as e:
                logger.error(f"❌ Error sending finished status for {message_type}: {e}")

        # Handle different completion message types
        if message_type == 'jira_dev_status':
            logger.debug(f"🎯 [COMPLETION] Processing jira_dev_status completion message")
            self._queue_entities_for_embedding(
                tenant_id=tenant_id,
                table_name='work_items_prs_links',
                entities=[],  # Empty list - signals completion
                job_id=job_id,
                message_type='jira_dev_status',
                integration_id=integration_id,
                provider=message.get('provider', 'jira'),
                last_sync_date=message.get('last_sync_date'),
                first_item=message.get('first_item', False),
                last_item=message.get('last_item', False),
                last_job_item=message.get('last_job_item', False),
                token=token
            )
            logger.debug(f"🎯 [COMPLETION] jira_dev_status completion message forwarded to embedding")
            return True

        elif message_type == 'jira_issues_with_changelogs':
            logger.debug(f"🎯 [COMPLETION] Processing jira_issues_with_changelogs completion message")
            self._queue_entities_for_embedding(
                tenant_id=tenant_id,
                table_name='work_items',
                entities=[],  # Empty list - signals completion
                job_id=job_id,
                message_type='jira_issues_with_changelogs',
                integration_id=integration_id,
                provider=message.get('provider', 'jira'),
                last_sync_date=message.get('last_sync_date'),
                first_item=message.get('first_item', False),
                last_item=message.get('last_item', False),
                last_job_item=message.get('last_job_item', False),
                token=token
            )
            logger.debug(f"🎯 [COMPLETION] jira_issues_with_changelogs completion message forwarded to embedding")
            return True

        else:
            logger.warning(f"⚠️ [COMPLETION] Unknown Jira completion message type: {message_type}")
            return False

    # ============ JIRA PROCESSING METHODS ============
    # All Jira-specific processing methods extracted from transform_worker.py

    async def _process_jira_project_search(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
        """
        Process Jira projects and issue types from raw_extraction_data.

        This method:
        1. Retrieves raw project data from raw_extraction_data table
        2. Processes projects and issue types
        3. Saves to projects and wits tables
        4. Creates project-wit relationships
        5. Queues entities for embedding

        Args:
            raw_data_id: ID of the raw data record
            tenant_id: Tenant ID
            integration_id: Integration ID
            job_id: ETL job ID
            message: Full message dict with flags

        Returns:
            bool: True if processing succeeded
        """
        try:
            # Extract message flags
            first_item = message.get('first_item', False) if message else False
            last_item = message.get('last_item', False) if message else False
            last_job_item = message.get('last_job_item', False) if message else False
            provider = message.get('provider', 'jira') if message else 'jira'
            old_last_sync_date = message.get('old_last_sync_date') if message else None  # 🔑 From extraction worker
            new_last_sync_date = message.get('new_last_sync_date') if message else None
            token = message.get('token') if message else None

            logger.info(f"🔄 Processing jira_projects_and_issue_types (raw_data_id={raw_data_id}, first={first_item}, last={last_item})")

            database = get_database()

            # Fetch raw data
            with database.get_read_session_context() as db:
                query = text("""
                    SELECT raw_data
                    FROM raw_extraction_data
                    WHERE id = :raw_data_id
                """)
                result = db.execute(query, {'raw_data_id': raw_data_id}).fetchone()

                if not result or not result[0]:
                    logger.error(f"No raw data found for raw_data_id={raw_data_id}")
                    return False

                projects_data = result[0]  # This is already a list from JSONB

            if not isinstance(projects_data, list):
                logger.error(f"Expected list of projects, got {type(projects_data)}")
                return False

            logger.debug(f"📊 Found {len(projects_data)} projects to process")

            # Process projects and issue types
            with database.get_write_session_context() as db:
                # Get existing data
                existing_projects = self._get_existing_projects(db, tenant_id, integration_id)
                existing_wits = self._get_existing_wits(db, tenant_id, integration_id)
                existing_relationships = self._get_existing_project_wit_relationships(db, tenant_id)

                # Accumulators for bulk operations
                projects_to_insert = []
                projects_to_update = []
                wits_to_insert = []
                wits_to_update = []
                project_wit_relationships = []

                # Process each project
                for project_data in projects_data:
                    result = self._process_project_data(
                        project_data, tenant_id, integration_id,
                        existing_projects, existing_wits, {},  # No custom fields for project search
                        existing_relationships, {}  # No global custom fields
                    )

                    projects_to_insert.extend(result.get('projects_to_insert', []))
                    projects_to_update.extend(result.get('projects_to_update', []))
                    wits_to_insert.extend(result.get('wits_to_insert', []))
                    wits_to_update.extend(result.get('wits_to_update', []))
                    project_wit_relationships.extend(result.get('project_wit_relationships', []))

                # Perform bulk operations
                self._perform_bulk_operations(
                    db, projects_to_insert, projects_to_update,
                    wits_to_insert, wits_to_update,
                    [], [],  # No custom fields for project search
                    project_wit_relationships
                )

                # Note: project-wit relationships are handled by _perform_bulk_operations

                db.commit()
                logger.debug(f"✅ Committed projects and issue types to database")

            # Queue entities for embedding (after commit)
            # Queue projects - loop and queue individual projects
            has_projects = bool(projects_to_insert or projects_to_update)
            has_wits = bool(wits_to_insert or wits_to_update)

            if has_projects:
                all_projects = projects_to_insert + projects_to_update
                self._queue_entities_for_embedding(
                    tenant_id, 'projects', all_projects, job_id,
                    message_type='jira_projects_and_issue_types',
                    integration_id=integration_id,
                    provider=provider,
                    old_last_sync_date=old_last_sync_date,  # 🔑 Forward old_last_sync_date
                    new_last_sync_date=new_last_sync_date,
                    first_item=first_item,  # First project gets first_item=True
                    last_item=False if has_wits else last_item,  # Only last if no WITs to follow
                    last_job_item=False if has_wits else last_job_item,  # Only last_job_item if no WITs
                    token=token
                )

            # Queue WITs - loop and queue individual WITs, last WIT gets last_item=True
            if has_wits:
                all_wits = wits_to_insert + wits_to_update
                self._queue_entities_for_embedding(
                    tenant_id, 'wits', all_wits, job_id,
                    message_type='jira_projects_and_issue_types',
                    integration_id=integration_id,
                    provider=provider,
                    old_last_sync_date=old_last_sync_date,  # 🔑 Forward old_last_sync_date
                    new_last_sync_date=new_last_sync_date,
                    first_item=first_item if not has_projects else False,  # First WIT gets first_item=True only if no projects
                    last_item=last_item,  # 🔑 Last WIT gets last_item=True
                    last_job_item=last_job_item,  # 🔑 Forward last_job_item flag
                    token=token
                )

            # 🎯 HANDLE NO UPDATES: If no projects and no WITs, mark both transform and embedding as finished
            if not has_projects and not has_wits and last_item:
                logger.info(f"🎯 [PROJECTS] No updates found - marking transform and embedding as finished")

                # 🎯 OPTION 1: Mark both steps as finished directly (current approach)
                # This avoids sending unnecessary completion messages through the queue
                await self._send_worker_status('transform', tenant_id, job_id, 'finished', 'jira_projects_and_issue_types')
                await self._send_worker_status('embedding', tenant_id, job_id, 'finished', 'jira_projects_and_issue_types')
                logger.debug(f"✅ [PROJECTS] Both transform and embedding steps marked as finished (no data to process)")

                # 🎯 OPTION 2: Send completion message to embedding (uncomment if you want the message to flow through embedding worker)
                # self._queue_entities_for_embedding(
                #     tenant_id=tenant_id,
                #     table_name='projects',  # Use projects table as the step identifier
                #     entities=[],  # Empty list signals completion
                #     job_id=job_id,
                #     message_type='jira_projects_and_issue_types',
                #     integration_id=integration_id,
                #     provider=provider,
                #     old_last_sync_date=old_last_sync_date,
                #     new_last_sync_date=new_last_sync_date,
                #     first_item=first_item,  # Preserve first_item flag
                #     last_item=last_item,  # Preserve last_item flag
                #     last_job_item=last_job_item,  # Preserve last_job_item flag
                #     token=token
                # )
                # logger.debug(f"✅ [PROJECTS] Completion message sent to embedding (no data to process)")
            # ✅ Send WebSocket status update when last_item=True (only if we have data to process)
            elif last_item and job_id:
                logger.info(f"🏁 [PROJECTS] Sending 'finished' status for transform step")
                await self._send_worker_status('transform', tenant_id, job_id, 'finished', 'jira_projects_and_issue_types')
                logger.debug(f"✅ [PROJECTS] Transform step marked as finished and WebSocket notification sent")

            logger.info(f"✅ [PROJECTS] Completed projects and issue types processing (raw_data_id={raw_data_id})")
            return True

        except Exception as e:
            logger.error(f"Error processing jira_projects_and_issue_types: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
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
                # Jira API returns 'values' array, not 'projects'
                projects_data = createmeta_response.get('values', createmeta_response.get('projects', []))

                if not projects_data:
                    logger.warning(f"No projects found in raw data: {raw_data_id}")
                    return True  # Not an error, just empty data

                logger.debug(f"🔍 DEBUG: Processing {len(projects_data)} projects from createmeta")

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

                logger.debug(f"🔍 DEBUG: Found {len(unique_issue_types)} unique issue types across all projects")
                logger.debug(f"🔍 DEBUG: Expected {total_relationships} project-wit relationships")
                logger.debug(f"🔍 DEBUG: Unique issue type IDs: {sorted(unique_issue_types)}")
                
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

                logger.debug(f"🔍 DEBUG: Found {len(existing_projects)} existing projects")
                logger.debug(f"🔍 DEBUG: Found {len(existing_wits)} existing WITs: {list(existing_wits.keys())}")
                logger.debug(f"🔍 DEBUG: Found {len(existing_custom_fields)} existing custom fields")
                logger.debug(f"🔍 DEBUG: Found {len(existing_relationships)} existing relationships")

                # Collect all unique custom fields globally (not per project)
                global_custom_fields = {}  # field_key -> field_info

                # Process each project
                logger.debug(f"🔍 DEBUG: Starting to process {len(projects_data)} projects individually...")
                for i, project_data in enumerate(projects_data):
                    project_key = project_data.get('key', 'UNKNOWN')
                    project_name = project_data.get('name', 'UNKNOWN')
                    # Handle both camelCase (project search API) and lowercase (createmeta API)
                    issue_types_count = len(project_data.get('issueTypes', project_data.get('issuetypes', [])))

                    logger.debug(f"🔍 DEBUG: Processing project {i+1}/{len(projects_data)}: {project_key} ({project_name}) with {issue_types_count} issue types")

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

                        logger.debug(f"🔍 DEBUG: After processing {project_key}: Total WITs to insert: {len(wits_to_insert)}, relationships: {len(project_wit_relationships)}")
                    else:
                        logger.warning(f"🔍 DEBUG: No result returned for project {project_key}")

                logger.debug(f"🔍 DEBUG: Final totals after all projects:")
                logger.debug(f"🔍 DEBUG:   - Projects to insert: {len(projects_to_insert)}")
                logger.debug(f"🔍 DEBUG:   - Projects to update: {len(projects_to_update)}")
                logger.debug(f"🔍 DEBUG:   - WITs to insert (before dedup): {len(wits_to_insert)}")
                logger.debug(f"🔍 DEBUG:   - WITs to update: {len(wits_to_update)}")
                logger.debug(f"🔍 DEBUG:   - Project-wit relationships: {len(project_wit_relationships)}")

                # 🔧 FIX: Deduplicate WITs globally by external_id
                # The same WIT (e.g., "Story" with id "10001") appears in multiple projects
                # We should only insert each unique WIT once
                unique_wits_to_insert = {}
                for wit in wits_to_insert:
                    external_id = wit.get('external_id')
                    if external_id and external_id not in unique_wits_to_insert:
                        unique_wits_to_insert[external_id] = wit

                wits_to_insert = list(unique_wits_to_insert.values())

                logger.debug(f"🔍 DEBUG: After WIT deduplication:")
                logger.debug(f"🔍 DEBUG:   - Unique WITs to insert: {len(wits_to_insert)}")
                logger.debug(f"🔍 DEBUG:   - WIT external IDs: {list(unique_wits_to_insert.keys())}")

                # Show WIT names for debugging
                for wit in wits_to_insert:
                    logger.debug(f"🔍 DEBUG:   - WIT to insert: {wit.get('original_name')} (id: {wit.get('external_id')})")

                # Also deduplicate WITs to update
                unique_wits_to_update = {}
                for wit in wits_to_update:
                    wit_id = wit.get('id')  # Database ID for updates
                    if wit_id and wit_id not in unique_wits_to_update:
                        unique_wits_to_update[wit_id] = wit

                wits_to_update = list(unique_wits_to_update.values())
                logger.debug(f"🔍 DEBUG:   - Unique WITs to update: {len(wits_to_update)}")

                # Process global custom fields once
                logger.debug(f"Processing {len(global_custom_fields)} unique custom fields globally")
                for field_key, field_info in global_custom_fields.items():
                    cf_result = self._process_custom_field_data(
                        field_key, field_info, tenant_id, integration_id,
                        existing_custom_fields
                    )
                    if cf_result:
                        custom_fields_to_insert.extend(cf_result.get('custom_fields_to_insert', []))
                        custom_fields_to_update.extend(cf_result.get('custom_fields_to_update', []))

                logger.debug(f"Custom fields to insert: {len(custom_fields_to_insert)}, to update: {len(custom_fields_to_update)}")

                # 4. Perform bulk operations (projects and WITs first)
                bulk_result = self._perform_bulk_operations(
                    session, projects_to_insert, projects_to_update,
                    wits_to_insert, wits_to_update,
                    custom_fields_to_insert, custom_fields_to_update,
                    []  # Empty relationships for now
                )

                # 5. Create project-wit relationships after projects and WITs are saved
                if project_wit_relationships:
                    logger.debug(f"Creating {len(project_wit_relationships)} project-wit relationships")
                    relationships_created = self._create_project_wit_relationships_for_search(
                        session, project_wit_relationships, integration_id, tenant_id
                    )
                    logger.debug(f"Created {relationships_created} project-wit relationships")

                # 6. Auto-map special fields if they exist
                import os
                development_field_id = os.getenv('JIRA_DEVELOPMENT_FIELD_ID', 'customfield_10000')
                sprints_field_id = os.getenv('JIRA_SPRINTS_FIELD_ID', 'customfield_10021')

                self._auto_map_special_field(session, tenant_id, integration_id, development_field_id, 'development_field_id')
                self._auto_map_special_field(session, tenant_id, integration_id, sprints_field_id, 'sprints_field_id')

                # 7. Update raw data status
                self._update_raw_data_status(session, raw_data_id, 'completed')

                # Commit all changes
                session.commit()

                # NOTE: /createmeta is for custom fields discovery only
                # Projects and WITs are NOT queued for embedding here
                # Only /project/search should queue for embedding

                logger.debug(f"Successfully processed custom fields for raw_data_id={raw_data_id}")
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
            from app.core.utils import DateTimeHelper
            now = DateTimeHelper.now_default()

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

                logger.debug(f"Processing special field: {field_id} - {field_name}")

                # 3. Check if field already exists
                existing_custom_fields = self._get_existing_custom_fields(session, tenant_id, integration_id)

                # 4. Insert or update custom field
                if field_id in existing_custom_fields:
                    # Update existing field
                    logger.debug(f"Special field {field_id} already exists, updating")
                    update_query = text("""
                        UPDATE custom_fields
                        SET name = :name,
                            field_type = :field_type,
                            last_updated_at = :now
                        WHERE external_id = :external_id
                        AND tenant_id = :tenant_id
                        AND integration_id = :integration_id
                    """)
                    session.execute(update_query, {
                        'name': field_name,
                        'field_type': field_type,
                        'external_id': field_id,
                        'tenant_id': tenant_id,
                        'integration_id': integration_id,
                        'now': now
                    })
                else:
                    # Insert new field
                    logger.debug(f"Inserting new special field: {field_id} - {field_name}")
                    insert_query = text("""
                        INSERT INTO custom_fields (
                            external_id, name, field_type, operations,
                            tenant_id, integration_id, active, created_at, last_updated_at
                        ) VALUES (
                            :external_id, :name, :field_type, :operations,
                            :tenant_id, :integration_id, TRUE, :created_at, :last_updated_at
                        )
                    """)
                    session.execute(insert_query, {
                        'external_id': field_id,
                        'name': field_name,
                        'field_type': field_type,
                        'operations': None,  # No operations for special fields
                        'tenant_id': tenant_id,
                        'integration_id': integration_id,
                        'created_at': now,
                        'last_updated_at': now
                    })

                # 5. Auto-map special fields if this is a special field
                import os
                development_field_id = os.getenv('JIRA_DEVELOPMENT_FIELD_ID', 'customfield_10000')
                sprints_field_id = os.getenv('JIRA_SPRINTS_FIELD_ID', 'customfield_10021')

                if field_id == development_field_id:
                    self._auto_map_special_field(session, tenant_id, integration_id, field_id, 'development_field_id')
                elif field_id == sprints_field_id:
                    self._auto_map_special_field(session, tenant_id, integration_id, field_id, 'sprints_field_id')

                # 6. Update raw data status
                self._update_raw_data_status(session, raw_data_id, 'completed')

                # Commit all changes
                session.commit()

                logger.debug(f"Successfully processed special field for raw_data_id={raw_data_id}")
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
            from app.core.utils import DateTimeHelper
            now = DateTimeHelper.now_default()

            query = text("""
                UPDATE raw_extraction_data
                SET status = :status, last_updated_at = :now
                WHERE id = :raw_data_id
            """)
            session.execute(query, {'raw_data_id': raw_data_id, 'status': status, 'now': now})
        except Exception as e:
            logger.error(f"Error updating raw data status: {e}")
            raise

    def _auto_map_special_field(self, session, tenant_id: int, integration_id: int,
                                 field_external_id: str, mapping_column: str):
        """
        Auto-map special field to custom_fields_mapping table.
        This is called after a special field is saved to custom_fields table.

        Args:
            session: Database session
            tenant_id: Tenant ID
            integration_id: Integration ID
            field_external_id: External ID of the field (e.g., 'customfield_10000')
            mapping_column: Column name in custom_fields_mapping (e.g., 'development_field_id', 'sprints_field_id')
        """
        try:
            from app.core.utils import DateTimeHelper

            now = DateTimeHelper.now_default()

            # Check if special field exists in custom_fields
            check_query = text("""
                SELECT id FROM custom_fields
                WHERE external_id = :external_id
                AND tenant_id = :tenant_id
                AND integration_id = :integration_id
                AND active = true
            """)
            result = session.execute(check_query, {
                'external_id': field_external_id,
                'tenant_id': tenant_id,
                'integration_id': integration_id
            }).fetchone()

            if not result:
                logger.debug(f"Special field {field_external_id} not found, skipping auto-mapping")
                return

            custom_field_db_id = result[0]
            logger.debug(f"Found special field {field_external_id} with ID {custom_field_db_id}")

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
                update_query = text(f"""
                    UPDATE custom_fields_mapping
                    SET {mapping_column} = :field_id,
                        last_updated_at = :now
                    WHERE tenant_id = :tenant_id
                    AND integration_id = :integration_id
                """)
                session.execute(update_query, {
                    'field_id': custom_field_db_id,
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'now': now
                })
                logger.debug(f"Auto-mapped special field {field_external_id} to {mapping_column}")
            else:
                # Create new mapping record
                insert_query = text(f"""
                    INSERT INTO custom_fields_mapping (
                        tenant_id, integration_id, {mapping_column},
                        active, created_at, last_updated_at
                    ) VALUES (
                        :tenant_id, :integration_id, :field_id,
                        true, :created_at, :last_updated_at
                    )
                """)
                session.execute(insert_query, {
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'field_id': custom_field_db_id,
                    'created_at': now,
                    'last_updated_at': now
                })
                logger.debug(f"Created custom_fields_mapping and auto-mapped special field {field_external_id} to {mapping_column}")

        except Exception as e:
            logger.error(f"Error auto-mapping special field {field_external_id}: {e}")
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

    def _create_project_wit_relationships_for_search(self, session, project_wit_relationships: List[tuple], integration_id: int, tenant_id: int) -> int:
        """
        Create project-wit relationships from external IDs.

        Args:
            session: Database session
            project_wit_relationships: List of (project_external_id, wit_external_id) tuples
            integration_id: Integration ID
            tenant_id: Tenant ID

        Returns:
            Number of relationships created
        """
        try:
            logger.info(f"🔍 DEBUG: _create_project_wit_relationships_for_search called with {len(project_wit_relationships)} relationships")

            if not project_wit_relationships:
                logger.debug("No project-wit relationships to create")
                return 0

            # Get mapping of external_id -> internal_id for projects
            logger.debug("🔍 DEBUG: Querying projects mapping...")
            projects_query = text("""
                SELECT external_id, id
                FROM projects
                WHERE integration_id = :integration_id AND tenant_id = :tenant_id AND active = true
            """)
            projects_result = session.execute(projects_query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id
            }).fetchall()
            projects_lookup = {row[0]: row[1] for row in projects_result}
            logger.debug(f"🔍 DEBUG: Found {len(projects_lookup)} projects")

            # Get mapping of external_id -> internal_id for WITs
            logger.debug("🔍 DEBUG: Querying WITs mapping...")
            wits_query = text("""
                SELECT external_id, id
                FROM wits
                WHERE integration_id = :integration_id AND tenant_id = :tenant_id AND active = true
            """)
            wits_result = session.execute(wits_query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id
            }).fetchall()
            wits_lookup = {row[0]: row[1] for row in wits_result}
            logger.debug(f"🔍 DEBUG: Found {len(wits_lookup)} WITs")

            # Get existing relationships
            logger.debug("🔍 DEBUG: Getting existing relationships...")
            existing_relationships = self._get_existing_project_wit_relationships(session, tenant_id)
            logger.debug(f"🔍 DEBUG: Found {len(existing_relationships)} existing relationships")

            # Build relationships to insert
            logger.debug("🔍 DEBUG: Building relationships to insert...")
            relationships_to_insert = []
            for project_external_id, wit_external_id in project_wit_relationships:
                # Convert to strings for database lookup (external_id is VARCHAR in DB)
                project_external_id_str = str(project_external_id)
                wit_external_id_str = str(wit_external_id)

                logger.debug(f"🔍 DEBUG: Looking up project {project_external_id_str} and wit {wit_external_id_str}")

                project_id = projects_lookup.get(project_external_id_str)
                wit_id = wits_lookup.get(wit_external_id_str)

                if not project_id:
                    logger.warning(f"Project with external_id {project_external_id_str} not found in lookup")
                    continue

                if not wit_id:
                    logger.warning(f"WIT with external_id {wit_external_id_str} not found in lookup")
                    continue

                # Check if relationship already exists
                if (project_id, wit_id) not in existing_relationships:
                    relationships_to_insert.append((project_id, wit_id))
                    logger.debug(f"🔍 DEBUG: Added relationship to insert: project_id={project_id}, wit_id={wit_id}")

            logger.debug(f"🔍 DEBUG: Built {len(relationships_to_insert)} relationships to insert")

            if not relationships_to_insert:
                logger.debug("No new project-wit relationships to create")
                return 0

            # Bulk insert relationships
            logger.debug(f"🔍 DEBUG: Starting bulk insert of {len(relationships_to_insert)} relationships...")
            BulkOperations.bulk_insert_relationships(session, 'projects_wits', relationships_to_insert)
            logger.debug(f"🔍 DEBUG: Bulk insert completed")

            logger.info(f"Created {len(relationships_to_insert)} project-wit relationships")
            return len(relationships_to_insert)

        except Exception as e:
            logger.error(f"Error creating project-wit relationships: {e}", exc_info=True)
            raise

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

            logger.debug(f"🔍 DEBUG: _process_project_data - Processing {project_key} ({project_name}) with {len(issue_types)} issue types")

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
                        'last_updated_at': DateTimeHelper.now_default()
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
                    'created_at': DateTimeHelper.now_default(),
                    'last_updated_at': DateTimeHelper.now_default()
                }
                result['projects_to_insert'].append(project_insert_data)
                project_id = None  # Will be set after insert

            # Process issue types (WITs) and collect unique custom fields per project
            # Handle both camelCase (project search API) and lowercase (createmeta API)
            issue_types = project_data.get('issueTypes', project_data.get('issuetypes', []))
            unique_custom_fields = {}  # field_key -> field_info (deduplicated)
            project_wit_external_ids = []  # Store WIT external IDs for this project

            logger.debug(f"🔍 DEBUG: Processing {len(issue_types)} issue types for project {project_key}")

            for i, issue_type in enumerate(issue_types):
                wit_external_id = issue_type.get('id')
                wit_name = issue_type.get('name', 'UNKNOWN')

                logger.debug(f"🔍 DEBUG: Processing issue type {i+1}/{len(issue_types)}: {wit_name} (id: {wit_external_id})")

                if wit_external_id:
                    project_wit_external_ids.append(wit_external_id)
                    logger.debug(f"🔍 DEBUG: Added WIT external ID {wit_external_id} to project {project_key}")

                wit_result = self._process_wit_data(
                    issue_type, tenant_id, integration_id, existing_wits
                )
                if wit_result:
                    wits_to_insert = wit_result.get('wits_to_insert', [])
                    wits_to_update = wit_result.get('wits_to_update', [])

                    logger.debug(f"🔍 DEBUG: WIT result for {wit_name}: {len(wits_to_insert)} to insert, {len(wits_to_update)} to update")

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
            logger.debug(f"🔍 DEBUG: Creating {len(project_wit_external_ids)} project-wit relationships for project {project_key}")
            logger.debug(f"🔍 DEBUG: WIT external IDs for {project_key}: {project_wit_external_ids}")

            for wit_external_id in project_wit_external_ids:
                relationship = (project_external_id, wit_external_id)
                result['project_wit_relationships'].append(relationship)
                logger.debug(f"🔍 DEBUG: Added relationship: project {project_external_id} -> wit {wit_external_id}")

            # Add unique custom fields from this project to global collection
            for field_key, field_info in unique_custom_fields.items():
                # Keep the first occurrence globally (across all projects)
                if field_key not in global_custom_fields:
                    global_custom_fields[field_key] = field_info

            logger.debug(f"🔍 DEBUG: Project {project_key} summary:")
            logger.debug(f"🔍 DEBUG:   - WITs to insert: {len(result['wits_to_insert'])}")
            logger.debug(f"🔍 DEBUG:   - WITs to update: {len(result['wits_to_update'])}")
            logger.debug(f"🔍 DEBUG:   - Project-wit relationships: {len(result['project_wit_relationships'])}")
            logger.debug(f"🔍 DEBUG:   - Unique custom fields: {len(unique_custom_fields)}")
            logger.debug(f"🔍 DEBUG:   - Relationship details: {result['project_wit_relationships']}")

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

            logger.debug(f"🔍 DEBUG: _process_wit_data - Processing WIT: {wit_name} (id: {wit_external_id})")

            if not all([wit_external_id, wit_name]):
                logger.warning(f"🔍 DEBUG: Incomplete WIT data: external_id={wit_external_id}, name={wit_name}")
                return result

            # Lookup wits_mapping_id from wits_mappings table
            wits_mapping_id = self._lookup_wit_mapping_id(wit_name, tenant_id)
            if wits_mapping_id:
                logger.debug(f"🔍 DEBUG: Found wits_mapping_id={wits_mapping_id} for WIT '{wit_name}'")
            else:
                logger.debug(f"🔍 DEBUG: No wits_mapping found for WIT '{wit_name}' - will be set to NULL")

            if wit_external_id in existing_wits:
                # Check if WIT needs update
                existing_wit = existing_wits[wit_external_id]
                logger.debug(f"🔍 DEBUG: WIT {wit_name} already exists, checking for updates...")

                if (existing_wit.original_name != wit_name or
                    existing_wit.description != wit_description or
                    existing_wit.hierarchy_level != hierarchy_level or
                    existing_wit.wits_mapping_id != wits_mapping_id):
                    logger.debug(f"🔍 DEBUG: WIT {wit_name} needs update")
                    result['wits_to_update'].append({
                        'id': existing_wit.id,
                        'external_id': wit_external_id,  # Include for queueing
                        'original_name': wit_name,
                        'description': wit_description,
                        'hierarchy_level': hierarchy_level,
                        'wits_mapping_id': wits_mapping_id,
                        'last_updated_at': DateTimeHelper.now_default()
                    })
                else:
                    logger.debug(f"🔍 DEBUG: WIT {wit_name} is up to date, no update needed")
            else:
                # New WIT
                logger.debug(f"🔍 DEBUG: WIT {wit_name} is new, adding to insert list")
                wit_insert_data = {
                    'external_id': wit_external_id,
                    'original_name': wit_name,
                    'description': wit_description,
                    'hierarchy_level': hierarchy_level,
                    'wits_mapping_id': wits_mapping_id,
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'active': True,
                    'created_at': DateTimeHelper.now_default(),
                    'last_updated_at': DateTimeHelper.now_default()
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
                        'last_updated_at': DateTimeHelper.now_default()
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
                    'created_at': DateTimeHelper.now_default(),
                    'last_updated_at': DateTimeHelper.now_default()
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
                logger.debug(f"Inserted {len(projects_to_insert)} projects")

            # 2. Bulk update projects
            if projects_to_update:
                BulkOperations.bulk_update(session, 'projects', projects_to_update)
                logger.debug(f"Updated {len(projects_to_update)} projects")

            # 3. Bulk insert WITs
            if wits_to_insert:
                BulkOperations.bulk_insert(session, 'wits', wits_to_insert)
                logger.debug(f"Inserted {len(wits_to_insert)} WITs")

            # 4. Bulk update WITs
            if wits_to_update:
                BulkOperations.bulk_update(session, 'wits', wits_to_update)
                logger.debug(f"Updated {len(wits_to_update)} WITs")

            # 5. Bulk insert custom fields (global, no project relationship)
            if custom_fields_to_insert:
                # Deduplicate by external_id to avoid unique constraint violations
                unique_custom_fields = {}
                for cf in custom_fields_to_insert:
                    external_id = cf.get('external_id')
                    if external_id and external_id not in unique_custom_fields:
                        unique_custom_fields[external_id] = cf

                deduplicated_custom_fields = list(unique_custom_fields.values())
                if deduplicated_custom_fields:
                    BulkOperations.bulk_insert(session, 'custom_fields', deduplicated_custom_fields)
                    logger.debug(f"Inserted {len(deduplicated_custom_fields)} custom fields (deduplicated from {len(custom_fields_to_insert)})")
                # Note: Custom fields are not vectorized (they're metadata)

            # 6. Bulk update custom fields
            if custom_fields_to_update:
                BulkOperations.bulk_update(session, 'custom_fields', custom_fields_to_update)
                logger.debug(f"Updated {len(custom_fields_to_update)} custom fields")
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

    async def _process_jira_statuses_and_project_relationships(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
        """
        Process statuses and project relationships from raw data.

        This function:
        1. Retrieves raw data from raw_extraction_data table
        2. Processes statuses and saves to statuses table with mapping links
        3. Processes project-status relationships and saves to projects_statuses table
        4. Returns success status
        """
        try:
            logger.info(f"🏁 [STATUSES] Starting statuses and project relationships processing (raw_data_id={raw_data_id})")

            # NOTE: Status updates are handled by TransformWorker router (lines 138-148, 276-283)
            # Do NOT send status updates from handler to avoid event loop conflicts

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

                    logger.debug(f"Processing individual project {project_key} with {len(project_statuses_response)} issue types")

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

                logger.debug(f"Processing {len(statuses_data)} statuses and {len(project_statuses_data)} project relationships")

                # Process statuses and project relationships (returns entities for vectorization)
                statuses_result = self._process_statuses_data(db, statuses_data, integration_id, tenant_id)
                relationships_processed = self._process_project_status_relationships_data(db, project_statuses_data, integration_id, tenant_id)

                # Update raw data status to completed
                from app.core.utils import DateTimeHelper
                now = DateTimeHelper.now_default()

                update_query = text("""
                    UPDATE raw_extraction_data
                    SET status = 'completed',
                        last_updated_at = :now,
                        error_details = NULL
                    WHERE id = :raw_data_id
                """)
                db.execute(update_query, {'raw_data_id': raw_data_id, 'now': now})

                # Commit all changes BEFORE queueing for vectorization
                db.commit()

                # Queue statuses for embedding AFTER commit
                # Get message info for forwarding
                provider = message.get('provider') if message else 'jira'
                new_last_sync_date = message.get('new_last_sync_date') if message else None

                # 🎯 NEW LOGIC: Only queue to embedding when last_item=True
                # This ensures we process all projects first, then query all distinct statuses once
                # This avoids duplicate embeddings for the same status across different projects

                statuses_processed = statuses_result['count']
                logger.debug(f"Successfully processed {statuses_processed} statuses and {relationships_processed} project relationships")

                # 🎯 DEBUG: Log message details
                logger.debug(f"🎯 [STATUSES] Message check: message={message is not None}, last_item={message.get('last_item') if message else 'N/A'}")

                if message and message.get('last_item'):
                    logger.debug(f"🎯 [STATUSES] Last item received - checking for updated statuses")

                    # Get message info for forwarding
                    provider = message.get('provider') if message else 'jira'
                    old_last_sync_date = message.get('old_last_sync_date') if message else None  # 🔑 From extraction worker
                    new_last_sync_date = message.get('new_last_sync_date') if message else None  # 🔑 Extraction start time
                    last_job_item = message.get('last_job_item', False)
                    first_item_flag = message.get('first_item', False)
                    token = message.get('token')  # 🔑 Extract token from message

                    # 🎯 Query statuses updated AFTER new_last_sync_date
                    # This ensures we only queue statuses that were actually updated during this extraction
                    if new_last_sync_date:
                        logger.debug(f"🎯 [STATUSES] Querying statuses updated after {new_last_sync_date}")
                        statuses_query = text("""
                            SELECT DISTINCT external_id
                            FROM statuses
                            WHERE tenant_id = :tenant_id
                              AND integration_id = :integration_id
                              AND last_updated_at > :new_last_sync_date
                            ORDER BY external_id
                        """)

                        with self.get_db_session() as db_read:
                            status_rows = db_read.execute(statuses_query, {
                                'tenant_id': tenant_id,
                                'integration_id': integration_id,
                                'new_last_sync_date': new_last_sync_date
                            }).fetchall()
                    else:
                        # Fallback: If no new_last_sync_date, query all statuses (first run scenario)
                        logger.debug(f"🎯 [STATUSES] No new_last_sync_date - querying all statuses (first run)")
                        statuses_query = text("""
                            SELECT DISTINCT external_id
                            FROM statuses
                            WHERE tenant_id = :tenant_id AND integration_id = :integration_id
                            ORDER BY external_id
                        """)

                        with self.get_db_session() as db_read:
                            status_rows = db_read.execute(statuses_query, {
                                'tenant_id': tenant_id,
                                'integration_id': integration_id
                            }).fetchall()

                    status_external_ids = [row[0] for row in status_rows]
                    logger.debug(f"🎯 [STATUSES] Found {len(status_external_ids)} statuses updated after {new_last_sync_date}")

                    # 🎯 HANDLE NO UPDATED STATUSES: If no statuses were updated, mark both transform and embedding as finished
                    if not status_external_ids:
                        logger.info(f"🎯 [STATUSES] No updated statuses found - marking transform and embedding as finished")

                        # 🎯 OPTION 1: Mark both steps as finished directly (current approach)
                        # This avoids sending unnecessary completion messages through the queue
                        await self._send_worker_status('transform', tenant_id, job_id, 'finished', 'jira_statuses_and_relationships')
                        await self._send_worker_status('embedding', tenant_id, job_id, 'finished', 'jira_statuses_and_relationships')
                        logger.debug(f"✅ [STATUSES] Both transform and embedding steps marked as finished (no updated statuses)")

                        # 🎯 OPTION 2: Send completion message to embedding (uncomment if you want the message to flow through embedding worker)
                        # self._queue_entities_for_embedding(
                        #     tenant_id=tenant_id,
                        #     table_name='statuses',
                        #     entities=[],  # Empty list signals completion
                        #     job_id=job_id,
                        #     message_type='jira_statuses_and_relationships',
                        #     integration_id=integration_id,
                        #     provider=provider,
                        #     old_last_sync_date=old_last_sync_date,
                        #     new_last_sync_date=new_last_sync_date,
                        #     first_item=first_item_flag,  # Preserve first_item flag
                        #     last_item=True,  # This is the last (and only) message
                        #     last_job_item=last_job_item,  # Preserve last_job_item flag
                        #     token=token
                        # )
                        # logger.debug(f"✅ [STATUSES] Completion message sent to embedding (no updated statuses)")
                    else:
                        # Queue each distinct status with proper first_item/last_item flags
                        for i, external_id in enumerate(status_external_ids):
                            is_first = (i == 0)
                            is_last = (i == len(status_external_ids) - 1)

                            self._queue_entities_for_embedding(
                                tenant_id, 'statuses',
                                [{'external_id': external_id}],
                                job_id,
                                message_type='jira_statuses_and_relationships',
                                integration_id=integration_id,
                                provider=provider,
                                old_last_sync_date=old_last_sync_date,  # 🔑 Forward old_last_sync_date
                                new_last_sync_date=new_last_sync_date,
                                first_item=is_first,
                                last_item=is_last,
                                last_job_item=last_job_item,
                                token=token  # 🔑 Include token in message
                            )

                        logger.debug(f"🎯 [STATUSES] Queued {len(status_external_ids)} distinct statuses for embedding")

                        # ✅ Send WebSocket status update immediately after queuing
                        # This updates database and sends WebSocket notification to UI
                        if job_id:
                            logger.debug(f"🏁 [STATUSES] Sending 'finished' status for transform step")
                            await self._send_worker_status('transform', tenant_id, job_id, 'finished', 'jira_statuses_and_relationships')
                            logger.debug(f"✅ [STATUSES] Transform step marked as finished and WebSocket notification sent")
                else:
                    logger.debug(f"🎯 [STATUSES] Not last item (first_item={message.get('first_item') if message else False}, last_item={message.get('last_item') if message else False}) - skipping embedding queue")

                logger.info(f"✅ [STATUSES] Completed statuses and project relationships processing (raw_data_id={raw_data_id})")
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
            from app.core.utils import DateTimeHelper

            statuses_to_insert = []
            statuses_to_update = []
            now = DateTimeHelper.now_default()

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
            logger.debug(f"Found {len(status_mapping_lookup)} status mappings: {list(status_mapping_lookup.keys())}")

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
                            'external_id': external_id,  # Add external_id for vectorization
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
                # Add timestamps to each record
                for status in statuses_to_insert:
                    status['created_at'] = now
                    status['last_updated_at'] = now

                insert_query = text("""
                    INSERT INTO statuses (
                        external_id, original_name, category, description, status_mapping_id,
                        integration_id, tenant_id, active, created_at, last_updated_at
                    ) VALUES (
                        :external_id, :original_name, :category, :description, :status_mapping_id,
                        :integration_id, :tenant_id, TRUE, :created_at, :last_updated_at
                    )
                """)
                db.execute(insert_query, statuses_to_insert)
                logger.debug(f"Inserted {len(statuses_to_insert)} new statuses with mapping links")

            # Bulk update existing statuses
            if statuses_to_update:
                # Add timestamp to each record
                for status in statuses_to_update:
                    status['last_updated_at'] = now

                update_query = text("""
                    UPDATE statuses
                    SET original_name = :original_name, category = :category,
                        description = :description, status_mapping_id = :status_mapping_id,
                        last_updated_at = :last_updated_at
                    WHERE id = :id
                """)
                db.execute(update_query, statuses_to_update)
                logger.debug(f"Updated {len(statuses_to_update)} existing statuses with mapping links")

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
            logger.debug(f"Found {len(projects_lookup)} projects for relationship mapping")

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
            logger.debug(f"Found {len(statuses_lookup)} statuses for relationship mapping")

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
                logger.debug(f"Inserted {len(relationships_to_insert)} new project-status relationships")

            return len(relationships_to_insert)

        except Exception as e:
            logger.error(f"Error processing project-status relationships data: {e}")
            raise

    def _queue_entities_for_embedding(
        self,
        tenant_id: int,
        table_name: str,
        entities: List[Dict[str, Any]],
        job_id: int = None,
        last_item: bool = False,
        provider: str = None,
        old_last_sync_date: str = None,  # 🔑 Old last sync date (for filtering)
        new_last_sync_date: str = None,  # 🔑 New last sync date (for job completion)
        message_type: str = None,
        integration_id: int = None,
        first_item: bool = False,
        last_job_item: bool = False,
        token: str = None  # 🔑 Job execution token
    ):
        """
        Queue entities for embedding by publishing messages to embedding queue.

        Args:
            tenant_id: Tenant ID
            table_name: Name of the table (projects, wits, statuses, etc.)
            entities: List of entity dictionaries with external_id or key
            old_last_sync_date: Old last sync date used for filtering
            new_last_sync_date: New last sync date to update on completion (extraction end date)
        """
        # 🎯 HANDLE COMPLETION MESSAGE: Empty entities with last_job_item=True
        if not entities and last_job_item:
            logger.debug(f"[COMPLETION] Sending job completion message to embedding queue (no {table_name} entities)")

            # Send completion message to embedding queue with external_id=None
            if not self.queue_manager:
                logger.error("QueueManager not available - cannot send completion message")
                return

            success = self.queue_manager.publish_embedding_job(
                tenant_id=tenant_id,
                table_name=table_name,
                external_id=None,  # 🔧 None signals completion message
                job_id=job_id,
                integration_id=integration_id,
                provider=provider,
                old_last_sync_date=old_last_sync_date,  # 🔑 Old last sync date (for filtering)
                new_last_sync_date=new_last_sync_date,  # 🔑 New last sync date (for job completion)
                first_item=first_item,
                last_item=last_item,
                last_job_item=last_job_item,  # 🎯 Signal job completion
                step_type=message_type,
                token=token  # 🔑 Include token in message
            )

            if success:
                logger.debug(f"✅ Sent completion message to embedding queue for {table_name}")
            else:
                logger.error(f"❌ Failed to send completion message to embedding queue for {table_name}")

            return

        if not entities:
            # 🎯 FLAG MESSAGE: If entities is empty but we have first_item=True OR last_item=True, publish flag message
            # This ensures WebSocket status updates are sent even when there are no entities to process
            if first_item or last_item:
                logger.debug(f"🎯 [FLAG-MESSAGE] Publishing flag message to embedding queue for {table_name} (first={first_item}, last={last_item})")
                if not self.queue_manager:
                    logger.error("QueueManager not available - cannot send flag message")
                    return

                success = self.queue_manager.publish_embedding_job(
                    tenant_id=tenant_id,
                    table_name=table_name,
                    external_id=None,  # 🔑 Key: None signals flag/completion message
                    job_id=job_id,
                    integration_id=integration_id,
                    provider=provider,
                    old_last_sync_date=old_last_sync_date,  # 🔑 Old last sync date (for filtering)
                    new_last_sync_date=new_last_sync_date,  # 🔑 New last sync date (for job completion)
                    first_item=first_item,    # ✅ Preserved (could be True for 'running' status)
                    last_item=last_item,      # ✅ Preserved (could be True for 'finished' status)
                    last_job_item=last_job_item,  # ✅ Preserved
                    step_type=message_type,
                    token=token  # 🔑 Include token in message
                )
                logger.debug(f"🎯 [FLAG-MESSAGE] Embedding flag message published: {success}")
            else:
                logger.debug(f"No entities to queue for {table_name}")
            return

        try:
            logger.debug(f"Attempting to queue {len(entities)} {table_name} entities for embedding")
            if not self.queue_manager:
                logger.error("QueueManager not available - cannot queue entities for embedding")
                return

            queued_count = 0

            # Update step status to running when queuing for embedding
            if job_id and queued_count == 0:  # Only on first entity to avoid multiple updates
                # Don't update overall status here - let embedding worker handle completion
                logger.debug(f"Transform completed, queuing {table_name} for embedding")

            for entity in entities:
                # Get external ID - work_items_prs_links uses internal ID, all others use external_id
                if table_name == 'work_items_prs_links':
                    external_id = str(entity.get('id'))
                else:
                    external_id = entity.get('external_id')

                if not external_id:
                    logger.warning(f"No external_id found for {table_name} entity: {entity}")
                    continue

                # Calculate flags for this entity
                entity_first_item = first_item and (queued_count == 0)
                entity_last_item = last_item and (queued_count == len(entities) - 1)

                # 🎯 DEBUG: Log flags for first entity
                if queued_count == 0:
                    logger.info(f"🎯 [EMBEDDING-QUEUE] First entity: table={table_name}, external_id={external_id}, first_item={entity_first_item}, last_item={entity_last_item}, incoming_first={first_item}, incoming_last={last_item}")

                # Publish embedding message with standardized structure
                success = self.queue_manager.publish_embedding_job(
                    tenant_id=tenant_id,
                    table_name=table_name,
                    external_id=str(external_id),
                    job_id=job_id,
                    integration_id=integration_id,
                    provider=provider,
                    old_last_sync_date=old_last_sync_date,  # 🔑 Old last sync date (for filtering)
                    new_last_sync_date=new_last_sync_date,  # 🔑 New last sync date (for job completion)
                    first_item=entity_first_item,  # True only for first entity when incoming first_item=True
                    last_item=entity_last_item,  # True only for last entity when incoming last_item=True
                    last_job_item=last_job_item,  # Forward last_job_item flag from incoming message
                    step_type=message_type,  # Pass the step type (e.g., 'jira_projects_and_issue_types')
                    token=token  # 🔑 Include token in message
                )

                if success:
                    queued_count += 1

            if queued_count > 0:
                logger.debug(f"Queued {queued_count} {table_name} entities for embedding")

        except Exception as e:
            logger.error(f"Error queuing entities for embedding: {e}")
            # Don't raise - embedding is async and shouldn't block transform

    def _queue_all_entities_for_embedding(
        self,
        session,
        tenant_id: int,
        integration_id: int,
        job_id: int,
        message_type: str,
        provider: str,
        old_last_sync_date: str,  # 🔑 Old last sync date (for filtering)
        new_last_sync_date: str,  # 🔑 New last sync date (for job completion)
        last_job_item: bool,
        token: str = None  # 🔑 Job execution token
    ):
        """
        Queue ALL active projects and wits for embedding (not just changed ones).

        This ensures complete vectorization of all entities, regardless of what was
        inserted/updated in the current batch.

        Args:
            session: Database session
            tenant_id: Tenant ID
            integration_id: Integration ID
            job_id: ETL job ID
            message_type: ETL step type
            provider: Provider name (jira, github, etc.)
            old_last_sync_date: Old last sync date (for filtering)
            new_last_sync_date: New last sync date (for job completion)
            last_job_item: Whether this is the final job item
        """
        try:
            # Get ALL active projects for this tenant/integration
            all_projects = session.query(Project.external_id).filter(
                Project.tenant_id == tenant_id,
                Project.integration_id == integration_id,
                Project.active == True
            ).all()

            # Get ALL active wits for this tenant/integration
            all_wits = session.query(Wit.external_id).filter(
                Wit.tenant_id == tenant_id,
                Wit.integration_id == integration_id,
                Wit.active == True
            ).all()

            total_entities = len(all_projects) + len(all_wits)
            logger.debug(f"🔄 Queueing ALL entities for embedding: {len(all_projects)} projects + {len(all_wits)} wits = {total_entities} total")

            if total_entities == 0:
                logger.warning(f"No active projects or wits found for tenant {tenant_id}, integration {integration_id}")
                return

            # Queue ALL projects (not just changed ones)
            for i, project in enumerate(all_projects):
                is_first = (i == 0)
                is_last = (i == len(all_projects) - 1) and len(all_wits) == 0

                self._queue_entities_for_embedding(
                    tenant_id=tenant_id,
                    table_name='projects',
                    entities=[{'external_id': project.external_id}],
                    job_id=job_id,
                    message_type=message_type,
                    integration_id=integration_id,
                    provider=provider,
                    old_last_sync_date=old_last_sync_date,  # 🔑 Forward old_last_sync_date
                    new_last_sync_date=new_last_sync_date,
                    first_item=is_first,
                    last_item=is_last,
                    last_job_item=last_job_item,
                    token=token  # 🔑 Include token in message
                )

            # Queue ALL wits (not just changed ones)
            for i, wit in enumerate(all_wits):
                is_first = (i == 0) and len(all_projects) == 0
                is_last = (i == len(all_wits) - 1)

                self._queue_entities_for_embedding(
                    tenant_id=tenant_id,
                    table_name='wits',
                    entities=[{'external_id': wit.external_id}],
                    job_id=job_id,
                    message_type=message_type,
                    integration_id=integration_id,
                    provider=provider,
                    old_last_sync_date=old_last_sync_date,  # 🔑 Forward old_last_sync_date
                    new_last_sync_date=new_last_sync_date,
                    first_item=is_first,
                    last_item=is_last,
                    last_job_item=last_job_item,
                    token=token  # 🔑 Include token in message
                )

            logger.debug(f"✅ Successfully queued {total_entities} entities for embedding")

        except Exception as e:
            logger.error(f"Error queuing all entities for embedding: {e}")
            # Don't raise - embedding is async and shouldn't block transform

    # REMOVED: _process_jira_issues_changelogs and _process_jira_single_issue
    # These were leftover/dead code - never called. The actual method used is _process_jira_single_issue_changelog below.

    async def _process_jira_single_issue_changelog(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
        """
        Process a single Jira issue with changelog from raw_extraction_data.

        This processes individual issues extracted from the paginated response.
        Each issue contains full field data and changelog data.

        Flow:
        1. Load single issue raw data from raw_extraction_data table
        2. Transform issue data and insert/update work_items table
        3. Transform changelog data and insert changelogs table
        4. Check if issue has development field - queue for dev_status extraction
        5. Queue work_item and changelogs for vectorization
        """
        try:
            # 🎯 HANDLE COMPLETION MESSAGE: raw_data_id=None signals job completion
            if raw_data_id is None and message and message.get('last_job_item'):
                logger.debug(f"[COMPLETION] Received completion message for jira_issues_with_changelogs (no data to process)")

                # Send completion message to embedding queue
                self._queue_entities_for_embedding(
                    tenant_id=tenant_id,
                    table_name='work_items',
                    entities=[],  # Empty list
                    job_id=job_id,
                    message_type='jira_issues_with_changelogs',
                    integration_id=integration_id,
                    provider=message.get('provider', 'jira'),
                    last_sync_date=message.get('last_sync_date'),
                    first_item=True,
                    last_item=True,
                    last_job_item=True  # 🎯 Signal job completion to embedding worker
                )

                logger.debug(f"✅ Sent completion message to embedding queue")
                return True

            # Extract message flags
            first_item = message.get('first_item', False) if message else False
            last_item = message.get('last_item', False) if message else False
            last_job_item = message.get('last_job_item', False) if message else False

            logger.info(f"🏁 [ISSUES] Starting issue with changelog processing (raw_data_id={raw_data_id}, first={first_item}, last={last_item})")

            with self.get_db_session() as db:
                # Load raw data (single issue)
                raw_data = self._get_raw_data(db, raw_data_id)
                if not raw_data:
                    logger.error(f"Raw data {raw_data_id} not found")
                    return False

                # Raw data contains a single issue object under 'issue' key
                issue = raw_data.get('issue')
                if not issue:
                    logger.error(f"No 'issue' key found in raw_data_id={raw_data_id}")
                    return False

                # Validate issue has required fields
                if not issue.get('key'):
                    logger.error(f"Issue missing 'key' field in raw_data_id={raw_data_id}")
                    return False

                # Get reference data for mapping
                projects_map, wits_map, statuses_map = self._get_reference_data_maps(db, integration_id, tenant_id)

                # Get custom field mappings from integration
                custom_field_mappings = self._get_custom_field_mappings(db, integration_id, tenant_id)

                # Process single issue (wrap in array for compatibility with existing method)
                issues_processed = self._process_issues_data(
                    db, [issue], integration_id, tenant_id, projects_map, wits_map, statuses_map, custom_field_mappings, job_id, message
                )

                # Process sprint associations
                sprint_associations_processed = self._process_sprint_associations(
                    db, [issue], integration_id, tenant_id, custom_field_mappings
                )

                # Process changelogs for this issue
                changelogs_processed = self._process_changelogs_data(
                    db, [issue], integration_id, tenant_id, statuses_map, job_id, message
                )

                # Note: dev_status extraction is now handled by extraction worker, not transform worker

                # Update raw data status to completed
                from app.core.utils import DateTimeHelper
                now = DateTimeHelper.now_default()

                update_query = text("""
                    UPDATE raw_extraction_data
                    SET status = 'completed',
                        last_updated_at = :now,
                        error_details = NULL
                    WHERE id = :raw_data_id
                """)
                db.execute(update_query, {'raw_data_id': raw_data_id, 'now': now})
                db.commit()

                logger.debug(f"Processed issue {issue.get('key')} with {changelogs_processed} changelogs - marked raw_data_id={raw_data_id} as completed")

            # ✅ Send WebSocket status update when last_item=True
            if last_item and job_id:
                logger.debug(f"🏁 [ISSUES] Sending 'finished' status for transform step")
                await self._send_worker_status('transform', tenant_id, job_id, 'finished', 'jira_issues_with_changelogs')
                logger.debug(f"✅ [ISSUES] Transform step marked as finished and WebSocket notification sent")

            logger.info(f"✅ [ISSUES] Completed issue with changelog processing (raw_data_id={raw_data_id})")
            return True

        except Exception as e:
            logger.error(f"Error processing single jira_single_issue_changelog (raw_data_id={raw_data_id}): {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

            # Mark raw data as failed
            try:
                from app.core.utils import DateTimeHelper
                now = DateTimeHelper.now_default()

                with self.get_db_session() as db:
                    error_query = text("""
                        UPDATE raw_extraction_data
                        SET status = 'failed',
                            error_details = CAST(:error_details AS jsonb),
                            last_updated_at = :now
                        WHERE id = :raw_data_id
                    """)
                    db.execute(error_query, {
                        'raw_data_id': raw_data_id,
                        'error_details': json.dumps({'error': str(e)[:500]}),
                        'now': now
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
                'customfield_10021': 'sprints',  # Special field
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
                    cfm.sprints_field_id,
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
                logger.debug(f"No custom field mappings found for integration {integration_id}")
                return {}

            # Get custom_fields external_ids for the mapped field IDs
            field_ids = [fid for fid in result if fid is not None]
            if not field_ids:
                logger.debug(f"No custom fields mapped for integration {integration_id}")
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

            # Special fields (indices 0, 1, 2, 3)
            if result[0]:  # team_field_id
                external_id = field_id_to_external_id.get(result[0])
                if external_id:
                    mappings[external_id] = 'team'

            if result[1]:  # sprints_field_id
                external_id = field_id_to_external_id.get(result[1])
                if external_id:
                    mappings[external_id] = 'sprints'  # Used by _process_sprint_associations to find sprint data in issue JSON

            if result[2]:  # development_field_id
                external_id = field_id_to_external_id.get(result[2])
                if external_id:
                    mappings[external_id] = 'development'

            if result[3]:  # story_points_field_id
                external_id = field_id_to_external_id.get(result[3])
                if external_id:
                    mappings[external_id] = 'story_points'

            # Regular custom fields (indices 4-23 for custom_field_01 to custom_field_20)
            for i in range(20):
                field_id = result[4 + i]  # Start from index 4
                if field_id:
                    external_id = field_id_to_external_id.get(field_id)
                    if external_id:
                        mappings[external_id] = f'custom_field_{i+1:02d}'

            logger.debug(f"Loaded {len(mappings)} custom field mappings for integration {integration_id}")
            return mappings

        except Exception as e:
            logger.error(f"Error loading custom field mappings: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {}

    def _extract_all_fields(self, fields: Dict, custom_field_mappings: Dict[str, str]) -> Dict:
        """
        Extract all mapped fields from Jira issue fields based on mappings.
        Includes special fields (team, development, story_points) and custom fields.

        Args:
            fields: Jira issue fields dict
            custom_field_mappings: Dict mapping Jira field IDs to work_items column names
                                  e.g., {
                                      'customfield_10001': 'team',
                                      'customfield_10000': 'development',
                                      'customfield_10024': 'story_points',
                                      'customfield_10128': 'custom_field_01'
                                  }

        Returns:
            Dict with all field column names and values
            e.g., {
                'team': 'R&I',
                'development': True,
                'story_points': 5.0,
                'custom_field_01': 'Epic Name',
                'custom_field_02': 'Some value'
            }
        """
        result = {}

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

                elif column_name == 'development':
                    # Development field - boolean indicating if there's any development data
                    # True if field has any content, False otherwise
                    development = False
                    if value is not None:
                        if isinstance(value, bool):
                            development = value
                        elif isinstance(value, str):
                            # Non-empty string (excluding empty JSON objects)
                            value_stripped = value.strip()
                            if value_stripped and value_stripped not in ('{}', '[]', '""', "''"):
                                development = True
                        elif isinstance(value, dict):
                            # Non-empty dict
                            if value:
                                development = True
                        elif isinstance(value, list):
                            # Non-empty list
                            if value:
                                development = True
                        else:
                            # Any other non-None value
                            development = True
                    result[column_name] = development

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

                elif column_name == 'sprints':
                    # Sprints field - DO NOT extract as column value
                    # Sprint data is handled separately by _process_sprint_associations
                    # which populates the sprints and work_items_sprints tables
                    # Skip this field to avoid trying to insert into non-existent work_items.sprints column
                    pass

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



        return result

    def _process_issues_data(
        self, db, issues_data: List[Dict], integration_id: int, tenant_id: int,
        projects_map: Dict, wits_map: Dict, statuses_map: Dict, custom_field_mappings: Dict[str, str], job_id: int = None, message: Dict[str, Any] = None
    ) -> int:
        """
        Process and insert/update issues in work_items table.

        Args:
            custom_field_mappings: Dict mapping Jira field IDs to work_items column names
                                  e.g., {'customfield_10024': 'custom_field_01'}
        """
        from app.core.utils import DateTimeHelper

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
        current_time = DateTimeHelper.now_default()

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
                # This will extract team, development, story_points, and custom_field_01-20
                all_fields_data = self._extract_all_fields(fields, custom_field_mappings)

                # Extract special fields from the result
                team = all_fields_data.pop('team', None)
                # Sprints removed - now using sprints table and work_items_sprints junction table
                development = all_fields_data.pop('development', False)
                story_points = all_fields_data.pop('story_points', None)

                # Remaining fields are custom_field_01-20 and overflow
                custom_fields_data = all_fields_data

                # Check if issue exists
                if external_id in existing_issues_map:
                    # Update existing issue
                    update_dict = {
                        'id': existing_issues_map[external_id]['id'],
                        'external_id': external_id,  # Add external_id for embedding queue
                        'key': existing_issues_map[external_id]['key'],  # Add key for vectorization
                        'summary': summary,
                        'description': description,
                        'project_id': project_id,
                        'wit_id': wit_id,
                        'status_id': status_id,
                        'story_points': story_points,
                        'priority': priority,
                        'resolution': resolution,
                        'assignee': assignee,
                        'team': team,
                        'labels': labels,
                        'updated': updated,
                        'parent_external_id': parent_external_id,
                        'development': development,
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
                        'story_points': story_points,
                        'priority': priority,
                        'resolution': resolution,
                        'assignee': assignee,
                        'team': team,
                        'labels': labels,
                        'created': created,
                        'updated': updated,
                        'parent_external_id': parent_external_id,
                        'development': development,
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

        # Get flags from incoming message to forward to embedding
        first_item = message.get('first_item', False) if message else False
        last_item = message.get('last_item', False) if message else False
        last_job_item = message.get('last_job_item', False) if message else False
        provider = message.get('provider') if message else 'jira'
        old_last_sync_date = message.get('old_last_sync_date') if message else None  # 🔑 From extraction worker
        new_last_sync_date = message.get('new_last_sync_date') if message else None
        token = message.get('token') if message else None  # 🔑 Execution token for job tracking

        # Bulk insert new issues
        if issues_to_insert:
            BulkOperations.bulk_insert(db, 'work_items', issues_to_insert)
            logger.debug(f"Inserted {len(issues_to_insert)} new issues")

            # Queue for embedding - forward first_item/last_item/last_job_item flags from incoming message
            self._queue_entities_for_embedding(tenant_id, 'work_items', issues_to_insert, job_id,
                                             message_type='jira_issues_with_changelogs', integration_id=integration_id,
                                             provider=provider, old_last_sync_date=old_last_sync_date,
                                             new_last_sync_date=new_last_sync_date,
                                             first_item=first_item, last_item=last_item, last_job_item=last_job_item,
                                             token=token)  # 🔑 Include token in message

        # Bulk update existing issues
        if issues_to_update:
            BulkOperations.bulk_update(db, 'work_items', issues_to_update)
            logger.debug(f"Updated {len(issues_to_update)} existing issues")

            logger.debug(f"[DEBUG] Queuing {len(issues_to_update)} issues_to_update for embedding")
            for i, entity in enumerate(issues_to_update[:3]):  # Log first 3 entities
                logger.debug(f"[DEBUG] issues_to_update[{i}] keys: {list(entity.keys())}")
                logger.debug(f"[DEBUG] issues_to_update[{i}] external_id: {entity.get('external_id')}")

            # Queue for embedding - forward first_item/last_item/last_job_item flags from incoming message
            self._queue_entities_for_embedding(tenant_id, 'work_items', issues_to_update, job_id,
                                             message_type='jira_issues_with_changelogs', integration_id=integration_id,
                                             provider=provider, old_last_sync_date=old_last_sync_date,
                                             new_last_sync_date=new_last_sync_date,
                                             first_item=first_item, last_item=last_item, last_job_item=last_job_item,
                                             token=token)  # 🔑 Include token in message

        return len(issues_to_insert) + len(issues_to_update)

    def _process_sprint_associations(
        self, db, issues_data: List[Dict], integration_id: int, tenant_id: int, custom_field_mappings: Dict[str, str]
    ) -> int:
        """
        Process sprint associations from issues and populate work_items_sprints junction table.

        This extracts sprint data from the sprints field in each issue, creates placeholder
        sprint records if needed, and creates the many-to-many relationship between work items and sprints.

        Args:
            db: Database session
            issues_data: List of issue dictionaries from Jira API
            integration_id: Integration ID
            tenant_id: Tenant ID
            custom_field_mappings: Dict mapping Jira field IDs to column names (includes 'sprints' mapping)

        Returns:
            Number of sprint associations processed
        """
        from app.core.utils import DateTimeHelper

        try:
            logger.debug(f"🔍 [SPRINT-DEBUG] Starting sprint associations processing for {len(issues_data)} issues")

            # Find the sprint field ID from custom_field_mappings
            sprint_field_id = None
            for field_id, field_name in custom_field_mappings.items():
                if field_name == 'sprints':
                    sprint_field_id = field_id
                    break

            if not sprint_field_id:
                logger.warning(f"⚠️ [SPRINT-DEBUG] No sprint field mapping found in custom_field_mappings - skipping sprint associations")
                return 0

            logger.debug(f"🔍 [SPRINT-DEBUG] Using sprint field: {sprint_field_id}")

            # Collect issue external_ids from payload
            issue_external_ids = [issue.get('id') for issue in issues_data if issue.get('id')]
            if not issue_external_ids:
                logger.debug("No valid issue external_ids found in payload")
                return 0

            # Query ONLY the work_items for the issues in this payload
            work_items_query = text("""
                SELECT external_id, id
                FROM work_items
                WHERE integration_id = :integration_id
                AND tenant_id = :tenant_id
                AND external_id = ANY(:external_ids)
            """)
            work_items_result = db.execute(work_items_query, {
                'integration_id': integration_id,
                'tenant_id': tenant_id,
                'external_ids': issue_external_ids
            }).fetchall()
            work_items_map = {row[0]: row[1] for row in work_items_result}

            # Collect all unique sprints and their associations
            sprints_to_create = {}  # {external_id: sprint_data}
            sprint_associations = []  # [{work_item_external_id, sprint_external_id, ...}]
            current_time = DateTimeHelper.now_default()

            for issue in issues_data:
                try:
                    issue_external_id = issue.get('id')
                    if not issue_external_id:
                        continue

                    # Get sprints field from issue using the mapped field ID
                    fields = issue.get('fields', {})
                    sprints_field = fields.get(sprint_field_id)

                    logger.debug(f"🔍 [SPRINT-DEBUG] Issue {issue.get('key')}: sprints_field type={type(sprints_field)}, value={sprints_field}")

                    if not sprints_field or not isinstance(sprints_field, list):
                        continue

                    # Extract sprint data from sprints array
                    for sprint in sprints_field:
                        if isinstance(sprint, dict):
                            sprint_external_id = str(sprint.get('id'))  # Sprint ID
                            board_id = sprint.get('boardId')
                            sprint_name = sprint.get('name')
                            sprint_state = sprint.get('state')  # future, active, closed

                            if sprint_external_id:
                                # Collect unique sprint data
                                if sprint_external_id not in sprints_to_create:
                                    sprints_to_create[sprint_external_id] = {
                                        'external_id': sprint_external_id,
                                        'board_id': board_id,
                                        'name': sprint_name,
                                        'state': sprint_state
                                    }

                                # Collect association (using external_id, will map to internal later)
                                sprint_associations.append({
                                    'work_item_external_id': issue_external_id,
                                    'sprint_external_id': sprint_external_id,
                                    'tenant_id': tenant_id
                                })

                except Exception as e:
                    logger.error(f"Error processing sprint associations for issue {issue.get('key', 'unknown')}: {e}")
                    continue

            if not sprint_associations:
                logger.info(f"📊 No sprint associations found in {len(issues_data)} issues")
                return 0

            logger.info(f"📊 Found {len(sprint_associations)} sprint associations from {len(issues_data)} issues")
            logger.info(f"📊 Found {len(sprints_to_create)} unique sprints to create/update")

            # Step 1: Get existing sprints
            existing_sprints_query = text("""
                SELECT external_id, id
                FROM sprints
                WHERE tenant_id = :tenant_id
                AND external_id = ANY(:external_ids)
            """)
            existing_sprints_result = db.execute(existing_sprints_query, {
                'tenant_id': tenant_id,
                'external_ids': list(sprints_to_create.keys())
            }).fetchall()
            existing_sprints_map = {row[0]: row[1] for row in existing_sprints_result}

            # Step 2: Upsert sprint records (insert new + update existing)
            # Use PostgreSQL ON CONFLICT to handle concurrent inserts gracefully
            sprints_to_upsert = []
            for sprint_external_id, sprint_data in sprints_to_create.items():
                sprints_to_upsert.append({
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'external_id': sprint_external_id,
                    'board_id': sprint_data['board_id'],
                    'name': sprint_data['name'],
                    'state': sprint_data['state'],
                    'active': True,
                    'created_at': current_time,
                    'last_updated_at': current_time
                })

            if sprints_to_upsert:
                # Use ON CONFLICT DO UPDATE to handle race conditions between concurrent workers
                upsert_query = text("""
                    INSERT INTO sprints (tenant_id, integration_id, external_id, board_id, name, state, active, created_at, last_updated_at)
                    VALUES (:tenant_id, :integration_id, :external_id, :board_id, :name, :state, :active, :created_at, :last_updated_at)
                    ON CONFLICT (tenant_id, integration_id, external_id)
                    DO UPDATE SET
                        board_id = EXCLUDED.board_id,
                        name = EXCLUDED.name,
                        state = EXCLUDED.state,
                        last_updated_at = EXCLUDED.last_updated_at
                """)

                for sprint in sprints_to_upsert:
                    db.execute(upsert_query, sprint)

                logger.info(f"✅ Upserted {len(sprints_to_upsert)} sprint records")

            # Refresh sprints map after upsert
            existing_sprints_result = db.execute(existing_sprints_query, {
                'tenant_id': tenant_id,
                'external_ids': list(sprints_to_create.keys())
            }).fetchall()
            existing_sprints_map = {row[0]: row[1] for row in existing_sprints_result}

            # Step 3: Create work_items_sprints associations
            # Map work_item external_ids to internal_ids
            associations_to_insert = []
            for assoc in sprint_associations:
                work_item_external_id = assoc['work_item_external_id']
                sprint_external_id = assoc['sprint_external_id']

                work_item_id = work_items_map.get(work_item_external_id)
                sprint_id = existing_sprints_map.get(sprint_external_id)

                if work_item_id and sprint_id:
                    associations_to_insert.append({
                        'work_item_id': work_item_id,
                        'sprint_id': sprint_id,
                        'added_date': current_time,
                        'tenant_id': assoc['tenant_id'],
                        'active': True,
                        'created_at': current_time,
                        'last_updated_at': current_time
                    })

            if associations_to_insert:
                # Use ON CONFLICT DO NOTHING to handle race conditions between concurrent workers
                # The unique constraint is on (work_item_id, sprint_id, added_date)
                upsert_assoc_query = text("""
                    INSERT INTO work_items_sprints
                        (work_item_id, sprint_id, added_date, tenant_id, active, created_at, last_updated_at)
                    VALUES
                        (:work_item_id, :sprint_id, :added_date, :tenant_id, :active, :created_at, :last_updated_at)
                    ON CONFLICT (work_item_id, sprint_id, added_date)
                    DO NOTHING
                """)

                inserted_count = 0
                for assoc in associations_to_insert:
                    result = db.execute(upsert_assoc_query, assoc)
                    # rowcount will be 1 if inserted, 0 if conflict (already exists)
                    inserted_count += result.rowcount

                if inserted_count > 0:
                    logger.info(f"✅ Created {inserted_count} new work_items_sprints associations (skipped {len(associations_to_insert) - inserted_count} duplicates)")
                else:
                    logger.debug(f"All {len(associations_to_insert)} sprint associations already exist")

            return len(sprint_associations)

        except Exception as e:
            logger.error(f"Error processing sprint associations: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return 0

    def _process_changelogs_data(
        self, db, issues_data: List[Dict], integration_id: int, tenant_id: int,
        statuses_map: Dict, job_id: int = None, message: Dict[str, Any] = None
    ) -> int:
        """Process and insert changelogs from issues data."""
        from datetime import timezone
        from app.core.utils import DateTimeHelper

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
        current_time = DateTimeHelper.now_default()

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
            logger.debug(f"Inserted {len(changelogs_to_insert)} new changelogs")

            # Get flags from incoming message to forward to embedding
            first_item = message.get('first_item', False) if message else False
            last_item = message.get('last_item', False) if message else False
            last_job_item = message.get('last_job_item', False) if message else False
            provider = message.get('provider') if message else 'jira'
            old_last_sync_date = message.get('old_last_sync_date') if message else None  # 🔑 From extraction worker
            new_last_sync_date = message.get('new_last_sync_date') if message else None

            # Queue for embedding - forward first_item/last_item/last_job_item flags from incoming message
            self._queue_entities_for_embedding(tenant_id, 'changelogs', changelogs_to_insert, job_id,
                                             message_type='jira_issues_with_changelogs', integration_id=integration_id,
                                             provider=provider, old_last_sync_date=old_last_sync_date,
                                             new_last_sync_date=new_last_sync_date,
                                             first_item=first_item, last_item=last_item, last_job_item=last_job_item)

        # Calculate and update enhanced workflow metrics from in-memory changelog data
        if changelogs_to_insert:
            logger.debug(f"Calculating enhanced workflow metrics for {len(work_items_map)} work items...")
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
        current_time = DateTimeHelper.now_default()

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
            logger.debug(f"Updated workflow metrics for {len(work_items_to_update)} work items")

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

    async def _process_jira_dev_status(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
        """
        Process Jira dev_status data from raw_extraction_data.

        Flow:
        1. Load raw data from raw_extraction_data table
        2. Extract PR links from dev_status
        3. Bulk insert/update work_items_prs_links table
        4. Queue for vectorization
        """
        try:


            # 🎯 DEBUG: Log message flags for dev_status processing
            first_item = message.get('first_item', False) if message else False
            last_item = message.get('last_item', False) if message else False
            last_job_item = message.get('last_job_item', False) if message else False

            logger.info(f"🏁 [DEV_STATUS] Starting dev status processing (raw_data_id={raw_data_id}, first={first_item}, last={last_item})")
            # NOTE: Status updates are handled by TransformWorker router (lines 138-148, 276-283)

            with self.get_db_session() as db:
                # Load raw data
                raw_data = self._get_raw_data(db, raw_data_id)
                if not raw_data:
                    logger.error(f"Raw data {raw_data_id} not found")
                    # NOTE: "finished" status is sent by TransformWorker router (line 276-283)
                    return False

                # Extract dev_status data - handle single issue format from extraction worker
                issue_key = raw_data.get('issue_key')
                issue_id = raw_data.get('issue_id')
                dev_status = raw_data.get('dev_status')

                if not dev_status or not issue_key:
                    logger.warning(f"No dev_status or issue_key found in raw_data_id={raw_data_id}")
                    # ✅ Send transform worker "finished" status when last_item=True even if no data
                    if message and message.get('last_item') and job_id:
                        logger.debug(f"🏁 [DEV_STATUS] Sending 'finished' status for transform step (no data)")
                        await self._send_worker_status("transform", tenant_id, job_id, "finished", "jira_dev_status")
                        logger.debug(f"✅ [DEV_STATUS] Transform step marked as finished (no data)")
                    return True

                # Convert to list format expected by _process_dev_status_data
                dev_status_data = [{
                    'issue_key': issue_key,
                    'issue_id': issue_id,
                    'dev_details': dev_status
                }]

                logger.debug(f"Processing dev_status for issue {issue_key}")

                # Process dev_status
                pr_links_processed = await self._process_dev_status_data(
                    db, dev_status_data, integration_id, tenant_id, job_id, message
                )

                # Update raw data status to completed
                from sqlalchemy import text
                from app.core.utils import DateTimeHelper
                now = DateTimeHelper.now_default()

                update_query = text("""
                    UPDATE raw_extraction_data
                    SET status = 'completed',
                        last_updated_at = :now,
                        error_details = NULL
                    WHERE id = :raw_data_id
                """)
                db.execute(update_query, {'raw_data_id': raw_data_id, 'now': now})
                db.commit()

                logger.debug(f"Processed {pr_links_processed} PR links from dev_status - marked raw_data_id={raw_data_id} as completed")

                # Note: WebSocket "finished" status is sent by _process_dev_status_data when last_item=True

                logger.info(f"✅ [DEV_STATUS] Completed dev status processing (raw_data_id={raw_data_id})")
                return True

        except Exception as e:
            logger.error(f"Error processing jira_dev_status: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

            # Mark as failed
            try:
                with self.get_db_session() as db:
                    from sqlalchemy import text
                    from app.core.utils import DateTimeHelper
                    now = DateTimeHelper.now_default()

                    update_query = text("""
                        UPDATE raw_extraction_data
                        SET status = 'failed',
                            last_updated_at = :now,
                            error_details = CAST(:error_details AS jsonb)
                        WHERE id = :raw_data_id
                    """)
                    import json
                    db.execute(update_query, {
                        'raw_data_id': raw_data_id,
                        'error_details': json.dumps({'error': str(e), 'traceback': traceback.format_exc()}),
                        'now': now
                    })
                    db.commit()
            except Exception as update_error:
                logger.error(f"Failed to mark raw_data as failed: {update_error}")

            # NOTE: "failed" status would be sent by TransformWorker router if needed
            # For now, just return False to indicate failure

            return False

    async def _process_dev_status_data(
        self, db, dev_status_data: List[Dict], integration_id: int, tenant_id: int, job_id: int = None, message: Dict[str, Any] = None
    ) -> int:
        """Process dev_status data and insert/update work_items_prs_links table."""
        from app.core.utils import DateTimeHelper

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
        current_time = DateTimeHelper.now_default()

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

        # Get flags from incoming message to forward to embedding
        first_item = message.get('first_item', False) if message else False
        last_item = message.get('last_item', False) if message else False
        last_job_item = message.get('last_job_item', False) if message else False
        provider = message.get('provider') if message else 'jira'
        old_last_sync_date = message.get('old_last_sync_date') if message else None  # 🔑 From extraction worker
        new_last_sync_date = message.get('new_last_sync_date') if message else None
        token = message.get('token') if message else None  # 🔑 Extract token from message

        logger.info(f"🎯 [DEV_STATUS] Flags from transform message: first_item={first_item}, last_item={last_item}, last_job_item={last_job_item}")

        # Bulk insert PR links
        if pr_links_to_insert:
            BulkOperations.bulk_insert(db, 'work_items_prs_links', pr_links_to_insert)
            logger.debug(f"Inserted {len(pr_links_to_insert)} new PR links")

            # Fetch the inserted records with their generated IDs for vectorization
            inserted_links = self._fetch_inserted_pr_links(db, pr_links_to_insert, integration_id, tenant_id)

            # Queue for embedding - forward first_item/last_item/last_job_item flags from incoming message
            if inserted_links:
                self._queue_entities_for_embedding(tenant_id, 'work_items_prs_links', inserted_links, job_id,
                                                 message_type='jira_dev_status', integration_id=integration_id,
                                                 provider=provider, old_last_sync_date=old_last_sync_date,
                                                 new_last_sync_date=new_last_sync_date,
                                                 first_item=first_item, last_item=last_item, last_job_item=last_job_item,
                                                 token=token)  # 🔑 Forward token to embedding
        else:
            # No PR links to insert - send message to embedding if first_item=True OR last_item=True
            # This ensures WebSocket status updates are sent even when there are no entities
            if first_item or last_item:
                logger.debug(f"🎯 [DEV_STATUS] No PR links to insert, sending flag message to embedding (first={first_item}, last={last_item})")
                self._queue_entities_for_embedding(
                    tenant_id=tenant_id,
                    table_name='work_items_prs_links',
                    entities=[],  # Empty entities
                    job_id=job_id,
                    message_type='jira_dev_status',
                    integration_id=integration_id,
                    provider=provider,
                    old_last_sync_date=old_last_sync_date,
                    new_last_sync_date=new_last_sync_date,
                    first_item=first_item,
                    last_item=last_item,
                    last_job_item=last_job_item,
                    token=token
                )

        # ✅ Send WebSocket status update when last_item=True (OUTSIDE the if block)
        if last_item and job_id:
            logger.info(f"🏁 [DEV_STATUS] Sending 'finished' status for transform step")
            await self.status_manager.send_worker_status(
                step="transform",
                tenant_id=tenant_id,
                job_id=job_id,
                status="finished",
                step_type="jira_dev_status"
            )
            logger.info(f"✅ [DEV_STATUS] Transform step marked as finished")

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

            logger.debug(f"Fetched {len(fetched_links)} PR links with IDs for vectorization")
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

    def _calculate_pr_metrics(self, pr_data: Dict[str, Any], commits: List[Dict[str, Any]], reviews: List[Dict[str, Any]], comments: List[Dict[str, Any]], review_threads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate PR metrics from GraphQL data (based on old etl-service logic).

        Args:
            pr_data: PR data from GraphQL
            commits: List of commits
            reviews: List of reviews
            comments: List of comments
            review_threads: List of review threads

        Returns:
            Dictionary with calculated metrics
        """
        metrics = {
            'commit_count': 0,
            'additions': 0,
            'deletions': 0,
            'changed_files': 0,
            'source': None,
            'destination': None,
            'reviewers': 0,
            'first_review_at': None,
            'rework_commit_count': 0,
            'review_cycles': 0,
            'discussion_comment_count': 0,
            'review_comment_count': 0
        }

        try:
            # 1. Count commits and sum additions/deletions/changed_files
            metrics['commit_count'] = len(commits) if commits else 0
            for commit in (commits or []):
                commit_data = commit.get('commit', {})
                metrics['additions'] += commit_data.get('additions', 0) or 0
                metrics['deletions'] += commit_data.get('deletions', 0) or 0
                metrics['changed_files'] += commit_data.get('changedFiles', 0) or 0

            # 2. Extract source and destination branches
            if pr_data.get('headRef'):
                metrics['source'] = pr_data['headRef'].get('name')
            if pr_data.get('baseRef'):
                metrics['destination'] = pr_data['baseRef'].get('name')

            # 3. Calculate review metrics
            if reviews:
                # Get unique reviewers
                reviewers = set()
                review_times = []

                for review in reviews:
                    if review.get('author', {}).get('login'):
                        reviewers.add(review['author']['login'])

                    if review.get('submittedAt'):
                        review_time = self._parse_datetime(review['submittedAt'])
                        if review_time:
                            review_times.append(review_time)

                metrics['reviewers'] = len(reviewers)

                # Get first review time
                if review_times:
                    metrics['first_review_at'] = min(review_times)

                # Count review cycles (CHANGES_REQUESTED or APPROVED)
                metrics['review_cycles'] = len([r for r in reviews if r.get('state') in ['CHANGES_REQUESTED', 'APPROVED']])

            # 4. Calculate rework commits (commits after first review)
            if metrics['first_review_at'] and commits:
                for commit in commits:
                    commit_data = commit.get('commit', {})
                    if commit_data.get('author', {}).get('date'):
                        commit_date = self._parse_datetime(commit_data['author']['date'])
                        if commit_date and commit_date > metrics['first_review_at']:
                            metrics['rework_commit_count'] += 1

            # 5. Count comments
            metrics['discussion_comment_count'] = len(comments) if comments else 0

            # 6. Count review thread comments
            for thread in (review_threads or []):
                thread_comments = thread.get('comments', {}).get('nodes', [])
                metrics['review_comment_count'] += len(thread_comments)

        except Exception as e:
            logger.error(f"Error calculating PR metrics: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

        return metrics

    def _update_job_status(self, job_id: int, step_name: str, step_status: str, message: str = None):
        """Update ETL job step status in database JSON structure."""
        try:
            from app.core.database import get_database
            from sqlalchemy import text
            from app.core.utils import DateTimeHelper

            now = DateTimeHelper.now_default()

            database = get_database()
            with database.get_write_session_context() as session:
                # Update specific step status within the JSON structure
                # Only update overall status to RUNNING if not already running
                # Use string formatting for step_name and step_status to avoid parameter binding issues
                update_query = text(f"""
                    UPDATE etl_jobs
                    SET status = jsonb_set(
                            jsonb_set(status, ARRAY['steps', '{step_name}', 'transform'], '"{step_status}"'::jsonb),
                            ARRAY['overall'],
                            CASE
                                WHEN status->>'overall' = 'READY' THEN '"RUNNING"'::jsonb
                                ELSE status->'overall'
                            END
                        ),
                        last_updated_at = :now
                    WHERE id = :job_id
                """)

                session.execute(update_query, {
                    'job_id': job_id,
                    'now': now
                })
                session.commit()

                logger.debug(f"Updated job {job_id} step {step_name} transform status to {step_status}")
                if message:
                    logger.debug(f"Job {job_id} message: {message}")

        except Exception as e:
            logger.error(f"Error updating job status: {e}")


