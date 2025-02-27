# Send Sage Testing Infrastructure

This directory contains a comprehensive testing infrastructure for the Send Sage application. The testing framework is built on pytest and includes utilities for API testing, data fixtures, response validation, and test parameterization.

## Test Organization

Tests are organized into the following categories:

- **Basic Tests**: Simple tests to verify configuration and file structure
- **Data Loading Tests**: Tests for loading fixture data independently
- **Unit Tests**: Test individual functions and methods in isolation
- **Integration Tests**: Test interactions between components
- **API Tests**: Test REST API endpoints and responses

## Simplified Testing Approach

A simplified testing approach has been implemented to allow running tests without complex database or external service dependencies. Basic test files include:

- **test_basic.py**: Verifies the test directory structure and configuration
- **test_data_loading.py**: Tests fixture data loading capabilities
- **test_grade_service.py**: Tests the GradeService utility without database dependencies

To run these simplified tests:

```bash
# Run only the simplified tests
python -m pytest app/tests/test_basic.py app/tests/test_data_loading.py app/tests/test_grade_service.py -v

# Run with pytest markers
python -m pytest app/tests/ -m unit
```

## Directory Structure

```
app/tests/
├── api/              # API endpoint tests
├── data/             # Test data and fixtures
│   └── fixtures/     # JSON and YAML test data files
├── fixtures/         # Pytest fixtures
├── factories/        # Service test factories
├── integration/      # Integration tests
├── unit/             # Unit tests
└── utils/            # Testing utilities
```

### Fixtures Organization

The fixtures directory contains modular test fixtures organized by domain:

```
app/tests/fixtures/
├── auth.py           # Authentication fixtures (users, tokens)
├── chat.py           # Chat service fixtures
├── climbing.py       # Climbing and grade fixtures
├── database.py       # Database session fixtures
├── external_services.py # External API mocks
├── redis.py          # Redis connection fixtures
├── services.py       # Service layer fixtures
└── test_data.py      # Test data generation utilities
```

Key fixtures include:

- **Climbing Domain**: `sample_grade_mappings`, `mock_grade_service`, `mock_climbing_service`
- **Chat Domain**: `sample_prompt_templates`, `mock_chat_service`, `mock_model_client`
- **Auth Domain**: `test_user`, `admin_user`, `auth_client`
- **Infrastructure**: `db_session`, `redis_client`, `mock_redis_client`

### Unit Tests Coverage

Below is a comprehensive list of unit tests organized by domain. This represents both existing tests and planned tests to achieve complete coverage of the application functionality.

```
app/tests/unit/
├── app/
│   ├──test_main.py
│   ├──test_db_sessions.py
│   ├──test_settings.py
│   └──test_utils.py
├── auth/
│   ├── test_auth_service.py        # Authentication service tests
│   ├── test_password_hashing.py    # Password security tests
│   └── test_token_service.py       # JWT token generation, rotation, andvalidation
├── chat/
│   ├── test_chat_service.py        # Chat service integration tests
│   ├── test_context_manager.py     # Chat context management
│   ├── test_model_client.py        # LLM model client functionality
│   └── test_prompt_formatting.py   # Prompt template rendering
├── logbook/
│   ├── test_climbing_grade_conversion.py    # Grade conversion functionality
│   ├── test_climbing_service_parameterized.py   # Parameterized climbing tests
│   ├── test_logbook_orchestrator.py    # Logbook service orchestration
│   └── test_pyramid_builder.py     # Performance pyramid building
├── logbook_connection/
│   ├── test_data_aggregation.py    # Data collection and processing
│   ├── test_mp_csv_processor.py    # Mountain Project data processing
│   └── test_eight_a_nu_processor.py    # 8a.nu data processing
├── factories/
│   ├── test_grade_service_factory.py   # Grade service factory tests
│   └── test_service_factories.py       # General service factory tests
└── utils/
    ├── test_grade_service.py       # Grade service utility tests
    └── test_validators.py          # Response validator tests
```

Current implementation status:

- ✅ Implemented: `test_chat_service.py`, `test_climbing_grade_conversion.py`, `test_climbing_service_parameterized.py`, `test_grade_service_factory.py`, `test_service_factories.py`
- 🔄 In progress: Various other unit tests
- ⏱ Planned: Remaining unit tests for complete coverage

## Test Utilities

### API Client

Located in `app/tests/utils/api_client.py`, the `TestApiClient` class provides an enhanced HTTP client for testing REST endpoints. Features include:

- Authentication with JWTs
- Methods for GET, POST, PUT, PATCH, DELETE requests
- Pagination support
- File uploads
- Response parsing

The `TestApiClient` uses `httpx.AsyncClient` with `ASGITransport` for direct testing of FastAPI applications without requiring a running server.

Example usage:

```python
async def test_get_user(api_client: TestApiClient, test_user):
    # Authenticate as test user
    await api_client.authenticate(user_id=test_user.id)

    # Make authenticated request
    response = await api_client.get(f"/api/v1/users/{test_user.id}")

    # Parse response
    data = await api_client.parse_response(response)
    assert data["id"] == test_user.id
```

### Response Validators

Located in `app/tests/utils/validators.py`, these utilities help validate API responses:

- `validate_pagination`: Validates pagination metadata
- `validate_user_response`: Validates user objects in responses
- `validate_climb_response`: Validates climbing session data with support for discipline field
- `validate_response_structure`: Validates overall response structure
- `validate_error_response`: Validates error responses
- `validate_auth_response`: Validates authentication responses

Example usage:

```python
async def test_list_users(api_client: TestApiClient, admin_headers):
    response = await api_client.get("/api/v1/users", headers=admin_headers)
    data = await api_client.parse_response(response)

    # Validate pagination structure
    validate_pagination(data, current_page=1, page_size=10)

    # Validate each user in the response
    for user in data["items"]:
        validate_user_response(user)
```

### Service Test Factories

Service test factories are located in `app/tests/factories/` and provide utilities for creating pre-configured service instances with appropriate mocks for testing. This follows the Factory Pattern, allowing for consistent service creation with configurable test dependencies.

Available factories:

1. **ChatServiceFactory**: Creates instances of `PremiumChatService` with mocked dependencies.
2. **ClimbingServiceFactory**: Creates instances of `LogbookOrchestrator` with mocked dependencies.
3. **GradeServiceFactory**: Creates instances of `GradeService` with configurable caching behavior and grade mappings.

Example usage:

```python
# Creating a chat service with mocked dependencies
service = await ChatServiceFactory.create_service(
    mock_redis=True,
    mock_llm=True,
    context_data={"user_info": "Test data"}
)

# Creating a climbing service with test data
climbing_service = await ClimbingServiceFactory.create_service(
    mock_db=True,
    mock_external_apis=True,
    test_climbs=[{"id": 1, "route": "Test Route", "grade": "5.10a"}]
)

# Creating a grade service with custom mappings and controlled cache behavior
grade_service = GradeServiceFactory.create_service(
    mock_cache=True,
    conversion_delay=0.1,  # Add delay to test caching
    grade_mappings=custom_grade_mappings
)

# Using the service mocks for assertions
service._test_mocks["llm_client"].generate_response.assert_called_once()
```

### Test Parameterization

Located in `app/tests/utils/parameterization.py`, these utilities help create parameterized tests:

- `TestCase`: A structured way to define test cases
- `auth_test_cases`: Generates authentication test cases
- `user_profile_test_cases`: Generates user profile test cases
- `subscription_test_cases`: Generates subscription management test cases
- `pagination_test_cases`: Generates pagination test cases

Example usage:

```python
@pytest.mark.parametrize(
    "test_case",
    auth_test_cases(),
    ids=lambda tc: tc.id
)
async def test_user_login(api_client: TestApiClient, test_case):
    # Make login request with test case input
    response = await api_client.post("/api/v1/auth/login", json=test_case.input)
    data = await api_client.parse_response(response)

    # Validate response matches expected result
    assert response.status_code == test_case.expected["status_code"]
    if "detail" in test_case.expected:
        assert data["detail"] == test_case.expected["detail"]
```

#### Example: Parameterized Testing for Services

A comprehensive example of parameterized testing for services can be found in `app/tests/unit/test_climbing_service_parameterized.py`. This demonstrates how to:

1. Define structured test cases separated from test logic
2. Create a test fixture that configures service behavior for each scenario
3. Use pytest's parameterization to run the same test with different inputs
4. Validate results based on expected outputs for each case

Here's an example from that file:

```python
# Define test cases for grade conversion
def grade_conversion_test_cases() -> List[TestCase]:
    """Generate test cases for grade conversion functionality."""
    return [
        TestCase(
            id="yds_to_french",
            input={
                "grade": "5.12a",
                "source_system": "yds",
                "target_system": "french"
            },
            expected={
                "converted_grade": "7a+",
                "status": "success"
            },
            description="Convert YDS to French grade"
        ),
        TestCase(
            id="invalid_grade",
            input={
                "grade": "invalid_grade",
                "source_system": "yds",
                "target_system": "french"
            },
            expected={
                "converted_grade": None,
                "status": "error",
                "error": "Invalid grade"
            },
            description="Invalid grade returns error"
        )
    ]

# Use the test cases in a parameterized test
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_case",
    grade_conversion_test_cases(),
    ids=[tc.id for tc in grade_conversion_test_cases()]
)
async def test_convert_grade(climbing_service_fixture, test_case):
    """Test grade conversion with different inputs."""
    # Get service and mock for testing
    service = climbing_service_fixture
    grade_service = service._test_mocks["grade_service"]

    # Extract test inputs
    grade = test_case.input["grade"]
    source_system = test_case.input["source_system"]
    target_system = test_case.input["target_system"]

    # Execute the function
    result = await grade_service.convert_grade_system(
        grade, source_system, target_system
    )

    # Verify results match expected output
    if test_case.expected.get("status") == "error":
        assert result is None
    else:
        assert result == test_case.expected["converted_grade"]
```

This approach makes tests more maintainable by:

- Clearly separating test data from test logic
- Making it easy to add new test cases without duplicating code
- Providing descriptive test IDs in test output
- Creating focused tests that verify one specific aspect of functionality

### Test Data Fixtures

Located in `app/tests/fixtures/test_data.py`, these utilities help generate test data:

- `load_fixture`: Loads data from JSON or YAML files
- `load_user_data`: Loads user test data
- `load_climb_data`: Loads climbing test data
- `create_user_data`: Generates user test data
- `create_climb_data`: Generates climbing session data with proper discipline field
- `create_conversation_data`: Generates conversation data

Example usage:

```python
def test_import_users(db_session):
    users = load_user_data()
    for user_data in users:
        # Create user in database
        user = User(**user_data)
        db_session.add(user)

    db_session.commit()

    # Verify users were created
    count = db_session.query(User).count()
    assert count == len(users)
```

## Implementation Notes and Testing Caveats

### API Client Implementation

- The `TestApiClient` uses `httpx.AsyncClient` with `ASGITransport` for direct testing of FastAPI applications
- For compatibility with newer versions of httpx (0.28+), we directly initialize the client with `ASGITransport(app=app)` rather than extracting it from TestClient
- Authentication is mocked for testing purposes, with support for real JWT token generation in integrated tests

### Service Factory Pattern

- Service factories provide a consistent way to create service instances with appropriate mocks
- Each factory stores references to mocks in `_test_mocks` dictionary for easy access in tests
- The factory pattern allows configuring different test scenarios with minimal code duplication
- Dependencies are properly typed with `AsyncMock` and `MagicMock` to provide autocomplete in tests

### Fixture Format Handling

- The `load_fixture` function supports JSON and YAML formats
- When testing with unsupported formats, the test validates that appropriate validation errors are raised
- Fixtures can be loaded from predefined paths or with full file paths for testing

### Performance Testing

- Tests for LRU caching behavior in `GradeService` use instrumentation to verify cache hits
- Instead of relying on timing, which can be unreliable in test environments, cache tests verify the underlying function is only called once per unique input
- Performance tests are designed to be deterministic and not affected by system load

### Known Warnings

- A pytest collection warning appears for `TestApiClient` because it has an `__init__` constructor
- This warning is expected and doesn't affect test functionality
- To suppress the warning, you can add a pytest marker or rename the class in a future update

## Running Tests

### Running Simplified Tests

```bash
# Run only basic tests that don't require complex fixtures
python -m pytest app/tests/test_basic.py app/tests/test_data_loading.py -v

# Run grade service tests
python -m pytest app/tests/test_grade_service.py -v

# Run service factory tests
python -m pytest app/tests/unit/test_service_factories.py -v
```

### Running All Tests

```bash
python -m pytest app/tests/
```

### Running Specific Test Categories

```bash
# Run only API tests
python -m pytest app/tests/ -m api

# Run only unit tests
python -m pytest app/tests/ -m unit

# Run only integration tests
python -m pytest app/tests/ -m integration
```

### Running Tests with Coverage

```bash
python -m pytest app/tests/ --cov=app --cov-report=term-missing
```

## Adding New Tests

When adding new tests:

1. Consider whether the test requires complex fixtures:
   - For independent utility tests, use the simplified approach
   - For full integration tests, use the complete fixture set
2. Place the test in the appropriate directory (unit, integration, or api)
3. Use pytest markers to categorize your test
4. Use existing fixtures and utilities where possible
5. Add new fixtures to the appropriate fixture file if needed
6. Follow the existing patterns for test organization
7. Use service factories for testing service components

Example test file structure:

```python
"""
Tests for user endpoints.
"""

import pytest
from fastapi import status

@pytest.mark.api
class TestUserEndpoints:

    @pytest.mark.asyncio
    async def test_get_user(self, api_client, test_user):
        # Test implementation...

    @pytest.mark.asyncio
    async def test_update_user(self, api_client, test_user):
        # Test implementation...
```

## Implementation Status

The test architecture specified in the PRD has been fully implemented, including:

- ✅ Directory structure for tests (unit, integration, api)
- ✅ Test data management with fixtures
- ✅ API testing framework with TestApiClient
- ✅ Response validators
- ✅ Service Test Factories for all main services
- ✅ Test parameterization utilities
- ✅ Environment configuration with TestSettings
- ✅ Comprehensive documentation in README.md and ARCHITECTURE.md

See the [ARCHITECTURE.md](./ARCHITECTURE.md) file for a comprehensive overview of the test architecture design principles, component interactions, and usage guidelines.

## Best Practices

1. **Use fixtures for setup and teardown**: Make use of the fixtures in `conftest.py` and specialized fixture modules.
2. **Use validators**: Validate API responses using the validator utilities.
3. **Use factories for service testing**: Create service instances with appropriate mocks using the factories.
4. **Parameterize tests**: Use the parameterization utilities to test multiple scenarios.
5. **Mock external services**: Use the mock fixtures for external services like OpenAI and Mountain Project.
6. **Clean up after tests**: Ensure that tests clean up any resources they create.
7. **Test for behavior, not implementation**: Focus on testing what functions do, not how they do it.
8. **Make tests deterministic**: Avoid tests that depend on timing, random numbers, or external systems when possible.
