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
- **After queuing all repositories to transform**: Queues extraction job for Step 2 (PRs with nested data)
- Transform processes each message and queues to embedding with same flags
- Embedding processes each message
- When `last_item=True`: sends "finished" status

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

## Flag Handling: first_item, last_item, last_job_item

### **Extraction Worker**

**When first_item=true (First PR of first Repository)**
- Updates step status to running and sends WebSocket notification
- Forwards first_item=true to the very FIRST PR message sent to TransformWorker

**When last_item=true and last_job_item=true (Last Repository)**
- Performs GraphQL request and checks: **Is this the last PR page?**

  **Case 1.1: YES - This is the last PR page**
  - Splits response by PRs and loops through checking for nested pagination needs
  - **Is there any nested pagination needed in any of those PRs?**

    **Case 1.1.2.1: NO nested pagination needed**
    - Sends last_item=true and last_job_item=true to the LAST PR message to TransformWorker

    **Case 1.1.2.2: YES nested pagination needed**
    - Sends ALL PR messages to TransformWorker with last_item=false, last_job_item=false
    - Loops each PR needing nested pagination and queues nested extraction jobs with last_item=false, last_job_item=false
    - On the LAST nested type (commits → reviews → comments → reviewThreads order):
      - Sets last_item=true, last_job_item=true on this extraction message
    - Nested extraction workers continue processing pages and forward flags through
    - On final nested page: sends last_item=true, last_job_item=true to TransformWorker

  **Case 1.2: NO - More PR pages exist**
  - Queues next PR page to ExtractionWorker with last_item=true, last_job_item=true
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

1. **Flag Propagation Through Pipeline**
   - Extraction determines when last_item=true and last_job_item=true based on PR pages and nested pagination
   - Transform forwards these flags to Embedding
   - Embedding uses last_job_item=true to finalize the job

2. **Nested Pagination Flag Handling**
   - Nested extraction workers receive and forward flags through all pages
   - Only the LAST nested type of the LAST PR gets last_item=true, last_job_item=true
   - This ensures job completion only after all nested data is processed

3. **Multiple PR Pages**
   - When more PR pages exist: queue next page with last_item=true, last_job_item=true
   - Current page PRs sent to Transform with last_item=false, last_job_item=false
   - Extraction continues until reaching final PR page

4. **No Nested Pagination Needed**
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

