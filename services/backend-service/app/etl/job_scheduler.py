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
        logger.info(f"🚀 Starting individual timer for job '{self.job_name}' (ID: {self.job_id})")

        # Calculate initial delay until next run
        next_run_delay = await self._calculate_initial_delay()
        if next_run_delay is not None:
            logger.info(f"   - Next run in {next_run_delay:.1f} minutes")
            # Start the individual timer for this job
            self.timer_task = asyncio.create_task(self._job_timer_loop(next_run_delay))
        else:
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
            with database.get_session_context() as session:

                # Get this specific job's details including next_run
                query = text("""
                    SELECT
                        status, active, next_run, schedule_interval_minutes
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
                logger.info(f"⏰ Time to run job '{self.job_name}' (ID: {self.job_id})")
                await self._trigger_job()

                # Calculate next run interval
                next_interval = await self._get_next_interval()
                if next_interval and next_interval > 0:
                    logger.info(f"⏱️ Job '{self.job_name}' scheduled to run again in {next_interval:.1f} minutes")
                    await asyncio.sleep(next_interval * 60)  # Convert to seconds
                else:
                    logger.info(f"⏹️ Job '{self.job_name}' not scheduled for next run")
                    break

        except asyncio.CancelledError:
            logger.info(f"⏹️ Timer cancelled for job '{self.job_name}'")
        except Exception as e:
            logger.error(f"Error in timer loop for job '{self.job_name}': {e}")

    async def _get_next_interval(self) -> Optional[float]:
        """Get the interval (in minutes) until this job should run next based on next_run column"""
        try:
            database = get_database()
            with database.get_session_context() as session:

                # Get updated job details including next_run
                query = text("""
                    SELECT status, active, next_run
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

                return max(0, delay_minutes)  # Don't return negative delays

        except Exception as e:
            logger.error(f"Error getting next interval for job '{self.job_name}': {e}")
            return None
            

    async def _trigger_job(self):
        """Trigger this job's execution"""
        try:
            database = get_database()
            with database.get_session_context() as session:
                # Set job to RUNNING status with proper timezone handling
                from app.core.utils import DateTimeHelper
                now = DateTimeHelper.now_default()

                update_query = text("""
                    UPDATE etl_jobs
                    SET status = 'RUNNING',
                        last_run_started_at = :now,
                        last_updated_at = :now
                    WHERE id = :job_id AND tenant_id = :tenant_id
                """)

                session.execute(update_query, {
                    'job_id': self.job_id,
                    'tenant_id': self.tenant_id,
                    'now': now
                })
                session.commit()

            logger.info(f"🚀 Triggered job '{self.job_name}' (ID: {self.job_id}) for tenant {self.tenant_id}")

            # TODO: Implement actual job execution logic here
            # For now, just simulate job completion after a short delay
            asyncio.create_task(self._simulate_job_execution())

        except Exception as e:
            logger.error(f"Error triggering job '{self.job_name}': {e}")

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
            with database.get_session_context() as session:
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

            logger.info("🔍 Opening database session...")
            with database.get_session_context() as session:

                logger.info("🔍 Querying for active jobs...")
                # Get all active jobs
                query = text("""
                    SELECT id, job_name, tenant_id
                    FROM etl_jobs
                    WHERE active = TRUE
                    ORDER BY id
                """)

                results = session.execute(query).fetchall()

                logger.info(f"🚀 Found {len(results)} active jobs - starting individual timers")

                for row in results:
                    job_id, job_name, tenant_id = row
                    logger.info(f"🔍 Starting timer for job '{job_name}' (ID: {job_id}, tenant: {tenant_id})")
                    await self._start_job_timer(job_id, job_name, tenant_id)

                logger.info(f"✅ All {len(results)} job timers started successfully")

        except Exception as e:
            logger.error(f"❌ Error starting job timers: {e}")
            logger.error(f"❌ Job timer startup error details: {type(e).__name__}: {str(e)}")
            raise

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
        logger.info("🚀 Starting job scheduler...")

        # Check database connection first with retry logic
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

        logger.info("🔧 Getting job timer manager...")
        manager = get_job_timer_manager()

        logger.info("🚀 Starting all job timers...")
        await manager.start_all_job_timers()
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
