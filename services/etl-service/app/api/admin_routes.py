"""
Admin Panel API Routes

Provides administrative functionality for user management, role assignment,
and system configuration. Only accessible to admin users.
"""

from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, EmailStr

from app.core.database import get_database
from app.models.unified_models import User, UserPermission, Integration, Project, Issue
from app.auth.auth_middleware import require_permission
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
    admin_users: int
    roles_distribution: dict
    database_stats: dict

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
    """Get all users with pagination"""
    try:
        database = get_database()
        with database.get_session() as session:
            users = session.query(User).offset(skip).limit(limit).all()

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
            user = session.query(User).filter(User.id == user_id).first()
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
    """Delete a user (soft delete by setting active=False)"""
    try:
        database = get_database()
        with database.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
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

            # Soft delete
            user.active = False
            session.commit()

            logger.info(f"Admin {admin_user.email} deleted user {user.email}")

            return {"message": "User deleted successfully"}

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
            # User statistics
            total_users = session.query(User).count()
            active_users = session.query(User).filter(User.active == True).count()
            admin_users = session.query(User).filter(User.is_admin == True, User.active == True).count()

            # Role distribution
            roles_distribution = {}
            for role in Role:
                count = session.query(User).filter(
                    User.role == role.value,
                    User.active == True
                ).count()
                roles_distribution[role.value] = count

            # Database statistics
            database_stats = {
                "integrations": session.query(func.count(Integration.id)).scalar() or 0,
                "projects": session.query(func.count(Project.id)).scalar() or 0,
                "issues": session.query(func.count(Issue.id)).scalar() or 0,
            }

            return SystemStatsResponse(
                total_users=total_users,
                active_users=active_users,
                admin_users=admin_users,
                roles_distribution=roles_distribution,
                database_stats=database_stats
            )

    except Exception as e:
        logger.error(f"Error fetching system stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch system statistics"
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


