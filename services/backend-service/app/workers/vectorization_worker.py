"""
Vectorization Worker for ETL Pipeline

Consumes messages from tenant-specific vectorization queues, fetches entities from database,
generates embeddings using HybridProviderManager, and stores vectors in Qdrant.

Replicates the vectorization logic from the old ETL service but uses RabbitMQ messages
instead of a database queue table.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.workers.base_worker import BaseWorker
from app.core.logging_config import get_logger
from app.models.unified_models import (
    WorkItem, Changelog, Project, Status, Wit,
    Pr, PrCommit, PrReview, PrComment, Repository,
    WorkItemPrLink, Integration, QdrantVector
)

logger = get_logger(__name__)

# Source type mapping for multi-agent architecture
SOURCE_TYPE_MAPPING = {
    # Jira Agent's scope (all Jira-related data including cross-links)
    'work_items': 'JIRA',
    'changelogs': 'JIRA',
    'projects': 'JIRA',
    'statuses': 'JIRA',
    'statuses_mappings': 'JIRA',
    'workflows': 'JIRA',
    'wits': 'JIRA',
    'wits_hierarchies': 'JIRA',
    'wits_mappings': 'JIRA',
    'wits_prs_links': 'JIRA',  # Jira agent owns the links

    # GitHub Agent's scope (all GitHub-related data + DORA metrics)
    'prs': 'GITHUB',
    'prs_commits': 'GITHUB',
    'prs_reviews': 'GITHUB',
    'prs_comments': 'GITHUB',
    'repositories': 'GITHUB',
    'dora_metric_insights': 'GITHUB',      # GitHub agent owns DORA metrics
    'dora_market_benchmarks': 'GITHUB',    # Market benchmarks for comparison
}


class VectorizationWorker(BaseWorker):
    """
    Worker that processes vectorization messages and stores vectors in Qdrant.
    
    Message Format:
    {
        "tenant_id": 1,
        "table_name": "work_items",
        "external_id": "BEN-12345",  # Or internal ID for work_items_prs_links
        "operation": "insert"
    }
    """
    
    # Batch size for processing (same as old ETL)
    PROCESSING_BATCH_SIZE = 5
    
    # Table name to model mapping
    TABLE_MODEL_MAP = {
        'work_items': WorkItem,
        'changelogs': Changelog,
        'projects': Project,
        'statuses': Status,
        'wits': Wit,
        'prs': Pr,
        'prs_commits': PrCommit,
        'prs_reviews': PrReview,
        'prs_comments': PrComment,
        'repositories': Repository,
        'work_items_prs_links': WorkItemPrLink
    }
    
    def __init__(self, tenant_id: int):
        """
        Initialize vectorization worker for a specific tenant.
        
        Args:
            tenant_id: Tenant ID to process vectorization for
        """
        queue_name = f"vectorization_queue_tenant_{tenant_id}"
        super().__init__(queue_name)
        self.tenant_id = tenant_id

        # Note: We don't cache HybridProviderManager or QdrantClient
        # Each message processing creates fresh instances with their own sessions
        # This ensures proper session management and avoids stale session issues

        logger.info(f"VectorizationWorker initialized for tenant {tenant_id}")
    
    def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a single vectorization message.
        
        Args:
            message: Message containing table_name, external_id, tenant_id, operation
            
        Returns:
            bool: True if processing succeeded
        """
        try:
            table_name = message.get('table_name')
            external_id = message.get('external_id')
            tenant_id = message.get('tenant_id')
            operation = message.get('operation', 'insert')
            
            # Validate message
            if not all([table_name, external_id, tenant_id]):
                logger.error(f"Invalid message format: {message}")
                return False
            
            # Validate table name
            if table_name not in self.TABLE_MODEL_MAP:
                logger.error(f"Unknown table name: {table_name}")
                return False
            
            logger.info(f"Processing vectorization: {table_name} - {external_id}")

            # Step 1: Fetch entity from database (separate session)
            entity_data = None
            record_id = None
            integration_id = None

            with self.get_db_session() as session:
                entity = self._fetch_entity(session, table_name, external_id, tenant_id)

                if not entity:
                    # This can happen if entity was queued before commit or if entity was deleted
                    logger.debug(f"Entity not found (may have been queued before commit): {table_name} - {external_id}")
                    return False

                # Prepare entity data for vectorization
                entity_data = self._prepare_entity_data(entity, table_name)
                record_id = entity.id

                # Get integration_id from entity (most entities have integration_id)
                integration_id = getattr(entity, 'integration_id', None)

                if not entity_data:
                    logger.warning(f"No data to vectorize for {table_name} - {external_id}")
                    return False

            # Step 2: Generate embedding (separate session created inside)
            embedding = self._generate_embedding(tenant_id, entity_data, table_name)

            if not embedding:
                logger.error(f"Failed to generate embedding for {table_name} - {external_id}")
                return False

            # Step 3: Store in Qdrant (separate session created inside)
            point_id = self._get_point_id(table_name, external_id, record_id)
            collection_name = f"client_{tenant_id}_{table_name}"

            success = self._store_in_qdrant(
                collection_name=collection_name,
                point_id=point_id,
                embedding=embedding,
                metadata=entity_data
            )

            if not success:
                logger.error(f"Failed to store in Qdrant: {table_name} - {external_id}")
                return False

            # Step 4: Store bridge record in qdrant_vectors table (separate session)
            with self.get_db_session() as session:
                self._store_bridge_record(
                    session=session,
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                    table_name=table_name,
                    record_id=record_id,
                    qdrant_point_id=point_id,
                    collection_name=collection_name
                )

            logger.info(f"✅ Vectorization complete: {table_name} - {external_id}")
            return True
                
        except Exception as e:
            logger.error(f"Error processing vectorization message: {e}")
            logger.exception(e)
            return False
    
    def _fetch_entity(
        self,
        session: Session,
        table_name: str,
        external_id: str,
        tenant_id: int
    ) -> Optional[Any]:
        """
        Fetch entity from database by external_id.
        
        Args:
            session: Database session
            table_name: Name of the table
            external_id: External ID (or internal ID for work_items_prs_links)
            tenant_id: Tenant ID
            
        Returns:
            Entity object or None
        """
        model = self.TABLE_MODEL_MAP[table_name]
        
        try:
            # Special case for work_items: use 'key' field instead of 'external_id'
            if table_name == 'work_items':
                entity = session.query(model).filter(
                    model.key == external_id,
                    model.tenant_id == tenant_id,
                    model.active == True
                ).first()
            
            # Special case for work_items_prs_links: use internal ID
            elif table_name == 'work_items_prs_links':
                entity = session.query(model).filter(
                    model.id == int(external_id),
                    model.tenant_id == tenant_id,
                    model.active == True
                ).first()
            
            # All other tables: use external_id field
            else:
                entity = session.query(model).filter(
                    model.external_id == external_id,
                    model.tenant_id == tenant_id,
                    model.active == True
                ).first()
            
            return entity
            
        except Exception as e:
            logger.error(f"Error fetching entity {table_name} - {external_id}: {e}")
            return None
    
    def _prepare_entity_data(self, entity: Any, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Prepare entity data for vectorization (replicate from old ETL).
        
        Args:
            entity: SQLAlchemy entity object
            table_name: Name of the table
            
        Returns:
            Dictionary with entity data for vectorization
        """
        try:
            if table_name == "work_items":
                return {
                    "key": entity.key,
                    "summary": entity.summary or "",
                    "description": entity.description or "",
                    "status_name": entity.status.name if entity.status else "",
                    "wit_name": entity.wit.name if entity.wit else "",
                    "priority": entity.priority or "",
                    "assignee": entity.assignee or "",
                    "reporter": entity.reporter or "",
                    "created_date": self._serialize_datetime(entity.created_date),
                    "updated_date": self._serialize_datetime(entity.updated_date)
                }
            
            elif table_name == "changelogs":
                return {
                    "external_id": entity.external_id,
                    "from_status_name": entity.from_status_name or "",
                    "to_status_name": entity.to_status_name or "",
                    "changed_by": entity.changed_by or "",
                    "transition_change_date": self._serialize_datetime(entity.transition_change_date),
                    "time_in_status_seconds": entity.time_in_status_seconds or 0,
                    "work_item_key": entity.work_item.key if entity.work_item else ""
                }
            
            elif table_name == "projects":
                return {
                    "key": entity.key,
                    "name": entity.name or "",
                    "description": entity.description or "",
                    "project_type": entity.project_type or "",
                    "lead": entity.lead or ""
                }
            
            elif table_name == "statuses":
                return {
                    "external_id": entity.external_id or "",
                    "original_name": entity.original_name or "",
                    "description": entity.description or "",
                    "category": entity.category or ""
                }
            
            elif table_name == "wits":
                return {
                    "name": entity.name or "",
                    "description": entity.description or "",
                    "icon_url": entity.icon_url or ""
                }
            
            elif table_name == "prs":
                return {
                    "title": entity.title or "",
                    "description": entity.description or "",
                    "status": entity.status or "",
                    "author": entity.author or "",
                    "created_at": self._serialize_datetime(entity.pr_created_at),
                    "updated_at": self._serialize_datetime(entity.pr_updated_at)
                }
            
            elif table_name == "prs_commits":
                return {
                    "sha": entity.sha or "",
                    "message": entity.message or "",
                    "author_name": entity.author_name or "",
                    "author_email": entity.author_email or "",
                    "authored_date": self._serialize_datetime(entity.authored_date),
                    "committed_date": self._serialize_datetime(entity.committed_date)
                }
            
            elif table_name == "prs_reviews":
                return {
                    "state": entity.state or "",
                    "body": entity.body or "",
                    "author_login": entity.author_login or "",
                    "submitted_at": self._serialize_datetime(entity.submitted_at)
                }
            
            elif table_name == "prs_comments":
                return {
                    "body": entity.body or "",
                    "author_login": entity.author_login or "",
                    "comment_type": entity.comment_type or "",
                    "path": entity.path or "",
                    "line": entity.line,
                    "created_at": self._serialize_datetime(entity.created_at_github)
                }
            
            elif table_name == "repositories":
                return {
                    "name": entity.name or "",
                    "full_name": entity.full_name or "",
                    "description": entity.description or "",
                    "language": entity.language or "",
                    "topics": entity.topics or "",
                    "created_at": self._serialize_datetime(entity.created_at),
                    "updated_at": self._serialize_datetime(entity.updated_at)
                }
            
            elif table_name == "work_items_prs_links":
                # Get work item key from relationship
                work_item_key = ""
                if entity.work_item:
                    work_item_key = entity.work_item.key
                
                return {
                    "work_item_key": work_item_key,
                    "repo_full_name": entity.repo_full_name or "",
                    "pull_request_number": entity.pull_request_number,
                    "branch_name": entity.branch_name or "",
                    "pr_status": entity.pr_status or "",
                    "created_at": self._serialize_datetime(entity.created_at)
                }
            
            else:
                logger.warning(f"No entity data preparation defined for table: {table_name}")
                return None

        except Exception as e:
            logger.error(f"Error preparing entity data for {table_name}: {e}")
            return None

    def _serialize_datetime(self, dt_value: Any) -> str:
        """Convert datetime objects to ISO format strings."""
        if dt_value is None:
            return ""
        if isinstance(dt_value, datetime):
            return dt_value.isoformat()
        if isinstance(dt_value, str):
            return dt_value
        return str(dt_value)

    def _get_point_id(self, table_name: str, external_id: str, record_id: int) -> str:
        """
        Generate Qdrant point ID for the entity (UUID format, same as old ETL).

        Args:
            table_name: Name of the table
            external_id: External ID (not used, kept for signature compatibility)
            record_id: Internal database ID

        Returns:
            Point ID string (UUID)
        """
        import uuid

        # Create deterministic UUID for point ID (consistent with old ETL)
        # This ensures same entity always gets same point ID
        unique_string = f"{self.tenant_id}_{table_name}_{record_id}"
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

        return point_id

    def _generate_embedding(
        self,
        tenant_id: int,
        entity_data: Dict[str, Any],
        table_name: str
    ) -> Optional[List[float]]:
        """
        Generate embedding for entity data using HybridProviderManager.
        Creates its own database session for querying integration configs.

        Args:
            tenant_id: Tenant ID
            entity_data: Prepared entity data
            table_name: Name of the table

        Returns:
            List of floats representing the embedding vector
        """
        try:
            # Use asyncio to call the async method
            import asyncio
            from app.ai.hybrid_provider_manager import HybridProviderManager
            from app.api.ai_config_routes import create_text_content_from_entity

            # Create text content using the same helper as old ETL
            text_to_embed = create_text_content_from_entity(entity_data, table_name)

            if not text_to_embed or not text_to_embed.strip():
                logger.warning(f"No text content to embed for {table_name}")
                return None

            # Create fresh session for HybridProviderManager
            # This ensures we have a valid session to query Integration table
            with self.get_db_session() as session:
                # Create fresh HybridProviderManager with its own session
                hybrid_provider = HybridProviderManager(session)

                # Initialize providers for this tenant (queries Integration table)
                init_success = asyncio.run(hybrid_provider.initialize_providers(tenant_id))

                if not init_success:
                    logger.error(f"Failed to initialize AI providers for tenant {tenant_id}")
                    return None

                # Generate embeddings using the same method as old ETL
                response = asyncio.run(
                    hybrid_provider.generate_embeddings(
                        texts=[text_to_embed],
                        tenant_id=tenant_id
                    )
                )

                if response.success and response.data and len(response.data) > 0:
                    embedding = response.data[0]  # Get first embedding from batch
                    logger.debug(f"Generated embedding of dimension {len(embedding)}")
                    return embedding
                else:
                    error_msg = response.error if hasattr(response, 'error') else "Unknown error"
                    logger.error(f"Failed to generate embedding: {error_msg}")
                    return None

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            logger.exception(e)
            return None

    def _store_in_qdrant(
        self,
        collection_name: str,
        point_id: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Store embedding in Qdrant collection using PulseQdrantClient (same as old ETL).
        Creates fresh Qdrant client for each operation.

        Args:
            collection_name: Qdrant collection name
            point_id: Point ID (UUID string)
            embedding: Embedding vector
            metadata: Metadata to store with the point

        Returns:
            bool: True if successful
        """
        try:
            import asyncio
            from app.ai.qdrant_client import PulseQdrantClient

            # Create fresh Qdrant client (no database session needed)
            qdrant_client = PulseQdrantClient()
            asyncio.run(qdrant_client.initialize())

            # Ensure collection exists (same as old ETL)
            asyncio.run(
                qdrant_client.ensure_collection_exists(
                    collection_name=collection_name,
                    vector_size=len(embedding)
                )
            )

            # Prepare vector data (same format as old ETL)
            vector_data = [{
                'id': point_id,  # UUID string
                'vector': embedding,
                'payload': {
                    **metadata,
                    'tenant_id': self.tenant_id
                }
            }]

            # Upsert using PulseQdrantClient (same as old ETL)
            result = asyncio.run(
                qdrant_client.upsert_vectors(
                    collection_name=collection_name,
                    vectors=vector_data
                )
            )

            if result.success:
                logger.debug(f"Stored point {point_id} in collection {collection_name}")
                return True
            else:
                logger.error(f"Failed to store in Qdrant: {result.error}")
                return False

        except Exception as e:
            logger.error(f"Error storing in Qdrant: {e}")
            logger.exception(e)
            return False

    def _store_bridge_record(
        self,
        session: Session,
        tenant_id: int,
        integration_id: int,
        table_name: str,
        record_id: int,
        qdrant_point_id: str,
        collection_name: str
    ):
        """
        Store bridge record in qdrant_vectors table.

        Args:
            session: Database session
            tenant_id: Tenant ID
            integration_id: Integration ID (links to embedding config)
            table_name: Table name
            record_id: Internal database record ID
            qdrant_point_id: Qdrant point ID
            collection_name: Qdrant collection name
        """
        try:
            from sqlalchemy.dialects.postgresql import insert

            # Get source_type from mapping
            source_type = SOURCE_TYPE_MAPPING.get(table_name, 'UNKNOWN')

            if source_type == 'UNKNOWN':
                logger.warning(f"Unknown table name in SOURCE_TYPE_MAPPING: {table_name}")

            # Use UPSERT to handle duplicates
            stmt = insert(QdrantVector).values(
                source_type=source_type,
                table_name=table_name,
                record_id=record_id,
                qdrant_collection=collection_name,
                qdrant_point_id=qdrant_point_id,
                vector_type='content',  # Default to 'content' type
                integration_id=integration_id,
                tenant_id=tenant_id,
                active=True
                # created_at and last_updated_at are auto-generated by IntegrationBaseEntity
            )

            # ON CONFLICT UPDATE last_updated_at and qdrant references
            stmt = stmt.on_conflict_do_update(
                index_elements=['tenant_id', 'table_name', 'record_id', 'vector_type'],
                set_={
                    'qdrant_point_id': qdrant_point_id,
                    'qdrant_collection': collection_name,
                    'integration_id': integration_id,
                    'active': True,
                    'last_updated_at': datetime.utcnow()
                }
            )

            session.execute(stmt)
            session.commit()

            logger.debug(f"Stored bridge record: {source_type}/{table_name} - {record_id} -> {qdrant_point_id}")

        except Exception as e:
            logger.error(f"Error storing bridge record: {e}")
            session.rollback()
            raise

