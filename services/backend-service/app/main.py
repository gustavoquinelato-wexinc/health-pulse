"""
Main FastAPI application for Backend Service.
Provides analytics APIs, authentication, and serves as API gateway for frontend.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn
import asyncio

# Backend Service - No scheduler needed

from app.core.config import get_settings
from app.core.database import get_database
from app.core.logging_config import get_logger
from app.core.middleware import (
    ErrorHandlingMiddleware, SecurityMiddleware, SecurityValidationMiddleware,
    RateLimitingMiddleware, HealthCheckMiddleware
)
from app.core.client_logging_middleware import ClientLoggingMiddleware
# Import Backend Service API routers
from app.api.health import router as health_router

from app.api.auth_routes import router as auth_router
from app.api.admin_routes import router as admin_router
from app.api.user_routes import router as user_router
from app.api.frontend_logs import router as frontend_logs_router
# Import new Core API routers with ML support
from app.api.issues import router as issues_router
from app.api.pull_requests import router as pull_requests_router
from app.api.projects import router as projects_router
from app.api.users import router as users_router
from app.api.ml_monitoring import router as ml_monitoring_router

# Suppress ALL noisy logs immediately to reduce terminal noise
import logging

# Disable SQLAlchemy logging completely
logging.getLogger("sqlalchemy").setLevel(logging.CRITICAL)
logging.getLogger("sqlalchemy.engine").setLevel(logging.CRITICAL)
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.CRITICAL)
logging.getLogger("sqlalchemy.pool").setLevel(logging.CRITICAL)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.CRITICAL)
logging.getLogger("sqlalchemy.orm").setLevel(logging.CRITICAL)
logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)
logging.getLogger("uvicorn").setLevel(logging.WARNING)

# Disable SQLAlchemy logging at the root level
logging.getLogger("sqlalchemy").disabled = True
logging.getLogger("sqlalchemy.engine").disabled = True
logging.getLogger("sqlalchemy.engine.Engine").disabled = True

# Also disable SQLAlchemy echo completely
import sqlalchemy
sqlalchemy.engine.Engine.echo = False

logger = get_logger(__name__)
settings = get_settings()

# Backend Service - No scheduler needed


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to handle authentication checks before route processing."""

    # Routes that don't require authentication
    PUBLIC_ROUTES = {
        "/", "/login", "/health", "/healthz", "/redoc", "/openapi.json",
        "/logout", "/auth/login", "/auth/validate"
    }

    # Routes that should redirect to login if not authenticated
    PROTECTED_WEB_ROUTES = {
        "/dashboard", "/admin"
    }

    # Route prefixes that should be treated as protected web routes
    PROTECTED_WEB_PREFIXES = [
        "/admin/"
    ]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # Always allow OPTIONS requests (CORS preflight) to pass through
        if method == "OPTIONS":
            logger.debug(f"OPTIONS request for {path} - allowing through")
            return await call_next(request)

        # Skip authentication for public routes
        if path in self.PUBLIC_ROUTES or path.startswith("/static/"):
            logger.debug(f"Public route {path} - skipping auth")
            return await call_next(request)

        # Skip authentication for API routes (they handle their own auth)
        if path.startswith("/api/") or path.startswith("/auth/"):
            logger.debug(f"API/Auth route {path} - skipping middleware auth")
            return await call_next(request)

        # For protected web routes and unknown routes, check authentication
        is_authenticated = await self.check_authentication(request)

        if not is_authenticated:
            # Determine redirect reason
            is_protected_route = (
                path in self.PROTECTED_WEB_ROUTES or
                any(path.startswith(prefix) for prefix in self.PROTECTED_WEB_PREFIXES)
            )

            if is_protected_route:
                return RedirectResponse(url="/login?error=authentication_required", status_code=302)
            else:
                # For unknown/404 routes, redirect with page_not_found error
                return RedirectResponse(url="/login?error=page_not_found", status_code=302)

        # User is authenticated, proceed with request
        return await call_next(request)

    async def check_authentication(self, request: Request) -> bool:
        """Check if user is authenticated."""
        try:
            from app.auth.auth_service import get_auth_service

            # Try to get token from cookies first
            token = request.cookies.get("pulse_token")

            if not token:
                # Try Authorization header
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.split(" ")[1]

            if not token:
                return False

            # Verify token via centralized auth-service
            import httpx
            from app.core.config import get_settings
            settings = get_settings()
            auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:4000')

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{auth_service_url}/api/v1/token/validate",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return bool(data.get("valid"))
                return False

        except Exception as e:
            logger.error(f"Authentication check failed: {e}")
            return False


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Manages the application lifecycle."""
    logger.info("Starting Backend Service...")

    try:
        # Initialize database connection
        database_initialized = await initialize_database()
        if database_initialized:
            logger.info("Database connection established successfully")
        else:
            logger.warning("Database connection failed - service will continue with limited functionality")

        # Backend Service - No scheduler needed

        # Clear all user sessions on startup for security
        # Skip in development mode to prevent authentication loops during frequent restarts
        from app.core.config import get_settings
        settings = get_settings()
        if not settings.DEBUG:
            await clear_all_user_sessions()
            logger.info("Session clearing enabled (production mode)")
        else:
            logger.info("Session clearing disabled (development mode - DEBUG=True)")

        logger.info("Backend Service started successfully")
        yield

    except Exception as e:
        logger.error(f"Failed to start Backend Service: {e}")
        # Don't raise the exception to allow the service to start even if database is not available
        logger.warning("Service started with limited functionality - database connection failed")
        yield
    finally:
        # Cleanup with robust error handling
        try:
            # Use print to avoid reentrant logging issues during shutdown
            print("[INFO] Shutting down Backend Service...")

            # Close database connections
            try:
                database = get_database()
                database.close_connections()
                print("[INFO] Database connections closed")
            except (Exception, asyncio.CancelledError):
                # Silently handle database cleanup errors
                pass

            print("[INFO] Backend Service shutdown complete")
        except (Exception, asyncio.CancelledError):
            # Silently handle any remaining shutdown errors
            pass


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## Backend Service - Pulse Platform Analytics API

    A specialized FastAPI backend service providing analytics APIs, authentication,
    and serving as the primary API gateway for the React frontend application.

    ### Key Features

    - **Analytics APIs**: DORA metrics, GitHub analytics, portfolio insights
    - **Authentication & Authorization**: JWT-based auth with role-based access control
    - **API Gateway**: Unified interface for frontend applications
    - **Job Management**: ETL job coordination and monitoring
    - **Real-time Data**: Live updates and WebSocket support
    - **Performance Optimized**: Query caching and connection pooling

    ### Analytics Capabilities

    1. **DORA Metrics**: Lead time, deployment frequency, MTTR calculations
    2. **GitHub Analytics**: Code quality metrics, PR analysis, contributor insights
    3. **Portfolio Analytics**: Cross-project aggregations and correlations
    4. **Executive Dashboards**: C-level KPIs and business intelligence
    5. **ETL Coordination**: Settings management and job control

    ### Authentication

    - **JWT Tokens**: Secure authentication with role-based access control
    - **Session Management**: Persistent sessions with automatic cleanup
    - **API Security**: Rate limiting, CORS, and comprehensive validation
    """,
    lifespan=lifespan,
    docs_url=None,  # Disabled - using custom protected route
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "Backend Service Support",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    tags_metadata=[
        {
            "name": "Analytics",
            "description": "Analytics APIs for DORA metrics, GitHub insights, and portfolio data.",
        },
        {
            "name": "Authentication",
            "description": "User authentication and authorization endpoints.",
        },
        {
            "name": "Jobs",
            "description": "ETL job management and coordination endpoints.",
        },
        {
            "name": "Administration",
            "description": "Administration endpoints for managing database and configurations.",
        },
        {
            "name": "Health",
            "description": "Endpoints for checking application and dependencies health.",
        },
    ]
)

# Middleware configuration (order matters - last added runs first)

# Authentication middleware
app.add_middleware(AuthenticationMiddleware)

# Rate limiting (configurable)
if not settings.DEBUG:
    app.add_middleware(RateLimitingMiddleware, max_requests=100, window_seconds=60)

# Manual CORS handler removed - using CORSMiddleware instead to avoid conflicts

# CORS configuration (FIRST - must handle preflight requests before any other middleware)
logger.info(f"🌐 CORS Origins configured: {settings.cors_origins_list}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # Use configured origins from settings
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Other middleware (after CORS)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(ClientLoggingMiddleware)  # Client-aware logging
app.add_middleware(SecurityMiddleware)
app.add_middleware(SecurityValidationMiddleware)
app.add_middleware(HealthCheckMiddleware)
from app.api.dora_routes import router as dora_router


# Include Backend Service API routes
app.include_router(health_router, prefix="/api/v1", tags=["Health"])

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication API"])
app.include_router(frontend_logs_router, prefix="/api/v1", tags=["Frontend Logs"])
app.include_router(dora_router)

app.include_router(user_router, tags=["User Preferences"])
app.include_router(admin_router, tags=["Administration"])  # admin_router already has /api/v1/admin prefix

# Include Core API routes with ML support
app.include_router(issues_router, prefix="/api/v1", tags=["Issues"])
app.include_router(pull_requests_router, prefix="/api/v1", tags=["Pull Requests"])
app.include_router(projects_router, prefix="/api/v1", tags=["Projects"])
app.include_router(users_router, prefix="/api/v1", tags=["Users"])
app.include_router(ml_monitoring_router, prefix="/api/v1", tags=["ML Monitoring"])

# Include Centralized Auth Integration routes
from app.api.centralized_auth_routes import router as centralized_auth_router
app.include_router(centralized_auth_router, prefix="/api/v1/auth/centralized", tags=["Centralized Auth"])

# Backend Service - API only, no static files or web routes


@app.get("/docs")
async def custom_docs(request: Request):
    """Custom docs endpoint that requires admin authentication."""
    try:
        # Check authentication
        token = request.cookies.get("pulse_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            return RedirectResponse(url="/login?error=authentication_required", status_code=302)

        # Verify token and check admin permissions
        from app.auth.auth_service import get_auth_service
        auth_service = get_auth_service()
        user = await auth_service.verify_token(token)

        if not user:
            return RedirectResponse(url="/login?error=invalid_token", status_code=302)

        # Check admin permission
        if not user.is_admin and user.role != 'admin':
            return RedirectResponse(url="/dashboard?error=permission_denied&resource=docs", status_code=302)

        # If admin, redirect to the actual docs
        from fastapi.openapi.docs import get_swagger_ui_html
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=app.title + " - API Documentation",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        )

    except Exception as e:
        logger.error(f"Docs access error: {e}")
        return RedirectResponse(url="/login?error=server_error", status_code=302)


# Admin route is handled by web_router - serves the admin.html template


# Debug route to check authentication status
@app.get("/debug/auth-status")
async def debug_auth_status(request: Request):
    """Debug endpoint to check authentication status."""
    # Create middleware instance to use its authentication check
    middleware = AuthenticationMiddleware(None)
    is_authenticated = await middleware.check_authentication(request)
    token_cookie = request.cookies.get("pulse_token")
    auth_header = request.headers.get("Authorization")

    return {
        "authenticated": is_authenticated,
        "has_cookie": bool(token_cookie),
        "cookie_value": token_cookie[:20] + "..." if token_cookie else None,
        "has_auth_header": bool(auth_header),
        "auth_header": auth_header[:30] + "..." if auth_header else None,
        "all_cookies": list(request.cookies.keys()),
        "user_agent": request.headers.get("User-Agent", "Unknown")
    }





# Authentication is now handled by AuthenticationMiddleware


# Backend Service - API only exception handlers

@app.exception_handler(404)
async def not_found_handler(request, _):
    """API-only 404 handler."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "detail": f"The requested resource '{request.url.path}' was not found",
            "timestamp": datetime.now().isoformat()
        }
    )


@app.exception_handler(403)
async def forbidden_handler(_request, _exc):
    """API-only 403 handler."""
    return JSONResponse(
        status_code=403,
        content={
            "error": "Forbidden",
            "detail": "You don't have permission to access this resource",
            "timestamp": datetime.now().isoformat()
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """API-only global exception handler."""
    import uuid

    # Generate error ID for tracking
    error_id = str(uuid.uuid4())[:8]

    logger.error("Unhandled exception",
                error=str(exc),
                error_id=error_id,
                path=str(request.url) if hasattr(request, 'url') else 'unknown')

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An unexpected error occurred",
            "error_id": error_id,
            "timestamp": datetime.now().isoformat()
        }
    )


async def initialize_database():
    """Initializes database connection and structure."""
    try:
        database = get_database()

        # Check connection
        if not database.is_connection_alive():
            logger.warning("Database connection not available - will retry on first use")
            return False

        # Check if tables exist, if not, create them
        if not database.check_table_exists("integrations"):
            logger.info("Creating database tables...")
            database.create_tables()
            logger.info("Database tables created - use migrations for initial data")

        logger.info("Database initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


# Backend Service - No scheduler functions needed


async def clear_all_user_sessions():
    """Clear all user sessions on startup for security."""
    # Mark all existing DB sessions inactive on startup for security
    logger.info("Marking all existing DB sessions inactive on startup for security")

    # Clear all user sessions from database (only if database is available)
    from app.core.database import get_database
    database = get_database()

    # Try to clear sessions from database, but don't fail if database is offline
    try:
        with database.get_session() as session:
            from app.models.unified_models import UserSession
            # ✅ SECURITY: Mark all existing sessions as inactive (affects all clients on startup)
            # Note: This is intentional on startup for security - all clients get fresh sessions
            session.query(UserSession).update({
                'active': False,
                'last_updated_at': datetime.now()
            })
            session.commit()

            session_count = session.query(UserSession).filter(UserSession.active == False).count()
            logger.info(f"Marked {session_count} user sessions as inactive (all clients - startup security)")

        logger.info("All existing authentication tokens have been invalidated")
    except Exception as db_error:
        logger.warning(f"Database not available - skipping user session cleanup (JWT tokens still invalidated)")
        # Continue startup even if database session cleanup fails







if __name__ == "__main__":
    # Configuration for direct execution - let uvicorn handle signals
    try:
        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG,
            log_level=settings.LOG_LEVEL.lower()
        )
    except KeyboardInterrupt:
        # This is expected during Ctrl+C - don't log it as an error
        pass
    except Exception as e:
        print(f"[ERROR] Unexpected error during server execution: {e}")



