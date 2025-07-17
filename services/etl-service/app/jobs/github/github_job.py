"""
GitHub Passive Job

Implements the GitHub sync portion of the Active/Passive Job Model.
This job:
1. Processes staged dev_status data from JiraDevDetailsStaging
2. Discovers repositories using GitHub Search API (incremental & safe)
3. Enriches pull requests using GitHub API (incremental & safe)
4. On success: Truncates staging table, sets Jira job to PENDING, itself to FINISHED
5. On failure: Sets itself to PENDING with appropriate checkpoint data
"""

from sqlalchemy.orm import Session
from app.core.logging_config import get_logger
from app.core.config import AppConfig, get_settings
from app.core.utils import DateTimeHelper
from app.core.websocket_manager import get_websocket_manager
from app.models.unified_models import JobSchedule, JiraDevDetailsStaging, Integration, Repository, PullRequest
from app.jobs.github.github_graphql_client import GitHubGraphQLClient
from app.jobs.github.github_graphql_processor import GitHubGraphQLProcessor
from app.jobs.github.github_graphql_extractor import (
    process_repository_prs_with_graphql, process_repository_prs_with_graphql_recovery
)
from typing import Dict, Any, List
from datetime import datetime, timedelta
import os

logger = get_logger(__name__)


async def run_github_sync(session: Session, job_schedule: JobSchedule):
    """
    Main GitHub sync function.
    
    Args:
        session: Database session
        job_schedule: JobSchedule record for this job
    """
    try:
        logger.info(f"Starting GitHub sync job (ID: {job_schedule.id})")

        # Initialize WebSocket manager and clear previous progress
        websocket_manager = get_websocket_manager()
        websocket_manager.clear_job_progress("github_sync")

        # Get GitHub integration
        await websocket_manager.send_progress_update("github_sync", 5.0, "Initializing GitHub integration...")
        github_integration = session.query(Integration).filter(
            Integration.name == "GitHub"
        ).first()

        if not github_integration:
            error_msg = "No GitHub integration found. Please run initialize_integrations.py first."
            logger.error(f"ERROR: {error_msg}")
            await websocket_manager.send_exception("github_sync", "ERROR", error_msg)
            job_schedule.set_pending_with_checkpoint(error_msg)
            session.commit()
            return

        # Setup GitHub token
        key = AppConfig.load_key()
        github_token = AppConfig.decrypt_token(github_integration.password, key)

        # Process GitHub data with unified queue-based recovery
        if job_schedule.is_recovery_run():
            logger.info("Recovery run detected - resuming from checkpoint")
            await websocket_manager.send_progress_update("github_sync", 15.0, "Resuming from checkpoint...")
        else:
            logger.info("Normal run - starting fresh")
            await websocket_manager.send_progress_update("github_sync", 15.0, "Starting repository discovery...")

        result = await process_github_data_with_graphql(session, github_integration, github_token, job_schedule)
        
        if result['success']:
            # Step 3: Link pull requests with Jira issues using staging data
            # This should happen even on partial success/rate limit to link the PRs that were processed
            logger.info("Step 3: Linking pull requests with Jira issues...")
            await websocket_manager.send_progress_update("github_sync", 95.0, "Linking pull requests with Jira issues...")
            linking_result = link_pull_requests_with_jira_issues(session, github_integration)

            if linking_result['success']:
                result['pr_links_created'] = linking_result['links_created']
                logger.info(f"Successfully linked {linking_result['links_created']} pull requests with Jira issues")
            else:
                logger.warning(f"PR-Issue linking completed with warnings: {linking_result.get('error', 'Unknown error')}")
                await websocket_manager.send_exception("github_sync", "WARNING", f"PR-Issue linking completed with warnings: {linking_result.get('error', 'Unknown error')}")
                result['pr_links_created'] = linking_result.get('links_created', 0)

            # Check if this was a complete success (not partial or rate limited)
            is_complete_success = (
                not result.get('rate_limit_reached', False) and
                not result.get('partial_success', False)
            )

            if is_complete_success:
                # Complete Success: Clean up checkpoint, truncate staging table, set jobs status
                logger.info("Complete success - cleaning up and finishing")

                # Clear checkpoint data
                job_schedule.clear_checkpoints()

                # Truncate staging table
                session.query(JiraDevDetailsStaging).delete()
                logger.info("Staging table truncated")

                # Set Jira job to PENDING and this job to FINISHED
                jira_job = session.query(JobSchedule).filter(JobSchedule.job_name == 'jira_sync').first()
                if jira_job:
                    jira_job.status = 'PENDING'

                job_schedule.set_finished()
                session.commit()

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

                logger.info("GitHub sync completed successfully")
                logger.info(f"   • Repositories processed: {result['repos_processed']}")
                logger.info(f"   • Pull requests processed: {result['prs_processed']}")
                logger.info(f"   • PR-Issue links created: {result.get('pr_links_created', 0)}")
                logger.info(f"   • Staging table cleared")
                logger.info(f"   • Jira job set to PENDING (cycle complete)")

            else:
                # Partial Success or Rate Limit: Keep staging data, keep job PENDING
                logger.info("Partial success or rate limit reached - preserving state")
                await websocket_manager.send_exception("github_sync", "WARNING", "Partial success - rate limit reached, will resume later")

                # Keep GitHub job as PENDING for next run
                job_schedule.status = 'PENDING'
                session.commit()

                # Send partial completion notification
                await websocket_manager.send_completion(
                    "github_sync",
                    False,  # Partial success
                    {
                        'repos_processed': result['repos_processed'],
                        'prs_processed': result['prs_processed'],
                        'pr_links_created': result.get('pr_links_created', 0),
                        'partial_success': True,
                        'rate_limit_reached': result.get('rate_limit_reached', False)
                    }
                )

                logger.info("GitHub sync partially completed")
                logger.info(f"   • Repositories processed: {result['repos_processed']}")
                logger.info(f"   • Pull requests processed: {result['prs_processed']}")
                logger.info(f"   • PR-Issue links created: {result.get('pr_links_created', 0)}")
                logger.info(f"   • Staging data preserved for next run")
                logger.info(f"   • GitHub job remains PENDING")
            
        else:
            # Failure: Set this job back to PENDING with checkpoint
            error_msg = result.get('error', 'Unknown error')
            checkpoint_data = result.get('checkpoint_data', {})

            await websocket_manager.send_exception("github_sync", "ERROR", error_msg, str(checkpoint_data))

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
            session.commit()

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
        
        # Set job back to PENDING on unexpected error
        job_schedule.set_pending_with_checkpoint(str(e))
        session.commit()


async def discover_repositories_from_staging(session: Session, integration: Integration, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Discover repositories combining GitHub Search API and Jira dev_status data.

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
        from app.models.unified_models import Repository, JiraDevDetailsStaging
        from datetime import datetime
        import os

        logger.info("Discovering repositories from combined sources...")
        logger.info("Combining repositories from:")
        logger.info("   • GitHub Search API (with 'health-' filter)")
        logger.info("   • Jira dev_status staging data")

        # Setup GitHub client
        from app.core.config import AppConfig
        key = AppConfig.load_key()
        github_token = AppConfig.decrypt_token(integration.password, key)
        github_client = GitHubClient(github_token)

        # Get organization from environment
        org = os.getenv('GITHUB_ORG', 'wexinc')
        name_filter = os.getenv('GITHUB_REPO_FILTER', 'health-')

        # Step 1: Get repositories from Jira dev_status staging data
        logger.info("Step 1: Extracting repositories from Jira dev_status staging data...")

        staged_data = session.query(JiraDevDetailsStaging).filter(
            JiraDevDetailsStaging.processed == False
        ).all()

        logger.info(f"Found {len(staged_data)} staged dev_status items")

        repo_names_from_jira = set()
        for staging_record in staged_data:
            dev_data = staging_record.get_dev_status_data()
            detail = dev_data.get('detail', [])
            for detail_item in detail:
                pull_requests = detail_item.get('pullRequests', [])
                for pr_data in pull_requests:
                    repo_name = pr_data.get('repositoryName')
                    if repo_name:
                        repo_names_from_jira.add(repo_name)

        logger.info(f"Found {len(repo_names_from_jira)} unique repositories in Jira dev_status data")
        if repo_names_from_jira:
            logger.info(f"Repository names: {', '.join(sorted(list(repo_names_from_jira)[:10]))}{'...' if len(repo_names_from_jira) > 10 else ''}")

        # Step 2: Get repositories from GitHub Search API
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

        # Step 2: Search repositories using GitHub API
        repos_from_search = github_client.search_repositories(org, start_date, end_date, name_filter)
        logger.info(f"Found {len(repos_from_search)} repositories from GitHub Search API")

        # Step 3: Combine both sources
        logger.info("Step 3: Combining repositories from both sources...")

        # Create a set of all repository names to fetch
        all_repo_names = set()

        # Add repositories from GitHub Search API
        for repo in repos_from_search:
            all_repo_names.add(repo['full_name'])

        # Add repositories from Jira dev_status (need to construct full names)
        for repo_name in repo_names_from_jira:
            # Assume they're in the same org if not already full name
            if '/' not in repo_name:
                full_name = f"{org}/{repo_name}"
            else:
                full_name = repo_name
            all_repo_names.add(full_name)

        logger.info(f"Total unique repositories to process: {len(all_repo_names)}")

        # Step 4: Fetch detailed repository data for all repositories
        logger.info("Step 4: Fetching detailed repository data...")

        all_repos = []

        # Add repos from search (already have detailed data)
        all_repos.extend(repos_from_search)

        # For repos from Jira that weren't found in search, fetch them individually
        search_repo_names = {repo['full_name'] for repo in repos_from_search}
        missing_repo_names = all_repo_names - search_repo_names

        if missing_repo_names:
            logger.info(f"Fetching {len(missing_repo_names)} additional repositories from Jira dev_status...")
            for full_name in missing_repo_names:
                try:
                    owner, repo_name = full_name.split('/', 1)
                    # Use the GitHub client's _make_request method to fetch individual repo
                    endpoint = f"repos/{owner}/{repo_name}"
                    repo_data = github_client._make_request(endpoint)
                    if repo_data:
                        all_repos.append(repo_data)
                        logger.debug(f"Fetched: {full_name}")
                    else:
                        logger.warning(f"Not found: {full_name}")
                except Exception as e:
                    logger.warning(f"Error fetching {full_name}: {e}")

        logger.info(f"Total repositories to process: {len(all_repos)}")

        if not all_repos:
            logger.warning("No repositories found from either source")
            return {
                'success': True,
                'repositories': [],
                'repos_processed': 0
            }

        # Step 5: Process repositories using bulk operations
        logger.info("Step 5: Processing repositories for database insertion...")

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
                logger.debug(f"Processing repository {repo_index}/{len(all_repos)}: {repo_data.get('full_name', 'unknown')}")

                # Check if repository already exists
                external_id = str(repo_data['id'])
                if external_id in existing_repos:
                    # For existing repositories, just skip for now (could implement updates later)
                    repos_skipped += 1
                else:
                    # Process repository data using the processor
                    repo_processed = temp_processor.process_repository_data(repo_data)
                    if repo_processed:
                        repos_to_insert.append(repo_processed)

            except Exception as e:
                logger.error(f"Error processing repository {repo_data.get('full_name', 'unknown')}: {e}")
                continue

        # Bulk insert new repositories
        if repos_to_insert:
            logger.info(f"Performing bulk insert of {len(repos_to_insert)} repositories...")
            from app.models.unified_models import Repository
            session.bulk_insert_mappings(Repository, repos_to_insert)
            session.commit()
            logger.info(f"Successfully inserted {len(repos_to_insert)} repositories")

        total_processed = len(repos_to_insert) + repos_skipped
        logger.info(f"Repository discovery completed!")
        logger.info(f"   • Repositories processed: {total_processed}")
        logger.info(f"   • New repositories inserted: {len(repos_to_insert)}")
        logger.info(f"   • Repositories skipped (already exist): {repos_skipped}")

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


def link_pull_requests_with_jira_issues(session: Session, github_integration: Integration) -> Dict[str, Any]:
    """
    Link pull requests with Jira issues using data from jira_dev_details_staging.

    The staging table already contains the issue_id, so we only need to:
    1. Parse JSON to get repositoryName and pullRequestNumber
    2. Find matching PullRequest records
    3. Link them directly to the staging_record.issue_id

    Args:
        session: Database session
        github_integration: GitHub integration object

    Returns:
        Dictionary with linking results
    """
    try:
        from app.models.unified_models import PullRequest, Repository, JiraDevDetailsStaging, Issue

        logger.info("Starting PR-Issue linking process...")

        # Get all unprocessed staging records
        staging_records = session.query(JiraDevDetailsStaging).filter(
            JiraDevDetailsStaging.processed == False
        ).all()

        if not staging_records:
            logger.info("No staging records found for PR-Issue linking")
            return {
                'success': True,
                'links_created': 0,
                'message': 'No staging data to process'
            }

        logger.info(f"Found {len(staging_records)} staging records to process")

        # Get all repositories for this client to create a lookup map
        repositories = session.query(Repository).filter(
            Repository.client_id == github_integration.client_id,
            Repository.active == True
        ).all()

        # Create repository lookup maps
        repo_by_name = {}  # repo_name -> Repository object
        repo_by_full_name = {}  # full_name -> Repository object

        for repo in repositories:
            # Map by just the repo name (last part of full_name)
            if repo.full_name and '/' in repo.full_name:
                repo_name = repo.full_name.split('/')[-1]
                repo_by_name[repo_name] = repo

            # Map by full name
            if repo.full_name:
                repo_by_full_name[repo.full_name] = repo

        logger.info(f"Created lookup maps for {len(repositories)} repositories")

        links_created = 0
        records_processed = 0

        # Process each staging record
        for staging_record in staging_records:
            try:
                # Get the dev_status data
                dev_data = staging_record.get_dev_status_data()
                if not dev_data:
                    continue

                # Extract pull request information from dev_status
                detail = dev_data.get('detail', [])
                for detail_item in detail:
                    pull_requests = detail_item.get('pullRequests', [])

                    for pr_data in pull_requests:
                        try:
                            # Extract PR linking information
                            repo_name = pr_data.get('repositoryName')
                            pr_number = pr_data.get('pullRequestNumber')

                            if not repo_name or not pr_number:
                                logger.debug(f"Missing repo_name or pr_number in staging data: {pr_data}")
                                continue

                            # Find the repository
                            repository = None

                            # Try exact repo name match first
                            if repo_name in repo_by_name:
                                repository = repo_by_name[repo_name]
                            # Try full name match (in case repo_name includes org)
                            elif repo_name in repo_by_full_name:
                                repository = repo_by_full_name[repo_name]
                            # Try with org prefix
                            else:
                                org = os.getenv('GITHUB_ORG', 'wexinc')
                                full_name_with_org = f"{org}/{repo_name}"
                                if full_name_with_org in repo_by_full_name:
                                    repository = repo_by_full_name[full_name_with_org]

                            if not repository:
                                logger.debug(f"Repository not found for name: {repo_name}")
                                continue

                            # Find the pull request
                            pull_request = session.query(PullRequest).filter(
                                PullRequest.repository_id == repository.id,
                                PullRequest.number == pr_number,
                                PullRequest.client_id == github_integration.client_id
                            ).first()

                            if not pull_request:
                                logger.debug(f"Pull request not found: {repo_name}#{pr_number}")
                                continue

                            # Check if already linked
                            if pull_request.issue_id:
                                logger.debug(f"Pull request {repo_name}#{pr_number} already linked to issue")
                                continue

                            # Link the pull request to the Jira issue
                            pull_request.issue_id = staging_record.issue_id
                            links_created += 1

                            logger.debug(f"Linked PR {repo_name}#{pr_number} to issue ID {staging_record.issue_id}")

                        except Exception as e:
                            logger.warning(f"Error processing PR data {pr_data}: {e}")
                            continue

                # Mark staging record as processed
                staging_record.processed = True
                records_processed += 1

                if records_processed % 10 == 0:
                    logger.info(f"Processed {records_processed}/{len(staging_records)} staging records, created {links_created} links so far...")
                    session.commit()  # Commit periodically

            except Exception as e:
                logger.error(f"Error processing staging record {staging_record.id}: {e}")
                continue

        # Final commit
        session.commit()

        logger.info(f"PR-Issue linking completed!")
        logger.info(f"   • Staging records processed: {records_processed}")
        logger.info(f"   • PR-Issue links created: {links_created}")

        return {
            'success': True,
            'links_created': links_created,
            'records_processed': records_processed
        }

    except Exception as e:
        logger.error(f"Error in PR-Issue linking: {e}")
        return {
            'success': False,
            'error': str(e),
            'links_created': 0,
            'records_processed': 0
        }


async def process_github_data_with_graphql(session: Session, integration: Integration, github_token: str, job_schedule: JobSchedule) -> Dict[str, Any]:
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

        # Initialize GraphQL client
        from app.core.config import get_settings
        settings = get_settings()
        graphql_client = GitHubGraphQLClient(github_token, rate_limit_threshold=settings.GITHUB_RATE_LIMIT_THRESHOLD)

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
            repos_result = await discover_repositories_from_staging(session, integration, job_schedule)
            if not repos_result['success']:
                return repos_result

            repositories = repos_result['repositories']
            logger.info(f"Found {len(repositories)} repositories to process")

            # Initialize queue for normal run
            job_schedule.initialize_repo_queue(repositories)

        # Step 2: Process pull requests using GraphQL
        total_prs_processed = 0

        for repo_index, repository in enumerate(repositories, 1):
            try:
                owner, repo_name = repository.full_name.split('/', 1)
                logger.info(f"Processing repository {repo_index}/{len(repositories)}: {owner}/{repo_name}")

                # Process PRs for this repository using GraphQL
                pr_result = process_repository_prs_with_graphql(
                    session, graphql_client, repository, owner, repo_name, integration, job_schedule
                )

                # Check if rate limit was reached during PR processing BEFORE marking as finished
                if pr_result.get('rate_limit_reached', False):
                    logger.warning("Rate limit threshold reached during PR processing, stopping gracefully")

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
                        'error': 'Rate limit threshold reached during PR processing',
                        'repos_processed': repo_index - 1,  # Don't count current repo as processed since it hit rate limit
                        'prs_processed': total_prs_processed
                    }

                if not pr_result['success']:
                    # Failure during PR processing - cleanup finished repos and save state
                    remaining_count = job_schedule.cleanup_finished_repos()
                    full_queue = job_schedule.get_repo_queue()
                    finished_count = len(full_queue) - remaining_count
                    session.commit()

                    logger.error(f"PR processing failed for {owner}/{repo_name}")
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
                logger.info(f"Committed data for repository {owner}/{repo_name}")
                logger.debug(f"Marked repository {repository.external_id} as finished in queue")

                # Check rate limit after each repository
                if graphql_client.should_stop_for_rate_limit():
                    logger.warning("Rate limit threshold reached, stopping gracefully")

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