"""Tests for the Mountain Project CSV client."""

import pytest
import pytest_asyncio
from typing import AsyncGenerator
import pandas as pd
from io import StringIO
import httpx
from unittest.mock import patch, Mock, PropertyMock
import os
import asyncio

from app.services.logbook.gateways.mp_csv_client import MountainProjectCSVClient
from app.core.exceptions import DataSourceError

SAMPLE_CSV = '''Date,Route,Rating,Notes,URL,Pitches,Location,Avg Stars,Your Stars,Style,Lead Style,Route Type,Your Rating,Length,Rating Code
3/23/2024,Balkan Dirt Diving,5.12a,"Awesome climb, not over after crux beginning.",https://www.mountainproject.com/route/105749977/balkan-dirt-diving,2,Colorado > Golden > Clear Creek Canyon > The Sports Wall,3.5,3,Lead,Fell/Hung,"Trad, Sport",,80,6600'''

TEST_PROFILE_URL = "https://www.mountainproject.com/user/200169262/isaac-rubey"

@pytest.fixture
def mock_response() -> Mock:
    """Create a mock HTTP response with sample CSV data."""
    response = Mock(spec=httpx.Response)
    response.text = SAMPLE_CSV
    response.status_code = 200
    return response

@pytest_asyncio.fixture
async def mp_client() -> AsyncGenerator[MountainProjectCSVClient, None]:
    """Create a Mountain Project CSV client instance."""
    client = MountainProjectCSVClient()
    async with client as mp_client:
        yield mp_client

@pytest.mark.asyncio
async def test_fetch_user_ticks_success(
    mp_client: MountainProjectCSVClient,
    mock_response: Mock
) -> None:
    """Test successful fetching and parsing of user ticks."""
    with patch.object(mp_client.client, 'get', return_value=mock_response):
        df = await mp_client.fetch_user_ticks(TEST_PROFILE_URL)
        
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert len(df) == 1
        assert 'tick_date' in df.columns
        assert 'route_name' in df.columns
        
        first_row = df.iloc[0]
        assert first_row['route_name'] == 'Balkan Dirt Diving'
        assert first_row['route_grade'] == '5.12a'

@pytest.mark.asyncio
async def test_fetch_user_ticks_http_error(
    mp_client: MountainProjectCSVClient
) -> None:
    """Test handling of HTTP errors."""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 404
    
    http_error = httpx.HTTPError("404 Not Found")
    # Create a mock response object and attach it to the HTTPError
    error_response = Mock(spec=httpx.Response)
    error_response.status_code = 404
    http_error.response = error_response
    
    mock_response.raise_for_status.side_effect = http_error
    
    with patch.object(mp_client.client, 'get', return_value=mock_response):
        with pytest.raises(DataSourceError) as exc_info:
            await mp_client.fetch_user_ticks(TEST_PROFILE_URL)
        assert "Failed to fetch Mountain Project data" in str(exc_info.value)

@pytest.mark.asyncio
async def test_fetch_user_ticks_empty_data(
    mp_client: MountainProjectCSVClient
) -> None:
    """Test handling of empty CSV data."""
    empty_response = Mock(spec=httpx.Response)
    empty_response.text = ""
    
    with patch.object(mp_client.client, 'get', return_value=empty_response):
        with pytest.raises(DataSourceError) as exc_info:
            await mp_client.fetch_user_ticks(TEST_PROFILE_URL)
        assert "Mountain Project returned empty data" in str(exc_info.value)

@pytest.mark.asyncio
async def test_column_renaming(
    mp_client: MountainProjectCSVClient,
    mock_response: Mock
) -> None:
    """Test that columns are correctly renamed."""
    with patch.object(mp_client.client, 'get', return_value=mock_response):
        df = await mp_client.fetch_user_ticks(TEST_PROFILE_URL)
        
        expected_columns = {
            'tick_date', 'route_name', 'route_grade', 'notes',
            'route_url', 'pitches', 'location', 'route_stars',
            'user_stars', 'style', 'lead_style', 'route_type'
        }
        
        assert all(col in df.columns for col in expected_columns)
        first_row = df.iloc[0]
        assert first_row['route_stars'] == 3.5
        assert first_row['user_stars'] == 3

@pytest.mark.asyncio
async def test_malformed_csv_missing_columns(
    mp_client: MountainProjectCSVClient
) -> None:
    """Test handling of CSV data with missing columns."""
    malformed_csv = "Date,Route\n3/23/2024,Some Route"  # Missing other columns
    malformed_response = Mock(spec=httpx.Response)
    malformed_response.text = malformed_csv
    malformed_response.status_code = 200

    with patch.object(mp_client.client, 'get', return_value=malformed_response):
        df = await mp_client.fetch_user_ticks(TEST_PROFILE_URL)
        # Assert that the expected columns are present, even if filled with NaN
        assert 'route_name' in df.columns
        assert 'tick_date' in df.columns
        assert 'route_grade' in df.columns #should exist, but be NaN
        assert pd.isna(df['route_grade'].iloc[0]) #check for NaN
        assert len(df) == 1

@pytest.mark.asyncio
async def test_malformed_csv_extra_columns(mp_client: MountainProjectCSVClient) -> None:
    """Test handling of CSV with extra/unexpected columns."""
    extra_column_csv = SAMPLE_CSV.replace(
        "Rating Code", "Rating Code,Extra Column"
    )  # Add an extra column
    extra_column_csv = extra_column_csv.replace("6600", "6600,ExtraValue")
    malformed_response = Mock(spec=httpx.Response)
    malformed_response.text = extra_column_csv
    malformed_response.status_code = 200

    with patch.object(mp_client.client, 'get', return_value=malformed_response):
        df = await mp_client.fetch_user_ticks(TEST_PROFILE_URL)
        assert "extra_column" not in df.columns  # Extra column should be ignored
        assert len(df) == 1

@pytest.mark.asyncio
async def test_bad_line_skipped(mp_client: MountainProjectCSVClient) -> None:
    """Test that on_bad_lines='skip' correctly skips malformed rows."""
    bad_line_csv = "Date,Route,Rating\n3/23/2024,Some Route,5.10a\n3/24/2024,Bad Route"  # Missing a field
    malformed_response = Mock(spec=httpx.Response)
    malformed_response.text = bad_line_csv
    malformed_response.status_code = 200

    with patch.object(mp_client.client, 'get', return_value=malformed_response):
        df = await mp_client.fetch_user_ticks(TEST_PROFILE_URL)
        assert len(df) == 1  # The bad line should be skipped
        assert df['route_name'].iloc[0] == 'Some Route'

@pytest.mark.asyncio
async def test_fetch_user_ticks_timeout(mp_client: MountainProjectCSVClient) -> None:
    """Test handling of request timeouts."""
    with patch.object(mp_client.client, 'get', side_effect=httpx.TimeoutException("Request timed out")):
        with pytest.raises(DataSourceError) as exc_info:
            await mp_client.fetch_user_ticks(TEST_PROFILE_URL)
        assert "Failed to fetch Mountain Project data" in str(exc_info.value)

@pytest.mark.asyncio
async def test_correct_url_construction(
    mp_client: MountainProjectCSVClient,
    mock_response: Mock
) -> None:
    """Test that the CSV export URL is correctly constructed."""
    with patch.object(mp_client.client, 'get', return_value=mock_response) as mock_get:
        await mp_client.fetch_user_ticks(TEST_PROFILE_URL)
        expected_url = f"{TEST_PROFILE_URL}/tick-export"
        mock_get.assert_called_once_with(expected_url)

@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("MP_TEST_LIVE") != "true", reason="Live MP test disabled")
async def test_fetch_user_ticks_live(mp_client: MountainProjectCSVClient):
    """Fetch ticks from a live, small MP account (rate-limited!)."""
    profile_url = "https://www.mountainproject.com/user/200169262/isaac-rubey/"  # Use a dedicated test account!
    # Implement rate limiting here!  e.g., sleep for 60 seconds, or use a more sophisticated approach.
    await asyncio.sleep(60)
    df = await mp_client.fetch_user_ticks(profile_url)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty  # Assuming the test account has at least one tick
    # Add more assertions based on the *known* data in your test account. 