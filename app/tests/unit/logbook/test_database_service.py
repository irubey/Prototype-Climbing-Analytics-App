"""
Unit tests for the DatabaseService.

Tests database operations related to logbook data including saving
user ticks, performance pyramids, tags, and sync metadata.
"""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, date, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
import traceback

from app.models.enums import LogbookType, ClimbingDiscipline, CruxAngle, CruxEnergyType
from app.models import UserTicks, PerformancePyramid, Tag, UserTicksTags, User
from app.services.logbook.database_service import DatabaseService
from app.core.exceptions import DatabaseError
from app.db.session import get_db

# Test user ID
TEST_USER_ID = uuid.uuid4()

@pytest.fixture
def mock_session():
    """Create a mock database session with comprehensive functionality."""
    session = AsyncMock(spec=AsyncSession)
    
    # Setup base session methods
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    
    # Create a properly structured mock result that doesn't return coroutines for synchronous methods
    mock_result = MagicMock()
    mock_scalar_result = MagicMock()
    
    # Set up synchronous methods
    mock_result.scalars = MagicMock(return_value=mock_scalar_result)
    mock_scalar_result.all = MagicMock(return_value=[])
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    
    # Make execute return the mock_result directly
    session.execute = AsyncMock(return_value=mock_result)
    
    return session

@pytest.fixture
def db_service(mock_session):
    """Create a real DatabaseService instance with a mock session."""
    return DatabaseService(mock_session)

@pytest.fixture
def sample_ticks_data():
    """Sample tick data for testing."""
    return [
        {
            "route_name": "Test Route 1",
            "route_grade": "5.10a",
            "tick_date": date(2023, 1, 1),
            "binned_grade": "5.10a",
            "binned_code": 10,
            "discipline": ClimbingDiscipline.SPORT,
            "lead_style": "Onsight",
            "location": "Test Crag, CO",
            "notes": "Great climb!",
            "length": 80,
            "pitches": 1,
            "send_bool": True,
            "user_id": TEST_USER_ID,
            "logbook_type": LogbookType.MOUNTAIN_PROJECT
        },
        {
            "route_name": "Test Route 2",
            "route_grade": "5.11b",
            "tick_date": date(2023, 1, 2),
            "binned_grade": "5.11b",
            "binned_code": 15,
            "discipline": ClimbingDiscipline.SPORT,
            "lead_style": "Redpoint",
            "location": "Another Crag, UT",
            "notes": "Hard climb!",
            "length": 100,
            "pitches": 1,
            "send_bool": True,
            "user_id": TEST_USER_ID,
            "logbook_type": LogbookType.MOUNTAIN_PROJECT
        }
    ]

@pytest.fixture
def sample_pyramid_data():
    """Sample performance pyramid data for testing."""
    return [
        {
            "tick_id": 1,
            "user_id": TEST_USER_ID,
            "send_date": date(2023, 1, 1),
            "location": "Test Crag, CO",
            "crux_angle": CruxAngle.VERTICAL,
            "crux_energy": CruxEnergyType.POWER,
            "binned_code": 10,
            "num_attempts": 1,
            "days_attempts": 1,
            "num_sends": 1
        },
        {
            "tick_id": 2,
            "user_id": TEST_USER_ID,
            "send_date": date(2023, 1, 2),
            "location": "Another Crag, UT",
            "crux_angle": CruxAngle.OVERHANG,
            "crux_energy": CruxEnergyType.POWER_ENDURANCE,
            "binned_code": 15,
            "num_attempts": 3,
            "days_attempts": 2,
            "num_sends": 1
        }
    ]

@pytest.mark.asyncio
async def test_save_user_ticks(db_service, mock_session, sample_ticks_data):
    """Test saving user ticks to database."""
    # Act
    result = await db_service.save_user_ticks(sample_ticks_data, TEST_USER_ID)
    
    # Assert
    mock_session.add_all.assert_called_once()
    mock_session.flush.assert_called_once()
    assert len(result) == 2
    assert all(tick.user_id == TEST_USER_ID for tick in result)

@pytest.mark.asyncio
async def test_save_user_ticks_error(db_service, mock_session, sample_ticks_data):
    """Test error handling when saving user ticks."""
    # Arrange
    mock_session.add_all.side_effect = SQLAlchemyError("Database error")
    
    # Act & Assert
    with pytest.raises(DatabaseError) as exc_info:
        await db_service.save_user_ticks(sample_ticks_data, TEST_USER_ID)
    
    assert "Error saving user ticks" in str(exc_info.value)
    mock_session.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_save_performance_pyramid(db_service, mock_session, sample_pyramid_data):
    """Test saving performance pyramid data to database."""
    # Act
    result = await db_service.save_performance_pyramid(sample_pyramid_data, TEST_USER_ID)
    
    # Assert
    mock_session.add_all.assert_called_once()
    mock_session.flush.assert_called_once()
    assert len(result) == 2
    assert all(pyramid.user_id == TEST_USER_ID for pyramid in result)

@pytest.mark.asyncio
async def test_save_performance_pyramid_error(db_service, mock_session, sample_pyramid_data):
    """Test error handling when saving performance pyramid."""
    # Arrange
    mock_session.add_all.side_effect = SQLAlchemyError("Database error")
    
    # Act & Assert
    with pytest.raises(DatabaseError) as exc_info:
        await db_service.save_performance_pyramid(sample_pyramid_data, TEST_USER_ID)
    
    assert "Error saving performance pyramid" in str(exc_info.value)
    mock_session.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_save_tags(db_service, mock_session):
    """Test saving tags to database."""
    # Arrange
    tag_names = ["Test Tag 1", "Test Tag 2"]
    tick_ids = [1, 2]
    
    # Configure mock to return ticks
    mock_ticks = [
        MagicMock(spec=UserTicks, id=1, tags=[]),
        MagicMock(spec=UserTicks, id=2, tags=[])
    ]
    
    # Setup the mock result structure
    mock_result = MagicMock()
    mock_scalar_result = MagicMock()
    mock_result.scalars = MagicMock(return_value=mock_scalar_result)
    mock_scalar_result.all = MagicMock(return_value=mock_ticks)
    
    # Configure scalar_one_or_none to return None (tags don't exist yet)
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    
    # Set up the execute to return our mock result
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    # Act
    result = await db_service.save_tags(tag_names, tick_ids)
    
    # Assert
    assert mock_session.add.call_count >= 2  # Two tags added
    assert mock_session.flush.call_count >= 1
    assert mock_session.execute.call_count >= 1

@pytest.mark.asyncio
async def test_save_tags_error(db_service, mock_session):
    """Test error handling when saving tags."""
    # Arrange
    tag_names = ["Test Tag 1", "Test Tag 2"]
    tick_ids = [1, 2]
    
    # Make execute raise an exception
    mock_session.execute.side_effect = SQLAlchemyError("Database error")
    
    # Act & Assert
    with pytest.raises(DatabaseError) as exc_info:
        await db_service.save_tags(tag_names, tick_ids)
    
    assert "Error saving tags" in str(exc_info.value)
    mock_session.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_update_sync_timestamp_mtn_project(db_service, mock_session):
    """Test updating Mountain Project sync timestamp."""
    # Arrange
    logbook_type = LogbookType.MOUNTAIN_PROJECT
    
    # Configure mock to return a user
    user_mock = MagicMock(spec=User, id=TEST_USER_ID, mtn_project_last_sync=None, eight_a_last_sync=None)
    
    # Setup the mock result structure
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=user_mock)
    
    # Set up the execute to return our mock result
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    # Act
    await db_service.update_sync_timestamp(TEST_USER_ID, logbook_type)
    
    # Assert
    mock_session.execute.assert_called_once()
    mock_session.flush.assert_called_once()
    assert user_mock.mtn_project_last_sync is not None

@pytest.mark.asyncio
async def test_update_sync_timestamp_eight_a_nu(db_service, mock_session):
    """Test updating 8a.nu sync timestamp."""
    # Arrange
    logbook_type = LogbookType.EIGHT_A_NU
    
    # Configure mock to return a user
    user_mock = MagicMock(spec=User, id=TEST_USER_ID, mtn_project_last_sync=None, eight_a_last_sync=None)
    
    # Setup the mock result structure
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=user_mock)
    
    # Set up the execute to return our mock result
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    # Act
    await db_service.update_sync_timestamp(TEST_USER_ID, logbook_type)
    
    # Assert
    mock_session.execute.assert_called_once()
    mock_session.flush.assert_called_once()
    assert user_mock.eight_a_last_sync is not None

@pytest.mark.asyncio
async def test_update_sync_timestamp_user_not_found(db_service, mock_session):
    """Test updating sync timestamp for non-existent user."""
    # Arrange
    logbook_type = LogbookType.MOUNTAIN_PROJECT
    
    # Configure mock to return None (user not found)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    
    # Set up the execute to return our mock result
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    # Act & Assert
    with pytest.raises(DatabaseError) as exc_info:
        await db_service.update_sync_timestamp(TEST_USER_ID, logbook_type)
    
    assert f"User {TEST_USER_ID} not found" in str(exc_info.value)

@pytest.mark.asyncio
async def test_update_sync_timestamp_error(db_service, mock_session):
    """Test error handling when updating sync timestamp."""
    # Arrange
    logbook_type = LogbookType.MOUNTAIN_PROJECT
    
    # Make execute raise an exception
    mock_session.execute.side_effect = SQLAlchemyError("Database error")
    
    # Act & Assert
    with pytest.raises(DatabaseError) as exc_info:
        await db_service.update_sync_timestamp(TEST_USER_ID, logbook_type)
    
    assert "Error updating sync timestamp" in str(exc_info.value)
    mock_session.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_get_user_ticks(db_service, mock_session):
    """Test retrieving user ticks."""
    # Arrange
    # Create test ticks
    test_ticks = [
        MagicMock(spec=UserTicks, id=1, route_name="Test Route 1", tags=[]),
        MagicMock(spec=UserTicks, id=2, route_name="Test Route 2", tags=[])
    ]
    
    # Configure mock to return ticks
    mock_result = MagicMock()
    mock_scalar_result = MagicMock()
    mock_result.scalars = MagicMock(return_value=mock_scalar_result)
    mock_scalar_result.all = MagicMock(return_value=test_ticks)
    
    # Set up the execute to return our mock result
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    # Act
    result = await db_service.get_user_ticks(TEST_USER_ID, include_tags=True)
    
    # Assert
    assert len(result) == 2
    assert result[0].route_name == "Test Route 1"
    assert result[1].route_name == "Test Route 2"
    assert mock_session.execute.called

@pytest.mark.asyncio
async def test_get_user_ticks_error(db_service, mock_session):
    """Test error handling when retrieving user ticks."""
    # Arrange
    mock_session.execute.side_effect = SQLAlchemyError("Database error")
    
    # Act & Assert
    with pytest.raises(DatabaseError) as exc_info:
        await db_service.get_user_ticks(TEST_USER_ID)
    
    assert "Error retrieving user ticks" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_performance_pyramid(db_service, mock_session):
    """Test retrieving performance pyramid data."""
    # Arrange
    # Create test pyramids
    test_pyramids = [
        MagicMock(spec=PerformancePyramid, id=1, user_id=TEST_USER_ID, tick_id=1),
        MagicMock(spec=PerformancePyramid, id=2, user_id=TEST_USER_ID, tick_id=2)
    ]
    
    # Configure mock to return pyramid data
    mock_result = MagicMock()
    mock_scalar_result = MagicMock()
    mock_result.scalars = MagicMock(return_value=mock_scalar_result)
    mock_scalar_result.all = MagicMock(return_value=test_pyramids)
    
    # Set up the execute to return our mock result
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    # Act
    result = await db_service.get_performance_pyramid(TEST_USER_ID)
    
    # Assert
    assert len(result) == 2
    assert result[0].tick_id == 1
    assert result[1].tick_id == 2
    assert mock_session.execute.called

@pytest.mark.asyncio
async def test_get_performance_pyramid_error(db_service, mock_session):
    """Test error handling when retrieving performance pyramid."""
    # Arrange
    mock_session.execute.side_effect = SQLAlchemyError("Database error")
    
    # Act & Assert
    with pytest.raises(DatabaseError) as exc_info:
        await db_service.get_performance_pyramid(TEST_USER_ID)
    
    assert "Error retrieving performance pyramid" in str(exc_info.value)

@pytest.mark.asyncio
async def test_cleanup(db_service, mock_session):
    """Test database session cleanup."""
    # Act
    await db_service.cleanup()
    
    # Assert
    mock_session.close.assert_called_once()

@pytest.mark.asyncio
async def test_cleanup_error(db_service, mock_session):
    """Test error handling during session cleanup."""
    # Arrange
    mock_session.close.side_effect = Exception("Error closing session")
    
    # Act
    await db_service.cleanup()
    
    # Assert
    mock_session.close.assert_called_once()
    # No exception should be raised, just logged

@pytest.mark.asyncio
async def test_get_instance():
    """Test get_instance class method."""
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)
    
    # Create a proper async generator for get_db
    async def mock_get_db():
        yield mock_session
    
    # Act
    with patch('app.services.logbook.database_service.get_db', return_value=mock_get_db()):
        async for service in DatabaseService.get_instance():
            # Assert
            assert isinstance(service, DatabaseService)
            assert service.session is mock_session
            break 