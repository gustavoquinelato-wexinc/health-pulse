"""
Main FastAPI application for ETL Service.
Configures the application, routes, scheduling and initialization.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
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
from app.core.database import get_database
from app.core.logging_config import get_logger
from app.core.middleware import (
    ErrorHandlingMiddleware, SecurityMiddleware, SecurityValidationMiddleware,
    RateLimitingMiddleware, HealthCheckMiddleware
)
# Import new modular API routers
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.data import router as data_router
from app.api.dashboard import router as dashboard_router
from app.api.logs import router as logs_router
from app.api.debug import router as debug_router
from app.api.scheduler import router as scheduler_router

# Import legacy routers (to be deprecated)
from app.api.admin_routes import router as admin_router
from app.api.web_routes import router as web_router
# from app.api.etl_routes import router as etl_router  # DEPRECATED: Split into modular routers

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
    ## ETL Service - Jira Deep Data Extraction

    A Python ETL web application using FastAPI to perform deep data extraction from Jira,
    including development status (dev_status), and load into a Snowflake Data Warehouse.

    ### Main Features

    - **Complete Jira Extraction**: Extracts all work items (issues, epics, stories, bugs)
    - **Development Status**: Extracts associated development data (commits, pull requests)
    - **Snowflake Data Warehouse**: Loads all data into a relational model
    - **REST API**: Endpoints for managing and triggering ETL jobs
    - **Automatic Scheduling**: Jobs can be scheduled for automatic execution
    - **Monitoring**: Structured logs and performance metrics

    ### ETL Process

    1. **Issue Extraction**: Connects to Jira and fetches all issues using JQL
    2. **Processing**: Normalizes and validates extracted data
    3. **Dev Data Extraction**: For each issue, fetches development data via API
    4. **Loading**: Performs UPSERT of data into Snowflake
    5. **Monitoring**: Records metrics and process logs

    ### Authentication

    The application uses API tokens for authentication with:
    - **Jira**: Atlassian API Token
    - **Snowflake**: SSO authentication or username/password
    - **GitHub**: Token for accessing development data
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

# Middleware configuration
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(SecurityMiddleware)
app.add_middleware(SecurityValidationMiddleware)
app.add_middleware(HealthCheckMiddleware)

# Rate limiting (configurable)
if not settings.DEBUG:
    app.add_middleware(RateLimitingMiddleware, max_requests=100, window_seconds=60)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include new modular API routes
app.include_router(health_router, tags=["Health"])
app.include_router(jobs_router, tags=["Jobs"])
app.include_router(data_router, tags=["Data"])
app.include_router(logs_router, tags=["Logs"])
app.include_router(debug_router, tags=["Debug"])
app.include_router(scheduler_router, tags=["Scheduler"])

# Include dashboard routes (no prefix for web pages)
app.include_router(dashboard_router, tags=["Dashboard"])

# Include legacy routes (to be deprecated)
app.include_router(
    admin_router,
    prefix=f"{settings.API_V1_STR}/admin",
    tags=["Administration"]
)

# Include web interface routes (no prefix for web pages)
app.include_router(
    web_router,
    tags=["Web Interface"]
)

# Mount static files (if directory exists)
import os
from pathlib import Path
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """Application root endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now().isoformat(),
        "docs_url": "/docs",
        "health_check": "/health"
    }


@app.get("/favicon.ico")
async def favicon():
    """Favicon endpoint to prevent 404 errors."""
    return Response(status_code=204)  # No Content


@app.get("/admin")
async def admin_dashboard():
    """Simple admin dashboard."""
    return {
        "message": "ETL Service Admin Dashboard",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "redoc": "/redoc",
            "etl_jobs": f"{settings.API_V1_STR}/etl/",
            "admin_routes": f"{settings.API_V1_STR}/admin/"
        },
        "status": "operational"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global handler for unhandled exceptions."""
    logger.error("Unhandled exception", error=str(exc), path=str(request.url) if hasattr(request, 'url') else 'unknown')
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An unexpected error occurred",
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


if __name__ == "__main__":
    # Configuration for direct execution
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )



