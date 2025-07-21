"""
Health check endpoints for ETL service monitoring.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db_session
from app.schemas.api_schemas import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check the health status of the ETL service and its dependencies"
)
async def health_check(db: Session = Depends(get_db_session)):
    """
    Comprehensive health check for the ETL service.
    
    Returns:
        HealthResponse: Service health status including database connectivity
    """
    try:
        # Test database connection
        from sqlalchemy import text
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
        message="ETL Service is running",
        database_status=db_status,
        database_message=db_message,
        version="1.0.0"
    )
