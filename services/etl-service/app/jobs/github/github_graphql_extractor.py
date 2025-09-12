"""
GitHub GraphQL Extractor
Handles the core logic for extracting PR data using GraphQL with nested pagination.
"""

import asyncio
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.core.logging_config import get_logger
from app.core.utils import DateTimeHelper
from app.core.websocket_manager import get_websocket_manager
from app.models.unified_models import Repository, Pr, PrReview, PrCommit, PrComment, Integration, JobSchedule
from app.jobs.github.github_graphql_client import GitHubGraphQLClient, GitHubRateLimitException
from app.jobs.github.github_graphql_processor import GitHubGraphQLProcessor
from app.jobs.github.github_graphql_pagination import (
    paginate_commits, paginate_reviews, paginate_comments, paginate_review_threads, resume_pr_nested_pagination
)
from app.clients.ai_client import bulk_store_entity_vectors_for_etl, bulk_update_entity_vectors_for_etl
from app.jobs.vectorization_helper import VectorizationQueueHelper

logger = get_logger(__name__)


async def process_repository_prs_with_graphql(session: Session, graphql_client: GitHubGraphQLClient,
                                       repository: Repository, owner: str, repo_name: str,
                                       integration: Integration, job_schedule: JobSchedule,
                                       websocket_manager=None) -> Dict[str, Any]:
    """
    Process pull requests for a repository using GraphQL with bulk inserts and early termination.

    Uses DESC ordering by updatedAt and stops when encountering PRs older than job_schedule.last_success_at
    for optimal efficiency. Only processes new/updated PRs since last sync.

    Args:
        session: Database session
        graphql_client: GraphQL client
        repository: Repository object
        owner: Repository owner
        repo_name: Repository name
        integration: GitHub integration (for configuration)
        job_schedule: Job schedule for checkpoint management

    Returns:
        Dictionary with processing results
    """
    try:
        logger.info(f"Processing PRs for {owner}/{repo_name} using GraphQL")

        # Get WebSocket manager if not provided
        if websocket_manager is None:
            websocket_manager = get_websocket_manager()

        processor = GitHubGraphQLProcessor(integration, repository.id)
        prs_processed = 0

        # Initialize vectorization queue helper
        from app.core.config import get_backend_url
        backend_url = get_backend_url()
        vectorization_helper = VectorizationQueueHelper(integration.tenant_id, backend_url)

        # Get last sync timestamp for early termination (DESC ordering optimization)
        # Use job_schedule.last_success_at instead of integration.last_sync_at
        last_sync_at = job_schedule.last_success_at
        if last_sync_at:
            logger.info(f"Using job_schedule.last_success_at for early termination: {last_sync_at}")
        else:
            logger.info("No last_sync_at found - will process all PRs")

        # Check if we're resuming from a previous cursor (recovery mode)
        checkpoint_state = job_schedule.get_checkpoint_state()
        pr_cursor = checkpoint_state.get('last_pr_cursor')  # Use saved cursor or None for fresh start

        if pr_cursor:
            logger.info(f"[{owner}/{repo_name}] Resuming PR processing from cursor: {pr_cursor}")
        else:
            logger.info(f"[{owner}/{repo_name}] Starting fresh PR processing (no saved cursor)")

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
            if graphql_client.is_rate_limited():
                logger.warning(f"Rate limit reached during PR processing for {owner}/{repo_name}, aborting to save state")
                # Save current state before aborting (pr_cursor is the next page to fetch)
                job_schedule.update_checkpoint({
                    'last_pr_cursor': pr_cursor,
                    'current_pr_node_id': None,
                    'last_commit_cursor': None,
                    'last_review_cursor': None,
                    'last_comment_cursor': None,
                    'last_review_thread_cursor': None
                })
                logger.info(f"[{owner}/{repo_name}] Rate limit checkpoint saved: next_cursor={pr_cursor}, processed={prs_processed} PRs")
                return {
                    'success': True,
                    'prs_processed': prs_processed,
                    'rate_limit_reached': True,
                    'partial_success': True,
                    'message': f'Rate limit reached, processed {prs_processed} PRs for {owner}/{repo_name}, state saved'
                }
            
            # Fetch batch of PRs with nested data
            from app.core.settings_manager import get_github_graphql_batch_size
            batch_size = get_github_graphql_batch_size()
            logger.info(f"[{owner}/{repo_name}] Fetching PR batch (size: {batch_size}) with cursor: {pr_cursor or 'None (first page)'}")

            import time
            start_time = time.time()

            # Make GraphQL call with yielding to prevent UI blocking
            response = graphql_client.get_pull_requests_with_details(owner, repo_name, pr_cursor)

            # Yield control after API call to prevent UI blocking
            import asyncio
            await asyncio.sleep(0)

            request_time = time.time() - start_time
            logger.info(f"[{owner}/{repo_name}] GraphQL request completed in {request_time:.2f}s")
            
            if not response or 'data' not in response:
                logger.error(f"Failed to fetch PR data for {owner}/{repo_name}")
                logger.info(f"[{owner}/{repo_name}] Saving checkpoint: processed {prs_processed} PRs, cursor: {pr_cursor}")

                # Save checkpoint data for recovery
                job_schedule.update_checkpoint({
                    'last_pr_cursor': pr_cursor,
                    'current_pr_node_id': None,
                    'last_commit_cursor': None,
                    'last_review_cursor': None,
                    'last_comment_cursor': None,
                    'last_review_thread_cursor': None
                })

                return {
                    'success': False,
                    'error': f'GitHub API connection failed for {owner}/{repo_name}. This may be due to network issues, API outage, or repository access permissions.',
                    'prs_processed': prs_processed,
                    'checkpoint_data': {
                        'last_pr_cursor': pr_cursor,
                        'prs_processed_before_failure': prs_processed
                    }
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
            
            logger.info(f"[{owner}/{repo_name}] Processing batch of {len(pr_nodes)} PRs (total processed so far: {prs_processed})")
            
            # Process each PR in the batch and collect data for bulk insert
            for pr_node in pr_nodes:
                try:
                    # Early termination optimization: Check if PR is older than last_sync_at
                    if last_sync_at:
                        pr_updated_at_str = pr_node.get('updatedAt')
                        if pr_updated_at_str:
                            try:
                                pr_updated_at = DateTimeHelper.parse_iso_datetime(pr_updated_at_str)
                                # Remove timezone info for comparison if needed
                                if last_sync_at.tzinfo is None and pr_updated_at.tzinfo is not None:
                                    pr_updated_at = pr_updated_at.replace(tzinfo=None)
                                elif last_sync_at.tzinfo is not None and pr_updated_at.tzinfo is None:
                                    pr_updated_at = pr_updated_at.replace(tzinfo=last_sync_at.tzinfo)

                                # If PR is older than last sync, we can stop (DESC ordering)
                                if pr_updated_at < last_sync_at:
                                    logger.info(f"Early termination: PR #{pr_node.get('number')} updated at {pr_updated_at} is older than last_sync_at {last_sync_at}")
                                    logger.info(f"Stopping PR processing for {owner}/{repo_name} - processed {prs_processed} PRs")

                                    # Perform any pending bulk inserts before stopping
                                    if bulk_prs or bulk_commits or bulk_reviews or bulk_comments:
                                        perform_bulk_inserts(session, bulk_prs, bulk_commits, bulk_reviews, bulk_comments)
                                        session.commit()

                                    # Clear checkpoint since we completed successfully
                                    job_schedule.update_checkpoint({})

                                    return {
                                        'success': True,
                                        'prs_processed': prs_processed,
                                        'rate_limit_reached': False,
                                        'partial_success': False,
                                        'message': f'Early termination: processed {prs_processed} PRs, stopped at PR older than last_sync_at'
                                    }
                            except Exception as e:
                                logger.warning(f"Error parsing PR updatedAt '{pr_updated_at_str}': {e}")
                                # Continue processing if date parsing fails

                    # Process the main PR data
                    pr_result = process_single_pr_for_bulk_insert(
                        pr_node, repository, processor, bulk_prs, bulk_commits, bulk_reviews, bulk_comments
                    )

                    if not pr_result['success']:
                        # Before failing, save any collected data
                        if bulk_prs or bulk_commits or bulk_reviews or bulk_comments:
                            perform_bulk_inserts(session, bulk_prs, bulk_commits, bulk_reviews, bulk_comments, f"{owner}/{repo_name}")

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
                        bulk_result = perform_bulk_inserts(session, bulk_prs, bulk_commits, bulk_reviews, bulk_comments, f"{owner}/{repo_name}")

                        # Queue entities for async vectorization
                        if bulk_result:
                            # Queue PRs
                            if bulk_result.get("prs_inserted"):
                                vectorization_helper.queue_entities_for_vectorization(
                                    bulk_result.get("prs_inserted", []), "prs", "insert"
                                )
                            if bulk_result.get("prs_updated"):
                                vectorization_helper.queue_entities_for_vectorization(
                                    bulk_result.get("prs_updated", []), "prs", "update"
                                )

                            # Queue commits
                            if bulk_result.get("commits_inserted"):
                                vectorization_helper.queue_entities_for_vectorization(
                                    bulk_result.get("commits_inserted", []), "prs_commits", "insert"
                                )

                            # Queue reviews
                            if bulk_result.get("reviews_inserted"):
                                vectorization_helper.queue_entities_for_vectorization(
                                    bulk_result.get("reviews_inserted", []), "prs_reviews", "insert"
                                )

                            # Queue comments
                            if bulk_result.get("comments_inserted"):
                                vectorization_helper.queue_entities_for_vectorization(
                                    bulk_result.get("comments_inserted", []), "prs_comments", "insert"
                                )

                        bulk_prs.clear()
                        bulk_commits.clear()
                        bulk_reviews.clear()
                        bulk_comments.clear()

                        # Yield control after bulk operations to prevent UI blocking
                        await asyncio.sleep(0.01)  # 10ms yield

                    # Yield control after each PR to keep UI responsive
                    if prs_processed % 5 == 0:  # Yield every 5 PRs instead of 10
                        await asyncio.sleep(0.003)  # 3ms yield

                    # Log progress every 10 PRs
                    if prs_processed % 10 == 0:
                        logger.info(f"[{owner}/{repo_name}] Processed {prs_processed} PRs so far...")

                    # Yield control every 3 PRs to prevent UI blocking
                    if prs_processed % 3 == 0:
                        await asyncio.sleep(0)  # Yield control to prevent blocking

                except Exception as e:
                    logger.error(f"[{owner}/{repo_name}] Error processing PR #{pr_node.get('number', 'unknown')}: {e}")
                    continue

            # Check if there are more pages
            page_info = pull_requests['pageInfo']
            if not page_info['hasNextPage']:
                logger.info(f"[{owner}/{repo_name}] Completed processing all PRs - no more pages")
                break

            prev_cursor = pr_cursor
            pr_cursor = page_info['endCursor']
            logger.info(f"[{owner}/{repo_name}] Page completed, moving to next page: prev_cursor={prev_cursor} -> next_cursor={pr_cursor}")

            # Yield control between pages to keep UI responsive
            await asyncio.sleep(0.02)  # 20ms yield between pages

        # Final bulk insert for remaining data
        if bulk_prs or bulk_commits or bulk_reviews or bulk_comments:
            bulk_result = perform_bulk_inserts(session, bulk_prs, bulk_commits, bulk_reviews, bulk_comments, f"{owner}/{repo_name}")
            logger.info(f"[{owner}/{repo_name}] Final bulk insert completed")

            # Queue final entities for async vectorization
            if bulk_result:
                # Queue PRs
                if bulk_result.get("prs_inserted"):
                    vectorization_helper.queue_entities_for_vectorization(
                        bulk_result.get("prs_inserted", []), "prs", "insert"
                    )
                if bulk_result.get("prs_updated"):
                    vectorization_helper.queue_entities_for_vectorization(
                        bulk_result.get("prs_updated", []), "prs", "update"
                    )

                # Queue commits
                if bulk_result.get("commits_inserted"):
                    vectorization_helper.queue_entities_for_vectorization(
                        bulk_result.get("commits_inserted", []), "prs_commits", "insert"
                    )

                # Queue reviews
                if bulk_result.get("reviews_inserted"):
                    vectorization_helper.queue_entities_for_vectorization(
                        bulk_result.get("reviews_inserted", []), "prs_reviews", "insert"
                    )

                # Queue comments
                if bulk_result.get("comments_inserted"):
                    vectorization_helper.queue_entities_for_vectorization(
                        bulk_result.get("comments_inserted", []), "prs_comments", "insert"
                    )

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

        # Note: Entities are now saved immediately during extraction steps
        # Vectorization will be triggered at the job level after all repositories are processed
        logger.info(f"[{owner}/{repo_name}] All entities saved to vectorization queue during extraction")

        except Exception as e:
            logger.error(f"[{owner}/{repo_name}] Failed to trigger async vectorization: {e}")
            # Don't fail the entire job if vectorization queueing fails

        return {
            'success': True,
            'rate_limit_reached': False,
            'partial_success': False,
            'prs_processed': prs_processed
        }
        
    except GitHubRateLimitException as e:
        logger.warning(f"Rate limit reached while processing repository {owner}/{repo_name}: {e}")

        # Save current state before returning (rate limit checkpoint)
        job_schedule.update_checkpoint({
            'last_pr_cursor': pr_cursor,
            'current_pr_node_id': None,
            'last_commit_cursor': None,
            'last_review_cursor': None,
            'last_comment_cursor': None,
            'last_review_thread_cursor': None
        })
        logger.info(f"[{owner}/{repo_name}] Rate limit checkpoint saved: cursor={pr_cursor}, processed={prs_processed} PRs")

        # Rate limit is a partial success - we processed what we could
        return {
            'success': True,  # Partial success
            'rate_limit_reached': True,
            'partial_success': True,
            'error': str(e),
            'prs_processed': prs_processed,
            'checkpoint_data': {
                'last_pr_cursor': pr_cursor,
                'current_pr_node_id': None,
                'last_commit_cursor': None,
                'last_review_cursor': None,
                'last_comment_cursor': None,
                'last_review_thread_cursor': None
            }
        }

    except Exception as e:
        logger.error(f"Error processing repository {owner}/{repo_name}: {e}")

        return {
            'success': False,
            'rate_limit_reached': False,
            'partial_success': False,
            'error': str(e),
            'prs_processed': prs_processed,
            'checkpoint_data': {}
        }


async def process_repository_prs_with_graphql_recovery(session: Session, graphql_client: GitHubGraphQLClient,
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

        # Get last sync timestamp for early termination (DESC ordering optimization)
        # Use job_schedule.last_success_at instead of integration.last_sync_at
        last_sync_at = job_schedule.last_success_at
        if last_sync_at:
            logger.info(f"Using job_schedule.last_success_at for early termination in recovery: {last_sync_at}")
        else:
            logger.info("No last_success_at found - will process all PRs in recovery")

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
            if graphql_client.is_rate_limited():
                logger.warning("Rate limit reached during recovery, aborting to save state")
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
            
            # Fetch batch of PRs with nested data with yielding
            response = graphql_client.get_pull_requests_with_details(owner, repo_name, pr_cursor)

            # Yield control after API call to prevent UI blocking
            import asyncio
            await asyncio.sleep(0)
            
            if not response or 'data' not in response:
                logger.error(f"Failed to fetch PR data for {owner}/{repo_name}")
                return {
                    'success': False,
                    'error': f'GitHub API connection failed during recovery for {owner}/{repo_name}. Check network connectivity and repository permissions.',
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

                    # Early termination optimization: Check if PR is older than last_sync_at
                    if last_sync_at:
                        pr_updated_at_str = pr_node.get('updatedAt')
                        if pr_updated_at_str:
                            try:
                                pr_updated_at = DateTimeHelper.parse_iso_datetime(pr_updated_at_str)
                                # Remove timezone info for comparison if needed
                                if last_sync_at.tzinfo is None and pr_updated_at.tzinfo is not None:
                                    pr_updated_at = pr_updated_at.replace(tzinfo=None)
                                elif last_sync_at.tzinfo is not None and pr_updated_at.tzinfo is None:
                                    pr_updated_at = pr_updated_at.replace(tzinfo=last_sync_at.tzinfo)

                                # If PR is older than last sync, we can stop (DESC ordering)
                                if pr_updated_at < last_sync_at:
                                    logger.info(f"Early termination in recovery: PR #{pr_node.get('number')} updated at {pr_updated_at} is older than last_sync_at {last_sync_at}")
                                    logger.info(f"Stopping PR processing for {owner}/{repo_name} - processed {prs_processed} PRs")

                                    # Clear checkpoint since we completed successfully
                                    job_schedule.update_checkpoint({})
                                    session.commit()

                                    return {
                                        'success': True,
                                        'prs_processed': prs_processed,
                                        'rate_limit_reached': False,
                                        'partial_success': False,
                                        'message': f'Early termination in recovery: processed {prs_processed} PRs, stopped at PR older than last_sync_at'
                                    }
                            except Exception as e:
                                logger.warning(f"Error parsing PR updatedAt '{pr_updated_at_str}' in recovery: {e}")
                                # Continue processing if date parsing fails

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

        # Save current state if it's a rate limit error
        if is_rate_limit_error:
            job_schedule.update_checkpoint({
                'last_pr_cursor': pr_cursor,
                'current_pr_node_id': None,
                'last_commit_cursor': None,
                'last_review_cursor': None,
                'last_comment_cursor': None,
                'last_review_thread_cursor': None
            })
            logger.info(f"[{owner}/{repo_name}] Recovery rate limit checkpoint saved: cursor={pr_cursor}, processed={prs_processed} PRs")

        return {
            'success': False,
            'rate_limit_reached': is_rate_limit_error,
            'partial_success': False,
            'error': str(e),
            'prs_processed': prs_processed,
            'checkpoint_data': {
                'last_pr_cursor': pr_cursor if is_rate_limit_error else None,
                'current_pr_node_id': None,
                'last_commit_cursor': None,
                'last_review_cursor': None,
                'last_comment_cursor': None,
                'last_review_thread_cursor': None
            } if is_rate_limit_error else {}
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

        # Set the external_repo_id from the repository
        pr_data['external_repo_id'] = repository.external_id

        # Check if PR already exists
        existing_pr = session.query(Pr).filter(
            Pr.external_id == str(pr_number),
            Pr.repository_id == repository.id
        ).first()

        if existing_pr:
            # Update existing PR
            for key, value in pr_data.items():
                if key not in ['id', 'created_at']:  # Don't update these fields
                    setattr(existing_pr, key, value)
            pull_request = existing_pr
        else:
            # Create new PR - Phase 3-1 clean architecture
            try:
                pull_request = Pr(**pr_data)
                session.add(pull_request)
            except Exception as e:
                logger.error(f"❌ Error creating PR {pr_data.get('number', 'unknown')}: {e}")
                raise

        session.flush()  # Get the PR ID

        # Process nested data with pagination
        nested_result = process_pr_nested_data(
            session, graphql_client, pr_node, pull_request.id, processor, job_schedule
        )

        if not nested_result['success']:
            # Save checkpoint with current PR node ID and nested cursor data
            checkpoint_data = {
                'current_pr_node_id': pr_node['id'],
                **nested_result.get('checkpoint_data', {})
            }

            # Save to database immediately
            job_schedule.update_checkpoint(checkpoint_data)
            logger.warning(f"Saved nested pagination checkpoint for PR {pr_node['id']}: {checkpoint_data}")

            return {
                'success': False,
                'error': nested_result['error'],
                'checkpoint_data': checkpoint_data
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
                # Save checkpoint immediately for commit pagination failure
                checkpoint_data = {
                    'current_pr_node_id': pr_node_id,
                    'last_commit_cursor': commit_result.get('last_cursor', commits_data['pageInfo']['endCursor'])
                }
                job_schedule.update_checkpoint(checkpoint_data)
                logger.warning(f"Saved commit pagination checkpoint for PR {pr_node_id}: cursor={checkpoint_data['last_commit_cursor']}")

                return {
                    'success': False,
                    'error': commit_result['error'],
                    'checkpoint_data': checkpoint_data
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
                # Save checkpoint immediately for review pagination failure
                checkpoint_data = {
                    'current_pr_node_id': pr_node_id,
                    'last_review_cursor': review_result.get('last_cursor', reviews_data['pageInfo']['endCursor'])
                }
                job_schedule.update_checkpoint(checkpoint_data)
                logger.warning(f"Saved review pagination checkpoint for PR {pr_node_id}: cursor={checkpoint_data['last_review_cursor']}")

                return {
                    'success': False,
                    'error': review_result['error'],
                    'checkpoint_data': checkpoint_data
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
                # Save checkpoint immediately for review thread pagination failure
                checkpoint_data = {
                    'current_pr_node_id': pr_node_id,
                    'last_review_thread_cursor': thread_result.get('last_cursor', review_threads_data['pageInfo']['endCursor'])
                }
                job_schedule.update_checkpoint(checkpoint_data)
                logger.warning(f"Saved review thread pagination checkpoint for PR {pr_node_id}: cursor={checkpoint_data['last_review_thread_cursor']}")

                return {
                    'success': False,
                    'error': thread_result['error'],
                    'checkpoint_data': checkpoint_data
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
    Process a single PR and collect data for bulk UPSERT operations.

    Note: This function only collects data. The actual UPSERT logic (update existing PRs,
    delete+insert nested data) is handled in perform_bulk_inserts().

    Args:
        pr_node: PR node data from GraphQL
        repository: Repository object
        processor: GraphQL processor
        bulk_prs: List to collect PR data for UPSERT
        bulk_commits: List to collect commit data for delete+insert
        bulk_reviews: List to collect review data for delete+insert
        bulk_comments: List to collect comment data for delete+insert

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

        # Set the external_repo_id from the repository
        pr_data['external_repo_id'] = repository.external_id

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
                    'integration_id': getattr(processor.integration, 'id', None) if processor.integration else None,
                    'tenant_id': commit.tenant_id,
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
                    'integration_id': getattr(processor.integration, 'id', None) if processor.integration else None,
                    'tenant_id': review.tenant_id,
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
                    'integration_id': getattr(processor.integration, 'id', None) if processor.integration else None,
                    'tenant_id': comment.tenant_id,
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
                    'integration_id': getattr(processor.integration, 'id', None) if processor.integration else None,
                    'tenant_id': comment.tenant_id,
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
                        bulk_reviews: list, bulk_comments: list, repo_context: str = None) -> Dict[str, Any]:
    """
    Perform bulk UPSERT operations for all collected data.

    For PRs: UPSERT (update existing, insert new)
    For nested data: DELETE existing + INSERT new (full refresh approach)

    Args:
        session: Database session
        bulk_prs: List of PR data dictionaries
        bulk_commits: List of commit data dictionaries
        bulk_reviews: List of review data dictionaries
        bulk_comments: List of comment data dictionaries

    Returns:
        Dict with inserted/updated PR information for AI processing
    """
    try:
        from app.models.unified_models import Pr, PrCommit, PrReview, PrComment

        # Step 1: UPSERT PRs (update existing, insert new)
        if bulk_prs:
            context_prefix = f"[{repo_context}] " if repo_context else ""
            logger.info(f"{context_prefix}Processing {len(bulk_prs)} pull requests with UPSERT logic...")

            # Get external IDs of PRs being processed
            pr_external_ids = [pr['external_id'] for pr in bulk_prs]

            # Find existing PRs
            existing_prs = session.query(Pr).filter(
                Pr.external_id.in_(pr_external_ids),
                Pr.repository_id.in_([pr['repository_id'] for pr in bulk_prs])
            ).all()

            existing_pr_map = {(pr.external_id, pr.repository_id): pr for pr in existing_prs}

            prs_to_insert = []
            prs_to_update = []

            for pr_data in bulk_prs:
                key = (pr_data['external_id'], pr_data['repository_id'])
                if key in existing_pr_map:
                    # Update existing PR
                    existing_pr = existing_pr_map[key]
                    for field, value in pr_data.items():
                        if field not in ['id', 'created_at']:  # Don't update these fields
                            setattr(existing_pr, field, value)
                    prs_to_update.append(existing_pr)
                else:
                    # New PR to insert
                    prs_to_insert.append(pr_data)

            # Perform bulk operations
            try:
                if prs_to_insert:
                    logger.info(f"{context_prefix}Bulk inserting {len(prs_to_insert)} new PRs...")
                    session.bulk_insert_mappings(Pr, prs_to_insert)

                if prs_to_update:
                    logger.info(f"{context_prefix}Updated {len(prs_to_update)} existing PRs...")

                session.flush()  # Ensure PRs are processed before nested data
            except Exception as e:
                logger.error(f"{context_prefix}Error during PR bulk operations: {e}")
                session.rollback()
                raise  # Re-raise the exception to be handled by the calling function

        # Now we need to get the PR IDs for the nested data
        # We'll update the nested data with actual PR IDs
        if bulk_commits or bulk_reviews or bulk_comments:
            # Get PR mappings (external_id -> database id)
            pr_external_ids = [str(pr['external_id']) for pr in bulk_prs]
            if pr_external_ids:
                pr_mappings = {}
                prs_from_db = session.query(Pr.id, Pr.external_id).filter(
                    Pr.external_id.in_(pr_external_ids)
                ).all()
                for pr_id, external_id in prs_from_db:
                    pr_mappings[external_id] = pr_id

                # Update commits with actual PR IDs
                for commit in bulk_commits:
                    pr_external_id = commit.pop('pull_request_external_id')
                    commit['pr_id'] = pr_mappings.get(pr_external_id)

                # Update reviews with actual PR IDs
                for review in bulk_reviews:
                    pr_external_id = review.pop('pull_request_external_id')
                    review['pr_id'] = pr_mappings.get(pr_external_id)

                # Update comments with actual PR IDs
                for comment in bulk_comments:
                    pr_external_id = comment.pop('pull_request_external_id')
                    comment['pr_id'] = pr_mappings.get(pr_external_id)

                # DELETE existing nested data for full refresh approach
                pr_ids_to_clean = list(pr_mappings.values())
                if pr_ids_to_clean:
                    logger.info(f"{context_prefix}Cleaning existing nested data for {len(pr_ids_to_clean)} PRs...")

                    # Delete existing commits
                    deleted_commits = session.query(PrCommit).filter(
                        PrCommit.pr_id.in_(pr_ids_to_clean)
                    ).delete(synchronize_session=False)

                    # Delete existing reviews
                    deleted_reviews = session.query(PrReview).filter(
                        PrReview.pr_id.in_(pr_ids_to_clean)
                    ).delete(synchronize_session=False)

                    # Delete existing comments
                    deleted_comments = session.query(PrComment).filter(
                        PrComment.pr_id.in_(pr_ids_to_clean)
                    ).delete(synchronize_session=False)

                    logger.info(f"{context_prefix}Deleted existing data: {deleted_commits} commits, {deleted_reviews} reviews, {deleted_comments} comments")

        # Bulk insert nested data (fresh data after cleanup)
        context_prefix = f"[{repo_context}] " if repo_context else ""
        try:
            if bulk_commits:
                logger.info(f"{context_prefix}Bulk inserting {len(bulk_commits)} commits...")
                session.bulk_insert_mappings(PrCommit, bulk_commits)

            if bulk_reviews:
                logger.info(f"{context_prefix}Bulk inserting {len(bulk_reviews)} reviews...")
                session.bulk_insert_mappings(PrReview, bulk_reviews)

            if bulk_comments:
                logger.info(f"{context_prefix}Bulk inserting {len(bulk_comments)} comments...")
                session.bulk_insert_mappings(PrComment, bulk_comments)

        except Exception as e:
            logger.error(f"{context_prefix}Error during bulk insert operations: {e}")
            session.rollback()
            raise  # Re-raise the exception to be handled by the calling function

        logger.info(f"{context_prefix}Bulk insert completed: {len(bulk_prs)} PRs, {len(bulk_commits)} commits, {len(bulk_reviews)} reviews, {len(bulk_comments)} comments")

        # Return PR, comment, review, and commit data for AI vector processing
        return {
            "prs_inserted": prs_to_insert if 'prs_to_insert' in locals() else [],
            "prs_updated": [pr_data for pr_data in bulk_prs if (pr_data['external_id'], pr_data['repository_id']) in existing_pr_map] if 'existing_pr_map' in locals() else [],
            "comments_inserted": bulk_comments if bulk_comments else [],
            "reviews_inserted": bulk_reviews if bulk_reviews else [],
            "commits_inserted": bulk_commits if bulk_commits else []
        }

    except Exception as e:
        logger.error(f"Error performing bulk inserts: {e}")
        raise


async def process_bulk_ai_vectors_for_github(
    session: Session,
    integration: Integration,
    prs_inserted: List[Dict[str, Any]],
    prs_updated: List[Dict[str, Any]],
    repo_context: str,
    comments_inserted: List[Dict[str, Any]] = None,
    reviews_inserted: List[Dict[str, Any]] = None,
    commits_inserted: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Bulk process AI vectors for inserted and updated GitHub pull requests, comments, reviews, and commits.

    This function handles:
    1. Bulk vector generation for new PRs (INSERT)
    2. Vector updates for modified PRs (UPDATE)
    3. Bulk vector generation for new PR comments (INSERT)
    4. Bulk vector generation for new PR reviews (INSERT)
    5. Bulk vector generation for new PR commits (INSERT)
    6. Proper handling of qdrant_vectors table and Qdrant database sync

    Args:
        session: Database session
        integration: Integration instance
        prs_inserted: List of newly inserted PR data
        prs_updated: List of updated PR data
        repo_context: Repository context for logging
        comments_inserted: List of newly inserted comment data
        reviews_inserted: List of newly inserted review data
        commits_inserted: List of newly inserted commit data

    Returns:
        Dict with processing results
    """
    try:
        comments_inserted = comments_inserted or []
        reviews_inserted = reviews_inserted or []
        commits_inserted = commits_inserted or []
        logger.info(f"[{repo_context}] Starting bulk AI vector processing: {len(prs_inserted)} new PRs, {len(prs_updated)} updated PRs, {len(comments_inserted)} new comments, {len(reviews_inserted)} new reviews, {len(commits_inserted)} new commits")

        total_created = 0
        total_updated = 0
        total_failed = 0
        comments_created = 0
        comments_failed = 0
        reviews_created = 0
        reviews_failed = 0
        commits_created = 0
        commits_failed = 0

        # Process new PRs for vector creation
        if prs_inserted:
            logger.info(f"[{repo_context}] Processing {len(prs_inserted)} new PRs for vector creation...")

            # Prepare entities for bulk vector creation
            entities_to_create = []
            for pr_data in prs_inserted:
                try:
                    # Create entity data for AI processing
                    entity_data = {
                        "number": pr_data.get("number"),
                        "title": pr_data.get("title"),
                        "body": pr_data.get("body"),
                        "state": pr_data.get("state"),
                        "author": pr_data.get("author"),
                        "labels": pr_data.get("labels"),
                        "base_branch": pr_data.get("base_branch"),
                        "head_branch": pr_data.get("head_branch")
                    }

                    # Remove None values to create cleaner text content
                    entity_data = {k: v for k, v in entity_data.items() if v is not None}

                    entities_to_create.append({
                        "entity_data": entity_data,
                        "record_id": str(pr_data.get("number")),  # Use PR number as record ID
                        "table_name": "pull_requests"
                    })

                except Exception as e:
                    logger.warning(f"[{repo_context}] Error preparing PR #{pr_data.get('number', 'unknown')} for vector creation: {e}")
                    total_failed += 1

            # Bulk create vectors
            if entities_to_create:
                # Get auth token for this tenant
                from app.jobs.orchestrator import _get_job_auth_token
                auth_token = _get_job_auth_token(integration.tenant_id)

                result = await bulk_store_entity_vectors_for_etl(entities_to_create, auth_token=auth_token)
                if result.success:
                    total_created = result.vectors_stored
                    total_failed += result.vectors_failed
                    logger.info(f"[{repo_context}] ✅ Bulk created {total_created} vectors for new PRs")
                else:
                    logger.error(f"[{repo_context}] ❌ Failed to bulk create vectors: {result.error}")
                    total_failed += len(entities_to_create)

        # Process updated PRs for vector updates
        if prs_updated:
            logger.info(f"[{repo_context}] Processing {len(prs_updated)} updated PRs for vector updates...")

            # Prepare entities for bulk vector updates
            entities_to_update = []
            for pr_data in prs_updated:
                try:
                    # Create entity data for AI processing
                    entity_data = {
                        "number": pr_data.get("number"),
                        "title": pr_data.get("title"),
                        "body": pr_data.get("body"),
                        "state": pr_data.get("state"),
                        "author": pr_data.get("author"),
                        "labels": pr_data.get("labels"),
                        "base_branch": pr_data.get("base_branch"),
                        "head_branch": pr_data.get("head_branch")
                    }

                    # Remove None values to create cleaner text content
                    entity_data = {k: v for k, v in entity_data.items() if v is not None}

                    entities_to_update.append({
                        "entity_data": entity_data,
                        "record_id": str(pr_data.get("number")),  # Use PR number as record ID
                        "table_name": "pull_requests"
                    })

                except Exception as e:
                    logger.warning(f"[{repo_context}] Error preparing PR #{pr_data.get('number', 'unknown')} for vector update: {e}")
                    total_failed += 1

            # Bulk update vectors
            if entities_to_update:
                # Get auth token for this tenant
                from app.jobs.orchestrator import _get_job_auth_token
                auth_token = _get_job_auth_token(integration.tenant_id)

                result = await bulk_update_entity_vectors_for_etl(entities_to_update, auth_token=auth_token)
                if result.success:
                    total_updated = result.vectors_updated
                    total_failed += result.vectors_failed
                    logger.info(f"[{repo_context}] ✅ Bulk updated {total_updated} vectors for updated PRs")
                else:
                    logger.error(f"[{repo_context}] ❌ Failed to bulk update vectors: {result.error}")
                    total_failed += len(entities_to_update)

        # Process new comments for vector creation
        if comments_inserted:
            logger.info(f"[{repo_context}] Processing {len(comments_inserted)} new comments for vector creation...")

            # Prepare entities for bulk vector creation
            entities_to_create = []
            for comment_data in comments_inserted:
                try:
                    # Create entity data for AI processing
                    entity_data = {
                        "external_id": comment_data.get("external_id"),
                        "author_login": comment_data.get("author_login"),
                        "body": comment_data.get("body"),
                        "comment_type": comment_data.get("comment_type"),
                        "path": comment_data.get("path"),
                        "line": comment_data.get("line"),
                        "position": comment_data.get("position")
                    }

                    # Remove None values to create cleaner text content
                    entity_data = {k: v for k, v in entity_data.items() if v is not None}

                    # Skip comments without body text
                    if not entity_data.get("body"):
                        comments_failed += 1
                        continue

                    entities_to_create.append({
                        "entity_data": entity_data,
                        "record_id": str(comment_data.get("external_id")),  # Use comment external ID as record ID
                        "table_name": "prs_comments"
                    })

                except Exception as e:
                    logger.warning(f"[{repo_context}] Error preparing comment {comment_data.get('external_id', 'unknown')} for vector creation: {e}")
                    comments_failed += 1

            # Bulk create vectors for comments
            if entities_to_create:
                # Get auth token for this tenant
                from app.jobs.orchestrator import _get_job_auth_token
                auth_token = _get_job_auth_token(integration.tenant_id)

                result = await bulk_store_entity_vectors_for_etl(entities_to_create, auth_token=auth_token)
                if result.success:
                    comments_created = result.vectors_stored
                    comments_failed += result.vectors_failed
                    logger.info(f"[{repo_context}] ✅ Bulk created {comments_created} vectors for new comments")
                else:
                    logger.error(f"[{repo_context}] ❌ Failed to bulk create comment vectors: {result.error}")
                    comments_failed += len(entities_to_create)

        # Process new reviews for vector creation
        if reviews_inserted:
            logger.info(f"[{repo_context}] Processing {len(reviews_inserted)} new reviews for vector creation...")

            # Prepare entities for bulk vector creation
            entities_to_create = []
            for review_data in reviews_inserted:
                try:
                    # Create entity data for AI processing
                    entity_data = {
                        "external_id": review_data.get("external_id"),
                        "author_login": review_data.get("author_login"),
                        "state": review_data.get("state"),
                        "body": review_data.get("body"),
                        "submitted_at": review_data.get("submitted_at")
                    }

                    # Remove None values to create cleaner text content
                    entity_data = {k: v for k, v in entity_data.items() if v is not None}

                    # Skip reviews without meaningful content (state and author are minimum)
                    if not entity_data.get("state") or not entity_data.get("author_login"):
                        reviews_failed += 1
                        continue

                    entities_to_create.append({
                        "entity_data": entity_data,
                        "record_id": str(review_data.get("external_id")),  # Use review external ID as record ID
                        "table_name": "prs_reviews"
                    })

                except Exception as e:
                    logger.warning(f"[{repo_context}] Error preparing review {review_data.get('external_id', 'unknown')} for vector creation: {e}")
                    reviews_failed += 1

            # Bulk create vectors for reviews
            if entities_to_create:
                # Get auth token for this tenant
                from app.jobs.orchestrator import _get_job_auth_token
                auth_token = _get_job_auth_token(integration.tenant_id)

                result = await bulk_store_entity_vectors_for_etl(entities_to_create, auth_token=auth_token)
                if result.success:
                    reviews_created = result.vectors_stored
                    reviews_failed += result.vectors_failed
                    logger.info(f"[{repo_context}] ✅ Bulk created {reviews_created} vectors for new reviews")
                else:
                    logger.error(f"[{repo_context}] ❌ Failed to bulk create review vectors: {result.error}")
                    reviews_failed += len(entities_to_create)

        # Process new commits for vector creation
        if commits_inserted:
            logger.info(f"[{repo_context}] Processing {len(commits_inserted)} new commits for vector creation...")

            # Prepare entities for bulk vector creation
            entities_to_create = []
            for commit_data in commits_inserted:
                try:
                    # Create entity data for AI processing
                    authored_date = commit_data.get("authored_date")
                    committed_date = commit_data.get("committed_date")

                    # Handle datetime serialization for authored_date
                    authored_date_str = None
                    if authored_date:
                        if hasattr(authored_date, 'isoformat'):
                            authored_date_str = authored_date.isoformat()
                        else:
                            authored_date_str = str(authored_date)

                    # Handle datetime serialization for committed_date
                    committed_date_str = None
                    if committed_date:
                        if hasattr(committed_date, 'isoformat'):
                            committed_date_str = committed_date.isoformat()
                        else:
                            committed_date_str = str(committed_date)

                    entity_data = {
                        "external_id": commit_data.get("external_id"),  # SHA
                        "author_name": commit_data.get("author_name"),
                        "author_email": commit_data.get("author_email"),
                        "committer_name": commit_data.get("committer_name"),
                        "committer_email": commit_data.get("committer_email"),
                        "message": commit_data.get("message"),
                        "authored_date": authored_date_str,
                        "committed_date": committed_date_str
                    }

                    # Remove None values to create cleaner text content
                    entity_data = {k: v for k, v in entity_data.items() if v is not None}

                    # Skip commits without message (main content)
                    if not entity_data.get("message"):
                        commits_failed += 1
                        continue

                    entities_to_create.append({
                        "entity_data": entity_data,
                        "record_id": str(commit_data.get("external_id")),  # Use commit SHA as record ID
                        "table_name": "prs_commits"
                    })

                except Exception as e:
                    logger.warning(f"[{repo_context}] Error preparing commit {commit_data.get('external_id', 'unknown')} for vector creation: {e}")
                    commits_failed += 1

            # Bulk create vectors for commits
            if entities_to_create:
                # Get auth token for this tenant
                from app.jobs.orchestrator import _get_job_auth_token
                auth_token = _get_job_auth_token(integration.tenant_id)

                result = await bulk_store_entity_vectors_for_etl(entities_to_create, auth_token=auth_token)
                if result.success:
                    commits_created = result.vectors_stored
                    commits_failed += result.vectors_failed
                    logger.info(f"[{repo_context}] ✅ Bulk created {commits_created} vectors for new commits")
                else:
                    logger.error(f"[{repo_context}] ❌ Failed to bulk create commit vectors: {result.error}")
                    commits_failed += len(entities_to_create)

        logger.info(f"[{repo_context}] Bulk AI vector processing completed: {total_created} PRs created, {total_updated} PRs updated, {comments_created} comments created, {reviews_created} reviews created, {commits_created} commits created, {total_failed + comments_failed + reviews_failed + commits_failed} failed")

        return {
            "success": True,
            "vectors_created": total_created,
            "vectors_updated": total_updated,
            "vectors_failed": total_failed,
            "comments_created": comments_created,
            "comments_failed": comments_failed,
            "reviews_created": reviews_created,
            "reviews_failed": reviews_failed,
            "commits_created": commits_created,
            "commits_failed": commits_failed
        }

    except Exception as e:
        logger.error(f"[{repo_context}] Error in bulk AI vector processing: {e}")
        return {
            "success": False,
            "error": str(e),
            "vectors_created": 0,
            "vectors_updated": 0,
            "vectors_failed": 0,
            "comments_created": 0,
            "comments_failed": 0,
            "reviews_created": 0,
            "reviews_failed": 0,
            "commits_created": 0,
            "commits_failed": 0
        }
