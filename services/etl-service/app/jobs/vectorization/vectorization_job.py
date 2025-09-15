"""
Vectorization Job

Dedicated job for processing the vectorization queue.
Runs independently from ETL jobs and provides full control over vectorization processing.

Features:
- Processes vectorization queue in configurable batches
- Full job lifecycle management (pending → running → completed/failed)
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

logger = get_logger(__name__)


class VectorizationJobProcessor:
    """Handles vectorization queue processing with full job lifecycle management."""
    
    def __init__(self):
        self.batch_size = 20  # Configurable batch size
        self.max_retries = 3
        self.backend_base_url = "http://localhost:3001"
        
    async def process_vectorization_queue(self, session, job_schedule: JobSchedule) -> Dict[str, Any]:
        """
        Main vectorization processing function.
        
        Args:
            session: Database session
            job_schedule: The vectorization job schedule
            
        Returns:
            Dict containing processing results and statistics
        """
        try:
            logger.info(f"🚀 Starting vectorization job for tenant {job_schedule.tenant_id}")
            
            # Get queue statistics
            queue_stats = await self._get_queue_statistics(session, job_schedule.tenant_id)
            logger.info(f"📊 Queue status: {queue_stats['pending']} pending, {queue_stats['total']} total items")
            
            if queue_stats['pending'] == 0:
                logger.info("✅ No items in queue - vectorization job completed")
                return {
                    'status': 'success',
                    'message': 'No items to process',
                    'items_processed': 0,
                    'items_failed': 0,
                    'queue_stats': queue_stats
                }
            
            # Process queue via backend
            processing_result = await self._trigger_backend_processing(job_schedule.tenant_id)
            
            if processing_result['success']:
                logger.info(f"✅ Vectorization processing completed successfully")
                return {
                    'status': 'success',
                    'message': f"Processed {queue_stats['pending']} items successfully",
                    'items_processed': queue_stats['pending'],
                    'items_failed': 0,
                    'queue_stats': queue_stats,
                    'processing_details': processing_result
                }
            else:
                logger.error(f"❌ Vectorization processing failed: {processing_result.get('error', 'Unknown error')}")
                return {
                    'status': 'error',
                    'message': f"Processing failed: {processing_result.get('error', 'Unknown error')}",
                    'items_processed': 0,
                    'items_failed': queue_stats['pending'],
                    'queue_stats': queue_stats,
                    'error_details': processing_result
                }
                
        except Exception as e:
            logger.error(f"❌ Vectorization job failed with exception: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
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
    
    async def _trigger_backend_processing(self, tenant_id: int) -> Dict[str, Any]:
        """
        Trigger backend vectorization processing.
        
        This replaces the HTTP trigger that was previously called from ETL jobs.
        Now it's called from the dedicated vectorization job.
        """
        try:
            # Get authentication token (same logic as before)
            auth_token = await self._get_auth_token()
            if not auth_token:
                return {
                    'success': False,
                    'error': 'Failed to obtain authentication token'
                }
            
            # Trigger backend processing
            async with httpx.AsyncClient(timeout=300.0) as client:
                headers = {
                    'Authorization': f'Bearer {auth_token}',
                    'Content-Type': 'application/json'
                }
                
                url = f"{self.backend_base_url}/api/v1/ai/vectors/process-queue"
                
                logger.info(f"🔄 Triggering backend vectorization for tenant {tenant_id}")
                response = await client.post(url, headers=headers, json={'tenant_id': tenant_id})
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ Backend processing triggered successfully: {result}")
                    return {
                        'success': True,
                        'response': result,
                        'status_code': response.status_code
                    }
                else:
                    error_msg = f"Backend returned status {response.status_code}: {response.text}"
                    logger.error(f"❌ Backend processing failed: {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg,
                        'status_code': response.status_code,
                        'response_text': response.text
                    }
                    
        except Exception as e:
            logger.error(f"❌ Failed to trigger backend processing: {e}")
            return {
                'success': False,
                'error': f"Exception during backend trigger: {str(e)}"
            }
    
    async def _get_auth_token(self) -> Optional[str]:
        """Get authentication token for backend API calls."""
        try:
            # Use the same authentication logic as before
            async with httpx.AsyncClient(timeout=30.0) as client:
                auth_url = "http://localhost:3001/auth/login"
                auth_data = {
                    "email": "system@etl.local",
                    "password": "etl_system_password"
                }
                
                response = await client.post(auth_url, json=auth_data)
                if response.status_code == 200:
                    result = response.json()
                    return result.get('access_token')
                else:
                    logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to get auth token: {e}")
            return None


# Main job execution function
async def run_vectorization_sync(session, job_schedule: JobSchedule) -> Dict[str, Any]:
    """
    Main entry point for vectorization job execution.
    Called by the orchestrator when the vectorization job is triggered.
    """
    processor = VectorizationJobProcessor()
    return await processor.process_vectorization_queue(session, job_schedule)
