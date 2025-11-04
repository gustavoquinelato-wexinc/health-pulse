"""
Jira Embedding API
Handles queueing Jira mapping records for embedding
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.auth_middleware import require_authentication
from app.core.database import get_database
from app.models.unified_models import (
    User, WitHierarchy, WitMapping, StatusMapping, Workflow
)
from app.core.logging_config import get_logger
from app.etl.workers.queue_manager import QueueManager

logger = get_logger(__name__)
router = APIRouter()


class QueueTableRequest(BaseModel):
    table_name: str


class QueueTableResponse(BaseModel):
    success: bool
    queued_count: int
    table_name: str
    message: str


@router.post("/embedding/queue-table", response_model=QueueTableResponse)
async def queue_table_for_embedding(
    request: QueueTableRequest,
    user: User = Depends(require_authentication)
):
    """
    Queue all active records from a Jira mapping table for embedding.
    Sends messages directly to embedding_queue_tenant_{id}.

    Supported tables:
    - wits_hierarchies
    - wits_mappings
    - status_mappings (or statuses_mappings)
    - workflows
    """
    try:
        table_name = request.table_name
        tenant_id = user.tenant_id

        # Normalize table name (accept both status_mappings and statuses_mappings)
        if table_name == 'status_mappings':
            table_name = 'statuses_mappings'

        # Validate table name
        valid_tables = ['wits_hierarchies', 'wits_mappings', 'statuses_mappings', 'workflows']
        if table_name not in valid_tables:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid table name. Must be one of: {', '.join(valid_tables)}"
            )

        # Map table names to models for counting records
        table_model_map = {
            'wits_hierarchies': WitHierarchy,
            'wits_mappings': WitMapping,
            'statuses_mappings': StatusMapping,
            'workflows': Workflow
        }

        model = table_model_map[table_name]

        # Get count of active records
        database = get_database()
        with database.get_read_session_context() as session:
            record_count = session.query(model).filter(
                model.tenant_id == tenant_id,
                model.active == True
            ).count()

            if record_count == 0:
                return QueueTableResponse(
                    success=True,
                    queued_count=0,
                    table_name=request.table_name,
                    message=f"No active records found in {request.table_name}"
                )

            # Use QueueManager to publish bulk mapping table message
            queue_manager = QueueManager()

            # Use the new bulk mapping table embedding approach
            # Always use the database table name (statuses_mappings) for consistency
            success = queue_manager.publish_mapping_table_embedding(
                tenant_id=tenant_id,
                table_name=table_name  # Use normalized database table name
            )

            if success:
                logger.info(f"Successfully queued {table_name} table for bulk embedding ({record_count} records)")
                return QueueTableResponse(
                    success=True,
                    queued_count=record_count,
                    table_name=request.table_name,  # Return the original table name from frontend
                    message=f"Successfully queued {request.table_name} table for bulk embedding ({record_count} records)"
                )
            else:
                logger.error(f"Failed to queue {table_name} table for bulk embedding")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to queue {request.table_name} table for embedding"
                )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queueing table for embedding: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue table for embedding: {str(e)}"
        )

