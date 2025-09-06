"""
Users API endpoints for Backend Service.
Provides read operations for users with optional ML fields support.
Note: User creation/updates are handled by the Auth Service.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel

from app.core.database import get_read_session
from app.core.logging_config import get_logger
from app.models.unified_models import User, UserSession, UserPermission
from app.auth.auth_middleware import UserData, require_authentication

router = APIRouter(prefix="/api", tags=["Users"])
logger = get_logger(__name__)


@router.get("/users")
async def get_users(
    tenant_id: int = Query(..., description="Tenant ID for data isolation"),
    include_ml_fields: bool = Query(False, description="Include ML fields in response"),
    limit: int = Query(100, le=1000, description="Maximum number of users to return"),
    offset: int = Query(0, ge=0, description="Number of users to skip for pagination"),
    search: Optional[str] = Query(None, description="Search in user name or email"),
    active_only: bool = Query(True, description="Return only active users"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get users with optional ML fields"""
    try:
        # Ensure client isolation
        if user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Tenant ID mismatch"
            )
        
        # Build query with filters
        query = db.query(User).filter(User.tenant_id == tenant_id)
        
        if active_only:
            query = query.filter(User.active == True)
            
        if search:
            query = query.filter(
                (User.name.ilike(f"%{search}%")) |
                (User.email.ilike(f"%{search}%"))
            )
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        users = query.order_by(User.email.asc()).offset(offset).limit(limit).all()
        
        # Enhanced response with optional ML fields
        result = []
        for user_obj in users:
            user_dict = user_obj.to_dict(include_ml_fields=include_ml_fields)
            # Remove sensitive fields from response
            user_dict.pop('password_hash', None)
            user_dict.pop('salt', None)
            result.append(user_dict)
        
        return {
            'users': result,
            'count': len(result),
            'total_count': total_count,
            'offset': offset,
            'limit': limit,
            'ml_fields_included': include_ml_fields,
            'filters': {
                'search': search,
                'active_only': active_only
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    include_ml_fields: bool = Query(False, description="Include ML fields in response"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get single user with optional ML fields"""
    try:
        user_obj = db.query(User).filter(
            User.id == user_id,
            User.tenant_id == user.tenant_id,
            User.active == True
        ).first()
        
        if not user_obj:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_dict = user_obj.to_dict(include_ml_fields=include_ml_fields)
        # Remove sensitive fields from response
        user_dict.pop('password_hash', None)
        user_dict.pop('salt', None)
        
        return user_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user")


@router.get("/users/me")
async def get_current_user_profile(
    include_ml_fields: bool = Query(False, description="Include ML fields in response"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get current user's profile with optional ML fields"""
    try:
        user_obj = db.query(User).filter(
            User.id == user.user_id,
            User.tenant_id == user.tenant_id,
            User.active == True
        ).first()
        
        if not user_obj:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        user_dict = user_obj.to_dict(include_ml_fields=include_ml_fields)
        # Remove sensitive fields from response
        user_dict.pop('password_hash', None)
        user_dict.pop('salt', None)
        
        return user_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching current user profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user profile")


@router.get("/users/{user_id}/sessions")
async def get_user_sessions(
    user_id: int,
    limit: int = Query(50, le=100, description="Maximum number of sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip for pagination"),
    active_only: bool = Query(True, description="Return only active sessions"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get user sessions (admin only or own sessions)"""
    try:
        # Users can only view their own sessions unless they're admin
        if user.user_id != user_id and not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Can only view own sessions"
            )
        
        # Verify user exists and belongs to same client
        user_obj = db.query(User).filter(
            User.id == user_id,
            User.tenant_id == user.tenant_id,
            User.active == True
        ).first()
        
        if not user_obj:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Build query for sessions
        query = db.query(UserSession).filter(UserSession.user_id == user_id)
        
        if active_only:
            query = query.filter(UserSession.active == True)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        sessions = query.order_by(UserSession.created_at.desc()).offset(offset).limit(limit).all()
        
        result = []
        for session in sessions:
            session_dict = session.to_dict()
            # Remove sensitive fields
            session_dict.pop('session_token', None)
            result.append(session_dict)
        
        return {
            'user_id': user_id,
            'sessions': result,
            'count': len(result),
            'total_count': total_count,
            'offset': offset,
            'limit': limit,
            'filters': {
                'active_only': active_only
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching sessions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user sessions")


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get user permissions (admin only or own permissions)"""
    try:
        # Users can only view their own permissions unless they're admin
        if user.user_id != user_id and not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Can only view own permissions"
            )
        
        # Verify user exists and belongs to same client
        user_obj = db.query(User).filter(
            User.id == user_id,
            User.tenant_id == user.tenant_id,
            User.active == True
        ).first()
        
        if not user_obj:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user permissions
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == user_id,
            UserPermission.active == True
        ).all()
        
        result = []
        for permission in permissions:
            result.append(permission.to_dict())
        
        return {
            'user_id': user_id,
            'permissions': result,
            'count': len(result)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching permissions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user permissions")


@router.get("/users/stats")
async def get_users_stats(
    tenant_id: int = Query(..., description="Tenant ID for data isolation"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_authentication)
):
    """Get user statistics for the client (admin only)"""
    try:
        # Ensure client isolation and admin access
        if user.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Tenant ID mismatch"
            )
        
        if not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Admin privileges required"
            )
        
        # Get basic stats
        total_users = db.query(func.count(User.id)).filter(
            User.tenant_id == tenant_id
        ).scalar()
        
        active_users = db.query(func.count(User.id)).filter(
            User.tenant_id == tenant_id,
            User.active == True
        ).scalar()
        
        # Get active sessions count
        active_sessions = db.query(func.count(UserSession.id)).join(User).filter(
            User.tenant_id == tenant_id,
            UserSession.active == True
        ).scalar()
        
        # Get role breakdown (if roles are stored in permissions)
        role_stats = db.query(
            UserPermission.permission_name,
            func.count(UserPermission.user_id.distinct()).label('user_count')
        ).join(User).filter(
            User.tenant_id == tenant_id,
            User.active == True,
            UserPermission.active == True
        ).group_by(UserPermission.permission_name).all()
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': total_users - active_users,
            'active_sessions': active_sessions,
            'role_breakdown': [{'role': r.permission_name, 'user_count': r.user_count} for r in role_stats],
            'tenant_id': tenant_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user statistics")
