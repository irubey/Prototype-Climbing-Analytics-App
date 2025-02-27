import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
import aiohttp
import asyncio
import redis
from sse_starlette.sse import EventSourceResponse
from app.services.chat.ai.model_client import ModelClient, Grok2Client, Grok3Client, RetryConfig
from app.services.chat.ai.basic_chat import BasicChatService, ChatError, QuotaExceededError, ModelError
from app.services.chat.ai.premium_chat import PremiumChatService, FileValidationError
from app.services.chat.context.orchestrator import ContextOrchestrator
from app.services.chat.events.manager import EventManager, EventType
from app.core.config import settings
from fastapi import HTTPException

# Test data
@pytest.fixture
def mock_context():
    return {
        "summary": "Intermediate climber focusing on bouldering",
        "recent_climbs": [
            {"grade": "V4", "date": "2024-02-20", "status": "sent"},
            {"grade": "V5", "date": "2024-02-19", "status": "project"}
        ],
        "goals": {"short_term": "Send V5", "long_term": "Compete in nationals"},
        "uploads": []
    }

@pytest.fixture
def mock_api_response():
    return {
        "choices": [{
            "message": {
                "content": "Based on your recent climbs, focus on power endurance."
            }
        }]
    }

@pytest.fixture
def mock_stream_response():
    return [
        b'{"choices":[{"delta":{"content":"Based"}}]}\n',
        b'{"choices":[{"delta":{"content":" on"}}]}\n',
        b'{"choices":[{"delta":{"content":" your climbs"}}]}\n'
    ]

# Model Client Tests
class TestModelClient:
    @pytest.mark.asyncio
    async def test_retry_config(self):
        """Test retry configuration and delay calculation."""
        delay = RetryConfig.get_delay(1)
        assert 0.8 <= delay <= 1.2  # Account for jitter
        
        delay = RetryConfig.get_delay(2)
        assert 1.6 <= delay <= 2.4  # Account for jitter
        
        delay = RetryConfig.get_delay(4)
        assert delay <= RetryConfig.MAX_DELAY

    @pytest.mark.asyncio
    async def test_should_retry(self):
        """Test retry decision logic."""
        client = Grok2Client()
        
        # Should retry on retryable status codes
        assert await client._should_retry(429, 1) is True
        assert await client._should_retry(500, 1) is True
        
        # Should not retry on non-retryable status codes
        assert await client._should_retry(400, 1) is False
        assert await client._should_retry(404, 1) is False
        
        # Should not retry if max attempts reached
        assert await client._should_retry(500, RetryConfig.MAX_RETRIES + 1) is False

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization and configuration."""
        with patch('app.services.chat.ai.model_client.settings.DEEPSEEK_API_KEY', None):
            with pytest.raises(ValueError) as exc_info:
                Grok2Client()
            assert "DEEPSEEK_API_KEY must be set" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_session_management(self):
        """Test session lifecycle management."""
        client = Grok2Client()
        async with client:
            assert client.session is not None
            assert not client.session.closed
        assert client.session.closed

    @pytest.mark.asyncio
    async def test_api_call_timeout(self):
        """Test timeout handling in API calls."""
        client = Grok2Client()
        with patch("aiohttp.ClientSession.post", side_effect=asyncio.TimeoutError):
            response = await client._make_api_call("completions", {})
            assert "error" in response
            assert "Request timed out" in response["error"]

# Grok2Client Tests
class TestGrok2Client:
    @pytest.mark.asyncio
    async def test_generate_response_success(self, mock_context, mock_api_response):
        """Test successful response generation."""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value.__aenter__.return_value.status = 200
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_api_response
            )
            
            client = Grok2Client()
            response = await client.generate_response("How can I improve?", mock_context)
            
            assert response == "Based on your recent climbs, focus on power endurance."
            assert mock_post.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_response_retry(self, mock_context, mock_api_response):
        """Test response generation with retries."""
        with patch("aiohttp.ClientSession.post") as mock_post:
            # First attempt fails, second succeeds
            mock_post.return_value.__aenter__.side_effect = [
                AsyncMock(status=500, text=AsyncMock(return_value="Server Error")),
                AsyncMock(
                    status=200,
                    json=AsyncMock(return_value=mock_api_response),
                    text=AsyncMock(return_value=json.dumps(mock_api_response))
                )
            ]
            
            client = Grok2Client()
            response = await client.generate_response("How can I improve?", mock_context)
            
            assert response == "Based on your recent climbs, focus on power endurance."
            assert mock_post.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_response_failure(self, mock_context):
        """Test response generation failure."""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value.__aenter__.return_value.status = 500
            mock_post.return_value.__aenter__.return_value.text = AsyncMock(
                return_value="Internal Server Error"
            )
            
            client = Grok2Client()
            with pytest.raises(ValueError) as exc_info:
                await client.generate_response("How can I improve?", mock_context)
            
            assert "Failed to generate response" in str(exc_info.value)

# Grok3Client Tests
class TestGrok3Client:
    @pytest.mark.asyncio
    async def test_generate_response_streaming(self, mock_context, mock_stream_response):
        """Test streaming response generation."""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value.__aenter__.return_value.status = 200
            mock_post.return_value.__aenter__.return_value.content = AsyncMock()
            mock_post.return_value.__aenter__.return_value.content.__aiter__.return_value = mock_stream_response

            client = Grok3Client()
            chunks = []
            generator = await client.generate_response("How can I improve?", mock_context, stream=True)

            async for chunk in generator:
                chunks.append(chunk)

            assert len(chunks) == 3
            assert "".join(chunks) == "Based on your climbs"

    @pytest.mark.asyncio
    async def test_streaming_fallback(self, mock_context, mock_api_response):
        """Test fallback to non-streaming on formatting errors."""
        with patch("aiohttp.ClientSession.post") as mock_post:
            # Streaming fails with formatting errors
            mock_post.return_value.__aenter__.return_value.status = 200
            mock_post.return_value.__aenter__.return_value.content.__aiter__ = AsyncMock(
                return_value=[b'invalid json']
            )
            
            client = Grok3Client()
            chunks = []
            generator = await client.generate_response("How can I improve?", mock_context, stream=True)
            async for chunk in generator:
                chunks.append(chunk)
            
            assert len(chunks) == 1
            assert "error" in chunks[0].lower()

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization and configuration."""
        with patch('app.services.chat.ai.model_client.settings.DEEPSEEK_API_KEY', None):
            with pytest.raises(ValueError) as exc_info:
                Grok3Client()
            assert "DEEPSEEK_API_KEY must be set" in str(exc_info.value)

        with patch('app.services.chat.ai.model_client.settings.DEEPSEEK_API_KEY', 'test_key'):
            client = Grok3Client()
            assert client.api_key == 'test_key'
            assert client.model == 'grok-3'

# BasicChatService Tests
class TestBasicChatService:
    @pytest.fixture
    def basic_service(self):
        context_manager = AsyncMock()
        event_manager = AsyncMock()
        redis_client = MagicMock()
        return BasicChatService(context_manager, event_manager, redis_client)

    @pytest.mark.asyncio
    async def test_quota_tracking(self, basic_service):
        """Test quota tracking functionality."""
        # Test quota not exceeded
        basic_service.redis.get.return_value = b"5"
        assert not await basic_service.exceeds_quota("user123")
        
        # Test quota exceeded
        basic_service.redis.get.return_value = b"10"
        with pytest.raises(QuotaExceededError) as exc_info:
            await basic_service.exceeds_quota("user123")
        assert "Monthly quota exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_success(self, basic_service, mock_context, mock_api_response):
        """Test successful chat processing."""
        basic_service.context_manager.get_context.return_value = mock_context
        basic_service.redis.get.return_value = b"5"
        
        with patch.object(Grok2Client, "generate_response", new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_api_response["choices"][0]["message"]["content"]
            
            response = await basic_service.process("user123", "How can I improve?", "conv123")
            
            assert response == "Based on your recent climbs, focus on power endurance."
            assert basic_service.event_manager.publish.call_count == 2  # processing + response

    @pytest.mark.asyncio
    async def test_process_quota_exceeded(self, basic_service):
        """Test processing with exceeded quota."""
        basic_service.redis.get.return_value = b"10"
        
        response = await basic_service.process("user123", "How can I improve?", "conv123")
        
        assert response is None
        basic_service.event_manager.publish.assert_called_once_with(
            "user123",
            EventType.ERROR,
            {
                "error": "Monthly quota exceeded (10/10 requests). Upgrade to Premium for unlimited coaching!",
                "error_type": "quota_exceeded",
                "details": {"current_usage": 10, "quota_limit": 10}
            }
        )

    @pytest.mark.asyncio
    async def test_redis_error_handling(self, basic_service):
        """Test Redis error handling in quota management."""
        basic_service.redis.pipeline.side_effect = redis.RedisError("Connection failed")
        await basic_service._increment_quota("user123")
        # Should continue without raising exception
        basic_service.event_manager.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_context_error_handling(self, basic_service):
        """Test context error handling in process."""
        basic_service.context_manager.get_context.side_effect = Exception("Context error")
        response = await basic_service.process("user123", "How can I improve?", "conv123")
        assert response is None
        basic_service.event_manager.publish.assert_called_with(
            "user123",
            EventType.ERROR,
            {
                "error": "Unable to process your climbing context. Please try again.",
                "error_type": "context_error",
                "details": {"original_error": "Context error"}
            }
        )

    @pytest.mark.asyncio
    async def test_processing_time_calculation(self, basic_service, mock_context):
        """Test processing time calculation and event metadata."""
        basic_service.context_manager.get_context.return_value = mock_context
        basic_service.redis.get.return_value = b"5"
        
        with patch.object(Grok2Client, "generate_response", new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "Test response"
            await basic_service.process("user123", "How can I improve?", "conv123")
            
            # Verify processing time in event
            calls = basic_service.event_manager.publish.call_args_list
            final_call = calls[-1]
            assert len(final_call.args) >= 3  # user_id, event_type, content, processing_time
            assert isinstance(final_call.args[3], float)  # processing_time is float
            assert final_call.args[3] >= 0  # processing_time is positive

# PremiumChatService Tests
class TestPremiumChatService:
    @pytest.fixture
    def premium_service(self):
        context_manager = AsyncMock()
        event_manager = AsyncMock()
        model_client = AsyncMock()
        return PremiumChatService(model_client, context_manager, event_manager)

    def test_file_validation(self, premium_service):
        """Test file validation rules."""
        # Test file size validation
        large_file = b"x" * (premium_service.MAX_FILE_SIZE + 1)
        with pytest.raises(FileValidationError) as exc_info:
            premium_service._validate_file_size(large_file, "large.csv")
        assert "exceeds maximum size" in str(exc_info.value)
        
        # Test file type validation
        with pytest.raises(FileValidationError) as exc_info:
            premium_service._validate_file_type("data.pdf")
        assert "Unsupported file type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_with_file(self, premium_service, mock_context):
        """Test processing with file upload."""
        premium_service.context_manager.get_context.return_value = mock_context
        
        csv_content = "date,grade,status\n2024-02-20,V4,sent"
        csv_file = csv_content.encode()
        
        premium_service.model_client.generate_response = AsyncMock(
            return_value="Based on your uploaded data..."
        )
        
        response = await premium_service.process(
            "user123",
            "Analyze my progress",
            "conv123",
            file=csv_file,
            filename="climbs.csv",
            stream=False
        )
        
        assert response == "Based on your uploaded data..."
        assert premium_service.event_manager.publish.call_count == 3  # processing + upload + response

    @pytest.mark.asyncio
    async def test_streaming_response(self, premium_service, mock_context, mock_stream_response):
        """Test streaming response handling."""
        premium_service.context_manager.get_context.return_value = mock_context

        async def mock_generate_response(*args, **kwargs):
            for chunk in mock_stream_response:
                data = json.loads(chunk.decode())
                content = data["choices"][0]["delta"]["content"]
                yield content

        premium_service.model_client.generate_response = AsyncMock(
            return_value=mock_generate_response()
        )

        chunks = []
        response = await premium_service.process("user123", "How can I improve?", "conv123", stream=True)
        async for chunk in response:
            chunks.append(chunk)

        assert len(chunks) == 3
        assert "".join(chunks) == "Based on your climbs"

    @pytest.mark.asyncio
    async def test_json_file_validation(self, premium_service):
        """Test JSON file validation and processing."""
        valid_json = json.dumps({"climbs": [{"grade": "V5"}]}).encode()
        invalid_json = b"invalid json"
        
        # Test valid JSON
        result = await premium_service.preprocess_file(valid_json, "data.json")
        assert result["type"] == "json"
        assert "climbs" in result["data"]
        
        # Test invalid JSON
        with pytest.raises(FileValidationError) as exc_info:
            await premium_service.preprocess_file(invalid_json, "bad.json")
        assert "malformed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_streaming_error_handling(self, premium_service, mock_context):
        """Test error handling during streaming response."""
        premium_service.context_manager.get_context.return_value = mock_context
        
        premium_service.model_client.generate_response = AsyncMock(
            side_effect=Exception("Stream error")
        )
        
        chunks = []
        response = await premium_service.process("user123", "Query", "conv123", stream=True)
        async for chunk in response:
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert "error" in chunks[0].lower()

    @pytest.mark.asyncio
    async def test_event_sequence(self, premium_service, mock_context):
        """Test correct event sequence for complex operations."""
        premium_service.context_manager.get_context.return_value = mock_context
        event_sequence = []
        
        async def mock_publish(user_id, event_type, content, *args):
            event_sequence.append(event_type)
        
        premium_service.event_manager.publish = AsyncMock(side_effect=mock_publish)
        
        response = await premium_service.process(
            "user123",
            "Query",
            "conv123",
            file=b"date,grade\n2024-02-20,V4",
            filename="data.csv",
            stream=True
        )
        async for _ in response:
            pass
        
        assert event_sequence == ["file_upload", "processing_start", "processing_complete"]

    @pytest.mark.asyncio
    async def test_upload_context_integration(self, premium_service, mock_context):
        """Test upload data integration with context."""
        premium_service.context_manager.get_context.return_value = mock_context.copy()
        
        test_file = b"date,grade\n2024-02-20,V4"
        
        premium_service.model_client.generate_response = AsyncMock(
            return_value="Response"
        )
        
        await premium_service.process(
            "user123",
            "Query",
            "conv123",
            file=test_file,
            filename="data.csv",
            stream=False
        )
        
        # Verify the model client was called with the updated context
        assert premium_service.model_client.generate_response.called
        call_args = premium_service.model_client.generate_response.call_args
        context_arg = call_args[0][1]  # Second argument to generate_response
        assert "uploads" in context_arg
        assert len(context_arg["uploads"]) == 1
        assert context_arg["uploads"][0]["type"] == "csv"

# Chat Endpoint Tests
class TestChatEndpoints:
    @pytest.fixture
    def mock_current_user(self):
        return {"id": "test_user", "tier": "basic"}

    @pytest.fixture
    def mock_premium_user(self):
        return {"id": "premium_user", "tier": "premium"}

    @pytest.fixture
    def mock_context_orchestrator(self, mock_context):
        orchestrator = AsyncMock(spec=ContextOrchestrator)
        orchestrator.get_context.return_value = mock_context
        return orchestrator

    @pytest.fixture
    def mock_basic_chat_service(self, mock_context_orchestrator, event_manager):
        service = AsyncMock(spec=BasicChatService)
        service.exceeds_quota.return_value = False
        service.process.return_value = "Test response"
        return service

    @pytest.fixture
    def mock_premium_chat_service(self, mock_context_orchestrator, event_manager):
        service = AsyncMock(spec=PremiumChatService)
        service.process.return_value = "Test response"
        return service

    @pytest.fixture
    def mock_event_manager(self):
        """Create a mock event manager with pre-subscribed users."""
        manager = AsyncMock(spec=EventManager)
        manager.publish = AsyncMock()
        manager.subscribe = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_stream_endpoint(self, mock_current_user):
        """Test SSE stream endpoint."""
        with patch("app.api.v1.endpoints.chat.get_current_user", return_value=mock_current_user):
            from app.api.v1.endpoints.chat import stream_events
            response = await stream_events(current_user=mock_current_user)
            
            assert isinstance(response, EventSourceResponse)
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "no-cache"
            assert response.headers["Connection"] == "keep-alive"

    @pytest.mark.asyncio
    async def test_basic_chat_endpoint_success(
        self, mock_current_user, mock_basic_chat_service, mock_context_orchestrator, mock_event_manager
    ):
        """Test successful basic chat request."""
        with patch("app.api.v1.endpoints.chat.get_current_user", return_value=mock_current_user), \
             patch("app.api.v1.endpoints.chat.get_basic_chat_service", return_value=mock_basic_chat_service), \
             patch("app.api.v1.endpoints.chat.get_context_orchestrator", return_value=mock_context_orchestrator), \
             patch("app.api.v1.endpoints.chat.event_manager", mock_event_manager):
            
            from app.api.v1.endpoints.chat import basic_chat_endpoint
            background_tasks = MagicMock()
            
            response = await basic_chat_endpoint(
                prompt="How can I improve?",
                conversation_id="conv123",
                background_tasks=background_tasks,
                current_user=mock_current_user,
                chat_service=mock_basic_chat_service
            )
            
            assert response == {"status": "processing"}
            assert background_tasks.add_task.called
            assert mock_basic_chat_service.process.called
            assert mock_event_manager.publish.call_count >= 1

    @pytest.mark.asyncio
    async def test_basic_chat_endpoint_quota_exceeded(
        self, mock_current_user, mock_basic_chat_service, mock_event_manager
    ):
        """Test basic chat request with exceeded quota."""
        mock_basic_chat_service.exceeds_quota.return_value = True
        
        with patch("app.api.v1.endpoints.chat.get_current_user", return_value=mock_current_user), \
             patch("app.api.v1.endpoints.chat.get_basic_chat_service", return_value=mock_basic_chat_service), \
             patch("app.api.v1.endpoints.chat.event_manager", mock_event_manager):
            
            from app.api.v1.endpoints.chat import basic_chat_endpoint
            background_tasks = MagicMock()
            
            with pytest.raises(HTTPException) as exc_info:
                await basic_chat_endpoint(
                    prompt="How can I improve?",
                    conversation_id="conv123",
                    background_tasks=background_tasks,
                    current_user=mock_current_user,
                    chat_service=mock_basic_chat_service
                )
            
            assert exc_info.value.status_code == 429
            assert "quota exceeded" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_premium_chat_endpoint_success(
        self, mock_premium_user, mock_premium_chat_service, mock_context_orchestrator, mock_event_manager
    ):
        """Test successful premium chat request."""
        with patch("app.api.v1.endpoints.chat.get_current_user", return_value=mock_premium_user), \
             patch("app.api.v1.endpoints.chat.get_premium_chat_service", return_value=mock_premium_chat_service), \
             patch("app.api.v1.endpoints.chat.get_context_orchestrator", return_value=mock_context_orchestrator), \
             patch("app.api.v1.endpoints.chat.event_manager", mock_event_manager):
            
            from app.api.v1.endpoints.chat import premium_chat_endpoint
            background_tasks = MagicMock()
            
            response = await premium_chat_endpoint(
                prompt="Analyze my progress",
                conversation_id="conv123",
                background_tasks=background_tasks,
                file=None,
                current_user=mock_premium_user,
                chat_service=mock_premium_chat_service
            )
            
            assert response == {"status": "processing"}
            assert background_tasks.add_task.called
            assert mock_premium_chat_service.process.called
            assert mock_event_manager.publish.call_count >= 1

    @pytest.mark.asyncio
    async def test_premium_chat_endpoint_with_file(
        self, mock_premium_user, mock_premium_chat_service, mock_event_manager
    ):
        """Test premium chat request with file upload."""
        test_file = MagicMock()
        test_file.filename = "climbs.csv"
        test_file.read = AsyncMock(return_value=b"date,grade\n2024-02-20,V4")

        with patch("app.api.v1.endpoints.chat.get_current_user", return_value=mock_premium_user), \
             patch("app.api.v1.endpoints.chat.get_premium_chat_service", return_value=mock_premium_chat_service), \
             patch("app.api.v1.endpoints.chat.event_manager", mock_event_manager):

            from app.api.v1.endpoints.chat import premium_chat_endpoint
            background_tasks = MagicMock()

            response = await premium_chat_endpoint(
                prompt="Analyze my progress",
                conversation_id="conv123",
                background_tasks=background_tasks,
                file=test_file,
                current_user=mock_premium_user,
                chat_service=mock_premium_chat_service
            )

            assert response == {"status": "processing"}
            assert background_tasks.add_task.called
            assert test_file.read.called
            mock_premium_chat_service.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_and_events(
        self, mock_current_user, mock_basic_chat_service, mock_event_manager
    ):
        """Test error handling and event publishing during errors."""
        mock_basic_chat_service.process.side_effect = Exception("Test error")
        
        with patch("app.api.v1.endpoints.chat.get_current_user", return_value=mock_current_user), \
             patch("app.api.v1.endpoints.chat.get_basic_chat_service", return_value=mock_basic_chat_service), \
             patch("app.api.v1.endpoints.chat.event_manager", mock_event_manager):
            
            from app.api.v1.endpoints.chat import basic_chat_endpoint
            background_tasks = MagicMock()
            
            with pytest.raises(HTTPException) as exc_info:
                await basic_chat_endpoint(
                    prompt="How can I improve?",
                    conversation_id="conv123",
                    background_tasks=background_tasks,
                    current_user=mock_current_user,
                    chat_service=mock_basic_chat_service
                )
            
            assert exc_info.value.status_code == 500
            assert mock_event_manager.publish.call_count >= 1
            # Verify error event was published
            error_call = [call for call in mock_event_manager.publish.call_args_list if call[0][1] == EventType.ERROR]
            assert len(error_call) >= 1
