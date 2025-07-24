"""
Utility functions for querying Jira-PR links using the new join-based architecture.

This module demonstrates how to efficiently query the relationship between
Jira issues and GitHub pull requests using the JiraPullRequestLinks table.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Dict, Any, Optional
from app.models.unified_models import Issue, PullRequest, JiraPullRequestLinks, Repository


def get_issues_with_linked_prs(session: Session, client_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get Jira issues with their linked pull requests using join queries.
    
    Args:
        session: Database session
        client_id: Client ID to filter by
        limit: Maximum number of issues to return
        
    Returns:
        List of dictionaries containing issue and PR information
    """
    results = session.query(
        Issue.id.label('issue_id'),
        Issue.key.label('issue_key'),
        Issue.title.label('issue_title'),
        Issue.status.label('issue_status'),
        PullRequest.id.label('pr_id'),
        PullRequest.number.label('pr_number'),
        PullRequest.title.label('pr_title'),
        PullRequest.state.label('pr_state'),
        Repository.full_name.label('repo_name'),
        JiraPullRequestLinks.pr_status.label('link_status'),
        JiraPullRequestLinks.branch_name.label('branch_name')
    ).select_from(Issue)\
    .join(JiraPullRequestLinks, Issue.id == JiraPullRequestLinks.issue_id)\
    .join(PullRequest, and_(
        JiraPullRequestLinks.external_repo_id == PullRequest.external_repo_id,
        JiraPullRequestLinks.pull_request_number == PullRequest.number
    ))\
    .join(Repository, PullRequest.repository_id == Repository.id)\
    .filter(
        Issue.client_id == client_id,
        Issue.active == True,
        PullRequest.active == True,
        JiraPullRequestLinks.active == True
    )\
    .limit(limit)\
    .all()
    
    return [
        {
            'issue_id': row.issue_id,
            'issue_key': row.issue_key,
            'issue_title': row.issue_title,
            'issue_status': row.issue_status,
            'pr_id': row.pr_id,
            'pr_number': row.pr_number,
            'pr_title': row.pr_title,
            'pr_state': row.pr_state,
            'repo_name': row.repo_name,
            'link_status': row.link_status,
            'branch_name': row.branch_name
        }
        for row in results
    ]


def get_prs_for_issue(session: Session, issue_key: str, client_id: int) -> List[Dict[str, Any]]:
    """
    Get all pull requests linked to a specific Jira issue.
    
    Args:
        session: Database session
        issue_key: Jira issue key (e.g., 'PROJ-123')
        client_id: Client ID to filter by
        
    Returns:
        List of pull request information
    """
    results = session.query(
        PullRequest.id,
        PullRequest.number,
        PullRequest.title,
        PullRequest.state,
        PullRequest.created_at,
        PullRequest.updated_at,
        Repository.full_name.label('repo_name'),
        JiraPullRequestLinks.pr_status.label('link_status'),
        JiraPullRequestLinks.branch_name,
        JiraPullRequestLinks.commit_sha
    ).select_from(Issue)\
    .join(JiraPullRequestLinks, Issue.id == JiraPullRequestLinks.issue_id)\
    .join(PullRequest, and_(
        JiraPullRequestLinks.external_repo_id == PullRequest.external_repo_id,
        JiraPullRequestLinks.pull_request_number == PullRequest.number
    ))\
    .join(Repository, PullRequest.repository_id == Repository.id)\
    .filter(
        Issue.key == issue_key,
        Issue.client_id == client_id,
        Issue.active == True,
        PullRequest.active == True,
        JiraPullRequestLinks.active == True
    )\
    .all()
    
    return [
        {
            'pr_id': row.id,
            'pr_number': row.number,
            'pr_title': row.title,
            'pr_state': row.state,
            'pr_created_at': row.created_at,
            'pr_updated_at': row.updated_at,
            'repo_name': row.repo_name,
            'link_status': row.link_status,
            'branch_name': row.branch_name,
            'commit_sha': row.commit_sha
        }
        for row in results
    ]


def get_issues_for_repository(session: Session, repo_full_name: str, client_id: int) -> List[Dict[str, Any]]:
    """
    Get all Jira issues that have PRs in a specific repository.
    
    Args:
        session: Database session
        repo_full_name: Repository full name (e.g., 'wexinc/health-api')
        client_id: Client ID to filter by
        
    Returns:
        List of issue information with PR counts
    """
    results = session.query(
        Issue.id,
        Issue.key,
        Issue.title,
        Issue.status,
        Issue.priority,
        Issue.created_at,
        Issue.updated_at
    ).select_from(Issue)\
    .join(JiraPullRequestLinks, Issue.id == JiraPullRequestLinks.issue_id)\
    .join(PullRequest, and_(
        JiraPullRequestLinks.external_repo_id == PullRequest.external_repo_id,
        JiraPullRequestLinks.pull_request_number == PullRequest.number
    ))\
    .join(Repository, PullRequest.repository_id == Repository.id)\
    .filter(
        Repository.full_name == repo_full_name,
        Issue.client_id == client_id,
        Issue.active == True,
        PullRequest.active == True,
        JiraPullRequestLinks.active == True
    )\
    .distinct()\
    .all()
    
    return [
        {
            'issue_id': row.id,
            'issue_key': row.key,
            'issue_title': row.title,
            'issue_status': row.status,
            'issue_priority': row.priority,
            'issue_created_at': row.created_at,
            'issue_updated_at': row.updated_at
        }
        for row in results
    ]


def get_pr_link_statistics(session: Session, client_id: int) -> Dict[str, Any]:
    """
    Get statistics about PR-Issue links.
    
    Args:
        session: Database session
        client_id: Client ID to filter by
        
    Returns:
        Dictionary with link statistics
    """
    # Total links
    total_links = session.query(JiraPullRequestLinks).filter(
        JiraPullRequestLinks.client_id == client_id,
        JiraPullRequestLinks.active == True
    ).count()
    
    # Issues with PR links
    issues_with_prs = session.query(Issue.id).distinct()\
        .join(JiraPullRequestLinks, Issue.id == JiraPullRequestLinks.issue_id)\
        .filter(
            Issue.client_id == client_id,
            Issue.active == True,
            JiraPullRequestLinks.active == True
        ).count()
    
    # PRs with issue links
    prs_with_issues = session.query(PullRequest.id).distinct()\
        .join(JiraPullRequestLinks, and_(
            JiraPullRequestLinks.external_repo_id == PullRequest.external_repo_id,
            JiraPullRequestLinks.pull_request_number == PullRequest.number
        ))\
        .filter(
            PullRequest.client_id == client_id,
            PullRequest.active == True,
            JiraPullRequestLinks.active == True
        ).count()
    
    # Repositories with links
    repos_with_links = session.query(Repository.id).distinct()\
        .join(PullRequest, PullRequest.repository_id == Repository.id)\
        .join(JiraPullRequestLinks, and_(
            JiraPullRequestLinks.external_repo_id == PullRequest.external_repo_id,
            JiraPullRequestLinks.pull_request_number == PullRequest.number
        ))\
        .filter(
            Repository.client_id == client_id,
            Repository.active == True,
            PullRequest.active == True,
            JiraPullRequestLinks.active == True
        ).count()
    
    return {
        'total_pr_links': total_links,
        'issues_with_prs': issues_with_prs,
        'prs_with_issues': prs_with_issues,
        'repositories_with_links': repos_with_links
    }
