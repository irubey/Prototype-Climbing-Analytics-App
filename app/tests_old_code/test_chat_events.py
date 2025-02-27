import pytest
import pytest_asyncio
import asyncio
import json
import time
import gc
from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import patch, MagicMock, AsyncMock
from sse_starlette.sse import EventSourceResponse
from app.services.chat.events.manager import EventManager, EventType, Event, EventMetadata
from app.core.exceptions import SSEError
from app.core.logging import logger
from contextlib import aclosing
from fastapi import BackgroundTasks, HTTPException

@pytest_asyncio.fixture
async def event_manager() -> AsyncGenerator[EventManager, None]:
    """Create a fresh EventManager instance for each test."""
    manager = EventManager()
    yield manager
    # Cleanup any remaining subscribers and tasks
    for user_id in list(manager.subscribers.keys()):
        await manager.disconnect(user_id)
    # Force cleanup of any remaining tasks
    await asyncio.sleep(0.1)

@pytest.mark.asyncio
async def test_event_manager_initialization():
    """Test that EventManager initializes with empty state."""
    manager = EventManager()
    assert isinstance(manager.subscribers, dict)
    assert isinstance(manager.message_queues, dict)
    assert isinstance(manager._cleanup_tasks, dict)
    assert len(manager.subscribers) == 0
    assert len(manager.message_queues) == 0
    assert len(manager._cleanup_tasks) == 0

@pytest.mark.asyncio
async def test_subscribe_new_user(event_manager: EventManager):
    """Test subscribing a new user creates necessary resources."""
    user_id = "test_user"
    response = await event_manager.subscribe(user_id)
    
    assert isinstance(response, EventSourceResponse)
    assert user_id in event_manager.subscribers
    assert user_id in event_manager.message_queues
    assert user_id in event_manager._cleanup_tasks
    assert len(event_manager.message_queues[user_id]) == 0
    
    # Cleanup
    await event_manager.disconnect(user_id)

@pytest.mark.asyncio
async def test_subscribe_existing_user(event_manager: EventManager):
    """Test subscribing an already subscribed user raises SSEError."""
    user_id = "test_user"
    await event_manager.subscribe(user_id)
    
    with pytest.raises(SSEError) as exc_info:
        await event_manager.subscribe(user_id)
    
    assert "User already subscribed" in str(exc_info.value)
    assert exc_info.value.context.get("connection_state") == "already_connected"

@pytest.mark.asyncio
async def test_publish_event(event_manager: EventManager):
    """Test publishing an event to a subscribed user."""
    user_id = "test_user"
    await event_manager.subscribe(user_id)
    
    test_content = {"message": "test message"}
    await event_manager.publish(
        user_id=user_id,
        event_type=EventType.PROCESSING,
        content=test_content,
        processing_time=0.1
    )
    
    assert len(event_manager.message_queues[user_id]) == 1
    event = event_manager.message_queues[user_id][0]
    assert isinstance(event, Event)
    assert event.type == EventType.PROCESSING
    assert event.content == test_content
    assert isinstance(event.metadata, EventMetadata)
    assert event.metadata.processing_time == 0.1

@pytest.mark.asyncio
async def test_publish_to_nonexistent_user(event_manager: EventManager):
    """Test publishing to a non-subscribed user raises SSEError."""
    with pytest.raises(SSEError) as exc_info:
        await event_manager.publish(
            user_id="nonexistent_user",
            event_type=EventType.PROCESSING,
            content={"message": "test"},
            processing_time=0.1
        )
    
    assert "User not subscribed" in str(exc_info.value)
    assert exc_info.value.context.get("connection_state") == "not_connected"

@pytest.mark.asyncio
async def test_disconnect_user(event_manager: EventManager):
    """Test disconnecting a user cleans up all resources."""
    user_id = "test_user"
    await event_manager.subscribe(user_id)
    await event_manager.disconnect(user_id)
    
    assert user_id not in event_manager.subscribers
    assert user_id not in event_manager.message_queues
    assert user_id not in event_manager._cleanup_tasks

@pytest.mark.asyncio
async def test_disconnect_nonexistent_user(event_manager: EventManager):
    """Test disconnecting a non-subscribed user returns silently."""
    await event_manager.disconnect("nonexistent_user")
    # Should not raise any exceptions

@pytest.mark.asyncio
async def test_event_metadata(event_manager: EventManager):
    """Test event metadata is correctly generated."""
    user_id = "test_user"
    await event_manager.subscribe(user_id)
    
    test_content = {"message": "test"}
    processing_time = 0.1
    
    await event_manager.publish(
        user_id=user_id,
        event_type=EventType.RESPONSE,
        content=test_content,
        processing_time=processing_time
    )
    
    event = event_manager.message_queues[user_id][0]
    assert isinstance(event.metadata.timestamp, str)
    # Verify timestamp is in ISO format
    datetime.fromisoformat(event.metadata.timestamp)
    assert event.metadata.response_length == len(json.dumps(test_content))
    assert event.metadata.processing_time == processing_time

@pytest.mark.asyncio
async def test_event_types(event_manager: EventManager):
    """Test all event types are handled correctly."""
    user_id = "test_user"
    await event_manager.subscribe(user_id)
    
    for event_type in EventType:
        await event_manager.publish(
            user_id=user_id,
            event_type=event_type,
            content={"type": event_type.value},
            processing_time=0.1
        )
    
    assert len(event_manager.message_queues[user_id]) == len(EventType)
    for i, event_type in enumerate(EventType):
        assert event_manager.message_queues[user_id][i].type == event_type

@pytest.mark.asyncio
async def test_event_serialization(event_manager: EventManager):
    """Test events are correctly serialized to dict format."""
    user_id = "test_user"
    await event_manager.subscribe(user_id)
    
    test_content = {"message": "test"}
    await event_manager.publish(
        user_id=user_id,
        event_type=EventType.RESPONSE,
        content=test_content
    )
    
    event = event_manager.message_queues[user_id][0]
    event_dict = event.to_dict()
    
    assert isinstance(event_dict, dict)
    assert event_dict["event"] == EventType.RESPONSE.value
    assert json.loads(event_dict["data"]) == test_content
    assert isinstance(event_dict["id"], str)
    assert isinstance(event_dict["metadata"], dict)
    assert all(key in event_dict["metadata"] for key in ["timestamp", "response_length", "processing_time"])

@pytest.mark.asyncio
async def test_cleanup_task_cancellation(event_manager: EventManager):
    """Test cleanup tasks are properly cancelled on disconnect."""
    user_id = "test_user"
    await event_manager.subscribe(user_id)
    
    cleanup_task = event_manager._cleanup_tasks[user_id]
    assert not cleanup_task.done()
    
    await event_manager.disconnect(user_id)
    await asyncio.sleep(0.1)  # Give task time to cancel
    
    assert cleanup_task.cancelled() or cleanup_task.done()

@pytest.mark.asyncio
async def test_multiple_subscribers(event_manager: EventManager):
    """Test handling multiple subscribers correctly."""
    user_ids = ["user1", "user2", "user3"]
    
    # Subscribe multiple users
    for user_id in user_ids:
        await event_manager.subscribe(user_id)
    
    # Publish to each user
    for user_id in user_ids:
        await event_manager.publish(
            user_id=user_id,
            event_type=EventType.PROCESSING,
            content={"message": f"test for {user_id}"}
        )
    
    # Verify each user's queue
    for user_id in user_ids:
        assert len(event_manager.message_queues[user_id]) == 1
        assert event_manager.message_queues[user_id][0].content["message"] == f"test for {user_id}"

@pytest.mark.asyncio
async def test_event_generator_cancellation(event_manager: EventManager):
    """Test event generator handles cancellation correctly."""
    user_id = "test_user"
    response = await event_manager.subscribe(user_id)
    
    # Mock the event generator
    generator = response.body_iterator
    
    # Simulate cancellation using aclosing
    async with aclosing(generator):
        try:
            # Force cancel the generator task
            task = asyncio.current_task()
            task.cancel()
            # The aclosing context manager will handle cleanup
        except asyncio.CancelledError:
            pass  # Expected
    
    # Explicitly disconnect after cancellation
    await event_manager.disconnect(user_id)
    
    # Verify cleanup occurred - use synchronous checks since they can't be cancelled
    try:
        # Check cleanup state directly
        cleanup_successful = (
            user_id not in event_manager.subscribers and
            user_id not in event_manager.message_queues and
            user_id not in event_manager._cleanup_tasks
        )
        
        if not cleanup_successful:
            # Log state if verification fails
            logger.error(
                "Cleanup verification failed",
                extra={
                    "user_id": user_id,
                    "subscribers": list(event_manager.subscribers.keys()),
                    "message_queues": list(event_manager.message_queues.keys()),
                    "cleanup_tasks": list(event_manager._cleanup_tasks.keys())
                }
            )
            
        # Assert after logging for better error messages
        assert user_id not in event_manager.subscribers, "User still in subscribers"
        assert user_id not in event_manager.message_queues, "User still in message queues"
        assert user_id not in event_manager._cleanup_tasks, "User still in cleanup tasks"
    except AssertionError as e:
        raise AssertionError(f"Cleanup verification failed: {str(e)}")

@pytest.mark.asyncio
async def test_cleanup_task_exception_handling(event_manager: EventManager):
    """Test cleanup task handles exceptions gracefully."""
    user_id = "test_user"
    await event_manager.subscribe(user_id)
    
    # Force an exception in the cleanup task
    cleanup_task = event_manager._cleanup_tasks[user_id]
    cleanup_task.cancel()
    
    # Explicitly disconnect to trigger cleanup
    await event_manager.disconnect(user_id)
    
    # Verify cleanup completed
    assert user_id not in event_manager.subscribers
    assert user_id not in event_manager.message_queues
    assert user_id not in event_manager._cleanup_tasks

@pytest.mark.asyncio
async def test_logging_on_operations(event_manager: EventManager, caplog):
    """Test that all operations are properly logged."""
    import logging
    from io import StringIO
    
    # Create a string buffer to capture logs
    log_output = StringIO()
    
    # Add a test handler to the pre-configured logger
    test_handler_id = logger.add(
        log_output,
        level="DEBUG"
    )
    
    try:
        user_id = "test_user"
        
        # Perform operations
        await event_manager.subscribe(user_id)
        await event_manager.publish(
            user_id=user_id,
            event_type=EventType.PROCESSING,
            content={"message": "test"}
        )
        await event_manager.disconnect(user_id)
        
        # Get captured logs
        log_messages = log_output.getvalue().splitlines()
        
        # Verify the expected operations were logged
        subscribe_found = False
        publish_found = False
        disconnect_found = False
        
        for msg in log_messages:
            if "User test_user subscribed to SSE" in msg:
                subscribe_found = True
            elif "Event published for user test_user" in msg:
                publish_found = True
            elif "User test_user disconnected from SSE" in msg:
                disconnect_found = True
        
        assert subscribe_found, "Subscribe log not found"
        assert publish_found, "Publish log not found"
        assert disconnect_found, "Disconnect log not found"
        
    finally:
        # Clean up our test handler
        logger.remove(test_handler_id)

@pytest.mark.asyncio
async def test_error_context_in_exceptions(event_manager: EventManager):
    """Test that exceptions contain appropriate context."""
    user_id = "test_user"
    
    # Test subscribe error context
    await event_manager.subscribe(user_id)
    try:
        await event_manager.subscribe(user_id)
    except SSEError as e:
        assert e.context.get("user_id") == user_id
        assert e.context.get("connection_state") == "already_connected"
    
    # Test publish error context
    try:
        await event_manager.publish(
            user_id="nonexistent_user",
            event_type=EventType.PROCESSING,
            content={"message": "test"}
        )
    except SSEError as e:
        assert e.context.get("user_id") == "nonexistent_user"
        assert e.context.get("connection_state") == "not_connected"

@pytest.mark.asyncio
async def test_heartbeat_mechanism(event_manager: EventManager):
    """Test that heartbeat events are generated correctly."""
    user_id = "test_user"
    response = await event_manager.subscribe(user_id)
    
    # Get the event generator
    generator = response.body_iterator
    
    # Wait for heartbeat (should come after 15s timeout)
    event = await anext(generator)
    assert event["event"] == "heartbeat"
    assert event["data"] == ""
    
    # Publish an event to verify normal operation
    await event_manager.publish(
        user_id=user_id,
        event_type=EventType.PROCESSING,
        content={"message": "test"}
    )
    
    # Get the published event
    event = await anext(generator)
    assert event["event"] == EventType.PROCESSING.value
    assert json.loads(event["data"]) == {"message": "test"}
    
    # Cleanup
    await event_manager.disconnect(user_id)

@pytest.mark.asyncio
async def test_concurrent_operations(event_manager: EventManager):
    """Test concurrent subscribe and publish operations."""
    user_ids = [f"user_{i}" for i in range(100)]
    
    async def subscribe_and_publish(user_id: str):
        await event_manager.subscribe(user_id)
        await event_manager.publish(
            user_id=user_id,
            event_type=EventType.PROCESSING,
            content={"message": f"test for {user_id}"}
        )
        
    # Execute concurrent operations
    await asyncio.gather(
        *(subscribe_and_publish(user_id) for user_id in user_ids)
    )
    
    # Verify all operations completed successfully
    for user_id in user_ids:
        assert user_id in event_manager.subscribers
        assert len(event_manager.message_queues[user_id]) == 1
        assert event_manager.message_queues[user_id][0].content["message"] == f"test for {user_id}"

@pytest.mark.asyncio
async def test_memory_cleanup(event_manager: EventManager):
    """Test memory is properly cleaned up after disconnections."""
    user_id = "test_user"
    
    # Get initial memory state
    gc.collect()
    initial_objects = len(gc.get_objects())
    
    # Perform operations
    await event_manager.subscribe(user_id)
    for _ in range(10):
        await event_manager.publish(
            user_id=user_id,
            event_type=EventType.PROCESSING,
            content={"message": "test"}
        )
    await event_manager.disconnect(user_id)
    
    # Force garbage collection and wait for cleanup
    await asyncio.sleep(0.2)
    gc.collect()
    gc.collect()  # Double collection to ensure cleanup
    final_objects = len(gc.get_objects())
    
    # Verify no significant memory growth (increased threshold for test stability)
    assert abs(final_objects - initial_objects) < 50  # Allow more variation

@pytest.mark.asyncio
async def test_queue_performance(event_manager: EventManager):
    """Test performance of queue operations."""
    user_id = "test_user"
    await event_manager.subscribe(user_id)
    
    start_time = time.perf_counter()
    
    # Publish 1000 events
    for i in range(1000):
        await event_manager.publish(
            user_id=user_id,
            event_type=EventType.PROCESSING,
            content={"message": f"test_{i}"}
        )
    
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    # Verify performance (should be under 1 second for 1000 events)
    assert duration < 1.0
    assert len(event_manager.message_queues[user_id]) == 1000

@pytest.mark.asyncio
async def test_event_ordering(event_manager: EventManager):
    """Test events are delivered in the correct order."""
    user_id = "test_user"
    await event_manager.subscribe(user_id)
    
    # Publish events with sequence numbers
    event_count = 100
    for i in range(event_count):
        await event_manager.publish(
            user_id=user_id,
            event_type=EventType.PROCESSING,
            content={"sequence": i}
        )
    
    # Verify order
    for i, event in enumerate(event_manager.message_queues[user_id]):
        assert event.content["sequence"] == i

@pytest.mark.asyncio
async def test_reconnection_handling(event_manager: EventManager):
    """Test handling of user reconnection after disconnect."""
    user_id = "test_user"
    
    # Initial connection
    await event_manager.subscribe(user_id)
    await event_manager.publish(
        user_id=user_id,
        event_type=EventType.PROCESSING,
        content={"message": "first"}
    )
    
    # Simulate disconnect
    await event_manager.disconnect(user_id)
    
    # Reconnect
    await event_manager.subscribe(user_id)
    await event_manager.publish(
        user_id=user_id,
        event_type=EventType.PROCESSING,
        content={"message": "second"}
    )
    
    assert len(event_manager.message_queues[user_id]) == 1
    assert event_manager.message_queues[user_id][0].content["message"] == "second"

@pytest.mark.asyncio
async def test_large_message_handling(event_manager: EventManager):
    """Test handling of large messages."""
    user_id = "test_user"
    await event_manager.subscribe(user_id)
    
    # Create a large message (1MB)
    large_content = {
        "data": "x" * (1024 * 1024)  # 1MB of data
    }
    
    await event_manager.publish(
        user_id=user_id,
        event_type=EventType.PROCESSING,
        content=large_content
    )
    
    event = event_manager.message_queues[user_id][0]
    assert len(json.dumps(event.content)) >= 1024 * 1024
    assert event.metadata.response_length >= 1024 * 1024

@pytest.mark.asyncio
async def test_stress_cleanup_tasks(event_manager: EventManager):
    """Test cleanup tasks under stress conditions."""
    user_count = 100
    user_ids = [f"user_{i}" for i in range(user_count)]
    
    # Subscribe all users
    await asyncio.gather(*(event_manager.subscribe(user_id) for user_id in user_ids))
    
    # Mock sleep to speed up cleanup checks but preserve some delay
    async def mock_sleep(*args, **kwargs):
        await asyncio.sleep(0.01)  # Small actual delay to prevent tight loops
    
    with patch('asyncio.sleep', side_effect=mock_sleep):
        try:
            # Disconnect half the users concurrently
            await asyncio.gather(*(
                event_manager.disconnect(user_id) for user_id in user_ids[:50]
            ))
            
            # Wait for cleanup to complete with timeout
            async with asyncio.timeout(5.0):  # Increased timeout for stability
                while True:
                    subscriber_count = len(event_manager.subscribers)
                    if subscriber_count == 50:
                        break
                    if subscriber_count < 50:
                        raise RuntimeError(f"Too few subscribers: {subscriber_count}")
                    await asyncio.sleep(0.05)
            
            # Verify final state
            assert len(event_manager.subscribers) == 50
            assert len(event_manager._cleanup_tasks) == 50
            assert len(event_manager.message_queues) == 50
            
            # Verify exactly which users remain
            remaining_users = set(user_ids[50:])
            assert set(event_manager.subscribers.keys()) == remaining_users
            assert set(event_manager._cleanup_tasks.keys()) == remaining_users
            assert set(event_manager.message_queues.keys()) == remaining_users
            
        except asyncio.TimeoutError:
            # Add diagnostic information if timeout occurs
            logger.error(
                "Stress test timeout",
                extra={
                    "subscribers": len(event_manager.subscribers),
                    "cleanup_tasks": len(event_manager._cleanup_tasks),
                    "message_queues": len(event_manager.message_queues),
                    "remaining_users": list(event_manager.subscribers.keys())
                }
            )
            raise 

@pytest_asyncio.fixture
async def mock_basic_chat_service():
    service = AsyncMock()
    service.exceeds_quota.return_value = False
    service.process.return_value = "Test response"
    return service

@pytest_asyncio.fixture
async def mock_premium_chat_service():
    service = AsyncMock()
    service.process.return_value = "Test response"
    return service

@pytest.mark.asyncio
async def test_endpoint_integration(
    event_manager: EventManager,
    mock_basic_chat_service: AsyncMock,
    mock_premium_chat_service: AsyncMock
):
    """Test integration between endpoints and event system."""
    from app.api.v1.endpoints.chat import stream_events, basic_chat_endpoint, premium_chat_endpoint
    from fastapi import BackgroundTasks
    
    user_id = "test_user"
    conversation_id = "test_conv"
    
    # Test stream endpoint with event system
    current_user = {"id": user_id, "tier": "basic"}
    with patch("app.api.v1.endpoints.chat.event_manager", event_manager):
        stream_response = await stream_events(current_user=current_user)
        assert isinstance(stream_response, EventSourceResponse)
        
        # Subscribe to events
        await event_manager.subscribe(current_user["id"])
        
        # Test basic chat endpoint integration
        background_tasks = BackgroundTasks()
        with patch("app.api.v1.endpoints.chat.get_basic_chat_service", return_value=mock_basic_chat_service):
            chat_response = await basic_chat_endpoint(
                prompt="Test query",
                conversation_id=conversation_id,
                background_tasks=background_tasks,
                current_user=current_user,
                chat_service=mock_basic_chat_service
            )
            assert chat_response == {"status": "processing"}
        
        # Verify events in queue
        assert len(event_manager.message_queues[user_id]) >= 1
        processing_event = event_manager.message_queues[user_id][0]
        assert processing_event.type == EventType.PROCESSING
        assert "Processing" in processing_event.content["status"]

@pytest.mark.asyncio
async def test_endpoint_error_propagation(
    event_manager: EventManager,
    mock_basic_chat_service: AsyncMock
):
    """Test error propagation from endpoints to event system."""
    from app.api.v1.endpoints.chat import stream_events, basic_chat_endpoint
    from fastapi import BackgroundTasks
    
    user_id = "test_user"
    current_user = {"id": user_id, "tier": "basic"}
    
    # Subscribe to events
    with patch("app.api.v1.endpoints.chat.event_manager", event_manager):
        stream_response = await stream_events(current_user=current_user)
        await event_manager.subscribe(current_user["id"])
        
        # Force an error in the chat process
        mock_basic_chat_service.process.side_effect = Exception("Test error")
        
        background_tasks = BackgroundTasks()
        with patch("app.api.v1.endpoints.chat.get_basic_chat_service", return_value=mock_basic_chat_service):
            with pytest.raises(HTTPException):
                await basic_chat_endpoint(
                    prompt="Test query",
                    conversation_id="test_conv",
                    background_tasks=background_tasks,
                    current_user=current_user,
                    chat_service=mock_basic_chat_service
                )
        
        # Verify error event was published
        error_events = [
            event for event in event_manager.message_queues[user_id]
            if event.type == EventType.ERROR
        ]
        assert len(error_events) == 1
        assert "Test error" in error_events[0].content["error"]

@pytest.mark.asyncio
async def test_endpoint_file_handling(
    event_manager: EventManager,
    mock_premium_chat_service: AsyncMock
):
    """Test file handling in premium endpoint with event system."""
    from app.api.v1.endpoints.chat import stream_events, premium_chat_endpoint
    from fastapi import BackgroundTasks, UploadFile
    import io
    
    user_id = "premium_user"
    current_user = {"id": user_id, "tier": "premium"}
    
    # Subscribe to events
    with patch("app.api.v1.endpoints.chat.event_manager", event_manager):
        stream_response = await stream_events(current_user=current_user)
        await event_manager.subscribe(current_user["id"])
        
        # Create a mock file
        file_content = b"date,grade\n2024-02-20,V4"
        mock_file = UploadFile(
            filename="test.csv",
            file=io.BytesIO(file_content)
        )
        
        background_tasks = BackgroundTasks()
        with patch("app.api.v1.endpoints.chat.get_premium_chat_service", return_value=mock_premium_chat_service):
            response = await premium_chat_endpoint(
                prompt="Analyze my progress",
                conversation_id="test_conv",
                background_tasks=background_tasks,
                file=mock_file,
                current_user=current_user,
                chat_service=mock_premium_chat_service
            )
            
            assert response == {"status": "processing"}
            assert mock_premium_chat_service.process.called
            
        # Verify events
        events = event_manager.message_queues[user_id]
        assert len(events) >= 1
        assert any(event.type == EventType.PROCESSING for event in events)

@pytest.mark.asyncio
async def test_endpoint_concurrent_users(
    event_manager: EventManager,
    mock_basic_chat_service: AsyncMock
):
    """Test multiple users accessing endpoints concurrently."""
    from app.api.v1.endpoints.chat import stream_events, basic_chat_endpoint
    from fastapi import BackgroundTasks
    
    user_count = 5
    users = [{"id": f"user_{i}", "tier": "basic"} for i in range(user_count)]
    
    async def user_session(user):
        # Subscribe to events
        with patch("app.api.v1.endpoints.chat.event_manager", event_manager):
            stream_response = await stream_events(current_user=user)
            await event_manager.subscribe(user["id"])
            
            # Send chat request
            background_tasks = BackgroundTasks()
            with patch("app.api.v1.endpoints.chat.get_basic_chat_service", return_value=mock_basic_chat_service):
                chat_response = await basic_chat_endpoint(
                    prompt="Test query",
                    conversation_id=f"conv_{user['id']}",
                    background_tasks=background_tasks,
                    current_user=user,
                    chat_service=mock_basic_chat_service
                )
                assert chat_response == {"status": "processing"}
            
            # Verify user's events
            assert len(event_manager.message_queues[user["id"]]) >= 1
    
    # Run concurrent user sessions
    await asyncio.gather(*(user_session(user) for user in users))
    
    # Verify all users have events
    for user in users:
        assert user["id"] in event_manager.message_queues
        assert len(event_manager.message_queues[user["id"]]) >= 1

@pytest.mark.asyncio
async def test_endpoint_cleanup_on_error(
    event_manager: EventManager,
    mock_basic_chat_service: AsyncMock
):
    """Test proper cleanup when endpoints encounter errors."""
    from app.api.v1.endpoints.chat import stream_events, basic_chat_endpoint
    from fastapi import BackgroundTasks
    
    user_id = "test_user"
    current_user = {"id": user_id, "tier": "basic"}
    
    # Subscribe to events
    with patch("app.api.v1.endpoints.chat.event_manager", event_manager):
        stream_response = await stream_events(current_user=current_user)
        await event_manager.subscribe(current_user["id"])
        
        # Force an error in the chat process
        mock_basic_chat_service.process.side_effect = Exception("Catastrophic error")
        
        background_tasks = BackgroundTasks()
        with patch("app.api.v1.endpoints.chat.get_basic_chat_service", return_value=mock_basic_chat_service):
            with pytest.raises(HTTPException):
                await basic_chat_endpoint(
                    prompt="Test query",
                    conversation_id="test_conv",
                    background_tasks=background_tasks,
                    current_user=current_user,
                    chat_service=mock_basic_chat_service
                )
        
        # Verify error handling and cleanup
        assert user_id in event_manager.subscribers  # User should still be subscribed
        error_events = [
            event for event in event_manager.message_queues[user_id]
            if event.type == EventType.ERROR
        ]
        assert len(error_events) == 1
        assert "Catastrophic error" in error_events[0].content["error"]
        
        # Disconnect and verify cleanup
        await event_manager.disconnect(user_id)
        assert user_id not in event_manager.subscribers
        assert user_id not in event_manager.message_queues 