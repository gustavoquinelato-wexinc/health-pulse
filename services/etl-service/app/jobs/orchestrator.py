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
- NOT_STARTED: Job has never run (ignored by orchestrator)
- PENDING: Job is ready to run (picked up by orchestrator)
- RUNNING: Job is currently executing (locked)
- FINISHED: Job completed successfully
- On completion: Current job sets itself to FINISHED and next job to PENDING
"""

from sqlalchemy.orm import Session
from app.core.database import get_database
from app.core.logging_config import get_logger
from app.core.job_manager import get_job_manager
from app.core.utils import DateTimeHelper
from app.models.unified_models import JobSchedule
from fastapi import BackgroundTasks
import asyncio

logger = get_logger(__name__)


async def trigger_jira_sync(force_manual=False, execution_params=None, client_id=None):
    """
    Trigger a Jira sync job via the orchestration system for a specific client.

    Args:
        force_manual: If True, forces correct job states for manual execution
                     (jira_sync=PENDING, github_sync=NOT_STARTED).
                     If False, uses normal orchestrator logic.
        execution_params: Optional execution parameters for the job
        client_id: Client ID to trigger job for (required for client isolation)

    Returns:
        Dict containing job execution results
    """
    if client_id is None:
        return {
            'status': 'error',
            'message': 'client_id is required for job execution',
            'issues_processed': 0,
            'changelogs_processed': 0
        }

    try:
        database = get_database()
        with database.get_session() as session:
            # ✅ SECURITY: Find or create jobs filtered by client_id
            jira_job = session.query(JobSchedule).filter(
                JobSchedule.job_name == 'jira_sync',
                JobSchedule.client_id == client_id
            ).first()
            github_job = session.query(JobSchedule).filter(
                JobSchedule.job_name == 'github_sync',
                JobSchedule.client_id == client_id
            ).first()

            if not jira_job or not github_job:
                # Initialize job schedules if they don't exist for this client
                initialize_job_schedules_for_client(client_id)
                jira_job = session.query(JobSchedule).filter(
                    JobSchedule.job_name == 'jira_sync',
                    JobSchedule.client_id == client_id
                ).first()
                github_job = session.query(JobSchedule).filter(
                    JobSchedule.job_name == 'github_sync',
                    JobSchedule.client_id == client_id
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
                # - github_sync = NOT_STARTED (will be set to PENDING when Jira finishes)
                jira_job.status = 'PENDING'
                jira_job.error_message = None
                github_job.status = 'NOT_STARTED'
                github_job.error_message = None
                session.commit()

                # Reset retry attempts when manually triggered
                from app.core.orchestrator_scheduler import get_orchestrator_scheduler
                orchestrator_scheduler = get_orchestrator_scheduler()
                orchestrator_scheduler.force_reset_retry_attempts('jira_sync')

                logger.info(f"TRIGGERED: jira_sync job (ID: {jira_job.id}) - MANUAL MODE - forced job states")
                logger.info(f"   - jira_sync: PENDING")
                logger.info(f"   - github_sync: NOT_STARTED")
            else:
                # Normal mode: just set jira_sync to PENDING (for API/regular triggers)
                jira_job.status = 'PENDING'
                jira_job.error_message = None
                session.commit()

                logger.info(f"TRIGGERED: jira_sync job (ID: {jira_job.id}) - NORMAL MODE")

            # Trigger the orchestrator to process the job for this client only (non-blocking)
            asyncio.create_task(run_orchestrator_for_client(client_id))

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


async def trigger_github_sync(force_manual=False, execution_params=None, client_id=None):
    """
    Trigger a GitHub sync job via the orchestration system for a specific client.

    Args:
        force_manual: If True, forces correct job states for manual execution
                     (jira_sync=FINISHED, github_sync=PENDING).
                     If False, uses normal orchestrator logic.
        execution_params: Optional execution parameters for the job
        client_id: Client ID to trigger job for (required for client isolation)

    Returns:
        Dict containing job execution results
    """
    if client_id is None:
        return {
            'status': 'error',
            'message': 'client_id is required for job execution',
            'pull_requests_processed': 0,
            'commits_processed': 0
        }

    try:
        database = get_database()
        with database.get_session() as session:
            # ✅ SECURITY: Find or create jobs filtered by client_id
            jira_job = session.query(JobSchedule).filter(
                JobSchedule.job_name == 'jira_sync',
                JobSchedule.client_id == client_id
            ).first()
            github_job = session.query(JobSchedule).filter(
                JobSchedule.job_name == 'github_sync',
                JobSchedule.client_id == client_id
            ).first()

            if not jira_job or not github_job:
                # Initialize job schedules if they don't exist for this client
                initialize_job_schedules_for_client(client_id)
                jira_job = session.query(JobSchedule).filter(
                    JobSchedule.job_name == 'jira_sync',
                    JobSchedule.client_id == client_id
                ).first()
                github_job = session.query(JobSchedule).filter(
                    JobSchedule.job_name == 'github_sync',
                    JobSchedule.client_id == client_id
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

            # Trigger the orchestrator to process the job for this client only (non-blocking)
            asyncio.create_task(run_orchestrator_for_client(client_id))

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

    Checks for PENDING jobs across ALL clients and triggers them asynchronously.
    Each client's jobs are processed independently.
    """
    try:
        logger.info("STARTING: ETL Orchestrator starting...")

        database = get_database()

        # ✅ SECURITY: Get all clients and process their jobs independently
        with database.get_session() as session:
            from app.models.unified_models import Client
            clients = session.query(Client).filter(Client.active == True).all()

            if not clients:
                logger.warning("No active clients found")
                return

            logger.info(f"Processing jobs for {len(clients)} active clients")

        # Process each client's jobs independently based on their individual settings
        for client in clients:
            try:
                # ✅ SECURITY: Check if this client's orchestrator should run based on their settings
                should_run = await should_run_orchestrator_for_client(client.id)
                if should_run:
                    logger.info(f"Processing jobs for client: {client.name} (ID: {client.id}) - interval elapsed")
                    await run_orchestrator_for_client(client.id)
                else:
                    logger.debug(f"Skipping client {client.name} (ID: {client.id}) - interval not elapsed or disabled")
            except Exception as e:
                logger.error(f"Error processing jobs for client {client.name}: {e}")
                continue

    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")


async def should_run_orchestrator_for_client(client_id: int) -> bool:
    """
    Check if the orchestrator should run for a specific client based on their settings.

    Args:
        client_id: Client ID to check

    Returns:
        bool: True if orchestrator should run for this client, False otherwise
    """
    try:
        from app.core.settings_manager import is_orchestrator_enabled, get_orchestrator_interval

        # Check if orchestrator is enabled for this client
        if not is_orchestrator_enabled(client_id):
            return False

        # Get client's orchestrator interval
        interval_minutes = get_orchestrator_interval(client_id)

        # Check when the last orchestrator run was for this client
        database = get_database()
        with database.get_session() as session:
            # Find the most recent job run for this client
            last_run = session.query(JobSchedule.last_run_started_at).filter(
                JobSchedule.client_id == client_id,
                JobSchedule.last_run_started_at.isnot(None)
            ).order_by(JobSchedule.last_run_started_at.desc()).first()

            if not last_run or not last_run[0]:
                # No previous runs - should run now
                logger.info(f"Client {client_id}: No previous runs found - should run")
                return True

            # Calculate time since last run
            from datetime import timedelta
            last_run_time = last_run[0]
            now = DateTimeHelper.now_utc()
            time_since_last_run = now - last_run_time
            interval_delta = timedelta(minutes=interval_minutes)

            should_run = time_since_last_run >= interval_delta

            if should_run:
                logger.info(f"Client {client_id}: Interval elapsed ({time_since_last_run.total_seconds()/60:.1f}min >= {interval_minutes}min) - should run")
            else:
                remaining_minutes = (interval_delta - time_since_last_run).total_seconds() / 60
                logger.debug(f"Client {client_id}: Interval not elapsed - {remaining_minutes:.1f}min remaining")

            return should_run

    except Exception as e:
        logger.error(f"Error checking if orchestrator should run for client {client_id}: {e}")
        return False


async def run_orchestrator_for_client(client_id: int):
    """
    Run orchestrator for a specific client.

    Args:
        client_id: Client ID to process jobs for
    """
    try:
        database = get_database()

        # Step 1: Quick check for pending jobs for this client
        pending_job_id = None
        pending_job_name = None

        with database.get_session() as session:
            # ✅ SECURITY: Find pending jobs filtered by client_id
            result = session.query(
                JobSchedule.id,
                JobSchedule.job_name
            ).filter(
                JobSchedule.client_id == client_id,
                JobSchedule.active == True,
                JobSchedule.status == 'PENDING'
            ).first()

            if not result:
                logger.info(f"INFO: No PENDING jobs found for client {client_id}, orchestrator exiting")
                return

            pending_job_id, pending_job_name = result.id, result.job_name
            logger.info(f"FOUND: PENDING job for client {client_id}: {pending_job_name} (ID: {pending_job_id})")

        # Step 2: Quick atomic update to lock the job (separate short session)
        with database.get_session() as session:
            # ✅ SECURITY: Atomic update with client_id verification
            updated_rows = session.query(JobSchedule).filter(
                JobSchedule.id == pending_job_id,
                JobSchedule.client_id == client_id,  # Verify client_id
                JobSchedule.status == 'PENDING'  # Double-check it's still pending
            ).update({
                'status': 'RUNNING',
                'last_run_started_at': DateTimeHelper.now_utc(),
                'error_message': None
            })

            if updated_rows == 0:
                logger.info(f"INFO: Job was already picked up by another orchestrator instance for client {client_id}")
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

        # Step 4: Trigger the job asynchronously (outside of database session)
        if pending_job_name == 'jira_sync':
            logger.info("TRIGGERING: Jira sync job...")
            asyncio.create_task(run_jira_sync_async(pending_job_id))
        elif pending_job_name == 'github_sync':
            logger.info("TRIGGERING: GitHub sync job...")
            asyncio.create_task(run_github_sync_async(pending_job_id))
        else:
            logger.error(f"ERROR: Unknown job name: {pending_job_name}")
            # Reset job to PENDING if unknown (separate session)
            with database.get_session() as session:
                session.query(JobSchedule).filter(
                    JobSchedule.id == pending_job_id
                ).update({'status': 'PENDING'})
                session.commit()
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


def initialize_job_schedules():
    """
    Initialize job schedules for ALL clients.

    This should be called once during setup to create initial job records for all clients.
    """
    try:
        database = get_database()
        with database.get_session() as session:
            from app.models.unified_models import Client
            clients = session.query(Client).filter(Client.active == True).all()

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


def initialize_job_schedules_for_client(client_id: int):
    """
    Initialize job schedules for a specific client.

    Args:
        client_id: Client ID to initialize jobs for

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        database = get_database()
        with database.get_session() as session:
            # ✅ SECURITY: Check if jobs already exist for this client
            existing_jobs = session.query(JobSchedule).filter(JobSchedule.client_id == client_id).count()
            if existing_jobs > 0:
                logger.info(f"INFO: Job schedules already initialized for client {client_id} ({existing_jobs} jobs found)")
                return True

            # Get the client
            from app.models.unified_models import Client, Integration
            client = session.query(Client).filter(Client.id == client_id).first()
            if not client:
                logger.error(f"Client {client_id} not found")
                return False

            # ✅ SECURITY: Get integrations for this specific client
            jira_integration = session.query(Integration).filter(
                Integration.name.ilike('JIRA'),
                Integration.client_id == client_id
            ).first()

            github_integration = session.query(Integration).filter(
                Integration.name.ilike('GITHUB'),
                Integration.client_id == client_id
            ).first()

            # Create initial job schedules for this client
            jira_job = JobSchedule(
                job_name='jira_sync',
                status='PENDING',  # Start with Jira ready to run
                integration_id=jira_integration.id if jira_integration else None,
                client_id=client_id  # ✅ SECURITY: Use provided client_id
            )

            github_job = JobSchedule(
                job_name='github_sync',
                status='NOT_STARTED',  # Start with GitHub not started (prevents wrong execution)
                integration_id=github_integration.id if github_integration else None,
                client_id=client_id  # ✅ SECURITY: Use provided client_id
            )

            session.add(jira_job)
            session.add(github_job)
            session.commit()

            logger.info(f"SUCCESS: Job schedules initialized successfully for client {client_id}")
            logger.info("   - jira_sync: PENDING (ready to run first)")
            logger.info("   - github_sync: NOT_STARTED (will be set to PENDING when Jira finishes)")

            return True
            
    except Exception as e:
        logger.error(f"ERROR: Failed to initialize job schedules: {e}")
        return False


def get_job_status(client_id: int = None):
    """
    Get the current status of jobs for a specific client.

    Args:
        client_id: Client ID to filter jobs (required for client isolation)

    Returns:
        Dict with job status information
    """
    try:
        database = get_database()
        with database.get_session() as session:
            # ✅ SECURITY: Filter jobs by client_id
            query = session.query(JobSchedule).filter(JobSchedule.active == True)
            if client_id is not None:
                query = query.filter(JobSchedule.client_id == client_id)
            jobs = query.all()

            status = {}
            for job in jobs:
                status[job.job_name] = {
                    'status': job.status,
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
