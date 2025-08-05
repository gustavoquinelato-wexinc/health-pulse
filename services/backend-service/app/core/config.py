"""
Backend Service application configuration.
Manages all configurations through environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings using Pydantic Settings."""
    
    # Application Settings
    APP_NAME: str = Field(default="Backend Service", env="APP_NAME")
    APP_VERSION: str = Field(default="1.0.0", env="APP_VERSION")
    DEBUG: bool = Field(default=False, env="DEBUG")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    # API Settings
    API_V1_STR: str = Field(default="/api/v1", env="API_V1_STR")
    HOST: str = Field(default="0.0.0.0", env="BACKEND_HOST")
    PORT: int = Field(default=3001, env="BACKEND_PORT")
    
    # PostgreSQL Configuration
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DATABASE: str
    
    # Database Connection Pool Settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    
    # Jira Configuration (optional - mainly used by ETL service)
    JIRA_URL: Optional[str] = None
    JIRA_USERNAME: Optional[str] = None
    JIRA_TOKEN: Optional[str] = None

    @property
    def jira_base_url(self) -> str:
        """Returns Jira base API URL."""
        if self.JIRA_URL:
            return f"{self.JIRA_URL}/rest/api/2"
        return ""

    @property
    def jira_dev_status_url(self) -> str:
        """Returns Jira dev status API URL."""
        if self.JIRA_URL:
            return f"{self.JIRA_URL}/rest/dev-status/1.0"
        return ""
    
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

    # JWT Configuration
    JWT_SECRET_KEY: str = Field(default="pulse-dev-secret-key-2024", env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")

    # Cache Configuration
    REDIS_URL: Optional[str] = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    CACHE_TTL_SECONDS: int = Field(default=3600, env="CACHE_TTL_SECONDS")

    # Service Communication URLs
    ETL_SERVICE_URL: str = Field(default="http://localhost:8000", env="ETL_SERVICE_URL")
    AI_SERVICE_URL: str = Field(default="http://localhost:8001", env="AI_SERVICE_URL")
    FRONTEND_URL: str = Field(default="http://localhost:5173", env="VITE_API_BASE_URL")

    # CORS Configuration
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:5173", env="CORS_ORIGINS")

    @property
    def cors_origins_list(self) -> list:
        """Convert CORS_ORIGINS string to list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def postgres_connection_string(self) -> str:
        """Builds the PostgreSQL connection string."""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}"
    
    @property
    def jira_base_url_legacy(self) -> str:
        """Legacy property - use jira_base_url instead."""
        return self.jira_base_url
    

    
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
    """Returns the settings instance with lazy initialization."""
    global _settings
    if _settings is None:
        # Try to load from .env file in current directory first
        from pathlib import Path

        # Find .env file - prioritize root-level configuration
        current_dir = Path.cwd()
        env_file = None

        # Strategy: Look for root-level .env first, then fallback to local
        # This supports both workspace-root execution and service-specific execution

        # 1. Check if we're in workspace root (has services/ directory)
        if (current_dir / "services").exists() and (current_dir / ".env").exists():
            env_file = str(current_dir / ".env")

        # 2. Check if we're in a subdirectory of workspace (go up to find root)
        elif not env_file:
            check_dir = current_dir
            for i in range(4):  # Check up to 4 levels up
                if (check_dir / "services").exists() and (check_dir / ".env").exists():
                    env_file = str(check_dir / ".env")
                    break
                check_dir = check_dir.parent
                if check_dir == check_dir.parent:  # Reached filesystem root
                    break

        # 3. Fallback: Look for .env in current directory and parent directories
        if not env_file:
            check_dir = current_dir
            for i in range(4):
                check_path = check_dir / ".env"
                if check_path.exists():
                    env_file = str(check_path)
                    break
                check_dir = check_dir.parent
                if check_dir == check_dir.parent:  # Reached filesystem root
                    break

        if env_file:
            print(f"Loading configuration from: {env_file}")
            _settings = Settings(_env_file=env_file)
        else:
            print("Warning: .env file not found, using environment variables only")
            _settings = Settings()

    return _settings


# For backward compatibility
settings = get_settings()
