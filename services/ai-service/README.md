# AI Service - Machine Learning and Analytics

The AI Service provides machine learning capabilities and advanced analytics for the Pulse Platform. It processes data from the ETL service to generate insights, predictions, and recommendations.

## 🎯 Features

### Core Functionality
- **Data Analysis**: Statistical analysis of software engineering metrics
- **Predictive Models**: ML models for project timeline and risk prediction
- **Anomaly Detection**: Identify unusual patterns in development data
- **Performance Analytics**: Team and project performance insights
- **Recommendation Engine**: Suggestions for process improvements

### Technical Features
- **FastAPI Framework**: High-performance async API
- **scikit-learn**: Machine learning algorithms
- **pandas/numpy**: Data processing and analysis
- **Model Serving**: RESTful endpoints for ML model inference
- **Model Management**: Version control and deployment of ML models

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ETL Service   │    │   AI Service    │    │   Backend API   │
│                 │───►│                 │───►│                 │
│  - Raw Data     │    │  - Analysis     │    │  - Insights     │
│  - Metrics      │    │  - Predictions  │    │  - Reports      │
│  - Events       │    │  - Models       │    │  - Dashboards   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 Project Structure

```
ai-service/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── api/
│   │   ├── __init__.py
│   │   ├── analysis.py         # Analysis endpoints
│   │   ├── models.py           # Model serving endpoints
│   │   └── predictions.py      # Prediction endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Configuration
│   │   ├── logging.py          # Logging setup
│   │   └── etl_client.py       # ETL service client
│   ├── models/
│   │   ├── __init__.py
│   │   ├── timeline_predictor.py
│   │   ├── risk_analyzer.py
│   │   └── performance_analyzer.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── data_processor.py
│   │   ├── model_manager.py
│   │   └── analytics_engine.py
│   └── schemas/
│       ├── __init__.py
│       ├── analysis.py
│       ├── predictions.py
│       └── models.py
├── models/                     # Trained ML models
├── tests/
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

## 🚀 Quick Start

### Using Docker (Recommended)

1. **From the monorepo root**:
```bash
cd pulse-platform
docker-compose up ai-service
```

2. **Access the service**:
- API Documentation: http://localhost:8001/docs
- Health Check: http://localhost:8001/health

### Local Development

1. **Install dependencies**:
```bash
cd services/ai-service
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Run the service**:
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## 📊 API Endpoints

### Analysis
- `POST /api/v1/analysis/project/{project_id}` - Analyze project metrics
- `POST /api/v1/analysis/team/{team_id}` - Analyze team performance
- `GET /api/v1/analysis/trends` - Get trend analysis

### Predictions
- `POST /api/v1/predictions/timeline` - Predict project timeline
- `POST /api/v1/predictions/risk` - Assess project risk
- `POST /api/v1/predictions/velocity` - Predict team velocity

### Models
- `GET /api/v1/models` - List available models
- `POST /api/v1/models/{model_id}/predict` - Make prediction
- `GET /api/v1/models/{model_id}/metrics` - Get model metrics

## 🤖 Machine Learning Models

### Timeline Predictor
- **Purpose**: Predict project completion dates
- **Features**: Historical velocity, story points, team size
- **Algorithm**: Random Forest Regression

### Risk Analyzer
- **Purpose**: Identify project risks
- **Features**: Code complexity, bug rates, team turnover
- **Algorithm**: Gradient Boosting Classifier

### Performance Analyzer
- **Purpose**: Analyze team and individual performance
- **Features**: Commit frequency, PR review time, bug resolution
- **Algorithm**: Clustering and Statistical Analysis

## 🔧 Configuration

### Environment Variables

```bash
# Application Settings
DEBUG=true
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8001

# ETL Service Integration
ETL_SERVICE_URL=http://etl-service:8000
ETL_API_KEY=your_etl_api_key

# Model Configuration
MODEL_STORAGE_PATH=/app/models
MODEL_CACHE_TTL=3600

# Analytics Configuration
ANALYSIS_BATCH_SIZE=1000
PREDICTION_CONFIDENCE_THRESHOLD=0.8
```

## 🧪 Testing

```bash
# Run all tests
python -m pytest

# Run specific test categories
python -m pytest tests/test_models/
python -m pytest tests/test_api/

# With coverage
python -m pytest --cov=app
```

## 📈 Monitoring

- Health checks at `/health`
- Model performance metrics
- Prediction accuracy tracking
- API response time monitoring

## 🔄 Data Flow

1. **Data Ingestion**: Fetch processed data from ETL service
2. **Feature Engineering**: Transform data for ML models
3. **Model Training**: Train/retrain models with new data
4. **Prediction**: Generate predictions and insights
5. **Results**: Serve results via API endpoints

---

**Part of the Pulse Platform - Software Engineering Intelligence**
