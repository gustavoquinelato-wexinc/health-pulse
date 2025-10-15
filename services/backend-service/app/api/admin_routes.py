"""
Admin Panel API Routes

Provides administrative functionality for user management, role assignment,
and system configuration. Only accessible to admin users.

CLEAN ARCHITECTURE - Backend Service Responsibilities:
- User Management (CRUD operations)
- Session Management (cross-service)
- Permission Management (delegated to Auth Service RBAC)
- System Statistics (for frontend dashboard)
- Theme/Color Settings (UI configuration)
- Tenant Management (CRUD + logo upload)
- Debug Endpoints (development support)

ETL-specific functionality (integrations, workflows, status mappings, issuetypes) 
is handled exclusively by the ETL service.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from pydantic import BaseModel, EmailStr

from app.core.database import get_database
from app.models.unified_models import (
    User, UserPermission, UserSession, Integration, Project, WorkItem, Tenant, Changelog,
    Repository, Pr, PrCommit, PrReview, PrComment,
    WorkItemPrLink, Wit, Status, JobSchedule, SystemSettings, TenantColors,
    StatusMapping, Workflow, WitMapping, WitHierarchy, MigrationHistory,
    ProjectWits, ProjectsStatuses
)
from app.auth.auth_middleware import require_permission, require_authentication
from app.auth.auth_service import get_auth_service
# RBAC is centralized in Auth Service; local permissions are not used
from app.core.logging_config import get_logger
import httpx
import asyncio
from app.core.config import get_settings
from app.services.color_resolution_service import ColorResolutionService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
settings = get_settings()

# Initialize color resolution service
color_resolution_service = ColorResolutionService()


# Worker Management Models (Tier-based Architecture)
class WorkerStatusResponse(BaseModel):
    """Response model for worker status."""
    running: bool
    workers: Dict[str, Dict[str, Any]]
    queue_stats: Dict[str, Any]
    raw_data_stats: Dict[str, Any]


class WorkerActionRequest(BaseModel):
    """Request model for worker actions."""
    action: str  # 'start', 'stop', 'restart'


class TenantTierRequest(BaseModel):
    """Request model for changing tenant tier."""
    tier: str  # 'free', 'basic', 'premium', 'enterprise'


class TenantTierResponse(BaseModel):
    """Response model for tenant tier configuration."""
    tenant_id: int
    tier: str
    worker_allocation: Dict[str, int]  # extraction, transform, vectorization counts


class WorkerPoolConfigResponse(BaseModel):
    """Response model for worker pool configuration."""
    tier_configs: Dict[str, Dict[str, int]]  # tier -> {extraction, transform, vectorization}
    current_tenant_tier: str
    current_tenant_allocation: Dict[str, int]


class WorkerLogsResponse(BaseModel):
    """Response model for worker logs."""
    logs: List[str]
    total_lines: int


# Additional Worker Management Schemas
class WorkerActionResponse(BaseModel):
    success: bool
    message: str
    worker_status: Optional[WorkerStatusResponse] = None


# 🚀 ETL Service Notification Functions
async def notify_etl_color_schema_change(tenant_id: int, colors: dict):
    """Notify ETL service of color schema changes"""
    try:
        # Get ETL service URL from configuration
        etl_url = f"{settings.ETL_SERVICE_URL}/api/v1/internal/color-schema-changed"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(etl_url, json={
                "tenant_id": tenant_id,
                "colors": colors,
                "event_type": "color_update"
            })

            if response.status_code == 200:
                logger.info(f"✅ ETL service notified of color schema change for client {tenant_id}")
            else:
                logger.warning(f"⚠️ ETL service notification failed: {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ Could not notify ETL service of color change: {e}")
        # Don't fail the main operation if ETL notification fails


async def notify_etl_color_schema_mode_change(tenant_id: int, mode: str):
    """Notify ETL service of color schema mode changes"""
    try:
        # Get ETL service URL from configuration
        etl_url = f"{settings.ETL_SERVICE_URL}/api/v1/internal/color-schema-mode-changed"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(etl_url, json={
                "tenant_id": tenant_id,
                "mode": mode,
                "event_type": "mode_update"
            })

            if response.status_code == 200:
                logger.info(f"✅ ETL service notified of color schema mode change for client {tenant_id}")
            else:
                logger.warning(f"⚠️ ETL service mode notification failed: {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ Could not notify ETL service of mode change: {e}")
        # Don't fail the main operation if ETL notification fails


async def notify_frontend_color_update(tenant_id: int, colors: dict):
    """Notify frontend clients of color schema changes via WebSocket through ETL service"""
    try:
        # The ETL service handles WebSocket broadcasting, so we can piggyback on that
        # The ETL notification already includes WebSocket broadcasting to clients
        logger.info(f"✅ Frontend WebSocket notification handled via ETL service for client {tenant_id}")
    except Exception as e:
        logger.warning(f"⚠️ Could not notify frontend of color change: {e}")
        # Don't fail the main operation if frontend notification fails


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class UserResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    active: bool
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None

class UserCreateRequest(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: str
    role: str

class UserUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None
    current_password: Optional[str] = None

class DatabaseStats(BaseModel):
    database_size: str
    table_count: int
    total_records: int
    monthly_growth_percentage: Optional[float] = None

class UserStats(BaseModel):
    total_users: int
    active_users: int
    logged_users: int
    admin_users: int
    today_active: int
    week_active: int
    month_active: int
    inactive_30_days: int

class PerformanceStats(BaseModel):
    connection_pool_utilization: float
    active_connections: int
    total_connections: int
    avg_response_time_ms: Optional[float] = None
    database_health: str

class SystemStatsResponse(BaseModel):
    database: DatabaseStats
    users: UserStats
    performance: PerformanceStats
    tables: Dict[str, int]
    table_categories: Optional[Dict[str, Dict[str, int]]] = None
    database_size_mb: Optional[float] = None

class ActiveSessionResponse(BaseModel):
    id: int
    user_id: int
    user_email: str
    created_at: str
    last_activity_at: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    token_hash: Optional[str] = None
    is_current: bool = False



class UnifiedColorSchemaRequest(BaseModel):
    light_colors: Dict[str, str]
    dark_colors: Dict[str, str]
    accessibility_level: Optional[str] = 'regular'  # 'regular', 'AA', 'AAA'

class ColorSchemaModeRequest(BaseModel):
    mode: str  # "default" or "custom"

class TenantResponse(BaseModel):
    id: int
    name: str
    website: Optional[str] = None
    active: bool
    assets_folder: Optional[str] = None
    logo_filename: Optional[str] = None

class TenantCreateRequest(BaseModel):
    name: str
    website: Optional[str] = None
    active: Optional[bool] = None

class TenantUpdateRequest(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    active: Optional[bool] = None
    assets_folder: Optional[str] = None
    logo_filename: Optional[str] = None

class PermissionMatrixResponse(BaseModel):
    roles: List[str]
    resources: List[str]
    actions: List[str]
    matrix: Dict[str, Dict[str, List[str]]]  # role -> resource -> actions


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get all users for current user's client with pagination"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
            users = session.query(User).filter(
                User.tenant_id == user.tenant_id
            ).offset(skip).limit(limit).all()

            return [
                UserResponse(
                    id=u.id,
                    email=u.email,
                    first_name=u.first_name,
                    last_name=u.last_name,
                    role=u.role,
                    active=u.active,
                    created_at=u.created_at.isoformat() if u.created_at else None,
                    last_login_at=u.last_login_at.isoformat() if u.last_login_at else None
                )
                for u in users
            ]
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch users"
        )


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreateRequest,
    admin_user: User = Depends(require_permission("users", "execute"))
):
    """Create a new user"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper
            from app.auth.auth_service import get_auth_service

            # Check if user already exists
            existing_user = session.query(User).filter(
                User.email == user_data.email,
                User.tenant_id == admin_user.tenant_id
            ).first()

            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User with this email already exists"
                )

            # Validate role
            valid_roles = ['admin', 'user', 'viewer']
            if user_data.role not in valid_roles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role: {user_data.role}. Must be one of: {valid_roles}"
                )

            # Hash password
            auth_service = get_auth_service()
            hashed_password = auth_service._hash_password(user_data.password)

            # Create new user
            new_user = User(
                email=user_data.email,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                password_hash=hashed_password,
                role=user_data.role,
                is_admin=(user_data.role == 'admin'),  # ✅ Set is_admin based on role
                tenant_id=admin_user.tenant_id,
                active=True,
                created_at=DateTimeHelper.now_utc(),
                last_login_at=None
            )

            session.add(new_user)
            session.commit()

            logger.info(f"Admin {admin_user.email} created user {new_user.email}")

            return UserResponse(
                id=new_user.id,
                email=new_user.email,
                first_name=new_user.first_name,
                last_name=new_user.last_name,
                role=new_user.role,
                active=new_user.active,
                created_at=new_user.created_at.isoformat() if new_user.created_at else None,
                last_login_at=None
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdateRequest,
    admin_user: User = Depends(require_permission("users", "admin"))
):
    """Update an existing user"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Find the user to update
            user_to_update = session.query(User).filter(
                User.id == user_id,
                User.tenant_id == admin_user.tenant_id
            ).first()

            if not user_to_update:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Update fields if provided
            if user_data.first_name is not None:
                user_to_update.first_name = user_data.first_name

            if user_data.last_name is not None:
                user_to_update.last_name = user_data.last_name

            if user_data.email is not None:
                # Check if email is already taken by another user
                existing_user = session.query(User).filter(
                    User.email == user_data.email,
                    User.tenant_id == admin_user.tenant_id,
                    User.id != user_id
                ).first()

                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already taken by another user"
                    )
                user_to_update.email = user_data.email

            if user_data.role is not None:
                # Validate role
                valid_roles = ['admin', 'user', 'viewer']
                if user_data.role not in valid_roles:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid role: {user_data.role}. Must be one of: {valid_roles}"
                    )
                user_to_update.role = user_data.role

            if user_data.active is not None:
                user_to_update.active = user_data.active

            # Handle password change
            if user_data.password is not None:
                from app.auth.auth_service import get_auth_service

                # Validate current password if provided
                if user_data.current_password is not None:
                    auth_service = get_auth_service()
                    if not auth_service._verify_password(user_data.current_password, user_to_update.password_hash):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Current password is incorrect"
                        )

                    # Check if new password is different from current password
                    if auth_service._verify_password(user_data.password, user_to_update.password_hash):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="New password must be different from current password"
                        )

                # Hash new password
                auth_service = get_auth_service()
                user_to_update.password_hash = auth_service._hash_password(user_data.password)

            session.commit()

            logger.info(f"Admin {admin_user.email} updated user {user_to_update.email}")

            return UserResponse(
                id=user_to_update.id,
                email=user_to_update.email,
                first_name=user_to_update.first_name,
                last_name=user_to_update.last_name,
                role=user_to_update.role,
                active=user_to_update.active,
                created_at=user_to_update.created_at.isoformat() if user_to_update.created_at else None,
                last_login_at=user_to_update.last_login_at.isoformat() if user_to_update.last_login_at else None
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin_user: User = Depends(require_permission("users", "delete"))
):
    """Delete a user"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Find the user to delete
            user_to_delete = session.query(User).filter(
                User.id == user_id,
                User.tenant_id == admin_user.tenant_id
            ).first()

            if not user_to_delete:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Prevent self-deletion
            if user_to_delete.id == admin_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete your own account"
                )

            # Count permissions
            user_permissions = session.query(UserPermission).filter(
                UserPermission.user_id == user_id
            ).count()

            # Delete user permissions first (foreign key constraint)
            session.query(UserPermission).filter(
                UserPermission.user_id == user_id
            ).delete()

            # Delete user sessions
            session.query(UserSession).filter(
                UserSession.user_id == user_id
            ).delete()

            # Delete the user
            session.delete(user_to_delete)
            session.commit()

            logger.info(f"Admin {admin_user.email} deleted user {user_to_delete.email} (had {user_permissions} permissions)")

            return {"message": f"User {user_to_delete.email} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )


# ============================================================================
# SYSTEM STATISTICS ENDPOINTS
# ============================================================================

@router.get("/system/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    admin_user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get system statistics for the admin dashboard"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # ✅ SECURITY: All counts filtered by tenant_id
            tenant_id = admin_user.tenant_id

            # Count users
            total_users = session.query(User).filter(
                User.tenant_id == tenant_id
            ).count()

            active_users = session.query(User).filter(
                User.tenant_id == tenant_id,
                User.active == True
            ).count()

            # Count logged users (active sessions)
            logged_users = session.query(UserSession).join(
                User, UserSession.user_id == User.id
            ).filter(
                User.tenant_id == tenant_id,
                UserSession.active == True
            ).count()

            # Count admin users
            admin_users = session.query(User).filter(
                User.tenant_id == tenant_id,
                User.role == 'admin'
            ).count()

            # Calculate time-based user activity metrics
            from datetime import timedelta
            from app.core.utils import DateTimeHelper
            now_utc = DateTimeHelper.now_default()

            # Initialize time-based metrics with safe defaults
            today_active = 0
            week_active = 0
            month_active = 0
            inactive_30_days = 0

            # Only calculate time-based metrics if UserSession table has data
            try:
                # Check if UserSession table exists and has records
                session_count = session.query(UserSession).count()

                if session_count > 0:
                    # Today active users (users with sessions created today)
                    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
                    today_active = session.query(User).join(
                        UserSession, User.id == UserSession.user_id
                    ).filter(
                        User.tenant_id == tenant_id,
                        User.active == True,
                        UserSession.created_at >= today_start
                    ).distinct().count()

                    # Week active users (users with sessions created in last 7 days)
                    week_start = now_utc - timedelta(days=7)
                    week_active = session.query(User).join(
                        UserSession, User.id == UserSession.user_id
                    ).filter(
                        User.tenant_id == tenant_id,
                        User.active == True,
                        UserSession.created_at >= week_start
                    ).distinct().count()

                    # Month active users (users with sessions created in last 30 days)
                    month_start = now_utc - timedelta(days=30)
                    month_active = session.query(User).join(
                        UserSession, User.id == UserSession.user_id
                    ).filter(
                        User.tenant_id == tenant_id,
                        User.active == True,
                        UserSession.created_at >= month_start
                    ).distinct().count()

                    # Inactive users (active users with no sessions in last 30 days)
                    # Get list of user IDs who have sessions in the last 30 days
                    active_user_ids = [
                        row[0] for row in session.query(UserSession.user_id).filter(
                            UserSession.created_at >= month_start
                        ).distinct().all()
                    ]

                    # Count active users not in the active_user_ids list
                    if active_user_ids:
                        inactive_30_days = session.query(User).filter(
                            User.tenant_id == tenant_id,
                            User.active == True,
                            ~User.id.in_(active_user_ids)
                        ).count()
                    else:
                        # If no sessions exist, all active users are inactive
                        inactive_30_days = active_users

                else:
                    logger.info("No user sessions found - using default values for time-based metrics")
                    # If no sessions exist, all active users are considered inactive
                    inactive_30_days = active_users

            except Exception as e:
                logger.warning(f"Error calculating time-based user metrics: {e}")
                # Use safe defaults
                today_active = 0
                week_active = 0
                month_active = 0
                inactive_30_days = active_users  # All active users are inactive if we can't calculate

            # Get comprehensive table counts for this client (matching ETL service)
            table_counts = {}
            total_records = 0

            # Define all table models with tenant_id filtering
            table_models = {
                "users_sessions": UserSession,
                "users_permissions": UserPermission,
                "tenants": Tenant,
                "integrations": Integration,
                "projects": Project,
                "work_items": WorkItem,
                "changelogs": Changelog,
                "repositories": Repository,
                "prs": Pr,
                "prs_commits": PrCommit,
                "prs_reviews": PrReview,
                "prs_comments": PrComment,
                "work_items_prs_links": WorkItemPrLink,
                "wits": Wit,
                "statuses": Status,
                "statuses_mappings": StatusMapping,
                "workflows": Workflow,
                "wits_mappings": WitMapping,
                "wits_hierarchies": WitHierarchy,
                "projects_wits": ProjectWits,
                "projects_statuses": ProjectsStatuses,
                "etl_jobs": JobSchedule,
                "system_settings": SystemSettings,
                "migration_history": MigrationHistory
            }

            # ✅ SECURITY: Count records filtered by tenant_id
            for table_name, model in table_models.items():
                try:
                    # Handle different table types
                    if table_name in ['migration_history']:
                        # Global tables - count all records
                        count = session.query(func.count(model.id)).scalar() or 0
                    elif table_name == 'tenants':
                        # Tenants table - count all tenants (no tenant_id filtering)
                        count = session.query(func.count(model.id)).scalar() or 0
                    elif table_name in ['users_sessions', 'users_permissions']:
                        # User-related tables - filter by user's tenant_id through user relationship
                        if table_name == 'users_sessions':
                            count = session.query(func.count(model.id)).join(
                                User, model.user_id == User.id
                            ).filter(User.tenant_id == tenant_id).scalar() or 0
                        else:  # users_permissions
                            count = session.query(func.count(model.id)).join(
                                User, model.user_id == User.id
                            ).filter(User.tenant_id == tenant_id).scalar() or 0
                    else:
                        # Standard client-specific tables
                        if hasattr(model, 'tenant_id'):
                            # Regular tables with tenant_id and id column
                            count = session.query(func.count(model.id)).filter(model.tenant_id == tenant_id).scalar() or 0
                        else:
                            # Junction tables without tenant_id (composite primary keys, no 'id' column)
                            if table_name in ['projects_wits', 'projects_statuses']:
                                count = session.query(model).count() or 0
                            else:
                                # Fallback for other tables without tenant_id
                                count = session.query(func.count(model.id)).scalar() or 0

                    table_counts[table_name] = count
                    total_records += count

                except Exception as e:
                    logger.warning(f"Could not count records for table {table_name}: {e}")
                    table_counts[table_name] = 0

            # Add users to total records
            total_records += total_users

            # Get database size in MB
            database_size_mb = 0.0
            database_size_formatted = "N/A"
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
                    database_size_formatted = size_result.size

            except Exception as e:
                logger.warning(f"Could not get database size: {e}")

            # Include users table in table counts
            table_counts['users'] = total_users

            # Count ALL tables (not just active ones)
            total_tables = len(table_counts)

            # Calculate monthly growth percentage
            monthly_growth = 0.0
            try:
                from datetime import datetime, timedelta
                from sqlalchemy import and_
                from app.core.utils import DateTimeHelper

                # Get current month and last month date ranges in configured timezone
                now = DateTimeHelper.now_default()
                current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

                # Count records created this month vs last month for main data tables
                current_month_records = 0
                last_month_records = 0

                # Focus on main data tables that have created_at fields
                growth_tables = {
                    'work_items': WorkItem,
                    'prs': Pr,
                    'repositories': Repository,
                    'changelogs': Changelog,
                    'prs_comments': PrComment,
                    'prs_commits': PrCommit,
                    'prs_reviews': PrReview,
                    'work_items_prs_links': WorkItemPrLink
                }

                for table_name, model in growth_tables.items():
                    if hasattr(model, 'created_at') and hasattr(model, 'tenant_id'):
                        # Current month
                        current_count = session.query(func.count(model.id)).filter(
                            and_(
                                model.tenant_id == tenant_id,
                                model.created_at >= current_month_start
                            )
                        ).scalar() or 0
                        current_month_records += current_count

                        # Last month
                        last_count = session.query(func.count(model.id)).filter(
                            and_(
                                model.tenant_id == tenant_id,
                                model.created_at >= last_month_start,
                                model.created_at < current_month_start
                            )
                        ).scalar() or 0
                        last_month_records += last_count

                # Calculate growth percentage
                if last_month_records > 0:
                    monthly_growth = ((current_month_records - last_month_records) / last_month_records) * 100
                elif current_month_records > 0:
                    monthly_growth = 100.0  # 100% growth if we had 0 last month but have records this month

            except Exception as e:
                logger.warning(f"Could not calculate monthly growth: {e}")
                monthly_growth = None

            # Database stats with detailed information
            database_stats = DatabaseStats(
                database_size=database_size_formatted,
                table_count=total_tables,
                total_records=total_records,
                monthly_growth_percentage=monthly_growth
            )

            user_stats = UserStats(
                total_users=total_users,
                active_users=active_users,
                logged_users=logged_users,
                admin_users=admin_users,
                today_active=today_active,
                week_active=week_active,
                month_active=month_active,
                inactive_30_days=inactive_30_days
            )

            # Categorize tables for better presentation (matching ETL service grouping)
            table_categories = {
                "Core Data": {
                    "users": total_users,
                    "users_sessions": table_counts.get('users_sessions', 0),
                    "users_permissions": table_counts.get('users_permissions', 0),
                    "clients": table_counts.get('clients', 0),
                    "integrations": table_counts.get('integrations', 0),
                    "projects": table_counts.get('projects', 0)
                },
                "WorkItems & Workflow": {
                    "work_items": table_counts.get('work_items', 0),
                    "changelogs": table_counts.get('changelogs', 0),
                    "wits": table_counts.get('wits', 0),
                    "statuses": table_counts.get('statuses', 0),
                    "statuses_mappings": table_counts.get('statuses_mappings', 0),
                    "workflows": table_counts.get('workflows', 0),
                    "issuetype_mappings": table_counts.get('issuetype_mappings', 0),
                    "issuetype_hierarchies": table_counts.get('issuetype_hierarchies', 0),
                    "projects_issuetypes": table_counts.get('projects_issuetypes', 0),
                    "projects_statuses": table_counts.get('projects_statuses', 0)
                },
                "Development Data": {
                    "repositories": table_counts.get('repositories', 0),
                    "pull_requests": table_counts.get('pull_requests', 0),
                    "pull_request_commits": table_counts.get('pull_request_commits', 0),
                    "pull_request_reviews": table_counts.get('pull_request_reviews', 0),
                    "pull_request_comments": table_counts.get('pull_request_comments', 0)
                },
                "Linking & Mapping": {
                    "jira_pull_request_links": table_counts.get('jira_pull_request_links', 0)
                },
                "System": {
                    "etl_jobs": table_counts.get('etl_jobs', 0),
                    "system_settings": table_counts.get('system_settings', 0),
                    "migration_history": table_counts.get('migration_history', 0)
                }
            }

            # Get real performance metrics
            from app.core.database_router import get_database_router
            db_router = get_database_router()
            pool_stats = db_router.get_connection_pool_stats()

            # Calculate performance metrics
            primary_pool = pool_stats['primary']
            performance_stats = PerformanceStats(
                connection_pool_utilization=round(primary_pool['utilization'] * 100, 1),
                active_connections=primary_pool['checked_out'],
                total_connections=primary_pool['size'] + primary_pool['overflow'],
                avg_response_time_ms=None,  # Would need query timing implementation
                database_health="Healthy" if primary_pool['utilization'] < 0.8 else "High Load"
            )

            return SystemStatsResponse(
                database=database_stats,
                users=user_stats,
                performance=performance_stats,
                tables=table_counts,
                table_categories=table_categories,
                database_size_mb=database_size_mb
            )

    except Exception as e:
        logger.error(f"Error fetching system stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch system statistics"
        )


# ============================================================================
# SESSION MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/auth/invalidate-session")
async def invalidate_session_endpoint(request: Request):
    """Invalidate a session using JWT token - for centralized auth system"""
    logger.info("🔄 Backend Service: invalidate-session endpoint called")

    try:
        # Get the Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("❌ No valid Authorization header found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No valid authorization token provided"
            )

        # Extract the token
        token = auth_header.split(" ")[1]
        logger.info(f"🔍 Extracted token: {token[:20]}...")

        # Get auth service and invalidate session
        auth_service = get_auth_service()
        result = await auth_service.invalidate_session_by_token(token)

        if result:
            logger.info("✅ Session invalidated successfully")
            return {"message": "Session invalidated successfully", "success": True}
        else:
            logger.warning("⚠️ Session not found or already invalidated")
            return {"message": "Session not found or already invalidated", "success": False}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error invalidating session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate session"
        )


@router.get("/current-session")
async def get_current_session(request: Request):
    """Get current session information for the authenticated user"""

    try:
        # Get the Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No valid authorization token provided"
            )

        # Extract the token
        token = auth_header.split(" ")[1]

        # Get auth service and validate token
        auth_service = get_auth_service()
        user_data = await auth_service.validate_token(token)

        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )

        # Get session information
        database = get_database()
        with database.get_read_session_context() as session:
            # Prefer matching by token hash for accuracy
            token_hash = auth_service._hash_token(token)
            user_session = session.query(UserSession).filter(
                UserSession.token_hash == token_hash,
                UserSession.active == True
            ).first()

            if not user_session:
                # Fallback: by user id
                user_session = session.query(UserSession).filter(
                    UserSession.user_id == user_data["user_id"],
                    UserSession.active == True
                ).first()

            if not user_session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found"
                )

            return {
                "session_id": user_session.id,
                "user_id": user_session.user_id,
                "token_hash": user_session.token_hash,
                "created_at": user_session.created_at.isoformat() if user_session.created_at else None,
                "last_activity_at": user_session.last_updated_at.isoformat() if user_session.last_updated_at else None,
                "ip_address": user_session.ip_address,
                "user_agent": user_session.user_agent
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session information"
        )


@router.get("/active-sessions", response_model=List[ActiveSessionResponse])
async def get_active_sessions(
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get all active sessions for the current client"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # ✅ SECURITY: Filter by tenant_id through user relationship
            active_sessions = session.query(UserSession, User).join(
                User, UserSession.user_id == User.id
            ).filter(
                User.tenant_id == user.tenant_id,
                UserSession.active == True
            ).all()

            # Determine current session's token hash from request cookie/header
            from app.auth.auth_service import get_auth_service
            auth_service = get_auth_service()
            token_hash = None
            try:
                auth_header = user.request.headers.get("Authorization") if hasattr(user, 'request') else None
            except Exception:
                auth_header = None
            # Fallback: cannot access request here; current-session endpoint exists for the UI. We'll mark current via token cookie on the UI.

            return [
                ActiveSessionResponse(
                    id=user_session.id,
                    user_id=user_session.user_id,
                    user_email=user_obj.email,
                    created_at=user_session.created_at.isoformat() if user_session.created_at else "",
                    last_activity_at=user_session.last_updated_at.isoformat() if user_session.last_updated_at else "",
                    ip_address=user_session.ip_address,
                    user_agent=user_session.user_agent,
                    token_hash=user_session.token_hash,
                    is_current=False
                )
                for user_session, user_obj in active_sessions
            ]

    except Exception as e:
        logger.error(f"Error fetching active sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch active sessions"
        )


@router.post("/terminate-all-sessions")
async def terminate_all_sessions(
    user: User = Depends(require_permission("admin_panel", "execute"))
):
    """Terminate all active sessions for the current client"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper
            from app.core.redis_session_manager import get_redis_session_manager

            # ✅ SECURITY: Get session IDs for current client only (using join for filtering)
            session_ids_to_terminate = session.query(UserSession.id).join(
                User, UserSession.user_id == User.id
            ).filter(
                User.tenant_id == user.tenant_id,
                UserSession.active == True
            ).all()

            # Extract the IDs from the result tuples
            session_ids = [session_id[0] for session_id in session_ids_to_terminate]
            terminated_count = len(session_ids)

            # Get all user IDs for the current client for Redis cleanup
            client_user_ids = session.query(User.id).filter(
                User.tenant_id == user.tenant_id
            ).all()
            user_ids_list = [user_id[0] for user_id in client_user_ids]

            # ✅ FIX: Update sessions without join to avoid SQLAlchemy error
            if session_ids:
                session.query(UserSession).filter(
                    UserSession.id.in_(session_ids)
                ).update({
                    UserSession.active: False,
                    UserSession.last_updated_at: DateTimeHelper.now_utc()
                }, synchronize_session=False)

            session.commit()

            # Also clear Redis sessions for all users in the client
            redis_manager = get_redis_session_manager()
            if redis_manager.is_available():
                for user_id in user_ids_list:
                    try:
                        await redis_manager.invalidate_all_user_sessions(user_id)
                        logger.debug(f"Cleared Redis sessions for user {user_id}")
                    except Exception as e:
                        logger.warning(f"Failed to clear Redis sessions for user {user_id}: {e}")

            logger.info(f"Admin {user.email} terminated {terminated_count} active sessions (including Redis cleanup)")

            return {
                "message": f"Terminated {terminated_count} active sessions",
                "terminated_count": terminated_count
            }

    except Exception as e:
        logger.error(f"Error terminating all sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to terminate sessions"
        )


@router.post("/terminate-session/{session_id}")
async def terminate_user_session(
    session_id: int,
    user: User = Depends(require_permission("admin_panel", "execute"))
):
    """Terminate a specific user session"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper
            from app.core.redis_session_manager import get_redis_session_manager

            # Find the session and verify it belongs to the same client
            user_session = session.query(UserSession).join(
                User, UserSession.user_id == User.id
            ).filter(
                UserSession.id == session_id,
                User.tenant_id == user.tenant_id,
                UserSession.active == True
            ).first()

            if not user_session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found or already terminated"
                )

            # Terminate the session in DB
            user_session.active = False
            user_session.last_updated_at = DateTimeHelper.now_utc()
            session.commit()

            # Get token hash for cleanup operations
            token_hash = user_session.token_hash

            # Also invalidate Redis session for immediate logout
            try:
                auth_service = get_auth_service()
                redis_mgr = get_redis_session_manager()
                if redis_mgr.is_available():
                    await redis_mgr.invalidate_session(token_hash)
            except Exception as e:
                logger.warning(f"Failed to invalidate Redis session for session {session_id}: {e}")

            # Notify ETL to invalidate its token cache immediately (single-instance ETL)
            try:
                from app.core.config import get_settings
                settings = get_settings()
                import httpx
                etl_url = settings.ETL_SERVICE_URL.rstrip('/') + '/api/v1/internal/auth/invalidate-token'
                headers = {
                    'X-Internal-Auth': settings.ETL_INTERNAL_SECRET,
                    'Content-Type': 'application/json'
                }
                payload = { 'token_hash': token_hash, 'tenant_id': user.tenant_id }
                async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
                    resp = await client.post(etl_url, headers=headers, json=payload)
                    if resp.status_code != 200:
                        logger.warning(f"ETL invalidate-token returned {resp.status_code}: {resp.text}")
                    else:
                        logger.info("ETL token cache invalidated for terminated session")
            except Exception as e:
                logger.warning(f"Failed to call ETL invalidate-token endpoint: {e}")

            logger.info(f"Admin {user.email} terminated session {session_id}")

            return {"message": "Session terminated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error terminating session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to terminate session"
        )


# ============================================================================
# PERMISSION MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/permissions/matrix", response_model=PermissionMatrixResponse)
async def get_permission_matrix(
    admin_user: User = Depends(require_permission("admin_panel", "read"))
):
    """Proxy permission matrix from Auth Service (source of truth)."""
    try:
        import httpx
        from app.core.config import get_settings
        settings = get_settings()
        auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{auth_service_url}/api/v1/permissions/matrix", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                return PermissionMatrixResponse(**data)
            raise HTTPException(status_code=resp.status_code, detail="Failed to fetch permission matrix")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching permission matrix: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch permission matrix"
        )


# ============================================================================
# THEME/COLOR SETTINGS ENDPOINTS
# ============================================================================












@router.post("/color-schema/mode")
async def update_color_schema_mode(
    request: ColorSchemaModeRequest,
    user: User = Depends(require_permission("settings", "admin"))
):
    """Update color schema mode (default or custom)"""
    try:
        # Validate mode value
        if request.mode not in ['default', 'custom']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mode must be 'default' or 'custom'"
            )

        database = get_database()
        with database.get_write_session_context() as session:
            # ✅ SECURITY: Update color schema mode in clients table
            client = session.query(Tenant).filter(
                Tenant.id == user.tenant_id
            ).first()

            if not client:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tenant not found"
                )

            # Update client's color schema mode
            client.color_schema_mode = request.mode
            client.last_updated_at = func.now()

            session.commit()

            # Note: Color schema changes are now broadcasted via browser events
            # from frontend-app ThemeContext to frontend-etl ThemeContext
            # No need for backend-to-ETL service notifications

            return {
                "success": True,
                "message": f"Color schema mode updated to '{request.mode}'",
                "mode": request.mode
            }

    except Exception as e:
        logger.error(f"Error updating color schema mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update color schema mode"
        )








# ============================================================================
# UNIFIED COLOR SCHEMA ENDPOINTS (New Architecture)
# ============================================================================

@router.get("/color-schema/unified")
async def get_unified_color_schema(
    mode: Optional[str] = None,
    user: User = Depends(require_authentication)
):
    """Get unified color schema with all theme modes and accessibility levels"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # Get client's current color schema mode or use provided mode
            if mode and mode in ['default', 'custom']:
                color_mode = mode
            else:
                client = session.query(Tenant).filter(
                    Tenant.id == user.tenant_id
                ).first()
                color_mode = client.color_schema_mode if client else "default"

            # Get ALL color data for this client (all modes, themes, accessibility levels)
            # This provides complete color data for client-side filtering and prevents flashing
            color_rows = session.query(TenantColors).filter(
                TenantColors.tenant_id == user.tenant_id,
                TenantColors.active == True
            ).order_by(
                TenantColors.color_schema_mode,
                TenantColors.theme_mode,
                TenantColors.accessibility_level
            ).all()

            if not color_rows:
                logger.error(f"CRITICAL: No color rows found for client {user.tenant_id} - database integrity issue!")

            # Convert to array format expected by frontend
            color_data = []
            for row in color_rows:
                color_data.append({
                    'color_schema_mode': row.color_schema_mode,  # CRITICAL FIX: Include mode in each object
                    'theme_mode': row.theme_mode,
                    'accessibility_level': row.accessibility_level,
                    'color1': row.color1,
                    'color2': row.color2,
                    'color3': row.color3,
                    'color4': row.color4,
                    'color5': row.color5,
                    'on_color1': row.on_color1,
                    'on_color2': row.on_color2,
                    'on_color3': row.on_color3,
                    'on_color4': row.on_color4,
                    'on_color5': row.on_color5,
                    'on_gradient_1_2': row.on_gradient_1_2,
                    'on_gradient_2_3': row.on_gradient_2_3,
                    'on_gradient_3_4': row.on_gradient_3_4,
                    'on_gradient_4_5': row.on_gradient_4_5,
                    'on_gradient_5_1': row.on_gradient_5_1
                })

            return {
                "success": True,
                "color_schema_mode": color_mode,
                "color_data": color_data
            }

    except Exception as e:
        logger.error(f"Error getting unified color schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get unified color schema"
        )


@router.post("/color-schema/unified")
async def update_unified_color_schema(
    request: UnifiedColorSchemaRequest,
    user: User = Depends(require_permission("settings", "admin"))
):
    """Update unified color schema with light and dark colors"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Update colors in the unified table structure
            # This will update multiple rows: light/dark × regular/AA/AAA

            for theme_mode in ['light', 'dark']:
                colors = request.light_colors if theme_mode == 'light' else request.dark_colors

                for accessibility_level in ['regular', 'AA', 'AAA']:
                    # Get or create the color settings row
                    color_row = session.query(TenantColors).filter(
                        TenantColors.tenant_id == user.tenant_id,
                        TenantColors.color_schema_mode == 'custom',
                        TenantColors.theme_mode == theme_mode,
                        TenantColors.accessibility_level == accessibility_level
                    ).first()

                    if not color_row:
                        color_row = TenantColors(
                            tenant_id=user.tenant_id,
                            color_schema_mode='custom',
                            theme_mode=theme_mode,
                            accessibility_level=accessibility_level
                        )
                        session.add(color_row)

                    # Apply accessibility enhancement if needed
                    if accessibility_level != 'regular':
                        # Apply accessibility color calculations
                        enhanced_colors = apply_accessibility_enhancement(colors, accessibility_level)
                    else:
                        enhanced_colors = colors

                    # Update base colors
                    color_row.color1 = enhanced_colors.get('color1')
                    color_row.color2 = enhanced_colors.get('color2')
                    color_row.color3 = enhanced_colors.get('color3')
                    color_row.color4 = enhanced_colors.get('color4')
                    color_row.color5 = enhanced_colors.get('color5')

                    # Calculate and update variants (on-colors, gradients)
                    # This would use the same calculation logic as the migration
                    calculated_variants = calculate_color_variants(enhanced_colors)

                    color_row.on_color1 = calculated_variants.get('on_color1')
                    color_row.on_color2 = calculated_variants.get('on_color2')
                    color_row.on_color3 = calculated_variants.get('on_color3')
                    color_row.on_color4 = calculated_variants.get('on_color4')
                    color_row.on_color5 = calculated_variants.get('on_color5')

                    color_row.on_gradient_1_2 = calculated_variants.get('on_gradient_1_2')
                    color_row.on_gradient_2_3 = calculated_variants.get('on_gradient_2_3')
                    color_row.on_gradient_3_4 = calculated_variants.get('on_gradient_3_4')
                    color_row.on_gradient_4_5 = calculated_variants.get('on_gradient_4_5')
                    color_row.on_gradient_5_1 = calculated_variants.get('on_gradient_5_1')

                    color_row.last_updated_at = func.now()

            session.commit()

            logger.info(f"User {user.email} updated unified color schema")

            # Broadcast color schema change to all tenant users' WebSocket connections
            try:
                from app.api.websocket_routes import get_session_websocket_manager
                session_ws_manager = get_session_websocket_manager()

                # Get all users in this tenant to broadcast to
                tenant_users = session.query(User).filter(User.tenant_id == user.tenant_id).all()

                # Prepare color data for broadcast
                colors_data = {
                    'light': request.light_colors,
                    'dark': request.dark_colors
                }

                # Broadcast to all tenant users
                for tenant_user in tenant_users:
                    await session_ws_manager.broadcast_color_schema_change(tenant_user.id, colors_data)

                logger.info(f"✅ Color schema change broadcast sent to {len(tenant_users)} users in tenant {user.tenant_id}")
            except Exception as e:
                logger.warning(f"Failed to broadcast color schema change via WebSocket: {e}")

            return {
                "success": True,
                "message": "Unified color schema updated successfully"
            }

    except Exception as e:
        logger.error(f"Error updating unified color schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update unified color schema"
        )


# Helper functions for unified color processing
def apply_accessibility_enhancement(colors: Dict[str, str], level: str) -> Dict[str, str]:
    """Apply accessibility enhancement to colors based on WCAG level"""
    # Placeholder implementation - would use the same logic as migration
    enhanced = colors.copy()
    if level == 'AAA':
        # Apply stronger accessibility enhancements
        for key, color in enhanced.items():
            enhanced[key] = darken_color_for_accessibility(color, 0.1)
    return enhanced

def calculate_color_variants(colors: Dict[str, str]) -> Dict[str, str]:
    """Calculate on-colors and gradients using proper calculation service"""
    from app.services.color_calculation_service import ColorCalculationService

    try:
        calculation_service = ColorCalculationService()
        variants = calculation_service.calculate_all_variants(colors)

        # Convert ColorVariants object to dictionary format expected by the API
        result = {}
        result.update(variants.on_colors)
        result.update(variants.gradient_colors)

        return result

    except Exception as e:
        logger.error(f"Error calculating color variants: {e}")
        # Fallback to safe defaults if calculation fails
        return {
            'on_color1': '#FFFFFF',
            'on_color2': '#FFFFFF',
            'on_color3': '#FFFFFF',
            'on_color4': '#FFFFFF',
            'on_color5': '#FFFFFF',
            'on_gradient_1_2': '#FFFFFF',
            'on_gradient_2_3': '#FFFFFF',
            'on_gradient_3_4': '#FFFFFF',
            'on_gradient_4_5': '#FFFFFF',
            'on_gradient_5_1': '#FFFFFF'
        }

def darken_color_for_accessibility(hex_color: str, factor: float) -> str:
    """Darken a color for accessibility - same logic as migration"""
    # Placeholder implementation
    return hex_color


# ============================================================================
# CLIENT MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/tenants", response_model=List[TenantResponse])
async def get_all_tenants(
    skip: int = 0,
    limit: int = 100,
    user: User = Depends(require_authentication)
):
    """Get current user's client information"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # ✅ SECURITY: Only show the current user's tenant
            tenants = session.query(Tenant).filter(
                Tenant.id == user.tenant_id
            ).offset(skip).limit(limit).all()

            # Auto-fix any assets_folder case issues
            for tenant in tenants:
                if tenant.assets_folder and tenant.assets_folder != tenant.assets_folder.lower():
                    tenant.assets_folder = tenant.assets_folder.lower()
                    session.commit()
                    logger.info(f"Auto-corrected assets_folder case for tenant {tenant.name}")

            return [
                TenantResponse(
                    id=tenant.id,
                    name=tenant.name,
                    website=tenant.website,
                    active=tenant.active,
                    assets_folder=tenant.assets_folder,
                    logo_filename=tenant.logo_filename
                )
                for tenant in tenants
            ]
    except Exception as e:
        logger.error(f"Error fetching tenants: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch clients"
        )


@router.post("/tenants", response_model=TenantResponse)
async def create_tenant(
    tenant_data: TenantCreateRequest,
    admin_user: User = Depends(require_permission("admin_panel", "execute"))
):
    """Create a new tenant"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Check if tenant name already exists
            existing_tenant = session.query(Tenant).filter(
                Tenant.name == tenant_data.name
            ).first()

            if existing_tenant:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tenant with this name already exists"
                )

            # Create new tenant
            new_tenant = Tenant(
                name=tenant_data.name,
                website=tenant_data.website,
                active=tenant_data.active if tenant_data.active is not None else True,
                created_at=DateTimeHelper.now_default(),
                last_updated_at=DateTimeHelper.now_default()
            )

            session.add(new_tenant)
            session.commit()

            logger.info(f"Admin {admin_user.email} created tenant {new_tenant.name}")

            return TenantResponse(
                id=new_tenant.id,
                name=new_tenant.name,
                website=new_tenant.website,
                active=new_tenant.active,
                assets_folder=new_tenant.assets_folder,
                logo_filename=new_tenant.logo_filename
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tenant"
        )


@router.put("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: int,
    tenant_data: TenantUpdateRequest,
    admin_user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Update an existing tenant"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Find the tenant to update
            tenant_to_update = session.query(Tenant).filter(
                Tenant.id == tenant_id
            ).first()

            if not tenant_to_update:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tenant not found"
                )

            # Update fields if provided
            if tenant_data.name is not None:
                # Check if name is already taken by another tenant
                existing_tenant = session.query(Tenant).filter(
                    Tenant.name == tenant_data.name,
                    Tenant.id != tenant_id
                ).first()

                if existing_tenant:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Name already taken by another tenant"
                    )
                tenant_to_update.name = tenant_data.name

            if tenant_data.website is not None:
                tenant_to_update.website = tenant_data.website

            if tenant_data.active is not None:
                tenant_to_update.active = tenant_data.active

            if tenant_data.assets_folder is not None:
                # Ensure assets_folder is always lowercase for consistency
                tenant_to_update.assets_folder = tenant_data.assets_folder.lower() if tenant_data.assets_folder else None

            if tenant_data.logo_filename is not None:
                tenant_to_update.logo_filename = tenant_data.logo_filename

            tenant_to_update.last_updated_at = DateTimeHelper.now_default()
            session.commit()

            logger.info(f"Admin {admin_user.email} updated tenant {tenant_to_update.name}")

            return TenantResponse(
                id=tenant_to_update.id,
                name=tenant_to_update.name,
                website=tenant_to_update.website,
                active=tenant_to_update.active,
                assets_folder=tenant_to_update.assets_folder,
                logo_filename=tenant_to_update.logo_filename
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tenant"
        )


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: int,
    admin_user: User = Depends(require_permission("admin_panel", "delete"))
):
    """Delete a client"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Find the client to delete
            client_to_delete = session.query(Tenant).filter(
                Tenant.id == tenant_id
            ).first()

            if not client_to_delete:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tenant not found"
                )

            # Check if there are users associated with this client
            user_count = session.query(User).filter(
                User.tenant_id == tenant_id
            ).count()

            if user_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete client: {user_count} users are associated with this client"
                )

            # Delete the client
            session.delete(client_to_delete)
            session.commit()

            logger.info(f"Admin {admin_user.email} deleted client {client_to_delete.name}")

            return {"message": f"Tenant {client_to_delete.name} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting client {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete client"
        )


@router.post("/tenants/{tenant_id}/logo")
async def upload_tenant_logo(
    tenant_id: int,
    logo: UploadFile = File(...),
    admin_user: User = Depends(require_permission("admin_panel", "execute"))
):
    """Upload a logo for a client"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper
            from pathlib import Path

            # Find the client
            client = session.query(Tenant).filter(
                Tenant.id == tenant_id
            ).first()

            if not client:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tenant not found"
                )

            # Validate file type - allow PNG, JPG, JPEG, and SVG
            allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/svg+xml"]
            if logo.content_type not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid file type. Only PNG, JPG, JPEG, and SVG files are allowed."
                )

            # Validate file size (max 5MB)
            file_content = await logo.read()
            if len(file_content) > 5 * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File size must be less than 5MB."
                )

            # Preserve original filename with proper sanitization
            import re

            # Get original filename or fallback
            original_filename = logo.filename or "logo"

            # Sanitize filename: remove/replace unsafe characters
            # Keep alphanumeric, dots, hyphens, underscores
            safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', original_filename)

            # Ensure filename doesn't start with dot or dash
            safe_filename = re.sub(r'^[.-]+', '', safe_filename)

            # Limit length to prevent filesystem issues
            if len(safe_filename) > 100:
                name_part, ext_part = safe_filename.rsplit('.', 1) if '.' in safe_filename else (safe_filename, '')
                safe_filename = name_part[:95] + ('.' + ext_part if ext_part else '')

            # Fallback if filename becomes empty after sanitization
            if not safe_filename or safe_filename == '.':
                # Determine file extension based on content type
                extension_map = {
                    "image/png": "png",
                    "image/jpeg": "jpg",
                    "image/jpg": "jpg",
                    "image/svg+xml": "svg"
                }
                file_extension = extension_map.get(logo.content_type, "png")
                safe_filename = f"logo.{file_extension}"

            client_filename = safe_filename

            # Create client-specific directories (relative to project root)
            # Path: services/backend-service/app/api/admin_routes.py -> go up 3 levels to project root
            project_root = Path(__file__).parent.parent.parent.parent.parent
            client_name_lower = client.name.lower().replace(' ', '_').replace('-', '_')
            frontend_client_dir = project_root / f"services/frontend-app/public/assets/{client_name_lower}"
            etl_client_dir = project_root / f"services/etl-service/app/static/assets/{client_name_lower}"

            frontend_client_dir.mkdir(parents=True, exist_ok=True)
            etl_client_dir.mkdir(parents=True, exist_ok=True)

            # Save file to both client directories
            frontend_logo_path = frontend_client_dir / client_filename
            etl_logo_path = etl_client_dir / client_filename

            # Write to both locations (file_content already read during validation)
            with open(frontend_logo_path, "wb") as f:
                f.write(file_content)

            with open(etl_logo_path, "wb") as f:
                f.write(file_content)

            # Update client record with assets folder and filename
            # Ensure assets_folder is always lowercase for consistency
            client.assets_folder = client_name_lower
            client.logo_filename = client_filename
            client.last_updated_at = DateTimeHelper.now_default()
            session.commit()

            logger.info(f"Admin {admin_user.email} uploaded logo for client {client.name}")

            return {
                "message": "Logo uploaded successfully",
                "assets_folder": client.assets_folder,
                "logo_filename": client.logo_filename,
                "tenant_id": tenant_id
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading client logo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload logo"
        )


# ============================================================================
# DEBUG ENDPOINTS
# ============================================================================

@router.get("/debug/config")
async def debug_config():
    """Debug endpoint to show current configuration"""
    from app.core.config import get_settings
    settings = get_settings()

    return {
        "database_url": settings.DATABASE_URL[:50] + "..." if settings.DATABASE_URL else None,
        "jwt_secret_key": "***" if settings.JWT_SECRET_KEY else None,
        "environment": getattr(settings, 'ENVIRONMENT', 'development'),
        "debug_mode": getattr(settings, 'DEBUG', False)
    }


# ============================================================================
# WORKER MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/workers/status", response_model=WorkerStatusResponse)
async def get_worker_status(
    current_user: User = Depends(require_authentication)
):
    """Get current status of ETL workers for current tenant's tier only."""
    try:
        from app.workers.worker_manager import get_worker_manager
        from app.core.database import get_database
        from app.etl.queue.queue_manager import QueueManager
        from sqlalchemy import text

        # Get current tenant's tier
        database = get_database()
        current_tenant_tier = 'free'  # default

        try:
            with database.get_read_session_context() as session:
                tenant = session.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
                if tenant:
                    current_tenant_tier = tenant.tier
        except Exception as e:
            logger.warning(f"Could not get tenant tier: {e}")

        # Get worker status from shared pool manager (filter to current tenant's tier only)
        manager = get_worker_manager()
        all_worker_status = manager.get_worker_status()

        # Filter workers to show only current tenant's tier
        filtered_workers = {}
        for worker_key, worker_info in all_worker_status.get('workers', {}).items():
            if worker_info.get('tier') == current_tenant_tier:
                filtered_workers[worker_key] = worker_info

        # Get tier-based queue statistics from RabbitMQ (only for current tenant's tier)
        queue_stats = {
            'architecture': 'tier-based',
            'current_tenant_tier': current_tenant_tier,
            'tier_queues': {}
        }

        try:
            queue_manager = QueueManager()
            queue_types = ['extraction', 'transform', 'vectorization']

            # Only get queue stats for current tenant's tier
            queue_stats['tier_queues'][current_tenant_tier] = {}
            for queue_type in queue_types:
                queue_name = queue_manager.get_tier_queue_name(current_tenant_tier, queue_type)
                try:
                    # Get message count from RabbitMQ
                    with queue_manager.get_channel() as channel:
                        method = channel.queue_declare(queue=queue_name, passive=True)
                        message_count = method.method.message_count
                        queue_stats['tier_queues'][current_tenant_tier][queue_type] = {
                            'queue_name': queue_name,
                            'message_count': message_count
                        }
                except Exception as e:
                    queue_stats['tier_queues'][current_tenant_tier][queue_type] = {
                        'queue_name': queue_name,
                        'message_count': 0,
                        'error': str(e)
                    }
        except Exception as e:
            logger.error(f"Error getting queue statistics: {e}")
            queue_stats['error'] = str(e)

        # Get raw data statistics (for current tenant only)
        raw_data_stats = {}

        try:
            with database.get_read_session_context() as session:
                query = text("""
                    SELECT
                        status,
                        type,
                        COUNT(*) as count,
                        MIN(created_at) as oldest,
                        MAX(created_at) as newest
                    FROM raw_extraction_data
                    WHERE active = true AND tenant_id = :tenant_id
                    GROUP BY status, type
                    ORDER BY status, type
                """)

                result = session.execute(query, {"tenant_id": current_user.tenant_id}).fetchall()

                for row in result:
                    key = f"{row.status}_{row.type}"
                    raw_data_stats[key] = {
                        'count': row.count,
                        'oldest': row.oldest.isoformat() if row.oldest else None,
                        'newest': row.newest.isoformat() if row.newest else None
                    }
        except Exception as e:
            raw_data_stats = {'error': str(e)}

        return WorkerStatusResponse(
            running=all_worker_status.get('running', False),
            workers=filtered_workers,  # Only current tenant's tier workers
            queue_stats=queue_stats,
            raw_data_stats=raw_data_stats
        )

    except Exception as e:
        logger.error(f"Error getting worker status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get worker status: {str(e)}"
        )


@router.post("/workers/action")
async def worker_action(
    request: WorkerActionRequest,
    current_user: User = Depends(require_authentication)
):
    """Perform action on ALL worker pools (shared architecture - affects all tenants)."""
    try:
        from app.workers.worker_manager import get_worker_manager

        manager = get_worker_manager()

        if request.action == "start":
            success = manager.start_all_workers()
            message = "All worker pools started" if success else "Failed to start worker pools"
        elif request.action == "stop":
            success = manager.stop_all_workers()
            message = "All worker pools stopped" if success else "Failed to stop worker pools"
        elif request.action == "restart":
            success = manager.restart_all_workers()
            message = "All worker pools restarted" if success else "Failed to restart worker pools"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {request.action}. Must be 'start', 'stop', or 'restart'"
            )

        logger.info(f"Worker pool action '{request.action}' performed by user {current_user.email}")

        return {
            "success": success,
            "message": message,
            "action": request.action,
            "note": "Shared worker pools affect all tenants"
        }

    except Exception as e:
        logger.error(f"Error controlling workers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to control workers: {str(e)}")


@router.get("/workers/config", response_model=WorkerPoolConfigResponse)
async def get_worker_pool_config(
    current_user: User = Depends(require_authentication)
):
    """Get worker pool configuration (tier-based shared pools)."""
    try:
        from app.core.database import get_database
        from app.workers.worker_manager import get_worker_manager
        from sqlalchemy import text

        tenant_id = current_user.tenant_id
        database = get_database()
        manager = get_worker_manager()

        # Get current tenant's tier
        with database.get_read_session_context() as session:
            query = text("SELECT tier FROM tenants WHERE id = :tenant_id")
            result = session.execute(query, {'tenant_id': tenant_id})
            row = result.fetchone()
            current_tier = row[0] if row else 'free'

        # Get tier configurations
        tier_configs = manager.get_tier_config()
        current_allocation = tier_configs.get(current_tier, tier_configs['free'])

        return WorkerPoolConfigResponse(
            tier_configs=tier_configs,
            current_tenant_tier=current_tier,
            current_tenant_allocation=current_allocation
        )

    except Exception as e:
        logger.error(f"Error getting worker pool config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get worker pool config: {str(e)}")


@router.post("/workers/config/tier", response_model=TenantTierResponse)
async def set_tenant_tier(
    request: TenantTierRequest,
    current_user: User = Depends(require_authentication)
):
    """Set tenant tier (free, basic, premium, enterprise) - requires worker pool restart."""
    try:
        from app.core.database import get_database
        from app.workers.worker_manager import get_worker_manager
        from sqlalchemy import text

        tenant_id = current_user.tenant_id
        new_tier = request.tier.lower()

        # Validate tier
        valid_tiers = ['free', 'basic', 'premium', 'enterprise']
        if new_tier not in valid_tiers:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tier: {new_tier}. Must be one of: {', '.join(valid_tiers)}"
            )

        database = get_database()
        manager = get_worker_manager()

        # Update tenant tier
        with database.get_write_session_context() as session:
            update_query = text("""
                UPDATE tenants
                SET tier = :tier, last_updated_at = NOW()
                WHERE id = :tenant_id
            """)
            session.execute(update_query, {'tenant_id': tenant_id, 'tier': new_tier})
            session.commit()

        # Get worker allocation for new tier
        tier_configs = manager.get_tier_config()
        worker_allocation = tier_configs.get(new_tier, tier_configs['free'])

        logger.info(f"Tenant {tenant_id} tier changed to '{new_tier}' by user {current_user.email}")

        return TenantTierResponse(
            tenant_id=tenant_id,
            tier=new_tier,
            worker_allocation=worker_allocation
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting tenant tier: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set tenant tier: {str(e)}")


# Note: Tenant-specific worker control removed - using shared worker pools
# All tenants in the same tier share worker pools
# To change tenant's worker allocation, change their tier using /workers/config/tier


@router.get("/debug/user-info")
async def get_debug_user_info(
    current_user: User = Depends(require_authentication)
):
    """Debug endpoint to check current user's tenant assignment and worker status"""
    try:
        from app.workers.worker_manager import get_worker_manager
        from app.core.database import get_database
        from app.models.unified_models import Tenant
        from sqlalchemy import text

        # Get user info
        user_info = {
            "user_id": current_user.user_id,
            "email": current_user.email,
            "tenant_id": current_user.tenant_id,
            "role": current_user.role,
            "is_admin": current_user.is_admin
        }

        # Get tenant info including tier
        database = get_database()
        with database.get_read_session_context() as session:
            tenant = session.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
            tenant_info = {
                "id": tenant.id if tenant else None,
                "name": tenant.name if tenant else None,
                "tier": tenant.tier if tenant else None,
                "active": tenant.active if tenant else None
            } if tenant else {"error": "Tenant not found"}

        # Get worker pool status
        manager = get_worker_manager()
        worker_status = manager.get_worker_status()

        # Get tenants by tier
        tenants_by_tier = manager._get_tenants_by_tier()

        return {
            "user": user_info,
            "tenant": tenant_info,
            "worker_status": worker_status,
            "tenants_by_tier": {tier: len(ids) for tier, ids in tenants_by_tier.items()},
            "debug_info": {
                "workers_running": manager.running,
                "total_workers": len(manager.worker_threads),
                "tier_pools": list(manager.tier_workers.keys())
            }
        }

    except Exception as e:
        logger.error(f"Error getting debug user info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get debug info: {str(e)}")


@router.get("/workers/logs", response_model=WorkerLogsResponse)
async def get_worker_logs(
    lines: int = 50,
    current_user: User = Depends(require_authentication)
):
    """Get recent worker logs."""
    try:
        import os
        from pathlib import Path

        # Look for log files
        log_paths = [
            Path("logs/workers.log"),
            Path("logs/backend_service_system.log"),
            Path("../logs/workers.log")
        ]

        logs = []
        total_lines = 0

        for log_path in log_paths:
            if log_path.exists():
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        file_lines = f.readlines()
                        total_lines += len(file_lines)

                        # Get last N lines
                        recent_lines = file_lines[-lines:] if len(file_lines) > lines else file_lines
                        logs.extend([line.strip() for line in recent_lines])
                        break  # Use first available log file
                except Exception as e:
                    logger.warning(f"Could not read log file {log_path}: {e}")
                    continue

        if not logs:
            logs = ["No log files found or accessible"]

        return WorkerLogsResponse(
            logs=logs[-lines:],  # Ensure we don't exceed requested lines
            total_lines=total_lines
        )

    except Exception as e:
        logger.error(f"Error getting worker logs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get worker logs: {str(e)}"
        )
