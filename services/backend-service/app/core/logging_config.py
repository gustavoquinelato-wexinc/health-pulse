"""
Clean, minimal logging configuration for Backend Service.
Autonomous microservice logging - no shared dependencies.
"""

import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from app.core.config import get_settings

# Service configuration
SERVICE_NAME = "backend-service"
settings = get_settings()
DEBUG = settings.DEBUG

# Global flag to track if logging has been set up
_logging_configured = False


def setup_logging(force_reconfigure=False):
    """
    Clean, minimal logging setup for Backend Service.

    Rules:
    - DEBUG: Console only (development debugging)
    - INFO+: Console + File (important events)
    - File rotation: 10MB max, 5 backups
    - Silence noisy third-party libraries
    """
    global _logging_configured

    if _logging_configured and not force_reconfigure:
        return

    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Standard formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    file_handler = RotatingFileHandler(
        f"logs/{SERVICE_NAME}.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)  # INFO+ to file, DEBUG console only
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Set root logger level
    root_logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

    # Silence noisy third-party libraries
    _silence_third_party_loggers()

    _logging_configured = True


def _silence_third_party_loggers():
    """Reduce verbosity of noisy third-party libraries."""

    # HTTP libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Database libraries
    logging.getLogger("sqlalchemy").setLevel(logging.CRITICAL)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.CRITICAL)
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.CRITICAL)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.CRITICAL)

    # Message queue
    logging.getLogger("pika").setLevel(logging.WARNING)
    logging.getLogger("aio_pika").setLevel(logging.WARNING)

    # Web framework
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)

    # Background jobs
    logging.getLogger("apscheduler").setLevel(logging.INFO)

    # Only show uvicorn startup in production
    if not DEBUG:
        logging.getLogger("uvicorn").setLevel(logging.WARNING)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a clean logger instance.

    Args:
        name: Logger name. If None, uses calling module name.

    Returns:
        Standard Python logger instance.
    """
    if name is None:
        # Get calling module name
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get('__name__', 'unknown')
        else:
            name = 'unknown'

    return logging.getLogger(name)


class RequestLogger:
    """Simple request logger for middleware"""

    def __init__(self, name: str = "request"):
        self.logger = get_logger(name)

    def info(self, message: str, **kwargs):
        """Log info message"""
        if kwargs:
            message = f"{message} - {kwargs}"
        self.logger.info(message)

    def error(self, message: str, **kwargs):
        """Log error message"""
        if kwargs:
            message = f"{message} - {kwargs}"
        self.logger.error(message)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        if kwargs:
            message = f"{message} - {kwargs}"
        self.logger.warning(message)

    @classmethod
    def log_request(cls, method: str, url: str, headers: Optional[dict] = None, client_context: Optional[dict] = None):
        """Log incoming request details"""
        logger = get_logger("http.request")

        # Build log message
        message_parts = [f"{method} {url}"]

        if client_context:
            if client_context.get('tenant_name'):
                message_parts.append(f"tenant={client_context['tenant_name']}")
            if client_context.get('user_role'):
                message_parts.append(f"role={client_context['user_role']}")

        message = " - ".join(message_parts)
        logger.info(message)

    @classmethod
    def log_response(cls, status_code: int, response_time: float, response_size: Optional[int] = None):
        """Log response details"""
        logger = get_logger("http.response")

        # Build log message
        message_parts = [f"Status: {status_code}", f"Time: {response_time:.3f}s"]

        if response_size:
            message_parts.append(f"Size: {response_size} bytes")

        message = " - ".join(message_parts)
        logger.info(message)


def get_tenant_logger(name: Optional[str] = None, tenant_name: Optional[str] = None):
    """
    Get a tenant-aware logger (simplified version).

    Args:
        name: Logger name. If None, uses calling module name.
        tenant_name: Tenant name for context (added to log messages).

    Returns:
        Standard Python logger instance.
    """
    logger = get_logger(name)

    if tenant_name:
        # Create a simple adapter that adds tenant context
        class TenantLoggerAdapter(logging.LoggerAdapter):
            def process(self, msg, kwargs):
                if self.extra and 'tenant' in self.extra:
                    return f"[{self.extra['tenant']}] {msg}", kwargs
                return msg, kwargs

        return TenantLoggerAdapter(logger, {'tenant': tenant_name})

    return logger


# Backward compatibility alias
def get_client_logger(name: Optional[str] = None, client_name: Optional[str] = None):
    """Backward compatibility alias for get_tenant_logger."""
    return get_tenant_logger(name, client_name)


class EnhancedLogger:
    """Enhanced logger that supports kwargs for structured logging."""

    def __init__(self, name: Optional[str] = None):
        self.logger = get_logger(name)

    def info(self, message: str, **kwargs):
        """Log info message with optional kwargs"""
        if kwargs:
            message = f"{message} - {kwargs}"
        self.logger.info(message)

    def error(self, message: str, **kwargs):
        """Log error message with optional kwargs"""
        if kwargs:
            message = f"{message} - {kwargs}"
        self.logger.error(message)

    def warning(self, message: str, **kwargs):
        """Log warning message with optional kwargs"""
        if kwargs:
            message = f"{message} - {kwargs}"
        self.logger.warning(message)

    def debug(self, message: str, **kwargs):
        """Log debug message with optional kwargs"""
        if kwargs:
            message = f"{message} - {kwargs}"
        self.logger.debug(message)


def get_enhanced_logger(name: Optional[str] = None) -> EnhancedLogger:
    """Get an enhanced logger that supports kwargs."""
    return EnhancedLogger(name)


class LoggerMixin:
    """Mixin to add clean logging to classes."""

    @property
    def logger(self) -> logging.Logger:
        """Returns logger for the class."""
        return get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    @property
    def enhanced_logger(self) -> EnhancedLogger:
        """Returns enhanced logger for the class that supports kwargs."""
        return get_enhanced_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")


# Legacy compatibility - remove complex classes
class TenantLoggingManager:
    """Simplified tenant logging manager for backward compatibility."""

    @classmethod
    def get_client_handler(cls, client_name: str):
        """Legacy method - now just returns None since we use standard logging."""
        return None