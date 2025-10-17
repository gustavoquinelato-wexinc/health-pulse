"""
Embedding helper for ETL jobs - handles async embedding queue operations.
"""

import asyncio
import httpx
from typing import List, Dict, Any, Optional
from app.core.logging_config import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)


class EmbeddingQueueHelper:
    """Helper class for managing embedding queue operations."""
    
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        # Get backend URL from settings instead of requiring it as parameter
        settings = get_settings()
        self.backend_url = settings.BACKEND_SERVICE_URL
        # Note: In-memory queue removed - entities are saved immediately to database
    
    def queue_entities_for_embedding(
        self,
        entities_inserted: List[Dict[str, Any]],
        table_name: str,
        operation: str = "insert"
    ) -> int:
        """
        Queue entities for async embedding and immediately save to database.

        Args:
            entities_inserted: List of entity dictionaries with data
            table_name: Name of the table (work_items, changelogs, etc.)
            operation: Operation type ('insert', 'update', 'delete')

        Returns:
            Number of entities queued
        """
        # Validate table name
        valid_tables = ["work_items", "changelogs", "projects", "statuses", "wits",
                       "prs", "prs_commits", "prs_reviews", "prs_comments", "wits_prs_links", "repositories"]
        if table_name not in valid_tables:
            logger.warning(f"Unknown table name for embedding: {table_name}")
            return 0

        queue_entries = []
        
        for entity_data in entities_inserted:
            # Prepare entity data for embedding
            entity_content = self._prepare_entity_content(entity_data, table_name)
            
            # Prepare qdrant metadata
            qdrant_metadata = self._prepare_qdrant_metadata(entity_data, table_name)
            
            queue_entry = {
                "tenant_id": self.tenant_id,
                "table_name": table_name,
                "external_id": str(entity_data.get("external_id", entity_data.get("id", ""))),
                "operation": operation,
                "entity_content": entity_content,
                "qdrant_metadata": qdrant_metadata,
                "status": "pending",
                "retry_count": 0
            }
            
            queue_entries.append(queue_entry)

        # Save to database immediately (no in-memory queue)
        if queue_entries:
            self._save_queue_entries_to_database(queue_entries)
            logger.info(f"Queued {len(queue_entries)} {table_name} entities for embedding")

        return len(queue_entries)
    
    def _prepare_entity_content(self, entity_data: Dict[str, Any], table_name: str) -> Dict[str, Any]:
        """Prepare entity content for embedding based on table type."""
        
        if table_name == "work_items":
            return {
                "title": entity_data.get("title", ""),
                "description": entity_data.get("description", ""),
                "key": entity_data.get("key", ""),
                "status": entity_data.get("status", ""),
                "priority": entity_data.get("priority", ""),
                "assignee": entity_data.get("assignee", ""),
                "reporter": entity_data.get("reporter", ""),
                "labels": entity_data.get("labels", []),
                "components": entity_data.get("components", [])
            }
        
        elif table_name == "changelogs":
            return {
                "field_name": entity_data.get("field_name", ""),
                "from_value": entity_data.get("from_value", ""),
                "to_value": entity_data.get("to_value", ""),
                "author": entity_data.get("author", ""),
                "created_at": str(entity_data.get("created_at", ""))
            }
        
        elif table_name == "projects":
            return {
                "name": entity_data.get("name", ""),
                "key": entity_data.get("key", ""),
                "description": entity_data.get("description", ""),
                "lead": entity_data.get("lead", ""),
                "project_type": entity_data.get("project_type", "")
            }
        
        elif table_name == "statuses":
            return {
                "name": entity_data.get("name", ""),
                "description": entity_data.get("description", ""),
                "category": entity_data.get("category", "")
            }
        
        elif table_name == "wits":
            return {
                "name": entity_data.get("original_name", entity_data.get("name", "")),
                "description": entity_data.get("description", ""),
                "hierarchy_level": str(entity_data.get("hierarchy_level", "")),
                "subtask": str(entity_data.get("subtask", False))
            }
        
        elif table_name == "prs":
            return {
                "title": entity_data.get("title", ""),
                "description": entity_data.get("description", ""),
                "state": entity_data.get("state", ""),
                "author": entity_data.get("author", ""),
                "base_branch": entity_data.get("base_branch", ""),
                "head_branch": entity_data.get("head_branch", "")
            }
        
        elif table_name == "prs_commits":
            return {
                "message": entity_data.get("message", ""),
                "author": entity_data.get("author", ""),
                "sha": entity_data.get("sha", "")
            }
        
        elif table_name == "prs_reviews":
            return {
                "body": entity_data.get("body", ""),
                "state": entity_data.get("state", ""),
                "author": entity_data.get("author", "")
            }
        
        elif table_name == "prs_comments":
            return {
                "body": entity_data.get("body", ""),
                "author": entity_data.get("author", ""),
                "comment_type": entity_data.get("comment_type", "")
            }
        
        elif table_name == "repositories":
            return {
                "name": entity_data.get("name", ""),
                "description": entity_data.get("description", ""),
                "language": entity_data.get("language", ""),
                "topics": entity_data.get("topics", [])
            }
        
        elif table_name == "wits_prs_links":
            return {
                "link_type": entity_data.get("link_type", ""),
                "work_item_key": entity_data.get("work_item_key", ""),
                "pr_title": entity_data.get("pr_title", "")
            }
        
        else:
            # Default: return all string fields
            return {k: str(v) for k, v in entity_data.items() if isinstance(v, (str, int, float))}
    
    def _prepare_qdrant_metadata(self, entity_data: Dict[str, Any], table_name: str) -> Dict[str, Any]:
        """Prepare metadata for Qdrant storage."""
        
        base_metadata = {
            "table_name": table_name,
            "tenant_id": self.tenant_id,
            "external_id": str(entity_data.get("external_id", entity_data.get("id", ""))),
            "created_at": str(entity_data.get("created_at", "")),
            "updated_at": str(entity_data.get("updated_at", ""))
        }
        
        # Add table-specific metadata
        if table_name == "work_items":
            base_metadata.update({
                "project_key": entity_data.get("project_key", ""),
                "wit_name": entity_data.get("wit_name", ""),
                "status": entity_data.get("status", ""),
                "priority": entity_data.get("priority", "")
            })
        
        elif table_name == "projects":
            base_metadata.update({
                "project_key": entity_data.get("key", ""),
                "project_type": entity_data.get("project_type", "")
            })
        
        elif table_name == "prs":
            base_metadata.update({
                "repository_name": entity_data.get("repository_name", ""),
                "state": entity_data.get("state", ""),
                "author": entity_data.get("author", "")
            })
        
        return base_metadata
    
    def _save_queue_entries_to_database(self, queue_entries: List[Dict[str, Any]]):
        """Save queue entries directly to database."""
        try:
            from app.core.database import get_database
            from app.models.unified_models import EmbeddingQueue
            
            database = get_database()
            with database.get_write_session_context() as session:
                for entry in queue_entries:
                    queue_record = EmbeddingQueue(
                        tenant_id=entry["tenant_id"],
                        table_name=entry["table_name"],
                        external_id=entry["external_id"],
                        operation=entry["operation"],
                        entity_content=entry["entity_content"],
                        qdrant_metadata=entry["qdrant_metadata"],
                        status=entry["status"],
                        retry_count=entry["retry_count"]
                    )
                    session.add(queue_record)
                
                session.commit()
                logger.info(f"Saved {len(queue_entries)} queue entries to database")
                
        except Exception as e:
            logger.error(f"Failed to save queue entries to database: {e}")
            raise
