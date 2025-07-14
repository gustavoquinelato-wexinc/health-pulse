"""
GitHub GraphQL Extractor
Handles the core logic for extracting PR data using GraphQL with nested pagination.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.core.logging_config import get_logger
from app.core.utils import DateTimeHelper
from app.models.unified_models import Repository, PullRequest, PullRequestReview, PullRequestCommit, PullRequestComment, Integration, JobSchedule
from app.jobs.github.github_graphql_client import GitHubGraphQLClient
from app.jobs.github.github_graphql_processor import GitHubGraphQLProcessor
from app.jobs.github.github_graphql_pagination import (
    paginate_commits, paginate_reviews, paginate_comments, paginate_review_threads, resume_pr_nested_pagination
)

logger = get_logger(__name__)


def process_repository_prs_with_graphql(session: Session, graphql_client: GitHubGraphQLClient, 
                                       repository: Repository, owner: str, repo_name: str,
                                       integration: Integration, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Process all pull requests for a repository using GraphQL.
    
    Args:
        session: Database session
        graphql_client: GraphQL client
        repository: Repository object
        owner: Repository owner
        repo_name: Repository name
        integration: GitHub integration
        job_schedule: Job schedule for checkpoint management
        
    Returns:
        Dictionary with processing results
    """
    try:
        logger.info(f"Processing PRs for {owner}/{repo_name} using GraphQL")
        
        processor = GitHubGraphQLProcessor(integration, repository.id)
        prs_processed = 0
        pr_cursor = None
        
        # Outer loop: Paginate through pull requests
        while True:
            # Check rate limit before making request and warn but continue
            if graphql_client.should_stop_for_rate_limit():
                logger.warning("Rate limit threshold reached during PR processing, but continuing")
            
            # Fetch batch of PRs with nested data
            response = graphql_client.get_pull_requests_with_details(owner, repo_name, pr_cursor)
            
            if not response or 'data' not in response:
                logger.error(f"Failed to fetch PR data for {owner}/{repo_name}")
                return {
                    'success': False,
                    'error': 'Failed to fetch PR data from GraphQL',
                    'prs_processed': prs_processed,
                    'checkpoint_data': {}
                }
            
            repository_data = response['data']['repository']
            if not repository_data:
                logger.warning(f"Repository {owner}/{repo_name} not found or not accessible")
                break
            
            pull_requests = repository_data['pullRequests']
            pr_nodes = pull_requests['nodes']
            
            if not pr_nodes:
                logger.info(f"No more PRs to process for {owner}/{repo_name}")
                break
            
            logger.info(f"Processing batch of {len(pr_nodes)} PRs")
            
            # Process each PR in the batch
            for pr_node in pr_nodes:
                try:
                    # Process the main PR data
                    pr_result = process_single_pr_with_nested_data(
                        session, graphql_client, pr_node, repository, processor, job_schedule
                    )
                    
                    if not pr_result['success']:
                        return {
                            'success': False,
                            'error': pr_result['error'],
                            'prs_processed': prs_processed,
                            'checkpoint_data': {
                                'last_pr_cursor': pr_cursor,
                                'current_pr_node_id': pr_node['id'],
                                **pr_result.get('checkpoint_data', {})
                            }
                        }
                    
                    prs_processed += 1
                    
                    # Log progress every 10 PRs
                    if prs_processed % 10 == 0:
                        logger.info(f"Processed {prs_processed} PRs so far...")

                except Exception as e:
                    logger.error(f"Error processing PR #{pr_node.get('number', 'unknown')}: {e}")
                    continue

            # Check if there are more pages
            page_info = pull_requests['pageInfo']
            if not page_info['hasNextPage']:
                logger.info(f"Completed processing all PRs for {owner}/{repo_name}")
                break

            pr_cursor = page_info['endCursor']
            logger.debug(f"Moving to next page with cursor: {pr_cursor}")

        logger.info(f"Repository {owner}/{repo_name} completed: {prs_processed} PRs processed")
        return {
            'success': True,
            'prs_processed': prs_processed
        }
        
    except Exception as e:
        logger.error(f"Error processing repository {owner}/{repo_name}: {e}")
        return {
            'success': False,
            'error': str(e),
            'prs_processed': prs_processed,
            'checkpoint_data': {}
        }


def process_repository_prs_with_graphql_recovery(session: Session, graphql_client: GitHubGraphQLClient, 
                                                repository: Repository, owner: str, repo_name: str,
                                                integration: Integration, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Process pull requests for a repository using GraphQL in recovery mode.
    
    Args:
        session: Database session
        graphql_client: GraphQL client
        repository: Repository object
        owner: Repository owner
        repo_name: Repository name
        integration: GitHub integration
        job_schedule: Job schedule with checkpoint data
        
    Returns:
        Dictionary with processing results
    """
    try:
        logger.info(f"Processing PRs for {owner}/{repo_name} using GraphQL (RECOVERY MODE)")

        processor = GitHubGraphQLProcessor(integration, repository.id)
        checkpoint_state = job_schedule.get_checkpoint_state()

        prs_processed = 0
        pr_cursor = checkpoint_state['last_pr_cursor']
        current_pr_node_id = checkpoint_state['current_pr_node_id']

        logger.info(f"Resuming from PR cursor: {pr_cursor}, current PR: {current_pr_node_id}")

        # If we have a current PR being processed, resume its nested pagination
        if current_pr_node_id:
            logger.info(f"Resuming nested pagination for PR: {current_pr_node_id}")
            
            # Resume processing the specific PR that was interrupted
            resume_result = resume_pr_nested_pagination(
                session, graphql_client, current_pr_node_id, repository, processor, job_schedule
            )
            
            if not resume_result['success']:
                return {
                    'success': False,
                    'error': resume_result['error'],
                    'prs_processed': 0,
                    'checkpoint_data': {
                        'last_pr_cursor': pr_cursor,
                        'current_pr_node_id': current_pr_node_id,
                        **resume_result.get('checkpoint_data', {})
                    }
                }
            
            prs_processed += 1
            logger.info(f"Resumed PR {current_pr_node_id} completed")

        # Continue with normal processing from the saved cursor
        while True:
            # Check rate limit before making request and warn but continue
            if graphql_client.should_stop_for_rate_limit():
                logger.warning("Rate limit threshold reached during recovery, but continuing")
            
            # Fetch batch of PRs with nested data
            response = graphql_client.get_pull_requests_with_details(owner, repo_name, pr_cursor)
            
            if not response or 'data' not in response:
                logger.error(f"Failed to fetch PR data for {owner}/{repo_name}")
                return {
                    'success': False,
                    'error': 'Failed to fetch PR data from GraphQL',
                    'prs_processed': prs_processed,
                    'checkpoint_data': {}
                }

            repository_data = response['data']['repository']
            if not repository_data:
                logger.warning(f"Repository {owner}/{repo_name} not found or not accessible")
                break

            pull_requests = repository_data['pullRequests']
            pr_nodes = pull_requests['nodes']

            if not pr_nodes:
                logger.info(f"No more PRs to process for {owner}/{repo_name}")
                break

            logger.info(f"Processing batch of {len(pr_nodes)} PRs (recovery mode)")
            
            # Process each PR in the batch
            for pr_node in pr_nodes:
                try:
                    # Skip the PR we already resumed (if any)
                    if current_pr_node_id and pr_node['id'] == current_pr_node_id:
                        current_pr_node_id = None  # Clear it so we don't skip others
                        continue
                    
                    # Process the main PR data
                    pr_result = process_single_pr_with_nested_data(
                        session, graphql_client, pr_node, repository, processor, job_schedule
                    )
                    
                    if not pr_result['success']:
                        return {
                            'success': False,
                            'error': pr_result['error'],
                            'prs_processed': prs_processed,
                            'checkpoint_data': {
                                'last_pr_cursor': pr_cursor,
                                'current_pr_node_id': pr_node['id'],
                                **pr_result.get('checkpoint_data', {})
                            }
                        }
                    
                    prs_processed += 1
                    
                except Exception as e:
                    logger.error(f"Error processing PR #{pr_node.get('number', 'unknown')}: {e}")
                    continue

            # Check if there are more pages
            page_info = pull_requests['pageInfo']
            if not page_info['hasNextPage']:
                logger.info(f"Completed recovery processing for {owner}/{repo_name}")
                break

            pr_cursor = page_info['endCursor']

        logger.info(f"Repository {owner}/{repo_name} recovery completed: {prs_processed} PRs processed")
        return {
            'success': True,
            'prs_processed': prs_processed
        }
        
    except Exception as e:
        logger.error(f"Error in recovery processing for {owner}/{repo_name}: {e}")
        return {
            'success': False,
            'error': str(e),
            'prs_processed': prs_processed,
            'checkpoint_data': {}
        }


def process_single_pr_with_nested_data(session: Session, graphql_client: GitHubGraphQLClient,
                                      pr_node: Dict[str, Any], repository: Repository,
                                      processor: GitHubGraphQLProcessor, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Process a single PR with all its nested data (commits, reviews, comments).

    Args:
        session: Database session
        graphql_client: GraphQL client
        pr_node: PR node from GraphQL response
        repository: Repository object
        processor: GraphQL processor
        job_schedule: Job schedule for checkpoint management

    Returns:
        Dictionary with processing results
    """
    try:
        pr_number = pr_node.get('number')
        pr_node_id = pr_node.get('id')

        logger.debug(f"Processing PR #{pr_number} (ID: {pr_node_id})")

        # Process main PR data
        pr_data = processor.process_pull_request_node(pr_node)
        if not pr_data:
            return {
                'success': False,
                'error': f'Failed to process PR #{pr_number} data',
                'checkpoint_data': {}
            }

        # Check if PR already exists
        existing_pr = session.query(PullRequest).filter(
            PullRequest.external_id == str(pr_number),
            PullRequest.repository_id == repository.id
        ).first()

        if existing_pr:
            # Update existing PR
            for key, value in pr_data.items():
                if key not in ['id', 'created_at']:  # Don't update these fields
                    setattr(existing_pr, key, value)
            pull_request = existing_pr
        else:
            # Create new PR
            pull_request = PullRequest(**pr_data)
            session.add(pull_request)

        session.flush()  # Get the PR ID

        # Process nested data with pagination
        nested_result = process_pr_nested_data(
            session, graphql_client, pr_node, pull_request.id, processor, job_schedule
        )

        if not nested_result['success']:
            return {
                'success': False,
                'error': nested_result['error'],
                'checkpoint_data': nested_result.get('checkpoint_data', {})
            }

        # Note: session.commit() is now handled at the repository level
        # session.commit()

        logger.debug(f"PR #{pr_number} processed successfully")
        return {
            'success': True
        }

    except Exception as e:
        logger.error(f"Error processing PR #{pr_node.get('number', 'unknown')}: {e}")
        session.rollback()
        return {
            'success': False,
            'error': str(e),
            'checkpoint_data': {}
        }


def process_pr_nested_data(session: Session, graphql_client: GitHubGraphQLClient,
                          pr_node: Dict[str, Any], pull_request_id: int,
                          processor: GitHubGraphQLProcessor, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Process nested data for a PR (commits, reviews, comments) with pagination.

    Args:
        session: Database session
        graphql_client: GraphQL client
        pr_node: PR node from GraphQL response
        pull_request_id: Database ID of the pull request
        processor: GraphQL processor
        job_schedule: Job schedule for checkpoint management

    Returns:
        Dictionary with processing results
    """
    try:
        pr_node_id = pr_node['id']

        # Process first page of commits
        commits_data = pr_node.get('commits', {})
        if commits_data.get('nodes'):
            commits = processor.process_commit_nodes(commits_data['nodes'], pull_request_id)
            session.add_all(commits)

        # Handle commits pagination if needed
        if commits_data.get('pageInfo', {}).get('hasNextPage'):
            commit_result = paginate_commits(
                session, graphql_client, pr_node_id, commits_data['pageInfo']['endCursor'],
                pull_request_id, processor
            )
            if not commit_result['success']:
                return {
                    'success': False,
                    'error': commit_result['error'],
                    'checkpoint_data': {
                        'last_commit_cursor': commits_data['pageInfo']['endCursor']
                    }
                }

        # Process first page of reviews
        reviews_data = pr_node.get('reviews', {})
        if reviews_data.get('nodes'):
            reviews = processor.process_review_nodes(reviews_data['nodes'], pull_request_id)
            session.add_all(reviews)

        # Handle reviews pagination if needed
        if reviews_data.get('pageInfo', {}).get('hasNextPage'):
            review_result = paginate_reviews(
                session, graphql_client, pr_node_id, reviews_data['pageInfo']['endCursor'],
                pull_request_id, processor
            )
            if not review_result['success']:
                return {
                    'success': False,
                    'error': review_result['error'],
                    'checkpoint_data': {
                        'last_review_cursor': reviews_data['pageInfo']['endCursor']
                    }
                }

        # Process first page of comments
        comments_data = pr_node.get('comments', {})
        if comments_data.get('nodes'):
            comments = processor.process_comment_nodes(comments_data['nodes'], pull_request_id, 'issue')
            session.add_all(comments)

        # Handle comments pagination if needed
        if comments_data.get('pageInfo', {}).get('hasNextPage'):
            comment_result = paginate_comments(
                session, graphql_client, pr_node_id, comments_data['pageInfo']['endCursor'],
                pull_request_id, processor
            )
            if not comment_result['success']:
                return {
                    'success': False,
                    'error': comment_result['error'],
                    'checkpoint_data': {
                        'last_comment_cursor': comments_data['pageInfo']['endCursor']
                    }
                }

        # Process first page of review threads
        review_threads_data = pr_node.get('reviewThreads', {})
        if review_threads_data.get('nodes'):
            review_comments = processor.process_review_thread_nodes(review_threads_data['nodes'], pull_request_id)
            session.add_all(review_comments)

        # Handle review threads pagination if needed
        if review_threads_data.get('pageInfo', {}).get('hasNextPage'):
            thread_result = paginate_review_threads(
                session, graphql_client, pr_node_id, review_threads_data['pageInfo']['endCursor'],
                pull_request_id, processor
            )
            if not thread_result['success']:
                return {
                    'success': False,
                    'error': thread_result['error'],
                    'checkpoint_data': {
                        'last_review_thread_cursor': review_threads_data['pageInfo']['endCursor']
                    }
                }

        return {
            'success': True
        }

    except Exception as e:
        logger.error(f"Error processing nested data for PR {pr_node.get('number', 'unknown')}: {e}")
        return {
            'success': False,
            'error': str(e),
            'checkpoint_data': {}
        }
