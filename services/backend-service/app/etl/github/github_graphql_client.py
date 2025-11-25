"""
GitHub GraphQL Client for Backend Service ETL
Handles GraphQL requests to GitHub API for PR extraction with nested data.
"""

import requests
import time
from typing import Dict, Any, Optional
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class GitHubRateLimitException(Exception):
    """Custom exception for GitHub API rate limit exceeded."""
    def __init__(self, message: str, reset_at: Optional[str] = None):
        super().__init__(message)
        self.reset_at = reset_at


class GitHubGraphQLClient:
    """Client for GitHub GraphQL API interactions with cursor-based pagination."""
    
    def __init__(self, token: str, db_session=None, batch_size: int = 50):
        """
        Initialize GitHub GraphQL client.

        Args:
            token: GitHub personal access token
            db_session: Optional database session for connection heartbeat
            batch_size: Number of items to fetch per page (default: 50)
        """
        self.token = token
        self.db_session = db_session
        self.batch_size = batch_size
        self.graphql_url = "https://api.github.com/graphql"
        self.rate_limit_remaining = 5000
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
        """Check if we have hit the rate limit."""
        return self.rate_limit_remaining <= 0

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

        # 🐛 DEBUG: Log the variables being sent
        logger.info(f"🔍 [GRAPHQL] Variables being sent: {variables}")

        for attempt in range(max_retries):
            try:
                if self.is_rate_limited():
                    logger.warning(f"GraphQL rate limit reached: {self.rate_limit_remaining} points remaining")

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
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        return None

                return response_data
                
            except requests.exceptions.RequestException as e:
                is_server_error = (
                    hasattr(e, 'response') and e.response is not None and
                    e.response.status_code in [502, 503, 504]
                )

                if is_server_error:
                    logger.warning(f"GitHub server error (attempt {attempt + 1}/{max_retries}): {e}")
                else:
                    logger.warning(f"GraphQL request failed (attempt {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    backoff_time = (2 ** attempt) * (3 if is_server_error else 1)
                    logger.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                else:
                    logger.error(f"Failed to make GraphQL request after {max_retries} attempts")
                    return None
        
        return None

    async def get_pull_requests_with_details(self, owner: str, repo_name: str, pr_cursor: str = None) -> Optional[Dict[str, Any]]:
        """
        Fetch a batch of pull requests with all nested data using GraphQL.

        Args:
            owner: Repository owner
            repo_name: Repository name
            pr_cursor: Cursor for pagination

        Returns:
            GraphQL response with pull requests and nested data
        """
        query = f"""
        query getPrBatchWithDetails(
          $owner: String!,
          $repoName: String!,
          $prCursor: String
        ) {{
          rateLimit {{
            remaining
            resetAt
          }}
          repository(owner: $owner, name: $repoName) {{
            pullRequests(first: {self.batch_size}, after: $prCursor, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
              pageInfo {{
                endCursor
                hasNextPage
              }}
              nodes {{
                id
                number
                title
                body
                state
                createdAt
                updatedAt
                mergedAt
                author {{
                  login
                }}
                commits(first: {self.batch_size}) {{
                  pageInfo {{
                    endCursor
                    hasNextPage
                  }}
                  nodes {{
                    commit {{
                      oid
                      message
                      author {{
                        name
                        email
                        date
                      }}
                    }}
                  }}
                }}
                reviews(first: {self.batch_size}) {{
                  pageInfo {{
                    endCursor
                    hasNextPage
                  }}
                  nodes {{
                    id
                    state
                    author {{
                      login
                    }}
                    createdAt
                  }}
                }}
                comments(first: {self.batch_size}) {{
                  pageInfo {{
                    endCursor
                    hasNextPage
                  }}
                  nodes {{
                    id
                    body
                    author {{
                      login
                    }}
                    createdAt
                  }}
                }}
                reviewThreads(first: {self.batch_size}) {{
                  pageInfo {{
                    endCursor
                    hasNextPage
                  }}
                  nodes {{
                    id
                    isResolved
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        
        variables = {
            'owner': owner,
            'repoName': repo_name,
            'prCursor': pr_cursor
        }

        return self._make_graphql_request(query, variables)

    async def get_more_commits_for_pr(self, pr_node_id: str, commit_cursor: str = None) -> Optional[Dict[str, Any]]:
        """Fetch additional commits for a specific pull request."""
        query = f"""
        query getMoreCommitsForPr(
          $prNodeId: ID!,
          $commitCursor: String
        ) {{
          rateLimit {{
            remaining
            resetAt
          }}
          node(id: $prNodeId) {{
            ... on PullRequest {{
              commits(first: {self.batch_size}, after: $commitCursor) {{
                pageInfo {{
                  endCursor
                  hasNextPage
                }}
                nodes {{
                  commit {{
                    oid
                    message
                    author {{
                      name
                      email
                      date
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        
        variables = {
            'prNodeId': pr_node_id,
            'commitCursor': commit_cursor
        }

        return self._make_graphql_request(query, variables)

    async def get_more_reviews_for_pr(self, pr_node_id: str, review_cursor: str = None) -> Optional[Dict[str, Any]]:
        """Fetch additional reviews for a specific pull request."""
        query = f"""
        query getMoreReviewsForPr(
          $prNodeId: ID!,
          $reviewCursor: String
        ) {{
          rateLimit {{
            remaining
            resetAt
          }}
          node(id: $prNodeId) {{
            ... on PullRequest {{
              reviews(first: {self.batch_size}, after: $reviewCursor) {{
                pageInfo {{
                  endCursor
                  hasNextPage
                }}
                nodes {{
                  id
                  state
                  author {{
                    login
                  }}
                  createdAt
                }}
              }}
            }}
          }}
        }}
        """
        
        variables = {
            'prNodeId': pr_node_id,
            'reviewCursor': review_cursor
        }

        return self._make_graphql_request(query, variables)

    async def get_more_comments_for_pr(self, pr_node_id: str, comment_cursor: str = None) -> Optional[Dict[str, Any]]:
        """Fetch additional comments for a specific pull request."""
        query = f"""
        query getMoreCommentsForPr(
          $prNodeId: ID!,
          $commentCursor: String
        ) {{
          rateLimit {{
            remaining
            resetAt
          }}
          node(id: $prNodeId) {{
            ... on PullRequest {{
              comments(first: {self.batch_size}, after: $commentCursor) {{
                pageInfo {{
                  endCursor
                  hasNextPage
                }}
                nodes {{
                  id
                  body
                  author {{
                    login
                  }}
                  createdAt
                }}
              }}
            }}
          }}
        }}
        """
        
        variables = {
            'prNodeId': pr_node_id,
            'commentCursor': comment_cursor
        }

        return self._make_graphql_request(query, variables)

    async def get_more_review_threads_for_pr(self, pr_node_id: str, thread_cursor: str = None) -> Optional[Dict[str, Any]]:
        """Fetch additional review threads for a specific pull request."""
        query = f"""
        query getMoreReviewThreadsForPr(
          $prNodeId: ID!,
          $threadCursor: String
        ) {{
          rateLimit {{
            remaining
            resetAt
          }}
          node(id: $prNodeId) {{
            ... on PullRequest {{
              reviewThreads(first: {self.batch_size}, after: $threadCursor) {{
                pageInfo {{
                  endCursor
                  hasNextPage
                }}
                nodes {{
                  id
                  isResolved
                }}
              }}
            }}
          }}
        }}
        """

        variables = {
            'prNodeId': pr_node_id,
            'threadCursor': thread_cursor
        }

        return self._make_graphql_request(query, variables)

