"""
Tests for chat schema validation.

This module tests schema validation, particularly focusing on:
- Validators for message length
- Validators for activity length
- Field constraints and validations
"""

import pytest
from pydantic import ValidationError
from datetime import datetime, timezone

from app.schemas.chat import (
    Message,
    ChatMessage,
    OnboardingData,
    ChatSettings
)
from app.models.enums import SessionLength, SleepScore, NutritionScore


@pytest.mark.unit
def test_message_validation():
    """Test Message schema validation."""
    # Valid message
    valid_message = Message(
        role="user",
        content="This is a valid message"
    )
    assert valid_message.role == "user"
    assert valid_message.content == "This is a valid message"
    assert isinstance(valid_message.created_at, datetime)
    
    # Invalid role
    with pytest.raises(ValidationError) as exc_info:
        Message(role="invalid_role", content="Test message")
    assert "role" in str(exc_info.value)
    
    # Empty content
    with pytest.raises(ValidationError) as exc_info:
        Message(role="user", content="")
    assert "content" in str(exc_info.value)
    
    # Content too long (over 4000 chars)
    with pytest.raises(ValidationError) as exc_info:
        Message(role="user", content="x" * 4001)
    assert "content" in str(exc_info.value)


@pytest.mark.unit
def test_chat_message_history_validation():
    """Test ChatMessage history length validation."""
    # Valid with default empty history
    valid_msg = ChatMessage(user_prompt="Test prompt")
    assert valid_msg.user_prompt == "Test prompt"
    assert valid_msg.conversation_history == []
    
    # Valid with some history
    history = [
        Message(role="user", content="First message"),
        Message(role="assistant", content="First response")
    ]
    valid_with_history = ChatMessage(
        user_prompt="Another prompt",
        conversation_history=history
    )
    assert len(valid_with_history.conversation_history) == 2
    
    # Too many messages in history (over 50)
    too_many_messages = [
        Message(role="user", content=f"Message {i}")
        for i in range(51)  # 51 messages exceeds limit
    ]
    
    with pytest.raises(ValidationError) as exc_info:
        ChatMessage(
            user_prompt="Test prompt", 
            conversation_history=too_many_messages
        )
    assert "List should have at most 50 items" in str(exc_info.value)


@pytest.mark.unit
def test_onboarding_data_validation():
    """Test OnboardingData validation, especially activity length."""
    # Valid minimal data
    valid_data = OnboardingData(
        user_summary="Beginner climber focused on bouldering",
        climbing_stats={"highest_grade": "V4"},
        recent_activity=[{"route": "Test Route", "grade": "V3"}],
        preferences={"preferred_climbing_style": "Bouldering"}
    )
    assert valid_data.user_summary == "Beginner climber focused on bouldering"
    
    # Get enum values dynamically for testing
    session_length_values = list(SessionLength)
    sleep_score_values = list(SleepScore)
    nutrition_score_values = list(NutritionScore)
    
    # With optional enum fields - using first values from enum
    with_enums = OnboardingData(
        user_summary="Intermediate sport climber",
        climbing_stats={"highest_grade": "5.11a"},
        recent_activity=[{"route": "Test Route", "grade": "5.10d"}],
        preferences={"preferred_climbing_style": "Sport"},
        session_length=session_length_values[0],
        sleep_score=sleep_score_values[0],
        nutrition_score=nutrition_score_values[0]
    )
    assert with_enums.session_length == session_length_values[0]
    assert with_enums.sleep_score == sleep_score_values[0]
    
    # Too many activities (over 10)
    too_many_activities = [
        {"date": f"2023-01-{i}", "route": f"Route {i}", "grade": "5.10a"}
        for i in range(1, 12)  # 11 activities exceeds limit
    ]
    
    with pytest.raises(ValidationError) as exc_info:
        OnboardingData(
            user_summary="Test User",
            climbing_stats={},
            recent_activity=too_many_activities,
            preferences={}
        )
    assert "List should have at most 10 items" in str(exc_info.value)


@pytest.mark.unit
def test_chat_settings_validation():
    """Test ChatSettings validation, especially for limits."""
    # Valid settings with no limits (premium)
    premium_settings = ChatSettings(
        use_reasoner=True,
        daily_message_limit=None,
        messages_remaining=None,
        conversation_retention_days=90
    )
    assert premium_settings.use_reasoner is True
    assert premium_settings.daily_message_limit is None
    
    # Valid settings with limits (basic tier)
    basic_settings = ChatSettings(
        use_reasoner=False,
        daily_message_limit=10,
        messages_remaining=5,
        conversation_retention_days=30
    )
    assert basic_settings.daily_message_limit == 10
    assert basic_settings.messages_remaining == 5
    
    # Invalid: remaining > limit
    with pytest.raises(ValidationError) as exc_info:
        ChatSettings(
            daily_message_limit=10,
            messages_remaining=15,  # Exceeds limit
            conversation_retention_days=30
        )
    assert "Remaining messages cannot exceed daily limit" in str(exc_info.value)
    
    # Invalid: retention days out of range
    with pytest.raises(ValidationError) as exc_info:
        ChatSettings(
            daily_message_limit=10,
            messages_remaining=5,
            conversation_retention_days=100  # Over 90 days limit
        )
    assert "conversation_retention_days" in str(exc_info.value) 