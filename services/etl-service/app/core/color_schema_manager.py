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
        # Cache configuration
        self.cache_ttl = 300  # 5 minutes in seconds
        self.cached_schema: Optional[Dict[str, Any]] = None
        self.last_fetch_time: Optional[float] = None
        
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
                "color1": "#C8102E",  # Red
                "color2": "#253746",  # Dark Blue
                "color3": "#00C7B1",  # Teal
                "color4": "#A2DDF8",  # Light Blue
                "color5": "#FFBF3F"   # Yellow
            },
            "theme": "light"
        }
        
        logger.info("🎨 ColorSchemaManager initialized with smart caching")
    
    def is_cache_valid(self) -> bool:
        """Check if cached data is still valid"""
        if not self.cached_schema or not self.last_fetch_time:
            return False
        
        age = time.time() - self.last_fetch_time
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
        """Fetch color schema from backend service"""
        settings = get_settings()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.BACKEND_SERVICE_URL}/api/v1/admin/color-schema",
                    headers={"Authorization": f"Bearer {auth_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()

                    if data.get("success"):
                        # Also get theme mode
                        theme_response = await client.get(
                            f"{settings.BACKEND_SERVICE_URL}/api/v1/admin/theme-mode",
                            headers={"Authorization": f"Bearer {auth_token}"}
                        )

                        theme_mode = 'light'  # default
                        if theme_response.status_code == 200:
                            theme_data = theme_response.json()
                            if theme_data.get('success'):
                                theme_mode = theme_data.get('mode', 'light')

                        # Combine color schema and theme data
                        return {
                            "success": True,
                            "mode": data.get("mode", "default"),
                            "colors": data.get("colors", {}),
                            "theme": theme_mode
                        }
                
                logger.warning(f"Backend returned non-success response: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to fetch color schema from backend: {e}")
            return None
    
    async def get_color_schema(self, auth_token: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get color schema with smart caching and fallback mechanisms.
        
        Args:
            auth_token: Authentication token for backend API
            force_refresh: Force refresh even if cache is valid
            
        Returns:
            Color schema data with fallback to cached/default values
        """
        current_time = time.time()
        self.last_attempt_time = current_time
        
        # Use cache if valid and not forced refresh
        if not force_refresh and self.is_cache_valid():
            logger.debug("📋 Using cached color schema")
            return self.cached_schema
        
        # Check rate limiting (anti-infinite-loop) - but allow fresh fetch if no cached data
        if not force_refresh and self.is_rate_limited() and self.cached_schema:
            logger.debug("⏱️ Rate limited - using cached schema")
            return self.cached_schema
        
        # Check circuit breaker - but allow fresh fetch if no cached data
        if self.is_circuit_open() and self.cached_schema:
            logger.debug("🚨 Circuit breaker open - using cached schema")
            return self.cached_schema
        
        # Try to fetch fresh data
        if auth_token:
            logger.debug("🔄 Fetching fresh color schema from backend")
            fresh_schema = await self.fetch_from_backend(auth_token)
            
            if fresh_schema:
                self.cached_schema = fresh_schema
                self.record_success()
                logger.info("✅ Color schema updated from backend")
                return fresh_schema
            else:
                self.record_failure()
        else:
            logger.debug("🔑 No auth token provided - using cached or default schema")
        
        # Fallback to cached data or default
        fallback = self.cached_schema or self.default_schema
        logger.debug("📋 Using fallback color schema")
        return fallback
    
    def invalidate_cache(self):
        """Manually invalidate cache (for future event-driven updates)"""
        self.last_fetch_time = None
        logger.info("🗑️ Color schema cache invalidated")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache status information for debugging"""
        current_time = time.time()
        
        cache_age = None
        if self.last_fetch_time:
            cache_age = current_time - self.last_fetch_time
        
        return {
            "cache_valid": self.is_cache_valid(),
            "cache_age_seconds": cache_age,
            "rate_limited": self.is_rate_limited(),
            "circuit_open": self.is_circuit_open(),
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
