"""
Job management endpoints for ETL service.
Handles job execution, status tracking, and control operations.
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, distinct
from app.core.database import get_db_session
from app.models.unified_models import (
    JobSchedule, Project, Wit, Status, WorkItem, Changelog, WitPrLinks
)
from app.schemas.api_schemas import (
    JobRunRequest, JobRunResponse, JobStatusResponse, JobStatus
)
# ✅ SECURITY: Add authentication for client isolation
from app.auth.centralized_auth_middleware import UserData, require_authentication

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
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
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
        # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
        jira_job = db.query(JobSchedule).filter(
            JobSchedule.job_name == 'jira_sync',
            JobSchedule.tenant_id == user.tenant_id
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
async def get_job_status(job_id: str, db: Session = Depends(get_db_session), user: UserData = Depends(require_authentication)):
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

    # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
    job = db.query(JobSchedule).filter(
        JobSchedule.id == job_id_int,
        JobSchedule.tenant_id == user.tenant_id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Map database status to API status
    status_mapping = {
        'PENDING': JobStatus.READY,
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
        progress_percentage=job.progress_percentage,
        current_step=job.current_step,
        errors=[job.error_message] if job.error_message else None
    )


@router.get("/etl/jobs", response_model=JobStatusResponse)
async def get_latest_job_status(db: Session = Depends(get_db_session), user: UserData = Depends(require_authentication)):
    """
    Get the status of the most recent job.

    Args:
        db: Database session

    Returns:
        JobStatusResponse: Latest job status
    """
    # Get the most recently started job
    # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
    latest_job = db.query(JobSchedule).filter(
        JobSchedule.tenant_id == user.tenant_id
    ).order_by(
        desc(JobSchedule.last_run_started_at)
    ).first()

    if not latest_job:
        raise HTTPException(status_code=404, detail="No jobs found")

    return await get_job_status(str(latest_job.id), db)


@router.post("/etl/jobs/{job_id}/stop")
async def stop_job(job_id: str, db: Session = Depends(get_db_session), user: UserData = Depends(require_authentication)):
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

    # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
    job = db.query(JobSchedule).filter(
        JobSchedule.id == job_id_int,
        JobSchedule.tenant_id == user.tenant_id
    ).first()
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
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
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
        # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
        github_job = db.query(JobSchedule).filter(
            JobSchedule.job_name == 'github_sync',
            JobSchedule.tenant_id == user.tenant_id
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
async def list_all_jobs(db: Session = Depends(get_db_session), user: UserData = Depends(require_authentication)):
    """
    List all available jobs with their current status.

    Args:
        db: Database session

    Returns:
        dict: List of all jobs with their status
    """
    # ✅ SECURITY: Filter by tenant_id to prevent cross-client data access
    jobs = db.query(JobSchedule).filter(
        JobSchedule.active == True,
        JobSchedule.tenant_id == user.tenant_id
    ).all()

    job_list = []
    for job in jobs:
        # Map database status to API status
        status_mapping = {
            'PENDING': JobStatus.READY,
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


@router.get("/jobs/jira_sync/summary")
async def get_jira_summary(
    db: Session = Depends(get_db_session),
    user: UserData = Depends(require_authentication)
):
    """
    Get summary statistics for Jira data tables for current user's client.

    Returns:
        dict: Summary statistics for all Jira-related tables
    """
    try:
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "tables": {}
        }

        # ✅ SECURITY: Projects summary filtered by tenant_id
        projects_count = db.query(func.count(Project.id)).filter(Project.tenant_id == user.tenant_id).scalar() or 0
        active_projects = db.query(func.count(Project.id)).filter(
            Project.tenant_id == user.tenant_id,
            Project.active == True
        ).scalar() or 0

        summary["tables"]["projects"] = {
            "total_count": projects_count,
            "active_count": active_projects,
            "inactive_count": projects_count - active_projects
        }

        # ✅ SECURITY: WorkItem types summary filtered by tenant_id
        issuetypes_count = db.query(func.count(Wit.id)).filter(Wit.tenant_id == user.tenant_id).scalar() or 0
        active_issuetypes = db.query(func.count(Wit.id)).filter(
            Wit.tenant_id == user.tenant_id,
            Wit.active == True
        ).scalar() or 0

        summary["tables"]["issuetypes"] = {
            "total_count": issuetypes_count,
            "active_count": active_issuetypes,
            "inactive_count": issuetypes_count - active_issuetypes
        }

        # ✅ SECURITY: Statuses summary filtered by tenant_id
        statuses_count = db.query(func.count(Status.id)).filter(Status.tenant_id == user.tenant_id).scalar() or 0
        active_statuses = db.query(func.count(Status.id)).filter(
            Status.tenant_id == user.tenant_id,
            Status.active == True
        ).scalar() or 0

        summary["tables"]["statuses"] = {
            "total_count": statuses_count,
            "active_count": active_statuses,
            "inactive_count": statuses_count - active_statuses
        }

        # ✅ SECURITY: WorkItems summary filtered by tenant_id
        issues_count = db.query(func.count(WorkItem.id)).filter(WorkItem.tenant_id == user.tenant_id).scalar() or 0
        active_issues = db.query(func.count(WorkItem.id)).filter(
            WorkItem.tenant_id == user.tenant_id,
            WorkItem.active == True
        ).scalar() or 0

        # ✅ SECURITY: WorkItems by status (top 5) filtered by tenant_id
        top_statuses = db.query(
            Status.original_name,
            func.count(WorkItem.id).label('count')
        ).join(WorkItem, WorkItem.status_id == Status.id)\
         .filter(
             WorkItem.tenant_id == user.tenant_id,
             WorkItem.active == True
         )\
         .group_by(Status.original_name)\
         .order_by(func.count(WorkItem.id).desc())\
         .limit(5).all()

        # ✅ SECURITY: WorkItems by type (top 5) filtered by tenant_id
        top_types = db.query(
            Wit.original_name,
            func.count(WorkItem.id).label('count')
        ).join(WorkItem, WorkItem.wit_id == Wit.id)\
         .filter(
             WorkItem.tenant_id == user.tenant_id,
             WorkItem.active == True
         )\
         .group_by(Wit.original_name)\
         .order_by(func.count(WorkItem.id).desc())\
         .limit(5).all()

        summary["tables"]["issues"] = {
            "total_count": issues_count,
            "active_count": active_issues,
            "inactive_count": issues_count - active_issues,
            "top_statuses": [{"name": status.original_name, "count": status.count} for status in top_statuses],
            "top_types": [{"name": type_.original_name, "count": type_.count} for type_ in top_types]
        }

        # ✅ SECURITY: Changelogs summary filtered by tenant_id
        changelogs_count = db.query(func.count(Changelog.id)).filter(Changelog.tenant_id == user.tenant_id).scalar() or 0
        active_changelogs = db.query(func.count(Changelog.id)).filter(
            Changelog.tenant_id == user.tenant_id,
            Changelog.active == True
        ).scalar() or 0

        # ✅ SECURITY: Recent changelog activity (last 30 days) filtered by tenant_id
        from datetime import timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_changelogs = db.query(func.count(Changelog.id))\
            .filter(
                Changelog.tenant_id == user.tenant_id,
                Changelog.created_at >= thirty_days_ago,
                Changelog.active == True
            ).scalar() or 0

        summary["tables"]["changelogs"] = {
            "total_count": changelogs_count,
            "active_count": active_changelogs,
            "inactive_count": changelogs_count - active_changelogs,
            "recent_activity_30d": recent_changelogs
        }

        # ✅ SECURITY: Jira PR Links summary filtered by tenant_id
        pr_links_count = db.query(func.count(WitPrLinks.id)).filter(
            WitPrLinks.tenant_id == user.tenant_id
        ).scalar() or 0
        active_pr_links = db.query(func.count(WitPrLinks.id)).filter(
            WitPrLinks.active == True,
            WitPrLinks.tenant_id == user.tenant_id
        ).scalar() or 0

        # Unique repositories linked
        unique_repos = db.query(func.count(distinct(WitPrLinks.repo_full_name)))\
            .filter(
                WitPrLinks.active == True,
                WitPrLinks.tenant_id == user.tenant_id
            ).scalar() or 0

        # PR status breakdown
        pr_status_breakdown = db.query(
            WitPrLinks.pr_status,
            func.count(WitPrLinks.id).label('count')
        ).filter(
            WitPrLinks.active == True,
            WitPrLinks.tenant_id == user.tenant_id
        ).group_by(WitPrLinks.pr_status)\
         .all()

        summary["tables"]["jira_pull_request_links"] = {
            "total_count": pr_links_count,
            "active_count": active_pr_links,
            "inactive_count": pr_links_count - active_pr_links,
            "unique_repositories": unique_repos,
            "pr_status_breakdown": [{"status": link.pr_status or "Unknown", "count": link.count} for link in pr_status_breakdown]
        }

        return summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Jira summary: {str(e)}")
