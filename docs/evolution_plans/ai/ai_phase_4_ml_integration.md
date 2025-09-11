# Phase 3: ML Integration & Training

**Implemented**: NO ❌
**Duration**: Weeks 5-6
**Priority**: HIGH
**Risk Level**: MEDIUM

## 💼 Business Outcome

**Predictive Analytics**: Transform reactive project management into proactive decision-making with ML-powered predictions for project delivery dates, issue complexity, and rework probability, reducing project delays by 40% and improving resource allocation accuracy by 60%.

## 🎯 Objectives

1. **PostgresML Model Training**: Train predictive models on replica database **PER CLIENT**
2. **ML Prediction Endpoints**: Create backend APIs for model predictions with client isolation
3. **ETL ML Enhancement**: Add ML predictions to data pipeline
4. **Model Performance Monitoring**: Track model accuracy and performance per client
5. **Anomaly Detection**: Identify unusual predictions and data patterns

## 🔒 CRITICAL: Client Isolation Requirements

**ALL ML operations must respect multi-tenancy:**
- **Model Training**: Separate models per client (`project_name => 'model_client_1_v1'`)
- **Data Filtering**: All training queries MUST include `client_id = X` filters
- **Predictions**: Only use client-specific models for predictions
- **Monitoring**: ML logs and metrics filtered by `client_id`

## 📋 Task Breakdown

### Task 3.1: PostgresML Model Training
**Duration**: 3-4 days  
**Priority**: CRITICAL  

#### Model 1: Project Trajectory Forecaster
**Business Value**: Predict epic completion dates for better project planning

```sql
-- Train on replica using live data from primary (via replication)
-- CRITICAL: Train model per client (client_id = 1 example)
-- This must be executed separately for each client
SELECT pgml.train(
    project_name => 'project_trajectory_forecast_client_1_v1',  -- Client-specific model name
    task => 'regression',
    relation_name => 'issues',
    y_column_name => 'total_lead_time_seconds',
    algorithm => 'xgboost',
    hyperparams => '{
        "n_estimators": 100,
        "max_depth": 6,
        "learning_rate": 0.1,
        "subsample": 0.8
    }',
    test_sampling => 'random',
    test_size => 0.2,
    -- CRITICAL: Filter by client_id for tenant isolation
    filter => "
        client_id = 1  -- MUST be client-specific
        AND issuetype_id IN (
            SELECT id FROM issuetypes
            WHERE original_name = 'Epic' AND active = true AND client_id = 1
        )
        AND status_id IN (
            SELECT s.id FROM statuses s
            JOIN status_mappings sm ON s.status_mapping_id = sm.id
            WHERE sm.status_to = 'Done' AND s.active = true
        )
        AND total_lead_time_seconds > 0
        AND total_lead_time_seconds < 31536000  -- Less than 1 year
        AND work_last_completed_at >= NOW() - INTERVAL '2 years'
        AND active = true
    "
);
```

#### Model 2: Issue Complexity Estimator
**Business Value**: Auto-estimate story points for backlog planning

```sql
-- CRITICAL: Train model per client (client_id = 1 example)
SELECT pgml.train(
    project_name => 'issue_complexity_estimator_client_1_v1',  -- Client-specific model name
    task => 'regression',
    relation_name => 'issues',
    y_column_name => 'story_points',
    algorithm => 'xgboost',
    hyperparams => '{
        "n_estimators": 150,
        "max_depth": 5,
        "learning_rate": 0.05
    }',
    -- Use text features from summary and custom fields
    preprocess_params => '{
        "text_columns": {
            "summary": {"imputer": "constant", "value": ""},
            "custom_field_01": {"imputer": "constant", "value": ""},
            "custom_field_05": {"imputer": "constant", "value": ""}
        }
    }',
    test_sampling => 'random',
    test_size => 0.25,
    -- CRITICAL: Filter by client_id for tenant isolation
    filter => "
        client_id = 1  -- MUST be client-specific
        AND story_points IS NOT NULL
        AND story_points > 0
        AND story_points <= 21  -- Reasonable story point range
        AND issuetype_id IN (
            SELECT id FROM issuetypes
            WHERE original_name IN ('Story', 'Task', 'Bug')
            AND active = true AND client_id = 1
        )
        AND summary IS NOT NULL
        AND LENGTH(summary) > 10
        AND created >= NOW() - INTERVAL '18 months'
        AND active = true
    "
);
```

#### Model 3: PR Rework Risk Classifier
**Business Value**: Identify PRs likely to need rework for proactive code review

```sql
-- CRITICAL: Create client-specific rework training view
-- This view must be created per client or filtered by client_id
CREATE OR REPLACE VIEW pr_rework_training_data AS
SELECT
    pr.*,
    -- Derive rework indicator from existing fields
    CASE
        WHEN pr.review_cycles > 2 OR pr.rework_commit_count > 3 THEN true
        ELSE false
    END as rework_indicator
FROM pull_requests pr
WHERE pr.merged_at IS NOT NULL  -- Only completed PRs
    AND pr.review_cycles IS NOT NULL
    AND pr.rework_commit_count IS NOT NULL
    AND pr.active = true;
    -- NOTE: client_id filtering must be applied when querying this view

-- CRITICAL: Train model per client (client_id = 1 example)
SELECT pgml.train(
    project_name => 'pr_rework_classifier_client_1_v1',  -- Client-specific model name
    task => 'classification',
    relation_name => 'pr_rework_training_data',
    y_column_name => 'rework_indicator',
    algorithm => 'lightgbm',
    hyperparams => '{
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.9
    }',
    test_sampling => 'random',
    test_size => 0.3,
    -- CRITICAL: Filter by client_id for tenant isolation
    filter => "
        client_id = 1  -- MUST be client-specific
        AND merged_at >= NOW() - INTERVAL '12 months'
        AND commit_count > 0
        AND changed_files > 0
    "
);
```

### Task 3.2: ML Prediction Endpoints
**Duration**: 3-4 days  
**Priority**: HIGH  

#### Trajectory Prediction Endpoint
```python
# services/backend-service/app/api/ml_predictions.py

@router.post("/api/ml/predict-trajectory")
async def predict_trajectory(
    request: TrajectoryPredictionRequest,
    db: Session = Depends(get_ml_session_context),  # Uses replica
    user: UserData = Depends(get_current_user)
):
    """Predict completion dates for epics using ML model"""
    try:
        # Execute prediction query on replica (same DB where model was trained)
        prediction_query = text("""
            SELECT
                i.key,
                i.summary,
                i.created,
                i.total_lead_time_seconds as current_lead_time,
                pgml.predict(
                    'project_trajectory_forecast_v1',
                    ARRAY[
                        i.story_points::float,
                        EXTRACT(epoch FROM (NOW() - i.created))::float,
                        i.comment_count::float,
                        CASE WHEN i.assignee_id IS NOT NULL THEN 1.0 ELSE 0.0 END
                    ]
                ) as predicted_lead_time_seconds,
                i.created + make_interval(
                    secs => pgml.predict('project_trajectory_forecast_v1',
                        ARRAY[i.story_points::float, EXTRACT(epoch FROM (NOW() - i.created))::float,
                              i.comment_count::float, CASE WHEN i.assignee_id IS NOT NULL THEN 1.0 ELSE 0.0 END]
                    )::integer
                ) as predicted_completion_date
            FROM issues i
            JOIN issuetypes it ON i.issuetype_id = it.id
            WHERE it.original_name = 'Epic'
                AND i.key = ANY(:epic_keys)
                AND i.client_id = :client_id
                AND i.active = true
            ORDER BY i.created DESC
        """)

        result = db.execute(prediction_query, {
            "epic_keys": request.epic_keys,
            "client_id": user.client_id
        }).fetchall()

        predictions = [
            {
                "epic_key": row.key,
                "summary": row.summary,
                "created": row.created,
                "current_lead_time_days": row.current_lead_time / 86400 if row.current_lead_time else None,
                "predicted_lead_time_days": row.predicted_lead_time_seconds / 86400,
                "predicted_completion_date": row.predicted_completion_date,
                "confidence": "high"  # TODO: Get actual confidence from model
            }
            for row in result
        ]

        # Log predictions for monitoring
        await log_ml_predictions(predictions, "trajectory", user.client_id)

        return {
            "predictions": predictions,
            "model_version": "project_trajectory_forecast_v1",
            "predicted_at": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Trajectory prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
```

#### Complexity Estimation Endpoint
```python
@router.post("/api/ml/estimate-complexity")
async def estimate_complexity(
    request: ComplexityEstimationRequest,
    db: Session = Depends(get_ml_session_context),
    user: UserData = Depends(get_current_user)
):
    """Estimate story points for issues using ML model"""
    try:
        complexity_query = text("""
            SELECT
                i.key,
                i.summary,
                i.story_points as current_story_points,
                pgml.predict(
                    'issue_complexity_estimator_v1',
                    ARRAY[
                        LENGTH(i.summary)::float,
                        i.comment_count::float,
                        CASE WHEN i.custom_field_01 IS NOT NULL THEN 1.0 ELSE 0.0 END,
                        CASE WHEN i.assignee_id IS NOT NULL THEN 1.0 ELSE 0.0 END
                    ]
                ) as estimated_story_points
            FROM issues i
            WHERE i.key = ANY(:issue_keys)
                AND i.client_id = :client_id
                AND i.active = true
            ORDER BY i.created DESC
        """)

        result = db.execute(complexity_query, {
            "issue_keys": request.issue_keys,
            "client_id": user.client_id
        }).fetchall()

        estimates = [
            {
                "issue_key": row.key,
                "summary": row.summary,
                "current_story_points": row.current_story_points,
                "estimated_story_points": round(row.estimated_story_points, 1),
                "estimation_confidence": "medium"  # TODO: Get actual confidence
            }
            for row in result
        ]

        # Log predictions for monitoring
        await log_ml_predictions(estimates, "complexity", user.client_id)

        return {
            "estimates": estimates,
            "model_version": "issue_complexity_estimator_v1",
            "estimated_at": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Complexity estimation error: {e}")
        raise HTTPException(status_code=500, detail=f"Estimation failed: {str(e)}")
```

### Task 3.3: ETL ML Enhancement
**Duration**: 2-3 days  
**Priority**: MEDIUM  

#### Enhanced GitHub Job with ML Predictions
```python
# services/etl-service/app/core/jobs/enhanced_github_job.py

class EnhancedGitHubJob(GitHubJob):
    """GitHub job enhanced with ML predictions"""
    
    def __init__(self, client_id: int, config: dict):
        super().__init__(client_id, config)
        self.ml_client = MLPredictionClient()
        self.ml_enabled = config.get('ml_predictions_enabled', False)
    
    async def process_pull_request_batch(self, pr_batch: List[Dict]) -> List[PullRequest]:
        """Enhanced PR processing with ML predictions"""
        
        # Existing processing (unchanged)
        processed_prs = await super().process_pull_request_batch(pr_batch)
        
        # NEW: Add ML predictions during ETL
        if self.ml_enabled and self.ml_client.is_available():
            enhanced_prs = await self.add_ml_predictions(processed_prs)
            return enhanced_prs
        
        return processed_prs
    
    async def add_ml_predictions(self, prs: List[PullRequest]) -> List[PullRequest]:
        """Add ML predictions to PR data during ETL"""
        try:
            # Predict rework risk for open PRs
            open_prs = [pr for pr in prs if pr.state == 'open']
            if open_prs:
                pr_numbers = [pr.number for pr in open_prs]
                rework_predictions = await self.ml_client.predict_rework_risk(pr_numbers)
                
                # Update PR objects with predictions
                for pr in open_prs:
                    prediction = rework_predictions.get(pr.number)
                    if prediction:
                        # Store predictions in custom fields or separate table
                        pr.ml_rework_probability = prediction['rework_probability']
                        pr.ml_risk_level = prediction['risk_level']
            
            return prs
            
        except Exception as e:
            self.logger.warning(f"ML prediction failed during ETL: {e}")
            return prs  # Graceful degradation
```

#### Enhanced Jira Job with Complexity Estimation
```python
# services/etl-service/app/core/jobs/enhanced_jira_job.py

class EnhancedJiraJob(JiraJob):
    """Jira job enhanced with ML complexity estimation"""
    
    async def process_issue_batch(self, issue_batch: List[Dict]) -> List[Issue]:
        """Enhanced issue processing with ML complexity estimation"""
        
        # Existing processing (unchanged)
        processed_issues = await super().process_issue_batch(issue_batch)
        
        # NEW: Add ML complexity estimation for unestimated stories
        if self.ml_enabled and self.ml_client.is_available():
            enhanced_issues = await self.add_complexity_estimates(processed_issues)
            return enhanced_issues
        
        return processed_issues
    
    async def add_complexity_estimates(self, issues: List[Issue]) -> List[Issue]:
        """Add ML complexity estimates during ETL"""
        try:
            # Find unestimated stories
            unestimated = [
                issue for issue in issues 
                if not issue.story_points and issue.issuetype_name == 'Story'
            ]
            
            if unestimated:
                issue_keys = [issue.key for issue in unestimated]
                complexity_estimates = await self.ml_client.estimate_complexity(issue_keys)
                
                # Update issue objects with estimates
                for issue in unestimated:
                    estimate = complexity_estimates.get(issue.key)
                    if estimate:
                        issue.ml_estimated_story_points = estimate['estimated_story_points']
                        issue.ml_estimation_confidence = estimate['estimation_confidence']
            
            return issues
            
        except Exception as e:
            self.logger.warning(f"ML complexity estimation failed during ETL: {e}")
            return issues
```

### Task 3.4: Model Performance Monitoring
**Duration**: 2-3 days  
**Priority**: MEDIUM  

#### ML Monitoring Service
```python
# services/backend-service/app/core/ml_monitoring.py

class MLModelMonitor:
    """Monitor ML model health and performance"""
    
    def __init__(self, db_router: DatabaseRouter):
        self.db_router = db_router
        self.models = {
            'trajectory': 'project_trajectory_forecast_v1',
            'complexity': 'issue_complexity_estimator_v1',
            'rework': 'pr_rework_classifier_v1'
        }
    
    async def check_model_health(self) -> Dict[str, Any]:
        """Comprehensive model health check"""
        health_status = {}
        
        with self.db_router.get_ml_session_context() as session:
            for model_type, model_name in self.models.items():
                try:
                    # Test model availability
                    session.execute(text(f"SELECT pgml.predict('{model_name}', ARRAY[1.0, 2.0, 3.0])"))
                    
                    # Get model metrics
                    metrics = session.execute(text(f"SELECT pgml.metrics('{model_name}')")).scalar()
                    
                    health_status[model_type] = {
                        "status": "healthy",
                        "model_name": model_name,
                        "metrics": metrics,
                        "last_checked": datetime.utcnow()
                    }
                    
                except Exception as e:
                    health_status[model_type] = {
                        "status": "unhealthy",
                        "model_name": model_name,
                        "error": str(e),
                        "last_checked": datetime.utcnow()
                    }
        
        return health_status
    
    async def log_prediction(self, model_name: str, prediction_value: float, 
                           input_features: Dict, client_id: int, response_time_ms: int):
        """Log ML prediction for monitoring"""
        try:
            with self.db_router.get_write_session() as session:
                log_entry = MLPredictionLog(
                    model_name=model_name,
                    prediction_value=prediction_value,
                    input_features=input_features,
                    response_time_ms=response_time_ms,
                    client_id=client_id,
                    created_at=datetime.utcnow(),
                    active=True
                )
                
                session.add(log_entry)
                session.commit()
                
        except Exception as e:
            logger.error(f"Failed to log ML prediction: {e}")
```

## ✅ Success Criteria

1. **Model Training**: All 3 models train successfully with acceptable accuracy
2. **Prediction Endpoints**: APIs return predictions within 2 seconds
3. **ETL Integration**: ML predictions added to data pipeline without errors
4. **Performance Monitoring**: Model health and prediction logging functional
5. **Accuracy Metrics**: Models achieve target accuracy thresholds
6. **Client Isolation**: All ML operations respect multi-tenancy

## 🚨 Risk Mitigation

1. **Model Training Failures**: Fallback to simpler algorithms if complex models fail
2. **Prediction Latency**: Implement caching and async processing
3. **Data Quality**: Validate training data before model training
4. **Resource Usage**: Monitor replica database performance during ML operations
5. **Model Drift**: Implement automated retraining triggers

## 📝 Testing Strategy

### Model Validation
- Cross-validation on training data
- Holdout test set evaluation
- Business metric correlation testing

### API Testing
- Prediction endpoint performance testing
- Error handling and edge cases
- Load testing under concurrent requests

### Integration Testing
- ETL jobs with ML predictions enabled
- End-to-end prediction pipeline
- Client isolation verification

## 🔄 Phase 3 Completion Enables

- **Phase 4**: AI service with predictive capabilities
- **Phase 5**: Production deployment with ML intelligence

