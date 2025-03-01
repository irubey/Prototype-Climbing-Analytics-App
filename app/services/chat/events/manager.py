from typing import Dict, Optional
from collections import deque
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import asyncio
from datetime import datetime
import json
from uuid import uuid4
from dataclasses import dataclass, asdict
from enum import Enum
from app.core.exceptions import SSEError
from app.core.logging import logger

class EventType(Enum):
    PROCESSING = "processing"
    PARTIAL_RESPONSE = "partial_response"
    RESPONSE = "response"
    UPLOAD_PROCESSED = "upload_processed"
    VISUALIZATION_SUGGESTION = "visualization_suggestion"
    ERROR = "error"

@dataclass
class EventMetadata:
    timestamp: str
    response_length: int
    processing_time: float

@dataclass
class Event:
    type: EventType
    content: dict
    id: str
    metadata: EventMetadata

    def to_dict(self):
        return {
            "event": self.type.value,
            "data": json.dumps(self.content),
            "id": self.id,
            "metadata": asdict(self.metadata)
        }
    
    def to_sse_message(self):
        """Format event as an SSE message string"""
        event_dict = self.to_dict()
        lines = [
            f"event: {event_dict['event']}",
            f"id: {event_dict['id']}",
            f"data: {event_dict['data']}"
        ]
        return "\n".join(lines) + "\n\n"

class EventManager:
    def __init__(self):
        """Initialize the EventManager with storage for subscribers and message queues."""
        self.subscribers: Dict[str, asyncio.Event] = {}
        self.message_queues: Dict[str, deque[Event]] = {}
        self._cleanup_tasks: Dict[str, asyncio.Task] = {}
        self._connection_tasks: Dict[str, asyncio.Task] = {}

    async def subscribe(self, user_id: str, request: Request = None) -> StreamingResponse:
        """
        Subscribe a user to receive SSE events.
        
        Args:
            user_id: The unique identifier for the user
            request: The FastAPI request object (used for disconnect detection)
            
        Returns:
            StreamingResponse: A stream of SSE events for the user
            
        Raises:
            SSEError: If subscription fails
        """
        try:
            # If user is already subscribed, clean up the existing subscription first
            if user_id in self.subscribers:
                logger.info(f"User {user_id} reconnecting - cleaning up previous session", 
                           extra={"user_id": user_id})
                await self.disconnect(user_id)
                
                # Small delay to ensure cleanup is complete
                await asyncio.sleep(0.1)

            # Create new subscription
            self.subscribers[user_id] = asyncio.Event()
            self.message_queues[user_id] = deque()
            
            # Start cleanup task
            self._cleanup_tasks[user_id] = asyncio.create_task(
                self._cleanup_after_disconnect(user_id)
            )
            
            logger.info(f"User {user_id} subscribed to SSE", extra={"user_id": user_id})

            async def event_generator():
                """Native async generator for SSE events - works better with Python 3.12"""
                try:
                    # Send initial connection established event
                    yield "event: connected\ndata: {\"status\":\"connected\"}\n\n"
                    
                    while user_id in self.subscribers:
                        # Check if client is still connected (if request object provided)
                        if request and await request.is_disconnected():
                            logger.info(f"Client disconnected detected for user {user_id}", 
                                       extra={"user_id": user_id})
                            break
                            
                        # Wait for new messages with timeout
                        try:
                            await asyncio.wait_for(
                                self.subscribers[user_id].wait(),
                                timeout=15.0  # 15 second timeout
                            )
                        except asyncio.TimeoutError:
                            # Send heartbeat on timeout
                            yield "event: heartbeat\ndata: \n\n"
                            continue
                        except asyncio.CancelledError:
                            logger.debug(f"Event generator cancelled for user {user_id}", 
                                        extra={"user_id": user_id})
                            break
                        
                        # Process any messages in the queue
                        while self.message_queues.get(user_id, []):
                            event = self.message_queues[user_id].popleft()
                            yield event.to_sse_message()
                        
                        # Clear the event flag once all messages are processed
                        if user_id in self.subscribers:
                            self.subscribers[user_id].clear()
                except Exception as e:
                    logger.error(f"SSE event generation error for user {user_id}", 
                                exc_info=e, extra={"user_id": user_id})
                finally:
                    # Ensure cleanup happens when the generator exits
                    logger.debug(f"Event generator completed for user {user_id}", 
                                extra={"user_id": user_id})
                    # Create task to avoid blocking the generator return
                    asyncio.create_task(self.disconnect(user_id))
            
            # Store connection in a task so we can track it
            gen = event_generator()
            
            # Create a StreamingResponse with appropriate SSE headers
            return StreamingResponse(
                gen,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
            
        except Exception as e:
            logger.error(f"SSE subscription error for user {user_id}", exc_info=e)
            if not isinstance(e, SSEError):
                e = SSEError(
                    detail=f"Subscription failed: {str(e)}",
                    context={"error": str(e), "user_id": user_id}
                )
            raise e

    async def publish(
        self, 
        user_id: str, 
        event_type: EventType, 
        content: dict, 
        processing_time: float = 0.0
    ) -> None:
        """
        Publish an event to a specific user's event stream.
        
        Args:
            user_id: The unique identifier for the user
            event_type: The type of event to publish
            content: The event content
            processing_time: The time taken to process the event
            
        Raises:
            SSEError: If publishing fails or user is not subscribed
        """
        try:
            if user_id not in self.subscribers:
                raise SSEError(
                    detail="User not subscribed",
                    context={"connection_state": "not_connected", "user_id": user_id}
                )

            metadata = EventMetadata(
                timestamp=datetime.utcnow().isoformat(),
                response_length=len(json.dumps(content)),
                processing_time=processing_time
            )
            
            event = Event(
                type=event_type,
                content=content,
                id=str(uuid4()),
                metadata=metadata
            )
            
            self.message_queues[user_id].append(event)
            self.subscribers[user_id].set()
            
            logger.debug(
                f"Event published for user {user_id}",
                extra={
                    "event_type": event_type.value,
                    "queue_size": len(self.message_queues[user_id])
                }
            )
            
        except Exception as e:
            logger.error(f"SSE publish error for user {user_id}", exc_info=e)
            if not isinstance(e, SSEError):
                e = SSEError(
                    detail=f"Event publishing failed: {str(e)}",
                    context={
                        "error": str(e),
                        "user_id": user_id,
                        "event_type": event_type.value if isinstance(event_type, EventType) else None
                    }
                )
            raise e

    async def disconnect(self, user_id: str) -> None:
        """
        Disconnect a user and cleanup their resources.
        
        Args:
            user_id: The unique identifier for the user
            
        Raises:
            SSEError: If cleanup fails
        """
        try:
            if user_id not in self.subscribers:
                return  # Silently return if user is not subscribed

            logger.info(f"Disconnecting user {user_id} from SSE", extra={"user_id": user_id})

            # Remove message queue first to prevent race conditions
            self.message_queues.pop(user_id, None)

            # Get cleanup task and subscriber event
            cleanup_task = self._cleanup_tasks.pop(user_id, None)
            subscriber = self.subscribers.pop(user_id, None)
            
            # Connection task if exists
            connection_task = self._connection_tasks.pop(user_id, None)
            if connection_task:
                connection_task.cancel()

            # Cancel cleanup task if it exists
            if cleanup_task:
                cleanup_task.cancel()
                try:
                    await asyncio.shield(asyncio.wait_for(cleanup_task, timeout=0.5))
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

            # Wake up any waiting generators
            if subscriber:
                subscriber.set()
            
            logger.info(f"User {user_id} disconnected from SSE", extra={"user_id": user_id})
            
        except Exception as e:
            logger.error(f"SSE disconnect error for user {user_id}", exc_info=e)
            # Don't raise an exception here, just log it
            # This prevents cascading failures during cleanup

    async def _cleanup_after_disconnect(self, user_id: str) -> None:
        """
        Cleanup task that monitors for disconnected clients.
        
        Args:
            user_id: The unique identifier for the user
        """
        try:
            while True:
                try:
                    await asyncio.sleep(30)  # Check every 30 seconds
                    if user_id not in self.subscribers:
                        logger.debug(f"Cleanup task detected disconnected user {user_id}", extra={"user_id": user_id})
                        break
                except asyncio.CancelledError:
                    logger.debug(f"Cleanup task cancelled for user {user_id}", extra={"user_id": user_id})
                    break
        except Exception as e:
            logger.error(f"SSE cleanup error for user {user_id}", exc_info=e, extra={"user_id": user_id})
        finally:
            try:
                # Ensure we're still in a valid state before attempting disconnect
                if user_id in self.subscribers:
                    await self.disconnect(user_id)
                else:
                    # Just clean up any remaining resources
                    if user_id in self.message_queues:
                        del self.message_queues[user_id]
                    if user_id in self._cleanup_tasks:
                        self._cleanup_tasks.pop(user_id, None)
            except Exception as e:
                logger.error(f"Final cleanup error for user {user_id}", exc_info=e, extra={"user_id": user_id})
