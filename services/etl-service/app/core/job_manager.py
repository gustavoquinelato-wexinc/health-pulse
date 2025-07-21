"""
Job Manager for tracking and controlling running jobs.
Provides job cancellation and status tracking capabilities.
"""

import asyncio
from typing import Dict, Optional, Set
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class JobManager:
    """
    Manages running jobs and provides cancellation capabilities.
    """
    
    def __init__(self):
        # Track running jobs by job name
        self.running_jobs: Dict[str, asyncio.Task] = {}
        # Track cancellation requests
        self.cancellation_requests: Set[str] = set()
        
    def register_job(self, job_name: str, task: asyncio.Task):
        """Register a running job task."""
        self.running_jobs[job_name] = task
        logger.info(f"Job registered: {job_name}")
        
        # Add callback to clean up when job completes
        def cleanup_job(task):
            if job_name in self.running_jobs:
                del self.running_jobs[job_name]
            if job_name in self.cancellation_requests:
                self.cancellation_requests.remove(job_name)
            logger.info(f"Job cleaned up: {job_name}")
        
        task.add_done_callback(cleanup_job)
    
    def is_job_running(self, job_name: str) -> bool:
        """Check if a job is currently running."""
        return job_name in self.running_jobs and not self.running_jobs[job_name].done()
    
    def request_cancellation(self, job_name: str) -> bool:
        """Request cancellation of a running job."""
        if not self.is_job_running(job_name):
            return False
        
        self.cancellation_requests.add(job_name)
        logger.info(f"Cancellation requested for job: {job_name}")
        return True
    
    def is_cancellation_requested(self, job_name: str) -> bool:
        """Check if cancellation has been requested for a job."""
        return job_name in self.cancellation_requests
    
    def force_cancel_job(self, job_name: str) -> bool:
        """Force cancel a running job with aggressive termination."""
        if not self.is_job_running(job_name):
            logger.warning(f"Cannot force cancel {job_name}: job not running")
            return False

        task = self.running_jobs[job_name]
        logger.warning(f"Force cancelling job {job_name} (task: {task})")

        # Try multiple cancellation approaches
        try:
            # 1. Standard cancellation
            task.cancel()

            # 2. Add to cancellation requests as well
            self.cancellation_requests.add(job_name)

            # 3. Remove from running jobs immediately
            if job_name in self.running_jobs:
                del self.running_jobs[job_name]

            logger.warning(f"Job {job_name} force cancelled successfully")
            return True

        except Exception as e:
            logger.error(f"Error during force cancellation of {job_name}: {e}")
            return False
    
    def get_running_jobs(self) -> Dict[str, str]:
        """Get list of currently running jobs."""
        running = {}
        for job_name, task in self.running_jobs.items():
            if not task.done():
                running[job_name] = "RUNNING"
            elif task.cancelled():
                running[job_name] = "CANCELLED"
            elif task.exception():
                running[job_name] = "ERROR"
            else:
                running[job_name] = "COMPLETED"
        return running
    
    def check_cancellation(self, job_name: str):
        """
        Check if cancellation was requested and raise CancellationError if so.
        Jobs should call this periodically during execution.
        """
        if self.is_cancellation_requested(job_name):
            logger.info(f"Job {job_name} detected cancellation request")
            raise asyncio.CancelledError(f"Job {job_name} was cancelled by user request")


# Global job manager instance
job_manager = JobManager()


def get_job_manager() -> JobManager:
    """Get the global job manager instance."""
    return job_manager


class CancellableJob:
    """
    Context manager for jobs that support cancellation.
    """
    
    def __init__(self, job_name: str):
        self.job_name = job_name
        self.job_manager = get_job_manager()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cleanup is handled by the task callback
        pass
    
    def check_cancellation(self):
        """Check if cancellation was requested."""
        self.job_manager.check_cancellation(self.job_name)
    
    async def async_check_cancellation(self):
        """Async version of cancellation check."""
        self.check_cancellation()
        # Allow other tasks to run
        await asyncio.sleep(0)


def register_job_task(job_name: str, task: asyncio.Task):
    """Register a job task for tracking and cancellation."""
    job_manager.register_job(job_name, task)


def is_job_running(job_name: str) -> bool:
    """Check if a job is currently running."""
    return job_manager.is_job_running(job_name)


def request_job_cancellation(job_name: str) -> bool:
    """Request cancellation of a running job."""
    return job_manager.request_cancellation(job_name)


def force_cancel_job(job_name: str) -> bool:
    """Force cancel a running job."""
    return job_manager.force_cancel_job(job_name)


def get_running_jobs() -> Dict[str, str]:
    """Get list of currently running jobs."""
    return job_manager.get_running_jobs()
