# Phase 3: AI Configuration & Vector Generation

**Implemented**: NO ❌
**Duration**: Weeks 5-7
**Priority**: HIGH
**Risk Level**: LOW

## 🎯 Phase Overview

Transform the platform from basic data analytics to intelligent, AI-powered insights with user-configurable AI models, high-performance embedding generation, and foundation for AI agents.

### **Sub-Phases:**
- **Phase 3-1**: Database Schema for AI Configuration *(1 day)*
- **Phase 3-2**: Backend AI Models & Services *(2 days)*
- **Phase 3-3**: Frontend AI Configuration Interface *(2 days)*
- **Phase 3-4**: ETL AI Integration *(2 days)*
- **Phase 3-5**: Vector Generation & Backfill *(2 days)*
- **Phase 3-6**: AI Agent Foundation *(2 days)*
- **Phase 3-7**: Testing & Documentation *(1 day)*

## 🎯 Overall Objectives

1. **Frontend AI Configuration**: User-friendly AI model selection and configuration
2. **Multi-Provider AI Support**: OpenAI, Azure, Gemini, Claude, Custom Gateway integration
3. **High-Performance Embedding Generation**: 10x faster than hackathon AI Gateway approach
4. **AI Agent Foundation**: Prepare infrastructure for dashboard AI agents and Q&A systems
5. **Vector Population**: Populate all embedding columns with meaningful vectors
6. **User Empowerment**: Business users control their AI experience through frontend interface

---

# Phase 3-1: Database Schema for AI Configuration

**Duration**: 1 day
**Priority**: CRITICAL
**Dependencies**: Phase 2 completion

## 🎯 Objectives

1. **Enhance Integration Table**: Add AI-specific columns for model configuration
2. **Client AI Preferences**: Store per-client AI configuration preferences
3. **Client AI Configuration**: Store organization-level AI policies and settings
4. **Migration Updates**: Update migrations 0001/0002 with CREATE statements (no ALTER)

## 📋 Database Schema Enhancements

### Enhanced Integration Table (Migration 0001 Update)
```sql
-- Update existing integrations table creation in 0001_initial_db_schema.py
CREATE TABLE IF NOT EXISTS integrations (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    integration_type VARCHAR(50) NOT NULL, -- 'jira', 'github', 'ai_model', etc.
    integration_subtype VARCHAR(50), -- 'embedding', 'llm', 'gateway', 'data_source'
    integration_name VARCHAR(100) NOT NULL,
    base_url TEXT,
    credentials JSONB DEFAULT '{}',
    configuration JSONB DEFAULT '{}',

    -- AI-specific columns
    model_config JSONB DEFAULT '{}',
    performance_config JSONB DEFAULT '{}',
    fallback_integration_id INTEGER REFERENCES integrations(id),

    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);
```

### Client AI Preferences Table (Migration 0001 Update)
```sql
-- Add to 0001_initial_db_schema.py
CREATE TABLE IF NOT EXISTS client_ai_preferences (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    preference_type VARCHAR(50) NOT NULL, -- 'agent_config', 'dashboard_ai', 'embedding_config'
    configuration JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    UNIQUE(client_id, preference_type)
);
```

### Client AI Configuration Table (Migration 0001 Update)
```sql
-- Add to 0001_initial_db_schema.py
CREATE TABLE IF NOT EXISTS client_ai_configuration (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    config_category VARCHAR(50) NOT NULL, -- 'models', 'policies', 'cost_limits', 'features'
    configuration JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    UNIQUE(client_id, config_category)
);
```

### AI Usage Tracking Table (Migration 0001 Update)
```sql
-- Add to 0001_initial_db_schema.py
CREATE TABLE IF NOT EXISTS ai_usage_tracking (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    provider VARCHAR(50) NOT NULL, -- 'openai', 'custom_gateway', 'sentence_transformers'
    operation VARCHAR(50) NOT NULL, -- 'embedding', 'text_generation', 'analysis'
    model_name VARCHAR(100),
    input_count INTEGER DEFAULT 0, -- Number of texts/requests processed
    input_tokens INTEGER DEFAULT 0, -- Input tokens used
    output_tokens INTEGER DEFAULT 0, -- Output tokens generated
    total_tokens INTEGER DEFAULT 0, -- Total tokens used
    cost DECIMAL(10,4) DEFAULT 0.0, -- Cost in USD
    request_metadata JSONB DEFAULT '{}', -- Additional request details
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);
```

### Indexes for AI Configuration (Migration 0001 Update)
```sql
-- Add to index creation section in 0001_initial_db_schema.py
CREATE INDEX IF NOT EXISTS idx_integrations_ai_type ON integrations(integration_type, integration_subtype);
CREATE INDEX IF NOT EXISTS idx_integrations_client_ai ON integrations(client_id, integration_type);
CREATE INDEX IF NOT EXISTS idx_client_ai_preferences_client ON client_ai_preferences(client_id);
CREATE INDEX IF NOT EXISTS idx_client_ai_preferences_type ON client_ai_preferences(preference_type);
CREATE INDEX IF NOT EXISTS idx_client_ai_config_client ON client_ai_configuration(client_id);
CREATE INDEX IF NOT EXISTS idx_client_ai_config_category ON client_ai_configuration(config_category);
CREATE INDEX IF NOT EXISTS idx_integrations_model_config ON integrations USING GIN(model_config);
CREATE INDEX IF NOT EXISTS idx_client_ai_preferences_config ON client_ai_preferences USING GIN(configuration);

-- AI usage tracking indexes
CREATE INDEX IF NOT EXISTS idx_ai_usage_tracking_client ON ai_usage_tracking(client_id);
CREATE INDEX IF NOT EXISTS idx_ai_usage_tracking_provider ON ai_usage_tracking(provider);
CREATE INDEX IF NOT EXISTS idx_ai_usage_tracking_operation ON ai_usage_tracking(operation);
CREATE INDEX IF NOT EXISTS idx_ai_usage_tracking_created_at ON ai_usage_tracking(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_usage_tracking_cost ON ai_usage_tracking(cost);
CREATE INDEX IF NOT EXISTS idx_ai_usage_tracking_tokens ON ai_usage_tracking(total_tokens);
CREATE INDEX IF NOT EXISTS idx_ai_usage_tracking_metadata ON ai_usage_tracking USING GIN(request_metadata);
```

---

# Phase 3-2: Backend AI Models & Services

**Duration**: 2 days
**Priority**: CRITICAL
**Dependencies**: Phase 3-1 completion

## 🎯 Objectives

1. **AI Provider Framework**: Generic interface for multiple AI providers
2. **Embedding Service**: High-performance embedding generation (10x faster than hackathon)
3. **Model Management**: Dynamic model loading and configuration
4. **Unified Models Update**: Add AI configuration models to backend/ETL/auth services

## 🚀 AI Provider Performance Strategy

**Problem**: AI Gateway was too slow during hackathon
**Solution**: Multiple high-performance approaches with user choice

### Provider Options:
- **Local Sentence Transformers**: 1000+ embeddings/second, $0 cost
- **OpenAI with Batching**: 100+ embeddings/second, high quality
- **Azure OpenAI**: 500+ embeddings/second, enterprise-grade
- **Custom Gateway**: Your hackathon models, configurable performance
- **Google Gemini**: Industry-standard alternative
- **Anthropic Claude**: When embedding support available

## 📋 Backend Implementation Tasks

### Unified Models Updates

#### Backend Service Models (services/backend-service/app/models/)
```python
# Add to unified_models.py

class Integration(Base):
    """Enhanced integration model with AI support"""
    __tablename__ = 'integrations'

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    integration_type = Column(String(50), nullable=False)
    integration_subtype = Column(String(50))  # NEW: 'embedding', 'llm', 'gateway'
    integration_name = Column(String(100), nullable=False)
    base_url = Column(Text)
    credentials = Column(JSONB, default={})
    configuration = Column(JSONB, default={})

    # AI-specific fields
    model_config = Column(JSONB, default={})  # NEW
    performance_config = Column(JSONB, default={})  # NEW
    fallback_integration_id = Column(Integer, ForeignKey('integrations.id'))  # NEW

    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    client = relationship("Client", back_populates="integrations")
    fallback_integration = relationship("Integration", remote_side=[id])

class ClientAIPreferences(Base):
    """Client AI configuration preferences"""
    __tablename__ = 'client_ai_preferences'

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    preference_type = Column(String(50), nullable=False)
    configuration = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    client = relationship("Client", back_populates="ai_preferences")

class ClientAIConfiguration(Base):
    """Client-level AI configuration"""
    __tablename__ = 'client_ai_configuration'

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    config_category = Column(String(50), nullable=False)
    configuration = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    client = relationship("Client", back_populates="ai_configuration")

class AIUsageTracking(Base):
    """AI usage tracking for cost monitoring and billing"""
    __tablename__ = 'ai_usage_tracking'

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    provider = Column(String(50), nullable=False)  # 'openai', 'custom_gateway', etc.
    operation = Column(String(50), nullable=False)  # 'embedding', 'text_generation'
    model_name = Column(String(100))
    input_count = Column(Integer, default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Numeric(10, 4), default=0.0)
    request_metadata = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    client = relationship("Client", back_populates="ai_usage_records")

# Update existing models with new relationships
class Client(Base):
    # ... existing fields ...
    ai_preferences = relationship("ClientAIPreferences", back_populates="client")
    ai_configuration = relationship("ClientAIConfiguration", back_populates="client")
    ai_usage_records = relationship("AIUsageTracking", back_populates="client")
```

#### ETL Service Models (services/etl-service/app/models/)
```python
# Copy same models to ETL service unified_models.py
# ETL needs access to AI configuration for embedding generation
# Note: All AI configuration is per-client, not per-user
```

### AI Provider Framework Implementation
```python
# services/backend-service/app/ai/ai_provider_framework.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import asyncio
import logging

@dataclass
class ModelInfo:
    """Information about an AI model"""
    name: str
    provider: str
    dimensions: int
    max_tokens: int
    cost_per_1k_tokens: float
    capabilities: List[str]  # ['embedding', 'text_generation', 'analysis']

@dataclass
class AIProviderConfig:
    """Configuration for AI provider"""
    provider_type: str
    model_name: str
    credentials: Dict[str, Any]
    model_config: Dict[str, Any]
    performance_config: Dict[str, Any]

class AIProviderInterface(ABC):
    """Abstract interface for AI providers"""

    @abstractmethod
    async def get_available_models(self) -> List[ModelInfo]:
        """Get list of available models"""
        pass

    @abstractmethod
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts"""
        pass

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Validate provider credentials"""
        pass

    @abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Get current model information"""
        pass

class SentenceTransformersProvider(AIProviderInterface):
    """Local Sentence Transformers provider - FASTEST"""

    def __init__(self, config: AIProviderConfig):
        self.config = config
        self.model = None
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """Initialize the model"""
        from sentence_transformers import SentenceTransformer
        model_name = self.config.model_config.get('model_name', 'all-mpnet-base-v2')
        self.model = SentenceTransformer(model_name)

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Ultra-fast local embedding generation"""
        if not self.model:
            await self.initialize()

        # Process in batches for memory efficiency
        batch_size = self.config.performance_config.get('batch_size', 100)
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None, self.model.encode, batch
            )

            batch_embeddings = [emb.tolist() for emb in embeddings]
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

class OpenAIProvider(AIProviderInterface):
    """OpenAI provider with batching optimization"""

    def __init__(self, config: AIProviderConfig):
        self.config = config
        self.client = None
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """Initialize OpenAI client"""
        import openai
        api_key = self.config.credentials.get('api_key')
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Optimized OpenAI embedding generation"""
        if not self.client:
            await self.initialize()

        batch_size = self.config.performance_config.get('batch_size', 50)
        model_name = self.config.model_config.get('model_name', 'text-embedding-3-small')
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            try:
                response = await self.client.embeddings.create(
                    model=model_name,
                    input=batch,
                    encoding_format="float"
                )

                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                # Respect rate limits
                await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error(f"OpenAI embedding error: {e}")
                raise

        return all_embeddings

class CustomGatewayProvider(AIProviderInterface):
    """Custom gateway provider for your hackathon models with cost tracking"""

    def __init__(self, config: AIProviderConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.usage_tracker = CustomGatewayUsageTracker(config)

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using custom gateway with cost tracking"""
        import aiohttp

        base_url = self.config.credentials.get('base_url')
        api_key = self.config.credentials.get('api_key')
        model_name = self.config.model_config.get('model_name')

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': model_name,
            'input': texts,
            'encoding_format': 'float'
        }

        async with aiohttp.ClientSession() as session:
            # Generate embeddings
            async with session.post(
                f"{base_url}/embeddings",
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    # Track usage and cost
                    await self.usage_tracker.track_embedding_usage(
                        texts=texts,
                        response_data=data,
                        session=session
                    )

                    return [item['embedding'] for item in data['data']]
                else:
                    raise Exception(f"Gateway error: {response.status}")

class CustomGatewayUsageTracker:
    """Track usage and costs for custom AI Gateway"""

    def __init__(self, config: AIProviderConfig):
        self.config = config
        self.base_url = config.credentials.get('base_url')
        self.api_key = config.credentials.get('api_key')
        self.logger = logging.getLogger(__name__)

    async def track_embedding_usage(
        self,
        texts: List[str],
        response_data: Dict[str, Any],
        session: aiohttp.ClientSession
    ):
        """Track embedding usage and calculate costs"""

        try:
            # Extract usage information from response
            usage_info = response_data.get('usage', {})
            input_tokens = usage_info.get('prompt_tokens', 0)
            total_tokens = usage_info.get('total_tokens', 0)

            # Calculate cost using AI Gateway endpoint
            cost_info = await self._calculate_request_cost(
                input_tokens=input_tokens,
                total_tokens=total_tokens,
                session=session
            )

            # Log usage for monitoring
            self.logger.info(
                f"AI Gateway Usage - Texts: {len(texts)}, "
                f"Input Tokens: {input_tokens}, "
                f"Total Tokens: {total_tokens}, "
                f"Cost: ${cost_info.get('cost', 0):.4f}"
            )

            # Store usage in database for client billing/monitoring
            await self._store_usage_record({
                'provider': 'custom_gateway',
                'operation': 'embedding',
                'input_count': len(texts),
                'input_tokens': input_tokens,
                'total_tokens': total_tokens,
                'cost': cost_info.get('cost', 0),
                'model': self.config.model_config.get('model_name'),
                'timestamp': datetime.now()
            })

        except Exception as e:
            self.logger.error(f"Failed to track usage: {e}")

    async def _calculate_request_cost(
        self,
        input_tokens: int,
        total_tokens: int,
        session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Calculate cost using AI Gateway /spend/calculate endpoint"""

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'input_tokens': input_tokens,
            'total_tokens': total_tokens,
            'model': self.config.model_config.get('model_name')
        }

        try:
            async with session.post(
                f"{self.base_url}/spend/calculate",
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.logger.warning(f"Cost calculation failed: {response.status}")
                    return {'cost': 0}
        except Exception as e:
            self.logger.error(f"Cost calculation error: {e}")
            return {'cost': 0}

    async def get_total_spend(self) -> Dict[str, Any]:
        """Get total spend using AI Gateway /key/info endpoint"""

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/key/info",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        self.logger.warning(f"Key info request failed: {response.status}")
                        return {'total_spend': 0}
        except Exception as e:
            self.logger.error(f"Key info error: {e}")
            return {'total_spend': 0}

    async def _store_usage_record(self, usage_data: Dict[str, Any]):
        """Store usage record in database for client monitoring"""

        # This would store in a new ai_usage_tracking table
        # for client billing and monitoring purposes

        try:
            # In full implementation, this would use SQLAlchemy
            # to store in ai_usage_tracking table

            self.logger.info(f"Stored usage record: {usage_data}")

        except Exception as e:
            self.logger.error(f"Failed to store usage record: {e}")

class AIProviderFactory:
    """Factory for creating AI providers"""

    @staticmethod
    def create_provider(config: AIProviderConfig) -> AIProviderInterface:
        """Create provider based on configuration"""

        if config.provider_type == "sentence_transformers":
            return SentenceTransformersProvider(config)
        elif config.provider_type == "openai":
            return OpenAIProvider(config)
        elif config.provider_type == "custom_gateway":
            return CustomGatewayProvider(config)
        else:
            raise ValueError(f"Unknown provider type: {config.provider_type}")
```

---

# Phase 3-3: Frontend AI Configuration Interface

**Duration**: 2 days
**Priority**: HIGH
**Dependencies**: Phase 3-2 completion

## 🎯 Objectives

1. **AI Configuration Hub**: Central frontend interface for AI model management
2. **User-Friendly Model Selection**: Business users can configure their AI experience
3. **Real-Time Testing**: Test AI models and see immediate results
4. **Performance Analytics**: Monitor AI usage, costs, and performance

## 📋 Frontend Implementation Tasks

### AI Configuration Menu (Frontend App)
```typescript
// services/frontend-app/src/components/AIConfiguration/

interface AIConfigurationProps {
  clientId: number;
}

// Main AI Configuration Hub
const AIConfigurationHub: React.FC<AIConfigurationProps> = ({ clientId }) => {
  return (
    <div className="ai-configuration-hub">
      <AIConfigurationTabs>
        <TabPanel label="AI Agents">
          <AIAgentConfiguration />
        </TabPanel>
        <TabPanel label="Embedding Models">
          <EmbeddingModelConfiguration />
        </TabPanel>
        <TabPanel label="Provider Management">
          <AIProviderManagement />
        </TabPanel>
        <TabPanel label="Testing & Analytics">
          <AITestingInterface />
        </TabPanel>
        <TabPanel label="Usage & Costs">
          <AIUsageMonitoring />
        </TabPanel>
      </AIConfigurationTabs>
    </div>
  );
};

// AI Agent Configuration Component
const AIAgentConfiguration: React.FC = () => {
  const [agentConfig, setAgentConfig] = useState<AIAgentConfig>({
    questionAnswering: {
      primaryModel: null,
      fallbackModel: null,
      responseStyle: 'detailed',
      confidenceThreshold: 0.8
    },
    insightGeneration: {
      analysisDepth: 'advanced',
      proactiveInsights: true,
      customPrompts: []
    },
    dashboardAI: {
      autoRefresh: true,
      anomalyDetection: true,
      predictiveAnalytics: true,
      narrativeGeneration: true
    }
  });

  return (
    <div className="ai-agent-config">
      <ConfigurationSection title="Question Answering">
        <ModelSelector
          label="Primary Model"
          value={agentConfig.questionAnswering.primaryModel}
          onChange={(model) => updateAgentConfig('questionAnswering.primaryModel', model)}
          capabilities={['text_generation', 'analysis']}
        />
        <ModelSelector
          label="Fallback Model"
          value={agentConfig.questionAnswering.fallbackModel}
          onChange={(model) => updateAgentConfig('questionAnswering.fallbackModel', model)}
          capabilities={['text_generation']}
        />
        <ResponseStyleSelector
          value={agentConfig.questionAnswering.responseStyle}
          onChange={(style) => updateAgentConfig('questionAnswering.responseStyle', style)}
        />
      </ConfigurationSection>

      <ConfigurationSection title="Dashboard AI">
        <ToggleSwitch
          label="Proactive Insights"
          checked={agentConfig.insightGeneration.proactiveInsights}
          onChange={(checked) => updateAgentConfig('insightGeneration.proactiveInsights', checked)}
        />
        <ToggleSwitch
          label="Anomaly Detection"
          checked={agentConfig.dashboardAI.anomalyDetection}
          onChange={(checked) => updateAgentConfig('dashboardAI.anomalyDetection', checked)}
        />
      </ConfigurationSection>
    </div>
  );
};

// Model Selection Component
const ModelSelector: React.FC<ModelSelectorProps> = ({
  label,
  value,
  onChange,
  capabilities
}) => {
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadAvailableModels();
  }, [capabilities]);

  const loadAvailableModels = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/ai/models/available', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capabilities })
      });
      const models = await response.json();
      setAvailableModels(models);
    } catch (error) {
      console.error('Failed to load models:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="model-selector">
      <label>{label}</label>
      <Select
        value={value}
        onChange={onChange}
        loading={loading}
        options={availableModels.map(model => ({
          value: model.name,
          label: `${model.name} (${model.provider})`,
          description: `${model.dimensions}d, $${model.cost_per_1k_tokens}/1K tokens`
        }))}
      />
      {value && (
        <ModelTestButton
          modelName={value}
          onTest={(result) => showTestResult(result)}
        />
      )}
    </div>
  );
};
```

### AI Provider Management Interface
```typescript
// AI Provider Management Component
const AIProviderManagement: React.FC = () => {
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [showAddProvider, setShowAddProvider] = useState(false);

  return (
    <div className="ai-provider-management">
      <div className="provider-list">
        {providers.map(provider => (
          <ProviderCard
            key={provider.id}
            provider={provider}
            onEdit={(provider) => editProvider(provider)}
            onDelete={(id) => deleteProvider(id)}
            onTest={(provider) => testProvider(provider)}
          />
        ))}
      </div>

      <Button onClick={() => setShowAddProvider(true)}>
        Add AI Provider
      </Button>

      {showAddProvider && (
        <AddProviderModal
          onSave={(provider) => saveProvider(provider)}
          onCancel={() => setShowAddProvider(false)}
          supportedProviders={[
            'sentence_transformers',
            'openai',
            'azure_openai',
            'google_gemini',
            'anthropic_claude',
            'custom_gateway'
          ]}
        />
      )}
    </div>
  );
};

// Add Provider Modal for Custom Gateway (Your Hackathon Models)
const AddProviderModal: React.FC<AddProviderModalProps> = ({
  onSave,
  onCancel,
  supportedProviders
}) => {
  const [providerType, setProviderType] = useState('');
  const [config, setConfig] = useState<ProviderConfig>({});

  const renderProviderSpecificFields = () => {
    switch (providerType) {
      case 'custom_gateway':
        return (
          <CustomGatewayFields
            config={config}
            onChange={setConfig}
            hackathonModels={loadHackathonModels()} // Load from your docs/hackathon
          />
        );
      case 'openai':
        return (
          <OpenAIFields
            config={config}
            onChange={setConfig}
          />
        );
      default:
        return null;
    }
  };

  return (
    <Modal title="Add AI Provider">
      <Form>
        <Select
          label="Provider Type"
          value={providerType}
          onChange={setProviderType}
          options={supportedProviders.map(provider => ({
            value: provider,
            label: formatProviderName(provider)
          }))}
        />

        {renderProviderSpecificFields()}

        <div className="modal-actions">
          <Button onClick={onCancel}>Cancel</Button>
          <Button
            onClick={() => onSave(config)}
            disabled={!isConfigValid(config)}
          >
            Save & Test
          </Button>
        </div>
      </Form>
    </Modal>
  );
};

// AI Usage Monitoring Component (integrates with AI Gateway endpoints)
const AIUsageMonitoring: React.FC = () => {
  const [usageData, setUsageData] = useState<AIUsageData>({});
  const [timeRange, setTimeRange] = useState('7d');
  const [loading, setLoading] = useState(false);

  const loadUsageData = async () => {
    setLoading(true);
    try {
      // Load internal usage tracking
      const response = await fetch(`/api/v1/ai/usage/summary?range=${timeRange}`);
      const data = await response.json();

      // Load AI Gateway key info using /key/info endpoint
      const gatewayResponse = await fetch('/api/v1/ai/gateway/key-info');
      const gatewayData = await gatewayResponse.json();

      setUsageData({
        ...data,
        gatewayTotalSpend: gatewayData.total_spend,
        gatewayKeyInfo: gatewayData
      });
    } catch (error) {
      console.error('Failed to load usage data:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ai-usage-monitoring">
      <div className="usage-summary">
        <MetricCard
          title="Total Cost (Internal)"
          value={`$${usageData.totalCost?.toFixed(2) || '0.00'}`}
          description="Tracked from request metadata"
        />
        <MetricCard
          title="Total Cost (Gateway)"
          value={`$${usageData.gatewayTotalSpend?.toFixed(2) || '0.00'}`}
          description="From /key/info endpoint"
        />
        <MetricCard
          title="Total Tokens"
          value={usageData.totalTokens?.toLocaleString() || '0'}
          description="Input + output tokens used"
        />
        <MetricCard
          title="Requests"
          value={usageData.totalRequests?.toLocaleString() || '0'}
          description="Total API requests made"
        />
      </div>

      <div className="gateway-integration">
        <h3>AI Gateway Integration</h3>
        <div className="gateway-endpoints">
          <EndpointCard
            endpoint="/key/info"
            description="Get API key information and total spend"
            usage="Used for overall cost tracking"
          />
          <EndpointCard
            endpoint="/spend/calculate"
            description="Calculate cost for specific requests"
            usage="Used for per-request cost tracking"
          />
          <EndpointCard
            endpoint="/embeddings"
            description="Generate embeddings with usage in response"
            usage="Returns token usage in 'usage' attribute"
          />
        </div>
      </div>
    </div>
  );
};
```

### AI Usage Tracking API Endpoints
```typescript
// services/backend-service/app/api/ai_usage.py

@router.get("/usage/summary")
async def get_usage_summary(
    range: str = "7d",
    user: User = Depends(require_authentication)
):
    """Get AI usage summary for client"""

    # Calculate date range
    end_date = datetime.now()
    if range == "1d":
        start_date = end_date - timedelta(days=1)
    elif range == "7d":
        start_date = end_date - timedelta(days=7)
    elif range == "30d":
        start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(days=90)

    # Query usage tracking table
    with get_db_session() as session:
        usage_records = session.query(AIUsageTracking).filter(
            AIUsageTracking.client_id == user.client_id,
            AIUsageTracking.created_at >= start_date
        ).all()

        # Calculate summary metrics
        total_cost = sum(record.cost for record in usage_records)
        total_tokens = sum(record.total_tokens for record in usage_records)
        total_requests = len(usage_records)

        # Provider breakdown
        provider_breakdown = {}
        for record in usage_records:
            if record.provider not in provider_breakdown:
                provider_breakdown[record.provider] = {
                    'cost': 0, 'tokens': 0, 'requests': 0
                }
            provider_breakdown[record.provider]['cost'] += record.cost
            provider_breakdown[record.provider]['tokens'] += record.total_tokens
            provider_breakdown[record.provider]['requests'] += 1

        return {
            'totalCost': float(total_cost),
            'totalTokens': total_tokens,
            'totalRequests': total_requests,
            'avgCostPerRequest': float(total_cost / total_requests) if total_requests > 0 else 0,
            'providerBreakdown': provider_breakdown,
            'dateRange': {'start': start_date.isoformat(), 'end': end_date.isoformat()}
        }

@router.get("/gateway/key-info")
async def get_gateway_key_info(
    user: User = Depends(require_authentication)
):
    """Get AI Gateway key information using /key/info endpoint"""

    # Load custom gateway configuration for client
    with get_db_session() as session:
        gateway_integration = session.query(Integration).filter(
            Integration.client_id == user.client_id,
            Integration.integration_type == 'ai_model',
            Integration.integration_subtype == 'gateway',
            Integration.active == True
        ).first()

        if not gateway_integration:
            return {'error': 'No AI Gateway configuration found'}

        # Use CustomGatewayUsageTracker to get key info
        config = AIProviderConfig(
            provider_type='custom_gateway',
            model_name='',
            credentials=gateway_integration.credentials,
            model_config={},
            performance_config={}
        )

        tracker = CustomGatewayUsageTracker(config)
        key_info = await tracker.get_total_spend()

        return key_info
```

---

# Phase 3-4: ETL AI Integration

**Duration**: 2 days
**Priority**: HIGH
**Dependencies**: Phase 3-3 completion

## 🎯 Objectives

1. **ETL AI Configuration**: Load AI configuration from database in ETL jobs
2. **Enhanced Text Extraction**: Smart text extraction from all data sources
3. **Real-Time Embedding Generation**: Generate embeddings during data processing
4. **Performance Optimization**: Batch processing for maximum efficiency

## 📋 ETL Implementation Tasks

### Enhanced Text Extractors
```python
# services/etl-service/app/core/text_extractors.py

class EnhancedTextExtractor:
    """Extract meaningful text content for embedding generation"""

    @staticmethod
    def extract_jira_text(issue_data: Dict) -> str:
        """Extract comprehensive text from Jira issue"""
        text_parts = []

        # Core fields with semantic context
        if issue_data.get('summary'):
            text_parts.append(f"Title: {issue_data['summary']}")

        if issue_data.get('description'):
            # Clean HTML/markdown from description
            clean_desc = EnhancedTextExtractor._clean_markup(issue_data['description'])
            text_parts.append(f"Description: {clean_desc}")

        # Issue type and priority context
        if issue_data.get('issuetype'):
            text_parts.append(f"Type: {issue_data['issuetype']}")

        if issue_data.get('priority'):
            text_parts.append(f"Priority: {issue_data['priority']}")

        # Custom fields with meaningful content
        for field_key, field_value in issue_data.items():
            if field_key.startswith('custom_field_') and field_value:
                if isinstance(field_value, str) and len(field_value) > 10:
                    clean_value = EnhancedTextExtractor._clean_markup(field_value)
                    text_parts.append(f"Field: {clean_value}")

        # Recent comments (most relevant)
        if issue_data.get('comments'):
            recent_comments = issue_data['comments'][-3:]  # Last 3 comments
            for comment in recent_comments:
                if comment.get('body'):
                    clean_comment = EnhancedTextExtractor._clean_markup(comment['body'])
                    text_parts.append(f"Comment: {clean_comment}")

        # Labels and components for categorization
        if issue_data.get('labels'):
            text_parts.append(f"Labels: {', '.join(issue_data['labels'])}")

        if issue_data.get('components'):
            components = [comp['name'] for comp in issue_data['components']]
            text_parts.append(f"Components: {', '.join(components)}")

        return " | ".join(text_parts)

    @staticmethod
    def extract_github_pr_text(pr_data: Dict) -> str:
        """Extract comprehensive text from GitHub PR"""
        text_parts = []

        if pr_data.get('title'):
            text_parts.append(f"Title: {pr_data['title']}")

        if pr_data.get('body'):
            clean_body = EnhancedTextExtractor._clean_markup(pr_data['body'])
            text_parts.append(f"Description: {clean_body}")

        # PR metadata for context
        if pr_data.get('state'):
            text_parts.append(f"State: {pr_data['state']}")

        # Recent review comments (most relevant)
        if pr_data.get('review_comments'):
            recent_comments = pr_data['review_comments'][-2:]  # Last 2 comments
            for comment in recent_comments:
                if comment.get('body'):
                    clean_comment = EnhancedTextExtractor._clean_markup(comment['body'])
                    text_parts.append(f"Review: {clean_comment}")

        # Labels for categorization
        if pr_data.get('labels'):
            labels = [label['name'] for label in pr_data['labels']]
            text_parts.append(f"Labels: {', '.join(labels)}")

        return " | ".join(text_parts)

    @staticmethod
    def extract_commit_text(commit_data: Dict) -> str:
        """Extract text from commit"""
        text_parts = []

        if commit_data.get('message'):
            # Extract meaningful commit message
            message = commit_data['message']
            # Take first line (summary) and first paragraph if available
            lines = message.split('\n')
            summary = lines[0]
            text_parts.append(f"Message: {summary}")

            # Add detailed description if available
            if len(lines) > 2 and lines[2].strip():
                description = lines[2].strip()[:200]  # Limit description
                text_parts.append(f"Details: {description}")

        # File changes context (limited but meaningful)
        if commit_data.get('files'):
            file_names = [f['filename'] for f in commit_data['files'][:3]]
            text_parts.append(f"Files: {', '.join(file_names)}")

            # Add change type context
            additions = sum(f.get('additions', 0) for f in commit_data['files'])
            deletions = sum(f.get('deletions', 0) for f in commit_data['files'])
            text_parts.append(f"Changes: +{additions} -{deletions}")

        return " | ".join(text_parts)

    @staticmethod
    def _clean_markup(text: str) -> str:
        """Clean HTML/Markdown markup from text"""
        if not text:
            return ""

        import re

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Remove Markdown formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
        text = re.sub(r'`(.*?)`', r'\1', text)        # Code
        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)  # Links

        # Clean excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Limit length
        if len(text) > 1000:
            text = text[:1000] + "..."

        return text
```

### AI-Enhanced ETL Jobs
```python
# services/etl-service/app/core/jobs/ai_enhanced_jira_job.py

from app.ai.ai_provider_framework import AIProviderFactory, AIProviderConfig
from app.core.text_extractors import EnhancedTextExtractor
from app.models.unified_models import Integration

class AIEnhancedJiraJob(JiraJob):
    """Jira job enhanced with AI embedding generation"""

    def __init__(self, client_id: int, config: dict):
        super().__init__(client_id, config)
        self.text_extractor = EnhancedTextExtractor()
        self.embedding_provider = None
        self.ai_config = None

    async def initialize_ai_provider(self):
        """Initialize AI provider based on client configuration"""

        # Load client AI configuration
        with self.database.get_read_session_context() as session:
            # Get embedding configuration for this client
            embedding_integration = session.query(Integration).filter(
                Integration.client_id == self.client_id,
                Integration.integration_type == 'ai_model',
                Integration.integration_subtype == 'embedding',
                Integration.active == True
            ).first()

            if embedding_integration:
                self.ai_config = AIProviderConfig(
                    provider_type=embedding_integration.configuration.get('provider'),
                    model_name=embedding_integration.model_config.get('model_name'),
                    credentials=embedding_integration.credentials,
                    model_config=embedding_integration.model_config,
                    performance_config=embedding_integration.performance_config
                )

                self.embedding_provider = AIProviderFactory.create_provider(self.ai_config)
                await self.embedding_provider.initialize()

                self.logger.info(f"Initialized AI provider: {self.ai_config.provider_type}")
            else:
                self.logger.warning(f"No embedding configuration found for client {self.client_id}")

    async def process_issue_batch(self, issue_batch: List[Dict]) -> List[Issue]:
        """Enhanced issue processing with embedding generation"""

        # Initialize AI provider if not already done
        if not self.embedding_provider:
            await self.initialize_ai_provider()

        # Extract text for all issues
        texts = []
        for issue_data in issue_batch:
            text = self.text_extractor.extract_jira_text(issue_data)
            texts.append(text)

        # Generate embeddings in batch (FAST!)
        embeddings = []
        if self.embedding_provider and texts:
            try:
                embeddings = await self.embedding_provider.generate_embeddings(texts)
                self.logger.info(f"Generated {len(embeddings)} embeddings for {len(texts)} issues")
            except Exception as e:
                self.logger.error(f"Embedding generation failed: {e}")
                # Continue without embeddings - graceful degradation

        # Process issues with embeddings
        processed_issues = []
        for i, issue_data in enumerate(issue_batch):
            issue = await self.process_single_issue(issue_data)

            # Add embedding to issue if available
            if i < len(embeddings):
                issue.embedding = embeddings[i]

            processed_issues.append(issue)

        return processed_issues
```

### Task 3.3: ETL Integration
**Duration**: 2 days  
**Priority**: HIGH  

#### Enhanced ETL Jobs with Embedding Generation
```python
# services/etl-service/app/core/jobs/enhanced_jira_job.py

from app.ai.embedding_service import EmbeddingService
from app.core.text_extractors import TextExtractor

class EnhancedJiraJob(JiraJob):
    """Jira job enhanced with embedding generation"""
    
    def __init__(self, client_id: int, config: dict):
        super().__init__(client_id, config)
        self.embedding_service = EmbeddingService(provider="sentence_transformers")
        self.text_extractor = TextExtractor()
    
    async def process_issue_batch(self, issue_batch: List[Dict]) -> List[Issue]:
        """Enhanced issue processing with embedding generation"""
        
        # Extract text for all issues
        texts = []
        for issue_data in issue_batch:
            text = self.text_extractor.extract_jira_text(issue_data)
            texts.append(text)
        
        # Generate embeddings in batch (FAST!)
        embeddings = await self.embedding_service.generate_embeddings_batch(texts)
        
        # Process issues with embeddings
        processed_issues = []
        for i, issue_data in enumerate(issue_batch):
            issue = await self.process_single_issue(issue_data)
            
            # Add embedding to issue
            if i < len(embeddings):
                issue.embedding = embeddings[i]
            
            processed_issues.append(issue)
        
        return processed_issues

### Task 3.4: Backfill Migration for Existing Data
**Duration**: 1 day
**Priority**: MEDIUM

#### Backfill Script for Historical Data
```python
# services/backend-service/scripts/migrations/0006_backfill_embeddings.py

import asyncio
from sqlalchemy.orm import Session
from app.ai.embedding_service import EmbeddingService
from app.core.text_extractors import TextExtractor
from app.core.database import get_db_session

async def backfill_embeddings():
    """Backfill embeddings for all existing data"""

    embedding_service = EmbeddingService(provider="sentence_transformers")
    text_extractor = TextExtractor()

    with get_db_session() as session:

        # Backfill Jira Issues
        print("🔄 Backfilling Jira issue embeddings...")
        issues = session.query(Issue).filter(Issue.embedding.is_(None)).all()

        batch_size = 100
        for i in range(0, len(issues), batch_size):
            batch = issues[i:i + batch_size]

            # Extract texts
            texts = []
            for issue in batch:
                text = text_extractor.extract_jira_text({
                    'summary': issue.summary,
                    'description': issue.description,
                    'labels': issue.labels
                })
                texts.append(text)

            # Generate embeddings
            embeddings = await embedding_service.generate_embeddings_batch(texts)

            # Update database
            for j, issue in enumerate(batch):
                if j < len(embeddings):
                    issue.embedding = embeddings[j]

            session.commit()
            print(f"   ✅ Processed {len(batch)} issues (batch {i//batch_size + 1})")

        # Backfill Pull Requests
        print("🔄 Backfilling PR embeddings...")
        prs = session.query(PullRequest).filter(PullRequest.embedding.is_(None)).all()

        for i in range(0, len(prs), batch_size):
            batch = prs[i:i + batch_size]

            texts = []
            for pr in batch:
                text = text_extractor.extract_github_pr_text({
                    'title': pr.title,
                    'body': pr.body
                })
                texts.append(text)

            embeddings = await embedding_service.generate_embeddings_batch(texts)

            for j, pr in enumerate(batch):
                if j < len(embeddings):
                    pr.embedding = embeddings[j]

            session.commit()
            print(f"   ✅ Processed {len(batch)} PRs (batch {i//batch_size + 1})")

        # Backfill Commits
        print("🔄 Backfilling commit embeddings...")
        commits = session.query(Commit).filter(Commit.embedding.is_(None)).all()

        for i in range(0, len(commits), batch_size):
            batch = commits[i:i + batch_size]

            texts = []
            for commit in batch:
                text = text_extractor.extract_commit_text({
                    'message': commit.message
                })
                texts.append(text)

            embeddings = await embedding_service.generate_embeddings_batch(texts)

            for j, commit in enumerate(batch):
                if j < len(embeddings):
                    commit.embedding = embeddings[j]

            session.commit()
            print(f"   ✅ Processed {len(batch)} commits (batch {i//batch_size + 1})")

if __name__ == "__main__":
    asyncio.run(backfill_embeddings())
```

### Task 3.5: Vector Quality Assurance
**Duration**: 1 day
**Priority**: MEDIUM

#### Embedding Quality Validation
```python
# services/backend-service/app/ai/vector_quality.py

import numpy as np
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session

class VectorQualityAssurance:
    """Ensure embedding quality and consistency"""

    @staticmethod
    def validate_embedding_quality(embeddings: List[List[float]]) -> Dict[str, float]:
        """Validate embedding quality metrics"""

        if not embeddings:
            return {"status": "error", "message": "No embeddings provided"}

        embeddings_array = np.array(embeddings)

        # Check dimensions consistency
        dimensions = [len(emb) for emb in embeddings]
        dimension_consistency = len(set(dimensions)) == 1

        # Check for zero vectors (usually indicates errors)
        zero_vectors = np.sum(np.sum(embeddings_array == 0, axis=1) == embeddings_array.shape[1])

        # Check magnitude distribution
        magnitudes = np.linalg.norm(embeddings_array, axis=1)
        avg_magnitude = np.mean(magnitudes)
        magnitude_std = np.std(magnitudes)

        # Check for duplicate vectors
        unique_embeddings = len(np.unique(embeddings_array, axis=0))
        duplicate_rate = 1 - (unique_embeddings / len(embeddings))

        return {
            "total_embeddings": len(embeddings),
            "dimension_consistency": dimension_consistency,
            "expected_dimensions": dimensions[0] if dimensions else 0,
            "zero_vectors": int(zero_vectors),
            "zero_vector_rate": zero_vectors / len(embeddings),
            "avg_magnitude": float(avg_magnitude),
            "magnitude_std": float(magnitude_std),
            "duplicate_rate": float(duplicate_rate),
            "quality_score": float(1.0 - (zero_vectors / len(embeddings)) - duplicate_rate)
        }

    @staticmethod
    def find_similar_content(
        query_embedding: List[float],
        session: Session,
        table_name: str = "issues",
        limit: int = 5
    ) -> List[Tuple[int, float]]:
        """Find similar content using vector similarity"""

        # This would use pgvector similarity search
        # Example for issues table
        if table_name == "issues":
            query = f"""
                SELECT id, embedding <-> %s::vector AS distance
                FROM issues
                WHERE embedding IS NOT NULL
                ORDER BY distance
                LIMIT %s
            """

            result = session.execute(query, (query_embedding, limit))
            return [(row.id, row.distance) for row in result]

        return []

## 🎯 Performance Benchmarks

### Expected Performance (Sentence Transformers)
- **Speed**: 1000+ embeddings/second on CPU
- **Memory**: ~2GB for model + processing
- **Quality**: 85-90% of OpenAI quality for most use cases
- **Cost**: $0 (no API calls)

### Expected Performance (OpenAI with Batching)
- **Speed**: 100+ embeddings/second
- **Quality**: 95%+ (industry standard)
- **Cost**: ~$0.0001 per 1K tokens
- **Reliability**: 99.9% uptime

## 📊 Success Metrics

### Technical Metrics
- ✅ **Embedding Generation Speed**: >500 embeddings/second
- ✅ **Quality Score**: >0.85 (low zero vectors, low duplicates)
- ✅ **Coverage**: 100% of text content has embeddings
- ✅ **Consistency**: All embeddings have correct dimensions

### Business Metrics
- ✅ **Search Relevance**: Semantic search returns relevant results
- ✅ **Performance**: ETL jobs complete within time windows
- ✅ **Cost Efficiency**: Embedding generation cost <$10/month per client

## 🔧 Dependencies

### New Requirements
```txt
# Add to requirements/backend-service.txt
sentence-transformers>=2.2.2
torch>=2.0.0
numpy>=1.24.0

# Add to requirements/etl-service.txt
sentence-transformers>=2.2.2
torch>=2.0.0
```

### Optional (for OpenAI approach)
```txt
openai>=1.0.0
tiktoken>=0.5.0
```

## 🚀 Implementation Priority

1. **Day 1-2**: Embedding service with Sentence Transformers (fastest path)
2. **Day 3**: ETL integration for new data
3. **Day 4**: Backfill script for existing data
4. **Day 5**: Quality assurance and optimization
5. **Day 6**: Performance testing and documentation

---

# Phase 3-6: AI Agent Foundation

**Duration**: 2 days
**Priority**: MEDIUM
**Dependencies**: Phase 3-5 completion

## 🎯 Objectives

1. **Dashboard AI Agents**: Foundation for proactive insights and anomaly detection
2. **Q&A Agent Framework**: Prepare infrastructure for natural language queries
3. **Agent Configuration**: User-configurable AI agent behavior
4. **Integration Points**: Connect AI agents with frontend dashboards

## 📋 AI Agent Implementation

### Dashboard AI Agent Framework
```python
# services/backend-service/app/ai/dashboard_agents.py

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class InsightResult:
    """Result from AI insight generation"""
    insight_type: str  # 'anomaly', 'trend', 'recommendation', 'alert'
    title: str
    description: str
    confidence: float
    data_points: List[Dict[str, Any]]
    suggested_actions: List[str]
    priority: str  # 'low', 'medium', 'high', 'critical'

class DashboardAIAgent:
    """AI agent for generating dashboard insights"""

    def __init__(self, client_id: int, user_config: Dict[str, Any]):
        self.client_id = client_id
        self.config = user_config
        self.logger = logging.getLogger(__name__)

    async def generate_proactive_insights(
        self,
        dashboard_data: Dict[str, Any]
    ) -> List[InsightResult]:
        """Generate proactive insights from dashboard data"""

        insights = []

        # Anomaly detection insights
        if self.config.get('anomaly_detection', True):
            anomaly_insights = await self._detect_anomalies(dashboard_data)
            insights.extend(anomaly_insights)

        # Trend analysis insights
        if self.config.get('trend_analysis', True):
            trend_insights = await self._analyze_trends(dashboard_data)
            insights.extend(trend_insights)

        # Performance recommendations
        if self.config.get('recommendations', True):
            recommendation_insights = await self._generate_recommendations(dashboard_data)
            insights.extend(recommendation_insights)

        return insights

    async def _detect_anomalies(self, data: Dict[str, Any]) -> List[InsightResult]:
        """Detect anomalies in dashboard metrics"""
        insights = []

        # Example: Deployment frequency anomaly
        if 'deployment_frequency' in data:
            current_freq = data['deployment_frequency']['current']
            historical_avg = data['deployment_frequency']['historical_avg']

            if current_freq < historical_avg * 0.7:  # 30% drop
                insights.append(InsightResult(
                    insight_type='anomaly',
                    title='Deployment Frequency Drop Detected',
                    description=f'Deployment frequency has dropped {((historical_avg - current_freq) / historical_avg * 100):.1f}% below historical average',
                    confidence=0.85,
                    data_points=[
                        {'metric': 'current_frequency', 'value': current_freq},
                        {'metric': 'historical_average', 'value': historical_avg}
                    ],
                    suggested_actions=[
                        'Review recent changes to deployment pipeline',
                        'Check for blockers in development process',
                        'Analyze team capacity and workload'
                    ],
                    priority='medium'
                ))

        return insights

    async def _analyze_trends(self, data: Dict[str, Any]) -> List[InsightResult]:
        """Analyze trends in metrics"""
        insights = []

        # Example: Lead time trend analysis
        if 'lead_time_trend' in data:
            trend_data = data['lead_time_trend']

            if len(trend_data) >= 4:  # Need at least 4 data points
                recent_avg = sum(trend_data[-2:]) / 2
                older_avg = sum(trend_data[:2]) / 2

                if recent_avg > older_avg * 1.2:  # 20% increase
                    insights.append(InsightResult(
                        insight_type='trend',
                        title='Lead Time Increasing Trend',
                        description=f'Lead time has increased {((recent_avg - older_avg) / older_avg * 100):.1f}% over recent periods',
                        confidence=0.75,
                        data_points=[
                            {'metric': 'recent_average', 'value': recent_avg},
                            {'metric': 'baseline_average', 'value': older_avg}
                        ],
                        suggested_actions=[
                            'Review code review process efficiency',
                            'Analyze testing and CI/CD pipeline performance',
                            'Consider team training or process improvements'
                        ],
                        priority='medium'
                    ))

        return insights

class QAAgent:
    """Q&A agent for natural language queries"""

    def __init__(self, client_id: int, ai_provider_config: Dict[str, Any]):
        self.client_id = client_id
        self.ai_config = ai_provider_config
        self.logger = logging.getLogger(__name__)

    async def answer_question(
        self,
        question: str,
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Answer natural language questions about data"""

        # This would integrate with the AI provider framework
        # to generate natural language responses

        response = {
            'answer': 'Based on your data...',
            'confidence': 0.85,
            'data_sources': ['issues', 'pull_requests', 'deployments'],
            'follow_up_questions': [
                'Would you like to see a breakdown by team?',
                'Should I analyze the trend over time?'
            ]
        }

        return response
```

### AI Agent API Endpoints
```python
# services/backend-service/app/api/ai_agents.py

from fastapi import APIRouter, Depends, HTTPException
from app.ai.dashboard_agents import DashboardAIAgent, QAAgent
from app.auth.auth_service import require_authentication

router = APIRouter()

@router.post("/dashboard/insights")
async def generate_dashboard_insights(
    dashboard_data: Dict[str, Any],
    user: User = Depends(require_authentication)
):
    """Generate AI insights for dashboard"""

    # Load client AI preferences
    client_config = await load_client_ai_preferences(user.client_id, 'dashboard_ai')

    agent = DashboardAIAgent(user.client_id, client_config)
    insights = await agent.generate_proactive_insights(dashboard_data)

    return {
        'insights': [insight.__dict__ for insight in insights],
        'generated_at': datetime.now().isoformat(),
        'agent_config': client_config
    }

@router.post("/qa/ask")
async def ask_question(
    question: str,
    context: Optional[Dict[str, Any]] = None,
    user: User = Depends(require_authentication)
):
    """Ask natural language question"""

    # Load client AI preferences for Q&A
    ai_config = await load_client_ai_preferences(user.client_id, 'qa_agent')

    agent = QAAgent(user.client_id, ai_config)
    response = await agent.answer_question(question, context)

    return response
```

---

# Phase 3-7: Testing & Documentation

**Duration**: 1 day
**Priority**: MEDIUM
**Dependencies**: Phase 3-6 completion

## 🎯 Objectives

1. **Comprehensive Testing**: Unit tests, integration tests, performance tests
2. **Documentation Updates**: Update all service documentation
3. **Performance Validation**: Confirm 10x performance improvement
4. **User Acceptance**: Validate frontend AI configuration interface

## 📋 Testing Implementation

### Performance Tests
```python
# tests/test_ai_performance.py

import pytest
import asyncio
import time
from app.ai.ai_provider_framework import SentenceTransformersProvider, AIProviderConfig

@pytest.mark.asyncio
async def test_embedding_performance():
    """Test embedding generation performance"""

    config = AIProviderConfig(
        provider_type="sentence_transformers",
        model_name="all-mpnet-base-v2",
        credentials={},
        model_config={"model_name": "all-mpnet-base-v2"},
        performance_config={"batch_size": 100}
    )

    provider = SentenceTransformersProvider(config)
    await provider.initialize()

    # Test with 1000 sample texts
    test_texts = [f"Sample text for embedding test {i}" for i in range(1000)]

    start_time = time.time()
    embeddings = await provider.generate_embeddings(test_texts)
    end_time = time.time()

    duration = end_time - start_time
    embeddings_per_second = len(test_texts) / duration

    # Assert performance target
    assert embeddings_per_second > 500, f"Performance too slow: {embeddings_per_second:.1f} embeddings/second"
    assert len(embeddings) == len(test_texts), "Missing embeddings"
    assert all(len(emb) == 768 for emb in embeddings), "Incorrect embedding dimensions"

    print(f"✅ Performance test passed: {embeddings_per_second:.1f} embeddings/second")

@pytest.mark.asyncio
async def test_ai_configuration_integration():
    """Test AI configuration loading and usage"""

    # Test configuration loading from database
    # Test provider initialization
    # Test fallback behavior
    pass

@pytest.mark.asyncio
async def test_dashboard_ai_agents():
    """Test dashboard AI agent functionality"""

    # Test insight generation
    # Test anomaly detection
    # Test trend analysis
    pass
```

## 📊 Final Success Metrics

### Performance Metrics
- ✅ **Embedding Speed**: >1000 embeddings/second (vs ~50 in hackathon)
- ✅ **API Response Time**: <200ms for AI configuration endpoints
- ✅ **Memory Usage**: <4GB for embedding service
- ✅ **Quality Score**: >0.85 for generated embeddings

### Business Metrics
- ✅ **User Adoption**: Frontend AI configuration interface usage
- ✅ **Cost Efficiency**: <$20/month per client for AI operations
- ✅ **Search Quality**: Semantic search relevance improvement
- ✅ **Agent Insights**: Dashboard AI generates actionable insights

### Technical Metrics
- ✅ **Database Coverage**: 100% of text content has embeddings
- ✅ **Provider Flexibility**: Support for 5+ AI providers
- ✅ **Configuration Options**: User-friendly model selection
- ✅ **Fallback Reliability**: Graceful degradation when providers fail

## 🎯 Phase 3 Completion Criteria

1. **Database Schema**: All AI configuration tables created and indexed
2. **Backend Services**: AI provider framework and embedding service implemented
3. **Frontend Interface**: AI configuration hub fully functional
4. **ETL Integration**: Real-time embedding generation in data pipelines
5. **Vector Population**: All historical data has embeddings
6. **AI Agents**: Foundation for dashboard insights and Q&A
7. **Performance**: 10x improvement over hackathon approach achieved
8. **Documentation**: All services updated with AI capabilities

This comprehensive Phase 3 transforms the platform from basic analytics to intelligent, AI-powered insights with user-configurable AI models and high-performance vector generation! 🚀
