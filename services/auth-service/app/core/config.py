"""
Configuration settings for Auth Service
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List


class AuthServiceSettings(BaseSettings):
    """Auth Service configuration settings"""

    model_config = SettingsConfigDict(
        env_file=[".env", "../../.env"],  # Try service .env first, then root .env
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Service Configuration
    AUTH_SERVICE_HOST: str = "0.0.0.0"
    AUTH_SERVICE_PORT: int = 4000

    # Timezone Configuration
    DEFAULT_TIMEZONE: str = "UTC"

    # JWT Configuration
    JWT_SECRET_KEY: str = "CG4JhJsv-y6cwTXlSHU6N-ZwIh2ibjUvoFuxC9PaPOU"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 5  # Short expiry for security - frontend should refresh tokens

    # Service URLs
    BACKEND_SERVICE_URL: str = "http://localhost:3001"
    FRONTEND_SERVICE_URL: str = "http://localhost:3000"
    ETL_SERVICE_URL: str = "http://localhost:8000"
    AUTH_SERVICE_URL: str = "http://localhost:4000"

    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8000,http://localhost:3001"

    # Cookie Configuration
    COOKIE_DOMAIN: str = ".localhost"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    # OKTA Configuration (Optional)
    OKTA_DOMAIN: str = ""
    OKTA_CLIENT_ID: str = ""
    OKTA_CLIENT_SECRET: str = ""
    OKTA_REDIRECT_URI: str = "http://localhost:4000/auth/okta/callback"

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert CORS_ORIGINS string to list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]



# Global settings instance
_settings = None


def get_settings() -> AuthServiceSettings:
    """Get settings instance (singleton pattern)"""
    global _settings
    if _settings is None:
        _settings = AuthServiceSettings()
    return _settings
