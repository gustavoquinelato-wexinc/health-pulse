"""
Admin Panel API Routes

Provides administrative functionality for user management, role assignment,
and system configuration. Only accessible to admin users.
"""

from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from pydantic import BaseModel, EmailStr, Field
import os
from pathlib import Path

from app.core.database import get_database
from app.models.unified_models import (
    Integration, Project, WorkItem, Tenant, Changelog,
    Repository, Pr, PrCommit, PrReview, PrComment,
    WitPrLinks, Wit, Status, JobSchedule, SystemSettings,
    StatusMapping, Workflow, WitMapping, WitHierarchy, MigrationHistory,
    ProjectWits, ProjectsStatuses
)
from app.auth.centralized_auth_middleware import UserData, require_web_admin_authentication, require_web_admin_authentication
from app.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# Pydantic models for API
# NOTE: User management models moved to Backend Service
# User management is now centralized in Backend Service

class SystemStatsResponse(BaseModel):
    total_users: int
    active_users: int
    logged_users: int
    admin_users: int
    roles_distribution: dict
    database_stats: dict
    database_size_mb: float
    total_records: int

class IntegrationResponse(BaseModel):
    id: int
    name: str
    integration_type: str
    base_url: Optional[str] = None
    username: Optional[str] = None
    ai_model: Optional[str] = None  # AI model name
    logo_filename: Optional[str] = None  # Filename of integration logo (stored in tenant assets folder)
    active: bool
    last_sync_at: Optional[str] = None

class IntegrationCreateRequest(BaseModel):
    provider: str
    type: str
    base_url: Optional[str] = None  # Optional for embedding integrations
    username: Optional[str] = None
    password: Optional[str] = None
    base_search: Optional[str] = None
    ai_model: Optional[str] = None  # AI model name
    ai_model_config: Optional[dict] = None  # AI model configuration
    cost_config: Optional[dict] = None  # Cost tracking and limits
    fallback_integration_id: Optional[int] = None  # FK to another integration for fallback
    logo_filename: Optional[str] = None  # Filename of integration logo (stored in tenant assets folder)
    active: bool = True

class IntegrationUpdateRequest(BaseModel):
    base_url: Optional[str] = None  # Optional for embedding integrations
    username: Optional[str] = None
    password: Optional[str] = None
    base_search: Optional[str] = None
    ai_model: Optional[str] = None  # AI model name
    ai_model_config: Optional[dict] = None  # AI model configuration
    cost_config: Optional[dict] = None  # Cost tracking and limits
    fallback_integration_id: Optional[int] = None  # FK to another integration for fallback
    logo_filename: Optional[str] = None  # Filename of integration logo (stored in tenant assets folder)

class IntegrationDetailResponse(BaseModel):
    id: int
    name: str
    integration_type: str
    base_url: Optional[str] = None
    username: Optional[str] = None
    base_search: Optional[str] = None
    ai_model: Optional[str] = None  # AI model name
    ai_model_config: Optional[dict] = None  # AI model configuration
    cost_config: Optional[dict] = None  # Cost tracking and limits
    fallback_integration_id: Optional[int] = None  # FK to another integration for fallback
    logo_filename: Optional[str] = None  # Filename of integration logo (stored in tenant assets folder)
    password_masked: Optional[str] = None  # Masked version for display
    active: bool

class PermissionMatrixResponse(BaseModel):
    roles: List[str]
    resources: List[str]
    actions: List[str]
    matrix: Dict[str, Dict[str, List[str]]]  # role -> resource -> actions


# User Management Endpoints - Redirected to Backend Service
@router.get("/users")
async def get_users_redirect():
    """Redirect user management to Backend Service"""
    from app.core.config import get_settings
    settings = get_settings()
    backend_url = settings.BACKEND_SERVICE_URL

    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail=f"User management is now handled by Backend Service. Please use: {backend_url}/api/v1/admin/users",
        headers={"Location": f"{backend_url}/api/v1/admin/users"}
    )


@router.post("/users")
async def create_user_redirect():
    """Redirect user creation to Backend Service"""
    from app.core.config import get_settings
    settings = get_settings()
    backend_url = settings.BACKEND_SERVICE_URL

    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail=f"User management is now handled by Backend Service. Please use: {backend_url}/api/v1/admin/users",
        headers={"Location": f"{backend_url}/api/v1/admin/users"}
    )


@router.put("/users/{user_id}")
async def update_user_redirect(user_id: int):
    """Redirect user update to Backend Service"""
    from app.core.config import get_settings
    settings = get_settings()
    backend_url = settings.BACKEND_SERVICE_URL

    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail=f"User management is now handled by Backend Service. Please use: {backend_url}/api/v1/admin/users/{user_id}",
        headers={"Location": f"{backend_url}/api/v1/admin/users/{user_id}"}
    )


@router.delete("/users/{user_id}")
async def delete_user_redirect(user_id: int):
    """Redirect user deletion to Backend Service"""
    from app.core.config import get_settings
    settings = get_settings()
    backend_url = settings.BACKEND_SERVICE_URL

    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail=f"User management is now handled by Backend Service. Please use: {backend_url}/api/v1/admin/users/{user_id}",
        headers={"Location": f"{backend_url}/api/v1/admin/users/{user_id}"}
    )


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    admin_user: UserData = Depends(require_web_admin_authentication)
):
    """Get system statistics"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # User statistics - now handled by Backend Service
            # Placeholder values - should be fetched from Backend Service
            total_users = 0
            active_users = 0
            logged_users = 0
            admin_users = 0

            # Role distribution - now handled by Backend Service
            roles_distribution = {
                "admin": 0,  # Placeholder - should be fetched from Backend Service
                "user": 0,   # Placeholder - should be fetched from Backend Service
                "view": 0    # Placeholder - should be fetched from Backend Service
            }

            # Comprehensive database statistics - count all main tables
            database_stats = {}
            total_records = 0

            # Define ETL-specific tables to count (exclude user management tables)
            try:
                from app.models.unified_models import (
                    Integration, Project, WorkItem, Changelog, Repository,
                    Pr, PrCommit, PrReview, PrComment,
                    WitPrLinks, Wit, Status, StatusMapping, Workflow,
                    WitMapping, WitHierarchy, ProjectWits, ProjectsStatuses,
                    JobSchedule, SystemSettings, MigrationHistory
                )

                table_models = {
                    "integrations": Integration,
                    "projects": Project,
                    "work_items": WorkItem,
                    "changelogs": Changelog,
                    "repositories": Repository,
                    "prs": Pr,
                    "prs_commits": PrCommit,
                    "prs_reviews": PrReview,
                    "prs_comments": PrComment,
                    "wits_prs_links": WitPrLinks,
                    "wits": Wit,
                    "statuses": Status,
                    "status_mappings": StatusMapping,
                    "workflows": Workflow,
                    "wits_mappings": WitMapping,
                    "wits_hierarchies": WitHierarchy,
                    "projects_wits": ProjectWits,
                    "projects_statuses": ProjectsStatuses,
                    "etl_jobs": JobSchedule,
                    "system_settings": SystemSettings,
                    "migration_history": MigrationHistory
                }
            except ImportError as e:
                logger.warning(f"Could not import some models: {e}")
                # Fallback to basic models only
                from app.models.unified_models import Integration, JobSchedule, SystemSettings
                table_models = {
                    "integrations": Integration,
                    "etl_jobs": JobSchedule,
                    "system_settings": SystemSettings,
                }

            # ✅ SECURITY: Count records filtered by tenant_id
            for table_name, model in table_models.items():
                try:
                    # Skip tables that don't have tenant_id (global tables)
                    if table_name in ['migration_history']:
                        # These are global tables - count all records
                        if table_name in ['projects_issuetypes', 'projects_statuses']:
                            count = session.query(model).count() or 0
                        else:
                            count = session.query(func.count(model.id)).scalar() or 0
                    else:
                        # Filter by tenant_id for client-specific tables
                        if hasattr(model, 'tenant_id'):
                            if table_name in ['projects_issuetypes', 'projects_statuses']:
                                count = session.query(model).filter(model.tenant_id == admin_user.tenant_id).count() or 0
                            else:
                                count = session.query(func.count(model.id)).filter(model.tenant_id == admin_user.tenant_id).scalar() or 0
                        else:
                            # For tables without tenant_id, count all
                            if table_name in ['projects_issuetypes', 'projects_statuses']:
                                count = session.query(model).count() or 0
                            else:
                                count = session.query(func.count(model.id)).scalar() or 0

                    database_stats[table_name] = count
                    total_records += count
                except Exception as e:
                    logger.warning(f"Could not count records for {table_name}: {e}")
                    database_stats[table_name] = 0

            # Get database size in MB
            database_size_mb = 0.0
            try:
                # Query PostgreSQL for database size
                from sqlalchemy import text
                size_result = session.execute(
                    text("SELECT pg_size_pretty(pg_database_size(current_database())) as size, "
                         "pg_database_size(current_database()) as size_bytes")
                ).fetchone()

                if size_result:
                    # Convert bytes to MB
                    database_size_mb = round(size_result.size_bytes / (1024 * 1024), 2)

            except Exception as e:
                logger.warning(f"Could not get database size: {e}")

            # Format database stats for frontend compatibility
            formatted_database_stats = {
                "size": f"{database_size_mb} MB" if database_size_mb > 0 else "N/A",
                "table_count": len([count for count in database_stats.values() if count > 0]),
                "total_records": total_records,
                "tables": database_stats  # Include individual table counts
            }

            return SystemStatsResponse(
                total_users=total_users,
                active_users=active_users,
                logged_users=logged_users,
                admin_users=admin_users,
                roles_distribution=roles_distribution,
                database_stats=formatted_database_stats,
                database_size_mb=database_size_mb,
                total_records=total_records
            )

    except Exception as e:
        logger.error(f"Error fetching system stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch system statistics"
        )


@router.post("/integrations")
async def create_integration(
    create_data: IntegrationCreateRequest,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Create a new integration"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from datetime import datetime

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

            # Validate type-specific required fields
            if create_data.type == "Data" and not create_data.base_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Base URL is required for Data integrations"
                )

            # Create new integration
            new_integration = Integration(
                provider=create_data.provider,
                type=create_data.type,
                base_url=create_data.base_url,
                username=create_data.username,
                base_search=create_data.base_search,
                ai_model=create_data.ai_model,
                ai_model_config=create_data.ai_model_config or {},
                cost_config=create_data.cost_config or {},
                fallback_integration_id=create_data.fallback_integration_id,
                logo_filename=create_data.logo_filename,
                tenant_id=user.tenant_id,
                active=create_data.active,
                created_at=datetime.utcnow(),
                last_updated_at=datetime.utcnow()
            )

            # Encrypt password if provided
            if create_data.password:
                from app.core.config import AppConfig
                key = AppConfig.load_key()
                new_integration.password = AppConfig.encrypt_token(create_data.password, key)

            session.add(new_integration)
            session.commit()

            logger.info(f"Admin {user.email} created integration {new_integration.provider}")

            return {
                "message": "Integration created successfully",
                "id": new_integration.id,
                "provider": new_integration.provider
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating integration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create integration"
        )


@router.get("/integrations", response_model=List[IntegrationResponse])
async def get_integrations(
    user: UserData = Depends(require_web_admin_authentication)
):
    """Get all integrations for current user's client"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
            integrations = session.query(Integration).filter(
                Integration.tenant_id == user.tenant_id
            ).order_by(Integration.provider).all()

            # Get last sync info from etl_jobs for each integration
            integration_responses = []
            for integration in integrations:
                # Find the most recent successful job for this integration
                latest_job = session.query(JobSchedule).filter(
                    JobSchedule.integration_id == integration.id,
                    JobSchedule.last_success_at.isnot(None)
                ).order_by(JobSchedule.last_success_at.desc()).first()

                last_sync_at = latest_job.last_success_at.isoformat() if latest_job and latest_job.last_success_at else None

                integration_responses.append(IntegrationResponse(
                    id=integration.id,
                    name=integration.provider or "Unknown",
                    integration_type=integration.type or "Unknown",  # Using type field (Data/AI/Embedding)
                    base_url=integration.base_url,
                    username=integration.username,
                    ai_model=integration.ai_model,  # Include AI model name
                    logo_filename=integration.logo_filename,  # Include logo filename
                    active=integration.active,  # BaseEntity provides this field
                    last_sync_at=last_sync_at  # Get from etl_jobs.last_success_at
                ))

            return integration_responses
    except Exception as e:
        logger.error(f"Error fetching integrations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch integrations"
        )


@router.get("/wits")
async def get_wits(
    user: UserData = Depends(require_web_admin_authentication)
):
    """Get all work item types for current user's tenant"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            from app.models.unified_models import Wit

            wits = session.query(Wit).filter(
                Wit.tenant_id == user.tenant_id,
                Wit.active == True
            ).order_by(Wit.original_name).all()

            return [
                {
                    "id": wit.id,
                    "external_id": wit.external_id,
                    "original_name": wit.original_name,
                    "description": wit.description,
                    "hierarchy_level": wit.hierarchy_level,
                    "wits_mapping_id": wit.wit_mapping_id,
                    "integration_id": wit.integration_id,
                    "active": wit.active
                }
                for wit in wits
            ]
    except Exception as e:
        logger.error(f"Error fetching work item types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch work item types"
        )


@router.get("/integrations/{integration_id}", response_model=IntegrationDetailResponse)
async def get_integration_details(
    integration_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Get integration details for editing"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.tenant_id == user.tenant_id
            ).first()
            if not integration:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found"
                )

            # Create masked password for display (show first 4 chars + asterisks)
            password_masked = None
            if integration.password:
                # For security, show a masked version
                password_masked = "••••••••••••••••"  # Fixed length mask

            return IntegrationDetailResponse(
                id=integration.id,
                name=integration.provider,
                integration_type=integration.type,
                base_url=integration.base_url,
                username=integration.username,
                base_search=integration.base_search,
                ai_model=integration.ai_model,  # Include AI model name
                ai_model_config=integration.ai_model_config,  # AI model configuration
                cost_config=integration.cost_config,  # Cost tracking and limits
                fallback_integration_id=integration.fallback_integration_id,  # Fallback integration
                logo_filename=integration.logo_filename,  # Include logo filename
                password_masked=password_masked,
                active=integration.active
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching integration details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch integration details"
        )


@router.put("/integrations/{integration_id}")
async def update_integration(
    integration_id: int,
    update_data: IntegrationUpdateRequest,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Update an integration"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Get the integration
            # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.tenant_id == user.tenant_id
            ).first()
            if not integration:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found"
                )

            # Validate type-specific required fields
            if integration.type == "Data" and not update_data.base_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Base URL is required for Data integrations"
                )

            # Update fields
            integration.base_url = update_data.base_url
            integration.username = update_data.username
            integration.base_search = update_data.base_search
            integration.ai_model = update_data.ai_model  # Update AI model name
            integration.ai_model_config = update_data.ai_model_config or {}
            integration.cost_config = update_data.cost_config or {}
            integration.fallback_integration_id = update_data.fallback_integration_id
            integration.logo_filename = update_data.logo_filename  # Update logo filename

            # Only update password if provided
            if update_data.password:
                # Encrypt the password using the SECRET_KEY
                from app.core.config import AppConfig
                key = AppConfig.load_key()
                integration.password = AppConfig.encrypt_token(update_data.password, key)

            # Update timestamp
            from datetime import datetime
            integration.last_updated_at = datetime.utcnow()

            session.commit()

            logger.info(f"Admin {user.email} updated integration {integration.provider}")

            return {"message": "Integration updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating integration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update integration"
        )


@router.patch("/integrations/{integration_id}/activate")
async def activate_integration(
    integration_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Activate an integration"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from datetime import datetime

            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.tenant_id == user.tenant_id
            ).first()

            if not integration:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found"
                )

            integration.active = True
            integration.last_updated_at = datetime.utcnow()
            session.commit()

            logger.info(f"Admin {user.email} activated integration {integration.provider}")

            return {"message": "Integration activated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating integration {integration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate integration"
        )


@router.patch("/integrations/{integration_id}/deactivate")
async def deactivate_integration(
    integration_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Deactivate an integration"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from datetime import datetime

            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.tenant_id == user.tenant_id
            ).first()

            if not integration:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found"
                )

            integration.active = False
            integration.last_updated_at = datetime.utcnow()
            session.commit()

            logger.info(f"Admin {user.email} deactivated integration {integration.provider}")

            return {"message": "Integration deactivated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating integration {integration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate integration"
        )


@router.delete("/integrations/{integration_id}")
async def delete_integration(
    integration_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Delete an integration"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import Project, WorkItem

            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.tenant_id == user.tenant_id
            ).first()

            if not integration:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found"
                )

            # Check for dependent projects
            dependent_projects = session.query(Project).filter(
                Project.integration_id == integration_id,
                Project.active == True
            ).count()

            # Check for dependent issues
            dependent_issues = session.query(WorkItem).filter(
                WorkItem.integration_id == integration_id,
                WorkItem.active == True
            ).count()

            if dependent_projects > 0 or dependent_issues > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete integration: {dependent_projects} active projects and {dependent_issues} active issues are using this integration"
                )

            # Delete the integration
            session.delete(integration)
            session.commit()

            logger.info(f"Admin {user.email} deleted integration {integration.provider}")

            return {"message": "Integration deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting integration {integration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete integration"
        )


@router.post("/integrations/{integration_id}/logo")
async def upload_integration_logo(
    integration_id: int,
    logo: UploadFile = File(...),
    user: UserData = Depends(require_web_admin_authentication)
):
    """Upload a logo for an integration"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from datetime import datetime

            # Find the integration
            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.tenant_id == user.tenant_id
            ).first()

            if not integration:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found"
                )

            # Validate file type
            if not logo.content_type or not logo.content_type.startswith('image/'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File must be an image"
                )

            # Validate file size (max 5MB)
            if logo.size and logo.size > 5 * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File size must be less than 5MB"
                )

            # Validate filename
            if not logo.filename:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File must have a valid filename"
                )

            # Get tenant information to determine assets folder
            tenant = session.query(Tenant).filter(
                Tenant.id == user.tenant_id
            ).first()

            if not tenant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tenant not found"
                )

            # Use tenant name (lowercase) as folder name if assets_folder not set
            tenant_folder = tenant.assets_folder or tenant.name.lower()

            # Create the integrations directory path (assets are served from /static/assets/ path)
            assets_dir = Path(__file__).parent.parent.parent / "static" / "assets" / tenant_folder / "integrations"
            assets_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename (use original filename or create one based on integration)
            file_extension = Path(logo.filename).suffix if logo.filename else '.svg'
            if not file_extension:
                file_extension = '.svg'  # Default to SVG

            # Use integration provider name as base filename (clean and user-friendly)
            base_filename = integration.provider.lower().replace('_', '-').replace(' ', '-')

            # Check if file already exists and remove it to avoid conflicts
            filename = f"{base_filename}{file_extension}"
            file_path = assets_dir / filename



            if file_path.exists():
                file_path.unlink()  # Remove existing file
                logger.info(f"Removed existing logo file: {file_path}")

            # Save the file


            with open(file_path, "wb") as buffer:
                content = await logo.read()
                buffer.write(content)

            # Update integration record with new logo filename
            integration.logo_filename = filename
            integration.last_updated_at = datetime.utcnow()
            session.commit()

            logger.info(f"Admin {user.email} uploaded logo for integration {integration.provider} -> {filename}")

            return {
                "message": "Logo uploaded successfully",
                "logo_filename": filename,
                "integration_id": integration_id
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading integration logo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload logo"
        )


@router.get("/status-mappings")
async def get_status_mappings(
    user: UserData = Depends(require_web_admin_authentication)
):
    """Get all status mappings"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # Query status mappings with workflow and integration information
            from app.models.unified_models import StatusMapping, Workflow, Integration

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
                {
                    "id": mapping.StatusMapping.id,
                    "status_from": mapping.StatusMapping.status_from,
                    "status_to": mapping.StatusMapping.status_to,
                    "status_category": mapping.StatusMapping.status_category,
                    "workflow_step_name": mapping.workflow_step_name,
                    "workflow_id": mapping.StatusMapping.workflow_id,
                    "step_number": mapping.step_number,
                    "integration_name": mapping.integration_name,
                    "integration_id": mapping.StatusMapping.integration_id,
                    "integration_logo": mapping.integration_logo,
                    "active": mapping.StatusMapping.active
                }
                for mapping in status_mappings
            ]
    except Exception as e:
        logger.error(f"Error fetching status mappings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch status mappings"
        )


class StatusMappingCreateRequest(BaseModel):
    status_from: str
    status_to: str
    status_category: str
    workflow_id: Optional[int] = None
    integration_id: Optional[int] = None


@router.post("/status-mappings")
async def create_status_mapping(
    create_data: StatusMappingCreateRequest,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Create a new status mapping"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import StatusMapping
            from datetime import datetime

            # Create new status mapping
            new_mapping = StatusMapping(
                status_from=create_data.status_from,
                status_to=create_data.status_to,
                status_category=create_data.status_category,
                workflow_id=create_data.workflow_id,
                integration_id=create_data.integration_id,
                tenant_id=user.tenant_id,
                active=True,
                created_at=datetime.utcnow(),
                last_updated_at=datetime.utcnow()
            )

            session.add(new_mapping)
            session.commit()

            logger.info(f"Admin {user.email} created status mapping {new_mapping.id}")

            return {"message": "Status mapping created successfully", "id": new_mapping.id}

    except Exception as e:
        logger.error(f"Error creating status mapping: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create status mapping"
        )


@router.get("/status-mappings/{mapping_id}")
async def get_status_mapping_details(
    mapping_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Get status mapping details for editing"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            from app.models.unified_models import StatusMapping

            # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
            mapping = session.query(StatusMapping).filter(
                StatusMapping.id == mapping_id,
                StatusMapping.tenant_id == user.tenant_id
            ).first()
            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Status mapping not found"
                )

            return {
                "id": mapping.id,
                "status_from": mapping.status_from,
                "status_to": mapping.status_to,
                "status_category": mapping.status_category,
                "workflow_id": mapping.workflow_id
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching status mapping details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch status mapping details"
        )


class StatusMappingUpdateRequest(BaseModel):
    status_from: str
    status_to: str
    status_category: str
    workflow_id: Optional[int] = None
    integration_id: Optional[int] = None


@router.put("/status-mappings/{mapping_id}")
async def update_status_mapping(
    mapping_id: int,
    update_data: StatusMappingUpdateRequest,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Update a status mapping"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import StatusMapping

            # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
            mapping = session.query(StatusMapping).filter(
                StatusMapping.id == mapping_id,
                StatusMapping.tenant_id == user.tenant_id
            ).first()
            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Status mapping not found"
                )

            # Update fields
            mapping.status_from = update_data.status_from
            mapping.status_to = update_data.status_to
            mapping.status_category = update_data.status_category
            mapping.workflow_id = update_data.workflow_id
            mapping.integration_id = update_data.integration_id

            # Update timestamp
            from datetime import datetime
            mapping.last_updated_at = datetime.utcnow()

            session.commit()

            logger.info(f"Admin {user.email} updated status mapping {mapping.id}")

            return {"message": "Status mapping updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating status mapping: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update status mapping"
        )


@router.delete("/status-mappings/{mapping_id}")
async def delete_status_mapping(
    mapping_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Delete a status mapping (soft delete to preserve referential integrity)"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import StatusMapping, Status

            # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
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
                logger.info(f"Admin {user.email} soft-deleted status mapping {mapping_id} (has {dependent_statuses} dependent statuses)")
                message = f"Status mapping deactivated successfully ({dependent_statuses} dependent statuses preserved)"
            else:
                # Hard delete if no dependencies
                session.delete(mapping)
                logger.info(f"Admin {user.email} hard-deleted status mapping {mapping_id} (no dependencies)")
                message = "Status mapping deleted successfully"

            session.commit()
            return {"message": message}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting status mapping: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete status mapping"
        )


@router.patch("/status-mappings/{mapping_id}/activate")
async def activate_status_mapping(
    mapping_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Activate a status mapping"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from datetime import datetime

            mapping = session.query(StatusMapping).filter(
                StatusMapping.id == mapping_id,
                StatusMapping.tenant_id == user.tenant_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Status mapping not found"
                )

            mapping.active = True
            mapping.last_updated_at = datetime.utcnow()
            session.commit()

            logger.info(f"Admin {user.email} activated status mapping {mapping_id}")

            return {"message": "Status mapping activated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating status mapping {mapping_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate status mapping"
        )





@router.get("/status-mappings/{mapping_id}/dependencies")
async def get_status_mapping_dependencies(
    mapping_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Get dependencies for a status mapping"""
    try:
        database = get_database()
        with database.get_admin_session_context() as session:
            from app.models.unified_models import StatusMapping, WorkItem, Status

            mapping = session.query(StatusMapping).filter(
                StatusMapping.id == mapping_id,
                StatusMapping.tenant_id == user.tenant_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Status mapping not found"
                )

            # Count dependent issues that use this status mapping
            # WorkItems are connected through their status_id -> Status -> status_mapping_id -> StatusMapping
            dependent_issues_count = session.query(WorkItem).join(
                Status, WorkItem.status_id == Status.id
            ).filter(
                Status.status_mapping_id == mapping_id,
                Status.active == True,
                WorkItem.active == True,
                WorkItem.tenant_id == user.tenant_id
            ).count()

            # Get available reassignment targets (active status mappings, excluding current)
            reassignment_targets = session.query(StatusMapping).filter(
                StatusMapping.active == True,
                StatusMapping.id != mapping_id,
                StatusMapping.tenant_id == user.tenant_id
            ).order_by(StatusMapping.status_from, StatusMapping.status_to).all()

            return {
                "mapping_id": mapping_id,
                "mapping": {
                    "id": mapping.id,
                    "status_from": mapping.status_from,
                    "status_to": mapping.status_to,
                    "status_category": mapping.status_category
                },
                "can_delete_safely": dependent_issues_count == 0,
                "dependent_issues_count": dependent_issues_count,
                "has_dependencies": dependent_issues_count > 0,
                "reassignment_targets": [
                    {
                        "id": target.id,
                        "status_from": target.status_from,
                        "status_to": target.status_to,
                        "status_category": target.status_category
                    }
                    for target in reassignment_targets
                ]
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dependencies for status mapping {mapping_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get status mapping dependencies"
        )


class StatusMappingDeactivationRequest(BaseModel):
    action: str  # "keep_issues", "reassign_issues"
    target_mapping_id: Optional[int] = None  # Required if action is "reassign_issues"


@router.patch("/status-mappings/{mapping_id}/deactivate")
async def deactivate_status_mapping_with_dependencies(
    mapping_id: int,
    deactivation_data: StatusMappingDeactivationRequest,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Deactivate a status mapping with options for handling dependencies"""
    try:
        database = get_database()
        with database.get_admin_session_context() as session:
            from app.models.unified_models import StatusMapping, WorkItem, Status
            from datetime import datetime

            # Verify mapping exists and belongs to user's client
            mapping = session.query(StatusMapping).filter(
                StatusMapping.id == mapping_id,
                StatusMapping.tenant_id == user.tenant_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Status mapping not found"
                )

            if not mapping.active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Status mapping is already inactive"
                )

            # Get dependent issues
            dependent_issues = session.query(WorkItem).join(
                Status, WorkItem.status_id == Status.id
            ).filter(
                Status.status_mapping_id == mapping_id,
                Status.active == True,
                WorkItem.active == True,
                WorkItem.tenant_id == user.tenant_id
            ).all()

            # Handle dependencies based on user choice
            if deactivation_data.action == "reassign_issues":
                if not deactivation_data.target_mapping_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Target mapping ID required for reassignment"
                    )

                # Verify target mapping exists and is active
                target_mapping = session.query(StatusMapping).filter(
                    StatusMapping.id == deactivation_data.target_mapping_id,
                    StatusMapping.active == True,
                    StatusMapping.tenant_id == user.tenant_id
                ).first()

                if not target_mapping:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Target mapping (ID: {deactivation_data.target_mapping_id}) not found or is inactive"
                    )

                # Update all dependent statuses to use the new status mapping
                # This involves updating the Status records to point to the target mapping
                dependent_statuses = session.query(Status).filter(
                    Status.status_mapping_id == mapping_id,
                    Status.active == True,
                    Status.tenant_id == user.tenant_id
                ).all()

                for status in dependent_statuses:
                    status.status_mapping_id = target_mapping.id

                message = f"Status mapping deactivated and {len(dependent_issues)} issues (via {len(dependent_statuses)} statuses) reassigned to '{target_mapping.status_from} → {target_mapping.status_to}'"
                logger.info(f"Admin {user.email} deactivated status mapping {mapping_id} and reassigned {len(dependent_statuses)} statuses affecting {len(dependent_issues)} issues to {target_mapping.status_from}")

            elif deactivation_data.action == "keep_issues":
                message = f"Status mapping deactivated ({len(dependent_issues)} issues will continue to reference this inactive mapping)"
                logger.info(f"Admin {user.email} deactivated status mapping {mapping_id}, keeping {len(dependent_issues)} dependent issues active")

            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid action: {deactivation_data.action}. Supported actions: keep_issues, reassign_issues"
                )

            # Deactivate the mapping
            mapping.active = False
            mapping.last_updated_at = datetime.utcnow()
            session.commit()

            return {
                "message": message,
                "action_taken": deactivation_data.action,
                "affected_issues": len(dependent_issues)
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating status mapping {mapping_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate status mapping"
        )


@router.get("/workflows")
async def get_workflows(
    user: UserData = Depends(require_web_admin_authentication)
):
    """Get all workflows"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            from app.models.unified_models import Workflow, Integration

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
                {
                    "id": workflow.Workflow.id,
                    "step_name": workflow.Workflow.step_name,
                    "step_number": workflow.Workflow.step_number,
                    "step_category": workflow.Workflow.step_category,
                    "is_commitment_point": workflow.Workflow.is_commitment_point,
                    "integration_name": workflow.integration_name,
                    "integration_id": workflow.Workflow.integration_id,
                    "integration_logo": workflow.integration_logo,
                    "active": workflow.Workflow.active,
                    "created_at": workflow.Workflow.created_at,
                    "last_updated_at": workflow.Workflow.last_updated_at
                }
                for workflow in workflows
            ]
    except Exception as e:
        logger.error(f"Error fetching workflows: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch workflows"
        )


@router.get("/workflows/{workflow_id}")
async def get_workflow_details(
    workflow_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Get workflow details for editing"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            from app.models.unified_models import Workflow

            # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
            workflow = session.query(Workflow).filter(
                Workflow.id == workflow_id,
                Workflow.tenant_id == user.tenant_id
            ).first()
            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found"
                )

            return {
                "id": workflow.id,
                "step_name": workflow.step_name,
                "step_number": workflow.step_number,
                "step_category": workflow.step_category,
                "is_commitment_point": workflow.is_commitment_point,
                "integration_id": workflow.integration_id
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching workflow details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch workflow details"
        )


@router.get("/workflow-stats")
async def get_workflow_stats(
    user: UserData = Depends(require_web_admin_authentication)
):
    """Get workflow statistics for the workflows page"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            from app.models.unified_models import Workflow, StatusMapping
            from sqlalchemy import func

            # Get total workflows count
            total_workflows = session.query(func.count(Workflow.id)).filter(
                Workflow.tenant_id == user.tenant_id
            ).scalar() or 0

            # Get active workflows count
            active_workflows = session.query(func.count(Workflow.id)).filter(
                Workflow.tenant_id == user.tenant_id,
                Workflow.active == True
            ).scalar() or 0

            # Get workflows with mappings count
            workflows_with_mappings = session.query(func.count(func.distinct(StatusMapping.workflow_id))).filter(
                StatusMapping.tenant_id == user.tenant_id,
                StatusMapping.active == True
            ).scalar() or 0

            # Get total status mappings count
            total_mappings = session.query(func.count(StatusMapping.id)).filter(
                StatusMapping.tenant_id == user.tenant_id
            ).scalar() or 0

            return {
                "total_workflows": total_workflows,
                "active_workflows": active_workflows,
                "workflows_with_mappings": workflows_with_mappings,
                "total_mappings": total_mappings,
                "completion_rate": round((workflows_with_mappings / total_workflows * 100) if total_workflows > 0 else 0, 1)
            }

    except Exception as e:
        logger.error(f"Error fetching workflow stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch workflow statistics"
        )


@router.get("/workflows/{workflow_id}/dependencies")
async def check_workflow_dependencies(
    workflow_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Check dependencies for a workflow before deactivation/deletion"""
    try:
        from fastapi import status
        database = get_database()
        with database.get_admin_session_context() as session:
            from app.models.unified_models import Workflow, StatusMapping, Status

            # Verify workflow exists and belongs to user's client
            workflow = session.query(Workflow).filter(
                Workflow.id == workflow_id,
                Workflow.tenant_id == user.tenant_id
            ).first()

            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found"
                )

            # Get dependent status mappings (must include tenant_id filter)
            dependent_mappings = session.query(StatusMapping).filter(
                StatusMapping.workflow_id == workflow_id,
                StatusMapping.tenant_id == user.tenant_id,
                StatusMapping.active == True
            ).all()

            # Count statuses and issues that depend on these mappings
            total_affected_statuses = 0
            total_affected_issues = 0
            mapping_details = []

            for mapping in dependent_mappings:
                # Count statuses using this mapping
                statuses = session.query(Status).filter(
                    Status.status_mapping_id == mapping.id,
                    Status.tenant_id == user.tenant_id,
                    Status.active == True
                ).all()

                status_count = len(statuses)
                total_affected_statuses += status_count

                # Count issues using these statuses
                mapping_issue_count = 0
                for status in statuses:
                    from app.models.unified_models import WorkItem
                    issue_count = session.query(WorkItem).filter(
                        WorkItem.status_id == status.id,
                        WorkItem.tenant_id == user.tenant_id,
                        WorkItem.active == True
                    ).count()
                    mapping_issue_count += issue_count

                total_affected_issues += mapping_issue_count

                mapping_details.append({
                    "id": mapping.id,
                    "status_from": mapping.status_from,
                    "status_to": mapping.status_to,
                    "status_category": mapping.status_category,
                    "affected_statuses": status_count,
                    "affected_issues": mapping_issue_count
                })

            # Get available reassignment targets (active workflows, excluding current)
            reassignment_targets = session.query(Workflow).filter(
                Workflow.active == True,
                Workflow.id != workflow_id,
                Workflow.tenant_id == user.tenant_id
            ).order_by(Workflow.step_number).all()

            return {
                "workflow": {
                    "id": workflow.id,
                    "step_name": workflow.step_name,
                    "step_category": workflow.step_category
                },
                "can_delete_safely": len(dependent_mappings) == 0,
                "dependency_count": len(dependent_mappings),
                "affected_statuses_count": total_affected_statuses,
                "affected_issues_count": total_affected_issues,
                "dependent_mappings": mapping_details,
                "reassignment_targets": [
                    {
                        "id": target.id,
                        "step_name": target.step_name,
                        "step_category": target.step_category,
                        "step_number": target.step_number
                    }
                    for target in reassignment_targets
                ]
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking workflow dependencies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check dependencies"
        )


class WorkflowUpdateRequest(BaseModel):
    step_name: str
    step_number: Optional[int] = None
    step_category: str
    is_commitment_point: bool = False
    integration_id: Optional[int] = None


class WorkflowDeactivationRequest(BaseModel):
    action: str  # "keep_mappings", "reassign_mappings"
    target_workflow_id: Optional[int] = None  # Required if action is "reassign_mappings"


@router.put("/workflows/{workflow_id}")
async def update_workflow(
    workflow_id: int,
    update_data: WorkflowUpdateRequest,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Update a workflow"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import Workflow, Integration

            # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
            workflow = session.query(Workflow).filter(
                Workflow.id == workflow_id,
                Workflow.tenant_id == user.tenant_id
            ).first()
            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found"
                )

            # Validate single commitment point constraint before updating
            if update_data.is_commitment_point:
                existing_commitment_point = session.query(Workflow).filter(
                    Workflow.tenant_id == user.tenant_id,
                    Workflow.integration_id == update_data.integration_id,
                    Workflow.is_commitment_point == True,
                    Workflow.active == True,
                    Workflow.id != workflow_id  # Exclude current workflow
                ).first()

                if existing_commitment_point:
                    # Get integration name for better error message
                    integration_name = "All Integrations"
                    if update_data.integration_id:
                        # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
                        integration = session.query(Integration).filter(
                            Integration.id == update_data.integration_id,
                            Integration.tenant_id == user.tenant_id
                        ).first()
                        if integration:
                            integration_name = integration.provider

                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Only one commitment point is allowed per integration. A commitment point already exists for '{integration_name}': '{existing_commitment_point.step_name}'. Please uncheck the commitment point for the existing workflow first."
                    )

            # Update fields
            workflow.step_name = update_data.step_name
            workflow.step_number = update_data.step_number
            workflow.step_category = update_data.step_category
            workflow.is_commitment_point = update_data.is_commitment_point
            workflow.integration_id = update_data.integration_id

            # Update timestamp
            from datetime import datetime
            workflow.last_updated_at = datetime.utcnow()

            session.commit()

            logger.info(f"Admin {user.email} updated workflow {workflow.id}")

            return {"message": "Workflow updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workflow"
        )


@router.patch("/workflows/{workflow_id}/deactivate")
async def deactivate_workflow(
    workflow_id: int,
    deactivation_data: WorkflowDeactivationRequest,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Deactivate a workflow with options for handling dependencies"""
    try:
        database = get_database()
        with database.get_admin_session_context() as session:
            from app.models.unified_models import Workflow, StatusMapping
            from datetime import datetime

            # Verify workflow exists and belongs to user's client
            workflow = session.query(Workflow).filter(
                Workflow.id == workflow_id,
                Workflow.tenant_id == user.tenant_id
            ).first()

            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found"
                )

            # Check if workflow is already inactive
            was_originally_active = workflow.active

            # Get dependent status mappings
            dependent_mappings = session.query(StatusMapping).filter(
                StatusMapping.workflow_id == workflow_id,
                StatusMapping.tenant_id == user.tenant_id,
                StatusMapping.active == True
            ).all()

            if deactivation_data.action == "reassign_mappings":
                if not deactivation_data.target_workflow_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="target_workflow_id is required when action is 'reassign_mappings'"
                    )

                # Verify target workflow exists and is active
                target_workflow = session.query(Workflow).filter(
                    Workflow.id == deactivation_data.target_workflow_id,
                    Workflow.tenant_id == user.tenant_id,
                    Workflow.active == True
                ).first()

                if not target_workflow:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Target workflow not found or inactive"
                    )

                # Reassign all dependent mappings to the target workflow
                for mapping in dependent_mappings:
                    mapping.workflow_id = deactivation_data.target_workflow_id
                    mapping.last_updated_at = datetime.utcnow()

                message = f"Workflow deactivated and {len(dependent_mappings)} status mappings reassigned to '{target_workflow.step_name}'"
                logger.info(f"Admin {user.email} deactivated workflow {workflow_id}, reassigned {len(dependent_mappings)} mappings to workflow {deactivation_data.target_workflow_id}")

            elif deactivation_data.action == "keep_mappings":
                message = f"Workflow deactivated ({len(dependent_mappings)} status mappings will continue to reference this inactive workflow)"
                logger.info(f"Admin {user.email} deactivated workflow {workflow_id}, keeping {len(dependent_mappings)} dependent mappings active")

            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid action: {deactivation_data.action}. Supported actions: keep_mappings, reassign_mappings"
                )

            # Deactivate the workflow (only if it was originally active)
            if was_originally_active:
                workflow.active = False
            session.commit()

            return {
                "message": message,
                "action_taken": deactivation_data.action,
                "affected_mappings": len(dependent_mappings)
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate workflow"
        )


@router.patch("/workflows/{workflow_id}/activate")
async def activate_workflow(
    workflow_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Activate a workflow"""
    try:
        database = get_database()
        with database.get_admin_session_context() as session:
            from app.models.unified_models import Workflow
            from datetime import datetime

            # Verify workflow exists and belongs to user's client
            workflow = session.query(Workflow).filter(
                Workflow.id == workflow_id,
                Workflow.tenant_id == user.tenant_id
            ).first()

            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found"
                )

            # Activate the workflow
            workflow.active = True
            session.commit()

            logger.info(f"Admin {user.email} activated workflow {workflow_id}")

            return {"message": "Workflow activated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate workflow"
        )


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Delete a workflow (only if no active dependencies exist)"""
    try:
        database = get_database()
        with database.get_admin_session_context() as session:
            from app.models.unified_models import Workflow, StatusMapping

            # Verify workflow exists and belongs to user's client
            workflow = session.query(Workflow).filter(
                Workflow.id == workflow_id,
                Workflow.tenant_id == user.tenant_id
            ).first()

            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found"
                )

            # Check for active dependencies
            dependent_mappings = session.query(StatusMapping).filter(
                StatusMapping.workflow_id == workflow_id,
                StatusMapping.tenant_id == user.tenant_id,
                StatusMapping.active == True
            ).count()

            if dependent_mappings > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete workflow: {dependent_mappings} active status mappings still reference this workflow. Please reassign or deactivate them first."
                )

            # Delete the workflow
            session.delete(workflow)
            session.commit()

            logger.info(f"Admin {user.email} deleted workflow {workflow_id} ({workflow.step_name})")

            return {"message": f"Workflow '{workflow.step_name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete workflow"
        )


class WorkflowCreateRequest(BaseModel):
    step_name: str
    step_number: Optional[int] = None
    step_category: str
    is_commitment_point: bool = False
    integration_id: Optional[int] = None


@router.post("/workflows")
async def create_workflow(
    create_data: WorkflowCreateRequest,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Create a new workflow"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import Workflow, Integration
            from datetime import datetime

            # Validate single commitment point constraint before creating
            if create_data.is_commitment_point:
                existing_commitment_point = session.query(Workflow).filter(
                    Workflow.tenant_id == user.tenant_id,
                    Workflow.integration_id == create_data.integration_id,
                    Workflow.is_commitment_point == True,
                    Workflow.active == True
                ).first()

                if existing_commitment_point:
                    # Get integration name for better error message
                    integration_name = "All Integrations"
                    if create_data.integration_id:
                        # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
                        integration = session.query(Integration).filter(
                            Integration.id == create_data.integration_id,
                            Integration.tenant_id == user.tenant_id
                        ).first()
                        if integration:
                            integration_name = integration.provider

                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Only one commitment point is allowed per integration. A commitment point already exists for '{integration_name}': '{existing_commitment_point.step_name}'. Please uncheck the commitment point for the existing workflow first."
                    )

            # Create new workflow
            new_workflow = Workflow(
                step_name=create_data.step_name,
                step_number=create_data.step_number,
                step_category=create_data.step_category,
                is_commitment_point=create_data.is_commitment_point,
                integration_id=create_data.integration_id,
                tenant_id=user.tenant_id,
                active=True,
                created_at=datetime.utcnow(),
                last_updated_at=datetime.utcnow()
            )

            session.add(new_workflow)
            session.commit()

            logger.info(f"Admin {user.email} created workflow {new_workflow.id}")

            return {"message": "Workflow created successfully", "id": new_workflow.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workflow"
        )


@router.patch("/flow-steps/{step_id}/deactivate")
async def deactivate_flow_step(
    step_id: int,
    deactivation_data: WorkflowDeactivationRequest,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Deactivate a flow step with options for handling dependencies"""
    try:
        database = get_database()
        with database.get_admin_session_context() as session:
            from app.models.unified_models import Workflow, StatusMapping

            # Verify flow step exists and belongs to user's client
            step = session.query(Workflow).filter(
                Workflow.id == step_id,
                Workflow.tenant_id == user.tenant_id
            ).first()

            # Debug logging for tenant_id verification
            if step:
                logger.info(f"Flow step found: ID={step.id}, tenant_id={step.tenant_id}, user.tenant_id={user.tenant_id}")
            else:
                logger.warning(f"Flow step {step_id} not found for user.tenant_id={user.tenant_id}")

            if not step:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Flow step not found"
                )

            # Store original active state for messaging
            was_originally_active = step.active

            # Allow reassignment for inactive steps (needed for deletion workflow)
            # Only block if trying to deactivate an already inactive step without reassignment
            if not step.active and deactivation_data.action != "reassign_mappings":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Flow step is already inactive"
                )

            # Get dependent status mappings
            dependent_mappings = session.query(StatusMapping).filter(
                StatusMapping.workflow_id == step_id,
                StatusMapping.active == True
            ).all()

            # Handle dependencies based on user choice
            if deactivation_data.action == "reassign_mappings":
                if not deactivation_data.target_workflow_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Target workflow ID required for reassignment"
                    )

                # Verify target flow step exists and is active
                target_step = session.query(Workflow).filter(
                    Workflow.id == deactivation_data.target_workflow_id,
                    Workflow.active == True,
                    Workflow.tenant_id == user.tenant_id
                ).first()

                if not target_step:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Target workflow (ID: {deactivation_data.target_workflow_id}) not found or is inactive. Please select an active workflow for reassignment."
                    )

                # Reassign all dependent mappings
                for mapping in dependent_mappings:
                    mapping.workflow_id = deactivation_data.target_workflow_id

                if was_originally_active:
                    message = f"Flow step deactivated and {len(dependent_mappings)} status mappings reassigned to '{target_step.step_name}'"
                    logger.info(f"Admin {user.email} deactivated flow step {step_id} and reassigned {len(dependent_mappings)} mappings to {target_step.step_name}")
                else:
                    message = f"{len(dependent_mappings)} status mappings reassigned to '{target_step.step_name}' (flow step was already inactive)"
                    logger.info(f"Admin {user.email} reassigned {len(dependent_mappings)} mappings from inactive flow step {step_id} to {target_step.step_name}")

            elif deactivation_data.action == "keep_mappings":
                message = f"Flow step deactivated ({len(dependent_mappings)} status mappings will continue to reference this inactive step)"
                logger.info(f"Admin {user.email} deactivated flow step {step_id}, keeping {len(dependent_mappings)} dependent mappings active")

            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid action: {deactivation_data.action}. Supported actions: keep_mappings, reassign_mappings"
                )

            # Deactivate the flow step (only if it was originally active)
            if was_originally_active:
                step.active = False
            session.commit()

            return {
                "message": message,
                "action_taken": deactivation_data.action,
                "affected_mappings": len(dependent_mappings)
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating flow step: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate flow step"
        )


@router.patch("/flow-steps/{step_id}/toggle-active")
async def toggle_flow_step_active(
    step_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Toggle the active status of a flow step (simple activate/deactivate)"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import Workflow

            # Verify flow step exists and belongs to user's client
            step = session.query(Workflow).filter(
                Workflow.id == step_id,
                Workflow.tenant_id == user.tenant_id
            ).first()

            if not step:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Flow step not found"
                )

            # Toggle active status
            step.active = not step.active
            action = "activated" if step.active else "deactivated"

            session.commit()

            logger.info(f"Admin {user.email} {action} flow step {step_id} ({step.step_name})")

            return {
                "message": f"Flow step {action} successfully",
                "active": step.active,
                "workflow_name": step.step_name
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling flow step active status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle flow step status"
        )


@router.delete("/flow-steps/{step_id}")
async def delete_flow_step(
    step_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Delete a flow step (only allows true deletion when no dependencies exist)"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import Workflow, StatusMapping

            step = session.query(Workflow).filter(
                Workflow.id == step_id,
                Workflow.tenant_id == user.tenant_id
            ).first()

            if not step:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Flow step not found"
                )

            # Check for dependent status mappings (both active and inactive)
            dependent_mappings = session.query(StatusMapping).filter(
                StatusMapping.workflow_id == step_id
            ).count()

            if dependent_mappings > 0:
                # Block deletion if dependencies exist
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete flow step: {dependent_mappings} status mappings depend on it. Use 'Deactivate' instead or reassign dependencies first."
                )

            # Safe to delete - no dependencies
            session.delete(step)
            session.commit()

            logger.info(f"Admin {user.email} deleted flow step {step_id} ({step.step_name}) - no dependencies")

            return {"message": f"Flow step '{step.step_name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting flow step: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete flow step"
        )


@router.get("/wit-mappings/options")
async def get_wit_mapping_options(
    user: UserData = Depends(require_web_admin_authentication)
):
    """Get available options for work item type mapping dropdowns"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            from app.models.unified_models import WitMapping, Wit
            from sqlalchemy import distinct

            # Get unique source types from existing mappings
            source_types = session.query(distinct(WitMapping.wit_from)).filter(
                WitMapping.tenant_id == user.tenant_id
            ).order_by(WitMapping.wit_from).all()

            # Get unique target types from existing mappings
            target_types = session.query(distinct(WitMapping.wit_to)).filter(
                WitMapping.tenant_id == user.tenant_id
            ).order_by(WitMapping.wit_to).all()

            # Also get unique original names from Wit table (raw data from integrations)
            raw_issuetypes = session.query(distinct(Wit.original_name)).filter(
                Wit.tenant_id == user.tenant_id,
                Wit.active == True
            ).order_by(Wit.original_name).all()

            # Combine and deduplicate source options
            all_source_options = set()
            for (source_type,) in source_types:
                if source_type:
                    all_source_options.add(source_type)
            for (raw_type,) in raw_issuetypes:
                if raw_type:
                    all_source_options.add(raw_type)

            # Target types are typically standardized names
            all_target_options = set()
            for (target_type,) in target_types:
                if target_type:
                    all_target_options.add(target_type)

            return {
                "source_types": sorted(list(all_source_options)),
                "target_types": sorted(list(all_target_options))
            }

    except Exception as e:
        logger.error(f"Error fetching issue type mapping options: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issue type mapping options"
        )


@router.get("/wit-mappings")
async def get_wit_mappings(
    user: UserData = Depends(require_web_admin_authentication)
):
    """Get all work item type mappings"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # Query issue type mappings with hierarchy and integration information
            from app.models.unified_models import WitMapping, WitHierarchy, Integration

            issuetype_mappings = session.query(
                WitMapping,
                WitHierarchy.level_name.label('hierarchy_name'),
                WitHierarchy.level_number.label('hierarchy_level'),
                WitHierarchy.description.label('hierarchy_description'),
                Integration.provider.label('integration_name'),
                Integration.logo_filename.label('integration_logo')
            ).join(
                WitHierarchy, WitMapping.wits_hierarchy_id == WitHierarchy.id
            ).outerjoin(
                Integration, WitMapping.integration_id == Integration.id
            ).filter(
                WitMapping.tenant_id == user.tenant_id
            ).order_by(
                WitHierarchy.level_number.desc(),  # Order by hierarchy level descending (highest first)
                WitMapping.wit_from
            ).all()

            return [
                {
                    "id": mapping.WitMapping.id,
                    "wit_from": mapping.WitMapping.wit_from,
                    "wit_to": mapping.WitMapping.wit_to,
                    "hierarchy_level": mapping.hierarchy_level if mapping.hierarchy_level is not None else 0,
                    "hierarchy_name": mapping.hierarchy_name,
                    "hierarchy_description": mapping.hierarchy_description,
                    "wits_hierarchy_id": mapping.WitMapping.wits_hierarchy_id,
                    "integration_name": mapping.integration_name,
                    "integration_id": mapping.WitMapping.integration_id,
                    "integration_logo": mapping.integration_logo,
                    "active": mapping.WitMapping.active
                }
                for mapping in issuetype_mappings
            ]
    except Exception as e:
        logger.error(f"Error fetching issue type mappings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issue type mappings"
        )


@router.patch("/wit-mappings/{mapping_id}/activate")
async def activate_wit_mapping(
    mapping_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Activate a work item type mapping"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import WitMapping
            from datetime import datetime

            mapping = session.query(WitMapping).filter(
                WitMapping.id == mapping_id,
                WitMapping.tenant_id == user.tenant_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="WorkItem type mapping not found"
                )

            mapping.active = True
            mapping.last_updated_at = datetime.utcnow()
            session.commit()

            logger.info(f"Admin {user.email} activated issue type mapping {mapping_id}")

            return {"message": "WorkItem type mapping activated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating issue type mapping {mapping_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate issue type mapping"
        )


class WitMappingDeactivationRequest(BaseModel):
    action: str  # "keep_issuetypes", "reassign_issuetypes"
    target_mapping_id: Optional[int] = None  # Required if action is "reassign_issuetypes"


@router.patch("/wit-mappings/{mapping_id}/deactivate")
async def deactivate_wit_mapping(
    mapping_id: int,
    deactivation_data: WitMappingDeactivationRequest,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Deactivate a work item type mapping with options for handling dependencies"""
    try:
        from fastapi import status
        database = get_database()
        with database.get_admin_session_context() as session:
            from app.models.unified_models import WitMapping, Wit
            from datetime import datetime

            # Verify mapping exists and belongs to user's client
            mapping = session.query(WitMapping).filter(
                WitMapping.id == mapping_id,
                WitMapping.tenant_id == user.tenant_id
            ).first()

            # Debug logging for tenant_id verification
            if mapping:
                logger.info(f"Wit mapping found: ID={mapping.id}, tenant_id={mapping.tenant_id}, user.tenant_id={user.tenant_id}")
            else:
                logger.warning(f"Wit mapping {mapping_id} not found for user.tenant_id={user.tenant_id}")

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="WorkItem type mapping not found"
                )

            # Store original active state for messaging
            was_originally_active = mapping.active

            # Allow reassignment for inactive mappings (needed for deletion workflow)
            # Only block if trying to deactivate an already inactive mapping without reassignment
            if not mapping.active and deactivation_data.action != "reassign_issuetypes":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="WorkItem type mapping is already inactive"
                )

            # Get dependent issue types
            dependent_issuetypes = session.query(Wit).filter(
                Wit.wits_mapping_id == mapping_id,
                Wit.active == True
            ).all()

            # Handle dependencies based on user choice
            if deactivation_data.action == "reassign_issuetypes":
                if not deactivation_data.target_mapping_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Target mapping ID required for reassignment"
                    )

                # Verify target mapping exists and is active
                target_mapping = session.query(WitMapping).filter(
                    WitMapping.id == deactivation_data.target_mapping_id,
                    WitMapping.active == True,
                    WitMapping.tenant_id == user.tenant_id
                ).first()

                if not target_mapping:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Target mapping (ID: {deactivation_data.target_mapping_id}) not found or is inactive. Please select an active mapping for reassignment."
                    )

                # Reassign all dependent issue types
                for issuetype in dependent_issuetypes:
                    issuetype.wits_mapping_id = deactivation_data.target_mapping_id

                if was_originally_active:
                    message = f"WorkItem type mapping deactivated and {len(dependent_issuetypes)} issue types reassigned to '{target_mapping.wit_to}'"
                    logger.info(f"Admin {user.email} deactivated mapping {mapping_id} and reassigned {len(dependent_issuetypes)} issue types to {target_mapping.wit_to}")
                else:
                    message = f"{len(dependent_issuetypes)} issue types reassigned to '{target_mapping.wit_to}' (mapping was already inactive)"
                    logger.info(f"Admin {user.email} reassigned {len(dependent_issuetypes)} issue types from inactive mapping {mapping_id} to {target_mapping.wit_to}")

            elif deactivation_data.action == "keep_issuetypes":
                message = f"WorkItem type mapping deactivated ({len(dependent_issuetypes)} issue types will continue to reference this inactive mapping)"
                logger.info(f"Admin {user.email} deactivated mapping {mapping_id}, keeping {len(dependent_issuetypes)} dependent issue types active")

            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid action: {deactivation_data.action}. Supported actions: keep_issuetypes, reassign_issuetypes"
                )

            # Deactivate the mapping (only if it was originally active)
            if was_originally_active:
                mapping.active = False
                mapping.last_updated_at = datetime.utcnow()
            session.commit()

            return {
                "message": message,
                "action_taken": deactivation_data.action,
                "affected_issuetypes": len(dependent_issuetypes)
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating issue type mapping {mapping_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate issue type mapping"
        )


@router.post("/wit-mappings")
async def create_wit_mapping(
    create_data: dict,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Create a new work item type mapping"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import WitMapping, WitHierarchy
            from datetime import datetime

            # Validate hierarchy level exists and is active
            hierarchy = session.query(WitHierarchy).filter(
                WitHierarchy.level_number == create_data['hierarchy_level'],
                WitHierarchy.tenant_id == user.tenant_id,
                WitHierarchy.active == True
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Active hierarchy level {create_data['hierarchy_level']} not found"
                )

            # Check for duplicate mapping
            existing = session.query(WitMapping).filter(
                WitMapping.wit_from == create_data['wit_from'],
                WitMapping.tenant_id == user.tenant_id
            ).first()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mapping for this work item type already exists"
                )

            # Create new mapping
            new_mapping = WitMapping(
                wit_from=create_data['wit_from'],
                wit_to=create_data['wit_to'],
                wits_hierarchy_id=hierarchy.id,
                integration_id=create_data.get('integration_id'),
                tenant_id=user.tenant_id,
                active=True,
                created_at=datetime.utcnow(),
                last_updated_at=datetime.utcnow()
            )

            session.add(new_mapping)
            session.commit()

            logger.info(f"Admin {user.email} created issue type mapping {new_mapping.id}")

            return {"message": "WorkItem type mapping created successfully", "id": new_mapping.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating issue type mapping: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create issue type mapping"
        )


@router.put("/wit-mappings/{mapping_id}")
async def update_wit_mapping(
    mapping_id: int,
    update_data: dict,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Update a work item type mapping"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import WitMapping, WitHierarchy
            from datetime import datetime

            mapping = session.query(WitMapping).filter(
                WitMapping.id == mapping_id,
                WitMapping.tenant_id == user.tenant_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="WorkItem type mapping not found"
                )

            # Validate hierarchy level exists and is active
            hierarchy = session.query(WitHierarchy).filter(
                WitHierarchy.level_number == update_data['hierarchy_level'],
                WitHierarchy.tenant_id == user.tenant_id,
                WitHierarchy.active == True
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Active hierarchy level {update_data['hierarchy_level']} not found"
                )

            # Check for duplicate mapping (excluding current one)
            existing = session.query(WitMapping).filter(
                WitMapping.wit_from == update_data['wit_from'],
                WitMapping.tenant_id == user.tenant_id,
                WitMapping.id != mapping_id
            ).first()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mapping for this work item type already exists"
                )

            # Update mapping
            mapping.wit_from = update_data['wit_from']
            mapping.wit_to = update_data['wit_to']
            mapping.wits_hierarchy_id = hierarchy.id
            mapping.integration_id = update_data.get('integration_id')
            mapping.last_updated_at = datetime.utcnow()

            session.commit()

            logger.info(f"Admin {user.email} updated issue type mapping {mapping_id}")

            return {"message": "WorkItem type mapping updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating issue type mapping {mapping_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update issue type mapping"
        )


@router.delete("/wit-mappings/{mapping_id}")
async def delete_wit_mapping(
    mapping_id: int,
    deletion_data: Optional[WitMappingDeactivationRequest] = None,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Delete a work item type mapping with options for handling dependencies"""
    try:
        database = get_database()
        with database.get_admin_session_context() as session:
            from app.models.unified_models import WitMapping, Wit
            from datetime import datetime

            mapping = session.query(WitMapping).filter(
                WitMapping.id == mapping_id,
                WitMapping.tenant_id == user.tenant_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="WorkItem type mapping not found"
                )

            # Get dependent issue types
            dependent_issuetypes = session.query(Wit).filter(
                Wit.wits_mapping_id == mapping_id,
                Wit.active == True
            ).all()

            # If there are dependencies and no deletion data provided, block deletion
            if dependent_issuetypes and not deletion_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete mapping: {len(dependent_issuetypes)} active issue types are using this mapping. Please specify reassignment options."
                )

            # Handle dependencies if deletion data is provided
            if deletion_data and dependent_issuetypes:
                if deletion_data.action == "reassign_issuetypes":
                    if not deletion_data.target_mapping_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Target mapping ID required for reassignment"
                        )

                    # Verify target mapping exists and is active
                    target_mapping = session.query(WitMapping).filter(
                        WitMapping.id == deletion_data.target_mapping_id,
                        WitMapping.active == True,
                        WitMapping.tenant_id == user.tenant_id
                    ).first()

                    if not target_mapping:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Target mapping (ID: {deletion_data.target_mapping_id}) not found or is inactive"
                        )

                    # Reassign all dependent issue types to the target mapping
                    for issuetype in dependent_issuetypes:
                        issuetype.wits_mapping_id = deletion_data.target_mapping_id
                        issuetype.last_updated_at = datetime.utcnow()

                    message = f"WorkItem type mapping deleted and {len(dependent_issuetypes)} issue types reassigned to target mapping"
                    logger.info(f"Admin {user.email} deleted mapping {mapping_id}, reassigned {len(dependent_issuetypes)} issue types to mapping {deletion_data.target_mapping_id}")

                elif deletion_data.action == "keep_issuetypes":
                    # Keep issue types but mark them as orphaned (they'll reference a deleted mapping)
                    # This is generally not recommended but allowed for data preservation
                    message = f"WorkItem type mapping deleted ({len(dependent_issuetypes)} issue types will reference deleted mapping)"
                    logger.info(f"Admin {user.email} deleted mapping {mapping_id}, keeping {len(dependent_issuetypes)} dependent issue types")

                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid action: {deletion_data.action}. Supported actions: keep_issuetypes, reassign_issuetypes"
                    )
            else:
                message = "WorkItem type mapping deleted successfully"
                logger.info(f"Admin {user.email} deleted issue type mapping {mapping_id}")

            # Delete the mapping
            session.delete(mapping)
            session.commit()

            return {"message": message}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting issue type mapping {mapping_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete issue type mapping"
        )


@router.get("/wit-mappings/{mapping_id}/dependencies")
async def get_wit_mapping_dependencies(
    mapping_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Get dependencies for a work item type mapping"""
    try:
        database = get_database()
        with database.get_admin_session_context() as session:
            from app.models.unified_models import WitMapping, WorkItem, Wit

            mapping = session.query(WitMapping).filter(
                WitMapping.id == mapping_id,
                WitMapping.tenant_id == user.tenant_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="WorkItem type mapping not found"
                )

            # Count dependent issue types that use this mapping
            dependent_issuetypes_count = session.query(Wit).filter(
                Wit.wits_mapping_id == mapping_id,
                Wit.active == True
            ).count()

            # Count dependent issues through the issue types
            dependent_issues_count = session.query(WorkItem).join(
                Wit, WorkItem.wit_id == Wit.id
            ).filter(
                Wit.wits_mapping_id == mapping_id,
                Wit.active == True,
                WorkItem.active == True
            ).count()

            # Get available reassignment targets (active issue type mappings, excluding current)
            reassignment_targets = session.query(WitMapping).filter(
                WitMapping.active == True,
                WitMapping.id != mapping_id,
                WitMapping.tenant_id == user.tenant_id
            ).order_by(WitMapping.wit_to).all()

            # Get detailed dependency information
            dependent_issuetypes = session.query(Wit).filter(
                Wit.wits_mapping_id == mapping_id,
                Wit.active == True
            ).all()

            issuetype_details = []
            for issuetype in dependent_issuetypes:
                # Count issues for this issuetype
                issue_count = session.query(WorkItem).filter(
                    WorkItem.wit_id == issuetype.id,
                    WorkItem.active == True
                ).count()

                issuetype_details.append({
                    "id": issuetype.id,
                    "original_name": issuetype.original_name,
                    "hierarchy_level": issuetype.hierarchy_level,
                    "affected_issues": issue_count
                })

            return {
                "mapping_id": mapping_id,
                "mapping": {
                    "id": mapping.id,
                    "wit_from": mapping.wit_from,
                    "wit_to": mapping.wit_to,
                    "hierarchy_level": mapping.wit_hierarchy.level_number if mapping.wit_hierarchy else None
                },
                "can_delete_safely": dependent_issuetypes_count == 0 and dependent_issues_count == 0,
                "dependent_issuetypes_count": dependent_issuetypes_count,
                "dependent_issues_count": dependent_issues_count,
                "has_dependencies": dependent_issuetypes_count > 0 or dependent_issues_count > 0,
                "dependent_issuetypes": issuetype_details,
                "reassignment_targets": [
                    {
                        "id": target.id,
                        "wit_from": target.wit_from,
                        "wit_to": target.wit_to,
                        "hierarchy_level": target.wit_hierarchy.level_number if target.wit_hierarchy else None
                    }
                    for target in reassignment_targets
                ]
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dependencies for issue type mapping {mapping_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get mapping dependencies"
        )


@router.get("/wits-hierarchies")
async def get_wits_hierarchies(user: UserData = Depends(require_web_admin_authentication)):
    """Get all work item type hierarchies"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            from app.models.unified_models import WitHierarchy, Integration

            hierarchies = session.query(
                WitHierarchy,
                Integration.provider.label('integration_name'),
                Integration.logo_filename.label('integration_logo')
            ).outerjoin(
                Integration, WitHierarchy.integration_id == Integration.id
            ).filter(
                WitHierarchy.tenant_id == user.tenant_id
            ).order_by(WitHierarchy.level_number.desc()).all()

            hierarchies_list = [
                {
                    "id": hierarchy.WitHierarchy.id,
                    "level_name": hierarchy.WitHierarchy.level_name,
                    "level_number": hierarchy.WitHierarchy.level_number,
                    "description": hierarchy.WitHierarchy.description,
                    "integration_name": hierarchy.integration_name,
                    "integration_id": hierarchy.WitHierarchy.integration_id,
                    "integration_logo": hierarchy.integration_logo,
                    "active": hierarchy.WitHierarchy.active
                }
                for hierarchy in hierarchies
            ]

            return {
                "success": True,
                "hierarchies": hierarchies_list
            }

    except Exception as e:
        logger.error(f"Error fetching issue type hierarchies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issue type hierarchies"
        )


class WitHierarchyCreateRequest(BaseModel):
    level_name: str
    level_number: int
    description: Optional[str] = None
    integration_id: Optional[int] = None


class WitHierarchyUpdateRequest(BaseModel):
    level_name: str
    level_number: int
    description: Optional[str] = None
    integration_id: Optional[int] = None


@router.post("/wits-hierarchies")
async def create_wits_hierarchy(
    create_data: WitHierarchyCreateRequest,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Create a new work item type hierarchy"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import WitHierarchy
            from datetime import datetime

            # Note: Multiple hierarchies can have the same level_number
            # No uniqueness check needed for level_number

            # Create new hierarchy
            new_hierarchy = WitHierarchy(
                level_name=create_data.level_name,
                level_number=create_data.level_number,
                description=create_data.description,
                integration_id=create_data.integration_id,
                tenant_id=user.tenant_id,
                active=True,
                created_at=datetime.utcnow(),
                last_updated_at=datetime.utcnow()
            )

            session.add(new_hierarchy)
            session.commit()

            logger.info(f"Admin {user.email} created issuetype hierarchy {new_hierarchy.id}")

            return {"message": "Wit hierarchy created successfully", "id": new_hierarchy.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating issuetype hierarchy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create issuetype hierarchy"
        )


@router.put("/wits-hierarchies/{hierarchy_id}")
async def update_wits_hierarchy(
    hierarchy_id: int,
    update_data: WitHierarchyUpdateRequest,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Update a work item type hierarchy"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import WitHierarchy
            from datetime import datetime

            hierarchy = session.query(WitHierarchy).filter(
                WitHierarchy.id == hierarchy_id,
                WitHierarchy.tenant_id == user.tenant_id
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Wit hierarchy not found"
                )

            # Check if level_number conflicts with another hierarchy
            if update_data.level_number != hierarchy.level_number:
                existing = session.query(WitHierarchy).filter(
                    WitHierarchy.level_number == update_data.level_number,
                    WitHierarchy.tenant_id == user.tenant_id,
                    WitHierarchy.id != hierarchy_id
                ).first()

                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Hierarchy level {update_data.level_number} already exists"
                    )

            # Update hierarchy
            hierarchy.level_name = update_data.level_name
            hierarchy.level_number = update_data.level_number
            hierarchy.description = update_data.description
            hierarchy.integration_id = update_data.integration_id
            hierarchy.last_updated_at = datetime.utcnow()

            session.commit()

            logger.info(f"Admin {user.email} updated issuetype hierarchy {hierarchy_id}")

            return {"message": "Wit hierarchy updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating issuetype hierarchy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update issuetype hierarchy"
        )


@router.delete("/wits-hierarchies/{hierarchy_id}")
async def delete_wits_hierarchy(
    hierarchy_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Delete a work item type hierarchy"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.models.unified_models import WitHierarchy, WitMapping

            hierarchy = session.query(WitHierarchy).filter(
                WitHierarchy.id == hierarchy_id,
                WitHierarchy.tenant_id == user.tenant_id
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Wit hierarchy not found"
                )

            # Check if hierarchy is being used by any mappings
            mappings_count = session.query(WitMapping).filter(
                WitMapping.wits_hierarchy_id == hierarchy_id
            ).count()

            if mappings_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete hierarchy: {mappings_count} issue type mappings are using this hierarchy"
                )

            session.delete(hierarchy)
            session.commit()

            logger.info(f"Admin {user.email} deleted issuetype hierarchy {hierarchy_id}")

            return {"message": "Wit hierarchy deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting issuetype hierarchy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete issuetype hierarchy"
        )


@router.get("/wits-hierarchies/{hierarchy_id}/dependencies")
async def get_wits_hierarchy_dependencies(
    hierarchy_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Get dependencies for a work item type hierarchy"""
    try:
        database = get_database()
        with database.get_admin_session_context() as session:
            from app.models.unified_models import WitHierarchy, WitMapping, WorkItem, Wit

            hierarchy = session.query(WitHierarchy).filter(
                WitHierarchy.id == hierarchy_id,
                WitHierarchy.tenant_id == user.tenant_id
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="WorkItem type hierarchy not found"
                )

            # Count dependent mappings that use this hierarchy
            dependent_mappings_count = session.query(WitMapping).filter(
                WitMapping.wits_hierarchy_id == hierarchy_id,
                WitMapping.active == True
            ).count()

            # Count dependent issues through the mappings and issue types
            dependent_issues_count = session.query(WorkItem).join(
                Wit, WorkItem.wit_id == Wit.id
            ).join(
                WitMapping, Wit.wits_mapping_id == WitMapping.id
            ).filter(
                WitMapping.wits_hierarchy_id == hierarchy_id,
                WitMapping.active == True,
                Wit.active == True,
                WorkItem.active == True
            ).count()

            # Get available reassignment targets (active hierarchies, excluding current)
            reassignment_targets = session.query(WitHierarchy).filter(
                WitHierarchy.active == True,
                WitHierarchy.id != hierarchy_id,
                WitHierarchy.tenant_id == user.tenant_id
            ).order_by(WitHierarchy.level_number.desc()).all()

            return {
                "hierarchy_id": hierarchy_id,
                "hierarchy": {
                    "id": hierarchy.id,
                    "level_name": hierarchy.level_name,
                    "level_number": hierarchy.level_number,
                    "description": hierarchy.description
                },
                "can_delete_safely": dependent_mappings_count == 0 and dependent_issues_count == 0,
                "dependent_mappings_count": dependent_mappings_count,
                "dependent_issues_count": dependent_issues_count,
                "has_dependencies": dependent_mappings_count > 0 or dependent_issues_count > 0,
                "reassignment_targets": [
                    {
                        "id": target.id,
                        "level_name": target.level_name,
                        "level_number": target.level_number,
                        "description": target.description
                    }
                    for target in reassignment_targets
                ]
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dependencies for hierarchy {hierarchy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get hierarchy dependencies"
        )


class WitHierarchyDeactivationRequest(BaseModel):
    action: str  # "keep_mappings", "reassign_mappings"
    target_hierarchy_id: Optional[int] = None  # Required if action is "reassign_mappings"


@router.patch("/wits-hierarchies/{hierarchy_id}/deactivate")
async def deactivate_wits_hierarchy(
    hierarchy_id: int,
    deactivation_data: WitHierarchyDeactivationRequest,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Deactivate a work item type hierarchy with options for handling dependencies"""
    try:
        database = get_database()
        with database.get_admin_session_context() as session:
            from app.models.unified_models import WitHierarchy, WitMapping
            from datetime import datetime

            # Verify hierarchy exists and belongs to user's client
            hierarchy = session.query(WitHierarchy).filter(
                WitHierarchy.id == hierarchy_id,
                WitHierarchy.tenant_id == user.tenant_id
            ).first()

            # Debug logging for tenant_id verification
            if hierarchy:
                logger.info(f"Wit hierarchy found: ID={hierarchy.id}, tenant_id={hierarchy.tenant_id}, user.tenant_id={user.tenant_id}")
            else:
                logger.warning(f"Wit hierarchy {hierarchy_id} not found for user.tenant_id={user.tenant_id}")

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="WorkItem type hierarchy not found"
                )

            # Store original active state for messaging
            was_originally_active = hierarchy.active

            # Allow reassignment for inactive hierarchies (needed for deletion workflow)
            # Only block if trying to deactivate an already inactive hierarchy without reassignment
            if not hierarchy.active and deactivation_data.action != "reassign_mappings":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="WorkItem type hierarchy is already inactive"
                )

            # Get dependent mappings
            dependent_mappings = session.query(WitMapping).filter(
                WitMapping.wits_hierarchy_id == hierarchy_id,
                WitMapping.active == True
            ).all()

            # Handle dependencies based on user choice
            if deactivation_data.action == "reassign_mappings":
                if not deactivation_data.target_hierarchy_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Target hierarchy ID required for reassignment"
                    )

                # Verify target hierarchy exists and is active
                target_hierarchy = session.query(WitHierarchy).filter(
                    WitHierarchy.id == deactivation_data.target_hierarchy_id,
                    WitHierarchy.active == True,
                    WitHierarchy.tenant_id == user.tenant_id
                ).first()

                if not target_hierarchy:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Target hierarchy (ID: {deactivation_data.target_hierarchy_id}) not found or is inactive. Please select an active hierarchy for reassignment."
                    )

                # Reassign all dependent mappings
                for mapping in dependent_mappings:
                    mapping.wits_hierarchy_id = deactivation_data.target_hierarchy_id

                if was_originally_active:
                    message = f"WorkItem type hierarchy deactivated and {len(dependent_mappings)} mappings reassigned to '{target_hierarchy.level_name}'"
                    logger.info(f"Admin {user.email} deactivated hierarchy {hierarchy_id} and reassigned {len(dependent_mappings)} mappings to {target_hierarchy.level_name}")
                else:
                    message = f"{len(dependent_mappings)} mappings reassigned to '{target_hierarchy.level_name}' (hierarchy was already inactive)"
                    logger.info(f"Admin {user.email} reassigned {len(dependent_mappings)} mappings from inactive hierarchy {hierarchy_id} to {target_hierarchy.level_name}")

            elif deactivation_data.action == "keep_mappings":
                message = f"WorkItem type hierarchy deactivated ({len(dependent_mappings)} mappings will continue to reference this inactive hierarchy)"
                logger.info(f"Admin {user.email} deactivated hierarchy {hierarchy_id}, keeping {len(dependent_mappings)} dependent mappings active")

            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid action: {deactivation_data.action}. Supported actions: keep_mappings, reassign_mappings"
                )

            # Deactivate the hierarchy (only if it was originally active)
            if was_originally_active:
                hierarchy.active = False
                hierarchy.last_updated_at = datetime.utcnow()
            session.commit()

            return {
                "message": message,
                "action_taken": deactivation_data.action,
                "affected_mappings": len(dependent_mappings)
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating hierarchy {hierarchy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate hierarchy"
        )


@router.patch("/wits-hierarchies/{hierarchy_id}/activate")
async def activate_wits_hierarchy(
    hierarchy_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Activate a work item type hierarchy"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from datetime import datetime

            hierarchy = session.query(WitHierarchy).filter(
                WitHierarchy.id == hierarchy_id,
                WitHierarchy.tenant_id == user.tenant_id
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="WorkItem type hierarchy not found"
                )

            hierarchy.active = True
            hierarchy.last_updated_at = datetime.utcnow()
            session.commit()

            logger.info(f"Admin {user.email} activated hierarchy {hierarchy_id}")

            return {"message": "WorkItem type hierarchy activated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating hierarchy {hierarchy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate hierarchy"
        )


# Permission Management Endpoints

@router.get("/permissions/matrix")
async def get_permission_matrix(
    admin_user: UserData = Depends(require_web_admin_authentication)
):
    """Redirect to Backend Service for permission matrix"""
    from app.core.config import get_settings
    settings = get_settings()
    backend_url = settings.BACKEND_SERVICE_URL

    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail=f"Permission management is now handled by Backend Service. Please use: {backend_url}/api/v1/admin/permissions/matrix",
        headers={"Location": f"{backend_url}/api/v1/admin/permissions/matrix"}
    )


# Active Sessions Management Endpoints - Redirected to Backend Service

@router.get("/active-sessions")
async def get_active_sessions(
    user: UserData = Depends(require_web_admin_authentication)
):
    """Redirect to Backend Service for active sessions"""
    from app.core.config import get_settings
    settings = get_settings()
    backend_url = settings.BACKEND_SERVICE_URL

    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail=f"Session management is now handled by Backend Service. Please use: {backend_url}/api/v1/admin/active-sessions",
        headers={"Location": f"{backend_url}/api/v1/admin/active-sessions"}
    )


@router.post("/terminate-all-sessions")
async def terminate_all_sessions(
    user: UserData = Depends(require_web_admin_authentication)
):
    """Redirect to Backend Service for session termination"""
    from app.core.config import get_settings
    settings = get_settings()
    backend_url = settings.BACKEND_SERVICE_URL

    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail=f"Session management is now handled by Backend Service. Please use: {backend_url}/api/v1/admin/terminate-all-sessions",
        headers={"Location": f"{backend_url}/api/v1/admin/terminate-all-sessions"}
    )


@router.post("/terminate-session/{session_id}")
async def terminate_user_session(
    session_id: int,
    user: UserData = Depends(require_web_admin_authentication)
):
    """Redirect to Backend Service for session termination"""
    from app.core.config import get_settings
    settings = get_settings()
    backend_url = settings.BACKEND_SERVICE_URL

    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail=f"Session management is now handled by Backend Service. Please use: {backend_url}/api/v1/admin/terminate-session/{session_id}",
        headers={"Location": f"{backend_url}/api/v1/admin/terminate-session/{session_id}"}
    )




