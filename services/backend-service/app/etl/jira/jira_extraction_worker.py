"""
Jira Extraction Worker - Processes Jira-specific extraction requests.

This worker handles Jira extraction messages from the extraction queue.
It contains all the extraction logic for different Jira extraction types.

Note: This is NOT a queue consumer itself. It's called from ExtractionWorkerRouter
which is the actual queue consumer. This class contains provider-specific logic.

Architecture:
- Receives messages from extraction_queue_premium (tier-based)
- Processes extraction based on message type
- Fetches data from Jira API
- Stores in raw_extraction_data
- Queues to transform worker
- Sends WebSocket status updates
- Queues next extraction step

Uses dependency injection to receive WorkerStatusManager for sending status updates.
"""

from typing import Dict, Any, Optional
from sqlalchemy import text
from datetime import datetime

from app.core.logging_config import get_logger
from app.core.database import get_database
from app.etl.jira.jira_client import JiraAPIClient
from app.etl.workers.queue_manager import QueueManager

logger = get_logger(__name__)


class JiraExtractionWorker:
    """
    Worker for processing Jira-specific extraction requests.

    Note: This is NOT a queue consumer itself. It's called from ExtractionWorkerRouter
    which is the actual queue consumer. This class contains provider-specific logic.

    Handles all Jira extraction types with built-in extraction logic.
    """

    def __init__(self, status_manager=None):
        """
        Initialize Jira extraction worker.

        Args:
            status_manager: WorkerStatusManager instance for sending status updates (injected by router)
        """
        self.database = get_database()
        self.status_manager = status_manager  # 🔑 Dependency injection
        logger.info("Initialized JiraExtractionWorker")

    async def _send_worker_status(self, step: str, tenant_id: int, job_id: int, status: str, step_type: str = None):
        """
        Send WebSocket status update for ETL job step.

        Delegates to the injected WorkerStatusManager.

        Args:
            step: ETL step name (extraction, transform, embedding)
            tenant_id: Tenant ID
            job_id: Job ID
            status: Status to send (running, finished, failed)
            step_type: Optional step type for logging
        """
        if self.status_manager:
            await self.status_manager.send_worker_status(step, tenant_id, job_id, status, step_type)
        else:
            logger.warning(f"⚠️ No status_manager available, skipping status update for job {job_id}")

    async def process_jira_extraction(self, extraction_type: str, message: Dict[str, Any]) -> bool:
        """
        Process Jira extraction message by routing to appropriate extraction method.

        Args:
            extraction_type: Type of extraction (e.g., 'jira_projects_and_issue_types')
            message: Message containing extraction parameters

        Returns:
            bool: True if extraction succeeded, False otherwise
        """
        try:
            logger.info(f"🚀 [JIRA] Processing {extraction_type} extraction")

            # Route to appropriate extraction method
            if extraction_type == 'jira_projects_and_issue_types':
                return await self._extract_projects_and_issue_types(message)
            elif extraction_type == 'jira_statuses_and_relationships':
                return await self._extract_statuses_and_relationships(message)
            elif extraction_type == 'jira_issues_with_changelogs':
                return await self._extract_issues_with_changelogs(message)
            elif extraction_type == 'jira_dev_status':
                return await self._fetch_jira_dev_status(message)
            elif extraction_type == 'jira_custom_fields':
                return await self._extract_jira_custom_fields(message)
            else:
                logger.error(f"❌ [JIRA] Unknown extraction type: {extraction_type}")
                return False

        except Exception as e:
            logger.error(f"❌ [JIRA] Error processing {extraction_type}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    def _get_jira_client(self, tenant_id: int, integration_id: int) -> tuple:
        """
        Get integration and create Jira client.

        Returns:
            tuple: (integration, jira_client) or (None, None) if failed
        """
        try:
            database = get_database()
            with database.get_read_session_context() as db:
                query = text("""
                    SELECT id, provider, base_url, username, password, active, settings
                    FROM integrations
                    WHERE id = :integration_id AND tenant_id = :tenant_id
                """)
                result = db.execute(query, {
                    'integration_id': integration_id,
                    'tenant_id': tenant_id
                }).fetchone()

                if not result:
                    logger.error(f"Integration {integration_id} not found for tenant {tenant_id}")
                    return None, None

                integration_data = {
                    'id': result[0],
                    'provider': result[1],
                    'base_url': result[2],
                    'username': result[3],
                    'password': result[4],
                    'active': result[5],
                    'settings': result[6]  # JSONB field with projects list
                }

            # Decrypt password if needed
            from app.core.config import AppConfig
            password = integration_data['password']
            if password:
                try:
                    key = AppConfig.load_key()
                    password = AppConfig.decrypt_token(password, key)
                except Exception as e:
                    logger.warning(f"Failed to decrypt password, using as-is: {e}")

            # Create Jira client with username, token, base_url
            jira_client = JiraAPIClient(
                username=integration_data['username'],
                token=password,
                base_url=integration_data['base_url']
            )

            return integration_data, jira_client

        except Exception as e:
            logger.error(f"Error getting Jira client: {e}")
            return None, None

    def _store_raw_data(self, tenant_id: int, integration_id: int, data_type: str, raw_data: dict) -> Optional[int]:
        """
        Store raw extraction data in database.

        Returns:
            int: raw_data_id if successful, None otherwise
        """
        try:
            database = get_database()
            with database.get_write_session_context() as db:
                insert_query = text("""
                    INSERT INTO raw_extraction_data (
                        tenant_id, integration_id, type, raw_data, created_at
                    ) VALUES (
                        :tenant_id, :integration_id, :type, CAST(:raw_data AS jsonb), NOW()
                    ) RETURNING id
                """)

                import json
                result = db.execute(insert_query, {
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'type': data_type,
                    'raw_data': json.dumps(raw_data)
                })

                raw_data_id = result.fetchone()[0]
                logger.info(f"✅ Stored raw data with ID: {raw_data_id}")
                return raw_data_id

        except Exception as e:
            logger.error(f"Error storing raw data: {e}")
            return None

    def _queue_next_step(self, tenant_id: int, integration_id: int, job_id: int, next_step: str, token: str = None, old_last_sync_date: str = None, first_item: bool = False, last_item: bool = False, last_job_item: bool = False):
        """
        Queue the next extraction step.

        This queues a new extraction job step (e.g., from projects to statuses).
        Uses direct message publishing instead of publish_extraction_job since
        we're triggering a new step, not queuing individual items.
        """
        try:
            queue_manager = QueueManager()

            # Build message for next extraction step
            message = {
                'tenant_id': tenant_id,
                'integration_id': integration_id,
                'job_id': job_id,
                'type': next_step,
                'provider': 'jira',
                'token': token,
                'old_last_sync_date': old_last_sync_date,   # 🔑 Forward last_sync_date through pipeline
                'first_item': first_item,                   # 🔑 True only on first item of job
                'last_item': last_item,                     # 🔑 True only on last item of job
                'last_job_item': last_job_item              # 🔑 True only on last item of job
            }

            # Get tenant tier and route to tier-based extraction queue
            tier = queue_manager._get_tenant_tier(tenant_id)
            tier_queue = queue_manager.get_tier_queue_name(tier, 'extraction')

            success = queue_manager._publish_message(tier_queue, message)

            if success:
                logger.info(f"✅ Queued next step: {next_step} to {tier_queue}")
            else:
                logger.error(f"❌ Failed to queue next step: {next_step}")

        except Exception as e:
            logger.error(f"Error queuing next step: {e}")

    def _update_job_status(self, job_id: int, status: str, error_message: str = None):
        """
        Update job overall status in database.

        Args:
            job_id: Job ID
            status: Overall status (READY, RUNNING, FINISHED, FAILED)
            error_message: Optional error message
        """
        try:
            database = get_database()
            with database.get_write_session_context() as db:
                if error_message:
                    # Update overall status and error message
                    # Use string formatting for the status value to avoid parameter binding issues
                    query = text(f"""
                        UPDATE etl_jobs
                        SET status = jsonb_set(status, ARRAY['overall'], '"{status}"'::jsonb),
                            error_message = :error_message,
                            last_updated_at = NOW()
                        WHERE id = :job_id
                    """)
                    db.execute(query, {
                        'error_message': error_message,
                        'job_id': job_id
                    })
                else:
                    # Update overall status only
                    query = text(f"""
                        UPDATE etl_jobs
                        SET status = jsonb_set(status, ARRAY['overall'], '"{status}"'::jsonb),
                            last_updated_at = NOW()
                        WHERE id = :job_id
                    """)
                    db.execute(query, {
                        'job_id': job_id
                    })

            logger.info(f"Updated job {job_id} overall status to {status}")

        except Exception as e:
            logger.error(f"Error updating job status: {e}")

    async def _extract_projects_and_issue_types(self, message: Dict[str, Any]) -> bool:
        """
        Extract Jira projects and issue types.

        This is Step 1 of the Jira extraction pipeline.
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            token = message.get('token')
            old_last_sync_date = message.get('old_last_sync_date')  # 🔑 Extract from message

            logger.info(f"🏁 [JIRA] Starting projects and issue types extraction")

            # Get Jira client
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                self._update_job_status(job_id, "FAILED", "Failed to initialize Jira client")
                return False

            # Fetch projects from Jira
            projects = jira_client.get_projects(expand="issueTypes")

            if not projects:
                logger.warning(f"No projects found")
                # Still queue next step even if no projects
                self._queue_next_step(tenant_id, integration_id, job_id, 'jira_statuses_and_relationships', token, old_last_sync_date)
                return True

            logger.info(f"📊 Found {len(projects)} projects")

            # Store raw data
            raw_data_id = self._store_raw_data(tenant_id, integration_id, 'jira_projects_and_issue_types', projects)
            if not raw_data_id:
                self._update_job_status(job_id, "FAILED", "Failed to store raw data")
                return False

            # Queue to transform
            queue_manager = QueueManager()
            success = queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                raw_data_id=raw_data_id,
                data_type='jira_projects_and_issue_types',
                job_id=job_id,
                provider='jira',
                old_last_sync_date=old_last_sync_date,  # 🔑 Forward to transform
                first_item=True,
                last_item=True,
                last_job_item=False,  # Not the final step
                token=token
            )

            if not success:
                self._update_job_status(job_id, "FAILED", "Failed to queue for transformation")
                return False

            # Send finished status for this step
            await self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_projects_and_issue_types")

            # Queue next step
            self._queue_next_step(tenant_id, integration_id, job_id, 'jira_statuses_and_relationships', token, old_last_sync_date, True, False, False)

            logger.info(f"✅ Projects and issue types extraction completed")
            return True

        except Exception as e:
            logger.error(f"❌ Error in projects extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_status(job_id, "FAILED", str(e))
            return False

    async def _extract_statuses_and_relationships(self, message: Dict[str, Any]) -> bool:
        """
        Extract Jira statuses and project relationships.

        This is Step 2 of the Jira extraction pipeline.
        Fetches statuses for EACH project individually and queues one message per project.
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            token = message.get('token')
            old_last_sync_date = message.get('old_last_sync_date')  # 🔑 Extract from message

            logger.info(f"🏁 [JIRA] Starting statuses and relationships extraction")

            # Get Jira client and integration settings
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                self._update_job_status(job_id, "FAILED", "Failed to initialize Jira client")
                return False

            # Get projects from integration settings
            settings = integration.get('settings', {})
            project_keys = settings.get('projects', [])

            if not project_keys:
                logger.warning(f"No projects configured in integration settings")
                # Queue next step even if no projects
                self._queue_next_step(tenant_id, integration_id, job_id, 'jira_issues_with_changelogs', token, old_last_sync_date, True, False, False)
                return True

            logger.info(f"📊 Fetching statuses for {len(project_keys)} projects: {project_keys}")

            queue_manager = QueueManager()
            total_projects = len(project_keys)

            # Fetch statuses for each project
            for i, project_key in enumerate(project_keys):
                is_first = (i == 0)
                is_last = (i == total_projects - 1)

                logger.info(f"📋 Fetching statuses for project {project_key} ({i+1}/{total_projects})")

                # Fetch project-specific statuses
                project_statuses = jira_client.get_project_statuses(project_key)

                if not project_statuses:
                    logger.warning(f"No statuses found for project {project_key}")
                    continue

                logger.info(f"📊 Found {len(project_statuses)} issue types with statuses for project {project_key}")

                # Store raw data (one per project) - wrap in dict with project_key
                raw_data_id = self._store_raw_data(
                    tenant_id,
                    integration_id,
                    'jira_project_statuses',  # Type per documentation
                    {
                        'project_key': project_key,
                        'statuses': project_statuses  # Array of issue types with statuses
                    }
                )

                if not raw_data_id:
                    logger.error(f"Failed to store raw data for project {project_key}")
                    continue

                # Queue to transform (one message per project)
                success = queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    raw_data_id=raw_data_id,
                    data_type='jira_statuses_and_relationships',
                    job_id=job_id,
                    provider='jira',
                    old_last_sync_date=old_last_sync_date,  # 🔑 Forward to transform
                    first_item=is_first,  # True only for first project
                    last_item=is_last,    # True only for last project
                    last_job_item=False,  # Not the final step
                    token=token
                )

                if not success:
                    logger.error(f"Failed to queue project {project_key} for transformation")
                    continue

                logger.info(f"✅ Queued project {project_key} to transform (first_item={is_first}, last_item={is_last})")

            # Send finished status for this step
            await self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_statuses_and_relationships")

            # Queue next step (issues with changelogs)
            self._queue_next_step(tenant_id, integration_id, job_id, 'jira_issues_with_changelogs', token, old_last_sync_date, True)

            logger.info(f"✅ Statuses and relationships extraction completed for {total_projects} projects")
            return True

        except Exception as e:
            logger.error(f"❌ Error in statuses extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_status(job_id, "FAILED", str(e))
            return False

    async def _extract_issues_with_changelogs(self, message: Dict[str, Any]) -> bool:
        """
        Extract Jira issues with changelogs.

        This is Step 3 of the Jira extraction pipeline.
        Fetches ALL issues based on last_sync_date and projects filter,
        then queues individual messages to transform for each issue.
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            token = message.get('token')
            old_last_sync_date = message.get('old_last_sync_date')  # 🔑 Extract from message

            logger.info(f"🏁 [JIRA] Starting issues with changelogs extraction")

            # Get Jira client and integration settings
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                self._update_job_status(job_id, "FAILED", "Failed to initialize Jira client")
                return False

            # Get projects from integration settings
            settings = integration.get('settings', {})
            project_keys = settings.get('projects', [])
            base_search = settings.get('base_search')  # Optional additional filter

            if not project_keys:
                logger.warning(f"No projects configured in integration settings")
                # Send completion message (no issues case)
                queue_manager = QueueManager()
                queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    raw_data_id=None,  # Completion message
                    data_type='jira_issues_with_changelogs',
                    job_id=job_id,
                    provider='jira',
                    old_last_sync_date=old_last_sync_date,  # 🔑 Forward to transform
                    first_item=True,
                    last_item=True,
                    last_job_item=True,  # Skip Step 4 (no issues)
                    token=token
                )
                await self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_issues_with_changelogs")
                return True

            # 🔑 Use old_last_sync_date from message (passed from jobs.py)
            # Convert string to datetime if needed for JQL formatting
            last_sync_date = None
            if old_last_sync_date:
                from datetime import datetime
                try:
                    # Parse YYYY-MM-DD format to datetime
                    last_sync_date = datetime.strptime(old_last_sync_date, '%Y-%m-%d')
                except Exception as e:
                    logger.warning(f"Failed to parse old_last_sync_date '{old_last_sync_date}': {e}")
                    last_sync_date = None

            # Build JQL query with projects filter and date filter
            jql_parts = []

            # Projects filter
            projects_filter = " OR ".join([f"project = {key}" for key in project_keys])
            jql_parts.append(f"({projects_filter})")

            # Base search filter (optional)
            if base_search:
                jql_parts.append(f"({base_search})")

            # Date filter
            if last_sync_date:
                date_str = last_sync_date.strftime('%Y-%m-%d %H:%M')
                jql_parts.append(f"updated >= '{date_str}'")
                logger.info(f"📅 Incremental sync from: {last_sync_date}")
            else:
                logger.info(f"📅 Full sync (no last_sync_date)")

            # Combine all parts
            jql = " AND ".join(jql_parts) + " ORDER BY updated ASC"
            logger.info(f"📋 JQL Query: {jql}")

            # Fetch issues from Jira (using fields=['*all'] to get all fields including development)
            issues_response = jira_client.search_issues(
                jql=jql,
                expand=['changelog'],
                fields=['*all'],
                max_results=100
            )

            if not issues_response or not issues_response.get('issues'):
                logger.warning(f"No issues found")
                # Send completion message (no issues case)
                queue_manager = QueueManager()
                queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    raw_data_id=None,  # Completion message
                    data_type='jira_issues_with_changelogs',
                    job_id=job_id,
                    provider='jira',
                    old_last_sync_date=old_last_sync_date,  # 🔑 Forward to transform
                    first_item=True,
                    last_item=True,
                    last_job_item=True,  # Skip Step 4 (no issues)
                    token=token
                )
                await self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_issues_with_changelogs")
                return True

            issues_list = issues_response.get('issues', [])
            total_issues = len(issues_list)
            logger.info(f"📊 Found {total_issues} issues")

            # 🔑 Get development field external_id from custom_fields_mapping table
            development_field_external_id = None
            database = get_database()
            with database.get_read_session_context() as db:
                query = text("""
                    SELECT cf.external_id
                    FROM custom_fields_mapping cfm
                    JOIN custom_fields cf ON cf.id = cfm.development_field_id
                    WHERE cfm.tenant_id = :tenant_id
                    AND cfm.integration_id = :integration_id
                    AND cfm.active = true
                    AND cf.active = true
                """)
                result = db.execute(query, {
                    'tenant_id': tenant_id,
                    'integration_id': integration_id
                }).fetchone()

                if result:
                    development_field_external_id = result[0]
                    logger.info(f"📋 Development field from mapping: {development_field_external_id}")
                else:
                    logger.info(f"⚠️ No development field mapped in custom_fields_mapping table")

            # Track issues with development field (for Step 4)
            issues_with_dev = []

            queue_manager = QueueManager()

            # Loop through issues and queue individual messages to transform
            for i, issue in enumerate(issues_list):
                is_first = (i == 0)
                is_last = (i == total_issues - 1)

                issue_key = issue.get('key', 'unknown')
                logger.info(f"📋 Processing issue {issue_key} ({i+1}/{total_issues})")

                # 🔑 Check if issue has development field using mapped field from database
                has_development = False
                if development_field_external_id:
                    fields = issue.get('fields', {})
                    field_value = fields.get(development_field_external_id)

                    # Check if field exists and has value
                    if field_value:
                        has_development = True
                        logger.info(f"✅ Issue {issue_key} has development field {development_field_external_id}")

                if has_development:
                    issues_with_dev.append(issue)

                # Store raw data (one per issue) - wrap in 'issue' key for transform worker
                raw_data_id = self._store_raw_data(
                    tenant_id,
                    integration_id,
                    'jira_issues_with_changelogs',
                    {'issue': issue}  # Wrap in dict with 'issue' key
                )

                if not raw_data_id:
                    logger.error(f"Failed to store raw data for issue {issue_key}")
                    continue

                # Determine last_job_item flag
                # If this is the last issue AND no issues have development field, set last_job_item=True
                last_job_item = False
                if is_last and len(issues_with_dev) == 0:
                    last_job_item = True  # No Step 4 needed
                    logger.info(f"🎯 Last issue with NO dev status - setting last_job_item=True")

                # Queue to transform (one message per issue)
                success = queue_manager.publish_transform_job(
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    raw_data_id=raw_data_id,
                    data_type='jira_issues_with_changelogs',
                    job_id=job_id,
                    provider='jira',
                    old_last_sync_date=old_last_sync_date,  # 🔑 Forward to transform
                    first_item=is_first,      # True only for first issue
                    last_item=is_last,        # True only for last issue
                    last_job_item=last_job_item,  # True only if last issue AND no dev status
                    token=token
                )

                if not success:
                    logger.error(f"Failed to queue issue {issue_key} for transformation")
                    continue

                logger.info(f"✅ Queued issue {issue_key} to transform (first_item={is_first}, last_item={is_last}, last_job_item={last_job_item})")

            # Send finished status for this step
            await self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_issues_with_changelogs")

            # If any issues have development field, queue Step 4 extraction jobs
            if issues_with_dev:
                logger.info(f"📋 Queuing Step 4 (dev_status) for {len(issues_with_dev)} issues with development field")

                total_dev_issues = len(issues_with_dev)
                for i, issue in enumerate(issues_with_dev):
                    is_first_dev = (i == 0)
                    is_last_dev = (i == total_dev_issues - 1)

                    issue_key = issue.get('key')
                    issue_id = issue.get('id')

                    # Queue extraction job for dev_status
                    dev_message = {
                        'tenant_id': tenant_id,
                        'integration_id': integration_id,
                        'job_id': job_id,
                        'type': 'jira_dev_status',
                        'provider': 'jira',
                        'issue_id': issue_id,
                        'issue_key': issue_key,
                        'first_item': is_first_dev,
                        'last_item': is_last_dev,
                        'token': token,
                        'old_last_sync_date': old_last_sync_date  # 🔑 Forward to Step 4
                    }

                    tier = queue_manager._get_tenant_tier(tenant_id)
                    tier_queue = queue_manager.get_tier_queue_name(tier, 'extraction')
                    queue_manager._publish_message(tier_queue, dev_message)

                    logger.info(f"✅ Queued dev_status extraction for issue {issue_key} (first_item={is_first_dev}, last_item={is_last_dev})")
            else:
                logger.info(f"⏭️ No issues with development field - Step 4 will be skipped")

            logger.info(f"✅ Issues with changelogs extraction completed ({total_issues} issues, {len(issues_with_dev)} with dev status)")
            return True

        except Exception as e:
            logger.error(f"❌ Error in issues extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_status(job_id, "FAILED", str(e))
            return False

    async def _fetch_jira_dev_status(self, message: Dict[str, Any]) -> bool:
        """
        Fetch Jira development status.

        This is Step 4 (final step) of the Jira extraction pipeline.
        This step is ONLY queued if Step 3 found issues with development field.
        Each message contains a single issue to fetch dev status for.
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            token = message.get('token')
            old_last_sync_date = message.get('old_last_sync_date')  # 🔑 Extract from message
            issue_id = message.get('issue_id')
            issue_key = message.get('issue_key')
            first_item = message.get('first_item', False)
            last_item = message.get('last_item', False)

            logger.info(f"🏁 [JIRA] Starting dev status extraction for issue {issue_key} (first_item={first_item}, last_item={last_item})")

            # Get Jira client
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                self._update_job_status(job_id, "FAILED", "Failed to initialize Jira client")
                return False

            # Fetch dev status for this issue
            try:
                dev_status = jira_client.get_dev_status(issue_id)

                if not dev_status:
                    logger.warning(f"No dev status found for issue {issue_key}")
                    # Even if no data, we still need to queue to transform to maintain the chain
                    # Use empty dict as placeholder
                    dev_status = {}

                logger.info(f"📊 Fetched dev status for issue {issue_key}")

            except Exception as e:
                logger.error(f"Error fetching dev status for issue {issue_key}: {e}")
                # Use empty dict as placeholder to maintain the chain
                dev_status = {}

            # Store raw data
            raw_data_id = self._store_raw_data(
                tenant_id,
                integration_id,
                'jira_dev_status',
                {
                    'issue_id': issue_id,
                    'issue_key': issue_key,
                    'dev_status': dev_status
                }
            )

            if not raw_data_id:
                logger.error(f"Failed to store raw data for issue {issue_key}")
                self._update_job_status(job_id, "FAILED", f"Failed to store dev status for {issue_key}")
                return False

            # Queue to transform
            queue_manager = QueueManager()
            success = queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                raw_data_id=raw_data_id,
                data_type='jira_dev_status',
                job_id=job_id,
                provider='jira',
                old_last_sync_date=old_last_sync_date,  # 🔑 Forward to transform
                first_item=first_item,      # True only for first dev status
                last_item=last_item,        # True only for last dev status
                last_job_item=last_item,    # 🎯 True on last item (final step)
                token=token
            )

            if not success:
                logger.error(f"Failed to queue dev status for issue {issue_key} to transform")
                self._update_job_status(job_id, "FAILED", f"Failed to queue dev status for {issue_key}")
                return False

            logger.info(f"✅ Queued dev status for issue {issue_key} to transform (first_item={first_item}, last_item={last_item}, last_job_item={last_item})")

            # Send finished status ONLY on last item
            if last_item:
                await self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_dev_status")
                logger.info(f"✅ Dev status extraction completed (last item)")

            return True

        except Exception as e:
            logger.error(f"❌ Error in dev status extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_status(job_id, "FAILED", str(e))
            return False

    async def _extract_jira_custom_fields(self, message: Dict[str, Any]) -> bool:
        """
        Extract Jira custom fields.

        This is used for custom fields discovery on the custom fields mapping page.
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            token = message.get('token')

            logger.info(f"🏁 [JIRA] Starting custom fields extraction")

            # Get Jira client
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                self._update_job_status(job_id, "FAILED", "Failed to initialize Jira client")
                return False

            # Fetch custom fields from Jira
            # This would normally call the createmeta endpoint
            logger.info(f"⏭️ Custom fields extraction not implemented yet")

            # Send finished status for this step
            await self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_custom_fields")

            logger.info(f"✅ Custom fields extraction completed (skipped)")
            return True

        except Exception as e:
            logger.error(f"❌ Error in custom fields extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_status(job_id, "FAILED", str(e))
            return False
