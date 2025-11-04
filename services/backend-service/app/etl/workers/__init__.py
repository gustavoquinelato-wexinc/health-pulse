"""
ETL Workers Infrastructure Module

Generic worker infrastructure for ETL pipeline:
- base_worker.py: Base class for all workers
- bulk_operations.py: Bulk database operations utility
- worker_manager.py: Worker lifecycle management
- queue_manager.py: RabbitMQ queue management
- extraction_worker_router.py: Routes extraction messages to provider workers
- transform_worker_router.py: Routes transform messages to provider workers
- embedding_worker_router.py: Routes embedding messages to provider workers
"""

