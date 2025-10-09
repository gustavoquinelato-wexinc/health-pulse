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
        logger.warning(f"Invalid internal auth: expected secret, got {provided[:10] if provided else 'None'}...")
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

        with db.get_session_context() as session:
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

        with db.get_session_context() as session:
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

        with db.get_session_context() as session:
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
            
            # Test the provider configuration
            test_result = await hybrid_manager.test_provider_configuration(
                provider_data, user.tenant_id
            )
            
            return {
                "success": True,
                "test_result": test_result
            }
            
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
        query = text("""
            INSERT INTO integrations (
                tenant_id, provider, type, base_url, ai_model,
                ai_model_config, cost_config, active, created_at, last_updated_at
            ) VALUES (:tenant_id, :provider, 'AI', :base_url, :ai_model,
                     :ai_model_config, :cost_config, :active, NOW(), NOW())
            RETURNING id
        """)

        with db.get_session_context() as session:
            result = session.execute(query, {
                "tenant_id": user.tenant_id,
                "provider": provider_config.provider,
                "type": provider_config.type,
                "base_url": provider_config.base_url,
                "ai_model": provider_config.ai_model,
                "ai_model_config": provider_config.ai_model_config,
                "cost_config": provider_config.cost_config,
                "active": provider_config.active
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
            update_query = text("""
                UPDATE integrations SET
                    provider = :provider, base_url = :base_url, ai_model = :ai_model,
                    ai_model_config = :ai_model_config, cost_config = :cost_config,
                    active = :active, last_updated_at = NOW()
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
                "tenant_id": user.tenant_id
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

        with db.get_session_context() as session:
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

        with db.get_session_context() as session:
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
            collection_name = f"client_{tenant_id}_{table_name}"

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
                collections_to_search.append(f"client_{tenant_id}_{table_name}")
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
                        collection_name = f"client_{tenant_id}_{table_name}"
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
                            existing_vector.vector_metadata = entity_data
                            existing_vector.updated_at = datetime.utcnow()
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

    except Exception as e:
        logger.error(f"Error in bulk vector operations: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# DEPRECATED: Old Vectorization Queue Endpoints (Database-based)
# ============================================================================
# These endpoints are DEPRECATED and will be removed in a future release.
# The new ETL architecture uses RabbitMQ-based vectorization queues instead
# of database tables. See VectorizationWorker in app/workers/vectorization_worker.py
# ============================================================================

class VectorizationQueueRequest(BaseModel):
    tenant_id: int

class VectorizationCleanupRequest(BaseModel):
    tenant_id: int
    retention_hours: Optional[int] = 24

class VectorizationFailedCleanupRequest(BaseModel):
    tenant_id: int
    retention_days: Optional[int] = 7
    confirm_delete_failed: bool = False  # Safety flag

class QdrantCleanupRequest(BaseModel):
    tenant_id: Optional[int] = None  # If None, cleans all tenants
    confirm_delete_all: bool = False  # Safety flag

@router.post("/ai/vectors/process-queue")
async def process_vectorization_queue(
    request: VectorizationQueueRequest,
    background_tasks: BackgroundTasks,
    user: UserData = Depends(require_authentication)
):
    """
    DEPRECATED: Process vectorization queue for a tenant (async)

    This endpoint is deprecated. The new ETL architecture uses RabbitMQ-based
    vectorization queues managed by VectorizationWorker instead of database tables.
    """
    logger.warning("DEPRECATED: /ai/vectors/process-queue endpoint called - use RabbitMQ-based vectorization instead")
    try:
        from fastapi import BackgroundTasks
        from app.models.unified_models import VectorizationQueue

        tenant_id = request.tenant_id

        logger.info(f"[QUEUE_PROCESSOR] Received vectorization trigger request for tenant {tenant_id}")
        logger.info(f"[QUEUE_PROCESSOR] User: {user.email} (tenant: {user.tenant_id})")

        # Verify user has access to this tenant
        if user.tenant_id != tenant_id:
            logger.warning(f"[QUEUE_PROCESSOR] Access denied: user tenant {user.tenant_id} != requested tenant {tenant_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this tenant"
            )

        # Start background processing
        import asyncio
        asyncio.create_task(process_tenant_vectorization_queue(tenant_id))

        logger.info(f"[QUEUE_PROCESSOR] Started async vectorization processing for tenant {tenant_id}")

        return {"status": "processing_started", "tenant_id": tenant_id}

    except Exception as e:
        logger.error(f"Error starting vectorization queue processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start processing: {str(e)}"
        )


@router.post("/ai/vectors/process-queue-internal")
async def process_vectorization_queue_internal(
    request: VectorizationQueueRequest,
    background_tasks: BackgroundTasks,
    req: Request
):
    """
    DEPRECATED: Process vectorization queue for a tenant (async) - Internal service endpoint

    This endpoint is deprecated. The new ETL architecture uses RabbitMQ-based
    vectorization queues managed by VectorizationWorker instead of database tables.
    """
    logger.warning("DEPRECATED: /ai/vectors/process-queue-internal endpoint called - use RabbitMQ-based vectorization instead")
    try:
        # Verify internal authentication
        verify_internal_auth(req)

        from fastapi import BackgroundTasks
        from app.models.unified_models import VectorizationQueue

        tenant_id = request.tenant_id

        logger.info(f"[QUEUE_PROCESSOR_INTERNAL] Received vectorization trigger request for tenant {tenant_id}")

        # Start background processing
        import asyncio
        asyncio.create_task(process_tenant_vectorization_queue(tenant_id))

        logger.info(f"[QUEUE_PROCESSOR_INTERNAL] Started async vectorization processing for tenant {tenant_id}")

        return {"status": "processing_started", "tenant_id": tenant_id}

    except Exception as e:
        logger.error(f"Error starting vectorization queue processing (internal): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start processing: {str(e)}"
        )


@router.post("/ai/vectors/cleanup-queue")
async def cleanup_vectorization_queue(
    request: VectorizationCleanupRequest,
    user: UserData = Depends(require_admin)  # Admin only for manual cleanup
):
    """Manually clean up old vectorization queue records"""
    try:
        from app.models.unified_models import VectorizationQueue

        tenant_id = request.tenant_id
        retention_hours = request.retention_hours

        with get_db_session() as session:
            await cleanup_old_completed_records(session, tenant_id, retention_hours)

            # Get current queue stats
            pending_count = session.query(VectorizationQueue).filter(
                VectorizationQueue.tenant_id == tenant_id,
                VectorizationQueue.status == 'pending'
            ).count()

            processing_count = session.query(VectorizationQueue).filter(
                VectorizationQueue.tenant_id == tenant_id,
                VectorizationQueue.status == 'processing'
            ).count()

            completed_count = session.query(VectorizationQueue).filter(
                VectorizationQueue.tenant_id == tenant_id,
                VectorizationQueue.status == 'completed'
            ).count()

            failed_count = session.query(VectorizationQueue).filter(
                VectorizationQueue.tenant_id == tenant_id,
                VectorizationQueue.status == 'failed'
            ).count()

        logger.info(f"[CLEANUP] Manual cleanup completed for tenant {tenant_id}")

        return {
            "status": "cleanup_completed",
            "tenant_id": tenant_id,
            "retention_hours": retention_hours,
            "current_queue_stats": {
                "pending": pending_count,
                "processing": processing_count,
                "completed": completed_count,
                "failed": failed_count
            }
        }

    except Exception as e:
        logger.error(f"Error in manual cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup: {str(e)}"
        )


@router.post("/ai/vectors/cleanup-failed-queue")
async def cleanup_failed_vectorization_queue(
    request: VectorizationFailedCleanupRequest,
    user: UserData = Depends(require_admin)  # Admin only
):
    """Manually clean up old FAILED vectorization queue records (admin only with confirmation)"""
    try:
        from app.models.unified_models import VectorizationQueue
        from datetime import datetime, timedelta

        tenant_id = request.tenant_id
        retention_days = request.retention_days
        confirm_delete = request.confirm_delete_failed

        if not confirm_delete:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must set confirm_delete_failed=true to delete failed records"
            )

        with get_db_session() as session:
            # Calculate cutoff time for failed records
            failed_cutoff_time = datetime.utcnow() - timedelta(days=retention_days)

            # Get count before deletion for reporting
            failed_count_before = session.query(VectorizationQueue).filter(
                VectorizationQueue.tenant_id == tenant_id,
                VectorizationQueue.status == 'failed',
                VectorizationQueue.last_error_at < failed_cutoff_time
            ).count()

            # Delete old failed records
            failed_deleted_count = session.query(VectorizationQueue).filter(
                VectorizationQueue.tenant_id == tenant_id,
                VectorizationQueue.status == 'failed',
                VectorizationQueue.last_error_at < failed_cutoff_time
            ).delete()

            session.commit()

            # Get remaining failed count
            remaining_failed_count = session.query(VectorizationQueue).filter(
                VectorizationQueue.tenant_id == tenant_id,
                VectorizationQueue.status == 'failed'
            ).count()

        logger.info(f"[FAILED_CLEANUP] Tenant {tenant_id}: Deleted {failed_deleted_count} old failed records (older than {retention_days} days)")

        return {
            "status": "failed_cleanup_completed",
            "tenant_id": tenant_id,
            "retention_days": retention_days,
            "failed_records_deleted": failed_deleted_count,
            "remaining_failed_records": remaining_failed_count,
            "warning": "Failed records contain valuable debugging information. Consider investigating before deletion."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in failed records cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup failed records: {str(e)}"
        )


@router.post("/ai/vectors/cleanup-qdrant")
async def cleanup_qdrant_collections(
    request: QdrantCleanupRequest,
    user: UserData = Depends(require_admin)  # Admin only
):
    """Completely clean up Qdrant collections (DANGEROUS - Admin only with confirmation)"""
    try:
        from app.ai.qdrant_client import PulseQdrantClient
        from app.models.unified_models import QdrantVector

        tenant_id = request.tenant_id
        confirm_delete = request.confirm_delete_all

        if not confirm_delete:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must set confirm_delete_all=true to delete Qdrant collections"
            )

        qdrant_client = PulseQdrantClient()
        deleted_collections = []
        failed_deletions = []

        with get_db_session() as session:
            if tenant_id:
                # Clean up specific tenant's collections
                logger.info(f"[QDRANT_CLEANUP] Cleaning up collections for tenant {tenant_id}")

                # Get collections for this tenant from database
                qdrant_records = session.query(QdrantVector).filter(
                    QdrantVector.tenant_id == tenant_id
                ).all()

                # Get unique collection names
                collections_to_delete = set(record.qdrant_collection for record in qdrant_records)

            else:
                # Clean up ALL collections (nuclear option)
                logger.warning("[QDRANT_CLEANUP] NUCLEAR CLEANUP: Deleting ALL Qdrant collections")

                # Get all collections from Qdrant directly
                try:
                    collections_info = await qdrant_client.list_collections()
                    collections_to_delete = set(collections_info.get('collections', []))
                except Exception as e:
                    logger.error(f"Failed to list Qdrant collections: {e}")
                    collections_to_delete = set()

                # Also get collections from database
                qdrant_records = session.query(QdrantVector).all()
                db_collections = set(record.qdrant_collection for record in qdrant_records)
                collections_to_delete.update(db_collections)

            # Delete each collection
            for collection_name in collections_to_delete:
                try:
                    success = await qdrant_client.delete_collection(collection_name)
                    if success:
                        deleted_collections.append(collection_name)
                        logger.info(f"[QDRANT_CLEANUP] Deleted collection: {collection_name}")
                    else:
                        failed_deletions.append(collection_name)
                        logger.error(f"[QDRANT_CLEANUP] Failed to delete collection: {collection_name}")
                except Exception as e:
                    failed_deletions.append(collection_name)
                    logger.error(f"[QDRANT_CLEANUP] Error deleting collection {collection_name}: {e}")

            # Clean up database records
            if tenant_id:
                # Delete QdrantVector records for specific tenant
                db_deleted_count = session.query(QdrantVector).filter(
                    QdrantVector.tenant_id == tenant_id
                ).delete()
            else:
                # Delete ALL QdrantVector records
                db_deleted_count = session.query(QdrantVector).delete()

            session.commit()

        result = {
            "status": "qdrant_cleanup_completed",
            "tenant_id": tenant_id or "ALL_TENANTS",
            "collections_deleted": deleted_collections,
            "failed_deletions": failed_deletions,
            "database_records_deleted": db_deleted_count,
            "total_collections_processed": len(collections_to_delete),
            "warning": "This operation permanently deletes all vector data. Make sure you have backups if needed."
        }

        logger.info(f"[QDRANT_CLEANUP] Cleanup completed: {len(deleted_collections)} collections deleted, {len(failed_deletions)} failed")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Qdrant cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup Qdrant: {str(e)}"
        )


async def process_tenant_vectorization_queue(tenant_id: int, progress_batch_size: int = 20):
    """
    DEPRECATED: Process ALL pending vectorization items for a tenant with progress updates every N items

    This function is deprecated. The new ETL architecture uses RabbitMQ-based
    vectorization queues managed by VectorizationWorker instead of database tables.
    """
    logger.warning("DEPRECATED: process_tenant_vectorization_queue called - use RabbitMQ-based vectorization instead")
    try:
        from app.models.unified_models import VectorizationQueue
        from datetime import datetime
        from app.core.database import get_database

        database = get_database()
        with database.get_write_session_context() as session:
            # Check total queue items first
            total_queue_items = session.query(VectorizationQueue).filter(
                VectorizationQueue.tenant_id == tenant_id
            ).count()

            pending_queue_items = session.query(VectorizationQueue).filter(
                VectorizationQueue.status == 'pending',
                VectorizationQueue.tenant_id == tenant_id
            ).count()

            # Check for stuck "processing" items and reset them to "pending" for retry
            stuck_processing_items = session.query(VectorizationQueue).filter(
                VectorizationQueue.status == 'processing',
                VectorizationQueue.tenant_id == tenant_id
            ).count()

            if stuck_processing_items > 0:
                logger.warning(f"[QUEUE_PROCESSOR] Found {stuck_processing_items} stuck 'processing' items - resetting to 'pending' for retry")
                session.query(VectorizationQueue).filter(
                    VectorizationQueue.status == 'processing',
                    VectorizationQueue.tenant_id == tenant_id
                ).update({
                    'status': 'pending',
                    'started_at': None,
                    'error_message': 'Reset from stuck processing status'
                })
                session.commit()

                # Recalculate pending count after reset
                pending_queue_items = session.query(VectorizationQueue).filter(
                    VectorizationQueue.status == 'pending',
                    VectorizationQueue.tenant_id == tenant_id
                ).count()

                logger.info(f"[QUEUE_PROCESSOR] After reset: {pending_queue_items} pending items")

            logger.info(f"[QUEUE_PROCESSOR] Queue status for tenant {tenant_id}: {pending_queue_items} pending, {total_queue_items} total")

            if pending_queue_items == 0:
                logger.info(f"[QUEUE_PROCESSOR] No pending vectorization items for tenant {tenant_id}")
                await send_vectorization_progress(tenant_id, 100, "No items to process - queue is empty")
                return

            # Send initial progress
            await send_vectorization_progress(tenant_id, 0, f"Starting vectorization of {pending_queue_items} entities...")

            # Process ALL items in batches, sending progress updates every progress_batch_size items
            total_processed = 0
            total_successful = 0
            total_failed = 0
            processing_batch_size = 5  # Process 5 items at a time for efficiency

            while True:
                # Get next batch of pending items
                pending_items = session.query(VectorizationQueue).filter(
                    VectorizationQueue.status == 'pending',
                    VectorizationQueue.tenant_id == tenant_id
                ).order_by(
                    VectorizationQueue.created_at.asc()
                ).limit(processing_batch_size).all()

                # Break if no more items to process
                if not pending_items:
                    logger.info(f"[QUEUE_PROCESSOR] No more pending items - processing complete")
                    break

                # Process this batch
                batch_result = await process_vectorization_batch(session, pending_items)
                batch_successful = batch_result.get('vectors_stored', 0)
                batch_failed = batch_result.get('vectors_failed', 0)

                total_processed += len(pending_items)
                total_successful += batch_successful
                total_failed += batch_failed

                logger.info(f"[QUEUE_PROCESSOR] Processed batch: {batch_successful} successful, {batch_failed} failed")

                # Send progress update every progress_batch_size items (webhook-style)
                if total_processed % progress_batch_size == 0 or len(pending_items) < processing_batch_size:
                    progress_percentage = min(95, (total_processed / pending_queue_items) * 100)
                    status_msg = f"Processed {total_processed}/{pending_queue_items}: {total_successful} successful, {total_failed} failed"
                    await send_vectorization_progress(
                        tenant_id, progress_percentage, status_msg,
                        items_processed=total_successful, items_failed=total_failed, total_items=pending_queue_items
                    )

                # Small delay to prevent overwhelming the system
                import asyncio
                await asyncio.sleep(0.1)

                # Refresh session to get updated counts
                session.commit()

            # Send completion notification with summary
            completion_msg = f"Vectorization complete: {total_successful} successful, {total_failed} failed ({total_processed} total)"
            await send_vectorization_progress(
                tenant_id, 95, completion_msg,
                items_processed=total_successful, items_failed=total_failed, total_items=pending_queue_items
            )

            # Clean up completed records immediately after processing
            logger.info(f"[QUEUE_PROCESSOR] Starting cleanup of completed records for tenant {tenant_id}")
            await send_vectorization_progress(tenant_id, 98, "Cleaning up completed records...")

            cleanup_result = await cleanup_completed_records_immediately(session, tenant_id)
            cleanup_msg = f"Cleanup complete: {cleanup_result['deleted_count']} completed records removed"
            logger.info(f"[QUEUE_PROCESSOR] {cleanup_msg}")

            await send_vectorization_progress(
                tenant_id, 100, f"{completion_msg}. {cleanup_msg}",
                items_processed=total_successful, items_failed=total_failed, total_items=pending_queue_items
            )

    except Exception as e:
        logger.error(f"[QUEUE_PROCESSOR] Error processing vectorization queue for tenant {tenant_id}: {e}")
        # Send error notification
        await send_vectorization_progress(tenant_id, 0, f"Vectorization failed: {str(e)}")


async def get_internal_ids_for_table(session, table_name: str, external_ids: list) -> dict:
    """
    Get internal database IDs for external IDs by joining with the appropriate table.

    Args:
        session: Database session
        table_name: Name of the table (prs, work_items, etc.)
        external_ids: List of external IDs to look up

    Returns:
        Dict mapping external_id -> internal_id
    """
    from app.models.unified_models import Pr, PrCommit, PrReview, PrComment, WorkItem, Changelog, Project, Status, Wit

    mappings = {}

    try:
        if table_name == 'prs':
            results = session.query(Pr.id, Pr.external_id).filter(
                Pr.external_id.in_(external_ids)
            ).all()
        elif table_name == 'prs_commits':
            results = session.query(PrCommit.id, PrCommit.external_id).filter(
                PrCommit.external_id.in_(external_ids)
            ).all()
        elif table_name == 'prs_reviews':
            results = session.query(PrReview.id, PrReview.external_id).filter(
                PrReview.external_id.in_(external_ids)
            ).all()
        elif table_name == 'prs_comments':
            results = session.query(PrComment.id, PrComment.external_id).filter(
                PrComment.external_id.in_(external_ids)
            ).all()
        elif table_name == 'work_items':
            # For work_items, we use the 'key' field (Jira issue key like "BDP-552")
            # not the 'external_id' field (which contains Jira internal ID)
            results = session.query(WorkItem.id, WorkItem.key).filter(
                WorkItem.key.in_(external_ids)
            ).all()
        elif table_name == 'changelogs':
            results = session.query(Changelog.id, Changelog.external_id).filter(
                Changelog.external_id.in_(external_ids)
            ).all()
        elif table_name == 'projects':
            results = session.query(Project.id, Project.external_id).filter(
                Project.external_id.in_(external_ids)
            ).all()
        elif table_name == 'statuses':
            results = session.query(Status.id, Status.external_id).filter(
                Status.external_id.in_(external_ids)
            ).all()
        elif table_name == 'wits':
            results = session.query(Wit.id, Wit.external_id).filter(
                Wit.external_id.in_(external_ids)
            ).all()
        elif table_name == 'work_items_prs_links':
            # For work_items_prs_links, the external_id is actually the internal database ID
            # This is the only exception to the external ID rule
            from app.models.unified_models import WorkItemPrLink
            results = session.query(WorkItemPrLink.id, WorkItemPrLink.id).filter(
                WorkItemPrLink.id.in_([int(eid) for eid in external_ids if eid.isdigit()])
            ).all()
        elif table_name == 'repositories':
            from app.models.unified_models import Repository
            # Convert external_ids to strings since repositories.external_id is VARCHAR
            string_external_ids = [str(eid) for eid in external_ids]
            results = session.query(Repository.id, Repository.external_id).filter(
                Repository.external_id.in_(string_external_ids)
            ).all()
        else:
            logger.warning(f"Unknown table name for ID mapping: {table_name}")
            return mappings

        # Build mapping dictionary
        for internal_id, external_id in results:
            mappings[str(external_id)] = internal_id

        logger.debug(f"Mapped {len(mappings)}/{len(external_ids)} external IDs for table {table_name}")

    except Exception as e:
        logger.error(f"Error getting internal IDs for table {table_name}: {e}")

    return mappings


async def process_vectorization_batch(session, batch_items):
    """
    DEPRECATED: Process a batch of vectorization items and return detailed results

    This function is deprecated. The new ETL architecture uses RabbitMQ-based
    vectorization queues managed by VectorizationWorker instead of database tables.
    """
    logger.warning("DEPRECATED: process_vectorization_batch called - use RabbitMQ-based vectorization instead")
    try:
        from datetime import datetime

        logger.info(f"[QUEUE_PROCESSOR] ===== STARTING BATCH PROCESSING =====")
        logger.info(f"[QUEUE_PROCESSOR] Batch size: {len(batch_items)} items")

        # Log each item in the batch
        for i, item in enumerate(batch_items):
            logger.info(f"[QUEUE_PROCESSOR] Item {i+1}: ID={item.id}, Table={item.table_name}, External_ID={item.external_id}, Status={item.status}")

        # Mark as processing
        logger.info(f"[QUEUE_PROCESSOR] STEP 1: Marking {len(batch_items)} items as processing...")
        for item in batch_items:
            item.status = 'processing'
            item.started_at = datetime.utcnow()
        session.commit()
        logger.info(f"[QUEUE_PROCESSOR] STEP 1: ✅ Successfully marked items as processing")

        # Group items by table for efficient joining
        logger.info(f"[QUEUE_PROCESSOR] STEP 2: Grouping items by table...")
        items_by_table = {}
        for item in batch_items:
            table_name = item.table_name
            if table_name not in items_by_table:
                items_by_table[table_name] = []
            items_by_table[table_name].append(item)

        logger.info(f"[QUEUE_PROCESSOR] STEP 2: ✅ Grouped into {len(items_by_table)} table groups: {list(items_by_table.keys())}")

        # Prepare for bulk vectorization with internal IDs
        logger.info(f"[QUEUE_PROCESSOR] STEP 3: Preparing entities for vectorization...")
        entities_to_vectorize = []

        # Process each table group
        for table_name, table_items in items_by_table.items():
            logger.info(f"[QUEUE_PROCESSOR] STEP 3.{table_name}: Processing {len(table_items)} items from table '{table_name}'")
            external_ids = [item.external_id for item in table_items]
            logger.info(f"[QUEUE_PROCESSOR] STEP 3.{table_name}: External IDs: {external_ids}")

            # Get internal IDs by joining with actual tables
            logger.info(f"[QUEUE_PROCESSOR] STEP 3.{table_name}: Looking up internal IDs...")
            internal_id_mappings = await get_internal_ids_for_table(session, table_name, external_ids)
            logger.info(f"[QUEUE_PROCESSOR] STEP 3.{table_name}: Found {len(internal_id_mappings)} internal ID mappings: {internal_id_mappings}")

            # Create vectorization entities with internal IDs
            logger.info(f"[QUEUE_PROCESSOR] STEP 3.{table_name}: Creating vectorization entities...")
            entities_created = 0
            entities_failed = 0

            for item in table_items:
                internal_id = internal_id_mappings.get(item.external_id)
                if internal_id:
                    entities_to_vectorize.append({
                        "entity_data": item.entity_data,  # Direct from queue
                        "record_id": internal_id,  # Internal database ID
                        "table_name": table_name,
                        "queue_item": item  # Reference for status updates
                    })
                    entities_created += 1
                    logger.debug(f"[QUEUE_PROCESSOR] STEP 3.{table_name}: ✅ Created entity for external_id {item.external_id} -> internal_id {internal_id}")
                else:
                    # Mark as failed if no internal ID found
                    error_msg = f"No internal ID found for external_id {item.external_id} in table {table_name}"
                    item.status = 'failed'
                    item.error_message = error_msg
                    item.last_error_at = datetime.utcnow()
                    entities_failed += 1
                    logger.error(f"[QUEUE_PROCESSOR] STEP 3.{table_name}: ❌ {error_msg}")

            logger.info(f"[QUEUE_PROCESSOR] STEP 3.{table_name}: ✅ Created {entities_created} entities, {entities_failed} failed")

        # Only process entities that have valid internal IDs
        logger.info(f"[QUEUE_PROCESSOR] STEP 4: Bulk vectorization...")
        if entities_to_vectorize:
            logger.info(f"[QUEUE_PROCESSOR] STEP 4: Processing {len(entities_to_vectorize)} entities for vectorization")

            # Log each entity being vectorized
            for i, entity in enumerate(entities_to_vectorize):
                logger.debug(f"[QUEUE_PROCESSOR] STEP 4: Entity {i+1}: table={entity['table_name']}, record_id={entity['record_id']}")

            # Bulk vectorize using existing function
            logger.info(f"[QUEUE_PROCESSOR] STEP 4: Calling bulk_vectorize_entities_from_queue...")
            result = await bulk_vectorize_entities_from_queue(entities_to_vectorize, batch_items[0].tenant_id, session)
            vectors_stored = result.get("vectors_stored", 0)
            vectors_failed = result.get("vectors_failed", 0)

            logger.info(f"[QUEUE_PROCESSOR] STEP 4: ✅ Vectorization result: {vectors_stored} stored, {vectors_failed} failed")
            logger.info(f"[QUEUE_PROCESSOR] STEP 4: Full result: {result}")

            # Update status for successfully vectorized items
            logger.info(f"[QUEUE_PROCESSOR] STEP 5: Updating queue item statuses...")
            for i, entity in enumerate(entities_to_vectorize):
                queue_item = entity["queue_item"]
                if i < vectors_stored:
                    queue_item.status = 'completed'
                    queue_item.completed_at = datetime.utcnow()
                    queue_item.error_message = None  # Clear any previous errors
                    logger.info(f"[QUEUE_PROCESSOR] STEP 5: ✅ Marked item {queue_item.id} as completed")
                else:
                    error_details = result.get("error_details", result.get("error", "Unknown vectorization error"))
                    queue_item.status = 'failed'
                    queue_item.error_message = f"Vectorization failed: {error_details}"
                    queue_item.last_error_at = datetime.utcnow()
                    logger.error(f"[QUEUE_PROCESSOR] STEP 5: ❌ Marked item {queue_item.id} as failed: {error_details}")
        else:
            logger.warning(f"[QUEUE_PROCESSOR] STEP 4: ⚠️ No entities to vectorize (all failed internal ID lookup)")

        # Count final results
        logger.info(f"[QUEUE_PROCESSOR] STEP 6: Counting final results...")
        successful_items = sum(1 for item in batch_items if item.status == 'completed')
        failed_items = sum(1 for item in batch_items if item.status == 'failed')
        processing_items = sum(1 for item in batch_items if item.status == 'processing')

        logger.info(f"[QUEUE_PROCESSOR] STEP 6: Final status counts - Completed: {successful_items}, Failed: {failed_items}, Still Processing: {processing_items}")

        session.commit()
        logger.info(f"[QUEUE_PROCESSOR] STEP 6: ✅ Database changes committed")

        batch_result = {
            "vectors_stored": successful_items,
            "vectors_failed": failed_items,
            "total_processed": len(batch_items)
        }

        logger.info(f"[QUEUE_PROCESSOR] ===== BATCH PROCESSING COMPLETE =====")
        logger.info(f"[QUEUE_PROCESSOR] FINAL RESULT: {successful_items} successful, {failed_items} failed out of {len(batch_items)} total")
        return batch_result

    except Exception as e:
        # Mark batch as failed
        logger.error(f"[QUEUE_PROCESSOR] ===== BATCH PROCESSING EXCEPTION =====")
        logger.error(f"[QUEUE_PROCESSOR] Exception: {str(e)}")
        import traceback
        logger.error(f"[QUEUE_PROCESSOR] Full traceback: {traceback.format_exc()}")

        logger.info(f"[QUEUE_PROCESSOR] Marking all {len(batch_items)} items as failed due to exception...")
        from datetime import datetime
        for item in batch_items:
            item.status = 'failed'
            item.error_message = f"Batch processing exception: {str(e)}"
            item.last_error_at = datetime.utcnow()
        session.commit()

        logger.error(f"[QUEUE_PROCESSOR] ❌ Batch processing failed with exception: {e}")
        return {
            "vectors_stored": 0,
            "vectors_failed": len(batch_items),
            "total_processed": len(batch_items),
            "error": str(e)
        }


# Vectorization Statistics Endpoints

@router.get("/vectorization/queue-stats")
async def get_vectorization_queue_stats(
    user: UserData = Depends(require_authentication)
):
    """Get vectorization queue statistics for the current tenant"""
    try:
        from app.models.unified_models import VectorizationQueue

        tenant_id = user.tenant_id

        session = next(get_db_session())
        try:
            # Count items by status
            pending_count = session.query(VectorizationQueue).filter(
                VectorizationQueue.tenant_id == tenant_id,
                VectorizationQueue.status == 'pending'
            ).count()

            processing_count = session.query(VectorizationQueue).filter(
                VectorizationQueue.tenant_id == tenant_id,
                VectorizationQueue.status == 'processing'
            ).count()

            completed_count = session.query(VectorizationQueue).filter(
                VectorizationQueue.tenant_id == tenant_id,
                VectorizationQueue.status == 'completed'
            ).count()

            failed_count = session.query(VectorizationQueue).filter(
                VectorizationQueue.tenant_id == tenant_id,
                VectorizationQueue.status == 'failed'
            ).count()

            total_count = pending_count + processing_count + completed_count + failed_count

            # Get last updated timestamp (use completed_at as the most recent activity)
            last_updated = session.query(func.max(VectorizationQueue.completed_at)).filter(
                VectorizationQueue.tenant_id == tenant_id
            ).scalar()

            # Calculate processing stats if we have data
            processing_stats = None
            if completed_count > 0:
                # Calculate success rate
                success_rate = f"{(completed_count / (completed_count + failed_count) * 100):.1f}%" if (completed_count + failed_count) > 0 else "N/A"

                # Get recent processing info
                recent_completed = session.query(VectorizationQueue).filter(
                    VectorizationQueue.tenant_id == tenant_id,
                    VectorizationQueue.status == 'completed'
                ).order_by(VectorizationQueue.completed_at.desc()).limit(10).all()

                if recent_completed:
                    # Calculate average processing time (if we have created_at and completed_at)
                    processing_times = []
                    for item in recent_completed:
                        if item.created_at and item.completed_at:
                            processing_time = (item.completed_at - item.created_at).total_seconds()
                            processing_times.append(processing_time)

                    avg_processing_time = f"{sum(processing_times) / len(processing_times):.1f}s" if processing_times else "N/A"
                    last_run = recent_completed[0].completed_at.isoformat() if recent_completed[0].completed_at else None
                else:
                    avg_processing_time = "N/A"
                    last_run = None

                processing_stats = {
                    "success_rate": success_rate,
                    "avg_processing_time": avg_processing_time,
                    "last_batch_size": min(10, completed_count),  # Assuming batch size of 10
                    "last_run": last_run
                }

            return {
                "pending": pending_count,
                "processing": processing_count,
                "completed": completed_count,
                "failed": failed_count,
                "total": total_count,
                "last_updated": last_updated.isoformat() if last_updated else None,
                "processing_stats": processing_stats
            }
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error fetching vectorization queue stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch queue statistics")


@router.get("/vectorization/vector-stats")
async def get_vector_database_stats(
    user: UserData = Depends(require_authentication)
):
    """Get vector database (Qdrant) statistics for the current tenant"""
    try:
        from app.core.ai_providers import get_hybrid_provider_manager

        tenant_id = user.tenant_id

        # Get Qdrant client through the hybrid provider manager
        with get_db_session() as session:
            hybrid_manager = get_hybrid_provider_manager(session)
            qdrant_client = hybrid_manager.get_qdrant_client()

            if not qdrant_client:
                return {
                    "collections": [],
                    "total_vectors": 0,
                    "error": "Qdrant client not available"
                }

            try:
                # Get collection info for this tenant
                collections_info = []
                total_vectors = 0

                # List all collections and filter by tenant
                collections = qdrant_client.get_collections()

                for collection in collections.collections:
                    collection_name = collection.name

                    # Check if this collection belongs to our tenant
                    # Collections are typically named like "tenant_{tenant_id}_{table_name}"
                    if collection_name.startswith(f"tenant_{tenant_id}_"):
                        try:
                            # Get collection info
                            collection_info = qdrant_client.get_collection(collection_name)
                            vectors_count = collection_info.vectors_count or 0
                            total_vectors += vectors_count

                            # Extract table name from collection name
                            table_name = collection_name.replace(f"tenant_{tenant_id}_", "")

                            collections_info.append({
                                "name": table_name,
                                "full_name": collection_name,
                                "vectors_count": vectors_count,
                                "status": collection_info.status.name if hasattr(collection_info, 'status') else "Unknown",
                                "disk_usage": f"{collection_info.disk_usage / (1024*1024):.1f} MB" if hasattr(collection_info, 'disk_usage') and collection_info.disk_usage else "Unknown"
                            })
                        except Exception as e:
                            logger.warning(f"Could not get info for collection {collection_name}: {e}")
                            collections_info.append({
                                "name": collection_name.replace(f"tenant_{tenant_id}_", ""),
                                "full_name": collection_name,
                                "vectors_count": 0,
                                "status": "Error",
                                "disk_usage": "Unknown"
                            })

                return {
                    "collections": collections_info,
                    "total_vectors": total_vectors,
                    "tenant_id": tenant_id
                }

            except Exception as e:
                logger.error(f"Error accessing Qdrant collections: {e}")
                return {
                    "collections": [],
                    "total_vectors": 0,
                    "error": f"Failed to access vector database: {str(e)}"
                }

    except Exception as e:
        logger.error(f"Error fetching vector database stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch vector database statistics")


async def send_vectorization_progress(tenant_id: int, percentage: float, message: str, job_name: str = None, items_processed: int = 0, items_failed: int = 0, total_items: int = 0):
    """
    Send vectorization progress update to ETL service via HTTP webhook.
    This pushes real-time updates instead of requiring polling.
    """
    try:
        import httpx
        from datetime import datetime

        # Always use "Vectorization" as job name for vectorization progress
        if not job_name:
            job_name = "Vectorization"

        # Prepare detailed progress payload
        progress_payload = {
            "job_name": job_name,
            "tenant_id": tenant_id,
            "percentage": percentage,
            "message": message,
            "items_processed": items_processed,
            "items_failed": items_failed,
            "total_items": total_items,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "completed" if percentage >= 100 else "in_progress"
        }

        logger.info(f"[WEBHOOK] Sending progress update to ETL: {job_name} - {percentage}% - {message}")

        # Send progress update to ETL service webhook endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/api/v1/webhooks/vectorization-progress",
                json=progress_payload,
                timeout=5.0  # Reasonable timeout for webhook
            )

            if response.status_code == 200:
                logger.debug(f"[WEBHOOK] ✅ Successfully sent progress update to ETL")
            else:
                logger.warning(f"[WEBHOOK] ⚠️ ETL webhook returned status {response.status_code}: {response.text}")

    except Exception as e:
        logger.warning(f"[WEBHOOK] ❌ Failed to send progress update to ETL: {e}")
        # Non-critical - don't fail vectorization if websocket fails


# Removed _detect_current_job_name function - vectorization progress should always
# be sent to "Vectorization" channel regardless of originating job


async def bulk_vectorize_entities_from_queue(entities: List[Dict[str, Any]], tenant_id: int, db_session) -> Dict[str, Any]:
    """
    DEPRECATED: Vectorize entities from the queue using existing infrastructure with AI Gateway batching

    This function is deprecated. The new ETL architecture uses RabbitMQ-based
    vectorization queues managed by VectorizationWorker instead of database tables.
    """
    logger.warning("DEPRECATED: bulk_vectorize_entities_from_queue called - use RabbitMQ-based vectorization instead")
    try:
        logger.info(f"[BULK_VECTORIZE] ===== STARTING BULK VECTORIZATION =====")
        logger.info(f"[BULK_VECTORIZE] Processing {len(entities)} entities for tenant {tenant_id}")

        # Use the existing bulk vectorization logic
        logger.info(f"[BULK_VECTORIZE] STEP 1: Initializing provider manager...")
        provider_manager = HybridProviderManager(db_session)
        await provider_manager.initialize_providers(tenant_id)
        logger.info(f"[BULK_VECTORIZE] STEP 1: ✅ Provider manager initialized")

        logger.info(f"[BULK_VECTORIZE] STEP 2: Initializing Qdrant client...")
        qdrant_client = PulseQdrantClient()
        await qdrant_client.initialize()
        logger.info(f"[BULK_VECTORIZE] STEP 2: ✅ Qdrant client initialized")

        vectors_stored = 0
        vectors_failed = 0

        # OPTIMIZATION: Batch AI Gateway calls instead of individual calls
        # Prepare all text content first
        logger.info(f"[BULK_VECTORIZE] STEP 3: Preparing text content for {len(entities)} entities...")
        entity_texts = []
        entity_metadata = []

        for i, entity in enumerate(entities):
            logger.debug(f"[BULK_VECTORIZE] STEP 3: Processing entity {i+1}/{len(entities)}: table={entity.get('table_name')}, record_id={entity.get('record_id')}")
            try:
                # Get entity data and metadata
                entity_data = entity["entity_data"]
                record_id = entity["record_id"]
                table_name = entity["table_name"]

                logger.debug(f"[BULK_VECTORIZE] STEP 3.{i+1}: Entity data keys: {list(entity_data.keys()) if isinstance(entity_data, dict) else 'Not a dict'}")

                # Create text content for vectorization
                logger.debug(f"[BULK_VECTORIZE] STEP 3.{i+1}: Creating text content for table '{table_name}'...")
                text_content = create_text_content_from_entity(entity_data, table_name)
                logger.debug(f"[BULK_VECTORIZE] STEP 3.{i+1}: Text content length: {len(text_content) if text_content else 0}")

                if text_content:
                    entity_texts.append(text_content)
                    entity_metadata.append({
                        "entity_data": entity_data,
                        "record_id": record_id,
                        "table_name": table_name,
                        "entity": entity
                    })
                    logger.debug(f"[BULK_VECTORIZE] STEP 3.{i+1}: ✅ Text content prepared successfully")
                else:
                    logger.warning(f"[BULK_VECTORIZE] STEP 3.{i+1}: ❌ No text content generated for {table_name} record {record_id}")
                    vectors_failed += 1

            except Exception as e:
                logger.error(f"[BULK_VECTORIZE] STEP 3.{i+1}: ❌ Error preparing entity {entity.get('record_id', 'unknown')}: {e}")
                import traceback
                logger.error(f"[BULK_VECTORIZE] STEP 3.{i+1}: Full traceback: {traceback.format_exc()}")
                # Update queue item with detailed error
                queue_item = entity.get('queue_item')
                if queue_item:
                    queue_item.status = 'failed'
                    queue_item.error_message = f"Entity preparation failed: {str(e)}"
                    queue_item.last_error_at = datetime.utcnow()
                vectors_failed += 1

        # Generate embeddings for ALL texts in one batch call
        logger.info(f"[BULK_VECTORIZE] STEP 3: ✅ Prepared {len(entity_texts)} text contents, {vectors_failed} failed")

        if entity_texts:
            logger.info(f"[BULK_VECTORIZE] STEP 4: Generating embeddings for {len(entity_texts)} entities in batch...")
            logger.debug(f"[BULK_VECTORIZE] STEP 4: Text lengths: {[len(text) for text in entity_texts[:5]]}...")  # Show first 5

            embedding_result = await provider_manager.generate_embeddings(entity_texts, tenant_id)
            logger.info(f"[BULK_VECTORIZE] STEP 4: Embedding generation completed. Success: {embedding_result.success}")

            if not embedding_result.success:
                error_msg = f"Batch embedding generation failed: {embedding_result.error}"
                logger.error(f"[BULK_VECTORIZE] STEP 4: ❌ {error_msg}")
                logger.error(f"[BULK_VECTORIZE] STEP 4: Full embedding result: {embedding_result}")

                # Update all queue items with detailed error
                logger.info(f"[BULK_VECTORIZE] STEP 4: Marking {len(entity_metadata)} items as failed due to embedding error...")
                for i, metadata in enumerate(entity_metadata):
                    queue_item = metadata.get('entity', {}).get('queue_item')
                    if queue_item:
                        queue_item.status = 'failed'
                        queue_item.error_message = error_msg
                        queue_item.last_error_at = datetime.utcnow()
                        logger.debug(f"[BULK_VECTORIZE] STEP 4: Marked item {queue_item.id} as failed")

                vectors_failed += len(entity_texts)
                logger.error(f"[BULK_VECTORIZE] ❌ Returning early due to embedding failure: {vectors_stored} stored, {vectors_failed} failed")
                return {
                    "vectors_stored": vectors_stored,
                    "vectors_failed": vectors_failed,
                    "error": error_msg
                }
        else:
            logger.warning(f"[BULK_VECTORIZE] STEP 4: ⚠️ No entity texts to process - all entities failed text preparation")
            return {
                "vectors_stored": vectors_stored,
                "vectors_failed": vectors_failed,
                "error": "No entity texts to process"
            }

        # Process each embedding result
        logger.info(f"[BULK_VECTORIZE] STEP 5: Processing embedding results...")
        embeddings = embedding_result.data
        logger.info(f"[BULK_VECTORIZE] STEP 5: Got {len(embeddings)} embeddings, expected {len(entity_metadata)}")

        if len(embeddings) != len(entity_metadata):
            error_msg = f"Embedding count mismatch: got {len(embeddings)}, expected {len(entity_metadata)}"
            logger.error(f"[BULK_VECTORIZE] STEP 5: ❌ {error_msg}")
            vectors_failed += len(entity_texts)
            return {
                "vectors_stored": vectors_stored,
                "vectors_failed": vectors_failed,
                "error": error_msg
            }

        # Store each embedding in Qdrant
        logger.info(f"[BULK_VECTORIZE] STEP 6: Storing {len(embeddings)} vectors in Qdrant...")
        for i, (embedding_vector, metadata) in enumerate(zip(embeddings, entity_metadata)):
            logger.debug(f"[BULK_VECTORIZE] STEP 6.{i+1}: Processing vector {i+1}/{len(embeddings)}")
            try:
                if not embedding_vector:
                    error_msg = f"No embedding data returned for {metadata['table_name']} {metadata['record_id']}"
                    logger.warning(f"[BULK_VECTORIZE] STEP 6.{i+1}: ⚠️ {error_msg}")
                    vectors_failed += 1
                    continue

                # Store in Qdrant
                entity_data = metadata["entity_data"]
                record_id = metadata["record_id"]
                table_name = metadata["table_name"]

                logger.debug(f"[BULK_VECTORIZE] STEP 6.{i+1}: Storing vector for {table_name} record {record_id}")

                collection_name = f"client_{tenant_id}_{table_name}"
                # Create deterministic UUID for point ID (consistent with individual vectorization)
                import uuid
                unique_string = f"{tenant_id}_{table_name}_{record_id}"
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))
                logger.debug(f"[BULK_VECTORIZE] STEP 6.{i+1}: Collection: {collection_name}, Point ID: {point_id}")

                # Ensure collection exists before upserting
                await qdrant_client.ensure_collection_exists(
                    collection_name=collection_name,
                    vector_size=len(embedding_vector)
                )

                # Prepare vector data for upsert
                vector_data = [{
                    'id': point_id,  # Now using UUID string instead of integer
                    'vector': embedding_vector,
                    'payload': {
                        **entity_data,
                        'tenant_id': tenant_id,
                        'table_name': table_name,
                        'record_id': record_id
                    }
                }]

                store_result = await qdrant_client.upsert_vectors(
                    collection_name=collection_name,
                    vectors=vector_data
                )

                if store_result.success:
                    # Check if bridge record already exists (upsert logic)
                    existing_record = db_session.query(QdrantVector).filter(
                        QdrantVector.tenant_id == tenant_id,
                        QdrantVector.table_name == table_name,
                        QdrantVector.record_id == record_id,
                        QdrantVector.vector_type == "entity_embedding"
                    ).first()

                    if existing_record:
                        # Update existing record
                        existing_record.qdrant_collection = collection_name
                        existing_record.qdrant_point_id = point_id
                        existing_record.embedding_model = embedding_result.provider_used
                        existing_record.embedding_provider = embedding_result.provider_used
                        existing_record.last_updated_at = datetime.utcnow()
                        logger.debug(f"[QUEUE_PROCESSOR] Updated existing bridge record for {table_name} {record_id}")
                    else:
                        # Create new bridge record
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
                        logger.debug(f"[QUEUE_PROCESSOR] Created new bridge record for {table_name} {record_id}")

                    vectors_stored += 1
                else:
                    vectors_failed += 1
                    logger.warning(f"[QUEUE_PROCESSOR] Failed to store vector for {table_name} {record_id}: {store_result.error}")

            except Exception as e:
                logger.error(f"[BULK_VECTORIZE] STEP 6.{i+1}: ❌ Error storing vector for entity {metadata.get('record_id', 'unknown')}: {e}")
                # Update queue item with detailed error
                queue_item = metadata.get('entity', {}).get('queue_item')
                if queue_item:
                    queue_item.status = 'failed'
                    queue_item.error_message = f"Vector storage failed: {str(e)}"
                    queue_item.last_error_at = datetime.utcnow()
                vectors_failed += 1

        # Commit all bridge records for this batch
        logger.info(f"[BULK_VECTORIZE] STEP 7: Finalizing results...")
        if vectors_stored > 0:
            logger.info(f"[BULK_VECTORIZE] STEP 7: Committing {vectors_stored} bridge records to database...")
            db_session.commit()
            logger.info(f"[BULK_VECTORIZE] STEP 7: ✅ Committed {vectors_stored} bridge records to qdrant_vectors table")
        else:
            logger.warning(f"[BULK_VECTORIZE] STEP 7: ⚠️ No vectors stored - nothing to commit")

        final_result = {
            "vectors_stored": vectors_stored,
            "vectors_failed": vectors_failed
        }

        logger.info(f"[BULK_VECTORIZE] ===== BULK VECTORIZATION COMPLETE =====")
        logger.info(f"[BULK_VECTORIZE] FINAL RESULT: {vectors_stored} stored, {vectors_failed} failed out of {len(entities)} total")
        logger.info(f"[BULK_VECTORIZE] Returning result: {final_result}")

        return final_result

    except Exception as e:
        logger.error(f"[BULK_VECTORIZE] ===== BULK VECTORIZATION EXCEPTION =====")
        logger.error(f"[BULK_VECTORIZE] Exception: {str(e)}")
        import traceback
        logger.error(f"[BULK_VECTORIZE] Full traceback: {traceback.format_exc()}")

        error_result = {
            "vectors_stored": 0,
            "vectors_failed": len(entities),
            "error": str(e)
        }

        logger.error(f"[BULK_VECTORIZE] ❌ Returning error result: {error_result}")
        return error_result


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


async def cleanup_old_completed_records(session, tenant_id: int, retention_hours: int = 24):
    """
    Clean up old COMPLETED vectorization records to prevent exponential data growth.

    IMPORTANT: This function ONLY deletes successfully completed records.
    Failed records are preserved for debugging and potential retry.
    Use the separate cleanup-failed-queue endpoint to manually clean failed records.
    """
    try:
        from datetime import datetime, timedelta
        from app.models.unified_models import VectorizationQueue

        # Calculate cutoff time (keep records for retention_hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=retention_hours)

        # Delete ONLY old completed records (successful vectorizations)
        deleted_count = session.query(VectorizationQueue).filter(
            VectorizationQueue.tenant_id == tenant_id,
            VectorizationQueue.status == 'completed',
            VectorizationQueue.completed_at < cutoff_time
        ).delete()

        # DO NOT delete failed records - keep them for debugging and potential retry
        # Failed records should be manually reviewed and cleaned up by administrators

        session.commit()

        if deleted_count > 0:
            logger.info(f"[CLEANUP] Tenant {tenant_id}: Deleted {deleted_count} old completed records (keeping all failed records for debugging)")

    except Exception as e:
        logger.error(f"[CLEANUP] Error cleaning up old records for tenant {tenant_id}: {e}")
        session.rollback()


async def cleanup_completed_records_immediately(session, tenant_id: int):
    """
    Clean up ALL completed vectorization records immediately after processing.
    This is called after successful vectorization to keep the queue clean.

    Args:
        session: Database session
        tenant_id: Tenant ID for cleanup

    Returns:
        Dict with cleanup results
    """
    try:
        from app.models.unified_models import VectorizationQueue

        # Count completed items before deletion
        completed_count = session.query(VectorizationQueue).filter(
            VectorizationQueue.tenant_id == tenant_id,
            VectorizationQueue.status == 'completed'
        ).count()

        if completed_count == 0:
            logger.debug(f"[CLEANUP] No completed items to clean up for tenant {tenant_id}")
            return {
                'success': True,
                'deleted_count': 0,
                'message': 'No completed items to clean up'
            }

        # Delete ALL completed items (they've been successfully vectorized)
        deleted_count = session.query(VectorizationQueue).filter(
            VectorizationQueue.tenant_id == tenant_id,
            VectorizationQueue.status == 'completed'
        ).delete(synchronize_session=False)

        session.commit()

        logger.info(f"[CLEANUP] Immediately cleaned up {deleted_count} completed vectorization items for tenant {tenant_id}")

        return {
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Successfully cleaned up {deleted_count} completed items'
        }

    except Exception as e:
        logger.error(f"[CLEANUP] Error in immediate cleanup: {e}")
        session.rollback()
        return {
            'success': False,
            'deleted_count': 0,
            'error': f"Cleanup failed: {str(e)}"
        }
