# Events and AI Services for SendSage Chat - Product Requirements Document (PRD)

**Date:** February 21, 2025  
**Author:** Grok 3 (xAI)

---

## Overview and Objectives

The `events` and `ai` services are pivotal components of SendSage's backend chat system, enabling real-time, AI-driven climbing coaching for Basic and Premium tiers. The `events` service uses Server-Sent Events (SSE) to deliver responsive updates, while the `ai` service manages interactions with Grok 2 (Basic tier, light reasoning) and Grok 3 (Premium tier, advanced reasoning with text-based uploads). These services integrate with the existing context system and D3.js visualizations, supporting SendSage's mission to transform climbing through personalized analytics and coaching.

### Objectives

- Deliver real-time feedback and tier-specific responses with granular event types.
- Provide affordable, concise coaching for Basic users and comprehensive, actionable guidance for Premium users.
- Scale to support 10,000 concurrent users within 12 months.
- Enhance user experience by linking chat responses to visualizations.

---

## Use Cases and User Scenarios

### Basic Tier

**Scenario:** Jane, a casual climber, asks, "How do I improve my bouldering?" She sees "Processing…" then receives, "Based on your V3 average, try finger strength drills twice a week."  
**Requirement:** Concise, single-step responses, limited to 10 queries/month, <500ms latency.

### Premium Tier

**Scenario:** Mark, a serious climber, asks, "Plan my V8 goal in 8 weeks." He sees "Processing…" followed by partial responses (e.g., "Week 1: 3 V5 sessions…"), ending with a full plan.  
**Scenario:** Mark uploads a CSV climb log and asks, "How's my progress?" He sees "Upload processed" then gets, "Your V5 sends are up 20%—focus on endurance next."  
**Requirement:** Detailed plans, text-based upload support (CSV, TXT, JSON), <1s text latency, <2s with uploads.

### Edge Cases

- **Quota Exceeded:** Jane exceeds 10 queries; sees, "Upgrade to Premium for unlimited coaching!"
- **Slow Response:** API lags; user sees, "Still working—hang tight!" after 1s.
- **Invalid Upload:** Mark uploads a malformed CSV; sees, "Your CSV needs a grade column—fix and retry."

---

## Detailed Functional Requirements

### `events/` Service

#### Purpose

Manage SSE for real-time chat updates, supporting concurrent users with granular, tier-specific events.

#### Files

- **`manager.py`**
  - **Class:** `EventManager`
  - **Functions:**
    - `subscribe(user_id: str)`: Yields events for a user.
    - `publish(user_id: str, event_type: str, content: dict, processing_time: float)`: Queues and sends events with metadata.
    - `disconnect(user_id: str)`: Cleans up subscriptions.
  - **Event Types:**
    - `"processing"`: {"status": "Processing..."}
    - `"partial_response"`: {"text": "Week 1: ..."} (Premium only, for streaming long answers)
    - `"response"`: {"text": "Here's your plan..."}
    - `"upload_processed"`: {"status": "Your CSV has been processed"} (Premium only)
    - `"visualization_suggestion"`: {"suggestion": "See your grade pyramid"} (both tiers)
    - `"error"`: {"error": "Upload failed—try a smaller file"}
  - **Metadata:**
    - `timestamp`: ISO format (e.g., "2025-02-21T10:00:00Z")
    - `response_length`: Characters in response (e.g., 150)
    - `processing_time`: Seconds (e.g., 0.45)

#### Example

```python
# app/services/chat/events/manager.py
from fastapi import Request
from sse_starlette.sse import EventSourceResponse
import asyncio
from uuid import uuid4
from datetime import datetime

class EventManager:
    def __init__(self):
        self.subscribers = {}
        self.message_queues = {}

    async def subscribe(self, user_id: str):
        if user_id not in self.subscribers:
            self.subscribers[user_id] = asyncio.Event()
            self.message_queues[user_id] = []
        while True:
            await self.subscribers[user_id].wait()
            while self.message_queues[user_id]:
                msg = self.message_queues[user_id].pop(0)
                yield {
                    "event": msg["type"],
                    "data": msg["content"],
                    "id": msg["id"],
                    "metadata": msg["metadata"]
                }
            self.subscribers[user_id].clear()

    async def publish(self, user_id: str, event_type: str, content: dict, processing_time: float = 0):
        if user_id in self.subscribers:
            msg_id = str(uuid4())
            metadata = {
                "timestamp": datetime.utcnow().isoformat(),
                "response_length": len(content.get("text", "")) if "text" in content else 0,
                "processing_time": processing_time
            }
            self.message_queues[user_id].append({
                "type": event_type,
                "content": content,
                "id": msg_id,
                "metadata": metadata
            })
            self.subscribers[user_id].set()
```

### `ai/` Service

#### Purpose

Handle AI model interactions, enforcing tier-specific constraints and processing text-based uploads (CSV, TXT, JSON).

#### Files

- **`model_client.py`**
  - **Classes:**
    - `ModelClient` (abstract): Defines `generate_response(prompt, context)`.
    - `Grok2Client`: Text-only, 4k token limit, light reasoning.
    - `Grok3Client`: Text-only, 128k token limit, advanced reasoning with uploads.
    - **Features:**
      - Async xAI API calls.
      - Fallback: Cached response or generic error on failure.
  - **`basic_chat.py`**  
     Class: BasicChatService
    - **Functions:**
      - `exceeds_quota(user_id)`: Checks Redis quota (10/month, resets 1st of month).
      - `process(user_id, prompt, conversation_id)`: Generates concise responses.
    - **Prompt:**

```plaintext
You are a friendly climbing coach. Your role is to provide concise, conversational advice to climbers based on their recent climbing history and goals. You have access to a context that includes their climbing profile, performance trends, training habits, health status, and goals. The context has a 'summary' field that gives a human-readable overview of the climber's situation. Focus on the user's last 10 climbs and their goals from the context. Provide advice that is straightforward and easy to understand, without detailed planning or multi-step reasoning. Keep your language simple and engaging.

- Do not ask for additional information or clarification; base your response solely on the provided context and query.
- If the context does not provide sufficient information to answer the query, provide general advice based on typical climber experiences at their level.
- Use the 'summary' field to understand the climber's experience level and tailor your advice accordingly.
- Do not reveal any personally identifiable information from the context.
- When appropriate, suggest that the user checks their D3.js visualizations for more insights, e.g., "See your grade pyramid for performance progress."
- Ensure that your advice is safe, healthy, and respectful.
- Present your response as a single, concise paragraph for easy reading.
```

- **`premium_chat.py`**
  - **Class:** `PremiumChatService`
  - **Functions:**
    - `preprocess_file(file, filename)`: Parses CSV/TXT/JSON uploads.
    - `process(user_id, prompt, conversation_id, file, filename)`: Generates detailed responses.
  - **Prompt:**

```plaintext
You are an expert climbing coach. You have access to a comprehensive context that includes the climber's full climbing history, performance metrics, training data, health status, goals, and any uploaded data. The context has a 'summary' field that provides a human-readable overview of the climber's situation. Your task is to use this context to provide detailed, step-by-step advice and plans based on the user's query. Analyze all parts of the context to offer personalized, actionable recommendations. Present your advice in a friendly, engaging manner, ensuring that it's clear and easy to follow.

- If the query is vague or lacks key details, you can ask targeted clarifying questions to refine your advice. Remember that the user may respond in a separate query.
- Provide your advice in a structured format that is easy to follow, such as bullet points or step-by-step lists when appropriate, especially for plans or detailed recommendations.
- Use the 'summary' field to understand the climber's experience level and tailor your advice accordingly.
- Do not reveal any personally identifiable information from the context.
- If you are unsure about any part of your advice, indicate that and provide the best possible information based on the context, e.g., "I'm not certain about your recent training, but based on your goals, try this..."
- When relevant, suggest that the user checks their D3.js visualizations for further insights, e.g., "Check your training trends for more details."
- Ensure that your advice is safe, healthy, and respectful.
```

**Example:**

```python
# app/services/chat/ai/premium_chat.py
from .model_client import Grok3Client
from ..context.orchestrator import ContextManager
import csv
import json
from io import StringIO

class PremiumChatService:
    def __init__(self, context_manager: ContextManager):
        self.model = Grok3Client()
        self.context_manager = context_manager

    async def preprocess_file(self, file: bytes, filename: str) -> dict:
        content = file.decode("utf-8")
        if filename.endswith(".csv"):
            reader = csv.DictReader(StringIO(content))
            if "grade" not in reader.fieldnames:
                raise ValueError("CSV needs a grade column")
            return list(reader)
        elif filename.endswith(".txt"):
            return {"text": content}
        elif filename.endswith(".json"):
            data = json.loads(content)
            if not isinstance(data, (dict, list)):
                raise ValueError("JSON must be an object or array")
            return data
        raise ValueError("Unsupported file type")

    async def process(self, user_id: str, prompt: str, conversation_id: str, file: bytes = None, filename: str = None):
        context = await self.context_manager.get_context(user_id, conversation_id)
        if file:
            upload_data = await self.preprocess_file(file, filename)
            context["uploads"].append(upload_data)
            await event_manager.publish(user_id, "upload_processed", {"status": f"Your {filename.split('.')[-1]} has been processed"})
        system_prompt = (
            "You're an expert climbing coach. Use all context (logbook, goals, uploads). "
            "Provide detailed, actionable advice with reasoning, in a friendly tone."
        )
        full_prompt = f"{system_prompt}\n\nUser: {prompt}"
        return await self.model.generate_response(full_prompt, context)
```

### Non-Functional Requirements

#### Performance

- Basic: <500ms response time.
- Premium: <1s (text), <2s (with uploads).
- Event Delivery: <100ms after response generation.

#### Scalability

Support 10,000 concurrent users with Redis-backed queues and load-balanced FastAPI instances.

#### Security

- Rate Limiting: 10 req/min (Basic), 100 req/min (Premium).
- Encryption: TLS/HTTPS for API calls, encrypt uploads in transit/at rest.

#### Monitoring

- Log event latency, AI response times, error rates, quota usage.
- Alerts: >5% error rate, latency >2s.

#### Integration

- With context/: Fetch unified JSON via ContextManager.
- With API: /chat/basic and /chat/premium use EventManager to stream responses.
- With Visualizations: Suggest D3.js links (e.g., "Check your grade pyramid").

#### Testing

- Unit Tests: Event queuing, quota enforcement, file preprocessing.
- Integration Tests: SSE streaming, AI response accuracy with uploads.
- Performance Tests: 10,000 users, <500ms Basic latency.

## Implementation Plan

### Project Overview

- **Goal:** Implement the events and ai services to deliver real-time, AI-driven climbing coaching for SendSage's Basic and Premium tiers.
- **Timeline:** March 1, 2025 - April 11, 2025 (6 weeks, 5 sprints).
- **Team:**
  - Backend Developer 1 (BD1): Events and core AI logic.
  - Backend Developer 2 (BD2): AI model integration and preprocessing.
  - Frontend Developer (FD): SSE integration with Next.js UI.
  - QA Engineer (QA): Testing and validation.
  - DevOps Engineer (DE): Scalability, monitoring setup.
- **Assumptions:**
  - Context system (ContextManager) is implemented and provides unified JSON context.
  - xAI API for Grok 2 and Grok 3 is available by March 1, 2025.
  - Redis and FastAPI infrastructure are in place.

### Sprint Breakdown

#### Sprint 1: Event Manager Implementation (March 1 - March 7, 2025)

**Goal:** Build the foundational events service with basic SSE functionality.

**Tasks:**

1. **Implement EventManager Class (BD1, 3 days, Mar 1-3)**

   - Develop subscribe, publish, and disconnect methods in app/services/chat/events/manager.py.
   - Support basic event types: "processing", "response", "error" with metadata.
   - Use Redis for queue persistence (initial setup).
   - Dependencies: FastAPI, sse-starlette library.

2. **Set Up SSE Endpoint (BD1, 2 days, Mar 4-5)**

   - Create /stream endpoint in app/api/v1/endpoints/chat.py.
   - Integrate with existing JWT authentication.
   - Dependencies: Context system for user_id.

3. **Frontend SSE Integration (FD, 2 days, Mar 4-5)**

   - Update Next.js chat UI to subscribe to /stream.
   - Display "processing" and "response" events.
   - Dependencies: /stream endpoint.

4. **Unit Tests (QA, 2 days, Mar 6-7)**
   - Test event queuing and delivery for 100 concurrent users.
   - Verify metadata accuracy (e.g., timestamp format).
   - Dependencies: EventManager implementation.

**Deliverables:**

- Working EventManager with basic event types.
- SSE endpoint and initial frontend integration.

**Risks and Mitigation:**

- Risk: SSE scalability issues with many subscribers.
- Mitigation: Use Redis to offload queue management; test with 100 users initially.

#### Sprint 2: Basic AI Service and Quota Logic (March 8 - March 14, 2025)

**Goal:** Implement model_client.py and basic_chat.py with quota enforcement.

**Tasks:**

1. **Develop ModelClient Base (BD2, 2 days, Mar 8-9)**

   - Create abstract ModelClient class and Grok2Client.
   - Mock xAI API calls with dummy responses.
   - Dependencies: xAI API documentation.

2. **Implement BasicChatService (BD1, 3 days, Mar 10-12)**

   - Build exceeds_quota and process methods.
   - Integrate with ContextManager for context retrieval.
   - Use Redis for quota tracking.
   - Add system prompt as per PRD.
   - Dependencies: ModelClient, Context system.

3. **Basic Chat Endpoint (BD1, 2 days, Mar 11-12)**

   - Create /chat/basic endpoint.
   - Publish events via EventManager.
   - Dependencies: BasicChatService, EventManager.

4. **Unit and Integration Tests (QA, 2 days, Mar 13-14)**
   - Test quota enforcement.
   - Verify <500ms latency with mock API.
   - Dependencies: BasicChatService, endpoint.

**Deliverables:**

- Functional model_client.py with Grok 2 mock.
- basic_chat.py with quota logic and endpoint integration.

**Risks and Mitigation:**

- Risk: xAI API not ready.
- Mitigation: Use mock responses; switch to real API in Sprint 5.

#### Sprint 3: Premium AI Service and Upload Parsing (March 15 - March 21, 2025)

**Goal:** Implement premium_chat.py with upload support and event integration.

**Tasks:**

1. **Extend ModelClient for Grok 3 (BD2, 2 days, Mar 15-16)**

   - Add Grok3Client with 128k token support.
   - Mock API calls with upload handling.
   - Dependencies: ModelClient base.

2. **Develop PremiumChatService (BD2, 3 days, Mar 17-19)**

   - Implement preprocess_file and process methods.
   - Parse CSV, TXT, JSON uploads with validation.
   - Integrate with ContextManager and append uploads.
   - Use system prompt from PRD.
   - Dependencies: Grok3Client, Context system.

3. **Premium Chat Endpoint and Events (BD1, 2 days, Mar 18-19)**

   - Create /chat/premium endpoint.
   - Add "partial_response" and "upload_processed" events.
   - Dependencies: PremiumChatService, EventManager.

4. **Integration Tests (QA, 2 days, Mar 20-21)**
   - Test upload parsing (valid/invalid files).
   - Verify SSE streaming (partial responses).
   - Dependencies: PremiumChatService, endpoint.

**Deliverables:**

- premium_chat.py with upload parsing.
- Premium endpoint with granular events.

**Risks and Mitigation:**

- Risk: Upload parsing errors delay integration.
- Mitigation: Start with TXT parsing, expand to CSV/JSON incrementally.

## Conclusion

This PRD defines a scalable, user-centric events and ai system for SendSage, delivering real-time, tiered coaching with Grok 2 and Grok 3. Granular events, precise AI constraints, and text-based upload support ensure a robust implementation aligned with your climbing analytics vision.
