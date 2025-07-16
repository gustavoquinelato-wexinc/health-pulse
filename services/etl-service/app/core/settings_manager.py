"""
System Settings Manager

Provides functions to manage system-wide configuration settings stored in the database.
Includes orchestrator schedule management and other configurable system settings.
"""

from typing import Optional, Any, Dict
from sqlalchemy.orm import Session
from app.core.database import get_database
from app.core.logging_config import get_logger
from app.models.unified_models import SystemSettings

logger = get_logger(__name__)


class SettingsManager:
    """Manages system settings stored in the database."""
    
    # Default settings with their types and descriptions
    DEFAULT_SETTINGS = {
        'orchestrator_interval_minutes': {
            'value': 60,
            'type': 'integer',
            'description': 'Orchestrator run interval in minutes'
        },
        'orchestrator_enabled': {
            'value': True,
            'type': 'boolean',
            'description': 'Whether the orchestrator is enabled'
        },
        'max_concurrent_jobs': {
            'value': 1,
            'type': 'integer',
            'description': 'Maximum number of concurrent ETL jobs'
        },
        'job_timeout_minutes': {
            'value': 120,
            'type': 'integer',
            'description': 'Job timeout in minutes'
        }
    }
    
    @staticmethod
    def get_setting(setting_key: str, default_value: Any = None) -> Any:
        """
        Get a setting value from the database.
        
        Args:
            setting_key: The setting key to retrieve
            default_value: Default value if setting doesn't exist
            
        Returns:
            The setting value converted to its proper type
        """
        try:
            database = get_database()
            with database.get_session() as session:
                setting = session.query(SystemSettings).filter(
                    SystemSettings.setting_key == setting_key
                ).first()
                
                if setting:
                    return setting.get_typed_value()
                
                # Return default from DEFAULT_SETTINGS or provided default
                if setting_key in SettingsManager.DEFAULT_SETTINGS:
                    return SettingsManager.DEFAULT_SETTINGS[setting_key]['value']
                
                return default_value
                
        except Exception as e:
            logger.error(f"Error getting setting {setting_key}: {e}")
            # Return default from DEFAULT_SETTINGS or provided default
            if setting_key in SettingsManager.DEFAULT_SETTINGS:
                return SettingsManager.DEFAULT_SETTINGS[setting_key]['value']
            return default_value
    
    @staticmethod
    def set_setting(setting_key: str, value: Any, description: str = None) -> bool:
        """
        Set a setting value in the database.
        
        Args:
            setting_key: The setting key to set
            value: The value to set
            description: Optional description for the setting
            
        Returns:
            True if successful, False otherwise
        """
        try:
            database = get_database()
            with database.get_session() as session:
                # Get or create setting
                setting = session.query(SystemSettings).filter(
                    SystemSettings.setting_key == setting_key
                ).first()
                
                if not setting:
                    # Determine type from DEFAULT_SETTINGS or value type
                    setting_type = 'string'
                    if setting_key in SettingsManager.DEFAULT_SETTINGS:
                        setting_type = SettingsManager.DEFAULT_SETTINGS[setting_key]['type']
                        if not description:
                            description = SettingsManager.DEFAULT_SETTINGS[setting_key]['description']
                    else:
                        # Infer type from value
                        if isinstance(value, bool):
                            setting_type = 'boolean'
                        elif isinstance(value, int):
                            setting_type = 'integer'
                        elif isinstance(value, (dict, list)):
                            setting_type = 'json'
                    
                    setting = SystemSettings(
                        setting_key=setting_key,
                        setting_type=setting_type,
                        description=description
                    )
                    session.add(setting)
                
                # Set the value
                setting.set_typed_value(value)
                
                # Update description if provided
                if description:
                    setting.description = description
                
                session.commit()
                logger.info(f"Setting {setting_key} updated to: {value}")
                return True
                
        except Exception as e:
            logger.error(f"Error setting {setting_key}: {e}")
            return False
    
    @staticmethod
    def get_all_settings() -> Dict[str, Any]:
        """
        Get all settings as a dictionary.
        
        Returns:
            Dictionary of all settings with their values
        """
        try:
            database = get_database()
            with database.get_session() as session:
                settings = session.query(SystemSettings).all()
                
                result = {}
                
                # Add database settings
                for setting in settings:
                    result[setting.setting_key] = {
                        'value': setting.get_typed_value(),
                        'type': setting.setting_type,
                        'description': setting.description
                    }
                
                # Add defaults for missing settings
                for key, default_info in SettingsManager.DEFAULT_SETTINGS.items():
                    if key not in result:
                        result[key] = default_info.copy()
                
                return result
                
        except Exception as e:
            logger.error(f"Error getting all settings: {e}")
            return SettingsManager.DEFAULT_SETTINGS.copy()
    
    @staticmethod
    def initialize_default_settings() -> bool:
        """
        Initialize default settings in the database if they don't exist.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            database = get_database()
            with database.get_session() as session:
                for key, info in SettingsManager.DEFAULT_SETTINGS.items():
                    existing = session.query(SystemSettings).filter(
                        SystemSettings.setting_key == key
                    ).first()
                    
                    if not existing:
                        setting = SystemSettings(
                            setting_key=key,
                            setting_type=info['type'],
                            description=info['description']
                        )
                        setting.set_typed_value(info['value'])
                        session.add(setting)
                
                session.commit()
                logger.info("Default settings initialized successfully")
                return True
                
        except Exception as e:
            logger.error(f"Error initializing default settings: {e}")
            return False


# Convenience functions for specific settings
def get_orchestrator_interval() -> int:
    """Get orchestrator interval in minutes."""
    return SettingsManager.get_setting('orchestrator_interval_minutes', 60)


def set_orchestrator_interval(minutes: int) -> bool:
    """Set orchestrator interval in minutes."""
    return SettingsManager.set_setting('orchestrator_interval_minutes', minutes)


def is_orchestrator_enabled() -> bool:
    """Check if orchestrator is enabled."""
    return SettingsManager.get_setting('orchestrator_enabled', True)


def set_orchestrator_enabled(enabled: bool) -> bool:
    """Enable or disable orchestrator."""
    return SettingsManager.set_setting('orchestrator_enabled', enabled)
