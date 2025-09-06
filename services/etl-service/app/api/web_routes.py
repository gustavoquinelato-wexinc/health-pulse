"""
Web Routes for ETL Service

Provides web interface routes for the ETL service including:
- Login page
- Home page
- Authentication endpoints
- Job control endpoints
"""

from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, List
import os
from pathlib import Path
from datetime import datetime
from sqlalchemy import func, case, text
import httpx

from app.core.logging_config import get_logger
from app.core.utils import DateTimeHelper
from app.jobs.orchestrator import get_job_status, trigger_jira_sync, trigger_github_sync
from app.core.database import get_database, get_db_session
from app.models.unified_models import JobSchedule
from app.auth.centralized_auth_middleware import (
    UserData, require_authentication, require_admin_authentication,
    require_web_authentication, get_current_user_optional
)
from app.auth.centralized_auth_service import get_centralized_auth_service
from app.auth.centralized_auth import get_centralized_auth, require_centralized_auth, create_auth_redirect
from app.core.config import settings

logger = get_logger(__name__)

# Helper function to get current user's client information
async def get_user_client_info(token: str) -> dict:
    """Get current user's client information for template rendering"""
    try:
        if not token:
            return {"client_logo": None, "client_name": "Tenant"}

        # Validate token and get user data
        auth_service = get_centralized_auth_service()
        user_data = await auth_service.verify_token(token)

        if not user_data:
            return {"client_logo": None, "client_name": "Tenant"}

        # Get client information from database
        from app.core.database import get_database
        from app.models.unified_models import Tenant

        database = get_database()
        with database.get_session() as session:
            client = session.query(Tenant).filter(
                Tenant.id == user_data.get('tenant_id'),
                Tenant.active == True
            ).first()

            if client:
                # Combine assets_folder and logo_filename for the full path
                logo_path = None
                if client.assets_folder and client.logo_filename:
                    logo_path = f"{client.assets_folder}/{client.logo_filename}"

                return {
                    "client_logo": logo_path,
                    "client_name": client.name
                }

        return {"client_logo": None, "client_name": "Tenant"}

    except Exception as e:
        logger.warning(f"Failed to get client info: {e}")
        return {"client_logo": None, "client_name": "Tenant"}

# Setup templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter()

# Pydantic models
class LoginRequest(BaseModel):
    email: str
    password: str

class JobToggleRequest(BaseModel):
    active: bool


class JobExecutionParams(BaseModel):
    """Parameters for job execution modes."""
    mode: Optional[str] = "all"
    custom_query: Optional[str] = None
    target_repository: Optional[str] = None
    target_repositories: Optional[List[str]] = None
    target_projects: Optional[List[str]] = None

# Legacy function for backward compatibility - now uses proper authentication
async def verify_token(user: UserData = Depends(require_authentication)):
    """Verify JWT token - now uses proper authentication system"""
    # Return user for routes that need it, but maintain backward compatibility
    # for routes that just need authentication verification
    return user

# Web page routes
@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirect to home if authenticated, otherwise to login"""
    logger.info("[AUTH] Root route accessed - checking authentication")

    # Check if user has a valid token
    token = request.cookies.get("pulse_token")
    logger.info("[AUTH] Cookie token found", has_token=bool(token))

    if token:
        logger.info(f"Validating token: {token[:20]}...")
        try:
            # Validate token via centralized auth service
            auth_service = get_centralized_auth_service()
            user_data = await auth_service.verify_token(token)
            if user_data:
                logger.info(f"User authenticated: {user_data.get('email')} - redirecting to /home")
                # User is authenticated, redirect to home
                return RedirectResponse(url="/home")
            else:
                logger.info("[AUTH] Token validation returned no user data")
        except Exception as e:
            logger.error(f"[AUTH] Token validation failed for root route: {e}")

    # No valid token, redirect to login
    logger.info("[AUTH] No valid authentication - redirecting to /login")
    return RedirectResponse(url="/login")

# Auth callback endpoint removed - no longer needed with subdomain cookies


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve login page - redirect to home if already authenticated"""
    logger.info("[AUTH] Login page accessed - checking if user is already authenticated")

    # Check if user is already authenticated via subdomain-shared cookie
    token = request.cookies.get("pulse_token")

    # If we have a token, validate it
    if token:
        try:
            # Validate token via centralized auth service
            from app.auth.centralized_auth_service import get_centralized_auth_service
            auth_service = get_centralized_auth_service()
            user_data = await auth_service.verify_token(token)

            if user_data:
                # Check if user has admin permissions before redirecting
                if user_data.get("is_admin", False) or user_data.get("role") == "admin":
                    logger.info(f"Admin user already authenticated: {user_data.get('email')} - redirecting to /home")

                    # Set subdomain-shared cookie and redirect
                    from app.core.config import get_settings
                    settings = get_settings()

                    response = RedirectResponse(url="/home")
                    response.set_cookie(
                        key="pulse_token",
                        value=token,
                        max_age=24 * 60 * 60,  # 24 hours
                        httponly=False,  # Allow JavaScript access for API calls
                        secure=settings.COOKIE_SECURE,  # From environment variable
                        samesite=settings.COOKIE_SAMESITE,  # From environment variable
                        path="/",
                        domain=settings.COOKIE_DOMAIN  # From environment variable
                    )
                else:
                    # User is authenticated but not admin - show permission denied
                    logger.info(f"[AUTH] Non-admin user already authenticated: {user_data.get('email')} - showing permission denied")

                    # Clear the token cookie since user doesn't have permission
                    from app.core.config import get_settings
                    settings = get_settings()

                    response = templates.TemplateResponse("login.html", {
                        "request": request,
                        "error": "Access Denied: ETL Management requires administrator privileges. Please contact your system administrator for access.",
                        "backend_service_url": settings.BACKEND_SERVICE_URL,
                        "frontend_service_url": settings.FRONTEND_SERVICE_URL,
                        "cookie_domain": settings.COOKIE_DOMAIN
                    })

                    # Clear the token cookie
                    response.set_cookie(
                        key="pulse_token",
                        value="",
                        max_age=0,  # Expire immediately
                        httponly=False,
                        secure=settings.COOKIE_SECURE,
                        samesite=settings.COOKIE_SAMESITE,
                        path="/",
                        domain=settings.COOKIE_DOMAIN
                    )
                return response
        except Exception as e:
            logger.debug(f"Token validation failed on login page: {e}")

    # User not authenticated, show login page (ETL service handles its own login)
    from app.core.config import get_settings
    settings = get_settings()

    backend_url = settings.BACKEND_SERVICE_URL
    frontend_url = settings.FRONTEND_URL
    cookie_domain = settings.COOKIE_DOMAIN
    logger.info(f"Login page: passing backend_service_url = {backend_url}")

    response = templates.TemplateResponse("login.html", {
        "request": request,
        "backend_service_url": backend_url,
        "frontend_service_url": frontend_url,
        "cookie_domain": cookie_domain
    })
    # Clear any invalid cookies
    response.delete_cookie("pulse_token", path="/")
    return response

# No auth callback needed - ETL service handles its own login

# POST login handler removed - using centralized auth service instead

@router.get("/home", response_class=HTMLResponse)
async def home_page(request: Request, token: Optional[str] = None):
    """Serve home page with optional token parameter for portal embedding"""

    # Check for token in URL parameter for portal embedding
    if token:
        try:
            # Validate token via centralized auth service
            auth_service = get_centralized_auth_service()
            user_data = await auth_service.verify_token(token)
            if user_data:
                # Check if this is an embedded request (iframe)
                embedded = request.query_params.get("embedded") == "true"

                # Set cookie for subsequent requests (accessible by JavaScript for API calls)
                response = templates.TemplateResponse("home.html", {
                    "request": request,
                    "user": user_data,
                    "token": token,
                    "embedded": embedded
                })
                response.set_cookie("pulse_token", token, max_age=86400, httponly=False, path="/")
                logger.info(f"Portal embedding: Token validated for user {user_data.get('email')}")
                return response
            else:
                logger.warning("[AUTH] Portal embedding: Invalid token provided")
        except Exception as e:
            logger.error(f"[AUTH] Portal embedding: Token validation error: {e}")

    # EVENT-DRIVEN COLOR SCHEMA: Load once on page load, update via events
    from app.core.color_schema_manager import get_color_schema_manager

    color_manager = get_color_schema_manager()

    # Get auth token for backend API call (one-time on page load)
    auth_token = None
    try:
        # Try to get token from cookie or header
        auth_token = request.cookies.get("pulse_token")
        if not auth_token:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                auth_token = auth_header[7:]
    except Exception:
        pass  # No token available

    # Get color schema - use direct backend call like workflows page for consistency
    color_schema_data = {"mode": "default"}  # Default fallback

    logger.debug(f"ETL Home Route Debug: Starting color schema fetch, auth_token present: {bool(auth_token)}")

    if auth_token:
        try:
            async with httpx.AsyncTenant() as client:
                # Get color schema from backend (unified API)
                response_color = await client.get(
                    f"{settings.BACKEND_SERVICE_URL}/api/v1/admin/color-schema/unified",
                    headers={"Authorization": f"Bearer {auth_token}"}
                )

                if response_color.status_code == 200:
                    data = response_color.json()
                    if data.get("success") and data.get("color_data"):
                        # Also get user-specific theme mode from backend
                        theme_response = await client.get(
                            f"{settings.BACKEND_SERVICE_URL}/api/v1/user/theme-mode",
                            headers={"Authorization": f"Bearer {auth_token}"}
                        )

                        theme_mode = 'light'  # default
                        if theme_response.status_code == 200:
                            theme_data = theme_response.json()
                            if theme_data.get('success'):
                                theme_mode = theme_data.get('mode', 'light')

                        # Process unified color data
                        color_data = data.get("color_data", [])
                        color_schema_mode = data.get("color_schema_mode", "default")

                        logger.debug(f"ETL Web Route Debug: client_color_schema_mode={color_schema_mode}, theme_mode={theme_mode}")
                        logger.debug(f"ETL Web Route Debug: Available color combinations: {[(c.get('color_schema_mode'), c.get('theme_mode'), c.get('accessibility_level')) for c in color_data]}")

                        # CRITICAL FIX: Filter by color_schema_mode to get the correct colors
                        light_regular = next((c for c in color_data if
                                            c.get('color_schema_mode') == color_schema_mode and
                                            c.get('theme_mode') == 'light' and
                                            c.get('accessibility_level') == 'regular'), None)
                        dark_regular = next((c for c in color_data if
                                           c.get('color_schema_mode') == color_schema_mode and
                                           c.get('theme_mode') == 'dark' and
                                           c.get('accessibility_level') == 'regular'), None)

                        logger.debug(f"ETL Web Route Debug: Selected colors - light_regular: {bool(light_regular)}, dark_regular: {bool(dark_regular)}")
                        if light_regular:
                            logger.debug(f"ETL Web Route Debug: Light colors - color1: {light_regular.get('color1')}, mode: {light_regular.get('color_schema_mode')}")
                        if dark_regular:
                            logger.debug(f"ETL Web Route Debug: Dark colors - color1: {dark_regular.get('color1')}, mode: {dark_regular.get('color_schema_mode')}")

                        # Use colors based on current theme
                        current_colors = light_regular if theme_mode == 'light' else dark_regular
                        if not current_colors:
                            current_colors = light_regular or dark_regular  # fallback

                        if current_colors:
                            # Combine color schema and theme data
                            color_schema_data = {
                                "success": True,
                                "mode": data.get("color_schema_mode", "default"),
                                "colors": {
                                    "color1": current_colors.get("color1"),
                                    "color2": current_colors.get("color2"),
                                    "color3": current_colors.get("color3"),
                                    "color4": current_colors.get("color4"),
                                    "color5": current_colors.get("color5")
                                },
                                "theme": theme_mode
                            }
                            logger.debug(f"ETL Web Route Debug: Final color_schema_data - mode: {color_schema_data['mode']}, color1: {color_schema_data['colors']['color1']}")
        except Exception as e:
            logger.debug(f"Could not fetch color schema for home page: {e}")

    logger.debug(f"ETL Home Route Debug: Final color_schema_data being sent to template: {color_schema_data}")

    # Check if this is an embedded request (iframe)
    embedded = request.query_params.get("embedded") == "true"

    # Get client information for header
    auth_token = request.cookies.get("pulse_token")
    client_info = await get_user_client_info(auth_token)

    # Always serve the home page - authentication is handled by frontend checkAuth()
    # The frontend will redirect to login if the token is invalid
    return templates.TemplateResponse("home.html", {
        "request": request,
        "color_schema": color_schema_data,
        "embedded": embedded,
        "client_logo": client_info["client_logo"],
        "client_name": client_info["client_name"]
    })


@router.get("/old_dashboard", response_class=HTMLResponse)
async def old_dashboard_page(request: Request, token: Optional[str] = None):
    """Serve old dashboard page for comparison"""
    try:
        # Check for token in URL parameter first (for portal embedding)
        auth_token = token
        if not auth_token:
            auth_token = request.cookies.get("pulse_token")

        if not auth_token:
            return RedirectResponse(url="/login", status_code=302)

        # Get color schema (use default for old dashboard)
        color_schema_data = {"mode": "default"}

        # Get tenant information for header
        tenant_info = await get_user_tenant_info(auth_token)

        return templates.TemplateResponse("old_dashboard.html", {
            "request": request,
            "color_schema": color_schema_data,
            "tenant_logo": tenant_info["tenant_logo"],
            "tenant_name": tenant_info["tenant_name"]
        })

    except Exception as e:
        logger.error(f"Old dashboard page error: {e}")
        # Fallback with minimal data
        return templates.TemplateResponse("old_dashboard.html", {"request": request, "color_schema": {"mode": "default"}})


@router.get("/test_colors", response_class=HTMLResponse)
async def test_colors_page(request: Request):
    """Serve enterprise colors test page"""
    return templates.TemplateResponse("test_enterprise_colors.html", {"request": request})

@router.get("/403", response_class=HTMLResponse)
async def test_403_page(request: Request):
    """Test 403 Forbidden error page"""
    return templates.TemplateResponse("403.html", {"request": request}, status_code=403)

@router.get("/500", response_class=HTMLResponse)
async def test_500_page(request: Request):
    """Test 500 Internal Server Error page"""
    return templates.TemplateResponse("500.html", {"request": request, "error_id": "TEST-500"}, status_code=500)

@router.get("/old_admin", response_class=HTMLResponse)
async def old_admin_page(request: Request, token: Optional[str] = None):
    """Serve old admin page for comparison purposes"""
    # Check for token in URL parameter for portal embedding
    if token:
        try:
            # Validate token via centralized auth service
            auth_service = get_centralized_auth_service()
            user_data = await auth_service.verify_token(token)
            if user_data:
                # Set cookie for subsequent requests (accessible by JavaScript for API calls)
                response = templates.TemplateResponse("old_admin", {"request": request, "user": user_data, "token": token})
                response.set_cookie("pulse_token", token, max_age=86400, httponly=False, path="/")
                logger.info(f"Portal embedding: Token validated for user {user_data.get('email')}")
                return response
            else:
                logger.warning("[AUTH] Portal embedding: Invalid token provided")
        except Exception as e:
            logger.error(f"[AUTH] Portal embedding: Token validation error: {e}")

    # Check for authentication via cookie or header
    auth_token = request.cookies.get("pulse_token")
    if not auth_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:]

    if auth_token:
        auth_service = get_centralized_auth_service()
        user = await auth_service.verify_token(auth_token)

        if user:
            # If token came from URL parameter, set cookie for subsequent requests
            response = templates.TemplateResponse("old_admin.html", {"request": request, "user": user, "token": token if token else None})
            if token:  # Token came from URL parameter
                response.set_cookie("pulse_token", token, max_age=86400, httponly=False, path="/")
                logger.info(f"Portal embedding: Old admin access granted for user {user.get('email')}")
            return response

    # Fallback if no token (shouldn't happen due to middleware)
    return templates.TemplateResponse("old_admin.html", {"request": request, "user": {"email": "Unknown"}})

@router.get("/api/v1/jobs/{job_id}/details")
async def get_job_details(job_id: int, user: UserData = Depends(require_admin_authentication)):
    """Get detailed job information for the job details modal"""
    try:
        logger.info(f"Getting job details for job ID {job_id}, tenant_id: {user.tenant_id}")

        from app.core.database import get_database
        from app.models.unified_models import JobSchedule

        database = get_database()
        logger.info(f"Database connection established for job details")

        with database.get_write_session_context() as session:
            # Get job schedule details by ID and client
            logger.info(f"Querying JobSchedule for job_id={job_id}, tenant_id={user.tenant_id}")

            job_schedule = session.query(JobSchedule).filter(
                JobSchedule.id == job_id,
                JobSchedule.tenant_id == user.tenant_id
            ).first()

            if not job_schedule:
                logger.warning(f"No job schedule found for job_id {job_id} and tenant_id {user.tenant_id}")
                # Return default values instead of 404 to prevent modal errors
                return {
                    "status": "NOT_CONFIGURED",
                    "last_run_started_at": None,
                    "last_success_at": None,
                    "retry_count": 0,
                    "error_message": "Job not yet configured or run",
                    "checkpoint_data": False,  # No checkpoints for unconfigured jobs
                    "progress_percentage": 0,
                    "current_step": "Not started"
                }

            logger.info(f"Found job schedule: status={job_schedule.status}")

            # Return job details with GitHub-specific fields
            return {
                "id": job_schedule.id,
                "status": job_schedule.status,
                "active": job_schedule.active,
                "created_at": job_schedule.created_at.isoformat() if job_schedule.created_at else None,
                "last_updated_at": job_schedule.last_updated_at.isoformat() if job_schedule.last_updated_at else None,
                "last_run_started_at": job_schedule.last_run_started_at.isoformat() if job_schedule.last_run_started_at else None,
                "last_success_at": job_schedule.last_success_at.isoformat() if job_schedule.last_success_at else None,
                "retry_count": job_schedule.retry_count or 0,
                "error_message": job_schedule.error_message,
                "is_recovery_run": job_schedule.is_recovery_run or False,
                "checkpoint_data": job_schedule.has_recovery_checkpoints(),  # Boolean indicating if there are checkpoints
                "current_pr_node_id": job_schedule.current_pr_node_id,
                "last_repo_sync_checkpoint": job_schedule.last_repo_sync_checkpoint.isoformat() if job_schedule.last_repo_sync_checkpoint else None,
                "last_pr_cursor": job_schedule.last_pr_cursor,
                "last_commit_cursor": job_schedule.last_commit_cursor,
                "last_review_cursor": job_schedule.last_review_cursor,
                "last_comment_cursor": job_schedule.last_comment_cursor,
                "last_review_thread_cursor": job_schedule.last_review_thread_cursor,
                "repo_processing_queue": job_schedule.repo_processing_queue,
                "progress_percentage": 100 if job_schedule.status == 'FINISHED' else (50 if job_schedule.status == 'RUNNING' else 0),
                "current_step": job_schedule.status.replace('_', ' ').title() if job_schedule.status else "Not started"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job details for job_id {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job details for job_id {job_id}: {str(e)}"
        )

@router.get("/api/v1/jobs/Jira/summary")
async def get_jira_summary(user: UserData = Depends(require_admin_authentication)):
    """Get Jira data summary for the Jira details modal"""
    try:
        from app.core.database import get_database
        from app.models.unified_models import (
            Project, Wit, Status, WorkItem,
            WorkItemChangelog, WitPrLinks
        )
        from sqlalchemy import func, desc

        database = get_database()

        with database.get_read_session_context() as session:
            # Projects summary
            projects_total = session.query(Project).filter(Project.tenant_id == user.tenant_id).count()
            projects_active = session.query(Project).filter(
                Project.tenant_id == user.tenant_id,
                Project.active == True
            ).count()

            # WorkItem Types summary
            issuetypes_total = session.query(Wit).filter(Wit.tenant_id == user.tenant_id).count()
            issuetypes_active = session.query(Wit).filter(
                Wit.tenant_id == user.tenant_id,
                Wit.active == True
            ).count()

            # Statuses summary
            statuses_total = session.query(Status).filter(Status.tenant_id == user.tenant_id).count()
            statuses_active = session.query(Status).filter(
                Status.tenant_id == user.tenant_id,
                Status.active == True
            ).count()

            # WorkItems summary
            issues_total = session.query(WorkItem).filter(WorkItem.tenant_id == user.tenant_id).count()
            issues_active = session.query(WorkItem).filter(
                WorkItem.tenant_id == user.tenant_id,
                WorkItem.active == True
            ).count()

            # Top issue types
            top_types = session.query(
                Wit.original_name,
                func.count(WorkItem.id).label('count')
            ).join(WorkItem).filter(
                WorkItem.tenant_id == user.tenant_id,
                WorkItem.active == True
            ).group_by(Wit.original_name).order_by(desc('count')).limit(5).all()

            # Top statuses
            top_statuses = session.query(
                Status.original_name,
                func.count(WorkItem.id).label('count')
            ).join(WorkItem).filter(
                WorkItem.tenant_id == user.tenant_id,
                WorkItem.active == True
            ).group_by(Status.original_name).order_by(desc('count')).limit(10).all()

            # Changelogs summary
            changelogs_total = session.query(WorkItemChangelog).filter(WorkItemChangelog.tenant_id == user.tenant_id).count()
            changelogs_active = session.query(WorkItemChangelog).filter(
                WorkItemChangelog.tenant_id == user.tenant_id,
                WorkItemChangelog.active == True
            ).count()

            # PR Links summary
            pr_links_total = session.query(WitPrLinks).filter(WitPrLinks.tenant_id == user.tenant_id).count()
            pr_links_active = session.query(WitPrLinks).filter(
                WitPrLinks.tenant_id == user.tenant_id,
                WitPrLinks.active == True
            ).count()

            # Unique repositories count
            unique_repos = session.query(func.count(func.distinct(WitPrLinks.repo_full_name))).filter(
                WitPrLinks.tenant_id == user.tenant_id,
                WitPrLinks.active == True
            ).scalar() or 0

            return {
                "tables": {
                    "projects": {
                        "total_count": projects_total,
                        "active_count": projects_active,
                        "inactive_count": projects_total - projects_active
                    },
                    "issuetypes": {
                        "total_count": issuetypes_total,
                        "active_count": issuetypes_active,
                        "inactive_count": issuetypes_total - issuetypes_active
                    },
                    "statuses": {
                        "total_count": statuses_total,
                        "active_count": statuses_active,
                        "inactive_count": statuses_total - statuses_active
                    },
                    "issues": {
                        "total_count": issues_total,
                        "active_count": issues_active,
                        "inactive_count": issues_total - issues_active,
                        "top_types": [{"name": name, "count": count} for name, count in top_types],
                        "top_statuses": [{"name": name, "count": count} for name, count in top_statuses]
                    },
                    "changelogs": {
                        "total_count": changelogs_total,
                        "active_count": changelogs_active,
                        "recent_activity_30d": 0  # TODO: Calculate recent activity
                    },
                    "jira_pull_request_links": {
                        "total_count": pr_links_total,
                        "active_count": pr_links_active,
                        "unique_repositories": unique_repos,
                        "pr_status_breakdown": []  # TODO: Add PR status breakdown
                    }
                }
            }

    except Exception as e:
        logger.error(f"Error getting Jira summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Jira summary: {str(e)}"
        )

@router.get("/api/v1/jobs/GitHub/summary")
async def get_github_summary(user: UserData = Depends(require_admin_authentication)):
    """Get GitHub data summary for the details modal"""
    try:
        from app.core.database import get_database

        database = get_database()
        with database.get_read_session_context() as session:
            from app.models.unified_models import (
                Repository, Pr, PrReview, PrCommit, PrComment,
                JobSchedule, Integration
            )
            from sqlalchemy import func, desc

            # Get GitHub integration and job schedule
            github_integration = session.query(Integration).filter(
                Integration.tenant_id == user.tenant_id,
                Integration.provider == 'github'
            ).first()

            github_job = None
            if github_integration:
                github_job = session.query(JobSchedule).filter(
                    JobSchedule.tenant_id == user.tenant_id,
                    JobSchedule.integration_id == github_integration.id
                ).first()

            # Repositories summary
            repos_total = session.query(Repository).filter(Repository.tenant_id == user.tenant_id).count()
            repos_active = session.query(Repository).filter(
                Repository.tenant_id == user.tenant_id,
                Repository.active == True
            ).count()

            # Top 3 languages
            top_languages = session.query(
                Repository.language,
                func.count(Repository.id).label('count')
            ).filter(
                Repository.tenant_id == user.tenant_id,
                Repository.active == True,
                Repository.language.isnot(None)
            ).group_by(Repository.language).order_by(desc('count')).limit(3).all()

            # Top 3 repositories by PR count
            top_repos = session.query(
                Repository.full_name,
                func.count(Pr.id).label('pr_count')
            ).join(Pr).filter(
                Repository.tenant_id == user.tenant_id,
                Repository.active == True
            ).group_by(Repository.full_name).order_by(desc('pr_count')).limit(3).all()

            # Pull Requests summary with code statistics
            prs_total = session.query(Pr).filter(Pr.tenant_id == user.tenant_id).count()
            prs_active = session.query(Pr).filter(
                Pr.tenant_id == user.tenant_id,
                Pr.active == True
            ).count()

            # Code statistics
            code_stats = session.query(
                func.sum(Pr.additions).label('total_additions'),
                func.sum(Pr.deletions).label('total_deletions'),
                func.sum(Pr.changed_files).label('total_changed_files')
            ).filter(
                Pr.tenant_id == user.tenant_id,
                Pr.active == True
            ).first()

            # Reviews summary
            reviews_total = session.query(PrReview).filter(PrReview.tenant_id == user.tenant_id).count()
            reviews_active = session.query(PrReview).filter(
                PrReview.tenant_id == user.tenant_id,
                PrReview.active == True
            ).count()

            # Commits summary
            commits_total = session.query(PrCommit).filter(PrCommit.tenant_id == user.tenant_id).count()
            commits_active = session.query(PrCommit).filter(
                PrCommit.tenant_id == user.tenant_id,
                PrCommit.active == True
            ).count()

            # Comments summary
            comments_total = session.query(PrComment).filter(PrComment.tenant_id == user.tenant_id).count()
            comments_active = session.query(PrComment).filter(
                PrComment.tenant_id == user.tenant_id,
                PrComment.active == True
            ).count()

            # Recovery information
            recovery_info = {}
            if github_job:
                # Collect cursor values
                cursor_fields = [
                    'last_pr_cursor', 'current_pr_node_id', 'last_commit_cursor',
                    'last_review_cursor', 'last_comment_cursor', 'last_review_thread_cursor'
                ]
                cursors = {}
                has_active_cursors = False

                for field in cursor_fields:
                    value = getattr(github_job, field, None)
                    if value:
                        cursors[field] = value
                        has_active_cursors = True

                # Parse repo processing queue
                repo_queue = None
                if github_job.repo_processing_queue:
                    try:
                        import json
                        repo_queue = json.loads(github_job.repo_processing_queue)
                    except:
                        repo_queue = None

                recovery_info = {
                    "job_status": github_job.status,
                    "active": github_job.active,
                    "last_run_started_at": github_job.last_run_started_at.isoformat() if github_job.last_run_started_at else None,
                    "last_success_at": github_job.last_success_at.isoformat() if github_job.last_success_at else None,
                    "has_active_cursors": has_active_cursors,
                    "cursors": cursors,
                    "repo_processing_queue": repo_queue,
                    "error_message": getattr(github_job, 'error_message', None),
                    "retry_count": getattr(github_job, 'retry_count', 0)
                }

            return {
                "repositories": {
                    "total": repos_total,
                    "active": repos_active,
                    "inactive": repos_total - repos_active,
                    "top_languages": [{"language": lang, "count": count} for lang, count in top_languages],
                    "top_repos": [{"repo": repo, "pr_count": count} for repo, count in top_repos]
                },
                "pull_requests": {
                    "total": prs_total,
                    "active": prs_active,
                    "inactive": prs_total - prs_active,
                    "total_additions": code_stats.total_additions or 0,
                    "total_deletions": code_stats.total_deletions or 0,
                    "total_changed_files": code_stats.total_changed_files or 0
                },
                "reviews": {
                    "total": reviews_total,
                    "active": reviews_active,
                    "inactive": reviews_total - reviews_active
                },
                "commits": {
                    "total": commits_total,
                    "active": commits_active,
                    "inactive": commits_total - commits_active
                },
                "comments": {
                    "total": comments_total,
                    "active": comments_active,
                    "inactive": comments_total - comments_active
                },
                "recovery": recovery_info
            }

    except Exception as e:
        logger.error(f"Error getting GitHub summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get GitHub summary: {str(e)}"
        )

@router.get("/api/v1/logs/download/{filename}")
async def download_log_file(filename: str, token: str = None, user: UserData = Depends(require_admin_authentication)):
    """Download a specific log file"""
    try:
        import os
        from fastapi.responses import FileResponse

        # Get current client name for client-specific log files
        from app.core.config import get_settings
        settings = get_settings()
        client_name = getattr(settings, 'CLIENT_NAME', 'default').lower()

        # Validate filename to prevent directory traversal - include client-specific files
        allowed_files = [
            'etl_service.log', 'orchestrator.log',  # Legacy files
            f'etl_service_{client_name}.log', f'orchestrator_{client_name}.log',  # Tenant-specific files
            'etl_service.log.1', 'orchestrator.log.1',  # Rotated legacy files
            f'etl_service_{client_name}.log.1', f'orchestrator_{client_name}.log.1'  # Rotated client-specific files
        ]
        if filename not in allowed_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{filename}' is not allowed for download"
            )

        # Get the logs directory path
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        if not os.path.exists(logs_dir):
            logs_dir = os.path.join(os.getcwd(), 'logs')

        file_path = os.path.join(logs_dir, filename)

        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Log file '{filename}' not found"
            )

        # Return file for download using streaming response to avoid Content-Length issues
        from fastapi.responses import StreamingResponse
        import os

        def file_generator():
            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(8192)  # Read in 8KB chunks
                    if not chunk:
                        break
                    yield chunk

        file_size = os.path.getsize(file_path)

        return StreamingResponse(
            file_generator(),
            media_type='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Length': str(file_size)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading log file {filename}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download log file: {str(e)}"
        )





@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, token: Optional[str] = None):
    """Serve admin panel page with optional token parameter for portal embedding"""
    try:
        # Check for token in URL parameter first (for portal embedding)
        auth_token = token
        if not auth_token:
            # Fall back to cookie or header
            auth_token = request.cookies.get("pulse_token")
            if not auth_token:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    auth_token = auth_header.split(" ")[1]

        if auth_token:
            auth_service = get_centralized_auth_service()
            user = await auth_service.verify_token(auth_token)

            if user:
                # Check if this is an embedded request (iframe)
                embedded = request.query_params.get("embedded") == "true"

                # If token came from URL parameter, set cookie for subsequent requests
                response = templates.TemplateResponse("admin.html", {
                    "request": request,
                    "user": user,
                    "token": token if token else None,
                    "embedded": embedded
                })
                if token:  # Token came from URL parameter
                    response.set_cookie("pulse_token", token, max_age=86400, httponly=False, path="/")
                    logger.info(f"Portal embedding: Admin access granted for user {user.get('email')}")
                return response

        # Check if this is an embedded request (iframe)
        embedded = request.query_params.get("embedded") == "true"

        # Fallback if no token (shouldn't happen due to middleware)
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "user": {"email": "Unknown"},
            "embedded": embedded
        })

    except Exception as e:
        logger.error(f"Admin page error: {e}")
        # Check if this is an embedded request (iframe)
        embedded = request.query_params.get("embedded") == "true"

        # Fallback with minimal user data
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "user": {"email": "Unknown"},
            "embedded": embedded
        })


@router.get("/status-mappings", response_class=HTMLResponse)
async def status_mappings_page(request: Request, token: Optional[str] = None):
    """Serve status mappings management page with optional token parameter for portal embedding"""
    try:
        # Check for token in URL parameter first (for portal embedding)
        auth_token = token
        if not auth_token:
            # Fall back to cookie or header
            auth_token = request.cookies.get("pulse_token")
            if not auth_token:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    auth_token = auth_header.split(" ")[1]

        # Get user info
        auth_service = get_centralized_auth_service()
        user = await auth_service.verify_token(auth_token) if auth_token else None

        # Check admin permission - simplified since we're using centralized auth
        if not user or not user.get("is_admin", False):
            return RedirectResponse(url="/home?error=permission_denied&resource=admin_panel", status_code=302)

        # Try to get color schema for authenticated users to prevent flash
        color_schema_data = None
        try:
            if auth_token:
                # Fetch color schema from backend
                import httpx
                from app.core.config import get_settings
                settings = get_settings()

                async with httpx.AsyncTenant() as client:
                    response_color = await client.get(
                        f"{settings.BACKEND_SERVICE_URL}/api/v1/admin/color-schema/unified",
                        headers={"Authorization": f"Bearer {auth_token}"}
                    )
                    if response_color.status_code == 200:
                        data = response_color.json()
                        if data.get("success") and data.get("color_data"):
                            # Also get user-specific theme mode from backend
                            theme_response = await client.get(
                                f"{settings.BACKEND_SERVICE_URL}/api/v1/user/theme-mode",
                                headers={"Authorization": f"Bearer {auth_token}"}
                            )

                            theme_mode = 'light'  # default
                            if theme_response.status_code == 200:
                                theme_data = theme_response.json()
                                if theme_data.get('success'):
                                    theme_mode = theme_data.get('mode', 'light')

                            # Process unified color data
                            color_data = data.get("color_data", [])
                            color_schema_mode = data.get("color_schema_mode", "default")

                            # CRITICAL FIX: Filter by color_schema_mode to get the correct colors
                            light_regular = next((c for c in color_data if
                                                c.get('color_schema_mode') == color_schema_mode and
                                                c.get('theme_mode') == 'light' and
                                                c.get('accessibility_level') == 'regular'), None)
                            dark_regular = next((c for c in color_data if
                                               c.get('color_schema_mode') == color_schema_mode and
                                               c.get('theme_mode') == 'dark' and
                                               c.get('accessibility_level') == 'regular'), None)

                            # Use colors based on current theme
                            current_colors = light_regular if theme_mode == 'light' else dark_regular
                            if not current_colors:
                                current_colors = light_regular or dark_regular  # fallback

                            if current_colors:
                                # Combine color schema and theme data
                                color_schema_data = {
                                    "success": True,
                                    "mode": data.get("color_schema_mode", "default"),
                                    "colors": {
                                        "color1": current_colors.get("color1"),
                                        "color2": current_colors.get("color2"),
                                        "color3": current_colors.get("color3"),
                                        "color4": current_colors.get("color4"),
                                        "color5": current_colors.get("color5")
                                    },
                                    "theme": theme_mode
                                }
        except Exception as e:
            logger.debug(f"Could not fetch color schema: {e}")

        # Check if this is an embedded request (iframe)
        embedded = request.query_params.get("embedded") == "true"

        # Create response and set cookie if token came from URL parameter
        response = templates.TemplateResponse("status_mappings.html", {
            "request": request,
            "user": user,
            "color_schema": color_schema_data,
            "embedded": embedded
        })
        if token:  # Token came from URL parameter
            response.set_cookie("pulse_token", token, max_age=86400, httponly=True, path="/")
            logger.info(f"Portal embedding: Status mappings access granted for user {user.get('email')}")
        return response

    except Exception as e:
        logger.error(f"Status mappings page error: {e}")
        return RedirectResponse(url="/login?error=server_error", status_code=302)


@router.get("/issuetype-mappings", response_class=HTMLResponse)
async def issuetype_mappings_page(request: Request):
    """Serve issue type mappings management page"""
    try:
        # Get user from token (middleware ensures we're authenticated)
        token = request.cookies.get("pulse_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        # Get user info
        auth_service = get_centralized_auth_service()
        user = await auth_service.verify_token(token)

        # Check admin permission - simplified since we're using centralized auth
        if not user or not user.get("is_admin", False):
            return RedirectResponse(url="/home?error=permission_denied&resource=admin_panel", status_code=302)

        # Try to get color schema for authenticated users to prevent flash
        color_schema_data = None
        try:
            if token:
                # Fetch color schema from backend
                import httpx
                from app.core.config import get_settings
                settings = get_settings()

                async with httpx.AsyncTenant() as client:
                    response_color = await client.get(
                        f"{settings.BACKEND_SERVICE_URL}/api/v1/admin/color-schema/unified",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    if response_color.status_code == 200:
                        data = response_color.json()
                        if data.get("success"):
                            # Also get user-specific theme mode from backend
                            theme_response = await client.get(
                                f"{settings.BACKEND_SERVICE_URL}/api/v1/user/theme-mode",
                                headers={"Authorization": f"Bearer {token}"}
                            )

                            theme_mode = 'light'  # default
                            if theme_response.status_code == 200:
                                theme_data = theme_response.json()
                                if theme_data.get('success'):
                                    theme_mode = theme_data.get('mode', 'light')

                            # Combine color schema and theme data
                            color_schema_data = {
                                "success": True,
                                "mode": data.get("mode", "default"),
                                "colors": data.get("colors", {}),
                                "theme": theme_mode
                            }
        except Exception as e:
            logger.debug(f"Could not fetch color schema: {e}")

        # Check if this is an embedded request (iframe)
        embedded = request.query_params.get("embedded") == "true"

        return templates.TemplateResponse("issuetype_mappings.html", {
            "request": request,
            "user": user,
            "color_schema": color_schema_data,
            "embedded": embedded
        })

    except Exception as e:
        logger.error(f"WorkItem type mappings page error: {e}")
        return RedirectResponse(url="/login?error=server_error", status_code=302)


@router.get("/issuetype-hierarchies", response_class=HTMLResponse)
async def issuetype_hierarchies_page(request: Request):
    """Serve issue type hierarchies management page (flow steps management)"""
    try:
        # Get user from token (middleware ensures we're authenticated)
        token = request.cookies.get("pulse_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        # Get user info
        auth_service = get_centralized_auth_service()
        user = await auth_service.verify_token(token)

        # Check admin permission - simplified since we're using centralized auth
        if not user or not user.get("is_admin", False):
            return RedirectResponse(url="/home?error=permission_denied&resource=admin_panel", status_code=302)

        # Get color schema - use direct backend call for consistency with other pages
        color_schema_data = {"mode": "default"}  # Default fallback

        if token:
            try:
                async with httpx.AsyncTenant() as client:
                    # Get color schema from backend (unified API)
                    response_color = await client.get(
                        f"{settings.BACKEND_SERVICE_URL}/api/v1/admin/color-schema/unified",
                        headers={"Authorization": f"Bearer {token}"}
                    )

                    if response_color.status_code == 200:
                        data = response_color.json()
                        if data.get("success") and data.get("color_data"):
                            # Also get user-specific theme mode from backend
                            theme_response = await client.get(
                                f"{settings.BACKEND_SERVICE_URL}/api/v1/user/theme-mode",
                                headers={"Authorization": f"Bearer {token}"}
                            )

                            theme_mode = 'light'  # default
                            if theme_response.status_code == 200:
                                theme_data = theme_response.json()
                                if theme_data.get('success'):
                                    theme_mode = theme_data.get('mode', 'light')

                            # Process unified color data
                            color_data = data.get("color_data", [])
                            color_schema_mode = data.get("color_schema_mode", "default")

                            # CRITICAL FIX: Filter by color_schema_mode to get the correct colors
                            current_colors = next((c for c in color_data if
                                                 c.get('color_schema_mode') == color_schema_mode and
                                                 c.get('theme_mode') == theme_mode and
                                                 c.get('accessibility_level') == 'regular'), None)
                            if not current_colors:
                                current_colors = next((c for c in color_data if
                                                     c.get('color_schema_mode') == color_schema_mode and
                                                     c.get('accessibility_level') == 'regular'), None)

                            if current_colors:
                                # Combine color schema and theme data
                                color_schema_data = {
                                    "success": True,
                                    "mode": data.get("color_schema_mode", "default"),
                                    "colors": {
                                        "color1": current_colors.get("color1"),
                                        "color2": current_colors.get("color2"),
                                        "color3": current_colors.get("color3"),
                                        "color4": current_colors.get("color4"),
                                        "color5": current_colors.get("color5")
                                    },
                                    "theme": theme_mode
                                }
            except Exception as e:
                logger.debug(f"Could not fetch color schema for issuetype hierarchies: {e}")

        # Check if this is an embedded request (iframe)
        embedded = request.query_params.get("embedded") == "true"

        return templates.TemplateResponse("issuetype_hierarchies.html", {
            "request": request,
            "user": user,
            "color_schema": color_schema_data,
            "embedded": embedded
        })

    except Exception as e:
        logger.error(f"WorkItem type hierarchies page error: {e}")
        return RedirectResponse(url="/login?error=server_error", status_code=302)


@router.get("/workflows", response_class=HTMLResponse)
async def workflows_page(request: Request):
    """Serve workflows management page"""
    try:
        # Get user from token (middleware ensures we're authenticated)
        token = request.cookies.get("pulse_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        # Get user info
        auth_service = get_centralized_auth_service()
        user = await auth_service.verify_token(token)

        # Check admin permission - simplified since we're using centralized auth
        if not user or not user.get("is_admin", False):
            return RedirectResponse(url="/home?error=permission_denied&resource=admin_panel", status_code=302)

        # Try to get color schema for authenticated users to prevent flash
        color_schema_data = None
        try:
            if token:
                # Fetch color schema from backend
                import httpx
                from app.core.config import get_settings
                settings = get_settings()

                async with httpx.AsyncTenant() as client:
                    response_color = await client.get(
                        f"{settings.BACKEND_SERVICE_URL}/api/v1/admin/color-schema/unified",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    if response_color.status_code == 200:
                        data = response_color.json()
                        if data.get("success") and data.get("color_data"):
                            # Also get user-specific theme mode from backend
                            theme_response = await client.get(
                                f"{settings.BACKEND_SERVICE_URL}/api/v1/user/theme-mode",
                                headers={"Authorization": f"Bearer {token}"}
                            )

                            theme_mode = 'light'  # default
                            if theme_response.status_code == 200:
                                theme_data = theme_response.json()
                                if theme_data.get('success'):
                                    theme_mode = theme_data.get('mode', 'light')

                            # Process unified color data
                            color_data = data.get("color_data", [])
                            color_schema_mode = data.get("color_schema_mode", "default")

                            # CRITICAL FIX: Filter by color_schema_mode to get the correct colors
                            current_colors = next((c for c in color_data if
                                                 c.get('color_schema_mode') == color_schema_mode and
                                                 c.get('theme_mode') == theme_mode and
                                                 c.get('accessibility_level') == 'regular'), None)
                            if not current_colors:
                                current_colors = next((c for c in color_data if
                                                     c.get('color_schema_mode') == color_schema_mode and
                                                     c.get('accessibility_level') == 'regular'), None)

                            if current_colors:
                                # Combine color schema and theme data
                                color_schema_data = {
                                    "success": True,
                                    "mode": data.get("color_schema_mode", "default"),
                                    "colors": {
                                        "color1": current_colors.get("color1"),
                                        "color2": current_colors.get("color2"),
                                        "color3": current_colors.get("color3"),
                                        "color4": current_colors.get("color4"),
                                        "color5": current_colors.get("color5")
                                    },
                                    "theme": theme_mode
                                }
        except Exception as e:
            logger.debug(f"Could not fetch color schema: {e}")

        # Check if this is an embedded request (iframe)
        embedded = request.query_params.get("embedded") == "true"

        # Get client information for header
        client_info = await get_user_client_info(token)

        return templates.TemplateResponse("workflows.html", {
            "request": request,
            "user": user,
            "color_schema": color_schema_data,
            "embedded": embedded,
            "client_logo": client_info["client_logo"],
            "client_name": client_info["client_name"]
        })

    except Exception as e:
        logger.error(f"Workflows page error: {e}")
        return RedirectResponse(url="/login?error=server_error", status_code=302)


@router.get("/logout", response_class=HTMLResponse)
async def logout_page(request: Request):
    """Handle web logout - invalidate session and clear all cookies"""

    logger.info("=== LOGOUT PROCESS STARTED ===")

    # First, invalidate the token on the server side
    try:
        token = request.cookies.get("pulse_token")
        if token:
            logger.info(f"Found token during logout: {token[:20]}...")

            # Invalidate session using centralized auth service
            try:
                logger.info("Attempting to invalidate session in Backend Service...")
                from app.auth.centralized_auth_service import get_centralized_auth_service
                auth_service = get_centralized_auth_service()
                success = await auth_service.invalidate_session(token)
                if success:
                    logger.info("Session invalidated successfully in Backend Service")
                else:
                    logger.warning("Failed to invalidate session in Backend Service")
            except Exception as e:
                logger.error(f"Error invalidating session: {e}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
        else:
            logger.info("No token found in cookies during logout")
    except Exception as e:
        logger.warning(f"Error during logout token handling: {e}")

    logger.info("Creating logout response with comprehensive cleanup...")

    # Create an HTML response that clears localStorage and cache before redirecting
    cleanup_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Logging out...</title>
        <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
        <meta http-equiv="Pragma" content="no-cache">
        <meta http-equiv="Expires" content="0">
    </head>
    <body>
        <div style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif;">
            <h2>Logging out...</h2>
            <p>Please wait while we clear your session data.</p>
        </div>
        <script>
            // Clear all localStorage
            try {
                localStorage.clear();
            } catch (e) {
                // Silently handle localStorage clearing errors
            }

            // Clear all sessionStorage
            try {
                sessionStorage.clear();
            } catch (e) {
                // Silently handle sessionStorage clearing errors
            }

            // Clear specific auth-related items
            const authKeys = ['pulse_token', 'pulse_user', 'colorScheme', 'theme'];
            authKeys.forEach(key => {
                try {
                    localStorage.removeItem(key);
                    sessionStorage.removeItem(key);
                } catch (e) {
                    // Silently handle key removal errors
                }
            });

            // Clear browser cache for auth-related requests
            if ('caches' in window) {
                caches.keys().then(names => {
                    names.forEach(name => {
                        if (name.includes('auth') || name.includes('api') || name.includes('etl')) {
                            caches.delete(name);
                        }
                    });
                }).catch(e => {
                    // Silently handle cache clearing errors
                });
            }

            // Clear all cookies via JavaScript (in addition to server-side clearing)
            document.cookie.split(";").forEach(cookie => {
                const eqPos = cookie.indexOf("=");
                const name = eqPos > -1 ? cookie.substr(0, eqPos).trim() : cookie.trim();
                // Clear cookie for current domain and path
                document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/";
                document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=" + window.location.hostname;
                document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=." + window.location.hostname;
            });

            // Try to notify frontend service about logout (cross-service coordination)
            try {
                const frontendUrl = 'http://localhost:3000'; // Frontend service URL
                // Use postMessage to communicate with frontend if it's open in another tab
                if (window.opener) {
                    window.opener.postMessage({ type: 'LOGOUT_FROM_ETL' }, frontendUrl);
                }

                // Also try to clear frontend localStorage if same origin
                if (window.location.hostname === 'localhost') {
                    // This will only work if both services are on the same domain
                    try {
                        window.localStorage.clear();
                        window.sessionStorage.clear();
                    } catch (e) {
                        // Silently handle cross-origin storage clearing errors
                    }
                }
            } catch (e) {
                // Silently handle cross-service coordination errors
            }

            // Redirect after cleanup
            setTimeout(() => {
                window.location.href = '/login';
            }, 1000);
        </script>
    </body>
    </html>
    """

    response = HTMLResponse(content=cleanup_html, status_code=200)

    # Clear the pulse_token cookie by setting it to empty with immediate expiration
    logger.info("Clearing pulse_token cookie by setting to empty with immediate expiration...")
    response.set_cookie(
        key="pulse_token",
        value="",  # Empty value
        max_age=0,  # Immediate expiration
        path="/",
        httponly=True,
        secure=False,
        samesite="lax"
    )

    # Also try the traditional delete_cookie method
    logger.info("Also trying delete_cookie method...")
    response.delete_cookie(
        key="pulse_token",
        path="/",
        httponly=True,
        secure=False,
        samesite="lax"
    )

    # Try alternative delete methods for safety
    logger.info("Trying alternative delete methods...")
    response.delete_cookie(key="pulse_token", path="/")
    response.delete_cookie(key="pulse_token")

    # Clear other potential auth cookies
    other_cookies = ["session", "auth_token", "token", "jwt", "pulse_user"]
    for cookie_name in other_cookies:
        response.delete_cookie(key=cookie_name, path="/")
        response.delete_cookie(key=cookie_name)

    logger.info("=== LOGOUT PROCESS COMPLETED ===")
    logger.info(f"Returning cleanup HTML with redirect to: /login")

    # Add aggressive cache control headers
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'

    return response


@router.post("/api/logout", response_class=JSONResponse)
async def api_logout(request: Request):
    """API endpoint for cross-service logout - clears session without redirect"""

    logger.info("=== API LOGOUT PROCESS STARTED ===")

    # Invalidate the token on the server side
    try:
        token = request.cookies.get("pulse_token")
        if token:
            logger.info(f"Found token during API logout: {token[:20]}...")

            # Invalidate session using centralized auth service
            try:
                logger.info("Attempting to invalidate session in Backend Service...")
                from app.auth.centralized_auth_service import get_centralized_auth_service
                auth_service = get_centralized_auth_service()
                success = await auth_service.invalidate_session(token)
                if success:
                    logger.info("[AUTH] Session invalidated successfully in Backend Service")
                else:
                    logger.warning("[AUTH] Failed to invalidate session in Backend Service")
            except Exception as e:
                logger.error(f"[AUTH] Error invalidating session: {e}")
        else:
            logger.info("No token found in cookies during API logout")
    except Exception as e:
        logger.warning(f"Error during API logout token handling: {e}")

    logger.info("Creating API logout response...")
    response = JSONResponse(content={"message": "Logout successful", "success": True})

    # Clear all cookies
    response.delete_cookie(key="pulse_token", path="/")
    response.delete_cookie(key="pulse_token")

    other_cookies = ["session", "auth_token", "token", "jwt", "pulse_user"]
    for cookie_name in other_cookies:
        response.delete_cookie(key=cookie_name, path="/")
        response.delete_cookie(key=cookie_name)

    # Add cache control headers
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    logger.info("=== API LOGOUT PROCESS COMPLETED ===")
    return response


# Navigation endpoint for cross-service authentication
@router.post("/auth/navigate")
async def navigate_with_token(request: Request):
    """Handle navigation from frontend with token authentication."""
    logger.info("ETL Navigation endpoint called!")
    try:
        # Handle both form data and JSON
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            data = await request.json()
            token = data.get("token")
            return_url = data.get("return_url")
        else:
            # Handle form data
            form_data = await request.form()
            token = form_data.get("token")
            return_url = form_data.get("return_url")

        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token is required"
            )

        # Debug: Check token format
        logger.info(f"Navigation token received: {token[:30]}... (length: {len(token)})")

        # Validate token via centralized auth service
        auth_service = get_centralized_auth_service()
        user_data = await auth_service.verify_token(token)

        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )

        # Create a database session for this token to ensure subsequent requests work
        # This is needed because backend startup clears all sessions
        session_created = await auth_service.ensure_session_exists(token, user_data)
        if session_created:
            logger.info(f"Navigation session ensured for user: {user_data['email']}")
        else:
            logger.warning(f"Failed to ensure session for user: {user_data['email']}")

        logger.info(f"Navigation successful for user: {user_data['email']}")

        # Create response with session cookie
        if "application/json" in content_type:
            # JSON request - return redirect URL
            response = JSONResponse({
                "success": True,
                "redirect_url": "/home",
                "message": "Authentication successful"
            })
        else:
            # Form request - direct redirect
            response = RedirectResponse(url="/home", status_code=302)

        # Set subdomain-shared session cookie for ETL service
        from app.core.config import get_settings
        settings = get_settings()

        response.set_cookie(
            key="pulse_token",
            value=token,
            max_age=24 * 60 * 60,  # 24 hours (match JWT expiry)
            httponly=False,  # Allow JavaScript access for API calls
            secure=settings.COOKIE_SECURE,  # From environment variable
            samesite=settings.COOKIE_SAMESITE,  # From environment variable
            path="/",
            domain=settings.COOKIE_DOMAIN  # From environment variable
        )

        # Store return URL in cookie for later use
        if return_url:
            response.set_cookie(
                key="return_url",
                value=return_url,
                max_age=3600,
                httponly=False,  # Allow JavaScript access for return navigation
                secure=False,
                samesite="lax",
                path="/"
            )

        logger.info(f"Navigation successful for user: {user_data.get('email')}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Navigation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Navigation failed"
        )


# Authentication API routes - Now redirected to Backend Service
@router.post("/auth/login")
async def login_redirect():
    """Redirect login requests to Backend Service"""
    from app.core.config import get_settings
    settings = get_settings()
    backend_url = settings.BACKEND_SERVICE_URL

    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail=f"Authentication is now handled by Backend Service. Please use: {backend_url}/auth/login",
        headers={"Location": f"{backend_url}/auth/login"}
    )


@router.post("/auth/logout")
async def logout_redirect():
    """Redirect logout requests to Backend Service"""
    from app.core.config import get_settings
    settings = get_settings()
    backend_url = settings.BACKEND_SERVICE_URL

    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail=f"Authentication is now handled by Backend Service. Please use: {backend_url}/auth/logout",
        headers={"Location": f"{backend_url}/auth/logout"}
    )


@router.get("/api/v1/auth/validate")
async def validate_token(user: UserData = Depends(require_authentication)):
    """Validate JWT token via centralized auth - returns 200 if valid, 401 if invalid"""
    try:
        # If we reach here, the token is valid (require_authentication succeeded)
        return {
            "valid": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
                "is_admin": user.is_admin,
                "active": user.active
            },
            "expires_in_hours": 24  # Let frontend know when token expires
        }
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


@router.post("/api/v1/auth/refresh")
async def refresh_token_redirect():
    """Redirect token refresh requests to Backend Service"""
    from app.core.config import get_settings
    settings = get_settings()
    backend_url = settings.BACKEND_SERVICE_URL

    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail=f"Authentication is now handled by Backend Service. Please use: {backend_url}/api/v1/auth/refresh",
        headers={"Location": f"{backend_url}/api/v1/auth/refresh"}
    )


# Job management API routes
@router.get("/api/v1/jobs/{job_name}/schedule-details")
async def get_job_schedule_details(job_name: str, user: UserData = Depends(require_admin_authentication)):
    """Get detailed job schedule information for a specific job"""
    try:
        from app.core.database import get_database
        from app.models.unified_models import JobSchedule
        from sqlalchemy.orm import Session

        database = get_database()

        with database.get_read_session_context() as session:
            # SECURITY: Filter job schedule by tenant_id
            job_schedule = session.query(JobSchedule).filter(
                JobSchedule.job_name == job_name,
                JobSchedule.tenant_id == user.tenant_id
            ).first()

            if not job_schedule:
                raise HTTPException(status_code=404, detail=f"Job schedule not found for {job_name}")

            # Convert to dict with all available fields
            schedule_details = {
                'id': job_schedule.id,
                'job_name': job_schedule.job_name,
                'status': job_schedule.status,
                'last_run_started_at': job_schedule.last_run_started_at.isoformat() if job_schedule.last_run_started_at else None,
                'last_success_at': job_schedule.last_success_at.isoformat() if job_schedule.last_success_at else None,
                'created_at': job_schedule.created_at.isoformat() if job_schedule.created_at else None,
                'last_updated_at': job_schedule.last_updated_at.isoformat() if job_schedule.last_updated_at else None,
                'error_message': job_schedule.error_message,
                'retry_count': job_schedule.retry_count,
                'active': job_schedule.active,

                # Checkpoint data (actual fields from model)
                'last_repo_sync_checkpoint': job_schedule.last_repo_sync_checkpoint.isoformat() if job_schedule.last_repo_sync_checkpoint else None,
                'repo_processing_queue': job_schedule.repo_processing_queue,
                'last_pr_cursor': job_schedule.last_pr_cursor,
                'current_pr_node_id': job_schedule.current_pr_node_id,
                'last_commit_cursor': job_schedule.last_commit_cursor,
                'last_review_cursor': job_schedule.last_review_cursor,
                'last_comment_cursor': job_schedule.last_comment_cursor,
                'last_review_thread_cursor': job_schedule.last_review_thread_cursor,

                # Additional computed fields
                'is_recovery_run': job_schedule.is_recovery_run(),
                'checkpoint_state': job_schedule.get_checkpoint_state()
            }

            return schedule_details

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job schedule details for {job_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job schedule details: {str(e)}")

# Simple cache for GitHub rate limits
_github_rate_limits_cache = {}

@router.get("/api/v1/github/rate-limits")
async def get_github_rate_limits(user: UserData = Depends(require_admin_authentication)):
    """Get current GitHub API rate limits with caching"""
    try:
        from app.core.database import get_database
        from app.models.unified_models import Integration
        from app.core.config import AppConfig
        import requests
        from datetime import datetime, timedelta

        # Check cache first (2-minute TTL)
        cache_key = "rate_limits"
        if cache_key in _github_rate_limits_cache:
            cached_data, cached_time = _github_rate_limits_cache[cache_key]
            if datetime.now() - cached_time < timedelta(minutes=2):
                logger.debug("Returning cached GitHub rate limits")
                return cached_data

        database = get_database()

        with database.get_read_session_context() as session:
            # Get GitHub integration for the authenticated user's client
            github_integration = session.query(Integration).filter(
                func.upper(Integration.provider) == 'GITHUB',
                Integration.tenant_id == user.tenant_id
            ).first()

            if not github_integration:
                raise HTTPException(status_code=404, detail=f"GitHub integration not found for client {user.tenant_id}")

            # Decrypt GitHub token
            key = AppConfig.load_key()
            github_token = AppConfig.decrypt_token(github_integration.password, key)

            # Make request to GitHub rate limit endpoint
            headers = {
                'Authorization': f'token {github_token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'ETL-Service/1.0'
            }

            # Make request with timeout to prevent hanging
            response = requests.get(
                'https://api.github.com/rate_limit',
                headers=headers,
                timeout=5  # 5 second timeout
            )

            if not response.ok:
                raise HTTPException(status_code=response.status_code, detail=f"GitHub API error: {response.text}")

            rate_limit_data = response.json()

            # Extract only the required rate limits (core, search, graphql)
            filtered_data = {
                'core': rate_limit_data['resources']['core'],
                'search': rate_limit_data['resources']['search'],
                'graphql': rate_limit_data['resources']['graphql'],
                'timestamp': rate_limit_data.get('rate', {}).get('reset', None)
            }

            # Cache the result
            _github_rate_limits_cache[cache_key] = (filtered_data, datetime.now())

            return filtered_data

    except requests.exceptions.Timeout:
        logger.warning("GitHub rate limits request timed out")
        raise HTTPException(status_code=408, detail="GitHub API request timed out")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting GitHub rate limits: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get GitHub rate limits: {str(e)}")





@router.get("/api/v1/jobs/status")
async def get_jobs_status(user: UserData = Depends(verify_token)):
    """Get current status of all jobs with optimized queries"""
    try:
        # SECURITY: Get job status filtered by tenant_id
        status_data = get_job_status(tenant_id=user.tenant_id)

        # Enhance with checkpoint data using optimized query
        database = get_database()
        with database.get_read_session_context() as session:
            # SECURITY: Get job objects filtered by tenant_id (include all jobs)
            jobs = session.query(JobSchedule).filter(
                JobSchedule.tenant_id == user.tenant_id
            ).all()

            for job in jobs:
                if job.job_name in status_data:
                    # Add checkpoint data efficiently using the model method
                    status_data[job.job_name]['checkpoint_data'] = job.get_checkpoint_state()
                    status_data[job.job_name]['active'] = job.active

        # Ensure consistent ordering: Jira first, then GitHub
        ordered_jobs = {}
        job_order = ['jira_sync', 'github_sync']

        for job_name in job_order:
            if job_name in status_data:
                ordered_jobs[job_name] = status_data[job_name]

        # Add any other jobs that might exist (for future extensibility)
        for job_name, job_data in status_data.items():
            if job_name not in ordered_jobs:
                ordered_jobs[job_name] = job_data

        # Wrap in jobs object for consistent API format
        return {"jobs": ordered_jobs}
        
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job status"
        )


@router.get("/api/home-status")
async def get_home_status_api(user: UserData = Depends(require_admin_authentication)):
    """Get comprehensive home page status for modern interface"""
    try:
        # Get job status
        job_status = get_job_status(tenant_id=user.tenant_id)

        # Calculate system health
        system_status = "Healthy"
        active_jobs = 0
        completed_today = 0

        for job_name, job_data in job_status.items():
            if job_data.get('status') == 'RUNNING':
                active_jobs += 1
            elif job_data.get('status') == 'ERROR':
                system_status = "Warning"

        # Get next run time (simplified)
        next_run = None
        try:
            db = get_database()
            with get_db_session(db) as session:
                next_schedule = session.query(JobSchedule).filter(
                    JobSchedule.is_active == True
                ).first()
                if next_schedule:
                    next_run = next_schedule.next_run.isoformat() if next_schedule.next_run else None
        except Exception as e:
            logger.warning(f"Could not get next run time: {e}")

        return {
            "system_status": {"status": system_status},
            "job_summary": {
                "active": active_jobs,
                "completed_today": completed_today
            },
            "jobs": job_status,
            "next_run": next_run,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting home status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get home status")


@router.get("/api/v1/user/color-schema")
async def get_user_color_schema(request: Request, user: UserData = Depends(require_web_authentication)):
    """Get user's color schema settings using event-driven smart caching"""
    from app.core.color_schema_manager import get_color_schema_manager

    color_manager = get_color_schema_manager()

    # Get auth token
    auth_token = None
    try:
        auth_token = request.cookies.get("pulse_token")
        if not auth_token:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                auth_token = auth_header[7:]
    except Exception:
        pass

    # Get color schema with smart caching (no auto-refresh, only event-driven updates)
    user_id = str(user.id) if user and hasattr(user, 'id') else "default"
    return await color_manager.get_color_schema(auth_token, user_id)


@router.get("/api/v1/debug/color-schema-cache")
async def get_color_schema_cache_status(user: UserData = Depends(require_web_authentication)):
    """Debug endpoint to check color schema cache status"""
    from app.core.color_schema_manager import get_color_schema_manager

    color_manager = get_color_schema_manager()
    user_id = str(user.id) if user and hasattr(user, 'id') else "default"
    cache_info = color_manager.get_cache_info(user_id)

    return {
        "success": True,
        "cache_info": cache_info,
        "timestamp": DateTimeHelper.now_utc().isoformat()
    }


# Internal API Endpoints for Backend Service Communication
@router.post("/api/v1/internal/color-schema-changed")
async def handle_color_schema_change(request: Request):
    """Internal endpoint: Handle color schema change notification from backend"""
    try:
        data = await request.json()
        tenant_id = data.get("tenant_id")
        colors = data.get("colors", {})
        event_type = data.get("event_type", "color_update")

        logger.info(f"[COLOR] Received color schema change notification for tenant {tenant_id}")
        logger.debug(f"Colors: {colors}")

        # Invalidate color schema cache to force refresh
        from app.core.color_schema_manager import get_color_schema_manager
        color_manager = get_color_schema_manager()
        color_manager.invalidate_cache()

        # Broadcast to connected WebSocket clients for real-time updates
        from app.core.websocket_manager import get_websocket_manager
        websocket_manager = get_websocket_manager()

        # Send color update to all connected clients for this tenant_id
        from datetime import datetime
        await websocket_manager.broadcast_to_client(tenant_id, {
            "type": "color_schema_updated",
            "colors": colors,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat()
        })

        logger.info(f"Color schema cache invalidated and clients notified for client {tenant_id}")

        return {
            "success": True,
            "message": "Color schema change processed successfully",
            "tenant_id": tenant_id
        }

    except Exception as e:
        logger.error(f"[COLOR] Error processing color schema change: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/api/v1/internal/color-schema-mode-changed")
async def handle_color_schema_mode_change(request: Request):
    """Internal endpoint: Handle color schema mode change notification from backend"""
    try:
        data = await request.json()
        tenant_id = data.get("tenant_id")
        mode = data.get("mode")

        logger.info(f"Color schema mode change notification received for client {tenant_id}: {mode}")

        # Invalidate color schema cache to force refresh on next page load
        from app.core.color_schema_manager import get_color_schema_manager
        color_manager = get_color_schema_manager()
        color_manager.invalidate_cache()

        logger.info(f"Color schema cache invalidated for client {tenant_id}")

        return {
            "success": True,
            "message": "Color schema mode change processed successfully",
            "tenant_id": tenant_id,
            "mode": mode
        }

    except Exception as e:
        logger.error(f"[COLOR] Error processing color schema mode change: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/api/v1/internal/user-theme-changed")
async def handle_user_theme_change(request: Request):
    """Internal endpoint: Handle user theme change notification from backend"""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        theme_mode = data.get("theme_mode")

        logger.info(f"User theme change notification received for user {user_id}: {theme_mode}")

        # Invalidate user-specific color schema cache to force refresh on next page load
        from app.core.color_schema_manager import get_color_schema_manager
        color_manager = get_color_schema_manager()
        color_manager.invalidate_cache(str(user_id))

        logger.info(f"Color schema cache invalidated for user {user_id}")

        return {
            "success": True,
            "message": "User theme change processed successfully",
            "user_id": user_id,
            "theme_mode": theme_mode
        }

    except Exception as e:
        logger.error(f"[COLOR] Error processing user theme change: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/api/v1/jobs/{job_name}/start")
async def start_job(
    job_name: str,
    execution_params: Optional[JobExecutionParams] = None,
    user: UserData = Depends(require_admin_authentication)
):
    """Force start a specific job with optional execution parameters"""
    try:
        valid_jobs = ['Jira', 'GitHub', 'WEX Fabric', 'WEX AD']
        if job_name not in valid_jobs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid job name. Must be one of: {', '.join(valid_jobs)}"
            )
        
        # Log execution parameters
        if execution_params:
            logger.info(f"Force starting job {job_name} in MANUAL MODE with parameters: {execution_params.dict()}")
        else:
            logger.info(f"Force starting job {job_name} in MANUAL MODE (default parameters)")

        # SECURITY: Use client-aware trigger functions with user's tenant_id
        # Run in background to avoid blocking the web request
        import asyncio
        job_name_lower = job_name.lower()
        if job_name_lower == 'jira':
            asyncio.create_task(trigger_jira_sync(
                force_manual=True,
                execution_params=execution_params,
                tenant_id=user.tenant_id
            ))
            result = {
                'status': 'triggered',
                'message': f'Jira sync job triggered successfully for client {user.tenant_id}',
                'job_name': job_name
            }
        elif job_name_lower == 'github':
            asyncio.create_task(trigger_github_sync(
                force_manual=True,
                execution_params=execution_params,
                tenant_id=user.tenant_id
            ))
            result = {
                'status': 'triggered',
                'message': f'GitHub sync job triggered successfully for client {user.tenant_id}',
                'job_name': job_name
            }
        elif job_name_lower == 'wex fabric':
            from app.jobs.orchestrator import trigger_fabric_sync
            asyncio.create_task(trigger_fabric_sync(
                force_manual=True,
                execution_params=execution_params,
                tenant_id=user.tenant_id
            ))
            result = {
                'status': 'triggered',
                'message': f'WEX Fabric sync job triggered successfully for client {user.tenant_id}',
                'job_name': job_name
            }
        elif job_name_lower == 'wex ad':
            from app.jobs.orchestrator import trigger_ad_sync
            asyncio.create_task(trigger_ad_sync(
                force_manual=True,
                execution_params=execution_params,
                tenant_id=user.tenant_id
            ))
            result = {
                'status': 'triggered',
                'message': f'WEX AD sync job triggered successfully for client {user.tenant_id}',
                'job_name': job_name
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job name"
            )

        # Return the result from the trigger function
        if result.get('status') == 'success':
            return {
                "success": True,
                "message": f"Job {job_name} completed successfully",
                "job_id": result.get('job_id'),
                "result": result
            }
        else:
            return {
                "success": False,
                "message": f"Job {job_name} failed: {result.get('message', 'Unknown error')}",
                "job_id": result.get('job_id'),
                "result": result
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting job {job_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start job {job_name}"
        )

@router.post("/api/v1/jobs/{job_name}/stop")
async def stop_job(job_name: str, user: UserData = Depends(require_admin_authentication)):
    """Force stop a specific job - requires admin privileges"""
    try:
        if job_name not in ['Jira', 'GitHub']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job name"
            )

        from app.core.job_manager import get_job_manager
        job_manager = get_job_manager()

        # Check if job is actually running
        if not job_manager.is_job_running(job_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job {job_name} is not currently running"
            )

        # Request cancellation
        cancelled = job_manager.request_cancellation(job_name)

        if cancelled:
            # Also update database status
            database = get_database()
            with database.get_write_session_context() as session:
                job = session.query(JobSchedule).filter(
                    JobSchedule.job_name == job_name,
                    JobSchedule.active == True
                ).first()

                if job and job.status == 'RUNNING':
                    job.status = 'PENDING'
                    job.error_message = 'Job cancelled by user request'
                    session.commit()

            logger.info(f"Job {job_name} cancellation requested by user {user.email}")

            return {
                "success": True,
                "message": f"Cancellation requested for job {job_name}",
                "note": "Job will stop at the next safe checkpoint"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to request cancellation for job {job_name}"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping job {job_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop job {job_name}"
        )





@router.get("/api/v1/jobs/status")
async def get_jobs_status(user: UserData = Depends(require_admin_authentication)):
    """Get status of all jobs including running state"""
    try:
        from app.core.job_manager import get_job_manager
        job_manager = get_job_manager()

        database = get_database()
        with database.get_read_session_context() as session:
            # Single optimized query for both jobs
            jobs = session.query(
                JobSchedule.job_name,
                JobSchedule.id,
                JobSchedule.status,
                JobSchedule.last_success_at,
                JobSchedule.error_message,
                JobSchedule.retry_count
            ).filter(
                JobSchedule.job_name.in_(['Jira', 'GitHub']),
                JobSchedule.active == True
            ).all()

            # Create a lookup dict for faster access
            job_lookup = {job.job_name: job for job in jobs}
            jobs_status = {}

            for job_name in ['Jira', 'GitHub']:
                if job_name in job_lookup:
                    job = job_lookup[job_name]
                    is_running = job.status == 'RUNNING'

                    jobs_status[job_name] = {
                        'id': str(job.id),
                        'status': job.status,
                        'is_running': is_running,
                        'can_stop': False,  # Force stop removed
                        'last_success_at': job.last_success_at.isoformat() if job.last_success_at else None,
                        'error_message': job.error_message,
                        'retry_count': job.retry_count
                    }
                else:
                    jobs_status[job_name] = {
                        'id': None,
                        'status': 'NOT_FOUND',
                        'is_running': False,
                        'can_stop': False,
                        'last_success_at': None,
                        'error_message': None,
                        'retry_count': 0
                    }

            return {
                "success": True,
                "jobs": jobs_status,
                "running_jobs": job_manager.get_running_jobs()
            }

    except Exception as e:
        logger.error(f"Error getting jobs status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get jobs status"
        )


@router.post("/api/v1/jobs/{job_name}/toggle")
async def toggle_job_active(job_name: str, request: JobToggleRequest, user: UserData = Depends(require_admin_authentication)):
    """Toggle job active/inactive status - requires admin privileges"""
    try:
        if job_name not in ['Jira', 'GitHub']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job name"
            )
        
        database = get_database()
        with database.get_write_session_context() as session:
            job = session.query(JobSchedule).filter(JobSchedule.job_name == job_name).first()
            
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            job.active = request.active
            session.commit()
            
            action = "activated" if request.active else "deactivated"
            logger.info(f"Job {job_name} {action}")
            
            return {
                "success": True,
                "message": f"Job {job_name} {action} successfully",
                "active": job.active
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling job {job_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle job {job_name}"
        )


@router.post("/api/v1/jobs/{job_id}/pause")
async def pause_job(job_id: int, user: UserData = Depends(require_admin_authentication)):
    """Pause a specific job by ID"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Get the specific job to pause by ID and client
            job_to_pause = session.query(JobSchedule).filter(
                JobSchedule.id == job_id,
                JobSchedule.tenant_id == user.tenant_id,
                JobSchedule.active == True
            ).first()

            if not job_to_pause:
                logger.error(f"[PAUSE] Job ID {job_id} not found or not active for client {user.tenant_id}")
                raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found")

            job_name = job_to_pause.job_name
            logger.info(f"[PAUSE] Job {job_name} (ID: {job_id}) found - Status: {job_to_pause.status}, Active: {job_to_pause.active}, Tenant: {job_to_pause.tenant_id}")

            if job_to_pause.status == 'PAUSED':
                logger.info(f"[PAUSE] Job {job_name} (ID: {job_id}) is already paused")
                return {"message": f"Job {job_name} is already paused", "status": "paused"}

            if job_to_pause.status == 'RUNNING':
                logger.warning(f"[PAUSE] Cannot pause job {job_name} (ID: {job_id}) while it's running")
                raise HTTPException(status_code=400, detail=f"Cannot pause job {job_name} while it's running")

            # Pause the job
            old_status = job_to_pause.status
            job_to_pause.set_paused()
            session.commit()

            logger.info(f"[PAUSE] Job {job_name} (ID: {job_id}) paused successfully: {old_status} -> PAUSED")

            return {
                "message": f"Job {job_name} paused successfully",
                "status": "paused",
                "job_id": job_id
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause job {job_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to pause job {job_name}"
        )


@router.post("/api/v1/jobs/{job_id}/unpause")
async def unpause_job(job_id: int, user: UserData = Depends(require_admin_authentication)):
    """Unpause a specific job by ID"""
    try:
        database = get_database()
        with database.get_write_session_context() as session:
            # Get the specific job to unpause by ID and client
            job_to_unpause = session.query(JobSchedule).filter(
                JobSchedule.id == job_id,
                JobSchedule.tenant_id == user.tenant_id,
                JobSchedule.active == True
            ).first()

            if not job_to_unpause:
                logger.error(f"[UNPAUSE] Job ID {job_id} not found for client {user.tenant_id}")
                raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found")

            job_name = job_to_unpause.job_name

            logger.info(f"[UNPAUSE] Job {job_name} (ID: {job_id}) current status: {job_to_unpause.status}")

            if job_to_unpause.status != 'PAUSED':
                logger.info(f"[UNPAUSE] Job {job_name} (ID: {job_id}) is not paused (status: {job_to_unpause.status})")
                return {"message": f"Job {job_name} is not paused", "status": job_to_unpause.status.lower()}

            # Simplified unpause: Set job to NOT_STARTED (ready to run)
            old_status = job_to_unpause.status
            job_to_unpause.status = 'NOT_STARTED'
            session.commit()

            logger.info(f"[UNPAUSE] Job {job_name} (ID: {job_id}) unpaused successfully: {old_status} -> NOT_STARTED")

            return {
                "message": f"Job {job_name} unpaused successfully",
                "status": "not_started",
                "job_id": job_id,
                "old_status": old_status,
                "new_status": "NOT_STARTED"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unpause job {job_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to unpause job {job_name}"
        )


# Orchestrator Control Endpoints
@router.post("/api/v1/orchestrator/start")
async def force_start_orchestrator(user: UserData = Depends(require_admin_authentication)):
    """Force start the orchestrator to check for PENDING jobs for this ETL instance's client only"""
    try:
        # Use simple_orchestrator for single-client ETL instance
        from app.main import simple_orchestrator

        # Run orchestrator in background
        import asyncio
        asyncio.create_task(simple_orchestrator())

        logger.info("Orchestrator manually triggered")

        return {
            "success": True,
            "message": "Orchestrator started successfully"
        }

    except Exception as e:
        logger.error(f"Error starting orchestrator: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start orchestrator"
        )


@router.post("/api/v1/orchestrator/pause")
async def pause_orchestrator(user: UserData = Depends(require_admin_authentication)):
    """Pause the scheduled orchestrator"""
    try:
        from app.main import scheduler

        # Pause the orchestrator job
        scheduler.pause_job('etl_orchestrator')

        logger.info("Orchestrator paused")

        return {
            "success": True,
            "message": "Orchestrator paused successfully"
        }

    except Exception as e:
        logger.error(f"Error pausing orchestrator: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause orchestrator"
        )


@router.post("/api/v1/orchestrator/resume")
async def resume_orchestrator(user: UserData = Depends(require_admin_authentication)):
    """Resume the scheduled orchestrator - requires admin privileges"""
    try:
        from app.main import scheduler

        # Resume the orchestrator job
        scheduler.resume_job('etl_orchestrator')

        logger.info("Orchestrator resumed")

        return {
            "success": True,
            "message": "Orchestrator resumed successfully"
        }

    except Exception as e:
        logger.error(f"Error resuming orchestrator: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resume orchestrator"
        )


@router.post("/api/v1/jobs/{job_id}/set-active")
async def set_job_active(job_id: int, user: UserData = Depends(require_admin_authentication)):
    """Set a specific job as active (PENDING) - simplified to only affect target job"""
    try:

        database = get_database()
        with database.get_write_session_context() as session:
            # Get the specific job by ID and client
            target_job = session.query(JobSchedule).filter(
                JobSchedule.id == job_id,
                JobSchedule.tenant_id == user.tenant_id,
                JobSchedule.active == True
            ).first()

            if not target_job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job ID {job_id} not found for client {user.tenant_id}"
                )

            job_name = target_job.job_name

            # Log if target job is already PENDING (but continue to reset other jobs)
            if target_job.status == 'PENDING':
                logger.info(f"[FORCE_PENDING] Job {job_name} (ID: {job_id}) is already PENDING, but will still reset other active jobs")

            # Check if target job is currently RUNNING
            if target_job.status == 'RUNNING':
                logger.warning(f"[FORCE_PENDING] Cannot set {job_name} (ID: {job_id}) to PENDING while it's RUNNING")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot set {job_name} to PENDING while it's RUNNING"
                )

            # Set other active, non-paused jobs to NOT_STARTED
            other_jobs = session.query(JobSchedule).filter(
                JobSchedule.tenant_id == user.tenant_id,
                JobSchedule.active == True,
                JobSchedule.id != job_id,  # Exclude the target job
                JobSchedule.status.notin_(['PAUSED'])  # Don't affect paused jobs
            ).all()

            logger.info(f"[FORCE_PENDING] Found {len(other_jobs)} other active, non-paused jobs to potentially reset")

            jobs_reset = []
            for other_job in other_jobs:
                if other_job.status != 'NOT_STARTED':
                    old_other_status = other_job.status
                    other_job.status = 'NOT_STARTED'
                    other_job.error_message = None  # Clear any previous errors
                    jobs_reset.append(f"{other_job.job_name} ({old_other_status} -> NOT_STARTED)")
                    logger.info(f"[FORCE_PENDING] Reset job {other_job.job_name} (ID: {other_job.id}): {old_other_status} -> NOT_STARTED")

            # Set target job to PENDING
            old_status = target_job.status
            target_job.status = 'PENDING'
            target_job.error_message = None  # Clear any previous errors

            # Commit all changes
            session.commit()

            logger.info(f"[FORCE_PENDING] Job {job_name} (ID: {job_id}) set to PENDING: {old_status} -> PENDING")
            if jobs_reset:
                logger.info(f"[FORCE_PENDING] Reset {len(jobs_reset)} other jobs: {', '.join(jobs_reset)}")
            else:
                logger.info(f"[FORCE_PENDING] No other jobs were reset")

            # Create success message
            if old_status == 'PENDING':
                message = f"Job {job_name} was already active and ready to run"
            else:
                message = f"Job {job_name} is now active and ready to run"

            if jobs_reset:
                message += f" (reset {len(jobs_reset)} other jobs to NOT_STARTED)"

            return {
                "success": True,
                "message": message,
                "job_id": job_id,
                "job_name": job_name,
                "old_status": old_status,
                "new_status": "PENDING",
                "jobs_reset": len(jobs_reset)
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting job ID {job_id} as active: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set job ID {job_id} as active"
        )


@router.get("/api/v1/orchestrator/status")
async def get_orchestrator_status(user: UserData = Depends(require_admin_authentication)):
    """Get orchestrator status"""
    try:
        # Import required modules (reduced logging for frequent calls)
        from app.main import scheduler
        from app.core.settings_manager import (
            get_orchestrator_interval, is_orchestrator_enabled,
            is_orchestrator_retry_enabled, get_orchestrator_retry_interval,
            get_orchestrator_max_retry_attempts
        )
        from app.core.orchestrator_scheduler import get_orchestrator_scheduler

        # Get orchestrator job status (simple single-client approach)
        if scheduler is None:
            logger.error("Scheduler is None!")
            return {
                "status": "scheduler_not_available",
                "next_run": None,
                "message": "Scheduler is not initialized",
                "interval_minutes": get_orchestrator_interval(),
                "enabled": is_orchestrator_enabled(),
                "fast_retry_active": False,
                "retry_config": {
                    "enabled": is_orchestrator_retry_enabled(),
                    "interval_minutes": get_orchestrator_retry_interval(),
                    "max_attempts": get_orchestrator_max_retry_attempts()
                },
                "retry_status": {
                    "retry_enabled": is_orchestrator_retry_enabled(),
                    "retry_interval_minutes": get_orchestrator_retry_interval(),
                    "max_attempts": get_orchestrator_max_retry_attempts(),
                    "jobs": {}
                }
            }

        job = scheduler.get_job("etl_orchestrator")
        logger.info(f"Got job: {job}")

        if not job:
            return {
                "status": "not_scheduled",
                "next_run": None,
                "message": "Orchestrator is not scheduled",
                "interval_minutes": get_orchestrator_interval(),
                "enabled": is_orchestrator_enabled(),
                "fast_retry_active": False,
                "retry_config": {
                    "enabled": is_orchestrator_retry_enabled(),
                    "interval_minutes": get_orchestrator_retry_interval(),
                    "max_attempts": get_orchestrator_max_retry_attempts()
                },
                "retry_status": {
                    "retry_enabled": is_orchestrator_retry_enabled(),
                    "retry_interval_minutes": get_orchestrator_retry_interval(),
                    "max_attempts": get_orchestrator_max_retry_attempts(),
                    "jobs": {}
                }
            }

        # Check if job is paused
        is_paused = job.next_run_time is None

        # Get retry status (system-wide for now)
        try:
            orchestrator_scheduler = get_orchestrator_scheduler()
            if orchestrator_scheduler:
                retry_status = orchestrator_scheduler.get_all_retry_status()
                fast_retry_active = orchestrator_scheduler.is_fast_retry_active()
            else:
                logger.warning("Orchestrator scheduler is None")
                retry_status = {
                    "retry_enabled": is_orchestrator_retry_enabled(),
                    "retry_interval_minutes": get_orchestrator_retry_interval(),
                    "max_attempts": get_orchestrator_max_retry_attempts(),
                    "jobs": {}
                }
                fast_retry_active = False
        except Exception as e:
            logger.error(f"Error getting orchestrator scheduler status: {e}")
            retry_status = {
                "retry_enabled": is_orchestrator_retry_enabled(),
                "retry_interval_minutes": get_orchestrator_retry_interval(),
                "max_attempts": get_orchestrator_max_retry_attempts(),
                "jobs": {}
            }
            fast_retry_active = False

        # Check if any jobs are currently running to determine countdown visibility
        from app.jobs.orchestrator import get_job_status
        job_status = get_job_status(tenant_id=user.tenant_id)
        any_job_running = any(job_data.get('status') == 'RUNNING' for job_data in job_status.values())

        # Simplified orchestrator status - no status, just countdown control
        if is_paused:
            orchestrator_status = "paused"
            status_message = "Orchestrator is paused"
            show_countdown = False
        else:
            orchestrator_status = "active"
            status_message = "Orchestrator"
            show_countdown = not any_job_running  # Hide countdown when jobs are running

        status_info = {
            "status": orchestrator_status,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "job_id": job.id,
            "name": job.name,
            "message": status_message,
            "show_countdown": show_countdown,
            "any_job_running": any_job_running,
            "interval_minutes": get_orchestrator_interval(),
            "enabled": is_orchestrator_enabled(),
            "fast_retry_active": fast_retry_active,
            "retry_config": {
                "enabled": is_orchestrator_retry_enabled(),
                "interval_minutes": get_orchestrator_retry_interval(),
                "max_attempts": get_orchestrator_max_retry_attempts()
            },
            "retry_status": retry_status
        }

        return status_info

    except Exception as e:
        logger.error(f"Error getting orchestrator status: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get orchestrator status"
        )


@router.post("/api/v1/orchestrator/reinitialize")
async def reinitialize_orchestrator(user: UserData = Depends(require_admin_authentication)):
    """Reinitialize orchestrator schedule (useful after database reset) - requires admin privileges"""
    try:
        logger.info("Reinitializing orchestrator schedule...")

        from app.main import update_orchestrator_schedule
        from app.core.settings_manager import get_orchestrator_interval, is_orchestrator_enabled

        # Get current settings from database
        interval_minutes = get_orchestrator_interval(user.tenant_id)
        enabled = is_orchestrator_enabled(user.tenant_id)

        # Force update the orchestrator schedule
        success = update_orchestrator_schedule(interval_minutes, enabled)

        if success:
            logger.info(f"Orchestrator reinitialized successfully: interval={interval_minutes}min, enabled={enabled}")
            return {
                "success": True,
                "message": f"Orchestrator reinitialized with {interval_minutes} minute interval",
                "interval_minutes": interval_minutes,
                "enabled": enabled
            }
        else:
            logger.error("Failed to reinitialize orchestrator")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reinitialize orchestrator"
            )

    except Exception as e:
        logger.error(f"Error reinitializing orchestrator: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reinitialize orchestrator: {str(e)}"
        )


@router.post("/api/v1/orchestrator/schedule")
async def update_orchestrator_schedule(
    request: dict,
    user: UserData = Depends(require_admin_authentication)
):
    """Update orchestrator schedule interval - requires admin privileges"""
    try:
        interval_minutes = request.get('interval_minutes')
        enabled = request.get('enabled', True)

        if not interval_minutes or interval_minutes < 1 or interval_minutes > 1440:  # Max 24 hours
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interval must be between 1 and 1440 minutes"
            )

        from app.main import update_orchestrator_schedule
        success = await update_orchestrator_schedule(interval_minutes, enabled)

        if success:
            logger.info(f"Orchestrator schedule updated: {interval_minutes} minutes, enabled: {enabled}")
            return {
                "success": True,
                "message": f"Orchestrator schedule updated to {interval_minutes} minutes",
                "interval_minutes": interval_minutes,
                "enabled": enabled
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update orchestrator schedule"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating orchestrator schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update orchestrator schedule"
        )


@router.post("/api/v1/orchestrator/retry")
async def update_orchestrator_retry_config(
    request: dict,
    user: UserData = Depends(require_admin_authentication)
):
    """Update orchestrator retry configuration - requires admin privileges"""
    try:
        retry_enabled = request.get('enabled')
        retry_interval = request.get('interval_minutes')
        max_attempts = request.get('max_attempts')

        # Validate inputs
        if retry_interval is not None and (retry_interval < 1 or retry_interval > 60):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Retry interval must be between 1 and 60 minutes"
            )

        if max_attempts is not None and (max_attempts < 1 or max_attempts > 10):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Max attempts must be between 1 and 10"
            )

        from app.core.settings_manager import (
            set_orchestrator_retry_enabled, set_orchestrator_retry_interval,
            set_orchestrator_max_retry_attempts
        )
        from app.core.orchestrator_scheduler import get_orchestrator_scheduler

        # Check if fast retry is currently active
        orchestrator_scheduler = get_orchestrator_scheduler()
        if orchestrator_scheduler:
            fast_retry_active = orchestrator_scheduler.is_fast_retry_active()
            current_countdown = orchestrator_scheduler.get_current_countdown_minutes()
        else:
            fast_retry_active = False
            current_countdown = None

        # Update settings
        updates = {}
        schedule_updated = False

        if retry_enabled is not None:
            set_orchestrator_retry_enabled(retry_enabled)
            updates['enabled'] = retry_enabled

        if retry_interval is not None:
            set_orchestrator_retry_interval(retry_interval)
            updates['interval_minutes'] = retry_interval

            # Check if we should apply the new retry interval immediately
            if fast_retry_active and orchestrator_scheduler:
                schedule_updated = orchestrator_scheduler.apply_new_retry_interval_if_smaller(retry_interval)

        if max_attempts is not None:
            set_orchestrator_max_retry_attempts(max_attempts)
            updates['max_attempts'] = max_attempts

        logger.info(f"Orchestrator retry configuration updated: {updates}")

        # Build appropriate message based on what happened
        message = "Orchestrator retry configuration updated successfully"
        if fast_retry_active and retry_interval is not None:
            if schedule_updated:
                message += f" (new retry interval applied immediately - was {current_countdown:.1f}min, now {retry_interval}min)"
            else:
                message += f" (current fast retry preserved - {current_countdown:.1f}min remaining, new interval will apply to future attempts)"
        elif fast_retry_active:
            message += " (current fast retry preserved - changes will apply to future retry attempts)"

        return {
            "success": True,
            "message": message,
            "updates": updates,
            "fast_retry_active": fast_retry_active,
            "schedule_updated": schedule_updated,
            "current_countdown_minutes": current_countdown
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating orchestrator retry configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update orchestrator retry configuration"
        )


@router.get("/api/v1/settings")
async def get_system_settings(user: UserData = Depends(require_admin_authentication)):
    """Get all system settings"""
    try:
        from app.core.settings_manager import SettingsManager
        settings = SettingsManager.get_all_settings()

        return {
            "success": True,
            "settings": settings
        }

    except Exception as e:
        logger.error(f"Error getting system settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system settings"
        )


@router.post("/api/v1/settings")
async def update_system_setting(
    request: dict,
    user: UserData = Depends(require_admin_authentication)
):
    """Update a system setting - requires admin privileges"""
    try:
        setting_key = request.get('setting_key')
        setting_value = request.get('setting_value')
        description = request.get('description')

        if not setting_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Setting key is required"
            )

        from app.core.settings_manager import SettingsManager
        # SECURITY: Pass tenant_id for client-specific settings
        success = SettingsManager.set_setting(setting_key, setting_value, description, tenant_id=user.tenant_id)

        if success:
            # If orchestrator setting was updated, refresh the schedule
            if setting_key in ['orchestrator_interval_minutes', 'orchestrator_enabled']:
                from app.core.settings_manager import get_orchestrator_interval, is_orchestrator_enabled
                from app.main import update_orchestrator_schedule

                interval = get_orchestrator_interval()
                enabled = is_orchestrator_enabled()
                await update_orchestrator_schedule(interval, enabled)
            elif setting_key == 'orchestrator_retry_interval_minutes':
                # For retry interval changes, check if we should apply immediately
                from app.core.orchestrator_scheduler import get_orchestrator_scheduler
                orchestrator_scheduler = get_orchestrator_scheduler()

                if orchestrator_scheduler and orchestrator_scheduler.is_fast_retry_active():
                    schedule_updated = orchestrator_scheduler.apply_new_retry_interval_if_smaller(int(setting_value))
                    if schedule_updated:
                        logger.info(f"Retry interval updated to {setting_value} minutes and applied immediately (was smaller than current countdown)")
                    else:
                        logger.info(f"Retry interval updated to {setting_value} minutes - current fast retry preserved (new interval will apply to future attempts)")
                else:
                    logger.info(f"Retry interval updated to {setting_value} minutes - will apply to future retry attempts")
            elif setting_key in ['orchestrator_retry_enabled', 'orchestrator_max_retry_attempts']:
                # For other retry settings, just log the change - no need to update schedule
                logger.info(f"Retry setting {setting_key} updated to {setting_value} - will apply to future retry attempts")

            return {
                "success": True,
                "message": f"Setting {setting_key} updated successfully",
                "setting_key": setting_key,
                "setting_value": setting_value
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update setting"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating system setting: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update system setting"
        )


@router.post("/api/v1/settings/bulk")
async def update_system_settings_bulk(
    request: dict,
    user: UserData = Depends(require_admin_authentication)
):
    """Update multiple system settings in bulk - requires admin privileges"""
    try:
        settings_data = request.get('settings', [])

        if not settings_data or not isinstance(settings_data, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Settings array is required"
            )

        from app.core.settings_manager import SettingsManager
        updated_settings = []
        failed_settings = []

        # Process each setting
        for setting_item in settings_data:
            if not isinstance(setting_item, dict):
                failed_settings.append({"error": "Invalid setting format", "data": setting_item})
                continue

            # Handle both 'key' and 'setting_key' for compatibility
            setting_key = setting_item.get('key') or setting_item.get('setting_key')
            setting_value = setting_item.get('value') or setting_item.get('setting_value')
            description = setting_item.get('description')

            if not setting_key:
                failed_settings.append({"error": "Setting key is required", "data": setting_item})
                continue

            try:
                # SECURITY: Pass tenant_id for client-specific settings
                success = SettingsManager.set_setting(setting_key, setting_value, description, tenant_id=user.tenant_id)

                if success:
                    updated_settings.append({
                        "setting_key": setting_key,
                        "setting_value": setting_value,
                        "status": "success"
                    })

                    # Handle special orchestrator settings
                    if setting_key in ['orchestrator_interval_minutes', 'orchestrator_enabled']:
                        from app.core.settings_manager import get_orchestrator_interval, is_orchestrator_enabled
                        from app.main import update_orchestrator_schedule

                        interval = get_orchestrator_interval()
                        enabled = is_orchestrator_enabled()
                        await update_orchestrator_schedule(interval, enabled)

                    elif setting_key == 'orchestrator_retry_interval_minutes':
                        # For retry interval changes, log for future retry attempts
                        from app.core.orchestrator_scheduler import get_orchestrator_scheduler
                        orchestrator_scheduler = get_orchestrator_scheduler()
                        if orchestrator_scheduler:
                            orchestrator_scheduler.update_retry_settings()
                        logger.info(f"Retry setting {setting_key} updated to {setting_value} - will apply to future retry attempts")

                else:
                    failed_settings.append({
                        "setting_key": setting_key,
                        "error": "Failed to update setting",
                        "status": "failed"
                    })

            except Exception as e:
                failed_settings.append({
                    "setting_key": setting_key,
                    "error": str(e),
                    "status": "failed"
                })

        # Determine overall success
        total_settings = len(settings_data)
        successful_count = len(updated_settings)
        failed_count = len(failed_settings)

        response = {
            "success": failed_count == 0,
            "message": f"Bulk update completed: {successful_count}/{total_settings} settings updated successfully",
            "updated_settings": updated_settings,
            "failed_settings": failed_settings,
            "summary": {
                "total": total_settings,
                "successful": successful_count,
                "failed": failed_count
            }
        }

        if failed_count > 0:
            logger.warning(f"Bulk settings update partially failed: {failed_count}/{total_settings} failed")
        else:
            logger.info(f"Bulk settings update successful: {successful_count} settings updated")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk settings update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process bulk settings update"
        )


@router.get("/websocket_test", response_class=HTMLResponse)
async def websocket_test():
    """WebSocket test page for debugging."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebSocket Test</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #1a1a1a;
            color: #ffffff;
        }
        .container {
            background-color: #2a2a2a;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .status {
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        }
        .connected { background-color: #2d5a2d; }
        .disconnected { background-color: #5a2d2d; }
        .log {
            background-color: #1a1a1a;
            padding: 15px;
            border-radius: 4px;
            height: 300px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 12px;
            border: 1px solid #444;
        }
        button {
            background-color: #4a5568;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            margin: 5px;
        }
        button:hover {
            background-color: #5a6578;
        }
        .progress-bar {
            width: 100%;
            height: 20px;
            background-color: #444;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }
        .progress-fill {
            height: 100%;
            background-color: #4a90e2;
            width: 0%;
            transition: width 0.3s ease;
        }
        .progress-text {
            text-align: center;
            margin: 10px 0;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h1>WebSocket Connection Test</h1>

    <div class="container">
        <h2>Connection Status</h2>
        <div id="jira-status" class="status disconnected">
            Jira: Disconnected
        </div>
        <div id="github-status" class="status disconnected">
            GitHub: Disconnected
        </div>

        <button onclick="connectAll()">Connect All</button>
        <button onclick="disconnectAll()">Disconnect All</button>
        <button onclick="clearLog()">Clear Log</button>
        <button onclick="sendTestMessage()">Send Test Message</button>
    </div>

    <div class="container">
        <h2>Progress Display</h2>
        <div id="progress-container">
            <div class="progress-text" id="progress-text">No progress data</div>
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill"></div>
            </div>
            <div id="progress-percentage">0%</div>
        </div>
    </div>

    <div class="container">
        <h2>WebSocket Log</h2>
        <div id="log" class="log"></div>
    </div>

    <script>
        let websockets = {
            jira_sync: null,
            github_sync: null
        };

        function log(message) {
            const logElement = document.getElementById('log');
            const timestamp = new Date().toLocaleTimeString();
            logElement.innerHTML += `[${timestamp}] ${message}\\n`;
            logElement.scrollTop = logElement.scrollHeight;
        }

        function updateStatus(jobName, connected) {
            const statusElement = document.getElementById(`${jobName.replace('_', '-')}-status`);
            if (!statusElement) {
                log(`[ERROR] Status element not found for ${jobName}`);
                return;
            }
            if (connected) {
                statusElement.className = 'status connected';
                statusElement.innerHTML = `[CONNECTED] ${jobName.replace('_', ' ').toUpperCase()}: Connected`;
            } else {
                statusElement.className = 'status disconnected';
                statusElement.innerHTML = `[DISCONNECTED] ${jobName.replace('_', ' ').toUpperCase()}: Disconnected`;
            }
        }

        function updateProgress(percentage, step) {
            document.getElementById('progress-text').textContent = step;
            document.getElementById('progress-fill').style.width = `${percentage}%`;
            document.getElementById('progress-percentage').textContent = `${Math.round(percentage)}%`;
        }

        function connectWebSocket(jobName) {
            if (websockets[jobName]) {
                websockets[jobName].close();
            }

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/progress/${jobName}`;

            log(`Attempting to connect to ${jobName} at: ${wsUrl}`);
            log(`Looking for status element: ${jobName.replace('_', '-')}-status`);

            try {
                const ws = new WebSocket(wsUrl);

                ws.onopen = function () {
                    log(`WebSocket connected for ${jobName}`);
                    websockets[jobName] = ws;
                    updateStatus(jobName, true);
                };

                ws.onmessage = function (event) {
                    try {
                        const data = JSON.parse(event.data);
                        log(`[WS] Message from ${jobName}: ${JSON.stringify(data)}`);

                        if (data.type === 'progress') {
                            updateProgress(data.percentage, data.step);
                        }
                    } catch (e) {
                        log(`Error parsing message from ${jobName}: ${e}`);
                    }
                };

                ws.onclose = function (event) {
                    log(`WebSocket disconnected for ${jobName}. Code: ${event.code}, Reason: ${event.reason}`);
                    websockets[jobName] = null;
                    updateStatus(jobName, false);
                };

                ws.onerror = function (error) {
                    log(`WebSocket error for ${jobName}: ${error}`);
                    updateStatus(jobName, false);
                };

            } catch (e) {
                log(`Failed to create WebSocket for ${jobName}: ${e}`);
                updateStatus(jobName, false);
            }
        }

        function connectAll() {
            log('Connecting to all WebSocket endpoints...');
            connectWebSocket('Jira');
            connectWebSocket('GitHub');
        }

        function disconnectAll() {
            log('Disconnecting all WebSocket connections...');
            Object.keys(websockets).forEach(jobName => {
                if (websockets[jobName]) {
                    websockets[jobName].close();
                    websockets[jobName] = null;
                    updateStatus(jobName, false);
                }
            });
        }

        function clearLog() {
            document.getElementById('log').innerHTML = '';
        }

        function sendTestMessage() {
            log('[TEST] Requesting test message via API...');
            fetch('/api/test_websocket', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    job_name: 'jira_sync',
                    percentage: Math.random() * 100,
                    message: `Test message: ${Math.floor(Math.random() * 1000)} of 5000 items (${(Math.random() * 100).toFixed(1)}%)`
                })
            })
            .then(response => response.json())
            .then(data => {
                log(`[API] Response: ${JSON.stringify(data)}`);
            })
            .catch(error => {
                log(`API Error: ${error}`);
            });
        }

        // Auto-connect on page load
        window.addEventListener('load', function() {
            log('WebSocket Test Page Loaded');
            log('Current URL: ' + window.location.href);

            // Auto-connect after a short delay
            setTimeout(() => {
                connectAll();
            }, 1000);
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@router.post("/api/test_websocket")
async def test_websocket_message(request: Request):
    """Send a test WebSocket message."""
    try:
        from app.core.websocket_manager import get_websocket_manager

        data = await request.json()
        job_name = data.get('job_name', 'Jira')
        percentage = data.get('percentage', 50.0)
        message = data.get('message', 'Test message')

        websocket_manager = get_websocket_manager()
        await websocket_manager.send_progress_update(job_name, percentage, message)

        connections = websocket_manager.get_connection_count(job_name)

        return {
            "success": True,
            "message": "Test message sent",
            "job_name": job_name,
            "percentage": percentage,
            "step": message,
            "connections": connections
        }

    except Exception as e:
        logger.error(f"Error sending test WebSocket message: {e}")
        return {
            "success": False,
            "error": str(e)
        }



