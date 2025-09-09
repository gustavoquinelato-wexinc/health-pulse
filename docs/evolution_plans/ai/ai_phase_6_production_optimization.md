# Phase 5: Production Optimization & Deployment

**Duration**: Weeks 9-10  
**Priority**: CRITICAL  
**Risk Level**: LOW  

## 🎯 Objectives

1. **Performance Optimization**: Optimize all AI components for production scale
2. **Automated Retraining**: Implement automated ML model retraining pipelines
3. **Comprehensive Monitoring**: Full observability across all AI components
4. **Production Deployment**: Deploy AI system to production with confidence
5. **User Training & Documentation**: Enable users to leverage AI capabilities

## 📋 Task Breakdown

### Task 5.1: Performance Optimization
**Duration**: 3-4 days  
**Priority**: CRITICAL  

#### Database Query Optimization
```sql
-- Optimize prediction queries with proper indexing
-- services/backend-service/scripts/optimization/ml_indexes.sql

-- Trajectory prediction optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issues_trajectory_prediction 
ON issues (issuetype_id, total_lead_time_seconds, work_last_completed_at, active, client_id) 
WHERE active = true AND total_lead_time_seconds > 0;

-- Complexity estimation optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_issues_complexity_estimation 
ON issues (story_points, issuetype_id, created, active, client_id) 
WHERE active = true AND story_points IS NOT NULL;

-- Rework prediction optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pr_rework_prediction 
ON pull_requests (merged_at, review_cycles, rework_commit_count, active, repository_id) 
WHERE active = true AND merged_at IS NOT NULL;

-- ML prediction log optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_prediction_log_performance 
ON ml_prediction_log (model_name, created_at, client_id, is_anomaly) 
WHERE active = true;

-- Materialized view for training data summary (CLIENT-SPECIFIC)
-- NOTE: This view needs to be created per client or queried with client_id filter
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_ml_training_summary AS
SELECT
    'trajectory' as model_type,
    client_id,
    COUNT(*) as training_records,
    MAX(work_last_completed_at) as latest_data,
    AVG(total_lead_time_seconds) as avg_lead_time,
    STDDEV(total_lead_time_seconds) as stddev_lead_time
FROM issues
WHERE issuetype_id IN (SELECT id FROM issuetypes WHERE original_name = 'Epic')
    AND total_lead_time_seconds > 0
    AND active = true
GROUP BY client_id
UNION ALL
SELECT
    'complexity' as model_type,
    client_id,
    COUNT(*) as training_records,
    MAX(created) as latest_data,
    AVG(story_points) as avg_story_points,
    STDDEV(story_points) as stddev_story_points
FROM issues
WHERE story_points IS NOT NULL AND active = true
GROUP BY client_id
UNION ALL
SELECT
    'rework' as model_type,
    client_id,
    COUNT(*) as training_records,
    MAX(merged_at) as latest_data,
    AVG(CASE WHEN review_cycles > 2 OR rework_commit_count > 3 THEN 1.0 ELSE 0.0 END) as rework_rate,
    NULL as stddev_value
FROM pull_requests
WHERE merged_at IS NOT NULL AND active = true
GROUP BY client_id;

-- Refresh materialized view daily
CREATE OR REPLACE FUNCTION refresh_ml_training_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_ml_training_summary;
END;
$$ LANGUAGE plpgsql;
```

#### AI Service Performance Optimization
```python
# services/ai-service/app/core/performance_optimizer.py

class AIServiceOptimizer:
    """Optimize AI service performance for production"""
    
    def __init__(self):
        self.connection_pool = None
        self.cache_client = None
        self.metrics_collector = None
    
    async def initialize_optimization(self):
        """Initialize performance optimization components"""
        
        # Connection pooling for database operations
        self.connection_pool = await asyncpg.create_pool(
            host=settings.REPLICA_DB_HOST,
            port=settings.REPLICA_DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        
        # Redis cache for ML predictions
        self.cache_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Metrics collection
        self.metrics_collector = MetricsCollector()
    
    async def cached_ml_prediction(self, model_name: str, input_features: List[float], 
                                 cache_ttl: int = 3600) -> Optional[float]:
        """Get ML prediction with caching"""
        
        # Create cache key
        features_hash = hashlib.md5(str(input_features).encode()).hexdigest()
        cache_key = f"ml_prediction:{model_name}:{features_hash}"
        
        # Try cache first
        try:
            cached_result = await self.cache_client.get(cache_key)
            if cached_result:
                self.metrics_collector.increment("ml_prediction_cache_hit")
                return float(cached_result)
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
        
        # Cache miss - get prediction from database
        try:
            async with self.connection_pool.acquire() as conn:
                query = """
                    SELECT pgml.predict($1, $2::float[]) as prediction
                """
                result = await conn.fetchval(query, model_name, input_features)
                
                # Cache the result
                try:
                    await self.cache_client.setex(cache_key, cache_ttl, str(result))
                    self.metrics_collector.increment("ml_prediction_cache_miss")
                except Exception as e:
                    logger.warning(f"Cache write failed: {e}")
                
                return result
                
        except Exception as e:
            logger.error(f"ML prediction failed: {e}")
            self.metrics_collector.increment("ml_prediction_error")
            return None
    
    async def batch_ml_predictions(self, model_name: str, 
                                 input_batch: List[List[float]]) -> List[Optional[float]]:
        """Batch ML predictions for better performance"""
        
        try:
            async with self.connection_pool.acquire() as conn:
                # Use PostgreSQL array operations for batch predictions
                query = """
                    SELECT pgml.predict($1, unnest($2::float[][])) as prediction
                """
                results = await conn.fetch(query, model_name, input_batch)
                return [row['prediction'] for row in results]
                
        except Exception as e:
            logger.error(f"Batch ML prediction failed: {e}")
            return [None] * len(input_batch)
    
    async def optimize_query_execution(self, sql_query: str, params: Dict) -> List[Dict]:
        """Execute queries with performance optimization"""
        
        start_time = time.time()
        
        try:
            async with self.connection_pool.acquire() as conn:
                # Set optimization parameters
                await conn.execute("SET work_mem = '256MB'")
                await conn.execute("SET random_page_cost = 1.1")
                await conn.execute("SET effective_cache_size = '4GB'")
                
                # Execute query
                results = await conn.fetch(sql_query, **params)
                
                execution_time = time.time() - start_time
                self.metrics_collector.record_query_time(execution_time)
                
                return [dict(row) for row in results]
                
        except Exception as e:
            execution_time = time.time() - start_time
            self.metrics_collector.record_query_error(execution_time)
            logger.error(f"Optimized query execution failed: {e}")
            raise
```

### Task 5.2: Automated Retraining Pipeline
**Duration**: 2-3 days  
**Priority**: HIGH  

#### ML Retraining Scheduler
```python
# services/backend-service/app/core/ml_retraining.py

class MLRetrainingScheduler:
    """Automated ML model retraining based on data freshness and performance"""
    
    def __init__(self, db_router: DatabaseRouter):
        self.db_router = db_router
        self.retraining_config = {
            'trajectory': {
                'schedule': '0 2 * * 0',  # Weekly on Sunday at 2 AM
                'min_new_records': 100,
                'performance_threshold': 0.8,
                'data_freshness_days': 30
            },
            'complexity': {
                'schedule': '0 3 * * 3',  # Weekly on Wednesday at 3 AM
                'min_new_records': 200,
                'performance_threshold': 0.75,
                'data_freshness_days': 14
            },
            'rework': {
                'schedule': '0 4 * * 6',  # Weekly on Saturday at 4 AM
                'min_new_records': 50,
                'performance_threshold': 0.7,
                'data_freshness_days': 21
            }
        }
    
    async def check_retraining_needs(self) -> Dict[str, Dict]:
        """Check which models need retraining"""
        retraining_status = {}
        
        with self.db_router.get_ml_session_context() as session:
            for model_type, config in self.retraining_config.items():
                try:
                    # Check data freshness
                    freshness_query = self._get_freshness_query(model_type, config['data_freshness_days'])
                    new_records = session.execute(text(freshness_query)).scalar()
                    
                    # Check model performance
                    current_metrics = session.execute(
                        text(f"SELECT pgml.metrics('{self._get_model_name(model_type)}')")
                    ).scalar()
                    
                    # Parse metrics to get performance score
                    performance_score = self._extract_performance_score(current_metrics, model_type)
                    
                    # Determine if retraining is needed
                    needs_retraining = (
                        new_records >= config['min_new_records'] or
                        performance_score < config['performance_threshold']
                    )
                    
                    retraining_status[model_type] = {
                        'needs_retraining': needs_retraining,
                        'new_records': new_records,
                        'performance_score': performance_score,
                        'last_check': datetime.utcnow(),
                        'reason': self._get_retraining_reason(
                            new_records, config['min_new_records'],
                            performance_score, config['performance_threshold']
                        )
                    }
                    
                except Exception as e:
                    logger.error(f"Error checking retraining needs for {model_type}: {e}")
                    retraining_status[model_type] = {
                        'needs_retraining': False,
                        'error': str(e),
                        'last_check': datetime.utcnow()
                    }
        
        return retraining_status
    
    async def execute_model_retraining(self, model_type: str) -> Dict[str, Any]:
        """Execute retraining for a specific model"""
        
        logger.info(f"🔄 Starting retraining for {model_type} model")
        start_time = time.time()
        
        try:
            with self.db_router.get_ml_session_context() as session:
                # Get training script
                training_script = self._get_training_script(model_type)
                
                # Execute training
                session.execute(text(training_script))
                session.commit()
                
                # Validate new model
                new_metrics = session.execute(
                    text(f"SELECT pgml.metrics('{self._get_model_name(model_type)}')")
                ).scalar()
                
                training_time = time.time() - start_time
                
                # Log retraining event
                await self._log_retraining_event(model_type, new_metrics, training_time)
                
                logger.info(f"✅ {model_type} model retrained successfully in {training_time:.2f}s")
                
                return {
                    'status': 'success',
                    'model_type': model_type,
                    'training_time_seconds': training_time,
                    'new_metrics': new_metrics,
                    'retrained_at': datetime.utcnow()
                }
                
        except Exception as e:
            training_time = time.time() - start_time
            logger.error(f"❌ {model_type} model retraining failed: {e}")
            
            # Log failure
            await self._log_retraining_failure(model_type, str(e), training_time)
            
            return {
                'status': 'failed',
                'model_type': model_type,
                'error': str(e),
                'training_time_seconds': training_time,
                'failed_at': datetime.utcnow()
            }
    
    async def scheduled_retraining_check(self):
        """Scheduled check and execution of model retraining"""
        
        logger.info("🔍 Running scheduled retraining check")
        
        # Check which models need retraining
        retraining_status = await self.check_retraining_needs()
        
        # Execute retraining for models that need it
        retraining_results = {}
        for model_type, status in retraining_status.items():
            if status.get('needs_retraining', False):
                logger.info(f"🎯 {model_type} model needs retraining: {status.get('reason', 'Unknown')}")
                result = await self.execute_model_retraining(model_type)
                retraining_results[model_type] = result
            else:
                logger.info(f"✅ {model_type} model is up to date")
        
        # Send notification if any retraining occurred
        if retraining_results:
            await self._send_retraining_notification(retraining_results)
        
        return {
            'check_completed_at': datetime.utcnow(),
            'models_checked': list(retraining_status.keys()),
            'models_retrained': list(retraining_results.keys()),
            'retraining_results': retraining_results
        }
```

### Task 5.3: Comprehensive Monitoring
**Duration**: 2-3 days  
**Priority**: HIGH  

#### AI System Monitoring Dashboard
```python
# services/backend-service/app/api/ai_monitoring.py

@router.get("/api/ai/monitoring/dashboard")
async def get_ai_monitoring_dashboard(
    client_id: int = Query(...),
    time_range: str = Query("24h", regex="^(1h|6h|24h|7d|30d)$"),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_admin_user)
):
    """Get comprehensive AI system monitoring dashboard"""
    
    try:
        # Convert time range to hours
        time_hours = {
            "1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720
        }[time_range]
        
        # ML Model Performance Metrics
        model_metrics = await get_model_performance_metrics(db, client_id, time_hours)
        
        # Prediction Volume and Latency
        prediction_stats = await get_prediction_statistics(db, client_id, time_hours)
        
        # Anomaly Detection Summary
        anomaly_summary = await get_anomaly_summary(db, client_id, time_hours)
        
        # Validation System Performance
        validation_stats = await get_validation_statistics(db, client_id, time_hours)
        
        # Self-Healing Learning Progress
        learning_progress = await get_learning_progress(db, client_id, time_hours)
        
        # System Health Status
        health_status = await get_ai_system_health(db)
        
        return {
            "dashboard_data": {
                "model_metrics": model_metrics,
                "prediction_stats": prediction_stats,
                "anomaly_summary": anomaly_summary,
                "validation_stats": validation_stats,
                "learning_progress": learning_progress,
                "health_status": health_status
            },
            "time_range": time_range,
            "generated_at": datetime.utcnow(),
            "client_id": client_id
        }
        
    except Exception as e:
        logger.error(f"AI monitoring dashboard error: {e}")
        raise HTTPException(500, f"Failed to generate monitoring dashboard: {str(e)}")

async def get_model_performance_metrics(db: Session, client_id: int, time_hours: int) -> Dict:
    """Get ML model performance metrics"""
    
    query = text("""
        SELECT 
            model_name,
            COUNT(*) as prediction_count,
            AVG(response_time_ms) as avg_response_time,
            COUNT(*) FILTER (WHERE is_anomaly = true) as anomaly_count,
            AVG(anomaly_score) as avg_anomaly_score,
            COUNT(*) FILTER (WHERE severity = 'critical') as critical_predictions
        FROM ml_prediction_log
        WHERE client_id = :client_id
            AND created_at >= NOW() - INTERVAL ':hours hours'
            AND active = true
        GROUP BY model_name
        ORDER BY prediction_count DESC
    """)
    
    results = db.execute(query, {"client_id": client_id, "hours": time_hours}).fetchall()
    
    return {
        "models": [
            {
                "model_name": row.model_name,
                "prediction_count": row.prediction_count,
                "avg_response_time_ms": round(row.avg_response_time, 2) if row.avg_response_time else 0,
                "anomaly_rate": round(row.anomaly_count / row.prediction_count * 100, 2) if row.prediction_count > 0 else 0,
                "avg_anomaly_score": round(row.avg_anomaly_score, 3) if row.avg_anomaly_score else 0,
                "critical_predictions": row.critical_predictions
            }
            for row in results
        ],
        "total_predictions": sum(row.prediction_count for row in results),
        "time_range_hours": time_hours
    }

async def get_validation_statistics(db: Session, client_id: int, time_hours: int) -> Dict:
    """Get validation system performance statistics"""
    
    query = text("""
        SELECT 
            error_type,
            COUNT(*) as failure_count,
            AVG(confidence) as avg_confidence,
            COUNT(*) FILTER (WHERE confidence > 0.8) as high_confidence_fixes
        FROM ai_learning_memory
        WHERE client_id = :client_id
            AND created_at >= NOW() - INTERVAL ':hours hours'
            AND active = true
        GROUP BY error_type
        ORDER BY failure_count DESC
    """)
    
    results = db.execute(query, {"client_id": client_id, "hours": time_hours}).fetchall()
    
    return {
        "validation_failures": [
            {
                "error_type": row.error_type,
                "failure_count": row.failure_count,
                "avg_confidence": round(row.avg_confidence, 3) if row.avg_confidence else 0,
                "high_confidence_fixes": row.high_confidence_fixes,
                "success_rate": round(row.high_confidence_fixes / row.failure_count * 100, 2) if row.failure_count > 0 else 0
            }
            for row in results
        ],
        "total_failures": sum(row.failure_count for row in results),
        "overall_learning_rate": round(
            sum(row.high_confidence_fixes for row in results) / 
            sum(row.failure_count for row in results) * 100, 2
        ) if sum(row.failure_count for row in results) > 0 else 0
    }
```

### Task 5.4: Production Deployment
**Duration**: 2-3 days  
**Priority**: CRITICAL  

#### Production Deployment Checklist

**🔒 CRITICAL: Client Isolation Verification**
Before production deployment, verify:
- All ML queries include `client_id` filtering
- Materialized views group by `client_id`
- ML model training is client-specific
- Monitoring dashboards filter by `client_id`
- No cross-client data leakage in any ML operations
```yaml
# deployment/production/ai-service-deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pulse-ai-service
  namespace: pulse-production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: pulse-ai-service
  template:
    metadata:
      labels:
        app: pulse-ai-service
    spec:
      containers:
      - name: ai-service
        image: pulse/ai-service:latest
        ports:
        - containerPort: 8080
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: WEX_AI_GATEWAY_URL
          valueFrom:
            secretKeyRef:
              name: ai-service-secrets
              key: wex-ai-gateway-url
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: ai-service-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: ai-service-secrets
              key: redis-url
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

#### Production Configuration
```python
# services/ai-service/app/config/production.py

class ProductionConfig:
    """Production configuration for AI service"""
    
    # Database settings
    DATABASE_POOL_SIZE = 20
    DATABASE_MAX_OVERFLOW = 30
    DATABASE_POOL_TIMEOUT = 30
    DATABASE_POOL_RECYCLE = 3600
    
    # Redis settings
    REDIS_POOL_SIZE = 10
    REDIS_SOCKET_TIMEOUT = 5
    REDIS_SOCKET_CONNECT_TIMEOUT = 5
    
    # ML model settings
    ML_PREDICTION_TIMEOUT = 30
    ML_BATCH_SIZE = 100
    ML_CACHE_TTL = 3600
    
    # Validation settings
    MAX_SQL_RETRIES = 3
    MAX_SEMANTIC_RETRIES = 2
    VALIDATION_TIMEOUT = 10
    
    # Performance settings
    ASYNC_WORKER_COUNT = 4
    REQUEST_TIMEOUT = 60
    MAX_CONCURRENT_REQUESTS = 100
    
    # Monitoring settings
    METRICS_ENABLED = True
    DETAILED_LOGGING = False
    LOG_LEVEL = "INFO"
    
    # Security settings
    ENABLE_RATE_LIMITING = True
    MAX_REQUESTS_PER_MINUTE = 60
    REQUIRE_API_KEY = True
```

## ✅ Success Criteria

1. **Performance**: AI responses within 10 seconds for 95% of requests
2. **Reliability**: 99.9% uptime for AI service
3. **Scalability**: Handle 1000+ concurrent users
4. **Monitoring**: Complete observability across all AI components
5. **Automation**: Automated retraining and deployment pipelines
6. **User Adoption**: 80% of users actively using AI features

## 🚨 Risk Mitigation

1. **Performance Degradation**: Comprehensive monitoring and alerting
2. **Model Drift**: Automated retraining and performance tracking
3. **System Overload**: Auto-scaling and circuit breakers
4. **Data Quality**: Continuous data validation and anomaly detection
5. **Security**: API authentication and rate limiting

## 📝 Final Testing Strategy

### Load Testing
- 1000+ concurrent users
- Peak traffic simulation
- Database performance under load
- ML prediction latency testing

### Integration Testing
- End-to-end AI workflow testing
- Cross-service communication
- Error handling and recovery
- Data consistency validation

### User Acceptance Testing
- Business user scenarios
- AI response quality validation
- UI/UX testing with AI features
- Performance from user perspective

## 🎉 Phase 5 Completion Delivers

- **Production-Ready AI Platform**: Complete AI-powered business intelligence system
- **Automated Operations**: Self-managing ML models and validation systems
- **Enterprise Scale**: System capable of handling enterprise workloads
- **Continuous Improvement**: Self-learning system that improves over time
- **Business Value**: Predictive insights driving strategic decision-making
