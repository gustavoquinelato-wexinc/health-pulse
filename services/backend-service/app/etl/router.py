"""
ETL API Router
Combines all ETL-related endpoints
"""

from fastapi import APIRouter

from .wits import router as wits_router
from .statuses import router as statuses_router
from .integrations import router as integrations_router
from .qdrant import router as qdrant_router
from .raw_data import router as raw_data_router
from .jobs import router as jobs_router
from .jira.jira_custom_fields import router as custom_fields_router
from .jira.jira_embedding_api import router as jira_embedding_router
from .projects import router as projects_router

# Create main ETL router
router = APIRouter()

# Include all ETL sub-routers
router.include_router(wits_router, tags=["ETL - Work Item Types"])
router.include_router(statuses_router, tags=["ETL - Statuses"])
router.include_router(integrations_router, tags=["ETL - Integrations"])
router.include_router(projects_router, tags=["ETL - Projects"])
router.include_router(qdrant_router, tags=["ETL - Qdrant"])
router.include_router(raw_data_router, tags=["ETL - Raw Data"])
router.include_router(jobs_router, tags=["ETL - Jobs"])
router.include_router(custom_fields_router, tags=["ETL - Custom Fields"])
router.include_router(jira_embedding_router, tags=["ETL - Jira Embedding"])
