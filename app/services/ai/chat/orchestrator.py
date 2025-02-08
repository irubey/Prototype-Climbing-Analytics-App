# Coordinates the overall chat flow:
# - Routes queries to conversational/evaluation modules
# - Merges outputs from the advanced reasoning module when needed

from typing import Dict, Any, Optional, Tuple
import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from functools import wraps

from ..model_wrappers.v3_client import DeepseekV3Client
from ..model_wrappers.r1_client import R1Client
from app.services.context.context_formatter import ContextFormatter
from app.services.context.data_integrator import DataIntegrator
from app.models import User

# Configure logging
logger = logging.getLogger(__name__)

class ChatError(Exception):
    """Base exception class for chat-related errors"""
    def __init__(self, message: str, error_type: str, details: Optional[Dict] = None):
        self.message = message
        self.error_type = error_type
        self.details = details or {}
        super().__init__(self.message)

class ModelTimeoutError(ChatError):
    """Raised when model API calls timeout"""
    def __init__(self, model_name: str, timeout_duration: int):
        super().__init__(
            f"{model_name} API call timed out after {timeout_duration}s",
            "timeout",
            {"model": model_name, "timeout": timeout_duration}
        )

class ContextError(ChatError):
    """Raised when there are issues with context processing"""
    pass

class ModelAPIError(ChatError):
    """Raised when model API calls fail"""
    pass

def handle_api_errors(func):
    """Decorator to handle API errors consistently"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except asyncio.TimeoutError as e:
            model_name = func.__name__.split('_')[-1]  # Extract model name from function
            logger.error(f"Timeout in {func.__name__}: {str(e)}")
            raise ModelTimeoutError(model_name, 30)  # Assuming 30s timeout
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            raise ModelAPIError(
                f"API error in {func.__name__}: {str(e)}",
                "api_error",
                {"original_error": str(e)}
            )
    return wrapper

class ChatOrchestrator:
    """
    Coordinates the overall chat flow, handling query routing and response generation.
    Implements dual-call mechanism for premium users:
    1. Initial conversational response (Deepseek V3)
    2. Concurrent complexity evaluation
    3. Advanced reasoning (R1) if needed
    4. Final response enhancement (Deepseek V3)
    """
    
    # Configuration constants
    TIMEOUT_INITIAL = 30  # seconds
    TIMEOUT_REASONING = 45  # seconds
    TIMEOUT_ENHANCEMENT = 20  # seconds
    MAX_RETRIES = 2
    
    def __init__(
        self,
        db: Session,
        v3_client: DeepseekV3Client,
        r1_client: R1Client,
        context_formatter: ContextFormatter,
        data_integrator: DataIntegrator
    ):
        self.db = db
        self.v3_client = v3_client
        self.r1_client = r1_client
        self.context_formatter = context_formatter
        self.data_integrator = data_integrator

    async def process_chat_message(
        self,
        user_id: str,
        message: str,
        conversation_history: Optional[list] = None,
        custom_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for processing chat messages.
        Handles both standard and premium user flows.
        """
        try:
            # Get user and verify premium status
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"User not found: {user_id}")
                raise ChatError("User not found", "user_error")
                
            is_premium = user.tier == 'premium'
            
            # Get integrated context
            try:
                context = await self.data_integrator.integrate_supplemental_data(
                    self.db, user_id, custom_context
                )
            except Exception as e:
                logger.error(f"Context integration failed: {str(e)}", exc_info=True)
                raise ContextError(
                    "Failed to integrate context data",
                    "context_error",
                    {"original_error": str(e)}
                )
            
            # Process message based on user tier
            try:
                if is_premium:
                    return await self._handle_premium_message(
                        message, context, conversation_history
                    )
                else:
                    return await self._handle_standard_message(
                        message, context, conversation_history
                    )
            except (ModelTimeoutError, ModelAPIError) as e:
                # Fall back to standard flow for premium users on error
                if is_premium:
                    logger.warning(
                        f"Premium flow failed, falling back to standard: {str(e)}"
                    )
                    return await self._handle_standard_message(
                        message, context, conversation_history
                    )
                raise
                
        except ChatError as e:
            # Log and return structured error response
            logger.error(
                f"Chat error: {e.message}",
                extra={"error_type": e.error_type, "details": e.details}
            )
            return self._create_error_response(e)
        except Exception as e:
            # Catch-all for unexpected errors
            logger.critical(f"Unexpected error: {str(e)}", exc_info=True)
            return self._create_error_response(
                ChatError(
                    "An unexpected error occurred",
                    "system_error",
                    {"original_error": str(e)}
                )
            )

    @handle_api_errors
    async def _handle_premium_message(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: Optional[list]
    ) -> Dict[str, Any]:
        """Handles premium user messages with dual-call mechanism"""
        try:
            # Start both initial response and evaluation concurrently
            initial_response_task = asyncio.create_task(
                asyncio.wait_for(
                    self._get_initial_response(message, context, conversation_history),
                    timeout=self.TIMEOUT_INITIAL
                )
            )
            evaluation_task = asyncio.create_task(
                asyncio.wait_for(
                    self._evaluate_complexity(message, context),
                    timeout=self.TIMEOUT_INITIAL
                )
            )
            
            # Wait for both tasks with timeout handling
            initial_response, needs_reasoning = await asyncio.gather(
                initial_response_task,
                evaluation_task,
                return_exceptions=True
            )
            
            # Handle any exceptions from the gathered tasks
            if isinstance(initial_response, Exception):
                logger.error(f"Initial response failed: {str(initial_response)}")
                raise initial_response
            if isinstance(needs_reasoning, Exception):
                logger.warning(f"Evaluation failed: {str(needs_reasoning)}")
                needs_reasoning = False  # Default to simple response on evaluation failure
            
            if not needs_reasoning:
                return {
                    "response": initial_response,
                    "response_type": "conversational",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            # Get advanced reasoning with timeout
            try:
                reasoning_response = await asyncio.wait_for(
                    self._get_advanced_reasoning(message, context, conversation_history),
                    timeout=self.TIMEOUT_REASONING
                )
            except asyncio.TimeoutError as e:
                logger.error("Advanced reasoning timed out", exc_info=True)
                return {
                    "response": initial_response,
                    "response_type": "conversational",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "fallback_reason": "reasoning_timeout"
                }
            
            # Enhance final response with timeout
            try:
                final_response = await asyncio.wait_for(
                    self._enhance_response(initial_response, reasoning_response, context),
                    timeout=self.TIMEOUT_ENHANCEMENT
                )
            except asyncio.TimeoutError as e:
                logger.warning("Response enhancement timed out, using reasoning directly")
                final_response = reasoning_response
            
            return {
                "response": final_response,
                "response_type": "advanced",
                "reasoning_available": True,
                "raw_reasoning": reasoning_response,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Premium message handling failed: {str(e)}", exc_info=True)
            raise

    @handle_api_errors
    async def _handle_standard_message(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: Optional[list]
    ) -> Dict[str, Any]:
        """Handles standard user messages with basic conversational flow"""
        try:
            response = await asyncio.wait_for(
                self._get_initial_response(message, context, conversation_history),
                timeout=self.TIMEOUT_INITIAL
            )
            
            return {
                "response": response,
                "response_type": "conversational",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Standard message handling failed: {str(e)}", exc_info=True)
            raise

    def _create_error_response(self, error: ChatError) -> Dict[str, Any]:
        """Creates a structured error response"""
        return {
            "error": True,
            "error_type": error.error_type,
            "message": error.message,
            "details": error.details,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    @handle_api_errors
    async def _get_initial_response(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: Optional[list]
    ) -> str:
        """Gets initial conversational response from Deepseek V3"""
        formatted_context = self.context_formatter.format_climber_context(
            context.get("core_data", {}).get("climber_summary", {})
        )
        
        return await self.v3_client.get_chat_response(
            message,
            formatted_context.conversational_context,
            conversation_history
        )

    @handle_api_errors
    async def _evaluate_complexity(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluates query complexity to determine if advanced reasoning is needed.
        Uses Deepseek V3 in evaluation mode.
        """
        evaluation = await self.v3_client.evaluate_complexity(message, context)
        return evaluation.lower() == "advanced reasoning needed"

    @handle_api_errors
    async def _get_advanced_reasoning(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: Optional[list]
    ) -> str:
        """Gets detailed analysis from R1 Advanced Reasoning"""
        formatted_context = self.context_formatter.format_climber_context(
            context.get("core_data", {}).get("climber_summary", {})
        )
        
        return await self.r1_client.get_reasoning_response(
            message,
            formatted_context.structured_context,
            conversation_history
        )

    @handle_api_errors
    async def _enhance_response(
        self,
        initial_response: str,
        reasoning_response: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Enhances the response by combining conversational and reasoning outputs.
        Uses Deepseek V3 for final polish.
        """
        return await self.v3_client.enhance_response(
            initial_response,
            reasoning_response,
            context
        )

