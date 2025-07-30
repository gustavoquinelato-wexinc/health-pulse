# 🚀 Client-Specific Logging - Quick Start Guide

## 📋 **Overview**

The Pulse Platform now has complete client-specific logging across all services, enabling proper multi-tenant log isolation and debugging.

## ✅ **What's Implemented**

### **ETL Service** (Multi-Instance)
```bash
# Each client runs separate ETL instance
CLIENT_NAME=WEX python -m uvicorn app.main:app --port 8001
CLIENT_NAME=TechCorp python -m uvicorn app.main:app --port 8002
```
- **Log Files**: `etl_service_wex.log`, `orchestrator_wex.log`
- **UI**: Icon-only download/delete buttons with client-specific file detection

### **Backend Service** (Single Instance, Multi-Client)
- **Middleware**: Extracts client context from JWT tokens
- **Log Files**: `backend_service_wex.log`, `backend_service_techcorp.log`
- **API Endpoints**: `/api/v1/logs/frontend` for frontend log collection

### **Frontend Application** (Single App, Multi-Client)
- **ClientLogger**: Automatic client detection and prefixed console logs
- **Error Boundary**: Professional error handling with client context
- **API Client**: Automatic request/response logging with timing

## 🎯 **Usage Examples**

### **Frontend Logging**
```javascript
import clientLogger from '../utils/clientLogger'

// User actions
clientLogger.logUserAction('button_click', 'submit_form', { formId: 'user-settings' })

// API calls (automatic via apiClient)
import apiClient from '../utils/apiClient'
const data = await apiClient.get('/api/v1/users') // Auto-logged

// Errors
clientLogger.error('Form validation failed', { 
  type: 'validation_error',
  field: 'email' 
})
```

### **Backend Logging**
```python
# Automatic via middleware - all requests logged with client context
from app.core.client_logging_middleware import get_client_logger_from_request

logger = get_client_logger_from_request(request, "api.users")
logger.info("User updated profile", user_id=user.id)
```

### **ETL Logging**
```python
# Automatic via CLIENT_NAME environment variable
logger = get_logger("etl.github")
logger.info("Processing repository", repo_name="pulse-platform")
```

## 📁 **Log File Structure**

```
logs/
├── etl/
│   ├── etl_service_wex.log      ← WEX ETL operations
│   └── etl_service_techcorp.log ← TechCorp ETL operations
├── backend/
│   ├── backend_service_wex.log      ← WEX API requests
│   ├── backend_service_techcorp.log ← TechCorp API requests
│   └── backend_service_system.log   ← System startup/errors
└── frontend/
    └── Transmitted to backend with client context
```

## 🔍 **Log Format Examples**

### **Console (Frontend)**
```
[WEX] User action: button_click
[TECHCORP] API GET /api/v1/users completed
[WEX] React Error Boundary caught error
```

### **Backend Log Files**
```
2025-07-30 10:15:23 - http.middleware - INFO - Request completed method=GET url=/api/v1/users status_code=200 client=WEX user_id=123
2025-07-30 10:15:24 - frontend_logs - ERROR - Frontend: Form validation failed client_id=1 user_id=123
```

### **ETL Log Files**
```
2025-07-30 10:20:15 - etl.github - INFO - Processing repository repo_name=pulse-platform client=WEX
2025-07-30 10:20:16 - etl.jira - INFO - Syncing issues project=PULSE client=WEX
```

## 🛠 **Integration Status**

| Component | Status | Integration |
|-----------|--------|-------------|
| **App.tsx** | ✅ | ClientErrorBoundary wrapper |
| **Header.tsx** | ✅ | User action logging |
| **ServiceFrame.tsx** | ✅ | Theme injection logging |
| **AuthContext.tsx** | ✅ | Authentication error logging |
| **ThemeContext.tsx** | ✅ | API client integration |
| **TypeScript** | ✅ | clientLogger.d.ts declarations |

## 🚀 **Next Steps**

1. **Test Multi-Client Scenarios**:
   ```bash
   # Test different CLIENT_NAME values
   CLIENT_NAME=WEX npm run dev:etl
   CLIENT_NAME=TechCorp npm run dev:etl
   ```

2. **Monitor Log Files**:
   ```bash
   # Watch client-specific logs
   tail -f services/backend-service/logs/backend_service_wex.log
   tail -f services/etl-service/logs/etl_service_wex.log
   ```

3. **Add More Components**:
   - Replace remaining `console.log` calls with `clientLogger`
   - Replace `fetch` calls with `apiClient`
   - Add user action logging to buttons/forms

## 🎉 **Benefits Achieved**

- **🔍 Easy Debugging**: Client-specific logs make troubleshooting faster
- **🔐 Security Compliance**: Client data isolation in logs
- **📊 Analytics**: Per-client usage and error tracking
- **🚀 Scalability**: Easy to add new clients without code changes
- **💼 Enterprise Ready**: Professional error handling and logging

---

**🎯 The Pulse Platform now has enterprise-grade, client-specific logging across all services!**
