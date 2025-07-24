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
    Issue, Status, StatusMapping, FlowStep,
    IssueType, IssuetypeMapping, IssuetypeHierarchy
)


def get_active_issues_query(session: Session, include_inactive: bool = False):
    """
    Get a query for issues that excludes deactivated records at all relationship levels.
    
    Args:
        session: Database session
        include_inactive: If True, includes data connected to inactive records (for data quality analysis)
    
    Returns:
        SQLAlchemy query object with proper active-only filtering
    """
    query = session.query(Issue).join(Status).join(StatusMapping).join(FlowStep)
    
    if not include_inactive:
        query = query.filter(
            and_(
                Issue.active == True,
                Status.active == True,
                StatusMapping.active == True,
                FlowStep.active == True
            )
        )
    
    return query


def get_workflow_metrics(session: Session, include_inactive: bool = False):
    """
    Get issue counts by flow step, excluding deactivated relationship chains.
    
    Args:
        session: Database session
        include_inactive: If True, includes data connected to inactive records
    
    Returns:
        List of dictionaries with flow step metrics
    """
    query = session.query(
        FlowStep.id,
        FlowStep.name,
        FlowStep.step_number,
        FlowStep.step_category,
        FlowStep.active.label('flow_step_active')
    ).join(StatusMapping).join(Status).join(Issue)
    
    if not include_inactive:
        query = query.filter(
            and_(
                FlowStep.active == True,
                StatusMapping.active == True,
                Status.active == True,
                Issue.active == True
            )
        )
    
    # Group by flow step and count issues
    from sqlalchemy import func
    query = query.add_column(func.count(Issue.id).label('issue_count'))
    query = query.group_by(
        FlowStep.id, FlowStep.name, FlowStep.step_number, 
        FlowStep.step_category, FlowStep.active
    )
    query = query.order_by(FlowStep.step_number)
    
    results = query.all()
    
    return [
        {
            'flow_step_id': result.id,
            'flow_step_name': result.name,
            'step_number': result.step_number,
            'step_category': result.step_category,
            'flow_step_active': result.flow_step_active,
            'issue_count': result.issue_count,
            'data_quality_note': 'Includes inactive chain data' if include_inactive else 'Active data only'
        }
        for result in results
    ]


def get_issuetype_metrics(session: Session, include_inactive: bool = False):
    """
    Get issue counts by issue type hierarchy, excluding deactivated relationship chains.
    
    Args:
        session: Database session
        include_inactive: If True, includes data connected to inactive records
    
    Returns:
        List of dictionaries with issue type metrics
    """
    query = session.query(
        IssuetypeHierarchy.id,
        IssuetypeHierarchy.level_name,
        IssuetypeHierarchy.level_number,
        IssuetypeHierarchy.active.label('hierarchy_active')
    ).join(IssuetypeMapping).join(IssueType).join(Issue)
    
    if not include_inactive:
        query = query.filter(
            and_(
                IssuetypeHierarchy.active == True,
                IssuetypeMapping.active == True,
                IssueType.active == True,
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


def get_data_quality_report(session: Session):
    """
    Generate a data quality report showing orphaned and inactive data.
    
    Args:
        session: Database session
    
    Returns:
        Dictionary with data quality metrics
    """
    # Count total vs active issues
    total_issues = session.query(Issue).count()
    active_chain_issues = get_active_issues_query(session, include_inactive=False).count()
    
    # Count issues connected to inactive flow steps
    inactive_flow_step_issues = session.query(Issue).join(Status).join(StatusMapping).join(FlowStep).filter(
        and_(
            Issue.active == True,
            Status.active == True,
            StatusMapping.active == True,
            FlowStep.active == False  # Flow step is inactive
        )
    ).count()
    
    # Count issues connected to inactive status mappings
    inactive_mapping_issues = session.query(Issue).join(Status).join(StatusMapping).filter(
        and_(
            Issue.active == True,
            Status.active == True,
            StatusMapping.active == False  # Status mapping is inactive
        )
    ).count()
    
    # Count issues connected to inactive statuses
    inactive_status_issues = session.query(Issue).join(Status).filter(
        and_(
            Issue.active == True,
            Status.active == False  # Status is inactive
        )
    ).count()
    
    return {
        'total_issues': total_issues,
        'active_chain_issues': active_chain_issues,
        'excluded_from_metrics': total_issues - active_chain_issues,
        'exclusion_breakdown': {
            'inactive_flow_step_chain': inactive_flow_step_issues,
            'inactive_status_mapping_chain': inactive_mapping_issues,
            'inactive_status_chain': inactive_status_issues,
        },
        'data_completeness_percentage': round((active_chain_issues / total_issues * 100), 2) if total_issues > 0 else 0,
        'recommendations': [
            'Review inactive flow steps and consider reassigning dependencies' if inactive_flow_step_issues > 0 else None,
            'Review inactive status mappings and consider reassigning dependencies' if inactive_mapping_issues > 0 else None,
            'Review inactive statuses and consider reassigning dependencies' if inactive_status_issues > 0 else None,
        ]
    }


def validate_metrics_query(query_description: str, includes_active_filtering: bool):
    """
    Validation helper to ensure metrics queries follow deactivation strategy.
    
    Args:
        query_description: Description of what the query does
        includes_active_filtering: Whether the query properly filters by active status at all levels
    
    Raises:
        ValueError: If query doesn't follow deactivation strategy
    """
    if not includes_active_filtering:
        raise ValueError(
            f"Metrics query '{query_description}' violates deactivation strategy. "
            "All metrics queries must filter by active status at ALL relationship levels. "
            "See docs/DEACTIVATION_STRATEGY.md for implementation guidelines."
        )


# Example usage patterns for common metrics scenarios
METRICS_EXAMPLES = {
    'workflow_distribution': """
        # Get issue distribution across workflow steps (active only)
        metrics = get_workflow_metrics(session, include_inactive=False)
        
        # Get workflow distribution including inactive chains (data quality view)
        quality_metrics = get_workflow_metrics(session, include_inactive=True)
    """,
    
    'custom_metrics': """
        # Custom metrics query following deactivation strategy
        from app.utils.metrics_helpers import validate_metrics_query
        
        # Your custom query here
        query = session.query(Issue).join(Status).join(StatusMapping).join(FlowStep).filter(
            and_(
                Issue.active == True,
                Status.active == True,
                StatusMapping.active == True,
                FlowStep.active == True,
                # Your additional filters here
            )
        )
        
        # Validate that query follows strategy
        validate_metrics_query("Custom workflow metrics", includes_active_filtering=True)
    """,
    
    'data_quality_check': """
        # Generate data quality report
        quality_report = get_data_quality_report(session)
        
        print(f"Data completeness: {quality_report['data_completeness_percentage']}%")
        print(f"Issues excluded from metrics: {quality_report['excluded_from_metrics']}")
    """
}
