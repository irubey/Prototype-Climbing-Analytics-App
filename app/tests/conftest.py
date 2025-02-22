# Add the project root (C:\Users\Isaac\send_sage) to sys.path so that module resolution is consistent.
import sys
from pathlib import Path
# Insert the project root (one level above "app")
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

"""
Test configuration and fixtures.
"""
import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator, AsyncIterator
from httpx import AsyncClient
import httpx
import os
from collections import defaultdict
from contextlib import asynccontextmanager, suppress
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch
# --- Logging Setup BEFORE App Import ---
from app.core.logging_config import setup_logging
setup_logging()  # Initialize logging HERE
# ----------------------------------------
from app.core.logging import logger
from sqlalchemy import schema, text
from fastapi import FastAPI
from app.core.config import settings, get_settings
from app.db.session import get_db, sessionmanager
import redis.asyncio as redis
from app.db.base_class import Base
from app.api.v1.router import api_router
from app.main import app as main_app
from app.services.utils.grade_service import GradeService
from app.services.chat.context.orchestrator import ContextOrchestrator
from app.services.chat.ai.basic_chat import BasicChatService
from app.services.chat.ai.premium_chat import PremiumChatService
from app.services.chat.events.manager import EventManager, EventType

# Now proceed with the rest of the conftest imports.
try:
    from app.core.config import settings
    from app.db.session import get_db, sessionmanager
    from app.db.base_class import Base
    from app.main import app
    from app.core.auth import get_password_hash
    from app.db.init_db import init_db  # Import init_db
except Exception as e:
    logger.error("Error during conftest setup", extra={"error": str(e)})
    raise

# Set the testing flag very early
settings.TESTING = True
logger.info("Test environment initialized", extra={"TESTING": settings.TESTING})

# Get DB manager instance
db_manager = sessionmanager.get_instance()
logger.info("Got DB manager instance", extra={"initialized": db_manager.initialized})

# Log environment details for debugging
logger.debug("Current working directory", extra={"cwd": os.getcwd()})
logger.debug("sys.path", extra={"sys_path": sys.path})

def pytest_collection_modifyitems(items):
    """Modify test items in place to ensure test isolation."""
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio(loop_scope="function"))

@pytest_asyncio.fixture(autouse=True)
async def setup_and_teardown() -> AsyncGenerator[None, None]:
    """Setup and teardown for each test."""
    # Setup
    await asyncio.sleep(0.1)  # Small delay to ensure previous test cleanup is complete
    yield
    # Teardown
    await asyncio.sleep(0.1)  # Small delay to ensure cleanup completes

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create and configure a new event loop for each test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    yield loop
    
    # Clean up any pending tasks
    pending = asyncio.all_tasks(loop)
    if pending:
        # Cancel all pending tasks
        for task in pending:
            task.cancel()
        
        # Wait for cancellation to complete with a timeout
        try:
            loop.run_until_complete(
                asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True),
                    timeout=1.0
                )
            )
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
    
    loop.close()

@pytest.fixture(scope="session")
def anyio_backend():
    """Configure backend for anyio/pytest-asyncio."""
    return "asyncio"

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Initialize test database at session level."""
    logger.info("Setting up test database for session")
    sessionmanager.init(settings.TEST_DATABASE_URL, force=True)
    
    async with sessionmanager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    await init_db()
    
    yield
    
    await sessionmanager.close()

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with sessionmanager.engine.connect() as conn:
        # Start a transaction
        await conn.begin()
        
        # Create a session bound to this connection
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint"
        )

        try:
            yield session
        finally:
            await session.close()
            # Rollback the transaction
            await conn.rollback()

@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[redis.Redis, None]:
    """Get a Redis client for testing."""
    client = redis.from_url(str(settings.REDIS_URL))
    try:
        await client.ping()
        await client.flushdb()  # Clear before test
        yield client
        await client.flushdb()  # Clear after test
    finally:
        await client.aclose()

@pytest_asyncio.fixture
async def app(db_session: AsyncSession, redis_client: redis.Redis) -> AsyncGenerator[FastAPI, None]:
    """Create a fresh FastAPI application for testing."""
    sessionmanager.init(settings.TEST_DATABASE_URL, force=True)

    test_app = FastAPI(
        title=main_app.title,
        openapi_url=main_app.openapi_url,
        docs_url=main_app.docs_url,
        redoc_url=main_app.redoc_url,
    )

    # Override dependencies
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield db_session
        finally:
            await db_session.close()

    async def override_get_redis() -> AsyncGenerator[redis.Redis, None]:
        try:
            yield redis_client
        finally:
            pass  # Redis client cleanup is handled by the fixture

    from app.api.v1.endpoints.chat import get_redis
    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_redis] = override_get_redis

    # Include routers
    test_app.include_router(api_router, prefix=settings.API_V1_STR)
    test_app.state.db_manager = sessionmanager

    yield test_app

    await sessionmanager.close()

@pytest_asyncio.fixture
async def mock_context_orchestrator(db_session: AsyncSession, redis_client: redis.Redis) -> AsyncGenerator[ContextOrchestrator, None]:
    """Get a mock ContextOrchestrator for testing."""
    orchestrator = ContextOrchestrator(db_session, redis_client)
    yield orchestrator

@pytest_asyncio.fixture
async def mock_basic_chat_service(mock_context_orchestrator: ContextOrchestrator, redis_client: redis.Redis, event_manager: EventManager) -> AsyncGenerator[BasicChatService, None]:
    """Get a mock BasicChatService for testing."""
    service = BasicChatService(mock_context_orchestrator, event_manager, redis_client)
    yield service

@pytest_asyncio.fixture
async def mock_premium_chat_service(mock_context_orchestrator: ContextOrchestrator, event_manager: EventManager) -> AsyncGenerator[PremiumChatService, None]:
    """Get a mock PremiumChatService for testing."""
    service = PremiumChatService(mock_context_orchestrator, event_manager)
    yield service

@pytest_asyncio.fixture
async def event_manager() -> AsyncGenerator[EventManager, None]:
    """Get a fresh EventManager instance for testing."""
    manager = EventManager()
    yield manager
    # Cleanup any remaining subscribers and tasks
    for user_id in list(manager.subscribers.keys()):
        await manager.disconnect(user_id)
    await asyncio.sleep(0.1)  # Small delay to ensure cleanup completes

@pytest_asyncio.fixture(autouse=True)
async def cleanup_tasks() -> AsyncGenerator[None, None]:
    """Cleanup any pending tasks after each test."""
    yield
    current_loop = asyncio.get_event_loop()
    tasks = [t for t in asyncio.all_tasks(current_loop) 
             if t is not asyncio.current_task(current_loop)]
    
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
        for task in tasks:
            if not task.done():
                task.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.gather(*tasks, return_exceptions=True)

@pytest_asyncio.fixture(autouse=True)
async def clear_redis(redis_client: redis.Redis) -> AsyncGenerator[None, None]:
    """Clear Redis data before and after each test."""
    try:
        await redis_client.flushdb()
        yield
    finally:
        await redis_client.flushdb()

@pytest_asyncio.fixture
async def client(
    app: FastAPI, 
    db_session: AsyncSession, 
    redis_client: redis.Redis
) -> AsyncGenerator[AsyncClient, None]:
    """Get an async test client."""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield db_session
        finally:
            await db_session.close()

    async def override_get_redis() -> AsyncGenerator[redis.Redis, None]:
        yield redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides["get_redis"] = override_get_redis

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
        await test_client.aclose()

# Test data fixtures
@pytest.fixture
def test_password() -> str:
    """Get test password."""
    return "TestPassword123!"

@pytest.fixture
def test_user_data(test_password: str) -> dict:
    """Get test user data."""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": test_password,
    }

@pytest.fixture
def test_superuser_data(test_password: str) -> dict:
    """Get test superuser data."""
    return {
        "email": "admin@example.com",
        "username": "admin",
        "password": test_password,
        "is_superuser": True
    }

@pytest.fixture
def test_premium_user_data(test_password: str) -> dict:
    """Get test premium user data."""
    return {
        "email": "premium@example.com",
        "username": "premium_user",
        "password": test_password,
        "tier": "premium",
        "payment_status": "active"
    }

@pytest_asyncio.fixture(autouse=True)
async def reset_grade_service():
    """Reset the GradeService singleton and its caches between tests."""
    # Clear the singleton instance
    GradeService._instance = None
    # Create a new instance (this will reset all caches)
    grade_service = GradeService.get_instance()
    yield grade_service
    # Clear caches after test
    grade_service._convert_single_grade_to_code.cache_clear()
    grade_service.get_grade_from_code.cache_clear()

@pytest_asyncio.fixture
async def mock_mp_client() -> AsyncGenerator[AsyncMock, None]:
    """Create a mock Mountain Project client for testing."""
    from app.services.logbook.gateways.mp_csv_client import MountainProjectCSVClient
    
    # Create mock HTTP client
    mock_http_client = AsyncMock(spec=httpx.AsyncClient)
    mock_http_client.get.return_value = AsyncMock(
        status_code=200,
        text="",  # Empty CSV data by default
        raise_for_status=AsyncMock()  # Won't raise by default
    )
    
    # Create mock MP client
    mock_client = AsyncMock(spec=MountainProjectCSVClient)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.client = mock_http_client
    
    # Patch both the client class and the httpx.AsyncClient
    with patch('app.services.logbook.orchestrator.MountainProjectCSVClient', return_value=mock_client), \
         patch('httpx.AsyncClient', return_value=mock_http_client):
        yield mock_client