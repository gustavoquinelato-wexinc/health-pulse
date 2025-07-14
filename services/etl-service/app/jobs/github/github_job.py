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


def run_github_sync(session: Session, job_schedule: JobSchedule):
    """
    Main GitHub sync function.
    
    Args:
        session: Database session
        job_schedule: JobSchedule record for this job
    """
    try:
        logger.info(f"🐙 Starting GitHub sync job (ID: {job_schedule.id})")
        
        # Get GitHub integration
        github_integration = session.query(Integration).filter(
            Integration.name == "GitHub"
        ).first()
        
        if not github_integration:
            error_msg = "No GitHub integration found. Please run initialize_integrations.py first."
            logger.error(f"❌ {error_msg}")
            job_schedule.set_pending_with_checkpoint(error_msg)
            session.commit()
            return
        
        # Setup GitHub token
        key = AppConfig.load_key()
        github_token = AppConfig.decrypt_token(github_integration.password, key)
        
        # Check if this is a recovery run
        if job_schedule.is_recovery_run():
            logger.info("🔄 Recovery run detected - resuming from checkpoint")
            result = process_github_data_with_graphql_recovery(session, github_integration, github_token, job_schedule)
        else:
            logger.info("🆕 Normal run - starting fresh")
            result = process_github_data_with_graphql(session, github_integration, github_token, job_schedule)
        
        if result['success']:
            # Success: Truncate staging table, set Jira job to PENDING, this job to FINISHED
            session.query(JiraDevDetailsStaging).delete()
            
            jira_job = session.query(JobSchedule).filter(JobSchedule.job_name == 'jira_sync').first()
            if jira_job:
                jira_job.status = 'PENDING'
            
            job_schedule.set_finished()
            session.commit()
            
            logger.info(f"✅ GitHub sync completed successfully")
            logger.info(f"   • Repositories processed: {result['repos_processed']}")
            logger.info(f"   • Pull requests processed: {result['prs_processed']}")
            logger.info(f"   • Staging table cleared")
            logger.info(f"   • Jira job set to PENDING (cycle complete)")
            
        else:
            # Failure: Set this job back to PENDING with checkpoint
            error_msg = result.get('error', 'Unknown error')
            checkpoint_data = result.get('checkpoint_data', {})

            job_schedule.set_pending_with_checkpoint(
                error_msg,
                repo_checkpoint=checkpoint_data.get('repo_checkpoint'),
                current_repo_id=checkpoint_data.get('current_repo_id'),
                last_pr_cursor=checkpoint_data.get('last_pr_cursor'),
                current_pr_node_id=checkpoint_data.get('current_pr_node_id'),
                last_commit_cursor=checkpoint_data.get('last_commit_cursor'),
                last_review_cursor=checkpoint_data.get('last_review_cursor'),
                last_comment_cursor=checkpoint_data.get('last_comment_cursor'),
                last_review_thread_cursor=checkpoint_data.get('last_review_thread_cursor')
            )
            session.commit()

            logger.error(f"❌ GitHub sync failed: {error_msg}")
            logger.info(f"   • Checkpoint data saved for recovery")
            
    except Exception as e:
        logger.error(f"❌ GitHub sync job error: {e}")
        import traceback
        traceback.print_exc()
        
        # Set job back to PENDING on unexpected error
        job_schedule.set_pending_with_checkpoint(str(e))
        session.commit()


def discover_repositories_from_staging(session: Session, integration: Integration, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Discover repositories from staged Jira dev_status data.

    Args:
        session: Database session
        integration: GitHub integration object
        job_schedule: Job schedule for checkpoint management

    Returns:
        Dictionary with discovery results containing repositories list
    """
    try:
        logger.info("🔍 Discovering repositories from staging data...")

        # Get staged dev_status data
        staged_data = session.query(JiraDevDetailsStaging).filter(
            JiraDevDetailsStaging.processed == False
        ).all()

        logger.info(f"Found {len(staged_data)} staged dev_status items")

        # Extract repository names from dev_status data
        repo_names_from_dev_status = set()
        for staging_record in staged_data:
            dev_data = staging_record.get_dev_status_data()
            detail = dev_data.get('detail', [])
            for detail_item in detail:
                pull_requests = detail_item.get('pullRequests', [])
                for pr_data in pull_requests:
                    repo_name = pr_data.get('repositoryName')
                    if repo_name:
                        repo_names_from_dev_status.add(repo_name)

        logger.info(f"Found {len(repo_names_from_dev_status)} unique repositories in dev_status data")

        # Get existing repositories from database
        repositories = session.query(Repository).filter(
            Repository.client_id == integration.client_id,
            Repository.active == True
        ).all()

        logger.info(f"Found {len(repositories)} existing repositories in database")

        return {
            'success': True,
            'repositories': repositories,
            'repos_processed': len(repositories)
        }

    except Exception as e:
        logger.error(f"Error discovering repositories: {e}")
        return {
            'success': False,
            'error': str(e),
            'repositories': [],
            'repos_processed': 0
        }


def process_github_data_with_graphql(session: Session, integration: Integration, github_token: str, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Process GitHub data using GraphQL API for efficient data fetching.

    Args:
        session: Database session
        integration: GitHub integration object
        github_token: Decrypted GitHub token
        job_schedule: Job schedule for checkpoint management

    Returns:
        Dictionary with processing results
    """
    try:
        logger.info("🚀 Starting GraphQL-based GitHub data processing")

        # Initialize GraphQL client
        graphql_client = GitHubGraphQLClient(github_token, rate_limit_threshold=500)

        # Step 1: Discover repositories (keep existing logic for now)
        repos_result = discover_repositories_from_staging(session, integration, job_schedule)
        if not repos_result['success']:
            return repos_result

        repositories = repos_result['repositories']
        logger.info(f"📁 Found {len(repositories)} repositories to process")

        # Step 2: Process pull requests using GraphQL
        total_prs_processed = 0

        for repo_index, repository in enumerate(repositories, 1):
            try:
                owner, repo_name = repository.full_name.split('/', 1)
                logger.info(f"🔄 Processing repository {repo_index}/{len(repositories)}: {owner}/{repo_name}")

                # Process PRs for this repository using GraphQL
                pr_result = process_repository_prs_with_graphql(
                    session, graphql_client, repository, owner, repo_name, integration, job_schedule
                )

                if not pr_result['success']:
                    # Save checkpoint and return failure
                    return {
                        'success': False,
                        'error': pr_result['error'],
                        'repos_processed': repo_index - 1,
                        'prs_processed': total_prs_processed,
                        'checkpoint_data': {
                            'repo_checkpoint': repository.repo_updated_at,
                            'current_repo_id': repository.external_id,
                            **pr_result.get('checkpoint_data', {})
                        }
                    }

                total_prs_processed += pr_result['prs_processed']

                # Check rate limit after each repository
                if graphql_client.should_stop_for_rate_limit():
                    logger.warning("⚠️ Rate limit threshold reached, stopping gracefully")
                    return {
                        'success': False,
                        'error': 'Rate limit threshold reached',
                        'repos_processed': repo_index,
                        'prs_processed': total_prs_processed,
                        'checkpoint_data': {
                            'repo_checkpoint': repository.repo_updated_at,
                            'current_repo_id': None  # Completed this repo
                        }
                    }

            except Exception as e:
                logger.error(f"❌ Error processing repository {repository.full_name}: {e}")
                continue

        logger.info(f"✅ GraphQL processing completed successfully")
        return {
            'success': True,
            'repos_processed': len(repositories),
            'prs_processed': total_prs_processed
        }

    except Exception as e:
        logger.error(f"❌ Error in GraphQL processing: {e}")
        return {
            'success': False,
            'error': str(e),
            'repos_processed': 0,
            'prs_processed': 0,
            'checkpoint_data': {}
        }

def process_github_data_with_graphql_recovery(session: Session, integration: Integration, github_token: str, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Process GitHub data using GraphQL API in recovery mode.

    Args:
        session: Database session
        integration: GitHub integration object
        github_token: Decrypted GitHub token
        job_schedule: Job schedule with checkpoint data

    Returns:
        Dictionary with processing results
    """
    try:
        logger.info("🔄 Starting GraphQL-based GitHub data processing (RECOVERY MODE)")

        # Initialize GraphQL client
        graphql_client = GitHubGraphQLClient(github_token, rate_limit_threshold=500)

        # Get checkpoint state
        checkpoint_state = job_schedule.get_checkpoint_state()
        current_repo_id = checkpoint_state['current_repo_id']

        logger.info(f"📍 Resuming from repository ID: {current_repo_id}")

        # Find the repository to resume from
        repository = session.query(Repository).filter(
            Repository.external_id == current_repo_id,
            Repository.client_id == integration.client_id
        ).first()

        if not repository:
            logger.error(f"❌ Repository with ID {current_repo_id} not found")
            return {
                'success': False,
                'error': f'Repository with ID {current_repo_id} not found',
                'repos_processed': 0,
                'prs_processed': 0,
                'checkpoint_data': {}
            }

        owner, repo_name = repository.full_name.split('/', 1)
        logger.info(f"🔄 Resuming processing for repository: {owner}/{repo_name}")

        # Process PRs for this repository using GraphQL with recovery
        pr_result = process_repository_prs_with_graphql_recovery(
            session, graphql_client, repository, owner, repo_name, integration, job_schedule
        )

        if not pr_result['success']:
            return {
                'success': False,
                'error': pr_result['error'],
                'repos_processed': 0,
                'prs_processed': 0,
                'checkpoint_data': {
                    'current_repo_id': current_repo_id,
                    **pr_result.get('checkpoint_data', {})
                }
            }

        # After successful recovery, continue with remaining repositories if any
        remaining_repos = session.query(Repository).filter(
            Repository.repo_updated_at > repository.repo_updated_at,
            Repository.client_id == integration.client_id
        ).order_by(Repository.repo_updated_at).all()

        total_prs_processed = pr_result['prs_processed']

        for repo_index, next_repository in enumerate(remaining_repos, 1):
            try:
                next_owner, next_repo_name = next_repository.full_name.split('/', 1)
                logger.info(f"🔄 Processing remaining repository {repo_index}/{len(remaining_repos)}: {next_owner}/{next_repo_name}")

                # Process PRs for this repository using GraphQL
                next_pr_result = process_repository_prs_with_graphql(
                    session, graphql_client, next_repository, next_owner, next_repo_name, integration, job_schedule
                )

                if not next_pr_result['success']:
                    return {
                        'success': False,
                        'error': next_pr_result['error'],
                        'repos_processed': repo_index,
                        'prs_processed': total_prs_processed,
                        'checkpoint_data': {
                            'repo_checkpoint': next_repository.repo_updated_at,
                            'current_repo_id': next_repository.external_id,
                            **next_pr_result.get('checkpoint_data', {})
                        }
                    }

                total_prs_processed += next_pr_result['prs_processed']

            except Exception as e:
                logger.error(f"❌ Error processing repository {next_repository.full_name}: {e}")
                continue

        logger.info(f"✅ GraphQL recovery processing completed successfully")
        return {
            'success': True,
            'repos_processed': 1 + len(remaining_repos),
            'prs_processed': total_prs_processed
        }

    except Exception as e:
        logger.error(f"❌ Error in GraphQL recovery processing: {e}")
        return {
            'success': False,
            'error': str(e),
            'repos_processed': 0,
            'prs_processed': 0,
            'checkpoint_data': {}
        }
