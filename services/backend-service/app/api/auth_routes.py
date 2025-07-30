"""
Authentication API routes for Backend Service.
Handles login, logout, token validation, and session management.
"""

from fastapi import APIRouter, HTTPException, status, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.logging_config import get_logger
from app.auth.auth_service import get_auth_service
from app.auth.auth_middleware import require_authentication
from app.schemas.api_schemas import LoginRequest, LoginResponse, TokenValidationResponse
from app.models.unified_models import User

router = APIRouter()
logger = get_logger(__name__)


@router.post("/login", response_model=LoginResponse)
async def login(login_request: LoginRequest, request: Request):
    """
    User login endpoint.
    Validates credentials and returns JWT token with user information.
    """
    logger.info(f"🔐 Login attempt for email: {login_request.email}")
    
    try:
        # Get client info from request
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "Unknown")
        
        # Authenticate user
        auth_service = get_auth_service()
        auth_result = await auth_service.authenticate_local(
            email=login_request.email,
            password=login_request.password,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if not auth_result:
            logger.warning(f"❌ Login failed for email: {login_request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        logger.info(f"✅ Login successful for email: {login_request.email}")

        return LoginResponse(
            success=True,
            token=auth_result["token"],
            user=auth_result["user"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed due to server error"
        )


@router.post("/logout")
async def logout(request: Request):
    """
    User logout endpoint.
    Invalidates the current session.
    """
    logger.info("🔐 Logout request received")
    
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("❌ Logout: Missing or invalid authorization header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header"
            )
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Invalidate session
        auth_service = get_auth_service()
        success = await auth_service.invalidate_session(token)
        
        if success:
            logger.info("✅ Logout successful - session invalidated")
            return {"message": "Logout successful", "success": True}
        else:
            logger.warning("❌ Logout failed - session not found")
            return {"message": "Session not found", "success": False}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed due to server error"
        )


@router.post("/validate", response_model=TokenValidationResponse)
async def validate_token(request: Request):
    """
    Token validation endpoint for frontend.
    Returns user information if token is valid.
    """
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            return TokenValidationResponse(valid=False, user=None)
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Validate token
        auth_service = get_auth_service()
        user = await auth_service.verify_token(token)
        
        if user:
            return TokenValidationResponse(
                valid=True,
                user={
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                    "is_admin": user.is_admin,
                    "client_id": user.client_id  # ✅ Added missing client_id
                }
            )
        else:
            return TokenValidationResponse(valid=False, user=None)
            
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return TokenValidationResponse(valid=False, user=None)


@router.post("/validate-service")
async def validate_service_token(user: User = Depends(require_authentication)):
    """
    Token validation endpoint for service-to-service communication.
    Returns user information if token is valid.
    """
    try:
        return {
            "valid": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
                "is_admin": user.is_admin,
                "client_id": user.client_id  # ✅ Added missing client_id
            }
        }
    except Exception as e:
        logger.error(f"Service token validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token validation failed"
        )


@router.get("/user-info")
async def get_user_info(user: User = Depends(require_authentication)):
    """
    Get current user information.
    Requires valid authentication token.
    """
    try:
        return {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_admin": user.is_admin,
            "auth_provider": user.auth_provider,
            "client_id": user.client_id,  # ✅ Added missing client_id for consistency
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None
        }
    except Exception as e:
        logger.error(f"Get user info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information"
        )
