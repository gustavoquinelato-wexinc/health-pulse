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
from app.models.unified_models import JobSchedule
from fastapi import BackgroundTasks
import asyncio

logger = get_logger(__name__)


async def trigger_jira_sync():
    """
    Trigger a Jira sync job via the orchestration system.

    This function is used by the API to trigger Jira extraction.
    It sets the jira_sync job to PENDING and runs the orchestrator.

    Returns:
        Dict containing job execution results
    """
    try:
        database = get_database()
        with database.get_session() as session:
            # Find or create the jira_sync job
            jira_job = session.query(JobSchedule).filter(JobSchedule.job_name == 'jira_sync').first()

            if not jira_job:
                # Initialize job schedules if they don't exist
                initialize_job_schedules()
                jira_job = session.query(JobSchedule).filter(JobSchedule.job_name == 'jira_sync').first()

            if not jira_job:
                return {
                    'status': 'error',
                    'message': 'Failed to initialize jira_sync job schedule',
                    'issues_processed': 0,
                    'changelogs_processed': 0
                }

            # Set job to PENDING to trigger execution
            jira_job.status = 'PENDING'
            jira_job.error_message = None
            session.commit()

            logger.info(f"TRIGGERED: jira_sync job (ID: {jira_job.id})")

            # Run the orchestrator to process the job
            await run_orchestrator()

            # Check the job status after orchestration
            session.refresh(jira_job)

            if jira_job.status == 'FINISHED':
                return {
                    'status': 'success',
                    'message': 'Jira sync completed successfully',
                    'job_id': str(jira_job.id),
                    'last_success_at': jira_job.last_success_at,
                    'issues_processed': 0,  # TODO: Get actual counts from job results
                    'changelogs_processed': 0  # TODO: Get actual counts from job results
                }
            else:
                return {
                    'status': 'error' if jira_job.status == 'PENDING' else jira_job.status,
                    'message': jira_job.error_message or f'Job status: {jira_job.status}',
                    'job_id': str(jira_job.id),
                    'issues_processed': 0,
                    'changelogs_processed': 0
                }

    except Exception as e:
        logger.error(f"ERROR: Error triggering Jira sync: {e}")
        return {
            'status': 'error',
            'message': f'Failed to trigger Jira sync: {str(e)}',
            'issues_processed': 0,
            'changelogs_processed': 0
        }


async def run_orchestrator():
    """
    Main orchestrator function that runs on schedule.
    
    Checks for PENDING jobs and triggers them asynchronously.
    """
    try:
        logger.info("STARTING: ETL Orchestrator starting...")

        database = get_database()
        with database.get_session() as session:
            # Look for the first PENDING job
            pending_job = session.query(JobSchedule).filter(
                JobSchedule.active == True,
                JobSchedule.status == 'PENDING'
            ).first()

            if not pending_job:
                logger.info("INFO: No PENDING jobs found, orchestrator exiting")
                return

            logger.info(f"FOUND: PENDING job: {pending_job.job_name}")

            # Lock the job by setting it to RUNNING
            pending_job.set_running()
            session.commit()

            logger.info(f"LOCKED: job {pending_job.job_name} (status: RUNNING)")

            # Trigger the appropriate passive job asynchronously
            if pending_job.job_name == 'jira_sync':
                logger.info("TRIGGERING: Jira sync job...")
                asyncio.create_task(run_jira_sync_async(pending_job.id))
            elif pending_job.job_name == 'github_sync':
                logger.info("TRIGGERING: GitHub sync job...")
                asyncio.create_task(run_github_sync_async(pending_job.id))
            else:
                logger.error(f"ERROR: Unknown job name: {pending_job.job_name}")
                # Reset job to PENDING if unknown
                pending_job.status = 'PENDING'
                session.commit()
                return

            logger.info(f"SUCCESS: Orchestrator completed - {pending_job.job_name} job triggered")
            
    except Exception as e:
        logger.error(f"ERROR: Orchestrator error: {e}")
        import traceback
        traceback.print_exc()


async def run_jira_sync_async(job_schedule_id: int):
    """
    Asynchronous wrapper for Jira sync job.

    Args:
        job_schedule_id: ID of the job schedule record
    """
    try:
        from app.jobs.jira.jira_job import run_jira_sync
        
        database = get_database()
        with database.get_session() as session:
            job_schedule = session.query(JobSchedule).filter(JobSchedule.id == job_schedule_id).first()
            if not job_schedule:
                logger.error(f"ERROR: Job schedule {job_schedule_id} not found")
                return

            logger.info(f"STARTING: Jira sync job (ID: {job_schedule_id})")
            await asyncio.to_thread(run_jira_sync, session, job_schedule)

    except Exception as e:
        logger.error(f"ERROR: Error in async Jira sync: {e}")
        import traceback
        traceback.print_exc()


async def run_github_sync_async(job_schedule_id: int):
    """
    Asynchronous wrapper for GitHub sync job.

    Args:
        job_schedule_id: ID of the job schedule record
    """
    try:
        from app.jobs.github.github_job import run_github_sync
        
        database = get_database()
        with database.get_session() as session:
            job_schedule = session.query(JobSchedule).filter(JobSchedule.id == job_schedule_id).first()
            if not job_schedule:
                logger.error(f"ERROR: Job schedule {job_schedule_id} not found")
                return

            logger.info(f"STARTING: GitHub sync job (ID: {job_schedule_id})")
            await asyncio.to_thread(run_github_sync, session, job_schedule)

    except Exception as e:
        logger.error(f"ERROR: Error in async GitHub sync: {e}")
        import traceback
        traceback.print_exc()


def initialize_job_schedules():
    """
    Initialize the job schedules table with default jobs.
    
    This should be called once during setup to create the initial job records.
    """
    try:
        database = get_database()
        with database.get_session() as session:
            # Check if jobs already exist
            existing_jobs = session.query(JobSchedule).count()
            if existing_jobs > 0:
                logger.info(f"INFO: Job schedules already initialized ({existing_jobs} jobs found)")
                return True
            
            # Get the first client (default client)
            from app.models.unified_models import Client
            client = session.query(Client).first()
            if not client:
                logger.error("No client found. Please run initialize_clients.py first")
                return False

            # Create initial job schedules
            jira_job = JobSchedule(
                job_name='jira_sync',
                status='PENDING',  # Start with Jira ready to run
                client_id=client.id
            )

            github_job = JobSchedule(
                job_name='github_sync',
                status='NOT_STARTED',  # Start with GitHub not started (prevents wrong execution)
                client_id=client.id
            )

            session.add(jira_job)
            session.add(github_job)
            session.commit()

            logger.info("SUCCESS: Job schedules initialized successfully")
            logger.info("   - jira_sync: PENDING (ready to run first)")
            logger.info("   - github_sync: NOT_STARTED (will be set to PENDING when Jira finishes)")
            
            return True
            
    except Exception as e:
        logger.error(f"ERROR: Failed to initialize job schedules: {e}")
        return False


def get_job_status():
    """
    Get the current status of all jobs.
    
    Returns:
        Dict with job status information
    """
    try:
        database = get_database()
        with database.get_session() as session:
            jobs = session.query(JobSchedule).filter(JobSchedule.active == True).all()
            
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
