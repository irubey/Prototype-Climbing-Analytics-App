"""
Unit tests for the LogbookOrchestrator class.

Tests the logbook data processing pipeline, including data fetching,
normalization, classification, entity building, and database operations.
"""

import pytest
import pandas as pd
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, call, Mock
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date

from app.core.exceptions import DataSourceError
from app.models.enums import LogbookType, ClimbingDiscipline
from app.services.logbook.orchestrator import LogbookOrchestrator
from app.services.logbook.database_service import DatabaseService

# Test data
TEST_USER_ID = uuid.uuid4()

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return AsyncMock()

@pytest.fixture
def mock_db_service():
    """Create a mock DatabaseService."""
    mock = AsyncMock(spec=DatabaseService)
    mock.save_user_ticks.return_value = [MagicMock(id=1), MagicMock(id=2)]
    mock.save_performance_pyramid.return_value = [MagicMock(id=1)]
    mock.save_tags.return_value = [MagicMock(name="test_tag")]
    return mock

@pytest.fixture
def mock_grade_service():
    """Create a mock GradeService."""
    mock = MagicMock()
    mock.convert_grades_to_codes.return_value = [10, 15, 20]
    mock.get_grade_from_code.side_effect = lambda code: f"Test Grade {code}"
    return mock

@pytest.fixture
def mock_classifier():
    """Create a mock ClimbClassifier."""
    mock = MagicMock()
    mock.classify_discipline.return_value = pd.Series(["SPORT", "BOULDER", "TRAD"])
    mock.classify_sends.return_value = pd.Series([True, False, True])
    mock.classify_length.return_value = pd.Series(["short", "medium", "long"])
    mock.classify_season.return_value = pd.Series(["winter", "summer", "fall"])
    mock.predict_crux_angle.side_effect = lambda x: "OVERHANG" if "overhang" in str(x).lower() else "SLAB"
    mock.predict_crux_energy.side_effect = lambda x: "POWER" if "power" in str(x).lower() else "ENDURANCE"
    return mock

@pytest.fixture
def mock_pyramid_builder():
    """Create a mock PyramidBuilder."""
    mock = MagicMock()
    mock.build_performance_pyramid = AsyncMock(return_value=[
        {"user_id": TEST_USER_ID, "tick_id": 1, "binned_code": 10, "send_date": date.today()}
    ])
    return mock

@pytest.fixture
def sample_mp_df():
    """Create a sample Mountain Project DataFrame."""
    return pd.DataFrame({
        'route_name': ['Test Route 1', 'Test Route 2', 'Test Route 3'],
        'route_grade': ['5.10a', '5.11b', '5.12c'],
        'tick_date': ['2023-01-01', '2023-02-15', '2023-03-20'],
        'length': [100, 200, 150],
        'pitches': [1, 2, 1],
        'location': ['Test Crag, CO', 'Another Crag, UT', 'Some Crag, NV'],
        'style': ['Lead', 'TR', 'Lead'],
        'lead_style': ['Onsight', '', 'Redpoint'],
        'route_type': ['Sport', 'Trad', 'Sport'],
        'notes': ['Fun route with overhang', 'Sustained climbing', 'Power crux at the top']
    })

@pytest.fixture
def sample_eight_a_df():
    """Create a sample 8a.nu DataFrame."""
    return pd.DataFrame({
        'name': ['Test Route 1', 'Test Route 2', 'Test Route 3'],
        'grade': ['7a', '7b', '8a'],
        'date': ['2023-01-01', '2023-02-15', '2023-03-20'],
        'cragName': ['Test Crag', 'Another Crag', 'Some Crag'],
        'countryName': ['United States', 'Spain', 'France'],
        'style': ['flash', 'redpoint', 'onsight'],
        'comments': ['Fun route', 'Sustained climbing', 'Hard crux'],
        'discipline': ['sport', 'boulder', 'sport']
    })

@pytest.fixture
def processed_df():
    """Create a sample processed DataFrame with all required columns."""
    df = pd.DataFrame({
        'route_name': ['Test Route 1', 'Test Route 2', 'Test Route 3'],
        'route_grade': ['5.10a', '5.11b', '5.12c'],
        'tick_date': [date(2023, 1, 1), date(2023, 2, 15), date(2023, 3, 20)],
        'length': [100, 200, 150],
        'pitches': [1, 2, 1],
        'location': ['Test Crag, CO', 'Another Crag, UT', 'Some Crag, NV'],
        'location_raw': [None, None, None],
        'lead_style': ['Onsight', '', 'Redpoint'],
        'style': ['Lead', 'TR', 'Lead'],
        'route_type': ['Sport', 'Trad', 'Sport'],
        'notes': ['Fun route with overhang', 'Sustained climbing', 'Power crux at the top'],
        'binned_code': [10, 15, 20],
        'binned_grade': ['Test Grade 10', 'Test Grade 15', 'Test Grade 20'],
        'discipline': [ClimbingDiscipline.SPORT, ClimbingDiscipline.BOULDER, ClimbingDiscipline.TRAD],
        'send_bool': [True, False, True],
        'length_category': ['short', 'medium', 'long'],
        'season_category': ['winter', 'summer', 'fall'],
        'cur_max_rp_sport': [10, 10, 10],
        'cur_max_rp_trad': [0, 15, 15],
        'cur_max_boulder': [0, 0, 0],
        'crux_angle': ['OVERHANG', 'SLAB', 'SLAB'],
        'crux_energy': ['POWER', 'ENDURANCE', 'POWER'],
        'difficulty_category': ['Project', 'Tier 2', 'Base Volume'],
        'route_quality': [0.8, 0.5, 0.9],
        'user_quality': [0.7, 0.6, 0.8],
        'logbook_type': [LogbookType.MOUNTAIN_PROJECT, LogbookType.MOUNTAIN_PROJECT, LogbookType.MOUNTAIN_PROJECT]
    })
    
    return df

@pytest.fixture
def mock_components(
    mock_db_session, 
    mock_db_service, 
    mock_grade_service, 
    mock_classifier,
    mock_pyramid_builder
):
    """Bundle all mock components together."""
    with patch('app.services.logbook.orchestrator.GradeService') as mock_gs_cls, \
         patch('app.services.logbook.orchestrator.ClimbClassifier') as mock_cc_cls, \
         patch('app.services.logbook.orchestrator.PyramidBuilder') as mock_pb_cls:
        
        # Configure class mocks to return instance mocks
        mock_gs_cls.get_instance.return_value = mock_grade_service
        mock_cc_cls.return_value = mock_classifier
        mock_pb_cls.return_value = mock_pyramid_builder
        
        yield {
            'db_session': mock_db_session,
            'db_service': mock_db_service,
            'grade_service': mock_grade_service,
            'classifier': mock_classifier,
            'pyramid_builder': mock_pyramid_builder
        }

@pytest.fixture
def orchestrator(mock_components):
    """Create a LogbookOrchestrator instance with mocked components."""
    return LogbookOrchestrator(
        db=mock_components['db_session'],
        db_service=mock_components['db_service']
    )

@pytest.mark.asyncio
async def test_initialization(mock_components):
    """Test LogbookOrchestrator initialization."""
    # Act
    orchestrator = LogbookOrchestrator(
        db=mock_components['db_session'],
        db_service=mock_components['db_service']
    )
    
    # Assert
    assert orchestrator.db == mock_components['db_session']
    assert orchestrator.db_service == mock_components['db_service']
    assert orchestrator.grade_service == mock_components['grade_service']
    assert orchestrator.classifier == mock_components['classifier']
    assert orchestrator.pyramid_builder == mock_components['pyramid_builder']

@pytest.mark.asyncio
async def test_fetch_raw_data_mountain_project(orchestrator):
    """Test fetching raw data from Mountain Project."""
    # Arrange
    profile_url = "https://www.mountainproject.com/user/12345/test-user"
    mock_mp_client = AsyncMock()
    mock_mp_client.fetch_user_ticks = AsyncMock(return_value=pd.DataFrame({"test": [1, 2, 3]}))
    mock_mp_client.__aenter__ = AsyncMock(return_value=mock_mp_client)
    mock_mp_client.__aexit__ = AsyncMock()
    
    # Act
    with patch('app.services.logbook.orchestrator.MountainProjectCSVClient', return_value=mock_mp_client):
        result = await orchestrator._fetch_raw_data(
            LogbookType.MOUNTAIN_PROJECT,
            profile_url=profile_url
        )
    
    # Assert
    mock_mp_client.fetch_user_ticks.assert_called_once_with(profile_url)
    assert isinstance(result, pd.DataFrame)
    assert result.equals(pd.DataFrame({"test": [1, 2, 3]}))

@pytest.mark.asyncio
async def test_fetch_raw_data_eight_a_nu(orchestrator):
    """Test fetching raw data from 8a.nu."""
    # Arrange
    username = "test_user"
    password = "password123"
    
    # Create sample ascents data that will be returned
    ascents_data = {"ascents": [{"id": 1}, {"id": 2}]}
    
    mock_eight_a_client = Mock()
    mock_eight_a_client.authenticate = Mock()
    mock_eight_a_client.get_ascents = Mock(return_value=ascents_data)
    mock_eight_a_client.__enter__ = Mock(return_value=mock_eight_a_client)
    mock_eight_a_client.__exit__ = Mock()
    
    # Act
    with patch('app.services.logbook.orchestrator.EightANuClientCLI', return_value=mock_eight_a_client):
        result = await orchestrator.process_eight_a_nu_ticks(
            user_id=uuid.UUID('00000000-0000-0000-0000-000000000001'),
            username=username,
            password=password
        )
    
    # Assert
    mock_eight_a_client.authenticate.assert_called_once_with(username, password)
    mock_eight_a_client.get_ascents.assert_called_once()
    assert len(result[0]) > 0  # Check that we have ticks
    assert len(result[1]) > 0  # Check that we have pyramid entries

@pytest.mark.asyncio
async def test_fetch_raw_data_unsupported_type(orchestrator):
    """Test fetching raw data with unsupported logbook type."""
    # Act & Assert
    with pytest.raises(ValueError, match="Unsupported logbook type"):
        await orchestrator._fetch_raw_data("UNSUPPORTED_TYPE")

@pytest.mark.asyncio
async def test_normalize_data_mountain_project(orchestrator, sample_mp_df):
    """Test normalizing Mountain Project data."""
    # Arrange
    mock_processor = MagicMock()
    mock_processor.process_raw_data.return_value = sample_mp_df
    
    # Act
    with patch('app.services.logbook.orchestrator.MountainProjectCSVProcessor', return_value=mock_processor):
        result = await orchestrator._normalize_data(
            sample_mp_df,
            LogbookType.MOUNTAIN_PROJECT,
            TEST_USER_ID
        )
    
    # Assert
    mock_processor.process_raw_data.assert_called_once_with(sample_mp_df)
    assert result.equals(sample_mp_df)

@pytest.mark.asyncio
async def test_normalize_data_eight_a_nu(orchestrator, sample_eight_a_df):
    """Test normalizing 8a.nu data."""
    # Arrange
    mock_processor = MagicMock()
    mock_processor.process_raw_data = AsyncMock(return_value=sample_eight_a_df)
    
    # Act
    with patch('app.services.logbook.orchestrator.EightANuProcessor', return_value=mock_processor):
        result = await orchestrator._normalize_data(
            sample_eight_a_df,
            LogbookType.EIGHT_A_NU,
            TEST_USER_ID
        )
    
    # Assert
    mock_processor.process_raw_data.assert_called_once_with(sample_eight_a_df)
    assert result.equals(sample_eight_a_df)

@pytest.mark.asyncio
async def test_normalize_data_unsupported_type(orchestrator, sample_mp_df):
    """Test normalizing data with unsupported logbook type."""
    # Act & Assert
    with pytest.raises(ValueError, match="Unsupported logbook type"):
        await orchestrator._normalize_data(
            sample_mp_df,
            "UNSUPPORTED_TYPE",
            TEST_USER_ID
        )

@pytest.mark.asyncio
async def test_process_data(orchestrator, sample_mp_df, mock_components):
    """Test processing data with classifications and grades."""
    # Arrange
    # Mock the dependent methods
    orchestrator._process_grades = AsyncMock(return_value=sample_mp_df)
    orchestrator._calculate_max_grades = AsyncMock(return_value=sample_mp_df)
    orchestrator._calculate_difficulty_category = AsyncMock(return_value=pd.Series(["Project", "Tier 2", "Base Volume"]))
    
    # Mock the Series that would result from the apply operations
    crux_angle_series = pd.Series(["OVERHANG", "SLAB", "SLAB"])
    crux_energy_series = pd.Series(["POWER", "ENDURANCE", "POWER"])
    
    # Mock the apply operations directly
    with patch('pandas.Series.apply', side_effect=lambda func, *args, **kwargs: 
               crux_angle_series if func is mock_components['classifier'].predict_crux_angle 
               else crux_energy_series if func is mock_components['classifier'].predict_crux_energy
               else None):
        # Act
        result = await orchestrator._process_data(sample_mp_df)
    
    # Assert
    orchestrator._process_grades.assert_called_once_with(sample_mp_df)
    mock_components['classifier'].classify_discipline.assert_called_once()
    mock_components['classifier'].classify_sends.assert_called_once()
    mock_components['classifier'].classify_length.assert_called_once()
    mock_components['classifier'].classify_season.assert_called_once()
    orchestrator._calculate_max_grades.assert_called_once()
    orchestrator._calculate_difficulty_category.assert_called_once()
    assert isinstance(result, pd.DataFrame)

@pytest.mark.asyncio
async def test_process_data_error_handling(orchestrator, sample_mp_df):
    """Test error handling in process_data method."""
    # Arrange
    orchestrator._process_grades = AsyncMock(side_effect=Exception("Test exception"))
    
    # Act & Assert
    with pytest.raises(DataSourceError, match="Error processing data"):
        await orchestrator._process_data(sample_mp_df)

@pytest.mark.asyncio
async def test_build_entities(orchestrator, processed_df, mock_components):
    """Test building database entities from processed data."""
    # Act
    ticks_data, pyramid_data, tag_data = await orchestrator._build_entities(processed_df, TEST_USER_ID)
    
    # Assert
    mock_components['pyramid_builder'].build_performance_pyramid.assert_called_once_with(
        processed_df, TEST_USER_ID
    )
    
    # Check that ticks data contains all expected records
    assert len(ticks_data) == 3
    for tick in ticks_data:
        assert 'route_name' in tick
        assert 'route_grade' in tick
        assert 'tick_date' in tick
        assert 'discipline' in tick
    
    # Check pyramid data
    assert pyramid_data == [
        {"user_id": TEST_USER_ID, "tick_id": 1, "binned_code": 10, "send_date": date.today()}
    ]
    
    # Check tag data (empty in this case)
    assert tag_data == []

@pytest.mark.asyncio
async def test_commit_to_database(orchestrator, mock_components):
    """Test committing entities to database."""
    # Arrange
    ticks_data = [
        {"route_name": "Test Route 1", "route_grade": "5.10a"},
        {"route_name": "Test Route 2", "route_grade": "5.11b"}
    ]
    pyramid_data = [{"user_id": TEST_USER_ID, "tick_id": 1, "binned_code": 10}]
    tag_data = ["Test Tag 1", "Test Tag 2"]
    
    # Act
    await orchestrator._commit_to_database(
        ticks_data,
        pyramid_data,
        tag_data,
        TEST_USER_ID,
        LogbookType.MOUNTAIN_PROJECT
    )
    
    # Assert
    mock_components['db_service'].save_user_ticks.assert_called_once_with(ticks_data, TEST_USER_ID)
    mock_components['db_service'].save_performance_pyramid.assert_called_once_with(pyramid_data, TEST_USER_ID)
    mock_components['db_service'].save_tags.assert_called_once_with(tag_data, [1, 2])
    mock_components['db_service'].update_sync_timestamp.assert_called_once_with(
        TEST_USER_ID, LogbookType.MOUNTAIN_PROJECT
    )

@pytest.mark.asyncio
async def test_process_logbook_data_mountain_project(orchestrator, sample_mp_df, processed_df):
    """Test complete processing of Mountain Project data."""
    # Arrange
    profile_url = "https://www.mountainproject.com/user/12345/test-user"
    
    # Mock all the methods called by process_logbook_data
    orchestrator._fetch_raw_data = AsyncMock(return_value=sample_mp_df)
    orchestrator._normalize_data = AsyncMock(return_value=sample_mp_df)
    orchestrator._process_data = AsyncMock(return_value=processed_df)
    orchestrator._build_entities = AsyncMock(return_value=(
        [{"id": 1}, {"id": 2}],  # ticks
        [{"id": 1}],  # pyramids
        ["Tag1", "Tag2"]  # tags
    ))
    orchestrator._commit_to_database = AsyncMock()
    
    # Act
    ticks, pyramids, tags = await orchestrator.process_logbook_data(
        user_id=TEST_USER_ID,
        logbook_type=LogbookType.MOUNTAIN_PROJECT,
        profile_url=profile_url
    )
    
    # Assert
    orchestrator._fetch_raw_data.assert_called_once_with(
        LogbookType.MOUNTAIN_PROJECT, profile_url=profile_url
    )
    orchestrator._normalize_data.assert_called_once_with(
        sample_mp_df, LogbookType.MOUNTAIN_PROJECT, TEST_USER_ID
    )
    orchestrator._process_data.assert_called_once_with(sample_mp_df)
    orchestrator._build_entities.assert_called_once_with(processed_df, TEST_USER_ID)
    orchestrator._commit_to_database.assert_called_once()
    
    assert ticks == [{"id": 1}, {"id": 2}]
    assert pyramids == [{"id": 1}]
    assert tags == ["Tag1", "Tag2"]

@pytest.mark.asyncio
async def test_process_logbook_data_eight_a_nu(orchestrator, sample_eight_a_df, processed_df):
    """Test complete processing of 8a.nu data."""
    # Arrange
    username = "test_user"
    password = "password123"
    
    # Mock all the methods called by process_logbook_data
    orchestrator._fetch_raw_data = AsyncMock(return_value=sample_eight_a_df)
    orchestrator._normalize_data = AsyncMock(return_value=sample_eight_a_df)
    orchestrator._process_data = AsyncMock(return_value=processed_df)
    orchestrator._build_entities = AsyncMock(return_value=(
        [{"id": 1}, {"id": 2}],  # ticks
        [{"id": 1}],  # pyramids
        ["Tag1", "Tag2"]  # tags
    ))
    orchestrator._commit_to_database = AsyncMock()
    
    # Act
    ticks, pyramids, tags = await orchestrator.process_logbook_data(
        user_id=TEST_USER_ID,
        logbook_type=LogbookType.EIGHT_A_NU,
        username=username,
        password=password
    )
    
    # Assert
    orchestrator._fetch_raw_data.assert_called_once_with(
        LogbookType.EIGHT_A_NU, username=username, password=password
    )
    orchestrator._normalize_data.assert_called_once_with(
        sample_eight_a_df, LogbookType.EIGHT_A_NU, TEST_USER_ID
    )
    orchestrator._process_data.assert_called_once_with(sample_eight_a_df)
    orchestrator._build_entities.assert_called_once_with(processed_df, TEST_USER_ID)
    orchestrator._commit_to_database.assert_called_once()
    
    assert ticks == [{"id": 1}, {"id": 2}]
    assert pyramids == [{"id": 1}]
    assert tags == ["Tag1", "Tag2"]

@pytest.mark.asyncio
async def test_process_logbook_data_error_handling(orchestrator):
    """Test error handling in process_logbook_data method."""
    # Arrange
    orchestrator._fetch_raw_data = AsyncMock(side_effect=Exception("Test exception"))
    
    # Act & Assert
    with pytest.raises(DataSourceError, match="Error processing"):
        await orchestrator.process_logbook_data(
            user_id=TEST_USER_ID,
            logbook_type=LogbookType.MOUNTAIN_PROJECT,
            profile_url="https://www.mountainproject.com/user/12345/test-user"
        ) 