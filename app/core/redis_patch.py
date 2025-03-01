"""
Redis monkey patching module.

This module replaces the Redis client creation functions with versions that return
our MockRedis implementation in development/testing environments.
This ensures that all Redis interactions across the application use the mock,
even if they bypass the get_redis() function.
"""

import sys
import logging
import importlib
from functools import wraps
from unittest.mock import patch
from app.core.config import settings

logger = logging.getLogger(__name__)

def apply_redis_patches():
    """
    Apply monkey patches to Redis library to ensure all connections
    use our MockRedis implementation in development/testing environments.
    """
    if settings.ENVIRONMENT.lower() not in ("development", "testing"):
        logger.info(f"Not applying Redis patches in {settings.ENVIRONMENT} environment")
        return
        
    # Import the real Redis module
    try:
        import redis.asyncio as asyncio_redis
        import redis  # Import sync Redis as well
        from app.core.redis_mock import MockRedis
        
        # Store the original from_url method (async)
        original_async_from_url = asyncio_redis.Redis.from_url
        
        @wraps(original_async_from_url)
        def patched_async_from_url(url, **kwargs):
            """
            Patched version of async Redis.from_url that returns a MockRedis instance
            instead of attempting real connections.
            """
            logger.info(f"Intercepted async Redis connection to {url} - using MockRedis instead")
            return MockRedis()
            
        # Replace the async from_url method
        asyncio_redis.Redis.from_url = patched_async_from_url
        
        # Patch the sync from_url method too
        original_sync_from_url = redis.Redis.from_url
        
        @wraps(original_sync_from_url)
        def patched_sync_from_url(url, **kwargs):
            """
            Patched version of sync Redis.from_url that returns a MockRedis instance
            instead of attempting real connections.
            """
            logger.info(f"Intercepted sync Redis connection to {url} - using MockRedis instead")
            return MockRedis()
            
        # Replace the sync from_url method
        redis.Redis.from_url = patched_sync_from_url
        
        # Patch the async Redis constructor
        original_async_init = asyncio_redis.Redis.__init__
        
        @wraps(original_async_init)
        def patched_async_init(self, *args, **kwargs):
            """
            Patched version of async Redis.__init__ that creates a MockRedis instance
            instead of a real Redis connection.
            """
            logger.info("Intercepted async Redis instantiation - using MockRedis instead")
            # Initialize self as if it were a MockRedis instance
            MockRedis.__init__(self)
            
        # Apply the async init patch
        asyncio_redis.Redis.__init__ = patched_async_init
        
        # Patch the sync Redis constructor
        original_sync_init = redis.Redis.__init__
        
        @wraps(original_sync_init)
        def patched_sync_init(self, *args, **kwargs):
            """
            Patched version of sync Redis.__init__ that creates a MockRedis instance
            instead of a real Redis connection.
            """
            logger.info("Intercepted sync Redis instantiation - using MockRedis instead") 
            # Initialize self as if it were a MockRedis instance
            MockRedis.__init__(self)
            
        # Apply the sync init patch
        redis.Redis.__init__ = patched_sync_init
        
        # Also patch the ConnectionPool to prevent direct connections
        if hasattr(asyncio_redis, 'ConnectionPool'):
            original_pool_init = asyncio_redis.ConnectionPool.__init__
            
            @wraps(original_pool_init)
            def patched_pool_init(self, *args, **kwargs):
                logger.info("Intercepted Redis ConnectionPool - replaced with mock")
                # Just create an empty object - the connections won't be used
                pass
                
            asyncio_redis.ConnectionPool.__init__ = patched_pool_init
            
        logger.info("Successfully applied Redis patches for development/testing")
        
    except ImportError as e:
        logger.warning(f"Could not apply Redis patches: {str(e)}")
    except Exception as e:
        logger.error(f"Error applying Redis patches: {str(e)}") 