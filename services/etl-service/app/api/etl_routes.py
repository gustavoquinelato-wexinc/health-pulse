"""
REST API routes for ETL job management and execution.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db_session, get_database
from app.core.config import get_settings
from app.core.utils import DateTimeHelper
from app.models.unified_models import Integration, Project, Issue, Commit, PullRequest
from app.schemas.api_schemas import (
    HealthResponse, JobRunRequest, JobRunResponse, JobStatusResponse,
    JobScheduleRequest, JobScheduleResponse, DataSummaryResponse,
    IssuesListResponse, CommitsListResponse, PullRequestsListResponse,
    JobStatus, IssueInfo, CommitInfo, PullRequestInfo
)
# REMOVED: Old job_manager import - now using new orchestration system

logger = logging.getLogger(__name__)
settings = get_settings()

# API routes router
router = APIRouter()

# In-memory storage for job status (In production, use Redis or database)
job_status_store = {}


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Checks application health status and dependencies",
    response_description="Application health status",
    tags=["Health Check"]
)
async def health_check(_: Session = Depends(get_db_session)):
    """
    Checks application health status.

    This endpoint verifies:
    - General application status
    - Snowflake database connectivity
    - Application version
    - Check timestamp

    Returns status 200 even when there are issues, but indicates state in 'status' field.
    """
    try:
        database = get_database()
        db_connected = database.is_connection_alive()
        
        return HealthResponse(
            status="healthy" if db_connected else "unhealthy",
            version=settings.APP_VERSION,
            database_connected=db_connected
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")


@router.post(
    "/etl/jira/extract",
    response_model=JobRunResponse,
    summary="Execute Jira Extraction Job",
    description="Starts a deep Jira data extraction job including dev_status",
    response_description="Information about the started job",
    responses={
        200: {
            "description": "Job started successfully",
            "content": {
                "application/json": {
                    "example": {
                        "job_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "running",
                        "message": "Jira extraction job started successfully",
                        "started_at": "2023-01-01T10:00:00"
                    }
                }
            }
        },
        500: {"description": "Internal server error"}
    }
)
async def run_jira_job(
    request: JobRunRequest,
    background_tasks: BackgroundTasks,
    _: Session = Depends(get_db_session)
):
    """
    Executes deep Jira data extraction job.

    This endpoint starts a background job that:

    1. **Extracts Issues**: Fetches all Jira issues using JQL
    2. **Processes Data**: Normalizes and validates extracted data
    3. **Extracts Dev Data**: For each issue, fetches development data
    4. **Loads to Snowflake**: Performs UPSERT of data to data warehouse

    ### Optional Parameters:

    - `force_full_sync`: Forces complete sync ignoring last date
    - `projects`: List of specific projects to synchronize
    - `include_dev_data`: Whether to include development data

    ### Asynchronous Process:

    The job runs in background. Use the returned `job_id` to track
    progress through the `/etl/jobs/{job_id}` endpoint.
    """
    try:
        job_id = str(uuid.uuid4())
        start_time = DateTimeHelper.now_utc()
        
        # Register job as started
        job_status_store[job_id] = {
            'job_id': job_id,
            'status': JobStatus.RUNNING,
            'started_at': start_time,
            'request': request.model_dump(),
            'progress_percentage': 0,
            'current_step': 'Initializing'
        }
        
        # Execute job in background
        background_tasks.add_task(
            _execute_jira_job,
            job_id,
            request
        )
        
        return JobRunResponse(
            job_id=job_id,
            status=JobStatus.RUNNING,
            message="Jira extraction job started successfully",
            started_at=start_time
        )
        
    except Exception as e:
        logger.error(f"Failed to start Jira job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start job: {str(e)}")


@router.get("/etl/jobs/{job_id}", response_model=JobStatusResponse)
async def get_jira_job_status(job_id: str):
    """Gets status of a specific job."""
    if job_id not in job_status_store:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = job_status_store[job_id]
    
    # Calculate duration if job was completed
    duration = None
    if job_data.get('completed_at') and job_data.get('started_at'):
        duration = (job_data['completed_at'] - job_data['started_at']).total_seconds()
    
    return JobStatusResponse(
        job_id=job_data['job_id'],
        status=job_data['status'],
        started_at=job_data.get('started_at'),
        completed_at=job_data.get('completed_at'),
        duration_seconds=duration,
        issues_processed=job_data.get('issues_processed'),
        commits_extracted=job_data.get('commits_extracted'),
        pull_requests_extracted=job_data.get('pull_requests_extracted'),
        errors=job_data.get('errors'),
        progress_percentage=job_data.get('progress_percentage'),
        current_step=job_data.get('current_step')
    )


@router.get("/etl/jobs", response_model=JobStatusResponse)
async def get_latest_jira_job_status():
    """Gets status of the latest executed job."""
    if not job_status_store:
        raise HTTPException(status_code=404, detail="No jobs found")
    
    # Find most recent job
    latest_job_id = max(job_status_store.keys(), 
                       key=lambda k: job_status_store[k]['started_at'])
    
    return await get_jira_job_status(latest_job_id)


@router.get("/etl/data/summary", response_model=DataSummaryResponse)
async def get_data_summary(db: Session = Depends(get_db_session)):
    """Gets data summary in the system."""
    try:
        integrations_count = db.query(func.count(Integration.integration_id)).scalar()
        projects_count = db.query(func.count(Project.project_id)).scalar()
        issues_count = db.query(func.count(Issue.issue_id)).scalar()
        commits_count = db.query(func.count(Commit.sha)).scalar()
        pull_requests_count = db.query(func.count(PullRequest.pull_request_id)).scalar()

        # Get last sync
        last_sync = db.query(func.max(Integration.last_sync_at)).scalar()
        
        return DataSummaryResponse(
            integrations_count=integrations_count,
            projects_count=projects_count,
            issues_count=issues_count,
            commits_count=commits_count,
            pull_requests_count=pull_requests_count,
            last_sync_at=last_sync
        )
        
    except Exception as e:
        logger.error(f"Failed to get data summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get data summary")


async def _execute_jira_job(job_id: str, request: JobRunRequest):
    """Executes Jira job in background with detailed logging."""
    import traceback

    try:
        logger.info(f"Starting job {job_id} with request: {request.model_dump()}")

        # Update status - Initializing
        job_status_store[job_id].update({
            'current_step': 'Initializing job',
            'progress_percentage': 5,
            'debug_info': {'step': 'init', 'timestamp': datetime.now().isoformat()}
        })

        # Update status - Testing connections
        job_status_store[job_id].update({
            'current_step': 'Testing connections',
            'progress_percentage': 10
        })

        # Test connections before starting
        try:
            database = get_database()
            if not database.is_connection_alive():
                raise Exception("Snowflake connection not available")
            logger.info(f"Job {job_id}: Snowflake connection verified")
        except Exception as e:
            logger.error(f"Job {job_id}: Snowflake connection failed: {e}")
            raise Exception(f"Database connection failed: {str(e)}")

        # Update status - Starting extraction
        job_status_store[job_id].update({
            'current_step': 'Starting Jira extraction',
            'progress_percentage': 15
        })

        logger.info(f"Job {job_id}: Starting Jira sync via new orchestration system")

        # Execute extraction using new orchestration system
        from app.jobs.orchestrator import trigger_jira_sync
        result = await trigger_jira_sync()

        logger.info(f"Job {job_id}: Jira sync completed with result: {result}")

        # Update status with result
        final_status = JobStatus.SUCCESS if result['status'] == 'success' else JobStatus.ERROR

        job_status_store[job_id].update({
            'status': final_status,
            'completed_at': datetime.now(),
            'issues_processed': result.get('issues_processed', 0),
            'commits_extracted': result.get('commits_extracted', 0),
            'pull_requests_extracted': result.get('pull_requests_extracted', 0),
            'errors': result.get('errors', []),
            'progress_percentage': 100,
            'current_step': 'Completed successfully' if final_status == JobStatus.SUCCESS else 'Completed with errors',
            'debug_info': {
                'final_result': result,
                'completion_timestamp': datetime.now().isoformat()
            }
        })

        if final_status == JobStatus.SUCCESS:
            logger.info(f"Job {job_id} completed successfully")
        else:
            logger.error(f"Job {job_id} completed with errors: {result.get('errors', [])}")

    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()

        logger.error(f"Job {job_id} failed with exception: {error_msg}")
        logger.error(f"Job {job_id} traceback: {error_traceback}")

        job_status_store[job_id].update({
            'status': JobStatus.ERROR,
            'completed_at': datetime.now(),
            'errors': [error_msg],
            'progress_percentage': 0,
            'current_step': f'Failed: {error_msg}',
            'debug_info': {
                'error_traceback': error_traceback,
                'error_timestamp': datetime.now().isoformat()
            }
        })


@router.get("/status", response_class=HTMLResponse)
async def job_status_page():
    """Internal job status page with management controls."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ETL Service - Job Status</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                padding: 30px;
            }
            .header {
                border-bottom: 2px solid #e9ecef;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }
            .header h1 {
                color: #2c3e50;
                margin: 0;
                font-size: 2.5em;
            }
            .header p {
                color: #6c757d;
                margin: 10px 0 0 0;
                font-size: 1.1em;
            }
            .status-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .status-card {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 20px;
            }
            .status-card h3 {
                margin: 0 0 15px 0;
                color: #495057;
                font-size: 1.2em;
            }
            .status-value {
                font-size: 1.8em;
                font-weight: bold;
                margin-bottom: 5px;
            }
            .status-running { color: #007bff; }
            .status-success { color: #28a745; }
            .status-error { color: #dc3545; }
            .status-idle { color: #6c757d; }
            .controls {
                display: flex;
                gap: 15px;
                margin-bottom: 30px;
                flex-wrap: wrap;
            }
            .btn {
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 1em;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
                text-decoration: none;
                display: inline-block;
                text-align: center;
            }
            .btn-primary {
                background-color: #007bff;
                color: white;
            }
            .btn-primary:hover {
                background-color: #0056b3;
            }
            .btn-danger {
                background-color: #dc3545;
                color: white;
            }
            .btn-danger:hover {
                background-color: #c82333;
            }
            .btn-secondary {
                background-color: #6c757d;
                color: white;
            }
            .btn-secondary:hover {
                background-color: #545b62;
            }
            .refresh-info {
                text-align: center;
                color: #6c757d;
                margin-top: 20px;
                font-style: italic;
            }
            .alert {
                padding: 15px;
                margin-bottom: 20px;
                border: 1px solid transparent;
                border-radius: 6px;
            }
            .alert-info {
                color: #0c5460;
                background-color: #d1ecf1;
                border-color: #bee5eb;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 ETL Service Status</h1>
                <p>Monitor and manage Jira extraction jobs</p>
            </div>

            <div class="alert alert-info">
                <strong>📊 Real-time Status:</strong> This page shows the current status of scheduled and manual jobs.
                Use the controls below to manage job execution.
            </div>

            <div class="status-grid">
                <div class="status-card">
                    <h3>📅 Next Scheduled Run</h3>
                    <div class="status-value status-idle" id="next-run">Loading...</div>
                    <small>Based on 24-hour interval</small>
                </div>
                <div class="status-card">
                    <h3>⏱️ Last Run Status</h3>
                    <div class="status-value" id="last-status">Loading...</div>
                    <small id="last-run-time">Checking...</small>
                </div>
                <div class="status-card">
                    <h3>🔄 Current Job</h3>
                    <div class="status-value" id="current-status">Loading...</div>
                    <div id="progress-container" style="margin-top: 10px; display: none;">
                        <div style="width: 100%; height: 20px; background-color: #e9ecef; border-radius: 10px; overflow: hidden;">
                            <div id="progress-fill" style="height: 100%; background-color: #007bff; transition: width 0.3s ease; width: 0%"></div>
                        </div>
                        <small id="current-step">Initializing...</small>
                    </div>
                </div>
                <div class="status-card">
                    <h3>📈 Statistics</h3>
                    <div id="stats-content">
                        <div>Issues: <span id="issues-count">-</span></div>
                        <div>Commits: <span id="commits-count">-</span></div>
                        <div>PRs: <span id="prs-count">-</span></div>
                    </div>
                </div>
            </div>

            <div class="status-grid" id="debug-section" style="display: none;">
                <div class="status-card">
                    <h3>🐛 Debug Information</h3>
                    <div id="debug-content">
                        <div><strong>Job ID:</strong> <span id="debug-job-id">-</span></div>
                        <div><strong>Started:</strong> <span id="debug-started">-</span></div>
                        <div><strong>Duration:</strong> <span id="debug-duration">-</span></div>
                        <div><strong>Progress:</strong> <span id="debug-progress">-</span></div>
                    </div>
                </div>
                <div class="status-card">
                    <h3>⚠️ Errors & Warnings</h3>
                    <div id="errors-content" style="max-height: 200px; overflow-y: auto;">
                        <div id="errors-list">No errors</div>
                    </div>
                </div>
                <div class="status-card">
                    <h3>📝 Recent Logs</h3>
                    <div id="logs-content" style="max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 0.9em;">
                        <div id="logs-list">Loading logs...</div>
                    </div>
                </div>
                <div class="status-card">
                    <h3>🔧 Debug Actions</h3>
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <button class="btn btn-secondary" onclick="downloadLogs()">📥 Download Logs</button>
                        <button class="btn btn-secondary" onclick="viewJobDetails()">🔍 View Job Details</button>
                        <button class="btn btn-secondary" onclick="testConnections()">🔗 Test Connections</button>
                    </div>
                </div>
            </div>

            <div class="controls">
                <button class="btn btn-primary" onclick="startJob()">▶️ Start Manual Job</button>
                <button class="btn btn-danger" onclick="stopJob()" id="stop-btn" disabled>⏹️ Stop Current Job</button>
                <button class="btn btn-secondary" onclick="refreshStatus()">🔄 Refresh Status</button>
                <button class="btn btn-secondary" onclick="toggleDebug()" id="debug-toggle">🐛 Show Debug Info</button>
                <a href="/docs" class="btn btn-secondary">📚 API Documentation</a>
            </div>

            <div class="refresh-info">
                🔄 Page auto-refreshes every 30 seconds | Last updated: <span id="last-updated">Never</span>
            </div>
        </div>

        <script>
            let currentJobId = null;
            let autoRefreshInterval = null;

            function startAutoRefresh() {
                if (autoRefreshInterval) clearInterval(autoRefreshInterval);
                autoRefreshInterval = setInterval(refreshStatus, 30000);
            }

            async function refreshStatus() {
                try {
                    document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();

                    const response = await fetch('/api/v1/etl/jobs');
                    if (response.ok) {
                        const jobData = await response.json();
                        updateCurrentJobStatus(jobData);
                    } else if (response.status === 404) {
                        updateCurrentJobStatus(null);
                    }

                    await updateSchedulerInfo();
                    await updateDataSummary();

                } catch (error) {
                    console.error('Failed to refresh status:', error);
                }
            }

            function updateCurrentJobStatus(jobData) {
                const statusElement = document.getElementById('current-status');
                const progressContainer = document.getElementById('progress-container');
                const progressFill = document.getElementById('progress-fill');
                const currentStep = document.getElementById('current-step');
                const stopBtn = document.getElementById('stop-btn');

                if (!jobData) {
                    statusElement.textContent = 'No jobs running';
                    statusElement.className = 'status-value status-idle';
                    progressContainer.style.display = 'none';
                    stopBtn.disabled = true;
                    currentJobId = null;
                    updateDebugInfo(null);
                    return;
                }

                currentJobId = jobData.job_id;
                statusElement.textContent = jobData.status;
                statusElement.className = `status-value status-${jobData.status.toLowerCase()}`;

                if (jobData.status === 'RUNNING') {
                    progressContainer.style.display = 'block';
                    progressFill.style.width = `${jobData.progress_percentage || 0}%`;
                    currentStep.textContent = jobData.current_step || 'Processing...';
                    stopBtn.disabled = false;
                } else {
                    progressContainer.style.display = 'none';
                    stopBtn.disabled = true;
                }

                const lastStatus = document.getElementById('last-status');
                const lastRunTime = document.getElementById('last-run-time');

                if (jobData.status !== 'RUNNING') {
                    lastStatus.textContent = jobData.status;
                    lastStatus.className = `status-value status-${jobData.status.toLowerCase()}`;

                    if (jobData.completed_at) {
                        const completedTime = new Date(jobData.completed_at).toLocaleString();
                        const duration = jobData.duration_seconds ?
                            `${Math.round(jobData.duration_seconds)}s` : 'Unknown';
                        lastRunTime.textContent = `Completed: ${completedTime} (${duration})`;
                    }
                }

                // Update debug information
                updateDebugInfo(jobData);
            }

            function updateDebugInfo(jobData) {
                if (!jobData) {
                    document.getElementById('debug-job-id').textContent = '-';
                    document.getElementById('debug-started').textContent = '-';
                    document.getElementById('debug-duration').textContent = '-';
                    document.getElementById('debug-progress').textContent = '-';
                    document.getElementById('errors-list').textContent = 'No errors';
                    return;
                }

                document.getElementById('debug-job-id').textContent = jobData.job_id || '-';
                document.getElementById('debug-started').textContent = jobData.started_at ?
                    new Date(jobData.started_at).toLocaleString() : '-';

                if (jobData.duration_seconds) {
                    document.getElementById('debug-duration').textContent = `${Math.round(jobData.duration_seconds)}s`;
                } else if (jobData.started_at) {
                    const start = new Date(jobData.started_at);
                    const now = new Date();
                    const duration = Math.round((now - start) / 1000);
                    document.getElementById('debug-duration').textContent = `${duration}s (running)`;
                } else {
                    document.getElementById('debug-duration').textContent = '-';
                }

                document.getElementById('debug-progress').textContent =
                    `${jobData.progress_percentage || 0}% - ${jobData.current_step || 'Unknown'}`;

                // Update errors
                const errorsList = document.getElementById('errors-list');
                if (jobData.errors && jobData.errors.length > 0) {
                    errorsList.innerHTML = jobData.errors.map(error =>
                        `<div style="color: #dc3545; margin-bottom: 5px;">❌ ${error}</div>`
                    ).join('');
                } else {
                    errorsList.textContent = 'No errors';
                }
            }

            function toggleDebug() {
                const debugSection = document.getElementById('debug-section');
                const toggleBtn = document.getElementById('debug-toggle');

                if (debugSection.style.display === 'none') {
                    debugSection.style.display = 'grid';
                    toggleBtn.textContent = '🐛 Hide Debug Info';
                    updateLogs();
                } else {
                    debugSection.style.display = 'none';
                    toggleBtn.textContent = '🐛 Show Debug Info';
                }
            }

            async function updateLogs() {
                try {
                    const response = await fetch('/api/v1/logs/recent');
                    if (response.ok) {
                        const logs = await response.json();
                        const logsList = document.getElementById('logs-list');
                        logsList.innerHTML = logs.map(log =>
                            `<div style="margin-bottom: 2px;">${log.timestamp} [${log.level}] ${log.message}</div>`
                        ).join('');
                    } else {
                        document.getElementById('logs-list').textContent = 'Logs not available';
                    }
                } catch (error) {
                    document.getElementById('logs-list').textContent = 'Failed to load logs';
                }
            }

            async function downloadLogs() {
                try {
                    const response = await fetch('/api/v1/logs/download');
                    if (response.ok) {
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `etl-logs-${new Date().toISOString().split('T')[0]}.log`;
                        document.body.appendChild(a);
                        a.click();
                        window.URL.revokeObjectURL(url);
                        document.body.removeChild(a);
                    } else {
                        alert('Failed to download logs');
                    }
                } catch (error) {
                    alert(`Error downloading logs: ${error.message}`);
                }
            }

            async function viewJobDetails() {
                if (!currentJobId) {
                    alert('No job selected');
                    return;
                }

                try {
                    const response = await fetch(`/api/v1/etl/jobs/${currentJobId}`);
                    if (response.ok) {
                        const jobData = await response.json();
                        const details = JSON.stringify(jobData, null, 2);
                        const newWindow = window.open('', '_blank');
                        newWindow.document.write(`
                            <html>
                                <head><title>Job Details - ${currentJobId}</title></head>
                                <body>
                                    <h1>Job Details</h1>
                                    <pre style="background: #f5f5f5; padding: 20px; border-radius: 5px;">${details}</pre>
                                </body>
                            </html>
                        `);
                    } else {
                        alert('Failed to get job details');
                    }
                } catch (error) {
                    alert(`Error getting job details: ${error.message}`);
                }
            }

            async function testConnections() {
                try {
                    const response = await fetch('/api/v1/debug/connections');
                    if (response.ok) {
                        const result = await response.json();
                        let message = 'Connection Test Results:\\n\\n';
                        for (const [service, status] of Object.entries(result)) {
                            message += `${service}: ${status.status} ${status.status === 'ok' ? '✅' : '❌'}\\n`;
                            if (status.error) {
                                message += `  Error: ${status.error}\\n`;
                            }
                        }
                        alert(message);
                    } else {
                        alert('Failed to test connections');
                    }
                } catch (error) {
                    alert(`Error testing connections: ${error.message}`);
                }
            }

            async function updateSchedulerInfo() {
                try {
                    const response = await fetch('/api/v1/scheduler/status');
                    if (response.ok) {
                        const data = await response.json();
                        if (data.next_run) {
                            const nextRun = new Date(data.next_run);
                            document.getElementById('next-run').textContent = nextRun.toLocaleString();
                        } else {
                            document.getElementById('next-run').textContent = 'Not scheduled';
                        }
                    }
                } catch (error) {
                    console.error('Failed to get scheduler info:', error);
                }
            }

            async function updateDataSummary() {
                try {
                    const response = await fetch('/api/v1/etl/data/summary');
                    if (response.ok) {
                        const data = await response.json();
                        document.getElementById('issues-count').textContent = data.total_issues || 0;
                        document.getElementById('commits-count').textContent = data.total_commits || 0;
                        document.getElementById('prs-count').textContent = data.total_pull_requests || 0;
                    }
                } catch (error) {
                    console.error('Failed to get data summary:', error);
                }
            }

            async function startJob() {
                try {
                    const response = await fetch('/api/v1/etl/jira/extract', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            projects: [],
                            include_dev_data: true
                        })
                    });

                    if (response.ok) {
                        const result = await response.json();
                        alert(`Job started successfully! Job ID: ${result.job_id}`);
                        refreshStatus();
                    } else {
                        const error = await response.json();
                        alert(`Failed to start job: ${error.detail}`);
                    }
                } catch (error) {
                    alert(`Error starting job: ${error.message}`);
                }
            }

            async function stopJob() {
                if (!currentJobId) {
                    alert('No job is currently running');
                    return;
                }

                if (!confirm('Are you sure you want to stop the current job?')) {
                    return;
                }

                try {
                    const response = await fetch(`/api/v1/etl/jobs/${currentJobId}/stop`, {
                        method: 'POST'
                    });

                    if (response.ok) {
                        alert('Job stop requested');
                        refreshStatus();
                    } else {
                        const error = await response.json();
                        alert(`Failed to stop job: ${error.detail}`);
                    }
                } catch (error) {
                    alert(`Error stopping job: ${error.message}`);
                }
            }

            document.addEventListener('DOMContentLoaded', function() {
                refreshStatus();
                startAutoRefresh();
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.post("/etl/jobs/{job_id}/stop")
async def stop_job(job_id: str):
    """Stop a running job."""
    if job_id not in job_status_store:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = job_status_store[job_id]

    if job_data['status'] != JobStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Job is not running")

    # Update job status to stopped
    job_status_store[job_id].update({
        'status': JobStatus.ERROR,
        'completed_at': datetime.now(),
        'errors': ['Job manually stopped'],
        'current_step': 'Stopped by user'
    })

    return {"message": f"Job {job_id} has been stopped"}


@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get scheduler status and next run time."""
    from app.main import get_scheduler

    scheduler = get_scheduler()
    if not scheduler:
        return {"status": "disabled", "message": "Scheduler not available"}

    if not scheduler.running:
        return {"status": "stopped", "message": "Scheduler is not running"}

    jobs = scheduler.get_jobs()
    jira_job = next((job for job in jobs if job.id == "jira_extraction_job"), None)

    if jira_job:
        next_run = jira_job.next_run_time
        return {
            "status": "running",
            "next_run": next_run.isoformat() if next_run else None,
            "job_count": len(jobs)
        }

    return {"status": "running", "message": "No scheduled jobs found"}


@router.get("/logs/recent")
async def get_recent_logs():
    """Get recent log entries for debugging."""
    try:
        import os
        from pathlib import Path

        # Try to read from log file
        log_file = Path("logs/etl_service.log")
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Get last 50 lines
                recent_lines = lines[-50:] if len(lines) > 50 else lines

                logs = []
                for line in recent_lines:
                    if line.strip():
                        # Parse log line (basic parsing)
                        parts = line.strip().split(' ', 3)
                        if len(parts) >= 3:
                            logs.append({
                                "timestamp": parts[0] + " " + parts[1] if len(parts) > 1 else parts[0],
                                "level": parts[2].strip('[]') if len(parts) > 2 else "INFO",
                                "message": parts[3] if len(parts) > 3 else line.strip()
                            })
                        else:
                            logs.append({
                                "timestamp": "Unknown",
                                "level": "INFO",
                                "message": line.strip()
                            })

                return logs
        else:
            return [{"timestamp": "N/A", "level": "INFO", "message": "Log file not found"}]

    except Exception as e:
        return [{"timestamp": "N/A", "level": "ERROR", "message": f"Failed to read logs: {str(e)}"}]


@router.get("/logs/download")
async def download_logs():
    """Download log file for debugging."""
    try:
        import os
        from pathlib import Path
        from fastapi.responses import FileResponse

        log_file = Path("logs/etl_service.log")
        if log_file.exists():
            return FileResponse(
                path=str(log_file),
                filename=f"etl-logs-{datetime.now().strftime('%Y-%m-%d')}.log",
                media_type='text/plain'
            )
        else:
            raise HTTPException(status_code=404, detail="Log file not found")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download logs: {str(e)}")


@router.get("/debug/connections")
async def test_connections():
    """Test all external connections for debugging."""
    results = {}

    # Test Snowflake connection
    try:
        database = get_database()
        if database.is_connection_alive():
            results["snowflake"] = {"status": "ok", "message": "Connection successful"}
        else:
            results["snowflake"] = {"status": "error", "error": "Connection not alive"}
    except Exception as e:
        results["snowflake"] = {"status": "error", "error": str(e)}

    # Test Jira connection
    try:
        from app.core.config import get_settings
        import requests

        settings = get_settings()
        auth = (settings.JIRA_USERNAME, settings.JIRA_TOKEN)
        response = requests.get(f"{settings.JIRA_URL}/rest/api/2/myself", auth=auth, timeout=10)

        if response.status_code == 200:
            results["jira"] = {"status": "ok", "message": "Authentication successful"}
        else:
            results["jira"] = {"status": "error", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        results["jira"] = {"status": "error", "error": str(e)}

    # Test Redis connection (if configured)
    try:
        from app.core.cache import get_cache_manager
        cache = get_cache_manager()
        # Try a simple cache operation
        cache.set("test_key", "test_value", ttl=1)
        value = cache.get("test_key")
        if value == "test_value":
            results["cache"] = {"status": "ok", "message": "Cache working"}
        else:
            results["cache"] = {"status": "warning", "message": "Cache not working properly"}
    except Exception as e:
        results["cache"] = {"status": "warning", "error": str(e)}

    return results


@router.get("/debug/job/{job_id}/details")
async def get_job_debug_details(job_id: str):
    """Get detailed debug information for a specific job."""
    if job_id not in job_status_store:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = job_status_store[job_id]

    # Add additional debug information
    debug_info = {
        **job_data,
        "memory_usage": "N/A",  # Could add actual memory usage
        "thread_info": "N/A",   # Could add thread information
        "system_info": {
            "timestamp": datetime.now().isoformat(),
            "service_uptime": "N/A"  # Could calculate actual uptime
        }
    }

    return debug_info
