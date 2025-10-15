"""
Integrations ETL Management API
Handles integration management for ETL processes
"""

from typing import List, Optional
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
import logging

from app.auth.auth_middleware import require_authentication
from app.core.database import get_database
from app.models.unified_models import Integration, User
from app.core.config import AppConfig

logger = logging.getLogger(__name__)
router = APIRouter()


class IntegrationResponse(BaseModel):
    id: int
    name: str
    integration_type: str
    base_url: Optional[str]
    username: Optional[str]
    settings: Optional[dict]  # Unified settings
    logo_filename: Optional[str]
    active: bool
    last_sync_at: Optional[str]


class IntegrationCreateRequest(BaseModel):
    provider: str
    type: str
    base_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    settings: Optional[dict] = None  # Unified settings
    logo_filename: Optional[str] = None
    active: bool = True


class IntegrationUpdateRequest(BaseModel):
    base_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    settings: Optional[dict] = None  # Unified settings
    logo_filename: Optional[str] = None
    ai_model: Optional[str] = None
    active: Optional[bool] = None


@router.get("/integrations", response_model=List[IntegrationResponse])
async def get_integrations(
    user: User = Depends(require_authentication)
):
    """Get all integrations for current user's client"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # Get integrations filtered by tenant_id and type='data' for ETL (case-insensitive)
            integrations = session.query(Integration).filter(
                Integration.tenant_id == user.tenant_id,
                Integration.type.ilike('%data%')
            ).order_by(Integration.provider).all()

            integration_responses = []
            for integration in integrations:
                # TODO: Get last sync time from etl_jobs table
                # For now, we'll set it to None
                last_sync_at = None

                integration_responses.append(IntegrationResponse(
                    id=integration.id,  # type: ignore
                    name=integration.provider or "Unknown",  # type: ignore
                    integration_type=integration.type or "Unknown",  # type: ignore
                    base_url=integration.base_url,  # type: ignore
                    username=integration.username,  # type: ignore
                    settings=integration.settings,  # type: ignore
                    logo_filename=integration.logo_filename,  # type: ignore
                    active=integration.active,
                    last_sync_at=last_sync_at
                ))

            return integration_responses

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch integrations: {str(e)}"
        )


@router.post("/integrations")
async def create_integration(
    create_data: IntegrationCreateRequest,
    user: User = Depends(require_authentication)
):
    """Create a new integration"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Check if integration with same provider already exists for this tenant
            existing_integration = session.query(Integration).filter(
                Integration.provider == create_data.provider,
                Integration.tenant_id == user.tenant_id
            ).first()

            if existing_integration:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Integration with provider '{create_data.provider}' already exists"
                )

            # Create new integration
            new_integration = Integration(
                provider=create_data.provider,
                type=create_data.type,
                base_url=create_data.base_url,
                username=create_data.username,
                settings=create_data.settings or {},  # Unified settings
                logo_filename=create_data.logo_filename,
                tenant_id=user.tenant_id,
                active=create_data.active,
                created_at=datetime.utcnow(),
                last_updated_at=datetime.utcnow()
            )

            # Encrypt password if provided
            if create_data.password:
                key = AppConfig.load_key()
                new_integration.password = AppConfig.encrypt_token(create_data.password, key)  # type: ignore

            session.add(new_integration)
            session.commit()
            session.refresh(new_integration)

            return {
                "id": new_integration.id,
                "message": "Integration created successfully"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create integration: {str(e)}"
        )


@router.put("/integrations/{integration_id}")
async def update_integration(
    integration_id: int,
    update_data: IntegrationUpdateRequest,
    user: User = Depends(require_authentication)
):
    """Update an integration"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Get the integration
            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.tenant_id == user.tenant_id
            ).first()

            if not integration:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found"
                )

            # Update fields
            if update_data.base_url is not None:
                integration.base_url = update_data.base_url  # type: ignore
            if update_data.username is not None:
                integration.username = update_data.username  # type: ignore
            if update_data.ai_model is not None:
                integration.ai_model = update_data.ai_model  # type: ignore
            if update_data.logo_filename is not None:
                integration.logo_filename = update_data.logo_filename  # type: ignore
            if update_data.active is not None:
                integration.active = update_data.active

            # Only update password if provided
            if update_data.password:
                key = AppConfig.load_key()
                integration.password = AppConfig.encrypt_token(update_data.password, key)  # type: ignore

            integration.last_updated_at = datetime.utcnow()

            session.commit()

            return {"message": "Integration updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update integration: {str(e)}"
        )


@router.delete("/integrations/{integration_id}")
async def delete_integration(
    integration_id: int,
    user: User = Depends(require_authentication)
):
    """Delete an integration"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.tenant_id == user.tenant_id
            ).first()

            if not integration:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found"
                )

            session.delete(integration)
            session.commit()

            return {"message": "Integration deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete integration: {str(e)}"
        )


@router.post("/integrations/{integration_id}/toggle-active")
async def toggle_integration_active(
    integration_id: int,
    request: dict,  # {"active": bool}
    user: User = Depends(require_authentication)
):
    """
    Toggle integration active/inactive status.

    Business Rule: Inactive integration cannot have active jobs.
    - Can deactivate integration only if all its jobs are inactive
    - Can activate integration regardless of job status
    """
    try:
        from sqlalchemy import text

        database = get_database()
        with database.get_write_session_context() as session:
            # Get the integration
            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.tenant_id == user.tenant_id
            ).first()

            if not integration:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found"
                )

            new_active_status = request.get("active", True)

            # If deactivating integration, check if it has any active jobs
            if not new_active_status:
                active_jobs_query = text("""
                    SELECT COUNT(*) FROM etl_jobs
                    WHERE integration_id = :integration_id
                    AND tenant_id = :tenant_id
                    AND active = true
                """)
                active_jobs_count = session.execute(active_jobs_query, {
                    'integration_id': integration_id,
                    'tenant_id': user.tenant_id
                }).fetchone()[0]

                if active_jobs_count > 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot deactivate integration {integration.provider} - it has {active_jobs_count} active job(s). Deactivate all jobs first."
                    )

            # Update integration status
            integration.active = new_active_status
            integration.last_updated_at = datetime.utcnow()
            session.commit()

            action = "activated" if new_active_status else "deactivated"
            logger.info(f"Integration {integration.provider} (ID: {integration_id}) {action}")

            return {
                "success": True,
                "message": f"Integration {integration.provider} {action} successfully",
                "integration_id": integration_id,
                "active": new_active_status
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle integration status: {str(e)}"
        )


@router.post("/integrations/upload-logo")
async def upload_integration_logo(
    logo: UploadFile = File(...),
    user: User = Depends(require_authentication)
):
    """Upload an integration logo (SVG only) to etl-frontend public assets"""
    try:
        # Validate file type
        if logo.content_type != 'image/svg+xml':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only SVG files are allowed"
            )

        # Read file contents
        contents = await logo.read()

        # Validate file size (max 1MB)
        if len(contents) > 1 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size must be less than 1MB"
            )

        # Define the target directory (etl-frontend public assets)
        # Navigate from backend-service to etl-frontend
        current_dir = Path(__file__).resolve().parent  # app/etl/
        services_dir = current_dir.parent.parent.parent  # services/
        assets_dir = services_dir / "etl-frontend" / "public" / "assets" / "integrations"

        # Create directory if it doesn't exist
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Save the file
        filename = (logo.filename or "logo.png").lower()
        file_path = assets_dir / filename

        with open(file_path, 'wb') as f:
            f.write(contents)

        return {
            "message": "Logo uploaded successfully",
            "filename": filename
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload logo: {str(e)}"
        )
