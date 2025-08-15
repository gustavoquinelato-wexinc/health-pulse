"""
Centralized Authentication Middleware for ETL Service.
Uses Backend Service for authentication validation.
"""

from typing import Optional
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse

from app.auth.centralized_auth_service import get_centralized_auth_service
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Security scheme for FastAPI
security = HTTPBearer(auto_error=False)


class UserData:
    """User data class to replace the User model for centralized auth."""
    
    def __init__(self, user_data: dict):
        self.id = user_data.get("id")
        self.email = user_data.get("email")
        self.first_name = user_data.get("first_name")
        self.last_name = user_data.get("last_name")
        self.role = user_data.get("role")
        self.is_admin = user_data.get("is_admin", False)
        self.active = user_data.get("active", True)
        self.client_id = user_data.get("client_id")


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[UserData]:
    """
    Dependency that optionally returns the current user.
    Returns None if not authenticated.
    """
    if not credentials:
        return None
    
    auth_service = get_centralized_auth_service()
    user_data = await auth_service.verify_token(credentials.credentials)
    
    if not user_data:
        return None
    
    logger.debug("User authenticated successfully via centralized auth")
    return UserData(user_data)


async def require_authentication(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserData:
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
    
    auth_service = get_centralized_auth_service()
    user_data = await auth_service.verify_token(credentials.credentials)
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.debug("User authenticated successfully via centralized auth")
    return UserData(user_data)


async def require_admin_authentication(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserData:
    """
    Dependency that requires admin authentication.
    Raises HTTPException if not authenticated or not admin.
    """
    user = await require_authentication(request, credentials)
    
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return user


async def require_web_authentication(request: Request) -> UserData:
    """
    Dependency for web pages that requires authentication.
    Raises HTTPException if not authenticated (for API endpoints).
    """
    # Try to get token from cookie first, then Authorization header
    token = request.cookies.get("pulse_token")

    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        logger.debug("No authentication token found for API request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = get_centralized_auth_service()
    user_data = await auth_service.verify_token(token)

    if not user_data:
        logger.debug("Invalid token for API request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug("Web user authenticated successfully via centralized auth")
    return UserData(user_data)


async def check_web_authentication(request: Request):
    """
    Check authentication for web pages and return appropriate response.
    Returns UserData if authenticated, RedirectResponse if not.
    Use this for web page routes that need to redirect to login.
    """
    # Try to get token from cookie first, then Authorization header
    token = request.cookies.get("pulse_token")

    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        logger.debug("No authentication token found, redirecting to login")
        return RedirectResponse(url="/login?error=authentication_required", status_code=302)

    auth_service = get_centralized_auth_service()
    user_data = await auth_service.verify_token(token)

    if not user_data:
        logger.debug("Invalid token, redirecting to login")
        return RedirectResponse(url="/login?error=invalid_token", status_code=302)

    logger.debug("Web user authenticated successfully via centralized auth")
    return UserData(user_data)


# Legacy function for backward compatibility
async def verify_token(user: UserData = Depends(require_authentication)):
    """Verify JWT token - now uses centralized authentication system"""
    return user
