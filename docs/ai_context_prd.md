# Context System for AI Chat Feature - Product Requirements Document (PRD)

**Date:** February 20, 2025  
**Author:** Grok 3 (xAI)

## 1. Overview and Objectives

The context system is a critical component of the AI chat feature in SendSage, designed to provide AI models with comprehensive, climber-specific data to generate personalized coaching responses. It integrates data from multiple sources, enhances it with trend analysis and relevance scoring, and formats it into a single, unified JSON context that includes a human-readable summary and detailed structured sections. This system supports queries related to climbing and general health (e.g., nutrition, recovery), leveraging SOTA models (Grok 2 for Basic tier, Grok 3 for Premium tier). The context remains identical across tiers, with differentiation based on upload/message limits and model type.

### Objectives

- Deliver accurate, up-to-date, and relevant climber data in a single context format for climbing and health-related queries
- Enable personalized, context-aware coaching responses tailored to user experience levels (casual beginners to advanced climbers)
- Ensure efficiency and scalability with a streamlined architecture

## 2. Use Cases and User Scenarios

### Basic Tier

**Scenario:** Jane, a casual climber, asks, "How do I improve my bouldering?" The system uses the "summary" field (written for beginners) and recent climbs to suggest simple drills.

**Requirement:** Provide a unified context accessible to Grok 2, with limits on uploads and messages.

### Premium Tier

**Scenario:** Mark, an advanced climber, asks, "Plan my next 8 weeks for a V8 goal." The system uses the full context (history, training, goals) to generate a detailed plan with precise language.

**Requirement:** Provide the same comprehensive context as Basic tier, processed by Grok 3, with higher upload/message limits.

### Onboarding and Data Upload

**Scenario:** A new user uploads a CSV of their climbing log. The system parses it, deduplicates based on timestamp/source priority, and integrates it into their context.

**Requirement:** Support text-based uploads (CSV, JSON, TXT) with user-friendly error feedback.

## 3. Detailed Functional Requirements

### 3.1 Data Aggregation

The DataAggregator class shall:

- Fetch data from:
  - ClimberContext: Goals, experience, training habits, performance metrics, style preferences (from user questionnaire)
  - UserTicks: Recent climbs (e.g., last 30), including grades, locations, and send status
  - PerformancePyramid: Performance details (e.g., crux angles, energy types)
  - ChatHistory: Recent conversation context for continuity
  - UserUpload: Parsed data from uploads (CSV, JSON, TXT)
- Incorporate custom instructions (e.g., training focus, injury considerations)
- Sources: Combination of connected external logbooks (handled elsewhere in the app), user questionnaire, and uploads

#### User Upload Handling

- Support CSV, JSON, and TXT files
- Validate formats/content, providing feedback (e.g., "Please add a grade column")
- Parse into structured data (e.g., climb logs with date, route, grade)
- Deduplicate overlapping entries based on timestamp (latest wins) or source priority

### 3.2 Context Formatting

The UnifiedFormatter class shall:

- Generate a single JSON context:
  - "summary": Human-readable overview tailored to experience level
  - Structured sections: Detailed data for profile, performance, training, health, goals, and uploads
- Include:
  - Trend data (all-time and last 6 months)
  - Relevance scores tied to climber goals (handled by AI models)
  - Comparative metrics (e.g., peer benchmarks)
  - Version field (e.g., "context_version": "1.0")

#### Example Context

```json
{
  "context_version": "1.0",
  "summary": "You've climbed for 3 years, focusing on bouldering. Your highest send is V5. Goal: V8 by December.",
  "profile": {
    "years_climbing": 3,
    "total_climbs": 200
  },
  "performance": {
    "highest_boulder_grade": "V5"
  },
  "trends": {
    "grade_progression_all_time": 0.5,
    "grade_progression_6mo": 0.8
  },
  "relevance": {
    "training": "goal-driven"
  },
  "goals": {
    "climbing_goals": "Send V8 by December"
  },
  "uploads": []
}
```

### 3.3 Dynamic Prioritization

- Analyze queries to prioritize context sections based on climber goals
- Highlight pertinent data in the "summary" field, adjusted for experience level

### 3.4 Trend Analysis

Calculate:

- Grade Progression: Average grade change (all-time and last 6 months)
- Training Consistency: Frequency and session duration
- Activity Levels: Climbs/sends per week/month

### 3.5 Relevance Scoring

- Assign scores to sections dynamically by AI models, based on query keywords and alignment with climber goals

### 3.6 Comparative Data

- Include anonymized benchmarks (e.g., "Your V5 send rate is above average for 3-year climbers")

### 3.7 Goal-Oriented Structuring

- Track progress toward goals (e.g., "50% to V8")
- Suggest focus areas (e.g., "Improve finger strength")

### 3.8 Caching

- Store contexts in Redis with a 1-hour TTL
- Invalidate cache on data updates (e.g., new climb, profile change)

### 3.9 Error Handling

- Provide feedback on upload errors (e.g., "Your file needs a grade column")
- Log errors for debugging

### 3.10 Versioning

- Embed "context_version" to manage format evolution

## 4. Non-Functional Requirements

### Performance and Latency

- Cached Contexts: <500ms retrieval
- Uncached Contexts: <2s generation
- Query Analysis: <100ms for prioritization

### Scalability and Concurrency

- Support 10,000 active users with concurrent requests
- Use Redis for caching and state management

### Security and Data Handling

- Encrypt data in transit/at rest

### Logging and Monitoring

- Log generation times, cache hits, and errors
- Monitor latency and data consistency

## 5. System Architecture and Integration

### Architecture Overview

- ContextManager: Orchestrates context generation and caching
- DataAggregator: Fetches/merges data from sources
- ContextEnhancer: Adds trends and goal-driven relevance
- UnifiedFormatter: Generates the JSON context
- CacheManager: Handles Redis caching/invalidation

### Key Components

#### DataAggregator

- Input: User ID, conversation ID
- Output: Raw data from all sources
- Details: Use SQLAlchemy for async queries

#### ContextEnhancer

- Input: Raw data, query
- Output: Enhanced data with trends (all-time, 6 months)
- Details: Statistical methods for trends; AI models handle relevance

#### UnifiedFormatter

- Input: Enhanced data
- Output: JSON with "summary" (experience-adjusted) and sections
- Details: Combines conversational and analytical data

#### CacheManager

- Input: User ID, conversation ID, context
- Output: Cached context or invalidation
- Details: Redis with TTL of 1 hour

### Event-Driven Updates

- Triggers: New climb, profile edit, upload
- Invalidate cache on data changes

## 6. User Experience Flow

- Context Generation: User queries → ContextManager checks cache → If miss, DataAggregator fetches → ContextEnhancer enhances → UnifiedFormatter generates → Cache updated
- Upload Handling: User uploads → System validates/parses → Feedback given → Context updated

## 7. API and Interfaces

- Internal API:
  - GET /context/{user_id}/{conversation_id}: Retrieve unified context
- Database Schemas: Use existing tables (ClimberContext, etc.)
- Cache: Redis with keys (e.g., context:{user_id}:{conversation_id})

## 8. Testing and Acceptance Criteria

- Unit Tests: Aggregation, enhancement, formatting
- Integration Tests: Cache functionality, deduplication
- Performance Tests: <500ms cached, <2s uncached under load

## 9. Security

- Data Encryption: Encrypt in transit/at rest

## 10. Future Considerations

- Multimodal Support: Add image/video uploads for technique analysis
- Advanced NLP: Use intent classification for better prioritization
- Enhanced Trends: Implement predictive analytics

## 11. Implementation Plan

### Sprint 1: Data Aggregation (March 15 - March 28, 2025)

**Tasks:**

- Implement DataAggregator class (4 days, Backend Developer 1)
  - Fetch data from ClimberContext, UserTicks, PerformancePyramid, ChatHistory
  - Use async SQLAlchemy queries
- Design upload parsing logic (3 days, Backend Developer 2)
  - Support CSV, JSON, TXT parsing
  - Add validation and error feedback
- Deduplication logic (2 days, Backend Developer 3)
  - Deduplicate uploads by timestamp/source priority
- Unit tests for aggregation (2 days, QA Engineer)
  - Test data fetching and upload parsing

**Deliverables:** Working DataAggregator with upload support  
**Dependencies:** Database schemas from Phase 1

### Sprint 2: Context Enhancement (March 29 - April 11, 2025)

**Tasks:**

- Implement ContextEnhancer class (4 days, Backend Developer 1)
  - Add trend analysis using NumPy
  - Calculate grade progression, training consistency, activity levels
- Integrate goal-driven prioritization (3 days, Backend Developer 2)
  - Pass query/goals to AI models for relevance scoring
- Add comparative metrics (2 days, Data Engineer)
  - Generate anonymized benchmarks from aggregated data
- Unit tests for enhancement (2 days, QA Engineer)
  - Verify trends and benchmarks

**Deliverables:** Enhanced data with trends and relevance  
**Dependencies:** DataAggregator from Sprint 1; Grok SDKs

### Sprint 3: Context Formatting (April 12 - April 25, 2025)

**Tasks:**

- Implement UnifiedFormatter class (4 days, Backend Developer 1)
  - Generate JSON context with "summary" and sections
  - Tailor "summary" to experience level
- API endpoint development (3 days, Backend Developer 2)
  - Build GET /context/{user_id}/{conversation_id}
- Frontend feedback UI (3 days, Frontend Developer)
  - Display upload errors
- Integration/unit tests (2 days, QA Engineer)
  - Test JSON output and API response

**Deliverables:** Unified JSON context and API  
**Dependencies:** ContextEnhancer from Sprint 2

### Sprint 4: Caching and Integration (April 26 - May 9, 2025)

**Tasks:**

- Implement CacheManager class (3 days, Backend Developer 3)
  - Store contexts in Redis with 1-hour TTL
  - Handle cache invalidation on updates
- Event-driven updates (3 days, Backend Developer 1)
  - Trigger invalidation on new climbs, profile edits, uploads
- End-to-end integration (3 days, Backend Developer 2)
  - Connect ContextManager to all components
- Performance tests (2 days, QA Engineer, DevOps Engineer)
  - Verify <500ms cached, <2s uncached latency

**Deliverables:** Fully integrated context system with caching  
**Dependencies:** All prior sprints; Redis setup from Phase 1

### Sprint 5: Polish and Testing (May 10 - May 15, 2025)

**Tasks:**

- Bug fixes and optimizations (3 days, All Developers)
  - Address issues from integration tests
- Comprehensive testing (2 days, QA Engineer)
  - Unit, integration, and performance tests

**Deliverables:** Stable, tested system ready for staging

## 12. Conclusion

This PRD defines an efficient context system that integrates climber data into a unified JSON format, supporting SendSage's AI chat feature for climbing and health-related queries. Identical across tiers, it leverages Grok 2 (Basic) and Grok 3 (Premium) capabilities, tailoring responses to user experience levels while ensuring scalability and performance.
