"""
Embedding Worker for ETL Pipeline (TIER-BASED QUEUE ARCHITECTURE)

Consumes messages from tier-based embedding queues, fetches entities from database,
generates embeddings using HybridProviderManager, and stores vectors in Qdrant.

Replicates the embedding logic from the old ETL service but uses RabbitMQ messages
instead of a database queue table.

Tier-Based Queue Architecture:
- Workers consume from tier-based queues (embedding_queue_free, embedding_queue_premium, etc.)
- Each message contains tenant_id for proper routing
- Multiple workers per tier share the same queue
"""

import warnings
import time
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

# Suppress asyncio event loop closure warnings
warnings.filterwarnings("ignore", message=".*Event loop is closed.*", category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*coroutine.*was never awaited.*", category=RuntimeWarning)

from app.workers.base_worker import BaseWorker
from app.core.logging_config import get_logger
from app.models.unified_models import (
    WorkItem, Changelog, Project, Status, Wit,
    Pr, PrCommit, PrReview, PrComment, Repository,
    WorkItemPrLink, Integration, QdrantVector,
    WitHierarchy, WitMapping, StatusMapping, Workflow
)
from app.etl.queue.queue_manager import QueueManager
from app.core.database import get_database

logger = get_logger(__name__)

# Source type mapping for multi-agent architecture
SOURCE_TYPE_MAPPING = {
    # Jira Agent's scope (all Jira-related data including cross-links)
    'work_items': 'JIRA',
    'changelogs': 'JIRA',
    'projects': 'JIRA',
    'statuses': 'JIRA',
    'statuses_mappings': 'JIRA',
    'status_mappings': 'JIRA',  # Queue message name (maps to statuses_mappings table)
    'workflows': 'JIRA',
    'wits': 'JIRA',
    'wits_hierarchies': 'JIRA',
    'wits_mappings': 'JIRA',
    'work_items_prs_links': 'JIRA',  # Jira agent owns the links (fixed: was wits_prs_links)

    # GitHub Agent's scope (all GitHub-related data + DORA metrics)
    'prs': 'GITHUB',
    'prs_commits': 'GITHUB',
    'prs_reviews': 'GITHUB',
    'prs_comments': 'GITHUB',
    'repositories': 'GITHUB',
}

class EmbeddingWorker(BaseWorker):
    """
    Embedding worker that processes embedding requests from tier-based queues.
    
    Handles:
    - Fetching entities from database based on message content
    - Generating embeddings using HybridProviderManager
    - Storing vectors in Qdrant with proper tenant isolation
    - Updating qdrant_vectors bridge table
    - Error handling and retry logic
    """
    
    def __init__(self, tier: str = 'free'):
        """
        Initialize embedding worker for specific tier.

        Args:
            tier: Tenant tier (free, basic, premium, enterprise)
        """
        queue_name = f"embedding_queue_{tier}"
        super().__init__(queue_name)
        self.tier = tier
        self.hybrid_provider = None

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

    def _send_worker_status_sync(self, worker_type: str, tenant_id: int, job_id: int, status: str, step: str, error_message: str = None):
        """Synchronous wrapper for sending worker status updates."""
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._send_worker_status(worker_type, tenant_id, job_id, status, step, error_message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error in sync worker status update: {e}")

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

    def _complete_etl_job_on_final_step(self, job_id: int, tenant_id: int):
        """Complete ETL job when embedding worker finishes the final step."""
        try:
            from app.core.database import get_write_session
            from sqlalchemy import text
            from datetime import datetime, timezone

            with get_write_session() as session:
                # Update job status to FINISHED
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = 'FINISHED',
                        last_run_completed_at = :completed_at,
                        updated_at = :updated_at
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                session.execute(update_query, {
                    'job_id': job_id,
                    'tenant_id': tenant_id,
                    'completed_at': datetime.now(timezone.utc),
                    'updated_at': datetime.now(timezone.utc)
                })

                session.commit()
                logger.info(f"✅ ETL job {job_id} completed successfully by embedding worker")

        except Exception as e:
            logger.error(f"Error completing ETL job: {e}")

    def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a single embedding message from the queue.

        This is the required abstract method from BaseWorker.

        Args:
            message: Message data from queue

        Returns:
            bool: True if message was processed successfully, False otherwise
        """
        try:
            # Initialize hybrid provider if not already done
            if self.hybrid_provider is None:
                self._initialize_hybrid_provider_sync()

            # Extract standardized message data
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            job_id = message.get('job_id')
            step_type = message.get('type')  # ETL step name
            provider = message.get('provider')
            first_item = message.get('first_item', False)
            last_item = message.get('last_item', False)
            last_sync_date = message.get('last_sync_date')
            last_job_item = message.get('last_job_item', False)

            # Transform → Embedding specific fields
            table_name = message.get('table_name')
            external_id = message.get('external_id')

            # Determine message type:
            # 1. ETL step messages: have step_type but no table_name
            # 2. Individual entity messages: have table_name and external_id
            is_etl_step_message = step_type is not None and table_name is None
            is_individual_entity_message = table_name is not None and external_id is not None

            # Send WebSocket status: embedding worker starting (for any message with first_item=true)
            if job_id and first_item:
                step_name = step_type or table_name or "embedding"
                logger.debug(f"🔄 EMBEDDING WORKER: Starting step {step_name} for job {job_id}")
                # Send status update using sync helper to avoid event loop conflicts
                self._send_worker_status_sync(
                    worker_type="embedding",
                    tenant_id=tenant_id,
                    job_id=job_id,
                    status="running",
                    step=step_name
                )

            # Process the embedding message asynchronously
            result = self._process_embedding_message_sync_helper(message)

            # Send WebSocket status: embedding worker finished (for any message with last_item=true)
            if job_id and last_item:
                step_name = step_type or table_name or "embedding"
                if result:
                    logger.debug(f"✅ EMBEDDING WORKER: Finished step {step_name} for job {job_id}")
                    # Send status update using sync helper to avoid event loop conflicts
                    self._send_worker_status_sync(
                        worker_type="embedding",
                        tenant_id=tenant_id,
                        job_id=job_id,
                        status="finished",
                        step=step_name
                    )
                else:
                    logger.debug(f"❌ EMBEDDING WORKER: Failed step {step_name} for job {job_id}")
                    # Send status update using sync helper to avoid event loop conflicts
                    self._send_worker_status_sync(
                        worker_type="embedding",
                        tenant_id=tenant_id,
                        job_id=job_id,
                        status="failed",
                        step=step_name
                    )

            # Handle job completion when last_job_item=true
            if job_id and last_job_item:
                logger.info(f"🏁 EMBEDDING WORKER: Processing last job item - completing ETL job {job_id}")
                if result:
                    self._complete_etl_job(job_id, tenant_id, last_sync_date)
                    logger.info(f"✅ EMBEDDING WORKER: ETL job {job_id} marked as FINISHED with date updates")
                else:
                    self._update_job_status(job_id, overall_status="FAILED", message="ETL job failed during embedding")
                    logger.error(f"❌ EMBEDDING WORKER: ETL job {job_id} marked as FAILED")

            return result

        except Exception as e:
            import traceback
            logger.error(f"❌ EMBEDDING WORKER: Error processing message: {e}")
            logger.error(f"❌ EMBEDDING WORKER: Full traceback: {traceback.format_exc()}")
            logger.error(f"❌ EMBEDDING WORKER: Message that caused error: {message}")
            return False

    def _initialize_hybrid_provider_sync(self):
        """Initialize the hybrid provider synchronously."""
        try:
            from app.ai.hybrid_provider_manager import HybridProviderManager
            from app.core.database import get_database

            # Create a persistent database session for the hybrid provider
            # Use read session since initialization mainly reads provider configs
            db = get_database()
            db_session = db.get_read_session()

            self.hybrid_provider = HybridProviderManager(db_session)
            # Note: Providers will be initialized per tenant when processing messages

            logger.info(f"✅ EMBEDDING WORKER: Hybrid provider manager created for {self.__class__.__name__}")

        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Failed to initialize hybrid provider: {e}")
            raise

    def _process_embedding_message_sync(self, message: Dict[str, Any]) -> bool:
        """
        Synchronous wrapper for embedding message processing.

        Args:
            message: Message data from queue

        Returns:
            bool: True if successful, False otherwise
        """
        import asyncio

        try:
            # Run the async embedding process
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._process_embedding_message(message))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Error in sync wrapper: {e}")
            return False


    async def _process_embedding_message_async(self, message: Dict[str, Any]) -> bool:
        """
        Core async processing logic for embedding messages.
        This method handles the actual embedding processing without job completion logic.
        """
        try:
            logger.debug(f"🔍 EMBEDDING WORKER: Received message: {message}")
            tenant_id = message.get('tenant_id')
            step_type = message.get('type')
            table_name = message.get('table_name')
            job_id = message.get('job_id')

            # Handle mapping tables differently - bulk process entire table
            if step_type == 'mappings':
                if not all([tenant_id, table_name]):
                    logger.error(f"❌ EMBEDDING WORKER: Missing required fields for mappings message: {message}")
                    return False

                logger.info(f"🔄 EMBEDDING WORKER: Processing entire {table_name} table for tenant {tenant_id}")
                return await self._process_mapping_table(tenant_id, table_name)

            # Handle ETL step messages (bulk processing) - use standardized 'type' field
            if step_type and not table_name:
                # Map ETL step types to entity types for bulk processing
                etl_step_to_entity_mapping = {
                    'jira_projects_and_issue_types': ['projects', 'wits'],
                    'jira_statuses_and_relationships': ['statuses'],
                    'jira_issues_with_changelogs': ['work_items', 'changelogs'],
                    'jira_dev_status': ['work_items_prs_links']
                }

                # If this is an ETL step type, process all related entity types
                if step_type in etl_step_to_entity_mapping:
                    logger.info(f"🔄 EMBEDDING WORKER: Processing ETL step {step_type} for tenant {tenant_id}")
                    success = True
                    for target_entity_type in etl_step_to_entity_mapping[step_type]:
                        logger.info(f"🔄 EMBEDDING WORKER: Processing {target_entity_type} entities for ETL step {step_type}")
                        step_success = await self._process_entity_type_bulk(tenant_id, target_entity_type)
                        if not step_success:
                            success = False
                            logger.error(f"❌ EMBEDDING WORKER: Failed to process {target_entity_type} for ETL step {step_type}")

                    return success
                else:
                    logger.warning(f"⚠️ EMBEDDING WORKER: Unknown ETL step type: {step_type}")
                    return True  # Don't fail for unknown step types

            # Handle completion messages - external_id=None signals completion
            if table_name and message.get('external_id') is None:
                logger.info(f"🎯 [COMPLETION] Received completion message for {table_name} (no data to process)")
                return True

            # Handle individual entity messages - use standardized fields
            elif table_name and message.get('external_id'):
                entity_id = message.get('external_id')

                if not all([tenant_id, table_name, entity_id]):
                    logger.error(f"❌ EMBEDDING WORKER: Missing required fields: {message}")
                    return False

                logger.info(f"🔍 EMBEDDING WORKER: Fetching entity data for {table_name} ID {entity_id}")
                return await self._process_entity(tenant_id, table_name, entity_id, message)

            else:
                logger.warning(f"⚠️ EMBEDDING WORKER: Unknown message format: {message}")
                return False

        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Error processing message: {e}")
            import traceback
            logger.error(f"❌ EMBEDDING WORKER: Full traceback: {traceback.format_exc()}")
            return False

    def _process_embedding_message_sync_helper(self, message: Dict[str, Any]) -> bool:
        """
        Synchronous helper for embedding message processing.
        Handles job completion logic and delegates async work to the async method.
        """
        try:
            tenant_id = message.get('tenant_id')
            job_id = message.get('job_id')
            table_name = message.get('table_name')
            external_id = message.get('external_id')
            last_job_item = message.get('last_job_item', False)

            # 🎯 DEBUG: Log all completion-related fields
            logger.info(f"🎯 [COMPLETION CHECK] table_name={table_name}, external_id={external_id}, last_job_item={last_job_item}")

            # Handle completion messages with job completion logic
            if table_name and external_id is None and last_job_item:
                logger.info(f"🎯 [JOB COMPLETION] Completing ETL job {job_id} from completion message (table={table_name})")
                self._complete_etl_job(job_id, tenant_id, message.get('last_sync_date'))
                return True
            else:
                # 🎯 DEBUG: Log why completion wasn't triggered
                if table_name is None:
                    logger.debug(f"🎯 [COMPLETION CHECK] Skipping: table_name is None")
                if external_id is not None:
                    logger.debug(f"🎯 [COMPLETION CHECK] Skipping: external_id is not None ({external_id})")
                if not last_job_item:
                    logger.debug(f"🎯 [COMPLETION CHECK] Skipping: last_job_item is False")

            # For all other messages, delegate to the async processing method
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._process_embedding_message_async(message))
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Error in sync helper: {e}")
            import traceback
            logger.error(f"❌ EMBEDDING WORKER: Full traceback: {traceback.format_exc()}")
            return False

    async def _process_embedding_message(self, message: Dict[str, Any]) -> bool:
        """
        Main embedding message processor with job completion handling.

        Args:
            message: Message containing tenant_id, entity_type, entity_id, etc.

        Returns:
            bool: True if processed successfully, False otherwise
        """
        try:
            # Delegate to the sync helper method which handles both completion and async processing
            return self._process_embedding_message_sync_helper(message)

        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Error processing message: {e}")
            import traceback
            logger.error(f"❌ EMBEDDING WORKER: Full traceback: {traceback.format_exc()}")
            return False

    async def _process_entity_type_bulk(self, tenant_id: int, entity_type: str) -> bool:
        """Process all entities of a specific type for bulk embedding."""
        try:
            logger.info(f"🔄 EMBEDDING WORKER: Starting bulk processing for {entity_type} in tenant {tenant_id}")

            # Get all entities of this type for the tenant
            database = get_database()
            with database.get_read_session_context() as session:
                entities = []

                if entity_type == 'work_items':
                    entities = session.query(WorkItem).filter(WorkItem.tenant_id == tenant_id).all()
                elif entity_type == 'projects':
                    entities = session.query(Project).filter(Project.tenant_id == tenant_id).all()
                elif entity_type == 'wits':
                    entities = session.query(Wit).filter(Wit.tenant_id == tenant_id).all()
                elif entity_type == 'statuses':
                    entities = session.query(Status).filter(Status.tenant_id == tenant_id).all()
                elif entity_type == 'changelogs':
                    entities = session.query(Changelog).filter(Changelog.tenant_id == tenant_id).all()
                elif entity_type == 'work_items_prs_links':
                    entities = session.query(WorkItemPrLink).filter(WorkItemPrLink.tenant_id == tenant_id).all()
                else:
                    logger.warning(f"⚠️ EMBEDDING WORKER: Unknown entity type for bulk processing: {entity_type}")
                    return True  # Return success for unknown types to avoid blocking the pipeline

                logger.info(f"📊 EMBEDDING WORKER: Found {len(entities)} {entity_type} entities to process")

                # Process each entity
                success_count = 0
                for entity in entities:
                    try:
                        # Use external_id for most entities, id for link tables
                        entity_id = getattr(entity, 'external_id', None) or getattr(entity, 'id', None)
                        if entity_id:
                            success = await self._process_entity(tenant_id, entity_type, str(entity_id))
                            if success:
                                success_count += 1
                    except Exception as entity_error:
                        logger.error(f"❌ EMBEDDING WORKER: Error processing {entity_type} entity {getattr(entity, 'id', 'unknown')}: {entity_error}")

                logger.info(f"✅ EMBEDDING WORKER: Bulk processing complete for {entity_type}: {success_count}/{len(entities)} successful")
                return success_count > 0 or len(entities) == 0  # Success if we processed some entities or there were none to process

        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Error in bulk processing for {entity_type}: {e}")
            return False

    async def _process_entity(self, tenant_id: int, entity_type: str, entity_id: str, message: Dict[str, Any] = None) -> bool:
        """Process a single entity for embedding."""
        try:
            # Initialize providers for this tenant if not already done
            if not self.hybrid_provider.providers:
                logger.info(f"🔄 EMBEDDING WORKER: Initializing providers for tenant {tenant_id}")
                init_success = await self.hybrid_provider.initialize_providers(tenant_id)
                if not init_success:
                    logger.error(f"❌ EMBEDDING WORKER: Failed to initialize providers for tenant {tenant_id}")
                    return False

            # Convert entity_id to int for database queries (except for external_id lookups)
            try:
                entity_id_int = int(entity_id)
            except (ValueError, TypeError):
                # For external_id lookups, keep as string
                entity_id_int = entity_id

            # Fetch entity data
            entity_data = await self._fetch_entity_data(tenant_id, entity_type, entity_id_int)
            if not entity_data:
                logger.debug(f"🔍 EMBEDDING WORKER: Entity not found: {entity_type} ID {entity_id}")
                return True  # Not an error, entity might have been deleted

            # Generate embedding
            text_content = self._extract_text_content(entity_data, entity_type)
            if not text_content:
                logger.debug(f"🔍 EMBEDDING WORKER: No text content for {entity_type} ID {entity_id}")
                return True  # Not an error, just no content to embed

            # Generate embedding vector
            embedding_result = await self.hybrid_provider.generate_embeddings(
                texts=[text_content],
                tenant_id=tenant_id
            )
            if not embedding_result.success or not embedding_result.data:
                logger.error(f"❌ EMBEDDING WORKER: Failed to generate embedding for {entity_type} ID {entity_id}: {embedding_result.error}")
                return False

            embedding_vector = embedding_result.data[0]  # Get first embedding from list

            # Store in Qdrant and update bridge table
            success = await self._store_embedding(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id_int,
                embedding_vector=embedding_vector,
                entity_data=entity_data,
                message=message or {}
            )

            if success:
                logger.debug(f"✅ EMBEDDING WORKER: Successfully processed {entity_type} ID {entity_id}")
            else:
                logger.error(f"❌ EMBEDDING WORKER: Failed to store embedding for {entity_type} ID {entity_id}")

            return success

        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Error processing {entity_type} entity {entity_id}: {e}")
            return False

    async def _process_mapping_table(self, tenant_id: int, table_name: str) -> bool:
        """
        Process an entire mapping table for embedding.

        Args:
            tenant_id: Tenant ID
            table_name: Name of the mapping table (status_mappings, wits_mappings, etc.)

        Returns:
            bool: True if processed successfully
        """
        try:
            # Initialize providers for this tenant if not already done
            if not await self.hybrid_provider.initialize_providers(tenant_id):
                logger.error(f"❌ EMBEDDING WORKER: Failed to initialize providers for tenant {tenant_id}")
                return False

            database = get_database()

            # Use table name directly (should always be database table name now)
            db_table_name = table_name

            # Map table names to model classes (using database table names)
            table_models = {
                'statuses_mappings': StatusMapping,  # Database table name
                'wits_mappings': WitMapping,
                'wits_hierarchies': WitHierarchy,
                'workflows': Workflow
            }

            if db_table_name not in table_models:
                logger.error(f"❌ EMBEDDING WORKER: Unknown mapping table: {db_table_name} (from {table_name})")
                return False

            model_class = table_models[db_table_name]

            with database.get_read_session_context() as session:
                # Get all records from the table for this tenant
                records = session.query(model_class).filter(
                    model_class.tenant_id == tenant_id
                ).all()

                logger.info(f"🔄 EMBEDDING WORKER: Found {len(records)} records in {table_name} for tenant {tenant_id}")

                if not records:
                    logger.info(f"✅ EMBEDDING WORKER: No records to process in {table_name}")
                    return True

                # Process each record with rate limiting
                success_count = 0
                for i, record in enumerate(records):
                    try:
                        # Add rate limiting - delay every 5 records to prevent provider overload
                        if i > 0 and i % 5 == 0:
                            logger.debug(f"🔄 EMBEDDING WORKER: Rate limiting - processed {i}/{len(records)} records, pausing...")
                            await asyncio.sleep(5)  # 5 second pause every 5 records

                        # Create entity data based on table type
                        entity_data = self._create_mapping_entity_data(record, table_name)

                        # Generate embedding with retry logic
                        embedding_vector = None
                        for retry in range(3):  # Try up to 3 times
                            embedding_vector = await self._generate_embedding(entity_data, table_name)
                            if embedding_vector:
                                break
                            elif retry < 2:  # Don't sleep on the last retry
                                logger.debug(f"🔄 EMBEDDING WORKER: Retry {retry + 1}/3 for {table_name} ID {record.id}")
                                await asyncio.sleep(3)  # Wait 3 seconds before retry

                        if not embedding_vector:
                            logger.warning(f"⚠️ EMBEDDING WORKER: Failed to generate embedding for {table_name} ID {record.id} after 3 retries")
                            continue

                        # Store embedding in Qdrant and update bridge table
                        success = await self._store_embedding(
                            tenant_id=tenant_id,
                            entity_type=table_name,
                            entity_id=record.id,
                            embedding_vector=embedding_vector,
                            entity_data=entity_data,
                            message={'tenant_id': tenant_id, 'table_name': table_name, 'type': 'mappings'}
                        )

                        if success:
                            success_count += 1
                            if success_count % 20 == 0:  # Log progress every 20 successful embeddings
                                logger.info(f"🔄 EMBEDDING WORKER: Progress {success_count}/{len(records)} records embedded for {table_name}")
                        else:
                            logger.warning(f"⚠️ EMBEDDING WORKER: Failed to embed {table_name} ID {record.id}")

                    except Exception as e:
                        logger.error(f"❌ EMBEDDING WORKER: Error processing {table_name} ID {record.id}: {e}")

                logger.info(f"✅ EMBEDDING WORKER: Successfully embedded {success_count}/{len(records)} records from {table_name}")
                return success_count > 0

        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Error processing mapping table {table_name}: {e}")
            return False
        finally:
            # Cleanup AI providers to prevent event loop errors
            try:
                if hasattr(self, 'hybrid_provider') and self.hybrid_provider:
                    await self.hybrid_provider.cleanup()
                    logger.debug(f"🧹 EMBEDDING WORKER: Cleaned up AI providers after processing {table_name}")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ EMBEDDING WORKER: Error during cleanup: {cleanup_error}")

    def _create_mapping_entity_data(self, record, table_name: str) -> Dict[str, Any]:
        """
        Create entity data dictionary for mapping table records.

        Args:
            record: Database record object
            table_name: Name of the table

        Returns:
            Dict containing entity data
        """
        base_data = {
            'id': record.id,
            'entity_type': table_name,
            'tenant_id': record.tenant_id
        }

        if table_name == 'statuses_mappings':
            base_data.update({
                'status_from': record.status_from,
                'status_to': record.status_to,
                'status_category': record.status_category
            })
        elif table_name == 'wits_mappings':
            base_data.update({
                'wit_from': record.wit_from,
                'wit_to': record.wit_to,
                'wits_hierarchy_id': record.wits_hierarchy_id
            })
        elif table_name == 'wits_hierarchies':
            base_data.update({
                'level_name': record.level_name,
                'level_number': record.level_number,
                'description': record.description
            })
        elif table_name == 'workflows':
            base_data.update({
                'step_name': record.step_name,
                'step_number': record.step_number,
                'step_category': record.step_category,
                'is_commitment_point': record.is_commitment_point
            })

        return base_data
    
    async def _fetch_entity_data(self, tenant_id: int, entity_type: str, entity_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch entity data from database for embedding generation.
        
        Args:
            tenant_id: Tenant ID
            entity_type: Type of entity (work_items, prs, etc.)
            entity_id: Entity ID
            
        Returns:
            Dict containing entity data or None if not found
        """
        try:
            database = get_database()
            
            with database.get_read_session_context() as session:
                # Map entity type to model class and fetch data
                # All entities are queried by external_id from queue messages
                if entity_type == 'work_items':
                    entity = session.query(WorkItem).filter(
                        WorkItem.external_id == str(entity_id),
                        WorkItem.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,  # Internal ID for qdrant_vectors table
                            'external_id': entity.external_id,
                            'key': entity.key,
                            'summary': entity.summary,
                            'description': entity.description,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }
                
                elif entity_type == 'prs':
                    entity = session.query(Pr).filter(
                        Pr.external_id == str(entity_id),
                        Pr.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,  # Internal ID for qdrant_vectors table
                            'external_id': entity.external_id,
                            'title': entity.title,
                            'description': entity.description,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'projects':
                    logger.info(f"🔍 EMBEDDING WORKER: Querying projects table for external_id='{entity_id}' tenant_id={tenant_id}")
                    entity = session.query(Project).filter(
                        Project.external_id == str(entity_id),
                        Project.tenant_id == tenant_id
                    ).first()

                    if entity:
                        logger.info(f"✅ EMBEDDING WORKER: Found project entity: id={entity.id}, external_id={entity.external_id}, name={entity.name}")
                        return {
                            'id': entity.id,  # Internal ID for qdrant_vectors table
                            'external_id': entity.external_id,
                            'key': entity.key,
                            'name': entity.name,
                            'project_type': entity.project_type,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }
                    else:
                        logger.warning(f"⚠️ EMBEDDING WORKER: No project found with external_id='{entity_id}' tenant_id={tenant_id}")

                elif entity_type == 'wits':
                    logger.info(f"🔍 EMBEDDING WORKER: Querying wits table for external_id='{entity_id}' tenant_id={tenant_id}")
                    entity = session.query(Wit).filter(
                        Wit.external_id == str(entity_id),
                        Wit.tenant_id == tenant_id
                    ).first()

                    if entity:
                        logger.info(f"✅ EMBEDDING WORKER: Found wit entity: id={entity.id}, external_id={entity.external_id}, name={entity.original_name}")
                        return {
                            'id': entity.id,  # Internal ID for qdrant_vectors table
                            'external_id': entity.external_id,
                            'original_name': entity.original_name,
                            'description': entity.description,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }
                    else:
                        logger.warning(f"⚠️ EMBEDDING WORKER: No wit found with external_id='{entity_id}' tenant_id={tenant_id}")

                elif entity_type == 'statuses':
                    logger.info(f"🔍 EMBEDDING WORKER: Querying statuses table for external_id='{entity_id}' tenant_id={tenant_id}")
                    entity = session.query(Status).filter(
                        Status.external_id == str(entity_id),
                        Status.tenant_id == tenant_id
                    ).first()

                    if entity:
                        logger.info(f"✅ EMBEDDING WORKER: Found status entity: id={entity.id}, external_id={entity.external_id}, name={entity.original_name}")
                        return {
                            'id': entity.id,  # Internal ID for qdrant_vectors table
                            'external_id': entity.external_id,
                            'original_name': entity.original_name,
                            'category': entity.category,
                            'description': entity.description,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }
                    else:
                        logger.warning(f"⚠️ EMBEDDING WORKER: No status found with external_id='{entity_id}' tenant_id={tenant_id}")

                elif entity_type == 'changelogs':
                    entity = session.query(Changelog).filter(
                        Changelog.external_id == str(entity_id),
                        Changelog.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,  # Internal ID for qdrant_vectors table
                            'external_id': entity.external_id,
                            'changed_by': entity.changed_by,
                            'transition_start_date': entity.transition_start_date.isoformat() if entity.transition_start_date else None,
                            'transition_change_date': entity.transition_change_date.isoformat() if entity.transition_change_date else None,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'work_items_prs_links':
                    entity = session.query(WorkItemPrLink).filter(
                        WorkItemPrLink.id == entity_id,
                        WorkItemPrLink.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,
                            'repo_full_name': entity.repo_full_name,
                            'pull_request_number': entity.pull_request_number,
                            'branch_name': entity.branch_name,
                            'commit_sha': entity.commit_sha,
                            'pr_status': entity.pr_status,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                # Mapping tables - use internal id instead of external_id
                elif entity_type == 'wits_hierarchies':
                    entity = session.query(WitHierarchy).filter(
                        WitHierarchy.id == entity_id,
                        WitHierarchy.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,
                            'level_name': entity.level_name,
                            'level_number': entity.level_number,
                            'description': entity.description,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'wits_mappings':
                    entity = session.query(WitMapping).filter(
                        WitMapping.id == entity_id,
                        WitMapping.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,
                            'wit_from': entity.wit_from,
                            'wit_to': entity.wit_to,
                            'wits_hierarchy_id': entity.wits_hierarchy_id,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'statuses_mappings':
                    entity = session.query(StatusMapping).filter(
                        StatusMapping.id == entity_id,
                        StatusMapping.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,
                            'status_from': entity.status_from,
                            'status_to': entity.status_to,
                            'status_category': entity.status_category,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'workflows':
                    entity = session.query(Workflow).filter(
                        Workflow.id == entity_id,
                        Workflow.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,
                            'step_name': entity.step_name,
                            'step_number': entity.step_number,
                            'step_category': entity.step_category,
                            'is_commitment_point': entity.is_commitment_point,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                # Add more entity types as needed...
                logger.warning(f"⚠️ EMBEDDING WORKER: Unknown entity type: {entity_type}")
                return None
                
        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Error fetching entity data: {e}")
            return None
    
    async def _generate_embedding(self, entity_data: Dict[str, Any], entity_type: str) -> Optional[List[float]]:
        """
        Generate embedding vector for entity data.
        
        Args:
            entity_data: Entity data dictionary
            entity_type: Type of entity
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            # Combine relevant text fields for embedding
            text_content = self._extract_text_content(entity_data, entity_type)
            
            if not text_content.strip():
                logger.warning(f"⚠️ EMBEDDING WORKER: No text content for {entity_type} ID {entity_data.get('id')}")
                return None
            
            # Generate embedding using hybrid provider
            embedding_result = await self.hybrid_provider.generate_embeddings(
                texts=[text_content],
                tenant_id=entity_data['tenant_id']
            )

            # Extract first embedding from ProviderResponse
            if embedding_result.success and embedding_result.data:
                return embedding_result.data[0]  # Return first embedding from list
            else:
                logger.error(f"❌ EMBEDDING WORKER: Invalid embedding result: success={embedding_result.success}, error={embedding_result.error}")
                return None
                
        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Error generating embedding: {e}")
            return None
    
    def _extract_text_content(self, entity_data: Dict[str, Any], entity_type: str) -> str:
        """
        Extract text content from entity data for embedding generation.

        Args:
            entity_data: Entity data dictionary
            entity_type: Type of entity

        Returns:
            Combined text content for embedding
        """
        text_parts = []
        logger.debug(f"🔍 EMBEDDING WORKER: Extracting text content for {entity_type}: {entity_data}")

        if entity_type == 'work_items':
            if entity_data.get('key'):
                text_parts.append(f"Key: {entity_data['key']}")
            if entity_data.get('summary'):
                text_parts.append(f"Summary: {entity_data['summary']}")
            if entity_data.get('description'):
                text_parts.append(f"Description: {entity_data['description']}")
                
        elif entity_type == 'prs':
            if entity_data.get('title'):
                text_parts.append(f"Title: {entity_data['title']}")
            if entity_data.get('description'):
                text_parts.append(f"Description: {entity_data['description']}")

        elif entity_type == 'projects':
            if entity_data.get('key'):
                text_parts.append(f"Key: {entity_data['key']}")
            if entity_data.get('name'):
                text_parts.append(f"Name: {entity_data['name']}")
            if entity_data.get('project_type'):
                text_parts.append(f"Type: {entity_data['project_type']}")

        elif entity_type == 'wits':
            if entity_data.get('original_name'):
                text_parts.append(f"Work Item Type: {entity_data['original_name']}")
            if entity_data.get('description'):
                text_parts.append(f"Description: {entity_data['description']}")

        elif entity_type == 'statuses':
            if entity_data.get('original_name'):
                text_parts.append(f"Status: {entity_data['original_name']}")
            if entity_data.get('category'):
                text_parts.append(f"Category: {entity_data['category']}")
            if entity_data.get('description'):
                text_parts.append(f"Description: {entity_data['description']}")

        elif entity_type == 'changelogs':
            if entity_data.get('changed_by'):
                text_parts.append(f"Changed by: {entity_data['changed_by']}")
            if entity_data.get('transition_start_date'):
                text_parts.append(f"Transition started: {entity_data['transition_start_date']}")
            if entity_data.get('transition_change_date'):
                text_parts.append(f"Transition completed: {entity_data['transition_change_date']}")

        elif entity_type == 'work_items_prs_links':
            if entity_data.get('repo_full_name'):
                text_parts.append(f"Repository: {entity_data['repo_full_name']}")
            if entity_data.get('pull_request_number'):
                text_parts.append(f"Pull Request: #{entity_data['pull_request_number']}")
            if entity_data.get('branch_name'):
                text_parts.append(f"Branch: {entity_data['branch_name']}")
            if entity_data.get('pr_status'):
                text_parts.append(f"Status: {entity_data['pr_status']}")

        # Mapping tables
        elif entity_type == 'wits_hierarchies':
            if entity_data.get('level_name'):
                text_parts.append(f"Level Name: {entity_data['level_name']}")
            if entity_data.get('level_number'):
                text_parts.append(f"Level Number: {entity_data['level_number']}")
            if entity_data.get('description'):
                text_parts.append(f"Description: {entity_data['description']}")

        elif entity_type == 'wits_mappings':
            if entity_data.get('wit_from'):
                text_parts.append(f"WIT From: {entity_data['wit_from']}")
            if entity_data.get('wit_to'):
                text_parts.append(f"WIT To: {entity_data['wit_to']}")

        elif entity_type == 'statuses_mappings':
            if entity_data.get('status_from'):
                text_parts.append(f"Status From: {entity_data['status_from']}")
            if entity_data.get('status_to'):
                text_parts.append(f"Status To: {entity_data['status_to']}")
            if entity_data.get('status_category'):
                text_parts.append(f"Status Category: {entity_data['status_category']}")

        elif entity_type == 'workflows':
            if entity_data.get('step_name'):
                text_parts.append(f"Workflow Step: {entity_data['step_name']}")
            if entity_data.get('step_number'):
                text_parts.append(f"Step Number: {entity_data['step_number']}")
            if entity_data.get('step_category'):
                text_parts.append(f"Step Category: {entity_data['step_category']}")
            if entity_data.get('is_commitment_point'):
                text_parts.append(f"Commitment Point: {entity_data['is_commitment_point']}")

        # Add more entity types as needed...

        result = " ".join(text_parts)
        logger.debug(f"✅ EMBEDDING WORKER: Extracted text for {entity_type}: {result[:100] if result else 'EMPTY'}")
        return result

    async def _store_embedding(self, tenant_id: int, entity_type: str, entity_id: int,
                             embedding_vector: List[float], entity_data: Dict[str, Any], message: Dict[str, Any]) -> bool:
        """
        Store embedding in Qdrant and update qdrant_vectors bridge table.

        Args:
            tenant_id: Tenant ID
            entity_type: Type of entity
            entity_id: Entity ID
            embedding_vector: Generated embedding vector
            entity_data: Original entity data

        Returns:
            bool: True if stored successfully, False otherwise
        """
        try:
            # Store in Qdrant (tenant-isolated collection)
            qdrant_success = await self._store_in_qdrant(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                embedding_vector=embedding_vector,
                entity_data=entity_data
            )

            if not qdrant_success:
                return False

            # Update qdrant_vectors bridge table
            integration_id = message.get('integration_id')
            # Use database ID from entity_data for record_id (integer field)
            database_id = entity_data.get('id')
            bridge_success = await self._update_bridge_table(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=database_id,  # Use database ID instead of external ID
                integration_id=integration_id
            )

            return bridge_success

        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Error storing embedding: {e}")
            return False

    async def _store_in_qdrant(self, tenant_id: int, entity_type: str, entity_id: int,
                             embedding_vector: List[float], entity_data: Dict[str, Any]) -> bool:
        """Store embedding vector in Qdrant with tenant isolation."""
        try:
            logger.info(f"🔄 EMBEDDING WORKER: Storing embedding in Qdrant for {entity_type}_{entity_id}")
            # Use PulseQdrantClient to store in Qdrant
            from app.ai.qdrant_client import PulseQdrantClient

            qdrant_client = PulseQdrantClient()
            await qdrant_client.initialize()
            logger.info(f"✅ EMBEDDING WORKER: Qdrant client initialized")

            # Use entity_type directly as collection name (should always be database table name now)
            collection_name = f"tenant_{tenant_id}_{entity_type}"

            # Create deterministic UUID for point ID (Qdrant requires UUID or unsigned integer)
            import uuid
            unique_string = f"{tenant_id}_{entity_type}_{entity_id}"
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

            payload = {
                'entity_type': entity_type,
                'entity_id': entity_id,
                'tenant_id': tenant_id,
                'source_type': SOURCE_TYPE_MAPPING.get(entity_type, 'UNKNOWN'),
                'created_at': datetime.now().isoformat(),
                **entity_data  # Include entity data in payload
            }

            # Ensure collection exists
            await qdrant_client.ensure_collection_exists(
                collection_name=collection_name,
                vector_size=len(embedding_vector)
            )

            # Store using PulseQdrantClient
            result = await qdrant_client.upsert_vectors(
                collection_name=collection_name,
                vectors=[{
                    'id': point_id,
                    'vector': embedding_vector,
                    'payload': payload
                }]
            )

            if result.success:
                logger.info(f"✅ EMBEDDING WORKER: Stored vector in Qdrant: {point_id}")
                return True
            else:
                logger.error(f"❌ EMBEDDING WORKER: Failed to store vector in Qdrant: {point_id} - {result.error}")
                return False

        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Error storing in Qdrant: {e}")
            return False

    async def _update_bridge_table(self, tenant_id: int, entity_type: str, entity_id: int, integration_id: int = None) -> bool:
        """Update qdrant_vectors bridge table to track stored vectors."""
        try:
            logger.info(f"🔄 EMBEDDING WORKER: Updating bridge table for {entity_type}_{entity_id}, integration_id={integration_id}")
            from app.models.unified_models import QdrantVector
            database = get_database()

            # Use the existing SOURCE_TYPE_MAPPING for consistency
            source_type = SOURCE_TYPE_MAPPING.get(entity_type, 'UNKNOWN')
            logger.info(f"🔄 EMBEDDING WORKER: Source type for {entity_type}: {source_type}")

            # If integration_id is not provided, try to find the appropriate integration
            if integration_id is None:
                logger.info(f"🔄 EMBEDDING WORKER: Looking up integration_id for source_type={source_type}")
                integration_id = await self._get_integration_id_for_source_type(tenant_id, source_type)
                if integration_id is None:
                    logger.error(f"❌ EMBEDDING WORKER: No integration_id found for {source_type} in tenant {tenant_id}")
                    return False
                logger.info(f"✅ EMBEDDING WORKER: Found integration_id={integration_id} for {source_type}")

            # Generate the same point ID as used in Qdrant storage
            import uuid
            unique_string = f"{tenant_id}_{entity_type}_{entity_id}"
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

            with database.get_write_session_context() as session:
                # Check if record already exists
                existing = session.query(QdrantVector).filter(
                    QdrantVector.source_type == source_type,
                    QdrantVector.table_name == entity_type,
                    QdrantVector.record_id == entity_id,
                    QdrantVector.tenant_id == tenant_id
                ).first()

                if existing:
                    # Update existing record
                    existing.active = True
                    existing.last_updated_at = datetime.now()
                    existing.qdrant_point_id = point_id
                    logger.info(f"✅ EMBEDDING WORKER: Updated bridge table record: {entity_type}_{entity_id}")
                else:
                    # Create new record
                    new_vector = QdrantVector(
                        source_type=source_type,
                        table_name=entity_type,
                        record_id=entity_id,
                        qdrant_collection=f"tenant_{tenant_id}_{entity_type}",
                        qdrant_point_id=point_id,
                        vector_type='content',
                        integration_id=integration_id,
                        tenant_id=tenant_id,
                        active=True,
                        created_at=datetime.now(),
                        last_updated_at=datetime.now()
                    )
                    session.add(new_vector)
                    logger.info(f"✅ EMBEDDING WORKER: Created bridge table record: {entity_type}_{entity_id}")

                session.commit()
                return True

        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Error updating bridge table: {e}")
            return False

    async def _get_integration_id_for_source_type(self, tenant_id: int, source_type: str) -> Optional[int]:
        """Get the integration_id for a given source_type (JIRA or GITHUB)."""
        try:
            from app.models.unified_models import Integration
            database = get_database()

            with database.get_read_session_context() as session:
                # Map source_type to provider name
                provider_mapping = {
                    'JIRA': 'Jira',
                    'GITHUB': 'GitHub'
                }
                provider_name = provider_mapping.get(source_type)

                if not provider_name:
                    logger.error(f"Unknown source_type: {source_type}")
                    return None

                # Find the integration for this tenant and provider
                integration = session.query(Integration).filter(
                    Integration.tenant_id == tenant_id,
                    Integration.provider == provider_name,
                    Integration.active == True
                ).first()

                if integration:
                    return integration.id
                else:
                    logger.warning(f"No active {provider_name} integration found for tenant {tenant_id}")
                    return None

        except Exception as e:
            logger.error(f"Error finding integration_id for {source_type}: {e}")
            return None

    def _update_job_status(self, job_id: int, step_name: str = None, step_status: str = None, overall_status: str = None, message: str = None):
        """Update ETL job step status or overall status in database JSON structure."""
        try:
            from app.core.database import get_database
            from sqlalchemy import text

            database = get_database()
            with database.get_write_session_context() as session:
                if overall_status:
                    # Update overall status (only for job completion)
                    # Use string formatting for overall_status to avoid parameter binding issues
                    update_query = text(f"""
                        UPDATE etl_jobs
                        SET status = jsonb_set(status, ARRAY['overall'], '"{overall_status}"'::jsonb),
                            last_updated_at = NOW()
                        WHERE id = :job_id
                    """)

                    session.execute(update_query, {
                        'job_id': job_id
                    })
                    logger.info(f"Updated job {job_id} overall status to {overall_status}")

                elif step_name and step_status:
                    # Update specific step status within the JSON structure
                    # Use string formatting for step_name and step_status to avoid parameter binding issues
                    update_query = text(f"""
                        UPDATE etl_jobs
                        SET status = jsonb_set(status, ARRAY['steps', '{step_name}', 'embedding'], '"{step_status}"'::jsonb),
                            last_updated_at = NOW()
                        WHERE id = :job_id
                    """)

                    session.execute(update_query, {
                        'job_id': job_id
                    })
                    logger.info(f"Updated job {job_id} step {step_name} embedding status to {step_status}")

                session.commit()
                if message:
                    logger.info(f"Job {job_id} message: {message}")

        except Exception as e:
            logger.error(f"Error updating job status: {e}")

    def _complete_etl_job(self, job_id: int, tenant_id: int, last_sync_date: str = None):
        """
        Complete the ETL job by updating its status to FINISHED and setting completion fields.

        Args:
            job_id: ETL job ID
            tenant_id: Tenant ID
            last_sync_date: Last sync date to update
        """
        try:
            from app.core.database import get_write_session
            from sqlalchemy import text

            with get_write_session() as session:
                # Update job status to FINISHED and set completion fields
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = jsonb_set(status, ARRAY['overall'], '"FINISHED"'::jsonb),
                        last_run_finished_at = NOW(),
                        last_updated_at = NOW()
                        """ + (", last_sync_date = :last_sync_date" if last_sync_date else "") + """
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                params = {'job_id': job_id, 'tenant_id': tenant_id}
                if last_sync_date:
                    params['last_sync_date'] = last_sync_date

                session.execute(update_query, params)
                session.commit()

                logger.info(f"🎯 [JOB COMPLETION] ETL job {job_id} marked as FINISHED")

                # Note: Job completion status updates are handled by the database update above
                # No need for additional WebSocket status updates here

        except Exception as e:
            logger.error(f"❌ Error completing ETL job {job_id}: {e}")


