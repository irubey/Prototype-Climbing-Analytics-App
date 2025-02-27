"""
Unit tests for Mountain Project CSV processor.

Tests the functionality for normalizing and processing Mountain Project CSV data.
"""

import pytest
import pandas as pd
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from app.core.exceptions import DataSourceError
from app.models.enums import LogbookType
from app.services.logbook.processing.mp_csv_processor import MountainProjectCSVProcessor

# Sample MP DataFrame for testing
@pytest.fixture
def sample_mp_df():
    """Create a sample Mountain Project DataFrame for tests."""
    return pd.DataFrame({
        'route': ['Test Route 1', 'Test Route 2', 'Test Route 3'],
        'rating': ['5.10a', '5.11b', '5.12c'],
        'date': ['2023-01-15', '2023-02-20', '2023-03-25'],
        'length': [100, 200, 150],
        'pitches': [1, 2, 1],
        'location': ['Test Crag > Test Area > Colorado', 'Another Crag > Utah', 'Some Crag'],
        'style': ['Lead', 'TR', 'Lead'],
        'lead_style': ['Onsight', '', 'Redpoint'],
        'route_type': ['Sport', 'Trad', 'Sport'],
        'notes': ['Fun route with great moves', 'Sustained climbing', 'Power crux at the top'],
        'url': [
            'https://www.mountainproject.com/route/12345', 
            'https://www.mountainproject.com/route/67890',
            'https://www.mountainproject.com/route/54321'
        ],
        'avg_stars': [3.5, 4.0, 3.8],
        'your_stars': [4, 3, 4]
    })

# Test user ID
TEST_USER_ID = uuid.uuid4()

def test_init():
    """Test MountainProjectCSVProcessor initialization."""
    # Act
    processor = MountainProjectCSVProcessor(TEST_USER_ID)
    
    # Assert
    assert processor.user_id == TEST_USER_ID

def test_process_raw_data_success(sample_mp_df):
    """Test successful processing of raw Mountain Project data."""
    # Arrange
    processor = MountainProjectCSVProcessor(TEST_USER_ID)
    
    # Act
    result = processor.process_raw_data(sample_mp_df)
    
    # Assert
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 3
    
    # Check required fields
    assert 'user_id' in result.columns
    assert 'logbook_type' in result.columns
    assert 'route_name' in result.columns
    assert 'route_grade' in result.columns
    assert 'tick_date' in result.columns
    
    # Check field values
    assert result['user_id'].iloc[0] == TEST_USER_ID
    assert result['logbook_type'].iloc[0] == LogbookType.MOUNTAIN_PROJECT
    assert result['route_name'].iloc[0] == 'Test Route 1'
    assert result['route_grade'].iloc[0] == '5.10a'
    assert isinstance(result['tick_date'].iloc[0], pd.Timestamp)
    
    # Check quality normalization (0-4 scale to 0-1)
    assert result['route_quality'].iloc[0] == 3.5 / 4.0
    assert result['user_quality'].iloc[0] == 4.0 / 4.0

def test_process_raw_data_empty_df():
    """Test handling of empty DataFrame."""
    # Arrange
    processor = MountainProjectCSVProcessor(TEST_USER_ID)
    empty_df = pd.DataFrame()
    
    # Act & Assert
    with pytest.raises(DataSourceError, match="No data found in Mountain Project CSV"):
        processor.process_raw_data(empty_df)

def test_process_raw_data_missing_columns():
    """Test handling of DataFrame with missing required columns."""
    # Arrange
    processor = MountainProjectCSVProcessor(TEST_USER_ID)
    
    # DataFrame missing 'route' and 'rating' columns
    incomplete_df = pd.DataFrame({
        'date': ['2023-01-15', '2023-02-20'],
        'location': ['Test Crag', 'Another Crag']
    })
    
    # Act & Assert
    with pytest.raises(DataSourceError, match="No data found in Mountain Project CSV"):
        processor.process_raw_data(incomplete_df)

def test_process_raw_data_location_processing(sample_mp_df):
    """Test processing of hierarchical location data."""
    # Arrange
    processor = MountainProjectCSVProcessor(TEST_USER_ID)
    
    # Act
    result = processor.process_raw_data(sample_mp_df)
    
    # Assert
    # First row has hierarchical location with > separator
    assert result['location_raw'].iloc[0] == 'Test Crag > Test Area > Colorado'
    assert result['location'].iloc[0] == 'Colorado, Test Crag'
    
    # Second row has a simpler hierarchy
    assert result['location_raw'].iloc[1] == 'Another Crag > Utah'
    assert result['location'].iloc[1] == 'Utah, Another Crag'
    
    # Third row has no hierarchy
    assert pd.isna(result['location_raw'].iloc[2])
    assert result['location'].iloc[2] == 'Some Crag'

def test_process_raw_data_numeric_conversion(sample_mp_df):
    """Test numeric data conversion and default values."""
    # Arrange
    processor = MountainProjectCSVProcessor(TEST_USER_ID)
    
    # Add row with non-numeric length and pitches
    sample_mp_df.loc[3] = {
        'route': 'Non-numeric Test',
        'rating': '5.9',
        'date': '2023-04-01',
        'length': 'unknown',  # Non-numeric length
        'pitches': 'many',    # Non-numeric pitches
        'location': 'Test Crag',
        'style': 'Lead',
        'lead_style': 'Onsight',
        'route_type': 'Sport',
        'notes': 'Test route',
        'url': 'https://www.mountainproject.com/route/99999',
        'avg_stars': 3.0,
        'your_stars': 3
    }
    
    # Act
    result = processor.process_raw_data(sample_mp_df)
    
    # Assert
    # Check default values for non-numeric entries
    assert result['length'].iloc[3] == 0  # Default for non-numeric length
    assert result['pitches'].iloc[3] == 1  # Default for non-numeric pitches

def test_process_raw_data_star_ratings(sample_mp_df):
    """Test processing of star ratings with various values."""
    # Arrange
    processor = MountainProjectCSVProcessor(TEST_USER_ID)
    
    # Add row with -1 star ratings (no data)
    sample_mp_df.loc[3] = {
        'route': 'No Rating Test',
        'rating': '5.9',
        'date': '2023-04-01',
        'length': 100,
        'pitches': 1,
        'location': 'Test Crag',
        'style': 'Lead',
        'lead_style': 'Onsight',
        'route_type': 'Sport',
        'notes': 'Test route',
        'url': 'https://www.mountainproject.com/route/99999',
        'avg_stars': -1,  # No rating
        'your_stars': -1  # No rating
    }
    
    # Act
    result = processor.process_raw_data(sample_mp_df)
    
    # Assert
    # Check that -1 values are converted to None (null)
    assert pd.isna(result['route_quality'].iloc[3])
    assert pd.isna(result['user_quality'].iloc[3])
    
    # Normal values should be normalized to 0-1 scale
    assert result['route_quality'].iloc[0] == 3.5 / 4.0
    assert result['user_quality'].iloc[0] == 4.0 / 4.0

def test_process_raw_data_exception_handling():
    """Test exception handling during data processing."""
    # Arrange
    processor = MountainProjectCSVProcessor(TEST_USER_ID)
    
    # Create a DataFrame that will cause an exception during processing
    bad_df = pd.DataFrame({
        'route': ['Test Route'],
        'rating': ['5.10a'],
        'date': ['not-a-date']  # This will cause pd.to_datetime to fail
    })
    
    # Act & Assert
    with pytest.raises(DataSourceError, match="Error normalizing Mountain Project data"):
        processor.process_raw_data(bad_df) 