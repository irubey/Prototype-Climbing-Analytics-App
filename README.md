# SendSage - AI-Powered Climbing Coach & Analytics Platform

🤖 **Your Personal Climbing AI Coach with Deep Analytics**

## About

SendSage combines cutting-edge **AI coaching** with comprehensive analytics to transform your climbing journey. At its core is **SageChat**, a context-aware AI climbing coach that understands your performance data, climbing history, and goals to provide personalized guidance. While maintaining our powerful visualization suite for free users, our premium offering focuses on intelligent, data-driven coaching conversations.

Key highlights:

- 🧠 **SageChat:** Context-aware AI climbing coach that understands your data
- 📊 Free interactive visualization suite
- 🎯 Personalized training recommendations
- 📈 Performance tracking and analysis
- 🔄 Real-time Mountain Project or 8a.nu data integration

## Core Features

### SageChat AI Coach

- **Contextual Understanding:** AI has context of your climbing, training, and lifestyle history, style, and preferences, goals, and more.
- **Personalized Guidance:**
  - Training program recommendations
  - Technical advice based on your climbing style
  - Project selection and preparation strategies
  - Recovery and injury prevention insights
  - Deep dive into your performance metrics and history
- **Data-Driven Coaching:** Leverages your performance metrics for targeted advice

### Analytics Dashboard (Free)

- **Performance Metrics:** Grade pyramids, progression tracking, and style analysis
- **Interactive Visualizations:** Geographic patterns and seasonal trends
- **Data Integration:** Seamless Mountain Project or 8a.nu sync
- **Custom Analytics:** Deep-dive performance characteristics and achievement tracking

## How It Works

### Step 1: Connect Your Data

- Link your Mountain Project or 8a.nu profile
- Secure OAuth2/JWT authentication

### Step 2: Access Your Tools

- Explore free visualization suite
- Premium users: Engage with SageChat for personalized coaching
- Real-time data synchronization

### Step 3: Get Personalized Guidance

- Receive data-driven insights
- Interact with SageChat for specific advice and training plans
- Track progress and adjust goals
- Asynchronous processing for faster response times

## Pricing Tiers

### Free Tier - Analytics Explorer

- Complete visualization suite
- Mountain Project or 8a.nu integration
- Basic performance metrics
- Secure token-based authentication

### Basic Tier - AI Chat

- Everything in Free tier
- Limited SageChat access
- Basic performance analysis
- Context aware chat with conversational AI
- Enhanced real-time data processing

### Premium Tier - AI Advanced Reasoning

- Everything in Basic tier
- Unlimited SageChat access
- Advanced performance analysis
- Personalized training recommendations
- Context aware chat with advanced reasoning and conversational AI
- Priority async processing

## Technologies

### AI & Machine Learning

- **Natural Language Processing:** Advanced context understanding
- **Performance Analysis:** Pattern recognition and prediction
- **Recommendation Engine:** Personalized training and project suggestions

### Backend & Data

- **FastAPI:** High-performance async web framework
- **AsyncPG:** Asynchronous PostgreSQL driver
- **SQLAlchemy:** Async ORM for efficient data operations
- **OAuth2/JWT:** Secure authentication and authorization
- **ASGI Server:** High-concurrency request handling

### Frontend

- **Next.js:** React framework for optimal performance
- **NextAuth:** Seamless authentication integration
- **D3.js:** Dynamic data visualizations
- **Tailwind CSS:** Modern utility-first styling
- **Real-time Updates:** WebSocket-based instant coaching feedback

### Testing Infrastructure

- **Pytest:** Modern test framework with rich fixtures and parameterization
- **Mock Factories:** Service factories for creating test instances with controlled behavior
- **Fixtures:** Comprehensive fixture library for test setup and dependency injection
- **Unit & Integration Tests:** Complete test coverage for core functionality
- **Test Utilities:** Custom test clients and validators for API testing
- **Async Testing:** First-class support for testing asynchronous code paths
  - **Important:** Define async tests at module level (not in classes) for proper pytest-asyncio collection
- **Parameterized Testing:** Data-driven testing with structured test cases
- **Environment Isolation:** Tests run in isolated environments to prevent cross-contamination
- **Mocking Framework:** Sophisticated mocking of external dependencies and database operations
- **CI/CD Integration:** Automated test runs on every code change

## Security & Performance

- **JWT-based Authentication:** Secure token management
- **Async Processing:** Enhanced response times
- **Cross-Origin Security:** Protected API endpoints
- **Token Refresh:** Seamless session management
- **Rate Limiting:** Protected API resources

## Try SendSage Today

[Access SendSage](https://send-sage.com/)

Transform your climbing with AI-powered coaching and comprehensive analytics.
