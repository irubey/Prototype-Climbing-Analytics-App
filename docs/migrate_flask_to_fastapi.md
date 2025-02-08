# Flask to FastAPI Migration PRD

## Overview

This document outlines the migration of our application from **Flask** (synchronous) to **FastAPI** (asynchronous) to improve performance, scalability, and developer productivity. By leveraging FastAPI's asynchronous capabilities, dependency injection, and automatic OpenAPI documentation, we can modernize our backend and prepare the system for high-concurrency scenarios such as AI-driven chat.

## 1. Introduction and Rationale

The migration includes a structured logging and error handling strategy combining:

- **Structured Logging**: Custom configuration using Python's logging module (or Loguru) for informative, parseable logs
- **Custom ASGI Middleware Logging**: Middleware for request/response logging without performance impact
- **Built-In Exception Handling**: FastAPI exception handling with custom handlers for HTTP and unhandled errors

## 2. Scope and Objectives

### Scope

- **Route Migration**: Convert Flask routes (Blueprints) to FastAPI's asynchronous APIRouters
- **Dependency Injection**: Replace Flask globals with FastAPI dependency injection
- **Template Integration**: Migrate from Flask's render_template to FastAPI's TemplateResponse
- **Logging & Error Handling**:
  - Implement structured logging with configurable logger
  - Create/integrate ASGI middleware for request/response logging
  - Configure FastAPI's exception handlers

### Objectives

- Maintain or improve current functionality
- Achieve better performance under high-concurrency workloads
- Ensure robust logging and monitoring
- Preserve existing Jinja2 templates while updating rendering context

## 3. Functional Requirements

### Asynchronous Endpoints

- Convert Flask routes to `async def` functions using APIRouters
- Auto-expose OpenAPI documentation

### Dependency Injection

- Replace Flask globals with explicit dependency injections
- Implement non-blocking, async-friendly dependencies

### Jinja2 Template Integration

- Utilize FastAPI's Jinja2Templates
- Pass required Request object for template functions

### Logging Requirements

#### Structured Logging

- Configure global logger with JSON/parsable output
- Implement ASGI middleware for HTTP request/response logging
- Provide centralized, environment-variable configurable setup

#### Error Handling

- Custom exception handlers for HTTPException and unhandled exceptions
- Consistent JSON error responses with appropriate status codes
- Optional third-party monitoring integration (e.g., Sentry)

## 4. Non-Functional Requirements

### Performance

- Improved request throughput and reduced latency
- Non-blocking operations in critical paths

### Maintainability

- Testing-friendly dependency injection
- Detailed logging and error messages

### Scalability

- High-concurrency support via async endpoints
- ASGI server capabilities

### Resilience

- Debug-friendly structured logging

## 5. Architecture and Design Decisions

### Routing and Templating

#### Routing

- Replace Blueprints with APIRouters
- Ensure async route handlers

#### Templating

- FastAPI's Jinja2Templates implementation
- Request object requirement in template context

### Logging and Error Handling Implementation

#### Structured Logging Configuration

```python
import logging

logger = logging.getLogger("myapp")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
```

#### ASGI Middleware Implementation

```python
from app.logging_setup import logger

class LoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            logger.info(f"Incoming request: {scope['method']} {scope['path']}")
            await self.app(scope, receive, send)
```

#### Exception Handler Implementation

```python
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from app.logging_setup import logger
from fastapi import FastAPI

app = FastAPI()

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP Exception: {exc.detail}", exc_info=exc)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled Exception occurred", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )
```

## 6. Implementation Plan

### Phase 1: Environment Setup

- Create migration branch/repository
- Install FastAPI, Uvicorn, dependencies
- Structure project folders (routes, dependencies, templates, logging, middleware, exceptions)

### Phase 2: Route Migration

- Catalog Flask endpoints
- Refactor to async APIRouter functions
- Replace Flask middleware/globals with dependencies

### Phase 3: Dependency Integration

- Convert Flask globals to FastAPI dependencies
- Develop injection helpers (user, db session)

### Phase 4: Template Migration

- Configure Jinja2Templates
- Update to TemplateResponse with Request object

### Phase 5: Logging Implementation

- Configure structured logging
- Develop/test ASGI logging middleware
- Integrate middleware with FastAPI
- Validate logging coverage

### Phase 6: Error Handling

- Implement exception handlers
- Test error scenarios
- Optional monitoring integration

### Phase 7: Verification

- Create unit/integration tests
- Validate API documentation
- Load test async endpoints
- Document configuration

## 7. Acceptance Criteria and Rollback

### Acceptance Criteria

- Functional async endpoints
- Complete API documentation
- Structured logging implementation
- Standardized error handling
- Passing tests and performance metrics
- Clear documentation

### Rollback Plan

- Maintain Flask backup branch
- Enable quick reversion if needed

## 8. Timeline

- **Week 1-2**: Environment setup, route cataloging
- **Week 3-4**: Endpoint migration, dependency injection
- **Week 5**: Logging/error handling implementation
- **Week 6-8**: Testing and staged rollout

## 9. Risk Management

### Identified Risks and Mitigation

1. **Flask Dependencies**

   - Risk: Hidden Flask middleware dependencies
   - Mitigation: Thorough code audit and testing

2. **Async Performance**

   - Risk: Logging/middleware configuration impact
   - Mitigation: Staging environment benchmarks

3. **Error Handling**
   - Risk: Incomplete error capture
   - Mitigation: External monitoring tools

## 10. Route Mappings

# Route Mapping: Flask to FastAPI

| Functionality               | Legacy Flask Route(s)               | Proposed FastAPI Route(s)                                                   | Notes/Changes                                                                                               |
| --------------------------- | ----------------------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **Authentication**          |                                     |                                                                             |                                                                                                             |
| Login                       | GET/POST `/login`                   | POST `/auth/token`                                                          | Replace session-based login with OAuth2-driven JWT token issuance. No template rendering on token endpoint. |
| Register                    | GET/POST `/register`                | POST `/auth/register`                                                       | Handle user creation with async validations and optional email confirmation flow.                           |
| Logout                      | GET `/logout`                       | POST `/auth/logout`                                                         | Implement stateless token invalidation or client-side token removal.                                        |
| Reset Password Request      | GET/POST `/reset-password`          | POST `/auth/reset-password`                                                 | Async email token generation and delivery.                                                                  |
| Reset Password (Token)      | GET/POST `/reset-password/<token>`  | POST `/auth/reset-password/{token}`                                         | Token validation and password reset with rate limiting.                                                     |
| **Payment**                 |                                     |                                                                             |                                                                                                             |
| Payment Page                | GET/POST `/payment`                 | <ul><li>GET `/payment`</li><li>POST `/payment/create-session`</li></ul>     | Split into separate endpoints for displaying options and creating Stripe sessions.                          |
| Payment Success             | GET `/payment/success`              | GET `/payment/success`                                                      | Handle async payment confirmation and user status updates.                                                  |
| Stripe Webhook              | POST `/stripe-webhook`              | POST `/payment/webhook`                                                     | Async webhook processing with signature verification.                                                       |
| **Core Features**           |                                     |                                                                             |                                                                                                             |
| Landing Page                | GET `/`                             | GET `/`                                                                     | Async authentication and payment status checks.                                                             |
| Logbook Connection          | GET/POST `/logbook-connection`      | <ul><li>GET `/logbook`</li><li>POST `/logbook/connect`</li></ul>            | Split into view and processing endpoints with async data handling.                                          |
| Terms & Privacy             | GET `/terms-privacy`                | GET `/legal/terms-privacy`                                                  | Static content delivery with caching.                                                                       |
| **Visualization**           |                                     |                                                                             |                                                                                                             |
| User Visualization          | GET `/userviz`                      | GET `/viz/dashboard`                                                        | Async data retrieval and metrics calculation.                                                               |
| Performance Pyramid         | GET `/performance-pyramid`          | GET `/viz/performance-pyramid`                                              | Async pyramid data generation and rendering.                                                                |
| Base Volume                 | GET `/base-volume`                  | GET `/viz/base-volume`                                                      | Async volume calculations and data aggregation.                                                             |
| Progression                 | GET `/progression`                  | GET `/viz/progression`                                                      | Async progression metrics and timeline generation.                                                          |
| When/Where                  | GET `/when-where`                   | GET `/viz/location-analysis`                                                | Async location data processing and visualization.                                                           |
| Performance Characteristics | GET `/performance-characteristics`  | GET `/viz/performance-characteristics`                                      | Async performance data aggregation and analysis.                                                            |
| **Data Management**         |                                     |                                                                             |                                                                                                             |
| Pyramid Input               | GET/POST `/pyramid-input`           | <ul><li>GET `/data/pyramid`</li><li>POST `/data/pyramid/update`</li></ul>   | Split into separate endpoints for form display and data processing.                                         |
| Delete Tick                 | DELETE `/delete-tick/<int:tick_id>` | DELETE `/data/ticks/{tick_id}`                                              | Async tick deletion with pyramid recalculation.                                                             |
| Refresh Logbook Data        | POST `/refresh-data`                | POST `/data/refresh`                                                        | Async data refresh with progress tracking.                                                                  |
| Create Ticks                | POST `/create-ticks`                | POST `/data/ticks/batch`                                                    | Async batch tick creation with validation.                                                                  |
| **Chat & AI**               |                                     |                                                                             |                                                                                                             |
| Sage Chat                   | GET `/sage-chat`                    | GET `/chat`                                                                 | Async chat initialization with user context loading.                                                        |
| Chat Message                | POST `/sage-chat/message`           | POST `/chat/message`                                                        | Async message processing with rate limiting.                                                                |
| Chat Settings               | POST `/sage-chat/onboard`           | Removed, handled in chat/settings                                           | Async user profile setup and validation.                                                                    |
| File Upload                 | POST `/upload`                      | POST `/chat/upload`                                                         | Async file processing with tier-based limitations.                                                          |
| Update Chat Settings        | GET/POST `/update-climber-summary`  | <ul><li>GET `/chat/settings`</li><li>POST `/chat/settings/update`</li></ul> | Split into view and update endpoints with async processing.                                                 |
| **System**                  |                                     |                                                                             |                                                                                                             |
| Health Check                | GET `/health`                       | GET `/system/health`                                                        | Async system metrics collection and reporting.                                                              |
| Support Count               | GET `/api/support-count`            | GET `/metrics/support-count`                                                | Implement async DB queries with caching.                                                                    |

## 11. Migration of Custom Route Decorators and Utilities

### Converting Custom Route Decorators to Dependencies

#### Current Approach

The Flask application uses decorators like `@temp_user_check` and `@payment_required` to inspect the global `current_user` and enforce business rules:

- Temporary session expiration
- Payment status validation
- Authentication checks

#### FastAPI Approach

Instead of decorators, we'll use FastAPI's dependency injection system, which:

- Makes endpoint requirements explicit in the signature
- Enhances OpenAPI documentation generation
- Improves testability

##### Authentication/Authorization Dependency

```python
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = await validate_token(token)
    if user.username.endswith('_temp'):
        raise HTTPException(
            status_code=401,
            detail="Temporary session expired"
        )
    return user
```

##### Route-Specific Business Rule Dependencies

```python
async def verify_payment_status(
    current_user: User = Depends(get_current_user)
):
    if current_user.payment_status not in VALID_PAYMENT_STATUSES:
        raise HTTPException(
            status_code=403,
            detail="Payment required"
        )
    return current_user

@app.get("/protected-route")
async def protected_endpoint(
    user: User = Depends(verify_payment_status)
):
    return {"message": "Access granted"}
```

### Leveraging Middleware for Cross-Cutting Concerns

While route-specific logic is handled by dependencies, cross-cutting concerns like logging use ASGI middleware:

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Pre-processing
        logger.info(f"Request: {request.method} {request.url}")
        response = await call_next(request)
        # Post-processing
        logger.info(f"Response: {response.status_code}")
        return response
```

### Custom JSON Encoding Solutions

#### Current Approach

The Flask application uses `CustomJSONEncoder` for handling dates, enums, and UUIDs.

#### FastAPI Options

##### Option A: Custom Response Class

```python
from fastapi.responses import JSONResponse
from datetime import date
from uuid import UUID
from enum import Enum

class CustomJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        def custom_encoder(obj):
            if isinstance(obj, date):
                return obj.strftime('%Y-%m-%d')
            if isinstance(obj, UUID):
                return str(obj)
            if isinstance(obj, Enum):
                return obj.value
            return str(obj)

        return json.dumps(
            content,
            default=custom_encoder
        ).encode('utf-8')
```

##### Option B: Override jsonable_encoder

```python
from fastapi.encoders import jsonable_encoder

def custom_jsonable_encoder(obj):
    if isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')
    if isinstance(obj, UUID):
        return str(obj)
    return jsonable_encoder(obj)
```

### Jinja2 Template Filter Migration

#### Current Approach

Flask application uses custom Jinja2 filters like `format_datetime`.

#### FastAPI Implementation

```python
from fastapi.templating import Jinja2Templates
from datetime import datetime

templates = Jinja2Templates(directory="templates")

def format_datetime(value):
    if not value:
        return ''
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            return value
    return value.strftime('%b %d, %Y')

# Register filter during startup
templates.env.filters["datetime"] = format_datetime
```

### Implementation Guidelines

1. **Dependencies vs. Middleware**

   - Use dependencies for route-specific logic (auth, payment validation)
   - Use middleware for global concerns (logging, error handling)
   - Chain dependencies when logic builds on other requirements

2. **JSON Encoding Strategy**

   - Choose between custom response class or encoder override
   - Maintain consistent serialization across the application
   - Consider performance implications of chosen approach

3. **Template Integration**
   - Register filters during application startup
   - Ensure consistent template rendering behavior
   - Maintain backward compatibility with existing templates

### Benefits

- Enhanced testability through dependency injection
- Explicit security and business logic in OpenAPI schema
- Improved code organization and maintainability
- Better error handling and validation
- Consistent behavior across the application

## 12. References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [FastAPI Error Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [Kludex FastAPI Tips](https://github.com/Kludex/fastapi-tips)
- [TestDriven.io Flask Migration](https://testdriven.io/blog/moving-from-flask-to-fastapi/)
- [Cursed Cursor](https://skylarbpayne.com/posts/cursed-cursor)

---

## Summary

This PRD provides a comprehensive migration plan from Flask to FastAPI, incorporating structured logging and error handling. The plan ensures a scalable, performant system ready for high-concurrency loads and future AI features. Implementation follows a phased approach with clear milestones and risk mitigation strategies.
