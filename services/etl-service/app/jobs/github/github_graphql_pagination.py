"""
GitHub GraphQL Pagination Helpers
Handles nested pagination for commits, reviews, comments, and review threads.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.core.logging_config import get_logger
from app.jobs.github.github_graphql_client import GitHubGraphQLTenant
from app.jobs.github.github_graphql_processor import GitHubGraphQLProcessor
from app.models.unified_models import Pr

logger = get_logger(__name__)


def paginate_commits(session: Session, graphql_client: GitHubGraphQLTenant, pr_node_id: str,
                    cursor: str, pull_request_id: int, processor: GitHubGraphQLProcessor) -> Dict[str, Any]:
    """
    Paginate through additional commits for a PR.
    
    Args:
        session: Database session
        graphql_client: GraphQL client
        pr_node_id: PR node ID
        cursor: Starting cursor
        pull_request_id: Database PR ID
        processor: GraphQL processor
        
    Returns:
        Dictionary with pagination results
    """
    try:
        logger.debug(f"Paginating commits for PR {pr_node_id}")

        while cursor:
            # Check rate limit
            if graphql_client.is_rate_limited():
                logger.warning(f"Rate limit reached during commit pagination for PR {pr_node_id}")
                return {
                    'success': False,
                    'error': 'Rate limit reached during commit pagination',
                    'last_cursor': cursor
                }

            # Fetch next page of commits
            response = graphql_client.get_more_commits_for_pr(pr_node_id, cursor)

            if not response or 'data' not in response:
                logger.error(f"Failed to fetch additional commits for PR {pr_node_id}")
                return {
                    'success': False,
                    'error': 'Failed to fetch additional commits',
                    'last_cursor': cursor
                }

            node_data = response['data']['node']
            if not node_data or 'commits' not in node_data:
                logger.warning(f"No commit data found for PR {pr_node_id}")
                break

            commits_data = node_data['commits']
            commit_nodes = commits_data.get('nodes', [])

            if commit_nodes:
                commits = processor.process_commit_nodes(commit_nodes, pull_request_id)
                session.add_all(commits)
                logger.debug(f"Added {len(commits)} commits")

            # Check if there are more pages
            page_info = commits_data.get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                logger.debug(f"Completed commit pagination for PR {pr_node_id}")
                break
            
            cursor = page_info.get('endCursor')
        
        return {
            'success': True
        }
        
    except Exception as e:
        logger.error(f"❌ Error paginating commits for PR {pr_node_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'last_cursor': cursor
        }


def paginate_reviews(session: Session, graphql_client: GitHubGraphQLTenant, pr_node_id: str,
                    cursor: str, pull_request_id: int, processor: GitHubGraphQLProcessor) -> Dict[str, Any]:
    """
    Paginate through additional reviews for a PR.
    
    Args:
        session: Database session
        graphql_client: GraphQL client
        pr_node_id: PR node ID
        cursor: Starting cursor
        pull_request_id: Database PR ID
        processor: GraphQL processor
        
    Returns:
        Dictionary with pagination results
    """
    try:
        logger.debug(f"🔄 Paginating reviews for PR {pr_node_id}")
        
        while cursor:
            # Check rate limit
            if graphql_client.is_rate_limited():
                logger.warning(f"Rate limit reached during review pagination for PR {pr_node_id}")
                return {
                    'success': False,
                    'error': 'Rate limit reached during review pagination',
                    'last_cursor': cursor
                }
            
            # Fetch next page of reviews
            response = graphql_client.get_more_reviews_for_pr(pr_node_id, cursor)
            
            if not response or 'data' not in response:
                logger.error(f"❌ Failed to fetch additional reviews for PR {pr_node_id}")
                return {
                    'success': False,
                    'error': 'Failed to fetch additional reviews',
                    'last_cursor': cursor
                }
            
            node_data = response['data']['node']
            if not node_data or 'reviews' not in node_data:
                logger.warning(f"⚠️ No review data found for PR {pr_node_id}")
                break
            
            reviews_data = node_data['reviews']
            review_nodes = reviews_data.get('nodes', [])
            
            if review_nodes:
                reviews = processor.process_review_nodes(review_nodes, pull_request_id)
                session.add_all(reviews)
                logger.debug(f"📝 Added {len(reviews)} reviews")
            
            # Check if there are more pages
            page_info = reviews_data.get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                logger.debug(f"✅ Completed review pagination for PR {pr_node_id}")
                break
            
            cursor = page_info.get('endCursor')
        
        return {
            'success': True
        }
        
    except Exception as e:
        logger.error(f"❌ Error paginating reviews for PR {pr_node_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'last_cursor': cursor
        }


def paginate_comments(session: Session, graphql_client: GitHubGraphQLTenant, pr_node_id: str,
                     cursor: str, pull_request_id: int, processor: GitHubGraphQLProcessor) -> Dict[str, Any]:
    """
    Paginate through additional comments for a PR.
    
    Args:
        session: Database session
        graphql_client: GraphQL client
        pr_node_id: PR node ID
        cursor: Starting cursor
        pull_request_id: Database PR ID
        processor: GraphQL processor
        
    Returns:
        Dictionary with pagination results
    """
    try:
        logger.debug(f"🔄 Paginating comments for PR {pr_node_id}")
        
        while cursor:
            # Check rate limit
            if graphql_client.is_rate_limited():
                logger.warning("⚠️ Rate limit reached during comment pagination")
                return {
                    'success': False,
                    'error': 'Rate limit reached',
                    'last_cursor': cursor
                }
            
            # Fetch next page of comments
            response = graphql_client.get_more_comments_for_pr(pr_node_id, cursor)
            
            if not response or 'data' not in response:
                logger.error(f"❌ Failed to fetch additional comments for PR {pr_node_id}")
                return {
                    'success': False,
                    'error': 'Failed to fetch additional comments',
                    'last_cursor': cursor
                }
            
            node_data = response['data']['node']
            if not node_data or 'comments' not in node_data:
                logger.warning(f"⚠️ No comment data found for PR {pr_node_id}")
                break
            
            comments_data = node_data['comments']
            comment_nodes = comments_data.get('nodes', [])
            
            if comment_nodes:
                comments = processor.process_comment_nodes(comment_nodes, pull_request_id, 'issue')
                session.add_all(comments)
                logger.debug(f"📝 Added {len(comments)} comments")
            
            # Check if there are more pages
            page_info = comments_data.get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                logger.debug(f"✅ Completed comment pagination for PR {pr_node_id}")
                break
            
            cursor = page_info.get('endCursor')
        
        return {
            'success': True
        }
        
    except Exception as e:
        logger.error(f"❌ Error paginating comments for PR {pr_node_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'last_cursor': cursor
        }


def paginate_review_threads(session: Session, graphql_client: GitHubGraphQLTenant, pr_node_id: str,
                           cursor: str, pull_request_id: int, processor: GitHubGraphQLProcessor) -> Dict[str, Any]:
    """
    Paginate through additional review threads for a PR.
    
    Args:
        session: Database session
        graphql_client: GraphQL client
        pr_node_id: PR node ID
        cursor: Starting cursor
        pull_request_id: Database PR ID
        processor: GraphQL processor
        
    Returns:
        Dictionary with pagination results
    """
    try:
        logger.debug(f"🔄 Paginating review threads for PR {pr_node_id}")
        
        while cursor:
            # Check rate limit
            if graphql_client.is_rate_limited():
                logger.warning(f"Rate limit reached during review thread pagination for PR {pr_node_id}")
                return {
                    'success': False,
                    'error': 'Rate limit reached during review thread pagination',
                    'last_cursor': cursor
                }
            
            # Fetch next page of review threads
            response = graphql_client.get_more_review_threads_for_pr(pr_node_id, cursor)
            
            if not response or 'data' not in response:
                logger.error(f"❌ Failed to fetch additional review threads for PR {pr_node_id}")
                return {
                    'success': False,
                    'error': 'Failed to fetch additional review threads',
                    'last_cursor': cursor
                }
            
            node_data = response['data']['node']
            if not node_data or 'reviewThreads' not in node_data:
                logger.warning(f"⚠️ No review thread data found for PR {pr_node_id}")
                break
            
            threads_data = node_data['reviewThreads']
            thread_nodes = threads_data.get('nodes', [])
            
            if thread_nodes:
                review_comments = processor.process_review_thread_nodes(thread_nodes, pull_request_id)
                session.add_all(review_comments)
                logger.debug(f"📝 Added {len(review_comments)} review thread comments")
            
            # Check if there are more pages
            page_info = threads_data.get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                logger.debug(f"✅ Completed review thread pagination for PR {pr_node_id}")
                break
            
            cursor = page_info.get('endCursor')
        
        return {
            'success': True
        }
        
    except Exception as e:
        logger.error(f"❌ Error paginating review threads for PR {pr_node_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'last_cursor': cursor
        }


def resume_pr_nested_pagination(session: Session, graphql_client: GitHubGraphQLTenant, pr_node_id: str,
                               repository, processor: GitHubGraphQLProcessor, job_schedule) -> Dict[str, Any]:
    """
    Resume nested pagination for a specific PR that was interrupted.
    
    Args:
        session: Database session
        graphql_client: GraphQL client
        pr_node_id: PR node ID to resume
        repository: Repository object
        processor: GraphQL processor
        job_schedule: Job schedule with checkpoint data
        
    Returns:
        Dictionary with resume results
    """
    try:
        logger.info(f"🔄 Resuming nested pagination for PR {pr_node_id}")
        
        checkpoint_state = job_schedule.get_checkpoint_state()
        
        # Find the PR in database
        pr_number = pr_node_id.split('_')[-1] if '_' in pr_node_id else None
        pull_request = session.query(Pr).filter(
            Pr.repository_id == repository.id,
            Pr.external_id == pr_number
        ).first() if pr_number else None
        
        if not pull_request:
            logger.error(f"❌ PR {pr_node_id} not found in database")
            return {
                'success': False,
                'error': f'PR {pr_node_id} not found in database',
                'checkpoint_data': {}
            }
        
        # Resume each type of nested pagination based on saved cursors
        if checkpoint_state.get('last_commit_cursor'):
            logger.info(f"🔄 Resuming commit pagination from cursor: {checkpoint_state['last_commit_cursor']}")
            commit_result = paginate_commits(
                session, graphql_client, pr_node_id, checkpoint_state['last_commit_cursor'],
                pull_request.id, processor
            )
            if not commit_result['success']:
                return {
                    'success': False,
                    'error': commit_result['error'],
                    'checkpoint_data': {
                        'last_commit_cursor': commit_result.get('last_cursor')
                    }
                }
        
        if checkpoint_state.get('last_review_cursor'):
            logger.info(f"🔄 Resuming review pagination from cursor: {checkpoint_state['last_review_cursor']}")
            review_result = paginate_reviews(
                session, graphql_client, pr_node_id, checkpoint_state['last_review_cursor'],
                pull_request.id, processor
            )
            if not review_result['success']:
                return {
                    'success': False,
                    'error': review_result['error'],
                    'checkpoint_data': {
                        'last_review_cursor': review_result.get('last_cursor')
                    }
                }
        
        if checkpoint_state.get('last_comment_cursor'):
            logger.info(f"🔄 Resuming comment pagination from cursor: {checkpoint_state['last_comment_cursor']}")
            comment_result = paginate_comments(
                session, graphql_client, pr_node_id, checkpoint_state['last_comment_cursor'],
                pull_request.id, processor
            )
            if not comment_result['success']:
                return {
                    'success': False,
                    'error': comment_result['error'],
                    'checkpoint_data': {
                        'last_comment_cursor': comment_result.get('last_cursor')
                    }
                }
        
        if checkpoint_state.get('last_review_thread_cursor'):
            logger.info(f"🔄 Resuming review thread pagination from cursor: {checkpoint_state['last_review_thread_cursor']}")
            thread_result = paginate_review_threads(
                session, graphql_client, pr_node_id, checkpoint_state['last_review_thread_cursor'],
                pull_request.id, processor
            )
            if not thread_result['success']:
                return {
                    'success': False,
                    'error': thread_result['error'],
                    'checkpoint_data': {
                        'last_review_thread_cursor': thread_result.get('last_cursor')
                    }
                }
        
        # Note: session.commit() is now handled at the repository level
        # session.commit()
        logger.info(f"Successfully resumed nested pagination for PR {pr_node_id}")
        
        return {
            'success': True
        }
        
    except Exception as e:
        logger.error(f"❌ Error resuming nested pagination for PR {pr_node_id}: {e}")
        session.rollback()
        return {
            'success': False,
            'error': str(e),
            'checkpoint_data': {}
        }
