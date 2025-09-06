# Phase 1-1: Database Schema Enhancement

**Implemented**: YES ✅
**Duration**: Days 1-2
**Priority**: CRITICAL
**Dependencies**: None
**Must Complete Before**: Phase 1-2 (Unified Models)

## 🎯 Objectives

1. **Enhanced Migration 0001**: Create clean schema with vector columns integrated
2. **ML Monitoring Tables**: Add AI learning and prediction logging infrastructure
3. **Vector Indexes**: Create HNSW indexes for similarity search
4. **PostgresML Preparation**: Upgrade replica for ML capabilities with full ML dependencies
5. **ML Dependencies Installation**: Install XGBoost, LightGBM, and scikit-learn for Phase 3 readiness
6. **Clean Execution**: No ALTER statements, only CREATE statements

## 📋 Implementation Tasks

### Task 1-1.1: Enhanced Migration Script
**File**: `services/backend-service/scripts/migrations/0001_initial_schema.py`

**Objective**: Create complete schema with vector columns integrated

**Changes Required**:
- Include `embedding vector(1536)` in all 24 existing business table CREATE statements
- Add 3 ML monitoring tables (without embedding columns - they're for system monitoring)
- Create all indexes after table creation
- Maintain clean, readable structure

### Task 1-1.2: Docker Infrastructure Update
**Files**:
- `docker-compose.yml`
- `docker/postgres/init-postgresml.sql`
- `docker/postgres/custom-entrypoint.sh`

**Objective**: Prepare PostgresML infrastructure for ML capabilities

**Changes Required**:
- Update both primary and replica to `postgresml/postgresml:2.10.0` for consistency
- Add PostgresML initialization script to both databases
- Use custom entrypoint to avoid dashboard startup issues
- Primary database: Full ML capabilities (training, inference)
- Replica database: Same extensions available (read-only operations, inference only)
- Maintain existing port mappings and volumes

### Task 1-1.3: ML Dependencies Installation
**Objective**: Install required ML libraries for Phase 3 readiness

**Dependencies to Install**:
- **XGBoost**: Required for trajectory forecasting and complexity estimation models
- **LightGBM**: Required for PR rework classification model
- **scikit-learn**: Required for data preprocessing and model validation
- **Additional ML libraries**: pandas, numpy (usually pre-installed)

**Installation Commands**:
```bash
# Install in PostgresML container after startup
docker exec pulse-postgres-primary pip3 install xgboost lightgbm scikit-learn

# Verify installation
docker exec pulse-postgres-primary python3 -c "import xgboost, lightgbm, sklearn; print('All ML dependencies installed successfully')"
```

## 🔧 Implementation Details

### Migration Structure
```sql
-- 1. Extensions
CREATE EXTENSION IF NOT EXISTS pgvector;
CREATE EXTENSION IF NOT EXISTS postgresml;  -- Optional for Phase 1

-- 2. All existing tables (with vector columns in CREATE statements)
CREATE TABLE IF NOT EXISTS clients (
    -- all existing fields
    embedding vector(1536)  -- included in creation
);

CREATE TABLE IF NOT EXISTS issues (
    -- all existing fields
    embedding vector(1536)  -- included in creation
);
-- ... (all 24 tables)

-- 3. ML monitoring tables (after existing tables)
CREATE TABLE IF NOT EXISTS ai_learning_memory (...);
CREATE TABLE IF NOT EXISTS ml_prediction_log (...);
CREATE TABLE IF NOT EXISTS ml_anomaly_alerts (...);

-- 4. All indexes (after all tables)
-- Existing business indexes
-- Vector indexes for all 24 tables
-- ML monitoring indexes
```

### Tables with Vector Columns (All 24)
1. clients
2. users
3. projects
4. issues
5. repositories
6. pull_requests
7. pull_request_comments
8. pull_request_reviews
9. pull_request_commits
10. statuses
11. status_mappings
12. issuetypes
13. issuetype_mappings
14. issuetype_hierarchies
15. workflows
16. issue_changelogs
17. jira_pull_request_links
18. projects_issuetypes
19. projects_statuses
20. user_permissions
21. user_sessions
22. system_settings
23. dora_market_benchmarks
24. dora_metric_insights

### ML Monitoring Tables
```sql
-- AI Learning Memory
CREATE TABLE IF NOT EXISTS ai_learning_memory (
    id SERIAL PRIMARY KEY,
    error_type VARCHAR(50) NOT NULL,
    user_intent TEXT NOT NULL,
    failed_query TEXT NOT NULL,
    specific_issue TEXT NOT NULL,
    suggested_fix TEXT NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    learning_context JSONB,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ML Prediction Log
CREATE TABLE IF NOT EXISTS ml_prediction_log (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    prediction_value FLOAT NOT NULL,
    input_features JSONB,
    anomaly_score FLOAT,
    is_anomaly BOOLEAN DEFAULT FALSE,
    severity VARCHAR(20) DEFAULT 'normal' CHECK (severity IN ('normal', 'warning', 'critical')),
    response_time_ms INTEGER,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ML Anomaly Alerts
CREATE TABLE IF NOT EXISTS ml_anomaly_alerts (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    alert_data JSONB NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by INTEGER REFERENCES users(id),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Docker Configuration
```yaml
# docker-compose.yml - Main database update for ML support
postgres:
  image: postgresml/postgresml:latest  # Updated for ML support
  container_name: pulse-postgres
  environment:
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  ports:
    - "5432:5432"
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - ./docker/postgres/init-postgresml.sql:/docker-entrypoint-initdb.d/init-postgresml.sql

# Replica with same image for consistency (read-only, but same extensions available)
postgres-replica:
  image: postgresml/postgresml:latest  # Same as primary for consistency
  container_name: pulse-postgres-replica
  environment:
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  ports:
    - "5435:5432"
  volumes:
    - postgres_replica_data:/var/lib/postgresql/data
    - ./docker/postgres/init-postgresml.sql:/docker-entrypoint-initdb.d/init-postgresml.sql
```

## ✅ Success Criteria

1. **Migration Execution**: Runs successfully on empty and existing databases
2. **Schema Validation**: All 24 tables have vector columns
3. **ML Tables**: All 3 ML monitoring tables created
4. **Indexes**: Vector and ML indexes created successfully
5. **PostgresML**: Replica upgraded and accessible
6. **ML Dependencies**: XGBoost, LightGBM, and scikit-learn installed and verified
7. **Extensions**: Vector and pgml extensions created successfully
8. **No Errors**: Clean execution without failures

## 🚨 Risk Mitigation

1. **Transaction Safety**: Single transaction with rollback capability
2. **Validation**: Comprehensive post-migration checks
3. **Backup Strategy**: Migration can be rolled back cleanly
4. **Testing**: Thorough testing on staging environment first

## 📝 Testing Checklist

- [ ] Migration runs on empty database
- [ ] Migration runs on database with existing data
- [ ] All 24 tables created with vector columns
- [ ] ML monitoring tables created
- [ ] Vector indexes created (HNSW)
- [ ] ML monitoring indexes created
- [ ] PostgresML extension available (if replica upgraded)
- [ ] XGBoost, LightGBM, scikit-learn installed and importable
- [ ] Vector extension working (test vector operations)
- [ ] pgml extension working (test basic ML functions)
- [ ] No migration errors or warnings
- [ ] Database performance acceptable
- [ ] Rollback capability verified

## 🔄 Completion Enables

- **Phase 1-2**: Unified Models can be updated to match new schema
- **Phase 1-3**: ETL jobs can be updated for schema compatibility
- **Phase 1-4**: Backend APIs can handle new tables/columns
- **Phase 1-5**: Auth service can work with enhanced user schema
- **Phase 1-6**: Frontend can be updated for new data structure

## 📋 Migration Execution

Use the existing migration system:
**File**: `services/backend-service/scripts/migration_runner.py`

**Usage**:
```bash
# Execute enhanced migration 0001
cd services/backend-service
python scripts/migration_runner.py

# The enhanced 0001_initial_db_schema.py should include:
# - All existing table CREATE statements with embedding vector(1536) added
# - ML monitoring tables (ai_learning_memory, ml_prediction_log, ml_anomaly_alerts)
# - Vector indexes (HNSW) for all tables
# - ML monitoring indexes
```

**Migration 0001 Enhancement Required**:
- Update existing CREATE TABLE statements to include `embedding vector(1536)`
- Add ML monitoring tables after existing tables
- Add vector and ML indexes after table creation
- Follow existing migration patterns and structure

## 📋 Handoff to Phase 1-2

**Deliverables**:
- ✅ Enhanced database schema with vector columns
- ✅ ML monitoring tables ready
- ✅ Vector indexes operational
- ✅ PostgresML infrastructure prepared with full ML dependencies
- ✅ XGBoost, LightGBM, and scikit-learn installed and verified
- ✅ Migration script ready for execution

**Next Phase Requirements**:
- Update unified models in backend and ETL services
- Ensure model compatibility with new schema
- Test model instantiation and serialization
