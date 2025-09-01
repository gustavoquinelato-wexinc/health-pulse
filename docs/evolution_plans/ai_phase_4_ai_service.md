# Phase 4: AI Service Implementation - LlamaIndex Orchestration

**Component**: Cognitive Core → Self-healing, self-validating AI agent that turns data into predictions and narrative insights
**Duration**: Weeks 7-8
**Priority**: HIGH
**Risk Level**: MEDIUM

## 🎯 Objectives

1. **LlamaIndex Orchestration**: Replace custom agents with proven LlamaIndex framework for intelligent tool orchestration
2. **Self-Healing SQL Generation**: AI that learns from mistakes and improves over time through user feedback
3. **ML Integration**: Seamless connection between SQL queries and PostgresML predictions
4. **Query Intelligence**: Automatic query complexity classification and optimal routing
5. **Production AI Service**: Scalable, reliable AI service with comprehensive monitoring and user feedback loops
6. **Advanced Analytics**: Predictive insights integrated into conversational business intelligence

## 📋 Task Breakdown

### Task 4.1: LlamaIndex Orchestration Implementation
**Duration**: 3-4 days
**Priority**: CRITICAL

#### AI Service Architecture with LlamaIndex
```
services/ai-service/
├── app/
│   ├── core/
│   │   ├── llamaindex_orchestrator.py  # LlamaIndex agent orchestration
│   │   ├── query_classifier.py         # Query complexity classification
│   │   ├── sql_tools.py                # SQL query tools for LlamaIndex
│   │   ├── ml_tools.py                 # PostgresML prediction tools
│   │   ├── validation_tools.py         # Phase 2 validation tools
│   │   ├── feedback_processor.py       # User feedback integration
│   │   ├── session_manager.py          # Session management
│   │   └── backend_client.py           # Backend service communication
│   ├── tools/
│   │   ├── database_tool.py            # LlamaIndex SQL database tool
│   │   ├── ml_prediction_tool.py       # ML model prediction tool
│   │   ├── validation_tool.py          # Query validation tool
│   │   └── feedback_tool.py            # User feedback collection tool
│   ├── schemas/
│   │   ├── agent_schemas.py            # Agent request/response models
│   │   ├── ml_schemas.py               # ML prediction schemas
│   │   ├── validation_schemas.py       # Validation schemas
│   │   └── feedback_schemas.py         # User feedback schemas
│   ├── api/
│   │   ├── agent_routes.py             # AI agent endpoints
│   │   ├── feedback_routes.py          # User feedback endpoints
│   │   ├── health_routes.py            # Health check endpoints
│   │   └── admin_routes.py             # Admin/monitoring endpoints
│   └── main.py
```

#### Hybrid Strategic Agent with LLM-Based Routing
```python
# services/ai-service/app/core/hybrid_strategic_agent.py

from langgraph.graph import StateGraph, START, END
from llama_index.core import SQLDatabase, ServiceContext
from llama_index.core.query_engine import NLSQLTableQueryEngine
from llama_index.core.tools import QueryEngineTool, FunctionTool
from llama_index.agent.openai import OpenAIAgent
from typing import Dict, List, Any, TypedDict
import asyncio
import json
import time

class StrategicAgentState(TypedDict):
    user_query: str
    client_id: int
    user_id: int
    analysis_intent: str
    query_complexity: str  # 'simple', 'moderate', 'complex'
    required_ml_models: List[str]  # ['trajectory', 'complexity', 'rework', 'none']
    requires_narrative: bool
    sql_query: str
    query_results: List[Dict]
    ml_predictions: Dict[str, Any]
    ai_response: str
    metadata: Dict[str, Any]
    processing_steps: List[str]
    learning_context: Dict[str, Any]
    timestamp: float

class HybridStrategicAgent:
    """Combines LangGraph workflow orchestration with LlamaIndex tool intelligence and LLM-based routing"""

    def __init__(self, db_client, ml_client, validation_client, wex_ai_client):
        self.db_client = db_client
        self.ml_client = ml_client
        self.validation_client = validation_client
        self.wex_ai_client = wex_ai_client
        self.self_healing_memory = SelfHealingMemory(db_client)

        # Initialize LlamaIndex components for complex queries
        self.llamaindex_orchestrator = self._create_llamaindex_orchestrator()

        # Create LangGraph workflow
        self.workflow = self._create_workflow()

    def _create_workflow(self) -> CompiledGraph:
        """Create LangGraph workflow with intelligent routing"""

        workflow = StateGraph(StrategicAgentState)

        # Workflow nodes
        workflow.add_node("intelligent_pre_analysis", self._intelligent_pre_analysis)
        workflow.add_node("simple_sql_execution", self._handle_simple_query)
        workflow.add_node("moderate_analysis", self._handle_moderate_query)
        workflow.add_node("complex_llamaindex", self._handle_complex_query)
        workflow.add_node("ml_predictions", self._add_ml_predictions)
        workflow.add_node("validate_response", self._validate_response)
        workflow.add_node("generate_narrative", self._generate_narrative)

        # Workflow edges
        workflow.add_edge(START, "intelligent_pre_analysis")
        workflow.add_conditional_edges(
            "intelligent_pre_analysis",
            self._route_by_complexity,
            {
                "simple": "simple_sql_execution",
                "moderate": "moderate_analysis",
                "complex": "complex_llamaindex"
            }
        )

        # ML predictions routing
        workflow.add_conditional_edges(
            "simple_sql_execution",
            self._check_ml_needed,
            {
                "ml_needed": "ml_predictions",
                "narrative_needed": "generate_narrative",
                "complete": "validate_response"
            }
        )

        workflow.add_conditional_edges(
            "moderate_analysis",
            self._check_ml_needed,
            {
                "ml_needed": "ml_predictions",
                "narrative_needed": "generate_narrative",
                "complete": "validate_response"
            }
        )

        workflow.add_edge("complex_llamaindex", "validate_response")
        workflow.add_edge("ml_predictions", "generate_narrative")
        workflow.add_edge("generate_narrative", "validate_response")
        workflow.add_edge("validate_response", END)

        return workflow.compile()

    async def _intelligent_pre_analysis(self, state: StrategicAgentState) -> StrategicAgentState:
        """Enhanced pre-analysis with LLM-based routing - Zero-shot classification"""
        user_query = state["user_query"]

        # LLM-Based Routing & Analysis Intent
        routing_prompt = f"""
        QUERY ANALYSIS TASK
        Analyze the user's query and determine the best way to handle it.

        User Query: "{user_query}"

        Please analyze this query and return a JSON response with:
        1. `analysis_intent`: A concise summary of what the user wants to know.
        2. `complexity`: One of ['simple', 'moderate', 'complex'].
            - 'simple': Direct facts, counts, or single-data-point lookups. (e.g., "How many open bugs?")
            - 'moderate': Multi-step analysis, single-model prediction, or aggregations. (e.g., "What's the average lead time for Team Alpha?")
            - 'complex': Requires multiple models, narrative synthesis, "why" questions, or strategic recommendations. (e.g., "Why did velocity drop last sprint?")
        3. `required_models`: A list of ML models needed to answer this. Options: ['trajectory', 'complexity', 'rework', 'none'].
        4. `requires_narrative`: Boolean. True if the answer needs a thoughtful explanation, not just data.

        Respond ONLY with valid JSON.
        """

        try:
            analysis_result = await self.wex_ai_client.quick_validation(
                prompt=routing_prompt,
                model="azure-gpt-4o-mini",  # Use the fast/cheap model
                max_tokens=200
            )

            result = json.loads(analysis_result)

            # Update the state with the routing decision
            state["analysis_intent"] = result.get("analysis_intent", user_query)
            state["query_complexity"] = result.get("complexity", "moderate")
            state["required_ml_models"] = result.get("required_models", [])
            state["requires_narrative"] = result.get("requires_narrative", True)

        except (json.JSONDecodeError, Exception) as e:
            # Fallback: assume it's a complex query
            state["analysis_intent"] = user_query
            state["query_complexity"] = "complex"
            state["required_ml_models"] = []
            state["requires_narrative"] = True

        # Check learning memory for similar queries (Phase 2 integration)
        similar_patterns = await self.self_healing_memory.retrieve_similar_patterns(
            user_query, error_type=None
        )
        if similar_patterns:
            state["learning_context"] = {
                "similar_successful_queries": similar_patterns[:3],
                "common_patterns": self._extract_common_patterns(similar_patterns)
            }

        state["processing_steps"] = ["intelligent_pre_analysis_completed"]
        return state

    def _route_by_complexity(self, state: StrategicAgentState) -> str:
        """Route based on LLM-determined complexity"""
        complexity = state.get("query_complexity", "moderate")

        if complexity == "simple":
            return "simple"
        elif complexity == "moderate":
            return "moderate"
        else:
            return "complex"

    def _check_ml_needed(self, state: StrategicAgentState) -> str:
        """Check if ML predictions or narrative generation is needed"""
        required_models = state.get("required_ml_models", [])
        requires_narrative = state.get("requires_narrative", False)

        if required_models and "none" not in required_models:
            return "ml_needed"
        elif requires_narrative:
            return "narrative_needed"
        else:
            return "complete"

    async def _handle_simple_query(self, state: StrategicAgentState) -> StrategicAgentState:
        """Handle simple queries with direct SQL execution"""
        user_query = state["user_query"]
        client_id = state["client_id"]

        # Generate simple SQL query
        sql_query = await self._generate_simple_sql(user_query, client_id)
        state["sql_query"] = sql_query

        # Execute query
        try:
            results = await self.db_client.execute(sql_query)
            state["query_results"] = results
            state["ai_response"] = self._format_simple_response(results, user_query)

        except Exception as e:
            state["ai_response"] = f"I encountered an error executing your query: {str(e)}"
            state["metadata"] = {"error": str(e), "query": sql_query}

        state["processing_steps"].append("simple_query_executed")
        return state

    async def _handle_moderate_query(self, state: StrategicAgentState) -> StrategicAgentState:
        """Handle moderate queries with multi-step analysis"""
        user_query = state["user_query"]
        client_id = state["client_id"]

        # Generate more complex SQL with aggregations
        sql_query = await self._generate_moderate_sql(user_query, client_id)
        state["sql_query"] = sql_query

        # Execute query with error handling
        try:
            results = await self.db_client.execute(sql_query)
            state["query_results"] = results

            # Basic analysis without full narrative
            state["ai_response"] = self._format_moderate_response(results, user_query)

        except Exception as e:
            # Use self-healing memory for retry
            corrected_query = await self._attempt_self_healing(sql_query, str(e), client_id)
            if corrected_query:
                results = await self.db_client.execute(corrected_query)
                state["query_results"] = results
                state["ai_response"] = self._format_moderate_response(results, user_query)
            else:
                state["ai_response"] = f"I encountered an error and couldn't automatically fix it: {str(e)}"

        state["processing_steps"].append("moderate_query_executed")
        return state

    async def _handle_complex_query(self, state: StrategicAgentState) -> StrategicAgentState:
        """Handle complex queries using LlamaIndex orchestration"""
        user_query = state["user_query"]
        client_id = state["client_id"]
        user_id = state.get("user_id")

        # Use LlamaIndex for complex orchestration
        try:
            result = await self.llamaindex_orchestrator.process_query(
                user_query, client_id, user_id
            )

            state["ai_response"] = result["response"]
            state["metadata"] = result["metadata"]
            state["query_results"] = result.get("query_results", [])

        except Exception as e:
            state["ai_response"] = "I encountered an error processing your complex query. Please try rephrasing or contact support."
            state["metadata"] = {"error": str(e), "fallback_used": True}

        state["processing_steps"].append("complex_query_processed_via_llamaindex")
        return state

    async def _add_ml_predictions(self, state: StrategicAgentState) -> StrategicAgentState:
        """Add ML predictions based on pre-analysis requirements"""
        required_models = state.get("required_ml_models", [])
        query_results = state.get("query_results", [])
        client_id = state["client_id"]

        ml_predictions = {}

        try:
            if "trajectory" in required_models:
                epic_keys = self._extract_epic_keys(query_results)
                if epic_keys:
                    trajectory_predictions = await self.ml_client.predict_trajectory(epic_keys, client_id)
                    ml_predictions["trajectory"] = trajectory_predictions

            if "complexity" in required_models:
                story_keys = self._extract_unestimated_story_keys(query_results)
                if story_keys:
                    complexity_estimates = await self.ml_client.estimate_complexity(story_keys, client_id)
                    ml_predictions["complexity"] = complexity_estimates

            if "rework" in required_models:
                pr_numbers = self._extract_open_pr_numbers(query_results)
                if pr_numbers:
                    rework_assessments = await self.ml_client.assess_rework_risk(pr_numbers, client_id)
                    ml_predictions["rework"] = rework_assessments

            state["ml_predictions"] = ml_predictions

        except Exception as e:
            state["ml_predictions"] = {}
            state["metadata"] = state.get("metadata", {})
            state["metadata"]["ml_error"] = str(e)

        state["processing_steps"].append("ml_predictions_added")
        return state

    async def _generate_narrative(self, state: StrategicAgentState) -> StrategicAgentState:
        """Generate narrative response combining data and ML predictions"""
        user_query = state["user_query"]
        query_results = state.get("query_results", [])
        ml_predictions = state.get("ml_predictions", {})
        analysis_intent = state.get("analysis_intent", user_query)

        # Create narrative prompt
        narrative_prompt = f"""
        Create a comprehensive business intelligence response for this query.

        User Question: {user_query}
        Analysis Intent: {analysis_intent}

        Data Results: {json.dumps(query_results[:10], default=str)}  # Limit for token efficiency
        ML Predictions: {json.dumps(ml_predictions, default=str)}

        Provide:
        1. Direct answer to the user's question
        2. Key insights from the data
        3. ML-powered predictions and their business implications
        4. Actionable recommendations
        5. Context and confidence levels

        Be conversational but professional. Focus on business value and actionable insights.
        """

        try:
            narrative_response = await self.wex_ai_client.generate_response(
                prompt=narrative_prompt,
                model="azure-gpt-4o",  # Use the more capable model for narrative
                max_tokens=1000
            )

            state["ai_response"] = narrative_response

        except Exception as e:
            # Fallback to basic response
            state["ai_response"] = self._create_fallback_response(query_results, ml_predictions, user_query)

        state["processing_steps"].append("narrative_generated")
        return state

    async def _validate_response(self, state: StrategicAgentState) -> StrategicAgentState:
        """Validate the final response using Phase 2 validation"""
        try:
            validation_result = await self.validation_client.validate_response(
                state["user_query"],
                state["ai_response"],
                state["client_id"]
            )

            if not validation_result.get("is_valid", True):
                # Attempt correction
                corrected_response = validation_result.get("suggested_correction")
                if corrected_response:
                    state["ai_response"] = corrected_response
                    state["metadata"] = state.get("metadata", {})
                    state["metadata"]["validation_corrected"] = True

        except Exception as e:
            # Validation failed, but don't break the response
            state["metadata"] = state.get("metadata", {})
            state["metadata"]["validation_error"] = str(e)

        state["processing_steps"].append("response_validated")
        return state

    async def process_query(self, user_query: str, client_id: int, user_id: int = None) -> Dict[str, Any]:
        """Main entry point for query processing"""

        initial_state = StrategicAgentState(
            user_query=user_query,
            client_id=client_id,
            user_id=user_id or 0,
            analysis_intent="",
            query_complexity="moderate",
            required_ml_models=[],
            requires_narrative=True,
            sql_query="",
            query_results=[],
            ml_predictions={},
            ai_response="",
            metadata={},
            processing_steps=[],
            learning_context={},
            timestamp=time.time()
        )

        try:
            # Execute through LangGraph workflow
            final_state = await self.workflow.ainvoke(initial_state)

            return {
                "response": final_state["ai_response"],
                "metadata": {
                    **final_state.get("metadata", {}),
                    "query_complexity": final_state["query_complexity"],
                    "required_ml_models": final_state["required_ml_models"],
                    "processing_steps": final_state["processing_steps"],
                    "processing_time_ms": (time.time() - final_state["timestamp"]) * 1000
                },
                "client_id": client_id,
                "user_id": user_id,
                "timestamp": final_state["timestamp"]
            }

        except Exception as e:
            # Graceful error handling
            return {
                "response": "I encountered an error processing your query. Please try rephrasing your question or contact support if the issue persists.",
                "error": str(e),
                "metadata": {
                    "error_type": type(e).__name__,
                    "processing_steps": ["error_occurred"]
                },
                "client_id": client_id,
                "user_id": user_id,
                "timestamp": time.time()
            }

    async def process_user_feedback(self, message_id: str, feedback: str, correction: str, client_id: int, user_id: int):
        """Process user feedback for continuous learning"""
        feedback_data = {
            'message_id': message_id,
            'feedback': feedback,
            'user_correction': correction,
            'client_id': client_id,
            'user_id': user_id,
            'timestamp': time.time()
        }

        # Store in ai_learning_memory for Phase 2 integration
        await self.db_client.execute("""
            INSERT INTO ai_learning_memory
            (query_text, response_text, error_type, user_feedback, user_correction, message_id, client_id, feedback_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, [
            feedback_data.get('original_query', ''),
            feedback_data.get('original_response', ''),
            'user_feedback',
            feedback,
            correction,
            message_id,
            client_id
        ])

        return {'status': 'feedback_processed', 'message_id': message_id}

    # Supporting methods
    def _extract_epic_keys(self, query_results: List[Dict]) -> List[str]:
        """Extract epic keys from query results"""
        epic_keys = []
        for row in query_results:
            if 'epic_key' in row and row['epic_key']:
                epic_keys.append(row['epic_key'])
            elif 'key' in row and row.get('issuetype_name') == 'Epic':
                epic_keys.append(row['key'])
        return list(set(epic_keys))  # Remove duplicates

    def _extract_unestimated_story_keys(self, query_results: List[Dict]) -> List[str]:
        """Extract story keys that need complexity estimation"""
        story_keys = []
        for row in query_results:
            if (row.get('issuetype_name') in ['Story', 'Task'] and
                (not row.get('story_points') or row.get('story_points') == 0)):
                story_keys.append(row['key'])
        return story_keys

    def _extract_open_pr_numbers(self, query_results: List[Dict]) -> List[int]:
        """Extract PR numbers for rework risk assessment"""
        pr_numbers = []
        for row in query_results:
            if 'pr_number' in row and row.get('state') == 'open':
                pr_numbers.append(row['pr_number'])
        return pr_numbers
```

### Task 4.2: Phased Approach to Query Intelligence
**Duration**: 1-2 days
**Priority**: HIGH

#### The Intelligence Evolution Strategy

**Phase 4 (Current): LLM-Based Routing (Zero-Shot Classification)**
- ✅ **Fast Implementation**: No training data required, can be built immediately
- ✅ **Highly Flexible**: Understands natural language nuances and new query types
- ✅ **Cost Effective**: Uses fast, cheap models (GPT-4o-mini) for routing decisions
- ✅ **Immediate Intelligence**: Sophisticated behavior from day one

**Phase 7 (Future): Dedicated ML Classifier**
- 🎯 **Ultimate Goal**: Train XGBoost/PostgresML model on real user query data
- 🎯 **Performance**: Faster routing decisions, lower per-query costs
- 🎯 **Data-Driven**: Based on 10,000+ real user queries collected from Phase 4
- 🎯 **Optimization**: Perfect dataset for training highly accurate classifier

#### LLM-Based Routing Implementation

```python
# The routing prompt that makes it all work
ROUTING_PROMPT_TEMPLATE = """
QUERY ANALYSIS TASK
Analyze the user's query and determine the best way to handle it.

User Query: "{user_query}"

Please analyze this query and return a JSON response with:
1. `analysis_intent`: A concise summary of what the user wants to know.
2. `complexity`: One of ['simple', 'moderate', 'complex'].
    - 'simple': Direct facts, counts, or single-data-point lookups.
      Examples: "How many open bugs?", "List active epics", "Count of PRs this month"
    - 'moderate': Multi-step analysis, single-model prediction, or aggregations.
      Examples: "What's the average lead time for Team Alpha?", "Show velocity trends", "Predict epic completion"
    - 'complex': Requires multiple models, narrative synthesis, "why" questions, or strategic recommendations.
      Examples: "Why did velocity drop last sprint?", "What should we focus on next quarter?", "Complete DORA analysis"
3. `required_models`: A list of ML models needed to answer this. Options: ['trajectory', 'complexity', 'rework', 'none'].
4. `requires_narrative`: Boolean. True if the answer needs a thoughtful explanation, not just data.

Respond ONLY with valid JSON.
"""

# Example routing decisions
ROUTING_EXAMPLES = {
    "How many issues are open?": {
        "complexity": "simple",
        "required_models": ["none"],
        "requires_narrative": False
    },

    "What's the predicted completion time for PROJ-123?": {
        "complexity": "moderate",
        "required_models": ["trajectory"],
        "requires_narrative": True
    },

    "Why is Team Alpha consistently missing deadlines and what should we do?": {
        "complexity": "complex",
        "required_models": ["trajectory", "complexity", "rework"],
        "requires_narrative": True
    }
}
```

#### PostgresML Integration Strategy

The routing system maximizes PostgresML usage by:

1. **Intelligent Model Selection**: Pre-analysis determines which PostgresML models to call
2. **Efficient Execution**: Only runs necessary models, not all models for every query
3. **Context-Aware Predictions**: ML predictions are contextualized within the business question
4. **Performance Optimization**: Simple queries bypass ML entirely for speed

```python
# PostgresML integration based on routing decisions
async def execute_ml_predictions_based_on_routing(self, state: StrategicAgentState):
    """Execute only the ML models identified during pre-analysis"""

    required_models = state["required_ml_models"]

    # Only call the models we actually need
    if "trajectory" in required_models:
        # Call PostgresML trajectory prediction
        trajectory_results = await self.db_client.execute("""
            SELECT pgml.predict('epic_trajectory_predictor',
                ARRAY[%s, %s, %s, %s]::FLOAT[]
            ) as predicted_days
        """, [story_count, total_points, team_velocity, complexity_score])

    if "complexity" in required_models:
        # Call PostgresML complexity estimation
        complexity_results = await self.db_client.execute("""
            SELECT pgml.predict('story_complexity_estimator',
                ARRAY[%s, %s, %s, %s]::FLOAT[]
            ) as predicted_points
        """, [description_length, criteria_count, component_complexity, team_avg])

    # This approach is much more efficient than calling all models for every query
```

#### Benefits of This Approach

1. **Immediate Sophistication**: Smart routing from day one without training data
2. **Data Collection**: Every query builds the dataset for future ML classifier
3. **Cost Optimization**: Uses cheap models for routing, expensive models only when needed
4. **Performance**: Simple queries stay fast, complex queries get full treatment
5. **Future-Proof**: Seamless migration to dedicated classifier in Phase 7

This strategy gives us **sophisticated behavior immediately** while building the **data asset for future optimization** - the best of both worlds!

    def __init__(self, db_client, ml_client, validation_client):
        self.db_client = db_client
        self.ml_client = ml_client
        self.validation_client = validation_client
        self.query_classifier = QueryComplexityClassifier(db_client)

        # Initialize LlamaIndex components
        self.sql_database = SQLDatabase(db_client.engine)
        self.service_context = ServiceContext.from_defaults(
            callback_manager=CallbackManager([self._feedback_callback])
        )

        # Create tools for the agent
        self.sql_tool = self._create_sql_tool()
        self.ml_tools = self._create_ml_tools()
        self.validation_tool = self._create_validation_tool()

        # Initialize the agent with all tools
        self.agent = OpenAIAgent.from_tools(
            [self.sql_tool, *self.ml_tools, self.validation_tool],
            service_context=self.service_context,
            verbose=True,
            system_prompt=self._get_system_prompt()
        )

    def _create_sql_tool(self) -> QueryEngineTool:
        """Create SQL query tool for LlamaIndex"""
        sql_engine = NLSQLTableQueryEngine(
            sql_database=self.sql_database,
            service_context=self.service_context,
            synthesize_response=True
        )

        return sql_engine.as_tool(
            name="sql_database",
            description="Use this tool to query the database for issues, pull requests, teams, and other development data. Always include client_id in WHERE clauses for multi-tenancy."
        )

    def _create_ml_tools(self) -> List[FunctionTool]:
        """Create ML prediction tools for LlamaIndex"""

        def predict_epic_trajectory(epic_key: str, client_id: int) -> Dict[str, Any]:
            """Predicts the completion timeline for a given Epic. Use for questions about deadlines, risks, or project forecasting."""
            return self.ml_client.predict_epic_trajectory(epic_key, client_id)

        def estimate_story_complexity(issue_key: str, client_id: int) -> Dict[str, Any]:
            """Estimates story point complexity for a given issue. Use for questions about effort estimation or capacity planning."""
            return self.ml_client.estimate_story_complexity(issue_key, client_id)

        def assess_rework_risk(pr_number: int, repository: str, client_id: int) -> Dict[str, Any]:
            """Assesses the risk of rework for a pull request. Use for questions about code quality or deployment risks."""
            return self.ml_client.assess_rework_risk(pr_number, repository, client_id)

        return [
            FunctionTool.from_defaults(fn=predict_epic_trajectory),
            FunctionTool.from_defaults(fn=estimate_story_complexity),
            FunctionTool.from_defaults(fn=assess_rework_risk)
        ]

    def _create_validation_tool(self) -> FunctionTool:
        """Create validation tool for LlamaIndex"""

        def validate_query_and_response(query: str, sql_query: str, response: str, client_id: int) -> Dict[str, Any]:
            """Validates SQL queries and responses for correctness and safety. Use before executing complex queries."""
            return self.validation_client.validate_query_and_response(query, sql_query, response, client_id)

        return FunctionTool.from_defaults(fn=validate_query_and_response)

    async def process_query(self, user_query: str, client_id: int, user_id: int = None) -> Dict[str, Any]:
        """Process user query through LlamaIndex orchestration"""

        # Classify query complexity for routing and monitoring
        classification = await self.query_classifier.classify_query(user_query, client_id)

        # Add client context to the query
        contextualized_query = f"""
        Client ID: {client_id}
        User Query: {user_query}

        Important: Always include 'client_id = {client_id}' in all SQL WHERE clauses for data isolation.
        Query Complexity: {classification['complexity']}
        """

        try:
            # Process through LlamaIndex agent
            response = await self.agent.achat(contextualized_query)

            # Extract metadata from the response
            metadata = {
                'query_complexity': classification['complexity'],
                'tools_used': self._extract_tools_used(response),
                'confidence_score': self._calculate_confidence(response),
                'processing_time_ms': response.metadata.get('processing_time', 0)
            }

            return {
                'response': str(response),
                'metadata': metadata,
                'client_id': client_id,
                'user_id': user_id,
                'timestamp': time.time()
            }

        except Exception as e:
            # Log error and return graceful failure
            await self._log_error(user_query, str(e), client_id, user_id)

            return {
                'response': "I encountered an error processing your query. Please try rephrasing your question or contact support if the issue persists.",
                'error': str(e),
                'metadata': {
                    'query_complexity': classification['complexity'],
                    'error_type': type(e).__name__
                },
                'client_id': client_id,
                'user_id': user_id,
                'timestamp': time.time()
            }

    def _get_system_prompt(self) -> str:
        """Get system prompt for the LlamaIndex agent"""
        return """
        You are an AI assistant specialized in software development analytics and business intelligence.

        Key Guidelines:
        1. ALWAYS include 'client_id = {client_id}' in SQL WHERE clauses for data isolation
        2. Use ML prediction tools for forecasting and risk assessment questions
        3. Validate complex queries before execution
        4. Provide business context and actionable insights
        5. Be conversational but professional
        6. If unsure, ask clarifying questions

        You have access to:
        - SQL database with development data (issues, PRs, teams, etc.)
        - ML models for trajectory prediction, complexity estimation, and risk assessment
        - Validation tools for query safety and correctness

        Always prioritize data accuracy and client isolation.
        """

    def _feedback_callback(self, event_type: str, payload: Dict[str, Any]):
        """Callback for collecting feedback and monitoring"""
        # This will be used for continuous learning and monitoring
        pass

    async def process_user_feedback(self, message_id: str, feedback: str, correction: str, client_id: int, user_id: int):
        """Process user feedback for continuous learning"""
        feedback_data = {
            'message_id': message_id,
            'feedback': feedback,
            'user_correction': correction,
            'client_id': client_id,
            'user_id': user_id,
            'timestamp': time.time()
        }

        # Store in ai_learning_memory for Phase 2 integration
        await self.db_client.execute("""
            INSERT INTO ai_learning_memory
            (query_text, response_text, error_type, correction_applied, user_feedback, client_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, [
            feedback_data.get('original_query', ''),
            feedback_data.get('original_response', ''),
            'user_feedback',
            correction,
            feedback,
            client_id
        ])

        return {'status': 'feedback_processed', 'message_id': message_id}
```
    
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

1. **Hybrid Architecture**: LangGraph workflow orchestration with LlamaIndex tool intelligence operational
2. **Intelligent Routing**: LLM-based query classification achieving >90% accuracy in complexity assessment
3. **Performance Optimization**:
   - Simple queries: <3 seconds response time
   - Moderate queries: <8 seconds response time
   - Complex queries: <15 seconds response time
4. **ML Integration**: PostgresML predictions seamlessly integrated based on routing decisions
5. **User Feedback Loop**: Feedback processing and integration into ai_learning_memory functional
6. **Self-Healing**: Agent learns from failures and user corrections to improve future responses
7. **Query Coverage**: System handles 95% of business intelligence queries without errors
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
