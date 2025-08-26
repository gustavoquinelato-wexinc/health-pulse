---
type: "manual"
---

# AI Jira Integration Guidelines for AI Agents

**Essential guidance for AI assistants to integrate task management with Jira**

## 🔗 Overview

This guide provides instructions for AI agents to connect with Jira using environment credentials and synchronize task management with Jira epics, stories, and sub-tasks.

## 🔧 Configuration

### Environment Variables
The following Jira configuration is set in the root `.env` file:

```env
# Jira Authentication
JIRA_URL=https://wexinc.atlassian.net
JIRA_USERNAME=gustavo.quinelato@wexinc.com
JIRA_TOKEN=<your-api-token>

# Project Configuration
JIRA_PROJECT_KEY_FOR_AUGMENT_AGENT=BST
JIRA_TEAM_FIELD_FOR_AUGMENT_AGENT=Agile Team[Dropdown]
JIRA_TEAM_VALUE_FOR_AUGMENT_AGENT=Research & Innovation Team

# Workflow Configuration
JIRA_SUBTASK_WORKFLOW=Backlog,Development,Released
JIRA_STORY_WORKFLOW=Backlog,Refining,To Do,Development,Code review,Ready for Story Testing,Story Testing,Ready for Acceptance,Acceptance Testing,Ready for Production,Released
JIRA_EPIC_WORKFLOW=Backlog,Development,Deployed to Production,Released

# Resolution Configuration
JIRA_STORY_RESOLUTION_REQUIRED=true
JIRA_SUCCESS_RESOLUTION=Done
JIRA_ABANDONED_RESOLUTION=Won't Do
```

**Reference**: See root `.env` file for actual values and current configuration.

### API Authentication
- **Method**: Basic Authentication using JIRA_USERNAME + JIRA_TOKEN
- **Headers**:
  - `Authorization: Basic <base64(JIRA_USERNAME:JIRA_TOKEN)>`
  - `Content-Type: application/json`
  - `Accept: application/json`

## 🎯 Integration Workflow

### Core Integration Pattern
1. **Environment Setup**: Load Jira credentials from environment variables
2. **Issue Creation**: Create epics, stories, and sub-tasks with proper formatting
3. **Status Management**: Transition issues through configured workflows
4. **Comment Management**: Add formatted comments with progress updates
5. **Task Synchronization**: Keep task management system in sync with Jira status

### Jira Client Usage
Use the enhanced Jira client at `scripts/augment_jira_integration/jira_agent_client.py`:

```bash
# Create Epic
python scripts/augment_jira_integration/jira_agent_client.py create-epic \
  --title "Epic Title" \
  --description "Epic description with Jira markup" \
  --acceptance-criteria "BDD format criteria" \
  --story-points 8 \
  --risk-assessment "Risk details"

# Create Story
python scripts/augment_jira_integration/jira_agent_client.py create-story \
  --title "Story Title" \
  --description "Story description" \
  --parent EPIC-KEY \
  --acceptance-criteria "BDD format criteria" \
  --story-points 5

# Create Subtask
python scripts/augment_jira_integration/jira_agent_client.py create-subtask \
  --parent STORY-KEY \
  --title "Subtask Title" \
  --description "Simple checklist of tasks" \
  --story-points 3
```

## 🔄 Workflow Management

### Supported Workflows
The integration supports three issue type workflows:

- **Sub-task**: `Backlog → Development → Released`
- **Story/Task**: `Backlog → Refining → To Do → Development → Code review → Ready for Story Testing → Story Testing → Ready for Acceptance → Acceptance Testing → Ready for Production → Released`
- **Epic**: `Backlog → Development → Deployed to Production → Released`

### Workflow Validation
- **Automatic Validation**: All transitions are validated against configured workflows
- **Error Prevention**: Invalid transitions are blocked with clear error messages
- **Flexible Movement**: Can move forward or backward in workflow as needed

### Resolution Handling
- **Stories/Tasks**: Automatically apply resolution when transitioning to final states
- **Sub-tasks**: No resolution required (simpler workflow)
- **Success Resolution**: "Done" (configurable)
- **Abandoned Resolution**: "Won't Do" (configurable)

## 🔄 Task Management Synchronization

### Jira Integration Workflows

**Three Clear Workflow Paths:**
1. **jira-epic-flow**: Epic creation only
2. **jira-story-flow**: Story and subtask creation only (requires existing epic)
3. **jira-e2e-flow**: Complete epic → story → subtask workflow

#### End-to-End Flow (Epic → Story → Subtask)
For complete epic-to-subtask workflow with task execution, see:
- **📋 Complete Workflow**: `.augment/rules/jira_e2e_flow.md`
- **🎯 Usage**: Only when user explicitly mentions "jira-e2e-flow"
- **🔄 Pattern**: Epic Creation → Epic to Development → Story Creation → Subtask Creation → **Task Execution** → Documentation → Release
- **⚠️ Authority**: User-driven only - AI never suggests E2E workflow autonomously
- **🎯 Key Feature**: Your tasks execute in Phase 4 between Jira setup and documentation

#### Epic Creation Flow
For comprehensive epic creation with quality assessment, see:
- **📋 Complete Workflow**: `.augment/rules/jira_epic_flow.md`
- **🎯 Usage**: Only when user explicitly mentions "jira-epic-flow" or requests epic creation only
- **🔄 Pattern**: Quality Assessment → Epic Creation → Documentation
- **⚠️ Authority**: User-driven only - AI never suggests epic creation autonomously

#### Story and Task Flow Integration
For comprehensive Jira integration with task management (requires existing epic), see:
- **📋 Complete Workflow**: `.augment/rules/jira_story_flow.md`
- **🎯 Usage**: Only when user explicitly mentions "jira-story-flow"
- **🔄 Pattern**: Story Creation → Subtask Creation → Task Execution → Documentation

### Standard Task Management (Without Jira)
When AI agents use task management tools for complex work without Jira integration:

### **Task List and Subtask Description Guidelines**

**Task List Creation**:
- **Scope**: Include ALL steps from start to completion
- **Jira Workflows**: Include Jira creation, transitions, documentation, and release tasks
- **Implementation**: Include your actual technical work tasks
- **Documentation**: Include success summaries and completion notices

**Subtask Descriptions**:
- **Content**: Simple checklist of implementation tasks only
- **Include**: Technical work (database changes, code updates, API development, etc.)
- **Exclude**: Jira management tasks (creation, transitions, comments)
- **Exclude**: Objectives, acceptance criteria, definition of done
- **Format**: Simple numbered list: "# Task description"
- **Purpose**: Subtask is a checklist, not a comprehensive specification

**Subtask Comments**:
- **Content**: Simple completion summary with key deliverables
- **Avoid**: Excessive detail, comprehensive documentation
- **Focus**: Key results and deliverables only
- **Format**: Brief, focused summary without extensive formatting

- **Create comprehensive task lists** that include both Jira management and implementation work
- **Update task status** as work progresses through different phases
- **Maintain task-to-Jira synchronization** when using integrated workflows

## 🎨 Jira Formatting Standards

### Markup Guidelines
Use proper Jira markup for all descriptions and comments:

- **Headers**: `h2.` for main sections, `h3.` for subsections
- **Lists**: `#` for numbered lists, `*` for bullet points
- **Emphasis**: `*text*` for bold/italics
- **Code**: `{code}` blocks for code snippets

### Content Structure
- **Epics**: Comprehensive business objectives with acceptance criteria and risk assessment
- **Stories**: User-focused with WWW format and BDD acceptance criteria
- **Subtasks**: Simple checklists of implementation tasks only

## 🚨 Error Handling

### Common Issues and Solutions

#### Authentication Errors
- **Issue**: 401 Unauthorized
- **Solution**: Verify JIRA_USERNAME and JIRA_TOKEN in environment
- **Check**: Ensure API token has proper permissions

#### Workflow Transition Errors
- **Issue**: Invalid transition attempted
- **Solution**: Use `get-transitions` command to check valid transitions
- **Pattern**: Follow configured workflow sequences

#### Field Validation Errors
- **Issue**: Required fields missing or invalid
- **Solution**: Ensure all required fields are provided with correct data types
- **Reference**: Check Jira project configuration for required fields

### Error Recovery
- **Continue on Error**: Don't abandon entire workflow due to single failure
- **Report Status**: Provide clear summary of what succeeded vs. what failed
- **User Guidance**: Offer specific steps to resolve issues

## 🔐 Security Considerations

### Data Protection
- **Client Isolation**: All Jira operations must respect client_id filtering
- **Authentication**: Use secure token-based authentication
- **Audit Trails**: Maintain logs of all Jira operations

### Access Control
- **Permissions**: Ensure API token has minimal required permissions
- **Scope**: Limit access to specific projects and issue types
- **Monitoring**: Track API usage and detect anomalies

## 📊 Monitoring and Observability

### Performance Metrics
- **Response Times**: Track API call latencies
- **Success Rates**: Monitor successful vs. failed operations
- **Usage Patterns**: Analyze workflow usage and optimization opportunities

### Logging
- **Operation Logs**: Record all Jira API calls and responses
- **Error Logs**: Capture and analyze failure patterns
- **Audit Logs**: Maintain compliance and security audit trails

## 🎯 Best Practices

### Workflow Efficiency
- **Batch Operations**: Group related Jira operations when possible
- **Caching**: Cache frequently accessed data to reduce API calls
- **Validation**: Validate data before making API calls

### User Experience
- **Clear Feedback**: Provide informative success and error messages
- **Progress Updates**: Keep users informed of long-running operations
- **Documentation**: Maintain clear documentation of created items

### Maintenance
- **Regular Updates**: Keep Jira client and configurations up to date
- **Testing**: Regularly test workflows in staging environments
- **Backup**: Maintain backups of important configurations and data

Remember: Jira integration should enhance productivity while maintaining data integrity and security standards.
