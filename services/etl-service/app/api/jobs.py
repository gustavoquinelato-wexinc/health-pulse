"""
Job management endpoints for ETL service.
Handles job execution, status tracking, and control operations.
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.core.database import get_db_session
from app.models.unified_models import JobSchedule
from app.schemas.api_schemas import (
    JobRunRequest, JobRunResponse, JobStatusResponse, JobStatus
)

router = APIRouter()


@router.post(
    "/etl/jira/extract",
    response_model=JobRunResponse,
    summary="Start Jira Data Extraction",
    description="Trigger a Jira data extraction job"
)
async def run_jira_job(
    request: JobRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session)
):
    """
    Start a Jira data extraction job.

    Args:
        request: Job configuration parameters
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        JobRunResponse: Job execution details including job ID
    """
    try:
        # Get or create Jira job schedule
        jira_job = db.query(JobSchedule).filter(
            JobSchedule.job_name == 'jira_sync'
        ).first()

        if not jira_job:
            # Create new job schedule
            jira_job = JobSchedule(
                job_name='jira_sync',
                status='PENDING',
                active=True
            )
            db.add(jira_job)
            db.commit()
            db.refresh(jira_job)

        # Check if job is already running
        if jira_job.status == 'RUNNING':
            raise HTTPException(status_code=400, detail="Jira job is already running")

        # Update job status to running
        jira_job.set_running()
        db.commit()

        # Add background task for actual job execution
        # background_tasks.add_task(execute_jira_extraction, jira_job.id, request, db)

        return JobRunResponse(
            job_id=str(jira_job.id),
            status=JobStatus.RUNNING,
            message="Jira extraction job started successfully",
            started_at=jira_job.last_run_started_at
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start job: {str(e)}")


@router.get("/etl/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, db: Session = Depends(get_db_session)):
    """
    Get the status of a specific job.

    Args:
        job_id: Unique job identifier
        db: Database session

    Returns:
        JobStatusResponse: Current job status and details
    """
    try:
        job_id_int = int(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(JobSchedule).filter(JobSchedule.id == job_id_int).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Map database status to API status
    status_mapping = {
        'PENDING': JobStatus.NOT_STARTED,
        'RUNNING': JobStatus.RUNNING,
        'FINISHED': JobStatus.SUCCESS,
        'PAUSED': JobStatus.CANCELLED
    }

    api_status = status_mapping.get(job.status, JobStatus.ERROR)

    return JobStatusResponse(
        job_id=job_id,
        status=api_status,
        started_at=job.last_run_started_at,
        completed_at=job.last_success_at,
        current_step=job.job_name,
        errors=[job.error_message] if job.error_message else None
    )


@router.get("/etl/jobs", response_model=JobStatusResponse)
async def get_latest_job_status(db: Session = Depends(get_db_session)):
    """
    Get the status of the most recent job.

    Args:
        db: Database session

    Returns:
        JobStatusResponse: Latest job status
    """
    # Get the most recently started job
    latest_job = db.query(JobSchedule).order_by(
        desc(JobSchedule.last_run_started_at)
    ).first()

    if not latest_job:
        raise HTTPException(status_code=404, detail="No jobs found")

    return await get_job_status(str(latest_job.id), db)


@router.post("/etl/jobs/{job_id}/stop")
async def stop_job(job_id: str, db: Session = Depends(get_db_session)):
    """
    Stop a running job.

    Args:
        job_id: Unique job identifier
        db: Database session

    Returns:
        dict: Stop operation result
    """
    try:
        job_id_int = int(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(JobSchedule).filter(JobSchedule.id == job_id_int).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != 'RUNNING':
        raise HTTPException(status_code=400, detail="Job is not running")

    # Update job status to paused (stopped)
    job.set_paused()
    job.error_message = 'Job stopped by user request'
    db.commit()

    return {
        "message": f"Job {job_id} stopped successfully",
        "job_id": job_id,
        "status": "PAUSED"
    }


@router.post(
    "/etl/github/extract",
    response_model=JobRunResponse,
    summary="Start GitHub Data Extraction",
    description="Trigger a GitHub data extraction job"
)
async def run_github_job(
    request: JobRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session)
):
    """
    Start a GitHub data extraction job.

    Args:
        request: Job configuration parameters
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        JobRunResponse: Job execution details including job ID
    """
    try:
        # Get or create GitHub job schedule
        github_job = db.query(JobSchedule).filter(
            JobSchedule.job_name == 'github_sync'
        ).first()

        if not github_job:
            # Create new job schedule
            github_job = JobSchedule(
                job_name='github_sync',
                status='PENDING',
                active=True
            )
            db.add(github_job)
            db.commit()
            db.refresh(github_job)

        # Check if job is already running
        if github_job.status == 'RUNNING':
            raise HTTPException(status_code=400, detail="GitHub job is already running")

        # Update job status to running
        github_job.set_running()
        db.commit()

        # Add background task for actual job execution
        # background_tasks.add_task(execute_github_extraction, github_job.id, request, db)

        return JobRunResponse(
            job_id=str(github_job.id),
            status=JobStatus.RUNNING,
            message="GitHub extraction job started successfully",
            started_at=github_job.last_run_started_at
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start GitHub job: {str(e)}")


@router.get("/etl/jobs/list")
async def list_all_jobs(db: Session = Depends(get_db_session)):
    """
    List all available jobs with their current status.

    Args:
        db: Database session

    Returns:
        dict: List of all jobs with their status
    """
    jobs = db.query(JobSchedule).filter(JobSchedule.active == True).all()

    job_list = []
    for job in jobs:
        # Map database status to API status
        status_mapping = {
            'PENDING': JobStatus.NOT_STARTED,
            'RUNNING': JobStatus.RUNNING,
            'FINISHED': JobStatus.SUCCESS,
            'PAUSED': JobStatus.CANCELLED
        }

        api_status = status_mapping.get(job.status, JobStatus.ERROR)

        job_list.append({
            "job_id": str(job.id),
            "job_name": job.job_name,
            "status": api_status,
            "last_run": job.last_run_started_at,
            "last_success": job.last_success_at,
            "error_message": job.error_message,
            "retry_count": job.retry_count
        })

    return {
        "jobs": job_list,
        "total_jobs": len(job_list)
    }
