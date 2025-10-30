# ETL Jira Job Lifecycle

This document explains how Jira ETL jobs work, including the 4-step extraction process, status management, flag handling, and completion patterns.

## Job Status Structure

```json
{
  "overall": "READY|RUNNING|FINISHED|FAILED",
  "steps": {
    "step_name": {
      "order": 1,
      "display_name": "Step Display Name",
      "extraction": "idle|running|finished|failed",
      "transform": "idle|running|finished|failed",
      "embedding": "idle|running|finished|failed"
    }
  }
}
```

---

## Step Structure

Jira has 4 sequential steps:
1. `jira_projects_and_issue_types` - Discover projects and issue types
2. `jira_statuses_and_relationships` - Extract statuses and relationships
3. `jira_issues_with_changelogs` - Extract issues and their change history
4. `jira_dev_status` - Extract development status field

---

## Data Extraction Rules

**Step 1: Projects and Issue Types**
- Extraction fetches all projects and issue types
- Stores in raw_extraction_data with type: `jira_projects_and_issue_types`
- Queues ONE message to transform queue with:
  - `type: 'jira_projects_and_issue_types'`
  - `first_item=True, last_item=True`
- **After queuing to transform**: Queues extraction job for Step 2 (statuses and relationships)
- Transform processes and queues to embedding with same flags
- Embedding processes and sends "finished" status

**Step 2: Statuses and Relationships**
- Extraction fetches statuses for EACH project individually
- Stores ONE raw_data_id per project in raw_extraction_data with type: `jira_project_statuses`
- Queues MULTIPLE messages to transform queue (one per project) with:
  - `type: 'jira_statuses_and_relationships'`
  - First project: `first_item=True, last_item=False`
  - Middle projects: `first_item=False, last_item=False`
  - Last project: `first_item=False, last_item=True`
- **After queuing all projects to transform**: Queues extraction job for Step 3 (issues with changelogs)
- Transform processes each project's statuses:
  - Inserts/updates statuses in database
  - When `first_item=True`: Does NOT queue to embedding (just processes the data)
  - When `last_item=True`: Queries ALL distinct status external_ids from database
    - Queues MULTIPLE messages to embedding queue (one per distinct status) with:
      - `type: 'jira_statuses_and_relationships'`
      - `table_name: 'statuses'`
      - First status: `first_item=True, last_item=False`
      - Middle statuses: `first_item=False, last_item=False`
      - Last status: `first_item=False, last_item=True`
- Embedding processes each status and sends "finished" status on last one

**Step 3: Issues with Changelogs**
- Extraction fetches issues using JQL with filters:
  - **Projects filter**: From `integration.settings.projects` array (e.g., `["BDP", "BEN", "BEX", "BST", ...]`)
  - **Base search filter**: From `integration.settings.base_search` (optional, can be null)
  - **Date filter**:
    - If `last_sync_date` is NOT null: `updated >= 'YYYY-MM-DD HH:MM'` (JQL datetime format without seconds)
    - If `last_sync_date` is null: No date filter (fetch all issues)
  - **Batch size**: From `integration.settings.sync_config.batch_size` (e.g., 100)
  - **Rate limit**: From `integration.settings.sync_config.rate_limit` (e.g., 10 requests/minute)
- **Identifies issues with code changes**: During extraction, checks if each issue has the development field (e.g., `customfield_10000`) populated
  - If development field exists → Issue has code changes → Add to `issues_with_code_changes` list
  - If development field is empty → Issue has no code changes → Skip for dev_status extraction
- Stores each issue in raw_extraction_data with type: `jira_issues_with_changelogs`
- Queues MULTIPLE messages to transform queue with:
  - `type: 'jira_issues_with_changelogs'`
  - First issue: `first_item=True, last_item=False`
  - Middle issues: `first_item=False, last_item=False`
  - Last issue: `first_item=False, last_item=True`
- **After queuing all issues to transform**: Queues extraction jobs for Step 4 (dev_status) for each issue in `issues_with_code_changes` list
  - Uses the development field presence as the indicator of code changes
  - Queues one extraction job per issue with code changes
- Transform processes each message and queues to embedding with same flags
- Embedding processes each message
- When `last_item=True`: sends "finished" status

**Step 3 Completion (No Issues Case)**
- If NO issues are extracted:
  - Extraction sends completion message to transform queue with:
    - `type: 'jira_issues_with_changelogs'`
    - `raw_data_id=None, first_item=True, last_item=True, last_job_item=True`
  - Transform recognizes completion and forwards to embedding
  - Embedding receives `last_job_item=True` and calls `_complete_etl_job()`
  - Sets overall status to FINISHED (skips Step 4 since no issues to process)

**Step 4: Dev Status (Final Step)**
- Extraction fetches development status field for issues with code changes
- Stores each issue's dev_status in raw_extraction_data with type: `jira_dev_status`
- Queues MULTIPLE messages to transform queue (one per issue) with:
  - `type: 'jira_dev_status'`
  - First issue: `first_item=True, last_item=False, last_job_item=False`
  - Middle issues: `first_item=False, last_item=False, last_job_item=False`
  - Last issue: `first_item=False, last_item=True, last_job_item=True`
- **After queuing all issues to transform**: No next extraction step (this is the final step)
- Transform processes each message and queues to embedding with same flags
- Embedding processes each message
- When `last_job_item=True`: calls `_complete_etl_job()` and sets overall status to FINISHED

**Step 4 Completion (No Dev Status Case)**
- If NO dev status data is extracted:
  - Extraction sends completion message to transform queue with:
    - `type: 'jira_dev_status'`
    - `raw_data_id=None, first_item=True, last_item=True, last_job_item=True`
  - Transform recognizes completion and forwards to embedding
  - Embedding receives `last_job_item=True` and calls `_complete_etl_job()`
  - Sets overall status to FINISHED

---

## Flag Usage in Jira

| Flag | When Set | Purpose |
|------|----------|---------|
| `first_item=True` | First message of a step | Send WebSocket "running" status |
| `last_item=True` | Last message of a step | Send WebSocket "finished" status |
| `last_job_item=True` | ONLY on last message of ENTIRE job (dev_status or jira_issues_with_changelogs steps) | Signal overall job completion |

---

## Jira Completion Scenarios

**Scenario 1: Normal Flow (Multiple Projects + Multiple Issues + Dev Status)**
```
Step 1 (1 message)
  ↓
Step 2 (multiple projects → multiple statuses)
  - Extraction: 1 raw_data_id per project
  - Transform: processes each project, queries distinct statuses on last_item=True
  - Embedding: 1 message per distinct status
  ↓
Step 3 (multiple issues)
  - Extraction: 1 raw_data_id per issue
  - Transform: processes each issue
  - Embedding: 1 message per issue
  ↓
Step 4 (dev_status for each issue with code changes)
  - Extraction: 1 raw_data_id per issue
  - Transform: processes each issue
  - Embedding: 1 message per issue, last one has last_job_item=True
  ↓
Job FINISHED
```

**Scenario 2: No Issues (Skip to Dev Status)**
```
Step 1 → Step 2 (multiple projects → multiple statuses) → Step 3 (completion message, no issues) → Step 4 (dev_status)
                                                                                                            ↓
                                                                                                    last_job_item=True
                                                                                                            ↓
                                                                                                    Job FINISHED
```

**Scenario 3: No Dev Status (End at Step 3)**
```
Step 1 → Step 2 (multiple projects → multiple statuses) → Step 3 (multiple issues) → Step 4 (completion message, no dev status)
                                                                                                ↓
                                                                                        last_job_item=True
                                                                                                ↓
                                                                                        Job FINISHED
```

**Scenario 4: No Issues AND No Dev Status**
```
Step 1 → Step 2 (multiple projects → multiple statuses) → Step 3 (completion message) → Step 4 (completion message)
                                                                                                ↓
                                                                                        last_job_item=True
                                                                                                ↓
                                                                                        Job FINISHED
```

---

## Jira Completion Flow

1. **Extraction Worker** on final step (dev_status) sends:
   - If data exists: `raw_data_id=<id>, first_item=True, last_item=True, last_job_item=True`
   - If no data: `raw_data_id=None, first_item=True, last_item=True, last_job_item=True`

2. **Transform Worker** receives message:
   - Recognizes `last_job_item=True` as job completion signal
   - Sends "finished" status for transform step (because `last_item=True`)
   - Forwards to embedding with `last_job_item=True`

3. **Embedding Worker** receives message:
   - Sends "finished" status for embedding step (because `last_item=True`)
   - Calls `_complete_etl_job()` (because `last_job_item=True`)
   - Sets overall status to FINISHED

4. **UI Timer** detects FINISHED:
   - Calls `checkJobCompletion` endpoint
   - Checks if all steps are finished
   - Waits 30 seconds, then calls `resetJobStatus`
   - Resets all steps to "idle" and overall to "READY"

