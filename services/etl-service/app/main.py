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
        "/", "/login", "/health", "/healthz", "/docs", "/redoc", "/openapi.json",
        "/logout", "/auth/login", "/debug/auth-status", "/debug/clear-cookies"
    }

    # Routes that should redirect to login if not authenticated
    PROTECTED_WEB_ROUTES = {
        "/dashboard", "/admin"
    }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Debug: Print to console (temporary)
        print(f"[AUTH MIDDLEWARE] Processing: {path}")

        # Skip authentication for public routes
        if path in self.PUBLIC_ROUTES or path.startswith("/static/"):
            print(f"[AUTH MIDDLEWARE] Public route: {path}")
            return await call_next(request)

        # Skip authentication for API routes (they handle their own auth)
        if path.startswith("/api/"):
            print(f"[AUTH MIDDLEWARE] API route: {path}")
            return await call_next(request)

        # For protected web routes and unknown routes, check authentication
        print(f"[AUTH MIDDLEWARE] Checking auth for: {path}")
        is_authenticated = await self.check_authentication(request)
        print(f"[AUTH MIDDLEWARE] Auth result: {is_authenticated}")

        if not is_authenticated:
            # Determine redirect reason
            if path in self.PROTECTED_WEB_ROUTES:
                print(f"[AUTH MIDDLEWARE] Redirecting protected route: {path}")
                return RedirectResponse(url="/login?error=authentication_required", status_code=302)
            else:
                # For unknown/404 routes, redirect with page_not_found error
                print(f"[AUTH MIDDLEWARE] Redirecting unknown route: {path}")
                return RedirectResponse(url="/login?error=page_not_found", status_code=302)

        # User is authenticated, proceed with request
        print(f"[AUTH MIDDLEWARE] User authenticated, proceeding: {path}")
        return await call_next(request)

    async def check_authentication(self, request: Request) -> bool:
        """Check if user is authenticated."""
        try:
            from app.auth.auth_service import get_auth_service

            # Try to get token from cookies first
            token = request.cookies.get("pulse_token")
            print(f"[AUTH DEBUG] Cookie token: {'Found' if token else 'None'}")

            if not token:
                # Try Authorization header
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.split(" ")[1]
                    print(f"[AUTH DEBUG] Header token: Found")
                else:
                    print(f"[AUTH DEBUG] Header token: None")

            if not token:
                print(f"[AUTH DEBUG] No token found, returning False")
                return False

            # Verify token
            print(f"[AUTH DEBUG] Verifying token: {token[:20]}...")
            auth_service = get_auth_service()
            user = await auth_service.verify_token(token)
            result = user is not None
            print(f"[AUTH DEBUG] Token verification result: {result}, user: {user.email if user else 'None'}")
            return result

        except Exception as e:
            print(f"[AUTH DEBUG] Exception in auth check: {e}")
            return False


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

        # Clear any existing user sessions on startup for security
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
    docs_url="/docs",
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


# Debug route to force clear all cookies
@app.get("/debug/clear-cookies")
async def debug_clear_cookies():
    """Debug endpoint to force clear all authentication cookies."""
    response = JSONResponse(content={
        "message": "All cookies cleared with correct parameters",
        "primary_cookie": "pulse_token",
        "method": "Using exact same parameters as when cookie was set"
    })

    # Clear pulse_token by setting to empty with immediate expiration
    response.set_cookie(
        key="pulse_token",
        value="",  # Empty value
        max_age=0,  # Immediate expiration
        path="/",
        httponly=True,
        secure=False,
        samesite="lax"
    )

    # Also try delete_cookie method
    response.delete_cookie(
        key="pulse_token",
        path="/",
        httponly=True,
        secure=False,
        samesite="lax"
    )

    # Try other variations for safety
    response.delete_cookie(key="pulse_token", path="/")
    response.delete_cookie(key="pulse_token")

    # Clear other potential cookies
    other_cookies = ["session", "auth_token", "token", "jwt"]
    for cookie_name in other_cookies:
        response.delete_cookie(key=cookie_name, path="/")
        response.delete_cookie(key=cookie_name)

    # Add aggressive cache control headers
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'

    return response


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
        if not database.check_table_exists("Integrations"):
            logger.info("Creating database tables...")
            database.create_tables()

            # Insert initial data if necessary
            await insert_initial_data()

        logger.info("Database initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


async def insert_initial_data():
    """Inserts initial data into the database."""
    try:
        from app.models.unified_models import Integration
        from app.core.config import AppConfig

        database = get_database()

        with database.get_session_context() as session:
            # Check if integrations already exist
            existing_integrations = session.query(Integration).count()

            if existing_integrations == 0:
                logger.info("Inserting initial integration data...")

                key = AppConfig.load_key()

                # Create Jira integration
                jira_integration = Integration(
                    Name="Jira",
                    Url=settings.JIRA_URL,
                    Username=settings.JIRA_USERNAME,
                    Password=AppConfig.encrypt_token(settings.JIRA_TOKEN, key),
                    LastSyncAt=datetime(1900, 1, 1),
                    CreatedAt=datetime.now(),
                    LastUpdatedAt=datetime.now()
                )

                session.add(jira_integration)

                # Add other integrations if configured
                if settings.GITHUB_TOKEN:
                    github_integration = Integration(
                        Name="GitHub",
                        Url="https://api.github.com",
                        Username=None,
                        Password=AppConfig.encrypt_token(settings.GITHUB_TOKEN, key),
                        LastSyncAt=datetime(1900, 1, 1),
                        CreatedAt=datetime.now(),
                        LastUpdatedAt=datetime.now()
                    )
                    session.add(github_integration)

                # Add Aha! integration if configured
                if settings.AHA_TOKEN and settings.AHA_URL:
                    aha_integration = Integration(
                        Name="Aha!",
                        Url=settings.AHA_URL,
                        Username=None,
                        Password=AppConfig.encrypt_token(settings.AHA_TOKEN, key),
                        LastSyncAt=datetime(1900, 1, 1),
                        CreatedAt=datetime.now(),
                        LastUpdatedAt=datetime.now()
                    )
                    session.add(aha_integration)

                # Add Azure DevOps integration if configured
                if settings.AZDO_TOKEN and settings.AZDO_URL:
                    azdo_integration = Integration(
                        Name="Azure DevOps",
                        Url=settings.AZDO_URL,
                        Username=None,
                        Password=AppConfig.encrypt_token(settings.AZDO_TOKEN, key),
                        LastSyncAt=datetime(1900, 1, 1),
                        CreatedAt=datetime.now(),
                        LastUpdatedAt=datetime.now()
                    )
                    session.add(azdo_integration)

                session.commit()
                logger.info("Initial integration data inserted successfully")

    except Exception as e:
        logger.error(f"Failed to insert initial data: {e}")
        raise


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

    Args:
        interval_minutes: New interval in minutes
        enabled: Whether the orchestrator should be enabled
    """
    if not SCHEDULER_AVAILABLE or not scheduler:
        logger.warning("Scheduler not available for schedule update")
        return False

    try:
        from app.core.settings_manager import set_orchestrator_interval, set_orchestrator_enabled

        # Update database settings
        set_orchestrator_interval(interval_minutes)
        set_orchestrator_enabled(enabled)

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
            logger.info(f"Orchestrator schedule updated to run every {interval_minutes} minutes")
        else:
            logger.info("Orchestrator disabled")

        return True

    except Exception as e:
        logger.error(f"Failed to update orchestrator schedule: {e}")
        return False


async def clear_all_user_sessions():
    """Clear all user sessions on startup for security."""
    try:
        from app.auth.auth_service import get_auth_service
        auth_service = get_auth_service()

        # Invalidate all existing tokens by updating the secret key
        logger.info("Invalidating all existing JWT tokens on startup for security")

        # Force regenerate JWT secret to invalidate all existing tokens
        from app.core.config import get_settings
        settings = get_settings()

        # Update the JWT secret in memory (this invalidates all existing tokens)
        import secrets
        new_secret = secrets.token_urlsafe(32)
        settings.JWT_SECRET_KEY = new_secret

        logger.info("All existing authentication tokens have been invalidated")

    except Exception as e:
        logger.warning(f"Failed to clear user sessions: {e}")


if __name__ == "__main__":
    # Configuration for direct execution
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )



