# Backend Service - Pulse Platform

A specialized Python/FastAPI backend service providing analytics APIs, authentication, and serving as the primary API gateway for the React frontend.

## 🎯 Overview

The Backend Service serves as the primary interface between the frontend and data layer, specializing in:
- **Complex Analytics**: DORA metrics, statistical calculations, data aggregations
- **API Gateway**: Unified API layer for frontend applications
- **Authentication**: JWT-based user authentication and authorization
- **Performance Optimization**: Query caching, connection pooling, response optimization
- **ETL Backend**: Complete ETL processing through /app/etl/* endpoints
- **ML Monitoring**: AI performance metrics, anomaly detection, and learning memory (Phase 1+)
- **Vector Operations**: Semantic search and similarity analysis infrastructure (Phase 1+)
- **AI Validation**: SQL syntax/semantic validation with self-healing capabilities (Phase 2)

## 🏗️ Architecture

### **Service Specialization with AI Enhancement**
```
Frontend ──► Analytics Backend ──► PostgreSQL Database (Enhanced)
    │              │                       │
    │              ├─ Complex Calculations │
    │              ├─ Data Aggregations    │
    │              ├─ Query Optimization   │
    │              ├─ Caching Layer        │
    │              ├─ ML Monitoring APIs   │ ← Phase 1
    │              ├─ Vector Operations    │ ← Phase 1
    │              └─ ETL Processing       │ ← /app/etl/*
    │                       │
    │                       ├─ pgvector (similarity search)
    │                       ├─ postgresml (ML capabilities)
    │                       ├─ ML monitoring tables
    │                       └─ RabbitMQ Queue System
    │
    ETL Frontend ──────────► Backend ETL Endpoints (/app/etl/*)
                            │
                            └─► AI Service (Phase 2+)
```

### **Technology Stack**
- **FastAPI** - Modern, fast web framework with automatic API documentation
- **SQLAlchemy** - Advanced ORM for complex analytical queries with vector support
- **Pydantic** - Data validation and serialization (enhanced for AI validation schemas)
- **sqlglot** - SQL parsing and syntax validation for AI-generated queries
- **NumPy/Pandas** - Data processing and statistical analysis *(recently added)*
- **WebSockets** - Real-time updates and notifications *(recently added)*
- **Redis** - Caching and session management
- **PostgreSQL** - Primary database with connection pooling
- **pgvector** - Vector similarity search and storage *(Phase 1)*
- **postgresml** - Machine learning capabilities *(Phase 1 - prepared)*
- **Vector Operations** - Semantic search infrastructure *(Phase 1)*

### **Core Responsibilities**
1. **Data Analytics**: Complex calculations, metrics, and statistical analysis
2. **API Gateway**: Unified interface for frontend applications
3. **Authentication**: User management and JWT token handling
4. **Performance**: Query optimization, caching, and response time optimization
5. **ETL Integration**: Configuration management and job coordination
6. **ML Monitoring**: AI performance metrics, anomaly detection, and learning memory *(Phase 1)*
7. **Vector Operations**: Semantic search and similarity analysis infrastructure *(Phase 1)*
8. **AI Integration**: Coordination with AI service for ML capabilities *(Phase 2+)*

## 🚀 Quick Start

### **Prerequisites**
- Python 3.11+
- PostgreSQL database (shared with ETL frontend)
- Redis for caching
- ETL Frontend running for ETL management interface

### **Development Setup**

#### **Quick Setup (Recommended)**
```bash
# From project root - sets up ALL services
python scripts/setup_development.py

# Then start backend service
cd services/backend-service
venv/Scripts/activate  # Windows
source venv/bin/activate  # Unix/Linux/macOS
uvicorn app.main:app --reload --port 3001
```

#### **Manual Setup (Alternative)**
```bash
cd services/backend-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies using centralized requirements
pip install -r ../../requirements/backend-service.txt

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
- **ETL Management**: `/app/etl/*`
- **ML Monitoring**: `/api/v1/ml/*` *(Phase 1)*
- **Health Checks**: `/health/database`, `/health/ml` *(Phase 1)*

## 🤖 AI Enhancements (Phase 1)

### **Clean Data Models (Phase 3-1)**
All unified models use clean PostgreSQL schema with Qdrant for vector storage:
```python
# Example: Clean Issue model (Phase 3-1)
class Issue(Base):
    # ... business fields only ...
    # Vector storage handled separately in Qdrant

    def to_dict(self):
        result = {
            # ... business fields only ...
        }
        return result
```

### **ML Monitoring APIs**
New endpoints for AI monitoring and management:
- **AI Learning Memory**: `/api/v1/ml/learning-memory` - User feedback and corrections
- **AI Predictions**: `/api/v1/ml/predictions` - ML model predictions and accuracy
- **Performance Metrics**: `/api/v1/ml/performance` - AI system performance monitoring
- **Anomaly Alerts**: `/api/v1/ml/anomalies` - ML-detected anomalies and alerts

### **AI Validation Endpoints (Phase 2)**
- **SQL Syntax Validation**: `/api/v1/ai/validate/sql-syntax` - PostgreSQL syntax checking with security validation
- **Semantic Validation**: `/api/v1/ai/validate/sql-semantics` - Intent matching and confidence scoring
- **Data Structure Validation**: `/api/v1/ai/validate/data-structure` - Schema validation for query results
- **Learning Memory**: `/api/v1/ai/learning/record-feedback` - Record validation failures for learning
- **Healing Suggestions**: `/api/v1/ai/learning/healing-suggestions` - Pattern-based query improvement suggestions

### **Vector Search Infrastructure**
Prepared for semantic search capabilities:
```python
# Vector similarity search (Phase 2+)
async def find_similar_issues(embedding: List[float], client_id: int, limit: int = 10):
    query = """
        SELECT id, summary, embedding <-> %s::vector AS distance
        FROM issues
        WHERE client_id = %s AND embedding IS NOT NULL
        ORDER BY distance
        LIMIT %s
    """
    return await execute_vector_query(query, [embedding, client_id, limit])
```

### **Health Check Enhancements**
Enhanced health checks for AI infrastructure:
```python
# Database health with ML monitoring
GET /health/database
{
    "status": "healthy",
    "database_connection": "ok",
    "ml_tables": {
        "ai_learning_memory": "available",
        "ai_predictions": "available",
        "ai_performance_metrics": "available",
        "ml_anomaly_alert": "available"
    },
    "vector_columns": {
        "tables_with_embeddings": 24,
        "total_embeddings": 0  // Phase 1: Not populated yet
    }
}

# ML infrastructure health
GET /health/ml
{
    "status": "healthy",
    "pgvector": {"available": true},
    "postgresml": {"available": false, "note": "Prepared for Phase 2+"},
    "vector_indexes": {"created": true, "count": 24},
    "ai_service_connection": {"status": "not_configured"}  // Phase 2+
}
```

### **Phase Implementation Status**

#### ✅ Phase 1 (Completed)
- **Enhanced Database Schema**: Vector columns in all 24 business tables
- **ML Monitoring Tables**: AI learning memory, predictions, performance metrics, anomaly alerts
- **Updated Models**: All unified models support vector columns and ML entities
- **Health Monitoring**: Database and ML infrastructure health checks
- **API Framework**: ML monitoring endpoints structure prepared

#### ✅ Phase 2 (Implemented)
- **AI Validation Layer**: SQL syntax validation using sqlglot with PostgreSQL compatibility
- **Semantic Validation**: Intent matching and confidence scoring for AI-generated queries
- **Self-Healing Memory**: Pattern recognition and learning from validation failures
- **Data Structure Validation**: Pydantic schemas for TeamAnalysis, DORA metrics, and Rework analysis
- **Validation API Endpoints**: REST APIs for syntax, semantic, and data structure validation
- **Enhanced Learning Memory**: Validation-specific columns and pattern tracking tables

#### 🔄 Phase 3+ (Future)
- **Embedding Generation**: Automatic text-to-vector conversion
- **Semantic Search**: Content similarity and discovery APIs
- **AI Service Integration**: Coordination with dedicated AI service
- **Predictive Analytics**: Story point estimation and timeline forecasting

---

**Note**: This service is designed to be the primary backend for the React frontend, providing optimized analytics capabilities and serving as the main API gateway for the Pulse Platform. With Phase 1 AI enhancements, it now includes comprehensive ML monitoring infrastructure and vector search capabilities.
