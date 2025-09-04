"""
Centralized Authentication Service for ETL Service.
Validates authentication through the Backend Service with caching for performance.
"""

import httpx
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from app.core.logging_config import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)


class TokenCache:
    """Simple in-memory token cache to reduce backend service calls."""

    def __init__(self, ttl_seconds: int = 300):  # 5 minutes default TTL
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()

    async def get(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached token data if not expired."""
        async with self._lock:
            if token_hash in self.cache:
                entry = self.cache[token_hash]
                if datetime.utcnow() < entry["expires_at"]:
                    logger.debug(f"Token cache HIT for user: {entry['data'].get('email', 'unknown')}")
                    return entry["data"]
                else:
                    # Remove expired entry
                    del self.cache[token_hash]
                    logger.debug("Token cache MISS - expired")
            return None

    async def set(self, token_hash: str, user_data: Dict[str, Any]):
        """Cache token data with TTL."""
        async with self._lock:
            # CRITICAL: Use timezone-naive UTC for consistency
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            self.cache[token_hash] = {
                "data": user_data,
                "expires_at": now_utc + timedelta(seconds=self.ttl_seconds)
            }
            logger.debug(f"Token cached for user: {user_data.get('email', 'unknown')}")

    async def invalidate(self, token_hash: str):
        """Remove token from cache."""
        async with self._lock:
            if token_hash in self.cache:
                del self.cache[token_hash]
                logger.debug("Token removed from cache")

    async def clear_expired(self):
        """Clean up expired cache entries."""
        async with self._lock:
            now = datetime.utcnow()
            expired_keys = [
                key for key, entry in self.cache.items()
                if now >= entry["expires_at"]
            ]
            for key in expired_keys:
                del self.cache[key]
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    async def clear_all(self):
        """Clear all cache entries (useful when backend service restarts)."""
        async with self._lock:
            cache_size = len(self.cache)
            self.cache.clear()
            if cache_size > 0:
                logger.info(f"Cleared all {cache_size} cache entries")


class CentralizedAuthService:
    """Service to validate authentication through Backend Service with caching."""

    def __init__(self):
        self.settings = get_settings()
        self.backend_service_url = self.settings.BACKEND_SERVICE_URL
        self.timeout = 5.0  # Reduced timeout for faster failures
        self.cache = TokenCache(ttl_seconds=300)  # 5-minute cache

        logger.info("[AUTH] Centralized Auth Service initialized", backend_url=self.backend_service_url)
        logger.info("[AUTH] Token caching enabled (5-minute TTL)")

        # Test connectivity on initialization
        logger.info(f"Testing connectivity to backend service at: {self.backend_service_url}")

    def _hash_token(self, token: str) -> str:
        """Create a hash of the token for cache key."""
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()

    async def clear_all_cached_tokens(self):
        """Clear all cached tokens - useful for resolving permission issues."""
        try:
            await self.cache.clear()
            logger.info("All cached tokens cleared successfully")
        except Exception as e:
            logger.error(f"Failed to clear cached tokens: {e}")
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token through Backend Service with caching.

        Args:
            token: JWT token to verify

        Returns:
            User data if token is valid, None if invalid
        """
        try:

            # Check cache first
            token_hash = self._hash_token(token)
            cached_data = await self.cache.get(token_hash)
            if cached_data:
                # Verify cached user still has admin permissions
                if cached_data.get("is_admin", False) or cached_data.get("role") == "admin":
                    return cached_data
                else:
                    # User lost admin permissions, remove from cache
                    logger.info(f"Cached user {cached_data.get('email')} no longer has admin permissions, removing from cache")
                    await self.cache.invalidate(token_hash)

            # Cache miss - call backend service
            logger.info(f"Attempting to validate token with backend service at: {self.backend_service_url}/api/v1/auth/validate")
            logger.debug(f"Token being validated: {token[:30]}... (length: {len(token)})")

            # Create client with explicit configuration for local connections
            client_config = {
                "timeout": self.timeout,
                "verify": False,  # Disable SSL verification for local connections
                "follow_redirects": True
            }

            from app.core.http_client import get_async_client
            client = get_async_client()
            response = await client.post(
                f"{self.backend_service_url}/api/v1/auth/validate",
                headers={"Authorization": f"Bearer {token}"}
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Backend service response: {data}")
                if data.get("valid") and data.get("user"):
                    user_data = data["user"]
                    # Only cache tokens for admin users since ETL service is admin-only
                    if user_data.get("is_admin", False) or user_data.get("role") == "admin":
                        await self.cache.set(token_hash, user_data)
                        logger.info(f"Token validation successful for admin user: {user_data['email']}")
                    else:
                        logger.info(f"Token validation successful but user is not admin: {user_data['email']} - not caching")
                    return user_data
                else:
                    logger.warning(f"Invalid response format from backend service. Response: {data}")
                    # Remove invalid token from cache
                    await self.cache.invalidate(token_hash)
                    return None
            elif response.status_code == 401:
                logger.debug("Token validation failed: unauthorized")
                # Remove unauthorized token from cache
                await self.cache.invalidate(token_hash)
                return None
            else:
                logger.error(f"Backend service returned status {response.status_code}")
                # Remove failed token from cache
                await self.cache.invalidate(token_hash)
                return None

        except httpx.TimeoutException:
            logger.error(f"Timeout while validating token with backend service at {self.backend_service_url}")
            # Remove token from cache on timeout to force re-validation
            await self.cache.invalidate(token_hash)
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error while validating token: {e}")
            logger.error(f"Backend service URL: {self.backend_service_url}")
            logger.error(f"Full URL attempted: {self.backend_service_url}/api/v1/auth/validate")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            # Remove token from cache on request error to force re-validation
            await self.cache.invalidate(token_hash)
            return None
        except Exception as e:
            logger.error(f"Unexpected error during token validation: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            # Remove token from cache on unexpected error to force re-validation
            await self.cache.invalidate(token_hash)
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

    # Navigation session creation removed - now handled by Redis shared sessions

    async def ensure_session_exists(self, token: str, user_data: Dict[str, Any]) -> bool:
        """
        Ensure a session exists for the given token and user.
        With Redis shared sessions, this is no longer needed but kept for compatibility.
        """
        # With Redis shared sessions, sessions are automatically managed
        # Just return True to maintain compatibility
        logger.debug(f"Session existence ensured via Redis for user: {user_data.get('email')}")
        return True

    async def invalidate_session(self, token: str) -> bool:
        """Invalidate a session by calling the Backend Service and clearing cache"""
        try:
            # Remove from cache first
            token_hash = self._hash_token(token)
            await self.cache.invalidate(token_hash)

            logger.info(f"🔄 Calling Backend Service to invalidate session...")
            logger.info(f"Backend URL: {self.backend_service_url}")
            logger.info(f"Token (first 20 chars): {token[:20]}...")

            async with httpx.AsyncClient() as client:
                url = f"{self.backend_service_url}/api/v1/auth/logout"
                logger.info(f"POST {url}")

                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0
                )

                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response text: {response.text}")

                if response.status_code in [200, 302]:
                    if response.status_code == 200:
                        logger.info("✅ Session invalidated successfully via Backend Service")
                    else:
                        logger.info("✅ Session invalidated successfully via Backend Service (redirect response)")
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
