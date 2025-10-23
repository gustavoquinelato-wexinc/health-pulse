# WEX Gateway Testing Scripts

This directory contains scripts to test and diagnose WEX Gateway connectivity issues.

## 🔍 Main Test Script: `test_wex_gateway.py`

Comprehensive test suite for validating WEX Gateway connection and functionality.

### Usage

```bash
# Basic test with default tenant (ID: 1)
python scripts/test_wex_gateway.py

# Test specific tenant
python scripts/test_wex_gateway.py --tenant-id 2

# Verbose output with detailed logging
python scripts/test_wex_gateway.py --verbose

# Save results to JSON file
python scripts/test_wex_gateway.py --output results.json

# Full example
python scripts/test_wex_gateway.py --tenant-id 1 --verbose --output wex_test_results.json
```

### What It Tests

1. **Database Integration Configuration**
   - Checks if WEX Gateway integration exists in database
   - Validates base_url, API key, and settings
   - Reports configuration issues

2. **Provider Initialization**
   - Tests WEXGatewayProvider class initialization
   - Validates OpenAI client setup
   - Checks timeout and model configuration

3. **Basic Connectivity**
   - Performs health check against WEX Gateway
   - Measures response time
   - Tests basic API availability

4. **Embedding Generation**
   - Tests embedding generation with various text inputs
   - Validates embedding dimensions and content
   - Tests edge cases (empty strings, special characters)

5. **Text Generation**
   - Tests chat completion functionality
   - Validates response quality and timing
   - Tests different prompt types

6. **Batch Processing**
   - Tests batch embedding generation
   - Measures performance with multiple texts
   - Validates batch size handling

7. **Error Handling**
   - Tests graceful handling of invalid inputs
   - Tests very long text processing
   - Tests empty input handling

### Sample Output

```
🔍 WEX Gateway Validation Test Suite
==================================================

1️⃣ Testing Database Integration Configuration...
   ✅ Found integration: WEX AI Gateway (ID: 5)
   🔗 Base URL: https://aips-ai-gateway.dev.ai-platform.int.wexfabric.com
   🔑 API Key: ✅ Present
   ⚙️  Settings: {
        "model_path": "azure-text-embedding-3-small",
        "cost_tier": "paid",
        "gateway_route": true
      }

2️⃣ Testing Provider Initialization...
   ✅ Provider initialized successfully
   🔗 Base URL: https://aips-ai-gateway.dev.ai-platform.int.wexfabric.com
   🤖 Model: azure-text-embedding-3-small
   ⏱️  Timeout: 120s

3️⃣ Testing Basic Connectivity...
   🏥 Health check: healthy
   ⏱️  Response time: 1.23s
   ✅ Gateway is responding correctly

4️⃣ Testing Embedding Generation...
   ✅ Test 1: Generated 1536D embedding in 0.85s
   ✅ Test 2: Generated 1536D embedding in 0.92s
   ✅ Test 3: Generated 1536D embedding in 0.78s
   ✅ Test 4: Generated 1536D embedding in 0.45s

5️⃣ Testing Text Generation...
   ✅ Test 1: Generated 156 chars in 2.34s
   ✅ Test 2: Generated 89 chars in 1.87s
   ✅ Test 3: Generated 12 chars in 1.23s

6️⃣ Testing Batch Processing...
   ✅ Batch processing: 10 embeddings in 2.45s
   📊 Average time per embedding: 0.245s

7️⃣ Testing Error Handling...
   ✅ Very long text: Handled gracefully
   ✅ Empty list: Handled gracefully

📊 Test Summary
==================================================
Tenant ID: 1
Timestamp: 2024-10-20 15:30:45

✅ Database Config: PASSED
✅ Provider Init: PASSED
✅ Connectivity: PASSED
✅ Embeddings: PASSED
✅ Text Generation: PASSED
✅ Batch Processing: PASSED
✅ Error Handling: PASSED

🎉 All tests completed successfully!
```

## 🚨 Common Issues and Solutions

### Issue: "Connection error" in logs

**Symptoms:**
```
app.ai.providers.wex_gateway_provider - ERROR - WEX Gateway embedding batch failed after 3 attempts: Connection error.
```

**Possible Causes:**
1. **Invalid Base URL**: Check if the WEX Gateway URL is correct and accessible
2. **Invalid API Key**: Verify the API key is correct and not expired
3. **Network Issues**: Check firewall, proxy, or network connectivity
4. **Gateway Downtime**: The WEX Gateway service might be temporarily unavailable

**Diagnostic Steps:**
```bash
# 1. Test with verbose logging
python scripts/test_wex_gateway.py --verbose

# 2. Check database configuration
python scripts/test_wex_gateway.py --tenant-id YOUR_TENANT_ID

# 3. Test network connectivity manually
curl -H "Authorization: Bearer YOUR_API_KEY" https://your-wex-gateway-url/health

# 4. Check backend service logs
docker logs backend-service | grep -i "wex\|gateway\|embedding"
```

### Issue: "No active AI provider integration found"

**Solution:**
1. Check if WEX Gateway integration is configured in database:
   ```sql
   SELECT * FROM integrations WHERE type = 'ai_provider' AND active = true;
   ```

2. If missing, run the migration script:
   ```bash
   python services/backend-service/scripts/migrations/0002_initial_seed_data_wex.py
   ```

### Issue: "Provider initialization failed"

**Possible Causes:**
1. Missing or invalid API key encryption
2. Corrupted integration settings
3. Missing environment variables

**Solution:**
1. Check encryption key is properly set:
   ```bash
   echo $ENCRYPTION_KEY
   ```

2. Verify integration settings in database:
   ```sql
   SELECT provider, base_url, settings FROM integrations WHERE type = 'ai_provider';
   ```

## 📋 Requirements

- Python 3.8+
- Backend service dependencies installed
- Database connection configured
- WEX Gateway integration set up in database

## 🔧 Environment Setup

Make sure your environment has:

```bash
# Database connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DATABASE=health_pulse

# Encryption key for API tokens
ENCRYPTION_KEY=your_base64_encoded_key

# Optional: WEX Gateway environment variables (for migration setup)
WEX_AI_GATEWAY_BASE_URL=https://your-gateway-url
WEX_AI_GATEWAY_API_KEY=your-api-key
```

## 📊 Exit Codes

- `0`: All tests passed
- `1`: One or more tests failed
- `130`: Test interrupted by user (Ctrl+C)

## 🔍 Troubleshooting Tips

1. **Always start with verbose mode** to see detailed error messages
2. **Check database first** - most issues are configuration-related
3. **Test connectivity manually** using curl or similar tools
4. **Check service logs** for additional context
5. **Verify environment variables** are properly set
6. **Test with different tenant IDs** if you have multiple tenants

## 📝 Reporting Issues

When reporting WEX Gateway issues, include:

1. Full test output with `--verbose` flag
2. Tenant ID being tested
3. Recent backend service logs
4. Database integration configuration (without sensitive data)
5. Network environment details (proxy, firewall, etc.)
