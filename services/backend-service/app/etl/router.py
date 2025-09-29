"""
ETL API Router
Combines all ETL-related endpoints
"""

from fastapi import APIRouter

from .wits import router as wits_router
from .statuses import router as statuses_router
from .integrations import router as integrations_router
from .qdrant import router as qdrant_router

# Create main ETL router
router = APIRouter()

# Include all ETL sub-routers
router.include_router(wits_router, tags=["ETL - Work Item Types"])
router.include_router(statuses_router, tags=["ETL - Statuses"])
router.include_router(integrations_router, tags=["ETL - Integrations"])
router.include_router(qdrant_router, tags=["ETL - Qdrant"])
