"""
Admin Panel API Routes

Provides administrative functionality for user management, role assignment,
and system configuration. Only accessible to admin users.

CLEAN ARCHITECTURE - Backend Service Responsibilities:
- User Management (CRUD operations)
- Session Management (cross-service)
- Permission Management (role-based access control)
- System Statistics (for frontend dashboard)
- Theme/Color Settings (UI configuration)
- Client Management (CRUD + logo upload)
- Debug Endpoints (development support)

ETL-specific functionality (integrations, workflows, status mappings, issuetypes) 
is handled exclusively by the ETL service.
"""

from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
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
import httpx
import asyncio
from app.core.config import get_settings

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
settings = get_settings()


# 🚀 ETL Service Notification Functions
async def notify_etl_color_schema_change(client_id: int, colors: dict):
    """Notify ETL service of color schema changes"""
    try:
        # Get ETL service URL from configuration
        etl_url = f"{settings.ETL_SERVICE_URL}/api/v1/internal/color-schema-changed"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(etl_url, json={
                "client_id": client_id,
                "colors": colors,
                "event_type": "color_update"
            })

            if response.status_code == 200:
                logger.info(f"✅ ETL service notified of color schema change for client {client_id}")
            else:
                logger.warning(f"⚠️ ETL service notification failed: {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ Could not notify ETL service of color change: {e}")
        # Don't fail the main operation if ETL notification fails


async def notify_etl_color_schema_mode_change(client_id: int, mode: str):
    """Notify ETL service of color schema mode changes"""
    try:
        # Get ETL service URL from configuration
        etl_url = f"{settings.ETL_SERVICE_URL}/api/v1/internal/color-schema-mode-changed"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(etl_url, json={
                "client_id": client_id,
                "mode": mode,
                "event_type": "mode_update"
            })

            if response.status_code == 200:
                logger.info(f"✅ ETL service notified of color schema mode change for client {client_id}")
            else:
                logger.warning(f"⚠️ ETL service mode notification failed: {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ Could not notify ETL service of mode change: {e}")
        # Don't fail the main operation if ETL notification fails


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    active: bool
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None

class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    role: str

class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    active: Optional[bool] = None

class DatabaseStats(BaseModel):
    database_size: str
    table_count: int
    total_records: int

class UserStats(BaseModel):
    total_users: int
    active_users: int
    logged_users: int
    admin_users: int

class SystemStatsResponse(BaseModel):
    database: DatabaseStats
    users: UserStats
    tables: Dict[str, int]

class ActiveSessionResponse(BaseModel):
    id: int
    user_id: int
    user_email: str
    created_at: str
    last_activity_at: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class ColorSchemaRequest(BaseModel):
    colors: Dict[str, str]

class ColorSchemaModeRequest(BaseModel):
    mode: str  # "default" or "custom"

class ThemeModeRequest(BaseModel):
    mode: str  # "light" or "dark"

class ClientResponse(BaseModel):
    id: int
    name: str
    website: Optional[str] = None
    active: bool
    logo_filename: Optional[str] = None

class ClientCreateRequest(BaseModel):
    name: str
    website: Optional[str] = None
    active: Optional[bool] = None

class ClientUpdateRequest(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    active: Optional[bool] = None

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
            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            users = session.query(User).filter(
                User.client_id == user.client_id
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
                User.client_id == admin_user.client_id
            ).first()

            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User with this email already exists"
                )

            # Validate role
            try:
                role_enum = Role(user_data.role)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role: {user_data.role}"
                )

            # Hash password
            auth_service = get_auth_service()
            hashed_password = auth_service.hash_password(user_data.password)

            # Create new user
            new_user = User(
                email=user_data.email,
                password_hash=hashed_password,
                role=role_enum,
                client_id=admin_user.client_id,
                active=True,
                created_at=DateTimeHelper.utcnow(),
                last_login_at=None
            )

            session.add(new_user)
            session.commit()

            logger.info(f"Admin {admin_user.email} created user {new_user.email}")

            return UserResponse(
                id=new_user.id,
                email=new_user.email,
                role=new_user.role.value,
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
                User.client_id == admin_user.client_id
            ).first()

            if not user_to_update:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Update fields if provided
            if user_data.email is not None:
                # Check if email is already taken by another user
                existing_user = session.query(User).filter(
                    User.email == user_data.email,
                    User.client_id == admin_user.client_id,
                    User.id != user_id
                ).first()

                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already taken by another user"
                    )
                user_to_update.email = user_data.email

            if user_data.role is not None:
                try:
                    role_enum = Role(user_data.role)
                    user_to_update.role = role_enum
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid role: {user_data.role}"
                    )

            if user_data.active is not None:
                user_to_update.active = user_data.active

            session.commit()

            logger.info(f"Admin {admin_user.email} updated user {user_to_update.email}")

            return UserResponse(
                id=user_to_update.id,
                email=user_to_update.email,
                role=user_to_update.role.value,
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
                User.client_id == admin_user.client_id
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
            # ✅ SECURITY: All counts filtered by client_id
            client_id = admin_user.client_id

            # Count users
            total_users = session.query(User).filter(
                User.client_id == client_id
            ).count()

            active_users = session.query(User).filter(
                User.client_id == client_id,
                User.active == True
            ).count()

            # Count logged users (active sessions)
            logged_users = session.query(UserSession).join(
                User, UserSession.user_id == User.id
            ).filter(
                User.client_id == client_id,
                UserSession.active == True
            ).count()

            # Count admin users
            admin_users = session.query(User).filter(
                User.client_id == client_id,
                User.role == Role.ADMIN
            ).count()

            # Get table counts for this client
            table_counts = {}

            # Count integrations
            table_counts['integrations'] = session.query(Integration).filter(
                Integration.client_id == client_id
            ).count()

            # Count projects
            table_counts['projects'] = session.query(Project).filter(
                Project.client_id == client_id
            ).count()

            # Count issues
            table_counts['issues'] = session.query(Issue).filter(
                Issue.client_id == client_id
            ).count()

            # Count repositories
            table_counts['repositories'] = session.query(Repository).filter(
                Repository.client_id == client_id
            ).count()

            # Count pull requests
            table_counts['pull_requests'] = session.query(PullRequest).filter(
                PullRequest.client_id == client_id
            ).count()

            # Calculate total records
            total_records = sum(table_counts.values()) + total_users

            # Database stats (simplified for now)
            database_stats = DatabaseStats(
                database_size="N/A",  # Would need database-specific queries
                table_count=len(table_counts) + 1,  # +1 for users table
                total_records=total_records
            )

            user_stats = UserStats(
                total_users=total_users,
                active_users=active_users,
                logged_users=logged_users,
                admin_users=admin_users
            )

            return SystemStatsResponse(
                database=database_stats,
                users=user_stats,
                tables=table_counts
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
                "created_at": user_session.created_at.isoformat() if user_session.created_at else None,
                "last_activity_at": user_session.last_activity_at.isoformat() if user_session.last_activity_at else None,
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
            # ✅ SECURITY: Filter by client_id through user relationship
            active_sessions = session.query(UserSession, User).join(
                User, UserSession.user_id == User.id
            ).filter(
                User.client_id == user.client_id,
                UserSession.active == True
            ).all()

            return [
                ActiveSessionResponse(
                    id=user_session.id,
                    user_id=user_session.user_id,
                    user_email=user_obj.email,
                    created_at=user_session.created_at.isoformat() if user_session.created_at else "",
                    last_activity_at=user_session.last_activity_at.isoformat() if user_session.last_activity_at else "",
                    ip_address=user_session.ip_address,
                    user_agent=user_session.user_agent
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

            # ✅ SECURITY: Only terminate sessions for users in the same client
            terminated_count = session.query(UserSession).join(
                User, UserSession.user_id == User.id
            ).filter(
                User.client_id == user.client_id,
                UserSession.active == True
            ).update({
                UserSession.active: False,
                UserSession.terminated_at: DateTimeHelper.utcnow()
            }, synchronize_session=False)

            session.commit()

            logger.info(f"Admin {user.email} terminated {terminated_count} active sessions")

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

            # Find the session and verify it belongs to the same client
            user_session = session.query(UserSession).join(
                User, UserSession.user_id == User.id
            ).filter(
                UserSession.id == session_id,
                User.client_id == user.client_id,
                UserSession.active == True
            ).first()

            if not user_session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found or already terminated"
                )

            # Terminate the session
            user_session.active = False
            user_session.terminated_at = DateTimeHelper.utcnow()
            session.commit()

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


# ============================================================================
# THEME/COLOR SETTINGS ENDPOINTS
# ============================================================================

@router.get("/color-schema")
async def get_color_schema(
    user: User = Depends(require_permission(Resource.SETTINGS, Action.READ))
):
    """Get custom color schema settings"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
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
                color_setting = session.query(SystemSettings).filter(
                    SystemSettings.setting_key == setting_key,
                    SystemSettings.client_id == user.client_id
                ).first()

                if color_setting:
                    color_settings[f"color{i}"] = color_setting.setting_value

            # Default colors if none are set
            default_colors = {
                "color1": "#C8102E",  # Primary
                "color2": "#253746",  # Secondary
                "color3": "#00C7B1",  # Accent
                "color4": "#A2DDF8",  # Neutral
                "color5": "#FFBF3F"   # Warning
            }

            # Merge with defaults
            final_colors = {**default_colors, **color_settings}

            return {
                "success": True,
                "mode": color_mode,
                "colors": final_colors
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
            # No need to query client - use user's client_id directly

            # Update each color setting
            colors = request.colors
            for color_key, color_value in colors.items():
                setting_key = f"custom_{color_key}"

                # ✅ SECURITY: Get or create setting filtered by client_id
                setting = session.query(SystemSettings).filter(
                    SystemSettings.setting_key == setting_key,
                    SystemSettings.client_id == user.client_id
                ).first()

                if setting:
                    setting.setting_value = color_value
                    setting.last_updated_at = func.now()
                else:
                    new_setting = SystemSettings(
                        setting_key=setting_key,
                        setting_value=color_value,
                        setting_type='string',
                        client_id=user.client_id,
                        description=f"Custom color setting for {color_key}"
                    )
                    session.add(new_setting)

            # Set color schema mode to custom
            mode_setting = session.query(SystemSettings).filter(
                SystemSettings.setting_key == "color_schema_mode",
                SystemSettings.client_id == user.client_id
            ).first()

            if mode_setting:
                mode_setting.setting_value = "custom"
                mode_setting.last_updated_at = func.now()
            else:
                new_mode_setting = SystemSettings(
                    setting_key="color_schema_mode",
                    setting_value="custom",
                    setting_type='string',
                    client_id=user.client_id,
                    description="Color schema mode (default or custom)"
                )
                session.add(new_mode_setting)

            session.commit()

            # Notify ETL service of color schema change
            await notify_etl_color_schema_change(user.client_id, colors)

            logger.info(f"User {user.email} updated color schema")

            return {"message": "Color schema updated successfully"}

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

            # 🚀 NEW: Notify ETL service of color schema mode change
            await notify_etl_color_schema_mode_change(user.client_id, request.mode)

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


@router.get("/theme-mode")
async def get_theme_mode(
    user: User = Depends(require_permission(Resource.SETTINGS, Action.READ))
):
    """Get the current theme mode for the client"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # ✅ SECURITY: Filter by client_id
            theme_setting = session.query(SystemSettings).filter(
                SystemSettings.setting_key == "theme_mode",
                SystemSettings.client_id == user.client_id
            ).first()

            theme_mode = theme_setting.setting_value if theme_setting else "light"

            return {
                "success": True,
                "mode": theme_mode
            }

    except Exception as e:
        logger.error(f"Error fetching theme mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch theme mode"
        )


@router.post("/theme-mode")
async def update_theme_mode(
    request: ThemeModeRequest,
    user: User = Depends(require_permission(Resource.SETTINGS, Action.ADMIN))
):
    """Update the theme mode for the client"""
    try:
        # Validate theme mode
        if request.mode not in ["light", "dark"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Theme mode must be 'light' or 'dark'"
            )

        database = get_database()
        with database.get_write_session_context() as session:
            # ✅ SECURITY: Get or create the theme mode setting filtered by client_id
            setting = session.query(SystemSettings).filter(
                SystemSettings.setting_key == "theme_mode",
                SystemSettings.client_id == user.client_id
            ).first()

            if setting:
                setting.setting_value = request.mode
                setting.last_updated_at = func.now()
            else:
                new_setting = SystemSettings(
                    setting_key="theme_mode",
                    setting_value=request.mode,
                    setting_type='string',
                    client_id=user.client_id,
                    description="Theme mode (light or dark)"
                )
                session.add(new_setting)

            session.commit()

            logger.info(f"User {user.email} updated theme mode to {request.mode}")

            return {"message": f"Theme mode updated to {request.mode}"}

    except Exception as e:
        logger.error(f"Error updating theme mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update theme mode"
        )


# ============================================================================
# CLIENT MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/clients", response_model=List[ClientResponse])
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
            clients = session.query(Client).filter(
                Client.id == user.client_id
            ).offset(skip).limit(limit).all()

            return [
                ClientResponse(
                    id=client.id,
                    name=client.name,
                    website=client.website,
                    active=client.active,
                    logo_filename=client.logo_filename
                )
                for client in clients
            ]
    except Exception as e:
        logger.error(f"Error fetching clients: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch clients"
        )


@router.post("/clients", response_model=ClientResponse)
async def create_client(
    client_data: ClientCreateRequest,
    admin_user: User = Depends(require_permission("admin_panel", "execute"))
):
    """Create a new client"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Check if client name already exists
            existing_client = session.query(Client).filter(
                Client.name == client_data.name
            ).first()

            if existing_client:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Client with this name already exists"
                )

            # Create new client
            new_client = Client(
                name=client_data.name,
                website=client_data.website,
                active=client_data.active if client_data.active is not None else True,
                created_at=DateTimeHelper.utcnow(),
                last_updated_at=DateTimeHelper.utcnow()
            )

            session.add(new_client)
            session.commit()

            logger.info(f"Admin {admin_user.email} created client {new_client.name}")

            return ClientResponse(
                id=new_client.id,
                name=new_client.name,
                website=new_client.website,
                active=new_client.active,
                logo_filename=new_client.logo_filename
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create client"
        )


@router.put("/clients/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    client_data: ClientUpdateRequest,
    admin_user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Update an existing client"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper

            # Find the client to update
            client_to_update = session.query(Client).filter(
                Client.id == client_id
            ).first()

            if not client_to_update:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Client not found"
                )

            # Update fields if provided
            if client_data.name is not None:
                # Check if name is already taken by another client
                existing_client = session.query(Client).filter(
                    Client.name == client_data.name,
                    Client.id != client_id
                ).first()

                if existing_client:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Name already taken by another client"
                    )
                client_to_update.name = client_data.name

            if client_data.website is not None:
                client_to_update.website = client_data.website

            if client_data.active is not None:
                client_to_update.active = client_data.active

            client_to_update.last_updated_at = DateTimeHelper.utcnow()
            session.commit()

            logger.info(f"Admin {admin_user.email} updated client {client_to_update.name}")

            return ClientResponse(
                id=client_to_update.id,
                name=client_to_update.name,
                website=client_to_update.website,
                active=client_to_update.active,
                logo_filename=client_to_update.logo_filename
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating client {client_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update client"
        )


@router.delete("/clients/{client_id}")
async def delete_client(
    client_id: int,
    admin_user: User = Depends(require_permission("admin_panel", "delete"))
):
    """Delete a client"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Find the client to delete
            client_to_delete = session.query(Client).filter(
                Client.id == client_id
            ).first()

            if not client_to_delete:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Client not found"
                )

            # Check if there are users associated with this client
            user_count = session.query(User).filter(
                User.client_id == client_id
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

            return {"message": f"Client {client_to_delete.name} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting client {client_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete client"
        )


@router.post("/clients/{client_id}/logo")
async def upload_client_logo(
    client_id: int,
    logo: UploadFile = File(...),
    admin_user: User = Depends(require_permission("admin_panel", "admin"))
):
    """Upload a logo for a client"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper
            import uuid
            from pathlib import Path

            # Find the client
            client = session.query(Client).filter(
                Client.id == client_id
            ).first()

            if not client:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Client not found"
                )

            # Validate file type
            allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
            if logo.content_type not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid file type. Only JPEG, PNG, GIF, and WebP are allowed."
                )

            # Generate unique filename
            file_extension = logo.filename.split('.')[-1] if '.' in logo.filename else 'png'
            unique_filename = f"client_{client_id}_{uuid.uuid4().hex[:8]}.{file_extension}"

            # Create directories if they don't exist
            frontend_logo_dir = Path("services/frontend-app/public/logos")
            etl_logo_dir = Path("services/etl-service/static/logos")

            frontend_logo_dir.mkdir(parents=True, exist_ok=True)
            etl_logo_dir.mkdir(parents=True, exist_ok=True)

            # Save file to both locations
            frontend_logo_path = frontend_logo_dir / unique_filename
            etl_logo_path = etl_logo_dir / unique_filename

            # Read file content
            file_content = await logo.read()

            # Write to both locations
            with open(frontend_logo_path, "wb") as f:
                f.write(file_content)

            with open(etl_logo_path, "wb") as f:
                f.write(file_content)

            # Update client record
            client.logo_filename = unique_filename
            client.last_updated_at = DateTimeHelper.utcnow()
            session.commit()

            logger.info(f"Admin {admin_user.email} uploaded logo for client {client.name}")

            return {
                "message": "Logo uploaded successfully",
                "filename": unique_filename,
                "client_id": client_id
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
