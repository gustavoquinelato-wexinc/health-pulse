# Jira Configuration Guide for AI Agents

**Last Updated**: 2025-09-30

## 🎯 Purpose

This guide provides critical configuration information for AI agents working with Jira integration, including proper environment variable setup and Jira markup formatting standards.

## 🔧 Environment Configuration

### Team Field Configuration

**User-Friendly**: The `JIRA_TEAM_VALUE_FOR_AUGMENT_AGENT` environment variable can contain **either the team name OR the numeric ID**. The Jira client automatically resolves team names to IDs.

#### Two Configuration Options

**Option 1: Team Name (Recommended - User-Friendly)**
```env
JIRA_TEAM_FIELD_FOR_AUGMENT_AGENT=customfield_10128
JIRA_TEAM_VALUE_FOR_AUGMENT_AGENT=Research & Innovation Team
```
- ✅ Easy to read and understand
- ✅ Automatically resolved to ID by the client
- ✅ No need to look up numeric IDs

**Option 2: Numeric ID (Direct)**
```env
JIRA_TEAM_FIELD_FOR_AUGMENT_AGENT=customfield_10128
JIRA_TEAM_VALUE_FOR_AUGMENT_AGENT=19601
```
- ✅ Direct ID, no resolution needed
- ✅ Slightly faster (skips resolution step)
- ❌ Less readable

#### How Auto-Resolution Works

The Jira client automatically:
1. Checks if the value is numeric (e.g., `19601`)
   - If yes: Uses it directly as the ID
2. If not numeric (e.g., `Research & Innovation Team`):
   - Queries Jira API to get field metadata
   - Finds the matching team name in allowed values
   - Resolves to the corresponding numeric ID
   - Uses the ID for all operations

#### Finding Team Names (Optional)

If you want to see available team names:

1. **Get an existing issue** with the team field set:
   ```bash
   python scripts/augment_jira_integration/jira_agent_client.py get --issue BST-1951
   ```

2. **Look for the team field value**:
   ```json
   {
     "fields": {
       "customfield_10128": {
         "value": "Research & Innovation Team",
         "id": "19601"
       }
     }
   }
   ```

3. **Use either the name or ID** in your `.env` file

### Complete Environment Variables

```env
# Jira Authentication
JIRA_URL=https://wexinc.atlassian.net
JIRA_USERNAME=gustavo.quinelato@wexinc.com
JIRA_TOKEN=<your-api-token>

# Project Configuration
JIRA_PROJECT_KEY_FOR_AUGMENT_AGENT=BST

# Team Field Configuration
# You can use either team name OR numeric ID (auto-resolved)
JIRA_TEAM_FIELD_FOR_AUGMENT_AGENT=customfield_10128
JIRA_TEAM_VALUE_FOR_AUGMENT_AGENT=Research & Innovation Team  # Or use: 19601

# Workflow Configuration
JIRA_SUBTASK_WORKFLOW=To Do,In Progress,Done
JIRA_STORY_WORKFLOW=To Do,In Progress,Code Review,Testing,Done
JIRA_EPIC_WORKFLOW=To Do,In Progress,Done

# Resolution Configuration
JIRA_STORY_RESOLUTION_REQUIRED=true
JIRA_SUCCESS_RESOLUTION=Done
JIRA_ABANDONED_RESOLUTION=Won't Do
```

## 📝 Jira Markup Formatting

### Critical Rules

**ALWAYS use Jira markup, NOT Markdown**, in all Jira descriptions and comments.

### Headers

❌ **WRONG** (Markdown):
```
## Main Section
### Subsection
#### Sub-subsection
```

✅ **CORRECT** (Jira):
```
h2. Main Section
h3. Subsection
h4. Sub-subsection
```

### Numbered Lists

❌ **WRONG** (Markdown/Plain):
```
1. First item
2. Second item
- Third item
```

✅ **CORRECT** (Jira):
```
# First item
# Second item
# Third item
```

### Bullet Lists

❌ **WRONG** (Markdown):
```
- First bullet
- Second bullet
• Third bullet
```

✅ **CORRECT** (Jira):
```
* First bullet
* Second bullet
* Third bullet
```

### Bold Text

❌ **WRONG** (Markdown):
```
**bold text**
__bold text__
```

✅ **CORRECT** (Jira):
```
*bold text*
```

### Code Blocks

❌ **WRONG** (Markdown):
````
```python
def hello():
    print("Hello")
```
````

✅ **CORRECT** (Jira):
```
{code:python}
def hello():
    print("Hello")
{code}
```

## 📋 Complete Example

### Subtask Description

```
h3. Database and Models

# Add raw_extraction_data table to migration 0001
# Execute database migration and verify table creation
# Copy unified_models.py from etl-service to backend-service

h3. Directory Structure

# Create queue/, transformers/, loaders/ directories
# Create __init__.py files in each directory

h3. RabbitMQ Integration

# Install pika dependency and update requirements.txt
# Implement queue/queue_manager.py with RabbitMQ connectivity
# Test RabbitMQ connection and queue topology

h3. Raw Data APIs

# Create raw_data.py with inline Pydantic schemas
# Implement POST /app/etl/raw-data/store endpoint
# Implement GET /app/etl/raw-data endpoint
# Implement PUT /app/etl/raw-data/{id}/status endpoint
# Add raw_data router to app/etl/router.py

h3. Testing and Validation

# Test raw data storage and retrieval APIs
# Verify batch processing (1 record = 1000 items)
# Verify queue messages contain only IDs
# Create unit tests for all new components
# Update documentation with implementation notes
```

### Completion Comment

```
h2. ✅ Phase 1 Documentation Complete

*Phase 1 planning and documentation has been completed successfully.*

h3. Documentation Deliverables

# phase_1_queue_infrastructure.md - Complete implementation guide
# PHASE_1_QUICK_REFERENCE.md - Quick reference guide for developers
# PHASE_1_CLARIFICATIONS.md - Clarifications based on technical review

h3. Key Architecture Decisions

# *Database vs RabbitMQ Separation*: Database stores complete API responses, RabbitMQ queues only IDs
# *Batch Processing*: 1 API call = 1 database record = 1 queue message
# *Single Table Design*: Only raw_extraction_data table needed
# *Migration Strategy*: Add table to existing migration 0001
# *No Redundancy*: Eliminated unnecessary folders and files

h3. Implementation Timeline

*Revised Duration*: 1 week (simplified from original 2 weeks)

# Database Schema: 1 hour
# Copy Models: 1 hour
# Directory Structure: 15 minutes
# Raw Data APIs: 2 days
# Queue Manager: 2 days
# Testing: 1 day

h3. Ready for Implementation

All documentation is complete and ready for Phase 1 implementation to begin.
```

## 🚨 Common Mistakes to Avoid

1. **Using Markdown syntax** instead of Jira markup
2. **Forgetting headers** in long descriptions/comments
3. **Mixing Markdown and Jira** markup in the same document
4. **Not organizing content** with proper headers and lists
5. **Using invalid team names** (if using name instead of ID, ensure exact match)

## ✅ Checklist for AI Agents

Before creating any Jira issue or comment:

- [ ] Verify `JIRA_TEAM_VALUE_FOR_AUGMENT_AGENT` is set (can be name or ID)
- [ ] Use `h2.`, `h3.`, `h4.` for headers (NOT `##`, `###`, `####`)
- [ ] Use `#` for numbered lists (NOT `1.`, `2.`, `-`)
- [ ] Use `*` for bullet lists (NOT `-`, `•`)
- [ ] Use `*text*` for bold (NOT `**text**`)
- [ ] Organize content with headers and lists for readability
- [ ] Test with `--debug` flag if issues occur
- [ ] If using team name, ensure exact match with Jira (case-sensitive)

## 📚 Related Documentation

- **Jira Story Flow**: `.augment/rules/jira_story_flow.md`
- **AI Jira Integration Guidelines**: `.augment/rules/ai_jira_integration_guidelines.md`
- **Story Health Coach**: `docs/ai_agent_assets/jira_guidelines/wex_story_health_coach.md`

---

**Remember**: Proper configuration and formatting are critical for successful Jira integration. Always use numeric IDs for custom field values and Jira markup for all content.

