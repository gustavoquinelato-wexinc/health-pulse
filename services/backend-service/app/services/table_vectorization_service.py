"""
Table-specific vectorization service for admin pages.
Provides direct vectorization of specific tables without job queue system.
"""

import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_database
from app.ai.qdrant_client import PulseQdrantClient
from app.ai.hybrid_provider_manager import HybridProviderManager
from app.models.unified_models import (
    WitHierarchy, WitMapping, StatusMapping, Workflow,
    WorkItem, Status, Wit, Project, Repository, Pr,
    PrComment, PrCommit, PrReview, Changelog, QdrantVector
)
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def create_text_content_from_admin_entity(entity_data: Dict[str, Any], table_name: str) -> str:
    """Create text content for vectorization based on admin entity type"""
    try:
        if entity_data is None or not isinstance(entity_data, dict):
            logger.warning(f"[TEXT_CONTENT] Invalid entity data for table '{table_name}'")
            return ""

        logger.debug(f"[TEXT_CONTENT] Creating text content for table '{table_name}' with data keys: {list(entity_data.keys())}")

        if table_name == "wits_hierarchies":
            parts = []
            if entity_data.get("parent_name"):
                parts.append(f"Parent: {entity_data['parent_name']}")
            if entity_data.get("child_name"):
                parts.append(f"Child: {entity_data['child_name']}")
            if entity_data.get("hierarchy_level"):
                parts.append(f"Level: {entity_data['hierarchy_level']}")
            return " | ".join(parts)

        elif table_name == "wits_mappings":
            parts = []
            if entity_data.get("external_name"):
                parts.append(f"External: {entity_data['external_name']}")
            if entity_data.get("internal_name"):
                parts.append(f"Internal: {entity_data['internal_name']}")
            if entity_data.get("mapping_type"):
                parts.append(f"Type: {entity_data['mapping_type']}")
            return " | ".join(parts)

        elif table_name == "statuses_mappings":
            parts = []
            if entity_data.get("external_status"):
                parts.append(f"External: {entity_data['external_status']}")
            if entity_data.get("internal_status"):
                parts.append(f"Internal: {entity_data['internal_status']}")
            if entity_data.get("status_category"):
                parts.append(f"Category: {entity_data['status_category']}")
            return " | ".join(parts)

        elif table_name == "workflows":
            parts = []
            if entity_data.get("name"):
                parts.append(f"Name: {entity_data['name']}")
            if entity_data.get("description"):
                parts.append(f"Description: {entity_data['description']}")
            if entity_data.get("workflow_type"):
                parts.append(f"Type: {entity_data['workflow_type']}")
            return " | ".join(parts)

        else:
            # Generic fallback
            content = " | ".join([f"{k}: {v}" for k, v in entity_data.items() if v and k not in ["id", "external_id", "tenant_id", "integration_id"]])
            logger.debug(f"[TEXT_CONTENT] Generic fallback for table '{table_name}': '{content[:100]}...' (length: {len(content)})")
            return content

    except Exception as e:
        logger.error(f"[TEXT_CONTENT] Error creating text content for {table_name}: {e}")
        return ""


class TableVectorizationService:
    """Service for table-specific vectorization operations."""
    
    # Table name mapping for validation and processing
    TABLE_MAPPING = {
        "wits_hierarchies": {
            "model": WitHierarchy,
            "display_name": "WITs Hierarchies",
            "collection_suffix": "wits_hierarchies"
        },
        "wits_mappings": {
            "model": WitMapping,
            "display_name": "WITs Mappings", 
            "collection_suffix": "wits_mappings"
        },
        "statuses_mappings": {
            "model": StatusMapping,
            "display_name": "Status Mappings",
            "collection_suffix": "statuses_mappings"
        },
        "workflows": {
            "model": Workflow,
            "display_name": "Workflows",
            "collection_suffix": "workflows"
        }
    }
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
    
    def _generate_session_id(self, table_name: str) -> str:
        """Generate unique session ID for tracking progress."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"vec_{table_name}_{timestamp}_{str(uuid.uuid4())[:8]}"
    
    def _validate_table_name(self, table_name: str) -> bool:
        """Validate if table name is supported for vectorization."""
        return table_name in self.TABLE_MAPPING
    
    async def get_table_item_count(self, table_name: str, tenant_id: int, integration_id: Optional[int] = None) -> int:
        """Get total count of items in table for tenant."""
        if not self._validate_table_name(table_name):
            raise ValueError(f"Unsupported table name: {table_name}")
        
        model = self.TABLE_MAPPING[table_name]["model"]
        
        database = get_database()
        with database.get_read_session_context() as db:
            query = db.query(model).filter(model.tenant_id == tenant_id)
            if integration_id:
                query = query.filter(model.integration_id == integration_id)
            return query.count()
    
    async def get_table_status(self, table_name: str, tenant_id: int) -> Dict[str, Any]:
        """Get vectorization status for a specific table."""
        if not self._validate_table_name(table_name):
            raise ValueError(f"Unsupported table name: {table_name}")
        
        try:
            # Get item count from database
            total_items = await self.get_table_item_count(table_name, tenant_id)
            
            # Get vector count from Qdrant
            qdrant_client = PulseQdrantClient()
            await qdrant_client.initialize()
            collection_name = f"client_{tenant_id}_{self.TABLE_MAPPING[table_name]['collection_suffix']}"

            try:
                collection_info = await asyncio.get_event_loop().run_in_executor(
                    None, qdrant_client.client.get_collection, collection_name
                )
                vector_count = collection_info.vectors_count if collection_info else 0
            except Exception:
                vector_count = 0
            
            # Check for active session
            active_session = None
            for session_id, session_data in self.active_sessions.items():
                if (session_data.get("table_name") == table_name and 
                    session_data.get("tenant_id") == tenant_id):
                    active_session = session_data
                    break
            
            return {
                "table_name": table_name,
                "display_name": self.TABLE_MAPPING[table_name]["display_name"],
                "total_items": total_items,
                "vectorized_items": vector_count,
                "qdrant_collection": collection_name,
                "status": active_session["status"] if active_session else "idle",
                "session_id": active_session["session_id"] if active_session else None,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting table status for {table_name}: {str(e)}")
            raise
    
    async def start_table_vectorization(self, table_name: str, tenant_id: int, integration_id: Optional[int] = None) -> Dict[str, Any]:
        """Start vectorization process for a specific table."""
        if not self._validate_table_name(table_name):
            raise ValueError(f"Unsupported table name: {table_name}")
        
        # Check if there's already an active session for this table
        for session_data in self.active_sessions.values():
            if (session_data.get("table_name") == table_name and 
                session_data.get("tenant_id") == tenant_id and
                session_data.get("status") in ["processing", "starting"]):
                raise ValueError(f"Vectorization already in progress for {table_name}")
        
        # Generate session ID
        session_id = self._generate_session_id(table_name)
        
        # Get total items count
        total_items = await self.get_table_item_count(table_name, tenant_id, integration_id)
        
        if total_items == 0:
            return {
                "session_id": session_id,
                "table_name": table_name,
                "total_items": 0,
                "status": "completed",
                "message": "No items to vectorize"
            }
        
        # Initialize session tracking
        self.active_sessions[session_id] = {
            "session_id": session_id,
            "table_name": table_name,
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "total_items": total_items,
            "processed_items": 0,
            "status": "starting",
            "started_at": datetime.now(),
            "current_item": None,
            "error": None
        }
        
        # Start vectorization in background
        asyncio.create_task(self._process_table_vectorization(session_id))
        
        return {
            "session_id": session_id,
            "table_name": table_name,
            "total_items": total_items,
            "status": "starting"
        }
    
    async def get_session_progress(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get progress for a specific vectorization session."""
        session_data = self.active_sessions.get(session_id)
        if not session_data:
            return None
        
        progress_percentage = 0
        if session_data["total_items"] > 0:
            progress_percentage = int((session_data["processed_items"] / session_data["total_items"]) * 100)
        
        return {
            "session_id": session_id,
            "table_name": session_data["table_name"],
            "processed": session_data["processed_items"],
            "total": session_data["total_items"],
            "status": session_data["status"],
            "progress_percentage": progress_percentage,
            "current_item": session_data.get("current_item"),
            "error": session_data.get("error"),
            "started_at": session_data["started_at"].isoformat()
        }
    
    async def _process_table_vectorization(self, session_id: str):
        """Background task to process table vectorization."""
        session_data = self.active_sessions.get(session_id)
        if not session_data:
            return
        
        try:
            session_data["status"] = "processing"
            
            table_name = session_data["table_name"]
            tenant_id = session_data["tenant_id"]
            integration_id = session_data.get("integration_id")
            
            model = self.TABLE_MAPPING[table_name]["model"]
            
            logger.info(f"[TABLE_VECTORIZATION] Starting vectorization for {table_name}, tenant {tenant_id}")

            # Initialize AI components
            database = get_database()
            with database.get_write_session_context() as db_session:
                # Initialize provider manager
                provider_manager = HybridProviderManager(db_session)
                await provider_manager.initialize_providers(tenant_id)

                # Initialize Qdrant client
                qdrant_client = PulseQdrantClient()
                await qdrant_client.initialize()

                # Get all items from table
                query = db_session.query(model).filter(model.tenant_id == tenant_id)
                if integration_id:
                    query = query.filter(model.integration_id == integration_id)

                items = query.all()
                total_items = len(items)

                logger.info(f"[TABLE_VECTORIZATION] Found {total_items} items to process")

                if total_items == 0:
                    session_data["status"] = "completed"
                    session_data["completed_at"] = datetime.utcnow()
                    return

                session_data["total_items"] = total_items
                vectors_stored = 0
                vectors_failed = 0

                # Process items in batches
                batch_size = 10
                for i in range(0, total_items, batch_size):
                    if session_data["status"] == "cancelled":
                        return

                    batch = items[i:i + batch_size]

                    # Prepare batch data for vectorization
                    entity_texts = []
                    entity_metadata = []

                    for item in batch:
                        try:
                            # Convert SQLAlchemy object to dict
                            entity_data = {c.name: getattr(item, c.name) for c in item.__table__.columns}

                            # Create text content
                            text_content = create_text_content_from_admin_entity(entity_data, table_name)

                            if text_content:
                                entity_texts.append(text_content)
                                entity_metadata.append({
                                    "entity_data": entity_data,
                                    "record_id": entity_data.get("id"),
                                    "table_name": table_name,
                                    "item": item
                                })

                                # Update current item being processed
                                session_data["current_item"] = self._get_item_display_name(item, table_name)
                            else:
                                vectors_failed += 1
                                logger.warning(f"[TABLE_VECTORIZATION] No text content for {table_name} item {entity_data.get('id')}")

                        except Exception as e:
                            vectors_failed += 1
                            logger.error(f"[TABLE_VECTORIZATION] Error preparing item: {e}")

                    # Generate embeddings for batch
                    if entity_texts:
                        try:
                            embedding_result = await provider_manager.generate_embeddings(entity_texts, tenant_id)

                            if embedding_result.success and embedding_result.data:
                                # Store vectors in Qdrant
                                for embedding, metadata in zip(embedding_result.data, entity_metadata):
                                    try:
                                        await self._store_vector_in_qdrant(
                                            qdrant_client, embedding, metadata, tenant_id,
                                            embedding_result.provider_used, db_session
                                        )
                                        vectors_stored += 1
                                    except Exception as e:
                                        vectors_failed += 1
                                        logger.error(f"[TABLE_VECTORIZATION] Error storing vector: {e}")
                            else:
                                vectors_failed += len(entity_texts)
                                logger.error(f"[TABLE_VECTORIZATION] Embedding generation failed: {embedding_result.error}")

                        except Exception as e:
                            vectors_failed += len(entity_texts)
                            logger.error(f"[TABLE_VECTORIZATION] Error in batch processing: {e}")

                    # Update progress
                    session_data["processed_items"] = min(i + batch_size, total_items)
                    session_data["vectors_stored"] = vectors_stored
                    session_data["vectors_failed"] = vectors_failed

                    # Small delay between batches
                    await asyncio.sleep(0.1)

                # Commit all changes
                db_session.commit()

                # Mark as completed
                session_data["status"] = "completed"
                session_data["completed_at"] = datetime.utcnow()
                session_data["vectors_stored"] = vectors_stored
                session_data["vectors_failed"] = vectors_failed

                logger.info(f"[TABLE_VECTORIZATION] Completed: {vectors_stored} stored, {vectors_failed} failed")
            
        except Exception as e:
            logger.error(f"Error in table vectorization for session {session_id}: {str(e)}")
            session_data["status"] = "error"
            session_data["error"] = str(e)
        
        # Clean up session after 5 minutes
        await asyncio.sleep(300)
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]

    async def _store_vector_in_qdrant(self, qdrant_client: PulseQdrantClient, embedding: List[float],
                                    metadata: Dict[str, Any], tenant_id: int, provider_used: str,
                                    db_session: Session):
        """Store vector in Qdrant and create bridge record in PostgreSQL."""
        try:
            entity_data = metadata["entity_data"]
            record_id = metadata["record_id"]
            table_name = metadata["table_name"]

            collection_name = f"client_{tenant_id}_{self.TABLE_MAPPING[table_name]['collection_suffix']}"

            # Create deterministic UUID for point ID
            import uuid
            unique_string = f"{tenant_id}_{table_name}_{record_id}"
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

            # Ensure collection exists
            await qdrant_client.ensure_collection_exists(
                collection_name=collection_name,
                vector_size=len(embedding)
            )

            # Prepare vector data for upsert
            vector_data = [{
                'id': point_id,
                'vector': embedding,
                'payload': {
                    **entity_data,
                    'tenant_id': tenant_id,
                    'table_name': table_name,
                    'record_id': record_id
                }
            }]

            # Store in Qdrant
            store_result = await qdrant_client.upsert_vectors(
                collection_name=collection_name,
                vectors=vector_data
            )

            if store_result.success:
                # Create bridge record in PostgreSQL
                bridge_record = QdrantVector(
                    tenant_id=tenant_id,
                    table_name=table_name,
                    record_id=record_id,
                    qdrant_collection=collection_name,
                    qdrant_point_id=point_id,
                    vector_type="entity_embedding",
                    embedding_model=provider_used,
                    embedding_provider=provider_used
                )
                db_session.add(bridge_record)
                logger.debug(f"[TABLE_VECTORIZATION] Stored vector and bridge record for {table_name} {record_id}")
            else:
                raise Exception(f"Qdrant storage failed: {store_result.error}")

        except Exception as e:
            logger.error(f"[TABLE_VECTORIZATION] Error storing vector: {e}")
            raise
    
    def _get_item_display_name(self, item: Any, table_name: str) -> str:
        """Get display name for current item being processed."""
        if table_name == "wits_hierarchies":
            return f"{item.level_name} (Level {item.level_number})"
        elif table_name == "wits_mappings":
            return f"{item.wit_from} → {item.wit_to}"
        elif table_name == "statuses_mappings":
            return f"{item.status_from} → {item.status_to}"
        elif table_name == "workflows":
            return f"{item.step_name} (Step {item.step_number})"
        else:
            return f"Item {item.id}"
    

    
    async def cancel_session(self, session_id: str) -> bool:
        """Cancel an active vectorization session."""
        session_data = self.active_sessions.get(session_id)
        if not session_data:
            return False
        
        session_data["status"] = "cancelled"
        session_data["cancelled_at"] = datetime.utcnow()
        
        return True


# Global instance
table_vectorization_service = TableVectorizationService()
