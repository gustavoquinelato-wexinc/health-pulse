"""
Configuration settings for Auth Service
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class AuthServiceSettings(BaseSettings):
    """Auth Service configuration settings"""
    
    # Service Configuration
    AUTH_SERVICE_HOST: str = Field(default="0.0.0.0", env="AUTH_SERVICE_HOST")
    AUTH_SERVICE_PORT: int = Field(default=4000, env="AUTH_SERVICE_PORT")

    # Timezone Configuration
    DEFAULT_TIMEZONE: str = Field(default="UTC", env="DEFAULT_TIMEZONE")

    # JWT Configuration
    JWT_SECRET_KEY: str = Field(default="A-JdcapOLIm3zoYtTkxA1vTMyNt7EEvH7jHCuDjAmqw", env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_EXPIRY_HOURS: int = Field(default=24, env="JWT_EXPIRY_HOURS")
    
    # Service URLs
    BACKEND_SERVICE_URL: str = Field(default="http://localhost:3001", env="BACKEND_SERVICE_URL")
    FRONTEND_SERVICE_URL: str = Field(default="http://localhost:3000", env="FRONTEND_SERVICE_URL")
    ETL_SERVICE_URL: str = Field(default="http://localhost:8000", env="ETL_SERVICE_URL")
    AUTH_SERVICE_URL: str = Field(default="http://localhost:4000", env="AUTH_SERVICE_URL")
    
    # CORS Configuration
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:5173,http://localhost:8000,http://localhost:3001", env="CORS_ORIGINS")
    
    # Cookie Configuration
    COOKIE_DOMAIN: str = Field(default=".localhost", env="COOKIE_DOMAIN")
    COOKIE_SECURE: bool = Field(default=False, env="COOKIE_SECURE")
    COOKIE_SAMESITE: str = Field(default="lax", env="COOKIE_SAMESITE")
    
    # OKTA Configuration (Optional)
    OKTA_DOMAIN: str = Field(default="", env="OKTA_DOMAIN")
    OKTA_CLIENT_ID: str = Field(default="", env="OKTA_CLIENT_ID")
    OKTA_CLIENT_SECRET: str = Field(default="", env="OKTA_CLIENT_SECRET")
    OKTA_REDIRECT_URI: str = Field(default="http://localhost:4000/auth/okta/callback", env="OKTA_REDIRECT_URI")
    
    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", env="LOG_FORMAT")
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert CORS_ORIGINS string to list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables not defined in this class


# Global settings instance
_settings = None


def get_settings() -> AuthServiceSettings:
    """Get settings instance (singleton pattern)"""
    global _settings
    if _settings is None:
        _settings = AuthServiceSettings()
    return _settings
