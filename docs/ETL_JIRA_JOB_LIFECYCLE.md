# ETL Jira Job Lifecycle

This document explains how Jira ETL jobs work, including the 5-step extraction process, status management, flag handling, and completion patterns.

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

Jira has 5 sequential steps:
1. `jira_projects_and_issue_types` - Discover projects and issue types
2. `jira_statuses_and_relationships` - Extract statuses and relationships
3. `jira_issues_with_changelogs` - Extract issues and their change history
4. `jira_dev_status` - Extract development status field
5. `jira_sprint_reports` - Extract sprint metrics and queue sprints for embedding

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
- **Identifies issues with code changes**: During extraction, queries `custom_fields_mapping` table to get the configured development field external_id
  - Queries: `SELECT cf.external_id FROM custom_fields_mapping cfm JOIN custom_fields cf ON cf.id = cfm.development_field_id WHERE cfm.tenant_id = :tenant_id AND cfm.integration_id = :integration_id`
  - If development field is mapped and issue has value in that field → Issue has code changes → Add to `issues_with_code_changes` list
  - If development field is not mapped or field is empty → Issue has no code changes → Skip for dev_status extraction
- Stores each issue in raw_extraction_data with type: `jira_issues_with_changelogs`
- Queues MULTIPLE messages to transform queue with:
  - `type: 'jira_issues_with_changelogs'`
  - First issue: `first_item=True, last_item=False`
  - Middle issues: `first_item=False, last_item=False`
  - Last issue: `first_item=False, last_item=True`
- **After queuing all issues to transform**: Queues extraction jobs for Step 4 (dev_status) for each issue in `issues_with_code_changes` list
  - Uses the development field presence as the indicator of code changes
  - Queues one extraction job per issue with code changes
- **Sprint Processing**: Transform worker processes sprint associations for each issue
  - Queries `custom_fields_mapping` table to get the configured sprints field external_id
  - Extracts sprint data from the issue's fields using the mapped field ID (e.g., `customfield_10020`)
  - Upserts sprint records in `sprints` table using `ON CONFLICT DO UPDATE` to handle concurrent workers
  - Creates associations in `work_items_sprints` junction table using `ON CONFLICT DO NOTHING` for idempotency
  - Both operations are race-condition safe for concurrent processing by multiple transform workers
  - **Note**: Sprints are NOT queued to embedding at this step - only metadata is stored
  - **Note**: Sprint field is NOT stored in `work_items` table - uses normalized `sprints` and `work_items_sprints` tables
  - **Note**: Sprint metrics and embedding happen in Step 5 (sprint_reports)
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

**Step 4: Dev Status**
- Extraction fetches development status field for issues with code changes
- Stores each issue's dev_status in raw_extraction_data with type: `jira_dev_status`
- Queues MULTIPLE messages to transform queue (one per issue) with:
  - `type: 'jira_dev_status'`
  - First issue: `first_item=True, last_item=False`
  - Middle issues: `first_item=False, last_item=False`
  - Last issue: `first_item=False, last_item=True`
- **After queuing all issues to transform**: Queues extraction job for Step 5 (sprint_reports)
- Transform processes each message and queues to embedding with same flags
- Embedding processes each message
- When `last_item=True`: sends "finished" status

**Step 4 Completion (No Dev Status Case)**
- If NO dev status data is extracted:
  - Extraction sends completion message to transform queue with:
    - `type: 'jira_dev_status'`
    - `raw_data_id=None, first_item=True, last_item=True`
  - Transform recognizes completion and forwards to embedding
  - Embedding sends "finished" status
  - Extraction worker then queues Step 5 (sprint_reports)

**Step 5: Sprint Reports (Final Step)**
- **Sprint Discovery**: Extraction queries database for unique sprint combinations
  - Queries `work_items_sprints` table joined with `sprints` table
  - Gets distinct `(board_id, sprint_id)` combinations for sprints created/updated since `last_sync_date`
  - Uses `custom_fields_mapping.sprints_field_id` to get the correct sprint field external_id
- **Sprint Metrics Extraction**: For each sprint combination:
  - Calls Jira API: `/rest/greenhopper/1.0/rapid/charts/sprintreport?rapidViewId={board_id}&sprintId={sprint_id}`
  - Extracts sprint metrics: completed_estimate, not_completed_estimate, punted_estimate, velocity, completion_percentage
  - Stores in raw_extraction_data with type: `jira_sprint_reports`
- Queues MULTIPLE messages to transform queue (one per sprint) with:
  - `type: 'jira_sprint_reports'`
  - First sprint: `first_item=True, last_item=False, last_job_item=False`
  - Middle sprints: `first_item=False, last_item=False, last_job_item=False`
  - Last sprint: `first_item=False, last_item=True, last_job_item=True`
- **Transform Processing**:
  - Queries raw_extraction_data using raw_data_id
  - Updates sprint record in `sprints` table with metrics
  - Queues sprint to embedding with `table_name='sprints'` and sprint's `external_id`
- **Embedding Processing**:
  - Fetches sprint entity from database using external_id
  - Generates embedding from sprint metadata and metrics
  - Stores vector in Qdrant collection `tenant_{id}_sprints`
  - Creates record in `qdrant_vectors` table
- When `last_job_item=True`: calls `_complete_etl_job()` and sets overall status to FINISHED

**Step 5 Completion (No Sprints Case)**
- If NO sprints are found:
  - Extraction sends completion message to transform queue with:
    - `type: 'jira_sprint_reports'`
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
   - Calls `complete_etl_job()` (because `last_job_item=True`)
   - Sets overall status to FINISHED
   - Sets `reset_deadline` = current time + 30 seconds
   - Sets `reset_attempt` = 0
   - Schedules delayed task to check and reset job

4. **Backend Scheduler** (`job_reset_scheduler.py`):
   - After 30 seconds, runs `check_and_reset_job()` task
   - Verifies all steps are finished
   - Checks embedding queue for remaining messages with job token
   - **If work remains**: Extends deadline (60s, 180s, 300s) and reschedules
   - **If all complete**: Resets job to READY

5. **UI Countdown** (system-level, not per-session):
   - Receives `reset_deadline` via WebSocket
   - Calculates remaining time: `deadline - current_time`
   - Displays "Resetting in 30s", "Resetting in 29s", etc.
   - All users see the same countdown

---

## Token Forwarding Through Jira Pipeline

Every Jira job uses a **unique token (UUID)** that is generated at job start and forwarded through ALL stages for job tracking and correlation.

### Token Flow for Each Step

**Step 1: jira_projects_and_issue_types**
```
Job Start (token generated)
    ↓ token in message
Extraction → Transform Queue (line 564 in jira_extraction.py)
    ↓ token in message
Transform → Embedding Queue (line 2233 in transform_worker.py)
    ↓ token in message
Embedding Worker (line 248, 268 in embedding_worker.py)
```

**Step 2: jira_statuses_and_relationships**
```
Extraction → Transform Queue (line 668 in jira_extraction.py)
    ↓ token in message
Transform → Embedding Queue (line 2233 in transform_worker.py)
    ↓ token in message
Embedding Worker (line 248, 268 in embedding_worker.py)
```

**Step 3: jira_issues_with_changelogs**
```
Extraction → Transform Queue (line 906 in jira_extraction.py)
    ↓ token in message
Transform → Embedding Queue (line 2233 in transform_worker.py)
    ↓ token in message
Embedding Worker (line 248, 268 in embedding_worker.py)
```

**Step 4: jira_dev_status (CRITICAL - Must forward token)**
```
Extraction (Initial) → Dev Status Extraction (line 1420 in jira_extraction.py)
    ↓ token in message
Extraction Worker → Transform Queue (line 490 in extraction_worker.py)
    ↓ token in message
Transform → Embedding Queue (line 3684 in transform_worker.py)
    ↓ token in message
Embedding Worker (line 248, 268 in embedding_worker.py)
```

### Critical Implementation Points

1. **jira_extraction.py line 1420**: Must include `token=token` when queuing dev_status extraction
2. **extraction_worker.py line 490**: Must include `token=message.get('token')` when publishing to transform
3. **transform_worker.py line 3676**: Must extract token from message: `token = message.get('token')`
4. **transform_worker.py line 3684**: Must include `token=token` when calling `_queue_entities_for_embedding()`

### Token Verification

To verify token is properly forwarded:
1. Check logs for token value in first message
2. Verify same token appears in all subsequent messages
3. Confirm token is present in embedding worker logs
4. Token should NOT become `None` at any stage

---

## Date Forwarding for Incremental Sync

Every Jira job uses **two date fields** for incremental sync:
- `old_last_sync_date` (or `last_sync_date`): Used for filtering data during extraction (from previous job run)
- `new_last_sync_date`: Extraction start time that will be saved for the next incremental run

### Date Flow Through Pipeline

**All Steps (same pattern for all 4 steps)**
```
Job Start (reads last_sync_date from database)
    ↓ old_last_sync_date in message
Extraction Worker (sets new_last_sync_date = current date)
    ↓ old_last_sync_date + new_last_sync_date in message
Transform Queue
    ↓ MUST forward both dates
Transform Worker
    ↓ old_last_sync_date + new_last_sync_date in message
Embedding Queue
    ↓ new_last_sync_date used for database update
Embedding Worker (updates last_sync_date when last_job_item=True)
```

### Critical Implementation Points

1. **Extraction Worker**: Sets `new_last_sync_date = DateTimeHelper.now_default()` at extraction start
   - This captures the extraction start time in configured timezone (America/New_York from .env)
   - Uses `old_last_sync_date` for filtering (e.g., `updated >= '2025-11-11 14:00'` in JQL)
   - **Important**: All timestamps use `DateTimeHelper.now_default()` for timezone consistency

2. **Transform Worker**: Must forward both dates to embedding
   - `jira_transform_worker.py`: Extract `new_last_sync_date` from message
   - Forward `new_last_sync_date` to embedding queue in all steps

3. **Embedding Worker**: Updates database when `last_job_item=True`
   - Calls `_complete_etl_job(job_id, tenant_id, new_last_sync_date)`
   - Updates `last_sync_date` column in `etl_jobs` table
   - Next run will use this value as `old_last_sync_date`

### Incremental Sync Behavior

**First Run (no last_sync_date in database)**
- `old_last_sync_date = None`
- Extraction uses no date filter (fetches all issues)
- Sets `new_last_sync_date = 2025-11-11 14:00:00`
- Embedding worker updates database: `last_sync_date = 2025-11-11 14:00:00`

**Second Run (last_sync_date exists in database)**
- `old_last_sync_date = 2025-11-11 14:00:00` (from database)
- Extraction uses incremental filter: `updated >= '2025-11-11 14:00'` in JQL
- Sets `new_last_sync_date = 2025-11-12 10:00:00`
- Embedding worker updates database: `last_sync_date = 2025-11-12 10:00:00`
- **Saves API quota**: Only fetches issues updated since last run

### Date Verification for Jira

To verify dates are properly forwarded:
1. Check logs for `new_last_sync_date` in extraction worker output
2. Verify both dates appear in transform queue messages
3. Verify both dates appear in embedding queue messages
4. Confirm `last_sync_date` is updated in database after job completion
5. Verify next run uses previous `new_last_sync_date` as `old_last_sync_date`

