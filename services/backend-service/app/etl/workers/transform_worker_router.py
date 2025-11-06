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
                    last_run_finished_at = NOW(),
                    last_sync_date = :last_sync_date,
                    last_updated_at = NOW(),
                    next_run = :next_run
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)

            session.execute(update_query, {
                'job_id': job_id,
                'tenant_id': tenant_id,
                'last_sync_date': last_sync_date,
                'next_run': next_run
            })
            session.commit()

            logger.info(f"✅ ETL job {job_id} completed successfully with next_run: {next_run}")

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
        # 🔑 Pass status_manager to handlers via dependency injection
        self.jira_handler = JiraTransformHandler(status_manager=self.status_manager)
        self.github_handler = GitHubTransformHandler(status_manager=self.status_manager)
        logger.info(f"Initialized TransformWorker #{worker_number} for tier queue: {queue_name}")

    async def process_message(self, message: Dict[str, Any]) -> bool:
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
            job_id = message.get('job_id')
            first_item = message.get('first_item', False)
            last_item = message.get('last_item', False)
            token = message.get('token')  # 🔑 Extract token from message

            # Send WebSocket status update when first_item=true (worker starting)
            logger.info(f"🔍 [DEBUG] Checking WebSocket conditions: job_id={job_id}, first_item={first_item}")
            if job_id and first_item:
                logger.info(f"🚀 [DEBUG] Sending WebSocket status update: transform worker running for {message_type}")
                try:
                    await self._send_worker_status("transform", tenant_id, job_id, "running", message_type)
                    logger.info(f"✅ [DEBUG] WebSocket status update completed for {message_type}")
                except Exception as ws_error:
                    logger.error(f"❌ [DEBUG] Error sending WebSocket status: {ws_error}")
            else:
                logger.info(f"❌ [DEBUG] WebSocket conditions not met: job_id={job_id}, first_item={first_item}")

            # 🎯 HANDLE COMPLETION MESSAGE: raw_data_id=None signals completion (check BEFORE field validation)
            logger.info(f"🔍 [DEBUG] Checking completion message: raw_data_id={raw_data_id} (type={type(raw_data_id).__name__}), message_type={message_type}")
            if raw_data_id is None:
                logger.info(f"🎯 [COMPLETION] raw_data_id is None - processing completion message for {message_type}")

                # Send WebSocket status: transform worker finished (on last_item)
                if last_item and job_id:
                    try:
                        await self._send_worker_status("transform", tenant_id, job_id, "finished", message_type)
                        logger.info(f"✅ Transform worker marked as finished for {message_type} (completion message)")
                    except Exception as e:
                        logger.error(f"❌ Error sending finished status for {message_type}: {e}")

                # Handle different completion message types
                if message_type == 'jira_dev_status':
                    logger.info(f"🎯 [COMPLETION] Processing jira_dev_status completion message")
                    self._queue_entities_for_embedding(
                        tenant_id=tenant_id,
                        table_name='work_items_prs_links',
                        entities=[],  # Empty list - signals completion
                        job_id=job_id,
                        message_type='jira_dev_status',
                        integration_id=integration_id,
                        provider=message.get('provider', 'jira'),
                        last_sync_date=message.get('last_sync_date'),
                        first_item=message.get('first_item', False),  # ✅ Preserved
                        last_item=message.get('last_item', False),    # ✅ Preserved
                        last_job_item=message.get('last_job_item', False),  # ✅ Preserved
                        token=token  # 🔑 Include token in message
                    )
                    logger.info(f"🎯 [COMPLETION] jira_dev_status completion message forwarded to embedding")
                    return True

                elif message_type == 'jira_issues_with_changelogs':
                    logger.info(f"🎯 [COMPLETION] Processing jira_issues_with_changelogs completion message")
                    self._queue_entities_for_embedding(
                        tenant_id=tenant_id,
                        table_name='work_items',
                        entities=[],  # Empty list - signals completion
                        job_id=job_id,
                        message_type='jira_issues_with_changelogs',
                        integration_id=integration_id,
                        provider=message.get('provider', 'jira'),
                        last_sync_date=message.get('last_sync_date'),
                        first_item=message.get('first_item', False),  # ✅ Preserved
                        last_item=message.get('last_item', False),    # ✅ Preserved
                        last_job_item=message.get('last_job_item', False)  # ✅ Preserved
                    )
                    logger.info(f"🎯 [COMPLETION] jira_issues_with_changelogs completion message forwarded to embedding")
                    return True

                elif message_type == 'github_repositories':
                    logger.info(f"🎯 [COMPLETION] Processing github_repositories completion message")
                    self.queue_manager.publish_embedding_job(
                        tenant_id=tenant_id,
                        table_name='repositories',
                        external_id=None,  # 🔑 Completion message marker
                        job_id=job_id,
                        step_type='github_repositories',
                        integration_id=integration_id,
                        provider=message.get('provider', 'github'),
                        last_sync_date=message.get('last_sync_date'),
                        first_item=message.get('first_item', False),  # ✅ Preserved
                        last_item=message.get('last_item', False),    # ✅ Preserved
                        last_job_item=message.get('last_job_item', False),  # ✅ Preserved
                        token=message.get('token')  # 🔑 Include token in message
                    )
                    logger.info(f"🎯 [COMPLETION] github_repositories completion message forwarded to embedding")
                    return True

                elif message_type in ('github_prs', 'github_prs_nested', 'github_prs_commits_reviews_comments'):
                    logger.info(f"🎯 [COMPLETION] Processing {message_type} completion message")
                    self.queue_manager.publish_embedding_job(
                        tenant_id=tenant_id,
                        table_name='prs',
                        external_id=None,  # 🔑 Completion message marker
                        job_id=job_id,
                        step_type='github_prs_commits_reviews_comments',
                        integration_id=integration_id,
                        provider=message.get('provider', 'github'),
                        last_sync_date=message.get('last_sync_date'),
                        first_item=message.get('first_item', False),  # ✅ Preserved
                        last_item=message.get('last_item', False),    # ✅ Preserved
                        last_job_item=message.get('last_job_item', False),  # ✅ Preserved
                        token=message.get('token')  # 🔑 Include token in message
                    )
                    logger.info(f"🎯 [COMPLETION] {message_type} completion message forwarded to embedding")
                    return True

                else:
                    logger.warning(f"⚠️ [COMPLETION] Unknown completion message type: {message_type}")
                    return False

            # Check required fields
            if not all([message_type, raw_data_id, tenant_id, integration_id]):
                logger.error(f"Missing required fields in message: {message}")
                return False

            logger.info(f"Processing {message_type} message for raw_data_id={raw_data_id} (first_item={first_item}, last_item={last_item})")

            # Send WebSocket status: transform worker starting (on first_item)
            if job_id and first_item:
                try:
                    await self._send_worker_status("transform", tenant_id, job_id, "running", message_type)
                except Exception as e:
                    logger.error(f"❌ Error sending WebSocket status: {e}")

            # Note: Job status is updated via WebSocket status updates above
            # No need to update database directly here

            # Route to appropriate handler based on provider
            result = False
            if message_type.startswith('jira_'):
                # Route all Jira messages to JiraTransformHandler
                result = self.jira_handler.process_jira_message(
                    message_type, raw_data_id, tenant_id, integration_id, job_id, message
                )
            elif message_type.startswith('github_'):
                # Route all GitHub messages to GitHubTransformHandler
                result = self.github_handler.process_github_message(
                    message_type, raw_data_id, tenant_id, integration_id, job_id, message
                )
            else:
                logger.warning(f"Unknown message type: {message_type}")
                result = False

            # 🔔 Send WebSocket status update when last_item=true (transform worker finished)
            if job_id and last_item and result:
                logger.info(f"🏁 [TRANSFORM] Sending WebSocket status update: transform worker finished for {message_type}")
                try:
                    await self._send_worker_status("transform", tenant_id, job_id, "finished", message_type)
                    logger.info(f"✅ [TRANSFORM] WebSocket finished status sent for {message_type}")
                except Exception as ws_error:
                    logger.error(f"❌ [TRANSFORM] Error sending WebSocket finished status: {ws_error}")

            return result

        except Exception as e:
            logger.error(f"Error processing transform message: {e}")
            return False
