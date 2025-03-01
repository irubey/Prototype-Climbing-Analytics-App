"""
Unit tests for visualization API endpoints.

This module tests the visualization endpoints in the API,
focusing on dashboard metrics, performance analytics,
and climbing data visualization capabilities.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.api.v1.endpoints.visualization import (
    get_dashboard_data,
    get_performance_data,
    get_performance_pyramid,
    get_base_volume,
    get_progression,
    get_location_analysis,
    get_performance_characteristics
)
from app.models import User, UserTicks, PerformancePyramid
from app.models.enums import ClimbingDiscipline
from app.schemas.visualization import (
    DashboardBaseMetrics,
    DashboardPerformanceMetrics,
    PerformancePyramidData,
    BaseVolumeData,
    ProgressionData,
    LocationAnalysis,
    PerformanceCharacteristics
)

# Mock functions to patch in the tested module
# These correspond to the functions we're patching in our tests
async def get_performance_pyramid_data(db, user_id, discipline):
    """Mock implementation for performance pyramid data retrieval."""
    return {}

async def get_base_volume_data(db, user_id):
    """Mock implementation for base volume data retrieval."""
    return {}

async def get_progression_data(db, user_id):
    """Mock implementation for progression data retrieval."""
    return {}

async def get_location_analysis_data(db, user_id):
    """Mock implementation for location analysis data retrieval."""
    return {}

async def get_performance_characteristics_data(db, user_id):
    """Mock implementation for performance characteristics data retrieval."""
    return {}

# Test constants
TEST_USER_ID = uuid.uuid4()

@pytest.fixture
def test_user():
    """Create a test user instance."""
    user = MagicMock(spec=User)
    user.id = TEST_USER_ID
    return user

@pytest.fixture
def mock_db(create_async_mock_db):
    """Create a properly configured mock database session using the factory."""
    return create_async_mock_db()

@pytest.fixture
def mock_dashboard_metrics():
    """Create mock dashboard metrics."""
    return DashboardBaseMetrics(
        recent_ticks=[],
        discipline_stats={"sport": 15, "boulder": 10, "trad": 5},
        grade_distribution={"5.10a": 5, "5.11b": 4, "V3": 6},
        total_climbs=30
    )

@pytest.fixture
def mock_performance_metrics():
    """Create mock performance metrics."""
    return DashboardPerformanceMetrics(
        highest_grades={"sport": "5.12a", "boulder": "V6"},
        latest_hard_sends=[]
    )

@pytest.fixture
def mock_pyramid_data():
    """Create mock performance pyramid data."""
    return {
        "discipline": ClimbingDiscipline.SPORT,
        "grade_counts": {"5.10a": 5, "5.11b": 3, "5.12a": 1},
        "total_sends": 9
    }

@pytest.fixture
def mock_base_volume_data():
    """Create mock base volume data."""
    return {
        "volume_by_difficulty": {
            "Base Volume": {"count": 25, "avg_length": 20.5},
            "Project": {"count": 5, "avg_length": 35.0}
        }
    }

@pytest.fixture
def mock_progression_data():
    """Create mock progression data."""
    return {
        "grade_progression": {
            "sport": [
                {"date": "2023-01-01", "grade": "5.10b"},
                {"date": "2023-03-01", "grade": "5.11a"}
            ],
            "boulder": [
                {"date": "2023-02-01", "grade": "V3"},
                {"date": "2023-04-01", "grade": "V5"}
            ]
        },
        "volume_progression": {
            "months": ["Jan", "Feb", "Mar", "Apr"],
            "counts": [5, 8, 10, 7]
        }
    }

@pytest.fixture
def mock_location_data():
    """Create mock location analysis data."""
    return {
        "locations": [
            {"name": "Red River Gorge", "count": 15, "top_grade": "5.12a"},
            {"name": "Bishop", "count": 10, "top_grade": "V6"}
        ],
        "location_distribution": {
            "Red River Gorge": 0.6,
            "Bishop": 0.4
        }
    }

@pytest.fixture
def mock_characteristics_data():
    """Create mock performance characteristics data."""
    return {
        "crux_types": {
            "crimp": 10,
            "slab": 8,
            "overhang": 7
        },
        "energy_systems": {
            "power": 15,
            "endurance": 10
        },
        "angles": {
            "vertical": 12,
            "overhanging": 8
        }
    }

@pytest.mark.asyncio
async def test_get_dashboard_data(
    test_user,
    mock_db,
    mock_dashboard_metrics
):
    """Test getting dashboard base metrics."""
    # Arrange
    with patch("app.api.v1.endpoints.visualization.get_dashboard_base_metrics", 
               return_value=mock_dashboard_metrics) as mock_get_metrics:
        
        # Act
        result = await get_dashboard_data(
            time_range=30,
            current_user=test_user,
            db=mock_db
        )
        
        # Assert
        assert result == mock_dashboard_metrics
        mock_get_metrics.assert_called_once_with(
            db=mock_db,
            user_id=test_user.id,
            time_range=timedelta(days=30)
        )

@pytest.mark.asyncio
async def test_get_dashboard_data_no_time_range(
    test_user,
    mock_db,
    mock_dashboard_metrics
):
    """Test getting dashboard metrics without time range."""
    # Arrange
    with patch("app.api.v1.endpoints.visualization.get_dashboard_base_metrics", 
               return_value=mock_dashboard_metrics) as mock_get_metrics:
        
        # Act
        result = await get_dashboard_data(
            time_range=None,
            current_user=test_user,
            db=mock_db
        )
        
        # Assert
        assert result == mock_dashboard_metrics
        mock_get_metrics.assert_called_once_with(
            db=mock_db,
            user_id=test_user.id,
            time_range=None
        )

@pytest.mark.asyncio
async def test_get_dashboard_data_error_handling(
    test_user,
    mock_db
):
    """Test error handling in dashboard data retrieval."""
    # Arrange
    with patch("app.api.v1.endpoints.visualization.get_dashboard_base_metrics", 
               side_effect=Exception("Test error")) as mock_get_metrics:
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard_data(
                time_range=None,
                current_user=test_user,
                db=mock_db
            )
        
        assert exc_info.value.status_code == 500
        assert "Could not fetch dashboard data" in exc_info.value.detail

@pytest.mark.asyncio
async def test_get_performance_data(
    test_user,
    mock_db,
    mock_performance_metrics
):
    """Test getting performance metrics."""
    # Arrange
    with patch("app.api.v1.endpoints.visualization.get_dashboard_performance_metrics", 
               return_value=mock_performance_metrics) as mock_get_metrics:
        
        # Act
        result = await get_performance_data(
            discipline=ClimbingDiscipline.SPORT,
            time_range=30,
            current_user=test_user,
            db=mock_db
        )
        
        # Assert
        assert result == mock_performance_metrics
        mock_get_metrics.assert_called_once_with(
            db=mock_db,
            user_id=test_user.id,
            discipline=ClimbingDiscipline.SPORT,
            time_range=timedelta(days=30)
        )

@pytest.mark.asyncio
async def test_get_performance_data_error_handling(
    test_user,
    mock_db
):
    """Test error handling in performance data retrieval."""
    # Arrange
    with patch("app.api.v1.endpoints.visualization.get_dashboard_performance_metrics", 
               side_effect=Exception("Test error")) as mock_get_metrics:
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_performance_data(
                discipline=None,
                time_range=None,
                current_user=test_user,
                db=mock_db
            )
        
        assert exc_info.value.status_code == 500
        assert "Could not fetch performance data" in exc_info.value.detail

@pytest.mark.asyncio
async def test_get_performance_pyramid(
    test_user,
    mock_db,
    mock_pyramid_data
):
    """Test getting performance pyramid data."""
    # Arrange
    with patch("app.api.v1.endpoints.visualization.get_performance_pyramid_data", 
               return_value=mock_pyramid_data) as mock_get_pyramid:
        
        # Act
        result = await get_performance_pyramid(
            current_user=test_user,
            db=mock_db,
            discipline=ClimbingDiscipline.SPORT
        )
        
        # Assert
        assert result == mock_pyramid_data
        mock_get_pyramid.assert_called_once_with(
            db=mock_db,
            user_id=test_user.id,
            discipline=ClimbingDiscipline.SPORT
        )

@pytest.mark.asyncio
async def test_get_performance_pyramid_error_handling(
    test_user,
    mock_db
):
    """Test error handling in performance pyramid retrieval."""
    # Arrange
    mock_db.execute.side_effect = Exception("Test error")
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_performance_pyramid(
            current_user=test_user,
            db=mock_db,
            discipline=ClimbingDiscipline.SPORT
        )
    
    assert exc_info.value.status_code == 500
    assert "Could not fetch performance pyramid" in exc_info.value.detail

@pytest.mark.asyncio
async def test_get_base_volume(
    test_user,
    mock_db,
    mock_base_volume_data
):
    """Test getting base volume data."""
    # Arrange
    with patch("app.api.v1.endpoints.visualization.get_base_volume_data", 
               return_value=mock_base_volume_data) as mock_get_volume:
        
        # Act
        result = await get_base_volume(
            current_user=test_user,
            db=mock_db
        )
        
        # Assert
        assert result == mock_base_volume_data
        mock_get_volume.assert_called_once_with(
            db=mock_db,
            user_id=test_user.id
        )

@pytest.mark.asyncio
async def test_get_base_volume_error_handling(
    test_user,
    mock_db
):
    """Test error handling in base volume retrieval."""
    # Arrange
    mock_db.execute.side_effect = Exception("Test error")
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_base_volume(
            current_user=test_user,
            db=mock_db
        )
    
    assert exc_info.value.status_code == 500
    assert "Could not fetch base volume data" in exc_info.value.detail

@pytest.mark.asyncio
async def test_get_progression(
    test_user,
    mock_db,
    mock_progression_data
):
    """Test getting progression data."""
    # Arrange
    with patch("app.api.v1.endpoints.visualization.get_progression_data", 
               return_value=mock_progression_data) as mock_get_progression:
        with patch("datetime.datetime", wraps=datetime) as mock_datetime:
            # Fix a specific date for testing
            mock_datetime.now.return_value = datetime(2023, 5, 1)
            
            # Act
            result = await get_progression(
                current_user=test_user,
                db=mock_db
            )
        
        # Assert
        assert result == mock_progression_data
        mock_get_progression.assert_called_once_with(
            db=mock_db,
            user_id=test_user.id
        )

@pytest.mark.asyncio
async def test_get_progression_error_handling(
    test_user,
    mock_db
):
    """Test error handling in progression data retrieval."""
    # Arrange
    mock_db.execute.side_effect = Exception("Test error")
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_progression(
            current_user=test_user,
            db=mock_db
        )
    
    assert exc_info.value.status_code == 500
    assert "Could not fetch progression data" in exc_info.value.detail

@pytest.mark.asyncio
async def test_get_location_analysis(
    test_user,
    mock_db,
    mock_location_data
):
    """Test getting location analysis data."""
    # Arrange
    with patch("app.api.v1.endpoints.visualization.get_location_analysis_data", 
               return_value=mock_location_data) as mock_get_location:
        
        # Act
        result = await get_location_analysis(
            current_user=test_user,
            db=mock_db
        )
        
        # Assert
        assert result == mock_location_data
        mock_get_location.assert_called_once_with(
            db=mock_db,
            user_id=test_user.id
        )

@pytest.mark.asyncio
async def test_get_location_analysis_error_handling(
    test_user,
    mock_db
):
    """Test error handling in location analysis retrieval."""
    # Arrange
    mock_db.execute.side_effect = Exception("Test error")
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_location_analysis(
            current_user=test_user,
            db=mock_db
        )
    
    assert exc_info.value.status_code == 500
    assert "Could not fetch location analysis" in exc_info.value.detail

@pytest.mark.asyncio
async def test_get_performance_characteristics(
    test_user,
    mock_db,
    mock_characteristics_data
):
    """Test getting performance characteristics data."""
    # Arrange
    with patch("app.api.v1.endpoints.visualization.get_performance_characteristics_data", 
               return_value=mock_characteristics_data) as mock_get_characteristics:
        
        # Act
        result = await get_performance_characteristics(
            current_user=test_user,
            db=mock_db
        )
        
        # Assert
        assert result == mock_characteristics_data
        mock_get_characteristics.assert_called_once_with(
            db=mock_db,
            user_id=test_user.id
        )

@pytest.mark.asyncio
async def test_get_performance_characteristics_error_handling(
    test_user,
    mock_db
):
    """Test error handling in performance characteristics retrieval."""
    # Arrange
    mock_db.execute.side_effect = Exception("Test error")
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_performance_characteristics(
            current_user=test_user,
            db=mock_db
        )
    
    assert exc_info.value.status_code == 500
    assert "Could not fetch performance characteristics" in exc_info.value.detail

# Additional tests for helper functions to improve code coverage

@pytest.mark.asyncio
async def test_get_base_volume_data_database_error():
    """Test handling of specific database errors in base volume retrieval."""
    # Arrange
    mock_db = AsyncMock(spec=AsyncSession)
    from sqlalchemy.exc import SQLAlchemyError
    mock_db.execute.side_effect = SQLAlchemyError("Database connection error")
    
    # Import the actual helper function
    from app.api.v1.endpoints.visualization import get_base_volume_data
    
    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        await get_base_volume_data(
            db=mock_db,
            user_id=TEST_USER_ID
        )
    
    # Verify the error was raised and propagated
    assert "Database connection error" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_location_analysis_data_database_error():
    """Test error handling in location analysis data when database fails."""
    # Arrange
    mock_db = AsyncMock(spec=AsyncSession)
    from sqlalchemy.exc import SQLAlchemyError
    
    # First query fails with database error
    mock_db.execute.side_effect = SQLAlchemyError("Database connection error")
    
    # Import the actual helper function
    from app.api.v1.endpoints.visualization import get_location_analysis_data
    
    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        await get_location_analysis_data(
            db=mock_db,
            user_id=TEST_USER_ID
        )
    
    # Verify the error was raised and propagated
    assert "Database connection error" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_performance_pyramid_data_database_error():
    """Test error handling in performance pyramid data retrieval with database error."""
    # Arrange
    mock_db = AsyncMock(spec=AsyncSession)
    from sqlalchemy.exc import SQLAlchemyError
    mock_db.execute.side_effect = SQLAlchemyError("Database connection error")
    
    # Import the actual helper function
    from app.api.v1.endpoints.visualization import get_performance_pyramid_data
    
    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        await get_performance_pyramid_data(
            db=mock_db,
            user_id=TEST_USER_ID,
            discipline=ClimbingDiscipline.SPORT
        )
    
    # Verify the error was raised and propagated
    assert "Database connection error" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_progression_data_database_error():
    """Test error handling in progression data retrieval with database error."""
    # Arrange
    mock_db = AsyncMock(spec=AsyncSession)
    from sqlalchemy.exc import SQLAlchemyError
    mock_db.execute.side_effect = SQLAlchemyError("Database connection error")
    
    # Import the actual helper function
    from app.api.v1.endpoints.visualization import get_progression_data
    
    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        await get_progression_data(
            db=mock_db,
            user_id=TEST_USER_ID
        )
    
    # Verify the error was raised and propagated
    assert "Database connection error" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_performance_characteristics_data_database_error():
    """Test error handling in performance characteristics data with database error."""
    # Arrange
    mock_db = AsyncMock(spec=AsyncSession)
    from sqlalchemy.exc import SQLAlchemyError
    mock_db.execute.side_effect = SQLAlchemyError("Database connection error")
    
    # Import the actual helper function
    from app.api.v1.endpoints.visualization import get_performance_characteristics_data
    
    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        await get_performance_characteristics_data(
            db=mock_db,
            user_id=TEST_USER_ID
        )
    
    # Verify the error was raised and propagated
    assert "Database connection error" in str(exc_info.value) 