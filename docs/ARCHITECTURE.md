# Pulse Platform - Architecture Documentation

## 🏗️ **System Architecture**

### **Unified Platform Architecture**

The Pulse Platform is now a unified engineering analytics platform with embedded ETL management capabilities:

```
Row 1: Unified Platform Services
┌─────────────────────────────────────────┐    ┌─────────────────┐    ┌───────────────────┐
│  Pulse Platform Frontend               │◄──►│  Backend        │    │  AI Service       │
│  (React/Vite) - Port: 5173            │    │  (Node.js)      │    │  (LangGraph)      │
│                                        │    │  Port: 3001     │    │  Port: 8001       │
│ ┌─────────────────────────────────────┐ │    │                 │    │                   │
│ │ Main Platform Features              │ │    │ • API Gateway   │    │ • AI Orchestrator │
│ │ • DORA Metrics Dashboard           │ │    │ • Authentication│    │ • Agent Workflows │
│ │ • Engineering Analytics            │ │    │ • User Mgmt     │    │ • MCP Servers     │
│ │ • Real-time Monitoring             │ │    │ • Session Mgmt  │    │ • Tool Integration│
│ │ • AI Chat Interface                │ │◄───┼─ Client Mgmt    │    │                   │
│ └─────────────────────────────────────┘ │    │                 │    │                   │
│                                        │    │                 │    │                   │
│ ┌─────────────────────────────────────┐ │    │                 │    │                   │
│ │ Embedded ETL Management             │ │    │                 │    │                   │
│ │ • iframe Integration (Port: 8000)   │ │◄───┼─────────────────┼────┼───────────────────┤
│ │ • Job Orchestration                │ │    │                 │    │                   │
│ │ • Data Pipeline Control            │ │    │                 │    │                   │
│ │ • Progress Monitoring              │ │    │                 │    │                   │
│ │ • Admin-only Access                │ │    │                 │    │                   │
│ └─────────────────────────────────────┘ │    │                 │    │                   │
└─────────────────────────────────────────┘    └─────────────────┘    └───────────────────┘
                    │                                    │                       │
                    └────────────────────────────────────┼───────────────────────┘
                                                        │
                                            ┌─────────────────┐
                                            │  ETL Service    │
                                            │  (FastAPI)      │
                                            │  Port: 8000     │
                                            │                 │
                                            │ • Data Extract  │
                                            │ • Job Control   │
                                            │ • Progress Track│
                                            │ • Recovery      │
                                            │ • Admin APIs    │
                                            └─────────────────┘
                                │                       │                       │
                                ▼                       ▼                       ▼
Row 2: Caching Layer            │              ┌─────────────────┐              │
                                └─────────────►│  Redis Cache    │◄─────────────┘
                                               │  (Caching)      │
                                               │  Port: 6379     │
                                               │                 │
                                               │ • Query Cache   │
                                               │ • Session Cache │
                                               │ • Job Queue     │
                                               │ • Performance   │
                                               └─────────────────┘
                                                       │
                                                       ▼
Row 3: Database Layer                         ┌─────────────────┐
                                              │  PostgreSQL     │
                                              │  (Database)     │
                                              │  Port: 5432     │
                                              │                 │
                                              │ • Primary DB    │
                                              │ • Job State     │
                                              │ • User Data     │
                                              │ • Audit Logs    │
                                              └─────────────────┘

External Integrations:
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Data APIs      │    │  AI/LLM APIs    │    │  MCP Ecosystem  │
│                 │    │                 │    │                 │
│ • Jira Cloud    │    │ • OpenAI        │    │ • MCP Servers   │
│ • GitHub API    │    │ • Claude        │    │ • Tool Protocols│
│ • Rate Limits   │    │ • Local LLMs    │    │ • Agent Tools   │
│ • Auth Tokens   │    │ • Embeddings    │    │ • Context Mgmt  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       ▲                       ▲
         │                       │                       │
    ETL Service            AI Service              Frontend (Direct)
```

### **Data Flow Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  External APIs  │───►│  ETL Service    │───►│  PostgreSQL     │
│                 │    │                 │    │                 │
│ • Jira Issues   │    │ • Extract       │    │ • Unified       │
│ • GitHub PRs    │    │ • Transform     │    │   Schema        │
│ • Repositories  │    │ • Load          │    │ • Normalized    │
│ • Changelogs    │    │ • Validate      │    │   Data          │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Frontend UI    │◄───│  AI Service     │◄───│  Data Analysis  │
│                 │    │                 │    │                 │
│ • Dashboards    │    │ • ML Models     │    │ • Pattern       │
│ • Reports       │    │ • Analytics     │    │   Recognition   │
│ • Alerts        │    │ • Insights      │    │ • Predictions   │
│ • Monitoring    │    │ • Predictions   │    │ • Correlations  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔗 **Embedded ETL Architecture**

### **Platform Integration Model**

The Pulse Platform now provides a unified user experience by embedding ETL management directly within the main frontend application:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Pulse Platform Frontend                     │
│                         (Port: 5173)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ DORA Metrics    │  │ Engineering     │  │ Settings        │ │
│  │ Dashboard       │  │ Analytics       │  │ Management      │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              ETL Management (Admin Only)                   │ │
│  │  ┌─────────────────────────────────────────────────────┐   │ │
│  │  │            Embedded ETL Interface                   │   │ │
│  │  │              (iframe: Port 8000)                    │   │ │
│  │  │                                                     │   │ │
│  │  │  • Job Orchestration Dashboard                      │   │ │
│  │  │  • Data Pipeline Configuration                      │   │ │
│  │  │  • Real-time Progress Monitoring                    │   │ │
│  │  │  • Integration Management                           │   │ │
│  │  │  • Admin Panel Access                               │   │ │
│  │  │                                                     │   │ │
│  │  │  Authentication: Shared JWT tokens                  │   │ │
│  │  │  Theme: Inherited from parent                       │   │ │
│  │  │  Branding: Client-specific logos                    │   │ │
│  │  └─────────────────────────────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### **Authentication Flow**

```
1. User Login (Platform)
   ├─ Frontend authenticates with Backend Service
   ├─ JWT token stored in localStorage + cookies
   └─ User role/permissions validated

2. ETL Access (Admin Only)
   ├─ Frontend checks user.is_admin
   ├─ If admin: Load ETL iframe with token
   ├─ ETL Service validates token with Backend
   └─ Seamless embedded experience

3. Token Management
   ├─ Shared JWT across all services
   ├─ Automatic token refresh
   └─ Centralized session management
```

### **Branding Strategy**

```
Login Pages (Platform Branding):
├─ Frontend Login: Pulse Platform logo
├─ ETL Login: Pulse Platform logo (fallback)
└─ Consistent platform identity

Internal Pages (Client Branding):
├─ Frontend Header: Client-specific logo (WEX, etc.)
├─ ETL Dashboard: Client-specific logo
└─ Dynamic logo loading based on user's client
```

## 🔄 **Service Details**

### **ETL Service (Embedded)**
- **Technology:** Python FastAPI
- **Port:** 8000
- **Responsibilities:**
  - **Data Processing:**
    - Data extraction from external APIs (Jira, GitHub)
    - Job orchestration and scheduling
    - Real-time progress tracking
    - Checkpoint-based recovery
  - **Embedded Interface:**
    - Admin-only web interface
    - iframe-compatible design
    - Centralized authentication integration
    - Client-specific branding support
  - **API Services:**
    - RESTful APIs for job management
    - WebSocket communication for real-time updates
    - Health monitoring endpoints
    - Admin panel APIs

### **Frontend Service (Unified Platform)**
- **Technology:** React + Vite + TypeScript
- **Port:** 5173
- **Responsibilities:**
  - **Primary Platform Interface:**
    - DORA Metrics Dashboard
    - Engineering Analytics
    - Real-time monitoring
    - User management interface
  - **Embedded ETL Management:**
    - iframe integration with ETL Service
    - Admin-only access control
    - Seamless authentication flow
    - Unified theme and branding
  - **Platform Features:**
    - Client-specific branding
    - Role-based navigation
    - Responsive design
    - Real-time updates

### **Backend Service**
- **Technology:** Node.js + TypeScript
- **Port:** 3001
- **Responsibilities:**
  - API gateway and routing
  - Authentication and authorization
  - User management
  - Session handling

### **AI Service**
- **Technology:** Python FastAPI
- **Port:** 8001
- **Responsibilities:**
  - Machine learning models
  - Data analysis and insights
  - Predictive analytics
  - Report generation

## 🗄️ **Database Schema**

### **Core Tables**

#### **Integration Management**
- `integrations` - API connection configurations
- `job_schedules` - Job execution schedules and status

#### **Jira Data**
- `jira_projects` - Project metadata
- `jira_issues` - Issue data and relationships
- `jira_changelogs` - Issue change history
- `jira_pull_request_links` - Issue-PR relationships

#### **GitHub Data**
- `github_repositories` - Repository metadata
- `github_pull_requests` - PR data and metrics
- `github_commits` - Commit information
- `github_reviews` - PR review data

### **Data Relationships**

```
jira_projects ──┐
                ├── jira_issues ──── jira_changelogs
                └── jira_pull_request_links
                            │
github_repositories ────────┼── github_pull_requests
                            │         │
                            └─────────├── github_commits
                                      └── github_reviews
```

## 🔧 **Job Orchestration**

### **Job Scheduling**
- **Smart Scheduling:** Alternating job execution
- **Status Management:** PENDING → ACTIVE → FINISHED cycle
- **Pause Support:** Jobs can be paused without affecting others
- **Recovery:** Automatic checkpoint-based recovery

### **Job States**
- **PENDING:** Ready to run
- **ACTIVE:** Currently executing
- **FINISHED:** Completed successfully
- **PAUSED:** Temporarily stopped
- **FAILED:** Execution failed

### **Checkpoint System**
- **Fault Tolerance:** Jobs can resume from last checkpoint
- **Progress Tracking:** Granular progress updates
- **Data Integrity:** Consistent state management
- **Recovery Logic:** Automatic failure recovery

## 🌐 **Communication Patterns**

### **REST APIs**
- **Frontend ↔ Backend:** Standard REST API calls
- **Backend ↔ ETL:** Service-to-service communication
- **ETL ↔ AI:** Data processing pipelines

### **WebSocket Communication**
- **Real-time Updates:** Job progress and status
- **Live Monitoring:** Dashboard updates
- **Error Notifications:** Immediate error reporting

### **External API Integration**
- **Jira API:** Issue tracking and project management
- **GitHub API:** Repository and development data
- **Rate Limiting:** Intelligent API usage management
- **Authentication:** Secure token-based access

## 🔒 **Security Architecture**

### **Multi-Client Security Model**
```
Client A User → Frontend → Backend → JWT (client_id=A) → Client A Data Only
Client B User → Frontend → Backend → JWT (client_id=B) → Client B Data Only
```

### **Client Isolation Layers**
1. **Authentication Layer:** JWT tokens include client_id context
2. **Database Layer:** All queries filter by client_id
3. **API Layer:** Endpoints validate client ownership
4. **Job Layer:** Background jobs respect client boundaries

### **Authorization Levels (Per Client)**
- **Admin:** Full access to client's data and settings
- **User:** Standard operations within client scope
- **Viewer:** Read-only access to client data

### **Data Security**
- **Complete Client Isolation:** Zero cross-client data access
- **Client-Scoped Operations:** All database operations filter by client_id
- **Secure Multi-Tenancy:** Enterprise-grade client separation
- **Encrypted Storage:** Sensitive data encryption per client
- **Secure Communication:** HTTPS/TLS for all external calls
- **Token Management:** JWT-based authentication with client context
- **API Security:** Rate limiting and input validation per client

## 📊 **Monitoring & Observability**

### **Health Checks**
- **Service Health:** Individual service status monitoring
- **Database Health:** Connection and performance monitoring
- **API Health:** External API connectivity checks
- **System Resources:** Memory and CPU usage tracking

### **Logging Strategy**
- **Structured Logging:** JSON-formatted logs
- **Log Levels:** DEBUG, INFO, WARNING, ERROR
- **Centralized Logging:** Aggregated log collection
- **Log Rotation:** Automatic log management

### **Metrics Collection**
- **Job Metrics:** Execution time, success rate, error rate
- **API Metrics:** Response time, throughput, error rate
- **System Metrics:** Resource usage, performance indicators
- **Business Metrics:** Data processing volumes, insights generated

## 🚀 **Deployment Architecture**

### **Development Environment**
- **Docker Compose:** Local development orchestration
- **Hot Reload:** Automatic code reloading
- **Debug Mode:** Enhanced logging and debugging
- **Test Data:** Sample data for development

### **Production Considerations**
- **Container Orchestration:** Kubernetes or Docker Swarm
- **Load Balancing:** Service load distribution
- **High Availability:** Multi-instance deployment
- **Backup Strategy:** Database and configuration backups

### **Scaling Strategy**
- **Horizontal Scaling:** Multiple service instances
- **Database Scaling:** Read replicas and partitioning
- **Caching Strategy:** Redis for performance optimization
- **CDN Integration:** Static asset delivery

## 🔧 **Development Patterns**

### **Code Organization**
- **Domain-Driven Design:** Business logic separation
- **Clean Architecture:** Dependency inversion
- **Repository Pattern:** Data access abstraction
- **Service Layer:** Business logic encapsulation

### **API Design**
- **RESTful APIs:** Standard HTTP methods and status codes
- **OpenAPI Specification:** Automated API documentation
- **Versioning Strategy:** API version management
- **Error Handling:** Consistent error response format

### **Testing Strategy**
- **Unit Testing:** Individual component testing
- **Integration Testing:** Service interaction testing
- **End-to-End Testing:** Complete workflow testing
- **Performance Testing:** Load and stress testing

---

**For implementation details, see service-specific documentation in each service directory.**
