# Sagechat AI Chat Feature - Product Requirements Document (PRD)

**Date:** 2/5/2025  
**Author:** Isaac Rubey

## 1. Overview and Objectives

The AI chat feature for SendSage is designed to provide climbers with a highly contextualized coaching experience. The system must cater to both free (standard) and premium users by combining immediate, friendly conversational responses with the option for deep, multi-step analysis. It leverages two AI models: **Deepseek V3** for conversational engagement and **R1 Advanced Reasoning** for technical, data-driven insights. The feature integrates user performance metrics, historical climbing data, and custom instructions to create personalized training recommendations and coaching advice.

## 2. Use Cases and User Scenarios

The system supports distinct experiences for free and premium users, with a streamlined onboarding process.

### Basic Users

- **Scenario:** Jane, a casual climber, asks, "How do I improve my bouldering?" Sagechat uses her last 5 logged climbs (e.g., V3 average) to suggest 2-3 beginner-friendly drills.
- **Requirement:** Clear, friendly responses incorporating basic climbing history (e.g., total climbs, favorite discipline).

### Premium Users

- **Scenario:** Mark, a serious climber, asks, "Plan my next 8 weeks for a V8 goal." Sagechat:
  - Responds conversationally ("Great goal, Mark! Let's build a plan…").
  - Concurrently evaluates complexity (detects "plan" and "goal").
  - Invokes R1 for a detailed 8-week schedule (e.g., 3 climbing days/week, 2 rest days).
  - Polishes with Deepseek V3 ("Here's your plan—start with V5 endurance this week!").
- **Requirement:** Dual-call mechanism with advanced reasoning for multi-step queries.

### Onboarding Process

- **Options:**
  - Connect Mountain Project logbook (auto-populates ClimberSummary with grades, total climbs).
  - Upload files (CSV, PDF logbooks; max 10MB) to enrich context.
- **Edge Case:** If data is missing (e.g., no grades), prompt: "Add your latest climb to get started!"

### Edge Cases

- **No History:** New users receive generic tips until data is added.
- **Tier Switch:** Mid-conversation premium upgrade unlocks advanced features seamlessly.

## 3. Detailed Functional Requirements

### Core Functions

#### Dual Interaction Modes

- Primary section with welcoming message
- Dedicated settings area for custom instructions and context uploads
- Conditional linking to logbook connection or visualization dashboard

#### Context Injection

- **Deepseek V3**: User-friendly performance metrics and coaching instructions
- **R1 Module**: Structured JSON payload with performance data, historical logs, and metrics

#### Premium Query Processing

- Parallel API calls
- Advanced reasoning evaluation
- R1 module integration
- Final Deepseek V3 polish

#### Middleware Logic and Error Handling

- Keyword examination
- Complexity indicators
- Default fallback mechanisms
- Error logging

#### User Interface Integration

- Visual differentiation between response types
- Premium indicators
- Expandable detailed views

#### Event-Driven Architecture with SSE (NEW)

The system implements an event-driven architecture using FastAPI's SSE support for real-time updates:

```python
# app/services/events/manager.py
from typing import Dict, Any, AsyncIterator
from fastapi import Request
from sse_starlette.sse import EventSourceResponse
import asyncio

class EventManager:
    def __init__(self):
        self.subscribers: Dict[str, asyncio.Event] = {}
        self.message_queues: Dict[str, list] = {}

    async def subscribe(
        self,
        user_id: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """Creates a new subscription for SSE updates"""
        if user_id not in self.subscribers:
            self.subscribers[user_id] = asyncio.Event()
            self.message_queues[user_id] = []

        while True:
            # Wait for new messages
            await self.subscribers[user_id].wait()

            # Process queued messages
            while self.message_queues[user_id]:
                message = self.message_queues[user_id].pop(0)
                yield {
                    "event": message["type"],
                    "data": message["content"],
                    "id": message["id"]
                }

            # Reset event for next update
            self.subscribers[user_id].clear()

    async def publish(
        self,
        user_id: str,
        message_type: str,
        content: Dict[str, Any],
        message_id: str
    ) -> None:
        """Publishes a new event to subscribed clients"""
        if user_id in self.subscribers:
            self.message_queues[user_id].append({
                "type": message_type,
                "content": content,
                "id": message_id
            })
            self.subscribers[user_id].set()

# app/api/v1/endpoints/chat.py
from fastapi import APIRouter, Request, Depends
from sse_starlette.sse import EventSourceResponse

router = APIRouter()
event_manager = EventManager()

@router.get("/stream")
async def stream_chat(
    request: Request,
    user_id: str = Depends(get_current_user)
) -> EventSourceResponse:
    """SSE endpoint for streaming chat updates"""
    return EventSourceResponse(
        event_manager.subscribe(user_id)
    )

@router.post("/message")
async def process_message(
    message: ChatMessage,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Processes chat message and triggers SSE updates"""
    # Process message asynchronously
    background_tasks.add_task(
        process_chat_message,
        user_id,
        message,
        event_manager
    )

    return {"status": "processing"}

async def process_chat_message(
    user_id: str,
    message: ChatMessage,
    event_manager: EventManager
) -> None:
    """Background task for processing chat messages"""
    try:
        # Initial response
        await event_manager.publish(
            user_id=user_id,
            message_type="processing_started",
            content={"status": "Processing your request..."},
            message_id="process_start"
        )

        # Get basic response
        basic_response = await get_basic_response(message)
        await event_manager.publish(
            user_id=user_id,
            message_type="basic_response",
            content=basic_response,
            message_id="basic_complete"
        )

        # For premium users, get advanced analysis
        if is_premium_user(user_id):
            advanced_response = await get_advanced_response(message)
            await event_manager.publish(
                user_id=user_id,
                message_type="advanced_response",
                content=advanced_response,
                message_id="advanced_complete"
            )

    except Exception as e:
        await event_manager.publish(
            user_id=user_id,
            message_type="error",
            content={"error": str(e)},
            message_id="error"
        )
```

This implementation provides several key benefits:

1. **Real-Time Updates**

   - Immediate feedback on request processing
   - Progressive response delivery
   - Streaming of long-running analyses

2. **Asynchronous Processing**

   - Non-blocking message handling
   - Background task management
   - Graceful error handling

3. **State Management**

   - Per-user event queues
   - Efficient message delivery
   - Clean connection handling

4. **Premium Features**
   - Tiered response streaming
   - Advanced analysis progress updates
   - Seamless basic/premium transitions

The SSE integration allows for:

- Immediate user feedback
- Progressive UI updates
- Real-time analysis streaming
- Efficient server resource usage

## 4. Non-Functional Requirements

### Performance and Latency

- Standard queries: <1 second response
- Premium queries: 2-3 second complete response
- Strict timeout thresholds

### Scalability and Concurrency

- Support for concurrent API calls
- High load adaptation
- Premium user dual request handling

### Security and Data Handling

- TLS/HTTPS encryption
- Role-based access controls
- Data sanitization
- PII masking in logs

### Logging and Monitoring

- Structured logs with correlation IDs
- Response time tracking
- Error rate monitoring
- Resource utilization metrics

## 5. System Architecture and Integration

### Frontend (Chat Interface)

- Template integration
- Real-time indicators
- Advanced reasoning progress display

### Backend Logic (Middleware)

- User type inspection
- Query complexity routing
- Service orchestration

### Core Modules

1. Conversational Deepseek V3 Module
2. Premium Query Evaluation Module
3. R1 Advanced Reasoning Module
4. Deepseek V3 Response Enhancement Module

### Database & Integration Services

- Model integration with app/models.py
- Mountain Project data ingestion
- Storage service bridging

### Implementation Structure

The codebase follows a modular architecture with clear separation of concerns:

```plaintext
app/
├── services/
│   ├── ai/
│   │   ├── base/
│   │   │   ├── model_client.py     # Abstract base class for model clients
│   │   │   └── exceptions.py       # Custom exception hierarchy
│   │   ├── chat/
│   │   │   ├── conversational.py    # Handles conversational responses
│   │   │   ├── evaluator.py         # Query complexity evaluation
│   │   │   ├── orchestrator.py      # Main chat flow coordination
│   │   │   ├── reasoning.py         # Advanced reasoning logic
│   │   │   └── response_enhancer.py # Output polish and enhancement
│   │   ├── model_wrappers/
│   │   │   ├── r1_client.py        # R1 Advanced Reasoning client
│   │   │   └── v3_client.py        # Deepseek V3 client implementation
│   │   ├── state/
│   │   │   ├── manager.py          # Redis-backed state management
│   │   │   └── repository.py       # Context data access layer
│   │   └── prompt_manager.py       # System prompt management
│   ├── context/
│   │   ├── context_formatter.py    # User data and metrics formatting
│   │   └── data_integrator.py     # External data integration
│   ├── monitoring/
│   │   ├── metrics.py             # Telemetry and metrics collection
│   │   └── circuit_breaker.py     # Service resilience patterns
│   ├── payment/
│   │   └── stripe_handler.py      # Premium user payment processing
│   └── user/
       └── user_service.py         # User management and authentication
```

Key service modules:

- **AI Services**: Implements the core chat functionality with separate modules for each responsibility
- **Context Services**: Handles data formatting and integration from external sources
- **Payment Services**: Manages premium user subscriptions
- **User Services**: Handles user authentication and management

### Key Components

#### Model Abstraction Layer (NEW)

The system implements a robust abstraction layer for AI model interactions:

```python
# app/services/ai/base/model_client.py
class BaseModelClient(ABC):
    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        context: dict,
        stream: bool = False
    ) -> Union[str, AsyncIterator[str]]:
        pass

    @abstractmethod
    async def validate_response(
        self,
        response: str
    ) -> bool:
        pass
```

#### State Management (NEW)

Redis-backed state management for conversation history and context:

```python
# app/services/ai/state/manager.py
class StateManager:
    def __init__(
        self,
        redis_client: Redis,
        ttl: int = 3600
    ):
        self.redis = redis_client
        self.ttl = ttl

    async def get_conversation_state(
        self,
        conversation_id: str
    ) -> Dict[str, Any]:
        return await self.redis.get(f"conv:{conversation_id}")

    async def update_state(
        self,
        conversation_id: str,
        new_state: Dict[str, Any]
    ) -> None:
        await self.redis.setex(
            f"conv:{conversation_id}",
            self.ttl,
            json.dumps(new_state)
        )
```

#### Error Handling (NEW)

Comprehensive error handling system:

```python
# app/services/ai/base/exceptions.py
class ChatServiceError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        details: Dict = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}

class ModelError(ChatServiceError):
    pass

class StateError(ChatServiceError):
    pass

class RateLimitError(ChatServiceError):
    pass
```

#### Context Repository Pattern (NEW)

The system implements a repository pattern for context management to decouple data access from business logic:

````python
# app/services/context/repository.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class ContextRepository(ABC):
    @abstractmethod
    async def get_user_context(
        self,
        user_id: str,
        include_history: bool = True
    ) -> Dict[str, Any]:
        """Retrieves user's context including climbing history and preferences"""
        pass

    @abstractmethod
    async def update_user_context(
        self,
        user_id: str,
        context_update: Dict[str, Any],
        partial: bool = True
    ) -> None:
        """Updates user context with new information"""
        pass

    @abstractmethod
    async def get_conversation_context(
        self,
        conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieves specific conversation context"""
        pass

class PostgresContextRepository(ContextRepository):
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_user_context(
        self,
        user_id: str,
        include_history: bool = True
    ) -> Dict[str, Any]:
        """
        Implements context retrieval from PostgreSQL using SQLAlchemy
        Aggregates:
        - User preferences
        - Climbing metrics
        - Training history
        - Goals and progression
        """
        pass

class RedisContextRepository(ContextRepository):
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def get_conversation_context(
        self,
        conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Implements fast conversation context retrieval from Redis
        Handles:
        - Short-term conversation state
        - Recent interactions
        - Temporary context modifications
        """
        pass

class UnitOfWork:
    def __init__(
        self,
        postgres_repo: PostgresContextRepository,
        redis_repo: RedisContextRepository
    ):
        self.postgres = postgres_repo
        self.redis = redis_repo
        self._transaction = None

    async def __aenter__(self):
        self._transaction = await self.postgres.db.begin()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self._transaction.rollback()
        else:
            await self._transaction.commit()

class ContextService:
    def __init__(self, unit_of_work: UnitOfWork):
        self.uow = unit_of_work

    async def get_enriched_context(
        self,
        user_id: str,
        conversation_id: str
    ) -> Dict[str, Any]:
        """
        Combines persistent and temporary context using Unit of Work
        Ensures data consistency across repositories
        """
        async with self.uow as transaction:
            user_context = await transaction.postgres.get_user_context(user_id)
            conv_context = await transaction.redis.get_conversation_context(conversation_id)

            return {
                **user_context,
                **(conv_context or {})
            }

## 6. User Experience Flow

- Personalized welcome messages
- Context-aware interactions
- Premium feature indicators
- Settings control panel
- Conditional data visualization

## 7. API, Middleware, and Error Handling

### API Endpoints

- POST /sage-chat/message
  - user_prompt
  - is_first_message
  - conversation_history
  - use_reasoner
- POST /sage-chat/onboard

### Middleware Functions

- Query complexity detection
- Dual Deepseek V3 call management
- Output validation and merging
- Fallback logic implementation

## 8. Testing and Acceptance Criteria

### Verification Requirements

- Context handling accuracy
- Query complexity routing
- Parallel execution performance
- UI indicator functionality
- Error fallback reliability
- Comprehensive test coverage

## 9. Security and Monitoring

### Security Measures

- Data encryption (transit and rest)
- Content sanitization
- API interaction logging
- System health monitoring

## 10. System Prompts

### Conversational Deepseek V3 - General Interaction

This prompt ensures a warm, engaging tone with context-aware advice.

```plaintext
You are Sage, a friendly and knowledgeable AI climbing coach. Your role is to engage users in natural conversation while offering personalized climbing advice based on their performance metrics and climbing history. Keep your responses clear, supportive, and engaging. Integrate provided user data seamlessly, and never reveal internal reasoning or chain-of-thought.
````

### Premium Query Gateway Deepseek V3 - Evaluation Mode

This prompt instructs Deepseek V3 to analyze the query for complexity.

```plaintext
You are acting as an evaluation layer for premium user queries. Analyze the user prompt for complexity and the need for multi-step reasoning. If the query involves detailed planning, extensive data analysis, or in-depth technical insights—indicated by keywords like "detailed", "step-by-step", or "comprehensive"—output only "advanced reasoning needed". Otherwise, output "normal response sufficient". Do not generate a final answer.
```

### Advanced Reasoning Deepseek-r1

This prompt instructs the advanced reasoning engine to produce a robust technical output.

```plaintext
You are an advanced reasoning engine designed for deep, multi-step analysis and complex data integration. Your task is to consider all provided contextual data (climbing performance, historical logs, user goals) and generate a detailed, technically robust plan or answer. Perform your internal reasoning privately and do not disclose your chain-of-thought. Present your final output clearly and concisely.
```

### Response Enhancement Deepseek V3 - Polish the r1 output

This prompt instructs Deepseek V3 to translate technical analysis into accessible language.

```plaintext
You are a conversational specialist tasked with translating a highly technical analysis into an engaging and easily digestible explanation. Given the advanced reasoning output, rephrase and present the key insights in a friendly, approachable tone. Clearly communicate actionable items without including any internal chain-of-thought details.
```

## 11.Data Model Fields and Data Integration

To fully support the AI chat feature, it is essential to detail the key data models that provide the contextual information required for both conversational interactions and advanced, data-driven reasoning. This section outlines the relevant models and fields as defined in `app/models.py` and describes how they integrate into the chat system.

The **User** model serves as the core identity for the climber. Important fields include the unique user identifier, username, and email, which are used for authentication and personalization. The `tier` field and associated payment status flags (such as `stripe_subscription_id` and `payment_status`) determine whether a user is eligible for premium features. These fields directly influence the routing logic—for example, a premium user will trigger the dual-call mechanism that evaluates query complexity.

The **ClimberSummary** model provides a comprehensive snapshot of the user's climbing performance and training context. Critical fields such as `highest_sport_grade_tried`, `highest_trad_grade_tried`, and `highest_boulder_grade_tried` represent historical performance metrics. Other fields, including `total_climbs`, `favorite_discipline`, and training context indicators (like `training_frequency` and `typical_session_length`), supply the data needed for generating personalized advice. Moreover, lifestyle and health indicators, such as `sleep_score` and `nutrition_score`, alongside qualitative factors like `injury_history` and `climbing_goals`, allow the AI to consider the full spectrum of user context. JSON fields (for example, `grade_pyramid_sport` and `current_projects`) ensure that structured data is available for advanced reasoning in a machine-friendly format.

Additional models further enhance the contextual data available for the chat feature. The **UserTicks** model captures historical climb data and performance outcomes, enriching the context passed to both the conversational and advanced reasoning modules. Similarly, the **PerformancePyramid** model provides granular performance metrics related to route attempts and performance trends, which can be leveraged to tailor technical analysis. Finally, the **UserUpload** model serves as a repository for external data sources such as spreadsheets or text logbooks provided by users, augmenting the automatically ingested data from Mountain Project integrations.

By integrating these models, the AI chat system can dynamically construct context payloads. For example, a summarized textual context derived from the ClimberSummary model is injected into Deepseek V3's conversational prompt, while a detailed JSON structure—comprising performance metrics, historical logs from UserTicks, and additional insights from PerformancePyramid—is used by the R1 module for rigorous multi-step processing. This division ensures that each AI component receives the form of data it requires, thereby maintaining clarity and consistency across the entire feature.

In summary, the above data model fields underpin the contextual intelligence of the chat service, enabling both immediate conversational responses and deep, technical analysis tailored to each climber's unique performance profile.

## 12. Implimentation Plan

1. **Data Integration and Context Management:**  
   Integrate data models (as outlined in `app/models.py`) by building modules in `services/context/` that extract and format essential fields (e.g., ClimberSummary metrics, UserTicks history). Ensure these modules generate both a concise human-friendly summary and a structured JSON payload for advanced reasoning.

- Create a `context_formatter.py` module in `services/context/` that extracts and formats the necessary fields from the ClimberSummary model.
- Create a `data_integrator.py` module in `services/context/` that integrates the formatted data from the ClimberSummary model with the UserTicks model to create a structured JSON payload for advanced reasoning.

2. **Core Chat Service Modules:**  
   In `services/ai/chat/`, implement:  
   • **Orchestrator:** `orchestrator.py` Coordinates query routing, invokes the conversational module, evaluator, advanced reasoning, and final polish in a dual-call mechanism for premium users.  
   • **Conversational Module:** `conversational.py` Handles Deepseek V3 calls for natural, everyday conversation.  
   • **Evaluator Module:** `evaluator.py` Uses Deepseek V3 (with specially crafted prompts) to examine queries for complexity and flag if advanced reasoning is needed.  
   • **Reasoning Module:** `reasoning.py` Communicates with the R1 API to perform deep, multi-step analysis using the structured context.  
   • **Response Enhancer:** `response_enhancer.py` Uses Deepseek V3 to polish the output from R1, translating technical details into a conversational narrative.

3. **Model Wrappers and Prompt Management:**  
   Develop API abstraction layers in `services/ai/model_wrappers/` for Deepseek V3 and R1. Centralize the system prompts for each module in `services/ai/prompt_manager.py`, enabling version control and easy updates.

4. **Middleware and Routing Logic:**  
   Build middleware logic `orchestrator.py` to identify user tier (standard vs. premium) and execute dual parallel calls for premium users. This layer will decide based on the evaluator's output whether to route the request through the advanced reasoning path or simply return the conversational response.

5. **User Interface Integration:**  
   Update chat templates (located in `templates/chat/`) to provide visual indicators for premium advanced analysis (e.g., an expandable section labeled "Expert Analysis") and integrate onboarding flows for external data (such as Mountain Project logbooks or file uploads).

## 13. Conclusion

This PRD serves as the definitive guide for implementing SendSage's AI chat feature, combining user-friendly conversation with advanced technical analysis. It provides comprehensive direction for API design, middleware orchestration, prompt management, and user experience integration, ensuring alignment with SendSage's strategic objectives.

#### Error Handling and Logging Architecture (NEW)

The chat system integrates with SendSage's centralized error handling and logging infrastructure:

```python
# app/services/ai/chat/exceptions.py
from app.core.exceptions import SendSageException
from fastapi import status

class ChatServiceError(SendSageException):
    """Base exception for chat service errors"""
    def __init__(
        self,
        detail: str = "Chat service error",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            context=context
        )

class ModelResponseError(ChatServiceError):
    """Raised when AI model response fails validation or generation"""
    def __init__(
        self,
        model_name: str,
        error_type: str,
        detail: str = "Model response error",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        context = context or {}
        context.update({
            "model_name": model_name,
            "error_type": error_type
        })
        super().__init__(detail=detail, context=context)

class StreamDisconnectedError(ChatServiceError):
    """Raised when SSE stream connection is lost"""
    def __init__(
        self,
        user_id: str,
        detail: str = "Stream connection lost",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        context = context or {}
        context.update({
            "user_id": user_id,
            "connection_type": "sse"
        })
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            context=context
        )

# app/services/ai/chat/error_handlers.py
from app.core.error_handlers import create_error_response
from app.core.logging import logger

async def chat_service_error_handler(
    request: Request,
    exc: ChatServiceError
) -> JSONResponse:
    """Handle chat service specific errors with detailed logging"""
    logger.error(
        f"Chat service error: {exc.detail}",
        extra={
            "error_type": exc.__class__.__name__,
            "path": request.url.path,
            "method": request.method,
            **exc.context
        }
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            status_code=exc.status_code,
            message=exc.detail,
            error_type=exc.__class__.__name__,
            details=exc.context
        )
    )

# app/services/ai/chat/orchestrator.py
class ChatOrchestrator:
    def __init__(self):
        self.logger = logger.bind(
            service="chat_orchestrator",
            component="ai"
        )

    async def process_message(
        self,
        user_id: str,
        message: ChatMessage,
        event_manager: EventManager
    ) -> None:
        """Process chat message with comprehensive error handling and logging"""
        correlation_id = str(uuid.uuid4())

        try:
            self.logger.info(
                "Processing chat message",
                extra={
                    "correlation_id": correlation_id,
                    "user_id": user_id,
                    "message_type": message.type
                }
            )

            # Initial response
            await event_manager.publish(
                user_id=user_id,
                message_type="processing_started",
                content={"status": "Processing your request..."},
                message_id=correlation_id
            )

            try:
                # Get basic response with timeout
                async with timeout(3.0):  # 3 second timeout
                    basic_response = await self.get_basic_response(message)
            except asyncio.TimeoutError as e:
                raise ModelResponseError(
                    model_name="deepseek_v3",
                    error_type="timeout",
                    detail="Basic response generation timed out",
                    context={"timeout_seconds": 3.0}
                )

            self.logger.debug(
                "Basic response generated",
                extra={
                    "correlation_id": correlation_id,
                    "response_length": len(basic_response)
                }
            )

            await event_manager.publish(
                user_id=user_id,
                message_type="basic_response",
                content=basic_response,
                message_id=f"{correlation_id}_basic"
            )

            # Premium user handling
            if await self.is_premium_user(user_id):
                try:
                    # Get advanced analysis with longer timeout
                    async with timeout(10.0):  # 10 second timeout
                        advanced_response = await self.get_advanced_response(
                            message,
                            basic_response
                        )
                except asyncio.TimeoutError as e:
                    self.logger.warning(
                        "Advanced analysis timed out",
                        extra={
                            "correlation_id": correlation_id,
                            "timeout_seconds": 10.0
                        }
                    )
                    # Don't raise - fallback to basic response
                    advanced_response = {
                        "error": "Advanced analysis timed out",
                        "fallback": basic_response
                    }

                await event_manager.publish(
                    user_id=user_id,
                    message_type="advanced_response",
                    content=advanced_response,
                    message_id=f"{correlation_id}_advanced"
                )

        except ModelResponseError as e:
            self.logger.error(
                f"Model error: {str(e)}",
                extra={
                    "correlation_id": correlation_id,
                    "error_type": e.__class__.__name__,
                    **e.context
                }
            )
            await event_manager.publish(
                user_id=user_id,
                message_type="error",
                content={"error": str(e)},
                message_id=f"{correlation_id}_error"
            )

        except StreamDisconnectedError as e:
            self.logger.warning(
                f"Stream disconnected: {str(e)}",
                extra={
                    "correlation_id": correlation_id,
                    "error_type": e.__class__.__name__,
                    **e.context
                }
            )
            # No publish attempt - stream is disconnected

        except Exception as e:
            self.logger.exception(
                f"Unexpected error in chat processing: {str(e)}",
                extra={
                    "correlation_id": correlation_id,
                    "error_type": e.__class__.__name__
                }
            )
            await event_manager.publish(
                user_id=user_id,
                message_type="error",
                content={"error": "An unexpected error occurred"},
                message_id=f"{correlation_id}_error"
            )
```

The error handling architecture provides:

1. **Custom Exception Hierarchy**

   - Extends `SendSageException` base class
   - Specialized exceptions for chat scenarios
   - Context-rich error information
   - Proper HTTP status code mapping

2. **Structured Logging**

   - Correlation IDs for request tracking
   - Contextual metadata for each log entry
   - Different log levels for various scenarios
   - Separate log files for different concerns

3. **Error Recovery Strategies**

   - Graceful degradation for premium features
   - Automatic fallback to basic responses
   - Timeout handling for model calls
   - Stream disconnection management

4. **Monitoring Integration**
   - Error rate tracking
   - Response time monitoring
   - Model performance metrics
   - User experience indicators

Key logging patterns:

1. **Operation Logging**

   - Start/end of message processing
   - Model response generation
   - Stream connection status
   - Performance metrics

2. **Error Logging**

   - Model failures with context
   - Stream disconnections
   - Timeout occurrences
   - Unexpected exceptions

3. **Debug Information**
   - Response lengths
   - Processing times
   - Queue states
   - Connection details

The system integrates with SendSage's existing logging infrastructure through:

- Centralized logger configuration
- Common log formatting
- Unified error response creation
- Consistent exception handling
