"""
GitHub Passive Job

Implements the GitHub sync portion of the Active/Passive Job Model.
This job:
1. Discovers repositories using GitHub Search API (incremental & safe)
2. Extracts pull requests using GitHub GraphQL API (incremental & safe)
3. On success: Sets Jira job to PENDING, itself to FINISHED
4. On failure: Sets itself to PENDING with appropriate checkpoint data

Note: PR-Issue linking is now handled via join queries on JiraPullRequestLinks table.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.logging_config import get_logger
from app.core.config import AppConfig, get_settings
from app.core.utils import DateTimeHelper
from app.core.websocket_manager import get_websocket_manager
from app.core.job_manager import CancellableJob
from app.models.unified_models import JobSchedule, Integration, Repository, PullRequest
from app.jobs.github.github_graphql_client import GitHubGraphQLClient
from app.jobs.github.github_graphql_processor import GitHubGraphQLProcessor
from app.jobs.github.github_graphql_extractor import (
    process_repository_prs_with_graphql, process_repository_prs_with_graphql_recovery
)
from typing import Dict, Any, List, Optional
from enum import Enum
import requests
import asyncio


class GitHubExecutionMode(Enum):
    """GitHub job execution modes."""
    REPOSITORIES = "repositories"     # Repository discovery only
    PULL_REQUESTS = "pull_requests"   # PR extraction for all repos
    SINGLE_REPO = "single_repo"       # All PRs from specific repository
    ALL = "all"                       # Full extraction (current production behavior)
from datetime import datetime, timedelta
import os

logger = get_logger(__name__)


async def get_github_rate_limits_internal(github_token: str) -> Dict[str, Any]:
    """
    Internal function to get GitHub rate limits.

    Args:
        github_token: GitHub personal access token

    Returns:
        Dictionary with core, search, and graphql rate limit info
    """
    try:
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'ETL-Service/1.0'
        }

        response = requests.get('https://api.github.com/rate_limit', headers=headers)

        if response.ok:
            rate_limit_data = response.json()
            return {
                'core': rate_limit_data['resources']['core'],
                'search': rate_limit_data['resources']['search'],
                'graphql': rate_limit_data['resources']['graphql']
            }
        else:
            logger.warning(f"Failed to get GitHub rate limits: {response.status_code}")
            return {}

    except Exception as e:
        logger.error(f"Error getting GitHub rate limits: {e}")
        return {}


async def execute_github_extraction_by_mode(
    session, github_integration, github_token, job_schedule, websocket_manager,
    execution_mode: GitHubExecutionMode, target_repository: Optional[str], target_repositories: Optional[List[str]],
    update_sync_timestamp: bool = True, update_job_schedule: bool = True
) -> Dict[str, Any]:
    """
    Execute GitHub extraction based on the specified mode.

    Args:
        session: Database session
        github_integration: GitHub integration instance
        github_token: GitHub API token
        job_schedule: Job schedule instance
        websocket_manager: WebSocket manager for progress updates
        execution_mode: Execution mode
        target_repository: Target repository for single_repo mode
        target_repositories: Target repositories for specific modes

    Returns:
        Extraction result dictionary
    """
    try:
        if execution_mode == GitHubExecutionMode.REPOSITORIES:
            logger.info("Executing REPOSITORIES mode - repository discovery only")
            return await extract_github_repositories_only(session, github_integration, github_token, websocket_manager, target_repositories)

        elif execution_mode == GitHubExecutionMode.PULL_REQUESTS:
            logger.info("Executing PULL_REQUESTS mode - PR extraction for all repos")
            return await extract_github_pull_requests_only(session, github_integration, github_token, job_schedule, websocket_manager, target_repositories)

        elif execution_mode == GitHubExecutionMode.SINGLE_REPO:
            logger.info("Executing SINGLE_REPO mode - all PRs from specific repository")
            if not target_repository:
                return {'success': False, 'error': 'Single repo mode requires a target repository'}
            return await extract_github_single_repo_prs(session, github_integration, github_token, job_schedule, websocket_manager, target_repository)

        elif execution_mode == GitHubExecutionMode.ALL:
            logger.info("Executing ALL mode - full extraction (production behavior)")
            return await process_github_data_with_graphql(session, github_integration, github_token, job_schedule, websocket_manager)

        else:
            return {'success': False, 'error': f'Unknown execution mode: {execution_mode}'}

    except Exception as e:
        logger.error(f"Error in GitHub extraction mode {execution_mode}: {e}")
        return {'success': False, 'error': str(e)}


async def execute_github_extraction_session_free(
    client_id: int,
    integration_id: int,
    github_token: str,
    job_schedule_id: int,
    execution_mode: GitHubExecutionMode,
    target_repository: Optional[str] = None,
    target_repositories: Optional[List[str]] = None,
    update_sync_timestamp: bool = True,
    update_job_schedule: bool = True
) -> Dict[str, Any]:
    """
    Execute GitHub extraction without keeping a database session open during API calls.
    This prevents connection timeouts and detached instance errors.
    """
    from app.core.database import get_database
    from sqlalchemy import func

    try:
        # Create fresh session for each database operation
        database = get_database()

        # Get integration details with a quick session
        with database.get_read_session_context() as session:
            if integration_id is None:
                # Get integration from job schedule
                job_schedule = session.query(JobSchedule).get(job_schedule_id)
                if not job_schedule:
                    return {'success': False, 'error': 'Job schedule not found'}

                integration = session.query(Integration).filter(
                    Integration.client_id == client_id,
                    func.upper(Integration.name) == 'GITHUB'
                ).first()

                if not integration:
                    return {'success': False, 'error': 'GitHub integration not found for client'}

                integration_id = integration.id
            else:
                integration = session.query(Integration).filter(
                    Integration.id == integration_id,
                    Integration.client_id == client_id
                ).first()

            if not integration:
                return {'success': False, 'error': 'Integration not found'}

            # Store integration details for github_client creation if needed
            integration_username = integration.username
            integration_password = integration.password

        # Create github_token if not provided
        if github_token is None:
            from app.core.config import AppConfig

            key = AppConfig.load_key()
            github_token = AppConfig.decrypt_token(integration_password, key)

        # Execute the extraction mode without an open session
        if execution_mode == GitHubExecutionMode.SINGLE_REPO:
            logger.info("Executing SINGLE_REPO mode - session-free approach")
            if not target_repository:
                return {'success': False, 'error': 'Single repo mode requires a target repository'}

            return await extract_github_single_repo_prs_session_free(
                client_id, integration_id, github_token, job_schedule_id, target_repository
            )

        elif execution_mode == GitHubExecutionMode.ALL:
            logger.info("Executing ALL mode - session-free approach")
            return await process_github_data_with_graphql_session_free(
                client_id, integration_id, github_token, job_schedule_id
            )

        else:
            return {'success': False, 'error': f'Session-free mode not implemented for: {execution_mode}'}

    except Exception as e:
        logger.error(f"Error in session-free GitHub extraction: {e}")
        return {'success': False, 'error': str(e)}


async def extract_github_repositories_only(session, github_integration, github_token, websocket_manager, target_repositories: Optional[List[str]]) -> Dict[str, Any]:
    """Extract GitHub repositories only (no PR processing)."""
    try:
        logger.info("Starting repository discovery only")
        await websocket_manager.send_progress_update("github_sync", 20.0, "Discovering repositories...")

        # Create a temporary job schedule for repository discovery
        from app.models.unified_models import JobSchedule
        temp_job_schedule = JobSchedule(job_name='temp_repo_discovery', status='RUNNING')

        # Discover repositories
        repos_result = await discover_all_repositories(session, github_integration, temp_job_schedule)

        if repos_result['success']:
            await websocket_manager.send_progress_update("github_sync", 100.0, f"Repository discovery completed - {repos_result['repos_processed']} repositories processed")
            return {
                'success': True,
                'repos_processed': repos_result['repos_processed'],
                'repositories': repos_result['repositories']
            }
        else:
            return repos_result

    except Exception as e:
        logger.error(f"Error in repository discovery: {e}")
        return {'success': False, 'error': str(e)}


async def extract_github_pull_requests_only(session, github_integration, github_token, job_schedule, websocket_manager, target_repositories: Optional[List[str]]) -> Dict[str, Any]:
    """Extract pull requests for all repositories (assumes repositories already exist)."""
    try:
        logger.info("Starting PR extraction for all repositories")
        await websocket_manager.send_progress_update("github_sync", 20.0, "Loading repositories...")

        from app.models.unified_models import Repository

        # Get all repositories from database
        repositories = session.query(Repository).filter(
            Repository.integration_id == github_integration.id,
            Repository.client_id == github_integration.client_id
        ).all()

        if not repositories:
            return {'success': False, 'error': 'No repositories found in database. Run repository discovery first.'}

        logger.info(f"Found {len(repositories)} repositories for PR extraction")

        # Initialize GraphQL client with database session for heartbeat
        graphql_client = GitHubGraphQLClient(github_token, db_session=session)

        # Initialize queue for PR processing
        job_schedule.initialize_repo_queue(repositories)

        # Process PRs for all repositories
        total_prs_processed = 0

        for repo_index, repository in enumerate(repositories, 1):
            try:
                owner, repo_name = repository.full_name.split('/', 1)
                logger.info(f"Processing PRs for repository {repo_index}/{len(repositories)}: {owner}/{repo_name}")

                progress = 20.0 + (70.0 * repo_index / len(repositories))
                await websocket_manager.send_progress_update("github_sync", progress, f"Processing PRs for {owner}/{repo_name}")

                # Process PRs for this repository (non-blocking)
                from app.jobs.github.github_graphql_extractor import process_repository_prs_with_graphql
                pr_result = await process_repository_prs_with_graphql(
                    session, graphql_client, repository, owner, repo_name, github_integration, job_schedule, websocket_manager
                )

                if pr_result['success']:
                    total_prs_processed += pr_result.get('prs_processed', 0)
                    logger.info(f"Processed {pr_result.get('prs_processed', 0)} PRs for {owner}/{repo_name}")
                else:
                    logger.warning(f"Failed to process PRs for {owner}/{repo_name}: {pr_result.get('error', 'Unknown error')}")

                # Check rate limit
                if graphql_client.is_rate_limited():
                    logger.warning("Rate limit reached during PR extraction")
                    break

                # Yield control after each repository to prevent UI blocking
                import asyncio
                await asyncio.sleep(0)  # Yield control to prevent blocking

            except Exception as e:
                logger.error(f"Error processing repository {repository.full_name}: {e}")
                continue

        await websocket_manager.send_progress_update("github_sync", 100.0, f"PR extraction completed - {total_prs_processed} PRs processed")

        return {
            'success': True,
            'repos_processed': len(repositories),
            'prs_processed': total_prs_processed
        }

    except Exception as e:
        logger.error(f"Error in PR extraction: {e}")
        return {'success': False, 'error': str(e)}


async def extract_github_single_repo_prs(session, github_integration, github_token, job_schedule, websocket_manager, target_repository: str) -> Dict[str, Any]:
    """Extract all PRs from a specific repository."""
    try:
        logger.info(f"Starting PR extraction for single repository: {target_repository}")
        await websocket_manager.send_progress_update("github_sync", 20.0, f"Loading repository {target_repository}...")

        from app.models.unified_models import Repository

        # Find the repository in database
        repository = session.query(Repository).filter(
            Repository.full_name == target_repository,
            Repository.integration_id == github_integration.id,
            Repository.client_id == github_integration.client_id
        ).first()

        if not repository:
            return {'success': False, 'error': f'Repository {target_repository} not found in database. Run repository discovery first.'}

        # Initialize GraphQL client with database session for heartbeat
        graphql_client = GitHubGraphQLClient(github_token, db_session=session)

        # Process PRs for this specific repository
        owner, repo_name = target_repository.split('/', 1)
        logger.info(f"Processing all PRs for {owner}/{repo_name}")

        await websocket_manager.send_progress_update("github_sync", 50.0, f"Extracting PRs from {owner}/{repo_name}")

        from app.jobs.github.github_graphql_extractor import process_repository_prs_with_graphql
        pr_result = await process_repository_prs_with_graphql(
            session, graphql_client, repository, owner, repo_name, github_integration, job_schedule, websocket_manager
        )

        if pr_result['success']:
            await websocket_manager.send_progress_update("github_sync", 100.0, f"Single repository PR extraction completed - {pr_result.get('prs_processed', 0)} PRs processed")
            return {
                'success': True,
                'repos_processed': 1,
                'prs_processed': pr_result.get('prs_processed', 0),
                'repository': target_repository
            }
        else:
            return pr_result

    except Exception as e:
        logger.error(f"Error in single repository PR extraction: {e}")
        return {'success': False, 'error': str(e)}


async def run_github_sync(
    session: Session,
    job_schedule: JobSchedule,
    execution_mode: GitHubExecutionMode = GitHubExecutionMode.ALL,
    target_repository: Optional[str] = None,
    target_repositories: Optional[List[str]] = None,
    update_sync_timestamp: bool = True,
    update_job_schedule: bool = True
):
    """
    Main GitHub sync function with execution mode support.

    Args:
        session: Database session
        job_schedule: JobSchedule record for this job
        execution_mode: Execution mode (repositories, pull_requests, single_repo, all)
        target_repository: Specific repository for single_repo mode (format: "owner/repo")
        target_repositories: Specific repositories for repositories/pull_requests modes
        update_sync_timestamp: Whether to update integration.last_sync_at (default: True)
        update_job_schedule: Whether to update job_schedule.status (default: True)
    """
    try:
        logger.info(f"Starting GitHub sync job (ID: {job_schedule.id}, Mode: {execution_mode.value})")
        logger.info(f"GitHub sync - Job status at entry: {job_schedule.status}")
        logger.info(f"GitHub sync - update_job_schedule: {update_job_schedule}")

        # Log execution parameters
        if execution_mode == GitHubExecutionMode.SINGLE_REPO:
            logger.info(f"Target Repository: {target_repository}")
        if target_repositories:
            logger.info(f"Target Repositories: {target_repositories}")

        # Initialize WebSocket manager and clear previous progress
        websocket_manager = get_websocket_manager()
        websocket_manager.clear_job_progress("github_sync")

        # Send status update that job is running
        if update_job_schedule:
            await websocket_manager.send_status_update(
                "github_sync",
                "RUNNING",
                {"message": "GitHub sync job is now running"}
            )

        # ✅ SECURITY: Get GitHub integration using job_schedule.integration_id for client isolation
        await websocket_manager.send_progress_update("github_sync", 5.0, "Initializing GitHub integration...")
        if job_schedule.integration_id:
            github_integration = session.query(Integration).filter(
                Integration.id == job_schedule.integration_id,
                Integration.client_id == job_schedule.client_id  # Double-check client isolation
            ).first()
        else:
            # Fallback: Get by name and client_id (for backward compatibility)
            github_integration = session.query(Integration).filter(
                func.upper(Integration.name) == "GITHUB",
                Integration.client_id == job_schedule.client_id
            ).first()

        if not github_integration:
            error_msg = f"No GitHub integration found for client {job_schedule.client_id}. Please check integration setup."
            logger.error(f"ERROR: {error_msg}")
            await websocket_manager.send_exception("github_sync", "ERROR", error_msg)
            job_schedule.set_pending_with_checkpoint(error_msg)
            session.commit()
            return

        # Setup GitHub token
        key = AppConfig.load_key()
        github_token = AppConfig.decrypt_token(github_integration.password, key)

        # Check rate limit before starting work
        await websocket_manager.send_progress_update("github_sync", 10.0, "Checking GitHub API rate limits...")
        initial_rate_limits = await get_github_rate_limits_internal(github_token)
        graphql_remaining = initial_rate_limits.get('graphql', {}).get('remaining', 0)

        if graphql_remaining <= 10:  # Need at least 10 requests to do meaningful work
            logger.warning(f"GitHub GraphQL API rate limit too low to proceed: {graphql_remaining} requests remaining")

            # Update job status to PENDING for early rate limit detection (only if update_job_schedule is True)
            if update_job_schedule:
                job_schedule.status = 'PENDING'

                # Send status update for early rate limit detection
                await websocket_manager.send_status_update(
                    "github_sync",
                    "PENDING",
                    {"message": "Rate limit too low to proceed - will retry later"}
                )
            else:
                logger.info("[JOB_SCHEDULE] Skipped updating job schedule status (test mode)")

            session.commit()

            # Schedule fast retry for early rate limit detection
            from app.core.orchestrator_scheduler import get_orchestrator_scheduler
            orchestrator_scheduler = get_orchestrator_scheduler()

            logger.info("GitHub job hit early rate limit - attempting to schedule fast retry...")
            fast_retry_scheduled = orchestrator_scheduler.schedule_fast_retry('github_sync')

            if fast_retry_scheduled:
                retry_interval = orchestrator_scheduler.get_retry_status('github_sync')['retry_interval_minutes']
                logger.info(f"   • Fast retry scheduled in {retry_interval} minutes")

            # Send completion notification for early rate limit detection
            await websocket_manager.send_completion(
                "github_sync",
                True,  # Partial success - we detected rate limit early
                {
                    'repos_processed': 0,
                    'prs_processed': 0,
                    'pr_links_created': 0,
                    'partial_success': True,
                    'rate_limit_reached': True,
                    'message': f'Rate limit too low to start ({graphql_remaining} requests remaining) - will retry later'
                }
            )

            return {
                'success': True,
                'rate_limit_reached': True,
                'partial_success': True,
                'error': f'Rate limit too low to proceed: {graphql_remaining} requests remaining',
                'repos_processed': 0,
                'prs_processed': 0
            }

        logger.info(f"GitHub rate limits OK: {graphql_remaining} GraphQL requests remaining")

        # Process GitHub data with unified queue-based recovery
        if job_schedule.is_recovery_run():
            logger.info("Recovery run detected - resuming from checkpoint")
            await websocket_manager.send_progress_update("github_sync", 15.0, "Resuming from checkpoint...")
        else:
            logger.info("Normal run - starting fresh")
            await websocket_manager.send_progress_update("github_sync", 15.0, "Starting repository discovery...")

        # Execute based on mode
        result = await execute_github_extraction_by_mode(
            session, github_integration, github_token, job_schedule, websocket_manager,
            execution_mode, target_repository, target_repositories,
            update_sync_timestamp, update_job_schedule
        )
        
        if result['success']:
            # Step 3: PR-Issue linking is now handled by Jira job via JiraPullRequestLinks table
            logger.info("Step 3: PR-Issue linking handled by Jira job (via JiraPullRequestLinks table)")
            await websocket_manager.send_progress_update("github_sync", 98.0, "GitHub sync completed - PR linking handled by Jira job")

            # Get current link statistics for reporting
            from app.utils.pr_link_queries import get_pr_link_statistics
            link_stats = get_pr_link_statistics(session, github_integration.client_id)
            result['pr_links_total'] = link_stats['total_pr_links']
            logger.info(f"Current PR-Issue links in database: {link_stats['total_pr_links']}")

            # Check if this was a complete success (not partial or rate limited)
            is_complete_success = (
                not result.get('rate_limit_reached', False) and
                not result.get('partial_success', False)
            )

            if is_complete_success:
                # Complete Success: Clean up checkpoint and set jobs status
                logger.info("Complete success - cleaning up and finishing")

                # Clear checkpoint data
                job_schedule.clear_checkpoints()

                # Update integration.last_sync_at only on complete success with no remaining checkpoints
                if update_sync_timestamp:
                    # Verify no recovery checkpoints remain
                    remaining_checkpoints = job_schedule.has_recovery_checkpoints()
                    if not remaining_checkpoints:
                        from datetime import datetime
                        # Update to current time (truncated to minute precision like Jira)
                        current_time = datetime.now().replace(second=0, microsecond=0)
                        github_integration.last_sync_at = current_time
                        logger.info(f"[SYNC_TIME] Updated GitHub integration last_sync_at to: {current_time.strftime('%Y-%m-%d %H:%M')}")
                    else:
                        logger.info("[SYNC_TIME] Skipped updating integration last_sync_at (recovery checkpoints remain)")
                else:
                    logger.info("[SYNC_TIME] Skipped updating integration last_sync_at (test mode)")

                # Handle job status transitions based on Jira job status (only if update_job_schedule is True)
                if update_job_schedule:
                    # ✅ SECURITY: Filter by client_id to prevent cross-client data access
                    jira_job = session.query(JobSchedule).filter(
                        JobSchedule.job_name == 'jira_sync',
                        JobSchedule.client_id == job_schedule.client_id
                    ).first()

                    if jira_job and jira_job.status == 'PAUSED':
                        # Jira is PAUSED: Keep GitHub as PENDING for next run
                        job_schedule.status = 'PENDING'
                        logger.info(f"   • Jira job is PAUSED - keeping GitHub job as PENDING")
                    else:
                        # Jira is not PAUSED: Set Jira to PENDING and GitHub to FINISHED
                        if jira_job:
                            jira_job.status = 'PENDING'
                        job_schedule.set_finished()
                        logger.info(f"   • Jira job set to PENDING, GitHub job set to FINISHED")

                        # Send status update that job is finished
                        await websocket_manager.send_status_update(
                            "github_sync",
                            "FINISHED",
                            {"message": "GitHub sync job completed successfully"}
                        )
                else:
                    logger.info("[JOB_SCHEDULE] Skipped updating job schedule status (test mode)")

                session.commit()

                # Get final rate limit status
                final_rate_limits = await get_github_rate_limits_internal(github_token)

                # Send final progress update
                await websocket_manager.send_progress_update("github_sync", 100.0, "GitHub sync completed successfully")

                # Small delay to ensure progress update is processed before completion notification
                import asyncio
                await asyncio.sleep(0.5)

                # Send completion notification
                await websocket_manager.send_completion(
                    "github_sync",
                    True,
                    {
                        'repos_processed': result['repos_processed'],
                        'prs_processed': result['prs_processed'],
                        'pr_links_created': result.get('pr_links_created', 0),
                        'staging_cleared': True,
                        'cycle_complete': True
                    }
                )

                # Reset retry attempts and restore normal schedule on success
                from app.core.orchestrator_scheduler import get_orchestrator_scheduler
                orchestrator_scheduler = get_orchestrator_scheduler()
                orchestrator_scheduler.reset_retry_attempts('github_sync')
                orchestrator_scheduler.restore_normal_schedule()

                logger.info("GitHub sync completed successfully")
                logger.info(f"   • Repositories processed: {result['repos_processed']}")
                logger.info(f"   • Pull requests processed: {result['prs_processed']}")
                logger.info(f"   • PR-Issue links created: {result.get('pr_links_created', 0)}")
                logger.info(f"   • Staging table cleared")
                logger.info(f"   • Jira job set to PENDING (cycle complete)")

            else:
                # Partial Success or Rate Limit: Keep staging data, keep job PENDING
                logger.info("Partial success or rate limit reached - preserving state")

                # Determine if this is a rate limit or other partial success
                is_rate_limit = result.get('rate_limit_reached', False)

                # Get final rate limit status
                final_rate_limits = await get_github_rate_limits_internal(github_token)

                if is_rate_limit:
                    # Rate limit reached - this is expected behavior, not an error
                    await websocket_manager.send_progress_update("github_sync", 100.0, "Rate limit reached - will resume on next run")
                    logger.warning("GitHub rate limit reached - will resume on next scheduled run")
                else:
                    # Other partial success scenario
                    await websocket_manager.send_progress_update("github_sync", 100.0, "GitHub sync partially completed - will resume later")
                    logger.warning("GitHub sync partially completed - will resume later")

                # Keep GitHub job as PENDING for next run (only if update_job_schedule is True)
                if update_job_schedule:
                    job_schedule.status = 'PENDING'

                    # Send status update for partial completion
                    await websocket_manager.send_status_update(
                        "github_sync",
                        "PENDING",
                        {"message": "GitHub sync partially completed - will resume later"}
                    )
                else:
                    logger.info("[JOB_SCHEDULE] Skipped updating job schedule status (test mode)")
                session.commit()

                # Send partial completion notification
                # For rate limits, send success=True (partial success), for other issues send success=False
                completion_success = is_rate_limit  # True for rate limits, False for other partial success
                await websocket_manager.send_completion(
                    "github_sync",
                    completion_success,
                    {
                        'repos_processed': result['repos_processed'],
                        'prs_processed': result['prs_processed'],
                        'pr_links_created': result.get('pr_links_created', 0),
                        'partial_success': True,
                        'rate_limit_reached': result.get('rate_limit_reached', False),
                        'message': 'Rate limit reached - will resume on next run' if is_rate_limit else 'Partial completion'
                    }
                )

                # Schedule fast retry for partial success (to continue processing sooner)
                from app.core.orchestrator_scheduler import get_orchestrator_scheduler
                orchestrator_scheduler = get_orchestrator_scheduler()

                logger.info("GitHub job partially completed - attempting to schedule fast retry...")
                fast_retry_scheduled = orchestrator_scheduler.schedule_fast_retry('github_sync')

                logger.info("GitHub sync partially completed")
                logger.info(f"   • Repositories processed: {result['repos_processed']}")
                logger.info(f"   • Pull requests processed: {result['prs_processed']}")
                logger.info(f"   • PR-Issue links created: {result.get('pr_links_created', 0)}")
                logger.info(f"   • Staging data preserved for next run")
                logger.info(f"   • GitHub job remains PENDING")
                if fast_retry_scheduled:
                    retry_interval = orchestrator_scheduler.get_retry_status('github_sync')['retry_interval_minutes']
                    logger.info(f"   • Fast retry scheduled in {retry_interval} minutes")
            
        else:
            # Failure: Set this job back to PENDING with checkpoint
            error_msg = result.get('error', 'Unknown error')
            checkpoint_data = result.get('checkpoint_data', {})

            # Schedule fast retry if enabled
            from app.core.orchestrator_scheduler import get_orchestrator_scheduler
            orchestrator_scheduler = get_orchestrator_scheduler()

            logger.info("GitHub job failed - attempting to schedule fast retry...")
            fast_retry_scheduled = orchestrator_scheduler.schedule_fast_retry('github_sync')

            if fast_retry_scheduled:
                retry_status = orchestrator_scheduler.get_retry_status('github_sync')
                logger.info(f"Fast retry scheduled successfully: {retry_status}")
            else:
                logger.warning("Fast retry was not scheduled")

            # Note: No redundant send_exception call - error will be shown via progress update

            if update_job_schedule:
                job_schedule.set_pending_with_checkpoint(
                    error_msg,
                    repo_checkpoint=checkpoint_data.get('repo_checkpoint'),
                    repo_queue=checkpoint_data.get('repo_queue'),
                    last_pr_cursor=checkpoint_data.get('last_pr_cursor'),
                    current_pr_node_id=checkpoint_data.get('current_pr_node_id'),
                    last_commit_cursor=checkpoint_data.get('last_commit_cursor'),
                    last_review_cursor=checkpoint_data.get('last_review_cursor'),
                    last_comment_cursor=checkpoint_data.get('last_comment_cursor'),
                    last_review_thread_cursor=checkpoint_data.get('last_review_thread_cursor')
                )
            else:
                # In test mode, just save the error message without changing job status
                job_schedule.error_message = error_msg
                logger.info("[JOB_SCHEDULE] Skipped updating job schedule status (test mode)")
            # Handle potential session corruption from async operations
            try:
                session.commit()
            except Exception as commit_error:
                logger.warning(f"Session commit failed, attempting rollback: {commit_error}")
                try:
                    session.rollback()
                    session.commit()  # Try again after rollback
                except Exception as rollback_error:
                    logger.error(f"Session rollback also failed: {rollback_error}")
                    # Session is corrupted, but we'll continue since error handling is complete

            # Send status update that job failed and is now pending
            if update_job_schedule:
                await websocket_manager.send_status_update(
                    "github_sync",
                    "PENDING",
                    {"message": f"GitHub sync failed - {error_msg[:100]}..."}
                )

            # Send final progress update for error case (short message for progress bar)
            await websocket_manager.send_progress_update("github_sync", 100.0, "❌ GitHub sync failed - check Issues & Warnings below")

            # Send failure completion notification
            await websocket_manager.send_completion(
                "github_sync",
                False,
                {
                    'error': error_msg,
                    'checkpoint_saved': True,
                    'repos_processed': result.get('repos_processed', 0),
                    'prs_processed': result.get('prs_processed', 0)
                }
            )

            logger.error(f"GitHub sync failed: {error_msg}")
            logger.info(f"   • Checkpoint data saved for recovery")

    except Exception as e:
        logger.error(f"GitHub sync job error: {e}")
        import traceback
        traceback.print_exc()

        # Rollback the session to clear any failed transaction state
        session.rollback()

        # Set job back to PENDING on unexpected error (only if update_job_schedule is True)
        if update_job_schedule:
            job_schedule.set_pending_with_checkpoint(str(e))
        else:
            job_schedule.error_message = str(e)
            logger.info("[JOB_SCHEDULE] Skipped updating job schedule status (test mode)")
        session.commit()


async def discover_all_repositories(session: Session, integration: Integration, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Discover repositories using unified /search endpoint approach:
    1. Query Jira PR links for non-health repository names
    2. Combine health- filter with non-health repo names using OR operators
    3. Use GitHub Search API exclusively with smart batching for 256 char limit

    Args:
        session: Database session
        integration: GitHub integration object
        job_schedule: Job schedule for checkpoint management

    Returns:
        Dictionary with discovery results containing repositories list
    """
    try:
        from app.jobs.github import GitHubClient
        from app.jobs.github.github_graphql_processor import GitHubGraphQLProcessor
        from app.models.unified_models import Repository
        from datetime import datetime
        import os

        logger.info("Discovering repositories using unified /search endpoint...")
        logger.info("Combining health- pattern + Jira repo names with OR operators")

        # Setup GitHub client
        from app.core.config import AppConfig
        key = AppConfig.load_key()
        github_token = AppConfig.decrypt_token(integration.password, key)
        github_client = GitHubClient(github_token)

        # Get organization from environment
        org = os.getenv('GITHUB_ORG', 'wexinc')
        # Use base_search from integration instead of environment variable
        name_filter = integration.base_search

        # Step 1: Get repositories from Jira PR links (non-health repos)
        logger.info("Step 1: Extracting repositories from Jira PR links...")

        from app.models.unified_models import JiraPullRequestLinks

        # Check if we have any PR links at all
        # ✅ SECURITY: Filter by client_id to prevent cross-client data access
        total_pr_links = session.query(JiraPullRequestLinks).filter(
            JiraPullRequestLinks.client_id == integration.client_id
        ).count()
        logger.info(f"Total PR links in database for client {integration.client_id}: {total_pr_links}")

        if total_pr_links == 0:
            logger.warning("No Jira PR links found - run Jira job first to populate data")

        # Get unique repository full names from PR links
        try:
            # ✅ SECURITY: Filter by client_id to prevent cross-client data access
            jira_repo_names = session.query(JiraPullRequestLinks.repo_full_name).filter(
                JiraPullRequestLinks.client_id == integration.client_id
            ).distinct().all()
        except Exception as e:
            logger.error(f"Error querying repo_full_name column: {e}")
            logger.error("This might mean the repo_full_name column doesn't exist - run the migration script")
            jira_repo_names = []
        jira_repo_names = {repo_name[0] for repo_name in jira_repo_names if repo_name[0]}

        logger.info(f"Found {len(jira_repo_names)} unique repositories in Jira PR links")

        # Filter out repositories that contain health- pattern (will be found by search)
        health_pattern = name_filter.replace('%20', ' ') if name_filter else None  # Convert URL encoding back to space
        # Clean the pattern for consistent filtering (remove trailing hyphens)
        clean_health_pattern = health_pattern.rstrip('-') if health_pattern and health_pattern.endswith('-') else health_pattern

        non_health_repo_names = []
        for repo_full_name in jira_repo_names:
            if '/' in repo_full_name:
                # Extract just the repo name part (after the '/')
                repo_name = repo_full_name.split('/', 1)[1]
                # Check if repo name contains health pattern anywhere (using cleaned pattern)
                if not clean_health_pattern or clean_health_pattern not in repo_name:
                    non_health_repo_names.append(repo_name)  # Store just the repo name for search

        logger.info(f"Non-{clean_health_pattern or 'filtered'} repositories from Jira: {len(non_health_repo_names)}")
        if non_health_repo_names and len(non_health_repo_names) <= 5:
            logger.info(f"Non-health repos: {', '.join(sorted(non_health_repo_names))}")
        elif non_health_repo_names:
            logger.info(f"Non-health repos: {', '.join(sorted(non_health_repo_names)[:3])}... (+{len(non_health_repo_names)-3} more)")

        # Step 2: Get repositories from GitHub Search API with health- filter
        logger.info(f"Step 2: Searching GitHub API for repositories in org: {org}")
        if name_filter:
            logger.info(f"Filtering by name: {name_filter}")

        # Determine start date based on job state
        if job_schedule.last_repo_sync_checkpoint:
            # Recovery run - use checkpoint date
            start_date = job_schedule.last_repo_sync_checkpoint.strftime('%Y-%m-%d')
            logger.info(f"Recovery run detected - using checkpoint date: {start_date}")
        elif integration.last_sync_at:
            # Normal run - use integration's last sync date
            start_date = integration.last_sync_at.strftime('%Y-%m-%d')
            logger.info(f"Using integration last sync date: {start_date}")
        else:
            # Fallback - should not happen if integration is properly initialized
            start_date = "1900-01-01"
            logger.warning("No last_sync_at found, using fallback date")

        end_date = datetime.today().strftime('%Y-%m-%d')

        logger.info(f"Date range: {start_date} to {end_date}")
        if integration.last_sync_at:
            logger.info(f"Integration last sync: {integration.last_sync_at}")
        else:
            logger.info("No previous sync found, using default start date")

        # Step 3: Combined search using single /search endpoint
        logger.info("Step 3: Combined repository search using /search endpoint only...")

        # Use combined search with health- filter + non-health repos from Jira
        all_repos = github_client.search_repositories_combined(
            org=org,
            start_date=start_date,
            end_date=end_date,
            filter=name_filter,
            additional_repo_names=list(non_health_repo_names) if non_health_repo_names else None
        )

        logger.info(f"Total repositories found via combined search: {len(all_repos)}")

        if not all_repos:
            logger.warning("No repositories found from combined search")
            return {
                'success': True,
                'repositories': [],
                'repos_processed': 0
            }

        # Step 4: Process repositories for database insertion
        logger.info("Step 4: Processing repositories for database insertion...")

        # Get existing repositories to avoid duplicates
        existing_repos = {
            repo.external_id: repo for repo in session.query(Repository).filter(
                Repository.client_id == integration.client_id
            ).all()
        }

        repos_to_insert = []
        repos_updated = 0
        repos_skipped = 0

        # Create a temporary processor for repository data processing
        temp_processor = GitHubGraphQLProcessor(integration, 0)  # repository_id not needed for data processing

        logger.info(f"Processing {len(all_repos)} repositories...")
        for repo_index, repo_data in enumerate(all_repos, 1):
            try:
                # Show progress every 50 repos and yield control
                if repo_index % 50 == 0 or repo_index == len(all_repos):
                    logger.info(f"Repository progress: {repo_index}/{len(all_repos)}")
                    # Yield control every 50 repos to keep UI responsive
                    import asyncio
                    await asyncio.sleep(0.01)  # 10ms yield

                # Check if repository already exists
                external_id = str(repo_data['id'])
                repo_name = repo_data.get('full_name', 'unknown')

                if external_id in existing_repos:
                    existing_repo = existing_repos[external_id]

                    # Process repository data for comparison
                    repo_processed = temp_processor.process_repository_data(repo_data)
                    if repo_processed:
                        # Check if any fields have changed
                        needs_update = False

                        # Compare key fields that might change
                        if existing_repo.name != repo_processed.get('name'):
                            needs_update = True
                        if existing_repo.description != repo_processed.get('description'):
                            needs_update = True
                        if existing_repo.default_branch != repo_processed.get('default_branch'):
                            needs_update = True
                        if existing_repo.is_private != repo_processed.get('is_private'):
                            needs_update = True

                        if needs_update:
                            # Update the existing repository
                            for field, value in repo_processed.items():
                                if hasattr(existing_repo, field):
                                    setattr(existing_repo, field, value)
                            repos_updated += 1
                            logger.debug(f"Updated repository: {repo_name}")
                        else:
                            repos_skipped += 1
                    else:
                        repos_skipped += 1
                else:
                    # Process repository data using the processor
                    repo_processed = temp_processor.process_repository_data(repo_data)
                    if repo_processed:
                        repos_to_insert.append(repo_processed)

            except Exception as e:
                logger.error(f"Error processing repository {repo_data.get('full_name', 'unknown')}: {e}")
                continue

        # Commit all changes
        total_changes = 0

        if repos_to_insert:
            logger.info(f"Inserting {len(repos_to_insert)} new repositories...")
            from app.models.unified_models import Repository
            session.bulk_insert_mappings(Repository, repos_to_insert)
            total_changes += len(repos_to_insert)

        if repos_updated > 0:
            total_changes += repos_updated

        if total_changes > 0:
            session.commit()
            logger.info(f"Committed {total_changes} repository changes")

        total_processed = len(repos_to_insert) + repos_updated + repos_skipped
        logger.info(f"Repository discovery completed!")
        logger.info(f"   • New repositories: {len(repos_to_insert)}")
        logger.info(f"   • Updated repositories: {repos_updated}")
        logger.info(f"   • Unchanged repositories: {repos_skipped}")

        # Get all repositories for return
        repositories = session.query(Repository).filter(
            Repository.client_id == integration.client_id,
            Repository.active == True
        ).all()

        return {
            'success': True,
            'repositories': repositories,
            'repos_processed': total_processed,
            'repos_inserted': len(repos_to_insert),
            'repos_updated': repos_updated,
            'repos_skipped': repos_skipped
        }

    except Exception as e:
        logger.error(f"Error discovering repositories: {e}")
        return {
            'success': False,
            'error': str(e),
            'repositories': [],
            'repos_processed': 0
        }


def link_pull_requests_with_jira_issues(session: Session, integration: Integration) -> dict:
    """
    Legacy function for backward compatibility with test scripts.

    In the new architecture, PR-Issue linking is handled by the Jira job
    via the JiraPullRequestLinks table. This function just returns current
    statistics for compatibility.

    Args:
        session: Database session
        integration: GitHub integration

    Returns:
        Dictionary with success status and link statistics
    """
    try:
        from app.utils.pr_link_queries import get_pr_link_statistics

        # Get current link statistics
        link_stats = get_pr_link_statistics(session, integration.client_id)

        return {
            'success': True,
            'links_created': link_stats['total_pr_links'],
            'message': 'PR-Issue linking is now handled by Jira job via JiraPullRequestLinks table'
        }

    except Exception as e:
        logger.error(f"Error getting PR link statistics: {e}")
        return {
            'success': False,
            'links_created': 0,
            'error': str(e)
        }


# Note: PR-Issue linking is now handled via join queries on JiraPullRequestLinks table.
# The above function is kept for backward compatibility with test scripts.



async def process_github_data_with_graphql(session: Session, integration: Integration, github_token: str, job_schedule: JobSchedule, websocket_manager=None) -> Dict[str, Any]:
    """
    Process GitHub data using GraphQL API for efficient data fetching with queue-based recovery.

    Args:
        session: Database session
        integration: GitHub integration object
        github_token: Decrypted GitHub token
        job_schedule: Job schedule for checkpoint management

    Returns:
        Dictionary with processing results
    """
    try:
        logger.info("Starting GraphQL-based GitHub data processing")

        # Get WebSocket manager if not provided
        if websocket_manager is None:
            websocket_manager = get_websocket_manager()

        # Initialize GraphQL client with database session for heartbeat
        graphql_client = GitHubGraphQLClient(github_token, db_session=session)

        # Determine processing mode and get repositories
        full_queue = job_schedule.get_repo_queue()

        if full_queue:
            # Recovery mode: Use unfinished repositories from queue
            unfinished_repos = [repo for repo in full_queue if not repo.get("finished", False)]
            logger.info(f"Recovery mode: Processing {len(unfinished_repos)} unfinished repositories")
            logger.info(f"Full queue contains {len(full_queue)} total repositories (for analysis)")

            repositories = []
            for repo_data in unfinished_repos:
                # Get repository from database using external_id
                repo = session.query(Repository).filter(
                    Repository.external_id == repo_data["repo_id"],
                    Repository.client_id == integration.client_id
                ).first()
                if repo:
                    repositories.append(repo)
                else:
                    logger.warning(f"Repository {repo_data['full_name']} not found in database")
        else:
            # Normal mode: Discover repositories
            logger.info("Normal mode: Discovering repositories")
            repos_result = await discover_all_repositories(session, integration, job_schedule)
            if not repos_result['success']:
                return repos_result

            repositories = repos_result['repositories']
            logger.info(f"Found {len(repositories)} repositories to process")

            # Initialize queue for normal run
            job_schedule.initialize_repo_queue(repositories)

        # Step 2: Process pull requests using GraphQL
        total_prs_processed = 0
        total_repos = len(repositories)

        # Send initial progress update
        await websocket_manager.send_progress_update(
            "github_sync",
            10.0,
            f"Starting PR processing for {total_repos} repositories"
        )

        # Use cancellable job context
        with CancellableJob('github_sync') as job_context:
            for repo_index, repository in enumerate(repositories, 1):
                try:
                    # Check for cancellation every repository
                    await job_context.async_check_cancellation()

                    owner, repo_name = repository.full_name.split('/', 1)
                    logger.info(f"[REPO {repo_index}/{total_repos}] Starting PR processing for {owner}/{repo_name}")

                    # Send repository-level progress update
                    repo_progress = 10.0 + (repo_index - 1) / total_repos * 80.0  # 10% to 90%
                    await websocket_manager.send_progress_update(
                        "github_sync",
                        repo_progress,
                        f"Repository {repo_index}/{total_repos}: {owner}/{repo_name}"
                    )

                    # Process PRs for this repository using GraphQL (non-blocking)
                    pr_result = await process_repository_prs_with_graphql(
                        session, graphql_client, repository, owner, repo_name, integration, job_schedule, websocket_manager
                    )

                    # Check if rate limit was reached during PR processing FIRST (regardless of success flag)
                    if pr_result.get('rate_limit_reached', False):
                        logger.warning(f"[{owner}/{repo_name}] Rate limit reached during PR processing, stopping gracefully")

                        # Cleanup finished repos and save remaining work
                        remaining_count = job_schedule.cleanup_finished_repos()
                        full_queue = job_schedule.get_repo_queue()
                        finished_count = len(full_queue) - remaining_count
                        session.commit()

                        if remaining_count > 0:
                            logger.info(f"Rate limit reached - {remaining_count} repositories remaining for next run")
                            logger.info(f"Queue analysis: {finished_count} finished, {remaining_count} pending")

                            # Debug: Show some finished repos
                            finished_repos = [repo for repo in full_queue if repo.get("finished", False)]
                            if finished_repos:
                                logger.debug(f"Sample finished repos: {[repo['full_name'] for repo in finished_repos[:5]]}")
                        else:
                            logger.info("Rate limit reached but all repositories completed")
                            logger.info(f"Queue analysis: {finished_count} repositories completed")

                        return {
                            'success': True,  # Partial success
                            'rate_limit_reached': True,
                            'partial_success': True,
                            'error': 'Rate limit reached during PR processing',
                            'repos_processed': repo_index - 1,  # Don't count current repo as processed since it hit rate limit
                            'prs_processed': total_prs_processed
                        }

                    # Check for other failures (non-rate-limit errors)
                    if not pr_result['success']:
                        # Failure during PR processing - cleanup finished repos and save state
                        remaining_count = job_schedule.cleanup_finished_repos()
                        full_queue = job_schedule.get_repo_queue()
                        finished_count = len(full_queue) - remaining_count
                        session.commit()

                        logger.error(f"PR processing failed for {owner}/{repo_name}: {pr_result.get('error', 'Unknown error')}")
                        logger.info(f"Queue analysis: {finished_count} finished, {remaining_count} repositories remaining")

                        # Get current queue state for checkpoint (full queue for analysis)
                        checkpoint_data = pr_result.get('checkpoint_data', {})
                        checkpoint_data['repo_queue'] = job_schedule.get_repo_queue()  # Full queue with finished=true entries

                        return {
                            'success': False,
                            'error': pr_result['error'],
                            'repos_processed': repo_index - 1,
                            'prs_processed': total_prs_processed,
                            'checkpoint_data': checkpoint_data
                        }

                    # Mark this repository as finished in the queue
                    job_schedule.mark_repo_finished(repository.external_id)
                    total_prs_processed += pr_result['prs_processed']

                    # Commit the data for this repository
                    session.commit()
                    prs_in_repo = pr_result.get('prs_processed', 0)
                    total_prs_processed += prs_in_repo

                    logger.info(f"[{owner}/{repo_name}] Repository completed successfully - {prs_in_repo} PRs processed")
                    logger.debug(f"Marked repository {repository.external_id} as finished in queue")

                    # Send detailed progress update
                    repo_progress = 10.0 + repo_index / total_repos * 80.0  # 10% to 90%
                    await websocket_manager.send_progress_update(
                        "github_sync",
                        repo_progress,
                        f"Completed {repo_index}/{total_repos} repositories ({total_prs_processed} PRs total)"
                    )

                    # Check rate limit after each repository
                    if graphql_client.is_rate_limited():
                        logger.warning("GitHub API rate limit reached, stopping gracefully")

                        # Cleanup finished repos and save remaining work
                        remaining_count = job_schedule.cleanup_finished_repos()
                        full_queue = job_schedule.get_repo_queue()
                        finished_count = len(full_queue) - remaining_count
                        session.commit()

                        if remaining_count > 0:
                            logger.info(f"Rate limit reached - {remaining_count} repositories remaining for next run")
                            logger.info(f"Queue analysis: {finished_count} finished, {remaining_count} pending")

                            # Debug: Show some finished repos
                            finished_repos = [repo for repo in full_queue if repo.get("finished", False)]
                            if finished_repos:
                                logger.debug(f"Sample finished repos: {[repo['full_name'] for repo in finished_repos[:5]]}")
                        else:
                            logger.info("Rate limit reached but all repositories completed")
                            logger.info(f"Queue analysis: {finished_count} repositories completed")

                        return {
                            'success': True,  # Partial success
                            'rate_limit_reached': True,
                            'partial_success': True,
                            'error': 'Rate limit threshold reached',
                            'repos_processed': repo_index,
                            'prs_processed': total_prs_processed
                        }

                except Exception as e:
                    logger.error(f"Error processing repository {repository.full_name}: {e}")

                    # Cleanup finished repos and save state
                    remaining_count = job_schedule.cleanup_finished_repos()
                    full_queue = job_schedule.get_repo_queue()
                    finished_count = len(full_queue) - remaining_count
                    session.commit()

                    logger.info(f"Queue analysis: {finished_count} finished, {remaining_count} repositories remaining")

                    return {
                        'success': False,
                        'error': str(e),
                        'repos_processed': repo_index - 1,
                        'prs_processed': total_prs_processed,
                        'checkpoint_data': {
                            'repo_queue': job_schedule.get_repo_queue()  # Full queue for analysis
                        }
                    }

            # All repositories and PRs processed successfully - cleanup will clear all checkpoints
            remaining_count = job_schedule.cleanup_finished_repos()
            if remaining_count == 0:
                logger.info("All repositories completed - all checkpoints cleared")
            else:
                logger.warning(f"Unexpected: {remaining_count} repositories still in queue after completion")

            logger.info(f"GraphQL processing completed successfully")
            return {
                'success': True,
                'rate_limit_reached': False,
                'partial_success': False,  # Complete success - all repositories processed
                'repos_processed': len(repositories),
                'prs_processed': total_prs_processed
            }

    except Exception as e:
        logger.error(f"Error in GraphQL processing: {e}")
        return {
            'success': False,
            'rate_limit_reached': False,
            'partial_success': False,
            'error': str(e),
            'repos_processed': 0,
            'prs_processed': 0,
            'checkpoint_data': {}
        }


async def extract_github_single_repo_prs_session_free(
    client_id: int,
    integration_id: int,
    github_token: str,
    job_schedule_id: int,
    target_repository: str
) -> Dict[str, Any]:
    """
    Session-free version of extract_github_single_repo_prs.
    Processes a single repository without keeping database session open during API calls.
    """
    from app.core.database import get_database
    from app.core.websocket_manager import get_websocket_manager
    from app.jobs.github.github_graphql_client import GitHubGraphQLClient

    try:
        database = get_database()
        websocket_manager = get_websocket_manager()

        # Get repository details with a quick session
        with database.get_read_session_context() as session:
            integration = session.query(Integration).get(integration_id)
            job_schedule = session.query(JobSchedule).get(job_schedule_id)

            repository = session.query(Repository).filter(
                Repository.name == target_repository,
                Repository.client_id == client_id
            ).first()

            if not repository:
                return {'success': False, 'error': f'Repository {target_repository} not found in database. Run repository discovery first.'}

        # Initialize GraphQL client
        graphql_client = GitHubGraphQLClient(github_token)

        # Process PRs for this specific repository
        owner, repo_name = target_repository.split('/', 1)
        logger.info(f"Processing all PRs for {owner}/{repo_name} (session-free)")

        await websocket_manager.send_progress_update("github_sync", 50.0, f"Extracting PRs from {owner}/{repo_name}")

        # Process with fresh session
        with database.get_job_session_context() as session:
            # Re-fetch objects in this session
            integration = session.query(Integration).get(integration_id)
            job_schedule = session.query(JobSchedule).get(job_schedule_id)
            repository = session.query(Repository).filter(
                Repository.name == target_repository,
                Repository.client_id == client_id
            ).first()

            from app.jobs.github.github_graphql_extractor import process_repository_prs_with_graphql
            pr_result = await process_repository_prs_with_graphql(
                session, graphql_client, repository, owner, repo_name, integration, job_schedule, websocket_manager
            )

        if pr_result['success']:
            await websocket_manager.send_progress_update("github_sync", 100.0, f"Completed processing {target_repository}")
            return {
                'success': True,
                'prs_processed': pr_result.get('prs_processed', 0),
                'rate_limit_reached': pr_result.get('rate_limit_reached', False)
            }
        else:
            return pr_result

    except Exception as e:
        logger.error(f"Error in session-free single repo extraction: {e}")
        return {'success': False, 'error': str(e)}


async def process_github_data_with_graphql_session_free(
    client_id: int,
    integration_id: int,
    github_token: str,
    job_schedule_id: int
) -> Dict[str, Any]:
    """
    Session-free version of process_github_data_with_graphql.
    Processes GitHub data without keeping database session open during API calls.
    """
    from app.core.database import get_database
    from app.core.websocket_manager import get_websocket_manager

    try:
        database = get_database()
        websocket_manager = get_websocket_manager()

        logger.info("Starting session-free GraphQL-based GitHub data processing")

        # Process repositories in chunks with fresh sessions
        chunk_size = 5  # Process 5 repositories at a time
        total_processed = 0
        total_prs_processed = 0

        # Get repository list with a quick session
        with database.get_read_session_context() as session:
            repositories = session.query(Repository).filter(
                Repository.client_id == client_id
            ).all()

            repo_list = [(repo.id, repo.name, repo.external_id) for repo in repositories]

        if not repo_list:
            logger.warning("No repositories found for processing")
            return {
                'success': True,
                'repos_processed': 0,
                'prs_processed': 0,
                'rate_limit_reached': False
            }

        logger.info(f"Processing {len(repo_list)} repositories in chunks of {chunk_size}")

        # Process repositories in chunks
        for i in range(0, len(repo_list), chunk_size):
            chunk = repo_list[i:i + chunk_size]

            # Process this chunk with a fresh session
            try:
                with database.get_job_session_context() as session:
                    # Re-fetch integration and job schedule in this session
                    integration = session.query(Integration).get(integration_id)
                    job_schedule = session.query(JobSchedule).get(job_schedule_id)

                    # Process each repository in this chunk
                    for repo_id, repo_name, repo_external_id in chunk:
                        repository = session.query(Repository).get(repo_id)

                        if '/' in repo_name:
                            owner, repo_name_only = repo_name.split('/', 1)

                            # Process this repository
                            from app.jobs.github.github_graphql_client import GitHubGraphQLClient
                            from app.jobs.github.github_graphql_extractor import process_repository_prs_with_graphql

                            graphql_client = GitHubGraphQLClient(github_token)

                            result = await process_repository_prs_with_graphql(
                                session, graphql_client, repository, owner, repo_name_only,
                                integration, job_schedule, websocket_manager
                            )

                            if result['success']:
                                total_prs_processed += result.get('prs_processed', 0)
                                total_processed += 1

                                progress = 10.0 + (total_processed / len(repo_list)) * 80.0
                                await websocket_manager.send_progress_update(
                                    "github_sync", progress,
                                    f"Processed {total_processed}/{len(repo_list)} repositories"
                                )
                            else:
                                logger.warning(f"Failed to process repository {repo_name}: {result.get('error', 'Unknown error')}")

            except Exception as chunk_error:
                logger.error(f"Error processing repository chunk {i//chunk_size + 1}: {chunk_error}")
                # Continue with next chunk instead of failing completely
                continue

        logger.info(f"Session-free GitHub processing completed: {total_processed} repositories, {total_prs_processed} PRs")

        return {
            'success': True,
            'repos_processed': total_processed,
            'prs_processed': total_prs_processed,
            'rate_limit_reached': False,
            'partial_success': False
        }

    except Exception as e:
        logger.error(f"Error in session-free GitHub data processing: {e}")
        return {'success': False, 'error': str(e)}


async def run_github_sync_optimized(
    job_schedule_id: int,
    execution_mode: GitHubExecutionMode = GitHubExecutionMode.ALL,
    target_repository: Optional[str] = None,
    target_repositories: Optional[List[str]] = None,
    update_sync_timestamp: bool = True,
    update_job_schedule: bool = True
):
    """
    Optimized GitHub sync with proper session management to prevent UI blocking.
    Uses session-free approach to prevent connection timeouts during API calls.
    """
    from app.core.database import get_database
    from app.models.unified_models import JobSchedule
    import asyncio

    database = get_database()
    logger.info(f"🚀 Starting optimized GitHub sync (ID: {job_schedule_id})")

    try:
        # Use session-free approach to prevent connection timeouts during long API calls
        # Get job schedule info with a quick session
        with database.get_read_session_context() as session:
            job_schedule = session.query(JobSchedule).filter(JobSchedule.id == job_schedule_id).first()
            if not job_schedule:
                logger.error(f"Job schedule {job_schedule_id} not found")
                return {'success': False, 'error': 'Job schedule not found'}

            # Store job details for session-free operations
            client_id = job_schedule.client_id

        # Add periodic yielding to prevent blocking
        await asyncio.sleep(0)

        # Use session-free execution to prevent connection timeouts
        result = await execute_github_extraction_session_free(
            client_id, None, None, job_schedule_id,  # integration details will be fetched inside
            execution_mode, target_repository, target_repositories,
            update_sync_timestamp, update_job_schedule
        )

        return result

    except Exception as e:
        logger.error(f"Optimized GitHub sync error: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}