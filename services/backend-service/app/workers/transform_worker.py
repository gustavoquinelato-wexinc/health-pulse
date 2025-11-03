"""
Transform Worker for processing raw ETL data (TIER-BASED QUEUE ARCHITECTURE).

Consumes messages from tier-based transform queues and processes raw data based on type:
- jira_custom_fields: Process custom fields discovery data from createmeta API
- jira_special_fields: Process special fields from field search API (e.g., development field)
- jira_issues: Process Jira issues data
- github_prs: Process GitHub PRs data

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


from .base_worker import BaseWorker
from .bulk_operations import BulkOperations
from app.models.unified_models import (
    Project, Wit, CustomField
)
from app.core.logging_config import get_logger
from app.core.database import get_database
from app.etl.queue.queue_manager import QueueManager

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
    Transform worker that processes raw extraction data into final database tables (tier-based queue architecture).

    Handles different data types:
    - jira_custom_fields: Creates/updates projects, WITs, custom fields, and relationships (from createmeta API)
    - jira_special_fields: Creates/updates special fields not in createmeta (e.g., development field)
    - jira_project_search: Creates/updates projects and WITs from project/search API (regular job execution)
    - jira_project_statuses: Creates/updates statuses and project relationships
    - jira_issues_changelogs: Processes work items and changelogs
    - jira_issue: Processes individual work items (optimized)
    - jira_dev_status: Processes development status data

    Tier-Based Queue Mode:
    - Consumes from tier-based queue (e.g., transform_queue_premium)
    - Uses tenant_id from message for proper data routing
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
        logger.info(f"Initialized TransformWorker #{worker_number} for tier queue: {queue_name}")

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

    async def _queue_to_embedding(self, tenant_id: int, integration_id: int, job_id: int,
                                 step_type: str, provider: str = None, first_item: bool = False,
                                 last_item: bool = False, last_sync_date: str = None,
                                 last_job_item: bool = False, external_id: str = None):
        """Queue ETL step completion message to embedding worker with standardized structure."""
        try:
            queue_manager = QueueManager()

            # Standardized base message structure
            message = {
                'tenant_id': tenant_id,
                'integration_id': integration_id,
                'job_id': job_id,
                'type': step_type,  # ETL step name
                'provider': provider or 'jira',
                'first_item': first_item,
                'last_item': last_item,
                'last_sync_date': last_sync_date,
                'last_job_item': last_job_item,
                'external_id': external_id or f"bulk_{step_type}"
            }

            # Get tenant tier and route to tier-based embedding queue
            tier = queue_manager._get_tenant_tier(tenant_id)
            tier_queue = queue_manager.get_tier_queue_name(tier, 'embedding')

            logger.info(f"📤 [EMBEDDING] Queuing ETL step {step_type} to {tier_queue}: first_item={first_item}, last_item={last_item}")

            success = queue_manager._publish_message(tier_queue, message)

            if success:
                logger.info(f"✅ [EMBEDDING] Successfully queued ETL step {step_type} to embedding")
            else:
                logger.error(f"❌ [EMBEDDING] Failed to queue ETL step {step_type} to embedding")

        except Exception as e:
            logger.error(f"Error queuing ETL step to embedding: {e}")

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
            job_id = message.get('job_id')
            first_item = message.get('first_item', False)
            last_item = message.get('last_item', False)
            bulk_processing = message.get('bulk_processing', False)
            token = message.get('token')  # 🔑 Extract token from message

            # Send WebSocket status update when first_item=true (worker starting)
            logger.info(f"🔍 [DEBUG] Checking WebSocket conditions: job_id={job_id}, first_item={first_item}")
            if job_id and first_item:
                logger.info(f"🚀 [DEBUG] Sending WebSocket status update: transform worker running for {message_type}")
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "running", message_type))
                    logger.info(f"✅ [DEBUG] WebSocket status update completed for {message_type}")
                except Exception as ws_error:
                    logger.error(f"❌ [DEBUG] Error sending WebSocket status: {ws_error}")
                finally:
                    loop.close()
            else:
                logger.info(f"❌ [DEBUG] WebSocket conditions not met: job_id={job_id}, first_item={first_item}")

            # 🎯 HANDLE COMPLETION MESSAGE: raw_data_id=None signals completion (check BEFORE field validation)
            logger.info(f"🔍 [DEBUG] Checking completion message: raw_data_id={raw_data_id} (type={type(raw_data_id).__name__}), message_type={message_type}")
            if raw_data_id is None:
                logger.info(f"🎯 [COMPLETION] raw_data_id is None - processing completion message for {message_type}")

                # Send WebSocket status: transform worker finished (on last_item)
                if last_item and job_id:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "finished", message_type))
                        logger.info(f"✅ Transform worker marked as finished for {message_type} (completion message)")
                    except Exception as e:
                        logger.error(f"❌ Error sending finished status for {message_type}: {e}")
                    finally:
                        loop.close()

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

            # Check required fields - for bulk processing, raw_data_id is optional
            if bulk_processing:
                # Bulk processing messages need: message_type, tenant_id, integration_id, job_id
                if not all([message_type, tenant_id, integration_id, job_id]):
                    logger.error(f"Missing required fields in bulk processing message: {message}")
                    return False
            else:
                # Regular messages need: message_type, raw_data_id, tenant_id, integration_id
                if not all([message_type, raw_data_id, tenant_id, integration_id]):
                    logger.error(f"Missing required fields in regular message: {message}")
                    return False

            if bulk_processing:
                logger.info(f"Processing {message_type} bulk message for job_id={job_id} (first_item={first_item}, last_item={last_item})")
            else:
                logger.info(f"Processing {message_type} message for raw_data_id={raw_data_id} (first_item={first_item}, last_item={last_item})")

            # Send WebSocket status: transform worker starting (on first_item)
            if job_id and first_item:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "running", message_type))
                finally:
                    loop.close()

            # Update job status to RUNNING (if job_id provided)
            if job_id:
                self._update_job_status(job_id, message_type, "running", f"Transforming {message_type}")

            # Handle bulk processing messages (no raw data to process)
            if bulk_processing:
                logger.info(f"🔄 [BULK] Processing bulk {message_type} message - no raw data processing needed")

                # Send WebSocket status: transform worker finished (on last_item)
                if job_id and last_item:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "finished", message_type))
                        # Queue to embedding worker
                        loop.run_until_complete(self._queue_to_embedding(tenant_id, integration_id, job_id, message_type,
                                                                        provider='jira', first_item=first_item, last_item=last_item))
                    finally:
                        loop.close()

                return True

            # Route to appropriate processor based on type (regular messages with raw_data_id)
            if message_type == 'jira_custom_fields':
                return self._process_jira_custom_fields(
                    raw_data_id, tenant_id, integration_id
                )
            elif message_type == 'jira_special_fields':
                return self._process_jira_special_fields(
                    raw_data_id, tenant_id, integration_id
                )

            elif message_type == 'jira_project_search':
                return self._process_jira_project_search(
                    raw_data_id, tenant_id, integration_id, job_id
                )
            elif message_type == 'jira_projects_and_issue_types':
                return self._process_jira_project_search(
                    raw_data_id, tenant_id, integration_id, job_id, message
                )
            elif message_type == 'jira_project_statuses':
                return self._process_jira_statuses_and_project_relationships(
                    raw_data_id, tenant_id, integration_id, job_id
                )
            elif message_type == 'jira_statuses_and_project_relationships':
                return self._process_jira_statuses_and_project_relationships(
                    raw_data_id, tenant_id, integration_id, job_id
                )
            elif message_type == 'jira_statuses_and_relationships':
                return self._process_jira_statuses_and_project_relationships(
                    raw_data_id, tenant_id, integration_id, job_id, message
                )
            elif message_type == 'jira_issues_changelogs':
                # Legacy batch processing (kept for backward compatibility)
                return self._process_jira_issues_changelogs(
                    raw_data_id, tenant_id, integration_id, job_id, message
                )
            elif message_type == 'jira_single_issue_changelog':
                # Individual issue processing with changelog
                return self._process_jira_single_issue_changelog(
                    raw_data_id, tenant_id, integration_id, job_id, message
                )
            elif message_type == 'jira_issues_with_changelogs':
                # Individual issue processing with changelog (new step name)
                return self._process_jira_single_issue_changelog(
                    raw_data_id, tenant_id, integration_id, job_id, message
                )
            elif message_type == 'jira_issue':
                # Legacy individual issue processing - route to issues_with_changelogs
                return self._process_jira_single_issue_changelog(
                    raw_data_id, tenant_id, integration_id, job_id, message
                )
            elif message_type == 'jira_dev_status':
                return self._process_jira_dev_status(
                    raw_data_id, tenant_id, integration_id, job_id, message
                )
            elif message_type == 'github_repositories':
                return self._process_github_repositories(
                    raw_data_id, tenant_id, integration_id, job_id, message
                )
            elif message_type == 'github_prs':
                return self._process_github_prs(
                    raw_data_id, tenant_id, integration_id, job_id, message
                )
            elif message_type == 'github_prs_nested':
                return self._process_github_prs_nested(
                    raw_data_id, tenant_id, integration_id, job_id, message
                )
            elif message_type == 'github_prs_commits_reviews_comments':
                # Legacy message type - route to new handler
                return self._process_github_prs(
                    raw_data_id, tenant_id, integration_id, job_id, message
                )
            else:
                logger.warning(f"Unknown message type: {message_type}")
                return False

            # This code is unreachable because all processors return above
            # WebSocket status updates should be handled within individual processors
            return False  # Should never reach here

        except Exception as e:
            logger.error(f"Error processing transform message: {e}")
            return False




    def _process_jira_project_search(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
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

            # ✅ Send transform worker "running" status when first_item=True
            if message and message.get('first_item') and job_id:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "running", "jira_projects_and_issue_types"))
                    logger.info(f"✅ Transform worker marked as running for jira_projects_and_issue_types")
                finally:
                    loop.close()

            database = get_database()
            with database.get_write_session_context() as session:
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

                # 6. Queue ALL entities for embedding AFTER commit (not just changed ones)
                # Get message info for forwarding
                provider = message.get('provider') if message else 'jira'
                last_sync_date = message.get('last_sync_date') if message else None
                last_job_item = message.get('last_job_item', False) if message else False

                # Queue ALL active projects and wits for embedding (ensures complete vectorization)
                self._queue_all_entities_for_embedding(
                    session=session,
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    job_id=job_id,
                    message_type='jira_projects_and_issue_types',
                    provider=provider,
                    last_sync_date=last_sync_date,
                    last_job_item=last_job_item,
                    token=token  # 🔑 Include token in message
                )

                # ✅ Send transform worker "finished" status when last_item=True
                if message and message.get('last_item') and job_id:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "finished", "jira_projects_and_issue_types"))
                        logger.info(f"✅ Transform worker marked as finished for jira_projects_and_issue_types")
                    finally:
                        loop.close()

                # ❌ REMOVED: Transform workers should NEVER queue back to extraction
                # The extraction worker already queued the next extraction step (jira_statuses_and_relationships)
                # when it completed jira_projects_and_issue_types
                logger.info(f"✅ Projects transform processing complete - extraction worker handles next extraction step")

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
        - Queues projects and WITs for embedding
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
                        'external_id': project_external_id,  # Needed for embedding queue
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
                # Projects and WITs are NOT queued for embedding here
                # Only /project/search should queue for embedding

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

    def _process_jira_statuses_and_project_relationships(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
        """
        Process statuses and project relationships from raw data.

        This function:
        1. Retrieves raw data from raw_extraction_data table
        2. Processes statuses and saves to statuses table with mapping links
        3. Processes project-status relationships and saves to projects_statuses table
        4. Returns success status
        """
        try:
            # ✅ Send transform worker "running" status when first_item=True
            if message and message.get('first_item') and job_id:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "running", "jira_statuses_and_relationships"))
                    logger.info(f"✅ Transform worker marked as running for jira_statuses_and_relationships")
                finally:
                    loop.close()

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

                # Queue statuses for embedding AFTER commit
                # Get message info for forwarding
                provider = message.get('provider') if message else 'jira'
                last_sync_date = message.get('last_sync_date') if message else None

                # 🎯 NEW LOGIC: Only queue to embedding when last_item=True
                # This ensures we process all projects first, then query all distinct statuses once
                # This avoids duplicate embeddings for the same status across different projects

                statuses_processed = statuses_result['count']
                logger.info(f"Successfully processed {statuses_processed} statuses and {relationships_processed} project relationships")

                # 🎯 DEBUG: Log message details
                logger.info(f"🎯 [STATUSES] Message check: message={message is not None}, last_item={message.get('last_item') if message else 'N/A'}")

                if message and message.get('last_item'):
                    logger.info(f"🎯 [STATUSES] Last item received - queuing all distinct statuses to embedding")

                    # Query all distinct status external_ids from statuses table for this tenant/integration
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
                    logger.info(f"🎯 [STATUSES] Found {len(status_external_ids)} distinct statuses to queue for embedding")

                    # Get message info for forwarding
                    provider = message.get('provider') if message else 'jira'
                    last_sync_date = message.get('last_sync_date') if message else None
                    last_job_item = message.get('last_job_item', False)

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
                            last_sync_date=last_sync_date,
                            first_item=is_first,
                            last_item=is_last,
                            last_job_item=last_job_item,
                            token=token  # 🔑 Include token in message
                        )

                    logger.info(f"🎯 [STATUSES] Queued {len(status_external_ids)} distinct statuses for embedding")

                    # ✅ Send transform worker "finished" status when last_item=True
                    if job_id:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "finished", "jira_statuses_and_relationships"))
                            logger.info(f"✅ Transform worker marked as finished for jira_statuses_and_relationships")
                        finally:
                            loop.close()
                else:
                    logger.info(f"🎯 [STATUSES] Not last item (first_item={message.get('first_item') if message else False}, last_item={message.get('last_item') if message else False}) - skipping embedding queue")

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

    def _queue_entities_for_embedding(
        self,
        tenant_id: int,
        table_name: str,
        entities: List[Dict[str, Any]],
        job_id: int = None,
        last_item: bool = False,
        provider: str = None,
        last_sync_date: str = None,
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
        """
        # 🎯 HANDLE COMPLETION MESSAGE: Empty entities with last_job_item=True
        if not entities and last_job_item:
            logger.info(f"[COMPLETION] Sending job completion message to embedding queue (no {table_name} entities)")

            # Send completion message to embedding queue with external_id=None
            queue_manager = QueueManager()
            success = queue_manager.publish_embedding_job(
                tenant_id=tenant_id,
                table_name=table_name,
                external_id=None,  # 🔧 None signals completion message
                job_id=job_id,
                integration_id=integration_id,
                provider=provider,
                last_sync_date=last_sync_date,
                first_item=first_item,
                last_item=last_item,
                last_job_item=last_job_item,  # 🎯 Signal job completion
                step_type=message_type,
                token=token  # 🔑 Include token in message
            )

            if success:
                logger.info(f"✅ Sent completion message to embedding queue for {table_name}")
            else:
                logger.error(f"❌ Failed to send completion message to embedding queue for {table_name}")

            return

        if not entities:
            # 🎯 COMPLETION CHAIN: If entities is empty but we have last_item=True, publish completion message
            if last_item:
                logger.info(f"🎯 [COMPLETION] Publishing completion message to embedding queue for {table_name}")
                queue_manager = QueueManager()
                success = queue_manager.publish_embedding_job(
                    tenant_id=tenant_id,
                    table_name=table_name,
                    external_id=None,  # 🔑 Key: None signals completion message
                    job_id=job_id,
                    integration_id=integration_id,
                    provider=provider,
                    last_sync_date=last_sync_date,
                    first_item=first_item,    # ✅ Preserved
                    last_item=last_item,      # ✅ Preserved (True)
                    last_job_item=last_job_item,  # ✅ Preserved
                    step_type=message_type,
                    token=token  # 🔑 Include token in message
                )
                logger.info(f"🎯 [COMPLETION] Embedding completion message published: {success}")
            else:
                logger.debug(f"No entities to queue for {table_name}")
            return

        try:
            logger.info(f"Attempting to queue {len(entities)} {table_name} entities for embedding")
            queue_manager = QueueManager()
            queued_count = 0

            # Update step status to running when queuing for embedding
            if job_id and queued_count == 0:  # Only on first entity to avoid multiple updates
                # Don't update overall status here - let embedding worker handle completion
                logger.info(f"Transform completed, queuing {table_name} for embedding")

            for entity in entities:
                # Get external ID based on table type
                external_id = None

                if table_name == 'projects':
                    external_id = entity.get('external_id')
                    logger.debug(f"Project entity keys: {list(entity.keys())}, external_id value: {external_id}")
                    logger.debug(f"Full project entity: {entity}")
                elif table_name == 'wits':
                    external_id = entity.get('external_id')
                elif table_name == 'statuses':
                    external_id = entity.get('external_id')
                elif table_name == 'custom_fields':
                    external_id = entity.get('external_id')
                elif table_name == 'work_items':
                    # For work_items, use 'external_id' field (maps to Jira payload IDs)
                    external_id = entity.get('external_id')
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

                # Publish embedding message with standardized structure
                success = queue_manager.publish_embedding_job(
                    tenant_id=tenant_id,
                    table_name=table_name,
                    external_id=str(external_id),
                    job_id=job_id,
                    integration_id=integration_id,
                    provider=provider,
                    last_sync_date=last_sync_date,
                    first_item=first_item and (queued_count == 0),  # Use passed first_item flag
                    last_item=last_item and (queued_count == len(entities) - 1),  # Use passed last_item flag
                    last_job_item=last_job_item,  # Forward last_job_item flag from incoming message
                    step_type=message_type,  # Pass the step type (e.g., 'jira_projects_and_issue_types')
                    token=token  # 🔑 Include token in message
                )

                if success:
                    queued_count += 1

            if queued_count > 0:
                logger.info(f"Queued {queued_count} {table_name} entities for embedding")

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
        last_sync_date: str,
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
            last_sync_date: Last sync date
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
            logger.info(f"🔄 Queueing ALL entities for embedding: {len(all_projects)} projects + {len(all_wits)} wits = {total_entities} total")

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
                    last_sync_date=last_sync_date,
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
                    last_sync_date=last_sync_date,
                    first_item=is_first,
                    last_item=is_last,
                    last_job_item=last_job_item,
                    token=token  # 🔑 Include token in message
                )

            logger.info(f"✅ Successfully queued {total_entities} entities for embedding")

        except Exception as e:
            logger.error(f"Error queuing all entities for embedding: {e}")
            # Don't raise - embedding is async and shouldn't block transform

    def _process_jira_issues_changelogs(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
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
                    db, issues_data, integration_id, tenant_id, projects_map, wits_map, statuses_map, custom_field_mappings, job_id, message
                )

                # Process changelogs
                changelogs_processed = self._process_changelogs_data(
                    db, issues_data, integration_id, tenant_id, statuses_map, job_id, message
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
                            error_details = CAST(:error_details AS jsonb),
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

    def _process_jira_single_issue(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
        """
        Process a single Jira issue from raw_extraction_data.

        This is the optimized version that processes individual issues instead of batches.

        Flow:
        1. Load single issue raw data from raw_extraction_data table
        2. Transform issue data and insert/update work_items table
        3. Transform changelog data and insert changelogs table
        4. Queue work_item and changelogs for vectorization
        """
        try:
            logger.debug(f"Processing single jira_issue for raw_data_id={raw_data_id}")

            with self.get_db_session() as db:
                # Load raw data (single issue)
                raw_data = self._get_raw_data(db, raw_data_id)
                if not raw_data:
                    logger.error(f"Raw data {raw_data_id} not found")
                    return False

                # Raw data is a single issue object (not wrapped in 'issues' array)
                issue = raw_data

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
                    db, [issue], integration_id, tenant_id, projects_map, wits_map, statuses_map, custom_field_mappings, job_id
                )

                # Process changelogs for this issue
                changelogs_processed = self._process_changelogs_data(
                    db, [issue], integration_id, tenant_id, statuses_map, job_id
                )

                # Note: dev_status extraction is now handled by extraction worker, not transform worker

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

                logger.debug(f"Processed issue {issue.get('key')} with {changelogs_processed} changelogs - marked raw_data_id={raw_data_id} as completed")
                return True

        except Exception as e:
            logger.error(f"Error processing single jira_issue (raw_data_id={raw_data_id}): {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

            # Mark raw data as failed
            try:
                with self.get_db_session() as db:
                    error_query = text("""
                        UPDATE raw_extraction_data
                        SET status = 'failed',
                            error_details = CAST(:error_details AS jsonb),
                            last_updated_at = NOW()
                        WHERE id = :raw_data_id
                    """)
                    db.execute(error_query, {
                        'raw_data_id': raw_data_id,
                        'error_details': json.dumps({'error': str(e)[:500]})
                    })
                    db.commit()
            except Exception as update_error:
                logger.error(f"Failed to update raw_data status to failed: {update_error}")

            return False

    def _process_jira_single_issue_changelog(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
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
                logger.info(f"[COMPLETION] Received completion message for jira_issues_with_changelogs (no data to process)")

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

                logger.info(f"✅ Sent completion message to embedding queue")
                return True

            logger.debug(f"Processing single jira_single_issue_changelog for raw_data_id={raw_data_id}")

            # ✅ Send transform worker "running" status when first_item=True
            if message and message.get('first_item') and job_id:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "running", "jira_issues_with_changelogs"))
                    logger.info(f"✅ Transform worker marked as running for jira_issues_with_changelogs")
                finally:
                    loop.close()

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

                # Process changelogs for this issue
                changelogs_processed = self._process_changelogs_data(
                    db, [issue], integration_id, tenant_id, statuses_map, job_id, message
                )

                # Note: dev_status extraction is now handled by extraction worker, not transform worker

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

                # ✅ Send transform worker "finished" status when last_item=True
                if message and message.get('last_item') and job_id:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "finished", "jira_issues_with_changelogs"))
                        logger.info(f"✅ Transform worker marked as finished for jira_issues_with_changelogs")
                    finally:
                        loop.close()

                logger.debug(f"Processed issue {issue.get('key')} with {changelogs_processed} changelogs - marked raw_data_id={raw_data_id} as completed")
                return True

        except Exception as e:
            logger.error(f"Error processing single jira_single_issue_changelog (raw_data_id={raw_data_id}): {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

            # Mark raw data as failed
            try:
                with self.get_db_session() as db:
                    error_query = text("""
                        UPDATE raw_extraction_data
                        SET status = 'failed',
                            error_details = CAST(:error_details AS jsonb),
                            last_updated_at = NOW()
                        WHERE id = :raw_data_id
                    """)
                    db.execute(error_query, {
                        'raw_data_id': raw_data_id,
                        'error_details': json.dumps({'error': str(e)[:500]})
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
                # This will extract team, development, story_points, and custom_field_01-20
                all_fields_data = self._extract_all_fields(fields, custom_field_mappings)

                # Extract special fields from the result
                team = all_fields_data.pop('team', None)
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
                        'priority': priority,
                        'resolution': resolution,
                        'assignee': assignee,
                        'team': team,
                        'labels': labels,
                        'updated': updated,
                        'parent_external_id': parent_external_id,
                        'development': development,
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
                        'development': development,
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

        # Get flags from incoming message to forward to embedding
        first_item = message.get('first_item', False) if message else False
        last_item = message.get('last_item', False) if message else False
        last_job_item = message.get('last_job_item', False) if message else False
        provider = message.get('provider') if message else 'jira'
        last_sync_date = message.get('last_sync_date') if message else None

        # Bulk insert new issues
        if issues_to_insert:
            BulkOperations.bulk_insert(db, 'work_items', issues_to_insert)
            logger.info(f"Inserted {len(issues_to_insert)} new issues")

            # Queue for embedding - forward first_item/last_item/last_job_item flags from incoming message
            self._queue_entities_for_embedding(tenant_id, 'work_items', issues_to_insert, job_id,
                                             message_type='jira_issues_with_changelogs', integration_id=integration_id,
                                             provider=provider, last_sync_date=last_sync_date,
                                             first_item=first_item, last_item=last_item, last_job_item=last_job_item)

        # Bulk update existing issues
        if issues_to_update:
            BulkOperations.bulk_update(db, 'work_items', issues_to_update)
            logger.info(f"Updated {len(issues_to_update)} existing issues")

            logger.debug(f"[DEBUG] Queuing {len(issues_to_update)} issues_to_update for embedding")
            for i, entity in enumerate(issues_to_update[:3]):  # Log first 3 entities
                logger.debug(f"[DEBUG] issues_to_update[{i}] keys: {list(entity.keys())}")
                logger.debug(f"[DEBUG] issues_to_update[{i}] external_id: {entity.get('external_id')}")

            # Queue for embedding - forward first_item/last_item/last_job_item flags from incoming message
            self._queue_entities_for_embedding(tenant_id, 'work_items', issues_to_update, job_id,
                                             message_type='jira_issues_with_changelogs', integration_id=integration_id,
                                             provider=provider, last_sync_date=last_sync_date,
                                             first_item=first_item, last_item=last_item, last_job_item=last_job_item,
                                             token=token)  # 🔑 Include token in message

        return len(issues_to_insert) + len(issues_to_update)

    def _process_changelogs_data(
        self, db, issues_data: List[Dict], integration_id: int, tenant_id: int,
        statuses_map: Dict, job_id: int = None, message: Dict[str, Any] = None
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

            # Get flags from incoming message to forward to embedding
            first_item = message.get('first_item', False) if message else False
            last_item = message.get('last_item', False) if message else False
            last_job_item = message.get('last_job_item', False) if message else False
            provider = message.get('provider') if message else 'jira'
            last_sync_date = message.get('last_sync_date') if message else None

            # Queue for embedding - forward first_item/last_item/last_job_item flags from incoming message
            self._queue_entities_for_embedding(tenant_id, 'changelogs', changelogs_to_insert, job_id,
                                             message_type='jira_issues_with_changelogs', integration_id=integration_id,
                                             provider=provider, last_sync_date=last_sync_date,
                                             first_item=first_item, last_item=last_item, last_job_item=last_job_item)

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

    def _process_jira_dev_status(self, raw_data_id: int, tenant_id: int, integration_id: int, job_id: int = None, message: Dict[str, Any] = None) -> bool:
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

            logger.info(f"🎯 [DEV_STATUS] Processing jira_dev_status for raw_data_id={raw_data_id} (first={first_item}, last={last_item}, job_end={last_job_item})")

            # ✅ Send transform worker "running" status when first_item=True
            if message and message.get('first_item') and job_id:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "running", "jira_dev_status"))
                    logger.info(f"✅ Transform worker marked as running for jira_dev_status (first_item=True)")
                finally:
                    loop.close()

            with self.get_db_session() as db:
                # Load raw data
                raw_data = self._get_raw_data(db, raw_data_id)
                if not raw_data:
                    logger.error(f"Raw data {raw_data_id} not found")
                    # ✅ Send transform worker "finished" status when last_item=True even if raw data not found
                    if message and message.get('last_item') and job_id:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "finished", "jira_dev_status"))
                            logger.info(f"✅ Transform worker marked as finished for jira_dev_status (raw data not found)")
                        finally:
                            loop.close()
                    return False

                # Extract dev_status data - handle single issue format from extraction worker
                issue_key = raw_data.get('issue_key')
                issue_id = raw_data.get('issue_id')
                dev_status = raw_data.get('dev_status')

                if not dev_status or not issue_key:
                    logger.warning(f"No dev_status or issue_key found in raw_data_id={raw_data_id}")
                    # ✅ Send transform worker "finished" status when last_item=True even if no data
                    if message and message.get('last_item') and job_id:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "finished", "jira_dev_status"))
                            logger.info(f"✅ Transform worker marked as finished for jira_dev_status (no data)")
                        finally:
                            loop.close()
                    return True

                # Convert to list format expected by _process_dev_status_data
                dev_status_data = [{
                    'issue_key': issue_key,
                    'issue_id': issue_id,
                    'dev_details': dev_status
                }]

                logger.info(f"Processing dev_status for issue {issue_key}")

                # Process dev_status
                pr_links_processed = self._process_dev_status_data(
                    db, dev_status_data, integration_id, tenant_id, job_id, message
                )

                # Update raw data status to completed
                from sqlalchemy import text
                update_query = text("""
                    UPDATE raw_extraction_data
                    SET status = 'completed',
                        last_updated_at = NOW(),
                        error_details = NULL
                    WHERE id = :raw_data_id
                """)
                db.execute(update_query, {'raw_data_id': raw_data_id})
                db.commit()

                logger.info(f"Processed {pr_links_processed} PR links from dev_status - marked raw_data_id={raw_data_id} as completed")

                # Note: first_item/last_item flags are now properly forwarded through _process_dev_status_data

                # ✅ Send transform worker "finished" status when last_item=True
                if message and message.get('last_item') and job_id:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "finished", "jira_dev_status"))
                        logger.info(f"✅ Transform worker marked as finished for jira_dev_status")
                    finally:
                        loop.close()

                return True

        except Exception as e:
            logger.error(f"Error processing jira_dev_status: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

            # Mark as failed
            try:
                with self.get_db_session() as db:
                    from sqlalchemy import text
                    update_query = text("""
                        UPDATE raw_extraction_data
                        SET status = 'failed',
                            last_updated_at = NOW(),
                            error_details = CAST(:error_details AS jsonb)
                        WHERE id = :raw_data_id
                    """)
                    import json
                    db.execute(update_query, {
                        'raw_data_id': raw_data_id,
                        'error_details': json.dumps({'error': str(e), 'traceback': traceback.format_exc()})
                    })
                    db.commit()
            except Exception as update_error:
                logger.error(f"Failed to mark raw_data as failed: {update_error}")

            # ✅ Send transform worker "failed" status when last_item=True even on exception
            if message and message.get('last_item') and job_id:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "failed", "jira_dev_status", error_message=str(e)))
                    logger.info(f"✅ Transform worker marked as failed for jira_dev_status (exception)")
                finally:
                    loop.close()

            return False

    def _process_dev_status_data(
        self, db, dev_status_data: List[Dict], integration_id: int, tenant_id: int, job_id: int = None, message: Dict[str, Any] = None
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

            # Get flags from incoming message to forward to embedding
            first_item = message.get('first_item', False) if message else False
            last_item = message.get('last_item', False) if message else False
            last_job_item = message.get('last_job_item', False) if message else False
            provider = message.get('provider') if message else 'jira'
            last_sync_date = message.get('last_sync_date') if message else None
            token = message.get('token') if message else None  # 🔑 Extract token from message

            # Queue for embedding - forward first_item/last_item/last_job_item flags from incoming message
            if inserted_links:
                self._queue_entities_for_embedding(tenant_id, 'work_items_prs_links', inserted_links, job_id,
                                                 message_type='jira_dev_status', integration_id=integration_id,
                                                 provider=provider, last_sync_date=last_sync_date,
                                                 first_item=first_item, last_item=last_item, last_job_item=last_job_item,
                                                 token=token)  # 🔑 Forward token to embedding

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
                        last_updated_at = NOW()
                    WHERE id = :job_id
                """)

                session.execute(update_query, {
                    'job_id': job_id
                })
                session.commit()

                logger.info(f"Updated job {job_id} step {step_name} transform status to {step_status}")
                if message:
                    logger.info(f"Job {job_id} message: {message}")

        except Exception as e:
            logger.error(f"Error updating job status: {e}")

    def _process_github_repositories(self, raw_data_id: int, tenant_id: int, integration_id: int,
                                    job_id: int, message: Dict[str, Any] = None) -> bool:
        """
        Process GitHub repositories batch from raw_extraction_data.

        Flow:
        1. Load raw data containing all repositories
        2. Transform each repository and upsert to repositories table
        3. Queue each repository for embedding with proper first_item/last_item flags
        4. Send WebSocket status updates

        Args:
            raw_data_id: ID of raw extraction data
            tenant_id: Tenant ID
            integration_id: Integration ID
            job_id: ETL job ID
            message: Original message with flags and metadata

        Returns:
            bool: True if processing succeeded
        """
        try:
            first_item = message.get('first_item', False) if message else False
            last_item = message.get('last_item', False) if message else False
            last_job_item = message.get('last_job_item', False) if message else False
            provider = message.get('provider', 'github') if message else 'github'
            last_sync_date = message.get('last_sync_date') if message else None

            logger.info(f"🚀 [GITHUB] Processing repositories batch for tenant {tenant_id}, integration {integration_id}, raw_data_id={raw_data_id}")

            # Send WebSocket status: transform worker starting (on first_item)
            if job_id and first_item:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "running", "github_repositories"))
                finally:
                    loop.close()

            # Fetch raw batch data
            from app.core.database import get_database
            database = get_database()

            with database.get_read_session_context() as db:
                raw_data_query = text("""
                    SELECT raw_data FROM raw_extraction_data
                    WHERE id = :raw_data_id AND tenant_id = :tenant_id
                """)
                result = db.execute(raw_data_query, {'raw_data_id': raw_data_id, 'tenant_id': tenant_id}).fetchone()

                if not result:
                    logger.error(f"Raw data not found for raw_data_id={raw_data_id}")
                    return False

                raw_batch_data = result[0]
                if isinstance(raw_batch_data, str):
                    raw_batch_data = json.loads(raw_batch_data)

            # Extract repositories from batch
            repositories = raw_batch_data.get('repositories', [])
            logger.info(f"📦 Processing {len(repositories)} repositories from batch")

            if not repositories:
                logger.warning(f"No repositories found in raw_data_id={raw_data_id}")
                return True

            # Transform and upsert all repositories in this batch
            # 🔑 Flag forwarding logic for looping through repositories:
            # - first_item=True only on FIRST repo in the loop
            # - last_item=True only on LAST repo in the loop
            # - last_job_item=True only on LAST repo in the loop (when incoming last_job_item=True)
            # - All middle repos: all flags=False

            # Collect repos to queue AFTER database transaction completes
            repos_to_queue = []

            with database.get_write_session_context() as db:
                for i, raw_repo_data in enumerate(repositories):
                    is_first_repo_in_loop = (i == 0)
                    is_last_repo_in_loop = (i == len(repositories) - 1)

                    transformed_repo = {
                        'tenant_id': tenant_id,
                        'integration_id': integration_id,
                        'external_id': str(raw_repo_data.get('id')),
                        'name': raw_repo_data.get('name'),
                        'full_name': raw_repo_data.get('full_name'),
                        'owner': raw_repo_data.get('owner', {}).get('login'),
                        'description': raw_repo_data.get('description'),
                        'language': raw_repo_data.get('language'),
                        'default_branch': raw_repo_data.get('default_branch'),
                        'visibility': raw_repo_data.get('visibility'),
                        'topics': json.dumps(raw_repo_data.get('topics', [])),  # Convert to JSON string for JSONB
                        'is_private': raw_repo_data.get('private', False),
                        'archived': raw_repo_data.get('archived', False),
                        'disabled': raw_repo_data.get('disabled', False),
                        'fork': raw_repo_data.get('fork', False),
                        'is_template': raw_repo_data.get('is_template', False),
                        'allow_forking': raw_repo_data.get('allow_forking', True),
                        'web_commit_signoff_required': raw_repo_data.get('web_commit_signoff_required', False),
                        'has_issues': raw_repo_data.get('has_issues', True),
                        'has_wiki': raw_repo_data.get('has_wiki', False),
                        'has_discussions': raw_repo_data.get('has_discussions', False),
                        'has_projects': raw_repo_data.get('has_projects', False),
                        'has_downloads': raw_repo_data.get('has_downloads', True),
                        'has_pages': raw_repo_data.get('has_pages', False),
                        'license': raw_repo_data.get('license', {}).get('name') if raw_repo_data.get('license') else None,
                        'stargazers_count': raw_repo_data.get('stargazers_count', 0),
                        'forks_count': raw_repo_data.get('forks_count', 0),
                        'open_issues_count': raw_repo_data.get('open_issues_count', 0),
                        'size': raw_repo_data.get('size', 0),
                        'repo_created_at': self._parse_datetime(raw_repo_data.get('created_at')),
                        'repo_updated_at': self._parse_datetime(raw_repo_data.get('updated_at')),
                        'pushed_at': self._parse_datetime(raw_repo_data.get('pushed_at')),
                        'active': True,
                        'last_updated_at': datetime.now()
                    }

                    upsert_query = text("""
                        INSERT INTO repositories (
                            tenant_id, integration_id, external_id, name, full_name, owner,
                            description, language, default_branch, visibility, topics,
                            is_private, archived, disabled, fork, is_template, allow_forking,
                            web_commit_signoff_required, has_issues, has_wiki, has_discussions,
                            has_projects, has_downloads, has_pages, license,
                            stargazers_count, forks_count, open_issues_count, size,
                            repo_created_at, repo_updated_at, pushed_at, active, last_updated_at
                        ) VALUES (
                            :tenant_id, :integration_id, :external_id, :name, :full_name, :owner,
                            :description, :language, :default_branch, :visibility, :topics,
                            :is_private, :archived, :disabled, :fork, :is_template, :allow_forking,
                            :web_commit_signoff_required, :has_issues, :has_wiki, :has_discussions,
                            :has_projects, :has_downloads, :has_pages, :license,
                            :stargazers_count, :forks_count, :open_issues_count, :size,
                            :repo_created_at, :repo_updated_at, :pushed_at, :active, :last_updated_at
                        )
                        ON CONFLICT (tenant_id, integration_id, external_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            full_name = EXCLUDED.full_name,
                            owner = EXCLUDED.owner,
                            description = EXCLUDED.description,
                            language = EXCLUDED.language,
                            default_branch = EXCLUDED.default_branch,
                            visibility = EXCLUDED.visibility,
                            topics = EXCLUDED.topics,
                            is_private = EXCLUDED.is_private,
                            archived = EXCLUDED.archived,
                            disabled = EXCLUDED.disabled,
                            fork = EXCLUDED.fork,
                            is_template = EXCLUDED.is_template,
                            allow_forking = EXCLUDED.allow_forking,
                            web_commit_signoff_required = EXCLUDED.web_commit_signoff_required,
                            has_issues = EXCLUDED.has_issues,
                            has_wiki = EXCLUDED.has_wiki,
                            has_discussions = EXCLUDED.has_discussions,
                            has_projects = EXCLUDED.has_projects,
                            has_downloads = EXCLUDED.has_downloads,
                            has_pages = EXCLUDED.has_pages,
                            license = EXCLUDED.license,
                            stargazers_count = EXCLUDED.stargazers_count,
                            forks_count = EXCLUDED.forks_count,
                            open_issues_count = EXCLUDED.open_issues_count,
                            size = EXCLUDED.size,
                            repo_created_at = EXCLUDED.repo_created_at,
                            repo_updated_at = EXCLUDED.repo_updated_at,
                            pushed_at = EXCLUDED.pushed_at,
                            active = EXCLUDED.active,
                            last_updated_at = EXCLUDED.last_updated_at
                        RETURNING id, external_id
                    """)

                    result = db.execute(upsert_query, transformed_repo)
                    repo_record = result.fetchone()

                    if repo_record:
                        # Store repo info for queueing AFTER transaction commits
                        repos_to_queue.append({
                            'external_id': repo_record[1],
                            'full_name': transformed_repo['full_name'],
                            'is_first_in_batch': is_first_repo_in_loop,
                            'is_last_in_batch': is_last_repo_in_loop
                        })

                        logger.debug(f"✅ Processed repository {transformed_repo['full_name']}")

            # 🔑 CRITICAL: Queue for embedding AFTER database transaction commits
            # This prevents race condition where embedding worker tries to read data before it's committed
            # 🔑 Flag logic for looping through repositories:
            # - first_item=True only on FIRST repo in the loop
            # - last_item=True only on LAST repo in the loop
            # - last_job_item=True only on LAST repo in the loop (when incoming last_job_item=True)
            for i, repo_info in enumerate(repos_to_queue):
                is_first_repo_in_loop = (i == 0)
                is_last_repo_in_loop = (i == len(repos_to_queue) - 1)

                # 🔑 Set flags based on position in the loop
                repo_first_item = is_first_repo_in_loop
                repo_last_item = is_last_repo_in_loop
                repo_last_job_item = is_last_repo_in_loop and last_job_item

                # 🔑 Extract token from message
                token = message.get('token') if message else None

                self.queue_manager.publish_embedding_job(
                    tenant_id=tenant_id,
                    table_name='repositories',
                    external_id=repo_info['external_id'],
                    job_id=job_id,
                    step_type='github_repositories',
                    integration_id=integration_id,
                    provider=provider,
                    last_sync_date=last_sync_date,
                    first_item=repo_first_item,
                    last_item=repo_last_item,
                    last_job_item=repo_last_job_item,
                    token=token  # 🔑 Include token in message
                )

                logger.debug(f"Queued repo {repo_info['full_name']} for embedding (first={repo_first_item}, last={repo_last_item}, job_end={repo_last_job_item})")

            # ✅ Mark raw data as completed after all repos are queued
            update_query = text("""
                UPDATE raw_extraction_data
                SET status = 'completed',
                    last_updated_at = NOW(),
                    error_details = NULL
                WHERE id = :raw_data_id
            """)
            with database.get_write_session_context() as db:
                db.execute(update_query, {'raw_data_id': raw_data_id})
                db.commit()

            logger.info(f"Processed {len(repos_to_queue)} repositories - marked raw_data_id={raw_data_id} as completed")

            # Send WebSocket status: transform worker finished (on last_item)
            if job_id and last_item:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "finished", "github_repositories"))
                finally:
                    loop.close()

            # 🔑 CRITICAL: Queue next extraction step (github_prs_commits_reviews_comments) after all repos are processed
            # This triggers Step 2 of the 2-step GitHub job
            # Extract repos from the ORIGINAL PAYLOAD (not from database) - these are already filtered by date range
            if job_id and last_item:
                logger.info(f"🔀 [GITHUB] Step 1 complete - Queuing Step 2: github_prs_commits_reviews_comments extraction")

                # 🔑 Get last_sync_date from message to pass to PR extraction
                pr_last_sync_date = message.get('last_sync_date') if message else None
                logger.info(f"📅 Passing last_sync_date to PR extraction: {pr_last_sync_date}")

                # 🔑 Get first_item flag from incoming message to pass to first PR extraction
                incoming_first_item = message.get('first_item', False) if message else False
                logger.info(f"📋 Incoming first_item flag: {incoming_first_item}")

                # 🔑 Get token from message to pass to PR extraction
                token = message.get('token') if message else None
                logger.info(f"🔑 Passing token to PR extraction: {token}")

                # Extract repositories from the original batch payload
                repos_from_payload = raw_batch_data.get('repositories', [])

                if repos_from_payload:
                    logger.info(f"📦 Queuing PR extraction for {len(repos_from_payload)} repositories from payload")

                    # Queue PR extraction for each repository from the original payload
                    for i, repo_data in enumerate(repos_from_payload):
                        # Get repo info from the payload
                        repo_id = repo_data.get('id')  # GitHub API ID
                        repo_name = repo_data.get('name')
                        repo_owner = repo_data.get('owner', {}).get('login') if isinstance(repo_data.get('owner'), dict) else repo_data.get('owner')
                        full_name = repo_data.get('full_name')

                        # Query database to get internal repository ID for this external_id
                        with database.get_read_session_context() as db:
                            repo_query = text("""
                                SELECT id FROM repositories
                                WHERE tenant_id = :tenant_id AND integration_id = :integration_id
                                  AND external_id = :external_id AND active = true
                                LIMIT 1
                            """)
                            repo_result = db.execute(repo_query, {
                                'tenant_id': tenant_id,
                                'integration_id': integration_id,
                                'external_id': str(repo_id)
                            }).fetchone()

                        if repo_result:
                            internal_repo_id = repo_result[0]
                            is_first_repo = (i == 0)
                            is_last_repo = (i == len(repos_from_payload) - 1)

                            # 🔑 first_item=True ONLY on first repo AND if incoming message had first_item=True
                            pr_first_item = is_first_repo and incoming_first_item

                            self.queue_manager.publish_extraction_job(
                                tenant_id=tenant_id,
                                integration_id=integration_id,
                                extraction_type='github_prs_commits_reviews_comments',
                                extraction_data={
                                    'repository_id': internal_repo_id,
                                    'owner': repo_owner,
                                    'repo_name': repo_name,
                                    'full_name': full_name,
                                    'pr_cursor': None  # Start from first page
                                },
                                job_id=job_id,
                                provider='github',
                                last_sync_date=pr_last_sync_date,  # 🔑 Pass from repository extraction
                                first_item=pr_first_item,  # 🔑 True only on first repo AND if incoming had first_item=True
                                last_item=is_last_repo,
                                last_job_item=False,  # 🔑 Never set to True here - completion message sent from PR extraction
                                last_repo=is_last_repo,  # 🔑 Signal to Step 2 that this is the last repository
                                last_pr=is_last_repo,  # 🔑 Signal to Step 2 that this is the last PR (will be set properly in extraction)
                                token=token  # 🔑 Include token in message
                            )

                            logger.debug(f"Queued PR extraction for repo {full_name} (first={is_first_repo}, last={is_last_repo})")
                        else:
                            logger.warning(f"Repository with external_id {repo_id} not found in database")
                else:
                    logger.warning(f"No repositories found in payload for tenant {tenant_id}, integration {integration_id}")

            logger.info(f"✅ [GITHUB] Processed {len(repositories)} repositories and queued for embedding")
            return True

        except Exception as e:
            logger.error(f"❌ [GITHUB] Error processing repositories: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    def _process_github_prs(
        self, raw_data_id: int, tenant_id: int, integration_id: int,
        job_id: int = None, message: Dict[str, Any] = None
    ) -> bool:
        """
        Process GitHub PR data with nested commits, reviews, comments.

        Handles PR+nested data (complete or partial nested data).

        Flow:
        - Insert PR + all nested data from pr_data object
        - Queue to embedding only if all nested data complete (no pending nested pagination)

        Args:
            raw_data_id: ID of raw extraction data
            tenant_id: Tenant ID
            integration_id: Integration ID
            job_id: ETL job ID
            message: Original message with flags and metadata

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            # ✅ Send transform worker "running" status when first_item=True
            if message and message.get('first_item') and job_id:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "running", "github_prs"))
                    logger.info(f"✅ Transform worker marked as running for github_prs")
                finally:
                    loop.close()

            from app.core.database import get_database
            database = get_database()

            with database.get_write_session_context() as db:
                # Load raw data with external_id (repository external_id)
                raw_data_query = text("""
                    SELECT raw_data, external_id FROM raw_extraction_data WHERE id = :raw_data_id
                """)
                result = db.execute(raw_data_query, {'raw_data_id': raw_data_id}).fetchone()

                if not result:
                    logger.error(f"Raw data {raw_data_id} not found")
                    return False

                import json
                raw_json = json.loads(result[0]) if isinstance(result[0], str) else result[0]
                raw_data_external_id = result[1]  # 🔑 Repository external_id from raw_extraction_data
                pr_id = raw_json.get('pr_id')

                # 🔑 Check if this is a nested pagination message (Type 2)
                # Type 2 messages have 'nested_type' and 'data' instead of 'pr_data'
                if raw_json.get('nested_type'):
                    logger.info(f"🔄 Routing to _process_github_prs_nested for {raw_json.get('nested_type')}")
                    return self._process_github_prs_nested(raw_data_id, tenant_id, integration_id, job_id, message)

                # 🔑 Initialize entities_to_queue_after_commit (will be set if conditions met)
                entities_to_queue_after_commit = None

                # 🔑 Extract PR data from pr_data object (Type 1 message)
                pr_data = raw_json.get('pr_data')
                if not pr_data:
                    logger.error(f"No pr_data found in raw_json for raw_data_id={raw_data_id}")
                    return False

                logger.info(f"📝 [TYPE 1] Processing PR data for PR {pr_id}")

                # Extract nested data from pr_data object
                pr_commits = pr_data.get('commits', {}).get('nodes', [])
                pr_reviews = pr_data.get('reviews', {}).get('nodes', [])
                pr_comments = pr_data.get('comments', {}).get('nodes', [])
                pr_review_threads = pr_data.get('reviewThreads', {}).get('nodes', [])

                # Check if there are more pages for any nested data
                has_pending_nested = (
                    pr_data.get('commits', {}).get('pageInfo', {}).get('hasNextPage', False) or
                    pr_data.get('reviews', {}).get('pageInfo', {}).get('hasNextPage', False) or
                    pr_data.get('comments', {}).get('pageInfo', {}).get('hasNextPage', False) or
                    pr_data.get('reviewThreads', {}).get('pageInfo', {}).get('hasNextPage', False)
                )

                logger.info(f"  PR has {len(pr_commits)} commits, {len(pr_reviews)} reviews, {len(pr_comments)} comments, {len(pr_review_threads)} review threads")
                logger.info(f"  Has pending nested data: {has_pending_nested}")

                # 🔑 Extract repository_id from raw_json (stored during extraction)
                repository_id = raw_json.get('repository_id')
                if not repository_id:
                    logger.error(f"Repository ID not found in raw_data for PR {pr_id}")
                    return False

                # Insert PR data
                pr_db_id = self._insert_pr(db, pr_data, tenant_id, integration_id, repository_id, raw_data_external_id)
                if not pr_db_id:
                    logger.error(f"Failed to insert PR {pr_id}")
                    return False

                # Insert nested data
                if pr_commits:
                    self._insert_commits(db, pr_commits, pr_db_id, tenant_id, integration_id)
                if pr_reviews:
                    self._insert_reviews(db, pr_reviews, pr_db_id, tenant_id, integration_id)
                if pr_comments:
                    self._insert_comments(db, pr_comments, pr_db_id, tenant_id, integration_id)
                if pr_review_threads:
                    self._insert_review_threads(db, pr_review_threads, pr_db_id, tenant_id, integration_id)

                logger.info(f"✅ Inserted PR {pr_id} with nested data")

                # 🔑 ALWAYS queue entities to embedding, regardless of first_item/last_item flags
                # Those flags are ONLY for WebSocket status updates and job completion tracking
                # Queue all entities: PR + all nested entities from this message
                entities_to_queue_after_commit = [
                    {'table_name': 'prs', 'external_id': pr_data['id']}
                ]

                # Add commits (use commit.oid as external_id, same as _insert_commits)
                for commit_data in pr_commits:
                    commit_external_id = commit_data.get('commit', {}).get('oid')
                    if commit_external_id:
                        logger.debug(f"  Queuing commit {commit_external_id} to embedding")
                        entities_to_queue_after_commit.append({'table_name': 'prs_commits', 'external_id': commit_external_id})
                    else:
                        logger.warning(f"  ⚠️ Commit has no oid: {commit_data}")

                # Add reviews (already a list from extraction)
                for review_data in pr_reviews:
                    if review_data.get('id'):
                        review_id = review_data['id']
                        logger.debug(f"  Queuing review {review_id} to embedding")
                        entities_to_queue_after_commit.append({'table_name': 'prs_reviews', 'external_id': review_id})

                # Add comments (already a list from extraction)
                for comment_data in pr_comments:
                    if comment_data.get('id'):
                        entities_to_queue_after_commit.append({'table_name': 'prs_comments', 'external_id': comment_data['id']})

                # Add review threads (stored as comments in prs_comments table)
                for thread_data in pr_review_threads:
                    # Review thread comments are nested in the thread object
                    for comment_data in thread_data.get('comments', {}).get('nodes', []):
                        if comment_data.get('id'):
                            entities_to_queue_after_commit.append({'table_name': 'prs_comments', 'external_id': comment_data['id']})

                logger.info(f"📤 Queuing {len(entities_to_queue_after_commit)} entities for PR {pr_id} to embedding")

                # ✅ Mark raw data as completed
                update_query = text("""
                    UPDATE raw_extraction_data
                    SET status = 'completed',
                        last_updated_at = NOW(),
                        error_details = NULL
                    WHERE id = :raw_data_id
                """)
                db.execute(update_query, {'raw_data_id': raw_data_id})

                # ✅ Send transform worker "finished" status when last_item=True
                if message and message.get('last_item') and job_id:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "finished", "github_prs"))
                        logger.info(f"✅ Transform worker marked as finished for github_prs")
                    finally:
                        loop.close()

                db.commit()
                logger.info(f"✅ [GITHUB] Processed PR data and marked raw_data_id={raw_data_id} as completed")

                # 🔑 Queue to embedding AFTER commit so entities are visible in database
                if entities_to_queue_after_commit:
                    last_item_flag = message.get('last_item', False) if message else False
                    last_job_item_flag = message.get('last_job_item', False) if message else False
                    token = message.get('token') if message else None  # 🔑 Extract token from message

                    self._queue_github_nested_entities_for_embedding(
                        tenant_id=tenant_id,
                        pr_external_id=pr_data['id'],
                        job_id=job_id,
                        integration_id=integration_id,
                        provider=message.get('provider', 'github') if message else 'github',
                        first_item=message.get('first_item', False) if message else False,
                        last_item=last_item_flag,  # 🔑 Use actual flag from message
                        last_job_item=last_job_item_flag,  # 🔑 Only True if this is the last message in the entire job
                        message=message,
                        entities_to_queue=entities_to_queue_after_commit,  # 🔑 Pass list of entities with external IDs
                        token=token  # 🔑 Forward token to embedding
                    )

                    # ✅ Send transform worker "finished" status when last_item=True
                    if last_item_flag and job_id:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(self._send_worker_status("transform", tenant_id, job_id, "finished", "github_prs_commits_reviews_comments"))
                            logger.info(f"✅ Transform worker marked as finished for github_prs_commits_reviews_comments")
                        finally:
                            loop.close()

                return True

        except Exception as e:
            logger.error(f"❌ [GITHUB] Error processing github_prs: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    def _process_github_prs_nested(
        self, raw_data_id: int, tenant_id: int, integration_id: int,
        job_id: int = None, message: Dict[str, Any] = None
    ) -> bool:
        """
        Process GitHub nested data (commits, reviews, comments, review threads) for a PR.

        Handles nested data continuation when a PR has more pages of nested data.

        Flow:
        - Insert only nested data for the specified nested_type
        - Queue to embedding only if this is the last page of nested data (has_more=false)

        Args:
            raw_data_id: ID of raw extraction data
            tenant_id: Tenant ID
            integration_id: Integration ID
            job_id: ETL job ID
            message: Original message with flags and metadata

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            from app.core.database import get_database
            database = get_database()

            with database.get_write_session_context() as db:
                # Load raw data
                raw_data_query = text("""
                    SELECT raw_data FROM raw_extraction_data WHERE id = :raw_data_id
                """)
                result = db.execute(raw_data_query, {'raw_data_id': raw_data_id}).fetchone()

                if not result:
                    logger.error(f"Raw data {raw_data_id} not found")
                    return False

                import json
                raw_json = json.loads(result[0]) if isinstance(result[0], str) else result[0]
                pr_id = raw_json.get('pr_id')
                nested_type = raw_json.get('nested_type')

                logger.info(f"📝 [NESTED] Processing {nested_type} for PR {pr_id}")

                # Lookup PR by external_id
                pr_lookup_query = text("""
                    SELECT id FROM prs WHERE external_id = :external_id AND tenant_id = :tenant_id
                """)
                pr_result = db.execute(pr_lookup_query, {
                    'external_id': pr_id,
                    'tenant_id': tenant_id
                }).fetchone()

                if not pr_result:
                    logger.warning(f"PR {pr_id} not found in database")
                    return False

                pr_db_id = pr_result[0]

                # Insert nested data based on type
                nested_data = raw_json.get('data', [])
                if nested_type == 'commits':
                    self._insert_commits(db, nested_data, pr_db_id, tenant_id, integration_id)
                elif nested_type == 'reviews':
                    self._insert_reviews(db, nested_data, pr_db_id, tenant_id, integration_id)
                elif nested_type == 'comments':
                    self._insert_comments(db, nested_data, pr_db_id, tenant_id, integration_id)
                elif nested_type == 'review_threads':
                    self._insert_review_threads(db, nested_data, pr_db_id, tenant_id, integration_id)

                logger.info(f"✅ Inserted {len(nested_data)} {nested_type} for PR {pr_id}")

                # Mark raw data as completed
                update_query = text("""
                    UPDATE raw_extraction_data
                    SET status = 'completed',
                        last_updated_at = NOW(),
                        error_details = NULL
                    WHERE id = :raw_data_id
                """)
                db.execute(update_query, {'raw_data_id': raw_data_id})

                # 🔑 ALWAYS queue nested entities to embedding, regardless of pagination
                # first_item/last_item flags are ONLY for WebSocket status updates
                # Queue every page of nested data as it arrives

                logger.info(f"📤 Queuing nested entities for PR {pr_id} to embedding ({nested_type})")

                # 🔑 Build list of nested entities to queue
                entities_to_queue = []

                # Map nested type to table name
                table_name_map = {
                    'commits': 'prs_commits',
                    'reviews': 'prs_reviews',
                    'comments': 'prs_comments',
                    'review_threads': 'prs_comments'  # Review threads are stored as comments
                }

                table_name = table_name_map.get(nested_type)
                if table_name:
                    if nested_type == 'review_threads':
                        # For review threads, extract comment IDs from inside each thread
                        for thread_data in nested_data:
                            for comment_data in thread_data.get('comments', {}).get('nodes', []):
                                comment_external_id = comment_data.get('id')
                                if comment_external_id:
                                    entities_to_queue.append({'table_name': table_name, 'external_id': comment_external_id})
                    else:
                        # For commits, reviews, comments - extract directly from data array
                        for entity_data in nested_data:
                            if nested_type == 'commits':
                                external_id = entity_data.get('commit', {}).get('oid')
                            else:
                                external_id = entity_data.get('id')

                            if external_id:
                                entities_to_queue.append({'table_name': table_name, 'external_id': external_id})

                db.commit()
                logger.info(f"✅ [GITHUB] Processed nested {nested_type} data and marked raw_data_id={raw_data_id} as completed")

                # 🔑 Queue to embedding AFTER commit so entities are visible in database
                if entities_to_queue:
                    token = message.get('token') if message else None  # 🔑 Extract token from message
                    self._queue_github_nested_entities_for_embedding(
                        tenant_id=tenant_id,
                        pr_external_id=pr_id,
                        job_id=job_id,
                        integration_id=integration_id,
                        provider=message.get('provider', 'github') if message else 'github',
                        first_item=message.get('first_item', False) if message else False,
                        last_item=message.get('last_item', False) if message else False,  # 🔑 Use actual flag from message
                        last_job_item=message.get('last_job_item', False) if message else False,
                        message=message,
                        entities_to_queue=entities_to_queue,
                        token=token  # 🔑 Forward token to embedding
                    )

                return True

        except Exception as e:
            logger.error(f"❌ [GITHUB] Error processing github_prs_nested: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    def _insert_pr(self, db, pr_data: dict, tenant_id: int, integration_id: int, repository_id: int = None, repo_external_id: str = None) -> int:
        """
        Insert or update a PR in the prs table.

        Args:
            db: Database session
            pr_data: PR data from GraphQL response (includes nested commits, reviews, comments, reviewThreads)
            tenant_id: Tenant ID
            integration_id: Integration ID
            repository_id: Database ID of the repository (from raw_data)
            repo_external_id: External ID of the repository (from raw_extraction_data.external_id)

        Returns:
            PR database ID if successful, None otherwise
        """
        try:
            from app.core.utils import DateTimeHelper
            from sqlalchemy import text

            pr_id = pr_data.get('id')
            if not pr_id:
                logger.error(f"PR data missing 'id' field")
                return None

            logger.info(f"🔍 Inserting PR {pr_id}")

            # Extract nested data from pr_data object
            pr_commits = pr_data.get('commits', {}).get('nodes', [])
            pr_reviews = pr_data.get('reviews', {}).get('nodes', [])
            pr_comments = pr_data.get('comments', {}).get('nodes', [])
            pr_review_threads = pr_data.get('reviewThreads', {}).get('nodes', [])

            # Calculate PR metrics from GraphQL data
            metrics = self._calculate_pr_metrics(pr_data, pr_commits, pr_reviews, pr_comments, pr_review_threads)
            logger.info(f"📊 Calculated PR metrics: commit_count={metrics['commit_count']}, reviewers={metrics['reviewers']}, rework_commits={metrics['rework_commit_count']}")

            # 🔑 Use repository_id from raw_data (passed as parameter)
            if not repository_id:
                logger.error(f"Repository ID not provided for PR {pr_id}")
                return None

            logger.info(f"  Using repository_id={repository_id} from raw_data")

            # Build PR data for insertion
            transformed_pr = {
                'external_id': pr_data['id'],
                'external_repo_id': repo_external_id,
                'number': pr_data.get('number'),
                'name': pr_data.get('title'),
                'body': pr_data.get('body'),
                'status': pr_data.get('state'),
                'pr_created_at': self._parse_datetime(pr_data.get('createdAt')),
                'pr_updated_at': self._parse_datetime(pr_data.get('updatedAt')),
                'closed_at': self._parse_datetime(pr_data.get('closedAt')),
                'merged_at': self._parse_datetime(pr_data.get('mergedAt')),
                'user_name': pr_data.get('author', {}).get('login'),
                'repository_id': repository_id,  # 🔑 Looked up from database
                'source': metrics['source'],
                'destination': metrics['destination'],
                'commit_count': metrics['commit_count'],
                'additions': metrics['additions'],
                'deletions': metrics['deletions'],
                'changed_files': metrics['changed_files'],
                'reviewers': metrics['reviewers'],
                'first_review_at': metrics['first_review_at'],
                'rework_commit_count': metrics['rework_commit_count'],
                'review_cycles': metrics['review_cycles'],
                'discussion_comment_count': metrics['discussion_comment_count'],
                'review_comment_count': metrics['review_comment_count'],
                'integration_id': integration_id,
                'tenant_id': tenant_id,
                'active': True,
                'last_updated_at': DateTimeHelper.now_default()
            }

            # Upsert PR
            upsert_query = text("""
                INSERT INTO prs (
                    external_id, external_repo_id, number, name, body, status, pr_created_at, pr_updated_at,
                    closed_at, merged_at, user_name, repository_id, source, destination, commit_count, additions,
                    deletions, changed_files, reviewers, first_review_at, rework_commit_count, review_cycles,
                    discussion_comment_count, review_comment_count, integration_id, tenant_id, active, last_updated_at
                ) VALUES (
                    :external_id, :external_repo_id, :number, :name, :body, :status, :pr_created_at, :pr_updated_at,
                    :closed_at, :merged_at, :user_name, :repository_id, :source, :destination, :commit_count, :additions,
                    :deletions, :changed_files, :reviewers, :first_review_at, :rework_commit_count, :review_cycles,
                    :discussion_comment_count, :review_comment_count, :integration_id, :tenant_id, :active, :last_updated_at
                )
                ON CONFLICT (external_id, tenant_id)
                DO UPDATE SET
                    external_repo_id = EXCLUDED.external_repo_id,
                    name = EXCLUDED.name,
                    body = EXCLUDED.body,
                    status = EXCLUDED.status,
                    pr_updated_at = EXCLUDED.pr_updated_at,
                    closed_at = EXCLUDED.closed_at,
                    merged_at = EXCLUDED.merged_at,
                    source = EXCLUDED.source,
                    destination = EXCLUDED.destination,
                    commit_count = EXCLUDED.commit_count,
                    additions = EXCLUDED.additions,
                    deletions = EXCLUDED.deletions,
                    changed_files = EXCLUDED.changed_files,
                    reviewers = EXCLUDED.reviewers,
                    first_review_at = EXCLUDED.first_review_at,
                    rework_commit_count = EXCLUDED.rework_commit_count,
                    review_cycles = EXCLUDED.review_cycles,
                    discussion_comment_count = EXCLUDED.discussion_comment_count,
                    review_comment_count = EXCLUDED.review_comment_count,
                    last_updated_at = EXCLUDED.last_updated_at
                RETURNING id
            """)

            pr_result = db.execute(upsert_query, transformed_pr)
            pr_db_id = pr_result.scalar()
            logger.info(f"✅ Upserted PR {pr_id} (db_id={pr_db_id})")

            return pr_db_id

        except Exception as e:
            logger.error(f"❌ Error inserting PR: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _insert_commits(self, db, commits: list, pr_db_id: int, tenant_id: int, integration_id: int = None) -> None:
        """Insert commits for a PR"""
        if not commits:
            logger.info(f"No commits to insert for PR {pr_db_id}")
            return

        from app.core.utils import DateTimeHelper
        from sqlalchemy import text

        logger.info(f"🔍 Inserting {len(commits)} commits for PR {pr_db_id}, tenant_id={tenant_id}, integration_id={integration_id}")

        for commit_data in commits:
            try:
                commit_oid = commit_data['commit']['oid']
                logger.info(f"  ✅ Inserting commit {commit_oid} (type: {type(commit_oid).__name__})")

                insert_query = text("""
                    INSERT INTO prs_commits (
                        pr_id, external_id, author_name, author_email, authored_date,
                        committer_name, committer_email, committed_date, message,
                        integration_id, tenant_id, active, created_at, last_updated_at
                    ) VALUES (
                        :pr_id, :external_id, :author_name, :author_email, :authored_date,
                        :committer_name, :committer_email, :committed_date, :message,
                        :integration_id, :tenant_id, :active, :created_at, :last_updated_at
                    )
                    ON CONFLICT (external_id, tenant_id)
                    DO UPDATE SET
                        message = EXCLUDED.message,
                        authored_date = EXCLUDED.authored_date,
                        committed_date = EXCLUDED.committed_date,
                        last_updated_at = EXCLUDED.last_updated_at
                """)

                db.execute(insert_query, {
                    'pr_id': pr_db_id,
                    'external_id': commit_oid,
                    'author_name': commit_data['commit']['author']['name'] if commit_data['commit'].get('author') else None,
                    'author_email': commit_data['commit']['author']['email'] if commit_data['commit'].get('author') else None,
                    'authored_date': self._parse_datetime(commit_data['commit']['author']['date']) if commit_data['commit'].get('author') else None,
                    'committer_name': commit_data['commit']['committer']['name'] if commit_data['commit'].get('committer') else None,
                    'committer_email': commit_data['commit']['committer']['email'] if commit_data['commit'].get('committer') else None,
                    'committed_date': self._parse_datetime(commit_data['commit']['committer']['date']) if commit_data['commit'].get('committer') else None,
                    'message': commit_data['commit']['message'],
                    'integration_id': integration_id,
                    'tenant_id': tenant_id,
                    'active': True,
                    'created_at': DateTimeHelper.now_default(),
                    'last_updated_at': DateTimeHelper.now_default()
                })
                logger.info(f"  ✅ Inserted commit {commit_oid} into prs_commits")
            except Exception as e:
                logger.error(f"❌ Error inserting commit {commit_data.get('commit', {}).get('oid', 'unknown')}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")

    def _insert_reviews(self, db, reviews: list, pr_db_id: int, tenant_id: int, integration_id: int = None) -> None:
        """Insert reviews for a PR"""
        if not reviews:
            logger.debug(f"No reviews to insert for PR {pr_db_id}")
            return

        from app.core.utils import DateTimeHelper
        from sqlalchemy import text

        logger.debug(f"Inserting {len(reviews)} reviews for PR {pr_db_id}, tenant_id={tenant_id}, integration_id={integration_id}")

        for review_data in reviews:
            try:
                review_id = review_data['id']
                logger.debug(f"  Inserting review {review_id}")

                insert_query = text("""
                    INSERT INTO prs_reviews (
                        pr_id, external_id, author_login, state, body, submitted_at,
                        integration_id, tenant_id, active, created_at, last_updated_at
                    ) VALUES (
                        :pr_id, :external_id, :author_login, :state, :body, :submitted_at,
                        :integration_id, :tenant_id, :active, :created_at, :last_updated_at
                    )
                    ON CONFLICT (external_id, tenant_id)
                    DO UPDATE SET
                        state = EXCLUDED.state,
                        body = EXCLUDED.body,
                        submitted_at = EXCLUDED.submitted_at,
                        last_updated_at = EXCLUDED.last_updated_at
                """)

                db.execute(insert_query, {
                    'pr_id': pr_db_id,
                    'external_id': review_id,
                    'author_login': review_data['author']['login'] if review_data.get('author') else None,
                    'state': review_data['state'],
                    'body': review_data.get('body'),
                    'submitted_at': self._parse_datetime(review_data['submittedAt']) if review_data.get('submittedAt') else None,
                    'integration_id': integration_id,
                    'tenant_id': tenant_id,
                    'active': True,
                    'created_at': DateTimeHelper.now_default(),
                    'last_updated_at': DateTimeHelper.now_default()
                })
                logger.debug(f"  ✅ Inserted review {review_id}")
            except Exception as e:
                logger.error(f"❌ Error inserting review {review_data.get('id', 'unknown')}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")

    def _insert_comments(self, db, comments: list, pr_db_id: int, tenant_id: int, integration_id: int = None) -> None:
        """Insert comments for a PR"""
        if not comments:
            return

        from app.core.utils import DateTimeHelper
        from sqlalchemy import text

        for comment_data in comments:
            try:
                insert_query = text("""
                    INSERT INTO prs_comments (
                        pr_id, external_id, author_login, body, created_at_github, updated_at_github,
                        integration_id, tenant_id, active, created_at, last_updated_at
                    ) VALUES (
                        :pr_id, :external_id, :author_login, :body, :created_at_github, :updated_at_github,
                        :integration_id, :tenant_id, :active, :created_at, :last_updated_at
                    )
                    ON CONFLICT (external_id, tenant_id)
                    DO UPDATE SET
                        body = EXCLUDED.body,
                        updated_at_github = EXCLUDED.updated_at_github,
                        last_updated_at = EXCLUDED.last_updated_at
                """)

                db.execute(insert_query, {
                    'pr_id': pr_db_id,
                    'external_id': comment_data['id'],
                    'author_login': comment_data['author']['login'] if comment_data.get('author') else None,
                    'body': comment_data['body'],
                    'created_at_github': self._parse_datetime(comment_data['createdAt']),
                    'updated_at_github': self._parse_datetime(comment_data['updatedAt']) if comment_data.get('updatedAt') else None,
                    'integration_id': integration_id,
                    'tenant_id': tenant_id,
                    'active': True,
                    'created_at': DateTimeHelper.now_default(),
                    'last_updated_at': DateTimeHelper.now_default()
                })
            except Exception as e:
                logger.warning(f"Error inserting comment {comment_data['id']}: {e}")

    def _insert_review_threads(self, db, threads: list, pr_db_id: int, tenant_id: int, integration_id: int = None) -> None:
        """Insert review threads and their comments for a PR"""
        if not threads:
            return

        from app.core.utils import DateTimeHelper
        from sqlalchemy import text

        for thread_data in threads:
            try:
                # Insert comments from the thread
                for comment_data in thread_data.get('comments', {}).get('nodes', []):
                    insert_query = text("""
                        INSERT INTO prs_comments (
                            pr_id, external_id, author_login, body, created_at_github, updated_at_github,
                            path, position, integration_id, tenant_id, active, created_at, last_updated_at
                        ) VALUES (
                            :pr_id, :external_id, :author_login, :body, :created_at_github, :updated_at_github,
                            :path, :position, :integration_id, :tenant_id, :active, :created_at, :last_updated_at
                        )
                        ON CONFLICT (external_id, tenant_id)
                        DO UPDATE SET
                            body = EXCLUDED.body,
                            updated_at_github = EXCLUDED.updated_at_github,
                            last_updated_at = EXCLUDED.last_updated_at
                    """)

                    db.execute(insert_query, {
                        'pr_id': pr_db_id,
                        'external_id': comment_data['id'],
                        'author_login': comment_data['author']['login'] if comment_data.get('author') else None,
                        'body': comment_data['body'],
                        'created_at_github': self._parse_datetime(comment_data['createdAt']),
                        'updated_at_github': self._parse_datetime(comment_data['updatedAt']) if comment_data.get('updatedAt') else None,
                        'path': comment_data.get('path'),
                        'position': comment_data.get('position'),
                        'integration_id': integration_id,
                        'tenant_id': tenant_id,
                        'active': True,
                        'created_at': DateTimeHelper.now_default(),
                        'last_updated_at': DateTimeHelper.now_default()
                    })
            except Exception as e:
                logger.warning(f"Error inserting review thread comment: {e}")

    def _queue_github_nested_entities_for_embedding(
        self,
        tenant_id: int,
        pr_external_id: str,
        job_id: int,
        integration_id: int,
        provider: str,
        first_item: bool = False,
        last_item: bool = False,
        last_job_item: bool = False,
        message: Dict[str, Any] = None,
        entities_to_queue: List[Dict[str, Any]] = None,
        token: str = None  # 🔑 Job execution token
    ) -> None:
        """
        Queue GitHub entities for embedding using individual entity messages.

        This queues individual PR, commits, reviews, and comments with their external IDs.
        Simple message structure: just pass external_id, embedding worker queries database.

        Args:
            tenant_id: Tenant ID
            pr_external_id: PR external ID
            job_id: ETL job ID
            integration_id: Integration ID
            provider: Provider name (github)
            first_item: Whether this is the first item in the step
            last_item: Whether this is the last item in the step
            last_job_item: Whether this is the last item in the entire job
            message: Original message (for provider/last_sync_date)
            entities_to_queue: List of dicts with 'table_name' and 'external_id'
        """
        try:
            if not entities_to_queue:
                logger.warning(f"⚠️ No entities provided for queuing GitHub entities")
                return

            # 🔑 Extract both dates from message
            last_sync_date = message.get('last_sync_date') if message else None  # old_last_sync_date (for filtering)
            new_last_sync_date = message.get('new_last_sync_date') if message else None  # extraction end date (for job completion)

            logger.info(f"📤 Queuing {len(entities_to_queue)} GitHub entities for embedding (first_item={first_item}, last_item={last_item}, last_job_item={last_job_item})")

            for i, entity in enumerate(entities_to_queue):
                table_name = entity.get('table_name')
                external_id = entity.get('external_id')

                if not table_name or not external_id:
                    logger.warning(f"⚠️ Skipping entity with missing table_name or external_id: {entity}")
                    continue

                is_last = (i == len(entities_to_queue) - 1)
                entity_first_item = first_item and (i == 0)
                entity_last_item = is_last and last_item
                entity_last_job_item = is_last and last_job_item

                logger.debug(f"  Entity {i}/{len(entities_to_queue)}: {table_name} {external_id} (first={entity_first_item}, last={entity_last_item}, last_job={entity_last_job_item})")

                self.queue_manager.publish_embedding_job(
                    tenant_id=tenant_id,
                    table_name=table_name,
                    external_id=str(external_id),
                    job_id=job_id,
                    integration_id=integration_id,
                    provider=provider,
                    last_sync_date=last_sync_date,  # 🔑 Used for filtering (old_last_sync_date)
                    new_last_sync_date=new_last_sync_date,  # 🔑 Used for job completion (extraction end date)
                    first_item=entity_first_item,  # Only first entity has first_item=true
                    last_item=entity_last_item,  # Only last entity has last_item=true
                    last_job_item=entity_last_job_item,  # Only last entity signals job completion
                    step_type='github_prs_commits_reviews_comments',  # 🔑 ETL step name for status tracking
                    token=token  # 🔑 Include token in message
                )

            logger.info(f"📤 Queued {len(entities_to_queue)} GitHub entities for embedding")

        except Exception as e:
            logger.error(f"❌ Error queuing GitHub nested entities for embedding: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
