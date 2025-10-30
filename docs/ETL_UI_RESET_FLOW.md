# ETL UI Reset Flow

This document explains how the UI detects job completion and resets the job status back to READY after a successful ETL job.

---

## Overview

After an ETL job completes (overall status = FINISHED), the UI needs to:
1. Verify all steps are truly finished
2. Wait 30 seconds
3. Reset the job status back to READY
4. Allow the next job to run

This flow prevents race conditions and ensures proper job orchestration.

---

## Step 1: Job Completion Detection

When the embedding worker receives a message with `last_job_item=True`:

1. **Embedding Worker** calls `_complete_etl_job()`
   - Sets overall status to FINISHED
   - Updates `last_run_finished_at` timestamp
   - Updates `last_sync_date` with the extraction date

2. **WebSocket Message** is sent to UI:
   ```json
   {
     "overall": "FINISHED",
     "steps": {
       "step_name": {
         "extraction": "finished",
         "transform": "finished",
         "embedding": "finished"
       }
     }
   }
   ```

3. **UI Timer** starts:
   - Detects overall status = FINISHED
   - Waits 30 seconds
   - Calls `checkJobCompletion` endpoint

---

## Step 2: checkJobCompletion Endpoint

This endpoint verifies that ALL steps are truly finished before allowing reset.

### For Jira Jobs

All 4 steps must be finished:
```
jira_projects_and_issue_types: extraction=finished, transform=finished, embedding=finished
jira_statuses_and_relationships: extraction=finished, transform=finished, embedding=finished
jira_issues_with_changelogs: extraction=finished, transform=finished, embedding=finished
jira_dev_status: extraction=finished, transform=finished, embedding=finished
```

### For GitHub Jobs

Step 1 must be finished, Step 2 can be finished OR idle:
```
github_repositories: extraction=finished, transform=finished, embedding=finished
github_prs_commits_reviews_comments: 
  - Can be: extraction=finished, transform=finished, embedding=finished (if PRs were extracted)
  - OR: extraction=idle, transform=idle, embedding=idle (if no PRs were extracted)
```

### Retry Logic

If not all steps are finished:
- Retry with exponential backoff:
  - 1st retry: 30 seconds
  - 2nd retry: 60 seconds
  - 3rd retry: 180 seconds (3 minutes)
  - 4th retry: 300 seconds (5 minutes)
- After 5 minutes, give up and show error to user

### Success Response

```json
{
  "all_finished": true,
  "steps_status": {
    "step_name": {
      "extraction": "finished",
      "transform": "finished",
      "embedding": "finished"
    }
  }
}
```

---

## Step 3: UI Waits 30 Seconds

After `checkJobCompletion` returns `all_finished=true`:

1. UI displays countdown timer (30 seconds)
2. User sees: "Job completed. Resetting in 30 seconds..."
3. After 30 seconds, UI calls `resetJobStatus` endpoint

### Why Wait 30 Seconds?

- Allows any pending WebSocket messages to be processed
- Ensures database transactions are committed
- Prevents race conditions with job scheduler
- Gives time for any cleanup operations

---

## Step 4: resetJobStatus Endpoint

This endpoint resets the job back to READY state.

### What It Does

1. Sets all step statuses to "idle":
   ```json
   {
     "extraction": "idle",
     "transform": "idle",
     "embedding": "idle"
   }
   ```

2. Sets overall status to "READY"

3. Clears any error messages

4. Updates `next_run` timestamp for job scheduler

### Response

```json
{
  "success": true,
  "overall": "READY",
  "steps": {
    "step_name": {
      "extraction": "idle",
      "transform": "idle",
      "embedding": "idle"
    }
  }
}
```

---

## Step 5: Job Scheduler Picks Up Next Job

After reset, the job scheduler:

1. Detects job status = READY
2. Checks if job is active
3. Checks if integration is active
4. Queues extraction job for next step or next job

---

## Complete Flow Diagram

```
Embedding Worker
    ↓
_complete_etl_job() called
    ↓
overall status = FINISHED
    ↓
WebSocket message sent to UI
    ↓
UI Timer Starts (30 seconds)
    ↓
UI calls checkJobCompletion
    ↓
Endpoint verifies all steps finished
    ↓
If not finished: retry with backoff
If finished: return all_finished=true
    ↓
UI waits 30 seconds
    ↓
UI calls resetJobStatus
    ↓
overall status = READY
all steps = idle
    ↓
Job Scheduler picks up next job
    ↓
Next extraction job queued
```

---

## Common Issues & Solutions

### Issue: UI Timer Keeps Retrying (300s countdown)

**Cause**: `checkJobCompletion` returns `all_finished=false` because a step is still "running"

**Solution**: 
- Verify completion message has `last_item=True` and `last_job_item=True`
- Verify transform worker sends "finished" status when receiving completion
- Verify embedding worker sends "finished" status when receiving completion
- Check logs for any errors in transform or embedding workers

### Issue: Job Status Stuck on FINISHED

**Cause**: `resetJobStatus` endpoint not called or failed

**Solution**:
- Check UI console for errors
- Manually call `resetJobStatus` endpoint
- Verify backend service is running
- Check database for job status

### Issue: Next Job Not Starting After Reset

**Cause**: Job scheduler not picking up the READY job

**Solution**:
- Verify job is marked as active
- Verify integration is marked as active
- Check job scheduler logs
- Verify next_run timestamp is in the past

### Issue: Multiple Jobs Running Simultaneously

**Cause**: Job scheduler not respecting job orchestration rules

**Solution**:
- Verify only one job per integration is RUNNING at a time
- Check job scheduler logic for concurrent job prevention
- Verify job status transitions are atomic

---

## WebSocket Status Updates During Reset

The UI receives WebSocket messages during the reset flow:

1. **Job Completion**:
   ```json
   {
     "overall": "FINISHED",
     "steps": { ... }
   }
   ```

2. **After Reset**:
   ```json
   {
     "overall": "READY",
     "steps": { ... }
   }
   ```

These messages update the UI in real-time without requiring page refresh.

