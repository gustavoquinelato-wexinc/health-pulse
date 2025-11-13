"""
Worker Status Manager - Handles WebSocket status updates for ETL workers.

This class provides a reusable component for sending worker status updates
without requiring inheritance from BaseWorker. It can be injected into any
worker class that needs to send status updates.
"""

from sqlalchemy import text
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class WorkerStatusManager:
    """
    Manages WebSocket status updates for ETL workers.

    This class can be composed into any worker (extraction, transform, embedding)
    to provide status update functionality without inheritance.

    Provides two main functions:
    1. send_worker_status() - Update individual step status (extraction/transform/embedding)
    2. complete_etl_job() - Mark entire job as FINISHED with last_sync_date update
    """

    def __init__(self):
        """Initialize the worker status manager."""
        from app.core.database import get_database
        self.database = get_database()
    
    async def send_worker_status(self, step: str, tenant_id: int, job_id: int, status: str, step_type: str = None):
        """
        Send WebSocket status update for ETL job step.

        Args:
            step: ETL step name (extraction, transform, embedding)
            tenant_id: Tenant ID
            job_id: Job ID
            status: Status to send (running, finished, failed)
            step_type: Optional step type for logging (e.g., 'github_repositories')
        """
        try:
            # 🔑 UPDATE database status FIRST, then send WebSocket
            
            # Use write session to update the database
            with self.database.get_write_session_context() as write_session:
                if step_type:
                    # Update specific step status (e.g., github_repositories extraction = running)
                    # Build SQL with all values embedded to avoid parameter binding issues
                    from app.core.utils import DateTimeHelper
                    now = DateTimeHelper.now_default()

                    # Build the SQL query with all values embedded
                    sql = f"""
                        UPDATE etl_jobs
                        SET status = jsonb_set(status, ARRAY['steps', '{step_type}', '{step}'], '"{status}"'::jsonb),
                            last_updated_at = '{now.isoformat()}'::timestamp
                        WHERE id = {job_id}
                    """
                    update_query = text(sql)
                    write_session.execute(update_query)
                    write_session.commit()
                    logger.info(f"📝 Updated database: job {job_id}, step {step_type}, {step} = {status}")
                else:
                    logger.warning(f"⚠️ No step_type provided for job {job_id}, skipping database update")
            
            # Now read the updated status and send via WebSocket
            with self.database.get_read_session_context() as read_session:
                result = read_session.execute(
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
                    logger.info(f"✅ WebSocket status '{status}' sent for {step} step (job_id={job_id})")

        except Exception as e:
            logger.error(f"Error sending WebSocket status: {e}")

    async def complete_etl_job(self, job_id: int, tenant_id: int, last_sync_date: str = None):
        """
        Complete the ETL job by updating its status to FINISHED and sending WebSocket notification.

        This is a generic method that can be called by any worker (extraction, transform, embedding)
        when they need to mark the entire job as complete.

        Steps:
        1. Set overall status to FINISHED
        2. Update last_run_finished_at
        3. Update last_sync_date if provided
        4. Calculate and set next_run
        5. Clear error_message and reset retry_count
        6. Send WebSocket notification with complete job status
        7. UI will automatically reset to READY after a few seconds

        Args:
            job_id: ETL job ID
            tenant_id: Tenant ID
            last_sync_date: Last sync date to update (optional)
        """
        try:
            from datetime import timedelta
            from app.core.utils import DateTimeHelper

            with self.database.get_write_session_context() as session:
                # First, fetch job details to calculate next_run
                job_query = text("""
                    SELECT schedule_interval_minutes
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

                schedule_interval_minutes = job_result[0]

                # Calculate next_run: use schedule_interval_minutes for normal completion
                now = DateTimeHelper.now_default()
                if schedule_interval_minutes and schedule_interval_minutes > 0:
                    next_run = now + timedelta(minutes=schedule_interval_minutes)
                else:
                    # Default to 1 hour if not set
                    next_run = now + timedelta(hours=1)

                # 🔑 Calculate reset_deadline (30 seconds from now for initial countdown)
                reset_deadline = now + timedelta(seconds=30)
                reset_deadline_iso = reset_deadline.isoformat()

                # 🔑 Set status to FINISHED with reset_deadline and reset_attempt
                # The reset scheduler will automatically check and reset the job
                # Build SQL with all values embedded to avoid parameter binding issues
                if last_sync_date:
                    sql = f"""
                        UPDATE etl_jobs
                        SET status = jsonb_set(
                              jsonb_set(
                                jsonb_set(status, ARRAY['overall'], '"FINISHED"'::jsonb),
                                ARRAY['reset_deadline'], to_jsonb('{reset_deadline_iso}'::text)
                              ),
                              ARRAY['reset_attempt'], to_jsonb(0)
                            ),
                            last_run_finished_at = '{now.isoformat()}'::timestamp,
                            last_updated_at = '{now.isoformat()}'::timestamp,
                            next_run = '{next_run.isoformat()}'::timestamp,
                            last_sync_date = '{last_sync_date}'::timestamp,
                            error_message = NULL,
                            retry_count = 0
                        WHERE id = {job_id} AND tenant_id = {tenant_id}
                    """
                else:
                    sql = f"""
                        UPDATE etl_jobs
                        SET status = jsonb_set(
                              jsonb_set(
                                jsonb_set(status, ARRAY['overall'], '"FINISHED"'::jsonb),
                                ARRAY['reset_deadline'], to_jsonb('{reset_deadline_iso}'::text)
                              ),
                              ARRAY['reset_attempt'], to_jsonb(0)
                            ),
                            last_run_finished_at = '{now.isoformat()}'::timestamp,
                            last_updated_at = '{now.isoformat()}'::timestamp,
                            next_run = '{next_run.isoformat()}'::timestamp,
                            error_message = NULL,
                            retry_count = 0
                        WHERE id = {job_id} AND tenant_id = {tenant_id}
                    """

                session.execute(text(sql))
                session.commit()

                logger.info(f"🎯 [JOB COMPLETION] ETL job {job_id} marked as FINISHED")
                logger.info(f"   last_run_finished_at: {now}")
                logger.info(f"   next_run: {next_run}")
                logger.info(f"   reset_deadline: {reset_deadline} (30s countdown)")
                if last_sync_date:
                    logger.info(f"   last_sync_date: {last_sync_date}")

            # Send WebSocket notification with updated job status
            with self.database.get_read_session_context() as read_session:
                result = read_session.execute(
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
                    logger.info(f"✅ WebSocket notification sent with overall status FINISHED")
                    logger.info(f"   Reset scheduler will check and reset job automatically")

            # 🔑 Schedule the reset check task (runs in 30 seconds)
            # This is a system-level task that runs even if no users are logged in
            from app.etl.workers.job_reset_scheduler import schedule_reset_check_task
            schedule_reset_check_task(job_id, tenant_id, delay_seconds=30)
            logger.info(f"📅 Scheduled automatic reset check for job {job_id} in 30 seconds")

        except Exception as e:
            logger.error(f"❌ Error completing ETL job {job_id}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

