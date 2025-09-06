"""
Pydantic schemas for API requests and responses.
Defines data models for REST API input and output.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    """Possible job statuses."""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


class HealthResponse(BaseModel):
    """Response for health check."""
    status: str = "healthy"
    message: str = "ETL Service is running"
    database_status: str
    database_message: str
    version: str

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class JobRunRequest(BaseModel):
    """Request to execute a job."""
    force_full_sync: Optional[bool] = Field(
        default=False,
        description="If True, forces complete sync ignoring last sync date",
        example=False
    )
    projects: Optional[List[str]] = Field(
        default=None,
        description="List of project keys to synchronize. If None, syncs all",
        example=["PROJ", "TEST", "DEMO"]
    )
    include_dev_data: Optional[bool] = Field(
        default=True,
        description="If True, includes development data extraction",
        example=True
    )

    class Config:
        json_schema_extra = {
            "example": {
                "force_full_sync": False,
                "projects": ["PROJ", "TEST"],
                "include_dev_data": True
            }
        }


class JobRunResponse(BaseModel):
    """Response for job execution."""
    job_id: str = Field(description="Unique ID of the executed job")
    status: JobStatus
    message: str
    started_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class JobStatusResponse(BaseModel):
    """Response for job status."""
    job_id: str
    status: JobStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    issues_processed: Optional[int] = None
    commits_extracted: Optional[int] = None
    pull_requests_extracted: Optional[int] = None
    errors: Optional[List[str]] = None
    progress_percentage: Optional[float] = None
    current_step: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Note: Individual job scheduling schemas removed
# Only the orchestrator is scheduled - individual jobs are triggered by the orchestrator


class IntegrationInfo(BaseModel):
    """Information about an integration."""
    id: int
    name: str
    base_url: str  # Updated to match new integration model
    username: Optional[str] = None
    model: Optional[str] = None  # AI model name
    last_sync_at: Optional[datetime] = None  # Populated from job_schedules.last_success_at (not from integration table)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ProjectInfo(BaseModel):
    """Information about a project."""
    id: int
    key: str
    name: str
    integration_id: int
    tool_internal_id: Optional[int] = None


class WorkItemInfo(BaseModel):
    """Information about an issue."""
    id: int
    key: str
    summary: str
    project_id: Optional[int] = None
    wit_id: Optional[int] = None
    status_id: Optional[int] = None
    assignee: Optional[str] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CommitInfo(BaseModel):
    """Information about a commit."""
    sha: str
    issue_id: int
    repository_url: Optional[str] = None
    author_name: Optional[str] = None
    message: Optional[str] = None
    commit_date: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PrInfo(BaseModel):
    """Information about a pull request."""
    id: int
    issue_id: int
    status: Optional[str] = None
    author_name: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    pr_created_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DataSummaryResponse(BaseModel):
    """Response with data summary in the system."""
    integrations_count: int
    projects_count: int
    issues_count: int
    commits_count: int
    pull_requests_count: int
    last_sync_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ErrorResponse(BaseModel):
    """Standard response for errors."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DatabaseStatsResponse(BaseModel):
    """Response with database statistics."""
    tables: Dict[str, int] = Field(description="Record count per table")
    last_updated: datetime
    database_size_mb: Optional[float] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Schemas for listing with pagination
class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=50, ge=1, le=1000, description="Page size")


class WorkItemsListResponse(BaseModel):
    """Response for issues listing."""
    issues: List[WorkItemInfo]
    total_count: int
    page: int
    page_size: int


class CommitsListResponse(BaseModel):
    """Response for commits listing."""
    commits: List[CommitInfo]
    total_count: int
    page: int
    page_size: int


class PrsListResponse(BaseModel):
    """Response for pull requests listing."""
    pull_requests: List[PrInfo]
    total_count: int
    page: int
    page_size: int
