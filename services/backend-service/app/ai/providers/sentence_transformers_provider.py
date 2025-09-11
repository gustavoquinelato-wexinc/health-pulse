"""
Sentence Transformers Provider - Phase 3-2 Hybrid Provider Framework
Local embedding generation using Sentence Transformers for zero-cost operations.
"""

import asyncio
import logging
import time
import threading
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from app.models.unified_models import Integration

logger = logging.getLogger(__name__)

class SentenceTransformersProvider:
    """Local Sentence Transformers provider for zero-cost embeddings"""

    def __init__(self, integration: Integration):
        self.integration = integration
        self.model_name = integration.ai_model or "all-MiniLM-L6-v2"
        self.model_config = integration.ai_model_config or {}
        
        # Model and performance tracking
        self.model = None
        self.model_loaded = False
        self.request_count = 0
        self.total_processing_time = 0.0
        self.avg_response_time = 0.0
        
        # Thread pool for CPU-intensive operations
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._lock = threading.Lock()

    async def initialize(self) -> bool:
        """Initialize the Sentence Transformers model"""
        try:
            # Import here to avoid dependency issues if not installed
            from sentence_transformers import SentenceTransformer
            
            logger.info(f"Loading Sentence Transformers model: {self.model_name}")
            
            # Load model in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                self.executor,
                self._load_model,
                self.model_name
            )
            
            self.model_loaded = True
            logger.info(f"Successfully loaded model: {self.model_name}")
            return True
            
        except ImportError:
            logger.error("sentence-transformers package not installed. Install with: pip install sentence-transformers")
            return False
        except Exception as e:
            logger.error(f"Failed to load Sentence Transformers model {self.model_name}: {e}")
            return False

    def _load_model(self, model_name: str):
        """Load model in thread pool (blocking operation)"""
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(model_name)

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Ultra-fast local embedding generation (1000+ embeddings/second)"""
        if not texts:
            return []

        if not self.model_loaded or self.model is None:
            logger.error("Model not loaded. Call initialize() first.")
            return []

        start_time = time.time()

        try:
            # Run in thread pool to avoid blocking async loop
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                self.executor,
                self._encode_texts,
                texts
            )

            processing_time = time.time() - start_time
            
            # Update performance metrics
            with self._lock:
                self.request_count += 1
                self.total_processing_time += processing_time
                self.avg_response_time = self.total_processing_time / self.request_count

            logger.debug(f"Generated {len(embeddings)} embeddings in {processing_time:.3f}s")
            
            return embeddings.tolist()

        except Exception as e:
            logger.error(f"Local embedding generation failed: {e}")
            return []

    def _encode_texts(self, texts: List[str]) -> np.ndarray:
        """Encode texts using the loaded model (blocking operation)"""
        return self.model.encode(texts, convert_to_numpy=True)

    async def health_check(self) -> Dict[str, Any]:
        """Check health of local model"""
        try:
            if not self.model_loaded:
                return {
                    "status": "unhealthy",
                    "provider": "Sentence Transformers",
                    "error": "Model not loaded",
                    "last_check": time.time()
                }
            
            # Simple test with a small embedding request
            test_response = await self.generate_embeddings(["health check test"])
            
            return {
                "status": "healthy" if test_response and len(test_response) > 0 else "unhealthy",
                "provider": "Sentence Transformers",
                "model": self.model_name,
                "model_loaded": self.model_loaded,
                "request_count": self.request_count,
                "avg_response_time": self.avg_response_time,
                "total_cost": 0.0,  # Always free
                "last_check": time.time()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "provider": "Sentence Transformers",
                "error": str(e),
                "last_check": time.time()
            }

    def get_capabilities(self) -> List[str]:
        """Get list of capabilities this provider supports"""
        return ["embedding"]  # Only embeddings, no text generation

    def get_cost_info(self) -> Dict[str, Any]:
        """Get cost information for this provider"""
        return {
            "provider": "Sentence Transformers",
            "cost_type": "free",
            "total_cost": 0.0,
            "request_count": self.request_count,
            "avg_cost_per_request": 0.0,
            "cost_savings": "100% cost savings vs. paid providers"
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for this provider"""
        return {
            "provider": "Sentence Transformers",
            "model": self.model_name,
            "model_loaded": self.model_loaded,
            "request_count": self.request_count,
            "avg_response_time": self.avg_response_time,
            "total_processing_time": self.total_processing_time,
            "status": "active" if self.model_loaded else "inactive"
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model"""
        if not self.model_loaded:
            return {"error": "Model not loaded"}
        
        # Get model dimensions
        try:
            test_embedding = self.model.encode(["test"], convert_to_numpy=True)
            dimensions = test_embedding.shape[1]
        except:
            dimensions = "unknown"
        
        return {
            "model_name": self.model_name,
            "dimensions": dimensions,
            "max_sequence_length": getattr(self.model, 'max_seq_length', 'unknown'),
            "model_loaded": self.model_loaded,
            "provider": "Sentence Transformers"
        }

    async def cleanup(self):
        """Cleanup resources"""
        if self.executor:
            self.executor.shutdown(wait=True)
        self.model = None
        self.model_loaded = False
        logger.info("Sentence Transformers provider cleaned up")
