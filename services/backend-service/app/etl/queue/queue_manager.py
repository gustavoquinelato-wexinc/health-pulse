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

    Multi-Tenant Queue Topology:
    - transform_queue_tenant_{tenant_id}: Process raw data → final tables (per tenant)
    - Supports dynamic queue creation and worker management per tenant
    """

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

        # Multi-tenant queue topology
        self.TRANSFORM_QUEUE_PREFIX = 'transform_queue_tenant_'
        self.VECTORIZATION_QUEUE_PREFIX = 'vectorization_queue_tenant_'

        logger.info(f"QueueManager initialized: {self.username}@{self.host}:{self.port}/{self.vhost}")

    def get_tenant_queue_name(self, tenant_id: int, queue_type: str = 'transform') -> str:
        """
        Get tenant-specific queue name.

        Args:
            tenant_id: Tenant ID
            queue_type: Type of queue ('transform', 'vectorization', etc.)

        Returns:
            str: Tenant-specific queue name
        """
        return f"{queue_type}_queue_tenant_{tenant_id}"
    
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
            logger.debug(f"RabbitMQ connection established: {self.host}:{self.port}")
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
    
    def setup_queues(self, tenant_ids: Optional[list] = None):
        """
        Set up multi-tenant queue topology.
        Creates transform and vectorization queues for specified tenants or discovers active tenants.

        Args:
            tenant_ids: List of tenant IDs to create queues for. If None, discovers active tenants.
        """
        with self.get_channel() as channel:
            # Get active tenant IDs if not provided
            if tenant_ids is None:
                tenant_ids = self._get_active_tenant_ids()

            # Create tenant-specific queues (both transform and vectorization)
            for tenant_id in tenant_ids:
                # Transform queue
                transform_queue = self.get_tenant_queue_name(tenant_id, 'transform')
                channel.queue_declare(
                    queue=transform_queue,
                    durable=True,  # Survive broker restart
                    arguments={'x-message-ttl': 86400000}  # 24 hours TTL
                )
                logger.info(f"Queue declared: {transform_queue}")

                # Vectorization queue
                vectorization_queue = self.get_tenant_queue_name(tenant_id, 'vectorization')
                channel.queue_declare(
                    queue=vectorization_queue,
                    durable=True,  # Survive broker restart
                    arguments={'x-message-ttl': 86400000}  # 24 hours TTL
                )
                logger.info(f"Queue declared: {vectorization_queue}")

            # Legacy queue removed - using only tenant-specific queues

        logger.info(f"✅ Multi-tenant queue topology setup complete for {len(tenant_ids)} tenants (transform + vectorization)")

    def setup_tenant_queue(self, tenant_id: int, queue_type: str = 'transform'):
        """
        Set up queue for a specific tenant.

        Args:
            tenant_id: Tenant ID
            queue_type: Type of queue to create
        """
        queue_name = self.get_tenant_queue_name(tenant_id, queue_type)

        with self.get_channel() as channel:
            channel.queue_declare(
                queue=queue_name,
                durable=True,
                arguments={'x-message-ttl': 86400000}
            )
            logger.info(f"Tenant queue declared: {queue_name}")

        return queue_name

    def _get_active_tenant_ids(self) -> list:
        """Get list of active tenant IDs from database."""
        try:
            from app.core.database import get_database
            from app.models.unified_models import Tenant

            database = get_database()
            with database.get_session() as session:
                tenants = session.query(Tenant).filter(Tenant.active == True).all()
                tenant_ids = [tenant.id for tenant in tenants]
                logger.info(f"Found {len(tenant_ids)} active tenants: {tenant_ids}")
                return tenant_ids
        except Exception as e:
            logger.error(f"Failed to get active tenant IDs: {e}")
            return [1]  # Fallback to tenant 1
    
    def publish_transform_job(
        self,
        tenant_id: int,
        integration_id: int,
        raw_data_id: int,
        data_type: str
    ) -> bool:
        """
        Publish a transform job to the tenant-specific transform queue.

        Args:
            tenant_id: Tenant ID
            integration_id: Integration ID
            raw_data_id: ID of raw_extraction_data record
            data_type: Type of data ('jira_custom_fields', 'jira_issues', 'github_prs', etc.)

        Returns:
            bool: True if published successfully
        """
        message = {
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'raw_data_id': raw_data_id,
            'type': data_type
        }

        # Use tenant-specific queue
        tenant_queue = self.get_tenant_queue_name(tenant_id, 'transform')

        # Ensure tenant queue exists
        try:
            self.setup_tenant_queue(tenant_id, 'transform')
        except Exception as e:
            logger.warning(f"Failed to ensure tenant queue exists: {e}")

        return self._publish_message(tenant_queue, message)

    def publish_vectorization_job(
        self,
        tenant_id: int,
        table_name: str,
        external_id: str,
        operation: str = "insert"
    ) -> bool:
        """
        Publish a vectorization job to the tenant-specific vectorization queue.

        Args:
            tenant_id: Tenant ID
            table_name: Name of the table (work_items, prs, etc.)
            external_id: External ID of the entity (or internal ID for work_items_prs_links)
            operation: Operation type ('insert', 'update', 'delete')

        Returns:
            bool: True if published successfully
        """
        message = {
            'tenant_id': tenant_id,
            'table_name': table_name,
            'external_id': external_id,
            'operation': operation
        }

        # Use tenant-specific vectorization queue
        tenant_queue = self.get_tenant_queue_name(tenant_id, 'vectorization')

        # Ensure tenant queue exists
        try:
            self.setup_tenant_queue(tenant_id, 'vectorization')
        except Exception as e:
            logger.warning(f"Failed to ensure vectorization queue exists: {e}")

        return self._publish_message(tenant_queue, message)

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
    
    def consume_messages(
        self,
        queue_name: str,
        callback: Callable[[Dict[str, Any]], None],
        auto_ack: bool = False
    ):
        """
        Consume messages from a queue.
        
        Args:
            queue_name: Name of the queue to consume from
            callback: Function to call for each message (receives message dict)
            auto_ack: Whether to auto-acknowledge messages
        """
        def on_message(ch, method, properties, body):
            try:
                message = json.loads(body)
                callback(message)
                if not auto_ack:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                if not auto_ack:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        
        with self.get_channel() as channel:
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=queue_name,
                on_message_callback=on_message,
                auto_ack=auto_ack
            )
            
            logger.info(f"Started consuming from {queue_name}")
            channel.start_consuming()

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

