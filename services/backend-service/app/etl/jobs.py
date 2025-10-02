"""
ETL Job Management APIs
Handles job status, control operations (pause/resume/force pending), and job details.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.database import get_db_session
from app.models.unified_models import Tenant

import logging

logger = logging.getLogger(__name__)

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
    last_run_finished_at: Optional[datetime],
    schedule_interval_minutes: int,
    retry_interval_minutes: int,
    status: str,
    retry_count: int
) -> Optional[datetime]:
    """
    Calculate when the job should run next.

    Logic:
    - If RUNNING: next_run is None (already running)
    - If FAILED with retries: use retry_interval_minutes from last_run_finished_at
    - If never run: use schedule_interval_minutes from now
    - Otherwise: use schedule_interval_minutes from last_run_finished_at
    """
    from datetime import timedelta
    import pytz
    import os

    # Get timezone from environment (default to America/New_York which is GMT-5)
    tz_name = os.getenv('SCHEDULER_TIMEZONE', 'America/New_York')
    tz = pytz.timezone(tz_name)

    # If running, no next run
    if status == 'RUNNING':
        return None

    # If never run, schedule from now + interval
    if not last_run_finished_at:
        now = datetime.now(tz)
        return now + timedelta(minutes=schedule_interval_minutes)

    # Ensure last_run_finished_at is timezone-aware
    if last_run_finished_at.tzinfo is None:
        last_run_finished_at = tz.localize(last_run_finished_at)

    # If failed with retries, use retry interval
    if status == 'FAILED' and retry_count > 0:
        return last_run_finished_at + timedelta(minutes=retry_interval_minutes)

    # Otherwise use normal schedule interval
    return last_run_finished_at + timedelta(minutes=schedule_interval_minutes)


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/jobs", response_model=List[JobCardResponse])
async def get_job_cards(
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session)
):
    """
    Get all job cards for the home page dashboard.
    Returns jobs ordered alphabetically by job_name.
    """
    try:
        from sqlalchemy import text

        query = text("""
            SELECT
                id, job_name, status, active,
                schedule_interval_minutes, retry_interval_minutes,
                integration_id, last_run_started_at, last_run_finished_at,
                error_message, retry_count
            FROM etl_jobs
            WHERE tenant_id = :tenant_id
            ORDER BY job_name ASC
        """)

        results = db.execute(query, {'tenant_id': tenant_id}).fetchall()

        job_cards = []
        for row in results:
            # Get integration info
            integration_type, logo_filename = get_integration_info(db, row[6])

            # Calculate next run
            next_run = calculate_next_run(
                last_run_finished_at=row[8],
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
    db: Session = Depends(get_db_session)
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
    db: Session = Depends(get_db_session)
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

        # If deactivating, check if integration is active
        if not request.active and integration_id:
            integration_query = text("""
                SELECT active FROM integrations WHERE id = :integration_id
            """)
            integration_result = db.execute(integration_query, {'integration_id': integration_id}).fetchone()

            if integration_result and integration_result[0]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot deactivate job {job_name} while its integration is active. Deactivate the integration first."
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


@router.post("/jobs/{job_id}/run-now", response_model=JobActionResponse)
async def run_job_now(
    job_id: int,
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session)
):
    """
    Manually trigger a job to run immediately.
    Sets status to RUNNING and triggers job execution.

    In Phase 1, this is a placeholder that just sets status.
    In Phase 2/3, this will actually trigger the job scheduler.
    """
    try:
        from sqlalchemy import text

        # Get current job
        query = text("""
            SELECT job_name, status, active
            FROM etl_jobs
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        result = db.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        job_name, current_status, active = result

        if not active:
            raise HTTPException(status_code=400, detail=f"Cannot run inactive job {job_name}")

        if current_status == 'RUNNING':
            raise HTTPException(status_code=400, detail=f"Job {job_name} is already running")

        # Set to RUNNING and record start time
        update_query = text("""
            UPDATE etl_jobs
            SET status = 'RUNNING',
                last_run_started_at = NOW(),
                last_updated_at = NOW()
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)
        db.execute(update_query, {'job_id': job_id, 'tenant_id': tenant_id})
        db.commit()

        logger.info(f"Job {job_name} (ID: {job_id}) manually triggered: {current_status} -> RUNNING")

        return JobActionResponse(
            success=True,
            message=f"Job {job_name} started successfully (Phase 1 placeholder - actual execution in Phase 2/3)",
            job_id=job_id,
            new_status="RUNNING"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error running job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to run job: {str(e)}")


@router.post("/jobs/{job_id}/settings", response_model=JobSettingsResponse)
async def update_job_settings(
    job_id: int,
    request: JobSettingsRequest,
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session)
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

