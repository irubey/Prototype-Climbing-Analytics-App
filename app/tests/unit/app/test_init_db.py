"""
Unit tests for database initialization and cleanup utilities.

These tests verify that the database initialization and disposal functions
work correctly under various scenarios, including successful operations
and error handling cases.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.init_db import init_db, dispose_db
from app.models.auth import KeyHistory


@pytest.fixture
def mock_session_manager():
    """Create a mock for the sessionmanager."""
    mock_manager = MagicMock()
    mock_manager.engine = MagicMock()
    mock_manager.engine.begin = AsyncMock()
    mock_manager.session = AsyncMock()
    mock_manager.close = AsyncMock()
    return mock_manager


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_conn():
    """Create a mock database connection."""
    conn = AsyncMock()
    conn.run_sync = AsyncMock()
    return conn


@pytest.mark.asyncio
@patch("app.db.init_db.sessionmanager")
@patch("app.db.init_db.Base")
@patch("app.core.logging.logger")
async def test_init_db_successful(mock_logger, mock_base, mock_sessionmanager):
    """Test successful database initialization with key creation."""
    # Setup mocks
    mock_conn = AsyncMock()
    mock_sessionmanager.engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_conn.run_sync = AsyncMock()

    # Setup session mock
    mock_db = AsyncMock(spec=AsyncSession)
    mock_sessionmanager.session.return_value.__aenter__.return_value = mock_db
    
    # Mock db.execute to return None first, then a mock key
    mock_result = MagicMock()
    mock_verify_key = MagicMock()
    mock_verify_key.id = "mock_kid"  # Set the ID explicitly
    mock_result.scalar_one_or_none.side_effect = [None, mock_verify_key]  # None for first check, Key with ID for verification
    mock_db.execute.return_value = mock_result

    # Mock auth functions
    mock_private_key = "mock_private_key"
    mock_public_key = "mock_public_key"
    mock_kid = "mock_kid"
    mock_encrypted_private_key = "mock_encrypted_private_key"
    
    mock_generate_key_pair = AsyncMock(return_value=(mock_private_key, mock_public_key, mock_kid))
    mock_encrypt_private_key = AsyncMock(return_value=mock_encrypted_private_key)
    
    # Patch the generate_key_pair and encrypt_private_key functions
    with patch("app.core.auth.generate_key_pair", mock_generate_key_pair), \
         patch("app.core.auth.encrypt_private_key", mock_encrypt_private_key):
        # Execute function
        await init_db()
    
    # Verify tables were created
    mock_conn.run_sync.assert_called_once_with(mock_base.metadata.create_all)
    
    # Verify key creation occurred
    mock_generate_key_pair.assert_called_once()
    mock_encrypt_private_key.assert_called_once_with(mock_private_key)
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    
    # Verify logging
    mock_logger.info.assert_any_call("Initializing database")
    mock_logger.info.assert_any_call("No existing keys found. Creating initial key pair.")
    mock_logger.info.assert_any_call("Initial key pair created and stored.")
    mock_logger.info.assert_any_call(f"Key verification successful. KID: {mock_verify_key.id}")
    mock_logger.info.assert_any_call("Database initialization complete")


@pytest.mark.asyncio
@patch("app.db.init_db.sessionmanager")
@patch("app.db.init_db.Base")
@patch("app.core.logging.logger")
async def test_init_db_existing_keys(mock_logger, mock_base, mock_sessionmanager):
    """Test database initialization when keys already exist."""
    # Setup mocks
    mock_conn = AsyncMock()
    mock_sessionmanager.engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_conn.run_sync = AsyncMock()

    # Setup session mock with existing key
    mock_db = AsyncMock(spec=AsyncSession)
    mock_sessionmanager.session.return_value.__aenter__.return_value = mock_db
    
    # Mock db.execute to return an existing key
    mock_result = MagicMock()
    mock_existing_key = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_existing_key
    mock_db.execute.return_value = mock_result

    # Execute function
    await init_db()
    
    # Verify tables were created
    mock_conn.run_sync.assert_called_once_with(mock_base.metadata.create_all)
    
    # Verify key creation was skipped
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
    
    # Verify logging
    mock_logger.info.assert_any_call("Initializing database")
    mock_logger.info.assert_any_call("Existing key found. Skipping key initialization.")
    mock_logger.info.assert_any_call("Database initialization complete")


@pytest.mark.asyncio
@patch("app.core.auth.generate_key_pair")
@patch("app.db.init_db.sessionmanager")
@patch("app.db.init_db.Base")
@patch("app.core.logging.logger")
async def test_init_db_key_verification_failed(mock_logger, mock_base, mock_sessionmanager, mock_generate_key_pair):
    """Test database initialization when key verification fails after creation."""
    # Setup mocks
    mock_conn = AsyncMock()
    mock_sessionmanager.engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_conn.run_sync = AsyncMock()

    # Setup session mock
    mock_db = AsyncMock(spec=AsyncSession)
    mock_sessionmanager.session.return_value.__aenter__.return_value = mock_db
    
    # Mock auth functions
    mock_private_key = "mock_private_key"
    mock_public_key = "mock_public_key"
    mock_kid = "mock_kid"
    mock_generate_key_pair.return_value = (mock_private_key, mock_public_key, mock_kid)
    
    # Mock db.execute to return None for first check, None again for verification (simulating key not found after commit)
    mock_result1 = MagicMock()
    mock_result1.scalar_one_or_none.return_value = None
    
    mock_result2 = MagicMock()
    mock_result2.scalar_one_or_none.return_value = None  # Key not found after commit
    
    mock_db.execute.side_effect = [mock_result1, mock_result2]

    # Execute function - should raise RuntimeError
    with patch("app.core.auth.encrypt_private_key", AsyncMock()):
        with pytest.raises(RuntimeError, match="Key not found after commit"):
            await init_db()
    
    # Verify error handling
    mock_logger.error.assert_any_call("Key verification FAILED. Key not found after commit.")


@pytest.mark.asyncio
@patch("app.core.auth.generate_key_pair")
@patch("app.db.init_db.sessionmanager")
@patch("app.db.init_db.Base")
@patch("app.core.logging.logger")
async def test_init_db_key_generation_error(mock_logger, mock_base, mock_sessionmanager, mock_generate_key_pair):
    """Test database initialization when key generation raises an error."""
    # Setup mocks
    mock_conn = AsyncMock()
    mock_sessionmanager.engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_conn.run_sync = AsyncMock()

    # Setup session mock
    mock_db = AsyncMock(spec=AsyncSession)
    mock_sessionmanager.session.return_value.__aenter__.return_value = mock_db
    
    # Mock db.execute to return None (so it attempts key creation)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Setup key generation to fail
    mock_generate_key_pair.side_effect = Exception("Key generation failed")

    # Execute function - should raise the Exception
    with pytest.raises(Exception, match="Key generation failed"):
        await init_db()
    
    # Verify error handling - the error is caught at both levels
    mock_logger.error.assert_any_call(
        "Error during key initialization",
        extra={
            "error": "Key generation failed",
            "error_type": "Exception"
        },
        exc_info=True
    )
    
    # Also verify the outer error handler was called
    mock_logger.error.assert_any_call(
        "Error during database initialization",
        extra={
            "error": "Key generation failed",
            "error_type": "Exception"
        },
        exc_info=True
    )


@pytest.mark.asyncio
@patch("app.db.init_db.sessionmanager")
@patch("app.core.logging.logger")
async def test_dispose_db_successful(mock_logger, mock_sessionmanager):
    """Test successful database disposal."""
    # Setup close as AsyncMock
    mock_sessionmanager.close = AsyncMock()
    
    # Execute function
    await dispose_db()
    
    # Verify session manager was closed
    mock_sessionmanager.close.assert_called_once()
    
    # Verify logging
    mock_logger.info.assert_any_call("Disposing database connections")
    mock_logger.info.assert_any_call("Database connections disposed")


@pytest.mark.asyncio
@patch("app.db.init_db.sessionmanager")
@patch("app.core.logging.logger")
async def test_dispose_db_error(mock_logger, mock_sessionmanager):
    """Test database disposal when an error occurs."""
    # Setup mock to raise exception
    mock_sessionmanager.close = AsyncMock(side_effect=Exception("Disposal error"))
    
    # Execute function - should raise the exception
    with pytest.raises(Exception, match="Disposal error"):
        await dispose_db()
    
    # Verify error handling
    mock_logger.error.assert_called_with(
        "Error during database disposal",
        extra={
            "error": "Disposal error",
            "error_type": "Exception"
        },
        exc_info=True
    ) 