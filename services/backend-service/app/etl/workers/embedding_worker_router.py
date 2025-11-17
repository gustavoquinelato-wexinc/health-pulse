"""
Embedding Worker Router - Routes embedding messages to provider-specific workers.

This router consumes from tier-based embedding queues and routes messages to:
- JiraEmbeddingWorker for Jira entity types
- GitHubEmbeddingWorker for GitHub entity types

Architecture:
- Generic router logic (queue consumption, retry, DLQ)
- Provider-specific logic delegated to provider workers
- Maintains separation of concerns

Tier-Based Queue Architecture:
- Workers consume from tier-based queues (embedding_queue_free, embedding_queue_premium, etc.)
- Each message contains tenant_id for proper routing
- Multiple workers per tier share the same queue
"""

import warnings
from typing import Dict, Any

# Suppress asyncio event loop closure warnings
warnings.filterwarnings("ignore", message=".*Event loop is closed.*", category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*coroutine.*was never awaited.*", category=RuntimeWarning)

from app.etl.workers.base_worker import BaseWorker
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Source type mapping for multi-agent architecture
SOURCE_TYPE_MAPPING = {
    # Jira Agent's scope (all Jira-related data including cross-links)
    'work_items': 'JIRA',
    'changelogs': 'JIRA',
    'projects': 'JIRA',
    'statuses': 'JIRA',
    'statuses_mappings': 'JIRA',
    'status_mappings': 'JIRA',  # Queue message name (maps to statuses_mappings table)
    'workflows': 'JIRA',
    'wits': 'JIRA',
    'wits_hierarchies': 'JIRA',
    'wits_mappings': 'JIRA',
    'work_items_prs_links': 'JIRA',  # Jira agent owns the links

    # GitHub Agent's scope (all GitHub-related data + DORA metrics)
    'prs': 'GITHUB',
    'prs_commits': 'GITHUB',
    'prs_reviews': 'GITHUB',
    'prs_comments': 'GITHUB',
    'repositories': 'GITHUB',
}


class EmbeddingWorker(BaseWorker):
    """
    Embedding Worker Router - Routes embedding messages to provider-specific workers.

    Routes messages to specialized workers:
    - JiraEmbeddingWorker: Processes all Jira entity types
    - GitHubEmbeddingWorker: Processes all GitHub entity types

    Tier-Based Queue Mode:
    - Consumes from tier-based queue (e.g., embedding_queue_premium)
    - Uses tenant_id from message for proper data routing
    - Routes to appropriate worker based on table_name or step_type
    """

    def __init__(self, tier: str = 'free'):
        """
        Initialize embedding worker router for specific tier.

        Args:
            tier: Tenant tier (free, basic, premium, enterprise)
        """
        queue_name = f"embedding_queue_{tier}"
        super().__init__(queue_name)
        self.tier = tier
        logger.info(f"✅ Initialized EmbeddingWorker router for tier: {tier}")

    async def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process embedding message by routing to appropriate provider worker.

        Message structure:
            {
                'tenant_id': int,
                'integration_id': int,
                'job_id': int,
                'type': str,  # ETL step name (e.g., 'jira_projects_and_issue_types')
                'table_name': str,  # Entity table name (e.g., 'work_items', 'prs')
                'external_id': str | None,  # Entity external_id (None for completion messages)
                'provider': str,  # 'jira' | 'github'
                'first_item': bool,
                'last_item': bool,
                'last_job_item': bool,
                'old_last_sync_date': str,
                'new_last_sync_date': str,
                'token': str
            }

        Returns:
            bool: True if message processed successfully
        """
        try:
            tenant_id = message.get('tenant_id')
            job_id = message.get('job_id')
            step_type = message.get('type')  # ETL step name
            table_name = message.get('table_name')
            external_id = message.get('external_id')
            first_item = message.get('first_item', False)

            logger.debug(f"📋 [EMBEDDING] Received message: tenant={tenant_id}, job={job_id}, step={step_type}, table={table_name}, external_id={external_id}")

            # 🔔 Send WebSocket status update when first_item=true (embedding worker starting)
            # This applies to ALL messages (ETL step or individual entity)
            if job_id and first_item:
                logger.info(f"🚀 [EMBEDDING] Sending 'running' status for {step_type or table_name}")
                try:
                    await self._send_worker_status("embedding", tenant_id, job_id, "running", step_type)
                    logger.debug(f"✅ [EMBEDDING] WebSocket 'running' status sent")
                except Exception as ws_error:
                    logger.error(f"❌ [EMBEDDING] Error sending WebSocket status: {ws_error}")

            # Route to appropriate embedding worker based on table_name or step_type
            # Determine provider from table_name or step_type
            provider = self._determine_provider(table_name, step_type)

            if not provider:
                logger.warning(f"⚠️ [EMBEDDING] Could not determine provider for table={table_name}, step={step_type}")
                return False

            logger.debug(f"📋 [EMBEDDING] Routing to {provider} embedding worker")

            # Route to provider-specific worker
            # IMPORTANT: Must cleanup worker after processing to close database sessions
            # NOTE: Individual workers now handle finished status and job completion internally
            worker = None
            try:
                if provider == 'jira':
                    from app.etl.jira.jira_embedding_worker import JiraEmbeddingWorker
                    worker = JiraEmbeddingWorker(
                        status_manager=self.status_manager,
                        queue_manager=self.queue_manager
                    )
                    result = await worker.process_jira_embedding(message)
                elif provider == 'github':
                    from app.etl.github.github_embedding_worker import GitHubEmbeddingWorker
                    worker = GitHubEmbeddingWorker(
                        status_manager=self.status_manager,
                        queue_manager=self.queue_manager
                    )
                    result = await worker.process_github_embedding(message)
                else:
                    logger.warning(f"❓ [EMBEDDING] Unknown provider: {provider}")
                    result = False
            finally:
                # Cleanup worker to close database session and async clients
                if worker and hasattr(worker, 'cleanup'):
                    try:
                        await worker.cleanup()
                        logger.debug(f"✅ [EMBEDDING] Worker cleanup completed for {provider}")
                    except Exception as cleanup_error:
                        logger.debug(f"Error during worker cleanup (suppressed): {cleanup_error}")

            return result

        except Exception as e:
            logger.error(f"❌ [EMBEDDING] Error processing message: {e}")
            import traceback
            logger.error(f"❌ [EMBEDDING] Full traceback: {traceback.format_exc()}")
            return False

    def _determine_provider(self, table_name: str = None, step_type: str = None) -> str:
        """
        Determine provider (jira/github) from table_name or step_type.

        Args:
            table_name: Entity table name (e.g., 'work_items', 'prs')
            step_type: ETL step name (e.g., 'jira_projects_and_issue_types')

        Returns:
            str: 'jira' or 'github' or None
        """
        # Try table_name first
        if table_name:
            source_type = SOURCE_TYPE_MAPPING.get(table_name)
            if source_type == 'JIRA':
                return 'jira'
            elif source_type == 'GITHUB':
                return 'github'

        # Try step_type
        if step_type:
            if step_type.startswith('jira_'):
                return 'jira'
            elif step_type.startswith('github_'):
                return 'github'

        return None

