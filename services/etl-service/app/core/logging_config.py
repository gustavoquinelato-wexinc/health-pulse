"""
Structured logging configuration for ETL Service application.
Uses structlog for organized and traceable logs.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict
import structlog
from structlog.stdlib import LoggerFactory
from structlog.dev import ConsoleRenderer
from structlog.processors import JSONRenderer, TimeStamper, add_log_level, StackInfoRenderer

from app.core.config import get_settings

settings = get_settings()


def setup_logging():
    """Configures the structured logging system."""
    
    # Basic logging configuration
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )
    
    # Common processors
    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        TimeStamper(fmt="ISO"),
        StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Configuration for development vs production
    if settings.DEBUG:
        # Development: colored and readable logs
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    else:
        # Production: JSON logs
        processors = shared_processors + [
            JSONRenderer()
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )
    
    # Configure specific loggers
    _configure_third_party_loggers()
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Add file handler
    file_handler = logging.FileHandler("logs/etl_service.log")
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Add handler to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)


def _configure_third_party_loggers():
    """Configures log levels for third-party libraries."""
    
    # Reduce verbosity of external libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("snowflake").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
    
    # Configure specific logs if needed
    if not settings.DEBUG:
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("fastapi").setLevel(logging.WARNING)


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """
    Returns a structured logger.
    
    Args:
        name: Logger name. If None, uses the calling module name.
    
    Returns:
        Configured structured logger.
    """
    if name is None:
        # Get calling module name
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    return structlog.get_logger(name)


class LoggerMixin:
    """Mixin to add structured logging to classes."""
    
    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Returns logger for the class."""
        return get_logger(self.__class__.__module__ + '.' + self.__class__.__name__)


class RequestLogger:
    """Utilities for HTTP request logging."""
    
    @staticmethod
    def log_request(method: str, url: str, headers: Dict = None, body: Any = None):
        """Log HTTP request."""
        logger = get_logger("http.request")
        
        log_data = {
            "method": method,
            "url": url,
            "headers_count": len(headers) if headers else 0
        }
        
        if body and settings.DEBUG:
            # In debug, include request body (be careful with sensitive data)
            log_data["body_size"] = len(str(body))
        
        logger.info("HTTP request", **log_data)
    
    @staticmethod
    def log_response(status_code: int, response_time: float, response_size: int = None):
        """Log HTTP response."""
        logger = get_logger("http.response")
        
        log_data = {
            "status_code": status_code,
            "response_time_ms": round(response_time * 1000, 2)
        }
        
        if response_size:
            log_data["response_size"] = response_size
        
        if status_code >= 400:
            logger.warning("HTTP response error", **log_data)
        else:
            logger.info("HTTP response", **log_data)


class JobLogger:
    """Utilities for job logging."""
    
    def __init__(self, job_name: str, job_id: str = None):
        self.job_name = job_name
        self.job_id = job_id or "unknown"
        self.logger = get_logger("jobs").bind(
            job_name=job_name,
            job_id=job_id
        )
    
    def start(self, **kwargs):
        """Log job start."""
        self.logger.info("Job started", **kwargs)
    
    def progress(self, step: str, progress_pct: float = None, **kwargs):
        """Log job progress."""
        log_data = {"step": step}
        if progress_pct is not None:
            log_data["progress_pct"] = progress_pct
        log_data.update(kwargs)
        
        self.logger.info("Job progress", **log_data)
    
    def success(self, duration: float = None, **kwargs):
        """Log job success."""
        log_data = kwargs.copy()
        if duration:
            log_data["duration_seconds"] = round(duration, 2)
        
        self.logger.info("Job completed successfully", **log_data)
    
    def error(self, error: Exception, **kwargs):
        """Log job error."""
        self.logger.error(
            "Job failed",
            error=str(error),
            error_type=type(error).__name__,
            **kwargs
        )
    
    def warning(self, message: str, **kwargs):
        """Log job warning."""
        self.logger.warning(message, **kwargs)

    def complete(self, duration: float = None, **kwargs):
        """Log job completion (alias for success)."""
        self.success(duration=duration, **kwargs)


class DatabaseLogger:
    """Utilities for database operation logging."""
    
    @staticmethod
    def log_query(query: str, params: Dict = None, execution_time: float = None):
        """Log database query."""
        logger = get_logger("database")
        
        log_data = {
            "query_type": query.strip().split()[0].upper() if query else "UNKNOWN",
            "query_length": len(query) if query else 0
        }
        
        if params:
            log_data["params_count"] = len(params)
        
        if execution_time:
            log_data["execution_time_ms"] = round(execution_time * 1000, 2)
        
        if settings.DEBUG and query:
            # In debug, include full query (be careful with sensitive data)
            log_data["query"] = query[:500] + "..." if len(query) > 500 else query
        
        logger.info("Database query", **log_data)
    
    @staticmethod
    def log_connection(action: str, database: str = None, **kwargs):
        """Log database connection."""
        logger = get_logger("database.connection")
        
        log_data = {"action": action}
        if database:
            log_data["database"] = database
        log_data.update(kwargs)
        
        logger.info("Database connection", **log_data)


# Initialize logging when module is imported
setup_logging()
