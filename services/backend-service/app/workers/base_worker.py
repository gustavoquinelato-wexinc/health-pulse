"""
Base worker class for queue processing.

Provides common functionality for all queue workers including connection management,
error handling, and message acknowledgment.
"""

import warnings
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable
from contextlib import contextmanager

# Suppress asyncio event loop closure warnings for workers
warnings.filterwarnings("ignore", message=".*Event loop is closed.*", category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*coroutine.*was never awaited.*", category=RuntimeWarning)

from app.etl.queue.queue_manager import QueueManager
from app.core.database import get_database
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class BaseWorker(ABC):
    """
    Base class for all queue workers.
    
    Provides common functionality:
    - RabbitMQ connection management
    - Database session management
    - Error handling and message acknowledgment
    - Graceful shutdown handling
    """
    
    def __init__(self, queue_name: str):
        """
        Initialize base worker.
        
        Args:
            queue_name: Name of the queue to consume from
        """
        self.queue_name = queue_name
        self.queue_manager = QueueManager()
        self.database = get_database()
        self.running = False
        
        logger.info(f"Initialized {self.__class__.__name__} for queue: {queue_name}")
    
    @abstractmethod
    def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a single message from the queue.
        
        Args:
            message: Message data from queue
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        pass
    
    def start_consuming(self):
        """
        Start consuming messages from the queue.
        Runs indefinitely until stopped.
        """
        logger.info(f"Starting {self.__class__.__name__} consumer for queue: {self.queue_name}")
        self.running = True

        try:
            # Use polling approach for graceful shutdown
            import time
            while self.running:
                try:
                    # Try to get a message with timeout
                    message = self.queue_manager.get_single_message(self.queue_name, timeout=1.0)
                    if message:
                        self._handle_message(message)
                    else:
                        # No message available, sleep briefly
                        time.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error processing message in {self.__class__.__name__}: {e}")
                    time.sleep(1.0)  # Wait before retrying

        except KeyboardInterrupt:
            logger.info(f"Received shutdown signal for {self.__class__.__name__}")
            self.stop()
        except Exception as e:
            logger.error(f"Error in {self.__class__.__name__} consumer: {e}")
            raise

        logger.info(f"{self.__class__.__name__} consumer stopped")
    
    def stop(self):
        """Stop the worker gracefully."""
        logger.info(f"Stopping {self.__class__.__name__}")
        self.running = False
    
    def _handle_message(self, message: Dict[str, Any]):
        """
        Internal message handler with error handling and acknowledgment.
        
        Args:
            message: Message data from queue
        """
        try:
            logger.debug(f"Processing message: {message}")
            
            # Process the message
            success = self.process_message(message)

            if success:
                logger.debug(f"Message processed successfully: {message.get('type', 'unknown')}")
            else:
                # Reduce log noise - entity may have been queued before commit
                logger.debug(f"Message processing failed (entity may not exist yet): {message.get('type', 'unknown')}")
                
        except Exception as e:
            logger.error(f"Error processing message in {self.__class__.__name__}: {e}")
            logger.error(f"Message data: {message}")
            # Message will be requeued due to auto_ack=False
    
    @contextmanager
    def get_db_session(self):
        """
        Get a database session with automatic cleanup.

        Usage:
            with self.get_db_session() as session:
                # Use session for writes

        Note: This uses write session context. For read-only operations,
        consider using get_db_read_session() instead.
        """
        with self.database.get_write_session_context() as session:
            yield session

    @contextmanager
    def get_db_read_session(self):
        """
        Get a read-only database session with automatic cleanup.

        Usage:
            with self.get_db_read_session() as session:
                # Use session for reads only
        """
        with self.database.get_read_session_context() as session:
            yield session
