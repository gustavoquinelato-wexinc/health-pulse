"""
Qdrant Database ETL Management API
Handles Qdrant vector database operations
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
import logging

from app.auth.auth_middleware import require_authentication
from app.core.database import get_database
from app.models.unified_models import (
    User, WorkItem, Changelog, Project, Status, Wit,
    WitHierarchy, WitMapping, StatusMapping, Workflow,
    Pr, PrComment, PrReview, PrCommit, Repository,
    WorkItemPrLink, QdrantVector
)
from app.ai.qdrant_client import PulseQdrantClient

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/qdrant/test-connection")
async def test_qdrant_connection(user: User = Depends(require_authentication)):
    """Test Qdrant connection and list collections"""
    try:
        qdrant_client = PulseQdrantClient()
        connected = await qdrant_client.initialize()

        if not connected:
            return {
                "success": False,
                "error": "Failed to connect to Qdrant"
            }

        collections_response = await qdrant_client.list_collections()

        # Get detailed info for first collection if any exist
        collection_details = []
        for collection_name in collections_response.get("collections", [])[:3]:  # Test first 3
            try:
                import asyncio
                info = await asyncio.get_event_loop().run_in_executor(
                    None, qdrant_client.client.get_collection, collection_name
                )
                collection_details.append({
                    "name": collection_name,
                    "type": str(type(info)),
                    "attributes": [attr for attr in dir(info) if not attr.startswith('_')],
                    "points_count": getattr(info, 'points_count', 'N/A'),
                    "vectors_count": getattr(info, 'vectors_count', 'N/A'),
                })
            except Exception as e:
                collection_details.append({
                    "name": collection_name,
                    "error": str(e)
                })

        return {
            "success": True,
            "connected": connected,
            "collections": collections_response,
            "sample_details": collection_details
        }
    except Exception as e:
        logger.error(f"Test connection error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


class EntityStats(BaseModel):
    name: str
    database_count: int
    qdrant_count: int
    completion: int
    qdrant_collection_exists: bool = False
    qdrant_actual_vectors: int = 0


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

        # Initialize Qdrant client to get actual collection data
        qdrant_client = PulseQdrantClient()
        qdrant_connected = await qdrant_client.initialize()

        logger.info(f"🔌 Qdrant connection status: {qdrant_connected}")
        logger.info(f"🔌 Qdrant host: {qdrant_client.host}:{qdrant_client.port}")

        # Get all collections from Qdrant if connected
        qdrant_collections = {}
        if qdrant_connected:
            try:
                import asyncio

                # Get collections list
                collections_response = await qdrant_client.list_collections()
                logger.info(f"📦 Qdrant collections response: {collections_response}")
                logger.info(f"📦 Collections list: {collections_response.get('collections', [])}")

                # Build a map of collection names to their info
                for collection_name in collections_response.get("collections", []):
                    logger.info(f"🔍 Checking collection: {collection_name} (tenant_id: {tenant_id})")
                    # Extract table name from collection name (format: tenant_{tenant_id}_{table_name})
                    if collection_name.startswith(f"tenant_{tenant_id}_"):
                        table_name = collection_name.replace(f"tenant_{tenant_id}_", "")
                        logger.info(f"✅ Found collection for table: {table_name}")

                        try:
                            # Get collection info using asyncio executor
                            collection_info = await asyncio.get_event_loop().run_in_executor(
                                None, qdrant_client.client.get_collection, collection_name
                            )

                            # Extract points count - collection_info.points_count is the correct attribute
                            points_count = getattr(collection_info, 'points_count', 0)

                            logger.info(f"✓ Collection {table_name}: {points_count} points")

                            qdrant_collections[table_name] = {
                                "exists": True,
                                "vectors_count": points_count,
                                "points_count": points_count
                            }

                        except Exception as e:
                            logger.warning(f"Could not get detailed info for {collection_name}: {e}")
                            # Still mark as existing even if we can't get count
                            qdrant_collections[table_name] = {
                                "exists": True,
                                "vectors_count": 0,
                                "points_count": 0
                            }

            except Exception as e:
                logger.error(f"❌ Error fetching Qdrant collections: {e}", exc_info=True)
        else:
            logger.warning("⚠️ Qdrant client not connected")

        logger.info(f"📊 Final qdrant_collections map: {qdrant_collections}")

        with database.get_read_session_context() as session:
            # Helper function to get count and vectorized count for a table
            def get_entity_stats(model, name: str, table_name: str) -> EntityStats:
                try:
                    # Get database count
                    db_count = session.query(func.count(model.id)).filter(
                        model.tenant_id == tenant_id
                    ).scalar() or 0

                    # Query qdrant_vectors table for tracking count
                    vectorized_count = session.query(func.count(QdrantVector.id)).filter(
                        QdrantVector.tenant_id == tenant_id,
                        QdrantVector.table_name == table_name,
                        QdrantVector.active == True
                    ).scalar() or 0

                    # Get actual Qdrant collection data if available
                    qdrant_info = qdrant_collections.get(table_name, {})
                    collection_exists = qdrant_info.get("exists", False)
                    actual_vectors = qdrant_info.get("points_count", 0)

                    # Use actual Qdrant count if available, otherwise use bridge table count
                    effective_count = actual_vectors if collection_exists else vectorized_count

                    # Calculate completion percentage
                    completion = int((effective_count / db_count * 100)) if db_count > 0 else 0

                    return EntityStats(
                        name=name,
                        database_count=db_count,
                        qdrant_count=effective_count,
                        completion=completion,
                        qdrant_collection_exists=collection_exists,
                        qdrant_actual_vectors=actual_vectors
                    )
                except Exception as e:
                    logger.error(f"Error getting stats for {name}: {str(e)}")
                    # Return zero stats if there's an error
                    return EntityStats(
                        name=name,
                        database_count=0,
                        qdrant_count=0,
                        completion=0,
                        qdrant_collection_exists=False,
                        qdrant_actual_vectors=0
                    )

            # Jira entities
            jira_entities = [
                get_entity_stats(WorkItem, "Work Items", "work_items"),
                get_entity_stats(Changelog, "Changelogs", "changelogs"),
                get_entity_stats(Project, "Projects", "projects"),
                get_entity_stats(Status, "Statuses", "statuses"),
                get_entity_stats(Wit, "Work Item Types", "wits"),
                get_entity_stats(WitHierarchy, "WIT Hierarchies", "wits_hierarchies"),
                get_entity_stats(WitMapping, "WIT Mappings", "wits_mappings"),
                get_entity_stats(WorkItemPrLink, "Work Item PR Links", "work_items_prs_links"),
                get_entity_stats(StatusMapping, "Status Mappings", "statuses_mappings"),
                get_entity_stats(Workflow, "Workflows", "workflows"),
            ]

            # GitHub entities
            github_entities = [
                get_entity_stats(Pr, "Pull Requests", "prs"),
                get_entity_stats(PrComment, "PR Comments", "prs_comments"),
                get_entity_stats(PrReview, "PR Reviews", "prs_reviews"),
                get_entity_stats(PrCommit, "PR Commits", "prs_commits"),
                get_entity_stats(Repository, "Repositories", "repositories"),
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


@router.post("/qdrant/collections/create-all")
async def create_all_collections(
    user: User = Depends(require_authentication)
):
    """
    Manually create all Qdrant collections for all active tenants.
    This checks if collections exist and creates them if they don't.
    """
    try:
        from app.ai.qdrant_setup import create_all_tenant_collections

        logger.info(f"User {user.email} triggered manual collection creation for all tenants")

        # Call the async function to create collections
        result = await create_all_tenant_collections()

        if result.get("success"):
            return {
                "success": True,
                "message": "Collections created successfully",
                "collections_created": result.get("collections_created", 0),
                "collections_already_exist": result.get("collections_already_exist", 0),
                "collections_failed": result.get("collections_failed", 0),
                "total_expected": result.get("total_expected", 0),
                "tenants_processed": result.get("tenants_processed", 0)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to create collections")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating collections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create collections: {str(e)}"
        )
