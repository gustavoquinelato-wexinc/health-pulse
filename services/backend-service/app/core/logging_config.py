"""
Clean, minimal logging configuration for Backend Service.
Autonomous microservice logging - no shared dependencies.
"""

import logging
import sys
import os
import re
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


class TokenMaskingFilter(logging.Filter):
    """Filter to mask JWT tokens in log messages (especially Uvicorn access logs)."""

    # Pattern to match JWT tokens in URLs (e.g., ?token=eyJhbGciOi...)
    TOKEN_PATTERN = re.compile(r'(\?|&)(token=)([A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)')

    def filter(self, record):
        """Mask tokens in log message."""
        # Mask in the raw message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self.TOKEN_PATTERN.sub(
                lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)[:10]}...{m.group(3)[-10:]}",
                record.msg
            )

        # Also mask in args (Uvicorn uses args for formatting)
        if hasattr(record, 'args') and record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    self.TOKEN_PATTERN.sub(
                        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)[:10]}...{m.group(3)[-10:]}",
                        str(arg)
                    ) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: self.TOKEN_PATTERN.sub(
                        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)[:10]}...{m.group(3)[-10:]}",
                        str(v)
                    ) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }

        return True


class UvicornAccessFilter(logging.Filter):
    """Filter to reduce noise from routine HTTP requests while keeping important ones."""

    # Routes to suppress (routine health checks, OPTIONS, etc.)
    SUPPRESS_ROUTES = {
        '/health', '/healthz', '/api/v1/auth/validate',
        '/api/v1/user/theme-mode', '/api/v1/admin/color-schema/unified',
        '/api/v1/websocket/status'
    }

    # Route prefixes to suppress
    SUPPRESS_PREFIXES = []

    # Methods to suppress for all routes
    SUPPRESS_METHODS = {'OPTIONS'}

    def filter(self, record):
        """Filter out routine HTTP requests to reduce log noise."""
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            msg = record.msg

            # Check if this is an HTTP request log
            if ' - "' in msg and ' HTTP/' in msg:
                # Extract method and path
                try:
                    # Format: "IP:PORT - "METHOD /path HTTP/1.1" STATUS"
                    parts = msg.split('"')
                    if len(parts) >= 2:
                        request_line = parts[1]  # "METHOD /path HTTP/1.1"
                        method_path = request_line.split(' ')
                        if len(method_path) >= 2:
                            method = method_path[0]
                            path = method_path[1]

                            # Remove query parameters for matching
                            path_without_query = path.split('?')[0]

                            # Suppress OPTIONS requests
                            if method in self.SUPPRESS_METHODS:
                                return False

                            # Suppress specific routes
                            if path_without_query in self.SUPPRESS_ROUTES:
                                return False

                            # Suppress route prefixes
                            for prefix in self.SUPPRESS_PREFIXES:
                                if path_without_query.startswith(prefix):
                                    return False

                except Exception:
                    # If parsing fails, allow the log through
                    pass

        return True


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

    # Console handler - only show WARNING+ to reduce noise, but allow ETL job logs
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if DEBUG else logging.WARNING)
    console_handler.setFormatter(formatter)

    # Add filter to allow important ETL job messages through
    def console_filter(record):
        message = record.getMessage()
        # Always show WARNING+ messages
        if record.levelno >= logging.WARNING:
            return True
        # Allow ETL job start/finish messages and worker debug messages
        if any(keyword in message for keyword in [
            "🚀 ETL JOB STARTED:", "🏁 ETL JOB FINISHED:", "💥 ETL JOB FAILED:",
            "Job scheduler started successfully", "Backend Service started successfully",
            "[WORKER-DEBUG]", "[DEBUG]", "🚀 Starting PREMIUM WORKER POOLS", "✅ ETL workers started",
            "📨", "🔍", "📋", "✅ Jira extraction job queued", "❌ Failed to publish", "DEBOGA",
            "🔐"  # Authentication debug logs
        ]):
            return True
        return False

    console_handler.addFilter(console_filter)
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
    # Log DEBUG+ to file when DEBUG=true, otherwise INFO+
    # This allows detailed debugging in development and ETL job logs in production
    file_handler.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    file_handler.setFormatter(formatter)

    # Add filter to allow important ETL job messages to file
    def file_filter(record):
        message = record.getMessage()
        # Always show WARNING+ messages
        if record.levelno >= logging.WARNING:
            return True
        # Allow INFO level ETL job messages and worker debug messages
        if record.levelno >= logging.INFO and any(keyword in message for keyword in [
            "🚀 ETL JOB STARTED:", "🏁 ETL JOB FINISHED:", "💥 ETL JOB FAILED:",
            "✅ JOB STARTED:", "📊 JOB STATUS CHECK:", "🔵 MANUAL TRIGGER:", "🟢 AUTO TRIGGER:",
            "Job scheduler started successfully", "Backend Service started successfully",
            "MANUAL TRIGGER:", "AUTO TRIGGER:",
            "[WORKER-DEBUG]", "[DEBUG]", "🚀 Starting PREMIUM WORKER POOLS", "✅ ETL workers started",
            "📨", "🔍", "📋", "✅ Jira extraction job queued", "❌ Failed to publish"
        ]):
            return True
        return False

    file_handler.addFilter(file_filter)
    root_logger.addHandler(file_handler)

    # Set root logger level
    root_logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

    # Apply token masking filter to all handlers (especially Uvicorn access logs)
    token_filter = TokenMaskingFilter()
    console_handler.addFilter(token_filter)
    file_handler.addFilter(token_filter)

    # Silence noisy third-party libraries
    _silence_third_party_loggers()

    # Apply token masking to Uvicorn access logger specifically
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    for handler in uvicorn_access_logger.handlers:
        handler.addFilter(token_filter)
    # Also add to future handlers
    uvicorn_access_logger.addFilter(token_filter)

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

    # Web framework - keep uvicorn.access at INFO to see masked WebSocket connections
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
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


def apply_uvicorn_filters():
    """
    Apply token masking and access filtering to Uvicorn loggers.

    This must be called AFTER Uvicorn starts, as Uvicorn creates its own handlers.
    Call this from the FastAPI lifespan startup event.
    """
    token_filter = TokenMaskingFilter()
    access_filter = UvicornAccessFilter()

    # Apply to uvicorn.access logger
    uvicorn_access_logger = logging.getLogger("uvicorn.access")

    # Remove any existing filters of these types to avoid duplicates
    for handler in uvicorn_access_logger.handlers:
        # Remove old filters
        handler.filters = [f for f in handler.filters
                          if not isinstance(f, (TokenMaskingFilter, UvicornAccessFilter))]
        # Add new filters
        handler.addFilter(token_filter)
        handler.addFilter(access_filter)

    # Also add to the logger itself for any future handlers
    uvicorn_access_logger.filters = [f for f in uvicorn_access_logger.filters
                                      if not isinstance(f, (TokenMaskingFilter, UvicornAccessFilter))]
    uvicorn_access_logger.addFilter(token_filter)
    uvicorn_access_logger.addFilter(access_filter)

    # Apply to uvicorn logger (for general uvicorn messages)
    uvicorn_logger = logging.getLogger("uvicorn")
    for handler in uvicorn_logger.handlers:
        handler.filters = [f for f in handler.filters if not isinstance(f, TokenMaskingFilter)]
        handler.addFilter(token_filter)

    logging.getLogger(__name__).info("✅ Applied token masking and access filters to Uvicorn loggers")


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