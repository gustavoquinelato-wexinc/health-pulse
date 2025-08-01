"""
Admin Panel API Routes

Provides administrative functionality for user management, role assignment,
and system configuration. Only accessible to admin users.
"""

from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from pydantic import BaseModel, EmailStr

from app.core.database import get_database
from app.models.unified_models import (
    User, UserPermission, UserSession, Integration, Project, Issue, Client, IssueChangelog,
    Repository, PullRequest, PullRequestCommit, PullRequestReview, PullRequestComment,
    JiraPullRequestLinks, Issuetype, Status, JobSchedule, SystemSettings,
    StatusMapping, Workflow, IssuetypeMapping, IssuetypeHierarchy, MigrationHistory,
    ProjectsIssuetypes, ProjectsStatuses
)
from app.auth.auth_middleware import require_permission
from app.auth.auth_service import get_auth_service
from app.auth.permissions import Role, Resource, Action, get_user_permissions, DEFAULT_ROLE_PERMISSIONS
from app.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


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
    active: bool
    last_sync_at: Optional[str] = None

class IntegrationUpdateRequest(BaseModel):
    base_url: str
    username: Optional[str] = None
    password: Optional[str] = None

class IntegrationDetailResponse(BaseModel):
    id: int
    name: str
    base_url: Optional[str] = None
    username: Optional[str] = None
    password_masked: Optional[str] = None  # Masked version for display

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
        with database.get_session() as session:
            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            users = session.query(User).filter(
                User.client_id == user.client_id
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
        with database.get_session() as session:
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
                client_id=admin_user.client_id,
                active=True
            )

            # Set password if provided (for local auth)
            if user_data.password:
                from app.auth.auth_service import AuthService
                auth_service = AuthService(database)
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
        with database.get_session() as session:
            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            user = session.query(User).filter(
                User.id == user_id,
                User.client_id == admin_user.client_id
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
        with database.get_session() as session:
            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            user = session.query(User).filter(
                User.id == user_id,
                User.client_id == admin_user.client_id
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


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    admin_user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get system statistics"""
    try:
        database = get_database()
        with database.get_session() as session:
            # ✅ SECURITY: User statistics filtered by client_id
            total_users = session.query(User).filter(User.client_id == admin_user.client_id).count()
            active_users = session.query(User).filter(
                User.client_id == admin_user.client_id,
                User.active == True
            ).count()

            # Count logged users (users with active sessions) for current client
            from app.core.utils import DateTimeHelper
            logged_users = session.query(User).join(UserSession).filter(
                User.client_id == admin_user.client_id,
                User.active == True,
                UserSession.active == True,
                UserSession.expires_at > DateTimeHelper.now_utc()
            ).distinct().count()

            # ✅ SECURITY: Admin users count filtered by client_id
            admin_users = session.query(User).filter(
                User.client_id == admin_user.client_id,
                User.is_admin == True,
                User.active == True
            ).count()

            # ✅ SECURITY: Role distribution filtered by client_id
            roles_distribution = {}
            for role in Role:
                count = session.query(User).filter(
                    User.client_id == admin_user.client_id,
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
                "clients": Client,
                "integrations": Integration,
                "projects": Project,
                "issues": Issue,
                "issue_changelogs": IssueChangelog,
                "repositories": Repository,
                "pull_requests": PullRequest,
                "pull_request_commits": PullRequestCommit,
                "pull_request_reviews": PullRequestReview,
                "pull_request_comments": PullRequestComment,
                "jira_pull_request_links": JiraPullRequestLinks,
                "issuetypes": Issuetype,
                "statuses": Status,
                "status_mappings": StatusMapping,
                "workflows": Workflow,
                "issuetype_mappings": IssuetypeMapping,
                "issuetype_hierarchies": IssuetypeHierarchy,
                "projects_issuetypes": ProjectsIssuetypes,
                "projects_statuses": ProjectsStatuses,
                "job_schedules": JobSchedule,
                "system_settings": SystemSettings,
                "migration_history": MigrationHistory
            }

            # ✅ SECURITY: Count records filtered by client_id
            for table_name, model in table_models.items():
                try:
                    # Skip tables that don't have client_id (global tables)
                    if table_name in ['clients', 'migration_history']:
                        # These are global tables - count all records
                        if table_name in ['projects_issuetypes', 'projects_statuses']:
                            count = session.query(model).count() or 0
                        else:
                            count = session.query(func.count(model.id)).scalar() or 0
                    else:
                        # Filter by client_id for client-specific tables
                        if hasattr(model, 'client_id'):
                            if table_name in ['projects_issuetypes', 'projects_statuses']:
                                count = session.query(model).filter(model.client_id == admin_user.client_id).count() or 0
                            else:
                                count = session.query(func.count(model.id)).filter(model.client_id == admin_user.client_id).scalar() or 0
                        else:
                            # For tables without client_id, count all (like user_sessions, user_permissions)
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

            return SystemStatsResponse(
                total_users=total_users,
                active_users=active_users,
                logged_users=logged_users,
                admin_users=admin_users,
                roles_distribution=roles_distribution,
                database_stats=database_stats,
                database_size_mb=database_size_mb,
                total_records=total_records
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
        with database.get_session() as session:
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


@router.get("/integrations", response_model=List[IntegrationResponse])
async def get_integrations(
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get all integrations for current user's client"""
    try:
        database = get_database()
        with database.get_session() as session:
            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            integrations = session.query(Integration).filter(
                Integration.client_id == user.client_id
            ).order_by(Integration.name).all()

            return [
                IntegrationResponse(
                    id=integration.id,
                    name=integration.name or "Unknown",
                    integration_type=integration.name or "Unknown",  # Using name as type for now
                    base_url=integration.url,
                    username=integration.username,
                    active=integration.active,  # BaseEntity provides this field
                    last_sync_at=integration.last_sync_at.isoformat() if integration.last_sync_at else None
                )
                for integration in integrations
            ]
    except Exception as e:
        logger.error(f"Error fetching integrations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch integrations"
        )


@router.get("/integrations/{integration_id}", response_model=IntegrationDetailResponse)
async def get_integration_details(
    integration_id: int,
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get integration details for editing"""
    try:
        database = get_database()
        with database.get_session() as session:
            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.client_id == user.client_id
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
                name=integration.name,
                base_url=integration.url,
                username=integration.username,
                password_masked=password_masked
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
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Update an integration"""
    try:
        database = get_database()
        with database.get_session() as session:
            # Get the integration
            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.client_id == user.client_id
            ).first()
            if not integration:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found"
                )

            # Update fields
            integration.url = update_data.base_url
            integration.username = update_data.username

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

            logger.info(f"Admin {user.email} updated integration {integration.name}")

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
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Activate an integration"""
    try:
        database = get_database()
        with database.get_session() as session:
            from datetime import datetime

            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.client_id == user.client_id
            ).first()

            if not integration:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found"
                )

            integration.active = True
            integration.last_updated_at = datetime.utcnow()
            session.commit()

            logger.info(f"Admin {user.email} activated integration {integration.name}")

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
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Deactivate an integration"""
    try:
        database = get_database()
        with database.get_session() as session:
            from datetime import datetime

            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.client_id == user.client_id
            ).first()

            if not integration:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found"
                )

            integration.active = False
            integration.last_updated_at = datetime.utcnow()
            session.commit()

            logger.info(f"Admin {user.email} deactivated integration {integration.name}")

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
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Delete an integration"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import Project, Issue

            integration = session.query(Integration).filter(
                Integration.id == integration_id,
                Integration.client_id == user.client_id
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
            dependent_issues = session.query(Issue).filter(
                Issue.integration_id == integration_id,
                Issue.active == True
            ).count()

            if dependent_projects > 0 or dependent_issues > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete integration: {dependent_projects} active projects and {dependent_issues} active issues are using this integration"
                )

            # Delete the integration
            session.delete(integration)
            session.commit()

            logger.info(f"Admin {user.email} deleted integration {integration.name}")

            return {"message": "Integration deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting integration {integration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete integration"
        )


@router.get("/status-mappings")
async def get_status_mappings(
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get all status mappings"""
    try:
        database = get_database()
        with database.get_session() as session:
            # Query status mappings with workflow information
            from app.models.unified_models import StatusMapping, Workflow

            status_mappings = session.query(
                StatusMapping,
                Workflow.step_name.label('workflow_step_name'),
                Workflow.step_number.label('step_number')
            ).outerjoin(
                Workflow, StatusMapping.workflow_id == Workflow.id
            ).order_by(StatusMapping.status_from).all()

            return [
                {
                    "id": mapping.StatusMapping.id,
                    "status_from": mapping.StatusMapping.status_from,
                    "status_to": mapping.StatusMapping.status_to,
                    "status_category": mapping.StatusMapping.status_category,
                    "workflow": mapping.workflow_step_name or "None",
                    "step_number": mapping.step_number,
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


@router.post("/status-mappings")
async def create_status_mapping(
    create_data: StatusMappingCreateRequest,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Create a new status mapping"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import StatusMapping
            from datetime import datetime

            # Create new status mapping
            new_mapping = StatusMapping(
                status_from=create_data.status_from,
                status_to=create_data.status_to,
                status_category=create_data.status_category,
                workflow_id=create_data.workflow_id,
                client_id=user.client_id,
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
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get status mapping details for editing"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import StatusMapping

            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            mapping = session.query(StatusMapping).filter(
                StatusMapping.id == mapping_id,
                StatusMapping.client_id == user.client_id
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


@router.put("/status-mappings/{mapping_id}")
async def update_status_mapping(
    mapping_id: int,
    update_data: StatusMappingUpdateRequest,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Update a status mapping"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import StatusMapping

            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            mapping = session.query(StatusMapping).filter(
                StatusMapping.id == mapping_id,
                StatusMapping.client_id == user.client_id
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
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Delete a status mapping (soft delete to preserve referential integrity)"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import StatusMapping, Status

            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            mapping = session.query(StatusMapping).filter(
                StatusMapping.id == mapping_id,
                StatusMapping.client_id == user.client_id
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
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Activate a status mapping"""
    try:
        database = get_database()
        with database.get_session() as session:
            from datetime import datetime

            mapping = session.query(StatusMapping).filter(
                StatusMapping.id == mapping_id,
                StatusMapping.client_id == user.client_id
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
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get dependencies for a status mapping"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import StatusMapping, Issue, Status

            mapping = session.query(StatusMapping).filter(
                StatusMapping.id == mapping_id,
                StatusMapping.client_id == user.client_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Status mapping not found"
                )

            # Count dependent issues that use this status mapping
            # Issues are connected through their status_id -> Status -> status_mapping_id -> StatusMapping
            dependent_issues_count = session.query(Issue).join(
                Status, Issue.status_id == Status.id
            ).filter(
                Status.status_mapping_id == mapping_id,
                Status.active == True,
                Issue.active == True,
                Issue.client_id == user.client_id
            ).count()

            # Get available reassignment targets (active status mappings, excluding current)
            reassignment_targets = session.query(StatusMapping).filter(
                StatusMapping.active == True,
                StatusMapping.id != mapping_id,
                StatusMapping.client_id == user.client_id
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
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Deactivate a status mapping with options for handling dependencies"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import StatusMapping, Issue, Status
            from datetime import datetime

            # Verify mapping exists and belongs to user's client
            mapping = session.query(StatusMapping).filter(
                StatusMapping.id == mapping_id,
                StatusMapping.client_id == user.client_id
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
            dependent_issues = session.query(Issue).join(
                Status, Issue.status_id == Status.id
            ).filter(
                Status.status_mapping_id == mapping_id,
                Status.active == True,
                Issue.active == True,
                Issue.client_id == user.client_id
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
                    StatusMapping.client_id == user.client_id
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
                    Status.client_id == user.client_id
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
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get all workflows"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import Workflow, Integration

            # ✅ SECURITY: Filter workflows by client_id
            workflows = session.query(
                Workflow,
                Integration.name.label('integration_name')
            ).outerjoin(
                Integration, Workflow.integration_id == Integration.id
            ).filter(
                Workflow.client_id == user.client_id
            ).order_by(Workflow.step_number.nulls_last()).all()

            return [
                {
                    "id": workflow.Workflow.id,
                    "step_name": workflow.Workflow.step_name,
                    "step_number": workflow.Workflow.step_number,
                    "step_category": workflow.Workflow.step_category,
                    "is_delivery_milestone": workflow.Workflow.is_delivery_milestone,
                    "integration_name": workflow.integration_name or "All Integrations",
                    "integration_id": workflow.Workflow.integration_id,
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
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get workflow details for editing"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import Workflow

            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            workflow = session.query(Workflow).filter(
                Workflow.id == workflow_id,
                Workflow.client_id == user.client_id
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
                "is_delivery_milestone": workflow.is_delivery_milestone,
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



class WorkflowUpdateRequest(BaseModel):
    step_name: str
    step_number: Optional[int] = None
    step_category: str
    is_delivery_milestone: bool = False
    integration_id: Optional[int] = None


class WorkflowDeactivationRequest(BaseModel):
    action: str  # "keep_mappings", "reassign_mappings"
    target_workflow_id: Optional[int] = None  # Required if action is "reassign_mappings"


@router.put("/workflows/{workflow_id}")
async def update_workflow(
    workflow_id: int,
    update_data: WorkflowUpdateRequest,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Update a workflow"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import Workflow

            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            workflow = session.query(Workflow).filter(
                Workflow.id == workflow_id,
                Workflow.client_id == user.client_id
            ).first()
            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found"
                )

            # Validate single delivery milestone constraint
            if update_data.is_delivery_milestone:
                existing_milestone = session.query(Workflow).filter(
                    Workflow.client_id == user.client_id,
                    Workflow.integration_id == update_data.integration_id,
                    Workflow.is_delivery_milestone == True,
                    Workflow.active == True,
                    Workflow.id != workflow_id  # Exclude current workflow
                ).first()

                if existing_milestone:
                    integration_name = "All Integrations" if update_data.integration_id is None else f"Integration ID {update_data.integration_id}"
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"A delivery milestone already exists for {integration_name}. Only one delivery milestone is allowed per client/integration combination."
                    )

            # Update fields
            workflow.step_name = update_data.step_name
            workflow.step_number = update_data.step_number
            workflow.step_category = update_data.step_category
            workflow.is_delivery_milestone = update_data.is_delivery_milestone
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


class WorkflowCreateRequest(BaseModel):
    step_name: str
    step_number: Optional[int] = None
    step_category: str
    is_delivery_milestone: bool = False
    integration_id: Optional[int] = None


@router.post("/workflows")
async def create_workflow(
    create_data: WorkflowCreateRequest,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Create a new workflow"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import Workflow
            from datetime import datetime

            # Validate single delivery milestone constraint
            if create_data.is_delivery_milestone:
                existing_milestone = session.query(Workflow).filter(
                    Workflow.client_id == user.client_id,
                    Workflow.integration_id == create_data.integration_id,
                    Workflow.is_delivery_milestone == True,
                    Workflow.active == True
                ).first()

                if existing_milestone:
                    integration_name = "All Integrations" if create_data.integration_id is None else f"Integration ID {create_data.integration_id}"
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"A delivery milestone already exists for {integration_name}. Only one delivery milestone is allowed per client/integration combination."
                    )

            # Create new workflow
            new_workflow = Workflow(
                step_name=create_data.step_name,
                step_number=create_data.step_number,
                step_category=create_data.step_category,
                is_delivery_milestone=create_data.is_delivery_milestone,
                integration_id=create_data.integration_id,
                client_id=user.client_id,
                active=True,
                created_at=datetime.utcnow(),
                last_updated_at=datetime.utcnow()
            )

            session.add(new_workflow)
            session.commit()

            logger.info(f"Admin {user.email} created workflow {new_workflow.id}")

            return {"message": "Workflow created successfully", "id": new_workflow.id}

    except Exception as e:
        logger.error(f"Error creating workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workflow"
        )


@router.patch("/workflows/{workflow_id}/deactivate")
async def deactivate_workflow(
    workflow_id: int,
    deactivation_data: WorkflowDeactivationRequest,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Deactivate a workflow with options for handling dependencies"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import Workflow, StatusMapping

            # Verify workflow exists and belongs to user's client
            workflow = session.query(Workflow).filter(
                Workflow.id == workflow_id,
                Workflow.client_id == user.client_id
            ).first()

            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found"
                )

            # Store original active state for messaging
            was_originally_active = workflow.active

            # Allow reassignment for inactive workflows (needed for deletion workflow)
            # Only block if trying to deactivate an already inactive workflow without reassignment
            if not workflow.active and deactivation_data.action != "reassign_mappings":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Workflow is already inactive"
                )

            # Get dependent status mappings
            dependent_mappings = session.query(StatusMapping).filter(
                StatusMapping.workflow_id == workflow_id,
                StatusMapping.active == True
            ).all()

            # Handle dependencies based on user choice
            if deactivation_data.action == "reassign_mappings":
                if not deactivation_data.target_workflow_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Target workflow ID required for reassignment"
                    )

                # Verify target workflow exists and is active
                target_workflow = session.query(Workflow).filter(
                    Workflow.id == deactivation_data.target_workflow_id,
                    Workflow.active == True,
                    Workflow.client_id == user.client_id
                ).first()

                if not target_workflow:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Target workflow (ID: {deactivation_data.target_workflow_id}) not found or is inactive. Please select an active workflow for reassignment."
                    )

                # Reassign all dependent mappings
                for mapping in dependent_mappings:
                    mapping.workflow_id = deactivation_data.target_workflow_id

                if was_originally_active:
                    message = f"Workflow deactivated and {len(dependent_mappings)} status mappings reassigned to '{target_workflow.step_name}'"
                    logger.info(f"Admin {user.email} deactivated workflow {workflow_id} and reassigned {len(dependent_mappings)} mappings to {target_workflow.step_name}")
                else:
                    message = f"{len(dependent_mappings)} status mappings reassigned to '{target_workflow.step_name}' (workflow was already inactive)"
                    logger.info(f"Admin {user.email} reassigned {len(dependent_mappings)} mappings from inactive workflow {workflow_id} to {target_workflow.step_name}")

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


@router.patch("/workflows/{workflow_id}/toggle-active")
async def toggle_workflow_active(
    workflow_id: int,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Toggle the active status of a workflow (simple activate/deactivate)"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import Workflow

            # Verify workflow exists and belongs to user's client
            workflow = session.query(Workflow).filter(
                Workflow.id == workflow_id,
                Workflow.client_id == user.client_id
            ).first()

            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found"
                )

            # Toggle active status
            workflow.active = not workflow.active
            action = "activated" if workflow.active else "deactivated"

            session.commit()

            logger.info(f"Admin {user.email} {action} workflow {workflow_id} ({workflow.step_name})")

            return {
                "message": f"Workflow {action} successfully",
                "active": workflow.active,
                "workflow_step_name": workflow.step_name
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling workflow active status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle workflow status"
        )


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: int,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Delete a workflow (only allows true deletion when no dependencies exist)"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import Workflow, StatusMapping

            workflow = session.query(Workflow).filter(
                Workflow.id == workflow_id,
                Workflow.client_id == user.client_id
            ).first()

            if not workflow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow not found"
                )

            # Check for dependent status mappings (both active and inactive)
            dependent_mappings = session.query(StatusMapping).filter(
                StatusMapping.workflow_id == workflow_id
            ).count()

            if dependent_mappings > 0:
                # Block deletion if dependencies exist
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete workflow: {dependent_mappings} status mappings depend on it. Use 'Deactivate' instead or reassign dependencies first."
                )

            # Safe to delete - no dependencies
            session.delete(workflow)
            session.commit()

            logger.info(f"Admin {user.email} deleted workflow {workflow_id} ({workflow.step_name}) - no dependencies")

            return {"message": f"Workflow '{workflow.step_name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete workflow"
        )


@router.get("/workflows/integrations")
async def get_workflow_integrations(
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get available integrations for workflow assignment"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import Integration

            integrations = session.query(Integration).filter(
                Integration.client_id == user.client_id,
                Integration.active == True
            ).order_by(Integration.name).all()

            return [
                {
                    "id": integration.id,
                    "name": integration.name
                }
                for integration in integrations
            ]
    except Exception as e:
        logger.error(f"Error fetching workflow integrations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch integrations"
        )


@router.get("/issuetype-mappings")
async def get_issuetype_mappings(
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get all issue type mappings"""
    try:
        database = get_database()
        with database.get_session() as session:
            # Query issue type mappings with hierarchy information
            from app.models.unified_models import IssuetypeMapping, IssuetypeHierarchy

            issuetype_mappings = session.query(
                IssuetypeMapping,
                IssuetypeHierarchy.level_name.label('hierarchy_name'),
                IssuetypeHierarchy.level_number.label('hierarchy_level'),
                IssuetypeHierarchy.description.label('hierarchy_description')
            ).join(
                IssuetypeHierarchy, IssuetypeMapping.issuetype_hierarchy_id == IssuetypeHierarchy.id
            ).order_by(
                IssuetypeHierarchy.level_number.desc(),  # Order by hierarchy level descending (highest first)
                IssuetypeMapping.issuetype_from
            ).all()

            return [
                {
                    "id": mapping.IssuetypeMapping.id,
                    "issuetype_from": mapping.IssuetypeMapping.issuetype_from,
                    "issuetype_to": mapping.IssuetypeMapping.issuetype_to,
                    "hierarchy_level": mapping.hierarchy_level,
                    "hierarchy_name": mapping.hierarchy_name,
                    "hierarchy_description": mapping.hierarchy_description,
                    "issuetype_hierarchy_id": mapping.IssuetypeMapping.issuetype_hierarchy_id,
                    "active": mapping.IssuetypeMapping.active
                }
                for mapping in issuetype_mappings
            ]
    except Exception as e:
        logger.error(f"Error fetching issue type mappings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issue type mappings"
        )


@router.patch("/issuetype-mappings/{mapping_id}/activate")
async def activate_issuetype_mapping(
    mapping_id: int,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Activate an issue type mapping"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import IssuetypeMapping
            from datetime import datetime

            mapping = session.query(IssuetypeMapping).filter(
                IssuetypeMapping.id == mapping_id,
                IssuetypeMapping.client_id == user.client_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Issue type mapping not found"
                )

            mapping.active = True
            mapping.last_updated_at = datetime.utcnow()
            session.commit()

            logger.info(f"Admin {user.email} activated issue type mapping {mapping_id}")

            return {"message": "Issue type mapping activated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating issue type mapping {mapping_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate issue type mapping"
        )


class IssuetypeMappingDeactivationRequest(BaseModel):
    action: str  # "keep_issuetypes", "reassign_issuetypes"
    target_mapping_id: Optional[int] = None  # Required if action is "reassign_issuetypes"


@router.patch("/issuetype-mappings/{mapping_id}/deactivate")
async def deactivate_issuetype_mapping(
    mapping_id: int,
    deactivation_data: IssuetypeMappingDeactivationRequest,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Deactivate an issue type mapping with options for handling dependencies"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import IssuetypeMapping, Issuetype
            from datetime import datetime

            # Verify mapping exists and belongs to user's client
            mapping = session.query(IssuetypeMapping).filter(
                IssuetypeMapping.id == mapping_id,
                IssuetypeMapping.client_id == user.client_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Issue type mapping not found"
                )

            # Store original active state for messaging
            was_originally_active = mapping.active

            # Allow reassignment for inactive mappings (needed for deletion workflow)
            # Only block if trying to deactivate an already inactive mapping without reassignment
            if not mapping.active and deactivation_data.action != "reassign_issuetypes":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Issue type mapping is already inactive"
                )

            # Get dependent issue types
            dependent_issuetypes = session.query(Issuetype).filter(
                Issuetype.issuetype_mapping_id == mapping_id,
                Issuetype.active == True
            ).all()

            # Handle dependencies based on user choice
            if deactivation_data.action == "reassign_issuetypes":
                if not deactivation_data.target_mapping_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Target mapping ID required for reassignment"
                    )

                # Verify target mapping exists and is active
                target_mapping = session.query(IssuetypeMapping).filter(
                    IssuetypeMapping.id == deactivation_data.target_mapping_id,
                    IssuetypeMapping.active == True,
                    IssuetypeMapping.client_id == user.client_id
                ).first()

                if not target_mapping:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Target mapping (ID: {deactivation_data.target_mapping_id}) not found or is inactive. Please select an active mapping for reassignment."
                    )

                # Reassign all dependent issue types
                for issuetype in dependent_issuetypes:
                    issuetype.issuetype_mapping_id = deactivation_data.target_mapping_id

                if was_originally_active:
                    message = f"Issue type mapping deactivated and {len(dependent_issuetypes)} issue types reassigned to '{target_mapping.issuetype_to}'"
                    logger.info(f"Admin {user.email} deactivated mapping {mapping_id} and reassigned {len(dependent_issuetypes)} issue types to {target_mapping.issuetype_to}")
                else:
                    message = f"{len(dependent_issuetypes)} issue types reassigned to '{target_mapping.issuetype_to}' (mapping was already inactive)"
                    logger.info(f"Admin {user.email} reassigned {len(dependent_issuetypes)} issue types from inactive mapping {mapping_id} to {target_mapping.issuetype_to}")

            elif deactivation_data.action == "keep_issuetypes":
                message = f"Issue type mapping deactivated ({len(dependent_issuetypes)} issue types will continue to reference this inactive mapping)"
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


@router.post("/issuetype-mappings")
async def create_issuetype_mapping(
    create_data: dict,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Create a new issue type mapping"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import IssuetypeMapping, IssuetypeHierarchy
            from datetime import datetime

            # Validate hierarchy level exists and is active
            hierarchy = session.query(IssuetypeHierarchy).filter(
                IssuetypeHierarchy.level_number == create_data['hierarchy_level'],
                IssuetypeHierarchy.client_id == user.client_id,
                IssuetypeHierarchy.active == True
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Active hierarchy level {create_data['hierarchy_level']} not found"
                )

            # Check for duplicate mapping
            existing = session.query(IssuetypeMapping).filter(
                IssuetypeMapping.issuetype_from == create_data['issuetype_from'],
                IssuetypeMapping.client_id == user.client_id
            ).first()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mapping for this issue type already exists"
                )

            # Create new mapping
            new_mapping = IssuetypeMapping(
                issuetype_from=create_data['issuetype_from'],
                issuetype_to=create_data['issuetype_to'],
                issuetype_hierarchy_id=hierarchy.id,
                client_id=user.client_id,
                active=True,
                created_at=datetime.utcnow(),
                last_updated_at=datetime.utcnow()
            )

            session.add(new_mapping)
            session.commit()

            logger.info(f"Admin {user.email} created issue type mapping {new_mapping.id}")

            return {"message": "Issue type mapping created successfully", "id": new_mapping.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating issue type mapping: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create issue type mapping"
        )


@router.put("/issuetype-mappings/{mapping_id}")
async def update_issuetype_mapping(
    mapping_id: int,
    update_data: dict,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Update an issue type mapping"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import IssuetypeMapping, IssuetypeHierarchy
            from datetime import datetime

            mapping = session.query(IssuetypeMapping).filter(
                IssuetypeMapping.id == mapping_id,
                IssuetypeMapping.client_id == user.client_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Issue type mapping not found"
                )

            # Validate hierarchy level exists and is active
            hierarchy = session.query(IssuetypeHierarchy).filter(
                IssuetypeHierarchy.level_number == update_data['hierarchy_level'],
                IssuetypeHierarchy.client_id == user.client_id,
                IssuetypeHierarchy.active == True
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Active hierarchy level {update_data['hierarchy_level']} not found"
                )

            # Check for duplicate mapping (excluding current one)
            existing = session.query(IssuetypeMapping).filter(
                IssuetypeMapping.issuetype_from == update_data['issuetype_from'],
                IssuetypeMapping.client_id == user.client_id,
                IssuetypeMapping.id != mapping_id
            ).first()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mapping for this issue type already exists"
                )

            # Update mapping
            mapping.issuetype_from = update_data['issuetype_from']
            mapping.issuetype_to = update_data['issuetype_to']
            mapping.issuetype_hierarchy_id = hierarchy.id
            mapping.last_updated_at = datetime.utcnow()

            session.commit()

            logger.info(f"Admin {user.email} updated issue type mapping {mapping_id}")

            return {"message": "Issue type mapping updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating issue type mapping {mapping_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update issue type mapping"
        )


@router.delete("/issuetype-mappings/{mapping_id}")
async def delete_issuetype_mapping(
    mapping_id: int,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Delete an issue type mapping"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import IssuetypeMapping, Issue

            mapping = session.query(IssuetypeMapping).filter(
                IssuetypeMapping.id == mapping_id,
                IssuetypeMapping.client_id == user.client_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Issue type mapping not found"
                )

            # Check for dependent issue types and issues (using correct relationship)
            from app.models.unified_models import Issuetype

            # Count dependent issue types
            dependent_issuetypes = session.query(Issuetype).filter(
                Issuetype.issuetype_mapping_id == mapping_id,
                Issuetype.active == True
            ).count()

            # Count dependent issues through issue types
            dependent_issues = session.query(Issue).join(
                Issuetype, Issue.issuetype_id == Issuetype.id
            ).filter(
                Issuetype.issuetype_mapping_id == mapping_id,
                Issuetype.active == True,
                Issue.active == True
            ).count()

            if dependent_issuetypes > 0 or dependent_issues > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete mapping: {dependent_issuetypes} active issue types and {dependent_issues} active issues are using this mapping. Use 'Deactivate' instead or reassign dependencies first."
                )

            # Delete the mapping
            session.delete(mapping)
            session.commit()

            logger.info(f"Admin {user.email} deleted issue type mapping {mapping_id}")

            return {"message": "Issue type mapping deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting issue type mapping {mapping_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete issue type mapping"
        )


@router.get("/issuetype-mappings/{mapping_id}/dependencies")
async def get_issuetype_mapping_dependencies(
    mapping_id: int,
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get dependencies for an issue type mapping"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import IssuetypeMapping, Issue, Issuetype

            mapping = session.query(IssuetypeMapping).filter(
                IssuetypeMapping.id == mapping_id,
                IssuetypeMapping.client_id == user.client_id
            ).first()

            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Issue type mapping not found"
                )

            # Count dependent issue types that use this mapping
            dependent_issuetypes_count = session.query(Issuetype).filter(
                Issuetype.issuetype_mapping_id == mapping_id,
                Issuetype.active == True
            ).count()

            # Count dependent issues through the issue types
            dependent_issues_count = session.query(Issue).join(
                Issuetype, Issue.issuetype_id == Issuetype.id
            ).filter(
                Issuetype.issuetype_mapping_id == mapping_id,
                Issuetype.active == True,
                Issue.active == True
            ).count()

            # Get available reassignment targets (active issue type mappings, excluding current)
            reassignment_targets = session.query(IssuetypeMapping).filter(
                IssuetypeMapping.active == True,
                IssuetypeMapping.id != mapping_id,
                IssuetypeMapping.client_id == user.client_id
            ).order_by(IssuetypeMapping.issuetype_to).all()

            # Get detailed dependency information
            dependent_issuetypes = session.query(Issuetype).filter(
                Issuetype.issuetype_mapping_id == mapping_id,
                Issuetype.active == True
            ).all()

            issuetype_details = []
            for issuetype in dependent_issuetypes:
                # Count issues for this issuetype
                issue_count = session.query(Issue).filter(
                    Issue.issuetype_id == issuetype.id,
                    Issue.active == True
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
                    "issuetype_from": mapping.issuetype_from,
                    "issuetype_to": mapping.issuetype_to,
                    "hierarchy_level": mapping.issuetype_hierarchy.level_number if mapping.issuetype_hierarchy else None
                },
                "can_delete_safely": dependent_issuetypes_count == 0 and dependent_issues_count == 0,
                "dependent_issuetypes_count": dependent_issuetypes_count,
                "dependent_issues_count": dependent_issues_count,
                "has_dependencies": dependent_issuetypes_count > 0 or dependent_issues_count > 0,
                "dependent_issuetypes": issuetype_details,
                "reassignment_targets": [
                    {
                        "id": target.id,
                        "issuetype_from": target.issuetype_from,
                        "issuetype_to": target.issuetype_to,
                        "hierarchy_level": target.issuetype_hierarchy.level_number if target.issuetype_hierarchy else None
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


@router.get("/issuetype-hierarchies")
async def get_issuetype_hierarchies(user: User = Depends(require_permission("admin_panel", "read"))):
    """Get all issue type hierarchies"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import IssuetypeHierarchy

            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            hierarchies = session.query(IssuetypeHierarchy).filter(
                IssuetypeHierarchy.client_id == user.client_id
            ).order_by(IssuetypeHierarchy.level_number.desc()).all()

            return [
                {
                    "id": hierarchy.id,
                    "level_name": hierarchy.level_name,
                    "level_number": hierarchy.level_number,
                    "description": hierarchy.description,
                    "active": hierarchy.active
                }
                for hierarchy in hierarchies
            ]

    except Exception as e:
        logger.error(f"Error fetching issue type hierarchies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issue type hierarchies"
        )


class IssuetypeHierarchyCreateRequest(BaseModel):
    level_name: str
    level_number: int
    description: Optional[str] = None


class IssuetypeHierarchyUpdateRequest(BaseModel):
    level_name: str
    level_number: int
    description: Optional[str] = None


@router.post("/issuetype-hierarchies")
async def create_issuetype_hierarchy(
    create_data: IssuetypeHierarchyCreateRequest,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Create a new issuetype hierarchy"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import IssuetypeHierarchy
            from datetime import datetime

            # Note: Multiple hierarchies can have the same level_number
            # No uniqueness check needed for level_number

            # Create new hierarchy
            new_hierarchy = IssuetypeHierarchy(
                level_name=create_data.level_name,
                level_number=create_data.level_number,
                description=create_data.description,
                client_id=user.client_id,
                active=True,
                created_at=datetime.utcnow(),
                last_updated_at=datetime.utcnow()
            )

            session.add(new_hierarchy)
            session.commit()

            logger.info(f"Admin {user.email} created issuetype hierarchy {new_hierarchy.id}")

            return {"message": "Issuetype hierarchy created successfully", "id": new_hierarchy.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating issuetype hierarchy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create issuetype hierarchy"
        )


@router.put("/issuetype-hierarchies/{hierarchy_id}")
async def update_issuetype_hierarchy(
    hierarchy_id: int,
    update_data: IssuetypeHierarchyUpdateRequest,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Update an issuetype hierarchy"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import IssuetypeHierarchy
            from datetime import datetime

            hierarchy = session.query(IssuetypeHierarchy).filter(
                IssuetypeHierarchy.id == hierarchy_id,
                IssuetypeHierarchy.client_id == user.client_id
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Issuetype hierarchy not found"
                )

            # Check if level_number conflicts with another hierarchy
            if update_data.level_number != hierarchy.level_number:
                existing = session.query(IssuetypeHierarchy).filter(
                    IssuetypeHierarchy.level_number == update_data.level_number,
                    IssuetypeHierarchy.client_id == user.client_id,
                    IssuetypeHierarchy.id != hierarchy_id
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
            hierarchy.last_updated_at = datetime.utcnow()

            session.commit()

            logger.info(f"Admin {user.email} updated issuetype hierarchy {hierarchy_id}")

            return {"message": "Issuetype hierarchy updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating issuetype hierarchy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update issuetype hierarchy"
        )


@router.delete("/issuetype-hierarchies/{hierarchy_id}")
async def delete_issuetype_hierarchy(
    hierarchy_id: int,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Delete an issuetype hierarchy"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import IssuetypeHierarchy, IssuetypeMapping

            hierarchy = session.query(IssuetypeHierarchy).filter(
                IssuetypeHierarchy.id == hierarchy_id,
                IssuetypeHierarchy.client_id == user.client_id
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Issuetype hierarchy not found"
                )

            # Check if hierarchy is being used by any mappings
            mappings_count = session.query(IssuetypeMapping).filter(
                IssuetypeMapping.issuetype_hierarchy_id == hierarchy_id
            ).count()

            if mappings_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete hierarchy: {mappings_count} issue type mappings are using this hierarchy"
                )

            session.delete(hierarchy)
            session.commit()

            logger.info(f"Admin {user.email} deleted issuetype hierarchy {hierarchy_id}")

            return {"message": "Issuetype hierarchy deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting issuetype hierarchy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete issuetype hierarchy"
        )


@router.get("/issuetype-hierarchies/{hierarchy_id}/dependencies")
async def get_issuetype_hierarchy_dependencies(
    hierarchy_id: int,
    user: User = Depends(require_permission("admin_panel", "read"))
):
    """Get dependencies for an issue type hierarchy"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import IssuetypeHierarchy, IssuetypeMapping, Issue, Issuetype

            hierarchy = session.query(IssuetypeHierarchy).filter(
                IssuetypeHierarchy.id == hierarchy_id,
                IssuetypeHierarchy.client_id == user.client_id
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Issue type hierarchy not found"
                )

            # Count dependent mappings that use this hierarchy
            dependent_mappings_count = session.query(IssuetypeMapping).filter(
                IssuetypeMapping.issuetype_hierarchy_id == hierarchy_id,
                IssuetypeMapping.active == True
            ).count()

            # Count dependent issues through the mappings and issue types
            dependent_issues_count = session.query(Issue).join(
                Issuetype, Issue.issuetype_id == Issuetype.id
            ).join(
                IssuetypeMapping, Issuetype.issuetype_mapping_id == IssuetypeMapping.id
            ).filter(
                IssuetypeMapping.issuetype_hierarchy_id == hierarchy_id,
                IssuetypeMapping.active == True,
                Issuetype.active == True,
                Issue.active == True
            ).count()

            # Get available reassignment targets (active hierarchies, excluding current)
            reassignment_targets = session.query(IssuetypeHierarchy).filter(
                IssuetypeHierarchy.active == True,
                IssuetypeHierarchy.id != hierarchy_id,
                IssuetypeHierarchy.client_id == user.client_id
            ).order_by(IssuetypeHierarchy.level_number.desc()).all()

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


class IssuetypeHierarchyDeactivationRequest(BaseModel):
    action: str  # "keep_mappings", "reassign_mappings"
    target_hierarchy_id: Optional[int] = None  # Required if action is "reassign_mappings"


@router.patch("/issuetype-hierarchies/{hierarchy_id}/deactivate")
async def deactivate_issuetype_hierarchy(
    hierarchy_id: int,
    deactivation_data: IssuetypeHierarchyDeactivationRequest,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Deactivate an issue type hierarchy with options for handling dependencies"""
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import IssuetypeHierarchy, IssuetypeMapping
            from datetime import datetime

            # Verify hierarchy exists and belongs to user's client
            hierarchy = session.query(IssuetypeHierarchy).filter(
                IssuetypeHierarchy.id == hierarchy_id,
                IssuetypeHierarchy.client_id == user.client_id
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Issue type hierarchy not found"
                )

            # Store original active state for messaging
            was_originally_active = hierarchy.active

            # Allow reassignment for inactive hierarchies (needed for deletion workflow)
            # Only block if trying to deactivate an already inactive hierarchy without reassignment
            if not hierarchy.active and deactivation_data.action != "reassign_mappings":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Issue type hierarchy is already inactive"
                )

            # Get dependent mappings
            dependent_mappings = session.query(IssuetypeMapping).filter(
                IssuetypeMapping.issuetype_hierarchy_id == hierarchy_id,
                IssuetypeMapping.active == True
            ).all()

            # Handle dependencies based on user choice
            if deactivation_data.action == "reassign_mappings":
                if not deactivation_data.target_hierarchy_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Target hierarchy ID required for reassignment"
                    )

                # Verify target hierarchy exists and is active
                target_hierarchy = session.query(IssuetypeHierarchy).filter(
                    IssuetypeHierarchy.id == deactivation_data.target_hierarchy_id,
                    IssuetypeHierarchy.active == True,
                    IssuetypeHierarchy.client_id == user.client_id
                ).first()

                if not target_hierarchy:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Target hierarchy (ID: {deactivation_data.target_hierarchy_id}) not found or is inactive. Please select an active hierarchy for reassignment."
                    )

                # Reassign all dependent mappings
                for mapping in dependent_mappings:
                    mapping.issuetype_hierarchy_id = deactivation_data.target_hierarchy_id

                if was_originally_active:
                    message = f"Issue type hierarchy deactivated and {len(dependent_mappings)} mappings reassigned to '{target_hierarchy.level_name}'"
                    logger.info(f"Admin {user.email} deactivated hierarchy {hierarchy_id} and reassigned {len(dependent_mappings)} mappings to {target_hierarchy.level_name}")
                else:
                    message = f"{len(dependent_mappings)} mappings reassigned to '{target_hierarchy.level_name}' (hierarchy was already inactive)"
                    logger.info(f"Admin {user.email} reassigned {len(dependent_mappings)} mappings from inactive hierarchy {hierarchy_id} to {target_hierarchy.level_name}")

            elif deactivation_data.action == "keep_mappings":
                message = f"Issue type hierarchy deactivated ({len(dependent_mappings)} mappings will continue to reference this inactive hierarchy)"
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


@router.patch("/issuetype-hierarchies/{hierarchy_id}/activate")
async def activate_issuetype_hierarchy(
    hierarchy_id: int,
    user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Activate an issue type hierarchy"""
    try:
        database = get_database()
        with database.get_session() as session:
            from datetime import datetime

            hierarchy = session.query(IssuetypeHierarchy).filter(
                IssuetypeHierarchy.id == hierarchy_id,
                IssuetypeHierarchy.client_id == user.client_id
            ).first()

            if not hierarchy:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Issue type hierarchy not found"
                )

            hierarchy.active = True
            hierarchy.last_updated_at = datetime.utcnow()
            session.commit()

            logger.info(f"Admin {user.email} activated hierarchy {hierarchy_id}")

            return {"message": "Issue type hierarchy activated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating hierarchy {hierarchy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate hierarchy"
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
        with database.get_session() as session:
            from app.core.utils import DateTimeHelper

            # ✅ SECURITY: Query active sessions filtered by client_id
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
                    User.client_id == user.client_id,  # Filter by client_id
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
        with database.get_session() as session:
            from app.core.utils import DateTimeHelper

            # ✅ SECURITY: Get session IDs for current client only (using join for filtering)
            session_ids_to_terminate = session.query(UserSession.id).join(User).filter(
                User.client_id == user.client_id,
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
        with database.get_session() as session:
            from app.core.utils import DateTimeHelper

            # ✅ SECURITY: Find the session to terminate (filtered by client_id)
            user_session = session.query(UserSession).join(User).filter(
                and_(
                    UserSession.id == session_id,
                    UserSession.active == True,
                    User.client_id == user.client_id  # Ensure session belongs to current client
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
        with database.get_session() as session:
            # ✅ SECURITY: Get color schema mode filtered by client_id
            mode_setting = session.query(SystemSettings).filter(
                SystemSettings.setting_key == "color_schema_mode",
                SystemSettings.client_id == user.client_id
            ).first()

            color_mode = mode_setting.setting_value if mode_setting else "default"

            # Get all custom color settings
            color_settings = {}
            for i in range(1, 6):
                setting_key = f"custom_color{i}"  # Fixed: removed underscore
                # ✅ SECURITY: Filter by client_id
                setting = session.query(SystemSettings).filter(
                    SystemSettings.setting_key == setting_key,
                    SystemSettings.client_id == user.client_id
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
        with database.get_session() as session:
            # ✅ SECURITY: Use current user's client for system settings
            # No need to query client - use user's client_id directly

            # Update each color setting
            colors = request.model_dump()
            for color_key, color_value in colors.items():
                setting_key = f"custom_{color_key}"

                # ✅ SECURITY: Get or create setting filtered by client_id
                setting = session.query(SystemSettings).filter(
                    SystemSettings.setting_key == setting_key,
                    SystemSettings.client_id == user.client_id
                ).first()

                if not setting:
                    setting = SystemSettings(
                        setting_key=setting_key,
                        setting_value=color_value,
                        setting_type='string',
                        description=f"Custom {color_key} for color schema",
                        client_id=user.client_id  # ✅ SECURITY: Use user's client_id
                    )
                    session.add(setting)
                else:
                    setting.setting_value = color_value
                    setting.last_updated_at = func.now()

            session.commit()

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
        with database.get_session() as session:
            # ✅ SECURITY: Use current user's client for system settings
            # No need to query client - use user's client_id directly

            # ✅ SECURITY: Get or create the color schema mode setting filtered by client_id
            setting = session.query(SystemSettings).filter(
                SystemSettings.setting_key == "color_schema_mode",
                SystemSettings.client_id == user.client_id
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
                    client_id=user.client_id  # ✅ SECURITY: Use user's client_id
                )
                session.add(setting)

            session.commit()

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
        with database.get_session() as session:
            # ✅ SECURITY: Get theme mode setting filtered by client_id
            setting = session.query(SystemSettings).filter(
                SystemSettings.setting_key == "theme_mode",
                SystemSettings.client_id == user.client_id
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
        with database.get_session() as session:
            # ✅ SECURITY: Get or create the theme mode setting filtered by client_id
            setting = session.query(SystemSettings).filter(
                SystemSettings.setting_key == "theme_mode",
                SystemSettings.client_id == user.client_id
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
                    client_id=user.client_id  # ✅ SECURITY: Use user's client_id
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

