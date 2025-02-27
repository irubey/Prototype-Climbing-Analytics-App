"""
Authentication and authorization schemas.

This module defines Pydantic models for authentication and authorization,
including user registration, login, token management, and password operations.
All schemas include comprehensive validation and documentation.
"""

# Core imports that don't create cycles
from datetime import datetime, timedelta
import re
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, UUID4, field_validator, HttpUrl, SecretStr, ConfigDict
from app.models.enums import (
    UserTier,
    PaymentStatus
)

# Module state tracking
import sys
from app.core.logging import logger

logger.info(
    "Loading auth schemas module",
    extra={
        "module_id": id(sys.modules[__name__]),
        "module_file": __file__,
        "module_name": __name__,
        "import_chain": [
            name for name in sys.modules
            if name.startswith("app.")
        ]
    }
)

# Enums are safe at module level


# Base schemas that don't require model imports
class UserBase(BaseModel):
    """Base schema for user data with email and username validation."""
    email: EmailStr = Field(
        ...,
        description="Unique email address",
        examples=["user@example.com"]
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Unique username (3-50 chars, alphanumeric with _ and -)",
        examples=["john_doe", "climbing_pro"]
    )
    mountain_project_url: Optional[str] = Field(
        "",
        description="Mountain Project profile URL",
        examples=["https://www.mountainproject.com/user/12345/john-doe"]
    )
    eight_a_nu_url: Optional[str] = Field(
        "",
        description="8a.nu profile URL",
        examples=["https://www.8a.nu/user/12345"]
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("mountain_project_url", mode="before")
    @classmethod
    def convert_http_url_to_string(cls, v: Any) -> Optional[str]:
        """Convert HttpUrl to string BEFORE validation."""
        if isinstance(v, str):
            return v
        if isinstance(v, HttpUrl):
            return str(v)
        return v

    @field_validator("eight_a_nu_url", mode="before")
    @classmethod
    def convert_eight_a_nu_url_to_string(cls, v: Any) -> Optional[str]:
        if isinstance(v, str):
            return v
        if isinstance(v, HttpUrl):
            return str(v)
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if not v.isalnum() and not all(c in "_-" for c in v if not c.isalnum()):
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        return v

# Schema definitions that don't depend on models
class UserCreate(UserBase):
    """Schema for user registration with password validation."""
    password: SecretStr = Field(
        ...,
        min_length=8,
        max_length=72,
        description="Password must be 8-72 characters with mixed case, numbers, and symbols"
    )

    @field_validator("mountain_project_url", mode="before")
    @classmethod
    def convert_http_url_to_string(cls, v: Any) -> Optional[str]:
        """Convert HttpUrl to string BEFORE validation."""
        if isinstance(v, str):
            return v
        if isinstance(v, HttpUrl):
            return str(v)
        return v

    @field_validator("eight_a_nu_url", mode="before")
    @classmethod
    def convert_eight_a_nu_url_to_string(cls, v: Any) -> Optional[str]:
        if isinstance(v, str):
            return v
        if isinstance(v, HttpUrl):
            return str(v)
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: SecretStr) -> SecretStr:
        """Validate password strength requirements."""
        password = v.get_secret_value()
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", password):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise ValueError("Password must contain at least one special character")
        return v

class UserLogin(BaseModel):
    """Schema for user login with rate limiting metadata."""
    email: EmailStr = Field(..., description="User's email address")
    password: SecretStr = Field(..., description="User's password")
    remember: bool = Field(False, description="Whether to extend token expiration time")
    client_ip: Optional[str] = Field(None, description="Client IP address for rate limiting")
    user_agent: Optional[str] = Field(None, description="User agent string for analytics")

class Token(BaseModel):
    """OAuth2 token response."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    refresh_token: Optional[str] = Field(None, description="JWT refresh token")

class TokenData(BaseModel):
    """JWT token payload data."""
    user_id: UUID = Field(..., description="User ID")
    scopes: List[str] = Field(default_factory=list, description="Token scopes")
    type: str = Field(..., description="Token type (access or refresh)")
    jti: str = Field(..., description="JWT ID for token tracking")

class TokenRefreshRequest(BaseModel):
    """Request to refresh an access token."""
    refresh_token: str = Field(..., description="JWT refresh token")

class TokenRevokeRequest(BaseModel):
    """Request to revoke a token."""
    token: str = Field(..., description="JWT token to revoke")
    token_type_hint: Optional[str] = Field(None, description="Token type hint (access or refresh)")

class TokenIntrospectRequest(BaseModel):
    """Request to introspect a token."""
    token: str = Field(..., description="JWT token to introspect")
    token_type_hint: Optional[str] = Field(None, description="Token type hint (access or refresh)")

class TokenIntrospectResponse(BaseModel):
    """Token introspection response."""
    active: bool = Field(..., description="Whether the token is active")
    scope: Optional[str] = Field(None, description="Space-separated list of scopes")
    client_id: Optional[str] = Field(None, description="Client identifier")
    username: Optional[str] = Field(None, description="Resource owner username")
    token_type: Optional[str] = Field(None, description="Type of token")
    exp: Optional[int] = Field(None, description="Expiration timestamp")
    iat: Optional[int] = Field(None, description="Issued at timestamp")
    nbf: Optional[int] = Field(None, description="Not before timestamp")
    sub: Optional[str] = Field(None, description="Subject of the token")
    aud: Optional[List[str]] = Field(None, description="Intended audiences")
    iss: Optional[str] = Field(None, description="Token issuer")
    jti: Optional[str] = Field(None, description="JWT ID")

class UserResponse(UserBase):
    """Schema for user response data with detailed metadata."""
    id: UUID4 = Field(..., description="Unique user identifier")
    tier: UserTier = Field(..., description="User subscription tier")
    payment_status: PaymentStatus = Field(..., description="Payment status")
    stripe_customer_id: Optional[str] = Field(None, description="Stripe customer ID")
    stripe_subscription_id: Optional[str] = Field(None, description="Stripe subscription ID")
    stripe_webhook_verified: bool = Field(False, description="Whether Stripe webhook is verified")
    daily_message_count: int = Field(0, description="Daily message count")
    last_message_date: Optional[datetime] = Field(None, description="Last message timestamp")
    mountain_project_last_sync: Optional[datetime] = Field(None, description="Last Mountain Project sync")
    eight_a_nu_last_sync: Optional[datetime] = Field(None, description="Last 8a.nu sync")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    is_active: bool = Field(..., description="Whether user account is active")
    last_payment_check: Optional[datetime] = Field(None, description="Last payment check timestamp")
    login_attempts: Optional[int] = Field(0, description="Failed login attempts")
    last_failed_login: Optional[datetime] = Field(None, description="Last failed login attempt")
    account_locked_until: Optional[datetime] = Field(None, description="Account lock expiration")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("mountain_project_url", mode="before")
    @classmethod
    def convert_http_url_to_string(cls, v: Any) -> Optional[str]:
        """Convert HttpUrl to string BEFORE validation."""
        if isinstance(v, str):
            return v
        if isinstance(v, HttpUrl):
            return str(v)
        return v

    @field_validator("eight_a_nu_url", mode="before")
    @classmethod
    def convert_eight_a_nu_url_to_string(cls, v: Any) -> Optional[str]:
        if isinstance(v, str):
            return v
        if isinstance(v, HttpUrl):
            return str(v)
        return v

# Password management schemas
class PasswordReset(BaseModel):
    """Schema for password reset request with rate limiting."""
    email: EmailStr = Field(..., description="Email for password reset")
    client_ip: Optional[str] = Field(None, description="Client IP for rate limiting")

class PasswordUpdate(BaseModel):
    """Schema for password update with validation."""
    token: str = Field(..., description="Password reset token", min_length=1)
    new_password: SecretStr = Field(
        ...,
        min_length=8,
        max_length=72,
        description="New password"
    )
    confirm_password: SecretStr = Field(
        ...,
        min_length=8,
        max_length=72,
        description="Confirm new password"
    )

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: SecretStr, info: Dict[str, Any]) -> SecretStr:
        """Validate that passwords match."""
        if "new_password" in info.data and v.get_secret_value() != info.data["new_password"].get_secret_value():
            raise ValueError("Passwords do not match")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: SecretStr) -> SecretStr:
        """Validate password strength requirements."""
        password = v.get_secret_value()
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", password):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise ValueError("Password must contain at least one special character")
        return v 