"""
AI Client for ETL Service
Simple client to call Backend Service AI endpoints
"""

import asyncio
import httpx
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import os

from app.core.config import settings

logger = logging.getLogger(__name__)

@dataclass
class EmbeddingResult:
    """Result from embedding generation"""
    success: bool
    embeddings: List[List[float]]
    provider_used: str
    processing_time: float
    cost: float
    error: Optional[str] = None

@dataclass
class VectorStoreResult:
    """Result from vector storage operation"""
    success: bool
    point_id: str
    collection_name: str
    provider_used: str
    processing_time: float
    cost: float
    error: Optional[str] = None

@dataclass
class VectorSearchResult:
    """Result from vector search operation"""
    success: bool
    results: List[Dict[str, Any]]
    total_found: int
    collections_searched: List[str]
    provider_used: str
    processing_time: float
    cost: float
    error: Optional[str] = None

class AIClient:
    """Client for calling Backend Service AI endpoints"""
    
    def __init__(self):
        # Use environment variable for Backend Service URL
        self.backend_url = getattr(settings, 'BACKEND_SERVICE_URL', 'http://localhost:3001')
        self.timeout = 30.0
        
    async def generate_embeddings(self, texts: List[str], auth_token: str = None) -> EmbeddingResult:
        """Generate embeddings using Backend Service AI"""
        try:
            headers = {
                "Content-Type": "application/json"
            }
            
            # Add authentication if token provided
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
            
            payload = {
                "texts": texts
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.backend_url}/api/v1/ai/embeddings",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("success"):
                        return EmbeddingResult(
                            success=True,
                            embeddings=data.get("embeddings", []),
                            provider_used=data.get("provider_used", "unknown"),
                            processing_time=data.get("processing_time", 0.0),
                            cost=data.get("cost", 0.0)
                        )
                    else:
                        return EmbeddingResult(
                            success=False,
                            embeddings=[],
                            provider_used="unknown",
                            processing_time=0.0,
                            cost=0.0,
                            error=data.get("error", "Unknown error")
                        )
                else:
                    logger.error(f"AI Service returned status {response.status_code}: {response.text}")
                    return EmbeddingResult(
                        success=False,
                        embeddings=[],
                        provider_used="unknown",
                        processing_time=0.0,
                        cost=0.0,
                        error=f"HTTP {response.status_code}: {response.text}"
                    )
                    
        except httpx.TimeoutException:
            logger.error("Timeout calling AI Service for embeddings")
            return EmbeddingResult(
                success=False,
                embeddings=[],
                provider_used="unknown",
                processing_time=0.0,
                cost=0.0,
                error="Timeout calling AI Service"
            )
        except Exception as e:
            logger.error(f"Error calling AI Service for embeddings: {e}")
            return EmbeddingResult(
                success=False,
                embeddings=[],
                provider_used="unknown",
                processing_time=0.0,
                cost=0.0,
                error=str(e)
            )
    
    async def store_entity_vector(
        self,
        entity_data: Dict[str, Any],
        table_name: str,
        record_id: str,
        auth_token: str = None
    ) -> VectorStoreResult:
        """Store entity vector in Qdrant via Backend Service"""
        try:
            # Check if auth token is available
            if not auth_token:
                logger.warning(f"[AI_VECTORS] ⚠️ No authentication token available - skipping AI vectorization for {table_name}:{record_id}")
                return VectorStoreResult(
                    success=True,
                    vector_id=None,
                    collection_name=None,
                    processing_time=0.0,
                    cost=0.0,
                    provider_used="none",
                    error="No authentication token - AI vectorization skipped"
                )

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_token}"
            }

            payload = {
                "entity_data": entity_data,
                "table_name": table_name,
                "record_id": record_id
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.backend_url}/api/v1/ai/vectors/store",
                    json=payload,
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get("success"):
                        return VectorStoreResult(
                            success=True,
                            point_id=data.get("point_id", ""),
                            collection_name=data.get("collection_name", ""),
                            provider_used=data.get("provider_used", "unknown"),
                            processing_time=data.get("processing_time", 0.0),
                            cost=data.get("cost", 0.0)
                        )
                    else:
                        return VectorStoreResult(
                            success=False,
                            point_id="",
                            collection_name="",
                            provider_used="unknown",
                            processing_time=0.0,
                            cost=0.0,
                            error=data.get("error", "Unknown error")
                        )
                else:
                    logger.error(f"Vector store returned status {response.status_code}: {response.text}")
                    return VectorStoreResult(
                        success=False,
                        point_id="",
                        collection_name="",
                        provider_used="unknown",
                        processing_time=0.0,
                        cost=0.0,
                        error=f"HTTP {response.status_code}: {response.text}"
                    )

        except httpx.TimeoutException:
            logger.error("Timeout calling Backend Service for vector storage")
            return VectorStoreResult(
                success=False,
                point_id="",
                collection_name="",
                provider_used="unknown",
                processing_time=0.0,
                cost=0.0,
                error="Timeout calling Backend Service"
            )
        except Exception as e:
            logger.error(f"Error calling Backend Service for vector storage: {e}")
            return VectorStoreResult(
                success=False,
                point_id="",
                collection_name="",
                provider_used="unknown",
                processing_time=0.0,
                cost=0.0,
                error=str(e)
            )

    async def search_similar_entities(
        self,
        query_text: str,
        table_name: str = None,
        similarity_threshold: float = 0.7,
        limit: int = 10,
        auth_token: str = None
    ) -> VectorSearchResult:
        """Search for similar entities using vector similarity"""
        try:
            headers = {
                "Content-Type": "application/json"
            }

            # Add authentication if token provided
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

            payload = {
                "query_text": query_text,
                "similarity_threshold": similarity_threshold,
                "limit": limit
            }

            if table_name:
                payload["table_name"] = table_name

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.backend_url}/api/v1/ai/vectors/search",
                    json=payload,
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get("success"):
                        return VectorSearchResult(
                            success=True,
                            results=data.get("results", []),
                            total_found=data.get("total_found", 0),
                            collections_searched=data.get("collections_searched", []),
                            provider_used=data.get("provider_used", "unknown"),
                            processing_time=data.get("processing_time", 0.0),
                            cost=data.get("cost", 0.0)
                        )
                    else:
                        return VectorSearchResult(
                            success=False,
                            results=[],
                            total_found=0,
                            collections_searched=[],
                            provider_used="unknown",
                            processing_time=0.0,
                            cost=0.0,
                            error=data.get("error", "Unknown error")
                        )
                else:
                    logger.error(f"Vector search returned status {response.status_code}: {response.text}")
                    return VectorSearchResult(
                        success=False,
                        results=[],
                        total_found=0,
                        collections_searched=[],
                        provider_used="unknown",
                        processing_time=0.0,
                        cost=0.0,
                        error=f"HTTP {response.status_code}: {response.text}"
                    )

        except httpx.TimeoutException:
            logger.error("Timeout calling Backend Service for vector search")
            return VectorSearchResult(
                success=False,
                results=[],
                total_found=0,
                collections_searched=[],
                provider_used="unknown",
                processing_time=0.0,
                cost=0.0,
                error="Timeout calling Backend Service"
            )
        except Exception as e:
            logger.error(f"Error calling Backend Service for vector search: {e}")
            return VectorSearchResult(
                success=False,
                results=[],
                total_found=0,
                collections_searched=[],
                provider_used="unknown",
                processing_time=0.0,
                cost=0.0,
                error=str(e)
            )

    async def test_connection(self) -> bool:
        """Test connection to Backend Service"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.backend_url}/api/v1/health")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to connect to Backend Service: {e}")
            return False

# Global AI client instance
_ai_client = None

def get_ai_client() -> AIClient:
    """Get global AI client instance"""
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client

# Convenience functions for ETL jobs
async def generate_embeddings_for_etl(texts: List[str]) -> EmbeddingResult:
    """
    Convenience function for ETL jobs to generate embeddings
    Uses system authentication (no user token required)
    """
    client = get_ai_client()

    # For ETL operations, we might need to use a service account token
    # For now, we'll try without authentication and handle errors gracefully
    try:
        result = await client.generate_embeddings(texts)

        if result.success:
            logger.info(f"Generated {len(result.embeddings)} embeddings using {result.provider_used} "
                       f"in {result.processing_time:.2f}s (cost: ${result.cost:.4f})")
        else:
            logger.error(f"Failed to generate embeddings: {result.error}")

        return result

    except Exception as e:
        logger.error(f"Error in ETL embedding generation: {e}")
        return EmbeddingResult(
            success=False,
            embeddings=[],
            provider_used="unknown",
            processing_time=0.0,
            cost=0.0,
            error=str(e)
        )

async def store_entity_vector_for_etl(
    entity_data: Dict[str, Any],
    table_name: str,
    record_id: str,
    auth_token: str = None
) -> VectorStoreResult:
    """
    Convenience function for ETL jobs to store entity vectors
    Requires auth token for backend service authentication
    """
    client = get_ai_client()

    try:
        result = await client.store_entity_vector(entity_data, table_name, record_id, auth_token=auth_token)

        if result.success:
            logger.info(f"Stored vector for {table_name}:{record_id} in {result.collection_name} "
                       f"using {result.provider_used} in {result.processing_time:.2f}s (cost: ${result.cost:.4f})")
        else:
            logger.warning(f"Failed to store vector for {table_name}:{record_id}: {result.error}")

        return result

    except Exception as e:
        logger.error(f"Error in ETL vector storage: {e}")
        return VectorStoreResult(
            success=False,
            point_id="",
            collection_name="",
            provider_used="unknown",
            processing_time=0.0,
            cost=0.0,
            error=str(e)
        )

async def search_similar_entities_for_etl(
    query_text: str,
    table_name: str = None,
    similarity_threshold: float = 0.7,
    limit: int = 10
) -> VectorSearchResult:
    """
    Convenience function for ETL jobs to search similar entities
    Uses system authentication (no user token required)
    """
    client = get_ai_client()

    try:
        result = await client.search_similar_entities(
            query_text, table_name, similarity_threshold, limit
        )

        if result.success:
            logger.info(f"Found {result.total_found} similar entities for query '{query_text[:50]}...' "
                       f"using {result.provider_used} in {result.processing_time:.2f}s (cost: ${result.cost:.4f})")
        else:
            logger.warning(f"Failed to search similar entities: {result.error}")

        return result

    except Exception as e:
        logger.error(f"Error in ETL vector search: {e}")
        return VectorSearchResult(
            success=False,
            results=[],
            total_found=0,
            collections_searched=[],
            provider_used="unknown",
            processing_time=0.0,
            cost=0.0,
            error=str(e)
        )


@dataclass
class BulkVectorResult:
    """Result from bulk vector operations"""
    success: bool
    vectors_stored: int = 0
    vectors_updated: int = 0
    vectors_failed: int = 0
    error: Optional[str] = None
    processing_time: float = 0.0
    provider_used: Optional[str] = None


async def bulk_store_entity_vectors_for_etl(
    entities: List[Dict[str, Any]],
    auth_token: str = None
) -> BulkVectorResult:
    """
    Bulk store entity vectors via Backend Service.

    Args:
        entities: List of entity data dicts with keys:
                 - entity_data: Dict with entity content
                 - record_id: Unique record identifier
                 - table_name: Database table name
        auth_token: User authentication token for Backend Service

    Returns:
        BulkVectorResult with operation results
    """
    try:
        if not entities:
            return BulkVectorResult(success=True, vectors_stored=0)

        # Check if auth token is available
        if not auth_token:
            logger.warning("[AI_VECTORS] No authentication token available - skipping AI vectorization")
            return BulkVectorResult(
                success=True,
                vectors_stored=0,
                vectors_failed=0,
                processing_time=0.0,
                provider_used="none",
                error="No authentication token - AI vectorization skipped"
            )

        import time
        start_time = time.time()

        # Prepare bulk request payload
        payload = {
            "entities": entities,
            "operation": "bulk_store"
        }

        # Get Backend Service URL from environment
        import os
        backend_url = os.getenv("BACKEND_SERVICE_URL", "http://localhost:3001")

        # Prepare headers with authentication
        headers = {"Content-Type": "application/json"}
        headers["Authorization"] = f"Bearer {auth_token}"

        # Call Backend Service bulk endpoint
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{backend_url}/api/v1/ai/vectors/bulk",
                json=payload,
                headers=headers
            )

            processing_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return BulkVectorResult(
                        success=True,
                        vectors_stored=data.get("vectors_stored", 0),
                        vectors_failed=data.get("vectors_failed", 0),
                        processing_time=processing_time,
                        provider_used=data.get("provider_used")
                    )
                else:
                    return BulkVectorResult(
                        success=False,
                        error=data.get("error", "Unknown error"),
                        processing_time=processing_time
                    )
            else:
                return BulkVectorResult(
                    success=False,
                    error=f"Backend Service returned {response.status_code}: {response.text}",
                    processing_time=processing_time
                )

    except Exception as e:
        return BulkVectorResult(
            success=False,
            error=f"Error calling Backend Service: {str(e)}"
        )


async def bulk_update_entity_vectors_for_etl(
    entities: List[Dict[str, Any]],
    auth_token: str = None
) -> BulkVectorResult:
    """
    Bulk update entity vectors via Backend Service.

    Args:
        entities: List of entity data dicts with keys:
                 - entity_data: Dict with entity content
                 - record_id: Unique record identifier
                 - table_name: Database table name
        auth_token: User authentication token for Backend Service

    Returns:
        BulkVectorResult with operation results
    """
    try:
        if not entities:
            return BulkVectorResult(success=True, vectors_updated=0)

        # Check if auth token is available
        if not auth_token:
            logger.warning("[AI_VECTORS] ⚠️ No authentication token available - skipping AI vectorization")
            return BulkVectorResult(
                success=True,
                vectors_updated=0,
                vectors_failed=0,
                processing_time=0.0,
                provider_used="none",
                error="No authentication token - AI vectorization skipped"
            )

        import time
        start_time = time.time()

        # Prepare bulk request payload
        payload = {
            "entities": entities,
            "operation": "bulk_update"
        }

        # Get Backend Service URL from environment
        import os
        backend_url = os.getenv("BACKEND_SERVICE_URL", "http://localhost:3001")

        # Prepare headers with authentication
        headers = {"Content-Type": "application/json"}
        headers["Authorization"] = f"Bearer {auth_token}"

        # Call Backend Service bulk endpoint
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{backend_url}/api/v1/ai/vectors/bulk",
                json=payload,
                headers=headers
            )

            processing_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return BulkVectorResult(
                        success=True,
                        vectors_updated=data.get("vectors_updated", 0),
                        vectors_failed=data.get("vectors_failed", 0),
                        processing_time=processing_time,
                        provider_used=data.get("provider_used")
                    )
                else:
                    return BulkVectorResult(
                        success=False,
                        error=data.get("error", "Unknown error"),
                        processing_time=processing_time
                    )
            else:
                return BulkVectorResult(
                    success=False,
                    error=f"Backend Service returned {response.status_code}: {response.text}",
                    processing_time=processing_time
                )

    except Exception as e:
        return BulkVectorResult(
            success=False,
            error=f"Error calling Backend Service: {str(e)}"
        )
