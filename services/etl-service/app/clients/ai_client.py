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

# Convenience function for ETL jobs
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
