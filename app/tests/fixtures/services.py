"""
Service layer fixtures for testing.

This module provides fixtures for service layer components including
mock services, context managers, event managers, and other service-related
functionality needed for testing.
"""

import pytest
import pytest_asyncio
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat.context.orchestrator import ContextOrchestrator
from app.services.chat.ai.basic_chat import BasicChatService
from app.services.chat.ai.premium_chat import PremiumChatService
from app.services.chat.events.manager import EventManager, EventType
from app.services.utils.grade_service import GradeService


@pytest_asyncio.fixture
async def mock_context_orchestrator(db_session: AsyncSession, redis_client: redis.Redis) -> AsyncGenerator[ContextOrchestrator, None]:
    """
    Provide a mocked context orchestrator for testing chat services.
    
    This fixture creates a mock of the ContextOrchestrator that can be
    configured by tests to return specific values.
    """
    mock_orchestrator = AsyncMock(spec=ContextOrchestrator)
    
    # Configure default behavior
    mock_orchestrator.get_context.return_value = {
        "user_context": {
            "experience_level": "intermediate",
            "climbing_types": ["bouldering", "sport"],
            "preferred_grades": ["V4-V6", "5.10-5.12"]
        },
        "climbing_history": [],
        "recent_conversations": []
    }
    
    yield mock_orchestrator


@pytest_asyncio.fixture
async def event_manager() -> AsyncGenerator[EventManager, None]:
    """
    Provide an event manager for testing.
    
    This fixture creates a real EventManager instance that can be
    used to test event-related functionality.
    """
    manager = EventManager()
    yield manager


@pytest_asyncio.fixture
async def mock_basic_chat_service(
    mock_context_orchestrator: ContextOrchestrator,
    redis_client: redis.Redis,
    event_manager: EventManager
) -> AsyncGenerator[BasicChatService, None]:
    """
    Provide a mocked basic chat service for testing.
    
    This fixture creates a partially mocked BasicChatService with
    dependencies injected for testing.
    """
    # Create the service with real dependencies
    service = BasicChatService(
        context_orchestrator=mock_context_orchestrator,
        redis_client=redis_client,
        event_manager=event_manager
    )
    
    # Patch the send_message method to avoid actual LLM calls
    with patch.object(service, "_send_to_llm", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {
            "content": "This is a test response from the mock chat service.",
            "model_used": "gpt-3.5-turbo",
            "tokens": {
                "prompt": 150,
                "completion": 50,
                "total": 200
            }
        }
        
        yield service


@pytest_asyncio.fixture
async def mock_premium_chat_service(
    mock_context_orchestrator: ContextOrchestrator,
    event_manager: EventManager
) -> AsyncGenerator[PremiumChatService, None]:
    """
    Provide a mocked premium chat service for testing.
    
    This fixture creates a partially mocked PremiumChatService with
    dependencies injected for testing.
    """
    # Create the service with real dependencies
    service = PremiumChatService(
        context_orchestrator=mock_context_orchestrator,
        event_manager=event_manager
    )
    
    # Patch the send_message method to avoid actual LLM calls
    with patch.object(service, "_send_to_llm", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {
            "content": "This is a test response from the mock premium chat service.",
            "model_used": "gpt-4",
            "tokens": {
                "prompt": 250,
                "completion": 150,
                "total": 400
            }
        }
        
        yield service


@pytest_asyncio.fixture(autouse=True)
async def reset_grade_service():
    """
    Reset the GradeService cache between tests.
    
    This fixture ensures that the GradeService cache is reset
    to avoid test interference.
    """
    # Store original cache
    original_cache = GradeService._grade_conversion_cache.copy()
    original_systems = GradeService._known_grade_systems.copy()
    
    # Yield for test execution
    yield
    
    # Restore original cache
    GradeService._grade_conversion_cache = original_cache
    GradeService._known_grade_systems = original_systems 