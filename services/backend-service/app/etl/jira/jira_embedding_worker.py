"""
Jira Embedding Worker - Handles embedding generation for all Jira entity types.

Processes embedding requests for:
- Work Items (issues)
- Projects
- Work Item Types (WITs)
- Statuses
- Changelogs
- Work Items-PRs Links
- Mapping Tables (status_mappings, wits_mappings, wits_hierarchies, workflows)

Architecture:
- Fetches entities from database using external_id
- Generates embeddings using HybridProviderManager
- Stores vectors in Qdrant with proper tenant isolation
- Updates qdrant_vectors bridge table
"""

import asyncio
import uuid
from typing import Dict, Any, Optional, List
from sqlalchemy import text

from app.core.utils import DateTimeHelper

from app.core.logging_config import get_logger
from app.core.database import get_database
from app.models.unified_models import (
    WorkItem, Changelog, Project, Status, Wit,
    WorkItemPrLink, WitHierarchy, WitMapping, StatusMapping, Workflow, QdrantVector
)
from app.etl.workers.embedding_worker_router import SOURCE_TYPE_MAPPING

logger = get_logger(__name__)


class JiraEmbeddingWorker:
    """
    Jira Embedding Worker - Processes embedding requests for all Jira entity types.

    Handles:
    - Fetching Jira entities from database
    - Generating embeddings using HybridProviderManager
    - Storing vectors in Qdrant
    - Updating qdrant_vectors bridge table
    """

    def __init__(self, status_manager=None, queue_manager=None):
        """
        Initialize Jira embedding worker.

        Args:
            status_manager: WorkerStatusManager for sending status updates
            queue_manager: QueueManager for publishing messages (if needed)
        """
        self.status_manager = status_manager
        self.queue_manager = queue_manager
        self.hybrid_provider = None
        self._initialize_hybrid_provider()
        logger.debug("✅ Initialized JiraEmbeddingWorker")

    def _initialize_hybrid_provider(self):
        """Initialize the hybrid provider with a persistent database session."""
        try:
            from app.ai.hybrid_provider_manager import HybridProviderManager
            from app.core.database import get_database

            # Create a persistent database session for the hybrid provider
            # Use read session since initialization mainly reads provider configs
            db = get_database()
            db_session = db.get_read_session()

            self.hybrid_provider = HybridProviderManager(db_session)
            # Note: Providers will be initialized per tenant when processing messages

            logger.info(f"✅ [JIRA EMBEDDING] Hybrid provider manager created")

        except Exception as e:
            logger.error(f"❌ [JIRA EMBEDDING] Failed to initialize hybrid provider: {e}")
            raise

    async def cleanup(self):
        """
        Cleanup async resources to prevent event loop errors.

        Called by BaseWorker after processing each message to ensure
        httpx AsyncClient instances are properly closed before event loop closes.
        """
        try:
            if self.hybrid_provider:
                await self.hybrid_provider.cleanup()
                logger.debug("✅ [JIRA EMBEDDING] Hybrid provider cleaned up")
        except Exception as e:
            logger.debug(f"Error during Jira embedding worker cleanup (suppressed): {e}")

    async def _send_worker_status(self, step: str, tenant_id: int, job_id: int,
                                   status: str, step_type: str = None):
        """
        Send worker status update using injected status manager.

        Args:
            step: ETL step name (e.g., 'extraction', 'transform', 'embedding')
            tenant_id: Tenant ID
            job_id: Job ID
            status: Status to send (e.g., 'running', 'finished', 'failed')
            step_type: Optional step type for logging (e.g., 'jira_issues')
        """
        if self.status_manager:
            await self.status_manager.send_worker_status(
                step=step,
                tenant_id=tenant_id,
                job_id=job_id,
                status=status,
                step_type=step_type
            )
        else:
            logger.warning(f"Status manager not available - cannot send {status} status for {step_type}")

    async def process_jira_embedding(self, message: Dict[str, Any]) -> bool:
        """
        Process Jira embedding message.

        Args:
            message: Embedding message

        Returns:
            bool: True if processed successfully
        """
        try:
            tenant_id = message.get('tenant_id')
            job_id = message.get('job_id')
            step_type = message.get('type')
            table_name = message.get('table_name')
            external_id = message.get('external_id')
            last_item = message.get('last_item', False)
            last_job_item = message.get('last_job_item', False)
            new_last_sync_date = message.get('new_last_sync_date')
            rate_limited = message.get('rate_limited', False)  # 🔑 Rate limit flag from transform

            logger.debug(f"🔍 [JIRA EMBEDDING] Processing: table={table_name}, external_id={external_id}, step={step_type}, rate_limited={rate_limited}")

            # Handle mapping tables differently - bulk process entire table
            if step_type == 'mappings':
                if not all([tenant_id, table_name]):
                    logger.error(f"❌ [JIRA EMBEDDING] Missing required fields for mappings message")
                    return False

                logger.info(f"🔄 [JIRA EMBEDDING] Processing entire {table_name} table for tenant {tenant_id}")
                result = await self._process_mapping_table(tenant_id, table_name)

                # 🔑 Send embedding worker "finished" status when last_item=True
                if last_item and job_id:
                    await self._send_worker_status("embedding", tenant_id, job_id, "finished", step_type)
                    logger.debug(f"✅ [JIRA EMBEDDING] Embedding step marked as finished for {table_name} (mappings)")

                # 🔑 Complete ETL job when last_job_item=True (only for successful processing)
                if last_job_item and job_id and result:
                    logger.info(f"🏁 [JIRA EMBEDDING] Processing last job item - completing ETL job {job_id}")
                    await self.status_manager.complete_etl_job(job_id, tenant_id, new_last_sync_date)
                    logger.info(f"✅ [JIRA EMBEDDING] ETL job {job_id} marked as FINISHED")

                return result

            # Handle completion messages - external_id=None signals completion
            if table_name and external_id is None:
                logger.info(f"🎯 [JIRA EMBEDDING] Received completion message for {table_name} (rate_limited={rate_limited})")

                # 🔑 Send embedding worker "finished" status when last_item=True
                if last_item and job_id:
                    await self._send_worker_status("embedding", tenant_id, job_id, "finished", step_type)
                    logger.debug(f"✅ [JIRA EMBEDDING] Embedding step marked as finished for {table_name} (completion message)")

                # 🔑 Complete ETL job when last_job_item=True
                if last_job_item and job_id:
                    if rate_limited:
                        logger.info(f"🏁 [JIRA EMBEDDING] Completing ETL job {job_id} with RATE_LIMITED status")
                    else:
                        logger.info(f"🏁 [JIRA EMBEDDING] Completing ETL job {job_id} with FINISHED status")

                    await self.status_manager.complete_etl_job(
                        job_id=job_id,
                        tenant_id=tenant_id,
                        last_sync_date=new_last_sync_date,
                        rate_limited=rate_limited  # 🔑 Forward rate_limited flag
                    )

                    if rate_limited:
                        logger.info(f"✅ [JIRA EMBEDDING] ETL job {job_id} marked as RATE_LIMITED")
                    else:
                        logger.info(f"✅ [JIRA EMBEDDING] ETL job {job_id} marked as FINISHED")

                return True

            # Handle individual entity messages
            if table_name and external_id:
                if not tenant_id:
                    logger.error(f"❌ [JIRA EMBEDDING] Missing tenant_id")
                    return False

                logger.info(f"🔍 [JIRA EMBEDDING] Fetching entity data for {table_name} ID {external_id}")
                result = await self._process_entity(tenant_id, table_name, external_id, message)

                # 🔑 Send embedding worker "finished" status when last_item=True
                if last_item and job_id:
                    await self._send_worker_status("embedding", tenant_id, job_id, "finished", step_type)
                    logger.debug(f"✅ [JIRA EMBEDDING] Embedding step marked as finished for {table_name}")

                # 🔑 Complete ETL job when last_job_item=True (only for successful processing)
                if last_job_item and job_id and result:
                    logger.info(f"🏁 [JIRA EMBEDDING] Processing last job item - completing ETL job {job_id}")
                    await self.status_manager.complete_etl_job(job_id, tenant_id, new_last_sync_date)
                    logger.info(f"✅ [JIRA EMBEDDING] ETL job {job_id} marked as FINISHED")

                return result

            logger.warning(f"⚠️ [JIRA EMBEDDING] Unknown message format")
            return False

        except Exception as e:
            logger.error(f"❌ [JIRA EMBEDDING] Error processing message: {e}")
            import traceback
            logger.error(f"❌ [JIRA EMBEDDING] Full traceback: {traceback.format_exc()}")
            return False

    async def _process_entity(self, tenant_id: int, entity_type: str, entity_id: str, message: Dict[str, Any]) -> bool:
        """Process a single Jira entity for embedding."""
        try:
            # Initialize providers for this tenant if not already done
            if not self.hybrid_provider.providers:
                logger.info(f"🔄 [JIRA EMBEDDING] Initializing providers for tenant {tenant_id}")
                init_success = await self.hybrid_provider.initialize_providers(tenant_id)
                if not init_success:
                    logger.error(f"❌ [JIRA EMBEDDING] Failed to initialize providers for tenant {tenant_id}")
                    return False

            # Fetch entity data
            entity_data = await self._fetch_entity_data(tenant_id, entity_type, entity_id)
            if not entity_data:
                logger.debug(f"🔍 [JIRA EMBEDDING] Entity not found: {entity_type} ID {entity_id}")
                return True  # Not an error, entity might have been deleted

            # Generate embedding
            text_content = self._extract_text_content(entity_data, entity_type)
            if not text_content:
                logger.debug(f"🔍 [JIRA EMBEDDING] No text content for {entity_type} ID {entity_id}")
                return True  # Not an error, just no content to embed

            # Generate embedding vector
            embedding_result = await self.hybrid_provider.generate_embeddings(
                texts=[text_content],
                tenant_id=tenant_id
            )
            if not embedding_result.success or not embedding_result.data:
                logger.error(f"❌ [JIRA EMBEDDING] Failed to generate embedding: {embedding_result.error}")
                return False

            embedding_vector = embedding_result.data[0]

            # Store in Qdrant and update bridge table
            success = await self._store_embedding(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_data['id'],  # Use internal ID for storage
                embedding_vector=embedding_vector,
                entity_data=entity_data,
                message=message or {}
            )

            if success:
                logger.debug(f"✅ [JIRA EMBEDDING] Successfully processed {entity_type} ID {entity_id}")
            else:
                logger.error(f"❌ [JIRA EMBEDDING] Failed to store embedding for {entity_type} ID {entity_id}")

            return success

        except Exception as e:
            logger.error(f"❌ [JIRA EMBEDDING] Error processing {entity_type} entity {entity_id}: {e}")
            import traceback
            logger.error(f"❌ [JIRA EMBEDDING] Full traceback: {traceback.format_exc()}")
            return False

    async def _fetch_entity_data(self, tenant_id: int, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch Jira entity data from database for embedding generation."""
        try:
            logger.debug(f"🔍 [JIRA EMBEDDING] Fetching {entity_type} with external_id={entity_id}, tenant_id={tenant_id}")
            database = get_database()

            # 🔑 Use WRITE session for reads to ensure we read from primary
            with database.get_write_session_context() as session:
                if entity_type == 'work_items':
                    entity = session.query(WorkItem).filter(
                        WorkItem.external_id == str(entity_id),
                        WorkItem.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,
                            'external_id': entity.external_id,
                            'key': entity.key,
                            'summary': entity.summary,
                            'description': entity.description,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'projects':
                    entity = session.query(Project).filter(
                        Project.external_id == str(entity_id),
                        Project.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,
                            'external_id': entity.external_id,
                            'key': entity.key,
                            'name': entity.name,
                            # Project model doesn't have description field
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'wits':
                    entity = session.query(Wit).filter(
                        Wit.external_id == str(entity_id),
                        Wit.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,
                            'external_id': entity.external_id,
                            'name': entity.original_name,  # Wit model uses 'original_name'
                            'description': entity.description,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'statuses':
                    entity = session.query(Status).filter(
                        Status.external_id == str(entity_id),
                        Status.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,
                            'external_id': entity.external_id,
                            'name': entity.original_name,  # Status model uses 'original_name'
                            'description': entity.description,
                            'category': entity.category,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'changelogs':
                    entity = session.query(Changelog).filter(
                        Changelog.external_id == str(entity_id),
                        Changelog.tenant_id == tenant_id
                    ).first()

                    if entity:
                        # Get status names from relationships
                        from_status_name = entity.from_status.original_name if entity.from_status else None
                        to_status_name = entity.to_status.original_name if entity.to_status else None

                        return {
                            'id': entity.id,
                            'external_id': entity.external_id,
                            'changed_by': entity.changed_by,
                            'from_status': from_status_name,
                            'to_status': to_status_name,
                            'transition_change_date': entity.transition_change_date,
                            'time_in_status_seconds': entity.time_in_status_seconds,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'work_items_prs_links':
                    entity = session.query(WorkItemPrLink).filter(
                        WorkItemPrLink.id == int(entity_id),  # This table uses internal ID
                        WorkItemPrLink.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,
                            'work_item_id': entity.work_item_id,
                            'external_repo_id': entity.external_repo_id,
                            'repo_full_name': entity.repo_full_name,
                            'pull_request_number': entity.pull_request_number,
                            'branch_name': entity.branch_name,
                            'pr_status': entity.pr_status,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                else:
                    logger.warning(f"⚠️ [JIRA EMBEDDING] Unknown entity type: {entity_type}")
                    return None

            return None

        except Exception as e:
            logger.error(f"❌ [JIRA EMBEDDING] Error fetching {entity_type} entity {entity_id}: {e}")
            return None

    def _extract_text_content(self, entity_data: Dict[str, Any], entity_type: str) -> str:
        """Extract text content from Jira entity data for embedding generation."""
        text_parts = []
        logger.debug(f"🔍 [JIRA EMBEDDING] Extracting text content for {entity_type}: {entity_data}")

        if entity_type == 'work_items':
            if entity_data.get('key'):
                text_parts.append(f"Key: {entity_data['key']}")
            if entity_data.get('summary'):
                text_parts.append(f"Summary: {entity_data['summary']}")
            if entity_data.get('description'):
                text_parts.append(f"Description: {entity_data['description']}")

        elif entity_type == 'projects':
            if entity_data.get('key'):
                text_parts.append(f"Key: {entity_data['key']}")
            if entity_data.get('name'):
                text_parts.append(f"Name: {entity_data['name']}")
            if entity_data.get('description'):
                text_parts.append(f"Description: {entity_data['description']}")

        elif entity_type == 'wits':
            if entity_data.get('name'):
                text_parts.append(f"Work Item Type: {entity_data['name']}")
            if entity_data.get('description'):
                text_parts.append(f"Description: {entity_data['description']}")

        elif entity_type == 'statuses':
            if entity_data.get('name'):
                text_parts.append(f"Status: {entity_data['name']}")
            if entity_data.get('category'):
                text_parts.append(f"Category: {entity_data['category']}")
            if entity_data.get('description'):
                text_parts.append(f"Description: {entity_data['description']}")

        elif entity_type == 'changelogs':
            # Changelogs track status transitions
            if entity_data.get('changed_by'):
                text_parts.append(f"Changed By: {entity_data['changed_by']}")
            if entity_data.get('from_status'):
                text_parts.append(f"From Status: {entity_data['from_status']}")
            if entity_data.get('to_status'):
                text_parts.append(f"To Status: {entity_data['to_status']}")
            if entity_data.get('time_in_status_seconds'):
                text_parts.append(f"Time in Status: {entity_data['time_in_status_seconds']} seconds")

        elif entity_type == 'work_items_prs_links':
            # Work item to PR link information
            if entity_data.get('work_item_id'):
                text_parts.append(f"Work Item ID: {entity_data['work_item_id']}")
            if entity_data.get('repo_full_name'):
                text_parts.append(f"Repository: {entity_data['repo_full_name']}")
            if entity_data.get('pull_request_number'):
                text_parts.append(f"PR Number: {entity_data['pull_request_number']}")
            if entity_data.get('branch_name'):
                text_parts.append(f"Branch: {entity_data['branch_name']}")
            if entity_data.get('pr_status'):
                text_parts.append(f"PR Status: {entity_data['pr_status']}")

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

        result = " ".join(text_parts)
        logger.debug(f"✅ [JIRA EMBEDDING] Extracted text for {entity_type}: {result[:100] if result else 'EMPTY'}")
        return result

    async def _store_embedding(self, tenant_id: int, entity_type: str, entity_id: int,
                               embedding_vector: list, entity_data: Dict[str, Any], message: Dict[str, Any]) -> bool:
        """Store embedding in Qdrant and update qdrant_vectors bridge table."""
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
                logger.error(f"❌ [JIRA EMBEDDING] Failed to store in Qdrant")
                return False

            # Update qdrant_vectors bridge table
            bridge_success = await self._update_bridge_table(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                message=message
            )

            if not bridge_success:
                logger.error(f"❌ [JIRA EMBEDDING] Failed to update bridge table")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ [JIRA EMBEDDING] Error storing embedding: {e}")
            import traceback
            logger.error(f"❌ [JIRA EMBEDDING] Full traceback: {traceback.format_exc()}")
            return False

    async def _store_in_qdrant(self, tenant_id: int, entity_type: str, entity_id: int,
                               embedding_vector: List[float], entity_data: Dict[str, Any]) -> bool:
        """Store embedding vector in Qdrant with tenant isolation."""
        try:
            logger.info(f"🔄 [JIRA EMBEDDING] Storing embedding in Qdrant for {entity_type}_{entity_id}")
            # Use PulseQdrantClient to store in Qdrant
            from app.ai.qdrant_client import PulseQdrantClient

            qdrant_client = PulseQdrantClient()
            await qdrant_client.initialize()
            logger.info(f"✅ [JIRA EMBEDDING] Qdrant client initialized")

            # Use entity_type directly as collection name (should always be database table name now)
            collection_name = f"tenant_{tenant_id}_{entity_type}"

            # Create deterministic UUID for point ID (Qdrant requires UUID or unsigned integer)
            unique_string = f"{tenant_id}_{entity_type}_{entity_id}"
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

            payload = {
                'entity_type': entity_type,
                'entity_id': entity_id,
                'tenant_id': tenant_id,
                'source_type': SOURCE_TYPE_MAPPING.get(entity_type, 'UNKNOWN'),
                'created_at': DateTimeHelper.now_default().isoformat(),
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
                logger.info(f"✅ [JIRA EMBEDDING] Stored vector in Qdrant: {point_id}")
                return True
            else:
                logger.error(f"❌ [JIRA EMBEDDING] Failed to store vector in Qdrant: {point_id} - {result.error}")
                return False

        except Exception as e:
            logger.error(f"❌ [JIRA EMBEDDING] Error storing in Qdrant: {e}")
            return False

    async def _update_bridge_table(self, tenant_id: int, entity_type: str, entity_id: int, message: Dict[str, Any]) -> bool:
        """Update qdrant_vectors bridge table to track stored vectors."""
        try:
            from app.models.unified_models import QdrantVector, Integration
            database = get_database()

            # Get source_type from SOURCE_TYPE_MAPPING
            source_type = SOURCE_TYPE_MAPPING.get(entity_type, 'UNKNOWN')

            # Get integration_id from message or lookup
            integration_id = message.get('integration_id')
            if integration_id is None:
                integration_id = await self._get_integration_id_for_source_type(tenant_id, source_type)
                if integration_id is None:
                    logger.error(f"❌ [JIRA EMBEDDING] No integration_id found for {source_type} in tenant {tenant_id}")
                    return False

            # Generate the same point ID as used in Qdrant storage
            unique_string = f"{tenant_id}_{entity_type}_{entity_id}"
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

            with database.get_write_session_context() as session:
                # Check if record already exists (must match unique constraint)
                existing = session.query(QdrantVector).filter(
                    QdrantVector.source_type == source_type,
                    QdrantVector.table_name == entity_type,
                    QdrantVector.record_id == entity_id,
                    QdrantVector.tenant_id == tenant_id,
                    QdrantVector.vector_type == 'content'
                ).first()

                if existing:
                    # Update existing record
                    existing.active = True
                    existing.last_updated_at = DateTimeHelper.now_default()
                    existing.qdrant_point_id = point_id
                    logger.debug(f"✅ [JIRA EMBEDDING] Updated bridge table: {entity_type} ID {entity_id}")
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
                        created_at=DateTimeHelper.now_default(),
                        last_updated_at=DateTimeHelper.now_default()
                    )
                    session.add(new_vector)
                    logger.debug(f"✅ [JIRA EMBEDDING] Inserted into bridge table: {entity_type} ID {entity_id}")

                session.commit()
                return True

        except Exception as e:
            # Handle race condition: another worker may have inserted the same record
            from psycopg2.errors import UniqueViolation
            if isinstance(e.__cause__, UniqueViolation) or 'duplicate key' in str(e).lower():
                logger.info(f"ℹ️ [JIRA EMBEDDING] Record already exists (race condition handled): {entity_type}_{entity_id}")
                return True

            logger.error(f"❌ [JIRA EMBEDDING] Error updating bridge table: {e}")
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
                    logger.error(f"❌ [JIRA EMBEDDING] Unknown source_type: {source_type}")
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
                    logger.error(f"❌ [JIRA EMBEDDING] No active {provider_name} integration found for tenant {tenant_id}")
                    return None

        except Exception as e:
            logger.error(f"❌ [JIRA EMBEDDING] Error getting integration_id: {e}")
            return None

    async def _process_mapping_table(self, tenant_id: int, table_name: str) -> bool:
        """Process an entire Jira mapping table for embedding."""
        try:
            # Initialize providers for this tenant if not already done
            if not self.hybrid_provider:
                from app.ai.hybrid_provider_manager import HybridProviderManager
                self.hybrid_provider = HybridProviderManager()

            if not self.hybrid_provider.providers:
                if not await self.hybrid_provider.initialize_providers(tenant_id):
                    logger.error(f"❌ [JIRA EMBEDDING] Failed to initialize providers for tenant {tenant_id}")
                    return False

            database = get_database()

            # Map table names to model classes
            table_models = {
                'statuses_mappings': StatusMapping,
                'wits_mappings': WitMapping,
                'wits_hierarchies': WitHierarchy,
                'workflows': Workflow
            }

            if table_name not in table_models:
                logger.error(f"❌ [JIRA EMBEDDING] Unknown mapping table: {table_name}")
                return False

            model_class = table_models[table_name]

            # 🔑 Use WRITE session for mapping tables
            with database.get_write_session_context() as session:
                # Get all records from the table for this tenant
                records = session.query(model_class).filter(
                    model_class.tenant_id == tenant_id
                ).all()

                logger.info(f"🔄 [JIRA EMBEDDING] Found {len(records)} records in {table_name} for tenant {tenant_id}")

                if not records:
                    logger.info(f"✅ [JIRA EMBEDDING] No records to process in {table_name}")
                    return True

                # Process each record with rate limiting
                success_count = 0
                for i, record in enumerate(records):
                    try:
                        # Add rate limiting - delay every 5 records
                        if i > 0 and i % 5 == 0:
                            logger.debug(f"🔄 [JIRA EMBEDDING] Rate limiting - processed {i}/{len(records)} records, pausing...")
                            await asyncio.sleep(5)

                        # Create entity data based on table type
                        entity_data = self._create_mapping_entity_data(record, table_name)

                        # Generate embedding
                        text_content = self._extract_text_content(entity_data, table_name)
                        if not text_content:
                            logger.debug(f"🔍 [JIRA EMBEDDING] No text content for {table_name} ID {record.id}")
                            continue

                        embedding_result = await self.hybrid_provider.generate_embeddings(
                            texts=[text_content],
                            tenant_id=tenant_id
                        )
                        if not embedding_result.success or not embedding_result.data:
                            logger.warning(f"⚠️ [JIRA EMBEDDING] Failed to generate embedding for {table_name} ID {record.id}")
                            continue

                        embedding_vector = embedding_result.data[0]

                        # Store embedding
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
                            if success_count % 20 == 0:
                                logger.info(f"🔄 [JIRA EMBEDDING] Progress {success_count}/{len(records)} records embedded for {table_name}")
                        else:
                            logger.warning(f"⚠️ [JIRA EMBEDDING] Failed to embed {table_name} ID {record.id}")

                    except Exception as e:
                        logger.error(f"❌ [JIRA EMBEDDING] Error processing {table_name} ID {record.id}: {e}")

                logger.info(f"✅ [JIRA EMBEDDING] Successfully embedded {success_count}/{len(records)} records from {table_name}")
                return success_count > 0

        except Exception as e:
            logger.error(f"❌ [JIRA EMBEDDING] Error processing mapping table {table_name}: {e}")
            return False

    def _create_mapping_entity_data(self, record, table_name: str) -> Dict[str, Any]:
        """Create entity data dictionary from mapping table record."""
        base_data = {
            'id': record.id,
            'tenant_id': record.tenant_id,
            'entity_type': table_name
        }

        if table_name == 'wits_hierarchies':
            base_data.update({
                'level_name': record.level_name,
                'level_number': record.level_number,
                'description': record.description
            })
        elif table_name == 'wits_mappings':
            base_data.update({
                'wit_from': record.wit_from,
                'wit_to': record.wit_to
            })
        elif table_name == 'statuses_mappings':
            base_data.update({
                'status_from': record.status_from,
                'status_to': record.status_to,
                'status_category': record.status_category
            })
        elif table_name == 'workflows':
            base_data.update({
                'step_name': record.step_name,
                'step_number': record.step_number,
                'step_category': record.step_category,
                'is_commitment_point': record.is_commitment_point
            })

        return base_data