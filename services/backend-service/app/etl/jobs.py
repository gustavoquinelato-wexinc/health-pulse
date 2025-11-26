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
from app.core.utils import DateTimeHelper

import logging

logger = logging.getLogger(__name__)

# Service-to-service authentication for internal ETL operations
def verify_internal_auth(request: Request):
    """Verify internal authentication using ETL_INTERNAL_SECRET"""
    from app.core.config import get_settings
    settings = get_settings()
    internal_secret = settings.ETL_INTERNAL_SECRET
    provided = request.headers.get("X-Internal-Auth")

    logger.info(f"🔐 Internal auth check: provided={provided}, secret_configured={bool(internal_secret)}")

    if not internal_secret:
        logger.warning("ETL_INTERNAL_SECRET not configured; rejecting internal auth request")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Internal auth not configured")
    if not provided or provided != internal_secret:
        # Don't log warning here - it's expected to fail when using user auth instead
        # The warning will be logged in verify_hybrid_auth if BOTH auth methods fail
        logger.info(f"🔐 Internal auth failed: provided={provided}, expected={internal_secret}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized internal request")

    logger.info("🔐 Internal authentication successful")

# Hybrid authentication: accepts both user tokens and service-to-service auth
async def verify_hybrid_auth(request: Request):
    """
    Hybrid authentication that accepts either:
    1. Service-to-service authentication (X-Internal-Auth) - for ETL job operations
    2. User authentication (JWT token) - for UI operations (mappings, configs, etc.)

    Returns: dict with auth_type ('user' or 'service') and user info if applicable
    """
    # Try service-to-service auth first (X-Internal-Auth header)
    logger.info(f"🔐 Hybrid auth: Checking headers for X-Internal-Auth")
    try:
        verify_internal_auth(request)
        logger.info("🔐 Hybrid auth: Service-to-service authentication successful")
        return {"auth_type": "service", "user": None}
    except HTTPException as e:
        logger.info(f"🔐 Hybrid auth: Service-to-service auth failed ({e.detail}), trying user auth")
        pass  # Fall through to user auth

    # Try user authentication (JWT token)
    try:
        token = None

        # 1. Try Authorization header first (for REST API calls)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            logger.debug("Hybrid auth: Found token in Authorization header")

        # 2. Try query parameter (for WebSocket connections)
        if not token:
            token = request.query_params.get("token")
            if token:
                logger.debug("Hybrid auth: Found token in query parameter")

        # 3. Try cookies (for session-based auth)
        if not token:
            token = request.cookies.get("pulse_token")
            if token:
                logger.debug("Hybrid auth: Found token in cookie")

        if token:
            # Verify token using auth service
            from app.auth.auth_service import get_auth_service
            auth_service = get_auth_service()
            user = await auth_service.verify_token(token, suppress_errors=False)

            if user:
                logger.info(f"Hybrid auth: User authentication successful for user: {user.email}")
                return {"auth_type": "user", "user": user}
            else:
                logger.debug("Hybrid auth: Token verification returned None")
        else:
            logger.debug("Hybrid auth: No token found in Authorization header, query params, or cookies")
    except Exception as e:
        logger.debug(f"Hybrid auth: User authentication failed: {e}")

    # Both authentication methods failed
    logger.warning("Hybrid auth: Both service-to-service and user authentication failed")
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
    status: Dict[str, Any]  # Full status JSON including overall, token, reset_deadline, reset_attempt, steps
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

    class Config:
        json_encoders = {
            # Convert timezone-naive datetimes (stored in NY timezone) to ISO with timezone info
            datetime: lambda v: DateTimeHelper.to_iso_with_tz(v) if v else None
        }


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

    # Checkpoint flag (Boolean - indicates if job has checkpoint records)
    checkpoint_data: bool

    class Config:
        json_encoders = {
            # Convert timezone-naive datetimes (stored in NY timezone) to ISO with timezone info
            datetime: lambda v: DateTimeHelper.to_iso_with_tz(v) if v else None
        }


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

    Returns timezone-naive datetime in configured timezone (America/New_York by default).
    """
    from datetime import timedelta

    # If running (any active status), no next run
    if status in ['RUNNING']:
        return None

    # If never run (first time), schedule from now + interval
    if not last_run_started_at:
        # Use DateTimeHelper.now_default() to get timezone-naive datetime in configured timezone
        now = DateTimeHelper.now_default()
        return now + timedelta(minutes=schedule_interval_minutes)

    # last_run_started_at is already timezone-naive in configured timezone
    # No need to convert - just add the interval

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
        import json

        query = text("""
            SELECT
                id, job_name, status, active,
                schedule_interval_minutes, retry_interval_minutes,
                integration_id, last_run_started_at, last_run_finished_at,
                error_message, retry_count, last_updated_at, next_run
            FROM etl_jobs
            WHERE tenant_id = :tenant_id
            ORDER BY job_name ASC
        """)

        results = db.execute(query, {'tenant_id': tenant_id}).fetchall()

        job_cards = []
        for row in results:
            # Parse status JSON
            status_json = row[2]
            if isinstance(status_json, str):
                status_json = json.loads(status_json)

            # Get integration info
            integration_type, logo_filename = get_integration_info(db, row[6])

            # 🔑 Use next_run from database (row[12]) instead of calculating it
            # The job scheduler maintains this column and it's the source of truth
            next_run = row[12]

            job_cards.append(JobCardResponse(
                id=row[0],
                job_name=row[1],
                status=status_json,  # Full status JSON
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
                id, job_name, status->>'overall' as status, active,
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

        # checkpoint_data is now a boolean flag
        checkpoint_data = result[13] if result[13] is not None else False

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
            SELECT job_name, active, integration_id, last_run_started_at,
                   schedule_interval_minutes, retry_interval_minutes,
                   status->>'overall' as status, retry_count
            FROM etl_jobs
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        result = db.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        (job_name, current_active, integration_id, last_run_started_at,
         schedule_interval_minutes, retry_interval_minutes, status, retry_count) = result

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

        # If activating an inactive job, recalculate next_run
        if request.active and not current_active:
            # Recalculate next_run when activating
            next_run = calculate_next_run(
                last_run_started_at=last_run_started_at,
                schedule_interval_minutes=schedule_interval_minutes,
                retry_interval_minutes=retry_interval_minutes,
                status=status,
                retry_count=retry_count
            )

            # Update active status AND next_run
            update_query = text("""
                UPDATE etl_jobs
                SET active = :active,
                    next_run = :next_run,
                    last_updated_at = NOW()
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(update_query, {
                'job_id': job_id,
                'tenant_id': tenant_id,
                'active': request.active,
                'next_run': next_run
            })
            logger.info(f"Job {job_name} (ID: {job_id}) activated with next_run recalculated to {next_run}")
        else:
            # Just update active status (deactivating or already active)
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

        job_name, status_json, active, integration_id, provider, integration_active = result

        # Parse status JSON to extract overall status
        import json
        if isinstance(status_json, str):
            status_json = json.loads(status_json)
        current_status = status_json.get('overall', 'READY')

        logger.info(f"📊 JOB STATUS CHECK: Job '{job_name}' current status = {current_status}")

        if not active:
            raise HTTPException(status_code=400, detail=f"Cannot run inactive job {job_name}")

        if not integration_active:
            raise HTTPException(status_code=400, detail=f"Cannot run job {job_name} - integration {provider} is inactive")

        if current_status == 'RUNNING':
            logger.warning(f"⚠️ ALREADY RUNNING: Job '{job_name}' is already RUNNING - rejecting request")
            raise HTTPException(status_code=400, detail=f"Job {job_name} is already running")

        # 🔑 Allow running jobs with RATE_LIMITED status (manual override)
        if current_status == 'RATE_LIMITED':
            logger.info(f"✅ RATE_LIMITED OVERRIDE: Allowing manual run of job '{job_name}' (status: RATE_LIMITED)")

        if current_status == 'FINISHED':
            logger.warning(f"⚠️ JOB FINISHING: Job '{job_name}' is FINISHED and resetting - rejecting request")
            raise HTTPException(status_code=400, detail=f"Job {job_name} is resetting. Please wait a moment and try again.")

        # Set to RUNNING and record start time with proper timezone
        # Use atomic update to prevent race conditions
        from app.core.utils import DateTimeHelper
        import uuid
        now = DateTimeHelper.now_default()
        job_token = str(uuid.uuid4())  # 🔑 Generate unique token for this job execution

        # Use atomic update with WHERE clause to prevent race conditions
        # 🔑 Set overall status to RUNNING, set token, and clear reset_deadline/reset_attempt
        # Also clear error_message when transitioning to RUNNING
        update_query = text("""
            UPDATE etl_jobs
            SET status = jsonb_set(
                  jsonb_set(
                    jsonb_set(
                      jsonb_set(status, ARRAY['overall'], to_jsonb('RUNNING'::text)),
                      ARRAY['token'], to_jsonb(CAST(:token AS text))
                    ),
                    ARRAY['reset_deadline'], 'null'::jsonb
                  ),
                  ARRAY['reset_attempt'], to_jsonb(0)
                ),
                last_run_started_at = :now,
                last_updated_at = :now,
                error_message = NULL
            WHERE id = :job_id AND tenant_id = :tenant_id AND status->>'overall' != 'RUNNING'
        """)

        rows_updated = db.execute(update_query, {
            'job_id': job_id,
            'tenant_id': tenant_id,
            'now': now,
            'token': job_token  # 🔑 Pass the generated token
        }).rowcount

        # If no rows were updated, another process already set it to RUNNING
        if rows_updated == 0:
            logger.warning(f"⚠️ RACE CONDITION: Job '{job_name}' was already set to RUNNING by another process")
            raise HTTPException(status_code=400, detail=f"Job {job_name} is already running")

        # 🔑 Commit the transaction so the token is visible to other sessions
        db.commit()

        logger.info(f"✅ JOB STARTED: Job '{job_name}' (ID: {job_id}) status changed: {current_status} -> RUNNING")

        # 🔑 Send WebSocket update to notify frontend that job is now RUNNING
        # This ensures the UI updates immediately when user clicks "Run Now"
        try:
            from app.api.websocket_routes import get_job_websocket_manager
            import asyncio

            # Get the updated job status from database
            status_query = text("SELECT status FROM etl_jobs WHERE id = :job_id AND tenant_id = :tenant_id")
            status_result = db.execute(status_query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

            if status_result:
                job_status = status_result[0]

                # Send WebSocket notification with the updated status
                job_websocket_manager = get_job_websocket_manager()

                # Send WebSocket update directly (we're already in an async context)
                try:
                    await job_websocket_manager.send_job_status_update(
                        tenant_id=tenant_id,
                        job_id=job_id,
                        status_json=job_status
                    )
                    logger.info(f"✅ WebSocket update sent for job {job_id} - status changed to RUNNING")
                except Exception as ws_error:
                    logger.warning(f"⚠️ Failed to send WebSocket update for job {job_id}: {ws_error}")
                    # Don't fail the request if WebSocket update fails - job is still queued
        except Exception as e:
            logger.warning(f"⚠️ Failed to send WebSocket update for job {job_id}: {e}")

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
                    SET status = jsonb_set(status, ARRAY['overall'], to_jsonb('FAILED'::text)),
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
        elif job_name.lower() == 'github':
            logger.info(f"🚀 Queuing GitHub extraction job for background processing (integration {integration_id})")

            # Queue the job for extraction
            success = await _queue_github_extraction_job(tenant_id, integration_id, job_id)

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
                    SET status = jsonb_set(status, ARRAY['overall'], to_jsonb('FAILED'::text)),
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
                SET status = jsonb_set(status, ARRAY['overall'], to_jsonb('FINISHED'::text)),
                    last_run_finished_at = NOW()
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(finish_query, {'job_id': job_id, 'tenant_id': tenant_id})
            db.commit()

            return JobActionResponse(
                success=True,
                message=f"Job {job_name} completed - Phase 2.1 only supports Jira and GitHub jobs",
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

        # Get current job details to recalculate next_run
        job_query = text("""
            SELECT status->>'overall' as overall_status,
                   last_run_started_at,
                   retry_count
            FROM etl_jobs
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        job_result = db.execute(job_query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

        if not job_result:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        status, last_run_started_at, retry_count = job_result

        # Recalculate next_run with new schedule interval using timezone-aware calculation
        next_run = calculate_next_run(
            last_run_started_at=last_run_started_at,
            schedule_interval_minutes=request.schedule_interval_minutes,
            retry_interval_minutes=request.retry_interval_minutes,
            status=status,
            retry_count=retry_count
        )

        # Update settings AND next_run
        update_query = text("""
            UPDATE etl_jobs
            SET schedule_interval_minutes = :schedule_interval,
                retry_interval_minutes = :retry_interval,
                next_run = :next_run,
                last_updated_at = NOW()
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        db.execute(update_query, {
            'job_id': job_id,
            'tenant_id': tenant_id,
            'schedule_interval': request.schedule_interval_minutes,
            'retry_interval': request.retry_interval_minutes,
            'next_run': next_run
        })
        db.commit()

        logger.info(f"Job {job_name} (ID: {job_id}) settings updated: "
                   f"schedule={request.schedule_interval_minutes}m, retry={request.retry_interval_minutes}m, next_run={next_run}")

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
        from app.etl.workers.queue_manager import QueueManager
        from sqlalchemy import text
        from app.core.database import get_database
        import json

        # Note: Job status is already set to 'RUNNING' by run_job_now function
        # No need to update it again here to avoid database locks

        logger.info(f"✅ Job {job_id} status already set to RUNNING - queuing extraction")

        # 🔑 Fetch the job token and last_sync_date from the database
        database = get_database()
        job_token = None
        old_last_sync_date = None

        with database.get_read_session_context() as session:
            query = text("""
                SELECT status, last_sync_date
                FROM etl_jobs
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            result = session.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

            if result:
                status = result[0]
                if isinstance(status, str):
                    status = json.loads(status)
                job_token = status.get('token')  # 🔑 Get token from status JSON

                # 🔑 Get last_sync_date for incremental sync
                last_sync_date = result[1]
                if last_sync_date:
                    # Convert datetime to string format with FULL TIMESTAMP (YYYY-MM-DD HH:MM:SS)
                    if isinstance(last_sync_date, str):
                        old_last_sync_date = last_sync_date  # Keep full timestamp
                    else:
                        old_last_sync_date = last_sync_date.strftime('%Y-%m-%d %H:%M:%S')
                    logger.info(f"📅 Using last_sync_date from database: {old_last_sync_date}")
                else:
                    logger.info(f"📅 No last_sync_date found in database, extraction will use 2-year default")

        # Queue the first extraction step: projects and issue types
        queue_manager = QueueManager()

        message = {
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'job_id': job_id,
            'type': 'jira_projects_and_issue_types',  # 🔑 Use 'type' field for extraction worker router
            'provider': 'jira',  # 🔑 Add provider field for routing
            'token': job_token,  # 🔑 Include token in message
            'old_last_sync_date': old_last_sync_date  # 🔑 Pass last_sync_date for incremental sync
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


async def _queue_github_extraction_job(tenant_id: int, integration_id: int, job_id: int) -> bool:
    """
    Queue GitHub extraction job for background processing.

    GitHub job is a 2-step process:
    1. github_repositories: Extract all repositories
    2. github_prs_commits_reviews_comments: Extract PRs with nested data (commits, reviews, comments)

    The transform worker for github_repositories will trigger the next step when it completes.

    RECOVERY: If job has rate limit checkpoint, resume from checkpoint instead of starting fresh.

    Args:
        tenant_id: Tenant ID
        integration_id: Integration ID for the GitHub extraction
        job_id: Job ID to update status

    Returns:
        bool: True if queued successfully
    """
    try:
        from app.etl.workers.queue_manager import QueueManager
        from sqlalchemy import text
        from app.core.database import get_database
        from app.models.unified_models import EtlJob
        import json

        # Note: Job status is already set to 'RUNNING' by run_job_now function
        # No need to update it again here to avoid database locks

        logger.info(f"✅ Job {job_id} status already set to RUNNING - queuing extraction")

        # 🔑 Check for checkpoint flag (new checkpoint system)
        database = get_database()
        with database.get_read_session_context() as db:
            job = db.query(EtlJob).filter(
                EtlJob.id == job_id,
                EtlJob.tenant_id == tenant_id
            ).first()

            if job and job.checkpoint_data:  # Boolean flag check
                logger.info(f"� Job {job_id} has checkpoint data - resuming from checkpoints")

                # Get job token from status JSON
                status = job.status if isinstance(job.status, dict) else json.loads(job.status)
                job_token = status.get('token')

                if not job_token:
                    logger.error(f"No token found in job status for checkpoint recovery")
                    return False

                # Query checkpoints with data
                from app.etl.github.github_extraction_worker import query_checkpoints_with_data
                checkpoints = query_checkpoints_with_data(
                    job_id=job_id,
                    tenant_id=tenant_id,
                    token=job_token
                )

                if not checkpoints:
                    logger.warning(f"No checkpoints with data found for job {job_id}, starting fresh")
                    # Clear the flag and start fresh
                    with database.get_write_session_context() as write_db:
                        update_query = text("""
                            UPDATE etl_jobs
                            SET checkpoint_data = FALSE
                            WHERE id = :job_id AND tenant_id = :tenant_id
                        """)
                        write_db.execute(update_query, {'job_id': job_id, 'tenant_id': tenant_id})
                else:
                    logger.info(f"� Found {len(checkpoints)} checkpoints to resume")

                    # Queue PR extraction for each checkpoint with data
                    queue_manager = QueueManager()

                    for i, checkpoint in enumerate(checkpoints):
                        is_first = (i == 0)
                        is_last = (i == len(checkpoints) - 1)

                        checkpoint_data = checkpoint['checkpoint_data']
                        owner = checkpoint['owner']
                        repo_name = checkpoint['repo_name']
                        full_name = checkpoint['full_name']

                        # Extract checkpoint details
                        node_type = checkpoint_data.get('node_type')

                        if node_type == 'prs':
                            # Resume PR extraction
                            pr_cursor = checkpoint_data.get('last_pr_cursor')
                            logger.info(f"📥 Resuming PR extraction for {full_name} with cursor: {pr_cursor}")

                            message = {
                                'tenant_id': tenant_id,
                                'integration_id': integration_id,
                                'job_id': job_id,
                                'type': 'github_prs_commits_reviews_comments',
                                'provider': 'github',
                                'owner': owner,
                                'repo_name': repo_name,
                                'full_name': full_name,
                                'pr_cursor': pr_cursor,
                                'first_item': is_first,
                                'last_item': False,
                                'last_job_item': False,
                                'last_repo': is_last,
                                'token': job_token,
                                'old_last_sync_date': job.last_sync_date.strftime('%Y-%m-%d %H:%M:%S') if job.last_sync_date else None
                            }

                            tier = queue_manager._get_tenant_tier(tenant_id)
                            tier_queue = queue_manager.get_tier_queue_name(tier, 'extraction')
                            queue_manager._publish_message(tier_queue, message)

                        elif node_type in ['commits', 'reviews', 'comments', 'review_threads']:
                            # Resume nested extraction
                            pr_node_id = checkpoint_data.get('current_pr_node_id')
                            nested_cursor = checkpoint_data.get('nested_cursor')
                            logger.info(f"📥 Resuming {node_type} extraction for {full_name}, PR {pr_node_id}")

                            message = {
                                'tenant_id': tenant_id,
                                'integration_id': integration_id,
                                'job_id': job_id,
                                'type': 'github_prs_commits_reviews_comments',
                                'provider': 'github',
                                'owner': owner,
                                'repo_name': repo_name,
                                'full_name': full_name,
                                'pr_node_id': pr_node_id,
                                'nested_type': node_type,
                                'nested_cursor': nested_cursor,
                                'first_item': is_first,
                                'last_item': False,
                                'last_job_item': False,
                                'last_repo': is_last,
                                'last_pr_last_nested': is_last,  # Assume last nested for simplicity
                                'token': job_token,
                                'old_last_sync_date': job.last_sync_date.strftime('%Y-%m-%d %H:%M:%S') if job.last_sync_date else None
                            }

                            tier = queue_manager._get_tenant_tier(tenant_id)
                            tier_queue = queue_manager.get_tier_queue_name(tier, 'extraction')
                            queue_manager._publish_message(tier_queue, message)

                    logger.info(f"✅ Queued {len(checkpoints)} checkpoint recovery messages")
                    return True

        # Normal start (no recovery checkpoint)
        logger.info(f"🚀 Starting fresh GitHub extraction for job {job_id}")

        # 🔑 Fetch the job token and last_sync_date from the database
        database = get_database()
        job_token = None
        old_last_sync_date = None

        with database.get_read_session_context() as session:
            query = text("""
                SELECT status, last_sync_date
                FROM etl_jobs
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            result = session.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

            if result:
                status = result[0]
                if isinstance(status, str):
                    status = json.loads(status)
                job_token = status.get('token')  # 🔑 Get token from status JSON

                # 🔑 Get last_sync_date for incremental sync
                last_sync_date = result[1]
                if last_sync_date:
                    # Convert datetime to string format with FULL TIMESTAMP (YYYY-MM-DD HH:MM:SS)
                    if isinstance(last_sync_date, str):
                        old_last_sync_date = last_sync_date  # Keep full timestamp
                    else:
                        old_last_sync_date = last_sync_date.strftime('%Y-%m-%d %H:%M:%S')
                    logger.info(f"📅 Using last_sync_date from database: {old_last_sync_date}")
                else:
                    logger.info(f"📅 No last_sync_date found in database, extraction will use 2-year default")

        # Queue the first extraction step: github_repositories
        queue_manager = QueueManager()

        message = {
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'job_id': job_id,
            'type': 'github_repositories',  # 🔑 Step 1: Repository discovery
            'provider': 'github',
            'first_item': True,  # First step of 2-step job
            'last_item': False,   # Not the last step - PR extraction comes next
            'token': job_token,  # 🔑 Include token in message
            'old_last_sync_date': old_last_sync_date  # 🔑 Pass last_sync_date for incremental sync
        }

        # Get tenant tier and route to tier-based extraction queue
        tier = queue_manager._get_tenant_tier(tenant_id)
        tier_queue = queue_manager.get_tier_queue_name(tier, 'extraction')

        success = queue_manager._publish_message(tier_queue, message)

        if success:
            logger.info(f"✅ GitHub extraction job queued successfully to {tier_queue}")
            logger.info(f"📋 GitHub job flow: Step 1 (github_repositories) → Step 2 (github_prs_commits_reviews_comments)")
            return True
        else:
            logger.error(f"❌ Failed to publish extraction message to {tier_queue}")
            return False

    except Exception as e:
        logger.error(f"Error queuing GitHub extraction: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False


async def _queue_github_prs_extraction(
    tenant_id: int,
    integration_id: int,
    job_id: int,
    pr_cursor: Optional[str] = None
) -> bool:
    """
    Queue GitHub PRs extraction message with optional cursor for recovery.

    Args:
        tenant_id: Tenant ID
        integration_id: Integration ID
        job_id: Job ID
        pr_cursor: Optional cursor for pagination (used for recovery)

    Returns:
        bool: True if queued successfully
    """
    try:
        from app.etl.workers.queue_manager import QueueManager

        queue_manager = QueueManager()

        message = {
            'type': 'github_prs_commits_reviews_comments',
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'job_id': job_id,
            'pr_cursor': pr_cursor,
            'first_item': True,
            'last_item': False,
            'provider': 'github'
        }

        # Get tenant tier and route to tier-based extraction queue
        tier = queue_manager._get_tenant_tier(tenant_id)
        tier_queue = queue_manager.get_tier_queue_name(tier, 'extraction')

        success = queue_manager._publish_message(tier_queue, message)

        if success:
            logger.info(f"✅ Queued PR extraction (cursor: {pr_cursor or 'None'}) to {tier_queue}")
            return True
        else:
            logger.error(f"❌ Failed to queue PR extraction")
            return False

    except Exception as e:
        logger.error(f"Error queuing PR extraction: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False


async def _queue_github_nested_extraction(
    tenant_id: int,
    integration_id: int,
    job_id: int,
    pr_id: str,
    pr_node_id: str,
    nested_nodes_status: Optional[dict] = None
) -> bool:
    """
    Queue nested extraction message with partial state for recovery.

    Args:
        tenant_id: Tenant ID
        integration_id: Integration ID
        job_id: Job ID
        pr_id: PR ID
        pr_node_id: PR node ID
        nested_nodes_status: Status of nested nodes (commits, reviews, comments, review_threads)

    Returns:
        bool: True if queued successfully
    """
    try:
        from app.etl.workers.queue_manager import QueueManager

        queue_manager = QueueManager()

        message = {
            'type': 'github_nested_extraction_recovery',
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'job_id': job_id,
            'pr_id': pr_id,
            'pr_node_id': pr_node_id,
            'nested_nodes_status': nested_nodes_status or {},
            'first_item': True,
            'last_item': False,
            'provider': 'github'
        }

        # Get tenant tier and route to tier-based extraction queue
        tier = queue_manager._get_tenant_tier(tenant_id)
        tier_queue = queue_manager.get_tier_queue_name(tier, 'extraction')

        success = queue_manager._publish_message(tier_queue, message)

        if success:
            logger.info(f"✅ Queued nested extraction for PR {pr_id} to {tier_queue}")
            return True
        else:
            logger.error(f"❌ Failed to queue nested extraction")
            return False

    except Exception as e:
        logger.error(f"Error queuing nested extraction: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False


async def _queue_github_repositories_extraction(
    tenant_id: int,
    integration_id: int,
    job_id: int,
    resume_from_pushed_date: Optional[str] = None
) -> bool:
    """
    Queue GitHub repositories extraction message with optional resume date.

    For rate limit recovery, uses the last extracted repo's pushed date as the new
    start_date for the search query. This allows overlapping some repos but ensures
    no repos are missed.

    Args:
        tenant_id: Tenant ID
        integration_id: Integration ID
        job_id: Job ID
        resume_from_pushed_date: Optional pushed date to resume from (YYYY-MM-DD format)

    Returns:
        bool: True if queued successfully
    """
    try:
        from app.etl.workers.queue_manager import QueueManager

        queue_manager = QueueManager()

        message = {
            'type': 'github_repositories',
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'job_id': job_id,
            'provider': 'github',
            'first_item': True,
            'last_item': False,
            'resume_from_pushed_date': resume_from_pushed_date  # 🔑 For recovery
        }

        # Get tenant tier and route to tier-based extraction queue
        tier = queue_manager._get_tenant_tier(tenant_id)
        tier_queue = queue_manager.get_tier_queue_name(tier, 'extraction')

        success = queue_manager._publish_message(tier_queue, message)

        if success:
            if resume_from_pushed_date:
                logger.info(f"✅ Queued repository extraction (resume from {resume_from_pushed_date}) to {tier_queue}")
            else:
                logger.info(f"✅ Queued repository extraction to {tier_queue}")
            return True
        else:
            logger.error(f"❌ Failed to queue repository extraction")
            return False

    except Exception as e:
        logger.error(f"Error queuing repository extraction: {e}")
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
        # Special cases:
        # - jira_dev_status: can be either all finished OR all idle (when no issues were extracted)
        # - GitHub steps (github_commits, github_reviews, github_pull_requests): can be idle if not executed in this job
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
                # For GitHub steps (except github_repositories): can be idle if not executed
                # 🔑 Updated to include github_prs_commits_reviews_comments (Phase 4 step)
                elif step_name in ['github_commits', 'github_reviews', 'github_pull_requests', 'github_prs_commits_reviews_comments']:
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

        # 🔑 Clear the token, reset_deadline, and reset_attempt when resetting to READY
        current_status['token'] = None
        current_status['reset_deadline'] = None
        current_status['reset_attempt'] = 0

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


@router.get("/jobs/{job_id}/check-remaining-messages")
async def check_remaining_messages(
    job_id: int,
    token: str = Query(..., description="Job execution token"),
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session),
    auth_result: dict = Depends(verify_hybrid_auth)
):
    """
    Check if there are remaining messages in the embedding queue for a specific job token.

    This endpoint is used by the frontend countdown timer to verify that all messages
    have been processed before resetting the job to READY state.

    Args:
        job_id: ETL job ID
        token: Job execution token (from status JSON)
        tenant_id: Tenant ID

    Returns:
        JSON with has_remaining_messages boolean
    """
    try:
        from app.etl.workers.queue_manager import QueueManager

        # Validate job exists and belongs to tenant
        query = text("""
            SELECT status
            FROM etl_jobs
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        result = db.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        # Validate token matches the job's current token
        status = result[0]
        if isinstance(status, str):
            status = json.loads(status)

        job_token = status.get('token')
        if job_token != token:
            logger.warning(f"Token mismatch for job {job_id}: provided {token}, expected {job_token}")
            raise HTTPException(status_code=400, detail="Invalid token for this job")

        # 🔑 Check embedding queue for messages with this token
        queue_manager = QueueManager()
        tier = queue_manager._get_tenant_tier(tenant_id)
        embedding_queue = queue_manager.get_tier_queue_name(tier, 'embedding')

        logger.info(f"🔍 Checking {embedding_queue} for messages with token {token}")

        has_remaining = queue_manager.check_messages_with_token(embedding_queue, token)

        logger.info(f"✅ Queue check complete for job {job_id}: has_remaining_messages={has_remaining}")

        return {
            "success": True,
            "job_id": job_id,
            "token": token,
            "has_remaining_messages": has_remaining,
            "message": "remaining messages found" if has_remaining else "no remaining messages"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking remaining messages for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check remaining messages: {str(e)}")

