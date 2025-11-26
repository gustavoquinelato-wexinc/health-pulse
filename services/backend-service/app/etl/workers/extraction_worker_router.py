"""
Extraction Worker Router - Routes extraction messages to provider-specific workers.

This router consumes from tier-based extraction queues and routes messages to:
- JiraExtractionWorker for Jira extraction types
- GitHubExtractionWorker for GitHub extraction types

Architecture:
- Generic router logic (queue consumption, retry, DLQ)
- Provider-specific logic delegated to provider workers
- Maintains separation of concerns
"""

import json
from typing import Dict, Any, Optional
from app.core.logging_config import get_logger
from app.etl.workers.base_worker import BaseWorker
from app.etl.workers.queue_manager import QueueManager

logger = get_logger(__name__)


class ExtractionWorker(BaseWorker):
    """
    Router for extraction messages.

    Consumes from tier-based extraction queues and routes to provider-specific workers.
    """

    def __init__(self, queue_name: Optional[str] = None, worker_number: Optional[int] = None, tenant_ids: Optional[list] = None):
        """
        Initialize extraction worker router.

        Args:
            queue_name: Name of the queue to consume from (required by BaseWorker)
            worker_number: Worker number for logging (optional)
            tenant_ids: List of tenant IDs (optional, not used for tier-based queues)
        """
        # If queue_name not provided, use a default
        if queue_name is None:
            queue_name = "extraction_queue_default"

        super().__init__(queue_name)
        self.worker_number = worker_number
        self.tenant_ids = tenant_ids
        logger.debug(f"✅ Initialized ExtractionWorker router (queue: {queue_name}, worker: {worker_number})")

    async def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process extraction message by routing to appropriate provider worker.

        Args:
            message: Extraction message with structure:
                {
                    'type': 'jira_dev_status' | 'jira_projects_and_issue_types' | 'github_repositories' | etc,
                    'provider': 'jira' | 'github',
                    'tenant_id': int,
                    'integration_id': int,
                    'job_id': int,
                    'token': str,
                    'first_item': bool,
                    'last_item': bool,
                    'last_job_item': bool,
                    ... provider-specific fields
                }

        Returns:
            bool: True if message processed successfully
        """
        try:
            extraction_type = message.get('type')
            provider = message.get('provider')
            tenant_id = message.get('tenant_id')
            job_id = message.get('job_id')
            first_item = message.get('first_item', False)

            logger.info(f"📋 [EXTRACTION] Processing {extraction_type} (provider: {provider}) for tenant {tenant_id}, job {job_id}")

            # 🔔 Send WebSocket status update when first_item=true (extraction worker starting)
            if job_id and first_item:
                logger.info(f"🚀 [EXTRACTION] Sending WebSocket status update: extraction worker running for {extraction_type}")
                try:
                    await self._send_worker_status("extraction", tenant_id, job_id, "running", extraction_type)
                    logger.debug(f"✅ [EXTRACTION] WebSocket status update completed for {extraction_type}")
                except Exception as ws_error:
                    logger.error(f"❌ [EXTRACTION] Error sending WebSocket status: {ws_error}")

            # Route to appropriate extraction handler based on provider
            # Note: Provider-specific workers now handle their own "finished" status updates
            # Router only sends "running" status when first_item=true
            # 🔑 Pass status_manager to provider workers for dependency injection
            result = False
            try:
                if provider == 'jira':
                    logger.debug(f"📋 [DEBUG] Routing to JiraExtractionWorker for {extraction_type}")
                    from app.etl.jira.jira_extraction_worker import JiraExtractionWorker
                    jira_worker = JiraExtractionWorker(status_manager=self.status_manager)
                    logger.debug(f"📋 [DEBUG] Calling jira_worker.process_jira_extraction")
                    result = await jira_worker.process_jira_extraction(extraction_type, message)
                    logger.debug(f"📋 [DEBUG] jira_worker.process_jira_extraction returned: {result}")
                elif provider == 'github':
                    logger.debug(f"📋 [DEBUG] Routing to GitHubExtractionWorker for {extraction_type}")
                    from app.etl.github.github_extraction_worker import GitHubExtractionWorker
                    github_worker = GitHubExtractionWorker(status_manager=self.status_manager)
                    logger.debug(f"📋 [DEBUG] Calling github_worker.process_github_extraction")
                    result = await github_worker.process_github_extraction(extraction_type, message)
                    logger.debug(f"📋 [DEBUG] github_worker.process_github_extraction returned: {result}")
                else:
                    logger.warning(f"❓ [DEBUG] Unknown provider: {provider} for extraction type: {extraction_type}")
                    result = False
            except Exception as route_error:
                logger.error(f"💥 [EXTRACTION] Error during routing: {route_error}")
                import traceback
                logger.error(f"💥 [EXTRACTION] Routing error traceback: {traceback.format_exc()}")
                result = False

            # � NOTE: "finished" status is now sent by provider-specific workers
            # This allows each worker to handle its own completion logic
            # (e.g., github_repositories finishes after LOOP 1 + LOOP 2, even though incoming message has last_item=False)

            if result:
                logger.debug(f"✅ [EXTRACTION] Successfully processed {extraction_type}")
            else:
                logger.error(f"❌ [EXTRACTION] Failed to process {extraction_type}")

            return result

        except Exception as e:
            logger.error(f"💥 [EXTRACTION] Error processing message: {e}")
            import traceback
            logger.error(f"💥 [EXTRACTION] Full traceback: {traceback.format_exc()}")
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

            logger.debug(f"Retrying message in {delay} seconds (attempt {retry_count})")

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
                    logger.debug(f"Message requeued for retry (attempt {retry_count})")
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
            from app.core.utils import DateTimeHelper
            now = DateTimeHelper.now_default()

            with self.get_db_session() as db:
                insert_query = text("""
                    INSERT INTO extraction_failures (
                        tenant_id, integration_id, extraction_type,
                        original_message, error_message, failed_at, created_at
                    ) VALUES (
                        :tenant_id, :integration_id, :extraction_type,
                        :original_message, :error_message, :failed_at, :created_at
                    )
                """)

                db.execute(insert_query, {
                    'tenant_id': message.get('tenant_id'),
                    'integration_id': message.get('integration_id'),
                    'extraction_type': message.get('type'),
                    'original_message': json.dumps(message),
                    'error_message': error_message[:1000],  # Limit error message length
                    'failed_at': now,
                    'created_at': now
                })
                db.commit()

            logger.error(f"Message sent to dead letter queue: {message.get('type')} - {error_message}")

            # Update job status to failed if job_id is present
            job_id = message.get('job_id')
            if job_id:
                from app.core.database import get_database
                database = get_database()
                from app.core.utils import DateTimeHelper
                now = DateTimeHelper.now_default()

                with database.get_write_session_context() as session:
                    update_query = text(f"""
                        UPDATE etl_jobs
                        SET status = jsonb_set(status, ARRAY['overall'], '"FAILED"'::jsonb),
                            error_message = :error_message,
                            last_updated_at = :now
                        WHERE id = :job_id
                    """)
                    session.execute(update_query, {
                        'job_id': job_id,
                        'error_message': error_message[:500],
                        'now': now
                    })
                    session.commit()

        except Exception as e:
            logger.error(f"Error sending message to dead letter queue: {e}")

