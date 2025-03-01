"""
Unit tests for database session management.

These tests verify that the DatabaseSessionManager works correctly,
including initialization, session creation, and cleanup operations.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import asyncio
import sys
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy.pool import NullPool
from fastapi import FastAPI, Request, HTTPException
from app.db.session import (
    DatabaseSessionManager, sessionmanager,
    get_db, create_all, drop_all
)


def test_singleton_pattern():
    """Test that get_instance always returns the same instance."""
    # Get two instances
    instance1 = DatabaseSessionManager.get_instance()
    instance2 = DatabaseSessionManager.get_instance()
    
    # Verify they are the same object
    assert instance1 is instance2
    
    # Verify it's the same as the global instance
    assert instance1 is sessionmanager


@pytest.mark.asyncio
@patch("app.db.session.create_async_engine")
@patch("app.db.session.async_sessionmaker")
@patch("app.db.session._get_logger")
@patch("app.db.session._get_settings")
async def test_init_basic(mock_get_settings, mock_get_logger, 
                        mock_sessionmaker, mock_create_engine):
    """Test basic initialization with default parameters."""
    # Setup mocks
    mock_settings = MagicMock()
    mock_settings.ENVIRONMENT = "development"
    mock_settings.TESTING = False
    mock_get_settings.return_value = mock_settings
    
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_create_engine.return_value = mock_engine
    
    mock_session_factory = MagicMock()
    mock_sessionmaker.return_value = mock_session_factory
    
    # Create a fresh manager for this test
    manager = DatabaseSessionManager()
    
    # Initialize with default parameters
    db_url = "postgresql://user:pass@localhost/dbname"
    manager.init(db_url)
    
    # Verify engine was created with correct URL and default parameters
    mock_create_engine.assert_called_once()
    call_args = mock_create_engine.call_args[0][0]
    assert "postgresql+asyncpg://" in call_args
    
    # Verify default engine parameters were used
    engine_kwargs = mock_create_engine.call_args[1]
    assert engine_kwargs["pool_pre_ping"] is True
    assert engine_kwargs["echo"] is True  # Because ENVIRONMENT is development
    assert engine_kwargs["pool_size"] == 5
    assert engine_kwargs["max_overflow"] == 10
    
    # Verify session maker was created
    mock_sessionmaker.assert_called_once_with(
        mock_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    
    # Verify initialized state
    assert manager._initialized is True
    assert manager._engine is mock_engine
    assert manager._sessionmaker is mock_session_factory


@pytest.mark.asyncio
@patch("app.db.session.create_async_engine")
@patch("app.db.session.async_sessionmaker")
@patch("app.db.session._get_logger")
@patch("app.db.session._get_settings")
async def test_init_with_nullpool(mock_get_settings, mock_get_logger, 
                                mock_sessionmaker, mock_create_engine):
    """Test initialization with NullPool."""
    # Setup mocks
    mock_settings = MagicMock()
    mock_settings.ENVIRONMENT = "production"
    mock_settings.TESTING = False
    mock_get_settings.return_value = mock_settings
    
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_create_engine.return_value = mock_engine
    
    mock_session_factory = MagicMock()
    mock_sessionmaker.return_value = mock_session_factory
    
    # Create a fresh manager for this test
    manager = DatabaseSessionManager()
    
    # Initialize with NullPool
    db_url = "postgresql://user:pass@localhost/dbname"
    manager.init(db_url, poolclass=NullPool)
    
    # Verify engine was created with NullPool
    engine_kwargs = mock_create_engine.call_args[1]
    assert engine_kwargs["poolclass"] is NullPool
    assert "pool_size" not in engine_kwargs  # Should not include pool parameters with NullPool
    assert "max_overflow" not in engine_kwargs


@pytest.mark.asyncio
@patch("app.db.session.create_async_engine")
@patch("app.db.session.async_sessionmaker")
@patch("app.db.session._get_logger")
@patch("app.db.session._get_settings")
async def test_init_with_custom_params(mock_get_settings, mock_get_logger, 
                                    mock_sessionmaker, mock_create_engine):
    """Test initialization with custom engine and session parameters."""
    # Setup mocks
    mock_settings = MagicMock()
    mock_settings.ENVIRONMENT = "production"
    mock_settings.TESTING = False
    mock_get_settings.return_value = mock_settings
    
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_create_engine.return_value = mock_engine
    
    mock_session_factory = MagicMock()
    mock_sessionmaker.return_value = mock_session_factory
    
    # Create a fresh manager for this test
    manager = DatabaseSessionManager()
    
    # Initialize with custom parameters
    db_url = "postgresql://user:pass@localhost/dbname"
    engine_kwargs = {
        "pool_size": 10,
        "max_overflow": 20,
        "connect_args": {"ssl": True}
    }
    session_kwargs = {
        "expire_on_commit": True,
        "autoflush": True
    }
    
    manager.init(db_url, engine_kwargs=engine_kwargs, session_kwargs=session_kwargs)
    
    # Verify engine was created with custom parameters
    engine_call_kwargs = mock_create_engine.call_args[1]
    assert engine_call_kwargs["pool_size"] == 10
    assert engine_call_kwargs["max_overflow"] == 20
    assert engine_call_kwargs["connect_args"] == {"ssl": True}
    
    # Verify session maker was created with custom parameters
    session_call_kwargs = mock_sessionmaker.call_args[1]
    assert session_call_kwargs["expire_on_commit"] is True
    assert session_call_kwargs["autoflush"] is True


@pytest.mark.asyncio
@patch("app.db.session._get_logger")
@patch("app.db.session._get_settings")
async def test_init_already_initialized(mock_get_settings, mock_get_logger):
    """Test that init doesn't reinitialize if already initialized unless forced."""
    # Setup mocks
    mock_settings = MagicMock()
    mock_settings.TESTING = False
    mock_get_settings.return_value = mock_settings
    
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    # Create a fresh manager for this test
    manager = DatabaseSessionManager()
    
    # Fake initialization
    manager._initialized = True
    manager._engine = MagicMock()
    manager._sessionmaker = MagicMock()
    
    # Call init without force
    db_url = "postgresql://user:pass@localhost/dbname"
    manager.init(db_url)
    
    # Verify warning was logged but no reinitialization occurred
    mock_logger.warning.assert_called_once()
    assert "already initialized" in mock_logger.warning.call_args[0][0]


@pytest.mark.asyncio
@patch("app.db.session.create_async_engine")
@patch("app.db.session.async_sessionmaker")
@patch("app.db.session._get_logger")
@patch("app.db.session._get_settings")
async def test_init_force_reinitialization(mock_get_settings, mock_get_logger,
                                        mock_sessionmaker, mock_create_engine):
    """Test that init forces reinitialization when force=True."""
    # Setup mocks
    mock_settings = MagicMock()
    mock_settings.ENVIRONMENT = "development"
    mock_settings.TESTING = False
    mock_get_settings.return_value = mock_settings
    
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_create_engine.return_value = mock_engine
    
    mock_session_factory = MagicMock()
    mock_sessionmaker.return_value = mock_session_factory
    
    # Create a fresh manager for this test
    manager = DatabaseSessionManager()
    
    # Fake initialization
    original_engine = MagicMock()
    original_sessionmaker = MagicMock()
    manager._initialized = True
    manager._engine = original_engine
    manager._sessionmaker = original_sessionmaker
    
    # Call init with force=True
    db_url = "postgresql://user:pass@localhost/dbname"
    manager.init(db_url, force=True)
    
    # Verify reinitialization occurred
    assert manager._engine is not original_engine
    assert manager._sessionmaker is not original_sessionmaker
    assert manager._engine is mock_engine
    assert manager._sessionmaker is mock_session_factory


@pytest.mark.asyncio
@patch("app.db.session._get_logger")
@patch("app.db.session._get_settings")
async def test_init_test_db_check(mock_get_settings, mock_get_logger):
    """Test that init rejects non-test DBs in test environment."""
    # Setup mocks
    mock_settings = MagicMock()
    mock_settings.TESTING = True
    mock_get_settings.return_value = mock_settings
    
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    # Create a fresh manager for this test
    manager = DatabaseSessionManager()
    
    # Call init with non-test DB URL in test environment
    db_url = "postgresql://user:pass@localhost/production_db"
    
    # Verify it raises ValueError
    with pytest.raises(ValueError) as excinfo:
        manager.init(db_url)
    
    assert "non-test database in test environment" in str(excinfo.value).lower()
    mock_logger.error.assert_called_once()


@pytest.mark.asyncio
@patch("app.db.session._get_logger")
async def test_session_not_initialized(mock_get_logger):
    """Test that session raises an error when not initialized."""
    # Setup mocks
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    # Create a fresh manager for this test
    manager = DatabaseSessionManager()
    manager._initialized = False
    manager._sessionmaker = None
    
    # Try to get a session
    with pytest.raises(RuntimeError) as excinfo:
        async with manager.session():
            pass
    
    assert "not initialized" in str(excinfo.value).lower()


@pytest.mark.asyncio
@patch("app.db.session._get_logger")
async def test_engine_not_initialized(mock_get_logger):
    """Test that accessing engine raises an error when not initialized."""
    # Setup mocks
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    # Create a fresh manager for this test
    manager = DatabaseSessionManager()
    manager._initialized = False
    manager._engine = None
    
    # Try to access the engine
    with pytest.raises(RuntimeError) as excinfo:
        _ = manager.engine
    
    assert "not initialized" in str(excinfo.value).lower()


@pytest.mark.asyncio
@patch("app.db.session._get_logger")
async def test_session_context_manager(mock_get_logger):
    """Test that session context manager yields and closes sessions properly."""
    # Setup mocks
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    mock_session = AsyncMock(spec=AsyncSession)
    mock_sessionmaker = MagicMock(return_value=mock_session)
    
    # Create a fresh manager for this test
    manager = DatabaseSessionManager()
    manager._initialized = True
    manager._sessionmaker = mock_sessionmaker
    
    # Use the session context manager
    async with manager.session() as session:
        assert session is mock_session
    
    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.db.session._get_logger")
async def test_close(mock_get_logger):
    """Test that close properly disposes the engine and resets state."""
    # Setup mocks
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_sessionmaker = MagicMock()
    
    # Create a fresh manager for this test
    manager = DatabaseSessionManager()
    manager._initialized = True
    manager._engine = mock_engine
    manager._sessionmaker = mock_sessionmaker
    
    # Close the manager
    await manager.close()
    
    # Verify engine was disposed
    mock_engine.dispose.assert_called_once()
    
    # Verify state was reset
    assert manager._initialized is False
    assert manager._engine is None
    assert manager._sessionmaker is None
    
    # Verify logging
    mock_logger.info.assert_called_with("Closed all database connections")


@pytest.mark.asyncio
@patch("app.db.session.sessionmanager")
async def test_create_all(mock_sessionmanager):
    """Test create_all function."""
    # Setup mocks
    mock_conn = AsyncMock()
    mock_conn.run_sync = AsyncMock()
    mock_sessionmanager.engine.begin.return_value.__aenter__.return_value = mock_conn
    
    # Call create_all
    await create_all()
    
    # Verify Base.metadata.create_all was called
    from app.db.base_class import Base
    mock_conn.run_sync.assert_called_once_with(Base.metadata.create_all)


@pytest.mark.asyncio
@patch("app.db.session.sessionmanager")
async def test_drop_all(mock_sessionmanager):
    """Test drop_all function."""
    # Setup mocks
    mock_conn = AsyncMock()
    mock_conn.run_sync = AsyncMock()
    mock_sessionmanager.engine.begin.return_value.__aenter__.return_value = mock_conn
    
    # Call drop_all
    await drop_all()
    
    # Verify Base.metadata.drop_all was called
    from app.db.base_class import Base
    mock_conn.run_sync.assert_called_once_with(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_get_db():
    """Test get_db dependency."""
    # Setup mock app and request
    mock_app = MagicMock(spec=FastAPI)
    mock_app.state = MagicMock()  # Create state attribute explicitly
    
    mock_db_manager = MagicMock()
    mock_session = AsyncMock(spec=AsyncSession)
    mock_app.state.db_manager = mock_db_manager
    
    # Mock session context manager
    mock_db_manager.session.return_value.__aenter__.return_value = mock_session
    
    mock_request = MagicMock(spec=Request)
    mock_request.app = mock_app
    
    # Test normal operation - session should be yielded and committed
    db_generator = get_db(mock_request)
    session = await db_generator.__anext__()
    
    assert session is mock_session
    
    # Simulate the end of the request
    try:
        await db_generator.__anext__()
    except StopAsyncIteration:
        pass
    
    # Verify commit was called
    mock_session.commit.assert_called_once()
    
    # Test exception handling - session should be rolled back
    mock_session.reset_mock()
    mock_session.commit.side_effect = Exception("Test exception")
    
    db_generator = get_db(mock_request)
    session = await db_generator.__anext__()
    
    # Simulate the end of the request with an exception
    with pytest.raises(Exception):
        try:
            await db_generator.__anext__()
        except StopAsyncIteration:
            pass
    
    # Verify rollback was called
    mock_session.rollback.assert_called_once()


@pytest.mark.asyncio
@patch("app.db.session._get_settings")
@patch("app.db.session.create_async_engine")
@patch("app.db.session.async_sessionmaker")
async def test_init_call_count_tracking(mock_sessionmaker, mock_create_engine, mock_get_settings):
    """Test that init call count is tracked correctly."""
    # Setup mocks
    mock_settings = MagicMock()
    mock_settings.ENVIRONMENT = "development"
    mock_settings.TESTING = False
    mock_get_settings.return_value = mock_settings
    
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_create_engine.return_value = mock_engine
    
    mock_session_factory = MagicMock()
    mock_sessionmaker.return_value = mock_session_factory
    
    # Create a fresh manager for this test
    with patch("app.db.session._get_logger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        manager = DatabaseSessionManager()
        assert manager._init_call_count == 0
        
        # First call
        db_url = "postgresql://user:pass@localhost/dbname"
        manager.init(db_url)
        assert manager._init_call_count == 1
        
        # Set initialized to False to allow another init
        manager._initialized = False
        
        # Second call
        manager.init(db_url)
        assert manager._init_call_count == 2
        
        # Verify logging included call count
        mock_logger.info.assert_any_call(
            "DatabaseSessionManager.init called",
            extra={
                "call_count": 1,
                "already_initialized": False,
                "force": False,
                "is_test_db": False
            }
        )
        
        mock_logger.info.assert_any_call(
            "DatabaseSessionManager.init called", 
            extra={
                "call_count": 2,
                "already_initialized": False,
                "force": False,
                "is_test_db": False
            }
        )


@pytest.mark.asyncio
@patch("app.db.session._get_logger")
@patch("app.db.session._get_settings")
async def test_initialized_property(mock_get_settings, mock_get_logger):
    """Test the initialized property."""
    # Setup mocks
    mock_settings = MagicMock()
    mock_get_settings.return_value = mock_settings
    
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    # Create a fresh manager for this test
    manager = DatabaseSessionManager()
    
    # Test initial state
    assert manager.initialized is False
    
    # Test after setting _initialized
    manager._initialized = True
    assert manager.initialized is True
    
    # Test after unsetting _initialized
    manager._initialized = False
    assert manager.initialized is False 