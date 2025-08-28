"""
Test AI Enhanced Models - Pulse AI Evolution Plan Phase 1-2
Tests the enhanced unified models with vector columns and ML monitoring.
"""

import pytest
import json
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.unified_models import Base, Client, User, Issue, Repository, PullRequest
from app.models.unified_models import AILearningMemory, AIPrediction, AIPerformanceMetric
from app.utils.ai_utils import AIEmbeddingManager, AILearningManager, AIPredictionManager, AIPerformanceManager


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client(db_session):
    """Create a test client."""
    client = Client(
        name="Test Client",
        website="https://test.com",
        assets_folder="test_assets",
        active=True
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


class TestAIEnhancedModels:
    """Test AI enhanced models functionality."""
    
    def test_client_model_has_embedding_column(self, db_session, test_client):
        """Test that Client model has embedding column."""
        # Check that embedding column exists and can be set
        test_embedding = [0.1, 0.2, 0.3] * 512  # 1536 dimensions
        test_client.embedding = test_embedding
        
        db_session.commit()
        db_session.refresh(test_client)
        
        assert test_client.embedding is not None
        assert len(test_client.embedding) == 1536
    
    def test_user_model_has_embedding_column(self, db_session, test_client):
        """Test that User model has embedding column."""
        user = User(
            client_id=test_client.id,
            email="test@example.com",
            first_name="Test",
            last_name="User",
            role="user"
        )
        
        # Set embedding
        test_embedding = [0.1, 0.2, 0.3] * 512  # 1536 dimensions
        user.embedding = test_embedding
        
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        assert user.embedding is not None
        assert len(user.embedding) == 1536
    
    def test_ai_learning_memory_model(self, db_session, test_client):
        """Test AILearningMemory model functionality."""
        learning_memory = AILearningMemory(
            client_id=test_client.id,
            error_type="query_parsing",
            user_intent="Find issues by status",
            failed_query="SELECT * FROM issues WHERE status = 'invalid'",
            specific_issue="Invalid status value provided",
            corrected_query="SELECT * FROM issues WHERE status = 'open'",
            user_feedback="The status should be 'open' not 'invalid'",
            message_id="msg_123"
        )
        
        db_session.add(learning_memory)
        db_session.commit()
        db_session.refresh(learning_memory)
        
        assert learning_memory.id is not None
        assert learning_memory.client_id == test_client.id
        assert learning_memory.error_type == "query_parsing"
        assert learning_memory.created_at is not None
    
    def test_ai_prediction_model(self, db_session, test_client):
        """Test AIPrediction model functionality."""
        input_data = {"issue_count": 100, "complexity_factors": ["dependencies", "size"]}
        prediction_result = {"estimated_completion_days": 14, "confidence": 0.85}
        
        prediction = AIPrediction(
            client_id=test_client.id,
            model_name="trajectory_predictor",
            model_version="1.2",
            input_data=json.dumps(input_data),
            prediction_result=json.dumps(prediction_result),
            confidence_score=0.85,
            prediction_type="trajectory"
        )
        
        db_session.add(prediction)
        db_session.commit()
        db_session.refresh(prediction)
        
        assert prediction.id is not None
        assert prediction.client_id == test_client.id
        assert prediction.model_name == "trajectory_predictor"
        assert json.loads(prediction.input_data) == input_data
        assert json.loads(prediction.prediction_result) == prediction_result
    
    def test_ai_performance_metric_model(self, db_session, test_client):
        """Test AIPerformanceMetric model functionality."""
        context_data = {"operation": "data_sync", "records_processed": 1000}
        
        metric = AIPerformanceMetric(
            client_id=test_client.id,
            metric_name="sync_processing_time",
            metric_value=45.5,
            metric_unit="seconds",
            service_name="backend",
            context_data=json.dumps(context_data)
        )
        
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)
        
        assert metric.id is not None
        assert metric.client_id == test_client.id
        assert metric.metric_name == "sync_processing_time"
        assert metric.metric_value == 45.5
        assert json.loads(metric.context_data) == context_data
    
    def test_client_ml_monitoring_relationships(self, db_session, test_client):
        """Test that Client has relationships to ML monitoring tables."""
        # Create related records
        learning_memory = AILearningMemory(
            client_id=test_client.id,
            error_type="test",
            user_intent="test intent",
            failed_query="test query",
            specific_issue="test issue"
        )
        
        prediction = AIPrediction(
            client_id=test_client.id,
            model_name="test_model",
            input_data="{}",
            prediction_result="{}",
            prediction_type="test"
        )
        
        metric = AIPerformanceMetric(
            client_id=test_client.id,
            metric_name="test_metric",
            metric_value=1.0,
            service_name="backend"
        )
        
        db_session.add_all([learning_memory, prediction, metric])
        db_session.commit()
        
        # Test relationships
        db_session.refresh(test_client)
        assert len(test_client.ai_learning_memories) == 1
        assert len(test_client.ai_predictions) == 1
        assert len(test_client.ai_performance_metrics) == 1


class TestAIUtilities:
    """Test AI utility functions."""
    
    def test_ai_embedding_manager_create_vector(self):
        """Test embedding vector creation."""
        embedding = AIEmbeddingManager.create_embedding_vector()
        
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)
        assert all(-1.0 <= x <= 1.0 for x in embedding)
    
    def test_ai_learning_manager_log_feedback(self, db_session, test_client):
        """Test logging user feedback."""
        learning_memory = AILearningManager.log_user_feedback(
            db=db_session,
            client_id=test_client.id,
            error_type="parsing_error",
            user_intent="Search for issues",
            failed_query="invalid query",
            specific_issue="Syntax error in query",
            corrected_query="corrected query",
            user_feedback="This should work better"
        )
        
        assert learning_memory is not None
        assert learning_memory.client_id == test_client.id
        assert learning_memory.error_type == "parsing_error"
    
    def test_ai_prediction_manager_log_prediction(self, db_session, test_client):
        """Test logging AI predictions."""
        input_data = {"feature1": 10, "feature2": "value"}
        prediction_result = {"prediction": "positive", "score": 0.8}
        
        prediction = AIPredictionManager.log_prediction(
            db=db_session,
            client_id=test_client.id,
            model_name="test_classifier",
            input_data=input_data,
            prediction_result=prediction_result,
            prediction_type="classification",
            confidence_score=0.8
        )
        
        assert prediction is not None
        assert prediction.client_id == test_client.id
        assert prediction.model_name == "test_classifier"
        assert json.loads(prediction.input_data) == input_data
    
    def test_ai_performance_manager_log_metric(self, db_session, test_client):
        """Test logging performance metrics."""
        context_data = {"endpoint": "/api/issues", "method": "GET"}
        
        metric = AIPerformanceManager.log_performance_metric(
            db=db_session,
            client_id=test_client.id,
            metric_name="api_response_time",
            metric_value=150.5,
            service_name="backend",
            metric_unit="milliseconds",
            context_data=context_data
        )
        
        assert metric is not None
        assert metric.client_id == test_client.id
        assert metric.metric_name == "api_response_time"
        assert metric.metric_value == 150.5
        assert json.loads(metric.context_data) == context_data


if __name__ == "__main__":
    pytest.main([__file__])
