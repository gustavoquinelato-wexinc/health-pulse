"""
Security module for data validation and sanitization.
"""

import re
import html
import hashlib
import secrets
import base64
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
import ipaddress

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class SecurityValidator:
    """Security validator for data input."""

    # Regex patterns for validation
    PATTERNS = {
        'sql_injection': re.compile(
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)|'
            r'(--|/\*|\*/|;|\'|"|\||&|\$|\(|\))',
            re.IGNORECASE
        ),
        'xss': re.compile(
            r'<script[^>]*>.*?</script>|'
            r'javascript:|'
            r'on\w+\s*=|'
            r'<iframe|'
            r'<object|'
            r'<embed',
            re.IGNORECASE | re.DOTALL
        ),
        'path_traversal': re.compile(
            r'(\.\./|\.\.\\|%2e%2e%2f|%2e%2e%5c)',
            re.IGNORECASE
        ),
        'command_injection': re.compile(
            r'(\||&|;|`|\$\(|\${|<|>|\n|\r)',
            re.IGNORECASE
        )
    }
    
    @classmethod
    def validate_sql_injection(cls, value: str) -> bool:
        """Checks for SQL injection attempts."""
        if not isinstance(value, str):
            return True
        
        if cls.PATTERNS['sql_injection'].search(value):
            logger.warning("Possible SQL injection attempt detected", value=value[:100])
            return False
        
        return True
    
    @classmethod
    def validate_xss(cls, value: str) -> bool:
        """Checks for XSS attempts."""
        if not isinstance(value, str):
            return True
        
        if cls.PATTERNS['xss'].search(value):
            logger.warning("Possible XSS attempt detected", value=value[:100])
            return False
        
        return True
    
    @classmethod
    def validate_path_traversal(cls, value: str) -> bool:
        """Checks for path traversal attempts."""
        if not isinstance(value, str):
            return True
        
        if cls.PATTERNS['path_traversal'].search(value):
            logger.warning("Possible path traversal attempt detected", value=value[:100])
            return False
        
        return True
    
    @classmethod
    def validate_command_injection(cls, value: str) -> bool:
        """Checks for command injection attempts."""
        if not isinstance(value, str):
            return True
        
        if cls.PATTERNS['command_injection'].search(value):
            logger.warning("Possible command injection attempt detected", value=value[:100])
            return False
        
        return True
    
    @classmethod
    def validate_all(cls, value: str) -> bool:
        """Executes all security validations."""
        if not isinstance(value, str):
            return True
        
        validations = [
            cls.validate_sql_injection(value),
            cls.validate_xss(value),
            cls.validate_path_traversal(value),
            cls.validate_command_injection(value)
        ]
        
        return all(validations)


class DataSanitizer:
    """Input data sanitizer."""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000, allow_html: bool = False) -> str:
        """Sanitizes string by removing dangerous characters."""
        if not isinstance(value, str):
            return str(value)

        # Remove control characters
        value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)

        # Escape HTML if not allowed
        if not allow_html:
            value = html.escape(value)

        # Limit size
        if len(value) > max_length:
            value = value[:max_length-3] + "..."

        return value.strip()
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitizes filename."""
        if not isinstance(filename, str):
            return "unknown"

        # Remove dangerous characters
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)

        # Remove dots at beginning/end
        filename = filename.strip('. ')

        # Limit size
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            max_name_len = 255 - len(ext) - 1 if ext else 255
            filename = name[:max_name_len] + ('.' + ext if ext else '')

        return filename or "unknown"
    
    @staticmethod
    def sanitize_url(url: str) -> Optional[str]:
        """Sanitizes and validates URL."""
        if not isinstance(url, str):
            return None

        try:
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme not in ['http', 'https']:
                return None

            # Check if has hostname
            if not parsed.netloc:
                return None

            # Rebuild clean URL
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"

            return clean_url

        except Exception:
            return None
    
    @staticmethod
    def sanitize_dict(data: Dict[str, Any], max_depth: int = 10) -> Dict[str, Any]:
        """Sanitizes dictionary recursively."""
        if max_depth <= 0:
            return {}

        sanitized = {}

        for key, value in data.items():
            # Sanitize key
            clean_key = DataSanitizer.sanitize_string(str(key), max_length=100)

            # Sanitize value based on type
            if isinstance(value, str):
                clean_value = DataSanitizer.sanitize_string(value)
            elif isinstance(value, dict):
                clean_value = DataSanitizer.sanitize_dict(value, max_depth - 1)
            elif isinstance(value, list):
                clean_value = [
                    DataSanitizer.sanitize_string(str(item)) if isinstance(item, str) else item
                    for item in value[:100]  # Limit list size
                ]
            else:
                clean_value = value

            sanitized[clean_key] = clean_value

        return sanitized


class IPValidator:
    """IP address validator."""

    # Private/local IP ranges that should be blocked in production
    PRIVATE_RANGES = [
        ipaddress.ip_network('10.0.0.0/8'),
        ipaddress.ip_network('172.16.0.0/12'),
        ipaddress.ip_network('192.168.0.0/16'),
        ipaddress.ip_network('127.0.0.0/8'),
        ipaddress.ip_network('169.254.0.0/16'),
        ipaddress.ip_network('::1/128'),
        ipaddress.ip_network('fc00::/7'),
        ipaddress.ip_network('fe80::/10'),
    ]
    
    @classmethod
    def is_valid_ip(cls, ip_str: str) -> bool:
        """Checks if it's a valid IP."""
        try:
            ipaddress.ip_address(ip_str)
            return True
        except ValueError:
            return False
    
    @classmethod
    def is_private_ip(cls, ip_str: str) -> bool:
        """Checks if it's a private/local IP."""
        try:
            ip = ipaddress.ip_address(ip_str)
            return any(ip in network for network in cls.PRIVATE_RANGES)
        except ValueError:
            return False
    
    @classmethod
    def is_allowed_ip(cls, ip_str: str, allow_private: bool = True) -> bool:
        """Checks if the IP is allowed."""
        if not cls.is_valid_ip(ip_str):
            return False
        
        if not allow_private and cls.is_private_ip(ip_str):
            return False
        
        return True


class TokenGenerator:
    """Secure token generator."""

    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """Generates secure API key."""
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_session_token(length: int = 24) -> str:
        """Generates session token."""
        return secrets.token_hex(length)

    @staticmethod
    def generate_csrf_token() -> str:
        """Generates CSRF token."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """Generates secure password hash."""
        if salt is None:
            salt = secrets.token_hex(16)

        # Uses PBKDF2 with SHA-256
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # 100k iterations
        )

        return base64.b64encode(password_hash).decode('utf-8'), salt

    @staticmethod
    def verify_password(password: str, password_hash: str, salt: str) -> bool:
        """Verifies password against hash."""
        try:
            computed_hash, _ = TokenGenerator.hash_password(password, salt)
            return secrets.compare_digest(password_hash, computed_hash)
        except Exception:
            return False


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # In production, use Redis

    def is_allowed(self, identifier: str) -> bool:
        """Checks if the request is allowed."""
        import time

        current_time = time.time()
        window_start = current_time - self.window_seconds

        # Clean old requests
        if identifier in self.requests:
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if req_time > window_start
            ]
        else:
            self.requests[identifier] = []

        # Check limit
        if len(self.requests[identifier]) >= self.max_requests:
            return False

        # Register new request
        self.requests[identifier].append(current_time)
        return True

    def get_remaining_requests(self, identifier: str) -> int:
        """Returns number of remaining requests."""
        if identifier not in self.requests:
            return self.max_requests

        return max(0, self.max_requests - len(self.requests[identifier]))


# Global rate limiter instance
default_rate_limiter = RateLimiter()


def validate_request_data(data: Any) -> bool:
    """Validates request data."""
    if isinstance(data, str):
        return SecurityValidator.validate_all(data)
    elif isinstance(data, dict):
        return all(
            validate_request_data(key) and validate_request_data(value)
            for key, value in data.items()
        )
    elif isinstance(data, list):
        return all(validate_request_data(item) for item in data)

    return True


def sanitize_request_data(data: Any) -> Any:
    """Sanitizes request data."""
    if isinstance(data, str):
        return DataSanitizer.sanitize_string(data)
    elif isinstance(data, dict):
        return DataSanitizer.sanitize_dict(data)
    elif isinstance(data, list):
        return [sanitize_request_data(item) for item in data]

    return data
