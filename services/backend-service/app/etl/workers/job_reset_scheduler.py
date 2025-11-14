"""
Job Reset Scheduler

Handles automatic reset of FINISHED ETL jobs after checking that all steps are complete
and all queues are empty. Uses self-scheduling delayed tasks with exponential backoff.

Flow:
1. Job finishes → set reset_deadline = now + 30s, schedule reset check task
2. Task runs after 30s → check step statuses + queues
3. If work remains → extend deadline (60s, 180s, 300s) and reschedule
4. If all complete → reset job to READY

This ensures the countdown is system-level (not per-user session) and works even
when no users are logged in.
"""

import asyncio
import json
import logging
from datetime import timedelta
from typing import Dict, Any, Optional
from sqlalchemy import text

from app.core.database import get_database
from app.core.utils import DateTimeHelper
from app.etl.workers.queue_manager import QueueManager

logger = logging.getLogger(__name__)


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
        
        # Check each step's status AND its corresponding queue (only if status = 'running')
        all_steps_finished = True
        steps = status.get('steps', {})
        
        for step_name, step_data in steps.items():
            # Check EXTRACTION status + queue
            extraction_status = step_data.get('extraction', 'idle')
            if extraction_status == 'running':
                # Status shows running - check if there are still messages in queue
                extraction_messages = queue_manager.check_messages_with_token(extraction_queue_name, token)
                
                if extraction_messages:
                    all_steps_finished = False
                    logger.info(f"   ⏳ Step '{step_name}' extraction is running with messages in {extraction_queue_name}")
                    break
            
            # Check TRANSFORM status + queue
            transform_status = step_data.get('transform', 'idle')
            if transform_status == 'running':
                # Status shows running - check if there are still messages in queue
                transform_messages = queue_manager.check_messages_with_token(transform_queue_name, token)
                
                if transform_messages:
                    all_steps_finished = False
                    logger.info(f"   ⏳ Step '{step_name}' transform is running with messages in {transform_queue_name}")
                    break
            
            # Check EMBEDDING status + queue
            embedding_status = step_data.get('embedding', 'idle')
            if embedding_status == 'running':
                # Status shows running - check if there are still messages in queue
                embedding_messages = queue_manager.check_messages_with_token(embedding_queue_name, token)
                
                if embedding_messages:
                    all_steps_finished = False
                    logger.info(f"   ⏳ Step '{step_name}' embedding is running with messages in {embedding_queue_name}")
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
        
        logger.info(f"⏰ Extended reset deadline for job {job_id} to {new_deadline} (attempt {reset_attempt + 1}, next check in {next_interval}s)")

        # Send WebSocket update to active users (if any)
        try:
            from app.api.websocket_routes import get_job_websocket_manager
            job_websocket_manager = get_job_websocket_manager()
            await job_websocket_manager.send_job_status_update(
                tenant_id=tenant_id,
                job_id=job_id,
                status_json=status
            )
            logger.info(f"✅ WebSocket update sent for extended deadline")
        except Exception as ws_error:
            logger.debug(f"WebSocket update failed (no active connections): {ws_error}")

        # Schedule another reset check task
        schedule_reset_check_task(job_id, tenant_id, delay_seconds=next_interval)
        
    except Exception as e:
        logger.error(f"❌ Error extending deadline for job {job_id}: {e}", exc_info=True)


async def reset_job_to_ready(job_id: int, tenant_id: int, status: Dict[str, Any]):
    """
    Reset job to READY status.
    
    Args:
        job_id: ETL job ID
        tenant_id: Tenant ID
        status: Current job status JSON
    """
    try:
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
        
        logger.info(f"✅ Job {job_id} reset to READY")

        # Send WebSocket update to active users (if any)
        try:
            from app.api.websocket_routes import get_job_websocket_manager
            job_websocket_manager = get_job_websocket_manager()
            await job_websocket_manager.send_job_status_update(
                tenant_id=tenant_id,
                job_id=job_id,
                status_json=status
            )
            logger.info(f"✅ WebSocket update sent for job reset to READY")
        except Exception as ws_error:
            logger.debug(f"WebSocket update failed (no active connections): {ws_error}")
        
    except Exception as e:
        logger.error(f"❌ Error resetting job {job_id} to READY: {e}", exc_info=True)


def schedule_reset_check_task(job_id: int, tenant_id: int, delay_seconds: int):
    """
    Schedule a delayed task to check and reset job.
    
    Args:
        job_id: ETL job ID
        tenant_id: Tenant ID
        delay_seconds: Delay in seconds before running the task
    """
    try:
        # Create the delayed task
        asyncio.create_task(delayed_reset_check(job_id, tenant_id, delay_seconds))
        logger.info(f"📅 Scheduled reset check for job {job_id} in {delay_seconds}s")
    except Exception as e:
        logger.error(f"❌ Error scheduling reset check task for job {job_id}: {e}", exc_info=True)


async def delayed_reset_check(job_id: int, tenant_id: int, delay_seconds: int):
    """
    Wait for delay, then run reset check task.
    
    Args:
        job_id: ETL job ID
        tenant_id: Tenant ID
        delay_seconds: Delay in seconds
    """
    try:
        logger.debug(f"⏱️ Waiting {delay_seconds}s before checking job {job_id} for reset")
        await asyncio.sleep(delay_seconds)
        await reset_check_task(job_id, tenant_id)
    except Exception as e:
        logger.error(f"❌ Error in delayed reset check for job {job_id}: {e}", exc_info=True)

