"""
GitHub Embedding Worker - Handles embedding generation for all GitHub entity types.

Processes embedding requests for:
- Pull Requests (PRs)
- PR Commits
- PR Reviews
- PR Comments
- Repositories

Architecture:
- Fetches entities from database using external_id
- Generates embeddings using HybridProviderManager
- Stores vectors in Qdrant with proper tenant isolation
- Updates qdrant_vectors bridge table
"""

import asyncio
import time
from typing import Dict, Any, Optional
from sqlalchemy import text

from app.core.logging_config import get_logger
from app.core.database import get_database
from app.models.unified_models import Pr, PrCommit, PrReview, PrComment, Repository

logger = get_logger(__name__)


class GitHubEmbeddingWorker:
    """
    GitHub Embedding Worker - Processes embedding requests for all GitHub entity types.

    Handles:
    - Fetching GitHub entities from database
    - Generating embeddings using HybridProviderManager
    - Storing vectors in Qdrant
    - Updating qdrant_vectors bridge table
    """

    def __init__(self, status_manager=None, queue_manager=None):
        """
        Initialize GitHub embedding worker.

        Args:
            status_manager: WorkerStatusManager for sending status updates
            queue_manager: QueueManager for publishing messages (if needed)
        """
        self.status_manager = status_manager
        self.queue_manager = queue_manager
        self.hybrid_provider = None
        self._initialize_hybrid_provider()
        logger.debug("✅ Initialized GitHubEmbeddingWorker")

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

            logger.info(f"✅ [GITHUB EMBEDDING] Hybrid provider manager created")

        except Exception as e:
            logger.error(f"❌ [GITHUB EMBEDDING] Failed to initialize hybrid provider: {e}")
            raise

    async def process_github_embedding(self, message: Dict[str, Any]) -> bool:
        """
        Process GitHub embedding message.

        Args:
            message: Embedding message

        Returns:
            bool: True if processed successfully
        """
        try:
            tenant_id = message.get('tenant_id')
            step_type = message.get('type')
            table_name = message.get('table_name')
            external_id = message.get('external_id')

            logger.debug(f"🔍 [GITHUB EMBEDDING] Processing: table={table_name}, external_id={external_id}, step={step_type}")

            # Handle completion messages - external_id=None signals completion
            if table_name and external_id is None:
                logger.info(f"🎯 [GITHUB EMBEDDING] Received completion message for {table_name}")
                return True

            # Handle individual entity messages
            if table_name and external_id:
                if not tenant_id:
                    logger.error(f"❌ [GITHUB EMBEDDING] Missing tenant_id")
                    return False

                logger.info(f"🔍 [GITHUB EMBEDDING] Fetching entity data for {table_name} ID {external_id}")
                return await self._process_entity(tenant_id, table_name, external_id, message)

            logger.warning(f"⚠️ [GITHUB EMBEDDING] Unknown message format")
            return False

        except Exception as e:
            logger.error(f"❌ [GITHUB EMBEDDING] Error processing message: {e}")
            import traceback
            logger.error(f"❌ [GITHUB EMBEDDING] Full traceback: {traceback.format_exc()}")
            return False

    async def _process_entity(self, tenant_id: int, entity_type: str, entity_id: str, message: Dict[str, Any]) -> bool:
        """Process a single GitHub entity for embedding."""
        try:
            # Initialize providers for this tenant if not already done
            if not self.hybrid_provider.providers:
                logger.info(f"🔄 [GITHUB EMBEDDING] Initializing providers for tenant {tenant_id}")
                init_success = await self.hybrid_provider.initialize_providers(tenant_id)
                if not init_success:
                    logger.error(f"❌ [GITHUB EMBEDDING] Failed to initialize providers for tenant {tenant_id}")
                    return False

            # Fetch entity data
            entity_data = await self._fetch_entity_data(tenant_id, entity_type, entity_id)
            if not entity_data:
                logger.debug(f"🔍 [GITHUB EMBEDDING] Entity not found: {entity_type} ID {entity_id}")
                return True  # Not an error, entity might have been deleted

            # Generate embedding
            text_content = self._extract_text_content(entity_data, entity_type)
            if not text_content:
                logger.debug(f"🔍 [GITHUB EMBEDDING] No text content for {entity_type} ID {entity_id}")
                return True  # Not an error, just no content to embed

            # Generate embedding vector
            embedding_result = await self.hybrid_provider.generate_embeddings(
                texts=[text_content],
                tenant_id=tenant_id
            )
            if not embedding_result.success or not embedding_result.data:
                logger.error(f"❌ [GITHUB EMBEDDING] Failed to generate embedding: {embedding_result.error}")
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
                logger.debug(f"✅ [GITHUB EMBEDDING] Successfully processed {entity_type} ID {entity_id}")
            else:
                logger.error(f"❌ [GITHUB EMBEDDING] Failed to store embedding for {entity_type} ID {entity_id}")

            return success

        except Exception as e:
            logger.error(f"❌ [GITHUB EMBEDDING] Error processing {entity_type} entity {entity_id}: {e}")
            import traceback
            logger.error(f"❌ [GITHUB EMBEDDING] Full traceback: {traceback.format_exc()}")
            return False

    async def _fetch_entity_data(self, tenant_id: int, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch GitHub entity data from database for embedding generation."""
        try:
            logger.debug(f"🔍 [GITHUB EMBEDDING] Fetching {entity_type} with external_id={entity_id}, tenant_id={tenant_id}")
            database = get_database()

            # 🔑 Use WRITE session for reads to ensure we read from primary
            with database.get_write_session_context() as session:
                if entity_type == 'prs':
                    # 🔑 RETRY LOOP: Wait for data to be committed by transform worker
                    max_retries = 5
                    retry_delay = 0.1  # 100ms between retries
                    entity = None

                    for attempt in range(max_retries):
                        entity = session.query(Pr).filter(
                            Pr.external_id == str(entity_id),
                            Pr.tenant_id == tenant_id
                        ).first()

                        if entity:
                            logger.info(f"✅ Found PR entity (attempt {attempt + 1}/{max_retries}): id={entity.id}, external_id={entity.external_id}")
                            break
                        elif attempt < max_retries - 1:
                            logger.warning(f"⏳ PR not found yet (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                            time.sleep(retry_delay)

                    if entity:
                        return {
                            'id': entity.id,
                            'external_id': entity.external_id,
                            'title': entity.name,  # Column is 'name', not 'title'
                            'description': entity.body,  # Column is 'body', not 'description'
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'prs_commits':
                    # 🔑 RETRY LOOP: Wait for data to be committed by transform worker
                    max_retries = 5
                    retry_delay = 0.1  # 100ms between retries
                    entity = None

                    for attempt in range(max_retries):
                        entity = session.query(PrCommit).filter(
                            PrCommit.external_id == str(entity_id),
                            PrCommit.tenant_id == tenant_id
                        ).first()

                        if entity:
                            logger.info(f"✅ Found commit entity (attempt {attempt + 1}/{max_retries}): id={entity.id}, external_id={entity.external_id}")
                            break
                        elif attempt < max_retries - 1:
                            logger.warning(f"⏳ Commit not found yet (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                            time.sleep(retry_delay)

                    if entity:
                        return {
                            'id': entity.id,
                            'external_id': entity.external_id,
                            'message': entity.message,
                            'author_name': entity.author_name,
                            'author_email': entity.author_email,
                            'committer_name': entity.committer_name,
                            'committer_email': entity.committer_email,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'prs_reviews':
                    # 🔑 RETRY LOOP: Wait for data to be committed by transform worker
                    max_retries = 5
                    retry_delay = 0.1  # 100ms between retries
                    entity = None

                    for attempt in range(max_retries):
                        entity = session.query(PrReview).filter(
                            PrReview.external_id == str(entity_id),
                            PrReview.tenant_id == tenant_id
                        ).first()

                        if entity:
                            logger.info(f"✅ Found review entity (attempt {attempt + 1}/{max_retries}): id={entity.id}, external_id={entity.external_id}")
                            break
                        elif attempt < max_retries - 1:
                            logger.warning(f"⏳ Review not found yet (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                            time.sleep(retry_delay)

                    if entity:
                        return {
                            'id': entity.id,
                            'external_id': entity.external_id,
                            'body': entity.body,
                            'state': entity.state,
                            'author_login': entity.author_login,
                            'submitted_at': entity.submitted_at,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'prs_comments':
                    # 🔑 RETRY LOOP: Wait for data to be committed by transform worker
                    max_retries = 5
                    retry_delay = 0.1  # 100ms between retries
                    entity = None

                    for attempt in range(max_retries):
                        entity = session.query(PrComment).filter(
                            PrComment.external_id == str(entity_id),
                            PrComment.tenant_id == tenant_id
                        ).first()

                        if entity:
                            logger.info(f"✅ Found comment entity (attempt {attempt + 1}/{max_retries}): id={entity.id}, external_id={entity.external_id}")
                            break
                        elif attempt < max_retries - 1:
                            logger.warning(f"⏳ Comment not found yet (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                            time.sleep(retry_delay)

                    if entity:
                        return {
                            'id': entity.id,
                            'external_id': entity.external_id,
                            'body': entity.body,
                            'author_login': entity.author_login,
                            'comment_type': entity.comment_type,
                            'path': entity.path,
                            'line': entity.line,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                elif entity_type == 'repositories':
                    entity = session.query(Repository).filter(
                        Repository.external_id == str(entity_id),
                        Repository.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,
                            'external_id': entity.external_id,
                            'name': entity.name,
                            'full_name': entity.full_name,
                            'owner': entity.owner,
                            'description': entity.description,
                            'language': entity.language,
                            'visibility': entity.visibility,
                            'topics': entity.topics,
                            'stargazers_count': entity.stargazers_count,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

                else:
                    logger.warning(f"⚠️ [GITHUB EMBEDDING] Unknown entity type: {entity_type}")
                    return None

            return None

        except Exception as e:
            logger.error(f"❌ [GITHUB EMBEDDING] Error fetching {entity_type} entity {entity_id}: {e}")
            return None

    def _extract_text_content(self, entity_data: Dict[str, Any], entity_type: str) -> str:
        """Extract text content from GitHub entity data for embedding generation."""
        text_parts = []
        logger.debug(f"🔍 [GITHUB EMBEDDING] Extracting text content for {entity_type}: {entity_data}")

        if entity_type == 'prs':
            if entity_data.get('title'):
                text_parts.append(f"Title: {entity_data['title']}")
            if entity_data.get('description'):
                text_parts.append(f"Description: {entity_data['description']}")

        elif entity_type == 'prs_commits':
            if entity_data.get('message'):
                text_parts.append(f"Message: {entity_data['message']}")
            if entity_data.get('author_name'):
                text_parts.append(f"Author: {entity_data['author_name']}")
            if entity_data.get('author_email'):
                text_parts.append(f"Email: {entity_data['author_email']}")
            if entity_data.get('committer_name'):
                text_parts.append(f"Committer: {entity_data['committer_name']}")

        elif entity_type == 'prs_reviews':
            if entity_data.get('body'):
                text_parts.append(f"Review: {entity_data['body']}")
            if entity_data.get('state'):
                text_parts.append(f"State: {entity_data['state']}")
            if entity_data.get('author_login'):
                text_parts.append(f"Reviewer: {entity_data['author_login']}")

        elif entity_type == 'prs_comments':
            if entity_data.get('body'):
                text_parts.append(f"Comment: {entity_data['body']}")
            if entity_data.get('author_login'):
                text_parts.append(f"Author: {entity_data['author_login']}")

        elif entity_type == 'repositories':
            if entity_data.get('full_name'):
                text_parts.append(f"Repository: {entity_data['full_name']}")
            if entity_data.get('description'):
                text_parts.append(f"Description: {entity_data['description']}")
            if entity_data.get('language'):
                text_parts.append(f"Language: {entity_data['language']}")
            if entity_data.get('topics'):
                topics_str = ', '.join(entity_data['topics']) if isinstance(entity_data['topics'], list) else str(entity_data['topics'])
                text_parts.append(f"Topics: {topics_str}")
            if entity_data.get('stargazers_count'):
                text_parts.append(f"Stars: {entity_data['stargazers_count']}")
            if entity_data.get('visibility'):
                text_parts.append(f"Visibility: {entity_data['visibility']}")

        result = " ".join(text_parts)
        logger.debug(f"✅ [GITHUB EMBEDDING] Extracted text for {entity_type}: {result[:100] if result else 'EMPTY'}")
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
                logger.error(f"❌ [GITHUB EMBEDDING] Failed to store in Qdrant")
                return False

            # Update qdrant_vectors bridge table
            bridge_success = await self._update_bridge_table(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                message=message
            )

            if not bridge_success:
                logger.error(f"❌ [GITHUB EMBEDDING] Failed to update bridge table")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ [GITHUB EMBEDDING] Error storing embedding: {e}")
            import traceback
            logger.error(f"❌ [GITHUB EMBEDDING] Full traceback: {traceback.format_exc()}")
            return False

    async def _store_in_qdrant(self, tenant_id: int, entity_type: str, entity_id: int,
                               embedding_vector: list, entity_data: Dict[str, Any]) -> bool:
        """Store embedding vector in Qdrant."""
        try:
            from app.ai.qdrant_manager import QdrantManager
            qdrant_manager = QdrantManager()

            # Create tenant-specific collection name
            collection_name = f"tenant_{tenant_id}"

            # Store vector with metadata
            success = await qdrant_manager.upsert_vector(
                collection_name=collection_name,
                vector_id=f"{entity_type}_{entity_id}",
                vector=embedding_vector,
                payload={
                    'tenant_id': tenant_id,
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'external_id': entity_data.get('external_id'),
                    **entity_data
                }
            )

            if success:
                logger.debug(f"✅ [GITHUB EMBEDDING] Stored in Qdrant: {entity_type} ID {entity_id}")
            else:
                logger.error(f"❌ [GITHUB EMBEDDING] Failed to store in Qdrant: {entity_type} ID {entity_id}")

            return success

        except Exception as e:
            logger.error(f"❌ [GITHUB EMBEDDING] Error storing in Qdrant: {e}")
            return False

    async def _update_bridge_table(self, tenant_id: int, entity_type: str, entity_id: int, message: Dict[str, Any]) -> bool:
        """Update qdrant_vectors bridge table."""
        try:
            from app.models.unified_models import QdrantVector
            from app.core.utils import DateTimeHelper

            database = get_database()

            with database.get_write_session_context() as session:
                # Check if record exists
                existing = session.query(QdrantVector).filter(
                    QdrantVector.tenant_id == tenant_id,
                    QdrantVector.entity_type == entity_type,
                    QdrantVector.entity_id == entity_id
                ).first()

                if existing:
                    # Update existing record
                    existing.last_updated_at = DateTimeHelper.default_now()
                    existing.active = True
                    logger.debug(f"✅ [GITHUB EMBEDDING] Updated bridge table: {entity_type} ID {entity_id}")
                else:
                    # Insert new record
                    new_record = QdrantVector(
                        tenant_id=tenant_id,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        active=True,
                        created_at=DateTimeHelper.default_now(),
                        last_updated_at=DateTimeHelper.default_now()
                    )
                    session.add(new_record)
                    logger.debug(f"✅ [GITHUB EMBEDDING] Inserted into bridge table: {entity_type} ID {entity_id}")

                session.commit()
                return True

        except Exception as e:
            logger.error(f"❌ [GITHUB EMBEDDING] Error updating bridge table: {e}")
            return False