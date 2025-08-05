"""
Redis Session Manager for Backend Service
Handles shared sessions across Frontend and ETL services
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import redis
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class RedisSessionManager:
    """
    Redis-based session manager for cross-service authentication.
    Stores session data in Redis with automatic expiration.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client = None
        self.session_prefix = "pulse:session:"
        self.user_sessions_prefix = "pulse:user_sessions:"
        self.default_ttl = 24 * 60 * 60  # 24 hours in seconds
        
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
                logger.info(f"✅ Redis session manager initialized: {self.settings.REDIS_URL}")
            else:
                logger.warning("⚠️ Redis URL not configured, session manager disabled")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize Redis session manager: {e}")
            self.redis_client = None
    
    def is_available(self) -> bool:
        """Check if Redis is available"""
        return self.redis_client is not None
    
    async def store_session(self, token_hash: str, user_data: Dict[str, Any], ttl_seconds: Optional[int] = None) -> bool:
        """
        Store session data in Redis with automatic expiration
        
        Args:
            token_hash: Hashed JWT token as key
            user_data: User information to store
            ttl_seconds: Time to live in seconds (default: 24 hours)
        
        Returns:
            bool: True if stored successfully
        """
        if not self.is_available():
            logger.warning("Redis not available, cannot store session")
            return False
            
        try:
            ttl = ttl_seconds or self.default_ttl
            session_key = f"{self.session_prefix}{token_hash}"
            
            # Prepare session data
            session_data = {
                "user_id": user_data.get("id"),
                "email": user_data.get("email"),
                "first_name": user_data.get("first_name"),
                "last_name": user_data.get("last_name"),
                "role": user_data.get("role"),
                "is_admin": user_data.get("is_admin"),
                "client_id": user_data.get("client_id"),
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()
            }
            
            # Store in Redis with expiration
            self.redis_client.setex(
                session_key,
                ttl,
                json.dumps(session_data)
            )
            
            # Also maintain a set of active sessions per user for logout-all functionality
            user_sessions_key = f"{self.user_sessions_prefix}{user_data.get('id')}"
            self.redis_client.sadd(user_sessions_key, token_hash)
            self.redis_client.expire(user_sessions_key, ttl)
            
            logger.info(f"✅ Session stored in Redis for user {user_data.get('email')} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to store session in Redis: {e}")
            return False
    
    async def get_session(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data from Redis
        
        Args:
            token_hash: Hashed JWT token as key
            
        Returns:
            Dict with user data if session exists and is valid, None otherwise
        """
        if not self.is_available():
            return None
            
        try:
            session_key = f"{self.session_prefix}{token_hash}"
            session_data_str = self.redis_client.get(session_key)
            
            if not session_data_str:
                logger.debug(f"No session found in Redis for token hash: {token_hash[:10]}...")
                return None
            
            session_data = json.loads(session_data_str)
            
            # Check if session has expired (double-check)
            expires_at = datetime.fromisoformat(session_data.get("expires_at"))
            if datetime.utcnow() > expires_at:
                logger.debug(f"Session expired for user {session_data.get('email')}")
                await self.invalidate_session(token_hash)
                return None
            
            logger.debug(f"✅ Session retrieved from Redis for user {session_data.get('email')}")
            return session_data
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve session from Redis: {e}")
            return None
    
    async def invalidate_session(self, token_hash: str) -> bool:
        """
        Remove session from Redis
        
        Args:
            token_hash: Hashed JWT token as key
            
        Returns:
            bool: True if invalidated successfully
        """
        if not self.is_available():
            return False
            
        try:
            session_key = f"{self.session_prefix}{token_hash}"
            
            # Get session data to find user_id before deletion
            session_data_str = self.redis_client.get(session_key)
            if session_data_str:
                session_data = json.loads(session_data_str)
                user_id = session_data.get("user_id")
                
                # Remove from user's session set
                if user_id:
                    user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
                    self.redis_client.srem(user_sessions_key, token_hash)
            
            # Remove the session
            result = self.redis_client.delete(session_key)
            
            if result:
                logger.info(f"✅ Session invalidated from Redis: {token_hash[:10]}...")
            else:
                logger.debug(f"Session not found in Redis for invalidation: {token_hash[:10]}...")
                
            return bool(result)
            
        except Exception as e:
            logger.error(f"❌ Failed to invalidate session in Redis: {e}")
            return False
    
    async def invalidate_all_user_sessions(self, user_id: int) -> bool:
        """
        Invalidate all sessions for a specific user (logout from all devices)
        
        Args:
            user_id: User ID
            
        Returns:
            bool: True if invalidated successfully
        """
        if not self.is_available():
            return False
            
        try:
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            
            # Get all session token hashes for this user
            token_hashes = self.redis_client.smembers(user_sessions_key)
            
            if not token_hashes:
                logger.debug(f"No active sessions found for user {user_id}")
                return True
            
            # Remove all sessions
            session_keys = [f"{self.session_prefix}{token_hash}" for token_hash in token_hashes]
            deleted_count = self.redis_client.delete(*session_keys)
            
            # Remove the user sessions set
            self.redis_client.delete(user_sessions_key)
            
            logger.info(f"✅ Invalidated {deleted_count} sessions for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to invalidate all user sessions: {e}")
            return False
    
    async def extend_session(self, token_hash: str, ttl_seconds: Optional[int] = None) -> bool:
        """
        Extend session expiration time
        
        Args:
            token_hash: Hashed JWT token as key
            ttl_seconds: New TTL in seconds (default: 24 hours)
            
        Returns:
            bool: True if extended successfully
        """
        if not self.is_available():
            return False
            
        try:
            session_key = f"{self.session_prefix}{token_hash}"
            ttl = ttl_seconds or self.default_ttl
            
            # Check if session exists
            if not self.redis_client.exists(session_key):
                logger.debug(f"Cannot extend non-existent session: {token_hash[:10]}...")
                return False
            
            # Extend expiration
            result = self.redis_client.expire(session_key, ttl)
            
            if result:
                logger.debug(f"✅ Session extended for {ttl}s: {token_hash[:10]}...")
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"❌ Failed to extend session: {e}")
            return False


# Global instance
_redis_session_manager = None

def get_redis_session_manager() -> RedisSessionManager:
    """Get the global Redis session manager instance"""
    global _redis_session_manager
    if _redis_session_manager is None:
        _redis_session_manager = RedisSessionManager()
    return _redis_session_manager
