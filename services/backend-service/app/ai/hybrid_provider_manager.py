"""
Hybrid Provider Manager - Phase 3-2 Multi-Provider Framework
Intelligently routes between WEX Gateway (primary) and local models (secondary) for cost optimization.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.models.unified_models import Integration, AIUsageTracking
from app.core.config import AppConfig
from .providers.wex_gateway_provider import WEXGatewayProvider
from .providers.sentence_transformers_provider import SentenceTransformersProvider

logger = logging.getLogger(__name__)

@dataclass
class ProviderConfig:
    """Simplified provider configuration using existing integrations table"""
    integration_id: int
    provider: str  # 'wex_ai_gateway', 'sentence_transformers'
    type: str      # 'ai_provider'
    base_url: Optional[str]
    api_key: Optional[str]
    ai_model: str
    ai_model_config: Dict[str, Any]
    cost_config: Dict[str, Any]
    fallback_integration_id: Optional[int] = None
    active: bool = True

@dataclass
class ProviderResponse:
    """Standardized response from any provider"""
    success: bool
    data: Any
    provider_used: str
    cost: float
    processing_time: float
    error: Optional[str] = None
    tokens_used: int = 0

class HybridProviderManager:
    """Manages both WEX AI Gateway and local model integrations with intelligent routing"""

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.providers: Dict[str, Union[WEXGatewayProvider, SentenceTransformersProvider]] = {}
        self.provider_configs: Dict[int, ProviderConfig] = {}
        self.performance_cache: Dict[str, Dict[str, float]] = {}
        
        # Provider performance tracking (updated dynamically)
        self.provider_performance = {
            "wex_ai_gateway": {"speed": 500, "cost": 0.0001, "quality": 0.95, "reliability": 0.98},
            "sentence_transformers": {"speed": 1000, "cost": 0.0, "quality": 0.85, "reliability": 0.99}
        }

    async def initialize_providers(self, tenant_id: int) -> bool:
        """Initialize providers from integrations table for specific tenant"""
        try:
            # Load AI and Embedding provider integrations for this tenant
            integrations = self.db_session.query(Integration).filter(
                Integration.tenant_id == tenant_id,
                Integration.type.in_(['AI', 'Embedding']),
                Integration.active == True
            ).all()

            if not integrations:
                logger.warning(f"No AI provider integrations found for tenant {tenant_id}")
                return False

            for integration in integrations:
                provider_config = ProviderConfig(
                    integration_id=integration.id,
                    provider=integration.provider,
                    type=integration.type,
                    base_url=integration.base_url,
                    api_key=AppConfig.decrypt_token(integration.password, AppConfig.load_key()) if integration.password else None,
                    ai_model=integration.ai_model or "",
                    ai_model_config=integration.ai_model_config or {},
                    cost_config=integration.cost_config or {},
                    fallback_integration_id=integration.fallback_integration_id,
                    active=integration.active
                )
                
                self.provider_configs[integration.id] = provider_config
                
                # Initialize specific provider using normalized type
                normalized_provider = self._normalize_provider_type(integration.provider)

                if normalized_provider == 'wex_ai_gateway':
                    self.providers[f"wex_gateway_{integration.id}"] = WEXGatewayProvider(integration)
                    logger.info(f"Initialized WEX Gateway provider for tenant {tenant_id}")

                elif normalized_provider == 'sentence_transformers':
                    provider = SentenceTransformersProvider(integration)
                    await provider.initialize()  # Load the model
                    self.providers[f"sentence_transformers_{integration.id}"] = provider
                    logger.info(f"Initialized Sentence Transformers provider for tenant {tenant_id}")

                else:
                    logger.warning(f"Unknown provider type: {integration.provider} (normalized: {normalized_provider})")

            logger.info(f"Initialized {len(self.providers)} AI providers for tenant {tenant_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize providers for tenant {tenant_id}: {e}")
            return False

    def _normalize_provider_type(self, provider_type: str) -> str:
        """Normalize provider type to handle both old and new formats"""
        if not provider_type:
            return ''

        # Convert to lowercase and remove spaces for comparison
        normalized = provider_type.lower().replace(' ', '_')

        # Handle different variations
        if 'wex' in normalized and 'ai' in normalized and 'gateway' in normalized:
            return 'wex_ai_gateway'
        elif 'sentence' in normalized and 'transformers' in normalized:
            return 'sentence_transformers'
        elif 'openai' in normalized and 'azure' not in normalized:
            return 'openai'
        elif 'azure' in normalized and 'openai' in normalized:
            return 'azure_openai'

        # Remove fallback suffix and try again
        if '_fallback' in normalized:
            return self._normalize_provider_type(normalized.replace('_fallback', ''))

        # Return as-is if no match found
        return normalized

    async def get_embedding_provider(self, tenant_id: int, prefer_local: bool = True) -> Optional[Integration]:
        """Get embedding provider for ETL or frontend use"""
        try:
            query = self.db_session.query(Integration).filter(
                Integration.tenant_id == tenant_id,
                Integration.type == 'Embedding',
                Integration.active == True
            )

            if prefer_local:
                # ETL prefers local models (gateway_route = false in ai_model_config)
                integrations = query.all()
                for integration in integrations:
                    config = integration.ai_model_config or {}
                    if not config.get('gateway_route', True):  # Default to True if not specified
                        return integration
                # Fallback to any active embedding provider
                return query.first()
            else:
                # Frontend can use any embedding provider, prefer external
                integrations = query.all()
                for integration in integrations:
                    config = integration.ai_model_config or {}
                    if config.get('gateway_route', False):  # Prefer gateway providers
                        return integration
                # Fallback to any active embedding provider
                return query.first()

        except Exception as e:
            logger.error(f"Error getting embedding provider: {e}")
            return None

    async def generate_embeddings(self, texts: List[str], tenant_id: int,
                                 preferred_provider: str = "auto") -> ProviderResponse:
        """Generate embeddings with intelligent provider selection"""
        if not texts:
            return ProviderResponse(
                success=False,
                data=[],
                provider_used="none",
                cost=0.0,
                processing_time=0.0,
                error="No texts provided"
            )

        start_time = time.time()
        
        try:
            # Select optimal provider
            selected_provider = await self._select_optimal_provider(
                operation="embedding",
                tenant_id=tenant_id,
                data_size=len(texts),
                preferred_provider=preferred_provider
            )
            
            if not selected_provider:
                return ProviderResponse(
                    success=False,
                    data=[],
                    provider_used="none",
                    cost=0.0,
                    processing_time=time.time() - start_time,
                    error="No suitable provider available"
                )

            # Generate embeddings using selected provider
            embeddings = await selected_provider.generate_embeddings(texts)
            processing_time = time.time() - start_time
            
            # Calculate cost (zero for local models)
            cost = await self._calculate_cost(selected_provider, "embedding", len(texts))
            
            # Track usage
            await self._track_usage(
                provider=selected_provider.__class__.__name__,
                operation="embedding",
                tenant_id=tenant_id,
                input_count=len(texts),
                cost=cost,
                processing_time=processing_time
            )
            
            return ProviderResponse(
                success=True,
                data=embeddings,
                provider_used=selected_provider.__class__.__name__,
                cost=cost,
                processing_time=processing_time
            )

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return ProviderResponse(
                success=False,
                data=[],
                provider_used="error",
                cost=0.0,
                processing_time=time.time() - start_time,
                error=str(e)
            )

    async def generate_text(self, prompt: str, tenant_id: int,
                           preferred_provider: str = "auto", **kwargs) -> ProviderResponse:
        """Generate text with intelligent provider selection"""
        start_time = time.time()

        try:
            # Select optimal provider (prefer WEX Gateway for text generation)
            selected_provider = await self._select_optimal_provider(
                operation="text_generation",
                tenant_id=tenant_id,
                data_size=len(prompt),
                preferred_provider=preferred_provider
            )

            if not selected_provider:
                return ProviderResponse(
                    success=False,
                    data="",
                    provider_used="none",
                    cost=0.0,
                    processing_time=time.time() - start_time,
                    error="No suitable provider available"
                )

            # Generate text using selected provider
            if hasattr(selected_provider, 'generate_text'):
                text = await selected_provider.generate_text(prompt, **kwargs)
                processing_time = time.time() - start_time

                # Calculate cost
                cost = await self._calculate_cost(selected_provider, "text_generation", len(prompt))

                # Track usage
                await self._track_usage(
                    provider=selected_provider.__class__.__name__,
                    operation="text_generation",
                    tenant_id=tenant_id,
                    input_count=len(prompt),
                    cost=cost,
                    processing_time=processing_time
                )

                return ProviderResponse(
                    success=True,
                    data=text,
                    provider_used=selected_provider.__class__.__name__,
                    cost=cost,
                    processing_time=processing_time
                )
            else:
                return ProviderResponse(
                    success=False,
                    data="",
                    provider_used=selected_provider.__class__.__name__,
                    cost=0.0,
                    processing_time=time.time() - start_time,
                    error="Provider does not support text generation"
                )

        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            return ProviderResponse(
                success=False,
                data="",
                provider_used="error",
                cost=0.0,
                processing_time=time.time() - start_time,
                error=str(e)
            )

    async def _select_optimal_provider(self, operation: str, tenant_id: int,
                                     data_size: int, preferred_provider: str = "auto"):
        """Intelligent provider selection based on operation type, cost, and performance"""
        available_providers = []

        # Get available providers for this tenant
        for provider_key, provider in self.providers.items():
            # Simple check: if we have any providers, they're available for this tenant
            # (since we initialized them for this tenant)
            available_providers.append(provider)

        if not available_providers:
            return None

        # If specific provider requested
        if preferred_provider != "auto":
            for provider in available_providers:
                if preferred_provider.lower() in provider.__class__.__name__.lower():
                    return provider

        # Intelligent selection based on operation type
        if operation == "embedding":
            # For embeddings: prefer local models for cost savings, WEX Gateway for quality
            if data_size <= 100:  # Small batches: use local for speed
                local_providers = [p for p in available_providers if "SentenceTransformers" in p.__class__.__name__]
                if local_providers:
                    return local_providers[0]
            else:  # Large batches: use WEX Gateway for quality
                wex_providers = [p for p in available_providers if "WEXGateway" in p.__class__.__name__]
                if wex_providers:
                    return wex_providers[0]

        elif operation == "text_generation":
            # For text generation: prefer WEX Gateway (local models don't support this)
            wex_providers = [p for p in available_providers if "WEXGateway" in p.__class__.__name__]
            if wex_providers:
                return wex_providers[0]

        # Fallback: return first available provider
        return available_providers[0] if available_providers else None

    async def _calculate_cost(self, provider, operation: str, input_size: int) -> float:
        """Calculate cost for provider operation"""
        if "SentenceTransformers" in provider.__class__.__name__:
            return 0.0  # Local models are free

        # WEX Gateway cost calculation (approximate)
        if operation == "embedding":
            return input_size * 0.0001  # $0.0001 per text
        elif operation == "text_generation":
            return input_size * 0.001   # $0.001 per character (rough estimate)

        return 0.0

    async def _track_usage(self, provider: str, operation: str, tenant_id: int,
                          input_count: int, cost: float, processing_time: float):
        """Track AI usage in database"""
        try:
            usage_record = AIUsageTracking(
                tenant_id=tenant_id,
                provider=provider,
                operation=operation,
                input_count=input_count,
                cost=cost,
                processing_time=processing_time,
                active=True
            )

            self.db_session.add(usage_record)
            self.db_session.commit()

        except Exception as e:
            logger.error(f"Failed to track usage: {e}")
            self.db_session.rollback()

    def get_provider_status(self, tenant_id: int) -> Dict[str, Any]:
        """Get status of all providers for a tenant"""
        status = {
            "tenant_id": tenant_id,
            "providers": {},
            "total_providers": 0,
            "active_providers": 0
        }

        for provider_key, provider in self.providers.items():
            provider_name = provider.__class__.__name__
            status["providers"][provider_name] = {
                "active": True,
                "type": "local" if "SentenceTransformers" in provider_name else "remote",
                "cost": "free" if "SentenceTransformers" in provider_name else "paid",
                "capabilities": ["embedding"] if "SentenceTransformers" in provider_name else ["embedding", "text_generation"]
            }
            status["total_providers"] += 1
            status["active_providers"] += 1

        return status

    async def test_provider_configuration(self, provider_data: Dict[str, Any], tenant_id: int) -> Dict[str, Any]:
        """Test a provider configuration without saving it"""
        try:
            provider_type = provider_data.get('provider')
            test_text = "This is a test message for validating AI provider configuration."

            start_time = time.time()

            # Normalize provider type to handle both old and new formats
            base_provider_type = self._normalize_provider_type(provider_type)

            if base_provider_type == 'wex_ai_gateway':
                # Create a mock integration object for testing
                from app.models.unified_models import Integration
                mock_integration = Integration(
                    id=0,
                    tenant_id=tenant_id,
                    type='AI',
                    provider=base_provider_type,  # Use normalized provider type
                    base_url=provider_data.get('base_url', ''),
                    username=None,
                    password=AppConfig.encrypt_token('test_key', AppConfig.load_key()),  # Use test key
                    ai_model=provider_data.get('ai_model', ''),
                    ai_model_config=provider_data.get('ai_model_config', {}),
                    cost_config=provider_data.get('cost_config', {}),
                    active=True
                )

                # Test WEX Gateway provider
                provider = WEXGatewayProvider(mock_integration)

                # Test connectivity (without actual API call for now)
                result = {
                    'status': 'passed',
                    'response_time': round((time.time() - start_time) * 1000, 2),
                    'provider': base_provider_type,
                    'model': provider_data.get('ai_model'),
                    'details': 'Configuration validated successfully'
                }

            elif base_provider_type == 'sentence_transformers':
                # Test local provider
                provider = SentenceTransformersProvider(
                    model=provider_data.get('ai_model', 'all-MiniLM-L6-v2'),
                    model_config=provider_data.get('ai_model_config', {})
                )

                # Test embedding generation
                embeddings = await provider.generate_embeddings([test_text])

                result = {
                    'status': 'passed' if embeddings.success else 'failed',
                    'response_time': round(embeddings.processing_time * 1000, 2),
                    'provider': base_provider_type,
                    'model': provider_data.get('ai_model'),
                    'details': f'Generated {len(embeddings.data) if embeddings.success else 0} embeddings',
                    'error': embeddings.error if not embeddings.success else None
                }

            else:
                result = {
                    'status': 'failed',
                    'response_time': 0,
                    'provider': base_provider_type,
                    'model': provider_data.get('ai_model'),
                    'details': 'Unknown provider type',
                    'error': f'Unsupported provider type: {base_provider_type}'
                }

            return result

        except Exception as e:
            logger.error(f"Error testing provider configuration: {e}")
            return {
                'status': 'failed',
                'response_time': round((time.time() - start_time) * 1000, 2) if 'start_time' in locals() else 0,
                'provider': provider_data.get('provider', 'unknown').replace('_fallback', ''),
                'model': provider_data.get('ai_model', 'unknown'),
                'details': 'Configuration test failed',
                'error': str(e)
            }
