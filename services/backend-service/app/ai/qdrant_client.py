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

    def __init__(self, host: str = None, port: int = None, timeout: int = None):
        import os
        # Read from environment variables if not provided
        self.host = host or os.getenv("QDRANT_HOST", "localhost")
        self.port = port or int(os.getenv("QDRANT_PORT", "6333"))
        self.timeout = timeout or int(os.getenv("QDRANT_TIMEOUT", "120"))
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

            # Reduce HTTP request logging verbosity
            import logging
            logging.getLogger("httpx").setLevel(logging.WARNING)
            logging.getLogger("qdrant_client").setLevel(logging.WARNING)
            
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

    async def ensure_collection_exists(self, collection_name: str, vector_size: int = 1536,
                                     distance_metric: str = "Cosine") -> VectorOperationResult:
        """Ensure collection exists, create if it doesn't"""
        if not self.connected:
            return VectorOperationResult(
                success=False,
                operation="ensure_collection",
                count=0,
                processing_time=0.0,
                error="Not connected to Qdrant"
            )

        try:
            start_time = time.time()

            # Check if collection exists
            try:
                collection_info = await asyncio.to_thread(
                    self.client.get_collection, collection_name
                )
                # Collection exists, return success
                return VectorOperationResult(
                    success=True,
                    operation="ensure_collection",
                    count=0,
                    processing_time=time.time() - start_time,
                    error=None
                )
            except Exception:
                # Collection doesn't exist, create it
                pass

            # Create the collection
            return await self.create_collection(collection_name, vector_size, distance_metric)

        except Exception as e:
            logger.error(f"Error ensuring collection {collection_name}: {e}")
            return VectorOperationResult(
                success=False,
                operation="ensure_collection",
                count=0,
                processing_time=time.time() - start_time if 'start_time' in locals() else 0.0,
                error=str(e)
            )

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
            error_msg = str(e)
            # Don't log "already exists" as ERROR - it's expected in concurrent scenarios
            if "already exists" in error_msg.lower() or "409" in error_msg:
                logger.debug(f"Collection {collection_name} already exists (concurrent creation)")
                return VectorOperationResult(
                    success=True,
                    operation="create_collection",
                    count=0,
                    processing_time=time.time() - start_time,
                    error=f"Collection {collection_name} already exists"
                )
            else:
                logger.error(f"Failed to create collection {collection_name}: {e}")
                return VectorOperationResult(
                    success=False,
                    operation="create_collection",
                    count=0,
                    processing_time=time.time() - start_time,
                    error=error_msg
                )

    async def upsert_vectors(self, collection_name: str, vectors: Union[List[List[float]], List[Dict[str, Any]]],
                           payloads: Optional[List[Dict[str, Any]]] = None, ids: Optional[List[str]] = None) -> VectorOperationResult:
        """Upsert vectors with batch processing

        Args:
            collection_name: Name of the collection
            vectors: Either list of vector arrays OR list of dicts with 'id', 'vector', 'payload' keys
            payloads: List of payload dicts (only used if vectors is list of arrays)
            ids: List of point IDs (only used if vectors is list of arrays)
        """
        if not self.connected:
            return VectorOperationResult(
                success=False,
                operation="upsert_vectors",
                count=0,
                processing_time=0.0,
                error="Not connected to Qdrant"
            )

        if not vectors:
            return VectorOperationResult(
                success=False,
                operation="upsert_vectors",
                count=0,
                processing_time=0.0,
                error="No vectors provided"
            )

        start_time = time.time()

        try:
            from qdrant_client.http import models

            # Handle two different input formats
            if isinstance(vectors[0], dict):
                # New format: list of dicts with 'id', 'vector', 'payload' keys
                points = []
                for vector_dict in vectors:
                    points.append(models.PointStruct(
                        id=vector_dict['id'],
                        vector=vector_dict['vector'],
                        payload=vector_dict['payload']
                    ))
            else:
                # Old format: separate vectors, payloads, ids lists
                if payloads is None or len(vectors) != len(payloads):
                    return VectorOperationResult(
                        success=False,
                        operation="upsert_vectors",
                        count=0,
                        processing_time=0.0,
                        error="Vectors and payloads must have same length"
                    )

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

    async def list_collections(self) -> Dict[str, Any]:
        """List all collections in Qdrant"""
        try:
            if not await self.initialize():
                return {"collections": [], "error": "Failed to connect to Qdrant"}

            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            return {
                "collections": collection_names,
                "count": len(collection_names)
            }

        except Exception as e:
            logger.error(f"Error listing Qdrant collections: {e}")
            return {"collections": [], "error": str(e)}

    async def delete_collection(self, collection_name: str) -> bool:
        """Delete a specific collection from Qdrant"""
        try:
            if not await self.initialize():
                logger.error("Failed to connect to Qdrant for collection deletion")
                return False

            # Check if collection exists first
            collections = self.client.get_collections()
            existing_collections = [col.name for col in collections.collections]

            if collection_name not in existing_collections:
                logger.warning(f"Collection {collection_name} does not exist in Qdrant")
                return True  # Consider it successful if it doesn't exist

            # Delete the collection
            result = self.client.delete_collection(collection_name)
            logger.info(f"Successfully deleted Qdrant collection: {collection_name}")
            return True

        except Exception as e:
            logger.error(f"Error deleting Qdrant collection {collection_name}: {e}")
            return False

    async def delete_all_collections(self) -> Dict[str, Any]:
        """Delete ALL collections from Qdrant (DANGEROUS)"""
        try:
            if not await self.initialize():
                return {"success": False, "error": "Failed to connect to Qdrant"}

            # Get all collections
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            deleted_collections = []
            failed_deletions = []

            # Delete each collection
            for collection_name in collection_names:
                try:
                    self.client.delete_collection(collection_name)
                    deleted_collections.append(collection_name)
                    logger.info(f"Deleted collection: {collection_name}")
                except Exception as e:
                    failed_deletions.append({"collection": collection_name, "error": str(e)})
                    logger.error(f"Failed to delete collection {collection_name}: {e}")

            return {
                "success": True,
                "deleted_collections": deleted_collections,
                "failed_deletions": failed_deletions,
                "total_processed": len(collection_names)
            }

        except Exception as e:
            logger.error(f"Error in delete_all_collections: {e}")
            return {"success": False, "error": str(e)}
