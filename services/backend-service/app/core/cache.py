"""
Cache system to improve application performance.
Implements in-memory cache with TTL and optionally Redis.
"""

import time
import json
import hashlib
from typing import Any, Dict, Optional, Union, Callable
from functools import wraps
from datetime import datetime, timedelta

from app.core.logging_config import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class InMemoryCache:
    """Simple in-memory cache with TTL."""
    
    def __init__(self, default_ttl: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
    
    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """Checks if cache entry has expired."""
        return time.time() > entry['expires_at']
    
    def _cleanup_expired(self):
        """Removes expired cache entries."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time > entry['expires_at']
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.debug("Cache cleanup", removed_keys=len(expired_keys))
    
    def get(self, key: str) -> Optional[Any]:
        """Gets value from cache."""
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        
        if self._is_expired(entry):
            del self.cache[key]
            return None
        
        entry['last_accessed'] = time.time()
        entry['access_count'] += 1
        
        logger.debug("Cache hit", key=key, access_count=entry['access_count'])
        return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Sets value in cache."""
        if ttl is None:
            ttl = self.default_ttl
        
        self.cache[key] = {
            'value': value,
            'created_at': time.time(),
            'expires_at': time.time() + ttl,
            'last_accessed': time.time(),
            'access_count': 0,
            'ttl': ttl
        }
        
        logger.debug("Cache set", key=key, ttl=ttl)
        
        # Periodic cleanup
        if len(self.cache) % 100 == 0:
            self._cleanup_expired()
    
    def delete(self, key: str) -> bool:
        """Removes value from cache."""
        if key in self.cache:
            del self.cache[key]
            logger.debug("Cache delete", key=key)
            return True
        return False
    
    def clear(self) -> None:
        """Clears all cache."""
        count = len(self.cache)
        self.cache.clear()
        logger.info("Cache cleared", removed_keys=count)
    
    def stats(self) -> Dict[str, Any]:
        """Returns cache statistics."""
        current_time = time.time()
        total_entries = len(self.cache)
        expired_entries = sum(
            1 for entry in self.cache.values()
            if current_time > entry['expires_at']
        )
        
        return {
            'total_entries': total_entries,
            'active_entries': total_entries - expired_entries,
            'expired_entries': expired_entries,
            'memory_usage_mb': self._estimate_memory_usage()
        }
    
    def _estimate_memory_usage(self) -> float:
        """Estimates memory usage in MB."""
        try:
            import sys
            total_size = sys.getsizeof(self.cache)
            for key, entry in self.cache.items():
                total_size += sys.getsizeof(key)
                total_size += sys.getsizeof(entry)
                total_size += sys.getsizeof(entry['value'])
            
            return total_size / (1024 * 1024)  # Convert to MB
        except Exception:
            return 0.0


class RedisCache:
    """Cache using Redis (optional)."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", default_ttl: int = 300):
        self.default_ttl = default_ttl
        self.redis_client = None
        
        try:
            import redis  # type: ignore
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Tests connection
            self.redis_client.ping()
            logger.info("Redis cache initialized", url=redis_url)
        except ImportError:
            logger.warning("Redis not available, falling back to in-memory cache")
        except Exception as e:
            logger.warning("Failed to connect to Redis", error=str(e))
    
    def get(self, key: str) -> Optional[Any]:
        """Gets value from cache."""
        if not self.redis_client:
            return None
        
        try:
            value = self.redis_client.get(key)
            if value is None:
                return None
            
            # Deserializes JSON
            return json.loads(value)
        except Exception as e:
            logger.error("Redis get error", key=key, error=str(e))
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Sets value in cache."""
        if not self.redis_client:
            return
        
        if ttl is None:
            ttl = self.default_ttl
        
        try:
            # Serializes to JSON
            serialized_value = json.dumps(value, default=str)
            self.redis_client.setex(key, ttl, serialized_value)
        except Exception as e:
            logger.error("Redis set error", key=key, error=str(e))
    
    def delete(self, key: str) -> bool:
        """Removes value from cache."""
        if not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error("Redis delete error", key=key, error=str(e))
            return False
    
    def clear(self) -> None:
        """Clears all cache."""
        if not self.redis_client:
            return
        
        try:
            self.redis_client.flushdb()
            logger.info("Redis cache cleared")
        except Exception as e:
            logger.error("Redis clear error", error=str(e))


class CacheManager:
    """Cache manager that automatically chooses between Redis and memory."""
    
    def __init__(self):
        # Tries to use Redis first, fallback to memory
        self.redis_cache = RedisCache()
        self.memory_cache = InMemoryCache()
        
        # Uses Redis if available, otherwise memory
        self.primary_cache = (
            self.redis_cache if self.redis_cache.redis_client 
            else self.memory_cache
        )
        
        logger.info(
            "Cache manager initialized", 
            cache_type=type(self.primary_cache).__name__
        )
    
    def get(self, key: str) -> Optional[Any]:
        """Gets value from cache."""
        return self.primary_cache.get(key)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Sets value in cache."""
        self.primary_cache.set(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        """Removes value from cache."""
        return self.primary_cache.delete(key)
    
    def clear(self) -> None:
        """Clears all cache."""
        self.primary_cache.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Returns cache statistics."""
        if hasattr(self.primary_cache, 'stats'):
            return self.primary_cache.stats()
        return {"cache_type": type(self.primary_cache).__name__}


# Global cache instance
cache_manager = CacheManager()


def cache_key(*args, **kwargs) -> str:
    """Generates cache key based on arguments."""
    # Creates unique string based on arguments
    key_data = {
        'args': args,
        'kwargs': sorted(kwargs.items())
    }
    
    key_string = json.dumps(key_data, sort_keys=True, default=str)
    
    # Generates MD5 hash for compact key
    return hashlib.md5(key_string.encode()).hexdigest()


def get_cache_manager() -> CacheManager:
    """Returns cache manager instance."""
    return cache_manager
