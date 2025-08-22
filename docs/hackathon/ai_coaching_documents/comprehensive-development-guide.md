# Comprehensive Development Guide - AI Orchestrator Hackathon

## 🎯 Mission Statement

We are building a **Strategic Business Intelligence AI Platform** for software development managers that connects technical development metrics to business outcomes. The platform provides:

1. **Tech-Business Alignment**: Identify sensitive/complex codebase areas causing business delays
2. **Corporate Outcome Tracking**: Visibility into Product Innovation Velocity, test coverage, AI adoption, API-first progress
3. **Strategic Decision Support**: Data-driven insights for resource allocation and process optimization
4. **Predictive Analytics**: Early warning systems for project risks and quality issues

This goes far beyond traditional DORA metrics to provide strategic insights that drive business decisions.

## 🚨 Critical Hackathon Context - Always Remember

### 1. 3-Day Hackathon Timeline
- **Aggressive "All-In" Approach**: We build everything in 3 days
- **No Phased Development**: All 24 tables from Day 1
- **Parallel Team Development**: Multiple team members working simultaneously
- **Proof of Concept Focus**: Demonstrate advanced capabilities, not production-ready system

### 2. All 24 Tables Required
- **Complete Dataset Needed**: Our demo scenarios require cross-table insights
- **No Shortcuts**: The power is in the comprehensive data combinations
- **Advanced Analytics**: Beyond standard metrics to qualitative insights
- **Management Decision Support**: Tool designed for dev manager insights

### 3. Team Coordination Strategy
- **`gus_` Prefix**: ALL new endpoints must use `gus_` prefix to prevent merge conflicts
- **Clear API Contracts**: Well-defined interfaces for parallel development
- **Independent Work**: Each team member can work on different components simultaneously

## 🏗️ Architecture Overview

### 3-Layer RAG Architecture
```
Frontend Layer (Port 3000)
    ↓ POST /ai/chat
AI Layer - LangGraph (Port 5002) [REASONING ENGINE]
    ↓ gus_ prefixed endpoints only
Backend Layer (Port 3001) [DATA ACCESS ONLY]
    ↓ All 24 tables with vector columns
PostgreSQL + pgvector (Port 5434)
```

### Core Principles
1. **AI-First Reasoning**: LangGraph handles all analysis, interpretation, and insights
2. **Generic Backend**: Backend provides only raw data access via `gus_` endpoints
3. **All 24 Tables**: Complete dataset vectorized from Day 1
4. **Intelligent Context Selection**: Pre-analysis prevents context explosion
5. **Advanced Analytics**: Qualitative insights and complex data combinations

## 📊 Strategic Business Intelligence Capabilities

### 1. Sensitive/Complex Areas Identification
- **High-Impact Problem Areas**: Which parts of the application slow down feature delivery?
- **Post-Release Rework Analysis**: Which features consistently require rework after release?
- **Test Coverage vs. Churn**: Areas with high churn and low test coverage?
- **Engineering Effort Allocation**: Where is the team spending most time & effort?

### 2. Corporate Outcome Tracking
- **Product Innovation Velocity (PIV)**: Epic lead time trends and trajectory
- **Test Coverage Progress**: Group of repos, changes by team within time period
- **AI Adoption Tracking**: Team and individual AI tool usage patterns
- **API-First Progress**: Percentage of APIs adhering to OpenAPI specs
- **Project Trajectory**: Realistic completion predictions based on historical data

### 3. Advanced Business Intelligence
- **Quality vs. Velocity Balance**: Maintaining quality while increasing delivery speed
- **Resource Optimization**: Alignment between effort and business priorities
- **Predictive Analytics**: Early warning systems for project delays and quality issues
- **Strategic Decision Support**: Data-driven insights for executive decision-making

## 🛠️ Implementation Strategy

### Day 1: Complete Foundation (8 hours)
**All 24 Tables Setup:**
- Vector columns for every table
- HNSW indexes for performance
- Structured text embedding templates
- All `gus_` prefixed endpoints

### Day 2: Advanced AI Analytics (8 hours)
**Sophisticated Cross-Table Analysis with WEX AI Gateway:**
- LangGraph agent with WEX AI Gateway integration
- GPT-4o for complex strategic business analysis
- GPT-4o-mini for fast classification and pre-analysis
- Complex data combination analytics using enterprise AI models
- Executive-level insight generation and strategic recommendations

### Day 3: Demo Scenarios (8 hours)
**Compelling Management Use Cases:**
- Developer leadership identification
- Project health predictions
- Workflow optimization recommendations
- Team collaboration analysis

## 🔧 Technical Implementation

### Backend Endpoints (All `gus_` prefixed)
1. **`POST /api/gus_semantic_search`** - Multi-table vector search
2. **`POST /api/gus_structured_query`** - Execute AI-generated SQL
3. **`POST /api/gus_table_metadata`** - Schema and relationship info
4. **`POST /api/gus_advanced_analytics`** - Complex cross-table analytics

### AI Layer Components with WEX AI Gateway
1. **Pre-Analysis**: Intelligent table group selection using `azure-gpt-4o-mini`
2. **Semantic Search**: Targeted multi-table search with `azure-text-embedding-3-small`
3. **Strategic AI Reasoning**: Comprehensive business analysis using `bedrock-claude-sonnet-4-v1`
4. **Response Generation**: Executive-focused recommendations using `bedrock-claude-sonnet-4-v1`

### WEX AI Gateway Integration
- **Base URL**: `https://aips-ai-gateway.ue1.dev.ai-platform.int.wexfabric.com/`
- **🏆 Primary Model**: `bedrock-claude-sonnet-4-v1` for strategic business intelligence
- **🚀 Secondary Model**: `azure-gpt-4o-mini` for classification and simple tasks
- **🔍 Embedding Model**: `azure-text-embedding-3-small` for vector generation
- **💎 Premium Model**: `bedrock-claude-opus-4-v1` for maximum intelligence when needed
- **Security**: Enterprise-grade security and compliance through WEX gateway
- **Same Family**: Claude Sonnet 4 - same model family as this conversation!

### All 24 Tables with Structured Embeddings
- **Core Business**: issues, projects, users, clients
- **Development**: pull_requests, commits, reviews, comments, repositories
- **Workflow**: workflows, statuses, changelogs, mappings, hierarchies
- **Benchmarks**: dora_market_benchmarks, dora_metric_insights
- **Relationships**: jira_pull_request_links, junction tables
- **Organizational**: users, permissions, sessions

## 🎯 Strategic Demo Scenarios for Business Leaders

### Scenario 1: Problem Area Identification
**Query**: "Which parts of the application are most frequently reworked or debugged by developers and are slowing down feature delivery?"
**Business Value**: Identify high-cost technical debt areas for strategic refactoring investment
**Showcases**: Cross-table analysis, cost-benefit analysis, strategic prioritization

### Scenario 2: Corporate Outcome Tracking
**Query**: "What progress have we made on Health directives such as PIV, automated test coverage, and AI adoption?"
**Business Value**: Executive visibility into strategic initiative progress
**Showcases**: Multi-metric tracking, trend analysis, benchmark comparison

### Scenario 3: Resource Optimization
**Query**: "Where is our engineering team spending most time & effort, and is it aligned with business priorities?"
**Business Value**: Optimize resource allocation for maximum business impact
**Showcases**: Effort analysis, business alignment assessment, reallocation recommendations

### Scenario 4: Quality vs. Velocity Balance
**Query**: "Are we maintaining quality while increasing delivery velocity, and what's our trajectory?"
**Business Value**: Ensure sustainable delivery pace without compromising quality
**Showcases**: Quality-velocity correlation, sustainability analysis, predictive modeling

### Scenario 5: Project Risk Assessment
**Query**: "How is our project trending and what does our timeline look like based on current patterns?"
**Business Value**: Early warning system for project delays and resource needs
**Showcases**: Predictive analytics, risk assessment, timeline forecasting

## ⚡ Success Criteria

### Technical Success
- All 24 tables vectorized and searchable
- Pre-analysis working to prevent context explosion
- Complex cross-table queries executing successfully
- AI generating meaningful insights and recommendations

### Demo Success
- Compelling scenarios that showcase advanced capabilities
- Clear value proposition for development managers
- Insights that aren't possible with traditional tools
- Smooth end-to-end user experience

### Team Success
- Parallel development working without conflicts
- `gus_` prefixed endpoints preventing merge issues
- Clear API contracts enabling independent work
- All components integrating successfully

## 🚨 Key Reminders for AI Agents

When working on this project, always remember:

1. **3-Day Hackathon**: Aggressive timeline, all-in approach
2. **All 24 Tables**: Complete dataset required for advanced analytics
3. **`gus_` Prefix**: All new endpoints must use this prefix
4. **Management Focus**: Tool designed for dev manager decision-making
5. **Advanced Analytics**: Beyond metrics to qualitative insights
6. **Cross-Table Intelligence**: The power is in data combinations
7. **Parallel Development**: Support team coordination and independent work

## 📋 Quick Reference

### Table Groups
- **CORE_BUSINESS**: issues, projects, users, clients
- **DEVELOPMENT**: pull_requests, commits, reviews, comments, repositories
- **WORKFLOW**: workflows, statuses, changelogs, mappings, hierarchies
- **BENCHMARKS**: dora_market_benchmarks, dora_metric_insights
- **RELATIONSHIPS**: jira_pull_request_links, junction tables
- **ORGANIZATIONAL**: users, permissions, sessions

### Endpoint Pattern
- All new endpoints: `/api/gus_[endpoint_name]`
- Request/Response models: `Gus[Name]Request/Response`
- Service functions: `gus_[function_name]`

### AI Analysis Flow
1. **Pre-Analysis**: Select relevant table groups
2. **Semantic Search**: Multi-table vector search
3. **Structured Query**: Additional data if needed
4. **AI Reasoning**: Generate insights and recommendations
5. **Response**: Management-focused output

---

*This guide ensures all AI agents working on this project understand the hackathon context, technical requirements, and team coordination needs.*
