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
settings = get_settings()


@router.post("/login", response_model=LoginResponse)
async def login(login_request: LoginRequest, request: Request):
    """
    User login endpoint - delegates to centralized auth service.
    Validates credentials and returns JWT token with user information.

    Flow:
    1. Backend → Auth-Service: Validate credentials
    2. Auth-Service → Backend: Validate password against database
    3. Auth-Service: Generate JWT token
    4. Backend: Store session (database + Redis)
    5. Backend → User: Return token
    """
    logger.info(f"Login attempt for email: {login_request.email}")

    try:
        # Get client info from request
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "Unknown")

        # Authenticate via centralized auth service
        from app.core.config import get_settings
        import httpx
        settings = get_settings()
        auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')

        async with httpx.AsyncClient() as client:
            # Step 1: Validate credentials
            response = await client.post(
                f"{auth_service_url}/api/v1/validate-credentials",
                json={
                    "email": login_request.email,
                    "password": login_request.password,
                    "include_ml_fields": getattr(login_request, 'include_ml_fields', False)
                },
                timeout=30.0  # Increased for heavy ETL operations
            )

            if response.status_code != 200:
                logger.warning(f"Login failed for email: {login_request.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )

            validation_data = response.json()

            if not validation_data.get("valid"):
                logger.warning(f"Invalid credentials for email: {login_request.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )

            # Step 2: Generate token
            gen_resp = await client.post(
                f"{auth_service_url}/api/v1/generate-token",
                json={
                    "email": login_request.email,
                    "password": login_request.password,
                    "include_ml_fields": getattr(login_request, 'include_ml_fields', False)
                },
                timeout=30.0  # Increased for heavy ETL operations
            )

            if gen_resp.status_code != 200:
                logger.error(f"Token generation failed for email: {login_request.email}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Token generation failed"
                )

            gen_data = gen_resp.json()
            auth_result = {
                "token": gen_data["access_token"],
                "user": gen_data["user"],
            }

            # Step 3: Store session locally (for admin panel, logout, etc.)
            auth_service = get_auth_service()
            try:
                await auth_service.store_session_from_token(
                    auth_result["token"],
                    auth_result["user"],
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            except Exception as e:
                logger.warning(f"Could not store session: {e}")

        logger.info(f"Login successful for email: {login_request.email}")

        # Create response with token
        response_data = LoginResponse(
            success=True,
            token=auth_result["token"],
            user=auth_result["user"]
        )

        # Create JSON response to set cookies
        response = JSONResponse(content=response_data.dict())

        # Set subdomain-shared cookie for all services
        response.set_cookie(
            key="pulse_token",
            value=auth_result["token"],
            max_age=24 * 60 * 60,  # 24 hours
            httponly=False,  # Allow JavaScript access for cross-service sharing
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            path="/",
            domain=settings.COOKIE_DOMAIN
        )

        logger.info(f"Session cookie set for domain: {settings.COOKIE_DOMAIN}")
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
    Invalidates the current session and broadcasts logout to all user's devices.
    """
    logger.info("Logout request received")

    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("Logout: Missing or invalid authorization header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header"
            )

        token = auth_header[7:]  # Remove "Bearer " prefix

        # Get user info before invalidating session
        auth_service = get_auth_service()
        user_data = await auth_service.verify_token(token, suppress_errors=True)

        # Invalidate session
        success = await auth_service.logout(token)

        # Broadcast logout to all user's WebSocket connections
        if success and user_data:
            try:
                from app.api.websocket_routes import get_session_websocket_manager
                session_ws_manager = get_session_websocket_manager()
                await session_ws_manager.broadcast_logout(user_data.id, reason="user_logout")
                logger.info(f"Logout broadcast sent to user_id={user_data.id}")
            except Exception as e:
                logger.warning(f"Failed to broadcast logout via WebSocket: {e}")

        if success:
            logger.info("Logout successful - session invalidated")
        else:
            logger.warning("Logout - session not found")

        # Always return success and clear cookie
        response = JSONResponse(content={"message": "Logout successful", "success": True})
        response.delete_cookie(
            key="pulse_token",
            path="/",
            domain=settings.COOKIE_DOMAIN  # Must specify domain to delete shared cookie
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
    logger.info(f"Logout-all request for user: {current_user.email}")

    try:
        # Invalidate all sessions for the user
        auth_service = get_auth_service()
        success = await auth_service.logout_all_sessions(current_user.id)

        if success:
            logger.info(f"Logout-all successful for user: {current_user.email}")
        else:
            logger.warning(f"Logout-all failed for user: {current_user.email}")

        # Always return success and clear cookie
        response = JSONResponse(content={"message": "Logged out from all devices", "success": True})
        response.delete_cookie(
            key="pulse_token",
            path="/",
            domain=settings.COOKIE_DOMAIN  # Must specify domain to delete shared cookie
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
            logger.debug(f"[AUTH] Backend validating token from header (length: {len(token)})")

        # 2. Fallback to cookie if no Authorization header
        if not token:
            token = request.cookies.get("pulse_token")
            if token:
                logger.debug(f"[AUTH] Backend validating token from cookie (length: {len(token)})")

        if not token:
            logger.debug("No token found in Authorization header or cookies")
            return TokenValidationResponse(valid=False, user=None)

        # Validate token via centralized auth service only
        try:
            import httpx
            from app.core.config import get_settings
            settings = get_settings()
            auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')

            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        f"{auth_service_url}/api/v1/token/validate",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=30.0  # Increased timeout for heavy ETL operations
                    )
                except httpx.ReadTimeout:
                    logger.warning("Token validation timeout during heavy load")
                    return {"valid": False, "user": None}
                except httpx.ConnectError:
                    logger.error(f"Cannot connect to auth service at {auth_service_url}")
                    return {"valid": False, "user": None}

                if response.status_code == 200:
                    token_data = response.json()
                    if token_data.get("valid"):
                        user_data = token_data.get("user")
                        # Log success without exposing email address (PII)
                        logger.debug(f"[AUTH] Backend token validation successful (centralized) for user_id: {user_data.get('id')}")

                        # Enforce revocation: require an ACTIVE DB session for this token
                        from app.core.database import get_database
                        from app.models.unified_models import UserSession
                        from app.core.utils import DateTimeHelper
                        auth_service = get_auth_service()
                        token_hash = auth_service._hash_token(token)

                        database = get_database()
                        with database.get_read_session_context() as db:
                            session_row = db.query(UserSession).filter(
                                UserSession.token_hash == token_hash,
                                UserSession.active == True
                            ).first()

                            if not session_row:
                                logger.info("[AUTH] Token valid cryptographically but no active session found; denying")
                                return TokenValidationResponse(valid=False, user=None)

                        # Optional: touch last_updated_at in a short write
                        with database.get_write_session_context() as dbw:
                            row = dbw.query(UserSession).filter(UserSession.token_hash == token_hash, UserSession.active == True).first()
                            if row:
                                row.last_updated_at = DateTimeHelper.now_utc()
                                dbw.commit()

                        return TokenValidationResponse(valid=True, user=user_data)
        except Exception as e:
            logger.debug(f"[AUTH] Error contacting centralized auth service: {e}")

        logger.debug(f"[AUTH] Backend token validation failed (token length: {len(token)})")
        return TokenValidationResponse(valid=False, user=None)
            
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return TokenValidationResponse(valid=False, user=None)


@router.post("/refresh")
async def refresh_token(request: Request):
    """
    Token refresh endpoint - delegates to centralized auth service.
    Validates current token and returns a new one if valid.
    """
    try:
        # Get token from Authorization header
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix

        if not token:
            logger.debug("No token found in Authorization header for refresh")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No token provided for refresh"
            )

        # Delegate to centralized auth service for token refresh
        settings = get_settings()
        auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{auth_service_url}/api/v1/token/refresh",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=60.0  # Extended timeout during heavy ETL operations
                )
            except httpx.ReadTimeout:
                logger.warning(f"Auth service timeout during heavy load - database may be busy with ETL operations")
                # Return 401 to trigger frontend token refresh retry instead of 503
                raise HTTPException(
                    status_code=401,
                    detail="Token refresh timeout - please try again"
                )
            except httpx.ConnectError:
                logger.error(f"Cannot connect to auth service at {auth_service_url}")
                raise HTTPException(
                    status_code=503,
                    detail="Authentication service unavailable"
                )

            if response.status_code == 200:
                token_data = response.json()
                new_token = token_data["access_token"]
                user_data = token_data["user"]

                logger.info(f"Token refreshed successfully via auth service for user_id: {user_data.get('id')}")

                # Create response with updated cookie
                response_data = {
                    "success": True,
                    "token": new_token,
                    "user": user_data
                }

                json_response = JSONResponse(content=response_data)

                # Update the subdomain-shared cookie with new token
                json_response.set_cookie(
                    key="pulse_token",
                    value=new_token,
                    max_age=24 * 60 * 60,  # 24 hours
                    httponly=False,  # Allow JavaScript access for cross-service sharing
                    secure=settings.COOKIE_SECURE,
                    samesite=settings.COOKIE_SAMESITE,
                    path="/",
                    domain=settings.COOKIE_DOMAIN
                )

                logger.info(f"Cookie updated with new token for domain: {settings.COOKIE_DOMAIN}")
                return json_response
            else:
                logger.warning(f"Auth service refresh failed with status: {response.status_code}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token refresh failed"
                )

    except httpx.RequestError as e:
        logger.error(f"Auth service communication error during refresh: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/extend-session")
async def extend_session(request: Request):
    """
    Extend session endpoint - called by auth service after token refresh.
    Stores new token and extends session expiry to 60 minutes from now.
    """
    try:
        # Parse request body
        body = await request.json()
        token = body.get("token")
        user_data = body.get("user_data")
        is_refresh = body.get("is_refresh", True)

        if not token or not user_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing token or user_data"
            )

        # Store session with extended expiry
        from app.auth.auth_service import get_auth_service
        auth_service = get_auth_service()

        await auth_service.store_session_from_token(token, user_data, is_refresh=is_refresh)

        logger.info(f"Session extended for user_id: {user_data['id']} (expires in 60 min)")

        return {
            "success": True,
            "message": "Session extended successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session extension error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session extension failed"
        )


# Navigation session endpoint removed - now handled by Redis shared sessions


# Session check endpoint removed - no longer needed with subdomain cookies


@router.post("/validate-service")
async def validate_service_token(
    include_ml_fields: bool = False,
    user: User = Depends(require_authentication)
):
    """
    Token validation endpoint for service-to-service communication with optional ML fields.
    Returns user information if token is valid.
    """
    try:
        return {
            "valid": True,
            "user": user.to_dict(include_ml_fields=include_ml_fields)
        }
    except Exception as e:
        logger.error(f"Service token validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token validation failed"
        )


# Cross-service login endpoint removed - no longer needed with subdomain cookies


@router.get("/user-info")
async def get_user_info(
    include_ml_fields: bool = False,
    user: User = Depends(require_authentication)
):
    """
    Get current user information with optional ML fields.
    Requires valid authentication token.
    """
    try:
        return user.to_dict(include_ml_fields=include_ml_fields)
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
