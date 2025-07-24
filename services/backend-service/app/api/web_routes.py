"""
Web Routes for ETL Dashboard

Provides web interface routes for the ETL dashboard including:
- Login page
- Dashboard page  
- Authentication endpoints
- Job control endpoints
"""

from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
# from fastapi.templating import Jinja2Templates  # Not needed - using React frontend
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, List
import os
from pathlib import Path
from datetime import datetime
from sqlalchemy import func

from app.core.logging_config import get_logger
from app.jobs.orchestrator import get_job_status, trigger_jira_sync, trigger_github_sync
from app.core.database import get_database
from app.models.unified_models import JobSchedule, User
from app.auth.auth_service import get_auth_service
from app.auth.auth_middleware import (
    get_current_user, require_authentication, require_admin, require_permission,
    require_web_authentication, require_web_permission,
    get_client_ip, get_user_agent
)

logger = get_logger(__name__)

# Templates not needed - using React frontend
# templates_dir = Path(__file__).parent.parent / "templates"
# templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter()

# Pydantic models
class LoginRequest(BaseModel):
    email: str
    password: str

class JobToggleRequest(BaseModel):
    active: bool


class JobExecutionParams(BaseModel):
    """Parameters for job execution modes."""
    mode: Optional[str] = "all"
    custom_query: Optional[str] = None
    target_repository: Optional[str] = None
    target_repositories: Optional[List[str]] = None
    target_projects: Optional[List[str]] = None

# Legacy function for backward compatibility - now uses proper authentication
async def verify_token(user: User = Depends(require_authentication)):
    """Verify JWT token - now uses proper authentication system"""
    # Return user for routes that need it, but maintain backward compatibility
    # for routes that just need authentication verification
    return user

# Web page routes
@router.get("/")
async def root():
    """Redirect to React frontend"""
    return RedirectResponse(url="http://localhost:5173", status_code=302)

@router.get("/login")
async def login_page(request: Request):
    """Redirect to React frontend login page"""
    return RedirectResponse(url="http://localhost:5173/login", status_code=302)

@router.get("/dashboard")
async def dashboard_page(request: Request):
    """Redirect to React frontend dashboard"""
    return RedirectResponse(url="http://localhost:5173/home", status_code=302)


@router.get("/admin")
async def admin_page(request: Request):
    """Redirect to React frontend admin page"""
    return RedirectResponse(url="http://localhost:5173/admin", status_code=302)


@router.get("/admin/status-mappings", response_class=HTMLResponse)
async def status_mappings_page(request: Request):
    """Serve status mappings management page"""
    try:
        # Get user from token (middleware ensures we're authenticated)
        token = request.cookies.get("pulse_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        # Get user info
        auth_service = get_auth_service()
        user = await auth_service.verify_token(token)

        # Check admin permission
        from app.auth.permissions import Resource, Action, has_permission
        from app.core.database import get_database

        database = get_database()
        with database.get_session() as session:
            if not has_permission(user, Resource.ADMIN_PANEL, Action.READ, session):
                return RedirectResponse(url="/login?error=permission_denied&resource=admin_panel", status_code=302)

        return RedirectResponse(url="http://localhost:5173/admin/status-mappings", status_code=302)

    except Exception as e:
        logger.error(f"Status mappings page error: {e}")
        return RedirectResponse(url="/login?error=server_error", status_code=302)


@router.get("/admin/issuetype-mappings", response_class=HTMLResponse)
async def issuetype_mappings_page(request: Request):
    """Serve issue type mappings management page"""
    try:
        # Get user from token (middleware ensures we're authenticated)
        token = request.cookies.get("pulse_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        # Get user info
        auth_service = get_auth_service()
        user = await auth_service.verify_token(token)

        # Check admin permission
        from app.auth.permissions import Resource, Action, has_permission
        from app.core.database import get_database

        database = get_database()
        with database.get_session() as session:
            if not has_permission(user, Resource.ADMIN_PANEL, Action.READ, session):
                return RedirectResponse(url="/login?error=permission_denied&resource=admin_panel", status_code=302)

        return RedirectResponse(url="http://localhost:5173/admin/issuetype-mappings", status_code=302)

    except Exception as e:
        logger.error(f"Issue type mappings page error: {e}")
        return RedirectResponse(url="/login?error=server_error", status_code=302)


@router.get("/admin/issuetype-hierarchies", response_class=HTMLResponse)
async def issuetype_hierarchies_page(request: Request):
    """Serve issue type hierarchies management page (temporarily redirected to flow steps)"""
    try:
        # Get user from token (middleware ensures we're authenticated)
        token = request.cookies.get("pulse_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        # Get user info
        auth_service = get_auth_service()
        user = await auth_service.verify_token(token)

        # Check admin permission
        from app.auth.permissions import Resource, Action, has_permission
        from app.core.database import get_database

        database = get_database()
        with database.get_session() as session:
            if not has_permission(user, Resource.ADMIN_PANEL, Action.READ, session):
                return RedirectResponse(url="/login?error=permission_denied&resource=admin_panel", status_code=302)

        return RedirectResponse(url="http://localhost:5173/admin/issuetype-hierarchies", status_code=302)

    except Exception as e:
        logger.error(f"Issue type hierarchies page error: {e}")
        return RedirectResponse(url="/login?error=server_error", status_code=302)


@router.get("/admin/flow-steps", response_class=HTMLResponse)
async def flow_steps_page(request: Request):
    """Serve flow steps management page"""
    try:
        # Get user from token (middleware ensures we're authenticated)
        token = request.cookies.get("pulse_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        # Get user info
        auth_service = get_auth_service()
        user = await auth_service.verify_token(token)

        # Check admin permission
        from app.auth.permissions import Resource, Action, has_permission
        from app.core.database import get_database

        database = get_database()
        with database.get_session() as session:
            if not has_permission(user, Resource.ADMIN_PANEL, Action.READ, session):
                return RedirectResponse(url="/login?error=permission_denied&resource=admin_panel", status_code=302)

        return RedirectResponse(url="http://localhost:5173/admin/flow-steps", status_code=302)

    except Exception as e:
        logger.error(f"Flow steps page error: {e}")
        return RedirectResponse(url="/login?error=server_error", status_code=302)


@router.get("/logout", response_class=HTMLResponse)
async def logout_page(request: Request):
    """Handle web logout - clear all cookies and redirect to login"""

    logger.info("=== LOGOUT PROCESS STARTED ===")

    # First, invalidate the token on the server side
    try:
        token = request.cookies.get("pulse_token")
        if token:
            logger.info(f"Found token during logout: {token[:20]}...")
            logger.info(f"Logging out user with token: {token[:20]}...")
        else:
            logger.info("No token found in cookies during logout")
    except Exception as e:
        logger.warning(f"Error during logout token handling: {e}")

    logger.info("Creating logout response with cookie deletion...")
    response = RedirectResponse(url="/login?message=logged_out", status_code=302)

    # Clear the pulse_token cookie by setting it to empty with immediate expiration
    logger.info("Clearing pulse_token cookie by setting to empty with immediate expiration...")
    response.set_cookie(
        key="pulse_token",
        value="",  # Empty value
        max_age=0,  # Immediate expiration
        path="/",
        httponly=True,
        secure=False,
        samesite="lax"
    )

    # Also try the traditional delete_cookie method
    logger.info("Also trying delete_cookie method...")
    response.delete_cookie(
        key="pulse_token",
        path="/",
        httponly=True,
        secure=False,
        samesite="lax"
    )

    # Try alternative delete methods for safety
    logger.info("Trying alternative delete methods...")
    response.delete_cookie(key="pulse_token", path="/")
    response.delete_cookie(key="pulse_token")

    # Clear other potential auth cookies
    other_cookies = ["session", "auth_token", "token", "jwt"]
    for cookie_name in other_cookies:
        response.delete_cookie(key=cookie_name, path="/")
        response.delete_cookie(key=cookie_name)

    logger.info("=== LOGOUT PROCESS COMPLETED ===")
    logger.info(f"Redirecting to: /login?message=logged_out")

    # Add aggressive cache control headers
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'

    return response

# Authentication API routes
@router.post("/auth/login")
async def login(login_request: LoginRequest, request: Request):
    """Handle login authentication"""
    try:
        email = login_request.email.lower().strip()
        password = login_request.password

        # Get client info for session tracking
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        # Authenticate user
        auth_service = get_auth_service()
        result = await auth_service.authenticate_local(email, password, ip_address, user_agent)

        if result:
            logger.info(f"Successful login for user: {email}")

            # Create response with token cookie
            response_data = {
                "success": True,
                "token": result["token"],
                "user": result["user"]
            }

            from fastapi.responses import JSONResponse
            response = JSONResponse(content=response_data)

            # Set secure cookie with token (expires in 24 hours)
            logger.info(f"Setting pulse_token cookie for user: {email}")
            response.set_cookie(
                key="pulse_token",
                value=result["token"],
                max_age=86400,  # 24 hours
                path="/",  # Explicitly set path
                httponly=True,  # Prevent XSS
                secure=False,   # Set to True in production with HTTPS
                samesite="lax"
            )
            logger.info("Cookie set successfully")

            return response
        else:
            logger.warning(f"Failed login attempt for email: {email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/auth/logout")
async def logout(request: Request, user: User = Depends(require_authentication)):
    """Handle user logout"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix

            auth_service = get_auth_service()
            success = await auth_service.invalidate_session(token)

            if success:
                logger.info(f"User logged out: {user.email}")

                # Create response and clear cookie with exact same parameters
                from fastapi.responses import JSONResponse
                response = JSONResponse(content={"success": True, "message": "Logged out successfully"})
                response.delete_cookie(
                    key="pulse_token",
                    path="/",
                    httponly=True,
                    secure=False,
                    samesite="lax"
                )
                return response
            else:
                logger.warning(f"Failed to invalidate session for user: {user.email}")

                # Still clear the cookie even if session invalidation failed
                from fastapi.responses import JSONResponse
                response = JSONResponse(content={"success": False, "message": "Session not found"})
                response.delete_cookie(
                    key="pulse_token",
                    path="/",
                    httponly=True,
                    secure=False,
                    samesite="lax"
                )
                return response
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No token provided"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get("/api/v1/auth/validate")
async def validate_token(user: User = Depends(require_authentication)):
    """Validate JWT token - returns 200 if valid, 401 if invalid"""
    try:
        # If we reach here, the token is valid (require_authentication succeeded)
        return {
            "valid": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "is_admin": user.is_admin
            },
            "expires_in_hours": 24  # Let frontend know when token expires
        }
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


@router.post("/api/v1/auth/refresh")
async def refresh_token(user: User = Depends(require_authentication)):
    """Refresh JWT token to extend session"""
    try:
        from app.auth.auth_service import get_auth_service
        auth_service = get_auth_service()

        # Create a new session for the user (this generates a new token)
        from app.core.database import get_database
        database = get_database()

        with database.get_session() as session:
            # Get the user from database to ensure fresh data
            fresh_user = session.query(User).filter(User.id == user.id).first()
            if not fresh_user:
                raise HTTPException(status_code=404, detail="User not found")

            # Create new session
            new_session = await auth_service._create_session(fresh_user, session)

            return {
                "token": new_session["token"],
                "user": new_session["user"],
                "message": "Token refreshed successfully"
            }

    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token"
        )


# Job management API routes
@router.get("/api/v1/jobs/{job_name}/schedule-details")
async def get_job_schedule_details(job_name: str, user: User = Depends(require_permission("etl_jobs", "read"))):
    """Get detailed job schedule information for a specific job"""
    try:
        from app.core.database import get_database
        from app.models.unified_models import JobSchedule
        from sqlalchemy.orm import Session

        database = get_database()

        with database.get_session_context() as session:
            job_schedule = session.query(JobSchedule).filter(JobSchedule.job_name == job_name).first()

            if not job_schedule:
                raise HTTPException(status_code=404, detail=f"Job schedule not found for {job_name}")

            # Convert to dict with all available fields
            schedule_details = {
                'id': job_schedule.id,
                'job_name': job_schedule.job_name,
                'status': job_schedule.status,
                'last_run_started_at': job_schedule.last_run_started_at.isoformat() if job_schedule.last_run_started_at else None,
                'last_success_at': job_schedule.last_success_at.isoformat() if job_schedule.last_success_at else None,
                'created_at': job_schedule.created_at.isoformat() if job_schedule.created_at else None,
                'last_updated_at': job_schedule.last_updated_at.isoformat() if job_schedule.last_updated_at else None,
                'error_message': job_schedule.error_message,
                'retry_count': job_schedule.retry_count,
                'active': job_schedule.active,

                # Checkpoint data (actual fields from model)
                'last_repo_sync_checkpoint': job_schedule.last_repo_sync_checkpoint.isoformat() if job_schedule.last_repo_sync_checkpoint else None,
                'repo_processing_queue': job_schedule.repo_processing_queue,
                'last_pr_cursor': job_schedule.last_pr_cursor,
                'current_pr_node_id': job_schedule.current_pr_node_id,
                'last_commit_cursor': job_schedule.last_commit_cursor,
                'last_review_cursor': job_schedule.last_review_cursor,
                'last_comment_cursor': job_schedule.last_comment_cursor,
                'last_review_thread_cursor': job_schedule.last_review_thread_cursor,

                # Additional computed fields
                'is_recovery_run': job_schedule.is_recovery_run(),
                'checkpoint_state': job_schedule.get_checkpoint_state()
            }

            return schedule_details

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job schedule details for {job_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job schedule details: {str(e)}")

@router.get("/api/v1/github/rate-limits")
async def get_github_rate_limits(user: User = Depends(require_permission("etl_jobs", "read"))):
    """Get current GitHub API rate limits"""
    try:
        from app.core.database import get_database
        from app.models.unified_models import Integration
        from app.core.config import AppConfig
        import requests

        database = get_database()

        with database.get_session_context() as session:
            # Get GitHub integration
            github_integration = session.query(Integration).filter(func.upper(Integration.name) == 'GITHUB').first()

            if not github_integration:
                raise HTTPException(status_code=404, detail="GitHub integration not found")

            # Decrypt GitHub token
            key = AppConfig.load_key()
            github_token = AppConfig.decrypt_token(github_integration.password, key)

            # Make request to GitHub rate limit endpoint
            headers = {
                'Authorization': f'token {github_token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'ETL-Service/1.0'
            }

            response = requests.get('https://api.github.com/rate_limit', headers=headers)

            if not response.ok:
                raise HTTPException(status_code=response.status_code, detail=f"GitHub API error: {response.text}")

            rate_limit_data = response.json()

            # Extract only the required rate limits (core, search, graphql)
            filtered_data = {
                'core': rate_limit_data['resources']['core'],
                'search': rate_limit_data['resources']['search'],
                'graphql': rate_limit_data['resources']['graphql'],
                'timestamp': rate_limit_data.get('rate', {}).get('reset', None)
            }

            return filtered_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting GitHub rate limits: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get GitHub rate limits: {str(e)}")

@router.get("/api/v1/jobs/status")
async def get_jobs_status(user: User = Depends(verify_token)):
    """Get current status of all jobs with detailed information"""
    try:
        # Get basic job status
        status_data = get_job_status()

        # Enhance with checkpoint data
        database = get_database()
        with database.get_session() as session:
            jobs = session.query(JobSchedule).filter(JobSchedule.active == True).all()

            for job in jobs:
                if job.job_name in status_data:
                    # Add checkpoint data
                    checkpoint_state = job.get_checkpoint_state()
                    status_data[job.job_name]['checkpoint_data'] = checkpoint_state
                    status_data[job.job_name]['active'] = job.active

        # Ensure consistent ordering: Jira first, then GitHub
        ordered_jobs = {}
        job_order = ['jira_sync', 'github_sync']

        for job_name in job_order:
            if job_name in status_data:
                ordered_jobs[job_name] = status_data[job_name]

        # Add any other jobs that might exist (for future extensibility)
        for job_name, job_data in status_data.items():
            if job_name not in ordered_jobs:
                ordered_jobs[job_name] = job_data

        # Wrap in jobs object for consistent API format
        return {"jobs": ordered_jobs}
        
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job status"
        )

@router.post("/api/v1/jobs/{job_name}/start")
async def start_job(
    job_name: str,
    execution_params: Optional[JobExecutionParams] = None,
    user: User = Depends(require_permission("etl_jobs", "execute"))
):
    """Force start a specific job with optional execution parameters"""
    try:
        if job_name not in ['jira_sync', 'github_sync']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job name"
            )
        
        # Log execution parameters
        if execution_params:
            logger.info(f"Force starting job {job_name} in MANUAL MODE with parameters: {execution_params.dict()}")
        else:
            logger.info(f"Force starting job {job_name} in MANUAL MODE (default parameters)")

        # Use the appropriate trigger function with force_manual=True and execution parameters
        # Run in background to avoid blocking the web request
        import asyncio
        if job_name == 'jira_sync':
            asyncio.create_task(trigger_jira_sync(force_manual=True, execution_params=execution_params))
            result = {
                'status': 'triggered',
                'message': f'Jira sync job triggered successfully',
                'job_name': job_name
            }
        elif job_name == 'github_sync':
            asyncio.create_task(trigger_github_sync(force_manual=True, execution_params=execution_params))
            result = {
                'status': 'triggered',
                'message': f'GitHub sync job triggered successfully',
                'job_name': job_name
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job name"
            )

        # Return the result from the trigger function
        if result.get('status') == 'success':
            return {
                "success": True,
                "message": f"Job {job_name} completed successfully",
                "job_id": result.get('job_id'),
                "result": result
            }
        else:
            return {
                "success": False,
                "message": f"Job {job_name} failed: {result.get('message', 'Unknown error')}",
                "job_id": result.get('job_id'),
                "result": result
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting job {job_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start job {job_name}"
        )

@router.post("/api/v1/jobs/{job_name}/stop")
async def stop_job(job_name: str, user: User = Depends(require_permission("etl_jobs", "execute"))):
    """Force stop a specific job - requires admin privileges"""
    try:
        if job_name not in ['jira_sync', 'github_sync']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job name"
            )

        from app.core.job_manager import get_job_manager
        job_manager = get_job_manager()

        # Check if job is actually running
        if not job_manager.is_job_running(job_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job {job_name} is not currently running"
            )

        # Request cancellation
        cancelled = job_manager.request_cancellation(job_name)

        if cancelled:
            # Also update database status
            database = get_database()
            with database.get_session() as session:
                job = session.query(JobSchedule).filter(
                    JobSchedule.job_name == job_name,
                    JobSchedule.active == True
                ).first()

                if job and job.status == 'RUNNING':
                    job.status = 'PENDING'
                    job.error_message = 'Job cancelled by user request'
                    session.commit()

            logger.info(f"Job {job_name} cancellation requested by user {user.email}")

            return {
                "success": True,
                "message": f"Cancellation requested for job {job_name}",
                "note": "Job will stop at the next safe checkpoint"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to request cancellation for job {job_name}"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping job {job_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop job {job_name}"
        )





@router.get("/api/v1/jobs/status")
async def get_jobs_status(user: User = Depends(require_permission("etl_jobs", "read"))):
    """Get status of all jobs including running state"""
    try:
        from app.core.job_manager import get_job_manager
        job_manager = get_job_manager()

        database = get_database()
        with database.get_session() as session:
            jobs_status = {}

            for job_name in ['jira_sync', 'github_sync']:
                job = session.query(JobSchedule).filter(
                    JobSchedule.job_name == job_name,
                    JobSchedule.active == True
                ).first()

                if job:
                    is_running = job.status == 'RUNNING'

                    jobs_status[job_name] = {
                        'id': str(job.id),
                        'status': job.status,
                        'is_running': is_running,
                        'can_stop': False,  # Force stop removed
                        'last_success_at': job.last_success_at.isoformat() if job.last_success_at else None,
                        'error_message': job.error_message,
                        'retry_count': job.retry_count
                    }
                else:
                    jobs_status[job_name] = {
                        'id': None,
                        'status': 'NOT_FOUND',
                        'is_running': False,
                        'can_stop': False,
                        'last_success_at': None,
                        'error_message': None,
                        'retry_count': 0
                    }

            return {
                "success": True,
                "jobs": jobs_status,
                "running_jobs": job_manager.get_running_jobs()
            }

    except Exception as e:
        logger.error(f"Error getting jobs status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get jobs status"
        )


@router.post("/api/v1/jobs/{job_name}/toggle")
async def toggle_job_active(job_name: str, request: JobToggleRequest, user: User = Depends(require_permission("etl_jobs", "execute"))):
    """Toggle job active/inactive status - requires admin privileges"""
    try:
        if job_name not in ['jira_sync', 'github_sync']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job name"
            )
        
        database = get_database()
        with database.get_session() as session:
            job = session.query(JobSchedule).filter(JobSchedule.job_name == job_name).first()
            
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            job.active = request.active
            session.commit()
            
            action = "activated" if request.active else "deactivated"
            logger.info(f"Job {job_name} {action}")
            
            return {
                "success": True,
                "message": f"Job {job_name} {action} successfully",
                "active": job.active
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling job {job_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle job {job_name}"
        )


@router.post("/api/v1/jobs/{job_name}/pause")
async def pause_job(job_name: str, user: User = Depends(require_permission("etl_jobs", "execute"))):
    """Pause a specific job"""
    try:
        database = get_database()
        with database.get_session() as session:
            # Get the job to pause
            job_to_pause = session.query(JobSchedule).filter(
                JobSchedule.job_name == job_name,
                JobSchedule.active == True
            ).first()

            if not job_to_pause:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found")

            if job_to_pause.status == 'PAUSED':
                return {"message": f"Job {job_name} is already paused", "status": "paused"}

            if job_to_pause.status == 'RUNNING':
                raise HTTPException(status_code=400, detail=f"Cannot pause job {job_name} while it's running")

            # Pause the job
            job_to_pause.set_paused()
            session.commit()

            logger.info(f"Job {job_name} paused successfully")

            return {
                "message": f"Job {job_name} paused successfully",
                "status": "paused"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause job {job_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to pause job {job_name}"
        )


@router.post("/api/v1/jobs/{job_name}/unpause")
async def unpause_job(job_name: str, user: User = Depends(require_permission("etl_jobs", "execute"))):
    """Unpause a specific job"""
    try:
        database = get_database()
        with database.get_session() as session:
            # Get both jobs to determine unpause logic
            all_jobs = session.query(JobSchedule).filter(JobSchedule.active == True).all()

            job_to_unpause = None
            other_job = None

            for job in all_jobs:
                if job.job_name == job_name:
                    job_to_unpause = job
                else:
                    other_job = job

            if not job_to_unpause:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found")

            if job_to_unpause.status != 'PAUSED':
                return {"message": f"Job {job_name} is not paused", "status": job_to_unpause.status.lower()}

            # Determine new status based on other job status
            other_job_status = other_job.status if other_job else 'FINISHED'
            job_to_unpause.set_unpaused(other_job_status)
            session.commit()

            logger.info(f"Job {job_name} unpaused successfully, new status: {job_to_unpause.status}")

            return {
                "message": f"Job {job_name} unpaused successfully",
                "status": job_to_unpause.status.lower(),
                "other_job_status": other_job_status.lower() if other_job else "none"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unpause job {job_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to unpause job {job_name}"
        )


# Orchestrator Control Endpoints
@router.post("/api/v1/orchestrator/start")
async def force_start_orchestrator(user: User = Depends(require_permission("orchestrator", "execute"))):
    """Force start the orchestrator to check for PENDING jobs"""
    try:
        from app.jobs.orchestrator import run_orchestrator

        # Run orchestrator in background
        import asyncio
        asyncio.create_task(run_orchestrator())

        logger.info("Orchestrator manually triggered")

        return {
            "success": True,
            "message": "Orchestrator started successfully"
        }

    except Exception as e:
        logger.error(f"Error starting orchestrator: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start orchestrator"
        )


@router.post("/api/v1/orchestrator/pause")
async def pause_orchestrator(user: User = Depends(require_permission("orchestrator", "execute"))):
    """Pause the scheduled orchestrator"""
    try:
        from app.main import scheduler

        # Pause the orchestrator job
        scheduler.pause_job('etl_orchestrator')

        logger.info("Orchestrator paused")

        return {
            "success": True,
            "message": "Orchestrator paused successfully"
        }

    except Exception as e:
        logger.error(f"Error pausing orchestrator: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause orchestrator"
        )


@router.post("/api/v1/orchestrator/resume")
async def resume_orchestrator(user: User = Depends(require_permission("orchestrator", "execute"))):
    """Resume the scheduled orchestrator - requires admin privileges"""
    try:
        from app.main import scheduler

        # Resume the orchestrator job
        scheduler.resume_job('etl_orchestrator')

        logger.info("Orchestrator resumed")

        return {
            "success": True,
            "message": "Orchestrator resumed successfully"
        }

    except Exception as e:
        logger.error(f"Error resuming orchestrator: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resume orchestrator"
        )


@router.post("/api/v1/jobs/{job_name}/set-active")
async def set_job_active(job_name: str, user: User = Depends(require_permission("etl_jobs", "execute"))):
    """Set a specific job as active (PENDING) and set the other job as FINISHED"""
    try:
        if job_name not in ['jira_sync', 'github_sync']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job name. Must be 'jira_sync' or 'github_sync'"
            )

        database = get_database()
        with database.get_session() as session:
            # Get both jobs
            jira_job = session.query(JobSchedule).filter(
                JobSchedule.job_name == 'jira_sync',
                JobSchedule.active == True
            ).first()

            github_job = session.query(JobSchedule).filter(
                JobSchedule.job_name == 'github_sync',
                JobSchedule.active == True
            ).first()

            if not jira_job or not github_job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="One or both jobs not found"
                )

            # Check if any job is currently running
            if jira_job.status == 'RUNNING' or github_job.status == 'RUNNING':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot set active while a job is currently running"
                )

            # Set the requested job as PENDING and handle the other job based on its current status
            if job_name == 'jira_sync':
                jira_job.status = 'PENDING'
                jira_job.error_message = None  # Clear any previous errors
                other_job_name = 'github_sync'
                other_job = github_job
            else:  # github_sync
                github_job.status = 'PENDING'
                github_job.error_message = None  # Clear any previous errors
                other_job_name = 'jira_sync'
                other_job = jira_job

            # Only set other job to FINISHED if it's not PAUSED
            other_job_action = "unchanged (PAUSED)"
            if other_job.status != 'PAUSED':
                other_job.status = 'FINISHED'
                other_job_action = "set to FINISHED"

            session.commit()

            logger.info(f"Job {job_name} set as active (PENDING) by user {user.email}. {other_job_name} {other_job_action}.")

            return {
                "success": True,
                "message": f"Job {job_name} is now active and ready to run",
                "active_job": job_name,
                "other_job": other_job_name,
                "note": f"{job_name} set to PENDING, {other_job_name} {other_job_action}"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting job {job_name} as active: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set job {job_name} as active"
        )


@router.get("/api/v1/orchestrator/status")
async def get_orchestrator_status(user: User = Depends(require_permission("orchestrator", "read"))):
    """Get orchestrator status"""
    try:
        from app.main import scheduler
        from app.core.settings_manager import (
            get_orchestrator_interval, is_orchestrator_enabled,
            is_orchestrator_retry_enabled, get_orchestrator_retry_interval,
            get_orchestrator_max_retry_attempts
        )
        from app.core.orchestrator_scheduler import get_orchestrator_scheduler

        # Get orchestrator job status
        job = scheduler.get_job('etl_orchestrator')

        if not job:
            return {
                "status": "not_scheduled",
                "next_run": None,
                "message": "Orchestrator is not scheduled"
            }

        # Check if job is paused
        is_paused = job.next_run_time is None

        # Get retry status
        orchestrator_scheduler = get_orchestrator_scheduler()
        retry_status = orchestrator_scheduler.get_all_retry_status()
        fast_retry_active = orchestrator_scheduler.is_fast_retry_active()

        status_info = {
            "status": "paused" if is_paused else "running",
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "job_id": job.id,
            "name": job.name,
            "message": f"Orchestrator is {'paused' if is_paused else 'running'}",
            "interval_minutes": get_orchestrator_interval(),
            "enabled": is_orchestrator_enabled(),
            "fast_retry_active": fast_retry_active,
            "retry_config": {
                "enabled": is_orchestrator_retry_enabled(),
                "interval_minutes": get_orchestrator_retry_interval(),
                "max_attempts": get_orchestrator_max_retry_attempts()
            },
            "retry_status": retry_status
        }

        return status_info

    except Exception as e:
        logger.error(f"Error getting orchestrator status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get orchestrator status"
        )


@router.post("/api/v1/orchestrator/schedule")
async def update_orchestrator_schedule(
    request: dict,
    user: User = Depends(require_permission("orchestrator", "execute"))
):
    """Update orchestrator schedule interval - requires admin privileges"""
    try:
        interval_minutes = request.get('interval_minutes')
        enabled = request.get('enabled', True)

        if not interval_minutes or interval_minutes < 1 or interval_minutes > 1440:  # Max 24 hours
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interval must be between 1 and 1440 minutes"
            )

        from app.main import update_orchestrator_schedule
        success = await update_orchestrator_schedule(interval_minutes, enabled)

        if success:
            logger.info(f"Orchestrator schedule updated: {interval_minutes} minutes, enabled: {enabled}")
            return {
                "success": True,
                "message": f"Orchestrator schedule updated to {interval_minutes} minutes",
                "interval_minutes": interval_minutes,
                "enabled": enabled
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update orchestrator schedule"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating orchestrator schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update orchestrator schedule"
        )


@router.post("/api/v1/orchestrator/retry")
async def update_orchestrator_retry_config(
    request: dict,
    user: User = Depends(require_permission("orchestrator", "execute"))
):
    """Update orchestrator retry configuration - requires admin privileges"""
    try:
        retry_enabled = request.get('enabled')
        retry_interval = request.get('interval_minutes')
        max_attempts = request.get('max_attempts')

        # Validate inputs
        if retry_interval is not None and (retry_interval < 1 or retry_interval > 60):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Retry interval must be between 1 and 60 minutes"
            )

        if max_attempts is not None and (max_attempts < 1 or max_attempts > 10):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Max attempts must be between 1 and 10"
            )

        from app.core.settings_manager import (
            set_orchestrator_retry_enabled, set_orchestrator_retry_interval,
            set_orchestrator_max_retry_attempts
        )
        from app.core.orchestrator_scheduler import get_orchestrator_scheduler

        # Check if fast retry is currently active
        orchestrator_scheduler = get_orchestrator_scheduler()
        fast_retry_active = orchestrator_scheduler.is_fast_retry_active()
        current_countdown = orchestrator_scheduler.get_current_countdown_minutes()

        # Update settings
        updates = {}
        schedule_updated = False

        if retry_enabled is not None:
            set_orchestrator_retry_enabled(retry_enabled)
            updates['enabled'] = retry_enabled

        if retry_interval is not None:
            set_orchestrator_retry_interval(retry_interval)
            updates['interval_minutes'] = retry_interval

            # Check if we should apply the new retry interval immediately
            if fast_retry_active:
                schedule_updated = orchestrator_scheduler.apply_new_retry_interval_if_smaller(retry_interval)

        if max_attempts is not None:
            set_orchestrator_max_retry_attempts(max_attempts)
            updates['max_attempts'] = max_attempts

        logger.info(f"Orchestrator retry configuration updated: {updates}")

        # Build appropriate message based on what happened
        message = "Orchestrator retry configuration updated successfully"
        if fast_retry_active and retry_interval is not None:
            if schedule_updated:
                message += f" (new retry interval applied immediately - was {current_countdown:.1f}min, now {retry_interval}min)"
            else:
                message += f" (current fast retry preserved - {current_countdown:.1f}min remaining, new interval will apply to future attempts)"
        elif fast_retry_active:
            message += " (current fast retry preserved - changes will apply to future retry attempts)"

        return {
            "success": True,
            "message": message,
            "updates": updates,
            "fast_retry_active": fast_retry_active,
            "schedule_updated": schedule_updated,
            "current_countdown_minutes": current_countdown
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating orchestrator retry configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update orchestrator retry configuration"
        )


@router.get("/api/v1/settings")
async def get_system_settings(user: User = Depends(require_permission("settings", "read"))):
    """Get all system settings"""
    try:
        from app.core.settings_manager import SettingsManager
        settings = SettingsManager.get_all_settings()

        return {
            "success": True,
            "settings": settings
        }

    except Exception as e:
        logger.error(f"Error getting system settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system settings"
        )


@router.post("/api/v1/settings")
async def update_system_setting(
    request: dict,
    user: User = Depends(require_permission("settings", "execute"))
):
    """Update a system setting - requires admin privileges"""
    try:
        setting_key = request.get('setting_key')
        setting_value = request.get('setting_value')
        description = request.get('description')

        if not setting_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Setting key is required"
            )

        from app.core.settings_manager import SettingsManager
        success = SettingsManager.set_setting(setting_key, setting_value, description)

        if success:
            # If orchestrator setting was updated, refresh the schedule
            if setting_key in ['orchestrator_interval_minutes', 'orchestrator_enabled']:
                from app.core.settings_manager import get_orchestrator_interval, is_orchestrator_enabled
                from app.main import update_orchestrator_schedule

                interval = get_orchestrator_interval()
                enabled = is_orchestrator_enabled()
                await update_orchestrator_schedule(interval, enabled)
            elif setting_key == 'orchestrator_retry_interval_minutes':
                # For retry interval changes, check if we should apply immediately
                from app.core.orchestrator_scheduler import get_orchestrator_scheduler
                orchestrator_scheduler = get_orchestrator_scheduler()

                if orchestrator_scheduler.is_fast_retry_active():
                    schedule_updated = orchestrator_scheduler.apply_new_retry_interval_if_smaller(int(setting_value))
                    if schedule_updated:
                        logger.info(f"Retry interval updated to {setting_value} minutes and applied immediately (was smaller than current countdown)")
                    else:
                        logger.info(f"Retry interval updated to {setting_value} minutes - current fast retry preserved (new interval will apply to future attempts)")
                else:
                    logger.info(f"Retry interval updated to {setting_value} minutes - will apply to future retry attempts")
            elif setting_key in ['orchestrator_retry_enabled', 'orchestrator_max_retry_attempts']:
                # For other retry settings, just log the change - no need to update schedule
                logger.info(f"Retry setting {setting_key} updated to {setting_value} - will apply to future retry attempts")

            return {
                "success": True,
                "message": f"Setting {setting_key} updated successfully",
                "setting_key": setting_key,
                "setting_value": setting_value
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update setting"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating system setting: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update system setting"
        )


@router.get("/websocket_test", response_class=HTMLResponse)
async def websocket_test():
    """WebSocket test page for debugging."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebSocket Test</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #1a1a1a;
            color: #ffffff;
        }
        .container {
            background-color: #2a2a2a;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .status {
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        }
        .connected { background-color: #2d5a2d; }
        .disconnected { background-color: #5a2d2d; }
        .log {
            background-color: #1a1a1a;
            padding: 15px;
            border-radius: 4px;
            height: 300px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 12px;
            border: 1px solid #444;
        }
        button {
            background-color: #4a5568;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            margin: 5px;
        }
        button:hover {
            background-color: #5a6578;
        }
        .progress-bar {
            width: 100%;
            height: 20px;
            background-color: #444;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }
        .progress-fill {
            height: 100%;
            background-color: #4a90e2;
            width: 0%;
            transition: width 0.3s ease;
        }
        .progress-text {
            text-align: center;
            margin: 10px 0;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h1>🔌 WebSocket Connection Test</h1>

    <div class="container">
        <h2>Connection Status</h2>
        <div id="jira-sync-status" class="status disconnected">
            🔴 Jira Sync: Disconnected
        </div>
        <div id="github-sync-status" class="status disconnected">
            🔴 GitHub Sync: Disconnected
        </div>

        <button onclick="connectAll()">Connect All</button>
        <button onclick="disconnectAll()">Disconnect All</button>
        <button onclick="clearLog()">Clear Log</button>
        <button onclick="sendTestMessage()">Send Test Message</button>
    </div>

    <div class="container">
        <h2>Progress Display</h2>
        <div id="progress-container">
            <div class="progress-text" id="progress-text">No progress data</div>
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill"></div>
            </div>
            <div id="progress-percentage">0%</div>
        </div>
    </div>

    <div class="container">
        <h2>WebSocket Log</h2>
        <div id="log" class="log"></div>
    </div>

    <script>
        let websockets = {
            jira_sync: null,
            github_sync: null
        };

        function log(message) {
            const logElement = document.getElementById('log');
            const timestamp = new Date().toLocaleTimeString();
            logElement.innerHTML += `[${timestamp}] ${message}\\n`;
            logElement.scrollTop = logElement.scrollHeight;
        }

        function updateStatus(jobName, connected) {
            const statusElement = document.getElementById(`${jobName.replace('_', '-')}-status`);
            if (!statusElement) {
                log(`❌ Status element not found for ${jobName}`);
                return;
            }
            if (connected) {
                statusElement.className = 'status connected';
                statusElement.innerHTML = `🟢 ${jobName.replace('_', ' ').toUpperCase()}: Connected`;
            } else {
                statusElement.className = 'status disconnected';
                statusElement.innerHTML = `🔴 ${jobName.replace('_', ' ').toUpperCase()}: Disconnected`;
            }
        }

        function updateProgress(percentage, step) {
            document.getElementById('progress-text').textContent = step;
            document.getElementById('progress-fill').style.width = `${percentage}%`;
            document.getElementById('progress-percentage').textContent = `${Math.round(percentage)}%`;
        }

        function connectWebSocket(jobName) {
            if (websockets[jobName]) {
                websockets[jobName].close();
            }

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/progress/${jobName}`;

            log(`🔌 Attempting to connect to ${jobName} at: ${wsUrl}`);
            log(`🔍 Looking for status element: ${jobName.replace('_', '-')}-status`);

            try {
                const ws = new WebSocket(wsUrl);

                ws.onopen = function () {
                    log(`✅ WebSocket connected for ${jobName}`);
                    websockets[jobName] = ws;
                    updateStatus(jobName, true);
                };

                ws.onmessage = function (event) {
                    try {
                        const data = JSON.parse(event.data);
                        log(`📨 Message from ${jobName}: ${JSON.stringify(data)}`);

                        if (data.type === 'progress') {
                            updateProgress(data.percentage, data.step);
                        }
                    } catch (e) {
                        log(`❌ Error parsing message from ${jobName}: ${e}`);
                    }
                };

                ws.onclose = function (event) {
                    log(`🔌 WebSocket disconnected for ${jobName}. Code: ${event.code}, Reason: ${event.reason}`);
                    websockets[jobName] = null;
                    updateStatus(jobName, false);
                };

                ws.onerror = function (error) {
                    log(`❌ WebSocket error for ${jobName}: ${error}`);
                    updateStatus(jobName, false);
                };

            } catch (e) {
                log(`❌ Failed to create WebSocket for ${jobName}: ${e}`);
                updateStatus(jobName, false);
            }
        }

        function connectAll() {
            log('🚀 Connecting to all WebSocket endpoints...');
            connectWebSocket('jira_sync');
            connectWebSocket('github_sync');
        }

        function disconnectAll() {
            log('🔌 Disconnecting all WebSocket connections...');
            Object.keys(websockets).forEach(jobName => {
                if (websockets[jobName]) {
                    websockets[jobName].close();
                    websockets[jobName] = null;
                    updateStatus(jobName, false);
                }
            });
        }

        function clearLog() {
            document.getElementById('log').innerHTML = '';
        }

        function sendTestMessage() {
            log('📤 Requesting test message via API...');
            fetch('/api/test_websocket', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    job_name: 'jira_sync',
                    percentage: Math.random() * 100,
                    message: `Test message: ${Math.floor(Math.random() * 1000)} of 5000 items (${(Math.random() * 100).toFixed(1)}%)`
                })
            })
            .then(response => response.json())
            .then(data => {
                log(`📨 API Response: ${JSON.stringify(data)}`);
            })
            .catch(error => {
                log(`❌ API Error: ${error}`);
            });
        }

        // Auto-connect on page load
        window.addEventListener('load', function() {
            log('🌐 WebSocket Test Page Loaded');
            log('📍 Current URL: ' + window.location.href);

            // Auto-connect after a short delay
            setTimeout(() => {
                connectAll();
            }, 1000);
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@router.post("/api/test_websocket")
async def test_websocket_message(request: Request):
    """Send a test WebSocket message."""
    try:
        from app.core.websocket_manager import get_websocket_manager

        data = await request.json()
        job_name = data.get('job_name', 'jira_sync')
        percentage = data.get('percentage', 50.0)
        message = data.get('message', 'Test message')

        websocket_manager = get_websocket_manager()
        await websocket_manager.send_progress_update(job_name, percentage, message)

        connections = websocket_manager.get_connection_count(job_name)

        return {
            "success": True,
            "message": "Test message sent",
            "job_name": job_name,
            "percentage": percentage,
            "step": message,
            "connections": connections
        }

    except Exception as e:
        logger.error(f"Error sending test WebSocket message: {e}")
        return {
            "success": False,
            "error": str(e)
        }

