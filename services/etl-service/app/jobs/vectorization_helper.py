"""
Vectorization helper for ETL jobs - handles async vectorization queue operations.
"""

import asyncio
import httpx
from typing import List, Dict, Any, Optional
from app.core.logging_config import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)


class VectorizationQueueHelper:
    """Helper class for managing vectorization queue operations."""
    
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        # Get backend URL from settings instead of requiring it as parameter
        settings = get_settings()
        self.backend_url = settings.BACKEND_SERVICE_URL
        # Note: In-memory queue removed - entities are saved immediately to database
    
    def queue_entities_for_vectorization(
        self,
        entities_inserted: List[Dict[str, Any]],
        table_name: str,
        operation: str = "insert"
    ) -> int:
        """
        Queue entities for async vectorization and immediately save to database.

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
            logger.warning(f"Unknown table name for vectorization: {table_name}")
            return 0

        queue_entries = []

        for entity in entities_inserted:
            # Prepare entity data based on table type
            entity_data = self._prepare_entity_data(entity, table_name)

            if not entity_data:
                continue

            # Pre-compute Qdrant metadata
            qdrant_metadata = {
                "collection_name": f"client_{self.tenant_id}_{table_name}",
                "record_id": entity.get("external_id"),
                "table_name": table_name
            }

            # Get the external ID - this will be used to join with actual tables during processing
            # Different entity types use different field names for external IDs
            external_id = None
            if table_name == "work_items":
                external_id = entity.get("key")  # Jira work items use "key" (e.g., "BDP-552")
            elif table_name == "changelogs":
                external_id = entity.get("external_id")  # Changelogs use "external_id"
            elif table_name in ["prs", "prs_commits", "prs_reviews", "prs_comments", "repositories"]:
                external_id = entity.get("external_id")  # GitHub entities use "external_id"
            elif table_name == "wits_prs_links":
                # Exception: WIT-PR links use internal database ID instead of external ID
                external_id = entity.get("id")  # Use database ID directly
            else:
                # Default fallback - try both field names
                external_id = entity.get("external_id") or entity.get("key")

            if external_id is None:
                logger.warning(f"No external identifier found for entity in table {table_name}. Tried 'external_id' and 'key'. Entity keys: {list(entity.keys())}")
                continue

            queue_entry = {
                "table_name": table_name,
                "external_id": str(external_id),  # Store as string for consistency
                "operation": operation,
                "entity_data": entity_data,
                "qdrant_metadata": qdrant_metadata,
                "tenant_id": self.tenant_id
            }

            queue_entries.append(queue_entry)

        # Immediately save to database instead of storing in memory
        if queue_entries:
            saved_count = self._save_queue_entries_immediately(queue_entries)
            logger.info(f"Immediately saved {saved_count} {table_name} entities to vectorization queue")
            return saved_count

        return 0

    def _save_queue_entries_immediately(self, queue_entries: List[Dict[str, Any]]) -> int:
        """
        Save queue entries immediately to database with duplicate handling.
        Uses UPSERT logic to handle cases where same commit appears in multiple PRs.

        Args:
            queue_entries: List of queue entry dictionaries

        Returns:
            Number of entries saved
        """
        try:
            from app.core.database import get_database
            from app.models.unified_models import VectorizationQueue
            from sqlalchemy.dialects.postgresql import insert

            database = get_database()
            with database.get_session_context() as session:
                # Use PostgreSQL UPSERT (ON CONFLICT DO NOTHING) to handle duplicates
                # This prevents unique constraint violations when same commit appears in multiple PRs

                if queue_entries:
                    # Build UPSERT statement
                    stmt = insert(VectorizationQueue).values(queue_entries)
                    # ON CONFLICT DO NOTHING - if duplicate exists, skip it
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=['table_name', 'external_id', 'operation', 'tenant_id']
                    )

                    result = session.execute(stmt)
                    session.commit()

                    # Get count of actually inserted rows (excludes duplicates)
                    inserted_count = result.rowcount
                    skipped_count = len(queue_entries) - inserted_count

                    if skipped_count > 0:
                        logger.debug(f"Vectorization queue: inserted {inserted_count}, skipped {skipped_count} duplicates")
                    else:
                        logger.debug(f"Successfully saved {inserted_count} entries to vectorization_queue")

                    return inserted_count
                else:
                    return 0

        except Exception as e:
            logger.error(f"Failed to save queue entries: {e}")
            # No fallback - if database save fails, we should know about it
            raise

    def _prepare_entity_data(self, entity: Dict[str, Any], table_name: str) -> Optional[Dict[str, Any]]:
        """Prepare entity data for vectorization based on table type."""
        
        if table_name == "changelogs":
            return {
                "external_id": entity.get("external_id"),
                "from_status_name": entity.get("from_status_name"),
                "to_status_name": entity.get("to_status_name"),
                "changed_by": entity.get("changed_by"),
                "transition_change_date": self._serialize_datetime(entity.get("transition_change_date")),
                "time_in_status_seconds": entity.get("time_in_status_seconds"),
                "work_item_key": entity.get("work_item_key")
            }
        
        elif table_name == "work_items":
            return {
                "key": entity.get("key"),
                "summary": entity.get("summary"),
                "description": entity.get("description"),
                "status_name": entity.get("status_name"),
                "wit_name": entity.get("wit_name"),
                "priority": entity.get("priority"),
                "assignee": entity.get("assignee"),
                "reporter": entity.get("reporter"),
                "created_date": self._serialize_datetime(entity.get("created_date")),
                "updated_date": self._serialize_datetime(entity.get("updated_date"))
            }
        
        elif table_name == "projects":
            return {
                "key": entity.get("key"),
                "name": entity.get("name"),
                "description": entity.get("description"),
                "project_type": entity.get("project_type"),
                "lead": entity.get("lead")
            }
        
        elif table_name == "statuses":
            return {
                "name": entity.get("name"),
                "description": entity.get("description"),
                "category": entity.get("category")
            }
        
        elif table_name == "wits":
            return {
                "name": entity.get("name"),
                "description": entity.get("description"),
                "icon_url": entity.get("icon_url")
            }
        
        elif table_name == "prs_commits":
            return {
                "sha": entity.get("sha"),
                "message": entity.get("message"),
                "author_name": entity.get("author_name"),
                "author_email": entity.get("author_email"),
                "authored_date": self._serialize_datetime(entity.get("authored_date")),
                "committed_date": self._serialize_datetime(entity.get("committed_date"))
            }
        
        elif table_name == "prs":
            return {
                "title": entity.get("title"),
                "description": entity.get("description"),
                "status": entity.get("status"),
                "author": entity.get("author"),
                "created_at": self._serialize_datetime(entity.get("pr_created_at")),
                "updated_at": self._serialize_datetime(entity.get("pr_updated_at"))
            }

        elif table_name == "prs_reviews":
            return {
                "state": entity.get("state"),
                "body": entity.get("body"),
                "author_login": entity.get("author_login"),
                "submitted_at": self._serialize_datetime(entity.get("submitted_at"))
            }

        elif table_name == "prs_comments":
            return {
                "body": entity.get("body"),
                "author_login": entity.get("author_login"),
                "comment_type": entity.get("comment_type"),
                "path": entity.get("path"),
                "line": entity.get("line"),
                "created_at": self._serialize_datetime(entity.get("created_at_github"))
            }

        elif table_name == "repositories":
            return {
                "name": entity.get("name"),
                "full_name": entity.get("full_name"),
                "description": entity.get("description"),
                "language": entity.get("language"),
                "topics": entity.get("topics"),
                "created_at": self._serialize_datetime(entity.get("created_at")),
                "updated_at": self._serialize_datetime(entity.get("updated_at"))
            }

        elif table_name == "wits_prs_links":
            return {
                "work_item_key": entity.get("work_item_key"),
                "repo_full_name": entity.get("repo_full_name"),
                "pr_number": entity.get("pr_number"),
                "pr_title": entity.get("pr_title"),
                "pr_status": entity.get("pr_status"),
                "pr_author": entity.get("pr_author"),
                "link_type": entity.get("link_type", "development"),
                "created_at": self._serialize_datetime(entity.get("created_at"))
            }

        else:
            logger.warning(f"No entity data preparation defined for table: {table_name}")
            return None
    
    def _serialize_datetime(self, dt_value: Any) -> Optional[str]:
        """Convert datetime objects to ISO format strings."""
        if dt_value is None:
            return None
        
        if hasattr(dt_value, 'isoformat'):
            # It's a datetime object
            return dt_value.isoformat()
        else:
            # It's already a string or other type
            return str(dt_value) if dt_value else None
    

    
    async def bulk_insert_to_queue_and_trigger(self, auth_token: str = None) -> Dict[str, Any]:
        """
        Legacy method - now just triggers vectorization since entities are saved immediately.
        Kept for backward compatibility. auth_token parameter is ignored (uses internal auth).
        """
        logger.warning("bulk_insert_to_queue_and_trigger is deprecated - use trigger_vectorization_only instead")
        if auth_token:
            logger.warning("auth_token parameter is deprecated and ignored - using internal authentication")
        return await self.trigger_vectorization_only()

    async def trigger_vectorization_only(self) -> Dict[str, Any]:
        """
        Trigger vectorization processing without bulk inserting (since entities are saved immediately).
        Uses internal authentication for service-to-service communication.

        Returns:
            Dictionary with trigger status
        """
        try:
            # Trigger async processing
            asyncio.create_task(
                self._trigger_async_vectorization()
            )

            logger.info("Triggered vectorization processing for immediately saved entities")

            return {
                "status": "triggered",
                "message": "Vectorization processing started for all saved entities"
            }

        except Exception as e:
            logger.error(f"Failed to trigger vectorization processing: {e}")
            raise

    async def _trigger_async_vectorization(self):
        """Fire-and-forget call to backend processor using internal auth."""
        try:
            # Use internal secret for service-to-service communication
            from app.core.config import get_settings
            settings = get_settings()
            internal_secret = settings.ETL_INTERNAL_SECRET

            url = f"{self.backend_url}/api/v1/ai/vectors/process-queue-internal"
            payload = {"tenant_id": self.tenant_id}
            headers = {
                "X-Internal-Auth": internal_secret,
                "Content-Type": "application/json"
            }

            logger.info(f"[VECTORIZATION] Sending trigger request to: {url}")
            logger.info(f"[VECTORIZATION] Payload: {payload}")
            logger.debug(f"[VECTORIZATION] Headers: {headers}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=5.0  # Short timeout - we don't wait for completion
                )

                logger.info(f"[VECTORIZATION] Backend response: {response.status_code}")
                if response.status_code != 200:
                    response_text = await response.atext() if hasattr(response, 'atext') else response.text
                    logger.warning(f"[VECTORIZATION] Backend response body: {response_text}")
                else:
                    logger.info(f"[VECTORIZATION] Successfully triggered backend processing")

        except Exception as e:
            logger.error(f"[VECTORIZATION] Failed to trigger vectorization processing: {e}")
            logger.error(f"[VECTORIZATION] Backend URL: {self.backend_url}")
            logger.error(f"[VECTORIZATION] Tenant ID: {self.tenant_id}")
            # This is non-critical - the queue entries are still in the database
            # and can be processed later
