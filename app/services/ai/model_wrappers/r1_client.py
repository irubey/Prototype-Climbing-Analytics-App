# Abstraction layer for r1 advanced reasoning API calls

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timezone
import asyncio
from openai import OpenAI
from ..prompt_manager import PromptManager

logger = logging.getLogger(__name__)

class R1Client:
    """
    Client wrapper for DeepSeek R1 Advanced Reasoning model.
    Handles API calls and response processing with split response format.
    """

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = "deepseek-reasoner"
        self.max_retries = 2
        self.timeout = 45  # seconds

    async def get_analysis(
        self,
        prompt: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 4096,
        stream: bool = False
    ) -> Any:
        """
        Gets analysis from R1 model with split response format.
        
        Args:
            prompt: Analysis prompt
            context: User context data
            conversation_history: Optional conversation history
            max_tokens: Maximum tokens for response
            stream: Whether to stream the response
            
        Returns:
            Model response containing reasoning_content and content
        """
        try:
            # Prepare messages
            messages = self._prepare_messages(prompt, context, conversation_history)
            
            # Make API call with retries
            for attempt in range(self.max_retries):
                try:
                    response = await asyncio.wait_for(
                        self._make_api_call(messages, max_tokens, stream),
                        timeout=self.timeout
                    )
                    
                    # Log successful response
                    logger.debug(
                        "R1 analysis completed",
                        extra={
                            "attempt": attempt + 1,
                            "has_reasoning": bool(response.choices[0].message.reasoning_content),
                            "content_length": len(response.choices[0].message.content)
                        }
                    )
                    
                    return response
                    
                except asyncio.TimeoutError:
                    if attempt == self.max_retries - 1:
                        raise
                    logger.warning(f"R1 API timeout, attempt {attempt + 1}")
                    continue
                    
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        raise
                    logger.warning(f"R1 API error: {str(e)}, attempt {attempt + 1}")
                    continue
                    
        except Exception as e:
            logger.error(f"R1 analysis failed: {str(e)}", exc_info=True)
            raise

    async def get_reasoning_response(
        self,
        query: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Gets reasoning response for a user query.
        
        Args:
            query: User's question
            context: User context data
            conversation_history: Optional conversation history
            
        Returns:
            Reasoning response text
        """
        try:
            # Build analysis prompt
            prompt = self._build_analysis_prompt(query, context)
            
            # Get analysis with split response
            response = await self.get_analysis(
                prompt,
                context,
                conversation_history
            )
            
            # Return content part (reasoning_content is handled separately)
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Failed to get reasoning response: {str(e)}", exc_info=True)
            raise

    def _prepare_messages(
        self,
        prompt: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> List[Dict[str, str]]:
        """Prepares message sequence for API call"""
        messages = []
        
        # Add system message with R1 system prompt
        messages.append({
            "role": "system",
            "content": PromptManager.get_r1_system_prompt()
        })
        
        # Add conversation history if provided
        if conversation_history:
            # Filter out any messages with reasoning_content
            messages.extend([
                msg for msg in conversation_history
                if "reasoning_content" not in msg
            ])
        
        # Add user message with context and prompt using centralized labels
        messages.append({
            "role": "user",
            "content": f"{PromptManager.USER_CONTEXT_LABEL}\n{self._format_context(context)}\n\n{PromptManager.QUERY_LABEL}\n{prompt}"
        })
        
        return messages

    async def _make_api_call(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        stream: bool
    ) -> Any:
        """Makes the actual API call to R1"""
        return await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            stream=stream
        )

    def _get_system_prompt(self) -> str:
        """Gets the system prompt for R1"""
        return PromptManager.R1_SYSTEM

    def _build_analysis_prompt(self, query: str, context: Dict[str, Any]) -> str:
        """Builds complete analysis prompt"""
        return PromptManager.get_r1_analysis_prompt(query, context)

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Formats context data for inclusion in prompt"""
        try:
            # Format context using centralized section headers
            sections = []
            if "observations" in context:
                sections.append(f"{PromptManager.R1_ANALYSIS_STRUCTURE['sections']['observations']['title']}\n{context['observations']}")
            if "analysis" in context:
                sections.append(f"{PromptManager.R1_ANALYSIS_STRUCTURE['sections']['analysis']['title']}\n{context['analysis']}")
            if "recommendations" in context:
                sections.append(f"{PromptManager.R1_ANALYSIS_STRUCTURE['sections']['recommendations']['title']}\n{context['recommendations']}")
            
            return "\n\n".join(sections) if sections else str(context)
            
        except Exception as e:
            logger.error(f"Context formatting failed: {str(e)}", exc_info=True)
            return str({})  # Return empty context on error
