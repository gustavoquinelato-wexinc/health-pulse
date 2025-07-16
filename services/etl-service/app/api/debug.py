"""
Debug endpoints for ETL service development and troubleshooting.
These endpoints provide diagnostic information and testing capabilities.
"""

import os
import sys
import psutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db_session
from app.core.config import get_settings

router = APIRouter()


@router.get("/debug/connections")
async def test_connections(db: Session = Depends(get_db_session)):
    """
    Test all external connections and dependencies.
    
    Returns:
        dict: Connection test results for all services
    """
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "connections": {}
    }
    
    # Test database connection
    try:
        db.execute(text("SELECT 1"))
        results["connections"]["database"] = {
            "status": "connected",
            "message": "Database connection successful"
        }
    except Exception as e:
        results["connections"]["database"] = {
            "status": "failed",
            "message": f"Database connection failed: {str(e)}"
        }
    
    # Test Jira connection
    try:
        settings = get_settings()
        if settings.JIRA_BASE_URL and settings.JIRA_EMAIL and settings.JIRA_API_TOKEN:
            # TODO: Add actual Jira API test
            results["connections"]["jira"] = {
                "status": "configured",
                "message": "Jira credentials configured",
                "base_url": settings.JIRA_BASE_URL,
                "email": settings.JIRA_EMAIL
            }
        else:
            results["connections"]["jira"] = {
                "status": "not_configured",
                "message": "Jira credentials not configured"
            }
    except Exception as e:
        results["connections"]["jira"] = {
            "status": "error",
            "message": f"Jira connection test failed: {str(e)}"
        }
    
    # Test GitHub connection
    try:
        settings = get_settings()
        if settings.GITHUB_TOKEN:
            # TODO: Add actual GitHub API test
            results["connections"]["github"] = {
                "status": "configured",
                "message": "GitHub token configured"
            }
        else:
            results["connections"]["github"] = {
                "status": "not_configured",
                "message": "GitHub token not configured"
            }
    except Exception as e:
        results["connections"]["github"] = {
            "status": "error",
            "message": f"GitHub connection test failed: {str(e)}"
        }
    
    return results


@router.get("/debug/system")
async def get_system_info():
    """
    Get system information and resource usage.
    
    Returns:
        dict: System information and performance metrics
    """
    try:
        # Get process information
        process = psutil.Process()
        
        # Get system information
        system_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "platform": sys.platform,
                "python_version": sys.version,
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "disk_usage": {
                    "total_gb": round(psutil.disk_usage('/').total / (1024**3), 2),
                    "used_gb": round(psutil.disk_usage('/').used / (1024**3), 2),
                    "free_gb": round(psutil.disk_usage('/').free / (1024**3), 2)
                }
            },
            "process": {
                "pid": process.pid,
                "memory_usage_mb": round(process.memory_info().rss / (1024**2), 2),
                "cpu_percent": process.cpu_percent(),
                "num_threads": process.num_threads(),
                "create_time": datetime.fromtimestamp(process.create_time()).isoformat(),
                "status": process.status()
            },
            "environment": {
                "debug_mode": os.getenv("DEBUG", "false").lower() == "true",
                "log_level": os.getenv("LOG_LEVEL", "INFO"),
                "database_url_configured": bool(os.getenv("DATABASE_URL")),
                "jira_configured": bool(os.getenv("JIRA_BASE_URL")),
                "github_configured": bool(os.getenv("GITHUB_TOKEN"))
            }
        }
        
        return system_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system info: {str(e)}")


@router.get("/debug/job/{job_id}/details")
async def get_job_debug_details(job_id: str):
    """
    Get detailed debug information for a specific job.
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        dict: Detailed job debug information
    """
    # TODO: Implement job debug details from database
    # This is a placeholder implementation
    
    return {
        "job_id": job_id,
        "debug_info": {
            "message": "Job debug details not yet implemented",
            "note": "This endpoint will provide detailed job execution information",
            "planned_features": [
                "Job execution timeline",
                "Error details and stack traces",
                "Performance metrics",
                "Resource usage during execution",
                "API call logs and responses"
            ]
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/debug/config")
async def get_debug_config():
    """
    Get current configuration for debugging (sensitive values masked).
    
    Returns:
        dict: Current configuration with sensitive values masked
    """
    try:
        settings = get_settings()
        
        # Create debug config with masked sensitive values
        debug_config = {
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": {
                "debug": settings.DEBUG,
                "log_level": settings.LOG_LEVEL,
                "host": settings.HOST,
                "port": settings.PORT,
                "database_url": "***MASKED***" if settings.DATABASE_URL else None,
                "jira": {
                    "base_url": settings.JIRA_BASE_URL,
                    "email": settings.JIRA_EMAIL,
                    "api_token": "***MASKED***" if settings.JIRA_API_TOKEN else None
                },
                "github": {
                    "token": "***MASKED***" if settings.GITHUB_TOKEN else None
                },
                "redis_url": "***MASKED***" if settings.REDIS_URL else None,
                "cache_ttl_seconds": settings.CACHE_TTL_SECONDS
            },
            "environment_variables": {
                "total_env_vars": len(os.environ),
                "pulse_related_vars": [
                    key for key in os.environ.keys() 
                    if any(keyword in key.lower() for keyword in ['pulse', 'jira', 'github', 'database', 'redis'])
                ]
            }
        }
        
        return debug_config
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get debug config: {str(e)}")


@router.post("/debug/test-error")
async def test_error_handling():
    """
    Test endpoint to trigger an error for testing error handling.
    
    Returns:
        This endpoint always raises an exception for testing purposes.
    """
    raise HTTPException(
        status_code=500, 
        detail="This is a test error for debugging error handling mechanisms"
    )
