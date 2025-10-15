"""
Extraction Worker - Handles additional data extraction requests (TIER-BASED QUEUE ARCHITECTURE).

This worker processes extraction requests that require additional API calls,
such as fetching dev_status for Jira issues.

Flow:
1. Receive extraction request from extraction_queue_{tier} (e.g., extraction_queue_premium)
2. Call external API to fetch data
3. Store raw data in raw_extraction_data table
4. Queue for transformation in transform_queue_{tier}

Tier-Based Queue Architecture:
- Workers consume from tier-based queues (extraction_queue_free, extraction_queue_premium, etc.)
- Each message contains tenant_id for proper routing
- Multiple workers per tier share the same queue
"""

import json
import time
from typing import Dict, Any, List, Optional

from app.workers.base_worker import BaseWorker
from app.core.logging_config import get_logger
from app.etl.queue.queue_manager import QueueManager
from sqlalchemy import text

logger = get_logger(__name__)


class ExtractionWorker(BaseWorker):
    """
    Worker that handles additional extraction requests (tier-based queue architecture).

    Supports different extraction types:
    - jira_dev_status_fetch: Fetch dev_status for a Jira issue
    - (future) github_pr_details_fetch: Fetch PR details
    - (future) jira_issue_links_fetch: Fetch issue links

    Tier-Based Queue Mode:
    - Consumes from tier-based queue (e.g., extraction_queue_premium)
    - Uses tenant_id from message for proper data routing
    """

    def __init__(self, queue_name: str, worker_number: int = 0, tenant_ids: Optional[List[int]] = None):
        """
        Initialize extraction worker for tier-based queue.

        Args:
            queue_name: Name of the tier-based extraction queue (e.g., 'extraction_queue_premium')
            worker_number: Worker instance number (for logging)
            tenant_ids: Deprecated (kept for backward compatibility)
        """
        super().__init__(queue_name)
        self.worker_number = worker_number
        logger.info(f"Initialized ExtractionWorker #{worker_number} for tier queue: {queue_name}")

    def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process an extraction message based on its type.
        
        Args:
            message: Message containing extraction request details
            
        Returns:
            bool: True if processing succeeded
        """
        try:
            extraction_type = message.get('type')
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            
            if not all([extraction_type, tenant_id, integration_id]):
                logger.error(f"Missing required fields in extraction message: {message}")
                return False
            
            logger.info(f"Processing {extraction_type} extraction request")
            
            # Route to appropriate extraction handler
            if extraction_type == 'jira_dev_status_fetch':
                return self._fetch_jira_dev_status(message)
            else:
                logger.warning(f"Unknown extraction type: {extraction_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing extraction message: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False
    
    def _fetch_jira_dev_status(self, message: Dict[str, Any]) -> bool:
        """
        Fetch dev_status for a Jira issue.
        
        Args:
            message: {
                'type': 'jira_dev_status_fetch',
                'issue_id': '12345',
                'issue_key': 'PROJ-123',
                'tenant_id': 1,
                'integration_id': 1
            }
            
        Returns:
            bool: True if fetch succeeded
        """
        try:
            issue_id = message.get('issue_id')
            issue_key = message.get('issue_key')
            tenant_id = message.get('tenant_id')
            integration_id = message.get('integration_id')
            
            if not all([issue_id, issue_key]):
                logger.error(f"Missing issue_id or issue_key in message: {message}")
                return False
            
            logger.debug(f"Fetching dev_status for issue {issue_key} (ID: {issue_id})")
            
            # Get integration details and create Jira client
            from app.core.database import get_database
            from app.models.unified_models import Integration
            
            database = get_database()
            with database.get_read_session_context() as session:
                integration = session.query(Integration).filter(
                    Integration.id == integration_id,
                    Integration.tenant_id == tenant_id
                ).first()
                
                if not integration:
                    logger.error(f"Integration {integration_id} not found for tenant {tenant_id}")
                    return False
                
                if not integration.active:
                    logger.warning(f"Integration {integration_id} is inactive, skipping dev_status fetch")
                    return True  # Not an error, just skip
            
            # Create Jira client and fetch dev_status
            from app.etl.jira_client import JiraAPIClient

            # Use the factory method that handles decryption automatically
            jira_client = JiraAPIClient.create_from_integration(integration)
            
            # Fetch dev_status from Jira API
            dev_status_data = jira_client.get_dev_status(issue_id)

            if not dev_status_data:
                logger.debug(f"No dev_status data found for issue {issue_key}")
                return True  # Not an error, just no data

            # Check if dev_status has actual PR data (not just empty arrays)
            detail = dev_status_data.get('detail', [])
            has_pr_data = False
            for item in detail:
                if item.get('pullRequests') or item.get('branches') or item.get('repositories'):
                    has_pr_data = True
                    break

            if not has_pr_data:
                logger.debug(f"Dev_status for issue {issue_key} has no PR data (empty arrays) - skipping")
                return True  # Not an error, just no useful data

            logger.debug(f"Fetched dev_status for issue {issue_key}: {len(detail)} items with PR data")
            
            # Store raw data in raw_extraction_data table
            with self.get_db_session() as db:
                insert_query = text("""
                    INSERT INTO raw_extraction_data (
                        tenant_id, integration_id, type, raw_data, status, created_at, last_updated_at
                    ) VALUES (
                        :tenant_id, :integration_id, :type, :raw_data, :status, NOW(), NOW()
                    ) RETURNING id
                """)
                
                result = db.execute(insert_query, {
                    'tenant_id': tenant_id,
                    'integration_id': integration_id,
                    'type': 'jira_dev_status',
                    'raw_data': json.dumps({
                        'issue_id': issue_id,
                        'issue_key': issue_key,
                        'dev_status': dev_status_data
                    }),
                    'status': 'pending'
                })
                
                raw_data_id = result.fetchone()[0]
                db.commit()
                
                logger.debug(f"Stored dev_status as raw_data_id={raw_data_id}")
            
            # Queue for transformation
            queue_manager = QueueManager()
            success = queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=integration_id,
                data_type='jira_dev_status',
                raw_data_id=raw_data_id
            )
            
            if success:
                logger.info(f"✅ Fetched and queued dev_status for issue {issue_key}")
                return True
            else:
                logger.error(f"Failed to queue dev_status for transformation (raw_data_id={raw_data_id})")
                return False
                
        except Exception as e:
            logger.error(f"Error fetching dev_status for issue {message.get('issue_key', 'unknown')}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

