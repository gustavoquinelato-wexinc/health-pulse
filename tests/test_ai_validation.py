#!/usr/bin/env python3
"""
Unit tests for AI Phase 2 validation components
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from app.ai.validation import (
    validate_sql_syntax,
    validate_sql_semantics,
    validate_sql_syntax_service,
    validate_sql_semantics_service,
    StrategicAgentState,
    ValidationResult,
    ValidationFeedback,
    ErrorType,
    SelfHealingMemory,
    QueryResultValidator,
    TeamAnalysisResult,
    DORAMetricsResult,
    ReworkAnalysisResult
)

class TestSQLSyntaxValidation:
    """Test SQL syntax validation functionality"""
    
    def test_validate_sql_syntax_service_valid_query(self):
        """Test SQL syntax validation with valid query"""
        valid_sql = "SELECT team_name, COUNT(*) FROM commits WHERE tenant_id = 1 GROUP BY team_name"
        
        result = validate_sql_syntax_service(valid_sql)
        
        assert result.passed is True
        assert len(result.errors) == 0
        assert result.confidence == 1.0
    
    def test_validate_sql_syntax_service_invalid_query(self):
        """Test SQL syntax validation with invalid query"""
        invalid_sql = "SELCT team_name FORM commits"  # Typos
        
        result = validate_sql_syntax_service(invalid_sql)
        
        assert result.passed is False
        assert len(result.errors) > 0
        assert result.confidence == 0.0
    
    def test_validate_sql_syntax_service_dangerous_query(self):
        """Test SQL syntax validation with dangerous operations"""
        dangerous_sql = "SELECT * FROM commits; DROP TABLE users;"
        
        result = validate_sql_syntax_service(dangerous_sql)
        
        assert result.passed is False
        assert any("dangerous" in error.lower() for error in result.errors)
    
    def test_validate_sql_syntax_service_missing_where(self):
        """Test SQL syntax validation with missing WHERE clause"""
        update_sql = "UPDATE commits SET status = 'processed'"
        
        result = validate_sql_syntax_service(update_sql)
        
        assert result.passed is False
        assert any("WHERE" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_sql_syntax_state_function(self):
        """Test SQL syntax validation state function"""
        state = StrategicAgentState(
            sql_query="SELECT COUNT(*) FROM commits WHERE tenant_id = 1"
        )
        
        result_state = await validate_sql_syntax(state)
        
        assert result_state.sql_validation_passed is True
        assert len(result_state.validation_errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_sql_syntax_state_function_no_query(self):
        """Test SQL syntax validation with no query"""
        state = StrategicAgentState(sql_query=None)
        
        result_state = await validate_sql_syntax(state)
        
        assert result_state.sql_validation_passed is False
        assert "No SQL query to validate" in result_state.validation_errors

class TestSemanticValidation:
    """Test semantic validation functionality"""
    
    @pytest.mark.asyncio
    async def test_validate_sql_semantics_service_count_intent(self):
        """Test semantic validation with count intent"""
        sql_query = "SELECT COUNT(*) FROM commits WHERE tenant_id = 1"
        user_intent = "How many commits do we have?"
        
        result = await validate_sql_semantics_service(sql_query, user_intent)
        
        assert result.passed is True
        assert result.confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_validate_sql_semantics_service_count_mismatch(self):
        """Test semantic validation with count intent mismatch"""
        sql_query = "SELECT team_name FROM commits WHERE tenant_id = 1"
        user_intent = "How many commits do we have?"
        
        result = await validate_sql_semantics_service(sql_query, user_intent)
        
        assert result.passed is False
        assert any("count" in error.lower() for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_sql_semantics_service_average_intent(self):
        """Test semantic validation with average intent"""
        sql_query = "SELECT AVG(lead_time_hours) FROM pull_requests WHERE tenant_id = 1"
        user_intent = "What's the average lead time?"
        
        result = await validate_sql_semantics_service(sql_query, user_intent)
        
        assert result.passed is True
        assert result.confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_validate_sql_semantics_state_function(self):
        """Test semantic validation state function"""
        state = StrategicAgentState(
            user_query="How many commits do we have?",
            sql_query="SELECT COUNT(*) FROM commits WHERE tenant_id = 1"
        )
        
        result_state = await validate_sql_semantics(state)
        
        assert result_state.semantic_validation_passed is True
        assert result_state.semantic_confidence > 0.5

class TestDataStructureValidation:
    """Test data structure validation functionality"""
    
    def test_validate_team_analysis_valid_data(self):
        """Test team analysis validation with valid data"""
        valid_data = [
            {
                "team_name": "Backend Team",
                "total_commits": 150,
                "total_prs": 45,
                "avg_lead_time_hours": 24.5,
                "deployment_frequency": 2.3,
                "change_failure_rate": 0.05,
                "mttr_hours": 2.1
            }
        ]
        
        validator = QueryResultValidator()
        result = validator.validate_team_analysis(valid_data)
        
        assert result.passed is True
        assert len(result.errors) == 0
    
    def test_validate_team_analysis_invalid_data(self):
        """Test team analysis validation with invalid data"""
        invalid_data = [
            {
                "team_name": "Backend Team",
                "total_commits": 150,
                # Missing required fields
            }
        ]
        
        validator = QueryResultValidator()
        result = validator.validate_team_analysis(invalid_data)
        
        assert result.passed is False
        assert len(result.errors) > 0
    
    def test_validate_dora_metrics_valid_data(self):
        """Test DORA metrics validation with valid data"""
        valid_data = [
            {
                "metric_name": "deployment_frequency",
                "metric_value": 2.5,
                "metric_unit": "per_week",
                "time_period": "2024-01",
                "tenant_id": 1,
                "calculation_date": "2024-01-15"
            }
        ]
        
        validator = QueryResultValidator()
        result = validator.validate_dora_metrics(valid_data)
        
        assert result.passed is True
        assert len(result.errors) == 0
    
    def test_validate_rework_analysis_valid_data(self):
        """Test rework analysis validation with valid data"""
        valid_data = [
            {
                "pr_id": 123,
                "rework_cycles": 2,
                "initial_size": 100,
                "final_size": 150,
                "rework_percentage": 25.0,
                "time_to_completion_hours": 48.5
            }
        ]
        
        validator = QueryResultValidator()
        result = validator.validate_rework_analysis(valid_data)
        
        assert result.passed is True
        assert len(result.errors) == 0

class TestSelfHealingMemory:
    """Test self-healing memory system"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def healing_memory(self, mock_db_session):
        """Create SelfHealingMemory instance with mock session"""
        return SelfHealingMemory(mock_db_session)
    
    def test_generate_pattern_hash(self, healing_memory):
        """Test pattern hash generation"""
        error_pattern = "syntax_error"
        user_intent = "Count commits"
        
        hash1 = healing_memory.generate_pattern_hash(error_pattern, user_intent)
        hash2 = healing_memory.generate_pattern_hash(error_pattern, user_intent)
        
        assert hash1 == hash2  # Same input should produce same hash
        assert len(hash1) == 64  # SHA256 hash truncated to 64 chars
    
    @pytest.mark.asyncio
    async def test_record_validation_failure(self, healing_memory):
        """Test recording validation failure"""
        feedback = ValidationFeedback(
            error_type=ErrorType.SYNTAX_ERROR,
            user_intent="Count commits",
            failed_query="SELCT COUNT(*) FROM commits",
            specific_issue="SQL syntax error",
            suggested_fix="Fix SELECT spelling",
            confidence=0.8,
            learning_context={"retry_count": 1},
            tenant_id=1
        )
        
        result = await healing_memory.record_validation_failure(feedback)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_healing_suggestions_syntax_error(self, healing_memory):
        """Test getting healing suggestions for syntax error"""
        suggestions = await healing_memory.get_healing_suggestions(
            ErrorType.SYNTAX_ERROR,
            "Count commits",
            "SELCT COUNT(*) FROM commits",
            1
        )
        
        assert len(suggestions) > 0
        assert any("syntax" in suggestion.lower() for suggestion in suggestions)
    
    @pytest.mark.asyncio
    async def test_get_healing_suggestions_semantic_error(self, healing_memory):
        """Test getting healing suggestions for semantic error"""
        suggestions = await healing_memory.get_healing_suggestions(
            ErrorType.SEMANTIC_ERROR,
            "Count commits",
            "SELECT team_name FROM commits",
            1
        )
        
        assert len(suggestions) > 0
        assert any("count" in suggestion.lower() for suggestion in suggestions)
    
    @pytest.mark.asyncio
    async def test_record_successful_healing(self, healing_memory):
        """Test recording successful healing"""
        pattern_hash = "test_hash_123"
        successful_query = "SELECT COUNT(*) FROM commits WHERE tenant_id = 1"
        
        result = await healing_memory.record_successful_healing(
            pattern_hash,
            successful_query,
            1
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_pattern_confidence(self, healing_memory):
        """Test getting pattern confidence"""
        pattern_hash = "test_hash_123"
        
        confidence = await healing_memory.get_pattern_confidence(pattern_hash)
        
        assert 0.0 <= confidence <= 1.0

class TestValidationModels:
    """Test validation data models"""
    
    def test_team_analysis_result_valid(self):
        """Test TeamAnalysisResult with valid data"""
        data = {
            "team_name": "Backend Team",
            "total_commits": 150,
            "total_prs": 45,
            "avg_lead_time_hours": 24.5,
            "deployment_frequency": 2.3,
            "change_failure_rate": 0.05,
            "mttr_hours": 2.1
        }
        
        result = TeamAnalysisResult(**data)
        
        assert result.team_name == "Backend Team"
        assert result.total_commits == 150
    
    def test_dora_metrics_result_valid(self):
        """Test DORAMetricsResult with valid data"""
        data = {
            "metric_name": "deployment_frequency",
            "metric_value": 2.5,
            "metric_unit": "per_week",
            "time_period": "2024-01",
            "tenant_id": 1,
            "calculation_date": "2024-01-15"
        }
        
        result = DORAMetricsResult(**data)
        
        assert result.metric_name == "deployment_frequency"
        assert result.metric_value == 2.5
    
    def test_rework_analysis_result_valid(self):
        """Test ReworkAnalysisResult with valid data"""
        data = {
            "pr_id": 123,
            "rework_cycles": 2,
            "initial_size": 100,
            "final_size": 150,
            "rework_percentage": 25.0,
            "time_to_completion_hours": 48.5
        }
        
        result = ReworkAnalysisResult(**data)
        
        assert result.pr_id == 123
        assert result.rework_cycles == 2

# Integration Tests

class TestValidationPipelineIntegration:
    """Integration tests for the complete validation pipeline"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for integration tests"""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_complete_validation_pipeline_success(self, mock_db_session):
        """Test complete validation pipeline with successful validation"""
        # Initial state
        state = StrategicAgentState(
            user_query="How many commits did the backend team make?",
            sql_query="SELECT COUNT(*) FROM commits WHERE team_name = 'backend' AND tenant_id = 1"
        )

        # Step 1: SQL Syntax Validation
        state = await validate_sql_syntax(state)
        assert state.sql_validation_passed is True

        # Step 2: Semantic Validation
        state = await validate_sql_semantics(state)
        assert state.semantic_validation_passed is True
        assert state.semantic_confidence > 0.5

        # Step 3: Simulate query execution and data validation
        mock_data = [{"count": 150}]
        # Data structure validation would happen here

        assert len(state.validation_errors) == 0

    @pytest.mark.asyncio
    async def test_complete_validation_pipeline_with_retry(self, mock_db_session):
        """Test validation pipeline with retry logic"""
        # Initial state with problematic query
        state = StrategicAgentState(
            user_query="How many commits do we have?",
            sql_query="SELECT team_name FROM commits WHERE tenant_id = 1",  # Missing COUNT
            sql_retry_count=0,
            semantic_retry_count=0
        )

        # Step 1: SQL Syntax Validation (should pass)
        state = await validate_sql_syntax(state)
        assert state.sql_validation_passed is True

        # Step 2: Semantic Validation (should fail - missing COUNT)
        state = await validate_sql_semantics(state)
        assert state.semantic_validation_passed is False
        assert any("count" in error.lower() for error in state.validation_errors)

        # Step 3: Self-healing retry
        healing_memory = SelfHealingMemory(mock_db_session)
        suggestions = await healing_memory.get_healing_suggestions(
            ErrorType.SEMANTIC_ERROR,
            state.user_query,
            state.sql_query,
            1
        )

        assert len(suggestions) > 0
        assert any("count" in suggestion.lower() for suggestion in suggestions)

    @pytest.mark.asyncio
    async def test_validation_failure_learning_integration(self, mock_db_session):
        """Test integration between validation failure and learning system"""
        # Create validation feedback
        feedback = ValidationFeedback(
            error_type=ErrorType.SEMANTIC_ERROR,
            user_intent="Count commits",
            failed_query="SELECT team_name FROM commits",
            specific_issue="Missing COUNT function for counting intent",
            suggested_fix="Add COUNT(*) function",
            confidence=0.9,
            learning_context={"analysis_type": "team_performance"},
            tenant_id=1
        )

        # Record failure in learning memory
        healing_memory = SelfHealingMemory(mock_db_session)
        result = await healing_memory.record_validation_failure(feedback)

        assert result is True

        # Get suggestions for similar pattern
        suggestions = await healing_memory.get_healing_suggestions(
            ErrorType.SEMANTIC_ERROR,
            "Count commits",
            "SELECT team_name FROM commits",
            1
        )

        assert len(suggestions) > 0

class TestWorkflowIntegration:
    """Integration tests for workflow with validation nodes"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_workflow_routing_logic(self, mock_db_session):
        """Test workflow routing logic with validation"""
        from app.ai.workflow import EnhancedStrategicWorkflow

        workflow_manager = EnhancedStrategicWorkflow(mock_db_session)

        # Test routing conditions
        state_with_sql = StrategicAgentState(sql_query="SELECT COUNT(*) FROM commits")
        state_without_sql = StrategicAgentState(sql_query=None)

        # Should validate when SQL exists
        assert workflow_manager._should_validate_sql(state_with_sql) == "validate"

        # Should skip when no SQL
        assert workflow_manager._should_validate_sql(state_without_sql) == "skip"

        # Test syntax validation routing
        passed_state = StrategicAgentState(sql_validation_passed=True)
        failed_state = StrategicAgentState(sql_validation_passed=False, sql_retry_count=0)
        max_retry_state = StrategicAgentState(sql_validation_passed=False, sql_retry_count=3)

        assert workflow_manager._check_syntax_validation(passed_state) == "passed"
        assert workflow_manager._check_syntax_validation(failed_state) == "retry"
        assert workflow_manager._check_syntax_validation(max_retry_state) == "failed"
