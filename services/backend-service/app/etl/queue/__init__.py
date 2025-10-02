"""
Queue management module for ETL service.
Handles RabbitMQ connectivity and message publishing/consuming.
"""

from .queue_manager import QueueManager

__all__ = ['QueueManager']

