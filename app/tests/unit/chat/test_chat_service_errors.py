"""
Tests for error handling in chat services.

This module focuses on error cases such as:
- Quota exceeded errors
- Model client errors
- Context-related errors
- Rate limiting
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import asyncio

from app.services.chat.events.manager import EventManager, EventType
from app.services.chat.ai.basic_chat import (
    BasicChatService, 
    QuotaExceededError, 
    ModelError, 
    ContextError,
    ChatError  # Add the base exception class
)
from app.services.chat.context.orchestrator import ContextOrchestrator


@pytest_asyncio.fixture
async def mock_redis():
    """Mock Redis client for testing."""
    redis_mock = AsyncMock()
    
    # Configure get method to be properly awaitable
    async def mock_get(*args, **kwargs):
        # Return the value set in the test
        if "quota" in args[0]:
            return "0"
        return redis_mock.get.return_value
    
    redis_mock.get.side_effect = mock_get
    
    # Setup pipeline
    pipeline_mock = AsyncMock()
    
    # Configure pipeline methods as methods returning the pipeline itself for chaining
    async def mock_incr(*args, **kwargs):
        return pipeline_mock
    
    async def mock_expire(*args, **kwargs):
        return pipeline_mock
    
    async def mock_execute(*args, **kwargs):
        return [1, True]
    
    pipeline_mock.incr.side_effect = mock_incr
    pipeline_mock.expire.side_effect = mock_expire
    pipeline_mock.execute.side_effect = mock_execute
    
    redis_mock.pipeline.return_value = pipeline_mock
    
    return redis_mock


@pytest_asyncio.fixture
async def mock_context_orchestrator():
    """Mock context orchestrator for testing."""
    context_mock = AsyncMock()
    
    # Setup default context return
    context_mock.get_context = AsyncMock(return_value={
        "user_id": "test-user",
        "profile": {"experience": "intermediate"},
        "summary": "Test user context"
    })
    
    return context_mock


@pytest_asyncio.fixture
async def mock_event_manager():
    """Mock event manager for testing."""
    event_manager = AsyncMock()
    
    # Setup publish method
    event_manager.publish_event = AsyncMock(return_value=None)
    event_manager.publish = AsyncMock(return_value=None)
    
    return event_manager


@pytest.fixture
def model_response():
    """Standard model response for testing."""
    return "This is a test response"


@pytest_asyncio.fixture
async def chat_service(mock_context_orchestrator, mock_event_manager, mock_redis, model_response):
    """Create a BasicChatService instance with mocked dependencies."""
    service = BasicChatService(
        context_manager=mock_context_orchestrator,
        event_manager=mock_event_manager,
        redis_client=mock_redis,
        monthly_quota=5  # Small quota for testing
    )
    
    # Mock the model client to avoid actual API calls
    model_client_mock = AsyncMock()
    model_client_mock.generate_response = AsyncMock(return_value=model_response)
    service.model = model_client_mock
    
    return service


@pytest.mark.asyncio
@pytest.mark.unit
async def test_quota_exceeded(chat_service, mock_redis):
    """Test handling of quota exceeded errors."""
    user_id = "test-user"
    prompt = "Test prompt"
    conversation_id = "test-convo"
    
    # Setup quota to be exceeded (must be returned by the mock_get side_effect)
    mock_redis.get.return_value = "5"  # Current usage equals quota
    
    # Replace exceeds_quota method to raise the right exception
    original_exceeds_quota = chat_service.exceeds_quota
    
    async def patched_exceeds_quota(uid):
        # Directly raise the exception that would be raised when quota is exceeded
        raise QuotaExceededError(5, 5)
    
    chat_service.exceeds_quota = patched_exceeds_quota
    
    try:
        # Test the process method properly handles quota exceeded
        result = await chat_service.process(user_id, prompt, conversation_id)
        
        # Should return None
        assert result is None
        
        # Verify error event was published with the correct data
        chat_service.event_manager.publish.assert_any_call(
            user_id,
            EventType.ERROR,
            {
                "error": "Monthly quota exceeded (5/5 requests). Upgrade to Premium for unlimited coaching!",
                "error_type": "quota_exceeded",
                "details": {"current_usage": 5, "quota_limit": 5}
            }
        )
    finally:
        # Restore the original method
        chat_service.exceeds_quota = original_exceeds_quota


@pytest.mark.asyncio
@pytest.mark.unit
async def test_model_error_handling(chat_service):
    """Test handling of model errors during response generation."""
    user_id = "test-user"
    prompt = "Test prompt"
    conversation_id = "test-convo"
    
    # Patch the exceeds_quota method to avoid the issue with get() returning a coroutine
    with patch.object(chat_service, 'exceeds_quota', AsyncMock(return_value=False)):
        # Configure mock to raise an exception
        error_message = "Model API error"
        chat_service.model.generate_response.side_effect = Exception(error_message)
        
        # Process should handle the error
        result = await chat_service.process(user_id, prompt, conversation_id)
        
        # Should return None
        assert result is None
        
        # Verify error was published via event manager
        chat_service.event_manager.publish.assert_any_call(
            user_id,
            EventType.ERROR,
            {
                "error": "Unable to generate response. Please try again in a moment.",
                "error_type": "model_error",
                "details": {"original_error": str(Exception(error_message)), "status_code": None}
            }
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_context_error_handling(chat_service, mock_context_orchestrator):
    """Test handling of context-related errors."""
    user_id = "test-user"
    prompt = "Test prompt"
    conversation_id = "test-convo"
    
    # Patch the exceeds_quota method to avoid the issue with get() returning a coroutine
    with patch.object(chat_service, 'exceeds_quota', AsyncMock(return_value=False)):
        # Configure context manager to raise an exception
        error_message = "Context fetch error"
        mock_context_orchestrator.get_context.side_effect = Exception(error_message)
        
        # Process should handle the error
        result = await chat_service.process(user_id, prompt, conversation_id)
        
        # Should return None
        assert result is None
        
        # Verify error was published via event manager
        chat_service.event_manager.publish.assert_any_call(
            user_id,
            EventType.ERROR,
            {
                "error": "Unable to process your climbing context. Please try again.",
                "error_type": "context_error",
                "details": {"original_error": error_message}
            }
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_quota_increment(chat_service, mock_redis, mock_context_orchestrator):
    """Test that quota is incremented after successful processing."""
    user_id = "test-user"
    prompt = "Test prompt"
    conversation_id = "test-convo"

    # Configure the mock context orchestrator
    mock_context_orchestrator.get_context.return_value = {"user_id": user_id}

    # Configure model to return a valid response
    chat_service.model.generate_response.return_value = "This is a test response"

    # Create a mock for the Redis pipeline that works correctly for async code
    pipeline_mock = AsyncMock()
    pipeline_mock.incr.return_value = pipeline_mock  # Return self for chaining
    pipeline_mock.expire.return_value = pipeline_mock  # Return self for chaining
    pipeline_mock.execute.return_value = AsyncMock(return_value=[1, True])  # Mock the execute result
    
    # Replace the pipeline method with a method that returns our pipeline mock
    original_pipeline = mock_redis.pipeline
    mock_redis.pipeline = MagicMock(return_value=pipeline_mock)

    # Patch the exceeds_quota method to return False
    async def mock_exceeds_quota(uid):
        return False

    original_exceeds_quota = chat_service.exceeds_quota
    chat_service.exceeds_quota = mock_exceeds_quota

    try:
        # Process should succeed
        result = await chat_service.process(user_id, prompt, conversation_id)

        # Verify successful response
        assert result == "This is a test response"
        
        # Verify that pipeline methods were called
        mock_redis.pipeline.assert_called_once()
        assert pipeline_mock.incr.called
        assert pipeline_mock.expire.called
        assert pipeline_mock.execute.called
    finally:
        # Restore original methods
        chat_service.exceeds_quota = original_exceeds_quota
        mock_redis.pipeline = original_pipeline


@pytest.mark.asyncio
@pytest.mark.unit
async def test_publish_error(chat_service):
    """Test error publishing functionality."""
    user_id = "test-user"
    
    # Create a test error to publish
    test_error = ChatError(
        message="Test error message",
        error_type="test_error",
        details={"additional": "test detail"}
    )
    
    # Publish the error
    await chat_service._publish_error(user_id, test_error)
    
    # Verify event was published with correct parameters
    chat_service.event_manager.publish.assert_called_once()
    call_args = chat_service.event_manager.publish.call_args[0]
    
    assert call_args[0] == user_id
    assert call_args[1] == EventType.ERROR
    error_data = call_args[2]
    
    assert error_data["error_type"] == "test_error"
    assert error_data["error"] == "Test error message"
    assert error_data["details"]["additional"] == "test detail" 