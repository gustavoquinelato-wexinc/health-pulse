# Multi-Tenant Worker Architecture

## 🎯 Problem Solved

**Original Issue**: JWT token errors when ETL frontend starts with fresh database, caused by:
- Workers starting automatically and trying to use user authentication
- Global queues and workers (no tenant isolation)
- No way for tenants to control their own workers

## 🏗️ Solution: Multi-Tenant Worker Architecture

### **Key Changes**

#### 1. **Service-to-Service Authentication**
- ✅ Workers use **system credentials** (no user tokens)
- ✅ Database access via system connection
- ✅ RabbitMQ access via service credentials
- ✅ **No JWT tokens needed** for background processing

#### 2. **Tenant-Specific Queues**
```
OLD: transform_queue (global)
NEW: transform_queue_tenant_1, transform_queue_tenant_2, etc.
```

#### 3. **Tenant-Specific Workers**
- ✅ One worker per tenant per queue type
- ✅ Dynamic worker creation/destruction
- ✅ Tenant isolation at worker level

#### 4. **Frontend Tenant Control**
- ✅ Tenants can control **only their workers**
- ✅ Admin can control **all tenant workers**
- ✅ Real-time worker status per tenant

---

## 🔧 Architecture Components

### **Queue Manager** (`services/backend-service/app/etl/queue/queue_manager.py`)
```python
# Multi-tenant queue naming
def get_tenant_queue_name(self, tenant_id: int, queue_type: str = 'transform') -> str:
    return f"{queue_type}_queue_tenant_{tenant_id}"

# Tenant-specific queue setup
def setup_tenant_queue(self, tenant_id: int, queue_type: str = 'transform'):
    # Creates queue: transform_queue_tenant_1
```

### **Worker Manager** (`services/backend-service/app/workers/worker_manager.py`)
```python
# Tenant-specific worker management
def start_tenant_workers(self, tenant_id: int) -> bool:
    # Creates worker for tenant's queue
    
def stop_tenant_workers(self, tenant_id: int) -> bool:
    # Stops only this tenant's workers
    
def get_tenant_worker_status(self, tenant_id: int):
    # Returns status for tenant's workers only
```

### **Transform Worker** (`services/backend-service/app/workers/transform_worker.py`)
```python
# Now accepts queue name parameter
def __init__(self, queue_name: str = 'transform_queue'):
    # Can work with any queue (tenant-specific or global)
```

---

## 🌐 API Endpoints

### **Global Worker Control** (Admin Only)
```http
POST /api/v1/admin/workers/control
{
  "action": "start|stop|restart"
}
```

### **Tenant Worker Control** (Tenant-Specific)
```http
POST /api/v1/admin/workers/tenant/control
{
  "action": "start|stop|restart",
  "tenant_id": 1
}
```

### **Tenant Worker Status**
```http
GET /api/v1/admin/workers/tenant/{tenant_id}/status
```

---

## 🎮 Frontend Integration

### **Queue Management Page** (`services/etl-frontend/src/pages/QueueManagementPage.tsx`)

**New Features:**
- ✅ **Tenant Worker Status**: Shows workers per tenant
- ✅ **Tenant Controls**: Start/stop/restart per tenant
- ✅ **Real-time Status**: Live worker status updates
- ✅ **Access Control**: Users see only their tenant's workers

**UI Components:**
```tsx
// Tenant-specific worker controls
{Object.entries(workerStatus.tenants).map(([tenantId, tenantData]) => (
  <div key={tenantId}>
    <h4>Tenant {tenantId}</h4>
    <Button onClick={() => performTenantWorkerAction('start', tenantId)}>
      Start Workers
    </Button>
    // ... stop, restart buttons
  </div>
))}
```

---

## 🚀 Usage Examples

### **1. Start Workers for All Tenants**
```python
from app.workers.worker_manager import get_worker_manager

manager = get_worker_manager()
manager.start_all_workers()  # Discovers active tenants automatically
```

### **2. Control Specific Tenant Workers**
```python
# Start workers for tenant 1
manager.start_tenant_workers(1)

# Stop workers for tenant 2  
manager.stop_tenant_workers(2)

# Get status for tenant 3
status = manager.get_tenant_worker_status(3)
```

### **3. Publish to Tenant Queue**
```python
from app.etl.queue.queue_manager import QueueManager

queue_manager = QueueManager()
queue_manager.publish_transform_job(
    tenant_id=1,  # Automatically routes to tenant_1 queue
    integration_id=1,
    raw_data_id=123,
    data_type='jira_custom_fields'
)
```

---

## 🧪 Testing

### **Test Script**
```bash
python services/backend-service/scripts/test_multitenant_workers.py
```

**Tests:**
- ✅ Queue creation per tenant
- ✅ Worker startup per tenant  
- ✅ Message publishing to tenant queues
- ✅ Worker control (start/stop/restart)
- ✅ Status monitoring

---

## 🔒 Security & Access Control

### **Worker Authentication**
- ✅ **No user tokens**: Workers use system database connections
- ✅ **Service credentials**: RabbitMQ access via service account
- ✅ **Tenant isolation**: Workers only process their tenant's data

### **Frontend Access Control**
- ✅ **Tenant users**: Can only control their tenant's workers
- ✅ **Admin users**: Can control all tenant workers
- ✅ **API validation**: Tenant ID validation in all endpoints

---

## 🎯 Benefits

1. **🔧 Fixes JWT Issues**: No more invalid token errors on startup
2. **🏢 Tenant Isolation**: Each tenant has dedicated workers
3. **⚡ Scalability**: Add workers per tenant as needed
4. **🎮 User Control**: Tenants can manage their own workers
5. **🛡️ Security**: Service-to-service authentication
6. **📊 Monitoring**: Real-time status per tenant
7. **🔄 Flexibility**: Dynamic worker management

---

## 🚀 Next Steps

1. **Deploy Changes**: Update backend and frontend services
2. **Test with Real Data**: Verify with actual tenant data
3. **Monitor Performance**: Check worker performance per tenant
4. **Scale as Needed**: Add more workers for high-volume tenants
5. **Add More Queue Types**: Extend to vectorization, etc.

---

## 📝 Migration Notes

- ✅ **Backward Compatible**: Legacy `transform_queue` still supported
- ✅ **Gradual Migration**: Can migrate tenants one by one
- ✅ **No Data Loss**: Existing queues continue to work
- ✅ **Easy Rollback**: Can revert to global workers if needed
