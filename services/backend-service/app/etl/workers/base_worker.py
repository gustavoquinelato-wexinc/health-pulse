"""
Base worker class for queue processing.

Provides common functionality for all queue workers including connection management,
error handling, message acknowledgment, and shared ETL communication utilities.
"""

import warnings
import json
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable
from contextlib import contextmanager
from sqlalchemy import text
from datetime import datetime

# Suppress asyncio event loop closure warnings for workers
warnings.filterwarnings("ignore", message=".*Event loop is closed.*", category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*coroutine.*was never awaited.*", category=RuntimeWarning)

from app.etl.workers.queue_manager import QueueManager
from app.etl.workers.worker_status_manager import WorkerStatusManager
from app.core.database import get_database
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class BaseWorker(ABC):
    """
    Base class for all queue workers.

    Provides common functionality:
    - RabbitMQ connection management
    - Database session management
    - Error handling and message acknowledgment
    - Graceful shutdown handling
    - Worker status updates via WorkerStatusManager
    """

    def __init__(self, queue_name: str):
        """
        Initialize base worker.

        Args:
            queue_name: Name of the queue to consume from
        """
        self.queue_name = queue_name
        self.queue_manager = QueueManager()
        self.database = get_database()
        self.status_manager = WorkerStatusManager()  # 🔑 Composition instead of inheritance
        self.running = False

        logger.info(f"Initialized {self.__class__.__name__} for queue: {queue_name}")
    
    @abstractmethod
    async def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a single message from the queue.

        Args:
            message: Message data from queue

        Returns:
            bool: True if processing succeeded, False otherwise
        """
        pass
    
    def start_consuming(self):
        """
        Start consuming messages from the queue.
        Runs indefinitely until stopped.
        """
        logger.info(f"🚀 [WORKER-DEBUG] Starting {self.__class__.__name__} consumer for queue: {self.queue_name}")
        self.running = True

        try:
            # Use polling approach for graceful shutdown
            import time
            poll_count = 0
            while self.running:
                try:
                    poll_count += 1
                    # Disabled: Log every 100 polls (about 10 seconds) - too noisy
                    # if poll_count % 100 == 0:
                    #     logger.info(f"🔄 [WORKER-DEBUG] {self.__class__.__name__} still polling queue {self.queue_name} (poll #{poll_count})")

                    # Try to get a message with timeout
                    message = self.queue_manager.get_single_message(self.queue_name, timeout=1.0)
                    if message:
                        logger.info(f"📨 [WORKER-DEBUG] {self.__class__.__name__} received message from {self.queue_name}: {message}")
                        self._handle_message(message)
                    else:
                        # No message available, sleep briefly
                        time.sleep(0.1)
                except Exception as e:
                    logger.error(f"❌ [WORKER-DEBUG] Error processing message in {self.__class__.__name__}: {e}")
                    time.sleep(1.0)  # Wait before retrying

        except KeyboardInterrupt:
            logger.info(f"Received shutdown signal for {self.__class__.__name__}")
            self.stop()
        except Exception as e:
            logger.error(f"Error in {self.__class__.__name__} consumer: {e}")
            raise

        logger.info(f"{self.__class__.__name__} consumer stopped")
    
    def stop(self):
        """Stop the worker gracefully."""
        logger.info(f"Stopping {self.__class__.__name__}")
        self.running = False
    
    def _handle_message(self, message: Dict[str, Any]):
        """
        Internal message handler with error handling and acknowledgment.

        Args:
            message: Message data from queue
        """
        try:
            logger.debug(f"Processing message: {message}")

            # Process the message asynchronously with proper event loop cleanup
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                success = loop.run_until_complete(self.process_message(message))

                # Properly shutdown async resources before closing loop
                # This gives pending tasks (like HTTP connection cleanup) time to complete
                pending = asyncio.all_tasks(loop)
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

            finally:
                # Shutdown async generators and close the loop
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    pass
                finally:
                    loop.close()

            if success:
                logger.debug(f"Message processed successfully: {message.get('type', 'unknown')}")
            else:
                # Reduce log noise - entity may have been queued before commit
                logger.debug(f"Message processing failed (entity may not exist yet): {message.get('type', 'unknown')}")

        except Exception as e:
            logger.error(f"Error processing message in {self.__class__.__name__}: {e}")
            logger.error(f"Message data: {message}")
            # Message will be requeued due to auto_ack=False
    
    @contextmanager
    def get_db_session(self):
        """
        Get a database session with automatic cleanup.

        Usage:
            with self.get_db_session() as session:
                # Use session for writes

        Note: This uses write session context. For read-only operations,
        consider using get_db_read_session() instead.
        """
        with self.database.get_write_session_context() as session:
            yield session

    @contextmanager
    def get_db_read_session(self):
        """
        Get a read-only database session with automatic cleanup.

        Usage:
            with self.get_db_read_session() as session:
                # Use session for reads only
        """
        with self.database.get_read_session_context() as session:
            yield session

    # ============ SHARED ETL COMMUNICATION UTILITIES ============

    async def _send_worker_status(self, step: str, tenant_id: int, job_id: int, status: str, step_type: str = None):
        """
        Send WebSocket status update for ETL job step.

        Delegates to WorkerStatusManager for the actual implementation.

        Args:
            step: ETL step name (extraction, transform, embedding)
            tenant_id: Tenant ID
            job_id: Job ID
            status: Status to send (running, finished, failed)
            step_type: Optional step type for logging
        """
        await self.status_manager.send_worker_status(step, tenant_id, job_id, status, step_type)

    def _update_job_status(self, job_id: int, status: str, step: str = None):
        """
        Update ETL job status in database.

        Args:
            job_id: Job ID
            status: New status (READY, RUNNING, FINISHED, FAILED)
            step: Optional step name for logging
        """
        try:
            with self.get_db_session() as session:
                # Update job status
                query = text("""
                    UPDATE etl_jobs
                    SET status = :status, last_updated_at = :now
                    WHERE id = :job_id
                """)

                session.execute(query, {
                    'status': status,
                    'job_id': job_id,
                    'now': datetime.utcnow()
                })

                session.commit()

                step_info = f" for {step}" if step else ""
                logger.info(f"Updated job {job_id} status to {status}{step_info}")

        except Exception as e:
            logger.error(f"Failed to update job status: {e}")

    def _update_worker_status(self, job_id: int, worker_type: str, status: str, step: str = None):
        """
        Update worker status in database for tracking.

        Args:
            job_id: Job ID
            worker_type: Type of worker (extraction, transform, embedding)
            status: Status (running, finished, failed)
            step: Optional step name
        """
        try:
            with self.get_db_session() as session:
                # Update worker status in etl_jobs table
                status_field = f"{worker_type}_status"
                query = text(f"""
                    UPDATE etl_jobs
                    SET {status_field} = :status, last_updated_at = :now
                    WHERE id = :job_id
                """)

                session.execute(query, {
                    'status': status,
                    'job_id': job_id,
                    'now': datetime.utcnow()
                })

                session.commit()

                step_info = f" for {step}" if step else ""
                logger.info(f"Updated {worker_type} worker status to {status} for job {job_id}{step_info}")

        except Exception as e:
            logger.error(f"Failed to update worker status in database: {e}")
