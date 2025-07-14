"""
GitHub Integration Package for ETL Service.

This package provides GitHub API integration capabilities including:
- Repository extraction and management
- Pull request data extraction with enhanced metrics using GraphQL
- Review and commit analysis with nested pagination
- Cross-integration with Jira development data

Main Components:
- GitHubGraphQLClient: GraphQL API client for efficient data fetching
- GitHubGraphQLProcessor: Data transformation and processing for GraphQL responses
- GitHubClient: REST API client (kept for testing and legacy compatibility)
"""

from .github_client import GitHubClient  # Keep for testing
from .github_graphql_client import GitHubGraphQLClient
from .github_graphql_processor import GitHubGraphQLProcessor
from .github_graphql_extractor import (
    process_repository_prs_with_graphql,
    process_repository_prs_with_graphql_recovery
)

__all__ = [
    'GitHubClient',  # Legacy REST client for testing
    'GitHubGraphQLClient',
    'GitHubGraphQLProcessor',
    'process_repository_prs_with_graphql',
    'process_repository_prs_with_graphql_recovery'
]
