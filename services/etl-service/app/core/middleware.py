"""
Custom middleware for error handling and monitoring.
"""

import time
import traceback
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging_config import get_logger, RequestLogger
from app.core.config import get_settings
from app.core.security import SecurityValidator, validate_request_data, default_rate_limiter

logger = get_logger(__name__)
settings = get_settings()


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for centralized error handling."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        try:
            # Log request
            RequestLogger.log_request(
                method=request.method,
                url=str(request.url),
                headers=dict(request.headers)
            )
            
            # Process request
            response = await call_next(request)
            
            # Calculate response time
            process_time = time.time() - start_time
            
            # Log response
            RequestLogger.log_response(
                status_code=response.status_code,
                response_time=process_time,
                response_size=None  # FastAPI doesn't easily provide size
            )
            
            # Add processing time header
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as exc:
            process_time = time.time() - start_time
            
            # Log error
            logger.error(
                "Request processing failed",
                method=request.method,
                url=str(request.url),
                process_time=process_time,
                error=str(exc),
                error_type=type(exc).__name__,
                traceback=traceback.format_exc() if settings.DEBUG else None
            )
            
            # Return standardized error response
            return await self._create_error_response(exc, process_time)
    
    async def _create_error_response(self, exc: Exception, process_time: float) -> JSONResponse:
        """Creates standardized error response."""
        
        # Determine status code based on exception type
        if isinstance(exc, ValueError):
            status_code = status.HTTP_400_BAD_REQUEST
            error_type = "validation_error"
        elif isinstance(exc, PermissionError):
            status_code = status.HTTP_403_FORBIDDEN
            error_type = "permission_error"
        elif isinstance(exc, FileNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
            error_type = "not_found_error"
        elif isinstance(exc, TimeoutError):
            status_code = status.HTTP_408_REQUEST_TIMEOUT
            error_type = "timeout_error"
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_type = "internal_error"
        
        # Response content
        content = {
            "error": error_type,
            "message": str(exc) if settings.DEBUG else "An error occurred",
            "timestamp": time.time(),
            "process_time": process_time
        }
        
        # Add details in debug mode
        if settings.DEBUG:
            content["details"] = {
                "exception_type": type(exc).__name__,
                "traceback": traceback.format_exc()
            }
        
        return JSONResponse(
            status_code=status_code,
            content=content,
            headers={"X-Process-Time": str(process_time)}
        )


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware for security headers."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Remove headers that might leak information
        if "Server" in response.headers:
            del response.headers["Server"]
        
        return response


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware."""
    
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # In production, use Redis or similar
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get client IP
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Clean old requests
        self._cleanup_old_requests(current_time)
        
        # Check rate limit
        if self._is_rate_limited(client_ip, current_time):
            logger.warning(
                "Rate limit exceeded",
                client_ip=client_ip,
                max_requests=self.max_requests,
                window_seconds=self.window_seconds
            )
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Too many requests. Limit: {self.max_requests} per {self.window_seconds} seconds",
                    "retry_after": self.window_seconds
                },
                headers={"Retry-After": str(self.window_seconds)}
            )
        
        # Record request
        self._record_request(client_ip, current_time)
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP considering proxies."""
        # Check proxy headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct IP
        return request.client.host if request.client else "unknown"
    
    def _cleanup_old_requests(self, current_time: float):
        """Remove old requests from cache."""
        cutoff_time = current_time - self.window_seconds
        
        for ip in list(self.requests.keys()):
            self.requests[ip] = [
                req_time for req_time in self.requests[ip]
                if req_time > cutoff_time
            ]
            
            # Remove IPs without recent requests
            if not self.requests[ip]:
                del self.requests[ip]
    
    def _is_rate_limited(self, client_ip: str, current_time: float) -> bool:
        """Check if IP exceeded rate limit."""
        if client_ip not in self.requests:
            return False
        
        return len(self.requests[client_ip]) >= self.max_requests
    
    def _record_request(self, client_ip: str, current_time: float):
        """Record a new request."""
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        
        self.requests[client_ip].append(current_time)


class SecurityValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for security validation."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Validate URL parameters
        for param_name, param_value in request.query_params.items():
            if not validate_request_data(param_value):
                logger.warning(
                    "Security validation failed for query parameter",
                    param=param_name,
                    client_ip=self._get_client_ip(request)
                )
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "error": "invalid_input",
                        "message": "Invalid characters detected in request"
                    }
                )

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


class HealthCheckMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic health checks."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Simple health check for load balancers
        if request.url.path == "/health" and request.method == "GET":
            return JSONResponse(
                content={
                    "status": "healthy",
                    "timestamp": time.time(),
                    "service": settings.APP_NAME,
                    "version": settings.APP_VERSION
                }
            )
        
        return await call_next(request)
