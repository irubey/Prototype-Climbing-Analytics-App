# Sagechat AI Chat Feature - Product Requirements Document (PRD)

**Date:** 2/5/2025  
**Author:** Isaac Rubey

## 1. Overview and Objectives

The AI chat feature for SendSage is designed to provide climbers with a highly contextualized coaching experience. The system must cater to both free (standard) and premium users by combining immediate, friendly conversational responses with the option for deep, multi-step analysis. It leverages two AI models: **Deepseek V3** for conversational engagement and **R1 Advanced Reasoning** for technical, data-driven insights. The feature integrates user performance metrics, historical climbing data, and custom instructions to create personalized training recommendations and coaching advice.

## 2. Use Cases and User Scenarios

The system must support several user scenarios:

### Standard Users

- Benefit from clear and friendly conversational interactions
- Incorporate basic performance or climbing history details

### Premium Users

- Handle advanced queries (detailed training plans, multi-step diagnostics)
- Utilize dual-call mechanism:
  - Initial call for friendly, conversational response
  - Concurrent call to evaluate query complexity
  - R1 module invocation for advanced reasoning when needed
  - Deepseek V3 polish for final output

### Onboarding Process

Users can either:

- Connect Mountain Project logbook (populating internal models like ClimberSummary)
- Upload supplemental files to enrich AI experience

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
│   │   ├── chat/
│   │   │   ├── conversational.py    # Handles conversational responses
│   │   │   ├── evaluator.py         # Query complexity evaluation
│   │   │   ├── orchestrator.py      # Main chat flow coordination
│   │   │   ├── reasoning.py         # Advanced reasoning logic
│   │   │   └── response_enhancer.py # Output polish and enhancement
│   │   ├── model_wrappers/
│   │   │   ├── r1_client.py        # R1 Advanced Reasoning client
│   │   │   └── v3_client.py        # Deepseek V3 client implementation
│   │   └── prompt_manager.py       # System prompt management
│   ├── context/
│   │   ├── context_formatter.py    # User data and metrics formatting
│   │   └── data_integrator.py     # External data integration
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
```

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
