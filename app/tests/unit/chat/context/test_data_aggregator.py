"""
Tests for DataAggregator functionality.

This module tests the DataAggregator class responsible for aggregating climber data
from various sources for context generation.
"""

import pytest
import pytest_asyncio
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import text
from uuid import UUID
from datetime import datetime, timedelta
from io import StringIO

from app.services.chat.context.data_aggregator import DataAggregator
from app.core.exceptions import DatabaseError


@pytest_asyncio.fixture
async def mock_db_session():
    """Create a fully mocked AsyncSession for testing without database connection."""
    mock_session = AsyncMock()
    
    # Add context manager methods to the mock
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    # Add basic methods that are commonly used
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()
    
    return mock_session


@pytest_asyncio.fixture
async def data_aggregator(mock_db_session):
    """Create a DataAggregator instance with a mocked DB session fixture."""
    return DataAggregator(mock_db_session)


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return 12345


@pytest.fixture
def sample_climber_data():
    """Sample climber context data for testing."""
    return {
        "user_id": "12345",
        "name": "Test Climber",
        "age": 30,
        "experience_years": 5,
        "height_cm": 175,
        "weight_kg": 70,
        "preferred_grade_system": "V-scale",
        "preferred_disciplines": ["bouldering", "sport"],
        "current_grade_boulder": "V5",
        "current_grade_sport": "5.11c",
        "goal_grade_boulder": "V7",
        "goal_grade_sport": "5.12b",
        "goal_deadline": (datetime.now() + timedelta(days=180)).isoformat(),
        "training_frequency_per_week": 3,
        "session_duration_minutes": 120,
        "injury_status": "none",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }


@pytest.fixture
def sample_ticks():
    """Sample climbing tick data for testing."""
    return [
        {
            "id": 1,
            "user_id": "12345",
            "date": (datetime.now() - timedelta(days=5)).isoformat(),
            "route": "Test Route 1",
            "grade": "V4",
            "send_status": "sent",
            "attempts": 3,
            "notes": "Felt strong"
        },
        {
            "id": 2,
            "user_id": "12345",
            "date": (datetime.now() - timedelta(days=10)).isoformat(),
            "route": "Test Route 2",
            "grade": "V5",
            "send_status": "sent",
            "attempts": 5,
            "notes": "Struggled with crux"
        },
        {
            "id": 3,
            "user_id": "12345",
            "date": (datetime.now() - timedelta(days=15)).isoformat(),
            "route": "Test Route 3",
            "grade": "5.11a",
            "send_status": "attempted",
            "attempts": 2,
            "notes": "Pumped out"
        }
    ]


@pytest.fixture
def sample_upload_csv():
    """Sample CSV upload content for testing."""
    return """date,route,grade,send_status
2023-10-20,Test Route,V5,sent
2023-10-19,Another Route,V4,attempted"""


@pytest.mark.asyncio
async def test_fetch_climber_context(data_aggregator, mock_db_session, sample_climber_data, sample_user_id):
    """Test fetching climber context from database."""
    # Mock the database query response
    mock_result = MagicMock()
    mock_result.first.return_value = MagicMock(_mapping=sample_climber_data)
    
    mock_db_session.execute.return_value = mock_result
    
    result = await data_aggregator.fetch_climber_context(sample_user_id)
        
    # Verify result matches sample data
    assert result == sample_climber_data


@pytest.mark.asyncio
async def test_fetch_climber_context_not_found(data_aggregator, mock_db_session):
    """Test fetching non-existent climber context."""
    # Mock the database query response for missing data
    mock_result = MagicMock()
    mock_result.first.return_value = None
    
    mock_db_session.execute.return_value = mock_result
    
    # Patch the UUID constructor to avoid validation errors
    with patch('app.services.chat.context.data_aggregator.UUID') as mock_uuid:
        # Configure mock to return a valid UUID object
        mock_uuid_instance = MagicMock()
        mock_uuid.return_value = mock_uuid_instance
        
        result = await data_aggregator.fetch_climber_context("nonexistent_user")
        
        # Verify mock_uuid was called with the user_id
        mock_uuid.assert_called_once_with("nonexistent_user")
        
    # Should return empty dict when not found
    assert result == {}


@pytest.mark.asyncio
async def test_fetch_climber_context_error(data_aggregator, mock_db_session):
    """Test database error handling when fetching climber context."""
    # Mock a database error
    mock_db_session.execute.side_effect = ValueError("Test error")
    
    with pytest.raises(DatabaseError):
        await data_aggregator.fetch_climber_context("invalid_user_id")


@pytest.mark.asyncio
async def test_fetch_recent_ticks(data_aggregator, mock_db_session, sample_ticks, sample_user_id):
    """Test fetching recent ticks from database."""
    # Mock the database query response
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [MagicMock(_mapping=tick) for tick in sample_ticks]
    
    mock_db_session.execute.return_value = mock_result
    
    result = await data_aggregator.fetch_recent_ticks(sample_user_id)
        
    # Verify result length matches sample data
    assert len(result) == len(sample_ticks)
    # Verify content of first tick
    assert result[0]["route"] == sample_ticks[0]["route"]
    assert result[0]["grade"] == sample_ticks[0]["grade"]


@pytest.mark.asyncio
async def test_fetch_recent_ticks_custom_timeframe(data_aggregator, mock_db_session, sample_ticks, sample_user_id):
    """Test fetching ticks with custom timeframe."""
    # Mock the database query response
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [MagicMock(_mapping=tick) for tick in sample_ticks]
    
    mock_db_session.execute.return_value = mock_result
    
    # Test with custom timeframe of 60 days
    result = await data_aggregator.fetch_recent_ticks(sample_user_id, days=60)
        
    # Verify query used the custom timeframe (hard to check in mocked environment)
    assert len(result) == len(sample_ticks)


@pytest.mark.asyncio
async def test_fetch_performance_metrics(data_aggregator, mock_db_session, sample_user_id):
    """Test fetching performance metrics from database."""
    # Sample performance metrics
    sample_metrics = {
        "user_id": str(sample_user_id),
        "boulder_pyramid": {
            "V1": 20,
            "V2": 15,
            "V3": 10,
            "V4": 5,
            "V5": 2
        },
        "sport_pyramid": {
            "5.9": 15,
            "5.10a": 12,
            "5.10b": 8,
            "5.10c": 5,
            "5.11a": 2
        },
        "updated_at": datetime.now().isoformat()
    }
    
    # Mock the database query response
    mock_result = MagicMock()
    mock_result.first.return_value = MagicMock(_mapping=sample_metrics)
    
    mock_db_session.execute.return_value = mock_result
    
    result = await data_aggregator.fetch_performance_metrics(sample_user_id)
        
    # Verify result matches sample data
    assert result["boulder_pyramid"] == sample_metrics["boulder_pyramid"]
    assert result["sport_pyramid"] == sample_metrics["sport_pyramid"]


@pytest.mark.asyncio
async def test_fetch_chat_history(data_aggregator, mock_db_session, sample_user_id):
    """Test fetching chat history from database."""
    # Sample chat history
    sample_history = [
        {
            "id": 1,
            "user_id": str(sample_user_id),
            "conversation_id": 101,
            "message": "What should I train for my V5 project?",
            "response": "For your V5 project, focus on finger strength and core training...",
            "created_at": datetime.now().isoformat()
        },
        {
            "id": 2,
            "user_id": str(sample_user_id),
            "conversation_id": 101,
            "message": "How often should I train finger strength?",
            "response": "For finger training, 2-3 sessions per week is recommended...",
            "created_at": datetime.now().isoformat()
        }
    ]
    
    # Mock the database query response
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [MagicMock(_mapping=entry) for entry in sample_history]
    
    mock_db_session.execute.return_value = mock_result
    
    result = await data_aggregator.fetch_chat_history(sample_user_id)
        
    # Verify result length matches sample data
    assert len(result) == len(sample_history)
    # Verify content of first chat entry
    assert result[0]["message"] == sample_history[0]["message"]
    assert result[0]["response"] == sample_history[0]["response"]


@pytest.mark.asyncio
async def test_fetch_chat_history_with_conversation_id(data_aggregator, mock_db_session, sample_user_id):
    """Test fetching chat history for a specific conversation."""
    # Sample chat history
    sample_history = [
        {
            "id": 1,
            "user_id": str(sample_user_id),
            "conversation_id": 101,
            "message": "What should I train for my V5 project?",
            "response": "For your V5 project, focus on finger strength and core training...",
            "created_at": datetime.now().isoformat()
        }
    ]
    
    # Mock the database query response
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [MagicMock(_mapping=entry) for entry in sample_history]
    
    mock_db_session.execute.return_value = mock_result
    
    result = await data_aggregator.fetch_chat_history(sample_user_id, conversation_id=101)
        
    # Verify result contains the entry for the specified conversation
    assert len(result) == 1
    assert result[0]["conversation_id"] == 101


def test_parse_upload_csv(data_aggregator, sample_upload_csv):
    """Test parsing CSV uploads."""
    result = data_aggregator.parse_upload(sample_upload_csv, "csv")
    
    # Verify result has the expected structure
    assert len(result) == 2
    assert result[0]["route"] == "Test Route"
    assert result[0]["grade"] == "V5"
    assert result[0]["send_status"] == "sent"


def test_parse_upload_json(data_aggregator):
    """Test parsing JSON uploads."""
    sample_json = """[
        {"date": "2023-10-20", "route": "Test Route", "grade": "V5", "send_status": "sent"},
        {"date": "2023-10-19", "route": "Another Route", "grade": "V4", "send_status": "attempted"}
    ]"""
    
    result = data_aggregator.parse_upload(sample_json, "json")
    
    # Verify result has the expected structure
    assert len(result) == 2
    assert result[0]["route"] == "Test Route"
    assert result[0]["grade"] == "V5"


def test_parse_upload_invalid_format(data_aggregator):
    """Test error handling for invalid file formats."""
    with pytest.raises(ValueError):
        data_aggregator.parse_upload("test data", "invalid_format")


def test_deduplicate_entries(data_aggregator, sample_ticks):
    """Test deduplication of entries."""
    # Create some duplicate entries
    existing_data = sample_ticks.copy()
    
    # Create new data where ONLY one entry has the same route name as in existing_data
    new_data = [
        # New unique entry
        {
            "date": (datetime.now() - timedelta(days=2)).isoformat(),
            "route": "New Route",
            "grade": "V3",
            "send_status": "sent"
        },
        # Exact duplicate of an existing entry by route name
        {
            "date": (datetime.now() - timedelta(days=1)).isoformat(),  # More recent date
            "route": "Test Route 1",  # Same route as in sample_ticks[0]
            "grade": "V4+",  # Slightly different grade
            "send_status": "sent"
        }
    ]
    
    # Expected deduplicated data should have:
    # 1. All routes from existing_data that don't have duplicates in new_data
    # 2. All unique routes from new_data
    # 3. For duplicate routes, the newer version (from new_data)
    result = data_aggregator.deduplicate_entries(existing_data, new_data)
    
    # Verify total count (3 original - 1 duplicate + 2 new = 4)
    assert len(result) == 4
    
    # Verify the duplicate entry from new_data replaced the one from existing_data
    # Find the entry with route "Test Route 1"
    duplicate_entries = [entry for entry in result if entry["route"] == "Test Route 1"]
    assert len(duplicate_entries) == 1
    # Verify it has the updated grade from new_data
    assert duplicate_entries[0]["grade"] == "V4+"
    
    # Verify the new unique entry was added
    new_entries = [entry for entry in result if entry["route"] == "New Route"]
    assert len(new_entries) == 1


@pytest.mark.asyncio
async def test_aggregate_all_data(data_aggregator, sample_user_id):
    """Test aggregating all data for a user."""
    # Mock individual fetching methods
    with patch.object(data_aggregator, 'fetch_climber_context', return_value={"name": "Test Climber"}), \
         patch.object(data_aggregator, 'fetch_recent_ticks', return_value=[{"route": "Test Route"}]), \
         patch.object(data_aggregator, 'fetch_performance_metrics', return_value={"boulder_pyramid": {"V5": 2}}), \
         patch.object(data_aggregator, 'fetch_chat_history', return_value=[{"message": "Test question"}]):
        
        result = await data_aggregator.aggregate_all_data(sample_user_id)
        
    # Verify aggregated result has all sections
    assert "climber_context" in result
    assert "recent_ticks" in result
    assert "performance_metrics" in result
    assert "chat_history" in result
    
    # Verify data from each source
    assert result["climber_context"]["name"] == "Test Climber"
    assert result["recent_ticks"][0]["route"] == "Test Route"
    assert result["performance_metrics"]["boulder_pyramid"]["V5"] == 2
    assert result["chat_history"][0]["message"] == "Test question" 