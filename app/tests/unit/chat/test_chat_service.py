"""
Tests for chat service functionality.

This module demonstrates how to use domain-specific fixtures
from the chat fixture module to test chat service functionality.
"""

import pytest
import pytest_asyncio
from typing import Dict, List, Any, Optional
from unittest.mock import AsyncMock

from app.tests.utils.parameterization import ParamTestCase


# Convert class-based tests to module-level functions
@pytest.mark.asyncio
@pytest.mark.unit
async def test_chat_response_generation(mock_chat_service, sample_user_contexts):
    """Test generating a chat response with user context."""
    # Get predefined context
    context_data = sample_user_contexts["intermediate_user"]
    
    # Configure the context manager mock
    context_manager = mock_chat_service._test_mocks["context_manager"]
    context_manager.get_context.return_value = context_data
    
    # Create a query message
    message = "Can you recommend a training plan for improving my climbing?"
    
    # Call the service method - implementation may vary in the actual service
    response = await mock_chat_service.generate_response(
        user_id=context_data["user_id"],
        message=message
    )
    
    # Verify response content contains relevant terms
    assert response is not None
    assert "training" in response.lower() or "plan" in response.lower()
    
    # Verify context manager was called
    context_manager.get_context.assert_called_once()

@pytest.mark.asyncio
@pytest.mark.unit
async def test_llm_response_handling(mock_model_client, sample_llm_responses):
    """Test handling different types of LLM responses."""
    # Test different query types
    query_types = {
        "training": "I need a training plan for my climbing",
        "gear": "What equipment should I get for sport climbing?",
        "technique": "How can I improve my climbing technique for V5?"
    }
    
    for topic, query in query_types.items():
        # Create message structure
        messages = [
            {"role": "system", "content": "You are a helpful climbing assistant."},
            {"role": "user", "content": query}
        ]
        
        # Get response
        response = await mock_model_client.generate_response(messages=messages)
        
        # Verify response matches expected content
        assert response["choices"][0]["message"]["role"] == "assistant"
        
        content = response["choices"][0]["message"]["content"]
        
        # Check specific content for each topic
        if topic == "training":
            assert "Week" in content
            assert "Training Plan" in content
        elif topic == "gear":
            assert "Climbing Rack" in content
            assert "Quickdraws" in content
        elif topic == "technique":
            assert "Plateau" in content
            assert "Body Positioning" in content

@pytest.mark.asyncio
@pytest.mark.unit
async def test_context_enhancement(mock_chat_service, create_chat_context):
    """Test enhancing user context with additional data."""
    # Create a customized context
    context = create_chat_context(
        user_level="advanced",
        custom_fields={
            "user_profile": {
                "name": "Test User",
                "focus_areas": ["Endurance", "Power"]
            }
        }
    )
    
    # Configure mock context manager
    context_manager = mock_chat_service._test_mocks["context_manager"]
    context_manager.get_context.return_value = context
    
    # Configure the context update
    context_update = {
        "recent_sessions": [
            {"date": "2023-08-20", "focus": "Strength", "duration": 120},
            {"date": "2023-08-22", "focus": "Technique", "duration": 90}
        ]
    }
    
    # Add an update_context method to the mock for testing
    async def mock_update_context(user_id, updates):
        # In a real implementation, this would update the database
        # For the test, we'll just verify it was called correctly
        assert user_id == context["user_id"]
        assert "recent_sessions" in updates
        return True
    
    context_manager.update_context = AsyncMock(side_effect=mock_update_context)
    
    # Call the method - implementation may vary
    result = await mock_chat_service.update_user_context(
        user_id=context["user_id"],
        updates=context_update
    )
    
    # Verify context manager was called
    context_manager.update_context.assert_called_once()
    
    # Ensure update was successful
    assert result is True

@pytest.mark.asyncio
@pytest.mark.unit
async def test_conversation_history_management(mock_chat_service, sample_conversation_histories):
    """Test managing conversation history."""
    # Get a sample conversation
    conversation = sample_conversation_histories["training_conversation"]
    
    # Create methods for testing history management
    redis_client = AsyncMock()
    
    async def mock_get_conversation(user_id):
        return conversation
        
    async def mock_add_message(user_id, message):
        assert "role" in message
        assert "content" in message
        return True
        
    redis_client.get_conversation_history = AsyncMock(side_effect=mock_get_conversation)
    redis_client.add_message_to_conversation = AsyncMock(side_effect=mock_add_message)
    
    # Add the redis client to the service mocks
    mock_chat_service._test_mocks["redis_client"] = redis_client
    
    # Add a method to the service for testing
    async def get_history(user_id):
        return await redis_client.get_conversation_history(user_id)
        
    async def add_to_history(user_id, message):
        return await redis_client.add_message_to_conversation(user_id, message)
    
    mock_chat_service.get_conversation_history = get_history
    mock_chat_service.add_message_to_history = add_to_history
    
    # Test getting history
    history = await mock_chat_service.get_conversation_history("user1")
    assert history == conversation
    
    # Test adding to history
    new_message = {"role": "user", "content": "New test message"}
    result = await mock_chat_service.add_message_to_history("user1", new_message)
    assert result is True
    
    # Verify redis methods were called
    redis_client.get_conversation_history.assert_called_once()
    redis_client.add_message_to_conversation.assert_called_once()


# Define parameterized test cases
def prompt_generation_test_cases():
    """Generate test cases for prompt generation."""
    return [
        ParamTestCase(
            id="basic_prompt",
            input={
                "template_name": "basic_chat",
                "variables": {
                    "user_message": "How do I improve my climbing?"
                }
            },
            expected={
                "contains": ["SendSage", "climbing assistant", "improve my climbing"],
                "excludes": ["profile", "activity"]
            },
            description="Basic prompt without context variables"
        ),
        ParamTestCase(
            id="context_prompt",
            input={
                "template_name": "context_enhanced",
                "variables": {
                    "user_message": "What grade should I aim for?",
                    "user_profile": {"experience": "intermediate", "grade": "5.11b"},
                    "recent_activity": "3 sessions last week"
                }
            },
            expected={
                "contains": ["SendSage", "profile", "activity", "grade should I aim for"],
                "excludes": ["current_grade"]
            },
            description="Context-enhanced prompt with user data"
        ),
        ParamTestCase(
            id="recommendation_prompt",
            input={
                "template_name": "recommendation",
                "variables": {
                    "user_profile": {"name": "Alex", "experience": "advanced"},
                    "recent_activity": "Sent 5.12c project",
                    "current_grade": "5.12c"
                }
            },
            expected={
                "contains": ["SendSage", "profile", "activity", "climbing grade", "recommendation"],
                "excludes": ["question"]
            },
            description="Recommendation prompt for advanced user"
        )
    ]


@pytest.mark.parametrize(
    "test_case",
    prompt_generation_test_cases(),
    ids=[tc.id for tc in prompt_generation_test_cases()]
)
@pytest.mark.unit
def test_prompt_generation(sample_prompt_templates, test_case):
    """
    Test prompt template generation with parameterized test cases.
    
    This test demonstrates combining the domain-specific fixtures with
    the test parameterization utilities for maintainable tests.
    """
    # Get the template from the fixtures
    template_name = test_case.input["template_name"]
    template = sample_prompt_templates[template_name]
    
    # Get variables for the template
    variables = test_case.input["variables"]
    
    # Generate the prompt
    prompt = template.format(**variables)
    
    # Check for expected content
    for expected_text in test_case.expected["contains"]:
        assert expected_text in prompt, f"'{expected_text}' not found in prompt"
    
    for excluded_text in test_case.expected["excludes"]:
        assert excluded_text not in prompt, f"'{excluded_text}' was found in prompt but should be excluded" 