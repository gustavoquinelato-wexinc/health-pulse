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
JIRA_PROJECT_KEY_FOR_AUGMENT_AGENT=BEN

# Dual Team Field Configuration (2025-10-02 Update)
JIRA_AGILE_TEAM_FIELD_FOR_AUGMENT_AGENT=customfield_10128
JIRA_AGILE_TEAM_VALUE_FOR_AUGMENT_AGENT=R&I
JIRA_TEAM_FIELD_FOR_AUGMENT_AGENT=customfield_10001
JIRA_TEAM_UUID_FOR_AUGMENT_AGENT=0234170d-98f3-4e52-8e47-bd46a1772e12

# QP Planning Session Configuration
JIRA_QP_PLANNING_SESSION_FIELD_FOR_AUGMENT_AGENT=customfield_10501
JIRA_QP_PLANNING_SESSION_VALUE_FOR_AUGMENT_AGENT=["2025 Q4"]

# WEX T-Shirt Size Configuration (Dynamic Calculation)
JIRA_TSHIRT_SIZE_FIELD_FOR_AUGMENT_AGENT=customfield_10412
JIRA_TEAM_SIZE_FOR_AUGMENT_AGENT=5
JIRA_TEAM_PRODUCTIVE_HOURS_PER_WEEK_FOR_AUGMENT_AGENT=30
JIRA_SPRINT_WEEKS_FOR_AUGMENT_AGENT=2
JIRA_TEAM_STORY_POINTS_PER_SPRINT_FOR_AUGMENT_AGENT=50

# Default Assignee Configuration
JIRA_ASSIGNEE_EMAIL_VALUE_FOR_AUGMENT_AGENT=gustavo.quinelato@wexinc.com

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

**Dual Team Field Configuration (Updated 2025-10-02)**:
- **Agile Team Field** (`JIRA_AGILE_TEAM_FIELD_FOR_AUGMENT_AGENT`): `customfield_10128` - Legacy team field
- **Team Field** (`JIRA_TEAM_FIELD_FOR_AUGMENT_AGENT`): `customfield_10001` - New team field
- **Team Values**: Both fields use the same team name (e.g., `R&I`) which resolves to the same ID
- **Usage**: Both fields are populated when creating stories and epics (not needed for subtasks)

**QP Planning Session Configuration**:
- **Field**: `JIRA_QP_PLANNING_SESSION_FIELD_FOR_AUGMENT_AGENT` = `customfield_10501`
- **Value**: `JIRA_QP_PLANNING_SESSION_VALUE_FOR_AUGMENT_AGENT` = `["2025 Q4"]` (JSON array format)
- **Usage**: Populated for stories and epics to track quarterly planning sessions

**Default Assignee Configuration**:
- **Field**: `JIRA_ASSIGNEE_EMAIL_VALUE_FOR_AUGMENT_AGENT` = `gustavo.quinelato@wexinc.com`
- **Usage**: Automatically assigns all created items (stories, epics, subtasks) to the specified user

**WEX T-Shirt Size Dynamic Calculation (Updated 2025-10-02)**:
- **Field**: `JIRA_TSHIRT_SIZE_FIELD_FOR_AUGMENT_AGENT` = `customfield_10412`
- **Calculation Method**: Automatically calculated based on epic scope and team capacity
- **Team Configuration**:
  - `JIRA_TEAM_SIZE_FOR_AUGMENT_AGENT` = `5` (number of developers)
  - `JIRA_TEAM_PRODUCTIVE_HOURS_PER_WEEK_FOR_AUGMENT_AGENT` = `30` (6h/day × 5 days)
  - `JIRA_SPRINT_WEEKS_FOR_AUGMENT_AGENT` = `2` (sprint duration)
  - `JIRA_TEAM_STORY_POINTS_PER_SPRINT_FOR_AUGMENT_AGENT` = `50` (team velocity)
- **Total Team Capacity**: 300 hours/sprint (5 × 30 × 2)
- **Algorithm**: Analyzes epic description, acceptance criteria, and risks for technical complexity
- **Dual Estimation**: Calculates both story points and hours, uses higher estimate for conservative planning
- **Size Mapping**: XXS (<0.5 sprints) to Jumbo (12+ sprints)
- **Usage**: Applied automatically to epics only during creation

**How Field Resolution Works**:
- The Jira client queries the Jira API to resolve team names to IDs
- Supports multiple field name formats: `name`, `title`, `value`, `displayName`
- Case-insensitive matching for better reliability
- Comprehensive debug output for troubleshooting

**✅ COMPLETED - Enhanced Field Integration (2025-10-02)**:
- **Enhancement**: Added support for dual team fields, dynamic T-shirt sizing, and team configuration
- **Fields Implemented**:
  - `customfield_10128` (Agile Team) - Legacy field with ID resolution
  - `customfield_10001` (Team) - Cross-project field with direct UUID
  - `customfield_10501` (QP Planning Session) - Quarterly planning with array format
  - `customfield_10412` (WEX T-Shirt Size) - Dynamic calculation based on scope and team capacity
- **Team Configuration**: Realistic productivity calculation (5 devs × 30h/week × 2 weeks = 300h/sprint)
- **Dynamic Sizing**: Intelligent scope analysis with dual estimation (story points + hours)
- **Default Assignee**: All items automatically assigned to configured user
- **Status**: Fully implemented and tested in jira_agent_client.py
- **Impact**: Epics and stories now populate all required custom fields with intelligent sizing
- **Test Results**: BEN-10365 (SM), BEN-10366 (XXS), BEN-10367 (SM) created with accurate T-shirt sizes

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
- **Format**: Use proper Jira markup with headers and numbered lists
  - Headers: `h3.` for section grouping
  - Lists: `#` for numbered items (NOT `1.`, `2.`, `-`)
  - Example:
    ```
    h3. Database Tasks
    # Add table to migration
    # Execute migration

    h3. API Tasks
    # Create endpoint
    # Add validation
    ```
- **Purpose**: Subtask is a checklist, not a comprehensive specification

**Subtask Comments**:
- **Content**: Simple completion summary with key deliverables
- **Avoid**: Excessive detail, comprehensive documentation
- **Focus**: Key results and deliverables only
- **Format**: Use proper Jira markup for readability
  - Headers: `h2.`, `h3.` (NOT markdown `##`, `###`)
  - Numbered lists: `#` (NOT `1.`, `2.`, `-`)
  - Bullet lists: `*` (NOT `-`)
  - Bold text: `*text*` (NOT `**text**`)
  - Organize with headers and lists for clarity

- **Create comprehensive task lists** that include both Jira management and implementation work
- **Update task status** as work progresses through different phases
- **Maintain task-to-Jira synchronization** when using integrated workflows

## 🎨 Jira Formatting Standards

### Markup Guidelines
**CRITICAL**: Always use proper Jira markup (NOT Markdown) for all descriptions and comments:

- **Headers**: `h2.` for main sections, `h3.` for subsections, `h4.` for sub-subsections
  - ❌ WRONG: `## Header`, `### Subheader`
  - ✅ CORRECT: `h2. Header`, `h3. Subheader`
- **Numbered Lists**: `#` at the start of each line
  - ❌ WRONG: `1. Item`, `2. Item`, `- Item`
  - ✅ CORRECT: `# Item`, `# Item`
- **Bullet Lists**: `*` at the start of each line
  - ❌ WRONG: `- Item`, `• Item`
  - ✅ CORRECT: `* Item`, `* Item`
- **Bold Text**: `*text*` for bold/italics
  - ❌ WRONG: `**text**`, `__text__`
  - ✅ CORRECT: `*text*`
- **Code Blocks**: `{code}` blocks for code snippets
  - ❌ WRONG: ` ```code``` `
  - ✅ CORRECT: `{code}code{code}`

**Example of Proper Jira Markup**:
```
h2. Main Section

*This is bold text*

h3. Subsection

# First numbered item
# Second numbered item
# Third numbered item

h3. Another Subsection

* First bullet point
* Second bullet point
* Third bullet point
```

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

#### Team Field Validation Errors
- **Issue**: `"Specify a valid value for Agile Team"` or team field errors
- **Root Cause**: Team field format mismatch or resolution failure
- **Solution**: Ensure team fields use correct format and values are resolvable
- **Current Status**: ✅ **RESOLVED** - Dual team field support implemented (2025-10-02)
- **Debug Commands**:
  ```bash
  # Test team field resolution
  python scripts/augment_jira_integration/jira_agent_client.py --debug create-story --title "Test" --description "Test" --parent BEN-10219
  ```
- **Expected Debug Output**:
  ```
  DEBUG - Resolved team 'R&I' to UUID: 21608
  DEBUG - Resolved agile team 'R&I' to ID: 21608
  DEBUG - Resolved QP planning '2025 Q4' to ID: 15832
  ```

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
