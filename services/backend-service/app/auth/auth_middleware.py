"""
Authentication middleware for ETL Service.
Provides authentication decorators and dependencies for FastAPI.
"""

from typing import Optional
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse

from app.auth.auth_service import get_auth_service
from app.models.unified_models import User
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Security scheme for FastAPI
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    Dependency to get the current authenticated user.
    Returns None if not authenticated (for optional authentication).
    """
    if not credentials:
        return None
    
    auth_service = get_auth_service()
    user = await auth_service.verify_token(credentials.credentials)
    
    if user:
        # Log successful authentication (avoid accessing user.email due to session expunge)
        logger.debug("User authenticated successfully")

    return user


async def require_authentication(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """
    Dependency that requires authentication.
    Raises HTTPException if not authenticated.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    auth_service = get_auth_service()
    user = await auth_service.verify_token(credentials.credentials)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.debug("User authenticated successfully")
    return user


async def require_web_authentication(
    request: Request
) -> User:
    """
    Web-specific authentication dependency that redirects to login on failure.
    Used for web pages instead of API endpoints.
    """
    try:
        # Try to get token from various sources
        token = None

        # 1. Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        # 2. Check cookies (for session-based auth)
        if not token:
            token = request.cookies.get("pulse_token")

        # 3. For web pages, we'll rely on JavaScript to include the token in headers
        # The frontend should set the Authorization header from localStorage

        if not token:
            logger.debug("No authentication token found, redirecting to login")
            return RedirectResponse(url="/login?error=authentication_required", status_code=302)

        auth_service = get_auth_service()
        user = await auth_service.verify_token(token)

        if not user:
            logger.debug("Invalid token, redirecting to login")
            return RedirectResponse(url="/login?error=invalid_token", status_code=302)

        logger.debug("Web user authenticated successfully")
        return user

    except Exception as e:
        logger.error(f"Web authentication error: {e}")
        return RedirectResponse(url="/login?error=authentication_failed", status_code=302)


async def require_admin(
    user: User = Depends(require_authentication)
) -> User:
    """
    Dependency that requires admin privileges.
    Raises HTTPException if user is not an admin.
    """
    if not user.is_admin:
        logger.warning(f"Admin access denied for user: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    logger.debug(f"Admin access granted for user: {user.email}")
    return user


async def require_role(required_role: str):
    """
    Dependency factory that requires a specific role.
    Returns a dependency function that checks for the required role.
    """
    async def role_checker(user: User = Depends(require_authentication)) -> User:
        if user.role != required_role and not user.is_admin:
            logger.warning(f"Role access denied for user, required: {required_role}, has: {user.role}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )

        logger.debug(f"Role access granted for user, role: {user.role}")
        return user

    return role_checker


def require_permission(resource: str, action: str):
    """
    Dependency factory that requires a specific permission.
    Returns a dependency function that checks for the required permission.
    """
    async def permission_checker(user: User = Depends(require_authentication)) -> User:
        from app.auth.permissions import Resource, Action, has_permission
        from app.core.database import get_database

        try:
            resource_enum = Resource(resource)
            action_enum = Action(action)

            # Check permission with database session for custom permissions
            database = get_database()
            with database.get_session() as session:
                if has_permission(user, resource_enum, action_enum, session):
                    logger.debug(f"Permission granted for user, resource: {resource}, action: {action}")
                    return user
                else:
                    logger.warning(f"Permission denied for user, resource: {resource}, action: {action}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission required: {action} on {resource}"
                    )
        except ValueError:
            logger.error(f"Invalid resource or action: {resource}, {action}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid resource or action"
            )

    return permission_checker


def require_web_permission(resource: str, action: str):
    """
    Web-specific permission dependency that redirects to login/error page on failure.
    Used for web pages instead of API endpoints.
    """
    async def web_permission_checker(user: User = Depends(require_web_authentication)) -> User:
        # If require_web_authentication returned a redirect, pass it through
        if isinstance(user, RedirectResponse):
            return user

        from app.auth.permissions import Resource, Action, has_permission
        from app.core.database import get_database

        try:
            resource_enum = Resource(resource)
            action_enum = Action(action)

            # Check permission with database session for custom permissions
            database = get_database()
            with database.get_session() as session:
                if has_permission(user, resource_enum, action_enum, session):
                    logger.debug(f"Web permission granted for user, resource: {resource}, action: {action}")
                    return user
                else:
                    logger.warning(f"Web permission denied for user, resource: {resource}, action: {action}")
                    return RedirectResponse(url=f"/dashboard?error=permission_denied&resource={resource}", status_code=302)
        except ValueError:
            logger.error(f"Invalid resource or action: {resource}, {action}")
            return RedirectResponse(url="/dashboard?error=invalid_permission", status_code=302)

    return web_permission_checker


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    # Check for forwarded headers first (for reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Extract user agent from request"""
    return request.headers.get("User-Agent", "unknown")
