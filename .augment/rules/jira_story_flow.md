---
type: "manual"
---

# Jira Story Flow with Task Integration

**Standardized workflow for AI agents when explicitly instructed to follow jira-story-flow**

## 🎯 When to Use This Rule

This rule should be followed **ONLY** when the user explicitly mentions "jira-story-flow" or directly references this rule. 

**Two Clear Paths:**
1. **WITH jira-story-flow**: Follow this complete Jira integration workflow
2. **WITHOUT jira-story-flow**: Follow standard guidelines without Jira integration

## 🔄 Complete Workflow Pattern

When instructed to follow jira-story-flow, AI agents must execute this exact sequence:

### **FIRST: Create Comprehensive Task List**
**BEFORE starting any phases**, create complete task list including ALL steps from Phase 0 through Phase 4:
- **Phase 0 tasks**: Environment validation, coaching document review, content preparation
- **Phase 1 tasks**: Task list validation (already complete at this point)
- **Phase 2 tasks**: Story creation, story transitions, subtask creation
- **Phase 3 tasks**: Your actual technical implementation work (5+ tasks)
- **Phase 4 tasks**: Success summaries, completion notices, subtask release, inform user of tickets

### **Phase 0: Quality Assurance & Pre-Flight Validation**
**CRITICAL**: Validate everything BEFORE creating any Jira issues

1. **Epic Validation**: Verify the provided epic key exists and is accessible
   ```bash
   python scripts/augment_jira_integration/jira_agent_client.py get --issue [EPIC_KEY]
   ```

2. **Environment Check**: Confirm all required environment variables are loaded
   - JIRA_URL, JIRA_USERNAME, JIRA_TOKEN
   - JIRA_PROJECT_KEY_FOR_AUGMENT_AGENT
   - JIRA_TEAM_FIELD_FOR_AUGMENT_AGENT (e.g., customfield_10128)
   - JIRA_TEAM_VALUE_FOR_AUGMENT_AGENT (can be team name or numeric ID - auto-resolved by client)
   - Workflow configurations

   **Note**: The Jira client automatically resolves team names to IDs, so you can use either:
   - Team name: `Research & Innovation Team` (user-friendly, auto-resolved)
   - Numeric ID: `19601` (direct, no resolution needed)

3. **Workflow Validation**: Verify story workflow transitions are available
   ```bash
   # Test that we can create and transition stories
   python scripts/augment_jira_integration/jira_agent_client.py get-transitions --issue [ANY_EXISTING_STORY]
   ```

4. **Story Quality Review**: Read and apply story health coaching guidelines
   - Review `/docs/ai_agent_assets/jira_guidelines/wex_story_health_coach.md`
   - Ensure story follows WWW (Who, What, Why) format
   - Validate story meets INVEST criteria
   - Prepare BDD-format acceptance criteria

5. **Content Preparation**: Prepare all titles, descriptions, and task lists
   - Story title and comprehensive description following WWW format
   - Subtask title and detailed task breakdown
   - Success criteria and deliverables
   - BDD-format acceptance criteria for customfield_10222

6. **Abort on Validation Failure**: If ANY validation fails:
   - STOP immediately - do not create any Jira issues
   - Report specific validation errors to user
   - Request user to resolve issues before proceeding

### **Phase 1: Task List Validation**
1. **Validate Task List**: Ensure comprehensive task list was created before Phase 0
   - **Verify ALL phases included**: Phase 0 (validation), Phase 2 (story/subtask), Phase 3 (implementation), Phase 4 (documentation)
   - **Confirm task quality**: Each task represents meaningful work (~20 minutes each)
   - **Task list should already be complete** from the FIRST step before starting phases

### **Phase 2: Jira Integration**
3. **Create Story**: Create story under the provided epic with proper formatting
   ```bash
   python scripts/augment_jira_integration/jira_agent_client.py create-story \
     --title "[Story Title following WWW format]" \
     --description "[Comprehensive story description with h2. headers]" \
     --parent [EPIC_KEY] \
     --acceptance-criteria "[BDD format acceptance criteria]" \
     --story-points [ESTIMATED_POINTS]
   ```

4. **Transition Story to Development**: Move story to active development status
   ```bash
   python scripts/augment_jira_integration/jira_agent_client.py transition \
     --issue [STORY_KEY] --status "Development"
   ```

5. **Create Consolidation Subtask**: Create single subtask containing implementation task checklist only
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
   - Use Jira markup format with proper headers and lists:
     - Headers: `h2.`, `h3.`, `h4.` for section headers
     - Numbered lists: `#` at the start of each line (NOT `1.`, `2.`, etc.)
     - Bullet lists: `*` at the start of each line (NOT `-`)
     - Example:
       ```
       h3. Database Tasks
       # Add table to migration
       # Execute migration

       h3. API Tasks
       # Create endpoint
       # Add validation
       ```

### **Phase 3: Implementation**
6. **Execute Your Tasks**: Perform all your planned implementation work (can be simulated)
7. **Update Task Management**: Mark each task as complete as you progress

### **Phase 4: Completion & Documentation**
8. **Add Success Summary to Subtask**: Add simple completion comment with key results
   ```bash
   python scripts/augment_jira_integration/jira_agent_client.py comment \
     --issue [SUBTASK_KEY] \
     --message "[Simple completion summary with key deliverables - avoid excessive detail]"
   ```

   **IMPORTANT - Jira Markup Format**:
   - Use `h2.`, `h3.`, `h4.` for headers (NOT markdown `##`, `###`)
   - Use `#` for numbered lists (NOT `1.`, `2.`, etc.)
   - Use `*` for bullet lists (NOT `-`)
   - Always organize content with proper headers and lists for readability

9. **Add Completion Notice to Story**: Notify parent story of subtask completion
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

   **CRITICAL - Jira Markup Format**:
   - Headers: `h2.`, `h3.` (NOT markdown `##`, `###`)
   - Numbered lists: `#` at line start (NOT `1.`, `2.`, `-`)
   - Bullet lists: `*` at line start (NOT `-`)
   - Bold text: `*text*` (NOT markdown `**text**`)
   - This ensures proper formatting in Jira comments

10. **Release Subtask**: Mark subtask as complete
    ```bash
    python scripts/augment_jira_integration/jira_agent_client.py transition \
      --issue [SUBTASK_KEY] --status "Released"
    ```

11. **Transition Story to Code Review**: Move story from Development to Code Review
    ```bash
    python scripts/augment_jira_integration/jira_agent_client.py transition \
      --issue [STORY_KEY] --status "Code Review"
    ```

12. **Transition Story to Ready for Story Testing**: Move story from Code Review to Ready for Story Testing
    ```bash
    python scripts/augment_jira_integration/jira_agent_client.py transition \
      --issue [STORY_KEY] --status "Ready for Story Testing"
    ```

13. **Create Git Commit**: Make a git commit with the story key at the beginning of the commit message
    ```bash
    git add .
    git commit -m "[STORY_KEY] [Brief description of the work completed]"
    ```

    **IMPORTANT**: This step is ONLY for story items (not epics or subtasks). The story key at the beginning enables Jira-GitHub integration.

14. **Push Git Changes**: Push the committed changes to the current branch
    ```bash
    git push origin [current_branch]
    ```

    Replace `[current_branch]` with the actual current branch name. This ensures the Jira-GitHub integration can link the commit to the story.

15. **Inform User of Created Jira Tickets**: Provide summary of all created Jira items
    - **Story**: [STORY_KEY] - [Story Title]
    - **Subtask**: [SUBTASK_KEY] - [Subtask Title]
    - **URLs**: Provide clickable links to all created items

## 🚨 Critical Requirements

### **Epic Key Requirement**
- User MUST provide epic key (changes frequently)
- AI should ask for epic key if not provided
- Abort remaining Jira steps on error and report what succeeded/failed

### **Error Handling**
- If any Jira operation fails, continue with remaining tasks but report failures
- Provide clear summary of what succeeded vs. what failed
- Do not abandon entire workflow due to single failure

### **Story Quality Standards**
- All stories must follow WWW (Who, What, Why) format
- Stories must meet INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable)
- Acceptance criteria must be in BDD format in customfield_10222
- Use proper Jira markup formatting (h2., h3., #, *)

### **Task Management Integration**
- **Task List Scope**: Include ALL steps from Jira creation through completion
- **Subtask Description**: Simple checklist of implementation tasks only (no Jira tasks, no objectives/AC/DoD)
- **Task List Management**: Update task management system throughout entire workflow
- **Jira Markup Format**: ALWAYS use proper Jira markup in all comments and descriptions:
  - Headers: `h2.`, `h3.`, `h4.` (NOT markdown `##`, `###`, `####`)
  - Numbered lists: `#` at line start (NOT `1.`, `2.`, `-`)
  - Bullet lists: `*` at line start (NOT `-`)
  - Bold text: `*text*` (NOT markdown `**text**`)
  - Organize content with headers and lists for readability
- Always include initial steps (create story, transition to development, create consolidation subtask)
- Always include final steps (add summary comments to both subtask and parent story, release subtask)

### **Workflow Compliance**
- Follow exact sequence: Epic validation → Story creation → Story transition → Subtask creation → Implementation → Documentation → Release
- Use environment variable configurations for project and team fields
- Respect workflow transitions defined in environment variables

## 📋 Success Criteria

A successful jira-story-flow execution includes:
- ✅ All validation steps completed successfully
- ✅ Story created with proper WWW format and INVEST compliance
- ✅ Story transitioned to Development status
- ✅ Subtask created with comprehensive task breakdown
- ✅ All implementation work completed
- ✅ Professional documentation added to both subtask and story
- ✅ Subtask released with proper status transition
- ✅ Clear summary provided of all completed work

## 🔄 Integration with Other Rules

This rule integrates with:
- **AI Jira Integration Guidelines**: `.augment/rules/ai_jira_integration_guidelines.md`
- **Story Health Coach**: `/docs/ai_agent_assets/jira_guidelines/wex_story_health_coach.md`

When "jira-story-flow" is not mentioned, follow standard guidelines without Jira integration.
