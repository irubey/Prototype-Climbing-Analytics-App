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
    create_async_mock_db
):
    """Test getting performance pyramid data."""
    # Arrange
    # Create a mock pyramid entry with a mock tick
    mock_tick = MagicMock(spec=UserTicks)
    mock_tick.route_grade = "5.10a"
    mock_tick.discipline = ClimbingDiscipline.SPORT
    mock_tick.send_bool = True
    
    mock_pyramid_entry = MagicMock(spec=PerformancePyramid)
    mock_pyramid_entry.tick = mock_tick
    mock_pyramid_entry.binned_code = 100
    
    # Use the create_async_mock_db helper with the right return type pattern
    # The factory needs to receive what should be returned by result.scalars().all()
    mock_db = create_async_mock_db([mock_pyramid_entry])
    
    # Act
    result = await get_performance_pyramid(
        current_user=test_user,
        db=mock_db,
        discipline=ClimbingDiscipline.SPORT
    )
    
    # Assert
    assert isinstance(result, dict)
    assert result["discipline"] == ClimbingDiscipline.SPORT
    assert "grade_counts" in result
    assert "total_sends" in result
    assert "5.10a" in result["grade_counts"]
    assert result["grade_counts"]["5.10a"] == 1
    assert result["total_sends"] == 1
    assert mock_db.execute.called

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
    mock_base_volume_data,
    create_async_mock_db
):
    """Test getting base volume data."""
    # Arrange
    mock_volume_result = [
        ("Base Volume", 25, 20.5),
        ("Project", 5, 35.0)
    ]

    # Use the create_async_mock_db helper to create a properly configured mock
    proper_mock_db = create_async_mock_db(mock_volume_result)
    
    # Act
    result = await get_base_volume(
        current_user=test_user,
        db=proper_mock_db
    )
    
    # Assert
    assert isinstance(result, dict)
    assert "volume_by_difficulty" in result
    assert "Base Volume" in result["volume_by_difficulty"]
    assert "Project" in result["volume_by_difficulty"]
    assert result["volume_by_difficulty"]["Base Volume"]["count"] == 25
    assert result["volume_by_difficulty"]["Project"]["avg_length"] == 35.0
    assert proper_mock_db.execute.called

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
    mock_progression_data,
    create_async_mock_db
):
    """Test getting progression data."""
    # Arrange
    # First call for sport grades
    sport_result = [
        (datetime(2023, 1, 1), "5.10b"),
        (datetime(2023, 3, 1), "5.11a")
    ]
    
    # Second call for boulder grades
    boulder_result = [
        (datetime(2023, 2, 1), "V3"),
        (datetime(2023, 4, 1), "V5")
    ]
    
    # Third call for volume by month
    volume_result = [
        ("2023-01", 5),
        ("2023-02", 8),
        ("2023-03", 10),
        ("2023-04", 7)
    ]
    
    # Use the create_async_mock_db helper to create a properly configured mock
    proper_mock_db = create_async_mock_db([sport_result, boulder_result, volume_result])
    
    # Act
    # Patch the datetime module that's imported in the visualization module
    with patch("datetime.datetime", wraps=datetime) as mock_datetime:
        # Fix a specific date for testing
        mock_datetime.now.return_value = datetime(2023, 5, 1)
        
        result = await get_progression(
            current_user=test_user,
            db=proper_mock_db
        )
    
    # Assert
    assert isinstance(result, dict)
    assert "grade_progression" in result or "progression_by_discipline" in result
    assert "volume_progression" in result or "monthly_volume" in result
    # Check that the mock db was called correctly
    assert proper_mock_db.execute.call_count == 3  # Three database queries

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
    mock_location_data,
    create_async_mock_db
):
    """Test getting location analysis data."""
    # Arrange
    # First query - location data with count and grades array
    location_result = [
        ("Red River Gorge", 15, ["5.10a", "5.11b", "5.12a"]),
        ("Bishop", 10, ["V4", "V5", "V6"])
    ]
    
    # Second query - seasonal data
    seasonal_result = [
        ("Summer", 12),
        ("Winter", 8)
    ]
    
    # Use the create_async_mock_db helper to create a properly configured mock
    proper_mock_db = create_async_mock_db([location_result, seasonal_result])
    
    # Act
    result = await get_location_analysis(
        current_user=test_user,
        db=proper_mock_db
    )
    
    # Assert
    assert isinstance(result, dict)
    assert "locations" in result or "location_distribution" in result
    # Depending on implementation, check relevant keys
    if "location_distribution" in result:
        assert len(result["location_distribution"]) >= 1
    if "seasonal_patterns" in result:
        assert len(result["seasonal_patterns"]) >= 1
    
    assert proper_mock_db.execute.call_count == 2  # Two database queries

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
    mock_characteristics_data,
    create_async_mock_db
):
    """Test getting performance characteristics data."""
    # Arrange
    # Create mock performance pyramid entries
    mock_entries = []
    
    # Entry 1 - Crimpy
    entry1 = MagicMock(spec=PerformancePyramid)
    entry1.crux_type = "crimp"
    entry1.crux_angle = "vertical"
    entry1.crux_energy = "power"
    entry1.num_attempts = 2
    mock_entries.append(entry1)
    
    # Entry 2 - Slab
    entry2 = MagicMock(spec=PerformancePyramid)
    entry2.crux_type = "slab"
    entry2.crux_angle = "vertical"
    entry2.crux_energy = "endurance"
    entry2.num_attempts = 1
    mock_entries.append(entry2)
    
    # Entry 3 - Overhang
    entry3 = MagicMock(spec=PerformancePyramid)
    entry3.crux_type = "overhang"
    entry3.crux_angle = "overhanging"
    entry3.crux_energy = "power"
    entry3.num_attempts = 3
    mock_entries.append(entry3)
    
    # Use the create_async_mock_db helper to create a properly configured mock
    proper_mock_db = create_async_mock_db(mock_entries)
    
    # Act
    result = await get_performance_characteristics(
        current_user=test_user,
        db=proper_mock_db
    )
    
    # Assert
    assert isinstance(result, dict)
    assert any(k in result for k in ["crux_types", "angle_distribution", "energy_systems", "energy_distribution", "attempts_analysis"])
    assert proper_mock_db.execute.called

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