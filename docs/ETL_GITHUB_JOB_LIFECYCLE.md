# ETL GitHub Job Lifecycle

This document explains how GitHub ETL jobs work, including the 2-step extraction process with nested pagination, status management, flag handling, and completion patterns.

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

GitHub has 2 steps:
1. `github_repositories` - Extract all repositories
2. `github_prs_commits_reviews_comments` - Extract PRs with nested data (commits, reviews, comments)

---

## Data Extraction Rules

**Step 1: Repositories**
- Extraction fetches all repositories (paginated)
- Stores each repository in raw_extraction_data with type: `github_repositories`
- Queues MULTIPLE messages to transform queue with:
  - `type: 'github_repositories'`
  - First repository: `first_item=True, last_item=False`
  - Middle repositories: `first_item=False, last_item=False`
  - Last repository: `first_item=False, last_item=True`
- Transform processes each message and queues to embedding with same flags
- Embedding processes each message
- When `last_item=True`: sends "finished" status

**Step 1 → Step 2 Transition (Extraction Worker Queues Next Extraction)**
- ✅ **CORRECTED**: Extraction worker (Step 1) queues Step 2 extraction directly - NO backwards communication

**Extraction Worker (Step 1) - LOOP 1: Queue all repositories to Transform**
- Iterates through all extracted repositories
- For each repo: stores in raw_extraction_data, queues to transform queue
- First repository: `first_item=True`
- Last repository: `last_item=True`
- ✅ **LOOP 1 COMPLETES** - all repos queued to transform

**Extraction Worker (Step 1) - LOOP 2: Queue all repositories to Step 2 Extraction**
- ✅ **SAME EXTRACTION WORKER** - no waiting for transform
- Iterates through all extracted repositories (same list from LOOP 1)
- For each repo: queues to extraction queue for Step 2 (NO database query)
- First repository: `first_item=True` (marks start of Step 2)
- Last repository: `last_item=True`
- Each message includes: `owner`, `repo_name`, `full_name`, `integration_id`, `last_sync_date`, `new_last_sync_date`
- ✅ **NO database queries**: Uses repo data directly from extraction
- ✅ **NO backwards communication**: Transform worker does NOT queue extraction
- ✅ **Parallel processing**: Transform processes repos while extraction processes PRs

**Transform Worker - Process Repositories**
- Receives repository messages from transform queue
- Inserts each repository into database
- Queues to embedding with same flags
- ✅ **No Step 2 queuing**: Extraction worker already queued Step 2

**Extraction Worker (Step 2)**
- Receives PR extraction messages from extraction queue
- Uses `owner`, `repo_name`, `last_sync_date` from message (NO database query for repository)
- Extracts PRs using GraphQL and queues to transform

**Step 1 Completion (No Repositories Case)**
- If NO repositories are extracted:
  - Extraction sends completion message to transform queue with:
    - `type: 'github_repositories'`
    - `raw_data_id=None, first_item=True, last_item=True, last_job_item=True`
    - ✅ `last_job_item=True` completes the job immediately (no PR extraction needed)
  - Transform recognizes completion and forwards to embedding
  - Embedding sends "finished" status and completes the job
  - **Job ends** - no Step 2 (PRs) since there are no repositories

**Step 2: PRs with Nested Data (Complex Multi-Phase) by Repository**

**Extraction Overview**
- Extraction fetches each Repository's PRs using GraphQL
- GraphQL response can have multiple PRs requiring multiple pages to get all PRs for a specific Repository
  - When multiple pages exist: queue another message to ExtractionWorker with next page cursor using `type: 'github_prs_commits_reviews_comments'`
  - Each extraction worker processes one page at a time (PR page or nested page)
- Each PR node can have internal nested nodes: commits, reviews, comments, reviewThreads
- Any nested node can have one or multiple pages
  - Single page: data is inside the PR node
  - Multiple pages: queue messages to ExtractionWorker for remaining pages using `type: 'github_prs_commits_reviews_comments'` with nested type specified

**When Processing PR Page**
- ExtractionWorker splits response JSON by PR and inserts each in raw_extraction_data with type: `github_prs`
- Queues individual message to transform queue by PR with: `type: 'github_prs_commits_reviews_comments'`

**When Processing Nested Page**
- ExtractionWorker splits response JSON by nested type (commits, reviews, comments, reviewThreads) and inserts in raw_extraction_data with type: `github_prs_nested`
- Queues individual message to transform queue by nested type with: `type: 'github_prs_commits_reviews_comments'`

**Transform**
- Transform processes each PR or nested message by getting raw_id from the message
- Retrieves data from raw_extraction_data table
- Converts to specific database entity and inserts/updates in the database
- After committing changes, queues to embedding using external_id (from raw_extraction_data JSON) and table_name

**Embedding**
- Embedding processes each message by getting database value based on external_id and table_name
- Sends to embedding provider using integration details and configurations
- Saves data in qdrant_vectors table (bridge table) in primary database
- Inserts/Updates specific collection in Qdrant database

---

## Flag Handling: first_item, last_item, last_job_item, last_repo, last_pr

### **Flag Definitions**

- **first_item**: True only on the first item in a sequence (for WebSocket status updates)
- **last_item**: True only on the last item in a sequence (for WebSocket status updates and step completion)
- **last_job_item**: True only when the entire job should complete (triggers job completion in embedding worker)
- **last_repo**: Internal flag used by extraction worker to track repository boundaries - indicates this is the last repository
- **last_pr**: Internal flag used by extraction worker to track PR boundaries within the last repository - indicates this is the last PR of the last repository

### **Extraction Worker (Step 2)**

**When first_item=true (First Repository's PR extraction)**
- Receives first_item=true from extraction queue message (queued by extraction worker Step 1)
- Updates step status to running and sends WebSocket notification
- Forwards first_item=true to the very FIRST PR message sent to TransformWorker

**When last_item=true and last_job_item=true (Last Repository's PR extraction)**
- Performs GraphQL request and checks: **Is this the last PR page?**

  **Case 1.1: YES - This is the last PR page**
  - Splits response by PRs and loops through checking for nested pagination needs
  - **Is there any nested pagination needed in any of those PRs?**

    **Case 1.1.2.1: NO nested pagination needed**
    - Sends last_item=true and last_job_item=true to the LAST PR message to TransformWorker
    - All other PRs sent with last_item=false, last_job_item=false

    **Case 1.1.2.2: YES nested pagination needed**
    - **Loop 1: Queue all PRs to TransformWorker** with last_item=false, last_job_item=false
    - **Loop 2: Queue nested extraction jobs** for each PR needing nested pagination:
      - For each nested type (commits → reviews → comments → reviewThreads order):
        - If this is NOT the last nested type: queue with last_pr=false
        - If this IS the last nested type: queue with last_pr=true ✅
      - Example: If PR needs commits, reviews, comments only (no reviewThreads):
        - commits: last_pr=false
        - reviews: last_pr=false
        - comments: last_pr=true ✅ (last nested type)
    - Nested extraction workers continue processing pages and forward flags through
    - On final nested page of final nested type: sends last_item=true, last_job_item=true to TransformWorker

  **Case 1.2: NO - More PR pages exist**
  - Queues next PR page to ExtractionWorker with last_item=false, last_job_item=false, last_repo=true
  - Sends ALL PR messages in current page to TransformWorker with last_item=false, last_job_item=false

**Case 2: If no more PR pages exist**
- Continues checking until reaching final page (Case 1.1 above)
- After finding the right last item extracted: updates step status to finished and sends WebSocket notification

### **Transform Worker**

**When first_item=true (First PR of first Repository)**
- Updates step status to running and sends WebSocket notification
- Forwards first_item=true to EmbeddingWorker

**When last_item=true and last_job_item=true (Last PR or last nested item from last PR of last repository)**
- Updates step status to finished and sends WebSocket notification
- Forwards last_item=true and last_job_item=true to EmbeddingWorker

### **Embedding Worker**

**When first_item=true (First PR of first Repository)**
- Updates step status to running and sends WebSocket notification

**When last_item=true and last_job_item=true (Last PR or last nested item from last PR of last repository)**
- Performs all embedding processing
- Updates step status AND overall job status to finished
- Sends WebSocket notification for UI update

---

---

## Critical Rules for GitHub Step 2

1. **last_repo and last_pr Flags (Extraction Worker Internal)**
   - `last_repo=true` is sent to extraction worker when processing the last repository
   - `last_pr=true` is set by extraction worker when queuing nested extraction for the last PR that needs nested pagination
   - These flags help extraction worker determine when to set `last_item=true, last_job_item=true`
   - **Rule for PR queuing**: Set `last_item=true, last_job_item=true` on last PR ONLY when:
     - This is the last PR in the page AND no more PR pages
     - AND no nested pagination needed for ANY PR
     - AND `last_repo=true` AND `last_pr=true`

2. **Nested Type Ordering**
   - Nested types are processed in fixed order: commits → reviews → comments → reviewThreads
   - When queuing nested extraction for a PR needing pagination:
     - Set `last_pr=false` on all nested types EXCEPT the last one
     - Set `last_pr=true` ONLY on the final nested type that needs extraction
   - Example: If PR needs commits and comments only:
     - commits: `last_pr=false`
     - comments: `last_pr=true` ✅ (last nested type)

3. **Flag Propagation Through Pipeline**
   - Extraction determines when last_item=true and last_job_item=true based on PR pages and nested pagination
   - Transform forwards these flags to Embedding
   - Embedding uses last_job_item=true to finalize the job
   - **Status Update Rule**: Only send "finished" status when sending `last_item=true` to transform

4. **Nested Pagination Flag Handling**
   - Nested extraction workers receive `last_pr=true` on the final nested type
   - When processing nested pages with `last_pr=true`:
     - If more pages exist: queue next page with `last_item=false, last_job_item=false, last_pr=true`
     - If final page: send to transform with `last_item=true, last_job_item=true, last_pr=true`
   - This ensures job completion only after all nested data is processed

5. **Multiple PR Pages**
   - When more PR pages exist: queue next page with last_item=false, last_job_item=false, last_repo=true
   - Current page PRs sent to Transform with last_item=false, last_job_item=false
   - Extraction continues until reaching final PR page

6. **No Nested Pagination Needed**
   - When last PR page has no nested pagination: send last_item=true, last_job_item=true on last PR
   - Job completion happens immediately after Transform and Embedding process this message

---

## GitHub Completion Scenarios

**Scenario 1: Normal Flow (Repositories + PRs with Nested Data)**
```
Step 1 (repositories) → Step 2 (PRs + nested pagination)
                                        ↓
                        last_item=true, last_job_item=true
                        (on last nested item of last PR)
                                        ↓
                                Job FINISHED
```

**Scenario 2: No Repositories (Skip to PRs)**
```
Step 1 (completion message) → Step 2 (PRs + nested pagination)
                                        ↓
                        last_item=true, last_job_item=true
                        (on last nested item of last PR)
                                        ↓
                                Job FINISHED
```

**Scenario 3: No PRs Found**
```
Step 1 (repositories) → Step 2 (no PRs)
                                        ↓
                        last_item=true, last_job_item=true
                        (on completion message)
                                        ↓
                                Job FINISHED
```

**Scenario 4: PRs with No Nested Pagination**
```
Step 1 (repositories) → Step 2 (PRs only, no nested)
                                        ↓
                        last_item=true, last_job_item=true
                        (on last PR message)
                                        ↓
                                Job FINISHED
```

---

## GitHub Completion Flow

1. **Extraction Worker** on final step (PRs) sends last_item=true, last_job_item=true when:
   - Last PR page with no nested pagination: on last PR message
   - Last PR page with nested pagination: on last nested type message
   - No PRs found: on completion message with raw_data_id=None

2. **Transform Worker** receives message with last_job_item=true:
   - Recognizes as job completion signal
   - Sends "finished" status for transform step (because last_item=true)
   - Forwards to embedding with last_job_item=true

3. **Embedding Worker** receives message with last_job_item=true:
   - Sends "finished" status for embedding step (because `last_item=True`)
   - Calls `_complete_etl_job()` (because `last_job_item=True`)
   - Sets overall status to FINISHED

4. **UI Timer** detects FINISHED:
   - Calls `checkJobCompletion` endpoint
   - Checks if all steps are finished (or idle for Step 2 if no PRs)
   - Waits 30 seconds, then calls `resetJobStatus`
   - Resets all steps to "idle" and overall to "READY"

---

## Token Forwarding Through GitHub Pipeline

Every GitHub job uses a **unique token (UUID)** that is generated at job start and forwarded through ALL stages for job tracking and correlation.

### Token Flow for Each Step

**Step 1: github_repositories**
```
Job Start (token generated)
    ↓ token in message
Extraction → Transform Queue
    ↓ token in message
Transform → Embedding Queue
    ↓ token in message
Embedding Worker
```

**Step 2: github_prs_commits_reviews_comments (with nested pagination)**
```
Extraction (Initial PR page) → Transform Queue
    ↓ token in message
Extraction (Nested pagination) → Extraction Queue (line 1353 in github_extraction.py)
    ↓ token in message (CRITICAL: Must forward token for nested extraction)
Extraction Worker (processes nested page)
    ↓ token in message
Transform → Embedding Queue
    ↓ token in message
Embedding Worker
```

### Critical Implementation Points

1. **github_extraction.py line 1353**: Must include `token=token` when queuing nested extraction jobs
   - This ensures nested pagination messages (commits, reviews, comments) maintain the token
   - Without this, token becomes `None` after first nested page

2. **transform_worker.py line 4155**: Extract token from message for repositories step
   - `token = message.get('token') if message else None`

3. **transform_worker.py line 4189**: Forward token when queuing repositories to embedding
   - `token=token` parameter in `publish_embedding_job()`

4. **transform_worker.py line 3676**: Extract token from message for PR/nested step
   - `token = message.get('token') if message else None`

5. **transform_worker.py line 5077**: Forward token when queuing PR entities to embedding
   - `token=token` parameter in `publish_embedding_job()`

### Token Verification for GitHub

To verify token is properly forwarded through nested pagination:
1. Check logs for token value in first repository message
2. Verify same token appears in first PR message
3. Verify same token appears in nested extraction messages (commits, reviews, comments)
4. Confirm token is present in all embedding worker logs
5. Token should NOT become `None` at any stage, especially during nested pagination

---

## Date Forwarding for Incremental Sync

Every GitHub job uses **two date fields** for incremental sync:
- `old_last_sync_date` (or `last_sync_date`): Used for filtering data during extraction (from previous job run)
- `new_last_sync_date`: Extraction start time that will be saved for the next incremental run

### Date Flow Through Pipeline

**Step 1: github_repositories**
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

**Step 2: github_prs_commits_reviews_comments**
```
Extraction Worker (receives dates from Step 1)
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

1. **Extraction Worker**: Sets `new_last_sync_date = datetime.now()` at extraction start
   - This captures the extraction start time for the next incremental run
   - Uses `old_last_sync_date` for filtering (e.g., `pushed:2025-11-11..2025-11-12`)

2. **Transform Worker - Regular Processing**: Must forward both dates to embedding
   - `github_transform_worker.py` line 265: Extract `new_last_sync_date` from message
   - `github_transform_worker.py` line 444: Forward `new_last_sync_date` to embedding queue

3. **Transform Worker - Completion Messages**: Must forward both dates to embedding
   - `github_transform_worker.py` line 188: Forward `new_last_sync_date` for repositories completion
   - `github_transform_worker.py` line 213: Forward `new_last_sync_date` for PRs completion

4. **Embedding Worker**: Updates database when `last_job_item=True`
   - Calls `_complete_etl_job(job_id, tenant_id, new_last_sync_date)`
   - Updates `last_sync_date` column in `etl_jobs` table
   - Next run will use this value as `old_last_sync_date`

### Incremental Sync Behavior

**First Run (no last_sync_date in database)**
- `old_last_sync_date = None`
- Extraction uses 2-year default: `pushed:2023-11-12..2025-11-11`
- Sets `new_last_sync_date = 2025-11-11`
- Embedding worker updates database: `last_sync_date = 2025-11-11`

**Second Run (last_sync_date exists in database)**
- `old_last_sync_date = 2025-11-11` (from database)
- Extraction uses incremental range: `pushed:2025-11-11..2025-11-12`
- Sets `new_last_sync_date = 2025-11-12`
- Embedding worker updates database: `last_sync_date = 2025-11-12`
- **Saves API quota**: Only fetches repositories/PRs updated since last run

### Date Verification for GitHub

To verify dates are properly forwarded:
1. Check logs for `new_last_sync_date` in extraction worker output
2. Verify both dates appear in transform queue messages
3. Verify both dates appear in embedding queue messages
4. Confirm `last_sync_date` is updated in database after job completion
5. Verify next run uses previous `new_last_sync_date` as `old_last_sync_date`

