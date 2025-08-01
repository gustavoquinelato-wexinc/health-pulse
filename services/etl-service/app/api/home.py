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


@router.get("/stats", response_model=HomeStatsResponse)
async def get_home_stats(
    user: UserData = Depends(require_admin_authentication)
):
    """Get home page statistics"""
    try:
        database = get_database()
        with database.get_session() as session:
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


@router.get("/integrations", response_model=List[IntegrationStatusResponse])
async def get_integration_status(
    user: UserData = Depends(require_admin_authentication)
):
    """Get integration status for the home page"""
    try:
        logger.info(f"Getting integration status for client_id: {user.client_id}")
        database = get_database()
        integrations = []

        with database.get_session() as session:
            # Get all integrations for this client
            db_integrations = session.query(Integration).filter(
                Integration.client_id == user.client_id
            ).all()

            logger.info(f"Found {len(db_integrations)} integrations for client {user.client_id}")
            
            for integration in db_integrations:
                try:
                    # Use integration.name as the type (JIRA, GITHUB, etc.)
                    integration_type = integration.name or "Unknown"
                    logger.debug(f"Processing integration: {integration.name} (type: {integration_type})")

                    # Determine status based on recent activity
                    status_value = "inactive"
                    last_sync = None

                    if integration.active:
                        # Check for recent data to determine if connected
                        if integration_type.lower() == 'jira':
                            try:
                                recent_issues = session.query(Issue).filter(
                                    and_(
                                        Issue.client_id == user.client_id,
                                        Issue.updated >= datetime.now() - timedelta(hours=24)
                                    )
                                ).first()

                                if recent_issues:
                                    status_value = "connected"
                                    last_sync = recent_issues.updated.isoformat()
                                else:
                                    status_value = "error"
                            except Exception as e:
                                logger.warning(f"Error checking Jira issues for integration {integration.name}: {e}")
                                status_value = "error"

                        elif integration_type.lower() == 'github':
                            try:
                                recent_prs = session.query(PullRequest).filter(
                                    and_(
                                        PullRequest.client_id == user.client_id,
                                        PullRequest.updated_at >= datetime.now() - timedelta(hours=24)
                                    )
                                ).first()

                                if recent_prs:
                                    status_value = "connected"
                                    last_sync = recent_prs.updated_at.isoformat()
                                else:
                                    status_value = "error"
                            except Exception as e:
                                logger.warning(f"Error checking GitHub PRs for integration {integration.name}: {e}")
                                status_value = "error"
                
                    integrations.append(IntegrationStatusResponse(
                        id=integration.id,
                        name=integration.name,
                        type=integration_type,
                        active=integration.active,
                        last_sync=last_sync,
                        status=status_value
                    ))
                except Exception as e:
                    logger.error(f"Error processing integration {integration.name}: {e}")
                    # Add integration with error status instead of failing completely
                    integrations.append(IntegrationStatusResponse(
                        id=integration.id,
                        name=integration.name,
                        type=integration.name or "Unknown",  # Fallback to name as type
                        active=integration.active,
                        last_sync=None,
                        status="error"
                    ))

        logger.info(f"Returning {len(integrations)} integrations")
        return integrations

    except Exception as e:
        logger.error(f"Error fetching integration status: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch integration status"
        )
