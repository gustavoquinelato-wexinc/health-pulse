"""
Clean, minimal logging configuration for Auth Service.
Autonomous microservice logging - no shared dependencies.
"""

import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Service configuration
SERVICE_NAME = "auth-service"
DEBUG = os.environ.get('DEBUG', 'false').lower() in ('true', '1', 'yes')

# Global flag to track if logging has been set up
_logging_configured = False


def setup_logging(force_reconfigure=False):
    """
    Clean, minimal logging setup for Auth Service.
    
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
    
    # Web framework
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    
    # Database (if used)
    logging.getLogger("sqlalchemy").setLevel(logging.CRITICAL)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.CRITICAL)
    
    # Only show uvicorn startup in production
    if not DEBUG:
        logging.getLogger("uvicorn").setLevel(logging.WARNING)


def get_logger(name: str = None) -> logging.Logger:
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
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin to add clean logging to classes."""
    
    @property
    def logger(self) -> logging.Logger:
        """Returns logger for the class."""
        return get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
