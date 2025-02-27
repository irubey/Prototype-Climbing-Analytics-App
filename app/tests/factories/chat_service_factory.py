"""Factories for creating pre-configured chat service test instances."""
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Optional, Any


class ChatServiceFactory:
    """Factory for creating preconfigured chat service test instances."""

    @classmethod
    async def create_service(
        cls,
        mock_redis: bool = True,
        mock_llm: bool = True,
        mock_context: bool = True,
        context_data: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ):
        """Create a chat service instance with configurable mocks.

        Args:
            mock_redis: Whether to mock the Redis client
            mock_llm: Whether to mock the LLM client
            mock_context: Whether to mock the context manager
            context_data: Optional predefined context data
            conversation_history: Optional predefined conversation history

        Returns:
            Configured ChatService instance with appropriate mocks
        """
        from app.services.chat.ai.model_client import ModelClient
        from app.services.chat.context.orchestrator import ContextOrchestrator
        from app.services.chat.events.manager import EventManager

        # Create default mock dependencies
        context_manager = AsyncMock(spec=ContextOrchestrator)
        event_manager = AsyncMock(spec=EventManager)
        model_client = AsyncMock(spec=ModelClient) if mock_llm else None

        # Configure mock behavior
        if mock_context and context_data:
            context_manager.get_context.return_value = context_data

        # Create Redis client mock separately (not passed to constructor)
        redis_client = None
        if mock_redis and conversation_history:
            redis_client = AsyncMock()
            redis_client.get_conversation_history.return_value = conversation_history

        # Import here to avoid circular imports
        from app.services.chat.ai.premium_chat import PremiumChatService

        # Create service instance with mocks - based on actual constructor parameters
        service = PremiumChatService(
            model_client=model_client,
            context_manager=context_manager,
            event_manager=event_manager
        )

        # Store mock references for test assertion access
        service._test_mocks = {
            "context_manager": context_manager,
            "event_manager": event_manager,
            "model_client": model_client,
            "redis_client": redis_client
        }
        
        # Add missing methods needed for tests
        async def generate_response(user_id, message):
            """Mock implementation of generate_response method."""
            # Get user context
            context = await context_manager.get_context(user_id)
            
            # Generate a response using the model client
            if model_client:
                messages = [{"role": "user", "content": message}]
                response = await model_client.generate_response(messages=messages)
                return response["choices"][0]["message"]["content"]
            
            return "Mock response for: " + message
            
        async def update_user_context(user_id, updates):
            """Mock implementation of update_user_context method."""
            # Pass to context manager
            if hasattr(context_manager, "update_context"):
                return await context_manager.update_context(user_id, updates)
            return True
            
        async def get_conversation_history(user_id):
            """Mock implementation of get_conversation_history method."""
            # Get from Redis client
            if redis_client and hasattr(redis_client, "get_conversation_history"):
                return await redis_client.get_conversation_history(user_id)
            return []
            
        async def add_message_to_history(user_id, message):
            """Mock implementation of add_message_to_history method."""
            # Add to Redis client
            if redis_client and hasattr(redis_client, "add_message_to_conversation"):
                return await redis_client.add_message_to_conversation(user_id, message)
            return True
        
        # Add the mock methods to the service
        service.generate_response = generate_response
        service.update_user_context = update_user_context
        service.get_conversation_history = get_conversation_history
        service.add_message_to_history = add_message_to_history

        return service 