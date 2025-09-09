"""
Pull Requests API endpoints for Backend Service.
Provides CRUD operations for pull requests with optional ML fields support.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_read_session, get_write_session
from app.core.logging_config import get_logger
from app.models.unified_models import Pr, Repository, PrComment, PrReview
from app.auth.auth_middleware import UserData, require_authentication

router = APIRouter(prefix="/api", tags=["Pull Requests"])
logger = get_logger(__name__)


# Request/Response Models
class PrCreateRequest(BaseModel):
    external_id: str
    external_repo_id: str
    repository_id: Optional[int] = None
    number: int
    name: str
    user_name: Optional[str] = None
    body: Optional[str] = None
    discussion_comment_count: Optional[int] = 0
    review_comment_count: Optional[int] = 0
    reviewers: Optional[int] = 0
    status: Optional[str] = None
    url: Optional[str] = None
    pr_created_at: Optional[datetime] = None
    pr_updated_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    commit_count: Optional[int] = 0
    additions: Optional[int] = 0
    deletions: Optional[int] = 0
    changed_files: Optional[int] = 0


class PrUpdateRequest(BaseModel):
    name: Optional[str] = None
    user_name: Optional[str] = None
    body: Optional[str] = None
    discussion_comment_count: Optional[int] = None
    review_comment_count: Optional[int] = None
    reviewers: Optional[int] = None
    status: Optional[str] = None
    url: Optional[str] = None
    pr_updated_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    commit_count: Optional[int] = None
    additions: Optional[int] = None
    deletions: Optional[int] = None
    changed_files: Optional[int] = None


@router.get("/pull-requests")
async def get_pull_requests(
    tenant_id: int = Query(..., description="Tenant ID for data isolation"),
    include_ml_fields: bool = Query(False, description="Include ML fields in response"),
    limit: int = Query(100, le=1000, description="Maximum number of PRs to return"),
    offset: int = Query(0, ge=0, description="Number of PRs to skip for pagination"),
    repository: Optional[str] = Query(None, description="Filter by repository name"),
    status: Optional[str] = Query(None, description="Filter by PR status"),
    user_name: Optional[str] = Query(None, description="Filter by user name"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get pull requests with optional ML fields"""
    try:
        # Ensure client isolation
        if user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Tenant ID mismatch"
            )
        
        # Build query with filters
        query = db.query(Pr).filter(
            Pr.tenant_id == tenant_id,
            Pr.active == True
        )
        
        # Apply optional filters
        if repository:
            query = query.join(Repository).filter(Repository.name.ilike(f"%{repository}%"))
        
        if status:
            query = query.filter(Pr.status == status)
            
        if user_name:
            query = query.filter(Pr.user_name.ilike(f"%{user_name}%"))
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        pull_requests = query.order_by(Pr.pr_created_at.desc()).offset(offset).limit(limit).all()
        
        # Enhanced response with optional ML fields
        result = []
        for pr in pull_requests:
            pr_dict = pr.to_dict(include_ml_fields=include_ml_fields)
            result.append(pr_dict)
        
        return {
            'pull_requests': result,
            'count': len(result),
            'total_count': total_count,
            'offset': offset,
            'limit': limit,
            'ml_fields_included': include_ml_fields,
            'filters': {
                'repository': repository,
                'status': status,
                'user_name': user_name
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching pull requests: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch pull requests")


@router.get("/pull-requests/{pr_id}")
async def get_pull_request(
    pr_id: int,
    include_ml_fields: bool = Query(False, description="Include ML fields in response"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get single pull request with optional ML fields"""
    try:
        pr = db.query(Pr).filter(
            Pr.id == pr_id,
            Pr.tenant_id == user.tenant_id,
            Pr.active == True
        ).first()
        
        if not pr:
            raise HTTPException(status_code=404, detail="Pull request not found")
        
        return pr.to_dict(include_ml_fields=include_ml_fields)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching pull request {pr_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch pull request")


@router.post("/pull-requests")
async def create_pull_request(
    pr_data: PrCreateRequest,
    db: Session = Depends(get_write_session),
    user: UserData = Depends(require_authentication)
):
    """Create pull request - models handle new fields automatically"""
    try:
        from app.core.utils import DateTimeHelper
        
        # Create pull request normally - embedding defaults to None in model
        pr = Pr(
            external_id=pr_data.external_id,
            external_repo_id=pr_data.external_repo_id,
            repository_id=pr_data.repository_id,
            number=pr_data.number,
            name=pr_data.name,
            user_name=pr_data.user_name,
            body=pr_data.body,
            discussion_comment_count=pr_data.discussion_comment_count,
            review_comment_count=pr_data.review_comment_count,
            reviewers=pr_data.reviewers,
            status=pr_data.status,
            url=pr_data.url,
            pr_created_at=pr_data.pr_created_at or DateTimeHelper.now_utc(),
            pr_updated_at=pr_data.pr_updated_at or DateTimeHelper.now_utc(),
            merged_at=pr_data.merged_at,
            commit_count=pr_data.commit_count,
            additions=pr_data.additions,
            deletions=pr_data.deletions,
            changed_files=pr_data.changed_files,
            tenant_id=user.tenant_id,
            active=True,
            created_at=DateTimeHelper.now_utc(),
            last_updated_at=DateTimeHelper.now_utc()
            # embedding automatically defaults to None in model
        )
        
        db.add(pr)
        db.commit()
        db.refresh(pr)
        
        logger.info(f"Created pull request #{pr.number} for client {user.tenant_id}")
        return pr.to_dict()
        
    except Exception as e:
        logger.error(f"Error creating pull request: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create pull request")


@router.put("/pull-requests/{pr_id}")
async def update_pull_request(
    pr_id: int,
    pr_data: PrUpdateRequest,
    db: Session = Depends(get_write_session),
    user: UserData = Depends(require_authentication)
):
    """Update pull request - models handle new fields automatically"""
    try:
        from app.core.utils import DateTimeHelper
        
        pr = db.query(Pr).filter(
            Pr.id == pr_id,
            Pr.tenant_id == user.tenant_id,
            Pr.active == True
        ).first()

        if not pr:
            raise HTTPException(status_code=404, detail="Pull request not found")

        # Update existing fields normally
        for field, value in pr_data.dict(exclude_unset=True).items():
            if hasattr(pr, field):
                setattr(pr, field, value)
        
        # Update timestamp
        pr.last_updated_at = DateTimeHelper.now_utc()

        db.commit()
        db.refresh(pr)

        logger.info(f"Updated pull request #{pr.number} for client {user.tenant_id}")
        return pr.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating pull request {pr_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update pull request")


@router.delete("/pull-requests/{pr_id}")
async def delete_pull_request(
    pr_id: int,
    db: Session = Depends(get_write_session),
    user: UserData = Depends(require_authentication)
):
    """Soft delete pull request (set active=False)"""
    try:
        from app.core.utils import DateTimeHelper
        
        pr = db.query(Pr).filter(
            Pr.id == pr_id,
            Pr.tenant_id == user.tenant_id,
            Pr.active == True
        ).first()

        if not pr:
            raise HTTPException(status_code=404, detail="Pull request not found")

        # Soft delete
        pr.active = False
        pr.last_updated_at = DateTimeHelper.now_utc()

        db.commit()

        logger.info(f"Deleted pull request #{pr.number} for client {user.tenant_id}")
        return {"message": "Pull request deleted successfully", "pr_id": pr_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting pull request {pr_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete pull request")


@router.get("/pull-requests/stats")
async def get_pull_requests_stats(
    tenant_id: int = Query(..., description="Tenant ID for data isolation"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get pull request statistics for the client"""
    try:
        # Ensure client isolation
        if user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Tenant ID mismatch"
            )
        
        # Get basic stats
        total_prs = db.query(func.count(Pr.id)).filter(
            Pr.tenant_id == tenant_id,
            Pr.active == True
        ).scalar()
        
        # Get status breakdown
        status_stats = db.query(
            Pr.status,
            func.count(Pr.id).label('count')
        ).filter(
            Pr.tenant_id == tenant_id,
            Pr.active == True
        ).group_by(Pr.status).all()
        
        # Get average metrics
        avg_stats = db.query(
            func.avg(Pr.commit_count).label('avg_commits'),
            func.avg(Pr.additions).label('avg_additions'),
            func.avg(Pr.deletions).label('avg_deletions'),
            func.avg(Pr.changed_files).label('avg_changed_files')
        ).filter(
            Pr.tenant_id == tenant_id,
            Pr.active == True
        ).first()
        
        return {
            'total_pull_requests': total_prs,
            'status_breakdown': [{'status': s.status, 'count': s.count} for s in status_stats],
            'averages': {
                'commits': float(avg_stats.avg_commits or 0),
                'additions': float(avg_stats.avg_additions or 0),
                'deletions': float(avg_stats.avg_deletions or 0),
                'changed_files': float(avg_stats.avg_changed_files or 0)
            },
            'tenant_id': tenant_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching pull request stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch pull request statistics")
