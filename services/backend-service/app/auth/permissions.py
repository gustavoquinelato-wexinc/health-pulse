"""
Role-Based Access Control (RBAC) System

This module defines the permission system for different user roles and provides
utilities for checking permissions on resources and actions.
"""

from enum import Enum
from typing import Dict, List, Set
from sqlalchemy.orm import Session
from app.models.unified_models import User, UserPermission


class Role(str, Enum):
    """Predefined user roles"""
    ADMIN = "admin"
    USER = "user"
    VIEW = "view"


class Resource(str, Enum):
    """System resources that can be protected"""
    ETL_JOBS = "etl_jobs"
    ORCHESTRATOR = "orchestrator"
    DASHBOARDS = "dashboards"
    LOGS = "logs"
    SETTINGS = "settings"
    USERS = "users"
    INTEGRATIONS = "integrations"
    ADMIN_PANEL = "admin_panel"
    LOG_DOWNLOAD = "log_download"


class Action(str, Enum):
    """Actions that can be performed on resources"""
    READ = "read"
    EXECUTE = "execute"
    DELETE = "delete"
    ADMIN = "admin"


# Default role permissions matrix
DEFAULT_ROLE_PERMISSIONS: Dict[Role, Dict[Resource, Set[Action]]] = {
    Role.ADMIN: {
        # Admins can access and operate everything
        Resource.ETL_JOBS: {Action.READ, Action.EXECUTE, Action.DELETE, Action.ADMIN},
        Resource.ORCHESTRATOR: {Action.READ, Action.EXECUTE, Action.DELETE, Action.ADMIN},
        Resource.DASHBOARDS: {Action.READ, Action.EXECUTE, Action.DELETE, Action.ADMIN},
        Resource.LOGS: {Action.READ, Action.EXECUTE, Action.DELETE, Action.ADMIN},
        Resource.SETTINGS: {Action.READ, Action.EXECUTE, Action.DELETE, Action.ADMIN},
        Resource.USERS: {Action.READ, Action.EXECUTE, Action.DELETE, Action.ADMIN},
        Resource.INTEGRATIONS: {Action.READ, Action.EXECUTE, Action.DELETE, Action.ADMIN},
        Resource.ADMIN_PANEL: {Action.READ, Action.EXECUTE, Action.DELETE, Action.ADMIN},
        Resource.LOG_DOWNLOAD: {Action.READ, Action.EXECUTE, Action.DELETE, Action.ADMIN},
    },

    Role.USER: {
        # Users can only view status - no control actions
        Resource.ETL_JOBS: {Action.READ},  # View status only, no control
        Resource.ORCHESTRATOR: {Action.READ},  # View status only, no control
        Resource.DASHBOARDS: {Action.READ},  # View-only dashboard access
        Resource.LOGS: {Action.READ},  # View simplified logs
        Resource.SETTINGS: set(),  # No settings access
        Resource.USERS: set(),  # No user management
        Resource.INTEGRATIONS: {Action.READ},  # View integration status only
        Resource.ADMIN_PANEL: set(),  # No admin panel access
        Resource.LOG_DOWNLOAD: set(),  # No log download
    },

    Role.VIEW: {
        # View-only access - most restrictive role
        Resource.ETL_JOBS: {Action.READ},  # View status only
        Resource.ORCHESTRATOR: {Action.READ},  # View status only
        Resource.DASHBOARDS: {Action.READ},  # Read-only dashboard access
        Resource.LOGS: {Action.READ},  # View simplified logs
        Resource.SETTINGS: set(),  # No settings access
        Resource.USERS: set(),  # No user management
        Resource.INTEGRATIONS: set(),  # No integration access
        Resource.ADMIN_PANEL: set(),  # No admin panel access
        Resource.LOG_DOWNLOAD: set(),  # No log download
    }
}


def has_permission(user: User, resource: Resource, action: Action, session: Session = None) -> bool:
    """
    Check if a user has permission to perform an action on a resource.
    
    Args:
        user: User object
        resource: Resource to check
        action: Action to perform
        session: Database session (optional, for custom permissions)
        
    Returns:
        bool: True if user has permission
    """
    # Admin users have all permissions
    if user.is_admin:
        return True
    
    # Check role-based permissions first
    user_role = Role(user.role) if user.role in [r.value for r in Role] else None
    if user_role and user_role in DEFAULT_ROLE_PERMISSIONS:
        role_permissions = DEFAULT_ROLE_PERMISSIONS[user_role]
        if resource in role_permissions and action in role_permissions[resource]:
            return True
    
    # Check custom user permissions if session provided
    if session:
        custom_permission = session.query(UserPermission).filter(
            UserPermission.user_id == user.id,
            UserPermission.resource == resource.value,
            UserPermission.action == action.value,
            UserPermission.active == True
        ).first()
        
        if custom_permission:
            return True
    
    return False


def get_user_permissions(user: User, session: Session = None) -> Dict[Resource, Set[Action]]:
    """
    Get all permissions for a user.
    
    Args:
        user: User object
        session: Database session (optional, for custom permissions)
        
    Returns:
        Dict mapping resources to allowed actions
    """
    permissions = {}
    
    # Start with role-based permissions
    user_role = Role(user.role) if user.role in [r.value for r in Role] else None
    if user_role and user_role in DEFAULT_ROLE_PERMISSIONS:
        permissions = DEFAULT_ROLE_PERMISSIONS[user_role].copy()
    
    # Add custom permissions if session provided
    if session:
        custom_permissions = session.query(UserPermission).filter(
            UserPermission.user_id == user.id,
            UserPermission.active == True
        ).all()
        
        for perm in custom_permissions:
            try:
                resource = Resource(perm.resource)
                action = Action(perm.action)
                
                if resource not in permissions:
                    permissions[resource] = set()
                permissions[resource].add(action)
            except ValueError:
                # Skip invalid resource/action values
                continue
    
    # Admin users get everything
    if user.is_admin:
        for resource in Resource:
            permissions[resource] = set(Action)
    
    return permissions


def grant_permission(user_id: int, resource: Resource, action: Action, session: Session, client_id: int) -> bool:
    """
    Grant a custom permission to a user.

    Args:
        user_id: User ID
        resource: Resource to grant access to
        action: Action to allow
        session: Database session
        client_id: Client ID for the permission

    Returns:
        bool: True if permission was granted
    """
    try:
        # Check if permission already exists
        existing = session.query(UserPermission).filter(
            UserPermission.user_id == user_id,
            UserPermission.resource == resource.value,
            UserPermission.action == action.value,
            UserPermission.client_id == client_id  # ✅ SECURITY: Include client_id in check
        ).first()

        if existing:
            existing.active = True
        else:
            permission = UserPermission(
                user_id=user_id,
                resource=resource.value,
                action=action.value,
                client_id=client_id,  # ✅ SECURITY: Use provided client_id
                active=True
            )
            session.add(permission)

        session.commit()
        return True

    except Exception:
        session.rollback()
        return False


def revoke_permission(user_id: int, resource: Resource, action: Action, session: Session) -> bool:
    """
    Revoke a custom permission from a user.
    
    Args:
        user_id: User ID
        resource: Resource to revoke access from
        action: Action to disallow
        session: Database session
        
    Returns:
        bool: True if permission was revoked
    """
    try:
        permission = session.query(UserPermission).filter(
            UserPermission.user_id == user_id,
            UserPermission.resource == resource.value,
            UserPermission.action == action.value
        ).first()
        
        if permission:
            permission.active = False
            session.commit()
            return True
        
        return False
        
    except Exception:
        session.rollback()
        return False
