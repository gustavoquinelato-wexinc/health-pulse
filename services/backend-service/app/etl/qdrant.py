"""
Qdrant Database ETL Management API
Handles Qdrant vector database operations
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func

from app.auth.auth_middleware import require_authentication
from app.core.database import get_database
from app.models.unified_models import (
    User, WorkItem, Changelog, Project, Status, Wit,
    WitHierarchy, WitMapping, StatusMapping, Workflow,
    Pr, PrComment, PrReview, PrCommit, Repository,
    WorkItemPrLink
)

router = APIRouter()


class EntityStats(BaseModel):
    name: str
    database_count: int
    qdrant_count: int
    completion: int


class IntegrationGroup(BaseModel):
    title: str
    logo_filename: str
    entities: List[EntityStats]


class QdrantDashboardResponse(BaseModel):
    total_database: int
    total_vectorized: int
    overall_completion: int
    integration_groups: List[IntegrationGroup]
    queue_pending: int
    queue_failed: int


@router.get("/qdrant/dashboard", response_model=QdrantDashboardResponse)
async def get_qdrant_dashboard(
    user: User = Depends(require_authentication)
):
    """Get Qdrant dashboard data with real database counts and vectorization status"""
    try:
        database = get_database()
        tenant_id = user.tenant_id

        with database.get_read_session_context() as session:
            # Helper function to get count and vectorized count for a table
            def get_entity_stats(model, name: str) -> EntityStats:
                try:
                    # Get database count
                    db_count = session.query(func.count(model.id)).filter(
                        model.tenant_id == tenant_id
                    ).scalar() or 0

                    # NOTE: vectorization_queue table was removed in migration 0005
                    # Vectorization is now integrated into transform workers
                    # TODO: Query Qdrant directly for actual vectorized counts
                    # For now, set to 0 (no vectorization tracking)
                    vectorized_count = 0

                    # Calculate completion percentage
                    completion = int((vectorized_count / db_count * 100)) if db_count > 0 else 0

                    return EntityStats(
                        name=name,
                        database_count=db_count,
                        qdrant_count=vectorized_count,
                        completion=completion
                    )
                except Exception as e:
                    print(f"Error getting stats for {name}: {str(e)}")
                    # Return zero stats if there's an error
                    return EntityStats(
                        name=name,
                        database_count=0,
                        qdrant_count=0,
                        completion=0
                    )

            # Jira entities
            jira_entities = [
                get_entity_stats(WorkItem, "Work Items"),
                get_entity_stats(Changelog, "Changelogs"),
                get_entity_stats(Project, "Projects"),
                get_entity_stats(Status, "Statuses"),
                get_entity_stats(Wit, "Work Item Types"),
                get_entity_stats(WitHierarchy, "WIT Hierarchies"),
                get_entity_stats(WitMapping, "WIT Mappings"),
                get_entity_stats(WorkItemPrLink, "Work Item PR Links"),
                get_entity_stats(StatusMapping, "Status Mappings"),
                get_entity_stats(Workflow, "Workflows"),
            ]

            # GitHub entities
            github_entities = [
                get_entity_stats(Pr, "Pull Requests"),
                get_entity_stats(PrComment, "PR Comments"),
                get_entity_stats(PrReview, "PR Reviews"),
                get_entity_stats(PrCommit, "PR Commits"),
                get_entity_stats(Repository, "Repositories"),
            ]

            # Create integration groups
            integration_groups = [
                IntegrationGroup(
                    title="Jira",
                    logo_filename="jira.svg",
                    entities=jira_entities
                ),
                IntegrationGroup(
                    title="GitHub",
                    logo_filename="github.svg",
                    entities=github_entities
                )
            ]

            # Calculate totals
            total_database = sum(e.database_count for group in integration_groups for e in group.entities)
            total_vectorized = sum(e.qdrant_count for group in integration_groups for e in group.entities)
            overall_completion = int((total_vectorized / total_database * 100)) if total_database > 0 else 0

            # NOTE: vectorization_queue table was removed in migration 0005
            # Vectorization is now integrated into transform workers
            # Set queue stats to 0 (no separate queue anymore)
            queue_pending = 0
            queue_failed = 0

            return QdrantDashboardResponse(
                total_database=total_database,
                total_vectorized=total_vectorized,
                overall_completion=overall_completion,
                integration_groups=integration_groups,
                queue_pending=queue_pending,
                queue_failed=queue_failed
            )

    except Exception as e:
        import traceback
        error_detail = f"Failed to fetch Qdrant dashboard data: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)  # Log to console for debugging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Qdrant dashboard data: {str(e)}"
        )


@router.get("/qdrant/health")
async def get_qdrant_health(
    user: User = Depends(require_authentication)
):
    """Get Qdrant database health status"""
    try:
        # TODO: Implement actual Qdrant health check
        # For now, return mock health data
        return {
            "status": "healthy",
            "version": "1.7.4",
            "uptime_seconds": 86400,  # 1 day
            "memory_usage": {
                "used_bytes": 134217728,  # 128MB
                "available_bytes": 1073741824  # 1GB
            },
            "disk_usage": {
                "used_bytes": 104857600,  # 100MB
                "available_bytes": 10737418240  # 10GB
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Qdrant health: {str(e)}"
        )
