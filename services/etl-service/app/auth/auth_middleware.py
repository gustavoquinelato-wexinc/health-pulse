"""
Authentication middleware for ETL Service.
Provides authentication decorators and dependencies for FastAPI.
"""

from typing import Optional
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

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
        # Log successful authentication
        logger.debug(f"User authenticated: {user.email}")
    
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
    
    logger.debug(f"User authenticated: {user.email}")
    return user


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
            logger.warning(f"Role access denied for user: {user.email}, required: {required_role}, has: {user.role}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )
        
        logger.debug(f"Role access granted for user: {user.email}, role: {user.role}")
        return user
    
    return role_checker


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
