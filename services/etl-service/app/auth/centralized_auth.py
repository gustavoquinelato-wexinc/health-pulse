"""
Centralized Authentication Integration for ETL Service
Handles OAuth-like flow with centralized auth service
"""

import os
import httpx
import secrets
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
import logging

logger = logging.getLogger(__name__)

class CentralizedAuthManager:
    """Manages centralized authentication for ETL service"""
    
    def __init__(self):
        self.auth_service_url = os.getenv('AUTH_SERVICE_URL', 'http://localhost:4000')
        self.backend_service_url = os.getenv('BACKEND_SERVICE_URL', 'http://localhost:3001')
        self.etl_service_url = os.getenv('ETL_SERVICE_URL', 'http://localhost:8000')
        self.service_id = 'etl'
        self.callback_uri = f"{self.etl_service_url}/auth/callback"
    
    def generate_auth_url(self, redirect_after_login: str = "/home") -> str:
        """Generate URL to redirect user to centralized auth service"""
        state = self._generate_state()
        
        # Store state and redirect info (in production, use Redis)
        # For now, we'll pass it in the state parameter
        auth_url = f"{self.auth_service_url}/login"
        auth_url += f"?service={self.service_id}"
        auth_url += f"&redirect_uri={self.callback_uri}"
        auth_url += f"&state={state}:{redirect_after_login}"
        
        logger.info(f"Generated auth URL: {auth_url}")
        return auth_url
    
    async def handle_auth_callback(self, code: str, state: str) -> Dict[str, Any]:
        """Handle callback from centralized auth service"""
        try:
            # Parse state to get redirect info
            state_parts = state.split(':', 1)
            if len(state_parts) != 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid state parameter"
                )
            
            state_token, redirect_after_login = state_parts
            
            # Exchange authorization code for access token
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.backend_service_url}/api/v1/auth/centralized/exchange-code",
                    json={
                        "code": code,
                        "service_id": self.service_id,
                        "redirect_uri": self.callback_uri
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Authorization code exchange failed"
                    )
                
                token_data = response.json()
                logger.info(f"Token exchange successful for user: {token_data['user']['email']}")
                
                return {
                    "access_token": token_data["access_token"],
                    "user": token_data["user"],
                    "redirect_to": redirect_after_login
                }
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Auth callback error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication callback failed"
            )
    
    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate token with backend service"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.backend_service_url}/api/v1/auth/validate",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("valid"):
                        return data.get("user")
                
                return None
                
        except Exception as e:
            logger.warning(f"Token validation failed: {e}")
            return None
    
    async def logout_all_services(self, token: str) -> bool:
        """Logout user from all services"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.backend_service_url}/api/v1/auth/centralized/logout-all-services",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0
                )
                
                return response.status_code == 200
                
        except Exception as e:
            logger.warning(f"Multi-service logout failed: {e}")
            return False
    
    def _generate_state(self) -> str:
        """Generate random state for CSRF protection"""
        return secrets.token_urlsafe(32)

# Global instance
centralized_auth = CentralizedAuthManager()

def get_centralized_auth() -> CentralizedAuthManager:
    """Get centralized auth manager instance"""
    return centralized_auth

async def require_centralized_auth(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency to require centralized authentication.
    Returns user data if authenticated, redirects to auth service if not.
    """
    # Check for token in cookies
    token = request.cookies.get('pulse_token')
    
    if not token:
        # No token, redirect to auth service
        auth_url = centralized_auth.generate_auth_url(str(request.url.path))
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            detail="Authentication required",
            headers={"Location": auth_url}
        )
    
    # Validate token
    user = await centralized_auth.validate_token(token)
    if not user:
        # Invalid token, redirect to auth service
        auth_url = centralized_auth.generate_auth_url(str(request.url.path))
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            detail="Authentication required",
            headers={"Location": auth_url}
        )
    
    return user

def create_auth_redirect(auth_url: str) -> RedirectResponse:
    """Create redirect response to auth service"""
    return RedirectResponse(url=auth_url, status_code=302)
