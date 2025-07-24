"""
Orchestrator Scheduler Helper

Manages dynamic scheduling of the orchestrator for fast retry functionality.
Allows temporarily advancing the next orchestrator run for failed jobs while
maintaining the normal interval for successful runs.
"""

from datetime import datetime, timedelta
from typing import Optional
from app.core.logging_config import get_logger
from app.core.settings_manager import (
    get_orchestrator_retry_interval, 
    is_orchestrator_retry_enabled,
    get_orchestrator_max_retry_attempts,
    get_orchestrator_interval
)

logger = get_logger(__name__)


class OrchestratorScheduler:
    """Manages dynamic orchestrator scheduling for fast retry functionality."""
    
    def __init__(self):
        self.scheduler = None
        self.retry_attempts = {}  # Track retry attempts per job
        
    def set_scheduler(self, scheduler):
        """Set the APScheduler instance."""
        self.scheduler = scheduler
        
    def schedule_fast_retry(self, job_name: str) -> bool:
        """
        Schedule the orchestrator to run sooner for a failed job.

        Args:
            job_name: Name of the job that failed

        Returns:
            bool: True if fast retry was scheduled, False otherwise
        """
        if not self.scheduler:
            logger.warning("Scheduler not available for fast retry")
            return False

        # Get current settings with debugging
        retry_enabled = is_orchestrator_retry_enabled()
        retry_interval = get_orchestrator_retry_interval()
        max_attempts = get_orchestrator_max_retry_attempts()

        logger.info(f"Fast retry settings: enabled={retry_enabled}, interval={retry_interval}min, max_attempts={max_attempts}")

        if not retry_enabled:
            logger.info("Fast retry is disabled in settings")
            return False

        # Check retry attempts
        current_attempts = self.retry_attempts.get(job_name, 0)

        if current_attempts >= max_attempts:
            logger.info(f"Job {job_name} has reached max retry attempts ({max_attempts}), using normal interval")
            self.retry_attempts[job_name] = 0  # Reset for next cycle
            return False

        # Increment retry attempts
        self.retry_attempts[job_name] = current_attempts + 1

        try:
            # Get current job info for debugging
            current_job = self.scheduler.get_job('etl_orchestrator')
            if current_job:
                logger.info(f"BEFORE: Current orchestrator next run: {current_job.next_run_time}")
                logger.info(f"BEFORE: Current orchestrator trigger: {current_job.trigger}")
            else:
                logger.warning("BEFORE: No orchestrator job found!")

            # Calculate next run time using UTC to match scheduler timezone
            from datetime import timezone
            now = datetime.now(timezone.utc)
            next_run = now + timedelta(minutes=retry_interval)
            logger.info(f"SCHEDULING: Fast retry for {job_name}")
            logger.info(f"SCHEDULING: Current time (UTC): {now}")
            logger.info(f"SCHEDULING: Retry interval: {retry_interval} minutes")
            logger.info(f"SCHEDULING: Target next run (UTC): {next_run}")

            # Modify the orchestrator job to run sooner
            self.scheduler.modify_job(
                'etl_orchestrator',
                next_run_time=next_run
            )

            # Verify the change
            updated_job = self.scheduler.get_job('etl_orchestrator')
            if updated_job:
                logger.info(f"AFTER: Updated orchestrator next run: {updated_job.next_run_time}")
                logger.info(f"AFTER: Updated orchestrator trigger: {updated_job.trigger}")

                # Calculate actual minutes until next run
                if updated_job.next_run_time:
                    from datetime import timezone
                    current_time = datetime.now(timezone.utc)
                    # Handle timezone-aware vs naive datetime comparison
                    if updated_job.next_run_time.tzinfo is None:
                        current_time = datetime.now()
                    time_diff = updated_job.next_run_time - current_time
                    minutes_until = time_diff.total_seconds() / 60
                    logger.info(f"AFTER: Minutes until next run: {minutes_until:.1f}")
            else:
                logger.error("AFTER: Failed to get updated job!")

            logger.info(f"Fast retry scheduled for {job_name} (attempt {current_attempts + 1}/{max_attempts}) - next run in {retry_interval} minutes")
            return True

        except Exception as e:
            logger.error(f"Failed to schedule fast retry for {job_name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def reset_retry_attempts(self, job_name: str):
        """Reset retry attempts for a job (called on successful completion)."""
        if job_name in self.retry_attempts:
            del self.retry_attempts[job_name]
            logger.info(f"Reset retry attempts for {job_name}")

    def force_reset_retry_attempts(self, job_name: str):
        """Force reset retry attempts for a job (called when manually triggered)."""
        if job_name in self.retry_attempts:
            old_attempts = self.retry_attempts[job_name]
            del self.retry_attempts[job_name]
            logger.info(f"Force reset retry attempts for {job_name} (was at {old_attempts} attempts)")
        else:
            logger.info(f"No retry attempts to reset for {job_name}")
    
    def restore_normal_schedule(self):
        """
        Restore the orchestrator to its normal interval.
        This is called after a successful run to ensure the next run follows the normal schedule.
        Uses current database settings to ensure any configuration changes are applied.
        """
        if not self.scheduler:
            return

        try:
            # Get current settings from database (in case they were updated during fast retry)
            normal_interval = get_orchestrator_interval()
            from datetime import timezone
            next_run = datetime.now(timezone.utc) + timedelta(minutes=normal_interval)

            logger.info(f"RESTORING: Normal schedule with {normal_interval} minute interval")
            logger.info(f"RESTORING: Next run scheduled for: {next_run}")
            logger.info(f"RESTORING: Using current database settings (may have been updated during fast retry)")

            # Modify the orchestrator job back to normal interval
            self.scheduler.modify_job(
                'etl_orchestrator',
                next_run_time=next_run
            )

            logger.info(f"Orchestrator schedule restored to normal interval ({normal_interval} minutes)")

        except Exception as e:
            logger.error(f"Failed to restore normal orchestrator schedule: {e}")
            import traceback
            traceback.print_exc()
    
    def get_retry_status(self, job_name: str) -> dict:
        """Get current retry status for a job."""
        current_attempts = self.retry_attempts.get(job_name, 0)
        max_attempts = get_orchestrator_max_retry_attempts()
        
        return {
            'job_name': job_name,
            'current_attempts': current_attempts,
            'max_attempts': max_attempts,
            'retry_enabled': is_orchestrator_retry_enabled(),
            'retry_interval_minutes': get_orchestrator_retry_interval()
        }
    
    def get_all_retry_status(self) -> dict:
        """Get retry status for all jobs."""
        return {
            'retry_enabled': is_orchestrator_retry_enabled(),
            'retry_interval_minutes': get_orchestrator_retry_interval(),
            'max_attempts': get_orchestrator_max_retry_attempts(),
            'jobs': {
                job_name: {
                    'current_attempts': attempts,
                    'max_attempts': get_orchestrator_max_retry_attempts()
                }
                for job_name, attempts in self.retry_attempts.items()
            }
        }

    def is_fast_retry_active(self) -> bool:
        """
        Check if fast retry is currently active by comparing the orchestrator's
        next run time with the normal interval.

        Returns:
            bool: True if fast retry is active (next run is sooner than normal interval)
        """
        if not self.scheduler:
            return False

        try:
            # Get the orchestrator job
            orchestrator_job = self.scheduler.get_job('etl_orchestrator')
            if not orchestrator_job or not orchestrator_job.next_run_time:
                return False

            # Calculate when the next run would be with normal interval
            from datetime import timezone
            normal_interval = get_orchestrator_interval()
            normal_next_run = datetime.now(timezone.utc) + timedelta(minutes=normal_interval)

            # If the scheduled next run is significantly sooner than normal interval,
            # then fast retry is likely active (allow 2 minute buffer for timing differences)
            time_until_next_run = (orchestrator_job.next_run_time - datetime.now(timezone.utc)).total_seconds() / 60

            is_fast_retry = time_until_next_run < (normal_interval - 2)

            logger.debug(f"Fast retry check: next_run_in={time_until_next_run:.1f}min, normal_interval={normal_interval}min, is_fast_retry={is_fast_retry}")

            return is_fast_retry

        except Exception as e:
            logger.warning(f"Error checking fast retry status: {e}")
            return False

    def get_current_countdown_minutes(self) -> Optional[float]:
        """
        Get the current countdown time in minutes until the next orchestrator run.

        Returns:
            float: Minutes until next run, or None if no job scheduled
        """
        if not self.scheduler:
            return None

        try:
            orchestrator_job = self.scheduler.get_job('etl_orchestrator')
            if not orchestrator_job or not orchestrator_job.next_run_time:
                return None

            from datetime import timezone
            time_until_next_run = (orchestrator_job.next_run_time - datetime.now(timezone.utc)).total_seconds() / 60

            return max(0, time_until_next_run)  # Don't return negative values

        except Exception as e:
            logger.warning(f"Error getting current countdown: {e}")
            return None

    def _is_github_job_pending(self) -> bool:
        """
        Check if the GitHub job is currently in PENDING status.

        Returns:
            bool: True if GitHub job status is 'PENDING', False otherwise
        """
        try:
            from app.core.database import get_database
            from app.models.unified_models import JobSchedule

            database = get_database()
            with database.get_session() as session:
                github_job = session.query(JobSchedule).filter(
                    JobSchedule.job_name == 'github_sync',
                    JobSchedule.active == True
                ).first()

                if github_job:
                    is_pending = github_job.status == 'PENDING'
                    logger.debug(f"GitHub job status check: {github_job.status}, is_pending={is_pending}")
                    return is_pending
                else:
                    logger.warning("GitHub job not found in database")
                    return False

        except Exception as e:
            logger.warning(f"Error checking GitHub job status: {e}")
            return False

    def should_apply_new_interval(self, new_interval_minutes: int, is_retry_setting: bool = False) -> bool:
        """
        Determine if a new interval should be applied immediately based on current countdown.

        Args:
            new_interval_minutes: The new interval being set
            is_retry_setting: True if this is a retry interval change, False for main interval

        Returns:
            bool: True if new interval should be applied immediately
        """
        current_countdown = self.get_current_countdown_minutes()
        if current_countdown is None:
            return True  # No current schedule, apply immediately

        fast_retry_active = self.is_fast_retry_active()

        # If fast retry is active and this is a retry setting change
        if fast_retry_active and is_retry_setting:
            # Check GitHub job status - only consider fast recovery timing if GitHub is PENDING
            github_job_pending = self._is_github_job_pending()

            if github_job_pending:
                # GitHub is PENDING: Include fast recovery in shortest time calculation
                should_apply = new_interval_minutes < current_countdown
                logger.info(f"Fast retry active, retry setting change, GitHub PENDING: current_countdown={current_countdown:.1f}min, new_retry_interval={new_interval_minutes}min, should_apply={should_apply}")
                return should_apply
            else:
                # GitHub is not PENDING: Exclude fast recovery from timing decisions
                logger.info(f"Fast retry active, retry setting change, GitHub NOT PENDING: excluding fast recovery from timing decisions, preserving current schedule")
                return False

        # If no fast retry is active and this is a main interval change
        if not fast_retry_active and not is_retry_setting:
            # Apply new main interval if it's smaller than current countdown
            should_apply = new_interval_minutes < current_countdown
            logger.info(f"Normal schedule, main interval change: current_countdown={current_countdown:.1f}min, new_main_interval={new_interval_minutes}min, should_apply={should_apply}")
            return should_apply

        # For all other cases, preserve current schedule
        logger.info(f"Preserving current schedule: fast_retry_active={fast_retry_active}, is_retry_setting={is_retry_setting}, current_countdown={current_countdown:.1f}min")
        return False

    def apply_new_retry_interval_if_smaller(self, new_retry_interval: int) -> bool:
        """
        Apply a new retry interval immediately if it's smaller than the current countdown.
        Only applies when fast retry is currently active and GitHub job is PENDING.

        Args:
            new_retry_interval: New retry interval in minutes

        Returns:
            bool: True if the new interval was applied immediately, False if preserved
        """
        if not self.scheduler:
            logger.warning("Scheduler not available for retry interval update")
            return False

        if not self.is_fast_retry_active():
            logger.info("Fast retry not active - new retry interval will apply to future retry attempts")
            return False

        should_apply = self.should_apply_new_interval(new_retry_interval, is_retry_setting=True)

        if not should_apply:
            current_countdown = self.get_current_countdown_minutes()
            github_job_pending = self._is_github_job_pending()

            if not github_job_pending:
                logger.info(f"Preserving current fast retry schedule - GitHub job is not PENDING, excluding fast recovery from timing decisions")
            else:
                logger.info(f"Preserving current fast retry schedule - new retry interval ({new_retry_interval} minutes) is larger than current countdown ({current_countdown:.1f} minutes)")
            return False

        try:
            # Apply the new retry interval immediately
            from datetime import timezone
            now = datetime.now(timezone.utc)
            next_run = now + timedelta(minutes=new_retry_interval)

            logger.info(f"APPLYING: New retry interval ({new_retry_interval} minutes) is smaller than current countdown")
            logger.info(f"APPLYING: Current time (UTC): {now}")
            logger.info(f"APPLYING: New next run (UTC): {next_run}")

            self.scheduler.modify_job(
                'etl_orchestrator',
                next_run_time=next_run
            )

            logger.info(f"Fast retry schedule updated to new interval ({new_retry_interval} minutes)")
            return True

        except Exception as e:
            logger.error(f"Failed to apply new retry interval: {e}")
            import traceback
            traceback.print_exc()
            return False


# Global instance
orchestrator_scheduler = OrchestratorScheduler()


def get_orchestrator_scheduler() -> OrchestratorScheduler:
    """Get the global orchestrator scheduler instance."""
    return orchestrator_scheduler
