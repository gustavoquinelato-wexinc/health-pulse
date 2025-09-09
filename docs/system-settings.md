# System Settings Guide

**Configuration Reference & Settings Management**

This document provides a comprehensive reference for all system settings in the Pulse Platform, including their purposes, valid values, and configuration options.

## 🎛️ Settings Architecture

### Settings Storage

All system settings are stored in the `system_settings` table with client-specific isolation:

```sql
CREATE TABLE system_settings (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    setting_key VARCHAR(255) NOT NULL,
    setting_value TEXT,
    setting_type VARCHAR(50) DEFAULT 'string',
    encrypted BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, setting_key)
);
```

### Setting Types

#### Data Types
- **string**: Text values (default)
- **integer**: Numeric values
- **boolean**: True/false values
- **json**: Complex structured data
- **encrypted**: Sensitive data (API keys, passwords)

#### Access Patterns
```python
# Reading settings
theme_mode = SettingsManager.get_setting("theme_mode", "light", client_id)
color_schema = SettingsManager.get_setting("color_schema_mode", "default", client_id)

# Writing settings
SettingsManager.set_setting("theme_mode", "dark", client_id)
SettingsManager.set_setting("custom_colors", color_data, client_id, "json")
```

## 🎨 UI & Branding Settings

### Theme Configuration

#### theme_mode
- **Purpose**: Controls light/dark mode preference per user
- **Type**: string (stored in users table, not system_settings)
- **Valid Values**: "light", "dark"
- **Default**: "light"
- **Scope**: User-specific preference affecting UI across frontend and ETL service
- **Storage**: `users.theme_mode` column
- **API**: `/api/v1/user/theme-mode` (user-specific, not admin)
- **Example**: `"dark"`

#### color_schema_mode
- **Purpose**: Determines which color schema to use
- **Type**: string
- **Valid Values**: "default", "custom"
- **Default**: "default"
- **Scope**: Controls whether to use default colors or custom client colors
- **Example**: `"custom"`

#### custom_colors
- **Purpose**: Client-specific color palette for branding
- **Type**: json
- **Structure**:
```json
{
  "primary": "#C8102E",
  "secondary": "#253746", 
  "accent": "#00C7B1",
  "neutral": "#A2DDF8",
  "warning": "#FFBF3F"
}
```
- **Default**: null (uses default colors)
- **Scope**: Applied when color_schema_mode is "custom"

### Tenant Branding

#### tenant_logo_filename
- **Purpose**: Filename of the tenant's logo image
- **Type**: string
- **Valid Values**: Any valid filename with extension
- **Default**: null
- **Storage**: Logo files stored in both frontend and ETL service static folders
- **Example**: `"wex_logo.png"`

#### tenant_name_display
- **Purpose**: Display name for the tenant in the UI
- **Type**: string
- **Valid Values**: Any string
- **Default**: Uses tenant.name from tenants table
- **Scope**: Shown in headers, titles, and branding areas
- **Example**: `"WEX Inc."`

## 🔧 Integration Settings

### GitHub Configuration

#### github_organization
- **Purpose**: GitHub organization name for data collection
- **Type**: string
- **Valid Values**: Valid GitHub organization name
- **Default**: null
- **Required**: Yes (for GitHub job functionality)
- **Example**: `"wex-inc"`

#### github_token
- **Purpose**: GitHub Personal Access Token for API access
- **Type**: encrypted
- **Valid Values**: Valid GitHub PAT with appropriate permissions
- **Default**: null
- **Required**: Yes (for GitHub job functionality)
- **Permissions Needed**: repo, read:org, read:user
- **Example**: `"ghp_xxxxxxxxxxxxxxxxxxxx"`

#### github_rate_limit_buffer
- **Purpose**: Buffer percentage for GitHub API rate limiting
- **Type**: integer
- **Valid Values**: 1-50 (percentage)
- **Default**: 10
- **Scope**: Prevents hitting GitHub API rate limits
- **Example**: `15`

### Jira Configuration

#### jira_base_url
- **Purpose**: Base URL for Jira instance
- **Type**: string
- **Valid Values**: Valid HTTPS URL
- **Default**: null
- **Required**: Yes (for Jira job functionality)
- **Example**: `"https://wexinc.atlassian.net"`

#### jira_email
- **Purpose**: Email address for Jira API authentication
- **Type**: string
- **Valid Values**: Valid email address
- **Default**: null
- **Required**: Yes (for Jira job functionality)
- **Example**: `"admin@wexinc.com"`

#### jira_api_token
- **Purpose**: Jira API token for authentication
- **Type**: encrypted
- **Valid Values**: Valid Jira API token
- **Default**: null
- **Required**: Yes (for Jira job functionality)
- **Example**: `"ATATT3xFfGF0..."`

#### jira_base_search (Integration Configuration)
- **Purpose**: JQL search criteria for Jira data collection (stored in integrations table)
- **Type**: string
- **Valid Values**: Valid JQL syntax including project filtering
- **Default**: "project in (BDP,BEN,BEX,BST,CDB,CDH,EPE,FG,HBA,HDO,HDS)"
- **Example**: `"project in (PROJ1,PROJ2) AND labels = 'urgent'"`
- **Note**: Replaces the deprecated separate projects column for better JQL flexibility

## ⚙️ Job Configuration Settings

### Orchestrator Settings

#### orchestrator_enabled
- **Purpose**: Enable/disable automatic job orchestration
- **Type**: boolean
- **Valid Values**: true, false
- **Default**: true
- **Scope**: Controls whether orchestrator runs automatically
- **Example**: `true`

#### orchestrator_interval_minutes
- **Purpose**: Interval between orchestrator runs
- **Type**: integer
- **Valid Values**: 5-1440 (5 minutes to 24 hours)
- **Default**: 15
- **Scope**: How often the orchestrator checks and schedules jobs
- **Example**: `30`

### GitHub Job Settings

#### github_job_interval_hours
- **Purpose**: Interval between GitHub job runs
- **Type**: integer
- **Valid Values**: 1-168 (1 hour to 1 week)
- **Default**: 4
- **Scope**: How often GitHub data is refreshed
- **Example**: `6`

#### github_job_fast_recovery_minutes
- **Purpose**: Fast recovery interval when GitHub job is PENDING
- **Type**: integer
- **Valid Values**: 5-120 (5 minutes to 2 hours)
- **Default**: 30
- **Scope**: Quick retry for pending GitHub jobs
- **Example**: `15`

### Jira Job Settings

#### jira_job_interval_hours
- **Purpose**: Interval between Jira job runs
- **Type**: integer
- **Valid Values**: 1-168 (1 hour to 1 week)
- **Default**: 6
- **Scope**: How often Jira data is refreshed
- **Example**: `8`

#### jira_job_fast_recovery_minutes
- **Purpose**: Fast recovery interval when Jira job is PENDING
- **Type**: integer
- **Valid Values**: 5-120 (5 minutes to 2 hours)
- **Default**: 60
- **Scope**: Quick retry for pending Jira jobs
- **Example**: `45`

## 📊 Analytics & Metrics Settings

### DORA Metrics Configuration

#### dora_lead_time_calculation
- **Purpose**: Method for calculating lead time
- **Type**: string
- **Valid Values**: "first_commit", "pr_created", "pr_approved"
- **Default**: "first_commit"
- **Scope**: Determines starting point for lead time calculation
- **Example**: `"pr_created"`

#### dora_deployment_detection
- **Purpose**: Method for detecting deployments
- **Type**: string
- **Valid Values**: "releases", "tags", "merge_to_main"
- **Default**: "releases"
- **Scope**: How deployments are identified in GitHub data
- **Example**: `"tags"`

#### dora_change_failure_threshold_hours
- **Purpose**: Time window to consider a deployment failure
- **Type**: integer
- **Valid Values**: 1-168 (1 hour to 1 week)
- **Default**: 24
- **Scope**: How long after deployment to look for failure indicators
- **Example**: `48`

### Dashboard Settings

#### dashboard_refresh_interval_seconds
- **Purpose**: Auto-refresh interval for dashboard data
- **Type**: integer
- **Valid Values**: 30-3600 (30 seconds to 1 hour)
- **Default**: 300 (5 minutes)
- **Scope**: How often dashboard data refreshes automatically
- **Example**: `180`

#### dashboard_default_date_range_days
- **Purpose**: Default date range for dashboard metrics
- **Type**: integer
- **Valid Values**: 7-365 (1 week to 1 year)
- **Default**: 30
- **Scope**: Initial date range shown on dashboard load
- **Example**: `90`

## 🔒 Security Settings

### Authentication Configuration

#### jwt_expiration_minutes
- **Purpose**: JWT token expiration time
- **Type**: integer
- **Valid Values**: 15-1440 (15 minutes to 24 hours)
- **Default**: 60
- **Scope**: How long JWT tokens remain valid
- **Example**: `120`

#### session_timeout_hours
- **Purpose**: User session timeout
- **Type**: integer
- **Valid Values**: 1-168 (1 hour to 1 week)
- **Default**: 24
- **Scope**: How long user sessions remain active
- **Example**: `8`

#### max_failed_login_attempts
- **Purpose**: Maximum failed login attempts before lockout
- **Type**: integer
- **Valid Values**: 3-10
- **Default**: 5
- **Scope**: Account lockout threshold
- **Example**: `3`

### API Security

#### api_rate_limit_per_minute
- **Purpose**: API requests per minute per user
- **Type**: integer
- **Valid Values**: 10-1000
- **Default**: 100
- **Scope**: Rate limiting for API endpoints
- **Example**: `200`

#### api_rate_limit_burst
- **Purpose**: Burst allowance for API rate limiting
- **Type**: integer
- **Valid Values**: 5-100
- **Default**: 20
- **Scope**: Additional requests allowed in burst
- **Example**: `50`

## 🗄️ Database Settings

### Connection Configuration

#### db_connection_pool_size
- **Purpose**: Database connection pool size
- **Type**: integer
- **Valid Values**: 5-100
- **Default**: 20
- **Scope**: Maximum concurrent database connections
- **Example**: `30`

#### db_connection_timeout_seconds
- **Purpose**: Database connection timeout
- **Type**: integer
- **Valid Values**: 5-300 (5 seconds to 5 minutes)
- **Default**: 30
- **Scope**: How long to wait for database connections
- **Example**: `60`

### Query Optimization

#### db_query_timeout_seconds
- **Purpose**: Maximum query execution time
- **Type**: integer
- **Valid Values**: 10-3600 (10 seconds to 1 hour)
- **Default**: 300 (5 minutes)
- **Scope**: Timeout for long-running queries
- **Example**: `600`

#### db_slow_query_threshold_ms
- **Purpose**: Threshold for logging slow queries
- **Type**: integer
- **Valid Values**: 100-10000 (100ms to 10 seconds)
- **Default**: 1000 (1 second)
- **Scope**: When to log queries as slow
- **Example**: `500`

## 📧 Notification Settings

### Email Configuration

#### email_notifications_enabled
- **Purpose**: Enable/disable email notifications
- **Type**: boolean
- **Valid Values**: true, false
- **Default**: false
- **Scope**: Controls all email notifications
- **Example**: `true`

#### notification_email_addresses
- **Purpose**: Email addresses for system notifications
- **Type**: json
- **Valid Values**: Array of valid email addresses
- **Default**: []
- **Example**: `["admin@company.com", "devops@company.com"]`

### Alert Thresholds

#### alert_job_failure_threshold
- **Purpose**: Number of consecutive job failures before alert
- **Type**: integer
- **Valid Values**: 1-10
- **Default**: 3
- **Scope**: When to send job failure alerts
- **Example**: `2`

#### alert_system_error_threshold
- **Purpose**: Number of system errors per hour before alert
- **Type**: integer
- **Valid Values**: 5-100
- **Default**: 20
- **Scope**: When to send system error alerts
- **Example**: `10`

## 🔧 Settings Management

### Configuration Best Practices

#### Setting Validation
```python
# Example setting validation
SETTING_VALIDATORS = {
    "theme_mode": lambda x: x in ["light", "dark"],
    "github_rate_limit_buffer": lambda x: 1 <= int(x) <= 50,
    "jwt_expiration_minutes": lambda x: 15 <= int(x) <= 1440,
    "notification_email_addresses": lambda x: all(validate_email(email) for email in json.loads(x))
}
```

#### Default Values
- All settings have sensible defaults
- Settings are optional unless marked as required
- Missing settings fall back to system defaults
- Client-specific settings override global defaults

#### Setting Updates
- Settings changes take effect immediately
- Some settings may require service restart
- Sensitive settings are encrypted automatically
- All setting changes are logged for audit

## 🤖 AI & ML Settings (Phase 1+)

### AI Feature Configuration

#### AI Feature Toggles
```json
{
  "ai_features_enabled": "false",
  "ml_predictions_enabled": "false",
  "semantic_search_enabled": "false",
  "embedding_generation_enabled": "false",
  "anomaly_detection_enabled": "false",
  "ai_validation_enabled": "false"
}
```

#### ML Model Configuration
```json
{
  "embedding_model": "text-embedding-3-small",
  "embedding_dimensions": "1536",
  "similarity_threshold": "0.8",
  "prediction_confidence_threshold": "0.7",
  "anomaly_detection_sensitivity": "medium"
}
```

#### AI Service Configuration
```json
{
  "ai_service_url": "http://localhost:5000",
  "ai_service_timeout": "30",
  "ai_batch_size": "100",
  "ai_retry_attempts": "3",
  "ai_cache_enabled": "true",
  "ai_cache_ttl": "3600"
}
```

### ML Monitoring Settings

#### Performance Monitoring
```json
{
  "ml_monitoring_enabled": "true",
  "performance_metrics_retention_days": "90",
  "anomaly_alert_threshold": "0.9",
  "prediction_accuracy_threshold": "0.8",
  "monitoring_sample_rate": "0.1"
}
```

#### Learning Memory Configuration
```json
{
  "learning_memory_enabled": "true",
  "max_learning_entries": "10000",
  "learning_confidence_threshold": "0.6",
  "auto_correction_enabled": "false",
  "feedback_collection_enabled": "true"
}
```

#### Vector Search Configuration
```json
{
  "vector_search_enabled": "false",
  "hnsw_ef_construction": "200",
  "hnsw_m": "16",
  "vector_similarity_metric": "cosine",
  "max_search_results": "50"
}
```

### AI Data Processing

#### Embedding Generation Settings
```json
{
  "auto_embed_new_content": "false",
  "embed_issue_summaries": "true",
  "embed_issue_descriptions": "true",
  "embed_pr_titles": "true",
  "embed_pr_descriptions": "true",
  "embed_comments": "false",
  "embedding_batch_size": "50"
}
```

#### ML Pipeline Configuration
```json
{
  "ml_pipeline_enabled": "false",
  "data_validation_enabled": "true",
  "feature_extraction_enabled": "false",
  "model_training_enabled": "false",
  "prediction_pipeline_enabled": "false",
  "pipeline_schedule": "daily"
}
```

### AI Security & Privacy

#### Data Privacy Settings
```json
{
  "ai_data_anonymization": "true",
  "pii_detection_enabled": "true",
  "sensitive_data_masking": "true",
  "ai_audit_logging": "true",
  "data_retention_policy": "strict"
}
```

#### AI Access Control
```json
{
  "ai_admin_only": "true",
  "ml_insights_role_required": "admin",
  "ai_api_rate_limit": "100",
  "ai_feature_permissions": "admin,power_user",
  "ai_data_access_level": "restricted"
}
```

### Phase Implementation Status

#### Phase 1 (Completed ✅)
- **Database Schema**: Vector columns and ML monitoring tables
- **Model Updates**: Enhanced unified models with AI capabilities
- **Infrastructure**: PostgresML and pgvector extensions
- **Settings Framework**: AI configuration structure prepared

#### Phase 2+ (Future)
- **Validation Layer**: Smart data validation using ML models
- **Embedding Generation**: Automatic text-to-vector conversion
- **Similarity Search**: Content discovery and duplicate detection
- **Predictive Analytics**: Story point estimation and forecasting
- **Anomaly Detection**: Automated issue and performance monitoring

---

This comprehensive settings system provides flexible, secure, and client-specific configuration management for the Pulse Platform, including advanced AI and ML capabilities.
