"""
Color Resolution Service
Main service for resolving colors based on client, user preferences, and accessibility needs
"""
import logging
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.unified_models import (
    TenantColors, User, Tenant
)
from app.core.database import get_database
from .color_calculation_service import ColorCalculationService
from .color_cache_service import ColorCacheService

logger = logging.getLogger(__name__)

class ColorResolutionService:
    """
    Main service for resolving colors based on client settings, user preferences, and accessibility needs.
    Integrates with caching and calculation services for optimal performance.
    """
    
    def __init__(self):
        self.calculation_service = ColorCalculationService()
        self.cache_service = ColorCacheService()
        self.logger = logging.getLogger(__name__)
    
    def get_client_colors(self, tenant_id: int, mode: str = 'custom', 
                         db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """
        Get client color settings with caching.
        
        Args:
            tenant_id: Tenant ID
            mode: Color schema mode ('default' or 'custom')
            db: Database session (optional)
            
        Returns:
            Dictionary with color settings or None if not found
        """
        try:
            # Try cache first
            cached_colors = self.cache_service.get_client_colors(tenant_id, mode)
            if cached_colors:
                return cached_colors
            
            # Get from database
            if not db:
                database = get_database()
                db = database.get_read_session()
            
            # For unified table, we need to specify theme_mode and accessibility_level
            # Default to 'light' theme and 'regular' accessibility for basic colors
            color_settings = db.query(TenantColors).filter(
                and_(
                    TenantColors.tenant_id == tenant_id,
                    TenantColors.color_schema_mode == mode,
                    TenantColors.theme_mode == 'light',  # Default to light theme
                    TenantColors.accessibility_level == 'regular',  # Default to regular
                    TenantColors.active == True
                )
            ).first()

            if not color_settings:
                self.logger.warning(f"No color settings found for client {tenant_id}, mode {mode}, theme light, level regular")
                return None

            # Convert to dictionary using unified table structure
            color_data = {
                'id': color_settings.id,
                'color_schema_mode': color_settings.color_schema_mode,
                'theme_mode': color_settings.theme_mode,
                'accessibility_level': color_settings.accessibility_level,

                # Base colors
                'color1': color_settings.color1,
                'color2': color_settings.color2,
                'color3': color_settings.color3,
                'color4': color_settings.color4,
                'color5': color_settings.color5,
                
                # On colors
                'on_color1': color_settings.on_color1,
                'on_color2': color_settings.on_color2,
                'on_color3': color_settings.on_color3,
                'on_color4': color_settings.on_color4,
                'on_color5': color_settings.on_color5,
                
                # Gradient colors
                'on_gradient_1_2': color_settings.on_gradient_1_2,
                'on_gradient_2_3': color_settings.on_gradient_2_3,
                'on_gradient_3_4': color_settings.on_gradient_3_4,
                'on_gradient_4_5': color_settings.on_gradient_4_5,
                'on_gradient_5_1': color_settings.on_gradient_5_1,

                # Metadata
                'tenant_id': color_settings.tenant_id,
                'created_at': color_settings.created_at.isoformat() if color_settings.created_at else None,
                'last_updated_at': color_settings.last_updated_at.isoformat() if color_settings.last_updated_at else None
            }
            
            # Cache the result
            self.cache_service.set_client_colors(tenant_id, mode, color_data)
            
            return color_data
            
        except Exception as e:
            self.logger.error(f"Error getting client colors: {e}")
            return None
    
    def get_accessibility_colors(self, tenant_id: int, mode: str = 'custom', 
                               level: str = 'AA', db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """
        Get accessibility color variants with caching.
        
        Args:
            tenant_id: Tenant ID
            mode: Color schema mode
            level: Accessibility level ('AA' or 'AAA')
            db: Database session (optional)
            
        Returns:
            Dictionary with accessibility color settings or None if not found
        """
        try:
            # Try cache first
            cached_colors = self.cache_service.get_accessibility_colors(tenant_id, mode, level)
            if cached_colors:
                return cached_colors
            
            # Get from database
            if not db:
                database = get_database()
                db = database.get_read_session()
            
            # Query unified color settings table
            # For accessibility colors, we need to determine the theme_mode
            # Default to 'light' theme for now, but this should be passed as parameter
            theme_mode = 'light'  # TODO: Pass theme_mode as parameter

            accessibility_colors = db.query(TenantColors).filter(
                and_(
                    TenantColors.tenant_id == tenant_id,
                    TenantColors.color_schema_mode == mode,
                    TenantColors.accessibility_level == level,
                    TenantColors.theme_mode == theme_mode,
                    TenantColors.active == True
                )
            ).first()

            if not accessibility_colors:
                self.logger.warning(f"No accessibility colors found for client {tenant_id}, mode {mode}, level {level}, theme {theme_mode}")
                return None
            
            # Convert to dictionary using unified table structure
            color_data = {
                'id': accessibility_colors.id,
                'color_schema_mode': accessibility_colors.color_schema_mode,
                'accessibility_level': accessibility_colors.accessibility_level,
                'theme_mode': accessibility_colors.theme_mode,

                # Base colors (accessibility-enhanced)
                'color1': accessibility_colors.color1,
                'color2': accessibility_colors.color2,
                'color3': accessibility_colors.color3,
                'color4': accessibility_colors.color4,
                'color5': accessibility_colors.color5,

                # On colors
                'on_color1': accessibility_colors.on_color1,
                'on_color2': accessibility_colors.on_color2,
                'on_color3': accessibility_colors.on_color3,
                'on_color4': accessibility_colors.on_color4,
                'on_color5': accessibility_colors.on_color5,

                # Gradient colors
                'on_gradient_1_2': accessibility_colors.on_gradient_1_2,
                'on_gradient_2_3': accessibility_colors.on_gradient_2_3,
                'on_gradient_3_4': accessibility_colors.on_gradient_3_4,
                'on_gradient_4_5': accessibility_colors.on_gradient_4_5,
                'on_gradient_5_1': accessibility_colors.on_gradient_5_1,

                # Metadata
                'tenant_id': accessibility_colors.tenant_id,
                'created_at': accessibility_colors.created_at.isoformat() if accessibility_colors.created_at else None,
                'last_updated_at': accessibility_colors.last_updated_at.isoformat() if accessibility_colors.last_updated_at else None
            }
            
            # Cache the result
            self.cache_service.set_accessibility_colors(tenant_id, mode, level, color_data)
            
            return color_data
            
        except Exception as e:
            self.logger.error(f"Error getting accessibility colors: {e}")
            return None
    
    def resolve_user_colors(self, user_id: int, tenant_id: int, 
                           db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """
        Resolve colors for a specific user considering their preferences.
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
            db: Database session (optional)
            
        Returns:
            Dictionary with resolved color settings for the user
        """
        try:
            # Try cache first
            cached_colors = self.cache_service.get_user_colors(user_id, tenant_id)
            if cached_colors:
                return cached_colors
            
            # Get user preferences
            if not db:
                database = get_database()
                db = database.get_read_session()
            
            user = db.query(User).filter(
                and_(User.id == user_id, User.active == True)
            ).first()
            
            if not user:
                self.logger.warning(f"User {user_id} not found")
                return None
            
            # Determine color mode and accessibility level from user preferences
            mode = 'custom'  # Default to custom mode
            accessibility_level = user.accessibility_level or 'regular'  # Use user's accessibility preference

            # Get appropriate colors based on user's accessibility level
            if accessibility_level in ['AA', 'AAA']:
                color_data = self.get_accessibility_colors(tenant_id, mode, accessibility_level, db)
            else:
                color_data = self.get_client_colors(tenant_id, mode, db)

            if not color_data:
                # Fallback to default mode if custom not found
                if accessibility_level in ['AA', 'AAA']:
                    color_data = self.get_accessibility_colors(tenant_id, 'default', accessibility_level, db)
                else:
                    color_data = self.get_client_colors(tenant_id, 'default', db)
            
            if color_data:
                # Add user-specific metadata
                color_data['resolved_for_user'] = user_id
                color_data['user_accessibility_level'] = accessibility_level
                color_data['user_theme_mode'] = user.theme_mode or 'light'
                color_data['resolved_accessibility_level'] = accessibility_level
                color_data['resolved_mode'] = color_data.get('color_schema_mode', mode)

                # Cache the result
                self.cache_service.set_user_colors(user_id, tenant_id, color_data)
            
            return color_data
            
        except Exception as e:
            self.logger.error(f"Error resolving user colors: {e}")
            return None
    
    def update_client_colors(self, tenant_id: int, mode: str, color_updates: Dict[str, Any],
                           db: Optional[Session] = None, colors_defined_in_mode: str = 'light') -> bool:
        """
        Update client color settings and recalculate variants.

        Args:
            tenant_id: Tenant ID
            mode: Color schema mode
            color_updates: Dictionary with color updates
            db: Database session (optional)
            colors_defined_in_mode: Mode colors are defined for ('light' or 'dark')

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            if not db:
                database = get_database()
                db = database.get_write_session()
            
            # Get existing color settings
            color_settings = db.query(TenantColors).filter(
                and_(
                    TenantColors.tenant_id == tenant_id,
                    TenantColors.color_schema_mode == mode,
                    TenantColors.active == True
                )
            ).first()
            
            if not color_settings:
                self.logger.error(f"Color settings not found for client {tenant_id}, mode {mode}")
                return False
            
            # Update base colors if provided
            base_colors = {}
            for i in range(1, 6):
                color_key = f'color{i}'
                if color_key in color_updates:
                    setattr(color_settings, color_key, color_updates[color_key])
                    base_colors[color_key] = color_updates[color_key]
                else:
                    base_colors[color_key] = getattr(color_settings, color_key)
            
            # Update settings if provided
            if 'font_contrast_threshold' in color_updates:
                color_settings.font_contrast_threshold = color_updates['font_contrast_threshold']

            # Update colors_defined_in_mode from parameter or color_updates
            if 'colors_defined_in_mode' in color_updates:
                color_settings.colors_defined_in_mode = color_updates['colors_defined_in_mode']
            else:
                color_settings.colors_defined_in_mode = colors_defined_in_mode
            
            # Recalculate variants
            variants = self.calculation_service.calculate_all_variants(
                base_colors,
                color_settings.colors_defined_in_mode,
                color_settings.font_contrast_threshold
            )
            
            # Update calculated variants
            for key, value in variants.on_colors.items():
                setattr(color_settings, key, value)
            for key, value in variants.gradient_colors.items():
                setattr(color_settings, key, value)
            for key, value in variants.adaptive_colors.items():
                setattr(color_settings, key, value)
            
            # Update timestamp
            from datetime import datetime
            color_settings.last_updated_at = datetime.now()
            
            # Commit changes
            db.commit()
            
            # Invalidate cache
            self.cache_service.invalidate_client_colors(tenant_id)
            
            self.logger.info(f"Updated color settings for client {tenant_id}, mode {mode}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating client colors: {e}")
            if db:
                db.rollback()
            return False
    
    def invalidate_caches(self, tenant_id: Optional[int] = None, user_id: Optional[int] = None) -> bool:
        """
        Invalidate color caches.
        
        Args:
            tenant_id: Tenant ID to invalidate (optional)
            user_id: User ID to invalidate (optional)
            
        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            success = True
            
            if tenant_id:
                success &= self.cache_service.invalidate_client_colors(tenant_id)
            
            if user_id:
                success &= self.cache_service.invalidate_user_colors(user_id)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error invalidating caches: {e}")
            return False
