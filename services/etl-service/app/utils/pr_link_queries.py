"""
Utility functions for querying Jira-PR links using the new join-based architecture.

This module demonstrates how to efficiently query the relationship between
Jira issues and GitHub pull requests using the WitPrLinks table.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Dict, Any, Optional
from app.models.unified_models import WorkItem, Pr, WitPrLinks, Repository


def get_issues_with_linked_prs(session: Session, tenant_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get Jira issues with their linked pull requests using join queries.
    
    Args:
        session: Database session
        tenant_id: Tenant ID to filter by
        limit: Maximum number of issues to return
        
    Returns:
        List of dictionaries containing issue and PR information
    """
    results = session.query(
        WorkItem.id.label('issue_id'),
        WorkItem.key.label('issue_key'),
        WorkItem.title.label('issue_title'),
        WorkItem.status.label('issue_status'),
        Pr.id.label('pr_id'),
        Pr.number.label('pr_number'),
        Pr.title.label('pr_title'),
        Pr.state.label('pr_state'),
        Repository.full_name.label('repo_name'),
        WitPrLinks.pr_status.label('link_status'),
        WitPrLinks.branch_name.label('branch_name')
    ).select_from(WorkItem)\
    .join(WitPrLinks, WorkItem.id == WitPrLinks.work_item_id)\
    .join(Pr, and_(
        WitPrLinks.external_repo_id == Pr.external_repo_id,
        WitPrLinks.pull_request_number == Pr.number
    ))\
    .join(Repository, Pr.repository_id == Repository.id)\
    .filter(
        WorkItem.tenant_id == tenant_id,
        WorkItem.active == True,
        Pr.active == True,
        WitPrLinks.active == True
    )\
    .limit(limit)\
    .all()
    
    return [
        {
            'issue_id': row.work_item_id,
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


def get_prs_for_issue(session: Session, issue_key: str, tenant_id: int) -> List[Dict[str, Any]]:
    """
    Get all pull requests linked to a specific Jira issue.
    
    Args:
        session: Database session
        issue_key: Jira issue key (e.g., 'PROJ-123')
        tenant_id: Tenant ID to filter by
        
    Returns:
        List of pull request information
    """
    results = session.query(
        Pr.id,
        Pr.number,
        Pr.title,
        Pr.state,
        Pr.created_at,
        Pr.updated_at,
        Repository.full_name.label('repo_name'),
        WitPrLinks.pr_status.label('link_status'),
        WitPrLinks.branch_name,
        WitPrLinks.commit_sha
    ).select_from(WorkItem)\
    .join(WitPrLinks, WorkItem.id == WitPrLinks.work_item_id)\
    .join(Pr, and_(
        WitPrLinks.external_repo_id == Pr.external_repo_id,
        WitPrLinks.pull_request_number == Pr.number
    ))\
    .join(Repository, Pr.repository_id == Repository.id)\
    .filter(
        WorkItem.key == issue_key,
        WorkItem.tenant_id == tenant_id,
        WorkItem.active == True,
        Pr.active == True,
        WitPrLinks.active == True
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


def get_issues_for_repository(session: Session, repo_full_name: str, tenant_id: int) -> List[Dict[str, Any]]:
    """
    Get all Jira issues that have PRs in a specific repository.
    
    Args:
        session: Database session
        repo_full_name: Repository full name (e.g., 'wexinc/health-api')
        tenant_id: Tenant ID to filter by
        
    Returns:
        List of issue information with PR counts
    """
    results = session.query(
        WorkItem.id,
        WorkItem.key,
        WorkItem.title,
        WorkItem.status,
        WorkItem.priority,
        WorkItem.created_at,
        WorkItem.updated_at
    ).select_from(WorkItem)\
    .join(WitPrLinks, WorkItem.id == WitPrLinks.work_item_id)\
    .join(Pr, and_(
        WitPrLinks.external_repo_id == Pr.external_repo_id,
        WitPrLinks.pull_request_number == Pr.number
    ))\
    .join(Repository, Pr.repository_id == Repository.id)\
    .filter(
        Repository.full_name == repo_full_name,
        WorkItem.tenant_id == tenant_id,
        WorkItem.active == True,
        Pr.active == True,
        WitPrLinks.active == True
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


def get_pr_link_statistics(session: Session, tenant_id: int) -> Dict[str, Any]:
    """
    Get statistics about PR-WorkItem links.
    
    Args:
        session: Database session
        tenant_id: Tenant ID to filter by
        
    Returns:
        Dictionary with link statistics
    """
    # Total links
    total_links = session.query(WitPrLinks).filter(
        WitPrLinks.tenant_id == tenant_id,
        WitPrLinks.active == True
    ).count()
    
    # WorkItems with PR links
    issues_with_prs = session.query(WorkItem.id).distinct()\
        .join(WitPrLinks, WorkItem.id == WitPrLinks.work_item_id)\
        .filter(
            WorkItem.tenant_id == tenant_id,
            WorkItem.active == True,
            WitPrLinks.active == True
        ).count()
    
    # PRs with issue links
    prs_with_issues = session.query(Pr.id).distinct()\
        .join(WitPrLinks, and_(
            WitPrLinks.external_repo_id == Pr.external_repo_id,
            WitPrLinks.pull_request_number == Pr.number
        ))\
        .filter(
            Pr.tenant_id == tenant_id,
            Pr.active == True,
            WitPrLinks.active == True
        ).count()
    
    # Repositories with links
    repos_with_links = session.query(Repository.id).distinct()\
        .join(Pr, Pr.repository_id == Repository.id)\
        .join(WitPrLinks, and_(
            WitPrLinks.external_repo_id == Pr.external_repo_id,
            WitPrLinks.pull_request_number == Pr.number
        ))\
        .filter(
            Repository.tenant_id == tenant_id,
            Repository.active == True,
            Pr.active == True,
            WitPrLinks.active == True
        ).count()
    
    return {
        'total_pr_links': total_links,
        'issues_with_prs': issues_with_prs,
        'prs_with_issues': prs_with_issues,
        'repositories_with_links': repos_with_links
    }
