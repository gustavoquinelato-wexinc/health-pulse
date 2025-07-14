# Backend Service - Backend for Frontend (BFF)

The Backend Service acts as a Backend for Frontend (BFF), providing a unified API layer that aggregates data from the ETL and AI services. It handles authentication, authorization, and business logic orchestration.

## 🎯 Features

### Core Functionality
- **API Aggregation**: Unified interface to ETL and AI services
- **Authentication & Authorization**: JWT-based user authentication
- **Business Logic**: Complex workflows and data orchestration
- **Caching**: Response caching for improved performance
- **Rate Limiting**: API rate limiting and throttling

### Technical Features
- **Express.js Framework**: Fast, minimalist web framework
- **TypeScript**: Type-safe development
- **JWT Authentication**: Secure token-based authentication
- **PostgreSQL Integration**: User and session management
- **Redis Caching**: High-performance caching layer

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Frontend App   │    │ Backend Service │    │   ETL Service   │
│                 │◄──►│      (BFF)      │◄──►│                 │
│  - React/Next   │    │  - Auth         │    │  - Data Ext.    │
│  - Dashboard    │    │  - Aggregation  │    │  - Jobs         │
│  - UI/UX        │    │  - Business     │    │  - Snowflake    │
└─────────────────┘    │    Logic        │    └─────────────────┘
                       │                 │    ┌─────────────────┐
                       │                 │◄──►│   AI Service    │
                       │                 │    │                 │
                       └─────────────────┘    │  - ML Models    │
                                              │  - Analytics    │
                                              │  - Predictions  │
                                              └─────────────────┘
```

## 📁 Project Structure

```
backend-service/
├── src/
│   ├── app.ts                  # Express application setup
│   ├── server.ts               # Server entry point
│   ├── config/
│   │   ├── database.ts         # Database configuration
│   │   ├── redis.ts            # Redis configuration
│   │   └── services.ts         # External services config
│   ├── controllers/
│   │   ├── auth.controller.ts
│   │   ├── etl.controller.ts
│   │   ├── ai.controller.ts
│   │   └── dashboard.controller.ts
│   ├── middleware/
│   │   ├── auth.middleware.ts
│   │   ├── cors.middleware.ts
│   │   ├── rate-limit.middleware.ts
│   │   └── error.middleware.ts
│   ├── routes/
│   │   ├── auth.routes.ts
│   │   ├── etl.routes.ts
│   │   ├── ai.routes.ts
│   │   └── dashboard.routes.ts
│   ├── services/
│   │   ├── auth.service.ts
│   │   ├── etl.service.ts
│   │   ├── ai.service.ts
│   │   └── cache.service.ts
│   ├── models/
│   │   ├── user.model.ts
│   │   └── session.model.ts
│   ├── types/
│   │   ├── auth.types.ts
│   │   ├── etl.types.ts
│   │   └── ai.types.ts
│   └── utils/
│       ├── logger.ts
│       ├── validation.ts
│       └── helpers.ts
├── tests/
├── db/
│   └── init.sql               # Database initialization
├── package.json
├── tsconfig.json
├── Dockerfile
├── .env.example
└── README.md
```

## 🚀 Quick Start

### Using Docker (Recommended)

1. **From the monorepo root**:
```bash
cd kairus-platform
docker-compose up backend-service
```

2. **Access the service**:
- API Base URL: http://localhost:3000
- Health Check: http://localhost:3000/health
- API Documentation: http://localhost:3000/api-docs

### Local Development

1. **Install dependencies**:
```bash
cd services/backend-service
npm install
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Run the service**:
```bash
npm run dev
```

## 📊 API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `POST /api/auth/refresh` - Refresh JWT token
- `GET /api/auth/profile` - Get user profile

### ETL Operations
- `GET /api/etl/jobs` - List ETL jobs
- `POST /api/etl/jobs` - Start new ETL job
- `GET /api/etl/jobs/{id}` - Get job details
- `GET /api/etl/integrations` - List integrations

### AI Analytics
- `GET /api/ai/analysis/{projectId}` - Get project analysis
- `POST /api/ai/predictions/timeline` - Get timeline predictions
- `GET /api/ai/models` - List available models
- `POST /api/ai/analysis/custom` - Custom analysis request

### Dashboard
- `GET /api/dashboard/overview` - Dashboard overview data
- `GET /api/dashboard/metrics` - Key metrics summary
- `GET /api/dashboard/projects` - Projects dashboard data
- `GET /api/dashboard/teams` - Teams performance data

## 🔧 Configuration

### Environment Variables

```bash
# Application Settings
NODE_ENV=development
PORT=3000
API_PREFIX=/api

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/kairus
DB_POOL_SIZE=10

# Redis Configuration
REDIS_URL=redis://localhost:6379
CACHE_TTL=3600

# JWT Configuration
JWT_SECRET=your-jwt-secret
JWT_EXPIRES_IN=24h
JWT_REFRESH_EXPIRES_IN=7d

# External Services
ETL_SERVICE_URL=http://etl-service:8000
AI_SERVICE_URL=http://ai-service:8001
ETL_API_KEY=your-etl-api-key
AI_API_KEY=your-ai-api-key

# CORS Configuration
CORS_ORIGIN=http://localhost:3001
CORS_CREDENTIALS=true

# Rate Limiting
RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX_REQUESTS=100
```

## 🔐 Authentication Flow

1. **User Login**: Validate credentials and issue JWT
2. **Token Validation**: Middleware validates JWT on protected routes
3. **Token Refresh**: Automatic token refresh mechanism
4. **Session Management**: Track active sessions in Redis

## 🔄 Data Aggregation

The BFF aggregates data from multiple sources:

1. **ETL Service**: Job status, integration data, raw metrics
2. **AI Service**: Analysis results, predictions, model outputs
3. **Local Database**: User data, preferences, cached results
4. **External APIs**: Additional data sources as needed

## 🧪 Testing

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run specific test suites
npm run test:unit
npm run test:integration
```

## 📈 Monitoring

- Health checks at `/health`
- Request/response logging
- Performance metrics collection
- Error tracking and alerting

## 🔒 Security Features

- JWT token authentication
- Rate limiting per IP/user
- Input validation and sanitization
- CORS configuration
- Security headers
- SQL injection prevention

## 🚀 Deployment

### Production Build

```bash
npm run build
npm start
```

### Docker Deployment

```bash
docker build -t kairus-backend .
docker run -p 3000:3000 kairus-backend
```

---

**Part of the Kairus Platform - Software Engineering Intelligence**
