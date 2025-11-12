"""
Health check endpoints for Backend service monitoring.
Enhanced with ML infrastructure monitoring for Phase 1-4.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any

from app.core.database import get_read_session, get_ml_session_context, test_vector_column_access
from app.core.logging_config import get_logger
from app.schemas.api_schemas import HealthResponse

router = APIRouter()
logger = get_logger(__name__)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Basic Health Check",
    description="Check the basic health status of the Backend service"
)
async def health_check(
    db: Session = Depends(get_read_session)
):
    """
    Basic health check for the Backend service.

    Returns:
        HealthResponse: Service health status including database connectivity
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        db_status = "healthy"
        db_message = "Database connection successful"
    except Exception as e:
        db_status = "unhealthy"
        db_message = f"Database connection failed: {str(e)}"

    # Determine overall status
    overall_status = "healthy" if db_status == "healthy" else "unhealthy"

    return HealthResponse(
        status=overall_status,
        message="Backend Service is running",
        database_status=db_status,
        database_message=db_message,
        version="1.0.0"
    )


@router.get("/health/database")
async def check_database_health():
    """Enhanced database health check including ML tables"""
    try:
        session = get_read_session()
        try:
            # Test existing tables
            session.execute(text("SELECT 1 FROM work_items LIMIT 1"))
            session.execute(text("SELECT 1 FROM prs LIMIT 1"))
            session.execute(text("SELECT 1 FROM projects LIMIT 1"))

            # Test new ML tables (Phase 1: May not have data yet)
            ml_tables_status = {}
            ml_tables = ['ai_learning_memory', 'ai_predictions', 'ml_anomaly_alerts']

            for table in ml_tables:
                try:
                    session.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                    ml_tables_status[table] = "available"
                except Exception:
                    ml_tables_status[table] = "not_available"

            # Test vector columns (Phase 1: Should exist but be null)
            vector_status = {}
            vector_tables = ['work_items', 'prs', 'projects', 'users']

            for table in vector_tables:
                try:
                    result = session.execute(text(f"SELECT COUNT(*) FROM {table} WHERE embedding IS NOT NULL")).scalar()
                    vector_status[f'{table}_with_embeddings'] = result
                except Exception:
                    vector_status[f'{table}_with_embeddings'] = "column_not_available"

            from app.core.utils import DateTimeHelper
            return {
                "status": "healthy",
                "database_connection": "ok",
                "ml_tables": ml_tables_status,
                "vector_columns": vector_status,
                "timestamp": DateTimeHelper.now_default()
            }
        finally:
            session.close()

    except Exception as e:
        from app.core.utils import DateTimeHelper
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": DateTimeHelper.now_default()
        }


@router.get("/health/ml")
async def check_ml_health():
    """ML infrastructure health check"""
    try:
        with get_ml_session_context() as session:
            # Test PostgresML availability (Phase 1: May not be available)
            try:
                result = session.execute(text("SELECT pgml.version()")).scalar()
                postgresml_status = {"available": True, "version": result}
            except Exception as e:
                postgresml_status = {"available": False, "error": str(e)}

            # Test pgvector availability
            try:
                session.execute(text("SELECT '[1,2,3]'::vector"))
                pgvector_status = {"available": True}
            except Exception as e:
                pgvector_status = {"available": False, "error": str(e)}

            # Test vector column access
            vector_access = test_vector_column_access()

            from app.core.utils import DateTimeHelper
            return {
                "status": "healthy" if pgvector_status["available"] else "degraded",
                "postgresml": postgresml_status,
                "pgvector": pgvector_status,
                "vector_columns_accessible": vector_access,
                "replica_connection": "ok",
                "timestamp": DateTimeHelper.now_default()
            }

    except Exception as e:
        from app.core.utils import DateTimeHelper
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": DateTimeHelper.now_default()
        }


@router.get("/health/comprehensive")
async def comprehensive_health_check():
    """Comprehensive health check combining all health aspects"""
    try:
        # Get all health check results
        basic_health = await health_check()
        db_health = await check_database_health()
        ml_health = await check_ml_health()

        # Determine overall status
        statuses = [
            basic_health.status,
            db_health.get("status", "unknown"),
            ml_health.get("status", "unknown")
        ]

        if "unhealthy" in statuses:
            overall_status = "unhealthy"
        elif "degraded" in statuses:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        from app.core.utils import DateTimeHelper
        return {
            "status": overall_status,
            "service": "Backend Service",
            "version": "1.0.0",
            "timestamp": DateTimeHelper.now_default(),
            "components": {
                "basic": {
                    "status": basic_health.status,
                    "database": basic_health.database_status
                },
                "database": db_health,
                "ml_infrastructure": ml_health
            },
            "summary": {
                "total_components": 3,
                "healthy_components": len([s for s in statuses if s == "healthy"]),
                "degraded_components": len([s for s in statuses if s == "degraded"]),
                "unhealthy_components": len([s for s in statuses if s == "unhealthy"])
            }
        }

    except Exception as e:
        logger.error(f"Error in comprehensive health check: {e}")
        from app.core.utils import DateTimeHelper
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": DateTimeHelper.now_default()
        }
