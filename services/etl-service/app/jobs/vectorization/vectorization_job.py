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

            # Send initial progress update
            await websocket_manager.send_progress_update("Vectorization", 0.0, "[STARTING] Initializing vectorization job...")

            # Get initial queue statistics
            queue_stats = await self._get_queue_statistics(session, job_schedule.tenant_id)
            logger.info(f"Queue status: {queue_stats['pending']} pending, {queue_stats['total']} total items")

            if queue_stats['pending'] == 0:
                logger.info("No items in queue - vectorization job completed")
                await websocket_manager.send_progress_update("Vectorization", 100.0, "[COMPLETE] No items to process")
                return {
                    'status': 'success',
                    'message': 'No items to process',
                    'items_processed': 0,
                    'items_failed': 0,
                    'queue_stats': queue_stats
                }

            await websocket_manager.send_progress_update("Vectorization", 5.0, f"[QUEUE] Found {queue_stats['pending']} items to process")

            # Process queue with progress tracking (backend handles cleanup automatically)
            processing_result = await self._process_queue_with_progress(job_schedule.tenant_id, queue_stats['pending'])

            if processing_result['success']:
                logger.info(f"Vectorization processing completed successfully")

                # Backend handles cleanup automatically, so we just report completion
                await websocket_manager.send_progress_update("Vectorization", 100.0,
                    f"[COMPLETE] Vectorization job completed successfully")

                return {
                    'status': 'success',
                    'message': f"Vectorization job completed successfully",
                    'items_processed': processing_result['items_processed'],
                    'items_failed': processing_result.get('items_failed', 0),
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

    async def _process_queue_with_progress(self, tenant_id: int, total_items: int) -> Dict[str, Any]:
        """
        Process the vectorization queue with real-time progress updates.
        Starts backend processing and polls for completion.

        Args:
            tenant_id: Tenant ID for processing
            total_items: Total number of items to process

        Returns:
            Dict containing processing results
        """
        try:
            # Get system authentication token
            auth_token = self._get_auth_token(tenant_id)
            if not auth_token:
                return {
                    'success': False,
                    'error': 'Failed to obtain system authentication token'
                }

            async with httpx.AsyncClient(timeout=1800.0) as client:  # 30 minute timeout
                headers = {
                    'Authorization': f'Bearer {auth_token}',
                    'Content-Type': 'application/json'
                }

                # Start backend processing
                start_url = f"{self.backend_base_url}/api/v1/ai/vectors/process-queue"
                logger.info(f"Starting backend vectorization for tenant {tenant_id}")
                await websocket_manager.send_progress_update("Vectorization", 10.0, "[PROCESSING] Starting backend vectorization...")

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

                # Wait for backend to complete processing (event-driven approach)
                # The backend will send progress updates via webhooks to /api/vectorization_progress
                # We just need to wait for completion and do a final status check

                await websocket_manager.send_progress_update("Vectorization", 15.0, "[WAITING] Backend processing started - waiting for completion...")

                # Wait for backend processing to complete (with timeout)
                max_wait_time = 1800  # 30 minutes
                wait_interval = 10    # Check every 10 seconds (much less frequent than before)
                elapsed_time = 0

                stats_url = f"{self.backend_base_url}/api/v1/vectorization/queue-stats"

                while elapsed_time < max_wait_time:
                    await asyncio.sleep(wait_interval)
                    elapsed_time += wait_interval

                    try:
                        # Check if processing is complete (minimal polling, just for completion detection)
                        stats_response = await client.get(stats_url, headers=headers)
                        if stats_response.status_code == 200:
                            stats = stats_response.json()
                            pending = stats.get('pending', 0)
                            processing = stats.get('processing', 0)
                            completed = stats.get('completed', 0)
                            failed = stats.get('failed', 0)

                            # Check if processing is complete
                            if pending == 0 and processing == 0:
                                logger.info(f"Vectorization processing completed: {completed} completed, {failed} failed")
                                await websocket_manager.send_progress_update("Vectorization", 100.0,
                                    f"[COMPLETE] Processing finished: {completed} completed, {failed} failed")
                                return {
                                    'success': True,
                                    'response': result,
                                    'status_code': response.status_code,
                                    'items_processed': completed,
                                    'items_failed': failed,
                                    'final_stats': stats
                                }

                        else:
                            logger.warning(f"Failed to get queue stats: {stats_response.status_code}")

                    except Exception as e:
                        logger.warning(f"Error polling queue stats: {e}")

                # Timeout reached
                logger.error(f"Vectorization processing timed out after {max_wait_time} seconds")
                return {
                    'success': False,
                    'error': f"Processing timed out after {max_wait_time} seconds",
                    'items_processed': 0,
                    'items_failed': total_items
                }

        except Exception as e:
            logger.error(f"Failed to process queue with progress: {e}")
            return {
                'success': False,
                'error': f"Exception during queue processing: {str(e)}"
            }


    

    def _get_auth_token(self, tenant_id: int) -> Optional[str]:
        """Get system authentication token for backend API calls."""
        try:
            # Use system token for automated job execution
            from app.jobs.orchestrator import _get_system_token

            token = _get_system_token(tenant_id)
            if token:
                logger.debug(f"System token obtained for tenant {tenant_id}")
                return token
            else:
                logger.error(f"Failed to get system token for tenant {tenant_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to get system auth token: {e}")
            return None


# Main job execution function
async def run_vectorization_sync(session, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Main entry point for vectorization job execution.
    Called by the orchestrator when the vectorization job is triggered.
    """
    processor = VectorizationJobProcessor()
    return await processor.process_vectorization_queue(session, job_schedule)
