"""
Projects API endpoints for Backend Service.
Provides CRUD operations for projects with optional ML fields support.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel

from app.core.database import get_read_session, get_write_session
from app.core.logging_config import get_logger
from app.models.unified_models import Project, WorkItem, Repository
from app.auth.auth_middleware import UserData, require_authentication

router = APIRouter(prefix="/api", tags=["Projects"])
logger = get_logger(__name__)


# Request/Response Models
class ProjectCreateRequest(BaseModel):
    external_id: str
    key: str
    name: str
    project_type: Optional[str] = None
    description: Optional[str] = None
    lead: Optional[str] = None
    url: Optional[str] = None


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    project_type: Optional[str] = None
    description: Optional[str] = None
    lead: Optional[str] = None
    url: Optional[str] = None


@router.get("/projects")
async def get_projects(
    tenant_id: int = Query(..., description="Tenant ID for data isolation"),
    include_ml_fields: bool = Query(False, description="Include ML fields in response"),
    limit: int = Query(100, le=1000, description="Maximum number of projects to return"),
    offset: int = Query(0, ge=0, description="Number of projects to skip for pagination"),
    project_type: Optional[str] = Query(None, description="Filter by project type"),
    search: Optional[str] = Query(None, description="Search in project name or key"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get projects with optional ML fields"""
    try:
        # Ensure client isolation
        if user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Tenant ID mismatch"
            )
        
        # Build query with filters
        query = db.query(Project).filter(
            Project.tenant_id == tenant_id,
            Project.active == True
        )
        
        # Apply optional filters
        if project_type:
            query = query.filter(Project.project_type == project_type)
            
        if search:
            query = query.filter(
                (Project.name.ilike(f"%{search}%")) |
                (Project.key.ilike(f"%{search}%"))
            )
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        projects = query.order_by(Project.name.asc()).offset(offset).limit(limit).all()
        
        # Enhanced response with optional ML fields
        result = []
        for project in projects:
            project_dict = project.to_dict(include_ml_fields=include_ml_fields)
            result.append(project_dict)
        
        return {
            'projects': result,
            'count': len(result),
            'total_count': total_count,
            'offset': offset,
            'limit': limit,
            'ml_fields_included': include_ml_fields,
            'filters': {
                'project_type': project_type,
                'search': search
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch projects")


@router.get("/projects/{project_id}")
async def get_project(
    project_id: int,
    include_ml_fields: bool = Query(False, description="Include ML fields in response"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get single project with optional ML fields"""
    try:
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.tenant_id == user.tenant_id,
            Project.active == True
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return project.to_dict(include_ml_fields=include_ml_fields)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch project")


@router.get("/projects/by-key/{project_key}")
async def get_project_by_key(
    project_key: str,
    include_ml_fields: bool = Query(False, description="Include ML fields in response"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get project by key with optional ML fields"""
    try:
        project = db.query(Project).filter(
            Project.key == project_key,
            Project.tenant_id == user.tenant_id,
            Project.active == True
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return project.to_dict(include_ml_fields=include_ml_fields)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project by key {project_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch project")


@router.post("/projects")
async def create_project(
    project_data: ProjectCreateRequest,
    db: Session = Depends(get_write_session),
    user: UserData = Depends(require_authentication)
):
    """Create project - models handle new fields automatically"""
    try:
        from app.core.utils import DateTimeHelper
        
        # Check if project key already exists for this client
        existing_project = db.query(Project).filter(
            Project.key == project_data.key,
            Project.tenant_id == user.tenant_id,
            Project.active == True
        ).first()
        
        if existing_project:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project with key '{project_data.key}' already exists"
            )
        
        # Create project normally - embedding defaults to None in model
        project = Project(
            external_id=project_data.external_id,
            key=project_data.key,
            name=project_data.name,
            project_type=project_data.project_type,
            description=project_data.description,
            lead=project_data.lead,
            url=project_data.url,
            tenant_id=user.tenant_id,
            active=True,
            created_at=DateTimeHelper.now_default(),
            last_updated_at=DateTimeHelper.now_default()
            # embedding automatically defaults to None in model
        )
        
        db.add(project)
        db.commit()
        db.refresh(project)
        
        logger.info(f"Created project {project.key} for client {user.tenant_id}")
        return project.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create project")


@router.put("/projects/{project_id}")
async def update_project(
    project_id: int,
    project_data: ProjectUpdateRequest,
    db: Session = Depends(get_write_session),
    user: UserData = Depends(require_authentication)
):
    """Update project - models handle new fields automatically"""
    try:
        from app.core.utils import DateTimeHelper
        
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.tenant_id == user.tenant_id,
            Project.active == True
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Update existing fields normally
        for field, value in project_data.dict(exclude_unset=True).items():
            if hasattr(project, field):
                setattr(project, field, value)
        
        # Update timestamp
        project.last_updated_at = DateTimeHelper.now_default()

        db.commit()
        db.refresh(project)

        logger.info(f"Updated project {project.key} for client {user.tenant_id}")
        return project.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update project")


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    db: Session = Depends(get_write_session),
    user: UserData = Depends(require_authentication)
):
    """Soft delete project (set active=False)"""
    try:
        from app.core.utils import DateTimeHelper
        
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.tenant_id == user.tenant_id,
            Project.active == True
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Soft delete
        project.active = False
        project.last_updated_at = DateTimeHelper.now_default()

        db.commit()

        logger.info(f"Deleted project {project.key} for client {user.tenant_id}")
        return {"message": "Project deleted successfully", "project_id": project_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete project")


@router.get("/projects/{project_id}/issues")
async def get_project_issues(
    project_id: int,
    include_ml_fields: bool = Query(False, description="Include ML fields in response"),
    limit: int = Query(100, le=1000, description="Maximum number of issues to return"),
    offset: int = Query(0, ge=0, description="Number of issues to skip for pagination"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get issues for a specific project"""
    try:
        # Verify project exists and user has access
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.tenant_id == user.tenant_id,
            Project.active == True
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get issues for this project
        query = db.query(WorkItem).filter(
            WorkItem.project_id == project_id,
            WorkItem.tenant_id == user.tenant_id,
            WorkItem.active == True
        )
        
        total_count = query.count()
        issues = query.order_by(WorkItem.created_at.desc()).offset(offset).limit(limit).all()
        
        # Enhanced response with optional ML fields
        result = []
        for issue in issues:
            issue_dict = issue.to_dict(include_ml_fields=include_ml_fields)
            result.append(issue_dict)
        
        return {
            'project': project.to_dict(),
            'issues': result,
            'count': len(result),
            'total_count': total_count,
            'offset': offset,
            'limit': limit,
            'ml_fields_included': include_ml_fields
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching issues for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch project issues")


@router.get("/projects/stats")
async def get_projects_stats(
    tenant_id: int = Query(..., description="Tenant ID for data isolation"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get project statistics for the client"""
    try:
        # Ensure client isolation
        if user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Tenant ID mismatch"
            )
        
        # Get basic stats
        total_projects = db.query(func.count(Project.id)).filter(
            Project.tenant_id == tenant_id,
            Project.active == True
        ).scalar()
        
        # Get project type breakdown
        type_stats = db.query(
            Project.project_type,
            func.count(Project.id).label('count')
        ).filter(
            Project.tenant_id == tenant_id,
            Project.active == True
        ).group_by(Project.project_type).all()
        
        # Get projects with issue counts
        project_issue_stats = db.query(
            Project.key,
            Project.name,
            func.count(WorkItem.id).label('issue_count')
        ).outerjoin(WorkItem, (WorkItem.project_id == Project.id) & (WorkItem.active == True)).filter(
            Project.tenant_id == tenant_id,
            Project.active == True
        ).group_by(Project.id, Project.key, Project.name).all()
        
        return {
            'total_projects': total_projects,
            'type_breakdown': [{'type': t.project_type, 'count': t.count} for t in type_stats],
            'project_issue_counts': [
                {'key': p.key, 'name': p.name, 'issue_count': p.issue_count} 
                for p in project_issue_stats
            ],
            'tenant_id': tenant_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch project statistics")
