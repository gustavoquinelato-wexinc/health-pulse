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
    Process all pull requests for a repository using GraphQL with bulk inserts.

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

        # Check if we're resuming from a previous cursor (recovery mode)
        checkpoint_state = job_schedule.get_checkpoint_state()
        pr_cursor = checkpoint_state.get('last_pr_cursor')  # Use saved cursor or None for fresh start

        if pr_cursor:
            logger.info(f"Resuming PR processing from cursor: {pr_cursor}")
        else:
            logger.info("Starting fresh PR processing (no saved cursor)")

        # Bulk insert collections
        bulk_prs = []
        bulk_commits = []
        bulk_reviews = []
        bulk_comments = []

        # Batch size for bulk operations
        BATCH_SIZE = 50
        
        # Outer loop: Paginate through pull requests
        while True:
            # Check rate limit before making request and abort if needed
            if graphql_client.should_stop_for_rate_limit():
                logger.warning("Rate limit threshold reached during PR processing, aborting to save state")
                # Save current state before aborting
                job_schedule.update_checkpoint({
                    'last_pr_cursor': pr_cursor,
                    'current_pr_node_id': None,
                    'last_commit_cursor': None,
                    'last_review_cursor': None,
                    'last_comment_cursor': None,
                    'last_review_thread_cursor': None
                })
                logger.info(f"Saved checkpoint: repo_id={repository.external_id}, pr_cursor={pr_cursor}")
                return {
                    'success': True,
                    'prs_processed': prs_processed,
                    'rate_limit_reached': True,
                    'partial_success': True,
                    'message': f'Rate limit reached, processed {prs_processed} PRs, state saved'
                }
            
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
            
            # Process each PR in the batch and collect data for bulk insert
            for pr_node in pr_nodes:
                try:
                    # Process the main PR data
                    pr_result = process_single_pr_for_bulk_insert(
                        pr_node, repository, processor, bulk_prs, bulk_commits, bulk_reviews, bulk_comments
                    )

                    if not pr_result['success']:
                        # Before failing, save any collected data
                        if bulk_prs or bulk_commits or bulk_reviews or bulk_comments:
                            perform_bulk_inserts(session, bulk_prs, bulk_commits, bulk_reviews, bulk_comments)

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

                    # Perform bulk insert when batch is full
                    if len(bulk_prs) >= BATCH_SIZE:
                        perform_bulk_inserts(session, bulk_prs, bulk_commits, bulk_reviews, bulk_comments)
                        bulk_prs.clear()
                        bulk_commits.clear()
                        bulk_reviews.clear()
                        bulk_comments.clear()

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

        # Final bulk insert for remaining data
        if bulk_prs or bulk_commits or bulk_reviews or bulk_comments:
            perform_bulk_inserts(session, bulk_prs, bulk_commits, bulk_reviews, bulk_comments)
            logger.info(f"Final bulk insert completed for {owner}/{repo_name}")

        logger.info(f"Repository {owner}/{repo_name} completed: {prs_processed} PRs processed")

        # Clear PR-level checkpoints for this repository since it's completed
        # Note: Repository-level queue management is handled in the main job function
        job_schedule.update_checkpoint({
            'last_pr_cursor': None,  # Clear cursor to indicate completion
            'current_pr_node_id': None,
            'last_commit_cursor': None,
            'last_review_cursor': None,
            'last_comment_cursor': None,
            'last_review_thread_cursor': None
        })
        logger.debug(f"Cleared PR-level checkpoints for completed repository {repository.external_id}")

        return {
            'success': True,
            'rate_limit_reached': False,
            'partial_success': False,
            'prs_processed': prs_processed
        }
        
    except Exception as e:
        logger.error(f"Error processing repository {owner}/{repo_name}: {e}")

        # Check if this is a rate limit error
        is_rate_limit_error = 'rate limit' in str(e).lower()

        return {
            'success': False,
            'rate_limit_reached': is_rate_limit_error,
            'partial_success': False,
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
            # Check rate limit before making request and abort if needed
            if graphql_client.should_stop_for_rate_limit():
                logger.warning("Rate limit threshold reached during recovery, aborting to save state")
                # Save current state before aborting
                job_schedule.update_checkpoint({
                    'last_pr_cursor': pr_cursor,
                    'current_pr_node_id': None,
                    'last_commit_cursor': None,
                    'last_review_cursor': None,
                    'last_comment_cursor': None,
                    'last_review_thread_cursor': None
                })
                logger.info(f"Saved checkpoint: repo_id={repository.external_id}, pr_cursor={pr_cursor}")
                return {
                    'success': True,
                    'prs_processed': prs_processed,
                    'rate_limit_reached': True,
                    'partial_success': True,
                    'message': f'Rate limit reached during recovery, processed {prs_processed} PRs, state saved'
                }
            
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

        # Clear PR-level checkpoints for this repository since recovery is completed
        job_schedule.update_checkpoint({
            'last_pr_cursor': None,  # Clear cursor to indicate completion
            'current_pr_node_id': None,
            'last_commit_cursor': None,
            'last_review_cursor': None,
            'last_comment_cursor': None,
            'last_review_thread_cursor': None
        })
        logger.debug(f"Cleared checkpoint for completed recovery of repository {repository.external_id}")

        return {
            'success': True,
            'rate_limit_reached': False,
            'partial_success': False,
            'prs_processed': prs_processed
        }
        
    except Exception as e:
        logger.error(f"Error in recovery processing for {owner}/{repo_name}: {e}")

        # Check if this is a rate limit error
        is_rate_limit_error = 'rate limit' in str(e).lower()

        return {
            'success': False,
            'rate_limit_reached': is_rate_limit_error,
            'partial_success': False,
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


def process_single_pr_for_bulk_insert(pr_node: Dict[str, Any], repository: Repository,
                                     processor: GitHubGraphQLProcessor, bulk_prs: list,
                                     bulk_commits: list, bulk_reviews: list, bulk_comments: list) -> Dict[str, Any]:
    """
    Process a single PR and collect data for bulk insert.

    Args:
        pr_node: PR node data from GraphQL
        repository: Repository object
        processor: GraphQL processor
        bulk_prs: List to collect PR data
        bulk_commits: List to collect commit data
        bulk_reviews: List to collect review data
        bulk_comments: List to collect comment data

    Returns:
        Dictionary with processing results
    """
    try:
        pr_number = pr_node.get('number')
        pr_node_id = pr_node.get('id')

        logger.debug(f"Processing PR #{pr_number} (ID: {pr_node_id}) for bulk insert")

        # Process main PR data
        pr_data = processor.process_pull_request_node(pr_node)
        if not pr_data:
            return {
                'success': False,
                'error': f'Failed to process PR #{pr_number} data'
            }

        # Add to bulk PR collection
        bulk_prs.append(pr_data)

        # Process nested data and add to bulk collections
        # Process commits
        commits_data = pr_node.get('commits', {})
        if commits_data.get('nodes'):
            commits = processor.process_commit_nodes(commits_data['nodes'], None)  # PR ID will be set later
            for commit in commits:
                commit_dict = {
                    'external_id': commit.external_id,
                    'pull_request_external_id': str(pr_number),  # Use PR number for linking
                    'repository_id': repository.id,
                    'author_name': commit.author_name,
                    'author_email': commit.author_email,
                    'committer_name': commit.committer_name,
                    'committer_email': commit.committer_email,
                    'message': commit.message,
                    'authored_date': commit.authored_date,
                    'committed_date': commit.committed_date,
                    'client_id': commit.client_id,
                    'active': commit.active,
                    'created_at': commit.created_at,
                    'last_updated_at': commit.last_updated_at
                }
                bulk_commits.append(commit_dict)

        # Process reviews
        reviews_data = pr_node.get('reviews', {})
        if reviews_data.get('nodes'):
            reviews = processor.process_review_nodes(reviews_data['nodes'], None)  # PR ID will be set later
            for review in reviews:
                review_dict = {
                    'external_id': review.external_id,
                    'pull_request_external_id': str(pr_number),  # Use PR number for linking
                    'author_login': review.author_login,
                    'state': review.state,
                    'body': review.body,
                    'submitted_at': review.submitted_at,
                    'client_id': review.client_id,
                    'active': review.active,
                    'created_at': review.created_at,
                    'last_updated_at': review.last_updated_at
                }
                bulk_reviews.append(review_dict)

        # Process comments
        comments_data = pr_node.get('comments', {})
        if comments_data.get('nodes'):
            comments = processor.process_comment_nodes(comments_data['nodes'], None, 'issue')  # PR ID will be set later
            for comment in comments:
                comment_dict = {
                    'external_id': comment.external_id,
                    'pull_request_external_id': str(pr_number),  # Use PR number for linking
                    'author_login': comment.author_login,
                    'body': comment.body,
                    'comment_type': comment.comment_type,
                    'created_at_github': comment.created_at_github,
                    'updated_at_github': comment.updated_at_github,
                    'client_id': comment.client_id,
                    'active': comment.active,
                    'created_at': comment.created_at,
                    'last_updated_at': comment.last_updated_at
                }
                bulk_comments.append(comment_dict)

        # Process review threads (review comments)
        review_threads_data = pr_node.get('reviewThreads', {})
        if review_threads_data.get('nodes'):
            review_comments = processor.process_review_thread_nodes(review_threads_data['nodes'], None)  # PR ID will be set later
            for comment in review_comments:
                comment_dict = {
                    'external_id': comment.external_id,
                    'pull_request_external_id': str(pr_number),  # Use PR number for linking
                    'author_login': comment.author_login,
                    'body': comment.body,
                    'comment_type': comment.comment_type,
                    'created_at_github': comment.created_at_github,
                    'updated_at_github': comment.updated_at_github,
                    'client_id': comment.client_id,
                    'active': comment.active,
                    'created_at': comment.created_at,
                    'last_updated_at': comment.last_updated_at
                }
                bulk_comments.append(comment_dict)

        return {
            'success': True
        }

    except Exception as e:
        logger.error(f"Error processing PR #{pr_node.get('number', 'unknown')} for bulk insert: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def perform_bulk_inserts(session: Session, bulk_prs: list, bulk_commits: list,
                        bulk_reviews: list, bulk_comments: list):
    """
    Perform bulk inserts for all collected data.

    Args:
        session: Database session
        bulk_prs: List of PR data dictionaries
        bulk_commits: List of commit data dictionaries
        bulk_reviews: List of review data dictionaries
        bulk_comments: List of comment data dictionaries
    """
    try:
        from app.models.unified_models import PullRequest, PullRequestCommit, PullRequestReview, PullRequestComment

        # Bulk insert PRs first
        if bulk_prs:
            logger.info(f"Bulk inserting {len(bulk_prs)} pull requests...")
            session.bulk_insert_mappings(PullRequest, bulk_prs)
            session.flush()  # Ensure PRs are inserted before nested data

        # Now we need to get the PR IDs for the nested data
        # We'll update the nested data with actual PR IDs
        if bulk_commits or bulk_reviews or bulk_comments:
            # Get PR mappings (external_id -> database id)
            pr_external_ids = [str(pr['external_id']) for pr in bulk_prs]
            if pr_external_ids:
                pr_mappings = {}
                prs_from_db = session.query(PullRequest.id, PullRequest.external_id).filter(
                    PullRequest.external_id.in_(pr_external_ids)
                ).all()
                for pr_id, external_id in prs_from_db:
                    pr_mappings[external_id] = pr_id

                # Update commits with actual PR IDs
                for commit in bulk_commits:
                    pr_external_id = commit.pop('pull_request_external_id')
                    commit['pull_request_id'] = pr_mappings.get(pr_external_id)

                # Update reviews with actual PR IDs
                for review in bulk_reviews:
                    pr_external_id = review.pop('pull_request_external_id')
                    review['pull_request_id'] = pr_mappings.get(pr_external_id)

                # Update comments with actual PR IDs
                for comment in bulk_comments:
                    pr_external_id = comment.pop('pull_request_external_id')
                    comment['pull_request_id'] = pr_mappings.get(pr_external_id)

        # Bulk insert nested data
        if bulk_commits:
            logger.info(f"Bulk inserting {len(bulk_commits)} commits...")
            session.bulk_insert_mappings(PullRequestCommit, bulk_commits)

        if bulk_reviews:
            logger.info(f"Bulk inserting {len(bulk_reviews)} reviews...")
            session.bulk_insert_mappings(PullRequestReview, bulk_reviews)

        if bulk_comments:
            logger.info(f"Bulk inserting {len(bulk_comments)} comments...")
            session.bulk_insert_mappings(PullRequestComment, bulk_comments)

        logger.info(f"Bulk insert completed: {len(bulk_prs)} PRs, {len(bulk_commits)} commits, {len(bulk_reviews)} reviews, {len(bulk_comments)} comments")

    except Exception as e:
        logger.error(f"Error performing bulk inserts: {e}")
        raise
