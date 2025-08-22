# Phase 1-4: Backend Service API Updates

**Duration**: Days 7-8  
**Priority**: CRITICAL  
**Dependencies**: Phase 1-2 (Unified Models) must be completed  
**Can Run Parallel With**: Phase 1-3 (ETL Jobs)

## 🎯 Objectives

1. **Database Router Enhancement**: Add ML session support for future phases
2. **API Endpoints Updates**: Add optional ML fields in API responses
3. **Health Check Enhancement**: Monitor new infrastructure components
4. **Response Serialization**: Use enhanced models' to_dict() methods
5. **ML Table Access**: Read-only access to ML monitoring tables

## 📋 Implementation Tasks

### Task 1-4.1: Database Router Enhancement
**File**: `services/backend-service/app/core/database.py`

**Objective**: Add ML session support for future ML operations

### Task 1-4.2: Core API Endpoints Updates
**Files**: 
- `services/backend-service/app/api/issues.py`
- `services/backend-service/app/api/pull_requests.py`
- `services/backend-service/app/api/projects.py`
- `services/backend-service/app/api/users.py`

**Objective**: Handle new fields without breaking functionality

### Task 1-4.3: Health Check Enhancements
**File**: `services/backend-service/app/api/health.py`

**Objective**: Monitor new infrastructure components

### Task 1-4.4: ML Monitoring Endpoints
**File**: `services/backend-service/app/api/ml_monitoring.py`

**Objective**: Read-only access to ML tables (Phase 1)

## 🔧 Implementation Details

### Enhanced Database Router
```python
# services/backend-service/app/core/database.py

from contextlib import contextmanager
from sqlalchemy import text
from typing import Generator
import logging

logger = logging.getLogger(__name__)

class EnhancedDatabaseRouter(DatabaseRouter):
    """Enhanced database router with ML session support"""
    
    def __init__(self):
        super().__init__()
        # Existing initialization preserved
    
    @contextmanager
    def get_ml_session_context(self) -> Generator[Session, None, None]:
        """Context manager for ML operations (replica-only, optimized)"""
        session = self.get_read_session()  # Always routes to replica
        try:
            # Optimize for ML workloads
            session.execute(text("SET statement_timeout = '300s'"))
            session.execute(text("SET transaction_read_only = on"))
            session.execute(text("SET work_mem = '256MB'"))  # Larger work memory for ML
            session.execute(text("SET random_page_cost = 1.1"))  # Optimize for SSD
            
            logger.debug("ML session context initialized")
            yield session
            
        except Exception as e:
            logger.error(f"ML session error: {e}")
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_ml_session(self, read_only: bool = True) -> Session:
        """Get session optimized for ML operations (typically read-only)"""
        if read_only:
            session = self.get_read_session()
        else:
            session = self.get_write_session()

        return session
    
    def test_vector_column_access(self) -> bool:
        """Test if vector columns are accessible"""
        try:
            with self.get_read_session() as session:
                # Test vector column access on a few key tables
                session.execute(text("SELECT embedding FROM issues LIMIT 1"))
                session.execute(text("SELECT embedding FROM pull_requests LIMIT 1"))
                session.execute(text("SELECT embedding FROM projects LIMIT 1"))
                return True
        except Exception as e:
            logger.warning(f"Vector column access test failed: {e}")
            return False
```

### Enhanced API Endpoints
```python
# services/backend-service/app/api/issues.py

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

router = APIRouter()

@router.get("/api/issues")
async def get_issues(
    client_id: int = Query(...),
    include_ml_fields: bool = Query(False, description="Include ML fields in response"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(get_current_user)
):
    """Get issues with optional ML fields"""
    try:
        # Existing query logic (unchanged)
        query = db.query(Issue).filter(
            Issue.client_id == client_id,
            Issue.active == True
        ).order_by(Issue.created_at.desc())
        
        # Apply pagination
        total_count = query.count()
        issues = query.offset(offset).limit(limit).all()
        
        # Enhanced response with optional ML fields
        result = []
        for issue in issues:
            issue_dict = issue.to_dict(include_ml_fields=include_ml_fields)
            result.append(issue_dict)
        
        return {
            'issues': result,
            'count': len(result),
            'total_count': total_count,
            'offset': offset,
            'limit': limit,
            'ml_fields_included': include_ml_fields
        }
        
    except Exception as e:
        logger.error(f"Error fetching issues: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch issues")

@router.get("/api/issues/{issue_id}")
async def get_issue(
    issue_id: int,
    include_ml_fields: bool = Query(False),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(get_current_user)
):
    """Get single issue with optional ML fields"""
    try:
        issue = db.query(Issue).filter(
            Issue.id == issue_id,
            Issue.client_id == user.client_id,
            Issue.active == True
        ).first()
        
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        return issue.to_dict(include_ml_fields=include_ml_fields)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching issue {issue_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch issue")

@router.post("/api/issues")
async def create_issue(
    issue_data: IssueCreateRequest,
    db: Session = Depends(get_write_session),
    user: UserData = Depends(get_current_user)
):
    """Create issue - models handle new fields automatically"""
    try:
        # Create issue normally - embedding defaults to None in model
        issue = Issue(
            key=issue_data.key,
            summary=issue_data.summary,
            description=issue_data.description,
            priority=issue_data.priority,
            status_name=issue_data.status_name,
            issuetype_name=issue_data.issuetype_name,
            assignee=issue_data.assignee,
            reporter=issue_data.reporter,
            story_points=issue_data.story_points,
            epic_link=issue_data.epic_link,
            project_id=issue_data.project_id,
            status_id=issue_data.status_id,
            issuetype_id=issue_data.issuetype_id,
            client_id=user.client_id,
            active=True
            # embedding automatically defaults to None in model
        )
        
        db.add(issue)
        db.commit()
        db.refresh(issue)
        
        return issue.to_dict()
        
    except Exception as e:
        logger.error(f"Error creating issue: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create issue")

@router.put("/api/issues/{issue_id}")
async def update_issue(
    issue_id: int,
    issue_data: IssueUpdateRequest,
    db: Session = Depends(get_write_session),
    user: UserData = Depends(get_current_user)
):
    """Update issue - models handle new fields automatically"""
    try:
        issue = db.query(Issue).filter(
            Issue.id == issue_id,
            Issue.client_id == user.client_id,
            Issue.active == True
        ).first()

        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")

        # Update existing fields normally
        for field, value in issue_data.dict(exclude_unset=True).items():
            if hasattr(issue, field):
                setattr(issue, field, value)

        db.commit()
        db.refresh(issue)

        return issue.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating issue {issue_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update issue")
```

### Enhanced Health Checks
```python
# services/backend-service/app/api/health.py

@router.get("/health/database")
async def check_database_health():
    """Enhanced database health check including ML tables"""
    try:
        with get_read_session() as session:
            # Test existing tables
            session.execute(text("SELECT 1 FROM issues LIMIT 1"))
            session.execute(text("SELECT 1 FROM pull_requests LIMIT 1"))
            session.execute(text("SELECT 1 FROM projects LIMIT 1"))
            
            # Test new ML tables (Phase 1: May not have data yet)
            ml_tables_status = {}
            ml_tables = ['ai_learning_memory', 'ml_prediction_log', 'ml_anomaly_alerts']
            
            for table in ml_tables:
                try:
                    session.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                    ml_tables_status[table] = "available"
                except Exception:
                    ml_tables_status[table] = "not_available"
            
            # Test vector columns (Phase 1: Should exist but be null)
            vector_status = {}
            vector_tables = ['issues', 'pull_requests', 'projects', 'users']
            
            for table in vector_tables:
                try:
                    result = session.execute(text(f"SELECT COUNT(*) FROM {table} WHERE embedding IS NOT NULL")).scalar()
                    vector_status[f'{table}_with_embeddings'] = result
                except Exception:
                    vector_status[f'{table}_with_embeddings'] = "column_not_available"
            
            return {
                "status": "healthy",
                "database_connection": "ok",
                "ml_tables": ml_tables_status,
                "vector_columns": vector_status,
                "timestamp": datetime.utcnow()
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }

@router.get("/health/ml")
async def check_ml_health():
    """ML infrastructure health check"""
    try:
        with get_ml_session_context() as session:
            # Test PostgresML availability (Phase 1: May not be available)
            try:
                result = session.execute(text("SELECT pgml.version()")).scalar()
                postgresml_status = {"available": True, "version": result}
            except Exception as e:
                postgresml_status = {"available": False, "error": str(e)}
            
            # Test pgvector availability
            try:
                session.execute(text("SELECT '[1,2,3]'::vector"))
                pgvector_status = {"available": True}
            except Exception as e:
                pgvector_status = {"available": False, "error": str(e)}
            
            # Test vector column access
            vector_access = test_vector_column_access()
            
            return {
                "status": "healthy" if pgvector_status["available"] else "degraded",
                "postgresml": postgresml_status,
                "pgvector": pgvector_status,
                "vector_columns_accessible": vector_access,
                "replica_connection": "ok",
                "timestamp": datetime.utcnow()
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }
```

### ML Monitoring Endpoints (Read-Only)
```python
# services/backend-service/app/api/ml_monitoring.py

@router.get("/api/ml/learning-memory")
async def get_learning_memory(
    client_id: int = Query(...),
    error_type: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_admin_user)
):
    """Get AI learning memory for analysis (admin only)"""
    try:
        query = db.query(AILearningMemory).filter(
            AILearningMemory.client_id == client_id,
            AILearningMemory.active == True
        )
        
        if error_type:
            query = query.filter(AILearningMemory.error_type == error_type)
        
        memories = query.order_by(AILearningMemory.created_at.desc()).limit(limit).all()
        
        return {
            "learning_memories": [memory.to_dict() for memory in memories],
            "count": len(memories),
            "error_type_filter": error_type
        }
        
    except Exception as e:
        logger.error(f"Error fetching learning memory: {e}")
        raise HTTPException(500, f"Failed to fetch learning memory: {str(e)}")

@router.get("/api/ml/prediction-logs")
async def get_prediction_logs(
    client_id: int = Query(...),
    model_name: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_admin_user)
):
    """Get ML prediction logs for monitoring (admin only)"""
    try:
        query = db.query(MLPredictionLog).filter(
            MLPredictionLog.client_id == client_id,
            MLPredictionLog.active == True
        )
        
        if model_name:
            query = query.filter(MLPredictionLog.model_name == model_name)
        
        logs = query.order_by(MLPredictionLog.created_at.desc()).limit(limit).all()
        
        return {
            "prediction_logs": [log.to_dict() for log in logs],
            "count": len(logs),
            "model_name_filter": model_name
        }
        
    except Exception as e:
        logger.error(f"Error fetching prediction logs: {e}")
        raise HTTPException(500, f"Failed to fetch prediction logs: {str(e)}")

@router.get("/api/ml/anomaly-alerts")
async def get_anomaly_alerts(
    client_id: int = Query(...),
    acknowledged: Optional[bool] = Query(None),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_admin_user)
):
    """Get ML anomaly alerts for monitoring (admin only)"""
    try:
        query = db.query(MLAnomalyAlert).filter(
            MLAnomalyAlert.client_id == client_id,
            MLAnomalyAlert.active == True
        )
        
        if acknowledged is not None:
            query = query.filter(MLAnomalyAlert.acknowledged == acknowledged)
        
        alerts = query.order_by(MLAnomalyAlert.created_at.desc()).limit(limit).all()
        
        return {
            "anomaly_alerts": [alert.to_dict() for alert in alerts],
            "count": len(alerts),
            "acknowledged_filter": acknowledged
        }
        
    except Exception as e:
        logger.error(f"Error fetching anomaly alerts: {e}")
        raise HTTPException(500, f"Failed to fetch anomaly alerts: {str(e)}")
```

## ✅ Success Criteria

1. **Database Router**: ML session support ready for future phases
2. **API Endpoints**: All existing endpoints work with enhanced models
3. **Health Checks**: Monitor new infrastructure components
4. **ML Endpoints**: Read-only access to ML monitoring tables
5. **Response Handling**: Optional ML fields in API responses using model to_dict()
6. **Model Integration**: Enhanced models work seamlessly in API operations
7. **Performance**: No significant performance degradation
8. **Simplicity**: No special compatibility code needed - models handle it

## 📝 Testing Checklist

- [ ] All existing API endpoints work unchanged
- [ ] New include_ml_fields parameter works correctly
- [ ] Health checks pass for new infrastructure
- [ ] ML monitoring endpoints accessible (admin only)
- [ ] Database router handles ML sessions
- [ ] Vector column access tests pass
- [ ] Error handling prevents API failures
- [ ] Response serialization includes optional ML fields

## 🔄 Completion Enables

- **Phase 1-5**: Auth service can integrate with enhanced backend
- **Phase 1-6**: Frontend can consume enhanced API responses
- **Phase 1-7**: Integration testing can validate API functionality

## 📋 Handoff to Phase 1-5 & 1-6

**Deliverables**:
- ✅ Enhanced database router with ML support
- ✅ Updated API endpoints with optional ML fields
- ✅ Comprehensive health checks
- ✅ ML monitoring endpoints (read-only)

**Next Phase Requirements**:
- Auth service can use enhanced backend APIs (Phase 1-5)
- Frontend can consume API responses with optional ML fields (Phase 1-6)
- Integration testing can validate end-to-end functionality (Phase 1-7)
