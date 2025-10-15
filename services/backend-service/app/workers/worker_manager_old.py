"""
Worker Manager for managing background queue workers.

Handles starting, stopping, and monitoring of all queue workers.
"""

import threading
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor

from .extraction_worker import ExtractionWorker
from .transform_worker import TransformWorker
from .vectorization_worker import VectorizationWorker
from app.etl.queue.queue_manager import QueueManager
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class WorkerManager:
    """
    Manages all background queue workers with SHARED WORKER POOL architecture.

    Uses tier-based shared worker pools instead of per-tenant workers:
    - free tier: 1 worker per pool (shared across all free tenants)
    - basic tier: 3 workers per pool (shared across all basic tenants)
    - premium tier: 5 workers per pool (shared across all premium tenants)
    - enterprise tier: 10 workers per pool (shared across all enterprise tenants)

    Each worker consumes from ALL tenant queues in round-robin fashion.
    """

    # Tier-based worker pool configuration
    TIER_WORKER_COUNTS = {
        'free': {'extraction': 1, 'transform': 1, 'vectorization': 1},
        'basic': {'extraction': 3, 'transform': 3, 'vectorization': 3},
        'premium': {'extraction': 5, 'transform': 5, 'vectorization': 5},
        'enterprise': {'extraction': 10, 'transform': 10, 'vectorization': 10}
    }

    def __init__(self):
        """Initialize worker manager with shared pool architecture."""
        self.workers: Dict[str, object] = {}  # worker_key -> worker_instance
        self.worker_threads: Dict[str, threading.Thread] = {}  # worker_key -> thread
        self.tier_workers: Dict[str, Dict[str, List[object]]] = {}  # tier -> {worker_type -> [workers]}
        self.executor = ThreadPoolExecutor(max_workers=100)
        self.running = False

        # Note: Signal handlers removed to avoid conflicts with FastAPI's lifespan management
        # FastAPI's lifespan context manager will handle graceful shutdown

        logger.info("WorkerManager initialized with SHARED WORKER POOL architecture")
    
    def start_all_workers(self):
        """Start shared worker pools for all tiers."""
        if self.running:
            logger.warning("Workers are already running")
            return False

        logger.info("Starting SHARED WORKER POOLS...")
        self.running = True

        # Setup queues first (creates tenant-specific queues)
        try:
            queue_manager = QueueManager()
            queue_manager.setup_queues()  # This will discover active tenants and create their queues
            logger.info("Multi-tenant queue topology setup complete")
        except Exception as e:
            logger.error(f"Failed to setup queues: {e}")
            return False

        # Start shared worker pools for each tier
        try:
            tenants_by_tier = self._get_tenants_by_tier()

            for tier, tenant_ids in tenants_by_tier.items():
                if not tenant_ids:
                    logger.info(f"No tenants in {tier} tier, skipping pool creation")
                    continue

                logger.info(f"Starting {tier} tier worker pool for {len(tenant_ids)} tenants: {tenant_ids}")
                self._start_tier_worker_pool(tier, tenant_ids)

            total_workers = sum(len(workers) for tier_workers in self.tier_workers.values() for workers in tier_workers.values())
            logger.info(f"✅ Started {total_workers} shared workers across {len(tenants_by_tier)} tiers")
            return True
        except Exception as e:
            logger.error(f"Failed to start shared worker pools: {e}")
            return False

    def start_tenant_workers(self, tenant_id: int) -> bool:
        """
        Start workers for a specific tenant with dynamic scaling based on worker_config.

        Args:
            tenant_id: Tenant ID to start workers for

        Returns:
            bool: True if workers started successfully
        """
        try:
            if tenant_id not in self.tenant_workers:
                self.tenant_workers[tenant_id] = {}

            # Get worker configuration for this tenant
            worker_counts = self._get_worker_counts(tenant_id)
            extraction_count = worker_counts['extraction_workers']
            transform_count = worker_counts['transform_workers']
            vectorization_count = worker_counts['vectorization_workers']

            logger.info(f"Starting {extraction_count} extraction + {transform_count} transform + {vectorization_count} vectorization workers for tenant {tenant_id}")

            queue_manager = QueueManager()

            # 1. Start MULTIPLE Extraction Workers
            extraction_queue = queue_manager.get_tenant_queue_name(tenant_id, 'extraction')
            queue_manager.setup_tenant_queue(tenant_id, 'extraction')

            self.tenant_workers[tenant_id]['extraction'] = []
            for worker_num in range(extraction_count):
                extraction_worker = ExtractionWorker(extraction_queue, worker_num)
                extraction_worker_key = f"extraction_tenant_{tenant_id}_worker_{worker_num}"

                extraction_thread = threading.Thread(
                    target=self._run_worker,
                    args=(extraction_worker_key, extraction_worker),
                    daemon=True,
                    name=f"Worker-{extraction_worker_key}"
                )
                extraction_thread.start()

                self.workers[extraction_worker_key] = extraction_worker
                self.worker_threads[extraction_worker_key] = extraction_thread
                self.tenant_workers[tenant_id]['extraction'].append(extraction_worker)

                logger.info(f"Started extraction worker {worker_num+1}/{extraction_count} for tenant {tenant_id}")

            # 2. Start MULTIPLE Transform Workers
            transform_queue = queue_manager.get_tenant_queue_name(tenant_id, 'transform')
            queue_manager.setup_tenant_queue(tenant_id, 'transform')

            self.tenant_workers[tenant_id]['transform'] = []
            for worker_num in range(transform_count):
                transform_worker = TransformWorker(transform_queue)
                transform_worker_key = f"transform_tenant_{tenant_id}_worker_{worker_num}"

                transform_thread = threading.Thread(
                    target=self._run_worker,
                    args=(transform_worker_key, transform_worker),
                    daemon=True,
                    name=f"Worker-{transform_worker_key}"
                )
                transform_thread.start()

                self.workers[transform_worker_key] = transform_worker
                self.worker_threads[transform_worker_key] = transform_thread
                self.tenant_workers[tenant_id]['transform'].append(transform_worker)

                logger.info(f"Started transform worker {worker_num+1}/{transform_count} for tenant {tenant_id}")

            # 3. Start MULTIPLE Vectorization Workers
            vectorization_queue = queue_manager.get_tenant_queue_name(tenant_id, 'vectorization')
            queue_manager.setup_tenant_queue(tenant_id, 'vectorization')

            self.tenant_workers[tenant_id]['vectorization'] = []
            for worker_num in range(vectorization_count):
                vectorization_worker = VectorizationWorker(tenant_id)
                vectorization_worker_key = f"vectorization_tenant_{tenant_id}_worker_{worker_num}"

                vectorization_thread = threading.Thread(
                    target=self._run_worker,
                    args=(vectorization_worker_key, vectorization_worker),
                    daemon=True,
                    name=f"Worker-{vectorization_worker_key}"
                )
                vectorization_thread.start()

                self.workers[vectorization_worker_key] = vectorization_worker
                self.worker_threads[vectorization_worker_key] = vectorization_thread
                self.tenant_workers[tenant_id]['vectorization'].append(vectorization_worker)

                logger.info(f"Started vectorization worker {worker_num+1}/{vectorization_count} for tenant {tenant_id}")

            logger.info(f"✅ Successfully started {extraction_count + transform_count + vectorization_count} workers for tenant {tenant_id}")
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
                logger.info(f"Stopping {worker_name} worker...")
                worker.stop()
                logger.info(f"Stopped {worker_name} worker")
            except Exception as e:
                logger.error(f"Error stopping {worker_name} worker: {e}")

        # Wait for threads to finish with shorter timeout for faster shutdown
        for worker_name, thread in self.worker_threads.items():
            try:
                logger.info(f"Waiting for {worker_name} thread to finish...")
                thread.join(timeout=3)  # Reduced to 3 seconds for faster shutdown
                if thread.is_alive():
                    logger.warning(f"Worker thread {worker_name} did not stop gracefully within 3 seconds")
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
        Stop all workers for a specific tenant (both transform and vectorization).

        Args:
            tenant_id: Tenant ID to stop workers for

        Returns:
            bool: True if workers stopped successfully
        """
        try:
            if tenant_id not in self.tenant_workers:
                logger.warning(f"No workers found for tenant {tenant_id}")
                return True

            # Find all worker keys for this tenant (handles multiple workers per type)
            worker_keys_to_stop = [
                key for key in self.workers.keys()
                if key.startswith(f"transform_tenant_{tenant_id}_") or
                   key.startswith(f"vectorization_tenant_{tenant_id}_")
            ]

            logger.info(f"Stopping {len(worker_keys_to_stop)} workers for tenant {tenant_id}")

            for worker_key in worker_keys_to_stop:
                if worker_key in self.workers:
                    # Stop the worker
                    worker = self.workers[worker_key]
                    worker.stop()

                    # Wait for thread to finish
                    if worker_key in self.worker_threads:
                        thread = self.worker_threads[worker_key]
                        thread.join(timeout=3)

                        if thread.is_alive():
                            logger.warning(f"Worker thread {worker_key} did not stop gracefully")
                        else:
                            logger.info(f"Worker thread {worker_key} stopped")

                        # Remove references
                        del self.worker_threads[worker_key]

                    del self.workers[worker_key]

            # Remove tenant worker references
            del self.tenant_workers[tenant_id]

            logger.info(f"✅ Stopped all workers for tenant {tenant_id}")
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
        """Get worker status for a specific tenant with multiple workers per type."""
        if tenant_id not in self.tenant_workers:
            return {
                'tenant_id': tenant_id,
                'has_workers': False,
                'workers': {},
                'worker_count': 0
            }

        tenant_workers = self.tenant_workers[tenant_id]
        total_worker_count = sum(len(workers) if isinstance(workers, list) else 1 for workers in tenant_workers.values())

        status = {
            'tenant_id': tenant_id,
            'has_workers': True,
            'worker_count': total_worker_count,
            'workers': {}
        }

        # Handle both old single-worker and new multi-worker format
        for worker_type, workers in tenant_workers.items():
            # Convert to list if single worker (backward compatibility)
            worker_list = workers if isinstance(workers, list) else [workers]

            status['workers'][worker_type] = {
                'count': len(worker_list),
                'instances': []
            }

            for idx, worker in enumerate(worker_list):
                worker_key = f"{worker_type}_tenant_{tenant_id}_worker_{idx}"
                thread = self.worker_threads.get(worker_key)

                status['workers'][worker_type]['instances'].append({
                    'worker_key': worker_key,
                    'worker_number': idx,
                    'worker_running': getattr(worker, 'running', False),
                    'thread_alive': thread.is_alive() if thread else False,
                    'thread_name': thread.name if thread else None,
                    'queue_name': getattr(worker, 'queue_name', None)
                })

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

    def _get_worker_counts(self, tenant_id: int) -> Dict[str, int]:
        """
        Get worker counts for a tenant from worker_config table.

        Args:
            tenant_id: Tenant ID

        Returns:
            Dict with extraction_workers, transform_workers and vectorization_workers counts
        """
        try:
            from app.core.database import get_database
            from app.models.unified_models import WorkerConfig
            from sqlalchemy import text

            database = get_database()
            with database.get_session() as session:
                # Try to get existing config
                config = session.query(WorkerConfig).filter(
                    WorkerConfig.tenant_id == tenant_id,
                    WorkerConfig.active == True
                ).first()

                if config:
                    logger.info(f"Worker config for tenant {tenant_id}: extraction={config.extraction_workers}, transform={config.transform_workers}, vectorization={config.vectorization_workers}")
                    return {
                        'extraction_workers': config.extraction_workers,
                        'transform_workers': config.transform_workers,
                        'vectorization_workers': config.vectorization_workers
                    }
                else:
                    # Create default config if not exists
                    logger.info(f"No worker config found for tenant {tenant_id}, creating default (1 extraction + 1 transform + 1 vectorization)")
                    insert_query = text("""
                        INSERT INTO worker_configs (tenant_id, extraction_workers, transform_workers, vectorization_workers)
                        VALUES (:tenant_id, 1, 1, 1)
                        ON CONFLICT (tenant_id) DO NOTHING
                    """)
                    session.execute(insert_query, {'tenant_id': tenant_id})
                    session.commit()

                    return {
                        'extraction_workers': 1,
                        'transform_workers': 1,
                        'vectorization_workers': 1
                    }
        except Exception as e:
            logger.error(f"Failed to get worker counts for tenant {tenant_id}: {e}")
            # Fallback to default
            return {
                'extraction_workers': 1,
                'transform_workers': 1,
                'vectorization_workers': 1
            }
    
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
