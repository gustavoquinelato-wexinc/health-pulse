"""
Structured logging configuration for ETL Service application.
Uses structlog for organized and traceable logs.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict
import structlog
from structlog.stdlib import LoggerFactory
from structlog.dev import ConsoleRenderer
from structlog.processors import JSONRenderer, TimeStamper, add_log_level, StackInfoRenderer

# Initialize colorama for Windows terminal color support
import colorama
colorama.init(autoreset=True)

from app.core.config import get_settings


class ColoredConsoleRenderer:
    """Custom colored console renderer that works better with Windows terminals."""

    def __init__(self):
        self.colors = {
            'debug': colorama.Fore.CYAN + colorama.Style.BRIGHT,
            'info': colorama.Fore.GREEN + colorama.Style.BRIGHT,
            'warning': colorama.Fore.YELLOW + colorama.Style.BRIGHT,
            'error': colorama.Fore.RED + colorama.Style.BRIGHT,
            'critical': colorama.Fore.MAGENTA + colorama.Style.BRIGHT,
        }

    def __call__(self, logger, method_name, event_dict):
        """Render log entry with colors."""
        timestamp = event_dict.get('timestamp', '')
        level = event_dict.get('level', 'info').lower()
        event = event_dict.get('event', '')
        logger_name = event_dict.get('logger', '')

        # Get color for log level
        color = self.colors.get(level, colorama.Fore.WHITE)

        # Enhance the event message with colored highlights
        enhanced_event = self._colorize_event_text(event, level)

        # Format the log message
        formatted = f"{timestamp} {color}[{level:8}]{colorama.Style.RESET_ALL} {enhanced_event}"

        if logger_name:
            formatted += f" {colorama.Fore.BLUE + colorama.Style.BRIGHT}[{logger_name}]{colorama.Style.RESET_ALL}"

        # Add any extra fields with enhanced coloring
        extra_fields = {k: v for k, v in event_dict.items()
                       if k not in ('timestamp', 'level', 'event', 'logger')}
        if extra_fields:
            colored_extras = []
            for k, v in extra_fields.items():
                colored_key = f"{colorama.Fore.CYAN + colorama.Style.BRIGHT}{k}{colorama.Style.RESET_ALL}"
                colored_value = self._colorize_value(str(v), k)
                colored_extras.append(f"{colored_key}={colored_value}")

            extra_str = ' '.join(colored_extras)
            formatted += f" {extra_str}"

        return formatted

    def _colorize_event_text(self, event, level):
        """Add color highlights to important parts of the event message."""
        import re

        if not event:
            return event

        # Color patterns for different types of information
        patterns = [
            # Project keys (e.g., BDP, BEN, etc.)
            (r'\b([A-Z]{2,4})\b', colorama.Fore.MAGENTA + colorama.Style.BRIGHT + r'\1' + colorama.Style.RESET_ALL),

            # Numbers (counts, IDs, etc.)
            (r'\b(\d+)\b', colorama.Fore.YELLOW + colorama.Style.BRIGHT + r'\1' + colorama.Style.RESET_ALL),

            # Status words (success, failed, completed, etc.)
            (r'\b(success|successful|successfully|completed|failed|error|warning)\b',
             colorama.Fore.GREEN + colorama.Style.BRIGHT + r'\1' + colorama.Style.RESET_ALL),

            # Action words (starting, extracting, processing, etc.)
            (r'\b(starting|extracting|processing|fetching|collecting|retrieved|updated)\b',
             colorama.Fore.CYAN + colorama.Style.BRIGHT + r'\1' + colorama.Style.RESET_ALL),

            # File/table names (anything with underscores or ending in common extensions)
            (r'\b(\w+_\w+|\w+\.(?:py|sql|json|csv))\b',
             colorama.Fore.BLUE + colorama.Style.BRIGHT + r'\1' + colorama.Style.RESET_ALL),

            # URLs or endpoints
            (r'(https?://[^\s]+|/[^\s]*)',
             colorama.Fore.BLUE + r'\1' + colorama.Style.RESET_ALL),
        ]

        colored_event = event
        for pattern, replacement in patterns:
            colored_event = re.sub(pattern, replacement, colored_event, flags=re.IGNORECASE)

        return colored_event

    def _colorize_value(self, value, key):
        """Colorize specific values based on their key or content."""
        # Color step descriptions
        if key == 'step':
            return f"{colorama.Fore.MAGENTA + colorama.Style.BRIGHT}{value}{colorama.Style.RESET_ALL}"

        # Color job names
        elif key in ('job_name', 'job_id'):
            return f"{colorama.Fore.CYAN + colorama.Style.BRIGHT}{value}{colorama.Style.RESET_ALL}"

        # Color numbers
        elif value.isdigit():
            return f"{colorama.Fore.YELLOW + colorama.Style.BRIGHT}{value}{colorama.Style.RESET_ALL}"

        # Color boolean values
        elif value.lower() in ('true', 'false', 'none', 'null'):
            color = colorama.Fore.GREEN if value.lower() == 'true' else colorama.Fore.RED
            return f"{color + colorama.Style.BRIGHT}{value}{colorama.Style.RESET_ALL}"

        # Default coloring
        else:
            return f"{colorama.Fore.WHITE}{value}{colorama.Style.RESET_ALL}"

settings = get_settings()

# Global flag to track if logging has been set up
_logging_configured = False


def setup_logging(force_reconfigure=False):
    """Configures the structured logging system."""
    global _logging_configured

    # Check if logging is already configured
    if _logging_configured and not force_reconfigure:
        return

    # Basic logging configuration
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        force=True  # Force reconfiguration of basic logging
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
    # Check for debug mode from multiple sources
    debug_mode = (
        settings.DEBUG or
        force_reconfigure or
        os.environ.get('DEBUG', '').lower() in ('true', '1', 'yes') or
        os.environ.get('FORCE_COLOR', '').lower() in ('true', '1', 'yes')
    )

    if debug_mode:
        # Development: colored and readable logs
        # Use custom colored renderer for better Windows terminal support
        processors = shared_processors + [
            ColoredConsoleRenderer()
        ]
    else:
        # Production: JSON logs
        processors = shared_processors + [
            JSONRenderer()
        ]
    
    # Clear structlog cache if forcing reconfiguration
    if force_reconfigure:
        try:
            # Clear the logger cache to allow reconfiguration
            structlog.reset_defaults()
        except Exception:
            # If reset_defaults doesn't work, try to clear manually
            pass

    # Configure structlog (allow reconfiguration if forced)
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=not force_reconfigure,  # Allow reconfiguration if forced
    )

    # Configure specific loggers
    _configure_third_party_loggers()

    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Add file handler (only if not already added)
    root_logger = logging.getLogger()
    if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
        file_handler = logging.FileHandler("logs/etl_service.log")
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Mark logging as configured
    _logging_configured = True


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


# Initialize logging when module is imported (only if not already configured)
if not _logging_configured:
    setup_logging()
