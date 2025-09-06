"""
User-specific API routes for Backend Service.
Handles user preferences and personal settings.
"""

from fastapi import APIRouter, HTTPException, Depends, status, File, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from typing import Optional
import httpx

from app.auth.auth_middleware import get_current_user
from app.models.unified_models import User
from app.core.database import get_database
from app.core.logging_config import get_logger
from app.core.config import get_settings
from app.services.color_resolution_service import ColorResolutionService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/user")

# Initialize color resolution service
color_resolution_service = ColorResolutionService()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ThemeModeRequest(BaseModel):
    mode: str  # "light" or "dark"

class ThemeModeResponse(BaseModel):
    success: bool
    mode: str
    message: Optional[str] = None

class AccessibilityPreferenceRequest(BaseModel):
    use_accessible_colors: bool

class AccessibilityPreferenceResponse(BaseModel):
    success: bool
    use_accessible_colors: bool
    message: Optional[str] = None

class ProfileResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    auth_provider: str
    theme_mode: str
    accessibility_level: str = 'regular'
    high_contrast_mode: bool = False
    reduce_motion: bool = False
    colorblind_safe_palette: bool = False
    profile_image_filename: Optional[str] = None
    last_login_at: Optional[str] = None

class ProfileUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    accessibility_level: Optional[str] = None
    high_contrast_mode: Optional[bool] = None
    reduce_motion: Optional[bool] = None
    colorblind_safe_palette: Optional[bool] = None

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

class StandardResponse(BaseModel):
    success: bool
    message: str


# ============================================================================
# USER THEME ENDPOINTS
# ============================================================================

@router.get("/theme-mode", response_model=ThemeModeResponse)
async def get_user_theme_mode(
    user: User = Depends(get_current_user)
):
    """Get the current user's theme mode preference"""
    try:
        logger.info(f"Fetching theme mode for user: {user.email}")

        # Always fetch fresh theme_mode from database to avoid cache issues
        database = get_database()
        with database.get_read_session_context() as session:
            db_user = session.query(User).filter(User.id == user.id).first()

            if not db_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            theme_mode = db_user.theme_mode or "light"  # Default to light if None

        return ThemeModeResponse(
            success=True,
            mode=theme_mode
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user theme mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch theme mode"
        )


@router.post("/theme-mode", response_model=ThemeModeResponse)
async def update_user_theme_mode(
    request: ThemeModeRequest,
    user: User = Depends(get_current_user)
):
    """Update the current user's theme mode preference"""
    try:
        # Validate theme mode
        if request.mode not in ["light", "dark"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Theme mode must be 'light' or 'dark'"
            )

        logger.info(f"Updating theme mode for user {user.email} to: {request.mode}")

        database = get_database()
        with database.get_write_session_context() as session:
            # Get the user record and update theme_mode
            db_user = session.query(User).filter(User.id == user.id).first()
            
            if not db_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Update theme mode
            db_user.theme_mode = request.mode
            db_user.last_updated_at = func.now()
            
            session.commit()

            logger.info(f"✅ User {user.email} theme mode updated to: {request.mode}")

            # Notify ETL service of user theme change
            await notify_etl_user_theme_change(user.id, request.mode)

            return ThemeModeResponse(
                success=True,
                mode=request.mode,
                message=f"Theme mode updated to {request.mode}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user theme mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update theme mode"
        )


# ============================================================================
# USER PROFILE ENDPOINTS
# ============================================================================

@router.get("/profile", response_model=ProfileResponse)
async def get_user_profile(
    user: User = Depends(get_current_user)
):
    """Get the current user's profile information"""
    try:
        logger.info(f"Fetching profile for user: {user.email}")

        # Always fetch fresh data from database
        database = get_database()
        with database.get_read_session_context() as session:
            db_user = session.query(User).filter(User.id == user.id).first()

            if not db_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            return ProfileResponse(
                id=db_user.id,
                email=db_user.email,
                first_name=db_user.first_name,
                last_name=db_user.last_name,
                role=db_user.role,
                auth_provider=db_user.auth_provider,
                theme_mode=db_user.theme_mode or "light",
                accessibility_level=db_user.accessibility_level or "regular",
                high_contrast_mode=db_user.high_contrast_mode or False,
                reduce_motion=db_user.reduce_motion or False,
                colorblind_safe_palette=db_user.colorblind_safe_palette or False,
                profile_image_filename=db_user.profile_image_filename,
                last_login_at=db_user.last_login_at.isoformat() if db_user.last_login_at else None
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch profile"
        )


@router.put("/profile", response_model=StandardResponse)
async def update_user_profile(
    request: ProfileUpdateRequest,
    user: User = Depends(get_current_user)
):
    """Update the current user's profile information"""
    try:
        logger.info(f"Updating profile for user: {user.email}")

        database = get_database()
        with database.get_write_session_context() as session:
            # Get the user record
            db_user = session.query(User).filter(User.id == user.id).first()

            if not db_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Update fields if provided
            if request.first_name is not None:
                db_user.first_name = request.first_name

            if request.last_name is not None:
                db_user.last_name = request.last_name

            if request.use_accessible_colors is not None:
                old_accessibility = db_user.use_accessible_colors
                db_user.use_accessible_colors = request.use_accessible_colors

                # Invalidate user color cache if accessibility preference changed
                if old_accessibility != request.use_accessible_colors:
                    color_resolution_service.invalidate_caches(user_id=user.id)
                    logger.info(f"User {user.email} accessibility preference changed: {old_accessibility} -> {request.use_accessible_colors}")

            db_user.last_updated_at = func.now()
            session.commit()

            logger.info(f"✅ User {user.email} profile updated successfully")

            return StandardResponse(
                success=True,
                message="Profile updated successfully"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.post("/accessibility-preference", response_model=AccessibilityPreferenceResponse)
async def update_accessibility_preference(
    request: AccessibilityPreferenceRequest,
    user: User = Depends(get_current_user)
):
    """Update user's accessibility color preference"""
    try:
        logger.info(f"Updating accessibility preference for user: {user.email}")

        database = get_database()
        with database.get_write_session_context() as session:
            # Get the user record
            db_user = session.query(User).filter(User.id == user.id).first()

            if not db_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            old_preference = db_user.use_accessible_colors
            db_user.use_accessible_colors = request.use_accessible_colors
            db_user.last_updated_at = func.now()

            session.commit()

            # Invalidate user color cache to force refresh with new preference
            color_resolution_service.invalidate_caches(user_id=user.id)

            logger.info(f"✅ User {user.email} accessibility preference updated: {old_preference} -> {request.use_accessible_colors}")

            return AccessibilityPreferenceResponse(
                success=True,
                use_accessible_colors=request.use_accessible_colors,
                message=f"Accessibility preference updated to {'enabled' if request.use_accessible_colors else 'disabled'}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating accessibility preference: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update accessibility preference"
        )


@router.get("/colors")
async def get_user_colors(
    user: User = Depends(get_current_user)
):
    """Get user-specific colors based on their accessibility preference"""
    try:
        logger.info(f"Getting colors for user: {user.email}")

        # Resolve colors based on user preferences
        user_colors = color_resolution_service.resolve_user_colors(user.id, user.tenant_id)

        if not user_colors:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Color configuration not found for user"
            )

        return {
            "success": True,
            "colors": user_colors,
            "user_preferences": {
                "accessibility_level": user.accessibility_level or "regular",
                "theme_mode": user.theme_mode or "light",
                "high_contrast_mode": user.high_contrast_mode or False,
                "reduce_motion": user.reduce_motion or False,
                "colorblind_safe_palette": user.colorblind_safe_palette or False
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user colors: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user colors"
        )


@router.post("/change-password", response_model=StandardResponse)
async def change_user_password(
    request: PasswordChangeRequest,
    user: User = Depends(get_current_user)
):
    """Change the current user's password"""
    try:
        # Validate password confirmation
        if request.new_password != request.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password and confirmation do not match"
            )

        # Validate password strength (basic validation)
        if len(request.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )

        logger.info(f"Changing password for user: {user.email}")

        database = get_database()
        with database.get_write_session_context() as session:
            # Get the user record
            db_user = session.query(User).filter(User.id == user.id).first()

            if not db_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Only allow password change for local auth users
            if db_user.auth_provider != 'local':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password change is only available for local authentication users"
                )

            # Verify current password
            from app.auth.auth_service import get_auth_service
            auth_service = get_auth_service()

            if not auth_service._verify_password(request.current_password, db_user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect"
                )

            # Check if new password is different from current password
            if auth_service._verify_password(request.new_password, db_user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New password must be different from current password"
                )

            # Hash and update the new password
            db_user.password_hash = auth_service._hash_password(request.new_password)
            db_user.last_updated_at = func.now()
            session.commit()

            logger.info(f"✅ Password changed successfully for user: {user.email}")

            return StandardResponse(
                success=True,
                message="Password changed successfully"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing user password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.post("/profile-image", response_model=StandardResponse)
async def upload_profile_image(
    profile_image: UploadFile = File(...),
    user: User = Depends(get_current_user)
):
    """Upload a profile image for the current user"""
    try:
        # Validate file type - only image files allowed
        if not profile_image.content_type or not profile_image.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )

        # Validate file size (max 5MB)
        if profile_image.size and profile_image.size > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size must be less than 5MB"
            )

        logger.info(f"Uploading profile image for user: {user.email}")

        database = get_database()
        with database.get_write_session_context() as session:
            from pathlib import Path
            import os

            # Get the user record
            db_user = session.query(User).filter(User.id == user.id).first()

            if not db_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Read file content
            file_content = await profile_image.read()

            # Get file extension
            file_extension = 'png'  # Default to PNG
            if profile_image.filename and '.' in profile_image.filename:
                file_extension = profile_image.filename.split('.')[-1].lower()

            # Generate user-specific folder name using exact email (sanitized for filesystem)
            user_folder = db_user.email.lower().replace('@', '_at_').replace('.', '_').replace('-', '_')
            profile_filename = f"profile-image.{file_extension}"

            # Get client information for assets folder structure
            from app.models.unified_models import Tenant
            client = session.query(Tenant).filter(Tenant.id == db_user.tenant_id).first()
            if not client:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tenant not found"
                )

            client_folder = client.assets_folder or client.name.lower()

            # Create user-specific directories (relative to project root)
            project_root = Path(__file__).parent.parent.parent.parent.parent
            frontend_user_dir = project_root / f"services/frontend-app/public/assets/{client_folder}/users/{user_folder}"
            etl_user_dir = project_root / f"services/etl-service/app/static/assets/{client_folder}/users/{user_folder}"

            frontend_user_dir.mkdir(parents=True, exist_ok=True)
            etl_user_dir.mkdir(parents=True, exist_ok=True)

            # Save file to both user directories
            frontend_image_path = frontend_user_dir / profile_filename
            etl_image_path = etl_user_dir / profile_filename

            # Write to both locations
            with open(frontend_image_path, "wb") as f:
                f.write(file_content)

            with open(etl_image_path, "wb") as f:
                f.write(file_content)

            # Update user record with profile image info
            db_user.profile_image_filename = profile_filename
            db_user.last_updated_at = func.now()
            session.commit()

            logger.info(f"✅ Profile image uploaded for user: {user.email}")

            return StandardResponse(
                success=True,
                message="Profile image uploaded successfully"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading profile image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload profile image"
        )


# ============================================================================
# FUTURE USER PREFERENCE ENDPOINTS
# ============================================================================

# TODO: Add other user preference endpoints here:
# - Notification preferences
# - Language preferences


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def notify_etl_user_theme_change(user_id: int, theme_mode: str):
    """Notify ETL service of user theme change for cache invalidation"""
    try:
        settings = get_settings()
        etl_service_url = settings.ETL_SERVICE_URL

        if not etl_service_url:
            logger.warning("ETL_SERVICE_URL not configured, skipping theme change notification")
            return

        async with httpx.AsyncTenant(timeout=5.0) as client:
            response = await client.post(
                f"{etl_service_url}/api/v1/internal/user-theme-changed",
                json={
                    "user_id": user_id,
                    "theme_mode": theme_mode
                }
            )

            if response.status_code == 200:
                logger.info(f"✅ ETL service notified of theme change for user {user_id}")
            else:
                logger.warning(f"⚠️ Failed to notify ETL service of theme change: {response.status_code}")

    except Exception as e:
        logger.error(f"❌ Error notifying ETL service of theme change: {e}")
        # Don't raise exception - theme change should succeed even if notification fails
