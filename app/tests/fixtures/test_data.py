"""
Test data fixtures for testing.

This module provides fixtures for loading and generating test data
for various entity types needed in tests.
"""

import pytest
import pytest_asyncio
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import random
from uuid import uuid4

from app.tests.config import test_settings


def load_fixture(
    fixture_name: str,
    format: str = "json"
) -> Union[Dict[str, Any], List[Any]]:
    """
    Load test data from a fixture file.

    Args:
        fixture_name: Name of the fixture file without extension
        format: Format of the fixture (json or yaml)

    Returns:
        The loaded fixture data
    """
    base_path = test_settings.TEST_DATA_DIR
    file_path = base_path / f"{fixture_name}.{format}"

    if not file_path.exists():
        raise FileNotFoundError(f"Test fixture not found: {file_path}")

    with open(file_path, "r") as f:
        if format == "json":
            return json.load(f)
        elif format == "yaml":
            return yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported fixture format: {format}")


@pytest.fixture
def load_user_data():
    """
    Load user test data from fixtures.
    
    This fixture provides a function to load predefined user data
    from JSON or YAML fixtures.
    """
    def _load_data(fixture_name: str = "users", format: str = "json") -> List[Dict[str, Any]]:
        return load_fixture(fixture_name, format)
    
    return _load_data


@pytest.fixture
def load_climb_data():
    """
    Load climbing test data from fixtures.
    
    This fixture provides a function to load predefined climbing data
    from JSON or YAML fixtures.
    """
    def _load_data(fixture_name: str = "climbs", format: str = "json") -> List[Dict[str, Any]]:
        return load_fixture(fixture_name, format)
    
    return _load_data


@pytest.fixture
def create_user_data():
    """
    Generate user test data dynamically.
    
    This fixture provides a function to create user data with
    customizable parameters for flexible test scenarios.
    """
    def _create(
        email_prefix: str = "test",
        domain: str = "example.com",
        password: str = "TestPassword123!",
        experience_level: str = "intermediate"
    ) -> Dict[str, Any]:
        """
        Generate consistent user test data with customizable parameters.
        
        Args:
            email_prefix: Prefix for the email address
            domain: Domain for the email address
            password: Password for the user
            experience_level: User's climbing experience level
            
        Returns:
            Dictionary with user data
        """
        username = f"{email_prefix}_{random.randint(1000, 9999)}"
        email = f"{username}@{domain}"

        return {
            "email": email,
            "username": username,
            "password": password,
            "experience_level": experience_level,
            "created_at": datetime.now(),
            "settings": {"beta_features": False, "notification_preferences": {"email": True}}
        }
    
    return _create


@pytest.fixture
def create_climb_data():
    """
    Generate climbing session test data dynamically.
    
    This fixture provides a function to create climbing data with
    customizable parameters for flexible test scenarios.
    """
    def _create(
        count: int = 5,
        user_id: Optional[str] = None,
        base_date: Optional[datetime] = None,
        grade_range: tuple = ("V1", "V7")
    ) -> List[Dict[str, Any]]:
        """
        Generate a list of climbing session test data.
        
        Args:
            count: Number of climbing sessions to generate
            user_id: Optional user ID to associate with climbs
            base_date: Starting date for the climbing sessions
            grade_range: Range of grades to use (inclusive)
            
        Returns:
            List of dictionaries with climbing session data
        """
        if base_date is None:
            base_date = datetime.now()

        grades = ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10"]
        valid_grades = grades[grades.index(grade_range[0]):grades.index(grade_range[1])+1]

        climbs = []
        for i in range(count):
            climb_type = random.choice(["Boulder", "Sport", "Trad"])
            climbs.append({
                "id": str(uuid4()),
                "date": base_date - timedelta(days=i*3),
                "route": f"Test Route {i+1}",
                "grade": random.choice(valid_grades),
                "send_status": random.choice(["sent", "project", "attempted"]),
                "user_id": user_id,
                "notes": f"Test climb notes {i+1}",
                "location": random.choice(["Indoor Gym", "Outdoor Crag", "Boulder Field"]),
                "climb_type": climb_type,
                "discipline": climb_type,
                "attempts": random.randint(1, 10)
            })

        return climbs
    
    return _create


@pytest.fixture
def create_conversation_data():
    """
    Generate conversation test data dynamically.
    
    This fixture provides a function to create chat conversation data with
    customizable parameters for testing chat services.
    """
    def _create(
        message_count: int = 5,
        user_id: Optional[str] = None,
        include_system_message: bool = True,
        topic: str = "climbing advice"
    ) -> Dict[str, Any]:
        """
        Generate conversation test data.
        
        Args:
            message_count: Number of messages to include
            user_id: Optional user ID to associate with the conversation
            include_system_message: Whether to include a system message
            topic: Topic of the conversation
            
        Returns:
            Dictionary with conversation data
        """
        conversation_id = str(uuid4())
        messages = []
        
        if include_system_message:
            messages.append({
                "role": "system",
                "content": "You are a helpful climbing assistant that provides advice on training, technique, and gear."
            })
        
        # Create alternating user/assistant messages
        for i in range(message_count):
            if i % 2 == 0:
                messages.append({
                    "role": "user",
                    "content": f"Question about {topic} #{i//2 + 1}."
                })
            else:
                messages.append({
                    "role": "assistant",
                    "content": f"Detailed answer about {topic} #{i//2 + 1}."
                })
        
        return {
            "conversation_id": conversation_id,
            "user_id": user_id or str(uuid4()),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "messages": messages,
            "metadata": {
                "topic": topic,
                "message_count": len(messages),
                "user_message_count": (message_count + 1) // 2,
                "assistant_message_count": message_count // 2
            }
        }
    
    return _create 