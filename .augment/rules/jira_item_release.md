---
type: "manual"
---

# Jira Item Release Flow

## Purpose
This rule defines the process for completing Jira items (epics or stories) by transitioning them through all remaining statuses to their final completion state after user validation.

## When to Use
- User has completed their validation/testing of implemented features
- User requests to "release" or "complete" or set as "done" a specific Jira item
- All technical work is done and user has verified functionality
- Ready to mark work as officially complete in Jira

## Process Flow

### Step 1: Identify Item Type
1. **Get the Jira item** using the provided key
2. **Determine item type**: Epic or Story
3. **Check current status** to understand where we are in the workflow

### Step 2: Epic Release Flow
If the item is an **Epic**:

1. **Check Epic Status**:
   - Get current status and available transitions
   - Identify the final completion status (usually "Done" or "Released")

2. **Transition Epic to Completion**:
   - Move through any intermediate statuses if required
   - End at the final completion status
   - Add completion comment with summary

3. **Epic Completion Comment Template**:
   ```
   Epic completed successfully after user validation.
   
   All associated stories and technical work have been implemented and validated.
   Ready for production use.
   
   Completion Date: [Current Date]
   ```

### Step 3: Story Release Flow
If the item is a **Story**:

1. **Check Story Status**:
   - Get current status and available transitions
   - Identify the final completion status (usually "Done" or "Story Testing Complete")

2. **Transition Story to Completion**:
   - If in "Ready for Story Testing": Move to "Story Testing" → "Done"
   - If in "Story Testing": Move to "Done"
   - If in other status: Follow available transitions to completion
   - Add completion comment with summary

3. **Story Completion Comment Template**:
   ```
   Story completed successfully after user validation.
   
   All acceptance criteria have been met and functionality has been verified.
   Technical implementation is complete and tested.
   
   Completion Date: [Current Date]
   ```

### Step 4: Validation and Confirmation
1. **Verify Final Status**: Confirm item reached final completion state
2. **Add Final Comment**: Include completion summary and date
3. **Report to User**: Provide confirmation with Jira links

## Implementation Guidelines

### Status Transition Logic
```python
# Epic transitions (typical flow)
epic_completion_flow = [
    "Development" → "Code review" → "Ready for Story Testing" → "Story Testing" → "Done"
]

# Story transitions (typical flow)  
story_completion_flow = [
    "Development" → "Code review" → "Ready for Story Testing" → "Story Testing" → "Done"
]
```

### Error Handling
- **Invalid transitions**: Report available transitions and ask user for guidance
- **Missing permissions**: Report permission issues and suggest alternatives
- **API failures**: Retry once, then report error with manual steps

### Required Information
- **Jira item key** (e.g., BST-1710, BST-1712)
- **Current user validation status** (assumed complete when user requests release)

## Command Examples

### User Request Examples
```
"Release BST-1710"
"Complete epic BST-1642" 
"Mark story BST-1712 as done"
"Push BST-1710 to final status"
```

### Agent Response Pattern
1. **Acknowledge request**: "Releasing [item-type] [key]..."
2. **Check current status**: "Current status: [status]"
3. **Execute transitions**: "Transitioning [status1] → [status2]..."
4. **Confirm completion**: "✅ [item-type] [key] successfully completed"
5. **Provide link**: "[Jira URL]"

## Success Criteria
- ✅ Item reaches final completion status
- ✅ Appropriate completion comment added
- ✅ User receives confirmation with Jira link
- ✅ No manual intervention required for standard flows

## Notes
- This process assumes user has already validated the work
- Focus on workflow completion, not technical validation
- Always check available transitions before attempting moves
- Provide clear feedback on any issues or manual steps needed
- Use appropriate completion comments based on item type

## Integration with Other Rules
- **Follows**: `jira_story_flow.md` (after implementation complete)
- **Precedes**: Project completion and documentation updates
- **Complements**: Standard Jira workflow management
