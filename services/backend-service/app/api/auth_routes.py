"""
Authentication API routes for Backend Service.
Handles login, logout, token validation, and session management.
"""

from fastapi import APIRouter, HTTPException, status, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import httpx

from app.core.database import get_db_session
from app.core.logging_config import get_logger
from app.core.config import get_settings
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
        
        # Authenticate user via centralized auth service first, then local
        auth_service = get_auth_service()

        # Try centralized auth service first
        try:
            from app.core.config import get_settings
            import httpx
            settings = get_settings()
            auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{auth_service_url}/api/v1/validate-credentials",
                    json={"email": login_request.email, "password": login_request.password},
                    timeout=10.0
                )

                if response.status_code == 200:
                    validation_data = response.json()
                    if validation_data.get("valid"):
                        # Centralized auth successful, create local session
                        user_data = validation_data["user"]

                        # Create local session using auth service
                        auth_result = await auth_service.create_session_from_user_data(
                            user_data=user_data,
                            ip_address=ip_address,
                            user_agent=user_agent
                        )
                    else:
                        auth_result = None
                else:
                    # Fallback to local authentication
                    auth_result = await auth_service.authenticate_local(
                        email=login_request.email,
                        password=login_request.password,
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
        except Exception as e:
            logger.warning(f"Centralized auth service unavailable, using local auth: {e}")
            # Fallback to local authentication
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

        # Create response with token
        response_data = LoginResponse(
            success=True,
            token=auth_result["token"],
            user=auth_result["user"]
        )

        # Create JSON response to set cookies
        response = JSONResponse(content=response_data.dict())

        # Set subdomain-shared cookie for all services
        from app.core.config import get_settings
        settings = get_settings()

        response.set_cookie(
            key="pulse_token",
            value=auth_result["token"],
            max_age=24 * 60 * 60,  # 24 hours (match JWT expiry)
            httponly=False,  # Must be False to allow JavaScript access for cross-service sharing
            secure=settings.COOKIE_SECURE,  # From environment variable
            samesite=settings.COOKIE_SAMESITE,  # From environment variable
            path="/",  # Ensure cookie is sent to all paths
            domain=settings.COOKIE_DOMAIN  # From environment variable
        )

        logger.info(f"✅ Subdomain-shared session cookie set for all services")
        return response
        
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
        success = await auth_service.logout(token)
        
        if success:
            logger.info("✅ Logout successful - session invalidated")
            response = JSONResponse(content={"message": "Logout successful", "success": True})
            # Clear the session cookie
            response.delete_cookie(
                key="pulse_token",
                path="/"
            )
            # Add cache control headers to prevent caching
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'
            return response
        else:
            logger.warning("❌ Logout failed - session not found")
            response = JSONResponse(content={"message": "Session not found", "success": False})
            # Clear the cookie anyway in case it exists
            response.delete_cookie(
                key="pulse_token",
                path="/"
            )
            # Add cache control headers to prevent caching
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed due to server error"
        )


@router.post("/logout-all")
async def logout_all(current_user: User = Depends(require_authentication)):
    """
    Logout user from all devices/sessions.
    Invalidates all active sessions for the current user.
    """
    logger.info(f"🔐 Logout-all request for user: {current_user.email}")

    try:
        # Invalidate all sessions for the user
        auth_service = get_auth_service()
        success = await auth_service.logout_all_sessions(current_user.id)

        if success:
            logger.info(f"✅ Logout-all successful for user: {current_user.email}")
            response = JSONResponse(content={"message": "Logged out from all devices", "success": True})
            # Clear the session cookie
            response.delete_cookie(
                key="pulse_token",
                path="/"
            )
            # Add cache control headers to prevent caching
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'
            return response
        else:
            logger.warning(f"❌ Logout-all failed for user: {current_user.email}")
            response = JSONResponse(content={"message": "Failed to logout from all devices", "success": False})
            # Clear the cookie anyway
            response.delete_cookie(
                key="pulse_token",
                path="/"
            )
            # Add cache control headers to prevent caching
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'
            return response

    except Exception as e:
        logger.error(f"Logout-all error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout-all failed due to server error"
        )


@router.post("/validate", response_model=TokenValidationResponse)
async def validate_token(request: Request):
    """
    Token validation endpoint for frontend.
    Returns user information if token is valid.
    """
    try:
        # Get token from Authorization header or cookie
        token = None

        # 1. Check Authorization header first
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            logger.info(f"Backend validating token from header: {token[:30]}... (length: {len(token)})")

        # 2. Fallback to cookie if no Authorization header
        if not token:
            token = request.cookies.get("pulse_token")
            if token:
                logger.info(f"Backend validating token from cookie: {token[:30]}... (length: {len(token)})")

        if not token:
            logger.debug("No token found in Authorization header or cookies")
            return TokenValidationResponse(valid=False, user=None)

        # Validate token - first try local, then centralized
        auth_service = get_auth_service()
        user = await auth_service.verify_token(token)

        if user:
            logger.info(f"Backend token validation successful (local) for user: {user.email}")
            return TokenValidationResponse(
                valid=True,
                user={
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                    "is_admin": user.is_admin,
                    "client_id": user.client_id
                }
            )

        # If local validation fails, try centralized auth service
        logger.debug("Local token validation failed, trying centralized auth service...")

        try:
            import httpx
            from app.core.config import get_settings
            settings = get_settings()
            auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{auth_service_url}/api/v1/token/validate",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0
                )

                if response.status_code == 200:
                    token_data = response.json()
                    if token_data.get("valid"):
                        user_data = token_data.get("user")
                        logger.info(f"Backend token validation successful (centralized) for user: {user_data['email']}")

                        # Cache the token locally for future requests
                        await auth_service.store_session_from_token(token, user_data)

                        return TokenValidationResponse(
                            valid=True,
                            user=user_data
                        )

                logger.debug("Centralized token validation also failed")

        except Exception as e:
            logger.warning(f"Error contacting centralized auth service: {e}")

        logger.warning(f"Backend token validation failed for token: {token[:30]}... (length: {len(token)})")
        return TokenValidationResponse(valid=False, user=None)
            
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return TokenValidationResponse(valid=False, user=None)


# Navigation session endpoint removed - now handled by Redis shared sessions


# Session check endpoint removed - no longer needed with subdomain cookies


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


# Cross-service login endpoint removed - no longer needed with subdomain cookies


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


# Cross-service authentication setup function removed - no longer needed with subdomain cookies


@router.post("/setup-etl-access")
async def setup_etl_access(request: Request, current_user: User = Depends(require_authentication)):
    """
    Set up ETL service access for the current user.
    Called by Frontend before navigating to ETL service.
    """
    try:
        # Get the current token from the Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header"
            )

        token = auth_header[7:]  # Remove "Bearer " prefix

        logger.info(f"🔗 Setting up ETL access for user: {current_user.email}")

        # With subdomain cookies, no additional setup needed

        return {
            "success": True,
            "message": "ETL access configured",
            "token": token  # Return the same token for Frontend to use
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error setting up ETL access: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to setup ETL access"
        )
