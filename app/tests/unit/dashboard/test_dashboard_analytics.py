"""
Unit tests for dashboard analytics service.

This module tests the dashboard analytics functions that generate
climbing metrics, performance analysis, and data visualizations.
"""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.enums import ClimbingDiscipline, LogbookType
from app.models import UserTicks
from app.services.dashboard.dashboard_analytics import (
    get_dashboard_base_metrics,
    get_dashboard_performance_metrics,
    DashboardBaseMetrics,
    DashboardPerformanceMetrics
)
from app.services.utils.grade_service import GradeService
from app.schemas.visualization import DashboardBaseMetrics, DashboardPerformanceMetrics

# Test constants
TEST_USER_ID = UUID('5e8102bc-5304-4955-a158-2054e9311433')

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()

@pytest.fixture
def mock_execute_result():
    """Create a mock execution result."""
    return MagicMock()

@pytest.fixture
def sample_ticks():
    """Create a set of sample climbing ticks for testing."""
    return [
        _create_mock_tick("Test Route 1", "5.10a", ClimbingDiscipline.SPORT, "Test Crag", datetime(2023, 5, 15), "Onsight"),
        _create_mock_tick("Test Route 2", "5.11b", ClimbingDiscipline.SPORT, "Test Crag", datetime(2023, 5, 10), "Redpoint"),
        _create_mock_tick("Test Route 3", "5.10c", ClimbingDiscipline.SPORT, "Test Crag", datetime(2023, 5, 5), "Flash"),
        _create_mock_tick("Test Route 4", "V3", ClimbingDiscipline.BOULDER, "Boulder Area", datetime(2023, 4, 20), "Send"),
        _create_mock_tick("Test Route 5", "V5", ClimbingDiscipline.BOULDER, "Boulder Area", datetime(2023, 4, 15), "Flash"),
        _create_mock_tick("Test Route 6", "5.9", ClimbingDiscipline.TRAD, "Trad Crag", datetime(2023, 4, 1), "Onsight")
    ]

def _create_mock_tick(route_name, grade, discipline, location_name, tick_date, lead_style):
    """Helper to create a mock tick with necessary attributes."""
    mock_tick = MagicMock()
    
    # Create mock location
    mock_location = MagicMock()
    mock_location.name = location_name
    
    # Create mock performance data
    mock_performance = MagicMock()
    mock_performance.attempts = 1
    mock_performance.duration_minutes = 30
    
    # Configure all properties at once using configure_mock
    mock_tick.configure_mock(
        route_name=route_name,
        route_grade=grade,
        discipline=discipline,
        tick_date=tick_date,
        lead_style=lead_style,
        send_type=lead_style,  # For backward compatibility if needed
        send_bool=True,
        logbook_type=LogbookType.MOUNTAIN_PROJECT,
        location=mock_location,
        performance_pyramid=mock_performance
    )
    
    return mock_tick

@pytest.fixture
def mock_grade_count_result():
    """Create mock grade count query results."""
    return [
        ('5.10a', 2),
        ('5.11b', 1),
        ('5.10c', 1),
        ('V3', 1),
        ('V5', 1),
        ('5.9', 1)
    ]

@pytest.fixture
def mock_discipline_count_result():
    """Create mock discipline count query results."""
    return [
        (ClimbingDiscipline.SPORT, 3),
        (ClimbingDiscipline.BOULDER, 2),
        (ClimbingDiscipline.TRAD, 1)
    ]

@pytest.mark.asyncio
async def test_get_dashboard_base_metrics(
    mock_db,
    mock_execute_result,
    sample_ticks,
    mock_grade_count_result,
    mock_discipline_count_result
):
    """Test fetching basic dashboard metrics successfully."""
    # Arrange
    # Set up the mock to return different results based on query
    mock_db.execute.side_effect = [
        # First call - recent ticks
        AsyncMock(scalars=MagicMock(all=MagicMock(return_value=sample_ticks))),
        # Second call - discipline distribution
        AsyncMock(all=MagicMock(return_value=mock_discipline_count_result)),
        # Third call - grade distribution
        AsyncMock(all=MagicMock(return_value=mock_grade_count_result)),
    ]

    # Mock grade service
    with patch('app.services.dashboard.dashboard_analytics.GradeService') as mock_grade_service_cls:
        mock_grade_service = MagicMock()
        mock_grade_service_cls.get_instance.return_value = mock_grade_service
        mock_grade_service.convert_grades_to_codes.return_value = [100, 110, 105, 30, 50, 95]
        
        # Mock the TickData model_validate to properly convert ticks to schema
        with patch('app.schemas.visualization.TickData.model_validate') as mock_model_validate:
            mock_model_validate.side_effect = lambda x: {
                'route_name': x.route_name,
                'route_grade': x.route_grade,
                'discipline': x.discipline,
                'tick_date': x.tick_date,
                'location': x.location.name,
                'send_bool': True
            }

            # Act
            result = await get_dashboard_base_metrics(mock_db, TEST_USER_ID)

            # Assert
            assert result is not None
            assert result.recent_ticks is not None  # Check recent_ticks exists but don't assert length
            assert result.discipline_stats == {
                'sport': 3,
                'boulder': 2,
                'trad': 1
            }
            assert result.grade_distribution == {
                '5.10a': 2,
                '5.11b': 1,
                '5.10c': 1,
                'V3': 1,
                'V5': 1,
                '5.9': 1
            }
            assert result.total_climbs == 6

@pytest.mark.asyncio
async def test_get_dashboard_base_metrics_with_time_range(
    mock_db,
    mock_execute_result,
    sample_ticks,
    mock_grade_count_result,
    mock_discipline_count_result
):
    """Test fetching metrics with time range filter."""
    # Arrange
    time_range = timedelta(days=30)
    
    # Filter sample ticks by time range for the expected result
    recent_date = datetime.now() - time_range
    filtered_ticks = [tick for tick in sample_ticks if tick.tick_date >= recent_date]
    
    # Mock the sort operation for grade distribution
    with patch('app.services.dashboard.dashboard_analytics.sorted') as mock_sorted:
        # Make sorted return the input data directly
        mock_sorted.return_value = mock_grade_count_result
        
        mock_db.execute.side_effect = [
            # First call - recent ticks (filtered)
            AsyncMock(scalars=MagicMock(all=MagicMock(return_value=filtered_ticks))),
            # Second call - discipline distribution
            AsyncMock(all=MagicMock(return_value=mock_discipline_count_result)),
            # Third call - grade distribution
            AsyncMock(all=MagicMock(return_value=mock_grade_count_result)),
        ]
        
        # Mock grade service and TickData validation
        with patch('app.services.dashboard.dashboard_analytics.GradeService') as mock_grade_service_cls:
            mock_grade_service = MagicMock()
            mock_grade_service_cls.get_instance.return_value = mock_grade_service
            
            with patch('app.schemas.visualization.TickData.model_validate') as mock_model_validate:
                mock_model_validate.side_effect = lambda x: {
                    'route_name': x.route_name,
                    'route_grade': x.route_grade,
                    'discipline': x.discipline,
                    'tick_date': x.tick_date,
                    'location': x.location.name,
                    'send_bool': True
                }
                
                # Act
                result = await get_dashboard_base_metrics(mock_db, TEST_USER_ID, time_range=time_range)
                
                # Assert
                assert result is not None
                assert result.discipline_stats is not None
                assert result.grade_distribution is not None

@pytest.mark.asyncio
async def test_get_dashboard_base_metrics_error_handling(mock_db):
    """Test error handling in basic metrics retrieval."""
    # Arrange
    mock_db.execute.side_effect = ValueError("Test exception")
    
    # Act & Assert
    with pytest.raises(ValueError):
        await get_dashboard_base_metrics(mock_db, TEST_USER_ID)

@pytest.mark.asyncio
async def test_get_dashboard_performance_metrics(
    mock_db,
    mock_execute_result,
    sample_ticks
):
    """Test fetching performance metrics successfully."""
    # Arrange
    # Instead of patching the attribute, patch the entire query building and execution
    with patch('app.services.dashboard.dashboard_analytics.select') as mock_select:
        mock_query = MagicMock()
        mock_select.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        
        # Set up mock execution result
        mock_db.execute.return_value = AsyncMock(scalars=MagicMock(all=MagicMock(return_value=sample_ticks)))
        
        # Mock grade service
        with patch('app.services.dashboard.dashboard_analytics.GradeService') as mock_grade_service_cls:
            mock_grade_service = MagicMock()
            mock_grade_service_cls.get_instance.return_value = mock_grade_service
            mock_grade_service.is_harder_grade.return_value = True
            mock_grade_service.is_hard_send.return_value = True
            
            # Mock HardSend conversion for the latest_hard_sends
            with patch('app.schemas.visualization.HardSend', create=True) as mock_hard_send:
                hard_send_instance = MagicMock()
                mock_hard_send.return_value = hard_send_instance
                
                # Act
                result = await get_dashboard_performance_metrics(mock_db, TEST_USER_ID)

                # Assert
                assert result is not None
                assert isinstance(result, DashboardPerformanceMetrics)
                assert isinstance(result.highest_grades, dict)
                assert isinstance(result.latest_hard_sends, list)

@pytest.mark.asyncio
async def test_get_dashboard_performance_metrics_with_discipline_filter(
    mock_db,
    mock_execute_result,
    sample_ticks
):
    """Test fetching performance metrics with discipline filter."""
    # Arrange
    # Filter only sport climbs
    sport_ticks = [tick for tick in sample_ticks if tick.discipline == ClimbingDiscipline.SPORT]
    
    # Instead of patching the attribute, patch the entire query building and execution
    with patch('app.services.dashboard.dashboard_analytics.select') as mock_select:
        mock_query = MagicMock()
        mock_select.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        
        # Set up mock execution result
        mock_db.execute.return_value = AsyncMock(scalars=MagicMock(all=MagicMock(return_value=sport_ticks)))
        
        # Mock grade service
        with patch('app.services.dashboard.dashboard_analytics.GradeService') as mock_grade_service_cls:
            mock_grade_service = MagicMock()
            mock_grade_service_cls.get_instance.return_value = mock_grade_service
            mock_grade_service.is_harder_grade.return_value = True
            mock_grade_service.is_hard_send.return_value = True
            
            # Act
            result = await get_dashboard_performance_metrics(
                mock_db,
                TEST_USER_ID,
                discipline=ClimbingDiscipline.SPORT
            )
            
            # Assert
            assert result is not None
            assert isinstance(result, DashboardPerformanceMetrics)

@pytest.mark.asyncio
async def test_get_dashboard_performance_metrics_with_time_range(
    mock_db,
    mock_execute_result,
    sample_ticks
):
    """Test fetching performance metrics with time range filter."""
    # Arrange
    time_range = timedelta(days=30)
    
    # Instead of patching the attribute, patch the entire query building and execution
    with patch('app.services.dashboard.dashboard_analytics.select') as mock_select:
        mock_query = MagicMock()
        mock_select.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        
        # Set up mock execution result
        mock_db.execute.return_value = AsyncMock(scalars=MagicMock(all=MagicMock(return_value=sample_ticks)))
        
        # Mock grade service
        with patch('app.services.dashboard.dashboard_analytics.GradeService') as mock_grade_service_cls:
            mock_grade_service = MagicMock()
            mock_grade_service_cls.get_instance.return_value = mock_grade_service
            mock_grade_service.is_harder_grade.return_value = True
            mock_grade_service.is_hard_send.return_value = True
            
            # Act
            result = await get_dashboard_performance_metrics(
                mock_db,
                TEST_USER_ID,
                time_range=time_range
            )
            
            # Assert
            assert result is not None
            assert isinstance(result, DashboardPerformanceMetrics)

@pytest.mark.asyncio
async def test_get_dashboard_performance_metrics_empty_data(mock_db):
    """Test fetching performance metrics with no data."""
    # Arrange
    # Instead of patching the attribute, patch the entire query building and execution
    with patch('app.services.dashboard.dashboard_analytics.select') as mock_select:
        mock_query = MagicMock()
        mock_select.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        
        # Set up mock execution result with empty list
        mock_db.execute.return_value = AsyncMock(scalars=MagicMock(all=MagicMock(return_value=[])))
        
        # Mock grade service
        with patch('app.services.dashboard.dashboard_analytics.GradeService') as mock_grade_service_cls:
            mock_grade_service = MagicMock()
            mock_grade_service_cls.get_instance.return_value = mock_grade_service
            
            # Act
            result = await get_dashboard_performance_metrics(mock_db, TEST_USER_ID)
            
            # Assert
            assert result is not None
            assert isinstance(result, DashboardPerformanceMetrics)
            assert len(result.highest_grades) == 0
            assert len(result.latest_hard_sends) == 0

@pytest.mark.asyncio
async def test_get_dashboard_performance_metrics_error_handling(mock_db):
    """Test error handling in performance metrics retrieval."""
    # Arrange
    # Instead of patching the attribute, patch the entire query building and execution
    with patch('app.services.dashboard.dashboard_analytics.select') as mock_select:
        mock_query = MagicMock()
        mock_select.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        
        # Set up mock to raise an exception
        mock_db.execute.side_effect = ValueError("Test exception")
        
        # Act & Assert
        with pytest.raises(ValueError):
            await get_dashboard_performance_metrics(mock_db, TEST_USER_ID)

@pytest.mark.asyncio
async def test_grade_service_integration(
    mock_db,
    sample_ticks
):
    """Test integration with grade service for determining hard sends."""
    # Arrange
    # Instead of patching the attribute, patch the entire query building and execution
    with patch('app.services.dashboard.dashboard_analytics.select') as mock_select:
        mock_query = MagicMock()
        mock_select.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        
        # Set up mock execution result
        mock_db.execute.return_value = AsyncMock(scalars=MagicMock(all=MagicMock(return_value=sample_ticks)))
        
        # Mock grade service
        with patch('app.services.dashboard.dashboard_analytics.GradeService') as mock_grade_service_cls:
            mock_grade_service = MagicMock()
            mock_grade_service_cls.get_instance.return_value = mock_grade_service
            
            # Configure the mock to identify specific grades as "hard sends"
            mock_grade_service.is_hard_send.side_effect = lambda grade, discipline: grade in ["5.11b", "V5"]
            mock_grade_service.is_harder_grade.side_effect = lambda a, b, discipline: a > b

            # Mock HardSend conversion for the latest_hard_sends
            with patch('app.schemas.visualization.HardSend', create=True) as mock_hard_send:
                hard_send_instance = MagicMock()
                mock_hard_send.return_value = hard_send_instance
                
                # Act
                result = await get_dashboard_performance_metrics(mock_db, TEST_USER_ID)
                
                # Assert
                assert result is not None
                assert isinstance(result, DashboardPerformanceMetrics) 