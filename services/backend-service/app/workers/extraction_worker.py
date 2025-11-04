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
from datetime import datetime

from app.workers.base_worker import BaseWorker
from app.core.logging_config import get_logger
from app.core.database import get_database
from app.etl.queue.queue_manager import QueueManager
from sqlalchemy import text

logger = get_logger(__name__)


class ExtractionWorker(BaseWorker):
    """
    Worker that handles additional extraction requests (tier-based queue architecture).

    Supports different extraction types:
    - jira_dev_status: Fetch dev_status for a Jira issue
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
            first_item = message.get('first_item', False)
            last_item = message.get('last_item', False)

            if not all([extraction_type, tenant_id, integration_id]):
                logger.error(f"❌ [DEBUG] Missing required fields in extraction message: {message}")
                return False

            logger.info(f"🚀 [DEBUG] Processing {extraction_type} extraction request for tenant {tenant_id}, integration {integration_id}, job {job_id}")

            # Send WebSocket status update when first_item=true (worker starting)
            if job_id and first_item:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("extraction", tenant_id, job_id, "running", extraction_type))
                finally:
                    loop.close()

            # Route to appropriate extraction handler
            result = False
            if extraction_type == 'jira_dev_status':
                logger.info(f"📋 [DEBUG] Routing to _fetch_jira_dev_status")
                result = self._fetch_jira_dev_status(message)
            elif extraction_type == 'jira_projects_and_issue_types':
                logger.info(f"📋 [DEBUG] Routing to _extract_jira_projects_and_issue_types")
                # Use asyncio.create_task to run async method from sync context
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(self._extract_jira_projects_and_issue_types(message))
                finally:
                    loop.close()
            elif extraction_type == 'github_repositories':
                logger.info(f"📋 [DEBUG] Routing to _extract_github_repositories")
                # Use asyncio.create_task to run async method from sync context
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(self._extract_github_repositories(message))
                finally:
                    loop.close()
            elif extraction_type == 'github_prs_commits_reviews_comments':
                logger.info(f"📋 [DEBUG] Routing to github_extraction_worker (Phase 4)")
                # Use asyncio.create_task to run async method from sync context
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    from app.etl.github_extraction import github_extraction_worker
                    extraction_result = loop.run_until_complete(github_extraction_worker(message))
                    result = extraction_result.get('success', False)

                    # Check for rate limit error (NEW)
                    if extraction_result.get('is_rate_limit'):
                        logger.warning(f"⏸️ Rate limit reached during GitHub extraction")
                        if job_id:
                            self._update_job_status_rate_limit_reached(
                                job_id,
                                tenant_id,
                                extraction_result.get('rate_limit_reset_at')
                            )
                        return True  # Don't retry, don't send to DLQ
                finally:
                    loop.close()
            elif extraction_type == 'jira_statuses_and_relationships':
                logger.info(f"📋 [DEBUG] Routing to _extract_jira_statuses_and_relationships")
                result = self._extract_jira_statuses_and_relationships(message)
            elif extraction_type == 'jira_issues_with_changelogs':
                logger.info(f"📋 [DEBUG] Routing to _extract_jira_issues_with_changelogs")
                result = self._extract_jira_issues_with_changelogs(message)
            elif extraction_type == 'jira_custom_fields':
                logger.info(f"📋 [DEBUG] Routing to _extract_jira_custom_fields")
                result = self._extract_jira_custom_fields(message)
            else:
                logger.warning(f"❓ [DEBUG] Unknown extraction type: {extraction_type}")
                result = False

            # Send WebSocket status update when last_item=true (worker finished)
            if job_id and last_item and result:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("extraction", tenant_id, job_id, "finished", extraction_type))
                finally:
                    loop.close()

            return result

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
                    SET status = jsonb_set(status, ARRAY['overall'], '"FAILED"'::jsonb),
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

    def _update_job_status_rate_limit_reached(self, job_id: int, tenant_id: int, rate_limit_reset_at: Optional[str] = None):
        """
        Update ETL job status to RATE_LIMIT_REACHED with next_run set to rate limit reset time.

        Args:
            job_id: ETL job ID
            tenant_id: Tenant ID
            rate_limit_reset_at: ISO format timestamp when rate limit resets (from checkpoint)
        """
        try:
            from app.core.database import get_database
            from app.core.utils import DateTimeHelper
            from sqlalchemy import text
            from datetime import timedelta

            database = get_database()

            # Calculate next_run based on rate_limit_reset_at
            if rate_limit_reset_at:
                try:
                    next_run = datetime.fromisoformat(rate_limit_reset_at)
                except (ValueError, TypeError):
                    # Fallback to 1 minute if parsing fails
                    next_run = DateTimeHelper.now_default() + timedelta(minutes=1)
            else:
                # Default to 1 minute retry
                next_run = DateTimeHelper.now_default() + timedelta(minutes=1)

            with database.get_write_session_context() as session:
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = jsonb_set(status, ARRAY['overall'], '"RATE_LIMIT_REACHED"'::jsonb),
                        error_message = 'GitHub API rate limit reached - will resume automatically',
                        next_run = :next_run,
                        last_updated_at = NOW()
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                session.execute(update_query, {
                    'job_id': job_id,
                    'tenant_id': tenant_id,
                    'next_run': next_run
                })
                session.commit()

                logger.info(f"⏸️ Updated job {job_id} status to RATE_LIMIT_REACHED, next_run: {next_run}")

        except Exception as e:
            logger.error(f"❌ Failed to update job status to RATE_LIMIT_REACHED: {e}")

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
                'last_job_item': bool  # NEW: Indicates this is the final item for job completion
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

            # 🎯 CRITICAL: Send WebSocket status IMMEDIATELY (before any extraction work)
            # This ensures extraction worker shows "running" before transform worker starts
            if job_id and first_item:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("extraction", tenant_id, job_id, "running", "jira_dev_status"))
                    logger.info(f"✅ [DEV_STATUS] Extraction worker set to RUNNING for job {job_id}")
                finally:
                    loop.close()
            
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
                logger.info(f"🔍 [DEBUG] No dev_status data found for issue {issue_key} - EARLY RETURN (flags: first={first_item}, last={last_item}, job_end={last_job_item})")

                # 🎯 COMPLETION CHAIN: If this is the last item, publish completion message to transform queue
                if last_item:
                    from app.etl.queue.queue_manager import QueueManager
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
                        last_sync_date=message.get('last_sync_date'),  # ✅ Preserved
                        first_item=first_item,    # ✅ Preserved
                        last_item=last_item,      # ✅ Preserved (True)
                        last_job_item=last_job_item,  # ✅ Preserved (True)
                        token=message.get('token')  # 🔑 Include token in message
                    )
                    logger.info(f"🎯 [COMPLETION] Transform completion message published: {success}")

                # Send WebSocket status: extraction worker finished (on last_item) even if no data
                if job_id and last_item:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_dev_status"))
                    finally:
                        loop.close()
                return True  # Not an error, just no data

            # Check if dev_status has actual PR data (not just empty arrays)
            detail = dev_status_data.get('detail', [])
            has_pr_data = False
            for item in detail:
                if item.get('pullRequests') or item.get('branches') or item.get('repositories'):
                    has_pr_data = True
                    break

            if not has_pr_data:
                logger.info(f"🔍 [DEBUG] Dev_status for issue {issue_key} has no PR data (empty arrays) - EARLY RETURN (flags: first={first_item}, last={last_item}, job_end={last_job_item})")

                # 🎯 COMPLETION CHAIN: If this is the last item, publish completion message to transform queue
                if last_item:
                    from app.etl.queue.queue_manager import QueueManager
                    queue_manager = QueueManager()
                    provider_name = message.get('provider', 'Jira')

                    logger.info(f"🎯 [COMPLETION] Publishing completion message to transform queue (no PR data)")
                    success = queue_manager.publish_transform_job(
                        tenant_id=tenant_id,
                        integration_id=integration_id,
                        data_type='jira_dev_status',
                        raw_data_id=None,  # 🔑 Key: None signals completion message
                        job_id=job_id,
                        provider=provider_name,
                        last_sync_date=message.get('last_sync_date'),  # ✅ Preserved
                        first_item=first_item,    # ✅ Preserved
                        last_item=last_item,      # ✅ Preserved (True)
                        last_job_item=last_job_item,  # ✅ Preserved (True)
                        token=message.get('token')  # 🔑 Include token in message
                    )
                    logger.info(f"🎯 [COMPLETION] Transform completion message published: {success}")

                # Send WebSocket status: extraction worker finished (on last_item) even if no useful data
                if job_id and last_item:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_dev_status"))
                    finally:
                        loop.close()
                return True  # Not an error, just no useful data

            logger.info(f"🔍 [DEBUG] Fetched dev_status for issue {issue_key}: {len(detail)} items with PR data - PROCEEDING TO STORE AND PUBLISH")

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
            from app.etl.queue.queue_manager import QueueManager
            queue_manager = QueueManager()

            # 🔄 NEW ARCHITECTURE: Get provider name for message
            provider_name = message.get('provider', 'Jira')  # Fixed: use provider instead of provider_name

            logger.info(f"🎯 [DEV_STATUS] Processing dev_status for {issue_key} (first={first_item}, last={last_item}, job_end={last_job_item})")
            logger.info(f"🔍 [DEBUG] About to publish transform job with flags: first_item={first_item}, last_item={last_item}, last_job_item={last_job_item}")

            success = queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                data_type='jira_dev_status',
                raw_data_id=raw_data_id,
                job_id=job_id,  # Fixed: use job_id parameter name
                provider=provider_name,  # Fixed: use provider parameter name
                last_sync_date=message.get('last_sync_date'),  # 🔧 Forward last_sync_date from incoming message
                first_item=first_item,
                last_item=last_item,
                last_job_item=last_job_item,  # 🎯 Forward the last_job_item flag
                token=message.get('token')  # 🔑 Include token in message
            )

            logger.info(f"🔍 [DEBUG] Published transform job: success={success}, raw_data_id={raw_data_id}, flags=(first={first_item}, last={last_item}, job_end={last_job_item})")

            if success:
                logger.info(f"✅ Fetched and queued dev_status for issue {issue_key}")

                # Send WebSocket status: extraction worker finished (on last_item)
                if job_id and last_item:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self._send_worker_status("extraction", tenant_id, job_id, "finished", "jira_dev_status"))
                    finally:
                        loop.close()

                return True
            else:
                logger.error(f"Failed to queue dev_status for transformation (raw_data_id={raw_data_id})")

                # Send WebSocket status: extraction worker failed (on last_item)
                if job_id and last_item:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self._send_worker_status("extraction", tenant_id, job_id, "failed", "jira_dev_status",
                                                                       error_message="Failed to queue dev_status for transformation"))
                    finally:
                        loop.close()

                return False
                
        except Exception as e:
            logger.error(f"Error fetching dev_status for issue {message.get('issue_key', 'unknown')}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

            # ✅ Send extraction worker "failed" status when last_item=True even on exception
            if job_id and last_item:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("extraction", tenant_id, job_id, "failed", "jira_dev_status", error_message=str(e)))
                    logger.info(f"✅ Extraction worker marked as failed for jira_dev_status (exception)")
                finally:
                    loop.close()

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
            step_name = message.get('type', 'jira_projects_and_issue_types')
            self._update_job_status(job_id, step_name, "running", "Extracting projects and issue types")

            # Send WebSocket status: extraction worker starting
            step_name = message.get('type', 'jira_projects_and_issue_types')  # Get step name from message
            await self._send_worker_status("extraction", tenant_id, job_id, "running", step_name)



            # Extract projects and issue types using existing logic
            from app.etl.jira_extraction import _extract_projects_and_issue_types

            # 🔑 Extract token from message
            token = message.get('token')

            # Execute extraction (this is async, so we use await)
            result = await _extract_projects_and_issue_types(
                jira_client, integration_id, tenant_id, job_id=job_id, token=token
            )

            if result.get('success'):
                logger.info(f"✅ [DEBUG] Projects and issue types extraction completed for tenant {tenant_id}")

                # Send WebSocket status: extraction worker finished
                await self._send_worker_status("extraction", tenant_id, job_id, "finished", step_name)

                # Note: _extract_projects_and_issue_types already queues to transform internally
                # No need to queue again here - avoid duplicate queuing

                # Queue next step: statuses and relationships
                logger.info(f"🔄 [DEBUG] Step 1 completed, queuing next step: jira_statuses_and_relationships")
                self._queue_next_extraction_step(tenant_id, integration_id, job_id, 'jira_statuses_and_relationships')
                return True
            else:
                logger.error(f"❌ [DEBUG] Projects and issue types extraction failed: {result.get('error')}")
                # Send WebSocket status: extraction worker failed
                await self._send_worker_status("extraction", tenant_id, job_id, "failed", "jira_projects_and_issue_types",
                                             error_message=result.get('error'))
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
            token = message.get('token')  # 🔑 Extract token from message

            logger.info(f"🏁 [DEBUG] Starting Jira statuses and relationships extraction for tenant {tenant_id}, integration {integration_id}, job {job_id}")

            # Get integration and create Jira client
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                return False

            # Send WebSocket status: extraction worker starting
            step_name = message.get('type', 'jira_statuses_and_relationships')
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._send_worker_status("extraction", tenant_id, job_id, "running", step_name))
            finally:
                loop.close()



            # Extract statuses and relationships using existing logic
            from app.etl.jira_extraction import _extract_statuses_and_relationships



            # Execute extraction
            logger.info(f"🔍 [DEBUG] About to call _extract_statuses_and_relationships via asyncio.run")
            import asyncio
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
            logger.info(f"🔍 [DEBUG] Full result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")

            if result.get('success'):
                logger.info(f"✅ [DEBUG] Statuses and relationships extraction completed for tenant {tenant_id}")

                # Send WebSocket status: extraction worker finished
                step_name = message.get('type', 'jira_statuses_and_relationships')
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("extraction", tenant_id, job_id, "finished", step_name))
                    # Note: _extract_statuses_and_relationships already queues to transform internally
                    # AND now also queues the next extraction step (jira_issues_with_changelogs) when processing the last project
                finally:
                    loop.close()

                # Queue next step: issues with changelogs
                logger.info(f"🔄 [DEBUG] Step 2 completed, queuing next step: jira_issues_with_changelogs")
                self._queue_next_extraction_step(tenant_id, integration_id, job_id, 'jira_issues_with_changelogs')
                return True
            else:
                logger.error(f"❌ [DEBUG] Statuses and relationships extraction failed: {result.get('error')}")
                # Send WebSocket status: extraction worker failed
                step_name = message.get('type', 'jira_statuses_and_relationships')
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("extraction", tenant_id, job_id, "failed", step_name,
                                                                   error_message=result.get('error')))
                finally:
                    loop.close()
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
            token = message.get('token')  # 🔑 Extract token from message

            logger.info(f"🏁 [DEBUG] Starting Jira issues with changelogs extraction for tenant {tenant_id}, integration {integration_id}, job {job_id}")

            # Get integration and create Jira client
            integration, jira_client = self._get_jira_client(tenant_id, integration_id)
            if not integration or not jira_client:
                return False

            # Send WebSocket status: extraction worker starting
            step_name = message.get('type', 'jira_issues_with_changelogs')
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._send_worker_status("extraction", tenant_id, job_id, "running", step_name))
            finally:
                loop.close()

            # Use existing extraction logic from jira_extraction.py
            from app.etl.jira_extraction import _extract_issues_with_changelogs



            # Execute extraction using existing logic
            result = asyncio.run(_extract_issues_with_changelogs(
                jira_client, integration_id, tenant_id, incremental, job_id, token=token
            ))

            if result.get('success'):
                logger.info(f"✅ [DEBUG] Issues extraction completed for tenant {tenant_id}")
                logger.info(f"📊 [DEBUG] Processed {result.get('issues_count', 0)} issues, {len(result.get('issues_with_code_changes', []))} with code changes")

                # Send WebSocket status: extraction worker finished
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("extraction", tenant_id, job_id, "finished", step_name))
                finally:
                    loop.close()

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

                # Queue for transformation - just log, don't update status
                logger.info("Extraction completed, queuing for transformation")

                # TODO: Queue transform job here
                # queue_manager = QueueManager()
                # queue_manager.publish_transform_job(tenant_id, integration_id, job_id)
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

    def _update_job_status(self, job_id: int, step_name: str, step_status: str, message: str = None):
        """
        Update ETL job step status in database JSON structure.
        Uses write session (primary database) for status updates.
        """
        try:
            from app.core.database import get_database
            from sqlalchemy import text

            database = get_database()
            with database.get_write_session_context() as session:
                # Update specific step status within the JSON structure
                # Only update overall status to RUNNING if not already running
                # Use string formatting for step_name and step_status to avoid parameter binding issues
                update_query = text(f"""
                    UPDATE etl_jobs
                    SET status = jsonb_set(
                            jsonb_set(status, ARRAY['steps', '{step_name}', 'extraction'], '"{step_status}"'::jsonb),
                            ARRAY['overall'],
                            CASE
                                WHEN status->>'overall' = 'READY' THEN '"RUNNING"'::jsonb
                                ELSE status->'overall'
                            END
                        ),
                        last_updated_at = NOW()
                    WHERE id = :job_id
                """)

                params = {
                    'job_id': job_id
                }
                logger.info(f"Executing SQL with params: {params}")
                session.execute(update_query, params)
                session.commit()

                logger.info(f"Updated job {job_id} step {step_name} extraction status to {step_status}")
                if message:
                    logger.info(f"Job {job_id} message: {message}")

        except Exception as e:
            logger.error(f"Error updating job status: {e}")

    def _update_job_overall_status(self, job_id: int, overall_status: str, message: str = None):
        """Update ETL job overall status (for failures or completion)."""
        try:
            from app.core.database import get_database
            from sqlalchemy import text

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
        """Send WebSocket status update by sending the current database JSON status."""
        try:
            # Update database worker status first
            self._update_worker_status_in_db(worker_type, tenant_id, job_id, status, step, error_message)

            # Get the current job status from database and send via WebSocket
            from app.core.database import get_database
            from sqlalchemy import text
            import json

            database = get_database()
            with database.get_read_session_context() as session:
                result = session.execute(
                    text('SELECT status FROM etl_jobs WHERE id = :job_id'),
                    {'job_id': job_id}
                ).fetchone()

                if result:
                    job_status = result[0]  # This is the JSON status structure

                    # Send WebSocket notification with the same JSON structure the UI reads on refresh
                    from app.api.websocket_routes import get_job_websocket_manager

                    job_websocket_manager = get_job_websocket_manager()
                    await job_websocket_manager.send_job_status_update(
                        tenant_id=tenant_id,
                        job_id=job_id,
                        status_json=job_status
                    )
                    logger.info(f"[WS] Sent job status update for job {job_id} (tenant {tenant_id})")

        except Exception as e:
            logger.error(f"Error sending worker status: {e}")

    def _update_worker_status_in_db(self, worker_type: str, tenant_id: int, job_id: int, status: str, step: str, error_message: str = None):
        """Update worker status in JSON status structure"""
        try:
            # Safety check: if step is None, skip the database update
            if step is None:
                logger.warning(f"Skipping worker status update - step is None for {worker_type} worker (job {job_id}, tenant {tenant_id})")
                return

            from app.core.database import get_write_session
            from sqlalchemy import text
            import json

            with get_write_session() as session:
                # Update JSON status structure: status->steps->{step}->{worker_type} = status
                # Use string formatting to avoid parameter style conflicts
                # Escape single quotes in values to prevent SQL injection
                safe_step = step.replace("'", "''")
                safe_worker_type = worker_type.replace("'", "''")
                safe_status = status.replace("'", "''")

                update_query = text(f"""
                    UPDATE etl_jobs
                    SET status = jsonb_set(
                        status,
                        ARRAY['steps', '{safe_step}', '{safe_worker_type}'],
                        to_jsonb('{safe_status}'::text)
                    ),
                    last_updated_at = NOW()
                    WHERE id = {job_id} AND tenant_id = {tenant_id}
                """)

                session.execute(update_query)
                session.commit()

                logger.info(f"Updated {worker_type} worker status to {status} for step {step} in job {job_id}")

        except Exception as e:
            logger.error(f"Failed to update worker status in database: {e}")

    async def _queue_to_transform(self, tenant_id: int, integration_id: int, job_id: int,
                                 step_type: str, first_item: bool = False, last_item: bool = False,
                                 bulk_processing: bool = False, external_id: str = None, token: str = None):
        """Queue data to transform worker with enhanced message structure."""
        try:
            from app.etl.queue.queue_manager import QueueManager

            queue_manager = QueueManager()

            # Standardized base message structure
            message = {
                'tenant_id': tenant_id,
                'integration_id': integration_id,
                'job_id': job_id,
                'type': step_type,  # ETL step name
                'provider': 'jira',  # Default provider
                'first_item': first_item,
                'last_item': last_item,
                'last_sync_date': None,  # Will be set by transform worker
                'last_job_item': False,  # Will be determined by transform worker
                'token': token,  # 🔑 Job execution token
                # Extraction → Transform specific fields
                'raw_data_id': None,  # Will be set for individual messages
                'bulk_processing': bulk_processing,
                'external_id': external_id or f"bulk_{step_type}"
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
                    # Note: This step will internally process multiple projects and send multiple transform messages
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
                    # Extraction → Extraction specific fields
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

    async def _extract_github_repositories(self, message: Dict[str, Any]) -> bool:
        """
        Extract GitHub repositories for a tenant.

        Args:
            message: Message containing extraction request details

        Returns:
            bool: True if extraction succeeded
        """
        try:
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            first_item = message.get('first_item', False)
            last_item = message.get('last_item', False)
            last_job_item = message.get('last_job_item', False)

            logger.info(f"🚀 [GITHUB] Starting repositories extraction for tenant {tenant_id}, integration {integration_id}")

            # Update job status to RUNNING
            step_name = message.get('type', 'github_repositories')
            self._update_job_status(job_id, step_name, "running", "Extracting GitHub repositories")

            # Send WebSocket status: extraction worker starting
            await self._send_worker_status("extraction", tenant_id, job_id, "running", step_name)

            # 🔑 Check for rate limit recovery resume date
            resume_from_pushed_date = message.get('resume_from_pushed_date')

            if resume_from_pushed_date:
                # RECOVERY MODE: Use last repo's pushed date as start_date
                logger.info(f"🔄 [RECOVERY] Resuming repository extraction from pushed date: {resume_from_pushed_date}")
                last_sync_date = resume_from_pushed_date
            else:
                # NORMAL MODE: Fetch last_sync_date from database (etl_jobs table)
                # If null, use 2 years ago as default (captures all useful data)
                database = get_database()
                last_sync_date = None
                with database.get_read_session_context() as session:
                    from app.models.unified_models import EtlJob
                    job = session.query(EtlJob).filter(EtlJob.id == job_id).first()
                    if job and job.last_sync_date:
                        last_sync_date = job.last_sync_date.strftime('%Y-%m-%d')
                        logger.info(f"📅 Using last_sync_date from database: {last_sync_date}")
                    else:
                        # Default: 2 years ago (captures all useful data)
                        from datetime import datetime, timedelta
                        two_years_ago = datetime.now() - timedelta(days=730)
                        last_sync_date = two_years_ago.strftime('%Y-%m-%d')
                        logger.info(f"📅 No last_sync_date in database, using 2-year default: {last_sync_date}")

            # Extract repositories using existing logic
            from app.etl.github_extraction import extract_github_repositories

            # 🔑 Extract token from message
            token = message.get('token')

            # Execute extraction
            result = await extract_github_repositories(
                integration_id, tenant_id, job_id, last_sync_date=last_sync_date, token=token
            )

            # Check for rate limit error
            if result.get('is_rate_limit'):
                logger.warning(f"⏸️ Rate limit reached during repository extraction")
                if job_id:
                    self._update_job_status_rate_limit_reached(
                        job_id,
                        tenant_id,
                        result.get('rate_limit_reset_at')
                    )
                return True  # Don't retry, don't send to DLQ

            if result.get('success'):
                logger.info(f"✅ [GITHUB] Repositories extraction completed for tenant {tenant_id}")
                logger.info(f"📊 [GITHUB] Processed {result.get('repositories_count', 0)} repositories")

                # Send WebSocket status: extraction worker finished
                await self._send_worker_status("extraction", tenant_id, job_id, "finished", step_name)

                return True
            else:
                logger.error(f"❌ [GITHUB] Repositories extraction failed: {result.get('error')}")
                self._update_job_overall_status(job_id, "FAILED", f"Extraction failed: {result.get('error')}")

                # Send WebSocket status: extraction worker failed
                await self._send_worker_status("extraction", tenant_id, job_id, "failed", step_name,
                                             error_message=result.get('error'))
                return False

        except Exception as e:
            logger.error(f"💥 [GITHUB] Error extracting repositories: {e}")
            import traceback
            logger.error(f"💥 [GITHUB] Full traceback: {traceback.format_exc()}")
            self._update_job_status_failed(job_id, str(e), tenant_id)
            return False

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
                self._update_job_overall_status(job_id, "FAILED", f"Extraction failed after retries: {error_message}")

        except Exception as e:
            logger.error(f"Error sending message to dead letter queue: {e}")

