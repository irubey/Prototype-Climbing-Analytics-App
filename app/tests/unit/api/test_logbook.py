"""
Unit tests for logbook API endpoints.

This module tests the logbook connection endpoints in the API, 
focusing on request validation, error handling, and background task scheduling.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.logbook import router, connect_logbook
from app.core.exceptions import LogbookConnectionError
from app.models import User
from app.schemas.logbook_connection import LogbookConnectPayload, IngestionType

# Test user data
TEST_USER_ID = uuid.uuid4()

@pytest.fixture
def test_user():
    """Create a test user instance."""
    user = MagicMock(spec=User)
    user.id = TEST_USER_ID
    return user

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock(spec=AsyncSession)

@pytest.fixture
def mock_background_tasks():
    """Create a mock BackgroundTasks instance."""
    return MagicMock(spec=BackgroundTasks)

@pytest.mark.asyncio
async def test_connect_logbook_mountain_project(
    test_user, 
    mock_db, 
    mock_background_tasks
):
    """Test successful Mountain Project logbook connection."""
    # Arrange
    with patch("app.api.v1.endpoints.logbook.LogbookOrchestrator") as mock_orchestrator_cls:
        mock_orchestrator = AsyncMock()
        mock_orchestrator_cls.return_value = mock_orchestrator
        
        payload = LogbookConnectPayload(
            source=IngestionType.MOUNTAIN_PROJECT,
            profile_url="https://www.mountainproject.com/user/12345/test-user"
        )
        
        # Act
        result = await connect_logbook(
            payload=payload,
            background_tasks=mock_background_tasks,
            db=mock_db,
            current_user=test_user
        )
        
        # Assert
        assert result == {"status": "Processing initiated successfully"}
        mock_orchestrator_cls.assert_called_once_with(mock_db)
        mock_background_tasks.add_task.assert_called_once_with(
            mock_orchestrator.process_mountain_project_ticks,
            user_id=test_user.id,
            profile_url=payload.profile_url
        )

@pytest.mark.asyncio
async def test_connect_logbook_eight_a_nu(
    test_user, 
    mock_db, 
    mock_background_tasks
):
    """Test successful 8a.nu logbook connection."""
    # Arrange
    with patch("app.api.v1.endpoints.logbook.LogbookOrchestrator") as mock_orchestrator_cls:
        mock_orchestrator = AsyncMock()
        mock_orchestrator_cls.return_value = mock_orchestrator
        
        payload = LogbookConnectPayload(
            source=IngestionType.EIGHT_A_NU,
            username="test_user",
            password="password123"
        )
        
        # Act
        result = await connect_logbook(
            payload=payload,
            background_tasks=mock_background_tasks,
            db=mock_db,
            current_user=test_user
        )
        
        # Assert
        assert result == {"status": "Processing initiated successfully"}
        mock_orchestrator_cls.assert_called_once_with(mock_db)
        mock_background_tasks.add_task.assert_called_once_with(
            mock_orchestrator.process_eight_a_nu_ticks,
            user_id=test_user.id,
            username=payload.username,
            password="[REDACTED]"  # Verify credentials are not logged
        )

@pytest.mark.asyncio
async def test_connect_logbook_exception_handling(
    test_user, 
    mock_db, 
    mock_background_tasks
):
    """Test exception handling in logbook connection."""
    # Arrange
    with patch("app.api.v1.endpoints.logbook.LogbookOrchestrator") as mock_orchestrator_cls:
        mock_orchestrator_cls.side_effect = Exception("Test exception")
        
        payload = LogbookConnectPayload(
            source=IngestionType.MOUNTAIN_PROJECT,
            profile_url="https://www.mountainproject.com/user/12345/test-user"
        )
        
        # Act & Assert
        with pytest.raises(LogbookConnectionError) as exc_info:
            await connect_logbook(
                payload=payload,
                background_tasks=mock_background_tasks,
                db=mock_db,
                current_user=test_user
            )
        
        assert str(exc_info.value) == "503: Test exception" 