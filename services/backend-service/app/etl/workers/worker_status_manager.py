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
                    # Use string formatting for the status value to avoid parameter binding issues
                    update_query = text(f"""
                        UPDATE etl_jobs
                        SET status = jsonb_set(status, ARRAY['steps', :step_type, :step], '"{status}"'::jsonb),
                            last_updated_at = NOW()
                        WHERE id = :job_id
                    """)
                    write_session.execute(update_query, {
                        'step_type': step_type,
                        'step': step,
                        'job_id': job_id
                    })
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

