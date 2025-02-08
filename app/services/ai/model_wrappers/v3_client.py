from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timezone
import asyncio
from openai import OpenAI
from ..prompt_manager import PromptManager

logger = logging.getLogger(__name__)

class DeepseekV3Client:
    """
    Client wrapper for DeepSeek V3 Conversational model.
    Handles API calls and response processing for natural language interactions.
    """

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = "deepseek-chat"
        self.max_retries = 2
        self.timeout = 30  # seconds
        self.default_temperature = 0.7

    async def get_chat_completion(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 2048,
        temperature: float = None,
        stream: bool = False
    ) -> str:
        """
        Gets chat completion from V3 model.
        
        Args:
            system_prompt: System context/instruction
            user_message: User's message
            conversation_history: Optional conversation history
            max_tokens: Maximum tokens for response
            temperature: Response temperature (0-1)
            stream: Whether to stream the response
            
        Returns:
            Model response text
        """
        try:
            # Prepare messages
            messages = self._prepare_messages(
                system_prompt,
                user_message,
                conversation_history
            )
            
            # Make API call with retries
            for attempt in range(self.max_retries):
                try:
                    response = await asyncio.wait_for(
                        self._make_api_call(
                            messages,
                            max_tokens,
                            temperature or self.default_temperature,
                            stream
                        ),
                        timeout=self.timeout
                    )
                    
                    # Log successful response
                    logger.debug(
                        "V3 chat completion completed",
                        extra={
                            "attempt": attempt + 1,
                            "response_length": len(response.choices[0].message.content),
                            "temperature": temperature or self.default_temperature
                        }
                    )
                    
                    return response.choices[0].message.content
                    
                except asyncio.TimeoutError:
                    if attempt == self.max_retries - 1:
                        raise
                    logger.warning(f"V3 API timeout, attempt {attempt + 1}")
                    continue
                    
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        raise
                    logger.warning(f"V3 API error: {str(e)}, attempt {attempt + 1}")
                    continue
                    
        except Exception as e:
            logger.error(f"V3 chat completion failed: {str(e)}", exc_info=True)
            raise

    async def get_enhanced_response(
        self,
        original_text: str,
        enhancement_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        preserve_structure: bool = True
    ) -> str:
        """
        Gets enhanced version of original text.
        
        Args:
            original_text: Text to enhance
            enhancement_prompt: Prompt guiding enhancement
            conversation_history: Optional conversation history
            preserve_structure: Whether to maintain original structure
            
        Returns:
            Enhanced text
        """
        try:
            # Build complete prompt
            system_prompt = self._get_enhancement_system_prompt(preserve_structure)
            
            # Get enhanced response
            enhanced_text = await self.get_chat_completion(
                system_prompt=system_prompt,
                user_message=f"{enhancement_prompt}\n\nOriginal text:\n{original_text}",
                conversation_history=conversation_history,
                temperature=0.4  # Lower temperature for more consistent enhancements
            )
            
            return enhanced_text
            
        except Exception as e:
            logger.error(f"Response enhancement failed: {str(e)}", exc_info=True)
            raise

    def _prepare_messages(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> List[Dict[str, str]]:
        """Prepares message sequence for API call"""
        messages = []
        
        # Add system message
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages

    async def _make_api_call(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        stream: bool
    ) -> Any:
        """Makes the actual API call to V3"""
        return await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream
        )

    def _get_enhancement_system_prompt(self, preserve_structure: bool) -> str:
        """Gets system prompt for text enhancement"""
        return PromptManager.get_enhancement_prompt(preserve_structure)