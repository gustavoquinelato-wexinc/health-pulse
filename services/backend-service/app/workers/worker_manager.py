"""
Worker Manager for managing background queue workers with SHARED POOL architecture.

Uses tier-based shared worker pools instead of per-tenant workers for better scalability.
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
    
    Each worker consumes from ALL tenant queues in its tier in round-robin fashion.
    This provides:
    - Constant resource usage regardless of tenant count
    - Better worker utilization (workers always busy)
    - Fair resource sharing across tenants
    - Scalability to thousands of tenants
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

        logger.info("WorkerManager initialized with SHARED WORKER POOL architecture")

    def start_all_workers(self):
        """Start shared worker pools for all tiers."""
        if self.running:
            logger.warning("Workers are already running")
            return False

        logger.info("🚀 Starting SHARED WORKER POOLS...")
        self.running = True

        # Setup queues first (creates tenant-specific queues)
        try:
            queue_manager = QueueManager()
            queue_manager.setup_queues()  # This will discover active tenants and create their queues
            logger.info("✅ Multi-tenant queue topology setup complete")
        except Exception as e:
            logger.error(f"❌ Failed to setup queues: {e}")
            return False

        # Start shared worker pools for each tier
        try:
            tenants_by_tier = self._get_tenants_by_tier()
            
            for tier, tenant_ids in tenants_by_tier.items():
                if not tenant_ids:
                    logger.info(f"⏭️ No tenants in {tier} tier, skipping pool creation")
                    continue
                    
                logger.info(f"🔧 Starting {tier} tier worker pool for {len(tenant_ids)} tenants: {tenant_ids}")
                self._start_tier_worker_pool(tier, tenant_ids)

            total_workers = sum(len(workers) for tier_workers in self.tier_workers.values() for workers in tier_workers.values())
            logger.info(f"✅ Started {total_workers} shared workers across {len(tenants_by_tier)} tiers")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start shared worker pools: {e}")
            return False

    def _start_tier_worker_pool(self, tier: str, tenant_ids: List[int]) -> bool:
        """
        Start shared worker pool for a specific tier.
        
        Workers in this pool will consume from ALL tenant queues in this tier (round-robin).

        Args:
            tier: Tier name (free, basic, premium, enterprise)
            tenant_ids: List of tenant IDs in this tier

        Returns:
            bool: True if workers started successfully
        """
        try:
            if tier not in self.tier_workers:
                self.tier_workers[tier] = {}

            # Get worker counts for this tier
            worker_counts = self.TIER_WORKER_COUNTS.get(tier, self.TIER_WORKER_COUNTS['free'])
            extraction_count = worker_counts['extraction']
            transform_count = worker_counts['transform']
            vectorization_count = worker_counts['vectorization']

            logger.info(f"   📊 {tier} tier: {extraction_count} extraction + {transform_count} transform + {vectorization_count} vectorization workers")

            queue_manager = QueueManager()

            # 1. Start Extraction Workers (consume from tier-based queue)
            self.tier_workers[tier]['extraction'] = []
            tier_extraction_queue = queue_manager.get_tier_queue_name(tier, 'extraction')

            for worker_num in range(extraction_count):
                extraction_worker = ExtractionWorker(
                    queue_name=tier_extraction_queue,
                    worker_number=worker_num,
                    tenant_ids=None  # Not needed for tier-based queues
                )
                extraction_worker_key = f"extraction_{tier}_worker_{worker_num}"

                extraction_thread = threading.Thread(
                    target=self._run_worker,
                    args=(extraction_worker_key, extraction_worker),
                    daemon=True,
                    name=f"Worker-{extraction_worker_key}"
                )
                extraction_thread.start()

                self.workers[extraction_worker_key] = extraction_worker
                self.worker_threads[extraction_worker_key] = extraction_thread
                self.tier_workers[tier]['extraction'].append(extraction_worker)

            logger.info(f"   ✅ Started {extraction_count} {tier} extraction workers (queue: {tier_extraction_queue})")

            # 2. Start Transform Workers (consume from tier-based queue)
            self.tier_workers[tier]['transform'] = []
            tier_transform_queue = queue_manager.get_tier_queue_name(tier, 'transform')

            for worker_num in range(transform_count):
                transform_worker = TransformWorker(
                    queue_name=tier_transform_queue,
                    worker_number=worker_num,
                    tenant_ids=None  # Not needed for tier-based queues
                )
                transform_worker_key = f"transform_{tier}_worker_{worker_num}"

                transform_thread = threading.Thread(
                    target=self._run_worker,
                    args=(transform_worker_key, transform_worker),
                    daemon=True,
                    name=f"Worker-{transform_worker_key}"
                )
                transform_thread.start()

                self.workers[transform_worker_key] = transform_worker
                self.worker_threads[transform_worker_key] = transform_thread
                self.tier_workers[tier]['transform'].append(transform_worker)

            logger.info(f"   ✅ Started {transform_count} {tier} transform workers (queue: {tier_transform_queue})")

            # 3. Start Vectorization Workers (consume from tier-based queue)
            self.tier_workers[tier]['vectorization'] = []
            tier_vectorization_queue = queue_manager.get_tier_queue_name(tier, 'vectorization')

            for worker_num in range(vectorization_count):
                vectorization_worker = VectorizationWorker(
                    tenant_id=None,  # Not needed for tier-based queues
                    worker_number=worker_num,
                    tenant_ids=None,  # Not needed for tier-based queues
                    queue_name=tier_vectorization_queue  # Pass tier-based queue name
                )
                vectorization_worker_key = f"vectorization_{tier}_worker_{worker_num}"

                vectorization_thread = threading.Thread(
                    target=self._run_worker,
                    args=(vectorization_worker_key, vectorization_worker),
                    daemon=True,
                    name=f"Worker-{vectorization_worker_key}"
                )
                vectorization_thread.start()

                self.workers[vectorization_worker_key] = vectorization_worker
                self.worker_threads[vectorization_worker_key] = vectorization_thread
                self.tier_workers[tier]['vectorization'].append(vectorization_worker)

            logger.info(f"   ✅ Started {vectorization_count} {tier} vectorization workers (queue: {tier_vectorization_queue})")

            total = extraction_count + transform_count + vectorization_count
            logger.info(f"✅ {tier.upper()} tier worker pool started ({total} workers total)")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to start {tier} tier worker pool: {e}")
            return False

    def stop_all_workers(self):
        """Stop all worker pools."""
        if not self.running:
            logger.warning("Workers are not running")
            return False

        logger.info("🛑 Stopping all worker pools...")
        self.running = False

        # Stop all workers
        for worker_key, worker in self.workers.items():
            try:
                logger.info(f"   Stopping {worker_key}...")
                worker.stop()
            except Exception as e:
                logger.error(f"   ❌ Error stopping {worker_key}: {e}")

        # Wait for all threads to finish (with timeout)
        for worker_key, thread in self.worker_threads.items():
            try:
                thread.join(timeout=5.0)
                if thread.is_alive():
                    logger.warning(f"   ⚠️ Worker {worker_key} did not stop gracefully")
            except Exception as e:
                logger.error(f"   ❌ Error joining thread {worker_key}: {e}")

        # Clear all tracking
        self.workers.clear()
        self.worker_threads.clear()
        self.tier_workers.clear()

        logger.info("✅ All workers stopped")
        return True

    def restart_all_workers(self):
        """Restart all worker pools."""
        logger.info("🔄 Restarting all worker pools...")
        self.stop_all_workers()
        return self.start_all_workers()

    def _run_worker(self, worker_key: str, worker: object):
        """
        Run a worker in a thread.

        Args:
            worker_key: Unique identifier for the worker
            worker: Worker instance to run
        """
        try:
            logger.info(f"🏃 Worker {worker_key} starting...")
            worker.start_consuming()  # Workers use start_consuming() not start()
            logger.info(f"✅ Worker {worker_key} completed")
        except Exception as e:
            logger.error(f"❌ Worker {worker_key} failed: {e}", exc_info=True)

    def _get_tenants_by_tier(self) -> Dict[str, List[int]]:
        """
        Get all active tenants grouped by tier.

        Returns:
            Dict mapping tier name to list of tenant IDs
        """
        try:
            from app.core.database import get_database
            from sqlalchemy import text

            database = get_database()
            with database.get_read_session_context() as session:
                query = text("""
                    SELECT id, tier
                    FROM tenants
                    WHERE active = TRUE
                    ORDER BY tier, id
                """)
                result = session.execute(query)
                rows = result.fetchall()

                # Group tenants by tier
                tenants_by_tier = {
                    'free': [],
                    'basic': [],
                    'premium': [],
                    'enterprise': []
                }

                for row in rows:
                    tenant_id = row[0]
                    tier = row[1]
                    if tier in tenants_by_tier:
                        tenants_by_tier[tier].append(tenant_id)
                    else:
                        logger.warning(f"Unknown tier '{tier}' for tenant {tenant_id}, defaulting to 'free'")
                        tenants_by_tier['free'].append(tenant_id)

                logger.info(f"📊 Tenants by tier: {dict((k, len(v)) for k, v in tenants_by_tier.items())}")
                return tenants_by_tier

        except Exception as e:
            logger.error(f"❌ Failed to get tenants by tier: {e}")
            # Fallback to single tenant in free tier
            return {'free': [1], 'basic': [], 'premium': [], 'enterprise': []}

    def get_worker_status(self) -> Dict:
        """
        Get status of all worker pools.

        Returns:
            Dict with worker status information organized by tier
        """
        status = {
            'running': self.running,
            'workers': {}
        }

        # Organize workers by tier and type
        for tier, worker_types in self.tier_workers.items():
            for worker_type, workers in worker_types.items():
                # Create a unique key for this tier+type combination
                status_key = f"{tier}_{worker_type}"

                status['workers'][status_key] = {
                    'tier': tier,
                    'type': worker_type,
                    'count': len(workers),
                    'instances': []
                }

                for idx, worker in enumerate(workers):
                    worker_key = f"{worker_type}_{tier}_worker_{idx}"
                    thread = self.worker_threads.get(worker_key)

                    status['workers'][status_key]['instances'].append({
                        'worker_key': worker_key,
                        'worker_number': idx,
                        'worker_running': hasattr(worker, 'running') and worker.running,
                        'thread_alive': thread.is_alive() if thread else False
                    })

        return status

    def get_tier_config(self) -> Dict[str, Dict[str, int]]:
        """
        Get worker pool configuration for all tiers.

        Returns:
            Dict mapping tier name to worker counts
        """
        return self.TIER_WORKER_COUNTS.copy()


# Singleton instance
_worker_manager_instance = None


def get_worker_manager() -> WorkerManager:
    """
    Get the singleton WorkerManager instance.

    Returns:
        WorkerManager: The singleton worker manager instance
    """
    global _worker_manager_instance
    if _worker_manager_instance is None:
        _worker_manager_instance = WorkerManager()
    return _worker_manager_instance
