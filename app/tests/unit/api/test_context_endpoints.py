"""
Tests for context API endpoints.

This module tests the REST API endpoints for retrieving and managing user context data.
"""

import pytest
import pytest_asyncio
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from app.db.session import get_db, DatabaseSessionManager
from app.core.auth import get_current_user

from app.api.v1.endpoints.context import router

@pytest.fixture
def sample_context_response():
    """Provides a sample context for testing API responses."""
    return {
        "context_version": "1.0",
        "summary": "You've climbed for 3 years, focusing on bouldering. Your highest send is V5. Goal: V8 by December.",
        "profile": {
            "years_climbing": 3,
            "total_climbs": 200,
            "experience_level": "intermediate"
        },
        "performance": {
            "highest_boulder_grade": "V5",
            "highest_sport_grade": "5.11c"
        },
        "trends": {
            "grade_progression_all_time": 0.5,
            "grade_progression_6mo": 0.8,
            "training_consistency": 0.7
        },
        "relevance": {
            "training": 0.9,
            "bouldering": 0.8
        },
        "goals": {
            "goal_grade_boulder": "V8",
            "goal_deadline": "2023-12-31T00:00:00Z",
            "progress": 0.6
        },
        "uploads": []
    }

@pytest_asyncio.fixture
async def mock_orchestrator():
    """Create a mock context orchestrator for testing."""
    mock = AsyncMock()
    
    # Configure default returns
    mock.get_context.return_value = None
    mock.refresh_context.return_value = True
    mock.handle_data_update.return_value = None
    mock.bulk_refresh_contexts.return_value = {}
    
    return mock

@pytest.fixture
def app(mock_db, test_user):
    """Create a test FastAPI application with only the context router."""
    from app.db.session import DatabaseSessionManager
    
    # Create a new FastAPI app instance
    app = FastAPI()
    
    # Set up a mock db_manager in app state
    app.state.db_manager = AsyncMock(spec=DatabaseSessionManager)
    app.state.db_manager.session = AsyncMock()
    
    # Add the router
    app.include_router(router, prefix="/api/v1/context")
    
    # Override the get_db dependency
    app.dependency_overrides[get_db] = lambda: mock_db
    # Override the authentication dependency directly
    app.dependency_overrides[get_current_user] = lambda: test_user
    
    return app

@pytest_asyncio.fixture
async def client(app):
    """Create an async client for testing the API."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

@pytest.fixture
def test_user():
    """Create a test user for authenticated endpoints."""
    return MagicMock(
        id="test_user_id",
        email="test@example.com",
        is_active=True,
        scopes=["user"]
    )

@pytest.fixture
def mock_db():
    """Creates a mock database session."""
    mock_session = AsyncMock()
    
    # Add async context manager methods
    async def _aenter(*args, **kwargs):
        return mock_session
    
    async def _aexit(*args, **kwargs):
        pass
    
    mock_session.__aenter__ = _aenter
    mock_session.__aexit__ = _aexit
    
    return mock_session

@pytest_asyncio.fixture
async def auth_client(app, client, mock_orchestrator):
    """Creates an authenticated test client."""
    from fastapi import BackgroundTasks
    
    # Patch only the orchestrator - auth is handled by app.dependency_overrides
    with patch("app.api.v1.endpoints.context.ContextOrchestrator", return_value=mock_orchestrator):
        with patch("app.api.v1.endpoints.context.BackgroundTasks", return_value=MagicMock(spec=BackgroundTasks)):
            yield client

@pytest.mark.asyncio
async def test_get_context(auth_client, mock_orchestrator, sample_context_response):
    """Test retrieving context for a user."""
    user_id = "test_user_123"

    # Configure mock to return sample context
    mock_orchestrator.get_context.return_value = sample_context_response

    # Make request to endpoint
    response = await auth_client.get(f"/api/v1/context/{user_id}")

    # Verify response
    assert response.status_code == 200
    assert response.json() == sample_context_response

    # Verify orchestrator was called with correct params
    mock_orchestrator.get_context.assert_called_once()
    args, kwargs = mock_orchestrator.get_context.call_args
    assert kwargs["user_id"] == user_id
    assert "query" in kwargs
    assert "force_refresh" in kwargs

@pytest.mark.asyncio
async def test_get_context_with_query(auth_client, mock_orchestrator, sample_context_response):
    """Test retrieving context with a query parameter."""
    user_id = "test_user_123"
    query = "How can I improve finger strength?"

    # Configure mock to return sample context
    mock_orchestrator.get_context.return_value = sample_context_response

    # Make request to endpoint with query param
    response = await auth_client.get(
        f"/api/v1/context/{user_id}",
        params={"query": query}
    )

    # Verify response
    assert response.status_code == 200

    # Verify orchestrator was called with query
    mock_orchestrator.get_context.assert_called_once()
    args, kwargs = mock_orchestrator.get_context.call_args
    assert kwargs["query"] == query

@pytest.mark.asyncio
async def test_get_context_not_found(auth_client, mock_orchestrator):
    """Test handling when context is not found."""
    user_id = "nonexistent_user"

    # Configure mock to return None (not found)
    mock_orchestrator.get_context.return_value = None

    # Make request to endpoint
    response = await auth_client.get(f"/api/v1/context/{user_id}")

    # Should return 404 Not Found
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_refresh_context(auth_client, mock_orchestrator):
    """Test initiating an asynchronous context refresh."""
    user_id = "test_user_123"

    # Configure mock to return success
    mock_orchestrator.refresh_context.return_value = True

    # Make request to endpoint
    response = await auth_client.post(f"/api/v1/context/{user_id}/refresh")

    # Verify response indicates success
    assert response.status_code == 200
    assert "initiated successfully" in response.json()["status"].lower()

    # Background task should be added, but not awaited in endpoint
    # So we don't verify the call directly

@pytest.mark.asyncio
async def test_update_context(auth_client, mock_orchestrator, sample_context_response):
    """Test updating specific sections of a user's context."""
    user_id = "test_user_123"

    # Update payload with new goal
    update_data = {
        "updates": {
            "goals": {
                "goal_grade_boulder": "V8",
                "goal_deadline": "2024-06-30T00:00:00Z"
            }
        },
        "replace": False  # Merge with existing data
    }

    # Configure mock to return updated context
    mock_orchestrator.handle_data_update.return_value = sample_context_response

    # Make request to endpoint
    response = await auth_client.patch(
        f"/api/v1/context/{user_id}",
        json=update_data
    )

    # Verify response
    assert response.status_code == 200
    assert response.json() == sample_context_response

    # Verify orchestrator was called with correct params
    mock_orchestrator.handle_data_update.assert_called_once()
    args, kwargs = mock_orchestrator.handle_data_update.call_args
    assert kwargs["user_id"] == user_id
    assert kwargs["updates"] == update_data["updates"]
    assert kwargs["replace"] == update_data["replace"]

@pytest.mark.asyncio
async def test_update_context_not_found(auth_client, mock_orchestrator):
    """Test handling when context to update is not found."""
    user_id = "nonexistent_user"

    # Update payload
    update_data = {
        "updates": {"goals": {"goal_grade_boulder": "V8"}},
        "replace": False
    }

    # Configure mock to return None (not found)
    mock_orchestrator.handle_data_update.return_value = None

    # Make request to endpoint
    response = await auth_client.patch(
        f"/api/v1/context/{user_id}",
        json=update_data
    )

    # Should return 404 Not Found
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_bulk_refresh_contexts(auth_client, mock_orchestrator):
    """Test initiating bulk context refresh for multiple users."""
    # List of user IDs to refresh
    user_ids = ["user1", "user2", "user3"]

    # Configure mock to return success result
    results = {id: True for id in user_ids}
    mock_orchestrator.bulk_refresh_contexts.return_value = results

    # Make request to endpoint
    response = await auth_client.post(
        "/api/v1/context/bulk-refresh",
        params={"user_ids": user_ids}
    )

    # Verify response indicates success
    assert response.status_code == 200
    assert "initiated successfully" in response.json()["status"].lower()

    # Background task should be added, not directly called

@pytest.mark.asyncio
async def test_bulk_refresh_contexts_no_ids(auth_client, mock_orchestrator):
    """Test bulk refresh with no specific user IDs (refresh all)."""
    # Make request to endpoint with no user_ids
    response = await auth_client.post("/api/v1/context/bulk-refresh")

    # Verify response indicates success
    assert response.status_code == 200
    assert "initiated successfully" in response.json()["status"].lower()

    # Background task should be added, not directly called

@pytest.mark.asyncio
async def test_unauthorized_access(mock_db):
    """Test that unauthorized access to endpoints returns 401."""
    from fastapi import BackgroundTasks, FastAPI
    from app.db.session import DatabaseSessionManager, get_db
    
    # Create a new app instance without auth overrides
    app = FastAPI()
    
    # Mock the get_db dependency directly
    app.dependency_overrides[get_db] = lambda: mock_db
    
    app.include_router(router, prefix="/api/v1/context")
    
    # Create an unauthenticated client
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        with patch("app.api.v1.endpoints.context.BackgroundTasks", return_value=MagicMock(spec=BackgroundTasks)):
            # Test get context endpoint
            response = await client.get("/api/v1/context/123")
            assert response.status_code == 401
            
            # Test refresh context endpoint
            response = await client.post("/api/v1/context/123/refresh")
            assert response.status_code == 401
            
            # Test update context endpoint
            response = await client.patch(
                "/api/v1/context/123",
                json={"updates": {"profile": {"years_climbing": 5}}, "replace": False}
            )
            assert response.status_code == 401
            
            # Test bulk refresh endpoint
            response = await client.post("/api/v1/context/bulk-refresh")
            assert response.status_code == 401

@pytest.mark.asyncio
async def test_validation_errors(auth_client, mock_orchestrator):
    """Test handling of validation errors in request data."""
    user_id = "test_user_123"

    # Invalid update data (missing required field)
    invalid_data = {
        # Missing "updates" field
        "replace": True
    }

    # Make request to endpoint
    response = await auth_client.patch(
        f"/api/v1/context/{user_id}",
        json=invalid_data
    )

    # Should return 422 Unprocessable Entity
    assert response.status_code == 422
    # Check for field required error instead of validation error
    assert "field required" in response.json()["detail"][0]["msg"].lower() 