"""
Worker Manager for managing background queue workers.

Handles starting, stopping, and monitoring of all queue workers.
"""

import threading
import signal
import sys
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor

from .transform_worker import TransformWorker
from app.etl.queue.queue_manager import QueueManager
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class WorkerManager:
    """
    Manages all background queue workers with multi-tenant support.

    Provides centralized control for starting, stopping, and monitoring
    tenant-specific queue workers that process ETL data transformations.
    """

    def __init__(self):
        """Initialize worker manager."""
        self.workers: Dict[str, object] = {}  # worker_key -> worker_instance
        self.worker_threads: Dict[str, threading.Thread] = {}  # worker_key -> thread
        self.tenant_workers: Dict[int, Dict[str, object]] = {}  # tenant_id -> {worker_type -> worker}
        self.executor = ThreadPoolExecutor(max_workers=20)  # Increased for multi-tenant
        self.running = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("Multi-tenant WorkerManager initialized")
    
    def start_all_workers(self):
        """Start workers for all active tenants."""
        if self.running:
            logger.warning("Workers are already running")
            return False

        logger.info("Starting multi-tenant queue workers...")
        self.running = True

        # Setup queues first
        try:
            queue_manager = QueueManager()
            queue_manager.setup_queues()  # This will discover active tenants
            logger.info("Multi-tenant queue topology setup complete")
        except Exception as e:
            logger.error(f"Failed to setup queues: {e}")
            return False

        # Start workers for all active tenants
        try:
            active_tenant_ids = self._get_active_tenant_ids()
            for tenant_id in active_tenant_ids:
                self.start_tenant_workers(tenant_id)

            logger.info(f"Started workers for {len(active_tenant_ids)} tenants")
            return True
        except Exception as e:
            logger.error(f"Failed to start tenant workers: {e}")
            return False

    def start_tenant_workers(self, tenant_id: int) -> bool:
        """
        Start workers for a specific tenant.

        Args:
            tenant_id: Tenant ID to start workers for

        Returns:
            bool: True if workers started successfully
        """
        try:
            if tenant_id not in self.tenant_workers:
                self.tenant_workers[tenant_id] = {}

            # Create tenant-specific transform worker
            queue_manager = QueueManager()
            tenant_queue = queue_manager.get_tenant_queue_name(tenant_id, 'transform')

            # Ensure tenant queue exists
            queue_manager.setup_tenant_queue(tenant_id, 'transform')

            # Create worker for this tenant's queue
            worker = TransformWorker(tenant_queue)
            worker_key = f"transform_tenant_{tenant_id}"

            # Start worker thread
            thread = threading.Thread(
                target=self._run_worker,
                args=(worker_key, worker),
                daemon=True,
                name=f"Worker-{worker_key}"
            )
            thread.start()

            # Store references
            self.workers[worker_key] = worker
            self.worker_threads[worker_key] = thread
            self.tenant_workers[tenant_id]['transform'] = worker

            logger.info(f"Started transform worker for tenant {tenant_id}: {worker_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to start workers for tenant {tenant_id}: {e}")
            return False
    
    def stop_all_workers(self):
        """Stop all workers gracefully."""
        if not self.running:
            logger.warning("Workers are not running")
            return

        logger.info("Stopping all queue workers...")
        self.running = False

        # Stop each worker
        for worker_name, worker in self.workers.items():
            try:
                worker.stop()
                logger.info(f"Stopped {worker_name} worker")
            except Exception as e:
                logger.error(f"Error stopping {worker_name} worker: {e}")

        # Wait for threads to finish
        for worker_name, thread in self.worker_threads.items():
            try:
                thread.join(timeout=10)  # Wait up to 10 seconds
                if thread.is_alive():
                    logger.warning(f"Worker thread {worker_name} did not stop gracefully")
                else:
                    logger.info(f"Worker thread {worker_name} stopped")
            except Exception as e:
                logger.error(f"Error joining {worker_name} thread: {e}")

        # Clear all references
        self.worker_threads.clear()
        self.workers.clear()
        self.tenant_workers.clear()
        logger.info("All workers stopped")

    def stop_tenant_workers(self, tenant_id: int) -> bool:
        """
        Stop workers for a specific tenant.

        Args:
            tenant_id: Tenant ID to stop workers for

        Returns:
            bool: True if workers stopped successfully
        """
        try:
            if tenant_id not in self.tenant_workers:
                logger.warning(f"No workers found for tenant {tenant_id}")
                return True

            # Stop tenant-specific workers
            worker_key = f"transform_tenant_{tenant_id}"

            if worker_key in self.workers:
                # Stop the worker
                worker = self.workers[worker_key]
                worker.stop()

                # Wait for thread to finish
                if worker_key in self.worker_threads:
                    thread = self.worker_threads[worker_key]
                    thread.join(timeout=10)

                    if thread.is_alive():
                        logger.warning(f"Worker thread {worker_key} did not stop gracefully")
                    else:
                        logger.info(f"Worker thread {worker_key} stopped")

                    # Remove references
                    del self.worker_threads[worker_key]

                del self.workers[worker_key]

            # Remove tenant worker references
            del self.tenant_workers[tenant_id]

            logger.info(f"Stopped workers for tenant {tenant_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop workers for tenant {tenant_id}: {e}")
            return False
    
    def get_worker_status(self) -> Dict[str, Dict]:
        """Get status of all workers with tenant breakdown."""
        status = {
            'running': self.running,
            'worker_count': len(self.worker_threads),
            'tenant_count': len(self.tenant_workers),
            'workers': {},
            'tenants': {}
        }

        # Overall worker status
        for worker_name, worker in self.workers.items():
            thread = self.worker_threads.get(worker_name)
            status['workers'][worker_name] = {
                'worker_running': getattr(worker, 'running', False),
                'thread_alive': thread.is_alive() if thread else False,
                'thread_name': thread.name if thread else None
            }

        # Tenant-specific status
        for tenant_id, tenant_workers in self.tenant_workers.items():
            status['tenants'][tenant_id] = {
                'worker_count': len(tenant_workers),
                'workers': {}
            }

            for worker_type, worker in tenant_workers.items():
                worker_key = f"{worker_type}_tenant_{tenant_id}"
                thread = self.worker_threads.get(worker_key)
                status['tenants'][tenant_id]['workers'][worker_type] = {
                    'worker_key': worker_key,
                    'worker_running': getattr(worker, 'running', False),
                    'thread_alive': thread.is_alive() if thread else False,
                    'thread_name': thread.name if thread else None
                }

        return status

    def get_tenant_worker_status(self, tenant_id: int):
        """Get worker status for a specific tenant."""
        if tenant_id not in self.tenant_workers:
            return {
                'tenant_id': tenant_id,
                'has_workers': False,
                'workers': {},
                'worker_count': 0
            }

        tenant_workers = self.tenant_workers[tenant_id]
        status = {
            'tenant_id': tenant_id,
            'has_workers': True,
            'worker_count': len(tenant_workers),
            'workers': {}
        }

        for worker_type, worker in tenant_workers.items():
            worker_key = f"{worker_type}_tenant_{tenant_id}"
            thread = self.worker_threads.get(worker_key)
            status['workers'][worker_type] = {
                'worker_key': worker_key,
                'worker_running': getattr(worker, 'running', False),
                'thread_alive': thread.is_alive() if thread else False,
                'thread_name': thread.name if thread else None,
                'queue_name': getattr(worker, 'queue_name', None)
            }

        return status

    def _get_active_tenant_ids(self) -> list:
        """Get list of active tenant IDs from database."""
        try:
            from app.core.database import get_database
            from app.models.unified_models import Tenant

            database = get_database()
            with database.get_session() as session:
                tenants = session.query(Tenant).filter(Tenant.active == True).all()
                tenant_ids = [tenant.id for tenant in tenants]
                logger.info(f"Found {len(tenant_ids)} active tenants: {tenant_ids}")
                return tenant_ids
        except Exception as e:
            logger.error(f"Failed to get active tenant IDs: {e}")
            return [1]  # Fallback to tenant 1
    
    def restart_worker(self, worker_name: str) -> bool:
        """Restart a specific worker."""
        if worker_name not in self.workers:
            logger.error(f"Unknown worker: {worker_name}")
            return False
        
        logger.info(f"Restarting {worker_name} worker...")
        
        # Stop the worker
        worker = self.workers[worker_name]
        worker.stop()
        
        # Wait for thread to finish
        thread = self.worker_threads.get(worker_name)
        if thread:
            thread.join(timeout=10)
            if thread.is_alive():
                logger.warning(f"Worker thread {worker_name} did not stop gracefully")
        
        # Start the worker again
        try:
            new_thread = threading.Thread(
                target=self._run_worker,
                args=(worker_name, worker),
                daemon=True,
                name=f"Worker-{worker_name}-restarted"
            )
            new_thread.start()
            self.worker_threads[worker_name] = new_thread
            logger.info(f"Restarted {worker_name} worker")
            return True
        except Exception as e:
            logger.error(f"Failed to restart {worker_name} worker: {e}")
            return False
    
    def _run_worker(self, worker_name: str, worker):
        """Run a worker in a thread with error handling."""
        try:
            logger.info(f"Starting {worker_name} worker thread")
            worker.start_consuming()
        except KeyboardInterrupt:
            logger.info(f"Received shutdown signal for {worker_name} worker")
        except Exception as e:
            logger.error(f"Error in {worker_name} worker: {e}")
            if self.running:
                logger.info(f"Attempting to restart {worker_name} worker...")
                # Could implement auto-restart logic here
        finally:
            logger.info(f"{worker_name} worker thread finished")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down workers...")
        self.stop_all_workers()
        # Don't call sys.exit(0) here as it interferes with FastAPI's async lifecycle


# Global worker manager instance
_worker_manager = None


def get_worker_manager() -> WorkerManager:
    """Get the global worker manager instance."""
    global _worker_manager
    if _worker_manager is None:
        _worker_manager = WorkerManager()
    return _worker_manager


def start_workers():
    """Start all workers (convenience function)."""
    manager = get_worker_manager()
    return manager.start_all_workers()


def stop_workers():
    """Stop all workers (convenience function)."""
    manager = get_worker_manager()
    manager.stop_all_workers()


def get_workers_status():
    """Get worker status (convenience function)."""
    manager = get_worker_manager()
    return manager.get_worker_status()
