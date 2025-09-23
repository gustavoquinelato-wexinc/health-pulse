"""
Vectorization Job

Dedicated job for processing the vectorization queue.
Runs independently from ETL jobs and provides full control over vectorization processing.

Features:
- Processes vectorization queue in configurable batches
- Full job lifecycle management (pending -> running -> completed/failed)
- Progress tracking and error handling
- Retry mechanisms for failed items
- Queue statistics and monitoring
"""

import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.core.logging_config import get_logger
from app.core.database import get_database
from app.models.unified_models import JobSchedule, Integration
from app.core.orchestrator_scheduler import get_orchestrator_scheduler
from app.core.websocket_manager import websocket_manager

logger = get_logger(__name__)


class VectorizationJobProcessor:
    """Handles vectorization queue processing with full job lifecycle management."""
    
    def __init__(self):
        self.batch_size = 20  # Configurable batch size
        self.max_retries = 3
        self.backend_base_url = "http://localhost:3001"
        
    async def process_vectorization_queue(self, session, job_schedule: JobSchedule) -> Dict[str, Any]:
        """
        Main vectorization processing function with real-time progress tracking.

        Args:
            session: Database session
            job_schedule: The vectorization job schedule

        Returns:
            Dict containing processing results and statistics
        """
        try:
            logger.info(f"Starting vectorization job for tenant {job_schedule.tenant_id}")

            # Vectorization Job: 4 Equal Steps (25% each)
            TOTAL_STEPS = 4

            # Step 1: Initialization (0% → 25%)
            await websocket_manager.send_step_progress_update("Vectorization", 0, TOTAL_STEPS, 0.0, "[STARTING] Initializing vectorization job...")

            # Get initial queue statistics
            queue_stats = await self._get_queue_statistics(session, job_schedule.tenant_id)
            logger.info(f"Queue status: {queue_stats['pending']} pending, {queue_stats['total']} total items")

            if queue_stats['pending'] == 0:
                logger.info("No items in queue - vectorization job completed")
                await websocket_manager.send_step_progress_update("Vectorization", 3, TOTAL_STEPS, None, "[COMPLETE] No items to process")
                return {
                    'status': 'success',
                    'message': 'No items to process',
                    'items_processed': 0,
                    'items_failed': 0,
                    'queue_stats': queue_stats
                }

            await websocket_manager.send_step_progress_update("Vectorization", 0, TOTAL_STEPS, None, f"[QUEUE] Found {queue_stats['pending']} items to process")

            # Step 2-4: Process queue with progress tracking (25% → 100%)
            processing_result = await self._process_queue_with_progress(job_schedule.tenant_id, queue_stats['pending'], TOTAL_STEPS)

            if processing_result['success']:
                logger.info(f"Vectorization processing triggered successfully - backend will send progress via webhooks")

                # Step 4: Trigger completion (75% → 100% will be handled by webhooks)
                await websocket_manager.send_step_progress_update("Vectorization", 3, TOTAL_STEPS, None,
                    f"[TRIGGERED] Backend processing started - progress updates via webhooks")

                return {
                    'status': 'success',
                    'message': f"Vectorization processing triggered - backend will send real-time updates via webhooks",
                    'webhook_enabled': True,
                    'backend_triggered': True,
                    'queue_stats': queue_stats,
                    'processing_details': processing_result
                }
            else:
                error_msg = processing_result.get('error', 'Unknown error')
                logger.error(f"Vectorization processing failed: {error_msg}")
                await websocket_manager.send_progress_update("Vectorization", 100.0, f"[ERROR] Processing failed: {error_msg}")

                return {
                    'status': 'error',
                    'message': f"Processing failed: {error_msg}",
                    'items_processed': 0,
                    'items_failed': queue_stats['pending'],
                    'queue_stats': queue_stats,
                    'error_details': processing_result
                }

        except Exception as e:
            logger.error(f"Vectorization job failed with exception: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

            await websocket_manager.send_progress_update("Vectorization", 100.0, f"[ERROR] Job failed: {str(e)}")

            return {
                'status': 'error',
                'message': f"Job failed with exception: {str(e)}",
                'items_processed': 0,
                'items_failed': 0,
                'error': str(e)
            }
    
    async def _get_queue_statistics(self, session, tenant_id: int) -> Dict[str, int]:
        """Get vectorization queue statistics for a tenant."""
        from app.models.unified_models import VectorizationQueue
        
        # Total items
        total_query = session.query(VectorizationQueue).filter(
            VectorizationQueue.tenant_id == tenant_id
        )
        total_count = total_query.count()
        
        # Pending items
        pending_query = session.query(VectorizationQueue).filter(
            VectorizationQueue.tenant_id == tenant_id,
            VectorizationQueue.status == 'pending'
        )
        pending_count = pending_query.count()
        
        # Processing items
        processing_query = session.query(VectorizationQueue).filter(
            VectorizationQueue.tenant_id == tenant_id,
            VectorizationQueue.status == 'processing'
        )
        processing_count = processing_query.count()
        
        # Failed items
        failed_query = session.query(VectorizationQueue).filter(
            VectorizationQueue.tenant_id == tenant_id,
            VectorizationQueue.status == 'failed'
        )
        failed_count = failed_query.count()
        
        return {
            'total': total_count,
            'pending': pending_count,
            'processing': processing_count,
            'failed': failed_count,
            'completed': total_count - pending_count - processing_count - failed_count
        }

    async def _process_queue_with_progress(self, tenant_id: int, total_items: int, total_steps: int = 4) -> Dict[str, Any]:
        """
        Process the vectorization queue with event-driven progress updates.
        Triggers backend processing and waits for webhook completion notifications.

        Args:
            tenant_id: Tenant ID for processing
            total_items: Total number of items to process

        Returns:
            Dict containing processing results
        """
        try:
            # Use internal secret for service-to-service communication
            from app.core.config import get_settings
            settings = get_settings()
            internal_secret = settings.ETL_INTERNAL_SECRET

            async with httpx.AsyncClient(timeout=1800.0) as client:  # 30 minute timeout
                headers = {
                    'X-Internal-Auth': internal_secret,
                    'Content-Type': 'application/json'
                }

                # Step 2: Queue Preparation (25% → 50%)
                start_url = f"{self.backend_base_url}/api/v1/ai/vectors/process-queue-internal"
                logger.info(f"Starting backend vectorization for tenant {tenant_id}")
                await websocket_manager.send_step_progress_update("Vectorization", 1, total_steps, 0.0, "[PROCESSING] Starting backend vectorization...")

                response = await client.post(start_url, headers=headers, json={'tenant_id': tenant_id})

                if response.status_code != 200:
                    error_msg = f"Backend returned status {response.status_code}: {response.text}"
                    logger.error(f"Backend processing failed: {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg,
                        'status_code': response.status_code,
                        'response_text': response.text
                    }

                result = response.json()
                logger.info(f"Backend processing started: {result}")

                # Step 3: Processing Started (50% → 75%)
                await websocket_manager.send_step_progress_update("Vectorization", 2, total_steps, 0.0, "[TRIGGERED] Backend processing started - waiting for completion...")

                # Backend will now send real-time progress updates via webhooks
                # Wait for completion by monitoring the database job status
                logger.info(f"✅ Backend vectorization triggered successfully - waiting for completion")

                # Step 4: Wait for completion (75% → 100%)
                completion_result = await self._wait_for_backend_completion(tenant_id, total_steps)

                return completion_result

        except Exception as e:
            logger.error(f"Failed to process queue with progress: {e}")
            return {
                'success': False,
                'error': f"Exception during queue processing: {str(e)}"
            }


    



    async def _wait_for_backend_completion(self, tenant_id: int, total_steps: int) -> Dict[str, Any]:
        """
        Wait for backend vectorization to complete using webhook completion signals.
        The backend will send a completion webhook when 100% done, which is more reliable
        than polling the queue status due to cleanup race conditions.
        """
        from app.core.websocket_manager import get_websocket_manager
        from app.core.completion_signals import wait_for_vectorization_completion, clear_vectorization_completion_signal
        websocket_manager = get_websocket_manager()

        max_wait_time = 1800  # 30 minutes maximum

        logger.info(f"Waiting for backend vectorization completion signal (max {max_wait_time}s)")

        try:
            # Wait for completion signal from webhook
            completion_data = await wait_for_vectorization_completion(tenant_id, max_wait_time)

            if completion_data:
                # Backend completed successfully
                await websocket_manager.send_step_progress_update("Vectorization", 3, total_steps, None, "[COMPLETE] Backend vectorization completed successfully")
                logger.info(f"✅ Backend vectorization completed - received completion signal")

                # Clean up the completion signal
                clear_vectorization_completion_signal(tenant_id)

                return {
                    'success': True,
                    'message': f'Vectorization completed successfully - {completion_data.get("items_processed", 0)} items processed',
                    'items_processed': completion_data.get('items_processed', 0),
                    'items_failed': completion_data.get('items_failed', 0),
                    'completion_data': completion_data
                }
            else:
                # Timeout or error
                logger.error(f"Vectorization timeout after {max_wait_time}s - no completion signal received")
                await websocket_manager.send_step_progress_update("Vectorization", 3, total_steps, None, "[TIMEOUT] Vectorization timed out - check backend logs")

                # Clean up the completion signal
                clear_vectorization_completion_signal(tenant_id)

                return {
                    'success': False,
                    'error': f'Vectorization timed out after {max_wait_time} seconds - no completion signal received',
                    'items_processed': 0,
                    'items_failed': 0
                }

        except Exception as e:
            logger.error(f"Error waiting for vectorization completion: {e}")
            await websocket_manager.send_step_progress_update("Vectorization", 3, total_steps, None, f"[ERROR] Vectorization failed: {str(e)}")

            # Clean up the completion signal
            clear_vectorization_completion_signal(tenant_id)

            return {
                'success': False,
                'error': f'Vectorization failed: {str(e)}',
                'items_processed': 0,
                'items_failed': 0
            }


# Main job execution function
async def run_vectorization_sync(session, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Main entry point for vectorization job execution.
    Called by the orchestrator when the vectorization job is triggered.
    """
    processor = VectorizationJobProcessor()
    return await processor.process_vectorization_queue(session, job_schedule)
