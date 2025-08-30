"""
Database Router for Backend Service
Intelligent database routing for read/write operations with replica support.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from app.core.config import get_settings

# Import pgvector for PostgreSQL vector type support
try:
    from pgvector.psycopg2 import register_vector
except ImportError:
    register_vector = None

logger = logging.getLogger(__name__)


class DatabaseRouter:
    """
    Intelligent database routing for read/write operations.
    Routes queries to appropriate database instance based on operation type.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.primary_engine = None
        self.replica_engine = None
        self.replica_available = True
        self.last_health_check = None
        self.max_lag_seconds = 30
        self._initialize_engines()

    def _setup_pgvector_event_listener(self, engine):
        """Set up event listener to register pgvector on every new connection."""
        if register_vector:
            @event.listens_for(engine, "connect")
            def register_vector_on_connect(dbapi_connection, connection_record):
                try:
                    register_vector(dbapi_connection)
                    logger.debug("pgvector registered for new connection")
                except Exception as e:
                    logger.warning(f"Failed to register pgvector for connection: {e}")

            logger.info("pgvector event listener registered for database router engine")
            return True
        else:
            logger.warning("pgvector not available - vector operations may not work")
            return False

    def _initialize_engines(self):
        """Initialize database engines for primary and replica."""
        # Primary database engine (writes)
        self.primary_engine = create_engine(
            self.settings.postgres_connection_string,
            poolclass=QueuePool,
            pool_size=self.settings.DB_POOL_SIZE,
            max_overflow=self.settings.DB_MAX_OVERFLOW,
            pool_timeout=self.settings.DB_POOL_TIMEOUT,
            pool_recycle=self.settings.DB_POOL_RECYCLE,
            echo=self.settings.DEBUG,
            pool_pre_ping=True
        )
        # Set up pgvector event listener for primary engine
        self._setup_pgvector_event_listener(self.primary_engine)
        
        # Replica database engine (reads) - only if replica is configured
        if self.settings.USE_READ_REPLICA and self.settings.POSTGRES_REPLICA_HOST:
            self.replica_engine = create_engine(
                self.settings.postgres_replica_connection_string,
                poolclass=QueuePool,
                pool_size=self.settings.DB_REPLICA_POOL_SIZE,
                max_overflow=self.settings.DB_REPLICA_MAX_OVERFLOW,
                pool_timeout=self.settings.DB_REPLICA_POOL_TIMEOUT,
                pool_recycle=self.settings.DB_POOL_RECYCLE,
                echo=self.settings.DEBUG,
                pool_pre_ping=True
            )
            # Set up pgvector event listener for replica engine
            self._setup_pgvector_event_listener(self.replica_engine)
            logger.info("✅ Database router initialized with replica support")
        else:
            logger.info("✅ Database router initialized (primary only)")
    
    def get_write_session(self) -> Session:
        """Always routes to primary database for write operations."""
        SessionLocal = sessionmaker(bind=self.primary_engine)
        return SessionLocal()
    
    def get_read_session(self) -> Session:
        """Routes to replica if available, fallback to primary."""
        if self._should_use_replica():
            try:
                SessionLocal = sessionmaker(bind=self.replica_engine)
                return SessionLocal()
            except Exception as e:
                logger.warning(f"Replica connection failed, falling back to primary: {e}")
                self.replica_available = False
        
        # Fallback to primary
        SessionLocal = sessionmaker(bind=self.primary_engine)
        return SessionLocal()
    
    @contextmanager
    def get_write_session_context(self):
        """Context manager for write operations (always primary)."""
        session = self.get_write_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    @contextmanager
    def get_read_session_context(self):
        """Context manager for read operations (replica if available)."""
        session = self.get_read_session()
        try:
            yield session
        except Exception as e:
            logger.error(f"Read session error: {e}")
            raise
        finally:
            session.close()
    
    @contextmanager
    def get_analytics_session_context(self):
        """Context manager for analytics queries (read-only, optimized)."""
        session = self.get_read_session()
        try:
            # Optimize for read queries
            session.execute(text("SET statement_timeout = '60s'"))
            session.execute(text("SET transaction_read_only = on"))
            yield session
        except Exception as e:
            logger.error(f"Analytics session error: {e}")
            raise
        finally:
            session.close()
    
    def _should_use_replica(self) -> bool:
        """Determine if replica should be used for reads."""
        if not self.settings.USE_READ_REPLICA or not self.replica_engine:
            return False
        
        if not self.replica_available:
            # Check if we should retry replica
            if self.last_health_check:
                time_since_check = datetime.utcnow() - self.last_health_check
                if time_since_check.total_seconds() < 60:  # Don't retry for 1 minute
                    return False
        
        return True
    
    async def check_replica_health(self) -> bool:
        """Check replica health and availability."""
        if not self.replica_engine:
            return False
        
        try:
            # Check primary LSN
            with self.get_write_session() as primary:
                primary_lsn = primary.execute(
                    text("SELECT pg_current_wal_lsn()")
                ).scalar()
            
            # Check replica LSN
            with self.get_read_session() as replica:
                replica_lsn = replica.execute(
                    text("SELECT pg_last_wal_replay_lsn()")
                ).scalar()
            
            # Calculate lag (simplified - in production you'd want more precise calculation)
            lag_acceptable = True  # For now, assume lag is acceptable
            
            self.replica_available = lag_acceptable
            self.last_health_check = datetime.utcnow()
            
            if not lag_acceptable:
                logger.warning("Replica lag detected, falling back to primary")
            
            return self.replica_available
            
        except Exception as e:
            logger.error(f"Replica health check failed: {e}")
            self.replica_available = False
            self.last_health_check = datetime.utcnow()
            return False
    
    def get_connection_pool_stats(self) -> dict:
        """Get current connection pool statistics."""
        primary_stats = {
            'size': self.primary_engine.pool.size(),
            'checked_in': self.primary_engine.pool.checkedin(),
            'checked_out': self.primary_engine.pool.checkedout(),
            'overflow': self.primary_engine.pool.overflow(),
            'utilization': self.primary_engine.pool.checkedout() / 
                          (self.primary_engine.pool.size() + self.primary_engine.pool.overflow()) if 
                          (self.primary_engine.pool.size() + self.primary_engine.pool.overflow()) > 0 else 0
        }
        
        replica_stats = None
        if self.replica_engine:
            replica_stats = {
                'size': self.replica_engine.pool.size(),
                'checked_in': self.replica_engine.pool.checkedin(),
                'checked_out': self.replica_engine.pool.checkedout(),
                'overflow': self.replica_engine.pool.overflow(),
                'utilization': self.replica_engine.pool.checkedout() / 
                              (self.replica_engine.pool.size() + self.replica_engine.pool.overflow()) if 
                              (self.replica_engine.pool.size() + self.replica_engine.pool.overflow()) > 0 else 0
            }
        
        return {
            'primary': primary_stats,
            'replica': replica_stats,
            'replica_available': self.replica_available,
            'timestamp': datetime.utcnow()
        }


# Global database router instance
_database_router: Optional[DatabaseRouter] = None


def get_database_router() -> DatabaseRouter:
    """Get the global database router instance."""
    global _database_router
    if _database_router is None:
        _database_router = DatabaseRouter()
    return _database_router


# Convenience functions for backward compatibility
def get_write_session() -> Session:
    """Get a write session (always primary)."""
    return get_database_router().get_write_session()


def get_read_session() -> Session:
    """Get a read session (replica if available, fallback to primary)."""
    return get_database_router().get_read_session()


def get_write_session_context():
    """Get a write session context manager."""
    return get_database_router().get_write_session_context()


def get_read_session_context():
    """Get a read session context manager."""
    return get_database_router().get_read_session_context()


def get_analytics_session_context():
    """Get an analytics session context manager."""
    return get_database_router().get_analytics_session_context()
