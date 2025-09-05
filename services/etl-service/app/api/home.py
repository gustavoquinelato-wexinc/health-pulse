"""
Home API Routes

Provides home page endpoints for the ETL service.
All endpoints require admin authentication since only admins access ETL.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.core.database import get_database
from app.models.unified_models import (
    Integration, Project, Issue, IssueChangelog, Repository,
    PullRequest, JobSchedule, SystemSettings
)
from app.auth.centralized_auth_middleware import UserData, require_admin_authentication
from app.core.logging_config import get_logger
from app.jobs.orchestrator import get_job_status

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/home", tags=["home"])


# Pydantic models for home page responses
class HomeStatsResponse(BaseModel):
    total_records: int
    active_jobs: int
    integrations: int
    last_sync: Optional[str] = None


class CurrentJobResponse(BaseModel):
    name: str
    status: str
    progress: Optional[float] = None
    started_at: Optional[str] = None
    estimated_completion: Optional[str] = None


class RecentActivityResponse(BaseModel):
    message: str
    timestamp: str
    icon: str
    type: str  # 'info', 'success', 'warning', 'error'


class IntegrationStatusResponse(BaseModel):
    id: int
    name: str
    type: str
    active: bool
    last_sync: Optional[str] = None
    status: str  # 'connected', 'error', 'inactive'


class JobCardResponse(BaseModel):
    id: int
    job_name: str
    execution_order: int
    integration_type: Optional[str] = None
    active: bool
    last_sync: Optional[str] = None
    status: str  # 'pending', 'running', 'connected', 'error', 'inactive'
    last_run_started_at: Optional[str] = None
    last_success_at: Optional[str] = None
    retry_count: Optional[int] = None


@router.get("/stats", response_model=HomeStatsResponse)
async def get_home_stats(
    user: UserData = Depends(require_admin_authentication)
):
    """Get home page statistics"""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # Count total records across main tables
            total_records = 0
            
            # Count issues (main data)
            issues_count = session.query(func.count(Issue.id)).filter(
                Issue.client_id == user.client_id
            ).scalar() or 0
            total_records += issues_count
            
            # Count pull requests
            pr_count = session.query(func.count(PullRequest.id)).filter(
                PullRequest.client_id == user.client_id
            ).scalar() or 0
            total_records += pr_count
            
            # Count projects
            projects_count = session.query(func.count(Project.id)).filter(
                Project.client_id == user.client_id
            ).scalar() or 0
            total_records += projects_count
            
            # Get active integrations count
            integrations_count = session.query(func.count(Integration.id)).filter(
                and_(
                    Integration.client_id == user.client_id,
                    Integration.active == True
                )
            ).scalar() or 0
            
            # Get last sync time from most recent issue or PR
            last_sync = None
            try:
                # Check last issue update
                last_issue = session.query(Issue.updated).filter(
                    Issue.client_id == user.client_id
                ).order_by(desc(Issue.updated)).first()

                # Check last PR update
                last_pr = session.query(PullRequest.updated_at).filter(
                    PullRequest.client_id == user.client_id
                ).order_by(desc(PullRequest.updated_at)).first()

                # Get the most recent
                if last_issue and last_pr:
                    last_sync = max(last_issue[0], last_pr[0]).isoformat()
                elif last_issue:
                    last_sync = last_issue[0].isoformat()
                elif last_pr:
                    last_sync = last_pr[0].isoformat()
                    
            except Exception as e:
                logger.warning(f"Could not get last sync time: {e}")
            
            # Get active jobs count
            active_jobs = 0
            try:
                job_status = get_job_status(client_id=user.client_id)
                active_jobs = sum(1 for job_data in job_status.values() 
                                if job_data.get('status') == 'RUNNING')
            except Exception as e:
                logger.warning(f"Could not get job status: {e}")
            
            return HomeStatsResponse(
                total_records=total_records,
                active_jobs=active_jobs,
                integrations=integrations_count,
                last_sync=last_sync
            )
            
    except Exception as e:
        logger.error(f"Error fetching home stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch home statistics"
        )


@router.get("/current-jobs", response_model=List[CurrentJobResponse])
async def get_current_jobs(
    user: UserData = Depends(require_admin_authentication)
):
    """Get currently running or recent jobs"""
    try:
        jobs = []
        
        # Get job status from orchestrator
        job_status = get_job_status(client_id=user.client_id)
        
        for job_name, job_data in job_status.items():
            status_value = job_data.get('status', 'UNKNOWN')
            
            # Only include active or recently completed jobs
            if status_value in ['RUNNING', 'PENDING', 'ERROR', 'FINISHED']:
                jobs.append(CurrentJobResponse(
                    name=job_name.replace('_', ' ').title(),
                    status=status_value.lower(),
                    progress=job_data.get('progress'),
                    started_at=job_data.get('started_at'),
                    estimated_completion=job_data.get('estimated_completion')
                ))
        
        return jobs
        
    except Exception as e:
        logger.error(f"Error fetching current jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch current jobs"
        )


@router.get("/recent-activity", response_model=List[RecentActivityResponse])
async def get_recent_activity(
    user: UserData = Depends(require_admin_authentication)
):
    """Get recent activity for the home page"""
    try:
        activities = []
        database = get_database()
        
        with database.get_session() as session:
            # Get recent issues (last 24 hours)
            yesterday = datetime.now() - timedelta(days=1)
            
            recent_issues = session.query(Issue).filter(
                and_(
                    Issue.client_id == user.client_id,
                    Issue.created_at >= yesterday
                )
            ).order_by(desc(Issue.created_at)).limit(5).all()
            
            for issue in recent_issues:
                activities.append(RecentActivityResponse(
                    message=f"New issue created: {issue.key}",
                    timestamp=issue.created_at.isoformat(),
                    icon="plus-circle",
                    type="info"
                ))
            
            # Get recent pull requests
            recent_prs = session.query(PullRequest).filter(
                and_(
                    PullRequest.client_id == user.client_id,
                    PullRequest.created_at >= yesterday
                )
            ).order_by(desc(PullRequest.created_at)).limit(5).all()
            
            for pr in recent_prs:
                activities.append(RecentActivityResponse(
                    message=f"Pull request opened: #{pr.number}",
                    timestamp=pr.created_at.isoformat(),
                    icon="code-branch",
                    type="success"
                ))
            
            # Sort all activities by timestamp (most recent first)
            activities.sort(key=lambda x: x.timestamp, reverse=True)
            
            # Return top 10 activities
            return activities[:10]
            
    except Exception as e:
        logger.error(f"Error fetching recent activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch recent activity"
        )


@router.get("/jobs", response_model=List[JobCardResponse])
async def get_job_cards(
    user: UserData = Depends(require_admin_authentication)
):
    """Get all job cards for the home page dashboard"""
    try:
        # Get job cards for client (reduced logging for frequent calls)
        database = get_database()
        job_cards = []

        with database.get_write_session_context() as session:
            # Get all job schedules for this client (including inactive), ordered by execution_order
            job_schedules = session.query(JobSchedule).filter(
                JobSchedule.client_id == user.client_id
            ).order_by(JobSchedule.execution_order.asc()).all()

            for job in job_schedules:
                try:
                    # Get integration info if job has one
                    integration_type = None
                    integration_active = True

                    if job.integration_id:
                        integration = session.query(Integration).filter(
                            Integration.id == job.integration_id
                        ).first()
                        if integration:
                            integration_type = integration.provider
                            integration_active = integration.active

                    # Always use actual database status values
                    status_value = job.status
                    logger.debug(f"[HOME] Job {job.job_name} - ID: {job.id}, Status: {status_value}, Active: {job.active}")
                    last_sync = None

                    # Set last_sync if job has completed successfully
                    if job.last_success_at:
                        last_sync = job.last_success_at.isoformat()

                    # Create a job card
                    job_cards.append(JobCardResponse(
                        id=job.id,
                        job_name=job.job_name,
                        execution_order=job.execution_order,
                        integration_type=integration_type,
                        active=job.active,  # Use job.active from job_schedules table, not integration.active
                        last_sync=last_sync,
                        status=status_value,
                        last_run_started_at=job.last_run_started_at.isoformat() if job.last_run_started_at else None,
                        last_success_at=job.last_success_at.isoformat() if job.last_success_at else None,
                        retry_count=job.retry_count
                    ))

                except Exception as e:
                    logger.error(f"Error processing job {job.job_name}: {e}")
                    # Add job with error status instead of failing completely
                    job_cards.append(JobCardResponse(
                        id=job.id,
                        job_name=job.job_name,
                        execution_order=job.execution_order or 999,
                        integration_type="Unknown",
                        active=False,
                        last_sync=None,
                        status="error"
                    ))

        # Return job cards (debug logging only if needed)
        if len(job_cards) == 0:
            logger.warning(f"No job cards found for client {user.client_id}")
        return job_cards

    except Exception as e:
        logger.error(f"Error fetching job cards: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch job cards"
        )


@router.get("/integrations", response_model=List[IntegrationStatusResponse])
async def get_integrations(
    user: UserData = Depends(require_admin_authentication)
):
    """Get actual integrations (for admin purposes)"""
    try:
        # Get integrations for client (reduced logging for frequent calls)
        database = get_database()
        integrations = []

        with database.get_session() as session:
            # Get all integrations for this client
            db_integrations = session.query(Integration).filter(
                Integration.client_id == user.client_id
            ).all()

            for integration in db_integrations:
                try:
                    # For AI provider integrations, just show as connected if active
                    status_value = "connected" if integration.active else "inactive"

                    integrations.append(IntegrationStatusResponse(
                        id=integration.id,
                        name=integration.provider,
                        type=integration.type,
                        active=integration.active,
                        last_sync=None,  # Integrations don't have sync times, jobs do
                        status=status_value
                    ))

                except Exception as e:
                    logger.error(f"Error processing integration {integration.provider}: {e}")
                    integrations.append(IntegrationStatusResponse(
                        id=integration.id,
                        name=integration.provider,
                        type=integration.type or "Unknown",
                        active=integration.active,
                        last_sync=None,
                        status="error"
                    ))

        logger.info(f"Returning {len(integrations)} integrations")
        return integrations

    except Exception as e:
        logger.error(f"Error fetching integrations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch integrations"
        )


@router.post("/jobs/{job_id}/toggle")
async def toggle_job_active_status(
    job_id: int,
    user: UserData = Depends(require_admin_authentication)
):
    """Toggle the active status of a job (enable/disable)"""
    try:
        database = get_database()

        with database.get_session() as session:
            # Get the job with client isolation
            job = session.query(JobSchedule).filter(
                JobSchedule.id == job_id,
                JobSchedule.client_id == user.client_id  # Ensure client isolation
            ).first()

            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job {job_id} not found for client {user.client_id}"
                )

            # Toggle the active status
            old_status = job.active
            job.active = not job.active

            # When deactivating a job, set status to NOT_STARTED
            if not job.active:
                job.status = "NOT_STARTED"
                logger.info(f"[JOB] Set job {job.job_name} status to NOT_STARTED (deactivated)")

            session.commit()

            logger.info(f"[JOB] Toggled job {job.job_name} (ID: {job_id}) active status: {old_status} -> {job.active}")

            return {
                "success": True,
                "job_id": job_id,
                "job_name": job.job_name,
                "old_status": old_status,
                "new_status": job.active,
                "message": f"Job {job.job_name} {'activated' if job.active else 'deactivated'} successfully"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[JOB] Error toggling job {job_id} active status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle job status"
        )

