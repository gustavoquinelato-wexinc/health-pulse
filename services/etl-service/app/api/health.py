"""
Health check endpoints for ETL service monitoring.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.core.database import get_db_session
from app.schemas.api_schemas import HealthResponse
from app.auth.centralized_auth_middleware import UserData, require_admin_authentication

router = APIRouter()


@router.get(
    "/health/quick",
    summary="Quick Health Check",
    description="Fast health check without authentication for system monitoring"
)
async def quick_health_check():
    """
    Quick health check for system monitoring - no authentication required.
    Used by dashboard system health cards for fast status updates.
    """
    try:
        # Quick database connection test
        from app.core.database import get_database
        from sqlalchemy import text

        database = get_database()
        with database.get_session() as session:
            session.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database_status": "healthy",
            "database_message": "Database connection successful",
            "service": "ETL Service",
            "timestamp": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database_status": "unhealthy",
            "database_message": f"Database connection failed: {str(e)}",
            "service": "ETL Service",
            "timestamp": "2024-01-01T00:00:00Z"
        }


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check the health status of the ETL service and its dependencies"
)
async def health_check(
    request: Request,
    db: Session = Depends(get_db_session)
):
    """
    Comprehensive health check for the ETL service.

    Returns:
        HealthResponse: Service health status including database connectivity
    """
    # Check authentication (both cookie and header)
    from app.auth.centralized_auth_service import get_centralized_auth_service

    # Try to get token from cookie first, then Authorization header
    token = request.cookies.get("pulse_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    # Verify token and check admin permissions
    auth_service = get_centralized_auth_service()
    user_data = await auth_service.verify_token(token)

    if not user_data:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    if not user_data.get("is_admin"):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

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
