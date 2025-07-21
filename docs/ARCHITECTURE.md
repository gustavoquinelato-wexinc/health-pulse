# Pulse Platform - Architecture Documentation

## 🏗️ **System Architecture**

### **Microservices Overview**

The Pulse Platform follows a microservices architecture with clear separation of concerns:

```
Row 1: Application Services
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌───────────────────┐
│  Frontend       │◄──►│  Backend        │◄──►│  ETL Service    │    │  AI Service       │
│  (React/Vite)   │    │  (Node.js)      │    │  (Python)       │    │  (LangGraph)      │
│  Port: 5173     │    │  Port: 3001     │    │  Port: 8000     │    │  Port: 8001       │
│                 │    │                 │    │                 │    │                   │
│ • Dashboard UI  │    │ • API Gateway   │    │ • Data Extract  │    │ • AI Orchestrator │
│ • Real-time UI  │    │ • Authentication│    │ • Job Control   │    │ • Agent Workflows │
│ • Job Management│    │ • User Mgmt     │    │ • Progress Track│    │ • MCP Servers     │
│ • AI Chat (MCP) │◄───┼─ Session Mgmt   │    │ • Recovery      │    │ • Tool Integration│
└─────────────────┘    └─────────────────┘    └─────────────────┘    └───────────────────┘
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

## 🔄 **Service Details**

### **ETL Service (Primary)**
- **Technology:** Python FastAPI
- **Port:** 8000
- **Responsibilities:**
  - Data extraction from external APIs
  - Job orchestration and scheduling
  - Real-time progress tracking
  - Checkpoint-based recovery
  - WebSocket communication

### **Frontend Service**
- **Technology:** React + Vite + TypeScript
- **Port:** 5173
- **Responsibilities:**
  - User interface and dashboard
  - Real-time job monitoring
  - Job management controls
  - Data visualization

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

### **Authentication Flow**
```
User → Frontend → Backend → JWT Token → Protected Resources
```

### **Authorization Levels**
- **Admin:** Full system access
- **User:** Standard operations
- **Viewer:** Read-only access

### **Data Security**
- **Encrypted Storage:** Sensitive data encryption
- **Secure Communication:** HTTPS/TLS for all external calls
- **Token Management:** JWT-based authentication
- **API Security:** Rate limiting and input validation

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
