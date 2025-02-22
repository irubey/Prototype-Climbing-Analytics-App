from abc import ABC, abstractmethod
from typing import Dict, Optional, AsyncGenerator, Union, List, Any
import aiohttp
import asyncio
from datetime import datetime
import json
import logging
import random
from app.core.config import settings

logger = logging.getLogger(__name__)

class RetryConfig:
    """Configuration for retry behavior."""
    BASE_DELAY = 1.0  # Base delay in seconds
    MAX_DELAY = 8.0   # Maximum delay in seconds
    MAX_RETRIES = 3   # Maximum number of retry attempts
    
    @staticmethod
    def get_delay(attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        base_delay = min(2.0 ** (attempt - 1), RetryConfig.MAX_DELAY)
        jitter = random.uniform(0.8, 1.2)
        return min(base_delay * jitter, RetryConfig.MAX_DELAY)

class ModelClient(ABC):
    """Base class for AI model clients with secure configuration."""
    
    def __init__(self):
        """Initialize model client with configuration from settings."""
        if not settings.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY must be set in environment variables")
        if not settings.DEEPSEEK_API_URL:
            raise ValueError("DEEPSEEK_API_URL must be set in environment variables")
            
        self.api_key = settings.DEEPSEEK_API_KEY
        self.base_url = settings.DEEPSEEK_API_URL
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    @abstractmethod
    async def generate_response(self, prompt: str, context: Dict) -> str:
        """Generate a response based on the prompt and context."""
        pass

    async def _should_retry(self, status_code: int, attempt: int) -> bool:
        """Determine if request should be retried based on status code and attempt number."""
        if attempt >= RetryConfig.MAX_RETRIES:
            return False
            
        # Retry on connection errors, timeouts, and specific HTTP status codes
        retryable_codes = {
            408,  # Request Timeout
            429,  # Too Many Requests
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504   # Gateway Timeout
        }
        return status_code in retryable_codes
        
    async def _make_api_call(self, endpoint: str, payload: Dict) -> Dict:
        """Make an async API call with secure headers, error handling, and retries."""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Environment": settings.ENVIRONMENT
        }
        
        for attempt in range(1, RetryConfig.MAX_RETRIES + 1):
            try:
                async with self.session.post(
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        return await response.json()
                        
                    error_body = await response.text()
                    should_retry = await self._should_retry(response.status, attempt)
                    
                    logger.warning(
                        f"API call failed (attempt {attempt}/{RetryConfig.MAX_RETRIES})",
                        extra={
                            "status_code": response.status,
                            "endpoint": endpoint,
                            "error": error_body,
                            "environment": settings.ENVIRONMENT,
                            "will_retry": should_retry
                        }
                    )
                    
                    if should_retry:
                        delay = RetryConfig.get_delay(attempt)
                        logger.info(f"Retrying in {delay:.2f} seconds...")
                        await asyncio.sleep(delay)
                        continue
                        
                    return {
                        "error": f"API call failed with status {response.status}",
                        "status_code": response.status
                    }
                    
            except asyncio.TimeoutError:
                should_retry = attempt < RetryConfig.MAX_RETRIES
                logger.warning(
                    f"API call timed out (attempt {attempt}/{RetryConfig.MAX_RETRIES})",
                    extra={
                        "endpoint": endpoint,
                        "environment": settings.ENVIRONMENT,
                        "will_retry": should_retry
                    }
                )
                
                if should_retry:
                    delay = RetryConfig.get_delay(attempt)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)
                    continue
                    
                return {"error": "Request timed out after all retries", "status_code": 408}
                
            except Exception as e:
                should_retry = attempt < RetryConfig.MAX_RETRIES
                logger.error(
                    f"API call failed (attempt {attempt}/{RetryConfig.MAX_RETRIES}): {str(e)}",
                    exc_info=True,
                    extra={
                        "endpoint": endpoint,
                        "environment": settings.ENVIRONMENT,
                        "will_retry": should_retry
                    }
                )
                
                if should_retry:
                    delay = RetryConfig.get_delay(attempt)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)
                    continue
                    
                return {"error": str(e)}
                
        return {"error": "All retry attempts failed", "status_code": 500}

    async def _stream_response(self, endpoint: str, payload: Dict) -> AsyncGenerator[str, None]:
        """Stream response chunks from the API with secure headers and retries."""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Environment": settings.ENVIRONMENT
        }
        
        for attempt in range(1, RetryConfig.MAX_RETRIES + 1):
            try:
                async with self.session.post(
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        async for line in response.content:
                            if line:
                                try:
                                    data = json.loads(line.decode())
                                    if "choices" in data and data["choices"]:
                                        content = data["choices"][0].get("delta", {}).get("content", "")
                                        if content:
                                            yield content
                                except json.JSONDecodeError:
                                    continue
                        return
                        
                    should_retry = await self._should_retry(response.status, attempt)
                    logger.warning(
                        f"Streaming API call failed (attempt {attempt}/{RetryConfig.MAX_RETRIES})",
                        extra={
                            "status_code": response.status,
                            "endpoint": endpoint,
                            "environment": settings.ENVIRONMENT,
                            "will_retry": should_retry
                        }
                    )
                    
                    if should_retry:
                        delay = RetryConfig.get_delay(attempt)
                        logger.info(f"Retrying stream in {delay:.2f} seconds...")
                        await asyncio.sleep(delay)
                        continue
                        
                    yield f"Error: Streaming failed with status {response.status}"
                    return
                    
            except Exception as e:
                should_retry = attempt < RetryConfig.MAX_RETRIES
                logger.error(
                    f"Streaming API call failed (attempt {attempt}/{RetryConfig.MAX_RETRIES}): {str(e)}",
                    exc_info=True,
                    extra={
                        "endpoint": endpoint,
                        "environment": settings.ENVIRONMENT,
                        "will_retry": should_retry
                    }
                )
                
                if should_retry:
                    delay = RetryConfig.get_delay(attempt)
                    logger.info(f"Retrying stream in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)
                    continue
                    
                yield "Error: Failed to stream response after all retries"
                return

class Grok2Client(ModelClient):
    """Basic tier model client with constrained parameters."""
    
    def __init__(self):
        super().__init__()
        self.model = "grok-2"
        self.max_tokens = 4000
        
    async def generate_response(self, prompt: str, context: Dict) -> str:
        """Generate a response using Grok 2 with basic reasoning capabilities."""
        # Prepare context for the model
        context_summary = context.get("summary", "No context available")
        recent_climbs = context.get("recent_climbs", [])[-10:]  # Last 10 climbs
        
        formatted_prompt = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a friendly climbing coach providing concise advice."
                },
                {
                    "role": "user",
                    "content": f"Context: {context_summary}\nRecent climbs: {json.dumps(recent_climbs)}\nQuery: {prompt}"
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": 0.7,
            "environment": settings.ENVIRONMENT
        }
        
        response = await self._make_api_call("completions", formatted_prompt)
        
        if "error" in response:
            logger.error(
                "Failed to generate response",
                extra={
                    "error": response["error"],
                    "status_code": response.get("status_code"),
                    "model": self.model,
                    "environment": settings.ENVIRONMENT
                }
            )
            raise ValueError(f"Failed to generate response: {response['error']}")
            
        return response.get("choices", [{}])[0].get("message", {}).get("content", "")

class Grok3Client(ModelClient):
    """Premium tier model client with advanced capabilities."""
    
    def __init__(self):
        super().__init__()
        self.model = "grok-3"
        self.max_tokens = 128000
        self._formatting_errors = 0
        self._max_formatting_errors = 3
        self.api_endpoint = f"{self.base_url}/completions"
        self.timeout = 30

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API request."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _get_session(self) -> aiohttp.ClientSession:
        """Get aiohttp session."""
        return aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            headers=self._get_headers()
        )

    def _prepare_request(self, prompt: str, context: Dict, stream: bool = False) -> Dict:
        """Prepare the request payload."""
        context_summary = context.get("summary", "No context available")
        recent_climbs = context.get("recent_climbs", [])
        uploads = context.get("uploads", [])
        goals = context.get("goals", {})
        
        context_str = (
            f"Context Summary: {context_summary}\n"
            f"Recent Climbs: {json.dumps(recent_climbs)}\n"
            f"Goals: {json.dumps(goals)}\n"
            f"Uploaded Data: {json.dumps(uploads)}"
        )
        
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert climbing coach providing detailed, "
                        "personalized advice based on comprehensive climbing data."
                    )
                },
                {
                    "role": "user",
                    "content": f"{context_str}\nQuery: {prompt}"
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": 0.8,
            "stream": stream,
            "environment": settings.ENVIRONMENT
        }

    async def generate_response(self, prompt: str, context: Dict[str, Any], stream: bool = False) -> Union[str, AsyncGenerator[str, None]]:
        """Generate a response from the model."""
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY must be set")

        messages = self._prepare_request(prompt, context)
        
        if stream:
            return self._generate_streaming_response(messages)
        return await self._generate_single_response(messages)

    async def _generate_streaming_response(self, messages: List[Dict[str, Any]]) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the model."""
        session = self._get_session()
        try:
            async with session:
                async with session.post(
                    self.api_endpoint,
                    json={"messages": messages, "stream": True},
                    timeout=self.timeout
                ) as response:
                    if response.status != 200:
                        yield "An error occurred while generating the response."
                        return

                    async for line in response.content:
                        try:
                            data = json.loads(line.decode())
                            if "choices" in data and data["choices"]:
                                content = data["choices"][0].get("delta", {}).get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.error(f"Error processing streaming chunk: {str(e)}")
                            continue
        except Exception as e:
            logger.error(f"Error in streaming response: {str(e)}")
            yield "An error occurred while generating the response."
        finally:
            await session.close()

    async def _generate_single_response(self, messages: List[Dict[str, Any]]) -> str:
        """Generate a single response from the model."""
        session = self._get_session()
        try:
            async with session:
                async with session.post(
                    self.api_endpoint,
                    json={"messages": messages},
                    timeout=self.timeout
                ) as response:
                    if response.status != 200:
                        return "An error occurred while generating the response."
                    
                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Error in single response: {str(e)}")
            return "An error occurred while generating the response."
        finally:
            await session.close()

    async def _create_single_chunk_generator(self, response: str) -> AsyncGenerator[str, None]:
        """Create an async generator that yields a single chunk."""
        yield response

    async def _generate_streaming(self, formatted_prompt: Dict) -> AsyncGenerator[str, None]:
        """Generate a streaming response."""
        if self._formatting_errors >= self._max_formatting_errors:
            logger.info(
                "Using non-streaming due to previous formatting errors",
                extra={
                    "error_count": self._formatting_errors,
                    "model": self.model,
                    "environment": settings.ENVIRONMENT
                }
            )
            response = await self._generate_non_streaming(formatted_prompt)
            yield response
            return

        try:
            async for chunk in self._stream_response("completions", formatted_prompt):
                if chunk.startswith("Error:"):
                    if "formatting" in chunk.lower():
                        self._formatting_errors += 1
                        logger.warning(
                            "Streaming format error detected, attempting fallback",
                            extra={
                                "error_count": self._formatting_errors,
                                "max_errors": self._max_formatting_errors,
                                "model": self.model,
                                "environment": settings.ENVIRONMENT
                            }
                        )
                        # Fallback to non-streaming
                        response = await self._generate_non_streaming(formatted_prompt)
                        yield response
                        return
                yield chunk
            
            # Reset error count on successful streaming
            self._formatting_errors = 0
            
        except Exception as e:
            logger.error(
                "Streaming failed, falling back to non-streaming",
                exc_info=True,
                extra={
                    "error": str(e),
                    "model": self.model,
                    "environment": settings.ENVIRONMENT
                }
            )
            response = await self._generate_non_streaming(formatted_prompt)
            yield response

    async def _generate_non_streaming(self, formatted_prompt: Dict) -> str:
        """Generate a non-streaming response with error handling."""
        # Ensure streaming is disabled for fallback
        formatted_prompt["stream"] = False
        
        response = await self._make_api_call("completions", formatted_prompt)
        
        if "error" in response:
            logger.error(
                "Failed to generate non-streaming response",
                extra={
                    "error": response["error"],
                    "status_code": response.get("status_code"),
                    "model": self.model,
                    "environment": settings.ENVIRONMENT
                }
            )
            raise ValueError(f"Failed to generate response: {response['error']}")
            
        return response.get("choices", [{}])[0].get("message", {}).get("content", "")

    async def _stream_response(self, endpoint: str, payload: Dict) -> AsyncGenerator[str, None]:
        """Stream response chunks from the API with secure headers and retries."""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Environment": settings.ENVIRONMENT
        }
        
        formatting_error_count = 0
        max_formatting_errors = 3  # Maximum consecutive formatting errors per stream
        
        for attempt in range(1, RetryConfig.MAX_RETRIES + 1):
            try:
                async with self.session.post(
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        async for line in response.content:
                            if line:
                                try:
                                    data = json.loads(line.decode())
                                    if "choices" in data and data["choices"]:
                                        content = data["choices"][0].get("delta", {}).get("content", "")
                                        if content:
                                            formatting_error_count = 0  # Reset on successful chunk
                                            yield content
                                except json.JSONDecodeError:
                                    formatting_error_count += 1
                                    logger.warning(
                                        f"JSON decode error in stream (error {formatting_error_count}/{max_formatting_errors})",
                                        extra={
                                            "attempt": attempt,
                                            "endpoint": endpoint,
                                            "environment": settings.ENVIRONMENT
                                        }
                                    )
                                    if formatting_error_count >= max_formatting_errors:
                                        yield "Error: Multiple formatting errors detected in stream"
                                        return
                                    continue
                        return
                        
                    should_retry = await self._should_retry(response.status, attempt)
                    logger.warning(
                        f"Streaming API call failed (attempt {attempt}/{RetryConfig.MAX_RETRIES})",
                        extra={
                            "status_code": response.status,
                            "endpoint": endpoint,
                            "environment": settings.ENVIRONMENT,
                            "will_retry": should_retry
                        }
                    )
                    
                    if should_retry:
                        delay = RetryConfig.get_delay(attempt)
                        logger.info(f"Retrying stream in {delay:.2f} seconds...")
                        await asyncio.sleep(delay)
                        continue
                        
                    yield f"Error: Streaming failed with status {response.status}"
                    return
                    
            except Exception as e:
                should_retry = attempt < RetryConfig.MAX_RETRIES
                logger.error(
                    f"Streaming API call failed (attempt {attempt}/{RetryConfig.MAX_RETRIES}): {str(e)}",
                    exc_info=True,
                    extra={
                        "endpoint": endpoint,
                        "environment": settings.ENVIRONMENT,
                        "will_retry": should_retry
                    }
                )
                
                if should_retry:
                    delay = RetryConfig.get_delay(attempt)
                    logger.info(f"Retrying stream in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)
                    continue
                    
                yield "Error: Failed to stream response after all retries"
                return
