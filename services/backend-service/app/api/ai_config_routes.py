"""
AI Configuration Routes for ETL Service

Provides web interface routes for AI configuration including:
- AI Provider management
- Performance monitoring
- Configuration validation
- Model selection and setup
"""

from fastapi import APIRouter, Request, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
from pathlib import Path
from datetime import datetime
from sqlalchemy import func, case, text

from app.core.logging_config import get_logger
from app.core.database import get_database, get_db_session
from app.models.unified_models import Integration, AIUsageTracking, QdrantVector
from app.auth.auth_middleware import require_authentication, require_admin, UserData
from app.core.config import settings
from app.ai.hybrid_provider_manager import HybridProviderManager
from app.ai.qdrant_client import PulseQdrantClient

logger = get_logger(__name__)

# Internal authentication for service-to-service calls
def verify_internal_auth(request: Request):
    """Verify internal authentication using ETL_INTERNAL_SECRET"""
    from app.core.config import get_settings
    settings = get_settings()
    internal_secret = settings.ETL_INTERNAL_SECRET
    provided = request.headers.get("X-Internal-Auth")

    if not internal_secret:
        logger.warning("ETL_INTERNAL_SECRET not configured; rejecting internal auth request")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Internal auth not configured")
    if not provided or provided != internal_secret:
        # Don't log warning here - it's expected to fail when using user auth instead
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized internal request")

    logger.debug("Internal authentication successful")

# Initialize router
router = APIRouter()

# API Endpoints for AI Configuration

@router.get("/ai-provider-types")
async def get_ai_provider_types(user: UserData = Depends(require_admin)):
    """Get available AI provider types from the database"""
    try:
        db = get_database()

        # Get distinct provider types from integrations table
        query = text("""
            SELECT DISTINCT provider, COUNT(*) as count
            FROM integrations
            WHERE tenant_id = :tenant_id AND LOWER(type) = 'ai'
            GROUP BY provider
            ORDER BY provider
        """)

        with db.get_read_session_context() as session:
            result = session.execute(query, {"tenant_id": user.tenant_id})
            provider_types = result.fetchall()

        # Convert to list of provider types with metadata
        available_types = []
        for row in provider_types:
            provider_type = row.provider
            count = row.count

            # Add metadata for known provider types
            if 'WEX AI Gateway' in provider_type:
                available_types.append({
                    "value": provider_type,
                    "label": "WEX AI Gateway",
                    "description": "Internal WEX AI service with multiple models",
                    "count": count
                })
            elif provider_type == 'Local Embeddings':
                available_types.append({
                    "value": provider_type,
                    "label": "Local Embeddings",
                    "description": "Local embedding models (zero cost)",
                    "count": count
                })
            elif provider_type == 'WEX Embeddings':
                available_types.append({
                    "value": provider_type,
                    "label": "WEX Embeddings",
                    "description": "WEX AI Gateway embedding service",
                    "count": count
                })
            elif provider_type == 'OpenAI':
                available_types.append({
                    "value": provider_type,
                    "label": "OpenAI",
                    "description": "OpenAI API service",
                    "count": count
                })
            elif provider_type == 'Azure OpenAI':
                available_types.append({
                    "value": provider_type,
                    "label": "Azure OpenAI",
                    "description": "Microsoft Azure OpenAI service",
                    "count": count
                })
            else:
                # Unknown provider type, add with generic info
                available_types.append({
                    "value": provider_type,
                    "label": provider_type.replace('_', ' ').title(),
                    "description": f"Custom {provider_type} provider",
                    "count": count
                })

        return {
            "success": True,
            "provider_types": available_types
        }

    except Exception as e:
        logger.error(f"Error fetching AI provider types: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch AI provider types")


@router.get("/ai-providers")
async def get_ai_providers(user: UserData = Depends(require_admin)):
    """Get AI providers for the current tenant"""
    try:
        db = get_database()

        # Get AI provider integrations for this tenant
        query = text("""
            SELECT id, provider as name, provider, type, base_url, ai_model, ai_model_config,
                   cost_config, active, created_at, last_updated_at as updated_at
            FROM integrations
            WHERE tenant_id = :tenant_id AND LOWER(type) = 'ai'
            ORDER BY provider
        """)

        with db.get_read_session_context() as session:
            result = session.execute(query, {"tenant_id": user.tenant_id})
            providers = result.fetchall()

        return {
            "success": True,
            "providers": [dict(provider._mapping) for provider in providers]
        }

    except Exception as e:
        logger.error(f"Error fetching AI providers: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch AI providers")

@router.get("/ai-performance-metrics")
async def get_ai_performance_metrics(
    user: UserData = Depends(require_admin),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get AI performance metrics for the current tenant"""
    try:
        logger.info(f"AI performance metrics requested by user {user.email} (tenant {user.tenant_id})")
        logger.info(f"Date range: {start_date} to {end_date}")
        db = get_database()

        # Build query parameters
        query_params = {"tenant_id": user.tenant_id}

        # Build date filter
        date_filter = ""
        if start_date and end_date:
            date_filter = "AND created_at >= :start_date AND created_at <= :end_date"
            query_params["start_date"] = start_date
            query_params["end_date"] = end_date
        else:
            date_filter = "AND created_at >= NOW() - INTERVAL '30 days'"

        # Get performance metrics from AI usage tracking
        # Note: Using placeholder values for avg_response_time since we don't have timing data
        query = text(f"""
            SELECT
                provider as provider_name,
                COUNT(*) as total_requests,
                0.0 as avg_response_time,
                COALESCE(SUM(cost), 0.0) as total_cost,
                100.0 as success_rate
            FROM ai_usage_trackings
            WHERE tenant_id = :tenant_id
            {date_filter}
            GROUP BY provider
            ORDER BY total_requests DESC
        """)

        with db.get_read_session_context() as session:
            # First check if table exists
            table_check = session.execute(text("SELECT to_regclass('ai_usage_trackings')")).scalar()
            logger.info(f"Table check result: {table_check}")

            if table_check is None:
                logger.warning("ai_usage_trackings table does not exist")
                return {
                    "success": True,
                    "metrics": [],
                    "message": "No AI usage tracking data available (table not found)"
                }

            result = session.execute(query, query_params)
            raw_metrics = result.fetchall()
            logger.info(f"Query returned {len(raw_metrics)} raw metrics")

            # Convert to list of dicts
            provider_metrics = [dict(metric._mapping) for metric in raw_metrics]

            # Aggregate metrics for the frontend format
            total_requests = sum(m['total_requests'] for m in provider_metrics)
            total_cost = sum(m['total_cost'] for m in provider_metrics)
            avg_response_time = sum(m['avg_response_time'] for m in provider_metrics) / len(provider_metrics) if provider_metrics else 0.0
            success_rate = sum(m['success_rate'] for m in provider_metrics) / len(provider_metrics) if provider_metrics else 100.0

            # Format provider usage data
            provider_usage = [
                {
                    "provider": m['provider_name'],
                    "requests": m['total_requests'],
                    "cost": m['total_cost'],
                    "avg_response_time": m['avg_response_time']
                }
                for m in provider_metrics
            ]

            # Create daily usage data (placeholder for now)
            daily_usage = []

        return {
            "total_requests": total_requests,
            "avg_response_time": avg_response_time,
            "total_cost": total_cost,
            "success_rate": success_rate,
            "provider_usage": provider_usage,
            "daily_usage": daily_usage
        }
        
    except Exception as e:
        logger.error(f"Error fetching AI performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch performance metrics")

@router.post("/ai-providers/test")
async def test_ai_provider(
    provider_data: dict,
    user: UserData = Depends(require_admin)
):
    """Test AI provider configuration"""
    try:
        # Import hybrid provider manager for testing
        from app.ai.hybrid_provider_manager import HybridProviderManager
        
        # Create a test session
        db_session = get_db_session()
        
        try:
            # Initialize hybrid provider manager
            hybrid_manager = HybridProviderManager(db_session)

            try:
                # Test the provider configuration
                test_result = await hybrid_manager.test_provider_configuration(
                    provider_data, user.tenant_id
                )

                return {
                    "success": True,
                    "test_result": test_result
                }
            finally:
                # Cleanup AI providers to prevent event loop errors
                await hybrid_manager.cleanup()

        finally:
            db_session.close()
        
    except Exception as e:
        logger.error(f"Error testing AI provider: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# Pydantic models for request/response
class AIProviderConfig(BaseModel):
    provider: str
    type: str = "ai_provider"
    base_url: Optional[str] = None
    ai_model: str
    ai_model_config: Optional[Dict[str, Any]] = None
    cost_config: Optional[Dict[str, Any]] = None
    active: bool = True

@router.post("/ai-providers")
async def create_ai_provider(
    provider_config: AIProviderConfig,
    user: UserData = Depends(require_admin)
):
    """Create a new AI provider configuration"""
    try:
        db = get_database()
        
        # Insert new AI provider
        from app.core.utils import DateTimeHelper
        now = DateTimeHelper.now_default()

        query = text("""
            INSERT INTO integrations (
                tenant_id, provider, type, base_url, ai_model,
                ai_model_config, cost_config, active, created_at, last_updated_at
            ) VALUES (:tenant_id, :provider, 'AI', :base_url, :ai_model,
                     :ai_model_config, :cost_config, :active, :created_at, :last_updated_at)
            RETURNING id
        """)

        with db.get_write_session_context() as session:
            result = session.execute(query, {
                "tenant_id": user.tenant_id,
                "provider": provider_config.provider,
                "type": provider_config.type,
                "base_url": provider_config.base_url,
                "ai_model": provider_config.ai_model,
                "ai_model_config": provider_config.ai_model_config,
                "cost_config": provider_config.cost_config,
                "active": provider_config.active,
                "created_at": now,
                "last_updated_at": now
            })
            provider_id = result.fetchone()[0]
        
        return {
            "success": True,
            "provider_id": provider_id,
            "message": "AI provider created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating AI provider: {e}")
        raise HTTPException(status_code=500, detail="Failed to create AI provider")

@router.put("/ai-providers/{provider_id}")
async def update_ai_provider(
    provider_id: int,
    provider_config: AIProviderConfig,
    user: UserData = Depends(require_admin)
):
    """Update an existing AI provider configuration"""
    try:
        db = get_database()

        # Check if provider exists and belongs to user's tenant
        check_query = """
            SELECT id FROM integrations
            WHERE id = %s AND tenant_id = %s AND LOWER(type) = 'ai provider'
        """
        existing = db.fetch_one(check_query, (provider_id, user.tenant_id))

        if not existing:
            raise HTTPException(status_code=404, detail="AI provider not found")

        # Update AI provider
        from app.core.utils import DateTimeHelper
        now = DateTimeHelper.now_default()

        update_query = text("""
            UPDATE integrations SET
                provider = :provider, base_url = :base_url, ai_model = :ai_model,
                ai_model_config = :ai_model_config, cost_config = :cost_config,
                active = :active, last_updated_at = :last_updated_at
            WHERE id = :provider_id AND tenant_id = :tenant_id
        """)

        session.execute(update_query, {
            "provider": provider_config.provider,
            "base_url": provider_config.base_url,
            "ai_model": provider_config.ai_model,
            "ai_model_config": provider_config.ai_model_config,
            "cost_config": provider_config.cost_config,
            "active": provider_config.active,
            "provider_id": provider_id,
            "tenant_id": user.tenant_id,
            "last_updated_at": now
        })

        return {
            "success": True,
            "message": "AI provider updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating AI provider: {e}")
        raise HTTPException(status_code=500, detail="Failed to update AI provider")

@router.delete("/ai-providers/{provider_id}")
async def delete_ai_provider(
    provider_id: int,
    user: UserData = Depends(require_admin)
):
    """Delete an AI provider configuration"""
    try:
        db = get_database()

        # Check if provider exists and belongs to user's tenant
        check_query = text("""
            SELECT id, provider FROM integrations
            WHERE id = :provider_id AND tenant_id = :tenant_id AND LOWER(type) = 'ai'
        """)

        with db.get_read_session_context() as session:
            result = session.execute(check_query, {"provider_id": provider_id, "tenant_id": user.tenant_id})
            existing = result.fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail="AI provider not found")

            # Delete AI provider
            delete_query = text("""
                DELETE FROM integrations
                WHERE id = :provider_id AND tenant_id = :tenant_id AND type = 'ai_provider'
            """)

            session.execute(delete_query, {"provider_id": provider_id, "tenant_id": user.tenant_id})

        return {
            "success": True,
            "message": f"AI provider '{existing.provider}' deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting AI provider: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete AI provider")

@router.get("/ai-providers/{provider_id}")
async def get_ai_provider(
    provider_id: int,
    user: UserData = Depends(require_admin)
):
    """Get a specific AI provider configuration"""
    try:
        db = get_database()

        query = text("""
            SELECT id, provider as name, provider, type, base_url, ai_model, ai_model_config,
                   cost_config, active, created_at, last_updated_at as updated_at
            FROM integrations
            WHERE id = :provider_id AND tenant_id = :tenant_id AND LOWER(type) = 'ai'
        """)

        with db.get_read_session_context() as session:
            result = session.execute(query, {"provider_id": provider_id, "tenant_id": user.tenant_id})
            provider = result.fetchone()

        if not provider:
            raise HTTPException(status_code=404, detail="AI provider not found")

        return {
            "success": True,
            "provider": dict(provider._mapping)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching AI provider: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch AI provider")

# Embedding generation endpoint for ETL Service
@router.post("/ai/embeddings")
async def generate_embeddings(
    request: dict,
    user: UserData = Depends(require_authentication)
):
    """Generate embeddings for ETL service"""
    try:
        texts = request.get("texts", [])
        if not texts:
            raise HTTPException(status_code=400, detail="No texts provided")

        # Import hybrid provider manager
        from app.ai.hybrid_provider_manager import HybridProviderManager

        # Create a database session
        db_session = get_db_session()

        try:
            # Initialize hybrid provider manager
            hybrid_manager = HybridProviderManager(db_session)

            try:
                # Generate embeddings
                result = await hybrid_manager.generate_embeddings(texts)

                if result.success:
                    return {
                        "success": True,
                        "embeddings": result.data,
                        "provider_used": result.provider_used,
                        "processing_time": result.processing_time,
                        "cost": result.cost
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error
                    }
            finally:
                # Cleanup AI providers to prevent event loop errors
                await hybrid_manager.cleanup()

        finally:
            db_session.close()

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate embeddings")


# Vector storage endpoint for ETL Service
@router.post("/ai/vectors/store")
async def store_entity_vector(
    request: dict,
    user: UserData = Depends(require_authentication)
):
    """Store entity vector in Qdrant for ETL service"""
    try:
        # Extract request parameters
        entity_data = request.get("entity_data", {})
        table_name = request.get("table_name")
        record_id = request.get("record_id")
        tenant_id = user.tenant_id

        if not entity_data or not table_name or not record_id:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: entity_data, table_name, record_id"
            )

        # Create text content for embedding
        text_content = ""
        if isinstance(entity_data, dict):
            # Extract meaningful text fields for embedding
            text_fields = []
            for key, value in entity_data.items():
                if isinstance(value, str) and value.strip():
                    text_fields.append(f"{key}: {value}")
            text_content = " | ".join(text_fields)
        else:
            text_content = str(entity_data)

        if not text_content.strip():
            raise HTTPException(status_code=400, detail="No text content found for embedding")

        db_session = get_db_session()

        try:
            # Initialize hybrid provider manager
            hybrid_manager = HybridProviderManager(db_session)

            try:
                # Generate embedding using cost-optimized provider (local for ETL)
                embedding_result = await hybrid_manager.generate_embeddings([text_content])

                if not embedding_result.success:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to generate embedding: {embedding_result.error}"
                    )

                embedding = embedding_result.data[0]  # Get first embedding

                # Initialize Qdrant client
                qdrant_client = PulseQdrantClient()

                # Create collection name with tenant isolation
                collection_name = f"tenant_{tenant_id}_{table_name}"

                # Ensure collection exists
                await qdrant_client.ensure_collection_exists(collection_name)

                # Create unique point ID (UUID format for Qdrant compatibility)
                import uuid
                import hashlib
                # Create deterministic UUID based on tenant_id, table_name, record_id
                unique_string = f"{tenant_id}_{table_name}_{record_id}"
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

                # Store vector in Qdrant with metadata
                vector_result = await qdrant_client.upsert_vectors(
                    collection_name=collection_name,
                    vectors=[{
                        "id": point_id,
                        "vector": embedding,
                        "payload": {
                            "tenant_id": tenant_id,
                            "table_name": table_name,
                            "record_id": str(record_id),
                            "text_content": text_content[:1000],  # Truncate for storage
                            "created_at": datetime.now().isoformat()
                        }
                    }]
                )

                if not vector_result.success:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to store vector in Qdrant: {vector_result.error}"
                    )

                # Create QdrantVector bridge record in PostgreSQL
                qdrant_vector = QdrantVector(
                    tenant_id=tenant_id,
                    table_name=table_name,
                    record_id=record_id,
                    qdrant_collection=collection_name,
                    qdrant_point_id=point_id,
                    vector_type="entity_embedding",
                    embedding_model=embedding_result.provider_used,
                    embedding_provider=embedding_result.provider_used
                )

                db_session.add(qdrant_vector)
                db_session.commit()

                return {
                    "success": True,
                    "point_id": point_id,
                    "collection_name": collection_name,
                    "provider_used": embedding_result.provider_used,
                    "processing_time": embedding_result.processing_time,
                    "cost": embedding_result.cost,
                    "message": "Vector stored successfully"
                }
            finally:
                # Cleanup AI providers to prevent event loop errors
                await hybrid_manager.cleanup()

        finally:
            db_session.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing entity vector: {e}")
        raise HTTPException(status_code=500, detail="Failed to store entity vector")


# Vector search endpoint for ETL Service
@router.post("/ai/vectors/search")
async def search_similar_entities(
    request: dict,
    user: UserData = Depends(require_authentication)
):
    """Search for similar entities using vector similarity"""
    try:
        # Extract request parameters
        query_text = request.get("query_text")
        table_name = request.get("table_name")
        similarity_threshold = request.get("similarity_threshold", 0.7)
        limit = request.get("limit", 10)
        tenant_id = user.tenant_id

        if not query_text:
            raise HTTPException(status_code=400, detail="Missing required field: query_text")

        db_session = get_db_session()

        try:
            # Initialize hybrid provider manager
            hybrid_manager = HybridProviderManager(db_session)

            try:
                # Generate query embedding
                embedding_result = await hybrid_manager.generate_embeddings([query_text])

                if not embedding_result.success:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to generate query embedding: {embedding_result.error}"
                    )

                query_embedding = embedding_result.data[0]

                # Initialize Qdrant client
                qdrant_client = PulseQdrantClient()

                # Determine collections to search
                collections_to_search = []
                if table_name:
                    # Search specific table
                    collections_to_search.append(f"tenant_{tenant_id}_{table_name}")
                else:
                    # Search all collections for this tenant
                    # Get all QdrantVector records for this tenant
                    qdrant_vectors = db_session.query(QdrantVector).filter(
                        QdrantVector.tenant_id == tenant_id
                    ).all()

                    collections_to_search = list(set([
                        qv.qdrant_collection for qv in qdrant_vectors
                    ]))

                all_results = []

                # Search each collection
                for collection_name in collections_to_search:
                    try:
                        search_result = await qdrant_client.search_vectors(
                            collection_name=collection_name,
                            query_vector=query_embedding,
                            limit=limit,
                            score_threshold=similarity_threshold
                        )

                        if search_result.success and search_result.data:
                            for result in search_result.data:
                                all_results.append({
                                    "collection": collection_name,
                                    "point_id": result.get("id"),
                                    "score": result.get("score"),
                                    "payload": result.get("payload", {}),
                                    "table_name": result.get("payload", {}).get("table_name"),
                                    "record_id": result.get("payload", {}).get("record_id")
                                })

                    except Exception as collection_error:
                        logger.warning(f"Error searching collection {collection_name}: {collection_error}")
                        continue

                # Sort by score (highest first)
                all_results.sort(key=lambda x: x["score"], reverse=True)

                # Limit results
                final_results = all_results[:limit]

                return {
                    "success": True,
                    "query_text": query_text,
                    "results": final_results,
                    "total_found": len(final_results),
                    "collections_searched": collections_to_search,
                    "provider_used": embedding_result.provider_used,
                    "processing_time": embedding_result.processing_time,
                    "cost": embedding_result.cost
                }
            finally:
                # Cleanup AI providers to prevent event loop errors
                await hybrid_manager.cleanup()

        finally:
            db_session.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching similar entities: {e}")
        raise HTTPException(status_code=500, detail="Failed to search similar entities")


# Bulk vector operations endpoint for ETL Service
@router.post("/ai/vectors/bulk")
async def bulk_vector_operations(
    request: dict,
    user: UserData = Depends(require_authentication)
):
    """Bulk vector operations for ETL jobs"""
    try:
        entities = request.get("entities", [])
        operation = request.get("operation", "bulk_store")

        logger.info(f"[ETL_REQUEST] Received bulk vector request: operation={operation}, entities_count={len(entities)}")
        if entities:
            first_entity = entities[0]
            logger.info(f"[ETL_REQUEST] First entity structure: {list(first_entity.keys())}")
            logger.info(f"[ETL_REQUEST] First entity data: {first_entity.get('entity_data', {})}")
            logger.info(f"[ETL_REQUEST] First entity record_id: {first_entity.get('record_id')} (type: {type(first_entity.get('record_id'))})")
            logger.info(f"[ETL_REQUEST] First entity table_name: {first_entity.get('table_name')}")





        if not entities:
            return {"success": True, "vectors_stored": 0, "vectors_updated": 0}

        # Import AI components
        from app.ai.hybrid_provider_manager import HybridProviderManager
        from app.ai.qdrant_client import PulseQdrantClient
        from app.models.unified_models import QdrantVector
        from app.core.database import get_database

        tenant_id = user.tenant_id
        database = get_database()

        with database.get_write_session_context() as db_session:
            # Initialize AI components
            hybrid_manager = HybridProviderManager(db_session)
            await hybrid_manager.initialize_providers(tenant_id)  # Initialize providers for this tenant
            qdrant_client = PulseQdrantClient()
            await qdrant_client.initialize()

            try:
                vectors_stored = 0
                vectors_updated = 0
                vectors_failed = 0
                provider_used = None

                if operation == "bulk_store":
                    # Bulk store new vectors
                    for entity in entities:
                        try:
                            entity_data = entity.get("entity_data", {})
                            record_id = entity.get("record_id")
                            table_name = entity.get("table_name")

                            if not all([entity_data, record_id, table_name]):
                                logger.warning(f"[ETL_REQUEST] Missing required data for entity: entity_data={bool(entity_data)}, record_id={record_id}, table_name={table_name}")
                                vectors_failed += 1
                                continue

                            # Create text content for embedding
                            logger.info(f"[ETL_REQUEST] Processing entity record_id={record_id}, table={table_name}")
                            logger.info(f"[ETL_REQUEST] Entity data keys: {list(entity_data.keys())}")

                            text_parts = []
                            for key, value in entity_data.items():
                                if value is not None:
                                    text_part = f"{key}: {str(value)}"
                                    text_parts.append(text_part)
                                    logger.info(f"[ETL_REQUEST] Added text part: '{text_part}'")

                            text_content = " | ".join(text_parts)
                            logger.info(f"[ETL_REQUEST] Generated text_content: '{text_content}' (length: {len(text_content)})")

                            if not text_content.strip():
                                logger.error(f"[ETL_REQUEST] Empty text content for record_id={record_id}")
                                vectors_failed += 1
                                continue

                            # Generate embedding
                            logger.info(f"[ETL_REQUEST] Generating embedding for record_id={record_id}")
                            embedding_result = await hybrid_manager.generate_embeddings([text_content], tenant_id)
                            if not embedding_result.success:
                                logger.error(f"[ETL_REQUEST] Embedding generation failed for record_id={record_id}: {embedding_result.error}")
                                vectors_failed += 1
                                continue

                            logger.info(f"[ETL_REQUEST] Embedding generated successfully for record_id={record_id}, provider={embedding_result.provider_used}")

                            provider_used = embedding_result.provider_used
                            embedding = embedding_result.data[0]

                            # Store in Qdrant
                            collection_name = f"tenant_{tenant_id}_{table_name}"
                            logger.info(f"[ETL_REQUEST] Storing vector in Qdrant collection: {collection_name}")
                            # Create deterministic UUID for point ID
                            import uuid
                            unique_string = f"{tenant_id}_{table_name}_{record_id}"
                            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

                            # Ensure collection exists
                            await qdrant_client.ensure_collection_exists(collection_name)

                            # Prepare metadata payload
                            metadata = {
                                "tenant_id": tenant_id,
                                "table_name": table_name,
                                "record_id": record_id,
                                **entity_data
                            }

                            # Store vector in Qdrant
                            store_result = await qdrant_client.upsert_vectors(
                                collection_name=collection_name,
                                vectors=[{
                                    "id": point_id,
                                    "vector": embedding,
                                    "payload": metadata
                                }]
                            )

                            if store_result.success:
                                # Create bridge record in PostgreSQL
                                bridge_record = QdrantVector(
                                    tenant_id=tenant_id,
                                    table_name=table_name,
                                    record_id=record_id,
                                    qdrant_collection=collection_name,
                                    qdrant_point_id=point_id,
                                    vector_type="entity_embedding",
                                    embedding_model=embedding_result.provider_used,
                                    embedding_provider=embedding_result.provider_used
                                )
                                db_session.add(bridge_record)
                                vectors_stored += 1
                            else:
                                vectors_failed += 1

                        except Exception as e:
                            logger.error(f"Error storing vector for {entity.get('record_id')}: {e}")
                            vectors_failed += 1

                    # Commit all bridge records
                    db_session.commit()

                elif operation == "bulk_update":
                    # Bulk update existing vectors
                    for entity in entities:
                        try:
                            entity_data = entity.get("entity_data", {})
                            record_id = entity.get("record_id")
                            table_name = entity.get("table_name")

                            if not all([entity_data, record_id, table_name]):
                                vectors_failed += 1
                                continue

                            # Find existing vector record
                            existing_vector = db_session.query(QdrantVector).filter(
                                QdrantVector.tenant_id == tenant_id,
                                QdrantVector.table_name == table_name,
                                QdrantVector.record_id == record_id
                            ).first()

                            if not existing_vector:
                                vectors_failed += 1
                                continue

                            # Create text content for embedding
                            text_parts = []
                            for key, value in entity_data.items():
                                if value and isinstance(value, str):
                                    text_parts.append(f"{key}: {value}")

                            text_content = " | ".join(text_parts)
                            if not text_content.strip():
                                vectors_failed += 1
                                continue

                            # Generate new embedding
                            embedding_result = await hybrid_manager.generate_embeddings([text_content], tenant_id)
                            if not embedding_result.success:
                                vectors_failed += 1
                                continue

                            provider_used = embedding_result.provider_used
                            embedding = embedding_result.data[0]

                            # Prepare metadata payload
                            metadata = {
                                "tenant_id": tenant_id,
                                "table_name": table_name,
                                "record_id": record_id,
                                **entity_data
                            }

                            # Update vector in Qdrant
                            update_result = await qdrant_client.upsert_vectors(
                                collection_name=existing_vector.collection_name,
                                vectors=[{
                                    "id": existing_vector.point_id,
                                    "vector": embedding,
                                    "payload": metadata
                                }]
                            )

                            if update_result.success:
                                # Update bridge record metadata
                                from app.core.utils import DateTimeHelper
                                existing_vector.vector_metadata = entity_data
                                existing_vector.updated_at = DateTimeHelper.now_default()
                                vectors_updated += 1
                            else:
                                vectors_failed += 1

                        except Exception as e:
                            logger.error(f"Error updating vector for {entity.get('record_id')}: {e}")
                            vectors_failed += 1

                    # Commit all updates
                    db_session.commit()

                result = {
                    "success": True,
                    "vectors_stored": vectors_stored,
                    "vectors_updated": vectors_updated,
                    "vectors_failed": vectors_failed,
                    "provider_used": provider_used
                }

                logger.info(f"[ETL_REQUEST] Final result: {result}")
                return result
            finally:
                # Cleanup AI providers to prevent event loop errors
                await hybrid_manager.cleanup()

    except Exception as e:
        logger.error(f"Error in bulk vector operations: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# Vectorization Helper Functions
# ============================================================================
# These functions are used by the RabbitMQ-based VectorizationWorker
# ============================================================================


def create_text_content_from_entity(entity_data: Dict[str, Any], table_name: str) -> str:
    """
    Create text content for vectorization based on entity type.

    This function is STILL USED by the new RabbitMQ-based VectorizationWorker.
    It prepares entity data into text format for embedding generation.
    """
    try:
        # Handle None entity_data
        if entity_data is None:
            logger.warning(f"[TEXT_CONTENT] Entity data is None for table '{table_name}' - cannot create text content")
            return ""

        if not isinstance(entity_data, dict):
            logger.warning(f"[TEXT_CONTENT] Entity data is not a dict for table '{table_name}': {type(entity_data)} - cannot create text content")
            return ""

        logger.debug(f"[TEXT_CONTENT] Creating text content for table '{table_name}' with data keys: {list(entity_data.keys())}")
        if table_name == "changelogs":
            parts = []
            if entity_data.get("from_status_name"):
                parts.append(f"From: {entity_data['from_status_name']}")
            if entity_data.get("to_status_name"):
                parts.append(f"To: {entity_data['to_status_name']}")
            if entity_data.get("changed_by"):
                parts.append(f"Changed by: {entity_data['changed_by']}")
            if entity_data.get("work_item_key"):
                parts.append(f"Issue: {entity_data['work_item_key']}")
            return " | ".join(parts)

        elif table_name == "work_items":
            parts = []
            if entity_data.get("key"):
                parts.append(f"Key: {entity_data['key']}")
            if entity_data.get("summary"):
                parts.append(f"Summary: {entity_data['summary']}")
            if entity_data.get("description"):
                parts.append(f"Description: {entity_data['description']}")
            if entity_data.get("status_name"):
                parts.append(f"Status: {entity_data['status_name']}")
            return " | ".join(parts)

        elif table_name == "prs_commits":
            parts = []
            if entity_data.get("message"):
                parts.append(f"Message: {entity_data['message']}")
            if entity_data.get("author_name"):
                parts.append(f"Author: {entity_data['author_name']}")
            if entity_data.get("sha"):
                parts.append(f"SHA: {entity_data['sha'][:8]}")
            return " | ".join(parts)

        elif table_name == "prs":
            parts = []
            if entity_data.get("title"):
                parts.append(f"Title: {entity_data['title']}")
            if entity_data.get("description"):
                parts.append(f"Description: {entity_data['description']}")
            if entity_data.get("author"):
                parts.append(f"Author: {entity_data['author']}")

            # If no meaningful content, use status and dates as fallback
            if not parts:
                if entity_data.get("status"):
                    parts.append(f"Status: {entity_data['status']}")
                if entity_data.get("created_at"):
                    parts.append(f"Created: {entity_data['created_at']}")
                if entity_data.get("updated_at"):
                    parts.append(f"Updated: {entity_data['updated_at']}")

            content = " | ".join(parts)
            logger.debug(f"[TEXT_CONTENT] PR content for table '{table_name}': '{content[:100]}...' (length: {len(content)})")
            return content

        elif table_name == "repositories":
            parts = []
            if entity_data.get("name"):
                parts.append(f"Name: {entity_data['name']}")
            if entity_data.get("description"):
                parts.append(f"Description: {entity_data['description']}")
            if entity_data.get("language"):
                parts.append(f"Language: {entity_data['language']}")
            if entity_data.get("topics"):
                parts.append(f"Topics: {', '.join(entity_data['topics']) if isinstance(entity_data['topics'], list) else entity_data['topics']}")

            content = " | ".join(parts)
            logger.debug(f"[TEXT_CONTENT] Repository content for table '{table_name}': '{content[:100]}...' (length: {len(content)})")
            return content

        elif table_name == "statuses":
            parts = []
            if entity_data.get("original_name"):
                parts.append(f"Name: {entity_data['original_name']}")
            if entity_data.get("category"):
                parts.append(f"Category: {entity_data['category']}")
            if entity_data.get("description"):
                parts.append(f"Description: {entity_data['description']}")

            content = " | ".join(parts)
            logger.debug(f"[TEXT_CONTENT] Status content for table '{table_name}': '{content[:100]}...' (length: {len(content)})")
            return content

        elif table_name == "projects":
            parts = []
            if entity_data.get("key"):
                parts.append(f"Key: {entity_data['key']}")
            if entity_data.get("name"):
                parts.append(f"Name: {entity_data['name']}")
            if entity_data.get("project_type"):
                parts.append(f"Type: {entity_data['project_type']}")
            if entity_data.get("external_id"):
                parts.append(f"ID: {entity_data['external_id']}")

            content = " | ".join(parts)
            logger.debug(f"[TEXT_CONTENT] Project content for table '{table_name}': '{content[:100]}...' (length: {len(content)})")
            return content

        elif table_name == "wits":
            parts = []
            # Use original_name (not name) to match Wit model
            if entity_data.get("original_name"):
                parts.append(f"Name: {entity_data['original_name']}")
            if entity_data.get("description"):
                parts.append(f"Description: {entity_data['description']}")
            if entity_data.get("hierarchy_level") is not None:
                parts.append(f"Level: {entity_data['hierarchy_level']}")

            # If no description, at least use the name
            if not parts and entity_data.get("original_name"):
                parts.append(f"Issue Type: {entity_data['original_name']}")

            content = " | ".join(parts)
            logger.debug(f"[TEXT_CONTENT] WIT content for table '{table_name}': '{content[:100]}...' (length: {len(content)})")
            return content

        else:
            # Generic fallback
            content = " | ".join([f"{k}: {v}" for k, v in entity_data.items() if v and k != "external_id"])
            logger.debug(f"[TEXT_CONTENT] Generic fallback for table '{table_name}': '{content[:100]}...' (length: {len(content)})")
            return content

    except Exception as e:
        logger.error(f"[TEXT_CONTENT] ❌ Error creating text content for {table_name}: {e}")
        import traceback
        logger.error(f"[TEXT_CONTENT] Full traceback: {traceback.format_exc()}")
        return ""

