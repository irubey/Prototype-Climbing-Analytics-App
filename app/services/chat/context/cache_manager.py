from typing import Dict, Optional, Union
import json
from datetime import datetime, timedelta
import redis
from redis.client import Redis
from redis.exceptions import RedisError

class CacheManager:
    """
    Manages Redis caching for context data with TTL and invalidation strategies.
    Handles storage, retrieval, and invalidation of context data in Redis.
    """

    def __init__(
        self,
        redis_client: Redis,
        ttl_seconds: int = 3600,  # 1 hour default TTL
        prefix: str = "context:"
    ):
        """
        Initialize the cache manager.
        
        Args:
            redis_client: Redis client instance
            ttl_seconds: Cache TTL in seconds (default 1 hour)
            prefix: Key prefix for context data in Redis
        """
        self.redis = redis_client
        self.ttl = ttl_seconds
        self.prefix = prefix

    def _build_key(self, user_id: int, conversation_id: Optional[int] = None) -> str:
        """
        Builds a Redis key for the context data.
        
        Args:
            user_id: User ID
            conversation_id: Optional conversation ID
            
        Returns:
            Redis key string
        """
        base_key = f"{self.prefix}{user_id}"
        return f"{base_key}:{conversation_id}" if conversation_id else base_key

    def _build_invalidation_pattern(self, user_id: int) -> str:
        """
        Builds a pattern for invalidating all user's context keys.
        
        Args:
            user_id: User ID
            
        Returns:
            Redis key pattern
        """
        return f"{self.prefix}{user_id}:*"

    async def get_context(
        self,
        user_id: int,
        conversation_id: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Retrieves context data from cache.
        
        Args:
            user_id: User ID
            conversation_id: Optional conversation ID
            
        Returns:
            Cached context data or None if not found
        """
        try:
            key = self._build_key(user_id, conversation_id)
            cached_data = self.redis.get(key)
            
            if cached_data:
                return json.loads(cached_data)
            return None
            
        except (RedisError, json.JSONDecodeError) as e:
            # Log error but don't raise - treat as cache miss
            print(f"Cache retrieval error: {str(e)}")  # Replace with proper logging
            return None

    async def set_context(
        self,
        user_id: int,
        context_data: Dict,
        conversation_id: Optional[int] = None
    ) -> bool:
        """
        Stores context data in cache with TTL.
        
        Args:
            user_id: User ID
            context_data: Context data to cache
            conversation_id: Optional conversation ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._build_key(user_id, conversation_id)
            serialized_data = json.dumps(context_data, default=str)
            
            # Set with TTL
            return bool(self.redis.setex(
                name=key,
                time=self.ttl,
                value=serialized_data
            ))
            
        except (RedisError, TypeError) as e:
            print(f"Cache storage error: {str(e)}")  # Replace with proper logging
            return False

    async def invalidate_context(
        self,
        user_id: int,
        conversation_id: Optional[int] = None
    ) -> bool:
        """
        Invalidates cached context data.
        
        Args:
            user_id: User ID
            conversation_id: Optional conversation ID. If None, invalidates all user's contexts
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if conversation_id:
                # Invalidate specific conversation context
                key = self._build_key(user_id, conversation_id)
                return bool(self.redis.delete(key))
            else:
                # Invalidate all user's contexts
                pattern = self._build_invalidation_pattern(user_id)
                keys = self.redis.keys(pattern)
                if keys:
                    return bool(self.redis.delete(*keys))
            return True
            
        except RedisError as e:
            print(f"Cache invalidation error: {str(e)}")  # Replace with proper logging
            return False

    async def refresh_ttl(
        self,
        user_id: int,
        conversation_id: Optional[int] = None
    ) -> bool:
        """
        Refreshes TTL for cached context data.
        
        Args:
            user_id: User ID
            conversation_id: Optional conversation ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._build_key(user_id, conversation_id)
            # Only refresh if key exists
            if self.redis.exists(key):
                return bool(self.redis.expire(key, self.ttl))
            return False
            
        except RedisError as e:
            print(f"TTL refresh error: {str(e)}")  # Replace with proper logging
            return False

    async def get_or_set_context(
        self,
        user_id: int,
        conversation_id: Optional[int],
        context_generator: callable
    ) -> Optional[Dict]:
        """
        Retrieves context from cache or generates and caches it if not found.
        
        Args:
            user_id: User ID
            conversation_id: Optional conversation ID
            context_generator: Async callable that generates context data
            
        Returns:
            Context data (from cache or newly generated)
        """
        # Try to get from cache first
        cached_context = await self.get_context(user_id, conversation_id)
        if cached_context:
            return cached_context
            
        try:
            # Generate new context
            new_context = await context_generator()
            if new_context:
                # Cache the new context
                await self.set_context(user_id, new_context, conversation_id)
            return new_context
            
        except Exception as e:
            print(f"Context generation error: {str(e)}")  # Replace with proper logging
            return None

    async def update_context(
        self,
        user_id: int,
        update_data: Dict,
        conversation_id: Optional[int] = None,
        merge: bool = True
    ) -> bool:
        """
        Updates cached context data, optionally merging with existing data.
        
        Args:
            user_id: User ID
            update_data: New data to update/merge
            conversation_id: Optional conversation ID
            merge: Whether to merge with existing data or replace entirely
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._build_key(user_id, conversation_id)
            
            if merge:
                # Get existing data
                existing_data = await self.get_context(user_id, conversation_id)
                if existing_data:
                    # Deep merge the dictionaries
                    merged_data = self._deep_merge(existing_data, update_data)
                    return await self.set_context(user_id, merged_data, conversation_id)
                    
            # Set new data directly if not merging or no existing data
            return await self.set_context(user_id, update_data, conversation_id)
            
        except Exception as e:
            print(f"Context update error: {str(e)}")  # Replace with proper logging
            return False

    def _deep_merge(self, dict1: Dict, dict2: Dict) -> Dict:
        """
        Deep merges two dictionaries, recursively updating nested structures.
        
        Args:
            dict1: Base dictionary
            dict2: Dictionary to merge (takes precedence)
            
        Returns:
            Merged dictionary
        """
        merged = dict1.copy()
        
        for key, value in dict2.items():
            if (
                key in merged and 
                isinstance(merged[key], dict) and 
                isinstance(value, dict)
            ):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
                
        return merged
