"""
Administration routes for system management.
Includes endpoints for managing databases, statistics, and configurations.
"""

from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.core.database import get_db_session, get_database
from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.core.cache import get_cache_manager
from app.core.utils import DateTimeHelper
from app.models.unified_models import (
    Integration, Project, Issue, Issuetype, Status,
    PullRequestCommit, PullRequest, ProjectsIssuetypes, ProjectsStatuses
)
from app.schemas.api_schemas import (
    DatabaseStatsResponse, ErrorResponse, IntegrationInfo
)

logger = get_logger(__name__)
settings = get_settings()

# Router for administration routes
router = APIRouter()


@router.get("/database/stats", response_model=DatabaseStatsResponse)
async def get_database_stats(db: Session = Depends(get_db_session)):
    """Get detailed database statistics."""
    try:
        stats = {}
        
        # Record count per table
        tables_counts = {
            "integrations": db.query(func.count(Integration.id)).scalar() or 0,
            "projects": db.query(func.count(Project.id)).scalar() or 0,
            "issues": db.query(func.count(Issue.id)).scalar() or 0,
            "issuetypes": db.query(func.count(Issuetype.id)).scalar() or 0,
            "statuses": db.query(func.count(Status.id)).scalar() or 0,
            "commits": db.query(func.count(PullRequestCommit.id)).scalar() or 0,
            "pull_requests": db.query(func.count(PullRequest.id)).scalar() or 0,
            "projects_issuetypes": db.query(func.count(ProjectsIssuetypes.project_id)).scalar() or 0,
            "projects_statuses": db.query(func.count(ProjectsStatuses.project_id)).scalar() or 0,
        }

        # Last update
        last_updated = db.query(func.max(Integration.last_sync_at)).scalar() or DateTimeHelper.now_utc()
        
        return DatabaseStatsResponse(
            tables=tables_counts,
            last_updated=last_updated,
            database_size_mb=None  # Snowflake does not easily provide the size
        )
        
    except Exception as e:
        logger.error("Failed to get database stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve database statistics"
        )


@router.post("/database/create-tables")
async def create_database_tables():
    """Creates all tables in the database."""
    try:
        database = get_database()
        database.create_tables()
        
        logger.info("Database tables created successfully")
        
        return {
            "message": "Database tables created successfully",
            "timestamp": DateTimeHelper.now_utc_iso()
        }
        
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create database tables: {str(e)}"
        )


@router.delete("/database/drop-tables")
async def drop_database_tables():
    """Removes all tables from the database. ⚠️ CAUTION: Destructive operation!"""
    try:
        database = get_database()
        database.drop_tables()
        
        logger.warning("Database tables dropped")
        
        return {
            "message": "Database tables dropped successfully",
            "warning": "All data has been permanently deleted",
            "timestamp": DateTimeHelper.now_utc_iso()
        }
        
    except Exception as e:
        logger.error("Failed to drop database tables", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to drop database tables: {str(e)}"
        )


@router.get("/database/connection-test")
async def test_database_connection():
    """Test the connection to the database."""
    try:
        database = get_database()
        is_connected = database.is_connection_alive()
        
        if is_connected:
           # Test a simple query
            with database.get_session_context() as session:
                result = session.execute(text("SELECT 1 as test")).fetchone()
                query_success = result[0] == 1 if result else False
        else:
            query_success = False
        
        return {
            "connected": is_connected,
            "query_test": query_success,
            "database": settings.POSTGRES_DATABASE,
            "host": settings.POSTGRES_HOST,
            "port": settings.POSTGRES_PORT,
            "timestamp": DateTimeHelper.now_utc_iso()
        }
        
    except Exception as e:
        logger.error("Database connection test failed", error=str(e))
        return {
            "connected": False,
            "query_test": False,
            "error": str(e),
            "timestamp": DateTimeHelper.now_utc_iso()
        }


@router.get("/integrations", response_model=list[IntegrationInfo])
async def list_integrations(db: Session = Depends(get_db_session)):
    """Lists all configured integrations."""
    try:
        integrations = db.query(Integration).all()
        
        return [
            IntegrationInfo(
                id=integration.integration_id,
                name=integration.name,
                url=integration.url,
                username=integration.username,
                last_sync_at=integration.last_sync_at
            )
            for integration in integrations
        ]
        
    except Exception as e:
        logger.error("Failed to list integrations", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve integrations"
        )


@router.get("/system/info")
async def get_system_info():
    """Gets system information."""
    try:
        import platform
        import sys
        
        # Basic system information
        system_info = {
            "application": {
                "name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "debug": settings.DEBUG,
                "log_level": settings.LOG_LEVEL
            },
            "system": {
                "platform": platform.platform(),
                "python_version": sys.version,
                "architecture": platform.architecture()[0]
            },
            "database": {
                "account": settings.SNOWFLAKE_ACCOUNT,
                "database": settings.SNOWFLAKE_DATABASE,
                "schema": settings.SNOWFLAKE_SCHEMA,
                "warehouse": settings.SNOWFLAKE_WAREHOUSE
            },
            "scheduler": {
                "timezone": settings.SCHEDULER_TIMEZONE
            },
            "timestamp": DateTimeHelper.now_utc_iso()
        }
        
        return system_info
        
    except Exception as e:
        logger.error("Failed to get system info", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system information"
        )


@router.get("/cache/stats")
async def get_cache_statistics():
    """Gets cache statistics."""
    try:
        cache_manager = get_cache_manager()
        stats = cache_manager.stats()

        return {
            "cache_stats": stats,
            "timestamp": DateTimeHelper.now_utc_iso()
        }

    except Exception as e:
        logger.error("Failed to get cache stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache statistics"
        )


@router.post("/cache/clear")
async def clear_cache():
    """Clears application caches."""
    try:
        cache_manager = get_cache_manager()
        cache_manager.clear()

        logger.info("Application cache cleared")

        return {
            "message": "Application cache cleared successfully",
            "timestamp": DateTimeHelper.now_utc_iso()
        }

    except Exception as e:
        logger.error("Failed to clear cache", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear application cache"
        )
