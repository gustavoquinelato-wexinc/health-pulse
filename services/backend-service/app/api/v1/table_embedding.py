"""
API endpoints for table-specific embedding operations.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from app.auth.auth_middleware import require_authentication
from app.services.table_embedding_service import table_embedding_service
from app.core.logging_config import get_logger

logger = get_logger(__name__)
from app.models.unified_models import User


router = APIRouter()


class EmbeddingRequest(BaseModel):
    """Request model for starting table embedding."""
    integration_id: Optional[int] = None


class EmbeddingResponse(BaseModel):
    """Response model for embedding operations."""
    session_id: str
    table_name: str
    total_items: int
    status: str
    message: str
    tenant_id: int


@router.get("/table/{table_name}/status")
async def get_table_embedding_status(
    table_name: str,
    user: User = Depends(require_authentication)
):
    """
    Get embedding status for a specific table.
    
    Args:
        table_name: Name of the table to check
        current_user_tenant: Current user and tenant info
    
    Returns:
        Dict with table embedding status information
    """
    try:
        logger.info(f"Getting embedding status for {table_name}, tenant {user.tenant_id}")

        # Validate table name
        if not table_embedding_service._validate_table_name(table_name):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported table name: {table_name}"
            )

        # For now, return a simple status
        return {
            "table_name": table_name,
            "tenant_id": user.tenant_id,
            "status": "ready",
            "message": f"Table {table_name} is ready for embedding"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting embedding status for {table_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get embedding status: {str(e)}"
        )


@router.post("/table/{table_name}/execute", response_model=EmbeddingResponse)
async def execute_table_embedding(
    table_name: str,
    request: EmbeddingRequest,
    user: User = Depends(require_authentication)
):
    """
    Execute embedding for a specific table.
    
    Args:
        table_name: Name of the table to embed
        request: Embedding request with optional integration filter
        current_user_tenant: Current user and tenant info
    
    Returns:
        EmbeddingResponse with session details
    """
    try:
        logger.info(f"Starting table embedding for {table_name}, tenant {user.tenant_id}")

        # Validate table name
        if not table_embedding_service._validate_table_name(table_name):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported table name: {table_name}"
            )

        # Start embedding
        result = await table_embedding_service.start_table_embedding(
            table_name=table_name,
            tenant_id=user.tenant_id,
            integration_id=request.integration_id
        )
        
        return EmbeddingResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing table embedding for {table_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute table embedding: {str(e)}"
        )
