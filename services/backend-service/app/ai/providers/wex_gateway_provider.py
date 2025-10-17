"""
WEX AI Gateway Provider - Phase 3-2 Hybrid Provider Framework
Enhanced version of existing WEX AI Gateway integration with batching and cost tracking.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI

from app.models.unified_models import Integration
from app.core.config import AppConfig

logger = logging.getLogger(__name__)

class WEXGatewayProvider:
    """Enhanced WEX AI Gateway provider with batching and cost tracking"""

    def __init__(self, integration: Integration):
        self.integration = integration
        self.base_url = integration.base_url
        self.api_key = AppConfig.decrypt_token(integration.password, AppConfig.load_key()) if integration.password else None

        # Extract settings from JSON field (new schema)
        settings = integration.settings or {}
        self.model_config = settings
        self.cost_config = {'cost_tier': settings.get('cost_tier', 'free')}
        self.model_name = settings.get('model_path', 'azure-text-embedding-3-small')

        # Initialize OpenAI client pointing to WEX Gateway
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.model_config.get('timeout', 120)
        )

        # Performance tracking
        self.request_count = 0
        self.total_cost = 0.0
        self.avg_response_time = 0.0

    async def generate_embeddings(self, texts: List[str], model: str = None) -> List[List[float]]:
        """Generate embeddings via WEX AI Gateway with batching"""
        if not texts:
            return []

        start_time = time.time()

        # Use model from integration or parameter
        model_name = model or self.model_name
        batch_size = self.model_config.get('batch_size', 100)
        max_retries = self.model_config.get('max_retries', 3)

        all_embeddings = []

        try:
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                for attempt in range(max_retries):
                    try:
                        response = await self.client.embeddings.create(
                            model=model_name,
                            input=batch
                        )

                        batch_embeddings = [item.embedding for item in response.data]
                        all_embeddings.extend(batch_embeddings)
                        
                        # Update performance metrics
                        self.request_count += 1
                        processing_time = time.time() - start_time
                        self.avg_response_time = (
                            (self.avg_response_time * (self.request_count - 1) + processing_time) 
                            / self.request_count
                        )
                        
                        # Track cost (approximate)
                        if hasattr(response, 'usage') and response.usage:
                            cost = response.usage.total_tokens * 0.0001  # Rough estimate
                            self.total_cost += cost
                        
                        break  # Success, exit retry loop
                        
                    except Exception as e:
                        if attempt == max_retries - 1:
                            logger.error(f"WEX Gateway embedding batch failed after {max_retries} attempts: {e}")
                            # Return zero vectors for failed batch (1536 dimensions for text-embedding-3-small)
                            all_embeddings.extend([[0.0] * 1536] * len(batch))
                        else:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff

            return all_embeddings

        except Exception as e:
            logger.error(f"WEX Gateway embedding generation failed: {e}")
            # Return zero vectors for all texts
            return [[0.0] * 1536] * len(texts)

    async def generate_text(self, prompt: str, model: str = None, **kwargs) -> str:
        """Generate text via WEX AI Gateway"""
        if not prompt:
            return ""

        start_time = time.time()
        model_name = model or self.model_name
        max_retries = self.model_config.get('max_retries', 3)
        
        # Merge model config with kwargs
        generation_params = {**self.model_config, **kwargs}
        # Remove non-OpenAI parameters
        generation_params.pop('batch_size', None)
        generation_params.pop('timeout', None)
        generation_params.pop('max_retries', None)

        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    **generation_params
                )

                # Update performance metrics
                self.request_count += 1
                processing_time = time.time() - start_time
                self.avg_response_time = (
                    (self.avg_response_time * (self.request_count - 1) + processing_time) 
                    / self.request_count
                )
                
                # Track cost
                if hasattr(response, 'usage') and response.usage:
                    cost = (
                        response.usage.prompt_tokens * 0.0001 + 
                        response.usage.completion_tokens * 0.0002
                    )  # Rough estimate
                    self.total_cost += cost

                return response.choices[0].message.content

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"WEX Gateway text generation failed after {max_retries} attempts: {e}")
                    raise e
                else:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        return ""

    async def cleanup(self):
        """Cleanup async resources to prevent event loop errors"""
        try:
            if hasattr(self.client, 'close'):
                await self.client.close()
            elif hasattr(self.client, '_client') and hasattr(self.client._client, 'aclose'):
                await self.client._client.aclose()
        except Exception as e:
            # Suppress cleanup errors to avoid noise in logs
            pass

    async def health_check(self) -> Dict[str, Any]:
        """Check health of WEX Gateway connection"""
        try:
            # Simple test with a small embedding request
            test_response = await self.generate_embeddings(["health check test"])
            
            return {
                "status": "healthy" if test_response and len(test_response) > 0 else "unhealthy",
                "provider": "WEX AI Gateway",
                "base_url": self.base_url,
                "model": self.model_name,
                "request_count": self.request_count,
                "total_cost": self.total_cost,
                "avg_response_time": self.avg_response_time,
                "last_check": time.time()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "provider": "WEX AI Gateway",
                "error": str(e),
                "last_check": time.time()
            }

    def get_capabilities(self) -> List[str]:
        """Get list of capabilities this provider supports"""
        return ["embedding", "text_generation", "chat_completion"]

    def get_cost_info(self) -> Dict[str, Any]:
        """Get cost information for this provider"""
        return {
            "provider": "WEX AI Gateway",
            "cost_type": "paid",
            "total_cost": self.total_cost,
            "request_count": self.request_count,
            "avg_cost_per_request": self.total_cost / max(self.request_count, 1),
            "cost_config": self.cost_config
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for this provider"""
        return {
            "provider": "WEX AI Gateway",
            "request_count": self.request_count,
            "avg_response_time": self.avg_response_time,
            "total_cost": self.total_cost,
            "status": "active"
        }

    async def cleanup(self):
        """Cleanup async resources to prevent event loop errors"""
        try:
            if self.client:
                await self.client.close()
                logger.debug("WEX Gateway provider cleaned up")
        except Exception as e:
            logger.warning(f"Error during WEX Gateway cleanup: {e}")
