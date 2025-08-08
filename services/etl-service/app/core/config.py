"""
ETL Service application configuration.
Manages all configurations through environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings using Pydantic Settings."""
    
    # Application Settings
    APP_NAME: str = Field(default="ETL Service", env="APP_NAME")
    APP_VERSION: str = Field(default="1.0.0", env="APP_VERSION")
    DEBUG: bool = Field(default=False, env="DEBUG")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    # 🎯 CLIENT-SPECIFIC CONFIGURATION (Multi-Instance Approach)
    CLIENT_NAME: str = Field(env="CLIENT_NAME", description="Client name this ETL instance serves (case-insensitive)")

    # API Settings
    API_V1_STR: str = Field(default="/api/v1", env="API_V1_STR")
    HOST: str = Field(default="0.0.0.0", env="ETL_HOST")
    PORT: int = Field(default=8000, env="ETL_PORT")
    
    # PostgreSQL Configuration
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DATABASE: str
    
    # Read Replica Configuration
    POSTGRES_REPLICA_HOST: Optional[str] = Field(default=None, env="POSTGRES_REPLICA_HOST")
    POSTGRES_REPLICA_PORT: int = Field(default=5432, env="POSTGRES_REPLICA_PORT")

    # Primary Database Pool Settings (Write-heavy operations)
    DB_POOL_SIZE: int = Field(default=5, env="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(default=10, env="DB_MAX_OVERFLOW")
    DB_POOL_TIMEOUT: int = Field(default=30, env="DB_POOL_TIMEOUT")
    DB_POOL_RECYCLE: int = Field(default=3600, env="DB_POOL_RECYCLE")

    # Replica Database Pool Settings (Read-heavy operations)
    DB_REPLICA_POOL_SIZE: int = Field(default=5, env="DB_REPLICA_POOL_SIZE")
    DB_REPLICA_MAX_OVERFLOW: int = Field(default=10, env="DB_REPLICA_MAX_OVERFLOW")
    DB_REPLICA_POOL_TIMEOUT: int = Field(default=30, env="DB_REPLICA_POOL_TIMEOUT")

    # Feature Flags
    USE_READ_REPLICA: bool = Field(default=False, env="USE_READ_REPLICA")
    REPLICA_FALLBACK_ENABLED: bool = Field(default=True, env="REPLICA_FALLBACK_ENABLED")
    
    # Jira Configuration
    JIRA_URL: str
    JIRA_USERNAME: str
    JIRA_TOKEN: str

    @property
    def jira_base_url(self) -> str:
        """Returns Jira base API URL."""
        return f"{self.JIRA_URL}/rest/api/2"

    @property
    def jira_dev_status_url(self) -> str:
        """Returns Jira dev status API URL."""
        return f"{self.JIRA_URL}/rest/dev-status/1.0"
    
    # GitHub Configuration (for dev status)
    GITHUB_TOKEN: Optional[str] = None

    # Azure DevOps Configuration
    AZDO_URL: Optional[str] = None
    AZDO_TOKEN: Optional[str] = None

    # Aha! Configuration
    AHA_URL: Optional[str] = None
    AHA_TOKEN: Optional[str] = None
    
    # Job Scheduling Configuration
    SCHEDULER_TIMEZONE: str = Field(default="UTC", env="SCHEDULER_TIMEZONE")
    
    # Security Configuration
    SECRET_KEY: str = Field(default="your-secret-key-change-this-in-production", env="SECRET_KEY")
    ENCRYPTION_KEY: str = Field(default="your-secret-encryption-key-here", env="ENCRYPTION_KEY")

    # JWT Configuration (loaded from shared .env but not used by ETL service)
    # ETL Service uses centralized authentication through Backend Service
    JWT_SECRET_KEY: str = Field(default="pulse-dev-secret-key-2024", env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")

    # Cache Configuration
    REDIS_URL: Optional[str] = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    CACHE_TTL_SECONDS: int = Field(default=3600, env="CACHE_TTL_SECONDS")

    # Service Communication URLs
    BACKEND_SERVICE_URL: str = Field(default="http://localhost:3001", env="BACKEND_SERVICE_URL")
    AI_SERVICE_URL: str = Field(default="http://localhost:8001", env="AI_SERVICE_URL")
    FRONTEND_URL: str = Field(default="http://localhost:5173", env="VITE_API_BASE_URL")

    # CORS Configuration
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:5173", env="CORS_ORIGINS")

    # Cookie Configuration
    COOKIE_DOMAIN: str = Field(default=".localhost", env="COOKIE_DOMAIN")
    COOKIE_SECURE: bool = Field(default=False, env="COOKIE_SECURE")
    COOKIE_SAMESITE: str = Field(default="lax", env="COOKIE_SAMESITE")

    # Internal communication secret (for backend -> ETL internal APIs)
    ETL_INTERNAL_SECRET: str = Field(default="dev-internal-secret-change", env="ETL_INTERNAL_SECRET")

    @property
    def cors_origins_list(self) -> list:
        """Convert CORS_ORIGINS string to list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def postgres_connection_string(self) -> str:
        """Builds the PostgreSQL connection string."""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}"

    @property
    def postgres_replica_connection_string(self) -> str:
        """Read replica connection string (falls back to primary if no replica configured)"""
        replica_host = self.POSTGRES_REPLICA_HOST or self.POSTGRES_HOST
        replica_port = self.POSTGRES_REPLICA_PORT if self.POSTGRES_REPLICA_HOST else self.POSTGRES_PORT
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{replica_host}:{replica_port}/{self.POSTGRES_DATABASE}"
    
    @property
    def jira_base_url(self) -> str:
        """Base URL for Jira APIs."""
        return f"{self.JIRA_URL}/rest/api/2"
    

    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from environment


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


def get_client_id_from_name(client_name: str) -> int:
    """
    Get client ID from client name using case-insensitive lookup.

    Args:
        client_name: Client name to look up

    Returns:
        Client ID

    Raises:
        Exception: If client not found or inactive
    """
    from app.core.database import get_database
    from app.models.unified_models import Client

    database = get_database()
    with database.get_session() as session:
        # Case-insensitive lookup with whitespace handling
        client = session.query(Client).filter(
            Client.name.ilike(client_name.strip()),  # Case-insensitive
            Client.active == True
        ).first()

        if not client:
            # Get available clients for error message
            available_clients = [c.name for c in session.query(Client).filter(Client.active == True).all()]
            raise Exception(f"Client '{client_name}' not found or inactive. Available active clients: {available_clients}")

        return client.id


def get_current_client_id() -> int:
    """Get the current ETL instance's client ID from configuration."""
    settings = get_settings()
    return get_client_id_from_name(settings.CLIENT_NAME)


# For backward compatibility
settings = get_settings()
