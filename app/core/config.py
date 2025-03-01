"""
Application configuration module.

This module defines all application settings using Pydantic for validation.
Settings are loaded from environment variables with appropriate type conversion
and validation.
"""

# Core imports that don't create cycles
from typing import List, Optional, Any, Dict, TYPE_CHECKING
from pydantic_settings import BaseSettings
from pydantic import (
    AnyHttpUrl,
    Field,
    field_validator,
    EmailStr,
    PostgresDsn,
    ValidationInfo,
    ConfigDict
)
import secrets
from pathlib import Path
from uuid import uuid4





# Track initialization state
_settings_initialized = False
_settings_instance = None

class Settings(BaseSettings):
    """
    Application settings with validation and documentation.
    
    Settings are loaded from environment variables and validated using Pydantic.
    Default values are provided where appropriate.
    """
    
    # Core Settings
    PROJECT_NAME: str = "Send Sage"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Server Settings
    APP_IMPORT: str = Field(
        default="app.main:app",
        description="Import path for the FastAPI application"
    )
    HOST: str = Field(
        default="0.0.0.0",
        description="Host address to bind the server to"
    )
    PORT: int = Field(
        default=8000,
        description="Port to run the server on"
    )
    
    # Environment Settings
    ENVIRONMENT: str = Field(
        default="development",
        description="Application environment (development, staging, production)"
    )
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    TESTING: bool = Field(
        default=False,
        description="Enable test mode"
    )
    
    # Security Settings
    SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for JWT encoding"
    )
    ALGORITHM: str = Field(
        default="RS256",
        description="Algorithm for JWT encoding"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60 * 24 * 8,  # 8 days
        description="Access token expiration in minutes"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=30,
        description="Refresh token expiration in days"
    )
    USE_COOKIE_AUTH: bool = Field(
        default=False,
        description="Use cookie-based refresh token if true, else header"
    )
    MASTER_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Master key for encrypting private keys at rest"
    )
    KEY_ROTATION_INTERVAL_DAYS: int = Field(
        default=7,
        description="Number of days between key rotations"
    )
    KEY_ROTATION_GRACE_PERIOD_DAYS: int = Field(
        default=1,
        description="Grace period in days for accepting old keys"
    )
    MAX_LOGIN_ATTEMPTS: int = Field(
        default=10,
        description="Maximum number of failed login attempts per minute"
    )
    MAX_PASSWORD_RESET_ATTEMPTS: int = Field(
        default=5,
        description="Maximum number of password reset attempts per hour"
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for rate limiting"
    )
    ALLOWED_HOSTS: List[str] = Field(
        default=["*"],
        description="List of allowed hosts for the application"
    )
    
    # CORS Settings
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = Field(
        default=None,
        description="List of origins that are allowed to make cross-origin requests"
    )
    
    # Database Settings - Simplified to a single URL
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Main database URL"
    )
    TEST_DATABASE_URL: Optional[str] = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/test_sendsage",
        description="Test database URL"
    )
    
    # External Services
    DEEPSEEK_API_KEY: Optional[str] = Field(
        default=None,
        description="DeepSeek API key"
    )
    DEEPSEEK_API_URL: Optional[str] = Field(
        default=None,
        description="DeepSeek API URL"
    )
    
    # Email Settings
    GMAIL_USERNAME: Optional[str] = Field(
        default=None,
        description="Gmail username for email sending"
    )
    GMAIL_PASSWORD: Optional[str] = Field(
        default=None,
        description="Gmail application password"
    )
    GMAIL_DEFAULT_SENDER: Optional[EmailStr] = Field(
        default=None,
        description="Default sender email address"
    )
    
    # Stripe Settings
    STRIPE_API_KEY: Optional[str] = Field(
        default=None,
        description="Stripe secret API key"
    )
    STRIPE_PUBLIC_KEY: Optional[str] = Field(
        default=None,
        description="Stripe publishable key"
    )
    STRIPE_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        description="Stripe webhook signing secret"
    )
    STRIPE_PRICE_ID_BASIC: Optional[str] = Field(
        default=None,
        description="Stripe price ID for basic tier"
    )
    STRIPE_PRICE_ID_PREMIUM: Optional[str] = Field(
        default=None,
        description="Stripe price ID for premium tier"
    )
    
    # Application URLs
    SERVER_HOST: str = Field(
        default="http://localhost:8000",
        description="Server host URL"
    )
    
    # File Paths
    TEMPLATES_DIR: Path = Field(
        default=Path(__file__).parent.parent / "templates",
        description="Path to templates directory"
    )
    
    CURRENT_KID: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Current Key ID for JWT signing"
    )

    # Chat Settings
    DEEPSEEK_API_KEY: Optional[str] = Field(
        default=None,
        description="DeepSeek API key"
    )
    DEEPSEEK_API_URL: Optional[str] = Field(
        default=None,
        description="DeepSeek API URL"
    )
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str] | str:
        """Validate and process CORS origins."""
        if isinstance(v, str) and not v.startswith("["):
            # Split by comma and strip each item, also removing trailing slashes
            return [i.strip().rstrip('/') for i in v.split(",")]
        elif isinstance(v, list):
            # Remove trailing slashes from list items
            return [str(origin).rstrip('/') for origin in v]
        raise ValueError("Invalid CORS origins format")
        
    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def assemble_allowed_hosts(cls, v: str | List[str]) -> List[str]:
        """Validate and process allowed hosts."""
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
        
    model_config = ConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
        from_attributes=True,
        populate_by_name=True
    )


def get_settings() -> Settings:
    """
    Get or create settings instance with initialization tracking.
    
    Returns:
        Settings instance
    """
    
    global _settings_initialized, _settings_instance
    
    if not _settings_initialized:
        _settings_instance = Settings()
        _settings_initialized = True
        
    return _settings_instance

# Create settings instance through getter
settings = get_settings()
