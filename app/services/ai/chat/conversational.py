# Manages v3 conversational interactions

from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timezone

from ..model_wrappers.v3_client import DeepseekV3Client
from ...context.context_formatter import ContextFormatter
from ..prompt_manager import PromptManager

logger = logging.getLogger(__name__)

class ConversationalManager:
    """
    Manages conversational interactions using Deepseek V3.
    Handles prompt construction, context integration, and conversation flow.
    """




    def __init__(self, v3_client: DeepseekV3Client, context_formatter: ContextFormatter):
        self.v3_client = v3_client
        self.context_formatter = context_formatter
        self.conversation_expiry = 3600  # 1 hour in seconds

    async def get_response(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Gets a conversational response using the base prompt.
        
        Args:
            message: User's input message
            context: User's climbing context
            conversation_history: Optional conversation history
            
        Returns:
            Conversational response from the model
        """
        try:
            # Format context for conversation
            formatted_context = self._format_context_for_conversation(context)
            
            # Construct full prompt with context
            system_prompt = self._build_system_prompt(formatted_context)
            
            # Clean and validate conversation history
            cleaned_history = self._prepare_conversation_history(conversation_history)
            
            # Get response from model
            response = await self.v3_client.get_chat_completion(
                system_prompt=system_prompt,
                user_message=message,
                conversation_history=cleaned_history
            )
            
            logger.debug(
                "Generated conversational response",
                extra={
                    "message_length": len(message),
                    "response_length": len(response),
                    "has_history": bool(conversation_history)
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating conversational response: {str(e)}", exc_info=True)
            raise

    async def evaluate_complexity(self, message: str, context: Dict[str, Any]) -> str:
        """
        Evaluates query complexity to determine if advanced reasoning is needed.
        
        Args:
            message: User's input message
            context: User's climbing context
            
        Returns:
            "advanced reasoning needed" or "normal response sufficient"
        """
        try:
            # Get evaluation from model
            evaluation = await self.v3_client.get_chat_completion(
                system_prompt=PromptManager.CONVERSATIONAL_EVALUATION,
                user_message=self._build_evaluation_prompt(message, context)
            )
            
            logger.debug(
                "Complexity evaluation completed",
                extra={
                    "evaluation_result": evaluation,
                    "message_length": len(message)
                }
            )
            
            return evaluation.strip().lower()
            
        except Exception as e:
            logger.error(f"Error evaluating query complexity: {str(e)}", exc_info=True)
            raise

    async def enhance_response(
        self,
        initial_response: str,
        reasoning_response: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Enhances technical reasoning into a conversational format.
        
        Args:
            initial_response: Original conversational response
            reasoning_response: Technical reasoning output
            context: User's climbing context
            
        Returns:
            Enhanced conversational response
        """
        try:
            enhancement_input = self._build_enhancement_prompt(
                initial_response,
                reasoning_response,
                context
            )
            
            enhanced_response = await self.v3_client.get_chat_completion(
                system_prompt=PromptManager.CONVERSATIONAL_ENHANCEMENT,
                user_message=enhancement_input
            )
            
            logger.debug(
                "Response enhancement completed",
                extra={
                    "initial_length": len(initial_response),
                    "reasoning_length": len(reasoning_response),
                    "enhanced_length": len(enhanced_response)
                }
            )
            
            return enhanced_response
            
        except Exception as e:
            logger.error(f"Error enhancing response: {str(e)}", exc_info=True)
            raise

    def _format_context_for_conversation(self, context: Dict[str, Any]) -> str:
        """Formats context data into a conversational format"""
        try:
            formatted_context = self.context_formatter.format_climber_context(
                context.get("core_data", {}).get("climber_summary", {})
            )
            return formatted_context.conversational_context
        except Exception as e:
            logger.error(f"Error formatting context: {str(e)}", exc_info=True)
            return ""  # Return empty context on error

    def _build_system_prompt(self, context: str) -> str:
        """Builds the complete system prompt with context"""
        return PromptManager.get_system_prompt(context)

    def _build_evaluation_prompt(self, message: str, context: Dict[str, Any]) -> str:
        """Builds the prompt for complexity evaluation"""
        context_summary = self._format_context_for_conversation(context)
        return PromptManager.get_evaluation_prompt(context_summary, message)

    def _build_enhancement_prompt(
        self,
        initial_response: str,
        reasoning_response: str,
        context: Dict[str, Any]
    ) -> str:
        """Builds the prompt for response enhancement"""
        context_summary = self._format_context_for_conversation(context)
        return PromptManager.get_enhancement_prompt(
            initial_response=initial_response,
            technical_analysis=reasoning_response,
            context=context_summary,
            preserve_structure=True
        )

    def _prepare_conversation_history(
        self,
        history: Optional[List[Dict[str, str]]]
    ) -> List[Dict[str, str]]:
        """
        Cleans and validates conversation history.
        Removes expired messages and ensures proper format.
        """
        if not history:
            return []
            
        current_time = datetime.now(timezone.utc).timestamp()
        cleaned_history = []
        
        for message in history:
            # Skip malformed messages
            if not isinstance(message, dict) or 'role' not in message or 'content' not in message:
                continue
                
            # Skip expired messages
            timestamp = message.get('timestamp', 0)
            if current_time - timestamp > self.conversation_expiry:
                continue
                
            cleaned_history.append({
                'role': message['role'],
                'content': message['content']
            })
        
        # Limit history length if needed
        return cleaned_history[-10:]  # Keep last 10 messages