"""
Status Mappings ETL Management API
Handles status mappings and workflows
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.auth_middleware import require_authentication
from app.core.database import get_database
from app.models.unified_models import Status, StatusMapping, Workflow, Integration, User

router = APIRouter()


class StatusResponse(BaseModel):
    id: int
    external_id: Optional[str]
    original_name: str
    description: Optional[str]
    status_category: Optional[str]
    integration_id: Optional[int]
    active: bool


class StatusMappingResponse(BaseModel):
    id: int
    status_from: str
    status_to: str
    status_category: Optional[str]
    workflow_step_name: Optional[str]
    workflow_id: Optional[int]
    step_number: Optional[int]
    integration_name: Optional[str]
    integration_id: Optional[int]
    integration_logo: Optional[str]
    active: bool


class WorkflowResponse(BaseModel):
    id: int
    step_name: str
    step_number: Optional[int]
    step_category: str
    is_commitment_point: bool
    integration_id: Optional[int]
    integration_name: Optional[str]
    integration_logo: Optional[str]
    active: bool


@router.get("/statuses", response_model=List[StatusResponse])
async def get_statuses(
    user: User = Depends(require_authentication)
):
    """Get all statuses for current user's tenant"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            statuses = session.query(Status).filter(
                Status.tenant_id == user.tenant_id,
                Status.active == True
            ).order_by(Status.original_name).all()

            return [
                StatusResponse(
                    id=status_obj.id,
                    external_id=status_obj.external_id,
                    original_name=status_obj.original_name,
                    description=status_obj.description,
                    status_category=status_obj.status_category,
                    integration_id=status_obj.integration_id,
                    active=status_obj.active
                )
                for status_obj in statuses
            ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch statuses: {str(e)}"
        )


@router.get("/status-mappings", response_model=List[StatusMappingResponse])
async def get_status_mappings(
    user: User = Depends(require_authentication)
):
    """Get all status mappings"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            status_mappings = session.query(
                StatusMapping,
                Workflow.step_name.label('workflow_step_name'),
                Workflow.step_number.label('step_number'),
                Integration.provider.label('integration_name'),
                Integration.logo_filename.label('integration_logo')
            ).outerjoin(
                Workflow, StatusMapping.workflow_id == Workflow.id
            ).outerjoin(
                Integration, StatusMapping.integration_id == Integration.id
            ).filter(
                StatusMapping.tenant_id == user.tenant_id
            ).order_by(StatusMapping.status_from).all()

            return [
                StatusMappingResponse(
                    id=mapping.StatusMapping.id,
                    status_from=mapping.StatusMapping.status_from,
                    status_to=mapping.StatusMapping.status_to,
                    status_category=mapping.StatusMapping.status_category,
                    workflow_step_name=mapping.workflow_step_name,
                    workflow_id=mapping.StatusMapping.workflow_id,
                    step_number=mapping.step_number,
                    integration_name=mapping.integration_name,
                    integration_id=mapping.StatusMapping.integration_id,
                    integration_logo=mapping.integration_logo,
                    active=mapping.StatusMapping.active
                )
                for mapping in status_mappings
            ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch status mappings: {str(e)}"
        )


@router.get("/workflows", response_model=List[WorkflowResponse])
async def get_workflows(
    user: User = Depends(require_authentication)
):
    """Get all workflows"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            workflows = session.query(
                Workflow,
                Integration.provider.label('integration_name'),
                Integration.logo_filename.label('integration_logo')
            ).outerjoin(
                Integration, Workflow.integration_id == Integration.id
            ).filter(
                Workflow.tenant_id == user.tenant_id
            ).order_by(Workflow.step_number.nulls_last()).all()

            return [
                WorkflowResponse(
                    id=workflow.Workflow.id,
                    step_name=workflow.Workflow.step_name,
                    step_number=workflow.Workflow.step_number,
                    step_category=workflow.Workflow.step_category,
                    is_commitment_point=workflow.Workflow.is_commitment_point,
                    integration_id=workflow.Workflow.integration_id,
                    integration_name=workflow.integration_name,
                    integration_logo=workflow.integration_logo,
                    active=workflow.Workflow.active
                )
                for workflow in workflows
            ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch workflows: {str(e)}"
        )
