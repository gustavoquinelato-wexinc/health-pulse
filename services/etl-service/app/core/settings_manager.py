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
        'orchestrator_retry_enabled': {
            'value': True,
            'type': 'boolean',
            'description': 'Whether to enable fast retry for failed jobs'
        },
        'orchestrator_retry_interval_minutes': {
            'value': 15,
            'type': 'integer',
            'description': 'Fast retry interval in minutes for failed jobs'
        },
        'orchestrator_max_retry_attempts': {
            'value': 3,
            'type': 'integer',
            'description': 'Maximum number of fast retry attempts before falling back to normal interval'
        },
        'max_concurrent_jobs': {
            'value': 1,
            'type': 'integer',
            'description': 'Maximum number of concurrent ETL jobs'
        },
        'job_timeout_minutes': {
            'value': 240,
            'type': 'integer',
            'description': 'Job timeout in minutes'
        },
        'github_graphql_batch_size': {
            'value': 50,
            'type': 'integer',
            'description': 'Number of pull requests to fetch per GraphQL request'
        },
        'github_request_timeout_seconds': {
            'value': 60,
            'type': 'integer',
            'description': 'Timeout for GitHub API requests in seconds'
        },
        'jira_database_batch_size': {
            'value': 100,
            'type': 'integer',
            'description': 'Batch size for Jira database operations (IN clauses)'
        },
        'jira_commit_batch_size': {
            'value': 500,
            'type': 'integer',
            'description': 'Number of records to process before committing transaction (prevents long-running transactions)'
        },
        'jira_session_refresh_interval': {
            'value': 1000,
            'type': 'integer',
            'description': 'Number of records processed before refreshing database session (prevents connection timeouts)'
        }
    }
    
    @staticmethod
    def get_setting(setting_key: str, default_value: Any = None, tenant_id: int = None) -> Any:
        """
        Get a setting value from the database.

        Args:
            setting_key: The setting key to retrieve
            default_value: Default value if setting doesn't exist
            tenant_id: Tenant ID to filter settings (required for client-specific settings)

        Returns:
            The setting value converted to its proper type
        """
        try:
            database = get_database()
            with database.get_session() as session:
                # ✅ SECURITY: Filter by tenant_id if provided
                query = session.query(SystemSettings).filter(SystemSettings.setting_key == setting_key)
                if tenant_id is not None:
                    query = query.filter(SystemSettings.tenant_id == tenant_id)
                setting = query.first()
                
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
    def set_setting(setting_key: str, value: Any, description: str = None, tenant_id: int = None) -> bool:
        """
        Set a setting value in the database.

        Args:
            setting_key: The setting key to set
            value: The value to set
            description: Optional description for the setting
            tenant_id: Tenant ID for client-specific settings (required for client-specific settings)

        Returns:
            True if successful, False otherwise
        """
        try:
            database = get_database()
            with database.get_session() as session:
                # ✅ SECURITY: Get or create setting filtered by tenant_id
                query = session.query(SystemSettings).filter(SystemSettings.setting_key == setting_key)
                if tenant_id is not None:
                    query = query.filter(SystemSettings.tenant_id == tenant_id)
                setting = query.first()
                
                if not setting:
                    # ✅ SECURITY: Use provided tenant_id or get default client
                    if tenant_id is not None:
                        target_tenant_id = tenant_id
                    else:
                        # Fallback to current ETL instance's client for global settings
                        from app.core.config import get_settings
                        from app.core.config import get_tenant_id_from_name
                        try:
                            settings = get_settings()
                            target_tenant_id = get_tenant_id_from_name(settings.CLIENT_NAME)
                        except Exception as e:
                            logger.error(f"Cannot determine client ID from CLIENT_NAME: {e}")
                            return False

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
                        description=description,
                        tenant_id=target_tenant_id  # ✅ SECURITY: Use appropriate tenant_id
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
    def get_all_settings(tenant_id: int = None) -> Dict[str, Any]:
        """
        Get all settings as a dictionary.

        Args:
            tenant_id: Tenant ID to filter settings (optional)

        Returns:
            Dictionary of all settings with their values
        """
        try:
            database = get_database()
            with database.get_session() as session:
                # ✅ SECURITY: Filter by tenant_id if provided
                query = session.query(SystemSettings)
                if tenant_id is not None:
                    query = query.filter(SystemSettings.tenant_id == tenant_id)
                settings = query.all()
                
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
        Initialize default settings for ALL clients in the database if they don't exist.

        Returns:
            True if successful, False otherwise
        """
        try:
            database = get_database()
            with database.get_session() as session:
                # ✅ SECURITY: Initialize settings for ALL clients
                from app.models.unified_models import Tenant
                clients = session.query(Tenant).filter(Tenant.active == True).all()
                if not clients:
                    logger.error("No active clients found - cannot initialize settings")
                    return False

                logger.info(f"Initializing default settings for {len(clients)} clients")

                for client in clients:
                    logger.info(f"Initializing settings for client: {client.name} (ID: {client.id})")

                    for key, info in SettingsManager.DEFAULT_SETTINGS.items():
                        # ✅ SECURITY: Check for existing settings by tenant_id
                        existing = session.query(SystemSettings).filter(
                            SystemSettings.setting_key == key,
                            SystemSettings.tenant_id == client.id
                        ).first()

                        if not existing:
                            setting = SystemSettings(
                                setting_key=key,
                                setting_type=info['type'],
                                description=info['description'],
                                tenant_id=client.id
                            )
                            setting.set_typed_value(info['value'])
                            session.add(setting)

                session.commit()
                logger.info("Default settings initialized successfully for all clients")
                return True

        except Exception as e:
            logger.error(f"Error initializing default settings: {e}")
            return False


# 🎯 SIMPLIFIED CONVENIENCE FUNCTIONS (Multi-Instance Approach)
# Each ETL instance serves one client, so we can simplify these functions

def get_current_tenant_id() -> int:
    """Get the current ETL instance's client ID from configuration."""
    from app.core.config import get_current_tenant_id
    return get_current_tenant_id()

def get_orchestrator_interval(tenant_id: int = None) -> int:
    """Get orchestrator interval in minutes for current client."""
    if tenant_id is None:
        tenant_id = get_current_tenant_id()
    return SettingsManager.get_setting('orchestrator_interval_minutes', 60, tenant_id=tenant_id)


def set_orchestrator_interval(minutes: int, tenant_id: int = None) -> bool:
    """Set orchestrator interval in minutes for current client."""
    if tenant_id is None:
        tenant_id = get_current_tenant_id()
    return SettingsManager.set_setting('orchestrator_interval_minutes', minutes, tenant_id=tenant_id)


def is_orchestrator_enabled(tenant_id: int = None) -> bool:
    """Check if orchestrator is enabled for current client."""
    if tenant_id is None:
        tenant_id = get_current_tenant_id()
    return SettingsManager.get_setting('orchestrator_enabled', True, tenant_id=tenant_id)


def set_orchestrator_enabled(enabled: bool, tenant_id: int = None) -> bool:
    """Enable or disable orchestrator for current client."""
    if tenant_id is None:
        tenant_id = get_current_tenant_id()
    return SettingsManager.set_setting('orchestrator_enabled', enabled, tenant_id=tenant_id)


def is_orchestrator_retry_enabled(tenant_id: int = None) -> bool:
    """Check if orchestrator fast retry is enabled for current client."""
    if tenant_id is None:
        tenant_id = get_current_tenant_id()
    return SettingsManager.get_setting('orchestrator_retry_enabled', True, tenant_id=tenant_id)


def set_orchestrator_retry_enabled(enabled: bool, tenant_id: int = None) -> bool:
    """Enable or disable orchestrator fast retry for current client."""
    if tenant_id is None:
        tenant_id = get_current_tenant_id()
    return SettingsManager.set_setting('orchestrator_retry_enabled', enabled, tenant_id=tenant_id)


def get_orchestrator_retry_interval(tenant_id: int = None) -> int:
    """Get orchestrator retry interval in minutes for current client."""
    if tenant_id is None:
        tenant_id = get_current_tenant_id()
    return SettingsManager.get_setting('orchestrator_retry_interval_minutes', 15, tenant_id=tenant_id)


def set_orchestrator_retry_interval(minutes: int, tenant_id: int = None) -> bool:
    """Set orchestrator retry interval in minutes for current client."""
    if tenant_id is None:
        tenant_id = get_current_tenant_id()
    return SettingsManager.set_setting('orchestrator_retry_interval_minutes', minutes, tenant_id=tenant_id)


def get_orchestrator_max_retry_attempts(tenant_id: int = None) -> int:
    """Get maximum retry attempts for current client."""
    if tenant_id is None:
        tenant_id = get_current_tenant_id()
    return SettingsManager.get_setting('orchestrator_max_retry_attempts', 3, tenant_id=tenant_id)


def set_orchestrator_max_retry_attempts(attempts: int, tenant_id: int = None) -> bool:
    """Set maximum retry attempts for current client."""
    if tenant_id is None:
        tenant_id = get_current_tenant_id()
    return SettingsManager.set_setting('orchestrator_max_retry_attempts', attempts, tenant_id=tenant_id)


def get_github_graphql_batch_size() -> int:
    """Get GitHub GraphQL batch size for pull requests."""
    return SettingsManager.get_setting('github_graphql_batch_size', 50)


def set_github_graphql_batch_size(batch_size: int) -> bool:
    """Set GitHub GraphQL batch size for pull requests."""
    return SettingsManager.set_setting('github_graphql_batch_size', batch_size)


def get_github_request_timeout() -> int:
    """Get GitHub API request timeout in seconds."""
    return SettingsManager.get_setting('github_request_timeout_seconds', 60)


def set_github_request_timeout(timeout_seconds: int) -> bool:
    """Set GitHub API request timeout in seconds."""
    return SettingsManager.set_setting('github_request_timeout_seconds', timeout_seconds)


def get_jira_database_batch_size() -> int:
    """Get Jira database batch size for IN clauses."""
    return SettingsManager.get_setting('jira_database_batch_size', 100)


def set_jira_database_batch_size(batch_size: int) -> bool:
    """Set Jira database batch size for IN clauses."""
    return SettingsManager.set_setting('jira_database_batch_size', batch_size)


def get_jira_commit_batch_size() -> int:
    """Get Jira commit batch size for transaction chunking."""
    return SettingsManager.get_setting('jira_commit_batch_size', 500)


def set_jira_commit_batch_size(batch_size: int) -> bool:
    """Set Jira commit batch size for transaction chunking."""
    return SettingsManager.set_setting('jira_commit_batch_size', batch_size)


def get_jira_session_refresh_interval() -> int:
    """Get Jira session refresh interval to prevent connection timeouts."""
    return SettingsManager.get_setting('jira_session_refresh_interval', 1000)


def set_jira_session_refresh_interval(interval: int) -> bool:
    """Set Jira session refresh interval to prevent connection timeouts."""
    return SettingsManager.set_setting('jira_session_refresh_interval', interval)
