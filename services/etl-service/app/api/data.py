"""
Data access endpoints for ETL service.
Provides access to extracted and processed data.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from app.core.database import get_db_session
from app.models.unified_models import (
    Issue, PullRequestCommit, PullRequest, Project, Client, Repository
)
from app.schemas.api_schemas import (
    DataSummaryResponse, IssuesListResponse, CommitsListResponse,
    PullRequestsListResponse, IssueInfo, CommitInfo, PullRequestInfo
)

router = APIRouter()


@router.get("/etl/data/summary", response_model=DataSummaryResponse)
async def get_data_summary(db: Session = Depends(get_db_session)):
    """
    Get a summary of all extracted data.
    
    Returns:
        DataSummaryResponse: Counts and statistics for all data types
    """
    try:
        # Get counts for each data type
        issues_count = db.query(func.count(Issue.id)).scalar() or 0
        commits_count = db.query(func.count(PullRequestCommit.id)).scalar() or 0
        pull_requests_count = db.query(func.count(PullRequest.id)).scalar() or 0
        users_count = 0  # No User model currently - could be derived from assignees/authors
        projects_count = db.query(func.count(Project.id)).scalar() or 0
        clients_count = db.query(func.count(Client.id)).scalar() or 0

        # Get latest update timestamps
        latest_issue = db.query(func.max(Issue.last_updated_at)).scalar()
        latest_commit = db.query(func.max(PullRequestCommit.last_updated_at)).scalar()
        latest_pr = db.query(func.max(PullRequest.last_updated_at)).scalar()
        
        return DataSummaryResponse(
            integrations_count=0,  # TODO: Add integrations count when needed
            projects_count=projects_count,
            issues_count=issues_count,
            commits_count=commits_count,
            pull_requests_count=pull_requests_count,
            last_sync_at=latest_pr  # Use latest PR update as overall sync indicator
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get data summary: {str(e)}")


@router.get("/etl/data/issues", response_model=IssuesListResponse)
async def get_issues(
    limit: int = Query(100, ge=1, le=1000, description="Number of issues to return"),
    offset: int = Query(0, ge=0, description="Number of issues to skip"),
    project_key: Optional[str] = Query(None, description="Filter by project key"),
    status: Optional[str] = Query(None, description="Filter by issue status"),
    db: Session = Depends(get_db_session)
):
    """
    Get a list of issues with optional filtering.
    
    Args:
        limit: Maximum number of issues to return
        offset: Number of issues to skip (for pagination)
        project_key: Optional project key filter
        status: Optional status filter
        db: Database session
        
    Returns:
        IssuesListResponse: List of issues with metadata
    """
    try:
        # Build query
        query = db.query(Issue)
        
        # Apply filters
        if project_key:
            query = query.filter(Issue.project_key == project_key)
        if status:
            query = query.filter(Issue.status == status)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        issues = query.order_by(desc(Issue.updated_at)).offset(offset).limit(limit).all()
        
        # Convert to response format
        issue_list = [
            IssueInfo(
                id=issue.id,
                key=issue.key,
                summary=issue.summary,
                status=issue.status,
                project_key=issue.project_key,
                created_at=issue.created_at,
                updated_at=issue.updated_at
            )
            for issue in issues
        ]
        
        return IssuesListResponse(
            issues=issue_list,
            total_count=total_count,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get issues: {str(e)}")


@router.get("/etl/data/commits", response_model=CommitsListResponse)
async def get_commits(
    limit: int = Query(100, ge=1, le=1000, description="Number of commits to return"),
    offset: int = Query(0, ge=0, description="Number of commits to skip"),
    repository: Optional[str] = Query(None, description="Filter by repository name"),
    db: Session = Depends(get_db_session)
):
    """
    Get a list of commits with optional filtering.
    
    Args:
        limit: Maximum number of commits to return
        offset: Number of commits to skip (for pagination)
        repository: Optional repository filter
        db: Database session
        
    Returns:
        CommitsListResponse: List of commits with metadata
    """
    try:
        # Build query - join with PullRequest and Repository to get repository info
        query = db.query(PullRequestCommit).join(PullRequest).join(Repository)

        # Apply filters
        if repository:
            query = query.filter(Repository.name == repository)

        # Get total count before pagination
        total_count = query.count()

        # Apply pagination and ordering
        commits = query.order_by(desc(PullRequestCommit.committed_date)).offset(offset).limit(limit).all()

        # Convert to response format
        commit_list = [
            CommitInfo(
                sha=commit.external_id,  # external_id is the SHA
                issue_id=commit.pull_request.issue_id if commit.pull_request.issue_id else 0,
                repository_url=commit.pull_request.repository.url if commit.pull_request.repository else None,
                author_name=commit.author_name,
                message=commit.message,
                commit_date=commit.committed_date
            )
            for commit in commits
        ]

        return CommitsListResponse(
            commits=commit_list,
            total_count=total_count,
            page=offset // limit + 1,
            page_size=limit
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get commits: {str(e)}")


@router.get("/etl/data/pull-requests", response_model=PullRequestsListResponse)
async def get_pull_requests(
    limit: int = Query(100, ge=1, le=1000, description="Number of PRs to return"),
    offset: int = Query(0, ge=0, description="Number of PRs to skip"),
    repository: Optional[str] = Query(None, description="Filter by repository name"),
    state: Optional[str] = Query(None, description="Filter by PR state"),
    db: Session = Depends(get_db_session)
):
    """
    Get a list of pull requests with optional filtering.
    
    Args:
        limit: Maximum number of PRs to return
        offset: Number of PRs to skip (for pagination)
        repository: Optional repository filter
        state: Optional state filter (open, closed, merged)
        db: Database session
        
    Returns:
        PullRequestsListResponse: List of pull requests with metadata
    """
    try:
        # Build query
        query = db.query(PullRequest)
        
        # Apply filters
        if repository:
            query = query.filter(PullRequest.repository_name == repository)
        if state:
            query = query.filter(PullRequest.state == state)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        pull_requests = query.order_by(desc(PullRequest.updated_at)).offset(offset).limit(limit).all()
        
        # Convert to response format
        pr_list = [
            PullRequestInfo(
                id=pr.id,
                number=pr.number,
                title=pr.title,
                state=pr.state,
                repository_name=pr.repository_name,
                author_login=pr.author_login,
                created_at=pr.created_at,
                updated_at=pr.updated_at
            )
            for pr in pull_requests
        ]
        
        return PullRequestsListResponse(
            pull_requests=pr_list,
            total_count=total_count,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pull requests: {str(e)}")
