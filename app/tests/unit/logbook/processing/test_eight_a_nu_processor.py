"""
Unit tests for 8a.nu data processor.

Tests the functionality for processing and normalizing 8a.nu ascent data.
"""

import pytest
import pytest_asyncio
import pandas as pd
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.core.exceptions import DataSourceError
from app.models.enums import LogbookType, ClimbingDiscipline, CruxAngle, CruxEnergyType
from app.services.logbook.processing.eight_a_nu_processor import EightANuProcessor
from app.services.utils.grade_service import GradeService

# Sample 8a.nu data for testing
@pytest.fixture
def sample_eight_a_data():
    """Create a sample 8a.nu DataFrame for tests."""
    return pd.DataFrame([
        {
            "id": "12345",
            "zlaggableName": "Test Route 1",
            "difficulty": "7a",
            "date": "2023-01-15",
            "cragName": "Test Crag",
            "areaName": "Test Area",
            "category": 0,  # Sport
            "traditional": False,
            "type": "rp",  # Redpoint
            "project": False,
            "rating": 4,
            "isOverhang": True,
            "isAthletic": True,
            "comment": "Great route!"
        },
        {
            "id": "67890",
            "zlaggableName": "Test Boulder",
            "difficulty": "7B",
            "date": "2023-02-20",
            "cragName": "Boulder Crag",
            "areaName": "Boulder Area",
            "category": 1,  # Boulder
            "traditional": False,
            "type": "fl",  # Flash
            "project": False,
            "rating": 5,
            "isSlab": True,
            "isTechnical": True,
            "comment": "Technical slab"
        },
        {
            "id": "24680",
            "zlaggableName": "Test Trad Route",
            "difficulty": "6c+",
            "date": "2023-03-10",
            "cragName": "Trad Crag",
            "areaName": "Trad Area",
            "category": 0,  # Sport, but marked as traditional
            "traditional": True,
            "type": "os",  # Onsight
            "project": False,
            "rating": 3,
            "isVertical": True,
            "isEndurance": True,
            "comment": "Classic trad line"
        },
        {
            "id": "13579",
            "zlaggableName": "Project Route",
            "difficulty": "8a",
            "date": "2023-04-05",
            "cragName": "Project Crag",
            "areaName": None,
            "category": 0,  # Sport
            "traditional": False,
            "type": "attempt",  # Attempt/Project
            "project": True,
            "rating": 4,
            "isRoof": True,
            "isCruxy": True,
            "comment": "Working on the crux"
        }
    ])

# Test user ID
TEST_USER_ID = uuid.uuid4()

@pytest_asyncio.fixture
async def mock_grade_service():
    """Create a mock GradeService."""
    with patch('app.services.utils.grade_service.GradeService.get_instance') as mock_get_instance:
        mock_service = AsyncMock(spec=GradeService)
        
        # Mock grade conversion methods
        async def mock_convert_grade(grade, from_system, to_system):
            # Simple mock conversion
            if from_system.value == "font" and to_system.value == "v_scale":
                # Font to V-scale conversion
                conversions = {
                    "7B": "V8",
                    "7A": "V6",
                    "6C+": "V5"
                }
                return conversions.get(grade, grade)
            elif from_system.value == "french" and to_system.value == "yds":
                # French to YDS conversion
                conversions = {
                    "7a": "5.11d",
                    "6c+": "5.11a",
                    "8a": "5.13b"
                }
                return conversions.get(grade, grade)
            return grade
        
        async def mock_convert_to_code(grade, system, discipline):
            # Simple mock code conversion
            if discipline == ClimbingDiscipline.BOULDER:
                codes = {"V8": 28, "V6": 26, "V5": 25}
                return codes.get(grade, 20)
            else:
                codes = {"5.11d": 24, "5.11a": 22, "5.13b": 30}
                return codes.get(grade, 20)
        
        # Set up the mock methods
        mock_service.convert_grade_system = AsyncMock(side_effect=mock_convert_grade)
        mock_service.convert_to_code = AsyncMock(side_effect=mock_convert_to_code)
        mock_service.get_grade_from_code = MagicMock(side_effect=lambda code: f"Grade-{code}")
        
        mock_get_instance.return_value = mock_service
        yield mock_service

@pytest_asyncio.fixture
async def processor(mock_grade_service):
    """Create an EightANuProcessor instance with mocked dependencies."""
    processor = EightANuProcessor(TEST_USER_ID)
    processor.grade_service = mock_grade_service
    return processor

@pytest.mark.asyncio
async def test_init():
    """Test EightANuProcessor initialization."""
    # Arrange & Act
    with patch('app.services.utils.grade_service.GradeService.get_instance') as mock_get_instance:
        mock_get_instance.return_value = MagicMock()
        processor = EightANuProcessor(TEST_USER_ID)
    
    # Assert
    assert processor.user_id == TEST_USER_ID
    assert processor.grade_service is not None

@pytest.mark.asyncio
async def test_process_raw_data_success(processor, sample_eight_a_data):
    """Test successful processing of raw 8a.nu data."""
    # Act
    result = await processor.process_raw_data(sample_eight_a_data)
    
    # Assert
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 4
    
    # Check required fields
    assert 'logbook_type' in result.columns
    assert 'route_name' in result.columns
    assert 'route_grade' in result.columns
    assert 'tick_date' in result.columns
    assert 'discipline' in result.columns
    assert 'send_bool' in result.columns
    
    # Check field values
    assert result['logbook_type'].iloc[0] == LogbookType.EIGHT_A_NU
    assert result['route_name'].iloc[0] == 'Test Route 1'
    assert result['route_grade'].iloc[0] == '5.11d'  # Converted from 7a
    assert isinstance(result['tick_date'].iloc[0], pd.Timestamp)
    
    # Check discipline classification
    assert result['discipline'].iloc[0] == ClimbingDiscipline.SPORT
    assert result['discipline'].iloc[1] == ClimbingDiscipline.BOULDER
    assert result['discipline'].iloc[2] == ClimbingDiscipline.TRAD
    
    # Check send classification
    assert result['send_bool'].iloc[0] == True  # Redpoint is a send
    assert result['send_bool'].iloc[1] == True  # Flash is a send
    assert result['send_bool'].iloc[2] == True  # Onsight is a send
    assert result['send_bool'].iloc[3] == False  # Project is not a send
    
    # Check location processing
    assert result['location'].iloc[0] == 'Test Crag, Test Area'
    assert result['location'].iloc[3] == 'Project Crag'  # No area name
    
    # Check quality normalization (0-5 scale to 0-1)
    assert result['route_quality'].iloc[0] == 4.0 / 5.0
    assert result['route_quality'].iloc[1] == 5.0 / 5.0
    
    # Check crux angle classification
    assert result['crux_angle'].iloc[0] == CruxAngle.OVERHANG
    assert result['crux_angle'].iloc[1] == CruxAngle.SLAB
    assert result['crux_angle'].iloc[2] == CruxAngle.VERTICAL
    assert result['crux_angle'].iloc[3] == CruxAngle.ROOF
    
    # Check crux energy classification
    assert result['crux_energy'].iloc[0] == CruxEnergyType.POWER
    assert result['crux_energy'].iloc[2] == CruxEnergyType.ENDURANCE
    assert result['crux_energy'].iloc[3] == CruxEnergyType.POWER

@pytest.mark.asyncio
async def test_process_raw_data_empty_df(processor):
    """Test handling of empty DataFrame."""
    # Arrange
    empty_df = pd.DataFrame()
    
    # Act & Assert
    with pytest.raises(DataSourceError, match="No data found in 8a.nu response"):
        await processor.process_raw_data(empty_df)

@pytest.mark.asyncio
async def test_process_raw_data_exception_handling(processor, sample_eight_a_data):
    """Test exception handling during data processing."""
    # Arrange
    # Make grade_service.convert_grade_system raise an exception
    processor.grade_service.convert_grade_system.side_effect = Exception("Conversion error")
    
    # Act & Assert
    with pytest.raises(DataSourceError, match="Error processing 8a.nu data"):
        await processor.process_raw_data(sample_eight_a_data)

@pytest.mark.asyncio
async def test_classify_disciplines(processor, sample_eight_a_data):
    """Test classification of climbing disciplines."""
    # Act
    result = processor._classify_disciplines(sample_eight_a_data)
    
    # Assert
    assert 'discipline' in result.columns
    assert 'route_type' in result.columns
    assert 'lead_style' in result.columns
    
    # Check discipline classification
    assert result['discipline'].iloc[0] == ClimbingDiscipline.SPORT
    assert result['discipline'].iloc[1] == ClimbingDiscipline.BOULDER
    assert result['discipline'].iloc[2] == ClimbingDiscipline.TRAD
    
    # Check route_type classification
    assert result['route_type'].iloc[0] == 'Sport'
    assert result['route_type'].iloc[1] == 'Boulder'
    assert result['route_type'].iloc[2] == 'Trad'
    
    # Check lead_style initial values
    assert result['lead_style'].iloc[0] == 'Sport'
    assert result['lead_style'].iloc[1] == 'Boulder'
    assert result['lead_style'].iloc[2] == 'Trad'

@pytest.mark.asyncio
async def test_classify_disciplines_exception(processor):
    """Test exception handling in discipline classification."""
    # Arrange
    # Create a DataFrame that will cause an exception
    bad_df = pd.DataFrame([{"category": "invalid"}])
    
    # Act & Assert
    with pytest.raises(DataSourceError, match="Error classifying disciplines"):
        processor._classify_disciplines(bad_df)

@pytest.mark.asyncio
async def test_classify_sends(processor, sample_eight_a_data):
    """Test classification of sends vs. attempts."""
    # Act
    result = processor._classify_sends(sample_eight_a_data)
    
    # Assert
    assert 'send_bool' in result.columns
    assert 'lead_style' in result.columns
    
    # Check send classification
    assert result['send_bool'].iloc[0] == True  # Redpoint is a send
    assert result['send_bool'].iloc[1] == True  # Flash is a send
    assert result['send_bool'].iloc[2] == True  # Onsight is a send
    assert result['send_bool'].iloc[3] == False  # Project is not a send
    
    # Check lead_style mapping
    assert result['lead_style'].iloc[0] == 'Redpoint'
    assert result['lead_style'].iloc[1] == 'Flash'
    assert result['lead_style'].iloc[2] == 'Onsight Trad'  # Traditional route
    assert result['lead_style'].iloc[3] == 'Project'

@pytest.mark.asyncio
async def test_classify_sends_exception(processor):
    """Test exception handling in send classification."""
    # Arrange
    # Create a DataFrame that will cause an exception
    bad_df = pd.DataFrame([{"type": "invalid"}])  # Missing 'project' column
    
    # Act & Assert
    with pytest.raises(DataSourceError, match="Error classifying sends"):
        processor._classify_sends(bad_df)

@pytest.mark.asyncio
async def test_process_route_characteristics(processor, sample_eight_a_data):
    """Test processing of route characteristics."""
    # Act
    result = await processor._process_route_characteristics(sample_eight_a_data)
    
    # Assert
    assert 'crux_angle' in result.columns
    assert 'crux_energy' in result.columns
    assert 'notes' in result.columns
    
    # Check crux angle classification
    assert result['crux_angle'].iloc[0] == CruxAngle.OVERHANG
    assert result['crux_angle'].iloc[1] == CruxAngle.SLAB
    assert result['crux_angle'].iloc[2] == CruxAngle.VERTICAL
    assert result['crux_angle'].iloc[3] == CruxAngle.ROOF
    
    # Check crux energy classification
    assert result['crux_energy'].iloc[0] == CruxEnergyType.POWER
    assert result['crux_energy'].iloc[2] == CruxEnergyType.ENDURANCE
    assert result['crux_energy'].iloc[3] == CruxEnergyType.POWER
    
    # Check notes generation
    assert "Great route!" in result['notes'].iloc[0]
    assert "#overhang" in result['notes'].iloc[0]
    assert "#athletic" in result['notes'].iloc[0]
    
    assert "Technical slab" in result['notes'].iloc[1]
    assert "#slab" in result['notes'].iloc[1]
    assert "#technical" in result['notes'].iloc[1]
    
    assert "Classic trad line" in result['notes'].iloc[2]
    assert "#trad" in result['notes'].iloc[2]
    assert "#vertical" in result['notes'].iloc[2]
    assert "#endurance" in result['notes'].iloc[2]
    
    assert "Working on the crux" in result['notes'].iloc[3]
    assert "#roof" in result['notes'].iloc[3]
    assert "#cruxy" in result['notes'].iloc[3]

@pytest.mark.asyncio
async def test_process_route_characteristics_exception(processor):
    """Test exception handling in route characteristics processing."""
    # Arrange
    # Create a DataFrame that will cause a KeyError since 'crux_angle' doesn't exist
    bad_df = pd.DataFrame([{"isOverhang": "invalid"}])  # Non-boolean value
    
    # Mock value_counts to raise an exception
    with patch.object(pd.Series, 'value_counts', side_effect=ValueError("Test error")):
        # Act & Assert
        with pytest.raises(DataSourceError, match="502: Error processing route characteristics"):
            await processor._process_route_characteristics(bad_df)

@pytest.mark.asyncio
async def test_generate_notes(processor):
    """Test generation of notes from route characteristics."""
    # Arrange
    test_cases = [
        # Case 1: Route with multiple characteristics
        {
            "comment": "Great route!",
            "recommended": True,
            "isOverhang": True,
            "isAthletic": True,
            "isCrimpy": True
        },
        # Case 2: Route with warning tags
        {
            "comment": "Be careful!",
            "looseRock": True,
            "highFirstBolt": True,
            "isDanger": True
        },
        # Case 3: Route with no comment
        {
            "recommended": True,
            "isVertical": True,
            "isTechnical": True
        },
        # Case 4: Route with no characteristics
        {
            "comment": "Just a route"
        },
        # Case 5: Route with pipe character in comment
        {
            "comment": "Great route | with pipe",
            "isEndurance": True
        }
    ]
    
    # Act
    results = [processor._generate_notes(pd.Series(case)) for case in test_cases]
    
    # Assert
    assert "#recommended" in results[0] and "#overhang" in results[0] and "#athletic" in results[0] and "#crimpy" in results[0]
    assert "#looserock" in results[1] and "#highfirstbolt" in results[1] and "#dangerous" in results[1]
    assert "#recommended" in results[2] and "#vertical" in results[2] and "#technical" in results[2]
    assert results[3] == "Just a route"
    assert "Great route  with pipe" in results[4] and "#endurance" in results[4]  # Pipe should be removed

@pytest.mark.asyncio
async def test_calculate_difficulty_category(processor):
    """Test calculation of difficulty categories based on grade indices."""
    # Arrange
    df = pd.DataFrame({
        'binned_code': [18, 22, 26, 30]
    })
    
    # Act
    result = processor._calculate_difficulty_category(df)
    
    # Assert
    assert len(result) == 4
    assert result.iloc[0] == 'Beginner'      # code <= 20
    assert result.iloc[1] == 'Intermediate'  # 20 < code <= 24
    assert result.iloc[2] == 'Advanced'      # 24 < code <= 28
    assert result.iloc[3] == 'Elite'         # code > 28 