"""
Redis and caching fixtures for testing.

This module provides fixtures for Redis clients, connections,
and caching-related functionality needed for tests.
"""

import pytest
import pytest_asyncio
from typing import AsyncGenerator
import redis.asyncio as redis
from unittest.mock import AsyncMock, MagicMock

from app.core.config import settings
from app.tests.config import test_settings


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[redis.Redis, None]:
    """
    Provide a Redis client for test functions.
    
    This fixture yields a Redis client that is automatically
    flushed after the test completes, ensuring no test data persists
    between tests.
    """
    # Create a Redis client for testing
    client = redis.Redis.from_url(
        url=settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )
    
    # Ensure the database is clean at the start
    await client.flushdb()
    
    # Yield the client for test use
    yield client
    
    # Clean up after the test
    await client.flushdb()
    await client.close()


@pytest_asyncio.fixture
async def mock_redis_client() -> AsyncGenerator[AsyncMock, None]:
    """
    Provide a mocked Redis client for tests that don't need actual Redis.
    
    This is useful for unit tests where we want to avoid the overhead
    of actual Redis connections, or for simulating specific Redis behaviors.
    """
    # Create a mock Redis client
    mock_client = AsyncMock(spec=redis.Redis)
    
    # Configure common mock methods
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    mock_client.delete.return_value = 1
    mock_client.exists.return_value = 0
    mock_client.incr.return_value = 1
    
    # Mock the hgetall method to return an empty dict by default
    mock_client.hgetall.return_value = {}
    
    # Use a real dictionary to simulate Redis hash storage
    hash_storage = {}
    
    async def mock_hset(key, field=None, value=None, mapping=None):
        if key not in hash_storage:
            hash_storage[key] = {}
        
        if mapping:
            hash_storage[key].update(mapping)
            return len(mapping)
        else:
            hash_storage[key][field] = value
            return 1
    
    async def mock_hget(key, field):
        if key not in hash_storage:
            return None
        return hash_storage[key].get(field)
    
    async def mock_hgetall(key):
        return hash_storage.get(key, {})
    
    # Assign the mock implementations
    mock_client.hset.side_effect = mock_hset
    mock_client.hget.side_effect = mock_hget
    mock_client.hgetall.side_effect = mock_hgetall
    
    yield mock_client


@pytest.fixture
def use_test_redis_client():
    """
    Fixture to patch the get_redis dependency with our test client.
    
    This fixture is used to override the standard Redis dependency
    in FastAPI endpoints for testing purposes.
    """
    async def override_get_redis() -> AsyncGenerator[redis.Redis, None]:
        client = redis.Redis.from_url(
            url=settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        yield client
        await client.close()
    
    return override_get_redis 