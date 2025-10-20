"""
Extraction Worker - Handles additional data extraction requests (TIER-BASED QUEUE ARCHITECTURE).

This worker processes extraction requests that require additional API calls,
such as fetching dev_status for Jira issues.

Flow:
1. Receive extraction request from extraction_queue_{tier} (e.g., extraction_queue_premium)
2. Call external API to fetch data
3. Store raw data in raw_extraction_data table
4. Queue for transformation in transform_queue_{tier}

Tier-Based Queue Architecture:
- Workers consume from tier-based queues (extraction_queue_free, extraction_queue_premium, etc.)
- Each message contains tenant_id for proper routing
- Multiple workers per tier share the same queue
"""

import json
import time
from typing import Dict, Any, List, Optional

from app.workers.base_worker import BaseWorker
from app.core.logging_config import get_logger
from app.etl.queue.queue_manager import QueueManager
from sqlalchemy import text

logger = get_logger(__name__)


class ExtractionWorker(BaseWorker):
    """
    Worker that handles additional extraction requests (tier-based queue architecture).

    Supports different extraction types:
    - jira_dev_status_fetch: Fetch dev_status for a Jira issue
    - (future) github_pr_details_fetch: Fetch PR details
    - (future) jira_issue_links_fetch: Fetch issue links

    Tier-Based Queue Mode:
    - Consumes from tier-based queue (e.g., extraction_queue_premium)
    - Uses tenant_id from message for proper data routing
    """

    def __init__(self, queue_name: str, worker_number: int = 0, tenant_ids: Optional[List[int]] = None):
        """
        Initialize extraction worker for tier-based queue.

        Args:
            queue_name: Name of the tier-based extraction queue (e.g., 'extraction_queue_premium')
            worker_number: Worker instance number (for logging)
            tenant_ids: Deprecated (kept for backward compatibility)
        """
        super().__init__(queue_name)
        self.worker_number = worker_number
        logger.info(f"Initialized ExtractionWorker #{worker_number} for tier queue: {queue_name}")

    def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Enhanced process_message with retry logic and dead letter queue support.

        Args:
            message: Message containing extraction request details

        Returns:
            bool: True if processing succeeded
        """
        max_retries = 3
        retry_count = message.get('retry_count', 0)

        try:
            # Call the original process_message logic
            return self._process_message_with_retries(message)

        except Exception as e:
            logger.error(f"Error processing extraction message (attempt {retry_count + 1}/{max_retries}): {e}")

            if retry_count < max_retries - 1:
                # Retry with exponential backoff
                self._retry_message(message, retry_count + 1)
                return True  # Message will be retried
            else:
                # Send to dead letter queue
                self._send_to_dead_letter_queue(message, str(e))
                return False

    def _process_message_with_retries(self, message: Dict[str, Any]) -> bool:
        """
        Original process_message logic renamed for retry handling.
        """
        try:
            # Support both 'extraction_type' and 'type' field names for compatibility
            extraction_type = message.get('extraction_type') or message.get('type')
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')

            if not all([extraction_type, tenant_id, integration_id]):
                logger.error(f"❌ [DEBUG] Missing required fields in extraction message: {message}")
                return False

            logger.info(f"🚀 [DEBUG] Processing {extraction_type} extraction request for tenant {tenant_id}, integration {integration_id}, job {job_id}")

            # Route to appropriate extraction handler
            if extraction_type == 'jira_dev_status_fetch':
                logger.info(f"📋 [DEBUG] Routing to _fetch_jira_dev_status")
                return self._fetch_jira_dev_status(message)
            elif extraction_type == 'jira_projects_and_issue_types':
                logger.info(f"📋 [DEBUG] Routing to _extract_jira_projects_and_issue_types")
                # Use asyncio.create_task to run async method from sync context
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self._extract_jira_projects_and_issue_types(message))
                finally:
                    loop.close()
            elif extraction_type == 'jira_statuses_and_relationships':
                logger.info(f"📋 [DEBUG] Routing to _extract_jira_statuses_and_relationships")
                return self._extract_jira_statuses_and_relationships(message)
            elif extraction_type == 'jira_issues_with_changelogs':
                logger.info(f"📋 [DEBUG] Routing to _extract_jira_issues_with_changelogs")
                return self._extract_jira_issues_with_changelogs(message)
            elif extraction_type == 'jira_custom_fields':
                logger.info(f"📋 [DEBUG] Routing to _extract_jira_custom_fields")
                return self._extract_jira_custom_fields(message)
            else:
                logger.warning(f"❓ [DEBUG] Unknown extraction type: {extraction_type}")
                return False

        except Exception as e:
            logger.error(f"💥 [DEBUG] Error processing extraction message: {e}")
            import traceback
            logger.error(f"💥 [DEBUG] Full traceback: {traceback.format_exc()}")

            # Update job status to FAILED if we have job_id
            if job_id:
                try:
                    self._update_job_status_failed(job_id, str(e), tenant_id)
                except Exception as update_error:
                    logger.error(f"Failed to update job status to FAILED: {update_error}")

            raise  # Re-raise for retry handling

    def _update_job_status_failed(self, job_id: int, error_message: str, tenant_id: int):
        """Update ETL job status to FAILED with error message"""
        try:
            from app.core.database import get_database
            from sqlalchemy import text

            database = get_database()
            with database.get_write_session_context() as session:
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = 'FAILED',
                        error_message = :error_message,
                        last_updated_at = NOW()
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                session.execute(update_query, {
                    'job_id': job_id,
                    'tenant_id': tenant_id,
                    'error_message': error_message[:500]  # Truncate to avoid DB issues
                })
                session.commit()

                logger.info(f"✅ Updated job {job_id} status to FAILED")

        except Exception as e:
            logger.error(f"❌ Failed to update job status to FAILED: {e}")

    def _fetch_jira_dev_status(self, message: Dict[str, Any]) -> bool:
        """
        Fetch dev_status for a Jira issue.
        
        Args:
            message: {
                'type': 'jira_dev_status_fetch',
                'issue_id': '12345',
                'issue_key': 'PROJ-123',
                'tenant_id': 1,
                'integration_id': 1
            }
            
        Returns:
            bool: True if fetch succeeded
        """
        try:
            issue_id = message.get('issue_id')
            issue_key = message.get('issue_key')
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            
            if not all([issue_id, issue_key]):
                logger.error(f"Missing issue_id or issue_key in message: {message}")
                return False
            
            logger.debug(f"Fetching dev_status for issue {issue_key} (ID: {issue_id})")
            
            # Get integration details and create Jira client
            from app.core.database import get_database
            from app.models.unified_models import Integration
            
            database = get_database()
            with database.get_read_session_context() as session:
                integration = session.query(Integration).filter(
                    Integration.id == integration_id,
                    Integration.tenant_id == tenant_id
                ).first()
                
                if not integration:
                    logger.error(f"Integration {integration_id} not found for tenant {tenant_id}")
                    return False
                
                if not integration.active:
                    logger.warning(f"Integration {integration_id} is inactive, skipping dev_status fetch")
                    return True  # Not an error, just skip
            
            # Create Jira client and fetch dev_status
            from app.etl.jira_client import JiraAPIClient

            # Use the factory method that handles decryption automatically
            jira_client = JiraAPIClient.create_from_integration(integration)
            
            # Fetch dev_status from Jira API
            dev_status_data = jira_client.get_dev_status(issue_id)

            if not dev_status_data:
                logger.debug(f"No dev_status data found for issue {issue_key}")
                return True  # Not an error, just no data

            # Check if dev_status has actual PR data (not just empty arrays)
            detail = dev_status_data.get('detail', [])
            has_pr_data = False
            for item in detail:
                if item.get('pullRequests') or item.get('branches') or item.get('repositories'):
                    has_pr_data = True
                    break

            if not has_pr_data:
                logger.debug(f"Dev_status for issue {issue_key} has no PR data (empty arrays) - skipping")
                return True  # Not an error, just no useful data

            logger.debug(f"Fetched dev_status for issue {issue_key}: {len(detail)} items with PR data")
            
            # Store raw data in raw_extraction_data table
            with self.get_db_session() as db:
                insert_query = text("""
                    INSERT INTO raw_extraction_data (
                        tenant_id, integration_id, type, raw_data, status, created_at, last_updated_at
                    ) VALUES (
                        :tenant_id, :integration_id, :type, :raw_data, :status, NOW(), NOW()
                    ) RETURNING id
                """)
                
                result = db.execute(insert_query, {
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'type': 'jira_dev_status',
                    'raw_data': json.dumps({
                        'issue_id': issue_id,
                        'issue_key': issue_key,
                        'dev_status': dev_status_data
                    }),
                    'status': 'pending'
                })
                
                raw_data_id = result.fetchone()[0]
                db.commit()
                
                logger.debug(f"Stored dev_status as raw_data_id={raw_data_id}")
            
            # Queue for transformation with ETL job tracking
            queue_manager = QueueManager()

            # Forward ETL job tracking information from the original message
            etl_job_id = message.get('etl_job_id')
            provider_name = message.get('provider_name')
            last_sync_date = message.get('last_sync_date')
            last_issue_changelog_item = message.get('last_issue_changelog_item', False)

            # ✅ Set last_item=true if this dev_status is for the last issue changelog item
            last_item = last_issue_changelog_item

            success = queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                data_type='jira_dev_status',
                raw_data_id=raw_data_id,
                etl_job_id=etl_job_id,
                provider_name=provider_name,
                last_sync_date=last_sync_date,
                first_item=False,
                last_issue_changelog_item=False,  # This flag is consumed, don't forward
                last_item=last_item  # ✅ Set last_item=true to trigger job completion
            )
            
            if success:
                logger.info(f"✅ Fetched and queued dev_status for issue {issue_key}")
                return True
            else:
                logger.error(f"Failed to queue dev_status for transformation (raw_data_id={raw_data_id})")
                return False
                
        except Exception as e:
            logger.error(f"Error fetching dev_status for issue {message.get('issue_key', 'unknown')}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    async def _extract_jira_projects_and_issue_types(self, message: Dict[str, Any]) -> bool:
        """
        Extract Jira projects and issue types.

        Args:
            message: {
                'type': 'jira_projects_and_issue_types',
                'tenant_id': 1,
                'integration_id': 1,
                'job_id': 123
            }

        Returns:
            bool: True if extraction succeeded
        """
        try:        
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')

            logger.info(f"🏁 [DEBUG] Starting Jira projects and issue types extraction for tenant {tenant_id}, integration {integration_id}, job {job_id}")

            # Get integration and create Jira client
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                return False

            # Update job status to RUNNING
            self._update_job_status(job_id, "RUNNING", "Extracting projects and issue types")

            # Send WebSocket status: extraction worker starting
            step_name = message.get('type', 'jira_projects_and_issue_types')  # Get step name from message
            await self._send_worker_status("extraction", tenant_id, job_id, "running", step_name)



            # Extract projects and issue types using existing logic
            from app.etl.jira_extraction import _extract_projects_and_issue_types

            # Create a simple progress tracker for this step
            class SimpleProgressTracker:
                def __init__(self, tenant_id, job_id, worker):
                    self.tenant_id = tenant_id
                    self.job_id = job_id
                    self.worker = worker

                async def update_step_progress(self, step, progress, message):
                    # Log progress without WebSocket updates
                    logger.info(f"Step {step} progress: {progress:.1%} - {message}")

                async def complete_step(self, step_index, message):
                    """Mark a step as completed."""
                    await self.update_step_progress(step_index, 1.0, message)

            progress_tracker = SimpleProgressTracker(tenant_id, job_id, self)

            # Execute extraction (this is async, so we use await)
            result = await _extract_projects_and_issue_types(
                jira_client, integration_id, tenant_id, progress_tracker, step_index=0, job_id=job_id
            )

            if result.get('success'):
                logger.info(f"✅ [DEBUG] Projects and issue types extraction completed for tenant {tenant_id}")

                # Send WebSocket status: extraction worker finished
                await self._send_worker_status("extraction", tenant_id, job_id, "finished", step_name)

                # Queue to transform with enhanced message (bulk processing)
                await self._queue_to_transform(tenant_id, integration_id, job_id, step_name,
                                             first_item=True, last_item=True, bulk_processing=True)

                # Queue next step: statuses and relationships
                logger.info(f"🔄 [DEBUG] Step 1 completed, queuing next step: jira_statuses_and_relationships")
                self._queue_next_extraction_step(tenant_id, integration_id, job_id, 'jira_statuses_and_relationships')
                return True
            else:
                logger.error(f"❌ [DEBUG] Projects and issue types extraction failed: {result.get('error')}")
                # Send WebSocket status: extraction worker failed
                await self._send_worker_status("extraction", tenant_id, job_id, "failed", "jira_projects_and_issue_types",
                                             error_message=result.get('error'))
                self._update_job_status(job_id, "FAILED", f"Extraction failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Error in projects and issue types extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_status(job_id, "FAILED", f"Extraction error: {str(e)}")
            return False

    def _extract_jira_statuses_and_relationships(self, message: Dict[str, Any]) -> bool:
        """
        Extract Jira statuses and relationships.
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')

            logger.info(f"🏁 [DEBUG] Starting Jira statuses and relationships extraction for tenant {tenant_id}, integration {integration_id}, job {job_id}")

            # Get integration and create Jira client
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                return False



            # Extract statuses and relationships using existing logic
            from app.etl.jira_extraction import _extract_statuses_and_relationships

            # Create progress tracker
            class SimpleProgressTracker:
                def __init__(self, tenant_id, job_id, worker):
                    self.tenant_id = tenant_id
                    self.job_id = job_id
                    self.worker = worker

                async def update_step_progress(self, step, progress, message):
                    # Log progress without WebSocket updates
                    logger.info(f"Step {step} progress: {progress:.1%} - {message}")

                async def complete_step(self, step_index, message):
                    """Mark a step as completed."""
                    await self.update_step_progress(step_index, 1.0, message)

            progress_tracker = SimpleProgressTracker(tenant_id, job_id, self)

            # Execute extraction
            logger.info(f"🔍 [DEBUG] About to call _extract_statuses_and_relationships via asyncio.run")
            import asyncio
            try:
                result = asyncio.run(_extract_statuses_and_relationships(
                    jira_client, integration_id, tenant_id, progress_tracker, step_index=1
                ))
                logger.info(f"🔍 [DEBUG] _extract_statuses_and_relationships completed, result: {result}")
            except Exception as async_error:
                logger.error(f"❌ [DEBUG] Exception in asyncio.run: {async_error}")
                import traceback
                logger.error(f"Asyncio traceback: {traceback.format_exc()}")
                raise

            logger.debug(f"🔄 [DEBUG] Statuses extraction result: {result}")
            logger.info(f"🔍 [DEBUG] Checking result.get('success'): {result.get('success')} (type: {type(result.get('success'))})")
            logger.info(f"🔍 [DEBUG] Full result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")

            if result.get('success'):
                logger.info(f"✅ [DEBUG] Statuses and relationships extraction completed for tenant {tenant_id}")

                # Queue next step: issues with changelogs
                logger.info(f"🔄 [DEBUG] Step 2 completed, queuing next step: jira_issues_with_changelogs")
                self._queue_next_extraction_step(tenant_id, integration_id, job_id, 'jira_issues_with_changelogs')
                return True
            else:
                logger.error(f"❌ [DEBUG] Statuses and relationships extraction failed: {result.get('error')}")
                self._update_job_status(job_id, "FAILED", f"Extraction failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Error in statuses and relationships extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_status(job_id, "FAILED", f"Extraction error: {str(e)}")
            return False

    def _extract_jira_issues_with_changelogs(self, message: Dict[str, Any]) -> bool:
        """
        Extract Jira issues with changelogs.
        """

        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            incremental = message.get('incremental', True)

            logger.info(f"🏁 [DEBUG] Starting Jira issues with changelogs extraction for tenant {tenant_id}, integration {integration_id}, job {job_id}")

            # Get integration and create Jira client
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                return False



            # Extract issues with changelogs using existing logic
            from app.etl.jira_extraction import _extract_issues_with_changelogs

            # Create progress tracker
            class SimpleProgressTracker:
                def __init__(self, tenant_id, job_id, worker):
                    self.tenant_id = tenant_id
                    self.job_id = job_id
                    self.worker = worker

                async def update_step_progress(self, step, progress, message):
                    # Log progress without WebSocket updates
                    logger.info(f"Step {step} progress: {progress:.1%} - {message}")

                async def complete_step(self, step_index, message):
                    """Mark a step as completed."""
                    await self.update_step_progress(step_index, 1.0, message)

            progress_tracker = SimpleProgressTracker(tenant_id, job_id, self)

            # Execute extraction
            import asyncio
            result = asyncio.run(_extract_issues_with_changelogs(
                jira_client, integration_id, tenant_id, incremental, progress_tracker, job_id
            ))

            if result.get('success'):
                logger.info(f"✅ [DEBUG] Issues with changelogs extraction completed for tenant {tenant_id}")

                # ✅ FIXED: Issues extraction already publishes to transform queue internally
                # The transform worker will handle dev_status extraction queueing for items with "development" field
                # No need to queue anything else here - the cycle continues via transform worker
                logger.info(f"🏁 [DEBUG] Issues extraction completed - transform worker will handle dev_status cycle")
                return True
            else:
                logger.error(f"❌ [DEBUG] Issues with changelogs extraction failed: {result.get('error')}")
                self._update_job_status(job_id, "FAILED", f"Extraction failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Error in issues with changelogs extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_status(job_id, "FAILED", f"Extraction error: {str(e)}")
            return False

    def _extract_jira_custom_fields(self, message: Dict[str, Any]) -> bool:
        """
        Extract Jira custom fields.
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')

            logger.info(f"Starting Jira custom fields extraction for tenant {tenant_id}")

            # Get integration and create Jira client
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                return False



            # Extract custom fields using existing logic
            from app.etl.jira_extraction import _extract_custom_fields

            # Create progress tracker
            class SimpleProgressTracker:
                def __init__(self, tenant_id, job_id, worker):
                    self.tenant_id = tenant_id
                    self.job_id = job_id
                    self.worker = worker

                async def update_step_progress(self, step, progress, message):
                    # Log progress without WebSocket updates
                    logger.info(f"Step {step} progress: {progress:.1%} - {message}")

                async def complete_step(self, step_index, message):
                    """Mark a step as completed."""
                    await self.update_step_progress(step_index, 1.0, message)

            progress_tracker = SimpleProgressTracker(tenant_id, job_id, self)

            # Execute extraction
            import asyncio
            result = asyncio.run(_extract_custom_fields(
                jira_client, integration_id, tenant_id, progress_tracker, step_index=3
            ))

            if result.get('success'):
                logger.info(f"✅ Custom fields extraction completed for tenant {tenant_id}")

                # Queue for transformation
                self._update_job_status(job_id, "QUEUED_TRANSFORM", "Extraction completed, queuing for transformation")

                # TODO: Queue transform job here
                # queue_manager = QueueManager()
                # queue_manager.publish_transform_job(tenant_id, integration_id, job_id)
                return True
            else:
                logger.error(f"Custom fields extraction failed: {result.get('error')}")
                self._update_job_status(job_id, "FAILED", f"Extraction failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Error in custom fields extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_status(job_id, "FAILED", f"Extraction error: {str(e)}")
            return False

    def _get_jira_client(self, tenant_id: int, integration_id: int):
        """
        Get integration and create Jira client.
        Uses read replica for configuration queries to optimize performance.

        Returns:
            tuple: (integration, jira_client) or (None, None) if failed
        """
        try:
            from app.core.database import get_database
            from app.models.unified_models import Integration
            from app.etl.jira_client import JiraAPIClient

            database = get_database()
            with database.get_read_session_context() as session:
                integration = session.query(Integration).filter(
                    Integration.id == integration_id,
                    Integration.tenant_id == tenant_id
                ).first()

                if not integration:
                    logger.error(f"Integration {integration_id} not found for tenant {tenant_id}")
                    return None, None

                if not integration.active:
                    logger.warning(f"Integration {integration_id} is inactive, skipping extraction")
                    return None, None

            # Create Jira client
            jira_client = JiraAPIClient.create_from_integration(integration)
            return integration, jira_client

        except Exception as e:
            logger.error(f"Error creating Jira client: {e}")
            return None, None

    def _update_job_status(self, job_id: int, status: str, message: str = None):
        """
        Update job status in database.
        Uses write session (primary database) for status updates.
        """
        try:
            from app.core.database import get_database
            from sqlalchemy import text

            database = get_database()
            with database.get_write_session_context() as session:
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = :status, last_updated_at = NOW()
                    WHERE id = :job_id
                """)

                session.execute(update_query, {
                    'status': status,
                    'job_id': job_id
                })
                session.commit()

                logger.info(f"Updated job {job_id} status to {status}")
                if message:
                    logger.info(f"Job {job_id} message: {message}")

        except Exception as e:
            logger.error(f"Error updating job status: {e}")

    def _update_job_activity(self, job_id: int, message: str = None):
        """
        Update job last_updated_at to show activity without changing status.
        Extraction worker uses this to show progress while keeping status as QUEUED.
        """
        try:
            from app.core.database import get_database
            from sqlalchemy import text

            database = get_database()
            with database.get_write_session_context() as session:
                update_query = text("""
                    UPDATE etl_jobs
                    SET last_updated_at = NOW()
                    WHERE id = :job_id
                """)

                session.execute(update_query, {'job_id': job_id})
                session.commit()

                logger.info(f"Updated job {job_id} activity timestamp")
                if message:
                    logger.info(f"Job {job_id} message: {message}")

        except Exception as e:
            logger.error(f"Error updating job activity: {e}")

    async def _send_worker_status(self, worker_type: str, tenant_id: int, job_id: int,
                                 status: str, step: str, error_message: str = None):
        """Send WebSocket status update for worker progress and update database."""
        try:
            # Update database worker status
            self._update_worker_status_in_db(worker_type, tenant_id, job_id, status, step, error_message)

            # Send WebSocket notification
            from app.api.websocket_routes import get_job_websocket_manager

            job_websocket_manager = get_job_websocket_manager()
            await job_websocket_manager.send_worker_status(
                worker_type=worker_type,
                tenant_id=tenant_id,
                job_id=job_id,
                status=status,
                step=step,
                error_message=error_message
            )
            logger.info(f"[WS] Sent {worker_type} status '{status}' for step '{step}' (tenant {tenant_id}, job {job_id})")

        except Exception as e:
            logger.error(f"Error sending worker status: {e}")

    def _update_worker_status_in_db(self, worker_type: str, tenant_id: int, job_id: int, status: str, step: str, error_message: str = None):
        """Update worker status in JSON status structure"""
        try:
            from app.core.database import get_write_session
            from sqlalchemy import text
            import json

            with get_write_session() as session:
                # Update JSON status structure: status->steps->{step}->{worker_type} = status
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = jsonb_set(
                        status,
                        ARRAY['steps', :step, :worker_type],
                        to_jsonb(:worker_status::text)
                    ),
                    last_updated_at = NOW()
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                session.execute(update_query, {
                    'step': step,
                    'worker_type': worker_type,
                    'worker_status': status,
                    'job_id': job_id,
                    'tenant_id': tenant_id
                })
                session.commit()

                logger.info(f"Updated {worker_type} worker status to {status} for step {step} in job {job_id}")

        except Exception as e:
            logger.error(f"Failed to update worker status in database: {e}")

    async def _queue_to_transform(self, tenant_id: int, integration_id: int, job_id: int,
                                 step_type: str, first_item: bool = False, last_item: bool = False,
                                 bulk_processing: bool = False, external_id: str = None):
        """Queue data to transform worker with enhanced message structure."""
        try:
            from app.etl.queue.queue_manager import QueueManager

            queue_manager = QueueManager()

            message = {
                'tenant_id': tenant_id,
                'integration_id': integration_id,
                'job_id': job_id,
                'type': step_type,
                'external_id': external_id or f"bulk_{step_type}",
                # Queue processing flags
                'first_item': first_item,
                'last_item': last_item,
                'bulk_processing': bulk_processing,
                # WebSocket routing information
                'websocket_channels': [
                    f"transform_status_tenant_{tenant_id}_job_{job_id}",
                    f"embedding_status_tenant_{tenant_id}_job_{job_id}"
                ]
            }

            # Get tenant tier and route to tier-based transform queue
            tier = queue_manager._get_tenant_tier(tenant_id)
            tier_queue = queue_manager.get_tier_queue_name(tier, 'transform')

            logger.info(f"📤 [TRANSFORM] Queuing {step_type} to {tier_queue}: first_item={first_item}, last_item={last_item}")

            success = queue_manager._publish_message(tier_queue, message)

            if success:
                logger.info(f"✅ [TRANSFORM] Successfully queued {step_type} to transform")
            else:
                logger.error(f"❌ [TRANSFORM] Failed to queue {step_type} to transform")

        except Exception as e:
            logger.error(f"Error queuing to transform: {e}")

    def _queue_next_extraction_step(self, tenant_id: int, integration_id: int, job_id: int, next_step: str):
        """
        Queue the next extraction step.
        """
        try:
            logger.info(f"🔄 [DEBUG] Queuing next extraction step: {next_step} for tenant {tenant_id}, integration {integration_id}, job {job_id}")

            queue_manager = QueueManager()

            message = {
                'tenant_id': tenant_id,
                'integration_id': integration_id,
                'job_id': job_id,
                'type': next_step,
                # WebSocket routing information
                'websocket_channels': [
                    f"extraction_status_tenant_{tenant_id}_job_{job_id}",
                    f"transform_status_tenant_{tenant_id}_job_{job_id}",
                    f"embedding_status_tenant_{tenant_id}_job_{job_id}"
                ],
                # Queue processing flags - bulk steps have both true
                'first_item': True,
                'last_item': True,
                'bulk_processing': True  # Indicates this is a bulk step
            }

            logger.info(f"📤 [DEBUG] Message to queue: {message}")

            # Get tenant tier and route to tier-based queue
            tier = queue_manager._get_tenant_tier(tenant_id)
            tier_queue = queue_manager.get_tier_queue_name(tier, 'extraction')

            logger.info(f"🎯 [DEBUG] Publishing to queue: {tier_queue} (tier: {tier})")

            success = queue_manager._publish_message(tier_queue, message)

            if success:
                logger.info(f"✅ [DEBUG] Successfully queued next extraction step: {next_step} to {tier_queue}")
            else:
                logger.error(f"❌ [DEBUG] Failed to queue next extraction step: {next_step} to {tier_queue}")

        except Exception as e:
            logger.error(f"💥 [DEBUG] Error queuing next extraction step: {e}")
            import traceback
            logger.error(f"💥 [DEBUG] Full traceback: {traceback.format_exc()}")

    def _retry_message(self, message: Dict[str, Any], retry_count: int):
        """
        Retry a failed message with exponential backoff.
        """
        try:
            import time
            import threading

            # Calculate delay: 2^retry_count seconds (1s, 2s, 4s)
            delay = 2 ** (retry_count - 1)

            logger.info(f"Retrying message in {delay} seconds (attempt {retry_count})")

            # Add retry count to message
            retry_message = message.copy()
            retry_message['retry_count'] = retry_count

            # Schedule retry after delay
            def delayed_retry():
                time.sleep(delay)
                queue_manager = QueueManager()

                # Get tenant tier and route to tier-based extraction queue
                tenant_id = message.get('tenant_id')
                tier = queue_manager._get_tenant_tier(tenant_id)
                tier_queue = queue_manager.get_tier_queue_name(tier, 'extraction')

                success = queue_manager._publish_message(tier_queue, retry_message)
                if success:
                    logger.info(f"Message requeued for retry (attempt {retry_count})")
                else:
                    logger.error(f"Failed to requeue message for retry")

            # Run retry in background thread
            retry_thread = threading.Thread(target=delayed_retry)
            retry_thread.daemon = True
            retry_thread.start()

        except Exception as e:
            logger.error(f"Error scheduling retry: {e}")

    def _send_to_dead_letter_queue(self, message: Dict[str, Any], error_message: str):
        """
        Send failed message to dead letter queue for manual investigation.
        """
        try:
            from sqlalchemy import text

            # Store failed message in database for investigation
            with self.get_db_session() as db:
                insert_query = text("""
                    INSERT INTO extraction_failures (
                        tenant_id, integration_id, extraction_type,
                        original_message, error_message, failed_at, created_at
                    ) VALUES (
                        :tenant_id, :integration_id, :extraction_type,
                        :original_message, :error_message, NOW(), NOW()
                    )
                """)

                db.execute(insert_query, {
                    'tenant_id': message.get('tenant_id'),
                    'integration_id': message.get('integration_id'),
                    'extraction_type': message.get('type'),
                    'original_message': json.dumps(message),
                    'error_message': error_message[:1000]  # Limit error message length
                })
                db.commit()

            logger.error(f"Message sent to dead letter queue: {message.get('type')} - {error_message}")

            # Update job status to failed if job_id is present
            job_id = message.get('job_id')
            if job_id:
                self._update_job_status(job_id, "FAILED", f"Extraction failed after retries: {error_message}")

        except Exception as e:
            logger.error(f"Error sending message to dead letter queue: {e}")

