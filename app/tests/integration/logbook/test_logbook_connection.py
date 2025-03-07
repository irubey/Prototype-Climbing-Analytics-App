"""
Integration tests for the logbook connection flow.

Tests the complete data flow from API request through orchestration 
to data processing and database storage.
"""

import pytest
import uuid
import pandas as pd
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch, call, Mock
from concurrent.futures import ThreadPoolExecutor

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LogbookType, ClimbingDiscipline
from app.schemas.logbook_connection import LogbookConnectPayload
from app.api.v1.endpoints.logbook import connect_logbook
from app.services.logbook.orchestrator import LogbookOrchestrator

# Sample CSV data for tests
SAMPLE_MP_CSV = """Date,Route,Rating,Your Rating,Notes,URL,Pitches,Location,Style,Lead Style,Route Type,Length,Rating Code,Avg Stars,Your Stars
2023-01-15,Test Route,5.10a,,Fun climb with good moves,https://www.mountainproject.com/route/12345,1,"Test Crag > Test Area > Colorado",Lead,Onsight,Sport,100,1000,3.4,4
2023-02-20,Another Route,5.11c,,Pumpy moves,https://www.mountainproject.com/route/67890,2,"Another Crag > Another Area > Utah",Lead,Redpoint,Sport,150,1100,3.8,3
"""

# Sample 8a.nu data
SAMPLE_8A_DATA = {
    "ascents": [
        {
            "id": 1,
            "name": "Test Route",
            "grade": "7a",
            "date": "2023-01-15",
            "cragName": "Test Crag",
            "countryName": "United States",
            "style": "flash",
            "comments": "Fun route",
            "platform": "eight_a",
            "discipline": "sport"
        },
        {
            "id": 2,
            "name": "Another Route",
            "grade": "7b",
            "date": "2023-02-20",
            "cragName": "Another Crag",
            "countryName": "Spain",
            "style": "redpoint",
            "comments": "Hard route",
            "platform": "eight_a",
            "discipline": "sport"
        }
    ],
    "totalItems": 2,
    "pageIndex": 0
}

# Test user ID
TEST_USER_ID = uuid.uuid4()

@pytest.fixture
def test_user():
    """Create a test user instance."""
    user = MagicMock()
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
@patch('app.services.logbook.gateways.mp_csv_client.MountainProjectCSVClient.__aenter__')
@patch('app.services.logbook.gateways.mp_csv_client.MountainProjectCSVClient.__aexit__')
async def test_mountain_project_integration(
    mock_aexit,
    mock_aenter,
    test_user,
    mock_db,
    mock_background_tasks
):
    """Test complete Mountain Project integration flow."""
    # Arrange - Mock external client
    mock_mp_client = AsyncMock()
    mock_mp_client.fetch_user_ticks.return_value = pd.read_csv(
        pd.io.common.StringIO(SAMPLE_MP_CSV),
        sep=',',
        quotechar='"'
    )
    mock_aenter.return_value = mock_mp_client
    
    # Set up mocks for nested services
    with patch('app.services.logbook.orchestrator.DatabaseService') as mock_db_service_cls, \
         patch('app.services.logbook.orchestrator.GradeService') as mock_grade_service_cls, \
         patch('app.services.logbook.orchestrator.ClimbClassifier') as mock_classifier_cls, \
         patch('app.services.logbook.orchestrator.PyramidBuilder') as mock_pyramid_builder_cls, \
         patch('app.services.logbook.processing.mp_csv_processor.MountainProjectCSVProcessor.process_raw_data') as mock_process:
        
        # Configure mocks
        mock_db_service = AsyncMock()
        mock_db_service_cls.return_value = mock_db_service
        
        mock_grade_service = MagicMock()
        mock_grade_service.convert_grades_to_codes.return_value = [10, 15]
        mock_grade_service.get_grade_from_code.side_effect = lambda code: f"5.{code}"
        mock_grade_service_cls.get_instance.return_value = mock_grade_service
        
        mock_classifier = MagicMock()
        mock_classifier.classify_discipline.return_value = pd.Series(["SPORT", "SPORT"])
        mock_classifier.classify_sends.return_value = pd.Series([True, True])
        mock_classifier.classify_length.return_value = pd.Series(["medium", "medium"])
        mock_classifier.classify_season.return_value = pd.Series(["winter", "winter"])
        mock_classifier_cls.return_value = mock_classifier
        
        mock_pyramid_builder = MagicMock()
        mock_pyramid_builder.build_performance_pyramid.return_value = [
            {"user_id": TEST_USER_ID, "tick_id": 1, "binned_code": 10, "send_date": date.today()}
        ]
        mock_pyramid_builder_cls.return_value = mock_pyramid_builder
        
        # Mock the processor to return properly formatted data
        mock_process.return_value = pd.DataFrame({
            'user_id': [TEST_USER_ID, TEST_USER_ID],
            'route_name': ['Test Route', 'Another Route'],
            'route_grade': ['5.10a', '5.11c'],
            'tick_date': [pd.Timestamp('2023-01-15'), pd.Timestamp('2023-02-20')],
            'binned_grade': [None, None],
            'binned_code': [None, None],
            'length': [100, 150],
            'pitches': [1, 2],
            'location': ['Colorado, Test Crag', 'Utah, Another Crag'],
            'location_raw': ['Test Crag > Test Area > Colorado', 'Another Crag > Another Area > Utah'],
            'lead_style': ['Onsight', 'Redpoint'],
            'style': ['Lead', 'Lead'],
            'route_type': ['Sport', 'Sport'],
            'notes': ['Fun climb with good moves', 'Pumpy moves'],
            'logbook_type': [LogbookType.MOUNTAIN_PROJECT, LogbookType.MOUNTAIN_PROJECT]
        })
        
        # Mock database operations
        mock_db_service.save_user_ticks.return_value = [MagicMock(id=1), MagicMock(id=2)]
        mock_db_service.save_performance_pyramid.return_value = [MagicMock(id=1)]
        mock_db_service.save_tags.return_value = []
        
        # Set up the request payload
        payload = LogbookConnectPayload(
            source="mountain_project",
            profile_url="https://www.mountainproject.com/user/12345/test-user"
        )
        
        # Act - First initiate the API flow
        result = await connect_logbook(
            payload=payload,
            background_tasks=mock_background_tasks,
            db=mock_db,
            current_user=test_user
        )
        
        # Now manually execute the background task
        # Get task function and args from background_tasks.add_task call
        task_func = mock_background_tasks.add_task.call_args[0][0]
        task_kwargs = {
            k: v for k, v in mock_background_tasks.add_task.call_args[1].items()
        }
        
        # Execute the task directly
        await task_func(**task_kwargs)
        
        # Assert - API response
        assert result == {"status": "Processing initiated successfully"}
        
        # Assert - Client and processor called correctly
        mock_mp_client.fetch_user_ticks.assert_called_once_with(payload.profile_url)
        mock_process.assert_called_once()
        
        # Assert - Classification methods called
        mock_classifier.classify_discipline.assert_called_once()
        mock_classifier.classify_sends.assert_called_once()
        mock_classifier.classify_length.assert_called_once()
        mock_classifier.classify_season.assert_called_once()
        
        # Assert - Database operations
        mock_db_service.save_user_ticks.assert_called_once()
        mock_db_service.save_performance_pyramid.assert_called_once()
        mock_db_service.update_sync_timestamp.assert_called_once_with(
            test_user.id, LogbookType.MOUNTAIN_PROJECT
        )

@pytest.mark.asyncio
@patch('app.services.logbook.gateways.eight_a_nu_scraper.EightANuClientCLI.__enter__')
@patch('app.services.logbook.gateways.eight_a_nu_scraper.EightANuClientCLI.__exit__')
async def test_eight_a_nu_integration(
    mock_exit,
    mock_enter,
    test_user,
    mock_db,
    mock_background_tasks
):
    """Test complete 8a.nu integration flow."""
    # Arrange - Mock external client
    mock_eight_a_client = Mock()
    mock_eight_a_client.authenticate = Mock()
    mock_eight_a_client.get_ascents.return_value = SAMPLE_8A_DATA
    mock_enter.return_value = mock_eight_a_client
    
    # Set up mocks for nested services
    with patch('app.services.logbook.orchestrator.DatabaseService') as mock_db_service_cls, \
         patch('app.services.logbook.orchestrator.GradeService') as mock_grade_service_cls, \
         patch('app.services.logbook.orchestrator.ClimbClassifier') as mock_classifier_cls, \
         patch('app.services.logbook.orchestrator.PyramidBuilder') as mock_pyramid_builder_cls, \
         patch('app.services.logbook.processing.eight_a_nu_processor.EightANuProcessor.process_raw_data') as mock_process:
        
        # Configure mocks
        mock_db_service = AsyncMock()
        mock_db_service_cls.return_value = mock_db_service
        
        mock_grade_service = MagicMock()
        mock_grade_service.convert_grades_to_codes.return_value = [20, 25]
        mock_grade_service.get_grade_from_code.side_effect = lambda code: f"7{'a' if code == 20 else 'b'}"
        mock_grade_service_cls.get_instance.return_value = mock_grade_service
        
        mock_classifier = MagicMock()
        mock_classifier.classify_discipline.return_value = pd.Series(["SPORT", "SPORT"])
        mock_classifier.classify_sends.return_value = pd.Series([True, True])
        mock_classifier.classify_length.return_value = pd.Series(["medium", "medium"])
        mock_classifier.classify_season.return_value = pd.Series(["winter", "winter"])
        mock_classifier_cls.return_value = mock_classifier
        
        mock_pyramid_builder = MagicMock()
        mock_pyramid_builder.build_performance_pyramid.return_value = [
            {"user_id": TEST_USER_ID, "tick_id": 1, "binned_code": 20, "send_date": date.today()}
        ]
        mock_pyramid_builder_cls.return_value = mock_pyramid_builder
        
        # Mock the processor to return properly formatted data
        mock_process.return_value = pd.DataFrame({
            'user_id': [TEST_USER_ID, TEST_USER_ID],
            'route_name': ['Test Route', 'Another Route'],
            'route_grade': ['7a', '7b'],
            'tick_date': [pd.Timestamp('2023-01-15'), pd.Timestamp('2023-02-20')],
            'binned_grade': [None, None],
            'binned_code': [None, None],
            'length': [100, 150],
            'pitches': [1, 1],
            'location': ['United States, Test Crag', 'Spain, Another Crag'],
            'location_raw': [None, None],
            'lead_style': ['flash', 'redpoint'],
            'style': ['sport', 'sport'],
            'notes': ['Fun route', 'Hard route'],
            'logbook_type': [LogbookType.EIGHT_A_NU, LogbookType.EIGHT_A_NU]
        })
        
        # Mock database operations
        mock_db_service.save_user_ticks.return_value = [MagicMock(id=1), MagicMock(id=2)]
        mock_db_service.save_performance_pyramid.return_value = [MagicMock(id=1)]
        mock_db_service.save_tags.return_value = []
        
        # Set up the request payload
        payload = LogbookConnectPayload(
            source="eight_a_nu",
            username="test_user",
            password="password123"
        )
        
        # Act - First initiate the API flow
        result = await connect_logbook(
            payload=payload,
            background_tasks=mock_background_tasks,
            db=mock_db,
            current_user=test_user
        )
        
        # Now manually execute the background task
        # Get task function and args from background_tasks.add_task call
        task_func = mock_background_tasks.add_task.call_args[0][0]
        task_kwargs = {
            k: v for k, v in mock_background_tasks.add_task.call_args[1].items()
        }
        
        # Execute the task directly
        await task_func(**task_kwargs)
        
        # Assert - API response
        assert result == {"status": "Processing initiated successfully"}
        
        # Assert - Client and processor called correctly
        mock_eight_a_client.authenticate.assert_called_once_with(payload.username, "[REDACTED]")
        mock_eight_a_client.get_ascents.assert_called_once()
        mock_process.assert_called_once()
        
        # Assert - Classification methods called
        mock_classifier.classify_discipline.assert_called_once()
        mock_classifier.classify_sends.assert_called_once()
        mock_classifier.classify_length.assert_called_once()
        mock_classifier.classify_season.assert_called_once()
        
        # Assert - Database operations
        mock_db_service.save_user_ticks.assert_called_once()
        mock_db_service.save_performance_pyramid.assert_called_once()
        mock_db_service.update_sync_timestamp.assert_called_once_with(
            test_user.id, LogbookType.EIGHT_A_NU
        ) 