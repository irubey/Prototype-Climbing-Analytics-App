"""
Mock Redis implementation for development environments.

This module provides an in-memory mock implementation of Redis for development
and testing purposes. It implements the most commonly used Redis methods
and stores values in memory.
"""

import asyncio
from typing import Dict, List, Optional, Any, Union
from unittest.mock import AsyncMock
import time as time_module  # Renamed import to avoid parameter naming conflicts

class MockRedis:
    """
    In-memory mock implementation of Redis for development and testing.
    Implements commonly used Redis methods with reasonable defaults.
    """
    
    def __init__(self):
        """Initialize the mock Redis with empty storage."""
        self._storage: Dict[str, Any] = {}
        self._expirations: Dict[str, float] = {}
        
    async def ping(self):
        """Test connection (always returns True)."""
        return True
        
    async def aclose(self):
        """Close the connection (no-op for mock implementation)."""
        # This is a no-op for the mock implementation since there's no real connection
        # Just clear the storage to simulate connection closure
        self._storage.clear()
        self._expirations.clear()
        return True
        
    async def get(self, key: str) -> Optional[bytes]:
        """Get a value from storage."""
        self._check_expiration(key)
        value = self._storage.get(key)
        # Redis returns bytes, so convert string to bytes
        if isinstance(value, str):
            return value.encode('utf-8')
        return value
        
    async def set(self, key: str, value: Any) -> bool:
        """Set a value in storage."""
        self._storage[key] = value
        return True
        
    async def setex(self, name, time=None, time_seconds=None, time_param=None, value=None, *args, **kwargs):
        """Set a value with expiration time."""
        # Handle both positional and keyword arguments
        seconds = None
        val = None
        
        # First check explicit keyword args
        if time is not None:
            seconds = time
        elif time_seconds is not None:
            seconds = time_seconds
        elif time_param is not None:
            seconds = time_param
            
        if value is not None:
            val = value
        
        # Handle positional args passed after name
        if seconds is None and args and len(args) >= 1:
            seconds = args[0]
            
        if val is None and args and len(args) >= 2:
            val = args[1]
            
        # Handle any other keyword args that might be passed
        if seconds is None and 'time' in kwargs:
            seconds = kwargs['time']
            
        if val is None and 'value' in kwargs:
            val = kwargs['value']
            
        # Ensure we have both seconds and value
        if seconds is not None and val is not None:
            self._storage[name] = val
            self._expirations[name] = time_module.time() + seconds
            return True
            
        # If we get here, we couldn't find the parameters we need
        raise ValueError(f"Invalid parameters for setex - need time and value. Got args={args}, kwargs={kwargs}")
        
    async def delete(self, *keys) -> int:
        """Delete keys from storage, return number of keys deleted."""
        count = 0
        for key in keys:
            if key in self._storage:
                del self._storage[key]
                self._expirations.pop(key, None)
                count += 1
        return count
        
    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        self._check_expiration(key)
        return key in self._storage
        
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key."""
        if key in self._storage:
            self._expirations[key] = time_module.time() + seconds
            return True
        return False
        
    async def incr(self, key: str) -> int:
        """Increment a numeric value, create if doesn't exist."""
        self._check_expiration(key)
        if key not in self._storage:
            self._storage[key] = 0
        
        # Try to parse as int if it's bytes or string
        if isinstance(self._storage[key], bytes):
            self._storage[key] = int(self._storage[key].decode('utf-8'))
        elif isinstance(self._storage[key], str):
            self._storage[key] = int(self._storage[key])
            
        self._storage[key] += 1
        return self._storage[key]
        
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern (simple glob support)."""
        self._check_all_expirations()
        if pattern == "*":
            return list(self._storage.keys())
            
        # Very simple glob pattern matching
        if pattern.startswith("*") and pattern.endswith("*"):
            substr = pattern[1:-1]
            return [k for k in self._storage.keys() if substr in k]
        elif pattern.startswith("*"):
            suffix = pattern[1:]
            return [k for k in self._storage.keys() if k.endswith(suffix)]
        elif pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self._storage.keys() if k.startswith(prefix)]
            
        # Exact match
        return [k for k in self._storage.keys() if k == pattern]
        
    def pipeline(self):
        """Return a pipeline object for batched operations."""
        return MockRedisPipeline(self)
        
    def _check_expiration(self, key: str) -> None:
        """Check if a key has expired and remove it if necessary."""
        if key in self._expirations:
            if time_module.time() > self._expirations[key]:
                del self._storage[key]
                del self._expirations[key]
            
    def _check_all_expirations(self) -> None:
        """Check all keys for expiration."""
        current_time = time_module.time()
        expired_keys = [
            key for key, expiry in self._expirations.items() 
            if current_time > expiry
        ]
        
        for key in expired_keys:
            del self._storage[key]
            del self._expirations[key]


class MockRedisPipeline:
    """Mock Redis pipeline for batched operations."""
    
    def __init__(self, redis_instance: MockRedis):
        """Initialize with parent Redis instance and empty command queue."""
        self._redis = redis_instance
        self._commands = []
        
    def incr(self, key: str):
        """Add incr command to pipeline."""
        self._commands.append(('incr', key))
        return self
        
    def expire(self, key: str, seconds: int):
        """Add expire command to pipeline."""
        self._commands.append(('expire', key, seconds))
        return self
        
    def delete(self, *keys):
        """Add delete command to pipeline."""
        self._commands.append(('delete', *keys))
        return self
        
    def get(self, key: str):
        """Add get command to pipeline."""
        self._commands.append(('get', key))
        return self
        
    def set(self, key: str, value: Any):
        """Add set command to pipeline."""
        self._commands.append(('set', key, value))
        return self
        
    def setex(self, name, time=None, value=None, *args, **kwargs):
        """Add setex command to pipeline."""
        # For pipeline commands, we need to store the args in the same format
        # that they'll be passed to the actual method
        
        # If using positional args
        if time is not None and value is not None:
            self._commands.append(('setex', name, time, value))
        # If using positional args via *args
        elif args and len(args) >= 2:
            self._commands.append(('setex', name, args[0], args[1]))
        # If using kwargs
        elif 'time' in kwargs and 'value' in kwargs:
            self._commands.append(('setex', name, kwargs['time'], kwargs['value']))
        else:
            # Store whatever we have and let the method handle it
            cmd_args = [name]
            if time is not None:
                cmd_args.append(time)
            if value is not None:
                cmd_args.append(value)
            cmd_args.extend(args)
            
            self._commands.append(('setex', *cmd_args))
            
        return self
        
    async def execute(self) -> List[Any]:
        """Execute all commands in the pipeline and return results."""
        results = []
        
        for cmd in self._commands:
            method_name = cmd[0]
            args = cmd[1:]
            
            method = getattr(self._redis, method_name)
            try:
                result = await method(*args)
                results.append(result)
            except Exception as e:
                print(f"Error executing pipeline command {method_name}: {str(e)}")
                # Add a default result that makes sense for the command
                if method_name == 'incr':
                    results.append(1)  # Default to 1 for increment
                elif method_name == 'expire':
                    results.append(True)  # Default to success for expire
                elif method_name == 'delete':
                    results.append(1)  # Default to 1 key deleted
                else:
                    results.append(None)  # Default to None for other commands
                
        # Clear commands after execution
        self._commands = []
        return results 