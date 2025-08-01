"""
Metrics Helper Functions with Deactivation Strategy Implementation

This module provides helper functions that implement the comprehensive deactivation
strategy for metrics calculations, ensuring that deactivated records at any level
of the relationship chain are properly excluded.

CRITICAL: All metrics calculations must use these helpers to ensure data integrity.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.unified_models import (
    Issue, Status, StatusMapping, Workflow,
    Issuetype, IssuetypeMapping, IssuetypeHierarchy
)


def get_active_issues_query(session: Session, client_id: int, include_inactive: bool = False):
    """
    Get a query for issues that excludes deactivated records at all relationship levels.
    🚨 SECURITY: Now requires client_id to prevent cross-client data access.

    Args:
        session: Database session
        client_id: Client ID to filter by (REQUIRED for security)
        include_inactive: If True, includes data connected to inactive records (for data quality analysis)

    Returns:
        SQLAlchemy query object with proper active-only and client filtering
    """
    query = session.query(Issue).join(Status).join(StatusMapping).join(Workflow)

    # 🚨 SECURITY: Always filter by client_id first
    query = query.filter(Issue.client_id == client_id)

    if not include_inactive:
        query = query.filter(
            and_(
                Issue.active == True,
                Status.active == True,
                StatusMapping.active == True,
                Workflow.active == True
            )
        )

    return query


def get_workflow_metrics(session: Session, client_id: int, include_inactive: bool = False):
    """
    Get issue counts by flow step, excluding deactivated relationship chains.
    🚨 SECURITY: Now requires client_id to prevent cross-client data access.

    Args:
        session: Database session
        client_id: Client ID to filter by (REQUIRED for security)
        include_inactive: If True, includes data connected to inactive records

    Returns:
        List of dictionaries with flow step metrics
    """
    query = session.query(
        Workflow.id,
        Workflow.step_name,
        Workflow.step_number,
        Workflow.step_category,
        Workflow.active.label('workflow_active')
    ).join(StatusMapping).join(Status).join(Issue)

    # 🚨 SECURITY: Always filter by client_id first
    query = query.filter(Issue.client_id == client_id)

    if not include_inactive:
        query = query.filter(
            and_(
                Workflow.active == True,
                StatusMapping.active == True,
                Status.active == True,
                Issue.active == True
            )
        )
    
    # Group by flow step and count issues
    from sqlalchemy import func
    query = query.add_column(func.count(Issue.id).label('issue_count'))
    query = query.group_by(
        Workflow.id, Workflow.step_name, Workflow.step_number,
        Workflow.step_category, Workflow.active
    )
    query = query.order_by(Workflow.step_number)
    
    results = query.all()
    
    return [
        {
            'workflow_id': result.id,
            'workflow_name': result.step_name,
            'step_number': result.step_number,
            'step_category': result.step_category,
            'workflow_active': result.workflow_active,
            'issue_count': result.issue_count,
            'data_quality_note': 'Includes inactive chain data' if include_inactive else 'Active data only'
        }
        for result in results
    ]


def get_issuetype_metrics(session: Session, client_id: int, include_inactive: bool = False):
    """
    Get issue counts by issue type hierarchy, excluding deactivated relationship chains.
    🚨 SECURITY: Now requires client_id to prevent cross-client data access.

    Args:
        session: Database session
        client_id: Client ID to filter by (REQUIRED for security)
        include_inactive: If True, includes data connected to inactive records

    Returns:
        List of dictionaries with issue type metrics
    """
    query = session.query(
        IssuetypeHierarchy.id,
        IssuetypeHierarchy.level_name,
        IssuetypeHierarchy.level_number,
        IssuetypeHierarchy.active.label('hierarchy_active')
    ).join(IssuetypeMapping).join(Issuetype).join(Issue)

    # 🚨 SECURITY: Always filter by client_id first
    query = query.filter(Issue.client_id == client_id)

    if not include_inactive:
        query = query.filter(
            and_(
                IssuetypeHierarchy.active == True,
                IssuetypeMapping.active == True,
                Issuetype.active == True,
                Issue.active == True
            )
        )
    
    # Group by hierarchy and count issues
    from sqlalchemy import func
    query = query.add_column(func.count(Issue.id).label('issue_count'))
    query = query.group_by(
        IssuetypeHierarchy.id, IssuetypeHierarchy.level_name, 
        IssuetypeHierarchy.level_number, IssuetypeHierarchy.active
    )
    query = query.order_by(IssuetypeHierarchy.level_number)
    
    results = query.all()
    
    return [
        {
            'hierarchy_id': result.id,
            'level_name': result.level_name,
            'level_number': result.level_number,
            'hierarchy_active': result.hierarchy_active,
            'issue_count': result.issue_count,
            'data_quality_note': 'Includes inactive chain data' if include_inactive else 'Active data only'
        }
        for result in results
    ]


def get_data_quality_report(session: Session, client_id: int):
    """
    Generate a data quality report showing orphaned and inactive data.
    🚨 SECURITY: Now requires client_id to prevent cross-client data access.

    Args:
        session: Database session
        client_id: Client ID to filter by (REQUIRED for security)

    Returns:
        Dictionary with data quality metrics
    """
    # 🚨 SECURITY: Count total vs active issues filtered by client_id
    total_issues = session.query(Issue).filter(Issue.client_id == client_id).count()
    active_chain_issues = get_active_issues_query(session, client_id, include_inactive=False).count()

    # Count issues connected to inactive workflows (filtered by client_id)
    inactive_workflow_issues = session.query(Issue).join(Status).join(StatusMapping).join(Workflow).filter(
        and_(
            Issue.client_id == client_id,  # 🚨 SECURITY: Client filtering
            Issue.active == True,
            Status.active == True,
            StatusMapping.active == True,
            Workflow.active == False  # Workflow is inactive
        )
    ).count()

    # Count issues connected to inactive status mappings (filtered by client_id)
    inactive_mapping_issues = session.query(Issue).join(Status).join(StatusMapping).filter(
        and_(
            Issue.client_id == client_id,  # 🚨 SECURITY: Client filtering
            Issue.active == True,
            Status.active == True,
            StatusMapping.active == False  # Status mapping is inactive
        )
    ).count()

    # Count issues connected to inactive statuses (filtered by client_id)
    inactive_status_issues = session.query(Issue).join(Status).filter(
        and_(
            Issue.client_id == client_id,  # 🚨 SECURITY: Client filtering
            Issue.active == True,
            Status.active == False  # Status is inactive
        )
    ).count()
    
    return {
        'total_issues': total_issues,
        'active_chain_issues': active_chain_issues,
        'excluded_from_metrics': total_issues - active_chain_issues,
        'exclusion_breakdown': {
            'inactive_workflow_chain': inactive_workflow_issues,
            'inactive_status_mapping_chain': inactive_mapping_issues,
            'inactive_status_chain': inactive_status_issues,
        },
        'data_completeness_percentage': round((active_chain_issues / total_issues * 100), 2) if total_issues > 0 else 0,
        'recommendations': [
            'Review inactive workflows and consider reassigning dependencies' if inactive_workflow_issues > 0 else None,
            'Review inactive status mappings and consider reassigning dependencies' if inactive_mapping_issues > 0 else None,
            'Review inactive statuses and consider reassigning dependencies' if inactive_status_issues > 0 else None,
        ]
    }


def validate_metrics_query(query_description: str, includes_active_filtering: bool, includes_client_filtering: bool):
    """
    Validation helper to ensure metrics queries follow deactivation strategy AND client isolation.
    🚨 SECURITY: Now validates both active filtering and client filtering.

    Args:
        query_description: Description of what the query does
        includes_active_filtering: Whether the query properly filters by active status at all levels
        includes_client_filtering: Whether the query properly filters by client_id (REQUIRED)

    Raises:
        ValueError: If query doesn't follow deactivation strategy or client isolation
    """
    if not includes_client_filtering:
        raise ValueError(
            f"🚨 SECURITY VIOLATION: Metrics query '{query_description}' missing client_id filtering. "
            "ALL metrics queries MUST filter by client_id to prevent cross-client data access."
        )

    if not includes_active_filtering:
        raise ValueError(
            f"Metrics query '{query_description}' violates deactivation strategy. "
            "All metrics queries must filter by active status at ALL relationship levels. "
            "See docs/DEACTIVATION_STRATEGY.md for implementation guidelines."
        )


# Example usage patterns for common metrics scenarios
METRICS_EXAMPLES = {
    'workflow_distribution': """
        # 🚨 SECURITY: All metrics functions now require client_id
        from app.core.config import get_current_client_id
        client_id = get_current_client_id()

        # Get issue distribution across workflow steps (active only)
        metrics = get_workflow_metrics(session, client_id, include_inactive=False)

        # Get workflow distribution including inactive chains (data quality view)
        quality_metrics = get_workflow_metrics(session, client_id, include_inactive=True)
    """,

    'custom_metrics': """
        # Custom metrics query following deactivation strategy AND client isolation
        from app.utils.metrics_helpers import validate_metrics_query
        from app.core.config import get_current_client_id

        client_id = get_current_client_id()

        # Your custom query here - MUST include client_id filtering
        query = session.query(Issue).join(Status).join(StatusMapping).join(Workflow).filter(
            and_(
                Issue.client_id == client_id,  # 🚨 SECURITY: Required client filtering
                Issue.active == True,
                Status.active == True,
                StatusMapping.active == True,
                Workflow.active == True,
                # Your additional filters here
            )
        )

        # Validate that query follows both strategies
        validate_metrics_query("Custom workflow metrics",
                             includes_active_filtering=True,
                             includes_client_filtering=True)
    """,

    'data_quality_check': """
        # Generate data quality report (now requires client_id)
        from app.core.config import get_current_client_id
        client_id = get_current_client_id()

        quality_report = get_data_quality_report(session, client_id)

        print(f"Data completeness: {quality_report['data_completeness_percentage']}%")
        print(f"Issues excluded from metrics: {quality_report['excluded_from_metrics']}")
    """
}
