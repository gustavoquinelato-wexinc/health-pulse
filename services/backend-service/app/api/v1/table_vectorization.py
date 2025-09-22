"""
API endpoints for table-specific vectorization operations.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from app.auth.auth_middleware import require_authentication
from app.services.table_vectorization_service import table_vectorization_service
from app.core.logging_config import get_logger

logger = get_logger(__name__)
from app.models.unified_models import User


router = APIRouter()


class VectorizationRequest(BaseModel):
    """Request model for starting table vectorization."""
    integration_id: Optional[int] = None


class VectorizationResponse(BaseModel):
    """Response model for vectorization operations."""
    session_id: str
    table_name: str
    total_items: int
    status: str
    message: Optional[str] = None


class TableStatusResponse(BaseModel):
    """Response model for table vectorization status."""
    table_name: str
    display_name: str
    total_items: int
    vectorized_items: int
    qdrant_collection: str
    status: str
    session_id: Optional[str] = None
    last_updated: str


class ProgressResponse(BaseModel):
    """Response model for vectorization progress."""
    session_id: str
    table_name: str
    processed: int
    total: int
    status: str
    progress_percentage: int
    current_item: Optional[str] = None
    error: Optional[str] = None
    started_at: str


@router.post("/table/{table_name}/execute", response_model=VectorizationResponse)
async def execute_table_vectorization(
    table_name: str,
    request: VectorizationRequest,
    user: User = Depends(require_authentication)
):
    """
    Execute vectorization for a specific table.
    
    Args:
        table_name: Name of the table to vectorize
        request: Vectorization request with optional integration filter
        current_user_tenant: Current user and tenant info
    
    Returns:
        VectorizationResponse with session details
    """
    try:
        logger.info(f"Starting table vectorization for {table_name}, tenant {user.tenant_id}")

        # Validate table name
        if not table_vectorization_service._validate_table_name(table_name):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported table name: {table_name}"
            )

        # Start vectorization
        result = await table_vectorization_service.start_table_vectorization(
            table_name=table_name,
            tenant_id=user.tenant_id,
            integration_id=request.integration_id
        )
        
        return VectorizationResponse(**result)
        
    except ValueError as e:
        logger.error(f"Validation error in table vectorization: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting table vectorization: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/table/{table_name}/status", response_model=TableStatusResponse)
async def get_table_status(
    table_name: str,
    user: User = Depends(require_authentication)
):
    """
    Get vectorization status for a specific table.
    
    Args:
        table_name: Name of the table to check
        current_user_tenant: Current user and tenant info
    
    Returns:
        TableStatusResponse with current status
    """
    try:
        # Validate table name
        if not table_vectorization_service._validate_table_name(table_name):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported table name: {table_name}"
            )

        # Get table status
        status = await table_vectorization_service.get_table_status(
            table_name=table_name,
            tenant_id=user.tenant_id
        )
        
        return TableStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"Error getting table status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/session/{session_id}/progress", response_model=ProgressResponse)
async def get_session_progress(
    session_id: str,
    user: User = Depends(require_authentication)
):
    """
    Get progress for a specific vectorization session.
    
    Args:
        session_id: Session ID to track
        current_user_tenant: Current user and tenant info
    
    Returns:
        ProgressResponse with current progress
    """
    try:
        # Get session progress
        progress = await table_vectorization_service.get_session_progress(session_id)

        if not progress:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )
        
        return ProgressResponse(**progress)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session progress: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/session/{session_id}/cancel")
async def cancel_session(
    session_id: str,
    user: User = Depends(require_authentication)
):
    """
    Cancel an active vectorization session.
    
    Args:
        session_id: Session ID to cancel
        current_user_tenant: Current user and tenant info
    
    Returns:
        Success message
    """
    try:
        # Cancel session
        cancelled = await table_vectorization_service.cancel_session(session_id)

        if not cancelled:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found or already completed: {session_id}"
            )
        
        return {"message": "Session cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling session: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sessions/clear-stuck")
async def clear_stuck_sessions(
    table_name: str = None,
    max_age_minutes: int = 30,
    user: User = Depends(require_authentication)
):
    """
    Clear stuck vectorization sessions.

    Args:
        table_name: Optional table name to filter sessions (if None, clears all stuck sessions)
        max_age_minutes: Maximum age in minutes for sessions to be considered stuck
        user: Current user info

    Returns:
        Number of sessions cleared
    """
    try:
        cleared_count = table_vectorization_service.clear_stuck_sessions(table_name, max_age_minutes)

        return {
            "message": f"Cleared {cleared_count} stuck session(s)",
            "cleared_count": cleared_count,
            "table_name": table_name,
            "max_age_minutes": max_age_minutes
        }

    except Exception as e:
        logger.error(f"Error clearing stuck sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/tables")
async def get_supported_tables(
    user: User = Depends(require_authentication)
):
    """
    Get list of supported tables for vectorization.

    Args:
        user: Current authenticated user

    Returns:
        List of supported table names and display names
    """
    try:
        tables = []
        for table_name, config in table_vectorization_service.TABLE_MAPPING.items():
            tables.append({
                "table_name": table_name,
                "display_name": config["display_name"],
                "collection_suffix": config["collection_suffix"]
            })
        
        return {"tables": tables}
        
    except Exception as e:
        logger.error(f"Error getting supported tables: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
