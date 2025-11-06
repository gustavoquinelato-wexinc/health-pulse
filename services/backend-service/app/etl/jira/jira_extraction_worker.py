"""
Jira Extraction Worker - Processes Jira-specific extraction requests.

Handles Jira extraction message types:
- jira_dev_status: Fetch dev_status for Jira issues
- jira_projects_and_issue_types: Extract projects and issue types
- jira_statuses_and_relationships: Extract statuses and relationships
- jira_issues_with_changelogs: Extract issues with changelogs
- jira_custom_fields: Extract custom fields

This worker is called from the extraction_worker_router based on message type.
"""

import json
import asyncio
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from app.core.logging_config import get_logger
from app.core.database import get_database
from app.models.unified_models import Integration
from app.etl.workers.queue_manager import QueueManager
from app.etl.jira.jira_client import JiraAPIClient
from sqlalchemy import text

logger = get_logger(__name__)


class JiraExtractionWorker:
    """
    Worker for processing Jira-specific extraction requests.

    Note: This is NOT a queue consumer itself. It's called from ExtractionWorkerRouter
    which is the actual queue consumer. This class contains provider-specific logic.

    Uses dependency injection to receive WorkerStatusManager for sending status updates.
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

    async def process_jira_extraction(self, message_type: str, message: Dict[str, Any]) -> bool:
        """
        Route Jira extraction message to appropriate processor.

        Args:
            message_type: Type of Jira extraction message
            message: Message containing extraction request details

        Returns:
            bool: True if processing succeeded
        """
        try:
            if message_type == 'jira_dev_status':
                logger.info(f"🚀 [JIRA] Processing jira_dev_status extraction")
                return self._fetch_jira_dev_status(message)
            elif message_type == 'jira_projects_and_issue_types':
                logger.info(f"🚀 [JIRA] Processing jira_projects_and_issue_types extraction")
                return await self._extract_jira_projects_and_issue_types(message)
            elif message_type == 'jira_statuses_and_relationships':
                logger.info(f"🚀 [JIRA] Processing jira_statuses_and_relationships extraction")
                return self._extract_jira_statuses_and_relationships(message)
            elif message_type == 'jira_issues_with_changelogs':
                logger.info(f"🚀 [JIRA] Processing jira_issues_with_changelogs extraction")
                return self._extract_jira_issues_with_changelogs(message)
            elif message_type == 'jira_custom_fields':
                logger.info(f"🚀 [JIRA] Processing jira_custom_fields extraction")
                return self._extract_jira_custom_fields(message)
            else:
                logger.warning(f"Unknown Jira extraction type: {message_type}")
                return False
        except Exception as e:
            logger.error(f"Error processing Jira extraction message: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    def _fetch_jira_dev_status(self, message: Dict[str, Any]) -> bool:
        """
        Fetch dev_status for a Jira issue.

        Args:
            message: {
                'type': 'jira_dev_status',
                'issue_id': '12345',
                'issue_key': 'PROJ-123',
                'tenant_id': 1,
                'integration_id': 1,
                'first_item': bool,
                'last_item': bool,
                'last_job_item': bool
            }

        Returns:
            bool: True if fetch succeeded
        """
        try:
            issue_id = message.get('issue_id')
            issue_key = message.get('issue_key')
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            first_item = message.get('first_item', False)
            last_item = message.get('last_item', False)
            last_job_item = message.get('last_job_item', False)

            logger.info(f"🔍 [DEBUG] Extracted flags from message: first_item={first_item}, last_item={last_item}, last_job_item={last_job_item}")

            if not all([issue_id, issue_key]):
                logger.error(f"Missing issue_id or issue_key in message: {message}")
                return False

            logger.debug(f"Fetching dev_status for issue {issue_key} (ID: {issue_id})")

            # Get integration details and create Jira client
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
            jira_client = JiraAPIClient.create_from_integration(integration)

            # Fetch dev_status from Jira API
            dev_status_data = jira_client.get_dev_status(issue_id)

            if not dev_status_data:
                logger.info(f"🔍 [DEBUG] No dev_status data found for issue {issue_key} - EARLY RETURN")

                # 🎯 COMPLETION CHAIN: If this is the last item, publish completion message to transform queue
                if last_item:
                    queue_manager = QueueManager()
                    provider_name = message.get('provider', 'Jira')

                    logger.info(f"🎯 [COMPLETION] Publishing completion message to transform queue (no dev_status data)")
                    success = queue_manager.publish_transform_job(
                        tenant_id=tenant_id,
                        integration_id=integration_id,
                        data_type='jira_dev_status',
                        raw_data_id=None,  # 🔑 Key: None signals completion message
                        job_id=job_id,
                        provider=provider_name,
                        last_sync_date=message.get('last_sync_date'),
                        first_item=first_item,
                        last_item=last_item,
                        last_job_item=last_job_item,
                        token=message.get('token')
                    )
                    logger.info(f"🎯 [COMPLETION] Transform completion message published: {success}")

                    # 🔑 Send "finished" status for extraction worker
                    logger.info(f"🏁 [JIRA] Sending extraction worker finished status for jira_dev_status (no dev_status data)")
                    try:
                        await self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_dev_status")
                        logger.info(f"✅ [JIRA] Extraction worker finished status sent for jira_dev_status")
                    except Exception as ws_error:
                        logger.error(f"❌ [JIRA] Error sending extraction finished status: {ws_error}")

                return True  # Not an error, just no data

            # Check if dev_status has actual PR data (not just empty arrays)
            detail = dev_status_data.get('detail', [])
            has_pr_data = False
            for item in detail:
                if item.get('pullRequests') or item.get('branches') or item.get('repositories'):
                    has_pr_data = True
                    break

            if not has_pr_data:
                logger.info(f"🔍 [DEBUG] Dev_status for issue {issue_key} has no PR data (empty arrays) - EARLY RETURN")

                # 🎯 COMPLETION CHAIN: If this is the last item, publish completion message to transform queue
                if last_item:
                    queue_manager = QueueManager()
                    provider_name = message.get('provider', 'Jira')

                    logger.info(f"🎯 [COMPLETION] Publishing completion message to transform queue (no PR data)")
                    success = queue_manager.publish_transform_job(
                        tenant_id=tenant_id,
                        integration_id=integration_id,
                        data_type='jira_dev_status',
                        raw_data_id=None,
                        job_id=job_id,
                        provider=provider_name,
                        last_sync_date=message.get('last_sync_date'),
                        first_item=first_item,
                        last_item=last_item,
                        last_job_item=last_job_item,
                        token=message.get('token')
                    )
                    logger.info(f"🎯 [COMPLETION] Transform completion message published: {success}")

                    # 🔑 Send "finished" status for extraction worker
                    logger.info(f"🏁 [JIRA] Sending extraction worker finished status for jira_dev_status (no PR data)")
                    try:
                        await self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_dev_status")
                        logger.info(f"✅ [JIRA] Extraction worker finished status sent for jira_dev_status")
                    except Exception as ws_error:
                        logger.error(f"❌ [JIRA] Error sending extraction finished status: {ws_error}")

                return True  # Not an error, just no useful data

            logger.info(f"🔍 [DEBUG] Fetched dev_status for issue {issue_key}: {len(detail)} items with PR data")

            # Store raw data in raw_extraction_data table
            database = get_database()
            with database.get_write_session_context() as db:
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
            provider_name = message.get('provider', 'Jira')

            logger.info(f"🎯 [DEV_STATUS] Processing dev_status for {issue_key} (first={first_item}, last={last_item}, job_end={last_job_item})")

            success = queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                data_type='jira_dev_status',
                raw_data_id=raw_data_id,
                job_id=job_id,
                provider=provider_name,
                last_sync_date=message.get('last_sync_date'),
                first_item=first_item,
                last_item=last_item,
                last_job_item=last_job_item,
                token=message.get('token')
            )

            logger.info(f"🔍 [DEBUG] Published transform job: success={success}, raw_data_id={raw_data_id}")

            if success:
                logger.info(f"✅ Fetched and queued dev_status for issue {issue_key}")

                # 🔑 Send "finished" status for extraction worker when last_item=True
                if last_item:
                    logger.info(f"🏁 [JIRA] Sending extraction worker finished status for jira_dev_status (last_item=True)")
                    try:
                        await self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_dev_status")
                        logger.info(f"✅ [JIRA] Extraction worker finished status sent for jira_dev_status")
                    except Exception as ws_error:
                        logger.error(f"❌ [JIRA] Error sending extraction finished status: {ws_error}")

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
            token = message.get('token')

            logger.info(f"🏁 [DEBUG] Starting Jira projects and issue types extraction for tenant {tenant_id}, integration {integration_id}, job {job_id}")

            # Get integration and create Jira client
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                return False

            # Extract projects and issue types using existing logic
            from app.etl.jira.extraction import _extract_projects_and_issue_types

            # Execute extraction (this is async, so we use await)
            result = await _extract_projects_and_issue_types(
                jira_client, integration_id, tenant_id, job_id=job_id, token=token
            )

            if result.get('success'):
                logger.info(f"✅ [DEBUG] Projects and issue types extraction completed for tenant {tenant_id}")

                # Note: _extract_projects_and_issue_types already queues to transform internally
                # No need to queue again here - avoid duplicate queuing

                # 🔑 Send "finished" status for extraction worker
                logger.info(f"🏁 [JIRA] Sending extraction worker finished status for jira_projects_and_issue_types")
                try:
                    await self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_projects_and_issue_types")
                    logger.info(f"✅ [JIRA] Extraction worker finished status sent for jira_projects_and_issue_types")
                except Exception as ws_error:
                    logger.error(f"❌ [JIRA] Error sending extraction finished status: {ws_error}")

                # Queue next step: statuses and relationships
                logger.info(f"🔄 [DEBUG] Step 1 completed, queuing next step: jira_statuses_and_relationships")
                self._queue_next_extraction_step(tenant_id, integration_id, job_id, 'jira_statuses_and_relationships')
                return True
            else:
                logger.error(f"❌ [DEBUG] Projects and issue types extraction failed: {result.get('error')}")
                self._update_job_overall_status(job_id, "FAILED", f"Extraction failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Error in projects and issue types extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_overall_status(job_id, "FAILED", f"Extraction error: {str(e)}")
            return False

    def _extract_jira_statuses_and_relationships(self, message: Dict[str, Any]) -> bool:
        """
        Extract Jira statuses and relationships.
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            token = message.get('token')

            logger.info(f"🏁 [DEBUG] Starting Jira statuses and relationships extraction for tenant {tenant_id}, integration {integration_id}, job {job_id}")

            # Get integration and create Jira client
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                return False

            # Extract statuses and relationships using existing logic
            from app.etl.jira.extraction import _extract_statuses_and_relationships

            # Execute extraction
            logger.info(f"🔍 [DEBUG] About to call _extract_statuses_and_relationships via asyncio.run")
            try:
                result = asyncio.run(_extract_statuses_and_relationships(
                    jira_client, integration_id, tenant_id, job_id, token=token
                ))
                logger.info(f"🔍 [DEBUG] _extract_statuses_and_relationships completed, result: {result}")
            except Exception as async_error:
                logger.error(f"❌ [DEBUG] Exception in asyncio.run: {async_error}")
                import traceback
                logger.error(f"Asyncio traceback: {traceback.format_exc()}")
                raise

            logger.debug(f"🔄 [DEBUG] Statuses extraction result: {result}")
            logger.info(f"🔍 [DEBUG] Checking result.get('success'): {result.get('success')} (type: {type(result.get('success'))})")

            if result.get('success'):
                logger.info(f"✅ [DEBUG] Statuses and relationships extraction completed for tenant {tenant_id}")

                # 🔑 Send "finished" status for extraction worker
                logger.info(f"🏁 [JIRA] Sending extraction worker finished status for jira_statuses_and_relationships")
                try:
                    await self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_statuses_and_relationships")
                    logger.info(f"✅ [JIRA] Extraction worker finished status sent for jira_statuses_and_relationships")
                except Exception as ws_error:
                    logger.error(f"❌ [JIRA] Error sending extraction finished status: {ws_error}")

                # Queue next step: issues with changelogs
                logger.info(f"🔄 [DEBUG] Step 2 completed, queuing next step: jira_issues_with_changelogs")
                self._queue_next_extraction_step(tenant_id, integration_id, job_id, 'jira_issues_with_changelogs')
                return True
            else:
                logger.error(f"❌ [DEBUG] Statuses and relationships extraction failed: {result.get('error')}")
                self._update_job_overall_status(job_id, "FAILED", f"Extraction failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Error in statuses and relationships extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_overall_status(job_id, "FAILED", f"Extraction error: {str(e)}")
            return False

    def _extract_jira_issues_with_changelogs(self, message: Dict[str, Any]) -> bool:
        """
        Extract Jira issues with changelogs and orchestrate the complete flow.

        New Architecture:
        1. Extract all issues in bulk from Jira
        2. Break down into individual issues
        3. Queue individual issues to transform (with proper first_item/last_item flags)
        4. Queue dev_status extractions for issues with development field (with proper flags)
        5. Set last_job_item=true on the final dev_status item for job completion
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            incremental = message.get('incremental', True)
            token = message.get('token')

            logger.info(f"🏁 [DEBUG] Starting Jira issues with changelogs extraction for tenant {tenant_id}, integration {integration_id}, job {job_id}")

            # Get integration and create Jira client
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                return False

            # Use existing extraction logic from jira_extraction.py
            from app.etl.jira.extraction import _extract_issues_with_changelogs

            # Execute extraction using existing logic
            result = asyncio.run(_extract_issues_with_changelogs(
                jira_client, integration_id, tenant_id, incremental, job_id, token=token
            ))

            if result.get('success'):
                logger.info(f"✅ [DEBUG] Issues extraction completed for tenant {tenant_id}")
                logger.info(f"📊 [DEBUG] Processed {result.get('issues_count', 0)} issues, {len(result.get('issues_with_code_changes', []))} with code changes")

                # 🔑 Send "finished" status for extraction worker
                logger.info(f"🏁 [JIRA] Sending extraction worker finished status for jira_issues_with_changelogs")
                try:
                    await self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_issues_with_changelogs")
                    logger.info(f"✅ [JIRA] Extraction worker finished status sent for jira_issues_with_changelogs")
                except Exception as ws_error:
                    logger.error(f"❌ [JIRA] Error sending extraction finished status: {ws_error}")

                return True
            else:
                logger.error(f"❌ [DEBUG] Issues extraction failed: {result.get('error')}")
                self._update_job_overall_status(job_id, "FAILED", f"Extraction failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Error in issues with changelogs extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_overall_status(job_id, "FAILED", f"Extraction error: {str(e)}")
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

            # Custom fields extraction is not part of regular ETL job flow
            # It's triggered separately from the custom fields UI
            logger.info("Custom fields extraction is handled separately from regular ETL jobs")
            result = {'success': True, 'message': 'Custom fields extraction skipped - handled separately'}

            if result.get('success'):
                logger.info(f"✅ Custom fields extraction completed for tenant {tenant_id}")
                return True
            else:
                logger.error(f"Custom fields extraction failed: {result.get('error')}")
                self._update_job_overall_status(job_id, "FAILED", f"Extraction failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Error in custom fields extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if 'job_id' in locals():
                self._update_job_overall_status(job_id, "FAILED", f"Extraction error: {str(e)}")
            return False

    def _get_jira_client(self, tenant_id: int, integration_id: int) -> Tuple[Optional[Integration], Optional[JiraAPIClient]]:
        """
        Get integration and create Jira client.
        Uses read replica for configuration queries to optimize performance.

        Returns:
            tuple: (integration, jira_client) or (None, None) if failed
        """
        try:
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

    def _update_job_overall_status(self, job_id: int, overall_status: str, message: str = None):
        """Update ETL job overall status (for failures or completion)."""
        try:
            database = get_database()
            with database.get_write_session_context() as session:
                # Use string formatting for overall_status to avoid parameter binding issues
                update_query = text(f"""
                    UPDATE etl_jobs
                    SET status = jsonb_set(status, ARRAY['overall'], '"{overall_status}"'::jsonb),
                        last_updated_at = NOW()
                    WHERE id = :job_id
                """)

                session.execute(update_query, {
                    'job_id': job_id
                })
                session.commit()

                logger.info(f"Updated job {job_id} overall status to {overall_status}")
                if message:
                    logger.info(f"Job {job_id} message: {message}")

        except Exception as e:
            logger.error(f"Error updating job overall status: {e}")

    def _queue_next_extraction_step(self, tenant_id: int, integration_id: int, job_id: int, next_step: str):
        """
        Queue the next extraction step.
        """
        try:
            logger.info(f"🔄 [DEBUG] Queuing next extraction step: {next_step} for tenant {tenant_id}, integration {integration_id}, job {job_id}")

            queue_manager = QueueManager()

            # 🔧 FIX: Different steps have different message patterns
            if next_step == 'jira_statuses_and_relationships':
                # This step processes multiple projects and sends multiple transform messages
                # It should NOT be treated as a single bulk operation
                message = {
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'job_id': job_id,
                    'type': next_step,  # ETL step name
                    'provider': 'jira',
                    'first_item': True,   # This is the first (and only) extraction message for this step
                    'last_item': True,    # This is the last (and only) extraction message for this step
                    'last_sync_date': None,  # Will be set by extraction worker
                    'last_job_item': False,  # Not the final job step (issues_with_changelogs comes next)
                }
            else:
                # Other steps use standard bulk processing pattern
                message = {
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'job_id': job_id,
                    'type': next_step,  # ETL step name
                    'provider': 'jira',  # Default provider
                    'first_item': True,  # Bulk steps are always first and last
                    'last_item': True,
                    'last_sync_date': None,  # Will be set by extraction worker
                    'last_job_item': False,  # Will be determined later
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

