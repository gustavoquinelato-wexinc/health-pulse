"""
Vectorization Queue Management API
Handles queueing records for vectorization
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import json

from app.auth.auth_middleware import require_authentication
from app.core.database import get_database
from app.models.unified_models import (
    User, WitHierarchy, WitMapping, StatusMapping, Workflow
)
from app.core.logging_config import get_logger
from app.etl.queue.queue_manager import QueueManager

logger = get_logger(__name__)
router = APIRouter()


class QueueTableRequest(BaseModel):
    table_name: str


class QueueTableResponse(BaseModel):
    success: bool
    queued_count: int
    table_name: str
    message: str


@router.post("/vectorization/queue-table", response_model=QueueTableResponse)
async def queue_table_for_vectorization(
    request: QueueTableRequest,
    user: User = Depends(require_authentication)
):
    """
    Queue all active records from a mapping table for vectorization.
    Sends messages directly to vectorization_queue_tenant_{id}.

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

        # Map table names to models
        table_model_map = {
            'wits_hierarchies': WitHierarchy,
            'wits_mappings': WitMapping,
            'statuses_mappings': StatusMapping,
            'workflows': Workflow
        }

        model = table_model_map[table_name]
        
        # Get all active records
        database = get_database()
        with database.get_read_session_context() as session:
            records = session.query(model).filter(
                model.tenant_id == tenant_id,
                model.active == True
            ).all()
            
            if not records:
                return QueueTableResponse(
                    success=True,
                    queued_count=0,
                    table_name=table_name,
                    message=f"No active records found in {table_name}"
                )

            # Use QueueManager to publish messages
            queue_manager = QueueManager()

            # Send messages for each record
            queued_count = 0
            for record in records:
                # Use the built-in publish_vectorization_job method
                success = queue_manager.publish_vectorization_job(
                    tenant_id=tenant_id,
                    table_name=table_name,
                    external_id=str(record.id),  # Use internal ID for mapping tables
                    operation="insert"
                )

                if success:
                    queued_count += 1
            
            logger.info(f"Queued {queued_count} records from {table_name} for tenant {tenant_id}")
            
            return QueueTableResponse(
                success=True,
                queued_count=queued_count,
                table_name=table_name,
                message=f"Successfully queued {queued_count} records for vectorization"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queueing table for vectorization: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue table for vectorization: {str(e)}"
        )

