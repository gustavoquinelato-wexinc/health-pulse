"""
Jira ETL Job Package

This package contains all components for Jira data extraction and processing.
Refactored from the monolithic jira_job.py for better maintainability.

Structure:
- jira_client.py: JiraAPITenant for API interactions
- jira_processor.py: JiraDataProcessor for data transformation
- jira_extractors.py: All extraction functions (_extract_*)
- jira_bulk_operations.py: Bulk database operations
- jira_job.py: New passive job implementation (Active/Passive Job Model)
- jira_utils.py: Utilities like JobLockManager
"""

# New orchestration system entry point
from .jira_job import run_jira_sync

# Export individual components for advanced usage
from .jira_client import JiraAPITenant
from .jira_processor import JiraDataProcessor
from .jira_utils import JobLockManager
from .jira_extractors import (
    extract_projects_and_issuetypes, extract_projects_and_statuses,
    extract_work_items_and_changelogs
)
from .jira_bulk_operations import perform_bulk_insert



# Removed deprecated extract_issue_changelogs function - changelogs are now processed with issues

__all__ = [
    'run_jira_sync',  # New orchestration system entry point
    'JiraAPITenant',
    'JiraDataProcessor',
    'JobLockManager',
    'extract_projects_and_issuetypes',  # Combined projects and issue types function
    'extract_projects_and_statuses',  # Combined projects and statuses function
    'extract_work_items_and_changelogs',  # Combined issues and changelogs function
    'extract_issue_changelogs',  # Backward compatibility wrapper
    'perform_bulk_insert'
]
