"""
Unit tests for Mountain Project CSV client.

Tests the functionality for retrieving and parsing user tick data from Mountain Project.
"""

import pytest
import pandas as pd
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
from io import StringIO

from app.core.exceptions import DataSourceError
from app.services.logbook.gateways.mp_csv_client import MountainProjectCSVClient

# Sample CSV data for tests
SAMPLE_CSV = """Date,Route,Rating,Your Rating,Notes,URL,Pitches,Location,Style,Lead Style,Route Type,Length,Rating Code,Avg Stars,Your Stars
2023-01-15,Test Route,5.10a,,Fun climb with good moves,https://www.mountainproject.com/route/12345,1,"Test Crag > Test Area > Colorado",Lead,Onsight,Sport,100,1000,3.4,4
2023-02-20,Another Route,5.11c,,Pumpy moves,https://www.mountainproject.com/route/67890,2,"Another Crag > Another Area > Utah",Lead,Redpoint,Sport,150,1100,3.8,3
"""

@pytest.mark.asyncio
async def test_fetch_user_ticks_success():
    """Test successful fetching of user ticks."""
    # Arrange
    profile_url = "https://www.mountainproject.com/user/12345/test-user"
    csv_url = "https://www.mountainproject.com/user/12345/test-user/tick-export"
    
    # Create mock response with sample CSV
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_CSV
    mock_response.raise_for_status = MagicMock()
    
    # Create mock client
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    
    # Act
    with patch('httpx.AsyncClient', return_value=mock_client):
        async with MountainProjectCSVClient() as client:
            client.client = mock_client  # Replace the client with our mock
            result = await client.fetch_user_ticks(profile_url)
    
    # Assert
    mock_client.get.assert_called_once_with(csv_url)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert result['route_name'].tolist() == ['Test Route', 'Another Route']
    assert result['route_grade'].tolist() == ['5.10a', '5.11c']
    assert result['pitches'].tolist() == [1, 2]

@pytest.mark.asyncio
async def test_fetch_user_ticks_with_non_www_domain():
    """Test URL correction for non-www domain."""
    # Arrange
    profile_url = "https://mountainproject.com/user/12345/test-user"
    expected_csv_url = "https://www.mountainproject.com/user/12345/test-user/tick-export"
    
    # Create mock response with sample CSV
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_CSV
    mock_response.raise_for_status = MagicMock()
    
    # Create mock client
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    
    # Act
    with patch('httpx.AsyncClient', return_value=mock_client):
        async with MountainProjectCSVClient() as client:
            client.client = mock_client
            result = await client.fetch_user_ticks(profile_url)
    
    # Assert
    mock_client.get.assert_called_once_with(expected_csv_url)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2

@pytest.mark.asyncio
async def test_fetch_user_ticks_http_error():
    """Test handling of HTTP errors."""
    # Arrange
    profile_url = "https://www.mountainproject.com/user/12345/test-user"
    
    # Create a mock response for the HTTPStatusError
    mock_response = MagicMock()
    mock_response.status_code = 404
    
    # Create mock client that raises HTTPStatusError (more specific than HTTPError)
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPStatusError("HTTP Error", request=MagicMock(), response=mock_response)
    
    # Act & Assert
    with patch('httpx.AsyncClient', return_value=mock_client):
        async with MountainProjectCSVClient() as client:
            client.client = mock_client
            with pytest.raises(DataSourceError, match="Failed to fetch Mountain Project data"):
                await client.fetch_user_ticks(profile_url)

@pytest.mark.asyncio
async def test_fetch_user_ticks_timeout():
    """Test handling of timeout errors."""
    # Arrange
    profile_url = "https://www.mountainproject.com/user/12345/test-user"
    
    # Create mock client that raises TimeoutError
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.TimeoutException("Timeout")
    
    # Act & Assert
    with patch('httpx.AsyncClient', return_value=mock_client):
        async with MountainProjectCSVClient() as client:
            client.client = mock_client
            with pytest.raises(DataSourceError, match="Failed to fetch Mountain Project data"):
                await client.fetch_user_ticks(profile_url)

@pytest.mark.asyncio
async def test_fetch_user_ticks_empty_data():
    """Test handling of empty CSV data."""
    # Arrange
    profile_url = "https://www.mountainproject.com/user/12345/test-user"
    
    # Create mock response with empty CSV
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = ""
    mock_response.raise_for_status = MagicMock()
    
    # Create mock client
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    
    # Act & Assert
    with patch('httpx.AsyncClient', return_value=mock_client):
        async with MountainProjectCSVClient() as client:
            client.client = mock_client
            with pytest.raises(DataSourceError, match="Mountain Project returned empty data"):
                await client.fetch_user_ticks(profile_url)

@pytest.mark.asyncio
async def test_fetch_user_ticks_missing_required_columns():
    """Test handling of CSV with missing required columns."""
    # Arrange
    profile_url = "https://www.mountainproject.com/user/12345/test-user"
    
    # CSV missing "Route" column
    bad_csv = """Date,Rating,Notes,URL,Pitches,Location
2023-01-15,5.10a,Fun climb,https://www.mountainproject.com/route/12345,1,Test Crag
"""
    
    # Create mock response with bad CSV
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = bad_csv
    mock_response.raise_for_status = MagicMock()
    
    # Create mock client
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    
    # Act
    with patch('httpx.AsyncClient', return_value=mock_client):
        async with MountainProjectCSVClient() as client:
            client.client = mock_client
            # This should not raise but return an empty DataFrame since rows with missing required fields are dropped
            result = await client.fetch_user_ticks(profile_url)
    
    # Assert
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0  # All rows should be dropped due to missing required fields

@pytest.mark.asyncio
async def test_rename_columns():
    """Test column renaming functionality."""
    # Arrange
    test_df = pd.DataFrame({
        'Date': ['2023-01-15', '2023-02-20'],
        'Route': ['Test Route', 'Another Route'],
        'Rating': ['5.10a', '5.11c'],
        'Your Rating': ['5.10b', '5.11d'],
        'Your Stars': [4, 3],
        'Extra Column': ['extra1', 'extra2']  # Column not in mapping
    })
    
    # Act
    result = MountainProjectCSVClient._rename_columns(test_df)
    
    # Assert
    assert 'tick_date' in result.columns
    assert 'route_name' in result.columns
    assert 'route_grade' in result.columns
    assert 'user_grade' in result.columns
    assert 'user_stars' in result.columns
    assert 'Extra Column' in result.columns  # Unmapped column should remain unchanged 