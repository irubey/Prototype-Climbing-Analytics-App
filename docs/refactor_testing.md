# Test Architecture Refactoring Plan

## Executive Summary

This document outlines a comprehensive plan to refactor the existing test suite into a more modular, scalable, and maintainable architecture. The current implementation, while functional, suffers from duplication, tight coupling, and maintenance challenges that will impede future development velocity. This refactoring will establish a robust testing foundation that supports the growing complexity of the application while reducing the overhead of writing and maintaining tests.

## Business Objectives

**Primary Goal**: Transform the existing test suite into a modular, maintainable architecture that scales with application growth.

**Key Benefits**:

- Reduced maintenance burden through elimination of duplicate test code
- Faster test development with reusable components and consistent patterns
- Improved test reliability with better isolation and deterministic fixtures
- Enhanced documentation through clear organization and purpose-focused components
- Lower onboarding friction for new developers joining the project

## Current Architecture Limitations

The existing test suite demonstrates several anti-patterns that hinder maintainability:

- Fixture proliferation across multiple files without clear organization
- Inconsistent mocking approaches for external dependencies
- Test data duplication resulting in inconsistent test scenarios
- Complex test setup with tightly coupled components
- Unclear separation between unit, integration, and API tests

## Detailed Requirements

### 1. Hierarchical Fixture Structure

**Requirement**: Organize fixtures into domain-specific modules within a dedicated fixtures directory.

**Implementation Details**:

Create a `tests/fixtures` directory with specialized fixture modules:

- `database.py` - Database and ORM fixtures
- `auth.py` - Authentication and authorization fixtures
- `services.py` - Service layer fixtures
- `redis.py` - Redis and caching fixtures
- `external_services.py` - Third-party service fixtures
- `test_data.py` - Test data loader fixtures

Each fixture module should include detailed docstrings explaining:

- Purpose of each fixture
- Dependencies between fixtures
- Usage examples
- Scope considerations

Implement a main `conftest.py` that imports and exposes all fixtures:

```python
"""Primary test configuration exposing all fixtures."""

# Database fixtures
from app.tests.fixtures.database import db_session, test_db_connection

# Authentication fixtures
from app.tests.fixtures.auth import auth_client, test_user, admin_user

# Service layer fixtures
from app.tests.fixtures.services import mock_chat_service, mock_climbing_service

# Redis fixtures
from app.tests.fixtures.redis import redis_client, redis_connection

# External service fixtures
from app.tests.fixtures.external_services import mock_openai, mock_weather_api

# Test data fixtures
from app.tests.fixtures.test_data import load_user_data, load_climb_data
```

### 2. Centralized Test Data Management

**Requirement**: Establish a consistent approach to test data management that eliminates duplication and improves maintainability.

**Implementation Details**:

Create a `tests/data` directory with JSON/YAML fixtures for static test data.

Implement data factory functions for dynamic test data generation:

```python
"""Test data factories for generating consistent test entities."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random

def create_user_data(
    email_prefix: str = "test",
    domain: str = "example.com",
    password: str = "TestPassword123!",
    experience_level: str = "intermediate"
) -> Dict:
    """Generate consistent user test data with customizable parameters."""
    username = f"{email_prefix}_{random.randint(1000, 9999)}"
    email = f"{username}@{domain}"

    return {
        "email": email,
        "username": username,
        "password": password,
        "experience_level": experience_level,
        "created_at": datetime.now(),
        "settings": {"beta_features": False, "notification_preferences": {"email": True}}
    }

def create_climb_data(
    count: int = 5,
    user_id: Optional[int] = None,
    base_date: Optional[datetime] = None,
    grade_range: tuple = ("V1", "V7")
) -> List[Dict]:
    """Generate a list of climbing session test data."""
    if base_date is None:
        base_date = datetime.now()

    grades = ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10"]
    valid_grades = grades[grades.index(grade_range[0]):grades.index(grade_range[1])+1]

    climbs = []
    for i in range(count):
        climbs.append({
            "date": base_date - timedelta(days=i*3),
            "route": f"Test Route {i+1}",
            "grade": random.choice(valid_grades),
            "send_status": random.choice(["sent", "project", "attempted"]),
            "user_id": user_id,
            "notes": f"Test climb notes {i+1}"
        })

    return climbs
```

Add data loader utilities for reading static fixtures:

```python
"""Utilities for loading test data from fixtures."""
import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Union

def load_fixture(
    fixture_name: str,
    format: str = "json"
) -> Union[Dict[str, Any], List[Any]]:
    """Load test data from a fixture file.

    Args:
        fixture_name: Name of the fixture file without extension
        format: Format of the fixture (json or yaml)

    Returns:
        The loaded fixture data
    """
    base_path = Path(__file__).parent / "fixtures"
    file_path = base_path / f"{fixture_name}.{format}"

    if not file_path.exists():
        raise FileNotFoundError(f"Test fixture not found: {file_path}")

    with open(file_path, "r") as f:
        if format == "json":
            return json.load(f)
        elif format == "yaml":
            return yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported fixture format: {format}")
```

### 3. Service Test Factories

**Requirement**: Create reusable factories for service layer testing to simplify test setup and improve consistency.

**Implementation Details**:

Implement a `tests/factories` directory with service-specific factory classes:

```python
"""Factories for creating pre-configured service instances for testing."""
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, List, Optional, Any

class ChatServiceFactory:
    """Factory for creating preconfigured chat service test instances."""

    @classmethod
    def create_service(
        cls,
        mock_redis: bool = True,
        mock_llm: bool = True,
        mock_context: bool = True,
        context_data: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ):
        """Create a chat service instance with configurable mocks.

        Args:
            mock_redis: Whether to mock the Redis client
            mock_llm: Whether to mock the LLM client
            mock_context: Whether to mock the context manager
            context_data: Optional predefined context data
            conversation_history: Optional predefined conversation history

        Returns:
            Configured ChatService instance with appropriate mocks
        """
        from app.services.chat import ChatService

        # Create default mock dependencies
        context_manager = AsyncMock()
        event_manager = AsyncMock()
        redis_client = AsyncMock() if mock_redis else None
        llm_client = AsyncMock() if mock_llm else None

        # Configure mock behavior
        if mock_context and context_data:
            context_manager.get_context.return_value = context_data

        if mock_redis and conversation_history:
            redis_client.get_conversation_history.return_value = conversation_history

        # Create service instance with mocks
        service = ChatService(
            context_manager=context_manager,
            event_manager=event_manager,
            redis_client=redis_client,
            llm_client=llm_client
        )

        # Store mock references for test assertion access
        service._test_mocks = {
            "context_manager": context_manager,
            "event_manager": event_manager,
            "redis_client": redis_client,
            "llm_client": llm_client
        }

        return service

class ClimbingServiceFactory:
    """Factory for creating preconfigured climbing service test instances."""
    # Similar implementation for climbing service
```

### 4. API Testing Framework

**Requirement**: Establish a consistent framework for API testing that simplifies authorization and request handling.

**Implementation Details**:

Create a robust API testing client in `tests/utils/api_client.py`:

```python
"""Enhanced API client for testing REST endpoints."""
from httpx import AsyncClient
from typing import Any, Dict, Optional, Union
from uuid import uuid4

class TestApiClient:
    """API test client with authentication and request helpers."""

    def __init__(self, app, base_url: str = "http://test"):
        """Initialize test client.

        Args:
            app: The FastAPI application
            base_url: Base URL for requests
        """
        self.app = app
        self.base_url = base_url
        self.client = AsyncClient(app=app, base_url=base_url)
        self.auth_headers = {}

    async def authenticate(
        self,
        user_id: Union[int, str],
        scopes: Optional[list] = None,
        db_session = None
    ):
        """Authenticate client with user credentials.

        Args:
            user_id: User ID to authenticate as
            scopes: Optional authorization scopes
            db_session: Database session for token creation

        Returns:
            Self for method chaining
        """
        from app.core.auth import create_access_token

        if scopes is None:
            scopes = ["user"]

        token = await create_access_token(
            subject=str(user_id),
            scopes=scopes,
            jti=str(uuid4()),
            db=db_session
        )

        self.auth_headers = {"Authorization": f"Bearer {token}"}
        return self

    async def get(self, url: str, authenticated: bool = True, **kwargs):
        """Perform GET request.

        Args:
            url: Endpoint URL
            authenticated: Whether to include auth headers
            **kwargs: Additional request parameters

        Returns:
            Response object
        """
        headers = kwargs.get("headers", {})
        if authenticated:
            headers.update(self.auth_headers)
        kwargs["headers"] = headers

        return await self.client.get(url, **kwargs)

    async def post(self, url: str, data: Any = None, json: Dict = None,
                  authenticated: bool = True, **kwargs):
        """Perform POST request.

        Args:
            url: Endpoint URL
            data: Form data
            json: JSON payload
            authenticated: Whether to include auth headers
            **kwargs: Additional request parameters

        Returns:
            Response object
        """
        headers = kwargs.get("headers", {})
        if authenticated:
            headers.update(self.auth_headers)
        kwargs["headers"] = headers

        return await self.client.post(url, data=data, json=json, **kwargs)

    # Similarly implement put, patch, delete methods
```

Create response validation helpers:

```python
"""Response validation utilities for API tests."""
from typing import Any, Dict, List, Optional, Union

def validate_pagination(
    response_data: Dict[str, Any],
    expected_page: int = 1,
    expected_page_size: int = 10,
    expected_total: Optional[int] = None
):
    """Validate pagination metadata in response.

    Args:
        response_data: The response data dict
        expected_page: Expected current page
        expected_page_size: Expected page size
        expected_total: Optional expected total items

    Raises:
        AssertionError: If validation fails
    """
    assert "pagination" in response_data, "Response missing pagination metadata"
    pagination = response_data["pagination"]

    assert pagination["page"] == expected_page, f"Expected page {expected_page}, got {pagination['page']}"
    assert pagination["page_size"] == expected_page_size, f"Expected page_size {expected_page_size}, got {pagination['page_size']}"

    if expected_total is not None:
        assert pagination["total"] == expected_total, f"Expected total {expected_total}, got {pagination['total']}"

def validate_user_response(user_data: Dict[str, Any], expected_fields: Optional[List[str]] = None):
    """Validate user object in response.

    Args:
        user_data: User data dictionary
        expected_fields: Optional list of fields that should be present

    Raises:
        AssertionError: If validation fails
    """
    # Default expected fields
    if expected_fields is None:
        expected_fields = ["id", "username", "email", "created_at"]

    for field in expected_fields:
        assert field in user_data, f"User data missing expected field: {field}"

    # Ensure sensitive fields are not present
    assert "password" not in user_data, "Response contains password field"
    assert "password_hash" not in user_data, "Response contains password_hash field"
```

### 5. Enhanced Test Parameterization

**Requirement**: Improve test organization and coverage through consistent parameterization patterns.

**Implementation Details**:

Create test parameterization utilities in `tests/utils/parameterization.py`:

```python
"""Test parameterization utilities."""
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple, Union

class TestCase(NamedTuple):
    """Structured test case definition for parameterized tests."""
    id: str  # Unique identifier for the test case
    input: Dict[str, Any]  # Input parameters
    expected: Dict[str, Any]  # Expected results
    description: Optional[str] = None  # Optional description
    marks: Optional[List[Callable]] = None  # Optional pytest marks

def auth_test_cases() -> List[TestCase]:
    """Generate authentication test cases."""
    return [
        TestCase(
            id="valid_credentials",
            input={"email": "test@example.com", "password": "ValidPassword123!"},
            expected={"status_code": 200, "token_type": "bearer"},
            description="Login with valid credentials succeeds"
        ),
        TestCase(
            id="invalid_password",
            input={"email": "test@example.com", "password": "WrongPassword"},
            expected={"status_code": 401, "detail": "Invalid credentials"},
            description="Login with invalid password fails"
        ),
        TestCase(
            id="non_existent_user",
            input={"email": "nonexistent@example.com", "password": "AnyPassword123!"},
            expected={"status_code": 401, "detail": "Invalid credentials"},
            description="Login with non-existent user fails"
        ),
        TestCase(
            id="missing_email",
            input={"password": "ValidPassword123!"},
            expected={"status_code": 422, "detail": "field required"},
            description="Login without email fails validation"
        ),
        TestCase(
            id="missing_password",
            input={"email": "test@example.com"},
            expected={"status_code": 422, "detail": "field required"},
            description="Login without password fails validation"
        )
    ]
```

Create a sample parameterized test using these utilities:

```python
"""Authentication endpoint tests."""
import pytest
from app.tests.utils.parameterization import auth_test_cases

@pytest.mark.parametrize(
    "test_case",
    auth_test_cases(),
    ids=[tc.id for tc in auth_test_cases()]
)
async def test_login(test_case, test_api_client, test_user_factory):
    """Test login endpoint under various scenarios.

    Args:
        test_case: Parameterized test case
        test_api_client: API client fixture
        test_user_factory: User factory fixture
    """
    # Setup test data
    if test_case.id in ("valid_credentials", "invalid_password"):
        await test_user_factory.create_user(
            email="test@example.com",
            password="ValidPassword123!" if test_case.id == "valid_credentials" else "DifferentPassword123!"
        )

    # Execute request
    response = await test_api_client.post(
        "/api/v1/auth/login",
        json=test_case.input
    )

    # Verify response
    assert response.status_code == test_case.expected["status_code"]

    response_json = response.json()
    if test_case.expected.get("token_type"):
        assert response_json["token_type"] == test_case.expected["token_type"]
        assert "access_token" in response_json

    if test_case.expected.get("detail"):
        assert test_case.expected["detail"] in response_json.get("detail", "")
```

### 6. Environment Configuration

**Requirement**: Establish a centralized, flexible test configuration system that supports different environments.

**Implementation Details**:

Create a dedicated configuration module in `tests/config.py`:

```python
"""Test configuration settings."""
import os
from pathlib import Path
from pydantic import BaseSettings, PostgresDsn

class TestSettings(BaseSettings):
    """Test environment settings."""

    # Environment selection
    TEST_ENV: str = "local"  # Options: local, ci, docker

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    TEST_DATA_DIR: Path = Path(__file__).parent / "data" / "fixtures"

    # Database
    TEST_DATABASE_URL: PostgresDsn = PostgresDsn.build(
        scheme="postgresql+asyncpg",
        user="postgres",
        password="postgres",
        host="localhost",
        path="/test_db"
    )

    # Test behavior
    MOCK_EXTERNAL_APIS: bool = True
    CAPTURE_LOGS: bool = True
    LOG_LEVEL: str = "ERROR"

    # Authentication
    TEST_TOKEN_SECRET: str = "test_secret_key_for_testing_only"
    TEST_TOKEN_ALGORITHM: str = "HS256"
    TEST_TOKEN_EXPIRE_MINUTES: int = 30

    # Performance testing
    LOAD_TEST_CONCURRENCY: int = 1
    LOAD_TEST_REQUESTS: int = 10

    class Config:
        """Pydantic config."""
        env_file = ".env.test"
        case_sensitive = True

# Create a global instance
test_settings = TestSettings()
```

Create environment-specific configuration files:

- `.env.test.local` - Local development testing
- `.env.test.ci` - Continuous integration testing
- `.env.test.docker` - Docker environment testing

## Implementation Plan

### Phase 1: Foundation (Week 1-2)

1. Create the directory structure:
   - `app/tests/fixtures/`
   - `app/tests/data/`
   - `app/tests/factories/`
   - `app/tests/utils/`
2. Implement core configuration components:
   - `config.py` with environment-specific settings
   - Environment configuration files
   - Set up CI pipeline updates to support the new architecture

### Phase 2: Core Components (Week 3-4)

1. Implement test data management:
   - Data factories for dynamic data
   - Static fixtures for common test cases
   - Data loaders
2. Create base test utilities:
   - API test client
   - Response validators
   - Parameterization helpers
3. Develop initial service factories for critical services

### Phase 3: Fixture Migration (Week 5-6)

1. Refactor existing fixtures into domain-specific modules
2. Update main `conftest.py` to expose all fixtures
3. Update documentation on fixture usage

### Phase 4: Test Refactoring (Week 7-8)

1. Refactor existing tests to use the new infrastructure
2. Implement enhanced parameterization for key test areas
3. Rationalize test separation (unit vs. integration vs. API)

### Phase 5: Documentation & Training (Week 9)

1. Create comprehensive documentation:
   - Test architecture overview
   - Fixture usage guides
   - Best practices document
   - Component reference
2. Conduct team training session on the new architecture

## Success Criteria

The refactoring will be considered successful when:

1. All tests pass with the same or better reliability
2. Test coverage is maintained or improved
3. Documentation is complete and accurate
4. Developer feedback confirms improved maintainability
5. New test development demonstrates accelerated implementation time

## Risks and Mitigations

| Risk                    | Impact | Mitigation                                                |
| ----------------------- | ------ | --------------------------------------------------------- |
| Breaking existing tests | High   | Implement changes incrementally with continuous testing   |
| Knowledge transfer gaps | Medium | Comprehensive documentation and training sessions         |
| Extended timeline       | Medium | Prioritize high-value components for early implementation |
| Increased complexity    | Low    | Focus on intuitive designs with clear usage patterns      |

## Conclusion

This test architecture refactoring represents a significant investment in the project's long-term health and development velocity. By addressing the current limitations and establishing a robust, scalable testing framework, we will dramatically reduce the maintenance burden while improving test reliability and coverage.
