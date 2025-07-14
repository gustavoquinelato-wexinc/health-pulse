# ETL Service - Integrations Setup Guide

This document describes how to configure and manage integrations in the ETL Service, including Jira, GitHub, Aha!, and Azure DevOps.

## 🔧 Supported Integrations

| Integration | Status | Purpose | Authentication |
|-------------|--------|---------|----------------|
| **Jira** | Required | Issue tracking, project management | Username + API Token |
| **GitHub** | Optional | Development data, commits, PRs | Personal Access Token |
| **Aha!** | Optional | Product roadmap, features | API Token |
| **Azure DevOps** | Optional | Development data, work items | Personal Access Token |

## 📋 Configuration

### Environment Variables

Add the following to your `.env` file:

```bash
# Jira Configuration (Required)
JIRA_URL="https://your-domain.atlassian.net"
JIRA_USERNAME="your-email@domain.com"
JIRA_TOKEN="your_jira_api_token"

# GitHub Configuration (Optional)
GITHUB_TOKEN="your_github_personal_access_token"

# Aha! Configuration (Optional)
AHA_URL="https://your-org.aha.io"
AHA_TOKEN="your_aha_api_token"

# Azure DevOps Configuration (Optional)
AZDO_URL="https://dev.azure.com/your-org"
AZDO_TOKEN="your_azdo_personal_access_token"
```

### Current Configuration

Based on your current setup:

```bash
# Jira Configuration
JIRA_URL="https://wexinc.atlassian.net"
JIRA_USERNAME="gustavo.quinelato@wexinc.com"
JIRA_TOKEN="ATATT3xFfGF0PrxXptKv..."

# GitHub Configuration
GITHUB_TOKEN="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"

# Aha! Configuration
AHA_URL="https://wexh.aha.io"
AHA_TOKEN="9h_rRq_saUfJk7O8if8cHwZpSd6L5tYribRhO0YmiaE"

# Azure DevOps Configuration
AZDO_URL="https://dev.azure.com/WEXHealthTech"
AZDO_TOKEN="BDWEMBIwtd9M97aEp9rqBeNRY2hcC3Mir7bxqMhP9dNVXFAhgXmpJQQJ99BEACAAAAAQzoiyAAASAZDONp4n"
```

## 🔐 Security Features

### Token Encryption

All integration tokens are automatically encrypted before being stored in the database using:

- **Encryption Algorithm**: Fernet (symmetric encryption)
- **Key Management**: Stored in `ENCRYPTION_KEY` environment variable
- **Storage**: Encrypted tokens stored in `integrations.password` field

### Token Decryption

Tokens are automatically decrypted when needed for API calls:

```python
from app.core.config import AppConfig

# Decrypt token for use
decrypted_token = AppConfig.decrypt_token(encrypted_token, key)
```

## 🛠️ Management Tools

### 1. Initialize Integrations Script

**Location**: `utils/initialize_integrations.py`

**Purpose**: Initialize all configured integrations with encrypted tokens

**Usage**:
```bash
# Initialize all configured integrations
python utils/initialize_integrations.py

# Dry run (show what would be done)
python utils/initialize_integrations.py --dry-run

# Initialize specific integration only
python utils/initialize_integrations.py --integration jira

# Force overwrite existing integrations
python utils/initialize_integrations.py --force
```

**Features**:
- ✅ Automatic token encryption
- ✅ Duplicate detection
- ✅ Dry run mode
- ✅ Individual integration targeting
- ✅ Force overwrite option

### 2. Database Reset Script

**Location**: `utils/reset_database.py`

**Enhanced Features**:
- ✅ Drops all tables and sequences
- ✅ Recreates table structure
- ✅ **NEW**: Initializes all configured integrations
- ✅ Interactive prompts for each step

**Usage**:
```bash
python utils/reset_database.py
```

### 3. Test Script

**Location**: `utils/test_jira_jobs.py`

**Enhanced Features**:
- ✅ Tests environment configuration
- ✅ **NEW**: Shows status of all optional integrations
- ✅ Tests Jira connection
- ✅ Step-by-step job debugging

**Usage**:
```bash
# Test environment and connections
python utils/test_jira_jobs.py --test-connection

# Interactive step-by-step debugging
python utils/test_jira_jobs.py --step-by-step
```

## 📊 Database Storage

### Integration Records

All integrations are stored in the `integrations` table:

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Auto-incrementing primary key |
| `name` | String | Integration name (Jira, GitHub, Aha!, Azure DevOps) |
| `url` | String | Base URL for the integration |
| `username` | String | Username (for Jira only) |
| `password` | String | **Encrypted** token/password |
| `last_sync_at` | DateTime | Last successful sync timestamp |
| `created_at` | DateTime | Record creation timestamp |
| `last_updated_at` | DateTime | Last update timestamp |

### Current Database State

After initialization, you should have:

```
✅ Jira integration (ID: 1)
✅ GitHub integration (ID: 101)  
✅ Aha! integration (ID: 201)
✅ Azure DevOps integration (ID: 301)
```

## 🔄 Automatic Initialization

### Application Startup

The ETL service automatically:

1. **Checks for existing integrations** on startup
2. **Creates missing integrations** if none exist
3. **Uses encrypted tokens** from environment variables
4. **Logs initialization status**

### First Run Setup

When running the application for the first time:

1. **Database tables** are created automatically
2. **Integration records** are inserted with encrypted tokens
3. **Ready for data extraction** immediately

## 🧪 Testing Integration Setup

### Quick Test

```bash
# Test all integrations are configured
python utils/test_jira_jobs.py --test-connection
```

**Expected Output**:
```
🔍 Testing Environment Configuration
--------------------------------------------------
✅ JIRA_URL: https://wexinc.atlas...
✅ JIRA_USERNAME: gustavo.quinelato@we...
✅ JIRA_TOKEN: ATATT3xFfGF0PrxXptKv...

📋 Optional Integrations:
   GitHub: ✅ Configured
   Aha!: ✅ Configured
   Azure DevOps: ✅ Configured

✅ Debug Mode: True
✅ Log Level: INFO
```

### Verify Database Records

```bash
# Check existing integrations
python utils/initialize_integrations.py --dry-run
```

## 🚀 Next Steps

1. **Test Jira Connection**: Verify Jira integration works
2. **Run Data Extraction**: Start ETL jobs to populate data
3. **Monitor Logs**: Check for any integration issues
4. **Add More Integrations**: Configure additional tools as needed

## 📝 Notes

- **Tokens are encrypted** automatically when stored
- **Environment variables** are the source of truth for configuration
- **Database records** are created from environment variables
- **Existing integrations** are not overwritten unless forced
- **All integrations** are optional except Jira (required for core functionality)
