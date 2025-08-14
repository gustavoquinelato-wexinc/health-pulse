"""
Authentication Service for ETL Service.
Handles local authentication with OKTA-ready architecture.
"""

import os
import jwt
import bcrypt
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.database import get_database
from app.core.logging_config import get_logger
from app.core.redis_session_manager import get_redis_session_manager
from app.models.unified_models import User, UserSession
from app.core.utils import DateTimeHelper
from app.core.config import get_settings

logger = get_logger(__name__)


class AuthService:
    """Authentication service for handling login, token generation, and user management."""
    
    def __init__(self):
        # Use Pydantic settings instead of os.getenv for proper configuration loading
        settings = get_settings()

        self.jwt_secret = settings.JWT_SECRET_KEY
        self.jwt_algorithm = settings.JWT_ALGORITHM

        # Use JWT expiry from settings
        expire_minutes = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.token_expiry = timedelta(minutes=expire_minutes)
        self.database = get_database()

        # Initialize Redis session manager for cross-service sessions
        self.redis_session_manager = get_redis_session_manager()

        # Log JWT configuration (without exposing secret key)
        secret_preview = f"{self.jwt_secret[:8]}...{self.jwt_secret[-8:]}" if len(self.jwt_secret) > 16 else "***"
        logger.info(f"🔑 Backend Service JWT configured: {secret_preview}")
        logger.info(f"JWT token expiry configured: {expire_minutes} minutes ({self.token_expiry})")
        logger.info(f"Redis session manager available: {self.redis_session_manager.is_available()}")
    
    async def authenticate_local(self, email: str, password: str, ip_address: str = None, user_agent: str = None) -> Optional[Dict[str, Any]]:
        """Local authentication (for development/admin)"""
        try:
            with self.database.get_write_session_context() as session:
                user = session.query(User).filter(
                    and_(
                        User.email == email.lower().strip(),
                        User.auth_provider == 'local',
                        User.active == True
                    )
                ).first()
                
                if not user or not self._verify_password(password, user.password_hash):
                    logger.warning(f"Authentication failed for email: {email}")
                    return None
                
                return await self._create_session(user, session, ip_address, user_agent)
                
        except Exception as e:
            logger.error(f"Local authentication error: {e}")
            return None
    
    async def authenticate_okta(self, okta_token: str, ip_address: str = None, user_agent: str = None) -> Optional[Dict[str, Any]]:
        """OKTA authentication (production) - placeholder for future implementation"""
        try:
            # TODO: Implement OKTA token verification
            # For now, return None to indicate OKTA is not implemented
            logger.info("OKTA authentication not yet implemented")
            return None
            
        except Exception as e:
            logger.error(f"OKTA auth failed: {e}")
            return None
    
    async def verify_token(self, token: str) -> Optional[User]:
        """Verify JWT token and return user if valid - checks Redis first, then database"""
        try:
            # Debug: Log JWT secret being used
            logger.info(f"Verifying JWT with secret: {self.jwt_secret[:10]}...")

            # Decode JWT token
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            user_id = payload.get("user_id")
            logger.info(f"JWT decoded successfully, user_id: {user_id}")

            if not user_id:
                return None

            token_hash = self._hash_token(token)

            # 1. First check Redis for fast session lookup
            if self.redis_session_manager.is_available():
                session_data = await self.redis_session_manager.get_session(token_hash)
                if session_data:
                    logger.debug(f"✅ Session found in Redis for user {session_data.get('email')}")

                    # Create User object from Redis data
                    user = User()
                    user.id = session_data.get("user_id")
                    user.email = session_data.get("email")
                    user.first_name = session_data.get("first_name")
                    user.last_name = session_data.get("last_name")
                    user.role = session_data.get("role")
                    user.is_admin = session_data.get("is_admin")
                    user.client_id = session_data.get("client_id")
                    user.theme_mode = session_data.get("theme_mode", "light")
                    user.active = True  # Redis sessions are always active

                    # Extend session on activity
                    await self.redis_session_manager.extend_session(token_hash)

                    return user
                else:
                    logger.debug(f"Session not found in Redis, checking database...")

            # 2. Fallback to database session lookup (use write session for activity updates)
            with self.database.get_write_session_context() as session:
                user_session = session.query(UserSession).filter(
                    and_(
                        UserSession.user_id == user_id,
                        UserSession.token_hash == token_hash,
                        UserSession.active == True,
                        UserSession.expires_at > DateTimeHelper.now_utc()
                    )
                ).first()

                if not user_session:
                    logger.debug(f"No valid session found for user {user_id} - token may be expired, invalid, or terminated")
                    return None

                # Get user from database
                user = session.query(User).filter(
                    and_(
                        User.id == user_id,
                        User.active == True
                    )
                ).first()

                if user:
                    # Update session activity timestamp
                    user_session.last_updated_at = DateTimeHelper.now_utc()

                    # Create a detached user object with all needed attributes
                    # This prevents DetachedInstanceError when session closes
                    detached_user = User()
                    detached_user.id = user.id
                    detached_user.email = user.email
                    detached_user.first_name = user.first_name
                    detached_user.last_name = user.last_name
                    detached_user.role = user.role
                    detached_user.is_admin = user.is_admin
                    detached_user.active = user.active
                    detached_user.client_id = user.client_id
                    detached_user.auth_provider = user.auth_provider
                    detached_user.theme_mode = user.theme_mode
                    detached_user.last_login_at = user.last_login_at
                    detached_user.created_at = user.created_at
                    detached_user.last_updated_at = user.last_updated_at

                    # Commit session activity update
                    session.commit()

                    # Store/update session in Redis for faster future lookups
                    if self.redis_session_manager.is_available():
                        user_data = {
                            "id": user.id,
                            "email": user.email,
                            "first_name": user.first_name,
                            "last_name": user.last_name,
                            "role": user.role,
                            "is_admin": user.is_admin,
                            "client_id": user.client_id,
                            "theme_mode": user.theme_mode
                        }
                        await self.redis_session_manager.store_session(token_hash, user_data)

                    logger.debug(f"Token verification successful for user: {user.email}")
                    return detached_user

                return None
                
        except jwt.ExpiredSignatureError:
            logger.warning(f"JWT token expired for user {user_id if 'user_id' in locals() else 'unknown'}")
            return None
        except jwt.InvalidTokenError:
            logger.warning(f"Invalid JWT token for user {user_id if 'user_id' in locals() else 'unknown'}")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None
    
    async def invalidate_session(self, token: str) -> bool:
        """Invalidate a user session"""
        try:
            logger.info(f"🔄 Invalidating session for token: {token[:50]}...")
            with self.database.get_write_session_context() as session:
                token_hash = self._hash_token(token)
                logger.info(f"🔍 Looking for session with token_hash: {token_hash[:50]}...")

                # Count total sessions (global stats for debugging)
                total_sessions = session.query(UserSession).count()
                active_sessions = session.query(UserSession).filter(UserSession.active == True).count()
                logger.info(f"📊 Total sessions: {total_sessions}, Active sessions: {active_sessions}")

                user_session = session.query(UserSession).filter(
                    UserSession.token_hash == token_hash
                ).first()

                if user_session:
                    logger.info(f"✅ Found session for user_id: {user_session.user_id}, active: {user_session.active}")
                    # Mark session as inactive instead of deleting for audit purposes
                    user_session.active = False
                    user_session.last_updated_at = DateTimeHelper.now_utc()
                    session.commit()
                    logger.info(f"✅ Session invalidated for user: {user_session.user_id}")
                    return True
                else:
                    logger.warning(f"❌ No session found with token_hash: {token_hash[:50]}...")
                    # Debug: Show all active sessions
                    all_active = session.query(UserSession).filter(UserSession.active == True).all()
                    for s in all_active:
                        logger.info(f"🔍 Active session: user_id={s.user_id}, token_hash={s.token_hash[:50]}...")

                return False

        except Exception as e:
            logger.error(f"Session invalidation error: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

    # Navigation session method removed - now handled by Redis shared sessions
    
    async def _create_session(self, user: User, session: Session, ip_address: str = None, user_agent: str = None) -> Dict[str, Any]:
        """Create JWT session for user - allows multiple concurrent sessions"""
        try:
            # Clean up only expired sessions for this user (allow multiple active sessions)
            from sqlalchemy import and_
            expired_sessions = session.query(UserSession).filter(
                and_(
                    UserSession.user_id == user.id,
                    UserSession.expires_at <= DateTimeHelper.now_utc()
                )
            ).delete()

            if expired_sessions > 0:
                logger.info(f"Cleaned up {expired_sessions} expired sessions for user {user.id} during login")

            # Create JWT payload
            payload = {
                "user_id": user.id,  # Now using integer ID directly
                "email": user.email,
                "role": user.role,
                "is_admin": user.is_admin,
                "client_id": user.client_id,  # ✅ CRITICAL: Include client_id for multi-client isolation
                "exp": DateTimeHelper.now_utc() + self.token_expiry,
                "iat": DateTimeHelper.now_utc()
            }

            # Generate JWT token
            logger.info(f"🔑 Creating JWT token with secret: {self.jwt_secret}")
            logger.info(f"🔑 JWT payload: {payload}")
            token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
            logger.info(f"🔑 Generated JWT token: {token[:50]}...")

            # Store session in database
            token_hash = self._hash_token(token)
            user_session = UserSession(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=DateTimeHelper.now_utc() + self.token_expiry,
                ip_address=ip_address,
                user_agent=user_agent,
                client_id=user.client_id,
                active=True,
                created_at=DateTimeHelper.now_utc(),
                last_updated_at=DateTimeHelper.now_utc()
            )

            session.add(user_session)
            
            # Update last login
            user.last_login_at = DateTimeHelper.now_utc()
            user.last_updated_at = DateTimeHelper.now_utc()

            session.commit()

            # Store session in Redis for cross-service access
            if self.redis_session_manager.is_available():
                user_data = {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                    "is_admin": user.is_admin,
                    "client_id": user.client_id,
                    "theme_mode": user.theme_mode
                }
                ttl_seconds = int(self.token_expiry.total_seconds())
                await self.redis_session_manager.store_session(token_hash, user_data, ttl_seconds)
                logger.info(f"✅ Session stored in Redis for cross-service access")

            logger.info(f"Session created for user: {user.email}")

            return {
                "token": token,
                "user": {
                    "id": user.id,  # Now using integer ID directly
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                    "is_admin": user.is_admin,
                    "client_id": user.client_id  # ✅ Added missing client_id
                }
            }
            
        except Exception as e:
            logger.error(f"Session creation error: {e}")
            session.rollback()
            raise
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify bcrypt password"""
        try:
            if not password_hash:
                return False
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    async def logout(self, token: str) -> bool:
        """
        Logout user by invalidating session in both Redis and database

        Args:
            token: JWT token to invalidate

        Returns:
            bool: True if logout successful
        """
        try:
            token_hash = self._hash_token(token)

            # 1. Invalidate in Redis first (faster)
            if self.redis_session_manager.is_available():
                await self.redis_session_manager.invalidate_session(token_hash)

            # 2. Invalidate in database (write operation)
            with self.database.get_write_session_context() as session:
                user_session = session.query(UserSession).filter(
                    UserSession.token_hash == token_hash
                ).first()

                if user_session:
                    user_session.active = False
                    user_session.last_updated_at = DateTimeHelper.now_utc()
                    session.commit()
                    logger.info(f"✅ Session invalidated for user {user_session.user_id}")
                    return True
                else:
                    logger.debug(f"Session not found in database for logout: {token_hash[:10]}...")
                    return False

        except Exception as e:
            logger.error(f"❌ Error during logout: {e}")
            return False

    async def logout_all_sessions(self, user_id: int) -> bool:
        """
        Logout user from all devices/sessions

        Args:
            user_id: User ID to logout from all sessions

        Returns:
            bool: True if logout successful
        """
        try:
            # 1. Invalidate all Redis sessions for user
            if self.redis_session_manager.is_available():
                await self.redis_session_manager.invalidate_all_user_sessions(user_id)

            # 2. Invalidate all database sessions for user (write operation)
            with self.database.get_write_session_context() as session:
                updated_count = session.query(UserSession).filter(
                    and_(
                        UserSession.user_id == user_id,
                        UserSession.active == True
                    )
                ).update({
                    "active": False,
                    "last_updated_at": DateTimeHelper.now_utc()
                })

                session.commit()
                logger.info(f"✅ Invalidated {updated_count} sessions for user {user_id}")
                return True

        except Exception as e:
            logger.error(f"❌ Error during logout all sessions: {e}")
            return False

    async def create_session_from_user_data(self, user_data: Dict[str, Any], ip_address: str = None, user_agent: str = None) -> Optional[Dict[str, Any]]:
        """
        Create a session from user data received from centralized auth service.

        Args:
            user_data: User data from centralized auth service
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Dict with token and user data, or None if failed
        """
        try:
            # Find the user in the database and create session (write operation needed for session creation)
            with self.database.get_write_session_context() as session:
                user = session.query(User).filter(User.id == user_data["id"]).first()

                if not user:
                    logger.error(f"User {user_data['id']} not found in database")
                    return None

                # Create session using existing method
                return await self._create_session(user, session, ip_address, user_agent)

        except Exception as e:
            logger.error(f"Failed to create session from user data: {e}")
            return None

    async def store_session_from_token(self, token: str, user_data: Dict[str, Any], ip_address: str = None, user_agent: str = None) -> bool:
        """
        Store session data from centralized auth service token.

        Args:
            token: JWT token from centralized auth service
            user_data: User data from token exchange

        Returns:
            bool: True if session stored successfully
        """
        try:
            # Decode token to get expiration
            import jwt
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            exp_timestamp = payload.get("exp")

            if not exp_timestamp:
                logger.error("Token missing expiration timestamp")
                return False

            expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc).replace(tzinfo=None)
            token_hash = self._hash_token(token)

            # Store in Redis if available
            if self.redis_session_manager.is_available():
                ttl_seconds = int((expires_at - DateTimeHelper.now_utc()).total_seconds())
                if ttl_seconds > 0:
                    await self.redis_session_manager.store_session(token_hash, user_data, ttl_seconds)

            # Store in database (write operation)
            with self.database.get_write_session_context() as session:
                # Check if user exists (cast id defensively)
                try:
                    user_id = int(user_data["id"]) if user_data.get("id") is not None else None
                except Exception:
                    user_id = None
                user = None
                if user_id is not None:
                    user = session.query(User).filter(User.id == user_id).first()
                if not user and user_data.get("email"):
                    user = session.query(User).filter(User.email == user_data["email"].lower().strip()).first()
                if not user:
                    logger.error(f"User not found in database (id={user_data.get('id')}, email={user_data.get('email')})")
                    return False

                # Create or update session
                user_session = session.query(UserSession).filter(
                    UserSession.token_hash == token_hash
                ).first()

                if not user_session:
                    user_session = UserSession(
                        user_id=user.id,
                        token_hash=token_hash,
                        expires_at=expires_at,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        client_id=user.client_id,
                        active=True,
                        created_at=DateTimeHelper.now_utc(),
                        last_updated_at=DateTimeHelper.now_utc()
                    )
                    session.add(user_session)
                else:
                    user_session.expires_at = expires_at
                    user_session.active = True
                    user_session.last_updated_at = DateTimeHelper.now_utc()
                    if ip_address:
                        user_session.ip_address = ip_address
                    if user_agent:
                        user_session.user_agent = user_agent

                session.commit()
                logger.info(f"✅ Session stored for user {user_data['email']}")
                return True

        except Exception as e:
            logger.error(f"❌ Failed to store session from token: {e}")
            return False

    def require_authentication(self):
        """
        Dependency function for FastAPI routes that require authentication.
        """
        from app.auth.auth_middleware import require_authentication
        return require_authentication

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def _hash_token(self, token: str) -> str:
        """Hash token for storage (for revocation purposes)"""
        return hashlib.sha256(token.encode('utf-8')).hexdigest()
    
    async def create_user(self, email: str, password: str, client_id: int, first_name: str = None, last_name: str = None,
                         role: str = 'user', is_admin: bool = False) -> Optional[User]:
        """Create a new local user"""
        try:
            with self.database.get_write_session_context() as session:
                # Check if user already exists (check globally, not just for client)
                # Note: Email uniqueness is enforced globally across all clients
                existing_user = session.query(User).filter(User.email == email.lower().strip()).first()
                if existing_user:
                    logger.warning(f"User already exists: {email}")
                    return None

                # Create new user
                password_hash = self._hash_password(password)
                user = User(
                    email=email.lower().strip(),
                    first_name=first_name,
                    last_name=last_name,
                    role=role,
                    is_admin=is_admin,
                    auth_provider='local',
                    password_hash=password_hash,
                    client_id=client_id,
                    active=True,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc()
                )

                session.add(user)
                session.commit()

                logger.info(f"User created: {email} with role: {role} for client_id: {client_id}")
                return user

        except Exception as e:
            logger.error(f"User creation error: {e}")
            return None


# Global auth service instance
_auth_service = None


def get_auth_service() -> AuthService:
    """Get the global auth service instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def reset_auth_service():
    """Reset the global auth service instance (useful for testing or config changes)"""
    global _auth_service
    _auth_service = None
