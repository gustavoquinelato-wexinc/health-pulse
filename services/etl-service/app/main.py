"""
Main FastAPI application for ETL Service.
Configures the application, routes, scheduling and initialization.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    AsyncIOScheduler = None
    IntervalTrigger = None

from app.core.config import get_settings
from app.core.database import get_database, get_db_session
from app.core.logging_config import get_logger
from app.core.middleware import (
    ErrorHandlingMiddleware, SecurityMiddleware, SecurityValidationMiddleware,
    RateLimitingMiddleware, HealthCheckMiddleware
)
# Import new modular API routers
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.data import router as data_router

from app.api.logs import router as logs_router
from app.api.debug import router as debug_router
from app.api.scheduler import router as scheduler_router

# Import web interface routers
from app.api.admin_routes import router as admin_router
from app.api.web_routes import router as web_router
from app.api.websocket_routes import router as websocket_router

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

# Scheduler global
scheduler = AsyncIOScheduler() if SCHEDULER_AVAILABLE else None


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to handle authentication checks before route processing."""

    # Routes that don't require authentication
    PUBLIC_ROUTES = {
        "/", "/login", "/health", "/healthz", "/redoc", "/openapi.json",
        "/logout", "/auth/login", "/favicon.ico", "/.well-known/appspecific/com.chrome.devtools.json"
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

        # Skip authentication for public routes
        if (path in self.PUBLIC_ROUTES or
            path.startswith("/static/") or
            path.startswith("/.well-known/") or
            path.endswith(".ico") or
            path.endswith(".json")):
            logger.debug(f"Skipping auth for public route: {path}")
            return await call_next(request)

        # Skip authentication for API routes (they handle their own auth)
        if path.startswith("/api/"):
            return await call_next(request)

        # For protected web routes and unknown routes, check authentication
        logger.debug(f"Checking authentication for protected route: {path}")
        auth_result = await self.check_authentication_detailed(request)

        if not auth_result["authenticated"]:
            # Determine redirect reason
            is_protected_route = (
                path in self.PROTECTED_WEB_ROUTES or
                any(path.startswith(prefix) for prefix in self.PROTECTED_WEB_PREFIXES)
            )

            if is_protected_route:
                logger.debug(f"Redirecting protected route {path} to login (auth required)")
                return RedirectResponse(url="/login?error=authentication_required", status_code=302)
            else:
                # For unknown/404 routes, redirect with page_not_found error
                logger.debug(f"Redirecting unknown route {path} to login (page not found)")
                return RedirectResponse(url="/login?error=page_not_found", status_code=302)

        # User is authenticated, check if they have permission for admin routes
        if path.startswith("/admin") and not auth_result["user_data"].get("is_admin", False):
            logger.debug(f"User lacks admin permission for {path}, redirecting to dashboard")
            return RedirectResponse(url="/dashboard?error=permission_denied&resource=admin_panel", status_code=302)

        # User is authenticated, proceed with request
        return await call_next(request)

    async def check_authentication(self, request: Request) -> bool:
        """Check if user is authenticated via centralized auth service."""
        result = await self.check_authentication_detailed(request)
        return result["authenticated"]

    async def check_authentication_detailed(self, request: Request) -> dict:
        """Check authentication and return detailed result with user data."""
        try:
            from app.auth.centralized_auth_service import get_centralized_auth_service

            # Try to get token from cookies first
            token = request.cookies.get("pulse_token")

            if not token:
                # Try Authorization header
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.split(" ")[1]

            if not token:
                logger.debug(f"No token found for path: {request.url.path}")
                return {"authenticated": False, "user_data": None, "reason": "no_token"}

            logger.debug(f"Validating token for path: {request.url.path}")
            # Verify token via centralized auth service
            auth_service = get_centralized_auth_service()
            user_data = await auth_service.verify_token(token)

            if user_data:
                logger.debug(f"Token validation successful for {request.url.path}: user={user_data.get('email')}, admin={user_data.get('is_admin')}")
                return {"authenticated": True, "user_data": user_data, "reason": "success"}
            else:
                logger.debug(f"Token validation failed for {request.url.path}")
                return {"authenticated": False, "user_data": None, "reason": "invalid_token"}

        except Exception as e:
            logger.error(f"Authentication check failed for {request.url.path}: {e}")
            return {"authenticated": False, "user_data": None, "reason": "error"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Manages the application lifecycle."""
    logger.info("Starting ETL Service...")
    
    try:
        # Initialize database connection
        database_initialized = await initialize_database()
        if database_initialized:
            logger.info("Database connection established successfully")
        else:
            logger.warning("Database connection failed - service will continue with limited functionality")

        # Initialize scheduler
        await initialize_scheduler()

        # Clear all user sessions on startup for security
        # This happens regardless of DEBUG mode for consistent security behavior
        await clear_all_user_sessions()

        logger.info("ETL Service started successfully")
        yield

    except Exception as e:
        logger.error(f"Failed to start ETL Service: {e}")
        # Don't raise the exception to allow the service to start even if database is not available
        logger.warning("Service started with limited functionality - database connection failed")
        yield
    finally:
        # Cleanup
        logger.info("Shutting down ETL Service...")
        if scheduler and scheduler.running:
            scheduler.shutdown()
        
        database = get_database()
        database.close_connections()
        
        logger.info("ETL Service shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## ETL Service - Pulse Platform Data Engine

    A comprehensive FastAPI-based ETL service for extracting, transforming, and loading data
    from multiple sources including Jira, GitHub, Aha!, and Azure DevOps with intelligent
    job orchestration and checkpoint recovery.

    ### Main Features

    - **Multi-source Integration**: Jira, GitHub, Aha!, Azure DevOps
    - **Intelligent Job Orchestration**: Active/Passive model with smart scheduling
    - **Checkpoint Recovery**: Precise failure recovery with cursor-based pagination
    - **Rate Limit Handling**: Graceful API rate limit management
    - **Real-time Monitoring**: Live dashboard with job control capabilities
    - **PostgreSQL Database**: Unified data model with efficient bulk operations

    ### ETL Process

    1. **Multi-source Extraction**: Connects to configured integrations using secure tokens
    2. **Data Processing**: Normalizes and validates extracted data with quality checks
    3. **Intelligent Loading**: Performs efficient UPSERT operations with conflict resolution
    4. **Checkpoint Management**: Saves progress for resumable processing after failures
    5. **Real-time Monitoring**: Provides live updates and comprehensive logging

    ### Authentication

    The application uses encrypted API tokens for authentication with:
    - **Jira**: Atlassian API Token with user/email authentication
    - **GitHub**: Personal Access Token for repository and PR data
    - **Aha!**: API Key for product management data
    - **Azure DevOps**: Personal Access Token for work items and repositories
    """,
    lifespan=lifespan,
    docs_url=None,  # Disabled - using custom protected route
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "ETL Service Support",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    tags_metadata=[
        {
            "name": "ETL Operations",
            "description": "Main ETL operations for Jira data extraction and processing.",
        },
        {
            "name": "Administration",
            "description": "Administration endpoints for managing database and configurations.",
        },
        {
            "name": "Health Check",
            "description": "Endpoints for checking application and dependencies health.",
        },
    ]
)

# Middleware configuration (order matters - last added runs first)

# Authentication middleware (runs first)
app.add_middleware(AuthenticationMiddleware)

# CORS configuration (runs second)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (configurable)
if not settings.DEBUG:
    app.add_middleware(RateLimitingMiddleware, max_requests=100, window_seconds=60)

# Other middleware
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(SecurityMiddleware)
app.add_middleware(SecurityValidationMiddleware)
app.add_middleware(HealthCheckMiddleware)

# Include modular API routes with consistent versioning
app.include_router(health_router, prefix="/api/v1", tags=["Health"])
app.include_router(jobs_router, prefix="/api/v1", tags=["Jobs"])
app.include_router(data_router, prefix="/api/v1", tags=["Data"])
app.include_router(logs_router, prefix="/api/v1", tags=["Logs"])
app.include_router(debug_router, prefix="/api/v1", tags=["Debug"])
app.include_router(scheduler_router, prefix="/api/v1", tags=["Scheduler"])



# Include web interface routes
app.include_router(
    admin_router,
    tags=["Administration"]
)

# Include web interface routes (no prefix for web pages)
app.include_router(
    web_router,
    tags=["Web Interface"]
)

# Include WebSocket routes
app.include_router(
    websocket_router,
    tags=["WebSocket"]
)

# Mount static files (if directory exists)
import os
from pathlib import Path
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Root route is handled by web_router - redirects to login page


@app.get("/favicon.ico")
async def favicon():
    """Favicon endpoint to prevent 404 errors."""
    return Response(status_code=204)  # No Content


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
        from app.auth.centralized_auth_service import get_centralized_auth_service
        auth_service = get_centralized_auth_service()
        user_data = await auth_service.verify_token(token)

        if not user_data:
            return RedirectResponse(url="/login?error=invalid_token", status_code=302)

        # Check admin permission
        if not user_data.get('is_admin') and user_data.get('role') != 'admin':
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


# Catch-all route removed - let FastAPI handle 404s naturally
# The middleware will catch unmatched routes and redirect unauthenticated users


@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler that returns HTML page for web requests and JSON for API requests."""
    from fastapi.templating import Jinja2Templates
    from pathlib import Path

    # Check if this is an API request (starts with /api/ or has Accept: application/json)
    path = str(request.url.path)
    accept_header = request.headers.get("accept", "")

    if path.startswith("/api/") or "application/json" in accept_header:
        # Return JSON response for API requests
        return JSONResponse(
            status_code=404,
            content={
                "error": "Not Found",
                "detail": f"The requested resource '{path}' was not found",
                "timestamp": datetime.now().isoformat()
            }
        )
    else:
        # Return HTML page for web requests (authentication handled by middleware)
        templates_dir = Path(__file__).parent / "templates"
        templates = Jinja2Templates(directory=str(templates_dir))
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)


@app.exception_handler(403)
async def forbidden_handler(request, exc):
    """Custom 403 handler that returns HTML page for web requests and JSON for API requests."""
    from fastapi.templating import Jinja2Templates
    from pathlib import Path

    # Check if this is an API request
    path = str(request.url.path)
    accept_header = request.headers.get("accept", "")

    if path.startswith("/api/") or "application/json" in accept_header:
        # Return JSON response for API requests
        return JSONResponse(
            status_code=403,
            content={
                "error": "Forbidden",
                "detail": "You don't have permission to access this resource",
                "timestamp": datetime.now().isoformat()
            }
        )
    else:
        # Return HTML page for web requests (authentication handled by middleware)
        templates_dir = Path(__file__).parent / "templates"
        templates = Jinja2Templates(directory=str(templates_dir))
        return templates.TemplateResponse("403.html", {"request": request}, status_code=403)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global handler for unhandled exceptions."""
    from fastapi.templating import Jinja2Templates
    from pathlib import Path
    import uuid

    # Generate error ID for tracking
    error_id = str(uuid.uuid4())[:8]

    logger.error("Unhandled exception",
                error=str(exc),
                error_id=error_id,
                path=str(request.url) if hasattr(request, 'url') else 'unknown')

    # Check if this is an API request
    path = str(request.url.path)
    accept_header = request.headers.get("accept", "")

    if path.startswith("/api/") or "application/json" in accept_header:
        # Return JSON response for API requests
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if settings.DEBUG else "An unexpected error occurred",
                "error_id": error_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    else:
        # Return HTML page for web requests (authentication handled by middleware)
        templates_dir = Path(__file__).parent / "templates"
        templates = Jinja2Templates(directory=str(templates_dir))
        return templates.TemplateResponse("500.html", {
            "request": request,
            "error_id": error_id
        }, status_code=500)


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


async def initialize_scheduler():
    """Initializes the job scheduler with database-driven configuration."""
    if not SCHEDULER_AVAILABLE:
        logger.warning("APScheduler not available, jobs will not be scheduled automatically")
        return

    if not scheduler:
        logger.warning("Scheduler not initialized")
        return

    try:
        # Initialize default settings in database
        from app.core.settings_manager import SettingsManager, get_orchestrator_interval, is_orchestrator_enabled
        SettingsManager.initialize_default_settings()

        # Set timezone
        scheduler.configure(timezone=settings.SCHEDULER_TIMEZONE)

        # Get orchestrator interval from database
        interval_minutes = get_orchestrator_interval()
        orchestrator_enabled = is_orchestrator_enabled()

        if orchestrator_enabled:
            # Add orchestrator job with database-configured interval
            scheduler.add_job(
                func=scheduled_orchestrator,
                trigger=IntervalTrigger(minutes=interval_minutes),
                id="etl_orchestrator",
                name="ETL Job Orchestrator",
                replace_existing=True,
                max_instances=1  # Prevents simultaneous executions
            )
            logger.info(f"ETL Orchestrator scheduled to run every {interval_minutes} minutes")
        else:
            logger.info("ETL Orchestrator is disabled in settings")

        # Note: Individual jobs (Jira, GitHub) are NOT scheduled independently
        # They are only triggered by the orchestrator or manual Force Start

        # Start scheduler
        scheduler.start()

        # Initialize orchestrator scheduler helper
        from app.core.orchestrator_scheduler import get_orchestrator_scheduler
        orchestrator_scheduler = get_orchestrator_scheduler()
        orchestrator_scheduler.set_scheduler(scheduler)

        # Ensure retry settings are initialized
        from app.core.settings_manager import (
            get_orchestrator_retry_interval, is_orchestrator_retry_enabled,
            get_orchestrator_max_retry_attempts
        )
        logger.info(f"Retry settings initialized: enabled={is_orchestrator_retry_enabled()}, "
                   f"interval={get_orchestrator_retry_interval()}min, "
                   f"max_attempts={get_orchestrator_max_retry_attempts()}")

        logger.info("Scheduler initialized successfully")

    except Exception as e:
        logger.error("Scheduler initialization failed", error=str(e))
        logger.warning("Continuing without scheduler - jobs can still be triggered manually")


async def scheduled_orchestrator():
    """Scheduled orchestrator that checks for PENDING jobs every minute."""
    try:
        from app.jobs.orchestrator import run_orchestrator
        await run_orchestrator()
    except Exception as e:
        logger.error(f"Scheduled orchestrator error: {e}")


# Note: scheduled_jira_job function removed - jobs are only triggered by orchestrator or manual Force Start


def get_scheduler():
    """Returns the scheduler instance."""
    return scheduler


async def update_orchestrator_schedule(interval_minutes: int, enabled: bool = True):
    """
    Updates the orchestrator schedule dynamically without restarting the server.
    Preserves fast retry timing if currently active.

    Args:
        interval_minutes: New interval in minutes
        enabled: Whether the orchestrator should be enabled
    """
    if not SCHEDULER_AVAILABLE or not scheduler:
        logger.warning("Scheduler not available for schedule update")
        return False

    try:
        from app.core.settings_manager import set_orchestrator_interval, set_orchestrator_enabled
        from app.core.orchestrator_scheduler import get_orchestrator_scheduler

        # Update database settings first
        set_orchestrator_interval(interval_minutes)
        set_orchestrator_enabled(enabled)

        # Check if we should apply the new interval immediately
        orchestrator_scheduler = get_orchestrator_scheduler()
        should_apply = orchestrator_scheduler.should_apply_new_interval(interval_minutes, is_retry_setting=False)

        if not should_apply:
            current_countdown = orchestrator_scheduler.get_current_countdown_minutes()
            logger.info(f"Preserving current schedule - new interval ({interval_minutes} minutes) is larger than current countdown ({current_countdown:.1f} minutes)")
            logger.info(f"New interval will apply after current schedule completes")
            return True

        # Get current countdown before removing the job (for logging)
        current_countdown = orchestrator_scheduler.get_current_countdown_minutes()

        # Remove existing orchestrator job if it exists
        try:
            scheduler.remove_job('etl_orchestrator')
            logger.info("Removed existing orchestrator job")
        except:
            pass  # Job might not exist

        if enabled:
            # Add new orchestrator job with updated interval
            scheduler.add_job(
                func=scheduled_orchestrator,
                trigger=IntervalTrigger(minutes=interval_minutes),
                id="etl_orchestrator",
                name="ETL Job Orchestrator",
                replace_existing=True,
                max_instances=1
            )
            if current_countdown:
                logger.info(f"Orchestrator schedule updated to run every {interval_minutes} minutes (applied immediately - was {current_countdown:.1f}min, now {interval_minutes}min)")
            else:
                logger.info(f"Orchestrator schedule updated to run every {interval_minutes} minutes")
        else:
            logger.info("Orchestrator disabled")

        return True

    except Exception as e:
        logger.error(f"Failed to update orchestrator schedule: {e}")
        return False


async def clear_all_user_sessions():
    """
    ETL Service startup - authentication is now centralized in Backend Service.
    This function is kept for compatibility but no longer manages sessions directly.
    """
    try:
        logger.info("ETL Service startup - authentication is centralized in Backend Service")
        logger.info("Session management is handled by Backend Service, not ETL Service")

        # Test connection to Backend Service
        from app.auth.centralized_auth_service import get_centralized_auth_service
        auth_service = get_centralized_auth_service()

        # Verify we can connect to Backend Service
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{auth_service.backend_service_url}/api/v1/health")
                if response.status_code == 401:
                    logger.info("Backend Service is running and authentication is required (expected)")
                elif response.status_code == 200:
                    logger.info("Backend Service is running and accessible")
                else:
                    logger.warning(f"Backend Service returned unexpected status: {response.status_code}")
        except httpx.RequestError as e:
            logger.warning(f"Could not connect to Backend Service: {e}")
            logger.warning("ETL Service will continue but authentication may not work")

        logger.info("ETL Service authentication setup complete")

    except Exception as e:
        logger.warning(f"Failed to verify Backend Service connection: {e}")
        import traceback
        traceback.print_exc()


@app.get("/debug/token-info")
async def debug_token_info(request: Request):
    """Debug endpoint to show token information."""
    token_cookie = request.cookies.get("pulse_token")
    auth_header = request.headers.get("Authorization")

    token_info = {
        "cookie_token_present": bool(token_cookie),
        "cookie_token_preview": token_cookie[:20] + "..." if token_cookie else None,
        "header_token_present": bool(auth_header),
        "header_token_preview": auth_header[:30] + "..." if auth_header else None
    }

    if token_cookie:
        try:
            import jwt
            # Try to decode without verification to see the payload
            payload = jwt.decode(token_cookie, options={"verify_signature": False})
            token_info["token_payload"] = {
                "user_id": payload.get("user_id"),
                "email": payload.get("email"),
                "exp": payload.get("exp"),
                "iat": payload.get("iat")
            }

            # Note: JWT verification now handled by centralized auth service
            # This debug info is for legacy compatibility only
            token_info["token_verified_with_current_secret"] = False
            token_info["verification_note"] = "Using centralized auth service"

        except Exception as e:
            token_info["token_decode_error"] = str(e)

    # Check session in database via centralized auth
    if token_cookie:
        try:
            from app.auth.centralized_auth_service import get_centralized_auth_service
            auth_service = get_centralized_auth_service()
            user_data = await auth_service.verify_token(token_cookie)
            token_info["session_valid_in_database"] = user_data is not None
            if user_data:
                token_info["user_info"] = {
                    "id": user_data.get("id"),
                    "email": user_data.get("email"),
                    "active": user_data.get("active")
                }
        except Exception as e:
            token_info["session_check_error"] = str(e)

    return token_info

@app.get("/debug/force-logout")
async def debug_force_logout():
    """Debug endpoint to force complete logout."""
    response = JSONResponse(content={"message": "Force logout completed"})

    # Clear all possible cookie variations
    cookie_names = ["pulse_token", "token", "access_token", "auth_token", "session"]
    for cookie_name in cookie_names:
        response.set_cookie(
            key=cookie_name,
            value="",
            max_age=0,
            expires=0,
            path="/",
            httponly=True,
            secure=False,
            samesite="lax"
        )
        response.delete_cookie(key=cookie_name, path="/")
        response.delete_cookie(key=cookie_name)

    # Add headers to clear everything
    response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage", "executionContexts"'
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response

@app.get("/debug/jwt-info")
async def debug_jwt_info():
    """Debug endpoint to check JWT configuration."""
    import os
    from app.core.config import get_settings

    settings = get_settings()

    return {
        "jwt_secret_preview": settings.JWT_SECRET_KEY[:10] + "..." if settings.JWT_SECRET_KEY else None,
        "jwt_algorithm": settings.JWT_ALGORITHM,
        "env_jwt_secret_preview": os.environ.get('JWT_SECRET_KEY', '')[:10] + "..." if os.environ.get('JWT_SECRET_KEY') else None,
        "auth_service_type": "centralized",
        "backend_service_url": settings.BACKEND_SERVICE_URL,
        "token_expiry_minutes": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    }


if __name__ == "__main__":
    # Configuration for direct execution
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )



