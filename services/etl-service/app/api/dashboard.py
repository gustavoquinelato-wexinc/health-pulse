"""
Dashboard endpoints for ETL service web interface.
Provides HTML pages for job monitoring and control.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

# Initialize templates
templates = Jinja2Templates(directory="app/templates")


@router.get("/status", response_class=HTMLResponse)
async def job_status_page():
    """
    Serve the job status dashboard page.
    
    Returns:
        HTMLResponse: Job status dashboard HTML page
    """
    # This would typically render a template with job status data
    # For now, return a simple HTML page
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ETL Job Status Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .status-card { 
                border: 1px solid #ddd; 
                border-radius: 8px; 
                padding: 20px; 
                margin: 10px 0; 
                background: #f9f9f9; 
            }
            .status-running { border-left: 4px solid #28a745; }
            .status-completed { border-left: 4px solid #007bff; }
            .status-failed { border-left: 4px solid #dc3545; }
            .btn { 
                padding: 8px 16px; 
                margin: 5px; 
                border: none; 
                border-radius: 4px; 
                cursor: pointer; 
            }
            .btn-primary { background: #007bff; color: white; }
            .btn-danger { background: #dc3545; color: white; }
            .btn-success { background: #28a745; color: white; }
        </style>
    </head>
    <body>
        <h1>ETL Job Status Dashboard</h1>
        
        <div class="status-card status-completed">
            <h3>Jira Data Extraction</h3>
            <p><strong>Status:</strong> Completed</p>
            <p><strong>Last Run:</strong> 2025-01-16 10:30:00</p>
            <p><strong>Records Processed:</strong> 1,250 issues</p>
            <button class="btn btn-primary" onclick="startJob('jira')">Start Job</button>
            <button class="btn btn-danger" onclick="stopJob('jira')">Stop Job</button>
        </div>
        
        <div class="status-card status-running">
            <h3>GitHub Data Extraction</h3>
            <p><strong>Status:</strong> Running</p>
            <p><strong>Started:</strong> 2025-01-16 11:00:00</p>
            <p><strong>Progress:</strong> 65% (450/692 repositories)</p>
            <button class="btn btn-danger" onclick="stopJob('github')">Stop Job</button>
        </div>
        
        <div class="status-card">
            <h3>System Health</h3>
            <p><strong>Database:</strong> ✅ Connected</p>
            <p><strong>Jira API:</strong> ✅ Connected</p>
            <p><strong>GitHub API:</strong> ✅ Connected</p>
            <p><strong>Rate Limits:</strong> ⚠️ GitHub: 30/5000 remaining</p>
        </div>
        
        <script>
            function startJob(jobType) {
                fetch(`/etl/${jobType}/extract`, { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        alert(`${jobType} job started: ${data.message}`);
                        location.reload();
                    })
                    .catch(error => {
                        alert(`Failed to start ${jobType} job: ${error}`);
                    });
            }
            
            function stopJob(jobType) {
                if (confirm(`Are you sure you want to stop the ${jobType} job?`)) {
                    fetch(`/etl/jobs/stop`, { method: 'POST' })
                        .then(response => response.json())
                        .then(data => {
                            alert(`${jobType} job stopped: ${data.message}`);
                            location.reload();
                        })
                        .catch(error => {
                            alert(`Failed to stop ${jobType} job: ${error}`);
                        });
                }
            }
            
            // Auto-refresh every 30 seconds
            setTimeout(() => location.reload(), 30000);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


@router.get("/", response_class=HTMLResponse)
async def dashboard_home():
    """
    Serve the main dashboard home page.
    
    Returns:
        HTMLResponse: Main dashboard HTML page
    """
    # Redirect to status page for now
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Pulse ETL Service</title>
        <meta http-equiv="refresh" content="0; url=/status">
    </head>
    <body>
        <p>Redirecting to dashboard...</p>
        <p>If you are not redirected, <a href="/status">click here</a>.</p>
    </body>
    </html>
    """)
