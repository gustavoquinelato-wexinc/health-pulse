# Integration Management System

## 🎯 Overview

The Integration Management System provides a comprehensive interface for managing external system connections including data sources (Jira, GitHub) and AI providers (WEX AI Gateway, OpenAI, Azure). The system supports tenant-based isolation, file upload for logos, and conditional configuration based on integration type.

## 🏗️ Architecture

### Database Schema

The `integrations` table serves as the unified configuration store for all external systems:

```sql
CREATE TABLE integrations (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,           -- 'jira', 'github', 'wex_ai_gateway'
    type VARCHAR(50) NOT NULL,               -- 'data_source', 'ai_provider', 'notification'
    username VARCHAR,
    password VARCHAR,                        -- Encrypted using SECRET_KEY
    base_url TEXT,
    base_search VARCHAR,                     -- Search filters for data sources
    model VARCHAR(100),                      -- AI model name
    
    -- JSON configuration columns
    model_config JSONB DEFAULT '{}',        -- AI model parameters
    provider_metadata JSONB DEFAULT '{}',   -- Provider-specific settings
    cost_config JSONB DEFAULT '{}',         -- Cost tracking and limits
    fallback_integration_id INTEGER,        -- FK to fallback integration
    logo_filename VARCHAR(255),             -- Tenant-specific logo file
    
    -- BaseEntity fields
    tenant_id INTEGER NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Tenant-Based Asset Organization

Integration logos are organized by tenant for proper isolation:

```
/assets/
├── wex/
│   ├── integrations/
│   │   ├── jira.svg
│   │   ├── github.svg
│   │   └── wex-ai-gateway.svg
│   └── wex-logo.png
├── apple/
│   └── integrations/
│       └── [tenant-specific logos]
└── google/
    └── integrations/
        └── [tenant-specific logos]
```

## 🔧 API Endpoints

### Integration CRUD Operations

#### GET /api/v1/admin/integrations
Returns list of integrations for current tenant.

**Response:**
```json
[
  {
    "id": 1,
    "name": "jira",
    "integration_type": "data_source",
    "base_url": "https://company.atlassian.net",
    "username": "api_user",
    "model": null,
    "logo_filename": "jira.svg",
    "active": true,
    "last_sync_at": "2024-01-15T10:30:00Z"
  }
]
```

#### GET /api/v1/admin/integrations/{id}
Returns detailed integration configuration for editing.

**Response:**
```json
{
  "id": 1,
  "name": "wex_ai_gateway",
  "integration_type": "ai_provider",
  "base_url": "https://ai-gateway.wex.com",
  "username": null,
  "base_search": null,
  "model": "gpt-4o-mini",
  "model_config": {
    "temperature": 0.3,
    "max_tokens": 700
  },
  "provider_metadata": {
    "region": "us-east-1",
    "endpoint": "custom"
  },
  "cost_config": {
    "max_monthly_cost": 1000,
    "cost_per_token": 0.0001
  },
  "fallback_integration_id": 2,
  "logo_filename": "wex-ai-gateway.svg",
  "password_masked": "••••••••••••••••",
  "active": true
}
```

#### POST /api/v1/admin/integrations
Creates a new integration.

**Request:**
```json
{
  "provider": "openai",
  "type": "ai_provider",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o-mini",
  "model_config": {
    "temperature": 0.7,
    "max_tokens": 1000
  },
  "cost_config": {
    "monthly_limit": 500.00
  },
  "active": true
}
```

#### PUT /api/v1/admin/integrations/{id}
Updates an existing integration.

#### POST /api/v1/admin/integrations/{id}/logo
Uploads a logo file for an integration.

**Request:** Multipart form with image file
**Response:**
```json
{
  "message": "Logo uploaded successfully",
  "logo_filename": "openai.svg",
  "integration_id": 1
}
```

## 🎨 Frontend Interface

### Integration Management Page

The integration management interface (`/integrations`) provides:

- **Visual Integration Table**: Shows logos, names, types, and status
- **Create/Edit Modal**: Conditional fields based on integration type
- **File Upload**: Logo management with tenant isolation
- **Real-time Validation**: JSON validation for AI provider fields

### Conditional Field Display

#### Data Source Integrations
- Provider (text input)
- Type (dropdown: data_source, ai_provider, notification)
- Base URL
- Username
- Password/Token
- Base Search (optional filter)
- Logo File Upload
- Active status

#### AI Provider Integrations
All data source fields plus:
- **Model**: AI model name (e.g., "gpt-4o-mini")
- **Model Configuration**: JSON for model parameters
- **Provider Metadata**: JSON for provider-specific settings
- **Cost Configuration**: JSON for cost tracking and limits
- **Fallback Integration**: Dropdown of other AI integrations

### Form Validation

- **JSON Validation**: Real-time validation of JSON fields with error messages
- **File Validation**: Image files only, max 5MB
- **Required Fields**: Provider, type, and base_url are required
- **Unique Constraints**: One integration per provider per tenant

## 🔐 Security Features

### Authentication & Authorization
- **Tenant Isolation**: All operations scoped to user's tenant
- **Admin Access**: Requires admin role for integration management
- **Password Encryption**: All passwords encrypted using SECRET_KEY

### File Upload Security
- **File Type Validation**: Only image files accepted
- **Size Limits**: Maximum 5MB file size
- **Path Security**: No path traversal, controlled naming
- **Tenant Scoping**: Files isolated by tenant folder

## 🔄 Integration Types

### Data Sources
- **Jira**: Issue tracking and project management
- **GitHub**: Code repositories and development metrics
- **Custom**: Any REST API data source

### AI Providers
- **WEX AI Gateway**: Internal AI service
- **OpenAI**: GPT models and embeddings
- **Azure OpenAI**: Enterprise AI services
- **Custom**: Any AI API provider

### Configuration Examples

#### Jira Integration
```json
{
  "provider": "jira",
  "type": "data_source",
  "base_url": "https://company.atlassian.net",
  "username": "api_user@company.com",
  "password": "encrypted_token",
  "base_search": "project in (DEV,QA,PROD)"
}
```

#### AI Provider Integration
```json
{
  "provider": "wex_ai_gateway",
  "type": "ai_provider",
  "base_url": "https://ai-gateway.wex.com",
  "model": "gpt-4o-mini",
  "model_config": {
    "temperature": 0.3,
    "max_tokens": 700,
    "top_p": 0.9
  },
  "provider_metadata": {
    "region": "us-east-1",
    "deployment": "production"
  },
  "cost_config": {
    "max_monthly_cost": 1000,
    "cost_per_token": 0.0001,
    "alert_threshold": 0.8
  },
  "fallback_integration_id": 2
}
```

## 📊 Monitoring & Analytics

### Integration Status
- **Last Sync**: Timestamp of last successful data sync
- **Active Status**: Enable/disable integrations
- **Health Checks**: Connection validation (planned)

### Usage Tracking
- **API Calls**: Track usage for cost management
- **Error Rates**: Monitor integration reliability
- **Performance**: Response time tracking

## 🚀 Future Enhancements

### Planned Features
- **Connection Testing**: Real-time connectivity validation
- **Usage Analytics**: Detailed usage and cost reporting
- **Webhook Support**: Real-time data updates
- **Custom Connectors**: Plugin system for new integrations
- **Backup/Restore**: Configuration backup and migration tools

### AI Integration Roadmap
- **Model Performance**: Track AI model accuracy and performance
- **Cost Optimization**: Automatic cost optimization recommendations
- **Multi-Model**: Support for multiple AI models per provider
- **Custom Models**: Integration with custom-trained models

---

**Related Documentation:**
- [Architecture Guide](architecture.md) - System design and multi-tenancy
- [Security & Authentication](security-authentication.md) - Security implementation
- [Jobs & Orchestration](jobs-orchestration.md) - ETL job management
- [System Settings](system-settings.md) - Configuration reference
