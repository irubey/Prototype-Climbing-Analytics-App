"""
Simple tests for loading fixture data.

These tests verify we can load fixture data without complex dependencies.
"""

import pytest
import json
from pathlib import Path


def load_fixture(fixture_name):
    """Load a JSON fixture file."""
    fixtures_dir = Path(__file__).parent / "data" / "fixtures"
    file_path = fixtures_dir / f"{fixture_name}.json"
    
    with open(file_path, "r") as f:
        return json.load(f)


def test_load_users_data():
    """Test loading user data from fixture."""
    users = load_fixture("users")
    
    # Verify basic structure
    assert isinstance(users, list), "Users data should be a list"
    assert len(users) > 0, "Users data should not be empty"
    
    # Check required fields in first user
    first_user = users[0]
    assert "email" in first_user, "User should have email"
    assert "username" in first_user, "User should have username"
    assert "password" in first_user, "User should have password"


def test_load_climbs_data():
    """Test loading climb data from fixture."""
    climbs = load_fixture("climbs")
    
    # Verify basic structure
    assert isinstance(climbs, list), "Climbs data should be a list"
    assert len(climbs) > 0, "Climbs data should not be empty"
    
    # Check required fields in first climb
    first_climb = climbs[0]
    assert "user_id" in first_climb, "Climb should have user_id"
    assert "route_name" in first_climb, "Climb should have route_name"
    assert "route_grade" in first_climb, "Climb should have route_grade"


def test_load_conversations_data():
    """Test loading conversation data from fixture."""
    conversations = load_fixture("conversations")
    
    # Verify basic structure
    assert isinstance(conversations, list), "Conversations data should be a list"
    assert len(conversations) > 0, "Conversations data should not be empty"
    
    # Check required fields in first conversation
    first_conv = conversations[0]
    assert "conversation_id" in first_conv, "Conversation should have conversation_id"
    assert "user_id" in first_conv, "Conversation should have user_id"
    assert "messages" in first_conv, "Conversation should have messages"
    
    # Check message structure
    messages = first_conv["messages"]
    assert isinstance(messages, list), "Messages should be a list"
    assert len(messages) > 0, "Messages should not be empty"
    
    first_message = messages[0]
    assert "role" in first_message, "Message should have role"
    assert "content" in first_message, "Message should have content"
    assert first_message["role"] in ["system", "user", "assistant"], f"Invalid message role: {first_message['role']}" 