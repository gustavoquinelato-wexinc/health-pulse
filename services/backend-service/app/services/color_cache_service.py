"""
Color Cache Service
Handles Redis caching for color data to optimize performance
"""
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import timedelta
import redis
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class ColorCacheService:
    """
    Redis-based caching service for color data.
    Provides fast access to frequently requested color configurations.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client = None
        self.cache_prefix = "pulse:colors:"
        self.client_colors_prefix = "pulse:client_colors:"
        self.user_colors_prefix = "pulse:user_colors:"
        self.default_ttl = 60 * 60 * 24  # 24 hours in seconds
        self.short_ttl = 60 * 15  # 15 minutes for frequently changing data
        
        self.logger = logging.getLogger(__name__)
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection"""
        try:
            if self.settings.REDIS_URL:
                self.redis_client = redis.from_url(
                    self.settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self.redis_client.ping()
                self.logger.info(f"✅ Color cache service initialized: {self.settings.REDIS_URL}")
            else:
                self.logger.warning("⚠️ Redis URL not configured, color caching disabled")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Redis for color caching: {e}")
            self.redis_client = None
    
    def is_available(self) -> bool:
        """Check if Redis is available"""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False
    
    def _get_cache_key(self, key_type: str, *args) -> str:
        """Generate cache key"""
        if key_type == "client_colors":
            tenant_id, mode = args
            return f"{self.client_colors_prefix}{tenant_id}:{mode}"
        elif key_type == "user_colors":
            user_id, tenant_id = args
            return f"{self.user_colors_prefix}{user_id}:{tenant_id}"
        elif key_type == "accessibility_colors":
            tenant_id, mode, level = args
            return f"{self.cache_prefix}accessibility:{tenant_id}:{mode}:{level}"
        else:
            return f"{self.cache_prefix}{':'.join(map(str, args))}"
    
    def get_client_colors(self, tenant_id: int, mode: str) -> Optional[Dict[str, Any]]:
        """
        Get cached client color settings.
        
        Args:
            tenant_id: Tenant ID
            mode: Color schema mode ('default' or 'custom')
            
        Returns:
            Cached color data or None if not found
        """
        if not self.is_available():
            return None
            
        try:
            if not self.redis_client:
                return None

            cache_key = self._get_cache_key("client_colors", tenant_id, mode)
            cached_data = self.redis_client.get(cache_key)

            if cached_data:
                self.logger.debug(f"Cache hit for client colors: {tenant_id}:{mode}")
                return json.loads(cached_data)  # type: ignore
            else:
                self.logger.debug(f"Cache miss for client colors: {tenant_id}:{mode}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting cached client colors: {e}")
            return None
    
    def set_client_colors(self, tenant_id: int, mode: str, color_data: Dict[str, Any], 
                         ttl: Optional[int] = None) -> bool:
        """
        Cache client color settings.
        
        Args:
            tenant_id: Tenant ID
            mode: Color schema mode
            color_data: Color data to cache
            ttl: Time to live in seconds (optional)
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self.is_available():
            return False
            
        try:
            if not self.redis_client:
                return False

            cache_key = self._get_cache_key("client_colors", tenant_id, mode)
            ttl = ttl or self.default_ttl

            self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(color_data, ensure_ascii=False)
            )
            
            self.logger.debug(f"Cached client colors: {tenant_id}:{mode} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            self.logger.error(f"Error caching client colors: {e}")
            return False
    
    def get_user_colors(self, user_id: int, tenant_id: int) -> Optional[Dict[str, Any]]:
        """
        Get cached user-specific color resolution.
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
            
        Returns:
            Cached user color data or None if not found
        """
        if not self.is_available():
            return None
            
        try:
            if not self.redis_client:
                return None

            cache_key = self._get_cache_key("user_colors", user_id, tenant_id)
            cached_data = self.redis_client.get(cache_key)

            if cached_data:
                self.logger.debug(f"Cache hit for user colors: {user_id}:{tenant_id}")
                return json.loads(cached_data)  # type: ignore
            else:
                self.logger.debug(f"Cache miss for user colors: {user_id}:{tenant_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting cached user colors: {e}")
            return None
    
    def set_user_colors(self, user_id: int, tenant_id: int, color_data: Dict[str, Any],
                       ttl: Optional[int] = None) -> bool:
        """
        Cache user-specific color resolution.
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
            color_data: User color data to cache
            ttl: Time to live in seconds (optional)
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self.is_available():
            return False
            
        try:
            if not self.redis_client:
                return False

            cache_key = self._get_cache_key("user_colors", user_id, tenant_id)
            ttl = ttl or self.short_ttl  # Shorter TTL for user-specific data

            self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(color_data, ensure_ascii=False)
            )
            
            self.logger.debug(f"Cached user colors: {user_id}:{tenant_id} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            self.logger.error(f"Error caching user colors: {e}")
            return False
    
    def get_accessibility_colors(self, tenant_id: int, mode: str, level: str) -> Optional[Dict[str, Any]]:
        """
        Get cached accessibility color variants.
        
        Args:
            tenant_id: Tenant ID
            mode: Color schema mode
            level: Accessibility level ('AA' or 'AAA')
            
        Returns:
            Cached accessibility color data or None if not found
        """
        if not self.is_available():
            return None
            
        try:
            if not self.redis_client:
                return None

            cache_key = self._get_cache_key("accessibility_colors", tenant_id, mode, level)
            cached_data = self.redis_client.get(cache_key)

            if cached_data:
                self.logger.debug(f"Cache hit for accessibility colors: {tenant_id}:{mode}:{level}")
                return json.loads(cached_data)  # type: ignore
            else:
                self.logger.debug(f"Cache miss for accessibility colors: {tenant_id}:{mode}:{level}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting cached accessibility colors: {e}")
            return None
    
    def set_accessibility_colors(self, tenant_id: int, mode: str, level: str, 
                               color_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Cache accessibility color variants.
        
        Args:
            tenant_id: Tenant ID
            mode: Color schema mode
            level: Accessibility level
            color_data: Accessibility color data to cache
            ttl: Time to live in seconds (optional)
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self.is_available():
            return False
            
        try:
            if not self.redis_client:
                return False

            cache_key = self._get_cache_key("accessibility_colors", tenant_id, mode, level)
            ttl = ttl or self.default_ttl

            self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(color_data, ensure_ascii=False)
            )
            
            self.logger.debug(f"Cached accessibility colors: {tenant_id}:{mode}:{level} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            self.logger.error(f"Error caching accessibility colors: {e}")
            return False
    
    def invalidate_client_colors(self, tenant_id: int) -> bool:
        """
        Invalidate all cached colors for a client.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            True if invalidated successfully, False otherwise
        """
        if not self.is_available():
            return False
            
        try:
            # Find all keys for this client
            patterns = [
                f"{self.client_colors_prefix}{tenant_id}:*",
                f"{self.cache_prefix}accessibility:{tenant_id}:*",
                f"{self.user_colors_prefix}*:{tenant_id}"
            ]
            
            deleted_count = 0
            for pattern in patterns:
                if not self.redis_client:
                    continue
                keys = self.redis_client.keys(pattern)
                if keys:
                    deleted_count += self.redis_client.delete(*keys)  # type: ignore
            
            self.logger.info(f"Invalidated {deleted_count} cached color entries for client {tenant_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error invalidating client colors cache: {e}")
            return False
    
    def invalidate_user_colors(self, user_id: int) -> bool:
        """
        Invalidate cached colors for a specific user.
        
        Args:
            user_id: User ID
            
        Returns:
            True if invalidated successfully, False otherwise
        """
        if not self.is_available():
            return False
            
        try:
            if not self.redis_client:
                return False

            pattern = f"{self.user_colors_prefix}{user_id}:*"
            keys = self.redis_client.keys(pattern)

            if keys:
                deleted_count = self.redis_client.delete(*keys)  # type: ignore
                self.logger.info(f"Invalidated {deleted_count} cached color entries for user {user_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error invalidating user colors cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        if not self.is_available():
            return {"available": False, "error": "Redis not available"}
            
        try:
            if not self.redis_client:
                return {"available": False, "error": "Redis client not initialized"}

            info = self.redis_client.info()

            # Count color-related keys
            color_keys = len(self.redis_client.keys(f"{self.cache_prefix}*"))  # type: ignore
            client_keys = len(self.redis_client.keys(f"{self.client_colors_prefix}*"))  # type: ignore
            user_keys = len(self.redis_client.keys(f"{self.user_colors_prefix}*"))  # type: ignore
            
            return {
                "available": True,
                "total_keys": info.get("db0", {}).get("keys", 0),  # type: ignore
                "color_cache_keys": color_keys,
                "client_color_keys": client_keys,
                "user_color_keys": user_keys,
                "memory_used": info.get("used_memory_human", "Unknown"),  # type: ignore
                "connected_clients": info.get("connected_clients", 0)  # type: ignore
            }
            
        except Exception as e:
            self.logger.error(f"Error getting cache stats: {e}")
            return {"available": False, "error": str(e)}
