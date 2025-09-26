# Phase 4-2: Automated ML Training Jobs

**Implemented**: NO ❌
**Duration**: Week 2 of Phase 4
**Priority**: HIGH
**Risk Level**: MEDIUM

## 💼 Business Outcome

**Automated ML Pipeline**: Establish automated model retraining capabilities that continuously improve prediction accuracy without manual intervention, ensuring models stay current with evolving data patterns and maintain 70%+ accuracy over time.

## 🎯 Objectives

1. **Automated Training Jobs**: Create scheduled ML training jobs in ETL orchestrator
2. **Training Decision Logic**: Implement smart retraining triggers based on data volume and performance
3. **Model Performance Monitoring**: Track model accuracy and trigger retraining when needed
4. **Training Pipeline Integration**: Integrate ML training with existing ETL job flow

## 🔒 CRITICAL: Tenant Isolation Requirements

**ALL automated ML operations must respect multi-tenancy:**
- **Scheduled Training**: Separate training schedules per tenant
- **Data Filtering**: All training queries MUST include `tenant_id = X` filters
- **Model Versioning**: Tenant-specific model naming (`model_tenant_1_v2`)
- **Performance Tracking**: ML metrics filtered by `tenant_id`

## 📋 Task Breakdown

### Task 4-2.1: ML Training Job Implementation
**Duration**: 2-3 days  
**Priority**: CRITICAL  

#### Automated Training Job Structure
```python
# services/etl-service/app/jobs/ml_training/ml_training_job.py

class MLModelTrainingJob:
    """Automated ML model retraining job"""
    
    def __init__(self):
        self.min_new_samples = {
            'story_points': 50,      # Retrain after 50 new items
            'lead_time': 30,         # Retrain after 30 completed items
            'rework_risk': 25        # Retrain after 25 merged PRs
        }
        self.min_accuracy_threshold = {
            'story_points': 0.7,     # R² score
            'lead_time': 0.6,        # R² score  
            'rework_risk': 0.65      # F1 score
        }
        self.max_days_without_training = 30
    
    async def run_ml_training(self, tenant_id: int) -> Dict[str, Any]:
        """Main training execution for a tenant"""
        try:
            logger.info(f"Starting ML training assessment for tenant {tenant_id}")
            
            # Check if retraining is needed
            training_needed = await self.assess_training_requirements(tenant_id)
            
            if not any(training_needed.values()):
                return {
                    'status': 'skipped',
                    'reason': 'no_training_needed',
                    'assessment': training_needed
                }
            
            # Execute training for models that need it
            training_results = {}
            
            if training_needed['story_points']:
                result = await self.retrain_story_point_model(tenant_id)
                training_results['story_points'] = result
            
            if training_needed['lead_time']:
                result = await self.retrain_lead_time_model(tenant_id)
                training_results['lead_time'] = result
                
            if training_needed['rework_risk']:
                result = await self.retrain_rework_risk_model(tenant_id)
                training_results['rework_risk'] = result
            
            return {
                'status': 'success',
                'models_trained': list(training_results.keys()),
                'results': training_results
            }
            
        except Exception as e:
            logger.error(f"ML training failed for tenant {tenant_id}: {e}")
            return {'status': 'failed', 'error': str(e)}
```

#### Training Requirements Assessment
```python
async def assess_training_requirements(self, tenant_id: int) -> Dict[str, bool]:
    """
    Determine which models need retraining based on:
    1. New data volume since last training
    2. Model performance degradation  
    3. Time since last training
    """
    
    # Get last training metadata
    last_training = await self.get_last_training_metadata(tenant_id)
    
    # Count new training data
    new_data_counts = await self.count_new_training_data(tenant_id, last_training)
    
    # Check current model performance
    current_performance = await self.evaluate_current_models(tenant_id)
    
    # Calculate days since last training
    days_since_training = {
        model: (datetime.now() - last_training[model]['date']).days 
        if last_training[model] else 999
        for model in ['story_points', 'lead_time', 'rework_risk']
    }
    
    # Decision logic for each model
    training_needed = {}
    
    for model_type in ['story_points', 'lead_time', 'rework_risk']:
        training_needed[model_type] = (
            # Sufficient new data
            new_data_counts[model_type] >= self.min_new_samples[model_type] or
            
            # Performance degraded
            (current_performance[model_type] and 
             current_performance[model_type] < self.min_accuracy_threshold[model_type]) or
            
            # Too much time passed
            days_since_training[model_type] >= self.max_days_without_training
        )
    
    logger.info(f"Training assessment for tenant {tenant_id}: {training_needed}")
    return training_needed
```

### Task 4-2.2: ETL Orchestrator Integration
**Duration**: 1-2 days
**Priority**: HIGH

#### Add ML Training to Job Schedule
```python
# services/etl-service/app/jobs/orchestrator.py

# Add ML training job to orchestrator
async def setup_ml_training_jobs(tenant_id: int):
    """Add ML training job to the orchestration schedule"""
    
    # Check if ML training job exists
    existing_ml_job = session.query(JobSchedule).filter(
        JobSchedule.tenant_id == tenant_id,
        JobSchedule.job_name.ilike('ML Training')
    ).first()
    
    if not existing_ml_job:
        # Create ML training job
        ml_job = JobSchedule(
            tenant_id=tenant_id,
            integration_id=None,  # System job, not integration-specific
            job_name='ML Training',
            execution_order=99,   # Run after all data jobs
            status='PENDING',
            active=True
        )
        session.add(ml_job)
        session.commit()
        logger.info(f"Created ML training job for tenant {tenant_id}")

# Modified orchestrator to include ML training
async def run_orchestrator_for_client(tenant_id: int):
    """Enhanced orchestrator with ML training"""
    
    # ... existing orchestrator logic ...
    
    # After all data jobs complete, check for ML training
    if pending_job_name.lower() == 'ml training':
        logger.info("TRIGGERING: ML Training job...")
        asyncio.create_task(run_ml_training_async(pending_job_id))
```

#### ML Training Job Execution
```python
async def run_ml_training_async(job_schedule_id: int):
    """Execute ML training job asynchronously"""
    
    database = get_database()
    
    with database.get_job_session_context() as session:
        # Get job details
        job_schedule = session.query(JobSchedule).get(job_schedule_id)
        tenant_id = job_schedule.tenant_id
        
        try:
            # Update job status
            job_schedule.status = 'RUNNING'
            job_schedule.last_run_started_at = datetime.utcnow()
            session.commit()
            
            # Run ML training
            ml_trainer = MLModelTrainingJob()
            result = await ml_trainer.run_ml_training(tenant_id)
            
            # Update job status based on result
            if result['status'] == 'success' or result['status'] == 'skipped':
                job_schedule.status = 'FINISHED'
                job_schedule.last_success_at = datetime.utcnow()
                job_schedule.error_message = None
                
                # Set next job to PENDING (cycle back to first job)
                await set_next_job_pending(session, tenant_id, job_schedule.execution_order)
                
            else:
                job_schedule.status = 'FINISHED'  # Don't block orchestrator on ML failures
                job_schedule.error_message = result.get('error', 'ML training failed')
                
                # Still proceed to next job
                await set_next_job_pending(session, tenant_id, job_schedule.execution_order)
            
            session.commit()
            logger.info(f"ML training job completed for tenant {tenant_id}: {result}")
            
        except Exception as e:
            logger.error(f"ML training job failed for tenant {tenant_id}: {e}")
            job_schedule.status = 'FINISHED'
            job_schedule.error_message = str(e)
            session.commit()
```

## ✅ Success Criteria

1. **Automated Training**: ML models retrain automatically based on data volume and performance
2. **Orchestrator Integration**: ML training runs as part of regular ETL job cycle
3. **Performance Monitoring**: Model accuracy tracked and triggers retraining when needed
4. **Tenant Isolation**: All training operations respect multi-tenant architecture
5. **Graceful Degradation**: ML training failures don't block other ETL jobs

## 🚨 Risk Mitigation

1. **Training Failures**: ML training failures don't block ETL orchestrator
2. **Resource Usage**: Training scheduled during low-usage periods
3. **Data Quality**: Validate training data before model training
4. **Model Versioning**: Keep previous model versions for rollback
5. **Performance Impact**: Monitor training impact on database performance

## 📋 Implementation Checklist

- [ ] Implement MLModelTrainingJob class with training assessment logic
- [ ] Add training requirement evaluation (data volume, performance, time)
- [ ] Integrate ML training job into ETL orchestrator
- [ ] Create model performance monitoring and tracking
- [ ] Implement graceful error handling for training failures
- [ ] Add logging and monitoring for training operations
- [ ] Test automated training with different data scenarios
- [ ] Validate tenant isolation in training operations

## 🔄 Next Steps

After completion, this enables:
- **Phase 4-3**: Smart ML training with performance optimization and advanced triggers
- **Continuous Learning**: Models automatically improve as more data becomes available
- **Production Readiness**: Automated ML pipeline suitable for production deployment
