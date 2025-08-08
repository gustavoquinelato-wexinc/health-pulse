"""
RBAC model for Auth Service

Defines Role, Resource, Action enums, default permissions matrix, and permission checks.
Auth Service is the source of truth for RBAC.
"""
from enum import Enum
from typing import Dict, Set


class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEW = "view"


class Resource(str, Enum):
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
    READ = "read"
    EXECUTE = "execute"
    DELETE = "delete"
    ADMIN = "admin"


DEFAULT_ROLE_PERMISSIONS: Dict[Role, Dict[Resource, Set[Action]]] = {
    Role.ADMIN: {
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
        Resource.ETL_JOBS: {Action.READ},
        Resource.ORCHESTRATOR: {Action.READ},
        Resource.DASHBOARDS: {Action.READ},
        Resource.LOGS: {Action.READ},
        Resource.SETTINGS: set(),
        Resource.USERS: set(),
        Resource.INTEGRATIONS: {Action.READ},
        Resource.ADMIN_PANEL: set(),
        Resource.LOG_DOWNLOAD: set(),
    },
    Role.VIEW: {
        Resource.ETL_JOBS: {Action.READ},
        Resource.ORCHESTRATOR: {Action.READ},
        Resource.DASHBOARDS: {Action.READ},
        Resource.LOGS: {Action.READ},
        Resource.SETTINGS: set(),
        Resource.USERS: set(),
        Resource.INTEGRATIONS: set(),
        Resource.ADMIN_PANEL: set(),
        Resource.LOG_DOWNLOAD: set(),
    },
}


def has_permission(is_admin: bool, role: str, resource: str, action: str) -> bool:
    """Check RBAC using role and admin flag.
    Note: Custom per-user overrides are not handled here and should be plugged in by callers if needed.
    """
    if is_admin:
        return True

    try:
        role_enum = Role(role)
        resource_enum = Resource(resource)
        action_enum = Action(action)
    except ValueError:
        return False

    role_perms = DEFAULT_ROLE_PERMISSIONS.get(role_enum, {})
    allowed_actions = role_perms.get(resource_enum, set())
    return action_enum in allowed_actions

