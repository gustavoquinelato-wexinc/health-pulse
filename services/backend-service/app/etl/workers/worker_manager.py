"""
Worker Manager for managing background queue workers with SHARED POOL architecture.

Uses tier-based shared worker pools instead of per-tenant workers for better scalability.
"""

import threading
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor

from app.etl.workers.extraction_worker_router import ExtractionWorker
from app.etl.workers.transform_worker_router import TransformWorker
from app.etl.workers.embedding_worker_router import EmbeddingWorker
from app.etl.workers.queue_manager import QueueManager
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

    # Premium tier worker pool configuration (fallback values)
    PREMIUM_WORKER_COUNTS_FALLBACK = {
        'extraction': 5,
        'transform': 5,
        'embedding': 5
    }

    def __init__(self):
        """Initialize worker manager with shared pool architecture."""
        self.workers: Dict[str, object] = {}  # worker_key -> worker_instance
        self.worker_threads: Dict[str, threading.Thread] = {}  # worker_key -> thread
        self.tier_workers: Dict[str, Dict[str, List[object]]] = {}  # tier -> {worker_type -> [workers]}
        self.executor = ThreadPoolExecutor(max_workers=100)
        self.running = False

        logger.info("WorkerManager initialized with SHARED WORKER POOL architecture")

    def get_premium_worker_config(self, tenant_id: int = 1) -> Dict[str, int]:
        """
        Get premium worker configurations from system_settings.

        Args:
            tenant_id: Tenant ID to get settings for

        Returns:
            Dict mapping worker types to counts
        """
        try:
            from app.core.database import get_database
            from sqlalchemy import text

            database = get_database()
            with database.get_read_session_context() as session:
                # Get worker counts from system_settings
                query = text("""
                    SELECT setting_key, setting_value
                    FROM system_settings
                    WHERE tenant_id = :tenant_id
                    AND setting_key IN ('premium_extraction_workers', 'premium_transform_workers', 'premium_embedding_workers')
                """)
                result = session.execute(query, {'tenant_id': tenant_id})
                rows = result.fetchall()

                worker_config = {}
                for row in rows:
                    setting_key = row[0]
                    setting_value = int(row[1])

                    if setting_key == 'premium_extraction_workers':
                        worker_config['extraction'] = setting_value
                    elif setting_key == 'premium_transform_workers':
                        worker_config['transform'] = setting_value
                    elif setting_key == 'premium_embedding_workers':
                        worker_config['embedding'] = setting_value

                # Use fallback values for missing settings
                for worker_type in ['extraction', 'transform', 'embedding']:
                    if worker_type not in worker_config:
                        worker_config[worker_type] = self.PREMIUM_WORKER_COUNTS_FALLBACK[worker_type]

                logger.info(f"📊 Loaded premium worker configuration from system_settings: {worker_config}")
                return worker_config

        except Exception as e:
            logger.error(f"Failed to load premium worker configuration from system_settings: {e}")
            logger.info("Using fallback premium worker configuration")
            return self.PREMIUM_WORKER_COUNTS_FALLBACK

    def start_all_workers(self):
        """Start premium worker pools."""
        if self.running:
            logger.warning("Workers are already running")
            return False

        logger.info("🚀 Starting PREMIUM WORKER POOLS...")
        self.running = True

        # Setup queues first (creates premium queues)
        try:
            queue_manager = QueueManager()
            queue_manager.setup_queues()  # This will create 3 premium queues
            logger.info("✅ Premium queue topology setup complete")
        except Exception as e:
            logger.error(f"❌ Failed to setup queues: {e}")
            return False

        # Start premium worker pools
        try:
            tenants_by_tier = self._get_tenants_by_tier()
            premium_tenant_ids = tenants_by_tier.get('premium', [])

            if not premium_tenant_ids:
                logger.warning("⚠️ No premium tenants found, but starting workers anyway for MVP")
                premium_tenant_ids = [1]  # Default to tenant 1 for MVP

            logger.info(f"🔧 Starting premium worker pool for {len(premium_tenant_ids)} tenants: {premium_tenant_ids}")
            self._start_premium_worker_pool(premium_tenant_ids)

            total_workers = sum(len(workers) for workers in self.tier_workers.get('premium', {}).values())
            logger.info(f"✅ Started {total_workers} premium workers")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start shared worker pools: {e}")
            return False

    def _start_premium_worker_pool(self, tenant_ids: List[int]) -> bool:
        """
        Start premium worker pool.

        Workers will consume from premium queues.

        Args:
            tenant_ids: List of tenant IDs (for MVP, typically just [1])

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            tier = 'premium'
            if tier not in self.tier_workers:
                self.tier_workers[tier] = {}

            # Get worker counts from system_settings
            worker_counts = self.get_premium_worker_config(tenant_ids[0] if tenant_ids else 1)
            extraction_count = worker_counts['extraction']
            transform_count = worker_counts['transform']
            embedding_count = worker_counts['embedding']

            logger.info(f"   📊 Premium tier: {extraction_count} extraction + {transform_count} transform + {embedding_count} embedding workers")

            queue_manager = QueueManager()

            # 1. Start Extraction Workers (consume from premium queue)
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

            # 3. Start Embedding Workers (consume from tier-based queue)
            self.tier_workers[tier]['embedding'] = []
            tier_embedding_queue = queue_manager.get_tier_queue_name(tier, 'embedding')

            for worker_num in range(embedding_count):
                embedding_worker = EmbeddingWorker(
                    tier=tier  # Pass tier instead of individual parameters
                )
                embedding_worker_key = f"embedding_{tier}_worker_{worker_num}"

                embedding_thread = threading.Thread(
                    target=self._run_worker,
                    args=(embedding_worker_key, embedding_worker),
                    daemon=True,
                    name=f"Worker-{embedding_worker_key}"
                )
                embedding_thread.start()

                self.workers[embedding_worker_key] = embedding_worker
                self.worker_threads[embedding_worker_key] = embedding_thread
                self.tier_workers[tier]['embedding'].append(embedding_worker)

            logger.info(f"   ✅ Started {embedding_count} {tier} embedding workers (queue: {tier_embedding_queue})")

            total = extraction_count + transform_count + embedding_count
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

                # Group tenants by tier (premium only for MVP)
                tenants_by_tier = {
                    'premium': []
                }

                for row in rows:
                    tenant_id = row[0]
                    tier_name = row[1]
                    if tier_name == 'premium':
                        tenants_by_tier['premium'].append(tenant_id)
                    else:
                        logger.warning(f"Non-premium tier '{tier_name}' for tenant {tenant_id}, adding to premium for MVP")
                        tenants_by_tier['premium'].append(tenant_id)

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
        return {'premium': self.get_premium_worker_config()}


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
