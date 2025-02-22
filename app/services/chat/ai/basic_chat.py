from datetime import datetime, UTC
import redis
from typing import Dict, Optional
import logging
from .model_client import Grok2Client
from ..context.orchestrator import ContextOrchestrator
from ..events.manager import EventManager, EventType
from app.core.config import settings

logger = logging.getLogger(__name__)

class ChatError(Exception):
    """Base exception for chat-related errors with error type and user message."""
    def __init__(self, message: str, error_type: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}
        self.user_message = message

class QuotaExceededError(ChatError):
    """Raised when user exceeds their monthly quota."""
    def __init__(self, current_usage: int, quota_limit: int):
        super().__init__(
            f"Monthly quota exceeded ({current_usage}/{quota_limit} requests). "
            "Upgrade to Premium for unlimited coaching!",
            "quota_exceeded",
            {"current_usage": current_usage, "quota_limit": quota_limit}
        )

class ModelError(ChatError):
    """Raised when the AI model encounters an error."""
    def __init__(self, original_error: str, status_code: Optional[int] = None):
        super().__init__(
            "Unable to generate response. Please try again in a moment.",
            "model_error",
            {"original_error": original_error, "status_code": status_code}
        )

class ContextError(ChatError):
    """Raised when there's an error fetching or processing context."""
    def __init__(self, original_error: str):
        super().__init__(
            "Unable to process your climbing context. Please try again.",
            "context_error",
            {"original_error": original_error}
        )

class BasicChatService:
    def __init__(
        self,
        context_manager: ContextOrchestrator,
        event_manager: EventManager,
        redis_client: redis.Redis,
        monthly_quota: int = 10
    ):
        self.context_manager = context_manager
        self.event_manager = event_manager
        self.redis = redis_client
        self.model = Grok2Client()
        self.monthly_quota = monthly_quota

    def _get_quota_key(self, user_id: str) -> str:
        """Generate Redis key for user's monthly quota."""
        current_month = datetime.now(UTC).strftime("%Y-%m")
        return f"chat:basic:quota:{user_id}:{current_month}"

    async def exceeds_quota(self, user_id: str) -> bool:
        """Check if user has exceeded their monthly quota."""
        try:
            quota_key = self._get_quota_key(user_id)
            current_usage = int(self.redis.get(quota_key) or 0)
            if current_usage >= self.monthly_quota:
                raise QuotaExceededError(current_usage, self.monthly_quota)
            return False
        except redis.RedisError as e:
            logger.error(f"Redis error checking quota: {str(e)}", exc_info=True)
            # Default to allowing the request if Redis fails
            return False

    async def _increment_quota(self, user_id: str):
        """Increment user's monthly quota usage with error handling."""
        try:
            quota_key = self._get_quota_key(user_id)
            pipe = self.redis.pipeline()
            pipe.incr(quota_key)
            pipe.expire(quota_key, 60 * 60 * 24 * 45)  # 45 days expiry
            pipe.execute()
        except redis.RedisError as e:
            logger.error(f"Failed to increment quota for user {user_id}: {str(e)}", exc_info=True)
            # Continue processing even if quota tracking fails
            pass

    async def _publish_error(self, user_id: str, error: ChatError):
        """Publish error event with structured error information."""
        await self.event_manager.publish(
            user_id,
            EventType.ERROR,
            {
                "error": error.user_message,
                "error_type": error.error_type,
                "details": error.details
            }
        )

    async def process(
        self,
        user_id: str,
        prompt: str,
        conversation_id: str
    ) -> Optional[str]:
        """Process a chat request for Basic tier users with enhanced error handling."""
        try:
            # Check quota with explicit error handling
            try:
                await self.exceeds_quota(user_id)
            except QuotaExceededError as e:
                await self._publish_error(user_id, e)
                return None

            # Notify processing start
            await self.event_manager.publish(
                user_id,
                EventType.PROCESSING,
                {"status": "Processing your request..."}
            )

            # Get context with error handling
            try:
                context = await self.context_manager.get_context(user_id, conversation_id)
            except Exception as e:
                context_error = ContextError(str(e))
                await self._publish_error(user_id, context_error)
                return None

            # Generate response with timing and error handling
            start_time = datetime.now(UTC)
            try:
                response = await self.model.generate_response(prompt, context)
            except Exception as e:
                model_error = ModelError(str(e))
                await self._publish_error(user_id, model_error)
                return None

            processing_time = (datetime.now(UTC) - start_time).total_seconds()

            # Increment quota only on successful response
            await self._increment_quota(user_id)

            # Publish successful response
            await self.event_manager.publish(
                user_id,
                EventType.RESPONSE,
                {
                    "text": response,
                    "request_info": {
                        "prompt_length": len(prompt),
                        "context_size": len(str(context))
                    }
                },
                processing_time
            )

            return response

        except Exception as e:
            logger.error(f"Unexpected error in chat processing: {str(e)}", exc_info=True)
            error = ChatError(
                "An unexpected error occurred. Our team has been notified.",
                "system_error",
                {"error_id": datetime.now(UTC).isoformat()}
            )
            await self._publish_error(user_id, error)
            return None
