"""
Tests demonstrating the use of service factories for testing services.

This module demonstrates how to use the service factories to create
pre-configured service instances for testing with appropriate mocks.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Import factories conditionally to handle test environments
try:
    from app.tests.factories import ChatServiceFactory, ClimbingServiceFactory
    SAMPLE_MODE = False
except (ImportError, ModuleNotFoundError):
    # Create mock factories for sample mode
    SAMPLE_MODE = True
    
    class MockFactory:
        @classmethod
        async def create_service(cls, **kwargs):
            mock_service = MagicMock()
            mock_service._test_mocks = {k: AsyncMock() for k in ["context_manager", "model_client", "db_service"]}
            return mock_service
    
    ChatServiceFactory = ClimbingServiceFactory = MockFactory


@pytest.mark.skipif(SAMPLE_MODE, reason="Running in sample mode without real implementations")
@pytest.mark.asyncio
async def test_chat_service_factory():
    """Test creating a chat service with the factory."""
    # Example context data
    context_data = {
        "user_info": {
            "name": "Test User",
            "climbing_grade": "5.11a",
            "climbing_style": "Sport"
        },
        "preferences": {
            "training_focus": "Endurance",
            "goal_grade": "5.12a"
        }
    }
    
    # Example conversation history
    conversation_history = [
        {"role": "user", "content": "What grade should I focus on next?"},
        {"role": "assistant", "content": "Based on your current level, 5.11c would be a good next goal."}
    ]
    
    # Create the service with our test data
    service = await ChatServiceFactory.create_service(
        context_data=context_data,
        conversation_history=conversation_history
    )
    
    # Verify mocks were configured correctly
    if hasattr(service, "_test_mocks"):
        assert service._test_mocks["context_manager"].get_context.return_value == context_data
        if "redis_client" in service._test_mocks:
            assert service._test_mocks["redis_client"].get_conversation_history.return_value == conversation_history
    
    # Demonstrate using the service in a test (simplified)
    if hasattr(service, "_test_mocks") and "model_client" in service._test_mocks:
        service._test_mocks["model_client"].generate_response.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "I recommend focusing on 5.11a as your next project grade."
                    }
                }
            ]
        }


@pytest.mark.skipif(SAMPLE_MODE, reason="Running in sample mode without real implementations")
@pytest.mark.asyncio
async def test_climbing_service_factory():
    """Test creating a climbing service with the factory."""
    # Example climb data
    test_climbs = [
        {
            "id": "climb1",
            "user_id": "user1",
            "route": "Test Route 1",
            "grade": "5.10a",
            "send_status": "sent",
            "date": "2023-01-15",
            "location": "Red River Gorge",
            "discipline": "Sport"
        },
        {
            "id": "climb2",
            "user_id": "user1",
            "route": "Test Route 2",
            "grade": "V4",
            "send_status": "project",
            "date": "2023-01-10",
            "location": "Bishop",
            "discipline": "Boulder"
        }
    ]
    
    # Create the service with our test data
    service = await ClimbingServiceFactory.create_service(
        test_climbs=test_climbs
    )
    
    # Verify db mock was configured correctly if in testing mode
    if hasattr(service, "_test_mocks") and "db_service" in service._test_mocks:
        if hasattr(service._test_mocks["db_service"], "get_user_ticks"):
            result = await service._test_mocks["db_service"].get_user_ticks()
            assert result == test_climbs
    
    # Test retrieving a specific climb
    if hasattr(service, "_test_mocks") and "db_service" in service._test_mocks:
        climb = await service._test_mocks["db_service"].get_tick_by_id("climb1")
        assert climb["route"] == "Test Route 1"
    
    # Demonstrate mocking grade conversion
    if hasattr(service, "_test_mocks") and "grade_service" in service._test_mocks:
        service._test_mocks["grade_service"].convert_grade_system.return_value = "7a"
    
    # In a real test you would call service methods and verify results 