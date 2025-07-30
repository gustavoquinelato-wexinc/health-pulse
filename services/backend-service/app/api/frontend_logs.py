"""
Frontend log collection endpoints.
Receives and processes client-side logs for centralized logging.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from datetime import datetime

from app.auth.auth_middleware import require_authentication
from app.core.client_logging_middleware import get_client_logger_from_request
from app.models.unified_models import User


class FrontendLogEntry(BaseModel):
    """Frontend log entry model."""
    timestamp: str = Field(..., description="ISO timestamp of the log entry")
    level: str = Field(..., description="Log level (DEBUG, INFO, WARN, ERROR)")
    message: str = Field(..., description="Log message")
    client: str = Field(None, description="Client name")
    clientId: int = Field(None, description="Client ID")
    userId: int = Field(None, description="User ID")
    url: str = Field(None, description="Page URL where log occurred")
    userAgent: str = Field(None, description="Browser user agent")
    type: str = Field(None, description="Log type (api_call, user_action, etc.)")
    error: Dict[str, Any] = Field(None, description="Error details if applicable")
    data: Dict[str, Any] = Field(None, description="Additional log data")


class FrontendLogBatch(BaseModel):
    """Batch of frontend log entries."""
    logs: List[FrontendLogEntry] = Field(..., description="List of log entries")


router = APIRouter()


@router.post("/logs/frontend")
async def receive_frontend_log(
    log_entry: FrontendLogEntry,
    request: Request,
    current_user: User = Depends(require_authentication)
):
    """
    Receive a single frontend log entry.
    
    This endpoint receives individual log entries from the frontend application
    and writes them to the appropriate client-specific log file.
    """
    try:
        # Get client-aware logger
        logger = get_client_logger_from_request(request, "frontend_logs")
        
        # Validate that the log entry matches the authenticated user's client
        if log_entry.clientId and log_entry.clientId != current_user.client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot log for different client"
            )
        
        # Ensure client context matches authenticated user
        log_entry.clientId = current_user.client_id
        log_entry.userId = current_user.id
        
        # Convert log entry to structured log
        log_data = {
            "frontend_timestamp": log_entry.timestamp,
            "frontend_level": log_entry.level,
            "frontend_url": log_entry.url,
            "frontend_user_agent": log_entry.userAgent,
            "frontend_type": log_entry.type,
            "user_id": current_user.id,
            "client_id": current_user.client_id
        }
        
        # Add error details if present
        if log_entry.error:
            log_data["frontend_error"] = log_entry.error
        
        # Add additional data if present
        if log_entry.data:
            log_data["frontend_data"] = log_entry.data
        
        # Log with appropriate level
        log_level = log_entry.level.lower()
        if log_level == "error":
            logger.error(f"Frontend: {log_entry.message}", **log_data)
        elif log_level == "warn":
            logger.warning(f"Frontend: {log_entry.message}", **log_data)
        elif log_level == "debug":
            logger.debug(f"Frontend: {log_entry.message}", **log_data)
        else:
            logger.info(f"Frontend: {log_entry.message}", **log_data)
        
        return {"status": "logged", "timestamp": datetime.utcnow().isoformat()}
        
    except Exception as e:
        # Use system logger for errors in log processing
        from app.core.logging_config import get_logger
        system_logger = get_logger("frontend_log_error")
        system_logger.error(f"Failed to process frontend log: {e}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process log entry"
        )


@router.post("/logs/frontend/batch")
async def receive_frontend_log_batch(
    log_batch: FrontendLogBatch,
    request: Request,
    current_user: User = Depends(require_authentication)
):
    """
    Receive a batch of frontend log entries.
    
    This endpoint receives multiple log entries at once for efficient processing.
    Useful for flushing buffered logs from the frontend.
    """
    try:
        # Get client-aware logger
        logger = get_client_logger_from_request(request, "frontend_logs")
        
        processed_count = 0
        error_count = 0
        
        for log_entry in log_batch.logs:
            try:
                # Validate client context
                if log_entry.clientId and log_entry.clientId != current_user.client_id:
                    error_count += 1
                    continue
                
                # Ensure client context matches authenticated user
                log_entry.clientId = current_user.client_id
                log_entry.userId = current_user.id
                
                # Convert log entry to structured log
                log_data = {
                    "frontend_timestamp": log_entry.timestamp,
                    "frontend_level": log_entry.level,
                    "frontend_url": log_entry.url,
                    "frontend_user_agent": log_entry.userAgent,
                    "frontend_type": log_entry.type,
                    "user_id": current_user.id,
                    "client_id": current_user.client_id,
                    "batch_processing": True
                }
                
                # Add error details if present
                if log_entry.error:
                    log_data["frontend_error"] = log_entry.error
                
                # Add additional data if present
                if log_entry.data:
                    log_data["frontend_data"] = log_entry.data
                
                # Log with appropriate level
                log_level = log_entry.level.lower()
                if log_level == "error":
                    logger.error(f"Frontend: {log_entry.message}", **log_data)
                elif log_level == "warn":
                    logger.warning(f"Frontend: {log_entry.message}", **log_data)
                elif log_level == "debug":
                    logger.debug(f"Frontend: {log_entry.message}", **log_data)
                else:
                    logger.info(f"Frontend: {log_entry.message}", **log_data)
                
                processed_count += 1
                
            except Exception as e:
                error_count += 1
                logger.warning(f"Failed to process individual log entry: {e}")
        
        # Log batch processing summary
        logger.info(
            f"Frontend log batch processed",
            total_logs=len(log_batch.logs),
            processed=processed_count,
            errors=error_count,
            user_id=current_user.id,
            client_id=current_user.client_id
        )
        
        return {
            "status": "processed",
            "total": len(log_batch.logs),
            "processed": processed_count,
            "errors": error_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        # Use system logger for errors in batch processing
        from app.core.logging_config import get_logger
        system_logger = get_logger("frontend_log_batch_error")
        system_logger.error(f"Failed to process frontend log batch: {e}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process log batch"
        )


@router.get("/logs/frontend/status")
async def get_frontend_logging_status(
    request: Request,
    current_user: User = Depends(require_authentication)
):
    """
    Get frontend logging status and configuration.
    
    Returns information about frontend logging capabilities and client context.
    """
    try:
        from app.core.client_logging_middleware import get_client_context_from_request
        
        client_context = get_client_context_from_request(request)
        
        return {
            "status": "active",
            "client_logging_enabled": True,
            "client_context": {
                "client_id": current_user.client_id,
                "client_name": client_context.get('client_name') if client_context else None,
                "user_id": current_user.id,
                "user_email": current_user.email
            },
            "log_levels": ["DEBUG", "INFO", "WARN", "ERROR"],
            "supported_types": [
                "api_call", "user_action", "navigation", "react_error",
                "file_download", "file_upload", "authentication"
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get logging status"
        )
