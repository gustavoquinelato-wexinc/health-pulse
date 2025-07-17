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
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
from pathlib import Path
from datetime import datetime

from app.core.logging_config import get_logger
from app.jobs.orchestrator import get_job_status, trigger_jira_sync
from app.core.database import get_database
from app.models.unified_models import JobSchedule, User
from app.auth.auth_service import get_auth_service
from app.auth.auth_middleware import (
    get_current_user, require_authentication, require_admin,
    get_client_ip, get_user_agent
)

logger = get_logger(__name__)

# Setup templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter()

# Pydantic models
class LoginRequest(BaseModel):
    email: str
    password: str

class JobToggleRequest(BaseModel):
    active: bool

# Legacy function for backward compatibility - now uses proper authentication
async def verify_token(user: User = Depends(require_authentication)):
    """Verify JWT token - now uses proper authentication system"""
    # Return user for routes that need it, but maintain backward compatibility
    # for routes that just need authentication verification
    return user

# Web page routes
@router.get("/", response_class=HTMLResponse)
async def root():
    """Redirect to login page"""
    return RedirectResponse(url="/login")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Serve dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

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
            return {
                "success": True,
                "token": result["token"],
                "user": result["user"]
            }
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
                return {"success": True, "message": "Logged out successfully"}
            else:
                logger.warning(f"Failed to invalidate session for user: {user.email}")
                return {"success": False, "message": "Session not found"}
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

# Job management API routes
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
async def start_job(job_name: str, user: User = Depends(require_admin)):
    """Force start a specific job - requires admin privileges"""
    try:
        if job_name not in ['jira_sync', 'github_sync']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job name"
            )
        
        database = get_database()
        with database.get_session() as session:
            job = session.query(JobSchedule).filter(
                JobSchedule.job_name == job_name,
                JobSchedule.active == True
            ).first()
            
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            # Set job to PENDING to trigger execution
            job.status = 'PENDING'
            job.error_message = None
            session.commit()

            logger.info(f"Job {job_name} manually started")

            # Immediately trigger orchestrator to pick up the PENDING job
            try:
                from app.jobs.orchestrator import run_orchestrator
                import asyncio

                # Run orchestrator in background to pick up the PENDING job
                asyncio.create_task(run_orchestrator())
                logger.info(f"Orchestrator triggered to pick up {job_name}")

            except Exception as e:
                logger.warning(f"Failed to trigger orchestrator after Force Start: {e}")
                # Don't fail the Force Start if orchestrator trigger fails

            return {
                "success": True,
                "message": f"Job {job_name} started successfully and orchestrator triggered",
                "job_id": str(job.id)
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
async def stop_job(job_name: str, user: User = Depends(require_admin)):
    """Force stop a specific job - requires admin privileges"""
    try:
        if job_name not in ['jira_sync', 'github_sync']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job name"
            )
        
        database = get_database()
        with database.get_session() as session:
            job = session.query(JobSchedule).filter(
                JobSchedule.job_name == job_name,
                JobSchedule.active == True
            ).first()
            
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            # Handle job stopping based on job type
            if job.status == 'RUNNING':
                if job_name == 'jira_sync':
                    # Jira: Simple abort - saved items will be reprocessed later
                    job.status = 'FINISHED'
                    job.error_message = "Manually stopped - saved items will be reprocessed on next run"
                    logger.info(f"Jira job manually stopped - clean abort")

                elif job_name == 'github_sync':
                    # GitHub: Set to PENDING with checkpoint for recovery
                    job.status = 'PENDING'
                    job.error_message = "Manually stopped - will resume from last checkpoint"
                    job.retry_count += 1
                    logger.info(f"GitHub job manually stopped - will resume from checkpoint")

                session.commit()

                return {
                    "success": True,
                    "message": f"Job {job_name} stopped successfully",
                    "recovery_info": {
                        "jira_sync": "Saved items will be reprocessed on next run",
                        "github_sync": "Will resume from last checkpoint"
                    }.get(job_name, "")
                }
            else:
                return {
                    "success": False,
                    "message": f"Job {job_name} is not currently running"
                }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping job {job_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop job {job_name}"
        )

@router.post("/api/v1/jobs/{job_name}/toggle")
async def toggle_job_active(job_name: str, request: JobToggleRequest, token: str = Depends(verify_token)):
    """Toggle job active/inactive status"""
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
async def pause_job(job_name: str, token: str = Depends(verify_token)):
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
async def unpause_job(job_name: str, token: str = Depends(verify_token)):
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
async def force_start_orchestrator(token: str = Depends(verify_token)):
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
async def pause_orchestrator(token: str = Depends(verify_token)):
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
async def resume_orchestrator(token: str = Depends(verify_token)):
    """Resume the scheduled orchestrator"""
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


@router.get("/api/v1/orchestrator/status")
async def get_orchestrator_status(token: str = Depends(verify_token)):
    """Get orchestrator status"""
    try:
        from app.main import scheduler

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

        status_info = {
            "status": "paused" if is_paused else "running",
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "job_id": job.id,
            "name": job.name,
            "message": f"Orchestrator is {'paused' if is_paused else 'running'}"
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
    token: str = Depends(verify_token)
):
    """Update orchestrator schedule interval"""
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


@router.get("/api/v1/settings")
async def get_system_settings(token: str = Depends(verify_token)):
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
    token: str = Depends(verify_token)
):
    """Update a system setting"""
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



