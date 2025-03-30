"""
Redis client configuration and dependency injection.

This module provides the Redis client configuration and dependency injection
for the application.
"""

from typing import AsyncGenerator
import redis.asyncio as redis
from fastapi import Depends

from app.core.config import settings
from app.core.redis_mock import MockRedis

async def get_redis_client() -> AsyncGenerator[redis.Redis, None]:
    """
    FastAPI dependency that provides a Redis client.
    Uses MockRedis in development/testing environments.
    """
    if settings.ENVIRONMENT.lower() in ("development", "testing"):
        client = MockRedis()
    else:
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    
    try:
        yield client
    finally:
        await client.aclose() 