"""
Database and ORM fixtures for testing.

This module provides fixtures for database sessions, connections, 
and other database-related functionality needed for tests.
"""

import asyncio
import pytest
import pytest_asyncio
from sqlalchemy import schema, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from typing import AsyncGenerator, Generator, Any, Dict

from app.core.config import settings
from app.db.session import get_db, sessionmanager
from app.db.base_class import Base
from app.tests.config import test_settings


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """
    Create a fresh database for testing.
    
    This fixture runs once per test session and creates a clean database
    by dropping and recreating all tables. It's marked as autouse to ensure
    the test database is always set up properly before any tests run.
    """
    # Use specific test database URL
    db_url = str(test_settings.TEST_DATABASE_URL)
    
    # Create async engine for setup
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
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session for test functions.
    
    This fixture yields a SQLAlchemy AsyncSession that is automatically
    rolled back after the test completes, ensuring no test data persists
    between tests.
    """
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


@pytest.fixture
def use_test_db_session():
    """
    Fixture to patch the get_db dependency with our test session.
    
    This fixture is used to override the standard database dependency
    in FastAPI endpoints for testing purposes.
    """
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with sessionmanager.session() as session:
            yield session
    
    return override_get_db 