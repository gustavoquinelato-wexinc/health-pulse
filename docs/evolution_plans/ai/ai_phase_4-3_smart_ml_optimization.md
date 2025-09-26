# Phase 4-3: Smart ML Training & Performance Optimization

**Implemented**: NO ❌
**Duration**: Week 3-4 of Phase 4
**Priority**: HIGH
**Risk Level**: LOW

## 💼 Business Outcome

**Intelligent ML Operations**: Deploy advanced ML training optimization with data drift detection, adaptive scheduling, and performance-based triggers that maintain 80%+ model accuracy while minimizing computational overhead and maximizing prediction reliability.

## 🎯 Objectives

1. **Data Drift Detection**: Automatically detect when data patterns change requiring model updates
2. **Adaptive Training Schedules**: Dynamic training frequency based on tenant data volume and patterns
3. **Performance-Based Triggers**: Advanced model performance monitoring with intelligent retraining
4. **Resource Optimization**: Efficient training scheduling and resource management
5. **Model Ensemble**: Combine multiple models for improved prediction accuracy

## 🔒 CRITICAL: Production Optimization Requirements

**ALL smart ML operations must be production-ready:**
- **Resource Management**: Training scheduled during low-usage periods
- **Performance Monitoring**: Real-time model performance tracking
- **Rollback Capability**: Automatic rollback to previous models if performance degrades
- **Cost Optimization**: Minimize unnecessary training while maintaining accuracy

## 📋 Task Breakdown

### Task 4-3.1: Data Drift Detection
**Duration**: 2-3 days  
**Priority**: HIGH  

#### Statistical Data Drift Detection
```python
# services/etl-service/app/jobs/ml_training/data_drift_detector.py

class DataDriftDetector:
    """Detect when data patterns change requiring model retraining"""
    
    def __init__(self):
        self.drift_threshold = 0.1  # 10% change triggers drift detection
        self.statistical_tests = ['ks_test', 'chi_square', 'psi']
    
    async def detect_data_drift(self, tenant_id: int, model_type: str) -> Dict[str, Any]:
        """
        Detect data drift using multiple statistical methods
        """
        try:
            # Get baseline data (used for last training)
            baseline_data = await self.get_baseline_training_data(tenant_id, model_type)
            
            # Get recent data (potential new training data)
            recent_data = await self.get_recent_data(tenant_id, model_type)
            
            if len(recent_data) < 30:  # Need minimum samples
                return {'drift_detected': False, 'reason': 'insufficient_recent_data'}
            
            # Run statistical tests
            drift_results = {}
            
            # Kolmogorov-Smirnov test for numerical features
            ks_results = await self.kolmogorov_smirnov_test(baseline_data, recent_data)
            drift_results['ks_test'] = ks_results
            
            # Population Stability Index for categorical features
            psi_results = await self.population_stability_index(baseline_data, recent_data)
            drift_results['psi_test'] = psi_results
            
            # Chi-square test for categorical distributions
            chi_square_results = await self.chi_square_test(baseline_data, recent_data)
            drift_results['chi_square_test'] = chi_square_results
            
            # Determine overall drift
            drift_detected = self.evaluate_drift_results(drift_results)
            
            return {
                'drift_detected': drift_detected,
                'drift_score': self.calculate_drift_score(drift_results),
                'test_results': drift_results,
                'recommendation': self.get_drift_recommendation(drift_detected, drift_results)
            }
            
        except Exception as e:
            logger.error(f"Data drift detection failed for tenant {tenant_id}, model {model_type}: {e}")
            return {'drift_detected': False, 'error': str(e)}
    
    async def kolmogorov_smirnov_test(self, baseline: pd.DataFrame, recent: pd.DataFrame) -> Dict[str, float]:
        """KS test for numerical feature distributions"""
        from scipy.stats import ks_2samp
        
        ks_results = {}
        numerical_features = ['summary_length', 'description_length', 'workflow_complexity_score']
        
        for feature in numerical_features:
            if feature in baseline.columns and feature in recent.columns:
                statistic, p_value = ks_2samp(baseline[feature], recent[feature])
                ks_results[feature] = {
                    'statistic': statistic,
                    'p_value': p_value,
                    'drift_detected': p_value < 0.05  # 5% significance level
                }
        
        return ks_results
    
    async def population_stability_index(self, baseline: pd.DataFrame, recent: pd.DataFrame) -> Dict[str, float]:
        """PSI for categorical feature distributions"""
        psi_results = {}
        categorical_features = ['priority', 'team', 'assignee']
        
        for feature in categorical_features:
            if feature in baseline.columns and feature in recent.columns:
                psi_score = self.calculate_psi(baseline[feature], recent[feature])
                psi_results[feature] = {
                    'psi_score': psi_score,
                    'drift_detected': psi_score > 0.1  # PSI > 0.1 indicates drift
                }
        
        return psi_results
    
    def calculate_psi(self, baseline_series: pd.Series, recent_series: pd.Series) -> float:
        """Calculate Population Stability Index"""
        # Get value counts and normalize
        baseline_dist = baseline_series.value_counts(normalize=True)
        recent_dist = recent_series.value_counts(normalize=True)
        
        # Align distributions
        all_values = set(baseline_dist.index) | set(recent_dist.index)
        
        psi = 0
        for value in all_values:
            baseline_pct = baseline_dist.get(value, 0.001)  # Small value to avoid log(0)
            recent_pct = recent_dist.get(value, 0.001)
            
            psi += (recent_pct - baseline_pct) * np.log(recent_pct / baseline_pct)
        
        return psi
```

### Task 4-3.2: Adaptive Training Schedules
**Duration**: 2-3 days
**Priority**: HIGH

#### Dynamic Training Frequency
```python
# services/etl-service/app/jobs/ml_training/adaptive_scheduler.py

class AdaptiveMLScheduler:
    """Dynamically adjust ML training frequency based on tenant patterns"""
    
    def __init__(self):
        self.base_schedules = {
            'high_volume': {'days': 7, 'min_samples': 100},      # Weekly for high-volume tenants
            'medium_volume': {'days': 14, 'min_samples': 50},    # Bi-weekly for medium-volume
            'low_volume': {'days': 30, 'min_samples': 25}        # Monthly for low-volume
        }
    
    async def determine_training_schedule(self, tenant_id: int) -> Dict[str, Any]:
        """Determine optimal training schedule for tenant"""
        
        # Analyze tenant data patterns
        data_analysis = await self.analyze_tenant_data_patterns(tenant_id)
        
        # Classify tenant volume
        volume_category = self.classify_tenant_volume(data_analysis)
        
        # Get base schedule
        base_schedule = self.base_schedules[volume_category]
        
        # Adjust based on data quality and model performance
        adjusted_schedule = await self.adjust_schedule_for_performance(
            tenant_id, base_schedule, data_analysis
        )
        
        return {
            'volume_category': volume_category,
            'training_interval_days': adjusted_schedule['days'],
            'min_samples_threshold': adjusted_schedule['min_samples'],
            'next_training_date': datetime.now() + timedelta(days=adjusted_schedule['days']),
            'reasoning': adjusted_schedule['reasoning']
        }
    
    async def analyze_tenant_data_patterns(self, tenant_id: int) -> Dict[str, Any]:
        """Analyze tenant's data volume and quality patterns"""
        
        # Get data volume over last 90 days
        volume_analysis = await self.get_data_volume_trends(tenant_id)
        
        # Get data quality metrics
        quality_analysis = await self.get_data_quality_metrics(tenant_id)
        
        # Get model performance trends
        performance_analysis = await self.get_model_performance_trends(tenant_id)
        
        return {
            'volume': volume_analysis,
            'quality': quality_analysis,
            'performance': performance_analysis
        }
    
    def classify_tenant_volume(self, data_analysis: Dict[str, Any]) -> str:
        """Classify tenant as high/medium/low volume"""
        
        weekly_avg_items = data_analysis['volume']['weekly_avg_new_items']
        
        if weekly_avg_items >= 50:
            return 'high_volume'
        elif weekly_avg_items >= 20:
            return 'medium_volume'
        else:
            return 'low_volume'
```

### Task 4-3.3: Performance-Based Training Triggers
**Duration**: 2-3 days
**Priority**: HIGH

#### Advanced Performance Monitoring
```python
# services/etl-service/app/jobs/ml_training/performance_monitor.py

class MLPerformanceMonitor:
    """Advanced ML model performance monitoring and trigger system"""
    
    def __init__(self):
        self.performance_thresholds = {
            'story_points': {'r2': 0.7, 'mae': 2.0},
            'lead_time': {'r2': 0.6, 'mae': 5.0},
            'rework_risk': {'f1': 0.65, 'precision': 0.7}
        }
        self.degradation_threshold = 0.1  # 10% performance drop triggers retraining
    
    async def evaluate_model_performance(self, tenant_id: int, model_type: str) -> Dict[str, Any]:
        """Comprehensive model performance evaluation"""
        
        try:
            # Get recent predictions vs actual results
            recent_predictions = await self.get_recent_predictions(tenant_id, model_type)
            
            if len(recent_predictions) < 20:  # Need minimum samples for evaluation
                return {
                    'evaluation_possible': False,
                    'reason': 'insufficient_recent_predictions',
                    'sample_count': len(recent_predictions)
                }
            
            # Calculate current performance metrics
            current_metrics = await self.calculate_performance_metrics(recent_predictions, model_type)
            
            # Get baseline performance (from training)
            baseline_metrics = await self.get_baseline_performance(tenant_id, model_type)
            
            # Detect performance degradation
            degradation_analysis = self.analyze_performance_degradation(
                current_metrics, baseline_metrics
            )
            
            # Generate recommendations
            recommendations = self.generate_performance_recommendations(
                current_metrics, baseline_metrics, degradation_analysis
            )
            
            return {
                'evaluation_possible': True,
                'current_performance': current_metrics,
                'baseline_performance': baseline_metrics,
                'degradation_detected': degradation_analysis['degradation_detected'],
                'degradation_severity': degradation_analysis['severity'],
                'recommendations': recommendations,
                'retraining_recommended': degradation_analysis['retraining_recommended']
            }
            
        except Exception as e:
            logger.error(f"Performance evaluation failed for tenant {tenant_id}, model {model_type}: {e}")
            return {'evaluation_possible': False, 'error': str(e)}
    
    async def calculate_performance_metrics(self, predictions: List[Dict], model_type: str) -> Dict[str, float]:
        """Calculate performance metrics based on model type"""
        
        actual_values = [p['actual_value'] for p in predictions]
        predicted_values = [p['predicted_value'] for p in predictions]
        
        if model_type in ['story_points', 'lead_time']:
            # Regression metrics
            from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
            
            return {
                'r2_score': r2_score(actual_values, predicted_values),
                'mae': mean_absolute_error(actual_values, predicted_values),
                'rmse': np.sqrt(mean_squared_error(actual_values, predicted_values)),
                'sample_count': len(predictions)
            }
            
        elif model_type == 'rework_risk':
            # Classification metrics
            from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score
            
            return {
                'f1_score': f1_score(actual_values, predicted_values),
                'precision': precision_score(actual_values, predicted_values),
                'recall': recall_score(actual_values, predicted_values),
                'accuracy': accuracy_score(actual_values, predicted_values),
                'sample_count': len(predictions)
            }
```

## ✅ Success Criteria

1. **Data Drift Detection**: Automatically detect data pattern changes with 90%+ accuracy
2. **Adaptive Scheduling**: Training frequency adapts to tenant data patterns and volume
3. **Performance Monitoring**: Real-time model performance tracking with degradation alerts
4. **Resource Optimization**: 50% reduction in unnecessary training while maintaining accuracy
5. **Production Stability**: Zero model-related production issues or performance degradation

## 🚨 Risk Mitigation

1. **False Drift Detection**: Multiple statistical tests with consensus-based decisions
2. **Over-Training**: Minimum time intervals between training runs
3. **Resource Exhaustion**: Training resource limits and scheduling optimization
4. **Model Degradation**: Automatic rollback to previous models if performance drops
5. **Data Quality**: Comprehensive data validation before training

## 📋 Implementation Checklist

- [ ] Implement data drift detection with multiple statistical tests
- [ ] Create adaptive training scheduler based on tenant patterns
- [ ] Build advanced performance monitoring and alerting
- [ ] Implement model rollback capabilities for performance degradation
- [ ] Add resource optimization and training scheduling
- [ ] Create comprehensive logging and monitoring for smart ML operations
- [ ] Test drift detection with various data scenarios
- [ ] Validate adaptive scheduling with different tenant profiles

## 🔄 Next Steps

After completion, this enables:
- **Phase 5**: AI Service implementation with reliable, optimized ML models
- **Production Deployment**: Enterprise-grade ML operations with automatic optimization
- **Continuous Improvement**: Self-optimizing ML pipeline that adapts to changing data patterns
