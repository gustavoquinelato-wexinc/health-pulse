# 🧪 Pulse Platform Tests

This directory contains integration and validation tests for the Pulse Platform.

## 📋 **Test Files**

### **🚨 Security Tests**
- **`test_client_isolation_security.py`** - **CRITICAL** security validation
  - Tests client data isolation
  - Prevents cross-client data access
  - **Run regularly** to ensure no security regressions

### **🔧 Functionality Tests**
- **`test_client_name_lookup.py`** - Client name lookup validation
  - Tests case-insensitive CLIENT_NAME → CLIENT_ID lookup
  - Validates error handling for invalid client names
  - Tests database client resolution

### **🏗️ Architecture Tests**
- **`test_per_client_orchestrators.py`** - Multi-instance setup validation
  - Tests ETL instances serve only their assigned client
  - Validates multi-instance architecture
  - Ensures no cross-client interference

## 🚀 **Running Tests**

### **All Tests**
```bash
# From project root
python tests/test_client_isolation_security.py
python tests/test_client_name_lookup.py
python tests/test_per_client_orchestrators.py
```

### **Security Test (Most Important)**
```bash
# Run this regularly!
python tests/test_client_isolation_security.py
```

### **Prerequisites**
- Database must be running and populated
- ETL services should be running for orchestrator tests
- Proper environment configuration

## ✅ **Expected Results**

### **Security Test**
```
🚨 CRITICAL SECURITY TEST: Client Isolation Validation
============================================================

📋 Step 1: Verifying Multi-Client Setup
✅ Found 2 active clients for testing
  • WEX (ID: 1)
  • TechCorp (ID: 2)

📋 Step 2: Testing Metrics Helpers Client Isolation
  ✅ get_active_issues_query: Client 1 = 1, Client 2 = 0
  ✅ get_workflow_metrics: Client 1 = 1 workflows, Client 2 = 0 workflows
  ✅ get_data_quality_report: Client 1 = 1 issues, Client 2 = 0 issues

📋 Step 3: Testing Cross-Client Data Isolation
  • WEX (ID: 1): 1 issues
  • TechCorp (ID: 2): 0 issues
  ✅ Data integrity check passed: 1 total issues = sum of client issues

📋 Step 4: Testing Function Parameter Requirements
  ✅ get_active_issues_query properly requires client_id parameter
  ✅ get_workflow_metrics properly requires client_id parameter

✅ Client Isolation Security Test Complete!

🎯 Security Status:
  • All metrics functions require client_id parameter
  • Cross-client data isolation verified
  • No unauthorized data access detected

🔒 SECURITY: Multi-instance architecture prevents cross-client access

🔒 SECURITY TEST PASSED
```

### **Client Name Lookup Test**
```
✅ 'WEX' → Client ID: 1
✅ 'wex' → Client ID: 1  
✅ 'Wex' → Client ID: 1
✅ Case-insensitive matching works
```

### **Multi-Instance Test**
```
✅ WEX ETL instance is healthy (Port 8000)
✅ TechCorp ETL instance is healthy (Port 8001)
✅ Each instance serves only its client
```

## 🔄 **CI/CD Integration**

These tests should be integrated into your CI/CD pipeline:

```yaml
# Example GitHub Actions
- name: Run Security Tests
  run: python tests/test_client_isolation_security.py

- name: Run Functionality Tests  
  run: |
    python tests/test_client_name_lookup.py
    python tests/test_per_client_orchestrators.py
```

## ⚠️ **Important Notes**

1. **Security test is CRITICAL** - Run before any deployment
2. **Tests require live database** - Not unit tests, but integration tests
3. **Multi-instance test requires running services** - Start ETL instances first
4. **All tests should pass** - Any failure indicates a serious issue
