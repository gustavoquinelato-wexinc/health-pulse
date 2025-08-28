# Phase 2: Validation & Self-Correction Layer

**Implemented**: NO ❌
**Component**: Cognitive Core → Self-healing, self-validating AI agent (Part 1 of 3)
**Duration**: Weeks 3-4
**Priority**: HIGH
**Risk Level**: MEDIUM

## 🎯 Objectives

1. **SQL Syntax Validation**: Catch AI-generated SQL errors before database execution
2. **Semantic Self-Correction**: Ensure SQL queries logically answer user questions
3. **Data Structure Validation**: Prevent malformed data from reaching analysis steps
4. **Self-Healing Memory**: Learn from validation failures AND user feedback to improve future queries
5. **User Feedback Integration**: Create the critical feedback loop that transforms users into AI trainers
6. **Validation Endpoints**: Backend endpoints for validation pipeline with feedback processing

## 📋 Task Breakdown

### Task 2.1: SQL Syntax Validation
**Duration**: 2-3 days  
**Priority**: CRITICAL  

#### Implementation Components
- **Dependency**: `sqlglot>=20.0.0` for SQL parsing
- **Validation Node**: Parse SQL for PostgreSQL syntax
- **Retry Logic**: Maximum 3 attempts with error feedback
- **Error Logging**: Detailed syntax error tracking

#### Key Features
```python
async def validate_sql_syntax(state: StrategicAgentState) -> StrategicAgentState:
    """Validate SQL syntax using sqlglot before database execution"""
    import sqlglot
    
    sql_query = state.get("sql_query", "")
    if not sql_query:
        state["validation_errors"] = ["No SQL query to validate"]
        return state
    
    try:
        # Parse SQL for PostgreSQL syntax
        parsed = sqlglot.parse_one(sql_query, read="postgres")
        state["sql_validation_passed"] = True
        state["validation_errors"] = []
        
    except Exception as e:
        state["sql_validation_passed"] = False
        state["validation_errors"] = [f"SQL syntax error: {str(e)}"]
    
    return state
```

### Task 2.2: Semantic Self-Correction
**Duration**: 3-4 days  
**Priority**: HIGH  

#### Implementation Components
- **AI Validation**: Use fast model (GPT-4o-mini) to validate SQL logic
- **Intent Matching**: Ensure SQL answers the user's actual question
- **Confidence Scoring**: Measure validation confidence (0.0-1.0)
- **Feedback Loop**: Provide specific improvement suggestions

#### Key Features
```python
async def validate_sql_semantics(state: StrategicAgentState) -> StrategicAgentState:
    """AI validates its own SQL logic using fast, cost-effective model"""
    
    validation_prompt = f"""
    SEMANTIC SQL VALIDATION TASK
    
    User's Original Question: "{state.get('user_query', '')}"
    Analysis Intent: "{state.get('analysis_intent', '')}"
    Generated SQL Query: "{state.get('sql_query', '')}"
    
    Does this SQL query accurately and completely address the user's goal?
    
    Common issues to check:
    - Does the query answer what was actually asked?
    - Are the correct tables and joins used?
    - Are filters appropriate for the question?
    - Does the aggregation match the user's intent?
    - Are there missing WHERE clauses for client isolation?
    
    Respond in JSON format:
    {{"valid": "yes/no", "justification": "brief explanation", "confidence": 0.0-1.0}}
    """
    
    # Use fast model for validation
    validation_result = await wex_ai_client.quick_validation(
        prompt=validation_prompt,
        model="azure-gpt-4o-mini",
        max_tokens=200
    )
    
    result = json.loads(validation_result)
    state["semantic_validation_passed"] = result.get("valid", "no").lower() == "yes"
    state["semantic_validation_justification"] = result.get("justification", "")
    state["semantic_confidence"] = result.get("confidence", 0.0)
    
    return state
```

### Task 2.3: Data Structure Validation
**Duration**: 2-3 days  
**Priority**: MEDIUM  

#### Implementation Components
- **Pydantic Schemas**: Define validation models for different query types
- **Schema Selection**: Automatic schema selection based on query intent
- **Record Validation**: Validate each result record against expected structure
- **Error Reporting**: Detailed validation error messages

#### Key Validation Schemas
```python
class TeamAnalysisRecord(BaseModel):
    """Validation schema for team analysis queries"""
    team: str = Field(..., min_length=1)
    project_name: Optional[str] = None
    issue_count: int = Field(..., ge=0)
    story_points: Optional[int] = Field(None, ge=0)
    assignee: Optional[str] = None

class DoraMetricsRecord(BaseModel):
    """Validation schema for DORA metrics queries"""
    metric_name: str
    current_value: float = Field(..., ge=0)
    performance_tier: str = Field(..., regex='^(Elite|High|Medium|Low)$')
    measurement_period: str

class ReworkAnalysisRecord(BaseModel):
    """Validation schema for rework analysis queries"""
    pull_request_number: int = Field(..., gt=0)
    repository_name: str = Field(..., min_length=1)
    review_cycles: int = Field(..., ge=0)
    rework_commit_count: int = Field(..., ge=0)
    rework_indicator: bool
```

### Task 2.4: Self-Healing Memory System
**Duration**: 3-4 days  
**Priority**: HIGH  

#### Implementation Components
- **Learning Database**: Store validation failures and successful patterns
- **Pattern Recognition**: Identify similar query patterns and solutions
- **Feedback Integration**: Use learning context in retry attempts
- **Memory Retrieval**: Query similar successful patterns for guidance

#### Enhanced Database Schema with User Feedback (Updated from Phase 1)
```sql
-- Enhanced ai_learning_memory table with user feedback integration
ALTER TABLE ai_learning_memory ADD COLUMN IF NOT EXISTS
    user_feedback VARCHAR(20), -- 'helpful', 'incorrect', 'incomplete'
ADD COLUMN IF NOT EXISTS
    user_correction TEXT,
ADD COLUMN IF NOT EXISTS
    feedback_timestamp TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS
    message_id VARCHAR(100), -- Links to specific AI responses
ADD COLUMN IF NOT EXISTS
    response_text TEXT, -- Store the AI response that received feedback
ADD COLUMN IF NOT EXISTS
    query_text TEXT; -- Store the original user query

-- Create index for user feedback queries
CREATE INDEX IF NOT EXISTS idx_ai_learning_feedback
ON ai_learning_memory(client_id, user_feedback, feedback_timestamp)
WHERE user_feedback IS NOT NULL;

-- Create index for message tracking
CREATE INDEX IF NOT EXISTS idx_ai_learning_message
ON ai_learning_memory(message_id)
WHERE message_id IS NOT NULL;
```

#### Self-Healing Logic
```python
class SelfHealingMemory:
    """Memory system for learning from validation failures"""
    
    async def store_validation_failure(self, feedback: ValidationFeedback):
        """Store validation failure for learning"""
        with self.db_router.get_write_session() as session:
            session.execute(text("""
                INSERT INTO ai_learning_memory
                (error_type, user_intent, failed_query, specific_issue, suggested_fix,
                 confidence, learning_context, client_id)
                VALUES (:error_type, :user_intent, :failed_query, :specific_issue,
                        :suggested_fix, :confidence, :learning_context, :client_id)
            """), {
                "error_type": feedback.error_type.value,
                "user_intent": feedback.user_intent,
                "failed_query": feedback.failed_query,
                "specific_issue": feedback.specific_issue,
                "suggested_fix": feedback.suggested_fix,
                "confidence": feedback.confidence,
                "learning_context": json.dumps(feedback.learning_context),
                "client_id": feedback.client_id
            })
            session.commit()
    
    async def retrieve_similar_patterns(self, user_intent: str, error_type: ErrorType) -> List[Dict]:
        """Retrieve similar successful patterns for guidance"""
        with self.db_router.get_read_session() as session:
            results = session.execute(text("""
                SELECT user_intent, suggested_fix, learning_context, confidence
                FROM ai_learning_memory
                WHERE error_type = :error_type
                AND user_intent ILIKE :intent_pattern
                AND confidence > 0.7
                ORDER BY created_at DESC
                LIMIT 5
            """), {
                "error_type": error_type.value,
                "intent_pattern": f"%{user_intent[:20]}%"
            }).fetchall()
            
            return [dict(row) for row in results]
```

### Task 2.5: Backend Validation Endpoints
**Duration**: 2-3 days  
**Priority**: MEDIUM  

#### Implementation Components
- **Validation API**: Endpoints for external validation requests
- **Health Monitoring**: Validation system health checks
- **Performance Metrics**: Track validation success rates and timing
- **Admin Interface**: View validation logs and learning memory

#### Key Endpoints
```python
# services/backend-service/app/api/validation.py

@router.post("/api/validate/sql-syntax")
async def validate_sql_syntax_endpoint(
    request: SQLValidationRequest,
    db: Session = Depends(get_read_session),
    user: UserData = Depends(get_current_user)
):
    """Validate SQL syntax"""
    try:
        validation_result = await validate_sql_syntax_service(request.sql_query)
        return {
            "valid": validation_result.passed,
            "errors": validation_result.errors,
            "suggestions": validation_result.suggestions
        }
    except Exception as e:
        raise HTTPException(500, f"Validation failed: {str(e)}")

@router.post("/api/validate/sql-semantics")
async def validate_sql_semantics_endpoint(
    request: SemanticValidationRequest,
    user: UserData = Depends(get_current_user)
):
    """Validate SQL semantics"""
    try:
        validation_result = await validate_sql_semantics_service(
            request.sql_query,
            request.user_intent,
            request.analysis_context
        )
        return {
            "valid": validation_result.passed,
            "confidence": validation_result.confidence,
            "justification": validation_result.justification
        }
    except Exception as e:
        raise HTTPException(500, f"Semantic validation failed: {str(e)}")

@router.get("/api/validation/learning-memory")
async def get_learning_memory(
    client_id: int = Query(...),
    error_type: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_read_session),
    user: UserData = Depends(require_admin_user)
):
    """Get AI learning memory for analysis"""
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
            "count": len(memories)
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch learning memory: {str(e)}")
```

## 🔧 LangGraph Workflow Integration

### Enhanced Workflow with Validation Loops
```python
# services/ai-service/app/core/strategic_agent.py

def create_enhanced_workflow(self) -> StateGraph:
    """Create workflow with validation loops"""
    workflow = StateGraph(StrategicAgentState)
    
    # Existing nodes
    workflow.add_node("pre_analysis", intelligent_pre_analysis)
    workflow.add_node("semantic_search", targeted_semantic_search)
    workflow.add_node("structured_query", intelligent_structured_query)
    
    # NEW: Validation nodes
    workflow.add_node("validate_sql_syntax", validate_sql_syntax)
    workflow.add_node("validate_sql_semantics", validate_sql_semantics)
    workflow.add_node("validate_data_structure", validate_data_structure)
    workflow.add_node("self_healing_sql_generation", self_healing_sql_generation)
    
    # Existing analysis nodes
    workflow.add_node("ai_analysis", comprehensive_ai_analysis)
    workflow.add_node("generate_response", generate_final_response)
    
    # Enhanced routing with validation loops
    workflow.set_entry_point("pre_analysis")
    workflow.add_edge("pre_analysis", "semantic_search")
    
    # Validation loop routing
    workflow.add_conditional_edges(
        "structured_query",
        lambda state: "validate_syntax" if state.get("sql_query") else "ai_analysis",
        {
            "validate_syntax": "validate_sql_syntax",
            "ai_analysis": "ai_analysis"
        }
    )
    
    # Self-healing retry logic
    workflow.add_conditional_edges(
        "validate_sql_syntax",
        self._should_retry_with_healing,
        {
            "retry_with_healing": "self_healing_sql_generation",
            "semantic_check": "validate_sql_semantics",
            "proceed": "ai_analysis"
        }
    )
    
    workflow.add_conditional_edges(
        "validate_sql_semantics",
        self._should_retry_semantic,
        {
            "retry_sql": "self_healing_sql_generation",
            "execute_query": "ai_analysis",
            "fallback_analysis": "ai_analysis"
        }
    )
    
    return workflow

def _should_retry_with_healing(self, state: StrategicAgentState) -> str:
    """Determine if SQL should be retried with self-healing"""
    syntax_passed = state.get("sql_validation_passed", False)
    retry_count = state.get("sql_retry_count", 0)
    
    if syntax_passed:
        return "semantic_check"
    elif retry_count < MAX_SQL_RETRIES:
        state["sql_retry_count"] = retry_count + 1
        return "retry_with_healing"
    else:
        return "proceed"  # Give up after max retries

def _should_retry_semantic(self, state: StrategicAgentState) -> str:
    """Determine if semantic validation should trigger retry"""
    semantic_passed = state.get("semantic_validation_passed", False)
    confidence = state.get("semantic_confidence", 0.0)
    retry_count = state.get("semantic_retry_count", 0)
    
    if semantic_passed and confidence > 0.7:
        return "execute_query"
    elif retry_count < MAX_SEMANTIC_RETRIES:
        state["semantic_retry_count"] = retry_count + 1
        return "retry_sql"
    else:
        return "execute_query"  # Proceed with low confidence
```

## ✅ Success Criteria

1. **SQL Syntax Validation**: 95%+ of syntax errors caught before database execution
2. **Semantic Validation**: 80%+ of semantic mismatches identified and corrected
3. **Data Validation**: 90%+ of malformed data caught before analysis
4. **Self-Healing**: Learning memory accumulates patterns and improves retry success
5. **Performance**: Validation adds <2 seconds to total query processing time
6. **Reliability**: System gracefully handles validation failures without crashing

## 🚨 Risk Mitigation

1. **Validation Overhead**: Implement timeout limits and fallback strategies
2. **False Positives**: Allow manual override for validation failures
3. **Learning Memory Growth**: Implement cleanup policies for old learning data
4. **Model Costs**: Use cost-effective models for validation tasks
5. **Infinite Loops**: Strict retry limits prevent endless validation cycles

## 📝 Testing Strategy

### Unit Tests
- SQL syntax validation with various error types
- Semantic validation with different query intents
- Data structure validation with malformed data
- Learning memory storage and retrieval

### Integration Tests
- End-to-end validation pipeline
- Retry logic with actual AI models
- Performance impact measurement
- Error handling and recovery

### Load Tests
- Validation system under high query volume
- Memory usage with large learning datasets
- Concurrent validation requests

## 🔄 Phase 2 Completion Enables

- **Phase 3**: ML model training with validated data
- **Phase 4**: Reliable AI service with self-correction
- **Phase 5**: Production deployment with confidence in AI reliability

## 📋 Implementation Checklist

### Validation Infrastructure
- [ ] Install sqlglot dependency
- [ ] Create validation node classes
- [ ] Implement retry logic with limits
- [ ] Add validation error logging

### Self-Healing System
- [ ] Create learning memory service
- [ ] Implement pattern recognition
- [ ] Add feedback integration
- [ ] Test memory storage and retrieval

### Backend Integration
- [ ] Create validation API endpoints
- [ ] Add health monitoring
- [ ] Implement admin interface
- [ ] Test validation pipeline

### LangGraph Integration
- [ ] Update workflow with validation nodes
- [ ] Add conditional routing logic
- [ ] Implement retry mechanisms
- [ ] Test end-to-end validation flow

### Testing & Validation
- [ ] Unit tests for all validation components
- [ ] Integration tests for complete pipeline
- [ ] Performance testing under load
- [ ] Error handling and recovery testing
