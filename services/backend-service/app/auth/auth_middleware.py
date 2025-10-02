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


class UserData:
    """User data class to replace the User model for centralized auth."""

    def __init__(self, user_data: dict):
        self.id = user_data.get("id")
        self.user_id = user_data.get("id")  # Alias for compatibility
        self.email = user_data.get("email")
        self.first_name = user_data.get("first_name")
        self.last_name = user_data.get("last_name")
        self.role = user_data.get("role")
        self.is_admin = user_data.get("is_admin", False)
        self.active = user_data.get("active", True)
        self.tenant_id = user_data.get("tenant_id")
        self.auth_provider = user_data.get("auth_provider", "centralized")
        self.theme_mode = user_data.get("theme_mode", "light")

    def __str__(self):
        return f"UserData(id={self.id}, email={self.email}, role={self.role})"


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[UserData]:
    """
    Dependency to get the current authenticated user.
    Returns None if not authenticated (for optional authentication).
    Supports both local and centralized authentication.
    """
    if not credentials:
        return None

    # Delegate to centralized authentication service only
    try:
        import httpx
        from app.core.config import get_settings
        settings = get_settings()
        auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{auth_service_url}/api/v1/token/validate",
                headers={"Authorization": f"Bearer {credentials.credentials}"},
                timeout=5.0
            )

            if response.status_code == 200:
                token_data = response.json()
                if token_data.get("valid"):
                    user_data_dict = token_data.get("user")
                    logger.debug("User authenticated successfully (centralized)")

                    # Create a UserData object from the centralized data
                    user_data = UserData(user_data_dict)
                    return user_data

        logger.debug("Centralized authentication failed")

    except Exception as e:
        logger.warning(f"Error during centralized authentication: {e}")

    return None


async def require_authentication(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserData:
    """
    Dependency that requires authentication.
    Supports both local system tokens and centralized auth tokens.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # First try local authentication (for system users)
    try:
        from app.auth.auth_service import get_auth_service
        auth_service = get_auth_service()
        user = await auth_service.verify_token(credentials.credentials)

        if user:
            logger.debug(f"User authenticated successfully (local): {user.email}")
            # Create UserData object from local user
            user_data = UserData({
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
                "is_admin": user.is_admin,
                "tenant_id": user.tenant_id,
                "auth_provider": user.auth_provider
            })
            return user_data
    except Exception as e:
        logger.debug(f"Local authentication failed: {e}")

    # Fallback to centralized authentication service
    try:
        import httpx
        from app.core.config import get_settings
        settings = get_settings()
        auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')

        from app.core.http_client import get_async_client
        client = get_async_client()
        response = await client.post(
            f"{auth_service_url}/api/v1/token/validate",
            headers={"Authorization": f"Bearer {credentials.credentials}"}
        )

        if response.status_code == 200:
                token_data = response.json()
                if token_data.get("valid"):
                    user_data_dict = token_data.get("user")

                    # Create UserData object
                    user_data = UserData(user_data_dict)
                    logger.debug("User authenticated successfully (centralized)")
                    return user_data
    except Exception as e:
        logger.warning(f"Centralized authentication error: {e}")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_web_authentication(
    request: Request
) -> UserData:
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

        # Delegate to centralized authentication service
        import httpx
        from app.core.config import get_settings
        settings = get_settings()
        auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')

        from app.core.http_client import get_async_client
        client = get_async_client()
        response = await client.post(
            f"{auth_service_url}/api/v1/token/validate",
            headers={"Authorization": f"Bearer {token}"}
        )

        if response.status_code == 200:
                token_data = response.json()
                if token_data.get("valid"):
                    user_data_dict = token_data.get("user")
                    user_data = UserData(user_data_dict)
                    logger.debug("Web user authenticated successfully")
                    return user_data

        logger.debug("Invalid token, redirecting to login")
        return RedirectResponse(url="/login?error=invalid_token", status_code=302)

    except Exception as e:
        logger.error(f"Web authentication error: {e}")
        return RedirectResponse(url="/login?error=authentication_failed", status_code=302)


async def require_admin(
    user: UserData = Depends(require_authentication)
) -> UserData:
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
    async def role_checker(user: UserData = Depends(require_authentication)) -> UserData:
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
    async def permission_checker(request: Request, user: UserData = Depends(require_authentication)) -> UserData:
        """Delegate permission check to auth-service RBAC."""
        import httpx
        from app.core.config import get_settings
        settings = get_settings()
        auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')

        # Extract token from header or cookie
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        if not token:
            token = request.cookies.get("pulse_token")

        try:
            from app.core.http_client import get_async_client
            client = get_async_client()
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            response = await client.post(
                f"{auth_service_url}/api/v1/permissions/check",
                headers=headers,
                json={"resource": resource, "action": action}
            )
            if response.status_code == 200 and response.json().get("allowed"):
                logger.debug(f"Permission granted for user, resource: {resource}, action: {action}")
                return user
            else:
                logger.warning(f"Permission denied for user, resource: {resource}, action: {action}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission required: {action} on {resource}"
                )
        except Exception:
            logger.error(f"Error checking permission: {resource}, {action}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permission check failed"
            )

    return permission_checker


def require_web_permission(resource: str, action: str):
    """
    Web-specific permission dependency that redirects to login/error page on failure.
    Delegates permission checks to Auth Service.
    """
    async def web_permission_checker(request: Request, user: UserData = Depends(require_web_authentication)) -> UserData:
        # If require_web_authentication returned a redirect, pass it through
        if isinstance(user, RedirectResponse):
            return user

        import httpx
        from app.core.config import get_settings
        settings = get_settings()
        auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')

        # Extract token from cookie or header
        token = request.cookies.get("pulse_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                response = await client.post(
                    f"{auth_service_url}/api/v1/permissions/check",
                    headers=headers,
                    json={"resource": resource, "action": action},
                    timeout=5.0
                )
                if response.status_code == 200 and response.json().get("allowed"):
                    logger.debug(f"Web permission granted for user, resource: {resource}, action: {action}")
                    return user
                else:
                    logger.warning(f"Web permission denied for user, resource: {resource}, action: {action}")
                    return RedirectResponse(url=f"/dashboard?error=permission_denied&resource={resource}", status_code=302)
        except Exception:
            logger.error(f"Error checking web permission: {resource}, {action}")
            return RedirectResponse(url="/dashboard?error=permission_check_failed", status_code=302)

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
