# Backend Service - Pulse Platform

A specialized Python/FastAPI backend service providing analytics APIs, authentication, and serving as the primary API gateway for the React frontend.

## 🎯 Overview

The Backend Service serves as the primary interface between the frontend and data layer, specializing in:
- **Complex Analytics**: DORA metrics, statistical calculations, data aggregations
- **API Gateway**: Unified API layer for frontend applications
- **Authentication**: JWT-based user authentication and authorization
- **Performance Optimization**: Query caching, connection pooling, response optimization
- **ETL Coordination**: Settings management and job coordination with ETL service

## 🏗️ Architecture

### **Service Specialization**
```
Frontend ──► Analytics Backend ──► PostgreSQL Database
    │              │                       │
    │              ├─ Complex Calculations │
    │              ├─ Data Aggregations    │
    │              ├─ Query Optimization   │
    │              └─ Caching Layer        │
    │                       │
    └─────────────────────► ETL Service (Job Coordination)
```

### **Technology Stack**
- **FastAPI** - Modern, fast web framework with automatic API documentation
- **SQLAlchemy** - Advanced ORM for complex analytical queries
- **Pydantic** - Data validation and serialization
- **NumPy/Pandas** - Data processing and statistical analysis
- **Redis** - Caching and session management
- **PostgreSQL** - Primary database with connection pooling

### **Core Responsibilities**
1. **Data Analytics**: Complex calculations, metrics, and statistical analysis
2. **API Gateway**: Unified interface for frontend applications
3. **Authentication**: User management and JWT token handling
4. **Performance**: Query optimization, caching, and response time optimization
5. **ETL Integration**: Configuration management and job coordination

## 🚀 Quick Start

### **Prerequisites**
- Python 3.11+
- PostgreSQL database (shared with ETL service)
- Redis for caching
- ETL Service running for job coordination

### **Development Setup**
```bash
cd services/analytics-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configuration is managed centrally at root level
# Edit the root .env file: ../../.env

# Run development server
uvicorn app.main:app --reload --port 3001

# Access API documentation
open http://localhost:3001/docs
```

## 📊 Analytics Capabilities

### **DORA Metrics**
- **Lead Time**: Time from commit to production deployment
- **Deployment Frequency**: How often deployments occur
- **Mean Time to Recovery (MTTR)**: Time to recover from failures
- **Change Failure Rate**: Percentage of deployments causing failures

### **GitHub Analytics**
- **Code Quality Metrics**: PR review times, code coverage, complexity
- **Contributor Analysis**: Activity patterns, collaboration metrics
- **Repository Insights**: Commit patterns, branch strategies, release cycles

### **Portfolio Analytics**
- **Cross-Project Metrics**: Aggregated performance across projects
- **Team Performance**: Velocity, quality, and delivery metrics
- **Business Alignment**: Feature delivery vs business objectives

### **Executive Dashboards**
- **C-Level KPIs**: High-level business and technical metrics
- **Trend Analysis**: Historical performance and predictive insights
- **Risk Assessment**: Identification of potential issues and bottlenecks

## 🔧 Configuration

### **Environment Variables**
Configuration is managed through the **centralized `.env` file** at the root level (`../../.env`).

Key variables used by the Analytics Backend:
```env
# Database Configuration (shared with ETL service)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=pulse_user
POSTGRES_PASSWORD=pulse_password
POSTGRES_DATABASE=pulse_db

# Redis Configuration (shared)
REDIS_URL=redis://localhost:6379

# JWT Configuration (shared)
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Service Integration
ETL_SERVICE_URL=http://localhost:8000

# API Configuration
API_V1_PREFIX=/api/v1
CORS_ORIGINS=["http://localhost:5173"]
```

**Important**: Do not create a local `.env` file. All configuration is centralized in the root `.env` file.

## 🏛️ Architecture Rationale

### **Why Python for Analytics?**
1. **Data Processing Excellence**: NumPy, Pandas, SciPy for advanced analytics
2. **Database Operations**: SQLAlchemy for complex analytical queries
3. **Statistical Analysis**: Rich ecosystem for mathematical computations
4. **Performance**: Optimized libraries for data-intensive operations
5. **Ecosystem Alignment**: Shared technology stack with ETL service

### **Service Separation Benefits**
- **ETL Service**: Specialized for data engineering (extraction, loading, orchestration)
- **Analytics Backend**: Specialized for data consumption (calculations, API serving)
- **Different Scaling**: ETL optimized for throughput, Analytics for latency
- **Independent Deployment**: Services can be updated and scaled independently

## 🔗 Integration Points

### **Frontend Integration**
- **RESTful APIs**: JSON-based API communication
- **Authentication**: JWT token-based authentication
- **Real-time Updates**: WebSocket support for live data
- **Error Handling**: Comprehensive error responses and logging

### **ETL Service Coordination**
- **Job Management**: Trigger and monitor ETL jobs
- **Configuration**: Manage ETL settings and parameters
- **Status Monitoring**: Real-time job status and progress tracking

### **Database Access**
- **Shared Schema**: Uses same database as ETL service
- **Optimized Queries**: Complex analytical queries with proper indexing
- **Connection Pooling**: Efficient database connection management

## 📚 API Documentation

### **Automatic Documentation**
- **OpenAPI/Swagger**: http://localhost:3001/docs
- **ReDoc**: http://localhost:3001/redoc
- **JSON Schema**: http://localhost:3001/openapi.json

### **Key Endpoints**
- **Authentication**: `/api/v1/auth/*`
- **DORA Metrics**: `/api/v1/metrics/dora/*`
- **GitHub Analytics**: `/api/v1/analytics/github/*`
- **Portfolio Data**: `/api/v1/portfolio/*`
- **ETL Management**: `/api/v1/etl/*`

---

**Note**: This service is designed to be the primary backend for the React frontend, providing optimized analytics capabilities and serving as the main API gateway for the Pulse Platform.
