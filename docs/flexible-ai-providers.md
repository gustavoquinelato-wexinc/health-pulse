# Flexible AI Provider Framework

**Status**: ✅ **IMPLEMENTED** (September 2025)
**Architecture**: JSON-based configuration with zero-schema-change flexibility

## 🎯 Overview

The Flexible AI Provider Framework enables unlimited AI provider management through JSON-based configuration, eliminating the need for database schema changes when adding new providers. The system automatically routes operations to the most appropriate provider based on context (ETL vs Frontend) and cost optimization.

## 🏗️ Architecture

### **Simplified Integration Types**

| Type | Purpose | Examples |
|------|---------|----------|
| **Data** | Data ingestion | Jira, GitHub, WEX Fabric, WEX AD |
| **AI** | Text generation | WEX AI Gateway, WEX AI Gateway Fallback |
| **Embedding** | Vector generation | Local Embeddings, WEX Embeddings |

### **JSON-Based Configuration**

All routing logic is stored in the `ai_model_config` JSONB column, enabling flexible provider management without schema changes.

#### AI Provider Configuration
```json
{
  "temperature": 0.3,
  "max_tokens": 700,
  "gateway_route": true,    // Routes through WEX AI Gateway
  "source": "external"     // Uses external cloud models
}
```

#### Local Embedding Configuration
```json
{
  "model_path": "/models/sentence-transformers/all-MiniLM-L6-v2",
  "cost_tier": "free",
  "gateway_route": false,   // Direct local processing
  "source": "local"        // Uses local models
}
```
*Note: `ai_model` field would contain just `"all-MiniLM-L6-v2"` (model name only)*

#### External Embedding Configuration
```json
{
  "model_path": "azure-text-embedding-3-small",
  "cost_tier": "paid",
  "gateway_route": true,    // Routes through WEX AI Gateway
  "source": "external"     // Uses external API
}
```

## 🎯 Smart Provider Selection

### **Context-Aware Routing**

The system automatically selects providers based on operation context:

#### ETL Operations (Data Processing)
```python
# Prefers local models for cost-effective data processing
embedding_provider = await hybrid_manager.get_embedding_provider(
    tenant_id=tenant_id, 
    prefer_local=True  # gateway_route: false
)
```

#### Frontend Operations (AI Agents)
```python
# Prefers gateway providers for high-quality AI interactions
embedding_provider = await hybrid_manager.get_embedding_provider(
    tenant_id=tenant_id, 
    prefer_local=False  # gateway_route: true
)
```

### **Selection Logic**

| Context | Type | Preference | Routing | Purpose |
|---------|------|------------|---------|---------|
| ETL | Embedding | `gateway_route: false` | Local | Cost-effective data vectorization |
| Frontend | Embedding | `gateway_route: true` | Gateway | High-quality semantic search |
| Frontend | AI | `gateway_route: true` | Gateway | Advanced text generation |

## 🚀 Future-Proof Design

### **Adding New Providers**

Adding new providers requires **zero schema changes**:

#### Ollama Local LLM
```json
{
  "temperature": 0.7,
  "max_tokens": 1000,
  "gateway_route": false,
  "source": "local",
  "endpoint": "http://localhost:11434"
}
```

#### Direct OpenAI Integration
```json
{
  "temperature": 0.3,
  "max_tokens": 700,
  "gateway_route": false,
  "source": "external",
  "api_endpoint": "https://api.openai.com/v1/chat/completions"
}
```

#### Custom Enterprise LLM
```json
{
  "temperature": 0.5,
  "max_tokens": 1500,
  "gateway_route": false,
  "source": "external",
  "api_endpoint": "https://enterprise-llm.company.com/v1/generate",
  "auth_type": "bearer_token"
}
```

## 💰 Cost Optimization

### **Automatic Cost Management**

| Provider | Cost | Use Case | Selection Logic |
|----------|------|----------|-----------------|
| Local Embeddings | $0 | ETL data processing | Default for `prefer_local=True` |
| WEX Embeddings | Paid | Frontend semantic search | Default for `prefer_local=False` |
| WEX AI Gateway | Paid | Complex text generation | Only for AI type providers |

### **Cost Tracking**

```json
{
  "cost_config": {
    "cost_tier": "free",           // "free" or "paid"
    "estimated_cost_per_1k": 0.0,  // Cost tracking
    "monthly_limit": null          // Optional spending limits
  }
}
```

## 🔧 Implementation Details

### **Database Schema**

No changes required to existing `integrations` table:

```sql
-- Existing schema supports all functionality
CREATE TABLE integrations (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,           -- 'WEX AI Gateway', 'Local Embeddings'
    type VARCHAR(50) NOT NULL,               -- 'Data', 'AI', 'Embedding'
    ai_model_config JSONB DEFAULT '{}',     -- All routing logic here
    -- ... other existing fields
);
```

### **Provider Selection API**

```python
class HybridProviderManager:
    async def get_embedding_provider(self, tenant_id: int, prefer_local: bool = True):
        """Get embedding provider based on context preference"""
        query = self.db_session.query(Integration).filter(
            Integration.tenant_id == tenant_id,
            Integration.type == 'Embedding',
            Integration.active == True
        )
        
        integrations = query.all()
        
        if prefer_local:
            # ETL: Prefer local models (gateway_route = false)
            for integration in integrations:
                config = integration.ai_model_config or {}
                if not config.get('gateway_route', True):
                    return integration
        else:
            # Frontend: Prefer gateway providers (gateway_route = true)
            for integration in integrations:
                config = integration.ai_model_config or {}
                if config.get('gateway_route', False):
                    return integration
        
        # Fallback to any active provider
        return query.first()
```

## 📊 Benefits

### **Technical Benefits**
- ✅ **Zero Schema Changes**: Add unlimited providers without migrations
- ✅ **Context-Aware Routing**: Automatic selection based on use case
- ✅ **Cost Optimization**: Smart routing between free and paid services
- ✅ **Future-Proof**: Easy integration of new AI technologies

### **Business Benefits**
- ✅ **Reduced IT Overhead**: No database changes for new providers
- ✅ **Cost Control**: Automatic selection of cost-effective providers
- ✅ **Flexibility**: Support for any AI provider or model
- ✅ **Scalability**: Architecture scales with AI ecosystem growth

## 🎯 Usage Examples

### **Current Providers**

1. **WEX AI Gateway** (Primary AI)
   - Type: `AI`
   - Configuration: `gateway_route: true, source: "external"`
   - Use: Frontend text generation

2. **WEX AI Gateway Fallback** (Backup AI)
   - Type: `AI`
   - Configuration: `gateway_route: true, source: "external"`
   - Use: Fallback for primary AI

3. **Local Embeddings** (Free)
   - Type: `Embedding`
   - Configuration: `gateway_route: false, source: "local"`
   - Use: ETL data vectorization

4. **WEX Embeddings** (Paid)
   - Type: `Embedding`
   - Configuration: `gateway_route: true, source: "external"`
   - Use: Frontend semantic search

### **Future Providers** (Easy to Add)

- **Ollama**: Local LLM hosting
- **Direct OpenAI**: Bypass gateway for specific use cases
- **Custom Models**: Enterprise-specific AI models
- **Specialized Embeddings**: Domain-specific embedding models

This flexible architecture positions the platform for unlimited AI provider integration while maintaining cost optimization and operational simplicity.
