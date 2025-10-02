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
    
    Queue Topology:
    - extract_queue: Raw data extraction jobs
    - transform_queue: Transform jobs (Phase 1)
    - load_queue: Load jobs (Phase 2)
    """
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        vhost: str = None
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
        self.host = host or os.getenv('RABBITMQ_HOST', 'localhost')
        self.port = port or int(os.getenv('RABBITMQ_PORT', '5672'))
        self.username = username or os.getenv('RABBITMQ_USER', 'etl_user')
        self.password = password or os.getenv('RABBITMQ_PASSWORD', 'etl_password')
        self.vhost = vhost or os.getenv('RABBITMQ_VHOST', 'pulse_etl')
        
        # Queue names
        self.EXTRACT_QUEUE = 'extract_queue'
        self.TRANSFORM_QUEUE = 'transform_queue'
        self.LOAD_QUEUE = 'load_queue'
        
        logger.info(f"QueueManager initialized: {self.username}@{self.host}:{self.port}/{self.vhost}")
    
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
    
    def setup_queues(self):
        """
        Set up queue topology (declare all queues).
        Should be called once during application startup.
        """
        with self.get_channel() as channel:
            # Declare extract queue
            channel.queue_declare(
                queue=self.EXTRACT_QUEUE,
                durable=True,  # Survive broker restart
                arguments={'x-message-ttl': 86400000}  # 24 hours TTL
            )
            logger.info(f"Queue declared: {self.EXTRACT_QUEUE}")
            
            # Declare transform queue
            channel.queue_declare(
                queue=self.TRANSFORM_QUEUE,
                durable=True,
                arguments={'x-message-ttl': 86400000}
            )
            logger.info(f"Queue declared: {self.TRANSFORM_QUEUE}")
            
            # Declare load queue
            channel.queue_declare(
                queue=self.LOAD_QUEUE,
                durable=True,
                arguments={'x-message-ttl': 86400000}
            )
            logger.info(f"Queue declared: {self.LOAD_QUEUE}")
            
        logger.info("✅ Queue topology setup complete")
    
    def publish_extract_job(
        self,
        tenant_id: int,
        integration_id: int,
        job_type: str,
        job_params: Dict[str, Any]
    ) -> bool:
        """
        Publish an extraction job to the extract queue.
        
        Args:
            tenant_id: Tenant ID
            integration_id: Integration ID
            job_type: Type of extraction job ('jira_sync', 'github_sync', etc.)
            job_params: Job parameters (JQL, date range, etc.)
            
        Returns:
            bool: True if published successfully
        """
        message = {
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'job_type': job_type,
            'job_params': job_params
        }
        
        return self._publish_message(self.EXTRACT_QUEUE, message)
    
    def publish_transform_job(
        self,
        tenant_id: int,
        integration_id: int,
        raw_data_id: int,
        entity_type: str
    ) -> bool:
        """
        Publish a transform job to the transform queue.
        
        Args:
            tenant_id: Tenant ID
            integration_id: Integration ID
            raw_data_id: ID of raw_extraction_data record
            entity_type: Type of entity ('jira_issues_batch', 'github_prs_batch', etc.)
            
        Returns:
            bool: True if published successfully
        """
        message = {
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'raw_data_id': raw_data_id,
            'entity_type': entity_type
        }
        
        return self._publish_message(self.TRANSFORM_QUEUE, message)
    
    def publish_load_job(
        self,
        tenant_id: int,
        integration_id: int,
        transformed_data_id: int,
        entity_type: str
    ) -> bool:
        """
        Publish a load job to the load queue.
        
        Args:
            tenant_id: Tenant ID
            integration_id: Integration ID
            transformed_data_id: ID of transformed data record
            entity_type: Type of entity
            
        Returns:
            bool: True if published successfully
        """
        message = {
            'tenant_id': tenant_id,
            'integration_id': integration_id,
            'transformed_data_id': transformed_data_id,
            'entity_type': entity_type
        }
        
        return self._publish_message(self.LOAD_QUEUE, message)
    
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

