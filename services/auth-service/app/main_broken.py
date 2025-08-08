"""
Centralized Authentication Service - API Only
Pure backend service for authentication validation and token management
No UI components - all authentication flows handled by other services
"""

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import jwt
from datetime import datetime, timedelta
import logging
import httpx
from pydantic_settings import BaseSettings

# Initialize FastAPI app
app = FastAPI(
    title="Pulse Authentication Service - API Only",
    description="Backend authentication validation service for Pulse Platform",
    version="1.0.0"
)

# Simple configuration for auth service
class AuthServiceSettings(BaseSettings):
    JWT_SECRET_KEY: str = "A-JdcapOLIm3zoYtTkxA1vTMyNt7EEvH7jHCuDjAmqw"  # Same as backend
    JWT_ALGORITHM: str = "HS256"
    BACKEND_SERVICE_URL: str = "http://localhost:3001"

    # Provider configuration
    ENABLE_LOCAL_AUTH: bool = True
    ENABLE_OKTA_AUTH: bool = False
    OKTA_DOMAIN: str = ""
    OKTA_CLIENT_ID: str = ""
    OKTA_CLIENT_SECRET: str = ""

    class Config:
        env_file = "../../../.env"

settings = AuthServiceSettings()

# Simplified authentication - direct backend service calls
# Provider system can be added later

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure CORS for cross-domain requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Frontend
        "http://localhost:8000",  # ETL Service
        "http://localhost:3001",  # Backend Service
        "https://app.company.com",  # Production Frontend
        "https://etl.company.com",  # Production ETL
        "https://api.company.com",  # Production Backend
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# No UI components - API only service

# No OAuth flow - direct API-only authentication

# Pydantic models
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: Dict[str, Any]

# Utility functions
def generate_jwt_token(user_data: Dict[str, Any]) -> str:
    """Generate JWT token for authenticated user"""
    payload = {
        "user_id": user_data["id"],
        "email": user_data["email"],
        "role": user_data["role"],
        "is_admin": user_data["is_admin"],
        "client_id": user_data["client_id"],
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow(),
        "iss": "pulse-auth-service"
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

# No OAuth validation needed - direct API calls only

# Routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "auth-service"}

# ============================================================================
# API ENDPOINTS - No UI, pure backend service
# ============================================================================

class CredentialValidationRequest(BaseModel):
    email: str
    password: str

class CredentialValidationResponse(BaseModel):
    valid: bool
    user: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

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
            expires_in=24 * 60 * 60,  # 24 hours
            user=validation_result.user
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token exchange error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token exchange failed"
        )

@app.post("/api/v1/token/validate")
async def validate_token(request: Request):
    """Validate JWT token"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return {"valid": False, "user": None}

        token = auth_header.split(" ")[1]

        # Decode and validate JWT token
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

            # Check if token is expired
            if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
                return {"valid": False, "user": None}

            # Return user data from token
            user_data = {
                "id": payload["user_id"],
                "email": payload["email"],
                "role": payload["role"],
                "is_admin": payload["is_admin"],
                "client_id": payload["client_id"]
            }

            return {"valid": True, "user": user_data}

        except jwt.InvalidTokenError:
            return {"valid": False, "user": None}

    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return {"valid": False, "user": None}

@app.post("/api/v1/logout")
async def logout_api(request: Request):
    """API logout endpoint - invalidate tokens"""
    try:
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

# No logout page - API only service

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4000)
