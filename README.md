# Kairus Platform - Software Engineering Intelligence Platform

A comprehensive monorepo containing four microservices for software engineering intelligence and analytics.

## 🏗️ Architecture Overview

The Kairus Platform is designed as a microservices architecture with the following components:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend App  │    │  Backend API    │    │   AI Service    │
│   (React/Next)  │◄──►│     (BFF)       │◄──►│   (Python)      │
│                 │    │   (Node.js)     │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   ETL Service   │◄──►│   Snowflake     │
                       │   (FastAPI)     │    │  Data Warehouse │
                       └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │      Jira       │
                       │   (Data Source) │
                       └─────────────────┘
```

## 📁 Project Structure

```
kairus-platform/
├── services/
│   ├── etl-service/          # Python FastAPI - Data extraction and loading
│   ├── ai-service/           # Python FastAPI - AI/ML processing
│   ├── backend-service/      # Node.js Express - Backend for Frontend (BFF)
│   └── frontend-app/         # React/Next.js - User interface
├── .gitignore
├── docker-compose.yml        # Orchestration for all services
└── README.md
```

## 🚀 Services Overview

### 1. ETL Service (Python/FastAPI)
**Primary Focus** - Complete implementation for Jira data extraction to Snowflake
- **Technology**: Python 3.13, FastAPI, SQLAlchemy
- **Features**:
  - Deep Jira data extraction (including dev_status endpoint)
  - Snowflake Data Warehouse integration
  - Scheduled ETL jobs with APScheduler
  - Comprehensive caching system
  - Security middleware and validation
  - Health monitoring and logging
- **Port**: 8000

### 2. AI Service (Python/FastAPI)
**Functional Skeleton** - AI/ML processing capabilities
- **Technology**: Python 3.11+, FastAPI, scikit-learn, pandas
- **Features**:
  - Data analysis endpoints
  - Machine learning model serving
  - Integration with ETL service data
  - Prediction and analytics APIs
- **Port**: 8001

### 3. Backend Service (Node.js/Express)
**Functional Skeleton** - Backend for Frontend (BFF)
- **Technology**: Node.js, Express, TypeScript
- **Features**:
  - API aggregation layer
  - Authentication and authorization
  - Business logic orchestration
  - Integration with ETL and AI services
- **Port**: 3000

### 4. Frontend App (React/Next.js)
**Functional Skeleton** - User interface
- **Technology**: React, Next.js, TypeScript, Tailwind CSS
- **Features**:
  - Dashboard for data visualization
  - ETL job monitoring
  - AI insights display
  - Responsive design
- **Port**: 3001

## 🐳 Quick Start with Docker

1. **Clone the repository**:
```bash
git clone <repository-url>
cd kairus-platform
```

2. **Start all services**:
```bash
docker-compose up -d
```

3. **Access the services**:
- Frontend: http://localhost:3001
- Backend API: http://localhost:3000
- ETL Service: http://localhost:8000
- AI Service: http://localhost:8001

## 🔧 Development Setup

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)

### Environment Configuration

Create `.env` files in each service directory:

```bash
# Copy example environment files
cp services/etl-service/.env.example services/etl-service/.env
cp services/ai-service/.env.example services/ai-service/.env
cp services/backend-service/.env.example services/backend-service/.env
cp services/frontend-app/.env.example services/frontend-app/.env
```

### Individual Service Development

Each service can be developed independently:

```bash
# ETL Service
cd services/etl-service
python -m uvicorn app.main:app --reload

# AI Service
cd services/ai-service
python -m uvicorn app.main:app --reload

# Backend Service
cd services/backend-service
npm run dev

# Frontend App
cd services/frontend-app
npm run dev
```

## 📊 Data Flow

1. **ETL Service** extracts data from Jira (including dev_status)
2. **ETL Service** transforms and loads data into Snowflake
3. **AI Service** processes data for insights and predictions
4. **Backend Service** aggregates data from ETL and AI services
5. **Frontend App** displays dashboards and analytics

## 🔐 Security Features

- JWT authentication across services
- API rate limiting
- Input validation and sanitization
- CORS configuration
- Security headers middleware
- Environment-based configuration

## 📈 Monitoring & Observability

- Health check endpoints for all services
- Structured logging with correlation IDs
- Performance metrics collection
- Error tracking and alerting

## 🧪 Testing

Run tests for all services:

```bash
# Run all tests
docker-compose -f docker-compose.test.yml up

# Individual service tests
cd services/etl-service && python -m pytest
cd services/ai-service && python -m pytest
cd services/backend-service && npm test
cd services/frontend-app && npm test
```

## 📚 Documentation

- [ETL Service Documentation](./services/etl-service/README.md)
- [AI Service Documentation](./services/ai-service/README.md)
- [Backend Service Documentation](./services/backend-service/README.md)
- [Frontend App Documentation](./services/frontend-app/README.md)

## 🤝 Contributing

Please read [CONTRIBUTING.md](./CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

## 🆘 Support

For support and questions:
- Create an issue in this repository
- Check the individual service documentation
- Review the troubleshooting guides in each service

---

**Built with ❤️ for Software Engineering Intelligence**
