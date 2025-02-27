# Send Sage Test Architecture

This document provides an in-depth overview of the Send Sage testing architecture, including design principles, component interactions, and usage guidelines.

## Architecture Overview

The Send Sage testing infrastructure follows a modular, layered architecture designed to support different testing needs from unit testing to integration testing and full API testing.

### Key Design Principles

1. **Separation of Concerns**: Each component has a clear, focused responsibility.
2. **Reusability**: Common testing patterns are abstracted into reusable components.
3. **Configurability**: Tests can be configured for different environments and scenarios.
4. **Isolation**: Tests are isolated from each other and from the external environment.
5. **Readability**: Tests should be easy to read and understand.

### Architecture Layers

The architecture is organized into the following layers:

1. **Configuration**: Centralized settings for test environments
2. **Test Data**: Static and dynamic test data generation
3. **Fixtures**: Reusable components for test setup and teardown
4. **Factories**: Service instance creation with appropriate mocks
5. **Utilities**: Helper functions for common testing patterns
6. **Tests**: The actual test implementations

## Component Interactions

The following diagram illustrates how components interact in a typical test:

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Test Settings  │──┬──▶│  Test Fixtures  │─────▶│  Test Instance  │
└─────────────────┘  │   └─────────────────┘      └─────────────────┘
                     │   ┌─────────────────┐             │
                     └──▶│ Service Factory │─────────────┘
                         └─────────────────┘
                                  ▲
                                  │
                         ┌─────────────────┐
                         │   Test Data     │
                         └─────────────────┘
```

## Key Components

### 1. Test Settings

The `TestSettings` class in `app/tests/config.py` provides centralized configuration for test environments. It includes:

- Path configurations
- Database settings
- Authentication settings
- Environment-specific configurations
- Performance testing parameters

Example usage:

```python
from app.tests.config import test_settings

def test_with_config():
    assert test_settings.TEST_ENV == "local"
    assert test_settings.MOCK_EXTERNAL_APIS is True
```

### 2. Test Data Management

Test data is managed through:

- Static fixtures in `app/tests/data/fixtures/`
- Data factory functions in `app/tests/fixtures/test_data.py`

Data factories provide consistent, reproducible test data with controlled randomness when needed:

```python
from app.tests.fixtures.test_data import create_user_data, create_climb_data

def test_with_generated_data():
    # Generate standard test user
    user = create_user_data()
    assert "email" in user
    assert "password" in user

    # Generate custom user
    admin = create_user_data(email_prefix="admin", experience_level="expert")
    assert admin["email"].startswith("admin")
    assert admin["experience_level"] == "expert"

    # Generate climb data for a specific user
    climbs = create_climb_data(user_id=user["id"], count=3)
    assert len(climbs) == 3
    assert all(climb["user_id"] == user["id"] for climb in climbs)
```

### 3. Service Factories

Service factories in `app/tests/factories/` create pre-configured service instances with appropriate mocks:

```python
from app.tests.factories import ChatServiceFactory

@pytest.mark.asyncio
async def test_with_chat_service():
    # Create a service with mocked dependencies
    service = await ChatServiceFactory.create_service()

    # Configure mock behavior
    service._test_mocks["llm_client"].generate_response.return_value = {
        "choices": [{"message": {"content": "Test response"}}]
    }

    # Test the service
    result = await service.generate_response("Test prompt")
    assert result == "Test response"
```

### 4. API Testing

API testing is facilitated by the `TestApiClient` class in `app/tests/utils/api_client.py`:

```python
from fastapi import status
from app.tests.utils.api_client import TestApiClient
from app.tests.utils.validators import validate_user_response

@pytest.mark.asyncio
async def test_get_user_endpoint(api_client: TestApiClient, test_user):
    # Authenticate
    await api_client.authenticate(user_id=test_user.id)

    # Make request
    response = await api_client.get(f"/api/v1/users/{test_user.id}")

    # Verify response
    assert response.status_code == status.HTTP_200_OK
    data = await api_client.parse_response(response)
    validate_user_response(data)
```

## Testing Patterns

### Unit Testing

Unit tests focus on testing individual functions and methods in isolation:

```python
def test_grade_conversion():
    grade_service = GradeService.get_instance()
    result = grade_service.convert_grade_system("5.10a", GradingSystem.YDS, GradingSystem.FRENCH)
    assert result == "6a"
```

### Integration Testing

Integration tests verify interactions between components:

```python
@pytest.mark.asyncio
async def test_logbook_import(db_session, test_user):
    # Create test dependencies
    db_service = DatabaseService(db_session)
    grade_service = GradeService.get_instance()

    # Create the orchestrator with real dependencies
    orchestrator = LogbookOrchestrator(
        db_service=db_service,
        grade_service=grade_service
    )

    # Test importing data
    result = await orchestrator.import_climbs(test_user.id, test_csv_data)

    # Verify results reflect proper integration
    assert result.imported_count == 5

    # Verify data was persisted
    climbs = await db_service.get_user_climbs(test_user.id)
    assert len(climbs) == 5
```

### API Testing

API tests verify the behavior of API endpoints:

```python
@pytest.mark.asyncio
async def test_create_climb(api_client: TestApiClient, test_user):
    # Authenticate
    await api_client.authenticate(user_id=test_user.id)

    # Create test data
    climb_data = {
        "route": "Test Route",
        "grade": "5.10a",
        "date": "2023-01-15",
        "send_status": "sent",
        "location": "Test Crag",
        "discipline": "Sport"
    }

    # Make request
    response = await api_client.post("/api/v1/climbs", json=climb_data)

    # Verify response
    assert response.status_code == status.HTTP_201_CREATED
    data = await api_client.parse_response(response)
    assert data["route"] == climb_data["route"]
    assert data["grade"] == climb_data["grade"]
```

## Test Organization

Tests are organized into directories based on their purpose:

- `app/tests/unit/` - Unit tests for individual components
- `app/tests/integration/` - Tests of component interactions
- `app/tests/api/` - API endpoint tests

### Fixture Organization

Fixtures are organized by domain in the `app/tests/fixtures/` directory:

- `climbing.py` - Climbing domain fixtures (grade systems, routes, user ticks)
- `chat.py` - Chat service fixtures (prompts, contexts, LLM responses)
- `auth.py` - Authentication fixtures (users, tokens, permissions)
- `services.py` - Service layer fixtures (mocked services)
- `database.py` - Database fixtures (sessions, connections)
- `redis.py` - Redis fixtures (clients, connections)
- `external_services.py` - External API mocks (OpenAI, Mountain Project)
- `test_data.py` - Test data generation utilities

The fixture organization follows these principles:

1. **Domain-Specific Grouping**: Fixtures are grouped by application domain
2. **Direct Import Strategy**: Core fixtures are imported directly in `conftest.py`
3. **Comprehensive Coverage**: Each domain has fixtures for both mocked data and services
4. **Factory Integration**: Fixtures work seamlessly with service factories

## Common Pitfalls and Solutions

### 1. Mocking AsyncIO Functions

When mocking async functions, use `AsyncMock` and await the mock calls:

```python
from unittest.mock import AsyncMock

async def test_async_function():
    # Create mock
    mock_client = AsyncMock()
    mock_client.get_data.return_value = {"key": "value"}

    # Use in test
    result = await mock_client.get_data()
    assert result["key"] == "value"

    # Verify call
    mock_client.get_data.assert_called_once()
```

### 2. Database Testing

Tests that require a database should use the database fixtures:

```python
@pytest.mark.asyncio
async def test_with_database(db_session):
    # Test with the database session
    result = await db_session.execute(...)
    # Assertions...
```

### 3. Handling External Service Dependencies

Always use the service factories to mock external services:

```python
@pytest.mark.asyncio
async def test_with_external_service():
    # Create service with mocked external dependencies
    service = await ClimbingServiceFactory.create_service(mock_external_apis=True)

    # Configure the mock
    service._test_mocks["mp_client"].search_routes.return_value = [...]

    # Test the function that uses the external service
    result = await service.find_similar_routes("Test Route")

    # Verify the external service was called correctly
    service._test_mocks["mp_client"].search_routes.assert_called_once_with("Test Route")
```

### 4. Async Test Collection in pytest

**Important**: When using pytest-asyncio, define async tests at the module level rather than inside test classes. Async tests defined within classes may not be properly collected by pytest-asyncio, even when properly marked with `@pytest.mark.asyncio`.

```python
# DO THIS: Module-level async tests work reliably
@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result == expected_value

# NOT THIS: Class-based async tests may not be collected properly
@pytest.mark.unit
class TestAsyncClass:
    @pytest.mark.asyncio
    async def test_async_method(self):
        result = await some_async_function()
        assert result == expected_value
```

If you need to organize related tests, consider using descriptive function names and grouping by filename instead of using test classes. Alternatively, ensure your pytest configuration properly supports class-based async tests with the specific version of pytest-asyncio you're using.

## Best Practices

1. **Test isolation**: Each test should be completely independent and not rely on the state from other tests.
2. **Use fixtures**: Use pytest fixtures for common setup and teardown operations.
3. **Descriptive names**: Use clear, descriptive test names that explain what is being tested.
4. **Arrange-Act-Assert**: Follow the AAA pattern in tests: Arrange (setup), Act (execute), Assert (verify).
5. **Test edge cases**: Include tests for edge cases and error conditions, not just the happy path.
6. **Mock external dependencies**: Never call real external services in tests.
7. **Clean up**: Always clean up resources created during tests, especially in fixtures.
8. **Use factory functions**: Use the factory functions to create test data and service instances.

## Contributing New Tests

When adding new tests:

1. Identify the appropriate test type (unit, integration, API)
2. Locate the corresponding directory
3. Create a new test file or add to an existing one
4. Use existing fixtures and factories
5. Follow the established patterns
6. Run the tests to ensure they pass
7. Update documentation if needed

## Conclusion

The Send Sage testing architecture provides a robust, flexible foundation for testing all aspects of the application. By following the patterns and principles outlined in this document, you can create reliable, maintainable tests that help ensure the quality of the application.
