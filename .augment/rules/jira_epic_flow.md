---
type: "manual"
---

# Jira Epic Flow with Quality Assessment

**Standardized workflow for AI agents when explicitly instructed to follow jira-epic-flow**

## 🎯 When to Use This Rule

This rule should be followed **ONLY** when the user explicitly mentions "jira-epic-flow" or directly requests epic creation. 

**Epic Creation Authority**: The user will explicitly ask when they need a new epic to be created. AI agents should NOT autonomously suggest or create epics.

**Two Clear Paths:**
1. **WITH jira-epic-flow**: Follow this complete epic creation and assessment workflow
2. **WITHOUT jira-epic-flow**: Follow standard guidelines without epic creation

## 🔄 Complete Epic Creation Workflow

When instructed to follow jira-epic-flow, AI agents must execute this exact sequence:

### **FIRST: Create Comprehensive Task List**
**BEFORE starting any phases**, create complete task list including ALL steps from Phase 0 through Phase 3:
- **Phase 0 tasks**: Environment validation, coaching document review, content preparation
- **Phase 1 tasks**: Task list validation (already complete at this point)
- **Phase 2 tasks**: Epic creation, epic validation, epic transition
- **Phase 3 tasks**: RAG assessment, Product Innovation validation, usage guidance, inform user of tickets

### **Phase 0: Quality Assurance & Pre-Flight Validation**
**CRITICAL**: Validate everything BEFORE creating any Jira epics

1. **Environment Check**: Confirm all required environment variables are loaded
   - JIRA_URL, JIRA_USERNAME, JIRA_TOKEN
   - JIRA_PROJECT_KEY_FOR_AUGMENT_AGENT
   - JIRA_TEAM_FIELD_FOR_AUGMENT_AGENT, JIRA_TEAM_VALUE_FOR_AUGMENT_AGENT
   - Epic workflow configurations

2. **Epic Quality Review**: Read and apply epic health coaching guidelines
   - Review `/docs/ai_agent_assets/jira_guidelines/wex_epic_health_coach.md`
   - Review `/docs/ai_agent_assets/jira_guidelines/wex_epic_rating_coach.md`
   - Review `/docs/ai_agent_assets/jira_guidelines/wex_work_decomposition.md`
   - Ensure epic qualifies as Product Innovation
   - Target 8+ quality score for story points field

3. **Content Preparation**: Prepare all epic components with proper Jira formatting
   - Epic title (clear and business-focused)
   - Comprehensive description with h2. headers and # numbered lists
   - BDD-format acceptance criteria for customfield_10222
   - Detailed risk assessment with mitigation plans for customfield_10218
   - Quality score (8+) for story points field (customfield_10024)

4. **Epic Assessment**: Conduct thorough quality evaluation
   - Apply RAG (Red-Amber-Green) rating system
   - Validate against Product Innovation criteria
   - Ensure INVEST principles compliance at epic level
   - Confirm 8+ score justification

5. **Abort on Validation Failure**: If ANY validation fails:
   - STOP immediately - do not create any Jira epics
   - Report specific validation errors to user
   - Request user to resolve issues before proceeding

### **Phase 1: Task List Validation**
6. **Validate Task List**: Ensure comprehensive task list was created before Phase 0
   - **Verify ALL phases included**: Phase 0 (validation), Phase 2 (epic creation), Phase 3 (quality documentation)
   - **Confirm task quality**: Each task represents meaningful work (~20 minutes each)
   - **Task list should already be complete** from the FIRST step before starting phases

### **Phase 2: Epic Creation**
7. **Create Epic**: Create epic with all enhanced fields and proper formatting
   ```bash
   python scripts/augment_jira_integration/jira_agent_client.py create-epic \
     --title "[Epic Title - Business-Focused]" \
     --description "[Comprehensive epic description with h2. headers and # numbered lists]" \
     --acceptance-criteria "[BDD format acceptance criteria with h3. headers]" \
     --story-points [QUALITY_SCORE_8_PLUS] \
     --risk-assessment "[Detailed risk assessment with h2./h3. headers and # numbered lists]"
   ```

8. **Epic Validation**: Verify epic was created successfully
   ```bash
   python scripts/augment_jira_integration/jira_agent_client.py get --issue [EPIC_KEY]
   ```

### **Phase 3: Quality Documentation**
9. **Provide Epic Assessment**: Document the epic quality evaluation
   - RAG rating with detailed justification
   - Product Innovation compliance confirmation
   - Quality score explanation (why 8+)
   - Recommendations for future improvements

10. **Epic Usage Guidance**: Provide guidance for using the epic
   - How to create stories under this epic
   - Reference to jira-story-flow for story creation
   - Integration with existing workflows

11. **Inform User of Created Jira Tickets**: Provide summary of all created Jira items
    - **Epic**: [EPIC_KEY] - [Epic Title]
    - **URLs**: Provide clickable links to all created items

## 🚨 Critical Requirements

### **Epic Quality Standards**
- All epics must qualify as Product Innovation per coaching guidelines
- Epic must achieve 8+ quality score (reflected in story points field)
- Must include comprehensive acceptance criteria in BDD format
- Must include detailed risk assessment with mitigation plans
- Use proper Jira markup formatting (h2., h3., #, *)

### **Content Requirements**
- **Description**: Business Objective, User Impact, Success Criteria, Scope and Boundaries, Dependencies, Assumptions
- **Acceptance Criteria (customfield_10222)**: 6+ comprehensive BDD-style criteria with h3. headers
- **Risk Assessment (customfield_10218)**: 5+ detailed risks with mitigation plans using proper formatting
- **Story Points (customfield_10024)**: Quality score of 8+ reflecting epic excellence

### **Product Innovation Criteria**
- **Customer and Business Value**: Clear value proposition for both
- **New or Enhanced**: Represents new product/service or significant enhancement
- **Delivery Inclusive**: Considers how product/service is delivered
- **Epic Level**: Appropriate scope for epic-level initiative

### **Assessment Framework**
- Apply RAG (Red-Amber-Green) rating system
- Use 0-10 quality scoring scale from rating coach
- Validate against epic health coach criteria
- Ensure compliance with work decomposition principles

## 📋 Epic Content Structure

### **Description Template**
```
h2. Business Objective
[Clear transformation goal and strategic alignment]

h2. User Impact
*Primary Users*: [Specific user roles and personas]
*Key Benefits*:
# [Benefit 1 with clear value]
# [Benefit 2 with measurable impact]
# [Benefit 3 with user experience improvement]
# [Benefit 4 with business advantage]

h2. Success Criteria
*Business Metrics*:
# [Measurable business outcome 1]
# [Measurable business outcome 2]
# [Measurable business outcome 3]
# [Measurable business outcome 4]

*Technical Metrics*:
# [Technical performance target 1]
# [Technical performance target 2]
# [Technical performance target 3]
# [Technical performance target 4]

h2. Scope and Boundaries
*Included*:
# [Scope item 1]
# [Scope item 2]
# [Scope item 3]

*Excluded*:
# [Exclusion 1 with rationale]
# [Exclusion 2 with rationale]
# [Exclusion 3 with rationale]

h2. Dependencies
*Internal Dependencies*:
# [Internal dependency 1]
# [Internal dependency 2]
# [Internal dependency 3]

*External Dependencies*:
# [External dependency 1]
# [External dependency 2]
# [External dependency 3]

h2. Assumptions
*Key Assumptions*:
# [Assumption 1]
# [Assumption 2]
# [Assumption 3]
# [Assumption 4]
```

### **Acceptance Criteria Template (customfield_10222)**
```
h3. AC1: [Acceptance Criteria Name]
*Given* [initial context/state]
*When* [action or event occurs]
*Then* [expected outcome]
*And* [additional expected outcomes]
*And* [quality/performance requirements]

h3. AC2: [Another Acceptance Criteria]
*Given* [different context]
*When* [different action]
*Then* [different expected outcome]
*And* [additional requirements]

[Continue for 6+ comprehensive acceptance criteria]
```

### **Risk Assessment Template (customfield_10218)**
```
h2. Risk Assessment and Mitigation Plan

h3. 1. [Risk Name] ([PRIORITY LEVEL])
*Risk Description*: [Detailed risk description]
*Impact*: [Business and technical impact]
*Probability*: [Probability level with percentage]
*Mitigation Plan*:
# [Specific mitigation action 1]
# [Specific mitigation action 2]
# [Specific mitigation action 3]
# [Monitoring and contingency measures]

[Continue for 5+ comprehensive risks]
```

## 📈 Success Criteria

A successful jira-epic-flow execution includes:
- ✅ All validation steps completed successfully
- ✅ Epic created with 8+ quality score
- ✅ Comprehensive description with proper Jira formatting
- ✅ BDD-format acceptance criteria in dedicated field
- ✅ Detailed risk assessment with mitigation plans
- ✅ Product Innovation criteria fully met
- ✅ RAG assessment provided with justification
- ✅ Epic ready for story creation and development

## 🔄 Integration with Other Rules

This rule integrates with:
- **Epic Health Coach**: `/docs/ai_agent_assets/jira_guidelines/wex_epic_health_coach.md`
- **Epic Rating Coach**: `/docs/ai_agent_assets/jira_guidelines/wex_epic_rating_coach.md`
- **Work Decomposition**: `/docs/ai_agent_assets/jira_guidelines/wex_work_decomposition.md`
- **AI Jira Integration Guidelines**: `.augment/rules/ai_jira_integration_guidelines.md`
- **Jira Story Flow**: `.augment/rules/jira_story_flow.md` (for creating stories under epics)

## 🎯 Epic Creation Authority

**IMPORTANT**: Epic creation is user-driven. AI agents should:
- ✅ **Wait for explicit user request** for epic creation
- ✅ **Follow jira-epic-flow** only when specifically mentioned
- ✅ **Provide guidance** on when epics might be appropriate
- ❌ **Never autonomously suggest** epic creation
- ❌ **Never create epics** without explicit user instruction

When "jira-epic-flow" is not mentioned, follow standard guidelines without epic creation.
