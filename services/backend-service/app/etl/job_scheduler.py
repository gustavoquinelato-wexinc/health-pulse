"""
Individual Job Timers for ETL Jobs

This module provides truly independent job execution.
Each job gets its own timer and runs independently (like WebSocket handshake pattern).
No central orchestrator or monitoring - pure job autonomy.
"""

import asyncio
import logging
from typing import Optional, Dict
import pytz
import os
from sqlalchemy import text
from app.core.database import get_database

logger = logging.getLogger(__name__)

class IndividualJobTimer:
    """
    Individual job timer - each job gets its own timer instance.

    Similar to WebSocket handshake pattern:
    - Each job establishes its own "timer connection"
    - Jobs run completely independently with their own settings
    - No global monitoring - each job manages itself
    - Auto-starts when backend-service starts
    """

    def __init__(self, job_id: int, job_name: str, tenant_id: int):
        self.job_id = job_id
        self.job_name = job_name
        self.tenant_id = tenant_id
        self.running = False
        self.timer_task: Optional[asyncio.Task] = None
        self.timezone = pytz.timezone(os.getenv('SCHEDULER_TIMEZONE', 'America/New_York'))

    async def start(self):
        """Start this job's individual timer"""
        if self.running:
            logger.warning(f"Job timer for '{self.job_name}' is already running")
            return

        self.running = True
        print(f"🚀 TIMER: Starting individual timer for job '{self.job_name}' (ID: {self.job_id})")  # Force print
        logger.info(f"🚀 Starting individual timer for job '{self.job_name}' (ID: {self.job_id})")

        # Calculate initial delay until next run
        next_run_delay = await self._calculate_initial_delay()
        if next_run_delay is not None:
            print(f"   - TIMER: Next run in {next_run_delay:.1f} minutes")  # Force print
            logger.info(f"   - Next run in {next_run_delay:.1f} minutes")
            # Start the individual timer for this job
            self.timer_task = asyncio.create_task(self._job_timer_loop(next_run_delay))
            print(f"   - TIMER: Timer task created for job '{self.job_name}'")  # Force print
        else:
            print(f"   - TIMER: Job '{self.job_name}' is not ready to schedule")  # Force print
            logger.info(f"   - Job '{self.job_name}' is not ready to schedule")

    async def stop(self):
        """Stop this job's individual timer"""
        self.running = False
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
            try:
                await self.timer_task
            except asyncio.CancelledError:
                pass
        logger.info(f"⏹️ Stopped individual timer for job '{self.job_name}'")

    async def _calculate_initial_delay(self) -> Optional[float]:
        """Calculate minutes until this job should run next"""
        try:
            database = get_database()
            with database.get_read_session_context() as session:

                # Get this specific job's details including next_run
                query = text("""
                    SELECT
                        status->>'overall' as overall_status, active, next_run, schedule_interval_minutes
                    FROM etl_jobs
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                result = session.execute(query, {'job_id': self.job_id, 'tenant_id': self.tenant_id}).fetchone()

                if not result:
                    logger.warning(f"Job '{self.job_name}' (ID: {self.job_id}) not found")
                    return None

                status, active, next_run, schedule_interval_minutes = result

                if not active:
                    logger.info(f"Job '{self.job_name}' is inactive - not scheduling")
                    return None

                if status == 'RUNNING':
                    logger.info(f"Job '{self.job_name}' is already running - not scheduling")
                    return None

                from app.core.utils import DateTimeHelper
                now = DateTimeHelper.now_default()

                # If next_run is not set, calculate it and update database
                if next_run is None:
                    logger.info(f"Job '{self.job_name}' has no next_run set - calculating initial schedule")
                    from datetime import timedelta
                    next_run = now + timedelta(minutes=schedule_interval_minutes)

                    # Update database with calculated next_run
                    update_query = text("""
                        UPDATE etl_jobs
                        SET next_run = :next_run, last_updated_at = :now
                        WHERE id = :job_id AND tenant_id = :tenant_id
                    """)
                    session.execute(update_query, {
                        'next_run': next_run,
                        'now': now,
                        'job_id': self.job_id,
                        'tenant_id': self.tenant_id
                    })
                    session.commit()
                    logger.info(f"Set initial next_run for job '{self.job_name}' to {next_run}")

                # Calculate delay until next_run
                delay_minutes = (next_run - now).total_seconds() / 60
                return max(0, delay_minutes)  # Don't return negative delays

        except Exception as e:
            logger.error(f"Error calculating initial delay for job '{self.job_name}': {e}")
            return None

    async def _job_timer_loop(self, initial_delay_minutes: float):
        """Individual timer loop for this specific job"""
        try:
            # Wait for the initial delay
            if initial_delay_minutes > 0:
                logger.info(f"⏱️ Job '{self.job_name}' waiting {initial_delay_minutes:.1f} minutes until next run")
                await asyncio.sleep(initial_delay_minutes * 60)  # Convert to seconds

            while self.running:
                # Trigger this job
                logger.info(f"⏰ ========== TIMER LOOP ITERATION START for '{self.job_name}' ==========")
                logger.info(f"⏰ Time to run job '{self.job_name}' (ID: {self.job_id})")
                await self._trigger_job()

                # Wait for job to complete before calculating next interval
                logger.info(f"⏳ Waiting for job '{self.job_name}' to complete...")
                await self._wait_for_job_completion()
                logger.info(f"✅ Job '{self.job_name}' completion detected")

                # Calculate next run interval
                logger.info(f"📊 Calculating next interval for '{self.job_name}'...")
                next_interval = await self._get_next_interval()

                if next_interval and next_interval > 0:
                    logger.info(f"⏱️ Job '{self.job_name}' scheduled to run again in {next_interval:.1f} minutes")
                    logger.info(f"😴 Timer sleeping for {next_interval:.1f} minutes...")
                    await asyncio.sleep(next_interval * 60)  # Convert to seconds
                    logger.info(f"⏰ Timer woke up for '{self.job_name}' - starting next iteration")
                else:
                    logger.info(f"⏹️ Job '{self.job_name}' not scheduled for next run - stopping timer")
                    break

        except asyncio.CancelledError:
            logger.info(f"⏹️ Timer cancelled for job '{self.job_name}'")
        except Exception as e:
            logger.error(f"Error in timer loop for job '{self.job_name}': {e}")

    async def _wait_for_job_completion(self):
        """Wait for the job to complete (status changes from RUNNING to READY/FINISHED/FAILED)"""
        try:
            max_wait_seconds = 3600  # 1 hour max wait
            poll_interval = 2  # Check every 2 seconds
            elapsed = 0

            database = get_database()
            while elapsed < max_wait_seconds:
                with database.get_read_session_context() as session:
                    query = text("""
                        SELECT status->>'overall' as overall_status
                        FROM etl_jobs
                        WHERE id = :job_id AND tenant_id = :tenant_id
                    """)
                    result = session.execute(query, {'job_id': self.job_id, 'tenant_id': self.tenant_id}).fetchone()

                    if not result:
                        logger.warning(f"Job '{self.job_name}' not found while waiting for completion")
                        return

                    status = result[0]

                    # Job is no longer running - it's completed
                    if status != 'RUNNING':
                        logger.info(f"✅ Job '{self.job_name}' completed with status: {status}")
                        # Wait a bit more to ensure job fully transitions to READY and next_run is set
                        await asyncio.sleep(3)
                        return

                # Still running, wait a bit
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            logger.warning(f"⚠️ Job '{self.job_name}' still running after {max_wait_seconds}s - continuing anyway")

        except Exception as e:
            logger.error(f"Error waiting for job completion '{self.job_name}': {e}")

    async def _get_next_interval(self) -> Optional[float]:
        """Get the interval (in minutes) until this job should run next based on next_run column"""
        try:
            database = get_database()
            with database.get_read_session_context() as session:

                # Get updated job details including next_run
                query = text("""
                    SELECT status->>'overall' as overall_status, active, next_run
                    FROM etl_jobs
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                result = session.execute(query, {'job_id': self.job_id, 'tenant_id': self.tenant_id}).fetchone()

                if not result:
                    return None

                status, active, next_run = result

                if not active or status == 'RUNNING':
                    return None

                if next_run is None:
                    logger.warning(f"Job '{self.job_name}' has no next_run set after execution")
                    return None

                # Calculate delay until next_run
                from app.core.utils import DateTimeHelper
                now = DateTimeHelper.now_default()
                delay_minutes = (next_run - now).total_seconds() / 60

                logger.info(f"📅 Job '{self.job_name}' next_run calculation:")
                logger.info(f"   Current time: {now}")
                logger.info(f"   Next run time: {next_run}")
                logger.info(f"   Delay: {delay_minutes:.2f} minutes")

                # CRITICAL: If delay is negative or very small, it means next_run is in the past
                # This can happen due to:
                # 1. Clock skew between when job finished and when we check
                # 2. Job took longer than expected
                # 3. Manual trigger while automatic timer was waiting
                # In all cases, we should use the schedule_interval_minutes as the delay
                if delay_minutes < 1:  # Less than 1 minute means something is wrong
                    logger.warning(f"⚠️ Delay too small ({delay_minutes:.2f} min) - next_run appears to be in the past")

                    # Get the schedule interval and use that as the delay
                    schedule_query = text("""
                        SELECT schedule_interval_minutes
                        FROM etl_jobs
                        WHERE id = :job_id AND tenant_id = :tenant_id
                    """)
                    schedule_result = session.execute(schedule_query, {
                        'job_id': self.job_id,
                        'tenant_id': self.tenant_id
                    }).fetchone()

                    if schedule_result:
                        fallback_delay = schedule_result[0]
                        logger.warning(f"⚠️ Using schedule_interval_minutes ({fallback_delay} min) as fallback delay")
                        return fallback_delay
                    else:
                        logger.error(f"⚠️ Could not get schedule_interval - stopping timer")
                        return None

                return delay_minutes

        except Exception as e:
            logger.error(f"Error getting next interval for job '{self.job_name}': {e}")
            return None
            

    async def _trigger_job(self):
        """Trigger this job's execution"""
        try:
            database = get_database()
            with database.get_read_session_context() as session:
                # First check if job is already running
                check_query = text("""
                    SELECT status->>'overall' as overall_status
                    FROM etl_jobs
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)
                result = session.execute(check_query, {
                    'job_id': self.job_id,
                    'tenant_id': self.tenant_id
                }).fetchone()

                if not result:
                    logger.error(f"Job '{self.job_name}' (ID: {self.job_id}) not found")
                    return

                current_status = result[0]
                logger.info(f"🔍 [TRIGGER] Job '{self.job_name}' current status: {current_status}")

                # Only trigger if job is in READY or RATE_LIMITED status
                if current_status == 'RUNNING':
                    logger.warning(f"⚠️ Job '{self.job_name}' is already RUNNING - skipping automatic trigger")
                    return

                if current_status == 'FINISHED':
                    # Edge case: Job is stuck in FINISHED (embedding still processing)
                    # Reschedule with fast retry interval to check again soon
                    logger.warning(f"⚠️ Job '{self.job_name}' is still FINISHED - rescheduling with fast retry interval")
                    await self._reschedule_with_fast_retry(session)
                    return

                # 🔑 Allow RATE_LIMITED jobs to auto-resume when next_run time is reached
                if current_status == 'RATE_LIMITED':
                    logger.info(f"✅ RATE_LIMITED AUTO-RESUME: Job '{self.job_name}' will resume from rate limit")

                if current_status not in ['READY', 'RATE_LIMITED']:
                    logger.warning(f"⚠️ Job '{self.job_name}' has status '{current_status}' (expected READY or RATE_LIMITED) - skipping automatic trigger")
                    return

                # Set job to RUNNING status with proper timezone handling
                from app.core.utils import DateTimeHelper
                import uuid
                now = DateTimeHelper.now_default()
                job_token = str(uuid.uuid4())  # 🔑 Generate unique token for this job execution

                # Use atomic update with WHERE clause to prevent race conditions
                # 🔑 Set both overall status to RUNNING and token for this execution
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = jsonb_set(
                          jsonb_set(status, ARRAY['overall'], to_jsonb('RUNNING'::text)),
                          ARRAY['token'],
                          to_jsonb(CAST(:token AS text))
                        ),
                        last_run_started_at = :now,
                        last_updated_at = :now
                    WHERE id = :job_id AND tenant_id = :tenant_id AND status->>'overall' = 'READY'
                """)

                rows_updated = session.execute(update_query, {
                    'job_id': self.job_id,
                    'tenant_id': self.tenant_id,
                    'now': now,
                    'token': job_token  # 🔑 Pass the generated token
                }).rowcount
                session.commit()

                # If no rows were updated, job was already set to a processing status by another process
                if rows_updated == 0:
                    logger.warning(f"⚠️ Job '{self.job_name}' was already started by another process - skipping")
                    return

            logger.info(f"🚀 AUTO-TRIGGERED job '{self.job_name}' (ID: {self.job_id}) for tenant {self.tenant_id}")

            # Execute the actual job based on job type
            asyncio.create_task(self._execute_actual_job())

        except Exception as e:
            logger.error(f"Error triggering job '{self.job_name}': {e}")

    async def _reschedule_with_fast_retry(self, session):
        """
        Reschedule job with fast retry interval when stuck in FINISHED status.

        This handles the edge case where:
        1. Close message arrives early → sets last_run_finished_at
        2. Embedding still processing → job stays FINISHED
        3. Without this, job would wait full schedule_interval before trying again

        Solution: Use fast retry interval (15 min) to check again soon
        """
        try:
            from datetime import timedelta
            from app.core.utils import DateTimeHelper

            now = DateTimeHelper.now_default()

            # Use fast retry interval (15 minutes) instead of full schedule interval
            # This allows quick recovery when embedding is still processing
            fast_retry_minutes = 15
            next_run = now + timedelta(minutes=fast_retry_minutes)

            update_query = text("""
                UPDATE etl_jobs
                SET next_run = :next_run,
                    last_updated_at = :now
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)

            session.execute(update_query, {
                'job_id': self.job_id,
                'tenant_id': self.tenant_id,
                'next_run': next_run,
                'now': now
            })
            session.commit()

            logger.info(f"🔄 Job '{self.job_name}' rescheduled with fast retry: next_run = {next_run} (15 min from now)")

        except Exception as e:
            logger.error(f"Error rescheduling job '{self.job_name}' with fast retry: {e}")

    async def _simulate_job_execution(self):
        """Simulate job execution (temporary - replace with actual job logic)"""
        try:
            # Simulate work
            await asyncio.sleep(5)

            # Mark job as completed and calculate next_run
            from app.core.utils import DateTimeHelper
            from datetime import timedelta
            now = DateTimeHelper.now_default()

            database = get_database()
            with database.get_write_session_context() as session:
                # Get job's schedule interval to calculate next_run
                schedule_query = text("""
                    SELECT schedule_interval_minutes
                    FROM etl_jobs
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)
                schedule_result = session.execute(schedule_query, {
                    'job_id': self.job_id,
                    'tenant_id': self.tenant_id
                }).fetchone()

                if schedule_result:
                    schedule_interval_minutes = schedule_result[0]
                    next_run = now + timedelta(minutes=schedule_interval_minutes)
                else:
                    next_run = now + timedelta(minutes=360)  # Default 6 hours

                update_query = text("""
                    UPDATE etl_jobs
                    SET status = 'READY',
                        last_run_finished_at = :now,
                        last_updated_at = :now,
                        next_run = :next_run,
                        error_message = NULL,
                        retry_count = 0
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                session.execute(update_query, {
                    'job_id': self.job_id,
                    'tenant_id': self.tenant_id,
                    'now': now,
                    'next_run': next_run
                })
                session.commit()

                logger.info(f"✅ Job '{self.job_name}' completed - next run scheduled for {next_run}")

            logger.info(f"✅ Completed simulated job '{self.job_name}' (ID: {self.job_id})")

        except Exception as e:
            logger.error(f"Error in simulated job execution for '{self.job_name}': {e}")

    async def _execute_actual_job(self):
        """Execute the actual job based on job type"""
        try:
            logger.info(f"🚀 ETL JOB STARTED: '{self.job_name}' (ID: {self.job_id}) - Beginning execution")
            logger.info(f"🔧 Starting actual execution for job '{self.job_name}' (ID: {self.job_id})")

            # Get integration information for this job
            database = get_database()
            with database.get_read_session_context() as session:
                # Get job details and integration info
                job_query = text("""
                    SELECT ej.job_name, ej.integration_id, i.provider, i.type
                    FROM etl_jobs ej
                    JOIN integrations i ON ej.integration_id = i.id
                    WHERE ej.id = :job_id AND ej.tenant_id = :tenant_id
                """)

                job_result = session.execute(job_query, {
                    'job_id': self.job_id,
                    'tenant_id': self.tenant_id
                }).fetchone()

                if not job_result:
                    raise Exception(f"Job {self.job_id} not found or integration missing")

                job_name, integration_id, provider, integration_type = job_result
                logger.info(f"🔍 Job details: {job_name}, Integration: {integration_id} ({provider}/{integration_type})")

            # Queue job for extraction instead of executing directly
            if job_name.lower() == 'jira':
                logger.info("🚀 Queuing Jira extraction job for background processing...")
                success = await self._queue_jira_extraction(integration_id)

                if success:
                    logger.info(f"✅ Jira extraction job queued successfully for integration {integration_id}")
                else:
                    logger.error(f"❌ Failed to queue Jira extraction job for integration {integration_id}")
                    await self._mark_job_failed("Failed to queue extraction job")

            elif job_name.lower() == 'github':
                logger.info("🚀 Queuing GitHub extraction job...")
                from app.etl.jobs import _queue_github_extraction_job

                success = await _queue_github_extraction_job(self.tenant_id, integration_id, self.job_id)
                if success:
                    logger.info(f"✅ GitHub extraction job queued successfully for integration {integration_id}")
                else:
                    logger.error(f"❌ Failed to queue GitHub extraction job for integration {integration_id}")
                    await self._mark_job_failed("Failed to queue extraction job")

            else:
                logger.warning(f"Unknown job type: {job_name} - marking as completed")
                await self._mark_job_completed()

            logger.info(f"✅ Job '{self.job_name}' execution completed")
            logger.info(f"🏁 ETL JOB FINISHED: '{self.job_name}' (ID: {self.job_id}) - Execution completed successfully")

        except Exception as e:
            logger.error(f"❌ Error executing job '{self.job_name}': {e}")
            import traceback
            logger.error(f"❌ Job execution traceback: {traceback.format_exc()}")
            logger.error(f"💥 ETL JOB FAILED: '{self.job_name}' (ID: {self.job_id}) - Execution failed with error: {e}")

            # Mark job as failed
            await self._mark_job_failed(str(e))

    async def _mark_job_completed(self):
        """Mark job as completed and calculate next run"""
        try:
            from app.core.utils import DateTimeHelper
            from datetime import timedelta
            now = DateTimeHelper.now_default()

            database = get_database()
            with database.get_write_session_context() as session:
                # Get job's schedule interval to calculate next_run
                schedule_query = text("""
                    SELECT schedule_interval_minutes
                    FROM etl_jobs
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)
                schedule_result = session.execute(schedule_query, {
                    'job_id': self.job_id,
                    'tenant_id': self.tenant_id
                }).fetchone()

                if schedule_result:
                    schedule_interval_minutes = schedule_result[0]
                    next_run = now + timedelta(minutes=schedule_interval_minutes)
                else:
                    next_run = now + timedelta(minutes=360)  # Default 6 hours

                # Update job status to READY and set next_run
                update_query = text("""
                    UPDATE etl_jobs
                    SET status = 'READY',
                        last_run_finished_at = :now,
                        last_updated_at = :now,
                        next_run = :next_run,
                        error_message = NULL,
                        retry_count = 0
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                session.execute(update_query, {
                    'job_id': self.job_id,
                    'tenant_id': self.tenant_id,
                    'now': now,
                    'next_run': next_run
                })
                session.commit()

            logger.info(f"✅ Job '{self.job_name}' marked as completed - next run at {next_run}")

        except Exception as e:
            logger.error(f"Error marking job as completed: {e}")

    async def _mark_job_failed(self, error_message: str):
        """Mark job as failed"""
        try:
            database = get_database()
            with database.get_write_session_context() as session:
                from app.core.utils import DateTimeHelper
                now = DateTimeHelper.now_default()

                update_query = text("""
                    UPDATE etl_jobs
                    SET status = jsonb_set(status, ARRAY['overall'], to_jsonb('FAILED'::text)),
                        last_updated_at = :now,
                        error_message = :error_message
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                session.execute(update_query, {
                    'job_id': self.job_id,
                    'tenant_id': self.tenant_id,
                    'now': now,
                    'error_message': error_message[:500]  # Limit error message length
                })
                session.commit()

            logger.error(f"❌ Job '{self.job_name}' marked as FAILED: {error_message}")
        except Exception as db_error:
            logger.error(f"Error updating job status to FAILED: {db_error}")

    async def _queue_jira_extraction(self, integration_id: int) -> bool:
        """
        Queue Jira extraction job for background processing.

        Args:
            integration_id: Integration ID for the Jira extraction

        Returns:
            bool: True if queued successfully
        """
        try:
            from app.etl.workers.queue_manager import QueueManager

            # Note: Job status is already set to 'RUNNING' by _trigger_job method
            # No need to update it again here to avoid database locks and constraint violations
            logger.info(f"✅ Job '{self.job_name}' status already set to RUNNING - queuing extraction")

            # Queue the first extraction step: projects and issue types
            queue_manager = QueueManager()

            message = {
                'tenant_id': self.tenant_id,
                'integration_id': integration_id,
                'job_id': self.job_id,
                'type': 'jira_projects_and_issue_types',  # 🔑 Use 'type' field for extraction worker router
                'provider': 'jira'  # 🔑 Add provider field for routing
            }

            # Get tenant tier and route to tier-based extraction queue
            tier = queue_manager._get_tenant_tier(self.tenant_id)
            tier_queue = queue_manager.get_tier_queue_name(tier, 'extraction')

            success = queue_manager._publish_message(tier_queue, message)

            if success:
                logger.info(f"✅ Jira extraction job queued successfully to {tier_queue}")
                return True
            else:
                logger.error(f"❌ Failed to publish extraction message to {tier_queue}")
                return False

        except Exception as e:
            logger.error(f"Error queuing Jira extraction: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False


class JobTimerManager:
    """
    Manager for individual job timers.

    Similar to WebSocket manager - creates and manages individual timer "connections" for each job.
    """

    def __init__(self):
        self.job_timers: Dict[int, IndividualJobTimer] = {}  # job_id -> timer

    async def start_all_job_timers(self):
        """Start individual timers for all active jobs (like WebSocket handshake for all jobs)"""
        try:
            logger.info("🔍 Getting database connection for job scheduler...")
            database = get_database()

            # First, fix any jobs with next_run in the past
            logger.info("🔧 Checking for jobs with next_run in the past...")
            await self._fix_past_next_run_times(database)

            logger.info("🔍 Opening database session...")
            with database.get_read_session_context() as session:

                logger.info("🔍 Querying for active jobs...")
                # Get all active jobs
                query = text("""
                    SELECT id, job_name, tenant_id
                    FROM etl_jobs
                    WHERE active = TRUE
                    ORDER BY id
                """)

                results = session.execute(query).fetchall()

                print(f"🚀 JOB SCHEDULER: Found {len(results)} active jobs - starting individual timers")  # Force print
                logger.info(f"🚀 Found {len(results)} active jobs - starting individual timers")

                for row in results:
                    job_id, job_name, tenant_id = row
                    print(f"🔍 JOB SCHEDULER: Starting timer for job '{job_name}' (ID: {job_id}, tenant: {tenant_id})")  # Force print
                    logger.info(f"🔍 Starting timer for job '{job_name}' (ID: {job_id}, tenant: {tenant_id})")
                    await self._start_job_timer(job_id, job_name, tenant_id)

                print(f"✅ JOB SCHEDULER: All {len(results)} job timers started successfully")  # Force print
                logger.info(f"✅ All {len(results)} job timers started successfully")

        except Exception as e:
            logger.error(f"❌ Error starting job timers: {e}")
            logger.error(f"❌ Job timer startup error details: {type(e).__name__}: {str(e)}")
            raise

    async def _fix_past_next_run_times(self, database):
        """
        Fix jobs with next_run in the past by recalculating based on schedule_interval_minutes.
        Uses timezone-aware comparison.
        """
        try:
            from app.core.utils import DateTimeHelper
            from datetime import timedelta

            now = DateTimeHelper.now_default()

            with database.get_write_session_context() as session:
                # Find jobs with next_run in the past or NULL
                query = text("""
                    SELECT id, job_name, next_run, schedule_interval_minutes, status->>'overall' as overall_status
                    FROM etl_jobs
                    WHERE active = TRUE
                      AND (next_run IS NULL OR next_run < :now)
                      AND status->>'overall' NOT IN ('RUNNING')
                    ORDER BY id
                """)

                jobs_to_fix = session.execute(query, {'now': now}).fetchall()

                if not jobs_to_fix:
                    logger.info("✅ All active jobs have valid next_run times")
                    return

                logger.info(f"🔧 Found {len(jobs_to_fix)} jobs with next_run in the past or NULL - fixing...")

                for job_id, job_name, old_next_run, schedule_interval_minutes, status in jobs_to_fix:
                    # Calculate new next_run based on current time + schedule_interval
                    new_next_run = now + timedelta(minutes=schedule_interval_minutes)

                    update_query = text("""
                        UPDATE etl_jobs
                        SET next_run = :next_run,
                            last_updated_at = :now
                        WHERE id = :job_id
                    """)

                    session.execute(update_query, {
                        'job_id': job_id,
                        'next_run': new_next_run,
                        'now': now
                    })

                    old_next_run_str = str(old_next_run)[:19] if old_next_run else 'NULL'
                    logger.info(f"  ✅ Fixed job '{job_name}' (ID: {job_id}): "
                              f"old_next_run={old_next_run_str}, "
                              f"new_next_run={str(new_next_run)[:19]}, "
                              f"interval={schedule_interval_minutes}min")

                session.commit()
                logger.info(f"✅ Fixed {len(jobs_to_fix)} jobs with past next_run times")

        except Exception as e:
            logger.error(f"❌ Error fixing past next_run times: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            # Don't raise - continue with scheduler startup

    async def _start_job_timer(self, job_id: int, job_name: str, tenant_id: int):
        """Start individual timer for a specific job"""
        try:
            if job_id in self.job_timers:
                logger.warning(f"Timer for job '{job_name}' (ID: {job_id}) already exists")
                return

            logger.info(f"🔧 Creating timer instance for job '{job_name}' (ID: {job_id})")
            # Create individual timer for this job
            timer = IndividualJobTimer(job_id, job_name, tenant_id)
            self.job_timers[job_id] = timer

            logger.info(f"🚀 Starting timer for job '{job_name}' (ID: {job_id})")
            # Start the timer
            await timer.start()

            logger.info(f"✅ Timer started successfully for job '{job_name}' (ID: {job_id})")

        except Exception as e:
            logger.error(f"❌ Error starting timer for job '{job_name}' (ID: {job_id}): {e}")
            logger.error(f"❌ Timer error details: {type(e).__name__}: {str(e)}")
            # Don't raise - continue with other jobs

    async def stop_all_job_timers(self):
        """Stop all individual job timers"""
        logger.info(f"⏹️ Stopping {len(self.job_timers)} job timers")

        for timer in self.job_timers.values():
            try:
                await timer.stop()
            except Exception as e:
                logger.error(f"Error stopping timer for job '{timer.job_name}': {e}")

        self.job_timers.clear()


# Global manager instance
_manager_instance: Optional[JobTimerManager] = None

def get_job_timer_manager() -> JobTimerManager:
    """Get the global job timer manager instance"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = JobTimerManager()
    return _manager_instance

async def start_job_scheduler():
    """Start individual timers for all jobs"""
    try:
        print("🚀 JOB SCHEDULER: Starting job scheduler...")  # Force print
        logger.info("🚀 Starting job scheduler...")

        # Check database connection first with retry logic
        print("🔍 JOB SCHEDULER: Checking database connection...")  # Force print
        logger.info("🔍 Checking database connection...")
        database = get_database()

        # Retry database connection check
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if database.is_connection_alive():
                    logger.info("✅ Database connection verified")
                    break
                else:
                    logger.warning(f"⚠️ Database connection attempt {attempt + 1}/{max_retries} failed")
                    if attempt < max_retries - 1:
                        import asyncio
                        await asyncio.sleep(2)  # Wait 2 seconds before retry
            except Exception as db_check_error:
                logger.warning(f"⚠️ Database check attempt {attempt + 1}/{max_retries} error: {db_check_error}")
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2)  # Wait 2 seconds before retry
        else:
            logger.error("❌ Database connection not available after retries - cannot start job scheduler")
            raise Exception("Database connection not available after retries")

        # Check if etl_jobs table exists
        logger.info("🔍 Checking if etl_jobs table exists...")
        try:
            if not database.check_table_exists("etl_jobs"):
                logger.error("❌ etl_jobs table does not exist - cannot start job scheduler")
                raise Exception("etl_jobs table does not exist")
            logger.info("✅ etl_jobs table verified")
        except Exception as table_check_error:
            logger.error(f"❌ Error checking etl_jobs table: {table_check_error}")
            raise

        print("🔧 JOB SCHEDULER: Getting job timer manager...")  # Force print
        logger.info("🔧 Getting job timer manager...")
        manager = get_job_timer_manager()

        print("🚀 JOB SCHEDULER: Starting all job timers...")  # Force print
        logger.info("🚀 Starting all job timers...")
        await manager.start_all_job_timers()
        print("✅ JOB SCHEDULER: Job scheduler started successfully")  # Force print
        logger.info("✅ Job scheduler started successfully")
    except Exception as e:
        logger.error(f"❌ Failed to start job scheduler: {e}")
        logger.error(f"❌ Job scheduler error details: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"❌ Job scheduler traceback: {traceback.format_exc()}")
        raise

async def stop_job_scheduler():
    """Stop all individual job timers"""
    manager = get_job_timer_manager()
    await manager.stop_all_job_timers()
