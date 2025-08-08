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
from app.auth.auth_middleware import require_permission, require_authentication
from app.auth.auth_service import get_auth_service
# RBAC is centralized in Auth Service; local permissions are not used
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

class ColorSchemaRequest(BaseModel):
    colors: Dict[str, str]

class ColorSchemaModeRequest(BaseModel):
    mode: str  # "default" or "custom"

class ClientResponse(BaseModel):
    id: int
    name: str
    website: Optional[str] = None
    active: bool
    assets_folder: Optional[str] = None
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
                User.client_id == admin_user.client_id
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
                client_id=admin_user.client_id,
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
                User.client_id == admin_user.client_id
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
                User.role == 'admin'
            ).count()

            # Calculate time-based user activity metrics
            from datetime import timedelta
            from app.core.utils import DateTimeHelper
            now_utc = DateTimeHelper.now_utc()

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
                        User.client_id == client_id,
                        User.active == True,
                        UserSession.created_at >= today_start
                    ).distinct().count()

                    # Week active users (users with sessions created in last 7 days)
                    week_start = now_utc - timedelta(days=7)
                    week_active = session.query(User).join(
                        UserSession, User.id == UserSession.user_id
                    ).filter(
                        User.client_id == client_id,
                        User.active == True,
                        UserSession.created_at >= week_start
                    ).distinct().count()

                    # Month active users (users with sessions created in last 30 days)
                    month_start = now_utc - timedelta(days=30)
                    month_active = session.query(User).join(
                        UserSession, User.id == UserSession.user_id
                    ).filter(
                        User.client_id == client_id,
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
                            User.client_id == client_id,
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

            # Define all table models with client_id filtering
            table_models = {
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
                    # Handle different table types
                    if table_name in ['migration_history']:
                        # Global tables - count all records
                        count = session.query(func.count(model.id)).scalar() or 0
                    elif table_name == 'clients':
                        # Clients table - count all clients (no client_id filtering)
                        count = session.query(func.count(model.id)).scalar() or 0
                    elif table_name in ['user_sessions', 'user_permissions']:
                        # User-related tables - filter by user's client_id through user relationship
                        if table_name == 'user_sessions':
                            count = session.query(func.count(model.id)).join(
                                User, model.user_id == User.id
                            ).filter(User.client_id == client_id).scalar() or 0
                        else:  # user_permissions
                            count = session.query(func.count(model.id)).join(
                                User, model.user_id == User.id
                            ).filter(User.client_id == client_id).scalar() or 0
                    else:
                        # Standard client-specific tables
                        if hasattr(model, 'client_id'):
                            if table_name in ['projects_issuetypes', 'projects_statuses']:
                                count = session.query(model).filter(model.client_id == client_id).count() or 0
                            else:
                                count = session.query(func.count(model.id)).filter(model.client_id == client_id).scalar() or 0
                        else:
                            # Fallback for tables without client_id
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

                # Get current month and last month date ranges in UTC (database timezone)
                now = DateTimeHelper.now_utc()
                current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

                # Count records created this month vs last month for main data tables
                current_month_records = 0
                last_month_records = 0

                # Focus on main data tables that have created_at fields
                growth_tables = {
                    'issues': Issue,
                    'pull_requests': PullRequest,
                    'repositories': Repository,
                    'issue_changelogs': IssueChangelog,
                    'pull_request_comments': PullRequestComment,
                    'pull_request_commits': PullRequestCommit,
                    'pull_request_reviews': PullRequestReview,
                    'jira_pull_request_links': JiraPullRequestLinks
                }

                for table_name, model in growth_tables.items():
                    if hasattr(model, 'created_at') and hasattr(model, 'client_id'):
                        # Current month
                        current_count = session.query(func.count(model.id)).filter(
                            and_(
                                model.client_id == client_id,
                                model.created_at >= current_month_start
                            )
                        ).scalar() or 0
                        current_month_records += current_count

                        # Last month
                        last_count = session.query(func.count(model.id)).filter(
                            and_(
                                model.client_id == client_id,
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
                    "user_sessions": table_counts.get('user_sessions', 0),
                    "user_permissions": table_counts.get('user_permissions', 0),
                    "clients": table_counts.get('clients', 0),
                    "integrations": table_counts.get('integrations', 0),
                    "projects": table_counts.get('projects', 0)
                },
                "Issues & Workflow": {
                    "issues": table_counts.get('issues', 0),
                    "issue_changelogs": table_counts.get('issue_changelogs', 0),
                    "issuetypes": table_counts.get('issuetypes', 0),
                    "statuses": table_counts.get('statuses', 0),
                    "status_mappings": table_counts.get('status_mappings', 0),
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
                    "job_schedules": table_counts.get('job_schedules', 0),
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
            # ✅ SECURITY: Filter by client_id through user relationship
            active_sessions = session.query(UserSession, User).join(
                User, UserSession.user_id == User.id
            ).filter(
                User.client_id == user.client_id,
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
                User.client_id == user.client_id,
                UserSession.active == True
            ).all()

            # Extract the IDs from the result tuples
            session_ids = [session_id[0] for session_id in session_ids_to_terminate]
            terminated_count = len(session_ids)

            # Get all user IDs for the current client for Redis cleanup
            client_user_ids = session.query(User.id).filter(
                User.client_id == user.client_id
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
                User.client_id == user.client_id,
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

            # Also invalidate Redis session for immediate logout
            try:
                auth_service = get_auth_service()
                token_hash = user_session.token_hash
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
                payload = { 'token_hash': token_hash, 'client_id': user.client_id }
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

@router.get("/color-schema")
async def get_color_schema(
    user: User = Depends(require_authentication)
):
    """Get color schema settings (default/custom) with contrast-aware on-color tokens"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # ✅ SECURITY: Get color schema mode filtered by client_id
            mode_setting = session.query(SystemSettings).filter(
                SystemSettings.setting_key == "color_schema_mode",
                SystemSettings.client_id == user.client_id
            ).first()

            color_mode = mode_setting.setting_value if mode_setting else "default"

            # Load default palette from DB (centralized; no hardcoded fallbacks unless missing)
            default_colors = {}
            for i in range(1, 6):
                setting_key = f"default_color{i}"
                setting = session.query(SystemSettings).filter(
                    SystemSettings.setting_key == setting_key,
                    SystemSettings.client_id == user.client_id
                ).first()
                if setting:
                    default_colors[f"color{i}"] = setting.setting_value

            # Fallback only if defaults are missing (installation edge cases)
            if len(default_colors) < 5:
                default_colors = {
                    "color1": "#2862EB",
                    "color2": "#763DED",
                    "color3": "#059669",
                    "color4": "#0EA5E9",
                    "color5": "#F59E0B"
                }

            # Load custom palette (if any)
            custom_colors = {}
            for i in range(1, 6):
                setting_key = f"custom_color{i}"
                setting = session.query(SystemSettings).filter(
                    SystemSettings.setting_key == setting_key,
                    SystemSettings.client_id == user.client_id
                ).first()
                if setting:
                    custom_colors[f"color{i}"] = setting.setting_value

            # Active colors
            active_colors = custom_colors if color_mode == 'custom' and custom_colors else default_colors

            # Load precomputed on-color tokens for the active mode
            on_colors = {}
            on_gradients = {}
            prefix = 'custom' if color_mode == 'custom' else 'default'
            for i in range(1, 6):
                key = f"{prefix}_on_color{i}"
                setting = session.query(SystemSettings).filter(
                    SystemSettings.setting_key == key,
                    SystemSettings.client_id == user.client_id
                ).first()
                if setting:
                    on_colors[f"color{i}"] = setting.setting_value
            for pair in ["1-2", "2-3", "3-4", "4-5"]:
                key = f"{prefix}_on_gradient_{pair}"
                setting = session.query(SystemSettings).filter(
                    SystemSettings.setting_key == key,
                    SystemSettings.client_id == user.client_id
                ).first()
                if setting:
                    on_gradients[pair] = setting.setting_value

            return {
                "success": True,
                "mode": color_mode,
                "colors": active_colors,
                "default_colors": default_colors,
                "custom_colors": custom_colors,
                "on_colors": on_colors,
                "on_gradients": on_gradients
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
    user: User = Depends(require_permission("settings", "admin"))
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

            # Recompute WCAG on-color tokens for CUSTOM palette before commit
            try:
                def _hex_to_rgb(h):
                    h = h.lstrip('#')
                    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
                def _lin(c):
                    return (c/12.92) if c <= 0.03928 else ((c+0.055)/1.055) ** 2.4
                def _rel_luma(hex_color):
                    r, g, b = _hex_to_rgb(hex_color)
                    return 0.2126*_lin(r) + 0.7152*_lin(g) + 0.0722*_lin(b)
                def _contrast(bg_hex, fg_hex):
                    L1 = _rel_luma(bg_hex)
                    L2 = _rel_luma(fg_hex)
                    L_light, L_dark = (max(L1, L2), min(L1, L2))
                    return (L_light + 0.05) / (L_dark + 0.05)
                def _pick_on(bg_hex):
                    black, white = '#000000', '#FFFFFF'
                    return white if _contrast(bg_hex, white) >= _contrast(bg_hex, black) else black
                def _pick_on_pair(a_hex, b_hex):
                    black, white = '#000000', '#FFFFFF'
                    min_black = min(_contrast(a_hex, black), _contrast(b_hex, black))
                    min_white = min(_contrast(a_hex, white), _contrast(b_hex, white))
                    return white if min_white >= min_black else black

                c1 = colors.get('color1'); c2 = colors.get('color2'); c3 = colors.get('color3'); c4 = colors.get('color4'); c5 = colors.get('color5')
                if all([c1, c2, c3, c4, c5]):
                    custom_on = {'1': _pick_on(c1), '2': _pick_on(c2), '3': _pick_on(c3), '4': _pick_on(c4), '5': _pick_on(c5)}
                    custom_on_grad = {'1-2': _pick_on_pair(c1, c2), '2-3': _pick_on_pair(c2, c3), '3-4': _pick_on_pair(c3, c4), '4-5': _pick_on_pair(c4, c5)}

                    for i in ['1','2','3','4','5']:
                        key = f"custom_on_color{i}"
                        setting = session.query(SystemSettings).filter(SystemSettings.setting_key == key, SystemSettings.client_id == user.client_id).first()
                        if setting:
                            setting.setting_value = custom_on[i]
                            setting.last_updated_at = func.now()
                        else:
                            session.add(SystemSettings(setting_key=key, setting_value=custom_on[i], setting_type='string', client_id=user.client_id, description=f"WCAG on-color for custom color {i}"))
                    for pair_key, val in custom_on_grad.items():
                        key = f"custom_on_gradient_{pair_key}"
                        setting = session.query(SystemSettings).filter(SystemSettings.setting_key == key, SystemSettings.client_id == user.client_id).first()
                        if setting:
                            setting.setting_value = val
                            setting.last_updated_at = func.now()
                        else:
                            session.add(SystemSettings(setting_key=key, setting_value=val, setting_type='string', client_id=user.client_id, description=f"WCAG on-color for custom gradient {pair_key}"))
            except Exception as ce:
                logger.warning(f"Failed to recompute custom on-color tokens: {ce}")

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








# ============================================================================
# CLIENT MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/clients", response_model=List[ClientResponse])
async def get_all_clients(
    skip: int = 0,
    limit: int = 100,
    user: User = Depends(require_authentication)
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
                    assets_folder=client.assets_folder,
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
                assets_folder=new_client.assets_folder,
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
    admin_user: User = Depends(require_permission("admin_panel", "execute"))
):
    """Upload a logo for a client"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            from app.core.utils import DateTimeHelper
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

            # Validate file type - only PNG files allowed
            if logo.content_type != "image/png":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid file type. Only PNG files are allowed."
                )

            # Validate file size (max 5MB)
            file_content = await logo.read()
            if len(file_content) > 5 * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File size must be less than 5MB."
                )

            # Generate client-specific filename (always PNG)
            client_name_lower = client.name.lower()
            client_filename = f"{client_name_lower}-logo.png"

            # Create client-specific directories (relative to project root)
            # Path: services/backend-service/app/api/admin_routes.py -> go up 3 levels to project root
            project_root = Path(__file__).parent.parent.parent.parent.parent
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
            client.assets_folder = client_name_lower
            client.logo_filename = client_filename
            client.last_updated_at = DateTimeHelper.now_utc()
            session.commit()

            logger.info(f"Admin {admin_user.email} uploaded logo for client {client.name}")

            return {
                "message": "Logo uploaded successfully",
                "assets_folder": client.assets_folder,
                "logo_filename": client.logo_filename,
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
