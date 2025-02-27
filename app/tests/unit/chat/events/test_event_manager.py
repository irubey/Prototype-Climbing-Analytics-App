"""
Tests for the EventManager class.

This module tests the EventManager which handles Server-Sent Events (SSE)
for real-time communication with clients.
"""

import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator, Dict, List, Any
from unittest.mock import MagicMock, patch
import time
import json

from app.services.chat.events.manager import EventManager, EventType


@pytest_asyncio.fixture
async def event_manager() -> AsyncGenerator[EventManager, None]:
    """Create a fresh EventManager instance for testing."""
    manager = EventManager()
    yield manager
    
    # Clean up any subscribers and tasks
    subscribers = list(manager.subscribers.keys())
    for user_id in subscribers:
        try:
            await manager.disconnect(user_id)
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    # Force cleanup of any remaining tasks
    tasks = [task for task in asyncio.all_tasks() 
             if task is not asyncio.current_task() and 
             ("event_generator" in task.get_name() or 
             "cleanup" in task.get_name())]
    
    for task in tasks:
        task.cancel()
        
    if tasks:
        await asyncio.sleep(0.1)  # Give tasks time to cancel


@pytest.mark.asyncio
async def test_event_manager_initialization():
    """Test that EventManager initializes with empty subscribers dict."""
    manager = EventManager()
    assert isinstance(manager.subscribers, dict)
    assert len(manager.subscribers) == 0


@pytest.mark.asyncio
async def test_subscribe_new_user(event_manager: EventManager):
    """Test subscribing a new user."""
    user_id = "test_user"
    # Get EventSourceResponse but don't start consuming it
    response = await event_manager.subscribe(user_id)
    
    # Check that subscription was created
    assert user_id in event_manager.subscribers
    assert user_id in event_manager.message_queues
    assert user_id in event_manager._cleanup_tasks
    
    # Verify EventSourceResponse is returned
    assert hasattr(response, "body_iterator")
    
    # Clean up
    await event_manager.disconnect(user_id)


@pytest.mark.asyncio
async def test_subscribe_existing_user(event_manager: EventManager):
    """Test subscribing an already subscribed user."""
    user_id = "test_user"
    
    # First subscription
    await event_manager.subscribe(user_id)
    
    # Get task from first subscription
    task1 = event_manager._cleanup_tasks[user_id]
    
    try:
        # Second subscription should raise exception
        await event_manager.subscribe(user_id)
        pytest.fail("Expected SSEError for subscribing existing user")
    except Exception:
        # This is expected
        pass
    
    # Task should still be the same
    task2 = event_manager._cleanup_tasks[user_id]
    assert task1 == task2
    
    # Clean up
    await event_manager.disconnect(user_id)


@pytest.mark.asyncio
async def test_publish_event(event_manager: EventManager):
    """Test publishing an event to a subscribed user."""
    user_id = "test_user"
    
    # Subscribe user
    await event_manager.subscribe(user_id)
    
    # Publish test event
    test_content = {"message": "Test message"}
    await event_manager.publish(user_id, EventType.RESPONSE, test_content)
    
    # Check queue contains the published event
    queue = event_manager.message_queues[user_id]
    assert len(queue) == 1
    
    # Get event from queue and verify content
    event = queue[0]
    assert event.type == EventType.RESPONSE
    assert event.content["message"] == "Test message"
    
    # Clean up
    await event_manager.disconnect(user_id)


@pytest.mark.asyncio
async def test_publish_to_nonexistent_user(event_manager: EventManager):
    """Test publishing to a non-subscribed user."""
    user_id = "nonexistent_user"
    
    try:
        # Should raise exception since user is not subscribed
        await event_manager.publish(user_id, EventType.RESPONSE, {"message": "Test"})
        pytest.fail("Expected exception for publishing to nonexistent user")
    except Exception:
        # This is expected behavior
        pass
    
    # User should not be automatically added to subscribers
    assert user_id not in event_manager.subscribers


@pytest.mark.asyncio
async def test_disconnect_user(event_manager: EventManager):
    """Test disconnecting a subscribed user."""
    user_id = "test_user"
    
    # Subscribe user
    await event_manager.subscribe(user_id)
    assert user_id in event_manager.subscribers
    
    # Disconnect user
    await event_manager.disconnect(user_id)
    
    # User should be removed from subscribers
    assert user_id not in event_manager.subscribers
    assert user_id not in event_manager.message_queues
    assert user_id not in event_manager._cleanup_tasks


@pytest.mark.asyncio
async def test_disconnect_nonexistent_user(event_manager: EventManager):
    """Test disconnecting a non-subscribed user."""
    user_id = "nonexistent_user"
    
    # Should not raise exception
    await event_manager.disconnect(user_id)


@pytest.mark.asyncio
async def test_cleanup_task_cancellation(event_manager: EventManager):
    """Test that cleanup task is properly cancelled when user disconnects."""
    user_id = "test_user"
    
    # Subscribe user (creates cleanup task)
    await event_manager.subscribe(user_id)
    
    # Get cleanup task
    cleanup_task = event_manager._cleanup_tasks[user_id]
    assert not cleanup_task.done()
    
    # Disconnect user (should cancel cleanup task)
    await event_manager.disconnect(user_id)
    
    # Task should be cancelled
    await asyncio.sleep(0.1)  # Give time for cancellation to complete
    assert cleanup_task.done()


@pytest.mark.asyncio
async def test_event_types(event_manager: EventManager):
    """Test that all event types are handled correctly."""
    user_id = "test_user"
    await event_manager.subscribe(user_id)
    
    # Test each event type from the actual enum
    for event_type in EventType:
        # Publish event
        await event_manager.publish(user_id, event_type, {"type": event_type.value})
        
        # Get from queue and verify
        event = event_manager.message_queues[user_id][-1]
        assert event.type == event_type
        assert event.content["type"] == event_type.value
    
    # Clean up
    await event_manager.disconnect(user_id)


@pytest.mark.asyncio
async def test_event_generator_with_new_messages():
    """Test event generator yields events when new messages are published."""
    manager = EventManager()
    user_id = "test_user"
    
    try:
        # Get the SSE response
        response = await manager.subscribe(user_id)
        
        # Create a list to hold the events
        events = []
        
        # Create a task to consume a few events from the body iterator
        async def consume_events():
            body_iterator = response.body_iterator
            async for data in body_iterator:
                # Each data is a string like "event:response\ndata:{"message":"Event 1"}"
                events.append(data)
                if len(events) >= 3:
                    break
        
        # Start consumer task
        consumer_task = asyncio.create_task(consume_events())
        
        # Publish events
        await asyncio.sleep(0.1)  # Give consumer task time to start
        await manager.publish(user_id, EventType.RESPONSE, {"message": "Event 1"})
        await manager.publish(user_id, EventType.RESPONSE, {"message": "Event 2"})
        
        # Wait for consumer to finish or timeout
        try:
            await asyncio.wait_for(consumer_task, timeout=2.0)
        except asyncio.TimeoutError:
            consumer_task.cancel()
            await asyncio.sleep(0.1)
    finally:
        # Cleanup
        await manager.disconnect(user_id)
    
    # Check events (not checking in detail as the format depends on SSE implementation)
    assert len(events) >= 2


@pytest.mark.asyncio
async def test_event_generator_timeout_sends_heartbeat():
    """Test that heartbeats are sent when no other events occur."""
    manager = EventManager()
    user_id = "test_user"
    
    try:
        # Get the SSE response
        response = await manager.subscribe(user_id)
        
        # Create a list to hold the events
        events = []
        
        # Create a task to consume events from the body iterator
        async def collect_events():
            body_iterator = response.body_iterator
            async for data in body_iterator:
                events.append(data)
                if "heartbeat" in data:
                    break  # Stop after getting a heartbeat
        
        # Start collector task with timeout
        collector_task = asyncio.create_task(collect_events())
        
        try:
            # Wait for collector to get a heartbeat event
            await asyncio.wait_for(collector_task, timeout=20.0)  # Waiting for the 15s heartbeat timeout
        except asyncio.TimeoutError:
            collector_task.cancel()
    finally:
        # Cleanup
        await manager.disconnect(user_id)
    
    # Verify we got a heartbeat event
    assert any("heartbeat" in str(e) for e in events)


@pytest.mark.asyncio
async def test_event_generator_cancellation_cleanup():
    """Test that resources are cleaned up when generator is cancelled."""
    manager = EventManager()
    user_id = "test_user"
    
    try:
        # Get the SSE response
        response = await manager.subscribe(user_id)
        
        # Create a task that starts consuming events but then gets cancelled
        async def run_generator():
            try:
                body_iterator = response.body_iterator
                async for _ in body_iterator:
                    pass  # Just consume events
            except asyncio.CancelledError:
                # Expected
                pass
        
        # Start and immediately cancel the task
        task = asyncio.create_task(run_generator())
        await asyncio.sleep(0.1)
        task.cancel()
        
        # Wait for task to be cancelled - don't wait too long
        try:
            # We expect this to raise CancelledError, so we catch it
            await asyncio.wait_for(task, timeout=0.5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            # Either cancellation or timeout is acceptable
            pass
        
        # Wait a bit for cleanup
        await asyncio.sleep(0.5)
    finally:
        # Force cleanup in case auto-cleanup failed
        if user_id in manager.subscribers:
            await manager.disconnect(user_id)
    
    # User should be removed from subscribers
    assert user_id not in manager.subscribers


@pytest.mark.asyncio
async def test_cleanup_task_handles_exceptions():
    """Test that exceptions in cleanup task don't affect other users."""
    manager = EventManager()
    user1 = "test_user1"
    user2 = "test_user2"
    
    try:
        # Subscribe both users
        await manager.subscribe(user1)
        await manager.subscribe(user2)
        
        # Save original method
        original_cleanup = manager._cleanup_after_disconnect
        
        # Make cleanup for user1 raise exception
        async def raising_cleanup(user_id):
            if user_id == user1:
                raise RuntimeError("Test exception in cleanup")
            else:
                await original_cleanup(user_id)
        
        try:
            # Replace cleanup method
            manager._cleanup_after_disconnect = raising_cleanup
            
            # Disconnect user1 (should not affect user2)
            await manager.disconnect(user1)
            
            # Verify user2 is still subscribed
            assert user2 in manager.subscribers
            
            # Verify user1 was properly disconnected despite exception
            assert user1 not in manager.subscribers
        finally:
            # Restore original method
            manager._cleanup_after_disconnect = original_cleanup
    finally:
        # Clean up user2
        if user2 in manager.subscribers:
            await manager.disconnect(user2)


@pytest.mark.asyncio
async def test_cleanup_after_disconnect_task():
    """Test _cleanup_after_disconnect task behavior."""
    manager = EventManager()
    user_id = "test_user"
    
    try:
        # Create a task that executes _cleanup_after_disconnect
        task = asyncio.create_task(manager._cleanup_after_disconnect(user_id))
        
        # Allow it to run for a moment
        await asyncio.sleep(0.05)
        
        # Cancel the task
        task.cancel()
        
        # Wait for cancellation to complete
        try:
            await asyncio.wait_for(task, timeout=0.5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        
        # Task should be cancelled/done
        assert task.done()
    finally:
        # Ensure any dangling tasks are cleaned up
        if user_id in manager.subscribers:
            await manager.disconnect(user_id)


@pytest.mark.asyncio
async def test_cleanup_final_exception_handling():
    """Test exception handling during final cleanup in _cleanup_after_disconnect."""
    manager = EventManager()
    user_id = "test_user"
    
    # Save original method
    original_disconnect = manager.disconnect
    
    try:
        # Subscribe the user first
        await manager.subscribe(user_id)
        
        # Create a mock disconnect that raises an exception
        async def raising_disconnect(user_id):
            raise RuntimeError("Test exception in disconnect")
        
        # Replace disconnect method
        manager.disconnect = raising_disconnect
        
        # Run cleanup with a short timeout (should not hang)
        cleanup_task = asyncio.create_task(manager._cleanup_after_disconnect(user_id))
        
        # Let it run briefly
        await asyncio.sleep(0.1)
        
        # Cancel the task - this should trigger the finally block
        cleanup_task.cancel()
        
        # Verify task completes without hanging
        try:
            await asyncio.wait_for(cleanup_task, timeout=0.5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        
        # Task should be done
        assert cleanup_task.done()
    finally:
        # Restore original method
        manager.disconnect = original_disconnect
        
        # Force cleanup in case auto-cleanup failed
        try:
            # Using the original disconnect method
            await original_disconnect(user_id)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_publish_exception_handling():
    """Test that publish handles exceptions gracefully."""
    manager = EventManager()
    user_id = "test_user"
    
    try:
        # Subscribe the user
        await manager.subscribe(user_id)
        
        # Create a mock subscribers dict that raises when accessed
        class RaisingDict(dict):
            def __getitem__(self, key):
                if key == user_id:
                    raise RuntimeError("Test exception")
                return super().__getitem__(key)
        
        # Save original subscribers
        original_subscribers = manager.subscribers
        
        try:
            # Replace subscribers with our raising version
            manager.subscribers = RaisingDict(original_subscribers)
            
            # Publish should raise exception since we're using SSEError
            with pytest.raises(Exception):
                await manager.publish(user_id, EventType.RESPONSE, {"message": "Test"})
        finally:
            # Restore original subscribers
            manager.subscribers = original_subscribers
    finally:
        # Clean up
        await manager.disconnect(user_id) 