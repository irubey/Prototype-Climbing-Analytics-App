"""
Tests for the chat context manager functionality.

This module tests the context management components that store and retrieve
context data for the chat service, including caching and orchestration.
"""

import pytest
import pytest_asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.services.chat.context.cache_manager import CacheManager
from app.services.chat.context.orchestrator import ContextOrchestrator

# Module-level fixtures

@pytest_asyncio.fixture
async def mock_redis_client():
    """Create a mock Redis client for testing."""
    # Use MagicMock since the Redis client is not async in the implementation
    redis = MagicMock()
    
    # Set up methods with normal return values (not AsyncMock)
    redis.get.return_value = None  # Default to cache miss
    redis.setex.return_value = True
    redis.delete.return_value = 1  # 1 key deleted
    redis.keys.return_value = []  # No keys by default
    redis.exists.return_value = False  # Key doesn't exist by default
    redis.expire.return_value = True  # TTL update success
    
    return redis

@pytest_asyncio.fixture
async def cache_manager(mock_redis_client):
    """Create a CacheManager instance with mocked Redis."""
    manager = CacheManager(
        redis_client=mock_redis_client,
        ttl_seconds=3600,
        prefix="test:"  # Add colon to match implementation
    )
    return manager

@pytest_asyncio.fixture
async def mocked_components():
    """Create mocked components for context orchestrator testing."""
    return {
        "db_session": AsyncMock(),
        "redis_client": MagicMock(),  # Use MagicMock for Redis
        "cache_ttl": 3600,
        "cache_prefix": "test:"
    }

@pytest_asyncio.fixture
async def context_orchestrator(mocked_components):
    """Create a ContextOrchestrator with mocked components."""
    orchestrator = ContextOrchestrator(
        db_session=mocked_components["db_session"],
        redis_client=mocked_components["redis_client"],
        cache_ttl=mocked_components["cache_ttl"],
        cache_prefix=mocked_components["cache_prefix"]
    )
    # Mock the data_aggregator attributes that are accessed in tests
    orchestrator.data_aggregator = AsyncMock()
    orchestrator.context_enhancer = AsyncMock()
    
    # Replace _generate_context with an AsyncMock
    orchestrator._generate_context = AsyncMock()
    
    return orchestrator

@pytest_asyncio.fixture
async def sample_context():
    """Create a sample context for testing."""
    return {
        "user_id": "user123",
        "profile": {
            "name": "Test User",
            "experience_level": "intermediate",
            "years_climbing": 3,
            "preferred_disciplines": ["sport", "boulder"]
        },
        "stats": {
            "highest_grade_sport": "5.12a",
            "highest_grade_boulder": "V6",
            "total_climbs": 235
        },
        "recent_activity": {
            "last_session_date": "2023-08-15",
            "sessions_last_month": 12,
            "recent_projects": ["Project X", "The Arete"]
        },
        "last_updated": "2023-08-20T14:30:00Z"
    }

# Cache Manager Tests

@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_key(cache_manager):
    """Test key building logic."""
    user_id = "user123"
    
    # Build key with default namespace
    key = cache_manager._build_key(user_id)
    assert key == "test:user123"
    
    # Test key with conversation_id if supported
    try:
        conversation_id = "conv456"
        key = cache_manager._build_key(user_id, conversation_id)
        assert "user123" in key
        assert "conv456" in key
    except TypeError:
        # If not supported, this test is skipped
        pass

@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_context_not_found():
    """Test getting context when not in cache."""
    # Use regular MagicMock since Redis client is not async in the implementation
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    
    # Create cache manager with the mock
    cache_manager = CacheManager(redis_client=mock_redis, ttl_seconds=3600, prefix="test:")
    
    # Get non-existent context
    context = await cache_manager.get_context("user123")
    
    # Verify result is None
    assert context is None
    
    # Verify Redis was called with correct key
    mock_redis.get.assert_called_once()
    key = mock_redis.get.call_args[0][0]
    assert key == "test:user123"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_context_found():
    """Test getting context that exists in cache."""
    # Create mock cached data
    cached_data = {
        "summary": "Intermediate climber",
        "recent_climbs": ["5.10a", "5.11b"],
        "grade_level": "intermediate"
    }
    
    # Use regular MagicMock since Redis client is not async in the implementation
    mock_redis = MagicMock()
    mock_redis.get.return_value = json.dumps(cached_data)
    
    # Create cache manager with the mock
    cache_manager = CacheManager(redis_client=mock_redis, ttl_seconds=3600, prefix="test:")
    
    # Get existing context
    context = await cache_manager.get_context("user123")
    
    # Verify context matches cached data
    assert context == cached_data
    
    # Verify Redis was called with correct key
    mock_redis.get.assert_called_once()
    key = mock_redis.get.call_args[0][0]
    assert key == "test:user123"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_context_json_error():
    """Test handling of JSON decode errors when getting context."""
    # Use regular MagicMock since Redis client is not async in the implementation
    mock_redis = MagicMock()
    mock_redis.get.return_value = "not valid json"
    
    # Create cache manager with the mock
    cache_manager = CacheManager(redis_client=mock_redis, ttl_seconds=3600, prefix="test:")
    
    # Get context with invalid JSON - should return None on error
    context = await cache_manager.get_context("user123")
    
    # Verify result is None (error case)
    assert context is None
    
    # Verify Redis was called
    mock_redis.get.assert_called_once()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_context():
    """Test setting context in cache."""
    # Create context data
    context_data = {
        "user_profile": {
            "experience": "advanced",
            "preferred_climbing_types": ["sport", "trad"]
        },
        "recent_climbs": [
            {"id": 1, "name": "Route 1", "grade": "5.12a"},
            {"id": 2, "name": "Route 2", "grade": "5.11c"}
        ]
    }
    
    # Use regular MagicMock since Redis client is not async in the implementation
    mock_redis = MagicMock()
    mock_redis.setex.return_value = True
    
    # Create cache manager with the mock
    cache_manager = CacheManager(redis_client=mock_redis, ttl_seconds=3600, prefix="test:")
    
    # Set context
    result = await cache_manager.set_context("user123", context_data)
    
    # Verify result
    assert result is True
    
    # Verify Redis was called
    mock_redis.setex.assert_called_once()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalidate_context_specific():
    """Test invalidating specific user context."""
    # Use regular MagicMock since Redis client is not async in the implementation
    mock_redis = MagicMock()
    mock_redis.keys.return_value = ["test:user123"]
    mock_redis.delete.return_value = 1
    
    # Create cache manager with the mock
    cache_manager = CacheManager(redis_client=mock_redis, ttl_seconds=3600, prefix="test:")
    
    # Invalidate context for specific user
    result = await cache_manager.invalidate_context("user123")
    
    # Verify result
    assert result is True
    
    # Verify Redis operations were called
    mock_redis.keys.assert_called_once()
    mock_redis.delete.assert_called_once()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_context_new():
    """Test updating context when none exists."""
    # Create a test instance with mock methods
    cache_manager = CacheManager(redis_client=MagicMock(), ttl_seconds=3600, prefix="test:")
    
    # Mock the methods directly on the instance
    cache_manager.get_context = AsyncMock(return_value=None)
    cache_manager.set_context = AsyncMock(return_value=True)
    
    # Update data
    update_data = {
        "new_field": "new value",
        "nested": {"key": "value"}
    }
    
    # Update non-existent context
    result = await cache_manager.update_context("user123", update_data)
    
    # Verify result
    assert result is True
    
    # Verify methods called correctly
    cache_manager.get_context.assert_called_once()
    cache_manager.set_context.assert_called_once()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_context_merge():
    """Test updating existing context by merging data."""
    # Create a test instance with mock methods
    cache_manager = CacheManager(redis_client=MagicMock(), ttl_seconds=3600, prefix="test:")
    
    # Existing context
    existing_context = {
        "user_profile": {
            "experience": "intermediate",
            "preferred_climbing_types": ["sport"]
        },
        "stats": {
            "total_climbs": 50,
            "average_grade": "5.10b"
        }
    }
    
    # Mock the methods directly on the instance
    cache_manager.get_context = AsyncMock(return_value=existing_context)
    cache_manager.set_context = AsyncMock(return_value=True)
    
    # Update data
    update_data = {
        "user_profile": {
            "preferred_climbing_types": ["sport", "trad"],
            "new_field": "new value"
        },
        "recent_climbs": [
            {"id": 1, "name": "New Route", "grade": "5.11a"}
        ]
    }
    
    # Update existing context
    result = await cache_manager.update_context("user123", update_data)
    
    # Verify result
    assert result is True
    
    # Verify methods called correctly
    cache_manager.get_context.assert_called_once()
    cache_manager.set_context.assert_called_once()
    
    # Check the data being set includes both original and new fields
    set_context_args = cache_manager.set_context.call_args[0]
    merged_data = set_context_args[1]
    
    assert merged_data["user_profile"]["experience"] == "intermediate"
    assert "new_field" in merged_data["user_profile"]
    assert "recent_climbs" in merged_data

@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_context_replace():
    """Test replacing existing context instead of merging."""
    # Create a test instance with mock methods
    cache_manager = CacheManager(redis_client=MagicMock(), ttl_seconds=3600, prefix="test:")
    
    # Existing context
    existing_context = {
        "user_profile": {
            "experience": "intermediate",
            "preferred_climbing_types": ["sport"]
        },
        "stats": {
            "total_climbs": 50,
            "average_grade": "5.10b"
        }
    }
    
    # Mock the methods directly on the instance
    cache_manager.get_context = AsyncMock(return_value=existing_context)
    cache_manager.set_context = AsyncMock(return_value=True)
    
    # Complete replacement data
    replacement_data = {
        "user_profile": {
            "experience": "advanced",
            "preferred_climbing_types": ["trad", "alpine"]
        },
        "stats": {
            "total_climbs": 75,
            "average_grade": "5.11c",
            "projects_completed": 5
        }
    }
    
    # Replace context
    result = await cache_manager.update_context(
        "user123",
        replacement_data,
        merge=False  # Don't merge, replace
    )
    
    # Verify result
    assert result is True
    
    # Verify methods called correctly
    cache_manager.get_context.assert_not_called()  # Should not need existing data for replace
    cache_manager.set_context.assert_called_once()
    
    # Check the data being set is the replacement data
    set_context_args = cache_manager.set_context.call_args[0]
    set_data = set_context_args[1]
    assert set_data == replacement_data

@pytest.mark.unit
@pytest.mark.asyncio
async def test_refresh_ttl():
    """Test refreshing TTL for existing context."""
    # Use regular MagicMock since Redis client is not async in the implementation
    mock_redis = MagicMock()
    mock_redis.exists.return_value = True
    mock_redis.expire.return_value = True
    
    # Create cache manager with the mock
    cache_manager = CacheManager(redis_client=mock_redis, ttl_seconds=3600, prefix="test:")
    
    # Refresh TTL
    result = await cache_manager.refresh_ttl("user123")
    
    # Verify result
    assert result is True
    
    # Verify Redis calls
    mock_redis.exists.assert_called_once()
    mock_redis.expire.assert_called_once()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_refresh_ttl_not_exists():
    """Test refreshing TTL for non-existent context."""
    # Use regular MagicMock since Redis client is not async in the implementation
    mock_redis = MagicMock()
    mock_redis.exists.return_value = False
    
    # Create cache manager with the mock
    cache_manager = CacheManager(redis_client=mock_redis, ttl_seconds=3600, prefix="test:")
    
    # Refresh TTL
    result = await cache_manager.refresh_ttl("user123")
    
    # Verify result matches implementation - key point!
    assert result is False
    
    # Verify Redis calls
    mock_redis.exists.assert_called_once()
    mock_redis.expire.assert_not_called()

# Context Orchestrator Tests

@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_context_from_cache(context_orchestrator, mocked_components, sample_context):
    """Test getting context from cache when available."""
    # Set up the cache_manager in the orchestrator to return the sample context
    context_orchestrator.cache_manager.get_or_set_context = AsyncMock(return_value=sample_context)
    
    # Get context
    result = await context_orchestrator.get_context("user123")
    
    # Verify result matches sample context
    assert result == sample_context
    
    # Verify cache was checked
    context_orchestrator.cache_manager.get_or_set_context.assert_called_once()
    
    # Verify no data aggregation was performed
    assert context_orchestrator._generate_context.call_count == 0

@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_context_generate_new(context_orchestrator, mocked_components, sample_context):
    """Test generating new context when not in cache."""
    # Mock the get_or_set_context method to call the factory function
    async def mock_get_or_set(user_id, conversation_id=None, context_generator=None):
        if context_generator:
            return await context_generator()
        return None
        
    context_orchestrator.cache_manager.get_or_set_context = AsyncMock(side_effect=mock_get_or_set)
    context_orchestrator._generate_context.return_value = sample_context
    
    # Get context
    result = await context_orchestrator.get_context("user123")
    
    # Verify result
    assert result == sample_context
    
    # Verify context was generated
    assert context_orchestrator._generate_context.call_count > 0

@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_context_force_refresh(context_orchestrator, mocked_components, sample_context):
    """Test forcing context refresh even when cached."""
    # Configure mocks
    context_orchestrator.cache_manager.invalidate_context = AsyncMock(return_value=True)
    
    async def mock_get_or_set(user_id, conversation_id=None, context_generator=None):
        if context_generator:
            return await context_generator()
        return sample_context
        
    context_orchestrator.cache_manager.get_or_set_context = AsyncMock(side_effect=mock_get_or_set)
    context_orchestrator._generate_context.return_value = sample_context
    
    # Call get_context with force_refresh=True
    result = await context_orchestrator.get_context("user123", force_refresh=True)
    
    # Verify result
    assert result == sample_context
    
    # Verify invalidation
    context_orchestrator.cache_manager.invalidate_context.assert_called_once()
    
    # Verify get_or_set_context was called
    context_orchestrator.cache_manager.get_or_set_context.assert_called_once()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_relevance(context_orchestrator, mocked_components, sample_context):
    """Test updating context relevance through orchestrator."""
    # Add relevance to be returned in enhanced context
    enhanced_context = sample_context.copy()
    enhanced_context["relevance"] = {"score": 0.85}
    
    # Configure mocks
    context_orchestrator.context_enhancer = AsyncMock()
    context_orchestrator.context_enhancer.enhance_context = AsyncMock(return_value=enhanced_context)
    context_orchestrator.formatter = MagicMock()
    context_orchestrator.formatter.format_context = MagicMock(return_value=enhanced_context)
    context_orchestrator.cache_manager.update_context = AsyncMock(return_value=True)
    
    # Call update_relevance method
    query = "What are my climbing stats?"
    result = await context_orchestrator._update_relevance(sample_context, query, "user123")
    
    # Verify the enhance_context was called
    context_orchestrator.context_enhancer.enhance_context.assert_called_once()
    
    # Verify formatter was called
    context_orchestrator.formatter.format_context.assert_called_once()
    
    # Verify cache update operation
    context_orchestrator.cache_manager.update_context.assert_called_once()
    
    # Verify result has relevance
    assert "relevance" in result

@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_data_update(context_orchestrator, mocked_components, sample_context):
    """Test handling data updates that affect context."""
    # Configure mocks
    context_orchestrator.cache_manager.invalidate_context = AsyncMock(return_value=True)
    context_orchestrator._generate_context.return_value = sample_context
    context_orchestrator.cache_manager.set_context = AsyncMock(return_value=True)
    
    # Create update event
    update_event = {
        "type": "new_climb",
        "data": {
            "grade": "5.12b",
            "date": "2023-08-22"
        }
    }
    
    # Call handle_data_update
    result = await context_orchestrator.handle_data_update("user123", "new_climb", update_event)
    
    # Verify correct methods were called
    context_orchestrator.cache_manager.invalidate_context.assert_called_once()
    assert context_orchestrator._generate_context.call_count > 0
    context_orchestrator.cache_manager.set_context.assert_called_once()
    
    # Verify result
    assert result is True

@pytest.mark.unit
@pytest.mark.asyncio
async def test_refresh_context(context_orchestrator, mocked_components, sample_context):
    """Test context refresh functionality."""
    # Configure mocks
    context_orchestrator._generate_context.return_value = sample_context
    context_orchestrator.cache_manager.set_context = AsyncMock(return_value=True)
    
    # Call refresh
    result = await context_orchestrator.refresh_context("user123")
    
    # Verify generation occurred
    assert context_orchestrator._generate_context.call_count > 0
    
    # Verify cache was updated
    context_orchestrator.cache_manager.set_context.assert_called_once()
    
    # Verify result
    assert result is True 