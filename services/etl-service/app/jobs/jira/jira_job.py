"""
Jira Passive Job

Implements the Jira sync portion of the Active/Passive Job Model.
This job:
1. Extracts all relevant issues from Jira
2. For each issue, calls the /dev_status endpoint
3. Stores raw dev_status JSON in JiraDevDetailsStaging table
4. On success: Sets GitHub job to PENDING and itself to FINISHED
5. On failure: Sets itself to PENDING with checkpoint data
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.logging_config import get_logger
from app.core.config import AppConfig, get_settings
from app.core.utils import DateTimeHelper
from app.core.websocket_manager import get_websocket_manager

from app.models.unified_models import JobSchedule, Integration, WorkItem, Tenant
from typing import Dict, Any, Optional, List
from enum import Enum
import asyncio


class JiraExecutionMode(Enum):
    """Jira job execution modes."""
    ISSUETYPES = "issuetypes"      # Extract issue types and projects only
    STATUSES = "statuses"          # Extract statuses and project links only
    ISSUES = "issues"              # Extract issues, changelogs, dev_status
    CUSTOM_QUERY = "custom_query"  # Execute custom JQL query
    ALL = "all"                    # Full extraction (current production behavior)
import os

logger = get_logger(__name__)


async def execute_jira_extraction_by_mode(
    session, jira_integration, jira_client, job_schedule,
    execution_mode: JiraExecutionMode, custom_query: Optional[str], target_projects: Optional[List[str]],
    update_sync_timestamp: bool = True, update_job_schedule: bool = True
) -> Dict[str, Any]:
    """
    Execute Jira extraction based on the specified mode.

    Args:
        session: Database session
        jira_integration: Jira integration instance
        jira_client: Jira API client
        job_schedule: Job schedule instance
        execution_mode: Execution mode
        custom_query: Custom JQL query (for custom_query mode)
        target_projects: Target projects filter

    Returns:
        Extraction result dictionary
    """
    try:
        if execution_mode == JiraExecutionMode.ISSUETYPES:
            logger.info("Executing ISSUETYPES mode - extracting issue types and projects")
            from app.jobs.jira.jira_extractors import extract_projects_and_issuetypes
            from app.core.logging_config import JobLogger
            job_logger = JobLogger("Jira")
            result = extract_projects_and_issuetypes(session, jira_client, jira_integration, job_logger)
            return {'success': True, **result}

        elif execution_mode == JiraExecutionMode.STATUSES:
            logger.info("Executing STATUSES mode - extracting statuses and project links")
            from app.jobs.jira.jira_extractors import extract_projects_and_statuses
            from app.core.logging_config import JobLogger
            job_logger = JobLogger("Jira")
            result = extract_projects_and_statuses(session, jira_client, jira_integration, job_logger)
            return {'success': True, **result}

        elif execution_mode == JiraExecutionMode.ISSUES:
            logger.info("Executing ISSUES mode - extracting issues, changelogs, and dev_status")
            from app.jobs.jira.jira_extractors import extract_work_items_and_changelogs
            from app.core.logging_config import JobLogger
            job_logger = JobLogger("Jira")
            websocket_manager = get_websocket_manager()
            result = await extract_work_items_and_changelogs(
                session, jira_client, jira_integration, job_logger,
                websocket_manager=websocket_manager,
                update_sync_timestamp=update_sync_timestamp,
                job_schedule=job_schedule
            )
            return {'success': True, **result}

        elif execution_mode == JiraExecutionMode.CUSTOM_QUERY:
            logger.info("Executing CUSTOM_QUERY mode - using provided JQL query")
            if not custom_query:
                return {'success': False, 'error': 'Custom query mode requires a JQL query'}
            return await extract_jira_custom_query(session, jira_integration, jira_client, job_schedule, custom_query, update_sync_timestamp)

        elif execution_mode == JiraExecutionMode.ALL:
            logger.info("Executing ALL mode - full extraction (production behavior)")
            return await extract_jira_issues_and_dev_status(session, jira_integration, jira_client, job_schedule)

        else:
            return {'success': False, 'error': f'Unknown execution mode: {execution_mode}'}

    except Exception as e:
        logger.error(f"Error in Jira extraction mode {execution_mode}: {e}")
        return {'success': False, 'error': str(e)}


async def execute_jira_extraction_session_free(
    tenant_id: int,
    integration_id: int,
    jira_client,
    job_schedule_id: int,
    execution_mode: JiraExecutionMode,
    custom_query: Optional[str] = None,
    target_projects: Optional[List[str]] = None,
    update_sync_timestamp: bool = True,
    update_job_schedule: bool = True
) -> Dict[str, Any]:
    """
    Execute Jira extraction without keeping a database session open during API calls.
    This prevents connection timeouts and detached instance errors.
    """
    from app.core.database import get_database
    from sqlalchemy import func

    try:
        # Create fresh session for each database operation
        database = get_database()

        # Get integration details (fetch from job schedule if not provided)
        with database.get_read_session_context() as session:
            if integration_id is None:
                # Get integration from job schedule
                job_schedule = session.query(JobSchedule).get(job_schedule_id)
                if not job_schedule:
                    return {'success': False, 'error': 'Job schedule not found'}

                integration = session.query(Integration).filter(
                    Integration.tenant_id == tenant_id,
                    func.upper(Integration.provider) == 'JIRA'
                ).first()

                if not integration:
                    return {'success': False, 'error': 'Jira integration not found for client'}

                integration_id = integration.id
            else:
                integration = session.query(Integration).filter(
                    Integration.id == integration_id,
                Integration.tenant_id == tenant_id
            ).first()

            if not integration:
                return {'success': False, 'error': 'Integration not found'}

            # Store integration details for jira_client creation if needed
            integration_username = integration.username
            integration_password = integration.password
            integration_url = integration.base_url

        # Create jira_client if not provided
        if jira_client is None:
            from app.jobs.jira import JiraAPIClient
            from app.core.config import AppConfig
            from app.core.config import get_settings

            key = AppConfig.load_key()
            jira_token = AppConfig.decrypt_token(integration_password, key)
            jira_client = JiraAPIClient(
                username=integration_username,
                token=jira_token,
                base_url=integration_url
            )

        # Execute the extraction mode without an open session
        if execution_mode == JiraExecutionMode.ISSUETYPES:
            logger.info("Executing ISSUETYPES mode - extracting issue types and statuses")
            from app.jobs.jira.jira_extractors import extract_issue_types_and_statuses

            with database.get_write_session_context() as session:
                # Re-fetch integration in new session
                integration = session.query(Integration).get(integration_id)
                result = await extract_issue_types_and_statuses(session, jira_client, integration, update_sync_timestamp)
            return {'success': True, **result}

        elif execution_mode == JiraExecutionMode.STATUSES:
            logger.info("Executing STATUSES mode - extracting statuses only")
            from app.jobs.jira.jira_extractors import extract_statuses_only

            with database.get_write_session_context() as session:
                integration = session.query(Integration).get(integration_id)
                result = await extract_statuses_only(session, jira_client, integration, update_sync_timestamp)
            return {'success': True, **result}

        elif execution_mode == JiraExecutionMode.ISSUES:
            logger.info("Executing ISSUES mode - extracting issues, changelogs, and dev_status")
            from app.jobs.jira.jira_extractors import extract_work_items_and_changelogs_session_free
            from app.core.logging_config import JobLogger
            from app.core.websocket_manager import get_websocket_manager

            job_logger = JobLogger("Jira")
            websocket_manager = get_websocket_manager()

            # Use session-free extraction to prevent connection timeouts
            result = await extract_work_items_and_changelogs_session_free(
                tenant_id, integration_id, jira_client, job_logger,
                websocket_manager=websocket_manager,
                update_sync_timestamp=update_sync_timestamp
            )
            return result

        elif execution_mode == JiraExecutionMode.CUSTOM_QUERY:
            logger.info("Executing CUSTOM_QUERY mode - using provided JQL query")
            if not custom_query:
                return {'success': False, 'error': 'Custom query mode requires a JQL query'}

            with database.get_write_session_context() as session:
                integration = session.query(Integration).get(integration_id)
                job_schedule = session.query(JobSchedule).get(job_schedule_id)
                result = await extract_jira_custom_query(session, integration, jira_client, job_schedule, custom_query, update_sync_timestamp)
            return result

        elif execution_mode == JiraExecutionMode.ALL:
            logger.info("Executing ALL mode - full extraction (production behavior)")

            with database.get_write_session_context() as session:
                integration = session.query(Integration).get(integration_id)
                job_schedule = session.query(JobSchedule).get(job_schedule_id)
                result = await extract_jira_issues_and_dev_status(session, integration, jira_client, job_schedule)
            return result

        else:
            return {'success': False, 'error': f'Unknown execution mode: {execution_mode}'}

    except Exception as e:
        logger.error(f"Error in session-free Jira extraction: {e}")
        return {'success': False, 'error': str(e)}


async def extract_jira_custom_query(session, jira_integration, jira_client, job_schedule, custom_query: str, update_sync_timestamp: bool = True) -> Dict[str, Any]:
    """
    Extract Jira issues using a custom JQL query.

    Args:
        session: Database session
        jira_integration: Jira integration instance
        jira_client: Jira API client
        job_schedule: Job schedule instance
        custom_query: Custom JQL query string

    Returns:
        Extraction result dictionary
    """
    try:
        logger.info(f"Executing custom JQL query: {custom_query}")

        from app.jobs.jira.jira_extractors import extract_work_items_and_changelogs
        from app.core.logging_config import JobLogger

        job_logger = JobLogger("Jira")
        websocket_manager = get_websocket_manager()

        # Store original JQL query method and replace with custom query
        original_get_issues = jira_client.get_issues_updated_since

        def custom_get_issues(start_date=None, max_results=50, next_page_token=None):
            """Custom issues getter that uses the provided JQL query with NEW enhanced API."""
            try:
                # Use the NEW enhanced JQL API instead of deprecated endpoint
                import requests

                request_body = {
                    'jql': custom_query,
                    'maxResults': min(max_results, 100),  # API limit is 100
                    'fields': [
                        # Standard fields
                        'key', 'summary', 'description', 'status', 'assignee', 'reporter', 'creator',
                        'priority', 'labels', 'components', 'versions', 'fixVersions', 'issuetype',
                        'project', 'created', 'updated', 'resolutiondate', 'resolution', 'environment',
                        'attachment', 'parent',
                        # Custom fields used in the system
                        'customfield_10000',  # Code changed indicator
                        'customfield_10011',  # Epic Name field
                        'customfield_10024',  # Story points
                        'customfield_10110',  # aha_epic_url (custom_field_01)
                        'customfield_10128',  # Team custom field
                        'customfield_10150',  # aha_initiative (custom_field_02)
                        'customfield_10218',  # Risk assessment
                        'customfield_10222',  # Acceptance criteria
                        'customfield_10359',  # aha_project_code (custom_field_03)
                        'customfield_10414',  # project_code (custom_field_04)
                        'customfield_12103'   # aha_milestone (custom_field_05)
                    ],
                    'expand': 'changelog'
                }

                if next_page_token:
                    request_body['nextPageToken'] = next_page_token

                response = requests.post(
                    f"{jira_client.base_url}/rest/api/latest/search/jql",
                    auth=(jira_client.username, jira_client.token),
                    json=request_body,
                    headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                    timeout=30
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error executing custom JQL query with new API: {e}")
                raise

        # Temporarily replace the method
        jira_client.get_issues_updated_since = custom_get_issues

        try:
            # Execute the extraction with the custom query
            result = await extract_work_items_and_changelogs(
                session, jira_client, jira_integration, job_logger,
                start_date=None,  # Not used with custom query
                websocket_manager=websocket_manager,
                update_sync_timestamp=update_sync_timestamp,
                job_schedule=job_schedule
            )

            logger.info(f"Custom query extraction completed: {result.get('issues_processed', 0)} issues processed")
            return {'success': True, **result}

        finally:
            # Restore original method
            jira_client.get_issues_updated_since = original_get_issues

    except Exception as e:
        logger.error(f"Error in custom JQL query extraction: {e}")
        return {'success': False, 'error': str(e)}


async def run_jira_sync(
    session: Session,
    job_schedule: JobSchedule,
    execution_mode: JiraExecutionMode = JiraExecutionMode.ALL,
    custom_query: Optional[str] = None,
    target_projects: Optional[List[str]] = None,
    update_sync_timestamp: bool = True,
    update_job_schedule: bool = True
):
    """
    Main Jira sync function with execution mode support.

    Args:
        session: Database session
        job_schedule: JobSchedule record for this job
        execution_mode: Execution mode (issuetypes, statuses, issues, custom_query, all)
        custom_query: Custom JQL query (for custom_query mode)
        target_projects: Specific projects to process (optional filter)
        update_sync_timestamp: Whether to update integration.last_sync_at (default: True)
        update_job_schedule: Whether to update job_schedule.status (default: True)
    """
    try:
        logger.info(f"Starting Jira sync job (ID: {job_schedule.id}, Mode: {execution_mode.value})")

        # Send status update that job is running
        if update_job_schedule:
            from app.core.websocket_manager import get_websocket_manager
            websocket_manager = get_websocket_manager()
            await websocket_manager.send_status_update(
                "Jira",
                "RUNNING",
                {"message": "Jira sync job is now running"}
            )

        # Log execution parameters
        if execution_mode == JiraExecutionMode.CUSTOM_QUERY:
            logger.info(f"Custom JQL Query: {custom_query}")
        if target_projects:
            logger.info(f"Target Projects: {target_projects}")

        # SECURITY: Get Jira integration using job_schedule.integration_id for client isolation
        if job_schedule.integration_id:
            jira_integration = session.query(Integration).filter(
                Integration.id == job_schedule.integration_id,
                Integration.tenant_id == job_schedule.tenant_id  # Double-check client isolation
            ).first()
        else:
            # Fallback: Get by name and tenant_id (for backward compatibility)
            jira_integration = session.query(Integration).filter(
                func.upper(Integration.provider) == "JIRA",
                Integration.tenant_id == job_schedule.tenant_id
            ).first()

        if not jira_integration:
            error_msg = f"No Jira integration found for client {job_schedule.tenant_id}. Please check integration setup."
            logger.error(f"ERROR: {error_msg}")
            job_schedule.set_pending_with_checkpoint(error_msg)
            session.commit()
            return
        
        # Store integration details for session-free operations
        integration_id = jira_integration.id
        integration_username = jira_integration.username
        integration_password = jira_integration.password
        integration_url = jira_integration.base_url
        tenant_id = job_schedule.tenant_id
        job_schedule_id = job_schedule.id

        # Setup Jira client
        from app.jobs.jira import JiraAPITenant

        key = AppConfig.load_key()
        jira_token = AppConfig.decrypt_token(integration_password, key)
        jira_client = JiraAPITenant(
            username=integration_username,
            token=jira_token,
            base_url=integration_url
        )

        # Set job as running before closing session
        if update_job_schedule:
            job_schedule.set_running()
            session.commit()

        # Close the session before long-running API operations
        session.close()

        # Execute data fetching without an open session
        result = await execute_jira_extraction_session_free(
            tenant_id, integration_id, jira_client, job_schedule_id,
            execution_mode, custom_query, target_projects,
            update_sync_timestamp, update_job_schedule
        )
        
        if result['success']:
            # Success: Handle job status transitions with a fresh session
            from app.core.database import get_database
            database = get_database()

            with database.get_write_session_context() as fresh_session:
                # Re-fetch job schedule in fresh session
                job_schedule = fresh_session.query(JobSchedule).get(job_schedule_id)
                if not job_schedule:
                    logger.error(f"Job schedule {job_schedule_id} not found")
                    return

                current_order = job_schedule.execution_order

                # Mark current job as finished
                job_schedule.set_finished()
                logger.info(f"Jira sync job completed successfully")

                # Find next ready job (skips paused jobs)
                from app.jobs.orchestrator import find_next_ready_job
                next_job = find_next_ready_job(fresh_session, tenant_id, current_order)

                # Reset retry attempts first
                from app.core.orchestrator_scheduler import get_orchestrator_scheduler
                orchestrator_scheduler = get_orchestrator_scheduler()
                orchestrator_scheduler.reset_retry_attempts('Jira')

                if next_job:
                    next_job.status = 'PENDING'
                    logger.info(f"Set next ready job to PENDING: {next_job.job_name} (order: {next_job.execution_order})")

                    # Check if this is cycling back to the first job (restart)
                    first_job = fresh_session.query(JobSchedule).filter(
                        JobSchedule.tenant_id == tenant_id,
                        JobSchedule.active == True,
                        JobSchedule.status != 'PAUSED'
                    ).order_by(JobSchedule.execution_order.asc()).first()

                    is_cycle_restart = (first_job and next_job.id == first_job.id)

                    if is_cycle_restart:
                        # Cycle restart - use regular countdown
                        logger.info(f"Next job is cycle restart ({next_job.job_name}) - using regular countdown")
                        orchestrator_scheduler.restore_normal_schedule()
                    else:
                        # Normal sequence - use fast retry for quick transition
                        logger.info(f"Next job is in sequence ({next_job.job_name}) - using fast retry for quick transition")
                        orchestrator_scheduler.schedule_fast_retry('Jira')
                else:
                    # No next job - restore normal schedule
                    orchestrator_scheduler.restore_normal_schedule()

                # Send status update that job is finished
                from app.core.websocket_manager import get_websocket_manager
                websocket_manager = get_websocket_manager()
                await websocket_manager.send_status_update(
                    "Jira",
                    "FINISHED",
                    {"message": "Jira sync job completed successfully"}
                )

                # Session will be committed automatically by context manager
            logger.info(f"Jira sync completed successfully")
            logger.info(f"   • WorkItems processed: {result.get('issues_processed', 0)}")
            logger.info(f"   • PR links created: {result.get('pr_links_created', 0)}")

        else:
            # Failure: Set this job back to PENDING with checkpoint using fresh session
            error_msg = result.get('error', 'Unknown error')
            checkpoint = result.get('last_processed_updated_at')

            from app.core.database import get_database
            database = get_database()

            with database.get_write_session_context() as fresh_session:
                job_schedule = fresh_session.query(JobSchedule).get(job_schedule_id)
                if job_schedule:
                    job_schedule.set_pending_with_checkpoint(error_msg, repo_checkpoint=checkpoint)
                    logger.info("Successfully updated job schedule with error status")

            # Schedule fast retry if enabled
            from app.core.orchestrator_scheduler import get_orchestrator_scheduler
            orchestrator_scheduler = get_orchestrator_scheduler()
            fast_retry_scheduled = orchestrator_scheduler.schedule_fast_retry('Jira')

            # Send status update that job failed and is now pending
            from app.core.websocket_manager import get_websocket_manager
            websocket_manager = get_websocket_manager()
            await websocket_manager.send_status_update(
                "Jira",
                "PENDING",
                {"message": f"Jira sync failed - {error_msg[:100]}..."}
            )

            # Send error progress update (short message for progress bar)
            await websocket_manager.send_progress_update("Jira", 100.0, "[ERROR] Jira sync failed - check WorkItems & Warnings below")

            # Send detailed error via exception message (like GitHub job does)
            await websocket_manager.send_exception("Jira", "ERROR", f"Jira sync failed: {error_msg}", error_msg)

            # Send failure completion notification (like GitHub job does)
            await websocket_manager.send_completion(
                "Jira",
                False,
                {
                    'error': error_msg,
                    'checkpoint_saved': checkpoint is not None,
                    'issues_processed': result.get('issues_processed', 0),
                    'changelogs_processed': result.get('changelogs_processed', 0)
                }
            )

            logger.error(f"Jira sync failed: {error_msg}")
            if checkpoint:
                logger.info(f"   • Checkpoint saved: {checkpoint}")
            if fast_retry_scheduled:
                retry_interval = orchestrator_scheduler.get_retry_status('Jira')['retry_interval_minutes']
                logger.info(f"   • Fast retry scheduled in {retry_interval} minutes")

    except Exception as e:
        logger.error(f"ERROR: Error in async Jira sync: {e}")
        import traceback
        traceback.print_exc()

        # Send error progress update (short message for progress bar)
        from app.core.websocket_manager import get_websocket_manager
        websocket_manager = get_websocket_manager()
        await websocket_manager.send_progress_update("Jira", 100.0, "[ERROR] Jira sync error - check WorkItems & Warnings below")

        # Send detailed error via exception message (like GitHub job does)
        await websocket_manager.send_exception("Jira", "ERROR", f"Jira sync error: {str(e)}", str(e))

        # Send failure completion notification (like GitHub job does)
        await websocket_manager.send_completion(
            "Jira",
            False,
            {
                'error': str(e),
                'checkpoint_saved': False,
                'issues_processed': 0,
                'changelogs_processed': 0
            }
        )

        # Set job back to PENDING on unexpected error using fresh session
        from app.core.database import get_database
        database = get_database()

        try:
            with database.get_write_session_context() as fresh_session:
                job_schedule = fresh_session.query(JobSchedule).get(job_schedule_id)
                if job_schedule:
                    job_schedule.set_pending_with_checkpoint(str(e))
                    logger.info("Successfully updated job schedule with error status")
        except Exception as session_error:
            logger.error(f"Job session error: {session_error}")

        # Schedule fast retry if enabled
        from app.core.orchestrator_scheduler import get_orchestrator_scheduler
        orchestrator_scheduler = get_orchestrator_scheduler()
        fast_retry_scheduled = orchestrator_scheduler.schedule_fast_retry('Jira')

        if fast_retry_scheduled:
            retry_interval = orchestrator_scheduler.get_retry_status('Jira')['retry_interval_minutes']
            logger.info(f"   • Fast retry scheduled in {retry_interval} minutes")


async def extract_jira_issues_and_dev_status(session: Session, integration: Integration, jira_client, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Extract Jira issues and their dev_status data.

    Args:
        session: Database session
        integration: Jira integration object
        jira_client: Jira API client
        job_schedule: Job schedule for checkpoint management

    Returns:
        Dictionary with extraction results
    """
    try:
        from app.jobs.jira.jira_extractors import extract_projects_and_issuetypes, extract_projects_and_statuses, extract_work_items_and_changelogs
        from app.core.logging_config import JobLogger

        job_logger = JobLogger("Jira")
        websocket_manager = get_websocket_manager()

        # Clear any previous progress and notify start
        websocket_manager.clear_job_progress("Jira")

        # Step 1: Extract projects and issue types
        logger.info("Step 1: Extracting projects and issue types...")
        await websocket_manager.send_progress_update("Jira", 10.0, "Extracting projects and issue types...")
        projects_result = extract_projects_and_issuetypes(session, jira_client, integration, job_logger)
        if not projects_result.get('projects_processed', 0):
            logger.warning("No projects found or processed")
            await websocket_manager.send_exception("Jira", "WARNING", "No projects found or processed")

        # Step 2: Extract projects and statuses
        logger.info("Step 2: Extracting projects and statuses...")
        await websocket_manager.send_progress_update("Jira", 20.0, "Extracting projects and statuses...")
        statuses_result = extract_projects_and_statuses(session, jira_client, integration, job_logger)
        if not statuses_result.get('statuses_processed', 0):
            logger.warning("No statuses found or processed")
            await websocket_manager.send_exception("Jira", "WARNING", "No statuses found or processed")

        # Step 3: Extract issues and changelogs
        logger.info("Step 3: Extracting issues and changelogs...")
        await websocket_manager.send_progress_update("Jira", 30.0, "Extracting issues and changelogs...")

        # Determine start date based on recovery vs incremental sync
        if job_schedule.has_recovery_checkpoints():
            # RECOVERY MODE: Use last_run_started_at (when job started extracting data)
            start_date = job_schedule.last_run_started_at
            logger.info(f"Recovery mode: Using last_run_started_at = {start_date}")
        else:
            # INCREMENTAL SYNC MODE: Use last_success_at formatted as %Y-%m-%d %H%M
            if job_schedule.last_success_at:
                # Format without seconds: %Y-%m-%d %H%M
                start_date = job_schedule.last_success_at.replace(second=0, microsecond=0)
                logger.info(f"Incremental sync: Using last_success_at = {start_date.strftime('%Y-%m-%d %H%M')}")
            else:
                # Default to 20 years ago for first run (comprehensive knowledge base for AI agents)
                from datetime import timedelta
                start_date = DateTimeHelper.now_default() - timedelta(days=7300)  # 20 years * 365 days
                logger.info(f"First run: Using 20-year fallback = {start_date.strftime('%Y-%m-%d %H%M')}")

        # Start the extraction with periodic progress updates
        await websocket_manager.send_progress_update("Jira", 35.0, "Starting issue and changelog processing...")

        # Run the extraction (progress updates are handled within the extractors)
        issues_result = await extract_work_items_and_changelogs(session, jira_client, integration, job_logger, start_date=start_date, websocket_manager=websocket_manager, job_schedule=job_schedule)

        if not issues_result['success']:
            return {
                'success': False,
                'error': f"WorkItems extraction failed: {issues_result.get('error', 'Unknown error')}",
                'issues_processed': 0,
                'pr_links_created': 0
            }

        # Send progress update after issues and changelogs are processed
        issues_processed = issues_result.get('issues_processed', 0)
        changelogs_processed = issues_result.get('changelogs_processed', 0)
        await websocket_manager.send_progress_update(
            "Jira",
            50.0,
            f"Completed processing {issues_processed:,} issues and {changelogs_processed:,} changelogs"
        )

        # Step 3.5: WorkItems and changelogs completed
        await websocket_manager.send_progress_update("Jira", 45.0, f"Processed {issues_result['issues_processed']} issues and {issues_result['changelogs_processed']} changelogs")

        # Step 4: Extract dev_status and create PR links
        logger.info("Step 4: Extracting dev_status data and creating PR links...")
        await websocket_manager.send_progress_update("Jira", 50.0, "Extracting dev_status data and creating PR links...")

        # Get issues with code_changed = True from the current extraction
        # Use hybrid approach: current extraction + recently updated issues
        current_issue_keys = set(issues_result.get('issue_keys', []))

        # Get recently updated issues with code changes (since last sync)
        recent_code_changed_issues = []
        if job_schedule.last_success_at:
            recent_code_changed_issues = session.query(WorkItem.key).filter(
                WorkItem.integration_id == integration.id,
                WorkItem.code_changed == True,
                WorkItem.last_updated_at > job_schedule.last_success_at
            ).all()

        recent_keys = {issue.key for issue in recent_code_changed_issues}
        all_keys_to_process = current_issue_keys | recent_keys

        # Get the actual WorkItem objects for processing
        issues_with_code_changes = session.query(WorkItem).filter(
            WorkItem.integration_id == integration.id,
            WorkItem.key.in_(all_keys_to_process),
            WorkItem.code_changed == True
        ).all()

        logger.info(f"Found {len(issues_with_code_changes)} issues with code changes")
        logger.info(f"   • From current extraction: {len(current_issue_keys)}")
        logger.info(f"   • Recently updated: {len(recent_keys)}")
        total_issues = len(issues_with_code_changes)

        pr_links_created = 0
        dev_status_skipped = 0
        issues_processed = 0

        for issue in issues_with_code_changes:
            try:
                if not issue.external_id:
                    logger.warning(f"WorkItem {issue.key} has no external_id, skipping")
                    continue

                # Delete existing PR links for this issue (as per your requirement)
                from app.models.unified_models import WitPrLinks
                existing_links_count = session.query(WitPrLinks).filter(
                    WitPrLinks.work_item_id == issue.id
                ).count()

                if existing_links_count > 0:
                    logger.debug(f"WorkItem {issue.key}: Deleting {existing_links_count} existing PR links")

                session.query(WitPrLinks).filter(
                    WitPrLinks.work_item_id == issue.id
                ).delete()

                # Fetch dev_status data from Jira (non-blocking)
                import asyncio
                import concurrent.futures

                # Run the blocking API call in a thread pool to prevent UI blocking
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    try:
                        # Timeout after 10 seconds to prevent hanging
                        dev_details = await asyncio.wait_for(
                            loop.run_in_executor(executor, jira_client.get_issue_dev_details, issue.external_id),
                            timeout=10.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"Dev_status fetch timed out for issue {issue.key}")
                        dev_details = None
                    except Exception as e:
                        logger.warning(f"Dev_status fetch failed for issue {issue.key}: {e}")
                        dev_details = None
                if dev_details:
                    # Import here to avoid circular imports
                    from app.jobs.jira.jira_extractors import has_useful_dev_status_data, extract_pr_links_from_dev_status

                    # Filter: Only process if contains actual PR or repository data
                    if has_useful_dev_status_data(dev_details):
                        # Debug: Log the dev_status structure for the first few issues (DEBUG level only)
                        if issues_processed < 3:
                            logger.debug(f"WorkItem {issue.key} dev_status structure: {dev_details}")

                        # Extract PR links from dev_status data
                        pr_links = extract_pr_links_from_dev_status(dev_details)

                        # Log only every 10th issue to reduce noise
                        if issues_processed % 10 == 0 or len(pr_links) > 0:
                            logger.debug(f"WorkItem {issue.key}: Extracted {len(pr_links)} PR links from dev_status")

                        # Create WitPrLinks records
                        for pr_link in pr_links:
                            logger.debug(f"Creating PR link: WorkItem {issue.key} -> Repo {pr_link['repo_full_name']} PR #{pr_link['pr_number']}")
                            link_record = WitPrLinks(
                                work_item_id=issue.id,
                                external_repo_id=pr_link['repo_id'],
                                repo_full_name=pr_link['repo_full_name'],
                                pull_request_number=pr_link['pr_number'],
                                branch_name=pr_link.get('branch'),
                                commit_sha=pr_link.get('commit'),
                                pr_status=pr_link.get('status'),
                                integration_id=integration.id,
                                tenant_id=integration.tenant_id,
                                active=True
                            )
                            session.add(link_record)
                            pr_links_created += 1

                        # Log creation only for issues with many PR links (reduce noise)
                        if len(pr_links) > 2:
                            logger.info(f"Created {len(pr_links)} PR links for issue {issue.key}")
                    else:
                        dev_status_skipped += 1
                        logger.debug(f"Skipped dev_status for issue {issue.key} (no useful data)")
                else:
                    dev_status_skipped += 1
                    logger.debug(f"No dev_status data for issue {issue.key}")

                issues_processed += 1

                # Update progress every 10 issues
                if issues_processed % 10 == 0:
                    progress = 50.0 + (issues_processed / total_issues) * 40.0  # 50% to 90%
                    percentage = (issues_processed / total_issues) * 100 if total_issues > 0 else 0
                    await websocket_manager.send_progress_update(
                        "Jira",
                        progress,
                        f"Processing dev_status: {issues_processed:,} of {total_issues:,} issues ({percentage:.1f}%)"
                    )
                    logger.info(f"Processed dev_status for {issues_processed}/{total_issues} issues")
                    session.commit()  # Commit periodically

                    # 🔥 Database heartbeat during dev_status processing to keep connection alive
                    try:
                        from sqlalchemy import text
                        session.execute(text("SELECT 1"))
                        logger.debug(f"[DB_HEARTBEAT] Connection kept alive during dev_status processing ({issues_processed}/{total_issues})")
                    except Exception as heartbeat_error:
                        logger.warning(f"[DB_HEARTBEAT] Failed to keep connection alive during dev_status: {heartbeat_error}")

                # Yield control after each issue to ensure UI responsiveness
                await asyncio.sleep(0)  # Yield control to prevent blocking

            except Exception as e:
                error_msg = f"Error processing dev_status for issue {issue.key}: {e}"
                logger.error(error_msg)
                await websocket_manager.send_exception("Jira", "ERROR", error_msg, str(e))
                continue

        # Final commit
        session.commit()

        # Summary of dev_status processing
        logger.info(f"Dev_status processing complete: {issues_processed} issues processed, {pr_links_created} PR links created, {dev_status_skipped} issues skipped")

        # Verify PR links were saved
        from app.models.unified_models import WitPrLinks
        total_pr_links_in_db = session.query(WitPrLinks).filter(
            WitPrLinks.tenant_id == integration.tenant_id
        ).count()
        logger.info(f"Final verification: {total_pr_links_in_db} total PR links in database for client {integration.tenant_id}")

        # Step 5: All processing completed - send final progress update
        await websocket_manager.send_progress_update("Jira", 100.0, f"[COMPLETE] Completed: {issues_result['issues_processed']} issues, {issues_result['changelogs_processed']} changelogs, {pr_links_created} PR links created")

        # Small delay to ensure progress update is processed before completion notification
        import asyncio
        await asyncio.sleep(0.5)

        # Send completion notification
        await websocket_manager.send_completion(
            "Jira",
            True,
            {
                'issues_processed': issues_result['issues_processed'],
                'changelogs_processed': issues_result['changelogs_processed'],
                'pr_links_created': pr_links_created
            }
        )

        logger.info(f"Jira extraction completed")
        logger.info(f"   • WorkItems processed: {issues_result['issues_processed']}")
        logger.info(f"   • Changelogs processed: {issues_result['changelogs_processed']}")
        logger.info(f"   • PR links created: {pr_links_created}")
        logger.info(f"   • Dev status items skipped (empty): {dev_status_skipped}")

        return {
            'success': True,
            'issues_processed': issues_result['issues_processed'],
            'changelogs_processed': issues_result['changelogs_processed'],
            'pr_links_created': pr_links_created
        }

    except Exception as e:
        logger.error(f"Error in Jira extraction: {e}")
        return {
            'success': False,
            'error': str(e),
            'issues_processed': 0,
            'pr_links_created': 0
        }


async def run_jira_sync_optimized(
    job_schedule_id: int,
    execution_mode: JiraExecutionMode = JiraExecutionMode.ALL,
    custom_query: Optional[str] = None,
    target_projects: Optional[List[str]] = None,
    update_sync_timestamp: bool = True,
    update_job_schedule: bool = True
):
    """
    Optimized Jira sync with proper session management to prevent UI blocking.
    Uses the original function but ensures sessions are managed properly.
    """
    from app.core.database import get_database
    from app.models.unified_models import JobSchedule
    import asyncio

    database = get_database()
    logger.info(f"[JIRA] Starting optimized Jira sync (ID: {job_schedule_id})")

    try:
        # Use session-free approach to prevent connection timeouts during long API calls
        # Get job schedule info with a quick session
        with database.get_read_session_context() as session:
            job_schedule = session.query(JobSchedule).filter(JobSchedule.id == job_schedule_id).first()
            if not job_schedule:
                logger.error(f"Job schedule {job_schedule_id} not found")
                return {'success': False, 'error': 'Job schedule not found'}

            # Store job details for session-free operations
            tenant_id = job_schedule.tenant_id

        # Add periodic yielding to prevent blocking
        await asyncio.sleep(0)

        # Use session-free execution to prevent connection timeouts
        result = await execute_jira_extraction_session_free(
            tenant_id, None, None, job_schedule_id,  # integration details will be fetched inside
            execution_mode, custom_query, target_projects,
            update_sync_timestamp, update_job_schedule
        )

        return result

    except Exception as e:
        logger.error(f"Optimized Jira sync error: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}
