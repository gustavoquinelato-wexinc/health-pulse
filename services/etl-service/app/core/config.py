"""
ETL Service application configuration.
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
    APP_NAME: str = "ETL Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # 🎯 TENANT-SPECIFIC CONFIGURATION (Multi-Instance Approach)
    CLIENT_NAME: str = ""  # Required: Tenant name this ETL instance serves (case-insensitive)

    # API Settings
    API_V1_STR: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Service URLs (no hardcoded URLs)
    BACKEND_SERVICE_URL: str = "http://localhost:3001"

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
    # Increased to prevent UI blocking during ETL jobs
    DB_POOL_SIZE: int = 20  # Up from 5 - reserve connections for UI while ETL runs
    DB_MAX_OVERFLOW: int = 30  # Up from 10 - allow burst capacity
    DB_POOL_TIMEOUT: int = 10  # Down from 30 - fail fast if no connections available
    DB_POOL_RECYCLE: int = 1800  # Down from 3600 - recycle connections more frequently

    # Replica Database Pool Settings (Read-heavy operations)
    DB_REPLICA_POOL_SIZE: int = 5
    DB_REPLICA_MAX_OVERFLOW: int = 10
    DB_REPLICA_POOL_TIMEOUT: int = 30

    # Feature Flags
    USE_READ_REPLICA: bool = False
    REPLICA_FALLBACK_ENABLED: bool = True
    
    # NOTE: Jira Configuration moved to database (integrations table)
    # All integration credentials are now stored in the database for security

    # NOTE: jira_base_url property removed - URLs now come from database

    # NOTE: Jira URL and projects properties removed - these now come from database integration records
    
    # NOTE: All integration configurations (GitHub, Azure DevOps, Aha!)
    # are now stored in the database (integrations table) for security
    
    # Job Scheduling Configuration
    SCHEDULER_TIMEZONE: str = "UTC"

    # Security Configuration
    SECRET_KEY: str = "QBYpLWwoEjV_m4ywClhaXmz2dtvjD56nDl2mf1tbuEg"
    ENCRYPTION_KEY: str = "ayHa2aciB-E3TYrlgHhr6WJ365b-s_uE5tfnHa5lIuM="

    # JWT Configuration (loaded from shared .env but not used by ETL service)
    # ETL Service uses centralized authentication through Backend Service
    JWT_SECRET_KEY: str = "CG4JhJsv-y6cwTXlSHU6N-ZwIh2ibjUvoFuxC9PaPOU"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Cache Configuration
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 3600

    # Service Communication URLs
    BACKEND_SERVICE_URL: str = "http://localhost:3001"
    FRONTEND_URL: str = "http://localhost:5173"

    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3333,http://localhost:5173"

    # Cookie Configuration
    COOKIE_DOMAIN: str = ".localhost"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    # Internal communication secret (for backend -> ETL internal APIs)
    ETL_INTERNAL_SECRET: str = "dev-internal-secret-change"

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
    
    # NOTE: jira_base_url property removed - URLs now come from database
    




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

    New precedence (per project policy):
    1) Service-local .env (services/etl-service/.env)
    2) Environment variables
    3) Root .env is reserved for docker-compose and not loaded by services
    """
    global _settings
    if _settings is None:
        from pathlib import Path
        # Prefer service-local .env relative to this file
        service_dir = Path(__file__).resolve().parents[2]  # services/etl-service
        service_env = service_dir / ".env"
        if service_env.exists():
            print(f"Loading configuration from service .env: {service_env}")
            _settings = Settings(_env_file=str(service_env))
        else:
            print("Service .env not found; using environment variables only")
            _settings = Settings()

    return _settings


def get_tenant_id_from_name(client_name: str) -> int:
    """
    Get tenant ID from tenant name using case-insensitive lookup.

    Args:
        client_name: Tenant name to look up

    Returns:
        Tenant ID

    Raises:
        Exception: If tenant not found or inactive
    """
    from app.core.database import get_database
    from app.models.unified_models import Tenant

    database = get_database()
    with database.get_session() as session:
        # Case-insensitive lookup with whitespace handling
        tenant = session.query(Tenant).filter(
            Tenant.name.ilike(client_name.strip()),  # Case-insensitive
            Tenant.active == True
        ).first()

        if not tenant:
            # Get available tenants for error message
            available_tenants = [c.name for c in session.query(Tenant).filter(Tenant.active == True).all()]
            raise Exception(f"Tenant '{client_name}' not found or inactive. Available active tenants: {available_tenants}")

        return tenant.id


def get_current_tenant_id() -> int:
    """Get the current ETL instance's tenant ID from configuration."""
    settings = get_settings()
    return get_tenant_id_from_name(settings.CLIENT_NAME)


# For backward compatibility
settings = get_settings()
