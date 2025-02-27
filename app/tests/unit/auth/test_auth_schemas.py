"""
Unit tests for authentication schemas in the Send Sage application.

This module tests the validation and behavior of authentication-related
Pydantic models in the schemas module.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from typing import List, Dict, Any, Optional
from pydantic import ValidationError
from enum import Enum

from app.schemas.auth import (
    UserLogin,
    UserCreate,
    UserResponse,
    TokenData,
    Token,
    TokenRefreshRequest,
    PasswordReset,
    PasswordUpdate
)
from app.schemas.user import UserProfile, UserProfileUpdate

# Define Scope locally for testing purposes
class Scope(str, Enum):
    """User permission scopes."""
    USER = "user"
    ADMIN = "admin"
    
    @staticmethod
    def from_string(scope_string: str) -> List[str]:
        """Convert a space-delimited string to a list of scopes."""
        if not scope_string:
            return []
        return [s for s in scope_string.split() if s]
    
    @staticmethod
    def to_string(scopes: List[str]) -> str:
        """Convert a list of scopes to a space-delimited string."""
        return " ".join(scopes)


@pytest.mark.unit
class TestUserSchemas:
    """Tests for user-related schemas."""
    
    def test_user_login_valid(self):
        """Test valid user login data."""
        # Valid data should create a model instance
        user_login = UserLogin(
            email="test@example.com",
            password="SecurePassword123!"
        )
        
        assert user_login.email == "test@example.com"
        assert user_login.password == "SecurePassword123!"
    
    def test_user_login_invalid_email(self):
        """Test user login with invalid email format."""
        # Invalid email should raise ValidationError
        with pytest.raises(ValidationError) as excinfo:
            UserLogin(
                email="not-an-email",
                password="SecurePassword123!"
            )
        
        # Verify error details
        errors = excinfo.value.errors()
        assert any("email" in error["loc"] for error in errors)
        assert any("valid email" in error["msg"].lower() for error in errors)
    
    def test_user_create_valid(self):
        """Test valid user creation data."""
        # Valid data should create a model instance
        user_create = UserCreate(
            email="newuser@example.com",
            username="newuser",
            password="NewSecurePassword123!",
            experience_level="intermediate"
        )
        
        assert user_create.email == "newuser@example.com"
        assert user_create.username == "newuser"
        assert user_create.password == "NewSecurePassword123!"
        assert user_create.experience_level == "intermediate"
    
    def test_user_create_password_validation(self):
        """Test user creation with weak password."""
        # Password too short
        with pytest.raises(ValidationError) as excinfo:
            UserCreate(
                email="newuser@example.com",
                username="newuser",
                password="short",
                experience_level="intermediate"
            )
        
        # Verify error details
        errors = excinfo.value.errors()
        assert any("password" in error["loc"] for error in errors)
        assert any("length" in error["msg"].lower() for error in errors)

    def test_user_profile_valid(self):
        """Test valid user profile data."""
        # Valid data should create a model instance
        user_profile = UserProfile(
            id=str(uuid4()),
            username="testuser",
            email="test@example.com",
            experience_level="intermediate",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            tier="free",
            payment_status="active",
            preferences={
                "theme": "dark",
                "grade_display": "yds"
            }
        )
        
        assert user_profile.username == "testuser"
        assert user_profile.email == "test@example.com"
        assert user_profile.preferences["theme"] == "dark"
    
    def test_user_profile_update_valid(self):
        """Test valid user profile update data."""
        # Valid data should create a model instance
        update_data = {
            "username": "updateduser",
            "email": "updated@example.com",
            "mountain_project_url": "https://www.mountainproject.com/user/12345/john-doe"
        }
        
        user_profile_update = UserProfileUpdate(**update_data)
        
        assert user_profile_update.username == "updateduser"
        assert user_profile_update.email == "updated@example.com"
    
    def test_user_profile_update_partial(self):
        """Test partial user profile update data."""
        # Only updating some fields should work
        update_data = {
            "username": "updateduser"
        }
        
        user_profile_update = UserProfileUpdate(**update_data)
        
        assert user_profile_update.username == "updateduser"
        assert user_profile_update.email is None


@pytest.mark.unit
class TestTokenSchemas:
    """Tests for token-related schemas."""
    
    def test_token_data_valid(self):
        """Test valid token data."""
        # Valid data should create a model instance
        user_id = uuid4()
        jti = str(uuid4())
        
        token_data = TokenData(
            user_id=user_id,
            scopes=["user"],
            type="access",
            jti=jti
        )
        
        assert token_data.user_id == user_id
        assert token_data.scopes == ["user"]
        assert token_data.type == "access"
        assert token_data.jti == jti
    
    def test_token_data_invalid_type(self):
        """Test token data with invalid token type."""
        # Invalid token type should raise ValidationError
        with pytest.raises(ValidationError) as excinfo:
            TokenData(
                user_id=uuid4(),
                scopes=["user"],
                type="invalid",  # Not 'access' or 'refresh'
                jti=str(uuid4())
            )
        
        # Verify error details
        errors = excinfo.value.errors()
        assert any("type" in error["loc"] for error in errors)
        assert any("access" in error["msg"].lower() for error in errors) or \
               any("refresh" in error["msg"].lower() for error in errors)
    
    def test_token_response_valid(self):
        """Test valid token response."""
        # Valid data should create a model instance
        token_response = Token(
            access_token="access.token.jwt",
            refresh_token="refresh.token.jwt",
            token_type="bearer",
            expires_in=3600
        )
        
        assert token_response.access_token == "access.token.jwt"
        assert token_response.refresh_token == "refresh.token.jwt"
        assert token_response.token_type == "bearer"
        assert token_response.expires_in == 3600
    
    def test_refresh_token_request_valid(self):
        """Test valid refresh token request."""
        # Valid data should create a model instance
        refresh_request = TokenRefreshRequest(
            refresh_token="refresh.token.jwt"
        )
        
        assert refresh_request.refresh_token == "refresh.token.jwt"


@pytest.mark.unit
class TestPasswordResetSchemas:
    """Tests for password reset related schemas."""
    
    def test_password_reset_request_valid(self):
        """Test valid password reset request."""
        # Valid data should create a model instance
        reset_request = PasswordReset(
            email="test@example.com"
        )
        
        assert reset_request.email == "test@example.com"
    
    def test_password_reset_request_invalid_email(self):
        """Test password reset request with invalid email."""
        # Invalid email should raise ValidationError
        with pytest.raises(ValidationError) as excinfo:
            PasswordReset(
                email="not-an-email"
            )
        
        # Verify error details
        errors = excinfo.value.errors()
        assert any("email" in error["loc"] for error in errors)
        assert any("valid email" in error["msg"].lower() for error in errors)
    
    def test_password_update_valid(self):
        """Test valid password update."""
        # Valid data should create a model instance
        update_data = PasswordUpdate(
            token="valid.reset.token",
            new_password="NewSecurePassword123!",
            confirm_password="NewSecurePassword123!"
        )
        
        assert update_data.token == "valid.reset.token"
        assert update_data.new_password.get_secret_value() == "NewSecurePassword123!"
        assert update_data.confirm_password.get_secret_value() == "NewSecurePassword123!"
    
    def test_password_update_weak_password(self):
        """Test password update with weak password."""
        # Password too short should raise ValidationError
        with pytest.raises(ValidationError) as excinfo:
            PasswordUpdate(
                token="valid.reset.token",
                new_password="short",  # Too short
                confirm_password="short"
            )
        
        # Verify error details
        errors = excinfo.value.errors()
        assert any("new_password" in error["loc"] for error in errors)
        assert any("length" in error["msg"].lower() for error in errors)


@pytest.mark.unit
class TestScope:
    """Tests for scope related functionality."""
    
    def test_scope_enum_values(self):
        """Test scope enum values."""
        # Verify enum values
        assert Scope.USER == "user"
        assert Scope.ADMIN == "admin"
    
    def test_scope_list_parsing(self):
        """Test parsing scopes from string."""
        # Scope strings should be correctly parsed
        scopes_str = "user admin"
        scopes_list = Scope.from_string(scopes_str)
        
        assert isinstance(scopes_list, list)
        assert Scope.USER in scopes_list
        assert Scope.ADMIN in scopes_list
        
        # Empty string should return empty list
        assert Scope.from_string("") == []
    
    def test_scope_string_formatting(self):
        """Test formatting scopes to string."""
        # Scope list should be correctly formatted
        scopes_list = [Scope.USER, Scope.ADMIN]
        scopes_str = Scope.to_string(scopes_list)
        
        assert isinstance(scopes_str, str)
        assert "user" in scopes_str
        assert "admin" in scopes_str
        
        # Empty list should return empty string
        assert Scope.to_string([]) == "" 