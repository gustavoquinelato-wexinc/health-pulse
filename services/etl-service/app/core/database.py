"""
PostgreSQL database connection management.
Migrated from Snowflake to PostgreSQL for better performance.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
import logging
import asyncio

from app.core.config import get_settings
from app.models.unified_models import Base

logger = logging.getLogger(__name__)
settings = get_settings()


class PostgreSQLDatabase:
    """PostgreSQL connection manager."""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize_engine()

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
        """Returns a new database session."""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")
        return self.SessionLocal()

    @contextmanager
    def get_session_context(self) -> Generator[Session, None, None]:
        """Context manager for database session."""
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

    @contextmanager
    def get_job_session_context(self) -> Generator[Session, None, None]:
        """
        Context manager for long-running job sessions with optimized settings.
        Uses shorter timeouts and autocommit for better concurrency.
        """
        session = self.get_session()
        try:
            # Configure session for job execution
            session.execute(text("SET statement_timeout = '30s'"))  # Prevent long-running queries
            session.execute(text("SET idle_in_transaction_session_timeout = '60s'"))  # Prevent idle locks
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Job session error: {e}")
            raise
        finally:
            session.close()

    @contextmanager
    def get_admin_session_context(self) -> Generator[Session, None, None]:
        """Context manager for admin operations with aggressive timeouts to prevent blocking."""
        session = self.get_session()
        try:
            # Set aggressive timeouts for admin operations during job execution
            session.execute(text("SET statement_timeout = '10s'"))  # Quick timeout for admin ops
            session.execute(text("SET idle_in_transaction_session_timeout = '15s'"))  # Prevent idle locks
            session.execute(text("SET lock_timeout = '5s'"))  # Don't wait long for locks
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Admin session error: {e}")
            raise
        finally:
            session.close()

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


async def get_async_job_session():
    """
    Get a database session optimized for async job execution.
    Returns a session that can be used with asyncio.sleep() for yielding control.
    """
    database = get_database()
    session = database.get_session()

    try:
        # Configure session for async job execution
        session.execute(text("SET statement_timeout = '30s'"))
        session.execute(text("SET idle_in_transaction_session_timeout = '60s'"))
        return session
    except Exception as e:
        session.close()
        raise e


async def commit_async_session(session: Session):
    """
    Commit a session asynchronously, yielding control to the event loop.
    """
    try:
        # Yield control before committing
        await asyncio.sleep(0)
        session.commit()
        await asyncio.sleep(0)  # Yield control after commit
    except Exception as e:
        session.rollback()
        raise e


async def close_async_session(session: Session):
    """
    Close a session asynchronously, yielding control to the event loop.
    """
    try:
        await asyncio.sleep(0)
        session.close()
    except Exception as e:
        logger.error(f"Error closing async session: {e}")
