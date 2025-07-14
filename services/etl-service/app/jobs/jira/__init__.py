"""
Jira ETL Job Package

This package contains all components for Jira data extraction and processing.
Refactored from the monolithic jira_job.py for better maintainability.

Structure:
- jira_client.py: JiraAPIClient for API interactions
- jira_processor.py: JiraDataProcessor for data transformation
- jira_extractors.py: All extraction functions (_extract_*)
- jira_bulk_operations.py: Bulk database operations
- jira_job.py: New passive job implementation (Active/Passive Job Model)
- jira_utils.py: Utilities like JobLockManager
"""

# New orchestration system entry point
from .jira_job import run_jira_sync

# Export individual components for advanced usage
from .jira_client import JiraAPIClient
from .jira_processor import JiraDataProcessor
from .jira_utils import JobLockManager
from .jira_extractors import (
    extract_projects_and_issuetypes, extract_projects_and_statuses,
    extract_work_items_and_changelogs
)
from .jira_bulk_operations import perform_bulk_insert



def extract_issue_changelogs(session, jira_client, integration, issue_keys, statuses_dict, job_logger):
    """Backward compatibility wrapper - changelogs are now processed with issues."""
    # This function is now a no-op since changelogs are processed with issues
    job_logger.progress("ℹ️  Changelogs are now processed together with issues in step 6")
    return 0

__all__ = [
    'run_jira_sync',  # New orchestration system entry point
    'JiraAPIClient',
    'JiraDataProcessor',
    'JobLockManager',
    'extract_projects_and_issuetypes',  # Combined projects and issue types function
    'extract_projects_and_statuses',  # Combined projects and statuses function
    'extract_work_items_and_changelogs',  # Combined issues and changelogs function
    'extract_issue_changelogs',  # Backward compatibility wrapper
    'perform_bulk_insert'
]
