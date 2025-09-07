# Phase 1-2: Unified Models Updates

**Implemented**: YES ✅
**Duration**: Days 3-4
**Priority**: CRITICAL
**Dependencies**: Phase 1-1 (Database Schema) must be completed
**Must Complete Before**: Phase 1-3 (ETL Jobs) and Phase 1-4 (Backend APIs)

## 🎯 Objectives

1. **Backend Models Update**: Add vector columns and ML models to unified_models.py
2. **ETL Models Synchronization**: Mirror backend models in ETL service
3. **Serialization Enhancement**: Handle new fields in to_dict() methods
4. **Relationship Updates**: Add ML monitoring relationships to Client model
5. **Backward Compatibility**: Ensure existing functionality unchanged

## 📋 Implementation Tasks

### Task 1-2.1: Backend Service Models
**File**: `services/backend-service/app/models/unified_models.py`

**Objective**: Add vector columns and ML monitoring models

**Changes Required**:
- Add `embedding: Optional[List[float]]` to all 24 existing models
- Create 3 new ML monitoring models
- Update Client model with ML relationships
- Enhance serialization methods

### Task 1-2.2: ETL Service Models
**File**: `services/etl-service/app/models/unified_models.py`

**Objective**: Mirror backend models exactly

**Changes Required**:
- Synchronize all model definitions with backend
- Add ETL-specific methods for new fields
- Ensure data processing compatibility

## 🔧 Implementation Details

### Backend Models Pattern
```python
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.sql import func

# Pattern for all existing models
class Issue(Base):
    __tablename__ = 'issues'
    
    # All existing fields (unchanged)
    id = Column(Integer, primary_key=True)
    key = Column(String(50), nullable=False)
    summary = Column(Text)
    description = Column(Text)
    priority = Column(String(50))
    status_name = Column(String(100))
    issuetype_name = Column(String(100))
    assignee = Column(String(100))
    assignee_id = Column(Integer)
    reporter = Column(String(100))
    reporter_id = Column(Integer)
    created = Column(DateTime(timezone=True))
    updated = Column(DateTime(timezone=True))
    resolved = Column(DateTime(timezone=True))
    due_date = Column(DateTime(timezone=True))
    story_points = Column(Integer)
    epic_link = Column(String(50))
    parent_key = Column(String(50))
    level_number = Column(Integer, default=0)
    
    # Timing and workflow fields
    work_started_at = Column(DateTime(timezone=True))
    work_first_completed_at = Column(DateTime(timezone=True))
    work_last_completed_at = Column(DateTime(timezone=True))
    total_lead_time_seconds = Column(BigInteger)
    
    # Custom fields (1-20)
    custom_field_01 = Column(Text)
    custom_field_02 = Column(Text)
    # ... (all 20 custom fields)
    
    # Relationships
    project_id = Column(Integer, ForeignKey('projects.id'))
    status_id = Column(Integer)
    issuetype_id = Column(Integer)
    parent_id = Column(Integer, ForeignKey('issues.id'))
    
    # Metadata
    comment_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    active = Column(Boolean, default=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    
    # NEW: Vector column (matches database schema)
    embedding: Optional[List[float]] = Column(ARRAY(Float), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="work_items")
    project = relationship("Project", back_populates="work_items")
    parent = relationship("WorkItem", remote_side=[id])
    
    def to_dict(self, include_ml_fields: bool = False):
        """Enhanced serialization with optional ML fields"""
        result = {
            'id': self.id,
            'key': self.key,
            'summary': self.summary,
            'description': self.description,
            'priority': self.priority,
            'status_name': self.status_name,
            'issuetype_name': self.issuetype_name,
            'assignee': self.assignee,
            'assignee_id': self.assignee_id,
            'reporter': self.reporter,
            'reporter_id': self.reporter_id,
            'created': self.created.isoformat() if self.created else None,
            'updated': self.updated.isoformat() if self.updated else None,
            'resolved': self.resolved.isoformat() if self.resolved else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'story_points': self.story_points,
            'epic_link': self.epic_link,
            'parent_key': self.parent_key,
            'level_number': self.level_number,
            'work_started_at': self.work_started_at.isoformat() if self.work_started_at else None,
            'work_first_completed_at': self.work_first_completed_at.isoformat() if self.work_first_completed_at else None,
            'work_last_completed_at': self.work_last_completed_at.isoformat() if self.work_last_completed_at else None,
            'total_lead_time_seconds': self.total_lead_time_seconds,
            'project_id': self.project_id,
            'status_id': self.status_id,
            'issuetype_id': self.issuetype_id,
            'parent_id': self.parent_id,
            'comment_count': self.comment_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'active': self.active,
            'client_id': self.client_id
        }
        
        # Add custom fields
        for i in range(1, 21):
            field_name = f'custom_field_{i:02d}'
            if hasattr(self, field_name):
                result[field_name] = getattr(self, field_name)
        
        # Include ML fields only if requested
        if include_ml_fields and hasattr(self, 'embedding'):
            result['embedding'] = self.embedding
        
        return result
```

### New ML Monitoring Models
```python
class AILearningMemory(Base):
    __tablename__ = 'ai_learning_memory'
    
    id = Column(Integer, primary_key=True)
    error_type = Column(String(50), nullable=False)
    user_intent = Column(Text, nullable=False)
    failed_query = Column(Text, nullable=False)
    specific_issue = Column(Text, nullable=False)
    suggested_fix = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    learning_context = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    active = Column(Boolean, default=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    
    # Relationships
    client = relationship("Client", back_populates="ai_learning_memories")
    
    def to_dict(self):
        return {
            'id': self.id,
            'error_type': self.error_type,
            'user_intent': self.user_intent,
            'failed_query': self.failed_query,
            'specific_issue': self.specific_issue,
            'suggested_fix': self.suggested_fix,
            'confidence': self.confidence,
            'learning_context': self.learning_context,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'active': self.active,
            'client_id': self.client_id
        }

class MLPredictionLog(Base):
    __tablename__ = 'ml_prediction_log'
    
    id = Column(Integer, primary_key=True)
    model_name = Column(String(100), nullable=False)
    prediction_value = Column(Float, nullable=False)
    input_features = Column(JSON)
    anomaly_score = Column(Float)
    is_anomaly = Column(Boolean, default=False)
    severity = Column(String(20), default='normal')
    response_time_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    active = Column(Boolean, default=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    
    # Relationships
    client = relationship("Client", back_populates="ml_prediction_logs")
    
    def to_dict(self):
        return {
            'id': self.id,
            'model_name': self.model_name,
            'prediction_value': self.prediction_value,
            'input_features': self.input_features,
            'anomaly_score': self.anomaly_score,
            'is_anomaly': self.is_anomaly,
            'severity': self.severity,
            'response_time_ms': self.response_time_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'active': self.active,
            'client_id': self.client_id
        }

class MLAnomalyAlert(Base):
    __tablename__ = 'ml_anomaly_alerts'
    
    id = Column(Integer, primary_key=True)
    model_name = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)
    alert_data = Column(JSON, nullable=False)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(Integer, ForeignKey('users.id'))
    acknowledged_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    active = Column(Boolean, default=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    
    # Relationships
    client = relationship("Client", back_populates="ml_anomaly_alerts")
    acknowledged_user = relationship("User")
    
    def to_dict(self):
        return {
            'id': self.id,
            'model_name': self.model_name,
            'severity': self.severity,
            'alert_data': self.alert_data,
            'acknowledged': self.acknowledged,
            'acknowledged_by': self.acknowledged_by,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'active': self.active,
            'client_id': self.client_id
        }
```

### Enhanced Client Model
```python
class Client(Base):
    __tablename__ = 'clients'
    
    # All existing fields (unchanged)
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    # ... all existing fields ...
    
    # NEW: Vector column
    embedding: Optional[List[float]] = Column(ARRAY(Float), nullable=True)
    
    # Existing relationships (all preserved)
    users = relationship("User", back_populates="client")
    projects = relationship("Project", back_populates="client")
    issues = relationship("Issue", back_populates="client")
    # ... all existing relationships ...
    
    # NEW: ML monitoring relationships
    ai_learning_memories = relationship("AILearningMemory", back_populates="client")
    ml_prediction_logs = relationship("MLPredictionLog", back_populates="client")
    ml_anomaly_alerts = relationship("MLAnomalyAlert", back_populates="client")
```

### ETL Models Synchronization
```python
# services/etl-service/app/models/unified_models.py

# Mirror all backend models exactly
class Issue(Base):
    __tablename__ = 'issues'
    
    # All fields identical to backend model
    # Including: embedding: Optional[List[float]] = Column(ARRAY(Float), nullable=True)
    
    def prepare_for_insert(self):
        """ETL-specific method for data preparation"""
        # Existing logic preserved
        
        # NEW: Set embedding to None during Phase 1
        self.embedding = None
        return self
    
    def to_dict(self, include_ml_fields: bool = False):
        """Mirror backend serialization exactly"""
        # Identical implementation to backend model
        pass
```

## ✅ Success Criteria

1. **Model Updates**: All 24 models have vector columns
2. **ML Models**: 3 new ML monitoring models created
3. **Serialization**: to_dict() methods handle new fields
4. **ETL Sync**: ETL models mirror backend exactly
5. **Relationships**: Client model has ML relationships
6. **Compatibility**: Existing functionality unchanged
7. **Testing**: All models instantiate without errors

## 📝 Testing Checklist

- [ ] All 24 backend models updated with vector columns
- [ ] ML monitoring models created and functional
- [ ] Client model relationships updated
- [ ] ETL models synchronized with backend
- [ ] Model instantiation works without errors
- [ ] Serialization methods handle new fields
- [ ] Backward compatibility maintained
- [ ] Database connections work with new models

## 🔄 Completion Enables

- **Phase 1-3**: ETL jobs can use updated models
- **Phase 1-4**: Backend APIs can use enhanced models
- **Phase 1-5**: Auth service can use updated User model
- **Phase 1-6**: Frontend can receive enhanced data structures

## 📋 Handoff to Phase 1-3 & 1-4

**Deliverables**:
- ✅ Backend unified models with vector columns and ML models
- ✅ ETL unified models synchronized with backend
- ✅ Enhanced serialization methods
- ✅ ML monitoring relationships established

**Next Phase Requirements**:
- Update ETL jobs to use new models (Phase 1-3)
- Update Backend APIs to handle new fields (Phase 1-4)
- Test model usage in data processing and API responses
