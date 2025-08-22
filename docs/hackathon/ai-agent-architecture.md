# 🤖 AI Agent Layer Architecture
*Comprehensive Guide to the Strategic Business Intelligence Agent*

## 📋 Table of Contents
1. [Overview & Philosophy](#overview--philosophy)
2. [Architecture Components](#architecture-components)
3. [Table Grouping Strategy](#table-grouping-strategy)
4. [LangGraph Workflow Engine](#langgraph-workflow-engine)
5. [AI Gateway Integration](#ai-gateway-integration)
6. [Memory & Context Management](#memory--context-management)
7. [Analysis & Synthesis Pipeline](#analysis--synthesis-pipeline)
8. [Query Complexity Examples](#query-complexity-examples)
9. [Performance Optimization](#performance-optimization)
10. [Future Enhancements](#future-enhancements)

---

## 🎯 Overview & Philosophy

### Core Mission
The AI Agent Layer transforms natural language business questions into comprehensive strategic insights by intelligently orchestrating data retrieval, analysis, and synthesis across 24+ database tables.

### Design Principles
- **Intelligence First**: AI decides the optimal query strategy, not hardcoded rules
- **Business Context**: Every response connects technical metrics to business outcomes
- **Conversation Continuity**: Maintains context across multi-turn conversations
- **Adaptive Complexity**: Scales from simple lookups to complex multi-step analysis
- **Transparency**: Shows SQL queries and data sources for full auditability

### Key Differentiators
- **Dynamic Workflow Planning**: AI plans its own execution steps
- **Semantic + Structured Hybrid**: Combines vector search with SQL analytics
- **Executive-Focused Output**: Transforms data into strategic recommendations
- **Multi-Model Architecture**: Uses optimal AI models for each task

---

## 🏗️ Architecture Components

### 1. Strategic Business Intelligence Agent (`StrategicBusinessIntelligenceAgent`)
**Location**: `services/gus_agent_ai/app/core/strategic_agent.py`

**Core Responsibilities**:
- Orchestrates the entire analysis workflow using LangGraph
- Manages conversation state and memory
- Coordinates between semantic search and structured queries
- Synthesizes findings into executive-ready insights

**Key Features**:
- **Dynamic Query Planning**: AI determines optimal execution strategy
- **Multi-Step Execution**: Can break complex queries into logical steps
- **Context Accumulation**: Builds comprehensive context from multiple data sources
- **Error Recovery**: Graceful handling of failed steps with fallback strategies

### 2. WEX AI Gateway Client (`WEXAIGatewayClient`)
**Location**: `services/gus_agent_ai/app/core/wex_ai_integration.py`

**Core Responsibilities**:
- Interfaces with multiple AI models through WEX AI Gateway
- Handles model selection based on task complexity
- Manages embeddings for semantic search
- Provides intelligent SQL generation and strategic analysis

**Model Usage Strategy**:
- **Pre-Analysis**: `azure-gpt-4o-mini` (fast classification)
- **Strategic Analysis**: `bedrock-claude-sonnet-4-v1` (deep reasoning)
- **SQL Generation**: `azure-gpt-4o-mini` (structured output)
- **Embeddings**: `azure-text-embedding-3-small` (semantic search)

### 3. Backend Integration Layer
**Location**: `services/backend/app/api/gus_endpoints.py`

**Core Responsibilities**:
- Provides secure database access with client isolation
- Implements semantic search across table groups with transaction isolation
- Executes AI-generated SQL with safety validation
- Manages table metadata and relationships with dynamic schema validation

---

## 📊 Table Grouping Strategy

### Improved Business-Aligned Grouping

#### 🏢 **CORE_BUSINESS** (Organizational Foundation)
```
clients          - Client organizations and settings
users           - Team members and their information
```
**Rationale**: Pure organizational data - "who we serve" and "who does the work"

#### 💻 **DEVELOPMENT** (Complete Development Lifecycle)
```
projects                - Project definitions and metadata
issues                 - Jira tickets, stories, bugs, tasks
issue_changelogs       - History of issue status changes
issuetypes            - Issue types (Story, Bug, Epic, etc.)
issuetype_mappings    - Issue type mappings between systems
issuetype_hierarchies - Parent-child relationships
repositories          - Git repositories and metadata
pull_requests         - GitHub/GitLab pull requests
pull_request_comments - Comments on pull requests
pull_request_reviews  - Code review data
pull_request_commits  - Commits within pull requests
```
**Rationale**: All development work and artifacts in one cohesive group

#### ⚙️ **WORKFLOW** (Process Definitions)
```
workflows        - Workflow steps and process definitions
statuses        - Available issue statuses (To Do, In Progress, Done)
status_mappings - Status mappings between systems
```
**Rationale**: Pure process definitions, separate from work items

#### 📈 **BENCHMARKS** (Industry Standards)
```
dora_market_benchmarks - Industry standard DORA metrics
dora_metric_insights   - DORA metric analysis and insights
```
**Rationale**: External benchmarking and performance standards

#### 🔗 **RELATIONSHIPS** (Data Connections)
```
jira_pull_request_links - Links between Jira issues and GitHub PRs
```
**Rationale**: Cross-system data relationships and integrations
**Note**: Junction tables are managed through structured queries for optimal performance

#### 👥 **ORGANIZATIONAL** (Access & Configuration)
```
user_permissions - User access permissions
user_sessions   - User login sessions
system_settings - System configuration settings
```
**Rationale**: System administration and access control

### Smart Table Selection Logic

The AI agent intelligently selects relevant table groups based on query analysis:

```python
# Query Pattern Examples
"What teams do we have?" 
→ DEVELOPMENT + WORKFLOW + RELATIONSHIPS
→ Gets: projects, issues, workflows, and their connections

"How are our DORA metrics?"
→ BENCHMARKS + DEVELOPMENT + WORKFLOW + RELATIONSHIPS  
→ Gets: benchmarks, development data, processes, and links

"Show me workflow efficiency"
→ WORKFLOW + RELATIONSHIPS
→ Gets: process definitions and their connections
```

---

## 🔄 LangGraph Workflow Engine

### Dynamic Workflow Architecture

The agent uses LangGraph to create adaptive, multi-step workflows that adjust based on query complexity and available data.

#### Core Workflow Nodes

1. **Query Planning** (`_intelligent_query_planning`)
   - Analyzes user query and conversation history
   - Determines optimal execution strategy
   - Plans dynamic steps based on complexity

2. **Semantic Search** (`_targeted_semantic_search`)
   - Performs vector similarity search across relevant table groups
   - Uses embeddings to find contextually relevant data
   - Filters by client_id and active records

3. **Dynamic Step Execution** (`_execute_planned_query_step`)
   - Executes planned query steps in sequence
   - Can loop for multi-step analysis
   - Handles step failures gracefully

4. **Strategic Analysis** (`_comprehensive_strategic_analysis`)
   - Synthesizes all gathered data
   - Applies business intelligence reasoning
   - Generates strategic insights and recommendations

5. **Response Generation** (`_generate_executive_response`)
   - Formats findings for executive consumption
   - Includes SQL transparency and data sources
   - Adapts format based on query type

#### Conditional Workflow Logic

```python
# Dynamic step execution with intelligent branching
workflow.add_conditional_edges(
    "execute_query_step",
    self._should_execute_next_step,
    {
        "execute_step": "execute_query_step",  # Loop for next step
        "analyze": "strategic_analysis"        # Proceed to analysis
    }
)
```

#### State Management

The workflow maintains comprehensive state across all steps:

```python
class StrategicAgentState(TypedDict):
    # Query planning
    query_plan: List[Dict[str, Any]]
    current_step_index: int
    
    # Data results
    all_query_results: List[Dict]
    sql_queries_executed: List[str]
    
    # Analysis results
    strategic_insights: Dict[str, Any]
    raw_ai_response: Optional[str]
    
    # Conversation context
    conversation_history: List[Dict[str, Any]]
    previous_analysis_results: Dict[str, Any]
```

---

## 🌐 AI Gateway Integration

### Multi-Model Strategy

The system leverages different AI models optimized for specific tasks:

#### Model Selection Logic
```python
# Fast classification and SQL generation
"azure-gpt-4o-mini": {
    "temperature": 0.1,
    "max_tokens": 2000,
    "use_cases": ["pre_analysis", "structured_query", "query_planning"]
}

# Deep strategic reasoning
"bedrock-claude-sonnet-4-v1": {
    "temperature": 0.3,
    "max_tokens": 4000,
    "use_cases": ["strategic_analysis", "executive_synthesis"]
}

# Semantic embeddings
"azure-text-embedding-3-small": {
    "dimensions": 1536,
    "use_cases": ["semantic_search", "context_similarity"]
}
```

#### Request Optimization
- **Parallel Processing**: Multiple AI calls when possible
- **Caching**: Embeddings and common responses cached
- **Fallback Strategies**: Graceful degradation when models unavailable
- **Performance Tracking**: Detailed metrics for optimization

### Prompt Engineering Strategy

#### Layered Prompt Architecture
1. **System Context**: Role definition and capabilities
2. **Business Context**: Client-specific information and priorities
3. **Data Context**: Actual database results and relationships
4. **Task Context**: Specific analysis requirements
5. **Output Format**: Structured response expectations

#### Example Strategic Analysis Prompt
```python
f"""
You are a strategic business intelligence analyst specializing in software development metrics.

CRITICAL ANALYSIS REQUIREMENTS:
1. MANDATORY: Use ONLY the actual database results provided
2. MANDATORY: Reference specific team names and numbers from the data
3. MANDATORY: Connect technical metrics to business outcomes
4. Focus on actionable executive recommendations

ACTUAL DATABASE RESULTS:
{comprehensive_data_context}

ANALYSIS INTENT: {analysis_intent}
BUSINESS PRIORITY: {business_priority}

Respond in executive-focused markdown format...
"""
```

---

## 🧠 Memory & Context Management

### Conversation Continuity

The agent maintains conversation state to enable natural follow-up questions:

#### Memory Architecture
```python
# Conversation memory structure
self.conversation_memory = {
    "conversation_id": {
        "history": [
            {
                "query": "What teams do we have?",
                "response": "Analysis of 7 teams...",
                "timestamp": 1234567890,
                "analysis_results": {...},
                "data_sources": [...]
            }
        ],
        "results": {
            "last_analysis": {...},
            "last_data_sources": [...],
            "last_query_results": [...]
        }
    }
}
```

#### Context Reuse Strategy
- **Smart Reuse**: Determines when previous results can answer new questions
- **Context Enhancement**: Builds on previous analysis for deeper insights
- **Progressive Analysis**: Each query adds to the knowledge base

#### Example Context Reuse
```python
# First query
"What teams do we have?" → Full team analysis

# Follow-up query (reuses previous data)
"Which team should we focus on?" → Uses cached team data for recommendations

# Enhanced query (builds on previous)
"How do they compare to industry benchmarks?" → Adds benchmark data to team analysis
```

### Context Building Pipeline

#### Multi-Source Context Assembly
1. **Conversation History**: Previous Q&A pairs and results
2. **Semantic Search Results**: Relevant data from vector search
3. **Structured Query Results**: Complete datasets from SQL queries
4. **Business Metadata**: Client priorities and business context
5. **Relationship Mapping**: Cross-table connections and dependencies

#### Context Optimization
- **Relevance Filtering**: Only includes pertinent historical data
- **Size Management**: Balances completeness with token limits
- **Structured Formatting**: Organizes context for optimal AI consumption

---

## 🔬 Analysis & Synthesis Pipeline

### Strategic Intelligence Framework

The agent transforms raw data into strategic insights through a sophisticated analysis pipeline:

#### Analysis Layers
1. **Data Validation**: Ensures data quality and completeness
2. **Pattern Recognition**: Identifies trends and anomalies
3. **Business Correlation**: Connects metrics to business outcomes
4. **Comparative Analysis**: Benchmarks against industry standards
5. **Predictive Insights**: Identifies risks and opportunities
6. **Strategic Synthesis**: Generates actionable recommendations

#### Business Intelligence Transformation

```python
# Raw Data → Strategic Insights Pipeline
Raw Metrics: "Team A: 71 PRs/member, Team B: 1.5 PRs/member"
↓
Pattern Analysis: "40x performance variance indicates process gaps"
↓
Business Impact: "Underutilization represents $X in lost productivity"
↓
Strategic Recommendation: "Scale Team A practices to unlock 25% efficiency gain"
```

#### Executive Response Framework

The agent structures responses for maximum executive impact:

1. **Executive Summary**: Key findings and business impact
2. **Strategic Opportunities**: Growth and optimization areas
3. **Risk Indicators**: Potential issues requiring attention
4. **Prioritized Recommendations**: Action items with timelines
5. **Supporting Data**: Metrics and evidence
6. **Implementation Guidance**: Next steps and success metrics

---

## 📝 Query Complexity Examples

### Simple Query Example

**User Input**: "How many issues do we have?"

**AI Processing**:
```python
# Query Planning
analysis_intent: "Issue count analysis"
table_groups: ["DEVELOPMENT"]
complexity: "simple"
steps: [
    {
        "type": "overview_query",
        "description": "Get total issue count",
        "estimated_records": "few"
    }
]

# SQL Generation
SELECT 
    COUNT(*) as total_issues,
    COUNT(DISTINCT team) as unique_teams,
    COUNT(DISTINCT project_id) as unique_projects
FROM issues 
WHERE client_id = :client_id AND active = true;

# Strategic Analysis
"Your organization currently manages 2,847 active issues across 7 teams and 12 projects, 
indicating a healthy development pipeline with distributed workload."
```

**Response Format**:
```markdown
## Issue Overview Analysis
**Total Active Issues**: 2,847
**Teams Involved**: 7
**Projects**: 12

### Key Insights
• Healthy issue distribution across teams
• Active development pipeline with good project coverage
• Average of 407 issues per team suggests balanced workload

### SQL Query Generated:
```sql
SELECT COUNT(*) as total_issues...
```
*Retrieved 1 record*
```

### Medium Query Example

**User Input**: "What can you tell me about the different teams in my database? List each of them and properly include your superficial analysis"

**AI Processing**:
```python
# Query Planning
analysis_intent: "Team performance analysis"
table_groups: ["DEVELOPMENT", "WORKFLOW", "RELATIONSHIPS"]
complexity: "moderate"
steps: [
    {
        "type": "overview_query",
        "description": "Get all teams overview",
        "estimated_records": "all"
    },
    {
        "type": "detailed_query", 
        "description": "Get team performance metrics",
        "estimated_records": "many"
    }
]

# Multi-Step SQL Execution
# Step 1: Team Discovery
SELECT DISTINCT 
    i.team,
    COUNT(DISTINCT i.assignee) as team_size,
    COUNT(i.id) as total_issues
FROM issues i
WHERE i.client_id = :client_id AND i.active = true
GROUP BY i.team
ORDER BY team_size DESC;

# Step 2: Detailed Metrics
SELECT
    i.team,
    COUNT(DISTINCT i.assignee) as team_members,
    COUNT(i.id) as total_issues,
    COUNT(DISTINCT pr.id) as total_pull_requests,
    COUNT(DISTINCT r.name) as repositories_used
FROM issues i
LEFT JOIN jira_pull_request_links jpl ON i.id = jpl.issue_id AND jpl.active = true
LEFT JOIN pull_requests pr ON (jpl.external_repo_id = pr.external_repo_id 
    AND jpl.pull_request_number = pr.number AND pr.active = true)
LEFT JOIN repositories r ON pr.repository_id = r.id AND r.active = true
WHERE i.client_id = :client_id AND i.active = true
GROUP BY i.team
ORDER BY team_members DESC;
```

**Response Format**:
```markdown
## Strategic Analysis: Team Performance Overview

### Technocats: High-Performance Development Team
- **Team Size**: 19 members
- **Activity**: 3,745 issues, 1,348 pull requests
- **Key Insight**: Exceptional productivity with 71 PRs per member - industry-leading efficiency

### B-Positive: Balanced Performance Team  
- **Team Size**: 18 members
- **Activity**: 2,900 issues, 968 pull requests  
- **Key Insight**: Strong balanced performance with 54 PRs per member and consistent delivery

### Flash: Underutilized Capacity
- **Team Size**: 18 members
- **Activity**: 229 issues, 33 pull requests
- **Key Insight**: ⚠️ Concerning underutilization with only 1.8 PRs per member - significant optimization opportunity

## Executive Recommendations
**🔴 HIGH PRIORITY**: Conduct Flash team capacity audit and reallocate resources (Timeline: 30 days)
**🟡 MEDIUM PRIORITY**: Scale Technocats methodology across organization (Timeline: 60 days)
```

### Complex Query Example

**User Input**: "Analyze our development velocity trends over the last quarter, compare against DORA benchmarks, identify bottlenecks in our workflow, and provide strategic recommendations for improving our delivery pipeline with specific focus on cycle time optimization"

**AI Processing**:
```python
# Query Planning
analysis_intent: "Comprehensive development velocity and workflow optimization analysis"
table_groups: ["DEVELOPMENT", "WORKFLOW", "BENCHMARKS", "RELATIONSHIPS"]
complexity: "complex"
steps: [
    {
        "type": "trend_query",
        "description": "Analyze velocity trends over last quarter",
        "estimated_records": "many"
    },
    {
        "type": "comparison_query",
        "description": "Compare against DORA benchmarks", 
        "estimated_records": "all"
    },
    {
        "type": "detailed_query",
        "description": "Identify workflow bottlenecks",
        "estimated_records": "many"
    }
]

# Multi-Step Complex Analysis
# Step 1: Velocity Trends (Last 90 days)
SELECT 
    DATE_TRUNC('week', pr.created_at) as week,
    COUNT(pr.id) as prs_created,
    COUNT(pr.id) FILTER (WHERE pr.status = 'merged') as prs_merged,
    AVG(EXTRACT(EPOCH FROM (pr.merged_at - pr.created_at))/3600) as avg_cycle_time_hours
FROM pull_requests pr
WHERE pr.client_id = :client_id 
    AND pr.active = true 
    AND pr.created_at >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('week', pr.created_at)
ORDER BY week;

# Step 2: DORA Benchmark Comparison
SELECT 
    dmb.metric_name,
    dmb.elite_threshold,
    dmb.high_threshold,
    dmb.medium_threshold,
    dmb.low_threshold,
    dmi.current_value,
    dmi.trend_direction,
    dmi.percentile_rank
FROM dora_market_benchmarks dmb
JOIN dora_metric_insights dmi ON dmb.metric_name = dmi.metric_name
WHERE dmb.client_id = :client_id AND dmb.active = true;

# Step 3: Workflow Bottleneck Analysis
SELECT 
    ic.from_status,
    ic.to_status,
    COUNT(*) as transition_count,
    AVG(EXTRACT(EPOCH FROM (ic.changed_at - LAG(ic.changed_at) 
        OVER (PARTITION BY ic.issue_id ORDER BY ic.changed_at)))/86400) as avg_days_in_status
FROM issue_changelogs ic
JOIN issues i ON ic.issue_id = i.id
WHERE ic.client_id = :client_id 
    AND ic.active = true 
    AND ic.changed_at >= NOW() - INTERVAL '90 days'
GROUP BY ic.from_status, ic.to_status
HAVING COUNT(*) > 10
ORDER BY avg_days_in_status DESC;
```

**Response Format**:
```markdown
## 🎯 Strategic Analysis: Development Velocity & Pipeline Optimization

**Confidence Level**: 85.0%

## 📈 Quarterly Velocity Trends
• **PR Creation Rate**: Increased 23% from 45 to 55 PRs/week
• **Merge Rate**: Improved 18% with 89% merge success rate
• **Cycle Time**: Reduced from 4.2 to 3.1 days average (26% improvement)

## 🏆 DORA Benchmark Performance
• **Deployment Frequency**: HIGH tier (85th percentile) - 2.3 deployments/day
• **Lead Time**: MEDIUM tier (62nd percentile) - 3.1 days average
• **MTTR**: HIGH tier (78th percentile) - 2.4 hours average
• **Change Failure Rate**: ELITE tier (92nd percentile) - 2.1% failure rate

## ⚠️ Workflow Bottleneck Analysis
• **"In Review" → "Done"**: 2.8 days average (longest bottleneck)
• **"To Do" → "In Progress"**: 1.9 days average (planning delays)
• **"In Progress" → "In Review"**: 0.8 days average (efficient development)

## 🎯 Strategic Recommendations

**🔴 HIGH PRIORITY**: Optimize code review process to reduce 2.8-day bottleneck
- *Expected Impact*: 30% cycle time reduction
- *Timeline*: 45 days
- *Success Metric*: Review time < 1.5 days

**🟡 MEDIUM PRIORITY**: Implement automated planning workflows to reduce planning delays
- *Expected Impact*: 15% lead time improvement  
- *Timeline*: 60 days
- *Success Metric*: Planning time < 1 day

**🟢 LOW PRIORITY**: Maintain current development velocity while scaling review capacity
- *Expected Impact*: Sustained high performance
- *Timeline*: Ongoing
- *Success Metric*: Maintain 89% merge rate

## 📊 Predictive Insights
Based on current trends, implementing these optimizations could move your organization to ELITE tier across all DORA metrics within 6 months, representing a potential 40% improvement in overall delivery performance.

### SQL Queries Executed:
**Step 1 Query**: Velocity trend analysis
**Step 2 Query**: DORA benchmark comparison  
**Step 3 Query**: Workflow bottleneck identification

*Total Records Retrieved: 847*
```

---

## ⚡ Performance Optimization

### Query Optimization Strategies

1. **Intelligent Limiting**: No artificial LIMIT clauses - gets complete data when needed
2. **Table Group Filtering**: Only queries relevant table groups
3. **Client Isolation**: All queries filtered by client_id for security and performance
4. **Active Record Filtering**: Excludes deactivated records at query level
5. **Index Optimization**: Leverages database indexes for common query patterns
6. **Transaction Isolation**: Each table search uses isolated transactions to prevent blocking
7. **Schema Validation**: Dynamic column checking ensures compatibility across table structures

### AI Model Optimization

1. **Model Selection**: Uses optimal model for each task type
2. **Parallel Processing**: Multiple AI calls when possible
3. **Caching Strategy**: Caches embeddings and common responses
4. **Token Management**: Optimizes context size for cost and performance
5. **Fallback Strategies**: Graceful degradation when models unavailable

### Memory Management

1. **Conversation Pruning**: Keeps only relevant conversation history
2. **Result Caching**: Stores analysis results for reuse
3. **Context Optimization**: Balances completeness with performance
4. **Garbage Collection**: Cleans up old conversation data

---

## 🚀 Future Enhancements

### Planned Capabilities

1. **Advanced Analytics**
   - Predictive modeling for project outcomes
   - Anomaly detection in development patterns
   - Automated trend analysis and alerting

2. **Enhanced Memory**
   - Long-term organizational knowledge base
   - Cross-conversation learning and insights
   - Personalized analysis based on user preferences

3. **Workflow Automation**
   - Automated report generation
   - Scheduled analysis and alerts
   - Integration with project management tools

4. **Advanced Visualizations**
   - Dynamic chart generation
   - Interactive dashboards
   - Real-time metric monitoring

### Technical Roadmap

1. **Performance Scaling**
   - Distributed query processing
   - Advanced caching strategies
   - Real-time data streaming

2. **AI Capabilities**
   - Multi-modal analysis (text, code, metrics)
   - Advanced reasoning and planning
   - Continuous learning from feedback

3. **Integration Expansion**
   - Additional data source connectors
   - Third-party tool integrations
   - API ecosystem development

---

*This document represents the current state of the AI Agent Layer architecture. For implementation details, see the source code in `services/gus_agent_ai/`.*
