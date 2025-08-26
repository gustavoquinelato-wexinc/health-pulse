# Jira Agent Client for Augment Agent

This script provides a simplified command-line interface for AI agents to interact with Jira using the configured environment variables. It supports essential operations: get issue by key, create issues, update issues, and workflow transitions with resolution handling.

## Configuration

The script uses the following environment variables from the root `.env` file:

- `JIRA_URL`: Base URL for the Jira instance
- `JIRA_USERNAME`: Email address for authentication  
- `JIRA_TOKEN`: Personal API token for authentication
- `JIRA_PROJECT_KEY_FOR_AUGMENT_AGENT`: Project key (e.g., "BST")
- `JIRA_TEAM_FIELD_FOR_AUGMENT_AGENT`: Team field name (e.g., "Agile Team[Dropdown]")
- `JIRA_TEAM_VALUE_FOR_AUGMENT_AGENT`: Team value (e.g., "Research & Innovation Team")

## Installation

Install dependencies using the platform's centralized requirements system:
```bash
python scripts/install_requirements.py augment-jira-integration
```

This will:
- Create a virtual environment in `scripts/augment_jira_integration/venv/`
- Install dependencies from `requirements/augment-jira-integration.txt`
- Set up the environment for the Jira integration script

## Usage

### Debug Mode
Add `--debug` flag to any command to see detailed debug information:
```bash
python scripts/augment_jira_integration/jira_agent_client.py --debug get --issue BST-123
```

### Get Issue by Key
```bash
python scripts/augment_jira_integration/jira_agent_client.py get \
  --issue BST-123
```

### Create Epic
```bash
python scripts/augment_jira_integration/jira_agent_client.py create-epic \
  --title "AI Integration Phase 2" \
  --description "Implement advanced AI features for the platform"
```

### Create Story
```bash
# Create story without parent epic
python scripts/augment_jira_integration/jira_agent_client.py create-story \
  --title "Query Classification" \
  --description "Implement LLM-based query routing"

# Create story under an epic
python scripts/augment_jira_integration/jira_agent_client.py create-story \
  --title "Query Classification" \
  --description "Implement LLM-based query routing" \
  --parent BST-123
```

### Create Subtask
```bash
python scripts/augment_jira_integration/jira_agent_client.py create-subtask \
  --parent BST-124 \
  --title "Unit Tests" \
  --description "Write comprehensive unit tests for query classifier"
```

### Update Issue
```bash
# Update title only
python scripts/augment_jira_integration/jira_agent_client.py update \
  --issue BST-125 \
  --title "Updated Title"

# Update both title and description
python scripts/augment_jira_integration/jira_agent_client.py update \
  --issue BST-125 \
  --title "Updated Title" \
  --description "Updated description"
```

### Add Comment
```bash
python scripts/augment_jira_integration/jira_agent_client.py comment \
  --issue BST-125 \
  --message "Progress update from AI agent"
```

### Transition Issue
```bash
# Basic transition
python scripts/augment_jira_integration/jira_agent_client.py transition \
  --issue BST-125 \
  --status "Development"

# Transition to final state with resolution
python scripts/augment_jira_integration/jira_agent_client.py transition \
  --issue BST-125 \
  --status "Released" \
  --resolution "Done"
```

### Get Valid Transitions
```bash
python scripts/augment_jira_integration/jira_agent_client.py get-transitions \
  --issue BST-125
```

## Output Format

All commands return JSON output for easy parsing by AI agents:

### Success Response (Create/Update)
```json
{
  "success": true,
  "key": "BST-123",
  "id": "12345",
  "url": "https://wexinc.atlassian.net/browse/BST-123",
  "message": "Epic created successfully: BST-123"
}
```

### Success Response (Get Issue)
```json
{
  "success": true,
  "issue": {
    "key": "BST-123",
    "summary": "Epic Title",
    "description": "Epic description text",
    "status": "In Progress",
    "assignee": "John Doe",
    "issuetype": "Epic",
    "project": "BST",
    "created": "2025-01-07T10:00:00.000-0600",
    "updated": "2025-01-07T15:30:00.000-0600",
    "url": "https://wexinc.atlassian.net/browse/BST-123"
  },
  "message": "Retrieved issue: BST-123"
}
```

### Error Response
```json
{
  "success": false,
  "error": "Jira API error (400): Field 'summary' is required",
  "message": "Operation failed: Field 'summary' is required"
}
```

## Debug Mode

Use the `--debug` flag to enable detailed debugging information:

```bash
python scripts/augment_jira_integration/jira_client.py --debug get --issue BST-123
```

Debug mode shows:
- **Environment Variables**: All loaded Jira configuration values
- **Request Details**: Full URL, authentication info, headers
- **Response Details**: HTTP status codes, response headers, rate limit info
- **Error Details**: Detailed error messages and response content

## Error Handling

The script includes comprehensive error handling:

- **Missing Environment Variables**: Validates all required variables on startup
- **Authentication Errors**: Handles 401/403 responses with clear messages
- **API Rate Limits**: Respects Jira API rate limits with appropriate timeouts
- **Network Issues**: Handles connection timeouts and network errors
- **Invalid Parameters**: Validates input parameters before making API calls

## Integration with AI Agents

AI agents should:

1. **Always use environment variables** - Never hardcode credentials
2. **Parse JSON output** - All responses are in JSON format for easy parsing
3. **Handle errors gracefully** - Check the `success` field in responses
4. **Provide user feedback** - Use the `message` field for user communication
5. **Include URLs** - Direct links to created/updated issues are provided

## Security Notes

- API tokens are read from environment variables only
- No credentials are logged or exposed in output
- Uses HTTPS for all API communications
- Follows Jira API best practices for authentication
