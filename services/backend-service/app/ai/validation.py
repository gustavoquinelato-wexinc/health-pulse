#!/usr/bin/env python3
"""
AI Phase 2: Validation & Self-Correction Layer
SQL syntax and semantic validation for AI-generated queries
"""

import json
import logging
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
import sqlglot
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class ErrorType(Enum):
    """Types of validation errors"""
    SYNTAX_ERROR = "syntax_error"
    SEMANTIC_ERROR = "semantic_error"
    DATA_STRUCTURE_ERROR = "data_structure_error"
    EXECUTION_ERROR = "execution_error"

class ValidationResult(BaseModel):
    """Result of validation operation"""
    passed: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    suggestions: List[str] = Field(default_factory=list)

class ValidationFeedback(BaseModel):
    """Feedback for learning memory system"""
    error_type: ErrorType
    user_intent: str
    failed_query: str
    specific_issue: str
    suggested_fix: str
    confidence: float
    learning_context: Dict[str, Any]
    client_id: int

class StrategicAgentState(BaseModel):
    """State object for AI agent workflow"""
    user_query: Optional[str] = None
    sql_query: Optional[str] = None
    analysis_intent: Optional[str] = None
    sql_validation_passed: bool = False
    semantic_validation_passed: bool = False
    validation_errors: List[str] = Field(default_factory=list)
    semantic_validation_justification: Optional[str] = None
    semantic_confidence: float = 0.0
    sql_retry_count: int = 0
    semantic_retry_count: int = 0

async def validate_sql_syntax(state: StrategicAgentState) -> StrategicAgentState:
    """
    Validate SQL syntax using sqlglot before database execution
    
    Args:
        state: Current agent state containing SQL query
        
    Returns:
        Updated state with validation results
    """
    sql_query = state.sql_query
    if not sql_query:
        state.validation_errors = ["No SQL query to validate"]
        state.sql_validation_passed = False
        return state
    
    try:
        # Parse SQL for PostgreSQL syntax
        parsed = sqlglot.parse_one(sql_query, read="postgres")
        
        if parsed is None:
            state.sql_validation_passed = False
            state.validation_errors = ["Failed to parse SQL query"]
            logger.warning(f"SQL parsing failed for query: {sql_query[:100]}...")
            return state
        
        # Additional syntax checks
        validation_errors = []
        
        # Check for common SQL injection patterns
        dangerous_patterns = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE']
        upper_query = sql_query.upper()
        for pattern in dangerous_patterns:
            if pattern in upper_query and 'SELECT' in upper_query:
                validation_errors.append(f"Potentially dangerous SQL operation detected: {pattern}")
        
        # Check for missing WHERE clauses in data modification queries
        if any(op in upper_query for op in ['UPDATE', 'DELETE']) and 'WHERE' not in upper_query:
            validation_errors.append("Data modification query missing WHERE clause")
        
        if validation_errors:
            state.sql_validation_passed = False
            state.validation_errors = validation_errors
        else:
            state.sql_validation_passed = True
            state.validation_errors = []
        
        logger.info(f"SQL syntax validation {'passed' if state.sql_validation_passed else 'failed'}")
        
    except Exception as e:
        state.sql_validation_passed = False
        state.validation_errors = [f"SQL syntax error: {str(e)}"]
        logger.error(f"SQL syntax validation error: {e}")
    
    return state

async def validate_sql_semantics(state: StrategicAgentState) -> StrategicAgentState:
    """
    AI validates its own SQL logic using fast, cost-effective model
    
    Args:
        state: Current agent state with user query and generated SQL
        
    Returns:
        Updated state with semantic validation results
    """
    try:
        # For now, implement basic semantic checks
        # In full implementation, this would use GPT-4o-mini for validation
        
        user_query = state.user_query or ""
        sql_query = state.sql_query or ""
        analysis_intent = state.analysis_intent or ""
        
        semantic_errors = []
        confidence = 1.0
        
        # Basic semantic validation checks
        if not sql_query:
            semantic_errors.append("No SQL query to validate semantically")
            confidence = 0.0
        
        # Check if query type matches user intent
        if "count" in user_query.lower() and "COUNT" not in sql_query.upper():
            semantic_errors.append("User asked for count but SQL doesn't include COUNT")
            confidence -= 0.3
        
        if "average" in user_query.lower() and "AVG" not in sql_query.upper():
            semantic_errors.append("User asked for average but SQL doesn't include AVG")
            confidence -= 0.3
        
        # Check for client isolation in multi-tenant queries
        if "client" not in sql_query.lower() and len(sql_query) > 50:
            semantic_errors.append("Query may be missing client isolation filter")
            confidence -= 0.2
        
        # Determine validation result
        if semantic_errors:
            state.semantic_validation_passed = False
            state.validation_errors.extend(semantic_errors)
            state.semantic_confidence = max(0.0, confidence)
            state.semantic_validation_justification = "; ".join(semantic_errors)
        else:
            state.semantic_validation_passed = True
            state.semantic_confidence = confidence
            state.semantic_validation_justification = "SQL query appears to match user intent"
        
        logger.info(f"Semantic validation {'passed' if state.semantic_validation_passed else 'failed'} "
                   f"with confidence {state.semantic_confidence:.2f}")
        
    except Exception as e:
        state.semantic_validation_passed = False
        state.validation_errors.append(f"Semantic validation error: {str(e)}")
        state.semantic_confidence = 0.0
        state.semantic_validation_justification = f"Validation failed: {str(e)}"
        logger.error(f"Semantic validation error: {e}")
    
    return state

def validate_sql_syntax_service(sql_query: str) -> ValidationResult:
    """
    Service function for SQL syntax validation
    
    Args:
        sql_query: SQL query to validate
        
    Returns:
        ValidationResult with validation outcome
    """
    try:
        # Parse SQL for PostgreSQL syntax
        parsed = sqlglot.parse_one(sql_query, read="postgres")
        
        if parsed is None:
            return ValidationResult(
                passed=False,
                errors=["Failed to parse SQL query"],
                suggestions=["Check SQL syntax for PostgreSQL compatibility"]
            )
        
        # Additional validation checks
        errors = []
        warnings = []
        suggestions = []
        
        # Check for dangerous operations
        dangerous_patterns = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE']
        upper_query = sql_query.upper()
        for pattern in dangerous_patterns:
            if pattern in upper_query and 'SELECT' in upper_query:
                errors.append(f"Potentially dangerous SQL operation: {pattern}")
                suggestions.append(f"Remove {pattern} operation from SELECT query")
        
        # Check for missing WHERE clauses
        if any(op in upper_query for op in ['UPDATE', 'DELETE']) and 'WHERE' not in upper_query:
            errors.append("Data modification query missing WHERE clause")
            suggestions.append("Add WHERE clause to limit affected rows")
        
        # Performance warnings
        if 'SELECT *' in sql_query:
            warnings.append("Using SELECT * may impact performance")
            suggestions.append("Specify only needed columns instead of SELECT *")
        
        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            confidence=1.0 if len(errors) == 0 else 0.0
        )
        
    except Exception as e:
        return ValidationResult(
            passed=False,
            errors=[f"SQL syntax error: {str(e)}"],
            suggestions=["Check SQL syntax and try again"],
            confidence=0.0
        )

async def validate_sql_semantics_service(
    sql_query: str, 
    user_intent: str, 
    analysis_context: Optional[Dict[str, Any]] = None
) -> ValidationResult:
    """
    Service function for SQL semantic validation
    
    Args:
        sql_query: SQL query to validate
        user_intent: Original user query/intent
        analysis_context: Additional context for validation
        
    Returns:
        ValidationResult with semantic validation outcome
    """
    try:
        errors = []
        warnings = []
        suggestions = []
        confidence = 1.0
        
        # Basic semantic checks
        if not sql_query:
            return ValidationResult(
                passed=False,
                errors=["No SQL query provided"],
                confidence=0.0
            )
        
        # Intent matching checks
        if "count" in user_intent.lower() and "COUNT" not in sql_query.upper():
            errors.append("User requested count but SQL doesn't include COUNT function")
            suggestions.append("Add COUNT() function to match user intent")
            confidence -= 0.4
        
        if "average" in user_intent.lower() and "AVG" not in sql_query.upper():
            errors.append("User requested average but SQL doesn't include AVG function")
            suggestions.append("Add AVG() function to match user intent")
            confidence -= 0.4
        
        # Multi-tenancy checks
        if "client" not in sql_query.lower() and len(sql_query) > 50:
            warnings.append("Query may be missing client isolation")
            suggestions.append("Consider adding client_id filter for data isolation")
            confidence -= 0.2
        
        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            confidence=max(0.0, confidence)
        )
        
    except Exception as e:
        return ValidationResult(
            passed=False,
            errors=[f"Semantic validation error: {str(e)}"],
            confidence=0.0
        )

# Data Structure Validation Schemas

class TeamAnalysisResult(BaseModel):
    """Expected structure for team analysis queries"""
    team_name: str
    total_commits: int
    total_prs: int
    avg_lead_time_hours: float
    deployment_frequency: float
    change_failure_rate: float
    mttr_hours: float

class DORAMetricsResult(BaseModel):
    """Expected structure for DORA metrics queries"""
    metric_name: str
    metric_value: float
    metric_unit: str
    time_period: str
    client_id: int
    calculation_date: str

class ReworkAnalysisResult(BaseModel):
    """Expected structure for rework analysis queries"""
    pr_id: int
    rework_cycles: int
    initial_size: int
    final_size: int
    rework_percentage: float
    time_to_completion_hours: float

class QueryResultValidator:
    """Validates query results against expected data structures"""

    @staticmethod
    def validate_team_analysis(data: List[Dict[str, Any]]) -> ValidationResult:
        """Validate team analysis query results"""
        try:
            errors = []
            warnings = []

            if not data:
                return ValidationResult(
                    passed=False,
                    errors=["No data returned from team analysis query"],
                    confidence=0.0
                )

            for i, row in enumerate(data):
                try:
                    TeamAnalysisResult(**row)
                except Exception as e:
                    errors.append(f"Row {i+1} validation failed: {str(e)}")

            # Check for reasonable data ranges
            for row in data:
                if row.get('avg_lead_time_hours', 0) < 0:
                    warnings.append("Negative lead time detected")
                if row.get('change_failure_rate', 0) > 1.0:
                    warnings.append("Change failure rate > 100% detected")

            return ValidationResult(
                passed=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                confidence=1.0 if len(errors) == 0 else 0.5
            )

        except Exception as e:
            return ValidationResult(
                passed=False,
                errors=[f"Team analysis validation error: {str(e)}"],
                confidence=0.0
            )

    @staticmethod
    def validate_dora_metrics(data: List[Dict[str, Any]]) -> ValidationResult:
        """Validate DORA metrics query results"""
        try:
            errors = []
            warnings = []

            if not data:
                return ValidationResult(
                    passed=False,
                    errors=["No data returned from DORA metrics query"],
                    confidence=0.0
                )

            for i, row in enumerate(data):
                try:
                    DORAMetricsResult(**row)
                except Exception as e:
                    errors.append(f"Row {i+1} validation failed: {str(e)}")

            # Check for valid metric ranges
            for row in data:
                metric_value = row.get('metric_value', 0)
                metric_name = row.get('metric_name', '')

                if 'frequency' in metric_name.lower() and metric_value < 0:
                    warnings.append(f"Negative frequency value for {metric_name}")
                if 'rate' in metric_name.lower() and metric_value > 1.0:
                    warnings.append(f"Rate > 100% for {metric_name}")

            return ValidationResult(
                passed=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                confidence=1.0 if len(errors) == 0 else 0.5
            )

        except Exception as e:
            return ValidationResult(
                passed=False,
                errors=[f"DORA metrics validation error: {str(e)}"],
                confidence=0.0
            )

    @staticmethod
    def validate_rework_analysis(data: List[Dict[str, Any]]) -> ValidationResult:
        """Validate rework analysis query results"""
        try:
            errors = []
            warnings = []

            if not data:
                return ValidationResult(
                    passed=False,
                    errors=["No data returned from rework analysis query"],
                    confidence=0.0
                )

            for i, row in enumerate(data):
                try:
                    ReworkAnalysisResult(**row)
                except Exception as e:
                    errors.append(f"Row {i+1} validation failed: {str(e)}")

            # Check for logical consistency
            for row in data:
                rework_cycles = row.get('rework_cycles', 0)
                rework_percentage = row.get('rework_percentage', 0)

                if rework_cycles < 0:
                    errors.append("Negative rework cycles detected")
                if rework_percentage < 0 or rework_percentage > 100:
                    warnings.append("Rework percentage outside 0-100% range")

            return ValidationResult(
                passed=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                confidence=1.0 if len(errors) == 0 else 0.5
            )

        except Exception as e:
            return ValidationResult(
                passed=False,
                errors=[f"Rework analysis validation error: {str(e)}"],
                confidence=0.0
            )

# Self-Healing Memory System

import hashlib
from datetime import datetime, timedelta
from typing import Optional

class SelfHealingMemory:
    """
    Self-healing memory system that learns from validation failures
    and provides pattern-based suggestions for query improvement
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.logger = logging.getLogger(__name__)

    def generate_pattern_hash(self, error_pattern: str, user_intent: str) -> str:
        """Generate a hash for error pattern recognition"""
        pattern_key = f"{error_pattern}:{user_intent.lower()}"
        return hashlib.sha256(pattern_key.encode()).hexdigest()[:64]

    async def record_validation_failure(self, feedback: ValidationFeedback) -> bool:
        """
        Record a validation failure for learning and pattern recognition

        Args:
            feedback: ValidationFeedback object with failure details

        Returns:
            bool: Success status of recording
        """
        try:
            pattern_hash = self.generate_pattern_hash(
                feedback.specific_issue,
                feedback.user_intent
            )

            # Record in ai_learning_memory
            learning_record = {
                'error_type': feedback.error_type.value,
                'user_intent': feedback.user_intent,
                'failed_query': feedback.failed_query,
                'specific_issue': feedback.specific_issue,
                'corrected_query': feedback.suggested_fix,
                'client_id': feedback.client_id,
                'validation_type': feedback.error_type.value,
                'confidence_score': feedback.confidence,
                'learning_context': feedback.learning_context,
                'pattern_hash': pattern_hash,
                'validation_passed': False,
                'created_at': datetime.now()
            }

            # Insert learning record (would use SQLAlchemy ORM in full implementation)
            self.logger.info(f"Recording validation failure: {feedback.error_type.value}")

            # Update or create pattern record
            await self._update_pattern_record(pattern_hash, feedback)

            return True

        except Exception as e:
            self.logger.error(f"Failed to record validation failure: {e}")
            return False

    async def _update_pattern_record(self, pattern_hash: str, feedback: ValidationFeedback):
        """Update or create pattern record for failure tracking"""
        try:
            # In full implementation, this would query ai_validation_patterns table
            # and update failure_count or create new record

            pattern_record = {
                'pattern_hash': pattern_hash,
                'error_pattern': feedback.specific_issue,
                'failure_count': 1,  # Would increment if exists
                'last_seen_at': datetime.now(),
                'pattern_metadata': {
                    'error_type': feedback.error_type.value,
                    'common_intent_keywords': self._extract_keywords(feedback.user_intent),
                    'query_complexity': len(feedback.failed_query.split()),
                    'client_context': feedback.client_id
                },
                'suggested_fix': feedback.suggested_fix,
                'confidence_score': feedback.confidence,
                'client_id': feedback.client_id
            }

            self.logger.info(f"Updated pattern record for hash: {pattern_hash[:16]}...")

        except Exception as e:
            self.logger.error(f"Failed to update pattern record: {e}")

    def _extract_keywords(self, user_intent: str) -> List[str]:
        """Extract key intent keywords for pattern matching"""
        keywords = []
        intent_lower = user_intent.lower()

        # Common analytics keywords
        analytics_keywords = [
            'count', 'average', 'sum', 'total', 'rate', 'percentage',
            'team', 'developer', 'commit', 'pull request', 'deployment',
            'lead time', 'cycle time', 'frequency', 'failure', 'recovery'
        ]

        for keyword in analytics_keywords:
            if keyword in intent_lower:
                keywords.append(keyword)

        return keywords[:5]  # Limit to top 5 keywords

    async def get_healing_suggestions(
        self,
        error_type: ErrorType,
        user_intent: str,
        failed_query: str,
        client_id: int
    ) -> List[str]:
        """
        Get healing suggestions based on historical patterns

        Args:
            error_type: Type of validation error
            user_intent: User's original intent
            failed_query: The query that failed validation
            client_id: Client context

        Returns:
            List of suggested fixes based on learned patterns
        """
        try:
            suggestions = []

            # Generate pattern hash for lookup
            pattern_hash = self.generate_pattern_hash(
                error_type.value,
                user_intent
            )

            # In full implementation, this would query ai_validation_patterns
            # for similar patterns and their successful fixes

            # Basic rule-based suggestions for now
            if error_type == ErrorType.SYNTAX_ERROR:
                suggestions.extend([
                    "Check SQL syntax for PostgreSQL compatibility",
                    "Verify table and column names exist",
                    "Ensure proper JOIN syntax and conditions"
                ])

            elif error_type == ErrorType.SEMANTIC_ERROR:
                if "count" in user_intent.lower():
                    suggestions.append("Add COUNT() function to match counting intent")
                if "average" in user_intent.lower():
                    suggestions.append("Add AVG() function to calculate averages")
                if "team" in user_intent.lower():
                    suggestions.append("Include team-related tables and filters")

            elif error_type == ErrorType.DATA_STRUCTURE_ERROR:
                suggestions.extend([
                    "Verify query returns expected column names",
                    "Check data types match expected schema",
                    "Ensure all required fields are included"
                ])

            # Add client-specific suggestions
            suggestions.append("Consider adding client_id filter for data isolation")

            self.logger.info(f"Generated {len(suggestions)} healing suggestions")
            return suggestions[:3]  # Return top 3 suggestions

        except Exception as e:
            self.logger.error(f"Failed to get healing suggestions: {e}")
            return ["Review query syntax and try again"]

    async def record_successful_healing(
        self,
        pattern_hash: str,
        successful_query: str,
        client_id: int
    ) -> bool:
        """
        Record a successful healing to improve future suggestions

        Args:
            pattern_hash: Hash of the error pattern that was fixed
            successful_query: The query that worked after healing
            client_id: Client context

        Returns:
            bool: Success status of recording
        """
        try:
            # In full implementation, this would:
            # 1. Update ai_validation_patterns.success_count
            # 2. Update confidence_score based on success rate
            # 3. Store successful_query as suggested_fix

            healing_record = {
                'pattern_hash': pattern_hash,
                'successful_query': successful_query,
                'healed_at': datetime.now(),
                'client_id': client_id
            }

            self.logger.info(f"Recorded successful healing for pattern: {pattern_hash[:16]}...")
            return True

        except Exception as e:
            self.logger.error(f"Failed to record successful healing: {e}")
            return False

    async def get_pattern_confidence(self, pattern_hash: str) -> float:
        """
        Get confidence score for a specific error pattern

        Args:
            pattern_hash: Hash of the error pattern

        Returns:
            float: Confidence score (0.0 to 1.0)
        """
        try:
            # In full implementation, this would query ai_validation_patterns
            # and calculate: success_count / (success_count + failure_count)

            # For now, return a default confidence
            return 0.7

        except Exception as e:
            self.logger.error(f"Failed to get pattern confidence: {e}")
            return 0.0
