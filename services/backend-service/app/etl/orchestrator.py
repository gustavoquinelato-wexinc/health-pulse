"""
ETL Orchestrator Control APIs
Handles orchestrator status and control operations (start/pause/resume/toggle).

Note: This is a placeholder for Phase 2/3 implementation.
The actual orchestrator logic will be implemented when we refactor the ETL service.
For now, these APIs manage orchestrator settings in the database.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.database import get_db_session
from app.models.unified_models import Tenant

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Pydantic Schemas
# ============================================================================

class OrchestratorStatusResponse(BaseModel):
    """Orchestrator status information."""
    enabled: bool
    interval_minutes: int
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    status: str  # 'running', 'paused', 'stopped'


class OrchestratorToggleRequest(BaseModel):
    """Request to toggle orchestrator enabled status."""
    enabled: bool


class OrchestratorActionResponse(BaseModel):
    """Response for orchestrator actions."""
    success: bool
    message: str
    enabled: bool


class OrchestratorSettingsResponse(BaseModel):
    """Orchestrator settings information."""
    interval_minutes: int
    retry_enabled: bool
    retry_interval_minutes: int
    max_retry_attempts: int


class OrchestratorSettingsUpdateRequest(BaseModel):
    """Request to update orchestrator settings."""
    interval_minutes: int = Field(..., ge=5, le=1440, description="Interval in minutes (5-1440)")
    retry_enabled: bool = Field(..., description="Enable fast retry for failed jobs")
    retry_interval_minutes: int = Field(..., ge=5, le=60, description="Retry interval in minutes (5-60)")
    max_retry_attempts: int = Field(..., ge=0, le=10, description="Max retry attempts (0=unlimited)")


# ============================================================================
# Helper Functions
# ============================================================================

def get_orchestrator_setting(db: Session, tenant_id: int, setting_key: str, default_value: str | None) -> str | None:
    """Get orchestrator setting from system_settings table."""
    from sqlalchemy import text
    
    query = text("""
        SELECT setting_value
        FROM system_settings
        WHERE tenant_id = :tenant_id AND setting_key = :setting_key AND active = TRUE
    """)
    result = db.execute(query, {'tenant_id': tenant_id, 'setting_key': setting_key}).fetchone()
    
    if result:
        return result[0]
    return default_value


def set_orchestrator_setting(db: Session, tenant_id: int, setting_key: str, setting_value: str, description: str | None = None):
    """Set orchestrator setting in system_settings table."""
    from sqlalchemy import text
    
    # Check if setting exists
    check_query = text("""
        SELECT id FROM system_settings
        WHERE tenant_id = :tenant_id AND setting_key = :setting_key
    """)
    result = db.execute(check_query, {'tenant_id': tenant_id, 'setting_key': setting_key}).fetchone()
    
    if result:
        # Update existing
        update_query = text("""
            UPDATE system_settings
            SET setting_value = :setting_value, last_updated_at = NOW()
            WHERE tenant_id = :tenant_id AND setting_key = :setting_key
        """)
        db.execute(update_query, {
            'tenant_id': tenant_id,
            'setting_key': setting_key,
            'setting_value': setting_value
        })
    else:
        # Insert new
        insert_query = text("""
            INSERT INTO system_settings (tenant_id, setting_key, setting_value, setting_type, description, active, created_at, last_updated_at)
            VALUES (:tenant_id, :setting_key, :setting_value, 'string', :description, TRUE, NOW(), NOW())
        """)
        db.execute(insert_query, {
            'tenant_id': tenant_id,
            'setting_key': setting_key,
            'setting_value': setting_value,
            'description': description or f'Orchestrator setting: {setting_key}'
        })


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/orchestrator/status", response_model=OrchestratorStatusResponse)
async def get_orchestrator_status(
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session)
):
    """
    Get orchestrator status and configuration.
    
    Returns:
    - enabled: Whether orchestrator is enabled
    - interval_minutes: How often orchestrator runs
    - status: Current status (running/paused/stopped)
    """
    try:
        # Get settings from database
        enabled_str = get_orchestrator_setting(db, tenant_id, 'orchestrator_enabled', 'true') or 'true'
        interval_str = get_orchestrator_setting(db, tenant_id, 'orchestrator_interval', '60') or '60'

        enabled = enabled_str.lower() == 'true'
        interval_minutes = int(interval_str)
        
        # Get last run and next run times
        last_run_str = get_orchestrator_setting(db, tenant_id, 'orchestrator_last_run', None)
        next_run_str = get_orchestrator_setting(db, tenant_id, 'orchestrator_next_run', None)

        # Parse ISO format timestamps
        last_run = None
        next_run = None
        if last_run_str:
            try:
                from datetime import datetime
                last_run = datetime.fromisoformat(last_run_str).isoformat()
            except:
                pass

        if next_run_str:
            try:
                from datetime import datetime
                next_run = datetime.fromisoformat(next_run_str).isoformat()
            except:
                pass

        # Determine status
        if not enabled:
            status = 'stopped'
        else:
            # Check if any jobs are running
            from sqlalchemy import text
            running_query = text("""
                SELECT COUNT(*) FROM etl_jobs
                WHERE tenant_id = :tenant_id AND status = 'RUNNING'
            """)
            running_count = db.execute(running_query, {'tenant_id': tenant_id}).scalar()

            if running_count and running_count > 0:
                status = 'running'
            else:
                status = 'paused'

        return OrchestratorStatusResponse(
            enabled=enabled,
            interval_minutes=interval_minutes,
            last_run=last_run,  # type: ignore
            next_run=next_run,  # type: ignore
            status=status
        )
        
    except Exception as e:
        logger.error(f"Error fetching orchestrator status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch orchestrator status: {str(e)}")


@router.post("/orchestrator/toggle", response_model=OrchestratorActionResponse)
async def toggle_orchestrator(
    request: OrchestratorToggleRequest,
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session)
):
    """
    Toggle orchestrator enabled/disabled.
    
    When disabled, orchestrator will not run and no jobs will be triggered automatically.
    """
    try:
        # Update setting
        set_orchestrator_setting(
            db,
            tenant_id,
            'orchestrator_enabled',
            'true' if request.enabled else 'false',
            'Enable/disable orchestrator automatic job execution'
        )
        db.commit()
        
        action = "enabled" if request.enabled else "disabled"
        logger.info(f"Orchestrator {action} for tenant {tenant_id}")
        
        return OrchestratorActionResponse(
            success=True,
            message=f"Orchestrator {action} successfully",
            enabled=request.enabled
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error toggling orchestrator: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle orchestrator: {str(e)}")


@router.post("/orchestrator/start", response_model=OrchestratorActionResponse)
async def start_orchestrator(
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session)
):
    """
    Manually trigger orchestrator to check for PENDING jobs.

    This will:
    1. Find the first PENDING or READY job (by execution_order)
    2. Set it to RUNNING
    3. Trigger mock job execution (Phase 1 - simulates progress)
    """
    try:
        from sqlalchemy import text
        import asyncio

        # Check if orchestrator is enabled
        enabled_str = get_orchestrator_setting(db, tenant_id, 'orchestrator_enabled', 'true') or 'true'
        enabled = enabled_str.lower() == 'true'

        if not enabled:
            raise HTTPException(
                status_code=400,
                detail="Orchestrator is disabled. Enable it first before starting."
            )

        # Find first PENDING or READY job (by execution_order)
        query = text("""
            SELECT id, job_name, status
            FROM etl_jobs
            WHERE tenant_id = :tenant_id
              AND active = TRUE
              AND status IN ('PENDING', 'READY')
            ORDER BY execution_order ASC
            LIMIT 1
        """)

        result = db.execute(query, {'tenant_id': tenant_id}).fetchone()

        if not result:
            logger.info(f"No PENDING or READY jobs found for tenant {tenant_id}")
            return OrchestratorActionResponse(
                success=True,
                message="No jobs ready to run. All jobs are either RUNNING, PAUSED, or FINISHED.",
                enabled=True
            )

        job_id, job_name, current_status = result

        # Set job to RUNNING
        update_query = text("""
            UPDATE etl_jobs
            SET status = 'RUNNING',
                last_run_started_at = NOW(),
                error_message = NULL,
                progress_percentage = 0,
                current_step = 'Starting...',
                last_updated_at = NOW()
            WHERE id = :job_id AND tenant_id = :tenant_id
        """)

        db.execute(update_query, {'job_id': job_id, 'tenant_id': tenant_id})

        # Update orchestrator last_run time
        from datetime import datetime
        set_orchestrator_setting(
            db, tenant_id,
            'orchestrator_last_run',
            datetime.utcnow().isoformat(),
            'Last orchestrator run time'
        )

        db.commit()

        logger.info(f"Manual orchestrator trigger: Set job '{job_name}' (ID: {job_id}) to RUNNING (was {current_status})")

        # Trigger mock job execution in background (Phase 1 - simulates progress)
        asyncio.create_task(execute_mock_job(job_id, job_name, tenant_id))

        return OrchestratorActionResponse(
            success=True,
            message=f"Job '{job_name}' started successfully",
            enabled=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting orchestrator: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start orchestrator: {str(e)}")


@router.post("/orchestrator/pause", response_model=OrchestratorActionResponse)
async def pause_orchestrator(
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session)
):
    """
    Pause orchestrator (same as disabling).
    
    This will prevent orchestrator from running automatically.
    """
    try:
        # Set enabled to false
        set_orchestrator_setting(
            db,
            tenant_id,
            'orchestrator_enabled',
            'false',
            'Enable/disable orchestrator automatic job execution'
        )
        db.commit()
        
        logger.info(f"Orchestrator paused for tenant {tenant_id}")
        
        return OrchestratorActionResponse(
            success=True,
            message="Orchestrator paused successfully",
            enabled=False
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error pausing orchestrator: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to pause orchestrator: {str(e)}")


@router.post("/orchestrator/resume", response_model=OrchestratorActionResponse)
async def resume_orchestrator(
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session)
):
    """
    Resume orchestrator (same as enabling).
    
    This will allow orchestrator to run automatically on its schedule.
    """
    try:
        # Set enabled to true
        set_orchestrator_setting(
            db,
            tenant_id,
            'orchestrator_enabled',
            'true',
            'Enable/disable orchestrator automatic job execution'
        )
        db.commit()
        
        logger.info(f"Orchestrator resumed for tenant {tenant_id}")
        
        return OrchestratorActionResponse(
            success=True,
            message="Orchestrator resumed successfully",
            enabled=True
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error resuming orchestrator: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resume orchestrator: {str(e)}")


@router.get("/orchestrator/settings", response_model=OrchestratorSettingsResponse)
async def get_orchestrator_settings(
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session)
):
    """
    Get orchestrator configuration settings.

    Returns all orchestrator settings including interval, retry configuration, etc.
    """
    try:
        # Get settings from database with defaults
        interval_str = get_orchestrator_setting(db, tenant_id, 'orchestrator_interval', '60') or '60'
        retry_enabled_str = get_orchestrator_setting(db, tenant_id, 'orchestrator_retry_enabled', 'true') or 'true'
        retry_interval_str = get_orchestrator_setting(db, tenant_id, 'orchestrator_retry_interval', '15') or '15'
        max_retry_str = get_orchestrator_setting(db, tenant_id, 'orchestrator_max_retry_attempts', '3') or '3'

        return OrchestratorSettingsResponse(
            interval_minutes=int(interval_str),
            retry_enabled=retry_enabled_str.lower() == 'true',
            retry_interval_minutes=int(retry_interval_str),
            max_retry_attempts=int(max_retry_str)
        )

    except Exception as e:
        logger.error(f"Error getting orchestrator settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get orchestrator settings: {str(e)}")


@router.post("/orchestrator/settings", response_model=OrchestratorActionResponse)
async def update_orchestrator_settings(
    request: OrchestratorSettingsUpdateRequest,
    tenant_id: int = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db_session)
):
    """
    Update orchestrator configuration settings.

    Updates interval, retry settings, and other orchestrator configuration.
    """
    try:
        # Update all settings
        set_orchestrator_setting(
            db, tenant_id,
            'orchestrator_interval',
            str(request.interval_minutes),
            'Orchestrator run interval in minutes'
        )

        set_orchestrator_setting(
            db, tenant_id,
            'orchestrator_retry_enabled',
            'true' if request.retry_enabled else 'false',
            'Enable fast retry for failed jobs'
        )

        set_orchestrator_setting(
            db, tenant_id,
            'orchestrator_retry_interval',
            str(request.retry_interval_minutes),
            'Fast retry interval in minutes'
        )

        set_orchestrator_setting(
            db, tenant_id,
            'orchestrator_max_retry_attempts',
            str(request.max_retry_attempts),
            'Maximum retry attempts before falling back to normal interval'
        )

        db.commit()

        logger.info(f"Orchestrator settings updated for tenant {tenant_id}: interval={request.interval_minutes}m, retry={request.retry_enabled}")

        return OrchestratorActionResponse(
            success=True,
            message="Orchestrator settings updated successfully",
            enabled=True  # Settings update doesn't affect enabled status
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating orchestrator settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update orchestrator settings: {str(e)}")


# ============================================================================
# Mock Job Execution (Phase 1 - Testing Only)
# ============================================================================

async def execute_mock_job(job_id: int, job_name: str, tenant_id: int):
    """
    Mock job execution that simulates progress from 0-100% and auto-finishes.

    This is Phase 1 testing logic - will be replaced with real extraction in Phase 2/3.

    Flow:
    1. Simulate progress from 0-100% over ~10 seconds
    2. Mark job as FINISHED
    3. Set next job to PENDING
    4. Schedule fast retry (15 min) for job-to-job transitions
    5. Schedule normal interval (60 min) when cycling back to first job
    """
    import asyncio
    from sqlalchemy import text
    from app.core.database import get_db_session

    logger.info(f"[MOCK] Starting mock execution for job '{job_name}' (ID: {job_id})")

    try:
        # Simulate progress from 0-100% over ~10 seconds
        steps = [
            (10, "Initializing..."),
            (25, "Extracting data..."),
            (50, "Processing records..."),
            (75, "Transforming data..."),
            (90, "Finalizing..."),
            (100, "Completing...")
        ]

        for progress, step_message in steps:
            # Update progress in database
            db = next(get_db_session())
            try:
                update_query = text("""
                    UPDATE etl_jobs
                    SET progress_percentage = :progress,
                        current_step = :step,
                        last_updated_at = NOW()
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)
                db.execute(update_query, {
                    'job_id': job_id,
                    'tenant_id': tenant_id,
                    'progress': progress,
                    'step': step_message
                })
                db.commit()
                logger.info(f"[MOCK] {job_name}: {progress}% - {step_message}")
            finally:
                db.close()

            # Wait before next update (total ~10 seconds)
            await asyncio.sleep(1.5)

        # Mark job as FINISHED and set next job to PENDING
        db = next(get_db_session())
        try:
            # Get current job info
            query = text("""
                SELECT execution_order
                FROM etl_jobs
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            result = db.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()

            if not result:
                logger.error(f"[MOCK] Job {job_id} not found")
                return

            execution_order = result[0]

            # Mark current job as FINISHED
            finish_query = text("""
                UPDATE etl_jobs
                SET status = 'FINISHED',
                    last_success_at = NOW(),
                    last_updated_at = NOW(),
                    error_message = NULL,
                    progress_percentage = 100,
                    current_step = 'Completed'
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(finish_query, {'job_id': job_id, 'tenant_id': tenant_id})

            logger.info(f"[MOCK] Job {job_name} (ID: {job_id}) marked as FINISHED")

            # Find next ready job (skips paused jobs)
            next_job_query = text("""
                SELECT id, job_name, execution_order
                FROM etl_jobs
                WHERE tenant_id = :tenant_id
                AND execution_order > :current_order
                AND active = TRUE
                ORDER BY execution_order ASC
                LIMIT 1
            """)
            next_job = db.execute(next_job_query, {
                'tenant_id': tenant_id,
                'current_order': execution_order
            }).fetchone()

            if next_job:
                next_job_id, next_job_name, next_job_order = next_job

                # Set next job to PENDING
                next_update_query = text("""
                    UPDATE etl_jobs
                    SET status = 'PENDING',
                        last_updated_at = NOW(),
                        progress_percentage = NULL,
                        current_step = NULL
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)
                db.execute(next_update_query, {'job_id': next_job_id, 'tenant_id': tenant_id})

                logger.info(f"[MOCK] Set next ready job to PENDING: {next_job_name} (order: {next_job_order})")

                # Check if this is cycling back to the first job (restart)
                first_job_query = text("""
                    SELECT id, job_name, execution_order
                    FROM etl_jobs
                    WHERE tenant_id = :tenant_id
                      AND active = TRUE
                      AND status != 'PAUSED'
                    ORDER BY execution_order ASC
                    LIMIT 1
                """)
                first_job_result = db.execute(first_job_query, {'tenant_id': tenant_id}).fetchone()

                is_cycle_restart = (first_job_result and next_job_id == first_job_result[0])

                if is_cycle_restart:
                    # Cycle restart - use normal interval (60 min)
                    interval_str = get_orchestrator_setting(db, tenant_id, 'orchestrator_interval', '60') or '60'
                    interval_minutes = int(interval_str)
                    logger.info(f"[MOCK] Next job is cycle restart ({next_job_name}) - using normal interval ({interval_minutes} min)")
                else:
                    # Job-to-job transition - use fast retry interval (15 min)
                    retry_str = get_orchestrator_setting(db, tenant_id, 'orchestrator_retry_interval', '15') or '15'
                    interval_minutes = int(retry_str)
                    logger.info(f"[MOCK] Next job is in sequence ({next_job_name}) - using fast retry ({interval_minutes} min)")

                # Update orchestrator next_run time
                from datetime import datetime, timedelta
                next_run_time = datetime.utcnow() + timedelta(minutes=interval_minutes)
                set_orchestrator_setting(
                    db, tenant_id,
                    'orchestrator_next_run',
                    next_run_time.isoformat(),
                    'Next scheduled orchestrator run time'
                )
                set_orchestrator_setting(
                    db, tenant_id,
                    'orchestrator_last_run',
                    datetime.utcnow().isoformat(),
                    'Last orchestrator run time'
                )
                logger.info(f"[MOCK] Orchestrator next run scheduled for: {next_run_time.isoformat()} ({interval_minutes} min from now)")
            else:
                logger.info("[MOCK] No next ready job found - all jobs completed or paused")

            db.commit()

        finally:
            db.close()

        logger.info(f"[MOCK] Mock execution completed for job '{job_name}'")

    except Exception as e:
        logger.error(f"[MOCK] Error in mock job execution for {job_name}: {e}")
        import traceback
        logger.error(traceback.format_exc())

        # Mark job as FINISHED with error
        db = next(get_db_session())
        try:
            error_query = text("""
                UPDATE etl_jobs
                SET status = 'FINISHED',
                    error_message = :error,
                    last_updated_at = NOW()
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(error_query, {
                'job_id': job_id,
                'tenant_id': tenant_id,
                'error': f"Mock execution error: {str(e)}"
            })
            db.commit()
        finally:
            db.close()

