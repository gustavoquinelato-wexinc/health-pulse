"""
Backend Service application configuration.
Manages all configurations through environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings using Pydantic Settings."""

    model_config = SettingsConfigDict(
        env_file=["../../.env", ".env"],  # Root .env as base, service .env overrides
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Application Settings
    APP_NAME: str = "Backend Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Timezone Configuration
    DEFAULT_TIMEZONE: str = "UTC"

    # API Settings
    API_V1_STR: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 3001
    
    # PostgreSQL Configuration
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DATABASE: str = "health_pulse"

    # Read Replica Configuration
    POSTGRES_REPLICA_HOST: Optional[str] = None
    POSTGRES_REPLICA_PORT: int = 5432

    # Primary Database Pool Settings (Write-heavy operations)
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600

    # Replica Database Pool Settings (Read-heavy operations)
    DB_REPLICA_POOL_SIZE: int = 5
    DB_REPLICA_MAX_OVERFLOW: int = 10
    DB_REPLICA_POOL_TIMEOUT: int = 30

    # Feature Flags
    USE_READ_REPLICA: bool = False
    REPLICA_FALLBACK_ENABLED: bool = True

    # NOTE: Jira Configuration moved to database (integrations table)
    # All integration credentials are now stored in the database for security

    # NOTE: Jira URL properties removed - URLs now come from database

    # NOTE: All integration configurations (GitHub, Azure DevOps, Aha!)
    # are now stored in the database (integrations table) for security

    # Job Scheduling Configuration
    SCHEDULER_TIMEZONE: str = "UTC"

    # Security Configuration
    SECRET_KEY: str = "QBYpLWwoEjV_m4ywClhaXmz2dtvjD56nDl2mf1tbuEg"
    ENCRYPTION_KEY: str = "ayHa2aciB-E3TYrlgHhr6WJ365b-s_uE5tfnHa5lIuM="

    # JWT Configuration
    JWT_SECRET_KEY: str = "CG4JhJsv-y6cwTXlSHU6N-ZwIh2ibjUvoFuxC9PaPOU"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Cache Configuration
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 3600

    # Service Communication URLs
    ETL_SERVICE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:5173"
    AUTH_SERVICE_URL: str = "http://localhost:4000"
    ETL_INTERNAL_SECRET: str = "dev-internal-secret-change"

    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3333,http://localhost:5173"

    # Cookie Configuration
    COOKIE_DOMAIN: str = ".localhost"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    @property
    def cors_origins_list(self) -> list:
        """Convert CORS_ORIGINS string to list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def postgres_connection_string(self) -> str:
        """Builds the PostgreSQL connection string with proper UTF-8 encoding."""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}?client_encoding=utf8"

    @property
    def postgres_replica_connection_string(self) -> str:
        """Read replica connection string (falls back to primary if no replica configured) with proper UTF-8 encoding"""
        replica_host = self.POSTGRES_REPLICA_HOST or self.POSTGRES_HOST
        replica_port = self.POSTGRES_REPLICA_PORT if self.POSTGRES_REPLICA_HOST else self.POSTGRES_PORT
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{replica_host}:{replica_port}/{self.POSTGRES_DATABASE}?client_encoding=utf8"
    
    # NOTE: Legacy jira_base_url_legacy property removed
    # Jira configuration now stored in database (integrations table)
    




class AppConfig:
    """Utility class for managing configurations and encryption."""

    @staticmethod
    def load_key() -> str:
        """Loads the encryption key."""
        return settings.ENCRYPTION_KEY
    
    @staticmethod
    def encrypt_token(token: str, key: str) -> str:
        """
        Encrypts a token using the provided key.
        """
        try:
            from cryptography.fernet import Fernet

            # Use the key directly (it's already a proper Fernet key)
            fernet = Fernet(key.encode('utf-8'))

            encrypted_token = fernet.encrypt(token.encode('utf-8'))
            return encrypted_token.decode('utf-8')
        except Exception as e:
            # Fallback: returns token without encryption (not recommended for production)
            print(f"Warning: Failed to encrypt token: {e}")
            return token
    
    @staticmethod
    def decrypt_token(encrypted_token: str, key: str) -> str:
        """
        Decrypts a token using the provided key.
        """
        try:
            from cryptography.fernet import Fernet

            # Use the key directly (it's already a proper Fernet key)
            fernet = Fernet(key.encode('utf-8'))

            decrypted_token = fernet.decrypt(encrypted_token.encode('utf-8'))
            return decrypted_token.decode('utf-8')
        except Exception as e:
            # Fallback: returns token without decryption
            print(f"Warning: Failed to decrypt token: {e}")
            return encrypted_token


# Global settings instance (lazy initialization)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Returns the settings instance with lazy initialization.

    Configuration precedence (corrected):
    1) Environment variables (highest priority)
    2) Service-local .env (services/backend-service/.env)
    3) Root .env (../../.env) (fallback for missing values)
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# For backward compatibility
settings = get_settings()
