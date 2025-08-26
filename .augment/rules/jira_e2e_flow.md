---
type: "manual"
---

# Jira End-to-End Flow (Epic → Story → Subtask)

**Complete workflow for AI agents when explicitly instructed to follow jira-e2e-flow**

## 🎯 When to Use This Rule

This rule should be followed **ONLY** when the user explicitly mentions "jira-e2e-flow" or requests complete epic-to-subtask workflow.

**E2E Authority**: The user will explicitly ask when they need the complete end-to-end workflow. This combines epic creation, story development, and task execution in one comprehensive flow.

**Create vs Update**: User will specify whether to create new Jira items or update existing ones. When user provides existing epic/story keys, use update commands instead of create commands.

**This is the COMPLETE workflow** - from epic creation through task execution to final documentation and release.

## 🔄 Complete End-to-End Workflow

When instructed to follow jira-e2e-flow, AI agents must execute this exact sequence:

### **FIRST: Create Comprehensive Task List**
**BEFORE starting any phases**, create complete task list including ALL steps from Phase 0 through Phase 5:
- **Phase 0 tasks**: Environment validation, coaching document review, content preparation
- **Phase 1 tasks**: Epic creation, epic validation, epic transition to Development
- **Phase 2 tasks**: Task list validation (already complete at this point)
- **Phase 3 tasks**: Story creation, story transitions, subtask creation
- **Phase 4 tasks**: Your actual technical implementation work (5+ tasks)
- **Phase 5 tasks**: Success summaries, completion notices, subtask release, inform user of tickets

### **Phase 0: Quality Assurance & Pre-Flight Validation**
**CRITICAL**: Validate everything BEFORE creating any Jira items

1. **Environment Check**: Confirm all required environment variables are loaded
   - JIRA_URL, JIRA_USERNAME, JIRA_TOKEN
   - JIRA_PROJECT_KEY_FOR_AUGMENT_AGENT
   - JIRA_TEAM_FIELD_FOR_AUGMENT_AGENT, JIRA_TEAM_VALUE_FOR_AUGMENT_AGENT
   - All workflow configurations

2. **Epic Quality Review**: Read and apply epic health coaching guidelines
   - Review `/docs/ai_agent_assets/jira_guidelines/wex_epic_health_coach.md`
   - Review `/docs/ai_agent_assets/jira_guidelines/wex_epic_rating_coach.md`
   - Review `/docs/ai_agent_assets/jira_guidelines/wex_work_decomposition.md`
   - Ensure epic qualifies as Product Innovation
   - Target 8+ quality score for story points field

3. **Story Quality Review**: Read and apply story health coaching guidelines
   - Review `/docs/ai_agent_assets/jira_guidelines/wex_story_health_coach.md`
   - Ensure story follows WWW (Who, What, Why) format
   - Validate story meets INVEST criteria
   - Prepare BDD-format acceptance criteria

4. **Content Preparation**: Prepare all components with proper Jira formatting
   - Epic: title, description, acceptance criteria, risk assessment, quality score
   - Story: title, description, acceptance criteria, story points
   - Subtask: title, description, task breakdown
   - Task list: comprehensive breakdown for implementation

5. **Abort on Validation Failure**: If ANY validation fails:
   - STOP immediately - do not create any Jira items
   - Report specific validation errors to user
   - Request user to resolve issues before proceeding

### **Phase 1: Epic Creation & Setup**
6. **Create or Update Epic**: Create new epic or update existing epic with all enhanced fields and proper formatting

   **Create New Epic:**
   ```bash
   python scripts/augment_jira_integration/jira_agent_client.py create-epic \
     --title "[Epic Title - Business-Focused]" \
     --description "[Comprehensive epic description with h2. headers and # numbered lists]" \
     --acceptance-criteria "[BDD format acceptance criteria with h3. headers]" \
     --story-points [QUALITY_SCORE_8_PLUS] \
     --risk-assessment "[Detailed risk assessment with h2./h3. headers and # numbered lists]" \
     --assignee "[USERNAME]"
   ```

   **Update Existing Epic (when user provides epic key):**
   ```bash
   python scripts/augment_jira_integration/jira_agent_client.py update-epic \
     --issue [EPIC_KEY] \
     --title "[Updated Epic Title]" \
     --description "[Updated epic description]" \
     --acceptance-criteria "[Updated acceptance criteria]" \
     --story-points [UPDATED_QUALITY_SCORE] \
     --risk-assessment "[Updated risk assessment]" \
     --assignee "[USERNAME]"
   ```

   **Note**: User will specify whether to create new or update existing epic

7. **Transition Epic to Development**: Move epic to active development status
   ```bash
   python scripts/augment_jira_integration/jira_agent_client.py transition \
     --issue [EPIC_KEY] --status "Development"
   ```

### **Phase 2: Task List Validation**
8. **Validate Task List**: Ensure comprehensive task list was created before Phase 0
   - **Verify ALL phases included**: Phase 0 (validation), Phase 1 (epic), Phase 3 (story/subtask), Phase 4 (implementation), Phase 5 (documentation)
   - **Confirm task quality**: Each task represents meaningful work (~20 minutes each)
   - **Task list should already be complete** from the FIRST step before starting phases

### **Phase 3: Story Creation & Setup**
10. **Create or Update Story**: Create new story or update existing story under the epic with proper formatting

    **Create New Story:**
    ```bash
    python scripts/augment_jira_integration/jira_agent_client.py create-story \
      --title "[Story Title following WWW format]" \
      --description "[Comprehensive story description with h2. headers]" \
      --parent [EPIC_KEY] \
      --acceptance-criteria "[BDD format acceptance criteria]" \
      --story-points [ESTIMATED_POINTS] \
      --assignee "[USERNAME]"
    ```

    **Update Existing Story (when user provides story key):**
    ```bash
    python scripts/augment_jira_integration/jira_agent_client.py update-story \
      --issue [STORY_KEY] \
      --title "[Updated Story Title]" \
      --description "[Updated story description]" \
      --acceptance-criteria "[Updated acceptance criteria]" \
      --story-points [UPDATED_POINTS] \
      --assignee "[USERNAME]"
    ```

    **Note**: User will specify whether to create new or update existing story

11. **Transition Story to Development**: Move story to active development status
    ```bash
    python scripts/augment_jira_integration/jira_agent_client.py transition \
      --issue [STORY_KEY] --status "Development"
    ```

12. **Create Consolidation Subtask**: Create single subtask containing implementation task checklist only
    ```bash
    python scripts/augment_jira_integration/jira_agent_client.py create-subtask \
      --parent [STORY_KEY] \
      --title "[Descriptive subtask title]" \
      --description "[Simple checklist of implementation tasks only - no objectives, acceptance criteria, or definition of done]" \
      --assignee "[USERNAME]"
    ```

    **IMPORTANT**: Subtask description should be a simple checklist of your implementation tasks only:
    - Include ONLY technical implementation work (database changes, code updates, etc.)
    - Exclude Jira management tasks (creation, transitions, comments)
    - Exclude objectives, acceptance criteria, definition of done
    - Use simple numbered list format: "# Task description"

### **Phase 4: Implementation (Your Tasks Execute Here)**
13. **Execute Your Tasks**: Perform all your planned implementation work
    - **THIS IS WHERE YOUR ACTUAL WORK HAPPENS**
    - Follow your task list systematically
    - Update task management as you progress
    - Mark each task as complete as you work through them
    - Can be actual implementation or simulated based on context

14. **Update Task Management**: Mark each task as complete as you progress through implementation

### **Phase 5: Completion & Documentation**
15. **Add Success Summary to Subtask**: Add simple completion comment with key results
    ```bash
    python scripts/augment_jira_integration/jira_agent_client.py comment \
      --issue [SUBTASK_KEY] \
      --message "[Simple completion summary with key deliverables - avoid excessive detail]"
    ```

16. **Add Completion Notice to Story**: Notify parent story of subtask completion
    ```bash
    python scripts/augment_jira_integration/jira_agent_client.py comment \
      --issue [STORY_KEY] \
      --message "h2. ✅ Subtask Completed Successfully

    *[Task description] subtask has been completed and released:*

    *Subtask*: [SUBTASK_KEY] - [Subtask Title]
    *Status*: ✅ *RELEASED*

    h3. Summary of Completed Work
    # [Clean numbered list of all completed tasks]
    # [Key deliverables and outcomes]
    # [Any important notes or follow-up items]"
    ```

17. **Release Subtask**: Mark subtask as complete
    ```bash
    python scripts/augment_jira_integration/jira_agent_client.py transition \
      --issue [SUBTASK_KEY] --status "Released"
    ```

18. **Inform User of Created Jira Tickets**: Provide summary of all created Jira items
    - **Epic**: [EPIC_KEY] - [Epic Title]
    - **Story**: [STORY_KEY] - [Story Title]
    - **Subtask**: [SUBTASK_KEY] - [Subtask Title]
    - **URLs**: Provide clickable links to all created items

## 🚨 Critical Requirements

### **Epic Quality Standards**
- All epics must qualify as Product Innovation per coaching guidelines
- Epic must achieve 8+ quality score (reflected in story points field)
- Must include comprehensive acceptance criteria in BDD format
- Must include detailed risk assessment with mitigation plans
- Epic must be transitioned to Development status

### **Story Quality Standards**
- All stories must follow WWW (Who, What, Why) format
- Stories must meet INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable)
- Acceptance criteria must be in BDD format in customfield_10222
- Story must be transitioned to Development status

### **Task Integration Requirements**
- **Phase 2 Task List**: Must include ALL steps from Jira creation through completion
- **Phase 4 is YOUR WORK**: This is where you execute your actual implementation tasks
- **Task List Scope**: Include Jira management + implementation + documentation tasks
- **Subtask Description**: Simple checklist of implementation tasks only (no Jira tasks, no objectives/AC/DoD)
- **Task Management**: Update task list throughout entire workflow
- Each task should represent ~20 minutes of meaningful work
- Tasks can be actual implementation or simulated based on context

### **Error Handling**
- If any Jira operation fails, continue with remaining tasks but report failures
- Provide clear summary of what succeeded vs. what failed
- Do not abandon entire workflow due to single failure
- Epic key and story key must be captured for subsequent operations

### **Formatting Standards**
- Use proper Jira markup formatting (h2., h3., #, *) throughout
- Format comments with proper numbered lists/bullet points
- Professional documentation standards for all Jira items

## 📋 Workflow Integration Points

### **Phase Flow Structure**
```
Phase 0: Validation (Epic + Story coaching documents)
Phase 1: Epic Creation + Transition to Development
Phase 2: Task List Setup
Phase 3: Story + Subtask Creation
Phase 4: YOUR TASK EXECUTION ← This is where your work happens
Phase 5: Documentation + Release
```

### **Task Execution Clarity**
- **Before Phase 4**: All Jira setup is complete, task list is ready
- **During Phase 4**: You execute your actual implementation work
- **After Phase 4**: Documentation and release activities

### **Integration with Existing Rules**
This rule is a COMPLETE workflow that integrates:
- **Epic Creation**: Quality assessment and creation with 8+ score
- **Story Creation**: WWW/INVEST compliance with BDD acceptance criteria
- **Task Execution**: Your actual implementation work in Phase 4
- **Quality Standards**: All coaching documents from `/docs/ai_agent_assets/jira_guidelines/`

## 📈 Success Criteria

A successful jira-e2e-flow execution includes:
- ✅ All validation steps completed successfully
- ✅ Epic created with 8+ quality score and transitioned to Development
- ✅ Story created with WWW/INVEST compliance and transitioned to Development
- ✅ Subtask created with comprehensive task breakdown
- ✅ **All implementation tasks completed successfully**
- ✅ Professional documentation added to both subtask and story
- ✅ Subtask released with proper status transition
- ✅ Clear summary provided of all completed work across epic, story, and subtask levels

## 🎯 E2E Workflow Authority and Usage

**IMPORTANT**: This is the COMPLETE end-to-end workflow. AI agents should:
- ✅ **Execute ALL phases** when "jira-e2e-flow" is triggered
- ✅ **Never skip phases** - this is a complete workflow from epic to release
- ✅ **Integrate task execution** in Phase 4 - this is where your actual work happens
- ✅ **Provide comprehensive documentation** across epic, story, and subtask levels
- ❌ **Never autonomously suggest** E2E workflow - user must explicitly request
- ❌ **Never partial execution** - if triggered, complete the entire workflow

This is the ALL-IN workflow for complete epic-to-subtask implementation with task execution.
