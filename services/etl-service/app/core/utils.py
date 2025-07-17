"""
Utilities and helper functions for ETL Service application.
"""

import logging
import re
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
from functools import wraps
import time

logger = logging.getLogger(__name__)


class DateTimeHelper:
    """Utilities for date and time manipulation."""
    
    @staticmethod
    def parse_jira_datetime(datetime_str: str) -> Optional[datetime]:
        """
        Converts Jira datetime string to datetime object.
        Supports different Jira formats.
        """
        if not datetime_str:
            return None
        
        try:
            # Remove timezone info for Snowflake compatibility
            if datetime_str.endswith('Z'):
                datetime_str = datetime_str[:-1]
            elif '+' in datetime_str:
                datetime_str = datetime_str.split('+')[0]
            elif datetime_str.endswith('000'):
                # Remove milliseconds if present
                datetime_str = datetime_str[:-3]
            
            # Replace T with space
            datetime_str = datetime_str.replace('T', ' ')
            
            # Try different formats
            formats = [
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d',
                '%d/%m/%Y %H:%M:%S',
                '%d/%m/%Y'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(datetime_str, fmt)
                except ValueError:
                    continue
            
            # If no format worked, try ISO format
            return datetime.fromisoformat(datetime_str)
            
        except Exception as e:
            logger.warning(f"Failed to parse datetime '{datetime_str}': {e}")
            return None
    
    @staticmethod
    def to_utc(dt: datetime) -> datetime:
        """Converts datetime to UTC."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """Formats duration in seconds to readable string."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"

    @staticmethod
    def parse_jira_datetime_to_naive_utc(datetime_str: str) -> Optional[datetime]:
        """
        Parse Jira datetime string to timezone-naive UTC datetime.

        This method ensures consistent datetime handling across the ETL service
        by converting all Jira datetimes to timezone-naive UTC format.

        Args:
            datetime_str: Jira datetime string (e.g., '2023-01-01T12:00:00.000+0000')

        Returns:
            Timezone-naive UTC datetime or None if parsing fails
        """
        if not datetime_str:
            return None

        try:
            # Jira uses ISO format: 2023-01-01T12:00:00.000+0000
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            # Convert to timezone-naive UTC for consistent database storage
            if dt.tzinfo is not None:
                dt = dt.utctimetuple()
                dt = datetime(*dt[:6])
            return dt
        except Exception as e:
            logger.warning(f"Could not parse datetime '{datetime_str}': {e}")
            return None

    @staticmethod
    def parse_datetime(datetime_str: str) -> Optional[datetime]:
        """
        Generic datetime parser that handles multiple formats.

        Args:
            datetime_str: Datetime string in various formats

        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not datetime_str:
            return None

        # Try different parsing methods
        parsers = [
            DateTimeHelper.parse_jira_datetime_to_naive_utc,
            DateTimeHelper.parse_jira_datetime,
            DateTimeHelper.parse_jira_datetime_preserve_local
        ]

        for parser in parsers:
            try:
                result = parser(datetime_str)
                if result:
                    return result
            except:
                continue

        # Try ISO format parsing as fallback
        try:
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00')).replace(tzinfo=None)
        except:
            pass

        logger.warning(f"Could not parse datetime '{datetime_str}' with any parser")
        return None

    @staticmethod
    def parse_iso_datetime(datetime_str: str) -> Optional[datetime]:
        """
        Parse ISO format datetime string (GitHub GraphQL format).

        Args:
            datetime_str: ISO datetime string (e.g., '2023-01-01T12:00:00Z')

        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not datetime_str:
            return None

        try:
            # Handle GitHub's ISO format with 'Z' suffix
            if datetime_str.endswith('Z'):
                datetime_str = datetime_str[:-1] + '+00:00'

            # Parse ISO format and convert to timezone-naive UTC
            dt = datetime.fromisoformat(datetime_str)
            if dt.tzinfo is not None:
                # Convert to UTC and make timezone-naive
                dt = dt.utctimetuple()
                return datetime(*dt[:6])
            return dt

        except Exception as e:
            logger.warning(f"Failed to parse ISO datetime '{datetime_str}': {e}")
            return None

    @staticmethod
    def parse_jira_datetime_preserve_local(datetime_str: str) -> Optional[datetime]:
        """
        Parse Jira datetime string preserving the local time (ignoring timezone).

        This method preserves the local time as shown in Jira, making it easier
        for users to correlate database times with what they see in Jira UI.

        Example:
            Input: "2025-05-30T10:34:55.069-0400"
            Output: datetime(2025, 5, 30, 10, 34, 55) (preserves 10:34 AM)

        Args:
            datetime_str: Jira datetime string (e.g., '2025-05-30T10:34:55.069-0400')

        Returns:
            Timezone-naive datetime preserving local time or None if parsing fails
        """
        if not datetime_str:
            return None

        try:
            # Parse the datetime but ignore timezone information
            # Extract just the date and time components before timezone
            if 'T' in datetime_str:
                date_time_part = datetime_str.split('T')
                if len(date_time_part) == 2:
                    date_part = date_time_part[0]
                    time_part = date_time_part[1]

                    # Remove timezone info (everything after + or -)
                    for tz_char in ['+', '-']:
                        if tz_char in time_part:
                            time_part = time_part.split(tz_char)[0]
                            break

                    # Remove 'Z' if present
                    time_part = time_part.rstrip('Z')

                    # Reconstruct datetime string without timezone
                    clean_datetime_str = f"{date_part}T{time_part}"

                    # Parse as naive datetime
                    return datetime.fromisoformat(clean_datetime_str)

            # Fallback to regular parsing if format is unexpected
            return datetime.fromisoformat(datetime_str.replace('Z', ''))

        except Exception as e:
            logger.warning(f"Could not parse datetime '{datetime_str}': {e}")
            return None

    @staticmethod
    def normalize_to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
        """
        Convert any datetime to timezone-naive UTC for consistent calculations.

        This method handles both timezone-aware and timezone-naive datetimes,
        ensuring all datetime operations use consistent timezone-naive UTC format.

        Args:
            dt: Datetime object (timezone-aware or naive)

        Returns:
            Timezone-naive UTC datetime or None if input is None
        """
        if dt is None:
            return None
        if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            # Convert to UTC and make naive
            utc_dt = dt.utctimetuple()
            return datetime(*utc_dt[:6])
        return dt

    @staticmethod
    def normalize_to_naive_local(dt: Optional[datetime]) -> Optional[datetime]:
        """
        Convert any datetime to timezone-naive preserving local time.

        This method removes timezone information while preserving the local time,
        making it consistent with the parse_jira_datetime_preserve_local approach.

        Args:
            dt: Datetime object (timezone-aware or naive)

        Returns:
            Timezone-naive datetime preserving local time or None if input is None
        """
        if dt is None:
            return None
        if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            # Remove timezone info but preserve local time
            return dt.replace(tzinfo=None)
        return dt

    @staticmethod
    def calculate_time_difference_hours(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> Optional[float]:
        """
        Calculate time difference between two datetimes in hours.

        Automatically normalizes both datetimes to timezone-naive local time before calculation
        to avoid timezone-related errors while preserving user-friendly time representation.

        Args:
            start_dt: Start datetime
            end_dt: End datetime

        Returns:
            Time difference in hours or None if calculation fails
        """
        if not start_dt or not end_dt:
            return None

        try:
            # Normalize both datetimes to timezone-naive local time
            start_normalized = DateTimeHelper.normalize_to_naive_local(start_dt)
            end_normalized = DateTimeHelper.normalize_to_naive_local(end_dt)

            if start_normalized and end_normalized:
                time_diff = end_normalized - start_normalized
                return time_diff.total_seconds() / 3600
            return None
        except Exception as e:
            logger.warning(f"Error calculating time difference: {e}")
            return None

    @staticmethod
    def calculate_time_difference_seconds_float(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> Optional[float]:
        """
        Calculate time difference between two datetimes in seconds (as float with millisecond precision).

        Automatically normalizes both datetimes to timezone-naive local time before calculation.
        Returns float seconds preserving millisecond precision for accurate timing analysis.

        Args:
            start_dt: Start datetime
            end_dt: End datetime

        Returns:
            Time difference in seconds (float) or None if calculation fails
            Example: 15.844 seconds (preserves 844 milliseconds)
        """
        if not start_dt or not end_dt:
            return None

        try:
            # Normalize both datetimes to timezone-naive local time
            start_normalized = DateTimeHelper.normalize_to_naive_local(start_dt)
            end_normalized = DateTimeHelper.normalize_to_naive_local(end_dt)

            if start_normalized and end_normalized:
                time_diff = end_normalized - start_normalized
                return time_diff.total_seconds()  # Returns float with millisecond precision
            return None
        except Exception as e:
            logger.warning(f"Error calculating time difference: {e}")
            return None

    @staticmethod
    def calculate_time_difference_seconds(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> Optional[float]:
        """
        Calculate time difference between two datetimes in seconds.

        Args:
            start_dt: Start datetime
            end_dt: End datetime

        Returns:
            Time difference in seconds or None if calculation fails
        """
        if not start_dt or not end_dt:
            return None

        try:
            # Normalize both datetimes to timezone-naive local time
            start_normalized = DateTimeHelper.normalize_to_naive_local(start_dt)
            end_normalized = DateTimeHelper.normalize_to_naive_local(end_dt)

            if start_normalized and end_normalized:
                time_diff = end_normalized - start_normalized
                return time_diff.total_seconds()
            return None
        except Exception as e:
            logger.warning(f"Error calculating time difference: {e}")
            return None

    @staticmethod
    def now_utc() -> datetime:
        """
        Get current datetime as timezone-naive UTC.

        Provides a consistent way to get current time across the application.

        Returns:
            Current datetime in timezone-naive UTC format
        """
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def now_central() -> datetime:
        """
        Get current datetime in Central Time (America/Chicago) as timezone-naive.

        Returns:
            datetime: Current Central Time without timezone info
        """
        try:
            import pytz
            central_tz = pytz.timezone('America/Chicago')
            utc_now = datetime.now(timezone.utc)
            central_now = utc_now.astimezone(central_tz)
            return central_now.replace(tzinfo=None)
        except ImportError:
            # Fallback: approximate Central Time as UTC-6 (ignoring DST)
            logger.warning("pytz not available, using UTC-6 approximation for Central Time")
            return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=6)



    @staticmethod
    def now_utc_iso() -> str:
        """
        Get current datetime as ISO format string.

        Useful for API responses and logging timestamps.

        Returns:
            Current datetime in ISO format string
        """
        return DateTimeHelper.now_utc().isoformat()

    @staticmethod
    def to_iso_string(dt: Optional[datetime]) -> Optional[str]:
        """
        Convert datetime to ISO format string.

        Args:
            dt: Datetime to convert

        Returns:
            ISO format string or None if input is None
        """
        if dt is None:
            return None
        normalized = DateTimeHelper.normalize_to_naive_utc(dt)
        return normalized.isoformat() if normalized else None


class DataValidator:
    """Utilities for data validation."""
    
    @staticmethod
    def is_valid_jira_key(key: str) -> bool:
        """Validates if a string is a valid Jira key (e.g., PROJ-123)."""
        if not key:
            return False
        pattern = r'^[A-Z][A-Z0-9]*-\d+$'
        return bool(re.match(pattern, key))
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Validates if a string is a valid email."""
        if not email:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Validates if a string is a valid URL."""
        if not url:
            return False
        pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        return bool(re.match(pattern, url))
    
    @staticmethod
    def sanitize_string(text: str, max_length: int = 1000) -> str:
        """Sanitizes string by removing special characters and limiting size."""
        if not text:
            return ""
        
        # Remove control characters
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        
        # Limit size
        if len(text) > max_length:
            text = text[:max_length-3] + "..."
        
        return text.strip()


def validate_url(url: str) -> bool:
    """Validates if a string is a valid URL."""
    return DataValidator.is_valid_url(url)


def sanitize_string(text: str, max_length: int = 1000) -> str:
    """Sanitizes string by removing special characters and limiting size."""
    return DataValidator.sanitize_string(text, max_length)


def generate_hash(data: Union[str, Dict, List]) -> str:
    """Generates MD5 hash for data."""
    if isinstance(data, (dict, list)):
        data = json.dumps(data, sort_keys=True)
    elif not isinstance(data, str):
        data = str(data)
    
    return hashlib.md5(data.encode('utf-8')).hexdigest()


class DataProcessor:
    """Utilities for data processing."""
    
    @staticmethod
    def extract_jira_issue_info(issue_data: Dict) -> Dict[str, Any]:
        """Extracts relevant information from a Jira issue."""
        fields = issue_data.get('fields', {})
        
        return {
            'id': issue_data.get('id'),
            'key': issue_data.get('key'),
            'summary': DataValidator.sanitize_string(fields.get('summary', '')),
            'description': DataValidator.sanitize_string(fields.get('description', ''), 5000),
            'created': DateTimeHelper.parse_jira_datetime(fields.get('created')),
            'updated': DateTimeHelper.parse_jira_datetime(fields.get('updated')),
            'priority': fields.get('priority', {}).get('name') if fields.get('priority') else None,
            'status': fields.get('status', {}).get('name') if fields.get('status') else None,
            'issuetype': fields.get('issuetype', {}).get('name') if fields.get('issuetype') else None,
            'assignee': fields.get('assignee', {}).get('displayName') if fields.get('assignee') else None,
            'reporter': fields.get('reporter', {}).get('displayName') if fields.get('reporter') else None,
            'project_key': fields.get('project', {}).get('key') if fields.get('project') else None,
            'labels': fields.get('labels', []),
            'components': [c.get('name') for c in fields.get('components', [])],
            'story_points': fields.get('customfield_10024'),  # Story Points field
            'parent_key': fields.get('parent', {}).get('key') if fields.get('parent') else None,
        }
    
    @staticmethod
    def chunk_list(lst: List, chunk_size: int) -> List[List]:
        """Divides a list into smaller chunks."""
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
    
    @staticmethod
    def flatten_dict(d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
        """Flattens a nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(DataProcessor.flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)


class RetryHelper:
    """Utilities for operation retry."""

    @staticmethod
    def retry_on_exception(
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: tuple = (Exception,),
        jitter: bool = True
    ):
        """
        Decorator for automatic retry on exception.

        Args:
            max_retries: Maximum number of attempts
            delay: Initial delay between attempts (seconds)
            backoff: Delay multiplier for each attempt
            exceptions: Tuple of exceptions that should be retried
            jitter: If True, adds random variation to delay
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                import random

                current_delay = delay
                last_exception = None

                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e

                        if attempt == max_retries:
                            logger.error(
                                "Function failed after max retries",
                                function=func.__name__,
                                max_retries=max_retries,
                                error=str(e)
                            )
                            raise e

                        # Calculate delay with optional jitter
                        actual_delay = current_delay
                        if jitter:
                            actual_delay *= (0.5 + random.random())

                        logger.warning(
                            "Function failed, retrying",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_attempts=max_retries + 1,
                            retry_delay=actual_delay,
                            error=str(e)
                        )

                        time.sleep(actual_delay)
                        current_delay *= backoff
                    except Exception as e:
                        # Non-listed exceptions are not retried
                        logger.error(
                            "Function failed with non-retryable exception",
                            function=func.__name__,
                            error=str(e),
                            error_type=type(e).__name__
                        )
                        raise e

                raise last_exception

            return wrapper
        return decorator


class ConfigHelper:
    """Configuration utilities."""
    
    @staticmethod
    def mask_sensitive_data(data: Dict, sensitive_keys: List[str] = None) -> Dict:
        """Masks sensitive data in dictionaries for logging."""
        if sensitive_keys is None:
            sensitive_keys = ['password', 'token', 'key', 'secret', 'credential']
        
        masked_data = data.copy()
        
        for key, value in masked_data.items():
            if any(sensitive_key.lower() in key.lower() for sensitive_key in sensitive_keys):
                if isinstance(value, str) and len(value) > 4:
                    masked_data[key] = value[:2] + '*' * (len(value) - 4) + value[-2:]
                else:
                    masked_data[key] = '***'
        
        return masked_data
