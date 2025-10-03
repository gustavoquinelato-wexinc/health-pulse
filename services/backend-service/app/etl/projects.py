"""
Projects ETL Management API
Handles project management for ETL processes
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.auth_middleware import UserData, require_authentication
from app.core.database import get_db_session
from app.models.unified_models import Project, Integration
from app.core.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/projects")
async def get_projects(
    integration_id: Optional[int] = Query(None, description="Filter by integration ID"),
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
):
    """
    Get projects, optionally filtered by integration.
    """
    try:
        query = db.query(Project).filter(
            Project.tenant_id == user.tenant_id,
            Project.active == True
        )
        
        if integration_id:
            # Verify integration exists and user has access
            integration = db.query(Integration).filter(
                Integration.id == integration_id,
                Integration.tenant_id == user.tenant_id,
                Integration.active == True
            ).first()
            
            if not integration:
                raise HTTPException(status_code=404, detail="Integration not found")
            
            query = query.filter(Project.integration_id == integration_id)
        
        projects = query.order_by(Project.name).all()
        
        return [
            {
                "id": project.id,
                "external_id": project.external_id,
                "key": project.key,
                "name": project.name,
                "project_type": project.project_type,
                "description": project.description,
                "lead": project.lead,
                "url": project.url,
                "integration_id": project.integration_id,
                "tenant_id": project.tenant_id,
                "active": project.active,
                "created_at": project.created_at.isoformat() if project.created_at else None,
                "last_updated_at": project.last_updated_at.isoformat() if project.last_updated_at else None
            }
            for project in projects
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to get projects")


@router.get("/projects/{project_id}")
async def get_project(
    project_id: int,
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
):
    """
    Get a specific project by ID.
    """
    try:
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.tenant_id == user.tenant_id,
            Project.active == True
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return {
            "id": project.id,
            "external_id": project.external_id,
            "key": project.key,
            "name": project.name,
            "project_type": project.project_type,
            "description": project.description,
            "lead": project.lead,
            "url": project.url,
            "integration_id": project.integration_id,
            "tenant_id": project.tenant_id,
            "active": project.active,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "last_updated_at": project.last_updated_at.isoformat() if project.last_updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get project")
