"""
Centralized Authentication Service - API Only
Pure backend service for authentication validation and token management
No UI components - all authentication flows handled by other services
"""

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import jwt
from datetime import datetime, timedelta, timezone
import logging
import httpx

# Import configuration
from app.core.config import get_settings

settings = get_settings()

# Configure clean logging
from app.core.logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Pulse Authentication Service - API Only",
    description="Backend authentication validation service for Pulse Platform",
    version="1.0.0"
)

# CORS configuration using environment variables
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class CredentialValidationRequest(BaseModel):
    email: str
    password: str
    include_ml_fields: Optional[bool] = False

class CredentialValidationResponse(BaseModel):
    valid: bool
    user: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: Dict[str, Any]

class TokenValidationResponse(BaseModel):
    valid: bool
    user: Optional[Dict[str, Any]] = None

class UserInfoRequest(BaseModel):
    include_ml_fields: Optional[bool] = False

class SessionInfoRequest(BaseModel):
    include_ml_fields: Optional[bool] = False

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def generate_jwt_token(user_data: Dict[str, Any]) -> str:
    """Generate JWT token for authenticated user"""
    # CRITICAL: Use configured timezone for consistency with backend service
    try:
        import pytz
        tz = pytz.timezone(settings.DEFAULT_TIMEZONE)
        # Get current time in the configured timezone
        utc_now = datetime.now(timezone.utc)
        local_now = utc_now.astimezone(tz)
        # Convert to timezone-naive for consistency with backend
        now_default = local_now.replace(tzinfo=None)
        exp_default = now_default + timedelta(hours=settings.JWT_EXPIRY_HOURS)

        # For JWT timestamps, convert timezone-naive times to UTC epoch
        # Treat the timezone-naive datetime as if it's in the configured timezone
        local_aware = tz.localize(now_default)
        exp_aware = tz.localize(exp_default)

        iat_timestamp = int(local_aware.timestamp())
        exp_timestamp = int(exp_aware.timestamp())
    except Exception as e:
        logger.warning(f"Timezone conversion failed: {e}, falling back to UTC")
        utc_now = datetime.now(timezone.utc)
        iat_timestamp = int(utc_now.timestamp())
        exp_timestamp = int((utc_now + timedelta(hours=settings.JWT_EXPIRY_HOURS)).timestamp())
        now_default = utc_now.replace(tzinfo=None)

    payload = {
        "user_id": user_data["id"],
        "email": user_data["email"],
        "role": user_data["role"],
        "is_admin": user_data["is_admin"],
        "tenant_id": user_data["tenant_id"],
        "exp": exp_timestamp,
        "iat": iat_timestamp,
        "iss": "pulse-auth-service"
    }

    logger.info(f"[AUTH] JWT token created: iat={now_default}, timezone={settings.DEFAULT_TIMEZONE}")
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

# RBAC imports
from app.core.rbac import Role, Resource, Action, DEFAULT_ROLE_PERMISSIONS, has_permission


class PermissionCheckRequest(BaseModel):
    token: str | None = None
    resource: str
    action: str


class PermissionCheckResponse(BaseModel):
    allowed: bool
    user: Optional[Dict[str, Any]] = None


class PermissionMatrixResponse(BaseModel):
    roles: list[str]
    resources: list[str]
    actions: list[str]
    matrix: Dict[str, Dict[str, list[str]]]


# ============================================================================
# API ENDPOINTS - No UI, pure backend service
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "auth-service", "version": "1.0.0"}

@app.post("/api/v1/validate-credentials", response_model=CredentialValidationResponse)
async def validate_credentials(request: CredentialValidationRequest):
    """
    Validate user credentials against backend service with optional ML fields.
    Called by backend service for authentication.
    """
    try:
        logger.info(f"Validating credentials for user: {request.email}")

        # Call backend service to validate credentials with ML fields support
        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                f"{settings.BACKEND_SERVICE_URL}/api/v1/auth/centralized/validate-credentials",
                json={
                    "email": request.email,
                    "password": request.password,
                    "include_ml_fields": request.include_ml_fields
                },
                timeout=10.0
            )

            if auth_response.status_code != 200:
                logger.warning(f"Backend validation failed for {request.email}")
                return CredentialValidationResponse(
                    valid=False,
                    error="Authentication service unavailable"
                )

            user_data = auth_response.json()
            if not user_data.get("valid"):
                logger.warning(f"Invalid credentials for {request.email}")
                return CredentialValidationResponse(
                    valid=False,
                    error="Invalid credentials"
                )

            logger.info(f"Credentials validated successfully for {request.email}")
            return CredentialValidationResponse(
                valid=True,
                user=user_data["user"]
            )

    except Exception as e:
        logger.error(f"Credential validation error: {e}")
        return CredentialValidationResponse(
            valid=False,
            error="Authentication service error"
        )

@app.post("/api/v1/generate-token", response_model=TokenResponse)
async def generate_token(request: CredentialValidationRequest):
    """
    Generate JWT token for validated user with optional ML fields.
    Called by backend service after credential validation.
    """
    try:
        logger.info(f"Token generation request for user: {request.email}")

        # First validate credentials with ML fields support
        validation_result = await validate_credentials(request)

        if not validation_result.valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=validation_result.error or "Invalid credentials"
            )

        # Generate JWT token
        access_token = generate_jwt_token(validation_result.user)

        logger.info(f"Token generated successfully for user: {request.email}")

        return TokenResponse(
            access_token=access_token,
            expires_in=settings.JWT_EXPIRY_HOURS * 60 * 60,  # Convert hours to seconds
            user=validation_result.user
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token generation failed"
        )

@app.post("/api/v1/token/validate", response_model=TokenValidationResponse)
async def validate_token(request: Request):
    """Validate JWT token"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return TokenValidationResponse(valid=False, user=None)

        token = auth_header.split(" ")[1]

        # Decode and validate JWT token
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

            # Check if token is expired using configured timezone
            try:
                import pytz
                tz = pytz.timezone(settings.DEFAULT_TIMEZONE)
                utc_now = datetime.now(timezone.utc)
                local_now = utc_now.astimezone(tz)
                now_default = local_now.replace(tzinfo=None)

                # Convert JWT timestamp back to local timezone for comparison
                exp_utc = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                exp_local = exp_utc.astimezone(tz)
                exp_default = exp_local.replace(tzinfo=None)
            except Exception:
                # Fallback to UTC if timezone configuration fails
                now_default = datetime.now(timezone.utc).replace(tzinfo=None)
                exp_default = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).replace(tzinfo=None)

            if now_default > exp_default:
                return TokenValidationResponse(valid=False, user=None)

            # Return user data from token
            user_data = {
                "id": payload["user_id"],
                "email": payload["email"],
                "role": payload["role"],
                "is_admin": payload["is_admin"],
                "tenant_id": payload["tenant_id"]
            }

            return TokenValidationResponse(valid=True, user=user_data)

        except jwt.InvalidTokenError:
            return TokenValidationResponse(valid=False, user=None)

    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return TokenValidationResponse(valid=False, user=None)

@app.post("/api/v1/logout")
async def logout_api(request):
    """API logout endpoint - invalidate tokens"""
    try:

        # Placeholder logout implementation (blacklist not implemented)
        return {"message": "Logged out successfully", "success": True}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")


@app.post("/api/v1/user/info")
async def get_user_info(request: UserInfoRequest, http_request: Request):
    """Get user information with optional ML fields from token"""
    try:
        # Get token from Authorization header
        auth_header = http_request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required"
            )

        token = auth_header.split(" ")[1]

        # Validate token first
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

            # Check if token is expired
            if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired"
                )

            # Get user data from backend service with ML fields if requested
            async with httpx.AsyncClient() as client:
                user_response = await client.get(
                    f"{settings.BACKEND_SERVICE_URL}/api/v1/users/{payload['user_id']}",
                    params={"include_ml_fields": request.include_ml_fields},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0
                )

                if user_response.status_code != 200:
                    raise HTTPException(
                        status_code=user_response.status_code,
                        detail="Failed to fetch user information"
                    )

                user_data = user_response.json()
                return {
                    "user": user_data,
                    "ml_fields_included": request.include_ml_fields
                }

        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information"
        )


@app.post("/api/v1/sessions/info")
async def get_session_info(request: SessionInfoRequest, http_request: Request):
    """Get current session information with optional ML fields"""
    try:
        # Get token from Authorization header
        auth_header = http_request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required"
            )

        token = auth_header.split(" ")[1]

        # Validate token first
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

            # Check if token is expired
            if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired"
                )

            # Get session data from backend service with ML fields if requested
            async with httpx.AsyncClient() as client:
                session_response = await client.get(
                    f"{settings.BACKEND_SERVICE_URL}/api/v1/users/{payload['user_id']}/sessions",
                    params={"include_ml_fields": request.include_ml_fields, "active_only": True},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0
                )

                if session_response.status_code != 200:
                    raise HTTPException(
                        status_code=session_response.status_code,
                        detail="Failed to fetch session information"
                    )

                session_data = session_response.json()
                return {
                    "sessions": session_data.get("sessions", []),
                    "ml_fields_included": request.include_ml_fields,
                    "user_id": payload["user_id"]
                }

        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session information"
        )


@app.get("/api/v1/sessions/current")
async def get_current_session(
    include_ml_fields: bool = False,
    http_request: Request = None
):
    """Get current session information with optional ML fields"""
    try:
        # Get token from Authorization header
        auth_header = http_request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required"
            )

        token = auth_header.split(" ")[1]

        # Validate token and extract session info
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

            # Check if token is expired
            if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired"
                )

            # Build session info from token payload
            session_info = {
                "user_id": payload["user_id"],
                "email": payload["email"],
                "role": payload["role"],
                "is_admin": payload["is_admin"],
                "tenant_id": payload["tenant_id"],
                "issued_at": datetime.fromtimestamp(payload["iat"], tz=timezone.utc).isoformat(),
                "expires_at": datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat(),
                "issuer": payload.get("iss", "pulse-auth-service")
            }

            # Include ML fields if requested (placeholder for future enhancement)
            if include_ml_fields:
                session_info["ml_fields"] = {
                    "embedding": None,  # Phase 1: Always None
                    "ml_context": None  # Phase 1: Always None
                }

            return {
                "session": session_info,
                "ml_fields_included": include_ml_fields,
                "valid": True
            }

        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get current session error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get current session"
        )


@app.post("/api/v1/permissions/check", response_model=PermissionCheckResponse)
async def permissions_check(request: PermissionCheckRequest, http_request: Request):
    """Check if the user (from token or Authorization header) has permission for resource/action."""
    try:
        # Determine token source: explicit field or Authorization header
        token = request.token
        if not token:
            auth_header = http_request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            return PermissionCheckResponse(allowed=False, user=None)

        # Validate token to extract user
        validation = await validate_token(http_request)
        if not validation.valid or not validation.user:
            return PermissionCheckResponse(allowed=False, user=None)

        user = validation.user
        allowed = has_permission(
            is_admin=user.get("is_admin", False),
            role=user.get("role"),
            resource=request.resource,
            action=request.action,
        )
        return PermissionCheckResponse(allowed=allowed, user=user if allowed else user)
    except Exception as e:
        logger.error(f"Permission check error: {e}")
        return PermissionCheckResponse(allowed=False, user=None)


@app.get("/api/v1/permissions/matrix", response_model=PermissionMatrixResponse)
async def permissions_matrix():
    """Expose the default role-based permission matrix."""
    try:
        roles = [r.value for r in Role]
        resources = [res.value for res in Resource]
        actions = [a.value for a in Action]
        matrix: Dict[str, Dict[str, list[str]]] = {}
        for role in Role:
            matrix[role.value] = {}
            for resource in Resource:
                actions_set = DEFAULT_ROLE_PERMISSIONS.get(role, {}).get(resource, set())
                matrix[role.value][resource.value] = [a.value for a in actions_set]
        return PermissionMatrixResponse(roles=roles, resources=resources, actions=actions, matrix=matrix)
    except Exception as e:
        logger.error(f"Permission matrix error: {e}")
        # Return empty but valid structure
        return PermissionMatrixResponse(roles=[], resources=[], actions=[], matrix={})

        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

            # In a full implementation, add token to blacklist
            # For now, we'll just log the logout
            try:
                payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                logger.info(f"User {payload.get('email')} logged out")
            except jwt.InvalidTokenError:
                pass

        return {"message": "Logged out successfully", "success": True}

    except Exception as e:
        logger.error(f"Logout error: {e}")
        return {"message": "Logout failed", "success": False}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.AUTH_SERVICE_HOST, port=settings.AUTH_SERVICE_PORT)
