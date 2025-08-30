"""
PostgreSQL database connection management with replica support.
Migrated from Snowflake to PostgreSQL for better performance.
Enhanced with read replica routing for improved scalability.
"""

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
import logging

from app.core.config import get_settings
from app.models.unified_models import Base
from app.core.database_router import (
    get_database_router, get_write_session, get_read_session,
    get_ml_session_context, get_ml_session, test_vector_column_access
)

# Import pgvector for PostgreSQL vector type support
try:
    from pgvector.psycopg2 import register_vector
except ImportError:
    register_vector = None

logger = logging.getLogger(__name__)
settings = get_settings()


class PostgreSQLDatabase:
    """PostgreSQL connection manager."""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize_engine()

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

            logger.info("pgvector event listener registered for all new connections")
            return True
        else:
            logger.warning("pgvector not available - vector operations may not work")
            return False

    def _initialize_engine(self):
        """Initializes SQLAlchemy engine with PostgreSQL connection."""
        try:
            # Create SQLAlchemy engine for PostgreSQL
            self.engine = create_engine(
                settings.postgres_connection_string,
                poolclass=QueuePool,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=settings.DB_POOL_TIMEOUT,
                pool_recycle=settings.DB_POOL_RECYCLE,
                pool_pre_ping=True,
                echo=False  # Disable SQLAlchemy logging completely
            )

            # Set up pgvector event listener for all new connections
            self._setup_pgvector_event_listener(self.engine)

            # Create sessionmaker
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )

            logger.info("PostgreSQL database connection initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL connection: {e}")
            raise
    
    def get_session(self) -> Session:
        """Returns a new database session (legacy method - uses primary)."""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")
        return self.SessionLocal()

    @contextmanager
    def get_session_context(self) -> Generator[Session, None, None]:
        """Context manager for database session (legacy method - uses primary)."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def get_write_session(self) -> Session:
        """Get a write session (always routes to primary database)."""
        return get_write_session()

    def get_read_session(self) -> Session:
        """Get a read session (routes to replica if available, fallback to primary)."""
        return get_read_session()

    @contextmanager
    def get_write_session_context(self) -> Generator[Session, None, None]:
        """Context manager for write operations (always primary)."""
        router = get_database_router()
        with router.get_write_session_context() as session:
            yield session

    @contextmanager
    def get_read_session_context(self) -> Generator[Session, None, None]:
        """Context manager for read operations (replica if available)."""
        router = get_database_router()
        with router.get_read_session_context() as session:
            yield session

    @contextmanager
    def get_analytics_session_context(self) -> Generator[Session, None, None]:
        """Context manager for analytics queries (read-only, optimized)."""
        router = get_database_router()
        with router.get_analytics_session_context() as session:
            yield session

    @contextmanager
    def get_ml_session_context(self) -> Generator[Session, None, None]:
        """Context manager for ML operations (replica-only, optimized)."""
        with get_ml_session_context() as session:
            yield session

    def get_ml_session(self, read_only: bool = True) -> Session:
        """Get session optimized for ML operations (typically read-only)."""
        return get_ml_session(read_only)

    def test_vector_column_access(self) -> bool:
        """Test if vector columns are accessible."""
        return test_vector_column_access()
    
    def is_connection_alive(self) -> bool:
        """Checks if the connection is alive."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True
        except Exception:
            return False

    def create_tables(self):
        """Creates all tables in the database."""
        try:
            # PostgreSQL automatically handles sequences for SERIAL/IDENTITY columns
            # Create tables using SQLAlchemy
            Base.metadata.create_all(bind=self.engine)

            logger.info("Database tables created successfully")

        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    def drop_tables(self):
        """Removes all tables from the database."""
        try:
            # First, drop any orphaned tables that might have foreign key constraints
            # but are not in our current model definitions
            logger.info("Checking for orphaned tables...")

            with self.engine.connect() as conn:
                # Drop github_extraction_sessions table if it exists (orphaned from old system)
                orphaned_tables = [
                    'github_extraction_sessions',
                    'commits',  # In case there are old commit tables
                    'old_pull_requests',  # In case there are old PR tables
                ]

                for table_name in orphaned_tables:
                    try:
                        conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                        logger.info(f"Dropped orphaned table: {table_name}")
                    except Exception as e:
                        logger.debug(f"Could not drop {table_name}: {e}")

                conn.commit()

            # PostgreSQL automatically handles sequences for SERIAL/IDENTITY columns
            # Drop tables using SQLAlchemy (handles dependencies automatically)
            Base.metadata.drop_all(bind=self.engine)

            logger.info("Database tables dropped successfully")

        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            raise
    
    def check_table_exists(self, table_name: str) -> bool:
        """Checks if a table exists in the current schema."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name)"
                ), {"table_name": table_name})
                return result.scalar()
        except Exception as e:
            logger.error(f"Error checking table existence: {e}")
            return False

    def close_connections(self):
        """Closes all connections."""
        try:
            if self.engine:
                self.engine.dispose()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing connections: {e}")


# Global database instance (lazy initialization)
_database = None


def get_database() -> PostgreSQLDatabase:
    """Returns the database instance (lazy initialization)."""
    global _database
    if _database is None:
        _database = PostgreSQLDatabase()
    return _database


def get_db_session() -> Generator[Session, None, None]:
    """Dependency to get database session in FastAPI."""
    database = get_database()
    with database.get_session_context() as session:
        yield session
