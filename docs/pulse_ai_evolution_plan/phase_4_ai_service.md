# Phase 4: AI Service Implementation

**Duration**: Weeks 7-8  
**Priority**: HIGH  
**Risk Level**: MEDIUM  

## 🎯 Objectives

1. **Enhanced Strategic Agent**: LangGraph workflow with validation loops and ML predictions
2. **Self-Healing SQL Generation**: AI that learns from mistakes and improves over time
3. **Anomaly Detection**: Identify unusual patterns in predictions and data
4. **Production AI Service**: Scalable, reliable AI service with comprehensive monitoring
5. **Advanced Analytics**: Predictive insights integrated into business intelligence

## 📋 Task Breakdown

### Task 4.1: Enhanced Strategic Agent Implementation
**Duration**: 3-4 days  
**Priority**: CRITICAL  

#### AI Service Architecture
```
services/ai-service/
├── app/
│   ├── core/
│   │   ├── strategic_agent.py          # Enhanced LangGraph workflow
│   │   ├── validation_nodes.py         # Phase 2 validation nodes
│   │   ├── self_healing_nodes.py       # Self-correction capabilities
│   │   ├── ml_prediction_nodes.py      # ML integration nodes
│   │   ├── anomaly_detection.py        # Anomaly detection system
│   │   ├── session_manager.py          # Session management
│   │   ├── wex_ai_integration.py       # WEX AI Gateway client
│   │   └── backend_client.py           # Backend service communication
│   ├── schemas/
│   │   ├── agent_schemas.py            # Agent request/response models
│   │   ├── ml_schemas.py               # ML prediction schemas
│   │   └── validation_schemas.py       # Validation schemas
│   ├── api/
│   │   ├── agent_routes.py             # AI agent endpoints
│   │   ├── health_routes.py            # Health check endpoints
│   │   └── admin_routes.py             # Admin/monitoring endpoints
│   └── main.py
```

#### Enhanced Strategic Agent Class
```python
# services/ai-service/app/core/strategic_agent.py

class EnhancedStrategicAgent:
    """Strategic agent with validation loops and ML capabilities"""
    
    def __init__(self, wex_ai_client, backend_client, ml_client):
        self.wex_ai_client = wex_ai_client
        self.backend_client = backend_client
        self.ml_client = ml_client
        self.self_healing_memory = SelfHealingMemory(backend_client)
        self.anomaly_detector = AnomalyDetector(ml_client)
        
    def create_workflow(self) -> StateGraph:
        """Create enhanced workflow with all capabilities"""
        workflow = StateGraph(StrategicAgentState)
        
        # Phase 1 foundation nodes
        workflow.add_node("pre_analysis", self.intelligent_pre_analysis)
        workflow.add_node("semantic_search", self.targeted_semantic_search)
        workflow.add_node("structured_query", self.intelligent_structured_query)
        
        # Phase 2 validation nodes
        workflow.add_node("validate_sql_syntax", validate_sql_syntax)
        workflow.add_node("validate_sql_semantics", validate_sql_semantics)
        workflow.add_node("validate_data_structure", validate_data_structure)
        
        # Phase 4 self-healing nodes
        workflow.add_node("self_healing_sql_generation", self.self_healing_sql_generation)
        workflow.add_node("learn_from_failure", self.learn_from_failure)
        
        # Phase 3 ML enhancement nodes
        workflow.add_node("ml_predictions", self.add_ml_predictions)
        workflow.add_node("trajectory_forecasting", self.forecast_project_trajectory)
        workflow.add_node("anomaly_detection", self.detect_anomalies)
        
        # Analysis and response nodes
        workflow.add_node("ai_analysis", self.comprehensive_ai_analysis)
        workflow.add_node("generate_response", self.generate_final_response)
        
        # Enhanced routing with complete validation and ML pipeline
        workflow.set_entry_point("pre_analysis")
        
        # Pre-analysis flow
        workflow.add_edge("pre_analysis", "semantic_search")
        workflow.add_edge("semantic_search", "structured_query")
        
        # Validation pipeline
        workflow.add_conditional_edges(
            "structured_query",
            self._route_after_query_generation,
            {
                "validate_syntax": "validate_sql_syntax",
                "ml_predictions": "ml_predictions",
                "ai_analysis": "ai_analysis"
            }
        )
        
        # Self-healing retry logic
        workflow.add_conditional_edges(
            "validate_sql_syntax",
            self._route_after_syntax_validation,
            {
                "semantic_validation": "validate_sql_semantics",
                "self_healing": "self_healing_sql_generation",
                "ml_predictions": "ml_predictions"
            }
        )
        
        workflow.add_conditional_edges(
            "validate_sql_semantics",
            self._route_after_semantic_validation,
            {
                "self_healing": "self_healing_sql_generation",
                "ml_predictions": "ml_predictions",
                "learn_failure": "learn_from_failure"
            }
        )
        
        # ML prediction pipeline
        workflow.add_edge("ml_predictions", "trajectory_forecasting")
        workflow.add_edge("trajectory_forecasting", "anomaly_detection")
        workflow.add_edge("anomaly_detection", "ai_analysis")
        
        # Final analysis and response
        workflow.add_edge("ai_analysis", "generate_response")
        
        return workflow
    
    async def intelligent_pre_analysis(self, state: StrategicAgentState) -> StrategicAgentState:
        """Enhanced pre-analysis with learning context"""
        # Existing pre-analysis logic
        user_query = state.get("user_query", "")
        
        # NEW: Check learning memory for similar queries
        similar_patterns = await self.self_healing_memory.retrieve_similar_patterns(
            user_query, 
            error_type=None  # Get all patterns
        )
        
        if similar_patterns:
            state["learning_context"] = {
                "similar_successful_queries": similar_patterns[:3],
                "common_patterns": self._extract_common_patterns(similar_patterns)
            }
        
        # Enhanced analysis intent with learning context
        analysis_intent = await self.wex_ai_client.determine_analysis_intent(
            user_query=user_query,
            learning_context=state.get("learning_context", {})
        )
        
        state["analysis_intent"] = analysis_intent
        state["pre_analysis_completed"] = True
        
        return state
    
    async def self_healing_sql_generation(self, state: StrategicAgentState) -> StrategicAgentState:
        """Generate SQL with self-healing capabilities"""
        
        # Get validation feedback from previous attempts
        validation_history = state.get("validation_feedback_history", [])
        user_intent = state.get("analysis_intent", "")
        
        # Retrieve similar successful patterns
        if validation_history:
            last_error = validation_history[-1]
            similar_patterns = await self.self_healing_memory.retrieve_similar_patterns(
                user_intent,
                ErrorType(last_error.get("error_type", "semantic_mismatch"))
            )
        else:
            similar_patterns = []
        
        # Enhanced prompt with learning context
        learning_context = self._format_learning_context(validation_history, similar_patterns)
        
        enhanced_prompt = f"""
        SELF-HEALING SQL GENERATION
        
        User Query: {state['user_query']}
        Analysis Intent: {user_intent}
        
        {learning_context}
        
        Database Schema Context: {state.get('schema_context', '')}
        
        Generate improved SQL that addresses previous validation issues.
        Apply lessons learned to avoid similar mistakes.
        Ensure client isolation with proper WHERE clauses.
        """
        
        # Generate SQL with enhanced context
        try:
            sql_response = await self.wex_ai_client.generate_structured_query(
                prompt=enhanced_prompt,
                context=state.get("business_context", ""),
                use_premium=len(validation_history) > 1  # Use premium model for complex cases
            )
            
            state["sql_query"] = sql_response.get("sql_query", "")
            state["query_explanation"] = sql_response.get("explanation", "")
            state["self_healing_applied"] = True
            
        except Exception as e:
            state["sql_generation_error"] = str(e)
            state["self_healing_applied"] = False
        
        return state
    
    async def add_ml_predictions(self, state: StrategicAgentState) -> StrategicAgentState:
        """Add ML predictions to analysis results"""
        
        query_results = state.get("all_query_results", [])
        analysis_intent = state.get("analysis_intent", "").lower()
        
        try:
            # Determine which ML predictions to add based on query intent
            if "epic" in analysis_intent or "trajectory" in analysis_intent:
                # Add trajectory predictions for epics
                epic_keys = self._extract_epic_keys(query_results)
                if epic_keys:
                    trajectory_predictions = await self.ml_client.predict_trajectory(epic_keys)
                    state["ml_trajectory_predictions"] = trajectory_predictions
            
            if "story" in analysis_intent or "complexity" in analysis_intent:
                # Add complexity estimates for unestimated stories
                story_keys = self._extract_unestimated_story_keys(query_results)
                if story_keys:
                    complexity_estimates = await self.ml_client.estimate_complexity(story_keys)
                    state["ml_complexity_estimates"] = complexity_estimates
            
            if "pull request" in analysis_intent or "rework" in analysis_intent:
                # Add rework risk assessments for open PRs
                pr_numbers = self._extract_open_pr_numbers(query_results)
                if pr_numbers:
                    rework_assessments = await self.ml_client.assess_rework_risk(pr_numbers)
                    state["ml_rework_assessments"] = rework_assessments
            
            state["ml_predictions_added"] = True
            
        except Exception as e:
            logger.warning(f"ML predictions failed: {e}")
            state["ml_predictions_added"] = False
            state["ml_prediction_error"] = str(e)
        
        return state
    
    async def detect_anomalies(self, state: StrategicAgentState) -> StrategicAgentState:
        """Detect anomalies in predictions and data"""
        
        try:
            anomalies_detected = []
            
            # Check trajectory prediction anomalies
            trajectory_predictions = state.get("ml_trajectory_predictions", {})
            if trajectory_predictions:
                trajectory_anomalies = await self.anomaly_detector.detect_trajectory_anomalies(
                    trajectory_predictions
                )
                anomalies_detected.extend(trajectory_anomalies)
            
            # Check complexity estimation anomalies
            complexity_estimates = state.get("ml_complexity_estimates", {})
            if complexity_estimates:
                complexity_anomalies = await self.anomaly_detector.detect_complexity_anomalies(
                    complexity_estimates
                )
                anomalies_detected.extend(complexity_anomalies)
            
            # Check data pattern anomalies
            query_results = state.get("all_query_results", [])
            if query_results:
                data_anomalies = await self.anomaly_detector.detect_data_anomalies(
                    query_results, state.get("analysis_intent", "")
                )
                anomalies_detected.extend(data_anomalies)
            
            state["anomalies_detected"] = anomalies_detected
            state["anomaly_detection_completed"] = True
            
            # Log significant anomalies
            critical_anomalies = [a for a in anomalies_detected if a.get("severity") == "critical"]
            if critical_anomalies:
                await self._log_critical_anomalies(critical_anomalies, state)
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            state["anomaly_detection_completed"] = False
            state["anomaly_detection_error"] = str(e)
        
        return state
    
    async def comprehensive_ai_analysis(self, state: StrategicAgentState) -> StrategicAgentState:
        """Enhanced AI analysis with ML predictions and anomaly context"""
        
        # Gather all analysis inputs
        query_results = state.get("all_query_results", [])
        ml_predictions = {
            "trajectory": state.get("ml_trajectory_predictions", {}),
            "complexity": state.get("ml_complexity_estimates", {}),
            "rework": state.get("ml_rework_assessments", {})
        }
        anomalies = state.get("anomalies_detected", [])
        
        # Enhanced analysis prompt with ML context
        analysis_prompt = f"""
        COMPREHENSIVE BUSINESS INTELLIGENCE ANALYSIS
        
        User Query: {state['user_query']}
        Analysis Intent: {state.get('analysis_intent', '')}
        
        Data Results: {json.dumps(query_results[:10], indent=2)}  # Limit for prompt size
        
        ML Predictions:
        {self._format_ml_predictions_for_prompt(ml_predictions)}
        
        Anomalies Detected:
        {self._format_anomalies_for_prompt(anomalies)}
        
        Provide strategic insights that:
        1. Answer the user's question directly
        2. Incorporate ML predictions for forward-looking insights
        3. Highlight any anomalies or unusual patterns
        4. Provide actionable recommendations
        5. Include confidence levels for predictions
        """
        
        try:
            analysis_response = await self.wex_ai_client.generate_comprehensive_analysis(
                prompt=analysis_prompt,
                use_premium=True  # Use premium model for final analysis
            )
            
            state["ai_analysis_result"] = analysis_response
            state["analysis_completed"] = True
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            state["analysis_completed"] = False
            state["analysis_error"] = str(e)
        
        return state
    
    # Routing methods
    def _route_after_query_generation(self, state: StrategicAgentState) -> str:
        """Route after SQL query generation"""
        if state.get("sql_query"):
            return "validate_syntax"
        elif state.get("analysis_intent", "").lower() in ["prediction", "forecast", "estimate"]:
            return "ml_predictions"
        else:
            return "ai_analysis"
    
    def _route_after_syntax_validation(self, state: StrategicAgentState) -> str:
        """Route after SQL syntax validation"""
        if not state.get("sql_validation_passed", False):
            retry_count = state.get("sql_retry_count", 0)
            if retry_count < MAX_SQL_RETRIES:
                return "self_healing"
            else:
                return "ml_predictions"  # Give up on SQL, try ML predictions
        else:
            return "semantic_validation"
    
    def _route_after_semantic_validation(self, state: StrategicAgentState) -> str:
        """Route after SQL semantic validation"""
        semantic_passed = state.get("semantic_validation_passed", False)
        confidence = state.get("semantic_confidence", 0.0)
        retry_count = state.get("semantic_retry_count", 0)
        
        if semantic_passed and confidence > 0.7:
            return "ml_predictions"
        elif retry_count < MAX_SEMANTIC_RETRIES:
            return "self_healing"
        else:
            # Log failure for learning
            return "learn_failure"
```

### Task 4.2: Anomaly Detection System
**Duration**: 2-3 days  
**Priority**: MEDIUM  

#### Anomaly Detection Implementation
```python
# services/ai-service/app/core/anomaly_detection.py

class AnomalyDetector:
    """Detect anomalies in ML predictions and data patterns"""
    
    def __init__(self, ml_client):
        self.ml_client = ml_client
        self.anomaly_thresholds = {
            "trajectory_prediction": {
                "max_lead_time_days": 365,  # More than 1 year is suspicious
                "min_lead_time_days": 1,    # Less than 1 day is suspicious
                "confidence_threshold": 0.3  # Low confidence predictions
            },
            "complexity_estimation": {
                "max_story_points": 21,     # More than 21 points is suspicious
                "min_story_points": 0.5,    # Less than 0.5 points is suspicious
                "confidence_threshold": 0.4
            },
            "rework_probability": {
                "high_risk_threshold": 0.8,  # Very high rework probability
                "confidence_threshold": 0.3
            }
        }
    
    async def detect_trajectory_anomalies(self, trajectory_predictions: Dict) -> List[Dict]:
        """Detect anomalies in trajectory predictions"""
        anomalies = []
        thresholds = self.anomaly_thresholds["trajectory_prediction"]
        
        for prediction in trajectory_predictions.get("predictions", []):
            lead_time_days = prediction.get("predicted_lead_time_days", 0)
            confidence = prediction.get("confidence_score", 1.0)
            
            # Check for extreme lead times
            if lead_time_days > thresholds["max_lead_time_days"]:
                anomalies.append({
                    "type": "trajectory_anomaly",
                    "severity": "high",
                    "epic_key": prediction.get("epic_key"),
                    "issue": f"Predicted lead time of {lead_time_days:.1f} days is unusually high",
                    "predicted_value": lead_time_days,
                    "threshold": thresholds["max_lead_time_days"]
                })
            
            elif lead_time_days < thresholds["min_lead_time_days"]:
                anomalies.append({
                    "type": "trajectory_anomaly",
                    "severity": "medium",
                    "epic_key": prediction.get("epic_key"),
                    "issue": f"Predicted lead time of {lead_time_days:.1f} days is unusually low",
                    "predicted_value": lead_time_days,
                    "threshold": thresholds["min_lead_time_days"]
                })
            
            # Check for low confidence predictions
            if confidence < thresholds["confidence_threshold"]:
                anomalies.append({
                    "type": "trajectory_confidence_anomaly",
                    "severity": "low",
                    "epic_key": prediction.get("epic_key"),
                    "issue": f"Low confidence ({confidence:.2f}) in trajectory prediction",
                    "confidence": confidence,
                    "threshold": thresholds["confidence_threshold"]
                })
        
        return anomalies
    
    async def detect_complexity_anomalies(self, complexity_estimates: Dict) -> List[Dict]:
        """Detect anomalies in complexity estimations"""
        anomalies = []
        thresholds = self.anomaly_thresholds["complexity_estimation"]
        
        for estimate in complexity_estimates.get("estimates", []):
            story_points = estimate.get("estimated_story_points", 0)
            confidence = estimate.get("confidence_score", 1.0)
            
            # Check for extreme story point estimates
            if story_points > thresholds["max_story_points"]:
                anomalies.append({
                    "type": "complexity_anomaly",
                    "severity": "high",
                    "issue_key": estimate.get("issue_key"),
                    "issue": f"Estimated {story_points} story points is unusually high",
                    "estimated_value": story_points,
                    "threshold": thresholds["max_story_points"]
                })
            
            elif story_points < thresholds["min_story_points"]:
                anomalies.append({
                    "type": "complexity_anomaly",
                    "severity": "low",
                    "issue_key": estimate.get("issue_key"),
                    "issue": f"Estimated {story_points} story points is unusually low",
                    "estimated_value": story_points,
                    "threshold": thresholds["min_story_points"]
                })
        
        return anomalies
    
    async def detect_data_anomalies(self, query_results: List[Dict], analysis_intent: str) -> List[Dict]:
        """Detect anomalies in query result data patterns"""
        anomalies = []
        
        if not query_results:
            return anomalies
        
        try:
            # Statistical anomaly detection
            if "team" in analysis_intent.lower():
                team_anomalies = self._detect_team_performance_anomalies(query_results)
                anomalies.extend(team_anomalies)
            
            if "velocity" in analysis_intent.lower():
                velocity_anomalies = self._detect_velocity_anomalies(query_results)
                anomalies.extend(velocity_anomalies)
            
            if "lead time" in analysis_intent.lower():
                lead_time_anomalies = self._detect_lead_time_anomalies(query_results)
                anomalies.extend(lead_time_anomalies)
            
        except Exception as e:
            logger.error(f"Data anomaly detection failed: {e}")
        
        return anomalies
```

## ✅ Success Criteria

1. **Enhanced Agent**: Complete LangGraph workflow with all validation and ML capabilities
2. **Self-Healing**: Agent learns from failures and improves query generation
3. **ML Integration**: Predictions seamlessly integrated into analysis workflow
4. **Anomaly Detection**: Unusual patterns identified and reported
5. **Performance**: End-to-end analysis completes within 30 seconds
6. **Reliability**: System handles errors gracefully with fallback strategies

## 🚨 Risk Mitigation

1. **Complexity Management**: Modular design allows disabling features if needed
2. **Performance Optimization**: Async processing and caching for ML operations
3. **Error Handling**: Comprehensive error handling with graceful degradation
4. **Resource Management**: Connection pooling and session management
5. **Monitoring**: Detailed logging and health checks for all components

## 🔄 Phase 4 Completion Enables

- **Phase 5**: Production optimization and deployment
- **Full AI Platform**: Complete AI-powered business intelligence system
