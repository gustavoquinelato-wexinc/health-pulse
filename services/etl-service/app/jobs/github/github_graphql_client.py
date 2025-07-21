"""
GitHub GraphQL Client for efficient data fetching with cursor-based pagination.
Replaces multiple REST API calls with single GraphQL queries.
"""

import requests
import time
from typing import Dict, Any, Optional, List
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class GitHubRateLimitException(Exception):
    """Custom exception for GitHub API rate limit exceeded."""
    pass


class GitHubGraphQLClient:
    """Client for GitHub GraphQL API interactions with cursor-based pagination."""
    
    def __init__(self, token: str):
        """
        Initialize GitHub GraphQL client.

        Args:
            token: GitHub personal access token
        """
        self.token = token
        self.graphql_url = "https://api.github.com/graphql"
        self.rate_limit_remaining = 5000  # Default GitHub GraphQL limit
        self.rate_limit_reset = None

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'User-Agent': 'ETL-Service/1.0'
        })

    def _update_rate_limit_info(self, response_data: Dict[str, Any]):
        """Update rate limit information from GraphQL response."""
        if 'data' in response_data and 'rateLimit' in response_data['data']:
            rate_limit = response_data['data']['rateLimit']
            self.rate_limit_remaining = rate_limit.get('remaining', self.rate_limit_remaining)
            self.rate_limit_reset = rate_limit.get('resetAt')
            logger.debug(f"GraphQL rate limit updated: {self.rate_limit_remaining} points remaining")

    def is_rate_limited(self) -> bool:
        """Check if we have hit the rate limit (0 remaining points)."""
        return self.rate_limit_remaining <= 0

    def check_rate_limit_before_request(self):
        """Check rate limit before making a request and log info if rate limited."""
        if self.is_rate_limited():
            logger.warning(f"GraphQL rate limit reached: {self.rate_limit_remaining} points remaining")
            logger.warning("Consider implementing checkpoint-based recovery in the calling function")

    def _make_graphql_request(self, query: str, variables: Dict[str, Any] = None, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Make a GraphQL request with retry logic.
        
        Args:
            query: GraphQL query string
            variables: Query variables
            max_retries: Maximum number of retries
            
        Returns:
            GraphQL response data or None if failed
        """
        payload = {
            'query': query,
            'variables': variables or {}
        }
        
        for attempt in range(max_retries):
            try:
                # Check rate limit before making request
                self.check_rate_limit_before_request()

                logger.debug(f"Making GitHub GraphQL request (attempt {attempt + 1})")
                response = self.session.post(self.graphql_url, json=payload, timeout=30)

                response.raise_for_status()
                response_data = response.json()

                # Update rate limit info from response
                self._update_rate_limit_info(response_data)

                # Check for GraphQL errors
                if 'errors' in response_data:
                    errors = response_data['errors']
                    error_messages = [error.get('message', 'Unknown error') for error in errors]
                    
                    # Check for rate limit errors
                    for error in errors:
                        if 'rate limit' in error.get('message', '').lower():
                            logger.warning("GraphQL rate limit exceeded - stopping gracefully")
                            raise GitHubRateLimitException(f"GitHub GraphQL API rate limit exceeded: {error['message']}")
                    
                    logger.error(f"GraphQL errors: {error_messages}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        return None

                return response_data
                
            except requests.exceptions.RequestException as e:
                # Check if this is a server error that might be temporary
                is_server_error = (
                    hasattr(e, 'response') and e.response is not None and
                    e.response.status_code in [502, 503, 504]  # Bad Gateway, Service Unavailable, Gateway Timeout
                )

                if is_server_error:
                    logger.warning(f"GitHub server error (attempt {attempt + 1}/{max_retries}): {e}")
                    logger.warning("This appears to be a temporary GitHub API server issue")
                else:
                    logger.warning(f"GraphQL request failed (attempt {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    # Use longer backoff for server errors
                    backoff_time = (2 ** attempt) * (3 if is_server_error else 1)
                    logger.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                else:
                    if is_server_error:
                        logger.error(f"GitHub API servers appear to be experiencing issues after {max_retries} attempts")
                        logger.error("This is likely a temporary GitHub service outage. Please try again later.")
                    else:
                        logger.error(f"Failed to make GraphQL request after {max_retries} attempts")
                    return None
        
        return None

    def get_pull_requests_with_details(self, owner: str, repo_name: str, pr_cursor: str = None) -> Optional[Dict[str, Any]]:
        """
        Fetch a batch of pull requests with all nested data using GraphQL.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            pr_cursor: Cursor for pagination
            
        Returns:
            GraphQL response with pull requests and nested data
        """
        query = """
        query getPullRequestBatchWithDetails(
          $owner: String!, 
          $repoName: String!, 
          $prCursor: String
        ) {
          rateLimit {
            remaining
            resetAt
          }
          repository(owner: $owner, name: $repoName) {
            pullRequests(
              first: 100,
              after: $prCursor,
              orderBy: {field: UPDATED_AT, direction: DESC}  # DESC for early termination optimization
            ) {
              pageInfo {
                endCursor
                hasNextPage
              }
              nodes {
                id
                number
                title
                state
                author { login }
                body
                createdAt
                updatedAt
                mergedAt
                closedAt
                mergedBy { login }
                additions
                deletions
                changedFiles
                url
                
                commits(first: 100) {
                  totalCount
                  pageInfo { endCursor, hasNextPage }
                  nodes {
                    commit {
                      oid
                      author { name, email, date }
                      committer { name, email, date }
                      message
                    }
                  }
                }
                
                reviews(first: 100) {
                  totalCount
                  pageInfo { endCursor, hasNextPage }
                  nodes {
                    id
                    author { login }
                    state
                    body
                    submittedAt
                  }
                }
                
                comments(first: 100) {
                  totalCount
                  pageInfo { endCursor, hasNextPage }
                  nodes {
                    id
                    author { login }
                    body
                    createdAt
                    updatedAt
                  }
                }
                
                reviewThreads(first: 50) {
                  pageInfo { endCursor, hasNextPage }
                  nodes {
                    comments(first: 10) {
                      pageInfo { endCursor, hasNextPage }
                      nodes {
                        id
                        author { login }
                        body
                        path
                        position
                        createdAt
                        updatedAt
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            'owner': owner,
            'repoName': repo_name,
            'prCursor': pr_cursor
        }
        
        logger.debug(f"Fetching PR batch for {owner}/{repo_name} with cursor: {pr_cursor}")
        return self._make_graphql_request(query, variables)

    def get_more_commits_for_pr(self, pr_node_id: str, commit_cursor: str = None) -> Optional[Dict[str, Any]]:
        """
        Fetch additional commits for a specific pull request.
        
        Args:
            pr_node_id: GraphQL node ID of the pull request
            commit_cursor: Cursor for pagination
            
        Returns:
            GraphQL response with additional commits
        """
        query = """
        query getMoreCommitsForPullRequest(
          $prNodeId: ID!, 
          $commitCursor: String
        ) {
          rateLimit {
            remaining
            resetAt
          }
          node(id: $prNodeId) {
            ... on PullRequest {
              commits(first: 100, after: $commitCursor) {
                pageInfo {
                  endCursor
                  hasNextPage
                }
                nodes {
                  commit {
                    oid
                    author { name, email, date }
                    committer { name, email, date }
                    message
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            'prNodeId': pr_node_id,
            'commitCursor': commit_cursor
        }
        
        logger.debug(f"Fetching additional commits for PR {pr_node_id} with cursor: {commit_cursor}")
        return self._make_graphql_request(query, variables)

    def get_more_reviews_for_pr(self, pr_node_id: str, review_cursor: str = None) -> Optional[Dict[str, Any]]:
        """
        Fetch additional reviews for a specific pull request.

        Args:
            pr_node_id: GraphQL node ID of the pull request
            review_cursor: Cursor for pagination

        Returns:
            GraphQL response with additional reviews
        """
        query = """
        query getMoreReviewsForPullRequest(
          $prNodeId: ID!,
          $reviewCursor: String
        ) {
          rateLimit {
            remaining
            resetAt
          }
          node(id: $prNodeId) {
            ... on PullRequest {
              reviews(first: 100, after: $reviewCursor) {
                pageInfo {
                  endCursor
                  hasNextPage
                }
                nodes {
                  id
                  author { login }
                  state
                  body
                  submittedAt
                }
              }
            }
          }
        }
        """

        variables = {
            'prNodeId': pr_node_id,
            'reviewCursor': review_cursor
        }

        logger.debug(f"Fetching additional reviews for PR {pr_node_id} with cursor: {review_cursor}")
        return self._make_graphql_request(query, variables)

    def get_more_comments_for_pr(self, pr_node_id: str, comment_cursor: str = None) -> Optional[Dict[str, Any]]:
        """
        Fetch additional comments for a specific pull request.

        Args:
            pr_node_id: GraphQL node ID of the pull request
            comment_cursor: Cursor for pagination

        Returns:
            GraphQL response with additional comments
        """
        query = """
        query getMoreCommentsForPullRequest(
          $prNodeId: ID!,
          $commentCursor: String
        ) {
          rateLimit {
            remaining
            resetAt
          }
          node(id: $prNodeId) {
            ... on PullRequest {
              comments(first: 100, after: $commentCursor) {
                pageInfo {
                  endCursor
                  hasNextPage
                }
                nodes {
                  id
                  author { login }
                  body
                  createdAt
                  updatedAt
                }
              }
            }
          }
        }
        """

        variables = {
            'prNodeId': pr_node_id,
            'commentCursor': comment_cursor
        }

        logger.debug(f"Fetching additional comments for PR {pr_node_id} with cursor: {comment_cursor}")
        return self._make_graphql_request(query, variables)

    def get_more_review_threads_for_pr(self, pr_node_id: str, review_thread_cursor: str = None) -> Optional[Dict[str, Any]]:
        """
        Fetch additional review threads for a specific pull request.

        Args:
            pr_node_id: GraphQL node ID of the pull request
            review_thread_cursor: Cursor for pagination

        Returns:
            GraphQL response with additional review threads
        """
        query = """
        query getMoreReviewThreadsForPullRequest(
          $prNodeId: ID!,
          $reviewThreadCursor: String
        ) {
          rateLimit {
            remaining
            resetAt
          }
          node(id: $prNodeId) {
            ... on PullRequest {
              reviewThreads(first: 50, after: $reviewThreadCursor) {
                pageInfo {
                  endCursor
                  hasNextPage
                }
                nodes {
                  comments(first: 10) {
                    pageInfo { endCursor, hasNextPage }
                    nodes {
                      id
                      author { login }
                      body
                      path
                      position
                      createdAt
                      updatedAt
                    }
                  }
                }
              }
            }
          }
        }
        """

        variables = {
            'prNodeId': pr_node_id,
            'reviewThreadCursor': review_thread_cursor
        }

        logger.debug(f"Fetching additional review threads for PR {pr_node_id} with cursor: {review_thread_cursor}")
        return self._make_graphql_request(query, variables)
