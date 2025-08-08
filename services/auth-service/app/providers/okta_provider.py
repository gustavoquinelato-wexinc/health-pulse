"""
OKTA Authentication Provider
Handles authentication against OKTA identity provider
"""

import httpx
from typing import Dict, Any, Optional
from urllib.parse import urlencode
from .base_provider import BaseAuthProvider, AuthenticationResult
import logging

logger = logging.getLogger(__name__)

class OktaAuthProvider(BaseAuthProvider):
    """OKTA authentication provider"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.okta_domain = config.get("okta_domain")  # e.g., "dev-123456.okta.com"
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        # Import settings to get environment variables
        from app.core.config import get_settings
        settings = get_settings()

        self.backend_service_url = config.get("backend_service_url", settings.BACKEND_SERVICE_URL)
        
        if not all([self.okta_domain, self.client_id, self.client_secret]):
            logger.warning("OKTA provider not fully configured")
    
    async def authenticate(self, email: str, password: str) -> AuthenticationResult:
        """
        OKTA doesn't support direct password authentication in OAuth flow.
        This method is not used for OKTA - use OAuth flow instead.
        """
        return AuthenticationResult(
            success=False,
            error_message="OKTA requires OAuth flow - use get_oauth_url() instead"
        )
    
    async def get_user_info(self, provider_user_id: str) -> Optional[Dict[str, Any]]:
        """Get user info from OKTA"""
        try:
            # This would require an OKTA API token
            # For now, return None - user info comes from OAuth callback
            return None
            
        except Exception as e:
            logger.error(f"Error getting OKTA user info: {e}")
            return None
    
    def get_oauth_url(self, state: str, redirect_uri: str) -> str:
        """Get OKTA OAuth authorization URL"""
        if not self.okta_domain or not self.client_id:
            raise ValueError("OKTA not properly configured")
        
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": "openid profile email",
            "redirect_uri": redirect_uri,
            "state": state
        }
        
        auth_url = f"https://{self.okta_domain}/oauth2/default/v1/authorize"
        return f"{auth_url}?{urlencode(params)}"
    
    async def handle_oauth_callback(self, code: str, state: str) -> AuthenticationResult:
        """Handle OAuth callback from OKTA"""
        try:
            if not all([self.okta_domain, self.client_id, self.client_secret]):
                return AuthenticationResult(
                    success=False,
                    error_message="OKTA not properly configured"
                )
            
            # Exchange authorization code for access token
            token_url = f"https://{self.okta_domain}/oauth2/default/v1/token"
            
            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    token_url,
                    data={
                        "grant_type": "authorization_code",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "redirect_uri": settings.OKTA_REDIRECT_URI  # From environment variable
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10.0
                )
                
                if token_response.status_code != 200:
                    logger.error(f"OKTA token exchange failed: {token_response.text}")
                    return AuthenticationResult(
                        success=False,
                        error_message="OKTA token exchange failed"
                    )
                
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                
                # Get user info from OKTA
                userinfo_response = await client.get(
                    f"https://{self.okta_domain}/oauth2/default/v1/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=5.0
                )
                
                if userinfo_response.status_code != 200:
                    logger.error(f"OKTA userinfo failed: {userinfo_response.text}")
                    return AuthenticationResult(
                        success=False,
                        error_message="Failed to get user info from OKTA"
                    )
                
                okta_user_data = userinfo_response.json()
                
                # Map OKTA user data to internal format
                mapped_user_data = self.map_user_data(okta_user_data)
                
                # Check if user exists in local system, create if not
                local_user_data = await self._ensure_local_user(mapped_user_data)
                
                return AuthenticationResult(
                    success=True,
                    user_data=local_user_data,
                    provider_data=okta_user_data
                )
                
        except Exception as e:
            logger.error(f"OKTA OAuth callback error: {e}")
            return AuthenticationResult(
                success=False,
                error_message="OKTA authentication failed"
            )
    
    def map_user_data(self, provider_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map OKTA user data to internal format"""
        return {
            "email": provider_data.get("email"),
            "first_name": provider_data.get("given_name", ""),
            "last_name": provider_data.get("family_name", ""),
            "provider": "okta",
            "provider_user_id": provider_data.get("sub"),  # OKTA user ID
            "is_active": True,
            "okta_data": provider_data  # Store original OKTA data
        }
    
    async def _ensure_local_user(self, mapped_user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure user exists in local system, create if not"""
        try:
            # Call backend service to create/update user from OKTA data
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.backend_service_url}/api/v1/auth/centralized/sync-okta-user",
                    json=mapped_user_data,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()["user"]
                else:
                    logger.error(f"Failed to sync OKTA user: {response.text}")
                    # Return mapped data as fallback
                    return mapped_user_data
                    
        except Exception as e:
            logger.error(f"Error syncing OKTA user: {e}")
            return mapped_user_data
    
    def get_display_name(self) -> str:
        """Display name for OKTA provider"""
        return "OKTA Single Sign-On"
