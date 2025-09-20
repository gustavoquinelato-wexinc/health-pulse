"""
ETL Job Orchestrator

Implements Active/Passive Job Model:
- Active Job (Orchestrator): Checks for PENDING jobs and triggers them
- Passive Jobs (Workers): Do the actual ETL work and manage their own state

The orchestrator runs on a schedule and:
1. Looks for jobs with status = 'PENDING'
2. Updates status to 'RUNNING' (locking mechanism)
3. Triggers the appropriate passive job asynchronously
4. Exits (passive job manages its own completion)

Job Status Flow:
- READY: Job has never run (ignored by orchestrator)
- PENDING: Job is ready to run (picked up by orchestrator)
- RUNNING: Job is currently executing (locked)
- FINISHED: Job completed successfully
- On completion: Current job sets itself to FINISHED and next job to PENDING
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_database
from app.core.logging_config import get_logger
from app.core.job_manager import get_job_manager
from app.core.utils import DateTimeHelper
from app.models.unified_models import JobSchedule, Integration
from fastapi import BackgroundTasks
import asyncio

logger = get_logger(__name__)

# Simple token storage for job execution context
_job_auth_tokens = {}

def _set_job_auth_token(tenant_id: int, token: str):
    """Store auth token for job execution"""
    _job_auth_tokens[tenant_id] = token

def _get_job_auth_token(tenant_id: int) -> str:
    """Get auth token for job execution"""
    # First try to get user token (for manual jobs)
    user_token = _job_auth_tokens.get(tenant_id)
    if user_token:
        return user_token

    # For automated jobs, get system token
    return _get_system_token(tenant_id)

def _clear_job_auth_token(tenant_id: int):
    """Clear auth token after job execution"""
    _job_auth_tokens.pop(tenant_id, None)


# System token cache for automated jobs
_system_tokens = {}

def _get_system_token(tenant_id: int) -> str:
    """Get system token for automated ETL jobs"""
    # Check if we have a cached system token
    if tenant_id in _system_tokens:
        return _system_tokens[tenant_id]

    # Create system token for this tenant
    try:
        token = _create_system_token_sync(tenant_id)
        if token:
            _system_tokens[tenant_id] = token
            logger.info(f"System token created for tenant {tenant_id}")
        return token
    except Exception as e:
        logger.error(f"Failed to get system token for tenant {tenant_id}: {e}")
        return None


def _create_system_token_sync(tenant_id: int) -> str:
    """Create system token synchronously using the system admin user"""
    try:
        import requests
        from app.core.config import get_settings

        settings = get_settings()
        backend_url = settings.BACKEND_SERVICE_URL

        # Use the system admin user from environment variables
        system_email = settings.SYSTEM_USER_EMAIL
        system_password = settings.SYSTEM_USER_PASSWORD

        # Login to get token using system endpoint
        response = requests.post(
            f"{backend_url}/auth/system/login",
            json={
                "email": system_email,
                "password": system_password
            },
            timeout=10.0
        )

        if response.status_code == 200:
            data = response.json()
            token = data.get("token")  # Backend service returns "token" not "access_token"
            if token:
                logger.info(f"System token created successfully for tenant {tenant_id}")
                return token
            else:
                logger.error(f"No token in login response for tenant {tenant_id}: {data}")
        else:
            logger.error(f"System user login failed for tenant {tenant_id}: {response.status_code} - {response.text}")

        return None

    except Exception as e:
        logger.error(f"Failed to create system token for tenant {tenant_id}: {e}")
        return None


def _clear_system_token(tenant_id: int):
    """Clear cached system token (e.g., when it expires)"""
    _system_tokens.pop(tenant_id, None)


def find_next_ready_job(session: Session, tenant_id: int, current_order: int) -> JobSchedule:
    """
    Find the next ready job in execution order that's not paused.

    Args:
        session: Database session
        tenant_id: Tenant ID for security filtering
        current_order: Current job's execution order

    Returns:
        Next ready JobSchedule or None if no ready jobs found
    """
    # First, try to find next job after current order that's ready to run
    next_job = session.query(JobSchedule).filter(
        JobSchedule.tenant_id == tenant_id,
        JobSchedule.active == True,
        JobSchedule.status != 'PAUSED',  # Skip paused jobs
        JobSchedule.execution_order > current_order
    ).order_by(JobSchedule.execution_order.asc()).first()

    if next_job:
        return next_job

    # If no next job, cycle back to first ready job (excluding current)
    first_job = session.query(JobSchedule).filter(
        JobSchedule.tenant_id == tenant_id,
        JobSchedule.active == True,
        JobSchedule.status != 'PAUSED',  # Skip paused jobs
        JobSchedule.execution_order != current_order  # Exclude current job
    ).order_by(JobSchedule.execution_order.asc()).first()

    return first_job


def check_integration_active(job_schedule_id: int) -> dict:
    """
    Check if the integration associated with a job schedule is active.

    Args:
        job_schedule_id: ID of the job schedule to check

    Returns:
        dict: {'active': bool, 'message': str}
    """
    try:
        database = get_database()
        with database.get_session() as session:
            # Get the job schedule
            job_schedule = session.query(JobSchedule).filter(
                JobSchedule.id == job_schedule_id
            ).first()

            if not job_schedule:
                return {
                    'active': False,
                    'message': f'Job schedule {job_schedule_id} not found'
                }

            # Get the associated integration
            # Special case: Vectorization job doesn't need an integration
            if not job_schedule.integration_id:
                if job_schedule.job_name.lower() == 'vectorization':
                    return {
                        'active': True,
                        'message': f'Vectorization job does not require an integration'
                    }
                else:
                    return {
                        'active': False,
                        'message': f'Job {job_schedule.job_name} has no associated integration'
                    }

            integration = session.query(Integration).filter(
                Integration.id == job_schedule.integration_id
            ).first()

            if not integration:
                return {
                    'active': False,
                    'message': f'Integration {job_schedule.integration_id} not found for job {job_schedule.job_name}'
                }

            if not integration.active:
                return {
                    'active': False,
                    'message': f'Integration {integration.provider} is inactive - job {job_schedule.job_name} cannot be executed'
                }

            return {
                'active': True,
                'message': f'Integration {integration.provider} is active'
            }

    except Exception as e:
        logger.error(f"Error checking integration active status: {e}")
        return {
            'active': False,
            'message': f'Error checking integration status: {str(e)}'
        }


def skip_job_due_to_inactive_integration(job_schedule_id: int, error_message: str):
    """
    Skip a job due to inactive integration and set the next job as pending.

    Args:
        job_schedule_id: ID of the job schedule to skip
        error_message: Error message to set on the job
    """
    try:
        database = get_database()
        with database.get_session() as session:
            # Get the job schedule
            job_schedule = session.query(JobSchedule).filter(
                JobSchedule.id == job_schedule_id
            ).first()

            if not job_schedule:
                logger.error(f"Job schedule {job_schedule_id} not found for skipping")
                return

            # Set job as finished with error message
            job_schedule.status = 'FINISHED'
            job_schedule.error_message = error_message
            job_schedule.last_success_at = None  # Don't update success time for skipped jobs

            logger.info(f"Job {job_schedule.job_name} marked as FINISHED due to inactive integration")

            # Find next ready job (skips paused jobs)
            next_job = find_next_ready_job(session, job_schedule.tenant_id, job_schedule.execution_order)

            if next_job:
                # Set next job as pending
                next_job.status = 'PENDING'
                next_job.error_message = None
                logger.info(f"Next ready job {next_job.job_name} set to PENDING")

            session.commit()
            logger.info(f"Successfully skipped job {job_schedule.job_name} and set next job as pending")

        # Schedule orchestrator restart to process the next job
        from app.core.orchestrator_scheduler import get_orchestrator_scheduler
        orchestrator_scheduler = get_orchestrator_scheduler()
        orchestrator_scheduler.schedule_fast_retry(job_schedule.job_name)

    except Exception as e:
        logger.error(f"Error skipping job due to inactive integration: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")




async def trigger_jira_sync(force_manual=False, execution_params=None, tenant_id=None, user_token=None):
    """
    Trigger a Jira sync job via the orchestration system for a specific client.

    Args:
        force_manual: If True, forces correct job states for manual execution
                     (jira_sync=PENDING, github_sync=READY).
                     If False, uses normal orchestrator logic.
        execution_params: Optional execution parameters for the job
        tenant_id: Tenant ID to trigger job for (required for client isolation)
        user_token: User authentication token for AI operations

    Returns:
        Dict containing job execution results
    """
    if tenant_id is None:
        return {
            'status': 'error',
            'message': 'tenant_id is required for job execution',
            'issues_processed': 0,
            'changelogs_processed': 0
        }

    try:
        database = get_database()
        with database.get_session() as session:
            # SECURITY: Find or create jobs filtered by tenant_id (case-insensitive)
            jira_job = session.query(JobSchedule).filter(
                func.lower(JobSchedule.job_name) == 'jira',
                JobSchedule.tenant_id == tenant_id
            ).first()
            github_job = session.query(JobSchedule).filter(
                func.lower(JobSchedule.job_name) == 'github',
                JobSchedule.tenant_id == tenant_id
            ).first()

            if not jira_job or not github_job:
                # Initialize job schedules if they don't exist for this client
                initialize_job_schedules_for_client(tenant_id)
                jira_job = session.query(JobSchedule).filter(
                    JobSchedule.job_name == 'jira_sync',
                    JobSchedule.tenant_id == tenant_id
                ).first()
                github_job = session.query(JobSchedule).filter(
                    JobSchedule.job_name == 'github_sync',
                    JobSchedule.tenant_id == tenant_id
                ).first()

            if not jira_job or not github_job:
                return {
                    'status': 'error',
                    'message': 'Failed to initialize job schedules',
                    'issues_processed': 0,
                    'changelogs_processed': 0
                }

            if force_manual:
                # Force correct job states for manual Jira execution:
                # - jira_sync = PENDING (ready to run)
                # - github_sync = READY (will be set to PENDING when Jira finishes)
                jira_job.status = 'PENDING'
                jira_job.error_message = None
                github_job.status = 'READY'
                github_job.error_message = None
                session.commit()

                # Reset retry attempts when manually triggered
                from app.core.orchestrator_scheduler import get_orchestrator_scheduler
                orchestrator_scheduler = get_orchestrator_scheduler()
                orchestrator_scheduler.force_reset_retry_attempts('jira_sync')

                logger.info(f"TRIGGERED: jira_sync job (ID: {jira_job.id}) - MANUAL MODE - forced job states")
                logger.info(f"   - jira_sync: PENDING")
                logger.info(f"   - github_sync: READY")
            else:
                # Normal mode: just set jira_sync to PENDING (for API/regular triggers)
                jira_job.status = 'PENDING'
                jira_job.error_message = None
                session.commit()

                logger.info(f"TRIGGERED: jira_sync job (ID: {jira_job.id}) - NORMAL MODE")

            # Store user token for job execution (if provided)
            if user_token:
                # Store token in a simple global context for this job execution
                _set_job_auth_token(tenant_id, user_token)

            # Trigger the orchestrator to process the job for this client only (non-blocking)
            asyncio.create_task(run_orchestrator_for_client(tenant_id))

            # Return immediately - job will run in background
            return {
                'status': 'triggered',
                'message': 'Jira sync job triggered successfully',
                'job_id': str(jira_job.id),
                'note': 'Job is running in background. Check job status for progress.'
            }

    except Exception as e:
        logger.error(f"ERROR: Error triggering Jira sync: {e}")
        return {
            'status': 'error',
            'message': f'Failed to trigger Jira sync: {str(e)}',
            'issues_processed': 0,
            'changelogs_processed': 0
        }


async def trigger_github_sync(force_manual=False, execution_params=None, tenant_id=None, user_token=None):
    """
    Trigger a GitHub sync job via the orchestration system for a specific client.

    Args:
        force_manual: If True, forces correct job states for manual execution
                     (jira_sync=FINISHED, github_sync=PENDING).
                     If False, uses normal orchestrator logic.
        execution_params: Optional execution parameters for the job
        tenant_id: Tenant ID to trigger job for (required for client isolation)
        user_token: User authentication token for AI operations

    Returns:
        Dict containing job execution results
    """
    if tenant_id is None:
        return {
            'status': 'error',
            'message': 'tenant_id is required for job execution',
            'pull_requests_processed': 0,
            'commits_processed': 0
        }

    try:
        database = get_database()
        with database.get_session() as session:
            # SECURITY: Find or create jobs filtered by tenant_id (case-insensitive)
            jira_job = session.query(JobSchedule).filter(
                func.lower(JobSchedule.job_name) == 'jira',
                JobSchedule.tenant_id == tenant_id
            ).first()
            github_job = session.query(JobSchedule).filter(
                func.lower(JobSchedule.job_name) == 'github',
                JobSchedule.tenant_id == tenant_id
            ).first()

            if not jira_job or not github_job:
                # Initialize job schedules if they don't exist for this client
                initialize_job_schedules_for_client(tenant_id)
                jira_job = session.query(JobSchedule).filter(
                    JobSchedule.job_name == 'jira_sync',
                    JobSchedule.tenant_id == tenant_id
                ).first()
                github_job = session.query(JobSchedule).filter(
                    JobSchedule.job_name == 'github_sync',
                    JobSchedule.tenant_id == tenant_id
                ).first()

            if not jira_job or not github_job:
                return {
                    'status': 'error',
                    'message': 'Failed to initialize job schedules',
                    'pull_requests_processed': 0,
                    'commits_processed': 0
                }

            if force_manual:
                # Force correct job states for manual GitHub execution:
                # - jira_sync = FINISHED (prerequisite completed)
                # - github_sync = PENDING (ready to run)
                jira_job.status = 'FINISHED'
                jira_job.error_message = None
                github_job.status = 'PENDING'
                github_job.error_message = None
                session.commit()

                # Reset retry attempts when manually triggered
                from app.core.orchestrator_scheduler import get_orchestrator_scheduler
                orchestrator_scheduler = get_orchestrator_scheduler()
                orchestrator_scheduler.force_reset_retry_attempts('github_sync')

                logger.info(f"TRIGGERED: github_sync job (ID: {github_job.id}) - MANUAL MODE - forced job states")
                logger.info(f"   - jira_sync: FINISHED")
                logger.info(f"   - github_sync: PENDING")
            else:
                # Normal mode: just set github_sync to PENDING (for API/regular triggers)
                github_job.status = 'PENDING'
                github_job.error_message = None
                session.commit()

                logger.info(f"TRIGGERED: github_sync job (ID: {github_job.id}) - NORMAL MODE")

            # Store user token for job execution (if provided)
            if user_token:
                # Store token in a simple global context for this job execution
                _set_job_auth_token(tenant_id, user_token)

            # Trigger the orchestrator to process the job for this client only (non-blocking)
            asyncio.create_task(run_orchestrator_for_client(tenant_id))

            # Return immediately - job will run in background
            return {
                'status': 'triggered',
                'message': 'GitHub sync job triggered successfully',
                'job_id': str(github_job.id),
                'note': 'Job is running in background. Check job status for progress.'
            }

    except Exception as e:
        logger.error(f"ERROR: Error triggering GitHub sync: {e}")
        return {
            'status': 'error',
            'message': f'Failed to trigger GitHub sync: {str(e)}',
            'pull_requests_processed': 0,
            'commits_processed': 0
        }


async def run_orchestrator():
    """
    Main orchestrator function that runs on schedule.

    Checks for PENDING jobs across ALL tenants and triggers them asynchronously.
    Each tenant's jobs are processed independently.
    """
    try:
        logger.info("STARTING: ETL Orchestrator starting...")

        database = get_database()

        # SECURITY: Get all tenants and process their jobs independently
        with database.get_session() as session:
            from app.models.unified_models import Tenant
            tenants = session.query(Tenant).filter(Tenant.active == True).all()

            if not tenants:
                logger.warning("No active tenants found")
                return

            logger.info(f"Processing jobs for {len(tenants)} active tenants")

        # Process each client's jobs independently based on their individual settings
        for tenant in tenants:
            try:
                # SECURITY: Check if this client's orchestrator should run based on their settings
                should_run = await should_run_orchestrator_for_client(tenant.id)
                if should_run:
                    logger.info(f"Processing jobs for client: {tenant.name} (ID: {tenant.id}) - interval elapsed")
                    await run_orchestrator_for_client(tenant.id)
                else:
                    logger.debug(f"Skipping client {tenant.name} (ID: {tenant.id}) - interval not elapsed or disabled")
            except Exception as e:
                logger.error(f"Error processing jobs for client {tenant.name}: {e}")
                continue

    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")


async def should_run_orchestrator_for_client(tenant_id: int) -> bool:
    """
    Check if the orchestrator should run for a specific client based on their settings.

    Args:
        tenant_id: Tenant ID to check

    Returns:
        bool: True if orchestrator should run for this client, False otherwise
    """
    try:
        from app.core.settings_manager import is_orchestrator_enabled, get_orchestrator_interval

        # Check if orchestrator is enabled for this client
        if not is_orchestrator_enabled(tenant_id):
            return False

        # Get client's orchestrator interval
        interval_minutes = get_orchestrator_interval(tenant_id)

        # Check when the last orchestrator run was for this client
        database = get_database()
        with database.get_session() as session:
            # Find the most recent job run for this client
            last_run = session.query(JobSchedule.last_run_started_at).filter(
                JobSchedule.tenant_id == tenant_id,
                JobSchedule.last_run_started_at.isnot(None)
            ).order_by(JobSchedule.last_run_started_at.desc()).first()

            if not last_run or not last_run[0]:
                # No previous runs - should run now
                logger.info(f"Tenant {tenant_id}: No previous runs found - should run")
                return True

            # Calculate time since last run
            from datetime import timedelta
            last_run_time = last_run[0]
            now = DateTimeHelper.now_utc()
            time_since_last_run = now - last_run_time
            interval_delta = timedelta(minutes=interval_minutes)

            should_run = time_since_last_run >= interval_delta

            if should_run:
                logger.info(f"Tenant {tenant_id}: Interval elapsed ({time_since_last_run.total_seconds()/60:.1f}min >= {interval_minutes}min) - should run")
            else:
                remaining_minutes = (interval_delta - time_since_last_run).total_seconds() / 60
                logger.debug(f"Tenant {tenant_id}: Interval not elapsed - {remaining_minutes:.1f}min remaining")

            return should_run

    except Exception as e:
        logger.error(f"Error checking if orchestrator should run for client {tenant_id}: {e}")
        return False


async def run_orchestrator_for_client(tenant_id: int):
    """
    Run orchestrator for a specific client.

    Args:
        tenant_id: Tenant ID to process jobs for
    """
    try:
        database = get_database()

        # Step 2: Quick check for pending jobs for this client
        pending_job_id = None
        pending_job_name = None

        with database.get_session() as session:
            # SECURITY: First look for PENDING jobs by execution_order filtered by tenant_id
            result = session.query(
                JobSchedule.id,
                JobSchedule.job_name
            ).filter(
                JobSchedule.tenant_id == tenant_id,
                JobSchedule.active == True,
                JobSchedule.status == 'PENDING'
            ).order_by(JobSchedule.execution_order.asc()).first()

            if result:
                pending_job_id, pending_job_name = result.id, result.job_name
                logger.info(f"FOUND: PENDING job for client {tenant_id}: {pending_job_name} (ID: {pending_job_id})")
            else:
                # No PENDING jobs found - look for READY jobs
                logger.info(f"INFO: No PENDING jobs found for client {tenant_id} - checking for READY jobs")
                result = session.query(
                    JobSchedule.id,
                    JobSchedule.job_name
                ).filter(
                    JobSchedule.tenant_id == tenant_id,
                    JobSchedule.active == True,
                    JobSchedule.status == 'READY'
                ).order_by(JobSchedule.execution_order.asc()).first()

                if not result:
                    logger.info(f"INFO: No READY jobs found for client {tenant_id} - no jobs to run")
                    return

                pending_job_id, pending_job_name = result.id, result.job_name
                logger.info(f"FOUND: READY job for client {tenant_id}: {pending_job_name} (ID: {pending_job_id}) - will start from beginning")

        # Step 2: Quick atomic update to lock the job (separate short session)
        with database.get_session() as session:
            # SECURITY: Atomic update with tenant_id verification (handles both PENDING and READY)
            updated_rows = session.query(JobSchedule).filter(
                JobSchedule.id == pending_job_id,
                JobSchedule.tenant_id == tenant_id,  # Verify tenant_id
                JobSchedule.status.in_(['PENDING', 'READY'])  # Accept both statuses
            ).update({
                'status': 'RUNNING',
                'last_run_started_at': DateTimeHelper.now_default(),
                'error_message': None
            })

            if updated_rows == 0:
                logger.info(f"INFO: Job was already picked up by another orchestrator instance for client {tenant_id}")
                return

            session.commit()
            logger.info(f"LOCKED: job {pending_job_name} (status: RUNNING)")

        # Step 3: Send WebSocket update (outside database session)
        from app.core.websocket_manager import get_websocket_manager
        websocket_manager = get_websocket_manager()
        logger.info(f"WEBSOCKET: Sending RUNNING status update for {pending_job_name}")
        await websocket_manager.send_status_update(
            pending_job_name,
            "RUNNING",
            {"message": f"Job {pending_job_name} is now running"}
        )

        # Step 4: Verify integration is active before triggering job
        integration_check_result = check_integration_active(pending_job_id)
        if not integration_check_result['active']:
            logger.warning(f"SKIPPING: {pending_job_name} - Integration inactive: {integration_check_result['message']}")
            # Set job as finished with error message and trigger next job
            skip_job_due_to_inactive_integration(pending_job_id, integration_check_result['message'])
            return

        # Step 5: Trigger the job asynchronously (outside of database session)
        job_name_lower = pending_job_name.lower()
        if job_name_lower == 'jira':
            logger.info("TRIGGERING: Jira sync job...")
            asyncio.create_task(run_jira_sync_async(pending_job_id))
        elif job_name_lower == 'github':
            logger.info("TRIGGERING: GitHub sync job...")
            asyncio.create_task(run_github_sync_async(pending_job_id))
        elif job_name_lower == 'wex fabric':
            logger.info("TRIGGERING: WEX Fabric sync job...")
            asyncio.create_task(run_fabric_sync_async(pending_job_id))
        elif job_name_lower == 'wex ad':
            logger.info("TRIGGERING: Active Directory sync job...")
            asyncio.create_task(run_ad_sync_async(pending_job_id))
        elif job_name_lower == 'vectorization':
            logger.info("TRIGGERING: Vectorization job...")
            asyncio.create_task(run_vectorization_sync_async(pending_job_id))
        else:
            logger.error(f"ERROR: Unknown job name: {pending_job_name}")
            # Reset job to PENDING if unknown (separate session)
            with database.get_session() as session:
                session.query(JobSchedule).filter(
                    JobSchedule.id == pending_job_id
                ).update({'status': 'PENDING'})
                session.commit()

            # Schedule orchestrator restart to retry the job
            from app.core.orchestrator_scheduler import get_orchestrator_scheduler
            orchestrator_scheduler = get_orchestrator_scheduler()
            orchestrator_scheduler.schedule_fast_retry(pending_job_name)
            return

        logger.info(f"SUCCESS: Orchestrator completed - {pending_job_name} job triggered")

        # Yield control to allow other async operations
        await asyncio.sleep(0)

    except Exception as e:
        logger.error(f"ERROR: Orchestrator error: {e}")
        import traceback
        traceback.print_exc()


async def run_jira_sync_async(job_schedule_id: int, execution_params=None):
    """
    Asynchronous wrapper for Jira sync job.

    Args:
        job_schedule_id: ID of the job schedule record
        execution_params: Optional execution parameters for the job
    """
    try:


        from app.jobs.jira.jira_job import run_jira_sync

        database = get_database()

        # Step 1: Quick session to get job schedule info
        job_schedule_id_copy = job_schedule_id
        with database.get_session() as session:
            job_schedule = session.query(JobSchedule).filter(JobSchedule.id == job_schedule_id).first()
            if not job_schedule:
                logger.error(f"ERROR: Job schedule {job_schedule_id} not found")
                return

            logger.info(f"STARTING: Jira sync job (ID: {job_schedule_id})")

        # Step 2: Run the job with shorter session management
        # Use the original function but with shorter database sessions
        from app.jobs.jira.jira_job import run_jira_sync, JiraExecutionMode

        # Use shorter session for job execution
        database = get_database()
        with database.get_job_session_context() as session:
            job_schedule = session.query(JobSchedule).filter(JobSchedule.id == job_schedule_id_copy).first()
            if not job_schedule:
                logger.error(f"Job schedule {job_schedule_id_copy} not found")
                return

            # Parse execution parameters if provided
            if execution_params:
                mode = JiraExecutionMode(execution_params.mode) if execution_params.mode != "all" else JiraExecutionMode.ALL
                await run_jira_sync(
                    session, job_schedule,
                    execution_mode=mode,
                    custom_query=execution_params.custom_query,
                    target_projects=execution_params.target_projects
                )
            else:
                # Default behavior (ALL mode)
                await run_jira_sync(session, job_schedule)

    except Exception as e:
        logger.error(f"ERROR: Error in async Jira sync: {e}")
        import traceback
        traceback.print_exc()


async def run_github_sync_async(job_schedule_id: int, execution_params=None):
    """
    Asynchronous wrapper for GitHub sync job.

    Args:
        job_schedule_id: ID of the job schedule record
        execution_params: Optional execution parameters for the job
    """
    try:
        from app.jobs.github.github_job import run_github_sync_optimized, GitHubExecutionMode

        database = get_database()

        # Step 1: Quick session to get job schedule info
        job_schedule_id_copy = job_schedule_id
        with database.get_session() as session:
            job_schedule = session.query(JobSchedule).filter(JobSchedule.id == job_schedule_id).first()
            if not job_schedule:
                logger.error(f"ERROR: Job schedule {job_schedule_id} not found")
                return

            logger.info(f"STARTING: GitHub sync job (ID: {job_schedule_id})")

        # Step 2: Run the job with shorter session management
        # Use the original function but with shorter database sessions
        from app.jobs.github.github_job import run_github_sync, GitHubExecutionMode

        # Use shorter session for job execution
        database = get_database()
        with database.get_job_session_context() as session:
            job_schedule = session.query(JobSchedule).filter(JobSchedule.id == job_schedule_id_copy).first()
            if not job_schedule:
                logger.error(f"Job schedule {job_schedule_id_copy} not found")
                return

            # Parse execution parameters if provided
            if execution_params:
                mode = GitHubExecutionMode(execution_params.mode) if execution_params.mode != "all" else GitHubExecutionMode.ALL
                await run_github_sync(
                    session, job_schedule,
                    execution_mode=mode,
                    target_repository=execution_params.target_repository,
                    target_repositories=execution_params.target_repositories
                )
            else:
                # Default behavior (ALL mode)
                await run_github_sync(session, job_schedule)

    except Exception as e:
        logger.error(f"ERROR: Error in async GitHub sync: {e}")
        import traceback
        traceback.print_exc()


async def run_fabric_sync_async(job_schedule_id: int):
    """
    Simple WEX Fabric sync job implementation.

    Args:
        job_schedule_id: ID of the job schedule record
    """
    try:
        logger.info(f"STARTING: WEX Fabric sync job (ID: {job_schedule_id})")

        # Pause orchestrator countdown while job is running
        from app.core.orchestrator_scheduler import get_orchestrator_scheduler
        orchestrator_scheduler = get_orchestrator_scheduler()
        orchestrator_scheduler.pause_orchestrator('WEX Fabric')

        from app.core.database import get_database
        from app.core.utils import DateTimeHelper
        database = get_database()

        # Get job schedule and determine sync date
        with database.get_session() as session:
            job_schedule = session.query(JobSchedule).get(job_schedule_id)
            if not job_schedule:
                logger.error(f"Job schedule {job_schedule_id} not found")
                return

            # Determine start date based on recovery vs incremental sync
            if job_schedule.has_recovery_checkpoints():
                # RECOVERY MODE: Use last_run_started_at
                start_date = job_schedule.last_run_started_at
                logger.info(f"Recovery mode: Using last_run_started_at = {start_date}")
            else:
                # INCREMENTAL SYNC MODE: Use last_success_at formatted as %Y-%m-%d %H%M
                if job_schedule.last_success_at:
                    start_date = job_schedule.last_success_at.replace(second=0, microsecond=0)
                    logger.info(f"Incremental sync: Using last_success_at = {start_date.strftime('%Y-%m-%d %H%M')}")
                else:
                    # Default to 20 years ago for first run (comprehensive knowledge base for AI agents)
                    from datetime import timedelta
                    start_date = DateTimeHelper.now_default() - timedelta(days=7300)  # 20 years * 365 days
                    logger.info(f"First run: Using 20-year fallback = {start_date.strftime('%Y-%m-%d %H%M')}")

            # Set last_run_started_at if not in recovery mode
            if not job_schedule.has_recovery_checkpoints():
                job_schedule.last_run_started_at = DateTimeHelper.now_default()
                session.commit()
                logger.info(f"Set last_run_started_at = {job_schedule.last_run_started_at}")

        # Simulate job execution with the determined start date
        logger.info(f"Fabric sync would query data updated >= {start_date.strftime('%Y-%m-%d %H%M')}")
        import asyncio
        await asyncio.sleep(2)  # Simulate work

        # Mark job as completed and set next job to PENDING
        with database.get_write_session_context() as session:
            job_schedule = session.query(JobSchedule).get(job_schedule_id)
            if not job_schedule:
                logger.error(f"Job schedule {job_schedule_id} not found")
                return

            tenant_id = job_schedule.tenant_id
            current_order = job_schedule.execution_order

            # Mark current job as finished
            job_schedule.set_finished()
            logger.info(f"WEX Fabric sync job completed successfully")

            # Find next ready job (skips paused jobs)
            next_job = find_next_ready_job(session, tenant_id, current_order)

            if next_job:
                next_job.status = 'PENDING'
                logger.info(f"Set next ready job to PENDING: {next_job.job_name} (order: {next_job.execution_order})")

            session.commit()

            # Resume orchestrator countdown and handle scheduling outside transaction
            from app.core.orchestrator_scheduler import get_orchestrator_scheduler
            orchestrator_scheduler = get_orchestrator_scheduler()
            orchestrator_scheduler.resume_orchestrator('WEX Fabric')

            if next_job:
                # Check if this is cycling back to the first job (restart)
                with database.get_read_session_context() as check_session:
                    first_job = check_session.query(JobSchedule).filter(
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
                        # Normal sequence - use fast transition for quick transition
                        logger.info(f"Next job is in sequence ({next_job.job_name}) - using fast transition for quick transition")
                        orchestrator_scheduler.schedule_fast_transition('WEX Fabric')
            else:
                # No next job - restore normal schedule
                orchestrator_scheduler.restore_normal_schedule()

    except Exception as e:
        logger.error(f"WEX Fabric sync job error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")

        # Set job back to PENDING on unexpected error
        from app.core.database import get_database
        database = get_database()

        try:
            with database.get_write_session_context() as fresh_session:
                job_schedule = fresh_session.query(JobSchedule).get(job_schedule_id)
                if job_schedule:
                    job_schedule.status = 'PENDING'
                    job_schedule.error_message = str(e)
                    logger.info("Successfully updated Fabric job schedule with error status")
        except Exception as session_error:
            logger.error(f"Fabric job session error: {session_error}")


async def run_ad_sync_async(job_schedule_id: int):
    """
    Simple Active Directory sync job implementation.

    Args:
        job_schedule_id: ID of the job schedule record
    """
    try:
        logger.info(f"STARTING: Active Directory sync job (ID: {job_schedule_id})")

        # Pause orchestrator countdown while job is running
        from app.core.orchestrator_scheduler import get_orchestrator_scheduler
        orchestrator_scheduler = get_orchestrator_scheduler()
        orchestrator_scheduler.pause_orchestrator('Active Directory')

        from app.core.database import get_database
        from app.core.utils import DateTimeHelper
        database = get_database()

        # Get job schedule and determine sync date
        with database.get_session() as session:
            job_schedule = session.query(JobSchedule).get(job_schedule_id)
            if not job_schedule:
                logger.error(f"Job schedule {job_schedule_id} not found")
                return

            # Determine start date based on recovery vs incremental sync
            if job_schedule.has_recovery_checkpoints():
                # RECOVERY MODE: Use last_run_started_at
                start_date = job_schedule.last_run_started_at
                logger.info(f"Recovery mode: Using last_run_started_at = {start_date}")
            else:
                # INCREMENTAL SYNC MODE: Use last_success_at formatted as %Y-%m-%d %H%M
                if job_schedule.last_success_at:
                    start_date = job_schedule.last_success_at.replace(second=0, microsecond=0)
                    logger.info(f"Incremental sync: Using last_success_at = {start_date.strftime('%Y-%m-%d %H%M')}")
                else:
                    # Default to 20 years ago for first run (comprehensive knowledge base for AI agents)
                    from datetime import timedelta
                    start_date = DateTimeHelper.now_default() - timedelta(days=7300)  # 20 years * 365 days
                    logger.info(f"First run: Using 20-year fallback = {start_date.strftime('%Y-%m-%d %H%M')}")

            # Set last_run_started_at if not in recovery mode
            if not job_schedule.has_recovery_checkpoints():
                job_schedule.last_run_started_at = DateTimeHelper.now_default()
                session.commit()
                logger.info(f"Set last_run_started_at = {job_schedule.last_run_started_at}")

        # Simulate job execution with the determined start date
        logger.info(f"AD sync would query data updated >= {start_date.strftime('%Y-%m-%d %H%M')}")
        import asyncio
        await asyncio.sleep(2)  # Simulate work

        # Mark job as completed and set next job to PENDING
        with database.get_write_session_context() as session:
            job_schedule = session.query(JobSchedule).get(job_schedule_id)
            if not job_schedule:
                logger.error(f"Job schedule {job_schedule_id} not found")
                return

            tenant_id = job_schedule.tenant_id
            current_order = job_schedule.execution_order

            # Mark current job as finished
            job_schedule.set_finished()
            logger.info(f"Active Directory sync job completed successfully")

            # Find next ready job (skips paused jobs)
            next_job = find_next_ready_job(session, tenant_id, current_order)

            if next_job:
                next_job.status = 'PENDING'
                logger.info(f"Set next ready job to PENDING: {next_job.job_name} (order: {next_job.execution_order})")

            session.commit()

            # Resume orchestrator countdown and handle scheduling outside transaction
            from app.core.orchestrator_scheduler import get_orchestrator_scheduler
            orchestrator_scheduler = get_orchestrator_scheduler()
            orchestrator_scheduler.resume_orchestrator('Active Directory')

            if next_job:
                # Check if this is cycling back to the first job (restart)
                with database.get_read_session_context() as check_session:
                    first_job = check_session.query(JobSchedule).filter(
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
                        # Normal sequence - use fast transition for quick transition
                        logger.info(f"Next job is in sequence ({next_job.job_name}) - using fast transition for quick transition")
                        orchestrator_scheduler.schedule_fast_transition('Active Directory')
            else:
                # No next job - restore normal schedule
                orchestrator_scheduler.restore_normal_schedule()

    except Exception as e:
        logger.error(f"Active Directory sync job error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")

        # Set job back to PENDING on unexpected error
        from app.core.database import get_database
        database = get_database()

        try:
            with database.get_write_session_context() as fresh_session:
                job_schedule = fresh_session.query(JobSchedule).get(job_schedule_id)
                if job_schedule:
                    job_schedule.status = 'PENDING'
                    job_schedule.error_message = str(e)
                    logger.info("Successfully updated AD job schedule with error status")
        except Exception as session_error:
            logger.error(f"AD job session error: {session_error}")


async def trigger_fabric_sync(force_manual=False, execution_params=None, tenant_id=None):
    """
    Trigger a WEX Fabric sync job.

    Args:
        force_manual: If True, forces correct job states for manual execution
        execution_params: Optional execution parameters for the job
        tenant_id: Tenant ID to trigger job for (required for client isolation)

    Returns:
        Dict containing job execution results
    """
    if tenant_id is None:
        return {
            'status': 'error',
            'message': 'tenant_id is required for job execution'
        }

    try:
        database = get_database()

        with database.get_session() as session:
            # Get the fabric job for this client (case-insensitive)
            fabric_job = session.query(JobSchedule).filter(
                func.lower(JobSchedule.job_name) == 'wex fabric',
                JobSchedule.tenant_id == tenant_id
            ).first()

            if not fabric_job:
                return {
                    'status': 'error',
                    'message': f'WEX Fabric sync job not found for tenant {tenant_id}'
                }

            if force_manual:
                # Set fabric job to PENDING, preserve PAUSED jobs, reset others to READY
                all_jobs = session.query(JobSchedule).filter(
                    JobSchedule.tenant_id == tenant_id,
                    JobSchedule.active == True
                ).all()

                for job in all_jobs:
                    if job.job_name.lower() == 'wex fabric':
                        job.status = 'PENDING'
                        job.error_message = None
                    elif job.status != 'PAUSED':  # Preserve PAUSED jobs
                        job.status = 'READY'
                        job.error_message = None

                session.commit()

        return {
            'status': 'triggered',
            'message': f'WEX Fabric sync job triggered successfully for client {tenant_id}',
            'job_name': 'WEX Fabric'
        }

    except Exception as e:
        logger.error(f"Error triggering fabric sync: {e}")
        return {
            'status': 'error',
            'message': f'Failed to trigger fabric sync: {str(e)}'
        }


async def trigger_ad_sync(force_manual=False, execution_params=None, tenant_id=None):
    """
    Trigger an Active Directory sync job.

    Args:
        force_manual: If True, forces correct job states for manual execution
        execution_params: Optional execution parameters for the job
        tenant_id: Tenant ID to trigger job for (required for client isolation)

    Returns:
        Dict containing job execution results
    """
    if tenant_id is None:
        return {
            'status': 'error',
            'message': 'tenant_id is required for job execution'
        }

    try:
        database = get_database()

        with database.get_session() as session:
            # Get the AD job for this client (case-insensitive)
            ad_job = session.query(JobSchedule).filter(
                func.lower(JobSchedule.job_name) == 'wex ad',
                JobSchedule.tenant_id == tenant_id
            ).first()

            if not ad_job:
                return {
                    'status': 'error',
                    'message': f'WEX AD sync job not found for tenant {tenant_id}'
                }

            if force_manual:
                # Set AD job to PENDING, preserve PAUSED jobs, reset others to NOT_STARTED
                all_jobs = session.query(JobSchedule).filter(
                    JobSchedule.tenant_id == tenant_id,
                    JobSchedule.active == True
                ).all()

                for job in all_jobs:
                    if job.job_name.lower() == 'wex ad':
                        job.status = 'PENDING'
                        job.error_message = None
                    elif job.status != 'PAUSED':  # Preserve PAUSED jobs
                        job.status = 'NOT_STARTED'
                        job.error_message = None

                session.commit()

        return {
            'status': 'triggered',
            'message': f'Active Directory sync job triggered successfully for client {tenant_id}',
            'job_name': 'ad_sync'
        }

    except Exception as e:
        logger.error(f"Error triggering AD sync: {e}")
        return {
            'status': 'error',
            'message': f'Failed to trigger AD sync: {str(e)}'
        }


def initialize_job_schedules():
    """
    Initialize job schedules for ALL clients.

    This should be called once during setup to create initial job records for all clients.
    """
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import Tenant
            clients = session.query(Tenant).filter(Tenant.active == True).all()

            if not clients:
                logger.error("No active clients found. Please run initialize_clients.py first")
                return False

            logger.info(f"Initializing job schedules for {len(clients)} clients")

            for client in clients:
                logger.info(f"Initializing jobs for client: {client.name} (ID: {client.id})")
                success = initialize_job_schedules_for_client(client.id)
                if not success:
                    logger.error(f"Failed to initialize jobs for client {client.name}")
                    return False

            return True

    except Exception as e:
        logger.error(f"Error initializing job schedules: {e}")
        return False


def initialize_job_schedules_for_client(tenant_id: int):
    """
    Initialize job schedules for a specific client.

    Args:
        tenant_id: Tenant ID to initialize jobs for

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        database = get_database()
        with database.get_session() as session:
            # SECURITY: Check if jobs already exist for this client
            existing_jobs = session.query(JobSchedule).filter(JobSchedule.tenant_id == tenant_id).count()
            if existing_jobs > 0:
                logger.info(f"INFO: Job schedules already initialized for client {tenant_id} ({existing_jobs} jobs found)")
                return True

            # Get the client
            from app.models.unified_models import Tenant, Integration
            client = session.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not client:
                logger.error(f"Tenant {tenant_id} not found")
                return False

            # SECURITY: Get integrations for this specific client
            jira_integration = session.query(Integration).filter(
                Integration.provider.ilike('JIRA'),
                Integration.tenant_id == tenant_id
            ).first()

            github_integration = session.query(Integration).filter(
                Integration.provider.ilike('GITHUB'),
                Integration.tenant_id == tenant_id
            ).first()

            # Create initial job schedules for this client
            jira_job = JobSchedule(
                job_name='Jira',
                status='PENDING',  # Start with Jira ready to run
                integration_id=jira_integration.id if jira_integration else None,
                tenant_id=tenant_id  # SECURITY: Use provided tenant_id
            )

            github_job = JobSchedule(
                job_name='GitHub',
                status='READY',  # Start with GitHub ready (prevents wrong execution)
                integration_id=github_integration.id if github_integration else None,
                tenant_id=tenant_id  # SECURITY: Use provided tenant_id
            )

            session.add(jira_job)
            session.add(github_job)
            session.commit()

            logger.info(f"SUCCESS: Job schedules initialized successfully for client {tenant_id}")
            logger.info("   - Jira: PENDING (ready to run first)")
            logger.info("   - GitHub: READY (will be set to PENDING when Jira finishes)")

            return True
            
    except Exception as e:
        logger.error(f"ERROR: Failed to initialize job schedules: {e}")
        return False


def get_job_status(tenant_id: int = None):
    """
    Get the current status of jobs for a specific client.

    Args:
        tenant_id: Tenant ID to filter jobs (required for client isolation)

    Returns:
        Dict with job status information
    """
    try:
        database = get_database()
        with database.get_session() as session:
            # SECURITY: Filter jobs by tenant_id (include all jobs, not just active)
            query = session.query(JobSchedule)
            if tenant_id is not None:
                query = query.filter(JobSchedule.tenant_id == tenant_id)
            jobs = query.all()

            status = {}
            for job in jobs:
                status[job.job_name] = {
                    'status': job.status,
                    'active': job.active,
                    'last_run_started_at': job.last_run_started_at.isoformat() if job.last_run_started_at else None,
                    'last_success_at': job.last_success_at.isoformat() if job.last_success_at else None,
                    'error_message': job.error_message,
                    'retry_count': job.retry_count,
                    'last_repo_sync_checkpoint': job.last_repo_sync_checkpoint.isoformat() if job.last_repo_sync_checkpoint else None
                }

            return status

    except Exception as e:
        logger.error(f"ERROR: Failed to get job status: {e}")
        return {}


async def run_vectorization_sync_async(job_schedule_id: int):
    """
    Async wrapper for Vectorization job.
    Handles job lifecycle and error management.
    """
    try:
        logger.info(f"STARTING: Vectorization job (ID: {job_schedule_id})")

        # Pause orchestrator countdown while job is running
        from app.core.orchestrator_scheduler import get_orchestrator_scheduler
        orchestrator_scheduler = get_orchestrator_scheduler()
        orchestrator_scheduler.pause_orchestrator('Vectorization')

        # Import here to avoid circular imports
        from app.jobs.vectorization.vectorization_job import run_vectorization_sync

        # Use shorter session for job execution
        database = get_database()
        with database.get_job_session_context() as session:
            job_schedule = session.query(JobSchedule).filter(JobSchedule.id == job_schedule_id).first()
            if not job_schedule:
                logger.error(f"Job schedule {job_schedule_id} not found")
                return

            # Execute the job
            result = await run_vectorization_sync(session, job_schedule)

        # Mark job as completed and set next job to PENDING
        with database.get_write_session_context() as session:
            job_schedule = session.query(JobSchedule).get(job_schedule_id)
            if not job_schedule:
                logger.error(f"Job schedule {job_schedule_id} not found")
                return

            tenant_id = job_schedule.tenant_id
            current_order = job_schedule.execution_order

            # Check if job was successful
            if result.get('status') == 'success':
                # Mark current job as finished
                job_schedule.set_finished()
                logger.info(f"Vectorization job completed successfully: {result.get('message', 'No message')}")

                # Send WebSocket completion update
                from app.core.websocket_manager import get_websocket_manager
                websocket_manager = get_websocket_manager()
                await websocket_manager.send_status_update(
                    "Vectorization",
                    "FINISHED",
                    {"message": "Vectorization job completed successfully"}
                )
                # Also send completion message to trigger progress bar hiding
                await websocket_manager.send_completion(
                    "Vectorization",
                    True,
                    {"message": "Vectorization job completed successfully", "result": result}
                )
            else:
                # Mark job as failed using set_pending_with_checkpoint
                error_msg = result.get('message', 'Unknown error')
                job_schedule.set_pending_with_checkpoint(error_msg)
                logger.error(f"Vectorization job failed: {error_msg}")

                # Send WebSocket failure update
                from app.core.websocket_manager import get_websocket_manager
                websocket_manager = get_websocket_manager()
                await websocket_manager.send_status_update(
                    "Vectorization",
                    "FAILED",
                    {"message": f"Vectorization job failed: {error_msg}"}
                )
                # Also send completion message to trigger progress bar hiding
                await websocket_manager.send_completion(
                    "Vectorization",
                    False,
                    {"message": f"Vectorization job failed: {error_msg}", "error": error_msg}
                )

            # Find next ready job (skips paused jobs)
            next_job = find_next_ready_job(session, tenant_id, current_order)

            if next_job:
                next_job.status = 'PENDING'
                logger.info(f"Set next ready job to PENDING: {next_job.job_name} (order: {next_job.execution_order})")
            else:
                logger.info("No more jobs in sequence - cycle complete")

            session.commit()

            # Resume orchestrator countdown and handle scheduling outside transaction
            from app.core.orchestrator_scheduler import get_orchestrator_scheduler
            orchestrator_scheduler = get_orchestrator_scheduler()
            orchestrator_scheduler.resume_orchestrator('Vectorization')

            if next_job:
                # Check if this is cycling back to the first job (restart)
                with database.get_read_session_context() as check_session:
                    first_job = check_session.query(JobSchedule).filter(
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
                        # Normal sequence - use fast transition for quick transition
                        logger.info(f"Next job is in sequence ({next_job.job_name}) - using fast transition for quick transition")
                        orchestrator_scheduler.schedule_fast_transition('Vectorization')
            else:
                # No next job - restore normal schedule
                orchestrator_scheduler.restore_normal_schedule()

    except Exception as e:
        logger.error(f"Vectorization job error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")

        # Set job back to PENDING on unexpected error
        database = get_database()
        try:
            with database.get_write_session_context() as fresh_session:
                job_schedule = fresh_session.query(JobSchedule).get(job_schedule_id)
                if job_schedule:
                    job_schedule.status = 'PENDING'
                    job_schedule.error_message = str(e)
                    logger.info("Successfully updated Vectorization job schedule with error status")
        except Exception as session_error:
            logger.error(f"Vectorization job session error: {session_error}")


async def trigger_vectorization_sync(force_manual=False, execution_params=None, tenant_id=None):
    """
    Trigger a Vectorization job.

    Args:
        force_manual: If True, forces correct job states for manual execution
        execution_params: Optional execution parameters for the job
        tenant_id: Tenant ID to trigger job for (required for client isolation)

    Returns:
        Dict containing job execution results
    """
    if tenant_id is None:
        return {
            'status': 'error',
            'message': 'tenant_id is required for job execution'
        }

    try:
        database = get_database()

        with database.get_session() as session:
            # Get the vectorization job for this client (case-insensitive)
            vectorization_job = session.query(JobSchedule).filter(
                func.lower(JobSchedule.job_name) == 'vectorization',
                JobSchedule.tenant_id == tenant_id
            ).first()

            if not vectorization_job:
                return {
                    'status': 'error',
                    'message': f'Vectorization job not found for tenant {tenant_id}'
                }

            if force_manual:
                # Set vectorization job to PENDING, preserve PAUSED jobs, reset others to READY
                all_jobs = session.query(JobSchedule).filter(
                    JobSchedule.tenant_id == tenant_id,
                    JobSchedule.active == True
                ).all()

                for job in all_jobs:
                    if job.job_name.lower() == 'vectorization':
                        job.status = 'PENDING'
                        job.error_message = None
                    elif job.status != 'PAUSED':  # Preserve PAUSED jobs
                        job.status = 'READY'
                        job.error_message = None

                session.commit()

        return {
            'status': 'triggered',
            'message': f'Vectorization job triggered successfully for client {tenant_id}',
            'job_name': 'Vectorization'
        }

    except Exception as e:
        logger.error(f"Error triggering vectorization sync: {e}")
        return {
            'status': 'error',
            'message': f'Failed to trigger vectorization sync: {str(e)}'
        }
