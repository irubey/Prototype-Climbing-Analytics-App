"""
Pytest configuration for Send Sage test suite - Enhanced Version.

This module provides core fixtures and configuration for the test suite.
Basic fixtures are always enabled, while more advanced fixtures are imported conditionally.
"""

import pytest
import pytest_asyncio
import os
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from pathlib import Path

# Import test settings
from app.tests.config import test_settings

# # Import application components
# from app.main import app
# from app.core.config import settings
# from app.db.session import sessionmanager

# Basic fixtures

@pytest.fixture
def event_loop():
    """Create an instance of the event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_data_dir() -> Path:
    """Return the path to the test data directory."""
    return test_settings.TEST_DATA_DIR

@pytest.fixture
def fixture_path():
    """Return a function to get the path to a fixture file."""
    def _fixture_path(fixture_name: str, format: str = "json") -> Path:
        return test_settings.TEST_DATA_DIR / f"{fixture_name}.{format}"
    return _fixture_path

# SQLAlchemy test helpers
@pytest.fixture
def create_async_mock_db():
    """
    Creates a properly configured AsyncMock for SQLAlchemy database operations.
    
    This fixture returns a factory function that can be used to create 
    AsyncMock objects that properly simulate SQLAlchemy AsyncSession behavior.
    """
    from unittest.mock import AsyncMock, MagicMock
    
    def _create_db(return_values=None):
        """
        Create a mock database session with configurable return values.
        
        Args:
            return_values: List of values to be returned by sequential execute calls
                           or a single value for a single execute call
        
        Returns:
            AsyncMock: Configured to properly handle SQLAlchemy query patterns
        """
        mock_db = AsyncMock()
        
        if return_values is None:
            # Default empty response
            mock_scalar = AsyncMock()
            mock_scalar.all.return_value = []
            mock_scalar.one_or_none.return_value = None
            mock_scalar.scalar_one_or_none.return_value = None
            
            mock_result = AsyncMock()
            mock_result.scalars.return_value = mock_scalar
            mock_result.all.return_value = []
            mock_result.scalar_one_or_none.return_value = None
            
            mock_db.execute.return_value = mock_result
        elif isinstance(return_values, list) and len(return_values) > 1:
            # Multiple sequential responses
            mock_results = []
            for value in return_values:
                mock_scalar = AsyncMock()
                mock_scalar.all.return_value = value if isinstance(value, list) else [value]
                mock_scalar.one_or_none.return_value = value[0] if isinstance(value, list) and value else value
                mock_scalar.scalar_one_or_none.return_value = value
                
                mock_result = AsyncMock()
                mock_result.scalars.return_value = mock_scalar
                mock_result.all.return_value = value if isinstance(value, list) else [value]
                mock_result.scalar_one_or_none.return_value = value
                
                mock_results.append(mock_result)
            
            mock_db.execute.side_effect = mock_results
        else:
            # Single response
            value = return_values[0] if isinstance(return_values, list) else return_values
            
            mock_scalar = AsyncMock()
            mock_scalar.all.return_value = value if isinstance(value, list) else [value]
            mock_scalar.one_or_none.return_value = value[0] if isinstance(value, list) and value else value
            mock_scalar.scalar_one_or_none.return_value = value
            
            mock_result = AsyncMock()
            mock_result.scalars.return_value = mock_scalar
            mock_result.all.return_value = value if isinstance(value, list) else [value]
            mock_result.scalar_one_or_none.return_value = value
            
            mock_db.execute.return_value = mock_result
        
        return mock_db
    
    return _create_db

@pytest.fixture
def mock_entity_factory():
    """
    Create a factory for mock entities that can properly handle attribute setting.
    
    This addresses the issue with trying to set __setattr__ on MagicMock objects.
    Instead, we create a dictionary-backed object that can be updated.
    """
    from unittest.mock import MagicMock
    
    def _create_mock_entity(entity_class, **attributes):
        """
        Create a mock entity with the specified attributes.
        
        Args:
            entity_class: The class to mock (e.g., User, UserTicks)
            **attributes: Initial attribute values
            
        Returns:
            MagicMock: A mock object with the specified attributes that can be updated
        """
        # Create a basic mock with the right spec
        mock_entity = MagicMock(spec=entity_class)
        
        # Store attributes in a separate dict
        attr_dict = attributes.copy()
        
        # Define custom descriptor methods that use the dict
        def _getattr(self, name):
            if name in attr_dict:
                return attr_dict[name]
            return super(MagicMock, self).__getattribute__(name)
        
        def _setattr(self, name, value):
            if name.startswith('_'):
                # Let mock handle its internal attributes
                super(MagicMock, self).__setattr__(name, value)
            else:
                # Store user attributes in our dict
                attr_dict[name] = value
        
        # Patch the mock's __getattribute__ method
        mock_entity.__getattribute__ = lambda name: _getattr(mock_entity, name)
        
        # We can't patch __setattr__ directly, so use configure_mock for initial values
        for key, value in attributes.items():
            if not key.startswith('_'):  # Skip private attributes
                setattr(mock_entity, key, value)
        
        # Add a update method for easy attribute updates
        mock_entity.update = lambda **kwargs: attr_dict.update(kwargs)
        
        return mock_entity
    
    return _create_mock_entity

# Conditionally import more advanced fixtures

# Database fixtures
try:
    from app.db.session import sessionmanager
    from app.db.base_class import Base
    
    @pytest_asyncio.fixture(scope="session", autouse=False)
    async def setup_test_db() -> AsyncGenerator[None, None]:
        """
        Create a fresh database for testing.
        
        This fixture runs once per test session and creates a clean database
        by dropping and recreating all tables.
        """
        # Use specific test database URL
        db_url = str(test_settings.TEST_DATABASE_URL)
        
        # Create async engine for setup
        from sqlalchemy.ext.asyncio import create_async_engine
        engine = create_async_engine(db_url, echo=False, future=True)
        
        async with engine.begin() as conn:
            # Drop all tables to ensure a clean state
            await conn.run_sync(Base.metadata.drop_all)
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
        
        # Close the engine
        await engine.dispose()
        
        yield
        
    @pytest_asyncio.fixture
    async def db_session() -> AsyncGenerator[Any, None]:
        """
        Provide a database session for test functions.
        
        This fixture yields a SQLAlchemy AsyncSession that is automatically
        rolled back after the test completes, ensuring no test data persists
        between tests.
        """
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        
        # Override the sessionmanager's engine with our test-specific engine
        test_engine = create_async_engine(
            str(test_settings.TEST_DATABASE_URL),
            echo=False,
            future=True
        )
        
        # Create a new session for the test
        async with sessionmanager.session() as session:
            # Start a nested transaction
            transaction = await session.begin_nested()
            
            # Yield the session for the test to use
            yield session
            
            # Roll back the transaction after the test
            if transaction.is_active:
                await transaction.rollback()
        
        # Ensure the engine is disposed
        await test_engine.dispose()
        
except ImportError:
    # If database components can't be imported, provide placeholder fixtures
    @pytest.fixture
    def setup_test_db():
        """Placeholder for database setup when database is not available."""
        pytest.skip("Database components not available")
    
    @pytest.fixture
    def db_session():
        """Placeholder for database session when database is not available."""
        pytest.skip("Database components not available")

# Redis fixtures
try:
    import redis.asyncio as redis
    
    @pytest_asyncio.fixture
    async def redis_client() -> AsyncGenerator[redis.Redis, None]:
        """
        Provide a Redis client for test functions.
        """
        # Create a Redis client for testing
        from app.core.config import settings
        
        try:
            client = redis.Redis.from_url(
                url=settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test connection
            await client.ping()
            
            # Ensure the database is clean at the start
            await client.flushdb()
            
            # Yield the client for test use
            yield client
            
            # Clean up after the test
            await client.flushdb()
            await client.close()
        except (redis.ConnectionError, redis.RedisError):
            pytest.skip("Redis server not available")
            
    @pytest_asyncio.fixture
    async def mock_redis_client() -> AsyncGenerator[Any, None]:
        """
        Provide a mocked Redis client for tests that don't need actual Redis.
        """
        from unittest.mock import AsyncMock
        
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
        
except ImportError:
    # If Redis can't be imported, provide placeholder fixtures
    @pytest.fixture
    def redis_client():
        """Placeholder for Redis client when Redis is not available."""
        pytest.skip("Redis components not available")
    
    @pytest.fixture
    def mock_redis_client():
        """Placeholder for mock Redis client when Redis is not available."""
        pytest.skip("Redis components not available")

# Grade service fixture
@pytest_asyncio.fixture(autouse=True)
async def reset_grade_service():
    """
    Reset the GradeService cache between tests.
    
    This fixture ensures that the GradeService cache is reset
    to avoid test interference.
    """
    try:
        from app.services.utils.grade_service import GradeService
        
        # Store original cache (if service is already initialized)
        if hasattr(GradeService, '_grade_conversion_cache'):
            original_cache = GradeService._grade_conversion_cache.copy() if GradeService._grade_conversion_cache else {}
        else:
            original_cache = {}
            
        if hasattr(GradeService, '_known_grade_systems'):
            original_systems = GradeService._known_grade_systems.copy() if GradeService._known_grade_systems else {}
        else:
            original_systems = {}
        
        # Yield for test execution
        yield
        
        # Restore original cache
        if hasattr(GradeService, '_grade_conversion_cache'):
            GradeService._grade_conversion_cache = original_cache
        if hasattr(GradeService, '_known_grade_systems'):
            GradeService._known_grade_systems = original_systems
    except ImportError:
        # Skip resetting if GradeService isn't available
        yield

# Custom pytest markers
def pytest_configure(config):
    """
    Configure pytest with custom markers.
    
    This function adds custom markers to pytest to allow for better
    categorization and selective running of tests.
    """
    config.addinivalue_line("markers", "api: marks tests as API tests")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "slow: marks tests as slow running")
    config.addinivalue_line("markers", "auth: marks tests involving authentication")
    config.addinivalue_line("markers", "redis: marks tests that require Redis")
    config.addinivalue_line("markers", "database: marks tests that require a database")

# Import fixtures from domain-specific modules
try:
    # Database fixtures
    from app.tests.fixtures.database import db_session, test_db_connection
except ImportError:
    pass

try:
    # Authentication fixtures
    from app.tests.fixtures.auth import auth_client, test_user, admin_user
except ImportError:
    pass

try:
    # Service layer fixtures
    from app.tests.fixtures.services import mock_chat_service, mock_climbing_service
except ImportError:
    pass

try:
    # Redis fixtures
    from app.tests.fixtures.redis import redis_client, redis_connection
except ImportError:
    pass

try:
    # External service fixtures
    from app.tests.fixtures.external_services import mock_openai, mock_weather_api
except ImportError:
    pass

try:
    # Test data fixtures
    from app.tests.fixtures.test_data import load_user_data, load_climb_data
except ImportError:
    pass

# Direct import of climbing fixtures
from app.tests.fixtures.climbing import (
    sample_climbing_areas,
    sample_routes,
    sample_user_ticks,
    load_climbing_data,
    climbing_disciplines,
    send_statuses,
    sample_grade_mappings,
    mock_grade_service,
    mock_climbing_service
)

try:
    # Chat domain-specific fixtures
    from app.tests.fixtures.chat import (
        sample_prompt_templates,
        sample_user_contexts,
        sample_conversation_histories,
        sample_llm_responses,
        create_chat_context,
        mock_chat_service,
        mock_model_client
    )
except ImportError:
    pass

# Service factories
try:
    from app.tests.factories import (
        ChatServiceFactory,
        ClimbingServiceFactory,
        GradeServiceFactory
    )
except ImportError:
    pass 

# Custom pytest markers
def pytest_collection_modifyitems(items):
    """Apply markers based on path."""
    for item in items:
        if "unit" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        elif "api" in item.nodeid:
            item.add_marker(pytest.mark.api)
        elif "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)