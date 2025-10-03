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
    Manages all background queue workers.
    
    Provides centralized control for starting, stopping, and monitoring
    queue workers that process ETL data transformations.
    """
    
    def __init__(self):
        """Initialize worker manager."""
        self.workers: Dict[str, object] = {}
        self.worker_threads: Dict[str, threading.Thread] = {}
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.running = False
        
        # Initialize workers
        self.workers['transform'] = TransformWorker()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("WorkerManager initialized")
    
    def start_all_workers(self):
        """Start all registered workers in separate threads."""
        if self.running:
            logger.warning("Workers are already running")
            return
        
        logger.info("Starting all queue workers...")
        self.running = True
        
        # Setup queues first
        try:
            queue_manager = QueueManager()
            queue_manager.setup_queues()
            logger.info("Queue topology setup complete")
        except Exception as e:
            logger.error(f"Failed to setup queues: {e}")
            return False
        
        # Start each worker in its own thread
        for worker_name, worker in self.workers.items():
            try:
                thread = threading.Thread(
                    target=self._run_worker,
                    args=(worker_name, worker),
                    daemon=True,
                    name=f"Worker-{worker_name}"
                )
                thread.start()
                self.worker_threads[worker_name] = thread
                logger.info(f"Started {worker_name} worker in thread {thread.name}")
            except Exception as e:
                logger.error(f"Failed to start {worker_name} worker: {e}")
        
        logger.info(f"Started {len(self.worker_threads)} workers")
        return True
    
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
        
        self.worker_threads.clear()
        logger.info("All workers stopped")
    
    def get_worker_status(self) -> Dict[str, Dict]:
        """Get status of all workers."""
        status = {
            'running': self.running,
            'workers': {}
        }
        
        for worker_name, worker in self.workers.items():
            thread = self.worker_threads.get(worker_name)
            status['workers'][worker_name] = {
                'worker_running': getattr(worker, 'running', False),
                'thread_alive': thread.is_alive() if thread else False,
                'thread_name': thread.name if thread else None
            }
        
        return status
    
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
        sys.exit(0)


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
