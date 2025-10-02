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


class StatusMappingUpdateRequest(BaseModel):
    status_from: Optional[str] = None
    status_to: Optional[str] = None
    status_category: Optional[str] = None
    workflow_id: Optional[int] = None
    integration_id: Optional[int] = None
    active: Optional[bool] = None


class WorkflowUpdateRequest(BaseModel):
    step_name: Optional[str] = None
    step_number: Optional[int] = None
    step_category: Optional[str] = None
    is_commitment_point: Optional[bool] = None
    integration_id: Optional[int] = None
    active: Optional[bool] = None


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
                created_at=DateTimeHelper.now_default(),
                last_updated_at=DateTimeHelper.now_default()
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
                created_at=DateTimeHelper.now_default(),
                last_updated_at=DateTimeHelper.now_default()
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


@router.put("/status-mappings/{mapping_id}", response_model=StatusMappingResponse)
async def update_status_mapping(
    mapping_id: int,
    mapping_data: StatusMappingUpdateRequest,
    user: User = Depends(require_authentication)
):
    """Update a status mapping"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Get the existing mapping
            mapping = session.query(StatusMapping).filter(
                StatusMapping.id == mapping_id,
                StatusMapping.tenant_id == user.tenant_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Status mapping not found"
                )

            # Update fields if provided
            if mapping_data.status_from is not None:
                mapping.status_from = mapping_data.status_from
            if mapping_data.status_to is not None:
                mapping.status_to = mapping_data.status_to
            if mapping_data.status_category is not None:
                mapping.status_category = mapping_data.status_category
            if mapping_data.workflow_id is not None:
                mapping.workflow_id = mapping_data.workflow_id
            if mapping_data.integration_id is not None:
                mapping.integration_id = mapping_data.integration_id
            if mapping_data.active is not None:
                mapping.active = mapping_data.active

            mapping.last_updated_at = DateTimeHelper.now_default()
            session.commit()

            # Get workflow and integration info for response
            workflow = session.query(Workflow).filter(
                Workflow.id == mapping.workflow_id
            ).first() if mapping.workflow_id else None

            integration = session.query(Integration).filter(
                Integration.id == mapping.integration_id
            ).first() if mapping.integration_id else None

            return StatusMappingResponse(
                id=mapping.id,
                status_from=mapping.status_from,
                status_to=mapping.status_to,
                status_category=mapping.status_category,
                workflow_step_name=workflow.step_name if workflow else None,
                workflow_id=mapping.workflow_id,
                step_number=workflow.step_number if workflow else None,
                integration_name=integration.provider if integration else None,
                integration_id=mapping.integration_id,
                integration_logo=integration.logo_filename if integration else None,
                active=mapping.active
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update status mapping: {str(e)}"
        )


@router.put("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: int,
    workflow_data: WorkflowUpdateRequest,
    user: User = Depends(require_authentication)
):
    """Update a workflow"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Get the existing workflow
            workflow = session.query(Workflow).filter(
                Workflow.id == workflow_id,
                Workflow.tenant_id == user.tenant_id
            ).first()

            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found"
                )

            # Update fields if provided
            if workflow_data.step_name is not None:
                workflow.step_name = workflow_data.step_name
            if workflow_data.step_number is not None:
                workflow.step_number = workflow_data.step_number
            if workflow_data.step_category is not None:
                workflow.step_category = workflow_data.step_category
            if workflow_data.is_commitment_point is not None:
                workflow.is_commitment_point = workflow_data.is_commitment_point
            if workflow_data.integration_id is not None:
                workflow.integration_id = workflow_data.integration_id
            if workflow_data.active is not None:
                workflow.active = workflow_data.active

            workflow.last_updated_at = DateTimeHelper.now_default()
            session.commit()

            # Get integration info for response
            integration = session.query(Integration).filter(
                Integration.id == workflow.integration_id
            ).first() if workflow.integration_id else None

            return WorkflowResponse(
                id=workflow.id,
                step_name=workflow.step_name,
                step_number=workflow.step_number,
                step_category=workflow.step_category,
                is_commitment_point=workflow.is_commitment_point,
                integration_id=workflow.integration_id,
                integration_name=integration.provider if integration else None,
                integration_logo=integration.logo_filename if integration else None,
                active=workflow.active
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update workflow: {str(e)}"
        )


@router.delete("/status-mappings/{mapping_id}")
async def delete_status_mapping(
    mapping_id: int,
    user: User = Depends(require_authentication)
):
    """Delete a status mapping"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Get the existing mapping
            mapping = session.query(StatusMapping).filter(
                StatusMapping.id == mapping_id,
                StatusMapping.tenant_id == user.tenant_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Status mapping not found"
                )

            # Check for dependent statuses
            dependent_statuses = session.query(Status).filter(
                Status.status_mapping_id == mapping_id,
                Status.active == True
            ).count()

            if dependent_statuses > 0:
                # Soft delete to preserve referential integrity
                mapping.active = False
                from app.core.utils import DateTimeHelper
                mapping.last_updated_at = DateTimeHelper.now_default()
                session.commit()
                return {"message": f"Status mapping deactivated successfully ({dependent_statuses} dependent statuses preserved)"}
            else:
                # Hard delete if no dependencies
                session.delete(mapping)
                session.commit()
                return {"message": "Status mapping deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete status mapping: {str(e)}"
        )


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: int,
    user: User = Depends(require_authentication)
):
    """Delete a workflow"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Get the existing workflow
            workflow = session.query(Workflow).filter(
                Workflow.id == workflow_id,
                Workflow.tenant_id == user.tenant_id
            ).first()

            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found"
                )

            # Check for dependent status mappings
            dependent_mappings = session.query(StatusMapping).filter(
                StatusMapping.workflow_id == workflow_id
            ).count()

            if dependent_mappings > 0:
                # Soft delete to preserve referential integrity
                workflow.active = False
                from app.core.utils import DateTimeHelper
                workflow.last_updated_at = DateTimeHelper.now_default()
                session.commit()
                return {"message": f"Workflow deactivated successfully ({dependent_mappings} dependent status mappings preserved)"}
            else:
                # Hard delete if no dependencies
                session.delete(workflow)
                session.commit()
                return {"message": "Workflow deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete workflow: {str(e)}"
        )
