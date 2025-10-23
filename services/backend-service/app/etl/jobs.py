"""
ETL Job Management APIs
Handles job status, control operations (pause/resume/force pending), and job details.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.database import get_db_session
from app.models.unified_models import Tenant
from app.auth.auth_middleware import require_authentication

import logging

logger = logging.getLogger(__name__)

# Service-to-service authentication for internal ETL operations
def verify_internal_auth(request: Request):
    """Verify internal authentication using ETL_INTERNAL_SECRET"""
    from app.core.config import get_settings
    settings = get_settings()
    internal_secret = settings.ETL_INTERNAL_SECRET
    provided = request.headers.get("X-Internal-Auth")

    if not internal_secret:
        logger.warning("ETL_INTERNAL_SECRET not configured; rejecting internal auth request")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Internal auth not configured")
    if not provided or provided != internal_secret:
        logger.warning(f"Invalid internal auth: expected secret, got {provided[:10] if provided else 'None'}...")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized internal request")

    logger.debug("Internal authentication successful")

# Hybrid authentication: accepts both user tokens and service-to-service auth
async def verify_hybrid_auth(request: Request):
    """
    Hybrid authentication that accepts either:
    1. Service-to-service authentication (X-Internal-Auth) - for ETL job operations
    2. User authentication (JWT token) - for UI operations (mappings, configs, etc.)

    Returns: dict with auth_type ('user' or 'service') and user info if applicable
    """
    # Try service-to-service auth first (X-Internal-Auth header)
    logger.debug(f"Hybrid auth: Checking headers: {dict(request.headers)}")
    try:
        verify_internal_auth(request)
        logger.info("Hybrid auth: Service-to-service authentication successful")
        return {"auth_type": "service", "user": None}
    except HTTPException as e:
        logger.debug(f"Hybrid auth: Service-to-service auth failed: {e}")
        pass  # Fall through to user auth

    # Try user authentication (JWT token)
    try:
        from app.auth.auth_middleware import require_authentication
        from fastapi.security import HTTPBearer
        from fastapi import Depends

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            # Create a mock credentials object
            from fastapi.security.http import HTTPAuthorizationCredentials
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

            # Use the existing require_authentication function
            user = await require_authentication(request, credentials)
            if user:
                logger.debug(f"Hybrid auth: User authentication successful for user: {user.email}")
                return {"auth_type": "user", "user": user}
    except Exception as e:
        logger.debug(f"Hybrid auth: User authentication failed: {e}")

    # Both authentication methods failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide either valid JWT token or X-Internal-Auth header."
    )

router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================

# Removed find_next_ready_job - no longer needed in autonomous architecture


# ============================================================================
# Pydantic Schemas
# ============================================================================

class JobCardResponse(BaseModel):
    """Response schema for job card display."""
    id: int
    job_name: str
    status: str  # 'READY', 'RUNNING', 'FINISHED', 'FAILED'
    active: bool
    schedule_interval_minutes: int
    retry_interval_minutes: int
    integration_id: Optional[int]
    integration_type: Optional[str]  # 'Jira', 'GitHub', 'WEX Fabric', 'WEX AD'
    integration_logo_filename: Optional[str]
    last_run_started_at: Optional[datetime]
    last_run_finished_at: Optional[datetime]
    next_run: Optional[datetime]
    error_message: Optional[str]
    retry_count: int


class JobDetailsResponse(BaseModel):
    """Detailed job information."""
    id: int
    job_name: str
    status: str
    active: bool
    schedule_interval_minutes: int
    retry_interval_minutes: int
    integration_id: Optional[int]

    # Timing information
    last_run_started_at: Optional[datetime]
    last_run_finished_at: Optional[datetime]
    created_at: datetime
    last_updated_at: datetime

    # Error tracking
    error_message: Optional[str]
    retry_count: int

    # Checkpoint data (JSONB)
    checkpoint_data: Optional[Dict[str, Any]]


class JobActionResponse(BaseModel):
    """Response for job actions."""
    success: bool
    message: str
    job_id: int
    new_status: str


class JobToggleRequest(BaseModel):
    """Request to toggle job active status."""
    active: bool


class JobSettingsRequest(BaseModel):
    """Request to update job settings."""
    schedule_interval_minutes: int = Field(..., ge=1, description="Schedule interval in minutes (must be >= 1)")
    retry_interval_minutes: int = Field(..., ge=1, description="Retry interval in minutes (must be >= 1)")


class JobSettingsResponse(BaseModel):
    """Response for job settings update."""
    success: bool
    message: str
    job_id: int
    schedule_interval_minutes: int
    retry_interval_minutes: int


class StepWorkerStatus(BaseModel):
    """Worker status for a specific step."""
    order: int = 0
    display_name: str = ""
    extraction: str = "idle"
    transform: str = "idle"
    embedding: str = "idle"


class JobStatusResponse(BaseModel):
    """Response for job status (JSON structure)."""
    job_id: int
    overall: str  # 'READY', 'RUNNING', 'FINISHED', 'FAILED'
    steps: Dict[str, StepWorkerStatus]
    last_updated: datetime


# ============================================================================
# Helper Functions
# ============================================================================

def get_integration_info(session: Session, integration_id: Optional[int]) -> tuple:
    """Get integration type and logo filename."""
    if not integration_id:
        return None, None

    from sqlalchemy import text
    query = text("""
        SELECT provider, logo_filename
        FROM integrations
        WHERE id = :integration_id
    """)
    result = session.execute(query, {'integration_id': integration_id}).fetchone()

    if result:
        return result[0], result[1]
    return None, None


def calculate_next_run(
    last_run_started_at: Optional[datetime],
    schedule_interval_minutes: int,
    retry_interval_minutes: int,
    status: str,
    retry_count: int
) -> Optional[datetime]:
    """
    Calculate when the job should run next.

    Logic:
    - If RUNNING: next_run is None (already running)
    - If FAILED with retries: use retry_interval_minutes from last_run_started_at
    - If never run (last_run_started_at is None): use schedule_interval_minutes from now
    - Otherwise: use schedule_interval_minutes from last_run_started_at

    Note: We use last_run_started_at as the baseline reference because:
    - It represents when the job actually started running
    - For first-time jobs, it's None so we calculate from current time
    - This ensures proper countdown behavior for all job types
    """
    from datetime import timedelta
    import pytz
    import os

    # Get timezone from environment (default to America/New_York which is GMT-5/GMT-4)
    tz_name = os.getenv('SCHEDULER_TIMEZONE', 'America/New_York')
    tz = pytz.timezone(tz_name)

    # If running (any active status), no next run
    if status in ['RUNNING']:
        return None

    # If never run (first time), schedule from now + interval
    if not last_run_started_at:
        now = datetime.now(tz)
        return now + timedelta(minutes=schedule_interval_minutes)

    # Ensure last_run_started_at is timezone-aware
    if last_run_started_at.tzinfo is None:
        last_run_started_at = tz.localize(last_run_started_at)

    # If failed with retries, use retry interval
    if status == 'FAILED' and retry_count > 0:
        return last_run_started_at + timedelta(minutes=retry_interval_minutes)

    # Otherwise use normal schedule interval
    return last_run_started_at + timedelta(minutes=schedule_interval_minutes)


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/jobs", response_model=List[JobCardResponse])
async def get_job_cards(
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session),
    auth_result: dict = Depends(verify_hybrid_auth)
):
    """
    Get all job cards for the home page dashboard.
    Returns jobs ordered alphabetically by job_name.
    Uses hybrid authentication (service-to-service or user JWT).
    """

    try:
        from sqlalchemy import text

        query = text("""
            SELECT
                id, job_name, status->>'overall' as status, active,
                schedule_interval_minutes, retry_interval_minutes,
                integration_id, last_run_started_at, last_run_finished_at,
                error_message, retry_count, last_updated_at
            FROM etl_jobs
            WHERE tenant_id = :tenant_id
            ORDER BY job_name ASC
        """)

        results = db.execute(query, {'tenant_id': tenant_id}).fetchall()

        job_cards = []
        for row in results:
            # Get integration info
            integration_type, logo_filename = get_integration_info(db, row[6])

            # Calculate next run using last_run_started_at (row[7])
            next_run = calculate_next_run(
                last_run_started_at=row[7],
                schedule_interval_minutes=row[4],
                retry_interval_minutes=row[5],
                status=row[2],
                retry_count=row[10]
            )

            job_cards.append(JobCardResponse(
                id=row[0],
                job_name=row[1],
                status=row[2],
                active=row[3],
                schedule_interval_minutes=row[4],
                retry_interval_minutes=row[5],
                integration_id=row[6],
                integration_type=integration_type,
                integration_logo_filename=logo_filename,
                last_run_started_at=row[7],
                last_run_finished_at=row[8],
                next_run=next_run,
                error_message=row[9],
                retry_count=row[10]
            ))

        return job_cards

    except Exception as e:
        logger.error(f"Error fetching job cards: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch job cards: {str(e)}")


@router.get("/jobs/{job_id}", response_model=JobDetailsResponse)
async def get_job_details(
    job_id: int,
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session),
    auth_result: dict = Depends(verify_hybrid_auth)
):
    """Get detailed information about a specific job."""

    try:
        from sqlalchemy import text
        import json

        query = text("""
            SELECT
                id, job_name, status, active,
                schedule_interval_minutes, retry_interval_minutes,
                integration_id, last_run_started_at, last_run_finished_at,
                created_at, last_updated_at, error_message, retry_count,
                checkpoint_data
            FROM etl_jobs
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)

        result = db.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        # Parse checkpoint_data if it exists
        checkpoint_data = result[13]
        if checkpoint_data and isinstance(checkpoint_data, str):
            try:
                checkpoint_data = json.loads(checkpoint_data)
            except:
                checkpoint_data = None

        return JobDetailsResponse(
            id=result[0],
            job_name=result[1],
            status=result[2],
            active=result[3],
            schedule_interval_minutes=result[4],
            retry_interval_minutes=result[5],
            integration_id=result[6],
            last_run_started_at=result[7],
            last_run_finished_at=result[8],
            created_at=result[9],
            last_updated_at=result[10],
            error_message=result[11],
            retry_count=result[12],
            checkpoint_data=checkpoint_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch job details: {str(e)}")


@router.post("/jobs/{job_id}/toggle-active", response_model=JobActionResponse)
async def toggle_job_active(
    job_id: int,
    request: JobToggleRequest,
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session),
    auth_result: dict = Depends(verify_hybrid_auth)
):
    """
    Toggle job active/inactive status.
    Inactive jobs are not executed by the orchestrator.
    """

    try:
        from sqlalchemy import text

        # Get current job
        query = text("""
            SELECT job_name, active, integration_id
            FROM etl_jobs
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        result = db.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        job_name, current_active, integration_id = result

        # If activating job, check if integration is active (inactive integration cannot have active jobs)
        if request.active and integration_id:
            integration_query = text("""
                SELECT active FROM integrations WHERE id = :integration_id
            """)
            integration_result = db.execute(integration_query, {'integration_id': integration_id}).fetchone()

            if integration_result and not integration_result[0]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot activate job {job_name} while its integration is inactive. Activate the integration first."
                )

        # Update active status
        update_query = text("""
            UPDATE etl_jobs
            SET active = :active, last_updated_at = NOW()
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        db.execute(update_query, {'job_id': job_id, 'tenant_id': tenant_id, 'active': request.active})
        db.commit()

        action = "activated" if request.active else "deactivated"
        logger.info(f"Job {job_name} (ID: {job_id}) {action}")

        return JobActionResponse(
            success=True,
            message=f"Job {job_name} {action} successfully",
            job_id=job_id,
            new_status="ACTIVE" if request.active else "INACTIVE"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error toggling job {job_id} active status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle job active status: {str(e)}")


@router.post("/jobs/{job_id}/run-now", response_model=JobActionResponse, status_code=202)
async def run_job_now(
    job_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session),
    auth_info: dict = Depends(verify_hybrid_auth)
):
    """
    Manually trigger a job to run immediately.
    Sets status to RUNNING and triggers actual job execution.

    For Jira jobs: Executes complete extraction with all 4 steps:
    1. Projects & Issue Types (0% -> 25%)
    2. Statuses & Project Relationships (25% -> 50%)
    3. Issues & Changelogs (50% -> 75%)
    4. Dev Status (75% -> 100%)

    Uses the same function as the automatic scheduler: execute_complete_jira_extraction()

    Supports both user authentication (manual triggers) and service-to-service auth (automatic scheduler).
    """
    try:
        # Log authentication type for debugging
        auth_type = auth_info.get("auth_type", "unknown")
        user = auth_info.get("user")
        if auth_type == "user" and user:
            logger.info(f"🔵 MANUAL TRIGGER: Job {job_id} manually triggered by user: {user.email}")
        elif auth_type == "service":
            logger.info(f"🟢 AUTO TRIGGER: Job {job_id} automatically triggered by job scheduler")
        else:
            logger.warning(f"⚠️ UNKNOWN TRIGGER: Job {job_id} triggered with unknown auth type: {auth_type}")
        from sqlalchemy import text

        # Get current job and integration details
        query = text("""
            SELECT j.job_name, j.status, j.active, j.integration_id,
                   i.provider, i.active as integration_active
            FROM etl_jobs j
            JOIN integrations i ON i.id = j.integration_id
            WHERE j.id = :job_id AND j.tenant_id = :tenant_id
        """)
        result = db.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        job_name, current_status, active, integration_id, provider, integration_active = result

        logger.info(f"📊 JOB STATUS CHECK: Job '{job_name}' current status = {current_status}")

        if not active:
            raise HTTPException(status_code=400, detail=f"Cannot run inactive job {job_name}")

        if not integration_active:
            raise HTTPException(status_code=400, detail=f"Cannot run job {job_name} - integration {provider} is inactive")

        if current_status == 'RUNNING':
            logger.warning(f"⚠️ ALREADY RUNNING: Job '{job_name}' is already RUNNING - rejecting request")
            raise HTTPException(status_code=400, detail=f"Job {job_name} is already running")

        # Set to RUNNING and record start time with proper timezone
        # Use atomic update to prevent race conditions
        from app.core.utils import DateTimeHelper
        now = DateTimeHelper.now_default()

        # Use atomic update with WHERE clause to prevent race conditions
        update_query = text("""
            UPDATE etl_jobs
            SET status = jsonb_set(status, ARRAY['overall'], to_jsonb('RUNNING'::text)),
                last_run_started_at = :now,
                last_updated_at = :now
            WHERE id = :job_id AND tenant_id = :tenant_id AND status->>'overall' != 'RUNNING'
        """)

        rows_updated = db.execute(update_query, {
            'job_id': job_id,
            'tenant_id': tenant_id,
            'now': now
        }).rowcount

        # If no rows were updated, another process already set it to RUNNING
        if rows_updated == 0:
            logger.warning(f"⚠️ RACE CONDITION: Job '{job_name}' was already set to RUNNING by another process")
            raise HTTPException(status_code=400, detail=f"Job {job_name} is already running")

        logger.info(f"✅ JOB STARTED: Job '{job_name}' (ID: {job_id}) status changed: {current_status} -> RUNNING")

        # Queue job for extraction instead of executing directly
        if job_name.lower() == 'jira':
            logger.info(f"🚀 Queuing Jira extraction job for background processing (integration {integration_id})")

            # Queue the job for extraction
            success = await _queue_jira_extraction_job(tenant_id, integration_id, job_id)

            if success:
                # Return HTTP 202 Accepted for non-blocking response

                return JobActionResponse(
                    success=True,
                    message=f"Job {job_name} queued successfully - extraction will begin shortly",
                    job_id=job_id,
                    new_status="QUEUED"
                )
            else:
                # Update job status to failed
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = 'FAILED',
                        error_message = 'Failed to queue extraction job',
                        last_updated_at = NOW()
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)
                db.execute(update_query, {'job_id': job_id, 'tenant_id': tenant_id})
                db.commit()

                raise HTTPException(
                    status_code=500,
                    detail="Failed to queue extraction job"
                )
        else:
            # For other jobs, set back to FINISHED with message
            finish_query = text("""
                UPDATE etl_jobs
                SET status = 'FINISHED',
                    last_run_finished_at = NOW()
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(finish_query, {'job_id': job_id, 'tenant_id': tenant_id})
            db.commit()

            return JobActionResponse(
                success=True,
                message=f"Job {job_name} completed - Phase 2.1 only supports Jira jobs",
                job_id=job_id,
                new_status="FINISHED"
            )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error running job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to run job: {str(e)}")



@router.post("/jobs/debug/start-scheduler")
async def debug_start_scheduler(
    request: Request,
    auth_info: dict = Depends(verify_hybrid_auth)
):
    """Debug endpoint to manually start the job scheduler"""
    try:
        from app.etl.job_scheduler import start_job_scheduler
        await start_job_scheduler()
        return {"success": True, "message": "Job scheduler started successfully"}
    except Exception as e:
        logger.error(f"Failed to start job scheduler: {e}")
        return {"success": False, "message": f"Failed to start job scheduler: {str(e)}"}

@router.get("/jobs/debug/scheduler-status")
async def debug_scheduler_status(
    request: Request,
    auth_info: dict = Depends(verify_hybrid_auth)
):
    """Debug endpoint to check job scheduler status"""
    try:
        from app.etl.job_scheduler import get_job_timer_manager
        manager = get_job_timer_manager()

        active_timers = len(manager.job_timers)
        timer_info = []

        for job_id, timer in manager.job_timers.items():
            timer_info.append({
                "job_id": job_id,
                "job_name": timer.job_name,
                "tenant_id": timer.tenant_id,
                "running": timer.running
            })

        return {
            "success": True,
            "active_timers": active_timers,
            "timers": timer_info,
            "message": f"Job scheduler has {active_timers} active timers"
        }
    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}")
        return {"success": False, "message": f"Failed to get scheduler status: {str(e)}"}

@router.post("/jobs/{job_id}/settings", response_model=JobSettingsResponse)
async def update_job_settings(
    job_id: int,
    request: JobSettingsRequest,
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session),
    auth_result: dict = Depends(verify_hybrid_auth)
):
    """
    Update job scheduling settings.
    """

    try:
        from sqlalchemy import text

        # Validate retry_interval < schedule_interval
        if request.retry_interval_minutes >= request.schedule_interval_minutes:
            raise HTTPException(
                status_code=400,
                detail="Retry interval must be less than schedule interval"
            )

        # Get current job
        query = text("""
            SELECT job_name
            FROM etl_jobs
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        result = db.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        job_name = result[0]

        # Update settings
        update_query = text("""
            UPDATE etl_jobs
            SET schedule_interval_minutes = :schedule_interval,
                retry_interval_minutes = :retry_interval,
                last_updated_at = NOW()
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        db.execute(update_query, {
            'job_id': job_id,
            'tenant_id': tenant_id,
            'schedule_interval': request.schedule_interval_minutes,
            'retry_interval': request.retry_interval_minutes
        })
        db.commit()

        logger.info(f"Job {job_name} (ID: {job_id}) settings updated: "
                   f"schedule={request.schedule_interval_minutes}m, retry={request.retry_interval_minutes}m")

        return JobSettingsResponse(
            success=True,
            message=f"Settings for {job_name} updated successfully",
            job_id=job_id,
            schedule_interval_minutes=request.schedule_interval_minutes,
            retry_interval_minutes=request.retry_interval_minutes
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating job {job_id} settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update job settings: {str(e)}")


async def _queue_jira_extraction_job(tenant_id: int, integration_id: int, job_id: int) -> bool:
    """
    Queue Jira extraction job for background processing.

    Args:
        tenant_id: Tenant ID
        integration_id: Integration ID for the Jira extraction
        job_id: Job ID to update status

    Returns:
        bool: True if queued successfully
    """
    try:
        from app.etl.queue.queue_manager import QueueManager
        from sqlalchemy import text
        from app.core.database import get_database

        # Note: Job status is already set to 'RUNNING' by run_job_now function
        # No need to update it again here to avoid database locks

        logger.info(f"✅ Job {job_id} status updated to QUEUED")

        # Queue the first extraction step: projects and issue types
        queue_manager = QueueManager()

        message = {
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'job_id': job_id,
            'extraction_type': 'jira_projects_and_issue_types'
        }

        # Get tenant tier and route to tier-based extraction queue
        tier = queue_manager._get_tenant_tier(tenant_id)
        tier_queue = queue_manager.get_tier_queue_name(tier, 'extraction')

        success = queue_manager._publish_message(tier_queue, message)

        if success:
            logger.info(f"✅ Jira extraction job queued successfully to {tier_queue}")
            return True
        else:
            logger.error(f"❌ Failed to publish extraction message to {tier_queue}")
            return False

    except Exception as e:
        logger.error(f"Error queuing Jira extraction: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False


@router.get("/jobs/{job_id}/worker-status", response_model=JobStatusResponse)
async def get_job_worker_status(
    job_id: int,
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session),
    auth_result: dict = Depends(verify_hybrid_auth)
):
    """
    Get current worker status for a job (hybrid approach fallback).

    This endpoint provides database-backed worker status for cases where
    WebSocket connections fail or when users login after a job has started.

    Args:
        job_id: Job ID to get worker status for
        tenant_id: Tenant ID from auth
        db: Database session

    Returns:
        JobWorkerStatusResponse: Current worker status from database
    """
    try:
        from sqlalchemy import text

        # Query current JSON status from database
        query = text("""
            SELECT status, last_updated_at
            FROM etl_jobs
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)

        result = db.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        (status_json, last_updated_at) = result

        # Parse JSON status
        import json
        status_data = json.loads(status_json) if isinstance(status_json, str) else status_json

        # Convert steps to StepWorkerStatus objects
        steps = {}
        for step_name, step_data in status_data.get('steps', {}).items():
            steps[step_name] = StepWorkerStatus(
                order=step_data.get('order', 0),
                display_name=step_data.get('display_name', step_name),
                extraction=step_data.get('extraction', 'idle'),
                transform=step_data.get('transform', 'idle'),
                embedding=step_data.get('embedding', 'idle')
            )

        return JobStatusResponse(
            job_id=job_id,
            overall=status_data.get('overall', 'READY'),
            steps=steps,
            last_updated=last_updated_at or datetime.now()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job worker status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job worker status: {str(e)}")


@router.get("/jobs/{job_id}/check-completion", response_model=dict)
async def check_job_completion(
    job_id: int,
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session),
    auth_result: dict = Depends(verify_hybrid_auth)
):
    """
    Check if all job steps are truly finished.

    This endpoint implements the hybrid approach:
    1. Checks if overall status is FINISHED
    2. Checks if ALL internal steps (extraction, transform, embedding) are FINISHED
    3. Returns whether to reset immediately or wait

    Returns:
        {
            "all_finished": bool,  # True if all steps are FINISHED
            "overall_status": str,  # Current overall status
            "steps": dict  # Current step statuses
        }
    """
    try:
        from sqlalchemy import text
        import json

        # Get job status
        query = text("""
            SELECT status
            FROM etl_jobs
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        result = db.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        status_json = result[0]
        if isinstance(status_json, str):
            status_json = json.loads(status_json)

        overall_status = status_json.get('overall', 'UNKNOWN')
        steps = status_json.get('steps', {})

        # Check if ALL steps are FINISHED
        # Special case: dev_status can be idle (when no issues were extracted)
        all_steps_finished = True
        if overall_status == 'FINISHED':
            for step_name, step_data in steps.items():
                extraction_status = step_data.get('extraction', 'idle')
                transform_status = step_data.get('transform', 'idle')
                embedding_status = step_data.get('embedding', 'idle')

                # For dev_status step: can be either all finished OR all idle (no issues extracted)
                if step_name == 'jira_dev_status':
                    is_finished = (extraction_status == 'finished' and
                                   transform_status == 'finished' and
                                   embedding_status == 'finished')
                    is_idle = (extraction_status == 'idle' and
                               transform_status == 'idle' and
                               embedding_status == 'idle')

                    if not (is_finished or is_idle):
                        all_steps_finished = False
                        logger.info(f"🔍 Step {step_name} not in valid state: extraction={extraction_status}, transform={transform_status}, embedding={embedding_status}")
                        break
                else:
                    # All other steps must be 'finished'
                    if not (extraction_status == 'finished' and
                            transform_status == 'finished' and
                            embedding_status == 'finished'):
                        all_steps_finished = False
                        logger.info(f"🔍 Step {step_name} not fully finished: extraction={extraction_status}, transform={transform_status}, embedding={embedding_status}")
                        break

        logger.info(f"🔍 Job {job_id} completion check: overall={overall_status}, all_steps_finished={all_steps_finished}")

        # Include server timestamp for accurate client-side calculations
        from datetime import datetime
        server_time = datetime.utcnow().isoformat()

        return {
            "all_finished": all_steps_finished,
            "overall_status": overall_status,
            "steps": steps,
            "server_time": server_time
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking job completion: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check job completion: {str(e)}")


@router.post("/jobs/{job_id}/reset", response_model=JobActionResponse)
async def reset_job_status(
    job_id: int,
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session),
    auth_result: dict = Depends(verify_hybrid_auth)
):
    """
    Reset ETL job status to READY state.

    This endpoint:
    1. Validates the job exists and belongs to the tenant
    2. Resets all step statuses to 'idle'
    3. Sets overall status to 'READY'
    4. Used by frontend auto-reset after job completion
    """
    try:
        from sqlalchemy import text
        import json

        # Get job details to validate existence
        query = text("""
            SELECT job_name, status
            FROM etl_jobs
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        result = db.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        job_name, current_status = result

        # Parse current status to preserve step structure
        if isinstance(current_status, str):
            current_status = json.loads(current_status)

        # Reset all step statuses to idle
        if 'steps' in current_status:
            for step_name, step_data in current_status['steps'].items():
                step_data['extraction'] = 'idle'
                step_data['transform'] = 'idle'
                step_data['embedding'] = 'idle'

        # Set overall status to READY
        current_status['overall'] = 'READY'

        # Update database
        update_query = text("""
            UPDATE etl_jobs
            SET status = :status,
                last_updated_at = NOW()
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        db.execute(update_query, {
            'job_id': job_id,
            'tenant_id': tenant_id,
            'status': json.dumps(current_status)
        })
        db.commit()

        logger.info(f"🔄 ETL job {job_name} (ID: {job_id}) status reset to READY for tenant {tenant_id}")

        return JobActionResponse(
            success=True,
            message=f"Job {job_name} status reset successfully",
            job_id=job_id,
            new_status="READY"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error resetting job {job_id} status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset job status: {str(e)}")

