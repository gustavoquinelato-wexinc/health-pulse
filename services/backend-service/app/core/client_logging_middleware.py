"""
Tenant-aware logging middleware for Backend Service.
Extracts client context from JWT tokens and enables client-specific logging.
"""

import time
from typing import Optional, Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging_config import get_client_logger, get_tenant_logger, RequestLogger
from app.auth.auth_service import get_auth_service


class TenantLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts client context and enables client-specific logging."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request with client-aware logging."""
        start_time = time.time()
        client_context = await self._extract_client_context(request)
        
        # Store client context in request state for use by other components
        request.state.client_context = client_context
        
        # Get client-aware logger
        if client_context and client_context.get('client_name'):
            logger = get_client_logger("http.middleware", client_context['client_name'])
        else:
            logger = get_client_logger("http.middleware")
        
        # Log request start
        RequestLogger.log_request(
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            client_context=client_context
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Log successful response
            process_time = time.time() - start_time

            # Determine client identifier for logging (avoid "anonymous" for security)
            if client_context and client_context.get('client_name'):
                tenant_identifier = client_context['client_name']
            elif client_context:
                tenant_identifier = 'authenticated'  # User is authenticated but client name unknown
            else:
                tenant_identifier = 'unauthenticated'  # No authentication context

            logger.info(
                "Request completed",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                process_time=process_time,
                client=tenant_identifier
            )
            
            return response
            
        except Exception as exc:
            # Log error
            process_time = time.time() - start_time

            # Determine client identifier for logging (avoid "anonymous" for security)
            if client_context and client_context.get('client_name'):
                tenant_identifier = client_context['client_name']
            elif client_context:
                tenant_identifier = 'authenticated'  # User is authenticated but client name unknown
            else:
                tenant_identifier = 'unauthenticated'  # No authentication context

            logger.error(
                "Request failed",
                method=request.method,
                url=str(request.url),
                error=str(exc),
                error_type=type(exc).__name__,
                process_time=process_time,
                client=tenant_identifier
            )
            raise
    
    async def _extract_client_context(self, request: Request) -> Optional[Dict[str, Any]]:
        """Extract client context from JWT token."""
        try:
            # Get token from Authorization header or cookie
            token = None
            
            # Try Authorization header first
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]
            
            # Fallback to cookie
            if not token:
                token = request.cookies.get("pulse_token")
            
            if not token:
                return None
            
            # Validate token and extract user info
            auth_service = get_auth_service()
            user = await auth_service.verify_token(token)
            
            if not user:
                return None
            
            # Get tenant name from database
            from app.core.database import get_database
            from app.models.unified_models import Tenant

            database = get_database()
            with database.get_session() as session:
                tenant = session.query(Tenant).filter(
                    Tenant.id == user.tenant_id,
                    Tenant.active == True
                ).first()

                if not tenant:
                    return None

                return {
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.name,
                    'user_id': user.id,
                    # Don't include email in context to avoid PII in logs
                    'user_role': user.role
                }
        
        except Exception as e:
            # Don't let tenant context extraction break the request
            # Just log the error and continue without tenant context
            logger = get_tenant_logger("tenant_context_extraction")
            logger.warning(f"Failed to extract tenant context: {e}")
            return None


def get_tenant_context_from_request(request: Request) -> Optional[Dict[str, Any]]:
    """Helper function to get tenant context from request state."""
    return getattr(request.state, 'client_context', None)


def get_tenant_logger_from_request(request: Request, name: str = None):
    """Helper function to get tenant-aware logger from request."""
    tenant_context = get_tenant_context_from_request(request)
    tenant_name = tenant_context.get('tenant_name') if tenant_context else None
    return get_tenant_logger(name, tenant_name)
