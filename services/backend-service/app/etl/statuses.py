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


class StatusMappingCreateRequest(BaseModel):
    status_from: str
    status_to: str
    status_category: str
    workflow_id: Optional[int] = None
    integration_id: Optional[int] = None


class WorkflowCreateRequest(BaseModel):
    step_name: str
    step_number: Optional[int] = None
    step_category: str
    is_commitment_point: bool = False
    integration_id: Optional[int] = None


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


@router.post("/status-mappings", response_model=StatusMappingResponse)
async def create_status_mapping(
    mapping_data: StatusMappingCreateRequest,
    user: User = Depends(require_authentication)
):
    """Create a new status mapping"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Create new status mapping
            new_mapping = StatusMapping(
                status_from=mapping_data.status_from,
                status_to=mapping_data.status_to,
                status_category=mapping_data.status_category,
                workflow_id=mapping_data.workflow_id,
                integration_id=mapping_data.integration_id,
                tenant_id=user.tenant_id,
                active=True,
                created_at=DateTimeHelper.utcnow(),
                last_updated_at=DateTimeHelper.utcnow()
            )

            session.add(new_mapping)
            session.flush()  # Get the ID

            # Get workflow and integration info if they exist
            workflow_step_name = None
            step_number = None
            integration_name = None
            integration_logo = None

            if new_mapping.workflow_id:
                workflow = session.query(Workflow).filter(
                    Workflow.id == new_mapping.workflow_id,
                    Workflow.tenant_id == user.tenant_id
                ).first()
                if workflow:
                    workflow_step_name = workflow.step_name
                    step_number = workflow.step_number

            if new_mapping.integration_id:
                integration = session.query(Integration).filter(
                    Integration.id == new_mapping.integration_id,
                    Integration.tenant_id == user.tenant_id
                ).first()
                if integration:
                    integration_name = integration.provider
                    integration_logo = integration.logo_filename

            return StatusMappingResponse(
                id=new_mapping.id,
                status_from=new_mapping.status_from,
                status_to=new_mapping.status_to,
                status_category=new_mapping.status_category,
                workflow_step_name=workflow_step_name,
                workflow_id=new_mapping.workflow_id,
                step_number=step_number,
                integration_name=integration_name,
                integration_id=new_mapping.integration_id,
                integration_logo=integration_logo,
                active=new_mapping.active
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create status mapping: {str(e)}"
        )


@router.post("/workflows", response_model=WorkflowResponse)
async def create_workflow(
    workflow_data: WorkflowCreateRequest,
    user: User = Depends(require_authentication)
):
    """Create a new workflow"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Create new workflow
            new_workflow = Workflow(
                step_name=workflow_data.step_name,
                step_number=workflow_data.step_number,
                step_category=workflow_data.step_category,
                is_commitment_point=workflow_data.is_commitment_point,
                integration_id=workflow_data.integration_id,
                tenant_id=user.tenant_id,
                active=True,
                created_at=DateTimeHelper.utcnow(),
                last_updated_at=DateTimeHelper.utcnow()
            )

            session.add(new_workflow)
            session.flush()  # Get the ID

            # Get integration info if exists
            integration_name = None
            integration_logo = None
            if new_workflow.integration_id:
                integration = session.query(Integration).filter(
                    Integration.id == new_workflow.integration_id,
                    Integration.tenant_id == user.tenant_id
                ).first()
                if integration:
                    integration_name = integration.provider
                    integration_logo = integration.logo_filename

            return WorkflowResponse(
                id=new_workflow.id,
                step_name=new_workflow.step_name,
                step_number=new_workflow.step_number,
                step_category=new_workflow.step_category,
                is_commitment_point=new_workflow.is_commitment_point,
                integration_id=new_workflow.integration_id,
                integration_name=integration_name,
                integration_logo=integration_logo,
                active=new_workflow.active
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create workflow: {str(e)}"
        )
