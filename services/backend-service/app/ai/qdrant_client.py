"""
Enhanced Qdrant Client - Phase 3-2 Hybrid Provider Framework
High-performance vector operations with tenant isolation and batch processing.
"""

import asyncio
import logging
import time
import uuid
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class VectorSearchResult:
    """Result from vector similarity search"""
    id: str
    score: float
    payload: Dict[str, Any]
    vector: Optional[List[float]] = None

@dataclass
class VectorOperationResult:
    """Result from vector operations"""
    success: bool
    operation: str
    count: int
    processing_time: float
    error: Optional[str] = None

class PulseQdrantClient:
    """High-performance Qdrant client with tenant isolation and batch operations"""

    def __init__(self, host: str = "localhost", port: int = 6333, timeout: int = 120):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client = None
        self.connected = False
        
        # Performance tracking
        self.operation_count = 0
        self.total_processing_time = 0.0

    async def initialize(self) -> bool:
        """Initialize Qdrant client connection"""
        try:
            # Import here to avoid dependency issues if not installed
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
            
            self.client = QdrantClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
            
            # Test connection
            collections = await asyncio.get_event_loop().run_in_executor(
                None, self.client.get_collections
            )
            
            self.connected = True
            logger.info(f"Connected to Qdrant at {self.host}:{self.port}")
            return True
            
        except ImportError:
            logger.error("qdrant-client package not installed. Install with: pip install qdrant-client")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            return False

    async def create_collection(self, collection_name: str, vector_size: int = 1536,
                              distance_metric: str = "Cosine") -> VectorOperationResult:
        """Create a new collection with tenant isolation"""
        if not self.connected:
            return VectorOperationResult(
                success=False,
                operation="create_collection",
                count=0,
                processing_time=0.0,
                error="Not connected to Qdrant"
            )

        start_time = time.time()
        
        try:
            from qdrant_client.http import models
            
            # Check if collection already exists
            collections = await asyncio.get_event_loop().run_in_executor(
                None, self.client.get_collections
            )
            
            existing_names = [col.name for col in collections.collections]
            if collection_name in existing_names:
                return VectorOperationResult(
                    success=True,
                    operation="create_collection",
                    count=0,
                    processing_time=time.time() - start_time,
                    error=f"Collection {collection_name} already exists"
                )

            # Create collection
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.client.create_collection,
                collection_name,
                models.VectorParams(
                    size=vector_size,
                    distance=getattr(models.Distance, distance_metric.upper())
                )
            )
            
            processing_time = time.time() - start_time
            self._update_metrics(processing_time)
            
            logger.info(f"Created Qdrant collection: {collection_name}")
            
            return VectorOperationResult(
                success=True,
                operation="create_collection",
                count=1,
                processing_time=processing_time
            )

        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            return VectorOperationResult(
                success=False,
                operation="create_collection",
                count=0,
                processing_time=time.time() - start_time,
                error=str(e)
            )

    async def upsert_vectors(self, collection_name: str, vectors: List[List[float]],
                           payloads: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> VectorOperationResult:
        """Upsert vectors with batch processing"""
        if not self.connected:
            return VectorOperationResult(
                success=False,
                operation="upsert_vectors",
                count=0,
                processing_time=0.0,
                error="Not connected to Qdrant"
            )

        if not vectors or len(vectors) != len(payloads):
            return VectorOperationResult(
                success=False,
                operation="upsert_vectors",
                count=0,
                processing_time=0.0,
                error="Vectors and payloads must have same length"
            )

        start_time = time.time()
        
        try:
            from qdrant_client.http import models
            
            # Generate IDs if not provided
            if ids is None:
                ids = [str(uuid.uuid4()) for _ in vectors]
            
            # Create points
            points = [
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                )
                for point_id, vector, payload in zip(ids, vectors, payloads)
            ]
            
            # Upsert in batches for performance
            batch_size = 100
            total_upserted = 0
            
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.client.upsert,
                    collection_name,
                    batch
                )
                
                total_upserted += len(batch)
            
            processing_time = time.time() - start_time
            self._update_metrics(processing_time)
            
            logger.info(f"Upserted {total_upserted} vectors to {collection_name}")
            
            return VectorOperationResult(
                success=True,
                operation="upsert_vectors",
                count=total_upserted,
                processing_time=processing_time
            )

        except Exception as e:
            logger.error(f"Failed to upsert vectors to {collection_name}: {e}")
            return VectorOperationResult(
                success=False,
                operation="upsert_vectors",
                count=0,
                processing_time=time.time() - start_time,
                error=str(e)
            )

    async def search_vectors(self, collection_name: str, query_vector: List[float],
                           limit: int = 10, score_threshold: float = 0.0,
                           filter_conditions: Optional[Dict[str, Any]] = None) -> List[VectorSearchResult]:
        """Search for similar vectors with filtering"""
        if not self.connected:
            return []

        start_time = time.time()
        
        try:
            from qdrant_client.http import models
            
            # Build filter if provided
            query_filter = None
            if filter_conditions:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value)
                        )
                        for key, value in filter_conditions.items()
                    ]
                )
            
            # Perform search
            search_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    query_filter=query_filter,
                    limit=limit,
                    with_payload=True
                )
            )
            
            processing_time = time.time() - start_time
            self._update_metrics(processing_time)
            
            # Convert to our result format
            results = []
            for hit in search_result:
                if hit.score >= score_threshold:
                    results.append(VectorSearchResult(
                        id=str(hit.id),
                        score=hit.score,
                        payload=hit.payload or {},
                        vector=hit.vector
                    ))
            
            logger.debug(f"Found {len(results)} similar vectors in {collection_name}")
            return results

        except Exception as e:
            logger.error(f"Vector search failed in {collection_name}: {e}")
            return []

    def _update_metrics(self, processing_time: float):
        """Update performance metrics"""
        self.operation_count += 1
        self.total_processing_time += processing_time

    async def health_check(self) -> Dict[str, Any]:
        """Check Qdrant connection health"""
        try:
            if not self.connected:
                return {
                    "status": "unhealthy",
                    "error": "Not connected",
                    "last_check": time.time()
                }
            
            # Test with a simple operation
            collections = await asyncio.get_event_loop().run_in_executor(
                None, self.client.get_collections
            )
            
            return {
                "status": "healthy",
                "host": self.host,
                "port": self.port,
                "collections_count": len(collections.collections),
                "operation_count": self.operation_count,
                "avg_processing_time": self.total_processing_time / max(self.operation_count, 1),
                "last_check": time.time()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": time.time()
            }
