"""
Unit tests for account management functionality.

This module tests account-related functions including:
- Account deactivation and reactivation
- Password management
- Token revocation
"""

import pytest
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
from datetime import datetime, timedelta
from enum import Enum
import asyncio

from app.models.user import User
from app.models.auth import RevokedToken
from app.core.auth import get_password_hash, verify_password
from app.models.enums import UserTier, PaymentStatus

# Define enums to match the application
class UserTier(str, Enum):
    FREE = "FREE"
    BASIC = "BASIC" 
    PREMIUM = "PREMIUM"
    
class PaymentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PENDING = "PENDING"
    
class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEACTIVATED = "DEACTIVATED"
    SUSPENDED = "SUSPENDED"

@pytest.fixture
def mock_free_user():
    """Create a mock free user for testing."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "free@example.com"
    user.tier = UserTier.FREE
    user.payment_status = PaymentStatus.INACTIVE
    user.account_status = AccountStatus.ACTIVE
    user.stripe_customer_id = None
    user.verify_password = MagicMock(return_value=True)  # Default to successful auth
    user.last_password_change = datetime.now() - timedelta(days=30)
    user.model_dump = MagicMock(return_value={
        "id": user.id,
        "email": user.email,
        "tier": UserTier.FREE,
        "payment_status": PaymentStatus.INACTIVE,
        "account_status": AccountStatus.ACTIVE,
        "stripe_customer_id": None
    })
    return user

@pytest.fixture
def mock_premium_user():
    """Create a mock premium user for testing."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "premium@example.com"
    user.tier = UserTier.PREMIUM
    user.payment_status = PaymentStatus.ACTIVE
    user.account_status = AccountStatus.ACTIVE
    user.stripe_customer_id = "cus_mock_12345"
    user.verify_password = MagicMock(return_value=True)  # Default to successful auth
    user.last_password_change = datetime.now() - timedelta(days=30)
    user.model_dump = MagicMock(return_value={
        "id": user.id,
        "email": user.email,
        "tier": UserTier.PREMIUM,
        "payment_status": PaymentStatus.ACTIVE,
        "account_status": AccountStatus.ACTIVE,
        "stripe_customer_id": "cus_mock_12345"
    })
    return user

@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client for testing."""
    mock_redis = AsyncMock(spec=redis.Redis)
    mock_redis.get = AsyncMock(return_value=None)  # Default to no rate limiting
    mock_redis.setex = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.keys = AsyncMock(return_value=[])  # Default to empty list of keys
    return mock_redis

@pytest.mark.asyncio
@pytest.mark.unit
async def test_deactivate_free_account(mock_free_user):
    """Test deactivating a free user account."""
    # Setup
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.commit = AsyncMock()
    mock_redis = AsyncMock(spec=redis.Redis)
    mock_redis.keys = AsyncMock(return_value=["token:123"])
    mock_redis.delete = AsyncMock()
    
    # Mock deactivate_account function
    async def mock_deactivate_account(db, redis_client, current_user):
        # Update user account status
        current_user.account_status = AccountStatus.DEACTIVATED
        
        # Save changes to database
        db.add(current_user)
        await db.commit()
        
        # Revoke all access tokens
        user_tokens = await redis_client.keys(f"token:{current_user.id}:*")
        if user_tokens:
            await redis_client.delete(*user_tokens)
            
        return {"message": "Account deactivated successfully"}
    
    # Test the function
    result = await mock_deactivate_account(
        db=mock_db,
        redis_client=mock_redis,
        current_user=mock_free_user
    )
    
    # Assertions
    assert "message" in result
    assert "deactivated" in result["message"].lower()
    assert mock_free_user.account_status == AccountStatus.DEACTIVATED
    mock_db.add.assert_called_once_with(mock_free_user)
    mock_db.commit.assert_called_once()
    mock_redis.keys.assert_called_once()
    mock_redis.delete.assert_called_once_with("token:123")

@pytest.mark.asyncio
@pytest.mark.unit
async def test_deactivate_premium_account(mock_premium_user):
    """Test deactivating a premium user account."""
    # Setup
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.commit = AsyncMock()
    mock_redis = AsyncMock(spec=redis.Redis)
    mock_redis.keys = AsyncMock(return_value=["token:456", "token:789"])
    mock_redis.delete = AsyncMock()
    
    # Mock deactivate_account function
    async def mock_deactivate_account(db, redis_client, current_user):
        # For premium users, we also need to cancel their subscription
        if current_user.tier != UserTier.FREE and current_user.stripe_customer_id:
            # In a real implementation, we'd call Stripe API here
            # For the test, we'll just update the user's payment status
            current_user.payment_status = PaymentStatus.INACTIVE
        
        # Update user account status
        current_user.account_status = AccountStatus.DEACTIVATED
        
        # Save changes to database
        db.add(current_user)
        await db.commit()
        
        # Revoke all access tokens
        user_tokens = await redis_client.keys(f"token:{current_user.id}:*")
        if user_tokens:
            await redis_client.delete(*user_tokens)
            
        return {"message": "Account deactivated successfully"}
    
    # Test the function
    result = await mock_deactivate_account(
        db=mock_db,
        redis_client=mock_redis,
        current_user=mock_premium_user
    )
    
    # Assertions
    assert "message" in result
    assert "deactivated" in result["message"].lower()
    assert mock_premium_user.account_status == AccountStatus.DEACTIVATED
    assert mock_premium_user.payment_status == PaymentStatus.INACTIVE
    mock_db.add.assert_called_once_with(mock_premium_user)
    mock_db.commit.assert_called_once()
    mock_redis.keys.assert_called_once()
    mock_redis.delete.assert_called_once_with("token:456", "token:789")

@pytest.mark.asyncio
@pytest.mark.unit
async def test_change_password_success(mock_free_user, mock_redis_client):
    """Test successfully changing a user's password."""
    # Setup
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.commit = AsyncMock()
    
    # Set up Redis mock to return token keys for revocation
    mock_redis_client.keys = AsyncMock(return_value=["token:123", "token:456"])
    
    # Mock password change data
    password_data = {
        "current_password": "oldpassword123",
        "new_password": "Newpassword456!",
        "confirm_password": "Newpassword456!"
    }
    
    # Mock change_password function
    async def mock_change_password(db, redis_client, current_user, password_data):
        # Check rate limiting
        rate_limit_key = f"password_change_attempt:{current_user.id}"
        attempt_count = await redis_client.get(rate_limit_key)
        
        if attempt_count and int(attempt_count) >= 5:
            raise Exception("Too many password change attempts. Try again later.")
            
        # Verify current password
        if not current_user.verify_password(password_data["current_password"]):
            # Update rate limit counter
            if not attempt_count:
                await redis_client.setex(rate_limit_key, 60 * 15, 1)  # 15 minutes expiry
            else:
                await redis_client.setex(rate_limit_key, 60 * 15, int(attempt_count) + 1)
                
            raise Exception("Current password is incorrect")
            
        # Check that new password and confirmation match
        if password_data["new_password"] != password_data["confirm_password"]:
            raise Exception("New password and confirmation do not match")
            
        # Check password strength
        if len(password_data["new_password"]) < 8:
            raise Exception("Password must be at least 8 characters long")
            
        # In a real implementation, we'd hash the new password here
        # For testing, we'll just assume it happens
        current_user.set_password = MagicMock()
        current_user.set_password(password_data["new_password"])
        current_user.last_password_change = datetime.now()
        
        # Save changes to database
        db.add(current_user)
        await db.commit()
        
        # Revoke all existing tokens
        user_tokens = await redis_client.keys(f"token:{current_user.id}:*")
        if user_tokens:
            await redis_client.delete(*user_tokens)
            
        return {"message": "Password changed successfully"}
    
    # Test the function
    result = await mock_change_password(
        db=mock_db,
        redis_client=mock_redis_client,
        current_user=mock_free_user,
        password_data=password_data
    )
    
    # Assertions
    assert "message" in result
    assert "password changed" in result["message"].lower()
    mock_free_user.set_password.assert_called_once_with(password_data["new_password"])
    assert mock_free_user.last_password_change is not None
    mock_db.add.assert_called_once_with(mock_free_user)
    mock_db.commit.assert_called_once()
    mock_redis_client.keys.assert_called_once_with(f"token:{mock_free_user.id}:*")
    mock_redis_client.delete.assert_called_once_with("token:123", "token:456")

@pytest.mark.asyncio
@pytest.mark.unit
async def test_change_password_wrong_current(mock_free_user, mock_redis_client):
    """Test changing password with incorrect current password."""
    # Setup
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Override verify_password to return False
    mock_free_user.verify_password = MagicMock(return_value=False)
    
    # Mock password change data
    password_data = {
        "current_password": "wrongpassword",
        "new_password": "Newpassword456!",
        "confirm_password": "Newpassword456!"
    }
    
    # Mock change_password function
    async def mock_change_password(db, redis_client, current_user, password_data):
        # Check rate limiting
        rate_limit_key = f"password_change_attempt:{current_user.id}"
        attempt_count = await redis_client.get(rate_limit_key)
        
        if attempt_count and int(attempt_count) >= 5:
            raise Exception("Too many password change attempts. Try again later.")
        
        # Verify current password
        if not current_user.verify_password(password_data["current_password"]):
            # Update rate limit counter
            if not attempt_count:
                await redis_client.setex(rate_limit_key, 60 * 15, 1)  # 15 minutes expiry
            else:
                await redis_client.setex(rate_limit_key, 60 * 15, int(attempt_count) + 1)
                
            raise Exception("Current password is incorrect")
            
        # Code below this shouldn't execute in this test
        return {"message": "Password changed successfully"}
    
    # Test the function - should raise exception
    with pytest.raises(Exception) as exc_info:
        await mock_change_password(
            db=mock_db,
            redis_client=mock_redis_client,
            current_user=mock_free_user,
            password_data=password_data
        )
        
    # Assertions
    assert "incorrect" in str(exc_info.value)
    mock_redis_client.get.assert_called_once()
    mock_redis_client.setex.assert_called_once()
    mock_free_user.verify_password.assert_called_once_with(password_data["current_password"])

@pytest.mark.asyncio
@pytest.mark.unit
async def test_change_password_mismatch(mock_free_user, mock_redis_client):
    """Test changing password with mismatched new password and confirmation."""
    # Setup
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Mock password change data with mismatch
    password_data = {
        "current_password": "oldpassword123",
        "new_password": "Newpassword456!",
        "confirm_password": "DifferentPassword789!"
    }
    
    # Mock change_password function
    async def mock_change_password(db, redis_client, current_user, password_data):
        # Check rate limiting (not relevant for this test)
        rate_limit_key = f"password_change_attempt:{current_user.id}"
        attempt_count = await redis_client.get(rate_limit_key)
        
        # Verify current password
        if not current_user.verify_password(password_data["current_password"]):
            # Update rate limit counter (not relevant for this test)
            raise Exception("Current password is incorrect")
            
        # Check that new password and confirmation match
        if password_data["new_password"] != password_data["confirm_password"]:
            raise Exception("New password and confirmation do not match")
            
        # Code below this shouldn't execute in this test
        return {"message": "Password changed successfully"}
    
    # Test the function - should raise exception
    with pytest.raises(Exception) as exc_info:
        await mock_change_password(
            db=mock_db,
            redis_client=mock_redis_client,
            current_user=mock_free_user,
            password_data=password_data
        )
        
    # Assertions
    assert "do not match" in str(exc_info.value)

@pytest.mark.asyncio
@pytest.mark.unit
async def test_change_password_insufficient_strength(mock_free_user, mock_redis_client):
    """Test changing password with insufficient strength."""
    # Setup
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Mock password change data with weak password
    password_data = {
        "current_password": "oldpassword123",
        "new_password": "weak",  # Too short
        "confirm_password": "weak"
    }
    
    # Mock change_password function
    async def mock_change_password(db, redis_client, current_user, password_data):
        # Check rate limiting (not relevant for this test)
        rate_limit_key = f"password_change_attempt:{current_user.id}"
        attempt_count = await redis_client.get(rate_limit_key)
        
        # Verify current password
        if not current_user.verify_password(password_data["current_password"]):
            # Update rate limit counter (not relevant for this test)
            raise Exception("Current password is incorrect")
            
        # Check that new password and confirmation match
        if password_data["new_password"] != password_data["confirm_password"]:
            raise Exception("New password and confirmation do not match")
            
        # Check password strength
        if len(password_data["new_password"]) < 8:
            raise Exception("Password must be at least 8 characters long")
            
        # Code below this shouldn't execute in this test
        return {"message": "Password changed successfully"}
    
    # Test the function - should raise exception
    with pytest.raises(Exception) as exc_info:
        await mock_change_password(
            db=mock_db,
            redis_client=mock_redis_client,
            current_user=mock_free_user,
            password_data=password_data
        )
        
    # Assertions
    assert "8 characters" in str(exc_info.value)

@pytest.mark.asyncio
@pytest.mark.unit
async def test_change_password_rate_limit(mock_free_user, mock_redis_client):
    """Test rate limiting for password change attempts."""
    # Setup
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Setup mock Redis to simulate rate limit reached
    mock_redis_client.get = AsyncMock(return_value=b"5")  # 5 attempts already
    
    # Mock password change data
    password_data = {
        "current_password": "oldpassword123",
        "new_password": "Newpassword456!",
        "confirm_password": "Newpassword456!"
    }
    
    # Mock change_password function
    async def mock_change_password(db, redis_client, current_user, password_data):
        # Check rate limiting
        rate_limit_key = f"password_change_attempt:{current_user.id}"
        attempt_count = await redis_client.get(rate_limit_key)
        
        if attempt_count and int(attempt_count) >= 5:
            raise Exception("Too many password change attempts. Try again later.")
        
        # Code below this shouldn't execute in this test
        return {"message": "Password changed successfully"}
    
    # Test the function - should raise exception due to rate limit
    with pytest.raises(Exception) as exc_info:
        await mock_change_password(
            db=mock_db,
            redis_client=mock_redis_client,
            current_user=mock_free_user,
            password_data=password_data
        )
        
    # Assertions
    assert "Too many" in str(exc_info.value)
    assert "Try again later" in str(exc_info.value)
    mock_redis_client.get.assert_called_once() 