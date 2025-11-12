"""
Transform Worker - Router and Queue Consumer for ETL data transformation.

Acts as the main queue consumer and router for transform messages:
- Consumes from tier-based transform queues
- Routes Jira messages to JiraTransformHandler
- Routes GitHub messages to GitHubTransformHandler
- Handles completion messages and WebSocket status updates

Tier-Based Queue Architecture:
- Workers consume from tier-based queues (transform_queue_free, transform_queue_premium, etc.)
- Each message contains tenant_id for proper routing
- Multiple workers per tier share the same queue
"""

import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy import text

from app.etl.workers.base_worker import BaseWorker
from app.etl.jira.jira_transform_worker import JiraTransformHandler
from app.etl.github.github_transform_worker import GitHubTransformHandler
from app.core.logging_config import get_logger
from app.core.database import get_database, get_write_session
from app.etl.workers.queue_manager import QueueManager

logger = get_logger(__name__)


def complete_etl_job(job_id: int, last_sync_date: str, tenant_id: int):
    """Complete ETL job by updating status, timestamps, last_sync_date, and next_run"""
    try:
        with get_write_session() as session:
            # First get the job details to calculate next_run
            job_query = text("""
                SELECT last_run_started_at, schedule_interval_minutes, retry_interval_minutes, retry_count
                FROM etl_jobs
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            job_result = session.execute(job_query, {
                'job_id': job_id,
                'tenant_id': tenant_id
            }).fetchone()

            if not job_result:
                logger.error(f"❌ Job {job_id} not found for completion")
                return

            last_run_started_at, schedule_interval_minutes, retry_interval_minutes, retry_count = job_result

            # Calculate next_run using the same logic as in jobs.py
            from app.etl.jobs import calculate_next_run
            from app.core.utils import DateTimeHelper

            now = DateTimeHelper.now_default()

            next_run = calculate_next_run(
                last_run_started_at=last_run_started_at,
                schedule_interval_minutes=schedule_interval_minutes,
                retry_interval_minutes=retry_interval_minutes,
                status='FINISHED',
                retry_count=retry_count
            )

            update_query = text("""
                UPDATE etl_jobs
                SET status = 'FINISHED',
                    last_run_finished_at = :now,
                    last_sync_date = :last_sync_date,
                    last_updated_at = :now,
                    next_run = :next_run
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)

            session.execute(update_query, {
                'job_id': job_id,
                'tenant_id': tenant_id,
                'last_sync_date': last_sync_date,
                'next_run': next_run,
                'now': now
            })
            session.commit()

            logger.debug(f"✅ ETL job {job_id} completed successfully with next_run: {next_run}")

    except Exception as e:
        logger.error(f"❌ Failed to complete ETL job {job_id}: {e}")
        raise


class TransformWorker(BaseWorker):
    """
    Transform Worker - Router and Queue Consumer for ETL data transformation.

    Routes messages to specialized handlers:
    - JiraTransformHandler: Processes all Jira message types
    - GitHubTransformHandler: Processes all GitHub message types

    Tier-Based Queue Mode:
    - Consumes from tier-based queue (e.g., transform_queue_premium)
    - Uses tenant_id from message for proper data routing
    - Routes to appropriate handler based on message type
    """

    def __init__(self, queue_name: str, worker_number: int = 0, tenant_ids: Optional[List[int]] = None):
        """
        Initialize transform worker for tier-based queue.

        Args:
            queue_name: Name of the tier-based transform queue (e.g., 'transform_queue_premium')
            worker_number: Worker instance number (for logging)
            tenant_ids: Deprecated (kept for backward compatibility)
        """
        super().__init__(queue_name)
        self.worker_number = worker_number
        # 🔑 Pass status_manager and queue_manager to handlers via dependency injection
        self.jira_handler = JiraTransformHandler(
            status_manager=self.status_manager,
            queue_manager=self.queue_manager
        )
        self.github_handler = GitHubTransformHandler(
            status_manager=self.status_manager,
            queue_manager=self.queue_manager
        )
        logger.debug(f"Initialized TransformWorker #{worker_number} for tier queue: {queue_name}")

    async def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a transform message by routing to appropriate provider worker.

        Args:
            message: Transform message with structure:
                {
                    'type': 'jira_projects_and_issue_types' | 'github_repositories' | etc,
                    'provider': 'jira' | 'github',
                    'tenant_id': int,
                    'integration_id': int,
                    'job_id': int,
                    'raw_data_id': int | None,
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
            message_type = message.get('type')
            provider = message.get('provider')
            tenant_id = message.get('tenant_id')
            job_id = message.get('job_id')
            first_item = message.get('first_item', False)

            logger.debug(f"📋 [TRANSFORM] Processing {message_type} (provider: {provider}) for tenant {tenant_id}, job {job_id}")

            # 🔔 Send WebSocket status update when first_item=true (transform worker starting)
            if job_id and first_item:
                logger.debug(f"🚀 [TRANSFORM] Sending WebSocket status update: transform worker running for {message_type}")
                try:
                    await self._send_worker_status("transform", tenant_id, job_id, "running", message_type)
                    logger.debug(f"✅ [TRANSFORM] WebSocket status update completed for {message_type}")
                except Exception as ws_error:
                    logger.error(f"❌ [TRANSFORM] Error sending WebSocket status: {ws_error}")

            # Route to appropriate transform handler based on provider
            # Note: Provider-specific workers now handle their own "finished" status updates
            # Router only sends "running" status when first_item=true
            result = False
            try:
                if provider == 'jira':
                    logger.debug(f"📋 [TRANSFORM] Routing to JiraTransformHandler for {message_type}")
                    result = await self.jira_handler.process_jira_message(
                        message_type, message
                    )
                    logger.debug(f"📋 [TRANSFORM] JiraTransformHandler returned: {result}")
                elif provider == 'github':
                    logger.debug(f"📋 [TRANSFORM] Routing to GitHubTransformHandler for {message_type}")
                    result = await self.github_handler.process_github_message(
                        message_type, message
                    )
                    logger.debug(f"📋 [TRANSFORM] GitHubTransformHandler returned: {result}")
                else:
                    logger.warning(f"❓ [TRANSFORM] Unknown provider: {provider} for message type: {message_type}")
                    result = False
            except Exception as route_error:
                logger.error(f"💥 [TRANSFORM] Error during routing: {route_error}")
                import traceback
                logger.error(f"💥 [TRANSFORM] Routing error traceback: {traceback.format_exc()}")
                result = False

            # Note: "finished" status is now sent by provider-specific workers
            # This allows each worker to handle its own completion logic

            if result:
                logger.debug(f"✅ [TRANSFORM] Successfully processed {message_type}")
            else:
                logger.error(f"❌ [TRANSFORM] Failed to process {message_type}")

            return result

        except Exception as e:
            logger.error(f"Error processing transform message: {e}")
            return False
