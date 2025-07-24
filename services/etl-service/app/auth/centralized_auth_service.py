"""
Centralized Authentication Service for ETL Service.
Validates authentication through the Backend Service instead of local auth.
"""

import httpx
from typing import Optional, Dict, Any
from app.core.logging_config import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)


class CentralizedAuthService:
    """Service to validate authentication through Backend Service."""
    
    def __init__(self):
        self.settings = get_settings()
        self.backend_service_url = self.settings.BACKEND_SERVICE_URL
        self.timeout = 10.0
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token through Backend Service.
        
        Args:
            token: JWT token to verify
            
        Returns:
            User data if token is valid, None if invalid
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.backend_service_url}/api/v1/auth/validate-service",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("valid") and data.get("user"):
                        logger.debug(f"Token validation successful for user: {data['user']['email']}")
                        return data["user"]
                    else:
                        logger.warning("Invalid response format from backend service")
                        return None
                elif response.status_code == 401:
                    logger.debug("Token validation failed: unauthorized")
                    return None
                else:
                    logger.error(f"Backend service returned status {response.status_code}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error("Timeout while validating token with backend service")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error while validating token: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during token validation: {e}")
            return None
    
    async def validate_user_permissions(self, user_data: Dict[str, Any], required_role: str = None) -> bool:
        """
        Validate user permissions based on user data from backend service.
        
        Args:
            user_data: User data returned from verify_token
            required_role: Required role for access (optional)
            
        Returns:
            True if user has required permissions
        """
        try:
            if not user_data or not user_data.get("active"):
                return False
            
            if required_role:
                user_role = user_data.get("role", "").lower()
                required_role = required_role.lower()
                
                # Admin can access everything
                if user_data.get("is_admin"):
                    return True
                
                # Check specific role requirements
                if required_role == "admin" and not user_data.get("is_admin"):
                    return False
                
                # For now, allow any active user to access ETL functions
                # This can be expanded with more granular permissions later
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating user permissions: {e}")
            return False

    async def invalidate_session(self, token: str) -> bool:
        """Invalidate a session by calling the Backend Service"""
        try:
            import httpx

            logger.info(f"🔄 Calling Backend Service to invalidate session...")
            logger.info(f"Backend URL: {self.backend_url}")
            logger.info(f"Token (first 20 chars): {token[:20]}...")

            async with httpx.AsyncClient() as client:
                url = f"{self.backend_url}/api/v1/admin/auth/invalidate-session"
                logger.info(f"POST {url}")

                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0
                )

                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response text: {response.text}")

                if response.status_code == 200:
                    logger.info("✅ Session invalidated successfully via Backend Service")
                    return True
                else:
                    logger.warning(f"❌ Failed to invalidate session: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            logger.error(f"❌ Error invalidating session: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False


# Global instance
_centralized_auth_service = None


def get_centralized_auth_service() -> CentralizedAuthService:
    """Get the global centralized auth service instance."""
    global _centralized_auth_service
    if _centralized_auth_service is None:
        _centralized_auth_service = CentralizedAuthService()
    return _centralized_auth_service
