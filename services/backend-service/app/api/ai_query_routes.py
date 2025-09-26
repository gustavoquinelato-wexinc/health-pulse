"""
AI Query Routes - Phase 3-6 Natural Language Query Interface
Provides API endpoints for natural language queries and semantic search.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.core.logging_config import get_logger
from app.core.database import get_database, get_db_session
from app.auth.auth_middleware import require_authentication, UserData
from app.ai.query_processor import AIQueryProcessor, QueryResult

logger = get_logger(__name__)
router = APIRouter()

# Request/Response Models
class AIQueryRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None

class AISearchRequest(BaseModel):
    query: str
    collections: Optional[List[str]] = None
    limit: Optional[int] = 10

class AIQueryResponse(BaseModel):
    success: bool
    answer: str
    sources: List[Dict[str, Any]]
    processing_time: float
    query_type: str
    confidence: float
    metadata: Dict[str, Any]

class AISearchResponse(BaseModel):
    success: bool
    results: List[Dict[str, Any]]
    total_found: int
    collections_searched: List[str]
    error: Optional[str] = None

class AICapabilitiesResponse(BaseModel):
    success: bool
    capabilities: Dict[str, Any]
    collections: List[Dict[str, Any]]
    query_types: List[str]
    tenant_id: int

@router.post("/ai/query", response_model=AIQueryResponse)
async def process_natural_language_query(
    request: AIQueryRequest,
    user: UserData = Depends(require_authentication)
) -> AIQueryResponse:
    """Process natural language query"""
    try:
        if not request.query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query cannot be empty"
            )

        # Get database session
        database = get_database()
        
        with database.get_read_session_context() as db_session:
            # Initialize query processor
            query_processor = AIQueryProcessor(db_session)
            await query_processor.initialize(user.tenant_id)

            # Process query
            result = await query_processor.process_query(
                query=request.query,
                tenant_id=user.tenant_id,
                context=request.context
            )

            return AIQueryResponse(
                success=result.success,
                answer=result.answer,
                sources=result.sources,
                processing_time=result.processing_time,
                query_type=result.query_type,
                confidence=result.confidence,
                metadata=result.metadata
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )

@router.post("/ai/search", response_model=AISearchResponse)
async def semantic_search(
    request: AISearchRequest,
    user: UserData = Depends(require_authentication)
) -> AISearchResponse:
    """Perform semantic search across collections"""
    try:
        if not request.query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query cannot be empty"
            )

        if request.limit and (request.limit < 1 or request.limit > 100):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be between 1 and 100"
            )

        # Get database session
        database = get_database()
        
        with database.get_read_session_context() as db_session:
            # Initialize query processor
            query_processor = AIQueryProcessor(db_session)
            await query_processor.initialize(user.tenant_id)

            # Perform semantic search
            result = await query_processor.semantic_search(
                query=request.query,
                tenant_id=user.tenant_id,
                collections=request.collections,
                limit=request.limit or 10
            )

            return AISearchResponse(
                success=result["success"],
                results=result["results"],
                total_found=result.get("total_found", 0),
                collections_searched=result.get("collections_searched", []),
                error=result.get("error")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic search failed: {str(e)}"
        )

@router.get("/ai/capabilities", response_model=AICapabilitiesResponse)
async def get_ai_capabilities(
    user: UserData = Depends(require_authentication)
) -> AICapabilitiesResponse:
    """Get AI query capabilities for the current tenant"""
    try:
        # Get database session
        database = get_database()
        
        with database.get_read_session_context() as db_session:
            # Initialize query processor
            query_processor = AIQueryProcessor(db_session)
            await query_processor.initialize(user.tenant_id)

            # Get capabilities
            result = await query_processor.get_capabilities(user.tenant_id)

            if not result["success"]:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=result.get("error", "Failed to get capabilities")
                )

            return AICapabilitiesResponse(
                success=result["success"],
                capabilities=result["capabilities"],
                collections=result["collections"],
                query_types=result["query_types"],
                tenant_id=result["tenant_id"]
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get AI capabilities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get AI capabilities: {str(e)}"
        )

@router.get("/ai/health")
async def ai_health_check(
    user: UserData = Depends(require_authentication)
) -> Dict[str, Any]:
    """Health check for AI query system"""
    try:
        # Get database session
        database = get_database()
        
        with database.get_read_session_context() as db_session:
            # Initialize query processor
            query_processor = AIQueryProcessor(db_session)
            await query_processor.initialize(user.tenant_id)

            # Test basic functionality
            test_result = await query_processor.semantic_search(
                query="test",
                tenant_id=user.tenant_id,
                limit=1
            )

            return {
                "status": "healthy" if test_result["success"] else "degraded",
                "ai_providers": "available",
                "vector_database": "connected" if test_result["success"] else "error",
                "tenant_id": user.tenant_id,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        logger.error(f"AI health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "tenant_id": user.tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        }
