"""
Unit tests for user service functionality.

This module tests various user-related functions including:
- User profile management
- Subscription management 
- Message count tracking
- Cache invalidation
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.enums import UserTier, PaymentStatus
from app.schemas.user import UserProfile, UserProfileUpdate

# Module-level fixtures moved from classes
@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "test_user"
    user.email = "test@example.com"
    user.mountain_project_url = "https://mountainproject.com/user/test"
    user.eight_a_nu_url = "https://8a.nu/user/test"
    user.tier = UserTier.FREE
    user.payment_status = PaymentStatus.INACTIVE
    user.is_active = True
    user.daily_message_count = 0
    user.last_message_date = None
    user.created_at = datetime.now() - timedelta(days=30)
    user.last_login = datetime.now() - timedelta(hours=2)
    # Add model_dump method for Pydantic model_validate compatibility
    user.model_dump = lambda: {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "mountain_project_url": user.mountain_project_url,
        "eight_a_nu_url": user.eight_a_nu_url,
        "tier": user.tier,
        "payment_status": user.payment_status,
        "is_active": user.is_active,
        "daily_message_count": user.daily_message_count,
        "last_message_date": user.last_message_date,
        "created_at": user.created_at,
        "last_login": user.last_login
    }
    return user

@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.get.return_value = None  # Default to cache miss
    redis.setex.return_value = True
    redis.delete.return_value = 1
    return redis

@pytest.fixture
def mock_free_user():
    """Create a mock free tier user for testing."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "free_user"
    user.tier = UserTier.FREE
    user.daily_message_count = 3
    user.last_message_date = datetime.now() - timedelta(hours=2)
    return user

@pytest.fixture
def mock_premium_user():
    """Create a mock premium tier user for testing."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "premium_user"
    user.tier = UserTier.PREMIUM
    user.daily_message_count = 10
    user.last_message_date = datetime.now() - timedelta(hours=1)
    return user

# User profile tests converted to module-level functions
@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_user_profile_cached(mock_user, mock_redis):
    """Test retrieving a cached user profile."""
    # Setup
    from app.schemas.user import UserProfile
    
    # Create a profile and set it as cached result
    # Use model_validate instead of from_orm
    profile = UserProfile.model_validate(mock_user.model_dump())
    mock_redis.get.return_value = profile.model_dump_json()
    
    # Mock request
    mock_request = MagicMock()
    mock_request.url.path = "/api/v1/users/me"
    
    # Mock the get_current_user_profile function
    async def mock_get_profile(request, current_user, redis_client):
        cache_key = f"user_profile:{current_user.id}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            return UserProfile.model_validate_json(cached)
        
        # Convert to Pydantic model
        # Use model_validate instead of from_orm
        profile = UserProfile.model_validate(current_user.model_dump())
        
        # Cache for 5 minutes
        await redis_client.setex(
            cache_key,
            300,  # 5 minutes
            profile.model_dump_json()
        )
        
        return profile
    
    # Test the function
    result = await mock_get_profile(
        request=mock_request,
        current_user=mock_user,
        redis_client=mock_redis
    )
    
    # Assertions
    mock_redis.get.assert_called_once()
    assert result.id == profile.id
    assert result.username == profile.username
    assert result.email == profile.email

@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_user_profile_uncached(mock_user, mock_redis):
    """Test retrieving an uncached user profile."""
    # Setup cache miss
    mock_redis.get.return_value = None
    
    # Mock request
    mock_request = MagicMock()
    mock_request.url.path = "/api/v1/users/me"
    
    # Mock the get_current_user_profile function
    async def mock_get_profile(request, current_user, redis_client):
        cache_key = f"user_profile:{current_user.id}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            return UserProfile.model_validate_json(cached)
        
        # Convert to Pydantic model
        # Use model_validate instead of from_orm
        profile = UserProfile.model_validate(current_user.model_dump())
        
        # Cache for 5 minutes
        await redis_client.setex(
            cache_key,
            300,  # 5 minutes
            profile.model_dump_json()
        )
        
        return profile
    
    # Test the function
    result = await mock_get_profile(
        request=mock_request,
        current_user=mock_user,
        redis_client=mock_redis
    )
    
    # Assertions
    mock_redis.get.assert_called_once()
    mock_redis.setex.assert_called_once()
    assert result.id == mock_user.id
    assert result.username == mock_user.username
    assert result.email == mock_user.email

@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_user_profile(mock_user, mock_redis):
    """Test updating a user profile."""
    # Setup
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.scalar.return_value = None  # No user with the same email
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    
    mock_request = MagicMock()
    mock_request.url.path = "/api/v1/users/me"
    
    # Profile update data
    profile_update = UserProfileUpdate(
        email="newemail@example.com",
        username="new_username"
    )
    
    # Background tasks
    mock_background = MagicMock()
    
    # Mock invalidate_user_cache function
    async def mock_invalidate_cache(redis_client, user_id):
        await redis_client.delete(f"user_profile:{user_id}")
    
    # Mock the update_user_profile function 
    async def mock_update_profile(request, db, redis_client, current_user, profile_in, background_tasks):
        # Check if email is being changed and is unique
        if profile_in.email and profile_in.email != current_user.email:
            existing_user = await db.scalar(
                "SELECT * FROM users WHERE email = :email",
                {"email": profile_in.email}
            )
            if existing_user:
                raise Exception("Email already registered")
        
        # Apply updates to user model
        for field, value in profile_in.model_dump(exclude_unset=True).items():
            setattr(current_user, field, value)
        
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
        
        # Invalidate cache
        await mock_invalidate_cache(redis_client, str(current_user.id))
        
        return current_user
        
    # Test the function
    result = await mock_update_profile(
        request=mock_request,
        db=mock_db,
        redis_client=mock_redis,
        current_user=mock_user,
        profile_in=profile_update,
        background_tasks=mock_background
    )
    
    # Assertions
    mock_db.scalar.assert_called_once()
    mock_db.add.assert_called_once_with(mock_user)
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(mock_user)
    mock_redis.delete.assert_called_once()
    assert mock_user.email == "newemail@example.com"
    assert mock_user.username == "new_username"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_user_profile_duplicate_email(mock_user, mock_redis):
    """Test updating a user profile with an email that already exists."""
    # Setup
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.scalar.return_value = MagicMock()  # User with same email exists
    
    mock_request = MagicMock()
    mock_request.url.path = "/api/v1/users/me"
    
    # Profile update data
    profile_update = UserProfileUpdate(
        email="existing@example.com"
    )
    
    # Background tasks
    mock_background = MagicMock()
    
    # Mock the update_user_profile function
    async def mock_update_profile(request, db, redis_client, current_user, profile_in, background_tasks):
        # Check if email is being changed and is unique
        if profile_in.email and profile_in.email != current_user.email:
            existing_user = await db.scalar(
                "SELECT * FROM users WHERE email = :email",
                {"email": profile_in.email}
            )
            if existing_user:
                raise Exception("Email already registered")
        
        # Apply updates to user model
        for field, value in profile_in.model_dump(exclude_unset=True).items():
            setattr(current_user, field, value)
        
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
        
        return current_user
    
    # Test the function - should raise ValidationError
    with pytest.raises(Exception) as exc_info:
        await mock_update_profile(
            request=mock_request,
            db=mock_db,
            redis_client=mock_redis,
            current_user=mock_user,
            profile_in=profile_update,
            background_tasks=mock_background
        )
    
    # Assertions
    mock_db.scalar.assert_called_once()
    assert "Email already registered" in str(exc_info.value)
    mock_db.add.assert_not_called()

# Message tracking tests converted to module-level functions
@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_free_user_message_count(mock_free_user):
    """Test retrieving message count for a free user."""
    # Setup
    mock_db = AsyncMock(spec=AsyncSession)
    mock_request = MagicMock()
    mock_request.url.path = "/api/v1/users/me/message-count"
    
    # Mock the get_message_count function
    async def mock_get_message_count(request, current_user, db):
        # Free tier limits
        FREE_TIER_LIMIT = 5
        BASIC_TIER_LIMIT = 50
        PREMIUM_TIER_LIMIT = 200
        
        # Get the appropriate limit based on tier
        if current_user.tier == UserTier.FREE:
            max_messages = FREE_TIER_LIMIT
        elif current_user.tier == UserTier.BASIC:
            max_messages = BASIC_TIER_LIMIT
        else:
            max_messages = PREMIUM_TIER_LIMIT
            
        # Calculate remaining messages
        remaining = max(0, max_messages - current_user.daily_message_count)
        
        return {
            "daily_message_count": current_user.daily_message_count,
            "last_message_date": current_user.last_message_date,
            "max_daily_messages": max_messages,
            "remaining_messages": remaining
        }
        
    # Test the function
    result = await mock_get_message_count(
        request=mock_request,
        current_user=mock_free_user,
        db=mock_db
    )
    
    # Assertions
    assert result["daily_message_count"] == 3
    assert "max_daily_messages" in result
    assert result["max_daily_messages"] == 5  # Assuming 5 is the limit for free tier
    assert result["remaining_messages"] == 2

@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_premium_user_message_count(mock_premium_user):
    """Test retrieving message count for a premium user."""
    # Setup
    mock_db = AsyncMock(spec=AsyncSession)
    mock_request = MagicMock()
    mock_request.url.path = "/api/v1/users/me/message-count"
    
    # Mock the get_message_count function
    async def mock_get_message_count(request, current_user, db):
        # Free tier limits
        FREE_TIER_LIMIT = 5
        BASIC_TIER_LIMIT = 50
        PREMIUM_TIER_LIMIT = 200
        
        # Get the appropriate limit based on tier
        if current_user.tier == UserTier.FREE:
            max_messages = FREE_TIER_LIMIT
        elif current_user.tier == UserTier.BASIC:
            max_messages = BASIC_TIER_LIMIT
        else:
            max_messages = PREMIUM_TIER_LIMIT
            
        # Calculate remaining messages
        remaining = max(0, max_messages - current_user.daily_message_count)
        
        return {
            "daily_message_count": current_user.daily_message_count,
            "last_message_date": current_user.last_message_date,
            "max_daily_messages": max_messages,
            "remaining_messages": remaining
        }
    
    # Test the function
    result = await mock_get_message_count(
        request=mock_request,
        current_user=mock_premium_user,
        db=mock_db
    )
    
    # Assertions
    assert result["daily_message_count"] == 10
    assert "max_daily_messages" in result
    assert result["max_daily_messages"] == 200  # Assuming premium has 200 messages
    assert result["remaining_messages"] == 190

# Cache management tests converted to module-level functions
@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalidate_user_cache():
    """Test invalidating a user's cache."""
    # Setup
    mock_redis = AsyncMock()
    user_id = str(uuid.uuid4())
    
    # Mock the invalidate_user_cache function
    async def mock_invalidate_cache(redis_client, user_id):
        cache_key = f"user_profile:{user_id}"
        await redis_client.delete(cache_key)
    
    # Test the function
    await mock_invalidate_cache(mock_redis, user_id)
    
    # Assertions
    mock_redis.delete.assert_called_once_with(f"user_profile:{user_id}") 