# Phase 3-2: Multi-Provider AI Framework (WrenAI-Inspired)

**Implemented**: NO ❌
**Duration**: 2 days (Days 2-3 of 10)
**Priority**: CRITICAL
**Dependencies**: Phase 3-1 completion

## 🚀 WrenAI-Inspired Optimizations Incorporated

Based on comprehensive analysis of WrenAI (open-source BI agent), the following optimizations are implemented in this phase:

### **1. Multi-Provider Architecture (WrenAI-Inspired)**
- **Provider Abstraction**: Clean separation between LLM providers and business logic
- **Configuration-Driven**: YAML-based pipeline configuration for different AI models
- **Unified Interface**: LiteLLM-style unified interface for multiple providers
- **Fallback Support**: Automatic fallback to secondary providers

### **2. Performance Optimizations**
- **Qdrant Vector Database**: High-performance alternative to pgvector (10-40x faster)
- **Batch Processing**: Optimized batch operations for embedding generation
- **Intelligent Caching**: Multi-level caching (query, schema, embedding)
- **Parallel Processing**: Concurrent validations and retrievals

### **3. Cost Optimization**
- **Provider Selection**: Smart selection based on cost vs performance
- **Usage Tracking**: Comprehensive cost monitoring and analytics
- **Local Models**: Sentence Transformers for zero-cost embeddings
- **Batch Optimization**: Minimize API calls through intelligent batching

## 🎯 Phase 3-2 Objectives

1. **Multi-Provider Architecture**: WrenAI-inspired provider abstraction for multiple AI models
2. **High-Performance Embedding**: 10x faster than hackathon approach with batching and caching
3. **Qdrant Client**: Enterprise-grade vector operations with client isolation
4. **Configuration-Driven**: YAML-based pipeline configuration like WrenAI
5. **Cost Optimization**: Smart provider selection and usage tracking
6. **Unified Models**: Update all services with AI configuration models

## 🚀 WrenAI-Inspired Provider Architecture

### **Provider Abstraction (Based on WrenAI's Design)**
```python
# services/backend-service/app/ai/providers/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import asyncio

@dataclass
class ModelInfo:
    """AI model information (inspired by WrenAI)"""
    name: str
    provider: str
    dimensions: int
    max_tokens: int
    cost_per_1k_tokens: float
    capabilities: List[str]  # ['embedding', 'text_generation', 'analysis']
    performance_tier: str    # 'fast', 'balanced', 'quality'

@dataclass
class AIProviderConfig:
    """Provider configuration (WrenAI-inspired)"""
    provider_type: str
    model_name: str
    credentials: Dict[str, Any]
    model_config: Dict[str, Any]
    performance_config: Dict[str, Any]
    timeout: int = 120
    max_retries: int = 3
    batch_size: int = 100

class BaseAIProvider(ABC):
    """Base AI provider interface (inspired by WrenAI's provider system)"""
    
    def __init__(self, config: AIProviderConfig):
        self.config = config
        self.model_info = self._get_model_info()
    
    @abstractmethod
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        pass
    
    @abstractmethod
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text response"""
        pass
    
    @abstractmethod
    def _get_model_info(self) -> ModelInfo:
        """Get model information"""
        pass
    
    async def health_check(self) -> bool:
        """Check provider health"""
        try:
            test_embedding = await self.generate_embeddings(["test"])
            return len(test_embedding) > 0 and len(test_embedding[0]) > 0
        except Exception:
            return False
```

### **OpenAI Provider (WrenAI-Style Implementation)**
```python
# services/backend-service/app/ai/providers/openai_provider.py
import openai
from typing import List
import asyncio
from .base import BaseAIProvider, ModelInfo

class OpenAIProvider(BaseAIProvider):
    """OpenAI provider with batching and performance optimization"""
    
    def __init__(self, config: AIProviderConfig):
        super().__init__(config)
        self.client = openai.AsyncOpenAI(
            api_key=config.credentials.get("api_key"),
            base_url=config.credentials.get("base_url"),
            timeout=config.timeout
        )
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """High-performance batch embedding generation"""
        if not texts:
            return []
        
        # Batch processing for performance (WrenAI approach)
        batch_size = self.config.batch_size
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                response = await self.client.embeddings.create(
                    model=self.config.model_name,
                    input=batch,
                    **self.config.model_config
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                # Track usage for cost monitoring
                await self._track_usage(
                    operation="embedding",
                    input_count=len(batch),
                    input_tokens=response.usage.total_tokens if hasattr(response, 'usage') else 0
                )
                
            except Exception as e:
                logger.error(f"OpenAI embedding batch failed: {e}")
                # Return zero vectors for failed batch
                all_embeddings.extend([[0.0] * self.model_info.dimensions] * len(batch))
        
        return all_embeddings
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text with retry logic"""
        for attempt in range(self.config.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    **{**self.config.model_config, **kwargs}
                )
                
                # Track usage
                await self._track_usage(
                    operation="text_generation",
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens
                )
                
                return response.choices[0].message.content
                
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    raise e
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    def _get_model_info(self) -> ModelInfo:
        """Get OpenAI model information"""
        model_configs = {
            "text-embedding-ada-002": ModelInfo(
                name="text-embedding-ada-002",
                provider="openai",
                dimensions=1536,
                max_tokens=8191,
                cost_per_1k_tokens=0.0001,
                capabilities=["embedding"],
                performance_tier="balanced"
            ),
            "text-embedding-3-small": ModelInfo(
                name="text-embedding-3-small",
                provider="openai",
                dimensions=1536,
                max_tokens=8191,
                cost_per_1k_tokens=0.00002,
                capabilities=["embedding"],
                performance_tier="fast"
            ),
            "gpt-4": ModelInfo(
                name="gpt-4",
                provider="openai",
                dimensions=0,
                max_tokens=8192,
                cost_per_1k_tokens=0.03,
                capabilities=["text_generation", "analysis"],
                performance_tier="quality"
            )
        }
        
        return model_configs.get(self.config.model_name, model_configs["text-embedding-ada-002"])
```

### **Sentence Transformers Provider (Local, High-Performance)**
```python
# services/backend-service/app/ai/providers/sentence_transformers_provider.py
from sentence_transformers import SentenceTransformer
import torch
from typing import List
from .base import BaseAIProvider, ModelInfo

class SentenceTransformersProvider(BaseAIProvider):
    """Local sentence transformers for high-performance, zero-cost embeddings"""
    
    def __init__(self, config: AIProviderConfig):
        super().__init__(config)
        
        # Load model with GPU support if available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(
            self.config.model_name,
            device=device
        )
        
        # Performance optimization
        if device == "cuda":
            self.model.half()  # Use half precision for speed
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Ultra-fast local embedding generation (1000+ embeddings/second)"""
        if not texts:
            return []
        
        try:
            # Batch processing with optimal batch size
            embeddings = self.model.encode(
                texts,
                batch_size=self.config.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True  # For better similarity search
            )
            
            # Track usage (no cost for local models)
            await self._track_usage(
                operation="embedding",
                input_count=len(texts),
                cost=0.0  # Free local processing
            )
            
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f"SentenceTransformers embedding failed: {e}")
            return [[0.0] * self.model_info.dimensions] * len(texts)
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Not supported for embedding-only models"""
        raise NotImplementedError("Text generation not supported by embedding models")
    
    def _get_model_info(self) -> ModelInfo:
        """Get sentence transformers model info"""
        model_configs = {
            "all-MiniLM-L6-v2": ModelInfo(
                name="all-MiniLM-L6-v2",
                provider="sentence_transformers",
                dimensions=384,
                max_tokens=512,
                cost_per_1k_tokens=0.0,  # Free
                capabilities=["embedding"],
                performance_tier="fast"
            ),
            "all-mpnet-base-v2": ModelInfo(
                name="all-mpnet-base-v2",
                provider="sentence_transformers",
                dimensions=768,
                max_tokens=514,
                cost_per_1k_tokens=0.0,  # Free
                capabilities=["embedding"],
                performance_tier="quality"
            )
        }
        
        return model_configs.get(self.config.model_name, model_configs["all-MiniLM-L6-v2"])
```

### **Provider Factory (WrenAI-Inspired Configuration)**
```python
# services/backend-service/app/ai/provider_factory.py
from typing import Dict, Type
from .providers.base import BaseAIProvider
from .providers.openai_provider import OpenAIProvider
from .providers.azure_openai_provider import AzureOpenAIProvider
from .providers.sentence_transformers_provider import SentenceTransformersProvider
from .providers.custom_gateway_provider import CustomGatewayProvider

class AIProviderFactory:
    """Factory for creating AI providers (WrenAI-inspired)"""
    
    _providers: Dict[str, Type[BaseAIProvider]] = {
        "openai": OpenAIProvider,
        "azure_openai": AzureOpenAIProvider,
        "sentence_transformers": SentenceTransformersProvider,
        "custom_gateway": CustomGatewayProvider,
        # Add more providers as needed
    }
    
    @classmethod
    def create_provider(cls, provider_type: str, config: AIProviderConfig) -> BaseAIProvider:
        """Create provider instance"""
        if provider_type not in cls._providers:
            raise ValueError(f"Unknown provider type: {provider_type}")
        
        provider_class = cls._providers[provider_type]
        return provider_class(config)
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of available provider types"""
        return list(cls._providers.keys())
```

### **Qdrant Client (Enterprise-Grade)**
```python
# services/backend-service/app/ai/qdrant_client.py
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition
import uuid
from typing import List, Dict, Any, Optional
import asyncio

class PulseQdrantClient:
    """Enterprise Qdrant client with client isolation and performance optimization"""
    
    def __init__(self):
        self.client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            timeout=int(os.getenv("QDRANT_TIMEOUT", "120"))
        )
    
    def _get_collection_name(self, client_id: int, table_name: str) -> str:
        """Generate client-specific collection name for perfect isolation"""
        return f"client_{client_id}_{table_name}"
    
    async def create_collection(self, client_id: int, table_name: str, vector_size: int = 1536):
        """Create client-specific collection with performance optimization"""
        collection_name = self._get_collection_name(client_id, table_name)
        
        try:
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                    # Performance optimization for 10M+ scale
                    hnsw_config={
                        "m": 16,
                        "ef_construct": 100,
                        "full_scan_threshold": 10000
                    }
                )
            )
            logger.info(f"Created Qdrant collection: {collection_name}")
        except Exception as e:
            if "already exists" not in str(e):
                logger.error(f"Failed to create collection {collection_name}: {e}")
                raise
    
    async def upsert_vectors_batch(self, client_id: int, table_name: str, 
                                  records: List[Dict[str, Any]]) -> List[str]:
        """Batch upsert for high performance"""
        collection_name = self._get_collection_name(client_id, table_name)
        
        points = []
        point_ids = []
        
        for record in records:
            point_id = str(uuid.uuid4())
            point_ids.append(point_id)
            
            # Add client_id to metadata for additional filtering
            metadata = record.get("metadata", {})
            metadata.update({
                "client_id": client_id,
                "table_name": table_name,
                "record_id": record["record_id"]
            })
            
            points.append(PointStruct(
                id=point_id,
                vector=record["vector"],
                payload=metadata
            ))
        
        # Batch upsert for performance
        await self.client.upsert(
            collection_name=collection_name,
            points=points
        )
        
        return point_ids
    
    async def search_similar(self, client_id: int, table_name: str, 
                           query_vector: List[float], limit: int = 10,
                           score_threshold: float = 0.7) -> List[Dict]:
        """High-performance similarity search with client isolation"""
        collection_name = self._get_collection_name(client_id, table_name)
        
        # Double-layer client isolation: collection name + filter
        filter_condition = Filter(
            must=[
                FieldCondition(key="client_id", match={"value": client_id})
            ]
        )
        
        results = await self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=filter_condition,
            limit=limit,
            score_threshold=score_threshold,
            # Performance optimization
            search_params={"hnsw_ef": 128}
        )
        
        return [
            {
                "id": result.id,
                "score": result.score,
                "metadata": result.payload,
                "record_id": result.payload.get("record_id"),
                "table_name": result.payload.get("table_name")
            }
            for result in results
        ]
```

## 📋 Implementation Tasks

### **Task 3-2.1: Provider Framework Implementation**
- [ ] Create base provider interface
- [ ] Implement OpenAI provider with batching
- [ ] Implement Azure OpenAI provider
- [ ] Implement Sentence Transformers provider
- [ ] Implement Custom Gateway provider
- [ ] Create provider factory

### **Task 3-2.2: Qdrant Client Implementation**
- [ ] Create PulseQdrantClient with client isolation
- [ ] Implement batch operations for performance
- [ ] Add collection management
- [ ] Implement similarity search with filtering

### **Task 3-2.3: Configuration System (WrenAI-Inspired)**
- [ ] Create YAML-based configuration
- [ ] Implement provider selection logic
- [ ] Add fallback provider support
- [ ] Create cost optimization logic

### **Task 3-2.4: Unified Models Update**
- [ ] Update backend service models
- [ ] Update ETL service models
- [ ] Update auth service models
- [ ] Add AI configuration relationships

## ✅ Success Criteria

1. **Multi-Provider Support**: All providers working with consistent interface
2. **Performance**: 10x improvement in embedding generation speed
3. **Client Isolation**: Perfect separation in Qdrant collections
4. **Configuration**: YAML-based provider configuration working
5. **Cost Tracking**: Usage monitoring for all providers
6. **Fallback Support**: Automatic fallback to secondary providers

## 🔄 Completion Enables

- **Phase 3-3**: Frontend AI configuration interface
- **Phase 3-4**: ETL AI integration with providers
- **Phase 3-5**: High-performance vector generation
