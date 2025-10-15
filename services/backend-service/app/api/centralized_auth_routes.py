"""
Centralized Authentication Integration Routes for Backend Service
Handles token exchange and validation with the centralized auth service
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import httpx
import logging

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.core.database import get_database
from app.auth.auth_service import get_auth_service
from app.models.unified_models import User
import bcrypt

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()

# Pydantic models
class CredentialValidationRequest(BaseModel):
    email: str
    password: str
    include_ml_fields: Optional[bool] = False

class CredentialValidationResponse(BaseModel):
    valid: bool
    user: Optional[Dict[str, Any]] = None

class AuthCodeExchangeRequest(BaseModel):
    code: str
    service_id: str
    redirect_uri: str

class AuthCodeExchangeResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: Dict[str, Any]

class TokenValidationResponse(BaseModel):
    valid: bool
    user: Optional[Dict[str, Any]] = None

@router.post("/validate-credentials", response_model=CredentialValidationResponse)
async def validate_user_credentials(request: CredentialValidationRequest):
    """
    Validate user credentials for centralized auth service.
    This endpoint is called by auth service during login process.
    """
    try:
        logger.info(f"[AUTH] Validating credentials for user (email length: {len(request.email)})")

        database = get_database()
        with database.get_read_session_context() as session:
            # Find user by email
            user = session.query(User).filter(
                User.email == request.email.lower(),
                User.active == True
            ).first()

            if not user:
                logger.warning(f"User not found: {request.email}")
                return CredentialValidationResponse(valid=False, user=None)

            # Verify password
            if not bcrypt.checkpw(request.password.encode('utf-8'), user.password_hash.encode('utf-8')):
                logger.warning(f"Invalid password for user: {request.email}")
                return CredentialValidationResponse(valid=False, user=None)

            # Return user data for token generation with optional ML fields
            user_data = user.to_dict(include_ml_fields=request.include_ml_fields)

            logger.info(f"[AUTH] Credentials validated successfully for user_id: {user.id}")
            return CredentialValidationResponse(valid=True, user=user_data)

    except Exception as e:
        logger.error(f"Error validating credentials: {e}")
        return CredentialValidationResponse(valid=False, user=None)

@router.post("/exchange-code", response_model=AuthCodeExchangeResponse)
async def exchange_authorization_code(request: AuthCodeExchangeRequest):
    """
    Exchange authorization code from centralized auth service for access token.
    This endpoint is called by frontend/ETL services after receiving auth code.
    """
    try:
        logger.info(f"Exchanging authorization code for service: {request.service_id}")
        
        # Get auth service URL from settings
        auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')
        
        # Call centralized auth service to exchange code for token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{auth_service_url}/api/v1/token/exchange",
                json={
                    "code": request.code,
                    "service_id": request.service_id,
                    "redirect_uri": request.redirect_uri
                },
                timeout=10.0
            )
            
            if response.status_code != 200:
                logger.error(f"Auth service token exchange failed: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Authorization code exchange failed"
                )
            
            token_data = response.json()
            logger.info(f"Token exchange successful for user: {token_data['user']['email']}")
            
            # Store session in backend service for future validation
            auth_service = get_auth_service()
            user_data = token_data['user']
            
            # Create or update user session in database/Redis
            # This ensures the token is valid for subsequent requests
            await auth_service.store_session_from_token(
                token=token_data['access_token'],
                user_data=user_data
            )
            
            return AuthCodeExchangeResponse(
                access_token=token_data['access_token'],
                expires_in=token_data['expires_in'],
                user=user_data
            )
            
    except httpx.TimeoutException:
        logger.error("Timeout while contacting auth service")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )
    except httpx.RequestError as e:
        logger.error(f"Request error while contacting auth service: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during token exchange: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token exchange failed"
        )

class TokenValidationRequest(BaseModel):
    token: str
    include_ml_fields: Optional[bool] = False

@router.post("/validate-centralized-token", response_model=TokenValidationResponse)
async def validate_centralized_token(request: TokenValidationRequest):
    """
    Validate token with centralized auth service.
    This is used by other services to validate tokens.
    """
    try:
        token = request.token
        logger.debug(f"[AUTH] Validating centralized token (length: {len(token)})")

        # First check if token is valid locally (Redis/database cache)
        auth_service = get_auth_service()
        user = await auth_service.verify_token(token)
        
        if user:
            logger.debug(f"[AUTH] Token valid locally for user_id: {user.id}")
            return TokenValidationResponse(
                valid=True,
                user=user.to_dict(include_ml_fields=request.include_ml_fields)
            )
        
        # If not valid locally, check with centralized auth service
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
                    logger.debug(f"[AUTH] Token valid via auth service for user_id: {user_data.get('id')}")

                    # Cache the token locally for future requests
                    await auth_service.store_session_from_token(token, user_data)
                    
                    return TokenValidationResponse(
                        valid=True,
                        user=user_data
                    )
            
            logger.debug("Token validation failed via auth service")
            return TokenValidationResponse(valid=False, user=None)
            
    except httpx.TimeoutException:
        logger.warning("Timeout while validating token with auth service - falling back to local validation")
        return TokenValidationResponse(valid=False, user=None)
    except httpx.RequestError as e:
        logger.warning(f"Request error while validating token with auth service: {e}")
        return TokenValidationResponse(valid=False, user=None)
    except Exception as e:
        logger.error(f"Unexpected error during token validation: {e}")
        return TokenValidationResponse(valid=False, user=None)

@router.post("/logout-all-services")
async def logout_all_services(user: User = Depends(get_auth_service().require_authentication)):
    """
    Logout user from all services by invalidating tokens centrally.
    """
    try:
        logger.info(f"Logging out user {user.email} from all services")
        
        # Invalidate local sessions
        auth_service = get_auth_service()
        await auth_service.logout_all_sessions(user.id)
        
        # Notify centralized auth service to invalidate tokens
        auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{auth_service_url}/api/v1/logout",
                json={"user_id": user.id},
                timeout=5.0
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully logged out user {user.email} from all services")
            else:
                logger.warning(f"Failed to notify auth service of logout: {response.status_code}")
        
        return {"message": "Logged out from all services", "success": True}
        
    except Exception as e:
        logger.error(f"Error during multi-service logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )

@router.get("/auth-service-status")
async def check_auth_service_status():
    """
    Check if centralized auth service is available.
    """
    try:
        auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{auth_service_url}/health", timeout=3.0)
            
            if response.status_code == 200:
                return {
                    "status": "available",
                    "auth_service_url": auth_service_url,
                    "response": response.json()
                }
            else:
                return {
                    "status": "unavailable",
                    "auth_service_url": auth_service_url,
                    "error": f"HTTP {response.status_code}"
                }
                
    except Exception as e:
        return {
            "status": "unavailable",
            "auth_service_url": getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000'),
            "error": str(e)
        }
