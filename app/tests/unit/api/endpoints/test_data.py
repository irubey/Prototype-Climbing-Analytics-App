"""
Unit tests for data API endpoints.

This module tests the data endpoints in the API,
focusing on tick management, performance pyramid updates,
and data refresh operations.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.data import (
    create_ticks_batch, 
    delete_tick, 
    update_pyramid, 
    refresh_data
)
from app.models import User, UserTicks, PerformancePyramid
from app.models.enums import ClimbingDiscipline, LogbookType
from app.schemas.data import (
    TickCreate,
    BatchTickCreate,
    PyramidInput,
    PerformanceData
)
from app.services.utils.grade_service import GradeService, GradingSystem

# Test constants
TEST_USER_ID = uuid.uuid4()
TEST_TICK_ID = 123

@pytest.fixture
def test_user():
    """Create a test user instance."""
    user = MagicMock(spec=User)
    user.id = TEST_USER_ID
    user.mountain_project_url = "https://www.mountainproject.com/user/12345/test-user"
    user.eight_a_nu_url = "https://www.8a.nu/user/test-user"
    return user

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock(spec=AsyncSession)

@pytest.fixture
def mock_background_tasks():
    """Create a mock BackgroundTasks instance."""
    return MagicMock(spec=BackgroundTasks)

@pytest.fixture
def mock_tick():
    """Create a mock tick instance."""
    tick = MagicMock(spec=UserTicks)
    tick.id = TEST_TICK_ID
    tick.user_id = TEST_USER_ID
    return tick

@pytest.fixture
def mock_pyramid():
    """Create a mock performance pyramid instance."""
    pyramid = MagicMock(spec=PerformancePyramid)
    pyramid.tick_id = TEST_TICK_ID
    pyramid.user_id = TEST_USER_ID
    pyramid.attempts = 3
    pyramid.duration_minutes = 45
    return pyramid

@pytest.fixture
def sample_tick_data():
    """Create sample tick data for testing."""
    return TickCreate(
        route_name="Test Route",
        route_grade="5.10a",
        discipline=ClimbingDiscipline.SPORT,
        tick_date="2023-05-15",
        send_bool=True,
        lead_style="Redpoint",
        length=30,
        location="Red River Gorge",
        logbook_type=LogbookType.MOUNTAIN_PROJECT,
        performance_data=PerformanceData(
            attempts=3,
            duration_minutes=45,
            crux_type="Crimpy",
            angle_type="Vertical",
            energy_type="Power"
        )
    )

@pytest.mark.asyncio
async def test_create_ticks_batch_success(
    test_user,
    mock_db,
    sample_tick_data
):
    """Test successful batch creation of ticks."""
    # Arrange
    # Create a modified sample_tick_data without binned_code for the test
    modified_tick_data = sample_tick_data.model_copy()
    modified_tick_data.binned_code = None  # Ensure binned_code is None
    batch_data = BatchTickCreate(ticks=[modified_tick_data, modified_tick_data])
    
    # Mock the grade service
    with patch("app.api.v1.endpoints.data.GradeService") as mock_grade_service_cls:
        mock_grade_service = AsyncMock()
        mock_grade_service_cls.get_instance.return_value = mock_grade_service
        mock_grade_service.convert_to_code.return_value = 100  # Mock binned code
        
        # Mock the database operations
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        
        # Set up mock tick object
        mock_tick = MagicMock()
        mock_tick.id = TEST_TICK_ID
        
        # Patch the model_dump method to exclude binned_code
        original_model_dump = type(modified_tick_data).model_dump
        
        def patched_model_dump(self, *args, **kwargs):
            kwargs.setdefault('exclude', set())
            if isinstance(kwargs['exclude'], set):
                kwargs['exclude'].add('binned_code')
            elif isinstance(kwargs['exclude'], dict):
                kwargs['exclude']['binned_code'] = True
            return original_model_dump(self, *args, **kwargs)
        
        # Patch at the class level, not the instance level
        with patch.object(type(modified_tick_data), 'model_dump', patched_model_dump):
            # Replace the UserTicks constructor
            with patch("app.api.v1.endpoints.data.UserTicks", return_value=mock_tick):
                # Replace the PerformancePyramid constructor
                with patch("app.api.v1.endpoints.data.PerformancePyramid", return_value=MagicMock()):
                    
                    # Act
                    result = await create_ticks_batch(
                        ticks=batch_data,
                        db=mock_db,
                        current_user=test_user
                    )
                    
                    # Assert
                    assert len(result) == 2
                    assert result[0] == TEST_TICK_ID
                    assert result[1] == TEST_TICK_ID
                    assert mock_db.add.call_count == 4  # 2 ticks and 2 pyramids
                    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_create_ticks_batch_invalid_grade(
    test_user,
    mock_db,
    sample_tick_data
):
    """Test batch creation with invalid grade data."""
    # Arrange
    sample_tick_data.route_grade = "Invalid Grade"
    batch_data = BatchTickCreate(ticks=[sample_tick_data])
    
    # Mock the grade service
    with patch("app.api.v1.endpoints.data.GradeService") as mock_grade_service_cls:
        mock_grade_service = AsyncMock()
        mock_grade_service_cls.get_instance.return_value = mock_grade_service
        mock_grade_service.convert_to_code.side_effect = ValueError("Invalid grade")
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await create_ticks_batch(
                ticks=batch_data,
                db=mock_db,
                current_user=test_user
            )
        
        assert exc_info.value.status_code == 400
        assert "Invalid grade" in exc_info.value.detail

@pytest.mark.asyncio
async def test_delete_tick_success(
    test_user,
    mock_db,
    mock_tick
):
    """Test successful tick deletion."""
    # Arrange
    mock_scalar_result = AsyncMock()
    mock_scalar_result.scalar_one_or_none.return_value = mock_tick
    mock_db.execute.return_value = mock_scalar_result
    
    # Act
    await delete_tick(
        tick_id=TEST_TICK_ID,
        db=mock_db,
        current_user=test_user
    )
    
    # Assert
    assert mock_db.execute.call_count == 3  # Select, delete pyramid, delete tick
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_delete_tick_not_found(
    test_user,
    mock_db
):
    """Test tick deletion when tick is not found."""
    # Arrange
    mock_scalar_result = AsyncMock()
    mock_scalar_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_scalar_result
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await delete_tick(
            tick_id=TEST_TICK_ID,
            db=mock_db,
            current_user=test_user
        )
    
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail
    # Verify no delete operations were performed
    assert mock_db.execute.call_count == 1  # Only the select operation

@pytest.mark.asyncio
async def test_update_pyramid_existing(mock_db):
    """Test updating an existing pyramid entry."""
    # Arrange
    pyramid_data = PyramidInput(
        tick_id=TEST_TICK_ID,
        attempts=5,
        duration_minutes=60,
        crux_type="Slopey",
        angle_type="Overhang",
        energy_type="Endurance"
    )
    
    # Create mock tick and pyramid
    mock_tick = MagicMock()
    mock_pyramid = MagicMock()
    
    # Set up the mock database responses
    mock_tick_result = AsyncMock()
    mock_tick_result.scalar_one_or_none = AsyncMock(return_value=mock_tick)
    
    mock_pyramid_result = AsyncMock()
    mock_pyramid_result.scalar_one_or_none = AsyncMock(return_value=mock_pyramid)
    
    # Set up the side effect to return different results for different queries
    mock_db.execute = AsyncMock(side_effect=[mock_tick_result, mock_pyramid_result])
    mock_db.refresh = AsyncMock()
    mock_db.commit = AsyncMock()
    
    # Set up a side effect for setattr to actually set the attributes on the mock
    original_setattr = setattr
    
    def mock_setattr(obj, name, value):
        if obj is mock_pyramid:
            original_setattr(mock_pyramid, name, value)
    
    # Use patch to replace setattr during the test
    with patch('app.api.v1.endpoints.data.setattr', side_effect=mock_setattr):
        # Act
        result = await update_pyramid(
            pyramid_data=pyramid_data,
            db=mock_db,
            current_user=MagicMock()
        )
        
        # Assert
        assert result == pyramid_data
        assert mock_db.refresh.called
        assert mock_db.commit.called
        
        # Verify attributes were updated on the mock pyramid
        assert mock_pyramid.attempts == 5
        assert mock_pyramid.duration_minutes == 60
        assert mock_pyramid.crux_type == "Slopey"
        assert mock_pyramid.angle_type == "Overhang"
        assert mock_pyramid.energy_type == "Endurance"
        
        # Verify the mock_db.execute was called twice
        assert mock_db.execute.call_count == 2

@pytest.mark.asyncio
async def test_update_pyramid_new(
    test_user,
    mock_db,
    mock_tick
):
    """Test creating a new performance pyramid when none exists."""
    # Arrange
    pyramid_data = PyramidInput(
        tick_id=TEST_TICK_ID,
        attempts=5,
        duration_minutes=60,
        crux_type="Slopey",
        angle_type="Overhang",
        energy_type="Endurance"
    )
    
    # Mock the database query for tick
    mock_tick_result = AsyncMock()
    mock_tick_result.scalar_one_or_none.return_value = mock_tick
    
    # Mock the database query for pyramid (not found)
    mock_pyramid_result = AsyncMock()
    mock_pyramid_result.scalar_one_or_none.return_value = None
    
    mock_db.execute.side_effect = [
        mock_tick_result,
        mock_pyramid_result
    ]
    
    # Create a proper mock for the new pyramid instance
    mock_new_pyramid = MagicMock()
    mock_new_pyramid.tick_id = TEST_TICK_ID
    mock_new_pyramid.user_id = TEST_USER_ID
    
    # We need to patch in a way that doesn't affect the select statement
    # Use a more targeted patch that only affects the constructor
    original_init = PerformancePyramid.__init__
    
    def patched_init(self, *args, **kwargs):
        # Don't actually initialize, just return our mock
        pass
    
    # Apply the patch only for the constructor
    with patch.object(PerformancePyramid, '__init__', patched_init):
        # Also patch add to track when it's called with our mock
        with patch.object(mock_db, 'add') as mock_add:
            # Act
            result = await update_pyramid(
                pyramid_data=pyramid_data,
                db=mock_db,
                current_user=test_user
            )
            
            # Assert
            assert result == pyramid_data
            mock_add.assert_called_once()

@pytest.mark.asyncio
async def test_update_pyramid_tick_not_found(
    test_user,
    mock_db
):
    """Test updating pyramid for a non-existent tick."""
    # Arrange
    pyramid_data = PyramidInput(
        tick_id=TEST_TICK_ID,
        attempts=5,
        duration_minutes=60
    )
    
    # Mock the database query for tick (not found)
    mock_tick_result = AsyncMock()
    mock_tick_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_tick_result
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await update_pyramid(
            pyramid_data=pyramid_data,
            db=mock_db,
            current_user=test_user
        )
    
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail

@pytest.mark.asyncio
async def test_refresh_data_success(
    test_user,
    mock_db,
    mock_background_tasks
):
    """Test successful data refresh initiation."""
    # Act
    result = await refresh_data(
        background_tasks=mock_background_tasks,
        db=mock_db,
        current_user=test_user
    )
    
    # Assert
    assert result.status == "pending"
    assert "background" in result.message
    # Note: Currently, background tasks are commented out in the implementation
    # so we don't expect any task to be added
    assert not mock_background_tasks.add_task.called

@pytest.mark.asyncio
async def test_refresh_data_no_logbooks(
    test_user,
    mock_db,
    mock_background_tasks
):
    """Test data refresh with no logbook URLs configured."""
    # Arrange
    test_user.mountain_project_url = None
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await refresh_data(
            background_tasks=mock_background_tasks,
            db=mock_db,
            current_user=test_user
        )
    
    assert exc_info.value.status_code == 400
    assert "not configured" in exc_info.value.detail 