"""
Local Authentication Provider
Handles authentication against the backend service database
"""

import httpx
from typing import Dict, Any, Optional
from .base_provider import BaseAuthProvider, AuthenticationResult
import logging

logger = logging.getLogger(__name__)

class LocalAuthProvider(BaseAuthProvider):
    """Local authentication provider using backend service"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Import settings to get environment variables
        from app.core.config import get_settings
        settings = get_settings()

        self.backend_service_url = config.get("backend_service_url", settings.BACKEND_SERVICE_URL)
    
    async def authenticate(self, email: str, password: str) -> AuthenticationResult:
        """Authenticate user against backend service"""
        try:
            async with httpx.AsyncTenant() as client:
                response = await client.post(
                    f"{self.backend_service_url}/api/v1/auth/centralized/validate-credentials",
                    json={"email": email, "password": password},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("valid"):
                        return AuthenticationResult(
                            success=True,
                            user_data=data["user"],
                            provider_data={"source": "local_database"}
                        )
                
                return AuthenticationResult(
                    success=False,
                    error_message="Invalid credentials"
                )
                
        except Exception as e:
            logger.error(f"Local authentication error: {e}")
            return AuthenticationResult(
                success=False,
                error_message="Authentication service unavailable"
            )
    
    async def get_user_info(self, provider_user_id: str) -> Optional[Dict[str, Any]]:
        """Get user info from backend service"""
        try:
            async with httpx.AsyncTenant() as client:
                response = await client.get(
                    f"{self.backend_service_url}/api/v1/users/{provider_user_id}",
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    return response.json()
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None
    
    def get_oauth_url(self, state: str, redirect_uri: str) -> str:
        """Local provider doesn't use OAuth"""
        raise NotImplementedError("Local provider doesn't support OAuth")
    
    async def handle_oauth_callback(self, code: str, state: str) -> AuthenticationResult:
        """Local provider doesn't use OAuth"""
        raise NotImplementedError("Local provider doesn't support OAuth")
    
    def map_user_data(self, provider_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map local user data (already in correct format)"""
        return provider_data
    
    def get_display_name(self) -> str:
        """Display name for local provider"""
        return "Local Database"
