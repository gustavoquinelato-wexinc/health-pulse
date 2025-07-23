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
    JobSchedule, Project, Issuetype, Status, Issue, IssueChangelog, JiraPullRequestLinks
)
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
        progress_percentage=job.progress_percentage,
        current_step=job.current_step,
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


@router.get("/jobs/jira_sync/summary")
async def get_jira_summary(db: Session = Depends(get_db_session)):
    """
    Get summary statistics for Jira data tables.

    Returns:
        dict: Summary statistics for all Jira-related tables
    """
    try:
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "tables": {}
        }

        # Projects summary
        projects_count = db.query(func.count(Project.id)).scalar() or 0
        active_projects = db.query(func.count(Project.id)).filter(Project.active == True).scalar() or 0

        summary["tables"]["projects"] = {
            "total_count": projects_count,
            "active_count": active_projects,
            "inactive_count": projects_count - active_projects
        }

        # Issue types summary
        issuetypes_count = db.query(func.count(Issuetype.id)).scalar() or 0
        active_issuetypes = db.query(func.count(Issuetype.id)).filter(Issuetype.active == True).scalar() or 0

        summary["tables"]["issuetypes"] = {
            "total_count": issuetypes_count,
            "active_count": active_issuetypes,
            "inactive_count": issuetypes_count - active_issuetypes
        }

        # Statuses summary
        statuses_count = db.query(func.count(Status.id)).scalar() or 0
        active_statuses = db.query(func.count(Status.id)).filter(Status.active == True).scalar() or 0

        summary["tables"]["statuses"] = {
            "total_count": statuses_count,
            "active_count": active_statuses,
            "inactive_count": statuses_count - active_statuses
        }

        # Issues summary
        issues_count = db.query(func.count(Issue.id)).scalar() or 0
        active_issues = db.query(func.count(Issue.id)).filter(Issue.active == True).scalar() or 0

        # Issues by status (top 5)
        top_statuses = db.query(
            Status.original_name,
            func.count(Issue.id).label('count')
        ).join(Issue, Issue.status_id == Status.id)\
         .filter(Issue.active == True)\
         .group_by(Status.original_name)\
         .order_by(func.count(Issue.id).desc())\
         .limit(5).all()

        # Issues by type (top 5)
        top_types = db.query(
            Issuetype.original_name,
            func.count(Issue.id).label('count')
        ).join(Issue, Issue.issuetype_id == Issuetype.id)\
         .filter(Issue.active == True)\
         .group_by(Issuetype.original_name)\
         .order_by(func.count(Issue.id).desc())\
         .limit(5).all()

        summary["tables"]["issues"] = {
            "total_count": issues_count,
            "active_count": active_issues,
            "inactive_count": issues_count - active_issues,
            "top_statuses": [{"name": status.original_name, "count": status.count} for status in top_statuses],
            "top_types": [{"name": type_.original_name, "count": type_.count} for type_ in top_types]
        }

        # Changelogs summary
        changelogs_count = db.query(func.count(IssueChangelog.id)).scalar() or 0
        active_changelogs = db.query(func.count(IssueChangelog.id)).filter(IssueChangelog.active == True).scalar() or 0

        # Recent changelog activity (last 30 days)
        from datetime import timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_changelogs = db.query(func.count(IssueChangelog.id))\
            .filter(IssueChangelog.created_at >= thirty_days_ago)\
            .filter(IssueChangelog.active == True).scalar() or 0

        summary["tables"]["changelogs"] = {
            "total_count": changelogs_count,
            "active_count": active_changelogs,
            "inactive_count": changelogs_count - active_changelogs,
            "recent_activity_30d": recent_changelogs
        }

        # Jira PR Links summary
        pr_links_count = db.query(func.count(JiraPullRequestLinks.id)).scalar() or 0
        active_pr_links = db.query(func.count(JiraPullRequestLinks.id)).filter(JiraPullRequestLinks.active == True).scalar() or 0

        # Unique repositories linked
        unique_repos = db.query(func.count(distinct(JiraPullRequestLinks.repo_full_name)))\
            .filter(JiraPullRequestLinks.active == True).scalar() or 0

        # PR status breakdown
        pr_status_breakdown = db.query(
            JiraPullRequestLinks.pr_status,
            func.count(JiraPullRequestLinks.id).label('count')
        ).filter(JiraPullRequestLinks.active == True)\
         .group_by(JiraPullRequestLinks.pr_status)\
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
