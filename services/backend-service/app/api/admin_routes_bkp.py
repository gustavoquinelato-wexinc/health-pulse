"""
Admin Panel API Routes

Provides administrative functionality for user management, role assignment,
and system configuration. Only accessible to admin users.
"""

from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from pydantic import BaseModel, EmailStr

from app.core.database import get_database
from app.models.unified_models import (
    User, UserPermission, UserSession, Integration, Project, WorkItem, Tenant, Changelog,
    Repository, Pr, PrCommit, PrReview, PrComment,
    WitPrLinks, Wit, Status, JobSchedule, SystemSettings,
    StatusMapping, Workflow, WitMapping, WitHierarchy, MigrationHistory,
    ProjectWits, ProjectsStatuses
)
from app.auth.auth_middleware import require_permission
from app.auth.auth_service import get_auth_service
from app.auth.permissions import Role, Resource, Action, get_user_permissions, DEFAULT_ROLE_PERMISSIONS
from app.core.logging_config import get_logger
import httpx
import asyncio
from app.core.config import get_settings

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
settings = get_settings()


# 🚀 ETL Service Notification Functions
async def notify_etl_color_schema_change(tenant_id: int, colors: dict):
    """Notify ETL service of color schema changes"""
    try:
        # Get ETL service URL (assuming it runs on port 8000)
        etl_url = f"http://localhost:8000/api/v1/internal/color-schema-changed"

        async with httpx.AsyncTenant(timeout=5.0) as client:
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
        # Get ETL service URL
        etl_url = f"http://localhost:8000/api/v1/internal/color-schema-mode-changed"

        async with httpx.AsyncTenant(timeout=5.0) as client:
            response = await client.post(etl_url, json={
                "tenant_id": tenant_id,
                "mode": mode,
                "event_type": "mode_update"
            })

            if response.status_code == 200:
                logger.info(f"✅ ETL service notified of color schema mode change for client {tenant_id}")
            else:
                logger.warning(f"⚠️ ETL service notification failed: {response.status_code}")

    except Exception as e:
        logger.warning(f"⚠️ Could not notify ETL service of mode change: {e}")
        # Don't fail the main operation if ETL notification fails


# Pydantic models for API
class UserResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    role: str
    is_admin: bool
    active: bool
    last_login_at: Optional[str]

    class Config:
        from_attributes = True

class UserCreateRequest(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str = "user"
    is_admin: bool = False
    password: Optional[str] = None

class UserUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    is_admin: Optional[bool] = None
    active: Optional[bool] = None

class UserStats(BaseModel):
    total_users: int
    active_users: int
    logged_users: int
    admin_users: int

class DatabaseStats(BaseModel):
    database_size: str
    table_count: int
    total_records: int

class SystemStatsResponse(BaseModel):
    database: DatabaseStats
    users: UserStats
    tables: dict

class TenantResponse(BaseModel):
    id: int
    name: str
    website: Optional[str]
    logo_filename: Optional[str]
    active: bool
    created_at: str
    last_updated_at: str

class TenantCreateRequest(BaseModel):
    name: str
    website: Optional[str] = None
    active: bool = True

class TenantUpdateRequest(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    active: Optional[bool] = None

class PermissionMatrixResponse(BaseModel):
    roles: List[str]
    resources: List[str]
    actions: List[str]
    matrix: Dict[str, Dict[str, List[str]]]  # role -> resource -> actions


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
                    is_admin=u.is_admin,
                    active=u.active,
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
            # Check if user already exists
            existing_user = session.query(User).filter(User.email == user_data.email).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User with this email already exists"
                )

            # Validate role
            if user_data.role not in [r.value for r in Role]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role. Must be one of: {[r.value for r in Role]}"
                )

            # Create new user
            new_user = User(
                email=user_data.email,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                role=user_data.role,
                is_admin=user_data.is_admin,
                tenant_id=admin_user.tenant_id,
                active=True
            )

            # Set password if provided (for local auth)
            if user_data.password:
                from app.auth.auth_service import get_auth_service
                auth_service = get_auth_service()
                new_user.password_hash = auth_service._hash_password(user_data.password)
                new_user.auth_provider = 'local'

            session.add(new_user)
            session.commit()
            session.refresh(new_user)

            logger.info(f"Admin {admin_user.email} created user {new_user.email} with role {new_user.role}")

            return UserResponse(
                id=new_user.id,
                email=new_user.email,
                first_name=new_user.first_name,
                last_name=new_user.last_name,
                role=new_user.role,
                is_admin=new_user.is_admin,
                active=new_user.active,
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
    admin_user: User = Depends(require_permission("users", "execute"))
):
    """Update an existing user"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
            user = session.query(User).filter(
                User.id == user_id,
                User.tenant_id == admin_user.tenant_id
            ).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Update fields if provided
            if user_data.first_name is not None:
                user.first_name = user_data.first_name
            if user_data.last_name is not None:
                user.last_name = user_data.last_name
            if user_data.role is not None:
                if user_data.role not in [r.value for r in Role]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid role. Must be one of: {[r.value for r in Role]}"
                    )
                user.role = user_data.role
            if user_data.is_admin is not None:
                user.is_admin = user_data.is_admin
            if user_data.active is not None:
                user.active = user_data.active

            session.commit()
            session.refresh(user)

            logger.info(f"Admin {admin_user.email} updated user {user.email}")

            return UserResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                role=user.role,
                is_admin=user.is_admin,
                active=user.active,
                last_login_at=user.last_login_at.isoformat() if user.last_login_at else None
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin_user: User = Depends(require_permission("users", "delete"))
):
    """Delete a user (hard delete - permanently removes user)"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
            user = session.query(User).filter(
                User.id == user_id,
                User.tenant_id == admin_user.tenant_id
            ).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Prevent self-deletion
            if user.id == admin_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete your own account"
                )

            # Check for dependencies (user sessions, permissions, etc.)
            from app.models.unified_models import UserSession, UserPermission

            # Count active sessions
            active_sessions = session.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.active == True
            ).count()

            # Count permissions
            user_permissions = session.query(UserPermission).filter(
                UserPermission.user_id == user_id
            ).count()

            if active_sessions > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete user: {active_sessions} active session(s) exist. Please deactivate the user instead."
                )

            # Delete user permissions first (foreign key constraint)
            session.query(UserPermission).filter(UserPermission.user_id == user_id).delete()

            # Delete inactive user sessions
            session.query(UserSession).filter(UserSession.user_id == user_id).delete()

            # Hard delete the user
            session.delete(user)
            session.commit()

            logger.info(f"Admin {admin_user.email} permanently deleted user {user.email}")

            return {"message": "User permanently deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )


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
                    role=u.role.value,
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


@router.get("/system/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    admin_user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get system statistics"""
    try:
        database = get_database()
        with database.get_analytics_session_context() as session:
            # ✅ SECURITY: User statistics filtered by tenant_id
            total_users = session.query(User).filter(User.tenant_id == admin_user.tenant_id).count()
            active_users = session.query(User).filter(
                User.tenant_id == admin_user.tenant_id,
                User.active == True
            ).count()

            # Count logged users (users with active sessions) for current client
            from app.core.utils import DateTimeHelper
            logged_users = session.query(User).join(UserSession).filter(
                User.tenant_id == admin_user.tenant_id,
                User.active == True,
                UserSession.active == True,
                UserSession.expires_at > DateTimeHelper.now_utc()
            ).distinct().count()

            # ✅ SECURITY: Admin users count filtered by tenant_id
            admin_users = session.query(User).filter(
                User.tenant_id == admin_user.tenant_id,
                User.is_admin == True,
                User.active == True
            ).count()

            # ✅ SECURITY: Role distribution filtered by tenant_id
            roles_distribution = {}
            for role in Role:
                count = session.query(User).filter(
                    User.tenant_id == admin_user.tenant_id,
                    User.role == role.value,
                    User.active == True
                ).count()
                roles_distribution[role.value] = count

            # Comprehensive database statistics - count all main tables
            database_stats = {}
            total_records = 0

            # Define all tables to count
            table_models = {
                "users": User,
                "user_sessions": UserSession,
                "user_permissions": UserPermission,
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
                "wits_prs_links": WitPrLinks,
                "wits": Wit,
                "statuses": Status,
                "status_mappings": StatusMapping,
                "workflows": Workflow,
                "wits_mappings": WitMapping,
                "wits_hierarchies": WitHierarchy,
                "projects_wits": ProjectWits,
                "projects_statuses": ProjectsStatuses,
                "job_schedules": JobSchedule,
                "system_settings": SystemSettings,
                "migration_history": MigrationHistory
            }

            # ✅ SECURITY: Count records filtered by tenant_id
            for table_name, model in table_models.items():
                try:
                    # Skip tables that don't have tenant_id (global tables)
                    if table_name in ['clients', 'migration_history']:
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
                            # For tables without tenant_id, count all (like user_sessions, user_permissions)
                            if table_name in ['projects_issuetypes', 'projects_statuses']:
                                count = session.query(model).count() or 0
                            else:
                                count = session.query(func.count(model.id)).scalar() or 0

                    database_stats[table_name] = count
                    total_records += count
                except Exception as e:
                    logger.warning(f"Could not count records for {table_name}: {e}")
                    database_stats[table_name] = 0

            # Get database size
            database_size_pretty = "Unknown"
            try:
                # Query PostgreSQL for database size
                from sqlalchemy import text
                size_result = session.execute(
                    text("SELECT pg_size_pretty(pg_database_size(current_database())) as size")
                ).fetchone()

                if size_result:
                    database_size_pretty = size_result.size

            except Exception as e:
                logger.warning(f"Could not get database size: {e}")

            return SystemStatsResponse(
                database=DatabaseStats(
                    database_size=database_size_pretty,
                    table_count=len(database_stats),
                    total_records=total_records
                ),
                users=UserStats(
                    total_users=total_users,
                    active_users=active_users,
                    logged_users=logged_users,
                    admin_users=admin_users
                ),
                tables=database_stats
            )

    except Exception as e:
        logger.error(f"Error fetching system stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch system statistics"
        )


@router.post("/auth/invalidate-session")
async def invalidate_session_endpoint(request: Request):
    """Invalidate a session using JWT token - for centralized auth system"""
    logger.info("🔄 Backend Service: invalidate-session endpoint called")

    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    logger.info(f"Authorization header present: {bool(auth_header)}")

    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("❌ Missing or invalid authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )

    token = auth_header[7:]  # Remove "Bearer " prefix
    logger.info(f"Token extracted (first 20 chars): {token[:20]}...")

    try:
        # Use the same auth service that created the token
        auth_service = get_auth_service()
        user = await auth_service.verify_token(token)

        if not user:
            logger.warning("❌ Token verification failed via auth service")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )

        logger.info(f"✅ Token verified successfully via auth service, user: {user.email}")

        # Use the auth service to invalidate the session
        success = await auth_service.invalidate_session(token)

        if success:
            logger.info(f"✅ Session invalidated successfully for user: {user.email}")
            return {"success": True, "message": "Session invalidated successfully"}
        else:
            logger.warning(f"❌ Failed to invalidate session for user: {user.email}")
            return {"success": False, "message": "Failed to invalidate session"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error invalidating session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate session"
        )


@router.get("/current-session")
async def get_current_session(request: Request):
    """Get current session information for the authenticated user"""

    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )

    token = auth_header[7:]  # Remove "Bearer " prefix

    try:
        # Use the auth service to verify token and get user info
        auth_service = get_auth_service()
        user = await auth_service.verify_token(token)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )

        # Find the current session for this token
        database = get_database()
        with database.get_read_session_context() as session:
            from app.models.unified_models import UserSession

            # Hash the token to find the matching session
            import hashlib
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            user_session = session.query(UserSession).filter(
                UserSession.user_id == user.id,
                UserSession.token_hash == token_hash,
                UserSession.active == True
            ).first()

            if user_session:
                return {
                    "session_id": user_session.id,
                    "user_id": user_session.user_id,
                    "email": user.email,
                    "login_time": user_session.created_at.isoformat() if user_session.created_at else None,
                    "last_activity": user_session.last_updated_at.isoformat() if user_session.last_updated_at else None,
                    "expires_at": user_session.expires_at.isoformat() if user_session.expires_at else None,
                    "ip_address": user_session.ip_address,
                    "user_agent": user_session.user_agent,
                    "active": user_session.active
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Current session not found"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get current session"
        )


@router.get("/debug/config")
async def debug_config():
    """Debug endpoint to show current configuration"""
    from app.core.config import get_settings
    settings = get_settings()

    return {
        "jwt_secret_key": settings.JWT_SECRET_KEY,
        "jwt_algorithm": settings.JWT_ALGORITHM,
        "debug": settings.DEBUG,
        "backend_service_url": settings.BACKEND_SERVICE_URL if hasattr(settings, 'BACKEND_SERVICE_URL') else "Not set",
        "env_file_loaded": "Check logs for 'Loading configuration from:' message"
    }


@router.get("/permissions/matrix", response_model=PermissionMatrixResponse)
async def get_permission_matrix(
    admin_user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get the complete permission matrix for all roles and resources"""
    try:
        # Get all available roles, resources, and actions
        roles = [role.value for role in Role]
        resources = [resource.value for resource in Resource]
        actions = [action.value for action in Action]

        # Build the permission matrix from DEFAULT_ROLE_PERMISSIONS
        matrix = {}
        for role in Role:
            matrix[role.value] = {}
            for resource in Resource:
                if resource in DEFAULT_ROLE_PERMISSIONS[role]:
                    matrix[role.value][resource.value] = [
                        action.value for action in DEFAULT_ROLE_PERMISSIONS[role][resource]
                    ]
                else:
                    matrix[role.value][resource.value] = []

        return PermissionMatrixResponse(
            roles=roles,
            resources=resources,
            actions=actions,
            matrix=matrix
        )
    except Exception as e:
        logger.error(f"Error fetching permission matrix: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch permission matrix"
        )





# WitMappingDeactivationRequest class removed - handled by ETL service


# All remaining issuetype endpoints removed - handled by ETL service

# Permission Management Endpoints

@router.get("/permissions/matrix", response_model=PermissionMatrixResponse)
async def get_permission_matrix(
    admin_user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get the complete permission matrix for all roles and resources"""
    try:
        # Get all available roles, resources, and actions
        roles = [role.value for role in Role]
        resources = [resource.value for resource in Resource]
        actions = [action.value for action in Action]

        # Build the permission matrix from DEFAULT_ROLE_PERMISSIONS
        matrix = {}
        for role in Role:
            matrix[role.value] = {}
            for resource in Resource:
                if resource in DEFAULT_ROLE_PERMISSIONS[role]:
                    matrix[role.value][resource.value] = [
                        action.value for action in DEFAULT_ROLE_PERMISSIONS[role][resource]
                    ]
                else:
                    matrix[role.value][resource.value] = []

        return PermissionMatrixResponse(
            roles=roles,
            resources=resources,
            actions=actions,
            matrix=matrix
        )
    except Exception as e:
        logger.error(f"Error fetching permission matrix: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch permission matrix"
        )


# Permission Management Endpoints

@router.get("/permissions/matrix", response_model=PermissionMatrixResponse)
async def get_permission_matrix(
    admin_user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get the complete permission matrix for all roles and resources"""
    try:
        # Get all available roles, resources, and actions
        roles = [role.value for role in Role]
        resources = [resource.value for resource in Resource]
        actions = [action.value for action in Action]

        # Build the permission matrix from DEFAULT_ROLE_PERMISSIONS
        matrix = {}
        for role in Role:
            matrix[role.value] = {}
            for resource in Resource:
                if resource in DEFAULT_ROLE_PERMISSIONS[role]:
                    matrix[role.value][resource.value] = [
                        action.value for action in DEFAULT_ROLE_PERMISSIONS[role][resource]
                    ]
                else:
                    matrix[role.value][resource.value] = []

        return PermissionMatrixResponse(
            roles=roles,
            resources=resources,
            actions=actions,
            matrix=matrix
        )
    except Exception as e:
        logger.error(f"Error fetching permission matrix: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch permission matrix"
        )


# User Management Endpoints (KEEP - Core Backend Responsibility)

@router.get("/users", response_model=List[UserResponse])
async def delete_issuetype_hierarchy(
    hierarchy_id: int,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Delete an issuetype hierarchy"""
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
                WitMapping.issuetype_hierarchy_id == hierarchy_id
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


# User Management Endpoints (KEEP - Core Backend Responsibility)

@router.get("/users", response_model=List[UserResponse])
async def get_issuetype_hierarchy_dependencies(
    hierarchy_id: int,
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get dependencies for an issue type hierarchy"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
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
                WitMapping.issuetype_hierarchy_id == hierarchy_id,
                WitMapping.active == True
            ).count()

            # Count dependent issues through the mappings and issue types
            dependent_issues_count = session.query(WorkItem).join(
                Wit, WorkItem.wit_id == Wit.id
            ).join(
                WitMapping, Wit.issuetype_mapping_id == WitMapping.id
            ).filter(
                WitMapping.issuetype_hierarchy_id == hierarchy_id,
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


# WitHierarchyDeactivationRequest class removed - handled by ETL service


# Permission Management Endpoints

@router.get("/permissions/matrix", response_model=PermissionMatrixResponse)
async def get_permission_matrix(
    admin_user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get the complete permission matrix for all roles and resources"""
    try:
        # Get all available roles, resources, and actions
        roles = [role.value for role in Role]
        resources = [resource.value for resource in Resource]
        actions = [action.value for action in Action]

        # Build the permission matrix from DEFAULT_ROLE_PERMISSIONS
        matrix = {}
        for role in Role:
            matrix[role.value] = {}
            for resource in Resource:
                if resource in DEFAULT_ROLE_PERMISSIONS[role]:
                    matrix[role.value][resource.value] = [
                        action.value for action in DEFAULT_ROLE_PERMISSIONS[role][resource]
                    ]
                else:
                    matrix[role.value][resource.value] = []

        return PermissionMatrixResponse(
            roles=roles,
            resources=resources,
            actions=actions,
            matrix=matrix
        )
    except Exception as e:
        logger.error(f"Error fetching permission matrix: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch permission matrix"
        )


# User Management Endpoints (KEEP - Core Backend Responsibility)

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
                    role=u.role.value,
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


# Permission Management Endpoints

@router.get("/permissions/matrix", response_model=PermissionMatrixResponse)
async def get_permission_matrix(
    admin_user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get the complete permission matrix for all roles and resources"""
    try:
        # Get all available roles, resources, and actions
        roles = [role.value for role in Role]
        resources = [resource.value for resource in Resource]
        actions = [action.value for action in Action]

        # Build the permission matrix from DEFAULT_ROLE_PERMISSIONS
        matrix = {}
        for role in Role:
            matrix[role.value] = {}
            for resource in Resource:
                if resource in DEFAULT_ROLE_PERMISSIONS[role]:
                    matrix[role.value][resource.value] = [
                        action.value for action in DEFAULT_ROLE_PERMISSIONS[role][resource]
                    ]
                else:
                    matrix[role.value][resource.value] = []

        return PermissionMatrixResponse(
            roles=roles,
            resources=resources,
            actions=actions,
            matrix=matrix
        )

    except Exception as e:
        logger.error(f"Error fetching permission matrix: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch permission matrix"
        )


# Active Sessions Management Endpoints

class ActiveSessionResponse(BaseModel):
    session_id: str
    user_name: str
    email: str
    role: str
    login_time: Optional[str]
    last_activity: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]

    class Config:
        from_attributes = True


@router.get("/active-sessions", response_model=List[ActiveSessionResponse])
async def get_active_sessions(
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get all active user sessions"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            from app.core.utils import DateTimeHelper

            # ✅ SECURITY: Query active sessions filtered by tenant_id
            active_sessions = session.query(
                UserSession,
                User.first_name,
                User.last_name,
                User.email,
                User.role
            ).join(
                User, UserSession.user_id == User.id
            ).filter(
                and_(
                    User.tenant_id == user.tenant_id,  # Filter by tenant_id
                    UserSession.active == True,
                    UserSession.expires_at > DateTimeHelper.now_utc(),
                    User.active == True
                )
            ).order_by(UserSession.created_at.desc()).all()

            return [
                ActiveSessionResponse(
                    session_id=str(session_obj.id),
                    user_name=f"{first_name or ''} {last_name or ''}".strip() or email.split('@')[0],
                    email=email,
                    role=role,
                    login_time=session_obj.created_at.isoformat() if session_obj.created_at else None,
                    last_activity=session_obj.last_updated_at.isoformat() if session_obj.last_updated_at else None,
                    ip_address=session_obj.ip_address,
                    user_agent=session_obj.user_agent
                )
                for session_obj, first_name, last_name, email, role in active_sessions
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
    """Terminate all active user sessions (including current user's session)"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # ✅ SECURITY: Get session IDs for current client only (using join for filtering)
            session_ids_to_terminate = session.query(UserSession.id).join(User).filter(
                User.tenant_id == user.tenant_id,
                UserSession.active == True
            ).all()

            # Extract the IDs from the result tuples
            session_ids = [session_id[0] for session_id in session_ids_to_terminate]
            terminated_count = len(session_ids)

            # ✅ FIX: Update sessions without join to avoid SQLAlchemy error
            if session_ids:
                session.query(UserSession).filter(
                    UserSession.id.in_(session_ids)
                ).update({
                    'active': False,
                    'last_updated_at': DateTimeHelper.now_utc()
                }, synchronize_session=False)

            session.commit()

            logger.info(f"Admin {user.email} terminated {terminated_count} user sessions")

            return {
                "message": f"Successfully terminated {terminated_count} user sessions",
                "terminated_count": terminated_count
            }

    except Exception as e:
        logger.error(f"Error terminating all sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to terminate all sessions"
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

            # ✅ SECURITY: Find the session to terminate (filtered by tenant_id)
            user_session = session.query(UserSession).join(User).filter(
                and_(
                    UserSession.id == session_id,
                    UserSession.active == True,
                    User.tenant_id == user.tenant_id  # Ensure session belongs to current client
                )
            ).first()

            if not user_session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found or already terminated"
                )

            # Get session user info for logging
            session_user = session.query(User).filter(User.id == user_session.user_id).first()

            # Deactivate the session
            user_session.active = False
            user_session.last_updated_at = DateTimeHelper.now_utc()

            session.commit()

            logger.info(f"Admin {user.email} terminated session {session_id} for user {session_user.email if session_user else 'unknown'}")

            return {
                "message": "Session terminated successfully",
                "session_id": session_id,
                "terminated_user": session_user.email if session_user else "unknown"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error terminating session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to terminate session"
        )


# Color Schema Settings Endpoints

class ColorSchemaRequest(BaseModel):
    color1: str
    color2: str
    color3: str
    color4: str
    color5: str

class ColorSchemaModeRequest(BaseModel):
    mode: str  # 'default' or 'custom'

class ThemeModeRequest(BaseModel):
    mode: str  # 'light' or 'dark'

@router.get("/color-schema")
async def get_color_schema(
    user: User = Depends(require_permission(Resource.SETTINGS, Action.READ))
):
    """Get custom color schema settings"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # ✅ SECURITY: Get color schema mode filtered by tenant_id
            mode_setting = session.query(SystemSettings).filter(
                SystemSettings.setting_key == "color_schema_mode",
                SystemSettings.tenant_id == user.tenant_id
            ).first()

            color_mode = mode_setting.setting_value if mode_setting else "default"

            # Get all custom color settings
            color_settings = {}
            for i in range(1, 6):
                setting_key = f"custom_color{i}"  # Fixed: removed underscore
                # ✅ SECURITY: Filter by tenant_id
                setting = session.query(SystemSettings).filter(
                    SystemSettings.setting_key == setting_key,
                    SystemSettings.tenant_id == user.tenant_id
                ).first()

                if setting:
                    color_settings[f"color{i}"] = setting.setting_value
                else:
                    # Default custom colors (WEX brand colors)
                    defaults = {
                        "color1": "#C8102E",  # WEX Red
                        "color2": "#253746",  # Dark Blue
                        "color3": "#00C7B1",  # Teal
                        "color4": "#A2DDF8",  # Light Blue
                        "color5": "#FFBF3F",  # Yellow
                    }
                    color_settings[f"color{i}"] = defaults[f"color{i}"]

            return {
                "success": True,
                "mode": color_mode,
                "colors": color_settings
            }

    except Exception as e:
        logger.error(f"Error getting color schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get color schema"
        )

@router.post("/color-schema")
async def update_color_schema(
    request: ColorSchemaRequest,
    user: User = Depends(require_permission(Resource.SETTINGS, Action.ADMIN))
):
    """Update custom color schema settings"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # ✅ SECURITY: Use current user's client for system settings
            # No need to query client - use user's tenant_id directly

            # Update each color setting
            colors = request.model_dump()
            for color_key, color_value in colors.items():
                setting_key = f"custom_{color_key}"

                # ✅ SECURITY: Get or create setting filtered by tenant_id
                setting = session.query(SystemSettings).filter(
                    SystemSettings.setting_key == setting_key,
                    SystemSettings.tenant_id == user.tenant_id
                ).first()

                if not setting:
                    setting = SystemSettings(
                        setting_key=setting_key,
                        setting_value=color_value,
                        setting_type='string',
                        description=f"Custom {color_key} for color schema",
                        tenant_id=user.tenant_id  # ✅ SECURITY: Use user's tenant_id
                    )
                    session.add(setting)
                else:
                    setting.setting_value = color_value
                    setting.last_updated_at = func.now()

            session.commit()

            # 🚀 NEW: Notify ETL service of color schema change
            await notify_etl_color_schema_change(user.tenant_id, colors)

            return {
                "success": True,
                "message": "Color schema updated successfully",
                "colors": colors
            }

    except Exception as e:
        logger.error(f"Error updating color schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update color schema"
        )

@router.post("/color-schema/mode")
async def update_color_schema_mode(
    request: ColorSchemaModeRequest,
    user: User = Depends(require_permission(Resource.SETTINGS, Action.ADMIN))
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
            # ✅ SECURITY: Use current user's client for system settings
            # No need to query client - use user's tenant_id directly

            # ✅ SECURITY: Get or create the color schema mode setting filtered by tenant_id
            setting = session.query(SystemSettings).filter(
                SystemSettings.setting_key == "color_schema_mode",
                SystemSettings.tenant_id == user.tenant_id
            ).first()

            if setting:
                # Update existing setting
                setting.setting_value = request.mode
                setting.last_updated_at = func.now()
            else:
                # Create new setting
                setting = SystemSettings(
                    setting_key="color_schema_mode",
                    setting_value=request.mode,
                    setting_type='string',
                    description="Color schema mode (default or custom)",
                    tenant_id=user.tenant_id  # ✅ SECURITY: Use user's tenant_id
                )
                session.add(setting)

            session.commit()

            # 🚀 NEW: Notify ETL service of color schema mode change
            await notify_etl_color_schema_mode_change(user.tenant_id, request.mode)

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


# Theme Mode Settings Endpoints

@router.get("/theme-mode")
async def get_theme_mode(
    user: User = Depends(require_permission(Resource.SETTINGS, Action.READ))
):
    """Get current theme mode setting"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # ✅ SECURITY: Get theme mode setting filtered by tenant_id
            setting = session.query(SystemSettings).filter(
                SystemSettings.setting_key == "theme_mode",
                SystemSettings.tenant_id == user.tenant_id
            ).first()

            theme_mode = setting.setting_value if setting else "light"

            return {
                "success": True,
                "mode": theme_mode
            }

    except Exception as e:
        logger.error(f"Error getting theme mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get theme mode"
        )

@router.post("/theme-mode")
async def update_theme_mode(
    request: ThemeModeRequest,
    user: User = Depends(require_permission(Resource.SETTINGS, Action.ADMIN))
):
    """Update theme mode (light or dark)"""
    try:
        # Validate mode value
        if request.mode not in ['light', 'dark']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mode must be 'light' or 'dark'"
            )

        database = get_database()
        with database.get_write_session_context() as session:
            # ✅ SECURITY: Get or create the theme mode setting filtered by tenant_id
            setting = session.query(SystemSettings).filter(
                SystemSettings.setting_key == "theme_mode",
                SystemSettings.tenant_id == user.tenant_id
            ).first()

            if setting:
                # Update existing setting
                setting.setting_value = request.mode
                setting.last_updated_at = func.now()
            else:
                # Create new setting
                setting = SystemSettings(
                    setting_key="theme_mode",
                    setting_value=request.mode,
                    setting_type='string',
                    description="User interface theme mode (light or dark)",
                    tenant_id=user.tenant_id  # ✅ SECURITY: Use user's tenant_id
                )
                session.add(setting)

            session.commit()

            return {
                "success": True,
                "message": f"Theme mode updated to '{request.mode}'",
                "mode": request.mode
            }

    except Exception as e:
        logger.error(f"Error updating theme mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update theme mode"
        )


# Tenant Management Endpoints

@router.get("/clients", response_model=List[TenantResponse])
async def get_all_clients(
    skip: int = 0,
    limit: int = 100,
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get current user's client information"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # ✅ SECURITY: Only show the current user's client
            clients = session.query(Tenant).filter(
                Tenant.id == user.tenant_id
            ).offset(skip).limit(limit).all()

            return [
                TenantResponse(
                    id=client.id,
                    name=client.name,
                    website=client.website,
                    logo_filename=client.logo_filename,
                    active=client.active,
                    created_at=client.created_at.isoformat() if client.created_at else "",
                    last_updated_at=client.last_updated_at.isoformat() if client.last_updated_at else ""
                )
                for client in clients
            ]
    except Exception as e:
        logger.error(f"Error fetching clients: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch clients"
        )


@router.post("/clients", response_model=TenantResponse)
async def create_client(
    client_data: TenantCreateRequest,
    admin_user: User = Depends(require_permission("admin_panel", "execute"))
):
    """Create a new client"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Check if client name already exists
            existing_client = session.query(Tenant).filter(
                Tenant.name == client_data.name
            ).first()

            if existing_client:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tenant name already exists"
                )

            # Create new client
            new_client = Tenant(
                name=client_data.name,
                website=client_data.website,
                active=client_data.active,
                created_at=DateTimeHelper.now_utc(),
                last_updated_at=DateTimeHelper.now_utc()
            )

            session.add(new_client)
            session.commit()
            session.refresh(new_client)

            logger.info(f"✅ Tenant created: {new_client.name} by admin {admin_user.email}")

            return TenantResponse(
                id=new_client.id,
                name=new_client.name,
                website=new_client.website,
                logo_filename=new_client.logo_filename,
                active=new_client.active,
                created_at=new_client.created_at.isoformat(),
                last_updated_at=new_client.last_updated_at.isoformat()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create client"
        )


@router.put("/clients/{tenant_id}", response_model=TenantResponse)
async def update_client(
    tenant_id: int,
    client_data: TenantUpdateRequest,
    admin_user: User = Depends(require_permission("admin_panel", "execute"))
):
    """Update an existing client"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Find the client
            client = session.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not client:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tenant not found"
                )

            # Check if new name conflicts with existing client
            if client_data.name and client_data.name != client.name:
                existing_client = session.query(Tenant).filter(
                    Tenant.name == client_data.name,
                    Tenant.id != tenant_id
                ).first()

                if existing_client:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Tenant name already exists"
                    )

            # Update fields
            if client_data.name is not None:
                client.name = client_data.name
            if client_data.website is not None:
                client.website = client_data.website
            if client_data.active is not None:
                client.active = client_data.active

            client.last_updated_at = DateTimeHelper.now_utc()

            session.commit()
            session.refresh(client)

            logger.info(f"✅ Tenant updated: {client.name} by admin {admin_user.email}")

            return TenantResponse(
                id=client.id,
                name=client.name,
                website=client.website,
                logo_filename=client.logo_filename,
                active=client.active,
                created_at=client.created_at.isoformat(),
                last_updated_at=client.last_updated_at.isoformat()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update client"
        )


@router.delete("/clients/{tenant_id}")
async def delete_client(
    tenant_id: int,
    admin_user: User = Depends(require_permission("admin_panel", "delete"))
):
    """Delete a client (with dependency checking)"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Find the client
            client = session.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not client:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tenant not found"
                )

            # Check for dependencies (users, integrations, etc.)
            user_count = session.query(User).filter(User.tenant_id == tenant_id).count()
            integration_count = session.query(Integration).filter(Integration.tenant_id == tenant_id).count()

            if user_count > 0 or integration_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete client: {user_count} users and {integration_count} integrations exist. Please reassign or delete them first."
                )

            # Delete logo file if exists
            if client.logo_filename:
                import os
                try:
                    # Delete from frontend static folder
                    frontend_logo_path = f"services/frontend-app/public/static/logos/{client.logo_filename}"
                    if os.path.exists(frontend_logo_path):
                        os.remove(frontend_logo_path)

                    # Delete from ETL static folder
                    etl_logo_path = f"services/etl-service/app/static/logos/{client.logo_filename}"
                    if os.path.exists(etl_logo_path):
                        os.remove(etl_logo_path)

                    logger.info(f"✅ Logo files deleted for client: {client.name}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to delete logo files: {e}")

            # Delete the client
            session.delete(client)
            session.commit()

            logger.info(f"✅ Tenant deleted: {client.name} by admin {admin_user.email}")

            return {
                "success": True,
                "message": f"Tenant '{client.name}' deleted successfully"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete client"
        )


@router.post("/clients/{tenant_id}/logo")
async def upload_client_logo(
    tenant_id: int,
    logo: UploadFile = File(...),
    admin_user: User = Depends(require_permission("admin_panel", "execute"))
):
    """Upload logo for a client (saves to both frontend and ETL static folders)"""
    try:
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

        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper
            import os
            import uuid
            from pathlib import Path

            # Find the client
            client = session.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not client:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tenant not found"
                )

            # Generate unique filename
            file_extension = logo.filename.split('.')[-1] if logo.filename and '.' in logo.filename else 'png'
            unique_filename = f"{client.name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}.{file_extension}"

            # Create directories if they don't exist
            frontend_logo_dir = Path("services/frontend-app/public/static/logos")
            etl_logo_dir = Path("services/etl-service/app/static/logos")

            frontend_logo_dir.mkdir(parents=True, exist_ok=True)
            etl_logo_dir.mkdir(parents=True, exist_ok=True)

            # Save to both locations
            frontend_logo_path = frontend_logo_dir / unique_filename
            etl_logo_path = etl_logo_dir / unique_filename

            # Read file content
            logo_content = await logo.read()

            # Write to both locations
            with open(frontend_logo_path, "wb") as f:
                f.write(logo_content)

            with open(etl_logo_path, "wb") as f:
                f.write(logo_content)

            # Delete old logo files if they exist
            if client.logo_filename:
                try:
                    old_frontend_path = frontend_logo_dir / client.logo_filename
                    old_etl_path = etl_logo_dir / client.logo_filename

                    if old_frontend_path.exists():
                        old_frontend_path.unlink()
                    if old_etl_path.exists():
                        old_etl_path.unlink()

                    logger.info(f"✅ Old logo files deleted for client: {client.name}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to delete old logo files: {e}")

            # Update client record
            client.logo_filename = unique_filename
            client.last_updated_at = DateTimeHelper.now_utc()

            session.commit()
            session.refresh(client)

            logger.info(f"✅ Logo uploaded for client: {client.name} by admin {admin_user.email}")

            return TenantResponse(
                id=client.id,
                name=client.name,
                website=client.website,
                logo_filename=client.logo_filename,
                active=client.active,
                created_at=client.created_at.isoformat(),
                last_updated_at=client.last_updated_at.isoformat()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading client logo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload logo"
        )

