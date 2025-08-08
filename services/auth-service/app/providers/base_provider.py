"""
Base Authentication Provider Interface
Defines the contract for authentication providers (local, OKTA, etc.)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel

class AuthenticationResult(BaseModel):
    """Result of authentication attempt"""
    success: bool
    user_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    provider_data: Optional[Dict[str, Any]] = None  # Provider-specific data

class BaseAuthProvider(ABC):
    """Base class for authentication providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider_name = self.__class__.__name__.lower().replace('provider', '')
    
    @abstractmethod
    async def authenticate(self, email: str, password: str) -> AuthenticationResult:
        """
        Authenticate user with email/password
        
        Args:
            email: User email
            password: User password
            
        Returns:
            AuthenticationResult with success status and user data
        """
        pass
    
    @abstractmethod
    async def get_user_info(self, provider_user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information from provider
        
        Args:
            provider_user_id: User ID in the provider system
            
        Returns:
            User data dictionary or None if not found
        """
        pass
    
    @abstractmethod
    def get_oauth_url(self, state: str, redirect_uri: str) -> str:
        """
        Get OAuth authorization URL for provider
        
        Args:
            state: CSRF protection state parameter
            redirect_uri: Where to redirect after authentication
            
        Returns:
            OAuth authorization URL
        """
        pass
    
    @abstractmethod
    async def handle_oauth_callback(self, code: str, state: str) -> AuthenticationResult:
        """
        Handle OAuth callback from provider
        
        Args:
            code: Authorization code from provider
            state: State parameter for CSRF protection
            
        Returns:
            AuthenticationResult with user data
        """
        pass
    
    def map_user_data(self, provider_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map provider user data to internal user format
        
        Args:
            provider_data: Raw user data from provider
            
        Returns:
            Mapped user data in internal format
        """
        # Default mapping - override in specific providers
        return {
            "email": provider_data.get("email"),
            "first_name": provider_data.get("first_name", ""),
            "last_name": provider_data.get("last_name", ""),
            "provider": self.provider_name,
            "provider_user_id": provider_data.get("id"),
            "is_active": True
        }
    
    def is_enabled(self) -> bool:
        """Check if this provider is enabled"""
        return self.config.get("enabled", False)
    
    def get_display_name(self) -> str:
        """Get human-readable provider name"""
        return self.config.get("display_name", self.provider_name.title())

class ProviderRegistry:
    """Registry for authentication providers"""
    
    def __init__(self):
        self._providers: Dict[str, BaseAuthProvider] = {}
        self._default_provider: Optional[str] = None
    
    def register(self, provider: BaseAuthProvider, is_default: bool = False):
        """Register an authentication provider"""
        self._providers[provider.provider_name] = provider
        if is_default or not self._default_provider:
            self._default_provider = provider.provider_name
    
    def get_provider(self, provider_name: str) -> Optional[BaseAuthProvider]:
        """Get provider by name"""
        return self._providers.get(provider_name)
    
    def get_default_provider(self) -> Optional[BaseAuthProvider]:
        """Get the default provider"""
        if self._default_provider:
            return self._providers.get(self._default_provider)
        return None
    
    def get_enabled_providers(self) -> Dict[str, BaseAuthProvider]:
        """Get all enabled providers"""
        return {
            name: provider 
            for name, provider in self._providers.items() 
            if provider.is_enabled()
        }
    
    def list_providers(self) -> Dict[str, Dict[str, Any]]:
        """List all providers with their info"""
        return {
            name: {
                "name": provider.provider_name,
                "display_name": provider.get_display_name(),
                "enabled": provider.is_enabled(),
                "is_default": name == self._default_provider
            }
            for name, provider in self._providers.items()
        }

# Global provider registry
provider_registry = ProviderRegistry()

def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry"""
    return provider_registry
