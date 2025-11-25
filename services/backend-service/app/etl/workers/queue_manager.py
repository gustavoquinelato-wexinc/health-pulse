"""
RabbitMQ Queue Manager for ETL Service - Phase 1
Handles RabbitMQ connectivity, queue topology, and message publishing/consuming.
"""

import pika
import json
import logging
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager
import os

logger = logging.getLogger(__name__)


class QueueManager:
    """
    Manages RabbitMQ connections and queue operations for ETL pipeline.

    Premium Queue Topology (MVP):
    - extraction_queue_premium: Extract additional data
    - transform_queue_premium: Process raw data → final tables
    - embedding_queue_premium: Generate embeddings

    Total: 3 queues (premium tier only)
    Messages include tenant_id for routing after consumption.
    """

    # Premium tier only for MVP
    TIERS = ['premium']
    QUEUE_TYPES = ['extraction', 'transform', 'embedding']

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        vhost: Optional[str] = None
    ):
        """
        Initialize Queue Manager with RabbitMQ connection parameters.

        Args:
            host: RabbitMQ host (default: from env or 'localhost')
            port: RabbitMQ port (default: from env or 5672)
            username: RabbitMQ username (default: from env or 'etl_user')
            password: RabbitMQ password (default: from env or 'etl_password')
            vhost: RabbitMQ virtual host (default: from env or 'pulse_etl')
        """
        self.host: str = host or os.getenv('RABBITMQ_HOST', 'localhost')
        self.port: int = port if port is not None else int(os.getenv('RABBITMQ_PORT', '5672'))
        self.username: str = username or os.getenv('RABBITMQ_USER', 'etl_user')
        self.password: str = password or os.getenv('RABBITMQ_PASSWORD', 'etl_password')
        self.vhost: str = vhost or os.getenv('RABBITMQ_VHOST', 'pulse_etl')

        logger.info(f"QueueManager initialized: {self.username}@{self.host}:{self.port}/{self.vhost}")

    def get_tier_queue_name(self, tier: str, queue_type: str = 'transform') -> str:
        """
        Get tier-based queue name.

        Args:
            tier: Tenant tier ('free', 'basic', 'premium', 'enterprise')
            queue_type: Type of queue ('extraction', 'transform', 'embedding')

        Returns:
            str: Tier-based queue name (e.g., 'transform_queue_premium')
        """
        return f"{queue_type}_queue_{tier}"
    
    def _get_connection(self) -> pika.BlockingConnection:
        """
        Create a new RabbitMQ connection.
        
        Returns:
            pika.BlockingConnection: Active RabbitMQ connection
        """
        credentials = pika.PlainCredentials(self.username, self.password)
        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            virtual_host=self.vhost,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        
        try:
            connection = pika.BlockingConnection(parameters)
            #logger.debug(f"RabbitMQ connection established: {self.host}:{self.port}")
            return connection
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    @contextmanager
    def get_channel(self):
        """
        Context manager for RabbitMQ channel.
        Automatically closes connection when done.
        
        Usage:
            with queue_manager.get_channel() as channel:
                channel.basic_publish(...)
        """
        connection = None
        channel = None
        try:
            connection = self._get_connection()
            channel = connection.channel()
            yield channel
        finally:
            if channel and channel.is_open:
                channel.close()
            if connection and connection.is_open:
                connection.close()
    
    def setup_queues(self):
        """
        Set up tier-based queue topology.
        Creates 12 queues total: 4 tiers × 3 queue types (extraction, transform, embedding).

        Queues created:
        - extraction_queue_free, extraction_queue_basic, extraction_queue_premium, extraction_queue_enterprise
        - transform_queue_free, transform_queue_basic, transform_queue_premium, transform_queue_enterprise
        - embedding_queue_free, embedding_queue_basic, embedding_queue_premium, embedding_queue_enterprise
        """
        with self.get_channel() as channel:
            queue_count = 0

            # Create tier-based queues for each tier and queue type
            for tier in self.TIERS:
                for queue_type in self.QUEUE_TYPES:
                    queue_name = self.get_tier_queue_name(tier, queue_type)
                    channel.queue_declare(
                        queue=queue_name,
                        durable=True,  # Survive broker restart
                        arguments={'x-message-ttl': 86400000}  # 24 hours TTL
                    )
                    logger.info(f"Queue declared: {queue_name}")
                    queue_count += 1

        logger.info(f"✅ Tier-based queue topology setup complete: {queue_count} queues created (4 tiers × 3 types)")

    def _get_active_tenant_ids(self) -> list:
        """Get list of active tenant IDs from database."""
        try:
            from app.core.database import get_database
            from app.models.unified_models import Tenant

            database = get_database()
            with database.get_read_session_context() as session:
                tenants = session.query(Tenant).filter(Tenant.active == True).all()
                tenant_ids = [tenant.id for tenant in tenants]
                logger.info(f"Found {len(tenant_ids)} active tenants: {tenant_ids}")
                return tenant_ids
        except Exception as e:
            logger.error(f"Failed to get active tenant IDs: {e}")
            return [1]  # Fallback to tenant 1

    def _get_tenant_tier(self, tenant_id: int) -> str:
        """
        Get tier for a specific tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            str: Tenant tier ('free', 'basic', 'premium', 'enterprise')
        """
        try:
            from app.core.database import get_database
            from app.models.unified_models import Tenant

            database = get_database()
            with database.get_read_session_context() as session:
                tenant = session.query(Tenant).filter(Tenant.id == tenant_id).first()
                if tenant:
                    return tenant.tier
                else:
                    logger.warning(f"Tenant {tenant_id} not found, defaulting to 'premium' tier")
                    return 'premium'
        except Exception as e:
            logger.error(f"Failed to get tenant tier for tenant {tenant_id}: {e}")
            return 'premium'  # Fallback to premium tier
    
    def publish_transform_job(
        self,
        tenant_id: int,
        integration_id: int,
        raw_data_id: int,
        data_type: str,
        job_id: int = None,
        provider: str = None,
        old_last_sync_date: str = None,
        new_last_sync_date: str = None,
        first_item: bool = False,
        last_item: bool = False,
        last_job_item: bool = False,
        last_repo: bool = False,
        last_pr_last_nested: bool = False,  # 🔑 For nested extraction: true ONLY for last nested type of last PR
        token: str = None,  # 🔑 Job execution token
        rate_limited: bool = False  # 🔑 True if rate limit was hit

    ) -> bool:
        """
        Publish a transform job to the tier-based transform queue.

        Args:
            tenant_id: Tenant ID
            integration_id: Integration ID
            raw_data_id: ID of raw_extraction_data record
            data_type: Type of data ('jira_custom_fields', 'jira_issues', 'github_prs', etc.)
            job_id: ETL job ID (for completion tracking)
            provider: Provider name (jira, github, etc.)
            old_last_sync_date: Last sync date used for filtering (previous sync date)
            new_last_sync_date: New last sync date to update on completion (extraction end date)
            first_item: True if this is the first item in the queue
            last_item: True if this is the last item in the current step
            last_job_item: True if this item should trigger job completion
            last_repo: True if this is the last repository (GitHub only)
            last_pr_last_nested: For nested extraction only - true ONLY for last nested type of last PR (GitHub only)
            token: Job execution token for tracking messages through pipeline
            rate_limited: True if rate limit was hit (signals RATE_LIMITED status instead of FINISHED)

        Returns:
            bool: True if published successfully
        """
        # Standardized base message structure
        message = {
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'job_id': job_id,
            'type': data_type,  # ETL step name
            'provider': provider,
            'first_item': first_item,
            'last_item': last_item,
            'old_last_sync_date': old_last_sync_date,  # 🔑 Used for filtering (previous sync date)
            'new_last_sync_date': new_last_sync_date,  # 🔑 Used for job completion (extraction end date)
            'last_job_item': last_job_item,
            'token': token,  # 🔑 Job execution token for tracking
            'rate_limited': rate_limited,  # 🔑 Rate limit flag
            # Extraction → Transform specific fields
            'raw_data_id': raw_data_id,
            # GitHub-specific boundary flags
            'last_repo': last_repo,
            'last_pr_last_nested': last_pr_last_nested  # 🔑 For nested extraction completion tracking
        }

        # Get tenant tier and route to tier-based queue
        tier = self._get_tenant_tier(tenant_id)
        tier_queue = self.get_tier_queue_name(tier, 'transform')

        return self._publish_message(tier_queue, message)

    def publish_extraction_job(
        self,
        tenant_id: int,
        integration_id: int,
        extraction_type: str,
        extraction_data: Dict[str, Any],
        job_id: int = None,
        provider: str = None,
        old_last_sync_date: str = None,
        new_last_sync_date: str = None,
        first_item: bool = False,
        last_item: bool = False,
        last_job_item: bool = False,
        last_repo: bool = False,
        last_pr_last_nested: bool = False,  # 🔑 For nested extraction: true ONLY for last nested type of last PR
        token: str = None  # 🔑 Job execution token
    ) -> bool:
        """
        Publish an extraction job to the tier-based extraction queue.

        Args:
            tenant_id: Tenant ID
            integration_id: Integration ID
            extraction_type: Type of extraction ('jira_dev_status', etc.)
            extraction_data: Additional data for extraction (issue_id, issue_key, etc.)
            etl_job_id: ETL job ID (for completion tracking)
            provider_name: Provider name (Jira, GitHub, etc.)
            old_last_sync_date: Last sync date used for filtering (previous sync date)
            new_last_sync_date: New last sync date to update on completion (extraction end date)
            first_item: True if this is the first item in the queue
            last_item: True if this is the last item in the current step
            last_job_item: True if this item should trigger job completion
            last_repo: True if this is the last repository (GitHub only)
            last_pr_last_nested: For nested extraction only - true ONLY for last nested type of last PR (GitHub only)
            token: Job execution token for tracking messages through the pipeline

        Returns:
            bool: True if published successfully
        """
        message = {
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'type': extraction_type,
            'last_repo': last_repo,
            'last_pr_last_nested': last_pr_last_nested,  # 🔑 For nested extraction completion tracking
            **extraction_data  # Merge additional data (issue_id, issue_key, etc.)
        }

        # Add optional ETL job tracking fields
        if job_id is not None:
            message['job_id'] = job_id
        if provider is not None:
            message['provider'] = provider
        if old_last_sync_date is not None:
            message['old_last_sync_date'] = old_last_sync_date  # 🔑 Used for filtering (previous sync date)
        if new_last_sync_date is not None:
            message['new_last_sync_date'] = new_last_sync_date  # 🔑 Used for job completion (extraction end date)
        if token is not None:
            message['token'] = token  # 🔑 Job execution token for message tracking

        # 🎯 ALWAYS include flags (not just when True) for proper worker orchestration
        message['first_item'] = first_item
        message['last_item'] = last_item
        message['last_job_item'] = last_job_item

        # Get tenant tier and route to tier-based queue
        tier = self._get_tenant_tier(tenant_id)
        tier_queue = self.get_tier_queue_name(tier, 'extraction')

        return self._publish_message(tier_queue, message)

    def publish_embedding_job(
        self,
        tenant_id: int,
        table_name: str,
        external_id: str,
        job_id: int = None,
        integration_id: int = None,
        provider: str = None,
        old_last_sync_date: str = None,
        new_last_sync_date: str = None,
        first_item: bool = False,
        last_item: bool = False,
        last_job_item: bool = False,
        step_type: str = None,
        token: str = None,  # 🔑 Job execution token
        rate_limited: bool = False  # 🔑 True if rate limit was hit
    ) -> bool:
        """
        Publish an individual entity embedding job to the tier-based embedding queue.

        Args:
            tenant_id: Tenant ID
            table_name: Name of the table (work_items, prs, etc.)
            external_id: External ID of the entity (or internal ID for work_items_prs_links)
            job_id: ETL job ID (for completion tracking)
            integration_id: Integration ID
            provider: Provider name (jira, github, etc.)
            old_last_sync_date: Old last sync date used for filtering
            new_last_sync_date: New last sync date to update on completion (extraction end date)
            first_item: True if this is the first item in the queue
            last_item: True if this is the last item that completes the job
            last_job_item: True if this is the final item that completes the entire job
            step_type: ETL step type for status tracking
            token: Job execution token for tracking messages through pipeline
            rate_limited: True if rate limit was hit (signals RATE_LIMITED status instead of FINISHED)

        Returns:
            bool: True if published successfully
        """
        # Standardized base message structure
        message = {
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'job_id': job_id,
            'type': step_type,  # ETL step name for status tracking
            'provider': provider,
            'first_item': first_item,
            'last_item': last_item,
            'old_last_sync_date': old_last_sync_date,  # 🔑 Used for filtering (old_last_sync_date)
            'new_last_sync_date': new_last_sync_date,  # 🔑 Used for job completion (extraction end date)
            'last_job_item': last_job_item,
            'token': token,  # 🔑 Job execution token for tracking
            'rate_limited': rate_limited,  # 🔑 Rate limit flag
            # Transform → Embedding specific fields
            'table_name': table_name,
            'external_id': external_id
        }

        # Get tenant tier and route to tier-based queue
        tier = self._get_tenant_tier(tenant_id)
        tier_queue = self.get_tier_queue_name(tier, 'embedding')

        return self._publish_message(tier_queue, message)

    def publish_mapping_table_embedding(
        self,
        tenant_id: int,
        table_name: str
    ) -> bool:
        """
        Publish a mapping table embedding job to process the entire table.

        Args:
            tenant_id: Tenant ID
            table_name: Name of the mapping table (status_mappings, wits_mappings, etc.)

        Returns:
            bool: True if published successfully
        """
        message = {
            'type': 'mappings',
            'tenant_id': tenant_id,
            'table_name': table_name
        }

        # Get the appropriate tier queue for this tenant
        tier = self._get_tenant_tier(tenant_id)
        tier_queue = self.get_tier_queue_name(tier, 'embedding')

        return self._publish_message(tier_queue, message)

    def publish_message(self, queue_name: str, message: Dict[str, Any]) -> bool:
        """
        Public method to publish a message to any queue.

        Args:
            queue_name: Name of the queue
            message: Message dictionary to publish

        Returns:
            bool: True if published successfully
        """
        return self._publish_message(queue_name, message)

    def _publish_message(self, queue_name: str, message: Dict[str, Any]) -> bool:
        """
        Internal method to publish a message to a queue.
        
        Args:
            queue_name: Name of the queue
            message: Message dictionary to publish
            
        Returns:
            bool: True if published successfully
        """
        try:
            with self.get_channel() as channel:
                channel.basic_publish(
                    exchange='',
                    routing_key=queue_name,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Make message persistent
                        content_type='application/json'
                    )
                )
            logger.info(f"Message published to {queue_name}: {message}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish message to {queue_name}: {e}")
            return False

    def get_single_message(self, queue_name: str, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        Get a single message from the queue with timeout.

        Args:
            queue_name: Name of the queue to get message from
            timeout: Timeout in seconds

        Returns:
            Message dict if available, None if no message or timeout
        """
        try:
            with self.get_channel() as channel:
                method_frame, header_frame, body = channel.basic_get(queue=queue_name, auto_ack=False)

                if method_frame:
                    try:
                        message = json.loads(body)
                        # Acknowledge the message
                        channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                        return message
                    except Exception as e:
                        logger.error(f"Error parsing message: {e}")
                        # Reject and requeue the message
                        channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
                        return None
                else:
                    return None

        except Exception as e:
            logger.error(f"Error getting message from {queue_name}: {e}")
            return None

    def get_queue_stats(self, queue_name: str) -> Optional[Dict[str, int]]:
        """
        Get statistics for a queue.

        Args:
            queue_name: Name of the queue

        Returns:
            Dict with message_count and consumer_count, or None if error
        """
        try:
            with self.get_channel() as channel:
                method = channel.queue_declare(queue=queue_name, passive=True)
                return {
                    'message_count': method.method.message_count,
                    'consumer_count': method.method.consumer_count
                }
        except Exception as e:
            logger.error(f"Failed to get queue stats for {queue_name}: {e}")
            return None

    def check_messages_with_token(self, queue_name: str, token: str, max_peek: int = 100) -> bool:
        """
        Check if there are any messages in the queue with the given token.

        This method peeks at messages without consuming them to check if any have the matching token.

        Args:
            queue_name: Name of the queue to check
            token: Token to search for in messages
            max_peek: Maximum number of messages to peek at (default: 100)

        Returns:
            bool: True if any message with the token is found, False otherwise
        """
        try:
            with self.get_channel() as channel:
                peeked_count = 0

                while peeked_count < max_peek:
                    # Get a message without auto-acking
                    method_frame, header_frame, body = channel.basic_get(queue=queue_name, auto_ack=False)

                    if not method_frame:
                        # No more messages in queue
                        logger.debug(f"No more messages in {queue_name} after peeking {peeked_count} messages")
                        return False

                    try:
                        message = json.loads(body)
                        message_token = message.get('token')

                        # Immediately requeue the message (put it back)
                        channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)

                        if message_token == token:
                            logger.info(f"✅ Found message with token {token} in {queue_name}")
                            return True

                        peeked_count += 1

                    except Exception as e:
                        logger.error(f"Error parsing message while peeking: {e}")
                        # Requeue the message
                        channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
                        peeked_count += 1

                logger.info(f"No messages with token {token} found in {queue_name} (checked {peeked_count} messages)")
                return False

        except Exception as e:
            logger.error(f"Error checking messages with token in {queue_name}: {e}")
            return False


# Global queue manager instance
_queue_manager: Optional[QueueManager] = None


def get_queue_manager() -> QueueManager:
    """
    Get the global queue manager instance.
    Creates it if it doesn't exist.
    
    Returns:
        QueueManager: Global queue manager instance
    """
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = QueueManager()
    return _queue_manager

