#!/usr/bin/env python3
"""
AI Phase 2: Validation API Endpoints
REST API endpoints for SQL validation, semantic validation, and learning memory
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ai.validation import (
    validate_sql_syntax_service,
    validate_sql_semantics_service,
    ValidationResult,
    ValidationFeedback,
    ErrorType,
    SelfHealingMemory,
    QueryResultValidator
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Request/Response Models

class SQLValidationRequest(BaseModel):
    """Request model for SQL syntax validation"""
    sql_query: str = Field(..., description="SQL query to validate")
    tenant_id: Optional[int] = Field(None, description="Tenant context for validation")

class SemanticValidationRequest(BaseModel):
    """Request model for semantic validation"""
    sql_query: str = Field(..., description="SQL query to validate")
    user_intent: str = Field(..., description="Original user query/intent")
    analysis_context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    tenant_id: Optional[int] = Field(None, description="Tenant context for validation")

class ValidationFeedbackRequest(BaseModel):
    """Request model for recording validation feedback"""
    error_type: str = Field(..., description="Type of validation error")
    user_intent: str = Field(..., description="Original user intent")
    failed_query: str = Field(..., description="Query that failed validation")
    specific_issue: str = Field(..., description="Specific validation issue")
    suggested_fix: str = Field(..., description="Suggested fix for the issue")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the feedback")
    learning_context: Dict[str, Any] = Field(..., description="Context for learning")
    tenant_id: int = Field(..., description="Tenant ID for the feedback")

class HealingSuggestionsRequest(BaseModel):
    """Request model for getting healing suggestions"""
    error_type: str = Field(..., description="Type of validation error")
    user_intent: str = Field(..., description="Original user intent")
    failed_query: str = Field(..., description="Query that failed validation")
    tenant_id: int = Field(..., description="Tenant context")

class DataValidationRequest(BaseModel):
    """Request model for data structure validation"""
    data: List[Dict[str, Any]] = Field(..., description="Query result data to validate")
    validation_type: str = Field(..., description="Type of validation (team_analysis, dora_metrics, rework_analysis)")

# API Endpoints

@router.post("/validate/sql-syntax", response_model=ValidationResult)
async def validate_sql_syntax(
    request: SQLValidationRequest,
    db: Session = Depends(get_db)
):
    """
    Validate SQL syntax using sqlglot parser
    
    Args:
        request: SQL validation request
        db: Database session
        
    Returns:
        ValidationResult with syntax validation outcome
    """
    try:
        logger.info(f"Validating SQL syntax for client {request.tenant_id}")
        
        result = validate_sql_syntax_service(request.sql_query)
        
        logger.info(f"SQL syntax validation {'passed' if result.passed else 'failed'}")
        return result
        
    except Exception as e:
        logger.error(f"SQL syntax validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SQL syntax validation failed: {str(e)}"
        )

@router.post("/validate/sql-semantics", response_model=ValidationResult)
async def validate_sql_semantics(
    request: SemanticValidationRequest,
    db: Session = Depends(get_db)
):
    """
    Validate SQL semantics and intent matching
    
    Args:
        request: Semantic validation request
        db: Database session
        
    Returns:
        ValidationResult with semantic validation outcome
    """
    try:
        logger.info(f"Validating SQL semantics for client {request.tenant_id}")
        
        result = await validate_sql_semantics_service(
            request.sql_query,
            request.user_intent,
            request.analysis_context
        )
        
        logger.info(f"SQL semantic validation {'passed' if result.passed else 'failed'} "
                   f"with confidence {result.confidence:.2f}")
        return result
        
    except Exception as e:
        logger.error(f"SQL semantic validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SQL semantic validation failed: {str(e)}"
        )

@router.post("/validate/data-structure", response_model=ValidationResult)
async def validate_data_structure(
    request: DataValidationRequest,
    db: Session = Depends(get_db)
):
    """
    Validate query result data structure
    
    Args:
        request: Data validation request
        db: Database session
        
    Returns:
        ValidationResult with data structure validation outcome
    """
    try:
        logger.info(f"Validating data structure for type: {request.validation_type}")
        
        validator = QueryResultValidator()
        
        if request.validation_type == "team_analysis":
            result = validator.validate_team_analysis(request.data)
        elif request.validation_type == "dora_metrics":
            result = validator.validate_dora_metrics(request.data)
        elif request.validation_type == "rework_analysis":
            result = validator.validate_rework_analysis(request.data)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown validation type: {request.validation_type}"
            )
        
        logger.info(f"Data structure validation {'passed' if result.passed else 'failed'}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Data structure validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data structure validation failed: {str(e)}"
        )

@router.post("/learning/record-feedback")
async def record_validation_feedback(
    request: ValidationFeedbackRequest,
    db: Session = Depends(get_db)
):
    """
    Record validation feedback for learning memory system
    
    Args:
        request: Validation feedback request
        db: Database session
        
    Returns:
        Success response
    """
    try:
        logger.info(f"Recording validation feedback for client {request.tenant_id}")
        
        # Convert string error_type to enum
        try:
            error_type = ErrorType(request.error_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid error type: {request.error_type}"
            )
        
        feedback = ValidationFeedback(
            error_type=error_type,
            user_intent=request.user_intent,
            failed_query=request.failed_query,
            specific_issue=request.specific_issue,
            suggested_fix=request.suggested_fix,
            confidence=request.confidence,
            learning_context=request.learning_context,
            tenant_id=request.tenant_id
        )
        
        healing_memory = SelfHealingMemory(db)
        success = await healing_memory.record_validation_failure(feedback)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record validation feedback"
            )
        
        logger.info("Validation feedback recorded successfully")
        return {"success": True, "message": "Validation feedback recorded"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Record validation feedback error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record validation feedback: {str(e)}"
        )

@router.post("/learning/healing-suggestions")
async def get_healing_suggestions(
    request: HealingSuggestionsRequest,
    db: Session = Depends(get_db)
):
    """
    Get healing suggestions based on learned patterns
    
    Args:
        request: Healing suggestions request
        db: Database session
        
    Returns:
        List of healing suggestions
    """
    try:
        logger.info(f"Getting healing suggestions for client {request.tenant_id}")
        
        # Convert string error_type to enum
        try:
            error_type = ErrorType(request.error_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid error type: {request.error_type}"
            )
        
        healing_memory = SelfHealingMemory(db)
        suggestions = await healing_memory.get_healing_suggestions(
            error_type,
            request.user_intent,
            request.failed_query,
            request.tenant_id
        )
        
        logger.info(f"Generated {len(suggestions)} healing suggestions")
        return {
            "suggestions": suggestions,
            "error_type": request.error_type,
            "confidence": await healing_memory.get_pattern_confidence(
                healing_memory.generate_pattern_hash(request.error_type, request.user_intent)
            )
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get healing suggestions error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get healing suggestions: {str(e)}"
        )

@router.get("/health")
async def validation_health_check():
    """Health check endpoint for validation service"""
    return {
        "status": "healthy",
        "service": "ai_validation",
        "version": "2.0.0",
        "features": [
            "sql_syntax_validation",
            "semantic_validation", 
            "data_structure_validation",
            "self_healing_memory"
        ]
    }
