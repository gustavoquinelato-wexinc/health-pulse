"""
Issues API endpoints for Backend Service.
Provides CRUD operations for issues with optional ML fields support.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel

from app.core.database import get_read_session, get_write_session
from app.core.logging_config import get_logger
from app.models.unified_models import Issue, Project, Status, Issuetype
from app.auth.auth_middleware import UserData, require_authentication

router = APIRouter(prefix="/api", tags=["Issues"])
logger = get_logger(__name__)


# Request/Response Models
class IssueCreateRequest(BaseModel):
    key: str
    summary: str
    description: Optional[str] = None
    priority: Optional[str] = None
    status_name: Optional[str] = None
    issuetype_name: Optional[str] = None
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    story_points: Optional[int] = None
    epic_link: Optional[str] = None
    project_id: Optional[int] = None
    status_id: Optional[int] = None
    issuetype_id: Optional[int] = None


class IssueUpdateRequest(BaseModel):
    summary: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status_name: Optional[str] = None
    issuetype_name: Optional[str] = None
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    story_points: Optional[int] = None
    epic_link: Optional[str] = None
    status_id: Optional[int] = None
    issuetype_id: Optional[int] = None


@router.get("/issues")
async def get_issues(
    client_id: int = Query(..., description="Client ID for data isolation"),
    include_ml_fields: bool = Query(False, description="Include ML fields in response"),
    limit: int = Query(100, le=1000, description="Maximum number of issues to return"),
    offset: int = Query(0, ge=0, description="Number of issues to skip for pagination"),
    project_key: Optional[str] = Query(None, description="Filter by project key"),
    status: Optional[str] = Query(None, description="Filter by issue status"),
    assignee: Optional[str] = Query(None, description="Filter by assignee"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get issues with optional ML fields"""
    try:
        # Ensure client isolation
        if user.client_id != client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Client ID mismatch"
            )
        
        # Build query with filters
        query = db.query(Issue).filter(
            Issue.client_id == client_id,
            Issue.active == True
        )
        
        # Apply optional filters
        if project_key:
            query = query.join(Project).filter(Project.key == project_key)
        
        if status:
            query = query.filter(Issue.status_name == status)
            
        if assignee:
            query = query.filter(Issue.assignee.ilike(f"%{assignee}%"))
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        issues = query.order_by(Issue.created_at.desc()).offset(offset).limit(limit).all()
        
        # Enhanced response with optional ML fields
        result = []
        for issue in issues:
            issue_dict = issue.to_dict(include_ml_fields=include_ml_fields)
            result.append(issue_dict)
        
        return {
            'issues': result,
            'count': len(result),
            'total_count': total_count,
            'offset': offset,
            'limit': limit,
            'ml_fields_included': include_ml_fields,
            'filters': {
                'project_key': project_key,
                'status': status,
                'assignee': assignee
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching issues: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch issues")


@router.get("/issues/{issue_id}")
async def get_issue(
    issue_id: int,
    include_ml_fields: bool = Query(False, description="Include ML fields in response"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get single issue with optional ML fields"""
    try:
        issue = db.query(Issue).filter(
            Issue.id == issue_id,
            Issue.client_id == user.client_id,
            Issue.active == True
        ).first()
        
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        return issue.to_dict(include_ml_fields=include_ml_fields)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching issue {issue_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch issue")


@router.post("/issues")
async def create_issue(
    issue_data: IssueCreateRequest,
    db: Session = Depends(get_write_session),
    user: UserData = Depends(require_authentication)
):
    """Create issue - models handle new fields automatically"""
    try:
        from app.core.utils import DateTimeHelper
        
        # Create issue normally - embedding defaults to None in model
        issue = Issue(
            key=issue_data.key,
            summary=issue_data.summary,
            description=issue_data.description,
            priority=issue_data.priority,
            status_name=issue_data.status_name,
            issuetype_name=issue_data.issuetype_name,
            assignee=issue_data.assignee,
            reporter=issue_data.reporter,
            story_points=issue_data.story_points,
            epic_link=issue_data.epic_link,
            project_id=issue_data.project_id,
            status_id=issue_data.status_id,
            issuetype_id=issue_data.issuetype_id,
            client_id=user.client_id,
            active=True,
            created_at=DateTimeHelper.now_utc(),
            last_updated_at=DateTimeHelper.now_utc()
            # embedding automatically defaults to None in model
        )
        
        db.add(issue)
        db.commit()
        db.refresh(issue)
        
        logger.info(f"Created issue {issue.key} for client {user.client_id}")
        return issue.to_dict()
        
    except Exception as e:
        logger.error(f"Error creating issue: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create issue")


@router.put("/issues/{issue_id}")
async def update_issue(
    issue_id: int,
    issue_data: IssueUpdateRequest,
    db: Session = Depends(get_write_session),
    user: UserData = Depends(require_authentication)
):
    """Update issue - models handle new fields automatically"""
    try:
        from app.core.utils import DateTimeHelper
        
        issue = db.query(Issue).filter(
            Issue.id == issue_id,
            Issue.client_id == user.client_id,
            Issue.active == True
        ).first()

        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")

        # Update existing fields normally
        for field, value in issue_data.dict(exclude_unset=True).items():
            if hasattr(issue, field):
                setattr(issue, field, value)
        
        # Update timestamp
        issue.last_updated_at = DateTimeHelper.now_utc()

        db.commit()
        db.refresh(issue)

        logger.info(f"Updated issue {issue.key} for client {user.client_id}")
        return issue.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating issue {issue_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update issue")


@router.delete("/issues/{issue_id}")
async def delete_issue(
    issue_id: int,
    db: Session = Depends(get_write_session),
    user: UserData = Depends(require_authentication)
):
    """Soft delete issue (set active=False)"""
    try:
        from app.core.utils import DateTimeHelper
        
        issue = db.query(Issue).filter(
            Issue.id == issue_id,
            Issue.client_id == user.client_id,
            Issue.active == True
        ).first()

        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")

        # Soft delete
        issue.active = False
        issue.last_updated_at = DateTimeHelper.now_utc()

        db.commit()

        logger.info(f"Deleted issue {issue.key} for client {user.client_id}")
        return {"message": "Issue deleted successfully", "issue_id": issue_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting issue {issue_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete issue")


@router.get("/issues/stats")
async def get_issues_stats(
    client_id: int = Query(..., description="Client ID for data isolation"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get issue statistics for the client"""
    try:
        # Ensure client isolation
        if user.client_id != client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Client ID mismatch"
            )
        
        # Get basic stats
        total_issues = db.query(func.count(Issue.id)).filter(
            Issue.client_id == client_id,
            Issue.active == True
        ).scalar()
        
        # Get status breakdown
        status_stats = db.query(
            Issue.status_name,
            func.count(Issue.id).label('count')
        ).filter(
            Issue.client_id == client_id,
            Issue.active == True
        ).group_by(Issue.status_name).all()
        
        # Get priority breakdown
        priority_stats = db.query(
            Issue.priority,
            func.count(Issue.id).label('count')
        ).filter(
            Issue.client_id == client_id,
            Issue.active == True
        ).group_by(Issue.priority).all()
        
        return {
            'total_issues': total_issues,
            'status_breakdown': [{'status': s.status_name, 'count': s.count} for s in status_stats],
            'priority_breakdown': [{'priority': p.priority, 'count': p.count} for p in priority_stats],
            'client_id': client_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching issue stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch issue statistics")
