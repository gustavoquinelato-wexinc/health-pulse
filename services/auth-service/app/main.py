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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def generate_jwt_token(user_data: Dict[str, Any]) -> str:
    """Generate JWT token for authenticated user"""
    # CRITICAL: Use timezone-naive UTC for consistency with database
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    payload = {
        "user_id": user_data["id"],
        "email": user_data["email"],
        "role": user_data["role"],
        "is_admin": user_data["is_admin"],
        "client_id": user_data["client_id"],
        "exp": now_utc + timedelta(hours=settings.JWT_EXPIRY_HOURS),
        "iat": now_utc,
        "iss": "pulse-auth-service"
    }
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
    Validate user credentials against backend service.
    Called by backend service for authentication.
    """
    try:
        logger.info(f"Validating credentials for user: {request.email}")

        # Call backend service to validate credentials
        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                f"{settings.BACKEND_SERVICE_URL}/api/v1/auth/centralized/validate-credentials",
                json={"email": request.email, "password": request.password},
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
    Generate JWT token for validated user.
    Called by backend service after credential validation.
    """
    try:
        logger.info(f"Token generation request for user: {request.email}")

        # First validate credentials
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

            # Check if token is expired
            if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
                return TokenValidationResponse(valid=False, user=None)

            # Return user data from token
            user_data = {
                "id": payload["user_id"],
                "email": payload["email"],
                "role": payload["role"],
                "is_admin": payload["is_admin"],
                "client_id": payload["client_id"]
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
