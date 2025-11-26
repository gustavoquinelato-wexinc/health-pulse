"""
Job Reset Scheduler

Handles automatic reset of FINISHED ETL jobs after checking that all steps are complete
and all queues are empty. Uses threading.Timer for delayed execution with exponential backoff.

Flow:
1. Job finishes → set reset_deadline = now + 30s, schedule reset check task
2. Task runs after 30s → check step statuses + queues
3. If work remains → extend deadline (60s, 180s, 300s) and reschedule
4. If all complete → reset job to READY

This ensures the countdown is system-level (not per-user session) and works even
when no users are logged in.

Uses threading.Timer instead of asyncio.create_task to avoid event loop issues
when called from worker threads.
"""

import asyncio
import json
import logging
import threading
from datetime import timedelta
from typing import Dict, Any, Optional
from sqlalchemy import text

from app.core.database import get_database
from app.core.utils import DateTimeHelper
from app.etl.workers.queue_manager import QueueManager

logger = logging.getLogger(__name__)

# Track active reset check timers by job_id to prevent duplicate timers
_active_reset_timers: Dict[int, threading.Timer] = {}


def calculate_next_interval(reset_attempt: int) -> int:
    """
    Calculate next delay interval based on attempt count.
    
    Args:
        reset_attempt: Current reset attempt number
        
    Returns:
        int: Delay in seconds
        
    Intervals:
        reset_attempt = 0 → 30s (initial, set when job finishes)
        reset_attempt = 1 → 60s (first reschedule)
        reset_attempt = 2 → 180s (second reschedule)
        reset_attempt = 3+ → 300s (all subsequent reschedules)
    """
    if reset_attempt == 0:
        return 30   # Initial countdown
    elif reset_attempt == 1:
        return 60   # First retry
    elif reset_attempt == 2:
        return 180  # Second retry (3 minutes)
    else:
        return 300  # All subsequent retries (5 minutes)


async def reset_check_task(job_id: int, tenant_id: int):
    """
    Delayed task that checks if job should be reset or deadline extended.
    
    This task:
    1. Checks if job is still FINISHED (might have been manually restarted)
    2. Checks each step's status and corresponding queue for remaining work
    3. If work remains → extends deadline and reschedules itself
    4. If all complete → resets job to READY
    
    Args:
        job_id: ETL job ID
        tenant_id: Tenant ID
    """
    try:
        database = get_database()
        
        # Get current job status from database
        with database.get_read_session_context() as db:
            query = text("""
                SELECT status
                FROM etl_jobs
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            result = db.execute(query, {'job_id': job_id, 'tenant_id': tenant_id}).fetchone()
            
            if not result:
                logger.error(f"❌ Job {job_id} not found for reset check")
                return
            
            status = result[0]
            if isinstance(status, str):
                status = json.loads(status)
        
        # Check if job is still FINISHED (might have been manually restarted)
        if status.get('overall') != 'FINISHED':
            logger.info(f"🔄 Job {job_id} is no longer FINISHED (status={status.get('overall')}), skipping reset check")
            return
        
        # Get token for queue checking
        token = status.get('token')
        if not token:
            logger.warning(f"⚠️ Job {job_id} has no token - forcing reset")
            await reset_job_to_ready(job_id, tenant_id, status)
            return
        
        # Get tenant tier to build queue names
        queue_manager = QueueManager()
        tier = queue_manager._get_tenant_tier(tenant_id)
        
        # Build tier-based queue names
        extraction_queue_name = queue_manager.get_tier_queue_name(tier, 'extraction')
        transform_queue_name = queue_manager.get_tier_queue_name(tier, 'transform')
        embedding_queue_name = queue_manager.get_tier_queue_name(tier, 'embedding')
        
        logger.info(f"🔍 Checking job {job_id} reset eligibility (token={token}, tier={tier})")
        
        # Check each step's status AND its corresponding queue
        # IMPORTANT: Always check queues even if status is 'finished' because:
        # - Multiple workers process messages concurrently
        # - One worker finishing doesn't mean all messages are processed
        # - Status updates are per-message, not per-queue
        all_steps_finished = True
        steps = status.get('steps', {})

        for step_name, step_data in steps.items():
            # Check EXTRACTION status + queue
            extraction_status = step_data.get('extraction', 'idle')

            # If status is 'running', worker is actively processing - extend deadline
            if extraction_status == 'running':
                all_steps_finished = False
                logger.info(f"   ⏳ Step '{step_name}' extraction is still running (worker actively processing)")
                break

            # If status is 'finished', check if there are still messages in queue
            if extraction_status == 'finished':
                extraction_messages = queue_manager.check_messages_with_token(extraction_queue_name, token)
                if extraction_messages:
                    all_steps_finished = False
                    logger.info(f"   ⏳ Step '{step_name}' extraction has messages in {extraction_queue_name} (status={extraction_status})")
                    break

            # Check TRANSFORM status + queue
            transform_status = step_data.get('transform', 'idle')

            # If status is 'running', worker is actively processing - extend deadline
            if transform_status == 'running':
                all_steps_finished = False
                logger.info(f"   ⏳ Step '{step_name}' transform is still running (worker actively processing)")
                break

            # If status is 'finished', check if there are still messages in queue
            if transform_status == 'finished':
                transform_messages = queue_manager.check_messages_with_token(transform_queue_name, token)
                if transform_messages:
                    all_steps_finished = False
                    logger.info(f"   ⏳ Step '{step_name}' transform has messages in {transform_queue_name} (status={transform_status})")
                    break

            # Check EMBEDDING status + queue
            embedding_status = step_data.get('embedding', 'idle')

            # If status is 'running', worker is actively processing - extend deadline
            if embedding_status == 'running':
                all_steps_finished = False
                logger.info(f"   ⏳ Step '{step_name}' embedding is still running (worker actively processing)")
                break

            # If status is 'finished', check if there are still messages in queue
            if embedding_status == 'finished':
                embedding_messages = queue_manager.check_messages_with_token(embedding_queue_name, token)
                if embedding_messages:
                    all_steps_finished = False
                    logger.info(f"   ⏳ Step '{step_name}' embedding has messages in {embedding_queue_name} (status={embedding_status})")
                    break
        
        if not all_steps_finished:
            # Steps still running with messages in queues - extend deadline and reschedule
            await extend_deadline_and_reschedule(job_id, tenant_id, status)
        else:
            # All steps finished and all queues are empty - safe to reset
            logger.info(f"✅ Job {job_id} is ready to reset - all steps finished and queues empty")
            await reset_job_to_ready(job_id, tenant_id, status)
            
    except Exception as e:
        logger.error(f"❌ Error in reset check task for job {job_id}: {e}", exc_info=True)


async def extend_deadline_and_reschedule(job_id: int, tenant_id: int, status: Dict[str, Any]):
    """
    Extend reset deadline and schedule another reset check task.
    
    Args:
        job_id: ETL job ID
        tenant_id: Tenant ID
        status: Current job status JSON
    """
    try:
        database = get_database()
        
        # Get current reset attempt count
        reset_attempt = status.get('reset_attempt', 0)

        # Calculate next interval
        next_interval = calculate_next_interval(reset_attempt + 1)

        # Calculate new deadline with timezone info for proper frontend calculation
        now_with_tz = DateTimeHelper.now_default_with_tz()
        new_deadline_with_tz = now_with_tz + timedelta(seconds=next_interval)

        # Get timezone-naive now for database update
        now = DateTimeHelper.now_default()  # ✅ Fixed: now_default() not default_now()

        # Update status JSON
        status['reset_deadline'] = new_deadline_with_tz.isoformat()
        status['reset_attempt'] = reset_attempt + 1

        # Update database
        with database.get_write_session_context() as db:
            update_query = text("""
                UPDATE etl_jobs
                SET status = :status,
                    last_updated_at = :now
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(update_query, {
                'job_id': job_id,
                'tenant_id': tenant_id,
                'status': json.dumps(status),
                'now': now
            })

        logger.info(f"⏰ Extended reset deadline for job {job_id} to {new_deadline_with_tz.isoformat()} (attempt {reset_attempt + 1}, next check in {next_interval}s)")

        # 🔑 DO NOT send WebSocket updates from reset scheduler
        # Workers are responsible for sending step status updates
        # Reset scheduler only updates reset_deadline field in database
        # This prevents race conditions where reset scheduler overwrites worker status updates
        logger.debug(f"📝 Reset deadline updated in database - workers will send status updates")

        # Schedule another reset check task
        await schedule_reset_check_task(job_id, tenant_id, delay_seconds=next_interval)
        
    except Exception as e:
        logger.error(f"❌ Error extending deadline for job {job_id}: {e}", exc_info=True)


async def reset_job_to_ready(job_id: int, tenant_id: int, status: Dict[str, Any]):
    """
    Reset job to READY status and calculate next_run.

    This ensures next_run is synchronized with the actual reset time,
    preventing the countdown from showing incorrect values.

    Args:
        job_id: ETL job ID
        tenant_id: Tenant ID
        status: Current job status JSON
    """
    try:
        from datetime import timedelta

        database = get_database()
        now = DateTimeHelper.now_default()

        # Update status JSON
        status['overall'] = 'READY'
        status['token'] = None
        status['reset_deadline'] = None
        status['reset_attempt'] = 0

        # Reset all step statuses to idle
        if 'steps' in status:
            for step_name, step_data in status['steps'].items():
                step_data['extraction'] = 'idle'
                step_data['transform'] = 'idle'
                step_data['embedding'] = 'idle'

        # 🔑 Calculate next_run based on schedule_interval_minutes
        # This is done at reset time to ensure synchronization
        with database.get_write_session_context() as db:
            # First, get schedule_interval_minutes
            schedule_query = text("""
                SELECT schedule_interval_minutes
                FROM etl_jobs
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            schedule_result = db.execute(schedule_query, {
                'job_id': job_id,
                'tenant_id': tenant_id
            }).fetchone()

            if schedule_result and schedule_result[0]:
                schedule_interval_minutes = schedule_result[0]
                next_run = now + timedelta(minutes=schedule_interval_minutes)
            else:
                # Default to 1 hour if not set
                next_run = now + timedelta(hours=1)

            # Update database with status and next_run
            update_query = text("""
                UPDATE etl_jobs
                SET status = :status,
                    next_run = :next_run,
                    last_updated_at = :now
                WHERE id = :job_id AND tenant_id = :tenant_id
            """)
            db.execute(update_query, {
                'job_id': job_id,
                'tenant_id': tenant_id,
                'status': json.dumps(status),
                'next_run': next_run,
                'now': now
            })

        logger.info(f"✅ Job {job_id} reset to READY")
        logger.info(f"   next_run: {next_run} (calculated at reset time)")

        # Send WebSocket update to active users (if any)
        # Include next_run in the message so frontend can update countdown immediately
        try:
            from app.api.websocket_routes import get_job_websocket_manager
            job_websocket_manager = get_job_websocket_manager()

            # Create enhanced status message with next_run timestamp
            status_with_next_run = {
                **status,
                'next_run': DateTimeHelper.to_iso_with_tz(next_run)  # Include next_run for countdown
            }

            await job_websocket_manager.send_job_status_update(
                tenant_id=tenant_id,
                job_id=job_id,
                status_json=status_with_next_run
            )
            logger.info(f"✅ WebSocket update sent for job reset to READY with next_run: {next_run}")
        except Exception as ws_error:
            logger.debug(f"WebSocket update failed (no active connections): {ws_error}")
        
    except Exception as e:
        logger.error(f"❌ Error resetting job {job_id} to READY: {e}", exc_info=True)


async def schedule_reset_check_task(job_id: int, tenant_id: int, delay_seconds: int):
    """
    Schedule a delayed task to check and reset job using threading.Timer.

    Args:
        job_id: ETL job ID
        tenant_id: Tenant ID
        delay_seconds: Delay in seconds before running the task
    """
    try:
        # Cancel any existing timer for this job
        if job_id in _active_reset_timers:
            existing_timer = _active_reset_timers[job_id]
            existing_timer.cancel()
            logger.debug(f"🔄 Cancelled existing reset check timer for job {job_id}")

        # Create a threading.Timer that will run the reset check
        timer = threading.Timer(delay_seconds, _run_reset_check_sync, args=(job_id, tenant_id))
        timer.daemon = True  # Daemon thread so it doesn't block shutdown
        timer.start()

        _active_reset_timers[job_id] = timer
        logger.info(f"📅 Scheduled reset check for job {job_id} in {delay_seconds}s")
    except Exception as e:
        logger.error(f"❌ Error scheduling reset check task for job {job_id}: {e}", exc_info=True)


def _run_reset_check_sync(job_id: int, tenant_id: int):
    """
    Synchronous wrapper to run async reset check task in a new event loop.

    This is called by threading.Timer and creates its own event loop to run
    the async reset_check_task function.

    Args:
        job_id: ETL job ID
        tenant_id: Tenant ID
    """
    try:
        logger.debug(f"⏱️ Running reset check for job {job_id}")

        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Run the async reset check task
            loop.run_until_complete(reset_check_task(job_id, tenant_id))
        finally:
            # Clean up the event loop
            loop.close()

        # Clean up the timer reference
        if job_id in _active_reset_timers:
            del _active_reset_timers[job_id]
            logger.debug(f"🧹 Cleaned up reset check timer for job {job_id}")

    except Exception as e:
        logger.error(f"❌ Error in reset check for job {job_id}: {e}", exc_info=True)

