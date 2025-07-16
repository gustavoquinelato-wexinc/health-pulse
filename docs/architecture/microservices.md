# Microservices Communication

## 🎯 Communication Philosophy

The Pulse Platform follows a **"Secure by Design, API-First"** approach to microservices communication:

- **No Direct Frontend-ETL**: All communication flows through Backend Service
- **Internal Authentication**: Service-to-service security with API keys
- **Unified API Layer**: Backend Service provides consistent API interface
- **Graceful Degradation**: Services handle communication failures elegantly
- **Observability**: Complete request tracing across service boundaries

## 🏗️ Service Communication Architecture

### **Communication Flow**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   ETL Service   │
│   Service       │    │   Service       │    │                 │
│   (React SPA)   │◄──►│   (API Gateway) │◄──►│   (Data Engine) │
│                 │    │                 │    │                 │
│  • User Auth    │    │  • JWT Verify   │    │  • Internal     │
│  • Dashboard    │    │  • RBAC Check   │    │    Auth Check   │
│  • API Calls    │    │  • ETL Proxy    │    │  • Job Exec     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                        │                        │
        │                        ▼                        ▼
        │               ┌─────────────────┐    ┌─────────────────┐
        │               │   PostgreSQL    │    │   Redis Cache   │
        │               │   (Main DB)     │    │   (Optional)    │
        │               └─────────────────┘    └─────────────────┘
        │
        ▼
┌─────────────────┐
│   Browser       │
│   (User)        │
└─────────────────┘
```

### **Communication Patterns**

#### **1. Frontend → Backend Communication**
- **Protocol**: HTTPS REST API
- **Authentication**: JWT Bearer tokens
- **Format**: JSON request/response
- **Error Handling**: Standardized error responses

#### **2. Backend → ETL Communication**
- **Protocol**: HTTP REST API (internal network)
- **Authentication**: Internal API keys
- **Format**: JSON request/response with proxy headers
- **Error Handling**: Circuit breaker pattern

#### **3. Service Discovery**
- **Development**: Static configuration (localhost:port)
- **Production**: Service mesh or load balancer (planned)

## 🔐 Authentication & Authorization

### **Frontend Authentication Flow**

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Browser   │    │  Frontend   │    │  Backend    │
│             │    │   Service   │    │   Service   │
└─────────────┘    └─────────────┘    └─────────────┘
        │                  │                  │
        │ 1. Login Request │                  │
        ├─────────────────►│                  │
        │                  │ 2. Auth Request  │
        │                  ├─────────────────►│
        │                  │                  │ 3. Validate
        │                  │                  │    Credentials
        │                  │ 4. JWT Token     │
        │                  │◄─────────────────┤
        │ 5. JWT Token     │                  │
        │◄─────────────────┤                  │
        │                  │                  │
        │ 6. API Requests  │                  │
        │ (with JWT)       │                  │
        ├─────────────────►│                  │
```

### **Service-to-Service Authentication**

```python
# Backend Service → ETL Service
headers = {
    'Authorization': f'Bearer {user_jwt_token}',
    'X-Internal-Auth': INTERNAL_API_KEY,
    'X-User-ID': user_id,
    'X-Request-ID': correlation_id
}

response = requests.post(
    f'{ETL_SERVICE_URL}/api/v1/jobs/start',
    headers=headers,
    json=request_data
)
```

## 📡 API Communication Patterns

### **1. Request Proxying Pattern**

#### **Backend Service Proxy Implementation**
```python
@app.route('/api/etl/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@jwt_required()
@require_permission('etl.access')
async def etl_proxy(path: str):
    """Proxy ETL requests with authentication"""
    
    # Get current user from JWT
    user = get_current_user()
    
    # Validate permissions
    if not user.has_permission('etl.access'):
        return {'error': 'Insufficient permissions'}, 403
    
    # Prepare headers for ETL service
    etl_headers = {
        'X-Internal-Auth': INTERNAL_API_KEY,
        'X-User-ID': str(user.id),
        'X-User-Email': user.email,
        'X-Request-ID': generate_correlation_id(),
        'Content-Type': 'application/json'
    }
    
    # Forward request to ETL service
    try:
        etl_response = await http_client.request(
            method=request.method,
            url=f'{ETL_SERVICE_URL}/api/v1/{path}',
            headers=etl_headers,
            json=request.json,
            params=request.args,
            timeout=30
        )
        
        return etl_response.json(), etl_response.status_code
        
    except httpx.TimeoutException:
        return {'error': 'ETL service timeout'}, 504
    except httpx.ConnectError:
        return {'error': 'ETL service unavailable'}, 503
```

### **2. Circuit Breaker Pattern**

#### **ETL Service Circuit Breaker**
```python
class ETLServiceCircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    async def call_etl_service(self, method: str, path: str, **kwargs):
        """Call ETL service with circuit breaker protection"""
        
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise ServiceUnavailableError("ETL service circuit breaker is OPEN")
        
        try:
            response = await http_client.request(method, f'{ETL_SERVICE_URL}/{path}', **kwargs)
            
            # Success - reset failure count
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
            self.failure_count = 0
            
            return response
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
            
            raise e
```

## 🔄 Data Flow Patterns

### **1. ETL Job Control Flow**

```
User Action → Frontend → Backend → ETL Service → Job Execution
     ↓           ↓          ↓           ↓            ↓
  Dashboard   Validate   Proxy     Execute      Update Status
   Update    ← Response ← Response ← Response ← Job Complete
```

#### **Job Start Flow**
```python
# Frontend Service
async function startJob(jobName) {
    const response = await fetch(`/api/etl/jobs/${jobName}/start`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${jwt_token}`,
            'Content-Type': 'application/json'
        }
    });
    
    if (response.ok) {
        updateJobStatus(jobName, 'RUNNING');
        startStatusPolling();
    }
}

# Backend Service
@app.post('/api/etl/jobs/{job_name}/start')
async def start_job(job_name: str, user: User = Depends(get_current_user)):
    # Validate user permissions
    if not user.can_start_jobs():
        raise HTTPException(403, "Insufficient permissions")
    
    # Proxy to ETL service
    response = await etl_circuit_breaker.call_etl_service(
        'POST', f'api/v1/jobs/{job_name}/start',
        headers={'X-Internal-Auth': INTERNAL_API_KEY}
    )
    
    return response.json()

# ETL Service
@router.post('/api/v1/jobs/{job_name}/start')
async def start_job(job_name: str, request: Request):
    # Validate internal authentication
    if not validate_internal_auth(request):
        raise HTTPException(403, "Internal authentication required")
    
    # Start job
    job = get_job_by_name(job_name)
    job.status = 'PENDING'
    session.commit()
    
    # Trigger orchestrator
    await run_orchestrator()
    
    return {"success": True, "message": f"Job {job_name} started"}
```

### **2. Real-time Status Updates**

#### **WebSocket Communication (Planned)**
```python
# Frontend Service - WebSocket client
const ws = new WebSocket('ws://backend-service/ws/job-status');

ws.onmessage = (event) => {
    const statusUpdate = JSON.parse(event.data);
    updateJobStatusInUI(statusUpdate);
};

# Backend Service - WebSocket server
@app.websocket('/ws/job-status')
async def job_status_websocket(websocket: WebSocket):
    await websocket.accept()
    
    # Subscribe to ETL service status updates
    async for status_update in etl_status_stream():
        await websocket.send_json(status_update)
```

#### **Polling-Based Updates (Current)**
```python
# Frontend Service - Status polling
async function pollJobStatus() {
    const response = await fetch('/api/etl/jobs/status', {
        headers: {'Authorization': `Bearer ${jwt_token}`}
    });
    
    const status = await response.json();
    updateJobStatusDisplay(status);
}

setInterval(pollJobStatus, 5000); // Poll every 5 seconds
```

## 🛡️ Security Patterns

### **1. Internal Service Authentication**

#### **ETL Service Security Middleware**
```python
@app.middleware("http")
async def validate_internal_requests(request: Request, call_next):
    """Validate internal service requests"""
    
    # Allow health checks
    if request.url.path == "/health":
        return await call_next(request)
    
    # Require internal authentication for API endpoints
    if request.url.path.startswith("/api/v1/"):
        internal_auth = request.headers.get('X-Internal-Auth')
        
        if not internal_auth or internal_auth != INTERNAL_API_KEY:
            return JSONResponse(
                status_code=403,
                content={"error": "Internal authentication required"}
            )
    
    return await call_next(request)
```

### **2. Request Validation & Sanitization**

#### **Input Validation**
```python
from pydantic import BaseModel, validator

class JobStartRequest(BaseModel):
    job_name: str
    force: bool = False
    
    @validator('job_name')
    def validate_job_name(cls, v):
        allowed_jobs = ['jira_sync', 'github_sync']
        if v not in allowed_jobs:
            raise ValueError(f'Invalid job name. Allowed: {allowed_jobs}')
        return v

@app.post('/api/v1/jobs/start')
async def start_job(request: JobStartRequest):
    # Request is automatically validated by Pydantic
    pass
```

## 📊 Monitoring & Observability

### **1. Request Tracing**

#### **Correlation ID Propagation**
```python
# Backend Service - Generate correlation ID
correlation_id = str(uuid.uuid4())

# Forward to ETL service
headers = {
    'X-Correlation-ID': correlation_id,
    'X-Internal-Auth': INTERNAL_API_KEY
}

# ETL Service - Log with correlation ID
logger.info(
    "Processing job request",
    extra={
        'correlation_id': request.headers.get('X-Correlation-ID'),
        'user_id': request.headers.get('X-User-ID'),
        'job_name': job_name
    }
)
```

### **2. Service Health Monitoring**

#### **Health Check Aggregation**
```python
# Backend Service - Aggregate health checks
@app.get('/health')
async def health_check():
    health_status = {
        'backend_service': 'healthy',
        'etl_service': await check_etl_service_health(),
        'database': await check_database_health(),
        'timestamp': datetime.utcnow().isoformat()
    }
    
    overall_status = 'healthy' if all(
        status == 'healthy' for status in health_status.values() 
        if isinstance(status, str)
    ) else 'unhealthy'
    
    return {
        'status': overall_status,
        'services': health_status
    }
```

## 🚀 Performance Optimization

### **1. Connection Pooling**

```python
# HTTP client with connection pooling
http_client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_keepalive_connections=20,
        max_connections=100
    ),
    timeout=httpx.Timeout(30.0)
)
```

### **2. Response Caching**

```python
# Cache frequently accessed data
@lru_cache(maxsize=100, ttl=300)  # 5-minute cache
async def get_job_status():
    response = await etl_service_client.get('/api/v1/jobs/status')
    return response.json()
```

This microservices communication design ensures secure, reliable, and observable service interactions while maintaining clear separation of concerns and enabling independent service evolution.
