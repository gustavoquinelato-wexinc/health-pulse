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

            # Update job status to EMBEDDING
            job_id = message.get('job_id')
            tenant_id = message.get('tenant_id')
            table_name = message.get('table_name')
            external_id = message.get('external_id')

            if job_id:
                self._update_job_status(job_id, "RUNNING", f"Creating embeddings for {table_name}")

            # Process the embedding message synchronously
            return self._process_embedding_message_sync(message)

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
            return asyncio.run(self._process_embedding_message(message))
        except Exception as e:
            logger.error(f"❌ EMBEDDING WORKER: Error in sync wrapper: {e}")
            return False


    async def _process_embedding_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a single embedding message from the queue.
        
        Args:
            message: Message containing tenant_id, entity_type, entity_id, etc.
            
        Returns:
            bool: True if processed successfully, False otherwise
        """
        try:
            logger.debug(f"🔍 EMBEDDING WORKER: Received message: {message}")
            tenant_id = message.get('tenant_id')
            message_type = message.get('type')

            # Handle mapping tables differently - bulk process entire table
            if message_type == 'mappings':
                table_name = message.get('table_name')
                if not all([tenant_id, table_name]):
                    logger.error(f"❌ EMBEDDING WORKER: Missing required fields for mappings message: {message}")
                    return False

                logger.info(f"🔄 EMBEDDING WORKER: Processing entire {table_name} table for tenant {tenant_id}")
                return await self._process_mapping_table(tenant_id, table_name)

            # Handle individual entity messages (existing logic)
            entity_type = message.get('entity_type') or message.get('table_name')
            entity_id = message.get('entity_id') or message.get('external_id')
            operation = message.get('operation', 'insert')

            logger.debug(f"🔍 EMBEDDING WORKER: Parsed - tenant_id: {tenant_id}, entity_type: {entity_type}, entity_id: {entity_id}, operation: {operation}")

            if not all([tenant_id, entity_type, entity_id]):
                logger.error(f"❌ EMBEDDING WORKER: Invalid message format: {message}")
                return False

            # Initialize providers for this tenant if not already done
            if not await self.hybrid_provider.initialize_providers(tenant_id):
                logger.error(f"❌ EMBEDDING WORKER: Failed to initialize providers for tenant {tenant_id}")
                return False

            logger.info(f"🔄 EMBEDDING WORKER: Processing {entity_type} ID {entity_id} for tenant {tenant_id}")
            
            # Update job status to EMBEDDING if this is the first embedding message
            job_id = message.get('job_id')
            if job_id:
                self._update_job_status(job_id, "EMBEDDING", f"Creating embeddings for {entity_type}")
            
            # Fetch entity from database
            logger.debug(f"🔍 EMBEDDING WORKER: Fetching entity data for {entity_type} ID {entity_id}")
            # Convert entity_id to int for database query
            try:
                entity_id_int = int(entity_id)
            except (ValueError, TypeError):
                logger.error(f"❌ EMBEDDING WORKER: Invalid entity_id format: {entity_id}")
                return False
            entity_data = await self._fetch_entity_data(tenant_id, entity_type, entity_id_int)
            if not entity_data:
                logger.debug(f"🔍 EMBEDDING WORKER: Entity not found: {entity_type} ID {entity_id} (likely from old queue messages)")
                return True  # Not an error, entity might have been deleted
            logger.debug(f"✅ EMBEDDING WORKER: Entity data fetched: {entity_data.keys() if entity_data else 'None'}")
            
            # Generate embedding
            logger.debug(f"🧠 EMBEDDING WORKER: Generating embedding for {entity_type} ID {entity_id}")
            embedding_vector = await self._generate_embedding(entity_data, entity_type)
            if not embedding_vector:
                logger.error(f"❌ EMBEDDING WORKER: Failed to generate embedding for {entity_type} ID {entity_id}")
                return False
            logger.debug(f"✅ EMBEDDING WORKER: Embedding generated, vector length: {len(embedding_vector) if embedding_vector else 0}")
            
            # Store in Qdrant and update bridge table
            logger.debug(f"💾 EMBEDDING WORKER: Storing embedding for {entity_type} ID {entity_id}")
            success = await self._store_embedding(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id_int,
                embedding_vector=embedding_vector,
                entity_data=entity_data,
                message=message
            )
            logger.debug(f"📊 EMBEDDING WORKER: Storage result for {entity_type} ID {entity_id}: {success}")
            
            if success:
                logger.info(f"✅ EMBEDDING WORKER: Successfully processed {entity_type} ID {entity_id}")

                # ✅ Handle ETL job completion for last_item
                if message.get('last_item'):
                    logger.info(f"🏁 EMBEDDING WORKER: Processing last item - completing ETL job")

                    etl_job_id = message.get('etl_job_id')
                    last_sync_date = message.get('last_sync_date')
                    provider_name = message.get('provider_name')

                    if etl_job_id and last_sync_date:
                        # Import and use the complete_etl_job function
                        from app.workers.transform_worker import complete_etl_job
                        complete_etl_job(etl_job_id, last_sync_date, tenant_id)
                        logger.info(f"✅ EMBEDDING WORKER: ETL job {etl_job_id} completed successfully")
                    else:
                        logger.warning(f"EMBEDDING WORKER: Missing etl_job_id or last_sync_date for completion: job_id={etl_job_id}, sync_date={last_sync_date}")

                return True
            else:
                logger.error(f"❌ EMBEDDING WORKER: Failed to store embedding for {entity_type} ID {entity_id}")
                return False
                
        except Exception as e:
            import traceback
            logger.error(f"❌ EMBEDDING WORKER: Error processing message {message}: {e}")
            logger.error(f"❌ EMBEDDING WORKER: Full traceback: {traceback.format_exc()}")
            return False
        finally:
            # Cleanup AI providers to prevent event loop errors
            try:
                if hasattr(self, 'hybrid_provider') and self.hybrid_provider:
                    await self.hybrid_provider.cleanup()
                    logger.debug("🧹 EMBEDDING WORKER: Cleaned up AI providers after message processing")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ EMBEDDING WORKER: Error during cleanup: {cleanup_error}")

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
                    entity = session.query(Project).filter(
                        Project.external_id == str(entity_id),
                        Project.tenant_id == tenant_id
                    ).first()

                    if entity:
                        return {
                            'id': entity.id,  # Internal ID for qdrant_vectors table
                            'external_id': entity.external_id,
                            'key': entity.key,
                            'name': entity.name,
                            'project_type': entity.project_type,
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
                            'id': entity.id,  # Internal ID for qdrant_vectors table
                            'external_id': entity.external_id,
                            'original_name': entity.original_name,
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
                            'id': entity.id,  # Internal ID for qdrant_vectors table
                            'external_id': entity.external_id,
                            'original_name': entity.original_name,
                            'category': entity.category,
                            'description': entity.description,
                            'entity_type': entity_type,
                            'tenant_id': tenant_id
                        }

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
        
        return " ".join(text_parts)

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
            # Use PulseQdrantClient to store in Qdrant
            from app.ai.qdrant_client import PulseQdrantClient

            qdrant_client = PulseQdrantClient()
            await qdrant_client.initialize()

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
            from app.models.unified_models import QdrantVector
            database = get_database()

            # Use the existing SOURCE_TYPE_MAPPING for consistency
            source_type = SOURCE_TYPE_MAPPING.get(entity_type, 'UNKNOWN')

            # If integration_id is not provided, try to find the appropriate integration
            if integration_id is None:
                integration_id = await self._get_integration_id_for_source_type(tenant_id, source_type)
                if integration_id is None:
                    logger.error(f"❌ EMBEDDING WORKER: No integration_id found for {source_type} in tenant {tenant_id}")
                    return False

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

    def _update_job_status(self, job_id: int, status: str, message: str = None):
        """Update ETL job status."""
        try:
            from app.core.database import get_database
            from sqlalchemy import text

            database = get_database()
            with database.get_write_session_context() as session:
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = :status, last_updated_at = NOW()
                    WHERE id = :job_id
                """)

                session.execute(update_query, {
                    'status': status,
                    'job_id': job_id
                })
                session.commit()

                logger.info(f"Updated job {job_id} status to {status}")
                if message:
                    logger.info(f"Job {job_id} message: {message}")

        except Exception as e:
            logger.error(f"Error updating job status: {e}")


