#!/usr/bin/env python3
"""
AI Phase 2: Enhanced LangGraph Workflow with Validation Layer
Integrates validation nodes into the strategic agent workflow
"""

import logging
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.graph import CompiledGraph

from app.ai.validation import (
    StrategicAgentState,
    validate_sql_syntax,
    validate_sql_semantics,
    SelfHealingMemory,
    ValidationFeedback,
    ErrorType
)

logger = logging.getLogger(__name__)

class EnhancedStrategicWorkflow:
    """
    Enhanced strategic agent workflow with AI Phase 2 validation layer
    """
    
    def __init__(self, db_session):
        self.db_session = db_session
        self.healing_memory = SelfHealingMemory(db_session)
        self.max_retry_attempts = 3
    
    def create_workflow(self) -> CompiledGraph:
        """
        Create LangGraph workflow with validation nodes and retry logic
        
        Returns:
            CompiledGraph: Compiled workflow with validation integration
        """
        workflow = StateGraph(StrategicAgentState)
        
        # Phase 1 foundation nodes (placeholders for existing implementation)
        workflow.add_node("pre_analysis", self._intelligent_pre_analysis)
        workflow.add_node("semantic_search", self._targeted_semantic_search)
        workflow.add_node("structured_query", self._intelligent_structured_query)
        
        # Phase 2 validation nodes
        workflow.add_node("validate_sql_syntax", validate_sql_syntax)
        workflow.add_node("validate_sql_semantics", validate_sql_semantics)
        workflow.add_node("validate_data_structure", self._validate_data_structure)
        workflow.add_node("self_healing_retry", self._self_healing_retry)
        
        # Analysis and response nodes
        workflow.add_node("execute_query", self._execute_query)
        workflow.add_node("ai_analysis", self._comprehensive_ai_analysis)
        workflow.add_node("generate_response", self._generate_final_response)
        
        # Error handling nodes
        workflow.add_node("handle_validation_failure", self._handle_validation_failure)
        
        # Set entry point
        workflow.set_entry_point("pre_analysis")
        
        # Basic workflow flow
        workflow.add_edge("pre_analysis", "semantic_search")
        workflow.add_edge("semantic_search", "structured_query")
        
        # Validation routing after SQL generation
        workflow.add_conditional_edges(
            "structured_query",
            self._should_validate_sql,
            {
                "validate": "validate_sql_syntax",
                "skip": "execute_query"
            }
        )
        
        # SQL syntax validation routing
        workflow.add_conditional_edges(
            "validate_sql_syntax",
            self._check_syntax_validation,
            {
                "passed": "validate_sql_semantics",
                "failed": "handle_validation_failure",
                "retry": "self_healing_retry"
            }
        )
        
        # Semantic validation routing
        workflow.add_conditional_edges(
            "validate_sql_semantics",
            self._check_semantic_validation,
            {
                "passed": "execute_query",
                "failed": "handle_validation_failure",
                "retry": "self_healing_retry"
            }
        )
        
        # Self-healing retry routing
        workflow.add_conditional_edges(
            "self_healing_retry",
            self._check_retry_result,
            {
                "retry_syntax": "validate_sql_syntax",
                "retry_semantic": "validate_sql_semantics",
                "give_up": "handle_validation_failure"
            }
        )
        
        # Query execution and data validation
        workflow.add_edge("execute_query", "validate_data_structure")
        
        # Data structure validation routing
        workflow.add_conditional_edges(
            "validate_data_structure",
            self._check_data_validation,
            {
                "passed": "ai_analysis",
                "failed": "handle_validation_failure"
            }
        )
        
        # Final flow
        workflow.add_edge("ai_analysis", "generate_response")
        workflow.add_edge("generate_response", END)
        workflow.add_edge("handle_validation_failure", END)
        
        return workflow.compile()
    
    # Routing condition functions
    
    def _should_validate_sql(self, state: StrategicAgentState) -> str:
        """Determine if SQL validation is needed"""
        if state.sql_query and len(state.sql_query.strip()) > 0:
            return "validate"
        return "skip"
    
    def _check_syntax_validation(self, state: StrategicAgentState) -> str:
        """Check SQL syntax validation result"""
        if state.sql_validation_passed:
            return "passed"
        elif state.sql_retry_count < self.max_retry_attempts:
            return "retry"
        else:
            return "failed"
    
    def _check_semantic_validation(self, state: StrategicAgentState) -> str:
        """Check semantic validation result"""
        if state.semantic_validation_passed:
            return "passed"
        elif state.semantic_retry_count < self.max_retry_attempts:
            return "retry"
        else:
            return "failed"
    
    def _check_retry_result(self, state: StrategicAgentState) -> str:
        """Determine retry routing based on error type"""
        if state.sql_retry_count >= self.max_retry_attempts and state.semantic_retry_count >= self.max_retry_attempts:
            return "give_up"
        elif not state.sql_validation_passed:
            return "retry_syntax"
        elif not state.semantic_validation_passed:
            return "retry_semantic"
        else:
            return "give_up"
    
    def _check_data_validation(self, state: StrategicAgentState) -> str:
        """Check data structure validation result"""
        # This would check if data validation passed
        # For now, assume it passes
        return "passed"
    
    # Node implementation functions (placeholders for existing implementation)
    
    async def _intelligent_pre_analysis(self, state: StrategicAgentState) -> StrategicAgentState:
        """Placeholder for existing pre-analysis implementation"""
        logger.info("Performing intelligent pre-analysis")
        state.analysis_intent = "team_performance_analysis"  # Example
        return state
    
    async def _targeted_semantic_search(self, state: StrategicAgentState) -> StrategicAgentState:
        """Placeholder for existing semantic search implementation"""
        logger.info("Performing targeted semantic search")
        return state
    
    async def _intelligent_structured_query(self, state: StrategicAgentState) -> StrategicAgentState:
        """Placeholder for existing structured query implementation"""
        logger.info("Generating intelligent structured query")
        # This would generate the SQL query that needs validation
        state.sql_query = "SELECT team_name, COUNT(*) as total_commits FROM commits GROUP BY team_name"
        return state
    
    async def _validate_data_structure(self, state: StrategicAgentState) -> StrategicAgentState:
        """Validate query result data structure"""
        logger.info("Validating data structure")
        # This would validate the actual query results
        # For now, assume validation passes
        return state
    
    async def _self_healing_retry(self, state: StrategicAgentState) -> StrategicAgentState:
        """Self-healing retry with learning context"""
        logger.info("Attempting self-healing retry")
        
        try:
            # Determine error type
            if not state.sql_validation_passed:
                error_type = ErrorType.SYNTAX_ERROR
                state.sql_retry_count += 1
            elif not state.semantic_validation_passed:
                error_type = ErrorType.SEMANTIC_ERROR
                state.semantic_retry_count += 1
            else:
                return state
            
            # Get healing suggestions
            suggestions = await self.healing_memory.get_healing_suggestions(
                error_type,
                state.user_query or "",
                state.sql_query or "",
                1  # Default client_id
            )
            
            # Apply healing suggestions (simplified implementation)
            if suggestions:
                logger.info(f"Applying healing suggestion: {suggestions[0]}")
                # In full implementation, this would regenerate SQL based on suggestions
                # For now, just log the attempt
            
            return state
            
        except Exception as e:
            logger.error(f"Self-healing retry failed: {e}")
            return state
    
    async def _execute_query(self, state: StrategicAgentState) -> StrategicAgentState:
        """Execute validated SQL query"""
        logger.info("Executing validated SQL query")
        # This would execute the validated SQL query
        return state
    
    async def _comprehensive_ai_analysis(self, state: StrategicAgentState) -> StrategicAgentState:
        """Placeholder for existing AI analysis implementation"""
        logger.info("Performing comprehensive AI analysis")
        return state
    
    async def _generate_final_response(self, state: StrategicAgentState) -> StrategicAgentState:
        """Placeholder for existing response generation implementation"""
        logger.info("Generating final response")
        return state
    
    async def _handle_validation_failure(self, state: StrategicAgentState) -> StrategicAgentState:
        """Handle validation failures with user feedback"""
        logger.warning("Handling validation failure")
        
        try:
            # Record validation failure for learning
            if state.validation_errors:
                feedback = ValidationFeedback(
                    error_type=ErrorType.SYNTAX_ERROR if not state.sql_validation_passed else ErrorType.SEMANTIC_ERROR,
                    user_intent=state.user_query or "",
                    failed_query=state.sql_query or "",
                    specific_issue="; ".join(state.validation_errors),
                    suggested_fix="Review query syntax and intent matching",
                    confidence=0.5,
                    learning_context={
                        "retry_count": state.sql_retry_count + state.semantic_retry_count,
                        "analysis_intent": state.analysis_intent
                    },
                    client_id=1  # Default client_id
                )
                
                await self.healing_memory.record_validation_failure(feedback)
            
            # Set error response
            state.validation_errors.append("Query validation failed after maximum retry attempts")
            
        except Exception as e:
            logger.error(f"Error handling validation failure: {e}")
        
        return state
