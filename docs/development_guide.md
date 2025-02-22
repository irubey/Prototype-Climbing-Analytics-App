# Send Sage Development Guide

## Development Environment Setup

### Prerequisites

- Python 3.9+
- PostgreSQL 13+
- Redis
- Git
- VS Code (recommended)

### Initial Setup

1. **Clone Repository:**

```bash
git clone https://github.com/yourusername/sendsage.git
cd sendsage
```

2. **Create Virtual Environment:**

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

3. **Install Dependencies:**

```bash
pip install -r requirements-fastapi.txt
pip install -r requirements-dev.txt  # Development dependencies
```

4. **Setup Pre-commit Hooks:**

```bash
pre-commit install
```

### Environment Configuration

Create a `.env` file in the project root:

```env
# Development Settings
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=dev-secret-key

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost/sendsage_dev

# Stripe Test Keys
STRIPE_API_KEY=sk_test_...
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_test_...

# Email (Development)
GMAIL_USERNAME=dev@example.com
GMAIL_PASSWORD=dev-password
GMAIL_DEFAULT_SENDER=noreply@dev.sendsage.com
```

## Project Structure

```
sendsage/
├── app_fastapi/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       └── router.py
│   ├── core/
│   │   ├── auth.py
│   │   ├── config.py
│   │   └── logging.py
│   ├── db/
│   │   ├── base.py
│   │   └── session.py
│   ├── models/
│   │   ├── user.py
│   │   └── climbing.py
│   └── schemas/
│       ├── auth.py
│       └── climbing.py
├── tests/
│   ├── conftest.py
│   └── test_*.py
├── docs/
├── alembic/
└── requirements/
```

## Development Workflow

### Running the Application

1. **Start Development Server:**

```bash
uvicorn app_fastapi.main:app --reload
```

2. **Access API Documentation:**

- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

### Database Migrations

1. **Create Migration:**

```bash
alembic revision --autogenerate -m "description"
```

2. **Apply Migration:**

```bash
alembic upgrade head
```

3. **Rollback Migration:**

```bash
alembic downgrade -1
```

### Testing

1. **Run All Tests:**

```bash
pytest
```

2. **Run Specific Test File:**

```bash
pytest tests/test_auth.py
```

3. **Run with Coverage:**

```bash
pytest --cov=app_fastapi
```

### Code Quality

1. **Run Linter:**

```bash
flake8 app_fastapi tests
```

2. **Run Type Checker:**

```bash
mypy app_fastapi
```

3. **Format Code:**

```bash
black app_fastapi tests
```

## Development Guidelines

### Code Style

- Follow PEP 8 guidelines
- Use type hints
- Write docstrings for all public functions
- Keep functions focused and small
- Use meaningful variable names

Example:

```python
from typing import Optional
from datetime import datetime

def get_user_ticks(
    user_id: str,
    start_date: Optional[datetime] = None
) -> list[dict]:
    """
    Get user's climbing ticks within date range.

    Args:
        user_id: User's unique identifier
        start_date: Optional start date filter

    Returns:
        List of tick dictionaries
    """
    # Implementation
```

### API Development

1. **Creating New Endpoint:**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from app_fastapi.core.auth import get_current_user

router = APIRouter()

@router.get("/endpoint")
async def get_data(
    current_user = Depends(get_current_user)
):
    """Endpoint description."""
    try:
        # Implementation
        return {"data": result}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
```

2. **Schema Definition:**

```python
from pydantic import BaseModel, Field, ConfigDict

class RequestModel(BaseModel):
    field1: str = Field(..., description="Field description")
    field2: int = Field(ge=0, description="Must be non-negative")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "field1": "example value",
                "field2": 42
            }
        }
    )
```

### Testing Guidelines

1. **Test Structure:**

```python
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_feature(client: AsyncClient):
    """Test description."""
    # Arrange
    test_data = {"key": "value"}

    # Act
    response = await client.post("/endpoint", json=test_data)

    # Assert
    assert response.status_code == 200
    assert response.json()["key"] == "value"
```

2. **Using Fixtures:**

```python
@pytest.fixture
async def test_user(client: AsyncClient):
    """Create test user."""
    user_data = {
        "email": "test@example.com",
        "password": "TestPass123!"
    }
    response = await client.post("/auth/register", json=user_data)
    return response.json()
```

### Error Handling

1. **Custom Exceptions:**

```python
from app_fastapi.core.exceptions import SendSageException

class ResourceNotFound(SendSageException):
    def __init__(self, resource: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} not found"
        )
```

2. **Error Responses:**

```python
try:
    result = await db.execute(query)
    if not result:
        raise ResourceNotFound("User")
except SQLAlchemyError as e:
    logger.error(f"Database error: {e}")
    raise DatabaseError()
```

### Background Tasks

1. **Task Definition:**

```python
from fastapi import BackgroundTasks

async def process_data(user_id: str):
    """Background task implementation."""
    try:
        # Long-running process
        pass
    except Exception as e:
        logger.error(f"Task failed: {e}")

@router.post("/process")
async def start_process(
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Start background process."""
    background_tasks.add_task(process_data, current_user.id)
    return {"status": "processing"}
```

## Debugging

### VS Code Configuration

1. **Launch Configuration:**

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app_fastapi.main:app", "--reload"],
      "jinja": true
    }
  ]
}
```

2. **Debug Tools:**

```python
import pdb; pdb.set_trace()  # Traditional debugger
breakpoint()  # Python 3.7+ debugger
```

### Logging

```python
from app_fastapi.core.logging import logger

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)
```

## Performance Optimization

1. **Database Queries:**

```python
# Use specific columns
query = select(User.id, User.email).filter(User.is_active == True)

# Use joins efficiently
query = (
    select(UserTicks)
    .options(joinedload(UserTicks.user))
    .filter(UserTicks.user_id == user_id)
)
```

2. **Caching:**

```python
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache

@router.get("/cached-data")
@cache(expire=300)  # Cache for 5 minutes
async def get_cached_data():
    """Cached endpoint."""
    # Expensive operation
    return result
```

## Documentation

### API Documentation

1. **OpenAPI Schema:**

```python
@router.get("/endpoint", response_model=ResponseModel)
async def get_data(
    param: str = Query(..., description="Parameter description")
) -> dict:
    """
    Endpoint description.

    Args:
        param: Parameter details

    Returns:
        Dictionary containing response data

    Raises:
        HTTPException: When data is not found
    """
    pass
```

2. **Response Examples:**

```python
class ResponseModel(BaseModel):
    class Config:
        json_schema_extra = {
            "example": {
                "field": "value"
            }
        }
```

## Version Control

### Git Workflow

1. **Feature Development:**

```bash
git checkout -b feature/feature-name
# Make changes
git add .
git commit -m "feat: description"
git push origin feature/feature-name
```

2. **Commit Message Format:**

- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- style: Code style changes
- refactor: Code refactoring
- test: Test changes
- chore: Build/maintenance changes
