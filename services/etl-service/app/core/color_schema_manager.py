"""
Smart Color Schema Manager for ETL Service
Provides efficient color schema loading with caching and fallback mechanisms.
"""

import time
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

import httpx
from app.core.logging_config import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)


class ColorSchemaManager:
    """
    Smart color schema manager with caching and anti-infinite-loop safeguards.
    
    Features:
    - 5-minute cache TTL to reduce database load
    - Rate limiting to prevent infinite loops
    - Circuit breaker for failure handling
    - Fallback to cached/default values
    """
    
    def __init__(self):
        # Cache configuration - now user-specific
        self.cache_ttl = 300  # 5 minutes in seconds
        self.user_caches: Dict[str, Dict[str, Any]] = {}  # user_id -> cache data
        self.max_cached_users = 100  # Maximum number of users to cache
        self.cleanup_interval = 600  # Cleanup every 10 minutes
        self.last_cleanup_time: Optional[float] = None
        
        # Rate limiting (anti-infinite-loop) - reduced for better responsiveness
        self.min_fetch_interval = 5  # Minimum 5 seconds between fetches (was 30)
        self.last_attempt_time: Optional[float] = None
        
        # Circuit breaker
        self.failure_count = 0
        self.max_failures = 3
        self.circuit_open_duration = 300  # 5 minutes
        self.circuit_opened_at: Optional[float] = None
        
        # Default fallback schema
        self.default_schema = {
            "success": True,
            "mode": "default",
            "colors": {
                "color1": "#2862EB",
                "color2": "#763DED",
                "color3": "#059669",
                "color4": "#0EA5E9",
                "color5": "#F59E0B"
            },
            "theme": "light"
        }
        
        logger.info("🎨 ColorSchemaManager initialized with smart caching")
    
    def is_cache_valid(self, user_id: str) -> bool:
        """Check if cached data is still valid for a specific user"""
        if user_id not in self.user_caches:
            return False

        user_cache = self.user_caches[user_id]
        if not user_cache.get('schema') or not user_cache.get('last_fetch_time'):
            return False

        age = time.time() - user_cache['last_fetch_time']
        return age < self.cache_ttl
    
    def is_rate_limited(self) -> bool:
        """Check if we're rate limited (anti-infinite-loop)"""
        if not self.last_attempt_time:
            return False
        
        time_since_last = time.time() - self.last_attempt_time
        return time_since_last < self.min_fetch_interval
    
    def is_circuit_open(self) -> bool:
        """Check if circuit breaker is open due to failures"""
        if not self.circuit_opened_at:
            return False
        
        time_since_opened = time.time() - self.circuit_opened_at
        if time_since_opened > self.circuit_open_duration:
            # Reset circuit breaker
            self.circuit_opened_at = None
            self.failure_count = 0
            logger.info("🔄 Circuit breaker reset - attempting color schema fetch")
            return False
        
        return True
    
    def record_success(self):
        """Record successful fetch"""
        self.failure_count = 0
        self.circuit_opened_at = None
        self.last_fetch_time = time.time()
        logger.debug("✅ Color schema fetch successful")
    
    def record_failure(self):
        """Record failed fetch and potentially open circuit"""
        self.failure_count += 1
        self.last_attempt_time = time.time()
        
        if self.failure_count >= self.max_failures:
            self.circuit_opened_at = time.time()
            logger.warning(f"🚨 Circuit breaker opened after {self.failure_count} failures")
        else:
            logger.warning(f"⚠️ Color schema fetch failed ({self.failure_count}/{self.max_failures})")
    
    async def fetch_from_backend(self, auth_token: str) -> Optional[Dict[str, Any]]:
        """Fetch color schema from backend service with enhanced color support"""
        settings = get_settings()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try user-specific colors first (includes accessibility preferences)
                user_response = await client.get(
                    f"{settings.BACKEND_SERVICE_URL}/api/v1/user/colors",
                    headers={"Authorization": f"Bearer {auth_token}"}
                )

                if user_response.status_code == 200:
                    user_data = user_response.json()
                    if user_data.get("success"):
                        colors = user_data.get("colors", {})
                        user_prefs = user_data.get("user_preferences", {})

                        # Get theme mode
                        theme_response = await client.get(
                            f"{settings.BACKEND_SERVICE_URL}/api/v1/user/theme-mode",
                            headers={"Authorization": f"Bearer {auth_token}"}
                        )

                        theme_mode = 'light'  # default
                        if theme_response.status_code == 200:
                            theme_data = theme_response.json()
                            if theme_data.get('success'):
                                theme_mode = theme_data.get('mode', 'light')

                        # Transform user colors to expected format
                        return {
                            "success": True,
                            "mode": colors.get("resolved_mode", "custom"),
                            "colors": {
                                "color1": colors.get("color1"),
                                "color2": colors.get("color2"),
                                "color3": colors.get("color3"),
                                "color4": colors.get("color4"),
                                "color5": colors.get("color5")
                            },
                            "on_colors": {
                                "color1": colors.get("on_color1"),
                                "color2": colors.get("on_color2"),
                                "color3": colors.get("on_color3"),
                                "color4": colors.get("on_color4"),
                                "color5": colors.get("on_color5")
                            },
                            "on_gradients": {
                                "1-2": colors.get("on_gradient_1_2"),
                                "2-3": colors.get("on_gradient_2_3"),
                                "3-4": colors.get("on_gradient_3_4"),
                                "4-5": colors.get("on_gradient_4_5"),
                                "5-1": colors.get("on_gradient_5_1")
                            },
                            "theme": theme_mode,
                            "enhanced": True,
                            "user_preferences": user_prefs,
                            "source": "user_specific_colors"
                        }

                # Fallback to admin color schema (use unified API)
                logger.debug("User colors not available, falling back to admin unified color schema")
                response = await client.get(
                    f"{settings.BACKEND_SERVICE_URL}/api/v1/admin/color-schema/unified",
                    headers={"Authorization": f"Bearer {auth_token}"}
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get("success") and data.get("color_data"):
                        # Get theme mode
                        theme_response = await client.get(
                            f"{settings.BACKEND_SERVICE_URL}/api/v1/user/theme-mode",
                            headers={"Authorization": f"Bearer {auth_token}"}
                        )

                        theme_mode = 'light'  # default
                        if theme_response.status_code == 200:
                            theme_data = theme_response.json()
                            if theme_data.get('success'):
                                theme_mode = theme_data.get('mode', 'light')

                        # Process unified color data
                        color_data = data.get("color_data", [])
                        light_regular = next((c for c in color_data if c.get('theme_mode') == 'light' and c.get('accessibility_level') == 'regular'), None)
                        dark_regular = next((c for c in color_data if c.get('theme_mode') == 'dark' and c.get('accessibility_level') == 'regular'), None)

                        # Use colors based on current theme
                        current_colors = light_regular if theme_mode == 'light' else dark_regular
                        if not current_colors:
                            current_colors = light_regular or dark_regular  # fallback

                        if current_colors:
                            # Combine color schema and theme data
                            return {
                                "success": True,
                                "mode": data.get("color_schema_mode", "default"),
                                "colors": {
                                    "color1": current_colors.get("color1"),
                                    "color2": current_colors.get("color2"),
                                    "color3": current_colors.get("color3"),
                                    "color4": current_colors.get("color4"),
                                    "color5": current_colors.get("color5")
                                },
                                "on_colors": {
                                    "color1": current_colors.get("on_color1"),
                                    "color2": current_colors.get("on_color2"),
                                    "color3": current_colors.get("on_color3"),
                                    "color4": current_colors.get("on_color4"),
                                    "color5": current_colors.get("on_color5")
                                },
                                "on_gradients": {
                                    "1-2": current_colors.get("on_gradient_1_2"),
                                    "2-3": current_colors.get("on_gradient_2_3"),
                                    "3-4": current_colors.get("on_gradient_3_4"),
                                    "4-5": current_colors.get("on_gradient_4_5"),
                                    "5-1": current_colors.get("on_gradient_5_1")
                                },
                                "theme": theme_mode,
                                "enhanced": True,
                                "source": "admin_unified_color_schema"
                            }

                logger.warning(f"Backend returned non-success response: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Failed to fetch color schema from backend: {e}")
            return None
    
    async def get_color_schema(self, auth_token: Optional[str] = None, user_id: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get color schema with smart caching and fallback mechanisms.

        Args:
            auth_token: Authentication token for backend API
            user_id: User ID for user-specific caching
            force_refresh: Force refresh even if cache is valid

        Returns:
            Color schema data with fallback to cached/default values
        """
        current_time = time.time()
        self.last_attempt_time = current_time

        # Default user_id if not provided
        if not user_id:
            user_id = "default"

        # Perform periodic cache maintenance
        self.perform_cache_maintenance()

        # Use cache if valid and not forced refresh
        if not force_refresh and self.is_cache_valid(user_id):
            logger.debug(f"📋 Using cached color schema for user {user_id}")
            return self.user_caches[user_id]['schema']
        
        # Get user's cached data if available
        user_cached_schema = None
        if user_id in self.user_caches:
            user_cached_schema = self.user_caches[user_id]['schema']

        # Check rate limiting (anti-infinite-loop) - but allow fresh fetch if no cached data
        if not force_refresh and self.is_rate_limited() and user_cached_schema:
            logger.debug(f"⏱️ Rate limited - using cached schema for user {user_id}")
            return user_cached_schema

        # Check circuit breaker - but allow fresh fetch if no cached data
        if self.is_circuit_open() and user_cached_schema:
            logger.debug(f"🚨 Circuit breaker open - using cached schema for user {user_id}")
            return user_cached_schema

        # Try to fetch fresh data
        if auth_token:
            logger.debug(f"🔄 Fetching fresh color schema from backend for user {user_id}")
            fresh_schema = await self.fetch_from_backend(auth_token)

            if fresh_schema:
                # Store in user-specific cache
                self.user_caches[user_id] = {
                    'schema': fresh_schema,
                    'last_fetch_time': time.time()
                }
                self.record_success()
                logger.info(f"✅ Color schema updated from backend for user {user_id}")
                return fresh_schema
            else:
                self.record_failure()
        else:
            logger.debug("🔑 No auth token provided - using cached or default schema")

        # Fallback to cached data or default
        fallback = user_cached_schema or self.default_schema
        logger.debug(f"📋 Using fallback color schema for user {user_id}")
        return fallback
    
    def cleanup_expired_caches(self):
        """Remove expired cache entries to manage memory"""
        current_time = time.time()
        expired_users = []

        for user_id, cache_data in self.user_caches.items():
            last_fetch = cache_data.get('last_fetch_time', 0)
            if current_time - last_fetch > self.cache_ttl:
                expired_users.append(user_id)

        for user_id in expired_users:
            del self.user_caches[user_id]
            logger.debug(f"🧹 Removed expired cache for user {user_id}")

        if expired_users:
            logger.info(f"🧹 Cleaned up {len(expired_users)} expired user caches")

        self.last_cleanup_time = current_time

    def enforce_cache_limits(self):
        """Enforce maximum cache size by removing oldest entries"""
        if len(self.user_caches) <= self.max_cached_users:
            return

        # Sort by last_fetch_time and remove oldest entries
        sorted_users = sorted(
            self.user_caches.items(),
            key=lambda x: x[1].get('last_fetch_time', 0)
        )

        users_to_remove = len(self.user_caches) - self.max_cached_users
        for i in range(users_to_remove):
            user_id = sorted_users[i][0]
            del self.user_caches[user_id]
            logger.debug(f"🧹 Removed cache for user {user_id} (cache limit)")

        logger.info(f"🧹 Enforced cache limit: removed {users_to_remove} oldest user caches")

    def perform_cache_maintenance(self):
        """Perform periodic cache maintenance"""
        current_time = time.time()

        # Only run cleanup if enough time has passed
        if (self.last_cleanup_time is None or
            current_time - self.last_cleanup_time > self.cleanup_interval):

            self.cleanup_expired_caches()
            self.enforce_cache_limits()

    def invalidate_cache(self, user_id: Optional[str] = None):
        """Manually invalidate cache (for future event-driven updates)"""
        if user_id:
            # Invalidate specific user's cache
            if user_id in self.user_caches:
                del self.user_caches[user_id]
                logger.info(f"🗑️ Color schema cache invalidated for user {user_id}")
        else:
            # Invalidate all user caches
            self.user_caches.clear()
            logger.info("🗑️ All color schema caches invalidated")
    
    def get_cache_info(self, user_id: str = "default") -> Dict[str, Any]:
        """Get cache status information for debugging"""
        current_time = time.time()

        cache_age = None
        if user_id in self.user_caches and self.user_caches[user_id].get('last_fetch_time'):
            cache_age = current_time - self.user_caches[user_id]['last_fetch_time']

        return {
            "user_id": user_id,
            "cache_valid": self.is_cache_valid(user_id),
            "cache_age_seconds": cache_age,
            "rate_limited": self.is_rate_limited(),
            "circuit_open": self.is_circuit_open(),
            "total_cached_users": len(self.user_caches),
            "failure_count": self.failure_count,
            "has_cached_data": self.cached_schema is not None
        }


# Global instance
_color_schema_manager: Optional[ColorSchemaManager] = None


def get_color_schema_manager() -> ColorSchemaManager:
    """Get the global color schema manager instance"""
    global _color_schema_manager
    if _color_schema_manager is None:
        _color_schema_manager = ColorSchemaManager()
    return _color_schema_manager
