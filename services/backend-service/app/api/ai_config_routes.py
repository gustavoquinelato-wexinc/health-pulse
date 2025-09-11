"""
AI Configuration Routes for ETL Service

Provides web interface routes for AI configuration including:
- AI Provider management
- Performance monitoring
- Configuration validation
- Model selection and setup
"""

from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
from pathlib import Path
from datetime import datetime
from sqlalchemy import func, case, text

from app.core.logging_config import get_logger
from app.core.database import get_database, get_db_session
from app.models.unified_models import Integration, AIUsageTracking
from app.auth.auth_middleware import require_authentication, require_admin, UserData
from app.core.config import settings

logger = get_logger(__name__)

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
