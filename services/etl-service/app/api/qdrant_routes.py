"""
Qdrant Analysis API Routes for ETL Service

Provides API endpoints for Qdrant vector database analysis and management:
- Database summary statistics
- Vectorization queue management
- Vector database operations
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import func, text, and_

from app.core.logging_config import get_logger
from app.core.database import get_database
from app.models.unified_models import (
    Pr, PrComment, PrReview, PrCommit,
    WorkItem, VectorizationQueue
)
from app.auth.centralized_auth_middleware import (
    UserData, require_admin_authentication
)

logger = get_logger(__name__)
router = APIRouter()

# Request/Response Models
class VectorizationQueueRequest(BaseModel):
    entity_type: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None

class BulkRevectorizationRequest(BaseModel):
    entity_type: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None

# Database Summary Endpoint
@router.get("/api/v1/database/summary")
async def get_database_summary(user: UserData = Depends(require_admin_authentication)):
    """Get database table counts and summary statistics"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            tenant_id = user.tenant_id
            
            # Count records in each table
            tables_summary = {}
            
            # Pull Requests
            prs_count = session.query(func.count(Pr.id)).filter(
                Pr.tenant_id == tenant_id
            ).scalar() or 0
            tables_summary['prs'] = {'total_count': prs_count}
            
            # PR Comments
            pr_comments_count = session.query(func.count(PrComment.id)).filter(
                PrComment.tenant_id == tenant_id
            ).scalar() or 0
            tables_summary['prs_comments'] = {'total_count': pr_comments_count}
            
            # PR Reviews
            pr_reviews_count = session.query(func.count(PrReview.id)).filter(
                PrReview.tenant_id == tenant_id
            ).scalar() or 0
            tables_summary['prs_reviews'] = {'total_count': pr_reviews_count}
            
            # PR Commits
            pr_commits_count = session.query(func.count(PrCommit.id)).filter(
                PrCommit.tenant_id == tenant_id
            ).scalar() or 0
            tables_summary['prs_commits'] = {'total_count': pr_commits_count}
            
            # Work Items (Issues)
            issues_count = session.query(func.count(WorkItem.id)).filter(
                WorkItem.tenant_id == tenant_id
            ).scalar() or 0
            tables_summary['issues'] = {'total_count': issues_count}

            # Work Item Comments (not implemented yet)
            tables_summary['issues_comments'] = {'total_count': 0}
            
            # Calculate totals
            total_records = sum(table['total_count'] for table in tables_summary.values())
            
            return {
                "success": True,
                "summary": {
                    "tables": tables_summary,
                    "total_records": total_records,
                    "tenant_id": tenant_id,
                    "last_updated": datetime.utcnow().isoformat()
                }
            }
            
    except Exception as e:
        logger.error(f"Error getting database summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database summary: {str(e)}"
        )

# Vectorization Queue Summary Endpoint
@router.get("/api/v1/vectorization/queue/summary")
async def get_vectorization_queue_summary(user: UserData = Depends(require_admin_authentication)):
    """Get vectorization queue summary statistics"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            tenant_id = user.tenant_id
            
            # Get queue statistics by status
            queue_stats = session.query(
                VectorizationQueue.status,
                func.count(VectorizationQueue.id).label('count')
            ).filter(
                VectorizationQueue.tenant_id == tenant_id
            ).group_by(VectorizationQueue.status).all()
            
            # Convert to dictionary
            status_counts = {stat.status: stat.count for stat in queue_stats}
            
            # Get statistics by table name (entity type)
            entity_stats = session.query(
                VectorizationQueue.table_name,
                VectorizationQueue.status,
                func.count(VectorizationQueue.id).label('count')
            ).filter(
                VectorizationQueue.tenant_id == tenant_id
            ).group_by(
                VectorizationQueue.table_name,
                VectorizationQueue.status
            ).all()

            # Organize by table name (entity type)
            by_entity_type = {}
            for stat in entity_stats:
                if stat.table_name not in by_entity_type:
                    by_entity_type[stat.table_name] = {}
                by_entity_type[stat.table_name][stat.status] = stat.count
            
            # Calculate totals
            total_pending = status_counts.get('pending', 0)
            total_processing = status_counts.get('processing', 0)
            total_completed = status_counts.get('completed', 0)
            total_failed = status_counts.get('failed', 0)
            total_count = sum(status_counts.values())
            
            return {
                "success": True,
                "summary": {
                    "total_pending": total_pending,
                    "total_processing": total_processing,
                    "total_completed": total_completed,
                    "total_failed": total_failed,
                    "total_count": total_count
                },
                "by_status": status_counts,
                "by_entity_type": by_entity_type,
                "tenant_id": tenant_id,
                "last_updated": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting vectorization queue summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vectorization queue summary: {str(e)}"
        )

# Queue Missing Records for Re-vectorization
@router.post("/api/v1/vectorization/queue/missing")
async def queue_missing_records(user: UserData = Depends(require_admin_authentication)):
    """Queue all missing records for re-vectorization"""
    try:
        # This is a placeholder implementation
        # In a real implementation, you would:
        # 1. Compare database records with Qdrant collections
        # 2. Identify missing vectors
        # 3. Queue them for re-vectorization
        
        logger.info(f"Queueing missing records for re-vectorization for tenant {user.tenant_id}")
        
        # For now, return a mock response
        return {
            "success": True,
            "queued_count": 0,
            "message": "Missing records queuing is not yet implemented",
            "tenant_id": user.tenant_id
        }
        
    except Exception as e:
        logger.error(f"Error queueing missing records: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue missing records: {str(e)}"
        )

# Queue Records by Entity Type
@router.post("/api/v1/vectorization/queue/entity-type")
async def queue_by_entity_type(
    request: VectorizationQueueRequest,
    user: UserData = Depends(require_admin_authentication)
):
    """Queue records by entity type for re-vectorization"""
    try:
        entity_type = request.entity_type
        if not entity_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Entity type is required"
            )
        
        logger.info(f"Queueing {entity_type} records for re-vectorization for tenant {user.tenant_id}")
        
        # For now, return a mock response
        return {
            "success": True,
            "queued_count": 0,
            "entity_type": entity_type,
            "message": f"Entity type {entity_type} queuing is not yet implemented",
            "tenant_id": user.tenant_id
        }
        
    except Exception as e:
        logger.error(f"Error queueing entity type records: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue entity type records: {str(e)}"
        )

# Queue Records by Date Range
@router.post("/api/v1/vectorization/queue/date-range")
async def queue_by_date_range(
    request: VectorizationQueueRequest,
    user: UserData = Depends(require_admin_authentication)
):
    """Queue records by date range for re-vectorization"""
    try:
        from_date = request.from_date
        to_date = request.to_date
        
        if not from_date or not to_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both from_date and to_date are required"
            )
        
        logger.info(f"Queueing records from {from_date} to {to_date} for re-vectorization for tenant {user.tenant_id}")
        
        # For now, return a mock response
        return {
            "success": True,
            "queued_count": 0,
            "from_date": from_date,
            "to_date": to_date,
            "message": f"Date range queuing is not yet implemented",
            "tenant_id": user.tenant_id
        }
        
    except Exception as e:
        logger.error(f"Error queueing date range records: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue date range records: {str(e)}"
        )

# Bulk Re-vectorization
@router.post("/api/v1/vectorization/queue/bulk")
async def bulk_revectorization(
    request: BulkRevectorizationRequest,
    user: UserData = Depends(require_admin_authentication)
):
    """Execute bulk re-vectorization with specified parameters"""
    try:
        logger.info(f"Executing bulk re-vectorization for tenant {user.tenant_id}")
        
        # For now, return a mock response
        return {
            "success": True,
            "queued_count": 0,
            "parameters": {
                "entity_type": request.entity_type,
                "from_date": request.from_date,
                "to_date": request.to_date
            },
            "message": "Bulk re-vectorization is not yet implemented",
            "tenant_id": user.tenant_id
        }
        
    except Exception as e:
        logger.error(f"Error executing bulk re-vectorization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute bulk re-vectorization: {str(e)}"
        )

# Preview Bulk Operation
@router.post("/api/v1/vectorization/queue/bulk/preview")
async def preview_bulk_operation(
    request: BulkRevectorizationRequest,
    user: UserData = Depends(require_admin_authentication)
):
    """Preview bulk operation to estimate affected records"""
    try:
        logger.info(f"Previewing bulk operation for tenant {user.tenant_id}")
        
        # For now, return a mock response
        return {
            "success": True,
            "estimated_count": 0,
            "parameters": {
                "entity_type": request.entity_type,
                "from_date": request.from_date,
                "to_date": request.to_date
            },
            "message": "Bulk operation preview is not yet implemented",
            "tenant_id": user.tenant_id
        }
        
    except Exception as e:
        logger.error(f"Error previewing bulk operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview bulk operation: {str(e)}"
        )
